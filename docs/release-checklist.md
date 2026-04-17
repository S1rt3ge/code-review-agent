# Release Checklist

Use this checklist for every release to `main` and production deployment.

## 1) Pre-release

- [ ] `main` is green on required checks.
- [ ] No open critical incidents.
- [ ] Migrations reviewed for backward compatibility.
- [ ] Security gates pass (`gitleaks`, dependency audits, SBOM job).
- [ ] Changelog updated (`CHANGELOG.md`).
- [ ] Release owner assigned.

## 2) Versioning and tagging

- [ ] Select version tag (e.g. `v0.3.0`).
- [ ] Ensure tag points to the exact commit intended for release.
- [ ] Confirm target commit has successful required checks before tagging.
- [ ] Confirm release notes summary (highlights, breaking changes, migration notes).

## 3) Deployment prep

- [ ] Confirm production env vars are set (DB URL, JWT secret, Sentry DSN, API keys).
- [ ] Confirm DB backup/snapshot policy is in place.
- [ ] Confirm rollback target is known (previous release tag).

## 4) Deploy and verify

- [ ] Trigger release workflow.
- [ ] Watch deployment logs until healthy.
- [ ] Verify health endpoint and core flow:
  - [ ] Login/auth
  - [ ] Review creation/analyze
  - [ ] Dashboard load
  - [ ] GitHub webhook path

## 5) Post-release

- [ ] Monitor Sentry and runtime metrics for 30+ minutes.
- [ ] Confirm `/health` stays `ok` (not `degraded`) after rollout.
- [ ] Confirm queue metrics stay within alert thresholds.
- [ ] Announce release and notable changes.
- [ ] Create follow-up issues for any deferred work.

## 6) Rollback criteria

Rollback immediately if any of the following occur:

- Sustained SEV-1 or SEV-2 impact after hotfix attempt.
- Data integrity concerns or migration incompatibility.
- Authentication or authorization failures affecting users.

Rollback procedure:

1. Redeploy previous stable tag.
2. Validate health and key user flows.
3. Communicate rollback and incident status.
4. Open incident/postmortem issue.
