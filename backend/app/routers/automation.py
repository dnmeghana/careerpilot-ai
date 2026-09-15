"""Automation router for CareerPilot V2."""

import json
from pathlib import Path
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session, joinedload

from ..auth import get_current_user
from ..automation.companies.registry import get_adapter_registry
from ..automation.engine import PlaywrightAutomationEngine
from ..automation.matcher import (
    JobMatchScorer,
    SelectedJobIdentity,
    extract_requisition_id_from_url_or_text,
)
from ..automation.scenarios.memory import ScenarioMemoryService
from ..automation.state_machine import ApplicationStateMachine, AutomationState
from ..database import get_db
from ..models import (
    Application,
    AutomationActionLog,
    AutomationRun,
    AutomationScenario,
    AutomationSetting,
    CandidateProfile,
    Job,
    User,
)
from ..schemas import (
    AutomationActionLogResponse,
    AutomationInterventionRequest,
    AutomationRunDetailResponse,
    AutomationRunResponse,
    AutomationScenarioCreate,
    AutomationScenarioResponse,
    AutomationScenarioUpdate,
    AutomationSettingResponse,
    AutomationSettingUpdate,
    AutomationTriggerRequest,
    CandidateProfileResponse,
    CandidateProfileUpdate,
    JobMatchScoreRequest,
    JobMatchScoreResponse,
    SelectedJobIdentitySchema,
)

router = APIRouter(prefix="/api/automation", tags=["Automation"])


# ============================================================================
# Candidate Profile Endpoints
# ============================================================================

@router.get("/profile", response_model=CandidateProfileResponse)
def get_candidate_profile(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> CandidateProfile:
    """Return the authenticated user's normalized candidate profile, creating one if not present."""
    profile = database.scalar(select(CandidateProfile).where(CandidateProfile.user_id == current_user.id))
    if not profile:
        profile = CandidateProfile(user_id=current_user.id)
        database.add(profile)
        database.commit()
        database.refresh(profile)
    return profile


@router.put("/profile", response_model=CandidateProfileResponse)
def update_candidate_profile(
    payload: CandidateProfileUpdate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> CandidateProfile:
    """Update the candidate profile."""
    profile = database.scalar(select(CandidateProfile).where(CandidateProfile.user_id == current_user.id))
    if not profile:
        profile = CandidateProfile(user_id=current_user.id)
        database.add(profile)

    for field, value in payload.model_dump().items():
        setattr(profile, field, value)

    database.commit()
    database.refresh(profile)
    return profile


# ============================================================================
# Automation Runs Endpoints
# ============================================================================

def resolve_selected_job_identity(run: AutomationRun, database: Optional[Session] = None) -> Optional[SelectedJobIdentitySchema]:
    """Extracts or resolves the immutable SelectedJobIdentity for a run."""
    if run.user_prompt_context_json:
        try:
            ctx = json.loads(run.user_prompt_context_json)
            if "selected_job_identity" in ctx and isinstance(ctx["selected_job_identity"], dict):
                return SelectedJobIdentitySchema(**ctx["selected_job_identity"])
        except Exception:
            pass

    location = None
    if run.job_id and database:
        job = database.scalar(select(Job).where(Job.id == run.job_id))
        if job:
            location = job.location

    req_id = extract_requisition_id_from_url_or_text(run.job_url)
    return SelectedJobIdentitySchema(
        company=run.company,
        exact_title=run.job_title,
        job_url=run.job_url or "",
        job_id=run.job_id,
        requisition_id=req_id,
        location=location,
        source="saved_job" if run.job_id else "portal",
    )


def serialize_run_response(run: AutomationRun, database: Optional[Session] = None) -> AutomationRunResponse:
    """Serializes AutomationRun into AutomationRunResponse with selected_job_identity populated."""
    resp = AutomationRunResponse.model_validate(run)
    resp.selected_job_identity = resolve_selected_job_identity(run, database)
    return resp


@router.post("/jobs/match-score", response_model=JobMatchScoreResponse)
def calculate_job_match_score(
    payload: JobMatchScoreRequest,
    current_user: User = Depends(get_current_user),
) -> JobMatchScoreResponse:
    """Calculates multi-factor semantic similarity score between target role criteria and candidate job."""
    scorer = JobMatchScorer()
    result = scorer.score_job(
        target_role=payload.target_role,
        candidate_title=payload.candidate_title,
        candidate_description=payload.candidate_description,
        candidate_location=payload.candidate_location,
        candidate_skills=payload.candidate_skills,
        user_skills=payload.user_skills,
        user_location=payload.user_location,
        user_experience_years=payload.user_experience_years,
        employment_type_pref=payload.employment_type_pref,
    )
    return JobMatchScoreResponse(
        match_score=result.match_score,
        is_match=result.is_match,
        title_score=result.title_score,
        skills_score=result.skills_score,
        location_score=result.location_score,
        experience_score=result.experience_score,
        normalized_target_title=result.normalized_target_title,
        normalized_job_title=result.normalized_job_title,
        reasons=result.reasons,
        breakdown=result.breakdown,
    )


@router.get("/runs", response_model=List[AutomationRunResponse])
def list_automation_runs(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> List[AutomationRun]:
) -> List[AutomationRunResponse]:
    """List automation runs owned by current user."""
    query = select(AutomationRun).where(AutomationRun.user_id == current_user.id)
    if status_filter:
        query = query.where(AutomationRun.status == status_filter)
    query = query.order_by(AutomationRun.created_at.desc())
    return list(database.scalars(query).all())
    runs = list(database.scalars(query).all())
    return [serialize_run_response(r, database) for r in runs]


@router.get("/runs/{run_id}", response_model=AutomationRunDetailResponse)
def get_automation_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> AutomationRunDetailResponse:
    """Get single run details with action logs."""
    run = database.scalar(
        select(AutomationRun)
        .where(AutomationRun.id == run_id, AutomationRun.user_id == current_user.id)
        .options(joinedload(AutomationRun.action_logs))
    )
    if not run:
        raise HTTPException(status_code=404, detail="Automation run not found.")

    selected_identity = resolve_selected_job_identity(run, database)

    return AutomationRunDetailResponse(
        id=run.id,
        user_id=run.user_id,
        job_id=run.job_id,
        application_id=run.application_id,
        company=run.company,
        job_title=run.job_title,
        job_url=run.job_url,
        current_url=run.current_url,
        page_title=run.page_title,
        status=run.status,
        current_step=run.current_step,
        error_message=run.error_message,
        requires_user_action=run.requires_user_action,
        user_prompt=run.user_prompt,
        user_prompt_context_json=run.user_prompt_context_json,
        suggested_action_json=run.suggested_action_json,
        user_response_json=run.user_response_json,
        screenshot_path=run.screenshot_path,
        scenarios_used_count=run.scenarios_used_count,
        selected_job_identity=selected_identity,
        started_at=run.started_at,
        completed_at=run.completed_at,
        created_at=run.created_at,
        updated_at=run.updated_at,
        action_logs=[
            AutomationActionLogResponse.model_validate(log)
            for log in run.action_logs
        ],
    )


@router.post("/runs/trigger", response_model=AutomationRunResponse, status_code=status.HTTP_201_CREATED)
async def trigger_automation_run(
    payload: AutomationTriggerRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> AutomationRun:
    """Queue and start an automation run for a saved job or URL."""
) -> AutomationRunResponse:
    """Queue and start an automation run for a saved job or URL with persisted job identity."""
    job: Optional[Job] = None
    if payload.job_id:
        job = database.scalar(select(Job).where(Job.id == payload.job_id, Job.user_id == current_user.id))
        if not job:
            raise HTTPException(status_code=404, detail="Job not found.")

    company = payload.company or (job.company if job else "Unknown Company")
    job_title = payload.job_title or (job.title if job else "Software Engineer")
    job_url = payload.job_url or (job.url if job else "")

    if not job_url:
        raise HTTPException(status_code=400, detail="A job posting URL is required to start automation.")

    requisition_id = payload.requisition_id or extract_requisition_id_from_url_or_text(job_url)
    location = payload.location or (job.location if job else None)
    source = payload.source or ("saved_job" if job else "manual")

    # Persist exact selected job identity
    selected_identity = SelectedJobIdentity(
        company=company,
        exact_title=job_title,
        job_url=job_url,
        job_id=str(job.id) if job else None,
        requisition_id=requisition_id,
        location=location,
        source=source,
    )

    # Check or create Application tracking record
    app_record: Optional[Application] = None
    if job:
        app_record = database.scalar(
            select(Application).where(Application.job_id == job.id, Application.user_id == current_user.id)
        )
        if not app_record:
            app_record = Application(
                user_id=current_user.id,
                job_id=job.id,
                status="wishlist",
                notes="Automation initiated by user.",
            )
            database.add(app_record)
            database.commit()
            database.refresh(app_record)

    context_data = {"selected_job_identity": selected_identity.to_dict()}

    run = AutomationRun(
        user_id=current_user.id,
        job_id=job.id if job else None,
        application_id=app_record.id if app_record else None,
        company=company,
        job_title=job_title,
        job_url=job_url,
        status="DISCOVERED",
        current_step="Queued",
        user_prompt_context_json=json.dumps(context_data),
    )
    database.add(run)
    database.commit()
    database.refresh(run)

    # Launch engine asynchronously in background
    engine = PlaywrightAutomationEngine(headless=True)
    background_tasks.add_task(engine.execute_run, database, run.id)

    return run
    return serialize_run_response(run, database)


@router.post("/runs/{run_id}/pause", response_model=AutomationRunResponse)
def pause_automation_run(
    run_id: UUID,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> AutomationRun:
    """Pause an active automation run."""
    run = database.scalar(
        select(AutomationRun).where(AutomationRun.id == run_id, AutomationRun.user_id == current_user.id)
    )
    if not run:
        raise HTTPException(status_code=404, detail="Automation run not found.")

    if run.status in (AutomationState.SUBMITTED.value, AutomationState.FAILED.value):
        raise HTTPException(status_code=400, detail=f"Cannot pause run in state '{run.status}'.")

    sm = ApplicationStateMachine(initial_state=AutomationState(run.status))
    run.status = sm.pause().value
    database.commit()
    database.refresh(run)
    return run


@router.post("/runs/{run_id}/resume", response_model=AutomationRunResponse)
async def resume_automation_run(
    run_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> AutomationRun:
    """Resume a paused or waiting run."""
    run = database.scalar(
        select(AutomationRun).where(AutomationRun.id == run_id, AutomationRun.user_id == current_user.id)
    )
    if not run:
        raise HTTPException(status_code=404, detail="Automation run not found.")

    if run.status not in (AutomationState.PAUSED.value, AutomationState.WAITING_FOR_USER.value):
        raise HTTPException(status_code=400, detail=f"Run is not in a paused/waiting state (current: {run.status}).")

    engine = PlaywrightAutomationEngine(headless=True)
    background_tasks.add_task(engine.execute_run, database, run.id)
    return run


@router.post("/runs/{run_id}/intervene", response_model=AutomationRunResponse)
async def handle_human_intervention(
    run_id: UUID,
    payload: AutomationInterventionRequest,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> AutomationRun:
    """Provide user decision or answer for a run waiting for user input."""
    run = database.scalar(
        select(AutomationRun).where(AutomationRun.id == run_id, AutomationRun.user_id == current_user.id)
    )
    if not run:
        raise HTTPException(status_code=404, detail="Automation run not found.")

    if not run.requires_user_action or run.status != AutomationState.WAITING_FOR_USER.value:
        raise HTTPException(status_code=400, detail="This run is not currently waiting for user intervention.")

    run.user_response_json = json.dumps({"action": payload.action, "value": payload.value})

    if payload.action == "reject":
        run.status = AutomationState.FAILED.value
        run.error_message = "Rejected by user during manual review."
        run.requires_user_action = False
        database.commit()
        database.refresh(run)
        return run

    if payload.action == "pause":
        run.status = AutomationState.PAUSED.value
        database.commit()
        database.refresh(run)
        return run

    # If approve or edit with value, save to scenario memory if requested
    if payload.remember_scenario and run.user_prompt_context_json and payload.value:
        try:
            ctx = json.loads(run.user_prompt_context_json)
            ScenarioMemoryService.save_resolved_scenario(
                db=database,
                user_id=current_user.id,
                company=run.company,
                field_key=ctx.get("field_key", "custom_question"),
                element_strategy={"label": ctx.get("label", "")},
                action_type="fill" if ctx.get("input_type") != "select" else "select",
                value_source="learned_answer",
                static_value=payload.value,
                confidence="HIGH",
                confidence_reason="Learned from user confirmation and input.",
            )
        except Exception:
            pass

    # Clear intervention requirement and resume run
    run.requires_user_action = False
    run.user_prompt = None
    database.commit()

    engine = PlaywrightAutomationEngine(headless=True)
    background_tasks.add_task(engine.execute_run, database, run.id)

    database.refresh(run)
    return run


# ============================================================================
# Scenario Memory Endpoints
# ============================================================================

@router.get("/scenarios", response_model=List[AutomationScenarioResponse])
def list_scenarios(
    company: Optional[str] = Query(default=None),
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> List[AutomationScenario]:
    """List learned scenarios for the user and global system scenarios."""
    query = select(AutomationScenario).where(
        (AutomationScenario.user_id == current_user.id) | (AutomationScenario.user_id == None)
    )
    if company:
        query = query.where(AutomationScenario.company.ilike(company))
    query = query.order_by(AutomationScenario.times_used.desc(), AutomationScenario.created_at.desc())
    return list(database.scalars(query).all())


@router.post("/scenarios", response_model=AutomationScenarioResponse, status_code=status.HTTP_201_CREATED)
def create_scenario(
    payload: AutomationScenarioCreate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> AutomationScenario:
    """Manually add a scenario to memory."""
    scenario = AutomationScenario(
        user_id=current_user.id,
        **payload.model_dump(),
    )
    database.add(scenario)
    database.commit()
    database.refresh(scenario)
    return scenario


@router.patch("/scenarios/{scenario_id}", response_model=AutomationScenarioResponse)
def update_scenario(
    scenario_id: UUID,
    payload: AutomationScenarioUpdate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> AutomationScenario:
    """Update or toggle a learned scenario."""
    scenario = database.scalar(
        select(AutomationScenario).where(
            AutomationScenario.id == scenario_id,
            AutomationScenario.user_id == current_user.id,
        )
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found.")

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(scenario, field, value)

    database.commit()
    database.refresh(scenario)
    return scenario


@router.delete("/scenarios/{scenario_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_scenario(
    scenario_id: UUID,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> None:
    """Delete a learned scenario."""
    scenario = database.scalar(
        select(AutomationScenario).where(
            AutomationScenario.id == scenario_id,
            AutomationScenario.user_id == current_user.id,
        )
    )
    if not scenario:
        raise HTTPException(status_code=404, detail="Scenario not found.")
    database.delete(scenario)
    database.commit()


# ============================================================================
# Automation Settings Endpoints
# ============================================================================

@router.get("/settings", response_model=AutomationSettingResponse)
def get_automation_settings(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> AutomationSetting:
    """Get automation settings for the user, creating defaults if not yet present."""
    settings = database.scalar(
        select(AutomationSetting).where(AutomationSetting.user_id == current_user.id)
    )
    if not settings:
        settings = AutomationSetting(user_id=current_user.id)
        database.add(settings)
        database.commit()
        database.refresh(settings)
    return settings


@router.put("/settings", response_model=AutomationSettingResponse)
def update_automation_settings(
    payload: AutomationSettingUpdate,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> AutomationSetting:
    """Update automation preferences and scheduling interval."""
    settings = database.scalar(
        select(AutomationSetting).where(AutomationSetting.user_id == current_user.id)
    )
    if not settings:
        settings = AutomationSetting(user_id=current_user.id)
        database.add(settings)

    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(settings, field, value)

    database.commit()
    database.refresh(settings)
    return settings


# ============================================================================
# Registered Adapters & Screenshots
# ============================================================================

@router.get("/adapters")
def list_company_adapters(current_user: User = Depends(get_current_user)) -> list[dict[str, str]]:
    """List registered company adapters."""
    registry = get_adapter_registry()
    return registry.list_adapters()


@router.get("/screenshots/{filename}")
def get_screenshot(
    filename: str,
    current_user: User = Depends(get_current_user),
) -> FileResponse:
    """Serve failure or event screenshots safely."""
    clean_filename = Path(filename).name
    file_path = Path("uploads/automation_screenshots") / clean_filename
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="Screenshot not found.")
    return FileResponse(file_path)
