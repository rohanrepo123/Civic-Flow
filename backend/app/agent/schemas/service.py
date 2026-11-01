from enum import StrEnum

from pydantic import Field, HttpUrl

from backend.app.agent.schemas.common import ContractModel, SourceReference


class ServiceCategory(StrEnum):
    CIVIL_CERTIFICATE = "civil_certificate"
    IDENTITY_DOCUMENT = "identity_document"
    TRANSPORT = "transport"
    LAND_REVENUE = "land_revenue"
    SOCIAL_WELFARE = "social_welfare"
    FOOD_SECURITY = "food_security"
    LABOUR_EMPLOYMENT = "labour_employment"
    HEALTHCARE = "healthcare"
    GRIEVANCE = "grievance"
    OTHERS = "others"
    EDUCATION = "education"
    CERTIFICATE = "certificate"
    SCHOLARSHIP = "scholarship"
    BENEFIT = "benefit"
    LICENSE = "license"
    REGISTRATION = "registration"
    OTHER = "other"


class VerificationStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    STALE = "stale"


class RequirementsStatus(StrEnum):
    NOT_YET_VERIFIED = "not_yet_verified"
    VERIFIED = "verified"


class ServiceRecord(ContractModel):
    service_id: str = Field(min_length=1, pattern=r"^[a-zA-Z0-9_.-]+$")
    name: str = Field(min_length=1)
    category: ServiceCategory
    jurisdiction: str = Field(min_length=1)
    description: str = ""
    aliases: list[str] = Field(default_factory=list)
    verification_status: VerificationStatus = VerificationStatus.UNVERIFIED
    requirements_status: RequirementsStatus = RequirementsStatus.NOT_YET_VERIFIED
    department: str | None = None
    official_portal: HttpUrl | None = None
    official_docs_url: HttpUrl | None = None
    official_sources: list[SourceReference] = Field(default_factory=list)
    requirements_ref: str | None = None
    eligibility_config: dict[str, object] = Field(default_factory=dict)
    workflow_config: dict[str, object] = Field(default_factory=dict)
