from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.app.agent.schemas.agent_events import AgentEvent, AgentEventType
from backend.app.agent.schemas.approval import ApprovalRequest, ApprovalStatus
from backend.app.agent.schemas.documents import DocumentMetadata, DocumentStatus, ExtractedField, SourceLocation
from backend.app.agent.schemas.eligibility import EligibilityResult, EligibilityStatus
from backend.app.agent.schemas.intent import Intent, IntentType
from backend.app.agent.schemas.planner import ExecutionPlan, PlanStep, PlanStepType
from backend.app.agent.schemas.requirements import ServiceRequirements
from backend.app.agent.schemas.service import ServiceCategory, ServiceRecord
from backend.app.agent.schemas.task import Task, TaskStatus
from backend.app.agent.schemas.browser import BrowserSessionCreate as AgentBrowserSessionCreate
from browser_worker.app.contracts import BrowserSessionCreate as WorkerBrowserSessionCreate
from civicflow_contracts import BrowserSessionCreate as SharedBrowserSessionCreate, Viewport


def test_intent_rejects_unknown_enum_value() -> None:
    with pytest.raises(ValidationError):
        Intent(
            intent="guessing",
            goal="apply",
            requires_browser=True,
        )


def test_service_and_requirements_models_validate() -> None:
    service = ServiceRecord(
        service_id="sample_certificate",
        name="Sample Certificate",
        category=ServiceCategory.CERTIFICATE,
        jurisdiction="Example State",
    )
    requirements = ServiceRequirements(service_id=service.service_id)
    assert requirements.service_id == service.service_id


def test_eligibility_document_plan_task_and_approval_models_validate() -> None:
    now = datetime.now(UTC)
    result = EligibilityResult(status=EligibilityStatus.INSUFFICIENT_INFORMATION)
    metadata = DocumentMetadata(
        document_id="doc-1",
        owner_id="user-1",
        filename="proof.pdf",
        media_type="application/pdf",
        size_bytes=42,
        status=DocumentStatus.PROCESSED,
    )
    field = ExtractedField(
        name="full_name",
        value="Example Citizen",
        confidence=0.99,
        source_document_id=metadata.document_id,
        source_location=SourceLocation(page_number=1),
    )
    plan = ExecutionPlan(
        service_id="sample_certificate",
        steps=[PlanStep(step_id="step-1", description="Review details", type=PlanStepType.INFORMATION)],
    )
    task = Task(task_id="task-1", user_id="user-1", user_request="Help me apply", created_at=now)
    approval = ApprovalRequest(
        approval_id="approval-1",
        task_id=task.task_id,
        action_type="review",
        description="Review this action",
        requested_at=now,
        status=ApprovalStatus.PENDING,
    )
    event = AgentEvent(
        event_id="event-1",
        task_id=task.task_id,
        sequence=1,
        type=AgentEventType.TASK_STARTED,
        timestamp=now,
    )

    assert result.status is EligibilityStatus.INSUFFICIENT_INFORMATION
    assert field.needs_human_review is False
    assert plan.steps[0].status.value == "pending"
    assert task.status is TaskStatus.CREATED
    assert approval.status is ApprovalStatus.PENDING
    assert event.sequence == 1


def test_shared_browser_model_imports_from_both_services_and_contract_package() -> None:
    kwargs = {
        "task_id": "task-1",
        "start_url": "https://example.gov.in",
        "viewport": Viewport(width=1280, height=800),
    }
    assert SharedBrowserSessionCreate(**kwargs).task_id == "task-1"
    assert AgentBrowserSessionCreate(**kwargs).task_id == "task-1"
    assert WorkerBrowserSessionCreate(**kwargs).task_id == "task-1"


def test_task_rejects_invalid_status_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        Task(
            task_id="task-1",
            user_id="user-1",
            user_request="Apply",
            status="finished_maybe",
            created_at=datetime.now(UTC),
        )

    with pytest.raises(ValidationError):
        Intent(intent=IntentType.FIND_SERVICE, goal="Find service", requires_browser=False, extra="bad")
