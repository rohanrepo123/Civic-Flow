import asyncio

from backend.app.agent.services.curated_knowledge import CuratedKnowledge
from backend.app.agent.services.service_registry import ServiceRegistry


class DeterministicEmbeddings:
    """Small test double: these tests validate citations and requirements, not model quality."""

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [[1.0, 0.0] for _ in texts]


def test_domicile_knowledge_keeps_old_document_list_cited_and_uncertain():
    knowledge = CuratedKnowledge.default(embeddings=DeterministicEmbeddings())
    service = next(item for item in ServiceRegistry.default().all() if item.service_id == "maharashtra_domicile_certificate")
    chunks = asyncio.run(knowledge.retrieve(service, "domicile checklist and fees"))
    requirements = asyncio.run(knowledge.extract(service_id=service.service_id, chunks=chunks))

    assert len(requirements.required_documents) == 6
    assert requirements.fees.amount == 20
    assert requirements.sources
    assert any("older official PDF" in notice for notice in requirements.uncertainties)


def test_scholarship_knowledge_asks_for_exact_scheme_without_invented_rules():
    knowledge = CuratedKnowledge.default(embeddings=DeterministicEmbeddings())
    service = next(item for item in ServiceRegistry.default().all() if item.service_id == "maharashtra_scholarship")
    chunks = asyncio.run(knowledge.retrieve(service, "Maharashtra scholarship"))
    requirements = asyncio.run(knowledge.extract(service_id=service.service_id, chunks=chunks))

    assert not requirements.eligibility_rules
    assert not requirements.required_documents
    assert any("exact scheme" in notice for notice in requirements.uncertainties)
    assert chunks[0].source_url.host == "mahadbt.maharashtra.gov.in"
