# CivicFlow: Complete Implementation Plan for Codex

**Project:** CivicFlow
**Architecture:** Multi-service AI agent with controlled browser automation
**Implementation approach:** Notebook-first prototyping, modular Python implementation, API-based integration
**Team size:** 3 members
**First demonstrator:** Maharashtra scholarship application
**Long-term goal:** Support different government and public-service workflows without rewriting the agent for every service.

---

# 1. Project objective

Build an AI-powered public-service assistant that helps citizens understand, prepare, and complete government-service applications.

A citizen should be able to say:

> I want to apply for a domicile certificate in Maharashtra. Help me complete the application.

CivicFlow should:

1. Understand the citizen's request.
2. Identify the relevant government service and jurisdiction.
3. Retrieve official requirements and application instructions.
4. Retrieve the citizen's profile and available documents.
5. Evaluate eligibility using deterministic rules.
6. Identify missing information and documents.
7. Extract and validate document information.
8. Generate a service-specific execution plan.
9. Open the appropriate government website in an embedded browser.
10. Observe the website and decide the next action.
11. Execute permitted actions through the browser worker.
12. Pause when citizen intervention or approval is required.
13. Resume from the same browser session after intervention.
14. Verify the actual outcome.
15. Provide a final summary with application or tracking details when available.

**Important architectural principle:** Scholarship is only the first use case. Do not write scholarship-specific logic into the core agent.

The architecture must support other services through configuration, structured requirements, and service-specific plans.

# 2. High-level architecture

Use four main components.

```text
                    CITIZEN
                       |
                       v
             REACT FRONTEND
              (MEMBER 1)
                       |
                       v
              FASTAPI BACKEND
              (MEMBER 1)
                       |
              Task / Event API
                       |
                       v
              AGENT ORCHESTRATOR
                 (MEMBER 2)
                       |
          +------------+------------+
          |            |            |
          v            v            v
       SERVICE       PROFILE      DOCUMENT
      KNOWLEDGE       CLIENT       CLIENT
          |            |            |
          +------------+------------+
                       |
                       v
                  LANGGRAPH
               WORKFLOW ENGINE
                       |
                       v
                BROWSER CLIENT
                 HTTP ADAPTER
                       |
                 REST API v1
                       |
                       v
                BROWSER WORKER
                 (MEMBER 3)
                       |
                       v
             PLAYWRIGHT + CHROMIUM
                       |
                       v
              GOVERNMENT WEBSITE
```

## Component ownership

| Component                 | Owner    | Responsibility                                                    |
| ------------------------- | -------- | ----------------------------------------------------------------- |
| React frontend            | Member 1 | User interface and embedded browser viewer                        |
| FastAPI backend           | Member 1 | Authentication, database, profiles, documents, tasks, approvals   |
| Agent orchestrator        | Member 2 | Reasoning, planning, workflow, eligibility, document intelligence |
| Knowledge retrieval       | Member 2 | Official-source retrieval and RAG                                 |
| Eligibility engine        | Member 2 | Deterministic rule evaluation                                     |
| Browser HTTP client       | Member 2 | Communicate with Member 3                                         |
| Browser worker API        | Member 3 | Browser sessions and action endpoints                             |
| Playwright controller     | Member 3 | Actual page interaction                                           |
| Browser observation       | Member 3 | Return structured page information                                |
| Browser screenshot stream | Member 3 | Send the browser view to the frontend                             |

## Strict ownership rule

Member 2 should never import a Playwright class from Member 3.

Member 3 should never implement eligibility, document reasoning, service selection, or task planning.

Member 1 should not implement the agent's reasoning.

The only way these systems communicate should be through agreed API contracts.

# 3. Technology stack

Use the following stack for the first implementation.

| Area                  | Technology                   |
| --------------------- | ---------------------------- |
| Main language         | Python                       |
| Agent orchestration   | LangGraph                    |
| LLM integration       | LangChain                    |
| Structured validation | Pydantic                     |
| Backend               | FastAPI                      |
| Database              | PostgreSQL                   |
| ORM                   | SQLAlchemy                   |
| PDF text extraction   | PyMuPDF                      |
| OCR                   | PaddleOCR, later phase       |
| Vector database       | FAISS for prototype          |
| Embeddings            | Configurable embedding model |
| Browser automation    | Playwright                   |
| Browser execution     | Chromium                     |
| Frontend              | React, TypeScript, Tailwind  |
| Checkpointing         | LangGraph checkpointer       |
| API communication     | REST with JSON               |
| Tests                 | Pytest                       |
| Local development     | Docker Compose               |
| Experimentation       | Jupyter Notebook             |

Keep the LLM provider, embedding model, database URL, and external service URLs configurable.

Do not hardcode API keys, provider names, model names, or production URLs inside application code.

# 4. Repository structure

Start with a monorepo so that the three members can work against shared contracts.

```text
civicflow/
│
├── AGENTS.md
├── README.md
├── .env.example
├── docker-compose.yml
├── pyproject.toml
│
├── docs/
│   ├── IMPLEMENTATION_PLAN.md
│   ├── ARCHITECTURE.md
│   ├── API_CONTRACTS.md
│   ├── BROWSER_API_V1.md
│   ├── TEAM_RESPONSIBILITIES.md
│   └── PROGRESS.md
│
├── contracts/
│   └── browser-api-v1.yaml
│
├── notebooks/
│   └── CivicFlow_Agent_Development.ipynb
│
├── packages/
│   └── civicflow_contracts/
│       ├── __init__.py
│       ├── browser.py
│       ├── agent_events.py
│       └── task.py
│
├── backend/
│   └── app/
│       ├── main.py
│       │
│       ├── agent/
│       │   ├── graph.py
│       │   ├── state.py
│       │   ├── config.py
│       │   │
│       │   ├── schemas/
│       │   │   ├── intent.py
│       │   │   ├── service.py
│       │   │   ├── requirements.py
│       │   │   ├── eligibility.py
│       │   │   ├── documents.py
│       │   │   ├── planner.py
│       │   │   └── browser.py
│       │   │
│       │   ├── nodes/
│       │   │   ├── intent.py
│       │   │   ├── service_resolver.py
│       │   │   ├── official_sources.py
│       │   │   ├── rag.py
│       │   │   ├── requirements.py
│       │   │   ├── profile.py
│       │   │   ├── eligibility.py
│       │   │   ├── documents.py
│       │   │   ├── missing_info.py
│       │   │   ├── planner.py
│       │   │   ├── browser_observer.py
│       │   │   ├── action_decision.py
│       │   │   ├── verification.py
│       │   │   ├── approval.py
│       │   │   └── summary.py
│       │   │
│       │   ├── services/
│       │   │   ├── eligibility_engine.py
│       │   │   ├── document_extractor.py
│       │   │   ├── requirement_extractor.py
│       │   │   ├── task_planner.py
│       │   │   └── source_validator.py
│       │   │
│       │   ├── clients/
│       │   │   ├── profile_client.py
│       │   │   ├── document_client.py
│       │   │   ├── browser_client.py
│       │   │   └── event_client.py
│       │   │
│       │   ├── prompts/
│       │   │   ├── intent_prompt.py
│       │   │   ├── requirements_prompt.py
│       │   │   ├── planner_prompt.py
│       │   │   └── action_prompt.py
│       │   │
│       │   └── mocks/
│       │       ├── mock_browser.py
│       │       ├── mock_profile.py
│       │       └── mock_documents.py
│       │
│       ├── api/
│       ├── models/
│       └── tests/
│
├── browser_worker/
│   └── app/
│       ├── main.py
│       ├── config.py
│       ├── api/
│       │   ├── sessions.py
│       │   ├── observations.py
│       │   ├── actions.py
│       │   ├── user_input.py
│       │   └── screenshots.py
│       │
│       ├── services/
│       │   ├── session_manager.py
│       │   ├── playwright_controller.py
│       │   ├── observer.py
│       │   ├── element_registry.py
│       │   ├── action_executor.py
│       │   ├── policy_guard.py
│       │   └── screenshot_service.py
│       │
│       └── tests/
│
└── tests/
    ├── contract/
    ├── integration/
    └── end_to_end/
```

## Notebook-first development rule

Use `CivicFlow_Agent_Development.ipynb` for experiments.

However, keep reusable functions in Python modules and import them into the notebook.

Do not put the entire production system in one notebook. Debugging a giant notebook is a special kind of punishment.

The notebook should contain these sections:

1. Environment setup.
2. Pydantic schemas.
3. Intent extraction.
4. Service resolver.
5. PDF extraction.
6. RAG pipeline.
7. Requirements extraction.
8. Eligibility evaluation.
9. Document extraction.
10. Task planning.
11. Mock browser integration.
12. LangGraph construction.
13. Human approval and resume.
14. End-to-end tests.

# 5. The most important part: deterministic Member 3 integration

This section is the integration contract. Both Member 2 and Member 3 must follow it.

## 5.1 Browser Worker principle

Member 3 owns a standalone service called `Browser Worker`.

Member 2 communicates with it using HTTP requests and JSON responses.

```text
MEMBER 2                          MEMBER 3

Browser Client
     |
     | POST /sessions
     |---------------------------->
     |                             Create browser session
     |
     | GET /observation
     |---------------------------->
     |                             Inspect current page
     |
     |<----------------------------
     | JSON observation
     |
     | POST /actions
     |---------------------------->
     |                             Validate action
     |                             Execute through Playwright
     |
     |<----------------------------
     | JSON execution result
     |
     | GET /observation
     |---------------------------->
     |                             Inspect result
     |
     |<----------------------------
     | Updated JSON observation
```

Member 2 should know nothing about how Member 3 finds elements, manages locators, or executes Playwright calls.

## 5.2 Fixed API endpoints

Use `/api/v1` as the initial API version.

| Method | Endpoint                             | Purpose                                |
| ------ | ------------------------------------ | -------------------------------------- |
| POST   | `/api/v1/sessions`                   | Create a browser session               |
| GET    | `/api/v1/sessions/{id}`              | Get session status                     |
| GET    | `/api/v1/sessions/{id}/observation`  | Observe current webpage                |
| POST   | `/api/v1/sessions/{id}/actions`      | Execute one agent action               |
| POST   | `/api/v1/sessions/{id}/control-mode` | Switch agent/user/paused mode          |
| POST   | `/api/v1/sessions/{id}/user-input`   | Receive citizen's manual browser input |
| GET    | `/api/v1/sessions/{id}/screenshot`   | Return current screenshot              |
| GET    | `/api/v1/sessions/{id}/stream`       | Stream browser screenshots             |
| DELETE | `/api/v1/sessions/{id}`              | Close browser session                  |
| GET    | `/healthz`                           | Health check                           |

Every endpoint must have a documented request, response, and error schema.

Do not invent additional endpoints independently without updating the shared contract.

## 5.3 Browser session creation

Request:

```json
{
  "task_id": "task_123",
  "start_url": "https://example.gov.in",
  "viewport": {
    "width": 1280,
    "height": 800
  }
}
```

Response:

```json
{
  "session_id": "browser_123",
  "status": "running",
  "control_mode": "agent",
  "created_at": "2026-10-31T10:00:00Z",
  "viewport": {
    "width": 1280,
    "height": 800
  }
}
```

The session ID is owned by Member 3.

Member 2 stores the ID in its graph state and uses it for subsequent requests.

## 5.4 Page observation schema

This is the most important response from Member 3.

Request:

```http
GET /api/v1/sessions/browser_123/observation
```

Response:

```json
{
  "session_id": "browser_123",
  "observation_id": "obs_001",
  "sequence": 1,
  "page": {
    "url": "https://example.gov.in",
    "title": "Government Service Portal",
    "state": "ready"
  },
  "elements": [
    {
      "element_id": "el_001",
      "role": "link",
      "label": "New Application",
      "input_type": null,
      "placeholder": null,
      "visible": true,
      "enabled": true,
      "required": false,
      "sensitive": false
    },
    {
      "element_id": "el_002",
      "role": "textbox",
      "label": "Applicant Name",
      "input_type": "text",
      "placeholder": "Enter full name",
      "visible": true,
      "enabled": true,
      "required": true,
      "sensitive": false
    },
    {
      "element_id": "el_003",
      "role": "textbox",
      "label": "Mobile Number",
      "input_type": "tel",
      "placeholder": "Enter mobile number",
      "visible": true,
      "enabled": true,
      "required": true,
      "sensitive": false
    }
  ],
  "screenshot_url": "/api/v1/sessions/browser_123/screenshot"
}
```

### Observation rules

Member 3 must:

- Return the current page URL and title.
- Return an explicit page state.
- Return interactive elements in a structured format.
- Return labels and roles.
- Identify disabled and invisible controls.
- Identify sensitive inputs.
- Include an observation ID and increasing sequence number.
- Return screenshot access information.
- Never invent elements.
- Never return element IDs that do not exist in the current observation.

Use these page states:

```text
ready
loading
authentication_required
captcha_detected
unexpected_error
closed
```

Use these element roles:

```text
link
button
textbox
combobox
checkbox
radio
file_upload
option
other
```

Element IDs are valid only for the observation that generated them. They must not be reused as permanent IDs across unrelated observations.

Member 3 internally maps each element ID to the actual Playwright locator.

Member 2 only uses the element ID.

## 5.5 Agent action schema

Member 2 proposes one action at a time.

Request:

```json
{
  "action_id": "act_001",
  "observation_id": "obs_001",
  "action": {
    "type": "fill",
    "element_id": "el_002",
    "value": "Example Applicant"
  },
  "expected_result": "Applicant name field is filled"
}
```

Response:

```json
{
  "action_id": "act_001",
  "status": "succeeded",
  "message": "Field filled successfully",
  "before_observation_id": "obs_001",
  "after_observation_id": "obs_002",
  "page_url": "https://example.gov.in"
}
```

### Supported agent actions

Use only these action types:

```text
navigate
click
fill
select_option
check
uncheck
press_key
scroll
go_back
reload
upload_file
```

`upload_file` accepts a short-lived, backend-generated file reference or download URL, not arbitrary local paths.

### Actions that must not be agent-executable

```text
submit_final_application
make_payment
enter_otp
enter_password
accept_final_declaration
solve_captcha
execute_arbitrary_javascript
```

The agent must not bypass human control over authentication, payment, final declarations, or final submission.

The user can interact with these through the browser's manual-control mode.

## 5.6 Action result statuses

Every action must return exactly one of these statuses:

```text
succeeded
failed
target_not_found
stale_observation
policy_blocked
user_intervention_required
timed_out
```

Do not return vague strings such as `"something went wrong"` as the only result.

A failed action must include a useful, non-sensitive error message.

## 5.7 Prevent stale element actions

Suppose Member 2 observes a page and receives:

```text
observation_id = obs_001
```

It then proposes a click on:

```text
element_id = el_002
```

Before Member 3 executes the action, the page changes.

Member 3 must reject that action with:

```json
{
  "action_id": "act_001",
  "status": "stale_observation",
  "message": "The page changed. Request a fresh observation.",
  "before_observation_id": "obs_001",
  "after_observation_id": "obs_002"
}
```

Member 2 must observe the page again and make a new decision.

This prevents the agent from clicking an element that no longer refers to the same control.

## 5.8 Idempotency

Every action must have a unique `action_id`.

If Member 2 sends the same action twice due to a timeout or network retry, Member 3 must not perform the action twice.

Member 3 should return the stored result for an already processed action ID.

This is especially important for actions that could create duplicate applications or trigger irreversible effects.

## 5.9 Manual user control

The browser must support two independent control modes.

```text
agent
user
paused
```

Rules:

- In `agent` mode, only validated agent actions are accepted.
- In `user` mode, only user-input events are accepted.
- In `paused` mode, no interaction is accepted.
- A session must not receive agent and user inputs simultaneously.

When login, OTP, CAPTCHA, or a legally significant action is required:

1. Member 2 pauses agent execution.
2. Member 2 changes the control mode to `user`.
3. Member 1 displays the browser session.
4. The citizen interacts with the actual browser.
5. Member 1 informs Member 2 when the citizen finishes.
6. Member 2 requests a new observation.
7. Member 2 verifies the new state before continuing.

### Manual user input contract

Request:

```json
{
  "event_id": "ui_001",
  "type": "pointer_click",
  "x_normalized": 0.42,
  "y_normalized": 0.35
}
```

Other supported event types:

```text
pointer_click
key_press
text_input
scroll
```

For `text_input`, the text is forwarded to the browser session and must not be persisted or recorded in ordinary logs.

Coordinates are normalized between 0 and 1 relative to the browser viewport. This avoids confusion when the React viewer is resized.

Member 3 must reject user-input events when the session is not in `user` mode.

## 5.10 Embedded browser display

Member 3 provides:

```http
GET /api/v1/sessions/{id}/screenshot
```

and:

```http
GET /api/v1/sessions/{id}/stream
```

The screenshot endpoint returns the latest JPEG image.

The stream endpoint returns browser screenshots using a documented streaming format such as MJPEG.

Member 1 renders the stream inside the CivicFlow interface.

The browser viewer must preserve the browser viewport's aspect ratio and map user clicks to normalized coordinates.

The initial implementation can use MJPEG. A more advanced WebSocket-based streaming implementation can be added later without changing the agent's action API.

## 5.11 Security rules for Member 3

- Run each citizen's session in an isolated browser context.
- Never expose browser session credentials to Member 2.
- Never return passwords or OTP values in observations.
- Mark password and OTP fields as sensitive.
- Reject agent attempts to fill sensitive authentication fields.
- Do not log form values, authentication payloads, or file URLs.
- Restrict navigation to approved destinations and validate URLs.
- Do not expose arbitrary JavaScript execution through the browser API.
- Enforce action idempotency.
- Authenticate service-to-service requests.
- Destroy session data according to a defined retention policy.

# 6. Shared contracts and integration rules

Create a shared package:

```text
packages/civicflow_contracts/
```

Both Member 2 and Member 3 import the same Python Pydantic models for browser requests and responses.

The OpenAPI definition in `contracts/browser-api-v1.yaml` is the documented external API contract.

Member 1 should generate or maintain TypeScript types from this contract instead of independently guessing response structures.

The contract must include:

- Request schemas.
- Response schemas.
- Enum values.
- Required and optional fields.
- Error responses.
- Authentication requirements.
- API version.
- Example requests and responses.

Add automated contract tests.

A Member 3 endpoint is not integration-ready simply because it works on their laptop. It is ready when the shared contract tests pass.

## Browser adapter owned by Member 2

Implement:

```python
class BrowserClient:
    async def create_session(self, request):
        ...

    async def get_session(self, session_id):
        ...

    async def observe(self, session_id):
        ...

    async def execute_action(self, session_id, action):
        ...

    async def change_control_mode(self, session_id, mode):
        ...

    async def send_user_input(self, session_id, event):
        ...

    async def close_session(self, session_id):
        ...
```

Use an HTTP client such as `httpx`.

The browser client must:

- Validate responses against shared schemas.
- Handle connection failures and timeouts.
- Preserve action IDs during safe retries.
- Never perform hidden retries of non-idempotent actions.
- Convert API failures into typed errors.
- Keep the browser service URL in configuration.

Create a `MockBrowserClient` with exactly the same interface.

This is what allows Member 2 to develop independently of Member 3.

# 7. Member 2: complete AI-agent implementation

## 7.1 Shared agent state

Use one typed state model for the LangGraph workflow.

Suggested fields:

```python
class CivicFlowState(TypedDict, total=False):
    task_id: str
    user_id: str

    user_request: str
    intent: dict
    jurisdiction: str

    service_candidates: list
    selected_service: dict

    official_sources: list
    retrieved_documents: list
    requirements: dict

    applicant_profile: dict
    applicant_documents: list
    extracted_document_data: dict

    eligibility_result: dict
    missing_information: list
    validation_errors: list

    execution_plan: list
    current_step: int

    browser_session_id: str
    browser_observation: dict
    proposed_action: dict
    browser_result: dict
    action_history: list

    approval_request: dict
    approval_status: str

    task_status: str
    retry_count: int
    errors: list
    events: list

    final_summary: str
```

Use explicit enums for task status, approval status, and browser outcomes.

Never store raw PDFs in graph state. Store document IDs and references.

Never store passwords, OTPs, or authentication tokens in graph state.

## 7.2 Intent understanding

Create an `intent_node`.

Input:

```text
I want to apply for a domicile certificate in Maharashtra.
```

Expected structured output:

```json
{
  "intent": "apply_for_service",
  "service_category": "certificate",
  "service_name": "domicile_certificate",
  "jurisdiction": "Maharashtra",
  "goal": "complete_application",
  "requires_browser": true,
  "missing_information": []
}
```

Supported intents:

```text
find_service
get_information
check_eligibility
apply_for_service
track_application
```

LLM output must be validated through Pydantic.

Do not allow the graph to route based on unvalidated free-form text.

## 7.3 Service resolver

Create a data-driven service registry.

Example:

```json
{
  "service_id": "maharashtra_domicile",
  "name": "Domicile Certificate",
  "category": "certificate",
  "jurisdiction": "Maharashtra",
  "department": "configured_department",
  "official_portal": null,
  "official_sources": [],
  "workflow_config": {}
}
```

The example is a development fixture, not a verified government-service record.

Each service record should eventually contain:

- Service name.
- Category.
- Jurisdiction.
- Department.
- Verified official source references.
- Official portal URL.
- Requirements reference.
- Eligibility configuration.
- Application workflow hints.

Do not invent official URLs.

When multiple services match, ask the citizen to select the correct service.

## 7.4 Official-source retrieval

Initially, use manually selected official PDFs and URLs.

Build a source registry with:

```text
source_id
service_id
source_title
source_url
publisher
publication_date
document_type
verification_status
retrieved_at
```

Distinguish official information from unverified information.

If the information cannot be verified, mark it as uncertain.

## 7.5 RAG pipeline

Implement these steps:

```text
Official PDF / HTML
        |
        v
Document extraction
        |
        v
Text cleaning
        |
        v
Chunking
        |
        v
Metadata assignment
        |
        v
Embedding generation
        |
        v
FAISS index
        |
        v
Retrieval
        |
        v
Requirements extraction
```

Each retrieved chunk must preserve:

- Source ID.
- Source URL.
- Page number.
- Document title.
- Text content.

Never provide a citizen with a requirement as an authoritative fact when it has no supporting source.

## 7.6 Requirements extraction

Convert official information into structured requirements.

Example:

```json
{
  "service_id": "maharashtra_domicile",
  "eligibility_rules": [],
  "required_documents": [
    {
      "document_type": "identity_proof",
      "mandatory": true,
      "acceptable_types": [],
      "source_reference": "source_001"
    }
  ],
  "application_steps": [],
  "fees": {
    "amount": null,
    "source_reference": null
  },
  "uncertainties": []
}
```

Do not invent missing fees or document requirements.

Each extracted requirement must include a source reference whenever available.

## 7.7 Profile retrieval

Member 1 provides the profile API.

Member 2 implements a client:

```python
async def get_user_profile(user_id: str) -> dict:
    ...
```

Do not access Member 1's database directly.

Keep user-provided, profile-derived, and document-derived information distinguishable.

## 7.8 Eligibility engine

Do not let an LLM make the final eligibility decision.

Create a deterministic rule evaluator.

Example rule types:

```text
equals
not_equals
greater_than
less_than
greater_than_or_equal
less_than_or_equal
in
not_in
contains
is_present
date_before
date_after
```

Rule example:

```json
{
  "field": "annual_income",
  "operator": "less_than_or_equal",
  "value": 250000,
  "source_reference": "source_001"
}
```

The amount is only an illustrative test value, not a claim about any actual scheme.

Eligibility statuses:

```text
potentially_eligible
not_eligible
insufficient_information
```

If the information is incomplete, do not classify the applicant as ineligible.

Return the failed rules, passed rules, missing fields, and supporting sources.

## 7.9 Document intelligence

Initial implementation:

1. Receive document IDs from Member 1.
2. Obtain document metadata.
3. Extract PDF text using PyMuPDF.
4. Classify document type.
5. Extract relevant fields.
6. Compare extracted fields with the citizen profile.
7. Mark low-confidence fields for human review.

Add OCR for scanned documents in a later stage.

Use confidence scores and source locations for extracted fields.

Do not silently overwrite a citizen's profile with extracted document values.

## 7.10 Missing-information node

Compare:

- Required fields.
- Available profile fields.
- Extracted document fields.
- Requirements for the selected service.

Generate a list of missing items.

Ask only for information that is genuinely missing or uncertain.

Once the user provides it, resume the workflow using the updated state.

## 7.11 Dynamic task planner

Generate execution plans using the actual service requirements and browser observations.

Example:

```json
{
  "service_id": "example_service",
  "steps": [
    {
      "step_id": "step_001",
      "description": "Open official application portal",
      "type": "browser_navigation",
      "status": "pending",
      "requires_human_approval": false
    },
    {
      "step_id": "step_002",
      "description": "Complete applicant information",
      "type": "browser_form",
      "status": "pending",
      "requires_human_approval": false
    }
  ]
}
```

The planner must not assume that every government portal has the same sequence of forms.

Use the real page observations to adapt.

## 7.12 Browser action decision

The LLM can propose an action, but a deterministic validation layer must approve it.

Validation rules:

1. The action type must be in the allowed enum.
2. The target element must exist in the latest observation.
3. The observation ID must match the latest observation.
4. The element must be visible and enabled.
5. The target must not be a sensitive authentication field.
6. The action must not be prohibited.
7. The session must be in agent-control mode.
8. The proposed action must match the current plan step.

Only then call `BrowserClient.execute_action()`.

## 7.13 Verification

After each action:

1. Request a new observation.
2. Compare actual page state against expected result.
3. Mark the step as successful only when evidence supports it.
4. Retry only after inspecting the current page.
5. Ask the citizen for help when the page needs intervention.
6. Stop safely when the portal behaves unexpectedly.

Never assume an action worked merely because the browser API returned a success status.

For potentially irreversible actions, verify whether the side effect already occurred before considering a retry.

## 7.14 Human approval and resume

Use LangGraph interrupts and persistent checkpointing.

Pause when:

- User authentication is required.
- OTP or CAPTCHA intervention is required.
- The citizen must review personal data.
- A legally significant declaration is required.
- Payment is required.
- Final application submission is required.

Approval must refer to a specific action and the exact data being approved.

Do not treat an LLM-generated statement such as "the user approved" as an actual approval.

When the citizen resumes, verify the browser state again before continuing.

# 8. LangGraph workflow

Use a controlled graph, not an unrestricted agent loop.

```text
START
  |
  v
INTENT
  |
  v
SERVICE RESOLVER
  |
  v
OFFICIAL SOURCE RETRIEVAL
  |
  v
RAG RETRIEVAL
  |
  v
REQUIREMENTS EXTRACTION
  |
  v
PROFILE RETRIEVAL
  |
  v
ELIGIBILITY
  |
  v
DOCUMENT ANALYSIS
  |
  v
MISSING INFORMATION CHECK
  |
  +------ Missing information?
  |             |
  |             YES
  |             |
  |             v
  |        ASK CITIZEN
  |             |
  |             v
  |        UPDATE STATE
  |             |
  |             +--------> MISSING INFORMATION CHECK
  |
  NO
  |
  v
TASK PLANNER
  |
  v
CREATE BROWSER SESSION
  |
  v
OBSERVE PAGE
  |
  v
DECIDE ACTION
  |
  v
POLICY VALIDATION
  |
  +------ Human control required?
  |             |
  |             YES
  |             |
  |             v
  |        PAUSE AGENT
  |             |
  |             v
  |        CITIZEN INTERACTION
  |             |
  |             v
  |        RESUME + OBSERVE
  |             |
  |             +--------> OBSERVE PAGE
  |
  NO
  |
  v
EXECUTE ACTION
  |
  v
VERIFY RESULT
  |
  +------ Successful?
  |          |
  |          YES
  |          |
  |          v
  |     MORE STEPS?
  |          |
  |          +---- YES ----> OBSERVE PAGE
  |          |
  |          +---- NO -----> FINAL REVIEW
  |
  +------ Needs retry?
  |          |
  |          +----> RE-OBSERVE / REPLAN
  |
  +------ Unsafe or unexpected?
             |
             v
          STOP SAFELY
             |
             v
         FINAL SUMMARY
             |
             v
            END
```

Use typed status values and conditional routing functions.

Keep graph nodes small and independently testable.

# 9. Member 1 integration contract

Member 2 will depend on these backend capabilities.

```python
async def get_user_profile(user_id: str):
    ...

async def get_user_documents(user_id: str):
    ...

async def get_document_metadata(document_id: str):
    ...

async def create_task_event(task_id: str, event: dict):
    ...

async def request_user_input(task_id: str, question: dict):
    ...

async def request_human_approval(task_id: str, approval: dict):
    ...

async def get_approval_status(approval_id: str):
    ...
```

Agree on the request and response schemas before implementing these clients.

## Agent events

The agent should emit events rather than expecting the frontend to inspect graph state.

Common event structure:

```json
{
  "event_id": "event_001",
  "task_id": "task_123",
  "sequence": 1,
  "type": "service.resolved",
  "timestamp": "2026-10-31T10:00:00Z",
  "payload": {
    "service_id": "example_service"
  }
}
```

Suggested event types:

```text
task.started
intent.extracted
service.resolved
sources.retrieved
requirements.extracted
eligibility.completed
documents.validated
information.required
plan.created
browser.session.created
browser.observation.updated
browser.action.started
browser.action.completed
approval.required
task.paused
task.resumed
task.completed
task.failed
```

Use monotonic sequence numbers to help the frontend process events in order.

# 10. Development phases

Implement the project in the following order.

Do not ask Codex to build the entire product in a single prompt. Implement one phase at a time, run tests, inspect changes, and continue.

## Phase 0: Project foundation

**Goal:** Create the repository structure and agreed technical contracts.

Tasks:

- Create folder structure.
- Add `AGENTS.md`.
- Add `.env.example`.
- Add `README.md`.
- Add the shared contract package.
- Define the browser API v1 contract.
- Create Docker Compose for local services.
- Create initial tests.
- Add `docs/PROGRESS.md`.

Acceptance criteria:

- Project installs successfully.
- Contract package imports successfully.
- Backend starts.
- Browser Worker starts with a health endpoint.
- Tests run successfully.
- No application logic is implemented prematurely.

## Phase 1: Core data models

Implement:

- Intent schemas.
- Service schemas.
- Requirements schemas.
- Eligibility schemas.
- Document schemas.
- Browser schemas.
- Task schemas.
- Event schemas.
- Approval schemas.

Acceptance criteria:

- Pydantic validation works.
- Invalid enums are rejected.
- Shared browser models can be imported by both services.
- Contract tests pass.

## Phase 2: Intent and service resolution

Implement:

- Intent extraction.
- Structured LLM output.
- Service registry.
- Service resolver.
- Ambiguity detection.
- Service selection response.

Acceptance criteria:

- A certificate request is recognized.
- A scholarship request is recognized.
- Different jurisdictions are distinguished.
- Ambiguous service names produce a clarification request.
- Unit tests pass.

## Phase 3: Official-source retrieval and RAG

Implement:

- PDF ingestion.
- HTML ingestion where needed.
- Text cleaning.
- Chunking.
- Metadata.
- Embeddings.
- FAISS retrieval.
- Source attribution.

Initially use manually selected official documents.

Acceptance criteria:

- PDF text is extracted.
- Retrieved chunks contain page references.
- Source URLs are preserved.
- Retrieval results are testable.
- Unsupported claims are not presented as verified information.

## Phase 4: Requirements extraction

Implement:

- Requirements extraction prompt.
- Structured output validation.
- Required-document extraction.
- Eligibility-rule extraction.
- Application-step extraction.
- Source provenance.

Acceptance criteria:

- The model extracts structured fields.
- Invalid output is rejected or marked uncertain.
- Every supported rule retains its source reference.
- Missing information is not fabricated.

## Phase 5: Eligibility engine

Implement:

- Rule evaluator.
- Field lookup.
- Type checking.
- Missing-field detection.
- Eligibility result.
- Explanation generation.

Acceptance criteria:

- Deterministic rules return reproducible results.
- Missing information returns `insufficient_information`.
- Rule failures are traceable.
- Tests cover each supported operator.

## Phase 6: Document intelligence

Implement:

- PDF metadata extraction.
- PDF text extraction.
- Document classification.
- Field extraction.
- Profile comparison.
- Confidence tracking.
- Human review for uncertain fields.

Acceptance criteria:

- A test PDF is processed.
- Extracted values are structured.
- Uncertain values are flagged.
- The source location for extracted values is preserved.

## Phase 7: Dynamic task planner

Implement:

- Planner input schema.
- Planner output schema.
- Step generation.
- Dependency management.
- Human intervention markers.
- Step status tracking.

Acceptance criteria:

- Plans are generated from service requirements.
- Plans are not hardcoded to scholarship.
- Plan steps have stable IDs.
- Human-control steps are explicit.

## Phase 8: Browser mock and API adapter

**This phase must be completed before the real browser service is integrated.**

Implement:

- `BrowserClient` interface.
- `MockBrowserClient`.
- Browser action validation.
- Observation validation.
- Stale-observation tests.
- Idempotency tests.
- Action error handling.

The mock should simulate:

- Opening a portal.
- Observing a page.
- Clicking a link.
- Filling a field.
- Receiving a new observation.
- Detecting authentication requirements.
- Pausing for user intervention.
- Resuming execution.

Acceptance criteria:

- Member 2 can complete the simulated browser workflow.
- No Playwright dependency exists in the Member 2 agent code.
- Mock and live browser clients have the same interface.
- All browser contract tests pass.

## Phase 9: Real Browser Worker integration

Member 3 implements the agreed Browser Worker API.

Member 2 only needs to:

1. Set `BROWSER_WORKER_URL`.
2. Configure the browser client.
3. Replace `MockBrowserClient` with `BrowserClient`.
4. Run integration tests.
5. Validate all API responses.

Acceptance criteria:

- A browser session can be created.
- An observation is returned.
- A permitted action is executed.
- An updated observation is returned.
- Stale actions are rejected.
- User control works.
- Browser screenshots are available.
- Closing a session cleans up its resources.

## Phase 10: Complete LangGraph workflow

Connect all nodes.

Implement:

- State transitions.
- Conditional routing.
- Checkpointing.
- Human interrupts.
- Resume.
- Error handling.
- Event emission.
- Final summary.

Acceptance criteria:

- A complete workflow runs using mock services.
- Missing information causes a pause.
- Resuming restores the expected task.
- Browser errors are handled.
- Approval status is checked independently.
- Tests cover the major graph paths.

## Phase 11: Member 1 backend and frontend integration

Implement:

- Agent API integration.
- Task event delivery.
- User input handling.
- Approval request handling.
- Browser viewer.
- Pause and resume UI.
- Execution status display.

Acceptance criteria:

- User can start a task.
- User can view agent activity.
- User can view the browser session.
- User can take manual control.
- User can resume the task.
- User can see the verified final status.

## Phase 12: Security and testing

Test:

- Cross-user browser isolation.
- Unauthorized API calls.
- Sensitive field handling.
- Document access permissions.
- Action idempotency.
- Stale observation handling.
- Session cleanup.
- Network failure.
- Browser crash.
- Workflow checkpoint recovery.
- Duplicate task events.

Do not run real government submissions as automated tests.

Use local mock pages and test portals for browser integration.

## Phase 13: Demonstration

Demonstrate a citizen asking to apply for a Maharashtra scholarship.

Show:

1. Intent recognition.
2. Service resolution.
3. Official requirements retrieval.
4. Eligibility assessment.
5. Document analysis.
6. Missing-information detection.
7. Execution-plan creation.
8. Browser session opening.
9. Page observation.
10. Controlled form interaction.
11. Human intervention.
12. Resume and verification.
13. Final task summary.

Then test a second structurally different service, such as a certificate workflow.

The second workflow is important. It demonstrates whether CivicFlow is actually general-purpose rather than a scholarship automation script wearing a different hat.

# 11. Exact task division

## Member 1

Responsible for:

- React application.
- FastAPI application.
- PostgreSQL.
- Authentication.
- Citizen profile API.
- Document upload and storage.
- Task lifecycle.
- Approval APIs.
- Agent event persistence.
- Browser viewer.
- Deployment.

Not responsible for:

- LLM reasoning.
- Eligibility engine.
- Agent planning.
- Playwright implementation.

## Member 2

Responsible for:

- Intent understanding.
- Service registry and resolution.
- Official-source retrieval.
- RAG.
- Requirements extraction.
- Eligibility engine.
- Document intelligence.
- Missing-information detection.
- Dynamic task planner.
- LangGraph.
- Browser decision-making.
- Browser API client.
- Verification.
- Human approval orchestration.
- Final summary.

Not responsible for:

- React browser viewer.
- Chromium lifecycle.
- Playwright internals.
- DOM locator implementation.
- Browser screenshot rendering.

## Member 3

Responsible for:

- Browser Worker API.
- Playwright and Chromium.
- Browser session manager.
- Page observation.
- Element registry.
- Action executor.
- Action policy enforcement.
- Screenshots.
- Screenshot streaming.
- User-control input relay.
- Session isolation.
- Browser integration tests.

Not responsible for:

- Service selection.
- RAG.
- Eligibility.
- Document extraction.
- Agent planning.
- LangGraph.
- Citizen profile management.

# 12. Exact Codex working procedure

## Step 1: Create the project instructions

Create a root-level `AGENTS.md` containing the following rules:

```markdown
# CivicFlow Engineering Instructions

## General
- Read docs/IMPLEMENTATION_PLAN.md before implementing features.
- Follow the established architecture and ownership boundaries.
- Work one phase at a time.
- Do not implement future phases prematurely.
- Keep reusable logic in Python modules.
- Use notebooks only for experimentation.
- Use Pydantic for structured contracts.
- Write tests for every meaningful feature.

## Architecture
- The agent must not import Playwright internals.
- The browser worker must remain a separate service.
- The browser API is the only integration boundary between Member 2 and Member 3.
- Use shared contracts.
- Do not create undocumented request or response formats.

## Safety
- Never automate OTP entry through the agent.
- Never automate payment or final application submission.
- Never execute arbitrary JavaScript from an LLM-generated action.
- Do not log credentials, OTPs, or sensitive form values.
- Do not fabricate official government URLs or requirements.
- Do not claim an action succeeded without verification.

## Code quality
- Use type hints.
- Handle expected API and validation errors.
- Keep functions small.
- Keep nodes independently testable.
- Avoid unnecessary dependencies.
- Do not silently change existing contracts.

## Completion
- Run the relevant tests after each phase.
- Report changed files.
- Report commands executed.
- Report test results.
- Update docs/PROGRESS.md.
- List incomplete items and known limitations.
```

Codex supports repository-specific guidance through `AGENTS.md`, making it useful for preserving these project rules across implementation sessions. See the [Codex AGENTS.md documentation](https://learn.chatgpt.com/docs/agent-configuration/agents-md).

## Step 2: Give Codex the implementation plan

Save this document as:

```text
docs/IMPLEMENTATION_PLAN.md
```

Then give Codex this initial prompt:

```text
You are the lead engineer implementing CivicFlow.

Read:
- AGENTS.md
- docs/IMPLEMENTATION_PLAN.md
- docs/ARCHITECTURE.md
- docs/API_CONTRACTS.md

First inspect the repository.

Implement Phase 0 only.

Do not implement the AI agent, real browser automation,
or government-service workflows yet.

Create the repository structure, shared contracts,
configuration, documentation, test setup, and health
endpoints as described in the implementation plan.

Preserve all ownership boundaries.

Before finishing:
1. Run the tests.
2. Report all created files.
3. Report all commands executed.
4. Report test results.
5. Update docs/PROGRESS.md.
6. Identify any blockers.
```

## Step 3: Implement each phase separately

After Phase 0 passes, use prompts like this:

```text
Read AGENTS.md and docs/IMPLEMENTATION_PLAN.md.

Implement Phase 1 only.

Do not modify completed functionality unless required.

Follow the shared schemas and naming conventions.

Write unit tests and run them.

Do not move to Phase 2 automatically.

At the end, report:
- Implemented functionality
- Files changed
- Tests added
- Test results
- Known limitations

Update docs/PROGRESS.md.
```

Change the phase number for each subsequent implementation.

## Step 4: Make Codex integrate Member 3's implementation

Once both sides are ready:

```text
Integrate the real Browser Worker with Member 2's agent.

Read the shared browser contract and inspect both services.

Do not change the API contract to accommodate an implementation
detail without identifying the compatibility problem first.

Replace MockBrowserClient with BrowserClient through
configuration and dependency injection.

Run contract tests and browser integration tests.

Verify:
- Session creation
- Page observation
- Element ID validation
- Action execution
- Action idempotency
- Stale observation handling
- Manual user control
- Screenshot retrieval
- Session cleanup

Do not modify LangGraph business logic unless necessary.

Report every failure and do not mark the integration complete
until the tests pass.
```

## Step 5: Review instead of blindly accepting changes

After each phase:

1. Inspect the changed files.
2. Run the tests yourself.
3. Review any new dependencies.
4. Verify the interfaces have not drifted.
5. Check that Codex has not implemented another member's responsibilities.
6. Commit the completed phase.

Do not ask Codex to rewrite the entire repository when one module fails. Give it the specific test failure and request a targeted fix.

# 13. First milestone and realistic scope control

Do not try to finish every advanced feature before the first demo.

Your first meaningful milestone should be:

**Citizen request → service resolution → official-source retrieval → requirements extraction → eligibility assessment → missing-information response.**

This proves the reasoning and knowledge components.

Your second milestone should be:

**Task plan → mocked browser execution → observation → action decision → verification.**

This proves that Member 2 and Member 3 can integrate.

Your third milestone should be:

**Real browser session → embedded viewer → user intervention → resume → verified task outcome.**

This proves the complete system.

# 14. Final project acceptance criteria

CivicFlow is ready for its first full demonstration when all of the following are true:

- [x] Citizen can start a task using natural language.
- [ ] Agent identifies the intended service.
- [ ] Jurisdiction is handled.
- [ ] Official sources are preserved.
- [ ] Requirements are extracted into structured data.
- [ ] Eligibility is evaluated deterministically.
- [ ] Missing information is identified.
- [ ] Documents are processed and validated.
- [ ] Dynamic execution plans are generated.
- [ ] Mock browser tests pass.
- [ ] Real Browser Worker integration passes.
- [ ] Browser page observations are structured.
- [ ] Agent actions are validated before execution.
- [ ] Stale observations are rejected.
- [ ] Duplicate actions are prevented.
- [ ] Browser sessions are isolated.
- [ ] The citizen can take manual control.
- [ ] Human approval is enforced for sensitive actions.
- [ ] Agent execution can resume.
- [ ] Browser actions are verified.
- [ ] Task events reach the frontend.
- [ ] Final summaries reflect actual outcomes.
- [ ] A second service works without rewriting the core graph.

---

# 15. Non-negotiable engineering decisions

1. **No unrestricted browser agent.** The LLM proposes actions; deterministic code validates them.
2. **No direct Playwright dependency in Member 2.** Browser communication happens through BrowserClient.
3. **No undocumented Member 3 API.** Shared contracts are mandatory.
4. **No hardcoded scholarship workflow.** Service-specific requirements drive the plan.
5. **No LLM-only eligibility decisions.** Use deterministic Python rule evaluation.
6. **No fabricated official information.** Preserve provenance and uncertainty.
7. **No blind browser retries.** Observe and verify before retrying.
8. **No automated final submission, payment, OTP entry, or legal declaration.** Keep the citizen in control.
9. **No all-at-once Codex implementation.** Implement, test, review, and commit each phase.
10. **No dependency on another member's internal implementation.** Depend only on documented interfaces.

**The target is not a chatbot that fills a form. The target is a controlled, resumable workflow system that understands different public services, prepares citizens' information, interacts with real portals, and verifies what actually happened.**
