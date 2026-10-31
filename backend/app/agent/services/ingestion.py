from dataclasses import dataclass
from collections.abc import Iterable
import re
from typing import Any
import unicodedata
from html.parser import HTMLParser
from pathlib import Path

from backend.app.agent.schemas.source import OfficialSource, RetrievedChunk


@dataclass(frozen=True)
class PageText:
    page_number: int | None
    text: str


class _VisibleTextParser(HTMLParser):
    _ignored_tags = {"script", "style", "noscript", "svg", "template"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.casefold() in self._ignored_tags:
            self._ignored_depth += 1
        elif tag.casefold() in {"p", "br", "div", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag: str) -> None:
        normalized_tag = tag.casefold()
        if normalized_tag in self._ignored_tags and self._ignored_depth:
            self._ignored_depth -= 1
        elif normalized_tag in {"p", "div", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data: str) -> None:
        if self._ignored_depth == 0:
            self.parts.append(data)


def clean_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).replace("\u00ad", "")
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")
    normalized = re.sub(r"[\t\f\v ]+", " ", normalized)
    normalized = re.sub(r" *\n *", "\n", normalized)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


class PdfIngestor:
    def extract_pages(self, path: Path) -> list[PageText]:
        try:
            import fitz
        except ImportError as exc:  # pragma: no cover - exercised in minimal installs
            raise RuntimeError("PDF ingestion requires the 'rag' project extra") from exc
        if not path.is_file():
            raise FileNotFoundError(path)
        with fitz.open(path) as document:
            return self._extract_document(document)

    def extract_bytes(self, data: bytes) -> list[PageText]:
        try:
            import fitz
        except ImportError as exc:  # pragma: no cover - exercised in minimal installs
            raise RuntimeError("PDF ingestion requires the 'rag' project extra") from exc
        if not data:
            raise ValueError("PDF bytes must not be empty")
        with fitz.open(stream=data, filetype="pdf") as document:
            return self._extract_document(document)

    @staticmethod
    def _extract_document(document: Iterable[Any]) -> list[PageText]:
        pages: list[PageText] = []
        for index, page in enumerate(document):
            content = clean_text(page.get_text("text"))
            if content:
                pages.append(PageText(page_number=index + 1, text=content))
        return pages


class HtmlIngestor:
    def extract_pages(self, html: str) -> list[PageText]:
        parser = _VisibleTextParser()
        parser.feed(html)
        parser.close()
        text = clean_text("".join(parser.parts))
        return [PageText(page_number=None, text=text)] if text else []


class TextChunker:
    def __init__(self, *, chunk_size: int = 1200, overlap: int = 160) -> None:
        if chunk_size <= 0 or overlap < 0 or overlap >= chunk_size:
            raise ValueError("chunk_size must be positive and overlap must be in [0, chunk_size)")
        self.chunk_size = chunk_size
        self.overlap = overlap

    def chunk_pages(
        self,
        pages: list[PageText],
        source: OfficialSource,
    ) -> list[RetrievedChunk]:
        chunks: list[RetrievedChunk] = []
        step = self.chunk_size - self.overlap
        for page in pages:
            text = clean_text(page.text)
            start = 0
            while start < len(text):
                end = min(start + self.chunk_size, len(text))
                content = text[start:end].strip()
                if content:
                    index = len(chunks)
                    chunks.append(
                        RetrievedChunk(
                            chunk_id=f"{source.source_id}:{page.page_number or 'html'}:{index}",
                            source_id=source.source_id,
                            service_id=source.service_id,
                            source_title=source.source_title,
                            source_url=source.source_url,
                            page_number=page.page_number,
                            chunk_index=index,
                            text=content,
                            verification_status=source.verification_status,
                        )
                    )
                if end >= len(text):
                    break
                start += step
        return chunks
