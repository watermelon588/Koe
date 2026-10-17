"""Spotify authorization uses isolated SQLite and mocked provider endpoints only."""
import asyncio
import time
import logging
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from koe import auth, connections, db, music_api, spotify_auth, spotify_service as spotify
from koe.config import settings

SITE = "https://koe.test"
SESSION = "owner-test-session"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(spotify, "devices", {})
    for name, value in {
        "koe_public_url": SITE, "koe_admin_email": "owner@test.com",
        "koe_secret_key": "a-test-secret-key-with-at-least-32-characters",
        "spotify_client_id": "spotify-client", "spotify_client_secret": "spotify-secret",
        "spotify_redirect_uri": SITE + "/auth/spotify/callback", "spotify_enabled": True,
    }.items():
        monkeypatch.setattr(settings, name, value)
    asyncio.run(db.sql("insert into koe_users (id, google_sub, email, name, created) values (%s,%s,%s,%s,%s)",
                       settings.koe_owner_id, "sub-owner", "owner@test.com", "Owner", auth._now().isoformat()))
    asyncio.run(db.sql("insert into koe_sessions (token_hash,user_id,created,expires) values (%s,%s,%s,%s)",
                       auth._hash(SESSION), settings.koe_owner_id, auth._now().isoformat(), "2099-01-01"))
    app = FastAPI()
    app.include_router(spotify_auth.router)
    app.include_router(music_api.router)
    app.include_router(connections.api)
    result = TestClient(app, base_url=SITE, follow_redirects=False)
    result.cookies.set(auth.SESSION_COOKIE, SESSION)
    result.headers["origin"] = SITE
    return result


def seed_connection(expired=False):
    connections.save(settings.koe_owner_id, "spotify", "Spotify account", spotify.SCOPES, {
        "access_token": "access-private", "refresh_token": "refresh-private",
        "expires_at": time.time() - 10 if expired else time.time() + 3600,
        "authorized_at": time.time(), "spotify_account_id": "immutable-account",
        "spotify_user_id": "spotify-owner", "connection_id": "generation-1",
    })


def start(client):
    response = client.post("/auth/spotify/connect", json={})
    assert response.status_code == 200, response.text
    return parse_qs(urlparse(response.json()["authorize_url"]).query)


def exchange_mocks():
    exchange = respx.post(spotify.TOKEN_URL).mock(return_value=httpx.Response(200, json={
        "access_token": "new-private-access", "refresh_token": "new-private-refresh",
        "expires_in": 3600, "token_type": "Bearer", "scope": " ".join(spotify.SCOPES)}))
    respx.get(spotify.API_URL + "/me").mock(return_value=httpx.Response(200, json={
        "account_id": "immutable-account", "id": "spotify-owner"}))
    return exchange


def test_connect_callback_is_bound_one_time_and_encrypted(client):
    query = start(client)
    assert query["redirect_uri"] == [SITE + "/auth/spotify/callback"]
    assert set(query["scope"][0].split()) == set(spotify.SCOPES)
    with respx.mock:
        exchange = exchange_mocks()
        url = "/auth/spotify/callback"
        params = {"code": "private-code", "state": query["state"][0]}
        done = client.get(url, params=params)
        replay = client.get(url, params=params)
    assert done.status_code == 303 and done.headers["location"] == "/app/music?spotify=connected"
    assert exchange.call_count == 1
    assert replay.headers["location"] == "/app/music?spotify=error"
    rows = asyncio.run(db.sql("select token_enc from koe_connections where provider='spotify'"))
    assert "private" not in rows[0]["token_enc"]
    assert "private" not in done.text
    assert done.headers["cache-control"] == "no-store"


def test_origin_and_session_required_even_with_development_bearer(client, monkeypatch):
    assert client.post("/auth/spotify/connect", json={}, headers={"origin": "https://evil.test"}).status_code == 403
    client.cookies.clear()
    monkeypatch.setattr(settings, "koe_access_token", "dev-token")
    assert client.post("/auth/spotify/connect", json={}, headers={"authorization": "Bearer dev-token"}).status_code == 401


def test_disabled_status_makes_no_provider_calls(client, monkeypatch):
    monkeypatch.setattr(settings, "spotify_enabled", False)
    with respx.mock:
        body = client.get("/api/music/status").json()
        assert body["enabled"] is False and body["capabilities"]["voice_control"] is False
        assert client.post("/auth/spotify/connect", json={}).json()["error"]["code"] == "spotify_disabled"


def test_refresh_keeps_omitted_refresh_token_and_disconnect_clears_locally(client):
    seed_connection(expired=True)
    with respx.mock:
        refresh = respx.post(spotify.TOKEN_URL).mock(return_value=httpx.Response(200, json={
            "access_token": "refreshed-private", "expires_in": 3600, "token_type": "Bearer"}))
        response = client.post("/api/music/sdk-token", json={"connection_id": "generation-1"})
        assert response.status_code == 200, response.text
        assert refresh.call_count == 1
        assert connections.load(settings.koe_owner_id, "spotify")["token"]["refresh_token"] == "refresh-private"
        assert client.delete("/api/connections/spotify").status_code == 204
    assert connections.load(settings.koe_owner_id, "spotify") is None
    assert client.post("/api/music/sdk-token", json={"connection_id": "generation-1"}).status_code == 409


@pytest.mark.parametrize("change", ["state", "cookie", "session", "expired", "owner"])
def test_callback_binding_failures_do_not_exchange_or_replace_existing_connection(client, change):
    seed_connection()
    query = start(client)
    state = query["state"][0]
    if change == "state":
        state = "wrong-state"
    elif change == "cookie":
        client.cookies.delete(spotify_auth.FLOW_COOKIE)
    elif change == "session":
        client.cookies.set(auth.SESSION_COOKIE, "different-session")
    elif change == "expired":
        asyncio.run(db.sql("update koe_spotify_flows set expires='2000-01-01'"))
    else:
        asyncio.run(db.sql("update koe_users set email='friend@test.com'"))
    with respx.mock:
        exchange = respx.post(spotify.TOKEN_URL).mock(return_value=httpx.Response(500))
        response = client.get("/auth/spotify/callback", params={"code": "private-code", "state": state})
    assert response.headers["location"] == "/app/music?spotify=error" and exchange.call_count == 0
    assert connections.load(settings.koe_owner_id, "spotify")["token"]["connection_id"] == "generation-1"


def test_consent_cancellation_preserves_old_connection_and_consumes_flow(client):
    seed_connection()
    query = start(client)
    with respx.mock:
        result = client.get("/auth/spotify/callback", params={"error": "access_denied", "state": query["state"][0]})
    assert result.headers["location"] == "/app/music?spotify=cancelled"
    assert connections.load(settings.koe_owner_id, "spotify")["token"]["connection_id"] == "generation-1"
    assert asyncio.run(db.sql("select consumed from koe_spotify_flows"))[0]["consumed"]


def test_missing_granted_scopes_rejects_callback_without_replacing_connection(client):
    seed_connection()
    query = start(client)
    with respx.mock:
        respx.post(spotify.TOKEN_URL).mock(return_value=httpx.Response(200, json={
            "access_token": "new-access", "refresh_token": "new-refresh", "token_type": "Bearer", "expires_in": 3600, "scope": "streaming"}))
        result = client.get("/auth/spotify/callback", params={"code": "code", "state": query["state"][0]})
    assert result.headers["location"] == "/app/music?spotify=error"
    assert connections.load(settings.koe_owner_id, "spotify")["token"]["connection_id"] == "generation-1"


def test_corrupt_encryption_key_and_old_generation_cannot_return_tokens(client, monkeypatch):
    seed_connection()
    old = client.post("/api/music/sdk-token", json={"connection_id": "obsolete"})
    assert old.json()["error"]["code"] == "spotify_generation_stale"
    monkeypatch.setattr(settings, "koe_secret_key", "different-secret-key-with-more-than-32-characters")
    response = client.post("/api/music/sdk-token", json={"connection_id": "generation-1"})
    assert response.json()["error"]["code"] == "spotify_reconnect_required"
    assert "private" not in response.text
    assert client.delete("/api/connections/spotify").status_code == 204


def test_invalid_grant_and_ambiguous_refresh_require_reconnect_without_retries(client):
    for response in (httpx.Response(400, json={"error": "invalid_grant"}), httpx.ReadTimeout("private-body")):
        seed_connection(expired=True)
        with respx.mock:
            refresh = respx.post(spotify.TOKEN_URL)
            refresh.mock(side_effect=response) if isinstance(response, Exception) else refresh.mock(return_value=response)
            result = client.post("/api/music/sdk-token", json={"connection_id": "generation-1"})
            assert refresh.call_count == 1
            assert result.json()["error"]["code"] == "spotify_reconnect_required"
            assert "private-body" not in result.text
        assert connections.load(settings.koe_owner_id, "spotify") is None


def test_concurrent_refresh_and_disconnect_never_restore_connection(client):
    seed_connection(expired=True)

    async def exercise():
        entered, release = asyncio.Event(), asyncio.Event()

        async def refresh(_request):
            entered.set()
            await release.wait()
            return httpx.Response(200, json={"access_token": "refreshed-private", "expires_in": 3600, "token_type": "Bearer"})

        with respx.mock:
            route = respx.post(spotify.TOKEN_URL).mock(side_effect=refresh)
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app), base_url=SITE,
                                         cookies={auth.SESSION_COOKIE: SESSION}, headers={"origin": SITE}) as http:
                first = asyncio.create_task(http.post("/api/music/sdk-token", json={"connection_id": "generation-1"}))
                await asyncio.wait_for(entered.wait(), 5)
                second = asyncio.create_task(http.post("/api/music/sdk-token", json={"connection_id": "generation-1"}))
                disconnect = asyncio.create_task(http.delete("/api/connections/spotify"))
                release.set()
                responses = await asyncio.gather(first, second, disconnect)
                assert responses[0].status_code == 200 and responses[2].status_code == 204
                assert route.call_count == 1
        assert await spotify.io(connections.load, settings.koe_owner_id, "spotify") is None
    asyncio.run(exercise())


def test_loopback_callback_origin_is_explicit_and_localhost_is_rejected(client, monkeypatch):
    monkeypatch.setattr(settings, "spotify_redirect_uri", "http://localhost:5173/auth/spotify/callback")
    assert client.get("/api/music/status").json()["configured"] is False
    monkeypatch.setattr(settings, "koe_local_url", "http://127.0.0.1:5173")
    monkeypatch.setattr(settings, "spotify_redirect_uri", "http://127.0.0.1:5173/auth/spotify/callback")
    result = client.post("/auth/spotify/connect", json={}, headers={"origin": "http://127.0.0.1:5173", "host": "127.0.0.1:5173"})
    assert result.status_code == 200, result.text


def test_disconnect_is_available_while_disabled_and_invalidates_pending_callback(client, monkeypatch):
    seed_connection()
    query = start(client)
    monkeypatch.setattr(settings, "spotify_enabled", False)
    assert client.delete("/api/connections/spotify").status_code == 204
    monkeypatch.setattr(settings, "spotify_enabled", True)
    with respx.mock:
        result = client.get("/auth/spotify/callback", params={"code": "code", "state": query["state"][0]})
    assert result.headers["location"] == "/app/music?spotify=error"


def test_error_envelopes_are_private_and_not_cached(client):
    response = client.post("/api/music/sdk-token", json={"connection_id": "anything", "unexpected": "private-metadata"})
    assert response.status_code == 400
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-koe-music-contract"] == "1.0.0"
    assert "private-metadata" not in response.text
    assert client.post("/api/music/sdk-token", content=b"x" * 17000).status_code == 400


def test_provider_and_callback_access_logs_do_not_include_music_queries_or_codes(caplog):
    with caplog.at_level(logging.INFO):
        logging.getLogger("httpx").info('HTTP Request: %s %s "%s %s %s"', "GET", "https://api.spotify.com/v1/search?q=private-song", "HTTP/1.1", 200, "OK")
        logging.getLogger("uvicorn.access").info('%s - "%s %s HTTP/%s" %d', "local", "GET", "/auth/spotify/callback?code=private-code", "1.1", 303)
        logging.getLogger("uvicorn.access").info('%s - "%s %s HTTP/%s" %d', "local", "GET", "/api/music/search?q=private-song", "1.1", 200)
        logging.getLogger("httpx").info('HTTP Request: %s %s "%s %s %s"', "GET", "https://example.com/ordinary", "HTTP/1.1", 200, "OK")
    assert "private-song" not in caplog.text and "private-code" not in caplog.text
    assert "example.com/ordinary" in caplog.text


def test_revoked_connection_retains_reconnect_status_after_reload(client):
    seed_connection(expired=True)
    with respx.mock:
        respx.post(spotify.TOKEN_URL).mock(return_value=httpx.Response(400, json={"error": "invalid_grant"}))
        client.post("/api/music/sdk-token", json={"connection_id": "generation-1"})
    status = client.get("/api/music/status").json()
    assert status["reconnect_required"] is True and status["unavailable_reason"] == "spotify_reconnect_required"
    client.delete("/api/connections/spotify")
    assert client.get("/api/music/status").json()["reconnect_required"] is False


def test_status_auth_errors_match_frontend_contract(client):
    asyncio.run(db.sql("update koe_users set email='invited-friend@test.com'"))
    response = client.get("/api/music/status")
    assert response.status_code == 403 and response.json()["error"]["code"] == "spotify_owner_required"
    client.cookies.clear()
    response = client.get("/api/music/status")
    assert response.status_code == 401 and response.json()["error"]["code"] == "spotify_sign_in_required"
