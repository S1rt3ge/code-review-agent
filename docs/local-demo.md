# Local Demo Walkthrough

This walkthrough keeps the product usable without paid email delivery, GitHub App setup, or hosted LLM credentials.

## Start The Stack

```bash
docker compose up --build
```

Open:

- App: `http://localhost:5173`
- API health: `http://localhost:8000/health`

Docker defaults to `AUTH_REQUIRE_EMAIL_VERIFICATION=false`, so local registration and login work without SMTP.

## Create A Local Review

1. Open `http://localhost:5173`.
2. Register a local account.
3. On the dashboard, click `Try demo review`.
4. Open the generated review detail page.

The demo review uses the deterministic Local Review Playground analyzer. It should finish without GitHub, SMTP, OpenAI, Anthropic, or Ollama.

## Generate A Review Passport

On the review detail page, use the Review Passport panel to generate a merge-readiness artifact.

For the bundled demo review, useful sample criteria are:

```text
- Remove unsafe dynamic execution
- Do not expose hardcoded secrets
- Add coverage for dangerous input handling
```

Expected result for the bundled demo review:

- verdict: `BLOCKED`
- confidence: low
- anti-slop signals include missing test evidence and unsafe implementation evidence
- QA script starts with `docker compose up --build`

This is intentional. The demo diff contains risky code so the passport proves that the product blocks weak AI-generated or under-tested changes instead of producing a generic approval.

## Paste Your Own Diff

1. From your local repository, copy a unified diff.
2. In the dashboard, click `Paste diff`.
3. Paste the diff and submit it.
4. Open the review detail page.
5. Generate a Review Passport with acceptance criteria from your issue/spec.

The pasted-diff path is the fastest way to test the product against real local work without wiring GitHub webhooks.

## Share The Passport

Use `Copy Markdown` in the Review Passport panel to copy a portable report with verdict, criteria coverage, anti-slop signals, and QA steps.

The panel also shows the derived gate status. `READY` maps to a passing GitHub commit status, while `READY_WITH_RISKS` and `BLOCKED` map to failing statuses.

For local playground reviews, GitHub posting and `Publish Gate` are intentionally unavailable because the review is backed by `local://playground`. For GitHub-backed reviews with a configured GitHub App installation, `Post to PR` creates or updates a dedicated Review Passport comment on the pull request, and `Publish Gate` posts the `AI Review Passport Gate` commit status to the PR head SHA.

## Stop The Stack

```bash
docker compose down
```

To remove local database data too:

```bash
docker compose down -v
```

## Troubleshooting

If registration asks for email verification, confirm the backend is running with:

```bash
AUTH_REQUIRE_EMAIL_VERIFICATION=false
```

If the app loads but API calls fail, check:

```bash
docker compose ps
```

Then open `http://localhost:8000/health` and confirm `database.status` is `connected`.
