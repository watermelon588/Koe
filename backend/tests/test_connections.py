"""ACCOUNTS_SPEC.md connections: per-person Google (Calendar + Sheets), tokens encrypted at rest. Google's token,
revoke and refresh endpoints are faked; storage is conftest's temp SQLite file."""
import asyncio
from datetime import datetime, timedelta, timezone
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
import respx

from koe import auth, connections, google_auth, identity
from koe.config import settings
from koe.db import sql
from fastapi import FastAPI
from fastapi.testclient import TestClient
from test_auth import ADMIN, SITE, sign_in

SECRET = "a-test-secret-that-is-long-enough-for-koe-1234"
GRANTED = f"openid https://www.googleapis.com/auth/userinfo.email {connections.CALENDAR_SCOPE} {connections.SHEETS_SCOPE}"


@pytest.fixture(autouse=True)
def secret(monkeypatch):
    monkeypatch.setattr(settings, "koe_secret_key", SECRET)
    monkeypatch.setattr(settings, 'github_token', '')


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(settings, "google_web_client_id", "client-id")
    monkeypatch.setattr(settings, "google_web_client_secret", "client-secret")
    monkeypatch.setattr(settings, "koe_admin_email", ADMIN)
    monkeypatch.setattr(settings, "koe_public_url", SITE)
    app = FastAPI()
    app.include_router(auth.router)
    app.include_router(connections.api)
    return TestClient(app, follow_redirects=False)


def connect(client, monkeypatch, scope=GRANTED, email=ADMIN):
    started = client.get("/auth/google/connect")
    assert started.status_code == 302, started.text
    q = parse_qs(urlparse(started.headers["location"]).query)
    monkeypatch.setattr(auth, "verify_id_token", lambda token: {
        "sub": "google-sub-1", "email": email, "email_verified": True, "nonce": q["nonce"][0]})
    with respx.mock:
        respx.post(auth.TOKEN).mock(return_value=httpx.Response(200, json={
            "id_token": "jwt", "access_token": "ya29.secret-access", "refresh_token": "1//secret-refresh",
            "expires_in": 3599, "scope": scope}))
        return q, client.get("/auth/google/callback", params={"code": "c", "state": q["state"][0]})


def test_tokens_are_encrypted_and_a_changed_key_is_refused(monkeypatch):
    sealed = connections.encrypt({"refresh_token": "1//secret-refresh"})
    assert "secret-refresh" not in sealed and connections.decrypt(sealed) == {"refresh_token": "1//secret-refresh"}
    monkeypatch.setattr(settings, "koe_secret_key", "another-secret-that-is-also-long-enough-xyz")
    with pytest.raises(connections.ConnectionError_):
        connections.decrypt(sealed)
    monkeypatch.setattr(settings, "koe_secret_key", "short")
    assert not connections.configured()


def test_connecting_needs_sign_in_and_asks_google_for_offline_calendar_and_sheets(client, monkeypatch):
    assert client.get("/auth/google/connect").status_code == 401
    sign_in(client, monkeypatch, ADMIN)
    q, _ = connect(client, monkeypatch)
    assert set(q["scope"][0].split()) == {"openid", "email", connections.CALENDAR_SCOPE, connections.SHEETS_SCOPE}
    assert q["access_type"] == ["offline"] and q["prompt"] == ["consent"] and q["login_hint"] == [ADMIN]
    assert q["redirect_uri"] == ["http://testserver/auth/google/callback"]  # the one URI already registered


def test_a_connection_is_stored_encrypted_and_listed(client, monkeypatch):
    sign_in(client, monkeypatch, ADMIN)
    _, done = connect(client, monkeypatch)
    assert done.status_code == 303 and done.headers["location"] == "/?connected=google#settings"
    row = asyncio.run(sql("select * from koe_connections"))[0]
    assert row["owner_id"] == settings.koe_owner_id and row["account"] == ADMIN
    assert "secret-refresh" not in row["token_enc"] and "secret-access" not in row["token_enc"]
    listed = client.get("/api/connections").json()
    assert {"provider": "google", "connected": True, "account": ADMIN} in listed["connections"]
    assert {"provider": "github", "connected": False, "account": ""} in listed["connections"]
    assert auth.SESSION_COOKIE in client.cookies  # connecting doesn't replace the sign-in session


def test_unticking_a_permission_stores_nothing(client, monkeypatch):
    sign_in(client, monkeypatch, ADMIN)
    _, done = connect(client, monkeypatch, scope=f"openid {connections.CALENDAR_SCOPE}")
    assert done.headers["location"] == "/?connect=missing-scopes#settings"
    assert asyncio.run(sql("select * from koe_connections")) == []


def test_tools_use_the_connected_account_and_refresh_it_when_expired(monkeypatch):
    connections.save(settings.koe_owner_id, "google", ADMIN, GRANTED.split(), {
        "access_token": "old", "refresh_token": "1//r",
        "expiry": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat()})
    def refresh(self, request):
        self.token, self.expiry = "fresh", datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(hours=1)
    monkeypatch.setattr(connections.Credentials, "refresh", refresh)
    creds = google_auth.credentials(required_scopes=[google_auth.SHEETS_SCOPE])
    assert creds.token == "fresh" and creds.client_id == settings.google_web_client_id
    assert connections.load(settings.koe_owner_id, "google")["token"]["access_token"] == "fresh"  # saved back


def test_a_friend_never_falls_back_to_the_owners_calendar(monkeypatch, tmp_path):
    (tmp_path / "token.json").write_text("{}")
    monkeypatch.setattr(settings, "google_token_file", str(tmp_path / "token.json"))
    token = identity.OWNER.set("friend-id")
    try:
        with pytest.raises(google_auth.GoogleAuthError, match="Connect Google"):
            google_auth.credentials()
    finally:
        identity.OWNER.reset(token)


def test_disconnect_forgets_the_tokens_and_revokes_them_at_google(client, monkeypatch):
    sign_in(client, monkeypatch, ADMIN)
    connect(client, monkeypatch)
    with respx.mock:
        revoke = respx.post(connections.GOOGLE_REVOKE).mock(return_value=httpx.Response(200))
        assert client.delete("/api/connections/google").status_code == 204
    assert revoke.called and b"secret-refresh" in revoke.calls[0].request.content
    assert asyncio.run(sql("select * from koe_connections")) == []


def test_create_my_timesheet_makes_the_sheet_the_tool_expects_and_uses_it(client, monkeypatch):
    from koe.tools import sheets
    sign_in(client, monkeypatch, ADMIN)
    connect(client, monkeypatch)
    monkeypatch.setattr(google_auth, "credentials", lambda **kw: type("C", (), {"token": "ya29.t"})())
    with respx.mock:
        made = respx.post(connections.SHEETS_API).mock(return_value=httpx.Response(200, json={"spreadsheetId": "sheet_123"}))
        r = client.post("/api/connections/google/timesheet")
    assert r.json() == {"timesheet": "https://docs.google.com/spreadsheets/d/sheet_123/edit"}
    sent = made.calls[0].request
    assert sent.headers["authorization"] == "Bearer ya29.t" and b'"Koe action ID"' in sent.content
    assert client.get("/api/connections").json()["timesheet"].endswith("/sheet_123/edit")
    assert sheets.prepare_hours("2026-10-13", "Acme", 2)["spreadsheet_id"] == "sheet_123"


def test_a_friend_without_a_timesheet_never_writes_to_the_owners(monkeypatch):
    from koe.tools import sheets
    monkeypatch.setattr(settings, "google_sheets_id", "owners_sheet")
    assert sheets.timesheet_id() == "owners_sheet"  # the owner keeps GOOGLE_SHEETS_ID
    token = identity.OWNER.set("friend-id")
    try:
        with pytest.raises(ValueError, match="Create my timesheet"):
            sheets.prepare_hours("2026-10-13", "Acme", 2)
    finally:
        identity.OWNER.reset(token)
