# CivicFlow Progress

## Status

Phases 0–13 are implemented as a runnable, local demonstrator. The app includes a FastAPI backend, React workspace, SQLAlchemy persistence, a checkpointed LangGraph, official source snapshots, and an isolated browser worker. Portal automation is opt-in and stays behind explicit HTTPS host allowlists.

## Implemented

- Phase 0: monorepo, ownership guidance, shared API contracts, health endpoints, Docker Compose, and environment configuration.
- Phase 1: validated models for intent, services, sources, eligibility, documents, plans, tasks, events, approvals, and browser actions.
- Phase 2: configurable structured LLM extraction, an offline intent baseline, service matching, and clarification pauses.
- Phases 3–4: PDF/HTML ingestion, attributed source chunks, retrieval, cited requirements, and explicit uncertainty for stale material.
- Phase 5: deterministic eligibility evaluation; missing or invalid values do not produce an eligibility claim.
- Phase 6: PDF text extraction and optional LLM document analysis. OCR is not included; low-confidence, image-only, or unmatched fields need human review.
- Phase 7: service-specific preparation plans with legal declarations and consequential steps reserved for the citizen.
- Phase 8: browser client, local action policy, mock worker, idempotency, and stale-observation handling.
- Phase 9: isolated Playwright worker API, bearer authentication, HTTPS domain allowlists, user control, screenshots, TTL cleanup, and file references.
- Phase 10: LangGraph workflow with state transitions, checkpoints, human interrupts, resume, event history, approval rechecks, and safe error summaries. Checkpoints use PostgreSQL in Compose; the local default uses an in-memory checkpointer.
- Phase 11: authenticated account, profile, private document, task, event, approval, browser screenshot/control/input APIs; React task and activity workspace; document upload and resume UI.
- Phase 12: API ownership/authentication tests, profile secret rejection, document permission checks, mock browser isolation/idempotency/stale-action coverage, and workflow resume/approval tests.
- Phase 13: runnable two-service demo for Maharashtra domicile certificates and MahaDBT scholarships with source links and uncertainty labels.
- Preserved the original root `agent.ipynb`.

## Official source material

- Maharashtra domicile service listing: Aaple Sarkar Right to Public Services page. It lists the service, designated officer, and 15-day notified timeline.
- Domicile checklist: the official Revenue Department PDF lists documents and INR 20 fee. Its age is flagged in the app, so users are told to confirm the checklist and fee on the live portal.
- Scholarship: MahaDBT FAQ/notice is current source material for the multiple-scheme structure and the 2026–27 portal notice. The assistant asks for the exact scheme before assessing eligibility.

The domicile and MahaDBT portal URLs are configured from official government pages. Browser navigation still requires a service token and an administrator-configured exact host allowlist. No automated test submits to a government portal.

## Validation

- `python -m compileall -q backend` — passed.
- `python -m pytest -q -p no:cacheprovider` — 88 passed, 1 opt-in browser integration test skipped.
- `npm run build` — passed; Vite generated the production bundle.
- `docker compose config --quiet` — passed.
- `python -m backend.app.demo` — ran both Maharashtra service examples offline.
- `CIVICFLOW_RUN_BROWSER_E2E=1 python -m pytest browser_worker/tests/test_playwright_integration.py -q -p no:cacheprovider` — 1 passed against in-memory pages.
- The normal suite skips the opt-in Chromium integration test unless `CIVICFLOW_RUN_BROWSER_E2E=1`.

The Windows environment emits known Pydantic/Python 3.14 and experimental NumPy build warnings. Those warnings did not fail the checks. PostgreSQL checkpoint operation is configured in the Compose path but was not exercised against a live PostgreSQL service in this environment.

## Member 2 provider alignment

- Preserved the pre-change project source snapshot at `civicflow_pre_member2.zip` (120 source/config/doc files; secrets, uploaded files, database files, caches, and dependency folders excluded).
- Added Ollama as the default agent provider with configurable `nemotron-3-super:cloud`, bounded JSON chat calls, zero temperature by default, and no automatic Ollama model download.
- Added explicit OpenAI chat provider selection through `LLM_PROVIDER=openai`; it requires an API key and never acts as a fallback.
- OpenAI is currently disabled in the workspace `.env` (`LLM_PROVIDER=ollama`, blank `OPENAI_MODEL`); the adapter remains available for a future explicit opt-in.
- Kept hosted document analysis disabled by default; it requires the explicit `OPENAI_ALLOW_DOCUMENT_DATA=true` deployment setting after the deployment has obtained consent.
- Added lazy BGE-M3 embeddings, normalized batched vectors, auto CPU/CUDA selection, and a local-cache-only default. The explicit `--download-model` command downloads weights.
- Wired curated source retrieval through the existing FAISS retriever and configured embedding provider.
- Expanded the catalogue to 20 government portal/service seeds plus the existing Karnataka development fixture; new discovery entries are marked unverified and have no invented requirements.
- Added member-specific environment examples, Docker dependency/cache settings, and setup/run instructions.
- Fixed local Vite development routing by proxying `/api` and `/healthz` to the backend; account registration now reaches FastAPI instead of returning an empty Vite response.
- Improved frontend auth error handling for non-JSON responses and added service/jurisdiction fields when clarification has no candidate buttons.
- Live demo verified: account registration returned HTTP 201, a custom domicile request completed through intent, source retrieval, requirements, eligibility, document validation, and planning.
- Added a casual conversation intent for greetings, thanks, and small talk. These requests complete locally with a friendly response and do not invoke service resolution, retrieval, embeddings, eligibility, documents, or browser actions.
- Full validation after the casual-chat change: `python -m pytest -q -p no:cacheprovider` passed (92 passed, 1 skipped).
- Validation: `python -m pytest -q -p no:cacheprovider` passed (91 passed, 1 skipped); with `CIVICFLOW_RUN_BROWSER_E2E=1`, the full suite passed (92 passed); `docker compose config --quiet` passed. A live Ollama request to `nemotron-3-super:cloud` returned JSON successfully after the provider was updated to strip Nemotron's reasoning preamble from the final structured response.
- Python 3.11 venv collection was made independent of Docker/PostgreSQL by forcing in-memory SQLite in backend test setup. Embedding settings tests now clear every embedding-related variable loaded from `.env`. Re-run in the reported venv passed: 91 passed, 1 skipped.
- Added a ChatGPT-style conversation panel showing the citizen request and CivicFlow response as chat bubbles while retaining workflow controls and source provenance.
- Expanded conversation handling so casual talk stays conversational, public-service forms and schemes remain in scope even when the exact service is unknown, and unrelated requests receive a safe out-of-scope response instead of entering the workflow.
- Split the frontend history into Recent applications and Recent conversations so casual or out-of-scope chats no longer appear as applications while remaining available to reopen.
- Updated the composer wording to “Message CivicFlow” / “Start chat” so casual conversations are presented as chats rather than applications.

## Member 1–3 integration (2026-11-01)

- Retrieved Member 1 `Amankum25/null` at `e6067cd` and Member 3 `rohi5431/civicflow-browser` at `3278bfb`; source checkouts are retained under `integration_sources/` for traceability.
- Preserved the Member 2 backend, Vite frontend, existing Compose path, and notebook. Added Member 1 contracts/services/Next.js app as parallel integrated stack files instead of overwriting the existing app.
- Verified the browser worker package copied in Member 1's repo matches Member 3's package files, so the integrated browser service uses Member 3's worker implementation and Member 1's API wrapper.
- Added an adapter from Member 2 LangGraph, service registry, curated BGE retrieval, and eligibility engine to Member 1's v1 AI contracts. The AI service has been changed from its mock implementation to call that adapter. OpenAI remains disabled; Ollama Nemotron is the configured provider.
- Wired the Next.js chat page to Core API assistant messages, and routed browser health/session/commands/control/stream-token requests through Core API. Core API adds the configured bearer token for its internal browser-service requests.
- Hardened the integrated demo labeling: mock sessions are described as simulated, fill fallback copy does not claim verification, and demo personal data is explicitly fictional sample content.
- Added `backend/infrastructure/docker-compose.yml` as an additive team-stack compose file with separate ports (UI 3001, Core 8010, AI 8011, Browser 8012). Setup instructions are in the root README.
- Validation for the integration: `python -m compileall -q backend` passed; the Member 1 AI service suite passed (2); browser worker security tests passed (5); `pnpm exec next build --webpack` and `pnpm exec tsc --noEmit` passed; `docker compose -f backend/infrastructure/docker-compose.yml config --quiet` passed.
- Validation limits: the repository-wide pytest run cannot collect under the installed Python 3.14 environment because native FAISS terminates the interpreter (`Windows fatal exception 0xc0000008`). Core API tests cannot collect because the installed `dotenv` package does not export `dotenv_values`. The default Turbopack build also failed to spawn its CSS worker in this environment; the same Next.js production build succeeded with Webpack. No real government portal has been submitted to or used for automated testing, and the Compose services were not started here.

## Direct local runtime (no containers)

- Added PowerShell setup, run, and stop scripts to create one Python environment, install the four integrated services and shared contracts, install the Next.js dependencies, launch each service as a local process, capture logs under `runtime_logs/`, and terminate only the recorded CivicFlow process trees.
- Added Core API local demo mode so its readiness endpoint does not require PostgreSQL or Redis; application records are already in-memory for this phase.
- The direct launcher defaults the Browser Agent to simulated mode to avoid downloading a Chromium binary. `-WithPlaywright` opts into Playwright after the user installs Chromium separately.
- Added `.cmd` wrappers for setup, run, and stop so the scripts can be launched from Command Prompt as well as PowerShell.
- Fixed Windows PowerShell 5.1 parsing by keeping its script text ASCII-only, and made stop clean stale process records without relying on CIM access. The stale PIDs were confirmed not running and their record was removed.
- Docker was not started. No CivicFlow service or Docker process was running when checked. Local scripts were syntax-checked. An attempt to provision Python dependencies could not reach the package index because DNS/network access is unavailable in this environment; finish setup on a machine with package access, then run the local launcher. The installed Python 3.13 has most ML packages already, so setup reuses compatible system packages and installs only missing dependencies into `.venv`.
- Updated the local launcher to choose available frontend/API ports from fallback ranges when the defaults cannot be bound. On 2026-11-01, Windows reported ports 3001 and 8000–8002 unbindable while listener/process tables showed no owning process. Startup then stopped because `.venv` lacks `uvicorn`; the available Python 3.11 venv points to a missing Windows Store interpreter, and Python 3.14 remains unsupported by the FAISS stack. No services remain running and no link is currently available.

## Conversational intent and progressive information collection

- Extended the Member 2 intent model with `collected_information`; the workflow updates this field and applicant profile each time a requested value is supplied.
- Added `history` to the Core chat contract and persist a conversation ID with the Next.js chat, so follow-up messages remain in the same conversation.
- The AI runtime stores interrupted LangGraph runs by conversation ID and resumes the same checkpoint when the citizen answers. It requests one missing field at a time and can reconstruct a recent service intent from submitted chat history if the AI process restarted.
- Resolved service name and jurisdiction are written back into intent state. Required documents are listed as outstanding without blocking basic preparation or forcing the user to provide all documents in one chat turn.
- Improved downstream error visibility: Core API reports the downstream HTTP status, and AI logs only the exception class, avoiding user content in logs.
- Validation: Python 3.13 `compileall`, Pydantic contract/intent smoke check, Next.js `tsc --noEmit`, and Windows PowerShell 5.1 parser checks passed. Pytest was unavailable under Python 3.13 and the referenced Python 3.11 venv executable could not be launched from this environment; the Python 3.14 FAISS crash remains the repository-wide test limitation.

## Scheme eligibility information flow

- Split general scheme eligibility questions from personal eligibility assessments with `eligibility_is_personal` in the intent contract. General questions now bypass applicant-profile loading, deterministic personal evaluation, and missing-applicant-field collection.
- Added explicit LangGraph nodes for VectorDB retrieval, LLM relevance judgment, optional official web fallback, and a concise sourced information answer.
- Added an optional Tavily adapter, enabled only when `TAVILY_API_KEY` is configured. It keeps HTTPS `.gov.in` results and marks them unverified; the LLM must still ground its answer in returned source text. With no search key/results, the assistant reports the limits of available curated material.
- The curated MahaDBT entry currently describes the multi-scheme structure and portal, not eligibility rules for every individual scholarship. The assistant must say exact criteria are unavailable until a matching scheme source is added or found.
- Validation: `py -3.13 -m compileall -q backend` passed. No live search was attempted and no test suite was run.

## MahaDBT resolution and layer-specific conversation memory

- Added MahaDBT, MahaDBT form, MahaDBT scholarship, and Maha DBT as aliases for the Maharashtra scholarship service. The intent extractor preserves this named alias and deterministically fills Maharashtra, including when the configured LLM returns only a generic scholarship label.
- Replaced technical or generic clarification wording with plain language: when the form is unknown, ask what it is about and which state it is for; when the service is known but state is missing, ask “Which state is this for?”
- Added separate compact per-conversation memory for intent interpretation, resolved service/jurisdiction, and knowledge source continuity. Context is scoped to the intent or source-judge stage that uses it and reconstructed from recent chat history after an AI process restart. Applicant details are not included in these memories.
- Validation: `py -3.13 -m compileall -q backend` passed, and a PowerShell catalogue check confirmed the MahaDBT alias maps to Maharashtra. A Python resolver smoke check stalled during imports and was interrupted; no full test suite was run.
- Generalized discovery beyond MahaDBT: when deterministic catalogue matching cannot choose, a separate LLM matcher reviews the complete service catalogue, current intent, and service-resolution memory. It only returns a known service ID above a confidence threshold, respects explicit jurisdiction, and leaves true ambiguity for a simple user clarification. Once matched, the existing service-specific VectorDB relevance judgment and official web fallback gather eligibility context.
- Follow-up validation: Python compilation and the PowerShell MahaDBT catalogue mapping check passed; the Python resolver smoke check still cannot complete because imports stall in this environment. No full test suite or live web search was run.

## Chat sessions and retrieval fallback

- Added named local chat sessions with separate conversation IDs, independent message histories, session switching, deletion, and a New chat action. Existing single-chat local storage is migrated into one session instead of being duplicated into every new chat.
- Fixed the 502/503 failure path when the local BGE-M3 model is not cached. Curated knowledge now falls back to service-scoped lexical retrieval until BGE-M3 is downloaded; semantic retrieval resumes automatically after restart. The AI service continues to expose only a safe error message to the user and does not log user content.
- Added a deterministic intent fallback when Nemotron/Ollama is temporarily unavailable or returns malformed JSON, so a transient model failure no longer turns a normal chat message into a 503/502.
- Validation for this change is pending TypeScript and Python static checks.

## JSON service catalogue and official document retrieval

- Added `backend/app/agent/data/service_catalog.json` with the supplied Maharashtra MahaDBT, Central NSP, and Bihar PMS entries.
- Extended `ServiceRecord` to accept education services, descriptions, and `official_docs_url`. The registry loads the built-in catalogue plus an optional file configured by `CIVICFLOW_SERVICE_CATALOG`.
- Each catalogue entry becomes a service-context chunk in the existing FAISS/BGE retrieval layer. The graph now runs catalogue retrieval and LLM relevance judgment for every service request, then fetches the configured official document and chunks its HTML or PDF content before requirements, eligibility, and portal guidance.
- Official document fetching is restricted to HTTPS `gov.in` hosts, follows only government-domain redirects, caps response size, and returns no content when the fetch fails. Source URLs remain attributable in the response.
- Validation: Python compilation, service-catalogue JSON validation, ServiceRegistry loading, and frontend TypeScript compilation passed.
