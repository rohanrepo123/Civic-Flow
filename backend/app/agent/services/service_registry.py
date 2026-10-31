import json
from pathlib import Path
from typing import Iterable

from backend.app.agent.schemas.service import ServiceRecord


class ServiceRegistry:
    def __init__(self, services: Iterable[ServiceRecord]) -> None:
        self._services = tuple(services)
        ids = [service.service_id for service in self._services]
        if len(ids) != len(set(ids)):
            raise ValueError("service registry contains duplicate service_id values")

    @classmethod
    def from_json(cls, path: Path) -> "ServiceRegistry":
        try:
            records = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"unable to load service registry: {path}") from exc
        if not isinstance(records, list):
            raise ValueError("service registry JSON must contain a list")
        return cls(ServiceRecord.model_validate(record) for record in records)

    @classmethod
    def default(cls) -> "ServiceRegistry":
        data_path = Path(__file__).parent.parent / "data" / "services.json"
        return cls.from_json(data_path)

    def all(self) -> tuple[ServiceRecord, ...]:
        return self._services
