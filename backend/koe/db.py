"""Koe's per-user tables: Neon when DATABASE_URL is set (survives Render's disk wipes), else one local SQLite file.

The same SQL runs on both (%s placeholders; SQLite gets ?). Times are ISO-8601 UTC text in both, so they compare
as strings. Neon tables: migrations/002_app_chat.sql, 003_accounts.sql, 004_connections.sql, 005_prefs.sql, 006_usage.sql. The approval/activity RPCs stay in store.py.
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
create table if not exists koe_prefs (owner_id text not null, name text not null, value text not null,
  updated text not null, primary key (owner_id, name));
create table if not exists koe_usage (owner_id text not null, day text not null, turns integer not null default 0,
  primary key (owner_id, day));
create table if not exists koe_spotify_flows (state_hash text primary key, owner_id text not null,
  session_hash text not null, cookie_hash text not null, redirect_uri text not null,
  expires text not null, consumed text);
create table if not exists koe_music_mutations (owner_id text not null, connection_id text not null,
  request_id text not null, body_hash text not null, operation text not null,
  state text not null check (state in ('prepared','sent','outcome_unknown','confirmed')),
  evidence_enc text not null, result_enc text, created text not null, updated text not null,
  primary key (owner_id, connection_id, request_id));
"""

# One reused Neon connection. Measured from the laptop: a new connection ~950 ms (TLS + auth to Singapore), a query
# on an open one ~120 ms, a 200 KB voice note ~320 ms. autocommit: each statement is its own transaction.
# prepare_threshold=None: Neon's pooler. ponytail: one connection behind a lock serializes queries; use
# psycopg_pool if traffic ever queues.
_neon: psycopg.Connection | None = None
_neon_lock = threading.Lock()
LOCK_SECONDS = 5  # allow a healthy cold handshake while bounding the queued request
READ_SECONDS = 10


def _run_neon(query: str, params: tuple) -> list[dict]:
    global _neon
    if not _neon_lock.acquire(timeout=LOCK_SECONDS):
        raise psycopg.OperationalError('Database is busy. No new operation was sent.')
    try:
        for attempt in (1, 2):
            if _neon is None or _neon.closed or _neon.broken:
                _neon = psycopg.connect(**store.connection_options(), row_factory=dict_row, autocommit=True,
                                        prepare_threshold=None)
            try:
                with _neon.transaction():
                    _neon.execute('SET LOCAL statement_timeout = 10000')
                    cur = _neon.execute(query, params)
                    return cur.fetchall() if cur.description else []
            except psycopg.OperationalError:
                _neon.close()  # Neon closes idle connections (compute suspend): reconnect next time
                _neon = None
                # Only a read is retried: a write whose commit is uncertain must never run twice (store.py rule).
                if attempt == 2 or not query.lstrip().lower().startswith("select"):
                    raise
    finally:
        _neon_lock.release()
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
    if query.lstrip().lower().startswith('select'):
        try:
            return await asyncio.wait_for(asyncio.to_thread(_run, query, params), READ_SECONDS)
        except TimeoutError:
            raise psycopg.OperationalError('Database read timed out. Try the read again later.') from None
    # Never time out and replay a write whose commit may still be in progress.
    return await asyncio.to_thread(_run, query, params)
