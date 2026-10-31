"""Order-preserving planner for structured, explicitly supplied steps."""

from dataclasses import dataclass
import re

from browser_agent.schemas.workflow import Workflow
from browser_agent.schemas.workflow_step import WorkflowStep
from browser_agent.workflows.workflow_validator import WorkflowIssue, WorkflowValidation, WorkflowValidator

_RESTRICTED = re.compile(
    r"submit|finali[sz]e|file application|payment|\bpay\b|checkout|purchase|"
    r"consent|declaration|certify|agree|accept|\bterms\b|captcha|\botp\b|one.?time.?code|"
    r"log.?in|sign.?in|password|credential|delete|withdraw|revoke|authorize",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class WorkflowPlan:
    """Validated steps in the original requested order plus pause points."""

    valid: bool
    ordered_steps: tuple[WorkflowStep, ...]
    restricted_step_ids: tuple[str, ...]
    issues: tuple[WorkflowIssue, ...]


class WorkflowPlanner:
    """Validate structured steps and mark risky actions for user checkpoints."""

    def __init__(self, validator: WorkflowValidator | None = None) -> None:
        self.validator = validator or WorkflowValidator()

    def plan(self, workflow: Workflow) -> WorkflowPlan:
        """Preserve user order; never infer a new action or value."""
        validation: WorkflowValidation = self.validator.validate(workflow)
        restricted = set(validation.restricted_step_ids)
        for step in workflow.steps:
            context = f"{step.instruction} {step.expected_result or ''}"
            if _RESTRICTED.search(context):
                restricted.add(step.step_id)
        ordered = tuple(workflow.steps)
        return WorkflowPlan(
            valid=validation.valid,
            ordered_steps=ordered,
            restricted_step_ids=tuple(step.step_id for step in ordered if step.step_id in restricted),
            issues=tuple(validation.issues),
        )
