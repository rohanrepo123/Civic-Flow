import json
from pathlib import Path

from backend.app.agent.schemas.source import OfficialSource


class SourceCatalog:
    """Manually curated source metadata; no URLs are discovered or invented."""

    def __init__(self, sources: list[OfficialSource]) -> None:
        self._sources = tuple(sources)
        ids = [source.source_id for source in sources]
        if len(ids) != len(set(ids)):
            raise ValueError("source catalog contains duplicate source_id values")

    @classmethod
    def from_json(cls, path: Path) -> "SourceCatalog":
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"unable to load source catalog: {path}") from exc
        if not isinstance(raw, list):
            raise ValueError("source catalog JSON must contain a list")
        return cls([OfficialSource.model_validate(item) for item in raw])

    @classmethod
    def default(cls) -> "SourceCatalog":
        return cls.from_json(Path(__file__).parent.parent / "data" / "sources.json")

    def for_service(self, service_id: str) -> tuple[OfficialSource, ...]:
        return tuple(source for source in self._sources if source.service_id == service_id)

    def all(self) -> tuple[OfficialSource, ...]:
        return self._sources
