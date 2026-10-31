"""Asynchronous Playwright browser lifecycle management."""

import asyncio
from pathlib import Path
from uuid import uuid4

from playwright.async_api import Browser, BrowserContext, Error as PlaywrightError, Page, async_playwright

from browser_agent.browser.navigation import Navigation
from browser_agent.browser.session import BrowserSession
from browser_agent.config import Settings, get_settings
from browser_agent.observation.page_observer import PageObserver
from browser_agent.schemas.observation import PageSnapshot


class BrowserController:
    """Owns one Playwright browser session and closes resources safely."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()
        self._playwright = None
        self.session: BrowserSession | None = None
        self.navigation: Navigation | None = None

    async def start(self) -> BrowserSession:
        """Start Playwright and create a browser context and page."""
        if self.session and self.session.status == "active":
            if self.session.browser.is_connected() and not self.session.page.is_closed():
                return self.session
            await self.close()
        browser: Browser | None = None
        context: BrowserContext | None = None
        playwright_manager = async_playwright()
        startup_timeout = self.settings.browser_timeout / 1000
        cleanup_timeout = max(1.0, min(startup_timeout, 30.0))
        try:
            self._playwright = await asyncio.wait_for(playwright_manager.start(), timeout=startup_timeout)
            browser = await self._playwright.chromium.launch(
                headless=self.settings.headless,
                timeout=self.settings.browser_timeout,
            )
            context = await asyncio.wait_for(browser.new_context(), timeout=startup_timeout)
            page: Page = await asyncio.wait_for(context.new_page(), timeout=startup_timeout)
            page.set_default_timeout(self.settings.browser_timeout)
            session = BrowserSession(str(uuid4()), browser, context, page, current_url=page.url)
            self.session = session
            page.on(
                "framenavigated",
                lambda frame: setattr(session, "current_url", frame.url) if frame == page.main_frame else None,
            )
            self.navigation = Navigation(page, self.settings.browser_timeout, self.settings.default_wait_until)
            return session
        except Exception as exc:
            if context is not None:
                try:
                    await asyncio.wait_for(context.close(), timeout=cleanup_timeout)
                except Exception:
                    pass
            if browser is not None:
                try:
                    await asyncio.wait_for(browser.close(), timeout=cleanup_timeout)
                except Exception:
                    pass
            if self._playwright is not None:
                try:
                    await asyncio.wait_for(self._playwright.stop(), timeout=cleanup_timeout)
                except Exception:
                    pass
                finally:
                    self._playwright = None
            else:
                # The manager owns the driver connection even if its startup
                # handshake timed out before returning an AsyncPlaywright.
                try:
                    await asyncio.wait_for(playwright_manager.__aexit__(None, None, None), timeout=cleanup_timeout)
                except Exception:
                    pass
            raise RuntimeError(f"Could not start Chromium browser: {exc}") from exc

    async def navigate(self, url: str) -> None:
        """Navigate the active session and update its URL."""
        self._require_session()
        assert self.navigation is not None and self.session is not None
        await self.navigation.navigate_to_url(url)
        self.session.current_url = self.session.page.url

    async def get_page_title(self) -> str:
        """Read the active page title."""
        self._require_session()
        assert self.navigation is not None
        return await self.navigation.get_page_title()

    async def get_current_url(self) -> str:
        """Read the active page URL."""
        self._require_session()
        assert self.navigation is not None
        return await self.navigation.get_current_url()

    async def go_back(self) -> None:
        """Navigate to the previous page in browser history, if one exists."""
        self._require_session()
        assert self.navigation is not None
        await self.navigation.go_back()

    async def reload_page(self) -> None:
        """Reload the current page using the configured navigation timeout."""
        self._require_session()
        assert self.navigation is not None
        await self.navigation.reload_page()

    async def observe_page(self) -> PageSnapshot:
        """Return a structured observation of the active page."""
        self._require_session()
        assert self.session is not None
        return await PageObserver(timeout=self.settings.browser_timeout).observe(self.session.page)

    async def capture_screenshot(self, path: str | Path) -> Path:
        """Save a screenshot of the active page and return its path."""
        self._require_session()
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        try:
            await self.session.page.screenshot(path=str(target), full_page=True)
        except PlaywrightError as exc:
            raise RuntimeError(f"Could not capture screenshot at {target}: {exc}") from exc
        return target

    def _require_session(self) -> None:
        if not self.session or self.session.status != "active":
            raise RuntimeError("Browser is not running. Call start() first.")
        if not self.session.browser.is_connected() or self.session.page.is_closed():
            self.session.status = "closed"
            raise RuntimeError("The browser session is no longer active; start a new session.")

    async def close(self) -> None:
        """Close context, browser, and Playwright even if cleanup partially fails."""
        session = self.session
        self.session = None
        self.navigation = None
        cleanup_timeout = max(1.0, min(self.settings.browser_timeout / 1000, 30.0))
        if session:
            session.status = "closed"
            try:
                await asyncio.wait_for(session.context.close(), timeout=cleanup_timeout)
            except Exception:
                pass
            try:
                await asyncio.wait_for(session.browser.close(), timeout=cleanup_timeout)
            except Exception:
                pass
        if self._playwright:
            try:
                await asyncio.wait_for(self._playwright.stop(), timeout=cleanup_timeout)
            except Exception:
                pass
            finally:
                self._playwright = None

    async def __aenter__(self) -> "BrowserController":
        await self.start()
        return self

    async def __aexit__(self, exc_type: object, exc: object, traceback: object) -> None:
        await self.close()
