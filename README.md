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
- Local Review Playground for demo and pasted-diff reviews without GitHub or paid AI providers
- Review Passport with acceptance-criteria coverage, anti-slop signals, and merge-readiness verdicts
- Deterministic review quality evals for local regression checks
- Review DNA CLI for generating repo-specific AI review instructions and quality gates
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

For local evaluation, the dashboard also includes a Local Review Playground:

1. Click `Try demo review` to create an instant deterministic review from a bundled diff.
2. Click `Paste diff` to review a local git diff without creating a GitHub App.
3. Open the generated review detail page to inspect findings, agent status, and zero-cost local execution.
4. Generate a Review Passport to turn the review into an evidence-backed merge-readiness artifact.

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

### Review Passport

Review detail pages can generate a Review Passport from the review findings, diff snapshot, and optional acceptance criteria.

The passport gives the change a merge-readiness verdict, highlights covered and missing criteria, reports anti-slop signals such as missing tests or placeholder implementation, and produces a short QA script that a reviewer can run locally.

Passports can also be copied as Markdown for local/demo workflows, posted back to GitHub as a PR comment, or published as the `AI Review Passport Gate` commit status for GitHub-backed reviews. `READY` publishes a passing status; `READY_WITH_RISKS` and `BLOCKED` publish failing statuses so branch protection can require the passport before merge.

### Auth and account lifecycle

The application supports a complete authenticated user flow:

- registration
- login via JWT
- email verification
- password reset
- verified-email enforcement for protected access

For local development, email verification can be disabled with
`AUTH_REQUIRE_EMAIL_VERIFICATION=false` so registration and login work without an
SMTP provider. Non-dev environments require verification unless the flag is
explicitly disabled.

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

### Prerequisites

- Python 3.12
- Node.js 20+
- PostgreSQL (or Docker)

### Backend

```bash
pip install -r requirements.txt -r requirements-dev-windows.in  # Windows local dev
python scripts/migrate.py
python -m backend.run
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

This starts PostgreSQL, the FastAPI backend, and the Vite frontend together.
Open the app at `http://localhost:5173`; the frontend proxies `/api` and `/ws`
to the backend container.

Docker defaults to `AUTH_REQUIRE_EMAIL_VERIFICATION=false`, so local accounts can
sign in immediately after registration. Set `AUTH_REQUIRE_EMAIL_VERIFICATION=true`
to test the production-style verification flow.

### Run the local demo in 5 minutes

After Docker starts, open `http://localhost:5173`, create an account, and click
`Try demo review` on the dashboard. This creates a completed review using the
local playground analyzer, so no SMTP, GitHub App, OpenAI, Anthropic, or Ollama
setup is required for the first product walkthrough.

Open the generated review detail page and generate a Review Passport with sample
acceptance criteria. The bundled demo intentionally receives a `BLOCKED` verdict
because the diff contains unsafe code and missing test evidence.

Use `Copy Markdown` to export the passport locally. GitHub PR posting and
`Publish Gate` are available for GitHub-backed reviews with a configured GitHub
App installation.

For a full walkthrough, see [`docs/local-demo.md`](docs/local-demo.md).

## Testing

### Backend

```bash
pytest -m "not integration" --tb=short -q
pytest -m integration --tb=short -q
```

### Review quality evals

```bash
python scripts/evaluate_review_quality.py
python scripts/evaluate_review_quality.py --json
```

The eval runner grades the deterministic Local Review Playground analyzer against
fixture cases in `evals/review_quality_cases.json`. It reports case pass rate,
expected finding recall, unexpected findings, and an overall score.

### Review DNA

```bash
python scripts/review_dna.py scan --json
python scripts/review_dna.py init
python scripts/review_dna.py instructions
python scripts/review_dna.py criteria
python scripts/review_dna.py check
```

Review DNA scans the repository for specs, evals, governance docs, local-first
constraints, and quality gates. It can write `review-dna.yml` and render
reviewer-ready Markdown so AI review tools use this project's actual standards
instead of generic feedback. The advisory `check` command compares changed files
against the profile and reports a project-fit score, missing spec/test evidence,
local-first risks, and recommended verification commands. Pull requests also run
a non-blocking Review DNA workflow that uploads the JSON report and writes the
same score to the GitHub Actions step summary.

Use `criteria` when generating a Review Passport: it renders paste-ready
acceptance criteria from `review-dna.yml`, including spec-first evidence,
required tests, local-demo constraints, and review quality gates.

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
