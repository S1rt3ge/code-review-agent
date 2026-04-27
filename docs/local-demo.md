# Local Demo

Run a productized self-hosted demo without paid hosting, a paid domain, GitHub App credentials, webhook setup, or hosted LLM keys.

## What Demo Mode Seeds

- One demo repository: `demo-org/checkout-service`.
- Three completed pull request reviews.
- Seven realistic findings across security, performance, style, and logic agents.
- Agent execution records for each review.
- Completed analysis queue records so dashboard queue metrics have real data.

## Start Backend

```bash
docker compose up -d postgres
python scripts/migrate.py
uvicorn backend.main:app --reload
```

The default local environment is `APP_ENV=development`, which allows demo seeding. Demo seeding is blocked in environments such as `production` and `staging`.

## Start Frontend

```bash
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`.

## Load Demo Data

1. Create a local account.
2. Sign in.
3. Open the dashboard.
4. Click `Load demo data` in the empty state.
5. The app opens the first seeded review detail page.

No real GitHub repository, webhook secret, tunnel URL, Claude key, OpenAI key, or Ollama server is required for this flow.

## API Endpoint

Authenticated users can also seed demo data directly:

```bash
curl -X POST http://localhost:8000/api/demo/seed \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d "{}"
```

The endpoint is idempotent for the current user. Running it again refreshes the deterministic demo records instead of creating duplicate review history.

## Environment Guard

Demo seeding is allowed only when `APP_ENV` is one of:

- `development`
- `dev`
- `local`
- `demo`
- `test`
- `testing`

In any other environment, `/api/demo/seed` returns `403`.
