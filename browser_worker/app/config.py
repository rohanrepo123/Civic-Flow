from dataclasses import dataclass
import os


@dataclass(frozen=True)
class BrowserWorkerSettings:
    api_token: str | None
    allowed_domains: frozenset[str]
    file_reference_domains: frozenset[str] = frozenset()
    session_ttl_seconds: int = 1800
    max_sessions: int = 10
    screenshot_interval_seconds: float = 0.5

    @classmethod
    def from_environment(cls) -> "BrowserWorkerSettings":
        token = os.getenv("BROWSER_WORKER_API_TOKEN", "").strip() or None
        domains = frozenset(
            item.strip().casefold().strip(".")
            for item in os.getenv("BROWSER_ALLOWED_DOMAINS", "").split(",")
            if item.strip()
        )
        file_domains = frozenset(
            item.strip().casefold().strip(".")
            for item in os.getenv("BROWSER_FILE_REFERENCE_DOMAINS", "").split(",")
            if item.strip()
        )
        ttl_value = os.getenv("BROWSER_SESSION_TTL_SECONDS", "1800").strip()
        try:
            ttl = int(ttl_value)
        except ValueError as exc:
            raise ValueError("BROWSER_SESSION_TTL_SECONDS must be an integer") from exc
        if ttl <= 0:
            raise ValueError("BROWSER_SESSION_TTL_SECONDS must be positive")
        return cls(
            api_token=token,
            allowed_domains=domains,
            file_reference_domains=file_domains,
            session_ttl_seconds=ttl,
        )
