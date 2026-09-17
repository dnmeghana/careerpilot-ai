from collections.abc import Generator
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base, get_db
from app.main import app
from app.models import PasswordResetToken, User
from app.services.email_service import get_email_service, ConsoleEmailService


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    def override_get_db() -> Generator[Session, None, None]:
        database = session_factory()
        try:
            yield database
        finally:
            database.close()

    email_service = ConsoleEmailService()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_email_service] = lambda: email_service

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def registration_payload(email: str = "pilot@example.com") -> dict[str, str]:
    return {
        "name": "Test Pilot",
        "email": email,
        "password": "correct horse battery staple",
        "confirm_password": "correct horse battery staple",
    }


def test_forgot_password_existing_user_returns_generic_message(client: TestClient) -> None:
    client.post("/api/auth/register", json=registration_payload())

    response = client.post("/api/auth/forgot-password", json={"email": "pilot@example.com"})

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "If an account exists for this email address, a password reset link has been generated."
    assert body["dev_reset_url"] is not None
    assert "/reset-password?token=" in body["dev_reset_url"]


def test_forgot_password_non_existing_user_returns_identical_generic_message(client: TestClient) -> None:
    response = client.post("/api/auth/forgot-password", json={"email": "unknown@example.com"})

    assert response.status_code == 200
    body = response.json()
    assert body["message"] == "If an account exists for this email address, a password reset link has been generated."
    assert body["dev_reset_url"] is None


def test_reset_password_success(client: TestClient) -> None:
    # 1. Register user
    reg_resp = client.post("/api/auth/register", json=registration_payload())
    old_jwt = reg_resp.json()["access_token"]

    # 2. Request reset link
    forgot_resp = client.post("/api/auth/forgot-password", json={"email": "pilot@example.com"})
    dev_url = forgot_resp.json()["dev_reset_url"]
    token = dev_url.split("token=")[1]

    # 3. Reset password
    reset_resp = client.post(
        "/api/auth/reset-password",
        json={
            "token": token,
            "new_password": "brand new secret password",
            "confirm_password": "brand new secret password",
        },
    )
    assert reset_resp.status_code == 200
    assert "successfully" in reset_resp.json()["message"]

    # 4. Old password fails
    old_login = client.post(
        "/api/auth/login",
        json={"email": "pilot@example.com", "password": "correct horse battery staple"},
    )
    assert old_login.status_code == 401

    # 5. New password succeeds
    new_login = client.post(
        "/api/auth/login",
        json={"email": "pilot@example.com", "password": "brand new secret password"},
    )
    assert new_login.status_code == 200
    assert new_login.json()["access_token"]

    # 6. Prior active JWT session is invalidated
    me_resp = client.get("/api/auth/me", headers={"Authorization": f"Bearer {old_jwt}"})
    assert me_resp.status_code == 401


def test_reset_password_cannot_reuse_token(client: TestClient) -> None:
    client.post("/api/auth/register", json=registration_payload())
    forgot_resp = client.post("/api/auth/forgot-password", json={"email": "pilot@example.com"})
    token = forgot_resp.json()["dev_reset_url"].split("token=")[1]

    # First use
    client.post(
        "/api/auth/reset-password",
        json={
            "token": token,
            "new_password": "brand new secret password",
            "confirm_password": "brand new secret password",
        },
    )

    # Second use must fail
    second_resp = client.post(
        "/api/auth/reset-password",
        json={
            "token": token,
            "new_password": "another new secret password",
            "confirm_password": "another new secret password",
        },
    )
    assert second_resp.status_code == 400
    assert "Invalid or expired" in second_resp.json()["detail"]


def test_reset_password_invalid_token(client: TestClient) -> None:
    resp = client.post(
        "/api/auth/reset-password",
        json={
            "token": "completely-invalid-token",
            "new_password": "brand new secret password",
            "confirm_password": "brand new secret password",
        },
    )
    assert resp.status_code == 400
    assert "Invalid or expired" in resp.json()["detail"]


def test_reset_password_expired_token(client: TestClient) -> None:
    client.post("/api/auth/register", json=registration_payload())
    forgot_resp = client.post("/api/auth/forgot-password", json={"email": "pilot@example.com"})
    token = forgot_resp.json()["dev_reset_url"].split("token=")[1]

    # Manually expire the token in database
    gen = app.dependency_overrides[get_db]()
    db = next(gen)
    token_record = db.scalar(select(PasswordResetToken))
    assert token_record is not None
    token_record.expires_at = datetime.now(timezone.utc) - timedelta(minutes=5)
    db.commit()
    db.close()

    resp = client.post(
        "/api/auth/reset-password",
        json={
            "token": token,
            "new_password": "brand new secret password",
            "confirm_password": "brand new secret password",
        },
    )
    assert resp.status_code == 400
    assert "Invalid or expired" in resp.json()["detail"]


def test_requesting_new_reset_invalidates_previous_token(client: TestClient) -> None:
    client.post("/api/auth/register", json=registration_payload())

    # First request
    resp1 = client.post("/api/auth/forgot-password", json={"email": "pilot@example.com"})
    token1 = resp1.json()["dev_reset_url"].split("token=")[1]

    # Second request
    resp2 = client.post("/api/auth/forgot-password", json={"email": "pilot@example.com"})
    token2 = resp2.json()["dev_reset_url"].split("token=")[1]
    assert token1 != token2

    # Using token 1 should fail because it was invalidated by token 2
    resp_fail = client.post(
        "/api/auth/reset-password",
        json={
            "token": token1,
            "new_password": "brand new secret password",
            "confirm_password": "brand new secret password",
        },
    )
    assert resp_fail.status_code == 400

    # Using token 2 should succeed
    resp_ok = client.post(
        "/api/auth/reset-password",
        json={
            "token": token2,
            "new_password": "brand new secret password",
            "confirm_password": "brand new secret password",
        },
    )
    assert resp_ok.status_code == 200


def test_reset_password_validation_failure(client: TestClient) -> None:
    # Mismatched passwords
    resp = client.post(
        "/api/auth/reset-password",
        json={
            "token": "some-token",
            "new_password": "password123",
            "confirm_password": "password456",
        },
    )
    assert resp.status_code == 422

    # Password too short
    resp2 = client.post(
        "/api/auth/reset-password",
        json={
            "token": "some-token",
            "new_password": "short",
            "confirm_password": "short",
        },
    )
    assert resp2.status_code == 422
