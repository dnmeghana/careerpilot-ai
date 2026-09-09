from collections.abc import Generator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject, NumberObject
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


def pdf_bytes() -> bytes:
    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
    resources = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})})
    page[NameObject("/Resources")] = resources
    stream = DecodedStreamObject()
    stream.set_data(b"BT /F1 12 Tf 72 720 Td (CareerPilot resume) Tj ET")
    stream[NameObject("/Length")] = NumberObject(len(stream.get_data()))
    page[NameObject("/Contents")] = writer._add_object(stream)
    output = __import__("io").BytesIO()
    writer.write(output)
    return output.getvalue()


def register(client: TestClient, email: str) -> dict[str, str]:
    response = client.post("/api/auth/register", json={"name": email.split("@")[0], "email": email, "password": "correct horse battery staple", "confirm_password": "correct horse battery staple"})
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_resume_upload_list_active_delete_and_ownership(client: TestClient) -> None:
    owner = register(client, "owner@example.com")
    other_user = register(client, "other@example.com")
    upload = client.post("/api/resumes", headers=owner, files={"file": ("resume.pdf", pdf_bytes(), "application/pdf")})

    assert upload.status_code == 201
    resume = upload.json()
    assert resume["filename"] == "resume.pdf"
    assert resume["is_active"] is True
    assert "CareerPilot resume" in resume["extracted_text"]
    assert resume["extracted_text_preview"] == "CareerPilot resume"

    listed = client.get("/api/resumes", headers=owner)
    assert listed.status_code == 200
    assert listed.json()[0]["id"] == resume["id"]
    assert client.get(f"/api/resumes/{resume['id']}", headers=other_user).status_code == 404
    assert client.put(f"/api/resumes/{resume['id']}/active", headers=other_user).status_code == 404
    assert client.delete(f"/api/resumes/{resume['id']}", headers=other_user).status_code == 404

    deleted = client.delete(f"/api/resumes/{resume['id']}", headers=owner)
    assert deleted.status_code == 204
    assert client.get("/api/resumes", headers=owner).json() == []


def test_resume_rejects_non_pdf_and_oversize(client: TestClient) -> None:
    headers = register(client, "validation@example.com")
    assert client.post("/api/resumes", headers=headers, files={"file": ("resume.txt", b"hello", "text/plain")}).status_code == 415
    assert client.post("/api/resumes", headers=headers, files={"file": ("resume.pdf", b"%PDF" + b"x" * (10 * 1024 * 1024), "application/pdf")}).status_code == 413
