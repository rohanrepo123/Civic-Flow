"""Translate Member 2 observations to Member 3's versioned HTTP contracts."""

import re
from datetime import UTC, datetime
from urllib.parse import urlparse
from uuid import uuid4

import httpx
from civicflow_contracts.browser import BrowserCommand, BrowserSessionCreateRequest

from backend.app.agent.schemas.browser import (
    BrowserAction, BrowserActionRequest, BrowserActionResponse, BrowserObservation,
    BrowserSessionCreate, BrowserSessionResponse, ControlMode, ControlModeResponse,
    ObservedElement, ObservedPage, PageState,
)
from backend.app.agent.services.action_policy import ActionPolicy


_SENSITIVE = re.compile(r"password|passcode|otp|captcha|pin|payment|card|declar|consent|agree|submit|signature", re.I)


class Member3BrowserClient:
    def __init__(self, base_url: str, token: str, *, client: httpx.AsyncClient | None = None) -> None:
        self.client = client or httpx.AsyncClient(base_url=base_url.rstrip("/"),
            headers={"Authorization": f"Bearer {token}"}, timeout=25)
        self.observations: dict[str, BrowserObservation] = {}
        self.snapshots: dict[str, dict] = {}
        self.domains: dict[str, set[str]] = {}
        self.modes: dict[str, str] = {}

    async def close(self) -> None:
        await self.client.aclose()

    async def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        response = await self.client.request(method, "/internal/v1/browser" + path, json=payload)
        response.raise_for_status()
        return response.json()

    async def create_session_for_task(self, request: BrowserSessionCreate, *, user_id: str, service_id: str) -> BrowserSessionResponse:
        host = urlparse(str(request.start_url)).hostname
        payload = BrowserSessionCreateRequest(user_id=user_id, application_id=request.task_id,
            service_id=service_id, approved_portal_url=request.start_url, allowed_domains=[host],
            requested_capabilities=["navigate", "inspect", "fill_non_sensitive"])
        data = await self._request("POST", "/sessions", payload.model_dump(mode="json"))
        sid = str(data["browser_session_id"])
        self.domains[sid] = {host}
        return BrowserSessionResponse(session_id=sid, status="running", control_mode=ControlMode.AGENT,
            created_at=datetime.now(UTC), viewport=request.viewport)

    async def observe(self, session_id: str) -> BrowserObservation:
        command = BrowserCommand(command_type="inspect")
        data = await self._request("POST", f"/sessions/{session_id}/commands", command.model_dump(mode="json"))
        snapshot = data["snapshot"]
        self.snapshots[session_id] = snapshot
        self.modes[session_id] = data.get("mode", "unknown")
        elements = []
        roles = {"text_input": "textbox", "text": "textbox", "textarea": "textbox",
                 "dropdown": "combobox", "button": "button", "link": "link", "checkbox": "checkbox"}
        for item in snapshot.get("interactive_elements", []):
            label = item.get("label") or item.get("name") or item.get("text") or ""
            sensitive = bool(_SENSITIVE.search(label + " " + str(item.get("input_type", ""))))
            elements.append(ObservedElement(element_id=item["element_id"],
                role=roles.get(item.get("element_type"), "other"), label=label,
                input_type=item.get("input_type"), visible=item.get("visible", True),
                enabled=item.get("enabled", True), required=item.get("required", False), sensitive=sensitive))
        auth = any(re.search(r"password|otp|captcha", item.label + " " + (item.input_type or ""), re.I) for item in elements)
        observation = BrowserObservation(session_id=session_id, observation_id=str(uuid4()),
            sequence=self.observations[session_id].sequence + 1 if session_id in self.observations else 1,
            page=ObservedPage(url=snapshot["url"], title=snapshot.get("title", ""),
                state=PageState.AUTHENTICATION_REQUIRED if auth else PageState.READY),
            elements=elements, screenshot_url=f"/internal/v1/browser/sessions/{session_id}/screenshot")
        self.observations[session_id] = observation
        return observation

    async def execute_action(self, session_id: str, request: BrowserActionRequest) -> BrowserActionResponse:
        observation = self.observations[session_id]
        reason = ActionPolicy(self.domains.get(session_id, set())).validate(request, observation)
        action = request.action
        if action.type != "fill":
            reason = "Only non-sensitive field preparation is enabled in this adapter."
        if self.modes.get(session_id) != "playwright":
            reason = "This is a simulated browser session; no live form was filled."
        if reason:
            return BrowserActionResponse(action_id=request.action_id, status="policy_blocked", message=reason,
                before_observation_id=request.observation_id, page_url=observation.page.url)
        element = next(item for item in observation.elements if item.element_id == action.element_id)
        # Member 3 currently grounds fills by label, so require a unique observed label.
        if sum(item.label == element.label for item in observation.elements) != 1:
            raise ValueError("Ambiguous observed browser field")
        command = BrowserCommand(command_type="fill", element_id=element.label, value=action.value)
        data = await self._request("POST", f"/sessions/{session_id}/commands", command.model_dump(mode="json"))
        verified = data.get("mode") == "playwright" and data.get("result", {}).get("verified") is True
        return BrowserActionResponse(action_id=request.action_id, status="succeeded" if verified else "user_intervention_required",
            message="Field preparation verified by worker." if verified else "Worker did not verify the fill; please review it.",
            before_observation_id=request.observation_id, page_url=observation.page.url)

    async def propose_action(self, state) -> BrowserActionRequest | None:
        sid = state["browser_session_id"]
        if self.modes.get(sid) != "playwright":
            return None
        observation = state["browser_observation"]
        used = {item.action_id for item in state.get("action_history", [])}
        profile = {re.sub(r"[^a-z0-9]", "", key.casefold()): value
                   for key, value in state.get("applicant_profile", {}).items()}
        for element in observation.elements:
            key = re.sub(r"[^a-z0-9]", "", element.label.casefold())
            action_id = f"fill:{element.element_id}"
            if (key in profile and profile[key] is not None and not isinstance(profile[key], (dict, list))
                    and element.role.value == "textbox" and not element.sensitive and action_id not in used):
                return BrowserActionRequest(action_id=action_id, observation_id=observation.observation_id,
                    action=BrowserAction(type="fill", element_id=element.element_id, value=str(profile[key])),
                    expected_result="The observed field equals the user-provided value.")
        return None

    async def verify_action(self, action, before, after) -> bool:
        if self.modes.get(after.session_id) != "playwright" or before.page.url != after.page.url:
            return False
        old = next((item for item in before.elements if item.element_id == action.action.element_id), None)
        matches = [item for item in self.snapshots[after.session_id].get("interactive_elements", [])
                   if old and (item.get("label") or item.get("name") or item.get("text")) == old.label]
        return len(matches) == 1 and matches[0].get("current_value") == action.action.value

    async def set_control_mode(self, session_id, mode) -> ControlModeResponse:
        action = {ControlMode.USER: "take-control", ControlMode.AGENT: "return-control", ControlMode.PAUSED: "pause"}[mode.control_mode]
        await self._request("POST", f"/sessions/{session_id}/{action}")
        return ControlModeResponse(session_id=session_id, control_mode=mode.control_mode)

    async def close_session(self, session_id: str) -> None:
        await self._request("POST", f"/sessions/{session_id}/close")
        for mapping in (self.observations, self.snapshots, self.domains, self.modes):
            mapping.pop(session_id, None)
