from dataclasses import dataclass
import os


@dataclass(frozen=True)
class AgentSettings:
    """Environment-backed agent configuration; secrets are never logged."""

    llm_provider: str | None
    llm_model: str | None
    llm_api_key: str | None
    llm_chat_completions_url: str | None
    ollama_base_url: str = "http://localhost:11434"
    ollama_chat_model: str = "nemotron-3-super:cloud"
    openai_api_key: str | None = None
    openai_model: str = ""
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-20b"
    llm_timeout_seconds: float = 120.0
    llm_temperature: float = 0.0
    openai_document_processing_enabled: bool = False

    @classmethod
    def from_environment(cls) -> "AgentSettings":
        def value(name: str) -> str | None:
            result = os.getenv(name, "").strip()
            return result or None

        provider = value("LLM_PROVIDER") or "ollama"
        return cls(
            llm_provider=provider,
            llm_model=value("LLM_MODEL"),
            llm_api_key=value("LLM_API_KEY"),
            llm_chat_completions_url=value("LLM_CHAT_COMPLETIONS_URL"),
            ollama_base_url=(value("OLLAMA_BASE_URL") or "http://localhost:11434").rstrip("/"),
            ollama_chat_model=value("OLLAMA_CHAT_MODEL") or "nemotron-3-super:cloud",
            openai_api_key=value("OPENAI_API_KEY") or value("LLM_API_KEY"),
            openai_model=value("OPENAI_MODEL") or value("LLM_MODEL") or "",
            groq_api_key=value("GROQ_API_KEY"),
            groq_model=value("GROQ_MODEL") or "openai/gpt-oss-20b",
            llm_timeout_seconds=float(value("LLM_TIMEOUT_SECONDS") or "120"),
            llm_temperature=float(value("LLM_TEMPERATURE") or "0"),
            openai_document_processing_enabled=(
                value("OPENAI_ALLOW_DOCUMENT_DATA") or "false"
            ).lower() in {"1", "true", "yes"},
        )

    @property
    def llm_enabled(self) -> bool:
        if self.llm_provider == "ollama":
            return bool(self.ollama_base_url and self.ollama_chat_model)
        if self.llm_provider == "openai":
            return bool((self.openai_api_key or self.llm_api_key) and (self.openai_model or self.llm_model))
        if self.llm_provider == "groq":
            return bool(self.groq_api_key and self.groq_model)
        return False

    @property
    def llm_configured(self) -> bool:
        return any(
            (
                self.llm_provider,
                self.llm_model,
                self.llm_api_key,
                self.llm_chat_completions_url,
                self.groq_api_key,
            )
        )

    @property
    def provider(self) -> str | None:
        return self.llm_provider
