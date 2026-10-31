"""Validated browser actions submitted to the execution engine."""

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


ActionType = Literal[
    "fill", "click", "select", "check", "uncheck", "radio_select", "upload", "scroll_into_view"
]


class BrowserAction(BaseModel):
    """One requested action bound to an element in a specific snapshot."""

    model_config = ConfigDict(extra="forbid")

    action_id: str = Field(min_length=1)
    action_type: ActionType
    element_id: str = Field(min_length=1)
    snapshot_id: UUID
    value: str | None = None
    file_path: str | None = None
    timeout_ms: int | None = Field(default=None, gt=0)
    requires_confirmation: bool = False
