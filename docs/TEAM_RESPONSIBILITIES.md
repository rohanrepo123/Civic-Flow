# Team Responsibilities

| Member | Owns | Does not own |
| --- | --- | --- |
| 1 | React frontend, FastAPI backend, database, authentication, profiles, documents, task/approval APIs, events, browser viewer | Agent reasoning or Playwright internals |
| 2 | Agent orchestration, retrieval, eligibility, document analysis, planning, browser HTTP client, verification | Browser lifecycle, DOM locators, frontend |
| 3 | Browser Worker API, Playwright/Chromium, sessions, observation, action policy, screenshots, user control | Service selection, RAG, eligibility, planning |

Teams integrate through documented HTTP/JSON contracts and shared Pydantic models.
