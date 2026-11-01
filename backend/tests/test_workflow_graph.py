import asyncio

from backend.app.agent.graph import WorkflowDependencies, create_civicflow_graph, resume_task, run_task
from backend.app.agent.schemas.intent import Intent, IntentType
from backend.app.agent.schemas.service import ServiceCategory, ServiceRecord, VerificationStatus
from backend.app.agent.services.service_registry import ServiceRegistry
from backend.app.agent.services.service_resolver import ServiceResolver
from backend.app.agent.schemas.task import TaskStatus
from backend.app.agent.mocks.mock_browser import MockBrowserClient, MockPage


class FixedIntentExtractor:
    def __init__(self, intent: Intent) -> None:
        self.intent = intent

    async def extract(self, user_request: str) -> Intent:
        return self.intent


def _service(service_id: str, name: str) -> ServiceRecord:
    return ServiceRecord(
        service_id=service_id,
        name=name,
        category=ServiceCategory.CERTIFICATE,
        jurisdiction="Maharashtra",
        aliases=["certificate"],
    )


def _intent(**updates) -> Intent:
    values = {
        "intent": IntentType.GET_INFORMATION,
        "service_category": ServiceCategory.CERTIFICATE,
        "service_name": "certificate",
        "jurisdiction": "Maharashtra",
        "goal": "get_information",
        "requires_browser": False,
    }
    values.update(updates)
    return Intent(**values)


def _graph(intent: Intent, services: list[ServiceRecord]):
    return create_civicflow_graph(
        WorkflowDependencies(
            intent_extractor=FixedIntentExtractor(intent),
            service_resolver=ServiceResolver(ServiceRegistry(services)),
        )
    )


def test_graph_runs_to_verifiedly_labeled_preparation_completion():
    graph = _graph(_intent(), [_service("certificate_mh", "Certificate")])
    result = asyncio.run(run_task(graph, {"user_id": "user-1", "user_request": "Tell me about the certificate"}, task_id="task-complete"))

    assert result["task_status"] is TaskStatus.COMPLETED
    assert "does not provide enough verified detail" in result["final_summary"]
    assert "applicant_profile" not in result
    assert result["events"][-1].type.value == "task.completed"


def test_out_of_scope_request_finishes_with_a_safe_conversational_response():
    graph = _graph(_intent(intent=IntentType.OUT_OF_SCOPE, goal="out_of_scope", requires_browser=False), [])
    result = asyncio.run(run_task(graph, {"user_id": "user-1", "user_request": "Tell me a joke"}, task_id="task-out-of-scope"))

    assert result["task_status"] is TaskStatus.COMPLETED
    assert "can’t help with that request" in result["final_summary"]
    assert result["events"][-1].type.value == "task.completed"


def test_missing_information_interrupt_can_resume():
    graph = _graph(_intent(intent=IntentType.APPLY_FOR_SERVICE, missing_information=["age"]), [_service("certificate_mh", "Certificate")])
    initial = asyncio.run(run_task(graph, {"user_id": "user-1", "user_request": "Help with certificate"}, task_id="task-resume"))

    assert initial["__interrupt__"][0].value["type"] == "information.required"
    resumed = asyncio.run(resume_task(graph, task_id="task-resume", resume_value={"age": 28}))

    assert resumed["task_status"] is TaskStatus.COMPLETED
    assert resumed["applicant_profile"]["age"] == 28
    assert not resumed["intent"].missing_information


def test_ambiguous_service_pauses_for_selection_then_resumes():
    intent = _intent(service_name=None, jurisdiction="Maharashtra")
    graph = _graph(intent, [_service("birth_certificate", "Birth Certificate"), _service("domicile_certificate", "Domicile Certificate")])
    initial = asyncio.run(run_task(graph, {"user_id": "user-1", "user_request": "Find a certificate"}, task_id="task-clarify"))

    interrupt = initial["__interrupt__"][0].value
    assert interrupt["type"] == "service.clarification_required"
    selected_id = interrupt["candidates"][1]["service_id"]
    resumed = asyncio.run(resume_task(graph, task_id="task-clarify", resume_value={"service_id": selected_id}))

    assert resumed["selected_service"].service_id == selected_id
    assert resumed["task_status"] is TaskStatus.COMPLETED


def test_approval_is_rechecked_independently_after_resume():
    service_data = _service("certificate_mh", "Certificate").model_dump(mode="json")
    service_data.update(verification_status=VerificationStatus.VERIFIED.value, official_portal="https://portal.example.test/start")
    service = ServiceRecord.model_validate(service_data)
    browser = MockBrowserClient(
        {"https://portal.example.test/start": MockPage("https://portal.example.test/start", "Test portal")},
        approved_domains={"portal.example.test"},
    )
    approval = {"status": "pending", "reads": 0}

    def read_approval(_: str) -> str:
        approval["reads"] += 1
        return approval["status"]

    graph = create_civicflow_graph(
        WorkflowDependencies(
            intent_extractor=FixedIntentExtractor(_intent(intent=IntentType.APPLY_FOR_SERVICE, requires_browser=True)),
            service_resolver=ServiceResolver(ServiceRegistry([service])),
            browser_client=browser,
            approval_status_reader=read_approval,
        )
    )
    initial = asyncio.run(run_task(graph, {"user_id": "user-1", "user_request": "Apply for a certificate", "approval_id": "approval-1"}, task_id="task-approval"))
    assert initial["__interrupt__"][0].value["type"] == "approval.required"
    approval["status"] = "approved"
    resumed = asyncio.run(resume_task(graph, task_id="task-approval", resume_value={}))

    assert approval["reads"] == 2
    assert resumed["approval_status"] == "approved"
    assert resumed["task_status"] is TaskStatus.COMPLETED


def test_browser_observation_failure_is_reported_without_claiming_success():
    service_data = _service("certificate_mh", "Certificate").model_dump(mode="json")
    service_data.update(verification_status="verified", official_portal="https://portal.example.test/start")
    service = ServiceRecord.model_validate(service_data)

    class BrokenBrowser(MockBrowserClient):
        async def observe(self, session_id: str):
            raise RuntimeError("worker unavailable")

    browser = BrokenBrowser(
        {"https://portal.example.test/start": MockPage("https://portal.example.test/start", "Test portal")},
        approved_domains={"portal.example.test"},
    )
    graph = create_civicflow_graph(
        WorkflowDependencies(
            intent_extractor=FixedIntentExtractor(_intent(intent=IntentType.APPLY_FOR_SERVICE, requires_browser=True)),
            service_resolver=ServiceResolver(ServiceRegistry([service])),
            browser_client=browser,
        )
    )

    result = asyncio.run(run_task(graph, {"user_id": "user-1", "user_request": "Apply for a certificate"}, task_id="task-browser-failure"))
    assert result["task_status"] is TaskStatus.FAILED
    assert "Browser observation failed safely." in result["errors"]
    assert result["final_summary"].startswith("I stopped safely")
