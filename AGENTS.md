# Repository Instructions For Codex

## First Move
Read `CLAUDE.md`, `README.md`, and any feature spec in `docs/` that touches the task. For a new feature, create or update a spec with `SPEC_TEMPLATE.md` before implementation.

## Working Style
- Keep changes scoped to the requested feature or fix.
- Respect the dirty worktree. Do not reset, revert, or overwrite user changes unless explicitly asked.
- Prefer existing project helpers over new abstractions.
- Update tests and docs in the same change when behavior, setup, or public API changes.
- Leave local playground flows usable without GitHub, email provider, or LLM credentials.

## Backend
- Stack: Python, FastAPI, SQLAlchemy, Pydantic, PostgreSQL.
- Keep route handlers thin. Put workflow logic in `backend/services`.
- Use existing auth policy helpers for email verification and current-user checks.
- Keep database work session-scoped and migration-safe.
- Add deterministic tests for new behavior before relying on external providers.

## Frontend
- Stack: React, Vite, Tailwind CSS, Zustand, JavaScript with JSDoc.
- Reuse `frontend/src/services/api.js` and existing page/component patterns.
- Keep dashboard workflows direct and testable.
- Do not introduce TypeScript unless the project is intentionally migrated.

## Verification Commands
- Backend unit/API: `python -m pytest -m "not integration" --tb=short -q`
- Backend integration: `python -m pytest -m integration --tb=short -q`
- Review evals: `python scripts/evaluate_review_quality.py`
- Backend lint: `python -m ruff check backend`
- Frontend tests/build: `cd frontend && npm test -- --run && npm run build`

## Local Run Commands
- Full stack: `docker compose up --build`
- App: `http://localhost:5173`
- API health: `http://localhost:8000/health`
- Stop stack: `docker compose down`

## Security
- Never hardcode secrets, tokens, provider keys, or passwords.
- Document required env vars in `.env.example`.
- Treat networked tools and third-party resources as read-only unless the user explicitly approves a write action.
- Keep production-like auth stricter than local demo auth.
