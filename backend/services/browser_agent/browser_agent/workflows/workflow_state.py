"""In-memory workflow state with a persistence-friendly interface."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from browser_agent.schemas.workflow_result import WorkflowStatus, WorkflowStepResult

HumanApprovalStatus = Literal["not_required", "waiting_for_user", "user_completed", "cancelled"]


class WorkflowState(BaseModel):
    """Serializable state record that can later be backed by a repository."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: str
    session_id: str
    step_manifest: list[str] = Field(default_factory=list)
    current_step_index: int = 0
    current_step_id: str | None = None
    completed_step_ids: list[str] = Field(default_factory=list)
    failed_step_ids: list[str] = Field(default_factory=list)
    skipped_step_ids: list[str] = Field(default_factory=list)
    step_results: list[WorkflowStepResult] = Field(default_factory=list)
    current_page_url: str = ""
    current_page_title: str = ""
    status: WorkflowStatus = "pending"
    human_approval_status: HumanApprovalStatus = "not_required"
    started_at: datetime
    completed_at: datetime | None = None


class WorkflowStateStore:
    """Small in-memory repository; its methods are the future persistence seam."""

    def __init__(self) -> None:
        self._states: dict[str, WorkflowState] = {}

    def get(self, workflow_id: str) -> WorkflowState | None:
        """Return an isolated copy of stored state, if present."""
        state = self._states.get(workflow_id)
        return state.model_copy(deep=True) if state is not None else None

    def save(self, state: WorkflowState) -> None:
        """Insert or replace a workflow record by ID."""
        self._states[state.workflow_id] = state.model_copy(deep=True)

    def delete(self, workflow_id: str) -> None:
        """Remove one in-memory record."""
        self._states.pop(workflow_id, None)
