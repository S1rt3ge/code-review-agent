# AI Code Review Agent

## Mission
AI-assisted code review platform for GitHub PRs and local pasted diffs. It should let a developer get useful findings fast, with the Docker stack usable as a no-paid-services local demo.

## Source Of Truth
- `README.md` - operator setup and launch instructions.
- `PROJECT_IDEA.md` - product vision and business context.
- `TECHNICAL_SPEC.md` - original architecture and system constraints.
- `docs/LOCAL_REVIEW_PLAYGROUND_SPEC.md` - local demo and pasted-diff flow.
- `SPEC_TEMPLATE.md` - template for new feature specs.
- `.claude/rules/*.md` - optional local Claude rules when present.

## Spec-First Workflow
1. For product work, read or create a short spec before code.
2. Use `SPEC_TEMPLATE.md` and cover user stories, data, API, UI, logic, and edge cases.
3. Keep specs close to behavior. Avoid TODO placeholders and vague future sections.
4. Implement tests with the change. Prefer deterministic local tests before provider or network tests.
5. Update `README.md` when the launch path, env, or user workflow changes.

## Architecture
GitHub webhook or local playground -> FastAPI routers -> review service -> analysis agents -> PostgreSQL -> React dashboard.

Email, auth, notifications, GitHub, and LLM providers are adapter boundaries. Local Docker defaults must not require paid email delivery, GitHub tokens, or LLM keys for the playground.

## Stack
- Backend: Python 3.12, FastAPI, SQLAlchemy, Pydantic, PostgreSQL, migration scripts.
- Review logic: deterministic playground analyzer plus LLM-backed agents for live reviews.
- Frontend: React 19, Vite, Tailwind CSS, Zustand, JSDoc-style JavaScript.
- Ops: Docker Compose with backend, frontend, and Postgres.

## Project Map
- `backend/routers` - API boundaries and auth checks.
- `backend/services` - business workflows, review creation, playground analyzer, notifications.
- `backend/agents` - analysis agents and LLM routing.
- `backend/utils` - database, auth, settings, and event-loop utilities.
- `backend/tests` - unit, API, and integration tests.
- `frontend/src/pages` - dashboard, auth, and review detail screens.
- `frontend/src/services` - API client wrappers.
- `docs` - feature specs and implementation notes.

## Local Commands
Docker:
- `docker compose up --build`
- App: `http://localhost:5173`
- API health: `http://localhost:8000/health`
- Stop: `docker compose down`

Backend without Docker:
- `pip install -r requirements.txt`
- `pip install -r requirements-dev-windows.in`
- `python scripts/migrate.py`
- `python -m backend.run`

Frontend without Docker:
- `cd frontend`
- `npm install`
- `npm run dev`

Verification:
- `python -m pytest -m "not integration" --tb=short -q`
- `python -m pytest -m integration --tb=short -q`
- `python scripts/evaluate_review_quality.py`
- `python -m ruff check backend`
- `cd frontend && npm test -- --run && npm run build`

## Local Auth
Docker and local dev may set `AUTH_REQUIRE_EMAIL_VERIFICATION=false` so registration and login work without a paid email provider. Production-like environments should keep verification enabled unless there is an explicit product decision.

## Engineering Rules
- Keep this file under 120 lines. Move detailed rules into dedicated files.
- Backend changes follow `.claude/rules/backend-rules.md` when that local package exists.
- Frontend changes follow `.claude/rules/frontend-rules.md` when that local package exists.
- Use existing auth, DB session, API client, and notification helpers before adding new abstractions.
- Do not hardcode secrets. Use env vars and `.env.example` for documented defaults.
- Preserve local playground behavior: no GitHub token, email provider, or LLM key required.
- Treat generated reviews as user-visible data. Keep schemas stable and migration-safe.

## Current Product Priorities
1. Smooth local onboarding through Docker.
2. A convincing Local Review Playground for demos and offline testing.
3. Deterministic review quality evals that prove findings stay useful.
4. Reliable GitHub PR review path with clear provider boundaries.
5. Focused, actionable findings rather than noisy review output.
