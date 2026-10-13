"""Per-person connections (ACCOUNTS_SPEC.md, connections): each person links their own Google (Calendar + Sheets),
later GitHub and Notion, and Koe's tools act with *their* account.

  GET    /api/connections            → [{provider, connected, account}]
  DELETE /api/connections/{provider} → forget it here and revoke it at the provider
  (Connecting is a browser redirect: GET /auth/google/connect, in auth.py.)

Tokens are encrypted with Fernet (AES-128-CBC + HMAC-SHA256) before they reach the database, under a key derived
from KOE_SECRET_KEY, which lives only in .env / Render: a copy of the table alone is useless.
https://cryptography.io/en/latest/fernet/
"""
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
    return {"ready": configured(), "connections": [
        {"provider": p, "connected": p in have, "account": have.get(p, "")} for p in PROVIDERS]}


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
