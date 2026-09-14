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
from .safety import detect_security_barrier
from .scenarios.memory import ScenarioMemoryService
from .scenarios.registry import get_scenario_registry
from .state_machine import ApplicationStateMachine, AutomationState

logger = logging.getLogger(__name__)


class PlaywrightAutomationEngine:
    """Core browser automation engine powered by Playwright."""

    def __init__(self, headless: bool = True) -> None:
        self.headless = headless
        self.screenshot_dir = Path("uploads/automation_screenshots")
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.ai_agent = AutomationAIAgent()
        self.scenario_registry = get_scenario_registry()
        self.adapter_registry = get_adapter_registry()

    async def capture_screenshot(self, page: Page, run_id: UUID, step_name: str) -> str:
        """Capture screenshot on failure or user intervention."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        clean_step = "".join(c if c.isalnum() else "_" for c in step_name)[:30]
        filename = f"{run_id}_{clean_step}_{timestamp}.png"
        file_path = self.screenshot_dir / filename
        try:
            await page.screenshot(path=str(file_path), full_page=False)
            return str(file_path)
        except Exception as error:
            logger.warning("Failed to take screenshot: %s", error)
            return ""

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

            try:
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

                    run.status = state_machine.transition(AutomationState.APPLICATION_STARTED).value
                    run.current_step = "Starting Application Form"
                    db.commit()

                    # Click apply button if on landing posting
                    await adapter.start_application(page)
                    await page.wait_for_timeout(1000)

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

                    # Check for bot / CAPTCHA security challenges first
                    has_captcha = await adapter.detect_captcha(page)
                    if has_captcha:
                        screenshot = await self.capture_screenshot(page, run.id, "captcha_encountered")
                        run.screenshot_path = screenshot
                        run.status = state_machine.transition(AutomationState.WAITING_FOR_USER).value
                        run.requires_user_action = True
                        run.user_prompt = "Manual action required: CAPTCHA or security verification prompt detected."
                        db.commit()
                        return run

                    # Check if completed already
                    if await adapter.detect_completion(page):
                        run.status = state_machine.transition(AutomationState.FORM_COMPLETED).value
                        db.commit()
                        break

                    step_info = await adapter.inspect_current_step(page)
                    run.current_step = step_info.step_name

                    # Check for session expiration or authentication timeout
                    page_html_lower = (await page.content()).lower()
                    if any(phrase in page_html_lower for phrase in ("session expired", "session has timed out", "sign in again", "log in again")):
                        screenshot = await self.capture_screenshot(page, run.id, "session_expired")
                        run.screenshot_path = screenshot
                        run.status = state_machine.transition(AutomationState.WAITING_FOR_USER).value
                        run.requires_user_action = True
                        run.user_prompt = "Manual action required: Session expired or authentication timeout on company portal."
                        db.commit()
                        return run

                    # If 0 fields and no next button, finish or exit loop
                    if len(step_info.fields) == 0 and not step_info.is_last_step:
                        has_next = await adapter.navigate_next(page)
                        if not has_next:
                            run.status = state_machine.transition(AutomationState.FORM_COMPLETED).value
                            db.commit()
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
                    if not has_next:
                        # If no next button found, check if completed
                        if await adapter.detect_completion(page):
                            run.status = state_machine.transition(AutomationState.FORM_COMPLETED).value
                        break

                    delay = settings.delay_between_actions_ms if settings else 800
                    await page.wait_for_timeout(delay)

                # 4. Handle Final Submission
                if state_machine.current_state == AutomationState.FORM_COMPLETED:
                    auto_submit = settings.auto_submit if settings else False
                    if auto_submit:
                        await adapter.submit_application(page)
                        run.status = state_machine.transition(AutomationState.SUBMITTED).value
                        run.completed_at = datetime.now(timezone.utc)
                    else:
                        run.status = state_machine.transition(AutomationState.SUBMISSION_REVIEW).value
                        run.status = state_machine.transition(AutomationState.WAITING_FOR_USER).value
                        run.requires_user_action = True
                        run.user_prompt = "Form completed! Please review and approve final application submission."
                        run.suggested_action_json = json.dumps({"action": "submit"})

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
                    screenshot = await self.capture_screenshot(page, run.id, "error")
                    run.screenshot_path = screenshot
                except Exception:
                    pass

                run.status = AutomationState.FAILED.value
                run.error_message = str(error)
                run.completed_at = datetime.now(timezone.utc)
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

            # Record action log
            log = AutomationActionLog(
                run_id=run.id,
                action_type=matched.action_type,
                action_source="known_scenario",
                step_name=field.label,
                selector_used=field.selector,
                value_used=matched.resolved_value if field.input_type != "file" else "[Resume PDF]",
                confidence=matched.confidence,
                confidence_reason=matched.confidence_reason,
                result="success" if success else "failed",
            )
            db.add(log)
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
            screenshot = await self.capture_screenshot(page, run.id, f"unknown_{field.field_key}")
            run.screenshot_path = screenshot
            run.status = state_machine.transition(AutomationState.WAITING_FOR_USER).value
            run.requires_user_action = True
            run.user_prompt = f"CareerPilot AI needs your input for {company}:\nQuestion: \"{field.label}\""
            run.user_prompt_context_json = json.dumps({
                "field_key": field.field_key,
                "label": field.label,
                "input_type": field.input_type,
                "options": field.options,
                "understanding": ai_resolution.question_understanding,
                "confidence_reason": ai_resolution.confidence_reason,
            })
            run.suggested_action_json = json.dumps({
                "action_type": ai_resolution.action_type,
                "target_value": ai_resolution.target_value,
            })
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

            # Record action log
            log = AutomationActionLog(
                run_id=run.id,
                action_type=ai_resolution.action_type,
                action_source="ai",
                step_name=field.label,
                selector_used=field.selector,
                value_used=ai_resolution.target_value if field.input_type != "file" else "[Resume PDF]",
                confidence=ai_resolution.confidence,
                confidence_reason=ai_resolution.confidence_reason,
                result="success" if success else "failed",
            )
            db.add(log)

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
