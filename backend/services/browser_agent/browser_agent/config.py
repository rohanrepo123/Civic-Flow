"""Environment-backed settings for the browser agent."""

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Validated runtime configuration, loaded from environment and .env."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    headless: bool = False
    browser_type: str = "chromium"
    browser_timeout: int = Field(default=30_000, gt=0)
    default_wait_until: str = "domcontentloaded"
    screenshot_dir: Path = Path("screenshots")
    upload_allowed_dir: Path | None = None

    @field_validator("browser_type")
    @classmethod
    def validate_browser_type(cls, value: str) -> str:
        if value.lower() != "chromium":
            raise ValueError("Only Chromium is supported in this phase.")
        return value.lower()

    @field_validator("default_wait_until")
    @classmethod
    def validate_wait_until(cls, value: str) -> str:
        if value not in {"commit", "domcontentloaded", "load", "networkidle"}:
            raise ValueError("DEFAULT_WAIT_UNTIL must be a supported Playwright load state.")
        return value


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
