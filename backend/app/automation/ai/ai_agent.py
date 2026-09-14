"""AI Reasoning Agent for resolving unknown application scenarios."""

import json
import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional

from ...models import CandidateProfile, Resume, User
from ...services.ai_service import AIService, get_ai_service
from ..safety import check_element_safety
from .unknown_scenario import UnknownScenario

logger = logging.getLogger(__name__)


@dataclass
class AIResolutionResult:
    question_understanding: str
    action_type: str  # "fill", "select", "check", "click", "upload", "ask_user", "pause", "stop"
    field_key: str
    target_value: Optional[str]
    confidence: str  # "HIGH", "MEDIUM", "LOW"
    confidence_reason: str
    requires_user_confirmation: bool
    can_persist_scenario: bool
    suggested_selector_strategy: Dict[str, Any]


class AutomationAIAgent:
    """Agent that reasons over unknown form scenarios and deduces safe actions."""

    def __init__(self, ai_service: Optional[AIService] = None) -> None:
        self.ai_service = ai_service or get_ai_service()

    def resolve_scenario(
        self,
        scenario: UnknownScenario,
        user: User,
        profile: Optional[CandidateProfile],
        active_resume: Optional[Resume],
    ) -> AIResolutionResult:
        """Reason over unknown scenario and return actionable resolution."""
        # 1. First run deterministic safety and sensitive checks
        has_sponsorship = profile is not None and profile.requires_sponsorship is not None
        demographic_opt_in = profile is not None and profile.demographic_sharing_opt_in

        safety_res = check_element_safety(
            field_name=scenario.element_attributes.get("name", ""),
            field_label=scenario.field_label,
            field_text=scenario.nearby_text,
            demographic_opt_in=demographic_opt_in,
            profile_has_sponsorship_info=has_sponsorship,
        )

        # If security challenge (CAPTCHA, MFA)
        if safety_res.is_captcha_or_mfa:
            return AIResolutionResult(
                question_understanding="Security check or CAPTCHA detected.",
                action_type="pause",
                field_key="security_check",
                target_value=None,
                confidence="LOW",
                confidence_reason="Security barriers require manual user resolution.",
                requires_user_confirmation=True,
                can_persist_scenario=False,
                suggested_selector_strategy={},
            )

        # If legal declaration
        if safety_res.is_legal:
            return AIResolutionResult(
                question_understanding=f"Legal declaration or agreement: '{scenario.field_label}'",
                action_type="ask_user",
                field_key="legal_declaration",
                target_value=None,
                confidence="LOW",
                confidence_reason="Legal agreements require manual user review and consent.",
                requires_user_confirmation=True,
                can_persist_scenario=False,
                suggested_selector_strategy={},
            )

        # If sponsorship/work auth and not in profile
        if safety_res.is_sponsorship and not has_sponsorship:
            return AIResolutionResult(
                question_understanding=f"Work authorization or visa sponsorship inquiry: '{scenario.field_label}'",
                action_type="ask_user",
                field_key="requires_sponsorship",
                target_value=None,
                confidence="LOW",
                confidence_reason="Sponsorship status is not specified in candidate profile.",
                requires_user_confirmation=True,
                can_persist_scenario=True,
                suggested_selector_strategy={"label": scenario.field_label},
            )

        # 2. Build structured prompt for LLM
        profile_summary = {
            "name": user.name,
            "email": user.email,
            "phone": profile.phone if profile else None,
            "location": profile.location if profile else None,
            "linkedin": profile.linkedin_url if profile else None,
            "github": profile.github_url if profile else None,
            "portfolio": profile.portfolio_url if profile else None,
            "work_auth": profile.work_authorization if profile else None,
            "requires_sponsorship": profile.requires_sponsorship if profile else None,
            "years_of_experience": profile.years_of_experience if profile else None,
            "degree": profile.education_degree if profile else None,
            "field": profile.education_field if profile else None,
            "school": profile.education_school if profile else None,
        }

        # Local deterministic resolution first (fast & offline safe)
        local_res = self._local_deduce(scenario, profile_summary, active_resume)
        if local_res and local_res.confidence == "HIGH":
            return local_res

        # Call AI provider if configured
        if self.ai_service.provider is not None:
            prompt = (
                f"You are an AI browser automation agent assisting a candidate with a job application form.\n"
                f"Form question/label: {scenario.field_label}\n"
                f"Input type: {scenario.input_type}\n"
                f"Options: {scenario.options}\n"
                f"Nearby context: {scenario.nearby_text}\n"
                f"Candidate Profile: {json.dumps(profile_summary)}\n\n"
                f"Determine:\n"
                f"1. What is the question asking?\n"
                f"2. Required action: fill, select, check, click, upload, or ask_user (if unknown or requires consent)\n"
                f"3. Value to use from profile (DO NOT FABRICATE or invent personal information)\n"
                f"4. Confidence: HIGH, MEDIUM, LOW\n"
                f"5. Requires user confirmation: true/false\n\n"
                f"Respond ONLY with a JSON object with keys: question_understanding, action_type, field_key, "
                f"target_value, confidence, confidence_reason, requires_user_confirmation, can_persist_scenario"
            )
            ai_data = self.ai_service._provider_json(prompt)
            if ai_data and isinstance(ai_data, dict):
                target_val = ai_data.get("target_value")
                # Strict hallucination guard: if target_value is not in profile or standard constants, require confirmation
                req_confirm = bool(ai_data.get("requires_user_confirmation", False))
                if target_val and not self._is_value_grounded(target_val, profile_summary):
                    req_confirm = True

                return AIResolutionResult(
                    question_understanding=str(ai_data.get("question_understanding", scenario.field_label)),
                    action_type=str(ai_data.get("action_type", "ask_user")),
                    field_key=str(ai_data.get("field_key", "custom_question")),
                    target_value=target_val,
                    confidence=str(ai_data.get("confidence", "MEDIUM")),
                    confidence_reason=str(ai_data.get("confidence_reason", "AI derived answer.")),
                    requires_user_confirmation=req_confirm,
                    can_persist_scenario=bool(ai_data.get("can_persist_scenario", True)),
                    suggested_selector_strategy={"label": scenario.field_label, "input_type": scenario.input_type},
                )

        # Fallback if local deduction produced a result
        if local_res:
            return local_res

        # Default safe fallback: Ask user rather than guessing
        return AIResolutionResult(
            question_understanding=f"Unrecognized question: '{scenario.field_label}'",
            action_type="ask_user",
            field_key="unknown_field",
            target_value=None,
            confidence="LOW",
            confidence_reason="Cannot reliably determine answer from candidate profile.",
            requires_user_confirmation=True,
            can_persist_scenario=True,
            suggested_selector_strategy={"label": scenario.field_label, "input_type": scenario.input_type},
        )

    def _local_deduce(
        self,
        scenario: UnknownScenario,
        profile: Dict[str, Any],
        active_resume: Optional[Resume],
    ) -> Optional[AIResolutionResult]:
        """Deterministic local deduction based on semantic rules."""
        label_lower = scenario.field_label.lower()
        nearby_lower = scenario.nearby_text.lower()
        combined = f"{label_lower} {nearby_lower}"

        # Resume upload
        if scenario.input_type == "file" or any(k in combined for k in ("resume", "cv", "curriculum vitae")):
            if active_resume:
                return AIResolutionResult(
                    question_understanding="Upload resume file",
                    action_type="upload",
                    field_key="resume",
                    target_value=active_resume.file_path,
                    confidence="HIGH",
                    confidence_reason="Selected active resume file from candidate library.",
                    requires_user_confirmation=False,
                    can_persist_scenario=True,
                    suggested_selector_strategy={"type": "file"},
                )

        # Dropdown options matching profile
        if scenario.input_type == "select" and scenario.options:
            # Sponsorship dropdown
            if "sponsorship" in combined and profile.get("requires_sponsorship") is not None:
                val = "Yes" if profile["requires_sponsorship"] else "No"
                match = next((opt for opt in scenario.options if opt.lower().startswith(val.lower())), None)
                if match:
                    return AIResolutionResult(
                        question_understanding="Sponsorship requirement selection",
                        action_type="select",
                        field_key="requires_sponsorship",
                        target_value=match,
                        confidence="HIGH",
                        confidence_reason=f"Matched option '{match}' to stored sponsorship preference.",
                        requires_user_confirmation=False,
                        can_persist_scenario=True,
                        suggested_selector_strategy={"label": scenario.field_label},
                    )

            # Work authorization dropdown
            if "authorized" in combined and profile.get("work_auth"):
                match = next((opt for opt in scenario.options if profile["work_auth"].lower() in opt.lower() or opt.lower() in profile["work_auth"].lower()), None)
                if match:
                    return AIResolutionResult(
                        question_understanding="Work authorization status selection",
                        action_type="select",
                        field_key="work_authorization",
                        target_value=match,
                        confidence="HIGH",
                        confidence_reason=f"Matched option '{match}' to profile work authorization.",
                        requires_user_confirmation=False,
                        can_persist_scenario=True,
                        suggested_selector_strategy={"label": scenario.field_label},
                    )

        # Checkbox for terms
        if scenario.input_type == "checkbox":
            if any(k in combined for k in ("agree", "terms", "policy", "privacy")):
                return AIResolutionResult(
                    question_understanding="Consent or privacy agreement checkbox",
                    action_type="ask_user",
                    field_key="agreement_checkbox",
                    target_value="true",
                    confidence="LOW",
                    confidence_reason="Agreement checkbox requires user confirmation.",
                    requires_user_confirmation=True,
                    can_persist_scenario=False,
                    suggested_selector_strategy={"label": scenario.field_label},
                )

        return None

    def _is_value_grounded(self, val: str, profile: Dict[str, Any]) -> bool:
        """Check if candidate value exists in stored profile."""
        val_str = str(val).lower()
        if val_str in ("yes", "no", "true", "false"):
            return True
        for k, v in profile.items():
            if v is not None and str(v).lower() in val_str:
                return True
        return False

