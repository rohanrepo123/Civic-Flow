# Deployment notes

## Source publication

Push the source to the configured GitHub repository. Keep `.env`, `.env.*` other than `.env.example`, API keys, browser tokens, and production secrets out of Git. Set the keys in each hosting provider's private environment-variable settings.

## Vercel frontend

Vercel can run the Next.js frontend in `frontend_member1`. Use Node.js 22, the `pnpm-lock.yaml` lockfile, and `pnpm build`. Set `CORE_API_URL` to a public HTTPS Core API endpoint. The frontend's `/api/core/*` route forwards to that API.

The frontend alone is not the complete CivicFlow deployment. The Core API, AI Agent, and Browser Agent are separate long-running services. The Browser Agent needs Playwright with Chromium and a public WebSocket endpoint. Set the following backend variables:

- Core API: `AI_AGENT_URL`, `BROWSER_AGENT_URL`, `BROWSER_AGENT_PUBLIC_URL`, `BROWSER_AGENT_API_TOKEN`, and `CORS_ORIGINS`.
- AI Agent: `LLM_PROVIDER=groq`, `GROQ_API_KEY`, and `GROQ_MODEL=openai/gpt-oss-20b`.
- Browser Agent: `BROWSER_AGENT_API_TOKEN`, live Playwright mode, and the configured safe portal policy.

`BROWSER_AGENT_URL` is the private service-to-service address. `BROWSER_AGENT_PUBLIC_URL` is the HTTPS browser-service address returned to the user's browser for WebSocket streaming. Do not put private service URLs or secrets in frontend `NEXT_PUBLIC_*` variables.

## Current production limitation

The Core API application records and Browser Agent sessions are currently held in memory. A process restart loses them. The app can be demonstrated on hosted services, but it is not ready for persistent citizen accounts or durable applications until these stores are backed by production persistence. Vercel cannot host the persistent Chromium worker as a standard Next.js function; deploy that worker to a long-running host that supports Chromium and WebSockets.

## Groq provider

The workspace's Groq key was checked against Groq's model list and a minimal JSON chat completion. Do not include that key in the repository. Set it as `GROQ_API_KEY` in the AI Agent service's environment, and set `LLM_PROVIDER=groq`; `GROQ_MODEL` defaults to `openai/gpt-oss-20b`.
