"""LLM-assisted matching of a citizen's wording to the service catalogue."""

import json
from typing import Any

from backend.app.agent.schemas.intent import Intent
from backend.app.agent.schemas.service import ServiceRecord
from backend.app.agent.services.llm import StructuredChatClient


class ServiceCandidateMatcher:
    def __init__(self, client: StructuredChatClient) -> None:
        self._client = client

    async def match(
        self,
        *,
        query: str,
        intent: Intent,
        services: list[ServiceRecord],
        context: dict[str, Any] | None = None,
    ) -> str | None:
        """Return a catalogue service ID only when the request identifies one clearly."""
        catalog = [
            {
                "service_id": service.service_id,
                "name": service.name,
                "aliases": service.aliases,
                "category": service.category.value,
                "jurisdiction": service.jurisdiction,
                "department": service.department,
                "description": service.description,
                "official_docs_url": str(service.official_docs_url) if service.official_docs_url else None,
            }
            for service in services
        ]
        raw = await self._client.complete_json(
            system_prompt=(
                "Match a citizen's request to the best public service in the supplied catalogue. "
                "Consider scheme names, common abbreviations, related form names, category, and jurisdiction. "
                "Use service memory only to resolve an obvious follow-up; a new explicit request overrides it. "
                "Do not ask for details already implied by a named scheme or portal. Do not claim two different "
                "schemes are the same. When the wording is generic or multiple services remain equally plausible, "
                "treat an explicitly stated jurisdiction as a hard constraint. "
                "return service_id null so the assistant can ask one simple clarification. "
                "Choose only an ID present in the catalogue. Return JSON {service_id: string|null, confidence: number}."
            ),
            user_prompt=json.dumps(
                {
                    "current_message": query,
                    "intent": intent.model_dump(mode="json"),
                    "service_memory": context or {},
                    "catalogue": catalog,
                },
                ensure_ascii=False,
            ),
        )
        data = json.loads(raw)
        service_id = data.get("service_id")
        confidence = data.get("confidence", 0)
        known = {service.service_id for service in services}
        if isinstance(service_id, str) and service_id in known and isinstance(confidence, (float, int)) and confidence >= 0.72:
            return service_id
        return None
