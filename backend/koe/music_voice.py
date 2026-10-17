"""Owner-granted transport gateway, separate from voice and Spotify content.

One player window; lost acknowledgements are never replayed automatically.
"""
import asyncio
import contextlib
import hashlib
import json
import time
import secrets
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Literal

from fastapi import APIRouter, Depends, Request, WebSocket, WebSocketDisconnect
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from koe import auth, identity, spotify_service as sp, music_selection
from koe.config import settings

router = APIRouter(route_class=sp.MusicRoute)
ACTIONS = ('play', 'play_match', 'pause', 'next', 'previous', 'set_volume', 'volume_up', 'volume_down')
PROMPT = (" Use music_control only for the owner's explicitly allowed playlist. "
          "For an artist or named song use play_match with artist and/or title copied from the user's request. "
          "Matching happens outside your context. Never read Spotify metadata, edit playlists or invent track names. "
          "If not_found or unavailable, say it is not available in their playlist and suggest adding it from the search shown on Music. "
          "If ambiguous, ask for an artist or more specific title. Never add music automatically. "
          "Queued play/next/previous ends this call after your brief reply, then starts music. "
          "Say the handoff will happen; never claim queued music is already playing. "
          "Deferred volume applies at next playback. Report failures and unknown outcomes honestly.")


def declaration():
    return {'name': 'music_control', 'description':
            'Transport/volume and user-supplied artist/title selection in the explicitly allowed playlist on Music. '
            'Playback during a call queues a handoff after your reply. No music metadata returned.',
            'parameters_json_schema': {'type': 'object', 'properties': {
                'action': {'type': 'string', 'enum': list(ACTIONS)},
                'artist': {'type': 'string', 'maxLength': 200, 'description': 'Artist from the user request, only for play_match. Picks a random matching track unless title is specified.'},
                'title': {'type': 'string', 'maxLength': 200, 'description': 'Song title from the user request, only for play_match.'},
                'volume_percent': {'type': 'integer', 'minimum': 0, 'maximum': 100,
                                   'description': 'Required only for set_volume.'}},
                'required': ['action'], 'additionalProperties': False}}


class Command(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    action: Literal['play', 'play_match', 'pause', 'next', 'previous', 'set_volume', 'volume_up', 'volume_down']
    volume_percent: int | None = Field(default=None, ge=0, le=100)
    artist: str | None = Field(default=None, min_length=1, max_length=200)
    title: str | None = Field(default=None, min_length=1, max_length=200)


class Permission(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    connection_id: str = Field(min_length=1, max_length=64)
    playlist_id: str = Field(pattern=r'^[A-Za-z0-9]{22}$')
    enabled: bool


async def grant(owner):
    sp.require_enabled()
    if not settings.spotify_voice_approved:
        raise sp.SpotifyError('spotify_voice_not_approved', 403, 'Voice control is not enabled for this deployment.')
    row = await sp.connection(owner)
    playlist = await sp.selected_id(owner)
    rows = await sp.sql("select value from koe_prefs where owner_id=%s and name='spotify_voice_grant'", owner)
    try:
        value = json.loads(rows[0]['value']) if rows else {}
    except (TypeError, ValueError):
        value = {}
    if value != {'connection_id': row['token']['connection_id'], 'playlist_id': playlist}:
        raise sp.SpotifyError('spotify_voice_permission_required', 403, 'Allow voice control for this playlist in Music first.')
    return value


@router.get('/api/music/voice-permission')
async def permission(current: str = Depends(sp.owner)):
    allowed = None
    try:
        allowed = await grant(current)
    except sp.SpotifyError:
        pass
    return {'available': settings.spotify_voice_approved and sp.configured() and settings.spotify_enabled,
            'enabled': allowed is not None, 'grant': allowed}


@router.put('/api/music/voice-permission')
async def permit(body: Permission, current: str = Depends(sp.owner)):
    if not body.enabled:
        await sp.sql("delete from koe_prefs where owner_id=%s and name='spotify_voice_grant'", current)
        existing = drivers.get(current)
        if existing:
            await existing.socket.close(1008, 'Voice permission revoked')
        return {'enabled': False}
    sp.require_enabled()
    if not settings.spotify_voice_approved:
        raise sp.SpotifyError('spotify_voice_not_approved', 403)
    async with sp.owner_lock(current):
        await sp.connection(current, body.connection_id)
        selected = await sp.selected(current, body.connection_id)
        if selected['id'] != body.playlist_id:
            raise sp.SpotifyError('spotify_playlist_stale', 409)
        value = {'connection_id': body.connection_id, 'playlist_id': body.playlist_id}
        await sp.sql("insert into koe_prefs (owner_id,name,value,updated) values (%s,'spotify_voice_grant',%s,%s) "
                     "on conflict (owner_id,name) do update set value=excluded.value,updated=excluded.updated",
                     current, json.dumps(value), auth._now().isoformat())
    return {'enabled': True}


@dataclass
class Driver:
    socket: WebSocket
    grant: dict
    session_hash: str
    pending: dict = field(default_factory=dict)
    results: OrderedDict = field(default_factory=OrderedDict)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    queued: dict = field(default_factory=dict)


drivers: dict[str, Driver] = {}
history: dict[tuple[str, str], OrderedDict] = {}
tickets: dict[str, dict] = {}


@router.post('/api/music/voice-ticket')
async def ticket(request: Request, current: str = Depends(sp.owner)):
    permission = await grant(current)
    now = time.monotonic()
    for key in list(tickets):
        if tickets[key]['expires'] < now:
            del tickets[key]
    if sum(row['owner'] == current for row in tickets.values()) >= 8:
        raise sp.SpotifyError('spotify_voice_limit')
    value = secrets.token_urlsafe(32)
    tickets[auth._hash(value)] = {'owner': current, 'grant': permission,
        'session_hash': auth._hash(request.cookies[auth.SESSION_COOKIE]), 'expires': now + 30}
    return {'ticket': value}


async def session_valid(session_hash):
    rows = await auth.sql("select u.id from koe_sessions s join koe_users u on u.id=s.user_id "
        "where s.token_hash=%s and s.revoked is null and s.expires>%s and u.email=%s",
        session_hash, auth._now().isoformat(), settings.koe_admin_email.lower())
    return bool(rows and rows[0]['id'] == settings.koe_owner_id)


class Release(BaseModel):
    model_config = ConfigDict(extra='forbid', strict=True)
    id: str = Field(pattern=r'^[a-f0-9]{64}$')


@router.post('/api/music/voice-release')
async def release(body: Release, current: str = Depends(sp.owner)):
    permission = await grant(current)
    driver = drivers.get(current)
    if not driver or driver.grant != permission:
        raise sp.SpotifyError('spotify_player_window_required')
    # Claim once before any await: a failed/lost response must never play twice.
    expiry = driver.queued.pop(body.id, 0)
    if expiry < time.monotonic():
        raise sp.SpotifyError('spotify_voice_handoff_expired')
    future = asyncio.get_running_loop().create_future()
    driver.pending[body.id] = future
    try:
        await driver.socket.send_json({'type': 'release', 'id': body.id, **permission})
        # Playback must register/transfer and then observe asynchronous SDK state.
        # Leave room inside MusicRoute's 30s and the browser's 35s deadlines.
        result = await asyncio.wait_for(asyncio.shield(future), 25)
        return result
    except (TimeoutError, RuntimeError):
        return {'state': 'outcome_unknown'}
    finally:
        driver.pending.pop(body.id, None)


@router.websocket('/ws/music-control')
async def player(socket: WebSocket):
    current, driver = None, None
    try:
        if socket.headers.get('origin') != auth.site(socket):
            await socket.close(1008)
            return
        await socket.accept()
        raw = await asyncio.wait_for(socket.receive_text(), 5)
        if len(raw) > 1024:
            return
        first = json.loads(raw)
        value = first.get('ticket') if isinstance(first, dict) else None
        record = tickets.pop(auth._hash(value), None) if isinstance(value, str) else None
        if not record or record['expires'] < time.monotonic() or not await session_valid(record['session_hash']):
            await socket.close(1008, 'Music sign-in ticket expired')
            return
        current = record['owner']
        async with sp.owner_lock(current):
            permission = await grant(current)
            if record['grant'] != permission or current in drivers:
                await socket.close(1008, 'Permission changed or another music window is registered')
                return
            driver = Driver(socket, permission, record['session_hash'])
            drivers[current] = driver
        await socket.send_json({'type': 'ready', **permission})
        while True:
            raw = await asyncio.wait_for(socket.receive_text(), 35)
            if len(raw) > 2048:
                break
            message = json.loads(raw)
            if not isinstance(message, dict):
                continue
            if not await session_valid(record['session_hash']) or await grant(current) != driver.grant:
                await socket.close(1008, 'Music permission or session changed')
                break
            if message.get('type') == 'ping':
                await socket.send_json({'type': 'pong'})
                continue
            key = message.get('id')
            entry = driver.pending.get(key) if isinstance(key, str) else None
            if not entry or entry.done():
                continue
            state = message.get('state')
            if state in ('applied', 'queued', 'deferred', 'failed', 'outcome_unknown'):
                # No arbitrary browser text, playlist data or tokens reach the model.
                entry.set_result({'state': state})
    except (WebSocketDisconnect, TimeoutError, sp.SpotifyError, ValueError, RuntimeError):
        pass
    finally:
        if driver:
            if drivers.get(current) is driver:
                del drivers[current]
            for future in driver.pending.values():
                if not future.done():
                    future.set_result({'state': 'outcome_unknown'})
        with contextlib.suppress(RuntimeError):
            await socket.close(1008)


async def control(args, *, request_id, session_id, caller_session=None):
    """Only the approved live-voice adapter calls this, never general/text tools."""
    try:
        owner = identity.OWNER.get()
        if owner != settings.koe_owner_id:
            raise sp.SpotifyError('spotify_owner_required', 403)
        command = Command.model_validate(args or {})
        if (command.action == 'set_volume') != (command.volume_percent is not None):
            raise ValueError('Specify volume_percent only for set_volume.')
        if command.action == 'play_match':
            if not (command.artist and command.artist.strip() or command.title and command.title.strip()):
                raise ValueError('Supply an artist or title.')
        elif command.artist is not None or command.title is not None:
            raise ValueError('Artist/title are only for play_match.')
        permission = await grant(owner)
        if not caller_session or not await session_valid(caller_session):
            raise sp.SpotifyError('spotify_sign_in_required', 401, 'Spotify voice control requires a current signed-in owner session.')
        driver = drivers.get(owner)
        if not driver or driver.grant != permission:
            raise sp.SpotifyError('spotify_player_window_required', message='Open the allowed playlist in Koe Music first.')
        if not await session_valid(driver.session_hash):
            raise sp.SpotifyError('spotify_sign_in_required', 401)
        key = hashlib.sha256(f'{session_id}:{request_id}'.encode()).hexdigest()
        async with driver.lock:
            if (owner, session_id) not in history and len(history) >= 128:
                raise sp.SpotifyError('spotify_voice_limit')
            records = history.setdefault((owner, session_id), OrderedDict())
            if key in records:
                before, result = records[key]
                if before != command.model_dump():
                    raise ValueError('The same command ID cannot change its action.')
                return result
            if len(records) >= 64:
                raise sp.SpotifyError('spotify_voice_limit', message='Start a new voice call before issuing more music commands.')
            selection = {}
            if command.action == 'play_match':
                selected = await music_selection.resolve(owner, permission['connection_id'], artist=command.artist, title=command.title)
                if (await grant(owner) != permission or drivers.get(owner) is not driver
                        or not await session_valid(caller_session)):
                    raise sp.SpotifyError('spotify_voice_permission_required', 403)
                if selected['state'] != 'matched':
                    result = {'action': command.action, 'state': selected['state']}
                    records[key] = (command.model_dump(), result)
                    await driver.socket.send_json({'type': 'suggestion', 'query': ' '.join(filter(None, [command.title, command.artist])),
                                                   'state': selected['state'], **permission})
                    return result
                selection = {'position': selected['position'], 'snapshot_id': selected['snapshot_id']}
            future = asyncio.get_running_loop().create_future()
            driver.pending[key] = future
            try:
                # User query text and playlist metadata stay out of the model's reply.
                await driver.socket.send_json({'type': 'command', 'id': key, **permission, **command.model_dump(), **selection})
                reply = await asyncio.wait_for(asyncio.shield(future), 8)
                result = {'action': command.action, **reply}
                if reply['state'] == 'queued':
                    driver.queued[key] = time.monotonic() + 30
                    result['_handoff_id'] = key
                if reply['state'] in ('failed', 'outcome_unknown'):
                    result = {'error': {'code': 'music_' + reply['state'],
                              'message': 'Music control was not confirmed. Check the music window before retrying.'}}
            except (TimeoutError, RuntimeError):
                result = {'error': {'code': 'music_outcome_unknown', 'message': 'Music acknowledgement was lost. Do not repeat automatically.'}}
            finally:
                driver.pending.pop(key, None)
            records[key] = (command.model_dump(), result)
            return result
    except (sp.SpotifyError, ValidationError, ValueError) as error:
        return {'error': {'code': error.code if isinstance(error, sp.SpotifyError) else 'music_invalid_command',
                          'message': error.message if isinstance(error, sp.SpotifyError) else 'Use a supported transport action and volume from 0 to 100.'}}


def end_session(session_id):
    history.pop((identity.owner_id(), session_id), None)
