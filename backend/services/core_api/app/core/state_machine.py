"""Application state machine — defines valid status transitions.

Only the Core API may invoke these transitions. AI and Browser services
may propose or emit evidence, but Core validates and records every change.
"""

from __future__ import annotations

from civicflow_contracts.common import ApplicationStatus

# Allowed transitions: current_status → set of valid next statuses
VALID_TRANSITIONS: dict[ApplicationStatus, set[ApplicationStatus]] = {
    ApplicationStatus.draft: {
        ApplicationStatus.prepared,
        ApplicationStatus.failed,
    },
    ApplicationStatus.prepared: {
        ApplicationStatus.validation_complete,
        ApplicationStatus.draft,  # allow reverting to draft
        ApplicationStatus.failed,
    },
    ApplicationStatus.validation_complete: {
        ApplicationStatus.waiting_for_approval,
        ApplicationStatus.prepared,  # allow going back
        ApplicationStatus.failed,
    },
    ApplicationStatus.waiting_for_approval: {
        ApplicationStatus.approved_for_submission,
        ApplicationStatus.validation_complete,  # allow going back
        ApplicationStatus.failed,
    },
    ApplicationStatus.approved_for_submission: {
        ApplicationStatus.submission_in_progress,
        ApplicationStatus.waiting_for_approval,  # allow revoking approval
        ApplicationStatus.failed,
    },
    ApplicationStatus.submission_in_progress: {
        ApplicationStatus.submitted,
        ApplicationStatus.uncertain,
        ApplicationStatus.failed,
    },
    ApplicationStatus.submitted: set(),  # terminal
    ApplicationStatus.failed: {
        ApplicationStatus.draft,  # allow retry
    },
    ApplicationStatus.uncertain: {
        ApplicationStatus.submitted,  # after verification
        ApplicationStatus.failed,
        ApplicationStatus.draft,  # allow retry
    },
}


class InvalidTransitionError(Exception):
    """Raised when an invalid state transition is attempted."""

    def __init__(self, current: ApplicationStatus, target: ApplicationStatus):
        self.current = current
        self.target = target
        super().__init__(f"Cannot transition from '{current.value}' to '{target.value}'")


def validate_transition(current: ApplicationStatus, target: ApplicationStatus) -> bool:
    """Check if a transition is valid. Returns True or raises InvalidTransitionError."""
    allowed = VALID_TRANSITIONS.get(current, set())
    if target not in allowed:
        raise InvalidTransitionError(current, target)
    return True


def can_transition(current: ApplicationStatus, target: ApplicationStatus) -> bool:
    """Non-raising version — returns True if the transition is valid."""
    allowed = VALID_TRANSITIONS.get(current, set())
    return target in allowed


# Submission pre-conditions
def can_start_submission(
    status: ApplicationStatus,
    all_reviewed: bool,
    user_approved: bool,
) -> tuple[bool, str]:
    """Check all preconditions before starting submission."""
    if status != ApplicationStatus.approved_for_submission:
        return False, f"Application must be in 'approved_for_submission' state (currently: {status.value})"
    if not all_reviewed:
        return False, "All review items must be completed"
    if not user_approved:
        return False, "Explicit user approval is required before submission"
    return True, "Ready for submission"
