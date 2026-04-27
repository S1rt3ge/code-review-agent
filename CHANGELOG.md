# Changelog

All notable changes to this project will be documented in this file.

The format is inspired by Keep a Changelog and follows semantic-style sections.

## [Unreleased]

### Added
- Demo Mode seed flow for local self-hosted demos:
  - Adds a guarded `/api/demo/seed` endpoint for non-production environments.
  - Seeds demo repository, reviews, findings, agent executions, and analysis queue records.
  - Adds a dashboard empty-state CTA to load demo data without GitHub or LLM credentials.
- First-run dashboard setup checklist with progress from repository, webhook-readiness, LLM provider, and review data.
- Local demo documentation in `docs/local-demo.md`.
- Release process baseline docs and workflow:
  - `docs/release-checklist.md`
  - `.github/workflows/release.yml`

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
