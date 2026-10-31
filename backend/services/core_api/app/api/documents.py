"""Document management endpoints."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from civicflow_contracts.application import DocumentResponse, UploadDocumentRequest
from civicflow_contracts.common import DocumentStatus

router = APIRouter()

# In-memory document store
_documents: dict[str, dict] = {}


@router.post("/applications/{application_id}/documents", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(application_id: str, body: UploadDocumentRequest):
    import uuid
    doc_id = f"doc-{uuid.uuid4().hex[:8]}"
    doc = {
        "document_id": doc_id,
        "name": body.name,
        "file_type": body.file_type,
        "status": DocumentStatus.uploaded.value,
        "notes": body.notes,
        "upload_url": f"/storage/docs/{doc_id}",
        "uploaded_at": "2026-10-31T08:00:00Z",
    }
    _documents[doc_id] = doc
    return DocumentResponse(**doc)


@router.get("/applications/{application_id}/documents", response_model=list[DocumentResponse])
async def list_documents(application_id: str):
    return [DocumentResponse(**d) for d in _documents.values()]


@router.delete("/documents/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(document_id: str):
    if document_id not in _documents:
        raise HTTPException(status_code=404, detail="Document not found")
    del _documents[document_id]
