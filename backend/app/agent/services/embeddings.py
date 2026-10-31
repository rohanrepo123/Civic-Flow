"""Local BGE-M3 embeddings with an explicit, optional API-compatible adapter."""

from dataclasses import dataclass
import os
from typing import Protocol

import httpx


class EmbeddingProvider(Protocol):
    def embed(self, texts: list[str]) -> list[list[float]]: ...


@dataclass(frozen=True)
class EmbeddingSettings:
    provider: str
    model: str
    api_key: str = ""
    endpoint_url: str = ""
    device: str = "auto"
    batch_size: int = 16
    local_files_only: bool = True

    @classmethod
    def from_environment(cls) -> "EmbeddingSettings | None":
        names = (
            "EMBEDDING_PROVIDER", "EMBEDDING_MODEL", "EMBEDDING_API_KEY", "EMBEDDING_URL",
            "EMBEDDING_DEVICE", "EMBEDDING_BATCH_SIZE",
        )
        if not any(os.getenv(name, "").strip() for name in names):
            return None
        provider = os.getenv("EMBEDDING_PROVIDER", "sentence_transformers").strip().lower()
        model = os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3").strip()
        if provider == "sentence_transformers":
            if not model:
                raise ValueError("EMBEDDING_MODEL must name a Sentence Transformers model")
            return cls(
                provider=provider,
                model=model,
                device=os.getenv("EMBEDDING_DEVICE", "auto").strip().lower() or "auto",
                batch_size=_batch_size(),
                local_files_only=os.getenv("EMBEDDING_ALLOW_DOWNLOAD", "false").strip().lower()
                not in {"1", "true", "yes"},
            )
        api_key = os.getenv("EMBEDDING_API_KEY", "").strip()
        endpoint = os.getenv("EMBEDDING_URL", "").strip()
        if not (model and api_key and endpoint):
            raise ValueError(
                "API embedding configuration is incomplete; set EMBEDDING_MODEL, "
                "EMBEDDING_API_KEY, and EMBEDDING_URL"
            )
        return cls(provider=provider, model=model, api_key=api_key, endpoint_url=endpoint)


def _batch_size() -> int:
    try:
        value = int(os.getenv("EMBEDDING_BATCH_SIZE", "16"))
    except ValueError as exc:
        raise ValueError("EMBEDDING_BATCH_SIZE must be a positive integer") from exc
    if value <= 0:
        raise ValueError("EMBEDDING_BATCH_SIZE must be a positive integer")
    return value


class BgeM3EmbeddingProvider:
    """Lazy, reusable BGE-M3 encoder; no model download occurs unless explicitly enabled."""

    def __init__(self, settings: EmbeddingSettings | None = None) -> None:
        self._settings = settings or EmbeddingSettings(
            provider="sentence_transformers", model="BAAI/bge-m3"
        )
        if self._settings.provider != "sentence_transformers":
            raise ValueError("BgeM3EmbeddingProvider requires sentence_transformers settings")
        self._model = None

    def _load_model(self):
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
            except ImportError as exc:
                raise RuntimeError(
                    "BGE-M3 needs the optional embeddings dependencies. Install with "
                    "python -m pip install -e '.[embeddings]' and download it with "
                    "python -m backend.app.agent.services.embeddings --download-model."
                ) from exc
            device = self._settings.device
            if device == "auto":
                try:
                    import torch
                    device = "cuda" if torch.cuda.is_available() else "cpu"
                except ImportError:
                    device = "cpu"
            try:
                self._model = SentenceTransformer(
                    self._settings.model,
                    device=device,
                    local_files_only=self._settings.local_files_only,
                    trust_remote_code=False,
                )
            except Exception as exc:
                if self._settings.local_files_only:
                    raise RuntimeError(
                        f"Embedding model {self._settings.model!r} is not cached locally. "
                        "Run `python -m backend.app.agent.services.embeddings --download-model` "
                        "once while online, then restart CivicFlow."
                    ) from exc
                raise
        return self._model

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        if any(not isinstance(text, str) for text in texts):
            raise ValueError("embedding inputs must be strings")
        model = self._load_model()
        vectors = model.encode(
            texts,
            batch_size=self._settings.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        if getattr(vectors, "ndim", None) != 2 or vectors.shape[0] != len(texts):
            raise ValueError("BGE-M3 returned an invalid embedding matrix")
        result = vectors.tolist()
        dimensions = {len(vector) for vector in result}
        if len(dimensions) != 1 or not dimensions.pop():
            raise ValueError("BGE-M3 returned inconsistent or empty embeddings")
        return [[float(value) for value in vector] for vector in result]


class HttpEmbeddingProvider:
    """Client for a specifically configured OpenAI-compatible embeddings endpoint."""

    def __init__(self, settings: EmbeddingSettings, *, timeout_seconds: float = 60) -> None:
        self._settings = settings
        self._timeout_seconds = timeout_seconds

    def embed(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = httpx.post(
            self._settings.endpoint_url,
            headers={"Authorization": f"Bearer {self._settings.api_key}"},
            json={"model": self._settings.model, "input": texts},
            timeout=self._timeout_seconds,
        )
        response.raise_for_status()
        try:
            rows = response.json()["data"]
            ordered = sorted(rows, key=lambda row: row["index"])
            vectors = [row["embedding"] for row in ordered]
        except (KeyError, TypeError) as exc:
            raise ValueError("embedding response did not match the configured API contract") from exc
        if len(vectors) != len(texts) or any(not isinstance(vector, list) for vector in vectors):
            raise ValueError("embedding response count or vector type is invalid")
        if any(not all(isinstance(value, (int, float)) for value in vector) for vector in vectors):
            raise ValueError("embedding response contains a non-numeric vector value")
        dimensions = {len(vector) for vector in vectors}
        if len(dimensions) != 1 or 0 in dimensions:
            raise ValueError("embedding vectors must have one consistent non-zero dimension")
        return [[float(value) for value in vector] for vector in vectors]


def build_embedding_provider(settings: EmbeddingSettings | None = None) -> EmbeddingProvider:
    configuration = settings or EmbeddingSettings.from_environment() or EmbeddingSettings(
        provider="sentence_transformers", model="BAAI/bge-m3"
    )
    if configuration.provider == "sentence_transformers":
        return BgeM3EmbeddingProvider(configuration)
    if configuration.provider in {"openai", "openai_compatible"}:
        return HttpEmbeddingProvider(configuration)
    raise ValueError("EMBEDDING_PROVIDER must be 'sentence_transformers' or an API provider")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Prepare the configured local embedding model")
    parser.add_argument("--download-model", action="store_true", help="download BGE-M3 into the local model cache")
    arguments = parser.parse_args()
    if not arguments.download_model:
        parser.error("pass --download-model to explicitly download BGE-M3")
    configuration = EmbeddingSettings.from_environment() or EmbeddingSettings(
        provider="sentence_transformers", model="BAAI/bge-m3", local_files_only=False
    )
    if configuration.provider != "sentence_transformers":
        parser.error("model download applies only to EMBEDDING_PROVIDER=sentence_transformers")
    configuration = EmbeddingSettings(
        provider=configuration.provider,
        model=configuration.model,
        device=configuration.device,
        batch_size=configuration.batch_size,
        local_files_only=False,
    )
    BgeM3EmbeddingProvider(configuration)._load_model()
    print(f"Cached embedding model {configuration.model}")
