# 🚀 Ready to Run in Claude Code

Все документы готовы. Ниже инструкции как запустить разработку.

---

## 📦 Что ты получил

### Основные документы (в outputs/):
1. **PROJECT_IDEA.md** (450 строк) — что строим и почему
2. **TECHNICAL_SPEC.md** (800 строк) — как строим (API, DB, agents)
3. **CLAUDE.md** (120 строк) — конфиг для Claude Code
4. **DEVELOPMENT_PLAN.md** (400 строк) — 30-день timeline
5. **SPEC_FIRST_EVALUATION.md** (300 строк) — оценка методологии

### Агенты (.claude/agents/):
1. **backend-engineer.md** (300 строк) — FastAPI, LangGraph, PostgreSQL
2. **frontend-developer.md** (250 строк) — React 19, TypeScript, TailwindCSS
3. **qa-reviewer.md** (200 строк) — tests, code review, evaluation

### Правила (.claude/rules/):
1. **backend-rules.md** (250 строк) — async, types, errors, testing
2. **frontend-rules.md** (300 строк) — React, TypeScript, Tailwind, testing

### Навыки (.claude/skills/):
1. **implement-agent.md** (400 строк) — как добавлять новые agents

---

## 🎯 Как запустить разработку

### Option 1: Быстрый запуск (рекомендуется)

**Step 1:** Открой Claude Code (terminal или web)

**Step 2:** Создай новую session

**Step 3:** Загрузи все документы в knowledge:
```bash
# Copy all files to working directory
cp /mnt/user-data/outputs/* .
cp -r /mnt/user-data/outputs/.claude .
```

**Step 4:** Начальный промпт для Claude Code:

```
You are orchestrating a 3-agent team to build an AI-powered code review system.

CRITICAL: Load these files into your knowledge FIRST:
1. PROJECT_IDEA.md (understand what to build)
2. TECHNICAL_SPEC.md (understand how to build)
3. CLAUDE.md (understand architecture + your roles)

Agent Configuration:
- .claude/agents/backend-engineer.md — Your backend specialist
- .claude/agents/frontend-developer.md — Your frontend specialist
- .claude/agents/qa-reviewer.md — Your QA specialist

Rules (apply to code):
- .claude/rules/backend-rules.md (glob: backend/**/*.py)
- .claude/rules/frontend-rules.md (glob: frontend/src/**/*.tsx)

Skills (for reference):
- .claude/skills/implement-agent.md (how to add new agents)

Execution Plan:
1. Read all documents above
2. Understand the system architecture
3. Create project structure (directories, files)
4. Start DEVELOPMENT_PLAN Phase 1, Task 1.1: Project Setup & Database
5. Work in parallel: backend-engineer + frontend-developer
6. Report status daily

KEY INSTRUCTIONS:
- backend-engineer: Use Opus model (complex logic)
- frontend-developer: Use Sonnet model (UI work, cheaper)
- qa-reviewer: Use Sonnet, Read-only (no Write/Edit), write test specs
- Work async/parallel where possible
- Commit code after each task
- Each task has deliverables - verify them before marking done

Begin with Phase 1, Task 1.1.
```

**Step 5:** Let agents work!

---

### Option 2: Local Setup (if you want to work on it locally first)

```bash
# Clone/create repo
mkdir code-review-agent && cd code-review-agent
git init

# Create structure
mkdir backend frontend supabase .claude/{agents,rules,skills}

# Copy all spec files
cp /mnt/user-data/outputs/*.md .
cp -r /mnt/user-data/outputs/.claude .

# Start backend manually
python -m venv venv
source venv/bin/activate
pip install fastapi sqlalchemy anthropic langgraph openai

# Or in Claude Code: paste the complete flow above
```

---

## 📋 Timeline

**Phase 1 (Week 1):** Backend foundation
- Project setup
- GitHub integration
- LLM router
- First agent (Security)
- **Expected:** Webhook receiving + security analysis working

**Phase 2 (Week 2):** Multi-agent orchestration
- Remaining agents (Perf, Style, Logic)
- Parallel execution (LangGraph)
- Result aggregation
- PR comments
- **Expected:** Full agent pipeline working

**Phase 3 (Week 3):** Frontend + Dashboard
- Dashboard page
- ReviewDetail page
- Settings page
- API integration
- **Expected:** Complete UI, fully functional

**Phase 4 (Week 4):** Testing + Evaluation
- Unit tests (>80% coverage)
- Integration tests
- Evaluation metrics
- **Expected:** All tests passing, metrics documented

**Phase 5 (Week 4-5):** Documentation + Deploy
- Complete documentation
- Docker setup
- Deploy to Railway/Render
- **Expected:** Production-ready system

**Total:** 30 days, 3 agents, multi-phase development

---

## ✅ Success Criteria (MVP Done When)

- [ ] GitHub webhook working (PR → analysis triggered)
- [ ] 4 agents running in parallel
- [ ] Findings posted to PR as comment
- [ ] Dashboard shows reviews + history
- [ ] LLM selection (Claude/GPT/Local via settings)
- [ ] All tests passing (unit + integration)
- [ ] Deployed to production
- [ ] Documentation complete

**Metrics targets:**
- Finding accuracy: ≥80%
- Review latency: <5 minutes
- Cost: <$0.30 per review

---

## 🔧 Configuration

### Environment Variables (needed for Claude Code)

Create `.env`:
```bash
# GitHub
GITHUB_APP_ID=your_app_id
GITHUB_APP_PRIVATE_KEY=your_key
GITHUB_CLIENT_ID=your_client_id
GITHUB_CLIENT_SECRET=your_secret
GITHUB_WEBHOOK_SECRET=your_webhook_secret

# Database
DATABASE_URL=postgresql://user:pass@localhost/code_review_db

# LLM APIs
ANTHROPIC_API_KEY=sk-ant-...
OPENAI_API_KEY=sk-...
OLLAMA_HOST=http://localhost:11434

# JWT
JWT_SECRET=random_secret_key

# Stripe (optional, for v2.0)
STRIPE_API_KEY=sk_live_...
```

### Database Setup

```bash
# Start PostgreSQL
docker-compose up postgres

# Create database
psql postgresql://localhost/code_review_db -c "CREATE DATABASE code_review_db"

# Run migrations (backend-engineer will create these)
psql -f supabase/migrations/001_initial_schema.sql
```

---

## 📖 Document Map

**For understanding the project:**
1. Start with **PROJECT_IDEA.md** (big picture)
2. Deep dive with **TECHNICAL_SPEC.md** (implementation details)

**For running agents:**
1. **CLAUDE.md** — architecture + your roles
2. **.claude/agents/[your-agent].md** — your specific instructions
3. **.claude/rules/[relevant-rules].md** — code standards to follow

**For adding features:**
1. **DEVELOPMENT_PLAN.md** — timeline + next steps
2. **.claude/skills/implement-agent.md** — how to extend system

**For evaluation:**
1. **SPEC_FIRST_EVALUATION.md** — methodology review + success metrics

---

## 🎓 How Agents Work Together

```
GitHub Webhook
      ↓
backend-engineer receives PR
      ↓
Extracts code + creates review record
      ↓
Calls orchestrator with selected agents
      ↓
Parallel execution:
  • security-agent → finds vulnerabilities
  • performance-agent → finds bottlenecks
  • style-agent → finds style issues
  • logic-agent → finds bugs
      ↓
result-aggregator dedupes + ranks findings
      ↓
backend-engineer posts comment to PR
      ↓
frontend-developer displays in dashboard
      ↓
qa-reviewer checks quality + accuracy
```

---

## 🚨 Important Notes

### For backend-engineer:
- Use async/await everywhere (FastAPI + LangGraph require it)
- Type hints on all functions (TypeScript for frontend)
- RLS at database level (security)
- All LLM calls through llm_router (flexibility)
- Test each module (Unit tests)

### For frontend-developer:
- TailwindCSS ONLY (no CSS files)
- React hooks (no class components)
- TypeScript strict mode
- All API calls through useApi hook
- Component tests for each component

### For qa-reviewer:
- NO Write/Edit tools (only Read, Bash, Grep)
- Check coverage >80%
- Run integration tests
- Measure evaluation metrics
- Report findings, don't fix code

---

## 📞 Getting Help

If agents get stuck:

1. **Check TECHNICAL_SPEC.md** for API specs
2. **Check DEVELOPMENT_PLAN.md** for current task definition
3. **Check relevant .claude/rules/** for code standards
4. **Ask for clarification** in prompt (don't assume)
5. **Document blockers** for human review

---

## 🎯 First 24 Hours

**What should be done:**
- [ ] Project structure created
- [ ] PostgreSQL running
- [ ] requirements.txt + package.json installed
- [ ] First API endpoint working (POST /reviews)
- [ ] GitHub webhook signature verification working
- [ ] Able to receive PR events from GitHub

**What you should see:**
```
✓ Backend running: uvicorn backend.main:app --reload
✓ Frontend running: npm run dev
✓ Database ready: 5 tables created (users, reviews, findings, etc.)
✓ GitHub webhook: able to receive test events
✓ Basic API: curl http://localhost:8000/api/reviews → 401 (no auth, expected)
```

---

## 📊 Metrics Dashboard (Phase 4)

When evaluation starts, track:

```
✓ Finding Accuracy: % findings humans agree with (target: ≥80%)
✓ Finding Recall: % actual issues caught (target: ≥75%)
✓ False Positives: % non-issues flagged (target: <15%)
✓ Review Latency: P95 time webhook→comment (target: <5 min)
✓ Cost Per Review: tokens used → $ (target: <$0.30)
✓ Test Coverage: % code covered by tests (target: ≥80%)
```

---

## 🎉 Ready?

**All documentation is prepared.**

You have:
- ✅ 5 core documents (2000+ lines)
- ✅ 3 agent prompts (750 lines)
- ✅ 2 rule sets (550 lines)
- ✅ 1 skill guide (400 lines)
- ✅ 30-day timeline
- ✅ Success criteria

**Next step:** Open Claude Code and paste the "Быстрый запуск" prompt above.

**Expected outcome:** Full-stack code review agent in 4-5 weeks.

---

**Good luck! 🚀**
