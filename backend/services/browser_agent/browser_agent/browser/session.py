"""Internal representation of one active browser session."""

from dataclasses import dataclass
from typing import Any


@dataclass
class BrowserSession:
    """Holds live Playwright objects; this object is intentionally not serializable."""

    session_id: str
    browser: Any
    context: Any
    page: Any
    current_url: str = "about:blank"
    status: str = "active"
