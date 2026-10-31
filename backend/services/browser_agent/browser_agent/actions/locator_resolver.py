"""Resolve grounded snapshot descriptors to unique semantic Playwright locators."""

import re

from playwright.async_api import Error as PlaywrightError, Locator, Page

from browser_agent.schemas.browser_action import ActionType
from browser_agent.schemas.observation import InteractiveElement


class LocatorResolutionError(RuntimeError):
    """A grounded element could not be resolved uniquely and safely."""


def _css_string(value: str) -> str:
    """Escape a string for a quoted CSS attribute selector."""
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\a ")


class LocatorResolver:
    """Prefer accessible locators and use exact attributes only as fallback."""

    async def resolve(
        self,
        page: Page,
        element: InteractiveElement,
        action_type: ActionType,
    ) -> Locator:
        """Return one fresh locator matching the supplied snapshot descriptor."""
        require_enabled = action_type not in {"scroll_into_view"}
        tag_name = element.tag_name.lower()
        if not re.fullmatch(r"[a-z][a-z0-9-]*", tag_name):
            raise LocatorResolutionError("The grounded element has an invalid tag descriptor.")
        accessible_name = element.label or element.aria_label or element.text
        candidates: list[Locator] = []

        # Radio controls should use Playwright's semantic role locator first;
        # get_by_label can match a surrounding label and duplicate it through
        # nested text in some markup patterns.
        if element.element_type == "radio" and element.role and accessible_name:
            try:
                candidates.append(page.get_by_role("radio", name=accessible_name, exact=True))
            except (PlaywrightError, ValueError):
                pass
        if element.label:
            candidates.append(page.get_by_label(element.label, exact=True))
        if element.role and accessible_name and element.element_type != "radio":
            try:
                candidates.append(page.get_by_role(element.role, name=accessible_name, exact=True))
            except (PlaywrightError, ValueError):
                pass
        if element.placeholder:
            candidates.append(page.get_by_placeholder(element.placeholder, exact=True))
        if element.aria_label:
            candidates.append(page.locator(f'[aria-label="{_css_string(element.aria_label)}"]'))
        if element.name:
            selector = f'{tag_name}[name="{_css_string(element.name)}"]'
            if element.input_type:
                selector += f'[type="{_css_string(element.input_type)}"]'
            candidates.append(page.locator(selector))
        if element.id_attribute:
            candidates.append(page.locator(f'[id="{_css_string(element.id_attribute)}"]'))
        if element.text and element.element_type in {"button", "link"}:
            candidates.append(page.get_by_text(element.text, exact=True))

        saw_ambiguous = False
        for locator in candidates:
            try:
                count = await locator.count()
                if count == 0:
                    continue
                if count != 1:
                    saw_ambiguous = True
                    continue
                if not await self._matches_descriptor(locator, element):
                    continue
                if action_type != "scroll_into_view" and not await locator.is_visible():
                    continue
                if require_enabled and not await locator.is_enabled():
                    raise LocatorResolutionError("The grounded element is disabled.")
                return locator
            except LocatorResolutionError:
                raise
            except PlaywrightError:
                continue

        qualifier = "ambiguous" if saw_ambiguous else "not found"
        raise LocatorResolutionError(f"The grounded element is {qualifier} in the current page.")

    @staticmethod
    async def _matches_descriptor(locator: Locator, expected: InteractiveElement) -> bool:
        """Guard against a semantic locator resolving to a different control."""
        try:
            actual = await locator.evaluate(
                "el => ({tag: el.tagName.toLowerCase(), name: el.getAttribute('name'), "
                "id: el.getAttribute('id'), type: el.tagName.toLowerCase()==='input' ? "
                "(el.getAttribute('type') || 'text').toLowerCase() : null})"
            )
        except PlaywrightError:
            return False
        if actual["tag"] != expected.tag_name.lower():
            return False
        for key, value in (("name", expected.name), ("id", expected.id_attribute), ("type", expected.input_type)):
            if value is not None and actual.get(key) != value:
                return False
        return True
