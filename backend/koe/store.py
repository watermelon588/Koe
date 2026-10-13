"""Backend-only Neon PostgreSQL store. SQL functions own atomic approval transitions.

Blocking connections run off the event loop (including Windows' Proactor loop).
Each connection context commits on success, rolls back on error, and closes.
https://www.psycopg.org/psycopg3/docs/basic/transactions.html
"""
import asyncio
import logging

import psycopg
from psycopg import sql
from psycopg.conninfo import conninfo_to_dict
from psycopg.types.json import Jsonb

from koe.config import settings

log = logging.getLogger("koe.store")
RPC_PARAMS = {
    "koe_propose_action": ("p_session", "p_channel", "p_tool", "p_args", "p_summary"),
    "koe_claim_action": ("p_id", "p_session", "p_approve"),
    "koe_finish_action": ("p_id", "p_session", "p_ok", "p_result"),
    "koe_record_activity": ("p_channel", "p_session", "p_kind", "p_summary", "p_payload"),
}
TABLES = ("koe_activity", "koe_pending_actions", "koe_daily_notes", "koe_github_deliveries")


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


async def rpc(name: str, **params):
    if name not in RPC_PARAMS or set(params) != set(RPC_PARAMS[name]):
        raise StoreError("Unsupported database operation.")
    options = connection_options()
    values = {"p_owner": settings.koe_owner_id, **params}
    values = {key: Jsonb(value) if isinstance(value, dict) else value for key, value in values.items()}
    # Both identifiers and parameters are fixed by this module, never supplied by the browser/model.
    assignments = sql.SQL(", ").join(
        sql.SQL("{} => {}").format(sql.Identifier(key), sql.Placeholder(key)) for key in values
    )
    query = sql.SQL("SELECT public.{}({})").format(sql.Identifier(name), assignments)

    def execute():
        try:
            with psycopg.connect(**options) as con:
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


async def dashboard_read() -> dict:
    """Owner-scoped display fields as JSON; never execution args or backend secrets."""
    if not configured():
        return {"activity": [], "pending": []}
    options = connection_options()
    owner = settings.koe_owner_id

    def read():
        try:
            with psycopg.connect(**options) as con:
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
            with psycopg.connect(**options) as con:
                con.execute("SET LOCAL statement_timeout = 10000")
                for table in TABLES:
                    con.execute(sql.SQL("SELECT 1 FROM public.{} LIMIT 0").format(sql.Identifier(table)))
        except psycopg.Error:
            raise StoreError("Neon connection/schema check failed; check DATABASE_URL and run the migration.") from None

    await asyncio.to_thread(read)
