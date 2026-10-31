"""Deterministic validation of user-authored workflows."""

from pydantic import BaseModel, ConfigDict, Field

from browser_agent.schemas.browser_action import ActionType
from browser_agent.schemas.workflow import Workflow


class WorkflowIssue(BaseModel):
    """One actionable workflow validation issue."""

    model_config = ConfigDict(extra="forbid")

    code: str
    message: str
    step_id: str | None = None


class WorkflowValidation(BaseModel):
    """Validation report and IDs of steps that must pause for a person."""

    model_config = ConfigDict(extra="forbid")

    valid: bool
    issues: list[WorkflowIssue] = Field(default_factory=list)
    restricted_step_ids: list[str] = Field(default_factory=list)


class WorkflowValidator:
    """Check required values, supported action types, and unique step IDs."""

    SUPPORTED_ACTIONS = frozenset(ActionType.__args__)

    def validate(self, workflow: Workflow) -> WorkflowValidation:
        """Return issues without changing or reordering any supplied step."""
        issues: list[WorkflowIssue] = []
        restricted: list[str] = []
        if not workflow.steps:
            issues.append(WorkflowIssue(code="empty_workflow", message="Workflow must include at least one step."))

        seen: set[str] = set()
        for step in workflow.steps:
            if not step.step_id.strip():
                issues.append(WorkflowIssue(code="missing_step_id", message="Step ID cannot be blank.", step_id=step.step_id))
            elif step.step_id in seen:
                issues.append(WorkflowIssue(code="duplicate_step_id", message="Step IDs must be unique.", step_id=step.step_id))
            seen.add(step.step_id)
            if not step.instruction.strip():
                issues.append(WorkflowIssue(code="missing_instruction", message="Instruction cannot be blank.", step_id=step.step_id))
            if step.action_type not in self.SUPPORTED_ACTIONS:
                issues.append(WorkflowIssue(code="unsupported_action", message="Action type is not supported.", step_id=step.step_id))
            if step.action_type in {"fill", "select"} and step.value is None:
                issues.append(WorkflowIssue(code="missing_value", message=f"{step.action_type} requires an explicit value.", step_id=step.step_id))
            if step.action_type == "upload" and not step.file_path:
                issues.append(WorkflowIssue(code="missing_file_path", message="Upload requires an explicit file path.", step_id=step.step_id))
            if step.requires_confirmation:
                restricted.append(step.step_id)

        return WorkflowValidation(valid=not issues, issues=issues, restricted_step_ids=restricted)
