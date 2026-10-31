from fastapi import APIRouter, HTTPException
from app.api.applications import _applications
router = APIRouter()
@router.get("/applications/{application_id}/tracking")
async def tracking(application_id: str):
    r = _applications.get(application_id)
    if not r: raise HTTPException(404, "Application not found")
    return {"application_id": application_id, "status": r["status"], **r.get("tracking", {"demo_mode": True})}
@router.get("/applications/{application_id}/tracking/events")
async def tracking_events(application_id: str):
    r = _applications.get(application_id)
    if not r: raise HTTPException(404, "Application not found")
    return r.get("activity", [])
