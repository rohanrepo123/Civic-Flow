from datetime import date, datetime
from enum import StrEnum

from pydantic import Field, HttpUrl

from backend.app.agent.schemas.common import ContractModel


class SourceVerificationStatus(StrEnum):
    VERIFIED = "verified"
    UNVERIFIED = "unverified"
    STALE = "stale"


class OfficialSource(ContractModel):
    source_id: str = Field(min_length=1)
    service_id: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    source_url: HttpUrl
    publisher: str | None = None
    publication_date: date | None = None
    document_type: str = Field(min_length=1)
    verification_status: SourceVerificationStatus = SourceVerificationStatus.UNVERIFIED
    retrieved_at: datetime | None = None


class RetrievedChunk(ContractModel):
    chunk_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    service_id: str = Field(min_length=1)
    source_title: str = Field(min_length=1)
    source_url: HttpUrl
    page_number: int | None = Field(default=None, ge=1)
    chunk_index: int = Field(ge=0)
    text: str = Field(min_length=1)
    verification_status: SourceVerificationStatus


class RetrievalHit(ContractModel):
    chunk: RetrievedChunk
    score: float
