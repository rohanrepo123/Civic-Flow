from typing import Protocol
from pathlib import Path
from uuid import uuid4
import os

import faiss
import numpy as np

from backend.app.agent.schemas.source import RetrievedChunk, RetrievalHit
from backend.app.agent.services.embeddings import EmbeddingProvider


class VectorIndex(Protocol):
    def add(self, vectors: list[list[float]], chunks: list[RetrievedChunk]) -> None: ...
    def search(self, vector: list[float], limit: int) -> list[tuple[RetrievedChunk, float]]: ...
    def size(self) -> int: ...


class FaissVectorIndex:
    """In-memory cosine-similarity index with stable chunk metadata mapping."""

    def __init__(self) -> None:
        self._index: faiss.Index | None = None
        self._chunks: list[RetrievedChunk] = []

    @staticmethod
    def _normalized(vectors: list[list[float]]) -> np.ndarray:
        matrix = np.asarray(vectors, dtype=np.float32)
        if matrix.ndim != 2 or matrix.shape[1] == 0:
            raise ValueError("embedding vectors must form a non-empty 2D matrix")
        norms = np.linalg.norm(matrix, axis=1, keepdims=True)
        if np.any(norms == 0):
            raise ValueError("zero-length embeddings cannot be indexed")
        return np.ascontiguousarray(matrix / norms)

    def add(self, vectors: list[list[float]], chunks: list[RetrievedChunk]) -> None:
        if len(vectors) != len(chunks):
            raise ValueError("each embedding must correspond to exactly one chunk")
        if not vectors:
            return
        matrix = self._normalized(vectors)
        if self._index is None:
            self._index = faiss.IndexFlatIP(matrix.shape[1])
        elif self._index.d != matrix.shape[1]:
            raise ValueError("embedding dimensions changed within the same index")
        self._index.add(matrix)
        self._chunks.extend(chunks)

    def size(self) -> int:
        return len(self._chunks)

    def save_cache(self, path: Path) -> None:
        if self._index is None:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_suffix(f".{uuid4().hex}.tmp")
        try:
            with temporary.open("wb") as stream:
                np.save(stream, self._index.reconstruct_n(0, self._index.ntotal), allow_pickle=False)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)

    @classmethod
    def from_cache(cls, path: Path, chunks: list[RetrievedChunk]) -> "FaissVectorIndex":
        # Numpy numeric data only: never load pickle or an untrusted FAISS binary.
        matrix = np.load(path, allow_pickle=False)
        if matrix.ndim != 2 or matrix.shape[0] != len(chunks) or not np.isfinite(matrix).all():
            raise ValueError("Invalid cached vectors")
        index = cls()
        index.add(matrix.tolist(), chunks)
        return index

    def search(self, vector: list[float], limit: int) -> list[tuple[RetrievedChunk, float]]:
        if limit <= 0:
            raise ValueError("limit must be positive")
        if self._index is None or not self._chunks:
            return []
        query = self._normalized([vector])
        if query.shape[1] != self._index.d:
            raise ValueError("query embedding dimension does not match indexed vectors")
        scores, indices = self._index.search(query, min(limit, len(self._chunks)))
        return [
            (self._chunks[int(index)], float(score))
            for score, index in zip(scores[0], indices[0], strict=True)
            if index >= 0
        ]


class SourceRetriever:
    def __init__(self, embeddings: EmbeddingProvider, index: VectorIndex | None = None) -> None:
        self._embeddings = embeddings
        self._index = index or FaissVectorIndex()

    def add_chunks(self, chunks: list[RetrievedChunk]) -> None:
        if not chunks:
            return
        vectors = self._embeddings.embed([chunk.text for chunk in chunks])
        self._index.add(vectors, chunks)

    def retrieve(self, query: str, *, top_k: int = 5, service_id: str | None = None) -> list[RetrievalHit]:
        if not query.strip():
            raise ValueError("query must not be empty")
        if top_k <= 0:
            raise ValueError("top_k must be positive")
        query_vectors = self._embeddings.embed([query])
        if len(query_vectors) != 1:
            raise ValueError("embedding provider must return one vector for one query")
        # Search all chunks before filtering by service to avoid hiding a valid match.
        matches = self._index.search(query_vectors[0], self._index_size())
        filtered = [
            RetrievalHit(chunk=chunk, score=score)
            for chunk, score in matches
            if service_id is None or chunk.service_id == service_id
        ]
        return filtered[:top_k]

    def _index_size(self) -> int:
        return max(1, self._index.size())
