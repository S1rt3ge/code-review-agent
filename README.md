# AI Code Review Agent

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white) ![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-queue%20backed-4169E1?logo=postgresql&logoColor=white) ![GitHub Actions](https://img.shields.io/badge/CI-security%20gated-2088FF?logo=githubactions&logoColor=white) ![License](https://img.shields.io/badge/License-MIT-green)

A production-oriented full-stack application that reviews GitHub pull requests using multiple specialized AI agents running in parallel.

The system ingests PR events, extracts code diffs, routes them through dedicated review agents (security, performance, style, logic), aggregates findings, and surfaces results through both GitHub PR comments and a real-time web dashboard.

This project was built as an end-to-end engineering exercise in backend architecture, async workflows, frontend UX, CI/CD hardening, operational reliability, and AI-assisted developer tooling.

## Key Engineering Wins

- Built a **durable database-backed analysis queue** with retry, stale-lock recovery, and health diagnostics instead of transient in-memory background tasks.
- Implemented a **multi-agent review pipeline** that separates security, performance, style, and logic concerns while aggregating results into a single developer-facing output.
- Hardened the project with **rate limiting, release gates, secret scanning, dependency audits, SBOM generation, branch protection, and governance policies**.
- Delivered a **full-stack authenticated product flow** with JWT auth, email verification, password reset, encrypted settings storage, and real-time WebSocket progress.

## Highlights

- Parallel multi-agent review with deduplicated result aggregation
- Async FastAPI backend with PostgreSQL, JWT auth, and WebSocket progress updates
- React dashboard for review history, settings, and real-time execution state
- Durable database-backed analysis queue with retry, stale-lock recovery, and health diagnostics
- GitHub webhook / PR comment integration
- Production hardening across auth, CI, release gating, dependency hygiene, and governance

## Product Overview

At a high level, the application behaves like an automated AI reviewer that sits inside a normal GitHub-based pull request workflow:

1. A pull request is opened or updated.
2. GitHub sends a webhook event to the backend.
3. A review record is created and queued for durable background processing.
4. Code diffs are chunked and analyzed by multiple domain-specific agents in parallel.
5. Findings are deduplicated, ranked, and stored.
6. Results are exposed in the dashboard and can be posted back to the PR as a structured comment.

## Architecture

```text
GitHub Pull Request Event
        |
        v
FastAPI Webhook Receiver
        |
        v
Review + Analysis Job Created
        |
        v
Durable Analysis Queue (DB-backed)
        |
        v
LangGraph-style Orchestrator
        |
        +--> Security Agent
        +--> Performance Agent
        +--> Style Agent
        +--> Logic Agent
        |
        v
Result Aggregation + Persistence
        |
        +--> Dashboard API / WebSocket updates
        +--> GitHub PR comment publishing
```

## Core Capabilities

### Multi-agent AI review

The backend runs several specialized review agents in parallel, each focused on a different concern:

| Agent | Focus |
|---|---|
| Security | Injection, secret exposure, auth flaws, insecure patterns |
| Performance | N+1 patterns, expensive loops, avoidable copies, scaling risks |
| Style | Naming, readability, consistency, maintainability issues |
| Logic | Boundary conditions, null handling, type mismatches, correctness bugs |

### Durable background processing

Instead of relying on fire-and-forget in-memory tasks, review execution is backed by a durable `analysis_jobs` queue in the database.

This includes:

- queued job persistence
- retries with backoff
- stale lock recovery
- queue health metrics
- startup recovery for interrupted work

### Real-time user feedback

The frontend subscribes to review progress through WebSockets so users can see analysis state changes while the backend processes a review.

### Auth and account lifecycle

The application supports a complete authenticated user flow:

- registration
- login via JWT
- email verification
- password reset
- verified-email enforcement for protected access

### GitHub integration

The system is designed to operate as part of a GitHub PR workflow, including:

- webhook validation
- repository linkage
- PR-triggered review creation
- optional PR comment publishing with findings

## Engineering Focus Areas

This project intentionally goes beyond a prototype and includes engineering concerns that are often missing from demo applications.

### Reliability

- Durable queue instead of transient in-process background work
- Stale job recovery for long-running tasks
- Startup recovery for interrupted review state
- Degraded health signaling when queue risk thresholds are exceeded

### Security

- Auth rate limiting
- Webhook signature validation
- Encrypted key storage with Fernet
- Production guardrail for default JWT secret
- Explicit production email delivery behavior
- Secret scanning and dependency audit gates in CI

### Observability

- Sentry integration hooks
- Queue diagnostics via `/health` and dashboard stats
- Alerting baseline for backlog, stale jobs, and runtime exceptions

### Delivery discipline

- Locked Python dependency workflow using `pip-tools`
- Deterministic frontend installs without `--legacy-peer-deps`
- Release checklist and release workflow with gating checks
- SBOM generation in CI
- Branch protection, CODEOWNERS, and governance documentation

## Tech Stack

### Backend

- Python 3.12
- FastAPI
- SQLAlchemy (async)
- PostgreSQL
- SlowAPI
- JWT auth
- Sentry SDK

### Frontend

- React 19
- Vite 8
- JavaScript with JSDoc typing
- Tailwind CSS 4
- Zustand
- Vitest + Testing Library

### AI / orchestration

- Multi-agent orchestration pattern inspired by LangGraph-style execution
- model/provider routing abstraction
- support for hosted and local model execution paths

### Tooling / Ops

- Docker / Docker Compose
- GitHub Actions
- Dependabot
- Gitleaks
- pip-audit / npm audit
- CycloneDX SBOM generation

## Repository Structure

```text
backend/
  agents/         # AI review agent implementations and orchestration
  routers/        # API endpoints
  services/       # queueing, GitHub, aggregation, notifications, extraction
  models/         # ORM models and API schemas
  utils/          # auth, crypto, DB, rate limiting, helpers

frontend/
  src/
    pages/        # route-level screens
    components/   # reusable UI pieces
    hooks/        # API / websocket / settings hooks
    store/        # Zustand state

supabase/migrations/
  SQL schema and incremental database migrations

.github/
  workflows/      # CI, release, PR labeling
  CODEOWNERS
  ISSUE_TEMPLATE/
```

## Selected Implementation Details

### Queue health model

The queue layer exposes operational metrics such as:

- pending job count
- running job count
- error job count
- retry count
- stale running job count
- oldest pending age

These metrics are surfaced through:

- `/health`
- `/api/dashboard/stats`

### Release workflow

The manual release workflow validates:

- semantic version format
- target branch correctness
- required check-runs are green
- changelog has non-empty unreleased notes

### Cross-platform Python dependency strategy

The project uses:

- `requirements.in` as the source spec
- `requirements.txt` as the canonical locked runtime dependency set
- `requirements-dev-windows.in` as a Windows-specific local development overlay

This keeps CI/runtime deterministic while still allowing local development on Windows.

## Local Development

### Run Local Demo In 5 Minutes

The self-hosted demo path does not require a GitHub App, webhook tunnel, hosted LLM key, paid domain, or paid infrastructure.

```bash
docker compose up -d postgres
python scripts/migrate.py
uvicorn backend.main:app --reload
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`, create an account, sign in, and click `Load demo data` on the empty dashboard. The demo seed creates a realistic repository, completed reviews, findings, agent execution history, and queue records for your user.

Demo seeding is intentionally blocked outside local/demo/test environments. See `docs/local-demo.md` for the full walkthrough.

### Prerequisites

- Python 3.12
- Node.js 20+
- PostgreSQL (or Docker)

### Backend

```bash
pip install -r requirements.txt -r requirements-dev-windows.in  # Windows local dev
uvicorn backend.main:app --reload
```

### Frontend

```bash
cd frontend
npm ci
npm run dev
```

### Docker

```bash
docker compose up --build
```

## Testing

### Backend

```bash
pytest -m "not integration" --tb=short -q
pytest -m integration --tb=short -q
```

### Frontend

```bash
cd frontend
npm test -- --run
npm run build
```

### CI gates

The repository includes automated checks for:

- backend tests
- frontend build
- secret scanning
- dependency auditing
- SBOM generation
- linting

## What This Project Demonstrates

This repository is intentionally strong as a hiring portfolio project because it demonstrates more than feature implementation.

It shows experience with:

- Designing async backend systems
- Building full-stack authenticated products
- Integrating external platforms such as GitHub
- Orchestrating AI-driven workflows
- Making systems production-capable through queueing, recovery, release gates, and operational docs
- Improving developer experience through automation and governance

## Notes

Some operational details in this repository are intentionally documented at a policy/process level rather than tied to any personal or private infrastructure. The goal is to show engineering quality and production thinking without exposing sensitive configuration or deployment specifics.

## License

MIT
