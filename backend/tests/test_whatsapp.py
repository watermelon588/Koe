import asyncio
import hashlib
import hmac
import json
import os

os.environ.setdefault("GEMINI_API_KEY", "test")

import pytest  # noqa: E402
import respx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from koe import whatsapp  # noqa: E402
from koe.config import settings  # noqa: E402
from koe.main import app  # noqa: E402

ME = "919876543210"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "whatsapp_verify_token", "tok")
    monkeypatch.setattr(settings, "whatsapp_app_secret", "appsecret")
    monkeypatch.setattr(settings, "allowed_whatsapp_numbers", ME)
    return TestClient(app)


def test_verification_handshake_echoes_challenge(client):
    r = client.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "tok",
                                                 "hub.challenge": "1158201444"})
    assert r.status_code == 200 and r.text == "1158201444"


def test_verification_rejects_wrong_token(client):
    r = client.get("/webhooks/whatsapp", params={"hub.mode": "subscribe", "hub.verify_token": "nope",
                                                 "hub.challenge": "x"})
    assert r.status_code == 403


def meta_payload(*senders):
    msgs = [{"from": s, "id": f"wamid.{i}", "type": "text", "text": {"body": "am I free at 7?"}}
            for i, s in enumerate(senders)]
    return {"object": "whatsapp_business_account",
            "entry": [{"changes": [{"field": "messages", "value": {"messages": msgs}}]}]}


def test_only_allow_listed_senders_get_through(client):
    assert [m["from"] for m in whatsapp.inbound_messages(meta_payload(ME, "15550001111"))] == [ME]
    status_only = {"entry": [{"changes": [{"value": {"statuses": [{"status": "delivered"}]}}]}]}
    assert whatsapp.inbound_messages(status_only) == []


def test_post_checks_signature_and_hands_messages_off(client, monkeypatch):
    handled = []
    monkeypatch.setattr(whatsapp, "handle_message", lambda msg, received=None: handled.append(msg))
    body = json.dumps(meta_payload(ME, "15550001111")).encode()
    sig = "sha256=" + hmac.new(b"appsecret", body, hashlib.sha256).hexdigest()

    bad = client.post("/webhooks/whatsapp", content=body, headers={"X-Hub-Signature-256": "sha256=00"})
    ok = client.post("/webhooks/whatsapp", content=body, headers={"X-Hub-Signature-256": sig})

    assert bad.status_code == 401
    assert ok.status_code == 200
    assert [m["from"] for m in handled] == [ME]


@respx.mock
def test_send_refuses_numbers_outside_allow_list(client):
    route = respx.post(url__startswith=whatsapp.GRAPH)
    with pytest.raises(ValueError):
        asyncio.run(whatsapp.send_text("15550001111", "hi"))
    assert route.call_count == 0
