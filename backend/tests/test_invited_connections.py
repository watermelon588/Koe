"""Invited users can connect their own providers without gaining owner access.

OAuth responses are synthetic; conftest isolates all storage in temporary SQLite.
"""
import asyncio
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from koe import auth, connections
from koe.config import settings
from koe.db import sql
from test_auth import ADMIN, SITE, sign_in

FRIEND = "reviewer@gmail.com"
GOOGLE_SCOPES = ["openid", "email", connections.CALENDAR_SCOPE, connections.SHEETS_SCOPE]


@pytest.fixture
def client(monkeypatch):
    for name, value in {
        "google_web_client_id": "google-client",
        "google_web_client_secret": "google-secret",
        "github_client_id": "github-client",
        "github_client_secret": "github-secret",
        "koe_secret_key": "invited-connection-test-secret-longer-than-32",
        "koe_admin_email": ADMIN,
        "koe_public_url": SITE,
    }.items():
        monkeypatch.setattr(settings, name, value)
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(connections.api)
    return TestClient(app, follow_redirects=False)


def invite_and_sign_in(client, monkeypatch):
    asyncio.run(sql("insert into koe_invites (email, invited_by, created) values (%s, %s, %s)",
                    FRIEND, ADMIN, "2026-10-26"))
    assert sign_in(client, monkeypatch, FRIEND, sub="reviewer-sub").status_code == 303
    user = client.get("/auth/status").json()["user"]
    assert user["is_admin"] is False and user["id"] != settings.koe_owner_id
    return user["id"]


def mock_exchange(provider, query, monkeypatch):
    if provider == "google":
        monkeypatch.setattr(auth, "verify_id_token", lambda token: {
            "sub": "reviewer-sub", "email": FRIEND, "email_verified": True,
            "nonce": query["nonce"][0],
        })
        return respx.post(auth.TOKEN).respond(200, json={
            "id_token": "synthetic-jwt", "access_token": "reviewer-google-access",
            "refresh_token": "reviewer-google-refresh", "expires_in": 3600,
            "scope": " ".join(GOOGLE_SCOPES),
        })
    respx.get("https://api.github.com/user").respond(200, json={"login": "reviewer-github"})
    return respx.post(auth.GITHUB_TOKEN).respond(200, json={
        "access_token": "reviewer-github-access", "scope": "repo,read:user",
    })


@pytest.mark.parametrize("provider", ["google", "github"])
def test_invited_person_completes_oauth_and_only_their_connection_changes(client, monkeypatch, provider):
    friend_id = invite_and_sign_in(client, monkeypatch)
    owner_account = ADMIN if provider == "google" else "owner-github"
    connections.save(settings.koe_owner_id, provider, owner_account, [], {"access_token": "owner-token"})
    owner_before = connections.load(settings.koe_owner_id, provider)

    started = client.get(f"/auth/{provider}/connect", params={"next": "/app/settings"})
    assert started.status_code == 302, started.text
    query = parse_qs(urlparse(started.headers["location"]).query)
    assert query["code_challenge_method"] == ["S256"]
    with respx.mock:
        exchange = mock_exchange(provider, query, monkeypatch)
        done = client.get(f"/auth/{provider}/callback", params={"code": "reviewer-code", "state": query["state"][0]})
    assert done.status_code == 303 and done.headers["location"] == f"/app/settings?connected={provider}"
    assert exchange.called
    row = asyncio.run(sql("select owner_id, token_enc from koe_connections where owner_id = %s and provider = %s",
                         friend_id, provider))[0]
    assert "reviewer-" not in row["token_enc"]
    assert connections.load(friend_id, provider)["token"]["access_token"] == f"reviewer-{provider}-access"
    assert connections.load(settings.koe_owner_id, provider) == owner_before
    listed = client.get("/api/connections").json()["connections"]
    account = FRIEND if provider == "google" else "reviewer-github"
    assert {"provider": provider, "connected": True, "account": account} in listed
    assert not any(c["account"] == owner_account for c in listed)


@pytest.mark.parametrize("provider", ["google", "github"])
def test_connection_callback_cannot_be_completed_by_a_different_signed_in_person(client, monkeypatch, provider):
    invite_and_sign_in(client, monkeypatch)
    started = client.get(f"/auth/{provider}/connect")
    assert started.status_code == 302, started.text
    query = parse_qs(urlparse(started.headers["location"]).query)
    flow_cookie = client.cookies.get(auth.FLOW_COOKIE)

    other = TestClient(client.app, follow_redirects=False)
    sign_in(other, monkeypatch, ADMIN, sub="owner-sub")
    switched_cookie = f"{auth.FLOW_COOKIE}={flow_cookie}; {auth.SESSION_COOKIE}={other.cookies.get(auth.SESSION_COOKIE)}"
    with respx.mock:
        exchange = mock_exchange(provider, query, monkeypatch)
        done = client.get(f"/auth/{provider}/callback", params={"code": "reviewer-code", "state": query["state"][0]},
                          headers={"cookie": switched_cookie})
    assert done.status_code == 400
    assert "Sign in to Koe again" in done.json()["detail"]
    if provider == "github":
        assert not exchange.called  # GitHub checks the session before exchanging credentials.
    assert asyncio.run(sql("select * from koe_connections")) == []


@pytest.mark.parametrize("provider", ["google", "github"])
def test_connect_still_rejects_people_without_a_session(client, provider):
    assert client.get(f"/auth/{provider}/connect").status_code == 401
