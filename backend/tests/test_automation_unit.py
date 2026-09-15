"""Comprehensive unit and API integration tests for CareerPilot V2 Automation."""

import json
from collections.abc import Generator
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.automation.ai.ai_agent import AutomationAIAgent
from app.automation.ai.unknown_scenario import UnknownScenario
from app.automation.companies.base import BaseCompanyAdapter, DiscoveredJob, StepResult
from app.automation.companies.registry import CompanyAdapterRegistry
from app.automation.confidence import ConfidenceLevel, evaluate_confidence
from app.automation.engine import PlaywrightAutomationEngine
from app.automation.scenarios.memory import ScenarioMemoryService
from app.automation.scenarios.registry import ScenarioRegistry
from app.automation.scheduler import AutomationScheduler
from app.automation.state_machine import (
    ApplicationStateMachine,
    AutomationState,
    InvalidStateTransitionError,
)
from app.database import Base, get_db
from app.main import app
from app.models import (
    Application,
    AutomationRun,
    AutomationScenario,
    AutomationSetting,
    CandidateProfile,
    Job,
    User,
)


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


def register_user(client: TestClient, email: str) -> dict[str, str]:
    response = client.post(
        "/api/auth/register",
        json={
            "name": "Jane Doe",
            "email": email,
            "password": "validPassword123!",
            "confirm_password": "validPassword123!",
        },
    )
    assert response.status_code == 201
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


# ============================================================================
# 1. State Machine Tests
# ============================================================================

def test_state_machine_valid_transitions_and_pause_resume():
    sm = ApplicationStateMachine(AutomationState.DISCOVERED)
    assert sm.current_state == AutomationState.DISCOVERED

    # Discovered -> Job Selected -> Application Started -> Form In Progress
    assert sm.transition(AutomationState.JOB_SELECTED) == AutomationState.JOB_SELECTED
    assert sm.transition(AutomationState.APPLICATION_STARTED) == AutomationState.APPLICATION_STARTED
    assert sm.transition(AutomationState.FORM_IN_PROGRESS) == AutomationState.FORM_IN_PROGRESS

    # Pause and Resume
    assert sm.pause() == AutomationState.PAUSED
    assert sm.resume() == AutomationState.FORM_IN_PROGRESS

    # Unknown Scenario -> AI Resolution -> Form In Progress
    assert sm.transition(AutomationState.UNKNOWN_SCENARIO) == AutomationState.UNKNOWN_SCENARIO
    assert sm.transition(AutomationState.AI_RESOLUTION) == AutomationState.AI_RESOLUTION
    assert sm.transition(AutomationState.FORM_IN_PROGRESS) == AutomationState.FORM_IN_PROGRESS

    # Form Completed -> Submission Review -> Submitted
    assert sm.transition(AutomationState.FORM_COMPLETED) == AutomationState.FORM_COMPLETED
    assert sm.transition(AutomationState.SUBMISSION_REVIEW) == AutomationState.SUBMISSION_REVIEW
    assert sm.transition(AutomationState.SUBMITTED) == AutomationState.SUBMITTED


def test_state_machine_invalid_transitions():
    sm = ApplicationStateMachine(AutomationState.DISCOVERED)
    with pytest.raises(InvalidStateTransitionError):
        sm.transition(AutomationState.SUBMITTED)

    sm = ApplicationStateMachine(AutomationState.SUBMITTED)
    with pytest.raises(InvalidStateTransitionError):
        sm.pause()


# ============================================================================
# 2. Company Adapter Registry Tests
# ============================================================================

class CustomAcmeAdapter(BaseCompanyAdapter):
    @property
    def company_name(self) -> str:
        return "AcmeCorp"

    def can_handle_url(self, url: str) -> bool:
        return "acmecorp.com" in url

    async def inspect_current_step(self, page):
        return StepResult(status="in_progress", step_name="Acme Apply")


def test_company_adapter_registration_and_dispatch():
    registry = CompanyAdapterRegistry()
    acme = CustomAcmeAdapter()
    registry.register(acme)

    assert registry.get_adapter_by_name("AcmeCorp") == acme
    assert registry.get_adapter_for_url("https://jobs.acmecorp.com/postings/123") == acme


# ============================================================================
# 3. Confidence System Tests
# ============================================================================

def test_confidence_evaluation():
    # Known scenario + reliable profile + stable selector = HIGH
    eval_high = evaluate_confidence(is_known_scenario=True, has_reliable_value=True, has_stable_selector=True)
    assert eval_high.level == ConfidenceLevel.HIGH
    assert eval_high.can_auto_execute is True

    # Missing value = LOW
    eval_low = evaluate_confidence(is_known_scenario=True, has_reliable_value=False, has_stable_selector=True)
    assert eval_low.level == ConfidenceLevel.LOW
    assert eval_low.requires_user_confirmation is True

    # Sensitive question = LOW
    eval_sensitive = evaluate_confidence(is_known_scenario=True, has_reliable_value=True, has_stable_selector=True, is_sensitive_question=True)
    assert eval_sensitive.level == ConfidenceLevel.LOW
    assert eval_sensitive.requires_user_confirmation is True

    # Final submission without auto-submit = MEDIUM confirmation
    eval_submit = evaluate_confidence(is_known_scenario=True, has_reliable_value=True, has_stable_selector=True, is_final_submission=True, user_auto_submit_enabled=False)
    assert eval_submit.requires_user_confirmation is True


# ============================================================================
# 4. Scenario Matching & Memory Persistence (Self-Healing)
# ============================================================================

def test_scenario_matching_and_memory_persistence():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    session_factory = sessionmaker(bind=engine)

    with session_factory() as db:
        user = User(name="Jane Doe", email="jane@example.com", password_hash="hash")
        db.add(user)
        db.commit()

        profile = CandidateProfile(
            user_id=user.id,
            phone="+15551234567",
            location="New York, NY",
            linkedin_url="https://linkedin.com/in/janedoe",
            requires_sponsorship=False,
            work_authorization="US Citizen",
        )
        db.add(profile)
        db.commit()

        registry = ScenarioRegistry()

        # Built-in scenario matching
        match_email = registry.match_field(db, user, "AnyCompany", "email", profile=profile)
        assert match_email is not None
        assert match_email.resolved_value == "jane@example.com"
        assert match_email.confidence == "HIGH"

        match_phone = registry.match_field(db, user, "AnyCompany", "phone", profile=profile)
        assert match_phone is not None
        assert match_phone.resolved_value == "+15551234567"

        # Save a new learned scenario into memory
        learned = ScenarioMemoryService.save_resolved_scenario(
            db=db,
            user_id=user.id,
            company="Stripe",
            field_key="favorite_framework",
            element_strategy={"label": "What is your favorite framework?"},
            action_type="fill",
            value_source="learned_answer",
            static_value="FastAPI",
            confidence="HIGH",
        )
        assert learned.times_used == 1

        # Subsequent run reuses the learned scenario!
        reused = registry.match_field(db, user, "Stripe", "favorite_framework", profile=profile)
        assert reused is not None
        assert reused.is_learned is True
        assert reused.resolved_value == "FastAPI"

    Base.metadata.drop_all(engine)


# ============================================================================
# 5. AI Reasoning Agent Fallback Tests
# ============================================================================

def test_ai_agent_fallback_and_safety():
    agent = AutomationAIAgent()
    user = User(name="Alex Smith", email="alex@example.com", password_hash="hash")
    profile = CandidateProfile(user_id=user.id, requires_sponsorship=None)  # Sponsorship unspecified

    # Scenario: Sponsorship question without profile info -> pauses and asks user
    scenario_sponsorship = UnknownScenario(
        company="Google",
        url="https://careers.google.com/jobs/1",
        page_title="Apply",
        current_step="Questions",
        field_label="Will you now or in the future require visa sponsorship?",
        input_type="select",
        options=["Yes", "No"],
    )

    result = agent.resolve_scenario(scenario_sponsorship, user, profile, None)
    assert result.requires_user_confirmation is True
    assert result.action_type == "ask_user"

    # Scenario: Legal declaration -> requires user confirmation
    scenario_legal = UnknownScenario(
        company="Google",
        url="https://careers.google.com/jobs/1",
        page_title="Apply",
        current_step="Agreements",
        field_label="I certify that all information submitted is true under penalty of perjury",
        input_type="checkbox",
    )
    res_legal = agent.resolve_scenario(scenario_legal, user, profile, None)
    assert res_legal.requires_user_confirmation is True
    assert res_legal.confidence == "LOW"


# ============================================================================
# 6. REST API Endpoints Tests (Profile, Runs, Scenarios, Settings)
# ============================================================================

def test_automation_api_endpoints(client: TestClient):
    auth_header = register_user(client, "automation-tester@example.com")

    # 1. Candidate Profile CRUD
    profile_res = client.get("/api/automation/profile", headers=auth_header)
    assert profile_res.status_code == 200
    assert profile_res.json()["phone"] is None

    update_res = client.put(
        "/api/automation/profile",
        headers=auth_header,
        json={
            "phone": "+1-800-555-0199",
            "location": "San Francisco, CA",
            "linkedin_url": "https://linkedin.com/in/alex",
            "work_authorization": "US Citizen",
            "requires_sponsorship": False,
        },
    )
    assert update_res.status_code == 200
    assert update_res.json()["phone"] == "+1-800-555-0199"
    assert update_res.json()["requires_sponsorship"] is False

    # 2. Automation Settings CRUD
    settings_res = client.get("/api/automation/settings", headers=auth_header)
    assert settings_res.status_code == 200
    assert settings_res.json()["schedule_interval"] == "manual"

    update_settings = client.put(
        "/api/automation/settings",
        headers=auth_header,
        json={"schedule_interval": "daily", "auto_submit": False, "max_daily_applications": 5},
    )
    assert update_settings.status_code == 200
    assert update_settings.json()["schedule_interval"] == "daily"
    assert update_settings.json()["max_daily_applications"] == 5

    # 3. Trigger run (with mocked execution)
    from unittest.mock import AsyncMock, patch

    async def mock_execute(db, run_id):
        run = db.get(AutomationRun, run_id)
        if run:
            run.status = "FORM_IN_PROGRESS"
            db.commit()

    with patch.object(PlaywrightAutomationEngine, "execute_run", side_effect=mock_execute):
        trigger_res = client.post(
            "/api/automation/runs/trigger",
            headers=auth_header,
            json={
                "company": "MockCorp",
                "job_title": "Platform Engineer",
                "job_url": "http://127.0.0.1:8899/jobs/platform",
            },
        )
        assert trigger_res.status_code == 201
        run_id = trigger_res.json()["id"]

        # 4. List runs
        runs_res = client.get("/api/automation/runs", headers=auth_header)
        assert runs_res.status_code == 200
        assert len(runs_res.json()) >= 1

        # 5. Pause run
        pause_res = client.post(f"/api/automation/runs/{run_id}/pause", headers=auth_header)
        assert pause_res.status_code == 200
        assert pause_res.json()["status"] == "PAUSED"

    # 6. Scenario Memory API
    scenarios_res = client.get("/api/automation/scenarios", headers=auth_header)
    assert scenarios_res.status_code == 200

    new_scen = client.post(
        "/api/automation/scenarios",
        headers=auth_header,
        json={
            "company": "Netflix",
            "field_key": "preferred_language",
            "element_strategy_json": json.dumps({"label": "Primary language"}),
            "action_type": "fill",
            "value_source": "static_value",
            "static_value": "Python",
            "confidence": "HIGH",
        },
    )
    assert new_scen.status_code == 201
    scen_id = new_scen.json()["id"]

    # Toggle scenario
    toggle_res = client.patch(
        f"/api/automation/scenarios/{scen_id}",
        headers=auth_header,
        json={"is_active": False},
    )
    assert toggle_res.status_code == 200
    assert toggle_res.json()["is_active"] is False

    # Delete scenario
    del_res = client.delete(f"/api/automation/scenarios/{scen_id}", headers=auth_header)
    assert del_res.status_code == 204


# ============================================================================
# 7. URL & Page Title Tracking and Access Denied Tests
# ============================================================================

def test_detect_access_denied():
    from app.automation.safety import detect_access_denied

    # Test title match
    blocked, reason = detect_access_denied("Normal body text", title="403 Forbidden - Access Denied")
    assert blocked is True
    assert "access was denied" in reason.lower()

    # Test cloudflare title
    blocked, reason = detect_access_denied("Checking your browser", title="Just a moment... | Cloudflare")
    assert blocked is True
    assert "cloudflare" in reason.lower()

    # Test body phrase match
    blocked, reason = detect_access_denied(
        "<h1>Error</h1><p>You don't have permission to access this resource. Ray ID: 12345</p>",
        title="Error"
    )
    assert blocked is True
    assert "access" in reason.lower()

    # Test normal page
    blocked, reason = detect_access_denied(
        "<h1>Welcome to Job Portal</h1><form><input name='name'/></form>",
        title="Careers at Acme"
    )
    assert blocked is False
    assert reason == ""


def test_api_returns_current_url_and_page_title(client: TestClient):
    auth_header = register_user(client, "url-tracker@example.com")

    # Directly verify through API with an injected run
    # Get the db session from dependency override or insert via endpoint
    from app.models import AutomationActionLog

    # Create run via trigger endpoint
    from unittest.mock import patch

    async def mock_execute_track(db, run_id):
        run = db.get(AutomationRun, run_id)
        if run:
            run.current_url = "https://amazon.jobs/en/jobs/123/apply"
            run.page_title = "Amazon Job Application - SDET"
            run.status = "WAITING_FOR_USER"
            run.requires_user_action = True
            run.user_prompt = "Access Denied: Cloudflare verification required"
            log = AutomationActionLog(
                run_id=run.id,
                action_type="PAUSE",
                step_name="Access Denied",
                confidence="LOW",
                confidence_reason="Access Denied detected: Cloudflare",
                action_source="BOT_DETECTION",
                current_url="https://amazon.jobs/en/jobs/123/apply",
                page_title="Amazon Job Application - SDET",
            )
            db.add(log)
            db.commit()

    with patch.object(PlaywrightAutomationEngine, "execute_run", side_effect=mock_execute_track):
        trigger_res = client.post(
            "/api/automation/runs/trigger",
            headers=auth_header,
            json={
                "company": "Amazon",
                "job_title": "SDET",
                "job_url": "https://amazon.jobs/en/jobs/123",
            },
        )
        assert trigger_res.status_code == 201
        run_id = trigger_res.json()["id"]

        # 1. GET /api/automation/runs
        list_res = client.get("/api/automation/runs", headers=auth_header)
        assert list_res.status_code == 200
        runs = list_res.json()
        target_run = next(r for r in runs if r["id"] == run_id)
        assert target_run["current_url"] == "https://amazon.jobs/en/jobs/123/apply"
        assert target_run["page_title"] == "Amazon Job Application - SDET"

        # 2. GET /api/automation/runs/{run_id}
        detail_res = client.get(f"/api/automation/runs/{run_id}", headers=auth_header)
        assert detail_res.status_code == 200
        detail = detail_res.json()
        assert detail["current_url"] == "https://amazon.jobs/en/jobs/123/apply"
        assert detail["page_title"] == "Amazon Job Application - SDET"
        assert len(detail["action_logs"]) >= 1
        assert detail["action_logs"][0]["current_url"] == "https://amazon.jobs/en/jobs/123/apply"
        assert detail["action_logs"][0]["page_title"] == "Amazon Job Application - SDET"


def test_is_valid_http_url_validation():
    from app.automation.engine import is_valid_http_url

    assert is_valid_http_url(None) is False
    assert is_valid_http_url("") is False
    assert is_valid_http_url("   ") is False
    assert is_valid_http_url("about:blank") is False
    assert is_valid_http_url("ABOUT:BLANK") is False
    assert is_valid_http_url("javascript:alert(1)") is False
    assert is_valid_http_url("chrome://settings") is False
    assert is_valid_http_url("file:///etc/passwd") is False

    assert is_valid_http_url("http://example.com") is True
    assert is_valid_http_url("https://amazon.jobs/en/jobs/12345/apply") is True
    assert is_valid_http_url("https://careers.google.com/jobs/results/?q=software") is True


@pytest.mark.asyncio
async def test_update_page_state_rejects_about_blank():
    from unittest.mock import AsyncMock, MagicMock
    from app.automation.engine import PlaywrightAutomationEngine

    engine = PlaywrightAutomationEngine()
    run = AutomationRun(
        id=uuid4(),
        user_id=uuid4(),
        company="TestCorp",
        job_title="Engineer",
        status="IN_PROGRESS",
    )

    # Mock page sitting at about:blank
    mock_page = MagicMock()
    mock_page.url = "about:blank"
    mock_page.is_closed.return_value = False
    mock_page.title = AsyncMock(return_value="")
    mock_page.context.pages = [mock_page]

    url, title = await engine._update_page_state(mock_page, run)
    assert url == ""
    assert title == ""
    assert run.current_url is None
    assert run.page_title is None

    # Now mock page navigated to real job application URL
    mock_page.url = "https://testcorp.com/careers/apply/123"
    mock_page.title = AsyncMock(return_value="Apply for Engineer - TestCorp")

    url, title = await engine._update_page_state(mock_page, run)
    assert url == "https://testcorp.com/careers/apply/123"
    assert title == "Apply for Engineer - TestCorp"
    assert run.current_url == "https://testcorp.com/careers/apply/123"
    assert run.page_title == "Apply for Engineer - TestCorp"


@pytest.mark.asyncio
async def test_update_page_state_discovers_opened_tabs():
    from unittest.mock import AsyncMock, MagicMock
    from app.automation.engine import PlaywrightAutomationEngine

    engine = PlaywrightAutomationEngine()
    run = AutomationRun(
        id=uuid4(),
        user_id=uuid4(),
        company="TestCorp",
        job_title="Engineer",
        status="IN_PROGRESS",
    )

    # Mock initial blank tab and new popup tab
    blank_page = MagicMock()
    blank_page.url = "about:blank"
    blank_page.is_closed.return_value = False
    blank_page.title = AsyncMock(return_value="")

    popup_page = MagicMock()
    popup_page.url = "https://careers.example.com/application/form"
    popup_page.is_closed.return_value = False
    popup_page.title = AsyncMock(return_value="Job Application Portal")

    blank_page.context.pages = [blank_page, popup_page]

    # Passing blank_page as active_page, engine should inspect context.pages and pick popup_page
    url, title = await engine._update_page_state(blank_page, run)
    assert url == "https://careers.example.com/application/form"
    assert title == "Job Application Portal"
    assert run.current_url == "https://careers.example.com/application/form"
    assert run.page_title == "Job Application Portal"


def test_record_log_sanitizes_about_blank():
    from unittest.mock import MagicMock
    from app.automation.engine import PlaywrightAutomationEngine

    engine = PlaywrightAutomationEngine()
    mock_db = MagicMock()
    run = AutomationRun(
        id=uuid4(),
        user_id=uuid4(),
        company="TestCorp",
        job_title="Engineer",
        status="IN_PROGRESS",
    )

    log = engine._record_log(
        db=mock_db,
        run=run,
        action_type="PAUSE",
        action_source="HUMAN_INTERVENTION",
        step_name="Submission Review",
        confidence="HIGH",
        current_url="about:blank",
        page_title="about:blank",
    )

    assert log.current_url is None
    assert log.page_title is None


