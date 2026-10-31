import asyncio
import os
from pathlib import Path

import pytest

pytest.importorskip("playwright")

from civicflow_contracts.browser import (
    BrowserAction,
    BrowserActionRequest,
    BrowserSessionCreate,
    ControlMode,
    ControlModeRequest,
    ElementRole,
    UserInputEvent,
    UserInputType,
    Viewport,
)
from browser_worker.app.config import BrowserWorkerSettings
from browser_worker.app.services.session_manager import BrowserSessionManager


PORTAL = "https://civicflow.test"


def find_installed_chromium() -> Path | None:
    roots: list[Path] = []
    configured_root = os.getenv("PLAYWRIGHT_BROWSERS_PATH")
    if configured_root and configured_root != "0":
        roots.append(Path(configured_root))
    local_app_data = os.getenv("LOCALAPPDATA")
    if local_app_data:
        roots.append(Path(local_app_data) / "ms-playwright")
    roots.extend(
        [
            Path.home() / ".cache" / "ms-playwright",
            Path.home() / "Library" / "Caches" / "ms-playwright",
        ]
    )
    candidates: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        candidates.extend(root.glob("chromium-*/chrome-win64/chrome.exe"))
        candidates.extend(root.glob("chromium-*/chrome-linux/chrome"))
        candidates.extend(root.glob("chromium-*/chrome-linux64/chrome"))
    return candidates[-1] if candidates else None


CHROMIUM_EXECUTABLE = find_installed_chromium()
RUN_REAL_BROWSER = os.getenv("CIVICFLOW_RUN_BROWSER_E2E") == "1"


@pytest.mark.skipif(
    not RUN_REAL_BROWSER or CHROMIUM_EXECUTABLE is None,
    reason="Set CIVICFLOW_RUN_BROWSER_E2E=1 and install Chromium to run the local browser integration test",
)
def test_real_worker_uses_chromium_with_local_mock_pages_and_manual_control() -> None:
    async def run() -> None:
        pages = {
            PORTAL: """
                <html><head><title>Local CivicFlow portal</title></head><body>
                    <a href='https://civicflow.test/apply'>New Application</a>
                </body></html>
            """,
            f"{PORTAL}/apply": """
                <html><head><title>Local application form</title></head><body>
                    <label>Applicant Name <input aria-label='Applicant Name' required></label>
                    <label>One-time password <input type='password' aria-label='One-time password'></label>
                </body></html>
            """,
        }
        manager = BrowserSessionManager(
            BrowserWorkerSettings("integration-token", frozenset({"civicflow.test"})),
            mock_pages=pages,
            executable_path=str(CHROMIUM_EXECUTABLE),
        )
        await manager.start()
        session_id = None
        try:
            session = await manager.create_session(
                BrowserSessionCreate(
                    task_id="task-integration",
                    start_url=PORTAL,
                    viewport=Viewport(width=1280, height=800),
                )
            )
            session_id = session.session_id
            initial = await manager.observe(session_id)
            link = next(element for element in initial.elements if element.label == "New Application")
            action = BrowserActionRequest(
                action_id="click-application",
                observation_id=initial.observation_id,
                action=BrowserAction(type="click", element_id=link.element_id),
                expected_result="Application form opens",
            )
            click_result = await manager.execute_action(session_id, action)
            assert click_result.status == "succeeded"
            form = await manager.observe(session_id)
            assert form.page.url == f"{PORTAL}/apply"
            assert any(element.role is ElementRole.TEXTBOX for element in form.elements)
            password = next(element for element in form.elements if element.label == "One-time password")
            assert password.sensitive is True

            secret_fill = BrowserActionRequest(
                action_id="attempt-otp",
                observation_id=form.observation_id,
                action=BrowserAction(type="fill", element_id=password.element_id, value="123456"),
                expected_result="Should be blocked",
            )
            blocked = await manager.execute_action(session_id, secret_fill)
            assert blocked.status == "policy_blocked"
            assert "123456" not in blocked.message

            screenshot = await manager.get_screenshot(session_id)
            assert screenshot.startswith(b"\xff\xd8")

            await manager.set_control_mode(
                session_id,
                ControlModeRequest(control_mode=ControlMode.USER),
            )
            page = manager._sessions[session_id].page
            bounds = await page.locator("input[aria-label='Applicant Name']").bounding_box()
            await manager.send_user_input(
                session_id,
                UserInputEvent(
                    event_id="manual-click",
                    type=UserInputType.POINTER_CLICK,
                    x_normalized=(bounds["x"] + bounds["width"] / 2) / 1280,
                    y_normalized=(bounds["y"] + bounds["height"] / 2) / 800,
                ),
            )
            await manager.send_user_input(
                session_id,
                UserInputEvent(event_id="manual-text", type=UserInputType.TEXT_INPUT, text="Citizen Name"),
            )
            assert await page.locator("input[aria-label='Applicant Name']").input_value() == "Citizen Name"
        finally:
            if session_id:
                await manager.close_session(session_id)
            await manager.stop()

    asyncio.run(run())
