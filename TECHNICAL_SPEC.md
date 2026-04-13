# TECHNICAL SPECIFICATION: AI-Powered Code Review Agent

## 1. System Overview

Multi-agent code review system orchestrated via LangGraph. Each agent specializes in analyzing code from different perspectives (security, performance, style, logic). Results are aggregated and presented in dashboard + GitHub PR comments.

**Core components:**
- GitHub Integration: webhook receiver + API caller
- Agent Orchestrator: LangGraph-based parallel execution
- LLM Router: selects Claude/GPT/Local based on user settings
- Dashboard: React frontend for results + settings
- Storage: PostgreSQL for history + findings

---

## 2. Data Models

### 2.1 Core Tables

#### users
```sql
id: uuid (PK)
email: text (UNIQUE NOT NULL)
username: text (UNIQUE NOT NULL)
plan: text (DEFAULT 'free') -- 'free', 'pro', 'enterprise'
api_key_claude: text (encrypted, nullable)
api_key_gpt: text (encrypted, nullable)
ollama_enabled: boolean (DEFAULT false)
ollama_host: text (nullable) -- 'http://localhost:11434'
created_at: timestamptz (DEFAULT now())
updated_at: timestamptz (DEFAULT now())

RLS:
  SELECT: auth.uid() = id
  UPDATE: auth.uid() = id
```

#### repositories
```sql
id: uuid (PK)
user_id: uuid (FK users.id)
github_repo_owner: text (NOT NULL)
github_repo_name: text (NOT NULL)
github_repo_url: text (NOT NULL) -- 'https://github.com/owner/name'
github_installation_id: bigint (for GitHub App)
webhook_secret: text (encrypted)
enabled: boolean (DEFAULT true)
created_at: timestamptz (DEFAULT now())

RLS:
  SELECT: auth.uid() = user_id
  UPDATE: auth.uid() = user_id
  
UNIQUE(user_id, github_repo_owner, github_repo_name)
```

#### reviews
```sql
id: uuid (PK)
user_id: uuid (FK users.id)
repo_id: uuid (FK repositories.id)
github_pr_number: integer (NOT NULL)
github_pr_title: text
head_sha: text (commit hash of PR)
base_sha: text (base branch commit)
status: text (DEFAULT 'pending') -- 'pending', 'analyzing', 'done', 'error'
error_message: text (nullable)
selected_agents: jsonb (e.g. '["security", "performance", "style"]')
lm_used: text -- 'claude', 'gpt', 'local'
total_findings: integer (DEFAULT 0)
tokens_input: integer (DEFAULT 0)
tokens_output: integer (DEFAULT 0)
estimated_cost: decimal (DEFAULT 0)
pr_comment_id: bigint (nullable, GitHub comment ID)
pr_comment_posted: boolean (DEFAULT false)
created_at: timestamptz (DEFAULT now())
completed_at: timestamptz (nullable)

RLS:
  SELECT: auth.uid() = user_id
  UPDATE: auth.uid() = user_id AND status IN ('pending', 'analyzing')
```

#### findings
```sql
id: uuid (PK)
review_id: uuid (FK reviews.id)
agent_name: text (NOT NULL) -- 'security', 'performance', 'style', 'logic', 'custom'
finding_type: text (NOT NULL) -- e.g. 'sql_injection', 'unused_variable', 'naming_convention'
severity: text (NOT NULL) -- 'critical', 'warning', 'info'
file_path: text (NOT NULL)
line_number: integer (NOT NULL)
message: text (NOT NULL) -- human readable
suggestion: text (nullable)
code_snippet: text (nullable, max 500 chars)
category: text -- 'security', 'performance', 'style', 'logic'
is_duplicate: boolean (DEFAULT false) -- if same finding from multiple agents
created_at: timestamptz (DEFAULT now())

RLS:
  SELECT: auth.uid() = (SELECT user_id FROM reviews WHERE id = review_id)
  
INDEX(review_id, severity)
INDEX(file_path, line_number)
```

#### agent_executions
```sql
id: uuid (PK)
review_id: uuid (FK reviews.id)
agent_name: text (NOT NULL)
status: text (DEFAULT 'pending') -- 'pending', 'running', 'done', 'error'
started_at: timestamptz (nullable)
completed_at: timestamptz (nullable)
tokens_input: integer (DEFAULT 0)
tokens_output: integer (DEFAULT 0)
findings_count: integer (DEFAULT 0)
error_message: text (nullable)

RLS:
  SELECT: auth.uid() = (SELECT user_id FROM reviews WHERE id = review_id)
```

#### audit_log
```sql
id: uuid (PK)
user_id: uuid (FK users.id)
action: text -- 'created_review', 'updated_settings', 'posted_comment'
resource_type: text -- 'review', 'settings', 'pr'
resource_id: text
metadata: jsonb (optional context)
created_at: timestamptz (DEFAULT now())

RLS:
  SELECT: auth.uid() = user_id
```

---

## 3. API Specification

### 3.1 GitHub Integration

#### POST /github/webhook
Receives GitHub webhook events (PR opened/updated).

**Request:**
```json
{
  "action": "opened|synchronize",
  "pull_request": {
    "number": 123,
    "title": "Add new feature",
    "head": { "sha": "abc123..." },
    "base": { "sha": "def456..." },
    "user": { "login": "username" }
  },
  "repository": {
    "owner": { "login": "org" },
    "name": "repo-name",
    "full_name": "org/repo-name"
  }
}
```

**Flow:**
1. Verify webhook signature (GitHub secret)
2. Find repository in DB (user_id via GitHub App installation)
3. Create review record (status='pending')
4. Fetch PR code diff via GitHub API
5. Call `/reviews/{id}/analyze` async
6. Return 202 Accepted

**Response:** `{ "review_id": "uuid", "status": "pending" }`

**Status codes:**
- 202: Webhook received, analysis queued
- 401: Invalid signature
- 404: Repository not configured
- 500: Server error

---

#### POST /reviews
Create manual review (user pastes code or links to PR).

**Request:**
```json
{
  "repo_id": "uuid",
  "github_pr_number": 123,
  "selected_agents": ["security", "performance", "style"],
  "code_diff": "...",
  "context": "optional additional context"
}
```

**Response:**
```json
{
  "review_id": "uuid",
  "status": "pending",
  "created_at": "2026-04-13T..."
}
```

---

#### GET /reviews/{id}
Get review status and results.

**Response:**
```json
{
  "id": "uuid",
  "status": "done|pending|analyzing",
  "findings": [
    {
      "id": "uuid",
      "agent_name": "security",
      "severity": "critical",
      "file_path": "src/api.py",
      "line_number": 42,
      "message": "SQL injection vulnerability in query",
      "suggestion": "Use parameterized queries",
      "code_snippet": "query = f\"SELECT * FROM users WHERE id={user_id}\""
    }
  ],
  "agent_executions": [
    {
      "agent_name": "security",
      "status": "done",
      "findings_count": 3,
      "completed_at": "2026-04-13T..."
    }
  ],
  "total_findings": 3,
  "tokens_used": 4250,
  "estimated_cost": 0.15,
  "completed_at": "2026-04-13T..."
}
```

---

#### POST /reviews/{id}/analyze
Start analysis for pending review.

**Query params:**
- `force_agents`: "security,performance,style" (override user default)

**Response:** `{ "status": "analyzing" }`

---

#### POST /reviews/{id}/post-comment
Post findings to GitHub PR as comment.

**Request:**
```json
{
  "format": "critical_first|by_file|by_agent",
  "include_agent_names": true
}
```

**Response:**
```json
{
  "comment_id": 9876543,
  "url": "https://github.com/owner/repo/pull/123#issuecomment-9876543",
  "posted_at": "2026-04-13T..."
}
```

---

### 3.2 Settings & LLM Configuration

#### GET /settings
Get user's current LLM configuration.

**Response:**
```json
{
  "plan": "pro",
  "api_key_claude_set": true,
  "api_key_gpt_set": false,
  "ollama_enabled": true,
  "ollama_host": "http://localhost:11434",
  "default_agents": ["security", "performance", "style"],
  "lm_preference": "claude" | "gpt" | "local"
}
```

---

#### PUT /settings
Update LLM settings.

**Request:**
```json
{
  "api_key_claude": "sk-...",
  "api_key_gpt": "sk-...",
  "ollama_enabled": true,
  "ollama_host": "http://localhost:11434",
  "default_agents": ["security", "performance"],
  "lm_preference": "claude|gpt|local|auto"
}
```

**Validation:**
- API keys: verify with LLM provider (make test call)
- Ollama host: test connectivity
- Agents: must be known agent names

**Response:**
```json
{
  "updated": true,
  "warnings": ["GPT API key invalid", "Ollama unreachable"]
}
```

---

#### POST /settings/test-llm
Test which LLM is currently configured.

**Response:**
```json
{
  "claude_available": true,
  "gpt_available": false,
  "ollama_available": true,
  "selected": "claude",
  "models": {
    "claude": "claude-opus-4-6",
    "ollama": "qwen2.5-coder:32b"
  }
}
```

---

### 3.3 History & Dashboard

#### GET /reviews
List user's reviews (paginated).

**Query params:**
- `repo_id`: filter by repo (optional)
- `status`: "done|pending|error" (optional)
- `limit`: default 20, max 100
- `offset`: pagination

**Response:**
```json
{
  "reviews": [
    {
      "id": "uuid",
      "repo": "owner/repo",
      "pr_number": 123,
      "status": "done",
      "total_findings": 3,
      "created_at": "2026-04-13T...",
      "completed_at": "2026-04-13T..."
    }
  ],
  "total": 42,
  "limit": 20,
  "offset": 0
}
```

---

#### GET /dashboard/stats
Dashboard summary.

**Response:**
```json
{
  "total_reviews": 42,
  "reviews_today": 3,
  "findings_by_severity": {
    "critical": 5,
    "warning": 18,
    "info": 42
  },
  "findings_by_agent": {
    "security": 15,
    "performance": 12,
    "style": 20,
    "logic": 10
  },
  "top_issues": [
    { "type": "unused_variable", "count": 8 },
    { "type": "naming_convention", "count": 7 }
  ],
  "avg_review_time_seconds": 145,
  "tokens_used_this_month": 425000,
  "estimated_cost_this_month": 2.15,
  "plan_remaining": "25/50 reviews"
}
```

---

## 4. Agent Specifications

Each agent is a specialized unit within LangGraph orchestration.

### 4.1 Security Agent

**Purpose:** Find security vulnerabilities (injection, auth, crypto, data exposure)

**Input:**
```python
{
  "code": str,           # full changed code
  "language": str,       # 'python', 'javascript', 'go', etc.
  "context": str,        # file path, dependencies
  "severity_threshold": str  # 'critical' | 'warning' | 'info'
}
```

**Output:**
```python
{
  "findings": [
    {
      "type": "sql_injection",
      "line": 42,
      "severity": "critical",
      "message": "String interpolation in SQL query",
      "suggestion": "Use parameterized queries",
      "code_snippet": "..."
    }
  ]
}
```

**Agent instructions (for LLM):**
- Look for: SQL injection, XSS, CSRF, hardcoded secrets, weak crypto, auth bypass
- Check: third-party library vulnerabilities
- Report: line number + exact code snippet + CVSS severity
- Avoid: style issues, non-security problems

**Model:** Claude Opus 4.6 (best for security reasoning)

---

### 4.2 Performance Agent

**Purpose:** Find performance bottlenecks (N+1 queries, inefficient algorithms, memory leaks)

**Input:**
```python
{
  "code": str,
  "language": str,
  "context": {
    "database": str,  # 'postgresql', 'mongodb'
    "framework": str  # 'fastapi', 'django', 'express'
  }
}
```

**Output:**
```python
{
  "findings": [
    {
      "type": "n_plus_one",
      "line": 28,
      "severity": "warning",
      "message": "N+1 query in loop",
      "suggestion": "Prefetch relations or use batch query",
      "impact": "High latency on large datasets"
    }
  ]
}
```

**Agent instructions:**
- Look for: N+1 queries, inefficient algorithms (O(n²)), unused variables, large data copying
- Check: database queries within loops
- Estimate: impact (high/medium/low)
- Avoid: stylistic things, security (unless related to perf DDoS)

**Model:** Claude Opus 4.6

---

### 4.3 Style Agent

**Purpose:** Code style, naming, conventions, readability

**Input:**
```python
{
  "code": str,
  "language": str,
  "style_guide": str  # 'pep8', 'airbnb', 'google', auto-detect
}
```

**Output:**
```python
{
  "findings": [
    {
      "type": "naming_convention",
      "line": 5,
      "severity": "info",
      "message": "Variable names should be snake_case",
      "suggestion": "Rename 'userName' to 'user_name'",
      "standard": "PEP 8"
    }
  ]
}
```

**Agent instructions:**
- Look for: naming (snake_case vs camelCase), line length, indentation, unused imports
- Check: docstrings, type hints, consistency
- Follow: detected style guide (auto-detect from existing code)
- Avoid: security/perf, logic errors

**Model:** Claude Sonnet 4.6 (cheaper, sufficient for style)

---

### 4.4 Logic Agent

**Purpose:** Logical errors, edge cases, incorrect implementations

**Input:**
```python
{
  "code": str,
  "language": str,
  "context": str,  # business logic description
  "related_files": [str]  # imports, dependencies
}
```

**Output:**
```python
{
  "findings": [
    {
      "type": "off_by_one",
      "line": 34,
      "severity": "warning",
      "message": "Loop bounds might be wrong",
      "suggestion": "Check: should it be range(n-1) or range(n)?",
      "logic_error": "May skip last item or crash on boundary"
    }
  ]
}
```

**Agent instructions:**
- Look for: logic errors, off-by-one bugs, null checks, type mismatches
- Check: boundary conditions, error handling, exception safety
- Consider: business logic from context
- Avoid: style (unless affects logic clarity)

**Model:** Claude Opus 4.6 (needs deep reasoning)

---

### 4.5 Custom Agent (v2.0)

**Purpose:** User-defined analysis (domain-specific, team-specific)

**Input:**
```python
{
  "code": str,
  "custom_prompt": str,  # user's instructions
  "context": str
}
```

**Output:**
```python
{
  "findings": [custom findings]
}
```

**User example custom prompts:**
- "Check for React hooks violations (eslint-plugin-react-hooks rules)"
- "Find places where we're not using our custom logger"
- "Check if error handling follows our standard pattern"

---

## 5. Agent Orchestration (LangGraph)

```
User selects agents (Security, Performance, Style, Logic)
         │
         ▼
  LLM Router decides: Claude? GPT? Local?
         │
         ▼
  Orchestrator.run():
  ├─ Code extraction (parse diff)
  ├─ Context gathering (lang, framework, style guide)
  ├─ Parallel agent tasks:
  │  ├─ Task(security_agent, code, context) → Promise
  │  ├─ Task(performance_agent, code, context) → Promise
  │  ├─ Task(style_agent, code, context) → Promise
  │  └─ Task(logic_agent, code, context) → Promise
  │
  └─ gather_results() → aggregate findings
         │
         ▼
  Result aggregator:
  ├─ Deduplicate (same issue from multiple agents)
  ├─ Rank by severity (critical → warning → info)
  ├─ Group by file
  └─ Return structured findings

  Findings → {Dashboard, PR comment}
```

**Parallel execution:** All agents run concurrently (AsyncIO + LangGraph async)

**Timeout:** Each agent max 30 seconds (fallback to partial results)

**Cost tracking:** Each agent logs tokens used (for billing)

---

## 6. LLM Router

**Decision logic:**

```python
def select_llm(user_settings):
    # Priority: user preference > available credentials
    
    if user_settings.lm_preference == 'local' and user_settings.ollama_enabled:
        return OllamaLocal(host=user_settings.ollama_host)
    
    if user_settings.lm_preference == 'claude' and user_settings.api_key_claude:
        return ClaudeOpus(key=user_settings.api_key_claude)
    
    if user_settings.lm_preference == 'gpt' and user_settings.api_key_gpt:
        return GPTAPI(key=user_settings.api_key_gpt)
    
    # Auto mode: choose best available
    if user_settings.lm_preference == 'auto':
        available = []
        if user_settings.api_key_claude:
            available.append(('claude', 5))
        if user_settings.api_key_gpt:
            available.append(('gpt', 3))
        if user_settings.ollama_enabled:
            available.append(('local', 1))
        
        if not available:
            raise ValueError("No LLM configured")
        
        # Return best quality option
        choice = max(available, key=lambda x: x[1])
        return get_llm(choice[0])
```

**Model selection per agent:**
- Security, Logic, Performance: Opus (need reasoning)
- Style: Sonnet (sufficient, cheaper)

**Cost considerations:**
- Claude Opus: $5/$25 per 1M tokens
- GPT-5.4: $2.50/$10 per 1M tokens
- Local (Qwen2.5-Coder-32B): $0 (self-hosted)

---

## 7. Dashboard UI Components

### 7.1 Pages

#### Settings Page
```
┌─ LLM Configuration
│  ├─ Radio buttons: Local | Claude | GPT | Auto
│  ├─ Input: Claude API key (with test button)
│  ├─ Input: GPT API key (with test button)
│  ├─ Checkbox: Enable Ollama
│  └─ Input: Ollama host (with connectivity check)
│
├─ Agent Selection
│  ├─ Checkbox: Security Agent
│  ├─ Checkbox: Performance Agent
│  ├─ Checkbox: Style Agent
│  └─ Checkbox: Logic Agent
│
└─ Repositories
   ├─ List: connected repos
   ├─ Button: Add GitHub repo
   └─ Toggle: enable/disable per repo
```

#### Dashboard Page
```
┌─ Summary Cards
│  ├─ Total reviews: 42
│  ├─ Reviews today: 3
│  ├─ Tokens used: 425k / 1M (pro plan)
│  └─ Cost this month: $2.15 / $5.00
│
├─ Recent Reviews (table)
│  ├─ Columns: Repo | PR # | Status | Findings | Time | Actions
│  ├─ Row: {org/repo | #123 | Done | 3 critical, 5 warning | 2m 30s | View | Post}
│  └─ Pagination: 20 per page
│
├─ Findings Statistics
│  ├─ Bar chart: findings by agent
│  ├─ Pie chart: findings by severity
│  └─ Table: top issue types
│
└─ Realtime Progress (when analyzing)
   ├─ Status: "Analyzing..."
   ├─ Progress: Security ✓ | Performance 🔄 | Style ◯ | Logic ◯
   └─ ETA: ~30 seconds remaining
```

#### Review Details Page
```
┌─ PR Header
│  ├─ Title, number, repo, author
│  ├─ Status badge (Done | Error)
│  └─ Stats: 3 critical, 5 warning, 2 info | 145 sec | $0.15
│
├─ Findings List (grouped by severity)
│  ├─ [CRITICAL] SQL injection (security agent, line 42)
│  │  ├─ Message: String interpolation in query
│  │  ├─ Suggestion: Use parameterized queries
│  │  ├─ Code: query = f"SELECT * FROM users WHERE id={user_id}"
│  │  └─ Agent: Security | Confidence: High
│  │
│  ├─ [WARNING] N+1 query (performance agent, line 28)
│  │  ├─ Message: Database query in loop
│  │  ├─ Suggestion: Batch load or use prefetch
│  │  └─ Agent: Performance | Impact: High
│  │
│  └─ [INFO] Naming convention (style agent, line 5)
│     └─ Variable 'userName' should be 'user_name' (PEP 8)
│
└─ Actions
   ├─ Button: Post to PR comment
   ├─ Button: Download as JSON
   └─ Button: Share (copy link)
```

---

## 8. GitHub Integration Details

### 8.1 Webhook Setup

**Event types:**
- `pull_request.opened` → create review
- `pull_request.synchronize` → update review

**Webhook payload:**
```json
{
  "action": "opened|synchronize",
  "pull_request": {
    "number": 123,
    "head": { "sha": "abc123" },
    "base": { "sha": "def456" }
  },
  "repository": {
    "owner": { "login": "org" },
    "name": "repo"
  }
}
```

**Processing:**
1. Verify signature: `X-Hub-Signature-256` header
2. Extract PR number + SHA
3. Fetch full PR diff via GitHub API
4. Queue async analysis
5. Return 202 immediately

---

### 8.2 PR Comment Format

**Template:**

```markdown
## 🤖 AI Code Review

**Status:** ✅ Analysis complete (2m 34s)

### 🔴 Critical Issues (1)
- **[security] SQL Injection** (line 42, `api.py`)
  ```python
  query = f"SELECT * FROM users WHERE id={user_id}"
  ```
  → Use parameterized queries: `cursor.execute("SELECT * FROM users WHERE id=%s", (user_id,))`

### 🟡 Warnings (2)
- **[performance] N+1 Query** (line 28, `service.py`)
  Loop contains database query. Prefetch relations or use batch load.

- **[style] Naming Convention** (line 5, `models.py`)
  Use snake_case: `userName` → `user_name` (PEP 8)

### ℹ️ Info (2)
- [style] Line too long (120/100 chars) at line 52

---
**Agents used:** Security, Performance, Style | **Model:** Claude Opus 4.6 | **Cost:** $0.12
```

---

## 9. Edge Cases & Error Handling

### 9.1 Code Extraction Edge Cases
- **Empty PR diff:** Skip analysis, return "No changes detected"
- **PR too large (>50k lines):** Analyze only first 10k lines, warn user
- **Binary files:** Skip with "Not applicable to binary files"
- **Deleted files only:** Skip with "Only deletions detected"

### 9.2 Agent Execution Edge Cases
- **Agent timeout (>30s):** Return partial results, log timeout warning
- **LLM rate limit:** Queue retry with exponential backoff
- **LLM API down:** Fallback to local model if available, else error
- **Invalid code syntax:** Some agents skip (style) but some can still analyze (security concept checks)

### 9.3 Concurrency Edge Cases
- **Duplicate webhook:** Check if review_id already exists, skip if running
- **User deletes API key mid-review:** Error, request reconfiguration
- **Repo disabled during analysis:** Cancel tasks, mark review as error

### 9.4 PR Comment Edge Cases
- **Can't post comment:** Return error but keep findings in dashboard
- **GitHub API rate limit:** Queue retry later
- **User doesn't have push permissions:** Show error but allow dashboard view

---

## 10. Testing Strategy

### 10.1 Unit Tests
- **LLM Router:** Test all LLM selection paths
- **Agent outputs:** Mock LLM responses, verify parsing
- **Result aggregator:** Test deduplication, ranking
- **Data validation:** Test API input schemas

### 10.2 Integration Tests
- **GitHub webhook:** Fake webhook events, verify DB writes
- **End-to-end review:** Paste code → get findings
- **LLM routing:** Test all 3 LLM options (mock APIs)
- **PR posting:** Verify GitHub API calls

### 10.3 Evaluation Metrics
- **Accuracy:** % findings humans agree with (RAGAS faithfulness)
- **Recall:** % actual issues found by agents (vs. manual code review)
- **F1:** Harmonic mean of precision + recall
- **Latency:** P95 time from webhook to PR comment
- **Cost:** Tokens used per review → USD

**Target:**
- Accuracy: ≥80%
- Latency: <5 minutes
- Cost: <$0.30 per review (for pro plan)

---

## 11. Deployment & Infrastructure

### 11.1 Docker Setup
```dockerfile
FROM python:3.12-slim

# Backend
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY backend/ .

# Frontend (nginx)
COPY frontend/build /usr/share/nginx/html

EXPOSE 8000 3000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0"]
```

### 11.2 Environment Variables
```
# LLM APIs
ANTHROPIC_API_KEY=sk-...
OPENAI_API_KEY=sk-...
OLLAMA_HOST=http://localhost:11434

# Database
DATABASE_URL=postgresql://user:pass@localhost/cra_db

# GitHub App
GITHUB_APP_ID=123456
GITHUB_APP_PRIVATE_KEY=-----BEGIN PRIVATE KEY-----...
GITHUB_CLIENT_ID=Iv1.xxx
GITHUB_CLIENT_SECRET=xxx

# JWT
JWT_SECRET=xxx

# Stripe (for pro plan)
STRIPE_API_KEY=sk_live_...
STRIPE_WEBHOOK_SECRET=whsec_...
```

### 11.3 Database Migrations
```
migrations/
├── 001_initial_schema.sql
├── 002_add_agent_executions.sql
├── 003_add_audit_log.sql
└── ...
```

---

## 12. Security Considerations

- **API keys storage:** Encrypted in database (Fernet)
- **GitHub webhook signature:** Verify HMAC-SHA256
- **RLS policies:** Enforce at DB level
- **Rate limiting:** 100 requests per minute per user
- **Input validation:** Max code size, max message length
- **Output sanitization:** Escape user content in PR comments
- **Logging:** Don't log API keys, sensitive code

---

## 13. Performance Targets

| Metric | Target | How |
|--------|--------|-----|
| Webhook → Analysis start | <1s | Async queue |
| Per-agent latency | <30s | Timeout + parallel |
| Total review time | <5m | Concurrent agents |
| Dashboard load | <2s | Lazy loading, caching |
| PR comment posting | <5s | Direct GitHub API |
| Database query | <100ms | Indexes, RLS batching |

---

## 14. Future Enhancements (v2.0+)

- [ ] Custom agent builder (UI for creating domain-specific agents)
- [ ] Fine-tuned models (train on team's code patterns)
- [ ] Team collaboration (shared findings, approvals)
- [ ] Metrics dashboard (quality trends, ROI)
- [ ] Integration with Slack (notifications)
- [ ] CLI tool (`cra analyze path/to/code`)
- [ ] VS Code extension
- [ ] Advanced findings (auto-fix suggestions, related issues)
