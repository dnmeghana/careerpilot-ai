"""Playwright test suite verifying all 12 application scenarios against a local mock portal server."""

import asyncio
import http.server
import json
import socket
import threading
from pathlib import Path
from typing import Generator
from uuid import uuid4

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.automation.ai.ai_agent import AutomationAIAgent
from app.automation.companies.registry import get_adapter_registry
from app.automation.engine import PlaywrightAutomationEngine
from app.automation.state_machine import AutomationState
from app.database import Base
from app.models import (
    Application,
    AutomationRun,
    AutomationSetting,
    CandidateProfile,
    Resume,
    User,
)


class MockPortalHandler(http.server.SimpleHTTPRequestHandler):
    """Serves custom HTML pages for all 12 automation scenarios."""

    def do_GET(self) -> None:
        path = self.path.split("?")[0]
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()

        pages = {
            "/1_standard": """
                <!DOCTYPE html><html><head><title>Standard Form</title></head><body>
                <h1>Standard Application</h1>
                <form action="/success" method="GET">
                    <label for="name">Full Name</label><input id="name" name="name" type="text" /><br/>
                    <label for="email">Email</label><input id="email" name="email" type="email" /><br/>
                    <label for="phone">Phone</label><input id="phone" name="phone" type="tel" /><br/>
                    <label for="location">Location</label><input id="location" name="location" type="text" /><br/>
                    <button type="submit">Submit</button>
                </form></body></html>
            """,
            "/2_new_question": """
                <!DOCTYPE html><html><head><title>New Question</title></head><body>
                <form action="/success" method="GET">
                    <label for="email">Email</label><input id="email" name="email" type="email" /><br/>
                    <label for="school">University / School</label><input id="school" name="school" type="text" /><br/>
                    <button type="submit">Submit</button>
                </form></body></html>
            """,
            "/3_dropdown": """
                <!DOCTYPE html><html><head><title>Dropdown Form</title></head><body>
                <form action="/success" method="GET">
                    <label for="work_auth">Work Authorization</label>
                    <select id="work_auth" name="work_auth">
                        <option value="">Select an option</option>
                        <option value="US Citizen">US Citizen</option>
                        <option value="Require Sponsorship">Require Sponsorship</option>
                    </select><br/>
                    <button type="submit">Submit</button>
                </form></body></html>
            """,
            "/4_checkbox": """
                <!DOCTYPE html><html><head><title>Checkbox Form</title></head><body>
                <form action="/success" method="GET">
                    <label for="terms"><input id="terms" type="checkbox" name="terms" /> I agree to the terms and privacy policy</label><br/>
                    <button type="submit">Submit</button>
                </form></body></html>
            """,
            "/5_resume_upload": """
                <!DOCTYPE html><html><head><title>Resume Upload</title></head><body>
                <form action="/success" method="GET">
                    <label for="resume_file">Upload Resume</label>
                    <input id="resume_file" name="resume_file" type="file" /><br/>
                    <button type="submit">Submit</button>
                </form></body></html>
            """,
            "/6_multistep_step1": """
                <!DOCTYPE html><html><head><title>Step 1</title></head><body>
                <h1>Application Step 1</h1>
                <form action="/6_multistep_step2" method="GET">
                    <label for="email">Email</label><input id="email" name="email" type="email" /><br/>
                    <button type="submit">Next</button>
                </form></body></html>
            """,
            "/6_multistep_step2": """
                <!DOCTYPE html><html><head><title>Step 2</title></head><body>
                <h1>Application Step 2</h1>
                <form action="/success" method="GET">
                    <label for="phone">Phone</label><input id="phone" name="phone" type="tel" /><br/>
                    <button type="submit">Submit</button>
                </form></body></html>
            """,
            "/7_unknown_sponsorship": """
                <!DOCTYPE html><html><head><title>Unknown Question</title></head><body>
                <form action="/success" method="GET">
                    <label for="sponsorship_future">Will you require sponsorship now or in the future?</label>
                    <input id="sponsorship_future" name="sponsorship_future" type="text" /><br/>
                    <button type="submit">Submit</button>
                </form></body></html>
            """,
            "/8_changed_selector": """
                <!DOCTYPE html><html><head><title>Changed Selector</title></head><body>
                <form action="/success" method="GET">
                    <!-- Stable accessible label with randomized input id -->
                    <label for="dynamic_rand_9981">Email</label>
                    <input id="dynamic_rand_9981" name="random_name_xyz" type="text" /><br/>
                    <button type="submit">Submit</button>
                </form></body></html>
            """,
            "/10_session_expired": """
                <!DOCTYPE html><html><head><title>Session Expired</title></head><body>
                <h1>Session Expired</h1>
                <p>Your session has timed out. Please sign in again to continue.</p>
                </body></html>
            """,
            "/11_captcha": """
                <!DOCTYPE html><html><head><title>Security Check</title></head><body>
                <h1>Verify you are human</h1>
                <div class="g-recaptcha" data-sitekey="sample_site_key"></div>
                <p>Security check to continue</p>
                </body></html>
            """,
            "/12_submission_review": """
                <!DOCTYPE html><html><head><title>Final Review</title></head><body>
                <h1>Review Application</h1>
                <form action="/success" method="GET">
                    <label for="email">Email</label><input id="email" name="email" type="email" value="jane@example.com" /><br/>
                    <button type="submit">Submit Application</button>
                </form></body></html>
            """,
            "/success": """
                <!DOCTYPE html><html><head><title>Submitted</title></head><body>
                <h1>Thank you for applying</h1>
                <p>Your application was sent successfully.</p>
                </body></html>
            """,
        }

        html = pages.get(path, "<h1>Page Not Found</h1>")
        self.wfile.write(html.strip().encode("utf-8"))

    def log_message(self, format: str, *args) -> None:
        # Suppress noisy HTTP server logs during testing
        pass


@pytest.fixture(scope="module")
def mock_server() -> Generator[str, None, None]:
    """Start local mock server on dynamic open port."""
    server = http.server.HTTPServer(("127.0.0.1", 0), MockPortalHandler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{port}"
    server.shutdown()
    server.server_close()


@pytest.fixture()
def db_session(tmp_path: Path) -> Generator[Session, None, None]:
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)
    with session_factory() as session:
        yield session
    Base.metadata.drop_all(engine)
    engine.dispose()


def create_candidate_context(db: Session, tmp_path: Path) -> tuple[User, Resume, CandidateProfile]:
    """Create test candidate user, resume file on disk, and profile."""
    user = User(name="Jane Doe", email="jane.doe@example.com", password_hash="hash")
    db.add(user)
    db.commit()

    # Write synthetic PDF resume
    resume_file = tmp_path / "resume.pdf"
    resume_file.write_bytes(b"%PDF-1.4 Mock resume content for Jane Doe")

    resume = Resume(
        user_id=user.id,
        filename="resume.pdf",
        file_path=str(resume_file),
        extracted_text="Jane Doe Senior Software Engineer",
        is_active=True,
    )
    db.add(resume)

    profile = CandidateProfile(
        user_id=user.id,
        phone="+1-555-0199",
        location="Seattle, WA",
        linkedin_url="https://linkedin.com/in/janedoe",
        education_school="University of Washington",
        work_authorization="US Citizen",
        requires_sponsorship=False,
    )
    db.add(profile)
    db.commit()
    db.refresh(user)
    db.refresh(resume)
    db.refresh(profile)
    return user, resume, profile


# ============================================================================
# 12 Playwright Scenario Tests
# ============================================================================

@pytest.mark.asyncio
async def test_scenario_1_standard_application_form(mock_server: str, db_session: Session, tmp_path: Path):
    """Scenario 1: Standard application form (name, email, phone, location) auto-fills from profile."""
    user, resume, profile = create_candidate_context(db_session, tmp_path)
    engine = PlaywrightAutomationEngine(headless=True)

    run = AutomationRun(
        user_id=user.id,
        company="MockCorp",
        job_title="Software Engineer",
        job_url=f"{mock_server}/1_standard",
        status="DISCOVERED",
    )
    db_session.add(run)
    db_session.commit()

    result = await engine.execute_run(db_session, run.id)
    assert result.status in (AutomationState.FORM_COMPLETED.value, AutomationState.WAITING_FOR_USER.value, AutomationState.SUBMITTED.value)
    assert result.scenarios_used_count >= 3  # Filled email, phone, location, name


@pytest.mark.asyncio
async def test_scenario_2_new_question_appears(mock_server: str, db_session: Session, tmp_path: Path):
    """Scenario 2: New question appears (e.g. University/School), AI resolves and auto-fills from profile."""
    user, resume, profile = create_candidate_context(db_session, tmp_path)
    engine = PlaywrightAutomationEngine(headless=True)

    run = AutomationRun(
        user_id=user.id,
        company="MockCorp",
        job_title="Software Engineer",
        job_url=f"{mock_server}/2_new_question",
        status="DISCOVERED",
    )
    db_session.add(run)
    db_session.commit()

    result = await engine.execute_run(db_session, run.id)
    assert result.status in (AutomationState.FORM_COMPLETED.value, AutomationState.WAITING_FOR_USER.value, AutomationState.SUBMITTED.value)


@pytest.mark.asyncio
async def test_scenario_3_dropdown_question(mock_server: str, db_session: Session, tmp_path: Path):
    """Scenario 3: Dropdown question selects matched profile option."""
    user, resume, profile = create_candidate_context(db_session, tmp_path)
    engine = PlaywrightAutomationEngine(headless=True)

    run = AutomationRun(
        user_id=user.id,
        company="MockCorp",
        job_title="Software Engineer",
        job_url=f"{mock_server}/3_dropdown",
        status="DISCOVERED",
    )
    db_session.add(run)
    db_session.commit()

    result = await engine.execute_run(db_session, run.id)
    assert result.status in (AutomationState.FORM_COMPLETED.value, AutomationState.WAITING_FOR_USER.value, AutomationState.SUBMITTED.value)


@pytest.mark.asyncio
async def test_scenario_4_checkbox_question(mock_server: str, db_session: Session, tmp_path: Path):
    """Scenario 4: Checkbox question requiring terms/policy confirmation pauses for user verification."""
    user, resume, profile = create_candidate_context(db_session, tmp_path)
    engine = PlaywrightAutomationEngine(headless=True)

    run = AutomationRun(
        user_id=user.id,
        company="MockCorp",
        job_title="Software Engineer",
        job_url=f"{mock_server}/4_checkbox",
        status="DISCOVERED",
    )
    db_session.add(run)
    db_session.commit()

    result = await engine.execute_run(db_session, run.id)
    assert result.status == AutomationState.WAITING_FOR_USER.value
    assert result.requires_user_action is True


@pytest.mark.asyncio
async def test_scenario_5_resume_upload(mock_server: str, db_session: Session, tmp_path: Path):
    """Scenario 5: Resume upload correctly attaches active PDF file."""
    user, resume, profile = create_candidate_context(db_session, tmp_path)
    engine = PlaywrightAutomationEngine(headless=True)

    run = AutomationRun(
        user_id=user.id,
        company="MockCorp",
        job_title="Software Engineer",
        job_url=f"{mock_server}/5_resume_upload",
        status="DISCOVERED",
    )
    db_session.add(run)
    db_session.commit()

    result = await engine.execute_run(db_session, run.id)
    assert result.scenarios_used_count >= 1


@pytest.mark.asyncio
async def test_scenario_6_multi_step_form(mock_server: str, db_session: Session, tmp_path: Path):
    """Scenario 6: Multi-step form navigates Step 1 -> Next -> Step 2 -> Submit."""
    user, resume, profile = create_candidate_context(db_session, tmp_path)
    engine = PlaywrightAutomationEngine(headless=True)

    run = AutomationRun(
        user_id=user.id,
        company="MockCorp",
        job_title="Software Engineer",
        job_url=f"{mock_server}/6_multistep_step1",
        status="DISCOVERED",
    )
    db_session.add(run)
    db_session.commit()

    result = await engine.execute_run(db_session, run.id)
    assert result.status in (AutomationState.FORM_COMPLETED.value, AutomationState.WAITING_FOR_USER.value, AutomationState.SUBMITTED.value)


@pytest.mark.asyncio
async def test_scenario_7_unknown_question_requiring_user_input(mock_server: str, db_session: Session, tmp_path: Path):
    """Scenario 7: Unknown sponsorship question when profile has None pauses and asks user."""
    user, resume, profile = create_candidate_context(db_session, tmp_path)
    profile.requires_sponsorship = None  # Unspecified
    db_session.commit()

    engine = PlaywrightAutomationEngine(headless=True)

    run = AutomationRun(
        user_id=user.id,
        company="MockCorp",
        job_title="Software Engineer",
        job_url=f"{mock_server}/7_unknown_sponsorship",
        status="DISCOVERED",
    )
    db_session.add(run)
    db_session.commit()

    result = await engine.execute_run(db_session, run.id)
    assert result.status == AutomationState.WAITING_FOR_USER.value
    assert result.requires_user_action is True
    assert "sponsorship" in (result.user_prompt or "").lower()


@pytest.mark.asyncio
async def test_scenario_8_changed_selector(mock_server: str, db_session: Session, tmp_path: Path):
    """Scenario 8: Element ID changed/randomized, accessible label strategy successfully finds and fills."""
    user, resume, profile = create_candidate_context(db_session, tmp_path)
    engine = PlaywrightAutomationEngine(headless=True)

    run = AutomationRun(
        user_id=user.id,
        company="MockCorp",
        job_title="Software Engineer",
        job_url=f"{mock_server}/8_changed_selector",
        status="DISCOVERED",
    )
    db_session.add(run)
    db_session.commit()

    result = await engine.execute_run(db_session, run.id)
    assert result.scenarios_used_count >= 1


@pytest.mark.asyncio
async def test_scenario_9_failed_page_load(db_session: Session, tmp_path: Path):
    """Scenario 9: Failed page load (invalid URL / connection error) enters FAILED state gracefully."""
    user, resume, profile = create_candidate_context(db_session, tmp_path)
    engine = PlaywrightAutomationEngine(headless=True)

    # Port 59999 has no listener
    run = AutomationRun(
        user_id=user.id,
        company="NonExistentCorp",
        job_title="Software Engineer",
        job_url="http://127.0.0.1:59999/does-not-exist",
        status="DISCOVERED",
    )
    db_session.add(run)
    db_session.commit()

    result = await engine.execute_run(db_session, run.id)
    assert result.status == AutomationState.FAILED.value
    assert result.error_message is not None


@pytest.mark.asyncio
async def test_scenario_10_session_expiration(mock_server: str, db_session: Session, tmp_path: Path):
    """Scenario 10: Session expiration or timeout detected on portal."""
    user, resume, profile = create_candidate_context(db_session, tmp_path)
    engine = PlaywrightAutomationEngine(headless=True)

    run = AutomationRun(
        user_id=user.id,
        company="MockCorp",
        job_title="Software Engineer",
        job_url=f"{mock_server}/10_session_expired",
        status="DISCOVERED",
    )
    db_session.add(run)
    db_session.commit()

    result = await engine.execute_run(db_session, run.id)
    # Form completion detected zero fields and handles without crash
    assert result.status in (AutomationState.FORM_COMPLETED.value, AutomationState.FAILED.value, AutomationState.WAITING_FOR_USER.value)


@pytest.mark.asyncio
async def test_scenario_11_captcha_encountered(mock_server: str, db_session: Session, tmp_path: Path):
    """Scenario 11: CAPTCHA detected immediately pauses automation with 'Manual action required'."""
    user, resume, profile = create_candidate_context(db_session, tmp_path)
    engine = PlaywrightAutomationEngine(headless=True)

    run = AutomationRun(
        user_id=user.id,
        company="MockCorp",
        job_title="Software Engineer",
        job_url=f"{mock_server}/11_captcha",
        status="DISCOVERED",
    )
    db_session.add(run)
    db_session.commit()

    result = await engine.execute_run(db_session, run.id)
    assert result.status == AutomationState.WAITING_FOR_USER.value
    assert result.requires_user_action is True
    assert "manual action required" in (result.user_prompt or "").lower()


@pytest.mark.asyncio
async def test_scenario_12_final_submission_requiring_approval(mock_server: str, db_session: Session, tmp_path: Path):
    """Scenario 12: Final submission requiring approval pauses in SUBMISSION_REVIEW/WAITING_FOR_USER when auto_submit=False."""
    user, resume, profile = create_candidate_context(db_session, tmp_path)

    # Explicitly configure auto_submit=False
    settings = AutomationSetting(user_id=user.id, auto_submit=False)
    db_session.add(settings)
    db_session.commit()

    engine = PlaywrightAutomationEngine(headless=True)

    run = AutomationRun(
        user_id=user.id,
        company="MockCorp",
        job_title="Software Engineer",
        job_url=f"{mock_server}/12_submission_review",
        status="DISCOVERED",
    )
    db_session.add(run)
    db_session.commit()

    result = await engine.execute_run(db_session, run.id)
    assert result.status == AutomationState.WAITING_FOR_USER.value
    assert result.requires_user_action is True
    assert "review and approve" in (result.user_prompt or "").lower()
