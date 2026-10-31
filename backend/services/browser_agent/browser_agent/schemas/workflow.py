"""A deterministic, user-authored ordered browser workflow."""

from datetime import datetime, timezone
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field

from browser_agent.schemas.workflow_step import WorkflowStep


class Workflow(BaseModel):
    """Ordered steps supplied by a caller; the planner never invents steps."""

    model_config = ConfigDict(extra="forbid")

    workflow_id: str = Field(default_factory=lambda: str(uuid4()), min_length=1)
    name: str = Field(min_length=1)
    description: str = ""
    steps: list[WorkflowStep] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
