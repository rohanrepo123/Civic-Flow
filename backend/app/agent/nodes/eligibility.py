from collections.abc import Mapping
from typing import Any

from backend.app.agent.schemas.eligibility import EligibilityResult
from backend.app.agent.schemas.requirements import ServiceRequirements
from backend.app.agent.services.eligibility_engine import EligibilityEngine


class EligibilityNode:
    def __init__(self, engine: EligibilityEngine | None = None) -> None:
        self._engine = engine or EligibilityEngine()

    def run(
        self,
        requirements: ServiceRequirements,
        profile: Mapping[str, Any],
    ) -> EligibilityResult:
        return self._engine.evaluate_requirements(requirements, profile)
