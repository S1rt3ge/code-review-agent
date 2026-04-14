# AI-Powered Code Review Agent

## Overview
Multi-agent code review system built with FastAPI + LangGraph. Analyzes GitHub PRs using specialized agents (Security, Performance, Style, Logic) that work in parallel. Results posted to dashboard + GitHub PR comments.

## Architecture
```
GitHub Webhook → FastAPI → LangGraph Orchestrator → [Security|Perf|Style|Logic] Agents
                                                              ↓
                                          Result Aggregator → {Dashboard, PR Comment}
```

**Agents:** Parallel execution, each agent specializes in one aspect. LLM router selects Claude/GPT/Local based on user settings.

## Tech Stack
**Backend:** Python 3.12, FastAPI, LangGraph, PostgreSQL, Pydantic
**Frontend:** React 19, JavaScript (JSDoc), TailwindCSS, Zustand
**LLM:** Claude Opus 4.6 (primary), GPT-5.4 (fallback), Qwen2.5-Coder-32B (local via Ollama)
**Infrastructure:** Docker, PostgreSQL, Redis (optional)

## Project Structure
```
code-review-agent/
├── backend/
│   ├── main.py                 # FastAPI app entry
│   ├── config.py               # Env config
│   ├── agents/
│   │   ├── orchestrator.py     # LangGraph main orchestration
│   │   ├── security_agent.py   # Security analysis
│   │   ├── performance_agent.py # Perf analysis
│   │   ├── style_agent.py      # Code style
│   │   ├── logic_agent.py      # Logic errors
│   │   └── llm_router.py       # LLM selection logic
│   ├── routers/
│   │   ├── github.py           # Webhook endpoints
│   │   ├── reviews.py          # Review endpoints
│   │   ├── settings.py         # User settings
│   │   └── dashboard.py        # Stats/analytics
│   ├── models/
│   │   ├── db_models.py        # SQLAlchemy ORM
│   │   └── schemas.py          # Pydantic schemas
│   ├── services/
│   │   ├── github_api.py       # GitHub API wrapper
│   │   ├── code_extractor.py   # Code diff parsing
│   │   └── result_aggregator.py# Dedup + ranking
│   └── utils/
│       ├── crypto.py           # Encrypt API keys
│       └── webhooks.py         # Signature verification
├── frontend/
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Dashboard.jsx
│   │   │   ├── ReviewDetail.jsx
│   │   │   ├── Settings.jsx
│   │   │   └── Login.jsx
│   │   ├── components/
│   │   │   ├── FindingsTable.jsx
│   │   │   ├── AgentStatus.jsx
│   │   │   ├── LLMSelector.jsx
│   │   │   ├── Navbar.jsx
│   │   │   ├── StatusBadge.jsx
│   │   │   └── ProtectedRoute.jsx
│   │   ├── hooks/
│   │   │   ├── useApi.js
│   │   │   ├── useWebsocket.js
│   │   │   └── useSettings.js
│   │   ├── store/
│   │   │   └── index.js
│   │   └── App.jsx
│   └── package.json
├── supabase/
│   ├── migrations/
│   │   ├── 001_initial_schema.sql
│   │   ├── 002_add_agents.sql
│   │   └── 003_add_audit_log.sql
│   └── functions/
├── .claude/
│   ├── agents/
│   │   ├── backend-engineer.md
│   │   ├── frontend-developer.md
│   │   └── qa-reviewer.md
│   ├── rules/
│   │   ├── backend-rules.md
│   │   ├── frontend-rules.md
│   │   └── database-rules.md
│   └── skills/
│       ├── implement-agent.md
│       └── analyze-code.md
├── docker-compose.yml
├── requirements.txt
├── .env.example
└── README.md
```

## Key Decisions

**1. LLM Selection Strategy:**
- User configures Claude/GPT/Local in settings
- Each agent call goes through `llm_router.select()` which picks best available
- Fallback chain: Claude → GPT → Local (if configured)
- Cost optimization: Sonnet for UI agents, Opus for complex logic

**2. Parallel Agents:**
- All agents run concurrently via LangGraph async
- Shared context (code diff, PR metadata)
- Individual timeouts (30s per agent)
- Results aggregated with deduplication

**3. GitHub Integration:**
- Webhook signature verification (HMAC-SHA256)
- GitHub App for authentication (not personal token)
- Async processing (202 response immediately)
- PR comments posted after analysis complete

**4. Dashboard:**
- React SPA, authenticated via JWT
- Real-time progress updates via WebSocket
- Settings page for LLM configuration
- History of past reviews with filtering

## API Rules

**GitHub Webhook:** `POST /github/webhook`
- Verify signature: `X-Hub-Signature-256`
- Create/update review record
- Queue analysis async
- Return 202 Accepted

**Review Analysis:** `POST /reviews/{id}/analyze`
- Fetch code diff
- Call orchestrator with selected agents
- Update review status → completed
- Post PR comment if enabled

**Settings:** `PUT /settings`
- Validate API keys (test call)
- Test Ollama connectivity
- Encrypt and store

**Dashboard:** `GET /dashboard/stats`
- Aggregate metrics (total reviews, findings by severity, etc.)
- Return JSON for frontend charts

## Database Rules

**RLS (Row-Level Security):**
- All tables have `user_id` FK
- SELECT: only own records
- UPDATE: only own records if status allows
- DELETE: restricted (soft delete via status)

**Indexes:**
- `reviews(user_id, status, created_at DESC)`
- `findings(review_id, severity, created_at DESC)`
- `agent_executions(review_id, agent_name)`

**Constraints:**
- Unique: `(user_id, repo_owner, repo_name)` for repositories
- FK: all foreign keys cascade

## Frontend Rules

**Components:**
- Settings page: LLM config, API key inputs, test buttons
- Dashboard: summary cards, recent reviews table, stats charts
- Review detail: findings grouped by severity, code snippets

**State Management:**
- Zustand store: user settings, current review, UI state
- Fetch on load, cache for 5 minutes
- WebSocket for realtime progress during analysis

**Styling:**
- TailwindCSS utility classes only
- Dark mode support
- Mobile responsive

## Agents (LangGraph Nodes)

**Node: security_agent**
- Input: code, language, context
- Output: findings list (type, line, severity, message, suggestion)
- Model: Claude Opus 4.6
- Looks for: SQL injection, XSS, auth bypass, hardcoded secrets, weak crypto

**Node: performance_agent**
- Input: code, language, framework context
- Output: findings list
- Model: Claude Opus 4.6
- Looks for: N+1 queries, O(n²) algorithms, memory leaks, large copies

**Node: style_agent**
- Input: code, language, style_guide
- Output: findings list
- Model: Claude Sonnet 4.6 (cheaper)
- Looks for: naming, line length, imports, docstrings

**Node: logic_agent**
- Input: code, language, business logic context
- Output: findings list
- Model: Claude Opus 4.6
- Looks for: off-by-one, null checks, type mismatches, boundary bugs

**Node: result_aggregator**
- Input: all agent outputs
- Output: deduplicated, ranked findings
- Removes duplicates (same issue from multiple agents)
- Sorts by severity: critical → warning → info
- Groups by file path

## Commands

**Run locally:**
```bash
# Backend
pip install -r requirements.txt
python -m uvicorn backend.main:app --reload

# Frontend
cd frontend && npm install && npm run dev

# Database (Supabase or local PostgreSQL)
docker-compose up postgres
psql -f supabase/migrations/001_initial_schema.sql
```

**Deploy:**
```bash
docker build -t code-review-agent .
docker run -p 8000:8000 -e DATABASE_URL=... code-review-agent
```

**Test LLM connectivity:**
```bash
curl http://localhost:8000/settings/test-llm
# Returns: {"claude_available": true, "gpt_available": false, "ollama_available": true}
```

## Status Codes

- **202 Accepted:** Webhook received, analysis queued
- **200 OK:** Settings updated, review done, findings retrieved
- **400 Bad Request:** Invalid API key, missing required field
- **401 Unauthorized:** Invalid signature, missing JWT
- **404 Not Found:** Repository not configured, review not found
- **409 Conflict:** Duplicate review already running
- **500 Server Error:** LLM API down, database error

## Metrics to Track

- **Review latency:** P95 time from webhook to PR comment (<5m target)
- **Finding accuracy:** RAGAS faithfulness score (≥0.8 target)
- **False positive rate:** % findings that aren't real issues (<15% target)
- **Tokens used:** Per review, per user (for billing)
- **Agent execution time:** Per agent, per review
- **LLM selection:** Which LLM used (Claude vs GPT vs Local)

## Next Steps (v2.0)

- [ ] Custom agent builder (no-code UI)
- [ ] Fine-tuned models (train on team patterns)
- [ ] Team collaboration (shared findings)
- [ ] Advanced suggestions (auto-fix)
- [ ] Metrics dashboard (quality trends)
- [ ] VS Code extension
- [ ] Slack integration

## Dependencies
- `fastapi>=0.104` — API framework
- `langgraph>=0.0.19` — Agent orchestration
- `sqlalchemy>=2.0` — ORM
- `psycopg[binary]>=3.1` — PostgreSQL driver
- `anthropic>=0.7` — Claude API
- `openai>=1.0` — GPT API
- `httpx` — Async HTTP client
- `pydantic>=2.0` — Data validation
- `pydantic-settings` — Environment config
- `python-jose[cryptography]` — JWT
- `cryptography` — Encrypt API keys
- `websockets` — Real-time updates
