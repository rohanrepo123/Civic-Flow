"""Pydantic models returned by page observation."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class InteractiveElement(BaseModel):
    """A visible interactive DOM element in one page snapshot."""

    model_config = ConfigDict(extra="forbid")

    element_id: str
    tag_name: str
    element_type: str
    role: str | None = None
    label: str | None = None
    text: str | None = None
    placeholder: str | None = None
    name: str | None = None
    id_attribute: str | None = None
    aria_label: str | None = None
    required: bool = False
    disabled: bool = False
    visible: bool = True
    enabled: bool = True
    input_type: str | None = None
    is_submit_control: bool = False
    options: list[str] = Field(default_factory=list)
    current_value: str | None = None
    checked: bool | None = None
    selected_index: int | None = None


class PageSnapshot(BaseModel):
    """Structured, point-in-time summary of a rendered page."""

    model_config = ConfigDict(extra="forbid")

    url: str
    title: str
    headings: list[str] = Field(default_factory=list)
    page_text: str = ""
    interactive_elements: list[InteractiveElement] = Field(default_factory=list)
    observed_at: datetime
    snapshot_id: UUID
