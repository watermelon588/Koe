"""Sign in with Google (ACCOUNTS_SPEC.md, identity): invite-only accounts and server-side sessions.

OpenID Connect authorization-code flow with PKCE, state and nonce:
https://developers.google.com/identity/openid-connect/openid-connect
  GET  /auth/google/start?next=/   → Google's consent page (state/nonce/PKCE verifier kept in a short HttpOnly cookie)
  GET  /auth/google/callback       → code → tokens → verified ID token → invited? → session cookie → back to `next`
  GET  /auth/status                → {"google": sign-in available?, "user": {...} | null}
  POST /auth/logout                → session revoked, cookie cleared (same-origin requests only)

The session cookie is HttpOnly (no script can read it) and only its SHA-256 is stored. Signing in proves identity
only: Calendar, Sheets, GitHub and Notion are separate connections with their own consent.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from koe.config import settings
from koe.db import sql

AUTHORIZE = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN = "https://oauth2.googleapis.com/token"
SESSION_COOKIE = "koe_session"
FLOW_COOKIE = "koe_oauth"
SESSION_DAYS = 30
FLOW_MINUTES = 10
LOCAL_SITE = "http://localhost:5173"  # Vite dev server, which proxies /auth to the backend
NO_STORE = {"Cache-Control": "no-store"}  # Vercel's proxy must never cache a sign-in answer

router = APIRouter()


def enabled() -> bool:
    return bool(settings.google_web_client_id and settings.google_web_client_secret)


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _b64(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()


def site(request: Request) -> str:
    """The address the person is on. Vercel's proxy sends x-forwarded-host/proto; Vite keeps Host. Only known sites
    pass: Google's redirect must match a registered URI exactly, and a forged Host header must not steer it."""
    host = request.headers.get("x-forwarded-host") or request.headers.get("host", "")
    proto = request.headers.get("x-forwarded-proto") or request.url.scheme
    origin = f"{proto}://{host}"
    if origin not in {settings.koe_public_url.rstrip("/"), LOCAL_SITE} - {""}:
        raise HTTPException(400, "Open Koe from its own address to sign in.")
    return origin


def same_origin(request: Request) -> None:
    """CSRF guard for state-changing requests: the browser's Origin must be Koe's own site."""
    if request.headers.get("origin") != site(request):
        raise HTTPException(403, "That request didn't come from Koe.")


def _safe_next(path: str) -> str:
    return path if path.startswith("/") and not path.startswith("//") and "\\" not in path else "/"


def _cookie(response: Response, request: Request, name: str, value: str, seconds: int, path: str = "/") -> None:
    response.set_cookie(name, value, max_age=seconds, path=path, httponly=True, samesite="lax",
                        secure=site(request).startswith("https://"))


@router.get("/auth/google/start")
def start(request: Request, next: str = "/"):
    if not enabled():
        raise HTTPException(404, "Google sign-in isn't set up on this server.")
    origin = site(request)
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    query = {
        "client_id": settings.google_web_client_id,
        "redirect_uri": f"{origin}/auth/google/callback",
        "response_type": "code",
        "scope": "openid email profile",
        "state": state,
        "nonce": nonce,
        "code_challenge": _b64(hashlib.sha256(verifier.encode()).digest()),
        "code_challenge_method": "S256",
        "prompt": "select_account",
    }
    response = RedirectResponse(f"{AUTHORIZE}?{urlencode(query)}", 302, headers=NO_STORE)
    flow = {"state": state, "nonce": nonce, "verifier": verifier, "next": _safe_next(next)}
    _cookie(response, request, FLOW_COOKIE, _b64(json.dumps(flow).encode()), FLOW_MINUTES * 60, path="/auth")
    return response


def verify_id_token(token: str) -> dict:
    """Signature (Google's published keys), expiry, issuer and audience: google-auth checks all four."""
    return id_token.verify_oauth2_token(token, google_requests.Request(), settings.google_web_client_id)


def _read_flow(raw: str | None) -> dict | None:
    try:
        return json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))) if raw else None
    except ValueError:
        return None


async def invited(email: str) -> bool:
    if settings.koe_admin_email and email == settings.koe_admin_email.lower():
        return True
    return bool(await sql("select 1 from koe_invites where email = %s", email))


async def save_user(sub: str, email: str, name: str) -> str:
    """The owner keeps id = KOE_OWNER_ID so everything Koe already stored for them stays theirs."""
    created = _now().isoformat()
    if settings.koe_admin_email and email == settings.koe_admin_email.lower():
        await sql("insert into koe_users (id, google_sub, email, name, created) values (%s, %s, %s, %s, %s) "
                  "on conflict (id) do update set google_sub = excluded.google_sub, email = excluded.email, "
                  "name = excluded.name", settings.koe_owner_id, sub, email, name, created)
        return settings.koe_owner_id
    rows = await sql("insert into koe_users (id, google_sub, email, name, created) values (%s, %s, %s, %s, %s) "
                     "on conflict (google_sub) do update set email = excluded.email, name = excluded.name "
                     "returning id", uuid4().hex, sub, email, name, created)
    return rows[0]["id"]


@router.get("/auth/google/callback")
async def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    origin = site(request)
    flow = _read_flow(request.cookies.get(FLOW_COOKIE))

    def back(path: str) -> RedirectResponse:
        response = RedirectResponse(path, 303, headers=NO_STORE)
        response.delete_cookie(FLOW_COOKIE, path="/auth")
        return response

    if error:  # e.g. the person pressed Cancel on Google's page
        return back("/?signin=cancelled")
    if not flow or not state or not code or not hmac.compare_digest(state, flow.get("state", "")):
        raise HTTPException(400, "This sign-in link expired or was opened twice. Please try again.")
    async with httpx.AsyncClient(timeout=15) as http:
        reply = await http.post(TOKEN, data={
            "code": code, "client_id": settings.google_web_client_id, "client_secret": settings.google_web_client_secret,
            "redirect_uri": f"{origin}/auth/google/callback", "grant_type": "authorization_code",
            "code_verifier": flow["verifier"],
        })
    if reply.status_code != 200 or "id_token" not in reply.json():
        raise HTTPException(400, "Google didn't accept this sign-in. Please try again.")
    try:
        claims = await asyncio.to_thread(verify_id_token, reply.json()["id_token"])
    except ValueError:
        raise HTTPException(400, "Google's answer couldn't be verified. Please try again.") from None
    if not hmac.compare_digest(str(claims.get("nonce", "")), flow["nonce"]) or not claims.get("email_verified"):
        raise HTTPException(400, "Google's answer couldn't be verified. Please try again.")

    email = str(claims["email"]).lower()
    if not await invited(email):
        return back("/?signin=not-invited")  # no account, no session
    user_id = await save_user(str(claims["sub"]), email, str(claims.get("name", "")))
    old = request.cookies.get(SESSION_COOKIE)
    if old:  # a new sign-in replaces the old session rather than adding to it
        await sql("update koe_sessions set revoked = %s where token_hash = %s", _now().isoformat(), _hash(old))
    token = secrets.token_urlsafe(32)
    now = _now()
    await sql("insert into koe_sessions (token_hash, user_id, created, expires) values (%s, %s, %s, %s)",
              _hash(token), user_id, now.isoformat(), (now + timedelta(days=SESSION_DAYS)).isoformat())
    response = back(flow["next"])
    _cookie(response, request, SESSION_COOKIE, token, SESSION_DAYS * 24 * 3600)
    return response


async def signed_in_user(request: Request) -> dict | None:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        return None
    rows = await sql("select u.id, u.email, u.name from koe_sessions s join koe_users u on u.id = s.user_id "
                     "where s.token_hash = %s and s.revoked is null and s.expires > %s", _hash(token), _now().isoformat())
    if not rows:
        return None
    return {**rows[0], "is_admin": bool(settings.koe_admin_email) and rows[0]["email"] == settings.koe_admin_email.lower()}


async def current_user(request: Request) -> dict:
    """FastAPI dependency for every per-user endpoint."""
    user = await signed_in_user(request)
    if not user:
        raise HTTPException(401, "Sign in to Koe.")
    return user


@router.get("/auth/status")
async def status(request: Request, response: Response):
    response.headers.update(NO_STORE)
    return {"google": enabled(), "user": await signed_in_user(request)}


@router.post("/auth/logout", status_code=204)
async def logout(request: Request):
    same_origin(request)
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        await sql("update koe_sessions set revoked = %s where token_hash = %s", _now().isoformat(), _hash(token))
    response = Response(status_code=204, headers=NO_STORE)
    response.delete_cookie(SESSION_COOKIE, path="/")
    return response
