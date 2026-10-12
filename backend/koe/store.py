"""Supabase PostgREST adapter. Approval transitions and their audit rows are SQL transactions.

Apply migrations/001_phase2.sql first. No automatic writes/retries on ambiguous network errors.
https://supabase.com/docs/guides/database/functions
https://supabase.com/docs/guides/getting-started/api-keys
"""
import logging

import httpx

from koe.config import settings

log = logging.getLogger("koe.store")


class StoreError(Exception):
    pass


def configured() -> bool:
    return bool(settings.supabase_url and settings.supabase_secret_key)


async def rpc(name: str, **params):
    if not configured():
        raise StoreError("Supabase is not configured; set SUPABASE_URL and SUPABASE_SECRET_KEY.")
    url = settings.supabase_url.rstrip("/")
    if not url.startswith("https://"):
        raise StoreError("SUPABASE_URL must use HTTPS.")
    key = settings.supabase_secret_key
    headers = {"apikey": key}
    # Modern secret keys aren't JWTs. Only legacy service_role keys use Bearer too.
    if not key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {key}"
    try:
        async with httpx.AsyncClient(timeout=15, trust_env=False) as client:
            response = await client.post(f"{url}/rest/v1/rpc/{name}", headers=headers,
                                         json={"p_owner": settings.koe_owner_id, **params})
    except httpx.HTTPError:
        raise StoreError("Supabase is unreachable; no action was retried.") from None
    if response.is_error:
        raise StoreError(f"Supabase returned HTTP {response.status_code}; check the migration and backend key.")
    try:
        return response.json()
    except ValueError:
        raise StoreError("Supabase returned an invalid response.") from None


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
        log.warning("Activity could not be saved to Supabase")


async def dashboard_read() -> dict:
    """Only owner-scoped display fields. Never expose args, message payloads or backend keys."""
    if not configured():
        return {"activity": [], "pending": []}
    if not settings.supabase_url.startswith("https://"):
        raise StoreError("SUPABASE_URL must use HTTPS.")
    headers = {"apikey": settings.supabase_secret_key}
    if not settings.supabase_secret_key.startswith("sb_secret_"):
        headers["Authorization"] = f"Bearer {settings.supabase_secret_key}"
    rows = {}
    queries = {
        "activity": ("koe_activity", {"select": "id,session_id,channel,kind,summary,ts,latency_json", "order": "ts.desc", "limit": 50}),
        "pending": ("koe_pending_actions", {"select": "id,session_id,channel,summary,expires_ts,status", "status": "eq.pending", "order": "created_ts.desc", "limit": 50}),
    }
    try:
        async with httpx.AsyncClient(timeout=10, trust_env=False) as client:
            for name, (table, params) in queries.items():
                response = await client.get(f"{settings.supabase_url.rstrip('/')}/rest/v1/{table}",
                    headers=headers, params={"owner_id": f"eq.{settings.koe_owner_id}", **params})
                response.raise_for_status()
                rows[name] = response.json()
                if not isinstance(rows[name], list):
                    raise ValueError("Expected rows")
    except (httpx.HTTPError, ValueError):
        raise StoreError("Saved dashboard activity is unavailable.") from None
    return rows
