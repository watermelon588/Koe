"""Expiring GitHub OAuth tokens rotate without losing per-person isolation.

Real storage and provider endpoints are isolated by conftest and respx.
"""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from datetime import datetime, timedelta, timezone
from threading import Barrier
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from koe import auth, connections, identity
from koe.config import settings
from koe.db import sql
from test_auth import ADMIN, SITE, sign_in

START = datetime(2026, 10, 26, 6, 0, tzinfo=timezone.utc)
REFRESH_URL = "https://github.com/login/oauth/access_token"


@pytest.fixture(autouse=True)
def refresh_settings(monkeypatch):
    for name, value in {
        "google_web_client_id": "test-google-client",
        "google_web_client_secret": "test-google-secret",
        "github_client_id": "test-github-client",
        "github_client_secret": "test-github-secret",
        "koe_secret_key": "github-refresh-test-secret-more-than-32-characters",
        "koe_admin_email": ADMIN,
        "koe_public_url": SITE,
        "github_token": "owner-environment-token",
        "github_login": "owner-github",
    }.items():
        monkeypatch.setattr(settings, name, value)
    token = identity.OWNER.set(settings.koe_owner_id)
    yield
    identity.OWNER.reset(token)


@pytest.fixture
def clock(monkeypatch):
    class Clock(datetime):
        current = START

        @classmethod
        def now(cls, tz=None):
            return cls.current.astimezone(tz) if tz else cls.current.replace(tzinfo=None)

    monkeypatch.setattr(connections, "datetime", Clock)
    return Clock


def save_token(owner=None, **changes):
    owner = owner or identity.owner_id()
    token = {
        "access_token": "expired-access", "refresh_token": "old-refresh",
        "expiry": (START - timedelta(minutes=1)).isoformat(),
        "refresh_expiry": (START + timedelta(days=180)).isoformat(),
        **changes,
    }
    connections.save(owner, "github", "connected-github", ["repo", "read:user"], token)
    return token


def rotated_response():
    return {
        "access_token": "rotated-access", "refresh_token": "rotated-refresh",
        "expires_in": 28800, "refresh_token_expires_in": 15897600,
        "scope": "repo,read:user", "token_type": "bearer",
    }


def mock_refresh(**kwargs):
    refresh = respx.post(REFRESH_URL).respond(200, json=rotated_response(), **kwargs)
    me = respx.get("https://api.github.com/user").respond(200, json={"login": "connected-github"})
    return refresh, me


def test_oauth_callback_saves_encrypted_refresh_and_expiration_metadata(monkeypatch):
    app = FastAPI()
    app.include_router(auth.router)
    client = TestClient(app, follow_redirects=False)
    sign_in(client, monkeypatch, ADMIN)
    started = client.get("/auth/github/connect")
    assert started.status_code == 302
    query = parse_qs(urlparse(started.headers["location"]).query)
    before = datetime.now(timezone.utc)
    with respx.mock:
        respx.post(REFRESH_URL).respond(200, json=rotated_response())
        respx.get("https://api.github.com/user").respond(200, json={"login": "connected-github"})
        done = client.get("/auth/github/callback", params={"code": "test-code", "state": query["state"][0]})
    after = datetime.now(timezone.utc)
    assert done.status_code == 303
    saved = connections.load(settings.koe_owner_id, "github")["token"]
    assert saved["refresh_token"] == "rotated-refresh"
    assert before + timedelta(seconds=28800) <= datetime.fromisoformat(saved["expiry"]) <= after + timedelta(seconds=28800)
    assert before + timedelta(seconds=15897600) <= datetime.fromisoformat(saved["refresh_expiry"]) <= after + timedelta(seconds=15897600)
    encrypted = asyncio.run(sql("select token_enc from koe_connections where owner_id = %s and provider = 'github'",
                                settings.koe_owner_id))[0]["token_enc"]
    assert "rotated-access" not in encrypted and "rotated-refresh" not in encrypted


def test_unexpired_cached_access_is_reused_without_refresh(clock):
    save_token(access_token="valid-access", expiry=(START + timedelta(hours=2)).isoformat())
    with respx.mock:
        assert connections.github_account()["token"] == "valid-access"
        assert connections.github_account()["token"] == "valid-access"
    assert connections.load(settings.koe_owner_id, "github")["token"]["refresh_token"] == "old-refresh"


@pytest.mark.parametrize("owner", ["owner", "invited-reviewer"])
def test_expired_access_refreshes_for_same_person_and_persists_rotated_tokens(clock, owner):
    user_id = settings.koe_owner_id if owner == "owner" else owner
    context = identity.OWNER.set(user_id)
    try:
        save_token()
        with respx.mock:
            refresh, me = mock_refresh()
            account = connections.github_account()
        assert account["token"] == "rotated-access" and account["login"] == "connected-github"
        assert refresh.call_count == 1 and me.call_count == 1
        sent = parse_qs(refresh.calls.last.request.content.decode())
        assert sent == {"client_id": ["test-github-client"], "client_secret": ["test-github-secret"],
                        "grant_type": ["refresh_token"], "refresh_token": ["old-refresh"]}
        assert refresh.calls.last.request.headers["accept"] == "application/json"
        assert me.calls.last.request.headers["authorization"] == "Bearer rotated-access"
        saved = connections.load(user_id, "github")["token"]
        assert saved["refresh_token"] == "rotated-refresh" and saved["access_token"] == "rotated-access"
        assert datetime.fromisoformat(saved["expiry"]) == START + timedelta(seconds=28800)
        assert datetime.fromisoformat(saved["refresh_expiry"]) == START + timedelta(seconds=15897600)
        encrypted = asyncio.run(sql("select token_enc from koe_connections where owner_id = %s and provider = 'github'",
                                    user_id))[0]["token_enc"]
        assert "rotated-access" not in encrypted and "rotated-refresh" not in encrypted
    finally:
        identity.OWNER.reset(context)


def test_a_cached_access_token_is_refreshed_when_it_expires(clock):
    save_token(access_token="valid-access", expiry=(START + timedelta(minutes=10)).isoformat())
    assert connections.github_account()["token"] == "valid-access"
    clock.current = START + timedelta(hours=1)
    with respx.mock:
        refresh, _ = mock_refresh()
        assert connections.github_account()["token"] == "rotated-access"
    assert refresh.call_count == 1


@pytest.mark.parametrize("failure", ["invalid_grant", "http_error", "different_account"])
def test_refresh_failure_or_identity_mismatch_never_uses_owner_environment_token(clock, failure):
    original = save_token()
    with respx.mock(assert_all_called=False) as router:
        if failure == "invalid_grant":
            router.post(REFRESH_URL).respond(200, json={"error": "bad_refresh_token"})
        elif failure == "http_error":
            router.post(REFRESH_URL).respond(401, json={"error": "bad_credentials"})
        else:
            router.post(REFRESH_URL).respond(200, json=rotated_response())
            router.get("https://api.github.com/user").respond(200, json={"login": "someone-else"})
        with pytest.raises(connections.ConnectionError_):
            connections.github_account()
    assert connections.load(settings.koe_owner_id, "github")["token"] == original


@pytest.mark.parametrize("changes", [
    {"refresh_token": ""},
    {"refresh_expiry": (START - timedelta(days=1)).isoformat()},
])
def test_expired_unrefreshable_connection_requires_reconnect_without_env_fallback(clock, changes):
    save_token(**changes)
    with respx.mock:
        with pytest.raises(connections.ConnectionError_):
            connections.github_account()


def test_concurrent_reads_rotate_a_refresh_token_only_once(clock, monkeypatch):
    save_token()
    barrier = Barrier(6)

    def read():
        barrier.wait(timeout=5)
        return connections.github_account()["token"]

    def reply(request):
        time.sleep(0.05)  # Concurrent readers must wait for the same rotation.
        return httpx.Response(200, json=rotated_response())

    # A standalone router/transport avoids respx's process-wide mock stack being
    # entered from copied worker contexts. Routes and call evidence stay local.
    router = respx.Router()
    refresh = router.post(REFRESH_URL).mock(side_effect=reply)
    me = router.get("https://api.github.com/user").respond(200, json={"login": "connected-github"})
    original_client = httpx.Client
    monkeypatch.setattr(connections.httpx, "Client", lambda **kwargs: original_client(
        transport=httpx.MockTransport(router.handler), **kwargs))
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(copy_context().run, read) for _ in range(6)]
        results = [future.result(timeout=10) for future in futures]
    assert results == ["rotated-access"] * 6
    assert refresh.call_count == me.call_count == 1
    assert connections.load(settings.koe_owner_id, "github")["token"]["refresh_token"] == "rotated-refresh"


@pytest.mark.parametrize("kind", [None, "personal_token"])
def test_legacy_nonexpiring_oauth_and_personal_tokens_still_work(clock, kind):
    token = {"access_token": "nonexpiring-access"}
    if kind:
        token["kind"] = kind
    connections.save(settings.koe_owner_id, "github", "connected-github", ["repo"], token)
    with respx.mock:
        assert connections.github_account()["token"] == "nonexpiring-access"
        clock.current = START + timedelta(days=365)
        assert connections.github_account()["token"] == "nonexpiring-access"
