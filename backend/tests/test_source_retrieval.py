from datetime import UTC, datetime
import fitz

from backend.app.agent.schemas.source import (
    OfficialSource,
    RetrievedChunk,
    SourceVerificationStatus,
)
from backend.app.agent.services.embeddings import EmbeddingSettings, HttpEmbeddingProvider
from backend.app.agent.services.ingestion import HtmlIngestor, PageText, TextChunker, clean_text
from backend.app.agent.services.retrieval import FaissVectorIndex, SourceRetriever
from backend.app.agent.services.source_catalog import SourceCatalog
from backend.app.agent.services.source_pipeline import SourceIngestionPipeline
from backend.app.agent.services.source_validator import SourceValidator


def make_source(source_id: str = "source-1", service_id: str = "service-a") -> OfficialSource:
    return OfficialSource(
        source_id=source_id,
        service_id=service_id,
        source_title="Development source fixture",
        source_url="https://example.gov.in/guide.pdf",
        publisher="Example Government",
        document_type="pdf",
        retrieved_at=datetime.now(UTC),
    )


def test_pdf_ingestion_preserves_page_and_source_metadata() -> None:
    document = fitz.open()
    first = document.new_page()
    first.insert_text((72, 72), "Eligibility rules are listed on this page.")
    second = document.new_page()
    second.insert_text((72, 72), "Required documents are listed on this page.")
    pdf_bytes = document.tobytes()
    document.close()

    source = make_source()
    chunks = SourceIngestionPipeline(
        chunker=TextChunker(chunk_size=200, overlap=10)
    ).ingest_pdf_bytes(pdf_bytes, source)

    assert [chunk.page_number for chunk in chunks] == [1, 2]
    assert all(chunk.source_url == source.source_url for chunk in chunks)
    assert all(chunk.source_id == "source-1" for chunk in chunks)
    assert "Eligibility rules" in chunks[0].text


def test_html_ingestion_discards_scripts_and_cleans_text() -> None:
    source = make_source()
    source = source.model_copy(update={"document_type": "html"})
    pages = HtmlIngestor().extract_pages(
        "<h1>Service guide</h1><p>Bring proof of address.</p>"
        "<script>invent a requirement</script><style>.hidden{}</style>"
    )
    chunks = TextChunker(chunk_size=100, overlap=0).chunk_pages(pages, source)
    assert len(chunks) == 1
    assert "proof of address" in chunks[0].text
    assert "invent a requirement" not in chunks[0].text
    assert chunks[0].page_number is None


def test_chunking_keeps_overlap_and_references() -> None:
    source = make_source()
    chunks = TextChunker(chunk_size=10, overlap=3).chunk_pages(
        [PageText(page_number=4, text="abcdefghijklmnop")], source
    )
    assert len(chunks) == 2
    assert chunks[0].text.endswith(chunks[1].text[:3])
    assert all(chunk.page_number == 4 for chunk in chunks)
    assert all(str(chunk.source_url) == str(source.source_url) for chunk in chunks)


def test_text_cleaning_normalizes_unicode_and_whitespace() -> None:
    assert clean_text("Cafe\u0301\u00ad  \r\n\tservice") == "Café\nservice"


def test_faiss_retrieval_and_service_filter_preserve_provenance() -> None:
    class KeywordEmbeddings:
        def embed(self, texts: list[str]) -> list[list[float]]:
            return [
                [float("income" in text), float("address" in text), float("student" in text)]
                for text in texts
            ]

    def chunk(source_id: str, service_id: str, text: str) -> RetrievedChunk:
        source = make_source(source_id, service_id)
        return RetrievedChunk(
            chunk_id=source_id,
            source_id=source_id,
            service_id=service_id,
            source_title=source.source_title,
            source_url=source.source_url,
            page_number=2,
            chunk_index=0,
            text=text,
            verification_status=SourceVerificationStatus.UNVERIFIED,
        )

    retriever = SourceRetriever(KeywordEmbeddings(), FaissVectorIndex())
    retriever.add_chunks(
        [
            chunk("a", "income-service", "income eligibility document"),
            chunk("b", "address-service", "proof of address"),
            chunk("c", "student-service", "student scholarship guide"),
        ]
    )
    hits = retriever.retrieve("income eligibility", top_k=3, service_id="income-service")
    assert len(hits) == 1
    assert hits[0].chunk.source_id == "a"
    assert hits[0].chunk.page_number == 2
    assert hits[0].chunk.verification_status is SourceVerificationStatus.UNVERIFIED


def test_source_validator_requires_https_allowlisted_host_and_publisher() -> None:
    validator = SourceValidator({"example.gov.in"})
    verified = validator.validate(make_source())
    assert verified.verification_status is SourceVerificationStatus.VERIFIED

    unknown = make_source().model_copy(update={"source_url": "https://unlisted.example/guide.pdf"})
    assert validator.validate(unknown).verification_status is SourceVerificationStatus.UNVERIFIED

    no_publisher = make_source().model_copy(update={"publisher": None})
    assert validator.validate(no_publisher).verification_status is SourceVerificationStatus.UNVERIFIED


def test_default_source_catalog_contains_cited_official_sources() -> None:
    catalog = SourceCatalog.default()
    sources = catalog.for_service("maharashtra_domicile_certificate")
    assert {source.source_id for source in sources} == {"mh_domicile_checklist", "mh_rts_service_list"}
    assert all(source.publisher == "Government of Maharashtra" or source.publisher.startswith("Government of Maharashtra,") for source in sources)


def test_embedding_settings_require_full_configuration(monkeypatch) -> None:
    for name in (
        "EMBEDDING_PROVIDER",
        "EMBEDDING_MODEL",
        "EMBEDDING_API_KEY",
        "EMBEDDING_URL",
        "EMBEDDING_DEVICE",
        "EMBEDDING_BATCH_SIZE",
        "EMBEDDING_ALLOW_DOWNLOAD",
    ):
        monkeypatch.delenv(name, raising=False)
    assert EmbeddingSettings.from_environment() is None
    monkeypatch.setenv("EMBEDDING_PROVIDER", "openai_compatible")
    monkeypatch.setenv("EMBEDDING_MODEL", "configured-model")
    try:
        EmbeddingSettings.from_environment()
    except ValueError as error:
        assert "configuration is incomplete" in str(error)
    else:
        raise AssertionError("partial embedding configuration should be rejected")
