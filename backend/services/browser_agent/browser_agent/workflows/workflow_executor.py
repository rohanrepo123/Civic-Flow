"""Execute a single workflow step through Phase 3 and Phase 4 interfaces."""

from dataclasses import dataclass

from playwright.async_api import Page

from browser_agent.actions.action_executor import ActionExecutor
from browser_agent.grounding.element_grounder import ElementGrounder
from browser_agent.schemas.action_result import ActionResult
from browser_agent.schemas.browser_action import BrowserAction
from browser_agent.schemas.grounding import GroundingResult
from browser_agent.schemas.observation import PageSnapshot
from browser_agent.schemas.workflow_step import WorkflowStep


@dataclass(frozen=True)
class StepExecution:
    """One grounding/action attempt and its terminal classification."""

    status: str
    message: str
    grounding_result: GroundingResult | None = None
    action_result: ActionResult | None = None
    requires_human_intervention: bool = False


class WorkflowExecutor:
    """Bridge a planned step to the existing observer, grounder, and executor."""

    def __init__(self, grounder: ElementGrounder, action_executor: ActionExecutor) -> None:
        self.grounder = grounder
        self.action_executor = action_executor

    async def execute_step(
        self,
        step: WorkflowStep,
        snapshot: PageSnapshot,
        page: Page,
        action_id: str,
    ) -> StepExecution:
        """Ground one instruction, then delegate one explicit action."""
        grounding = await self.grounder.find_element(step.instruction, snapshot)
        if not grounding.success or grounding.selected_element is None:
            waiting = grounding.needs_clarification
            return StepExecution(
                status="waiting_for_user" if waiting else "failed",
                message="Grounding requires clarification." if waiting else "No grounded target was found.",
                grounding_result=grounding,
                requires_human_intervention=waiting,
            )

        action = BrowserAction(
            action_id=action_id,
            action_type=step.action_type,
            element_id=grounding.element_id,
            snapshot_id=snapshot.snapshot_id,
            value=step.value,
            file_path=step.file_path,
            requires_confirmation=step.requires_confirmation,
        )
        action_result = await self.action_executor.execute(action, grounding, snapshot, page)
        if action_result.requires_human_intervention:
            status = "waiting_for_user"
        elif action_result.success and action_result.verified:
            status = "completed"
        else:
            status = "failed"
        return StepExecution(
            status=status,
            message=action_result.message,
            grounding_result=grounding,
            action_result=action_result,
            requires_human_intervention=action_result.requires_human_intervention,
        )
