# AI Code Review Agent

Automatically reviews GitHub Pull Requests using four specialized AI agents running in parallel. Findings are posted back as a structured PR comment and visualized in a React dashboard.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![React](https://img.shields.io/badge/React-19-61dafb) ![FastAPI](https://img.shields.io/badge/FastAPI-0.104-009688) ![Tests](https://img.shields.io/badge/backend_tests-148_passing-brightgreen) ![License](https://img.shields.io/badge/license-MIT-green)

---

## How it works

```
GitHub PR opened
       │
       ▼
POST /api/github/webhook  (HMAC-SHA256 verified)
       │
       ▼
FastAPI creates Review record, returns 202
       │
       ▼  (background task)
LangGraph Orchestrator
       │
       ├──► Security Agent  ─┐
       ├──► Performance Agent─┤  (parallel, 30s timeout each)
       ├──► Style Agent     ─┤
       └──► Logic Agent     ─┘
                              │
                              ▼
                    Result Aggregator
                    (dedup + severity sort)
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
             Dashboard UI         PR Comment posted
          (real-time via WS)      to GitHub
```

**Four agents, each focused on one concern:**

| Agent | Finds |
|---|---|
| Security | SQL injection, XSS, hardcoded secrets, weak crypto, auth bypass |
| Performance | N+1 queries, O(n²) loops, memory leaks, large unnecessary copies |
| Style | Naming conventions, line length, missing docstrings, unused imports |
| Logic | Off-by-one errors, null dereferences, type mismatches, boundary bugs |

---

## Features

- Parallel agent execution with per-agent timeouts
- Multi-LLM support: Claude Opus 4.6 (primary), GPT (fallback), Ollama (local/private)
- Real-time WebSocket progress updates while analysis runs
- GitHub App integration — webhook trigger + automatic PR comments
- React dashboard with review history, findings table, and per-agent stats
- JWT authentication, encrypted API key storage (Fernet)
- 148 backend tests + 30 frontend tests

---

## Tech stack

| Layer | Technology |
|---|---|
| Backend | Python 3.12, FastAPI, LangGraph, SQLAlchemy (async) |
| Database | PostgreSQL 16 |
| Frontend | React 19, JavaScript + JSDoc, TailwindCSS, Zustand |
| LLMs | Claude Opus 4.6, OpenAI GPT, Ollama (Qwen2.5-Coder) |
| Auth | JWT (HS256), Fernet encryption for stored keys |
| Infrastructure | Docker, docker-compose |

---

## Quick start

### Prerequisites

- Docker + Docker Compose
- A GitHub account (for the App integration)
- An Anthropic or OpenAI API key (optional — you can also use local Ollama)

### 1. Clone and configure

```bash
git clone https://github.com/S1rt3ge/code-review-agent
cd code-review-agent
cp .env.example .env
```

Open `.env` and set the required values:

```env
# Required
JWT_SECRET=any-long-random-string-change-this
FERNET_KEY=<run: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">

# Optional but needed for real analysis
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...

# Required for GitHub App integration
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY=-----BEGIN RSA PRIVATE KEY-----...
GITHUB_WEBHOOK_SECRET=your-webhook-secret
```

### 2. Start everything

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| Frontend | http://localhost:5173 |
| Backend API | http://localhost:8000 |
| API docs (Swagger) | http://localhost:8000/docs |
| pgAdmin | http://localhost:5050 |

### 3. Create an account

Open http://localhost:5173 and register. Or via curl:

```bash
# Register
curl -s -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","username":"you","password":"YourPass123!"}'

# Get a JWT token
curl -s -X POST http://localhost:8000/api/auth/token \
  -d "username=you@example.com&password=YourPass123!"
```

---

## GitHub App setup

This is needed for the webhook trigger and for posting comments back to PRs.

1. Go to https://github.com/settings/apps/new and create a new GitHub App:
   - **Webhook URL:** `https://your-domain.com/api/github/webhook`
   - **Permissions:** Pull requests → Read & Write, Contents → Read
   - **Subscribe to events:** `pull_request`

2. Generate a private key and download the `.pem` file.

3. Add to your `.env`:
   ```env
   GITHUB_APP_ID=123456
   GITHUB_APP_PRIVATE_KEY=<contents of .pem, with newlines replaced by \n>
   GITHUB_WEBHOOK_SECRET=<the secret you set in the App settings>
   ```

4. Install the App on your repositories from the App's install page.

Once installed, opening a PR on a connected repo automatically triggers a review.

---

## Running tests

```bash
# All backend tests (requires running Postgres via docker compose)
docker compose --profile test run --rm tests

# Specific test file
docker compose --profile test run --rm tests pytest backend/tests/test_integration.py -v

# Frontend tests (no Docker needed)
cd frontend && npm test -- --run
```

**Current coverage:**
- Backend: 148 tests — agents, services, auth, reviews, settings, dashboard, webhooks, integration
- Frontend: 30 tests — components (StatusBadge, FindingsTable), store (auth), hooks (useApi)

---

## Project structure

```
code-review-agent/
├── backend/
│   ├── agents/
│   │   ├── orchestrator.py        # LangGraph async dispatch (parallel)
│   │   ├── security_agent.py
│   │   ├── performance_agent.py
│   │   ├── style_agent.py
│   │   ├── logic_agent.py
│   │   └── llm_router.py          # Claude / GPT / Ollama selection
│   ├── routers/
│   │   ├── auth.py                # register, token (OAuth2), /me
│   │   ├── reviews.py             # CRUD + analyze + post-comment
│   │   ├── settings.py            # LLM config, encrypted key storage
│   │   ├── dashboard.py           # aggregate stats
│   │   └── github.py              # webhook receiver
│   ├── services/
│   │   ├── analyzer.py            # background analysis runner
│   │   ├── github_api.py          # GitHub App auth + REST calls
│   │   ├── code_extractor.py      # unified diff → CodeChunk
│   │   ├── result_aggregator.py   # dedup + severity ranking
│   │   ├── pr_commenter.py        # markdown comment builder
│   │   └── ws_manager.py          # WebSocket broadcast manager
│   ├── models/
│   │   ├── db_models.py           # SQLAlchemy ORM
│   │   └── schemas.py             # Pydantic request/response schemas
│   └── utils/
│       ├── auth.py                # JWT + PBKDF2 password hashing
│       ├── crypto.py              # Fernet encrypt/decrypt
│       └── webhooks.py            # HMAC-SHA256 signature verification
├── frontend/
│   └── src/
│       ├── pages/                 # Dashboard, ReviewDetail, Settings, Login
│       ├── components/            # FindingsTable, AgentStatus, Navbar, StatusBadge
│       ├── hooks/                 # useApi, useWebsocket, useSettings
│       └── store/                 # Zustand: useAuthStore, useSettingsStore, useUiStore
├── supabase/migrations/           # 001–005 SQL migrations (auto-applied by Postgres container)
├── .github/workflows/ci.yml       # CI: backend tests + frontend build on push/PR
├── Dockerfile                     # Multi-stage: Node build → Python runtime
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

---

## API reference

| Method | Path | Auth | Description |
|---|---|---|---|
| POST | `/api/auth/register` | — | Create account, returns JWT |
| POST | `/api/auth/token` | — | Login (OAuth2 form), returns JWT |
| POST | `/api/auth/password-reset/request` | — | Request password reset link |
| POST | `/api/auth/password-reset/confirm` | — | Confirm reset token + set new password |
| POST | `/api/auth/email-verification/request` | — | Resend email verification link |
| POST | `/api/auth/email-verification/confirm` | — | Verify account email token |
| GET | `/api/auth/me` | JWT | Current user profile |
| GET | `/api/reviews` | JWT | List reviews (paginated) |
| POST | `/api/reviews` | JWT | Create review manually |
| GET | `/api/reviews/{id}` | JWT | Review detail + findings |
| POST | `/api/reviews/{id}/analyze` | JWT | Trigger analysis |
| POST | `/api/reviews/{id}/post-comment` | JWT | Post findings to GitHub PR |
| GET | `/api/settings` | JWT | Get LLM config |
| PUT | `/api/settings` | JWT | Update LLM config + API keys |
| POST | `/api/settings/test-llm` | JWT | Test LLM connectivity |
| GET | `/api/dashboard/stats` | JWT | Aggregate stats per user |
| POST | `/api/github/webhook` | Signature | GitHub webhook receiver |
| WS | `/ws/progress/{review_id}` | — | Real-time agent progress |

Interactive docs with request/response schemas: **http://localhost:8000/docs**

---

## Environment variables

| Variable | Required | Description |
|---|---|---|
| `DATABASE_URL` | Yes | `postgresql+psycopg://user:pass@host/db` |
| `JWT_SECRET` | Yes | Secret for signing JWT tokens |
| `FERNET_KEY` | Yes | Key for encrypting stored API keys |
| `ANTHROPIC_API_KEY` | No | Claude API key (app-level fallback) |
| `OPENAI_API_KEY` | No | OpenAI API key (app-level fallback) |
| `OLLAMA_HOST` | No | Ollama base URL (default: `http://localhost:11434`) |
| `GITHUB_APP_ID` | No | GitHub App ID |
| `GITHUB_APP_PRIVATE_KEY` | No | GitHub App RSA private key |
| `GITHUB_WEBHOOK_SECRET` | No | Webhook HMAC secret |
| `CORS_ORIGINS` | No | Allowed origins (default: localhost dev ports) |
| `FRONTEND_BASE_URL` | No | Base URL used in email links |
| `SMTP_HOST` / `SMTP_PORT` | No | SMTP server settings for real email delivery |
| `SMTP_USER` / `SMTP_PASSWORD` | No | SMTP auth credentials |
| `SMTP_USE_TLS` / `SMTP_FROM` | No | SMTP security + sender |
| `SENTRY_DSN` | No | Backend Sentry DSN |
| `VITE_SENTRY_DSN` | No | Frontend Sentry DSN |
| `REDIS_URL` | No | Optional Redis for multi-instance WS fan-out |
| `ANALYSIS_QUEUE_*` | No | Durable analysis queue poll/retry tuning |

> Security note: in non-dev environments (`APP_ENV` not development/local/test),
> app startup is blocked if `JWT_SECRET` remains `change-me-in-production`.

### Durable analysis queue

- Analysis execution is now driven by a DB-backed `analysis_jobs` table.
- `POST /api/reviews/{id}/analyze` and GitHub webhook events enqueue durable jobs instead of raw in-process tasks.
- A worker loop starts with the app and processes due jobs with retry/backoff.

### CI security gates

- CI now runs secret scanning (`gitleaks`) on repository history and diffs.
- Backend dependency audit uses `pip-audit` (fails on known vulnerable packages).
- Frontend dependency audit uses `npm audit --audit-level=critical`.
- CI publishes SBOM artifacts for backend and frontend (`CycloneDX`: Python XML + frontend JSON).

---

## License

MIT
