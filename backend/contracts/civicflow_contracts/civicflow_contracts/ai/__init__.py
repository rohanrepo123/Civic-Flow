"""AI service request/response contracts."""
from typing import Any
from uuid import UUID
from pydantic import Field
from civicflow_contracts.common import ContractMetadata, ContractModel
from civicflow_contracts.application import ServiceContext, ApplicationContext


class SourceCitation(ContractModel):
    title: str
    url: str
    excerpt: str | None = None
    retrieved_at: str | None = None

from enum import StrEnum
class EligibilityOutcome(StrEnum):
    eligible = "eligible"
    ineligible = "ineligible"
    needs_information = "needs_information"
    unknown = "unknown"

class AgentActionType(StrEnum):
    ask_user = "ask_user"
    evaluate_eligibility = "evaluate_eligibility"
    prepare_form = "prepare_form"
    create_browser_session = "create_browser_session"
    inspect_portal = "inspect_portal"
    fill_non_sensitive = "fill_non_sensitive"
    request_approval = "request_approval"


class DocumentRequirement(ContractModel):
    document_type: str
    required: bool = True
    reason: str = ""
    source_citations: list[SourceCitation] = Field(default_factory=list)


class EligibilityRequest(ContractMetadata):
    user_id: UUID
    service_context: ServiceContext
    applicant: dict[str, Any] = Field(default_factory=dict)


class EligibilityResult(ContractModel):
    eligible: bool | None = None
    outcome: EligibilityOutcome
    reasons: list[str] = Field(default_factory=list)
    missing_information: list[str] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    source_citations: list[SourceCitation] = Field(default_factory=list)


class AgentMessage(ContractModel):
    role: str = Field(pattern="^(user|assistant|system)$")
    content: str = Field(max_length=12000)


class AgentActionRequest(ContractModel):
    action_type: AgentActionType
    parameters: dict[str, Any] = Field(default_factory=dict)
    requires_user_approval: bool = True


class AgentTurnRequest(ContractMetadata):
    user_id: UUID
    conversation_id: str
    message: str = Field(min_length=1, max_length=12000)
    selected_service_context: ServiceContext | None = None
    sanitized_application_context: ApplicationContext | None = None
    allowed_actions: list[str] = Field(default_factory=list)
    history: list[AgentMessage] = Field(default_factory=list)


class AgentTurnResponse(ContractMetadata):
    run_id: str
    assistant_message: str
    intent: str
    selected_service: ServiceContext | None = None
    eligibility_result: EligibilityResult | None = None
    missing_information: list[str] = Field(default_factory=list)
    document_requirements: list[DocumentRequirement] = Field(default_factory=list)
    proposed_next_action: AgentActionRequest | None = None
    source_citations: list[SourceCitation] = Field(default_factory=list)
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    uncertainty: list[str] = Field(default_factory=list)
    mode: str = "deterministic_mock"


class ServiceDiscoveryRequest(ContractMetadata):
    user_id: UUID
    query: str
    category: str | None = None
    jurisdiction: str | None = None


class DocumentRequirementsRequest(ContractMetadata):
    user_id: UUID
    service_context: ServiceContext
    applicant: dict[str, Any] = Field(default_factory=dict)
