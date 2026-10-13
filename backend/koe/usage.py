"""Gemini quota (ACCOUNTS_SPEC.md, quota): friends share the owner's free Gemini key, so each gets KOE_DAILY_TURNS
turns a day (a message, a voice note, or starting a call). Adding their own free key from AI Studio in Settings →
Connections removes the limit. The owner is never limited: it's their key.
"""
import asyncio
from datetime import datetime
from zoneinfo import ZoneInfo

from koe import connections, identity
from koe.config import settings
from koe.db import sql

# ponytail: cached per process (whatsapp.gemini() runs on the event loop); one backend instance.
_own_keys: dict[str, str] = {}


class OverQuota(Exception):
    pass


def own_key(owner: str | None = None) -> str:
    """The person's own Gemini key (stored encrypted, provider "gemini"), or "" if they haven't added one."""
    owner = owner or identity.owner_id()
    if owner not in _own_keys:
        try:
            row = connections.load(owner, "gemini") if connections.configured() else None
        except connections.ConnectionError_:
            row = None
        _own_keys[owner] = row["token"]["key"] if row else ""
    return _own_keys[owner]


def gemini_key() -> str:
    return own_key() or settings.gemini_api_key


def forget(owner: str) -> None:
    _own_keys.pop(owner, None)


async def spend() -> None:
    """Count one turn for the person asking; raise OverQuota past the daily limit on the shared key."""
    owner = identity.owner_id()
    if identity.is_owner() or await asyncio.to_thread(own_key, owner):
        return
    day = datetime.now(ZoneInfo(settings.timezone)).date().isoformat()
    rows = await sql("insert into koe_usage (owner_id, day, turns) values (%s, %s, 1) on conflict (owner_id, day) "
                     "do update set turns = koe_usage.turns + 1 returning turns", owner, day)
    if rows[0]["turns"] > settings.koe_daily_turns:
        raise OverQuota(f"You've used today's {settings.koe_daily_turns} turns on Koe's shared Gemini key. Add your own "
                        "free key in Settings → Connections to keep going, or try again tomorrow.")
