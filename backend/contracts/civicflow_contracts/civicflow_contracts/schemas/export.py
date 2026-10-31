"""Regenerate checked-in JSON Schema artifacts with `python -m civicflow_contracts.schemas.export`."""
import json
from pathlib import Path
from civicflow_contracts.ai import (AgentTurnRequest, AgentTurnResponse, EligibilityRequest,
    EligibilityResult, DocumentRequirementsRequest, ServiceDiscoveryRequest)
from civicflow_contracts.application import (ApplicationContext, ApplicationStatusEvent,
    ServiceContext, ServiceSummary, SubmissionEvidence)
from civicflow_contracts.browser import (BrowserCommand, BrowserEvent, BrowserSessionCreateRequest,
    BrowserSessionResponse, SensitiveFieldNotice)
from civicflow_contracts.common import ErrorResponse, EventEnvelope

MODELS = [AgentTurnRequest, AgentTurnResponse, EligibilityRequest, EligibilityResult,
    DocumentRequirementsRequest, ServiceDiscoveryRequest, ApplicationContext,
    ApplicationStatusEvent, ServiceContext, ServiceSummary, SubmissionEvidence,
    BrowserCommand, BrowserEvent, BrowserSessionCreateRequest, BrowserSessionResponse,
    SensitiveFieldNotice, ErrorResponse, EventEnvelope]

def export():
    root = Path(__file__).parent
    for model in MODELS:
        (root / f"{model.__name__}.schema.json").write_text(
            json.dumps(model.model_json_schema(), indent=2) + "\n", encoding="utf-8")

if __name__ == "__main__": export()
