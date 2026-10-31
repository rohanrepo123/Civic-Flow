"""Serializable results produced by element grounding."""

from pydantic import BaseModel, ConfigDict, Field

from browser_agent.schemas.observation import InteractiveElement


class GroundingCandidate(BaseModel):
    """A possible element with its score and a concise match explanation."""

    model_config = ConfigDict(extra="forbid")

    element: InteractiveElement
    confidence: float = Field(ge=0.0, le=1.0)
    explanation: str


class GroundingResult(BaseModel):
    """Grounding output tied to the snapshot from which its IDs came."""

    model_config = ConfigDict(extra="forbid")

    success: bool
    instruction: str
    selected_element: InteractiveElement | None = None
    element_id: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    alternatives: list[GroundingCandidate] = Field(default_factory=list)
    needs_clarification: bool = False
    clarification_reason: str | None = None
    explanation: str
    snapshot_id: str
