"""ACCOUNTS_SPEC.md identity: Google sign-in, invite list, sessions. Google's token endpoint and ID-token check are
faked; storage is the temp SQLite file from conftest."""
import asyncio
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from koe import auth
from koe.config import settings
from koe.db import sql

SITE = "http://testserver"
ADMIN = "owner@gmail.com"


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "google_web_client_id", "client-id")
    monkeypatch.setattr(settings, "google_web_client_secret", "client-secret")
    monkeypatch.setattr(settings, "koe_admin_email", ADMIN)
    monkeypatch.setattr(settings, "koe_public_url", SITE)
    app = FastAPI()
    app.include_router(auth.router)

    @app.get("/api/me")
    async def me(user=Depends(auth.current_user)):
        return user

    return TestClient(app, follow_redirects=False)


def sign_in(client, monkeypatch, email, sub="google-sub-1", verified=True, next_path="/"):
    """Start → (Google) → callback. Returns the callback response."""
    started = client.get("/auth/google/start", params={"next": next_path})
    query = parse_qs(urlparse(started.headers["location"]).query)
    monkeypatch.setattr(auth, "verify_id_token", lambda token: {
        "sub": sub, "email": email, "email_verified": verified, "name": "Someone", "nonce": query["nonce"][0]})
    with respx.mock:
        respx.post(auth.TOKEN).mock(return_value=httpx.Response(200, json={"id_token": "signed.jwt", "access_token": "x"}))
        return client.get("/auth/google/callback", params={"code": "the-code", "state": query["state"][0]})


def test_start_sends_people_to_google_with_pkce_state_and_nonce(client):
    r = client.get("/auth/google/start")
    assert r.status_code == 302 and r.headers["cache-control"] == "no-store"
    url = urlparse(r.headers["location"])
    q = parse_qs(url.query)
    assert f"{url.scheme}://{url.netloc}{url.path}" == auth.AUTHORIZE
    assert q["redirect_uri"] == [f"{SITE}/auth/google/callback"] and q["scope"] == ["openid email profile"]
    assert q["code_challenge_method"] == ["S256"] and len(q["code_challenge"][0]) == 43
    assert q["state"][0] and q["nonce"][0] and "client-secret" not in r.headers["location"]
    assert "httponly" in r.headers["set-cookie"].lower()


def test_the_owner_signs_in_and_keeps_their_existing_id(client, monkeypatch):
    r = sign_in(client, monkeypatch, ADMIN, next_path="/#chat")
    assert r.status_code == 303 and r.headers["location"] == "/#chat"
    cookie = [c for c in r.headers.get_list("set-cookie") if c.startswith(auth.SESSION_COOKIE + "=")][0].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    me = client.get("/api/me").json()
    assert me["id"] == settings.koe_owner_id and me["email"] == ADMIN and me["is_admin"] is True
    stored = asyncio.run(sql("select token_hash from koe_sessions"))
    assert len(stored[0]["token_hash"]) == 64 and client.cookies[auth.SESSION_COOKIE] != stored[0]["token_hash"]


def test_an_invited_friend_gets_their_own_account(client, monkeypatch):
    asyncio.run(sql("insert into koe_invites (email, invited_by, created) values (%s, %s, %s)", "friend@gmail.com", ADMIN, "x"))
    sign_in(client, monkeypatch, "Friend@Gmail.com", sub="friend-sub")
    me = client.get("/api/me").json()
    assert me["email"] == "friend@gmail.com" and me["id"] != settings.koe_owner_id and me["is_admin"] is False


def test_someone_not_invited_gets_no_account_and_no_session(client, monkeypatch):
    r = sign_in(client, monkeypatch, "stranger@gmail.com", sub="stranger")
    assert r.headers["location"] == "/?signin=not-invited"
    assert auth.SESSION_COOKIE not in client.cookies
    assert client.get("/api/me").status_code == 401
    assert asyncio.run(sql("select * from koe_users")) == []


def test_an_unverified_email_or_a_wrong_state_is_refused(client, monkeypatch):
    assert sign_in(client, monkeypatch, ADMIN, verified=False).status_code == 400
    client.get("/auth/google/start")
    assert client.get("/auth/google/callback", params={"code": "c", "state": "forged"}).status_code == 400
    assert client.get("/api/me").status_code == 401


def test_next_only_ever_points_inside_koe(client, monkeypatch):
    for evil in ("//evil.example", "https://evil.example", "/\\evil.example"):
        client.cookies.clear()
        assert sign_in(client, monkeypatch, ADMIN, next_path=evil).headers["location"] == "/"


def test_a_forged_host_cannot_steer_googles_redirect(client):
    r = client.get("/auth/google/start", headers={"x-forwarded-host": "evil.example", "x-forwarded-proto": "https"})
    assert parse_qs(urlparse(r.headers["location"]).query)["redirect_uri"] == [f"{SITE}/auth/google/callback"]


def test_logout_revokes_the_session_and_needs_koes_own_origin(client, monkeypatch):
    sign_in(client, monkeypatch, ADMIN)
    assert client.post("/auth/logout", headers={"origin": "https://evil.example"}).status_code == 403
    assert client.get("/api/me").status_code == 200
    stolen = client.cookies[auth.SESSION_COOKIE]
    assert client.post("/auth/logout", headers={"origin": SITE}).status_code == 204
    client.cookies.set(auth.SESSION_COOKIE, stolen)  # replaying the old cookie doesn't work either
    assert client.get("/api/me").status_code == 401


def test_an_expired_session_is_signed_out(client, monkeypatch):
    sign_in(client, monkeypatch, ADMIN)
    asyncio.run(sql("update koe_sessions set expires = %s", "2000-01-01T00:00:00+00:00"))
    assert client.get("/api/me").status_code == 401


def test_status_says_whether_sign_in_is_available(client, monkeypatch):
    assert client.get("/auth/status").json() == {"google": True, "user": None}
    monkeypatch.setattr(settings, "google_web_client_secret", "")
    assert client.get("/auth/status").json()["google"] is False
    assert client.get("/auth/google/start").status_code == 404


def test_a_replayed_id_token_with_another_nonce_is_refused(client, monkeypatch):
    started = client.get("/auth/google/start")
    state = parse_qs(urlparse(started.headers["location"]).query)["state"][0]
    monkeypatch.setattr(auth, "verify_id_token", lambda token: {
        "sub": "s", "email": ADMIN, "email_verified": True, "nonce": "from-another-sign-in"})
    with respx.mock:
        respx.post(auth.TOKEN).mock(return_value=httpx.Response(200, json={"id_token": "old.jwt"}))
        assert client.get("/auth/google/callback", params={"code": "c", "state": state}).status_code == 400
    assert client.get("/api/me").status_code == 401



def test_the_owner_trades_the_session_for_a_one_time_websocket_ticket(client, monkeypatch):
    assert client.post("/api/ws-ticket").status_code == 401
    sign_in(client, monkeypatch, ADMIN)
    ticket = client.post("/api/ws-ticket").json()["ticket"]
    assert auth.ws_owner(ticket) == settings.koe_owner_id
    assert auth.ws_owner(ticket) is None  # used up
    assert auth.ws_owner("session") is None and auth.ws_owner(None) is None


def test_a_signed_in_friend_cannot_use_koe_until_their_own_connections_exist(client, monkeypatch):
    # Every tool still uses the owner's GitHub/Calendar/Notion, so a friend is kept out of /api for now.
    asyncio.run(sql("insert into koe_invites (email, invited_by, created) values (%s, %s, %s)", "friend@gmail.com", ADMIN, "x"))
    sign_in(client, monkeypatch, "friend@gmail.com", sub="friend-sub")
    assert client.get("/auth/status").json()["user"]["email"] == "friend@gmail.com"
    assert client.post("/api/ws-ticket").status_code == 403


def test_the_access_token_still_works_for_scripts(client, monkeypatch):
    monkeypatch.setattr(settings, "koe_access_token", "tok")
    assert client.post("/api/ws-ticket", headers={"Authorization": "Bearer nope"}).status_code == 401
    assert client.post("/api/ws-ticket", headers={"Authorization": "Bearer tok"}).status_code == 200
    assert auth.ws_owner("tok") == settings.koe_owner_id
