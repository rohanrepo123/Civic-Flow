"""Clarification decisions for weak, tied, or unusable grounding candidates."""

from browser_agent.grounding.confidence import ConfidenceThresholds
from browser_agent.grounding.semantic_matcher import SemanticMatch


def ambiguity_reason(
    matches: list[SemanticMatch],
    thresholds: ConfidenceThresholds,
) -> str | None:
    """Return a clarification reason when leading candidates are near-tied."""
    plausible = [item for item in matches if item.confidence >= thresholds.minimum_candidate]
    if len(plausible) < 2:
        return None
    first, second = plausible[0], plausible[1]
    if first.confidence - second.confidence <= thresholds.ambiguity_margin:
        first_label = first.element.label or first.element.text or first.element.element_type
        second_label = second.element.label or second.element.text or second.element.element_type
        return f"Several elements match similarly: {first_label!r} and {second_label!r}. Please clarify which one you mean."
    return None
