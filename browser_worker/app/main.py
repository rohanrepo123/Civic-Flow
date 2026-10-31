from contextlib import asynccontextmanager
import hmac
from typing import AsyncIterator
from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, Security, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from civicflow_contracts.browser import (
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
from browser_worker.app.config import BrowserWorkerSettings
from browser_worker.app.services.session_manager import BrowserServiceError, BrowserSessionManager


class BrowserManagerProtocol:
    async def start(self) -> None: ...
    async def stop(self) -> None: ...
    async def create_session(self, request: BrowserSessionCreate) -> BrowserSessionResponse: ...
    async def get_session(self, session_id: str) -> BrowserSessionResponse: ...
    async def observe(self, session_id: str) -> BrowserObservation: ...
    async def execute_action(self, session_id: str, request: BrowserActionRequest) -> BrowserActionResponse: ...
    async def set_control_mode(self, session_id: str, request: ControlModeRequest) -> ControlModeResponse: ...
    async def send_user_input(self, session_id: str, event: UserInputEvent) -> Acknowledgement: ...
    async def get_screenshot(self, session_id: str) -> bytes: ...
    async def stream_screenshots(self, session_id: str) -> AsyncIterator[bytes]: ...
    async def close_session(self, session_id: str) -> None: ...


def create_app(
    *,
    settings: BrowserWorkerSettings | None = None,
    manager: BrowserManagerProtocol | None = None,
) -> FastAPI:
    configured = settings or BrowserWorkerSettings.from_environment()
    browser_manager = manager or BrowserSessionManager(configured)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        await browser_manager.start()
        try:
            yield
        finally:
            await browser_manager.stop()

    app = FastAPI(title="CivicFlow Browser Worker", version="1.0.0", lifespan=lifespan)
    bearer = HTTPBearer(auto_error=False)

    async def require_service_auth(
        credentials: HTTPAuthorizationCredentials | None = Security(bearer),
    ) -> None:
        if not configured.api_token:
            raise BrowserServiceError(
                "service_auth_not_configured",
                "Browser Worker service authentication is not configured",
                503,
            )
        if credentials is None or not hmac.compare_digest(credentials.credentials, configured.api_token):
            raise BrowserServiceError("unauthorized", "Service authentication failed", 401)

    @app.exception_handler(BrowserServiceError)
    async def browser_error_handler(_: Request, exc: BrowserServiceError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"code": exc.code, "message": str(exc), "request_id": uuid4().hex},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(_: Request, __: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"code": "validation_error", "message": "Request failed schema validation", "request_id": uuid4().hex},
        )

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "browser-worker"}

    @app.post(
        "/api/v1/sessions",
        response_model=BrowserSessionResponse,
        status_code=status.HTTP_201_CREATED,
        dependencies=[Depends(require_service_auth)],
    )
    async def create_session(request: BrowserSessionCreate) -> BrowserSessionResponse:
        return await browser_manager.create_session(request)

    @app.get(
        "/api/v1/sessions/{session_id}",
        response_model=BrowserSessionResponse,
        dependencies=[Depends(require_service_auth)],
    )
    async def get_session(session_id: str) -> BrowserSessionResponse:
        return await browser_manager.get_session(session_id)

    @app.get(
        "/api/v1/sessions/{session_id}/observation",
        response_model=BrowserObservation,
        dependencies=[Depends(require_service_auth)],
    )
    async def observe(session_id: str) -> BrowserObservation:
        return await browser_manager.observe(session_id)

    @app.post(
        "/api/v1/sessions/{session_id}/actions",
        response_model=BrowserActionResponse,
        dependencies=[Depends(require_service_auth)],
    )
    async def execute_action(session_id: str, request: BrowserActionRequest) -> BrowserActionResponse:
        return await browser_manager.execute_action(session_id, request)

    @app.post(
        "/api/v1/sessions/{session_id}/control-mode",
        response_model=ControlModeResponse,
        dependencies=[Depends(require_service_auth)],
    )
    async def set_control_mode(session_id: str, request: ControlModeRequest) -> ControlModeResponse:
        return await browser_manager.set_control_mode(session_id, request)

    @app.post(
        "/api/v1/sessions/{session_id}/user-input",
        response_model=Acknowledgement,
        dependencies=[Depends(require_service_auth)],
    )
    async def send_user_input(session_id: str, event: UserInputEvent) -> Acknowledgement:
        return await browser_manager.send_user_input(session_id, event)

    @app.get(
        "/api/v1/sessions/{session_id}/screenshot",
        dependencies=[Depends(require_service_auth)],
    )
    async def get_screenshot(session_id: str) -> Response:
        return Response(await browser_manager.get_screenshot(session_id), media_type="image/jpeg")

    @app.get(
        "/api/v1/sessions/{session_id}/stream",
        dependencies=[Depends(require_service_auth)],
    )
    async def stream_screenshots(session_id: str) -> StreamingResponse:
        return StreamingResponse(
            browser_manager.stream_screenshots(session_id),
            media_type="multipart/x-mixed-replace; boundary=frame",
        )

    @app.delete(
        "/api/v1/sessions/{session_id}",
        status_code=status.HTTP_204_NO_CONTENT,
        dependencies=[Depends(require_service_auth)],
    )
    async def close_session(session_id: str) -> Response:
        await browser_manager.close_session(session_id)
        return Response(status_code=status.HTTP_204_NO_CONTENT)

    app.state.browser_manager = browser_manager
    app.state.settings = configured
    return app


app = create_app()
