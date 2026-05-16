# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog and follows semantic-style sections.

## [Unreleased]

### Added
- Productized self-hosted demo release scope:
  - Local Review Playground demo reviews and pasted-diff reviews without GitHub,
    SMTP, hosted LLM keys, or paid infrastructure.
  - First-run dashboard onboarding with setup progress for account,
    repositories, LLM provider status, and first review creation.
  - Repository setup polish with skeleton loading, retryable error state, and
    mobile-friendly connected repository cards.
  - Review Passport generation with acceptance-criteria coverage,
    anti-AI-slop signals, manual QA steps, Markdown export, PR comment posting,
    and optional GitHub commit-status gate publishing.
  - Deterministic review quality eval harness for local regression checks.
- Release process baseline docs and workflow:
  - `docs/release-checklist.md`
  - `.github/workflows/release.yml`
- Productized self-hosted demo documentation:
  - README quick path for running the local demo in 5 minutes.
  - `docs/local-demo.md`
  - `docs/webhook-tunnel.md`
  - `docs/ollama-setup.md`
  - `docs/v0.2-roadmap.md`

### Changed
- Local Docker/demo setup can disable email verification with
  `AUTH_REQUIRE_EMAIL_VERIFICATION=false`, keeping registration and login usable
  without a paid SMTP provider.
- Settings and repository setup copy now emphasize BYOK/local Ollama and free
  webhook tunnel options for self-hosted evaluation.

## [2026-04-16]

### Added
- Authentication hardening and account lifecycle:
  - Password reset request/confirm endpoints.
  - Email verification request/confirm endpoints.
  - Login/protected access enforcement for verified email.
- Durable analysis queue:
  - DB-backed `analysis_jobs` model and migration.
  - Queue worker startup/shutdown lifecycle with retry/backoff.
- Startup recovery:
  - Automatic recovery of stuck `analyzing` reviews.
- Security and observability:
  - Auth rate limiting with SlowAPI.
  - Sentry integration (backend + frontend).
  - Startup fail-fast for default `JWT_SECRET` outside dev/test.
- CI security gates:
  - Secret scanning (`gitleaks`).
  - Dependency audits (`pip-audit`, `npm audit`).
  - SBOM generation and artifact upload.
- Repository governance:
  - CODEOWNERS.
  - Branch protection policy and governance checklist.
- Automation hygiene:
  - Dependabot config.
  - PR path labeler workflow/config.
  - Pull request release-note template.
- Security/operations docs:
  - `SECURITY.md`.
  - Incident response runbook.

### Changed
- CI runs both non-integration and integration backend test sets.
- CI now enforces full `ruff check backend`.
- Frontend tests in CI are fail-fast (no `continue-on-error`).

### Notes
- This entry captures the production-hardening milestone consolidated across PRs #7, #8, #9, #10, and #16.
