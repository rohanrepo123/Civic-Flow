import asyncio
import base64
import hashlib
import hmac
import json
import os
import secrets
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, EmailStr, Field
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.app.agent.graph import WorkflowDependencies, create_civicflow_graph, resume_task, run_task
from backend.app.agent.clients.browser_client import BrowserHttpClient, GuardedBrowserClient
from backend.app.agent.nodes.intent import build_intent_extractor
from backend.app.agent.schemas.task import TaskStatus
from backend.app.agent.schemas.documents import DocumentMetadata, DocumentStatus
from backend.app.agent.services.curated_knowledge import CuratedKnowledge
from backend.app.agent.services.document_extractor import DocumentExtractor
from backend.app.agent.services.llm import build_chat_client
from backend.app.agent.config import AgentSettings
from backend.app.agent.workflow_serializer import WorkflowSerializer
from backend.app.agent.services.service_registry import ServiceRegistry
from backend.app.agent.services.service_resolver import ServiceResolver
from backend.app.agent.services.action_policy import ActionPolicy
from backend.app.agent.schemas.browser import ControlMode, ControlModeRequest, UserInputEvent
from backend.app.db import ApprovalRow, Base, DocumentRow, EventRow, ProfileRow, TaskRow, UserRow, make_database, migrate_small_schema_updates


TOKEN_SECRET = (os.getenv("AUTH_TOKEN_SECRET", "").strip() or "local-development-secret-change-me").encode()
if os.getenv("APP_ENV", "development").casefold() == "production" and TOKEN_SECRET == b"local-development-secret-change-me":
    raise RuntimeError("AUTH_TOKEN_SECRET must be configured in production")
TOKEN_TTL = timedelta(hours=12)
MAX_UPLOAD_BYTES = 15 * 1024 * 1024
DOCUMENT_ROOT = Path(os.getenv("DOCUMENT_STORAGE_DIR", "./private_uploads")).resolve()


class Credentials(BaseModel):
    email: EmailStr
    password: str = Field(min_length=10, max_length=256)


class TaskRequest(BaseModel):
    user_request: str = Field(min_length=3, max_length=8000)
    require_approval: bool = False


class ResumeRequest(BaseModel):
    value: dict


class ApprovalDecision(BaseModel):
    approved: bool


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode().rstrip("=")


def _password_hash(password: str, salt: bytes | None = None) -> str:
    salt = salt or secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 310_000)
    return f"{_b64(salt)}.{_b64(digest)}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        salt_text, expected = stored.split(".", 1)
        salt = base64.urlsafe_b64decode(salt_text + "=" * (-len(salt_text) % 4))
        return hmac.compare_digest(_password_hash(password, salt).split(".", 1)[1], expected)
    except (ValueError, TypeError):
        return False


def _issue_token(user_id: str) -> str:
    payload = _b64(json.dumps({"sub": user_id, "exp": int((datetime.now(UTC) + TOKEN_TTL).timestamp())}, separators=(",", ":")).encode())
    signature = _b64(hmac.new(TOKEN_SECRET, payload.encode(), hashlib.sha256).digest())
    return f"{payload}.{signature}"


def _token_user(token: str) -> str:
    try:
        payload, signature = token.split(".", 1)
        expected = _b64(hmac.new(TOKEN_SECRET, payload.encode(), hashlib.sha256).digest())
        if not hmac.compare_digest(signature, expected):
            raise ValueError
        data = json.loads(base64.urlsafe_b64decode(payload + "=" * (-len(payload) % 4)))
        if int(data["exp"]) <= int(datetime.now(UTC).timestamp()):
            raise ValueError
        return str(data["sub"])
    except (ValueError, KeyError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired access token") from exc


def create_app(*, database_url: str | None = None) -> FastAPI:
    configured_database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///./civicflow.db")
    engine, session_factory = make_database(configured_database_url)
    Base.metadata.create_all(engine)
    migrate_small_schema_updates(engine)
    registry = ServiceRegistry.default()
    knowledge = CuratedKnowledge.default()
    worker_token = os.getenv("BROWSER_WORKER_API_TOKEN", "").strip()
    browser_client = None
    if worker_token:
        raw_browser = BrowserHttpClient(os.getenv("BROWSER_WORKER_URL", "http://browser-worker:8001"), service_token=worker_token)
        browser_client = GuardedBrowserClient(raw_browser, ActionPolicy())
    settings = AgentSettings.from_environment()
    hosted_document_processing_allowed = (
        settings.llm_provider != "openai" or settings.openai_document_processing_enabled
    )
    document_extractor = (
        DocumentExtractor(build_chat_client(settings))
        if settings.llm_enabled and hosted_document_processing_allowed
        else None
    )

    def load_profile(user_id: str) -> dict:
        with session_factory() as session:
            profile = session.get(ProfileRow, user_id)
            return dict(profile.data) if profile else {}

    async def analyze_documents(user_id: str, documents: list, profile: dict):
        with session_factory() as session:
            rows = session.scalars(select(DocumentRow).where(DocumentRow.user_id == user_id)).all()
            metadata = [
                DocumentMetadata(
                    document_id=row.document_id,
                    owner_id=user_id,
                    filename=row.filename,
                    media_type=row.content_type,
                    size_bytes=Path(row.storage_path).stat().st_size if Path(row.storage_path).exists() else 0,
                    document_type=row.document_type,
                    status=DocumentStatus.NEEDS_REVIEW if row.document_type else DocumentStatus.UPLOADED,
                )
                for row in rows
            ]
            analyses = []
            if document_extractor is not None:
                for index, row in enumerate(rows):
                    if row.content_type != "application/pdf":
                        metadata[index] = metadata[index].model_copy(update={"status": DocumentStatus.NEEDS_REVIEW})
                        continue
                    try:
                        analysis = await document_extractor.analyze_pdf_bytes(
                            document=metadata[index],
                            pdf_bytes=Path(row.storage_path).read_bytes(),
                            profile=profile,
                        )
                        metadata[index] = analysis.document
                        analyses.extend(analysis.extracted_fields)
                    except Exception:
                        metadata[index] = metadata[index].model_copy(update={"status": DocumentStatus.NEEDS_REVIEW})
            return metadata, analyses

    def read_approval_status(approval_id: str) -> str:
        with session_factory() as session:
            approval = session.get(ApprovalRow, approval_id)
            return approval.status if approval is not None else "expired"

    workflow_dependencies = WorkflowDependencies(
        intent_extractor=build_intent_extractor(),
        service_resolver=ServiceResolver(registry),
        requirement_extractor=knowledge,
        source_retriever=knowledge.retrieve,
        profile_loader=load_profile,
        document_analyzer=analyze_documents,
        approval_status_reader=read_approval_status,
        browser_client=browser_client,
    )
    workflow = create_civicflow_graph(workflow_dependencies)
    app = FastAPI(title="CivicFlow API", version="0.2.0")
    bearer = HTTPBearer(auto_error=False)

    def db_session():
        session = session_factory()
        try:
            yield session
        finally:
            session.close()

    def current_user(
        credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    ) -> str:
        if credentials is None or credentials.scheme.casefold() != "bearer":
            raise HTTPException(status_code=401, detail="Bearer token required")
        return _token_user(credentials.credentials)

    def owned_task(session: Session, task_id: str, user_id: str) -> TaskRow:
        task = session.get(TaskRow, task_id)
        if task is None or task.user_id != user_id:
            raise HTTPException(status_code=404, detail="Task not found")
        return task

    def serialize_task(task: TaskRow) -> dict:
        return {
            "task_id": task.task_id,
            "status": task.status,
            "user_request": task.user_request,
            "summary": task.summary,
            "state": task.state,
            "created_at": task.created_at,
            "updated_at": task.updated_at,
        }

    async def persist_result(task_id: str, user_id: str, result: dict) -> None:
        with session_factory() as session:
            task = session.get(TaskRow, task_id)
            if task is None or task.user_id != user_id:
                return
            pending = (result.get("__interrupt__") or [None])[0]
            if pending is not None:
                prompt = jsonable_encoder(pending.value)
                pending_status = TaskStatus.WAITING_FOR_APPROVAL if prompt.get("type") == "approval.required" else TaskStatus.WAITING_FOR_USER
            else:
                prompt = None
                pending_status = result.get("task_status", TaskStatus.RUNNING)
            task.status = pending_status.value
            task.summary = result.get("final_summary")
            task.state = {
                key: jsonable_encoder(value)
                for key, value in result.items()
                if key not in {"events", "__interrupt__"}
            }
            if prompt is not None:
                task.state["pending_prompt"] = prompt
            for event in result.get("events", []):
                if session.get(EventRow, event.event_id) is None:
                    session.add(EventRow(
                        event_id=event.event_id,
                        task_id=task_id,
                        sequence=event.sequence,
                        data=event.model_dump(mode="json"),
                    ))
            session.commit()

    async def execute_task(task_id: str, user_id: str, request: str, approval_id: str | None = None) -> None:
        try:
            inputs = {"user_id": user_id, "user_request": request}
            if approval_id:
                inputs["approval_id"] = approval_id
            result = await run_task(
                workflow,
                inputs,
                task_id=task_id,
            )
            await persist_result(task_id, user_id, result)
        except Exception:
            with session_factory() as session:
                task = session.get(TaskRow, task_id)
                if task:
                    task.status = TaskStatus.FAILED.value
                    task.summary = "The task stopped safely because an internal workflow error occurred."
                    session.commit()

    async def recover_checkpoint(task_id: str, user_id: str, request: str) -> None:
        try:
            config = {"configurable": {"thread_id": task_id}}
            snapshot = await workflow.aget_state(config)
            if snapshot and snapshot.values:
                result = await workflow.ainvoke(None, config)
            else:
                result = await run_task(workflow, {"user_id": user_id, "user_request": request}, task_id=task_id)
            await persist_result(task_id, user_id, result)
        except Exception:
            with session_factory() as session:
                task = session.get(TaskRow, task_id)
                if task:
                    task.status = TaskStatus.FAILED.value
                    task.summary = "The task could not recover safely from its saved checkpoint."
                    session.commit()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        nonlocal workflow
        postgres_saver = None
        if configured_database_url.startswith(("postgresql://", "postgresql+psycopg://")):
            from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

            postgres_url = configured_database_url.replace("postgresql+psycopg://", "postgresql://", 1)
            postgres_saver = AsyncPostgresSaver.from_conn_string(postgres_url, serde=WorkflowSerializer())
            saver = await postgres_saver.__aenter__()
            await saver.setup()
            workflow = create_civicflow_graph(workflow_dependencies, checkpointer=saver)
            app.state.workflow = workflow
        try:
            with session_factory() as session:
                interrupted = session.scalars(select(TaskRow).where(TaskRow.status == TaskStatus.RUNNING.value)).all()
                recovering = [(task.task_id, task.user_id, task.user_request) for task in interrupted]
            for task_id, user_id, request in recovering:
                asyncio.create_task(recover_checkpoint(task_id, user_id, request))
            yield
        finally:
            if postgres_saver is not None:
                await postgres_saver.__aexit__(None, None, None)
            if browser_client is not None:
                raw = getattr(browser_client, "_client", None)
                close = getattr(raw, "close", None)
                if close is not None:
                    await close()

    app.router.lifespan_context = lifespan

    @app.get("/healthz", tags=["health"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok", "service": "backend"}

    @app.post("/api/v1/auth/register", status_code=201)
    def register(payload: Credentials, session: Session = Depends(db_session)) -> dict:
        email = str(payload.email).casefold()
        if session.scalar(select(UserRow).where(UserRow.email == email)):
            raise HTTPException(status_code=409, detail="An account already exists for this email")
        user = UserRow(user_id=str(uuid4()), email=email, password_hash=_password_hash(payload.password))
        session.add(user)
        session.commit()
        return {"access_token": _issue_token(user.user_id), "token_type": "bearer", "user_id": user.user_id}

    @app.post("/api/v1/auth/login")
    def login(payload: Credentials, session: Session = Depends(db_session)) -> dict:
        user = session.scalar(select(UserRow).where(UserRow.email == str(payload.email).casefold()))
        if user is None or not _verify_password(payload.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid email or password")
        return {"access_token": _issue_token(user.user_id), "token_type": "bearer", "user_id": user.user_id}

    @app.get("/api/v1/profile")
    def get_profile(user_id: str = Depends(current_user), session: Session = Depends(db_session)) -> dict:
        profile = session.get(ProfileRow, user_id)
        return {"user_id": user_id, "data": profile.data if profile else {}}

    @app.put("/api/v1/profile")
    def put_profile(data: dict, user_id: str = Depends(current_user), session: Session = Depends(db_session)) -> dict:
        forbidden = {"password", "passcode", "otp", "captcha", "secret", "token"}

        def has_secret(value: object) -> bool:
            if isinstance(value, dict):
                return any(any(term in str(key).casefold() for term in forbidden) or has_secret(item) for key, item in value.items())
            if isinstance(value, list):
                return any(has_secret(item) for item in value)
            return False

        if has_secret(data):
            raise HTTPException(status_code=422, detail="Authentication secrets cannot be stored in the profile")
        profile = session.get(ProfileRow, user_id)
        if profile is None:
            profile = ProfileRow(user_id=user_id, data=data)
            session.add(profile)
        else:
            profile.data = data
            profile.updated_at = datetime.now(UTC)
        session.commit()
        return {"user_id": user_id, "data": profile.data}

    @app.post("/api/v1/documents", status_code=201)
    async def upload_document(file: UploadFile = File(...), document_type: str | None = Form(None), user_id: str = Depends(current_user), session: Session = Depends(db_session)) -> dict:
        name = Path(file.filename or "document").name[:255]
        if file.content_type not in {"application/pdf", "image/jpeg", "image/png"}:
            raise HTTPException(status_code=415, detail="Only PDF, JPEG, and PNG files are accepted")
        data = await file.read(MAX_UPLOAD_BYTES + 1)
        if not data or len(data) > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="Document is empty or exceeds the 15 MB limit")
        if file.content_type == "application/pdf" and not data.startswith(b"%PDF-"):
            raise HTTPException(status_code=415, detail="File content does not match its declared type")
        document_id = str(uuid4())
        folder = DOCUMENT_ROOT / user_id
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / document_id
        destination.write_bytes(data)
        row = DocumentRow(document_id=document_id, user_id=user_id, filename=name, content_type=file.content_type, sha256=hashlib.sha256(data).hexdigest(), storage_path=str(destination), document_type=document_type.strip()[:120] if document_type else None)
        session.add(row)
        session.commit()
        return {"document_id": document_id, "filename": name, "content_type": row.content_type, "document_type": row.document_type, "status": row.status}

    @app.get("/api/v1/documents")
    def list_documents(user_id: str = Depends(current_user), session: Session = Depends(db_session)) -> list[dict]:
        rows = session.scalars(select(DocumentRow).where(DocumentRow.user_id == user_id).order_by(DocumentRow.created_at.desc())).all()
        return [{"document_id": row.document_id, "filename": row.filename, "content_type": row.content_type, "status": row.status, "created_at": row.created_at} for row in rows]

    @app.get("/api/v1/documents/{document_id}/content")
    def document_content(document_id: str, user_id: str = Depends(current_user), session: Session = Depends(db_session)) -> Response:
        row = session.get(DocumentRow, document_id)
        if row is None or row.user_id != user_id:
            raise HTTPException(status_code=404, detail="Document not found")
        content = Path(row.storage_path).read_bytes()
        return Response(content, media_type=row.content_type, headers={"Content-Disposition": f'attachment; filename="{row.filename}"'})

    @app.post("/api/v1/tasks", status_code=202)
    async def start_task(payload: TaskRequest, user_id: str = Depends(current_user), session: Session = Depends(db_session)) -> dict:
        task_id = str(uuid4())
        approval_id = str(uuid4()) if payload.require_approval else None
        task = TaskRow(task_id=task_id, user_id=user_id, user_request=payload.user_request, status=TaskStatus.RUNNING.value, state={"approval_id": approval_id} if approval_id else {})
        session.add(task)
        if approval_id:
            session.add(ApprovalRow(approval_id=approval_id, task_id=task_id, user_id=user_id, description="Review the workflow before it continues."))
        session.commit()
        asyncio.create_task(execute_task(task_id, user_id, payload.user_request, approval_id))
        return serialize_task(task)

    @app.get("/api/v1/tasks")
    def list_tasks(user_id: str = Depends(current_user), session: Session = Depends(db_session)) -> list[dict]:
        rows = session.scalars(select(TaskRow).where(TaskRow.user_id == user_id).order_by(TaskRow.created_at.desc()).limit(100)).all()
        return [serialize_task(row) for row in rows]

    @app.get("/api/v1/tasks/{task_id}")
    def get_task(task_id: str, user_id: str = Depends(current_user), session: Session = Depends(db_session)) -> dict:
        return serialize_task(owned_task(session, task_id, user_id))

    @app.get("/api/v1/tasks/{task_id}/events")
    def task_events(task_id: str, after: int = 0, user_id: str = Depends(current_user), session: Session = Depends(db_session)) -> list[dict]:
        owned_task(session, task_id, user_id)
        rows = session.scalars(select(EventRow).where(EventRow.task_id == task_id, EventRow.sequence > after).order_by(EventRow.sequence)).all()
        return [row.data for row in rows]

    @app.post("/api/v1/tasks/{task_id}/resume", status_code=202)
    async def continue_task(task_id: str, payload: ResumeRequest, user_id: str = Depends(current_user), session: Session = Depends(db_session)) -> dict:
        task = owned_task(session, task_id, user_id)
        if task.status not in {TaskStatus.WAITING_FOR_USER.value, TaskStatus.WAITING_FOR_APPROVAL.value, TaskStatus.PAUSED.value}:
            raise HTTPException(status_code=409, detail="Task is not waiting for user input")
        asyncio.create_task(resume_and_persist(task_id, user_id, payload.value))
        task.status = TaskStatus.RUNNING.value
        session.commit()
        return {"task_id": task_id, "status": task.status}

    @app.get("/api/v1/tasks/{task_id}/browser/screenshot")
    async def browser_screenshot(task_id: str, user_id: str = Depends(current_user), session: Session = Depends(db_session)) -> Response:
        task = owned_task(session, task_id, user_id)
        session_id = task.state.get("browser_session_id")
        if browser_client is None or not session_id:
            raise HTTPException(status_code=404, detail="No browser session is attached to this task")
        try:
            return Response(await browser_client.get_screenshot(session_id), media_type="image/jpeg", headers={"Cache-Control": "no-store"})
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Browser screenshot is temporarily unavailable") from exc

    @app.post("/api/v1/tasks/{task_id}/browser/control")
    async def browser_control(task_id: str, mode: ControlModeRequest, user_id: str = Depends(current_user), session: Session = Depends(db_session)) -> dict:
        task = owned_task(session, task_id, user_id)
        session_id = task.state.get("browser_session_id")
        if browser_client is None or not session_id:
            raise HTTPException(status_code=404, detail="No browser session is attached to this task")
        try:
            response = await browser_client.set_control_mode(session_id, mode)
            return response.model_dump(mode="json")
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Browser control is temporarily unavailable") from exc

    @app.post("/api/v1/tasks/{task_id}/browser/input")
    async def browser_input(task_id: str, event: UserInputEvent, user_id: str = Depends(current_user), session: Session = Depends(db_session)) -> dict:
        task = owned_task(session, task_id, user_id)
        session_id = task.state.get("browser_session_id")
        if browser_client is None or not session_id:
            raise HTTPException(status_code=404, detail="No browser session is attached to this task")
        try:
            response = await browser_client.send_user_input(session_id, event)
            return response.model_dump(mode="json")
        except Exception as exc:
            raise HTTPException(status_code=503, detail="Browser input is temporarily unavailable") from exc

    async def resume_and_persist(task_id: str, user_id: str, value: dict) -> None:
        try:
            result = await resume_task(workflow, task_id=task_id, resume_value=value)
            await persist_result(task_id, user_id, result)
        except Exception:
            with session_factory() as session:
                task = session.get(TaskRow, task_id)
                if task:
                    task.status = TaskStatus.FAILED.value
                    task.summary = "The task could not resume safely."
                    session.commit()

    @app.post("/api/v1/tasks/{task_id}/approvals", status_code=201)
    def create_approval(task_id: str, description: str = "Review this requested action", user_id: str = Depends(current_user), session: Session = Depends(db_session)) -> dict:
        owned_task(session, task_id, user_id)
        approval = ApprovalRow(approval_id=str(uuid4()), task_id=task_id, user_id=user_id, description=description)
        session.add(approval)
        session.commit()
        return {"approval_id": approval.approval_id, "task_id": task_id, "status": approval.status, "description": description}

    @app.post("/api/v1/approvals/{approval_id}/decision")
    def decide_approval(approval_id: str, payload: ApprovalDecision, user_id: str = Depends(current_user), session: Session = Depends(db_session)) -> dict:
        approval = session.get(ApprovalRow, approval_id)
        if approval is None or approval.user_id != user_id:
            raise HTTPException(status_code=404, detail="Approval not found")
        if approval.status != "pending":
            raise HTTPException(status_code=409, detail="Approval has already been decided")
        approval.status = "approved" if payload.approved else "rejected"
        approval.decided_at = datetime.now(UTC)
        session.commit()
        return {"approval_id": approval_id, "status": approval.status}

    app.state.database_engine = engine
    app.state.workflow = workflow
    app.state.session_factory = session_factory
    app.state.browser_client = browser_client
    return app


app = create_app()
