# PROJECT IDEA: Review DNA CLI

## 1. Problem

AI code review tools usually review a pull request as if every repository has the
same standards. In practice, review quality depends on project-specific context:

- which commands must pass before merge
- which files prove the product promise
- which local-only flows must work without paid providers
- which review rules are stricter than generic linting
- which docs define acceptance criteria

For this project, a reviewer already needs to connect at least 6 context sources:
`README.md`, `PROJECT_IDEA.md`, feature specs in `docs/`, eval fixtures in
`evals/`, backend services, and CI/release policy. Without a project-specific
profile, AI review output becomes generic comments instead of proof that the
change respects the product methodology.

The practical pain:

- solo developers lose 20-40 minutes per PR re-explaining project rules
- AI reviewers miss local demo constraints such as no GitHub, SMTP, or paid LLM
- portfolio visitors cannot see why this review agent is different from a demo
- regression risk grows as specs, evals, passports, and docs evolve separately

## 2. Solution

Review DNA CLI generates a deterministic repository profile that tells humans
and AI reviewers how this project should be reviewed.

Process:

1. Scan the repository for product docs, specs, evals, test commands, CI policy,
   and local-first constraints.
2. Build a structured `ReviewDNAProfile` with quality gates, evidence sources,
   review rules, and local run instructions.
3. Print the profile as JSON or write `review-dna.yml`.
4. Generate reviewer instructions that can be pasted into Codex, GitHub PR
   descriptions, CodeRabbit-style tools, or local review prompts.
5. Compare a local change set against the profile and produce a project-fit
   score before the change reaches PR review.

User-visible outcome:

- one local command explains how to review the repo
- one local command checks whether the current change respects that review DNA
- no GitHub token, SMTP provider, database, or LLM key is required
- the output becomes a portable proof artifact for the project

## 3. Why Now

The project already has a proof-oriented direction:

- Local Review Playground proves the analyzer without external services.
- Review Passport turns a review into merge evidence.
- Anti-AI-Slop Mode catches failure patterns in AI-generated code.
- Review Quality Eval Harness measures deterministic analyzer behavior.

Review DNA is the missing upstream artifact: it defines what a "good review" is
for this repository before any specific PR is analyzed.

## 4. Target Audience

Primary: solo developers building serious portfolio projects.

- Need: make every PR review stricter and more explainable.
- Pain: they cannot depend on another maintainer for project context.
- Success: a reviewer can run one command and understand the repo standards.

Secondary: open-source maintainers.

- Need: consistent contributor guidance and review expectations.
- Pain: repeated review comments about tests, setup, docs, and scope.
- Success: generated instructions become a PR review checklist.

Tertiary: small teams adopting AI review.

- Need: calibrate AI review to their own conventions.
- Pain: generic AI feedback creates noise and misses product-specific rules.
- Success: each repo has a deterministic review profile.

## 5. Architecture

```text
Repository files
    |
    v
Review DNA scanner
    |
    +--> docs/spec detector
    +--> stack detector
    +--> test/eval command detector
    +--> local-first constraint detector
    +--> quality gate detector
    |
    v
ReviewDNAProfile
    |
    +--> JSON output
    +--> review-dna.yml
    +--> reviewer instructions markdown
```

Layers:

- CLI: `scripts/review_dna.py`
- Service: `backend/services/review_dna.py`
- Tests: `backend/tests/test_review_dna.py`
- Generated artifact: `review-dna.yml` when the user explicitly runs `init`

## 6. Monetization / Distribution

Review DNA should stay free and local for this repo.

Distribution angles:

- GitHub README badge: "Review DNA enabled"
- Generated `review-dna.yml` for open-source projects
- CLI output that can be attached to PRs or releases
- Future hosted tier could compare PRs against Review DNA across many repos

## 7. Competitors

| Competitor | What it does | Missing gap | Review DNA angle |
| --- | --- | --- | --- |
| GitHub Copilot | IDE assistance and chat | Not a repo-specific review contract | Portable review rules for this repo |
| Generic AI PR reviewers | Comment on changed code | Often ignore local setup and specs | Deterministic repo profile before review |
| Snyk / security scanners | Security dependency and code checks | Narrow security focus | Product, tests, docs, and local demo gates |
| Linters / CI | Enforce configured rules | No product methodology context | Explains why gates exist and how to review |
| Manual checklists | Human-readable process | Drift from code and CI | Generated from repository evidence |

## 8. Launch Plan

MVP:

- `scan` command emits JSON profile.
- `init` command writes `review-dna.yml` and refuses to overwrite by default.
- `instructions` command prints reviewer-ready Markdown.
- Unit tests cover stack detection, command detection, overwrite safety, and
  instruction rendering.

v0.4:

- Commit a portable `review-dna.yml` with `source_root: "."`.
- Add `check` command that evaluates changed files against Review DNA.
- Produce a project-fit score, status, issues, and recommended commands.
- Keep the check advisory and local-only so a solo developer is not blocked by
  remote branch protection while iterating.

v0.5:

- Add a GitHub Actions advisory check that publishes Review DNA output to the
  PR summary without becoming a required merge gate.
- Add a Review DNA Criteria Pack export that turns the profile into Review
  Passport-ready acceptance criteria.
- Dashboard panel that displays the Review DNA profile.
- Passport integration that imports review rules as acceptance criteria.
- Optional GitHub Action that uploads Review DNA as a PR artifact.

Metrics:

- CLI runs in under 2 seconds on the repo.
- Generated profile includes at least 5 evidence sources.
- Check output explains at least 3 common risks: missing spec, missing tests,
  and local-first regression risk.
- PR advisory check shows Review DNA status and score without blocking a solo
  maintainer when the score is not perfect.
- Criteria Pack output can be pasted into Review Passport as acceptance
  criteria without manual rewriting.
- Tests remain deterministic and require no external services.
- New contributors can run profile generation from a fresh clone.

## 9. Risks

| Risk | Probability | Mitigation |
| --- | --- | --- |
| Profile becomes too generic | Medium | Use concrete detectors and project file evidence |
| YAML output drifts from repo state | Medium | Regenerate via CLI and keep source fields explicit |
| CLI overwrites user edits | Low | Refuse overwrite unless `--force` is passed |
| Scope grows into another review engine | Medium | Keep MVP limited to profile and instructions |
| Check blocks a solo maintainer unnecessarily | Medium | Make CLI advisory in MVP, with explicit status and score |
| GitHub workflow accidentally becomes branch protection friction | Medium | Keep workflow advisory, return success for project-fit WARN/FAIL, and document that it is not required |
| Criteria export becomes vague checklist text | Medium | Generate stable AC ids, concrete criteria, evidence sources, and verification commands |
| Static file checks miss semantic intent | Medium | Phrase output as project-fit evidence, not proof of correctness |
| Generated instructions expose secrets | Low | Only read file names and curated docs, never `.env` values |

## 10. Technical Details

The implementation is local-only Python:

- no database migrations
- no HTTP endpoints
- no frontend changes
- no network access
- no provider credentials

The service should use dataclasses and deterministic filesystem reads. It should
ignore heavy/generated directories such as `.git`, `.pytest_cache`,
`.ruff_cache`, `node_modules`, `dist`, and `__pycache__`.

The CLI must return:

- exit code `0` for successful scan/init/instructions/check execution
- exit code `2` for invalid input, missing profile file, or safe overwrite block

`check` is advisory in the first version. It reads changed file paths from git or
from explicit `--changed-file` arguments, then applies deterministic rules:

- application code changes without tests reduce project-fit score
- behavior changes without spec/idea docs reduce project-fit score
- auth, provider, Docker, settings, or local demo changes require local-first
  evidence
- review analyzer/passport/DNA changes recommend review quality evals

The GitHub Actions slice must call the same deterministic CLI, upload JSON as an
artifact, and write a Markdown summary. Project-fit `WARN` or `FAIL` should be
visible in the PR but should not fail the job; invalid CLI/runtime errors may
still fail so workflow breakage is not hidden.

The Criteria Pack slice should convert Review DNA into a small set of stable
acceptance criteria. These criteria become the bridge between repository-level
methodology and Review Passport's pasted `spec_input` field.

The Criteria artifact slice should make that bridge visible on every PR by
publishing both JSON and Markdown criteria artifacts from the advisory workflow.
This keeps the workflow non-blocking while giving reviewers a ready-made
Review Passport input.

