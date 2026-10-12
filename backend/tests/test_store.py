import asyncio
import os

os.environ.setdefault("GEMINI_API_KEY", "test")

import httpx
import pytest
import respx

from koe import store
from koe.config import settings


@pytest.fixture(autouse=True)
def config(monkeypatch):
    monkeypatch.setattr(settings, "supabase_url", "https://koe-test.supabase.co")
    monkeypatch.setattr(settings, "supabase_secret_key", "sb_secret_test")


@respx.mock
def test_secret_key_uses_apikey_header_and_claim_is_scoped_to_conversation():
    route = respx.post("https://koe-test.supabase.co/rest/v1/rpc/koe_claim_action").mock(
        return_value=httpx.Response(200, json={"id": "action", "status": "executing"}))
    result = asyncio.run(store.claim("action", "session", True))
    request = route.calls.last.request
    assert request.headers["apikey"] == "sb_secret_test"
    assert "authorization" not in request.headers
    assert b'"p_session":"session"' in request.content
    assert result["status"] == "executing"


def test_missing_storage_configuration_fails_without_request(monkeypatch):
    monkeypatch.setattr(settings, "supabase_secret_key", "")
    with pytest.raises(store.StoreError, match="not configured"):
        asyncio.run(store.claim("id", "session", True))


@respx.mock
def test_storage_failure_does_not_leak_response_or_secret():
    respx.post("https://koe-test.supabase.co/rest/v1/rpc/koe_claim_action").mock(
        return_value=httpx.Response(401, text="secret diagnostic sb_secret_test"))
    with pytest.raises(store.StoreError) as exc:
        asyncio.run(store.claim("id", "session", True))
    assert "sb_secret_test" not in str(exc.value)
    assert "401" in str(exc.value)


@respx.mock
def test_dashboard_reads_are_owner_scoped_and_omit_private_execution_payloads():
    activity = respx.get("https://koe-test.supabase.co/rest/v1/koe_activity").mock(return_value=httpx.Response(200, json=[]))
    pending = respx.get("https://koe-test.supabase.co/rest/v1/koe_pending_actions").mock(return_value=httpx.Response(200, json=[]))
    assert asyncio.run(store.dashboard_read()) == {"activity": [], "pending": []}
    for route in (activity, pending):
        params = route.calls.last.request.url.params
        assert params["owner_id"] == f"eq.{settings.koe_owner_id}"
        assert "args_json" not in params["select"] and "payload_json" not in params["select"]
