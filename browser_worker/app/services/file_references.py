from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import uuid4


@dataclass(frozen=True)
class FilePayload:
    name: str
    mime_type: str
    buffer: bytes


class FileReferenceStore:
    """Short-lived, one-time file references; arbitrary local paths are never accepted."""

    def __init__(self, *, ttl_seconds: int = 120, max_bytes: int = 10_000_000) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._max_bytes = max_bytes
        self._files: dict[str, tuple[datetime, FilePayload]] = {}

    @property
    def max_bytes(self) -> int:
        return self._max_bytes

    def issue(self, payload: FilePayload) -> str:
        if not payload.buffer or len(payload.buffer) > self._max_bytes:
            raise ValueError("file payload is empty or exceeds the configured size limit")
        token = uuid4().hex
        self._files[token] = (datetime.now(UTC) + self._ttl, payload)
        return token

    def consume(self, token: str) -> FilePayload:
        self._purge_expired()
        entry = self._files.pop(token, None)
        if entry is None:
            raise KeyError("file reference is invalid, expired, or already used")
        return entry[1]

    def _purge_expired(self) -> None:
        now = datetime.now(UTC)
        expired = [token for token, (deadline, _) in self._files.items() if deadline <= now]
        for token in expired:
            self._files.pop(token, None)
