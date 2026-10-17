"""Session-bound one-time Spotify OAuth; no Spotify voice tools."""
import secrets
import time
from datetime import timedelta
from urllib.parse import urlencode
from uuid import uuid4

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import RedirectResponse

from koe import auth, connections, spotify_service as sp
from koe.config import settings

router = APIRouter(route_class=sp.MusicRoute)
FLOW_COOKIE = "koe_spotify_flow"
CALLBACK = "/auth/spotify/callback"


@router.post("/auth/spotify/connect")
async def connect(request: Request, current: str = Depends(sp.owner)):
    sp.require_enabled()
    if settings.spotify_redirect_uri != auth.site(request) + CALLBACK:
        raise sp.SpotifyError("spotify_not_configured", message="Configure Spotify's exact Koe callback origin.")
    async with sp.owner_lock(current):
        unknown = await sp.sql("select request_id from koe_music_mutations where owner_id=%s "
                               "and state in ('sent','outcome_unknown') limit 1", current)
        if unknown:
            raise sp.SpotifyError("spotify_outcome_unknown", message="Inspect unresolved music actions before reconnecting, or disconnect explicitly.")
        now = auth._now()
        await sp.sql("delete from koe_spotify_flows where state_hash in "
                     "(select state_hash from koe_spotify_flows where expires <= %s limit 100)", now.isoformat())
        rows = await sp.sql("select count(*) as total from koe_spotify_flows where owner_id=%s", current)
        if rows[0]["total"] >= 10:
            raise sp.SpotifyError("spotify_invalid_request", 400, "Wait for the previous connection attempts to expire.")
        state, cookie = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        await sp.sql("insert into koe_spotify_flows "
                     "(state_hash,owner_id,session_hash,cookie_hash,redirect_uri,expires) values (%s,%s,%s,%s,%s,%s)",
                     auth._hash(state), current, auth._hash(request.cookies[auth.SESSION_COOKIE]), auth._hash(cookie),
                     settings.spotify_redirect_uri, (now + timedelta(minutes=10)).isoformat())
        query = {"client_id": settings.spotify_client_id, "response_type": "code",
                 "redirect_uri": settings.spotify_redirect_uri, "scope": " ".join(sp.SCOPES), "state": state}
        response = sp.JSONResponse({"authorize_url": "https://accounts.spotify.com/authorize?" + urlencode(query)})
        auth._cookie(response, request, FLOW_COOKIE, cookie, 600, path=CALLBACK)
        return response


def back(marker):
    response = RedirectResponse(f"/app/music?spotify={marker}", status_code=303, headers=sp.HEADERS)
    response.delete_cookie(FLOW_COOKIE, path=CALLBACK)
    return response


@router.get(CALLBACK)
async def callback(request: Request, code: str = "", state: str = "", error: str = ""):
    # Callback errors deliberately do not carry credentials or provider text to UI.
    try:
        current = await sp.owner(request)
        sp.require_enabled()
        cookie = request.cookies.get(FLOW_COOKIE, "")
        if not state or len(state) > 128 or not cookie or len(cookie) > 128 or len(code) > 4096:
            return back("error")
        if settings.spotify_redirect_uri != auth.site(request) + CALLBACK:
            return back("error")
        async with sp.owner_lock(current):
            now = auth._now().isoformat()
            rows = await sp.sql("update koe_spotify_flows set consumed=%s where state_hash=%s and owner_id=%s "
                                "and session_hash=%s and cookie_hash=%s and redirect_uri=%s and consumed is null "
                                "and expires>%s returning state_hash", now, auth._hash(state), current,
                                auth._hash(request.cookies[auth.SESSION_COOKIE]), auth._hash(cookie),
                                settings.spotify_redirect_uri, now)
            if not rows:
                return back("error")
            if error:
                return back("cancelled")
            if not code:
                return back("error")
            body = await sp.http("POST", sp.TOKEN_URL,
                                 auth=(settings.spotify_client_id, settings.spotify_client_secret),
                                 data={"grant_type": "authorization_code", "code": code,
                                       "redirect_uri": settings.spotify_redirect_uri})
            token = sp.token_fields(body)
            scopes = body.get("scope", "").split()
            if not set(sp.SCOPES) <= set(scopes):
                return back("error")
            profile = await sp.http("GET", sp.API_URL + "/me", access_token=token["access_token"])
            if any(not isinstance(profile.get(key), str) or not 1 <= len(profile[key]) <= 256
                   for key in ("account_id", "id")):
                return back("error")
            # Revalidate sign-in after provider latency, before committing the link.
            if await sp.owner(request) != current:
                return back("error")
            unknown = await sp.sql("select request_id from koe_music_mutations where owner_id=%s "
                                   "and state in ('sent','outcome_unknown') limit 1", current)
            if unknown:
                return back("error")
            token.update(authorized_at=time.time(), connection_id=uuid4().hex,
                         spotify_account_id=profile["account_id"], spotify_user_id=profile["id"])
            await sp.invalidate(current)
            await sp.io(connections.save, current, "spotify", "Spotify", scopes, token)
            return back("connected")
    except Exception:
        return back("error")


async def disconnect_response(request):
    # Also called from the existing dynamic connections route, so that cannot
    # bypass the Spotify session/origin/lock boundary regardless of router order.
    try:
        current = await sp.owner(request)
        async with sp.owner_lock(current):
            await sp.invalidate(current)
        return Response(status_code=204, headers=sp.HEADERS)
    except sp.SpotifyError as exc:
        return sp.error_response(exc)
    except Exception:
        return sp.error_response(sp.SpotifyError("spotify_storage_unavailable", 503))


@router.delete("/api/connections/spotify")
async def disconnect(request: Request):
    return await disconnect_response(request)
