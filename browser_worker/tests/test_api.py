from datetime import UTC, datetime

from fastapi.testclient import TestClient

from civicflow_contracts.browser import (
    Acknowledgement,
    BrowserObservation,
    BrowserSessionCreate,
    BrowserSessionResponse,
    ControlMode,
    ControlModeRequest,
    ControlModeResponse,
    ObservedPage,
    PageState,
    Viewport,
)
from browser_worker.app.config import BrowserWorkerSettings
from browser_worker.app.main import create_app


class FakeManager:
    def __init__(self) -> None:
        self.closed: list[str] = []

    async def start(self) -> None: pass
    async def stop(self) -> None: pass

    async def create_session(self, request: BrowserSessionCreate) -> BrowserSessionResponse:
        return BrowserSessionResponse(
            session_id="browser-test",
            status="running",
            control_mode=ControlMode.AGENT,
            created_at=datetime.now(UTC),
            viewport=request.viewport,
        )

    async def get_session(self, session_id: str) -> BrowserSessionResponse:
        return BrowserSessionResponse(
            session_id=session_id,
            status="running",
            control_mode=ControlMode.AGENT,
            created_at=datetime.now(UTC),
            viewport=Viewport(width=1280, height=800),
        )

    async def observe(self, session_id: str) -> BrowserObservation:
        return BrowserObservation(
            session_id=session_id,
            observation_id="obs-1",
            sequence=1,
            page=ObservedPage(url="https://example.gov.in", title="Portal", state=PageState.READY),
            elements=[],
            screenshot_url=f"/api/v1/sessions/{session_id}/screenshot",
        )

    async def execute_action(self, session_id, request):
        return {
            "action_id": request.action_id,
            "status": "succeeded",
            "message": "executed",
            "before_observation_id": request.observation_id,
            "after_observation_id": "obs-2",
            "page_url": "https://example.gov.in",
        }

    async def set_control_mode(self, session_id: str, request: ControlModeRequest) -> ControlModeResponse:
        return ControlModeResponse(session_id=session_id, control_mode=request.control_mode)

    async def send_user_input(self, session_id: str, event) -> Acknowledgement:
        return Acknowledgement(accepted=True)

    async def get_screenshot(self, session_id: str) -> bytes:
        return b"jpeg-fixture"

    async def stream_screenshots(self, session_id: str):
        yield b"--frame\r\n"

    async def close_session(self, session_id: str) -> None:
        self.closed.append(session_id)


def make_client(token: str | None = "unit-token") -> tuple[TestClient, FakeManager]:
    manager = FakeManager()
    settings = BrowserWorkerSettings(token, frozenset({"example.gov.in"}))
    return TestClient(create_app(settings=settings, manager=manager)), manager


def test_health_is_public_and_protected_endpoints_require_service_auth() -> None:
    client, _ = make_client()
    with client:
        assert client.get("/healthz").json() == {"status": "ok", "service": "browser-worker"}
        denied = client.post("/api/v1/sessions", json={})
        assert denied.status_code == 401
        assert denied.json()["code"] == "unauthorized"


def test_missing_service_token_fails_closed() -> None:
    client, _ = make_client(token=None)
    with client:
        response = client.get("/api/v1/sessions/abc", headers={"Authorization": "Bearer x"})
        assert response.status_code == 503
        assert response.json()["code"] == "service_auth_not_configured"


def test_session_and_observation_routes_match_shared_contract() -> None:
    client, manager = make_client()
    headers = {"Authorization": "Bearer unit-token"}
    with client:
        created = client.post(
            "/api/v1/sessions",
            headers=headers,
            json={
                "task_id": "task-1",
                "start_url": "https://example.gov.in",
                "viewport": {"width": 1280, "height": 800},
            },
        )
        assert created.status_code == 201
        assert created.json()["session_id"] == "browser-test"
        observed = client.get("/api/v1/sessions/browser-test/observation", headers=headers)
        assert observed.status_code == 200
        assert observed.json()["observation_id"] == "obs-1"
        screenshot = client.get("/api/v1/sessions/browser-test/screenshot", headers=headers)
        assert screenshot.status_code == 200
        assert screenshot.headers["content-type"] == "image/jpeg"
        closed = client.delete("/api/v1/sessions/browser-test", headers=headers)
        assert closed.status_code == 204
        assert manager.closed == ["browser-test"]


def test_invalid_request_uses_documented_error_shape() -> None:
    client, _ = make_client()
    with client:
        response = client.post(
            "/api/v1/sessions",
            headers={"Authorization": "Bearer unit-token"},
            json={"task_id": "task-1", "start_url": "not-a-url", "viewport": {}},
        )
        assert response.status_code == 422
        assert response.json()["code"] == "validation_error"
        assert "request_id" in response.json()
