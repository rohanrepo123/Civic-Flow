from datetime import datetime
from enum import StrEnum

from pydantic import Field

from backend.app.agent.schemas.common import ContractModel


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXPIRED = "expired"
    CANCELLED = "cancelled"


class ApprovalRequest(ContractModel):
    approval_id: str = Field(min_length=1)
    task_id: str = Field(min_length=1)
    action_type: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: ApprovalStatus = ApprovalStatus.PENDING
    requested_at: datetime
    decided_at: datetime | None = None
    decision_reason: str | None = None
