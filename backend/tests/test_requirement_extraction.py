import asyncio
import json
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from backend.app.agent.schemas.requirements import EligibilityOperator
from backend.app.agent.schemas.source import RetrievedChunk, SourceVerificationStatus
from backend.app.agent.services.requirement_extractor import RequirementExtractor


def make_chunk(
    chunk_id: str = "src-1:p2:0",
    service_id: str = "service-1",
    status: SourceVerificationStatus = SourceVerificationStatus.UNVERIFIED,
) -> RetrievedChunk:
    return RetrievedChunk(
        chunk_id=chunk_id,
        source_id="src-1",
        service_id=service_id,
        source_title="Official guide candidate",
        source_url="https://example.gov.in/guide.pdf",
        page_number=2,
        chunk_index=0,
        text="Applicants must provide a proof of identity.",
        verification_status=status,
    )


class FakeClient:
    def __init__(self, output: str) -> None:
        self.output = output
        self.calls = 0

    async def complete_json(self, *, system_prompt: str, user_prompt: str) -> str:
        self.calls += 1
        assert "Do not infer missing fees" in system_prompt
        assert "src-1:p2:0" in user_prompt
        return self.output


def test_requirements_are_kept_only_with_valid_chunk_citations() -> None:
    output = {
        "service_id": "ignored-untrusted-id",
        "eligibility_rules": [
            {
                "field": "age",
                "operator": "greater_than",
                "value": 18,
                "source_reference": "src-1:p2:0",
            },
            {
                "field": "income",
                "operator": "less_than",
                "value": 100,
                "source_reference": "invented-chunk",
            },
        ],
        "required_documents": [
            {
                "document_type": "identity_proof",
                "mandatory": True,
                "source_reference": "src-1:p2:0",
            }
        ],
        "application_steps": [],
        "fees": {"amount": "500", "currency": "INR", "source_reference": None},
        "uncertainties": [],
        "sources": [
            {
                "source_id": "invented",
                "title": "Fake source",
                "url": "https://fake.example/",
            }
        ],
    }
    extractor = RequirementExtractor(FakeClient(json.dumps(output)))
    result = asyncio.run(extractor.extract(service_id="service-1", chunks=[make_chunk()]))

    assert result.service_id == "service-1"
    assert len(result.eligibility_rules) == 1
    assert result.eligibility_rules[0].operator is EligibilityOperator.GREATER_THAN
    assert len(result.required_documents) == 1
    assert result.fees.amount is None
    assert [source.source_id for source in result.sources] == ["src-1:p2:0"]
    assert result.sources[0].page_number == 2
    assert any("without a valid source citation" in note for note in result.uncertainties)
    assert any("not verified" in note for note in result.uncertainties)


def test_no_relevant_sources_returns_empty_requirements_without_llm_call() -> None:
    client = FakeClient("should not be used")
    result = asyncio.run(
        RequirementExtractor(client).extract(
            service_id="service-1",
            chunks=[make_chunk(service_id="different-service")],
        )
    )
    assert client.calls == 0
    assert not result.required_documents
    assert result.uncertainties


def test_invalid_operator_is_rejected_by_structured_validation() -> None:
    output = {
        "service_id": "service-1",
        "eligibility_rules": [
            {
                "field": "age",
                "operator": "magic_operator",
                "value": 18,
                "source_reference": "src-1:p2:0",
            }
        ],
    }
    with pytest.raises(ValidationError):
        asyncio.run(
            RequirementExtractor(FakeClient(json.dumps(output))).extract(
                service_id="service-1", chunks=[make_chunk()]
            )
        )


def test_invalid_json_is_rejected() -> None:
    with pytest.raises(ValueError, match="invalid JSON"):
        asyncio.run(
            RequirementExtractor(FakeClient("not-json")).extract(
                service_id="service-1", chunks=[make_chunk()]
            )
        )
