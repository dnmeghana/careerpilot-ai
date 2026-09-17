"""Configurable job discovery and application scheduler."""

import asyncio
import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Application, AutomationRun, AutomationSetting, Job, User
from ..models import Application, AutomationRun, AutomationSetting, DiscoveredJob, Job, JobSearchConfig, Resume, User
from .companies.registry import get_adapter_registry
from .engine import PlaywrightAutomationEngine
from .matcher import (
    JobMatchScorer,
    SelectedJobIdentity,
    extract_requisition_id_from_url_or_text,
    is_duplicate_candidate,
)

logger = logging.getLogger(__name__)


class AutomationScheduler:
    """Async scheduler for periodic job discovery and automated applications."""

    def __init__(self) -> None:
        self.is_running = False
        self._task: Optional[asyncio.Task[None]] = None
        self.adapter_registry = get_adapter_registry()
        self.engine = PlaywrightAutomationEngine(headless=True)

    def start(self) -> None:
        """Start the background scheduler task."""
        if not self.is_running:
            self.is_running = True
            self._task = asyncio.create_task(self._scheduler_loop())
            logger.info("Automation scheduler started.")

    def stop(self) -> None:
        """Stop the background scheduler."""
        self.is_running = False
        if self._task:
            self._task.cancel()
            self._task = None
            logger.info("Automation scheduler stopped.")

    async def _scheduler_loop(self) -> None:
        """Main loop that executes periodic checks."""
        while self.is_running:
            try:
                await self.run_scheduled_checks()
            except asyncio.CancelledError:
                break
            except Exception as error:
                logger.exception("Error in scheduler loop: %s", error)

            # Check every 60 seconds whether any user schedule is due
            await asyncio.sleep(60)

    async def run_scheduled_checks(self) -> None:
        """Check all users with active automation schedules and execute due jobs."""
        with SessionLocal() as db:
            # 1. Check legacy AutomationSetting schedules
            users_with_settings = db.scalars(
                select(AutomationSetting).where(
                    AutomationSetting.is_enabled == True,
                    AutomationSetting.schedule_interval != "manual",
                )
            ).all()

            for setting in users_with_settings:
                if self._is_schedule_due(setting):
                    await self.process_user_schedule(db, setting.user_id)

            # 2. Check JobSearchConfig schedules
            configs = db.scalars(
                select(JobSearchConfig).where(
                    JobSearchConfig.is_active == True,
                    JobSearchConfig.schedule_interval != "manual",
                )
            ).all()

            for config in configs:
                if self._is_search_config_due(config):
                    await self.process_search_config_schedule(db, config.id)

    def _is_search_config_due(self, config: JobSearchConfig) -> bool:
        """Determine if a job search config discovery check is due."""
        interval_str = (config.schedule_interval or "manual").lower()
        if interval_str == "manual":
            return False

        interval_hours = 24
        if interval_str in ("1h", "every hour", "hourly"):
            interval_hours = 1
        elif interval_str in ("4h", "every 4 hours"):
            interval_hours = 4
        elif interval_str in ("daily", "24h"):
            interval_hours = 24

        last_time = config.last_searched_at
        if not last_time:
            return True

        now = datetime.now(timezone.utc)
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)

        return now - last_time >= timedelta(hours=interval_hours)

    async def process_search_config_schedule(self, db: Session, config_id: UUID) -> List[DiscoveredJob]:
        """Execute scheduled multi-job discovery for a JobSearchConfig."""
        config = db.get(JobSearchConfig, config_id)
        if not config or not config.is_active:
            return []

        search_url = (config.platform_search_url or "").strip()
        if not search_url:
            return []

        adapter = self.adapter_registry.get_adapter_for_url(search_url)
        max_results = config.max_jobs_to_discover or 10
        desired_title = config.desired_job_title
        desired_location = config.desired_location
        user_experience = config.years_of_experience
        specific_company = config.specific_company
        min_score = config.min_match_score if config.min_match_score is not None else 60.0
        skip_applied = config.skip_already_applied if config.skip_already_applied is not None else True

        # Load active resume skills
        resume = None
        if config.active_resume_id:
            resume = db.get(Resume, config.active_resume_id)
        if not resume:
            resume = db.scalar(
                select(Resume).where(Resume.user_id == config.user_id, Resume.is_active == True)
            )

        user_skills = []
        if resume and resume.extracted_text:
            common_tech = ["python", "javascript", "typescript", "react", "fastapi", "docker", "aws", "sql", "postgresql", "node", "java", "kubernetes", "git"]
            for tech in common_tech:
                if tech in resume.extracted_text.lower():
                    user_skills.append(tech.title())

        discovered_raw = []
        try:
            from playwright.async_api import async_playwright
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                page = await browser.new_page()
                try:
                    discovered_raw = await adapter.discover_jobs_from_search(page, search_url, max_jobs=max_results)
                except Exception:
                    pass
                await browser.close()
        except Exception:
            discovered_raw = adapter.discover_jobs(query=desired_title, location=desired_location or "")

        existing_jobs = list(
            db.scalars(select(DiscoveredJob).where(DiscoveredJob.user_id == config.user_id)).all()
        )
        already_applied_targets = []
        if skip_applied:
            applied_jobs = list(
                db.scalars(
                    select(DiscoveredJob).where(
                        DiscoveredJob.user_id == config.user_id,
                        DiscoveredJob.status.in_(["APPLIED", "APPLYING", "QUEUED"]),
                    )
                ).all()
            )
            applied_apps = list(
                db.scalars(
                    select(Application).where(Application.user_id == config.user_id)
                ).all()
            )
            already_applied_targets = applied_jobs + applied_apps

        scorer = JobMatchScorer(match_threshold=min_score)
        new_jobs = []

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

            db_job = DiscoveredJob(
                user_id=config.user_id,
                config_id=config.id,
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
            db.add(db_job)
            existing_jobs.append(db_job)
            new_jobs.append(db_job)

        config.last_searched_at = datetime.now(timezone.utc)
        db.commit()
        return new_jobs

    def _is_schedule_due(self, setting: AutomationSetting) -> bool:
        """Determine if a scheduled check is due based on setting.schedule_interval."""
        interval_str = (setting.schedule_interval or "manual").lower()
        if interval_str == "manual":
            return False

        interval_hours = 24
        if interval_str in ("1h", "every hour", "hourly"):
            interval_hours = 1
        elif interval_str in ("4h", "every 4 hours"):
            interval_hours = 4
        elif interval_str in ("daily", "24h"):
            interval_hours = 24

        # Check last automated run timestamp for this user
        last_run = setting.user.automation_runs[-1] if setting.user.automation_runs else None
        if not last_run:
            return True

        now = datetime.now(timezone.utc)
        last_time = last_run.created_at
        if last_time.tzinfo is None:
            last_time = last_time.replace(tzinfo=timezone.utc)

        return now - last_time >= timedelta(hours=interval_hours)

    async def process_user_schedule(self, db: Session, user_id: UUID) -> List[AutomationRun]:
        """Execute scheduled job check, avoid duplicates, and trigger runs within limits."""
        user = db.get(User, user_id)
        if not user or not user.automation_setting or not user.automation_setting.is_enabled:
            return []

        setting = user.automation_setting

        # 1. Check daily application count against rate limit
        today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
        daily_runs_count = len([
            r for r in user.automation_runs
            if r.created_at.replace(tzinfo=timezone.utc if r.created_at.tzinfo is None else r.created_at.tzinfo) >= today_start
        ])

        if daily_runs_count >= setting.max_daily_applications:
            logger.info("User %s reached max daily applications limit (%d).", user_id, setting.max_daily_applications)
            return []

        # 2. Check allowed companies filter
        allowed_companies: Optional[List[str]] = None
        if setting.allowed_companies_json:
            try:
                allowed_companies = [c.lower() for c in json.loads(setting.allowed_companies_json)]
            except Exception:
                pass

        # 3. Discover or check saved jobs with status wishlist that have URLs
        saved_jobs = db.scalars(
            select(Job).where(Job.user_id == user_id, Job.url.is_not(None))
        ).all()

        triggered_runs: List[AutomationRun] = []

        for job in saved_jobs:
            if not job.url:
                continue

            if allowed_companies and job.company.lower() not in allowed_companies:
                continue

            # Prevent duplicate application: check if application already submitted or in progress
            existing_app = db.scalar(
                select(Application).where(Application.user_id == user_id, Application.job_id == job.id)
            )
            if existing_app and existing_app.status in ("applied", "screening", "interview", "offer"):
                continue

            # Check if an active automation run already exists
            existing_run = db.scalar(
                select(AutomationRun).where(
                    AutomationRun.user_id == user_id,
                    AutomationRun.job_id == job.id,
                    AutomationRun.status.in_(("APPLICATION_STARTED", "FORM_IN_PROGRESS", "WAITING_FOR_USER")),
                )
            )
            if existing_run:
                continue

            # Create new Application tracking record if not present
            if not existing_app:
                existing_app = Application(
                    user_id=user_id,
                    job_id=job.id,
                    status="wishlist",
                    notes="Automated application queued by CareerPilot scheduler.",
                )
                db.add(existing_app)
                db.commit()
                db.refresh(existing_app)

            # Create AutomationRun
            run = AutomationRun(
                user_id=user_id,
                job_id=job.id,
                application_id=existing_app.id,
                company=job.company,
                job_title=job.title,
                job_url=job.url,
                status="DISCOVERED",
                current_step="Queued by Scheduler",
            )
            db.add(run)
            db.commit()
            db.refresh(run)

            # Execute run through engine
            try:
                await self.engine.execute_run(db, run.id)
                triggered_runs.append(run)
            except Exception as e:
                logger.error("Error executing scheduled run %s: %s", run.id, e)

            # Check rate limit per run
            daily_runs_count += 1
            if daily_runs_count >= setting.max_daily_applications:
                break

        return triggered_runs


_SCHEDULER_INSTANCE: Optional[AutomationScheduler] = None


def get_automation_scheduler() -> AutomationScheduler:
    """Return the global scheduler singleton."""
    global _SCHEDULER_INSTANCE
    if _SCHEDULER_INSTANCE is None:
        _SCHEDULER_INSTANCE = AutomationScheduler()
    return _SCHEDULER_INSTANCE

