import asyncio

import pytest
from pydantic import ValidationError

from backend.app.agent.nodes.intent import IntentNode, RuleBasedIntentExtractor
from backend.app.agent.nodes.intent import build_intent_extractor
from backend.app.agent.config import AgentSettings
from backend.app.agent.schemas.intent import Intent, IntentType
from backend.app.agent.schemas.resolution import ResolutionStatus
from backend.app.agent.schemas.service import ServiceCategory, ServiceRecord
from backend.app.agent.services.llm import (
    LLMIntentExtractor,
    OllamaChatClient,
    build_chat_client,
    final_json_object,
)
from backend.app.agent.services.service_registry import ServiceRegistry
from backend.app.agent.services.service_resolver import ServiceResolver


@pytest.mark.parametrize(
    ("user_text", "intent_type", "category", "service_name", "jurisdiction"),
    [
        (
            "I want to apply for a domicile certificate in Maharashtra",
            IntentType.APPLY_FOR_SERVICE,
            ServiceCategory.CERTIFICATE,
            "domicile_certificate",
            "Maharashtra",
        ),
        (
            "Check scholarship eligibility in Maharashtra",
            IntentType.CHECK_ELIGIBILITY,
            ServiceCategory.SCHOLARSHIP,
            "scholarship",
            "Maharashtra",
        ),
        (
            "Find a scholarship in Karnataka",
            IntentType.FIND_SERVICE,
            ServiceCategory.SCHOLARSHIP,
            "scholarship",
            "Karnataka",
        ),
    ],
)
def test_rule_based_intent_extracts_certificate_and_scholarship(
    user_text: str,
    intent_type: IntentType,
    category: ServiceCategory,
    service_name: str,
    jurisdiction: str,
) -> None:
    intent = asyncio.run(RuleBasedIntentExtractor().extract(user_text))
    assert intent.intent is intent_type
    assert intent.service_category is category
    assert intent.service_name == service_name
    assert intent.jurisdiction == jurisdiction


def test_intent_node_uses_injected_extractor() -> None:
    node = IntentNode(RuleBasedIntentExtractor())
    result = asyncio.run(node.run("Track my application"))
    assert result.intent is IntentType.TRACK_APPLICATION
    assert result.requires_browser is True


def test_casual_conversation_does_not_require_service_resolution() -> None:
    intent = asyncio.run(RuleBasedIntentExtractor().extract("hello"))
    assert intent.intent is IntentType.CASUAL_CONVERSATION
    assert intent.requires_browser is False


def test_general_help_request_is_casual_until_the_user_names_a_service() -> None:
    intent = asyncio.run(RuleBasedIntentExtractor().extract("Can you help me?"))
    assert intent.intent is IntentType.CASUAL_CONVERSATION


def test_intent_node_short_circuits_out_of_scope_before_calling_the_llm() -> None:
    class UnexpectedExtractor:
        async def extract(self, user_request: str) -> Intent:
            raise AssertionError("out-of-scope requests must not call the LLM")

    result = asyncio.run(IntentNode(UnexpectedExtractor()).run("tell me a joke"))
    assert result.intent is IntentType.OUT_OF_SCOPE


@pytest.mark.parametrize("user_text", ["tell me a joke", "what is the weather today?"])
def test_unrelated_requests_are_marked_out_of_scope(user_text: str) -> None:
    intent = asyncio.run(RuleBasedIntentExtractor().extract(user_text))
    assert intent.intent is IntentType.OUT_OF_SCOPE
    assert intent.requires_browser is False


@pytest.mark.parametrize(
    "user_text",
    [
        "Can you help me with any government form?",
        "I want to fill a scheme application",
        "Help me understand the documents for a public service",
    ],
)
def test_generic_forms_and_schemes_remain_in_scope(user_text: str) -> None:
    intent = asyncio.run(RuleBasedIntentExtractor().extract(user_text))
    assert intent.intent is not IntentType.OUT_OF_SCOPE


def test_intent_extractor_uses_offline_baseline_when_unconfigured() -> None:
    extractor = build_intent_extractor(
        AgentSettings(None, None, None, None)
    )
    assert isinstance(extractor, RuleBasedIntentExtractor)


def test_ollama_cloud_model_is_the_default_provider_configuration(monkeypatch) -> None:
    for name in ("LLM_PROVIDER", "OLLAMA_CHAT_MODEL", "OLLAMA_BASE_URL"):
        monkeypatch.delenv(name, raising=False)
    settings = AgentSettings.from_environment()
    assert settings.llm_provider == "ollama"
    assert settings.ollama_chat_model == "nemotron-3-super:cloud"
    assert isinstance(build_chat_client(settings), OllamaChatClient)


def test_groq_provider_uses_configured_secret_and_json_compatible_endpoint(monkeypatch) -> None:
    from backend.app.agent.services.llm import HttpChatCompletionClient

    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.setenv("GROQ_API_KEY", "test-groq-key")
    monkeypatch.delenv("GROQ_MODEL", raising=False)
    settings = AgentSettings.from_environment()
    client = build_chat_client(settings)

    assert isinstance(client, HttpChatCompletionClient)
    assert client._settings.llm_chat_completions_url == "https://api.groq.com/openai/v1/chat/completions"
    assert client._settings.llm_model == "openai/gpt-oss-20b"


def test_groq_provider_requires_api_key(monkeypatch) -> None:
    monkeypatch.setenv("LLM_PROVIDER", "groq")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    settings = AgentSettings.from_environment()
    with pytest.raises(ValueError, match="GROQ_API_KEY"):
        build_chat_client(settings)


def test_final_json_object_discards_nemotron_reasoning_preamble() -> None:
    content = '<think>Maybe this format is useful: {"wrong": true}</think>\n{"ok": true}'
    assert final_json_object(content) == '{"ok": true}'


def test_final_json_object_preserves_nested_result_object() -> None:
    content = 'Reasoning... {"result": {"status": "ready"}}'
    assert final_json_object(content) == '{"result": {"status": "ready"}}'


def test_intent_extractor_rejects_partial_llm_configuration() -> None:
    with pytest.raises(ValueError, match="configuration is incomplete"):
        build_intent_extractor(AgentSettings("provider", "model", None, None))


def test_service_resolver_resolves_curated_domicile_service() -> None:
    registry = ServiceRegistry.default()
    intent = Intent(
        intent=IntentType.APPLY_FOR_SERVICE,
        service_category=ServiceCategory.CERTIFICATE,
        service_name="domicile_certificate",
        jurisdiction="Maharashtra",
        goal="complete_application",
        requires_browser=True,
    )
    result = ServiceResolver(registry).resolve(intent)
    assert result.status is ResolutionStatus.RESOLVED
    assert result.selected_service is not None
    assert result.selected_service.service_id == "maharashtra_domicile_certificate"
    assert result.selected_service.verification_status.value == "verified"
    assert str(result.selected_service.official_portal).startswith("https://aaplesarkar.mahaonline.gov.in/")


def test_service_resolver_returns_not_found_for_unknown_jurisdiction() -> None:
    intent = Intent(
        intent=IntentType.APPLY_FOR_SERVICE,
        service_category=ServiceCategory.CERTIFICATE,
        service_name="domicile_certificate",
        jurisdiction="Unknown State",
        goal="complete_application",
        requires_browser=True,
    )
    result = ServiceResolver(ServiceRegistry.default()).resolve(intent)
    assert result.status is ResolutionStatus.NOT_FOUND
    assert result.clarification_question


def test_service_resolver_distinguishes_jurisdictions() -> None:
    resolver = ServiceResolver(ServiceRegistry.default())
    for state, expected_id in (
        ("Maharashtra", "maharashtra_scholarship"),
        ("Karnataka", "karnataka_scholarship_demo"),
    ):
        intent = Intent(
            intent=IntentType.FIND_SERVICE,
            service_category=ServiceCategory.SCHOLARSHIP,
            service_name="scholarship",
            jurisdiction=state,
            goal="find_service",
            requires_browser=False,
        )
        result = resolver.resolve(intent)
        assert result.status is ResolutionStatus.RESOLVED
        assert result.selected_service is not None
        assert result.selected_service.service_id == expected_id


def test_service_resolver_asks_when_registry_matches_are_tied() -> None:
    registry = ServiceRegistry(
        [
            ServiceRecord(
                service_id="certificate_a",
                name="Certificate A",
                category=ServiceCategory.CERTIFICATE,
                jurisdiction="Maharashtra",
            ),
            ServiceRecord(
                service_id="certificate_b",
                name="Certificate B",
                category=ServiceCategory.CERTIFICATE,
                jurisdiction="Maharashtra",
            ),
        ]
    )
    intent = Intent(
        intent=IntentType.FIND_SERVICE,
        service_category=ServiceCategory.CERTIFICATE,
        jurisdiction="Maharashtra",
        goal="find_service",
        requires_browser=False,
    )
    result = ServiceResolver(registry).resolve(intent)
    assert result.status is ResolutionStatus.AMBIGUOUS
    assert len(result.candidates) == 2
    assert result.clarification_question


class FakeStructuredClient:
    def __init__(self, response: str) -> None:
        self.response = response

    async def complete_json(self, *, system_prompt: str, user_prompt: str) -> str:
        assert "Do not invent" in system_prompt
        assert user_prompt
        return self.response


def test_llm_intent_extractor_validates_structured_output() -> None:
    extractor = LLMIntentExtractor(
        FakeStructuredClient(
            '{"intent":"apply_for_service","service_category":"certificate",'
            '"service_name":"domicile_certificate","jurisdiction":"Maharashtra",'
            '"goal":"complete_application","requires_browser":true,"missing_information":[]}'
        )
    )
    result = asyncio.run(extractor.extract("Apply for a domicile certificate"))
    assert result.intent is IntentType.APPLY_FOR_SERVICE
    assert result.service_category is ServiceCategory.CERTIFICATE


def test_llm_intent_extractor_rejects_invalid_enum() -> None:
    extractor = LLMIntentExtractor(
        FakeStructuredClient(
            '{"intent":"make_it_up","goal":"x","requires_browser":false}'
        )
    )
    with pytest.raises(ValidationError):
        asyncio.run(extractor.extract("Find a service"))
