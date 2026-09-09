from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
from app.database import Base, get_db
from app.main import app


@pytest.fixture()
def client(tmp_path: Path) -> Generator[TestClient, None, None]:
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


def register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/auth/register", json={"name": email.split("@")[0], "email": email, "password": "correct horse battery staple", "confirm_password": "correct horse battery staple"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_job_crud_validation_and_ownership(client: TestClient) -> None:
    owner = register(client, "job-owner@example.com")
    other_user = register(client, "job-other@example.com")
    payload = {
        "title": "Senior Product Designer",
        "company": "Northstar Labs",
        "description": "Design the next generation of workflow tools.",
        "url": "https://example.com/jobs/123",
        "location": "Remote",
    }

    created = client.post("/api/jobs", headers=owner, json=payload)
    assert created.status_code == 201
    job = created.json()
    assert job["title"] == payload["title"]
    assert job["company"] == payload["company"]

    listed = client.get("/api/jobs", headers=owner)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [job["id"]]
    assert client.get(f"/api/jobs/{job['id']}", headers=owner).json()["location"] == "Remote"

    assert client.get(f"/api/jobs/{job['id']}", headers=other_user).status_code == 404
    assert client.put(f"/api/jobs/{job['id']}", headers=other_user, json=payload).status_code == 404
    assert client.delete(f"/api/jobs/{job['id']}", headers=other_user).status_code == 404

    updated = {**payload, "title": "Lead Product Designer", "location": None}
    response = client.put(f"/api/jobs/{job['id']}", headers=owner, json=updated)
    assert response.status_code == 200
    assert response.json()["title"] == "Lead Product Designer"
    assert response.json()["location"] is None

    assert client.post("/api/jobs", headers=owner, json={**payload, "title": " "}).status_code == 422
    assert client.delete(f"/api/jobs/{job['id']}", headers=owner).status_code == 204
    assert client.get("/api/jobs", headers=owner).json() == []