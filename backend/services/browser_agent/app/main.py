"""Standalone browser session API. Session control supports both Playwright and mock-backed modes."""
from contextlib import asynccontextmanager, suppress
from datetime import datetime, timedelta, timezone
import asyncio
import base64
import html
from ipaddress import ip_address
import secrets
import os
from urllib.parse import urlparse
from uuid import UUID
from fastapi import FastAPI, HTTPException, Request, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from civicflow_contracts import CONTRACT_VERSION
from civicflow_contracts.browser import (BrowserCommand, BrowserEvent, BrowserSessionCreateRequest,
    BrowserSessionResponse, BrowserSessionStatus, BrowserCapability)
from app.playwright_runtime import PlaywrightRuntime

async def _expire_sessions() -> None:
    while True:
        now = datetime.now(timezone.utc)
        for session_id, session in list(sessions.items()):
            if session["expires_at"] <= now and session["session_status"] not in {
                BrowserSessionStatus.closed,
                BrowserSessionStatus.expired,
                BrowserSessionStatus.failed,
            }:
                with suppress(HTTPException):
                    await _set(session_id, BrowserSessionStatus.expired)
            if session["expires_at"] + timedelta(minutes=5) <= now:
                stream_tokens.pop(session.get("stream_token"), None)
                sessions.pop(session_id, None)
                runtime = runtimes.pop(session_id, None)
                if runtime:
                    with suppress(Exception):
                        await runtime.close()
        await asyncio.sleep(30)


@asynccontextmanager
async def lifespan(_application: FastAPI):
    cleanup_task = asyncio.create_task(_expire_sessions())
    try:
        yield
    finally:
        cleanup_task.cancel()
        with suppress(asyncio.CancelledError):
            await cleanup_task
        for session_id in list(sessions):
            with suppress(HTTPException):
                await _set(session_id, BrowserSessionStatus.closed)
        stream_tokens.clear()


app = FastAPI(title="CivicFlow Browser Agent", version="0.1.0", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:3000,http://127.0.0.1:3000").split(","), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
sessions: dict[UUID, dict] = {}
stream_tokens: dict[str, tuple[UUID, datetime]] = {}
runtimes: dict[UUID, PlaywrightRuntime] = {}
_browser_runtime = os.getenv("CIVICFLOW_BROWSER_RUNTIME", "playwright").strip().lower()
if _browser_runtime not in {"playwright", "mock"}:
    raise RuntimeError("CIVICFLOW_BROWSER_RUNTIME must be 'playwright' or explicitly 'mock'.")
PLAYWRIGHT_ENABLED = _browser_runtime == "playwright"
PLAYWRIGHT_READY = False
ALLOW_LOCAL_MOCK = os.getenv("CIVICFLOW_ALLOW_LOCAL_MOCK", "true").lower() == "true"
MOCK_MODE_ENABLED = not PLAYWRIGHT_ENABLED and ALLOW_LOCAL_MOCK
BROWSER_AGENT_API_TOKEN = os.getenv("BROWSER_AGENT_API_TOKEN", "").strip()


@app.middleware("http")
async def require_core_service_token(request: Request, call_next):
    if request.url.path.startswith("/internal/v1/browser/"):
        if not BROWSER_AGENT_API_TOKEN:
            return Response(status_code=503, content="Browser service authentication is not configured")
        if request.headers.get("authorization") != f"Bearer {BROWSER_AGENT_API_TOKEN}":
            return Response(status_code=401, content="Core service token required")
    return await call_next(request)

def generate_portal_frame_svg(url: str, title: str = "Fictional Public Service Form") -> str:
    escaped_url = html.escape(url or "http://localhost:9090")
    escaped_title = html.escape(title or "Fictional Public Service Form")
    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 640" width="1024" height="640">
      <defs>
        <linearGradient id="flag" x1="0%" y1="0%" x2="100%" y2="0%">
          <stop offset="0%" stop-color="#FF9933"/>
          <stop offset="50%" stop-color="#FFFFFF"/>
          <stop offset="100%" stop-color="#138808"/>
        </linearGradient>
      </defs>
      <rect width="1024" height="640" fill="#f8fafc"/>
      <rect x="0" y="0" width="1024" height="5" fill="url(#flag)"/>
      <rect x="0" y="5" width="1024" height="64" fill="#0f3930"/>
      <circle cx="40" cy="37" r="18" fill="#1b5e50"/>
      <polygon points="40,24 45,34 35,34" fill="#ffd166"/>
      <text x="70" y="32" fill="#ffffff" font-family="system-ui, -apple-system, sans-serif" font-size="14" font-weight="700">CIVICFLOW SIMULATED DEMO</text>
      <text x="70" y="50" fill="#a7f3d0" font-family="system-ui, -apple-system, sans-serif" font-size="11">Fictional test page · No government portal is open</text>
      <rect x="780" y="22" width="215" height="30" rx="15" fill="#134e42"/>
      <circle cx="798" cy="37" r="6" fill="#34d399"/>
      <text x="812" y="41" fill="#ecfdf5" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600">MOCK VIEW · NO LIVE PORTAL</text>

      <rect x="0" y="69" width="1024" height="38" fill="#e2e8f0"/>
      <rect x="16" y="75" width="992" height="26" rx="6" fill="#ffffff" stroke="#cbd5e1"/>
      <circle cx="34" cy="88" r="4" fill="#059669"/>
      <text x="46" y="92" fill="#475569" font-family="monospace" font-size="12">{escaped_url}</text>

      <rect x="40" y="125" width="944" height="475" rx="8" fill="#ffffff" stroke="#e2e8f0" stroke-width="1.5"/>
      <rect x="40" y="125" width="944" height="44" rx="8" fill="#f1f5f9"/>
      <text x="60" y="152" fill="#0f172a" font-family="system-ui, -apple-system, sans-serif" font-size="15" font-weight="700">{escaped_title}</text>
      <text x="820" y="152" fill="#059669" font-family="system-ui, -apple-system, sans-serif" font-size="12" font-weight="600">SIMULATED FORM</text>

      <rect x="60" y="195" width="430" height="70" rx="6" fill="#f8fafc" stroke="#e2e8f0"/>
      <text x="75" y="217" fill="#64748b" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600">APPLICANT FULL NAME (AS PER AADHAAR)</text>
      <text x="75" y="244" fill="#0f172a" font-family="system-ui, -apple-system, sans-serif" font-size="14" font-weight="500">Example Citizen (fictional)</text>

      <rect x="520" y="195" width="430" height="70" rx="6" fill="#f8fafc" stroke="#e2e8f0"/>
      <text x="535" y="217" fill="#64748b" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600">FATHER / GUARDIAN NAME</text>
      <text x="535" y="244" fill="#0f172a" font-family="system-ui, -apple-system, sans-serif" font-size="14" font-weight="500">Example Guardian</text>

      <rect x="60" y="285" width="280" height="70" rx="6" fill="#f8fafc" stroke="#e2e8f0"/>
      <text x="75" y="307" fill="#64748b" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600">DATE OF BIRTH</text>
      <text x="75" y="334" fill="#0f172a" font-family="system-ui, -apple-system, sans-serif" font-size="14" font-weight="500">01/01/2000 (sample)</text>

      <rect x="365" y="285" width="280" height="70" rx="6" fill="#f8fafc" stroke="#e2e8f0"/>
      <text x="380" y="307" fill="#64748b" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600">ANNUAL FAMILY INCOME (₹)</text>
      <text x="380" y="334" fill="#0f172a" font-family="system-ui, -apple-system, sans-serif" font-size="14" font-weight="500">Sample amount</text>

      <rect x="670" y="285" width="280" height="70" rx="6" fill="#f8fafc" stroke="#e2e8f0"/>
      <text x="685" y="307" fill="#64748b" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600">CATEGORY</text>
      <text x="685" y="334" fill="#0f172a" font-family="system-ui, -apple-system, sans-serif" font-size="14" font-weight="500">Sample category</text>

      <rect x="60" y="375" width="890" height="90" rx="6" fill="#f8fafc" stroke="#e2e8f0"/>
      <text x="75" y="397" fill="#64748b" font-family="system-ui, -apple-system, sans-serif" font-size="11" font-weight="600">RESIDENTIAL ADDRESS &amp; DISTRICT</text>
      <text x="75" y="424" fill="#0f172a" font-family="system-ui, -apple-system, sans-serif" font-size="14" font-weight="500">Sample address (fictional)</text>

      <rect x="60" y="485" width="890" height="48" rx="6" fill="#ecfdf5" stroke="#a7f3d0"/>
      <text x="75" y="514" fill="#065f46" font-family="system-ui, -apple-system, sans-serif" font-size="12" font-weight="600">☑ Self-declaration: All information provided matches verified government records.</text>

      <text x="40" y="625" fill="#94a3b8" font-family="system-ui, -apple-system, sans-serif" font-size="11">CivicFlow AI Browser Agent · Isolated Sandbox · Citizen Takeover Available</text>
      <text x="870" y="625" fill="#94a3b8" font-family="system-ui, -apple-system, sans-serif" font-size="11">FICTIONAL TEST DATA</text>
    </svg>"""
    return base64.b64encode(svg.encode("utf-8")).decode("ascii")


def validate_target(url: str, allowed: list[str]) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    local_mock = ALLOW_LOCAL_MOCK and parsed.scheme in {"http", "https"} and host in {"localhost", "127.0.0.1"} and parsed.port == 9090
    if (parsed.scheme != "https" and not local_mock) or not host:
        raise HTTPException(400, "Only HTTPS portal URLs are allowed")
    try:
        address = ip_address(host)
        if not local_mock and not address.is_global:
            raise HTTPException(400, "Private and local network targets are blocked")
    except ValueError:
        if not local_mock and (host in {"localhost", "localhost.localdomain"} or "." not in host):
            raise HTTPException(400, "Local network targets are blocked")
    if not local_mock and not any(host == d.lower().lstrip(".") or host.endswith("." + d.lower().lstrip(".")) for d in allowed):
        raise HTTPException(403, "Target host is not in the service-approved domain list")

@app.get("/health/live")
async def live(): return {"status": "alive", "service": "browser_agent"}

@app.get("/health/ready")
async def ready():
    mode = "playwright" if PLAYWRIGHT_ENABLED else "mock"
    return {"status": "ready", "service": "browser_agent", "contract_version": CONTRACT_VERSION, "mode": mode, "live_browser": PLAYWRIGHT_ENABLED}

@app.get("/internal/v1/browser/capabilities")
async def capabilities():
    mode = "playwright" if PLAYWRIGHT_ENABLED else "mock"
    return {"contract_version": CONTRACT_VERSION, "capabilities": ["navigate", "inspect", "fill_non_sensitive", "screenshot", "pause_resume", "user_takeover"], "mode": mode, "live_browser": PLAYWRIGHT_ENABLED}

@app.post("/internal/v1/browser/sessions", response_model=BrowserSessionResponse)
async def create_session(req: BrowserSessionCreateRequest):
    global PLAYWRIGHT_READY
    validate_target(str(req.approved_portal_url), req.allowed_domains)
    sid = UUID(int=__import__("uuid").uuid4().int)
    expires = datetime.now(timezone.utc) + timedelta(seconds=req.session_policy.max_duration_seconds)
    token = secrets.token_urlsafe(32)
    if PLAYWRIGHT_ENABLED:
        runtime = None
        try:
            headless = os.getenv("BROWSER_HEADLESS", "false").strip().lower() == "true"
            runtime = await PlaywrightRuntime.start(headless=headless)
            await asyncio.wait_for(runtime.navigate(str(req.approved_portal_url)), timeout=12.0)
            runtimes[sid] = runtime
            PLAYWRIGHT_READY = True
        except Exception as exc:
            if runtime is not None:
                with suppress(Exception):
                    await runtime.close()
            PLAYWRIGHT_READY = bool(runtimes)
            detail = str(exc).replace(str(req.approved_portal_url), "the approved portal URL")[:300]
            raise HTTPException(
                status_code=503,
                detail=f"Live Chromium could not open the portal. Check Playwright/Chromium installation and network access. {detail}",
            ) from exc
    elif not MOCK_MODE_ENABLED:
        raise HTTPException(status_code=503, detail="Browser service is not configured for live Chromium or explicit mock mode.")
    stream_tokens[token] = (sid, expires)
    session = {"browser_session_id": sid, "session_status": BrowserSessionStatus.active,
        "expires_at": expires, "user_id": req.user_id, "application_id": req.application_id,
        "allowed_domains": req.allowed_domains, "url": str(req.approved_portal_url),
        "contract_version": CONTRACT_VERSION, "correlation_id": req.correlation_id, "stream_token": token}
    sessions[sid] = session
    return BrowserSessionResponse(browser_session_id=sid, session_status=BrowserSessionStatus.active,
        expires_at=expires, stream_endpoint=f"/internal/v1/browser/sessions/{sid}/stream?token={token}",
        stream_token=token,
        capabilities=req.requested_capabilities or list(BrowserCapability))

@app.get("/internal/v1/browser/sessions/{session_id}")
async def get_session(session_id: UUID):
    session = sessions.get(session_id)
    if not session: raise HTTPException(404, "Browser session not found")
    if PLAYWRIGHT_ENABLED and session["session_status"] == BrowserSessionStatus.active and session_id not in runtimes:
        await _set(session_id, BrowserSessionStatus.failed)
        session = sessions[session_id]
    return {k: v for k, v in session.items() if k not in {"allowed_domains", "user_id", "stream_token"}}

@app.get("/internal/v1/browser/sessions/{session_id}/stream-token")
async def get_stream_token(session_id: UUID):
    session = sessions.get(session_id)
    if not session: raise HTTPException(404, "Browser session not found")
    if session["session_status"] in {BrowserSessionStatus.closed, BrowserSessionStatus.expired, BrowserSessionStatus.failed}:
        raise HTTPException(409, "The browser session is no longer available.")
    token = secrets.token_urlsafe(32)
    expires = datetime.now(timezone.utc) + timedelta(minutes=15)
    stream_tokens[token] = (session_id, expires)
    return {"stream_token": token, "stream_endpoint": f"/internal/v1/browser/sessions/{session_id}/stream?token={token}"}

@app.get("/internal/v1/browser/sessions/{session_id}/screenshot")
async def get_screenshot(session_id: UUID):
    session = sessions.get(session_id)
    if not session: raise HTTPException(404, "Browser session not found")
    runtime = runtimes.get(session_id)
    if not runtime:
        if not MOCK_MODE_ENABLED:
            await _set(session_id, BrowserSessionStatus.failed)
            raise HTTPException(503, "The live browser has stopped; no simulated screenshot is available.")
        return {"session_id": str(session_id), "mode": "mock", "screenshot": None, "message": "Playwright runtime not active."}
    try:
        frame = await runtime.controller.session.page.screenshot(type="jpeg", quality=75)
        return {"session_id": str(session_id), "mode": "playwright", "screenshot": base64.b64encode(frame).decode("ascii"), "mime_type": "image/jpeg"}
    except Exception as exc:
        raise HTTPException(500, f"Screenshot failed: {exc}")

@app.post("/internal/v1/browser/sessions/{session_id}/commands")
async def command(session_id: UUID, req: BrowserCommand):
    session = sessions.get(session_id)
    if not session: raise HTTPException(404, "Browser session not found")
    if session["session_status"] != BrowserSessionStatus.active: raise HTTPException(409, "Session is not under automation control")
    if PLAYWRIGHT_ENABLED and session_id not in runtimes:
        await _set(session_id, BrowserSessionStatus.failed)
        raise HTTPException(503, "The live browser has stopped; this command was not executed.")
    if req.command_type == "navigate":
        if not req.target_url: raise HTTPException(422, "target_url is required")
        validate_target(str(req.target_url), session["allowed_domains"])
        session["url"] = str(req.target_url)
        if session_id in runtimes:
            await runtimes[session_id].navigate(str(req.target_url))
    if req.command_type == "inspect":
        if session_id in runtimes:
            snapshot = await runtimes[session_id].observe()
            return {"contract_version": CONTRACT_VERSION, "command_id": req.command_id, "status": "completed", "mode": "playwright", "snapshot": snapshot.model_dump(mode="json")}
        if not MOCK_MODE_ENABLED:
            raise HTTPException(503, "The live Chromium session is unavailable; this command was not simulated.")
        # Deterministic mock snapshot is available only when mock mode is explicitly enabled.
        mock_snapshot = {
            "snapshot_id": "mock-snap-01",
            "url": session.get("url", ""),
            "title": "CivicFlow Fictional Local Test Form",
            "headings": ["Simulated Income and Domicile Test Form"],
            "interactive_elements": [
                {"element_id": "e0001", "element_type": "text_input", "label": "Applicant Full Name", "name": "applicantName", "required": True, "enabled": True},
                {"element_id": "e0002", "element_type": "text_input", "label": "Father's / Husband's Name", "name": "fatherName", "required": True, "enabled": True},
                {"element_id": "e0003", "element_type": "text_input", "label": "Date of Birth", "name": "dob", "required": True, "enabled": True},
                {"element_id": "e0004", "element_type": "dropdown", "label": "Gender", "name": "gender", "required": True, "enabled": True},
                {"element_id": "e0005", "element_type": "dropdown", "label": "Social Category", "name": "category", "required": True, "enabled": True},
                {"element_id": "e0006", "element_type": "text_input", "label": "Mobile Number", "name": "mobile", "required": True, "enabled": True},
                {"element_id": "e0007", "element_type": "text_input", "label": "Annual Family Income", "name": "income", "required": True, "enabled": True},
                {"element_id": "e0008", "element_type": "dropdown", "label": "District", "name": "district", "required": True, "enabled": True},
                {"element_id": "e0009", "element_type": "textarea", "label": "Residential Address", "name": "address", "required": True, "enabled": True},
                {"element_id": "e0010", "element_type": "button", "label": "Next: Review Details", "name": "submit", "required": False, "enabled": True},
            ]
        }
        return {"contract_version": CONTRACT_VERSION, "command_id": req.command_id, "status": "completed", "mode": "mock", "snapshot": mock_snapshot}
    if req.command_type == "fill":
        if not req.element_id or req.value is None:
            raise HTTPException(422, "fill requires an element instruction and value")
        if session_id in runtimes:
            result = await runtimes[session_id].fill(req.element_id, req.value)
            return {"contract_version": CONTRACT_VERSION, "command_id": req.command_id, "status": "completed" if result.get("success") else "needs_user_input", "mode": "playwright", "result": result}
        if not MOCK_MODE_ENABLED:
            raise HTTPException(503, "The live Chromium session is unavailable; this field was not filled.")
        return {"contract_version": CONTRACT_VERSION, "command_id": req.command_id, "status": "completed", "mode": "mock", "result": {"success": True, "message": f"Simulated fill for '{req.element_id}'"}}
    # Sensitive values are never reflected, logged, or placed in event payloads.
    return {"contract_version": CONTRACT_VERSION, "command_id": req.command_id, "status": "accepted", "mode": "playwright" if session_id in runtimes else "mock"}

async def _set(session_id: UUID, status: BrowserSessionStatus):
    global PLAYWRIGHT_READY
    if session_id not in sessions: raise HTTPException(404, "Browser session not found")
    current_status = sessions[session_id]["session_status"]
    terminal_statuses = {BrowserSessionStatus.closed, BrowserSessionStatus.expired, BrowserSessionStatus.failed}
    if current_status in terminal_statuses and status not in terminal_statuses:
        raise HTTPException(409, "The browser session is already closed, failed, or expired.")
    if PLAYWRIGHT_ENABLED and session_id not in runtimes and status not in terminal_statuses:
        sessions[session_id]["session_status"] = BrowserSessionStatus.failed
        raise HTTPException(503, "The live browser has stopped.")
    sessions[session_id]["session_status"] = status
    if status in terminal_statuses:
        stream_tokens.pop(sessions[session_id].get("stream_token"), None)
        runtime = runtimes.pop(session_id, None)
        if runtime:
            await runtime.close()
        PLAYWRIGHT_READY = bool(runtimes)
    return await get_session(session_id)

@app.post("/internal/v1/browser/sessions/{session_id}/pause")
async def pause(session_id: UUID): return await _set(session_id, BrowserSessionStatus.paused)
@app.post("/internal/v1/browser/sessions/{session_id}/resume")
async def resume(session_id: UUID): return await _set(session_id, BrowserSessionStatus.active)
@app.post("/internal/v1/browser/sessions/{session_id}/take-control")
async def take_control(session_id: UUID): return await _set(session_id, BrowserSessionStatus.user_control)
@app.post("/internal/v1/browser/sessions/{session_id}/return-control")
async def return_control(session_id: UUID): return await _set(session_id, BrowserSessionStatus.active)
@app.post("/internal/v1/browser/sessions/{session_id}/close")
async def close(session_id: UUID): return await _set(session_id, BrowserSessionStatus.closed)

@app.websocket("/internal/v1/browser/sessions/{session_id}/stream")
async def stream(websocket: WebSocket, session_id: UUID, token: str):
    token_record = stream_tokens.pop(token, None)  # single-use opaque stream credential
    session = sessions.get(session_id)
    token_session, token_expires = token_record if token_record else (None, None)
    if token_session != session_id or not session or session["session_status"] in {BrowserSessionStatus.closed, BrowserSessionStatus.expired, BrowserSessionStatus.failed} or token_expires <= datetime.now(timezone.utc) or session["expires_at"] <= datetime.now(timezone.utc):
        await websocket.close(code=4401)
        return
    await websocket.accept()
    try:
        await websocket.send_json({"contract_version": CONTRACT_VERSION, "event_type": "session_status", "status": session["session_status"].value, "url": session.get("url")})
        portal_url = session.get("url", "")
        fallback_svg_b64 = generate_portal_frame_svg(portal_url)
        runtime = runtimes.get(session_id)
        if not runtime and MOCK_MODE_ENABLED:
            # Mock mode: stream synthetic portal frames
            while session["session_status"] not in {BrowserSessionStatus.closed, BrowserSessionStatus.expired}:
                await websocket.send_json({
                    "contract_version": CONTRACT_VERSION,
                    "event_type": "frame",
                    "data": fallback_svg_b64,
                    "mime_type": "image/svg+xml",
                    "url": portal_url,
                    "title": "CivicFlow Simulated Demo · No live portal",
                })
                await asyncio.sleep(1.5)
            return
        if not runtime:
            await websocket.send_json({
                "contract_version": CONTRACT_VERSION,
                "event_type": "stream_unavailable",
                "message": "No live browser is attached to this session.",
            })
            await websocket.close(code=1011)
            return

        while session["session_status"] not in {BrowserSessionStatus.closed, BrowserSessionStatus.expired, BrowserSessionStatus.failed}:
            page = runtime.controller.session.page
            if page.is_closed():
                await _set(session_id, BrowserSessionStatus.failed)
                await websocket.send_json({
                    "contract_version": CONTRACT_VERSION,
                    "event_type": "stream_unavailable",
                    "message": "The Chromium window was closed. Connect a new browser session to continue.",
                })
                await websocket.close(code=1011)
                return
            if session["session_status"] == BrowserSessionStatus.user_control:
                await asyncio.sleep(0.5)
                continue
            try:
                frame = await page.screenshot(type="jpeg", quality=65)
                await websocket.send_json({
                    "contract_version": CONTRACT_VERSION,
                    "event_type": "frame",
                    "data": base64.b64encode(frame).decode("ascii"),
                    "mime_type": "image/jpeg",
                    "url": page.url,
                    "title": await page.title()
                })
            except Exception:
                await websocket.send_json({
                    "contract_version": CONTRACT_VERSION,
                    "event_type": "stream_unavailable",
                    "message": "The live portal preview stopped. Reconnect the browser session to continue.",
                })
                await _set(session_id, BrowserSessionStatus.failed)
                await websocket.close(code=1011)
                return
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        return
    except Exception:
        return
