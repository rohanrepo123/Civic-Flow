from fastapi import APIRouter, HTTPException
from civicflow_contracts.browser import BrowserCommand
from app.api.applications import _applications
from app.adapters.clients import get_browser_client
from app.api.services import _SERVICE_CATALOG
router = APIRouter()

@router.get("/browser/health")
async def browser_health():
    return await get_browser_client().health_check()

@router.post("/applications/{application_id}/browser-sessions")
async def create_session(application_id: str):
    record = _applications.get(application_id)
    if not record: raise HTTPException(404, "Application not found")
    service_id = record["service_id"]
    service = next((item for item in _SERVICE_CATALOG if item["id"] == service_id), None)
    portal = service.get("official_url") if service else None
    if not portal: raise HTTPException(409, "This service has no approved portal URL")
    return await get_browser_client().create_session(application_id, service_id, portal)

@router.get("/browser-sessions/{session_id}")
async def get_session(session_id: str): return await get_browser_client().get_session(session_id)

@router.get("/browser-sessions/{session_id}/stream-token")
async def stream_token(session_id: str):
    client = get_browser_client()
    if not hasattr(client, "get_stream_token"):
        raise HTTPException(503, "Browser streaming is unavailable")
    return await client.get_stream_token(session_id)

@router.post("/browser-sessions/{session_id}/commands")
async def send_command(session_id: str, command: BrowserCommand):
    return await get_browser_client().send_command(session_id, command.model_dump(mode="json"))

@router.post("/browser-sessions/{session_id}/{action}")
async def session_action(session_id: str, action: str):
    methods = {"pause": "pause_session", "resume": "resume_session", "take-control": "take_control", "return-control": "return_control"}
    if action not in methods: raise HTTPException(404, "Unknown browser action")
    return await getattr(get_browser_client(), methods[action])(session_id)
