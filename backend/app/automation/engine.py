"""Playwright Automation Engine for job application execution."""

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from playwright.async_api import Browser, BrowserContext, Page, async_playwright
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..config import get_settings
from ..models import (
    Application,
    AutomationActionLog,
    AutomationRun,
    AutomationScenario,
    CandidateProfile,
    Job,
    Resume,
    User,
)
from .ai.ai_agent import AutomationAIAgent
from .ai.unknown_scenario import extract_unknown_scenario
from .companies.base import FormFieldDescriptor
from .companies.registry import get_adapter_registry
from .confidence import evaluate_confidence
from .matcher import (
    SelectedJobIdentity,
    extract_requisition_id_from_url_or_text,
    verify_current_page_matches_selected_job,
)
from .safety import detect_access_denied, detect_security_barrier
from .scenarios.memory import ScenarioMemoryService
from .scenarios.registry import get_scenario_registry
from .state_machine import ApplicationStateMachine, AutomationState

logger = logging.getLogger(__name__)


def is_valid_http_url(url: Optional[str]) -> bool:
    """Validate that a URL is a non-empty, real HTTP/HTTPS web address (not about:blank)."""
    if not url or not isinstance(url, str):
        return False
    clean = url.strip()
    if not clean or clean.lower() == "about:blank":
        return False
    return clean.lower().startswith(("http://", "https://"))


class PlaywrightAutomationEngine:
    """Core browser automation engine powered by Playwright."""
    """Core browser automation engine coordinating multi-company form execution."""

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self.screenshot_dir = Path("uploads/automation_screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.ai_agent = AutomationAIAgent()
        self.scenario_registry = get_scenario_registry()
        self.adapter_registry = get_adapter_registry()

    async def capture_screenshot(self, page: Page, run_id: UUID, step_name: str) -> str:
        """Capture screenshot on failure or user intervention."""
        target_page = page
        try:
            if target_page.is_closed() or not is_valid_http_url(target_page.url):
                if hasattr(target_page, "context"):
                    for p in reversed(target_page.context.pages):
                        if not p.is_closed() and is_valid_http_url(p.url):
                            target_page = p
                            break
        except Exception:
            pass

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_step = "".join(c if c.isalnum() else "_" for c in step_name)[:30]
        filename = f"{run_id}_{clean_step}_{timestamp}.png"
        file_path = self.screenshot_dir / filename
        try:
            await page.screenshot(path=str(file_path), full_page=False)
            await target_page.screenshot(path=str(file_path), full_page=False)
            return str(file_path)
        except Exception as error:
            logger.warning("Failed to take screenshot: %s", error)
            return ""

    async def _update_page_state(self, page: Page, run: AutomationRun) -> tuple[str, str]:
        """Capture the live URL and page title from Playwright and update the run record.

        Never persists or returns 'about:blank' or non-HTTP schemes as valid tracked URLs.
        """
        target_page = page
        try:
            if target_page.is_closed():
                pages = [p for p in target_page.context.pages if not p.is_closed()]
                if pages:
                    target_page = pages[-1]
        except Exception:
            pass

        url = ""
        try:
            raw_url = target_page.url or ""
            if is_valid_http_url(raw_url):
                url = raw_url.strip()
            elif hasattr(target_page, "context"):
                for p in reversed(target_page.context.pages):
                    try:
                        if not p.is_closed() and is_valid_http_url(p.url):
                            url = p.url.strip()
                            target_page = p
                            break
                    except Exception:
                        pass
        except Exception:
            pass

        if not url:
            if is_valid_http_url(run.current_url):
                url = run.current_url.strip()
            elif is_valid_http_url(run.job_url):
                url = run.job_url.strip()

        title = ""
        try:
            raw_title = await target_page.title()
            if raw_title and raw_title.strip():
                title = raw_title.strip()
        except Exception:
            pass

        if not title and run.page_title:
            title = run.page_title.strip()

        run.current_url = url if is_valid_http_url(url) else None
        run.page_title = title if title else None
        return run.current_url or "", run.page_title or ""

    def _get_selected_identity(self, run: AutomationRun, db: Session) -> SelectedJobIdentity:
        """Resolve the selected job's exact identity from run context or database."""
        if run.user_prompt_context_json:
            try:
                ctx = json.loads(run.user_prompt_context_json)
                if isinstance(ctx, dict) and "selected_job_identity" in ctx:
                    return SelectedJobIdentity.from_dict(ctx["selected_job_identity"])
            except Exception:
                pass

        location = None
        req_id = None
        source = "portal"
        if run.job_id:
            try:
                job = db.query(Job).filter(Job.id == run.job_id).first()
                if job:
                    location = job.location
                    req_id = extract_requisition_id_from_url_or_text(job.url or "")
            except Exception:
                pass

        if not req_id and run.job_url:
            req_id = extract_requisition_id_from_url_or_text(run.job_url)

        return SelectedJobIdentity(
            company=run.company,
            exact_title=run.job_title,
            job_url=run.job_url or "",
            job_id=run.job_id,
            requisition_id=req_id,
            location=location,
            source=source,
        )

    def _record_log(
        self,
        db: Session,
        run: AutomationRun,
        action_type: str,
        action_source: str,
        step_name: str,
        current_url: Optional[str] = None,
        page_title: Optional[str] = None,
        result: str = "success",
        confidence: str = "HIGH",
        confidence_reason: Optional[str] = None,
        selector_used: Optional[str] = None,
        value_used: Optional[str] = None,
        screenshot_path: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> AutomationActionLog:
        """Create and persist an action log entry with full URL and title tracking."""
        effective_url = current_url if is_valid_http_url(current_url) else run.current_url
        if not is_valid_http_url(effective_url):
            effective_url = None

        effective_title = page_title or run.page_title
        if effective_title and effective_title.strip().lower() in ("about:blank", "blank"):
            effective_title = None

        log = AutomationActionLog(
            run_id=run.id,
            action_type=action_type,
            action_source=action_source,
            step_name=step_name,
            current_url=effective_url,
            page_title=effective_title,
            selector_used=selector_used,
            value_used=value_used,
            confidence=confidence,
            confidence_reason=confidence_reason,
            result=result,
            error_message=error_message,
            screenshot_path=screenshot_path,
        )
        db.add(log)
        return log

    async def execute_run(self, db: Session, run_id: UUID) -> AutomationRun:
        """Execute or resume an automation run through the state machine."""
        run = db.get(AutomationRun, run_id)
        if not run:
            raise ValueError(f"Automation run {run_id} not found.")

        user = db.get(User, run.user_id)
        if not user:
            raise ValueError(f"User for run {run_id} not found.")

        profile = user.candidate_profile
        active_resume = db.scalar(
            select(Resume).where(Resume.user_id == user.id, Resume.is_active == True)
        )
        settings = user.automation_setting

        state_machine = ApplicationStateMachine(
            initial_state=AutomationState(run.status)
        )

        adapter = self.adapter_registry.get_adapter_for_url(run.job_url or "")

        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=self.headless)
            context = await browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
            )
            page = await context.new_page()

            # Dynamic frame navigation listener to track current URL (ignoring about:blank)
            def on_frame_navigated(frame):
                if frame == page.main_frame and is_valid_http_url(frame.url):
                    run.current_url = frame.url.strip()

            page.on("framenavigated", on_frame_navigated)
            context.on("page", lambda new_p: new_p.on("framenavigated", on_frame_navigated))

            try:
                # If resuming a run that was paused or waiting, restore the page to the target URL
                target_nav_url = run.current_url if is_valid_http_url(run.current_url) else run.job_url
                if is_valid_http_url(target_nav_url) and state_machine.current_state not in (
                    AutomationState.DISCOVERED,
                    AutomationState.JOB_SELECTED,
                ):
                    try:
                        await page.goto(target_nav_url, wait_until="domcontentloaded", timeout=30000)
                        await self._update_page_state(page, run)
                    except Exception as nav_err:
                        logger.warning("Failed to restore page to target_nav_url %s: %s", target_nav_url, nav_err)

                # 1. State: DISCOVERED -> JOB_SELECTED
                if state_machine.current_state == AutomationState.DISCOVERED:
                    run.status = state_machine.transition(AutomationState.JOB_SELECTED).value
                    run.current_step = "Opening Job Posting"
                    db.commit()

                # 2. State: JOB_SELECTED -> APPLICATION_STARTED
                if state_machine.current_state == AutomationState.JOB_SELECTED:
                    if not run.job_url:
                        raise ValueError("No job URL provided for application run.")
                    await adapter.open_job(page, run.job_url)
                    await page.wait_for_load_state("domcontentloaded")
                    url, title = await self._update_page_state(page, run)
                    self._record_log(
                        db=db,
                        run=run,
                        action_type="navigate",
                        action_source="playwright",
                        step_name="Opened job page",
                        current_url=url,
                        page_title=title,
                        confidence_reason=f"Navigated to job posting: {url}",
                    )

                    # Verify current page matches the selected job identity
                    selected_identity = self._get_selected_identity(run, db)
                    page_text = ""
                    try:
                        page_text = await page.inner_text("body")
                    except Exception:
                        pass

                    verification = verify_current_page_matches_selected_job(
                        selected_job=selected_identity,
                        current_url=url,
                        page_title=title,
                        page_content=page_text,
                    )

                    if not verification.is_verified:
                        screenshot = await self.capture_screenshot(page, run.id, "job_identity_mismatch")
                        run.screenshot_path = screenshot
                        run.current_step = "Job Identity Verification Mismatch"
                        run.status = state_machine.transition(AutomationState.WAITING_FOR_USER).value
                        run.requires_user_action = True
                        run.user_prompt = (
                            f"Job identity verification failed: {verification.reason}. "
                            f"Please verify that the opened page matches the intended job posting before continuing."
                        )
                        run.user_prompt_context_json = json.dumps({
                            "reason": verification.reason,
                            "current_url": url,
                            "page_title": title,
                            "step": "Job Identity Verification Mismatch",
                            "company": run.company,
                            "job_title": run.job_title,
                            "verification_details": verification.details,
                            "selected_job_identity": selected_identity.to_dict(),
                        })
                        self._record_log(
                            db=db,
                            run=run,
                            action_type="verify_job_identity",
                            action_source="verification",
                            step_name="Job Identity Verification",
                            current_url=url,
                            page_title=title,
                            result="mismatch",
                            confidence=verification.confidence,
                            confidence_reason=verification.reason,
                            screenshot_path=screenshot,
                        )
                        db.commit()
                        return run

                    self._record_log(
                        db=db,
                        run=run,
                        action_type="verify_job_identity",
                        action_source="verification",
                        step_name="Job Identity Verification",
                        current_url=url,
                        page_title=title,
                        result="verified",
                        confidence=verification.confidence,
                        confidence_reason=verification.reason,
                    )

                    run.status = state_machine.transition(AutomationState.APPLICATION_STARTED).value
                    run.current_step = "Starting Application Form"
                    db.commit()

                    # Click apply button if on landing posting
                    await adapter.start_application(page)
                    await page.wait_for_timeout(1000)
                    url, title = await self._update_page_state(page, run)
                    self._record_log(
                        db=db,
                        run=run,
                        action_type="start_application",
                        action_source="playwright",
                        step_name="Started application",
                        current_url=url,
                        page_title=title,
                        confidence_reason=f"Started application on portal: {url}",
                    )
                    db.commit()

                # 3. State: FORM_IN_PROGRESS loop
                if state_machine.current_state in (
                    AutomationState.APPLICATION_STARTED,
                    AutomationState.PAUSED,
                    AutomationState.WAITING_FOR_USER,
                ):
                    if state_machine.current_state == AutomationState.PAUSED:
                        run.status = state_machine.resume(AutomationState.FORM_IN_PROGRESS).value
                    elif state_machine.current_state == AutomationState.WAITING_FOR_USER:
                        run.status = state_machine.transition(AutomationState.FORM_IN_PROGRESS).value
                        run.requires_user_action = False
                        run.user_prompt = None
                    else:
                        run.status = state_machine.transition(AutomationState.FORM_IN_PROGRESS).value

                    db.commit()

                max_steps = 15
                step_count = 0

                while state_machine.current_state == AutomationState.FORM_IN_PROGRESS and step_count < max_steps:
                    step_count += 1
                    url, title = await self._update_page_state(page, run)
                    page_content = await page.content()

                    # Check for Access Denied first
                    is_denied, denied_reason = detect_access_denied(page_content, title)
                    if is_denied:
                        screenshot = await self.capture_screenshot(page, run.id, "access_denied")
                        run.screenshot_path = screenshot
                        run.current_step = "Access Denied"
                        run.status = state_machine.transition(AutomationState.WAITING_FOR_USER).value
                        run.requires_user_action = True
                        run.user_prompt = "The automation cannot continue because access was denied."
                        run.user_prompt_context_json = json.dumps({
                            "reason": "The automation cannot continue because access was denied.",
                            "current_url": url,
                            "page_title": title,
                            "step": "Access Denied",
                            "company": run.company,
                            "job_title": run.job_title,
                        })
                        self._record_log(
                            db=db,
                            run=run,
                            action_type="access_denied",
                            action_source="security",
                            step_name="Access denied",
                            current_url=url,
                            page_title=title,
                            result="access_denied",
                            confidence_reason=denied_reason,
                            screenshot_path=screenshot,
                        )
                        db.commit()
                        return run

                    # Check for bot / CAPTCHA security challenges
                    has_captcha = await adapter.detect_captcha(page)
                    if has_captcha:
                        screenshot = await self.capture_screenshot(page, run.id, "captcha_encountered")
                        run.screenshot_path = screenshot
                        run.current_step = "CAPTCHA / Security Check"
                        run.status = state_machine.transition(AutomationState.WAITING_FOR_USER).value
                        run.requires_user_action = True
                        run.user_prompt = "Manual action required: CAPTCHA or security verification prompt detected."
                        run.user_prompt_context_json = json.dumps({
                            "reason": "Manual action required: CAPTCHA or security verification prompt detected.",
                            "current_url": url,
                            "page_title": title,
                            "step": "CAPTCHA / Security Check",
                            "company": run.company,
                            "job_title": run.job_title,
                        })
                        self._record_log(
                            db=db,
                            run=run,
                            action_type="captcha",
                            action_source="security",
                            step_name="CAPTCHA challenge",
                            current_url=url,
                            page_title=title,
                            result="blocked",
                            confidence_reason="CAPTCHA or bot protection challenge detected.",
                            screenshot_path=screenshot,
                        )
                        db.commit()
                        return run

                    # Check if completed already
                    if await adapter.detect_completion(page):
                        run.status = state_machine.transition(AutomationState.FORM_COMPLETED).value
                        self._record_log(
                            db=db,
                            run=run,
                            action_type="detect_completion",
                            action_source="playwright",
                            step_name="Application completed",
                            current_url=url,
                            page_title=title,
                            result="success",
                            confidence_reason="Detected application completion confirmation screen.",
                        )
                        db.commit()
                        break

                    step_info = await adapter.inspect_current_step(page)
                    run.current_step = step_info.step_name

                    # Check for session expiration or authentication timeout
                    page_html_lower = page_content.lower()
                    if any(phrase in page_html_lower for phrase in ("session expired", "session has timed out", "sign in again", "log in again")):
                        screenshot = await self.capture_screenshot(page, run.id, "session_expired")
                        run.screenshot_path = screenshot
                        run.current_step = "Session Expired"
                        run.status = state_machine.transition(AutomationState.WAITING_FOR_USER).value
                        run.requires_user_action = True
                        run.user_prompt = "Manual action required: Session expired or authentication timeout on company portal."
                        run.user_prompt_context_json = json.dumps({
                            "reason": "Session expired or authentication timeout on company portal.",
                            "current_url": url,
                            "page_title": title,
                            "step": "Session Expired",
                            "company": run.company,
                            "job_title": run.job_title,
                        })
                        self._record_log(
                            db=db,
                            run=run,
                            action_type="session_timeout",
                            action_source="security",
                            step_name="Session expired",
                            current_url=url,
                            page_title=title,
                            result="waiting_for_user",
                            confidence_reason="Session timeout detected on company portal.",
                            screenshot_path=screenshot,
                        )
                        db.commit()
                        return run

                    # If 0 fields and no next button, finish or exit loop
                    if len(step_info.fields) == 0 and not step_info.is_last_step:
                        has_next = await adapter.navigate_next(page)
                        if not has_next:
                            run.status = state_machine.transition(AutomationState.FORM_COMPLETED).value
                            db.commit()
                            break
                            if is_valid_http_url(page.url):
                                run.status = state_machine.transition(AutomationState.FORM_COMPLETED).value
                                db.commit()
                                break
                            else:
                                logger.warning("Page is at blank/invalid URL, not completing form: %s", page.url)
                                break
                        continue

                    for field in step_info.fields:
                        action_success = await self._process_form_field(
                            db=db,
                            page=page,
                            run=run,
                            user=user,
                            profile=profile,
                            active_resume=active_resume,
                            company=run.company,
                            field=field,
                            state_machine=state_machine,
                        )

                        if not action_success:
                            # If paused or waiting for user, commit and return immediately
                            if state_machine.current_state in (
                                AutomationState.WAITING_FOR_USER,
                                AutomationState.PAUSED,
                                AutomationState.FAILED,
                            ):
                                db.commit()
                                return run

                    # Check if this was the final step or there are more steps
                    if step_info.is_last_step:
                        run.status = state_machine.transition(AutomationState.FORM_COMPLETED).value
                        db.commit()
                        break

                    # Navigate to next step
                    has_next = await adapter.navigate_next(page)
                    if has_next:
                        delay = settings.delay_between_actions_ms if settings else 800
                        await page.wait_for_timeout(delay)
                        next_url, next_title = await self._update_page_state(page, run)
                        self._record_log(
                            db=db,
                            run=run,
                            action_type="step_navigation",
                            action_source="playwright",
                            step_name=f"Navigated to {run.current_step or 'next step'}",
                            current_url=next_url,
                            page_title=next_title,
                            result="success",
                            confidence_reason=f"Moved to application step: {run.current_step or 'next page'}",
                        )
                        db.commit()
                    else:
                        # If no next button found, check if completed
                        if await adapter.detect_completion(page):
                            run.status = state_machine.transition(AutomationState.FORM_COMPLETED).value
                        break

                    delay = settings.delay_between_actions_ms if settings else 800
                    await page.wait_for_timeout(delay)

                # 4. Handle Final Submission
                if state_machine.current_state == AutomationState.FORM_COMPLETED:
                    auto_submit = settings.auto_submit if settings else False
                    url, title = await self._update_page_state(page, run)
                    if auto_submit:
                        await adapter.submit_application(page)
                        run.status = state_machine.transition(AutomationState.SUBMITTED).value
                        run.completed_at = datetime.now(timezone.utc)
                        url, title = await self._update_page_state(page, run)
                        self._record_log(
                            db=db,
                            run=run,
                            action_type="submit",
                            action_source="playwright",
                            step_name="Submitted application",
                            current_url=url,
                            page_title=title,
                            result="success",
                            confidence_reason="Application submitted automatically per user settings.",
                        )
                    else:
                        screenshot = await self.capture_screenshot(page, run.id, "submission_review")
                        run.screenshot_path = screenshot
                        run.current_step = "Submission Review"
                        run.status = state_machine.transition(AutomationState.SUBMISSION_REVIEW).value
                        run.status = state_machine.transition(AutomationState.WAITING_FOR_USER).value
                        run.requires_user_action = True
                        run.user_prompt = "Form completed! Please review and approve final application submission."
                        run.suggested_action_json = json.dumps({"action": "submit"})
                        run.user_prompt_context_json = json.dumps({
                            "reason": "Please review all filled information before final submission.",
                            "current_url": url if is_valid_http_url(url) else None,
                            "page_title": title if title else None,
                            "step": "Submission Review",
                            "company": run.company,
                            "job_title": run.job_title,
                        })
                        self._record_log(
                            db=db,
                            run=run,
                            action_type="submission_review",
                            action_source="safety_guard",
                            step_name="Submission Review",
                            current_url=url if is_valid_http_url(url) else None,
                            page_title=title if title else None,
                            result="waiting_for_user",
                            confidence_reason="Form completed. User confirmation required before final submission.",
                            screenshot_path=screenshot,
                        )

                # Update associated Application record if present
                if run.application_id:
                    app_record = db.get(Application, run.application_id)
                    if app_record:
                        app_record.automation_status = run.status
                        app_record.last_automation_attempt = datetime.now(timezone.utc)
                        if run.status == AutomationState.SUBMITTED.value:
                            app_record.status = "applied"
                            app_record.application_date = datetime.now(timezone.utc).date()

                db.commit()
                return run

            except Exception as error:
                logger.exception("Automation run %s failed: %s", run_id, error)
                try:
                    url, title = await self._update_page_state(page, run)
                    screenshot = await self.capture_screenshot(page, run.id, "error")
                    run.screenshot_path = screenshot
                except Exception:
                    url = run.current_url or run.job_url or ""
                    title = run.page_title or ""

                run.status = AutomationState.FAILED.value
                run.error_message = str(error)
                run.completed_at = datetime.now(timezone.utc)
                self._record_log(
                    db=db,
                    run=run,
                    action_type="error",
                    action_source="playwright",
                    step_name="Encountered error",
                    current_url=url,
                    page_title=title,
                    result="failed",
                    error_message=str(error),
                    confidence="LOW",
                    confidence_reason=f"Runtime exception: {error}",
                    screenshot_path=run.screenshot_path,
                )
                db.commit()
                return run
            finally:
                await context.close()
                await browser.close()

    async def _process_form_field(
        self,
        db: Session,
        page: Page,
        run: AutomationRun,
        user: User,
        profile: Optional[CandidateProfile],
        active_resume: Optional[Resume],
        company: str,
        field: FormFieldDescriptor,
        state_machine: ApplicationStateMachine,
    ) -> bool:
        """Attempt to resolve and interact with a form field."""
        # 1. Match against known scenarios first
        matched = self.scenario_registry.match_field(
            db=db,
            user=user,
            company=company,
            field_key=field.field_key,
            label=field.label,
            input_type=field.input_type,
            profile=profile,
            active_resume=active_resume,
        )

        if matched and matched.resolved_value is not None:
            # Execute known action
            success = await self._interact_with_element(
                page=page,
                field=field,
                action_type=matched.action_type,
                value=matched.resolved_value,
            )

            # Record action log with URL and page title
            url, title = await self._update_page_state(page, run)
            self._record_log(
                db=db,
                run=run,
                action_type=matched.action_type,
                action_source="known_scenario",
                step_name=f"Completed field: {field.label}",
                current_url=url,
                page_title=title,
                selector_used=field.selector,
                value_used=matched.resolved_value if field.input_type != "file" else "[Resume PDF]",
                confidence=matched.confidence,
                confidence_reason=matched.confidence_reason,
                result="success" if success else "failed",
            )
            run.scenarios_used_count += 1
            if matched.scenario_id:
                ScenarioMemoryService.record_scenario_usage(db, matched.scenario_id)

            return success

        # 2. Unknown scenario: Hand off to AI reasoning agent
        element_handle = page.locator(field.selector).first
        unknown_ctx = await extract_unknown_scenario(
            page=page,
            element=element_handle,
            company=company,
            current_step=run.current_step or "Form",
        )

        state_machine.transition(AutomationState.UNKNOWN_SCENARIO)
        state_machine.transition(AutomationState.AI_RESOLUTION)
        run.status = AutomationState.AI_RESOLUTION.value
        db.commit()

        ai_resolution = self.ai_agent.resolve_scenario(
            scenario=unknown_ctx,
            user=user,
            profile=profile,
            active_resume=active_resume,
        )

        # If user confirmation is required (low confidence, legal, demographic, or missing info)
        if ai_resolution.requires_user_confirmation:
            url, title = await self._update_page_state(page, run)
            screenshot = await self.capture_screenshot(page, run.id, f"unknown_{field.field_key}")
            run.screenshot_path = screenshot
            run.status = state_machine.transition(AutomationState.WAITING_FOR_USER).value
            run.requires_user_action = True
            run.user_prompt = f"CareerPilot AI needs your input for {company}:\nQuestion: \"{field.label}\""
            reason_text = ai_resolution.confidence_reason or f"User confirmation required for '{field.label}'."
            run.user_prompt_context_json = json.dumps({
                "field_key": field.field_key,
                "label": field.label,
                "input_type": field.input_type,
                "options": field.options,
                "understanding": ai_resolution.question_understanding,
                "confidence_reason": ai_resolution.confidence_reason,
                "reason": reason_text,
                "current_url": url,
                "page_title": title,
                "step": run.current_step or "Application Form",
                "company": company,
                "job_title": run.job_title,
            })
            run.suggested_action_json = json.dumps({
                "action_type": ai_resolution.action_type,
                "target_value": ai_resolution.target_value,
            })
            self._record_log(
                db=db,
                run=run,
                action_type="intervention_required",
                action_source="safety_guard",
                step_name=f"Input required: {field.label}",
                current_url=url,
                page_title=title,
                result="waiting_for_user",
                confidence=ai_resolution.confidence,
                confidence_reason=reason_text,
                screenshot_path=screenshot,
            )
            db.commit()
            return False

        # If high confidence AI resolution with grounded value -> execute and save scenario!
        if ai_resolution.target_value:
            success = await self._interact_with_element(
                page=page,
                field=field,
                action_type=ai_resolution.action_type,
                value=ai_resolution.target_value,
            )

            # Record action log with URL and page title
            url, title = await self._update_page_state(page, run)
            self._record_log(
                db=db,
                run=run,
                action_type=ai_resolution.action_type,
                action_source="ai",
                step_name=f"Completed field: {field.label}",
                current_url=url,
                page_title=title,
                selector_used=field.selector,
                value_used=ai_resolution.target_value if field.input_type != "file" else "[Resume PDF]",
                confidence=ai_resolution.confidence,
                confidence_reason=ai_resolution.confidence_reason,
                result="success" if success else "failed",
            )

            # Self-healing: persist learned scenario to memory for future runs
            if ai_resolution.can_persist_scenario and success:
                ScenarioMemoryService.save_resolved_scenario(
                    db=db,
                    user_id=user.id,
                    company=company,
                    field_key=field.field_key,
                    element_strategy=ai_resolution.suggested_selector_strategy,
                    action_type=ai_resolution.action_type,
                    value_source="learned_answer",
                    static_value=ai_resolution.target_value,
                    confidence="HIGH",
                    confidence_reason=f"Persisted after successful AI resolution: {ai_resolution.confidence_reason}",
                )

            state_machine.transition(AutomationState.FORM_IN_PROGRESS)
            run.status = AutomationState.FORM_IN_PROGRESS.value
            return success

        return False

    async def _interact_with_element(
        self,
        page: Page,
        field: FormFieldDescriptor,
        action_type: str,
        value: str,
    ) -> bool:
        """Execute element interaction using resilient accessible strategies."""
        locator = page.locator(field.selector).first
        if await locator.count() == 0:
            # Fallback to accessible label locator
            locator = page.get_by_label(field.label).first

        if await locator.count() == 0:
            logger.warning("Could not find element for field %s", field.field_key)
            return False

        try:
            if action_type == "fill":
                await locator.fill(value)
                return True
            elif action_type == "select":
                await locator.select_option(label=value)
                return True
            elif action_type == "check":
                if value.lower() in ("true", "yes", "1"):
                    await locator.check()
                else:
                    await locator.uncheck()
                return True
            elif action_type == "upload":
                # Ensure resume file exists on disk
                file_path = Path(value)
                if file_path.exists():
                    await locator.set_input_files(str(file_path))
                    return True
                else:
                    logger.warning("Resume file does not exist on disk: %s", value)
                    return False
            elif action_type == "click":
                await locator.click()
                return True
        except Exception as err:
            logger.warning("Error interacting with field %s: %s", field.field_key, err)
            return False

        return False
