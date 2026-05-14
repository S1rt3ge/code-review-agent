# Feature Specification: Review Quality Eval Harness

## Description

Add a deterministic local evaluation harness for the review engine. It is for maintainers and portfolio reviewers who want proof that the Local Review Playground catches representative security, performance, style, and logic issues without external LLM providers, GitHub credentials, email delivery, or a database.

## User Stories

- As a maintainer, I want to run one command that grades the local review analyzer, so that I can catch regressions before changing agent logic.
- As a developer, I want to add a small JSON eval case with expected findings, so that future behavior is documented as executable evidence.
- As a reviewer of the project, I want to see pass/fail metrics, so that the AI review feature looks measurable rather than hand-wavy.

## Data Model

No database changes.

Eval cases live in `evals/review_quality_cases.json`:

```text
cases[]
- id: string, stable unique eval id
- title: string, human-readable case name
- code_diff: string, unified diff input
- selected_agents: string[], agents enabled for the case
- expected_findings[]: expected finding descriptors
  - agent_name: string
  - finding_type: string
  - file_path: string optional
  - line_number: int optional
  - severity: string optional
- max_unexpected_findings: int, default 0
```

## API

No HTTP API changes.

CLI:

```text
python scripts/evaluate_review_quality.py
Options:
- --cases PATH: override eval fixture path
- --json: emit machine-readable JSON report
Exit codes:
- 0 when all cases pass
- 1 when eval cases run but at least one case fails
- 2 when fixtures cannot be loaded or validated
```

## Screens

No UI changes. Results are printed in the terminal.

## Business Logic

- Load eval cases from JSON and validate required fields.
- Run `backend.services.playground_review.analyze_diff_locally` for each case.
- Match expected findings by `agent_name` and `finding_type`, and by optional `file_path`, `line_number`, and `severity` when provided.
- A case passes when all expected findings are matched and unexpected findings do not exceed `max_unexpected_findings`.
- Report case pass rate, expected finding recall, unexpected finding count, and an overall score.

## Edge Cases

- Empty case file should fail validation.
- Malformed JSON or missing fields should return exit code 2 from the CLI.
- Clean diffs with no expected findings should pass only when the analyzer emits no unexpected findings.
- Cases should respect `selected_agents`, so disabled agents cannot create expected matches.
- Large diffs are not the initial target; this eval is a fast smoke/regression suite.

## Priority / Dependencies

Priority: high after the Local Review Playground.

Dependencies:
- `backend/services/playground_review.py`
- `evals/review_quality_cases.json`
- `scripts/evaluate_review_quality.py`
