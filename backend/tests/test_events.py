import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from fastapi import WebSocketDisconnect

from koe import agent, dashboard, events
from koe.config import settings


def test_fanout_is_bounded_and_slow_clients_get_current_snapshot():
    async def scenario():
        hub = events.Hub()
        slow, fast = hub.subscribe(), hub.subscribe()
        for i in range(150):
            hub.publish("tool", name=f"read-{i}", phase="end", ok=True)
            assert (await fast.get())["name"] == f"read-{i}"
        assert slow.qsize() <= 32
        items = [slow.get_nowait() for _ in range(slow.qsize())]
        assert any(e["type"] == "snapshot" for e in items)
        assert len(hub.snapshot()["activity"]) == 100
    asyncio.run(scenario())


def test_snapshot_expiry_compares_actual_instants_and_removes_resolved_actions():
    hub = events.Hub()
    future = (datetime.now(timezone.utc) + timedelta(minutes=5)).astimezone(timezone(timedelta(hours=-7))).isoformat()
    hub.publish("approval_pending", action={"id": "a", "summary": "Book", "expires_ts": future}, session_id="s")
    assert hub.snapshot()["pending"][0]["id"] == "a"
    hub.publish("approval_result", action_id="a", clear=False, result={"error": {"message": "wait"}})
    assert len(hub.snapshot()["pending"]) == 1
    hub.publish("approval_result", action_id="a", clear=True, result={"status": "executed"})
    assert hub.snapshot()["pending"] == []
    assert hub.calendar_dirty


class Browser:
    def __init__(self, token="private"):
        self.token = token
        self.incoming, self.outgoing = asyncio.Queue(), asyncio.Queue()
        self.closed = None

    async def accept(self):
        pass

    async def receive_json(self):
        if self.token is not None:
            token, self.token = self.token, None
            return {"type": "auth", "token": token}
        message = await self.incoming.get()
        if message is None:
            raise WebSocketDisconnect()
        if message == "malformed":
            raise ValueError()
        return message

    async def send_json(self, message):
        await self.outgoing.put(message)

    async def close(self, code, reason):
        self.closed = code


@pytest.mark.parametrize("configured,token", [("", "private"), ("private", "wrong"), ("private", "₹")])
def test_unauthorized_socket_never_reads_or_leaks_dashboard(monkeypatch, configured, token):
    monkeypatch.setattr(settings, "koe_access_token", configured)
    async def forbidden():
        pytest.fail("No reads before auth")
    monkeypatch.setattr(dashboard, "refresh", forbidden)
    async def scenario():
        browser = Browser(token)
        await dashboard.dashboard(browser)
        assert browser.closed == 1008
        assert browser.outgoing.empty()
        assert not events.hub.clients
    asyncio.run(scenario())


def test_authenticated_stream_receives_live_events_and_cleans_up(monkeypatch):
    monkeypatch.setattr(settings, "koe_access_token", "private")
    async def no_refresh():
        pass
    monkeypatch.setattr(dashboard, "refresh", no_refresh)
    async def scenario():
        browser = Browser()
        task = asyncio.create_task(dashboard.dashboard(browser))
        assert (await asyncio.wait_for(browser.outgoing.get(), 1))["type"] == "snapshot"
        await asyncio.sleep(0)
        events.publish("alert", summary="CI failed")
        for _ in range(3):
            message = await asyncio.wait_for(browser.outgoing.get(), 1)
            if message["type"] == "alert":
                assert message["summary"] == "CI failed"
                break
        else:
            pytest.fail("Missing live alert")
        browser.incoming.put_nowait("malformed")
        browser.incoming.put_nowait({"type": "approval", "approve": True, "action_id": "foreign"})
        browser.incoming.put_nowait({"type": "refresh"})
        assert (await asyncio.wait_for(browser.outgoing.get(), 1))["type"] == "snapshot"
        browser.incoming.put_nowait(None)
        await asyncio.wait_for(task, 1)
        assert not events.hub.clients
    asyncio.run(scenario())


def test_refresh_coalesces_clients_and_reports_missing_credentials(monkeypatch):
    monkeypatch.setattr(dashboard, "_refreshed_at", float("-inf"))
    monkeypatch.setattr(dashboard, "_refresh_lock", asyncio.Lock())
    monkeypatch.setattr(settings, "github_token", "")
    calls = []
    async def calendar(day):
        calls.append(day)
        return {"error": {"message": "Google is not connected"}}
    monkeypatch.setattr(dashboard.calendar, "calendar_list", calendar)
    async def scenario():
        await asyncio.gather(dashboard.refresh(), dashboard.refresh(), dashboard.refresh())
        assert len(calls) == 1
        snapshot = events.hub.snapshot()
        assert "not connected" in snapshot["panels"]["calendar"]["result"]["error"]["message"]
        assert "Settings → Connections → GitHub" in snapshot["panels"]["prs"]["result"]["error"]["message"]
        assert "Not connected" in snapshot["storage"]
    asyncio.run(scenario())


def test_tool_result_updates_only_the_matching_dashboard_scope(monkeypatch):
    async def reads(**kwargs):
        return {"prs": [{"number": 1}], "count": 1}
    monkeypatch.setitem(agent.TOOLS, "github_my_prs", agent.TOOLS["github_my_prs"]._replace(fn=reads))
    async def scenario():
        context = agent.Conversation("cli")
        await agent.run_tool("github_my_prs", {"state": "closed"}, context=context)
        assert "prs" not in events.hub.panels
        await agent.run_tool("github_my_prs", {}, context=context)
        assert events.hub.panels["prs"]["result"]["count"] == 1
        assert events.hub.activity[0]["phase"] == "end"
        assert events.hub.activity[0]["session_id"] == context.session_id
    asyncio.run(scenario())


def test_background_refresh_does_not_overwrite_a_newer_conversational_result(monkeypatch):
    monkeypatch.setattr(dashboard, "_refreshed_at", float("-inf"))
    monkeypatch.setattr(dashboard, "_refresh_lock", asyncio.Lock())
    monkeypatch.setattr(settings, "github_token", "")
    async def calendar(day):
        events.publish("panel", name="calendar", result={"events": [{"id": "new"}]})
        return {"events": [{"id": "old"}]}
    monkeypatch.setattr(dashboard.calendar, "calendar_list", calendar)
    asyncio.run(dashboard.refresh())
    assert events.hub.panels["calendar"]["result"]["events"][0]["id"] == "new"


def test_cancelled_tool_emits_an_end_event_and_propagates_cancellation(monkeypatch):
    async def cancelled(**kwargs):
        raise asyncio.CancelledError()
    monkeypatch.setitem(agent.TOOLS, "github_my_prs", agent.TOOLS["github_my_prs"]._replace(fn=cancelled))
    async def scenario():
        with pytest.raises(asyncio.CancelledError):
            await agent.run_tool("github_my_prs", {}, context=agent.Conversation("web"))
        assert events.hub.activity[0]["phase"] == "end"
        assert events.hub.activity[0]["ok"] is False
    asyncio.run(scenario())
def test_non_calendar_approval_does_not_dirty_calendar_panel():
    from koe.events import Hub
    hub = Hub()
    hub.publish('approval_result', action_id='comment', clear=True,
                result={'status': 'executed', 'tool': 'github_comment'})
    assert not hub.calendar_dirty
    hub.publish('approval_result', action_id='booking', clear=True,
                result={'status': 'executed', 'tool': 'calendar_upsert_event'})
    assert hub.calendar_dirty

