# API Contracts

The citizen backend API is versioned under `/api/v1`. Register or log in with `/auth/register` or `/auth/login`, then send the returned bearer token on authenticated requests. Profile and documents are scoped to the authenticated user. Task events are delivered by polling `/tasks/{task_id}/events?after={sequence}`; workflow continuation uses `/tasks/{task_id}/resume`.

Task start accepts `user_request` and optional `require_approval`. The task status endpoint exposes a resumable pending prompt in its state. Approval decisions use `/approvals/{approval_id}/decision`. Browser screenshot, user control, and input endpoints are proxied through the backend and enforce task ownership.

The browser worker contract is separately versioned as `/api/v1` and defined in `contracts/browser-api-v1.yaml`. Shared Pydantic models live in `packages/civicflow_contracts/civicflow_contracts/browser.py`.

The agent depends on JSON request and response models only. Observation element IDs are observation-scoped; actions must name the observation they were based on. The worker must reject stale observations and must not accept arbitrary JavaScript. Sensitive authentication fields are not agent-fillable. Health endpoints are available at `/healthz` on each service.

Agent requirements are represented by `ServiceRequirements`. Curated service requirements cite retrieved chunk IDs; the API exposes source links and uncertainty notices. Stale or unverified material is labeled for human confirmation.
