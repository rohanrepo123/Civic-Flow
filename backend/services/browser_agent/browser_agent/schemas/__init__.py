"""Shared Pydantic schemas for the browser agent."""

from browser_agent.schemas.observation import InteractiveElement, PageSnapshot
from browser_agent.schemas.grounding import GroundingCandidate, GroundingResult
from browser_agent.schemas.browser_action import BrowserAction
from browser_agent.schemas.action_result import ActionResult
from browser_agent.schemas.workflow_step import WorkflowStep
from browser_agent.schemas.workflow import Workflow
from browser_agent.schemas.workflow_result import WorkflowProgressEvent, WorkflowResult, WorkflowStepResult

__all__ = [
    "InteractiveElement", "PageSnapshot", "GroundingCandidate", "GroundingResult",
    "BrowserAction", "ActionResult", "Workflow", "WorkflowStep", "WorkflowResult",
    "WorkflowStepResult", "WorkflowProgressEvent",
]
