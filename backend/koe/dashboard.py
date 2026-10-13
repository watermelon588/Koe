"""Read-only dashboard WebSocket. Auth first; shared refreshes use existing read tools."""
import asyncio
import contextlib
import hmac
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from koe import events, store
from koe.config import settings
from koe.tools import calendar, github

router = APIRouter()
_refresh_lock = asyncio.Lock()
_refreshed_at = float("-inf")


async def refresh():
    global _refreshed_at
    async with _refresh_lock:
        if time.monotonic() - _refreshed_at < 30 and not events.hub.calendar_dirty:
            return
        _refreshed_at = time.monotonic()
        events.hub.calendar_dirty = False
        day = datetime.now(ZoneInfo(settings.timezone)).date().isoformat()

        async def panel(name, fn):
            previous = events.hub.panels.get(name)
            try:
                result = await asyncio.wait_for(fn(), timeout=20)
            except Exception:
                result = {"error": {"message": "Could not refresh this panel. Check service setup and try again."}}
            # A conversational read may finish while this slower background refresh is in flight.
            if events.hub.panels.get(name) is previous:
                events.publish("panel", name=name, result=result, date=day, timezone=settings.timezone)

        async def github_read(fn):
            if not settings.github_token:
                return {"error": {"message": "GitHub is not connected. Add GITHUB_TOKEN to backend/.env."}}
            return await fn()

        async def history():
            try:
                rows = await store.dashboard_read()
                events.hub.history = rows["activity"]
                for pending in rows["pending"]:
                    if pending["id"] not in events.hub.resolved:
                        events.hub.pending.setdefault(pending["id"], pending)
                events.hub.storage = "Saved activity connected." if store.configured() else "Not connected: configure Neon to save activity."
            except store.StoreError:
                events.hub.storage = "Saved activity unavailable. Check Neon settings and migration."

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
            await ws.send_json(events.hub.snapshot())
        # No approval, chat, or tool execution is accepted on this read-only socket.


async def _send(ws: WebSocket, queue: asyncio.Queue):
    while True:
        await ws.send_json(await queue.get())


async def _periodic(ws: WebSocket):
    while True:
        await refresh()
        await ws.send_json(events.hub.snapshot())
        await asyncio.sleep(60)


@router.websocket("/ws/events")
async def dashboard(ws: WebSocket):
    await ws.accept()
    if not settings.koe_access_token:
        await ws.close(code=1008, reason="Set KOE_ACCESS_TOKEN in backend/.env to connect the dashboard.")
        return
    try:
        auth = await asyncio.wait_for(ws.receive_json(), timeout=10)
        token = auth.get("token") if isinstance(auth, dict) and auth.get("type") == "auth" else None
        if not isinstance(token, str) or not hmac.compare_digest(token.encode(), settings.koe_access_token.encode()):
            raise ValueError("Unauthorized")
    except (ValueError, TypeError, KeyError, asyncio.TimeoutError, WebSocketDisconnect):
        with contextlib.suppress(WebSocketDisconnect, RuntimeError):
            await ws.close(code=1008, reason="Enter the Koe access token from backend/.env.")
        return
    queue = events.hub.subscribe()
    tasks = []
    try:
        await ws.send_json(events.hub.snapshot())
        tasks = [asyncio.create_task(_receive(ws)), asyncio.create_task(_send(ws, queue)),
                 asyncio.create_task(_periodic(ws))]
        done, _ = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
        for task in done:
            task.result()
    except (WebSocketDisconnect, RuntimeError, OSError):
        pass
    finally:
        events.hub.clients.discard(queue)
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
