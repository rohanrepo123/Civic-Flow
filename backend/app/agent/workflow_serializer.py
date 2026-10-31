from typing import Any

from langgraph.checkpoint.serde.jsonplus import JsonPlusSerializer
from pydantic import BaseModel

from backend.app.agent.schemas.agent_events import AgentEvent
from backend.app.agent.schemas.documents import DocumentMetadata, ExtractedField
from backend.app.agent.schemas.eligibility import EligibilityResult
from backend.app.agent.schemas.intent import Intent
from backend.app.agent.schemas.planner import PlannerResult
from backend.app.agent.schemas.requirements import ServiceRequirements
from backend.app.agent.schemas.resolution import ServiceResolution
from backend.app.agent.schemas.service import ServiceRecord
from backend.app.agent.schemas.source import RetrievedChunk
from backend.app.agent.schemas.browser import BrowserActionRequest, BrowserActionResponse, BrowserObservation


_MODELS: tuple[type[BaseModel], ...] = (
    AgentEvent,
    DocumentMetadata,
    ExtractedField,
    EligibilityResult,
    Intent,
    PlannerResult,
    ServiceRequirements,
    ServiceResolution,
    ServiceRecord,
    RetrievedChunk,
    BrowserActionRequest,
    BrowserActionResponse,
    BrowserObservation,
)
_MODEL_BY_NAME = {f"{model.__module__}.{model.__qualname__}": model for model in _MODELS}
_TAG = "__civicflow_pydantic__"


def _pack(value: Any) -> Any:
    if isinstance(value, BaseModel):
        return {_TAG: f"{type(value).__module__}.{type(value).__qualname__}", "data": _pack(value.model_dump(mode="json"))}
    if isinstance(value, dict):
        return {key: _pack(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_pack(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_pack(item) for item in value)
    return value


def _unpack(value: Any) -> Any:
    if isinstance(value, dict):
        model_name = value.get(_TAG)
        if model_name is not None:
            model = _MODEL_BY_NAME.get(model_name)
            if model is None:
                raise ValueError("Checkpoint contains an unrecognized CivicFlow model")
            return model.model_validate(_unpack(value["data"]))
        return {key: _unpack(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_unpack(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_unpack(item) for item in value)
    return value


class WorkflowSerializer(JsonPlusSerializer):
    """JSON/msgpack checkpoint codec for a fixed allowlist of workflow models."""

    def dumps_typed(self, obj: Any) -> tuple[str, bytes]:
        return super().dumps_typed(_pack(obj))

    def loads_typed(self, data: tuple[str, bytes]) -> Any:
        return _unpack(super().loads_typed(data))
