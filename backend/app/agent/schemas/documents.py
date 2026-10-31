from enum import StrEnum

from pydantic import Field

from backend.app.agent.schemas.common import ContractModel


class DocumentStatus(StrEnum):
    UPLOADED = "uploaded"
    PROCESSING = "processing"
    PROCESSED = "processed"
    NEEDS_REVIEW = "needs_review"
    FAILED = "failed"


class DocumentMetadata(ContractModel):
    document_id: str = Field(min_length=1)
    owner_id: str = Field(min_length=1)
    filename: str = Field(min_length=1)
    media_type: str = Field(min_length=1)
    size_bytes: int = Field(ge=0)
    document_type: str | None = None
    status: DocumentStatus


class SourceLocation(ContractModel):
    page_number: int | None = Field(default=None, ge=1)
    text_start: int | None = Field(default=None, ge=0)
    text_end: int | None = Field(default=None, ge=0)


class ExtractedField(ContractModel):
    name: str = Field(min_length=1)
    value: str | int | float | bool | None
    confidence: float = Field(ge=0, le=1)
    source_document_id: str = Field(min_length=1)
    source_location: SourceLocation
    needs_human_review: bool = False


class FieldComparisonStatus(StrEnum):
    MATCH = "match"
    CONFLICT = "conflict"
    PROFILE_MISSING = "profile_missing"


class FieldComparison(ContractModel):
    profile_field: str = Field(min_length=1)
    extracted_field: str = Field(min_length=1)
    status: FieldComparisonStatus
    needs_human_review: bool


class DocumentAnalysis(ContractModel):
    document: DocumentMetadata
    classification_confidence: float = Field(ge=0, le=1)
    extracted_fields: list[ExtractedField] = Field(default_factory=list)
    comparisons: list[FieldComparison] = Field(default_factory=list)
    issues: list[str] = Field(default_factory=list)
