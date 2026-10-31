"""Bounded, idempotency-aware retry decisions for workflow failures."""

from dataclasses import dataclass

from browser_agent.schemas.workflow_step import WorkflowStep

_IDEMPOTENT_ACTIONS = frozenset({"fill", "select", "check", "uncheck", "radio_select", "scroll_into_view"})
_PERMANENT_FAILURES = (
    "ambiguous", "only supported", "invalid action", "incompatible", "disabled",
    "required value", "missing required", "requires a value", "requires an explicit",
    "option is missing", "option is ambiguous", "uploads are disabled",
    "outside the configured allowed", "upload path does not exist",
    "not a regular file", "configured upload path is not a directory",
)
_RECOVERABLE_FAILURES = (
    "stale", "page changed after observation", "detached", "timed out", "timeout",
    "not found", "no longer exists", "observation failed",
)


@dataclass(frozen=True)
class RecoveryDecision:
    """Whether one more observation/ground/action attempt is safe."""

    retry: bool
    message: str
    requires_human_intervention: bool = False


class WorkflowRecovery:
    """Retry only bounded operations that can safely be repeated with same inputs."""

    def __init__(self, max_retries: int = 1) -> None:
        if max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        self.max_retries = max_retries

    def decide(
        self,
        step: WorkflowStep,
        retries_used: int,
        *,
        requires_human_intervention: bool = False,
        verified: bool = False,
        error: str | None = None,
    ) -> RecoveryDecision:
        """Retry only recognized transient failures for idempotent actions."""
        if requires_human_intervention:
            return RecoveryDecision(False, "Failure requires human participation.", True)
        if verified:
            return RecoveryDecision(False, "The action is already verified.")
        normalized_error = (error or "").casefold()
        if any(marker in normalized_error for marker in _PERMANENT_FAILURES):
            ambiguous = "ambiguous" in normalized_error
            return RecoveryDecision(
                False,
                "The failure is permanent and must be corrected before continuing.",
                requires_human_intervention=ambiguous,
            )
        if step.action_type not in _IDEMPOTENT_ACTIONS:
            return RecoveryDecision(False, "This action is not safe to retry automatically; inspect the page before proceeding.", True)
        if not any(marker in normalized_error for marker in _RECOVERABLE_FAILURES):
            return RecoveryDecision(False, "The failure is not classified as safely recoverable.")
        if retries_used >= self.max_retries:
            uncertain = True
            return RecoveryDecision(
                False,
                "The configured retry limit has been reached.",
                requires_human_intervention=uncertain,
            )
        return RecoveryDecision(True, "A fresh observation and re-grounding are safe before retrying this idempotent action.")

    @staticmethod
    def is_idempotent(action_type: str) -> bool:
        """Expose the retry policy for tests and orchestration adapters."""
        return action_type in _IDEMPOTENT_ACTIONS
