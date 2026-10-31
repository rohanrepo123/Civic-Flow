"""Natural-language selection of actionable elements from a PageSnapshot."""

from browser_agent.grounding.ambiguity import ambiguity_reason
from browser_agent.grounding.confidence import ConfidenceScorer, ConfidenceThresholds
from browser_agent.grounding.semantic_matcher import SemanticMatch, SemanticMatcher, infer_expected_type, normalize_element_type
from browser_agent.schemas.grounding import GroundingCandidate, GroundingResult
from browser_agent.schemas.observation import InteractiveElement, PageSnapshot


class ElementGrounder:
    """Match instructions to snapshot elements without performing actions."""

    def __init__(self, thresholds: ConfidenceThresholds | None = None) -> None:
        self.thresholds = thresholds or ConfidenceThresholds()
        self.matcher = SemanticMatcher(ConfidenceScorer(self.thresholds))

    async def find_element(
        self,
        instruction: str,
        snapshot: PageSnapshot,
        expected_element_type: str | None = None,
    ) -> GroundingResult:
        """Find a high-confidence, visible, enabled, type-compatible element.

        The result carries the source ``snapshot_id``. Callers must compare it
        with their current observation before attempting any later action.
        """
        if not instruction.strip():
            return self._failure(instruction, snapshot, 0.0, "Instruction is empty; provide a description of the target.", [])

        matches = self.matcher.rank(instruction, snapshot.interactive_elements, expected_element_type)
        plausible = [item for item in matches if item.confidence >= self.thresholds.minimum_candidate]
        if not plausible:
            return self._failure(
                instruction, snapshot, matches[0].confidence if matches else 0.0,
                "No page element matched the instruction with sufficient confidence. Please rephrase or observe the page again.", [],
            )

        # A strong textual match that is unusable must not silently fall
        # through to a weaker target of a different type or state.
        strongest = plausible[0]
        invalid_reason = self._unusable_reason(strongest, expected_element_type, instruction)
        actionable = [item for item in plausible if self._unusable_reason(item, expected_element_type, instruction) is None]
        if invalid_reason:
            return self._failure(
                instruction, snapshot, strongest.confidence, invalid_reason,
                self._alternatives(plausible),
            )

        if not actionable:
            # Defensive fallback; all candidates were filtered as unusable.
            return self._failure(instruction, snapshot, strongest.confidence, "No actionable matching element is available.", self._alternatives(plausible))

        tie_reason = ambiguity_reason(actionable, self.thresholds)
        if tie_reason:
            return self._failure(instruction, snapshot, actionable[0].confidence, tie_reason, self._alternatives(actionable))

        best = actionable[0]
        if best.confidence < self.thresholds.high_confidence:
            return self._failure(
                instruction, snapshot, best.confidence,
                f"The best candidate is below the high-confidence threshold ({self.thresholds.high_confidence:.2f}). Please clarify the target.",
                self._alternatives(actionable),
            )

        alternatives = [item for item in self._alternatives(actionable) if item.element.element_id != best.element.element_id]
        return GroundingResult(
            success=True,
            instruction=instruction,
            selected_element=self._safe_element(best.element),
            element_id=best.element.element_id,
            confidence=best.confidence,
            alternatives=alternatives,
            needs_clarification=False,
            clarification_reason=None,
            explanation=best.explanation,
            snapshot_id=str(snapshot.snapshot_id),
        )

    @staticmethod
    def _unusable_reason(
        match: SemanticMatch,
        expected_element_type: str | None,
        instruction: str,
    ) -> str | None:
        element = match.element
        if not element.visible:
            return f"The best matching element ({element.label or element.element_id}) is hidden and cannot be selected."
        if element.disabled or not element.enabled:
            return f"The best matching element ({element.label or element.element_id}) is disabled."
        expected = normalize_element_type(expected_element_type) or infer_expected_type(instruction)
        if expected and not match.compatible:
            return f"The best text match is a {element.element_type} element, incompatible with the requested {expected} control."
        return None

    @staticmethod
    def _safe_element(element: InteractiveElement) -> InteractiveElement:
        """Return a copy without any potentially sensitive control value."""
        return element.model_copy(update={"current_value": None})

    @staticmethod
    def _alternatives(matches: list[SemanticMatch], limit: int = 5) -> list[GroundingCandidate]:
        return [
            GroundingCandidate(element=ElementGrounder._safe_element(item.element), confidence=item.confidence, explanation=item.explanation)
            for item in matches[:limit]
        ]

    @staticmethod
    def _failure(
        instruction: str,
        snapshot: PageSnapshot,
        confidence: float,
        reason: str,
        alternatives: list[GroundingCandidate],
    ) -> GroundingResult:
        return GroundingResult(
            success=False,
            instruction=instruction,
            selected_element=None,
            element_id=None,
            confidence=confidence,
            alternatives=alternatives,
            needs_clarification=True,
            clarification_reason=reason,
            explanation=reason,
            snapshot_id=str(snapshot.snapshot_id),
        )
