# Alerting Baseline

This document defines the minimum production alerts for the current system.

## Queue alerts

### Queue backlog age

- Trigger when `oldest_pending_age_seconds > 300` for 5+ minutes.
- Severity: **SEV-2** if user-facing review completion is delayed.

### Stale running jobs

- Trigger when `stale_running_count > 0`.
- Severity: **SEV-2** if repeated, otherwise **SEV-3**.

### Queue error growth

- Trigger when `error_count > 0` and increasing over successive checks.
- Severity: **SEV-2** if multiple reviews fail, **SEV-3** for isolated failures.

## Sentry alerts

### Backend exception spike

- Trigger when error rate exceeds baseline for 5 minutes.
- Focus areas:
  - auth failures beyond expected levels
  - webhook parsing/verification failures
  - analysis queue processing exceptions

### Frontend exception spike

- Trigger on sudden increase in React/render/runtime errors.
- Severity depends on affected page(s):
  - login/dashboard/review flow errors => **SEV-2**
  - isolated settings/retryable UX issues => **SEV-3**

## Health endpoint interpretation

- `/health.status == ok`
  - DB connected and queue within safe thresholds.
- `/health.status == degraded`
  - DB disconnected, queue stale jobs present, queue errors present, or backlog age too high.

## Response expectations

- Acknowledge alerts within **15 minutes**.
- Create/append to incident timeline if alert persists beyond **15 minutes**.
- Link relevant Sentry issue and `/health` payload snapshot in incident notes.
