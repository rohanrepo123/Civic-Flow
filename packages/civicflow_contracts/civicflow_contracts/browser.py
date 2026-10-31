from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator


class ControlMode(StrEnum):
    AGENT = "agent"
    USER = "user"
    PAUSED = "paused"


class PageState(StrEnum):
    READY = "ready"
    LOADING = "loading"
    AUTHENTICATION_REQUIRED = "authentication_required"
    CAPTCHA_DETECTED = "captcha_detected"
    UNEXPECTED_ERROR = "unexpected_error"
    CLOSED = "closed"


class ElementRole(StrEnum):
    LINK = "link"
    BUTTON = "button"
    TEXTBOX = "textbox"
    COMBOBOX = "combobox"
    CHECKBOX = "checkbox"
    RADIO = "radio"
    FILE_UPLOAD = "file_upload"
    OPTION = "option"
    OTHER = "other"


class Viewport(BaseModel):
    width: int = Field(ge=320, le=7680)
    height: int = Field(ge=240, le=4320)


class BrowserSessionCreate(BaseModel):
    task_id: str = Field(min_length=1)
    start_url: HttpUrl
    viewport: Viewport


class BrowserSessionResponse(BaseModel):
    session_id: str
    status: Literal["running", "closed", "error"]
    control_mode: ControlMode
    created_at: datetime
    viewport: Viewport


class ObservedElement(BaseModel):
    element_id: str
    role: ElementRole
    label: str
    input_type: str | None = None
    placeholder: str | None = None
    visible: bool
    enabled: bool
    required: bool = False
    sensitive: bool = False


class ObservedPage(BaseModel):
    url: str
    title: str
    state: PageState


class BrowserObservation(BaseModel):
    session_id: str
    observation_id: str
    sequence: int = Field(ge=1)
    page: ObservedPage
    elements: list[ObservedElement]
    screenshot_url: str


class BrowserAction(BaseModel):
    type: Literal[
        "navigate",
        "click",
        "fill",
        "select_option",
        "check",
        "uncheck",
        "press_key",
        "scroll",
        "go_back",
        "reload",
        "upload_file",
    ]
    element_id: str | None = None
    value: str | None = None
    url: HttpUrl | None = None
    file_reference: str | None = None

    @model_validator(mode="after")
    def validate_action_shape(self) -> "BrowserAction":
        element_actions = {
            "click", "fill", "select_option", "check", "uncheck", "press_key", "upload_file"
        }
        value_actions = {"fill", "select_option", "press_key"}
        if self.type == "navigate" and self.url is None:
            raise ValueError("navigate action requires url")
        if self.type in element_actions and not self.element_id:
            raise ValueError(f"{self.type} action requires element_id")
        if self.type in value_actions and self.value is None:
            raise ValueError(f"{self.type} action requires value")
        if self.type == "upload_file" and not self.file_reference:
            raise ValueError("upload_file action requires a short-lived file_reference")
        if self.type != "navigate" and self.url is not None:
            raise ValueError("url is valid only for navigate actions")
        if self.type != "upload_file" and self.file_reference is not None:
            raise ValueError("file_reference is valid only for upload_file actions")
        return self


class BrowserActionRequest(BaseModel):
    action_id: str
    observation_id: str
    action: BrowserAction
    expected_result: str


class BrowserActionResponse(BaseModel):
    action_id: str
    status: Literal[
        "succeeded",
        "failed",
        "target_not_found",
        "stale_observation",
        "policy_blocked",
        "user_intervention_required",
        "timed_out",
    ]
    message: str
    before_observation_id: str
    after_observation_id: str | None = None
    page_url: str


class ControlModeRequest(BaseModel):
    control_mode: ControlMode


class ControlModeResponse(BaseModel):
    session_id: str
    control_mode: ControlMode


class Acknowledgement(BaseModel):
    accepted: bool


class UserInputType(StrEnum):
    POINTER_CLICK = "pointer_click"
    KEY_PRESS = "key_press"
    TEXT_INPUT = "text_input"
    SCROLL = "scroll"


class UserInputEvent(BaseModel):
    event_id: str
    type: UserInputType
    x_normalized: float | None = Field(default=None, ge=0, le=1)
    y_normalized: float | None = Field(default=None, ge=0, le=1)
    key: str | None = None
    text: str | None = Field(default=None, repr=False)
    delta_x_normalized: float | None = None
    delta_y_normalized: float | None = None

    @model_validator(mode="after")
    def validate_event_shape(self) -> "UserInputEvent":
        if self.type is UserInputType.POINTER_CLICK and (self.x_normalized is None or self.y_normalized is None):
            raise ValueError("pointer_click requires normalized x and y coordinates")
        if self.type is UserInputType.KEY_PRESS and not self.key:
            raise ValueError("key_press requires key")
        if self.type is UserInputType.TEXT_INPUT and self.text is None:
            raise ValueError("text_input requires text")
        if self.type is UserInputType.SCROLL and self.delta_y_normalized is None:
            raise ValueError("scroll requires delta_y_normalized")
        return self
