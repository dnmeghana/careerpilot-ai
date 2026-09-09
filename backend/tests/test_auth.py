from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


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

    app.dependency_overrides[get_db] = override_get_db
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


def test_successful_registration_returns_token_and_public_user(client: TestClient) -> None:
    response = client.post("/api/auth/register", json=registration_payload())

    assert response.status_code == 201
    body = response.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["user"]["email"] == "pilot@example.com"
    assert "password_hash" not in body["user"]


def test_duplicate_registration_returns_conflict(client: TestClient) -> None:
    client.post("/api/auth/register", json=registration_payload())

    response = client.post("/api/auth/register", json=registration_payload())

    assert response.status_code == 409


def test_successful_login_returns_token(client: TestClient) -> None:
    client.post("/api/auth/register", json=registration_payload())

    response = client.post(
        "/api/auth/login",
        json={"email": "PILOT@example.com", "password": "correct horse battery staple"},
    )

    assert response.status_code == 200
    assert response.json()["access_token"]
    assert "password_hash" not in response.json()["user"]


def test_invalid_password_returns_unauthorized(client: TestClient) -> None:
    client.post("/api/auth/register", json=registration_payload())

    response = client.post(
        "/api/auth/login",
        json={"email": "pilot@example.com", "password": "wrong password"},
    )

    assert response.status_code == 401


def test_registration_and_login_reject_invalid_input(client: TestClient) -> None:
    assert client.post("/api/auth/register", json=registration_payload("not-an-email")).status_code == 422
    assert client.post(
        "/api/auth/register",
        json={**registration_payload(), "password": "short", "confirm_password": "short"},
    ).status_code == 422
    assert client.post(
        "/api/auth/register",
        json={**registration_payload(), "confirm_password": "different password"},
    ).status_code == 422
    assert client.post("/api/auth/login", json={"email": "pilot@example.com", "password": ""}).status_code == 422


def test_malformed_and_expired_tokens_are_rejected(client: TestClient) -> None:
    assert client.get("/api/auth/me", headers={"Authorization": "Bearer malformed"}).status_code == 401
    registration = client.post("/api/auth/register", json=registration_payload("token@example.com"))
    token = registration.json()["access_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}.tampered"}).status_code == 401


def test_protected_endpoints_require_and_accept_token(client: TestClient) -> None:
    without_token = client.get("/api/auth/me")
    assert without_token.status_code == 401
    assert without_token.headers["www-authenticate"] == "Bearer"

    registration = client.post("/api/auth/register", json=registration_payload())
    headers = {"Authorization": f"Bearer {registration.json()['access_token']}"}

    me = client.get("/api/auth/me", headers=headers)
    dashboard = client.get("/api/dashboard", headers=headers)

    assert me.status_code == 200
    assert me.json()["email"] == "pilot@example.com"
    assert dashboard.status_code == 200
    assert dashboard.json()["stats"]["total_applications"] == 0