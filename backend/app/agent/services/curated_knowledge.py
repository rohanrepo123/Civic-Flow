import json
import asyncio
import re
import hashlib
import os
from pathlib import Path
from threading import Lock

from backend.app.agent.schemas.requirements import FeeInformation, RequiredDocument, ServiceRequirements
from backend.app.agent.schemas.source import RetrievedChunk, SourceVerificationStatus
from backend.app.agent.schemas.common import SourceReference
from backend.app.agent.services.embeddings import EmbeddingProvider, build_embedding_provider
from backend.app.agent.services.retrieval import SourceRetriever, FaissVectorIndex
from backend.app.agent.services.service_registry import ServiceRegistry


class CuratedKnowledge:
    """Offline retriever over reviewed, attributed source excerpts."""

    def __init__(
        self,
        chunks: list[RetrievedChunk],
        requirements: dict[str, ServiceRequirements],
        embeddings: EmbeddingProvider | None = None,
        cache_path: Path | None = None,
    ) -> None:
        self._chunks = tuple(chunks)
        self._requirements = requirements
        self._embeddings = embeddings or build_embedding_provider()
        self._retriever: SourceRetriever | None = None
        self._retrieval_lock = Lock()
        self._cache_path = cache_path

    @classmethod
    def default(cls, embeddings: EmbeddingProvider | None = None, registry: ServiceRegistry | None = None) -> "CuratedKnowledge":
        data_dir = Path(__file__).parent.parent / "data"
        chunks_data = json.loads((data_dir / "curated_chunks.json").read_text(encoding="utf-8"))
        raw_requirements = json.loads((data_dir / "curated_requirements.json").read_text(encoding="utf-8"))
        chunks = [RetrievedChunk.model_validate(row) for row in chunks_data]
        if registry is None:
            registry = ServiceRegistry.default()
        if registry:
            for service in registry.all():
                source_url = service.official_docs_url or service.official_portal
                if source_url is None:
                    continue
                chunks.append(
                    RetrievedChunk(
                        chunk_id=f"{service.service_id}:catalog",
                        source_id=f"{service.service_id}:catalog",
                        service_id=service.service_id,
                        source_title=service.name,
                        source_url=source_url,
                        chunk_index=0,
                        text=(
                            f"{service.name}. Category: {service.category.value}. "
                            f"Jurisdiction: {service.jurisdiction}. {service.description} "
                            f"Official portal: {service.official_portal or 'not provided'}. "
                            f"Official documentation: {service.official_docs_url or 'not provided'}."
                        ),
                        verification_status=SourceVerificationStatus.UNVERIFIED,
                    )
                )
        requirements = {
            service_id: ServiceRequirements.model_validate(row)
            for service_id, row in raw_requirements.items()
        }
        cache_path = None
        if embeddings is None:
            fingerprint = json.dumps({"chunks": [chunk.model_dump(mode="json") for chunk in chunks],
                "provider": os.getenv("EMBEDDING_PROVIDER", "sentence_transformers"),
                "model": os.getenv("EMBEDDING_MODEL", "BAAI/bge-m3"),
                "endpoint": os.getenv("EMBEDDING_URL", ""), "format": 1}, sort_keys=True)
            digest = hashlib.sha256(fingerprint.encode()).hexdigest()
            directory = Path(os.getenv("CIVICFLOW_VECTOR_CACHE_DIR") or Path(__file__).resolve().parents[4] / "runtime" / "vectors")
            cache_path = directory / f"catalogue-{digest}.npy"
        return cls(chunks, requirements, embeddings=embeddings, cache_path=cache_path)

    async def retrieve(self, service, query: str) -> list[RetrievedChunk]:
        return await asyncio.to_thread(self._retrieve, service.service_id, query)

    async def search_catalog(self, query: str) -> list[RetrievedChunk]:
        """Search across services before the orchestrator selects a service."""
        chunks = await asyncio.to_thread(self._retrieve, None, query)
        semantic = [chunk for chunk in chunks if chunk.chunk_id.endswith(":catalog")]
        terms = set(re.findall(r"[a-z0-9]{2,}", query.casefold()))
        lexical = sorted(semantic, key=lambda chunk: len(terms & set(re.findall(r"[a-z0-9]{2,}", chunk.text.casefold()))), reverse=True)
        merged = {chunk.chunk_id: chunk for chunk in lexical[:3] + semantic[:8]}
        return list(merged.values())[:8]

    def _retrieve(self, service_id: str | None, query: str) -> list[RetrievedChunk]:
        with self._retrieval_lock:
            try:
                if self._retriever is None:
                    index = None
                    if self._cache_path and self._cache_path.is_file():
                        try:
                            index = FaissVectorIndex.from_cache(self._cache_path, list(self._chunks))
                        except (ValueError, OSError):
                            index = None
                    retriever = SourceRetriever(self._embeddings, index=index)
                    if index is None:
                        index = FaissVectorIndex()
                        retriever = SourceRetriever(self._embeddings, index=index)
                        retriever.add_chunks(list(self._chunks))
                        if self._cache_path:
                            try:
                                index.save_cache(self._cache_path)
                            except OSError:
                                pass  # A read-only cache directory must not break retrieval.
                    self._retriever = retriever
                hits = self._retriever.retrieve(
                    query,
                    top_k=max(1, len(self._chunks)),
                    service_id=service_id,
                )
                chunks = [hit.chunk for hit in hits]
                if service_id is not None:
                    chunks.sort(key=lambda chunk: chunk.chunk_id.endswith(":catalog"))
                return chunks
            except RuntimeError:
                # Chat must remain available when BGE-M3 has not been cached yet.
                # The semantic retriever will be used automatically after the model
                # is downloaded and the service is restarted.
                return self._lexical_retrieve(service_id, query)

    def _lexical_retrieve(self, service_id: str | None, query: str) -> list[RetrievedChunk]:
        query_terms = set(re.findall(r"[a-z0-9]{3,}", query.casefold()))
        candidates = [chunk for chunk in self._chunks if service_id is None or chunk.service_id == service_id]
        ranked = sorted(
            candidates,
            key=lambda chunk: (
                len(query_terms & set(re.findall(r"[a-z0-9]{3,}", f"{chunk.source_title} {chunk.text}".casefold()))),
                chunk.verification_status is SourceVerificationStatus.VERIFIED,
            ),
            reverse=True,
        )
        return ranked

    async def extract(self, *, service_id: str, chunks: list[RetrievedChunk]) -> ServiceRequirements:
        selected = self._requirements.get(service_id)
        if selected is None:
            return ServiceRequirements(service_id=service_id, uncertainties=["No reviewed requirements are available for this service."])
        available_ids = {chunk.chunk_id for chunk in chunks if chunk.service_id == service_id}
        cited_ids = {
            item.source_reference
            for item in [*selected.eligibility_rules, *selected.required_documents, *selected.application_steps]
            if item.source_reference
        }
        if selected.fees.source_reference:
            cited_ids.add(selected.fees.source_reference)
        if not cited_ids.issubset(available_ids):
            return ServiceRequirements(service_id=service_id, uncertainties=["Reviewed requirements could not be matched to the retrieved source excerpts."])
        result = selected.model_copy(deep=True)
        source_by_chunk = {chunk.chunk_id: chunk for chunk in chunks}
        result.sources = [
            SourceReference(source_id=chunk.chunk_id, title=chunk.source_title, url=chunk.source_url)
            for chunk in chunks
            if chunk.service_id == service_id
        ]
        if any(source_by_chunk[item].verification_status is not SourceVerificationStatus.VERIFIED for item in cited_ids):
            result.uncertainties.append("One or more supporting source excerpts are stale or require confirmation against the current portal.")
        return result
