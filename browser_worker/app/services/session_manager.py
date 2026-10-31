import asyncio
from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
import json
import re
import time
from typing import AsyncIterator
from urllib.parse import unquote, urljoin, urlparse
from uuid import uuid4

from playwright.async_api import (
    Browser,
    BrowserContext,
    Error as PlaywrightError,
    Locator,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
    async_playwright,
)
import httpx

from civicflow_contracts.browser import (
    BrowserActionRequest,
    BrowserActionResponse,
    BrowserObservation,
    BrowserSessionCreate,
    BrowserSessionResponse,
    ControlMode,
    ControlModeRequest,
    ControlModeResponse,
    ElementRole,
    ObservedElement,
    ObservedPage,
    PageState,
    UserInputEvent,
    UserInputType,
)
from browser_worker.app.config import BrowserWorkerSettings
from browser_worker.app.services.file_references import FilePayload, FileReferenceStore
from browser_worker.app.services.policy_guard import WorkerActionPolicy


class BrowserServiceError(RuntimeError):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code


@dataclass
class _Session:
    session_id: str
    task_id: str
    context: BrowserContext
    page: Page
    viewport_width: int
    viewport_height: int
    created_at: datetime
    last_active: float = field(default_factory=time.monotonic)
    sequence: int = 0
    mode: ControlMode = ControlMode.AGENT
    last_observation: BrowserObservation | None = None
    element_registry: dict[str, Locator] = field(default_factory=dict)
    actions: dict[str, tuple[str, BrowserActionResponse]] = field(default_factory=dict)
    closed: bool = False
    lock: asyncio.Lock = field(default_factory=asyncio.Lock, repr=False)


class BrowserSessionManager:
    _ELEMENT_SELECTOR = "a,button,input,textarea,select,option,[role=button],[role=link]"
    _SENSITIVE_LABEL = re.compile(r"\b(password|passcode|otp|one.time.code|verification code|captcha)\b", re.I)

    def __init__(
        self,
        settings: BrowserWorkerSettings,
        *,
        file_references: FileReferenceStore | None = None,
        executable_path: str | None = None,
        mock_pages: dict[str, str] | None = None,
    ) -> None:
        self.settings = settings
        self.file_references = file_references or FileReferenceStore()
        self._executable_path = executable_path
        self._mock_pages = {url.rstrip("/").casefold(): html for url, html in (mock_pages or {}).items()}
        self._playwright: Playwright | None = None
        self._browser: Browser | None = None
        self._sessions: dict[str, _Session] = {}
        self._policy = WorkerActionPolicy(set(settings.allowed_domains))
        self._cleanup_task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._browser is not None:
            return
        self._playwright = await async_playwright().start()
        launch_args = {"headless": True}
        if self._executable_path:
            launch_args["executable_path"] = self._executable_path
        self._browser = await self._playwright.chromium.launch(**launch_args)
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())

    async def stop(self) -> None:
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None
        for session_id in list(self._sessions):
            await self.close_session(session_id)
        if self._browser is not None:
            await self._browser.close()
            self._browser = None
        if self._playwright is not None:
            await self._playwright.stop()
            self._playwright = None

    async def create_session(self, request: BrowserSessionCreate) -> BrowserSessionResponse:
        await self._expire_sessions()
        if self._browser is None:
            raise BrowserServiceError("worker_not_ready", "Browser Worker is not ready", 503)
        self._validate_url(str(request.start_url))
        if len(self._sessions) >= self.settings.max_sessions:
            raise BrowserServiceError("session_limit", "Browser Worker session limit reached", 429)
        context = await self._browser.new_context(
            viewport={"width": request.viewport.width, "height": request.viewport.height},
            accept_downloads=False,
        )
        page = await context.new_page()
        page.set_default_timeout(10_000)
        await context.route("**/*", self._route_guard)
        try:
            await page.goto(str(request.start_url), wait_until="domcontentloaded")
        except PlaywrightError as exc:
            await context.close()
            raise BrowserServiceError("navigation_failed", "Unable to open the approved start page", 502) from exc
        session_id = f"browser_{uuid4().hex}"
        session = _Session(
            session_id=session_id,
            task_id=request.task_id,
            context=context,
            page=page,
            viewport_width=request.viewport.width,
            viewport_height=request.viewport.height,
            created_at=datetime.now(UTC),
        )
        self._sessions[session_id] = session
        await self._observe(session)
        return self._session_response(session)

    async def get_session(self, session_id: str) -> BrowserSessionResponse:
        session = await self._get_session(session_id)
        session.last_active = time.monotonic()
        return self._session_response(session)

    async def observe(self, session_id: str) -> BrowserObservation:
        session = await self._get_session(session_id)
        async with session.lock:
            session.last_active = time.monotonic()
            return await self._observe(session)

    async def execute_action(
        self,
        session_id: str,
        request: BrowserActionRequest,
    ) -> BrowserActionResponse:
        session = await self._get_session(session_id)
        async with session.lock:
            return await self._execute_action_locked(session, request)

    async def _execute_action_locked(
        self,
        session: _Session,
        request: BrowserActionRequest,
    ) -> BrowserActionResponse:
        session.last_active = time.monotonic()
        fingerprint = hashlib.sha256(request.model_dump_json().encode("utf-8")).hexdigest()
        previous = session.actions.get(request.action_id)
        if previous is not None:
            if previous[0] == fingerprint:
                return previous[1]
            return self._action_result(
                session,
                request,
                "policy_blocked",
                "An action ID cannot be reused for a different request.",
            )
        observation = session.last_observation
        if session.mode is not ControlMode.AGENT:
            result = self._action_result(
                session, request, "user_intervention_required", "Agent control is not active."
            )
            return self._remember(session, fingerprint, result)
        if observation is None or request.observation_id != observation.observation_id:
            result = self._action_result(
                session,
                request,
                "stale_observation",
                "The page changed. Request a fresh observation.",
                after_observation_id=observation.observation_id if observation else None,
            )
            return self._remember(session, fingerprint, result)
        reason = self._policy.validate(request, observation)
        if reason is not None:
            status = "target_not_found" if "target is not present" in reason else "policy_blocked"
            result = self._action_result(session, request, status, reason)
            return self._remember(session, fingerprint, result)

        try:
            await self._perform_action(session, request)
            status = "succeeded"
            message = "Action executed; request a fresh observation to verify the page state."
        except PlaywrightTimeoutError:
            status = "timed_out"
            message = "Browser action timed out; request a fresh observation before retrying."
        except (PlaywrightError, BrowserServiceError):
            status = "failed"
            message = "Browser action failed; request a fresh observation before retrying."
        after = await self._observe(session)
        result = BrowserActionResponse(
            action_id=request.action_id,
            status=status,
            message=message,
            before_observation_id=request.observation_id,
            after_observation_id=after.observation_id,
            page_url=session.page.url,
        )
        return self._remember(session, fingerprint, result)

    async def set_control_mode(
        self,
        session_id: str,
        request: ControlModeRequest,
    ) -> ControlModeResponse:
        session = await self._get_session(session_id)
        async with session.lock:
            session.mode = request.control_mode
            session.last_active = time.monotonic()
            return ControlModeResponse(session_id=session_id, control_mode=session.mode)

    async def send_user_input(self, session_id: str, event: UserInputEvent):
        session = await self._get_session(session_id)
        async with session.lock:
            if session.mode is not ControlMode.USER:
                raise BrowserServiceError("wrong_control_mode", "Session is not in user control mode", 409)
            session.last_active = time.monotonic()
            if event.type is UserInputType.POINTER_CLICK:
                await session.page.mouse.click(
                    event.x_normalized * session.viewport_width,
                    event.y_normalized * session.viewport_height,
                )
            elif event.type is UserInputType.KEY_PRESS:
                await session.page.keyboard.press(event.key)
            elif event.type is UserInputType.TEXT_INPUT:
                # Do not persist or log user-provided text.
                await session.page.keyboard.insert_text(event.text)
            elif event.type is UserInputType.SCROLL:
                await session.page.mouse.wheel(
                    (event.delta_x_normalized or 0) * session.viewport_width,
                    event.delta_y_normalized * session.viewport_height,
                )
            await self._observe(session)
            return {"accepted": True}

    async def get_screenshot(self, session_id: str) -> bytes:
        session = await self._get_session(session_id)
        async with session.lock:
            session.last_active = time.monotonic()
            return await session.page.screenshot(type="jpeg", quality=75)

    async def stream_screenshots(self, session_id: str) -> AsyncIterator[bytes]:
        while session_id in self._sessions:
            session = await self._get_session(session_id)
            async with session.lock:
                session.last_active = time.monotonic()
                frame = await session.page.screenshot(type="jpeg", quality=65)
            yield b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + frame + b"\r\n"
            await asyncio.sleep(self.settings.screenshot_interval_seconds)

    async def close_session(self, session_id: str) -> None:
        session = await self._get_session(session_id)
        async with session.lock:
            self._sessions.pop(session_id, None)
            session.closed = True
            await session.context.close()

    async def _perform_action(self, session: _Session, request: BrowserActionRequest) -> None:
        action = request.action
        locator = session.element_registry.get(action.element_id or "")
        if action.type == "navigate":
            if action.url is None:
                raise BrowserServiceError("invalid_action", "Navigation requires a URL", 422)
            self._validate_url(str(action.url))
            await session.page.goto(str(action.url), wait_until="domcontentloaded")
        elif action.type == "click":
            href = await locator.get_attribute("href")
            if href:
                target_url = urljoin(session.page.url, href)
                self._validate_url(target_url)
            await locator.click()
        elif action.type == "fill":
            await locator.fill(action.value)
        elif action.type == "select_option":
            await locator.select_option(action.value)
        elif action.type == "check":
            await locator.check()
        elif action.type == "uncheck":
            await locator.uncheck()
        elif action.type == "press_key":
            await locator.press(action.value)
        elif action.type == "scroll":
            amount = 600 if not action.value else int(action.value)
            await session.page.mouse.wheel(0, amount)
        elif action.type == "go_back":
            await session.page.go_back(wait_until="domcontentloaded")
        elif action.type == "reload":
            await session.page.reload(wait_until="domcontentloaded")
        elif action.type == "upload_file":
            if not action.file_reference:
                raise BrowserServiceError("invalid_file_reference", "File reference is required", 422)
            try:
                payload = self.file_references.consume(action.file_reference)
            except KeyError as exc:
                payload = await self._download_file_reference(action.file_reference)
            await locator.set_input_files(
                {"name": payload.name, "mimeType": payload.mime_type, "buffer": payload.buffer}
            )

    async def _download_file_reference(self, reference: str):
        parsed = urlparse(reference)
        host = (parsed.hostname or "").casefold().strip(".")
        allowed = any(
            host == domain or host.endswith(f".{domain}")
            for domain in self.settings.file_reference_domains
        )
        if parsed.scheme != "https" or not allowed:
            raise BrowserServiceError(
                "invalid_file_reference",
                "File reference is not an approved short-lived HTTPS URL",
                422,
            )
        try:
            async with httpx.AsyncClient(timeout=20, follow_redirects=False) as client:
                async with client.stream("GET", reference) as response:
                    response.raise_for_status()
                    length = int(response.headers.get("content-length", "0") or 0)
                    if length > self.file_references.max_bytes:
                        raise BrowserServiceError("file_too_large", "Uploaded file exceeds the size limit", 413)
                    buffer = bytearray()
                    async for part in response.aiter_bytes():
                        buffer.extend(part)
                        if len(buffer) > self.file_references.max_bytes:
                            raise BrowserServiceError("file_too_large", "Uploaded file exceeds the size limit", 413)
                    filename = "application-upload"
                    disposition = response.headers.get("content-disposition", "")
                    match = re.search(r"filename\*?=(?:UTF-8''|\")?([^;\"]+)", disposition, re.I)
                    if match:
                        filename = unquote(match.group(1).strip().strip("\"'"))
                        filename = filename.replace("/", "_").replace("\\", "_")[:180] or "application-upload"
                    media_type = response.headers.get("content-type", "application/octet-stream").split(";", 1)[0]
                    if not buffer:
                        raise BrowserServiceError("empty_file", "File reference returned an empty file", 422)
                    return FilePayload(name=filename, mime_type=media_type, buffer=bytes(buffer))
        except BrowserServiceError:
            raise
        except httpx.HTTPError as exc:
            raise BrowserServiceError(
                "file_reference_unavailable",
                "Approved file reference could not be retrieved",
                422,
            ) from exc

    async def _observe(self, session: _Session) -> BrowserObservation:
        session.sequence += 1
        observation_id = f"obs_{session.sequence:06d}"
        elements: list[ObservedElement] = []
        registry: dict[str, Locator] = {}
        locator_list = session.page.locator(self._ELEMENT_SELECTOR)
        count = min(await locator_list.count(), 300)
        for index in range(count):
            locator = locator_list.nth(index)
            try:
                values = await locator.evaluate(
                    """element => {
                        const tag = element.tagName.toLowerCase();
                        const type = tag === 'input' ? (element.getAttribute('type') || 'text').toLowerCase() : null;
                        const labels = element.labels ? Array.from(element.labels).map(label => label.innerText).join(' ') : '';
                        const label = element.getAttribute('aria-label') || labels || element.getAttribute('title') ||
                            element.getAttribute('placeholder') || (['a','button'].includes(tag) ? element.innerText : '') ||
                            element.getAttribute('name') || tag;
                        const role = element.getAttribute('role');
                        let mappedRole = 'other';
                        if (tag === 'a' || role === 'link') mappedRole = 'link';
                        else if (tag === 'button' || role === 'button') mappedRole = 'button';
                        else if (tag === 'select') mappedRole = 'combobox';
                        else if (tag === 'textarea' || (tag === 'input' && ['text','email','tel','number','password','search','date'].includes(type))) mappedRole = 'textbox';
                        else if (tag === 'input' && type === 'file') mappedRole = 'file_upload';
                        else if (tag === 'input' && type === 'checkbox') mappedRole = 'checkbox';
                        else if (tag === 'input' && type === 'radio') mappedRole = 'radio';
                        else if (tag === 'option') mappedRole = 'option';
                        const sensitive = type === 'password' || /password|passcode|otp|one.time.code|verification code|captcha/i.test(label);
                        return {role: mappedRole, label: String(label).trim().slice(0, 200), input_type: type,
                            placeholder: element.getAttribute('placeholder'), required: Boolean(element.required), sensitive};
                    }"""
                )
                visible = await locator.is_visible()
                enabled = await locator.is_enabled()
            except PlaywrightError:
                continue
            element_id = f"el_{session.sequence:06d}_{len(elements) + 1:03d}"
            try:
                role = ElementRole(values["role"])
                elements.append(
                    ObservedElement(
                        element_id=element_id,
                        role=role,
                        label=values["label"] or "Unlabeled control",
                        input_type=values["input_type"],
                        placeholder=values["placeholder"],
                        visible=visible,
                        enabled=enabled,
                        required=values["required"],
                        sensitive=values["sensitive"],
                    )
                )
                registry[element_id] = locator
            except (KeyError, ValueError):
                continue

        page_state = await self._page_state(session.page)
        observation = BrowserObservation(
            session_id=session.session_id,
            observation_id=observation_id,
            sequence=session.sequence,
            page=ObservedPage(url=session.page.url, title=await session.page.title(), state=page_state),
            elements=elements,
            screenshot_url=f"/api/v1/sessions/{session.session_id}/screenshot",
        )
        session.element_registry = registry
        session.last_observation = observation
        return observation

    async def _page_state(self, page: Page) -> PageState:
        if page.is_closed():
            return PageState.CLOSED
        try:
            ready_state = await page.evaluate("() => document.readyState")
            body_text = (await page.locator("body").inner_text(timeout=1000)).casefold()[:10000]
            has_captcha = await page.locator(
                "iframe[src*='captcha'], [class*='captcha' i], [id*='captcha' i]"
            ).count()
        except PlaywrightError:
            return PageState.LOADING
        if has_captcha or "captcha" in body_text:
            return PageState.CAPTCHA_DETECTED
        if page.url.casefold().find("login") >= 0 or "sign in to continue" in body_text:
            return PageState.AUTHENTICATION_REQUIRED
        if await page.locator("input[type=password]").count():
            return PageState.AUTHENTICATION_REQUIRED
        if "internal server error" in body_text or "service unavailable" in body_text:
            return PageState.UNEXPECTED_ERROR
        return PageState.READY if ready_state == "complete" else PageState.LOADING

    def _validate_url(self, url: str) -> None:
        parsed = urlparse(url)
        host = (parsed.hostname or "").casefold().strip(".")
        if parsed.scheme != "https":
            raise BrowserServiceError("navigation_blocked", "Only HTTPS destinations are allowed", 422)
        if not any(host == domain or host.endswith(f".{domain}") for domain in self.settings.allowed_domains):
            raise BrowserServiceError("navigation_blocked", "Destination is not allowlisted", 422)

    async def _route_guard(self, route, request) -> None:
        if request.is_navigation_request():
            parsed = urlparse(request.url)
            host = (parsed.hostname or "").casefold().strip(".")
            allowed = parsed.scheme == "https" and any(
                host == domain or host.endswith(f".{domain}")
                for domain in self.settings.allowed_domains
            )
            if not allowed:
                await route.abort("blockedbyclient")
                return
            mock_html = self._mock_pages.get(request.url.rstrip("/").casefold())
            if mock_html is not None:
                await route.fulfill(status=200, content_type="text/html; charset=utf-8", body=mock_html)
                return
        await route.continue_()

    async def _get_session(self, session_id: str) -> _Session:
        await self._expire_sessions()
        session = self._sessions.get(session_id)
        if session is None:
            raise BrowserServiceError("session_not_found", "Browser session was not found", 404)
        return session

    async def _expire_sessions(self) -> None:
        cutoff = time.monotonic() - self.settings.session_ttl_seconds
        expired = [key for key, session in self._sessions.items() if session.last_active < cutoff]
        for session_id in expired:
            session = self._sessions.pop(session_id)
            await session.context.close()

    async def _cleanup_loop(self) -> None:
        while True:
            await asyncio.sleep(min(30, self.settings.session_ttl_seconds / 4))
            await self._expire_sessions()

    @staticmethod
    def _session_response(session: _Session) -> BrowserSessionResponse:
        return BrowserSessionResponse(
            session_id=session.session_id,
            status="closed" if session.closed else "running",
            control_mode=session.mode,
            created_at=session.created_at,
            viewport={"width": session.viewport_width, "height": session.viewport_height},
        )

    @staticmethod
    def _action_result(
        session: _Session,
        request: BrowserActionRequest,
        status: str,
        message: str,
        *,
        after_observation_id: str | None = None,
    ) -> BrowserActionResponse:
        return BrowserActionResponse(
            action_id=request.action_id,
            status=status,
            message=message,
            before_observation_id=request.observation_id,
            after_observation_id=(
                after_observation_id
                if after_observation_id is not None
                else (session.last_observation.observation_id if session.last_observation else None)
            ),
            page_url=session.page.url,
        )

    @staticmethod
    def _remember(
        session: _Session,
        fingerprint: str,
        result: BrowserActionResponse,
    ) -> BrowserActionResponse:
        session.actions[result.action_id] = (fingerprint, result)
        return result
