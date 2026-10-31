from datetime import datetime
from enum import StrEnum

from pydantic import Field

from backend.app.agent.schemas.common import ContractModel


class TaskStatus(StrEnum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_FOR_USER = "waiting_for_user"
    WAITING_FOR_APPROVAL = "waiting_for_approval"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class Task(ContractModel):
    task_id: str = Field(min_length=1)
    user_id: str = Field(min_length=1)
    user_request: str = Field(min_length=1)
    status: TaskStatus = TaskStatus.CREATED
    service_id: str | None = None
    created_at: datetime
    updated_at: datetime | None = None
    retry_count: int = Field(default=0, ge=0)
    errors: list[str] = Field(default_factory=list)


class TaskStatusUpdate(ContractModel):
    status: TaskStatus
    message: str | None = None
