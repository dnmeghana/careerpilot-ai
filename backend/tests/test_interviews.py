from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.main import app


def register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/auth/register", json={"name": "Test Pilot", "email": email, "password": "correct horse battery staple", "confirm_password": "correct horse battery staple"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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


def test_interview_generation_and_progress(client: TestClient) -> None:
    owner = register(client, "interview-owner@example.com")
    other_user = register(client, "interview-other@example.com")
    job = client.post("/api/jobs", headers=owner, json={"title": "Backend Engineer", "company": "Northstar", "description": "Build reliable Python APIs with PostgreSQL."}).json()

    created = client.post("/api/interviews", headers=owner, json={"job_id": job["id"], "interview_type": "technical"})
    assert created.status_code == 201
    interview = created.json()
    assert interview["interview_type"] == "Technical"
    assert len(interview["questions"]) == 3
    assert all(question["suggested_answer"] and not question["completed"] for question in interview["questions"])
    assert all(question["category"] in {"Technical", "Behavioral", "Experience", "Problem Solving", "Role Specific"} for question in interview["questions"])
    regenerated = client.post(f"/api/interviews/{interview['id']}/regenerate", headers=owner, json={})
    assert regenerated.status_code == 200
    assert len(regenerated.json()["questions"]) == 3
    fetched = client.get(f"/api/interviews/{interview['id']}", headers=owner)
    assert fetched.status_code == 200
    assert fetched.json()["id"] == interview["id"]
    assert client.get(f"/api/interviews/{interview['id']}", headers=other_user).status_code == 404

    updated = client.patch(f"/api/interviews/{interview['id']}", headers=owner, json={"question_id": regenerated.json()["questions"][0]["id"], "completed": True, "notes": "Review API trade-offs."})
    assert updated.status_code == 200
    assert updated.json()["questions"][0]["completed"] is True
    assert updated.json()["notes"] == "Review API trade-offs."


def test_mock_interview_evaluates_answers_and_completes(client: TestClient) -> None:
    owner = register(client, "mock-owner@example.com")
    job = client.post("/api/jobs", headers=owner, json={"title": "Product Designer", "company": "Northstar", "description": "Design thoughtful product experiences."}).json()

    started = client.post("/api/mock-interviews", headers=owner, json={"job_id": job["id"], "interview_type": "behavioral"})
    assert started.status_code == 201
    mock_interview = started.json()
    assert len(mock_interview["questions"]) == 3
    assert mock_interview["current_question"] == 0

    for index, question in enumerate(mock_interview["questions"]):
        submitted = client.post(
            f"/api/mock-interviews/{mock_interview['id']}/answers/{question['id']}",
            headers=owner,
            json={"answer": f"I handled this situation carefully. The result was measurable improvement in step {index + 1}."},
        )
        assert submitted.status_code == 200
        mock_interview = submitted.json()
        assert mock_interview["questions"][index]["score"] is not None
        assert mock_interview["questions"][index]["feedback"]["weaknesses"]

    assert mock_interview["completed_at"] is not None
    assert 0 <= mock_interview["overall_score"] <= 100
    assert mock_interview["current_question"] == 3


def test_assistant_uses_owned_context(client: TestClient) -> None:
    owner = register(client, "assistant-owner@example.com")
    other_user = register(client, "assistant-other@example.com")
    job = client.post("/api/jobs", headers=owner, json={"title": "Data Analyst", "company": "Northstar", "description": "Analyze product metrics."}).json()

    response = client.post("/api/assistant/chat", headers=owner, json={"message": "How should I prepare for this role?", "job_id": job["id"]})
    assert response.status_code == 200
    assert response.json()["response"]
    assert any("Data Analyst" in label for label in response.json()["context_labels"])

    forbidden = client.post("/api/assistant/chat", headers=other_user, json={"message": "Tell me about this job.", "job_id": job["id"]})
    assert forbidden.status_code == 404