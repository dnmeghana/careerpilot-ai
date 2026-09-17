"""Comprehensive test suite for Job Title Matching, Scoring, and Verification.

Covers:
1. Exact title match
2. Partial title match
3. Title with specialization
4. Title with seniority
5. Software Developer vs Software Development Engineer equivalence
6. Unrelated titles containing the same keyword (negative / non-builder penalty)
7. Same title with different job/requisition IDs
8. Same title with different locations
9. Selected job vs current page mismatch (Playwright automation pause)
10. Match score API endpoint (/api/automation/jobs/match-score)
"""

import asyncio
import http.server
import json
import threading
from typing import Generator
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.automation.companies.registry import get_adapter_registry
from app.automation.engine import PlaywrightAutomationEngine
from app.automation.matcher import (
    JobMatchScorer,
    JobTitleNormalizer,
    SelectedJobIdentity,
    extract_requisition_id_from_url_or_text,
    verify_current_page_matches_selected_job,
)
from app.automation.state_machine import AutomationState
from app.database import Base, get_db
from app.main import app
from app.models import (
    Application,
    AutomationActionLog,
    AutomationRun,
    AutomationSetting,
    CandidateProfile,
    Resume,
    User,
)


# =========================================================================
# 1. Unit Tests for JobTitleNormalizer & JobMatchScorer
# =========================================================================

def test_1_exact_title_match():
    """Exact title match should yield 100% title score and high match."""
    scorer = JobMatchScorer()
    res = scorer.score_job(
        target_role="Software Developer",
        candidate_title="Software Developer",
    )
    assert res.is_match is True
    assert res.title_score == 100.0
    assert res.match_score >= 85.0
    assert "Exact" in res.reasons[0]


def test_2_partial_title_match():
    """Partial title match should flexibly match without naive substring check."""
    scorer = JobMatchScorer()
    res = scorer.score_job(
        target_role="Software Developer",
        candidate_title="Software Developer - Backend",
    )
    assert res.is_match is True
    assert res.title_score >= 80.0
    assert res.match_score >= 80.0


def test_3_title_with_specialization():
    """Title with matching specialization should score high; conflicting specialization should be penalized."""
    scorer = JobMatchScorer()
    
    # Matching specialization
    res_matching = scorer.score_job(
        target_role="Software Developer - Backend",
        candidate_title="Backend Software Developer",
    )
    assert res_matching.is_match is True
    assert res_matching.title_score >= 90.0

    # Divergent specialization
    res_divergent = scorer.score_job(
        target_role="Software Developer - Backend",
        candidate_title="Software Developer - Frontend",
    )
    # Backend vs Frontend specialization difference should trigger penalty
    assert res_divergent.title_score < res_matching.title_score


def test_4_title_with_seniority():
    """Seniority normalization should recognize roman numerals and levels."""
    p_ii = JobTitleNormalizer.parse("Software Developer II")
    assert p_ii.seniority_rank == 3
    assert p_ii.seniority == "II"

    p_sr = JobTitleNormalizer.parse("Senior Software Developer")
    assert p_sr.seniority_rank == 4
    assert p_sr.seniority == "senior"

    scorer = JobMatchScorer()
    res = scorer.score_job(
        target_role="Software Developer",
        candidate_title="Senior Software Developer",
    )
    assert res.is_match is True
    assert res.title_score >= 80.0


def test_5_software_developer_vs_software_development_engineer():
    """'Software Developer' and 'Software Development Engineer' are recognized synonyms."""
    p1 = JobTitleNormalizer.parse("Software Developer")
    p2 = JobTitleNormalizer.parse("Software Development Engineer")
    assert p1.core_role == "software developer"
    assert p2.core_role == "software developer"

    scorer = JobMatchScorer()
    title_score, reasons = scorer.calculate_title_similarity(
        "Software Developer", "Software Development Engineer"
    )
    assert title_score == 100.0


def test_6_unrelated_titles_with_same_keyword():
    """Titles with non-builder keywords (sales, support) must NOT match despite shared words."""
    scorer = JobMatchScorer()

    # Software Developer vs Software Sales Specialist
    res_sales = scorer.score_job(
        target_role="Software Developer",
        candidate_title="Software Sales Specialist",
    )
    assert res_sales.is_match is False
    assert res_sales.title_score < 40.0

    # Software Developer vs Customer Support for Software
    res_support = scorer.score_job(
        target_role="Software Developer",
        candidate_title="Customer Support for Software",
    )
    assert res_support.is_match is False
    assert res_support.title_score < 40.0


# =========================================================================
# 2. Strict Job Identity Verification Tests
# =========================================================================

def test_7_same_title_with_different_job_ids():
    """Even if titles match, different requisition IDs must fail verification."""
    selected_job = SelectedJobIdentity(
        company="Acme Corp",
        exact_title="Software Developer",
        job_url="https://jobs.acmeworks.com/positions/12345",
        job_id="job-uuid-1",
        requisition_id="REQ-12345",
        location="New York, NY",
    )

    # Current page is for a different requisition: REQ-67890
    result = verify_current_page_matches_selected_job(
        selected_job=selected_job,
        current_url="https://jobs.acmeworks.com/positions/67890?reqId=REQ-67890",
        page_title="Software Developer - Acme Corp",
        page_content="Requisition ID: REQ-67890. Looking for a Software Developer in New York.",
    )

    assert result.is_verified is False
    assert result.confidence == "LOW"
    assert any("mismatch" in r.lower() for r in result.mismatch_reasons)
    assert result.extracted_job_id in ("67890", "REQ-67890")


def test_8_same_title_with_different_locations():
    """Conflicting location between selected job and page must fail verification."""
    selected_job = SelectedJobIdentity(
        company="Acme Corp",
        exact_title="Software Developer",
        job_url="https://jobs.acmeworks.com/positions/12345",
        job_id="job-uuid-1",
        requisition_id=None,
        location="New York, NY",
    )

    # Page explicitly indicates London, UK
    result = verify_current_page_matches_selected_job(
        selected_job=selected_job,
        current_url="https://jobs.acmeworks.com/positions/12345",
        page_title="Software Developer - London, UK | Acme Corp",
        page_content="Office: London. We are seeking a developer based in London.",
    )

    assert result.is_verified is False
    assert result.confidence == "LOW"
    assert any("Location mismatch" in r for r in result.mismatch_reasons)


def test_same_job_with_title_formatting_variation_verified():
    """Portal adding company name or minor branding should verify successfully."""
    selected_job = SelectedJobIdentity(
        company="Stripe",
        exact_title="Software Developer - Backend",
        job_url="https://stripe.com/jobs/dev-123",
        requisition_id="dev-123",
        location="Remote",
    )

    result = verify_current_page_matches_selected_job(
        selected_job=selected_job,
        current_url="https://stripe.com/jobs/dev-123",
        page_title="Software Developer - Backend | Stripe Careers",
        page_content="Job ID: dev-123. Location: Remote. Apply now.",
    )

    assert result.is_verified is True
    assert result.confidence == "HIGH"


# =========================================================================
# 3. Playwright Automation Engine Integration Test: Job Mismatch Pause
# =========================================================================

class MockJobMismatchPortalHandler(http.server.SimpleHTTPRequestHandler):
    """Serves a page with a different job to trigger identity mismatch."""

    def do_GET(self) -> None:
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        if "/mismatched_job" in self.path:
            # Different job ID and role specialization
            html = """
            <!DOCTYPE html><html><head><title>Frontend Designer - REQ-99999</title></head><body>
            <h1>Frontend Designer</h1>
            <p>Requisition ID: REQ-99999</p>
            <p>Location: London</p>
            <button id="apply-btn">Apply</button>
            </body></html>
            """
        else:
            html = "<h1>404 Not Found</h1>"

        self.wfile.write(html.strip().encode("utf-8"))

    def log_message(self, format: str, *args) -> None:
        pass


@pytest.fixture(scope="module")
def mismatch_server() -> Generator[str, None, None]:
    server = http.server.HTTPServer(("127.0.0.1", 0), MockJobMismatchPortalHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


@pytest.fixture()
def db_session() -> Generator[Session, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    db = session_factory()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.mark.asyncio
async def test_9_playwright_selected_job_vs_page_mismatch_pauses_for_user(mismatch_server: str, db_session: Session):
    """Playwright automation should verify the page matches the selected job and pause when there's a mismatch."""
    user = User(
        id=uuid4(),
        email=f"mismatch_{uuid4().hex[:8]}@example.com",
        name="Jane Doe",
        password_hash="test",
    )
    db_session.add(user)
    db_session.flush()

    profile = CandidateProfile(
    id=uuid4(),
    user_id=user.id,
    phone="555-0199",
    location="New York, NY",
    )
    db_session.add(profile)

    resume = Resume(
        id=uuid4(),
        user_id=user.id,
        filename="resume.pdf",
        file_path="/tmp/resume.pdf",
        extracted_text="Python, FastAPI, Docker",
        is_active=True,
    )
    db_session.add(resume)

    settings = AutomationSetting(
    user_id=user.id,
    auto_submit=False,
    )
    db_session.add(settings)

    # We select a job for Backend Software Developer with REQ-12345 in New York
    selected_identity = SelectedJobIdentity(
        company="Generic Portal",
        exact_title="Software Developer - Backend",
        job_url=f"{mismatch_server}/mismatched_job",
        requisition_id="REQ-12345",
        location="New York, NY",
        source="portal",
    )

    run = AutomationRun(
        id=uuid4(),
        user_id=user.id,
        company="Generic Portal",
        job_title="Software Developer - Backend",
        job_url=f"{mismatch_server}/mismatched_job",
        status=AutomationState.JOB_SELECTED.value,
        current_step="Opening Job Posting",
        user_prompt_context_json=json.dumps({
            "selected_job_identity": selected_identity.to_dict()
        }),
    )
    db_session.add(run)
    db_session.commit()

    engine = PlaywrightAutomationEngine(
        headless=True,
        screenshots_dir="/tmp/careerpilot_test_screenshots",
    )

    result_run = await engine.execute_run(db_session, run.id)

    # Verify that the run halted at Job Identity Verification Mismatch
    assert result_run.status == AutomationState.WAITING_FOR_USER.value
    assert result_run.requires_user_action is True
    assert result_run.current_step == "Job Identity Verification Mismatch"
    assert "Job identity verification failed" in (result_run.user_prompt or "")

    # Verify action log recorded the mismatch
    logs = db_session.query(AutomationActionLog).filter(AutomationActionLog.run_id == run.id).all()
    verify_log = next((l for l in logs if l.action_type == "verify_job_identity"), None)
    assert verify_log is not None
    assert verify_log.result == "mismatch"
    assert verify_log.confidence == "LOW"


# =========================================================================
# 4. API Test for Job Match Score Endpoint
# =========================================================================

def test_10_api_match_score_endpoint():
    """Test POST /api/automation/jobs/match-score calculates multi-factor score via API."""
    from app.routers.auth import get_current_user

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine, autoflush=False, autocommit=False)

    test_user = User(
        id=uuid4(),
        name="Test User",
        email="test_score@example.com",
        password_hash="test",
    )

    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = lambda: test_user
    with TestClient(app) as client:
        # Match case
        response = client.post(
            "/api/automation/jobs/match-score",
            json={
                "target_role": "Software Developer",
                "candidate_title": "Software Development Engineer II",
                "candidate_skills": ["Python", "Docker", "PostgreSQL"],
                "user_skills": ["Python", "Docker"],
                "candidate_location": "New York, NY",
                "user_location": "New York, NY",
            },
        )
        assert response.status_code == 200
        data = response.json()
        assert data["is_match"] is True
        assert data["title_score"] >= 80.0
        assert data["match_score"] >= 80.0
        assert "score_breakdown" in data

        # Unrelated case
        response_unrelated = client.post(
            "/api/automation/jobs/match-score",
            json={
                "target_role": "Software Developer",
                "candidate_title": "Software Sales Associate",
            },
        )
        assert response_unrelated.status_code == 200
        data_unrelated = response_unrelated.json()
        assert data_unrelated["is_match"] is False
        assert data_unrelated["title_score"] < 40.0

    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()
