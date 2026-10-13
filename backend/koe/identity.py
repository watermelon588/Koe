"""Whose request is this? Set once per request or socket (auth.http_owner, the WebSocket handlers); read by storage
and tools so each person's chat, approvals and connected accounts stay theirs. A context variable follows the
request into worker threads (asyncio.to_thread) and background tasks without passing it through every call.
https://docs.python.org/3/library/contextvars.html
"""
from contextvars import ContextVar

from koe.config import settings

OWNER: ContextVar[str | None] = ContextVar("koe_owner", default=None)


def owner_id() -> str:
    """The signed-in person, or the configured owner (CLI, webhooks, the access token)."""
    return OWNER.get() or settings.koe_owner_id


def is_owner() -> bool:
    return owner_id() == settings.koe_owner_id
