# Feature Specification: First-Run Onboarding

## Description

Guide a newly registered user from an empty dashboard to a first useful review.
The dashboard should show a compact setup checklist when there are no reviews,
using existing API data to mark account, repository, LLM, and first-review
progress. The local demo path stays first so the app remains useful without
GitHub, SMTP, or paid LLM setup.

## User Stories

- As a new user, I want a clear first action on the empty dashboard, so that I
  can create a useful review without reading external docs.
- As a solo evaluator, I want local-demo progress to be separate from GitHub
  setup, so that I can test the product before installing a GitHub App.
- As a user configuring the full workflow, I want links to Settings and
  Repositories, so that I can finish setup without hunting through navigation.

## Data Model

No database migration is required. The checklist derives state from existing
authenticated API responses:

```text
dashboard stats
- total_reviews: number

repositories list
- repositories: array

settings
- api_key_claude_set: boolean
- api_key_gpt_set: boolean
- ollama_enabled: boolean
```

## API

No new API endpoints are required.

Existing authenticated endpoints used by the dashboard:

```text
GET /api/dashboard/stats
GET /api/reviews?limit=20
GET /api/repositories
GET /api/settings
```

If setup metadata cannot be loaded, the dashboard should still show the local
demo actions and avoid blocking first review creation.

## Screens

Dashboard empty state:

- Loading: existing stats/table skeletons remain.
- Empty: show `No reviews yet`, `Try demo review`, `Paste diff`, and a setup
  checklist with progress count.
- Success: completed checklist rows show completed state; incomplete rows link
  to the relevant next screen.
- Error: setup metadata errors show a small non-blocking note inside the
  checklist area.

## Business Logic

- The checklist renders only when the unfiltered reviews list is empty.
- `Account ready` is complete when the dashboard is authenticated.
- `Connect a repository` is complete when `/repositories` returns at least one
  repository.
- `Configure an LLM provider` is complete when Settings reports Claude, GPT, or
  Ollama configured.
- `Run your first review` is complete when `total_reviews > 0`; on the empty
  dashboard this remains the active next action.

## Edge Cases

- No repositories and no LLM provider: local demo actions remain available.
- Repository or settings request fails: show a non-blocking checklist warning.
- Filtered review list is empty: keep the existing filter-empty message instead
  of onboarding.
- User has reviews: do not show first-run onboarding.

## Priority / Dependencies

Priority: v0.2.0 release polish. Depends on existing dashboard, repositories,
settings, and local playground APIs.
