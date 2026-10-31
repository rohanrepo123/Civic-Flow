"""One explicitly requested step in a browser workflow."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from browser_agent.schemas.browser_action import ActionType

WorkflowStepStatus = Literal["pending", "running", "completed", "failed", "skipped", "waiting_for_user"]


class WorkflowStep(BaseModel):
    """Structured intent and action for one workflow step."""

    model_config = ConfigDict(extra="forbid")

    step_id: str = Field(min_length=1)
    instruction: str = Field(min_length=1)
    action_type: ActionType | str
    value: str | None = None
    file_path: str | None = None
    expected_result: str | None = None
    requires_confirmation: bool = False
    status: WorkflowStepStatus = "pending"
