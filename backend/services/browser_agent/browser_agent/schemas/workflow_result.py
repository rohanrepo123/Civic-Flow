"""Workflow outcomes and structured progress events."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from browser_agent.schemas.action_result import ActionResult
from browser_agent.schemas.grounding import GroundingResult
from browser_agent.schemas.workflow_step import WorkflowStepStatus

WorkflowStatus = Literal["pending", "running", "completed", "failed", "waiting_for_user"]
WorkflowEventType = Literal[
    "workflow_started", "workflow_resumed", "step_started", "page_observed", "element_grounded",
    "action_executed", "action_verified", "step_completed", "step_failed", "recovery_started",
    "waiting_for_user", "workflow_completed", "workflow_failed",
]


class WorkflowProgressEvent(BaseModel):
    """Privacy-conscious progress notification for future SSE/WebSocket adapters."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: str
    step_id: str | None = None
    event_type: WorkflowEventType
    message: str
    timestamp: datetime
    status: WorkflowStatus


class WorkflowStepResult(BaseModel):
    """Recorded outcome and bounded retry history for a workflow step."""

    model_config = ConfigDict(extra="forbid")

    step_id: str
    status: WorkflowStepStatus
    attempts: int = 0
    retry_messages: list[str] = Field(default_factory=list)
    grounding_result: GroundingResult | None = None
    action_attempts: list[ActionResult] = Field(default_factory=list)
    action_result: ActionResult | None = None
    message: str


class WorkflowResult(BaseModel):
    """Final or paused aggregate workflow status."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: str
    status: WorkflowStatus
    total_steps: int
    completed_steps: int
    failed_steps: int
    skipped_steps: int
    waiting_steps: int = 0
    current_step_id: str | None = None
    requires_human_intervention: bool = False
    message: str
    step_results: list[WorkflowStepResult] = Field(default_factory=list)
    started_at: datetime
    completed_at: datetime | None = None
