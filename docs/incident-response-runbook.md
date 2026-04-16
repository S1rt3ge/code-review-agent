# Incident Response Runbook

This runbook covers detection, containment, recovery, and postmortem for production incidents.

## Severity levels

- **SEV-1**: Full outage, data loss risk, or active security incident.
- **SEV-2**: Major feature degradation with user impact.
- **SEV-3**: Partial degradation or non-critical issue.

## First 15 minutes

1. **Acknowledge** incident and assign incident commander.
2. **Classify severity** and create incident timeline document.
3. **Stabilize communications** (single owner for status updates).
4. **Collect signals**:
   - API health (`/health`)
   - CI deployment history
   - Sentry spikes/errors
   - DB availability and connection pool saturation

## Containment actions

- If webhook storm or queue overload:
  - Temporarily disable repository integration for noisy repos.
  - Scale down analysis concurrency by adjusting queue settings.
- If auth/security anomaly:
  - Rotate affected credentials/secrets.
  - Revoke compromised API tokens.
  - Tighten ingress/rate limits immediately.
- If bad deploy:
  - Roll back to last known-good deployment.

## Recovery checklist

- [ ] Service health endpoints green
- [ ] Background analysis queue draining normally
- [ ] Error rate and latency returned to baseline
- [ ] User-facing functionality validated (login, dashboard, review flow)
- [ ] Monitoring/alerts stable for at least 30 minutes

## Communication template

- **Status**: Investigating | Identified | Monitoring | Resolved
- **Impact**: who/what is affected
- **Scope**: API, frontend, queue, database, integrations
- **ETA**: next update time

## Postmortem (within 48 hours)

- Incident summary and root cause
- Customer impact and duration
- What worked / what failed in response
- Corrective actions with owners and due dates
- Follow-up tasks tracked in GitHub issues
