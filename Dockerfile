# ── Stage 1: Build React frontend ────────────────────────────────────────────
FROM node:20-alpine AS frontend-builder

WORKDIR /frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --legacy-peer-deps

COPY frontend/ ./
RUN npm run build


# ── Stage 2: Production backend ──────────────────────────────────────────────
FROM python:3.12-slim AS backend

# System deps for psycopg binary wheel
RUN apt-get update && apt-get install -y --no-install-recommends \
    libpq5 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend source
COPY backend/ ./backend/
COPY supabase/migrations/ ./supabase/migrations/
COPY scripts/ ./scripts/
COPY entrypoint.sh ./entrypoint.sh

# Copy built frontend assets (can be served by a reverse-proxy or FastAPI StaticFiles)
COPY --from=frontend-builder /frontend/dist ./frontend/dist

# Non-root user for security
RUN useradd -m -u 1001 appuser \
    && chown -R appuser /app \
    && chmod +x /app/entrypoint.sh

USER appuser

EXPOSE 8000

# Runs migrations then starts the server
CMD ["/app/entrypoint.sh"]
