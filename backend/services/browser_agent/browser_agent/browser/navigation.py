"""Reusable asynchronous page navigation operations."""

from playwright.async_api import Error as PlaywrightError, Page, Response


class Navigation:
    """Navigation helpers for a Playwright page."""

    def __init__(self, page: Page, timeout: int = 30_000, wait_until: str = "domcontentloaded") -> None:
        self.page = page
        self.timeout = timeout
        self.wait_until = wait_until

    async def navigate_to_url(self, url: str) -> Response | None:
        """Navigate to URL and return the main-resource response, if any."""
        try:
            response = await self.page.goto(url, timeout=self.timeout, wait_until=self.wait_until)
            return response
        except PlaywrightError as exc:
            # Playwright errors can echo URLs containing query tokens or user data.
            raise RuntimeError(f"Could not navigate to the requested URL ({type(exc).__name__}).") from None

    async def get_current_url(self) -> str:
        """Return the current page URL."""
        return self.page.url

    async def get_page_title(self) -> str:
        """Return the current page title."""
        try:
            return await self.page.title()
        except PlaywrightError as exc:
            raise RuntimeError(f"Could not read the page title: {exc}") from exc

    async def go_back(self) -> Response | None:
        """Navigate to the previous history entry, when one exists."""
        try:
            return await self.page.go_back(timeout=self.timeout, wait_until=self.wait_until)
        except PlaywrightError as exc:
            raise RuntimeError(f"Could not navigate back: {exc}") from exc

    async def reload_page(self) -> Response | None:
        """Reload the current page."""
        try:
            return await self.page.reload(timeout=self.timeout, wait_until=self.wait_until)
        except PlaywrightError as exc:
            raise RuntimeError(f"Could not reload the page: {exc}") from exc
