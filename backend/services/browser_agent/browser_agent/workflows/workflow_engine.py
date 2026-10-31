"""Multi-step, deterministic orchestration over the Phase 1–4 browser modules."""

from datetime import datetime, timezone
import hashlib
import inspect
import json
from typing import Awaitable, Callable
from uuid import uuid4

from playwright.async_api import Page

from browser_agent.actions.action_executor import ActionExecutor
from browser_agent.grounding.element_grounder import ElementGrounder
from browser_agent.observation.page_observer import PageObserver
from browser_agent.schemas.observation import PageSnapshot
from browser_agent.schemas.workflow import Workflow
from browser_agent.schemas.workflow_result import (
    WorkflowProgressEvent,
    WorkflowResult,
    WorkflowStepResult,
)
from browser_agent.schemas.workflow_step import WorkflowStep
from browser_agent.workflows.workflow_executor import StepExecution, WorkflowExecutor
from browser_agent.workflows.workflow_planner import WorkflowPlan, WorkflowPlanner
from browser_agent.workflows.workflow_recovery import WorkflowRecovery
from browser_agent.workflows.workflow_state import WorkflowState, WorkflowStateStore

EventCallback = Callable[[WorkflowProgressEvent], object | Awaitable[object]]


class WorkflowEngine:
    """Execute user-authored steps sequentially and pause on uncertainty."""

    def __init__(
        self,
        *,
        observer: PageObserver | None = None,
        grounder: ElementGrounder | None = None,
        action_executor: ActionExecutor | None = None,
        planner: WorkflowPlanner | None = None,
        recovery: WorkflowRecovery | None = None,
        state_store: WorkflowStateStore | None = None,
    ) -> None:
        self.observer = observer or PageObserver()
        self.grounder = grounder or ElementGrounder()
        self.action_executor = action_executor or ActionExecutor()
        self.workflow_executor = WorkflowExecutor(self.grounder, self.action_executor)
        self.planner = planner or WorkflowPlanner()
        self.recovery = recovery or WorkflowRecovery(max_retries=1)
        self.state_store = state_store or WorkflowStateStore()

    async def run(
        self,
        workflow: Workflow,
        page: Page,
        session_id: str,
        event_callback: EventCallback | None = None,
    ) -> WorkflowResult:
        """Validate and run a workflow, returning a completed or paused result."""
        plan = self.planner.plan(workflow)
        if not plan.valid:
            result = self._invalid_result(workflow, plan)
            await self._emit(
                workflow.workflow_id,
                None,
                "workflow_failed",
                "Workflow validation failed.",
                "failed",
                event_callback,
            )
            return result

        manifest = self._manifest(plan)
        state = self.state_store.get(workflow.workflow_id)
        if state is not None:
            if state.session_id != session_id or state.step_manifest != manifest:
                return self._detached_result(workflow, state, "Workflow state does not match this session or step plan.")
            if state.status in {"waiting_for_user", "completed", "failed"}:
                return self._result(workflow, state, self._status_message(state.status))
            if state.status == "running":
                return self._result(workflow, state, "Workflow is already running.")

        now = datetime.now(timezone.utc)
        state = WorkflowState(
            workflow_id=workflow.workflow_id,
            session_id=session_id,
            step_manifest=manifest,
            status="running",
            started_at=now,
        )
        self.state_store.save(state)
        await self._emit(workflow.workflow_id, None, "workflow_started", "Workflow started.", "running", event_callback)
        return await self._continue(workflow, plan, state, page, event_callback)

    async def resume_after_user_action(
        self,
        workflow: Workflow,
        page: Page,
        session_id: str,
        completed_step_id: str,
        event_callback: EventCallback | None = None,
    ) -> WorkflowResult:
        """Resume after the user manually completed the waiting step.

        This method records a human-reported completion and continues with later
        workflow steps. It never executes the restricted step itself.
        """
        plan = self.planner.plan(workflow)
        state = self.state_store.get(workflow.workflow_id)
        if not plan.valid or state is None:
            return self._detached_result(workflow, state, "No resumable workflow state exists.")
        if state.session_id != session_id or state.step_manifest != self._manifest(plan):
            return self._detached_result(workflow, state, "Workflow state does not match this session or step plan.")
        if state.status != "waiting_for_user" or state.current_step_id != completed_step_id:
            return self._detached_result(workflow, state, "The supplied step is not the current human checkpoint.")

        index = state.current_step_index
        if index >= len(plan.ordered_steps) or plan.ordered_steps[index].step_id != completed_step_id:
            return self._detached_result(workflow, state, "Workflow checkpoint position is inconsistent.")
        old_result = next((item for item in reversed(state.step_results) if item.step_id == completed_step_id), None)
        if old_result is not None:
            state.step_results[state.step_results.index(old_result)] = old_result.model_copy(
                update={"status": "completed", "message": "User reports completing this checkpoint manually."}
            )
        else:
            state.step_results.append(
                WorkflowStepResult(
                    step_id=completed_step_id,
                    status="completed",
                    attempts=0,
                    message="User reports completing this checkpoint manually.",
                )
            )
        if completed_step_id not in state.completed_step_ids:
            state.completed_step_ids.append(completed_step_id)
        state.current_step_index += 1
        state.current_step_id = None
        state.status = "running"
        state.human_approval_status = "user_completed"
        self.state_store.save(state)
        await self._emit(
            workflow.workflow_id,
            completed_step_id,
            "workflow_resumed",
            "Workflow resumed after the user's manual step.",
            "running",
            event_callback,
        )
        await self._emit(
            workflow.workflow_id,
            completed_step_id,
            "step_completed",
            "User reports completing the checkpoint manually.",
            "running",
            event_callback,
        )
        return await self._continue(workflow, plan, state, page, event_callback)

    async def _continue(
        self,
        workflow: Workflow,
        plan: WorkflowPlan,
        state: WorkflowState,
        page: Page,
        event_callback: EventCallback | None,
    ) -> WorkflowResult:
        restricted_ids = set(plan.restricted_step_ids)
        while state.current_step_index < len(plan.ordered_steps):
            step = plan.ordered_steps[state.current_step_index]
            state.current_step_id = step.step_id
            if step.step_id in restricted_ids:
                result = WorkflowStepResult(
                    step_id=step.step_id,
                    status="waiting_for_user",
                    attempts=0,
                    message="This step requires a human to review and perform it manually.",
                )
                self._replace_step_result(state, result)
                state.status = "waiting_for_user"
                state.human_approval_status = "waiting_for_user"
                self.state_store.save(state)
                await self._emit(workflow.workflow_id, step.step_id, "step_started", "Step started.", "running", event_callback)
                await self._emit(
                    workflow.workflow_id,
                    step.step_id,
                    "waiting_for_user",
                    "Review and manually complete this restricted step, then resume with its step ID.",
                    "waiting_for_user",
                    event_callback,
                )
                return self._result(workflow, state, result.message)

            await self._emit(workflow.workflow_id, step.step_id, "step_started", "Step started.", "running", event_callback)
            attempt_result = await self._run_step(workflow, step, page, state, event_callback)
            if attempt_result.status == "waiting_for_user":
                self._replace_step_result(state, attempt_result)
                state.status = "waiting_for_user"
                state.human_approval_status = "waiting_for_user"
                state.current_step_id = step.step_id
                self.state_store.save(state)
                await self._emit(
                    workflow.workflow_id,
                    step.step_id,
                    "waiting_for_user",
                    "Grounding or action safety requires a human decision.",
                    "waiting_for_user",
                    event_callback,
                )
                return self._result(workflow, state, attempt_result.message)
            if attempt_result.status == "failed":
                self._replace_step_result(state, attempt_result)
                state.failed_step_ids.append(step.step_id)
                state.status = "failed"
                state.completed_at = datetime.now(timezone.utc)
                self._skip_remaining(plan, state)
                self.state_store.save(state)
                await self._emit(workflow.workflow_id, step.step_id, "step_failed", "Step failed; later steps were skipped.", "failed", event_callback)
                await self._emit(workflow.workflow_id, None, "workflow_failed", "Workflow stopped after an unrecoverable step failure.", "failed", event_callback)
                return self._result(workflow, state, attempt_result.message)

            self._replace_step_result(state, attempt_result)
            if step.step_id not in state.completed_step_ids:
                state.completed_step_ids.append(step.step_id)
            state.current_step_index += 1
            state.current_step_id = None
            self.state_store.save(state)
            await self._emit(workflow.workflow_id, step.step_id, "step_completed", "Step completed and verified.", "running", event_callback)

        state.status = "completed"
        state.current_step_id = None
        state.completed_at = datetime.now(timezone.utc)
        state.human_approval_status = "user_completed" if state.human_approval_status == "user_completed" else "not_required"
        self.state_store.save(state)
        await self._emit(workflow.workflow_id, None, "workflow_completed", "All workflow steps completed.", "completed", event_callback)
        return self._result(workflow, state, "Workflow completed successfully.")

    async def _run_step(
        self,
        workflow: Workflow,
        step: WorkflowStep,
        page: Page,
        state: WorkflowState,
        event_callback: EventCallback | None,
    ) -> WorkflowStepResult:
        attempts = 0
        retries_used = 0
        retry_messages: list[str] = []
        grounding_history = None
        action_attempts = []
        final_action_result = None

        while True:
            attempts += 1
            try:
                snapshot = await self.observer.observe(page)
            except Exception:
                decision = self.recovery.decide(step, retries_used, error="page observation failed")
                if decision.retry:
                    retries_used += 1
                    retry_messages.append("Page observation failed; retrying with a fresh observation.")
                    await self._emit(workflow.workflow_id, step.step_id, "recovery_started", retry_messages[-1], "running", event_callback)
                    continue
                return WorkflowStepResult(
                    step_id=step.step_id,
                    status="waiting_for_user" if decision.requires_human_intervention else "failed",
                    attempts=attempts,
                    retry_messages=retry_messages,
                    message="Page observation failed and recovery was unavailable.",
                )

            state.current_page_url = snapshot.url
            state.current_page_title = snapshot.title
            self.state_store.save(state)
            await self._emit(workflow.workflow_id, step.step_id, "page_observed", "Current page observed.", "running", event_callback)

            try:
                execution: StepExecution = await self.workflow_executor.execute_step(
                    step,
                    snapshot,
                    page,
                    action_id=f"{workflow.workflow_id[:20]}_{step.step_id[:20]}_{attempts}_{uuid4().hex[:6]}",
                )
            except Exception:
                execution = StepExecution(status="failed", message="Browser step execution raised an unexpected error.")

            grounding_history = execution.grounding_result or grounding_history
            if execution.grounding_result is not None:
                await self._emit(
                    workflow.workflow_id,
                    step.step_id,
                    "element_grounded",
                    "Target grounded." if execution.grounding_result.success else "Grounding did not produce a safe target.",
                    "running",
                    event_callback,
                )
            if execution.action_result is not None:
                final_action_result = execution.action_result
                action_attempts.append(execution.action_result)
                await self._emit(workflow.workflow_id, step.step_id, "action_executed", "Action attempt returned.", "running", event_callback)
                await self._emit(
                    workflow.workflow_id,
                    step.step_id,
                    "action_verified",
                    "Action verified." if execution.action_result.verified else "Action was not verified.",
                    "running",
                    event_callback,
                )

            if execution.status == "completed":
                if execution.action_result is not None:
                    state.current_page_url = execution.action_result.page_url
                    state.current_page_title = execution.action_result.page_title
                try:
                    refreshed = await self.observer.observe(page)
                    changed = self.workflow_executor.action_executor.verifier.snapshot_signature(snapshot) != self.workflow_executor.action_executor.verifier.snapshot_signature(refreshed)
                    state.current_page_url = refreshed.url
                    state.current_page_title = refreshed.title
                    self.state_store.save(state)
                    if changed:
                        await self._emit(workflow.workflow_id, step.step_id, "page_observed", "Page snapshot refreshed after an action change.", "running", event_callback)
                except Exception:
                    # The action's verifier already succeeded; the next step
                    # still performs a fresh observation before grounding.
                    pass
                return WorkflowStepResult(
                    step_id=step.step_id,
                    status="completed",
                    attempts=attempts,
                    retry_messages=retry_messages,
                    grounding_result=grounding_history,
                    action_attempts=action_attempts,
                    action_result=final_action_result,
                    message="Step completed and verified.",
                )

            if execution.status == "waiting_for_user":
                return WorkflowStepResult(
                    step_id=step.step_id,
                    status="waiting_for_user",
                    attempts=attempts,
                    retry_messages=retry_messages,
                    grounding_result=grounding_history,
                    action_attempts=action_attempts,
                    action_result=final_action_result,
                    message=execution.message,
                )

            decision = self.recovery.decide(
                step,
                retries_used,
                requires_human_intervention=execution.requires_human_intervention,
                verified=bool(execution.action_result and execution.action_result.verified),
                error=(execution.action_result.error if execution.action_result else execution.message),
            )
            if decision.retry:
                retries_used += 1
                retry_messages.append(decision.message)
                await self._emit(workflow.workflow_id, step.step_id, "recovery_started", decision.message, "running", event_callback)
                continue
            if decision.requires_human_intervention:
                return WorkflowStepResult(
                    step_id=step.step_id,
                    status="waiting_for_user",
                    attempts=attempts,
                    retry_messages=retry_messages,
                    grounding_result=grounding_history,
                    action_attempts=action_attempts,
                    action_result=final_action_result,
                    message=decision.message,
                )
            return WorkflowStepResult(
                step_id=step.step_id,
                status="failed",
                attempts=attempts,
                retry_messages=retry_messages,
                grounding_result=grounding_history,
                action_attempts=action_attempts,
                action_result=final_action_result,
                message=execution.message or decision.message,
            )

    async def _emit(
        self,
        workflow_id: str,
        step_id: str | None,
        event_type: str,
        message: str,
        status: str,
        callback: EventCallback | None,
    ) -> None:
        """Send a structured event; callback errors never change workflow state."""
        if callback is None:
            return
        event = WorkflowProgressEvent(
            workflow_id=workflow_id,
            step_id=step_id,
            event_type=event_type,
            message=message,
            timestamp=datetime.now(timezone.utc),
            status=status,
        )
        try:
            outcome = callback(event)
            if inspect.isawaitable(outcome):
                await outcome
        except Exception:
            return

    def _result(self, workflow: Workflow, state: WorkflowState, message: str) -> WorkflowResult:
        return WorkflowResult(
            workflow_id=workflow.workflow_id,
            status=state.status,
            total_steps=len(workflow.steps),
            completed_steps=len(state.completed_step_ids),
            failed_steps=len(state.failed_step_ids),
            skipped_steps=len(state.skipped_step_ids),
            waiting_steps=sum(item.status == "waiting_for_user" for item in state.step_results),
            current_step_id=state.current_step_id,
            requires_human_intervention=state.status == "waiting_for_user",
            message=message,
            step_results=state.step_results,
            started_at=state.started_at,
            completed_at=state.completed_at,
        )

    @staticmethod
    def _replace_step_result(state: WorkflowState, result: WorkflowStepResult) -> None:
        for index, previous in enumerate(state.step_results):
            if previous.step_id == result.step_id:
                state.step_results[index] = result
                return
        state.step_results.append(result)

    @staticmethod
    def _skip_remaining(plan: WorkflowPlan, state: WorkflowState) -> None:
        for step in plan.ordered_steps[state.current_step_index + 1 :]:
            if step.step_id in state.completed_step_ids or step.step_id in state.failed_step_ids:
                continue
            state.skipped_step_ids.append(step.step_id)
            WorkflowEngine._replace_step_result(
                state,
                WorkflowStepResult(step_id=step.step_id, status="skipped", message="Skipped after an earlier step failed."),
            )

    @staticmethod
    def _manifest(plan: WorkflowPlan) -> list[str]:
        manifest: list[str] = []
        for step in plan.ordered_steps:
            content = {
                "step_id": step.step_id,
                "instruction": step.instruction,
                "action_type": step.action_type,
                "value": step.value,
                "file_path": step.file_path,
                "expected_result": step.expected_result,
                "requires_confirmation": step.requires_confirmation,
            }
            fingerprint = hashlib.sha256(json.dumps(content, sort_keys=True).encode("utf-8")).hexdigest()
            manifest.append(f"{step.step_id}:{step.action_type}:{fingerprint}")
        return manifest

    @staticmethod
    def _status_message(status: str) -> str:
        return {
            "waiting_for_user": "Workflow is paused for human intervention.",
            "completed": "Workflow was already completed.",
            "failed": "Workflow previously failed and will not be replayed automatically.",
        }.get(status, "Workflow state returned.")

    def _detached_result(self, workflow: Workflow, state: WorkflowState | None, message: str) -> WorkflowResult:
        now = datetime.now(timezone.utc)
        if state is None:
            return WorkflowResult(
                workflow_id=workflow.workflow_id,
                status="failed",
                total_steps=len(workflow.steps),
                completed_steps=0,
                failed_steps=0,
                skipped_steps=0,
                message=message,
                started_at=now,
                completed_at=now,
            )
        return self._result(workflow, state, message)

    def _invalid_result(self, workflow: Workflow, plan: WorkflowPlan) -> WorkflowResult:
        now = datetime.now(timezone.utc)
        issues_by_step = {issue.step_id for issue in plan.issues if issue.step_id is not None}
        step_results = [
            WorkflowStepResult(
                step_id=step.step_id,
                status="failed",
                message="Workflow step failed validation.",
            )
            for step in workflow.steps
            if step.step_id in issues_by_step
        ]
        issue_text = "; ".join(issue.message for issue in plan.issues)
        return WorkflowResult(
            workflow_id=workflow.workflow_id,
            status="failed",
            total_steps=len(workflow.steps),
            completed_steps=0,
            failed_steps=len(step_results),
            skipped_steps=0,
            current_step_id=step_results[0].step_id if step_results else None,
            message=issue_text or "Workflow validation failed.",
            step_results=step_results,
            started_at=now,
            completed_at=now,
        )
