# Development Plan: Code Review Agent

Полный timeline для разработки с использованием Spec-First методологии.

---

## Current Status

**Last updated:** 2026-04-14

| Phase | Status | Tests |
|-------|--------|-------|
| 1.1 Project Setup & DB | ✅ Done | — |
| 1.2 GitHub Integration | ✅ Done | — |
| 1.3 JWT Auth & Settings | ✅ Done | — |
| 1.4 Security Agent + Orchestrator | ✅ Done | 72 passing |
| 2.1 Remaining Agents | ✅ Done | — |
| 2.2 Parallel Execution | ✅ Done | — |
| 2.3 Result Aggregation | ✅ Done | — |
| 2.4 PR Comment Generation | ✅ Done | 127 passing |
| 3.1 Dashboard Pages | ✅ Done | build clean |
| 3.2 API Integration | ✅ Done | useApi + useSettings |
| 3.3 Real-time Progress | ✅ Done | useWebsocket |
| **3.4 Auth Flow (Login/Register)** | **⬅ NEXT** | — |

**Run tests:** `docker compose --profile test run --rm tests`
**Run backend:** `docker compose up backend`

---

## Phase 0: Preparation (Already Done ✅)

✅ PROJECT_IDEA.md — полное описание проблемы, архитектуры, MVP
✅ TECHNICAL_SPEC.md — детальная спецификация (API, models, agents)
✅ CLAUDE.md — конфиг для Claude Code (120 строк)

**Total time:** ~6 часов (готово)

---

## Phase 1: Backend Foundation ✅ DONE

### Task 1.1: Project Setup & Database ✅
**Completed:** Session 1

- [x] `mkdir code-review-agent && git init`
- [x] `requirements.txt` (fastapi, sqlalchemy, anthropic, openai, langgraph)
- [x] `.env.example` (all env vars)
- [x] Docker setup (docker-compose.yml with postgres + tests profile)
- [x] `backend/config.py` — pydantic-settings, env_ignore_empty, CORS validator
- [x] `backend/main.py` — FastAPI app, lifespan, health check, WebSocket placeholder
- [x] Migrations 001–003: users, repositories, reviews, findings, agent_executions, audit_log
- [x] `backend/utils/crypto.py` — Fernet encrypt/decrypt
- [x] `backend/utils/webhooks.py` — HMAC-SHA256 signature verification
- [x] 20 tests passing (crypto + webhooks)

**Deliverable:** ✅ Docker-first dev setup, DB, health check at GET /health

---

### Task 1.2: GitHub Integration ✅
**Completed:** Session 2

- [x] `backend/services/github_api.py` — GitHub App JWT auth, installation token cache, paginated PR files, post/update comments
- [x] `backend/services/code_extractor.py` — unified diff → CodeChunk objects, language detection
- [x] `backend/services/analyzer.py` — background task: fetch→extract→orchestrate→persist→post comment
- [x] `backend/routers/github.py` — webhook auto-triggers `run_analysis` after creating review
- [x] `backend/routers/reviews.py` — analyze_review fires asyncio.create_task; post_comment fully wired
- [x] 50 tests passing (+21 new)

**Deliverable:** ✅ Webhook → analysis pipeline wired end-to-end

---

### Task 1.3: LLM Router & Settings ✅
**Completed:** Session 2

- [x] `backend/agents/llm_router.py` — Claude/GPT/Ollama selection, auto-mode, quality scores
- [x] `backend/utils/auth.py` — PBKDF2-SHA256 passwords, JWT create/verify, get_current_user dependency
- [x] `backend/routers/auth.py` — POST /auth/register, /auth/token, /auth/login, GET /auth/me
- [x] `backend/routers/settings.py` — real DB persistence, Fernet-encrypted API keys, test-llm endpoint
- [x] Migration 004: hashed_password column
- [x] 61 tests passing (+11 new)

**Deliverable:** ✅ Full JWT auth + encrypted settings persisted to DB

---

### Task 1.4: Basic Agent (Security) ✅
**Completed:** Session 2

- [x] `backend/agents/security_agent.py` — SQL injection, XSS, hardcoded secrets, weak crypto, IDOR
- [x] `backend/agents/orchestrator.py` — provider-agnostic _call_llm, asyncio.gather parallel dispatch, per-agent timeout+error isolation
- [x] analyzer.py updated to use real run_graph (stub removed)
- [x] 72 tests passing (+11 new)

**Deliverable:** ✅ Security agent + orchestrator wired into analysis pipeline

---

## Phase 2: Multi-Agent Orchestration (Week 2-3)

### Task 2.1: Remaining Agents
**Time:** 2 дня
**Owner:** backend-engineer agent

- [ ] `backend/agents/performance_agent.py` — perf analysis
- [ ] `backend/agents/style_agent.py` — code style analysis
- [ ] `backend/agents/logic_agent.py` — logic error detection
- [ ] Each agent: same structure (prompt, input, output)
- [ ] Test individually

**Deliverable:** All 4 agents implemented

---

### Task 2.2: Parallel Execution (LangGraph)
**Time:** 1.5 дня
**Owner:** backend-engineer agent

- [ ] Update `orchestrator.py` for parallel execution
  - [ ] Nodes for each agent (security, performance, style, logic)
  - [ ] Routes: which agents to run (based on user selection)
  - [ ] Parallel: all agents run concurrently via asyncio
  - [ ] Timeouts: 30s per agent
  - [ ] Gather results from all agents
- [ ] LangGraph state: code context, findings, agent status
- [ ] Test: run all 4 agents in parallel, measure time

**Deliverable:** Multi-agent orchestration working, parallel execution confirmed

---

### Task 2.3: Result Aggregation
**Time:** 1 день
**Owner:** backend-engineer agent

- [ ] `backend/services/result_aggregator.py`
  - [ ] Deduplication: same issue from multiple agents
  - [ ] Ranking: by severity (critical → warning → info)
  - [ ] Grouping: by file path
- [ ] Store findings in DB (with agent_name, severity, line number)
- [ ] Test: verify deduplication works

**Deliverable:** Results properly aggregated and ranked

---

### Task 2.4: PR Comment Generation
**Time:** 1 день
**Owner:** backend-engineer agent

- [ ] `backend/services/pr_commenter.py`
  - [ ] Format findings as markdown
  - [ ] Group by severity
  - [ ] Include code snippets
  - [ ] Add agent metadata + cost + time
- [ ] Endpoint `POST /reviews/{id}/post-comment` calls this
- [ ] Test: post comment to real PR (or mock)

**Deliverable:** Findings formatted and posted to GitHub PR

---

## Phase 3: Dashboard & Frontend (Week 3-4)

### Task 3.1: Dashboard Pages
**Time:** 2 дня
**Owner:** frontend-developer agent

- [ ] `frontend/src/pages/Dashboard.tsx`
  - [ ] Summary cards (total reviews, today, tokens, cost)
  - [ ] Recent reviews table (sortable, filterable)
  - [ ] Stats charts (findings by agent, by severity)
- [ ] `frontend/src/pages/ReviewDetail.tsx`
  - [ ] PR header (title, number, author)
  - [ ] Findings list (grouped by severity)
  - [ ] Code snippets per finding
  - [ ] Agent metadata + timing
- [ ] `frontend/src/pages/Settings.tsx`
  - [ ] LLM selector (Local | Claude | GPT | Auto)
  - [ ] API key inputs (with test buttons)
  - [ ] Ollama host input (with connectivity check)
  - [ ] Agent selection checkboxes

**Deliverable:** All 3 pages functional, styled with Tailwind

---

### Task 3.2: API Integration
**Time:** 1.5 дня
**Owner:** frontend-developer agent

- [ ] API client setup (axios or fetch)
- [ ] `hooks/useApi.ts` — wrapper for API calls with auth
- [ ] `hooks/useSettings.ts` — settings state management (Zustand)
- [ ] `hooks/useReviews.ts` — reviews list state
- [ ] Connect components to API endpoints
- [ ] Error handling + loading states

**Deliverable:** Frontend fully connected to backend

---

### Task 3.3: Real-time Progress
**Time:** 1 день
**Owner:** frontend-developer agent

- [ ] WebSocket setup (during analysis)
- [ ] `hooks/useWebsocket.ts` — connect to backend
- [ ] Real-time agent status updates
  - [ ] Security ✓ | Performance 🔄 | Style ◯ | Logic ◯
  - [ ] Progress bar (estimated time remaining)
- [ ] Auto-refresh dashboard when review complete

**Deliverable:** Real-time progress visible during analysis

---

### Task 3.4: Styling & Polish
**Time:** 1 день
**Owner:** frontend-developer agent

- [ ] Dark mode support
- [ ] Mobile responsive design
- [ ] Loading skeletons
- [ ] Toast notifications (success/error)
- [ ] Empty states (no reviews, no findings)

**Deliverable:** Production-ready UI

---

## Phase 4: Testing & Evaluation (Week 4)

### Task 4.1: Unit Tests
**Time:** 1.5 дня
**Owner:** qa-reviewer agent

- [ ] Backend tests
  - [ ] LLM router: test all paths (Claude, GPT, Local)
  - [ ] GitHub webhook: signature verification
  - [ ] Agent outputs: mock LLM responses, verify parsing
  - [ ] Result aggregator: deduplication, ranking
- [ ] Frontend tests
  - [ ] Components: render tests, props validation
  - [ ] Hooks: API mocking, state updates
  - [ ] Pages: navigation, filtering

**Deliverable:** Unit tests with >80% coverage

---

### Task 4.2: Integration Tests
**Time:** 1.5 дня
**Owner:** qa-reviewer agent

- [ ] End-to-end: webhook → analysis → PR comment
- [ ] LLM routing: test all 3 LLM options (mock APIs)
- [ ] Settings: API key validation, encryption
- [ ] Dashboard: load, filter, view reviews
- [ ] Error cases: timeout, API down, invalid code

**Deliverable:** Integration test suite passing

---

### Task 4.3: Evaluation & Benchmarking
**Time:** 1 день
**Owner:** qa-reviewer agent

- [ ] Create test dataset (20-30 sample PRs with known issues)
- [ ] Run system on test set
- [ ] Measure:
  - [ ] Finding accuracy (vs. manual review)
  - [ ] Recall (% of actual issues found)
  - [ ] False positive rate
  - [ ] Latency (P95 time)
  - [ ] Cost (tokens per review)
- [ ] Document results

**Deliverable:** Evaluation report with metrics

---

## Phase 5: Documentation & Deployment (Week 4-5)

### Task 5.1: Documentation
**Time:** 1 день
**Owner:** backend-engineer agent

- [ ] `README.md` — setup instructions, examples
- [ ] `API.md` — endpoint documentation
- [ ] `ARCHITECTURE.md` — system design diagram
- [ ] `DEPLOYMENT.md` — how to deploy (Docker, Railway, etc.)
- [ ] `CONTRIBUTING.md` — how to add new agents

**Deliverable:** Full documentation

---

### Task 5.2: Docker & Deployment
**Time:** 1.5 дня
**Owner:** backend-engineer agent

- [ ] Dockerfile (FastAPI + PostgreSQL client)
- [ ] docker-compose.yml (backend + postgres + redis optional)
- [ ] `.dockerignore` + `.gitignore`
- [ ] Deploy to Railway or Render
  - [ ] Set env vars
  - [ ] Run migrations
  - [ ] Test in production
- [ ] GitHub Actions CI/CD (tests on push)

**Deliverable:** Production deployment working

---

### Task 5.3: GitHub Repository Setup
**Time:** 0.5 дня
**Owner:** backend-engineer agent

- [ ] `git init && git add && git commit`
- [ ] Push to GitHub (public repo)
- [ ] Add repo description, topics, license (MIT)
- [ ] Configure GitHub Pages (optional, for docs)
- [ ] Add badges (build status, coverage, etc.)

**Deliverable:** Public GitHub repo ready

---

## Timeline Summary

| Phase | Tasks | Duration | Owner |
|-------|-------|----------|-------|
| **0: Prep** | Specs + planning | 6h ✅ | Claude |
| **1: Backend** | Setup, GitHub, LLM, 1 agent | 7 days | backend-engineer |
| **2: Multi-Agent** | 3 more agents, parallel, aggregation, PR comment | 5.5 days | backend-engineer |
| **3: Frontend** | Dashboard, settings, API integration, realtime | 4.5 days | frontend-developer |
| **4: Testing** | Unit tests, integration tests, evaluation | 4 days | qa-reviewer |
| **5: Docs & Deploy** | Documentation, Docker, GitHub | 3 days | backend-engineer |
| **TOTAL** | Full system | ~30 days | All agents |

---

## Resource Allocation

**Suggested Claude Code agent team:**

1. **backend-engineer (Opus)** — All backend tasks (API, agents, DB)
   - Tools: Read, Write, Edit, Bash, Glob
   - Model: Claude Opus 4.6 (complex logic, reasoning)

2. **frontend-developer (Sonnet)** — All frontend tasks (UI, styling, API integration)
   - Tools: Read, Write, Edit, Bash, Glob
   - Model: Claude Sonnet 4.6 (sufficient for UI, cheaper)

3. **qa-reviewer (Sonnet)** — Tests, evaluation, documentation review
   - Tools: Read, Bash, Glob, Grep (NO Write/Edit)
   - Model: Claude Sonnet 4.6
   - Role: Reviewer only, doesn't change code

**Parallel execution:**
- Week 1: All 3 agents work simultaneously (backend setup, frontend setup, test planning)
- Week 2-3: backend-engineer + frontend-developer in parallel
- Week 4: All 3 agents (backend tweaks, frontend polish, testing)
- Week 5: backend-engineer (deployment), documentation

---

## Iteration & Feedback Loop

**Weekly checkpoints:**
- Monday: Review previous week, plan current week
- Wednesday: Sync on blockers, adjust timeline if needed
- Friday: Demo to stakeholders, collect feedback

**Feedback integration:**
- Agent findings reviewed by human
- Adjust prompts/logic based on false positives
- Update TECHNICAL_SPEC if requirements change
- Cascade changes to CLAUDE.md

---

## Success Criteria

✅ MVP complete when:
1. GitHub webhook working (PR opens → analysis triggered)
2. All 4 agents running in parallel
3. Findings posted to PR comment
4. Dashboard shows review history + stats
5. LLM router selects Claude/GPT/Local based on settings
6. Tests passing (unit + integration)
7. Deployed to Railway or similar
8. Documentation complete

**Expected metrics:**
- Finding accuracy: ≥80%
- Review latency: <5 minutes
- Cost: <$0.30 per review
- Uptime: >99% (after launch)

---

## Risk Mitigation

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|-----------|
| LLM API rate limits | Medium | High | Queue + exponential backoff |
| GitHub webhook signature failure | Low | High | Thorough testing, signature verification |
| Agent hallucinations | Medium | Medium | Evaluation framework, human review |
| Database migration issues | Low | High | Test migrations locally first |
| Frontend performance | Low | Low | Lazy loading, caching |
| Deployment failure | Low | Medium | CI/CD tests, rollback plan |

---

## Post-MVP: v2.0 Features (Optional)

Not in MVP scope, but on the roadmap:

- [ ] Custom agent builder (UI for domain-specific agents)
- [ ] Local Ollama support (Qwen2.5-Coder-32B)
- [ ] GPT-5.4 integration
- [ ] Fine-tuned models (train on team patterns)
- [ ] Team collaboration (shared findings)
- [ ] Advanced metrics (quality trends, ROI)
- [ ] VS Code extension
- [ ] Slack notifications
- [ ] Auto-fix suggestions (AI-generated patches)

---

## Claude Code Execution

**To start development in Claude Code:**

1. Copy CLAUDE.md content into Claude Code knowledge
2. Create .claude/agents/ files (backend-engineer, frontend-developer, qa-reviewer)
3. Create .claude/rules/ files (backend, frontend, database)
4. Create .claude/skills/ files (implement-feature, analyze-code)
5. Paste this full development plan in initial prompt
6. Let agents begin Phase 1

**Suggested initial prompt:**

```
You are coordinating a 3-agent team to build a code review system.

Use these documents:
1. PROJECT_IDEA.md (problem, architecture, MVP)
2. TECHNICAL_SPEC.md (detailed API, models, database)
3. CLAUDE.md (orchestration config)
4. DEVELOPMENT_PLAN.md (this file, timeline)

Start with Phase 1, Task 1.1: Project Setup.

Agents:
- backend-engineer (Opus, Python/FastAPI expertise)
- frontend-developer (Sonnet, React/TypeScript expertise)
- qa-reviewer (Sonnet, testing/evaluation)

Work in parallel where possible. Sync daily on blockers.

Begin.
```
