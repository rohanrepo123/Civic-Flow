from dataclasses import dataclass, field
from datetime import UTC, datetime
import hashlib
from uuid import uuid4

from backend.app.agent.clients.browser_client import BrowserClientError
from backend.app.agent.schemas.browser import (
    Acknowledgement,
    BrowserActionRequest,
    BrowserActionResponse,
    BrowserObservation,
    BrowserSessionCreate,
    BrowserSessionResponse,
    ControlModeRequest,
    ControlModeResponse,
    ControlMode,
    ElementRole,
    ObservedElement,
    ObservedPage,
    PageState,
    UserInputEvent,
    UserInputType,
    Viewport,
)
from backend.app.agent.services.action_policy import ActionPolicy


@dataclass(frozen=True)
class MockElement:
    role: ElementRole
    label: str
    input_type: str | None = None
    placeholder: str | None = None
    visible: bool = True
    enabled: bool = True
    required: bool = False
    sensitive: bool = False
    target_url: str | None = None


@dataclass(frozen=True)
class MockPage:
    url: str
    title: str
    state: PageState = PageState.READY
    elements: tuple[MockElement, ...] = ()


@dataclass
class _MockSession:
    session_id: str
    task_id: str
    viewport: Viewport
    created_at: datetime
    page: MockPage
    mode: ControlMode = ControlMode.AGENT
    sequence: int = 0
    last_observation: BrowserObservation | None = None
    elements_by_id: dict[str, MockElement] = field(default_factory=dict)
    form_values: dict[str, str] = field(default_factory=dict, repr=False)
    history: list[MockPage] = field(default_factory=list)
    actions: dict[str, tuple[str, BrowserActionResponse]] = field(default_factory=dict)
    closed: bool = False


class MockBrowserClient:
    """Simulates browser session lifecycle and actions without Playwright."""

    def __init__(
        self,
        pages: dict[str, MockPage] | None = None,
        *,
        approved_domains: set[str] | None = None,
    ) -> None:
        self._pages = {self._url_key(url): page for url, page in (pages or {}).items()}
        self._policy = ActionPolicy(approved_domains)
        self._sessions: dict[str, _MockSession] = {}

    @staticmethod
    def _url_key(url: str) -> str:
        return url.rstrip("/").casefold()

    async def create_session(self, request: BrowserSessionCreate) -> BrowserSessionResponse:
        url = str(request.start_url)
        page = self._pages.get(self._url_key(url))
        if page is None:
            page = MockPage(url=url, title="Mock service portal")
        session_id = f"browser_{uuid4().hex}"
        session = _MockSession(
            session_id=session_id,
            task_id=request.task_id,
            viewport=request.viewport,
            created_at=datetime.now(UTC),
            page=page,
        )
        self._sessions[session_id] = session
        self._observe(session)
        return self._session_response(session)

    async def get_session(self, session_id: str) -> BrowserSessionResponse:
        return self._session_response(self._get_session(session_id))

    async def observe(self, session_id: str) -> BrowserObservation:
        return self._observe(self._get_session(session_id))

    async def execute_action(
        self,
        session_id: str,
        request: BrowserActionRequest,
    ) -> BrowserActionResponse:
        session = self._get_session(session_id)
        fingerprint = hashlib.sha256(request.model_dump_json().encode("utf-8")).hexdigest()
        previous = session.actions.get(request.action_id)
        if previous is not None:
            if previous[0] == fingerprint:
                return previous[1]
            return BrowserActionResponse(
                action_id=request.action_id,
                status="policy_blocked",
                message="An action ID cannot be reused for a different request.",
                before_observation_id=request.observation_id,
                after_observation_id=(session.last_observation.observation_id if session.last_observation else None),
                page_url=session.page.url,
            )

        if session.mode is not ControlMode.AGENT:
            return self._remember(
                session,
                fingerprint,
                self._result(session, request, "user_intervention_required", "Agent control is not active."),
            )

        observation = session.last_observation
        if observation is None or request.observation_id != observation.observation_id:
            return self._remember(
                session,
                fingerprint,
                self._result(
                    session,
                    request,
                    "stale_observation",
                    "The page changed. Request a fresh observation.",
                    after_observation_id=observation.observation_id if observation else None,
                ),
            )

        reason = self._policy.validate(request, observation)
        if reason is not None:
            if "target is not present" in reason:
                status = "target_not_found"
            else:
                status = "policy_blocked"
            return self._remember(session, fingerprint, self._result(session, request, status, reason))

        action = request.action
        element = session.elements_by_id.get(action.element_id or "")
        if action.type == "navigate" and action.url is not None:
            target_url = str(action.url)
            target_page = self._pages.get(self._url_key(target_url))
            session.history.append(session.page)
            session.page = target_page or MockPage(url=target_url, title="Mock page")
        elif action.type == "click" and element is not None and element.target_url:
            target_page = self._pages.get(self._url_key(element.target_url))
            if target_page is not None:
                session.history.append(session.page)
                session.page = target_page
        elif action.type in {"fill", "select_option"} and element is not None:
            session.form_values[element.label] = action.value or ""
        elif action.type == "go_back" and session.history:
            session.page = session.history.pop()
        elif action.type == "reload":
            pass

        after = self._observe(session)
        result = BrowserActionResponse(
            action_id=request.action_id,
            status="succeeded",
            message="Action executed by the mock browser.",
            before_observation_id=request.observation_id,
            after_observation_id=after.observation_id,
            page_url=session.page.url,
        )
        return self._remember(session, fingerprint, result)

    async def set_control_mode(
        self,
        session_id: str,
        mode: ControlModeRequest,
    ) -> ControlModeResponse:
        session = self._get_session(session_id)
        session.mode = mode.control_mode
        return ControlModeResponse(session_id=session_id, control_mode=session.mode)

    async def send_user_input(self, session_id: str, event: UserInputEvent) -> Acknowledgement:
        session = self._get_session(session_id)
        if session.mode is not ControlMode.USER:
            raise BrowserClientError(
                "Manual input is accepted only in user control mode",
                status_code=409,
                code="wrong_control_mode",
            )
        if event.type is UserInputType.TEXT_INPUT:
            # The mock acknowledges text input without retaining it in state or logs.
            return Acknowledgement(accepted=True)
        if event.type is UserInputType.POINTER_CLICK:
            session.page = MockPage(
                url=session.page.url,
                title=session.page.title,
                state=PageState.READY,
                elements=session.page.elements,
            )
        self._observe(session)
        return Acknowledgement(accepted=True)

    async def get_screenshot(self, session_id: str) -> bytes:
        self._get_session(session_id)
        return b"mock-browser-screenshot"

    async def close_session(self, session_id: str) -> None:
        session = self._get_session(session_id)
        session.closed = True
        session.page = MockPage(url=session.page.url, title=session.page.title, state=PageState.CLOSED)
        self._observe(session)

    def _get_session(self, session_id: str) -> _MockSession:
        session = self._sessions.get(session_id)
        if session is None:
            raise BrowserClientError("Browser session was not found", status_code=404, code="session_not_found")
        return session

    def _observe(self, session: _MockSession) -> BrowserObservation:
        session.sequence += 1
        observation_id = f"obs_{session.sequence:06d}"
        elements: list[ObservedElement] = []
        registry: dict[str, MockElement] = {}
        for index, source in enumerate(session.page.elements, start=1):
            element_id = f"el_{session.sequence:06d}_{index:03d}"
            registry[element_id] = source
            elements.append(
                ObservedElement(
                    element_id=element_id,
                    role=source.role,
                    label=source.label,
                    input_type=source.input_type,
                    placeholder=source.placeholder,
                    visible=source.visible,
                    enabled=source.enabled,
                    required=source.required,
                    sensitive=source.sensitive,
                )
            )
        session.elements_by_id = registry
        observation = BrowserObservation(
            session_id=session.session_id,
            observation_id=observation_id,
            sequence=session.sequence,
            page=ObservedPage(url=session.page.url, title=session.page.title, state=session.page.state),
            elements=elements,
            screenshot_url=f"/api/v1/sessions/{session.session_id}/screenshot",
        )
        session.last_observation = observation
        return observation

    @staticmethod
    def _session_response(session: _MockSession) -> BrowserSessionResponse:
        return BrowserSessionResponse(
            session_id=session.session_id,
            status="closed" if session.closed else "running",
            control_mode=session.mode,
            created_at=session.created_at,
            viewport=session.viewport,
        )

    @staticmethod
    def _result(
        session: _MockSession,
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
        session: _MockSession,
        fingerprint: str,
        result: BrowserActionResponse,
    ) -> BrowserActionResponse:
        session.actions[result.action_id] = (fingerprint, result)
        return result
