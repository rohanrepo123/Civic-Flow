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
- The direct launcher now defaults to live Playwright/Chromium. Setup installs Chromium; `-MockBrowser` must be requested explicitly for simulated UI-only mode. Failed live browser launches return HTTP 503 and no longer claim a mock session opened the real portal.
- Added `.cmd` wrappers for setup, run, and stop so the scripts can be launched from Command Prompt as well as PowerShell.
- Fixed Windows PowerShell 5.1 parsing by keeping its script text ASCII-only, and made stop clean stale process records without relying on CIM access. The stale PIDs were confirmed not running and their record was removed.
- Docker was not started. The prior setup attempt could not reach the package index and Chromium is not installed in the selected Python environment. Run `scripts\setup-local.cmd` on a machine with package and browser-download access before launching services.
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
- Validation for the session and failure-path changes is recorded in the 2026-11-01 orchestration repair section below.

## JSON service catalogue and official document retrieval

- Added `backend/app/agent/data/service_catalog.json` with the supplied Maharashtra MahaDBT, Central NSP, and Bihar PMS entries.
- Extended `ServiceRecord` to accept education services, descriptions, and `official_docs_url`. The registry loads the built-in catalogue plus an optional file configured by `CIVICFLOW_SERVICE_CATALOG`.
- Each catalogue entry becomes a service-context chunk in the existing FAISS/BGE retrieval layer. The graph now runs catalogue retrieval and LLM relevance judgment for every service request, then fetches the configured official document and chunks its HTML or PDF content before requirements, eligibility, and portal guidance.
- Official document fetching is restricted to HTTPS `gov.in` hosts, follows only government-domain redirects, caps response size, and returns no content when the fetch fails. Source URLs remain attributable in the response.
- Validation: Python compilation, service-catalogue JSON validation, ServiceRegistry loading, and frontend TypeScript compilation passed.

## Orchestration repair and 120-service registry (2026-11-01)

- Repaired the source-pipeline import and passed the matcher method (`.match`) to the graph. Retrieval now searches catalogue vectors before service selection, judges the candidate IDs, fetches bounded official documents before final source relevance judgment, and answers general information questions without requesting applicant details.
- Added the supplied `D:/service_registry_110_v2.json` as the checked-in 120-record service catalogue. Added its category values, derived parenthetical aliases, and case-insensitive service-ID overrides so the registry and index use the configured catalogue. The vector index is fingerprinted and cached as non-pickle NumPy vectors under `runtime/vectors`.
- Added `.nic.in` support for the Bihar entries, bounded streaming, prevalidated redirects, same-host guideline discovery, and citation-checked requirement extraction for newly catalogued services.
- New application creation now waits for Core API and stores its canonical application ID. Existing browser-local application IDs are adopted by Core API when their browser session is created, preventing the workspace's `Application not found` error.
- Chat is scoped by an HTTP-only signed local identity or authenticated user. Initial chat IDs are unique; late responses update their originating chat; casual messages do not resume workflow interrupts. Workflow checkpoints, pending runs, and compact memories persist in local SQLite. Agent turns are serialized and have an explicit timeout; Core API allows a longer downstream timeout.
- Connected the Member 3 worker over its HTTP contracts for live observation and guarded non-sensitive field preparation. Simulated sessions clearly do not report live fills as successful. OTP, CAPTCHA, payment, consent, submission, and legal-declaration actions remain blocked.
- The browser workspace's pause, manual-control, refresh, and stop controls now call the worker; the direct-portal mode opens the official site in a new tab because embedding is frequently blocked.
- Validation: 43 targeted backend tests passed, including catalogue order, `.nic.in` document fetch, redirect and size limits, grounded extraction, SQLite restart resume, and vector-cache tests. Chat session isolation passed; frontend `tsc --noEmit` and Webpack production build passed; Python `compileall` and `git diff --check` passed. The full backend suite could not collect four modules because the active Python environment lacks SQLAlchemy and PyMuPDF. A direct Core API adoption smoke check could not import the route module because its app package eagerly imports the unavailable Argon2 dependency. The BGE warm-up smoke check also could not run because Pillow is absent from this environment; lexical catalogue retrieval remains the fallback when BGE cannot initialize.
- Limitations: local Core API application storage and the browser worker's sessions remain in-memory. The chat and workflow checkpoint state persists across AI restarts, but browser sessions themselves are not restored after a Browser Agent restart. Automated portal interaction remains constrained to the worker's existing grounded fill contract and user-controlled steps. No live portal/browser end-to-end run was performed in this environment.

## Live local browser path and microservice reliability (2026-11-01)

- Changed raw local startup to use Playwright/Chromium by default and install Chromium during setup. `-MockBrowser` is now an explicit UI-only option; the previous `-WithPlaywright` flag remains accepted for compatibility.
- Live sessions use a visible, isolated Chromium window so the citizen can sign in and manually interact with the actual portal after taking control. The in-app view streams screenshots from that same session. Direct portal mode is labeled as a separate browser tab and not as the controlled session.
- Removed silent mock fallbacks from live session creation, inspection, filling, and screenshots. A missing browser or failed live preview returns an error, marks the session failed, and permits a fresh connection. Browser sessions are expired, closed on service shutdown, and pruned after their TTL.
- Added a connect guard to avoid duplicate Chromium windows during frontend development-mode effect replay. The launcher checks the installed Chromium executable before starting live services.
- Replaced the credential-like value in `.env.example` with a blank optional search key and a non-secret local secret placeholder.
- Validation: the configured backend suite passed 108 tests with 1 skipped; the Browser Agent regression suite passed 8 tests. Frontend `tsc --noEmit`, the chat-session script, Python `compileall`, PowerShell parser checks, and `git diff --check` passed. The production frontend build completed.
- Live end-to-end verification: created a temporary Core API draft, opened the real MahaDBT portal in visible Playwright Chromium, received a live `image/jpeg` WebSocket frame, and inspected 122 portal controls. The session was closed and the temporary application deleted. No form was submitted. All four local services now return HTTP 200 at the frontend and readiness endpoints.
- Resource limitation: BGE-M3 is not cached. Two model downloads stopped before completion; the standard HTTP retry hit `MemoryError` while streaming the large model weights. Retrieval continues with the lexical catalogue fallback. The setup output and README now point users to the launcher's exact `runtime\huggingface` cache location.
- Known limits: local Core API application storage and Browser Agent sessions remain in-memory. Chat and workflow checkpoints persist across AI Agent restarts, but live browser sessions do not restore after Browser Agent restarts. OTP, CAPTCHA, payment, consent, legal declarations, and final submission remain user-controlled.

## Runtime API routing repair (2026-11-01)

- Fixed the service-start and chat failures caused by a production frontend bundle targeting the build-time default Core API port while `run-local.ps1` selected different available ports. The frontend now sends Core API requests to a same-origin Next.js Route Handler, which forwards them to the runtime `CORE_API_URL` set by the launcher. Removed build-time API rewrites and direct browser-worker port assumptions.
- Added the selected Browser Agent's WebSocket stream URL to the shared browser-session contract and Core API response so the workspace connects to the correct dynamically selected worker port.
- Preserved upstream error details for service creation failures and fixed empty-body proxy responses for successful HTTP 204 deletions.
- Validation: frontend type-check, Python `compileall`, and `git diff --check` passed; production build succeeded. Through the running production app, created a temporary MahaDBT application, confirmed its Browser Agent stream URL points to port 8011, sent a casual `hi` and received a Nemotron greeting, then closed the session and deleted the test application. Frontend and all three API readiness endpoints returned HTTP 200.
- Final local smoke check: restarted CivicFlow on ports 3001 and 8009-8011; verified frontend/Core API/AI Agent/Browser Agent readiness, Core API identity and 33-service catalog routes, application create/delete, live browser-session URL selection, and a casual Nemotron chat. Stopped all four tracked services and the stale CivicFlow dev server; confirmed all local app ports 3000-3010 and 8000-8020 are closed and no CivicFlow service record remains. Also stopped the verified loopback Uvicorn listeners previously found on ports 8000-8008.

## Real portal routing and HTTPS validation (2026-11-01)

- Replaced the legacy `mock-citizen-certificate` catalog entry's localhost sandbox URL and invented sample eligibility/documents with Maharashtra's Aaple Sarkar service directory; kept the old service ID for existing drafts.
- Custom application creation now resolves a full state/jurisdiction name against the configured Geo registry and selects only its configured HTTPS portal. HTTP custom portal URLs are rejected; unknown jurisdictions remain without a guessed portal.
- The custom-service UI now sends the full jurisdiction name instead of truncating it into an invalid state code. Workspace resolution ignores stale non-HTTPS localStorage portal URLs and falls back to a catalog HTTPS URL when available. It no longer invents localhost:9090 for unknown portals.
- The browser viewer now explains when no verified HTTPS portal is configured and does not attempt to connect.
- Added regression coverage for the legacy certificate service URL, full-state-name resolution, unknown jurisdiction behavior, and rejection of HTTP portal URLs.
- Validation: frontend `pnpm exec tsc --noEmit` passed; `git diff --check` passed; no CivicFlow listeners were found on ports 3000-3010 or 8000-8020. Focused pytest collection was blocked by the repository's conflicting `civicflow_contracts` package paths; after constraining pytest configuration, import/startup hung before producing test output. No services were started during this check.
- Follow-up validation: `pnpm exec next build --webpack` succeeded after clearing the generated `.next` directory; the build required elevated filesystem access because Windows blocked Next.js generated-directory creation in the sandbox. Ports remain closed.

## Hosting preparation and Groq provider (2026-11-01)

- Added Groq as an explicit provider on the existing OpenAI-compatible JSON chat adapter. `GROQ_API_KEY` is read from the environment; `GROQ_MODEL` defaults to `openai/gpt-oss-20b`. The local launcher now honors the selected provider from `.env` rather than always forcing Ollama.
- The workspace `.env` selects Groq, but remains ignored and was not staged. `.env.example` documents the optional Groq variables; Ollama Nemotron remains the default for new setups.
- Verified the configured Groq credential against the models endpoint (HTTP 200) and a minimal JSON chat completion (HTTP 200, `{"ready":true}`). The key was passed only in authorization headers and not printed.
- Added deployment notes for Vercel's frontend and the separate Core API, AI Agent, and Chromium Browser Agent. Added `BROWSER_AGENT_PUBLIC_URL` so Core API can return a browser WebSocket URL reachable by a hosted user's browser.
- Validation: Python compilation, PowerShell launcher parsing, Groq client configuration selection, Next frontend typecheck/build from the prior fix, and `git diff --check` passed. A focused pytest invocation remained hung during collection and was interrupted; provider behavior was verified directly and with the live API check.
- Hosting limitation: no Vercel CLI or linked Vercel project is available here. The Core API currently holds application records in memory, so the repository is not yet ready for durable production applications. GitHub publication is separate from running the services.
