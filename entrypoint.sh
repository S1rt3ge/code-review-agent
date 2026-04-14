#!/bin/sh
set -e

echo "Running database migrations..."
python scripts/migrate.py

echo "Starting application..."
exec uvicorn backend.main:app --host 0.0.0.0 --port "${PORT:-8000}" --workers "${WORKERS:-2}"
