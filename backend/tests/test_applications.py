from collections.abc import Generator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


def register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={
            "name": email.split("@")[0],
            "email": email,
            "password": "correct horse battery staple",
            "confirm_password": "correct horse battery staple",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def job_payload() -> dict[str, str]:
    return {
        "title": "Backend Engineer",
        "company": "Northstar Labs",
        "description": "Build reliable APIs with Python and SQL.",
        "url": "https://example.com/jobs/backend",
        "location": "Remote",
    }


@pytest.fixture()
def client() -> Generator[TestClient, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
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


def test_application_crud_validation_and_ownership(client: TestClient) -> None:
    owner = register(client, "application-owner@example.com")
    other_user = register(client, "application-other@example.com")
    job_response = client.post("/api/jobs", headers=owner, json=job_payload())
    assert job_response.status_code == 201
    job_id = job_response.json()["id"]
    payload = {
        "job_id": job_id,
        "status": "applied",
        "application_date": "2026-09-01",
        "salary": 125000,
        "recruiter_email": "recruiter@example.com",
        "notes": "Follow up next week",
    }

    created = client.post("/api/applications", headers=owner, json=payload)
    assert created.status_code == 201
    application = created.json()
    assert application["company"] == "Northstar Labs"
    assert application["status"] == "applied"

    assert client.get(f"/api/applications/{application['id']}", headers=other_user).status_code == 404
    assert client.put(f"/api/applications/{application['id']}", headers=other_user, json=payload).status_code == 404
    assert client.delete(f"/api/applications/{application['id']}", headers=other_user).status_code == 404
    assert client.post("/api/applications", headers=other_user, json=payload).status_code == 404

    assert client.post("/api/applications", headers=owner, json=payload).status_code == 409
    assert client.post("/api/applications", headers=owner, json={**payload, "status": "unknown"}).status_code == 422
    assert client.post("/api/applications", headers=owner, json={**payload, "salary": -1}).status_code == 422

    updated = client.put(
        f"/api/applications/{application['id']}",
        headers=owner,
        json={**payload, "status": "interview", "salary": 130000},
    )
    assert updated.status_code == 200
    assert updated.json()["status"] == "interview"

    listed = client.get("/api/applications", headers=owner, params={"status": "interview", "search": "Northstar"})
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [application["id"]]

    assert client.delete(f"/api/applications/{application['id']}", headers=owner).status_code == 204
    assert client.get(f"/api/applications/{application['id']}", headers=owner).status_code == 404


def test_application_missing_resource_and_invalid_query(client: TestClient) -> None:
    headers = register(client, "application-validation@example.com")
    missing_id = "00000000-0000-0000-0000-000000000000"

    assert client.get(f"/api/applications/{missing_id}", headers=headers).status_code == 404
    assert client.get("/api/applications", headers=headers, params={"sort": "invalid"}).status_code == 422
    assert client.get("/api/applications", headers=headers, params={"search": "x" * 121}).status_code == 422
