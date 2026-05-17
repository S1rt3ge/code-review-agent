# Feature Specification: Review DNA CLI

## Description

Review DNA CLI creates a deterministic project-specific review profile. It is
for solo developers, maintainers, and portfolio reviewers who want AI review to
respect this repository's actual methodology, local demo constraints, specs,
evals, and release gates.

The feature touches only local files and Python services. It must work without
GitHub credentials, SMTP, PostgreSQL, Docker, or paid LLM providers.

The user-visible outcome is:

- `python scripts/review_dna.py scan --json` prints a machine-readable profile
- `python scripts/review_dna.py init` writes `review-dna.yml`
- `python scripts/review_dna.py instructions` prints reviewer-ready Markdown
- `python scripts/review_dna.py check` evaluates the current change set against
  the profile and reports a project-fit score

## User Stories

- As a solo developer, I want one command to summarize how this repo should be
  reviewed, so that I do not need to re-explain project rules in every PR.
- As a maintainer, I want generated reviewer instructions, so that AI review
  focuses on specs, local demo behavior, tests, and release gates.
- As a portfolio reviewer, I want concrete evidence sources, so that I can see
  the project is calibrated rather than generic.
- As a developer, I want `init` to refuse overwriting an existing
  `review-dna.yml`, so that local edits are not lost.
- As a local evaluator, I want the CLI to run without external services, so that
  the feature is testable from a fresh clone.
- As a solo maintainer, I want an advisory check of changed files against the
  repo's methodology, so that I can catch missing specs, tests, or local-demo
  evidence before opening a PR.
- As a PR reviewer, I want the check to recommend the commands most relevant to
  the changed files, so that I can verify the risk instead of reading a generic
  checklist.

## Data Model

No database changes.

Runtime dataclasses:

```text
ReviewDNAProfile
- project_name: str
- generated_by: str
- source_root: str
- stacks: list[str]
- evidence_sources: list[EvidenceSource]
- quality_gates: list[QualityGate]
- local_constraints: list[str]
- review_rules: list[str]
- suggested_commands: list[str]
```

```text
EvidenceSource
- path: str
- kind: str
- reason: str
```

```text
QualityGate
- name: str
- command: str
- required: bool
- reason: str
```

```text
ReviewDNACheckIssue
- code: str
- severity: str
- message: str
- paths: list[str]
- recommendation: str
```

```text
ReviewDNACheckResult
- status: str
- score: int
- changed_files: list[str]
- issues: list[ReviewDNACheckIssue]
- recommended_commands: list[str]
```

Generated file:

```text
review-dna.yml
- project_name: string
- generated_by: string
- source_root: string, always "." for committed portable profiles
- stacks: string[]
- evidence_sources[]:
  - path: string
  - kind: string
  - reason: string
- quality_gates[]:
  - name: string
  - command: string
  - required: boolean
  - reason: string
- local_constraints: string[]
- review_rules: string[]
- suggested_commands: string[]
```

No RLS is required because no database table is added.

## API

No HTTP API changes.

CLI:

```text
python scripts/review_dna.py scan [--repo PATH] [--json]
```

Behavior:

- scans `PATH`, defaulting to the repository root
- prints text summary by default
- prints JSON when `--json` is passed

Exit codes:

- `0` successful scan
- `2` invalid repo path

```text
python scripts/review_dna.py init [--repo PATH] [--output PATH] [--force]
```

Behavior:

- writes a YAML-compatible profile to `PATH`, default `review-dna.yml`
- refuses to overwrite an existing file unless `--force` is passed

Exit codes:

- `0` profile written
- `2` invalid repo path or output already exists without `--force`

```text
python scripts/review_dna.py instructions [--repo PATH] [--profile PATH]
```

Behavior:

- renders reviewer-ready Markdown from `review-dna.yml` when `--profile` exists
- otherwise scans the repository and renders instructions from the live profile

Exit codes:

- `0` instructions rendered
- `2` invalid repo path or invalid profile path

```text
python scripts/review_dna.py check [--repo PATH] [--profile PATH]
                               [--changed-file PATH] [--json]
```

Behavior:

- loads `review-dna.yml` when present, otherwise scans the repo
- uses repeated `--changed-file` values when provided
- otherwise reads changed file paths from local git status
- prints a text report by default
- prints JSON when `--json` is passed
- remains advisory in MVP; failed project-fit returns exit code `1`, invalid
  input returns `2`

Exit codes:

- `0` check ran and status is `PASS`
- `1` check ran and status is `WARN` or `FAIL`
- `2` invalid repo path, invalid profile path, or git status cannot be read

## Screens

No UI changes in the first slice. Results are terminal output.

Terminal states:

- Loading: no spinner; commands are fast and synchronous.
- Empty: a valid but minimal repo prints an empty-evidence profile with a warning
  in text mode.
- Error: invalid path or overwrite block prints a concise stderr message.
- Success: scan prints profile, init prints output path, instructions prints
  Markdown, check prints score/status/issues.

## Business Logic

- Stack detection:
  - `backend/` or `requirements.txt` means `python`
  - `frontend/package.json` means `react-vite`
  - `docker-compose.yml` or `Dockerfile` means `docker`
  - `.github/workflows` means `github-actions`
- Evidence sources:
  - include `README.md`, `PROJECT_IDEA.md`, `TECHNICAL_SPEC.md`
  - include `SPEC_TEMPLATE.md`
  - include feature idea docs under `docs/*IDEA*.md`
  - include feature specs under `docs/*SPEC*.md`
  - include eval fixtures under `evals/*.json`
  - include release/governance docs under `docs/*checklist*.md` and
    `docs/*policy*.md`
- Quality gates:
  - include project verification commands from `AGENTS.md` when present
  - include review eval command when `scripts/evaluate_review_quality.py` exists
  - include frontend test/build command when `frontend/package.json` exists
  - include Docker local run command when `docker-compose.yml` exists
- Local constraints:
  - always include no required GitHub credentials for local playground
  - include no required SMTP when local auth verification can be disabled
  - include no required paid LLM for deterministic demo/evals
- Review rules:
  - require spec-first changes for new features
  - require tests before implementation for behavior changes
  - require docs updates when setup, public API, or workflow changes
  - require local demo flow to remain usable without paid services
  - require Review Passport / Anti-AI-Slop evidence when review logic changes
- `init` must not overwrite existing output unless `--force` is passed.
- `init` must write `source_root: "."` for portable committed profiles.
- Profile output must be deterministic: sort paths and rules by stable priority.
- The scanner must not read `.env`, secrets, node_modules, build outputs, or git
  internals.
- Check rules:
  - start score at `100`
  - subtract `25` for each high severity issue
  - subtract `15` for each medium severity issue
  - subtract `5` for each low severity issue
  - status is `PASS` when score is at least `90` and no issues exist
  - status is `WARN` when score is at least `70` and issues exist
  - status is `FAIL` when score is below `70` or any high severity issue exists
  - application code changes under `backend/`, `frontend/src/`, or `scripts/`
    require matching tests unless the change is docs-only
  - application code changes require a feature spec or idea doc update unless
    the changed files are tests-only
  - local auth, provider, Docker, settings, env, or GitHub integration changes
    require local-first evidence in docs or tests
  - review analyzer, passport, playground, eval, or DNA changes recommend
    `python scripts/evaluate_review_quality.py`
  - frontend changes recommend frontend tests/build
  - backend or script changes recommend backend tests and ruff

## Edge Cases

- Missing repo path returns exit code `2`.
- Empty repository returns a valid profile with no evidence sources.
- Existing `review-dna.yml` blocks `init` unless `--force` is passed.
- Unreadable files are skipped; the profile should not fail because one optional
  doc cannot be read.
- Paths are normalized to POSIX-style relative paths in output.
- Large repositories avoid recursive full-content scanning; the MVP only checks
  known file names and shallow glob patterns.
- Non-ASCII file names are allowed as paths but file contents are not required
  for detection.
- Empty change sets return `PASS` with score `100`.
- Explicit `--changed-file` paths are normalized to POSIX-style relative paths.
- `check` must ignore deleted generated/cache paths when evaluating evidence.

## Priority / Dependencies

Priority: high after Review Passport and eval harness.

Rollout order:

1. Add idea/spec docs.
2. Add service tests for scan/profile/rendering behavior.
3. Add CLI tests for exit codes and overwrite safety.
4. Implement `backend/services/review_dna.py`.
5. Implement `scripts/review_dna.py`.
6. Document usage in `README.md` after tests pass.
7. Add portable `review-dna.yml`.
8. Add service and CLI tests for Review DNA Check.
9. Implement advisory `check` command and JSON/text reports.

Dependencies:

- `backend/services/review_eval.py` for existing eval positioning only; no direct
  runtime dependency is required in MVP.
- `scripts/evaluate_review_quality.py` as a detected quality gate.
- `SPEC_TEMPLATE.md`, `PROJECT_IDEA.md`, `README.md`, and `docs/*SPEC*.md` as
  evidence sources.
