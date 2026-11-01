import pytest

from backend.app.agent.schemas.eligibility import EligibilityResult, EligibilityStatus
from backend.app.agent.schemas.planner import PlannerInput, PlanStepType
from backend.app.agent.schemas.requirements import (
    ApplicationStep,
    RequiredDocument,
    ServiceRequirements,
)
from backend.app.agent.schemas.service import (
    ServiceCategory,
    ServiceRecord,
    VerificationStatus,
)
from backend.app.agent.services.task_planner import TaskPlanner
from civicflow_contracts.browser import BrowserObservation, ObservedPage, PageState


def service(
    service_id: str = "service-a",
    *,
    portal: str | None = None,
    verified: bool = False,
) -> ServiceRecord:
    return ServiceRecord(
        service_id=service_id,
        name="Example service",
        category=ServiceCategory.CERTIFICATE,
        jurisdiction="Example region",
        verification_status=(VerificationStatus.VERIFIED if verified else VerificationStatus.UNVERIFIED),
        official_portal=portal,
    )


def requirements(
    service_id: str = "service-a",
    *,
    documents: list[RequiredDocument] | None = None,
    steps: list[ApplicationStep] | None = None,
) -> ServiceRequirements:
    return ServiceRequirements(
        service_id=service_id,
        required_documents=documents or [],
        application_steps=steps or [],
    )


def test_planner_uses_service_requirements_and_varies_between_services() -> None:
    planner = TaskPlanner()
    certificate = planner.create(
        PlannerInput(
            service=service(),
            requirements=requirements(
                documents=[RequiredDocument(document_type="proof_of_address")],
                steps=[ApplicationStep(step_id="address", description="Enter address", order=1)],
            ),
        )
    )
    scholarship = planner.create(
        PlannerInput(
            service=service("service-b"),
            requirements=requirements(
                "service-b",
                documents=[RequiredDocument(document_type="transcript")],
                steps=[ApplicationStep(step_id="course", description="Enter course details", order=1)],
            ),
        )
    )
    certificate_text = " ".join(step.description for step in certificate.plan.steps)
    scholarship_text = " ".join(step.description for step in scholarship.plan.steps)
    assert "proof_of_address" in certificate_text
    assert "transcript" in scholarship_text
    assert certificate.plan.service_id != scholarship.plan.service_id


def test_unverified_portal_never_creates_automated_navigation() -> None:
    result = TaskPlanner().create(
        PlannerInput(
            service=service(portal="https://portal.example.gov.in"),
            requirements=requirements(),
        )
    )
    assert not any(step.type is PlanStepType.BROWSER_NAVIGATION for step in result.plan.steps)
    portal_check = next(step for step in result.plan.steps if step.step_id == "verify-official-portal")
    assert portal_check.type is PlanStepType.HUMAN_INTERVENTION
    assert portal_check.requires_human_approval


def test_verified_portal_allows_navigation_but_sensitive_steps_stay_with_citizen() -> None:
    result = TaskPlanner().create(
        PlannerInput(
            service=service(portal="https://portal.example.gov.in", verified=True),
            requirements=requirements(
                steps=[
                    ApplicationStep(step_id="fill", description="Enter applicant details", order=1),
                    ApplicationStep(step_id="submit", description="Submit final application", order=2),
                    ApplicationStep(step_id="pay", description="Make payment", order=3),
                ]
            ),
        )
    )
    assert any(step.type is PlanStepType.BROWSER_NAVIGATION for step in result.plan.steps)
    assert any(step.type is PlanStepType.BROWSER_FORM for step in result.plan.steps)
    protected = [step for step in result.plan.steps if step.step_id.startswith("citizen-action-")]
    assert len(protected) == 2
    assert all(step.type is PlanStepType.HUMAN_INTERVENTION for step in protected)
    assert all(step.requires_human_approval for step in protected)


def test_observed_authentication_page_requires_manual_user_intervention() -> None:
    observation = BrowserObservation(
        session_id="browser-1",
        observation_id="observation-1",
        sequence=1,
        page=ObservedPage(
            url="https://portal.example.gov.in/login",
            title="Sign in",
            state=PageState.AUTHENTICATION_REQUIRED,
        ),
        elements=[],
        screenshot_url="/api/v1/sessions/browser-1/screenshot",
    )
    result = TaskPlanner().create(
        PlannerInput(
            service=service(portal="https://portal.example.gov.in", verified=True),
            requirements=requirements(),
            browser_observation=observation.model_dump(mode="json"),
        )
    )
    assert any(step.step_id == "citizen-handle-authentication" for step in result.plan.steps)
    assert all(step.type is not PlanStepType.BROWSER_FORM for step in result.plan.steps)


def test_insufficient_eligibility_adds_human_information_step() -> None:
    result = TaskPlanner().create(
        PlannerInput(
            service=service(),
            requirements=requirements(),
            eligibility_result=EligibilityResult(
                status=EligibilityStatus.INSUFFICIENT_INFORMATION,
                missing_fields=["annual_income"],
            ),
        )
    )
    step = next(step for step in result.plan.steps if step.step_id == "resolve-eligibility-information")
    assert step.type is PlanStepType.HUMAN_INTERVENTION
    assert "annual_income" in step.description


def test_plan_ids_and_dependencies_are_stable_and_linear() -> None:
    task_input = PlannerInput(
        service=service(),
        requirements=requirements(
            documents=[RequiredDocument(document_type="identity_proof")],
            steps=[ApplicationStep(step_id="step-1", description="Fill a field", order=1)],
        ),
    )
    planner = TaskPlanner()
    first = planner.create(task_input).plan
    second = planner.create(task_input).plan
    assert [step.step_id for step in first.steps] == [step.step_id for step in second.steps]
    for index, step in enumerate(first.steps):
        expected = [] if index == 0 else [first.steps[index - 1].step_id]
        assert step.depends_on == expected


def test_planner_rejects_mismatched_service_and_requirements() -> None:
    with pytest.raises(ValueError, match="same service_id"):
        TaskPlanner().create(
            PlannerInput(service=service("a"), requirements=requirements("b"))
        )
