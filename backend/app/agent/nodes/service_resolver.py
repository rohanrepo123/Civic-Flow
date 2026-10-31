from backend.app.agent.schemas.intent import Intent
from backend.app.agent.schemas.resolution import ServiceResolution
from backend.app.agent.services.service_resolver import ServiceResolver


class ServiceResolverNode:
    def __init__(self, resolver: ServiceResolver) -> None:
        self._resolver = resolver

    def run(self, intent: Intent) -> ServiceResolution:
        return self._resolver.resolve(intent)
