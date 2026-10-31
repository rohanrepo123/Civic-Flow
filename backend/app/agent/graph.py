import inspect
import re
from datetime import UTC, datetime
from typing import Any, Awaitable, Callable
from uuid import uuid4

from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import Command, interrupt

from backend.app.agent.clients.browser_client import BrowserClient, GuardedBrowserClient
from backend.app.agent.nodes.intent import IntentExtractor, IntentNode
from backend.app.agent.schemas.agent_events import AgentEvent, AgentEventType
from backend.app.agent.schemas.browser import BrowserSessionCreate
from backend.app.agent.schemas.documents import DocumentMetadata, ExtractedField
from backend.app.agent.schemas.eligibility import EligibilityResult, EligibilityStatus
from backend.app.agent.schemas.intent import Intent, IntentType
from backend.app.agent.schemas.planner import PlannerInput, PlannerResult
from backend.app.agent.schemas.requirements import ServiceRequirements
from backend.app.agent.schemas.resolution import ResolutionStatus, ServiceResolution
from backend.app.agent.schemas.service import ServiceRecord
from backend.app.agent.schemas.source import RetrievedChunk
from backend.app.agent.schemas.task import TaskStatus
from backend.app.agent.services.eligibility_engine import EligibilityEngine
from backend.app.agent.services.requirement_extractor import RequirementExtractor
from backend.app.agent.services.service_resolver import ServiceResolver
from backend.app.agent.services.task_planner import TaskPlanner
from backend.app.agent.state import CivicFlowState
from backend.app.agent.workflow_serializer import WorkflowSerializer
from backend.app.agent.schemas.browser import (
    BrowserActionRequest,
    BrowserObservation,
    ControlMode,
    ControlModeRequest,
    PageState,
)


AsyncOrSync = Callable[..., Any | Awaitable[Any]]
ApprovalStatusReader = Callable[[str], Any | Awaitable[Any]]
ActionProposer = Callable[[CivicFlowState], BrowserActionRequest | None | Awaitable[BrowserActionRequest | None]]
ActionVerifier = Callable[[BrowserActionRequest, BrowserObservation, BrowserObservation], bool | Awaitable[bool]]


class WorkflowDependencies:
    def __init__(
        self,
        *,
        intent_extractor: IntentExtractor,
        service_resolver: ServiceResolver,
        requirement_extractor: RequirementExtractor | None = None,
        source_retriever: AsyncOrSync | None = None,
        service_matcher: AsyncOrSync | None = None,
        source_relevance_judge: AsyncOrSync | None = None,
        web_search: AsyncOrSync | None = None,
        profile_loader: AsyncOrSync | None = None,
        document_analyzer: AsyncOrSync | None = None,
        browser_client: BrowserClient | None = None,
        action_proposer: ActionProposer | None = None,
        action_verifier: ActionVerifier | None = None,
        approval_status_reader: ApprovalStatusReader | None = None,
        planner: TaskPlanner | None = None,
        max_browser_actions: int = 20,
    ) -> None:
        self.intent_extractor = intent_extractor
        self.service_resolver = service_resolver
        self.requirement_extractor = requirement_extractor
        self.source_retriever = source_retriever
        self.service_matcher = service_matcher
        self.source_relevance_judge = source_relevance_judge
        self.web_search = web_search
        self.profile_loader = profile_loader
        self.document_analyzer = document_analyzer
        self.browser_client = browser_client
        self.action_proposer = action_proposer
        self.action_verifier = action_verifier
        self.approval_status_reader = approval_status_reader
        self.planner = planner or TaskPlanner()
        self.max_browser_actions = max_browser_actions


async def _call(function: AsyncOrSync, *args: Any, **kwargs: Any) -> Any:
    result = function(*args, **kwargs)
    return await result if inspect.isawaitable(result) else result


def _accepts_keyword(function: AsyncOrSync, keyword: str) -> bool:
    try:
        return keyword in inspect.signature(function).parameters
    except (TypeError, ValueError):
        return False


def _event(state: CivicFlowState, event_type: AgentEventType, payload: dict[str, Any] | None = None) -> list[AgentEvent]:
    events = list(state.get("events", []))
    events.append(
        AgentEvent(
            event_id=f"event_{uuid4().hex}",
            task_id=state["task_id"],
            sequence=len(events) + 1,
            type=event_type,
            timestamp=datetime.now(UTC),
            payload=payload or {},
        )
    )
    return events


def _set_profile_value(profile: dict[str, Any], field_name: str, value: Any) -> None:
    parts = field_name.split(".")
    current = profile
    for part in parts[:-1]:
        child = current.get(part)
        if not isinstance(child, dict):
            child = {}
            current[part] = child
        current = child
    current[parts[-1]] = value


def _is_sensitive_field(field_name: str) -> bool:
    return bool(re.search(r"password|passcode|one.time|\botp\b|captcha|token|secret", field_name, re.I))


def _question_for_missing_field(field_name: str) -> str:
    if field_name == "service_name":
        return "Which public service or form do you want help with?"
    if field_name == "jurisdiction":
        return "Which state or union territory is this for?"
    if field_name.startswith("document:"):
        return f"The service lists {field_name.split(':', 1)[1]} as a required document. Do you have it available?"
    label = field_name.replace("_", " ").replace(".", " ").strip()
    return f"What is your {label}? You can provide other details in later messages."


def create_civicflow_graph(
    dependencies: WorkflowDependencies,
    *,
    checkpointer: Any | None = None,
):
    intent_node = IntentNode(dependencies.intent_extractor)
    eligibility_engine = EligibilityEngine()
    guarded_browser: BrowserClient | None = dependencies.browser_client

    async def extract_intent(state: CivicFlowState) -> dict[str, Any]:
        intent = await intent_node.run(state["user_request"], state.get("layer_context", {}))
        events = _event(
            state,
            AgentEventType.INTENT_EXTRACTED,
            {"intent": intent.intent.value, "service_category": intent.service_category.value if intent.service_category else None},
        )
        return {"intent": intent, "events": events}

    async def resolve_service(state: CivicFlowState) -> dict[str, Any]:
        intent = state["intent"]
        resolution = dependencies.service_resolver.resolve(intent)
        if resolution.status is not ResolutionStatus.RESOLVED and dependencies.service_matcher is not None:
            try:
                match = await _call(
                    dependencies.service_matcher,
                    query=state["user_request"],
                    intent=intent,
                    services=list(dependencies.service_resolver.all_services()),
                    context=state.get("layer_context", {}).get("service_resolution", {}),
                )
            except Exception:
                match = None
            selected_match = next(
                (item for item in dependencies.service_resolver.all_services() if item.service_id == match),
                None,
            )
            if selected_match is not None:
                resolution = ServiceResolution(
                    status=ResolutionStatus.RESOLVED,
                    selected_service=selected_match,
                    candidates=[selected_match],
                )
        while resolution.status is not ResolutionStatus.RESOLVED:
            if not intent.service_name:
                question = "Sure — what is the form or scheme about, and which state is it for? For example, a scholarship form in Maharashtra."
            elif not intent.jurisdiction:
                question = "Which state is this for?"
            else:
                question = "I found a few possible services. Which one do you mean? You can describe it in a few words."
            answer = interrupt(
                {
                    "type": "service.clarification_required",
                    "question": question,
                    "candidates": [item.model_dump(mode="json") for item in resolution.candidates],
                    "service_name": intent.service_name,
                    "jurisdiction": intent.jurisdiction,
                }
            )
            if not isinstance(answer, dict):
                continue
            selected_id = answer.get("service_id")
            selected = next(
                (item for item in resolution.candidates if item.service_id == selected_id),
                None,
            )
            if selected is not None:
                resolution = ServiceResolution(
                    status=ResolutionStatus.RESOLVED,
                    selected_service=selected,
                    candidates=[selected],
                )
                break
            updates = {}
            if isinstance(answer.get("service_name"), str):
                updates["service_name"] = answer["service_name"]
            if isinstance(answer.get("jurisdiction"), str):
                updates["jurisdiction"] = answer["jurisdiction"]
            if updates:
                collected = {**intent.collected_information, **updates}
                missing = [field for field in intent.missing_information if field not in updates]
                intent = intent.model_copy(
                    update={**updates, "collected_information": collected, "missing_information": missing}
                )
                resolution = dependencies.service_resolver.resolve(intent)
        selected_service = resolution.selected_service
        collected = {
            **intent.collected_information,
            "service_name": selected_service.name,
            "jurisdiction": selected_service.jurisdiction,
        }
        intent = intent.model_copy(
            update={
                "service_name": selected_service.name,
                "jurisdiction": selected_service.jurisdiction,
                "collected_information": collected,
                "missing_information": [
                    field for field in intent.missing_information
                    if field not in {"service_name", "jurisdiction"}
                ],
            }
        )
        events = _event(
            state,
            AgentEventType.SERVICE_RESOLVED,
            {"service_id": selected_service.service_id, "verification_status": selected_service.verification_status.value},
        )
        return {"intent": intent, "service_resolution": resolution, "selected_service": selected_service, "events": events}

    async def retrieve_sources(state: CivicFlowState) -> dict[str, Any]:
        service = state["selected_service"]
        if dependencies.source_retriever is None:
            chunks: list[RetrievedChunk] = []
        else:
            chunks = await _call(dependencies.source_retriever, service, state["user_request"])
        events = _event(
            state,
            AgentEventType.SOURCES_RETRIEVED,
            {"service_id": service.service_id, "source_count": len(chunks)},
        )
        return {"official_sources": chunks, "events": events}

    async def judge_retrieval(state: CivicFlowState) -> dict[str, Any]:
        chunks = state.get("official_sources", [])
        if not chunks:
            return {"retrieval_relevant": False, "retrieval_judgment": "VectorDB returned no source chunks."}
        if dependencies.source_relevance_judge is None:
            return {
                "retrieval_relevant": any(
                    chunk.verification_status.value == "verified" for chunk in chunks
                ),
                "retrieval_judgment": "Fallback check: only the presence of verified matching-service chunks was checked.",
            }
        try:
            judge_kwargs = {}
            if _accepts_keyword(dependencies.source_relevance_judge, "memory"):
                judge_kwargs["memory"] = state.get("layer_context", {}).get("knowledge", {})
            judgment = await _call(
                dependencies.source_relevance_judge,
                state["user_request"],
                state["selected_service"],
                chunks,
                **judge_kwargs,
            )
        except Exception:
            return {"retrieval_relevant": False, "retrieval_judgment": "The relevance judge was unavailable."}
        if isinstance(judgment, dict):
            return {
                "retrieval_relevant": bool(judgment.get("relevant")),
                "retrieval_judgment": str(judgment.get("reason", "")),
            }
        return {"retrieval_relevant": bool(judgment), "retrieval_judgment": "LLM relevance judgment completed."}

    async def web_search_fallback(state: CivicFlowState) -> dict[str, Any]:
        if state.get("retrieval_relevant") or dependencies.web_search is None:
            return {}
        try:
            results = await _call(
                dependencies.web_search,
                state["user_request"],
                state["selected_service"],
            )
        except Exception:
            return {"retrieval_judgment": "Official web search was unavailable; using available curated context only."}
        chunks = [item for item in results if isinstance(item, RetrievedChunk)] if isinstance(results, list) else []
        if not chunks:
            chunks = list(state.get("official_sources", []))
        return {"official_sources": chunks}

    async def answer_eligibility_information(state: CivicFlowState) -> dict[str, Any]:
        service = state["selected_service"]
        requirements = state.get("requirements")
        chunks = state.get("official_sources", [])
        rules = list(requirements.eligibility_rules) if requirements else []
        text = ""
        if dependencies.source_relevance_judge is not None and chunks:
            # The configured structured LLM judge may also produce a grounded concise answer.
            try:
                judge_kwargs = {"answer": True}
                if _accepts_keyword(dependencies.source_relevance_judge, "memory"):
                    judge_kwargs["memory"] = state.get("layer_context", {}).get("knowledge", {})
                answer = await _call(
                    dependencies.source_relevance_judge,
                    state["user_request"],
                    service,
                    chunks,
                    **judge_kwargs,
                )
                if isinstance(answer, dict):
                    text = str(answer.get("answer", ""))
            except Exception:
                text = ""
        if not text and rules:
            criteria = [f"{rule.field.replace('_', ' ')} {rule.operator.value.replace('_', ' ')} {rule.value}" for rule in rules]
            text = f"The available sourced eligibility criteria for {service.name} are: " + "; ".join(criteria) + "."
        if not text:
            text = (
                f"I found information for {service.name} in {service.jurisdiction}, but the available source "
                "does not contain scheme-specific eligibility criteria. For scholarships, eligibility varies "
                "by the exact scheme. Share the scholarship name if you have it, or I can help find the matching scheme."
            )
        citations = []
        seen_urls: set[str] = set()
        for chunk in chunks:
            url = str(chunk.source_url)
            if url not in seen_urls and chunk.verification_status.value == "verified":
                citations.append({"title": chunk.source_title, "url": url})
                seen_urls.add(url)
        if citations:
            text += "\n\nSources: " + " ".join(f"{item['title']}: {item['url']}" for item in citations)
        events = _event(state, AgentEventType.TASK_COMPLETED, {"intent": "eligibility_information_answered", "citation_count": len(citations)})
        return {"informational_answer": text, "final_summary": text, "events": events, "task_status": TaskStatus.COMPLETED}

    async def extract_requirements(state: CivicFlowState) -> dict[str, Any]:
        service = state["selected_service"]
        chunks = state.get("official_sources", [])
        if dependencies.requirement_extractor is not None:
            requirements = await dependencies.requirement_extractor.extract(
                service_id=service.service_id,
                chunks=chunks,
            )
        else:
            requirements = ServiceRequirements(
                service_id=service.service_id,
                uncertainties=["No requirement extraction provider is configured."],
            )
        events = _event(
            state,
            AgentEventType.REQUIREMENTS_EXTRACTED,
            {"service_id": service.service_id, "rule_count": len(requirements.eligibility_rules), "document_count": len(requirements.required_documents)},
        )
        return {"requirements": requirements, "events": events}

    async def load_profile(state: CivicFlowState) -> dict[str, Any]:
        profile = dict(state.get("applicant_profile", {}))
        if dependencies.profile_loader is not None:
            loaded = await _call(dependencies.profile_loader, state["user_id"])
            if isinstance(loaded, dict):
                profile.update(loaded)
        return {"applicant_profile": profile}

    async def evaluate_eligibility(state: CivicFlowState) -> dict[str, Any]:
        result = eligibility_engine.evaluate_requirements(
            state["requirements"],
            state.get("applicant_profile", {}),
        )
        events = _event(
            state,
            AgentEventType.ELIGIBILITY_COMPLETED,
            {"status": result.status.value, "passed_count": len(result.passed_rules), "failed_count": len(result.failed_rules)},
        )
        return {"eligibility_result": result, "events": events}

    async def analyze_documents(state: CivicFlowState) -> dict[str, Any]:
        documents = list(state.get("applicant_documents", []))
        fields = list(state.get("extracted_document_fields", []))
        if dependencies.document_analyzer is not None:
            analyzed = await _call(
                dependencies.document_analyzer,
                state.get("user_id", ""),
                documents,
                state.get("applicant_profile", {}),
            )
            if isinstance(analyzed, tuple) and len(analyzed) == 2:
                documents, fields = list(analyzed[0]), list(analyzed[1])
        events = _event(
            state,
            AgentEventType.DOCUMENTS_VALIDATED,
            {"document_count": len(documents), "extracted_field_count": len(fields)},
        )
        return {"applicant_documents": documents, "extracted_document_fields": fields, "events": events}

    def find_missing_information(state: CivicFlowState) -> dict[str, Any]:
        missing: list[str] = []
        for name in state["intent"].missing_information:
            if name not in missing:
                missing.append(name)
        if state["intent"].intent in {IntentType.APPLY_FOR_SERVICE, IntentType.CHECK_ELIGIBILITY}:
            for name in state["eligibility_result"].missing_fields:
                if name != "eligibility_rules" and name not in missing:
                    missing.append(name)
        present_types = {
            document.document_type.casefold().strip()
            for document in state.get("applicant_documents", [])
            if document.document_type and document.status.value in {"processed", "needs_review", "uploaded"}
        }
        for required in state["requirements"].required_documents if state["intent"].intent is IntentType.APPLY_FOR_SERVICE else []:
            accepted = {value.casefold().strip() for value in required.acceptable_types}
            accepted.add(required.document_type.casefold().strip())
            if required.mandatory and not (accepted & present_types):
                request = f"document:{required.document_type}"
                if request not in missing:
                    missing.append(request)
        events = list(state.get("events", []))
        if missing:
            events = _event(state, AgentEventType.INFORMATION_REQUIRED, {"items": missing})
        blocking_missing = [field for field in missing if not field.startswith("document:")]
        return {"missing_information": missing, "blocking_missing_information": blocking_missing, "events": events}

    async def collect_missing_information(state: CivicFlowState) -> dict[str, Any]:
        missing = list(state.get("blocking_missing_information", []))
        next_field = missing[0] if missing else None
        answer = interrupt(
            {
                "type": "information.required",
                "items": [next_field] if next_field else [],
                "question": _question_for_missing_field(next_field) if next_field else "What information can you provide?",
                "message": "I will save this in the current workflow and ask for any other detail separately. Authentication secrets are not accepted.",
            }
        )
        if not isinstance(answer, dict):
            return {"task_status": TaskStatus.WAITING_FOR_USER}
        requested = set(state.get("missing_information", []))
        profile = dict(state.get("applicant_profile", {}))
        errors = list(state.get("validation_errors", []))
        intent = state["intent"]
        collected = dict(intent.collected_information)
        supplied_fields: set[str] = set()
        for field_name, value in answer.items():
            if field_name not in requested or field_name.startswith("document:"):
                continue
            if _is_sensitive_field(field_name):
                errors.append(f"Sensitive authentication field '{field_name}' cannot be stored by the agent.")
                continue
            if field_name in {"service_name", "jurisdiction"}:
                intent = intent.model_copy(update={field_name: value})
            else:
                _set_profile_value(profile, field_name, value)
            collected[field_name] = value
            supplied_fields.add(field_name)
        intent = intent.model_copy(
            update={
                "collected_information": collected,
                "missing_information": [
                    field for field in intent.missing_information if field not in supplied_fields
                ]
            }
        )
        events = _event(state, AgentEventType.TASK_RESUMED, {"provided_fields": [key for key in answer if key in requested]})
        return {"intent": intent, "applicant_profile": profile, "validation_errors": errors, "task_status": TaskStatus.RUNNING, "events": events}

    def create_plan(state: CivicFlowState) -> dict[str, Any]:
        planner_result = dependencies.planner.create(
            PlannerInput(
                service=state["selected_service"],
                requirements=state["requirements"],
                eligibility_result=(
                    state["eligibility_result"]
                    if state["intent"].intent in {IntentType.APPLY_FOR_SERVICE, IntentType.CHECK_ELIGIBILITY}
                    else None
                ),
                browser_observation=state.get("browser_observation"),
            )
        )
        events = _event(
            state,
            AgentEventType.PLAN_CREATED,
            {"service_id": state["selected_service"].service_id, "step_count": len(planner_result.plan.steps)},
        )
        return {"execution_plan": planner_result, "events": events}

    async def prepare_browser(state: CivicFlowState) -> dict[str, Any]:
        service = state["selected_service"]
        intent = state["intent"]
        if not intent.requires_browser:
            return {"browser_ready": False}
        if (
            dependencies.browser_client is None
            or service.official_portal is None
            or service.verification_status.value != "verified"
        ):
            return {"browser_ready": False, "task_status": TaskStatus.WAITING_FOR_USER}
        try:
            browser_session = await dependencies.browser_client.create_session(
                BrowserSessionCreate(
                    task_id=state["task_id"],
                    start_url=service.official_portal,
                    viewport={"width": 1280, "height": 800},
                )
            )
        except Exception:
            return {"browser_ready": False, "task_status": TaskStatus.FAILED, "errors": ["Browser session could not be created safely."]}
        events = _event(
            state,
            AgentEventType.BROWSER_SESSION_CREATED,
            {"session_id": browser_session.session_id},
        )
        return {"browser_session_id": browser_session.session_id, "browser_ready": True, "events": events}

    async def observe_browser(state: CivicFlowState) -> dict[str, Any]:
        if dependencies.browser_client is None or not state.get("browser_session_id"):
            return {}
        try:
            observation = await dependencies.browser_client.observe(state["browser_session_id"])
        except Exception:
            return {"task_status": TaskStatus.FAILED, "errors": ["Browser observation failed safely."]}
        events = _event(
            state,
            AgentEventType.BROWSER_OBSERVATION_UPDATED,
            {"observation_id": observation.observation_id, "page_state": observation.page.state.value},
        )
        return {"browser_observation": observation, "events": events}

    async def manual_control_gate(state: CivicFlowState) -> dict[str, Any]:
        observation = state.get("browser_observation")
        if observation is None or observation.page.state not in {
            PageState.AUTHENTICATION_REQUIRED,
            PageState.CAPTCHA_DETECTED,
        }:
            return {"manual_intervention_required": False}
        if dependencies.browser_client is None:
            return {"task_status": TaskStatus.FAILED, "errors": ["Manual browser control is unavailable."]}
        await dependencies.browser_client.set_control_mode(
            state["browser_session_id"],
            ControlModeRequest(control_mode=ControlMode.USER),
        )
        events = _event(
            state,
            AgentEventType.TASK_PAUSED,
            {"reason": observation.page.state.value, "session_id": state["browser_session_id"]},
        )
        resume = interrupt(
            {
                "type": "browser.user_intervention_required",
                "session_id": state["browser_session_id"],
                "page_state": observation.page.state.value,
                "screenshot_url": observation.screenshot_url,
            }
        )
        if resume is not None:
            await dependencies.browser_client.set_control_mode(
                state["browser_session_id"],
                ControlModeRequest(control_mode=ControlMode.AGENT),
            )
            events = _event(state, AgentEventType.TASK_RESUMED, {"session_id": state["browser_session_id"]})
            fresh = await dependencies.browser_client.observe(state["browser_session_id"])
            return {"browser_observation": fresh, "manual_intervention_required": fresh.page.state in {PageState.AUTHENTICATION_REQUIRED, PageState.CAPTCHA_DETECTED}, "events": events, "task_status": TaskStatus.RUNNING}
        return {"manual_intervention_required": True, "task_status": TaskStatus.WAITING_FOR_USER, "events": events}

    async def approval_gate(state: CivicFlowState) -> dict[str, Any]:
        approval_id = state.get("approval_id")
        if not approval_id:
            return {"approval_status": "not_required"}
        if dependencies.approval_status_reader is None:
            return {"approval_status": "unavailable", "task_status": TaskStatus.FAILED, "errors": ["Approval status could not be checked independently."]}
        status_value = await _call(dependencies.approval_status_reader, approval_id)
        status_text = getattr(status_value, "value", status_value)
        if status_text == "pending":
            interrupt({"type": "approval.required", "approval_id": approval_id})
            status_value = await _call(dependencies.approval_status_reader, approval_id)
            status_text = getattr(status_value, "value", status_value)
        events = _event(state, AgentEventType.APPROVAL_REQUIRED, {"approval_id": approval_id, "status": str(status_text)})
        if status_text != "approved":
            return {"approval_status": str(status_text), "task_status": TaskStatus.WAITING_FOR_APPROVAL if status_text == "pending" else TaskStatus.PAUSED, "events": events}
        return {"approval_status": "approved", "events": events}

    async def propose_action(state: CivicFlowState) -> dict[str, Any]:
        if dependencies.action_proposer is None or dependencies.browser_client is None:
            return {"action_queue_done": True}
        if len(state.get("action_history", [])) >= dependencies.max_browser_actions:
            return {"task_status": TaskStatus.PAUSED, "action_queue_done": True, "errors": ["Browser action limit reached; human review is required."]}
        try:
            proposed = await dependencies.action_proposer(state)
        except Exception:
            return {"task_status": TaskStatus.FAILED, "errors": ["Browser action proposal failed safely."], "action_queue_done": True}
        if proposed is None:
            return {"action_queue_done": True}
        return {"proposed_action": proposed, "action_queue_done": False}

    async def execute_browser_action(state: CivicFlowState) -> dict[str, Any]:
        client = dependencies.browser_client
        action = state.get("proposed_action")
        observation = state.get("browser_observation")
        if client is None or action is None or observation is None:
            return {"task_status": TaskStatus.FAILED, "errors": ["Browser action prerequisites are unavailable."]}
        events = _event(
            state,
            AgentEventType.BROWSER_ACTION_STARTED,
            {"action_id": action.action_id, "action_type": action.action.type},
        )
        try:
            result = await client.execute_action(state["browser_session_id"], action)
        except Exception:
            return {"task_status": TaskStatus.FAILED, "errors": ["Browser action failed safely."], "events": events}
        history = list(state.get("action_history", [])) + [result]
        events = _event(state, AgentEventType.BROWSER_ACTION_COMPLETED, {"action_id": result.action_id, "status": result.status})
        if result.status != "succeeded":
            return {"browser_result": result, "action_history": history, "events": events, "task_status": TaskStatus.PAUSED, "errors": [f"Browser action stopped with status '{result.status}'."]}
        return {"browser_result": result, "action_history": history, "events": events}

    async def verify_browser_action(state: CivicFlowState) -> dict[str, Any]:
        client = dependencies.browser_client
        action = state.get("proposed_action")
        previous = state.get("browser_observation")
        result = state.get("browser_result")
        if client is None or action is None or previous is None or result is None:
            return {"task_status": TaskStatus.FAILED, "errors": ["Browser action could not be verified."]}
        try:
            updated = await client.observe(state["browser_session_id"])
            verified = (
                await _call(dependencies.action_verifier, action, previous, updated)
                if dependencies.action_verifier is not None
                else False
            )
        except Exception:
            return {"task_status": TaskStatus.PAUSED, "errors": ["Action outcome could not be verified; human review is required."]}
        if not verified:
            return {"browser_observation": updated, "task_status": TaskStatus.PAUSED, "errors": ["Action outcome was not verified; no blind retry was attempted."]}
        events = _event(state, AgentEventType.BROWSER_OBSERVATION_UPDATED, {"observation_id": updated.observation_id, "verified_action_id": action.action_id})
        return {"browser_observation": updated, "proposed_action": None, "browser_result": None, "events": events, "task_status": TaskStatus.RUNNING}

    def create_summary(state: CivicFlowState) -> dict[str, Any]:
        current_status = state.get("task_status", TaskStatus.RUNNING)
        intent = state.get("intent")
        if intent and intent.intent is IntentType.CASUAL_CONVERSATION:
            request = state.get("user_request", "").casefold()
            if "thank" in request:
                summary = "You’re welcome! I can help you understand public-service requirements whenever you need."
            elif any(word in request for word in ("bye", "goodbye")):
                summary = "Goodbye! I’ll be here when you need help with a public service."
            elif "how are you" in request:
                summary = "I’m ready to help. Tell me which public service, portal, or application you want to understand."
            else:
                summary = "Hello! Tell me which public service or application you need help with, and include the jurisdiction if you know it."
            events = _event(state, AgentEventType.TASK_COMPLETED, {"status": TaskStatus.COMPLETED.value})
            return {"final_summary": summary, "task_status": TaskStatus.COMPLETED, "events": events}
        if intent and intent.intent is IntentType.OUT_OF_SCOPE:
            summary = (
                "I can help with public-service forms, schemes, eligibility, documents, "
                "and application preparation. I can’t help with that request, but we can "
                "still chat. Tell me what you need whenever you’re ready."
            )
            events = _event(state, AgentEventType.TASK_COMPLETED, {"status": TaskStatus.COMPLETED.value})
            return {"final_summary": summary, "task_status": TaskStatus.COMPLETED, "events": events}
        service = state.get("selected_service")
        service_label = service.name if service is not None else "the requested service"
        if state.get("errors"):
            summary = f"I stopped safely while preparing {service_label}. {state['errors'][-1]}"
        elif current_status in {TaskStatus.WAITING_FOR_USER, TaskStatus.WAITING_FOR_APPROVAL}:
            summary = f"I prepared a plan for {service_label}, but it needs your information or verification before continuing. No application was submitted."
        elif current_status is TaskStatus.PAUSED:
            summary = f"I paused {service_label} because the next outcome could not be verified. Please review the browser and plan."
        else:
            eligibility = state.get("eligibility_result")
            eligibility_line = (
                f" Eligibility status: {eligibility.status.value}."
                if eligibility and state.get("intent") and state["intent"].intent in {IntentType.APPLY_FOR_SERVICE, IntentType.CHECK_ELIGIBILITY}
                else ""
            )
            summary = f"The preparation workflow for {service_label} is complete.{eligibility_line} No final application was submitted automatically."
            if state.get("requirements") and state["requirements"].uncertainties:
                summary += " Some requirements need review against the linked official sources."
            current_status = TaskStatus.COMPLETED
        events = _event(
            state,
            AgentEventType.TASK_COMPLETED if current_status is TaskStatus.COMPLETED else AgentEventType.TASK_FAILED if current_status is TaskStatus.FAILED else AgentEventType.TASK_PAUSED,
            {"status": current_status.value},
        )
        return {"final_summary": summary, "task_status": current_status, "events": events}

    def route_after_missing(state: CivicFlowState) -> str:
        return "collect_missing" if state.get("blocking_missing_information") else "plan"

    def route_after_browser_prepare(state: CivicFlowState) -> str:
        return "observe_browser" if state.get("browser_ready") else "summary"

    def route_after_manual(state: CivicFlowState) -> str:
        if state.get("task_status") is TaskStatus.FAILED:
            return "summary"
        if state.get("manual_intervention_required"):
            return "summary"
        return "approval_gate"

    def route_after_approval(state: CivicFlowState) -> str:
        if state.get("approval_status") == "approved":
            return "propose_action"
        if state.get("approval_status") == "not_required":
            return "propose_action"
        return "summary"

    def route_after_proposal(state: CivicFlowState) -> str:
        if state.get("task_status") is TaskStatus.FAILED or state.get("action_queue_done"):
            return "summary"
        return "execute_action"

    def route_after_action(state: CivicFlowState) -> str:
        if state.get("task_status") in {TaskStatus.PAUSED, TaskStatus.FAILED}:
            return "summary"
        return "verify_action"

    def route_after_verification(state: CivicFlowState) -> str:
        if state.get("task_status") is TaskStatus.RUNNING:
            return "observe_browser"
        return "summary"

    builder = StateGraph(CivicFlowState)
    builder.add_node("intent", extract_intent)
    builder.add_node("service", resolve_service)
    builder.add_node("retrieve_sources", retrieve_sources)
    builder.add_node("judge_retrieval", judge_retrieval)
    builder.add_node("web_search_fallback", web_search_fallback)
    builder.add_node("eligibility_information", answer_eligibility_information)
    builder.add_node("requirements", extract_requirements)
    builder.add_node("profile", load_profile)
    builder.add_node("eligibility", evaluate_eligibility)
    builder.add_node("documents", analyze_documents)
    builder.add_node("missing", find_missing_information)
    builder.add_node("collect_missing", collect_missing_information)
    builder.add_node("plan", create_plan)
    builder.add_node("prepare_browser", prepare_browser)
    builder.add_node("observe_browser", observe_browser)
    builder.add_node("manual_gate", manual_control_gate)
    builder.add_node("approval_gate", approval_gate)
    builder.add_node("propose_action", propose_action)
    builder.add_node("execute_action", execute_browser_action)
    builder.add_node("verify_action", verify_browser_action)
    builder.add_node("summary", create_summary)

    builder.add_edge(START, "intent")
    def route_after_intent(state: CivicFlowState) -> str:
        return "summary" if state["intent"].intent in {IntentType.CASUAL_CONVERSATION, IntentType.OUT_OF_SCOPE} else "service"

    def route_after_retrieval(state: CivicFlowState) -> str:
        return "judge_retrieval" if state["intent"].intent is IntentType.CHECK_ELIGIBILITY else "requirements"

    def route_after_requirements(state: CivicFlowState) -> str:
        if state["intent"].intent is IntentType.CHECK_ELIGIBILITY and not state["intent"].eligibility_is_personal:
            return "eligibility_information"
        return "profile"

    builder.add_conditional_edges("intent", route_after_intent, {"summary": "summary", "service": "service"})
    builder.add_edge("service", "retrieve_sources")
    builder.add_conditional_edges("retrieve_sources", route_after_retrieval, {"judge_retrieval": "judge_retrieval", "requirements": "requirements"})
    builder.add_edge("judge_retrieval", "web_search_fallback")
    builder.add_edge("web_search_fallback", "requirements")
    builder.add_conditional_edges("requirements", route_after_requirements, {"eligibility_information": "eligibility_information", "profile": "profile"})
    builder.add_edge("eligibility_information", END)
    builder.add_edge("profile", "eligibility")
    builder.add_edge("eligibility", "documents")
    builder.add_edge("documents", "missing")
    builder.add_conditional_edges("missing", route_after_missing, {"collect_missing": "collect_missing", "plan": "plan"})
    builder.add_edge("collect_missing", "eligibility")
    builder.add_edge("plan", "prepare_browser")
    builder.add_conditional_edges("prepare_browser", route_after_browser_prepare, {"observe_browser": "observe_browser", "summary": "summary"})
    builder.add_edge("observe_browser", "manual_gate")
    builder.add_conditional_edges(
        "manual_gate",
        route_after_manual,
        {"summary": "summary", "approval_gate": "approval_gate"},
    )
    builder.add_conditional_edges(
        "approval_gate",
        route_after_approval,
        {"propose_action": "propose_action", "summary": "summary"},
    )
    builder.add_conditional_edges(
        "propose_action",
        route_after_proposal,
        {"summary": "summary", "execute_action": "execute_action"},
    )
    builder.add_conditional_edges(
        "execute_action",
        route_after_action,
        {"summary": "summary", "verify_action": "verify_action"},
    )
    builder.add_conditional_edges(
        "verify_action",
        route_after_verification,
        {"summary": "summary", "observe_browser": "observe_browser"},
    )
    builder.add_edge("summary", END)
    return builder.compile(checkpointer=checkpointer or MemorySaver(serde=WorkflowSerializer()))


async def run_task(graph, inputs: CivicFlowState, *, task_id: str) -> CivicFlowState:
    if not task_id:
        raise ValueError("task_id is required for checkpointed workflows")
    payload = dict(inputs)
    payload["task_id"] = task_id
    payload.setdefault("task_status", TaskStatus.RUNNING)
    payload.setdefault("events", [])
    payload.setdefault("errors", [])
    payload.setdefault("action_history", [])
    return await graph.ainvoke(payload, {"configurable": {"thread_id": task_id}})


async def resume_task(graph, *, task_id: str, resume_value: Any) -> CivicFlowState:
    return await graph.ainvoke(
        Command(resume=resume_value),
        {"configurable": {"thread_id": task_id}},
    )
