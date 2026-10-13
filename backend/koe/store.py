"""Backend-only Neon PostgreSQL store. SQL functions own atomic approval transitions.

Blocking connections run off the event loop (including Windows' Proactor loop).
Each connection context commits on success, rolls back on error, and closes.
https://www.psycopg.org/psycopg3/docs/basic/transactions.html
"""
import asyncio
import logging
import threading
import time
from contextlib import contextmanager

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

from koe import identity
from koe.config import settings

log = logging.getLogger("koe.store")
RPC_PARAMS = {
    "koe_propose_action": ("p_session", "p_channel", "p_tool", "p_args", "p_summary"),
    "koe_claim_action": ("p_id", "p_session", "p_approve"),
    "koe_finish_action": ("p_id", "p_session", "p_ok", "p_result"),
    "koe_record_activity": ("p_channel", "p_session", "p_kind", "p_summary", "p_payload"),
}
TABLES = ("koe_activity", "koe_pending_actions", "koe_daily_notes", "koe_github_deliveries",
          "koe_app_messages", "koe_app_voice", "koe_app_push")


class StoreError(Exception):
    pass


def configured() -> bool:
    return bool(settings.database_url)


def connection_options() -> dict:
    if not configured():
        raise StoreError("Neon is not configured; set DATABASE_URL in backend/.env.")
    try:
        options = conninfo_to_dict(settings.database_url)
    except psycopg.Error:
        raise StoreError("DATABASE_URL must be a valid PostgreSQL connection string.") from None
    if not options.get("host") or options.get("sslmode") not in {"require", "verify-ca", "verify-full"}:
        raise StoreError("DATABASE_URL must specify a host and require SSL (sslmode=require or verify-full).")
    # Neon PgBouncer rejects libpq's `options` startup parameter. Set the timeout
    # inside each transaction instead; preserve SSL/channel-binding parameters.
    options.update(connect_timeout=10, application_name="koe")
    return options


# One reused connection for every call below. Measured 2026-10-13: opening a new one costs ~1.3 s (TLS + auth to
# Neon in Singapore), a statement on an open one ~0.12 s, and a chat turn makes 3+ activity writes. Each use is
# still one transaction (commit on success, rollback on error), exactly like `with psycopg.connect()` was; a failed
# write is never retried. ponytail: one connection behind a lock serializes statements; psycopg_pool if that queues.
IDLE_RECONNECT = 240  # Neon suspends idle compute after ~5 min: reconnect first rather than write down a dead line
_con: psycopg.Connection | None = None
_con_used = 0.0
_con_lock = threading.Lock()


@contextmanager
def _connection(options: dict):
    global _con, _con_used
    with _con_lock:
        if _con is None or _con.closed or _con.broken or time.monotonic() - _con_used > IDLE_RECONNECT:
            if _con is not None:
                _con.close()
            _con = psycopg.connect(**options, autocommit=True, prepare_threshold=None)
        try:
            with _con.transaction():
                yield _con
        except psycopg.OperationalError:
            _con.close()
            _con = None
            raise
        finally:
            _con_used = time.monotonic()


async def rpc(name: str, **params):
    if name not in RPC_PARAMS or set(params) != set(RPC_PARAMS[name]):
        raise StoreError("Unsupported database operation.")
    options = connection_options()
    values = {"p_owner": identity.owner_id(), **params}
    values = {key: Jsonb(value) if isinstance(value, dict) else value for key, value in values.items()}
    # Both identifiers and parameters are fixed by this module, never supplied by the browser/model.
    assignments = sql.SQL(", ").join(
        sql.SQL("{} => {}").format(sql.Identifier(key), sql.Placeholder(key)) for key in values
    )
    query = sql.SQL("SELECT public.{}({})").format(sql.Identifier(name), assignments)

    def execute():
        try:
            with _connection(options) as con:
                con.execute("SET LOCAL statement_timeout = 10000")
                return con.execute(query, values).fetchone()[0]
        except psycopg.Error:
            # An uncertain commit must never result in an automatic retry of a write.
            raise StoreError("Neon database operation failed; check connectivity and migration; no action was retried.") from None

    return await asyncio.to_thread(execute)


async def propose(session: str, channel: str, tool: str, args: dict, summary: str) -> dict:
    return await rpc("koe_propose_action", p_session=session, p_channel=channel,
                     p_tool=tool, p_args=args, p_summary=summary)


async def claim(action_id: str, session: str, approve: bool) -> dict | None:
    return await rpc("koe_claim_action", p_id=action_id, p_session=session, p_approve=approve)


async def finish(action_id: str, session: str, result: dict) -> dict:
    return await rpc("koe_finish_action", p_id=action_id, p_session=session,
                     p_ok="error" not in result, p_result=result)


async def record(channel: str, session: str, kind: str, summary: str, payload: dict | None = None):
    if configured():
        await rpc("koe_record_activity", p_channel=channel, p_session=session,
                  p_kind=kind, p_summary=summary[:2000], p_payload=payload or {})


async def record_best_effort(*args, **kwargs):
    try:
        await record(*args, **kwargs)
    except StoreError:
        log.warning("Activity could not be saved to Neon")


_background: set[asyncio.Task] = set()
MAX_BACKGROUND = 128


def record_later(*args, **kwargs) -> bool:
    """The activity log is an audit trail, not part of the answer: write it without making the turn wait
    (~0.4 s per record). Proposals, claims and results are never written this way."""
    if not configured():
        return False
    if len(_background) >= MAX_BACKGROUND:
        log.warning('Activity backlog full; best-effort record skipped')
        return False
    task = asyncio.create_task(record_best_effort(*args, **kwargs))
    _background.add(task)  # keep a reference so it isn't garbage-collected mid-write
    task.add_done_callback(_audit_done)
    return True


def _audit_done(task):
    _background.discard(task)
    if not task.cancelled() and task.exception() is not None:
        log.warning('Background activity record failed')  # never log private exception bodies


async def drain_background(timeout=5) -> int:
    """Best-effort shutdown drain; durable approval writes never enter this queue.

    Cancelling a to_thread await cannot interrupt an SQL request already in flight.
    Existing connection/statement timeouts still bound that work; it is never replayed.
    """
    tasks = {t for t in _background if t.get_loop() is asyncio.get_running_loop() and not t.done()}
    if not tasks:
        return 0
    _, pending = await asyncio.wait(tasks, timeout=timeout)
    if pending:
        log.warning('Shutdown activity drain expired; %d best-effort records remain', len(pending))
        for task in pending:
            task.cancel()
        await asyncio.gather(*pending, return_exceptions=True)
    return len(pending)


async def dashboard_read() -> dict:
    """Owner-scoped display fields as JSON; never execution args or backend secrets."""
    if not configured():
        return {"activity": [], "pending": []}
    options = connection_options()
    owner = identity.owner_id()

    def read():
        try:
            with _connection(options) as con:
                con.execute("SET LOCAL statement_timeout = 10000")
                queries = {
                    "activity": """SELECT to_jsonb(display) FROM (
                        SELECT id,session_id,channel,kind,summary,ts,latency_json
                        FROM public.koe_activity WHERE owner_id=%(owner)s ORDER BY ts DESC LIMIT 50
                    ) AS display""",
                    "pending": """SELECT to_jsonb(display) FROM (
                        SELECT id,session_id,channel,summary,expires_ts,status
                        FROM public.koe_pending_actions WHERE owner_id=%(owner)s AND status='pending'
                        ORDER BY created_ts DESC LIMIT 50
                    ) AS display""",
                }
                return {name: [row[0] for row in con.execute(query, {"owner": owner}).fetchall()]
                        for name, query in queries.items()}
        except psycopg.Error:
            raise StoreError("Saved dashboard activity is unavailable. Check Neon connectivity and migration.") from None

    return await asyncio.to_thread(read)


async def check_connection() -> None:
    """Read-only check of all tables, without exposing any stored data."""
    options = connection_options()

    def read():
        try:
            with _connection(options) as con:
                con.execute("SET LOCAL statement_timeout = 10000")
                for table in TABLES:
                    con.execute(sql.SQL("SELECT 1 FROM public.{} LIMIT 0").format(sql.Identifier(table)))
        except psycopg.Error:
            raise StoreError("Neon connection/schema check failed; check DATABASE_URL and run the migration.") from None

    await asyncio.to_thread(read)


async def pending_for_session(session: str) -> dict | None:
    """Private server-side hydration, including execution args; never return this row to the browser."""
    if not configured():
        return None
    options, owner = connection_options(), identity.owner_id()

    def read():
        try:
            with _connection(options) as con:
                con.execute('SET LOCAL statement_timeout = 10000')
                row = con.execute("""SELECT to_jsonb(p) FROM public.koe_pending_actions p
                    WHERE owner_id=%s AND session_id=%s AND status='pending'
                    AND expires_ts > now() ORDER BY created_ts DESC LIMIT 1""", (owner, session)).fetchone()
                return row[0] if row else None
        except psycopg.Error:
            raise StoreError('Pending Notion approval could not be loaded. Check Neon.') from None

    return await asyncio.to_thread(read)


async def notion_activity() -> list[dict]:
    """Display-only Notion audit history; never return stored arguments or result payloads."""
    if not configured():
        return []
    options, owner = connection_options(), identity.owner_id()

    def read():
        try:
            with _connection(options) as con:
                con.execute('SET LOCAL statement_timeout = 10000')
                rows = con.execute("""SELECT to_jsonb(display) FROM (
                    SELECT a.id,a.ts,a.kind,a.summary,p.tool
                    FROM public.koe_activity a LEFT JOIN public.koe_pending_actions p
                      ON p.owner_id=a.owner_id AND p.id::text=a.payload_json->>'action_id'
                    WHERE a.owner_id=%s AND (
                      (a.kind='tool' AND a.summary IN ('notion_read','notion_log','notion_save','notion_archive','notion_setup'))
                      OR p.tool IN ('notion_save','notion_archive'))
                    ORDER BY a.ts DESC LIMIT 20
                ) display""", (owner,)).fetchall()
                return [row[0] for row in rows]
        except psycopg.Error:
            raise StoreError('Notion activity is unavailable. Check Neon connectivity.') from None

    return await asyncio.to_thread(read)
