"""Learned Scenario Memory service for self-healing automation."""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...models import AutomationScenario


class ScenarioMemoryService:
    """Stores and updates learned application scenarios to enable self-healing."""

    @staticmethod
    def record_scenario_usage(db: Session, scenario_id: UUID) -> None:
        """Increment usage statistics for a scenario."""
        scenario = db.get(AutomationScenario, scenario_id)
        if scenario:
            scenario.times_used += 1
            scenario.last_used_at = datetime.now(timezone.utc)
            db.commit()

    @staticmethod
    def save_resolved_scenario(
        db: Session,
        user_id: Optional[UUID],
        company: str,
        field_key: str,
        element_strategy: Dict[str, Any],
        action_type: str,
        value_source: str,
        static_value: Optional[str] = None,
        confidence: str = "HIGH",
        confidence_reason: str = "Learned from successful user approval and execution.",
        page_signature: str = "*",
    ) -> AutomationScenario:
        """Persist or update a learned scenario."""
        strategy_json = json.dumps(element_strategy)

        # Check if an existing scenario matches (user_id, company, field_key)
        existing = db.scalar(
            select(AutomationScenario).where(
                AutomationScenario.user_id == user_id,
                AutomationScenario.company == company,
                AutomationScenario.field_key == field_key,
            )
        )

        if existing:
            existing.element_strategy_json = strategy_json
            existing.action_type = action_type
            existing.value_source = value_source
            existing.static_value = static_value
            existing.confidence = confidence
            existing.confidence_reason = confidence_reason
            existing.version += 1
            existing.times_used += 1
            existing.last_used_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(existing)
            return existing

        new_scenario = AutomationScenario(
            user_id=user_id,
            company=company,
            page_signature=page_signature,
            field_key=field_key,
            element_strategy_json=strategy_json,
            action_type=action_type,
            value_source=value_source,
            static_value=static_value,
            confidence=confidence,
            confidence_reason=confidence_reason,
            version=1,
            is_active=True,
            is_approved=True,
            times_used=1,
            last_used_at=datetime.now(timezone.utc),
        )
        db.add(new_scenario)
        db.commit()
        db.refresh(new_scenario)
        return new_scenario

