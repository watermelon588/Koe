"""Sign in with Google (ACCOUNTS_SPEC.md, identity): invite-only accounts and server-side sessions.

OpenID Connect authorization-code flow with PKCE, state and nonce:
https://developers.google.com/identity/openid-connect/openid-connect
  GET  /auth/google/start?next=/   → Google's consent page (state/nonce/PKCE verifier kept in a short HttpOnly cookie)
  GET  /auth/google/callback       → code → tokens → verified ID token → invited? → session cookie → back to `next`
  GET  /auth/google/connect?next=  → the same dance with Calendar + Sheets scopes and offline access, for a signed-in
                                     person: their tokens are stored encrypted (connections.py), no new session
  GET  /auth/status                → {"google": sign-in available?, "user": {...} | null}
  POST /auth/logout                → session revoked, cookie cleared (same-origin requests only)
  POST /api/ws-ticket              → a one-time, 60-second ticket for /ws/call and /ws/events

WebSockets go straight to the backend's own address (Vercel's proxy doesn't carry them), where the sign-in cookie
isn't sent, so the page trades its session for a ticket first. KOE_ACCESS_TOKEN still works everywhere, for local
development and scripts.

The session cookie is HttpOnly (no script can read it) and only its SHA-256 is stored. Signing in proves identity
only: Calendar, Sheets, GitHub and Notion are separate connections with their own consent.
"""
import asyncio
import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
from uuid import uuid4

import httpx
from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from google.auth.transport import requests as google_requests
from google.oauth2 import id_token

from koe import identity
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
    """The address the person is on: the Vite dev server locally, otherwise always KOE_PUBLIC_URL. It never comes
    from a header alone, so a forged Host can't steer Google's redirect (which must match a registered URI exactly),
    and it doesn't depend on how Vercel's and Render's proxies rewrite forwarding headers."""
    local_site = settings.koe_local_url.rstrip("/")
    if (request.headers.get("x-forwarded-host") or request.headers.get("host", "")) == local_site.removeprefix("http://").removeprefix("https://"):
        return local_site
    if not settings.koe_public_url:
        raise HTTPException(400, "Set KOE_PUBLIC_URL on the server to sign in from the web.")
    return settings.koe_public_url.rstrip("/")


def same_origin(request: Request) -> None:
    """CSRF guard for state-changing requests: the browser's Origin must be Koe's own site."""
    if request.headers.get("origin") != site(request):
        raise HTTPException(403, "That request didn't come from Koe.")


def _safe_next(path: str) -> str:
    return path if path.startswith("/") and not path.startswith("//") and "\\" not in path else "/"


def _cookie(response: Response, request: Request, name: str, value: str, seconds: int, path: str = "/") -> None:
    response.set_cookie(name, value, max_age=seconds, path=path, httponly=True, samesite="lax",
                        secure=site(request).startswith("https://"))


def _to_google(request: Request, next_path: str, scopes: list[str], extra: dict | None = None, **flow_extra) -> RedirectResponse:
    """Redirect to Google's consent page; state, nonce and the PKCE verifier wait in a 10-minute HttpOnly cookie."""
    origin = site(request)
    state, nonce, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    query = {
        "client_id": settings.google_web_client_id,
        "redirect_uri": f"{origin}/auth/google/callback",
        "response_type": "code",
        "scope": " ".join(scopes),
        "state": state,
        "nonce": nonce,
        "code_challenge": _b64(hashlib.sha256(verifier.encode()).digest()),
        "code_challenge_method": "S256",
        **(extra or {}),
    }
    response = RedirectResponse(f"{AUTHORIZE}?{urlencode(query)}", 302, headers=NO_STORE)
    flow = {"state": state, "nonce": nonce, "verifier": verifier, "next": _safe_next(next_path), **flow_extra}
    _cookie(response, request, FLOW_COOKIE, _b64(json.dumps(flow).encode()), FLOW_MINUTES * 60, path="/auth")
    return response


@router.get("/auth/google/start")
def start(request: Request, next: str = "/"):
    if not enabled():
        raise HTTPException(404, "Google sign-in isn't set up on this server.")
    return _to_google(request, next, ["openid", "email", "profile"], {"prompt": "select_account"}, purpose="signin")


@router.get("/auth/google/connect")
async def connect(request: Request, next: str = "/#settings", docs: bool = False):
    """Connect the signed-in person's Google Calendar + Sheets. `prompt=consent` + offline access makes Google send
    a refresh token, so Koe keeps working after the 1-hour access token expires.
    https://developers.google.com/identity/protocols/oauth2/web-server#offline"""
    from koe import connections  # connections imports auth
    if not enabled() or not connections.configured():
        raise HTTPException(404, "Connecting Google isn't set up on this server (Google client and KOE_SECRET_KEY).")
    user = await signed_in_user(request)
    if not user:
        raise HTTPException(401, "Sign in to Koe first.")
    _owner_only(user)
    extra = {"access_type": "offline", "prompt": "consent", "include_granted_scopes": "true", "login_hint": user["email"]}
    scopes = connections.GOOGLE_SCOPES + ([connections.DOCS_SCOPE, connections.DRIVE_FILE_SCOPE] if docs else [])
    return _to_google(request, next, scopes, extra, purpose="connect", owner=user["id"], docs=docs)


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

    if flow.get("purpose") == "connect":
        return await _finish_connect(request, flow, reply.json(), str(claims["email"]).lower(), back)

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


async def _finish_connect(request: Request, flow: dict, tokens: dict, account: str, back) -> RedirectResponse:
    from koe import connections
    user = await signed_in_user(request)
    if not user or user["id"] != flow.get("owner"):  # the person who started connecting must be the one finishing
        raise HTTPException(400, "Sign in to Koe again, then connect Google.")
    granted = str(tokens.get("scope", "")).split()
    required = {connections.CALENDAR_SCOPE, connections.SHEETS_SCOPE}
    if flow.get("docs"):
        required.update((connections.DOCS_SCOPE, connections.DRIVE_FILE_SCOPE))
    if not required <= set(granted):
        return back(_with_query(flow["next"], "connect=missing-scopes"))  # the person unticked a permission
    previous = None
    if not tokens.get('refresh_token'):
        try:
            previous = await asyncio.to_thread(connections.load, user["id"], "google")
        except connections.ConnectionError_:
            pass  # reconnect must also repair a connection encrypted under an old key
    refresh = tokens.get("refresh_token") or (previous["token"].get("refresh_token") if previous and previous["account"] == account else None)
    expiry = _now() + timedelta(seconds=int(tokens.get("expires_in", 3600)))
    await asyncio.to_thread(connections.save, user["id"], "google", account, granted, {
        "access_token": tokens["access_token"], "refresh_token": refresh, "expiry": expiry.isoformat()})
    return back(_with_query(flow["next"], "connected=google"))


def _with_query(path: str, query: str) -> str:
    """Put ?query before any #hash, so the page can read it from location.search."""
    base, _, fragment = path.partition("#")
    joined = f"{base}{'&' if '?' in base else '?'}{query}"
    return f"{joined}#{fragment}" if fragment else joined


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


# ── Access for /api/* and the WebSockets ───────────────────────────────────────────────────────────────

def _access_token_ok(supplied: str) -> bool:
    return bool(settings.koe_access_token) and hmac.compare_digest(supplied.encode(), settings.koe_access_token.encode())


def _owner_only(user: dict) -> str:
    # Connecting Google/GitHub is still owner-only, pending the owner's decision to let friends connect their own.
    if not user["is_admin"]:
        raise HTTPException(403, "Koe isn't ready for friends yet. The owner will tell you when it is.")
    return user["id"]


async def http_owner(request: Request) -> str:
    """Who is calling an /api endpoint: the signed-in owner (cookie), or anyone holding KOE_ACCESS_TOKEN."""
    user = await signed_in_user(request)
    if user:  # an invited friend acts as themselves: their own chat, approvals, hub and connected accounts
        identity.OWNER.set(user["id"])
        return user["id"]
    if _access_token_ok(request.headers.get("authorization", "").removeprefix("Bearer ").strip()):
        identity.OWNER.set(settings.koe_owner_id)
        return settings.koe_owner_id
    raise HTTPException(401, "Sign in to Koe.")


TICKET_SECONDS = 60
_tickets: dict[str, tuple[str, float]] = {}  # ponytail: in memory, one backend instance; a restart only voids tickets
_ticket_sessions: dict[str, str] = {}  # optional cookie proof for separately gated music commands


@router.post("/api/ws-ticket")
async def ws_ticket(request: Request, response: Response):
    response.headers.update(NO_STORE)
    owner = await http_owner(request)
    now = time.monotonic()
    for old in [t for t, (_, expires) in _tickets.items() if expires < now]:
        del _tickets[old]
        _ticket_sessions.pop(old, None)
    ticket = secrets.token_urlsafe(32)
    _tickets[ticket] = (owner, now + TICKET_SECONDS)
    if request.cookies.get(SESSION_COOKIE) and settings.spotify_voice_approved:
        _ticket_sessions[ticket] = _hash(request.cookies[SESSION_COOKIE])
    return {"ticket": ticket}


def consume_ticket_session(credential):
    if not isinstance(credential, str):
        return None
    session = _ticket_sessions.pop(credential, None)
    ticket = _tickets.get(credential)
    return session if ticket and ticket[1] >= time.monotonic() else None


def ws_required() -> bool:
    return bool(settings.koe_access_token) or enabled()


def ws_owner(credential) -> str | None:
    """The `token` in a WebSocket's first frame: a one-time ticket (used up here) or KOE_ACCESS_TOKEN."""
    if not isinstance(credential, str) or not credential:
        return None
    ticket = _tickets.pop(credential, None)
    _ticket_sessions.pop(credential, None)
    if ticket and ticket[1] >= time.monotonic():
        return ticket[0]
    return settings.koe_owner_id if _access_token_ok(credential) else None


# ── Connect GitHub (OAuth App, authorization code + PKCE) ──────────────────────────────────────────────
# https://docs.github.com/en/apps/oauth-apps/building-oauth-apps/authorizing-oauth-apps
GITHUB_AUTHORIZE = "https://github.com/login/oauth/authorize"
GITHUB_TOKEN = "https://github.com/login/oauth/access_token"
GITHUB_SCOPES = "repo read:user"  # repo: read PRs/CI and post approved comments, private repos included


@router.get("/auth/github/connect")
async def github_connect(request: Request, next: str = "/#settings"):
    from koe import connections
    if not connections.github_ready():
        raise HTTPException(404, "Connecting GitHub isn't set up on this server (GitHub OAuth App and KOE_SECRET_KEY).")
    user = await signed_in_user(request)
    if not user:
        raise HTTPException(401, "Sign in to Koe first.")
    _owner_only(user)
    state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(48)
    query = {"client_id": settings.github_client_id, "redirect_uri": f"{site(request)}/auth/github/callback",
             "scope": GITHUB_SCOPES, "state": state, "allow_signup": "false",
             "code_challenge": _b64(hashlib.sha256(verifier.encode()).digest()), "code_challenge_method": "S256"}
    response = RedirectResponse(f"{GITHUB_AUTHORIZE}?{urlencode(query)}", 302, headers=NO_STORE)
    flow = {"state": state, "verifier": verifier, "next": _safe_next(next), "purpose": "github", "owner": user["id"]}
    _cookie(response, request, FLOW_COOKIE, _b64(json.dumps(flow).encode()), FLOW_MINUTES * 60, path="/auth")
    return response


@router.get("/auth/github/callback")
async def github_callback(request: Request, code: str = "", state: str = "", error: str = ""):
    from koe import connections
    flow = _read_flow(request.cookies.get(FLOW_COOKIE))

    def back(path: str) -> RedirectResponse:
        response = RedirectResponse(path, 303, headers=NO_STORE)
        response.delete_cookie(FLOW_COOKIE, path="/auth")
        return response

    if error:
        return back(_with_query(flow["next"] if flow else "/#settings", "connect=cancelled"))
    if not flow or flow.get("purpose") != "github" or not state or not code or not hmac.compare_digest(state, flow.get("state", "")):
        raise HTTPException(400, "This GitHub link expired or was opened twice. Please try again.")
    user = await signed_in_user(request)
    if not user or user["id"] != flow.get("owner"):
        raise HTTPException(400, "Sign in to Koe again, then connect GitHub.")
    async with httpx.AsyncClient(timeout=15) as http:
        reply = await http.post(GITHUB_TOKEN, headers={"Accept": "application/json"}, data={
            "client_id": settings.github_client_id, "client_secret": settings.github_client_secret, "code": code,
            "redirect_uri": f"{site(request)}/auth/github/callback", "code_verifier": flow["verifier"]})
        token = reply.json().get("access_token") if reply.status_code == 200 else None
        if not token:
            return back(_with_query(flow["next"], "connect=github-failed"))
        me = await http.get("https://api.github.com/user", headers={"Authorization": f"Bearer {token}",
                                                                   "Accept": "application/vnd.github+json"})
    if me.status_code != 200:
        return back(_with_query(flow["next"], "connect=github-failed"))
    scopes = [x.strip() for x in str(reply.json().get("scope", "")).split(",") if x.strip()]
    await asyncio.to_thread(connections.save, user["id"], "github", me.json()["login"], scopes, {"access_token": token})
    connections.forget_github(user["id"])
    return back(_with_query(flow["next"], "connected=github"))
