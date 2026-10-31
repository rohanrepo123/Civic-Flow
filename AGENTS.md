# CivicFlow Engineering Instructions

## General
- Read `docs/IMPLEMENTATION_PLAN.md` before implementing features.
- Follow the established architecture and ownership boundaries.
- Work one phase at a time; do not implement future phases prematurely.
- Keep reusable logic in Python modules and use notebooks only for experiments.
- Use Pydantic for structured contracts.

## Architecture
- The agent must not import Playwright internals.
- The browser worker remains a separate service.
- The browser API is the integration boundary between the agent and browser worker.
- Use shared contracts and do not create undocumented request or response formats.

## Safety
- Never automate OTP entry, payment, final application submission, or legal declarations.
- Never execute arbitrary JavaScript from an LLM-generated action.
- Do not log credentials, OTPs, or sensitive form values.
- Do not fabricate official government URLs or requirements.
- Do not claim an action succeeded without verification.

## Code quality
- Use type hints, handle expected errors, and keep functions small.
- Keep workflow nodes independently testable.
- Avoid unnecessary dependencies and silent contract changes.

## Completion
- Run relevant checks after each phase.
- Report changed files, commands, results, blockers, and known limitations.
- Update `docs/PROGRESS.md`.
