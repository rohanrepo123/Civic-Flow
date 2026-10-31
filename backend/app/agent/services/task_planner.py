import re

from backend.app.agent.schemas.planner import (
    ExecutionPlan,
    PlanStep,
    PlanStepStatus,
    PlanStepType,
    PlannerInput,
    PlannerResult,
)
from backend.app.agent.schemas.eligibility import EligibilityStatus
from backend.app.agent.schemas.service import VerificationStatus
from backend.app.agent.schemas.browser import PageState


_HUMAN_ONLY_TERMS = re.compile(
    r"\b(submit|submission|payment|pay|otp|one.time.password|captcha|password|"
    r"legal declaration|final declaration|sign|signature|authenticate|login)\b",
    re.IGNORECASE,
)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", value.casefold()).strip("-") or "item"


class TaskPlanner:
    """Create a deterministic plan from the selected service's actual data."""

    def create(self, planner_input: PlannerInput) -> PlannerResult:
        service = planner_input.service
        requirements = planner_input.requirements
        if service.service_id != requirements.service_id:
            raise ValueError("service and requirements must refer to the same service_id")

        notices: list[str] = []
        steps: list[PlanStep] = []

        def add(step_id: str, description: str, kind: PlanStepType, human: bool = False) -> None:
            dependencies = [steps[-1].step_id] if steps else []
            steps.append(
                PlanStep(
                    step_id=step_id,
                    description=description,
                    type=kind,
                    status=PlanStepStatus.PENDING,
                    depends_on=dependencies,
                    requires_human_approval=human,
                )
            )

        add("review-service-requirements", "Review the sourced service requirements", PlanStepType.INFORMATION)

        if planner_input.eligibility_result is not None:
            eligibility = planner_input.eligibility_result
            if eligibility.status is EligibilityStatus.INSUFFICIENT_INFORMATION:
                missing = ", ".join(eligibility.missing_fields) or "additional eligibility details"
                add(
                    "resolve-eligibility-information",
                    f"Provide or review missing eligibility information: {missing}",
                    PlanStepType.HUMAN_INTERVENTION,
                    human=True,
                )
            elif eligibility.status is EligibilityStatus.NOT_ELIGIBLE:
                notices.append("The supplied eligibility rules indicate one or more failed conditions.")

        seen_document_types: set[str] = set()
        for required_document in requirements.required_documents:
            normalized_type = _slug(required_document.document_type)
            if normalized_type in seen_document_types:
                continue
            seen_document_types.add(normalized_type)
            label = "Prepare" if required_document.mandatory else "Consider preparing"
            add(
                f"prepare-document-{normalized_type}",
                f"{label} the {required_document.document_type} document",
                PlanStepType.DOCUMENT_PREPARATION,
            )

        for index, uncertainty in enumerate(requirements.uncertainties, start=1):
            notices.append(uncertainty)
            add(
                f"review-requirement-uncertainty-{index:03d}",
                "Review an uncertain or unverified requirement before relying on it",
                PlanStepType.HUMAN_INTERVENTION,
                human=True,
            )

        page_state = (
            planner_input.browser_observation.page.state
            if planner_input.browser_observation is not None
            else None
        )
        if page_state in {PageState.AUTHENTICATION_REQUIRED, PageState.CAPTCHA_DETECTED}:
            label = "authentication" if page_state is PageState.AUTHENTICATION_REQUIRED else "CAPTCHA"
            add(
                f"citizen-handle-{label}",
                f"Complete the {label} step in the browser personally",
                PlanStepType.HUMAN_INTERVENTION,
                human=True,
            )
        elif page_state in {PageState.UNEXPECTED_ERROR, PageState.CLOSED}:
            add(
                "resolve-browser-state",
                "Review the browser session state before continuing",
                PlanStepType.HUMAN_INTERVENTION,
                human=True,
            )
        elif page_state is PageState.LOADING:
            add("wait-for-page-ready", "Wait until the page is ready, then observe it again", PlanStepType.INFORMATION)

        portal_is_trusted = (
            service.verification_status is VerificationStatus.VERIFIED
            and service.official_portal is not None
        )
        already_at_portal = False
        if portal_is_trusted and planner_input.browser_observation is not None:
            observed_url = planner_input.browser_observation.page.url.rstrip("/").casefold()
            portal_url = str(service.official_portal).rstrip("/").casefold()
            already_at_portal = observed_url == portal_url
        if portal_is_trusted and not already_at_portal:
            add(
                "open-verified-service-portal",
                "Open the configured, verified service portal",
                PlanStepType.BROWSER_NAVIGATION,
            )
        else:
            notices.append("No verified official portal is configured; browser navigation is not planned.")
            add(
                "verify-official-portal",
                "Confirm the official service portal before any browser interaction",
                PlanStepType.HUMAN_INTERVENTION,
                human=True,
            )

        for application_step in sorted(requirements.application_steps, key=lambda item: (item.order, item.step_id)):
            if _HUMAN_ONLY_TERMS.search(application_step.description):
                add(
                    f"citizen-action-{_slug(application_step.step_id)}",
                    f"Citizen review required: {application_step.description}",
                    PlanStepType.HUMAN_INTERVENTION,
                    human=True,
                )
            elif portal_is_trusted:
                add(
                    f"service-step-{_slug(application_step.step_id)}-{application_step.order:03d}",
                    application_step.description,
                    PlanStepType.BROWSER_FORM,
                )
            else:
                add(
                    f"review-service-step-{_slug(application_step.step_id)}",
                    f"Review the documented step: {application_step.description}",
                    PlanStepType.INFORMATION,
                )

        add("verify-outcome", "Verify the actual service outcome before reporting completion", PlanStepType.VERIFICATION)
        return PlannerResult(
            plan=ExecutionPlan(service_id=service.service_id, steps=steps),
            notices=notices,
        )
