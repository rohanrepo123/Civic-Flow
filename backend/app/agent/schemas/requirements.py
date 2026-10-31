from enum import StrEnum
from decimal import Decimal

from pydantic import Field

from backend.app.agent.schemas.common import ContractModel, SourceReference


class EligibilityOperator(StrEnum):
    EQUALS = "equals"
    NOT_EQUALS = "not_equals"
    GREATER_THAN = "greater_than"
    LESS_THAN = "less_than"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    IN = "in"
    NOT_IN = "not_in"
    CONTAINS = "contains"
    IS_PRESENT = "is_present"
    DATE_BEFORE = "date_before"
    DATE_AFTER = "date_after"


class EligibilityRule(ContractModel):
    field: str = Field(min_length=1)
    operator: EligibilityOperator
    value: object | None = None
    source_reference: str | None = None


class RequiredDocument(ContractModel):
    document_type: str = Field(min_length=1)
    mandatory: bool = True
    acceptable_types: list[str] = Field(default_factory=list)
    source_reference: str | None = None


class ApplicationStep(ContractModel):
    step_id: str = Field(min_length=1)
    description: str = Field(min_length=1)
    order: int = Field(ge=1)
    source_reference: str | None = None


class FeeInformation(ContractModel):
    amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=3)
    source_reference: str | None = None


class ServiceRequirements(ContractModel):
    service_id: str = Field(min_length=1)
    eligibility_rules: list[EligibilityRule] = Field(default_factory=list)
    required_documents: list[RequiredDocument] = Field(default_factory=list)
    application_steps: list[ApplicationStep] = Field(default_factory=list)
    fees: FeeInformation = Field(default_factory=FeeInformation)
    sources: list[SourceReference] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
