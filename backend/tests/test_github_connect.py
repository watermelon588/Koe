"""ACCOUNTS_SPEC.md connections, GitHub: OAuth App + PKCE, token encrypted, repos chosen per person, tools use the
caller's token and never fall back to the owner's for anyone else. GitHub's endpoints are faked."""
import asyncio
import base64
import json
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx
from fastapi import FastAPI
from fastapi.testclient import TestClient

from koe import auth, connections, identity
from koe.config import settings
from koe.db import sql
from koe.tools import github_work
from test_auth import ADMIN, SITE, sign_in


@pytest.fixture
def client(monkeypatch):
    for name, value in {"google_web_client_id": "client-id", "google_web_client_secret": "client-secret",
                        "koe_admin_email": ADMIN, "koe_public_url": SITE, "github_client_id": "gh-client",
                        "github_client_secret": "gh-secret", "koe_secret_key": "a-test-secret-that-is-long-enough-for-koe-1234"}.items():
        monkeypatch.setattr(settings, name, value)
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(connections.api)
    return TestClient(app, follow_redirects=False)


def connect_github(client, login="octo-rohit"):
    started = client.get("/auth/github/connect")
    assert started.status_code == 302, started.text
    q = parse_qs(urlparse(started.headers["location"]).query)
    with respx.mock:
        exchange = respx.post(auth.GITHUB_TOKEN).mock(return_value=httpx.Response(200, json={
            "access_token": "gho_secret_token", "scope": "repo,read:user", "token_type": "bearer"}))
        respx.get("https://api.github.com/user").mock(return_value=httpx.Response(200, json={"login": login}))
        done = client.get("/auth/github/callback", params={"code": "c", "state": q["state"][0]})
    return q, exchange, done


def test_connecting_github_asks_for_repo_access_with_pkce_and_stores_the_token_encrypted(client, monkeypatch):
    assert client.get("/auth/github/connect").status_code == 401
    sign_in(client, monkeypatch, ADMIN)
    q, exchange, done = connect_github(client)
    assert q["client_id"] == ["gh-client"] and q["scope"] == ["repo read:user"] and q["allow_signup"] == ["false"]
    assert q["code_challenge_method"] == ["S256"] and q["redirect_uri"] == [f"{SITE}/auth/github/callback"]
    sent = parse_qs(exchange.calls.last.request.content.decode())
    assert exchange.calls.last.request.headers["accept"] == "application/json" and sent["code_verifier"][0]
    assert done.headers["location"] == "/?connected=github#settings"
    row = asyncio.run(sql("select account, token_enc from koe_connections where provider = 'github'"))[0]
    assert row["account"] == "octo-rohit" and "gho_secret_token" not in row["token_enc"]
    assert {"provider": "github", "connected": True, "account": "octo-rohit"} in client.get("/api/connections").json()["connections"]


def test_repos_are_listed_from_github_and_chosen_per_person(client, monkeypatch):
    sign_in(client, monkeypatch, ADMIN)
    connect_github(client)
    with respx.mock:
        listed = respx.get(f"{connections.GITHUB_API}/user/repos").mock(return_value=httpx.Response(200, json=[
            {"full_name": "rohit/koe"}, {"full_name": "rohit/notes"}]))
        body = client.get("/api/connections/github/repos").json()
    assert body["repos"] == ["rohit/koe", "rohit/notes"] and listed.calls.last.request.headers["authorization"] == "Bearer gho_secret_token"
    assert client.put("/api/connections/github/repos", json={"repos": ["not a repo"]}).status_code == 400
    assert client.put("/api/connections/github/repos", json={"repos": ["rohit/koe"]}).status_code == 204
    assert github_work.repositories() == ["rohit/koe"]


def test_tools_use_the_callers_token_and_a_friend_never_gets_the_owners(monkeypatch):
    monkeypatch.setattr(settings, "koe_secret_key", "a-test-secret-that-is-long-enough-for-koe-1234")
    monkeypatch.setattr(settings, "github_token", "ghp_owners_env_token")
    connections.save("friend-id", "github", "friend-login", ["repo"], {"access_token": "gho_friends_token"})

    async def whoami():
        with respx.mock:
            route = respx.get("https://api.github.com/user").mock(return_value=httpx.Response(200, json={}))
            await github_work.request("GET", "/user")
            return route.calls.last.request.headers["authorization"]

    assert asyncio.run(whoami()) == "Bearer ghp_owners_env_token"  # the owner: .env still works
    token = identity.OWNER.set("friend-id")
    try:
        assert asyncio.run(whoami()) == "Bearer gho_friends_token"
    finally:
        identity.OWNER.reset(token)
    token = identity.OWNER.set("someone-else")
    try:
        with pytest.raises(github_work.GitHubError, match="not connected"):
            asyncio.run(github_work.request("GET", "/user"))
        with pytest.raises(ValueError, match="Settings"):
            github_work.repositories()
    finally:
        identity.OWNER.reset(token)


def test_disconnecting_github_revokes_the_grant(client, monkeypatch):
    sign_in(client, monkeypatch, ADMIN)
    connect_github(client)
    with respx.mock:
        revoke = respx.delete(f"{connections.GITHUB_API}/applications/gh-client/grant").mock(return_value=httpx.Response(204))
        assert client.delete("/api/connections/github").status_code == 204
    request = revoke.calls.last.request
    assert request.headers["authorization"] == "Basic " + base64.b64encode(b"gh-client:gh-secret").decode()
    assert json.loads(request.content) == {"access_token": "gho_secret_token"}
    assert asyncio.run(sql("select * from koe_connections where provider = 'github'")) == []
