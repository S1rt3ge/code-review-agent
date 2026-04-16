# Repository Governance Checklist

Use this checklist when bootstrapping a new environment or auditing repo controls.

## Access and reviews

- [ ] `main` is protected with PR-only merges.
- [ ] At least one required approval is enforced.
- [ ] CODEOWNERS review is required.
- [ ] Direct push to `main` is blocked.

## CI and security gates

- [ ] Required checks include:
  - [ ] `CI / Security Gates`
  - [ ] `CI / SBOM`
  - [ ] `CI / Backend Tests (Python 3.12)`
  - [ ] `CI / Frontend Build`
- [ ] Secret scanning alerts are enabled.
- [ ] Dependency security alerts are enabled.

## Runtime and secrets hygiene

- [ ] Production `JWT_SECRET` is non-default.
- [ ] Production secrets are stored in provider secret manager (not plaintext env files in repo).
- [ ] Sentry DSN configured for production.

## Evidence

- [ ] Link to latest successful CI run:
- [ ] Date of last governance review:
- [ ] Reviewer:
