"""Confidence evaluation system for automation actions.

Treats confidence as an engineering decision signal:
- HIGH: Known scenario + reliable profile/static value + stable selector. Safe for automatic execution.
- MEDIUM: AI understands the scenario with acceptable certainty, but needs verification depending on action risk.
- LOW: AI cannot reliably determine the required action or profile value is missing/uncertain. Pauses for user input.
"""

from enum import Enum
from typing import NamedTuple


class ConfidenceLevel(str, Enum):
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"


class ConfidenceEvaluation(NamedTuple):
    level: ConfidenceLevel
    reason: str
    can_auto_execute: bool
    requires_user_confirmation: bool


def evaluate_confidence(
    is_known_scenario: bool,
    has_reliable_value: bool,
    has_stable_selector: bool,
    is_sensitive_question: bool = False,
    is_legal_declaration: bool = False,
    is_final_submission: bool = False,
    user_auto_submit_enabled: bool = False,
    ai_confidence_hint: str | None = None,
) -> ConfidenceEvaluation:
    """Evaluate confidence level and determine execution permissions."""
    # Strict safety constraints always demand manual approval regardless of other signals
    if is_final_submission and not user_auto_submit_enabled:
        return ConfidenceEvaluation(
            level=ConfidenceLevel.MEDIUM,
            reason="Final submission requires user confirmation because automatic submission is disabled.",
            can_auto_execute=False,
            requires_user_confirmation=True,
        )

    if is_legal_declaration:
        return ConfidenceEvaluation(
            level=ConfidenceLevel.LOW,
            reason="Legal declarations, background check terms, and binding agreements require user confirmation.",
            can_auto_execute=False,
            requires_user_confirmation=True,
        )

    if is_sensitive_question:
        return ConfidenceEvaluation(
            level=ConfidenceLevel.LOW,
            reason="Demographic, EEO, or sensitive personal question requires explicit user confirmation.",
            can_auto_execute=False,
            requires_user_confirmation=True,
        )

    # Missing profile value or missing information
    if not has_reliable_value:
        return ConfidenceEvaluation(
            level=ConfidenceLevel.LOW,
            reason="Required value is missing from candidate profile or cannot be reliably determined.",
            can_auto_execute=False,
            requires_user_confirmation=True,
        )

    # Known scenario matching
    if is_known_scenario and has_reliable_value and has_stable_selector:
        return ConfidenceEvaluation(
            level=ConfidenceLevel.HIGH,
            reason="Matched trusted scenario registry with reliable profile value and stable selector.",
            can_auto_execute=True,
            requires_user_confirmation=False,
        )

    if is_known_scenario and has_reliable_value and not has_stable_selector:
        return ConfidenceEvaluation(
            level=ConfidenceLevel.MEDIUM,
            reason="Matched known scenario but element selector strategy had to fall back to heuristic match.",
            can_auto_execute=True,
            requires_user_confirmation=False,
        )

    # AI resolution logic
    if ai_confidence_hint == "HIGH" and has_reliable_value:
        return ConfidenceEvaluation(
            level=ConfidenceLevel.HIGH,
            reason="AI identified form field with high semantic alignment to existing candidate profile data.",
            can_auto_execute=True,
            requires_user_confirmation=False,
        )
    elif ai_confidence_hint == "MEDIUM":
        return ConfidenceEvaluation(
            level=ConfidenceLevel.MEDIUM,
            reason="AI identified likely action but recommends confirmation due to ambiguity.",
            can_auto_execute=False,
            requires_user_confirmation=True,
        )
    else:
        return ConfidenceEvaluation(
            level=ConfidenceLevel.LOW,
            reason="AI cannot reliably deduce the answer or action safely.",
            can_auto_execute=False,
            requires_user_confirmation=True,
        )

