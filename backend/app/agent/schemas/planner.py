from enum import StrEnum

from pydantic import Field

from backend.app.agent.schemas.common import ContractModel
from backend.app.agent.schemas.eligibility import EligibilityResult
from backend.app.agent.schemas.requirements import ServiceRequirements
from backend.app.agent.schemas.service import ServiceRecord
from backend.app.agent.schemas.browser import BrowserObservation


class PlanStepType(StrEnum):
    INFORMATION = "information"
    DOCUMENT_PREPARATION = "document_preparation"
    BROWSER_NAVIGATION = "browser_navigation"
    BROWSER_FORM = "browser_form"
    HUMAN_INTERVENTION = "human_intervention"
    VERIFICATION = "verification"


class PlanStepStatus(StrEnum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    WAITING_FOR_USER = "waiting_for_user"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    FAILED = "failed"


class PlanStep(ContractModel):
    step_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    type: PlanStepType
    status: PlanStepStatus = PlanStepStatus.PENDING
    depends_on: list[str] = Field(default_factory=list)
    requires_human_approval: bool = False


class ExecutionPlan(ContractModel):
    service_id: str = Field(min_length=1)
    steps: list[PlanStep] = Field(min_length=1)


class PlannerInput(ContractModel):
    service: ServiceRecord
    requirements: ServiceRequirements
    eligibility_result: EligibilityResult | None = None
    browser_observation: BrowserObservation | None = None


class PlannerResult(ContractModel):
    plan: ExecutionPlan
    notices: list[str] = Field(default_factory=list)
