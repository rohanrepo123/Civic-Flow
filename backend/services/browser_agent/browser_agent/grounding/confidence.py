"""Transparent confidence calculations and configurable selection thresholds."""

from dataclasses import dataclass

from pydantic import BaseModel, ConfigDict, Field


class ConfidenceThresholds(BaseModel):
    """Thresholds controlling auto-selection and clarification behavior."""

    model_config = ConfigDict(extra="forbid")

    minimum_candidate: float = Field(default=0.28, ge=0.0, le=1.0)
    high_confidence: float = Field(default=0.78, ge=0.0, le=1.0)
    ambiguity_margin: float = Field(default=0.07, ge=0.0, le=1.0)


@dataclass(frozen=True)
class MatchFeatures:
    """Normalized feature values used by the visible scoring formula."""

    exact_match: bool
    query_precision: float
    candidate_coverage: float
    fuzzy_similarity: float
    compatible_type: bool
    all_keywords_match: bool = False
    query_token_count: int = 0


class ConfidenceScorer:
    """Combine exact, token, fuzzy, and compatible-type evidence."""

    def __init__(self, thresholds: ConfidenceThresholds | None = None) -> None:
        self.thresholds = thresholds or ConfidenceThresholds()

    def score(self, features: MatchFeatures) -> float:
        """Return a deterministic score from 0 to 1.

        Formula: 0.45 * query-token precision + 0.20 * candidate coverage +
        0.35 * fuzzy similarity, with an exact-match floor of 0.94 and a
        compatible-type bonus of 0.04. When all query keywords occur across the
        element's semantic attributes, apply a 0.82 floor (0.75 for one-word
        queries). Scores are capped at 1.0.
        """
        score = (
            0.45 * features.query_precision
            + 0.20 * features.candidate_coverage
            + 0.35 * features.fuzzy_similarity
        )
        if features.exact_match:
            score = max(score, 0.94)
        if features.compatible_type:
            score += 0.04
        if features.all_keywords_match:
            score = max(score, 0.75 if features.query_token_count <= 1 else 0.82)
        return round(min(score, 1.0), 4)
