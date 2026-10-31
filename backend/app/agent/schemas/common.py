from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ContractModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class SourceReference(ContractModel):
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    url: HttpUrl | None = None
    page_number: int | None = Field(default=None, ge=1)


class TimestampedModel(ContractModel):
    created_at: datetime
