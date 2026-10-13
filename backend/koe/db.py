"""Koe's per-user tables: Neon when DATABASE_URL is set (survives Render's disk wipes), else one local SQLite file.

The same SQL runs on both (%s placeholders; SQLite gets ?). Times are ISO-8601 UTC text in both, so they compare
as strings. Neon tables: migrations/002_app_chat.sql, 003_accounts.sql, 004_connections.sql. The approval/activity RPCs stay in store.py.
"""
import asyncio
import sqlite3
import threading
from contextlib import closing
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

from koe import store

DATA = Path(__file__).resolve().parent.parent / "data"  # backend/data, git-ignored
DB = DATA / "app.db"

SQLITE_SCHEMA = """
create table if not exists koe_app_messages (id integer primary key autoincrement, owner_id text not null,
  ts text not null, role text not null, text text not null default '', voice text, action_id text, action_status text);
create table if not exists koe_app_voice (name text primary key, owner_id text not null, created text not null,
  audio blob not null);
create table if not exists koe_app_push (endpoint text primary key, owner_id text not null, subscription text not null);
create table if not exists koe_users (id text primary key, google_sub text unique not null, email text not null,
  name text not null default '', created text not null);
create table if not exists koe_invites (email text primary key, invited_by text not null, created text not null);
create table if not exists koe_sessions (token_hash text primary key, user_id text not null, created text not null,
  expires text not null, revoked text);
create table if not exists koe_connections (owner_id text not null, provider text not null, account text not null default '',
  scopes text not null default '', token_enc text not null, created text not null, updated text not null,
  primary key (owner_id, provider));
"""

# One reused Neon connection. Measured from the laptop: a new connection ~950 ms (TLS + auth to Singapore), a query
# on an open one ~120 ms, a 200 KB voice note ~320 ms. autocommit: each statement is its own transaction.
# prepare_threshold=None: Neon's pooler. ponytail: one connection behind a lock serializes queries; use
# psycopg_pool if traffic ever queues.
_neon: psycopg.Connection | None = None
_neon_lock = threading.Lock()


def _run_neon(query: str, params: tuple) -> list[dict]:
    global _neon
    with _neon_lock:
        for attempt in (1, 2):
            if _neon is None or _neon.closed or _neon.broken:
                _neon = psycopg.connect(**store.connection_options(), row_factory=dict_row, autocommit=True,
                                        prepare_threshold=None)
            try:
                cur = _neon.execute(query, params)
                return cur.fetchall() if cur.description else []
            except psycopg.OperationalError:
                _neon.close()  # Neon closes idle connections (compute suspend): reconnect next time
                _neon = None
                # Only a read is retried: a write whose commit is uncertain must never run twice (store.py rule).
                if attempt == 2 or not query.lstrip().lower().startswith("select"):
                    raise
    return []


def _run(query: str, params: tuple) -> list[dict]:
    if store.configured():
        return _run_neon(query, params)
    DB.parent.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(DB)) as con, con:
        con.row_factory = sqlite3.Row
        con.executescript(SQLITE_SCHEMA)
        cur = con.execute(query.replace("%s", "?"), params)
        return [dict(r) for r in cur.fetchall()] if cur.description else []


async def sql(query: str, *params) -> list[dict]:
    """One statement, off the event loop: a Neon round trip must not stall a call or other requests."""
    return await asyncio.to_thread(_run, query, params)
