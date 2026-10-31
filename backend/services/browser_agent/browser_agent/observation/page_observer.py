"""Public API for taking structured, privacy-aware page snapshots."""

from datetime import datetime, timezone
from uuid import uuid4

from playwright.async_api import Error as PlaywrightError, Page

from browser_agent.observation.dom_parser import DOMParser
from browser_agent.schemas.observation import PageSnapshot


class PageObserver:
    """Observe a loaded Playwright page without interacting with its controls."""

    def __init__(self, timeout: int = 5_000) -> None:
        self.timeout = timeout
        self.parser = DOMParser()

    async def observe(self, page: Page) -> PageSnapshot:
        """Return a structured snapshot of the current rendered page.

        A DOM-content-loaded wait is attempted first, but a timeout is tolerated
        so observation can still work for long-running or client-rendered pages.
        """
        if page.is_closed():
            raise RuntimeError("Cannot observe a closed Playwright page.")
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=self.timeout)
        except PlaywrightError:
            # The current DOM may still be usable when a load state times out.
            pass
        last_error: PlaywrightError | None = None
        for _ in range(2):
            try:
                raw = await self.parser.parse(page)
                break
            except PlaywrightError as exc:
                last_error = exc
                if page.is_closed():
                    break
        else:
            assert last_error is not None
            raise RuntimeError(f"Could not observe the current page: {last_error}") from last_error
        if page.is_closed():
            raise RuntimeError("The page closed while it was being observed.")
        return PageSnapshot(
            url=raw.get("url", page.url),
            title=raw.get("title", ""),
            headings=raw.get("headings", []),
            page_text=raw.get("page_text", ""),
            interactive_elements=self.parser.parse_elements(raw.get("controls", [])),
            observed_at=datetime.now(timezone.utc),
            snapshot_id=uuid4(),
        )
