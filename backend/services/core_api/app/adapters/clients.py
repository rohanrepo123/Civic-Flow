from __future__ import annotations
from typing import Protocol
from uuid import UUID, uuid4
import httpx
from fastapi import HTTPException
from civicflow_contracts import CONTRACT_VERSION
from civicflow_contracts.ai import AgentTurnRequest, AgentTurnResponse
from civicflow_contracts.browser import BrowserSessionStatus
from app.core.config import settings

class AIServiceClient(Protocol):
    async def health_check(self): ...
    async def create_agent_turn(self, request: AgentTurnRequest) -> AgentTurnResponse: ...
    async def get_agent_run(self, run_id: str): ...
    async def evaluate_eligibility(self, payload: dict): ...
    async def discover_service(self, payload: dict): ...
    async def get_document_requirements(self, payload: dict): ...

class BrowserServiceClient(Protocol):
    async def health_check(self): ...
    async def create_session(self, application_id: str, service_id: str, portal_url: str): ...
    async def get_session(self, session_id: str): ...
    async def send_command(self, session_id: str, command: dict): ...
    async def get_stream_token(self, session_id: str): ...
    async def pause_session(self, session_id: str): ...
    async def resume_session(self, session_id: str): ...
    async def take_control(self, session_id: str): ...
    async def return_control(self, session_id: str): ...
    async def close_session(self, session_id: str): ...

class MockAIServiceClient:
    async def health_check(self): return {"status": "ready", "mode": "deterministic_mock"}
    async def create_agent_turn(self, request):
        return AgentTurnResponse(contract_version=CONTRACT_VERSION, correlation_id=request.correlation_id,
            run_id=str(uuid4()), assistant_message="I can help prepare this service application. Mock mode is active.",
            intent="service_assistance", confidence=0.2, uncertainty=["Deterministic mock response; no model provider configured."], mode="deterministic_mock")
    async def get_agent_run(self, run_id): return {"run_id": run_id, "status": "completed"}
    async def evaluate_eligibility(self, payload): return {"outcome": "unknown", "eligible": None, "reasons": ["Mock evaluation has no configured rules."], "confidence": 0.0}
    async def discover_service(self, payload): return {"results": [], "mode": "deterministic_mock"}
    async def get_document_requirements(self, payload): return {"requirements": [], "mode": "deterministic_mock"}

class MockBrowserServiceClient:
    def __init__(self): self.sessions = {}
    async def health_check(self): return {"status": "ready", "mode": "mock"}
    async def create_session(self, application_id, service_id, portal_url):
        sid = str(uuid4()); self.sessions[sid] = {"browser_session_id": sid, "application_id": application_id, "service_id": service_id, "url": portal_url, "session_status": BrowserSessionStatus.active.value, "contract_version": CONTRACT_VERSION}
        return self.sessions[sid]
    async def get_session(self, session_id):
        if session_id not in self.sessions: raise HTTPException(404, "Browser session not found")
        return self.sessions[session_id]
    async def send_command(self, session_id, command): return {"session": await self.get_session(session_id), "status": "accepted"}
    async def _status(self, sid, status):
        item = await self.get_session(sid); item["session_status"] = status; return item
    async def pause_session(self, sid): return await self._status(sid, "paused")
    async def resume_session(self, sid): return await self._status(sid, "active")
    async def take_control(self, sid): return await self._status(sid, "user_control")
    async def return_control(self, sid): return await self._status(sid, "active")
    async def close_session(self, sid): return await self._status(sid, "closed")

class HTTPServiceClient:
    """Small shared transport with timeouts, correlation headers and version checks."""
    def __init__(self, base_url: str, service_token: str = ""):
        self.base_url = base_url.rstrip("/")
        self.service_token = service_token.strip()
    async def _request(self, method, path, body=None):
        retry_safe = method.upper() in {"GET", "HEAD", "OPTIONS"} or bool((body or {}).get("idempotency_key"))
        headers = {"X-Correlation-ID": str((body or {}).get("correlation_id", uuid4()))}
        if self.service_token:
            headers["Authorization"] = f"Bearer {self.service_token}"
        if (body or {}).get("idempotency_key"):
            headers["Idempotency-Key"] = str(body["idempotency_key"])
        attempts = max(1, settings.SERVICE_RETRY_MAX) if retry_safe else 1
        last_error = None
        for attempt in range(attempts):
            try:
                timeout = max(settings.AI_REQUEST_TIMEOUT, settings.AGENT_TURN_TIMEOUT + 20) if isinstance(self, HTTPAIServiceClient) else settings.SERVICE_REQUEST_TIMEOUT
                async with httpx.AsyncClient(timeout=httpx.Timeout(timeout, connect=10)) as client:
                    response = await client.request(method, f"{self.base_url}{path}", json=body, headers=headers)
                response.raise_for_status(); data = response.json()
                break
            except httpx.HTTPStatusError as exc:
                raise HTTPException(
                    502,
                    f"Downstream service returned HTTP {exc.response.status_code}.",
                ) from exc
            except (httpx.HTTPError, ValueError) as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    raise HTTPException(502, f"Downstream service request failed: {type(exc).__name__}") from exc
        else:
            raise HTTPException(502, f"Downstream service request failed: {type(last_error).__name__}")
        version = data.get("contract_version")
        if path.startswith("/internal/") and version != CONTRACT_VERSION:
            raise HTTPException(502, "Downstream contract version missing or mismatched")
        return data

class HTTPAIServiceClient(HTTPServiceClient):
    async def health_check(self): return await self._request("GET", "/health/ready")
    async def create_agent_turn(self, request): return AgentTurnResponse.model_validate(await self._request("POST", "/internal/v1/agent/turn", request.model_dump(mode="json")))
    async def get_agent_run(self, run_id): return await self._request("GET", f"/internal/v1/agent/runs/{run_id}")
    async def evaluate_eligibility(self, payload): return await self._request("POST", "/internal/v1/agent/eligibility/evaluate", payload)
    async def discover_service(self, payload): return await self._request("POST", "/internal/v1/agent/services/discover", payload)
    async def get_document_requirements(self, payload): return await self._request("POST", "/internal/v1/agent/documents/requirements", payload)

class HTTPBrowserServiceClient(HTTPServiceClient):
    def __init__(self, base_url: str, service_token: str = ""):
        super().__init__(base_url, service_token=service_token)

    async def health_check(self): return await self._request("GET", "/health/ready")
    async def create_session(self, application_id, service_id, portal_url):
        payload = {"contract_version": CONTRACT_VERSION, "correlation_id": str(uuid4()), "user_id": str(uuid4()), "application_id": application_id, "service_id": service_id, "approved_portal_url": portal_url, "allowed_domains": [__import__("urllib.parse", fromlist=["urlparse"]).urlparse(portal_url).hostname], "requested_capabilities": ["navigate", "inspect", "fill_non_sensitive"]}
        return await self._request("POST", "/internal/v1/browser/sessions", payload)
    async def get_session(self, sid): return await self._request("GET", f"/internal/v1/browser/sessions/{sid}")
    async def send_command(self, sid, command): return await self._request("POST", f"/internal/v1/browser/sessions/{sid}/commands", command)
    async def get_stream_token(self, sid): return await self._request("GET", f"/internal/v1/browser/sessions/{sid}/stream-token")
    async def _action(self, sid, action): return await self._request("POST", f"/internal/v1/browser/sessions/{sid}/{action}")
    async def pause_session(self,sid): return await self._action(sid,"pause")
    async def resume_session(self,sid): return await self._action(sid,"resume")
    async def take_control(self,sid): return await self._action(sid,"take-control")
    async def return_control(self,sid): return await self._action(sid,"return-control")
    async def close_session(self,sid): return await self._action(sid,"close")

_ai = None; _browser = None
def get_ai_client():
    global _ai
    if _ai is None: _ai = HTTPAIServiceClient(settings.AI_AGENT_URL) if not settings.USE_MOCK_AI else MockAIServiceClient()
    return _ai
def get_browser_client():
    global _browser
    if _browser is None: _browser = HTTPBrowserServiceClient(settings.BROWSER_AGENT_URL, service_token=settings.BROWSER_AGENT_API_TOKEN) if not settings.USE_MOCK_BROWSER else MockBrowserServiceClient()
    return _browser
