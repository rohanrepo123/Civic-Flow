"""Member 2's AI service, exposed through Member 1's versioned contracts."""

from contextlib import asynccontextmanager
import logging
from typing import Any

from fastapi import FastAPI, HTTPException

from civicflow_contracts import CONTRACT_VERSION
from civicflow_contracts.ai import (
    AgentTurnRequest,
    AgentTurnResponse,
    DocumentRequirementsRequest,
    EligibilityRequest,
    EligibilityResult,
    ServiceDiscoveryRequest,
)

from app.member2_runtime import Member2Runtime, reject_authentication_secrets


@asynccontextmanager
async def lifespan(application: FastAPI):
    application.state.member2_runtime = Member2Runtime.create()
    yield


app = FastAPI(title="CivicFlow AI Agent", version="1.0.0", lifespan=lifespan)
logger = logging.getLogger("civicflow.ai_agent")


def runtime() -> Member2Runtime:
    current = getattr(app.state, "member2_runtime", None)
    if current is None:
        current = Member2Runtime.create()
        app.state.member2_runtime = current
    return current


@app.get("/health/live")
async def live() -> dict[str, str]:
    return {"status": "alive", "service": "ai_agent"}


@app.get("/health/ready")
async def ready() -> dict[str, str]:
    agent = runtime()
    return {
        "status": "ready",
        "service": "ai_agent",
        "contract_version": CONTRACT_VERSION,
        "mode": agent.mode(),
    }


@app.get("/internal/v1/agent/capabilities")
async def capabilities() -> dict[str, Any]:
    agent = runtime()
    return {
        "contract_version": CONTRACT_VERSION,
        "mode": agent.mode(),
        "provider": agent.settings.llm_provider,
        "chat_model": agent.settings.ollama_chat_model if agent.settings.llm_provider == "ollama" else agent.settings.openai_model,
        "embedding_model": "BAAI/bge-m3",
        "capabilities": [
            "casual_conversation",
            "intent_understanding",
            "service_discovery",
            "source_grounded_guidance",
            "eligibility_evaluation",
            "document_requirements",
            "form_preparation_advice",
        ],
    }


@app.post("/internal/v1/agent/turn", response_model=AgentTurnResponse)
async def turn(request: AgentTurnRequest) -> AgentTurnResponse:
    context: dict[str, Any] = {}
    if request.sanitized_application_context is not None:
        context = {
            "sanitized_data": request.sanitized_application_context.sanitized_data,
            "applicant": request.sanitized_application_context.applicant.attributes,
        }
    history = [message.model_dump(mode="json") for message in request.history]
    try:
        reject_authentication_secrets(request.message, {"context": context, "history": history})
        return await runtime().turn(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except Exception as exc:
        logger.error("Agent turn failed safely (%s).", type(exc).__name__)
        raise HTTPException(status_code=503, detail="The AI service could not complete this request safely.") from exc


@app.get("/internal/v1/agent/runs/{run_id}")
async def get_run(run_id: str) -> dict[str, Any]:
    result = runtime().runs.get(run_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Agent run not found")
    return {
        "contract_version": CONTRACT_VERSION,
        "run_id": run_id,
        "status": "completed",
        "mode": runtime().mode(),
        "result": result,
    }


@app.post("/internal/v1/agent/eligibility/evaluate", response_model=EligibilityResult)
async def eligibility(request: EligibilityRequest) -> EligibilityResult:
    try:
        return runtime().evaluate_eligibility(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/internal/v1/agent/services/discover")
async def discover(request: ServiceDiscoveryRequest) -> dict[str, Any]:
    try:
        reject_authentication_secrets(request.query, {})
        return await runtime().discover(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/internal/v1/agent/documents/requirements")
async def requirements(request: DocumentRequirementsRequest) -> dict[str, Any]:
    try:
        return await runtime().document_requirements(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
