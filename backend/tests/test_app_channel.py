"""SPEC §14: the Koe app channel. Gemini, Live and Web Push are faked; storage is a temp SQLite file."""
import asyncio
import io
import wave
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from koe import app_channel, github_hooks
from koe.config import settings
from koe.main import app

AUTH = {"Authorization": "Bearer tok"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "koe_access_token", "tok")
    pushed = []
    async def notify(body, title="Koe", tag="koe"):
        pushed.append((title, body))
    monkeypatch.setattr(app_channel, "notify", notify)
    c = TestClient(app)
    c.pushed = pushed
    return c


def fake_agent(monkeypatch, result):
    asked = []
    async def chat(text, history, context, client=None, seen=None):
        asked.append(text)
        return result
    monkeypatch.setattr(app_channel.text_agent, "chat", chat)
    return asked


def wav_bytes(seconds=0.2):
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(16000)
        w.writeframes(b"\x00\x00" * int(16000 * seconds))
    return buf.getvalue()


def test_every_endpoint_needs_the_access_token(client, monkeypatch):
    assert client.get("/api/app/messages").status_code == 401
    assert client.get("/api/app/messages", headers={"Authorization": "Bearer nope"}).status_code == 401
    monkeypatch.setattr(settings, "koe_access_token", "")  # not configured = closed, not open
    assert client.get("/api/app/messages", headers={"Authorization": "Bearer "}).status_code == 401


def test_a_text_message_gets_a_reply_that_is_saved_and_pushed(client, monkeypatch):
    asked = fake_agent(monkeypatch, {"text": "You're free after 7."})
    r = client.post("/api/app/messages", json={"text": "  am I free tonight?  "}, headers=AUTH)
    assert r.status_code == 200
    mine, koe = r.json()["messages"]
    assert (mine["role"], mine["text"]) == ("you", "am I free tonight?")
    assert (koe["role"], koe["text"], koe["voice"]) == ("koe", "You're free after 7.", None)
    assert asked == ["am I free tonight?"]
    assert [m["text"] for m in client.get("/api/app/messages", headers=AUTH).json()["messages"]] == ["am I free tonight?", "You're free after 7."]
    assert client.get(f"/api/app/messages?after={koe['id']}", headers=AUTH).json()["messages"] == []
    assert client.pushed == [("Koe", "You're free after 7.")]


def test_an_empty_message_is_refused(client):
    assert client.post("/api/app/messages", json={"text": "   "}, headers=AUTH).status_code == 400


def test_a_proposal_is_resolved_by_its_confirm_button(client, monkeypatch):
    fake_agent(monkeypatch, {"text": "Book 7 to 7:30 with Rahul?", "pending_action": {"id": "act-1", "summary": "x", "expires_ts": "2099-01-01T00:00:00Z"}})
    koe = client.post("/api/app/messages", json={"text": "book rahul at 7"}, headers=AUTH).json()["messages"][1]
    assert koe["action_id"] == "act-1" and koe["action_status"] is None
    decided = []
    async def confirm(context, approve, action_id=None):
        decided.append((approve, action_id))
        return {"status": "executed", "title": "Call with Rahul"}
    monkeypatch.setattr(app_channel.agent, "confirm", confirm)
    r = client.post("/api/app/approvals/act-1", json={"approve": True}, headers=AUTH).json()
    assert decided == [(True, "act-1")] and r["action"] == {"id": "act-1", "status": "executed"}
    assert r["messages"][0]["text"].startswith("Saved: Call with Rahul")
    stored = client.get("/api/app/messages", headers=AUTH).json()["messages"]
    assert stored[1]["action_status"] == "executed"


def test_a_voice_note_is_transcribed_and_answered_with_a_voice_note(client, monkeypatch):
    asked = fake_agent(monkeypatch, {"text": "Yes, seven is free."})
    async def transcribe(audio, mime):
        assert mime == "audio/wav" and audio[:4] == b"RIFF"
        return "Am I free at seven?"
    monkeypatch.setattr(app_channel.whatsapp, "transcribe", transcribe)
    async def speak(text):
        return await app_channel.save_voice(wav_bytes())
    monkeypatch.setattr(app_channel, "speak", speak)

    r = client.post("/api/app/voice", content=wav_bytes(), headers={**AUTH, "Content-Type": "audio/wav"})
    mine, koe = r.json()["messages"]
    assert mine["text"] == "Am I free at seven?" and mine["voice"].endswith(".wav")
    assert koe["voice"].endswith(".wav") and koe["voice"] != mine["voice"] and asked == ["Am I free at seven?"]
    got = client.get(f"/api/app/voice/{mine['voice']}", headers=AUTH)
    assert got.status_code == 200 and got.headers["content-type"] == "audio/wav" and got.content[:4] == b"RIFF"


def test_voice_uploads_are_checked(client, monkeypatch):
    monkeypatch.setattr(app_channel, "MAX_VOICE_BYTES", 1000)
    assert client.post("/api/app/voice", content=b"not audio", headers=AUTH).status_code == 415
    assert client.post("/api/app/voice", content=wav_bytes(1), headers=AUTH).status_code == 413
    assert client.get("/api/app/voice/..%2Fapp.db", headers=AUTH).status_code == 404
    assert client.get("/api/app/voice/app.db", headers=AUTH).status_code == 404


def test_a_failed_spoken_reply_still_delivers_the_text(client, monkeypatch):
    fake_agent(monkeypatch, {"text": "Seven works."})
    async def transcribe(audio, mime):
        return "seven?"
    async def speak(text):
        raise RuntimeError("Live unavailable")
    monkeypatch.setattr(app_channel.whatsapp, "transcribe", transcribe)
    monkeypatch.setattr(app_channel, "speak", speak)
    koe = client.post("/api/app/voice", content=wav_bytes(), headers=AUTH).json()["messages"][1]
    assert koe["text"] == "Seven works." and koe["voice"] is None


def test_push_subscriptions_are_validated(client):
    assert client.post("/api/app/push/subscribe", json={"endpoint": "http://x"}, headers=AUTH).status_code == 400
    sub = {"endpoint": "https://fcm.googleapis.com/fcm/send/abc", "keys": {"p256dh": "k", "auth": "a"}}
    assert client.post("/api/app/push/subscribe", json=sub, headers=AUTH).json() == {"ok": True}
    key = client.get("/api/app/push/key", headers=AUTH).json()["key"]
    assert len(key) == 87  # base64url of a 65-byte uncompressed P-256 point, no padding


def test_notify_pushes_to_each_device_and_forgets_gone_ones(monkeypatch):
    for name in ("gone", "live"):
        asyncio.run(app_channel.sql("insert into koe_app_push values (%s, %s, %s)", f"https://push.example/{name}",
                    app_channel.owner(), '{"endpoint": "https://push.example/%s", "keys": {"p256dh": "k", "auth": "a"}}' % name))
    sent = []
    async def webpush_async(subscription, data, **kwargs):
        sent.append((subscription["endpoint"], data, kwargs["vapid_claims"]))
        if subscription["endpoint"].endswith("gone"):
            raise app_channel.WebPushException("gone", response=SimpleNamespace(status=410))
    monkeypatch.setattr(app_channel, "webpush_async", webpush_async)
    assert asyncio.run(app_channel.notify("hello")) == 1  # the gone device doesn't count
    assert {e for e, _, _ in sent} == {"https://push.example/gone", "https://push.example/live"}
    assert '"body": "hello"' in sent[0][1] and sent[0][2] == {"sub": settings.koe_push_contact}
    left = asyncio.run(app_channel.sql("select endpoint from koe_app_push"))
    assert [r["endpoint"] for r in left] == ["https://push.example/live"]


def test_a_github_alert_lands_in_the_chat_and_is_pushed(monkeypatch):
    pushed = []
    async def notify(body, title="Koe", tag="koe"):
        pushed.append((title, body))
    monkeypatch.setattr(app_channel, "notify", notify)
    monkeypatch.setattr(settings, "allowed_whatsapp_numbers", "")
    asyncio.run(github_hooks.send_alert("CI failed on #20"))
    assert pushed == [("GitHub", "CI failed on #20")]
    assert [(m["role"], m["text"]) for m in asyncio.run(app_channel.list_messages())] == [("alert", "CI failed on #20")]


def test_the_push_key_can_come_from_the_environment(monkeypatch):
    # Render's disk is wiped on restart, so the key must survive as VAPID_PRIVATE_KEY.
    from py_vapid import Vapid02, b64urlencode
    key = Vapid02()
    key.generate_keys()
    raw = b64urlencode(key.private_key.private_numbers().private_value.to_bytes(32, "big"))
    monkeypatch.setattr(app_channel.settings, "vapid_private_key", raw)
    assert app_channel.vapid().private_key.private_numbers() == key.private_key.private_numbers()
    assert not (app_channel.DATA / "vapid.pem").exists()


def test_the_install_page_can_send_a_test_notification(client, monkeypatch):
    async def notify(body, title="Koe", tag="koe"):
        return 2
    monkeypatch.setattr(app_channel, "notify", notify)
    assert client.post("/api/app/push/test").status_code == 401
    assert client.post("/api/app/push/test", headers=AUTH).json() == {"sent": 2}


def test_each_owner_sees_only_their_own_chat_voice_notes_and_devices(client, monkeypatch):
    # ACCOUNTS_SPEC.md task 5: rows belong to an owner; another owner gets nothing, not even by guessing a name.
    me = settings.koe_owner_id
    sub = {"endpoint": "https://fcm.googleapis.com/fcm/send/mine", "keys": {"p256dh": "k", "auth": "a"}}
    assert client.post("/api/app/push/subscribe", json=sub, headers=AUTH).status_code == 200
    asyncio.run(app_channel.add_message("you", "my secret plan"))
    note = asyncio.run(app_channel.save_voice(wav_bytes()))

    monkeypatch.setattr(settings, "koe_owner_id", "friend")
    assert client.get("/api/app/messages", headers=AUTH).json() == {"messages": [], "workspace": []}
    assert client.get(f"/api/app/voice/{note}", headers=AUTH).status_code == 404
    assert asyncio.run(app_channel.sql("select endpoint from koe_app_push where owner_id = %s", "friend")) == []
    assert client.get("/api/app/messages", headers=AUTH).json()["messages"] == []

    monkeypatch.setattr(settings, "koe_owner_id", me)
    assert [m["text"] for m in client.get("/api/app/messages", headers=AUTH).json()["messages"]] == ["my secret plan"]
    assert "owner_id" not in client.get("/api/app/messages", headers=AUTH).json()["messages"][0]


# ── Live workspace (SPEC §2 "Live workspace"): the chat API says what Koe read, proposed or wrote ─────────────

ROW = {"date": "2026-10-13", "client": "Client A", "hours": 2.5, "note": "Pairing", "spreadsheet_id": "sheet-1",
       "sheet_name": "Hours", "token": "private-token"}


def proposing_agent(monkeypatch):
    """A turn that reads the calendar, then proposes one Sheets row (stored like store.propose would)."""
    async def chat(text, history, context, client=None, seen=None):
        seen.append(("calendar_list", {"date": "2026-10-13"}, {"date": "2026-10-13", "timezone": "Asia/Kolkata", "events": []}))
        seen.append(("github_my_prs", {}, {"prs": []}))  # not a workspace tool: never shown
        seen.append(("sheets_log_hours", ROW, {"pending_action": {"id": "act-9"}}))
        context.pending = {"id": "act-9", "tool": "sheets_log_hours", "args_json": ROW, "summary": "Log 2.5 hours", "expires_ts": "2099-01-01T00:00:00Z"}
        return {"text": "Log 2.5 hours for Client A?", "pending_action": context.pending}
    monkeypatch.setattr(app_channel.text_agent, "chat", chat)


def test_a_turn_returns_workspace_events_with_the_exact_pending_row_and_no_secrets(client, monkeypatch):
    proposing_agent(monkeypatch)
    body = client.post("/api/app/messages", json={"text": "log 2.5h for Client A"}, headers=AUTH).json()
    work = body["workspace"]
    assert [(e["type"], e.get("phase"), e["work"]["service"]) for e in work] == [
        ("tool", "start", "calendar"), ("tool", "end", "calendar"),
        ("tool", "start", "sheets"), ("tool", "end", "sheets"), ("approval_pending", None, "sheets")]
    assert work[0]["operation_id"] == work[1]["operation_id"] != work[2]["operation_id"]
    pending = work[-1]["work"]
    assert pending["action_id"] == "act-9" == body["messages"][1]["action_id"]
    assert pending["details"] == {"date": "2026-10-13", "client": "Client A", "hours": 2.5, "note": "Pairing", "sheet_name": "Hours"}
    assert pending["url"] == "https://docs.google.com/spreadsheets/d/sheet-1/edit"
    assert "private-token" not in str(body)
    assert body['messages'][1]['approval']['display']['title'] == 'Log 2.5 hours · Client A'
    # Reopening the app shows the open proposal again; a follow-up poll does not re-open the panel.
    assert client.get("/api/app/messages", headers=AUTH).json()["workspace"][0]["type"] == "approval_pending"
    assert client.get("/api/app/messages?after=1", headers=AUTH).json()["workspace"] == []


def test_confirming_returns_the_authoritative_row_and_a_failure_is_never_shown_saved(client, monkeypatch):
    proposing_agent(monkeypatch)
    client.post("/api/app/messages", json={"text": "log it"}, headers=AUTH)
    async def confirm(context, approve, action_id=None):
        context.pending = None
        return {"status": "executed", "row": 8, "range": "Hours!A8:E8", "title": "2.5 hours for Client A",
                "url": "https://docs.google.com/spreadsheets/d/sheet-1/edit"}
    monkeypatch.setattr(app_channel.agent, "confirm", confirm)
    r = client.post("/api/app/approvals/act-9", json={"approve": True}, headers=AUTH).json()
    [event] = r["workspace"]
    assert event["type"] == "approval_result" and event["status"] == "executed"
    assert (event["work"]["row"], event["work"]["range"], event["work"]["details"]["client"]) == (8, "Hours!A8:E8", "Client A")

    proposing_agent(monkeypatch)
    client.post("/api/app/messages", json={"text": "log it again"}, headers=AUTH)
    async def failed(context, approve, action_id=None):
        context.pending = None
        return {"error": {"code": "sheets_unreachable", "message": "Sheets did not confirm the entry.", "hint": "Check the sheet."}}
    monkeypatch.setattr(app_channel.agent, "confirm", failed)
    [event] = client.post("/api/app/approvals/act-9", json={"approve": True}, headers=AUTH).json()["workspace"]
    assert event["status"] == "unavailable" and event["work"]["error"]["message"] == "Sheets did not confirm the entry."
    assert "row" not in event["work"]


def test_a_typed_yes_returns_the_result_and_marks_the_proposal_bubble(client, monkeypatch):
    proposing_agent(monkeypatch)
    koe = client.post("/api/app/messages", json={"text": "log it"}, headers=AUTH).json()["messages"][1]
    async def chat(text, history, context, client=None, seen=None):
        context.pending = None
        return {"text": "Saved", "approval_result": {"status": "executed", "row": 9, "range": "Hours!A9:E9"}}
    monkeypatch.setattr(app_channel.text_agent, "chat", chat)
    [event] = client.post("/api/app/messages", json={"text": "yes"}, headers=AUTH).json()["workspace"]
    assert (event["type"], event["status"], event["work"]["row"], event["work"]["action_id"]) == ("approval_result", "executed", 9, "act-9")
    stored = {m["id"]: m for m in client.get("/api/app/messages", headers=AUTH).json()["messages"]}
    assert stored[koe["id"]]["action_status"] == "executed"
