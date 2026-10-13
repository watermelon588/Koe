"""Single-owner, single-process dashboard fan-out. Never await a slow browser in a tool/audio path.

Queue bounds: https://docs.python.org/3/library/asyncio-queue.html
WebSocket lifetime: https://fastapi.tiangolo.com/advanced/websockets/
"""
import asyncio
from collections import deque
from datetime import datetime, timezone
from uuid import uuid4


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class Hub:
    def __init__(self):
        self.clients: set[asyncio.Queue] = set()
        self.panels: dict[str, dict] = {}
        self.activity: deque[dict] = deque(maxlen=100)
        self.history: list[dict] = []
        self.pending: dict[str, dict] = {}
        self.resolved: deque[str] = deque(maxlen=100)
        self.latencies: deque[dict] = deque(maxlen=100)
        self.storage = "Not connected: configure Neon to save activity."
        self.calendar_dirty = False

    def subscribe(self) -> asyncio.Queue:
        queue = asyncio.Queue(maxsize=32)
        self.clients.add(queue)
        return queue

    def publish(self, event_type: str, **data) -> dict:
        event = {**data, "type": event_type, "id": str(uuid4()), "ts": now()}
        # action IDs are separate from event IDs, so replayed events remain identifiable.
        if event_type == "panel":
            self.panels[data["name"]] = event
        elif event_type == "approval_pending":
            if len(self.pending) >= 100:
                self.pending.pop(next(iter(self.pending)))
            self.pending[data["action"]["id"]] = {**data["action"],
                "session_id": data.get("session_id"), "channel": data.get("channel")}
        elif event_type == "approval_result":
            result = data.get('result', {})
            if result.get("status") == "executed" and result.get('tool', 'calendar_upsert_event') in ('calendar_upsert_event', 'calendar_cancel_event'):
                self.calendar_dirty = True
            if data.get("clear"):
                self.pending.pop(data["action_id"], None)
                self.resolved.append(data["action_id"])
        elif event_type == "latency":
            self.latencies.append(event)
        if event_type in {"tool", "approval_pending", "approval_progress", "approval_result", "alert"}:
            self.activity.appendleft(event)
        for queue in tuple(self.clients):
            if queue.full():
                # Replace missed increments with a complete snapshot. Audio never waits for a client.
                while not queue.empty():
                    queue.get_nowait()
                queue.put_nowait(self.snapshot())
            else:
                queue.put_nowait(event)
        return event

    def snapshot(self) -> dict:
        live_sessions = {e.get("session_id") for e in self.activity if e.get("session_id")}
        history = [r for r in self.history if r.get("session_id") not in live_sessions]
        current = datetime.now(timezone.utc)
        self.pending = {key: p for key, p in self.pending.items()
                        if datetime.fromisoformat(p["expires_ts"].replace("Z", "+00:00")) > current}
        pending = list(self.pending.values())
        saved_latency = [{"id": r["id"], "ts": r["ts"],
                          "ms": r["latency_json"]["speech_end_to_first_audio_ms"]}
                         for r in history if r.get("latency_json", {}).get("speech_end_to_first_audio_ms") is not None]
        return {"type": "snapshot", "panels": self.panels.copy(),
                "activity": (list(self.activity) + history)[:100], "pending": pending,
                "latencies": sorted(saved_latency + list(self.latencies), key=lambda e: e["ts"])[-100:],
                "storage": self.storage}


hub = Hub()


def publish(event_type: str, **data):
    return hub.publish(event_type, **data)
