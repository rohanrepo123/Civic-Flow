"""Adapter from Member 2's LangGraph pipeline to Member 1's frozen contracts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse
from uuid import uuid4

from civicflow_contracts.ai import (
    AgentActionRequest,
    AgentActionType,
    AgentTurnRequest,
    AgentTurnResponse,
    DocumentRequirement,
    EligibilityOutcome,
    EligibilityRequest,
    EligibilityResult,
    ServiceDiscoveryRequest,
    SourceCitation,
)
from civicflow_contracts.application import ServiceContext, ServiceSummary

from backend.app.agent.config import AgentSettings
from backend.app.agent.graph import WorkflowDependencies, create_civicflow_graph, resume_task, run_task
from backend.app.agent.nodes.intent import RuleBasedIntentExtractor, build_intent_extractor
from backend.app.agent.schemas.intent import Intent, IntentType
from backend.app.agent.schemas.requirements import EligibilityRule
from backend.app.agent.schemas.service import ServiceRecord
from backend.app.agent.services.curated_knowledge import CuratedKnowledge
from backend.app.agent.services.eligibility_engine import EligibilityEngine
from backend.app.agent.services.service_registry import ServiceRegistry
from backend.app.agent.services.service_resolver import ServiceResolver
from backend.app.agent.services.service_discovery import ServiceCandidateMatcher
from backend.app.agent.services.llm import build_chat_client
from backend.app.agent.services.source_fallback import SourceRelevanceJudge, TavilyOfficialSearch
from backend.app.agent.services.official_documents import OfficialDocumentFetcher


_SECRET_KEY = re.compile(
    r"password|passcode|one.?time.?password|otp|captcha|payment.?pin|card.?number|"
    r"security.?code|cvv|e.?sign|private.?key|access.?token|refresh.?token",
    re.IGNORECASE,
)
_SECRET_VALUE = re.compile(
    r"\b(?:password|passcode|otp|captcha|payment pin|cvv|security code)\s*(?:is|:|=)\s*\S+",
    re.IGNORECASE,
)


def reject_authentication_secrets(message: str, value: Any, path: str = "context") -> None:
    """Reject secret-like context keys and explicit credential values without logging them."""
    if _SECRET_VALUE.search(message):
        raise ValueError("Authentication credentials must be entered directly on the service portal.")
    if isinstance(value, dict):
        for key, child in value.items():
            if _SECRET_KEY.search(str(key)) and child not in (None, "", [], {}):
                raise ValueError("Authentication credentials must not be sent to the AI service.")
            reject_authentication_secrets(message, child, f"{path}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            reject_authentication_secrets(message, child, f"{path}.{index}")


def _citations_from_sources(sources: list[Any]) -> list[SourceCitation]:
    citations: list[SourceCitation] = []
    seen: set[str] = set()
    for source in sources:
        url = str(getattr(source, "url", getattr(source, "source_url", "")))
        title = str(getattr(source, "title", getattr(source, "source_title", "Official source")))
        if url and url not in seen:
            citations.append(SourceCitation(title=title, url=url))
            seen.add(url)
    return citations


def _service_context(
    service: ServiceRecord,
    requirements: Any | None = None,
    citations: list[SourceCitation] | None = None,
) -> ServiceContext:
    sources = citations or _citations_from_sources(service.official_sources)
    return ServiceContext(
        service=ServiceSummary(
            service_id=service.service_id,
            name=service.name,
            category=service.category.value,
            description=service.description,
            jurisdiction=service.jurisdiction,
            portal_url=str(service.official_portal) if service.official_portal else None,
            allowed_domains=(
                [urlparse(str(service.official_portal)).hostname]
                if service.official_portal and urlparse(str(service.official_portal)).hostname
                else []
            ),
        ),
        eligibility_rules=(
            {
                f"rule_{index}": rule.model_dump(mode="json")
                for index, rule in enumerate(requirements.eligibility_rules, start=1)
            }
            if requirements is not None
            else {}
        ),
        required_documents=(
            [item.document_type for item in requirements.required_documents]
            if requirements is not None
            else []
        ),
        source_urls=[citation.url for citation in sources],
    )


def _rules_from_context(raw_rules: Any) -> list[EligibilityRule]:
    if isinstance(raw_rules, list):
        candidates = raw_rules
    elif isinstance(raw_rules, dict):
        candidates = []
        for field_name, value in raw_rules.items():
            if isinstance(value, dict):
                if "field" in value and "operator" in value:
                    candidates.append(value)
                elif "operator" in value:
                    candidates.append({"field": field_name, **value})
    else:
        return []
    rules: list[EligibilityRule] = []
    for candidate in candidates:
        try:
            rules.append(EligibilityRule.model_validate(candidate))
        except (TypeError, ValueError):
            continue
    return rules


@dataclass
class Member2Runtime:
    settings: AgentSettings
    registry: ServiceRegistry
    knowledge: CuratedKnowledge
    intent_extractor: Any
    graph: Any
    runs: dict[str, dict[str, Any]]
    pending_runs: dict[str, dict[str, Any]]
    conversation_memories: dict[str, dict[str, dict[str, Any]]]

    @classmethod
    def create(cls) -> "Member2Runtime":
        settings = AgentSettings.from_environment()
        registry = ServiceRegistry.default()
        knowledge = CuratedKnowledge.default()
        resolver = ServiceResolver(registry)
        intent_extractor = build_intent_extractor(settings)
        chat_client = build_chat_client(settings) if settings.llm_enabled else None
        relevance_judge = SourceRelevanceJudge(chat_client) if chat_client else None
        service_matcher = ServiceCandidateMatcher(chat_client) if chat_client else None
        graph = create_civicflow_graph(
            WorkflowDependencies(
                intent_extractor=intent_extractor,
                service_resolver=resolver,
                requirement_extractor=knowledge,
                source_retriever=knowledge.retrieve,
                service_matcher=service_matcher,
                source_relevance_judge=relevance_judge,
                web_search=TavilyOfficialSearch.from_environment(),
                official_document_fetcher=OfficialDocumentFetcher(),
            )
        )
        return cls(
            settings=settings,
            registry=registry,
            knowledge=knowledge,
            intent_extractor=intent_extractor,
            graph=graph,
            runs={},
            pending_runs={},
            conversation_memories={},
        )

    def mode(self) -> str:
        if self.settings.llm_enabled:
            return f"langgraph_{self.settings.llm_provider}"
        return "langgraph_rules_only"

    async def discover(self, request: ServiceDiscoveryRequest) -> dict[str, Any]:
        intent = await RuleBasedIntentExtractor().extract(request.query)
        category = intent.service_category
        if request.category:
            from backend.app.agent.schemas.service import ServiceCategory

            normalized = request.category.casefold().rstrip("s")
            category = next(
                (item for item in ServiceCategory if item.value.casefold().rstrip("s") == normalized),
                category,
            )
        intent = intent.model_copy(
            update={
                "service_category": category,
                "jurisdiction": request.jurisdiction or intent.jurisdiction,
                "service_name": intent.service_name or request.query,
                "intent": IntentType.FIND_SERVICE,
                "goal": IntentType.FIND_SERVICE.value,
                "requires_browser": False,
            }
        )
        result = ServiceResolver(self.registry).resolve(intent)
        records = result.candidates or ([result.selected_service] if result.selected_service else [])
        ranked = []
        for service in records:
            if service is None:
                continue
            citations = _citations_from_sources(service.official_sources)
            ranked.append(
                {
                    "service_id": service.service_id,
                    "name": service.name,
                    "category": service.category.value,
                    "jurisdiction": service.jurisdiction,
                    "confidence": 0.85 if service.verification_status.value == "verified" else 0.55,
                    "source_url": citations[0].url if citations else None,
                    "source_citations": [citation.model_dump(mode="json") for citation in citations],
                    "jurisdiction_verified": bool(request.jurisdiction or intent.jurisdiction),
                    "verification_status": service.verification_status.value,
                }
            )
        return {
            "contract_version": request.contract_version,
            "correlation_id": request.correlation_id,
            "results": ranked,
            "status": result.status.value,
            "clarification_question": result.clarification_question,
            "mode": self.mode(),
        }

    async def turn(self, request: AgentTurnRequest) -> AgentTurnResponse:
        context: dict[str, Any] = {}
        if request.sanitized_application_context is not None:
            context.update(request.sanitized_application_context.sanitized_data)
            context.update(request.sanitized_application_context.applicant.attributes)
        history = [
            {"role": item.role, "content": item.content}
            for item in request.history[-8:]
        ]
        reject_authentication_secrets(request.message, {"context": context, "history": history})

        graph_request = request.message.strip()
        selected = request.selected_service_context
        conversation_id = request.conversation_id
        layer_context = self.conversation_memories.get(conversation_id, {})
        if not layer_context:
            previous_user = next(
                (item["content"] for item in reversed(history) if item["role"] == "user"),
                "",
            )
            if previous_user:
                previous_intent = await RuleBasedIntentExtractor().extract(previous_user)
                if previous_intent.intent not in {IntentType.CASUAL_CONVERSATION, IntentType.OUT_OF_SCOPE}:
                    layer_context = {
                        "intent": {"last_intent": previous_intent.intent.value},
                        "service_resolution": {
                            "service_name": previous_intent.service_name,
                            "jurisdiction": previous_intent.jurisdiction,
                        },
                        "knowledge": {},
                    }
        pending_run = self.pending_runs.get(conversation_id)
        if pending_run is not None:
            run_id = pending_run["run_id"]
            resume_value = await self._resume_value(request.message, pending_run["interrupt"])
            result = await resume_task(self.graph, task_id=run_id, resume_value=resume_value)
        else:
            graph_request = await self._restore_recent_intent(graph_request, history)
            if selected is not None:
                graph_request = (
                    f"{graph_request}\nPublic service context: {selected.service.name}, "
                    f"{selected.service.jurisdiction}. Service ID: {selected.service.service_id}."
                )
            run_id = str(uuid4())
            result = await run_task(
                self.graph,
                {
                    "user_id": str(request.user_id),
                    "user_request": graph_request,
                    "applicant_profile": context,
                    "layer_context": layer_context,
                },
                task_id=run_id,
            )

        pending = (result.get("__interrupt__") or [None])[0]
        pending_value = pending.value if pending is not None else None
        if pending_value is not None:
            self.pending_runs[conversation_id] = {"run_id": run_id, "interrupt": pending_value}
        else:
            self.pending_runs.pop(conversation_id, None)

        intent: Intent | None = result.get("intent")
        message = (
            pending_value.get("question") or pending_value.get("message")
            if isinstance(pending_value, dict)
            else None
        ) or result.get("final_summary") or "I couldn’t complete that step safely. Please try again."
        service: ServiceRecord | None = result.get("selected_service")
        requirements = result.get("requirements")
        citations = _citations_from_sources(
            list(result.get("official_sources", [])) + list(getattr(requirements, "sources", []))
        )
        if service is not None:
            selected = _service_context(service, requirements, citations)
            if service.official_portal and all(
                citation.url != str(service.official_portal) for citation in citations
            ):
                citations.append(
                    SourceCitation(
                        title=f"{service.name} portal",
                        url=str(service.official_portal),
                    )
                )

        # Keep distinct, compact memories for the intent, service resolver, and
        # knowledge stages. They contain service/source metadata, not applicant PII.
        self.conversation_memories[conversation_id] = {
            "intent": {
                "last_intent": intent.intent.value if intent else None,
                "last_request": request.message[:500],
            },
            "service_resolution": (
                {
                    "service_id": service.service_id,
                    "service_name": service.name,
                    "jurisdiction": service.jurisdiction,
                }
                if service is not None
                else layer_context.get("service_resolution", {})
            ),
            "knowledge": {
                "sources": [
                    {"title": item.title, "url": str(item.url)}
                    for item in citations[:8]
                ],
                "service_id": service.service_id if service else None,
            },
        }

        proposed_action = None
        allowed = set(request.allowed_actions)
        if pending_value and "ask_user" in allowed:
            proposed_action = AgentActionRequest(
                action_type=AgentActionType.ask_user,
                parameters={"question": message},
                requires_user_approval=True,
            )
        elif intent and intent.intent is IntentType.APPLY_FOR_SERVICE and "prepare_form" in allowed:
            proposed_action = AgentActionRequest(
                action_type=AgentActionType.prepare_form,
                parameters={"service_id": service.service_id if service else None},
                requires_user_approval=True,
            )

        eligibility_result = None
        raw_eligibility = result.get("eligibility_result")
        if raw_eligibility is not None and intent and intent.intent in {
            IntentType.CHECK_ELIGIBILITY,
            IntentType.APPLY_FOR_SERVICE,
        }:
            if raw_eligibility.status.value == "not_eligible":
                outcome, eligible = EligibilityOutcome.ineligible, False
            elif raw_eligibility.status.value == "insufficient_information":
                outcome, eligible = EligibilityOutcome.needs_information, None
            else:
                outcome, eligible = EligibilityOutcome.unknown, None
            eligibility_result = EligibilityResult(
                outcome=outcome,
                eligible=eligible,
                reasons=[item.explanation for item in raw_eligibility.failed_rules]
                + (["A positive rule check is not a guarantee of eligibility."] if eligible is None else []),
                missing_information=raw_eligibility.missing_fields,
                confidence=0.75 if raw_eligibility.supporting_sources else 0.25,
                source_citations=citations,
            )

        document_requirements = []
        if requirements is not None:
            for document in requirements.required_documents:
                document_requirements.append(
                    DocumentRequirement(
                        document_type=document.document_type,
                        required=document.mandatory,
                        reason="Listed in curated service requirements; verify against the linked current official source.",
                        source_citations=citations,
                    )
                )

        missing = list(result.get("missing_information", []))
        if isinstance(pending_value, dict) and pending_value.get("type") == "information.required":
            missing.extend(item for item in pending_value.get("items", []) if item not in missing)
        elif isinstance(pending_value, dict) and pending_value.get("type") == "service.clarification_required" and intent:
            missing.extend(field for field in intent.missing_information if field not in missing)
        if missing and pending_value is None:
            message = f"{message}\n\nWe can continue when you are ready. Still needed: {', '.join(missing)}."
        if service is not None and service.official_portal and pending_value is None:
            message += f"\n\nPortal: {service.official_portal}"
        uncertainty = list(getattr(requirements, "uncertainties", []) or [])
        if not citations:
            uncertainty.append("No source citation was retrieved for this response.")
        response = AgentTurnResponse(
            contract_version=request.contract_version,
            correlation_id=request.correlation_id,
            run_id=run_id,
            assistant_message=message,
            intent=intent.intent.value if intent else "service_assistance",
            selected_service=selected,
            eligibility_result=eligibility_result,
            missing_information=list(dict.fromkeys(missing)),
            document_requirements=document_requirements,
            proposed_next_action=proposed_action,
            source_citations=citations,
            confidence=0.8 if citations else 0.45,
            uncertainty=list(dict.fromkeys(uncertainty)),
            mode=self.mode(),
        )
        self.runs[run_id] = response.model_dump(mode="json")
        return response

    async def _restore_recent_intent(
        self,
        current_message: str,
        history: list[dict[str, str]],
    ) -> str:
        """Rebuild a lightweight service intent if the process lost its checkpoint."""
        previous_assistant = next(
            (item["content"] for item in reversed(history) if item["role"] == "assistant"),
            "",
        )
        if "?" not in previous_assistant:
            return current_message
        previous_user = next(
            (item["content"] for item in reversed(history) if item["role"] == "user"),
            "",
        )
        if not previous_user:
            return current_message
        prior_intent = await RuleBasedIntentExtractor().extract(previous_user)
        if prior_intent.intent in {IntentType.CASUAL_CONVERSATION, IntentType.OUT_OF_SCOPE}:
            return current_message
        return f"Earlier service request: {previous_user}\nCitizen's follow-up: {current_message}"

    @staticmethod
    async def _resume_value(message: str, interrupt_value: dict[str, Any]) -> dict[str, Any]:
        """Turn a single citizen reply into the field requested by the paused graph."""
        answer = message.strip()
        if not answer or answer.casefold() in {"skip", "not sure", "i don't know", "i do not know"}:
            return {}

        if interrupt_value.get("type") == "information.required":
            items = interrupt_value.get("items") or []
            if not items:
                return {}
            return {str(items[0]): answer}

        if interrupt_value.get("type") == "service.clarification_required":
            candidates = interrupt_value.get("candidates") or []
            ordinal = re.fullmatch(r"\s*(\d+)\s*", answer)
            if ordinal:
                index = int(ordinal.group(1)) - 1
                if 0 <= index < len(candidates):
                    return {"service_id": candidates[index].get("service_id")}
            normalized = answer.casefold().replace("_", " ").strip()
            for candidate in candidates:
                for value in (candidate.get("service_id"), candidate.get("name")):
                    if isinstance(value, str) and normalized == value.casefold().replace("_", " ").strip():
                        return {"service_id": candidate.get("service_id")}
            jurisdiction_names = set(RuleBasedIntentExtractor._jurisdictions)
            jurisdiction_names.update(
                item.get("jurisdiction", "") for item in candidates if item.get("jurisdiction")
            )
            jurisdiction = next(
                (name for name in jurisdiction_names if name and name.casefold() in normalized),
                None,
            )
            if jurisdiction:
                return {"jurisdiction": jurisdiction}
            return {"service_name": answer}
        return {}

    def evaluate_eligibility(self, request: EligibilityRequest) -> EligibilityResult:
        reject_authentication_secrets("", request.applicant)
        rules = _rules_from_context(request.service_context.eligibility_rules)
        result = EligibilityEngine().evaluate(rules, request.applicant)
        sources = [SourceCitation(title="Official service source", url=str(url)) for url in request.service_context.source_urls]
        if result.status.value == "potentially_eligible":
            outcome, eligible = EligibilityOutcome.unknown, None
            reasons = ["Sourced rules were satisfied; this is not an official eligibility decision."]
        elif result.status.value == "not_eligible":
            outcome, eligible = EligibilityOutcome.ineligible, False
            reasons = [rule.explanation for rule in result.failed_rules]
        elif result.status.value == "insufficient_information" and "eligibility_rules" not in result.missing_fields:
            outcome, eligible = EligibilityOutcome.needs_information, None
            reasons = ["Applicant information is incomplete for the available rules."]
        else:
            outcome, eligible = EligibilityOutcome.unknown, None
            reasons = ["No complete, sourced deterministic eligibility rules are configured for this service."]
        return EligibilityResult(
            outcome=outcome,
            eligible=eligible,
            reasons=reasons + result.validation_errors,
            missing_information=[field for field in result.missing_fields if field != "eligibility_rules"],
            confidence=0.8 if rules and sources else 0.0,
            source_citations=sources,
        )

    async def document_requirements(self, request: Any) -> dict[str, Any]:
        reject_authentication_secrets("", request.applicant)
        known = {service.service_id: service for service in self.registry.all()}
        service = known.get(request.service_context.service.service_id)
        requirements = None
        citations: list[SourceCitation] = []
        if service is not None:
            chunks = await self.knowledge.retrieve(service, service.name)
            requirements = await self.knowledge.extract(service_id=service.service_id, chunks=chunks)
            citations = _citations_from_sources(chunks)
        items = []
        if requirements is not None and requirements.required_documents:
            items = [
                DocumentRequirement(
                    document_type=item.document_type,
                    required=item.mandatory,
                    reason="Curated requirement; confirm against the current official portal.",
                    source_citations=citations,
                )
                for item in requirements.required_documents
            ]
        else:
            items = [
                DocumentRequirement(
                    document_type=name,
                    required=True,
                    reason="Provided by Core API service context; verify with the official service source.",
                    source_citations=[
                        SourceCitation(title="Official service source", url=str(url))
                        for url in request.service_context.source_urls
                    ],
                )
                for name in request.service_context.required_documents
            ]
        uncertainty = list(getattr(requirements, "uncertainties", []) or [])
        return {
            "contract_version": request.contract_version,
            "correlation_id": request.correlation_id,
            "requirements": [item.model_dump(mode="json") for item in items],
            "uncertainty": uncertainty,
            "mode": self.mode(),
        }
