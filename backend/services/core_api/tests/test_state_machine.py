import pytest
from civicflow_contracts.common import ApplicationStatus
from app.core.state_machine import validate_transition, InvalidTransitionError, can_start_submission

def test_application_status_guards_submission_until_approved():
    with pytest.raises(InvalidTransitionError):
        validate_transition(ApplicationStatus.validation_complete, ApplicationStatus.submission_in_progress)
    assert can_start_submission(ApplicationStatus.approved_for_submission, True, True)[0]
    assert not can_start_submission(ApplicationStatus.approved_for_submission, False, True)[0]
    assert not can_start_submission(ApplicationStatus.approved_for_submission, True, False)[0]
