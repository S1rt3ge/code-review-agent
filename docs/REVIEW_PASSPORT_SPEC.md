# Feature Specification: Review Passport and Anti-AI-Slop Mode

## Description

Review Passport turns a normal review result into a proof-oriented merge packet. It is for solo developers, portfolio reviewers, and small teams that need more than generic AI review comments. The feature compares a review against a pasted spec or issue acceptance criteria, links findings to concrete evidence, generates a manual QA script, and produces a merge verdict.

Anti-AI-Slop Mode is a deterministic layer inside the passport. It flags common AI-generated-code failure patterns: placeholder completeness, missing tests, assertionless tests, broad changes without evidence, over-mocking, swallowed errors, and unreviewable blast radius. The first implementation must work in the local playground without GitHub, SMTP, or paid LLM providers.

The user-visible outcome is a `Review Passport` panel on the review detail page with:
- verdict: `READY`, `READY_WITH_RISKS`, or `BLOCKED`
- spec coverage matrix
- evidence-backed findings and anti-slop signals
- manual QA script
- local/free execution copy for demo use

## User Stories

- As a solo developer, I want to paste acceptance criteria into a review, so that I can see whether the PR actually satisfies the task before I merge it.
- As a portfolio reviewer, I want a review passport with evidence and a verdict, so that I can judge the project quality without trusting vague AI output.
- As a developer reviewing AI-generated code, I want anti-slop signals, so that I can catch missing tests, placeholder code, and broad unproven changes.
- As a local evaluator, I want the passport to work on `Try demo review` and pasted diffs without paid providers, so that the demo remains self-hosted and free.
- As a user, I want invalid or oversized spec input rejected clearly, so that I can fix the input without database or terminal work.
- As a dashboard user, I want to generate a Review Passport directly from Review DNA, so that the project methodology is evaluated without manual copy/paste.
- As a dashboard user, I want review rows to show the current passport verdict, so that I can see merge-readiness without opening every review.

## Data Model

### review_passports

One generated passport per review. Regenerating replaces the previous passport for that review.

```text
review_passports
- id: uuid PK
- review_id: uuid FK reviews(id) ON DELETE CASCADE NOT NULL
- user_id: uuid FK users(id) ON DELETE CASCADE NOT NULL
- mode: text NOT NULL
- spec_source_type: text NOT NULL
- spec_source_ref: text NULL
- spec_input: text NULL
- spec_digest: text NOT NULL
- verdict: text NOT NULL
- confidence_score: integer NOT NULL DEFAULT 0
- coverage_summary: jsonb NOT NULL DEFAULT '[]'
- anti_slop_signals: jsonb NOT NULL DEFAULT '[]'
- qa_steps: jsonb NOT NULL DEFAULT '[]'
- missing_evidence: jsonb NOT NULL DEFAULT '[]'
- generated_at: timestamptz NOT NULL DEFAULT now()
- created_at: timestamptz NOT NULL DEFAULT now()
- updated_at: timestamptz NOT NULL DEFAULT now()
```

Constraints:
- `UNIQUE(review_id)`
- `mode IN ('spec_evidence', 'anti_ai_slop', 'combined')`
- `spec_source_type IN ('manual', 'local_demo', 'pr_body', 'github_issue', 'review_dna')`
- `verdict IN ('READY', 'READY_WITH_RISKS', 'BLOCKED')`
- `confidence_score BETWEEN 0 AND 100`

Indexes:
- `INDEX(review_passports_user_id_idx ON review_passports(user_id))`
- `INDEX(review_passports_review_id_idx ON review_passports(review_id))`
- `INDEX(review_passports_verdict_idx ON review_passports(verdict))`

Ownership rule:
- Every query must join or filter by `user_id == current_user.id`.
- A passport cannot be created for a review owned by another user.

### review_input_snapshots

Stores the minimum normalized input required to regenerate deterministic evidence. This avoids depending on external GitHub availability after the original review.

```text
review_input_snapshots
- id: uuid PK
- review_id: uuid FK reviews(id) ON DELETE CASCADE NOT NULL
- user_id: uuid FK users(id) ON DELETE CASCADE NOT NULL
- input_type: text NOT NULL
- content_digest: text NOT NULL
- changed_files: jsonb NOT NULL DEFAULT '[]'
- added_lines: jsonb NOT NULL DEFAULT '[]'
- created_at: timestamptz NOT NULL DEFAULT now()
```

Constraints:
- `UNIQUE(review_id, input_type)`
- `input_type IN ('diff')`

Indexes:
- `INDEX(review_input_snapshots_review_id_idx ON review_input_snapshots(review_id))`
- `INDEX(review_input_snapshots_user_id_idx ON review_input_snapshots(user_id))`

`added_lines` shape:

```json
[
  {
    "file_path": "backend/services/example.py",
    "line_number": 42,
    "content": "return value"
  }
]
```

Limits:
- `spec_input`: max 20000 characters at the API layer.
- `added_lines`: max 2500 lines per review.
- `content`: trim each line to 500 characters before storing.
- No secrets are redacted by the first version; the UI must warn that pasted diffs/specs are stored locally in the project database.

## API

### POST `/api/reviews/{review_id}/passport`

Auth: Bearer user JWT.

Creates or replaces the passport for a review.

Body:

```json
{
  "mode": "combined",
  "spec_source_type": "manual",
  "spec_source_ref": "Issue #48",
  "spec_input": "- User can run local demo in 5 minutes\n- No paid provider required",
  "code_diff": "diff --git a/app.py b/app.py\n..."
}
```

Success: `201 Created`

```json
{
  "id": "uuid",
  "review_id": "uuid",
  "mode": "combined",
  "spec_source_type": "manual",
  "spec_source_ref": "Issue #48",
  "verdict": "READY_WITH_RISKS",
  "confidence_score": 78,
  "coverage_summary": [
    {
      "criterion_id": "AC-1",
      "criterion": "User can run local demo in 5 minutes",
      "status": "covered",
      "evidence": [
        {
          "type": "file_line",
          "file_path": "README.md",
          "line_number": 299,
          "summary": "README documents the 30-second local demo flow"
        }
      ]
    }
  ],
  "anti_slop_signals": [
    {
      "type": "missing_tests",
      "severity": "medium",
      "summary": "Application code changed without matching test changes",
      "evidence": ["frontend/src/pages/ReviewDetail.jsx"]
    }
  ],
  "qa_steps": [
    {
      "step": 1,
      "title": "Run local stack",
      "command": "docker compose up --build",
      "expected": "Frontend is available at http://localhost:5173"
    }
  ],
  "missing_evidence": []
}
```

Errors:
- `400` invalid mode, invalid source type, empty spec for `spec_evidence` or `combined`, malformed diff.
- `401` unauthenticated.
- `403` email verification required or review does not belong to the user.
- `404` review not found.
- `413` `spec_input` or `code_diff` exceeds limits.

### POST `/api/reviews/{review_id}/passport/review-dna`

Auth: Bearer user JWT.

Creates or replaces the passport for a review using the current Review DNA
Criteria Pack as `spec_input`.

Body: empty.

Behavior:
- loads `review-dna.yml` when present, otherwise scans the repository
- renders the Criteria Pack as Review Passport acceptance criteria
- sets `mode` to `combined`
- sets `spec_source_type` to `review_dna`
- sets `spec_source_ref` to `Review DNA Criteria Pack (<profile>)`
- uses the stored review diff snapshot; no external provider call is made

Success: `201 Created` with `ReviewPassportResponse`.

Errors:
- `400` Review DNA criteria cannot be loaded or the review has no diff snapshot.
- `401` unauthenticated.
- `403` email verification required or review does not belong to the user.
- `404` review not found.

### GET `/api/reviews/{review_id}/passport`

Auth: Bearer user JWT.

Returns the existing passport for a review.

Success: `200 OK` with `ReviewPassportResponse`.

Errors:
- `401` unauthenticated.
- `403` review does not belong to the user.
- `404` review or passport not found.

### GET `/api/reviews`

Existing list response includes a lightweight nullable `passport` summary for
each review:

```json
{
  "passport": {
    "verdict": "READY_WITH_RISKS",
    "confidence_score": 82,
    "spec_source_type": "review_dna",
    "generated_at": "2026-05-18T12:30:00Z",
    "github_gate_state": "failure"
  }
}
```

Behavior:
- `passport` is `null` when no Review Passport has been generated.
- The list endpoint must eager-load the one-to-one passport relation to avoid
  per-row async lazy loads.
- The summary must not include raw `spec_input`, diff snapshots, QA steps, or
  full evidence payloads.

### DELETE `/api/reviews/{review_id}/passport`

Auth: Bearer user JWT.

Deletes the passport for a review.

Success: `204 No Content`.

Errors:
- `401` unauthenticated.
- `403` review does not belong to the user.
- `404` review or passport not found.

## Screens

### Review Detail: Review Passport Panel

Visible on `/reviews/{id}` under the existing review explainer panel.

Data:
- Review title, status, model, findings count from existing review response.
- Existing passport if present.
- Input form if no passport exists or user chooses regenerate.

Actions:
- `Generate passport`: opens spec input form.
- `Generate with Review DNA`: creates a passport from repo methodology without filling the form manually.
- `Regenerate`: replaces existing passport.
- `Delete`: removes passport after confirmation.
- `Copy QA script`: copies numbered manual QA steps.

States:
- Loading: panel skeleton and disabled actions.
- Empty: explain that a passport needs acceptance criteria or a local demo spec.
- Error: inline error with retry.
- Success: verdict banner, coverage matrix, anti-slop signal list, QA script.

### Passport Form

Fields:
- Mode segmented control: `Spec evidence`, `Anti-AI-Slop`, `Combined`.
- Spec source type menu: `Manual`, `Local demo`, `PR body`, `GitHub issue`.
- Source reference input: optional, max 120 chars.
- Spec input textarea: required for `Spec evidence` and `Combined`, max 20000 chars.
- Diff textarea: optional when a review input snapshot already exists; required otherwise.

Validation:
- Empty spec is rejected for spec-based modes before API call.
- Oversized spec or diff shows character count and submit remains disabled.
- `Anti-AI-Slop` can run without spec input if a diff snapshot exists.

### Dashboard

No new top-level route in the first slice.

Review rows show a compact `Review Passport` column:
- `READY` for `READY` passports.
- `RISKS` for `READY_WITH_RISKS` passports.
- `BLOCKED` for `BLOCKED` passports.
- `Not generated` when no passport exists.

When a passport exists, the row also shows its confidence percentage.

## Business Logic

### Spec Criteria Extraction

The first version is deterministic and local:
- Split spec input by markdown checklist items, bullet lines, numbered lines, and lines containing `must`, `should`, `acceptance`, `user can`, or `no paid`.
- Normalize each criterion to max 240 characters.
- Keep up to 25 criteria.
- Assign stable IDs `AC-1`, `AC-2`, ...

### Evidence Matching

Inputs:
- extracted criteria
- existing review findings
- normalized changed files and added lines from the diff snapshot

Rules:
- A criterion is `covered` when keyword overlap or explicit file/path evidence is found in changed files, added lines, finding messages, or suggestions.
- A criterion is `missing` when no changed file, added line, or finding evidence matches.
- A criterion is `risky` when it matches at least one high or critical finding.
- A criterion is `uncertain` when weak evidence exists but no direct file or finding evidence exists.

Evidence objects must include:
- `type`: `file_line`, `finding`, `changed_file`, or `inference`
- `file_path`: optional
- `line_number`: optional
- `finding_id`: optional
- `summary`: required, max 300 chars

### Anti-AI-Slop Signals

Signals in the first version:
- `missing_tests`: non-test application files changed and no test files changed.
- `assertionless_tests`: added test file lines contain test declarations but no `assert`, `expect`, `toBe`, `toEqual`, `toHaveBeen`, or `pytest.raises`.
- `placeholder_code`: added lines contain `TODO`, `FIXME`, `pass`, `NotImplementedError`, `return null`, `return None`, or placeholder copy.
- `broad_blast_radius`: more than 12 changed files or more than 5 top-level directories changed.
- `swallowed_error`: reuse existing local review logic for bare `except`, empty `catch`, or silent fallback.
- `unbounded_input`: added endpoint or form logic accepts long text without max length or size validation.
- `over_mocked_tests`: added tests contain more mock setup lines than assertion lines by a ratio greater than 3:1.

Each signal includes:
- `type`
- `severity`: `low`, `medium`, `high`, or `critical`
- `summary`
- `evidence`: array of file paths or file-line strings
- `suggestion`

### Verdict Calculation

`BLOCKED` when:
- any critical finding exists, or
- any criterion is `missing` and at least one high anti-slop signal exists, or
- spec mode has no criteria after parsing.

`READY_WITH_RISKS` when:
- at least one criterion is `missing`, `risky`, or `uncertain`, or
- any medium/high anti-slop signal exists, or
- review has findings with severity `medium`, `high`, or `critical`.

`READY` when:
- all criteria are `covered`, and
- no medium/high/critical anti-slop signals exist, and
- review has no blocking findings.

`confidence_score`:
- Start at 100.
- Subtract 20 for each missing criterion.
- Subtract 12 for each risky criterion.
- Subtract 8 for each uncertain criterion.
- Subtract 15 for each critical/high anti-slop signal.
- Subtract 8 for each medium anti-slop signal.
- Clamp to 0-100.

### QA Script Generation

Generate deterministic QA steps from:
- local run commands in README and CLAUDE.md
- criteria keywords
- changed file areas

Minimum steps:
- Run `docker compose up --build`.
- Open `http://localhost:5173`.
- Register or log in with local email verification disabled.
- Create or open the relevant review.
- Verify each covered criterion manually.

For anti-slop signals, add targeted checks:
- missing tests: run backend/frontend tests named by touched area.
- placeholder code: inspect listed files and confirm no placeholder path executes.
- unbounded input: paste oversized input and expect client or API rejection.

### Security And Privacy

- Passport generation is scoped to the authenticated user.
- Do not send spec input, diff input, or added-line snapshots to external LLM providers in the first version.
- Do not log raw spec input or raw diff input.
- API errors must not echo full spec or diff content.
- Stored snapshots are local DB data and must be deleted when the review is deleted.
- GitHub issue retrieval is not part of the first implementation; `github_issue` source type is accepted only when the user pastes the issue text manually.

## Edge Cases

- Empty spec in `combined` or `spec_evidence`: reject with `400`.
- Empty spec in `anti_ai_slop`: allowed only when a diff snapshot exists.
- Empty diff and no existing snapshot: reject with `400`.
- Diff has only deleted/context lines: reject with `400`.
- Spec exceeds 20000 chars: reject with `413`.
- Diff exceeds existing playground 100000 char limit: reject with `413`.
- More than 25 criteria: keep the first 25 and include a low-severity `criteria_truncated` signal.
- No findings and all criteria covered: passport can be `READY`.
- No findings but missing tests signal: passport is `READY_WITH_RISKS`.
- Existing passport: replace in a transaction so GET never returns partial regenerated data.
- Concurrent regenerations: last committed request wins; no duplicate passport rows.
- Review owned by another user: return `403` without revealing whether the passport exists.

## Priority / Dependencies

Priority: P0 v0.3 differentiator after v0.2 release cleanup.

Dependencies:
- Existing authenticated review detail flow.
- Existing local playground diff parsing and deterministic analyzer.
- Existing review, finding, repository, and agent execution tables.
- New migrations for `review_passports` and `review_input_snapshots`.
- Frontend API client in `frontend/src/services/api.js`.
- Review detail page in `frontend/src/pages/ReviewDetail.jsx`.

Implementation order:
1. Backend unit tests for spec criteria extraction, anti-slop signal detection, verdict calculation, and QA script generation.
2. Migration and ORM/schema models for passport and input snapshot persistence.
3. Backend service `backend/services/review_passport.py`.
4. API tests for create/get/delete passport endpoints, auth ownership, validation, and replacement behavior.
5. Store diff snapshots during playground demo and pasted-diff review creation.
6. Frontend API wrappers and Review Detail passport panel tests.
7. Review Detail UI implementation with generate/regenerate/delete/copy QA script actions.
8. Eval fixture updates so `python scripts/evaluate_review_quality.py` can include anti-slop cases.
9. README and `docs/local-demo.md` update showing the Review Passport demo flow.

Verification commands:
- `python -m pytest -m "not integration" --tb=short -q`
- `python -m pytest -m integration --tb=short -q`
- `python scripts/evaluate_review_quality.py`
- `python -m ruff check backend`
- `cd frontend && npm test -- --run && npm run build`
