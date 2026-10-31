from typing import Any, TypedDict

from backend.app.agent.schemas.agent_events import AgentEvent
from backend.app.agent.schemas.documents import DocumentMetadata, ExtractedField
from backend.app.agent.schemas.eligibility import EligibilityResult
from backend.app.agent.schemas.intent import Intent
from backend.app.agent.schemas.planner import PlannerResult
from backend.app.agent.schemas.requirements import ServiceRequirements
from backend.app.agent.schemas.resolution import ServiceResolution
from backend.app.agent.schemas.service import ServiceRecord
from backend.app.agent.schemas.source import RetrievedChunk
from backend.app.agent.schemas.task import TaskStatus
from backend.app.agent.schemas.browser import BrowserActionRequest, BrowserObservation, BrowserActionResponse


class CivicFlowState(TypedDict, total=False):
    task_id: str
    user_id: str
    user_request: str
    layer_context: dict[str, dict[str, Any]]
    intent: Intent
    service_resolution: ServiceResolution
    selected_service: ServiceRecord
    official_sources: list[RetrievedChunk]
    retrieval_relevant: bool
    retrieval_judgment: str
    informational_answer: str
    requirements: ServiceRequirements
    applicant_profile: dict[str, Any]
    applicant_documents: list[DocumentMetadata]
    extracted_document_fields: list[ExtractedField]
    eligibility_result: EligibilityResult
    missing_information: list[str]
    blocking_missing_information: list[str]
    validation_errors: list[str]
    execution_plan: PlannerResult
    browser_session_id: str
    browser_ready: bool
    manual_intervention_required: bool
    browser_observation: BrowserObservation
    proposed_action: BrowserActionRequest
    browser_result: BrowserActionResponse
    action_history: list[BrowserActionResponse]
    approval_id: str
    approval_status: str
    action_queue_done: bool
    task_status: TaskStatus
    retry_count: int
    errors: list[str]
    events: list[AgentEvent]
    final_summary: str
