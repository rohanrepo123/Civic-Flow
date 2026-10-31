from uuid import uuid4
import pytest
from pydantic import ValidationError
from civicflow_contracts import CONTRACT_VERSION
from civicflow_contracts.common import ApplicationStatus
from civicflow_contracts.ai import AgentTurnRequest
from civicflow_contracts.browser import BrowserSessionCreateRequest, BrowserCommand

def test_contract_metadata_defaults_and_forbids_extra_fields():
    request = AgentTurnRequest(user_id=uuid4(), conversation_id="c1", message="Help me find a service")
    assert request.contract_version == CONTRACT_VERSION
    assert request.correlation_id and request.request_id
    with pytest.raises(ValidationError):
        AgentTurnRequest(user_id=uuid4(), conversation_id="c1", message="hi", unexpected="value")
    with pytest.raises(ValidationError):
        AgentTurnRequest(contract_version="2.0.0", user_id=uuid4(), conversation_id="c1", message="hi")

def test_application_status_is_strict_enum():
    assert ApplicationStatus("waiting_for_approval") is ApplicationStatus.waiting_for_approval
    with pytest.raises(ValueError): ApplicationStatus("accepted")

def test_browser_create_requires_https_and_allowed_domains():
    payload = dict(user_id=uuid4(), application_id=uuid4(), service_id="service-x",
        approved_portal_url="https://portal.example.gov", allowed_domains=["example.gov"])
    assert BrowserSessionCreateRequest(**payload).service_id == "service-x"
    with pytest.raises(ValidationError): BrowserSessionCreateRequest(**{**payload, "approved_portal_url": "http://portal.example.gov"})

def test_browser_command_rejects_unknown_command():
    with pytest.raises(ValidationError): BrowserCommand(command_type="submit")
