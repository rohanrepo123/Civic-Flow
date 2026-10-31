"""Core API configuration — loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """All configurable values for the Core API."""

    APP_VERSION: str = "0.1.0"

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://civicflow:civicflow@localhost:5432/civicflow"

    # --- Redis ---
    REDIS_URL: str = "redis://localhost:6379/0"

    # --- Object Storage (MinIO / S3) ---
    OBJECT_STORAGE_URL: str = "http://localhost:9000"
    OBJECT_STORAGE_ACCESS_KEY: str = "minioadmin"
    OBJECT_STORAGE_SECRET_KEY: str = "minioadmin"
    OBJECT_STORAGE_BUCKET: str = "civicflow-documents"

    # --- JWT Auth ---
    JWT_SECRET_KEY: str = "CHANGE-ME-in-production-use-a-real-secret"
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_MINUTES: int = 10080  # 7 days

    # --- Downstream Service URLs ---
    AI_AGENT_URL: str = "http://localhost:8001"
    BROWSER_AGENT_URL: str = "http://localhost:8002"
    BROWSER_AGENT_API_TOKEN: str = ""

    # --- CORS ---
    CORS_ORIGINS: list[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # --- Service Communication ---
    SERVICE_REQUEST_TIMEOUT: int = 30  # seconds
    SERVICE_RETRY_MAX: int = 3

    # --- Mock Mode ---
    USE_MOCK_AI: bool = True
    USE_MOCK_BROWSER: bool = True
    ENFORCE_AUTH: bool = False
    LOCAL_DEMO_MODE: bool = False

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8", "extra": "ignore"}


settings = Settings()
