import re
import inspect
from typing import Any

from backend.app.agent.config import AgentSettings
from backend.app.agent.schemas.intent import Intent, IntentType
from backend.app.agent.schemas.service import ServiceCategory
from backend.app.agent.services.llm import (
    IntentExtractor,
    LLMIntentExtractor,
    build_chat_client,
)


class RuleBasedIntentExtractor:
    """Predictable offline baseline; only extracts explicit cues from user text."""

    _jurisdictions = ("Maharashtra", "Karnataka", "Tamil Nadu", "Delhi", "India")
    _service_cues = (
        "form",
        "scheme",
        "government",
        "public service",
        "application",
        "apply",
        "certificate",
        "scholarship",
        "student aid",
        "benefit",
        "pension",
        "allowance",
        "license",
        "licence",
        "registration",
        "register",
        "eligibility",
        "eligible",
        "qualify",
        "requirement",
        "document",
        "fee",
        "portal",
        "track",
        "application status",
        "fill",
    )

    async def extract(self, user_request: str) -> Intent:
        request = user_request.strip()
        if not request:
            raise ValueError("user_request must not be empty")
        text = request.casefold()

        if re.search(
            r"^(hi|hello|hey|hii|good morning|good afternoon|good evening|thanks|thank you|"
            r"bye|goodbye|how are you|who are you|what can you do|help|help me|can you help me|"
            r"what's up|whats up|nice to meet you|are you real)$",
            text.rstrip(".!?").strip(),
        ):
            return Intent(
                intent=IntentType.CASUAL_CONVERSATION,
                goal="casual_conversation",
                requires_browser=False,
            )

        if not any(cue in text for cue in self._service_cues):
            return Intent(
                intent=IntentType.OUT_OF_SCOPE,
                goal="out_of_scope",
                requires_browser=False,
            )

        if re.search(r"\b(track|tracking|application status|status of my)\b", text):
            intent_type = IntentType.TRACK_APPLICATION
        elif re.search(r"\b(eligible|eligibility|qualify|qualification)\b", text):
            intent_type = IntentType.CHECK_ELIGIBILITY
        elif re.search(r"\b(find|which|locate|search for)\b", text):
            intent_type = IntentType.FIND_SERVICE
        elif re.search(r"\b(what|which|tell me|explain|information about|available|requirements|documents|required documents|fees|how do i)\b", text):
            intent_type = IntentType.GET_INFORMATION
        else:
            intent_type = IntentType.APPLY_FOR_SERVICE

        if re.search(r"\b(mahadbt|maha\s*dbt)\b", text):
            category = ServiceCategory.SCHOLARSHIP
            name = "mahadbt"
        elif re.search(r"\b(scholarship|scholarships|student aid)\b", text):
            category = ServiceCategory.SCHOLARSHIP
            name = "scholarship"
        elif re.search(r"\b(certificate|domicile|birth certificate|caste certificate)\b", text):
            category = ServiceCategory.CERTIFICATE
            name = "domicile_certificate" if "domicile" in text else "certificate"
        elif re.search(r"\b(license|licence)\b", text):
            category = ServiceCategory.LICENSE
            name = "license"
        elif re.search(r"\b(benefit|pension|allowance)\b", text):
            category = ServiceCategory.BENEFIT
            name = "benefit"
        elif re.search(r"\b(registration|register)\b", text):
            category = ServiceCategory.REGISTRATION
            name = "registration"
        else:
            category = None
            name = None

        jurisdiction = next(
            (item for item in self._jurisdictions if item.casefold() in text),
            None,
        )
        if name == "mahadbt":
            jurisdiction = jurisdiction or "Maharashtra"
        missing: list[str] = []
        if category is None:
            missing.append("service_name")
        if category is not None and jurisdiction is None:
            missing.append("jurisdiction")

        return Intent(
            intent=intent_type,
            service_category=category,
            service_name=name,
            jurisdiction=jurisdiction,
            goal="complete_application" if intent_type is IntentType.APPLY_FOR_SERVICE else intent_type.value,
            requires_browser=intent_type in {IntentType.APPLY_FOR_SERVICE, IntentType.TRACK_APPLICATION},
            eligibility_is_personal=bool(
                intent_type is IntentType.CHECK_ELIGIBILITY
                and re.search(r"\b(am i|do i|can i|my eligibility|whether i|for me)\b", text)
            ),
            missing_information=missing,
        )


class IntentNode:
    def __init__(self, extractor: IntentExtractor) -> None:
        self._extractor = extractor

    async def run(self, user_request: str, context: dict[str, Any] | None = None) -> Intent:
        baseline = await RuleBasedIntentExtractor().extract(user_request)
        if baseline.intent in {IntentType.CASUAL_CONVERSATION, IntentType.OUT_OF_SCOPE}:
            return baseline
        extract = self._extractor.extract
        try:
            if "context" in inspect.signature(extract).parameters:
                intent = await extract(user_request, context=context)
            else:
                intent = await extract(user_request)
        except Exception:
            # Keep the assistant usable when the configured LLM is temporarily
            # unavailable or returns malformed structured output. Later workflow
            # stages still validate service and source information independently.
            intent = baseline
        if baseline.service_name == "mahadbt":
            intent = intent.model_copy(
                update={
                    "service_category": ServiceCategory.SCHOLARSHIP,
                    "service_name": "mahadbt",
                    "jurisdiction": "Maharashtra",
                    "missing_information": [
                        field for field in intent.missing_information if field != "jurisdiction"
                    ],
                }
            )
        return intent


def build_intent_extractor(settings: AgentSettings | None = None) -> IntentExtractor:
    configuration = settings or AgentSettings.from_environment()
    if not configuration.llm_configured:
        return RuleBasedIntentExtractor()
    if not configuration.llm_enabled:
        if configuration.llm_provider not in {"ollama", "openai"}:
            raise ValueError("LLM configuration is incomplete: LLM_PROVIDER must be either 'ollama' or 'openai'")
        if configuration.llm_provider == "openai":
            raise ValueError("OpenAI provider selected but OPENAI_API_KEY is not set")
        raise ValueError("LLM configuration is incomplete for the selected LLM_PROVIDER")
    return LLMIntentExtractor(build_chat_client(configuration))
