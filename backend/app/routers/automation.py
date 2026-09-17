from datetime import datetime, timezone
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
    is_duplicate_candidate,
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
    DiscoveredJob,
    Job,
    JobSearchConfig,
    Resume,
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
    DiscoveredJobResponse,
    JobDiscoveryResultResponse,
    JobDiscoveryTriggerRequest,
    JobMatchScoreRequest,
    JobMatchScoreResponse,
    JobSearchConfigRequest,
    JobSearchConfigResponse,
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
        score_breakdown=result.breakdown,
    )


@router.get("/runs", response_model=List[AutomationRunResponse])
def list_automation_runs(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> List[AutomationRunResponse]:
    """List automation runs owned by current user."""
    query = select(AutomationRun).where(AutomationRun.user_id == current_user.id)
    if status_filter:
        query = query.where(AutomationRun.status == status_filter)
    query = query.order_by(AutomationRun.created_at.desc())
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


# ============================================================================
# Job Search & Multi-Job Discovery Endpoints (V2)
# ============================================================================

@router.get("/search/config", response_model=Optional[JobSearchConfigResponse])
def get_job_search_config(
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> Optional[JobSearchConfig]:
    """Retrieve saved job search configuration for current user."""
    return database.scalar(
        select(JobSearchConfig).where(JobSearchConfig.user_id == current_user.id)
    )


@router.post("/search/config", response_model=JobSearchConfigResponse)
def save_job_search_config(
    payload: JobSearchConfigRequest,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> JobSearchConfig:
    """Create or update job search configuration."""
    config = database.scalar(
        select(JobSearchConfig).where(JobSearchConfig.user_id == current_user.id)
    )
    if not config:
        config = JobSearchConfig(user_id=current_user.id)
        database.add(config)

    for k, v in payload.model_dump().items():
        setattr(config, k, v)

    database.commit()
    database.refresh(config)
    return config


@router.post("/search/discover", response_model=JobDiscoveryResultResponse)
async def trigger_job_discovery(
    payload: JobDiscoveryTriggerRequest,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> JobDiscoveryResultResponse:
    """Discover, match, rank, and persist job candidates from a search URL."""
    config = None
    if payload.config_id:
        config = database.get(JobSearchConfig, payload.config_id)
    if not config:
        config = database.scalar(
            select(JobSearchConfig).where(JobSearchConfig.user_id == current_user.id)
        )

    search_url = (payload.search_url or (config.platform_search_url if config else "")).strip()
    if not search_url:
        raise HTTPException(
            status_code=400,
            detail="Please provide a search_url or configure Job Search parameters first.",
        )

    max_results = payload.max_results or (config.max_jobs_to_discover if config else 10)
    desired_title = config.desired_job_title if config else "Software Developer"
    desired_location = config.desired_location if config else None
    user_experience = config.years_of_experience if config else None
    specific_company = config.specific_company if config else None
    min_score = payload.min_match_score if getattr(payload, "min_match_score", None) is not None else (config.min_match_score if config and config.min_match_score is not None else 60.0)
    skip_applied = payload.skip_already_applied if getattr(payload, "skip_already_applied", None) is not None else (config.skip_already_applied if config and config.skip_already_applied is not None else True)

    # Load active resume skills
    resume = None
    if config and config.active_resume_id:
        resume = database.get(Resume, config.active_resume_id)
    if not resume:
        resume = database.scalar(
            select(Resume).where(Resume.user_id == current_user.id, Resume.is_active == True)
        )

    user_skills = []
    if resume and resume.extracted_text:
        common_tech = ["python", "javascript", "typescript", "react", "fastapi", "docker", "aws", "sql", "postgresql", "node", "java", "kubernetes", "git"]
        for tech in common_tech:
            if tech in resume.extracted_text.lower():
                user_skills.append(tech.title())

    # Find adapter for search_url
    registry = get_adapter_registry()
    adapter = registry.get_adapter_for_url(search_url)

    # Scrape candidates using Playwright or adapter discovery
    discovered_raw = []
    try:
        from playwright.async_api import async_playwright
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            discovered_raw = await adapter.discover_jobs_from_search(page, search_url, max_jobs=max_results)
            try:
                discovered_raw = await adapter.discover_jobs_from_search(page, search_url, max_jobs=max_results)
            except PermissionError as barrier_err:
                # Capture screenshot and register human intervention record
                screenshot = None
                try:
                    from ..automation.engine import PlaywrightAutomationEngine
                    engine = PlaywrightAutomationEngine()
                    screenshot = await engine.capture_screenshot(page, current_user.id, "discovery_barrier")
                except Exception:
                    pass

                barrier_run = AutomationRun(
                    user_id=current_user.id,
                    company=config.specific_company if config and config.specific_company else "Search Platform",
                    job_title=f"Discovery Barrier: {desired_title}",
                    job_url=search_url,
                    current_url=search_url,
                    screenshot_path=screenshot,
                    status=AutomationState.WAITING_FOR_USER.value,
                    current_step="Security Barrier",
                    requires_user_action=True,
                    user_prompt=f"Access barrier encountered during job discovery: {barrier_err}. Please resolve the security check.",
                    user_prompt_context_json=json.dumps({
                        "reason": str(barrier_err),
                        "search_url": search_url,
                        "step": "Security Barrier",
                        "screenshot_path": screenshot,
                    }),
                )
                database.add(barrier_run)
                database.commit()
                await browser.close()
                raise HTTPException(
                    status_code=403,
                    detail=f"Security barrier encountered on job search portal: {barrier_err}. Human intervention required.",
                )
            await browser.close()
    except HTTPException:
        raise
    except Exception:
        discovered_raw = adapter.discover_jobs(query=desired_title, location=desired_location or "")

    # Load existing discovered jobs for deduplication
    # Load existing discovered jobs and applications for deduplication
    existing_jobs = list(
        database.scalars(select(DiscoveredJob).where(DiscoveredJob.user_id == current_user.id)).all()
    )
    already_applied_targets = []
    if skip_applied:
        applied_jobs = list(
            database.scalars(
                select(DiscoveredJob).where(
                    DiscoveredJob.user_id == current_user.id,
                    DiscoveredJob.status.in_(["APPLIED", "APPLYING", "QUEUED"])
                )
            ).all()
        )
        applied_apps = list(
            database.scalars(
                select(Application).where(Application.user_id == current_user.id)
            ).all()
        )
        already_applied_targets = applied_jobs + applied_apps

    scorer = JobMatchScorer(match_threshold=min_score)
    new_saved_jobs = []
    total_matched = 0

    for cand in discovered_raw:
        if is_duplicate_candidate(
            candidate_url=cand.url,
            candidate_title=cand.title,
            candidate_company=cand.company,
            existing_records=existing_jobs,
            candidate_requisition_id=cand.requisition_id,
            candidate_location=cand.location,
            already_applied_records=already_applied_targets if skip_applied else None,
        ):
            continue

        score_res = scorer.score_job(
            target_role=desired_title,
            candidate_title=cand.title,
            candidate_description=cand.description,
            candidate_location=cand.location,
            candidate_skills=cand.skills,
            user_skills=user_skills,
            user_location=desired_location,
            user_experience_years=user_experience,
            candidate_company=cand.company,
            specific_company=specific_company,
            candidate_experience_str=cand.experience_str,
        )

        if score_res.is_match:
            total_matched += 1

        db_job = DiscoveredJob(
            user_id=current_user.id,
            config_id=config.id if config else None,
            company=cand.company,
            exact_title=cand.title,
            job_url=cand.url,
            location=cand.location,
            platform=cand.platform,
            raw_description=cand.description,
            requisition_id=cand.requisition_id,
            experience_raw=cand.experience_str,
            matched_skills_json=json.dumps(score_res.matched_skills),
            missing_skills_json=json.dumps(score_res.missing_skills),
            match_score=score_res.match_score,
            title_score=score_res.title_score,
            skills_score=score_res.skills_score,
            location_score=score_res.location_score,
            experience_score=score_res.experience_score,
            is_matched=score_res.is_match,
            match_reasons_json=json.dumps(score_res.reasons),
            match_breakdown_json=json.dumps(score_res.breakdown),
            status="MATCHED" if score_res.is_match else "REJECTED",
        )
        database.add(db_job)
        existing_jobs.append(db_job)
        new_saved_jobs.append(db_job)

    if config:
        config.last_searched_at = datetime.now(timezone.utc)

    database.commit()
    for j in new_saved_jobs:
        database.refresh(j)

    return JobDiscoveryResultResponse(
        total_discovered=len(discovered_raw),
        total_matched=total_matched,
        new_candidates_saved=len(new_saved_jobs),
        jobs=[DiscoveredJobResponse.model_validate(j) for j in new_saved_jobs],
    )


@router.get("/search/jobs", response_model=List[DiscoveredJobResponse])
def list_discovered_jobs(
    status_filter: Optional[str] = Query(default=None, alias="status"),
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> List[DiscoveredJobResponse]:
    """List discovered job postings with filtering and match scores."""
    query = select(DiscoveredJob).where(DiscoveredJob.user_id == current_user.id)
    if status_filter:
        query = query.where(DiscoveredJob.status == status_filter)
    query = query.order_by(DiscoveredJob.match_score.desc(), DiscoveredJob.discovered_at.desc())
    jobs = list(database.scalars(query).all())
    return [DiscoveredJobResponse.model_validate(j) for j in jobs]


@router.post("/search/jobs/{job_id}/queue", response_model=DiscoveredJobResponse)
def queue_discovered_job(
    job_id: UUID,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> DiscoveredJobResponse:
    """Move a discovered candidate into the application queue."""
    job = database.get(DiscoveredJob, job_id)
    if not job or job.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Discovered job not found.")

    job.status = "QUEUED"
    database.commit()
    database.refresh(job)
    return DiscoveredJobResponse.model_validate(job)


@router.post("/search/jobs/{job_id}/apply", response_model=AutomationRunResponse)
async def apply_discovered_job(
    job_id: UUID,
    background_tasks: BackgroundTasks,
    current_user: User = Depends(get_current_user),
    database: Session = Depends(get_db),
) -> AutomationRunResponse:
    """Trigger application automation for a specific discovered job candidate."""
    discovered = database.get(DiscoveredJob, job_id)
    if not discovered or discovered.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Discovered job not found.")

    discovered.status = "APPLYING"

    exact_identity = SelectedJobIdentity(
        company=discovered.company,
        exact_title=discovered.exact_title,
        job_url=discovered.job_url,
        requisition_id=discovered.requisition_id or extract_requisition_id_from_url_or_text(discovered.job_url),
        location=discovered.location,
        source=discovered.platform or "discovery",
    )

    run = AutomationRun(
        user_id=current_user.id,
        company=discovered.company,
        job_title=discovered.exact_title,
        job_url=discovered.job_url,
        current_url=discovered.job_url,
        status=AutomationState.JOB_SELECTED.value,
        current_step="Discovery Job Selected",
        user_prompt_context_json=json.dumps({
            "selected_job_identity": exact_identity.to_dict()
        }),
    )
    database.add(run)
    database.flush()

    discovered.automation_run_id = run.id
    database.commit()
    database.refresh(run)

    engine = PlaywrightAutomationEngine(headless=True)
    background_tasks.add_task(engine.execute_run, database, run.id)

    return serialize_run_response(run, database)
