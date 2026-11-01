# Free deployment

The repository includes a no-Docker Render Blueprint in `render.yaml`. It defines native Python/Node web services for the Core API, AI Agent, Chromium Browser Agent, and Next.js frontend. Render wires public HTTPS service URLs and the browser token between services. To provision it, create a Render account and start a Blueprint deployment for this GitHub repository. Render will ask for `GROQ_API_KEY`; enter it in Render's secret prompt. The key is not stored in Git or the Blueprint.

## Free-tier behavior

This is a hobby/demo deployment, not a reliable production host. Render's free web instances use 512 MB RAM, spin down after 15 minutes of inactivity, take about a minute to wake, and share a 750 free-instance-hour monthly workspace allowance. Free service filesystems are ephemeral. Core API applications and Browser Agent sessions are in memory, so restarts or idle spin-down lose them. Chromium may exceed the free Browser Agent's memory limit; smoke-test the Blueprint after Render provisions the services.

To fit the free AI service memory budget, its Blueprint sets `EMBEDDING_PROVIDER=lexical`. Local installs still default to BGE-M3; the hosted demo uses lexical fallback retrieval and Groq chat. Change to BGE only on a host with enough RAM and a prepared model cache.

## Service wiring

- Core API: demo mode, in-memory records, AI and Browser Agent public URLs, generated JWT and browser tokens.
- AI Agent: `LLM_PROVIDER=groq`, `GROQ_MODEL=openai/gpt-oss-20b`, and secret `GROQ_API_KEY`.
- Browser Agent: live headless Playwright/Chromium, with its stream URL returned to the browser UI.
- Frontend: Next.js web service, configured at runtime with `CORE_API_URL`.

`BROWSER_AGENT_URL` is used by backend services. `BROWSER_AGENT_PUBLIC_URL` is returned to the user's browser for WebSocket streaming. No secret is exposed through a frontend `NEXT_PUBLIC_*` variable.

## Vercel

Vercel Hobby can host the frontend, but it cannot act as CivicFlow's WebSocket server, and it does not host the long-running Core API, AI Agent, or Chromium Browser Agent. Use it only if those services are deployed elsewhere and configure the frontend's `CORE_API_URL` accordingly.

## Groq check

The workspace's Groq key was checked against Groq's model list and a minimal JSON chat completion. The key is ignored locally and must be entered in the hosting provider's secret settings; never commit `.env`.
