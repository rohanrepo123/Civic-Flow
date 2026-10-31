"""JSON-serializable outcome of one attempted browser action."""

from pydantic import BaseModel, ConfigDict

from browser_agent.schemas.browser_action import ActionType


class ActionResult(BaseModel):
    """Execution and verification result with sensitive values omitted."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    action_id: str
    action_type: ActionType
    element_id: str
    message: str
    before_value: str | None = None
    after_value: str | None = None
    value_present: bool | None = None
    value_matches: bool | None = None
    selected_option_matches: bool | None = None
    checked_state_matches: bool | None = None
    verified: bool = False
    screenshot_path: str | None = None
    error: str | None = None
    requires_human_intervention: bool = False
    page_url: str = ""
    page_title: str = ""
