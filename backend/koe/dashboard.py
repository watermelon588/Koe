"""Read-only dashboard WebSocket. Auth first; shared refreshes use existing read tools."""
import asyncio
import contextlib
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from koe import auth, connections, events, identity, store
from koe.config import settings
from koe.tools import calendar, github

router = APIRouter()


async def refresh():
    """Re-read this person's panels (their calendar, their GitHub) into their own hub."""
    hub = events.hub_for()
    async with hub.refresh_lock:
        if time.monotonic() - hub.refreshed_at < 30 and not hub.calendar_dirty:
            return
        hub.refreshed_at = time.monotonic()
        hub.calendar_dirty = False
        day = datetime.now(ZoneInfo(settings.timezone)).date().isoformat()

        async def panel(name, fn):
            previous = hub.panels.get(name)
            try:
                result = await asyncio.wait_for(fn(), timeout=20)
            except Exception:
                result = {"error": {"message": "Could not refresh this panel. Check service setup and try again."}}
            # A conversational read may finish while this slower background refresh is in flight.
            if hub.panels.get(name) is previous:
                events.publish("panel", name=name, result=result, date=day, timezone=settings.timezone)

        async def github_read(fn):
            if not connections.github_account()["token"]:
                return {"error": {"message": "GitHub is not connected: Settings → Connections → GitHub."}}
            return await fn()

        async def history():
            try:
                rows = await store.dashboard_read()
                hub.history = rows["activity"]
                for pending in rows["pending"]:
                    if pending["id"] not in hub.resolved:
                        hub.pending.setdefault(pending["id"], pending)
                hub.storage = "Saved activity connected." if store.configured() else "Not connected: configure Neon to save activity."
            except store.StoreError:
                hub.storage = "Saved activity unavailable. Check Neon settings and migration."

        await asyncio.gather(panel("calendar", lambda: calendar.calendar_list(day)),
                             panel("reviews", lambda: github_read(github.github_review_queue)),
                             panel("prs", lambda: github_read(github.github_my_prs)), history())


async def _receive(ws: WebSocket):
    while True:
        try:
            message = await ws.receive_json()
        except (ValueError, TypeError, KeyError):
            continue
        if isinstance(message, dict) and message.get("type") == "refresh":
            await refresh()
            await ws.send_json(events.hub_for().snapshot())
        # No approval, chat, or tool execution is accepted on this read-only socket.


async def _send(ws: WebSocket, queue: asyncio.Queue):
    while True:
        await ws.send_json(await queue.get())


async def _periodic(ws: WebSocket):
    while True:
        await refresh()
        await ws.send_json(events.hub_for().snapshot())
        await asyncio.sleep(60)


@router.websocket("/ws/events")
async def dashboard(ws: WebSocket):
    await ws.accept()
    if not auth.ws_required():
        await ws.close(code=1008, reason="Set up Google sign-in or KOE_ACCESS_TOKEN in backend/.env to connect the dashboard.")
        return
    try:
        first = await asyncio.wait_for(ws.receive_json(), timeout=10)
        owner = auth.ws_owner(first.get("token")) if isinstance(first, dict) and first.get("type") == "auth" else None
        if not owner:
            raise ValueError("Unauthorized")
        identity.OWNER.set(owner)  # this socket shows its owner's day
    except (ValueError, TypeError, KeyError, asyncio.TimeoutError, WebSocketDisconnect):
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            await ws.close(code=1008, reason="Sign in to Koe again.")
        return
    hub = events.hub_for()  # only this person's events reach this socket
    queue = hub.subscribe()
    tasks = []
    try:
        await ws.send_json(hub.snapshot())
        tasks = [asyncio.create_task(_receive(ws)), asyncio.create_task(_send(ws, queue)),
                 asyncio.create_task(_periodic(ws))]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except (WebSocketDisconnect, RuntimeError, OSError):
        pass
    finally:
        hub.clients.discard(queue)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
