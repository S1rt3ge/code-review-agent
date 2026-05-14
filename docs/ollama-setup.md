# Ollama Setup

Ollama is the recommended free/local LLM path for the self-hosted demo. It keeps model execution on your own machine or server and does not require Claude or OpenAI API keys.

## Install Ollama

Install Ollama from the official download page for your operating system.

After installing, verify it works:

```bash
ollama --version
```

## Pull A Code Model

Recommended starting point:

```bash
ollama pull qwen2.5-coder:7b
```

Other useful options:

- `qwen2.5-coder:3b`: faster and lighter for small machines.
- `qwen2.5-coder:7b`: balanced local demo default.
- `qwen2.5-coder:32b`: higher quality, requires substantially more memory.

## Run Locally With The Backend On The Same Machine

Start Ollama normally:

```bash
ollama serve
```

In the app, open `Settings`, enable `Local Ollama`, and use:

```text
http://localhost:11434
```

Click `Test LLM Connection` to confirm the backend can reach Ollama.

## Run With Docker Or A Remote Backend

If the backend is not running on the same host as Ollama, `localhost:11434` from the backend points to the backend machine, not your laptop.

Use one of these options:

- Run Ollama on the same host as the backend.
- Expose Ollama through a private network/VPN you control.
- Use a temporary tunnel for demos.

For temporary demo tunnels, start Ollama with permissive origins:

```bash
OLLAMA_ORIGINS=* ollama serve
```

Then expose port `11434`:

```bash
cloudflared tunnel --url http://localhost:11434
```

Or:

```bash
ngrok http 11434
```

Paste the generated HTTPS URL into `Settings` > `Local Ollama`.

## BYOK Hosted Providers

Claude and OpenAI are optional bring-your-own-key providers. Keys are encrypted server-side before storage. Usage is billed to your own Anthropic/OpenAI account based on each provider's pricing and token usage.

You do not need hosted keys for the local demo path if Ollama is available.

## Troubleshooting

### Ollama Not Available

- Confirm `ollama serve` is running.
- Confirm the host URL is reachable from the backend process.
- If using Docker, do not assume container `localhost` can reach host `localhost`.
- Pull at least one model with `ollama pull qwen2.5-coder:7b`.

### URL Rejected By Settings

- Local/private hosts are allowed in development and test environments.
- Non-development deployments reject private hosts unless explicitly configured with `ALLOW_PRIVATE_OLLAMA_HOSTS=true`.

### Slow Reviews

- Use `qwen2.5-coder:3b` on smaller machines.
- Close other memory-heavy applications.
- Use a hosted BYOK provider if local hardware is too constrained.
