from enum import StrEnum

from pydantic import Field

from backend.app.agent.schemas.common import ContractModel


class EligibilityStatus(StrEnum):
    POTENTIALLY_ELIGIBLE = "potentially_eligible"
    NOT_ELIGIBLE = "not_eligible"
    INSUFFICIENT_INFORMATION = "insufficient_information"


class RuleResult(ContractModel):
    rule_id: str = Field(min_length=1)
    passed: bool | None
    explanation: str = Field(min_length=1)
    source_reference: str | None = None


class EligibilityResult(ContractModel):
    status: EligibilityStatus
    passed_rules: list[RuleResult] = Field(default_factory=list)
    failed_rules: list[RuleResult] = Field(default_factory=list)
    missing_fields: list[str] = Field(default_factory=list)
    supporting_sources: list[str] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
