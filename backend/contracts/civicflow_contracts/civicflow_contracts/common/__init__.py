"""Versioned primitives shared by all CivicFlow services."""
from datetime import datetime, timezone
from enum import StrEnum
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator

CONTRACT_VERSION = "1.0.0"


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", use_enum_values=True)


class ApplicationStatus(StrEnum):
    draft = "draft"
    prepared = "prepared"
    validation_complete = "validation_complete"
    waiting_for_approval = "waiting_for_approval"
    approved_for_submission = "approved_for_submission"
    submission_in_progress = "submission_in_progress"
    submitted = "submitted"
    failed = "failed"
    uncertain = "uncertain"

class ServiceCategory(StrEnum):
    education="education"; certificates="certificates"; licenses="licenses"; benefits="benefits"; registrations="registrations"; other="other"

class ServiceStatus(StrEnum):
    available="available"; coming_soon="coming_soon"; information_only="information_only"

class DocumentStatus(StrEnum):
    pending="pending"; uploaded="uploaded"; verified="verified"; rejected="rejected"

class ReviewStatus(StrEnum):
    not_started="not_started"; in_progress="in_progress"; complete="complete"


class ContractMetadata(ContractModel):
    contract_version: str = Field(default=CONTRACT_VERSION, pattern=r"^\d+\.\d+\.\d+$")
    correlation_id: UUID = Field(default_factory=uuid4)
    request_id: UUID = Field(default_factory=uuid4)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    idempotency_key: str | None = Field(default=None, max_length=128)

    @field_validator("contract_version")
    @classmethod
    def reject_unsupported_contract_version(cls, value: str) -> str:
        if value != CONTRACT_VERSION:
            raise ValueError(f"Unsupported contract version: {value}; expected {CONTRACT_VERSION}")
        return value


class ErrorDetail(ContractModel):
    code: str
    message: str
    retryable: bool = False
    details: dict[str, Any] = Field(default_factory=dict)


class ErrorResponse(ContractMetadata):
    error: ErrorDetail


class EventEnvelope(ContractMetadata):
    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    source_service: str
    user_id: UUID | None = None
    application_id: UUID | None = None
    service_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)
