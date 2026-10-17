"""Real owner auth/storage/socket bridge with a fake player; no Spotify account writes."""
import asyncio
import json

import httpx
import pytest
import respx
from starlette.websockets import WebSocketDisconnect

from koe import agent, auth, db, identity, music_voice as mv, spotify_service as sp
from koe.config import settings
from test_spotify_auth import client, seed_connection, SITE, SESSION  # noqa: F401
from test_music_api import PLAYLIST, playlist


@pytest.fixture
def allowed(client, monkeypatch):
    monkeypatch.setattr(settings, 'spotify_voice_approved', True)
    client.app.include_router(mv.router)
    seed_connection()
    async def setup():
        await sp.set_playlist(settings.koe_owner_id, PLAYLIST)
        await db.sql("insert into koe_prefs (owner_id,name,value,updated) values (%s,'spotify_voice_grant',%s,'now')",
                     settings.koe_owner_id, json.dumps({'connection_id': 'generation-1', 'playlist_id': PLAYLIST}))
    asyncio.run(setup())
    return client


async def issue(action='pause', request_id='call-1', session_id='voice-session', **args):
    token = identity.OWNER.set(settings.koe_owner_id)
    try:
        return await mv.control({'action': action, **args}, request_id=request_id, session_id=session_id, caller_session=auth._hash(SESSION))
    finally:
        identity.OWNER.reset(token)


def open_player(client):
    response = client.post('/api/music/voice-ticket', json={})
    assert response.status_code == 200, response.text
    return response.json()['ticket']


def test_voice_is_separate_from_general_tools_and_requires_deployment_approval(allowed, monkeypatch):
    assert 'music_control' not in agent.TOOLS
    assert 'music_control' not in {item['name'] for item in agent.declarations()}
    monkeypatch.setattr(settings, 'spotify_voice_approved', False)
    response = allowed.get('/api/music/voice-permission')
    assert response.json() == {'available': False, 'enabled': False, 'grant': None}
    assert allowed.post('/api/music/voice-ticket', json={}).status_code == 403


def test_permission_explicitly_checks_selected_private_owned_playlist(allowed):
    body = {'connection_id': 'generation-1', 'playlist_id': PLAYLIST, 'enabled': True}
    with respx.mock:
        respx.get(sp.API_URL + '/playlists/' + PLAYLIST).mock(return_value=httpx.Response(200, json=playlist()))
        assert allowed.put('/api/music/voice-permission', json=body).status_code == 200
        respx.get(sp.API_URL + '/playlists/' + PLAYLIST).mock(return_value=httpx.Response(200, json=playlist(public=True)))
        assert allowed.put('/api/music/voice-permission', json=body).status_code == 400
    assert allowed.put('/api/music/voice-permission', json={**body, 'enabled': False}).status_code == 200
    assert allowed.get('/api/music/voice-permission').json()['enabled'] is False


def test_permission_cannot_be_bypassed_by_bearer_or_origin(allowed, monkeypatch):
    assert allowed.post('/api/music/voice-ticket', json={}, headers={'origin': 'https://evil.test'}).status_code == 403
    allowed.cookies.clear()
    monkeypatch.setattr(settings, 'koe_access_token', 'development')
    assert allowed.post('/api/music/voice-ticket', json={}, headers={'authorization': 'Bearer development'}).status_code == 401


def test_ticket_single_use_and_same_origin_player(allowed):
    with allowed:
        ticket = open_player(allowed)
        with pytest.raises(WebSocketDisconnect):
            with allowed.websocket_connect('/ws/music-control', headers={'origin': 'https://evil.test'}):
                pass
        with allowed.websocket_connect('/ws/music-control', headers={'origin': SITE}) as socket:
            socket.send_json({'ticket': ticket})
            assert socket.receive_json()['type'] == 'ready'
            socket.send_json({'type': 'ping'})
            assert socket.receive_json() == {'type': 'pong'}
        with pytest.raises(WebSocketDisconnect):
            with allowed.websocket_connect('/ws/music-control', headers={'origin': SITE}) as socket:
                socket.send_json({'ticket': ticket})
                socket.receive_json()


def test_player_ack_is_sanitized_and_duplicate_command_is_not_sent_twice(allowed):
    with allowed:
        ticket = open_player(allowed)
        with allowed.websocket_connect('/ws/music-control', headers={'origin': SITE}) as socket:
            socket.send_json({'ticket': ticket}); socket.receive_json()
            future = allowed.portal.start_task_soon(issue)
            command = socket.receive_json()
            assert command['action'] == 'pause'
            socket.send_json({'id': command['id'], 'state': 'applied', 'playlist': 'secret metadata', 'token': 'secret'})
            assert future.result(3) == {'action': 'pause', 'state': 'applied'}
            assert allowed.portal.call(issue) == {'action': 'pause', 'state': 'applied'}
            assert mv.drivers[settings.koe_owner_id].pending == {}


def test_play_is_queued_until_one_time_audio_release(allowed):
    with allowed:
        ticket = open_player(allowed)
        with allowed.websocket_connect('/ws/music-control', headers={'origin': SITE}) as socket:
            socket.send_json({'ticket': ticket}); socket.receive_json()
            future = allowed.portal.start_task_soon(issue, 'play')
            command = socket.receive_json()
            socket.send_json({'id': command['id'], 'state': 'queued'})
            result = future.result(3)
            assert result['state'] == 'queued'
            release = allowed.portal.start_task_soon(mv.release, mv.Release(id=result['_handoff_id']), settings.koe_owner_id)
            assert socket.receive_json()['type'] == 'release'
            socket.send_json({'id': command['id'], 'state': 'applied'})
            assert release.result(3) == {'state': 'applied'}
            assert allowed.post('/api/music/voice-release', json={'id': command['id']}).status_code == 409


def test_lost_ack_is_unknown_even_after_player_reconnect(allowed):
    with allowed:
        ticket = open_player(allowed)
        with allowed.websocket_connect('/ws/music-control', headers={'origin': SITE}) as socket:
            socket.send_json({'ticket': ticket}); socket.receive_json()
            future = allowed.portal.start_task_soon(issue, 'volume_up')
            socket.receive_json()
        first = future.result(3)
        assert first['error']['code'] == 'music_outcome_unknown'
        ticket = open_player(allowed)
        with allowed.websocket_connect('/ws/music-control', headers={'origin': SITE}) as socket:
            socket.send_json({'ticket': ticket}); socket.receive_json()
            assert allowed.portal.call(issue, 'volume_up') == first
            assert mv.drivers[settings.koe_owner_id].pending == {}


@pytest.mark.parametrize('args', [
    {'action': 'set_volume', 'volume_percent': 101}, {'action': 'set_volume', 'volume_percent': True},
    {'action': 'set_volume'}, {'action': 'play', 'volume_percent': 40},
    {'action': 'search'}, {'action': 'play', 'playlist_id': 'unapproved'},
])
def test_invalid_or_expanded_commands_never_reach_player(allowed, args):
    async def scenario():
        token = identity.OWNER.set(settings.koe_owner_id)
        try:
            result = await mv.control(args, request_id='invalid', session_id='voice')
            assert result['error']['code'] == 'music_invalid_command'
        finally:
            identity.OWNER.reset(token)
    asyncio.run(scenario())


def test_revoked_or_expired_session_cannot_redeem_ticket(allowed):
    with allowed:
        ticket = open_player(allowed)
        allowed.portal.call(db.sql, "update koe_sessions set revoked='now' where token_hash=%s", auth._hash(SESSION))
        with pytest.raises(WebSocketDisconnect):
            with allowed.websocket_connect('/ws/music-control', headers={'origin': SITE}) as socket:
                socket.send_json({'ticket': ticket}); socket.receive_json()


def test_second_window_and_stale_playlist_are_rejected(allowed):
    with allowed:
        first, second = open_player(allowed), open_player(allowed)
        with allowed.websocket_connect('/ws/music-control', headers={'origin': SITE}) as socket:
            socket.send_json({'ticket': first}); socket.receive_json()
            with pytest.raises(WebSocketDisconnect):
                with allowed.websocket_connect('/ws/music-control', headers={'origin': SITE}) as other:
                    other.send_json({'ticket': second}); other.receive_json()
            allowed.portal.call(sp.set_playlist, settings.koe_owner_id, 'q' * 22)
            socket.send_json({'type': 'ping'})
            with pytest.raises(WebSocketDisconnect):
                socket.receive_json()


def test_active_caller_cookie_is_required_even_when_owner_identity_is_known(allowed):
    async def scenario():
        token = identity.OWNER.set(settings.koe_owner_id)
        try:
            result = await mv.control({'action': 'pause'}, request_id='bearer-only', session_id='web', caller_session=None)
            assert result['error']['code'] == 'spotify_sign_in_required'
        finally:
            identity.OWNER.reset(token)
    asyncio.run(scenario())


def test_voice_ticket_carries_one_time_cookie_proof_without_exposing_cookie(allowed):
    allowed.app.include_router(auth.router)
    with allowed:
        reply = allowed.post('/api/ws-ticket')
        assert reply.status_code == 200
        assert SESSION not in reply.text
        ticket = reply.json()['ticket']
        assert auth.consume_ticket_session(ticket) == auth._hash(SESSION)
        assert auth.consume_ticket_session(ticket) is None
        assert auth.ws_owner(ticket) == settings.koe_owner_id
        assert auth.ws_owner(ticket) is None


def test_artist_and_title_match_only_playable_playlist_tracks():
    from koe.music_selection import choose
    def song(n, title, artist, playable=True):
        return (n, {'id': str(n)*22, 'uri': 'spotify:track:' + str(n)*22, 'type': 'track',
                    'name': title, 'artists': [{'name': artist}], 'is_playable': playable})
    tracks = [song(0, 'Tik Tok', 'Ke$ha'), song(1, 'Praying', 'Kesha'), song(2, 'Tik Tok', 'Another Artist')]
    assert choose(tracks, artist='Kesha')['position'] in (0, 1)
    assert choose(tracks, artist='kesha', title='tik tok') == {'state': 'matched', 'position': 0}
    assert choose(tracks, title='Tik Tok')['state'] == 'ambiguous'
    assert choose(tracks, title='Missing')['state'] == 'not_found'
    assert choose([song(0, 'Praying', 'Kesha', False)], artist='Kesha')['state'] == 'unavailable'
