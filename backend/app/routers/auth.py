from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from ..auth import create_access_token, get_current_user, hash_password, verify_password
from ..database import get_db
from ..models import User
from ..schemas import TokenResponse, UserCreate, UserLogin, UserResponse

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