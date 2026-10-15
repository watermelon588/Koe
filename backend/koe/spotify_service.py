"""Manual Spotify adapter. Never imported by tools, model context, or voice transport.

One backend process; all music operations serialize per owner, including refresh,
reconnect and disconnect. Crypto, DB and SSL setup run off the event loop.
"""
import asyncio
import json
import logging
import math
import re
import time
import weakref
from contextlib import asynccontextmanager
from contextvars import ContextVar
from urllib.parse import urlparse

import httpx
from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute

from koe import auth, connections, db
from koe.config import settings

VERSION = "1.0.0"
HEADERS = {"Cache-Control": "no-store", "X-Koe-Music-Contract": VERSION}
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_URL = "https://api.spotify.com/v1"
SCOPES = ["streaming", "user-read-email", "user-read-private", "user-read-playback-state",
          "user-modify-playback-state", "playlist-read-private", "playlist-modify-private"]
ID = re.compile(r"[A-Za-z0-9]{22}")
URI = re.compile(r"spotify:track:[A-Za-z0-9]{22}")
_locks = weakref.WeakKeyDictionary()
# In-memory registration is invalidated by restart, disconnect and replacement.
devices: dict[tuple[str, str], dict] = {}
sent_intent = ContextVar("spotify_sent_intent", default=None)


class PrivacyFilter(logging.Filter):
    """Suppress third-party access logs containing music searches or OAuth codes."""
    def filter(self, record):
        args = record.args if isinstance(record.args, tuple) else ()
        if record.name == "httpx" and len(args) >= 2:
            try:
                if urlparse(str(args[1])).hostname in ("api.spotify.com", "accounts.spotify.com"):
                    return False
            except ValueError:
                return False
        if record.name == "uvicorn.access" and len(args) >= 3:
            path = str(args[2]).split("?", 1)[0]
            if path.startswith("/api/music/") or path.startswith("/auth/spotify/"):
                return False
        return True


for _logger_name in ("httpx", "uvicorn.access"):
    logging.getLogger(_logger_name).addFilter(PrivacyFilter())


class SpotifyError(Exception):
    def __init__(self, code, status=409, message="Spotify is unavailable for this action.", retry_after=None):
        self.code, self.status, self.message, self.retry_after = code, status, message, retry_after


def error_response(exc):
    error = {"code": exc.code, "message": exc.message, "outcome": "not_sent"}
    headers = dict(HEADERS)
    if exc.retry_after is not None:
        error["retry_after_seconds"] = exc.retry_after
        headers["Retry-After"] = str(exc.retry_after)
    return JSONResponse({"error": error}, status_code=exc.status, headers=headers)


class MusicRoute(APIRoute):
    def get_route_handler(self):
        handler = super().get_route_handler()

        async def bounded(request):
            marker = sent_intent.set(None)
            try:
                async with asyncio.timeout(30):
                    if request.method in ("POST", "PUT", "DELETE"):
                        chunks, size = [], 0
                        async for chunk in request.stream():
                            size += len(chunk)
                            if size > 16_384:
                                raise SpotifyError("spotify_invalid_request", 400, "The music request is too large.")
                            chunks.append(chunk)
                        request._body = b"".join(chunks)
                    response = await handler(request)
                response.headers.update(HEADERS)
                return response
            except SpotifyError as exc:
                return error_response(exc)
            except RequestValidationError:
                return error_response(SpotifyError("spotify_invalid_request", 400, "Check the music request fields."))
            except HTTPException as exc:
                code = {401: "spotify_sign_in_required", 403: "spotify_owner_required"}.get(exc.status_code, "spotify_invalid_request")
                return error_response(SpotifyError(code, exc.status_code, "Sign in as the Koe owner."))
            except TimeoutError:
                if sent_intent.get():
                    return JSONResponse({"request_id": sent_intent.get(), "state": "outcome_unknown", "result": None}, status_code=202, headers=HEADERS)
                return error_response(SpotifyError("spotify_unavailable", 503, "The music request timed out."))
            except Exception:
                if sent_intent.get():
                    return JSONResponse({"request_id": sent_intent.get(), "state": "outcome_unknown", "result": None}, status_code=202, headers=HEADERS)
                # No provider bodies, credentials, SQL or private metadata in logs/errors.
                return error_response(SpotifyError("spotify_storage_unavailable", 503, "Music storage is temporarily unavailable."))
            finally:
                sent_intent.reset(marker)
        return bounded


async def io(function, *args):
    """Do not release an owner lock while a canceled DB/crypto thread still runs."""
    task = asyncio.create_task(asyncio.to_thread(function, *args))
    try:
        return await asyncio.shield(task)
    except asyncio.CancelledError:
        try:
            await task
        finally:
            raise


async def sql(query, *params):
    return await io(db._run, query, params)


def owner_lock(owner):
    locks = _locks.setdefault(asyncio.get_running_loop(), {})
    return locks.setdefault(owner, asyncio.Lock())


async def owner(request: Request):
    user = await auth.signed_in_user(request)
    if not user:
        raise SpotifyError("spotify_sign_in_required", 401, "Sign in to Koe first.")
    if not user["is_admin"] or user["id"] != settings.koe_owner_id:
        raise SpotifyError("spotify_owner_required", 403, "Spotify is available only to the Koe owner.")
    if request.method not in ("GET", "HEAD"):
        if request.headers.get("origin") != auth.site(request):
            raise SpotifyError("spotify_origin_invalid", 403, "Open this action from Koe.")
    return user["id"]


def configured():
    try:
        parsed = urlparse(settings.spotify_redirect_uri)
        valid_origin = (parsed.scheme == "https" or
                        (parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "::1")))
        parsed.port  # validate a malformed configured port, too
        return bool(connections.configured() and settings.spotify_client_id and settings.spotify_client_secret
                    and valid_origin and parsed.hostname and parsed.hostname != "localhost"
                    and not parsed.username and not parsed.password and not parsed.query and not parsed.fragment
                    and parsed.path == "/auth/spotify/callback")
    except ValueError:
        return False


def require_enabled():
    if not configured():
        raise SpotifyError("spotify_not_configured", message="Spotify setup is incomplete.")
    if not settings.spotify_enabled:
        raise SpotifyError("spotify_disabled", message="Spotify is awaiting setup and policy verification.")


async def connection(owner, generation=None):
    try:
        row = await io(connections.load, owner, "spotify")
    except (connections.ConnectionError_, ValueError, KeyError):
        raise SpotifyError("spotify_reconnect_required", message="Reconnect Spotify in Settings.") from None
    if not row:
        raise SpotifyError("spotify_not_connected", message="Connect Spotify first.")
    token = row["token"]
    if not isinstance(token, dict) or not token.get("connection_id") or not token.get("refresh_token"):
        raise SpotifyError("spotify_reconnect_required", message="Reconnect Spotify in Settings.")
    if generation is not None and token["connection_id"] != generation:
        raise SpotifyError("spotify_generation_stale", message="Spotify changed. Refresh the music screen.")
    if not set(SCOPES) <= set(row["scopes"]):
        raise SpotifyError("spotify_scope_missing", 403, "Reconnect Spotify to grant the required permissions.")
    return row


@asynccontextmanager
async def active_owner(request: Request):
    # Used via a small yielding dependency in music_api.
    current = await owner(request)
    require_enabled()
    async with owner_lock(current):
        yield current


async def http(method, url, *, access_token=None, **kwargs):
    """Fixed caller-selected hosts only, finite response budget, no write retries."""
    if not (url == TOKEN_URL or url.startswith(API_URL + "/")):
        raise ValueError("Unsupported Spotify destination")
    headers = {"Authorization": f"Bearer {access_token}"} if access_token else {}
    client = await io(lambda: httpx.AsyncClient(timeout=10, trust_env=False, follow_redirects=False))
    try:
        async with asyncio.timeout(12):
            async with client.stream(method, url, headers=headers, follow_redirects=False, **kwargs) as response:
                chunks, size = [], 0
                async for chunk in response.aiter_bytes():
                    size += len(chunk)
                    if size > 1_048_576:
                        raise SpotifyError("spotify_unavailable", 503)
                    chunks.append(chunk)
                raw = b"".join(chunks)
                status = response.status_code
                if status >= 300:
                    # Inspect only a bounded allowlisted error code, never expose the body.
                    try:
                        body = json.loads(raw)
                        reason = body.get("error", {})
                        code = reason.get("reason", "") if isinstance(reason, dict) else reason
                    except (ValueError, AttributeError):
                        code = ""
                    if code == "QUOTA_EXCEEDED":
                        raise SpotifyError("spotify_quota_exceeded", 503)
                    if status == 429:
                        retry = response.headers.get("retry-after", "30")
                        delay = max(1, min(3600, int(retry))) if retry.isdigit() else 30
                        raise SpotifyError("spotify_rate_limited", 429, "Spotify is limiting requests. Wait before trying again.", delay)
                    if code in ("PREMIUM_REQUIRED", "PREMIUM_ACCOUNT_REQUIRED"):
                        raise SpotifyError("spotify_premium_required", 403, "Spotify Premium is required.")
                    if status == 401 or code == "invalid_grant":
                        raise SpotifyError("spotify_reconnect_required")
                    if status == 403:
                        raise SpotifyError("spotify_forbidden", 403, "Spotify denied this action. Check app access and permissions.")
                    if status == 404:
                        if url.startswith(API_URL + "/playlists/"):
                            raise SpotifyError("spotify_playlist_stale", message="The selected playlist is no longer available.")
                        raise SpotifyError("spotify_device_unavailable")
                    if status == 400:
                        raise SpotifyError("spotify_invalid_request", 400, "Spotify rejected this request. Review a fresh preview.")
                    raise SpotifyError("spotify_unavailable", 503)
                if status == 204:
                    return {}
                try:
                    result = json.loads(raw)
                except ValueError:
                    raise SpotifyError("spotify_unavailable", 503) from None
                if not isinstance(result, dict):
                    raise SpotifyError("spotify_unavailable", 503)
                return result
    except (httpx.HTTPError, TimeoutError):
        raise SpotifyError("spotify_unavailable", 503) from None
    finally:
        await client.aclose()


def token_fields(body, previous=None):
    previous = previous or {}
    access, refresh, expiry = body.get("access_token"), body.get("refresh_token", previous.get("refresh_token")), body.get("expires_in")
    if (not isinstance(access, str) or not 1 <= len(access) <= 8192 or
            not isinstance(refresh, str) or not 1 <= len(refresh) <= 8192 or
            type(expiry) not in (int, float) or not math.isfinite(expiry) or not 1 <= expiry <= 86400 or
            str(body.get("token_type", "")).lower() != "bearer"):
        raise SpotifyError("spotify_reconnect_required")
    return {**previous, "access_token": access, "refresh_token": refresh, "expires_at": time.time() + expiry}


async def invalidate(owner, *, reconnect=False):
    if reconnect:
        row = await io(connections.load, owner, "spotify")
        generation = row["token"].get("connection_id") if row else None
        if generation:
            await sql("insert into koe_prefs (owner_id,name,value,updated) values (%s,'spotify_reconnect_connection_id',%s,%s) "
                      "on conflict (owner_id,name) do update set value=excluded.value,updated=excluded.updated",
                      owner, generation, auth._now().isoformat())
        await sql("insert into koe_prefs (owner_id,name,value,updated) values (%s,'spotify_reconnect_required','true',%s) "
                  "on conflict (owner_id,name) do update set value=excluded.value,updated=excluded.updated",
                  owner, auth._now().isoformat())
    else:
        await sql("delete from koe_prefs where owner_id=%s and name in ('spotify_reconnect_required','spotify_reconnect_connection_id')", owner)
    await sql("delete from koe_connections where owner_id=%s and provider='spotify'", owner)
    await sql("delete from koe_prefs where owner_id=%s and name='spotify_playlist_id'", owner)
    await sql("delete from koe_spotify_flows where owner_id=%s", owner)
    if not reconnect:
        await sql("delete from koe_music_mutations where owner_id=%s", owner)
    for key in list(devices):
        if key[0] == owner:
            del devices[key]


async def access_token(owner, generation=None):
    """Caller holds owner_lock across this and all later provider requests."""
    row = await connection(owner, generation)
    token = row["token"]
    if type(token.get("expires_at")) not in (int, float) or not math.isfinite(token["expires_at"]):
        raise SpotifyError("spotify_reconnect_required")
    if token["expires_at"] <= time.time() + 60:
        try:
            body = await http("POST", TOKEN_URL,
                              auth=(settings.spotify_client_id, settings.spotify_client_secret),
                              data={"grant_type": "refresh_token", "refresh_token": token["refresh_token"]})
            updated = token_fields(body, token)
            scope = body.get("scope", " ".join(row["scopes"]))
            if not isinstance(scope, str):
                raise SpotifyError("spotify_reconnect_required")
            scopes = scope.split()
            if not set(SCOPES) <= set(scopes):
                raise SpotifyError("spotify_scope_missing", 403)
        except SpotifyError as exc:
            # A timed-out refresh may have rotated its refresh token: require renewed
            # consent rather than automatically replaying an ambiguous exchange.
            if exc.code not in ("spotify_rate_limited", "spotify_quota_exceeded"):
                await invalidate(owner, reconnect=True)
                raise SpotifyError("spotify_reconnect_required", message="Reconnect Spotify to renew access.") from None
            raise
        await io(connections.save, owner, "spotify", row["account"], scopes, updated)
        token = updated
    return token


async def request(owner, method, path, *, generation=None, **kwargs):
    token = await access_token(owner, generation)
    try:
        return await http(method, API_URL + path, access_token=token["access_token"], **kwargs)
    except SpotifyError as exc:
        if exc.code == "spotify_reconnect_required":
            await invalidate(owner, reconnect=True)
        raise


def text(value, limit=200):
    return value[:limit] if isinstance(value, str) else ""


def integer(value, maximum=1_000_000):
    if type(value) is not int or not 0 <= value <= maximum:
        raise SpotifyError("spotify_unavailable", 503)
    return value


def safe_url(value, *, image=False):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        parsed = urlparse(value)
        host = parsed.hostname or ""
        allowed = (host in ("i.scdn.co", "mosaic.scdn.co") or host.endswith(".spotifycdn.com")) if image else host == "open.spotify.com"
        return value if allowed and parsed.scheme == "https" and not parsed.username and not parsed.password and not parsed.port else None
    except ValueError:
        return None


def artwork(data):
    images = data.get("images", [])
    if not isinstance(images, list):
        return None
    for item in images[:10]:
        if isinstance(item, dict) and (url := safe_url(item.get("url"), image=True)):
            return url
    return None


def playlist(data, user_id):
    if not isinstance(data, dict):
        raise SpotifyError("spotify_unavailable", 503)
    if (data.get("public") is not False or data.get("collaborative") is not False or
            not isinstance(data.get("owner"), dict) or data["owner"].get("id") != user_id):
        raise SpotifyError("spotify_playlist_ineligible", 400, "Choose your own private, noncollaborative playlist.")
    identifier, snapshot = data.get("id"), data.get("snapshot_id")
    if not isinstance(identifier, str) or not ID.fullmatch(identifier) or not isinstance(snapshot, str) or not 1 <= len(snapshot) <= 256:
        raise SpotifyError("spotify_unavailable", 503)
    items = data.get("items", data.get("tracks", {}))
    if not isinstance(items, dict):
        raise SpotifyError("spotify_unavailable", 503)
    return {"id": identifier, "name": text(data.get("name")), "snapshot_id": snapshot,
            "spotify_url": "https://open.spotify.com/playlist/" + identifier,
            "image_url": artwork(data), "total": integer(items.get("total", 0))}


def track(data):
    data = data if isinstance(data, dict) else {}
    identifier, uri = data.get("id"), data.get("uri")
    valid = isinstance(identifier, str) and ID.fullmatch(identifier) and uri == "spotify:track:" + identifier
    kind = data.get("type") == "track" and not data.get("is_local")
    playable = bool(valid and kind and data.get("is_playable") is True and not data.get("restrictions"))
    album = data.get("album") if isinstance(data.get("album"), dict) else {}
    artists = data.get("artists") if isinstance(data.get("artists"), list) else []
    duration = data.get("duration_ms", 0)
    return {"id": identifier if valid and kind else None, "uri": uri if valid and kind else None,
            "name": text(data.get("name")) or "Unavailable item",
            "artists": [text(a.get("name")) for a in artists[:10] if isinstance(a, dict)],
            "album": text(album.get("name")), "image_url": artwork(album),
            "spotify_url": "https://open.spotify.com/track/" + identifier if valid and kind else None,
            "duration_ms": duration if type(duration) is int and 0 <= duration <= 86_400_000 else 0,
            "playable": playable, "unavailable_reason": None if playable else "unavailable_or_unsupported"}


def page(data, offset, limit, mapper):
    if not isinstance(data, dict) or not isinstance(data.get("items"), list) or len(data["items"]) > limit:
        raise SpotifyError("spotify_unavailable", 503)
    total = integer(data.get("total"))
    end = offset + len(data["items"])
    return {"items": [mapper(item) for item in data["items"]], "offset": offset, "limit": limit, "total": total,
            "next_offset": end if data["items"] and end < min(total, 5001) else None}


async def selected_id(owner):
    rows = await sql("select value from koe_prefs where owner_id=%s and name='spotify_playlist_id'", owner)
    if not rows or not ID.fullmatch(rows[0]["value"]):
        raise SpotifyError("spotify_playlist_required", message="Choose a private playlist first.")
    return rows[0]["value"]


async def selected(owner, generation=None):
    row = await connection(owner, generation)
    identifier = await selected_id(owner)
    data = await request(owner, "GET", "/playlists/" + identifier, generation=generation)
    result = playlist(data, row["token"]["spotify_user_id"])
    if result["id"] != identifier:
        raise SpotifyError("spotify_unavailable", 503)
    return result


async def set_playlist(owner, identifier):
    await sql("insert into koe_prefs (owner_id,name,value,updated) values (%s,'spotify_playlist_id',%s,%s) "
              "on conflict (owner_id,name) do update set value=excluded.value,updated=excluded.updated",
              owner, identifier, auth._now().isoformat())


def device(owner, session, generation, identifier):
    record = devices.get((owner, session))
    if not record or record["connection_id"] != generation or record["device_id"] != identifier or record["expires_at"] <= time.time():
        raise SpotifyError("spotify_device_unavailable", message="Reconnect this browser's Spotify player.")
    return record
