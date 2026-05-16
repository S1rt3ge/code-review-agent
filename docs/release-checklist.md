# Release Checklist

Use this checklist for every release to `main` and production deployment.

## 1) Pre-release

- [ ] `main` is green on required checks.
- [ ] No release-blocking PRs remain open.
- [ ] No open critical incidents.
- [ ] Migrations reviewed for backward compatibility.
- [ ] Security gates pass (`gitleaks`, dependency audits, SBOM job).
- [ ] Changelog updated (`CHANGELOG.md`).
- [ ] Release owner assigned.

## 2) Local verification

- [ ] Backend non-integration tests pass:
  `pytest -m "not integration" --tb=short -q --cov=backend --cov-report=term --cov-fail-under=60`
- [ ] Backend integration tests pass:
  `pytest -m integration --tb=short -q`
- [ ] Backend lint passes:
  `ruff check backend`
- [ ] Frontend tests pass:
  `npm test -- --run --coverage` from `frontend/`.
- [ ] Frontend build passes:
  `npm run build` from `frontend/`.
- [ ] Dependency audits pass:
  `npm audit` from `frontend/` and `python -m pip_audit -r requirements.txt`.

## 3) Productized self-hosted demo gate

- [ ] Docker stack starts with `docker compose up --build`.
- [ ] Local registration and login work with `AUTH_REQUIRE_EMAIL_VERIFICATION=false`.
- [ ] Dashboard `Try demo review` creates a completed local review without SMTP, GitHub, or hosted LLM credentials.
- [ ] Dashboard `Paste diff` creates a local review from user-provided diff text.
- [ ] Review detail page can generate and copy a Review Passport.
- [ ] Repositories page shows webhook setup values and free tunnel options.
- [ ] The release can be evaluated without paid hosting, a paid domain, project-owner API spend, or a paid email provider.

## 4) Versioning and tagging

- [ ] Select version tag (e.g. `v0.3.0`).
- [ ] Ensure tag points to the exact commit intended for release.
- [ ] Confirm target commit has successful required check-runs (`Security Gates`, `SBOM`, `Backend Tests`, `Frontend Build`) before tagging.
- [ ] Confirm release notes summary (highlights, breaking changes, migration notes).
- [ ] Confirm `CHANGELOG.md` has meaningful `[Unreleased]` notes to roll into the release.

## 5) Deployment prep

- [ ] Confirm production env vars are set (DB URL, JWT secret, Sentry DSN, API keys).
- [ ] Confirm DB backup/snapshot policy is in place.
- [ ] Confirm rollback target is known (previous release tag).

## 6) Deploy and verify

- [ ] Trigger release workflow.
- [ ] Watch deployment logs until healthy.
- [ ] Verify health endpoint and core flow:
  - [ ] Login/auth
  - [ ] Review creation/analyze
  - [ ] Dashboard load
  - [ ] GitHub webhook path

## 7) Post-release

- [ ] Monitor Sentry and runtime metrics for 30+ minutes.
- [ ] Confirm `/health` stays `ok` (not `degraded`) after rollout.
- [ ] Confirm queue metrics stay within alert thresholds.
- [ ] Announce release and notable changes.
- [ ] Create follow-up issues for any deferred work.

## 8) Rollback criteria

Rollback immediately if any of the following occur:

- Sustained SEV-1 or SEV-2 impact after hotfix attempt.
- Data integrity concerns or migration incompatibility.
- Authentication or authorization failures affecting users.

Rollback procedure:

1. Redeploy previous stable tag.
2. Validate health and key user flows.
3. Communicate rollback and incident status.
4. Open incident/postmortem issue.
