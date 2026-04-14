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


async def run() -> None:
    url = os.environ.get("DATABASE_URL", "")
    if not url:
        print("ERROR: DATABASE_URL is not set", file=sys.stderr)
        sys.exit(1)

    # asyncpg uses postgresql:// not postgresql+psycopg://
    url = url.replace("postgresql+psycopg://", "postgresql://")

    conn = await asyncpg.connect(url)
    try:
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
        await conn.close()


if __name__ == "__main__":
    asyncio.run(run())
