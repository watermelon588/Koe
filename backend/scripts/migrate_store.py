"""Apply the additive Neon schema using backend/.env; never print the connection string.

Run from backend/: python -m scripts.migrate_store
"""
from pathlib import Path

import psycopg

from koe import store


def main():
    try:
        options = store.connection_options()
        # Every file is additive and rerunnable, applied in name order; each owns its BEGIN/COMMIT.
        # No runtime request applies schema changes.
        migrations = sorted((Path(__file__).resolve().parents[1] / "migrations").glob("*.sql"))
        with psycopg.connect(**options, autocommit=True) as con:
            for migration in migrations:
                con.execute(migration.read_text(encoding="utf-8"), prepare=False)
                print(f"applied {migration.name}")
        print("PASS Neon: schema applied; existing rows retained. No external tools were called.")
        return 0
    except (psycopg.Error, store.StoreError):
        print("FAIL Neon migration: check DATABASE_URL, database ownership, SSL and network. Credentials were not printed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
