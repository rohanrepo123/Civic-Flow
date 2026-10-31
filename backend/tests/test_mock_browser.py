import asyncio

import pytest
from pydantic import ValidationError

from backend.app.agent.clients.browser_client import BrowserClientError, GuardedBrowserClient
from backend.app.agent.mocks.mock_browser import MockBrowserClient, MockElement, MockPage
from backend.app.agent.schemas.browser import (
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
from backend.app.agent.services.action_policy import ActionPolicy


PORTAL = "https://portal.example.gov.in"


def make_client() -> MockBrowserClient:
    pages = {
        PORTAL: MockPage(
            url=PORTAL,
            title="Example portal",
            elements=(
                MockElement(role=ElementRole.LINK, label="New Application", target_url=f"{PORTAL}/apply"),
                MockElement(role=ElementRole.TEXTBOX, label="Applicant Name", required=True),
                MockElement(
                    role=ElementRole.TEXTBOX,
                    label="One-time password",
                    input_type="password",
                    sensitive=True,
                ),
                MockElement(role=ElementRole.BUTTON, label="Submit Application"),
                MockElement(role=ElementRole.BUTTON, label="Sign in"),
            ),
        ),
        f"{PORTAL}/apply": MockPage(
            url=f"{PORTAL}/apply",
            title="Application form",
            elements=(MockElement(role=ElementRole.TEXTBOX, label="Applicant Name"),),
        ),
    }
    return MockBrowserClient(pages, approved_domains={"portal.example.gov.in"})


async def open_session(client: MockBrowserClient, start_url: str = PORTAL) -> tuple[str, object]:
    session = await client.create_session(
        BrowserSessionCreate(
            task_id="task-1",
            start_url=start_url,
            viewport=Viewport(width=1280, height=800),
        )
    )
    return session.session_id, await client.observe(session.session_id)


def action_request(observation, action: BrowserAction, action_id: str = "action-1") -> BrowserActionRequest:
    return BrowserActionRequest(
        action_id=action_id,
        observation_id=observation.observation_id,
        action=action,
        expected_result="The requested safe interaction is reflected in the next observation",
    )


def test_mock_browser_fills_form_and_action_retries_are_idempotent() -> None:
    async def run() -> None:
        client = make_client()
        session_id, observation = await open_session(client)
        field = next(item for item in observation.elements if item.label == "Applicant Name")
        request = action_request(
            observation,
            BrowserAction(type="fill", element_id=field.element_id, value="Example Citizen"),
        )
        first = await client.execute_action(session_id, request)
        retry = await client.execute_action(session_id, request)
        assert first.status == "succeeded"
        assert retry == first
        assert first.after_observation_id != first.before_observation_id
        assert "Example Citizen" not in first.message

    asyncio.run(run())

def test_mock_browser_click_changes_page_and_observation_ids_expire() -> None:
    async def run() -> None:
        client = make_client()
        session_id, old_observation = await open_session(client)
        link = next(item for item in old_observation.elements if item.label == "New Application")
        request = action_request(old_observation, BrowserAction(type="click", element_id=link.element_id))
        result = await client.execute_action(session_id, request)
        assert result.status == "succeeded"
        fresh = await client.observe(session_id)
        assert fresh.page.url == f"{PORTAL}/apply"
        assert fresh.observation_id != old_observation.observation_id
        stale = await client.execute_action(session_id, request.model_copy(update={"action_id": "retry-stale"}))
        assert stale.status == "stale_observation"
        assert stale.after_observation_id == fresh.observation_id

    asyncio.run(run())


@pytest.mark.parametrize("label", ["One-time password", "Submit Application", "Sign in"])
def test_mock_browser_blocks_sensitive_or_consequential_actions(label: str) -> None:
    async def run() -> None:
        client = make_client()
        session_id, observation = await open_session(client)
        element = next(item for item in observation.elements if item.label == label)
        action_type = "fill" if label == "One-time password" else "click"
        kwargs = {"element_id": element.element_id}
        if action_type == "fill":
            kwargs["value"] = "secret-value"
        request = action_request(observation, BrowserAction(type=action_type, **kwargs))
        result = await client.execute_action(session_id, request)
        assert result.status == "policy_blocked"
        assert "secret-value" not in result.message

    asyncio.run(run())


def test_mock_browser_rejects_disallowed_navigation_and_reused_action_id() -> None:
    async def run() -> None:
        client = make_client()
        session_id, observation = await open_session(client)
        navigation = action_request(
            observation,
            BrowserAction(type="navigate", url="https://untrusted.example/path"),
            "nav-1",
        )
        blocked = await client.execute_action(session_id, navigation)
        assert blocked.status == "policy_blocked"

        field = next(item for item in observation.elements if item.label == "Applicant Name")
        first = action_request(
            observation,
            BrowserAction(type="fill", element_id=field.element_id, value="one"),
            "same-id",
        )
        await client.execute_action(session_id, first)
        second = action_request(
            observation,
            BrowserAction(type="fill", element_id=field.element_id, value="two"),
            "same-id",
        )
        conflict = await client.execute_action(session_id, second)
        assert conflict.status == "policy_blocked"

    asyncio.run(run())


def test_manual_control_mode_and_text_input_are_not_retained() -> None:
    async def run() -> None:
        client = make_client()
        session_id, observation = await open_session(client)
        button = next(item for item in observation.elements if item.label == "New Application")
        request = action_request(observation, BrowserAction(type="click", element_id=button.element_id))
        with pytest.raises(BrowserClientError):
            await client.send_user_input(
                session_id,
                UserInputEvent(event_id="input-0", type=UserInputType.TEXT_INPUT, text="private text"),
            )
        await client.set_control_mode(session_id, ControlModeRequest(control_mode=ControlMode.USER))
        blocked = await client.execute_action(session_id, request)
        assert blocked.status == "user_intervention_required"

        accepted = await client.send_user_input(
            session_id,
            UserInputEvent(event_id="input-1", type=UserInputType.TEXT_INPUT, text="private text"),
        )
        assert accepted.accepted
        session = await client.get_session(session_id)
        assert session.control_mode is ControlMode.USER

    asyncio.run(run())


def test_session_isolation_cleanup_and_shared_action_validation() -> None:
    async def run() -> None:
        client = make_client()
        session_a, observation_a = await open_session(client)
        session_b, observation_b = await open_session(client)
        assert session_a != session_b
        assert observation_a.session_id != observation_b.session_id
        await client.close_session(session_a)
        assert (await client.get_session(session_a)).status == "closed"
        assert (await client.get_session(session_b)).status == "running"

    asyncio.run(run())
    with pytest.raises(ValidationError):
        BrowserAction(type="navigate")


def test_guarded_client_rejects_sensitive_action_before_worker_call() -> None:
    async def run() -> None:
        worker = make_client()
        client = GuardedBrowserClient(worker, ActionPolicy({"portal.example.gov.in"}))
        session = await client.create_session(
            BrowserSessionCreate(
                task_id="task-1",
                start_url=PORTAL,
                viewport=Viewport(width=1280, height=800),
            )
        )
        observation = await client.observe(session.session_id)
        element = next(item for item in observation.elements if item.label == "One-time password")
        request = action_request(
            observation,
            BrowserAction(type="fill", element_id=element.element_id, value="private"),
        )
        result = await client.execute_action(session.session_id, request)
        assert result.status == "policy_blocked"
        assert "private" not in result.message

    asyncio.run(run())

\n