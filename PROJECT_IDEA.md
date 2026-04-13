# PROJECT_IDEA: AI-Powered Code Review Agent

## 1. Проблема
Разработчики тратят 2-4 часа на код-ревью для одного PR. Процесс:
- Читают код вручную (60-90 минут)
- Проверяют на security issues (30-45 минут)
- Анализируют производительность (20-30 минут)
- Пишут комментарии (30-40 минут)

При этом ~25% issues пропускают потому что устают. Лучшие практики нарушаются систематически.

## 2. Решение
Автоматизированная система code review на базе multi-agent AI:

**Поток:**
1. GitHub webhook → PR created/updated
2. Dashboard загружает код автоматически
3. User выбирает какие агенты запустить (Security, Performance, Style, etc.)
4. Агенты работают параллельно над PR
5. Результаты выводятся:
   - В dashboard (structured findings)
   - В PR comment (GitHub)
6. User может выбрать модель (Claude, GPT, local Qwen) через API ключ в настройках

**Время:** 3-5 минут вместо 2-4 часов

## 3. Почему сейчас
- Frontier coding models converged: Claude Opus 4.6 (80.8%) и Gemini 3.1 Pro (80.6%) достаточно точны на SWE-bench
- Open-source модели (Qwen2.5-Coder-32B, DeepSeek-V3.2) могут работать локально
- GitHub Actions + webhooks надёжны
- Multi-agent разработка стала mainstream (LangGraph, CrewAI, AutoGen)

## 4. Целевая аудитория
**Primary:** Mid-level команды (10-50 разработчиков)
- Проблема: много PR в день, ревьюеры устают, качество падает
- Current: используют Copilot Chat, ChatGPT, manual review
- Need: автоматический первый pass review + структурированные findings

**Secondary:** Open-source поддерживающие
- Need: быстрая обратная связь на community PR
- Current: ждут, когда maintainer найдёт время

**Tertiary:** Solo devs / freelancers
- Need: второе мнение, лучшие практики
- Current: ничего, пушат как есть

## 5. Архитектура

```
┌─────────────────────────────────────────────┐
│  GitHub Integration Layer                   │
│  ├─ Webhook receiver (PR created/updated)   │
│  └─ API (fetch code, post comments)         │
└────────────┬────────────────────────────────┘
             │
┌────────────▼────────────────────────────────┐
│  Backend (FastAPI + LangGraph)              │
│  ├─ Orchestrator (webhook processor)        │
│  ├─ Agent Router (select agents)            │
│  ├─ LLM Router (Claude/GPT/Local)           │
│  └─ Storage (PostgreSQL + pgvector)         │
└────────────┬────────────────────────────────┘
             │
    ┌────────┴─────────┬──────────────┐
    │                  │              │
┌───▼────┐ ┌──────┬───┐ ┌───────┐ ┌──▼──────┐
│Security│ │Style │Perf│ │Logic  │ │ Custom  │
│Agent   │ │Agent │Agent│ │Agent  │ │Agents   │
└────────┘ └──────┴────┘ └───────┘ └─────────┘
    │           (work parallel)        │
    └───────────┬──────────────────────┘
                │
┌───────────────▼──────────────────────┐
│  Result Aggregator                   │
│  ├─ Deduplicate findings              │
│  ├─ Rank by severity                  │
│  └─ Format for dashboard + PR         │
└───────────────┬──────────────────────┘
                │
        ┌───────┴────────┐
        │                │
    ┌───▼────┐    ┌─────▼────┐
    │Dashboard│    │GitHub PR │
    │(React)  │    │Comment   │
    └─────────┘    └──────────┘
```

**Layers:**
- **Integration:** GitHub webhooks + API (fastapi-github)
- **Orchestration:** LangGraph для управления агентами (parallel execution)
- **Agents:** Security, Performance, Style, Logic, Custom (выбирает user)
- **LLM Routing:** Local (Ollama) vs Claude (API) vs GPT (API) based on settings
- **Storage:** PostgreSQL для истории, pgvector для embeddings finding
- **Frontend:** React dashboard (settings, history, realtime results)

## 6. Стек
**Backend:**
- FastAPI (API + webhooks)
- LangGraph (multi-agent orchestration)
- PostgreSQL (review history, findings)
- Ollama (local LLM inference, optional)
- Anthropic SDK / OpenAI SDK (cloud LLMs)

**Frontend:**
- React 19 + TypeScript
- TailwindCSS
- Zustand (state management)
- Websockets (realtime agent progress)

**Infrastructure:**
- Docker (containerization)
- GitHub Actions (CI/CD)
- Railway / Render (deployment)
- ngrok / webhook.site (local testing)

**LLM Stack:**
- Claude Opus 4.6 (primary, best for code)
- GPT-5.4 (fallback, cheaper for some tasks)
- Qwen2.5-Coder-32B via Ollama (local, free)

## 7. Конкуренты

| Конкурент | Что делает | Чего не хватает | Наше преимущество |
|-----------|-----------|-----------------|------------------|
| GitHub Copilot | AI suggestions в IDE | Нет PR review, нет parallel agents | Parallel multi-agent + PR integration |
| DeepCode / Snyk | Security scanning | Только security, не style/perf | Multi-agent для всех аспектов |
| ReviewNB | Notebook review | Только notebooks | GitHub native + configurable agents |
| PR Review AI (Claude) | Генерирует review | UI слабый, no agent selection | Rich dashboard + flexible agents + local |
| Manual linters | Fast, reliable | Не понимают контекст | AI-понимание + human approval flow |

## 8. MVP (фаза 1)

**Функции:**
- ✅ GitHub webhook integration
- ✅ 3 основных агента: Security, Performance, Style
- ✅ Claude Opus 4.6 как основная модель
- ✅ Dashboard с results
- ✅ PR comment generation
- ✅ Settings для API ключей
- ✅ Basic history (last 10 reviews)

**Исключено из MVP:**
- ❌ Local Ollama support (добавим в v1.1)
- ❌ GPT integration (добавим в v1.1)
- ❌ Custom agents builder (v2.0)
- ❌ Team collaboration (v2.0)
- ❌ Metrics / evaluation dashboard (v2.0)

**Users:** 5-10 beta users (friends + open-source maintainers)

## 9. v2.0+ (фаза 2-3)

**Features:**
- Local LLM support (Ollama + Qwen2.5-Coder-32B)
- GPT-5.4 integration
- Custom agent builder UI (no-code)
- Agent selection checkboxes (Security: on/off, Perf: on/off, etc.)
- Advanced findings (related issues, suggestions for fixes)
- Team collaboration (shared findings, comments)
- Metrics dashboard (review quality, findings distribution)
- Fine-tuned domain-specific agents (e.g., React components, FastAPI)

## 10. Монетизация

**Tier 1: Free**
- 10 reviews/month
- Cloud LLM (Claude, shared quota)
- 3 basic agents
- Dashboard only

**Tier 2: Pro ($19/month)**
- Unlimited reviews
- Cloud LLMs (Claude + GPT)
- All 6 agents (including Logic + Custom)
- Dashboard + PR comments
- 30-day history

**Tier 3: Enterprise (custom)**
- Self-hosted option (local LLM)
- Custom agents
- Private GitHub Enterprise support
- Team collaboration
- SLA + support

**Gating:**
- Free: 10 reviews (hard limit)
- Pro: API ключ required (they pay for LLM)
- Enterprise: contact sales

## 11. Модули системы

```
1. github-integration
   Input: GitHub webhook (PR event)
   Output: Code diff, PR metadata
   
2. code-extractor
   Input: Repo URL + PR number
   Output: Changed files, full context
   
3. agent-orchestrator (LangGraph)
   Input: Code + selected agents
   Output: Agent tasks distributed
   
4. security-agent
   Input: Code
   Output: {issues: [{type, line, severity, suggestion}]}
   
5. performance-agent
   Input: Code
   Output: {issues: [{type, line, impact, suggestion}]}
   
6. style-agent
   Input: Code
   Output: {issues: [{type, line, standard, suggestion}]}
   
7. logic-agent
   Input: Code + context
   Output: {issues: [{type, line, logic_error, suggestion}]}
   
8. custom-agent (v2)
   Input: Code + custom prompt
   Output: Custom findings
   
9. result-aggregator
   Input: All agent outputs
   Output: Deduplicated, ranked findings
   
10. pr-commenter
    Input: Findings
    Output: GitHub PR comment (formatted)
    
11. dashboard
    Input: User actions
    Output: UI (settings, history, realtime)
    
12. settings-manager
    Input: API keys (Claude, GPT, Ollama)
    Output: LLM router config
```

**Зависимости:**
- github-integration → code-extractor → agent-orchestrator
- agent-orchestrator → [security, performance, style, logic, custom] agents
- All agents → result-aggregator → [pr-commenter, dashboard]
- settings-manager → LLM router (inside agent-orchestrator)

## 12. Данные / Модели

**GitHub side:**
- Repository: owner, name, url
- PullRequest: id, number, title, body, head_sha, base_sha, author
- File: path, language (inferred from extension)
- Diff: old_code, new_code, hunks (line ranges)

**Our side:**
- Review: id, pr_id, repo_id, status (pending/done), created_at, completed_at
- Finding: id, review_id, type (security/perf/style/logic/custom), severity (critical/warning/info), file, line, message, suggestion
- AgentExecution: review_id, agent_name, status, started_at, completed_at, tokens_used, cost
- UserSettings: user_id, api_key_claude, api_key_gpt, ollama_host, selected_agents, created_at
- ReviewHistory: user_id, review_id, repo_name, pr_number, findings_count, generated_at

## 13. Техдетали

**Repo structure:**
```
code-review-agent/
├── CLAUDE.md (120 строк)
├── SPEC_TEMPLATE.md
├── .claude/
│   ├── agents/ (security, performance, style, logic, custom)
│   ├── rules/ (backend, frontend, etc.)
│   └── skills/ (implement-agent, analyze-code, etc.)
├── backend/
│   ├── main.py (FastAPI app)
│   ├── agents/ (LangGraph agents)
│   ├── routers/ (GitHub, settings, reviews)
│   └── models/ (SQLAlchemy ORM)
├── frontend/
│   ├── src/
│   │   ├── pages/ (Dashboard, Settings)
│   │   ├── components/ (FindingsTable, AgentStatus)
│   │   └── hooks/ (useWebsocket, useSettings)
│   └── package.json
├── supabase/
│   ├── migrations/ (SQL)
│   └── functions/ (Edge Functions if needed)
├── docker-compose.yml
└── README.md
```

**AI Pipeline:**
- GitHub webhook → FastAPI endpoint
- Extract code diff + context
- LangGraph orchestrator selects agents based on user settings
- Each agent gets code + context (via LLM RoutingChoice: Claude/GPT/Ollama)
- Agents run parallel (AsyncIO)
- Results aggregated + deduplicated
- Output: structured findings (JSON) + formatted PR comment

**Key decision: LLM Router**
- If user set Claude API key → use Claude Opus 4.6
- If user set GPT API key → use GPT-5.4
- If user enabled local + has Ollama → use Qwen2.5-Coder-32B
- Fallback priority: Claude > GPT > Local

## 14. MVP Timeline
- Week 1: Setup + GitHub integration + basic agent
- Week 2: Add 3 agents (security, perf, style) + aggregator
- Week 3: Dashboard + PR comment + settings
- Week 4: Testing + documentation + deployment

## 15. Success metrics (для evaluation)
- **Finding accuracy:** % findings that humans agree with (RAGAS-like)
- **Finding recall:** % real issues found by agents
- **False positive rate:** % findings that are actually non-issues
- **Review latency:** P95 time from webhook to PR comment (target: <5 min)
- **Cost per review:** tokens used → $ (optimize)
- **User adoption:** beta users, reviews per day, return rate

**Baseline:** Manual code review = 100% accuracy + 120 min latency + high cost (human hours)
**Target:** 85%+ accuracy + 5 min latency + 90% cost reduction
