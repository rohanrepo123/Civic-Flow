from enum import StrEnum

from pydantic import Field

from backend.app.agent.schemas.common import ContractModel
from backend.app.agent.schemas.service import ServiceRecord


class ResolutionStatus(StrEnum):
    RESOLVED = "resolved"
    AMBIGUOUS = "ambiguous"
    NOT_FOUND = "not_found"


class ServiceResolution(ContractModel):
    status: ResolutionStatus
    selected_service: ServiceRecord | None = None
    candidates: list[ServiceRecord] = Field(default_factory=list)
    clarification_question: str | None = None
