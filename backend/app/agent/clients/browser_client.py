from typing import Protocol

import httpx
from pydantic import ValidationError

from backend.app.agent.schemas.browser import (
    Acknowledgement,
    BrowserActionRequest,
    BrowserActionResponse,
    BrowserObservation,
    BrowserSessionCreate,
    BrowserSessionResponse,
    ControlModeRequest,
    ControlModeResponse,
    UserInputEvent,
)
from backend.app.agent.services.action_policy import ActionPolicy


class BrowserClientError(RuntimeError):
    def __init__(self, message: str, *, status_code: int | None = None, code: str = "browser_error") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code


class BrowserClient(Protocol):
    async def create_session(self, request: BrowserSessionCreate) -> BrowserSessionResponse: ...
    async def get_session(self, session_id: str) -> BrowserSessionResponse: ...
    async def observe(self, session_id: str) -> BrowserObservation: ...
    async def execute_action(self, session_id: str, request: BrowserActionRequest) -> BrowserActionResponse: ...
    async def set_control_mode(self, session_id: str, mode: ControlModeRequest) -> ControlModeResponse: ...
    async def send_user_input(self, session_id: str, event: UserInputEvent) -> Acknowledgement: ...
    async def get_screenshot(self, session_id: str) -> bytes: ...
    async def close_session(self, session_id: str) -> None: ...


class GuardedBrowserClient:
    """Apply local action policy before forwarding to a live or mock worker."""

    def __init__(self, client: BrowserClient, policy: ActionPolicy) -> None:
        self._client = client
        self._policy = policy
        self._observations: dict[str, BrowserObservation] = {}

    async def create_session(self, request: BrowserSessionCreate) -> BrowserSessionResponse:
        response = await self._client.create_session(request)
        self._observations.pop(response.session_id, None)
        return response

    async def get_session(self, session_id: str) -> BrowserSessionResponse:
        return await self._client.get_session(session_id)

    async def observe(self, session_id: str) -> BrowserObservation:
        observation = await self._client.observe(session_id)
        self._observations[session_id] = observation
        return observation

    async def execute_action(
        self,
        session_id: str,
        request: BrowserActionRequest,
    ) -> BrowserActionResponse:
        observation = self._observations.get(session_id)
        if observation is None:
            observation = await self.observe(session_id)
        reason = self._policy.validate(request, observation)
        if reason is not None:
            status = (
                "stale_observation"
                if request.observation_id != observation.observation_id
                else "target_not_found"
                if "target is not present" in reason
                else "policy_blocked"
            )
            return BrowserActionResponse(
                action_id=request.action_id,
                status=status,
                message=reason,
                before_observation_id=request.observation_id,
                after_observation_id=observation.observation_id,
                page_url=observation.page.url,
            )
        self._observations.pop(session_id, None)
        return await self._client.execute_action(session_id, request)

    async def set_control_mode(self, session_id: str, mode: ControlModeRequest) -> ControlModeResponse:
        return await self._client.set_control_mode(session_id, mode)

    async def send_user_input(self, session_id: str, event: UserInputEvent) -> Acknowledgement:
        response = await self._client.send_user_input(session_id, event)
        self._observations.pop(session_id, None)
        return response

    async def get_screenshot(self, session_id: str) -> bytes:
        return await self._client.get_screenshot(session_id)

    async def close_session(self, session_id: str) -> None:
        self._observations.pop(session_id, None)
        await self._client.close_session(session_id)


class BrowserHttpClient:
    """Member 2 adapter; communicates with Member 3 only over the documented API."""

    def __init__(
        self,
        base_url: str,
        *,
        service_token: str | None = None,
        timeout_seconds: float = 30,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        if not base_url.strip():
            raise ValueError("browser worker base URL is required")
        headers = {"Authorization": f"Bearer {service_token}"} if service_token else {}
        self._client = client or httpx.AsyncClient(
            base_url=base_url.rstrip("/"),
            headers=headers,
            timeout=timeout_seconds,
        )
        self._owns_client = client is None

    async def close(self) -> None:
        if self._owns_client:
            await self._client.aclose()

    async def __aenter__(self) -> "BrowserHttpClient":
        return self

    async def __aexit__(self, *_: object) -> None:
        await self.close()

    async def create_session(self, request: BrowserSessionCreate) -> BrowserSessionResponse:
        return await self._json("POST", "/api/v1/sessions", BrowserSessionResponse, json=request.model_dump(mode="json"))

    async def get_session(self, session_id: str) -> BrowserSessionResponse:
        return await self._json("GET", self._session_path(session_id), BrowserSessionResponse)

    async def observe(self, session_id: str) -> BrowserObservation:
        return await self._json(
            "GET", f"{self._session_path(session_id)}/observation", BrowserObservation
        )

    async def execute_action(
        self,
        session_id: str,
        request: BrowserActionRequest,
    ) -> BrowserActionResponse:
        return await self._json(
            "POST",
            f"{self._session_path(session_id)}/actions",
            BrowserActionResponse,
            json=request.model_dump(mode="json"),
        )

    async def set_control_mode(
        self,
        session_id: str,
        mode: ControlModeRequest,
    ) -> ControlModeResponse:
        return await self._json(
            "POST",
            f"{self._session_path(session_id)}/control-mode",
            ControlModeResponse,
            json=mode.model_dump(mode="json"),
        )

    async def send_user_input(self, session_id: str, event: UserInputEvent) -> Acknowledgement:
        return await self._json(
            "POST",
            f"{self._session_path(session_id)}/user-input",
            Acknowledgement,
            json=event.model_dump(mode="json"),
        )

    async def get_screenshot(self, session_id: str) -> bytes:
        response = await self._request("GET", f"{self._session_path(session_id)}/screenshot")
        return response.content

    async def close_session(self, session_id: str) -> None:
        await self._request("DELETE", self._session_path(session_id))

    @staticmethod
    def _session_path(session_id: str) -> str:
        if not session_id or "/" in session_id or ".." in session_id:
            raise ValueError("invalid browser session ID")
        return f"/api/v1/sessions/{session_id}"

    async def _json(self, method: str, path: str, model: type, **kwargs: object):
        response = await self._request(method, path, **kwargs)
        try:
            return model.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise BrowserClientError("Browser Worker returned an invalid response", code="invalid_response") from exc

    async def _request(self, method: str, path: str, **kwargs: object) -> httpx.Response:
        try:
            response = await self._client.request(method, path, **kwargs)
            response.raise_for_status()
            return response
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            code = f"http_{status}"
            try:
                payload = exc.response.json()
                code = str(payload.get("code", code))
            except (ValueError, AttributeError):
                pass
            raise BrowserClientError(
                "Browser Worker rejected the request", status_code=status, code=code
            ) from exc
        except httpx.RequestError as exc:
            raise BrowserClientError("Browser Worker is unavailable", code="transport_error") from exc
