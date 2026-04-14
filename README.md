# AI-Powered Code Review Agent

Multi-agent code review system that automatically analyzes GitHub Pull Requests and posts findings as PR comments. Built with FastAPI + LangGraph on the backend and React 19 on the frontend.

## Architecture

```
GitHub Webhook → FastAPI → LangGraph Orchestrator → [Security | Performance | Style | Logic]
                                                              ↓ asyncio.gather (parallel)
                                          Result Aggregator → Dashboard + PR Comment
```

Four specialized agents run in parallel, each focused on a different aspect of code quality. Results are deduplicated, ranked by severity, and posted back to the PR as a structured comment.

## Features

- **4 parallel agents** — Security, Performance, Style, Logic
- **Multi-LLM support** — Claude Opus 4.6 (primary), GPT (fallback), Ollama (local/private)
- **Real-time progress** — WebSocket updates while analysis runs
- **GitHub App integration** — Webhook trigger, automatic PR comments
- **React dashboard** — Review history, findings table, per-agent stats
- **JWT auth** — Register/login, encrypted API key storage

## Tech Stack

| Layer | Tech |
|-------|------|
| Backend | Python 3.12, FastAPI, LangGraph, SQLAlchemy async |
| Database | PostgreSQL |
| Frontend | React 19, JavaScript (JSDoc), TailwindCSS, Zustand |
| LLMs | Claude Opus 4.6, OpenAI GPT, Ollama (Qwen2.5-Coder) |
| Auth | JWT (HS256), Fernet key encryption |
| Infra | Docker, docker-compose |

## Quick Start

### Prerequisites

- Docker + Docker Compose
- (Optional) Anthropic / OpenAI API key for real LLM calls

### 1. Clone and configure

```bash
git clone https://github.com/S1rt3ge/code-review-agent
cd code-review-agent
cp .env.example .env
```

Edit `.env` — at minimum set:

```env
JWT_SECRET=any-long-random-string
FERNET_KEY=<output of: python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())">
ANTHROPIC_API_KEY=sk-ant-...   # optional — needed for real analysis
```

### 2. Start services

```bash
docker compose up --build
```

| Service | URL |
|---------|-----|
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| Frontend | http://localhost:5173 (dev) |
| Health check | http://localhost:8000/health |

### 3. Register and log in

```bash
# Register
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"you@example.com","password":"yourpassword"}'

# Get JWT token
curl -X POST http://localhost:8000/api/auth/token \
  -d "username=you@example.com&password=yourpassword"
```

Then open http://localhost:5173 and sign in via the UI.

## Running Tests

```bash
# All backend tests (runs inside Docker with real Postgres)
docker compose --profile test run --rm tests

# Single file
docker compose --profile test run --rm tests pytest backend/tests/test_pr_commenter.py -v
```

Current coverage: **127 backend tests** passing.

## Project Structure

```
code-review-agent/
├── backend/
│   ├── agents/
│   │   ├── orchestrator.py       # asyncio.gather parallel dispatch
│   │   ├── security_agent.py     # SQL injection, XSS, secrets
│   │   ├── performance_agent.py  # N+1, O(n²), memory leaks
│   │   ├── style_agent.py        # naming, line length, docstrings
│   │   ├── logic_agent.py        # off-by-one, null checks, type errors
│   │   └── llm_router.py         # Claude / GPT / Ollama selection
│   ├── routers/
│   │   ├── auth.py               # register, login, /me
│   │   ├── reviews.py            # CRUD + analyze + post-comment
│   │   ├── settings.py           # LLM config, encrypted key storage
│   │   ├── dashboard.py          # aggregate stats (JWT-protected)
│   │   └── github.py             # webhook receiver
│   ├── services/
│   │   ├── analyzer.py           # background analysis task
│   │   ├── github_api.py         # GitHub App auth + API calls
│   │   ├── code_extractor.py     # unified diff → CodeChunk
│   │   ├── result_aggregator.py  # dedup + severity ranking
│   │   ├── pr_commenter.py       # markdown comment builder
│   │   └── ws_manager.py         # WebSocket broadcast manager
│   └── utils/
│       ├── auth.py               # JWT + PBKDF2 password hashing
│       ├── crypto.py             # Fernet encrypt/decrypt
│       └── webhooks.py           # HMAC-SHA256 signature verification
├── frontend/
│   └── src/
│       ├── pages/                # Dashboard, ReviewDetail, Settings, Login
│       ├── components/           # FindingsTable, AgentStatus, Navbar, …
│       ├── hooks/                # useApi, useWebsocket, useSettings
│       └── store/                # Zustand: auth, settings, UI
├── supabase/migrations/          # 001–004 SQL migrations
├── docker-compose.yml
├── requirements.txt
└── .env.example
```

## GitHub App Setup

1. Create a GitHub App at https://github.com/settings/apps/new
   - Webhook URL: `https://your-domain.com/api/github/webhook`
   - Permissions: Pull requests (Read & Write), Contents (Read)
   - Subscribe to: `pull_request` events
2. Generate a private key and download it
3. Set in `.env`:
   ```env
   GITHUB_APP_ID=123456
   GITHUB_APP_PRIVATE_KEY=<contents of .pem file, newlines as \n>
   GITHUB_WEBHOOK_SECRET=<secret you set in the app>
   ```
4. Install the app on your repositories

## API Reference

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/auth/register` | Create account |
| POST | `/api/auth/token` | Get JWT (OAuth2 form) |
| GET | `/api/auth/me` | Current user |
| GET | `/api/reviews` | List reviews (paginated) |
| POST | `/api/reviews` | Create review manually |
| GET | `/api/reviews/{id}` | Review detail + findings |
| POST | `/api/reviews/{id}/analyze` | Trigger analysis |
| POST | `/api/reviews/{id}/post-comment` | Post to GitHub PR |
| GET | `/api/settings` | Get LLM config |
| PUT | `/api/settings` | Update LLM config |
| POST | `/api/settings/test-llm` | Test LLM connectivity |
| GET | `/api/dashboard/stats` | Aggregate stats |
| POST | `/api/github/webhook` | GitHub webhook receiver |
| WS | `/ws/progress/{review_id}` | Real-time agent updates |

Full interactive docs: http://localhost:8000/docs

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | Yes | PostgreSQL connection string |
| `JWT_SECRET` | Yes | Secret for signing JWT tokens |
| `FERNET_KEY` | Yes | Key for encrypting stored API keys |
| `ANTHROPIC_API_KEY` | No | Claude API key (app-level fallback) |
| `OPENAI_API_KEY` | No | OpenAI API key (app-level fallback) |
| `GITHUB_APP_ID` | No | GitHub App ID |
| `GITHUB_APP_PRIVATE_KEY` | No | GitHub App private key (RSA) |
| `GITHUB_WEBHOOK_SECRET` | No | Webhook signature secret |
| `CORS_ORIGINS` | No | Allowed origins (default: localhost dev ports) |

## License

MIT
