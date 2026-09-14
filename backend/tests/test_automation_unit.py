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
