"""Run all pending SQL migrations in order.

Usage:
    python scripts/migrate.py

Reads DATABASE_URL from environment. Applies every *.sql file in
supabase/migrations/ in lexicographic order, skipping files that have
already been recorded in the schema_migrations table.
"""

import asyncio
import os
import sys
from pathlib import Path

import asyncpg


MIGRATIONS_DIR = Path(__file__).parent.parent / "supabase" / "migrations"
PROJECT_ROOT = Path(__file__).parent.parent
MIGRATION_LOCK_ID = 42424242


def _load_dotenv() -> None:
    """Load a local .env file when DATABASE_URL was not exported."""
    if os.environ.get("DATABASE_URL"):
        return

    env_path = PROJECT_ROOT / ".env"
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


def _normalize_database_url(url: str) -> str:
    """Normalize SQLAlchemy/PaaS postgres URLs for asyncpg."""
    if url.startswith("postgresql+psycopg://"):
        return url.replace("postgresql+psycopg://", "postgresql://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql://", 1)
    return url


async def run() -> None:
    _load_dotenv()
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        sys.exit(1)

    url = _normalize_database_url(url)

    conn = await asyncpg.connect(url)
    lock_acquired = False
    try:
        await conn.execute("SELECT pg_advisory_lock($1)", MIGRATION_LOCK_ID)
        lock_acquired = True

        await conn.execute("""
            CREATE TABLE IF NOT EXISTS schema_migrations (
                filename TEXT PRIMARY KEY,
                applied_at TIMESTAMPTZ NOT NULL DEFAULT now()
            )
        """)

        applied = {
            row["filename"]
            for row in await conn.fetch("SELECT filename FROM schema_migrations")
        }

        migration_files = sorted(MIGRATIONS_DIR.glob("*.sql"))
        if not migration_files:
            print("No migration files found.")
            return

        for path in migration_files:
            if path.name in applied:
                print(f"  skip  {path.name}")
                continue
            print(f"  apply {path.name} ... ", end="", flush=True)
            sql = path.read_text(encoding="utf-8")
            async with conn.transaction():
                await conn.execute(sql)
                await conn.execute(
                    "INSERT INTO schema_migrations (filename) VALUES ($1)", path.name
                )
            print("done")

        print("Migrations complete.")
    finally:
        if lock_acquired:
            await conn.execute("SELECT pg_advisory_unlock($1)", MIGRATION_LOCK_ID)
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
