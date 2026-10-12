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
    async def chat(text, history, context, client):
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
    fake_agent(monkeypatch, {"text": "Book 7 to 7:30 with Rahul?", "pending_action": {"id": "act-1", "summary": "x"}})
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
        name = "f" * 32 + ".wav"
        (app_channel.VOICE / name).write_bytes(wav_bytes())
        return name
    monkeypatch.setattr(app_channel, "speak", speak)

    r = client.post("/api/app/voice", content=wav_bytes(), headers={**AUTH, "Content-Type": "audio/wav"})
    mine, koe = r.json()["messages"]
    assert mine["text"] == "Am I free at seven?" and mine["voice"].endswith(".wav")
    assert koe["voice"] == "f" * 32 + ".wav" and asked == ["Am I free at seven?"]
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
    with app_channel.db() as con:
        for name in ("gone", "live"):
            con.execute("insert into push values (?, ?)", (f"https://push.example/{name}",
                        '{"endpoint": "https://push.example/%s", "keys": {"p256dh": "k", "auth": "a"}}' % name))
    sent = []
    async def webpush_async(subscription, data, **kwargs):
        sent.append((subscription["endpoint"], data, kwargs["vapid_claims"]))
        if subscription["endpoint"].endswith("gone"):
            raise app_channel.WebPushException("gone", response=SimpleNamespace(status=410))
    monkeypatch.setattr(app_channel, "webpush_async", webpush_async)
    asyncio.run(app_channel.notify("hello"))
    assert {e for e, _, _ in sent} == {"https://push.example/gone", "https://push.example/live"}
    assert '"body": "hello"' in sent[0][1] and sent[0][2] == {"sub": settings.koe_push_contact}
    with app_channel.db() as con:
        assert [r["endpoint"] for r in con.execute("select endpoint from push")] == ["https://push.example/live"]


def test_a_github_alert_lands_in_the_chat_and_is_pushed(monkeypatch):
    pushed = []
    async def notify(body, title="Koe", tag="koe"):
        pushed.append((title, body))
    monkeypatch.setattr(app_channel, "notify", notify)
    monkeypatch.setattr(settings, "allowed_whatsapp_numbers", "")
    asyncio.run(github_hooks.send_alert("CI failed on #20"))
    assert pushed == [("GitHub", "CI failed on #20")]
    assert [(m["role"], m["text"]) for m in app_channel.list_messages()] == [("alert", "CI failed on #20")]
