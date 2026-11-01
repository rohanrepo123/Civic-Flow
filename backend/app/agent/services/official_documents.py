"""Fetch and chunk explicitly configured official service documents."""

from urllib.parse import urlparse

import httpx

from backend.app.agent.schemas.service import ServiceRecord
from backend.app.agent.schemas.source import OfficialSource, RetrievedChunk, SourceVerificationStatus
from backend.app.agent.services.ingestion import SourceIngestionPipeline
from backend.app.agent.services.source_validator import SourceValidator


class OfficialDocumentFetcher:
    """Fetch only HTTPS government documents supplied by the service catalogue."""

    def __init__(self, *, timeout_seconds: float = 20.0, max_bytes: int = 8_000_000) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes
        self._pipeline = SourceIngestionPipeline()
        self._validator = SourceValidator({"gov.in"})

    async def __call__(self, service: ServiceRecord, query: str = "") -> list[RetrievedChunk]:
        del query
        configured_url = service.official_docs_url or service.official_portal
        if configured_url is None or not self._is_allowed_url(str(configured_url)):
            return []
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds, follow_redirects=True) as client:
                response = await client.get(str(configured_url))
                response.raise_for_status()
                final_url = str(response.url)
                if not self._is_allowed_url(final_url) or len(response.content) > self._max_bytes:
                    return []
                content_type = response.headers.get("content-type", "").casefold()
                path = urlparse(final_url).path.casefold()
                document_type = "pdf" if "pdf" in content_type or path.endswith(".pdf") else "html"
                source = self._source(service, final_url, document_type)
                if document_type == "pdf":
                    return self._pipeline.ingest_pdf_bytes(response.content, source)
                return self._pipeline.ingest_html(response.text, source)
        except (httpx.HTTPError, RuntimeError, ValueError):
            return []

    @staticmethod
    def _is_allowed_url(url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.hostname or "").casefold().strip(".")
        return parsed.scheme == "https" and (host == "gov.in" or host.endswith(".gov.in"))

    def _source(self, service: ServiceRecord, url: str, document_type: str) -> OfficialSource:
        source = OfficialSource(
            source_id=f"{service.service_id}:official-document",
            service_id=service.service_id,
            source_title=f"{service.name} official guidance",
            source_url=url,
            publisher=service.department or (urlparse(url).hostname or "Government source"),
            document_type=document_type,
            verification_status=SourceVerificationStatus.UNVERIFIED,
        )
        return self._validator.validate(source)
