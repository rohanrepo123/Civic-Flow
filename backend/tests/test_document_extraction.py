import asyncio
import json

import fitz
import pytest
from pydantic import ValidationError

from backend.app.agent.schemas.documents import (
    DocumentMetadata,
    DocumentStatus,
    FieldComparisonStatus,
)
from backend.app.agent.services.document_extractor import DocumentExtractor


def make_pdf(text: str = "Full Name: Alice Example") -> bytes:
    document = fitz.open()
    page = document.new_page()
    page.insert_text((72, 72), text)
    data = document.tobytes()
    document.close()
    return data


def metadata() -> DocumentMetadata:
    return DocumentMetadata(
        document_id="doc-123",
        owner_id="user-123",
        filename="identity.pdf",
        media_type="application/pdf",
        size_bytes=256,
        status=DocumentStatus.UPLOADED,
    )


class FakeClient:
    def __init__(self, response: str) -> None:
        self.response = response
        self.calls = 0

    async def complete_json(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        assert "never guess missing values" in system_prompt.casefold()
        assert "doc-123" in user_prompt
        return self.response


def output(
    *,
    value: str = "Alice Example",
    confidence: float = 0.99,
    start: int | None = 11,
    end: int | None = 24,
    page_number: int | None = 1,
) -> str:
    return json.dumps(
        {
            "document_type": "identity_proof",
            "classification_confidence": 0.98,
            "fields": [
                {
                    "name": "full_name",
                    "value": value,
                    "confidence": confidence,
                    "page_number": page_number,
                    "text_start": start,
                    "text_end": end,
                }
            ],
            "issues": [],
        }
    )


def test_document_pdf_extraction_tracks_location_without_overwriting_profile() -> None:
    extractor = DocumentExtractor(FakeClient(output()))
    result = asyncio.run(
        extractor.analyze_pdf_bytes(
            document=metadata(),
            pdf_bytes=make_pdf(),
            profile={"full_name": "alice example"},
        )
    )
    assert result.document.document_type == "identity_proof"
    assert result.document.status is DocumentStatus.PROCESSED
    assert result.extracted_fields[0].source_document_id == "doc-123"
    assert result.extracted_fields[0].source_location.page_number == 1
    assert result.extracted_fields[0].source_location.text_start == 11
    assert result.comparisons[0].status is FieldComparisonStatus.MATCH
    assert result.extracted_fields[0].needs_human_review is False
    assert "full_name" not in result.document.model_dump()


def test_conflicting_profile_value_is_flagged_for_human_review() -> None:
    extractor = DocumentExtractor(FakeClient(output(value="Alice Example")))
    result = asyncio.run(
        extractor.analyze_pdf_bytes(
            document=metadata(),
            pdf_bytes=make_pdf(),
            profile={"full_name": "Bob Citizen"},
        )
    )
    assert result.document.status is DocumentStatus.NEEDS_REVIEW
    assert result.comparisons[0].status is FieldComparisonStatus.CONFLICT
    assert result.extracted_fields[0].needs_human_review


@pytest.mark.parametrize(
    ("confidence", "start", "end", "page_number"),
    [(0.4, 11, 23, 1), (0.99, -1, 5, 1), (0.99, 11, 23, 8)],
)
def test_low_confidence_or_invalid_location_requires_review(
    confidence: float,
    start: int,
    end: int,
    page_number: int,
) -> None:
    extractor = DocumentExtractor(FakeClient(output(confidence=confidence, start=start, end=end, page_number=page_number)))
    result = asyncio.run(
        extractor.analyze_pdf_bytes(
            document=metadata(),
            pdf_bytes=make_pdf(),
            profile={},
        )
    )
    assert result.document.status is DocumentStatus.NEEDS_REVIEW
    assert result.extracted_fields[0].needs_human_review
    assert result.issues


def test_scanned_or_empty_pdf_is_not_claimed_as_processed() -> None:
    blank = fitz.open()
    blank.new_page()
    data = blank.tobytes()
    blank.close()
    client = FakeClient("unused")
    result = asyncio.run(
        DocumentExtractor(client).analyze_pdf_bytes(
            document=metadata(), pdf_bytes=data, profile={}
        )
    )
    assert client.calls == 0
    assert result.document.status is DocumentStatus.NEEDS_REVIEW
    assert "OCR is not available" in result.issues[0]


def test_invalid_extracted_confidence_is_rejected() -> None:
    extractor = DocumentExtractor(FakeClient(output(confidence=1.5)))
    with pytest.raises(ValidationError):
        asyncio.run(
            extractor.analyze_pdf_bytes(
                document=metadata(), pdf_bytes=make_pdf(), profile={}
            )
        )
