"""Bounded discovery of relevant documents on official government hosts."""

import hashlib
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from backend.app.agent.schemas.service import ServiceRecord
from backend.app.agent.schemas.source import OfficialSource, RetrievedChunk, SourceVerificationStatus
from backend.app.agent.services.source_pipeline import SourceIngestionPipeline


def is_official_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").casefold().rstrip(".")
        return (parsed.scheme == "https" and parsed.port in (None, 443)
                and not parsed.username and not parsed.password
                and any(host.endswith("." + domain) for domain in ("gov.in", "nic.in")))
    except ValueError:
        return False


class DocumentLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[tuple[str, str]] = []
        self.href: str | None = None
        self.label = ""

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self.href = dict(attrs).get("href")
            self.label = ""

    def handle_data(self, data: str) -> None:
        if self.href:
            self.label += data

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.href:
            self.links.append((self.href, self.label))
            self.href = None


class OfficialDocumentFetcher:
    def __init__(self, *, timeout_seconds: float = 15, max_bytes: int = 8_000_000,
                 max_documents: int = 3, client: httpx.AsyncClient | None = None) -> None:
        self._timeout_seconds = timeout_seconds
        self._max_bytes = max_bytes
        self._max_documents = max_documents
        self._client = client
        self._pipeline = SourceIngestionPipeline()

    _is_allowed_url = staticmethod(is_official_url)

    async def _download(self, client: httpx.AsyncClient, url: str) -> tuple[str, bytes, str]:
        for _ in range(5):
            if not is_official_url(url):
                raise ValueError("Non-official document destination")
            async with client.stream("GET", url, follow_redirects=False, timeout=self._timeout_seconds) as response:
                if response.is_redirect:
                    url = urljoin(url, response.headers.get("location", ""))
                    continue
                response.raise_for_status()
                content_type = response.headers.get("content-type", "").casefold()
                if not any(item in content_type for item in ("html", "pdf", "text/plain")):
                    raise ValueError("Unsupported official document type")
                content = bytearray()
                async for block in response.aiter_bytes():
                    if len(content) + len(block) > self._max_bytes:
                        raise ValueError("Official document exceeds download limit")
                    content.extend(block)
                return url, bytes(content), content_type
        raise ValueError("Too many document redirects")

    async def __call__(self, service: ServiceRecord, query: str = "") -> list[RetrievedChunk]:
        if self._client is not None:
            return await self._fetch(self._client, service, query)
        async with httpx.AsyncClient() as client:
            return await self._fetch(client, service, query)

    async def _fetch(self, client: httpx.AsyncClient, service: ServiceRecord, query: str) -> list[RetrievedChunk]:
        configured = service.official_docs_url or service.official_portal
        if configured is None:
            return []
        queue = [str(configured)]
        visited: set[str] = set()
        chunks: list[RetrievedChunk] = []
        terms = set(re.findall(r"[a-z]{3,}", query.casefold()))
        for _ in range(self._max_documents):
            if not queue:
                break
            url = queue.pop(0)
            if url in visited:
                continue
            visited.add(url)
            try:
                final_url, content, content_type = await self._download(client, url)
                pdf = "pdf" in content_type
                source = OfficialSource(
                    source_id=f"{service.service_id}:doc:{hashlib.sha256(final_url.encode()).hexdigest()[:16]}",
                    service_id=service.service_id, source_title=f"{service.name} official guidance",
                    source_url=final_url, publisher=urlparse(final_url).hostname or "Government",
                    document_type="pdf" if pdf else "html",
                    verification_status=SourceVerificationStatus.VERIFIED,
                )
                if pdf:
                    chunks.extend(self._pipeline.ingest_pdf_bytes(content, source))
                else:
                    html = content.decode("utf-8", errors="replace")
                    chunks.extend(self._pipeline.ingest_html(html, source))
                    links = DocumentLinks()
                    links.feed(html)
                    ranked = []
                    for href, label in links.links:
                        target = urljoin(final_url, href).split("#", 1)[0]
                        words = set(re.findall(r"[a-z]{3,}", (label + " " + href).casefold()))
                        score = len(words & terms) + len(words & {"guidelines", "eligibility", "requirements", "documents", "pdf"})
                        if score and is_official_url(target) and target not in visited:
                            ranked.append((score, target))
                    queue.extend(target for _, target in sorted(ranked, reverse=True) if target not in queue)
            except (httpx.HTTPError, RuntimeError, ValueError):
                continue
        return sorted(chunks, key=lambda chunk: len(terms & set(re.findall(r"[a-z]{3,}", chunk.text.casefold()))), reverse=True)[:12]
