from collections.abc import Generator
from io import BytesIO

import pytest
from fastapi.testclient import TestClient
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject
from pypdf import PdfWriter
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.config import get_settings
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


def pdf_bytes() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 720 Td (Python SQL FastAPI resume experience) Tj ET")
    stream[NameObject("/Length")] = NumberObject(len(stream.get_data()))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


@pytest.fixture()
def client(tmp_path) -> Generator[TestClient, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    get_settings().resume_upload_dir = str(tmp_path / "resumes")

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


def test_analysis_requires_owned_resources_and_returns_skill_gap(client: TestClient) -> None:
    owner = register(client, "analysis-owner@example.com")
    other_user = register(client, "analysis-other@example.com")
    resume = client.post("/api/resumes", headers=owner, files={"file": ("resume.pdf", pdf_bytes(), "application/pdf")})
    assert resume.status_code == 201
    resume_id = resume.json()["id"]
    job = client.post(
        "/api/jobs",
        headers=owner,
        json={"title": "API Engineer", "company": "Northstar", "description": "Python SQL FastAPI", "url": "https://example.com/job"},
    )
    assert job.status_code == 201
    job_id = job.json()["id"]

    assert client.post("/api/analysis/resume-job", headers=other_user, json={"resume_id": resume_id, "job_id": job_id}).status_code == 404
    response = client.post("/api/analysis/resume-job", headers=owner, json={"resume_id": resume_id, "job_id": job_id})
    assert response.status_code == 201
    assert 0 <= response.json()["match_percentage"] <= 100
    assert response.json()["resume_id"] == resume_id

    skill_gap = client.get("/api/analysis/skill-gap", headers=owner)
    assert skill_gap.status_code == 200
    assert skill_gap.json()["has_analysis"] is True
    assert skill_gap.json()["job_id"] == job_id
    assert client.get("/api/analysis/skill-gap", headers=other_user).json()["has_analysis"] is False


def test_analysis_rejects_missing_resources_and_missing_description(client: TestClient) -> None:
    headers = register(client, "analysis-invalid@example.com")
    missing_id = "00000000-0000-0000-0000-000000000000"
    assert client.post("/api/analysis/resume-job", headers=headers, json={"resume_id": missing_id, "job_id": missing_id}).status_code == 404
    assert client.post("/api/analysis/resume-job", headers=headers, json={"resume_id": "not-a-uuid", "job_id": missing_id}).status_code == 422

    job = client.post("/api/jobs", headers=headers, json={"title": "No Description", "company": "Northstar"})
    assert job.status_code == 201
    assert client.get("/api/analysis/skill-gap", headers=headers).json()["has_analysis"] is False


def test_dashboard_analytics_are_scoped_to_user(client: TestClient) -> None:
    owner = register(client, "analytics-owner@example.com")
    other_user = register(client, "analytics-other@example.com")
    job = client.post("/api/jobs", headers=owner, json={"title": "Analyst", "company": "Northstar", "description": "Analyze data"}).json()
    application = client.post("/api/applications", headers=owner, json={"job_id": job["id"], "status": "offer", "salary": 100000})
    assert application.status_code == 201

    dashboard = client.get("/api/dashboard", headers=owner)
    assert dashboard.status_code == 200
    assert dashboard.json()["stats"] == {"total_applications": 1, "interviews": 0, "offers": 1, "rejections": 0, "success_rate": 100.0}
    assert len(dashboard.json()["recent_applications"]) == 1
    assert client.get("/api/dashboard", headers=other_user).json()["stats"]["total_applications"] == 0
