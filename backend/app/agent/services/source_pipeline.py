from pathlib import Path

from backend.app.agent.schemas.source import OfficialSource, RetrievedChunk
from backend.app.agent.services.ingestion import HtmlIngestor, PdfIngestor, TextChunker


class SourceIngestionPipeline:
    def __init__(
        self,
        *,
        pdf_ingestor: PdfIngestor | None = None,
        html_ingestor: HtmlIngestor | None = None,
        chunker: TextChunker | None = None,
    ) -> None:
        self._pdf = pdf_ingestor or PdfIngestor()
        self._html = html_ingestor or HtmlIngestor()
        self._chunker = chunker or TextChunker()

    def ingest_pdf(self, path: Path, source: OfficialSource) -> list[RetrievedChunk]:
        if source.document_type.casefold() != "pdf":
            raise ValueError("source document_type must be 'pdf'")
        return self._chunker.chunk_pages(self._pdf.extract_pages(path), source)

    def ingest_pdf_bytes(self, data: bytes, source: OfficialSource) -> list[RetrievedChunk]:
        if source.document_type.casefold() != "pdf":
            raise ValueError("source document_type must be 'pdf'")
        return self._chunker.chunk_pages(self._pdf.extract_bytes(data), source)

    def ingest_html(self, html: str, source: OfficialSource) -> list[RetrievedChunk]:
        if source.document_type.casefold() not in {"html", "webpage"}:
            raise ValueError("source document_type must be 'html' or 'webpage'")
        return self._chunker.chunk_pages(self._html.extract_pages(html), source)
