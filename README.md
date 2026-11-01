# CivicFlow

CivicFlow is a controlled, resumable assistant for public-service applications. It helps citizens understand requirements, prepare information, and interact with service portals while keeping sensitive and consequential actions under citizen control.

The repository includes a FastAPI service, checkpointed LangGraph workflow, browser-worker boundary, React workspace, profile/document/task APIs, and local mock/test coverage. Government service and source fixtures are intentionally marked unverified until official portals and requirements are independently checked.

## Repository map

- `backend/` — citizen-facing API service (Member 1 boundary)
- `browser_worker/` — isolated browser service (Member 3 boundary)
- `packages/civicflow_contracts/` — shared JSON/Pydantic contracts
- `contracts/` — versioned HTTP API contract
- `docs/` — architecture, implementation plan, and progress
- `notebooks/` — experiments; reusable code belongs in modules
- `agent.ipynb` — existing user notebook, preserved

## Member 2 agent setup

The agent uses Ollama by default, with your cloud model `nemotron-3-super:cloud` for chat and BGE-M3 (`BAAI/bge-m3`) for local semantic retrieval. Ollama cloud models require an Ollama sign-in; chat requests use Ollama cloud inference while embeddings stay local.

1. Install Ollama and start its local service.
2. Sign in to Ollama: `ollama signin`.
3. Pull the configured cloud model once: `ollama pull nemotron-3-super:cloud`.
4. Install Python dependencies: `python -m pip install -r requirements.txt`.
5. Cache BGE-M3 once: `python -m backend.app.agent.services.embeddings --download-model`.
6. Copy `.env.example` to `.env`. For running Python directly, keep `OLLAMA_BASE_URL=http://localhost:11434`.
7. Run the preserved Member 2 app directly with the commands in Local development below.

OpenAI is disabled in this setup. The agent uses `nemotron-3-super:cloud` through Ollama. OpenAI can be enabled later only by explicitly setting `LLM_PROVIDER=openai`, `OPENAI_API_KEY`, and `OPENAI_MODEL` in `.env`.

## Preserved Member 2 local app

Run the backend and Vite frontend in separate PowerShell terminals from the repository root:

```powershell
python -m uvicorn backend.app.main:app --reload --port 8000
```

```powershell
npm --prefix frontend run dev -- --host 127.0.0.1 --port 3000
```

Open `http://localhost:3000`. Copy `.env.example` to `.env` and use `OLLAMA_BASE_URL=http://localhost:11434` for the host Ollama service. The Member 2 development browser worker remains separate; set its private token and exact approved HTTPS hosts before enabling navigation.

The browser worker fails closed when its service token or destination allowlist is missing. Development service fixtures have no portal URLs. Configure only verified hosts before enabling navigation.

Python 3.11–3.13 is recommended. Install Chromium using `python -m playwright install chromium` only when using real Playwright browsing.

The API serves `/api/v1/auth/register` and `/api/v1/auth/login`; all profile, document, task, event, approval, and browser-control endpoints require the returned bearer token. Uploaded files are scoped by user. The browser integration stays disabled unless a worker token is configured, and unverified service fixtures cannot open a portal.

No real government portal is contacted by the automated browser integration test; it uses in-memory mock pages.

Run the offline service demonstration with `python -m backend.app.demo`. It shows the Maharashtra domicile and scholarship workflows with links to their official sources. The domicile checklist PDF is older and is explicitly marked for confirmation. For scheme questions, CivicFlow first matches the user's wording to the service catalogue, checks retrieved source relevance, and searches official government pages when configured; it asks a follow-up only when it cannot identify a sufficiently clear scheme or jurisdiction.

## Run the integrated team stack without Docker

The Member 1 Core API, Member 2 LangGraph AI service, Member 3 Browser Agent, and Next.js interface run as local processes. No container engine, PostgreSQL server, or Redis server is required for the in-memory local demo.

Use Python 3.11, 3.12, or 3.13 and Node.js 22. From Command Prompt or PowerShell at the repository root:

```powershell
scripts\setup-local.cmd
scripts\run-local.cmd
```

The setup reuses an active Python virtual environment when one is activated in the terminal. Otherwise it creates `.venv` and reuses compatible system packages, reducing duplicate disk use. Missing service dependencies are installed into the selected environment. If you install manually, use `python -m pip install -r requirements.txt` from the repository root.

The launcher prints the frontend link and all service health links after they become ready. It prefers frontend port 3001 and service ports 8000-8002, and automatically selects free fallback ports when Windows has reserved the defaults. Use the printed frontend link to open the app. Stop the background services cleanly with:

```powershell
scripts\stop-local.cmd
```

The launcher reads provider settings from the root `.env`, uses Ollama Nemotron (`OLLAMA_CHAT_MODEL=nemotron-3-super:cloud`) and keeps OpenAI disabled. Sign in to Ollama on the host before chatting. For semantic source retrieval, cache BGE-M3 once after setup in PowerShell:

```powershell
$env:HF_HOME = Join-Path (Get-Location).Path 'runtime\huggingface'
.\.venv\Scripts\python.exe -m backend.app.agent.services.embeddings --download-model
```

The model download is several gigabytes and is stored in the ignored `runtime\huggingface` cache that the launcher uses. Setup installs Chromium, and `scripts\run-local.cmd` starts live browser sessions by default. During an application session, a visible Chromium window opens on this computer; use **Take manual control** to interact with that window. To run only the simulated UI, explicitly use `scripts\run-local.cmd -MockBrowser`.

Setup builds the frontend for production mode to reduce local memory use. After changing frontend source code, rebuild it before restarting with `pnpm --dir frontend_member1 exec next build --webpack`.

For live form assistance, create an application from a listed service. CivicFlow opens that service's approved portal in its isolated Chromium window and shows a live preview in the workspace. Sign in and handle OTP/CAPTCHA prompts yourself in the Chromium window. Use **Inspect page elements** and **Fill field** for supported text fields, or keep manual control and use the portal directly. Review and complete consent, legal declarations, payment, and final submission yourself. If the preview reports that Chromium stopped, connect a new browser session; the UI does not claim that simulated content is a live portal.

### Adding a service catalogue JSON

The AI service loads additional catalogue entries from `backend/app/agent/data/service_catalog.json` when it starts. You can replace that file with a JSON array containing `service_id`, `name`, `category`, `jurisdiction`, `official_portal`, `description`, and `official_docs_url`. To use another file, set `CIVICFLOW_SERVICE_CATALOG` to its path before starting the AI service.

For each entry, CivicFlow creates a service-context chunk in the in-memory FAISS index. A request then goes through catalogue retrieval, LLM relevance judging, and a guarded fetch of the configured official documentation URL. The fetched text is chunked and passed to the requirements and eligibility stages. Only HTTPS `gov.in` URLs are fetched; portal and documentation URLs are returned as source citations. Restart the AI service after changing the catalogue.

The Core API uses in-memory application records in this local demo, so those records reset when it stops. Browser sessions are isolated in the Browser Agent process and also end when stopped. The existing Member 2 Vite app and source files remain preserved.
