from enum import StrEnum
from typing import Any

from pydantic import Field

from backend.app.agent.schemas.common import ContractModel
from backend.app.agent.schemas.service import ServiceCategory


class IntentType(StrEnum):
    CASUAL_CONVERSATION = "casual_conversation"
    OUT_OF_SCOPE = "out_of_scope"
    FIND_SERVICE = "find_service"
    GET_INFORMATION = "get_information"
    CHECK_ELIGIBILITY = "check_eligibility"
    APPLY_FOR_SERVICE = "apply_for_service"
    TRACK_APPLICATION = "track_application"


class Intent(ContractModel):
    intent: IntentType
    service_category: ServiceCategory | None = None
    service_name: str | None = None
    jurisdiction: str | None = None
    goal: str = Field(min_length=1)
    requires_browser: bool
    eligibility_is_personal: bool = False
    collected_information: dict[str, Any] = Field(default_factory=dict)
    missing_information: list[str] = Field(default_factory=list)
