"""Preflight checks for action/element compatibility and human approval."""

from dataclasses import dataclass
import re

from browser_agent.schemas.browser_action import BrowserAction
from browser_agent.schemas.observation import InteractiveElement

_AUTHENTICATION = re.compile(
    r"password|passcode|one.?time.?code|\botp\b|verification.?code|security.?code|"
    r"two.?factor|\b2fa\b|multi.?factor|auth|token|secret|credential|social.?security|\bssn\b",
    re.IGNORECASE,
)
_PRIVATE_VALUE = re.compile(
    r"name|email|phone|mobile|address|birth|\bdob\b|\bssn\b|social.?security|account|case.?number|benefit|income|"
    r"\bstate\b|country|postal|\bzip\b|gender|\bsex\b|race|ethnicity|disability|medical|health|immigration|citizenship",
    re.IGNORECASE,
)
_PAYMENT = re.compile(r"payment|\bpay\b|checkout|purchase|credit.?card|debit.?card|billing", re.IGNORECASE)
_LEGAL_ACCEPTANCE = re.compile(
    r"agree|accept|consent|declaration|certify|\bterms\b|privacy policy|legal statement",
    re.IGNORECASE,
)
_FINAL_SUBMISSION = re.compile(r"submit|send|finali[sz]e|file application|complete application", re.IGNORECASE)
_AUTH_CHALLENGE = re.compile(
    r"captcha|one.?time.?code|\botp\b|verification.?code|authenticator|two.?factor|\b2fa\b|multi.?factor",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ValidationDecision:
    """Preflight verdict; rejected human-controlled actions remain unexecuted."""

    allowed: bool
    reason: str | None = None
    requires_human_intervention: bool = False


def element_description(element: InteractiveElement) -> str:
    """Return semantic text used only for safety checks and messages."""
    return " ".join(
        value for value in (element.label, element.aria_label, element.text, element.name, element.placeholder)
        if value
    )


def is_sensitive_element(element: InteractiveElement) -> bool:
    """Identify controls whose values must not appear in results or errors."""
    description = element_description(element)
    return (
        element.input_type in {"password", "hidden", "file"}
        or bool(_AUTHENTICATION.search(description))
        or bool(_PRIVATE_VALUE.search(description))
    )


def requires_human_for_authentication(element: InteractiveElement) -> bool:
    """Whether an action would handle credentials or an authentication challenge."""
    return element.input_type == "password" or bool(_AUTHENTICATION.search(element_description(element)))


class ActionValidator:
    """Validate supported operations and pause actions needing human control."""

    def validate(
        self,
        action: BrowserAction,
        element: InteractiveElement,
        page_text: str = "",
    ) -> ValidationDecision:
        """Reject incompatible, consequential, or sensitive actions pre-execution."""
        if action.requires_confirmation:
            return ValidationDecision(False, "This action is marked as requiring confirmation.", True)

        description = element_description(element)
        action_type = action.action_type
        if action_type == "fill":
            allowed = element.element_type in {"text_input", "textarea"} or element.input_type in {"email", "tel", "number"}
            if not allowed:
                return ValidationDecision(False, "Fill is only supported for text-like inputs and textareas.")
            if action.value is None:
                return ValidationDecision(False, "A fill action requires a value.")
        elif action_type == "select":
            if element.element_type != "dropdown":
                return ValidationDecision(False, "Select is only supported for dropdown elements.")
            if action.value is None:
                return ValidationDecision(False, "A select action requires an option label or value.")
        elif action_type in {"check", "uncheck"}:
            if element.element_type != "checkbox":
                return ValidationDecision(False, "Check and uncheck are only supported for checkboxes.")
        elif action_type == "radio_select":
            if element.element_type != "radio":
                return ValidationDecision(False, "Radio select is only supported for radio buttons.")
        elif action_type == "click":
            if element.element_type not in {"button", "link"}:
                return ValidationDecision(False, "Click is only supported for buttons and links.")
            if _FINAL_SUBMISSION.search(description) or element.input_type == "submit" or element.is_submit_control:
                return ValidationDecision(False, "Final application submission is blocked in this phase.", True)
        elif action_type == "upload":
            if element.element_type != "file_upload" and element.input_type != "file":
                return ValidationDecision(False, "Upload is only supported for file inputs.")
            if not action.file_path:
                return ValidationDecision(False, "Upload requires an explicit file path.")
        elif action_type != "scroll_into_view":
            return ValidationDecision(False, "Unsupported action type.")

        if action_type in {"check", "radio_select", "select"} and _LEGAL_ACCEPTANCE.search(description):
            return ValidationDecision(False, "Legal declarations and consent require explicit human review; this engine will not accept them.", True)
        if action_type == "click" and element.element_type == "button" and _LEGAL_ACCEPTANCE.search(description):
            return ValidationDecision(False, "Legal declarations and consent require explicit human review; this engine will not accept them.", True)

        if action_type != "scroll_into_view" and (_PAYMENT.search(description) or _PAYMENT.search(page_text)):
            return ValidationDecision(False, "Payment-related actions require human participation and are blocked.", True)
        if action_type != "scroll_into_view" and (_AUTH_CHALLENGE.search(description) or _AUTH_CHALLENGE.search(page_text)):
            return ValidationDecision(False, "Authentication, OTP, and CAPTCHA actions require human participation.", True)
        if action_type == "fill" and requires_human_for_authentication(element):
            return ValidationDecision(False, "Sensitive authentication fields must be completed by a human.", True)

        return ValidationDecision(True)
