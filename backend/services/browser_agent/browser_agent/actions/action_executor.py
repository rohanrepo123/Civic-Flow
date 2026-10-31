"""Freshness-checked, verified execution of grounded browser actions."""

from datetime import datetime, timezone
from pathlib import Path
import re
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from playwright.async_api import Error as PlaywrightError, Page
from playwright.async_api import TimeoutError as PlaywrightTimeoutError

from browser_agent.actions.action_validator import ActionValidator, is_sensitive_element
from browser_agent.actions.file_uploader import FileUploader
from browser_agent.actions.locator_resolver import LocatorResolutionError, LocatorResolver
from browser_agent.config import Settings, get_settings
from browser_agent.observation.page_observer import PageObserver
from browser_agent.schemas.action_result import ActionResult
from browser_agent.schemas.browser_action import BrowserAction
from browser_agent.schemas.grounding import GroundingResult
from browser_agent.schemas.observation import InteractiveElement, PageSnapshot


class ActionExecutor:
    """Execute one grounded action after validating freshness and safety."""

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        allowed_upload_dir: str | Path | None = None,
        screenshot_dir: str | Path | None = None,
        save_screenshots: bool = True,
        minimum_confidence: float = 0.78,
    ) -> None:
        from browser_agent.verification.action_verifier import ActionVerifier

        self.settings = settings or get_settings()
        upload_dir = allowed_upload_dir if allowed_upload_dir is not None else self.settings.upload_allowed_dir
        self.file_uploader = FileUploader(upload_dir)
        self.screenshot_dir = Path(screenshot_dir) if screenshot_dir is not None else self.settings.screenshot_dir
        self.save_screenshots = save_screenshots
        self.minimum_confidence = minimum_confidence
        self.validator = ActionValidator()
        self.locator_resolver = LocatorResolver()
        self.verifier = ActionVerifier()

    async def execute(
        self,
        action: BrowserAction,
        grounding_result: GroundingResult,
        snapshot: PageSnapshot,
        page: Page,
    ) -> ActionResult:
        """Validate, resolve, execute once, verify, and report an action."""
        source_element = self._validate_binding(action, grounding_result, snapshot)
        if isinstance(source_element, ActionResult):
            return await self._with_page_info(source_element, page)

        decision = self.validator.validate(action, source_element, snapshot.page_text)
        if not decision.allowed:
            result = self._failure(action, decision.reason or "Action was rejected.", human=decision.requires_human_intervention)
            return await self._with_page_info(result, page)

        try:
            latest = await PageObserver(timeout=min(self.settings.browser_timeout, 5_000)).observe(page)
        except Exception:
            result = self._failure(action, "Could not confirm the page snapshot is current.")
            return await self._with_page_info(result, page)
        if not self._snapshot_is_fresh(snapshot, latest):
            result = self._failure(action, "The page changed after observation; take a new snapshot and ground the element again.")
            return await self._with_page_info(result, page)

        fresh_elements = [item for item in latest.interactive_elements if item.element_id == action.element_id]
        if len(fresh_elements) != 1:
            result = self._failure(action, "The grounded element no longer exists uniquely in the current page.")
            return await self._with_page_info(result, page)
        element = fresh_elements[0]

        decision = self.validator.validate(action, element, latest.page_text)
        if not decision.allowed:
            result = self._failure(action, decision.reason or "Action was rejected.", human=decision.requires_human_intervention)
            return await self._with_page_info(result, page)

        try:
            locator = await self.locator_resolver.resolve(page, element, action.action_type)
        except LocatorResolutionError as exc:
            result = self._failure(action, str(exc), human="ambiguous" in str(exc).casefold())
            return await self._with_page_info(result, page)
        except PlaywrightError:
            result = self._failure(action, "Could not safely resolve the grounded element.")
            return await self._with_page_info(result, page)

        timeout = action.timeout_ms or self.settings.browser_timeout
        before_value = None
        if action.action_type in {"check", "uncheck", "radio_select"}:
            before_value = await self.verifier.read_safe_value(locator, element)
        attempted = False
        verified = False
        error: str | None = None
        message = "Action was executed but could not be verified."
        after_value: str | None = None
        value_present: bool | None = None
        value_matches: bool | None = None
        selected_option_matches: bool | None = None
        checked_state_matches: bool | None = None
        try:
            attempted = True
            if action.action_type == "fill":
                assert action.value is not None
                await locator.fill(action.value, timeout=timeout)
                verified = await self.verifier.verify_fill(locator, action.value)
                value_present = bool(await locator.input_value())
                value_matches = verified
                # Do not echo user-supplied fill contents in ActionResult.
                after_value = None
            elif action.action_type == "select":
                assert action.value is not None
                option_value, option_label = await self._resolve_option(locator, action.value)
                await locator.select_option(value=option_value, timeout=timeout)
                verified = await self.verifier.verify_select(locator, option_label)
                selected_option_matches = verified
            elif action.action_type in {"check", "uncheck"}:
                desired = action.action_type == "check"
                await locator.set_checked(desired, timeout=timeout)
                verified = await self.verifier.verify_checked(locator, desired)
                checked_state_matches = verified
                after_value = await self.verifier.read_safe_value(locator, element)
            elif action.action_type == "radio_select":
                if action.value is not None and not await self._radio_matches(locator, action.value):
                    raise ValueError("The requested radio option does not match the grounded element.")
                await locator.set_checked(True, timeout=timeout)
                verified = await self.verifier.verify_checked(locator, True)
                checked_state_matches = verified
                after_value = await self.verifier.read_safe_value(locator, element)
            elif action.action_type == "click":
                # A click is sent once only. A timeout is never retried because
                # navigation or a consequential state change may have occurred.
                await locator.click(timeout=timeout)
                verified, _ = await self.verifier.verify_click(page, latest)
            elif action.action_type == "upload":
                assert action.file_path is not None
                await self.file_uploader.upload(locator, action.file_path, timeout)
                verified = await self.verifier.verify_upload(locator, action.file_path)
            elif action.action_type == "scroll_into_view":
                await locator.scroll_into_view_if_needed(timeout=timeout)
                verified = await self.verifier.verify_scroll(locator)
            message = f"{action.action_type} action verified." if verified else "The action ran, but the expected state change could not be verified."
            if not verified:
                error = "Post-action verification failed."
        except ValueError as exc:
            error = str(exc)
            message = "Action was rejected or could not be completed."
        except PlaywrightTimeoutError:
            error = "The browser action timed out; it was not retried."
            message = "Action timed out; check the page before trying again."
        except PlaywrightError:
            error = "The browser could not complete the action."
            message = "Browser action failed."
        except Exception:
            error = "Unexpected action execution failure."
            message = "Browser action failed."

        screenshot_path = await self._capture_screenshot(page, action) if attempted else None
        if attempted and self.save_screenshots and screenshot_path is None and error is None:
            error = "Action was verified, but the screenshot could not be saved."
        if is_sensitive_element(element):
            before_value = None
            after_value = None
        # Filled values are always omitted, even for fields that appear benign.
        if action.action_type == "fill":
            before_value = None
            after_value = None
        final_url, final_title = await self._page_info(page)
        return ActionResult(
            success=verified,
            action_id=action.action_id,
            action_type=action.action_type,
            element_id=action.element_id,
            message=message,
            before_value=before_value,
            after_value=after_value,
            value_present=value_present,
            value_matches=value_matches,
            selected_option_matches=selected_option_matches,
            checked_state_matches=checked_state_matches,
            verified=verified,
            screenshot_path=screenshot_path,
            error=error,
            requires_human_intervention=False,
            page_url=final_url,
            page_title=final_title,
        )

    def _validate_binding(
        self,
        action: BrowserAction,
        grounding_result: GroundingResult,
        snapshot: PageSnapshot,
    ) -> InteractiveElement | ActionResult:
        """Ensure the action points to the selected element in its source snapshot."""
        snapshot_id = str(snapshot.snapshot_id)
        if str(action.snapshot_id) != snapshot_id or grounding_result.snapshot_id != snapshot_id:
            return self._failure(action, "The action or grounding result belongs to a stale snapshot.")
        if not grounding_result.success or grounding_result.needs_clarification or grounding_result.selected_element is None:
            return self._failure(action, "Grounding did not produce a safe, unambiguous target.", human=grounding_result.needs_clarification)
        if grounding_result.confidence < self.minimum_confidence:
            return self._failure(action, "Grounding confidence is below the action threshold.", human=True)
        if grounding_result.element_id != action.element_id or grounding_result.selected_element.element_id != action.element_id:
            return self._failure(action, "The action element does not match the grounded element.")
        elements = [element for element in snapshot.interactive_elements if element.element_id == action.element_id]
        if len(elements) != 1:
            return self._failure(action, "The grounded element is missing or duplicated in its snapshot.")
        expected = elements[0].model_dump(exclude={"current_value"})
        selected = grounding_result.selected_element.model_dump(exclude={"current_value"})
        if selected != expected:
            return self._failure(action, "The grounding descriptor does not match the supplied snapshot.")
        return elements[0]

    def _snapshot_is_fresh(self, previous: PageSnapshot, latest: PageSnapshot) -> bool:
        """Compare observed structure rather than treating random snapshot IDs as permanent."""
        return self.verifier.snapshot_signature(previous) == self.verifier.snapshot_signature(latest)

    async def _resolve_option(self, locator, requested: str) -> tuple[str, str]:
        """Resolve an exact option label or value before selecting it once."""
        options = await locator.locator("option").evaluate_all(
            "items => items.map(option => ({value: option.value, label: (option.label || option.textContent || '').trim()}))"
        )
        exact_labels = [item for item in options if item["label"].casefold() == requested.casefold()]
        matches = exact_labels or [item for item in options if item["value"] == requested]
        if len(matches) != 1:
            raise ValueError("The requested dropdown option is missing or ambiguous.")
        return matches[0]["value"], matches[0]["label"]

    @staticmethod
    async def _radio_matches(locator, requested: str) -> bool:
        """Ensure an optional requested option agrees with the grounded radio."""
        metadata = await locator.evaluate(
            "el => ({value: el.value || '', aria: el.getAttribute('aria-label') || '', "
            "labels: el.labels ? Array.from(el.labels).map(label => (label.innerText || '').trim()) : []})"
        )
        candidates = [metadata["value"], metadata["aria"], *metadata["labels"]]
        return any(
            value and (
                value.casefold() == requested.casefold()
                or re.search(rf"\b{re.escape(requested)}\b", value, re.IGNORECASE) is not None
            )
            for value in candidates
        )

    async def _capture_screenshot(self, page: Page, action: BrowserAction) -> str | None:
        """Capture an action screenshot using a unique, sanitized filename."""
        if not self.save_screenshots or page.is_closed():
            return None
        try:
            self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        except OSError:
            return None
        safe_action_id = re.sub(r"[^A-Za-z0-9_-]+", "_", action.action_id)[:60] or "action"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        target = self.screenshot_dir / f"{stamp}_{safe_action_id}_{uuid4().hex[:8]}.png"
        try:
            await page.screenshot(path=str(target), full_page=True)
        except (PlaywrightError, OSError):
            return None
        return str(target)

    @staticmethod
    def _failure(action: BrowserAction, error: str, human: bool = False) -> ActionResult:
        return ActionResult(
            success=False,
            action_id=action.action_id,
            action_type=action.action_type,
            element_id=action.element_id,
            message=error,
            verified=False,
            error=error,
            requires_human_intervention=human,
        )

    async def _with_page_info(self, result: ActionResult, page: Page) -> ActionResult:
        result.page_url, result.page_title = await self._page_info(page)
        return result

    @staticmethod
    async def _page_info(page: Page) -> tuple[str, str]:
        """Return page metadata with query strings and fragments removed."""
        try:
            parts = urlsplit(page.url)
            if parts.scheme == "file":
                safe_url = "file://[local]"
            else:
                host = parts.hostname or ""
                if ":" in host and not host.startswith("["):
                    host = f"[{host}]"
                try:
                    if parts.port:
                        host = f"{host}:{parts.port}"
                except ValueError:
                    pass
                path_segments = parts.path.split("/")
                safe_segments = [
                    "[redacted]" if len(segment) >= 40 or segment.count(".") == 2 else segment
                    for segment in path_segments
                ]
                safe_path = "/".join(safe_segments)
                safe_url = urlunsplit((parts.scheme, host, safe_path, "", ""))
        except Exception:
            safe_url = ""
        try:
            title = await page.title() if not page.is_closed() else ""
        except PlaywrightError:
            title = ""
        return safe_url, title
