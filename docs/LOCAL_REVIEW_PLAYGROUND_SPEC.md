# Feature Specification: Local Review Playground

## Description

Local Review Playground removes the setup barrier before the first useful result. A user running the project locally can create a realistic review either from a bundled demo diff or from a pasted git diff, then inspect findings immediately in the existing review detail screen. The feature does not require GitHub App setup, webhooks, SMTP, OpenAI, Anthropic, or Ollama.

The feature is a local-product on-ramp, not a replacement for GitHub review automation. It reuses the existing `repositories`, `reviews`, `findings`, and `agent_executions` tables so the dashboard, review list, stats, and detail pages continue to work without a separate demo data model.

## User Stories

- As a local evaluator, I want to click `Try demo review`, so that I can see a complete review result within seconds after `docker compose up`.
- As a developer, I want to paste a git diff and run a local review, so that I can test the product without installing a GitHub App.
- As a user with no configured LLM provider, I want deterministic local findings, so that the playground still demonstrates the product shape.
- As a returning user, I want each demo or pasted diff to create a new review record, so that I can compare examples in the dashboard.
- As a user, I want invalid or empty diffs rejected clearly, so that I know what to paste.

## Data Model

No new tables are required.

`repositories`
- Reuse one synthetic repository per user.
- `user_id`: current user id.
- `github_repo_owner`: `local`.
- `github_repo_name`: `playground`.
- `github_repo_url`: `local://playground`.
- `github_installation_id`: `NULL`.
- Unique constraint `uq_repo_user_owner_name` prevents duplicate synthetic repos.

`reviews`
- `user_id`: current user id.
- `repo_id`: synthetic playground repository id.
- `github_pr_number`: generated local sequence number.
- `github_pr_title`: `Local demo review` or user-provided title.
- `status`: `done`.
- `selected_agents`: selected local agents.
- `lm_used`: `local-playground`.
- `total_findings`: count of generated findings.
- `tokens_input`: estimated from diff length.
- `tokens_output`: estimated from finding text length.
- `estimated_cost`: `0.0000`.
- `completed_at`: request completion timestamp.

`findings`
- One row per local heuristic finding.
- Uses existing fields: `agent_name`, `finding_type`, `severity`, `file_path`, `line_number`, `message`, `suggestion`, `code_snippet`, `category`.

`agent_executions`
- One row per selected agent.
- `status`: `done`.
- `findings_count`: number of findings produced by that agent.
- `tokens_input` / `tokens_output`: deterministic local estimates.

## API

### POST `/api/reviews/playground/demo`

Auth: Bearer user JWT.

Body:

```json
{
  "selected_agents": ["security", "performance", "style", "logic"]
}
```

Success: `201 Created`, returns `ReviewResponse` with status `done`, findings, and agent executions.

Errors:
- `400` if all selected agents are invalid or omitted as an empty list.
- `401` if unauthenticated.
- `403` if email verification is required and the user is unverified.

### POST `/api/reviews/playground/diff`

Auth: Bearer user JWT.

Body:

```json
{
  "title": "Fix auth cache invalidation",
  "code_diff": "diff --git a/app.py b/app.py\n...",
  "selected_agents": ["security", "logic"]
}
```

Success: `201 Created`, returns `ReviewResponse` with status `done`, findings, and agent executions.

Errors:
- `400` if `code_diff` is empty or does not contain added lines.
- `413` if `code_diff` exceeds 100000 characters.
- `401` if unauthenticated.
- `403` if email verification is required and the user is unverified.

## Screens

### Dashboard Empty State

Visible when the user has no reviews and no status filter.

Data:
- `total_reviews = 0`.
- Existing stats cards remain visible.

Actions:
- `Try demo review`: calls `POST /api/reviews/playground/demo`, then navigates to `/reviews/{id}`.
- `Paste diff`: opens the review modal in paste-diff mode.

States:
- Loading: disable action buttons and show short progress text.
- Error: show inline error with retry.
- Success: navigate to review detail.

### New Review Modal

Modes:
- `Repository PR`: existing repository + PR number flow.
- `Paste diff`: local playground flow.

Paste diff fields:
- Title: optional, max 160 chars.
- Diff textarea: required, max 100000 chars.
- Agent checkboxes: default all agents.

States:
- Empty repositories must not block paste-diff mode.
- Empty diff shows local validation before sending.
- API error is shown inline.

### Review Detail

No new page is required.

Expected result:
- Header title shows local review title.
- Status is `done`.
- Details show zero cost and `local-playground` model.
- Findings table shows generated findings.
- GitHub comment button is not useful for local playground reviews because the synthetic repository has no installation id; if clicked, existing backend validation returns a clear error.

## Business Logic

- The playground always scopes data to the current authenticated user.
- The synthetic repository is created lazily and reused.
- Demo review uses a bundled diff with examples for all four agents.
- Paste-diff review uses deterministic local heuristics:
  - Security: hardcoded secret-like assignments, `eval`, shell injection patterns.
  - Performance: repeated awaits inside loops, broad repeated file reads, obvious quadratic loops.
  - Style: very long added lines or unclear broad exception handling.
  - Logic: bare `except`, swallowed errors, impossible branches, suspicious boolean conditions.
- A selected agent with no findings still gets a completed `agent_executions` row.
- The local playground never sends pasted code to external providers.
- The local playground never writes comments to GitHub automatically.

## Edge Cases

- Empty diff: reject with `400`.
- Diff has only deleted/context lines: reject with `400`.
- Diff exceeds 100000 characters: reject with `413`.
- Invalid agent names: reject with `400`.
- Duplicate requests: create separate review rows; do not deduplicate.
- Existing synthetic repository: reuse it instead of creating another row.
- No LLM configured: still works because heuristic mode is local.
- No findings detected: create a done review with zero findings and completed agent executions.

## Priority / Dependencies

Priority: P0 portfolio/product upgrade.

Dependencies:
- Existing auth.
- Existing review, repository, finding, and agent execution tables.
- Existing Dashboard and ReviewDetail pages.

Implementation order:
1. Backend service tests for local heuristic analysis.
2. Backend integration tests for demo and pasted diff endpoints.
3. Backend service and router implementation.
4. Dashboard empty-state actions and paste-diff modal mode.
5. Frontend tests for local playground actions.
6. README update with 30-second local demo instructions.
