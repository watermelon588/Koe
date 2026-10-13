"""ACCOUNTS_SPEC.md quota: friends on the shared Gemini key get KOE_DAILY_TURNS a day; their own key removes the cap;
the owner is never limited. Google's models endpoint is faked."""
import asyncio

import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from koe import app_channel, connections, gemini, identity, usage, whatsapp
from koe.config import settings
from koe.main import app


@pytest.fixture(autouse=True)
def setup(monkeypatch):
    monkeypatch.setattr(settings, "koe_daily_turns", 2)
    monkeypatch.setattr(settings, "koe_secret_key", "a-test-secret-that-is-long-enough-for-koe-1234")
    monkeypatch.setattr(usage, "_own_keys", {})


def as_person(person):
    return identity.OWNER.set(person)


def test_a_friend_on_the_shared_key_gets_the_daily_limit_and_the_owner_never_does():
    token = as_person("friend-id")
    try:
        asyncio.run(usage.spend())
        asyncio.run(usage.spend())
        with pytest.raises(usage.OverQuota, match="Settings → Connections"):
            asyncio.run(usage.spend())
    finally:
        identity.OWNER.reset(token)
    for _ in range(5):
        asyncio.run(usage.spend())  # the owner: no limit, nothing counted


def test_a_friends_own_key_removes_the_limit_and_is_the_key_koe_uses():
    connections.save("friend-id", "gemini", "key ending abcd", [], {"key": "AIza-friends-own-key-abcd"})
    token = as_person("friend-id")
    try:
        for _ in range(5):
            asyncio.run(usage.spend())
        assert gemini.keys() == ["AIza-friends-own-key-abcd"]  # their quota only, never the shared keys
        assert whatsapp.gemini() is whatsapp.gemini()  # one reused client per key
    finally:
        identity.OWNER.reset(token)
    assert gemini.keys()[0] == settings.gemini_api_key  # everyone else: the shared keys


def test_saving_a_key_checks_it_with_google_first(monkeypatch):
    monkeypatch.setattr(settings, "koe_access_token", "tok")
    client = TestClient(app)
    auth = {"Authorization": "Bearer tok"}
    with respx.mock:
        respx.get(connections.GEMINI_MODELS).mock(return_value=httpx.Response(400))
        assert client.put("/api/connections/gemini", json={"key": "AIza-a-wrong-key-123456789"}, headers=auth).status_code == 400
        assert usage.own_key(settings.koe_owner_id) == ""
        ok = respx.get(connections.GEMINI_MODELS).mock(return_value=httpx.Response(200, json={"models": []}))
        assert client.put("/api/connections/gemini", json={"key": "AIza-the-right-key-123456789"}, headers=auth).status_code == 204
    assert ok.calls.last.request.headers["x-goog-api-key"] == "AIza-the-right-key-123456789"
    assert usage.own_key(settings.koe_owner_id) == "AIza-the-right-key-123456789"
    row = asyncio.run(app_channel.sql("select token_enc, account from koe_connections where provider = 'gemini'"))[0]
    assert "right-key" not in row["token_enc"] and row["account"] == "key ending 6789"


def test_over_the_limit_the_chat_says_so_instead_of_calling_gemini(monkeypatch):
    monkeypatch.setattr(settings, "koe_access_token", "tok")
    monkeypatch.setattr(settings, "koe_daily_turns", 0)
    monkeypatch.setattr(identity, "is_owner", lambda: False)  # as a friend on the shared key

    async def never(*a, **k):
        raise AssertionError("Gemini must not be called over the limit")

    monkeypatch.setattr(app_channel.text_agent, "chat", never)
    r = TestClient(app).post("/api/app/messages", json={"text": "hi"}, headers={"Authorization": "Bearer tok"})
    assert "today's 0 turns" in r.json()["messages"][1]["text"]
