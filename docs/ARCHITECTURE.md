# CivicFlow Architecture

```text
Citizen -> React frontend -> FastAPI backend -> Agent orchestrator
                                               |        |       |
                                         knowledge  profile  documents
                                               |
                                         BrowserClient (HTTP/JSON)
                                               |
                                         Browser Worker
                                               |
                                      Playwright / Chromium
```

The browser worker is a separate service. The agent must not import its Playwright implementation; `contracts/browser-api-v1.yaml` is the boundary. Service rules and workflow plans are data driven so new public-service workflows do not require scholarship-specific core logic. Source ingestion preserves URL, source ID, document title, and page number through chunking and FAISS retrieval. A source is marked verified only when its HTTPS host matches an explicit allowlist and its publisher is recorded.

## Phase 0 deployment

Docker Compose defines a backend health service, a browser-worker health service, and PostgreSQL for local development. Future phases add the application behavior behind these service boundaries.
