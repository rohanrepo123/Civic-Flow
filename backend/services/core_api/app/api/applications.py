"""Application CRUD endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, status

from civicflow_contracts.application import (
    ApplicationDetail,
    ApplicationSummary,
    CreateApplicationRequest,
    UpdateApplicationRequest,
    ActivityEvent,
    TrackingInfo,
    DocumentRequirement,
    CustomApplicationRequest, CustomApplicationResponse,
)
from civicflow_contracts.common import ApplicationStatus, DocumentStatus
from app.core.state_machine import validate_transition, InvalidTransitionError
from app.api.services import _SERVICE_CATALOG

from urllib.parse import urlparse
from app.api.geo import _CACHED_STATES

router = APIRouter()

# In-memory store (replaced by PostgreSQL in Phase 3)
_applications: dict[str, dict] = {}

# Mimics the frontend's default documents for post-matric-scholarship
_DEFAULT_DOCUMENTS = {
    "post-matric-scholarship": ["Aadhaar Card", "Income Certificate", "Previous Marksheet"],
    "mock-citizen-certificate": ["Identity Proof", "Address Proof", "Income Declaration"],
}

@router.post("/custom", response_model=CustomApplicationResponse, status_code=status.HTTP_201_CREATED)
async def create_custom_application(body: CustomApplicationRequest):
    """Create a discovery-first application with resolved jurisdiction portal URL."""
    app_id = _make_id()
    ts = _now()

    # Resolve portal URL if not explicitly provided
    portal_url = body.portal_url
    if not portal_url and body.state_code:
        st_match = next((s for s in _CACHED_STATES if s["state_code"].lower() == body.state_code.lower()), None)
        if st_match and st_match.get("primary_portal_url"):
            portal_url = st_match["primary_portal_url"]

    allowed = []
    if portal_url:
        h = urlparse(portal_url).hostname
        if h:
            allowed.append(h)

    _applications[app_id] = {
        "id": app_id, "service_id": "custom-request", "user_id": "user-aarav-patil",
        "status": ApplicationStatus.draft.value, "current_step": 0, "progress": 0,
        "form_data": {"request_text": body.request_text, "state_code": body.state_code,
                       "district": body.district, "department_id": body.department_id,
                       **body.additional_context}, "documents": [], "review_state": {},
        "approval_state": "not_started", "tracking": {"demo_mode": True},
        "created_at": ts, "updated_at": ts, "selected_scholarship": None,
        "activity": [{"id": f"{app_id}-created", "label": "Custom service request received", "timestamp": ts, "tone": "blue"}],
        "application_mode": "custom", "custom_status": "request_received",
        "portal_url": portal_url,
        "allowed_domains": allowed,
    }
    return CustomApplicationResponse(application_id=app_id, message="Request received. CivicFlow will discover and verify the official service source.")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _make_id() -> str:
    return f"app-{uuid.uuid4().hex[:12]}"


@router.post("", response_model=ApplicationDetail, status_code=status.HTTP_201_CREATED)
async def create_application(body: CreateApplicationRequest):
    app_id = _make_id()
    ts = _now()
    docs = [
        {
            "document_id": f"{body.service_id}-doc-{i}",
            "name": name,
            "file_type": "PDF / JPG",
            "status": DocumentStatus.pending.value,
        }
        for i, name in enumerate(_DEFAULT_DOCUMENTS.get(body.service_id, []))
    ]
    portal_url = next((str(s.get("official_url")) for s in _SERVICE_CATALOG if s["id"] == body.service_id and s.get("official_url")), None)
    allowed = []
    if portal_url:
        h = urlparse(portal_url).hostname
        if h:
            allowed.append(h)

    record = {
        "id": app_id,
        "service_id": body.service_id,
        "user_id": "user-aarav-patil",  # TODO: from auth
        "status": ApplicationStatus.draft.value,
        "current_step": 0,
        "progress": 0,
        "form_data": body.form_data or {},
        "documents": docs,
        "review_state": {k: False for k in ["personal", "education", "financial", "documents"]},
        "approval_state": "not_started",
        "tracking": {"demo_mode": True},
        "created_at": ts,
        "updated_at": ts,
        "selected_scholarship": body.selected_scholarship,
        "portal_url": portal_url,
        "allowed_domains": allowed,
        "application_mode": "catalog",
        "activity": [{"id": f"{app_id}-created", "label": "Application draft created", "timestamp": ts, "tone": "blue"}],
    }
    _applications[app_id] = record
    return _to_detail(record)


@router.post("/{application_id}/ensure", response_model=ApplicationDetail)
async def ensure_legacy_application(application_id: str, body: CreateApplicationRequest):
    """Adopt a browser-local draft so Core API and Browser Agent share its ID."""
    if not application_id.startswith("app-") or len(application_id) > 80:
        raise HTTPException(status_code=422, detail="Invalid application identifier")
    existing = _applications.get(application_id)
    if existing:
        if existing["service_id"] != body.service_id:
            raise HTTPException(status_code=409, detail="Application identifier belongs to a different service")
        return _to_detail(existing)
    ts = _now()
    docs = [{"document_id": f"{body.service_id}-doc-{i}", "name": name,
             "file_type": "PDF / JPG", "status": DocumentStatus.pending.value}
            for i, name in enumerate(_DEFAULT_DOCUMENTS.get(body.service_id, []))]
    service = next((item for item in _SERVICE_CATALOG if item["id"] == body.service_id), None)
    portal = service.get("official_url") if service else None
    _applications[application_id] = {
        "id": application_id, "service_id": body.service_id, "user_id": "user-aarav-patil",
        "status": ApplicationStatus.draft.value, "current_step": 0, "progress": 0,
        "form_data": body.form_data or {}, "documents": docs,
        "review_state": {key: False for key in ("personal", "education", "financial", "documents")},
        "approval_state": "not_started", "tracking": {"demo_mode": True},
        "created_at": ts, "updated_at": ts, "selected_scholarship": body.selected_scholarship,
        "portal_url": portal, "allowed_domains": [urlparse(portal).hostname] if portal else [],
        "application_mode": "catalog",
        "activity": [{"id": f"{application_id}-adopted", "label": "Application workspace restored", "timestamp": ts, "tone": "blue"}],
    }
    return _to_detail(_applications[application_id])


@router.get("", response_model=list[ApplicationSummary])
async def list_applications():
    return [
        ApplicationSummary(
            id=r["id"], service_id=r["service_id"], status=r["status"],
            progress=r["progress"], created_at=r["created_at"], updated_at=r["updated_at"],
        )
        for r in _applications.values()
    ]


@router.get("/{application_id}", response_model=ApplicationDetail)
async def get_application(application_id: str):
    record = _applications.get(application_id)
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")
    return _to_detail(record)

@router.get("/{application_id}/portal")
async def get_application_portal(application_id: str):
    record = _applications.get(application_id)
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")
    url = record.get("portal_url")
    if not url:
        raise HTTPException(status_code=404, detail="No official portal is attached to this application")
    from urllib.parse import urlparse
    return {"application_id": application_id, "portal_url": url, "allowed_domains": [urlparse(url).hostname], "source_status": "listed_official_source"}


@router.patch("/{application_id}", response_model=ApplicationDetail)
async def update_application(application_id: str, body: UpdateApplicationRequest):
    record = _applications.get(application_id)
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")

    if body.status is not None:
        if body.status in {
            ApplicationStatus.approved_for_submission,
            ApplicationStatus.submission_in_progress,
            ApplicationStatus.submitted,
        }:
            raise HTTPException(status_code=409, detail="Approval and submission statuses can only be set through their guarded workflow")
        try:
            validate_transition(ApplicationStatus(record["status"]), body.status)
        except InvalidTransitionError as e:
            raise HTTPException(status_code=422, detail=str(e))
        record["status"] = body.status.value
        record["activity"].append({
            "id": f"{application_id}-status-{uuid.uuid4().hex[:6]}",
            "label": f"Status changed to {body.status.value}",
            "timestamp": _now(),
            "tone": "blue",
        })

    if body.form_data is not None:
        record["form_data"].update(body.form_data)
    if body.current_step is not None:
        record["current_step"] = body.current_step
    if body.progress is not None:
        record["progress"] = body.progress
    if body.selected_scholarship is not None:
        record["selected_scholarship"] = body.selected_scholarship

    record["updated_at"] = _now()
    return _to_detail(record)


@router.delete("/{application_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_application(application_id: str):
    if application_id not in _applications:
        raise HTTPException(status_code=404, detail="Application not found")
    del _applications[application_id]


@router.get("/{application_id}/activity", response_model=list[ActivityEvent])
async def get_activity(application_id: str):
    record = _applications.get(application_id)
    if not record:
        raise HTTPException(status_code=404, detail="Application not found")
    return [ActivityEvent(**e) for e in record.get("activity", [])]


def _to_detail(record: dict) -> ApplicationDetail:
    form = record.get("form_data", {})
    return ApplicationDetail(
        id=record["id"],
        service_id=record["service_id"],
        user_id=record["user_id"],
        status=record["status"],
        current_step=record["current_step"],
        progress=record["progress"],
        form_data=form,
        documents=[
            DocumentRequirement(
                document_id=d["document_id"], name=d["name"],
                file_type=d["file_type"], status=d["status"],
            )
            for d in record.get("documents", [])
        ],
        review_state=record.get("review_state", {}),
        approval_state=record.get("approval_state", "not_started"),
        tracking=TrackingInfo(**record.get("tracking", {"demo_mode": True})),
        created_at=record["created_at"],
        updated_at=record["updated_at"],
        selected_scholarship=record.get("selected_scholarship"),
        portal_url=record.get("portal_url"),
        allowed_domains=record.get("allowed_domains", []),
        custom_request=form.get("request_text") if isinstance(form, dict) else None,
        custom_state=form.get("state_code") if isinstance(form, dict) else None,
        custom_district=form.get("district") if isinstance(form, dict) else None,
        application_mode=record.get("application_mode", "catalog"),
    )
