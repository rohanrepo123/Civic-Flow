import re
from urllib.parse import urlparse

from civicflow_contracts.browser import BrowserActionRequest, BrowserObservation


_SENSITIVE_LABEL = re.compile(r"\b(password|passcode|otp|one.time.code|verification code|captcha)\b", re.I)
_AUTH_LABEL = re.compile(r"\b(log ?in|sign ?in|authenticate)\b", re.I)
_CONSEQUENTIAL_LABEL = re.compile(
    r"\b(submit|submission|payment|pay now|declaration|accept|agree|consent|certify|"
    r"undertaking|signature|sign and submit)\b",
    re.I,
)


class WorkerActionPolicy:
    """Worker-owned validation, independent of agent implementation details."""

    def __init__(self, approved_domains: set[str]) -> None:
        self._approved_domains = {domain.casefold().strip(".") for domain in approved_domains}

    def validate(self, request: BrowserActionRequest, observation: BrowserObservation) -> str | None:
        if request.observation_id != observation.observation_id:
            return "Action was based on a stale observation."
        action = request.action
        if action.type == "navigate":
            if action.url is None:
                return "Navigation requires an explicit URL."
            host = (urlparse(str(action.url)).hostname or "").casefold().strip(".")
            if not self._allowed_host(host):
                return "Navigation destination is not on the approved domain list."
            if re.search(r"/(submit|payment|declaration)(/|$)", urlparse(str(action.url)).path, re.I):
                return "Consequential submission, payment, or declaration navigation is blocked."
        if action.type in {"click", "fill", "select_option", "check", "uncheck", "press_key", "upload_file"}:
            element = next(
                (item for item in observation.elements if item.element_id == action.element_id),
                None,
            )
            if element is None:
                return "Action target is not present in this observation."
            if not element.visible or not element.enabled:
                return "Action target is not visible and enabled."
            label = " ".join((element.label, element.input_type or "", element.placeholder or ""))
            if action.type in {"fill", "press_key"} and (element.sensitive or _SENSITIVE_LABEL.search(label)):
                return "Agent interaction with sensitive authentication fields is blocked."
            if action.type == "click" and _AUTH_LABEL.search(label):
                return "Authentication must be completed by the citizen."
            if action.type in {"click", "fill", "check", "uncheck", "press_key"} and _CONSEQUENTIAL_LABEL.search(label):
                return "Consequential submission, payment, or declaration actions require the citizen."
        return None

    def _allowed_host(self, host: str) -> bool:
        return any(host == domain or host.endswith(f".{domain}") for domain in self._approved_domains)
