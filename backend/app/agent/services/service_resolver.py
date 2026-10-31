from backend.app.agent.schemas.intent import Intent
from backend.app.agent.schemas.resolution import ResolutionStatus, ServiceResolution
from backend.app.agent.schemas.service import ServiceRecord
from backend.app.agent.services.service_registry import ServiceRegistry


def _normalize(value: str | None) -> str:
    return " ".join((value or "").casefold().replace("_", " ").split())


class ServiceResolver:
    def __init__(self, registry: ServiceRegistry) -> None:
        self._registry = registry

    def all_services(self) -> tuple[ServiceRecord, ...]:
        """Expose the configured service catalogue to the discovery stage."""
        return self._registry.all()

    def resolve(self, intent: Intent) -> ServiceResolution:
        query = _normalize(intent.service_name)
        jurisdiction = _normalize(intent.jurisdiction)
        ranked: list[tuple[int, object]] = []
        for service in self._registry.all():
            score = 0
            service_name = _normalize(service.name)
            aliases = [_normalize(alias) for alias in service.aliases]
            if query:
                if query == _normalize(service.service_id) or query == service_name or query in aliases:
                    score += 4
                elif any(query in alias or alias in query for alias in aliases if alias):
                    score += 2
            if intent.service_category is not None and intent.service_category is service.category:
                score += 2
            if jurisdiction:
                if jurisdiction == _normalize(service.jurisdiction):
                    score += 3
                else:
                    continue
            if score:
                ranked.append((score, service))

        if not ranked:
            return ServiceResolution(
                status=ResolutionStatus.NOT_FOUND,
                clarification_question="Which service and jurisdiction do you mean?",
            )
        best = max(score for score, _ in ranked)
        candidates = [service for score, service in ranked if score == best]
        if len(candidates) != 1:
            return ServiceResolution(
                status=ResolutionStatus.AMBIGUOUS,
                candidates=candidates,
                clarification_question="Which of these services should I use?",
            )
        selected = candidates[0]
        return ServiceResolution(
            status=ResolutionStatus.RESOLVED,
            selected_service=selected,
            candidates=[selected],
        )
