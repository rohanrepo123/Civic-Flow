"""Post-action checks without returning private form contents."""

from typing import Any

from playwright.async_api import Error as PlaywrightError, Locator, Page

from browser_agent.actions.action_validator import is_sensitive_element
from browser_agent.observation.page_observer import PageObserver
from browser_agent.schemas.observation import InteractiveElement, PageSnapshot


class ActionVerifier:
    """Verify browser state changes after an executor operation."""

    async def verify_fill(self, locator: Locator, expected: str) -> bool:
        """Read the field internally and compare without returning its value."""
        return await locator.input_value() == expected

    async def verify_select(self, locator: Locator, expected_label: str) -> bool:
        """Confirm the selected option label matches the requested label."""
        selected = await locator.locator("option:checked").all_inner_texts()
        return len(selected) == 1 and selected[0].strip() == expected_label

    async def verify_checked(self, locator: Locator, expected: bool) -> bool:
        """Confirm the requested checkbox or radio state."""
        return await locator.is_checked() is expected

    async def verify_upload(self, locator: Locator, expected_path: str) -> bool:
        """Compare uploaded file metadata, never reading file contents."""
        expected_name = expected_path.replace("\\", "/").rsplit("/", 1)[-1]
        uploaded: list[dict[str, Any]] = await locator.evaluate(
            "el => Array.from(el.files || []).map(file => ({name: file.name, size: file.size}))"
        )
        return len(uploaded) == 1 and uploaded[0].get("name") == expected_name

    async def verify_scroll(self, locator: Locator) -> bool:
        """Confirm the target intersects the viewport after scrolling."""
        if not await locator.is_visible():
            return False
        return bool(await locator.evaluate(
            "el => { const r = el.getBoundingClientRect(); "
            "return r.bottom > 0 && r.right > 0 && r.top < innerHeight && r.left < innerWidth; }"
        ))

    async def verify_click(self, page: Page, before: PageSnapshot) -> tuple[bool, PageSnapshot | None]:
        """Verify a click through navigation or observable page-state change."""
        if page.is_closed():
            return False, None
        try:
            after = await PageObserver().observe(page)
        except (RuntimeError, PlaywrightError):
            return False, None
        return self.snapshot_signature(before) != self.snapshot_signature(after), after

    @staticmethod
    def snapshot_signature(snapshot: PageSnapshot) -> tuple[Any, ...]:
        """Build a comparison signature excluding timestamps and random IDs."""
        return (
            snapshot.url,
            snapshot.title,
            tuple(snapshot.headings),
            snapshot.page_text,
            tuple(
                (
                    element.element_id,
                    element.tag_name,
                    element.element_type,
                    element.role,
                    element.label,
                    element.text,
                    element.placeholder,
                    element.name,
                    element.id_attribute,
                    element.aria_label,
                    element.required,
                    element.disabled,
                    element.visible,
                    element.enabled,
                    element.input_type,
                    element.is_submit_control,
                    tuple(element.options),
                    element.checked,
                    element.selected_index,
                )
                for element in snapshot.interactive_elements
            ),
        )

    @staticmethod
    def safe_control_value(element: InteractiveElement, value: str | None) -> str | None:
        """Redact sensitive or personal field state before building results."""
        if is_sensitive_element(element):
            return None
        return value

    async def read_safe_value(self, locator: Locator, element: InteractiveElement) -> str | None:
        """Read only non-sensitive control state suitable for ActionResult."""
        if is_sensitive_element(element):
            return None
        try:
            if element.element_type in {"checkbox", "radio"}:
                return "checked" if await locator.is_checked() else "not checked"
        except PlaywrightError:
            return None
        return None
