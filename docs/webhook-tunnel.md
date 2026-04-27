# Local Webhook Tunnel

Use this guide to receive real GitHub pull request webhooks while the backend runs on your own machine. No paid hosting, paid domain, or GitHub App hosting is required.

## Prerequisites

- Backend running on `http://localhost:8000`.
- A GitHub repository you can configure webhooks for.
- A shared webhook secret set in your backend `.env` as `GITHUB_WEBHOOK_SECRET`.

Use a long random value for the secret. The exact same value must be pasted into GitHub.

## Backend URL

The app receives pull request webhooks at:

```text
/api/github/webhook
```

When running locally, GitHub cannot reach `localhost`, so expose the backend with a free tunnel and use:

```text
https://<your-tunnel-host>/api/github/webhook
```

## Option A: Cloudflare Tunnel

Cloudflare Tunnel can create a temporary `trycloudflare.com` URL without buying a domain.

1. Install `cloudflared` from Cloudflare's official downloads page.
2. Start the backend locally:

```bash
uvicorn backend.main:app --reload
```

3. Start the tunnel:

```bash
cloudflared tunnel --url http://localhost:8000
```

4. Copy the generated `https://....trycloudflare.com` URL.
5. Use `https://....trycloudflare.com/api/github/webhook` as the GitHub webhook payload URL.

## Option B: ngrok

ngrok is quick for local testing. The free URL may change after restart.

1. Install ngrok.
2. Start the backend locally:

```bash
uvicorn backend.main:app --reload
```

3. Start the tunnel:

```bash
ngrok http 8000
```

4. Copy the generated `https://....ngrok-free.app` URL.
5. Use `https://....ngrok-free.app/api/github/webhook` as the GitHub webhook payload URL.

## GitHub Webhook Settings

In GitHub, open your repository and go to `Settings` > `Webhooks` > `Add webhook`.

Use these values:

- Payload URL: `https://<your-tunnel-host>/api/github/webhook`
- Content type: `application/json`
- Secret: the exact value of `GITHUB_WEBHOOK_SECRET`
- SSL verification: enabled
- Events: `Let me select individual events`, then select `Pull requests`
- Active: checked

## Test Delivery

After saving the webhook, GitHub sends a `ping` event. The backend should return `202` for valid signed deliveries.

To trigger a real review event, open or update a pull request in the configured repository.

## Troubleshooting

### 401 Invalid Webhook Signature

- Confirm `GITHUB_WEBHOOK_SECRET` is set in the backend environment.
- Confirm the same secret is pasted into GitHub with no extra spaces.
- Restart the backend after changing `.env`.
- Confirm GitHub includes `X-Hub-Signature-256` in the delivery headers.

### 404 Repository Not Configured

- Add the repository in the app's `Repositories` page first.
- Make sure the owner and repository name match GitHub exactly.
- Make sure the repository is enabled in the app.

### Tunnel URL Works In Browser But GitHub Fails

- Confirm the payload URL includes `/api/github/webhook`.
- Confirm the tunnel points to backend port `8000`, not frontend port `5173`.
- Check tunnel logs for blocked or failed requests.
- If using ngrok, update GitHub after restarting ngrok because the URL may change.

### Webhook Is Accepted But No Review Appears

- Confirm the GitHub event is `pull_request`.
- Confirm the pull request action is `opened` or `synchronize`.
- Check backend logs for queue or analysis errors.
