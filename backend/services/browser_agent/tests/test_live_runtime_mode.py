"""Regression checks that live browser failures are never reported as success."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

SERVICE_ROOT = Path(__file__).resolve().parents[1]
CONTRACTS_ROOT = Path(__file__).resolve().parents[3] / "contracts" / "civicflow_contracts"
sys.path.insert(0, str(CONTRACTS_ROOT))
sys.path.insert(0, str(SERVICE_ROOT))

from app import main  # noqa: E402
from app.playwright_runtime import PlaywrightRuntime  # noqa: E402
from civicflow_contracts.browser import BrowserSessionCreateRequest  # noqa: E402


@pytest.fixture(autouse=True)
def clear_sessions():
    main.sessions.clear()
    main.stream_tokens.clear()
    main.runtimes.clear()
    main.PLAYWRIGHT_READY = False
    yield
    main.sessions.clear()
    main.stream_tokens.clear()
    main.runtimes.clear()
    main.PLAYWRIGHT_READY = False


def request() -> BrowserSessionCreateRequest:
    return BrowserSessionCreateRequest(
        application_id="local-test-application",
        service_id="local-test-service",
        approved_portal_url="https://example.gov.in",
        allowed_domains=["example.gov.in"],
    )


def test_live_chromium_failure_does_not_create_a_simulated_session(monkeypatch):
    monkeypatch.setattr(main, "PLAYWRIGHT_ENABLED", True)
    monkeypatch.setattr(main, "MOCK_MODE_ENABLED", False)

    async def fail_start(cls, *, headless: bool = False):
        raise RuntimeError("Chromium executable is unavailable")

    monkeypatch.setattr(PlaywrightRuntime, "start", fail_start)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(main.create_session(request()))

    assert raised.value.status_code == 503
    assert "Live Chromium could not open the portal" in raised.value.detail
    assert main.sessions == {}
    assert main.runtimes == {}


def test_mock_session_requires_explicit_mock_configuration(monkeypatch):
    monkeypatch.setattr(main, "PLAYWRIGHT_ENABLED", False)
    monkeypatch.setattr(main, "MOCK_MODE_ENABLED", False)

    with pytest.raises(HTTPException) as raised:
        asyncio.run(main.create_session(request()))

    assert raised.value.status_code == 503
    assert main.sessions == {}


def test_explicit_mock_mode_is_labeled_as_mock(monkeypatch):
    monkeypatch.setattr(main, "PLAYWRIGHT_ENABLED", False)
    monkeypatch.setattr(main, "MOCK_MODE_ENABLED", True)

    session = asyncio.run(main.create_session(request()))

    assert session.session_status == "active"
    assert str(session.browser_session_id) in {str(key) for key in main.sessions}
    assert asyncio.run(main.ready())["mode"] == "mock"
