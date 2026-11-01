import json
import asyncio
import re
from pathlib import Path
from threading import Lock

from backend.app.agent.schemas.requirements import FeeInformation, RequiredDocument, ServiceRequirements
from backend.app.agent.schemas.source import RetrievedChunk, SourceVerificationStatus
from backend.app.agent.schemas.common import SourceReference
from backend.app.agent.services.embeddings import EmbeddingProvider, build_embedding_provider
from backend.app.agent.services.retrieval import SourceRetriever
from backend.app.agent.services.service_registry import ServiceRegistry


class CuratedKnowledge:
    """Offline retriever over reviewed, attributed source excerpts."""

    def __init__(
        self,
        chunks: list[RetrievedChunk],
        requirements: dict[str, ServiceRequirements],
        embeddings: EmbeddingProvider | None = None,
    ) -> None:
        self._chunks = tuple(chunks)
        self._requirements = requirements
        self._embeddings = embeddings or build_embedding_provider()
        self._retriever: SourceRetriever | None = None
        self._retrieval_lock = Lock()

    @classmethod
    def default(cls, embeddings: EmbeddingProvider | None = None) -> "CuratedKnowledge":
        data_dir = Path(__file__).parent.parent / "data"
        chunks_data = json.loads((data_dir / "curated_chunks.json").read_text(encoding="utf-8"))
        raw_requirements = json.loads((data_dir / "curated_requirements.json").read_text(encoding="utf-8"))
        chunks = [RetrievedChunk.model_validate(row) for row in chunks_data]
        catalog_path = data_dir / "service_catalog.json"
        if catalog_path.is_file():
            for service in ServiceRegistry.from_json(catalog_path).all():
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
        return cls(chunks, requirements, embeddings=embeddings)

    async def retrieve(self, service, query: str) -> list[RetrievedChunk]:
        return await asyncio.to_thread(self._retrieve, service.service_id, query)

    def _retrieve(self, service_id: str, query: str) -> list[RetrievedChunk]:
        with self._retrieval_lock:
            try:
                if self._retriever is None:
                    self._retriever = SourceRetriever(self._embeddings)
                    self._retriever.add_chunks(list(self._chunks))
                hits = self._retriever.retrieve(
                    query,
                    top_k=max(1, len(self._chunks)),
                    service_id=service_id,
                )
                return [hit.chunk for hit in hits]
            except RuntimeError:
                # Chat must remain available when BGE-M3 has not been cached yet.
                # The semantic retriever will be used automatically after the model
                # is downloaded and the service is restarted.
                return self._lexical_retrieve(service_id, query)

    def _lexical_retrieve(self, service_id: str, query: str) -> list[RetrievedChunk]:
        query_terms = set(re.findall(r"[a-z0-9]{3,}", query.casefold()))
        candidates = [chunk for chunk in self._chunks if chunk.service_id == service_id]
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
