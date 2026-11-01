from uuid import UUID
from fastapi import APIRouter, HTTPException, Depends
from app.core.chat_identity import chat_identity
from civicflow_contracts.application import AssistantMessageRequest, ServiceSummary
from civicflow_contracts.ai import AgentMessage, AgentTurnRequest, ServiceContext
from civicflow_contracts.common import CONTRACT_VERSION
from app.api.applications import _applications
from app.api.services import _SERVICE_CATALOG
from app.adapters.clients import get_ai_client
router = APIRouter()

@router.get("/assistant/session")
async def assistant_session(identity: UUID = Depends(chat_identity)):
    return {"scope": str(identity)}

@router.post("/assistant/messages")
async def assistant_message(body: AssistantMessageRequest, identity: UUID = Depends(chat_identity)):
    record = _applications.get(body.application_id) if body.application_id else None
    if body.application_id and not record: raise HTTPException(404, "Application not found")
    ctx = None
    if record is not None:
        service = next((item for item in _SERVICE_CATALOG if item["id"] == record["service_id"]), None)
        if service is not None:
            portal_url = service.get("official_url")
            from urllib.parse import urlparse

            hostname = urlparse(portal_url).hostname if portal_url else None
            ctx = ServiceContext(
                service=ServiceSummary(
                    service_id=record["service_id"],
                    name=service["title"],
                    category=service["category"].value,
                    description=service.get("description", ""),
                    jurisdiction=service.get("jurisdiction") or "",
                    portal_url=portal_url,
                    allowed_domains=[hostname] if hostname else [],
                ),
                required_documents=service.get("required_documents", []),
                source_urls=[portal_url] if portal_url and portal_url.startswith("https://") else [],
            )
    req = AgentTurnRequest(contract_version=CONTRACT_VERSION, user_id=identity, conversation_id=body.conversation_id,
        message=body.message, selected_service_context=ctx,
        sanitized_application_context=None, allowed_actions=[],
        history=[AgentMessage(role=item.role, content=item.content) for item in body.history[-12:]])
    result = await get_ai_client().create_agent_turn(req)
    return {"message": result.assistant_message, "run_id": result.run_id, "mode": result.mode,
        "intent": result.intent, "source_citations": result.source_citations,
        "proposed_next_action": result.proposed_next_action,
        "missing_information": result.missing_information}

@router.post("/eligibility/evaluate")
async def evaluate_eligibility():
    return {"outcome": "unknown", "eligible": None, "reasons": ["Provide service and applicant context to evaluate eligibility."], "confidence": 0.0}
