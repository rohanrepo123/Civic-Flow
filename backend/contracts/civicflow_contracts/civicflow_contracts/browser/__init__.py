"""Browser service command, session, event and safety contracts."""
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4
from pydantic import Field, HttpUrl, field_validator
from civicflow_contracts.common import ContractMetadata, ContractModel


class BrowserSessionStatus(StrEnum):
    created = "created"
    active = "active"
    paused = "paused"
    user_control = "user_control"
    closing = "closing"
    closed = "closed"
    failed = "failed"
    expired = "expired"


class BrowserCapability(StrEnum):
    navigate = "navigate"
    inspect = "inspect"
    fill_non_sensitive = "fill_non_sensitive"
    screenshot = "screenshot"
    stream = "stream"

class BrowserCommandType(StrEnum):
    navigate = "navigate"
    inspect = "inspect"
    fill = "fill"
    screenshot = "screenshot"
    click = "click"
    scroll = "scroll"

class BrowserEventType(StrEnum):
    session_created = "SessionCreated"
    navigation_completed = "NavigationCompleted"
    page_inspected = "PageInspected"
    form_fields_identified = "FormFieldsIdentified"
    form_fields_filled = "FormFieldsFilled"
    sensitive_input_required = "SensitiveInputRequired"
    user_control_started = "UserControlStarted"
    user_control_returned = "UserControlReturned"
    submission_attempt_started = "SubmissionAttemptStarted"
    submission_evidence_captured = "SubmissionEvidenceCaptured"
    submission_outcome_uncertain = "SubmissionOutcomeUncertain"
    session_failed = "SessionFailed"
    session_closed = "SessionClosed"

class SensitiveFieldType(StrEnum):
    password = "password"
    otp = "otp"
    captcha = "captcha"
    authentication_secret = "authentication_secret"
    unknown = "unknown"


class BrowserSessionPolicy(ContractModel):
    max_duration_seconds: int = Field(default=1800, ge=60, le=7200)
    require_user_control_for_sensitive_fields: bool = True
    allow_downloads: bool = False
    allow_uploads: bool = False


class BrowserSessionCreateRequest(ContractMetadata):
    user_id: UUID | str = Field(default_factory=uuid4)
    application_id: UUID | str
    service_id: str
    approved_portal_url: HttpUrl
    allowed_domains: list[str] = Field(min_length=1)
    session_policy: BrowserSessionPolicy = Field(default_factory=BrowserSessionPolicy)
    requested_capabilities: list[BrowserCapability] = Field(default_factory=list)

    @field_validator("approved_portal_url")
    @classmethod
    def require_https_portal(cls, value: HttpUrl) -> HttpUrl:
        local_mock = value.scheme == "http" and value.host in {"localhost", "127.0.0.1"} and value.port == 9090
        if value.scheme != "https" and not local_mock:
            raise ValueError("approved portal URL must use HTTPS (except the explicitly configured local mock portal)")
        return value


class BrowserSessionResponse(ContractMetadata):
    browser_session_id: UUID = Field(default_factory=uuid4)
    session_status: BrowserSessionStatus = BrowserSessionStatus.created
    stream_endpoint: str | None = None
    stream_token: str | None = None
    expires_at: datetime
    capabilities: list[BrowserCapability] = Field(default_factory=list)


class BrowserCommand(ContractMetadata):
    command_id: UUID = Field(default_factory=uuid4)
    command_type: BrowserCommandType
    target_url: HttpUrl | None = None
    element_id: str | None = None
    value: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class SensitiveFieldNotice(ContractModel):
    field_id: str
    label: str = "Sensitive field"
    sensitive_type: SensitiveFieldType
    user_entry_required: bool = True
    value_redacted: bool = True


class BrowserEvent(ContractMetadata):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: BrowserEventType
    browser_session_id: UUID
    application_id: UUID
    user_id: UUID
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    payload: dict[str, Any] = Field(default_factory=dict)


__all__ = ["BrowserCapability", "BrowserCommand", "BrowserCommandType", "BrowserEvent", "BrowserEventType", "BrowserSessionCreateRequest", "BrowserSessionPolicy", "BrowserSessionResponse", "BrowserSessionStatus", "SensitiveFieldNotice", "SensitiveFieldType"]
