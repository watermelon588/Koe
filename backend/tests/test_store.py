import asyncio
from contextlib import contextmanager

import pytest

from koe import store
from koe.config import settings


@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql://owner:private-password@db.neon.tech/koe?sslmode=require", raising=False)


def fake_database(monkeypatch, results):
    calls = []

    class Cursor:
        def __init__(self, result):
            self.result = result

        def fetchone(self):
            return (self.result,)

        def fetchall(self):
            return [(row,) for row in self.result]

    class Connection:
        def execute(self, query, params=None):
            if query == "SET LOCAL statement_timeout = 10000":
                return Cursor(None)
            calls.append((query.as_string() if hasattr(query, "as_string") else query, params))
            return Cursor(results.pop(0))

    @contextmanager
    def connect(*args, **kwargs):
        yield Connection()

    monkeypatch.setattr(store.psycopg, "connect", connect)
    return calls


def test_claim_binds_owner_conversation_and_action_as_values(monkeypatch):
    calls = fake_database(monkeypatch, [{"id": "action", "status": "executing"}])
    session = "session'; drop table koe_activity; --"
    result = asyncio.run(store.claim("action", session, True))
    query, params = calls[0]
    assert session not in query
    assert params["p_session"] == session
    assert params["p_owner"] == settings.koe_owner_id
    assert params["p_id"] == "action" and params["p_approve"] is True
    assert result["status"] == "executing"


def test_missing_storage_configuration_fails_without_connecting(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "")
    with pytest.raises(store.StoreError, match="not configured"):
        asyncio.run(store.claim("id", "session", True))


@pytest.mark.parametrize("url", ["not-a-url", "postgresql://owner:secret@db.neon.tech/koe?sslmode=disable"])
def test_invalid_or_unencrypted_configuration_fails_closed(monkeypatch, url):
    monkeypatch.setattr(settings, "database_url", url)
    with pytest.raises(store.StoreError):
        asyncio.run(store.claim("id", "session", True))


def test_storage_failure_is_sanitized_and_never_retried(monkeypatch):
    attempts = []

    def fail(*a, **kw):
        attempts.append(True)
        raise store.psycopg.OperationalError("diagnostic private-password postgresql://owner:secret@db.neon.tech/koe")

    monkeypatch.setattr(store.psycopg, "connect", fail)
    with pytest.raises(store.StoreError) as exc:
        asyncio.run(store.claim("id", "session", True))
    assert "private-password" not in str(exc.value) and "postgresql://" not in str(exc.value)
    assert "no action was retried" in str(exc.value)
    assert len(attempts) == 1


def test_dashboard_reads_are_owner_scoped_and_omit_private_execution_payloads(monkeypatch):
    calls = fake_database(monkeypatch, [[{"id": "activity", "ts": "2026-10-13T00:00:00Z"}], []])
    rows = asyncio.run(store.dashboard_read())
    assert rows == {"activity": [{"id": "activity", "ts": "2026-10-13T00:00:00Z"}], "pending": []}
    for query, params in calls:
        assert params["owner"] == settings.koe_owner_id
        assert "args_json" not in query and "payload_json" not in query
        assert "LIMIT 50" in query


def test_proposal_json_is_bound_and_unrecognized_function_is_refused(monkeypatch):
    calls = fake_database(monkeypatch, [{"id": "proposal"}])
    args = {"title": "Meeting'; select pg_sleep(10); --"}
    assert asyncio.run(store.propose("session", "web", "calendar_upsert_event", args, "Meeting"))["id"] == "proposal"
    query, params = calls[0]
    assert args["title"] not in query and params["p_args"].obj == args
    with pytest.raises(store.StoreError):
        asyncio.run(store.rpc("pg_sleep", seconds=10))
    assert len(calls) == 1


def test_blocking_database_work_does_not_block_the_event_loop(monkeypatch):
    import threading

    main_thread = threading.get_ident()
    observed = []

    @contextmanager
    def connect(*a, **kw):
        observed.append(threading.get_ident())
        class Connection:
            def execute(self, *a, **kw):
                class Cursor:
                    def fetchone(self):
                        return (None,)
                return Cursor()
        yield Connection()

    monkeypatch.setattr(store.psycopg, "connect", connect)
    assert asyncio.run(store.claim("action", "session", True)) is None
    assert observed and observed[0] != main_thread


def test_settings_representation_omits_backend_credentials():
    from koe.config import Settings

    values = {name: f"private-{name}" for name in (
        "gemini_api_key", "github_token", "github_webhook_secret", "notion_token",
        "whatsapp_token", "whatsapp_app_secret", "whatsapp_verify_token", "database_url", "koe_access_token",
    )}
    representation = repr(Settings(_env_file=None, **values))
    assert all(secret not in representation for secret in values.values())
