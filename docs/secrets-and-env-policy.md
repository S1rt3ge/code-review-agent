# Secrets and Environment Policy

This policy separates CI secrets from runtime/deployment secrets.

## 1) Repository Actions secrets (GitHub)

Required for CI workflows:

- `FERNET_KEY`
  - Used by backend tests and encryption utilities.
  - Rotation: every 90 days or after suspected exposure.

Optional workflow secrets:

- Add only if future workflows require external integrations (registry publish, Slack notify, etc.).

## 2) Runtime secrets (deployment platform)

These should be stored in your deployment secret manager (Railway/Vercel/Kubernetes secrets/etc.), **not** in GitHub repository secrets unless a workflow explicitly needs them.

Core production secrets:

- `DATABASE_URL`
- `JWT_SECRET` (must be non-default)
- `GITHUB_WEBHOOK_SECRET`
- `FERNET_KEY`
- `SMTP_HOST` / `SMTP_FROM` / `SMTP_PASSWORD` (if auth flows use email delivery)

Integration/API secrets (if used):

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- `GITHUB_APP_PRIVATE_KEY`
- `GITHUB_CLIENT_SECRET`
- `SMTP_PASSWORD`
- `SENTRY_DSN`

## 3) Rotation and incident response

- Rotate immediately after any suspected leak.
- After rotation, verify:
  - auth flows (`/api/auth/*`)
  - webhook signature validation
  - encrypted settings access
  - CI pipeline health

## 4) Prohibited practices

- Do not commit plaintext secrets to repo.
- Do not store production secrets in `.env.example`.
- Do not paste sensitive values in issue/PR comments.

## 5) Verification checklist

- [ ] `main` branch protection is enabled.
- [ ] Required CI checks configured and passing.
- [ ] `FERNET_KEY` exists in GitHub Actions secrets.
- [ ] Runtime secrets configured in deployment platform.
- [ ] SMTP configured for production, or `SMTP_REQUIRED_IN_PRODUCTION=false` explicitly documented as an accepted exception.
