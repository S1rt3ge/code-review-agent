# Feature Specification: Review Passport Gate

## Description

Review Passport Gate turns a passport verdict into a concrete merge signal. The dashboard can show the gate decision locally, and GitHub-backed reviews can publish the decision as a GitHub commit status with the context `AI Review Passport Gate`.

This matters because a passport should not only explain risk after a reviewer opens the dashboard. It should also become a workflow signal that branch protection can require.

## User Stories

- As a maintainer, I want `READY` passports to publish a passing GitHub status, so that safe changes can satisfy a required check.
- As a maintainer, I want `READY_WITH_RISKS` and `BLOCKED` passports to publish a failing status, so that risky or incomplete changes cannot silently merge.
- As a local-demo user, I want to see the gate decision without GitHub credentials, so that the demo still works offline.
- As a developer, I want a clear reason and next action, so that a failing gate tells me what to fix.

## Data Model

`review_passports`
- `github_gate_state`: text nullable, last published GitHub commit status state (`success`, `failure`, or `error`).
- `github_gate_url`: text nullable, URL returned by GitHub for the posted commit status.
- `github_gate_posted_at`: timestamptz nullable, last successful gate publication timestamp.

Ownership remains unchanged through `review_passports.user_id` and `reviews.user_id`.

## API

```text
GET /api/reviews/{review_id}/passport/gate
Auth: Bearer user JWT
Success: 200 {
  "state": "failure",
  "context": "AI Review Passport Gate",
  "verdict": "BLOCKED",
  "description": "Review Passport is BLOCKED; fix missing/risky evidence.",
  "required_action": "Fix blocking evidence and regenerate the passport.",
  "github_gate_state": null,
  "github_gate_url": null,
  "github_gate_posted_at": null
}
Errors: 401 unauthenticated, 403 wrong owner, 404 review/passport missing
```

```text
POST /api/reviews/{review_id}/passport/gate/publish
Auth: Bearer user JWT
Body: {}
Success: 200 {
  "state": "failure",
  "context": "AI Review Passport Gate",
  "verdict": "READY_WITH_RISKS",
  "description": "Review Passport has risks; review missing evidence and QA.",
  "required_action": "Resolve risks or intentionally override outside this tool.",
  "github_gate_state": "failure",
  "github_gate_url": "https://github.com/...",
  "github_gate_posted_at": "..."
}
Errors:
- 400 local playground review, missing head SHA, GitHub App missing, or installation id missing
- 401 unauthenticated
- 403 wrong owner
- 404 review/repository/passport missing
- 502 GitHub API error
```

## Screens

Review detail / Review Passport panel:

- With a passport: show a compact gate row with state, verdict, required action, and last GitHub publication state.
- Actions: `Publish Gate`.
- Local/demo reviews: show gate state but return a clear inline error when publishing is attempted.
- Success: show `Gate published to GitHub.` and expose the status URL if available.
- Error: show the API error in the existing passport panel error area.

## Business Logic

- `READY` maps to GitHub status state `success`.
- `READY_WITH_RISKS` maps to `failure`.
- `BLOCKED` maps to `failure`.
- Unknown verdict maps to `error`.
- The GitHub status context is always `AI Review Passport Gate`.
- Publishing uses the existing GitHub App installation token path.
- Publishing creates a new commit status for `reviews.head_sha`; GitHub treats the newest status for a context as the current gate.
- Publishing does not require comments to be posted first.
- Publishing never calls external LLM providers.

## Edge Cases

- Passport missing: return 404 and ask the user to generate a passport first.
- Local playground review: gate can be read, publish returns 400.
- Missing `head_sha`: publish returns 400 because GitHub commit statuses require a SHA.
- GitHub API unavailable or permission missing: return 502 without deleting local gate data.
- Repeated publish: create another status with the same context and refresh local metadata.

## Priority / Dependencies

Priority: next differentiation slice after Review Passport export and PR comments.

Dependencies:
- Existing Review Passport persistence.
- Existing GitHub API client and GitHub App auth.
- Existing review detail UI.

Verification:
- Unit tests for verdict-to-gate mapping.
- GitHub API client test for commit status payload.
- API tests for local gate read, local publish guard, and mocked GitHub publish.
- Frontend tests for gate display and publish action.
