"""Small DOM based accessibility fallbacks independent of Playwright versions."""

from typing import Any


_IMPLICIT_ROLES = {
    "a": "link",
    "button": "button",
    "select": "combobox",
    "textarea": "textbox",
    "summary": "button",
}


def accessible_role(element: dict[str, Any]) -> str | None:
    """Return an explicit or common implicit ARIA role for an element."""
    explicit = element.get("role")
    if explicit:
        return str(explicit).split()[0]
    tag = str(element.get("tag_name", "")).lower()
    input_type = str(element.get("input_type", "text")).lower()
    if tag == "input":
        return {
            "button": "button", "submit": "button", "reset": "button", "image": "button",
            "checkbox": "checkbox", "radio": "radio", "range": "slider",
            "number": "spinbutton", "search": "searchbox",
        }.get(input_type, "textbox")
    return _IMPLICIT_ROLES.get(tag)


def accessible_label(element: dict[str, Any]) -> str | None:
    """Choose the best available accessible-name fallback for a DOM element."""
    # ARIA naming attributes override the native label in the accessible name.
    for key in ("aria_label", "label", "text", "placeholder", "title", "name"):
        value = element.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None
