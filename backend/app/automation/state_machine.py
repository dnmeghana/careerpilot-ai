"""Application automation state machine.

Defines valid states, allowed transitions, and state management for
job application automation runs.
"""

from enum import Enum
from typing import Set


class AutomationState(str, Enum):
    DISCOVERED = "DISCOVERED"
    JOB_SELECTED = "JOB_SELECTED"
    APPLICATION_STARTED = "APPLICATION_STARTED"
    FORM_IN_PROGRESS = "FORM_IN_PROGRESS"
    WAITING_FOR_USER = "WAITING_FOR_USER"
    UNKNOWN_SCENARIO = "UNKNOWN_SCENARIO"
    AI_RESOLUTION = "AI_RESOLUTION"
    FORM_COMPLETED = "FORM_COMPLETED"
    SUBMISSION_REVIEW = "SUBMISSION_REVIEW"
    SUBMITTED = "SUBMITTED"
    FAILED = "FAILED"
    PAUSED = "PAUSED"


# Mapping from current state to the set of allowed next states
VALID_TRANSITIONS: dict[AutomationState, Set[AutomationState]] = {
    AutomationState.DISCOVERED: {
        AutomationState.JOB_SELECTED,
        AutomationState.FAILED,
        AutomationState.PAUSED,
    },
    AutomationState.JOB_SELECTED: {
        AutomationState.APPLICATION_STARTED,
        AutomationState.WAITING_FOR_USER,
        AutomationState.FAILED,
        AutomationState.PAUSED,
    },
    AutomationState.APPLICATION_STARTED: {
        AutomationState.FORM_IN_PROGRESS,
        AutomationState.WAITING_FOR_USER,
        AutomationState.UNKNOWN_SCENARIO,
        AutomationState.FAILED,
        AutomationState.PAUSED,
    },
    AutomationState.FORM_IN_PROGRESS: {
        AutomationState.FORM_IN_PROGRESS,
        AutomationState.UNKNOWN_SCENARIO,
        AutomationState.WAITING_FOR_USER,
        AutomationState.FORM_COMPLETED,
        AutomationState.FAILED,
        AutomationState.PAUSED,
    },
    AutomationState.UNKNOWN_SCENARIO: {
        AutomationState.AI_RESOLUTION,
        AutomationState.WAITING_FOR_USER,
        AutomationState.FAILED,
        AutomationState.PAUSED,
    },
    AutomationState.AI_RESOLUTION: {
        AutomationState.FORM_IN_PROGRESS,
        AutomationState.WAITING_FOR_USER,
        AutomationState.FAILED,
        AutomationState.PAUSED,
    },
    AutomationState.WAITING_FOR_USER: {
        AutomationState.FORM_IN_PROGRESS,
        AutomationState.SUBMITTED,
        AutomationState.FAILED,
        AutomationState.PAUSED,
    },
    AutomationState.FORM_COMPLETED: {
        AutomationState.SUBMISSION_REVIEW,
        AutomationState.SUBMITTED,
        AutomationState.FAILED,
        AutomationState.PAUSED,
    },
    AutomationState.SUBMISSION_REVIEW: {
        AutomationState.SUBMITTED,
        AutomationState.WAITING_FOR_USER,
        AutomationState.FAILED,
        AutomationState.PAUSED,
    },
    AutomationState.PAUSED: {
        AutomationState.FORM_IN_PROGRESS,
        AutomationState.APPLICATION_STARTED,
        AutomationState.WAITING_FOR_USER,
        AutomationState.SUBMISSION_REVIEW,
        AutomationState.FAILED,
    },
    # Terminal states can transition to FAILED or stay
    AutomationState.SUBMITTED: set(),
    AutomationState.FAILED: set(),
}


class InvalidStateTransitionError(ValueError):
    """Raised when an illegal state transition is attempted."""

    def __init__(self, current: AutomationState, target: AutomationState) -> None:
        super().__init__(
            f"Cannot transition automation run from state '{current.value}' to '{target.value}'. "
            f"Allowed next states: {[s.value for s in VALID_TRANSITIONS.get(current, set())]}"
        )
        self.current = current
        self.target = target


class ApplicationStateMachine:
    """Controls transitions and validates application lifecycle states."""

    def __init__(self, initial_state: AutomationState = AutomationState.DISCOVERED) -> None:
        self.current_state = initial_state
        self.previous_state: AutomationState | None = None

    def can_transition_to(self, target_state: AutomationState) -> bool:
        """Check if transition to target state is legally allowed."""
        allowed = VALID_TRANSITIONS.get(self.current_state, set())
        return target_state in allowed

    def transition(self, target_state: AutomationState) -> AutomationState:
        """Perform a validated transition to target_state."""
        if not self.can_transition_to(target_state):
            raise InvalidStateTransitionError(self.current_state, target_state)
        self.previous_state = self.current_state
        self.current_state = target_state
        return self.current_state

    def pause(self) -> AutomationState:
        """Pause execution from any non-terminal state."""
        if self.current_state in (AutomationState.SUBMITTED, AutomationState.FAILED):
            raise InvalidStateTransitionError(self.current_state, AutomationState.PAUSED)
        return self.transition(AutomationState.PAUSED)

    def resume(self, destination_state: AutomationState | None = None) -> AutomationState:
        """Resume from paused state back to an active state."""
        if self.current_state != AutomationState.PAUSED:
            raise ValueError(f"Cannot resume from state '{self.current_state.value}'; must be in PAUSED state.")

        # Default to previous state if valid, or FORM_IN_PROGRESS
        target = destination_state or self.previous_state or AutomationState.FORM_IN_PROGRESS
        if target == AutomationState.PAUSED:
            target = AutomationState.FORM_IN_PROGRESS
        return self.transition(target)

