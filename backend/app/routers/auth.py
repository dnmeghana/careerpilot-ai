import hashlib
import secrets
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..config import get_settings
from ..database import get_db
from ..models import User
from ..schemas import TokenResponse, UserCreate, UserLogin, UserResponse
from ..models import PasswordResetToken, User
from ..schemas import (
    ForgotPasswordRequest,
    ForgotPasswordResponse,
    ResetPasswordRequest,
    ResetPasswordResponse,
    TokenResponse,
    UserCreate,
    UserLogin,
    UserResponse,
)
from ..services.email_service import BaseEmailService, get_email_service

router = APIRouter(prefix="/api/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new account",
    description="Create an account with a validated email and password, then return a bearer access token.",
    responses={409: {"description": "An account with this email already exists."}},
)
def register(user_data: UserCreate, database: Session = Depends(get_db)) -> TokenResponse:
    email = user_data.email.lower()
    if database.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists")

    user = User(name=user_data.name, email=email, password_hash=hash_password(user_data.password))
    database.add(user)
    try:
        database.commit()
    except IntegrityError:
        database.rollback()
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="An account with this email already exists") from None
    database.refresh(user)
    return TokenResponse(access_token=create_access_token(user.id), user=user)
    return TokenResponse(access_token=create_access_token(user.id, token_version=user.token_version), user=user)


@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Log in",
    description="Verify credentials and return a bearer access token for the account.",
    responses={401: {"description": "The email or password is invalid."}},
)
def login(credentials: UserLogin, database: Session = Depends(get_db)) -> TokenResponse:
    user = database.scalar(select(User).where(User.email == credentials.email.lower()))
    if user is None or not verify_password(credentials.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password", headers={"WWW-Authenticate": "Bearer"})
    return TokenResponse(access_token=create_access_token(user.id), user=user)
    return TokenResponse(access_token=create_access_token(user.id, token_version=user.token_version), user=user)


@router.get(
    "/me",
    response_model=UserResponse,
    tags=["Users"],
    summary="Get the current user",
    description="Return the profile for the authenticated user represented by the bearer token.",
    responses={401: {"description": "Authentication token is missing or invalid."}},
)
def me(current_user: User = Depends(get_current_user)) -> User:
    return current_user


@router.post(
    "/forgot-password",
    response_model=ForgotPasswordResponse,
    summary="Request a password reset link",
    description="Generate a secure single-use reset token and send a reset email if the account exists.",
)
def forgot_password(
    req: ForgotPasswordRequest,
    database: Session = Depends(get_db),
    email_service: BaseEmailService = Depends(get_email_service),
) -> ForgotPasswordResponse:
    settings = get_settings()
    email = req.email.lower()
    user = database.scalar(select(User).where(User.email == email))

    generic_message = "If an account exists for this email address, a password reset link has been generated."
    dev_reset_url: str | None = None

    if user is not None:
        now = datetime.now(timezone.utc)
        # Invalidate existing active tokens for this user
        existing_tokens = database.scalars(
            select(PasswordResetToken).where(
                PasswordResetToken.user_id == user.id,
                PasswordResetToken.used_at.is_(None),
            )
        ).all()
        for t in existing_tokens:
            t.used_at = now

        raw_token = secrets.token_urlsafe(32)
        token_hash = hashlib.sha256(raw_token.encode("utf-8")).hexdigest()
        expires_at = now + timedelta(minutes=settings.password_reset_token_expire_minutes)

        reset_token_record = PasswordResetToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=expires_at,
        )
        database.add(reset_token_record)
        database.commit()

        reset_url = f"{settings.frontend_url.rstrip('/')}/reset-password?token={raw_token}"
        email_service.send_password_reset_email(to_email=user.email, reset_url=reset_url)

        if settings.environment == "development":
            dev_reset_url = reset_url

    return ForgotPasswordResponse(message=generic_message, dev_reset_url=dev_reset_url)


@router.post(
    "/reset-password",
    response_model=ResetPasswordResponse,
    summary="Reset account password",
    description="Reset password using a valid, unused, non-expired password reset token.",
    responses={
        400: {"description": "Invalid, expired, or previously used reset token."},
        422: {"description": "Validation error for password format or confirmation match."},
    },
)
def reset_password(
    req: ResetPasswordRequest,
    database: Session = Depends(get_db),
) -> ResetPasswordResponse:
    token_hash = hashlib.sha256(req.token.encode("utf-8")).hexdigest()
    reset_token = database.scalar(
        select(PasswordResetToken).where(PasswordResetToken.token_hash == token_hash)
    )

    now = datetime.now(timezone.utc)
    if (
        reset_token is None
        or reset_token.used_at is not None
        or (reset_token.expires_at.tzinfo is not None and reset_token.expires_at < now)
        or (reset_token.expires_at.tzinfo is None and reset_token.expires_at < now.replace(tzinfo=None))
    ):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset link. Please request a new one.",
        )

    user = database.scalar(select(User).where(User.id == reset_token.user_id))
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired password reset link. Please request a new one.",
        )

    user.password_hash = hash_password(req.new_password)
    user.token_version = (user.token_version or 1) + 1
    reset_token.used_at = now

    database.commit()

    return ResetPasswordResponse(
        message="Your password has been reset successfully. You can now log in with your new password."
    )