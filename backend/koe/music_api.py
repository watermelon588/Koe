"""Owner's manual music HTTP surface; isolated from Koe agent and voice paths."""
import asyncio
import time
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field

from koe import auth, spotify_service as sp, spotify_store as journal
from koe.config import settings

router = APIRouter(prefix="/api/music", route_class=sp.MusicRoute)


class Body(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)


class Generation(Body):
    connection_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


async def active(request: Request):
    async with sp.active_owner(request) as current:
        yield current


@router.get("/status")
async def status(current: str = Depends(sp.owner)):
    ready = sp.configured()
    reason, row = None, None
    try:
        row = await sp.connection(current)
    except sp.SpotifyError as exc:
        reason = exc.code
    generation = row["token"]["connection_id"] if row else None
    reconnect = await sp.sql("select value from koe_prefs where owner_id=%s and name='spotify_reconnect_required'", current)
    if reconnect and not row:
        reason = "spotify_reconnect_required"
        previous = await sp.sql("select value from koe_prefs where owner_id=%s and name='spotify_reconnect_connection_id'", current)
        generation = previous[0]["value"] if previous else None
    reconnect_required = reason in ("spotify_reconnect_required", "spotify_scope_missing")
    selected = await sp.sql("select value from koe_prefs where owner_id=%s and name='spotify_playlist_id'", current)
    if not ready:
        reason = "spotify_not_configured"
    elif not settings.spotify_enabled:
        reason = "spotify_disabled"
    usable = ready and settings.spotify_enabled and row is not None
    return {"contract_version": sp.VERSION, "configured": ready, "enabled": settings.spotify_enabled,
            "connected": row is not None, "reconnect_required": reconnect_required,
            "connection_id": generation, "selected_playlist_id": selected[0]["value"] if selected else None,
            "capabilities": {"connect": ready and settings.spotify_enabled, "playlist_read": usable,
                             "playlist_write": usable, "playback": usable, "remove_occurrence": False,
                             "remove_all_occurrences": usable, "voice_control": usable and settings.spotify_voice_approved},
            "unavailable_reason": reason, "external_url": "https://open.spotify.com/"}


@router.post("/sdk-token")
async def sdk_token(body: Generation, current: str = Depends(active)):
    token = await sp.access_token(current, body.connection_id)
    return {"access_token": token["access_token"], "expires_at": token["expires_at"], "connection_id": token["connection_id"]}


class Selection(Generation):
    playlist_id: str = Field(pattern=r"^[A-Za-z0-9]{22}$")


class Intent(Generation):
    request_id: str = Field(min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class CreatePlaylist(Intent):
    name: str = Field(min_length=1, max_length=100)


class Snapshot(Intent):
    snapshot_id: str = Field(min_length=1, max_length=256)


class Item(Snapshot):
    uri: str = Field(pattern=r"^spotify:track:[A-Za-z0-9]{22}$")


class Removal(Item):
    remove_all_occurrences: Literal[True]


class Order(Snapshot):
    range_start: int = Field(ge=0, le=5000)
    insert_before: int = Field(ge=0, le=5001)
    range_length: int = Field(default=1, ge=1, le=1)


class Device(Generation):
    device_id: str = Field(min_length=1, max_length=256, pattern=r"^[A-Za-z0-9_-]+$")


class PlaybackIntent(Intent, Device):
    pass


class Transfer(PlaybackIntent):
    operation: Literal["transfer"]


class Play(PlaybackIntent):
    operation: Literal["play"]
    position: int = Field(default=0, ge=0, le=5000)
    snapshot_id: str | None = Field(default=None, min_length=1, max_length=256)


class Shuffle(PlaybackIntent):
    operation: Literal["shuffle"]
    state: bool


class Repeat(PlaybackIntent):
    operation: Literal["repeat"]
    state: Literal["off", "context", "track"]


def mutation_response(result):
    return JSONResponse(result, status_code=202 if result["state"] == "outcome_unknown" else 200, headers=sp.HEADERS)


@router.get("/playlists")
async def playlists(offset: int = Query(0, ge=0, le=5000), limit: int = Query(20, ge=1, le=50), current: str = Depends(active)):
    row = await sp.connection(current)
    data = await sp.request(current, "GET", "/me/playlists", params={"offset": offset, "limit": limit})

    def eligible(item):
        try:
            return sp.playlist(item, row["token"]["spotify_user_id"])
        except sp.SpotifyError as exc:
            if exc.code == "spotify_playlist_ineligible":
                return None
            raise
    result = sp.page(data, offset, limit, eligible)
    result["items"] = [item for item in result["items"] if item is not None]
    return result


@router.put("/playlist")
async def choose(body: Selection, current: str = Depends(active)):
    row = await sp.connection(current, body.connection_id)
    data = await sp.request(current, "GET", "/playlists/" + body.playlist_id, generation=body.connection_id)
    result = sp.playlist(data, row["token"]["spotify_user_id"])
    if result["id"] != body.playlist_id:
        raise sp.SpotifyError("spotify_unavailable", 503)
    await sp.set_playlist(current, body.playlist_id)
    return {"playlist": result}


@router.post("/playlists")
async def create_playlist(body: CreatePlaylist, current: str = Depends(active)):
    if not body.name.strip():
        raise sp.SpotifyError("spotify_invalid_request", 400, "Enter a playlist name.")
    ticket, replay = await journal.prepare(current, body.model_dump(), "create", {})
    if replay:
        return mutation_response(replay)
    row = await sp.connection(current, body.connection_id)
    token = await sp.access_token(current, body.connection_id)

    async def send():
        data = await sp.http("POST", sp.API_URL + "/me/playlists", access_token=token["access_token"],
                             json={"name": body.name.strip(), "public": False, "collaborative": False})
        result = sp.playlist(data, row["token"]["spotify_user_id"])
        await sp.set_playlist(current, result["id"])
        return {"playlist": result}
    return mutation_response(await journal.send(ticket, send))


@router.get("/playlist/items")
async def items(offset: int = Query(0, ge=0, le=5000), limit: int = Query(50, ge=1, le=50), current: str = Depends(active)):
    playlist = await sp.selected(current)
    data = await sp.request(current, "GET", "/playlists/" + playlist["id"] + "/items", params={"offset": offset, "limit": limit})
    position = iter(range(offset, offset + limit))
    result = sp.page(data, offset, limit, lambda item: {
        "position": next(position), "track": sp.track(item.get("item", item.get("track")) if isinstance(item, dict) else None)})
    # Do not label a concurrently changed page with the earlier snapshot.
    after = await sp.selected(current)
    if after["snapshot_id"] != playlist["snapshot_id"]:
        raise sp.SpotifyError("spotify_playlist_stale", message="Playlist changed while loading. Refresh it.")
    return {**result, "playlist": after}


@router.get("/search")
async def search(q: str = Query(min_length=1, max_length=100), offset: int = Query(0, ge=0, le=5000),
                 limit: int = Query(10, ge=1, le=10), current: str = Depends(active)):
    if not q.strip():
        raise sp.SpotifyError("spotify_invalid_request", 400)
    data = await sp.request(current, "GET", "/search", params={"q": q.strip(), "type": "track", "offset": offset, "limit": limit})
    return sp.page(data.get("tracks"), offset, limit, sp.track)


async def playlist_intent(current, body, operation):
    identifier = await sp.selected_id(current)
    ticket, replay = await journal.prepare(current, body.model_dump(), operation, {"playlist_id": identifier})
    if replay:
        return ticket, replay, None
    playlist = await sp.selected(current, body.connection_id)
    if playlist["snapshot_id"] != body.snapshot_id:
        raise sp.SpotifyError("spotify_playlist_stale", message="Playlist changed. Review a fresh preview.")
    return ticket, None, playlist


async def playlist_send(current, body, ticket, playlist, method, payload):
    token = await sp.access_token(current, body.connection_id)

    async def send():
        data = await sp.http(method, sp.API_URL + "/playlists/" + playlist["id"] + "/items",
                             access_token=token["access_token"], json=payload)
        snapshot = data.get("snapshot_id")
        if not isinstance(snapshot, str) or not 1 <= len(snapshot) <= 256:
            raise sp.SpotifyError("spotify_unavailable", 503)
        return {"snapshot_id": snapshot}
    return mutation_response(await journal.send(ticket, send))


@router.post("/playlist/items")
async def add_item(body: Item, current: str = Depends(active)):
    ticket, replay, playlist = await playlist_intent(current, body, "add")
    if replay:
        return mutation_response(replay)
    track = sp.track(await sp.request(current, "GET", "/tracks/" + body.uri.rsplit(":", 1)[1], generation=body.connection_id))
    if not track["playable"] or track["uri"] != body.uri:
        raise sp.SpotifyError("spotify_invalid_request", 400, "This track is unavailable for this account.")
    return await playlist_send(current, body, ticket, playlist, "POST", {"uris": [body.uri]})


@router.delete("/playlist/items")
async def remove_item(body: Removal, current: str = Depends(active)):
    ticket, replay, playlist = await playlist_intent(current, body, "remove_all")
    if replay:
        return mutation_response(replay)
    return await playlist_send(current, body, ticket, playlist, "DELETE", {"items": [{"uri": body.uri}], "snapshot_id": body.snapshot_id})


@router.put("/playlist/items/order")
async def reorder(body: Order, current: str = Depends(active)):
    ticket, replay, playlist = await playlist_intent(current, body, "reorder")
    if replay:
        return mutation_response(replay)
    if body.range_start >= playlist["total"] or body.insert_before > playlist["total"]:
        raise sp.SpotifyError("spotify_invalid_request", 400, "That playlist position no longer exists.")
    return await playlist_send(current, body, ticket, playlist, "PUT", {
        "range_start": body.range_start, "insert_before": body.insert_before, "range_length": 1, "snapshot_id": body.snapshot_id})


@router.get("/mutations/{request_id}")
async def mutation(request_id: str, connection_id: str = Query(min_length=1, max_length=64), current: str = Depends(active)):
    if not 1 <= len(request_id) <= 64:
        raise sp.SpotifyError("spotify_invalid_request", 400)
    try:
        await sp.connection(current, connection_id)
    except sp.SpotifyError as exc:
        if exc.code not in ("spotify_reconnect_required", "spotify_not_connected"):
            raise
        prior = await sp.sql("select value from koe_prefs where owner_id=%s and name='spotify_reconnect_connection_id'", current)
        if not prior or prior[0]["value"] != connection_id:
            raise
    row = await journal.lookup(current, connection_id, request_id)
    if not row:
        raise sp.SpotifyError("spotify_invalid_request", 400, "No recorded music action with that ID.")
    return mutation_response(await journal.view(row))


@router.post("/device")
async def register_device(body: Device, request: Request, current: str = Depends(active)):
    await sp.connection(current, body.connection_id)
    # SDK ready and the Web API device list can propagate at different times. Retry reads only;
    # never transfer/play until this exact SDK ID is independently observed and validated.
    # https://developer.spotify.com/documentation/web-playback-sdk/reference#ready
    try:
        async with asyncio.timeout(4):
            for attempt in range(8):
                data = await sp.request(current, "GET", "/me/player/devices", generation=body.connection_id)
                available = data.get("devices")
                if not isinstance(available, list) or len(available) > 100:
                    raise sp.SpotifyError("spotify_unavailable", 503)
                matches = [d for d in available if isinstance(d, dict) and d.get("id") == body.device_id]
                if matches:
                    if (len(matches) != 1 or matches[0].get("name") != "Koe Web Player"
                            or matches[0].get("type") != "Computer" or matches[0].get("is_restricted") is not False):
                        raise sp.SpotifyError("spotify_device_unavailable", message="Spotify did not identify this as an unrestricted Koe browser player. No playback was requested.")
                    break
                if attempt == 7:
                    raise TimeoutError
                await asyncio.sleep(.3)
    except TimeoutError:
        raise sp.SpotifyError("spotify_device_unavailable", message="Spotify has not listed this browser player yet. No playback was requested; press Play to retry.") from None
    record = {"device_id": body.device_id, "connection_id": body.connection_id, "expires_at": time.time() + 900}
    sp.devices[(current, auth._hash(request.cookies[auth.SESSION_COOKIE]))] = record
    return record


@router.post("/playback")
async def playback(body: Annotated[Transfer | Play | Shuffle | Repeat, Field(discriminator="operation")],
                   request: Request, current: str = Depends(active)):
    session = auth._hash(request.cookies[auth.SESSION_COOKIE])
    sp.device(current, session, body.connection_id, body.device_id)
    identifier = await sp.selected_id(current) if isinstance(body, Play) else None
    ticket, replay = await journal.prepare(current, body.model_dump(), "playback_" + body.operation,
                                           {"playlist_id": identifier, "session_hash": session})
    if replay:
        return mutation_response(replay)
    sp.device(current, session, body.connection_id, body.device_id)
    token = await sp.access_token(current, body.connection_id)
    if isinstance(body, Play):
        playlist = await sp.selected(current, body.connection_id)
        if body.snapshot_id is not None and body.snapshot_id != playlist['snapshot_id']:
            raise sp.SpotifyError('spotify_playlist_stale', message='Playlist changed after song selection. Ask again.')
        if body.position >= playlist["total"]:
            raise sp.SpotifyError("spotify_invalid_request", 400, "Choose a track in this playlist.")
        # Targeted state evidence prevents silent takeover when another device is active.
        state = await sp.request(current, "GET", "/me/player", generation=body.connection_id)
        if not isinstance(state.get("device"), dict) or state["device"].get("id") != body.device_id:
            raise sp.SpotifyError("spotify_device_unavailable", message="Transfer explicitly to this browser before playing.")
        path, params, payload = "/me/player/play", {"device_id": body.device_id}, {
            "context_uri": "spotify:playlist:" + playlist["id"], "offset": {"position": body.position}}
    elif isinstance(body, Transfer):
        path, params, payload = "/me/player", {}, {"device_ids": [body.device_id], "play": False}
    else:
        path, params, payload = "/me/player/" + body.operation, {"device_id": body.device_id, "state": str(body.state).lower()}, None

    async def send():
        await sp.http("PUT", sp.API_URL + path, access_token=token["access_token"], params=params,
                      **({"json": payload} if payload is not None else {}))
        return {"accepted": True}
    return mutation_response(await journal.send(ticket, send))


@router.get("/playback")
async def playback_state(request: Request, connection_id: str = Query(min_length=1, max_length=64),
                         device_id: str = Query(min_length=1, max_length=256), current: str = Depends(active)):
    await sp.connection(current, connection_id)
    sp.device(current, auth._hash(request.cookies[auth.SESSION_COOKIE]), connection_id, device_id)
    data = await sp.request(current, "GET", "/me/player", generation=connection_id)
    device = data.get("device")
    if not isinstance(device, dict) or device.get("id") != device_id or type(data.get("is_playing")) is not bool:
        return {"state": "unknown", "is_playing": None, "device_id": None}
    return {"state": "observed", "is_playing": data["is_playing"], "device_id": device_id}
