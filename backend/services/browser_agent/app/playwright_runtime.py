"""Optional Playwright runtime adapter for the Core Browser session API.

The HTTP session contract remains stable. This adapter keeps Member 3's
observation/grounding/workflow package behind an explicit feature flag so the
local mock mode remains usable when Chromium is unavailable.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from browser_agent.browser import BrowserController


@dataclass
class PlaywrightRuntime:
    controller: Any

    @classmethod
    async def start(cls, *, headless: bool = False) -> "PlaywrightRuntime":
        from browser_agent.browser import BrowserController
        from browser_agent.config import Settings
        controller = BrowserController(settings=Settings(headless=headless))
        await controller.start()
        return cls(controller)

    async def navigate(self, url: str) -> None:
        await self.controller.navigate(url)

    async def observe(self):
        return await self.controller.observe_page()

    async def fill(self, instruction: str, value: str):
        """Observe, ground, and safely fill one non-sensitive field."""
        from browser_agent.actions import ActionExecutor
        from browser_agent.grounding import ElementGrounder
        from browser_agent.schemas import BrowserAction

        snapshot = await self.controller.observe_page()
        grounding = await ElementGrounder().find_element(instruction, snapshot, expected_element_type="text")
        if not grounding.success or not grounding.element_id:
            return {"success": False, "message": grounding.clarification_reason or "Could not identify a unique field.", "needs_clarification": True, "snapshot_id": str(snapshot.snapshot_id)}
        action = BrowserAction(action_id=f"fill-{snapshot.snapshot_id}", action_type="fill", element_id=grounding.element_id, snapshot_id=snapshot.snapshot_id, value=value)
        result = await ActionExecutor(save_screenshots=False).execute(action, grounding, snapshot, self.controller.session.page)
        return result.model_dump(mode="json")

    async def screenshot(self, path: str | Path):
        return await self.controller.capture_screenshot(path)

    async def close(self) -> None:
        await self.controller.close()
