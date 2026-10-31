"""Restricted file input support that enforces an explicit allowed directory."""

from pathlib import Path

from playwright.async_api import Locator


class FileUploader:
    """Upload existing files only from a configured directory tree."""

    def __init__(self, allowed_directory: str | Path | None) -> None:
        self.allowed_directory = Path(allowed_directory) if allowed_directory is not None else None

    def validate_path(self, file_path: str | Path) -> Path:
        """Resolve and validate a file, rejecting missing configuration and escapes."""
        if self.allowed_directory is None:
            raise ValueError("File uploads are disabled until an allowed upload directory is configured.")
        try:
            root = self.allowed_directory.expanduser().resolve(strict=True)
            target = Path(file_path).expanduser().resolve(strict=True)
        except OSError as exc:
            raise ValueError("The upload path or configured upload directory does not exist.") from exc
        if not root.is_dir():
            raise ValueError("The configured upload path is not a directory.")
        if not target.is_file():
            raise ValueError("The selected upload path is not a regular file.")
        try:
            target.relative_to(root)
        except ValueError as exc:
            raise ValueError("The selected file is outside the configured allowed upload directory.") from exc
        return target

    async def upload(self, locator: Locator, file_path: str | Path, timeout_ms: int | None = None) -> Path:
        """Set the validated file on a unique file input."""
        target = self.validate_path(file_path)
        await locator.set_input_files(str(target), timeout=timeout_ms)
        return target
