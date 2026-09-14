"""Known Scenario Registry and Execution Strategies."""

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from ...models import AutomationScenario, CandidateProfile, Resume, User


@dataclass
class MatchedScenario:
    scenario_id: Optional[UUID]
    company: str
    field_key: str
    action_type: str  # fill, select, check, click, upload
    value_source: str
    resolved_value: Optional[str]
    confidence: str
    confidence_reason: str
    is_learned: bool
    selector_strategy: Dict[str, Any]


# Universal built-in scenario definitions for standard application fields
BUILTIN_SCENARIOS = [
    {
        "field_key": "email",
        "action_type": "fill",
        "value_source": "profile.email",
        "element_strategy": {"role": "textbox", "name_contains": ["email", "e-mail"], "type": "email"},
        "confidence": "HIGH",
        "confidence_reason": "Standard email address from authenticated user account.",
    },
    {
        "field_key": "first_name",
        "action_type": "fill",
        "value_source": "profile.first_name",
        "element_strategy": {"role": "textbox", "name_contains": ["first name", "given name", "firstname"], "type": "text"},
        "confidence": "HIGH",
        "confidence_reason": "Standard first name from user profile.",
    },
    {
        "field_key": "last_name",
        "action_type": "fill",
        "value_source": "profile.last_name",
        "element_strategy": {"role": "textbox", "name_contains": ["last name", "family name", "surname", "lastname"], "type": "text"},
        "confidence": "HIGH",
        "confidence_reason": "Standard last name from user profile.",
    },
    {
        "field_key": "name",
        "action_type": "fill",
        "value_source": "profile.name",
        "element_strategy": {"role": "textbox", "name_contains": ["full name", "your name", "name"], "type": "text"},
        "confidence": "HIGH",
        "confidence_reason": "Full legal name from user profile.",
    },
    {
        "field_key": "phone",
        "action_type": "fill",
        "value_source": "profile.phone",
        "element_strategy": {"role": "textbox", "name_contains": ["phone", "mobile", "telephone", "tel"], "type": "tel"},
        "confidence": "HIGH",
        "confidence_reason": "Primary contact telephone from user profile.",
    },
    {
        "field_key": "location",
        "action_type": "fill",
        "value_source": "profile.location",
        "element_strategy": {"role": "textbox", "name_contains": ["location", "city", "address", "current location"], "type": "text"},
        "confidence": "HIGH",
        "confidence_reason": "Preferred geographic location from candidate profile.",
    },
    {
        "field_key": "linkedin_url",
        "action_type": "fill",
        "value_source": "profile.linkedin_url",
        "element_strategy": {"role": "textbox", "name_contains": ["linkedin"], "type": "url"},
        "confidence": "HIGH",
        "confidence_reason": "LinkedIn profile URL from candidate profile.",
    },
    {
        "field_key": "github_url",
        "action_type": "fill",
        "value_source": "profile.github_url",
        "element_strategy": {"role": "textbox", "name_contains": ["github"], "type": "url"},
        "confidence": "HIGH",
        "confidence_reason": "GitHub portfolio link from candidate profile.",
    },
    {
        "field_key": "portfolio_url",
        "action_type": "fill",
        "value_source": "profile.portfolio_url",
        "element_strategy": {"role": "textbox", "name_contains": ["portfolio", "personal website", "website"], "type": "url"},
        "confidence": "HIGH",
        "confidence_reason": "Personal portfolio URL from candidate profile.",
    },
    {
        "field_key": "resume",
        "action_type": "upload",
        "value_source": "resume_file",
        "element_strategy": {"role": "button", "name_contains": ["resume", "cv", "upload", "attach"], "type": "file"},
        "confidence": "HIGH",
        "confidence_reason": "Active resume document from user library.",
    },
    {
        "field_key": "years_of_experience",
        "action_type": "fill",
        "value_source": "profile.years_of_experience",
        "element_strategy": {"role": "textbox", "name_contains": ["years of experience", "total experience"], "type": "number"},
        "confidence": "HIGH",
        "confidence_reason": "Years of experience from candidate profile.",
    },
]


class ScenarioRegistry:
    """Matches form fields against known built-in and persisted scenarios."""

    def find_scenario(
        self,
        db: Session,
        user_id: UUID,
        company: str,
        field_key: str,
        page_signature: str = "*",
    ) -> Optional[AutomationScenario]:
        """Query database for learned/persisted scenario."""
        query = select(AutomationScenario).where(
            AutomationScenario.field_key == field_key,
            AutomationScenario.is_active == True,
            AutomationScenario.is_approved == True,
            or_(
                AutomationScenario.user_id == user_id,
                AutomationScenario.user_id == None,
            ),
            or_(
                AutomationScenario.company.ilike(company),
                AutomationScenario.company == "*",
            ),
        ).order_by(
            AutomationScenario.user_id.desc().nullslast(),
            AutomationScenario.times_used.desc(),
        )
        return db.scalar(query)

    def match_field(
        self,
        db: Session,
        user: User,
        company: str,
        field_key: str,
        label: str = "",
        input_type: str = "text",
        profile: Optional[CandidateProfile] = None,
        active_resume: Optional[Resume] = None,
    ) -> Optional[MatchedScenario]:
        """Attempt to match a field to a known scenario and resolve its target value."""
        # 1. Check user/global learned scenarios from database
        persisted = self.find_scenario(db, user.id, company, field_key)
        if persisted:
            strategy = {}
            try:
                strategy = json.loads(persisted.element_strategy_json)
            except Exception:
                pass

            resolved_val = self._resolve_value_source(
                persisted.value_source,
                persisted.static_value,
                user,
                profile,
                active_resume,
            )

            return MatchedScenario(
                scenario_id=persisted.id,
                company=persisted.company,
                field_key=persisted.field_key,
                action_type=persisted.action_type,
                value_source=persisted.value_source,
                resolved_value=resolved_val,
                confidence=persisted.confidence,
                confidence_reason=persisted.confidence_reason or "Loaded from learned scenario memory.",
                is_learned=True,
                selector_strategy=strategy,
            )

        # 2. Check universal built-in scenarios
        for builtin in BUILTIN_SCENARIOS:
            if builtin["field_key"] == field_key or self._fuzzy_match(field_key, label, builtin["field_key"]):
                resolved_val = self._resolve_value_source(
                    builtin["value_source"],
                    None,
                    user,
                    profile,
                    active_resume,
                )
                return MatchedScenario(
                    scenario_id=None,
                    company="*",
                    field_key=builtin["field_key"],
                    action_type=builtin["action_type"],
                    value_source=builtin["value_source"],
                    resolved_value=resolved_val,
                    confidence=builtin["confidence"],
                    confidence_reason=builtin["confidence_reason"],
                    is_learned=False,
                    selector_strategy=builtin["element_strategy"],
                )

        return None

    def _fuzzy_match(self, field_key: str, label: str, target_key: str) -> bool:
        """Check if field_key or label semantically targets the target_key."""
        key_norm = field_key.lower().replace("_", " ")
        lbl_norm = label.lower()

        if target_key == "first_name":
            return any(k in key_norm or k in lbl_norm for k in ("first name", "given name", "firstname"))
        if target_key == "last_name":
            return any(k in key_norm or k in lbl_norm for k in ("last name", "surname", "family name", "lastname"))
        if target_key == "name":
            return any(k in key_norm or k in lbl_norm for k in ("full name", "your name")) and not any(k in key_norm for k in ("company", "first", "last"))
        if target_key == "email":
            return "email" in key_norm or "email" in lbl_norm
        if target_key == "phone":
            return any(k in key_norm or k in lbl_norm for k in ("phone", "mobile", "tel"))
        if target_key == "resume":
            return any(k in key_norm or k in lbl_norm for k in ("resume", "cv", "curriculum"))
        return False

    def _resolve_value_source(
        self,
        value_source: str,
        static_value: Optional[str],
        user: User,
        profile: Optional[CandidateProfile],
        active_resume: Optional[Resume],
    ) -> Optional[str]:
        """Safely fetch field value from user data without guessing."""
        if static_value is not None and static_value != "":
            return static_value

        if value_source == "profile.email":
            return user.email

        first_name, _, last_name = user.name.partition(" ")
        if value_source == "profile.first_name":
            return first_name.strip()
        if value_source == "profile.last_name":
            return (last_name.strip() or first_name.strip())
        if value_source == "profile.name":
            return user.name

        if profile:
            if value_source == "profile.phone":
                return profile.phone
            if value_source == "profile.location":
                return profile.location
            if value_source == "profile.linkedin_url":
                return profile.linkedin_url
            if value_source == "profile.github_url":
                return profile.github_url
            if value_source == "profile.portfolio_url":
                return profile.portfolio_url
            if value_source == "profile.years_of_experience":
                return str(profile.years_of_experience) if profile.years_of_experience is not None else None
            if value_source == "profile.work_authorization":
                return profile.work_authorization
            if value_source == "profile.requires_sponsorship":
                if profile.requires_sponsorship is None:
                    return None
                return "Yes" if profile.requires_sponsorship else "No"

            # Check custom answers in answers_json
            if profile.answers_json:
                try:
                    custom_answers = json.loads(profile.answers_json)
                    if isinstance(custom_answers, dict) and value_source in custom_answers:
                        return str(custom_answers[value_source])
                except Exception:
                    pass

        if value_source == "resume_file":
            return active_resume.file_path if active_resume else None

        return None


_SCENARIO_REGISTRY = ScenarioRegistry()


def get_scenario_registry() -> ScenarioRegistry:
    return _SCENARIO_REGISTRY

