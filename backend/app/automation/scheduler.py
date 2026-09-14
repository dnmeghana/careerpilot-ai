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
from .companies.registry import get_adapter_registry
from .engine import PlaywrightAutomationEngine

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
            users_with_settings = db.scalars(
                select(AutomationSetting).where(
                    AutomationSetting.is_enabled == True,
                    AutomationSetting.schedule_interval != "manual",
                )
            ).all()

            for setting in users_with_settings:
                if self._is_schedule_due(setting):
                    await self.process_user_schedule(db, setting.user_id)

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

