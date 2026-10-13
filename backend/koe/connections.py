"""Per-person connections (ACCOUNTS_SPEC.md, connections): each person links their own Google (Calendar + Sheets),
later GitHub and Notion, and Koe's tools act with *their* account.

  GET    /api/connections            → [{provider, connected, account}]
  DELETE /api/connections/{provider} → forget it here and revoke it at the provider
  POST   /api/connections/google/timesheet → create "Koe timesheet" in the person's Drive with the Hours headers
  (Connecting is a browser redirect: GET /auth/google/connect, in auth.py.)

Tokens are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) before they reach the database, under a key derived
from KOE_SECRET_KEY, which lives only in .env / Render: a copy of the table alone is useless.
https://cryptography.io/en/latest/fernet/
"""
import asyncio
import base64
import hashlib
import json
from datetime import datetime, timezone

import httpx
from cryptography.fernet import Fernet, InvalidToken
from fastapi import APIRouter, Depends, HTTPException, Response
from google.auth.transport.requests import Request as GoogleRequest
from google.oauth2.credentials import Credentials

from koe import auth, identity
from koe.config import settings
from koe.db import _run, sql

PROVIDERS = ("google", "github", "notion")
GOOGLE_TOKEN = "https://oauth2.googleapis.com/token"
GOOGLE_REVOKE = "https://oauth2.googleapis.com/revoke"
CALENDAR_SCOPE = "https://www.googleapis.com/auth/calendar.events"
SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
GOOGLE_SCOPES = ["openid", "email", CALENDAR_SCOPE, SHEETS_SCOPE]
SHEETS_API = "https://sheets.googleapis.com/v4/spreadsheets"
TIMESHEET_HEADERS = ["Date", "Client", "Hours", "Note", "Koe action ID"]  # tools/sheets.py checks row 1 against these


class ConnectionError_(Exception):
    """A connection exists but can't be used (key missing or changed, scope missing)."""


def configured() -> bool:
    return len(settings.koe_secret_key) >= 32


def _box() -> Fernet:
    if not configured():
        raise ConnectionError_("Set KOE_SECRET_KEY (32+ random characters) on the server to store connections.")
    # Any long random string works: SHA-256 turns it into the 32-byte key Fernet needs.
    return Fernet(base64.urlsafe_b64encode(hashlib.sha256(settings.koe_secret_key.encode()).digest()))


def encrypt(data: dict) -> str:
    return _box().encrypt(json.dumps(data).encode()).decode()


def decrypt(token_enc: str) -> dict:
    try:
        return json.loads(_box().decrypt(token_enc.encode()))
    except InvalidToken:
        raise ConnectionError_("This connection was saved with a different KOE_SECRET_KEY. Reconnect it in Settings.") from None


def save(owner: str, provider: str, account: str, scopes: list[str], token: dict) -> None:
    """Sync: called from the OAuth callback (via asyncio.to_thread) and from tool threads after a refresh."""
    now = datetime.now(timezone.utc).isoformat()
    _run("insert into koe_connections (owner_id, provider, account, scopes, token_enc, created, updated) "
         "values (%s, %s, %s, %s, %s, %s, %s) on conflict (owner_id, provider) do update set "
         "account = excluded.account, scopes = excluded.scopes, token_enc = excluded.token_enc, updated = excluded.updated",
         (owner, provider, account, " ".join(scopes), encrypt(token), now, now))


def load(owner: str, provider: str) -> dict | None:
    rows = _run("select account, scopes, token_enc from koe_connections where owner_id = %s and provider = %s",
                (owner, provider))
    if not rows:
        return None
    return {"account": rows[0]["account"], "scopes": rows[0]["scopes"].split(), "token": decrypt(rows[0]["token_enc"])}


# ── Per-person settings (koe_prefs) ──────────────────────────────────────────────────────────────────
# Read synchronously (the Sheets tool validates a proposal outside any thread), so they're cached per process.
# ponytail: one backend instance; a second instance would need cache invalidation.
_prefs: dict[tuple[str, str], str] = {}


def pref(name: str, owner: str | None = None) -> str:
    owner = owner or identity.owner_id()
    if (owner, name) not in _prefs:
        rows = _run("select value from koe_prefs where owner_id = %s and name = %s", (owner, name))
        _prefs[(owner, name)] = rows[0]["value"] if rows else ""
    return _prefs[(owner, name)]


async def set_pref(name: str, value: str, owner: str | None = None) -> None:
    owner = owner or identity.owner_id()
    await sql("insert into koe_prefs (owner_id, name, value, updated) values (%s, %s, %s, %s) on conflict (owner_id, name) "
              "do update set value = excluded.value, updated = excluded.updated",
              owner, name, value, datetime.now(timezone.utc).isoformat())
    _prefs[(owner, name)] = value


def google_credentials(required_scopes: list[str]) -> Credentials | None:
    """The calling person's Google credentials, refreshed when expired, or None if they haven't connected Google.
    Runs in a worker thread (the tools call google_auth.credentials via asyncio.to_thread)."""
    owner = identity.owner_id()
    row = load(owner, "google")
    if not row:
        return None
    if not set(required_scopes) <= set(row["scopes"]):
        raise ConnectionError_("Koe needs more Google permissions. Reconnect Google in Settings → Connections.")
    token = row["token"]
    creds = Credentials(
        token=token.get("access_token"), refresh_token=token.get("refresh_token"), token_uri=GOOGLE_TOKEN,
        client_id=settings.google_web_client_id, client_secret=settings.google_web_client_secret, scopes=row["scopes"],
        expiry=datetime.fromisoformat(token["expiry"]).replace(tzinfo=None) if token.get("expiry") else None,  # google-auth: naive UTC
    )
    if not creds.valid:
        if not creds.refresh_token:
            raise ConnectionError_("Google access ended. Reconnect Google in Settings → Connections.")
        creds.refresh(GoogleRequest())
        save(owner, "google", row["account"], row["scopes"], {
            **token, "access_token": creds.token,
            "expiry": creds.expiry.replace(tzinfo=timezone.utc).isoformat() if creds.expiry else None})
    return creds


# The same gate as the rest of /api: the session cookie (or KOE_ACCESS_TOKEN); it also sets identity.OWNER.
api = APIRouter(prefix="/api/connections", dependencies=[Depends(auth.http_owner)])


@api.get("")
async def list_connections():
    rows = await sql("select provider, account from koe_connections where owner_id = %s", identity.owner_id())
    have = {r["provider"]: r["account"] for r in rows}
    sheet = await asyncio.to_thread(pref, "google_sheets_id", identity.owner_id())
    return {"ready": configured(), "timesheet": f"https://docs.google.com/spreadsheets/d/{sheet}/edit" if sheet else "",
            "connections": [{"provider": p, "connected": p in have, "account": have.get(p, "")} for p in PROVIDERS]}


@api.post("/google/timesheet")
async def create_timesheet():
    """A new spreadsheet in the person's own Drive, tab and headers exactly as the Sheets tool expects, so nobody
    copies an ID. https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/create"""
    from koe import google_auth
    try:
        creds = await asyncio.to_thread(google_auth.credentials, required_scopes=[SHEETS_SCOPE])
    except google_auth.GoogleAuthError as exc:
        raise HTTPException(409, str(exc)) from None
    body = {
        "properties": {"title": "Koe timesheet"},
        "sheets": [{"properties": {"title": settings.google_sheets_tab}, "data": [{"startRow": 0, "startColumn": 0, "rowData": [
            {"values": [{"userEnteredValue": {"stringValue": h}} for h in TIMESHEET_HEADERS]}]}]}],
    }
    async with httpx.AsyncClient(timeout=20) as http:
        r = await http.post(SHEETS_API, json=body, headers={"Authorization": f"Bearer {creds.token}"})
    if r.status_code != 200:
        raise HTTPException(502, "Google didn't create the sheet. Is the Google Sheets API enabled for this project?")
    sheet_id = r.json()["spreadsheetId"]
    await set_pref("google_sheets_id", sheet_id)
    return {"timesheet": f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"}


@api.delete("/{provider}", status_code=204)
async def disconnect(provider: str):
    if provider not in PROVIDERS:
        raise HTTPException(404, "No such connection.")
    owner = identity.owner_id()
    rows = await sql("select token_enc from koe_connections where owner_id = %s and provider = %s", owner, provider)
    if rows and provider == "google":
        try:  # best effort: also end Koe's access at Google (https://developers.google.com/identity/protocols/oauth2/web-server#tokenrevoke)
            token = decrypt(rows[0]["token_enc"])
            async with httpx.AsyncClient(timeout=10) as http:
                await http.post(GOOGLE_REVOKE, data={"token": token.get("refresh_token") or token.get("access_token")})
        except (ConnectionError_, httpx.HTTPError):
            pass
    await sql("delete from koe_connections where owner_id = %s and provider = %s", owner, provider)
    return Response(status_code=204)  # a 204 must have no body (FastAPI would send `null`)
