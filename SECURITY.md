# Security Policy

## Supported versions

| Version | Supported |
|---|---|
| `main` | :white_check_mark: |
| Earlier commits/releases | :x: |

## Reporting a vulnerability

Please **do not** open public issues for security vulnerabilities.

Use one of the following private channels:

1. Preferred: GitHub Security Advisory ("Report a vulnerability")
   - https://github.com/S1rt3ge/code-review-agent/security/advisories/new
2. If advisory flow is unavailable, contact maintainer privately and include "[SECURITY]" in the subject.

## What to include in reports

- Affected component(s) and environment
- Reproduction steps or proof-of-concept
- Impact assessment (data exposure, privilege escalation, DoS, etc.)
- Suggested mitigation, if known

## Response targets

- Initial acknowledgement: within **72 hours**
- Triage and severity assessment: within **7 days**
- Fix timeline:
  - Critical: as soon as possible, target <= 7 days
  - High: target <= 14 days
  - Medium/Low: scheduled in normal release cycle

## Disclosure policy

- Vulnerabilities are disclosed after a fix is available and users have had a reasonable upgrade window.
- Coordinated disclosure is preferred.

## Security hardening recommendations for operators

- Use non-default `JWT_SECRET` in production.
- Store secrets in deployment secret managers, not plaintext files.
- Enable Sentry in production for rapid anomaly detection.
- Keep dependency updates enabled (Dependabot + CI security gates).
