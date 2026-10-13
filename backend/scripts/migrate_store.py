"""Apply the additive Neon schema using backend/.env; never print the connection string.

Run from backend/: python -m scripts.migrate_store
"""
from pathlib import Path

import psycopg

from koe import store


def main():
    try:
        options = store.connection_options()
        migration = (Path(__file__).resolve().parents[1] / "migrations/001_phase2.sql").read_text(encoding="utf-8")
        # The file owns BEGIN/COMMIT. No runtime request applies schema changes.
        with psycopg.connect(**options, autocommit=True) as con:
            con.execute(migration, prepare=False)
        print("PASS Neon: schema applied; existing rows retained. No external tools were called.")
        return 0
    except (psycopg.Error, store.StoreError):
        print("FAIL Neon migration: check DATABASE_URL, database ownership, SSL and network. Credentials were not printed.")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
