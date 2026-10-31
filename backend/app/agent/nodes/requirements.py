from backend.app.agent.schemas.requirements import ServiceRequirements
from backend.app.agent.schemas.source import RetrievedChunk
from backend.app.agent.services.requirement_extractor import RequirementExtractor


class RequirementsNode:
    def __init__(self, extractor: RequirementExtractor) -> None:
        self._extractor = extractor

    async def run(self, service_id: str, chunks: list[RetrievedChunk]) -> ServiceRequirements:
        return await self._extractor.extract(service_id=service_id, chunks=chunks)
