import json
import json.decoder
from typing import Any, Protocol

import httpx

from backend.app.agent.config import AgentSettings
from backend.app.agent.schemas.intent import Intent


class IntentExtractor(Protocol):
    async def extract(self, user_request: str, *, context: dict[str, Any] | None = None) -> Intent: ...


class StructuredChatClient(Protocol):
    async def complete_json(self, *, system_prompt: str, user_prompt: str) -> str: ...


def final_json_object(content: str) -> str:
    """Return the last valid top-level JSON object in model output, dropping any preamble."""
    decoder = json.JSONDecoder()
    objects: list[dict] = []
    cursor = 0
    while True:
        start = content.find("{", cursor)
        if start < 0:
            break
        try:
            value, end = decoder.raw_decode(content, start)
        except json.JSONDecodeError:
            cursor = start + 1
            continue
        if isinstance(value, dict):
            objects.append(value)
            cursor = end
        else:
            cursor = start + 1
    if not objects:
        raise ValueError("LLM response did not contain a valid JSON object")
    return json.dumps(objects[-1], ensure_ascii=False)


class HttpChatCompletionClient:
    """Client for a configured OpenAI-compatible JSON chat-completions endpoint."""

    def __init__(self, settings: AgentSettings, *, timeout_seconds: float = 30.0) -> None:
        if not settings.llm_enabled:
            raise ValueError("LLM model, API key, and chat-completions URL must be configured")
        self._settings = settings
        self._timeout = timeout_seconds

    async def complete_json(self, *, system_prompt: str, user_prompt: str) -> str:
        endpoint = self._settings.llm_chat_completions_url
        api_key = self._settings.llm_api_key
        model = self._settings.llm_model
        if not (endpoint and api_key and model):
            raise ValueError("OpenAI-compatible provider requires a model, API key, and endpoint")
        headers = {"Authorization": f"Bearer {self._settings.llm_api_key}"}
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "response_format": {"type": "json_object"},
            "temperature": self._settings.llm_temperature,
        }
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                endpoint,
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
        try:
            content = response.json()["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ValueError("LLM response did not contain a chat message") from exc
        if not isinstance(content, str):
            raise ValueError("LLM response content must be text")
        return content


class OllamaChatClient:
    """Structured JSON client for a locally running Ollama instance."""

    def __init__(self, settings: AgentSettings) -> None:
        if not settings.ollama_base_url or not settings.ollama_chat_model:
            raise ValueError("Ollama requires OLLAMA_BASE_URL and OLLAMA_CHAT_MODEL")
        self._settings = settings

    async def complete_json(self, *, system_prompt: str, user_prompt: str) -> str:
        payload = {
            "model": self._settings.ollama_chat_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "format": "json",
            "stream": False,
            "options": {"temperature": self._settings.llm_temperature},
        }
        async with httpx.AsyncClient(timeout=self._settings.llm_timeout_seconds) as client:
            response = await client.post(f"{self._settings.ollama_base_url}/api/chat", json=payload)
            response.raise_for_status()
        try:
            content = response.json()["message"]["content"]
        except (KeyError, TypeError) as exc:
            raise ValueError("Ollama response did not contain a chat message") from exc
        if not isinstance(content, str):
            raise ValueError("Ollama response content must be text")
        return final_json_object(content)


def build_chat_client(settings: AgentSettings) -> StructuredChatClient:
    """Select the configured provider explicitly; never silently switch providers."""
    if settings.llm_provider == "ollama":
        return OllamaChatClient(settings)
    if settings.llm_provider == "openai":
        api_key = settings.openai_api_key or settings.llm_api_key
        if not api_key:
            raise ValueError("OpenAI provider selected but OPENAI_API_KEY is not set")
        adapted = AgentSettings(
            llm_provider="openai",
            llm_model=settings.openai_model,
            llm_api_key=api_key,
            llm_chat_completions_url=(
                settings.llm_chat_completions_url or "https://api.openai.com/v1/chat/completions"
            ),
            openai_api_key=api_key,
            openai_model=settings.openai_model,
            llm_timeout_seconds=settings.llm_timeout_seconds,
            llm_temperature=settings.llm_temperature,
        )
        client = HttpChatCompletionClient(adapted, timeout_seconds=settings.llm_timeout_seconds)
        return client
    raise ValueError("LLM_PROVIDER must be either 'ollama' or 'openai'")


class LLMIntentExtractor:
    def __init__(self, client: StructuredChatClient) -> None:
        self._client = client

    async def extract(self, user_request: str, *, context: dict[str, Any] | None = None) -> Intent:
        if not user_request.strip():
            raise ValueError("user_request must not be empty")
        content = await self._client.complete_json(
            system_prompt=(
                "Extract a public-service request into the requested JSON fields. "
                "Do not invent service names or jurisdiction; use null when unknown. "
                "Preserve named schemes, portals, acronyms, and distinctive form names in service_name; "
                "do not flatten a named portal into a generic category. Use prior service memory only to "
                "interpret a clear follow-up, and let an explicit new request override that memory. "
                "For greetings, thanks, or casual small talk use intent casual_conversation "
                "with requires_browser false. For requests unrelated to public services, "
                "forms, schemes, applications, or casual conversation use intent out_of_scope "
                "with requires_browser false. Requests to understand or fill any public-service "
                "form or scheme are in scope even when the exact service is unknown. "
                "Allowed intent values: casual_conversation, out_of_scope, find_service, get_information, check_eligibility, "
                "apply_for_service, track_application. Allowed service_category values: "
                "education, certificate, scholarship, benefit, license, registration, other, civil_certificate, "
                "identity_document, transport, land_revenue, social_welfare, food_security, labour_employment, healthcare, grievance, others. "
                "Return JSON with intent, service_category, service_name, jurisdiction, "
                "goal, requires_browser, eligibility_is_personal, collected_information, and missing_information. "
                "Set eligibility_is_personal true only when the user asks whether THEY personally qualify; "
                "a general question asking for a scheme's eligibility criteria is informational and must be false. "
                "Classify a question about a scheme's eligibility criteria as check_eligibility even when it is not personal. "
                "Preserve details supplied over earlier turns in collected_information. "
                "List only the next detail needed in missing_information; do not require "
                "the user to provide every detail in one message."
            ),
            user_prompt=json.dumps(
                {
                    "current_message": user_request,
                    "intent_memory": (context or {}).get("intent", {}),
                    "service_memory": (context or {}).get("service_resolution", {}),
                },
                ensure_ascii=False,
            ),
        )
        try:
            data = json.loads(content)
        except json.JSONDecodeError as exc:
            raise ValueError("LLM returned invalid JSON for intent extraction") from exc
        return Intent.model_validate(data)
