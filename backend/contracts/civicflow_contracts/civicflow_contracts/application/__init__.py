"""Application and service catalogue contracts."""
from typing import Any, Literal
from uuid import UUID
from pydantic import Field, HttpUrl, model_validator
from civicflow_contracts.common import ContractMetadata, ContractModel, ApplicationStatus, ServiceCategory, ServiceStatus, DocumentStatus
from enum import Enum


class ServiceSummary(ContractModel):
    service_id: str
    name: str
    category: str
    description: str = ""
    jurisdiction: str = ""
    portal_url: HttpUrl | None = None
    allowed_domains: list[str] = Field(default_factory=list)


class ServiceContext(ContractModel):
    service: ServiceSummary
    eligibility_rules: dict[str, Any] = Field(default_factory=dict)
    required_documents: list[str] = Field(default_factory=list)
    source_urls: list[HttpUrl] = Field(default_factory=list)


class ApplicantContext(ContractModel):
    attributes: dict[str, Any] = Field(default_factory=dict)
    known_fields: list[str] = Field(default_factory=list)


class ApplicationContext(ContractModel):
    application_id: UUID
    service_id: str
    status: ApplicationStatus
    sanitized_data: dict[str, Any] = Field(default_factory=dict)
    applicant: ApplicantContext = Field(default_factory=ApplicantContext)


class ApplicationStatusEvent(ContractMetadata):
    application_id: UUID
    previous_status: ApplicationStatus | None = None
    status: ApplicationStatus
    reason: str
    actor: str


class SubmissionEvidence(ContractModel):
    evidence_id: UUID
    captured_at: str
    evidence_type: str
    portal_domain: str
    confirmation_text: str | None = None
    reference_number: str | None = None
    verified: bool = False
    evidence_digest: str

# Frontend-facing Core API schemas (kept in the shared package during the initial integration).
from datetime import datetime
class RegisterRequest(ContractModel):
    name: str = Field(min_length=1, max_length=120); email: str; password: str = Field(min_length=10); phone: str | None = None; location: str | None = None
class LoginRequest(ContractModel):
    email: str; password: str
class TokenResponse(ContractModel):
    access_token: str; refresh_token: str; token_type: str = "bearer"
class UserProfile(ContractModel):
    id: str; name: str; email: str; phone: str | None = None; location: str | None = None
class CategoryInfo(ContractModel):
    key: str; label: str; description: str; service_count: int
class ServiceListItem(ContractModel):
    id: str; title: str; category: ServiceCategory; description: str; jurisdiction: str | None = None; department: str | None = None; status: ServiceStatus
    integration_mode: str = "information_only"; application_mode: str = "catalog"; aliases: list[str] = Field(default_factory=list)
class ServiceDetail(ServiceListItem):
    official_url: str | None = None; workflow_steps: list[str] = Field(default_factory=list); eligibility_criteria: list[str] = Field(default_factory=list); required_documents: list[str] = Field(default_factory=list)

class CustomApplicationRequest(ContractModel):
    request_text: str = Field(min_length=10, max_length=2000)
    state_code: str | None = Field(default=None, min_length=2, max_length=3)
    jurisdiction: str | None = Field(default=None, min_length=2, max_length=80)
    district: str | None = None
    department_id: str | None = None
    portal_url: str | None = None
    additional_context: dict[str, Any] = Field(default_factory=dict)

    @model_validator(mode="after")
    def require_jurisdiction(self):
        if not (self.jurisdiction or self.state_code):
            raise ValueError("Provide a state code or jurisdiction name")
        return self

class CustomApplicationResponse(ContractModel):
    application_id: str
    status: str = "request_received"
    message: str
    next_action: str = "service_discovery"
class DocumentRequirement(ContractModel):
    document_id: str; name: str; file_type: str; status: DocumentStatus
class TrackingInfo(ContractModel):
    demo_mode: bool = True; reference_number: str | None = None; last_checked: str | None = None
class CreateApplicationRequest(ContractModel):
    service_id: str; form_data: dict[str, Any] = Field(default_factory=dict); selected_scholarship: str | None = None
class UpdateApplicationRequest(ContractModel):
    status: ApplicationStatus | None = None; form_data: dict[str, Any] | None = None; current_step: int | None = None; progress: int | None = None; selected_scholarship: str | None = None
class ActivityEvent(ContractModel):
    id: str; label: str; timestamp: str; tone: str = "blue"
class ApplicationSummary(ContractModel):
    id: str; service_id: str; status: ApplicationStatus; progress: int; created_at: str; updated_at: str
class ApplicationDetail(ApplicationSummary):
    user_id: str; current_step: int = 0; form_data: dict[str, Any] = Field(default_factory=dict); documents: list[DocumentRequirement] = Field(default_factory=list); review_state: dict[str, bool] = Field(default_factory=dict); approval_state: str = "not_started"; tracking: TrackingInfo = Field(default_factory=TrackingInfo); selected_scholarship: str | None = None
    portal_url: str | None = None
    allowed_domains: list[str] = Field(default_factory=list)
    custom_request: str | None = None
    custom_state: str | None = None
    custom_district: str | None = None
    application_mode: str = "catalog"
class UploadDocumentRequest(ContractModel):
    name: str; file_type: str; notes: str | None = None
class DocumentResponse(ContractModel):
    document_id: str; name: str; file_type: str; status: DocumentStatus; notes: str | None = None; upload_url: str | None = None; uploaded_at: str
class ReviewUpdateRequest(ContractModel):
    items: dict[str, bool]
class ApprovalRequest(ContractModel):
    approved: bool
    application_id: str
class AssistantHistoryMessage(ContractModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=12000)

class AssistantMessageRequest(ContractModel):
    message: str
    application_id: str | None = None
    conversation_id: str = "default"
    history: list[AssistantHistoryMessage] = Field(default_factory=list, max_length=24)
class TrackingEvent(ContractModel):
    id: str; label: str; timestamp: str; status: str
