"""Event envelope contracts for asynchronous service-to-service communication."""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from civicflow_contracts.common import ContractMeta


class EventType(str, Enum):
    """All event types in the CivicFlow system."""
    # Application events
    application_created = "application.created"
    application_updated = "application.updated"
    application_status_changed = "application.status_changed"
    application_approved = "application.approved"
    application_submitted = "application.submitted"
    application_failed = "application.failed"
    application_deleted = "application.deleted"

    # Document events
    document_uploaded = "document.uploaded"
    document_verified = "document.verified"
    document_rejected = "document.rejected"

    # AI events
    ai_turn_completed = "ai.turn_completed"
    ai_eligibility_evaluated = "ai.eligibility_evaluated"
    ai_action_proposed = "ai.action_proposed"

    # Browser events
    browser_session_created = "browser.session_created"
    browser_session_closed = "browser.session_closed"
    browser_navigation_completed = "browser.navigation_completed"
    browser_form_filled = "browser.form_filled"
    browser_sensitive_input_required = "browser.sensitive_input_required"
    browser_submission_evidence = "browser.submission_evidence"
    browser_user_control_changed = "browser.user_control_changed"

    # System events
    system_health_changed = "system.health_changed"


class EventEnvelope(BaseModel):
    """Standard event wrapper for all async events."""
    meta: ContractMeta = Field(default_factory=ContractMeta)
    event_type: EventType
    source_service: str = Field(..., description="Service that emitted the event: core_api | ai_agent | browser_agent")
    payload: dict[str, Any] = Field(default_factory=dict)
    idempotency_key: str | None = None


class ApplicationStatusEvent(BaseModel):
    """Specific event for application status transitions."""
    meta: ContractMeta = Field(default_factory=ContractMeta)
    application_id: str
    previous_status: str
    new_status: str
    changed_by: str = Field(..., description="user_id or service name that triggered the change")
    reason: str | None = None
