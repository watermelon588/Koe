"""ACCOUNTS_SPEC.md success criterion 4: one person never sees or approves another's data. Storage owner comes from
identity.OWNER (set per request/socket), never from the browser or the model."""
import asyncio
from contextlib import contextmanager

from fastapi.testclient import TestClient

from koe import app_channel, identity, store
from koe.config import settings
from koe.main import app


def test_activity_and_approvals_are_stored_under_the_person_asking(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql://u:p@db.neon.tech/koe?sslmode=require")
    sent = []

    class Connection:
        def execute(self, query, params=None):
            if params:
                sent.append(params["p_owner"])
            return type("Cursor", (), {"fetchone": lambda self: ({"id": "a", "status": "pending"},)})()

    @contextmanager
    def connect(*args, **kwargs):
        yield Connection()

    monkeypatch.setattr(store.psycopg, "connect", connect)
    asyncio.run(store.propose("s", "app", "calendar_upsert_event", {}, "Book it"))
    token = identity.OWNER.set("friend-id")
    try:
        asyncio.run(store.propose("s", "app", "calendar_upsert_event", {}, "Book it"))
        asyncio.run(store.claim("a", "s", True))
    finally:
        identity.OWNER.reset(token)
    assert sent == [settings.koe_owner_id, "friend-id", "friend-id"]


def test_each_person_has_their_own_conversation_with_koe(monkeypatch):
    monkeypatch.setattr(settings, "koe_access_token", "tok")
    seen = []

    async def chat(text, history, context, client=None, **kw):
        seen.append((settings.koe_owner_id, id(history), id(context)))
        history.append(text)
        return {"text": "ok"}

    monkeypatch.setattr(app_channel.text_agent, "chat", chat)
    monkeypatch.setattr(app_channel, "notify", lambda *a, **k: asyncio.sleep(0))
    client = TestClient(app)
    for person in ("rohit-test", "friend-test", "rohit-test"):
        monkeypatch.setattr(settings, "koe_owner_id", person)  # the access token maps to the configured owner
        assert client.post("/api/app/messages", json={"text": f"hi from {person}"},
                           headers={"Authorization": "Bearer tok"}).status_code == 200
    (a1, ha1, ca1), (b, hb, cb), (a2, ha2, ca2) = seen
    assert (ha1, ca1) == (ha2, ca2) and (hb, cb) != (ha1, ca1)  # same person → same memory; another → separate
    assert app_channel.CHATS["friend-test"].history == ["hi from friend-test"]
