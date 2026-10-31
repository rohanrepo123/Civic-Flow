import asyncio
from datetime import UTC, datetime

import httpx
import pytest

from backend.app.agent.clients.browser_client import BrowserClientError, BrowserHttpClient
from backend.app.agent.schemas.browser import BrowserSessionCreate, Viewport


def test_http_client_uses_documented_paths_and_validates_responses() -> None:
    calls: list[tuple[str, str]] = []

    async def handler(request: httpx.Request) -> httpx.Response:
        calls.append((request.method, request.url.path))
        if request.method == "POST" and request.url.path == "/api/v1/sessions":
            return httpx.Response(
                201,
                json={
                    "session_id": "browser-1",
                    "status": "running",
                    "control_mode": "agent",
                    "created_at": datetime.now(UTC).isoformat(),
                    "viewport": {"width": 1280, "height": 800},
                },
            )
        if request.method == "GET" and request.url.path.endswith("/screenshot"):
            return httpx.Response(200, content=b"image-bytes", headers={"content-type": "image/jpeg"})
        if request.method == "DELETE":
            return httpx.Response(204)
        return httpx.Response(404, json={"code": "not_found", "message": "private server detail"})

    async def run() -> None:
        transport = httpx.MockTransport(handler)
        async with httpx.AsyncClient(base_url="http://browser-worker", transport=transport) as raw_client:
            client = BrowserHttpClient("http://browser-worker", client=raw_client)
            session = await client.create_session(
                BrowserSessionCreate(
                    task_id="task-1",
                    start_url="https://example.gov.in",
                    viewport=Viewport(width=1280, height=800),
                )
            )
            assert session.session_id == "browser-1"
            assert await client.get_screenshot(session.session_id) == b"image-bytes"
            await client.close_session(session.session_id)

    asyncio.run(run())
    assert calls == [
        ("POST", "/api/v1/sessions"),
        ("GET", "/api/v1/sessions/browser-1/screenshot"),
        ("DELETE", "/api/v1/sessions/browser-1"),
    ]


def test_http_client_maps_worker_errors_without_leaking_response_body() -> None:
    async def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            404,
            json={"code": "session_not_found", "message": "sensitive user detail"},
        )

    async def run() -> None:
        async with httpx.AsyncClient(
            base_url="http://browser-worker",
            transport=httpx.MockTransport(handler),
        ) as raw_client:
            client = BrowserHttpClient("http://browser-worker", client=raw_client)
            with pytest.raises(BrowserClientError) as error:
                await client.observe("missing-session")
            assert error.value.status_code == 404
            assert error.value.code == "session_not_found"
            assert "sensitive user detail" not in str(error.value)

    asyncio.run(run())


def test_http_client_rejects_path_injection_in_session_id() -> None:
    client = BrowserHttpClient("http://browser-worker", client=httpx.AsyncClient())
    with pytest.raises(ValueError, match="invalid browser session ID"):
        client._session_path("../other")
    asyncio.run(client._client.aclose())
