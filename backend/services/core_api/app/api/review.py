from fastapi import APIRouter, HTTPException
from app.api.applications import _applications, _now
from civicflow_contracts.application import ReviewUpdateRequest, ApprovalRequest
from civicflow_contracts.common import ApplicationStatus
from app.core.state_machine import validate_transition
router = APIRouter()

@router.get("/applications/{application_id}/review")
async def review(application_id: str):
    record = _applications.get(application_id)
    if not record: raise HTTPException(404, "Application not found")
    return {"application_id": application_id, "items": record["review_state"], "complete": all(record["review_state"].values())}

@router.patch("/applications/{application_id}/review")
async def update_review(application_id: str, body: ReviewUpdateRequest):
    record = _applications.get(application_id)
    if not record: raise HTTPException(404, "Application not found")
    record["review_state"].update(body.items)
    if all(record["review_state"].values()):
        current = ApplicationStatus(record["status"])
        if current == ApplicationStatus.prepared:
            validate_transition(current, ApplicationStatus.validation_complete)
            record["status"] = ApplicationStatus.validation_complete.value
    record["updated_at"] = _now()
    return {"application_id": application_id, "items": record["review_state"], "complete": all(record["review_state"].values())}

@router.post("/applications/{application_id}/approve")
async def approve(application_id: str, body: ApprovalRequest):
    record = _applications.get(application_id)
    if not record or body.application_id != application_id: raise HTTPException(404, "Application not found")
    if not body.approved: raise HTTPException(400, "Explicit approval is required")
    if not all(record["review_state"].values()): raise HTTPException(409, "Complete every review item before approval")
    current = ApplicationStatus(record["status"])
    if current == ApplicationStatus.validation_complete:
        validate_transition(current, ApplicationStatus.waiting_for_approval)
        record["status"] = ApplicationStatus.waiting_for_approval.value
    if ApplicationStatus(record["status"]) != ApplicationStatus.waiting_for_approval:
        raise HTTPException(409, "Application is not awaiting approval")
    validate_transition(ApplicationStatus.waiting_for_approval, ApplicationStatus.approved_for_submission)
    record["status"] = ApplicationStatus.approved_for_submission.value
    record["approval_state"] = "approved"
    record["activity"].append({"id": f"{application_id}-approval", "label": "User approved submission", "timestamp": _now(), "tone": "green"})
    return {"application_id": application_id, "status": record["status"], "approved_at": _now()}
