# AI Code Review Agent

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white) ![FastAPI](https://img.shields.io/badge/FastAPI-async-009688?logo=fastapi&logoColor=white) ![React](https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black) ![PostgreSQL](https://img.shields.io/badge/PostgreSQL-queue%20backed-4169E1?logo=postgresql&logoColor=white) ![License](https://img.shields.io/badge/License-MIT-green)

AI Code Review Agent is a local-first review assistant for pull requests and pasted diffs.
It analyzes code changes, groups useful findings, and can generate a Review Passport that
turns a review into a merge-readiness checklist.

The fastest path does not require GitHub, SMTP, OpenAI, Anthropic, or any paid provider.
Run the Docker stack, create a local account, and start with the bundled demo review.

## What You Get

- Multi-agent code review for security, performance, style, and logic issues
- Local Review Playground for demo reviews and pasted diffs
- Review Passport with acceptance-criteria coverage, anti-slop signals, QA steps, and a merge verdict
- React dashboard with review history, findings, and live progress
- Optional GitHub webhook, PR comment, and commit status integration
- Local demo auth that works without email delivery

## How it works

Four specialized agents — **Security**, **Performance**, **Style**, and **Logic** — review each diff **in parallel**, then their findings are aggregated into a single **Review Passport** with a merge verdict.

- **Parallel agents** — each reviewer owns one concern and runs concurrently for fast, structured findings (LangGraph orchestration).
- **Multi-LLM routing** — Claude Opus 4.6 as primary, OpenAI GPT as fallback, and local Ollama/Qwen for private repos; stored API keys are encrypted at rest (Fernet).
- **GitHub App** — HMAC-SHA256-verified webhooks post findings as PR comments and commit statuses; a durable queue handles retries and stale-lock recovery.
- **Review Passport** — acceptance-criteria coverage, anti-slop signals, QA steps, and a blocking/approve verdict.
- **Local-first** — the full demo runs offline in Docker, no GitHub or paid providers required.

## Quick Start

Prerequisites:

- Docker Desktop
- Git

Run the app:

```bash
git clone https://github.com/S1rt3ge/code-review-agent.git
cd code-review-agent
docker compose up --build
```

No `.env` file is required for the local demo. Docker Compose ships with safe
local defaults, including disabled email verification.

Open:

- App: `http://localhost:5173`
- API health: `http://localhost:8000/health`

Stop the stack:

```bash
docker compose down
```

Reset local database data:

```bash
docker compose down -v
```

## First Review In 2 Minutes

1. Open `http://localhost:5173`.
2. Register a local account.
3. Click `Try demo review` on the dashboard.
4. Open the generated review.
5. Generate a Review Passport.

The demo review is deterministic and offline-friendly. It intentionally contains risky code,
so the Review Passport should produce a blocking verdict instead of a generic approval.

Useful sample acceptance criteria:

```text
- Remove unsafe dynamic execution
- Do not expose hardcoded secrets
- Add coverage for dangerous input handling
```

## Review Your Own Diff

You can test the product on local work without creating a GitHub App:

```bash
git diff > my-change.diff
```

Then open the dashboard, click `Paste diff`, paste the diff, and run the review.

## Local Auth

Docker defaults to:

```bash
AUTH_REQUIRE_EMAIL_VERIFICATION=false
```

That means local registration and login work immediately without an SMTP provider.
Use email verification only when you are testing a production-like setup.

## Optional GitHub Setup

The local playground works without GitHub. Configure GitHub only when you want PR automation:

1. Create a GitHub App.
2. Set the webhook URL to your backend `/api/github/webhook` endpoint.
3. Set `GITHUB_WEBHOOK_SECRET`.
4. Install the app on a repository.
5. Connect the repository in the dashboard.

For local webhook testing, expose the backend with a tunnel such as ngrok or Cloudflare Tunnel.

## Optional LLM Providers

The demo path works without provider keys. For live AI-backed reviews, configure one or more:

- Anthropic API key
- OpenAI API key
- Local Ollama endpoint

Provider settings are managed in the app settings page. Stored API keys are encrypted at rest.

For environment overrides, copy `.env.example` to `.env` and fill only the
values you need. Keep `.env` private.

## Run Without Docker

Backend:

```bash
pip install -r requirements.txt -r requirements-dev-windows.in
export DATABASE_URL=postgresql+psycopg://cra_user:cra_password@localhost:5432/cra_db
python scripts/migrate.py
python -m backend.run
```

The backend expects a reachable PostgreSQL database. The URL above matches the
default credentials from `docker-compose.yml` if you run only the Postgres
service with Docker.

Frontend:

```bash
cd frontend
npm ci
npm run dev
```

## Verification

Backend:

```bash
python -m pytest -m "not integration" --tb=short -q
python -m ruff check backend
```

Review quality evals:

```bash
python scripts/evaluate_review_quality.py
```

Frontend:

```bash
cd frontend
npm test -- --run
npm run build
```

Browser smoke test:

```bash
docker compose up -d --build
cd frontend
npm run test:e2e:install
npm run test:e2e:local
```

The smoke test opens Chromium and checks the local user flow end to end:
register, sign in, create a demo review, and generate a Review Passport.
By default it targets `http://127.0.0.1:5173` and `http://127.0.0.1:8000`;
override with `E2E_BASE_URL` and `E2E_API_URL` when needed.

## Troubleshooting

If login asks for email verification, make sure the backend has:

```bash
AUTH_REQUIRE_EMAIL_VERIFICATION=false
```

If the frontend loads but API calls fail:

```bash
docker compose ps
```

Then check `http://localhost:8000/health` and confirm the database is connected.

If Docker rebuilds slowly, run the stack once and keep it running while you test.

## License

MIT
