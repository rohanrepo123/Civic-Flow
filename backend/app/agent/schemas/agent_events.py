from datetime import datetime
from enum import StrEnum
from typing import Any

from pydantic import Field

from backend.app.agent.schemas.common import ContractModel


class AgentEventType(StrEnum):
    TASK_STARTED = "task.started"
    INTENT_EXTRACTED = "intent.extracted"
    SERVICE_RESOLVED = "service.resolved"
    SOURCES_RETRIEVED = "sources.retrieved"
    REQUIREMENTS_EXTRACTED = "requirements.extracted"
    ELIGIBILITY_COMPLETED = "eligibility.completed"
    DOCUMENTS_VALIDATED = "documents.validated"
    INFORMATION_REQUIRED = "information.required"
    PLAN_CREATED = "plan.created"
    BROWSER_SESSION_CREATED = "browser.session.created"
    BROWSER_OBSERVATION_UPDATED = "browser.observation.updated"
    BROWSER_ACTION_STARTED = "browser.action.started"
    BROWSER_ACTION_COMPLETED = "browser.action.completed"
    APPROVAL_REQUIRED = "approval.required"
    TASK_PAUSED = "task.paused"
    TASK_RESUMED = "task.resumed"
    TASK_COMPLETED = "task.completed"
    TASK_FAILED = "task.failed"


class AgentEvent(ContractModel):
    event_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    sequence: int = Field(ge=1)
    type: AgentEventType
    timestamp: datetime
    payload: dict[str, Any] = Field(default_factory=dict)
