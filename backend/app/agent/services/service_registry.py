import json
import os
import re
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
        return cls(ServiceRecord.model_validate(cls._normalize_record(record)) for record in records)

    @staticmethod
    def _normalize_record(record: object) -> dict:
        if not isinstance(record, dict):
            raise ValueError("each service catalogue entry must be an object")
        normalized = dict(record)
        aliases = list(normalized.get("aliases") or [])
        name = normalized.get("name")
        if isinstance(name, str) and name not in aliases:
            aliases.append(name)
            aliases.extend(alias for alias in re.findall(r"\(([^)]+)\)", name) if alias not in aliases)
        normalized["aliases"] = aliases
        docs_url = normalized.get("official_docs_url")
        sources = list(normalized.get("official_sources") or [])
        if isinstance(docs_url, str) and not any(item.get("url") == docs_url for item in sources if isinstance(item, dict)):
            sources.append({
                "source_id": f"{normalized.get('service_id', 'service')}:official-docs",
                "title": f"{name or 'Service'} official guidance",
                "url": docs_url,
            })
        normalized["official_sources"] = sources
        return normalized

    @classmethod
    def default(cls) -> "ServiceRegistry":
        data_path = Path(__file__).parent.parent / "data" / "services.json"
        records = list(cls.from_json(data_path).all())
        configured = os.getenv("CIVICFLOW_SERVICE_CATALOG", "").strip()
        catalog_path = Path(configured) if configured else data_path.parent / "service_catalog.json"
        if configured and not catalog_path.is_file():
            raise ValueError("CIVICFLOW_SERVICE_CATALOG does not point to a file")
        by_id = {record.service_id: record for record in records}
        if catalog_path.is_file():
            by_id.update({record.service_id: record for record in cls.from_json(catalog_path).all()})
        return cls(by_id.values())

    def all(self) -> tuple[ServiceRecord, ...]:
        return self._services
