"""Manual Spotify routes: private destination, durable replay, no remote control."""
import asyncio
import json

import httpx
import respx
import pytest

from koe import connections, db, spotify_service as sp
from koe import spotify_store as journal
from koe.config import settings
from test_spotify_auth import client, seed_connection  # noqa: F401 (shared fixture)

PLAYLIST = "p" * 22
TRACK = "t" * 22
URI = "spotify:track:" + TRACK


def playlist(**changes):
    return {"id": PLAYLIST, "name": "Chill", "owner": {"id": "spotify-owner"}, "public": False,
            "collaborative": False, "snapshot_id": "snapshot-1", "items": {"total": 3}, "images": [], **changes}


def select(client):
    response = client.put("/api/music/playlist", json={"connection_id": "generation-1", "playlist_id": PLAYLIST})
    assert response.status_code == 200, response.text


def test_selected_playlist_requires_owned_private_noncollaborative(client):
    seed_connection()
    for changes in ({"public": True}, {"collaborative": True}, {"owner": {"id": "someone-else"}}):
        with respx.mock:
            respx.get(sp.API_URL + "/playlists/" + PLAYLIST).mock(return_value=httpx.Response(200, json=playlist(**changes)))
            result = client.put("/api/music/playlist", json={"connection_id": "generation-1", "playlist_id": PLAYLIST})
            assert result.status_code == 400, result.text


def test_add_is_durably_replayed_once_and_changed_body_is_rejected(client):
    seed_connection()
    with respx.mock:
        respx.get(sp.API_URL + "/playlists/" + PLAYLIST).mock(return_value=httpx.Response(200, json=playlist()))
        respx.get(sp.API_URL + "/tracks/" + TRACK).mock(return_value=httpx.Response(200, json={
            "id": TRACK, "uri": URI, "type": "track", "is_playable": True}))
        add = respx.post(sp.API_URL + "/playlists/" + PLAYLIST + "/items").mock(return_value=httpx.Response(201, json={"snapshot_id": "snapshot-2"}))
        select(client)
        body = {"connection_id": "generation-1", "request_id": "add-once", "snapshot_id": "snapshot-1", "uri": URI}
        first = client.post("/api/music/playlist/items", json=body)
        second = client.post("/api/music/playlist/items", json=body)
        assert first.status_code == 200, first.text
        assert first.json() == second.json() and add.call_count == 1
        assert json.loads(add.calls.last.request.content) == {"uris": [URI]}
        changed = client.post("/api/music/playlist/items", json={**body, "uri": "spotify:track:" + "u" * 22})
        assert changed.json()["error"]["code"] == "spotify_request_conflict"
    journal = asyncio.run(db.sql("select * from koe_music_mutations"))
    assert journal[0]["state"] == "confirmed" and TRACK not in journal[0]["evidence_enc"]
    evidence = connections.decrypt(journal[0]["evidence_enc"])
    assert evidence["intent"]["uri"] == URI and evidence["destination"] == {"playlist_id": PLAYLIST}


def test_timeout_write_and_restart_never_resend(client):
    seed_connection()
    with respx.mock:
        respx.get(sp.API_URL + "/playlists/" + PLAYLIST).mock(return_value=httpx.Response(200, json=playlist()))
        respx.get(sp.API_URL + "/tracks/" + TRACK).mock(return_value=httpx.Response(200, json={"id": TRACK, "uri": URI, "type": "track", "is_playable": True}))
        add = respx.post(sp.API_URL + "/playlists/" + PLAYLIST + "/items").mock(side_effect=httpx.ReadTimeout("private error"))
        select(client)
        body = {"connection_id": "generation-1", "request_id": "uncertain", "snapshot_id": "snapshot-1", "uri": URI}
        response = client.post("/api/music/playlist/items", json=body)
        assert response.status_code == 202 and response.json()["state"] == "outcome_unknown", response.text
        assert client.post("/api/music/playlist/items", json=body).json()["state"] == "outcome_unknown"
        assert add.call_count == 1
    assert client.get("/api/music/mutations/uncertain?connection_id=generation-1").json()["state"] == "outcome_unknown"


def test_current_items_wrapper_unavailable_and_legacy_track_are_normalized(client):
    seed_connection()
    with respx.mock:
        respx.get(sp.API_URL + "/playlists/" + PLAYLIST).mock(return_value=httpx.Response(200, json=playlist()))
        respx.get(sp.API_URL + "/playlists/" + PLAYLIST + "/items").mock(return_value=httpx.Response(200, json={
            "items": [{"item": None}, {"item": {"type": "episode", "name": "Podcast"}},
                      {"track": {"id": TRACK, "uri": URI, "type": "track", "name": "Song", "is_playable": True}}],
            "offset": 0, "limit": 50, "total": 3}))
        select(client)
        response = client.get("/api/music/playlist/items")
    assert response.status_code == 200, response.text
    tracks = [item["track"] for item in response.json()["items"]]
    assert [item["playable"] for item in tracks] == [False, False, True]


def test_no_unknown_device_or_arbitrary_playlist_can_be_controlled(client):
    seed_connection()
    body = {"connection_id": "generation-1", "request_id": "play", "device_id": "remote", "operation": "play"}
    with respx.mock:
        assert client.post("/api/music/playback", json=body).json()["error"]["code"] == "spotify_device_unavailable"
        assert client.post("/api/music/playback", json={**body, "context_uri": "spotify:playlist:other"}).status_code == 400


def test_stale_playlist_snapshot_and_unknown_destination_fail_before_write(client):
    seed_connection()
    with respx.mock:
        respx.get(sp.API_URL + "/playlists/" + PLAYLIST).mock(return_value=httpx.Response(200, json=playlist()))
        write = respx.post(sp.API_URL + "/playlists/" + PLAYLIST + "/items").mock(return_value=httpx.Response(201, json={"snapshot_id": "s2"}))
        select(client)
        body = {"connection_id": "generation-1", "request_id": "stale", "snapshot_id": "old", "uri": URI}
        assert client.post("/api/music/playlist/items", json=body).json()["error"]["code"] == "spotify_playlist_stale"
        assert client.post("/api/music/playlist/items", json={**body, "playlist_id": "other"}).status_code == 400
        assert write.call_count == 0


def test_explicit_all_occurrence_removal_uses_current_items_schema(client):
    seed_connection()
    with respx.mock:
        respx.get(sp.API_URL + "/playlists/" + PLAYLIST).mock(return_value=httpx.Response(200, json=playlist()))
        write = respx.delete(sp.API_URL + "/playlists/" + PLAYLIST + "/items").mock(return_value=httpx.Response(200, json={"snapshot_id": "s2"}))
        select(client)
        body = {"connection_id": "generation-1", "request_id": "remove-all", "snapshot_id": "snapshot-1", "uri": URI}
        assert client.request("DELETE", "/api/music/playlist/items", json=body).status_code == 400
        result = client.request("DELETE", "/api/music/playlist/items", json={**body, "remove_all_occurrences": True})
        assert result.status_code == 200, result.text
    assert json.loads(write.calls.last.request.content) == {"items": [{"uri": URI}], "snapshot_id": "snapshot-1"}


def test_create_and_reorder_are_journaled_with_validated_private_destination(client):
    seed_connection()
    with respx.mock:
        create = respx.post(sp.API_URL + "/me/playlists").mock(return_value=httpx.Response(201, json=playlist()))
        body = {"connection_id": "generation-1", "request_id": "create", "name": "Chill"}
        assert client.post("/api/music/playlists", json=body).status_code == 200
        assert client.post("/api/music/playlists", json=body).status_code == 200
        assert create.call_count == 1
        assert json.loads(create.calls.last.request.content)["public"] is False
        respx.get(sp.API_URL + "/playlists/" + PLAYLIST).mock(return_value=httpx.Response(200, json=playlist()))
        reorder = respx.put(sp.API_URL + "/playlists/" + PLAYLIST + "/items").mock(return_value=httpx.Response(200, json={"snapshot_id": "s2"}))
        result = client.put("/api/music/playlist/items/order", json={"connection_id": "generation-1", "request_id": "move", "snapshot_id": "snapshot-1", "range_start": 0, "insert_before": 3})
        assert result.status_code == 200, result.text
    assert json.loads(reorder.calls.last.request.content) == {"range_start": 0, "range_length": 1, "insert_before": 3, "snapshot_id": "snapshot-1"}


def test_search_rate_limits_and_quota_errors_do_not_leak_provider_body(client):
    seed_connection()
    for status, payload, code in ((429, {"private": "secret-track"}, "spotify_rate_limited"),
                                  (429, {"error": {"reason": "QUOTA_EXCEEDED", "message": "secret-track"}}, "spotify_quota_exceeded")):
        with respx.mock:
            respx.get(sp.API_URL + "/search").mock(return_value=httpx.Response(status, json=payload, headers={"retry-after": "120"}))
            result = client.get("/api/music/search?q=typed-query")
        assert result.json()["error"]["code"] == code and "secret-track" not in result.text
        if code == "spotify_rate_limited":
            assert result.json()["error"]["retry_after_seconds"] == 120 and result.headers["retry-after"] == "120"


def test_journal_capacity_and_sent_crash_records_prevent_new_or_duplicate_sends(client, monkeypatch):
    seed_connection()
    monkeypatch.setattr(journal, "CAPACITY", 1)
    with respx.mock:
        create = respx.post(sp.API_URL + "/me/playlists").mock(side_effect=httpx.ReadTimeout("ambiguous"))
        body = {"connection_id": "generation-1", "request_id": "crashed", "name": "Chill"}
        assert client.post("/api/music/playlists", json=body).status_code == 202
        # Simulate a process crash after the durable sent claim and before recording a result.
        asyncio.run(db.sql("update koe_music_mutations set state='sent', result_enc=null"))
        assert client.post("/api/music/playlists", json=body).status_code == 202 and create.call_count == 1
        full = client.post("/api/music/playlists", json={**body, "request_id": "new"})
        assert full.json()["error"]["code"] == "spotify_journal_full"


def test_device_registration_waits_for_discovery_without_sending_playback(client):
    seed_connection()
    with respx.mock:
        discovery = respx.get(sp.API_URL + "/me/player/devices").mock(side_effect=[
            httpx.Response(200, json={"devices": []}),
            httpx.Response(200, json={"devices": [{"id": "browser", "name": "Koe Web Player", "type": "Computer", "is_restricted": False}]})])
        result = client.post("/api/music/device", json={"connection_id": "generation-1", "device_id": "browser"})
        assert result.status_code == 200, result.text
        assert discovery.call_count == 2
        assert all(call.request.method == "GET" for call in respx.calls)


def test_device_registration_does_not_accept_restricted_or_renamed_device(client):
    seed_connection()
    for change in ({"is_restricted": True}, {"name": "Web Player (Chrome)"}, {"type": "Smartphone"}):
        with respx.mock:
            discovery = respx.get(sp.API_URL + "/me/player/devices").mock(return_value=httpx.Response(200, json={"devices": [
                {"id": "browser", "name": "Koe Web Player", "type": "Computer", "is_restricted": False, **change}]}))
            result = client.post("/api/music/device", json={"connection_id": "generation-1", "device_id": "browser"})
            assert result.status_code == 409
            assert "No playback was requested" in result.json()["error"]["message"]
            assert discovery.call_count == 1


def test_absent_sdk_device_exhausts_only_bounded_reads(client):
    seed_connection()
    with respx.mock:
        discovery = respx.get(sp.API_URL + "/me/player/devices").mock(return_value=httpx.Response(200, json={"devices": []}))
        result = client.post("/api/music/device", json={"connection_id": "generation-1", "device_id": "browser"})
        assert result.status_code == 409
        assert 1 <= discovery.call_count <= 8  # either the attempt cap or four-second deadline may win
        assert "No playback was requested" in result.json()["error"]["message"]
        assert not sp.devices
        assert all(call.request.method == "GET" for call in respx.calls)


def test_registered_local_device_transfer_sends_play_false_and_state_is_targeted(client):
    seed_connection()
    with respx.mock:
        respx.get(sp.API_URL + "/me/player/devices").mock(return_value=httpx.Response(200, json={"devices": [
            {"id": "browser", "name": "Koe Web Player", "type": "Computer", "is_restricted": False},
            {"id": "remote", "name": "Phone", "type": "Smartphone", "is_restricted": False}]}))
        body = {"connection_id": "generation-1", "device_id": "browser"}
        assert client.post("/api/music/device", json={**body, "device_id": "remote"}).status_code == 409
        assert client.post("/api/music/device", json=body).status_code == 200
        transfer = respx.put(sp.API_URL + "/me/player").mock(return_value=httpx.Response(204))
        command = {**body, "request_id": "transfer", "operation": "transfer"}
        assert client.post("/api/music/playback", json=command).status_code == 200
        assert json.loads(transfer.calls.last.request.content) == {"device_ids": ["browser"], "play": False}
        respx.get(sp.API_URL + "/me/player").mock(return_value=httpx.Response(200, json={"device": {"id": "remote", "private": "other-room"}, "is_playing": True}))
        state = client.get("/api/music/playback?connection_id=generation-1&device_id=browser")
        assert state.json() == {"state": "unknown", "is_playing": None, "device_id": None}


def test_concurrent_identical_mutations_send_once(client):
    seed_connection()

    async def exercise():
        with respx.mock:
            create = respx.post(sp.API_URL + "/me/playlists").mock(return_value=httpx.Response(201, json=playlist()))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=client.app), base_url="https://koe.test",
                                         cookies={"koe_session": "owner-test-session"}, headers={"origin": "https://koe.test"}) as http:
                body = {"connection_id": "generation-1", "request_id": "same-intent", "name": "Chill"}
                results = await asyncio.gather(*(http.post("/api/music/playlists", json=body) for _ in range(4)))
                assert all(result.status_code == 200 for result in results)
                assert create.call_count == 1
    asyncio.run(exercise())


def test_result_storage_failure_after_send_is_unknown_and_never_replayed(client, monkeypatch):
    seed_connection()

    async def fail_finish(*_args, **_kwargs):
        raise RuntimeError("private-db-body")

    with respx.mock:
        create = respx.post(sp.API_URL + "/me/playlists").mock(return_value=httpx.Response(201, json=playlist()))
        monkeypatch.setattr(journal, "finish", fail_finish)
        body = {"connection_id": "generation-1", "request_id": "save-failed", "name": "Chill"}
        first = client.post("/api/music/playlists", json=body)
        replay = client.post("/api/music/playlists", json=body)
        assert first.status_code == 202 and replay.status_code == 202
        assert create.call_count == 1 and "private-db-body" not in first.text


def test_write_throttling_is_recorded_without_resending(client):
    seed_connection()
    with respx.mock:
        create = respx.post(sp.API_URL + "/me/playlists").mock(return_value=httpx.Response(429, json={}, headers={"retry-after": "30"}))
        body = {"connection_id": "generation-1", "request_id": "throttled", "name": "Chill"}
        first = client.post("/api/music/playlists", json=body)
        second = client.post("/api/music/playlists", json=body)
        assert first.status_code == second.status_code == 429
        assert create.call_count == 1


def test_reconnect_does_not_discard_unknown_operations_without_explicit_disconnect(client):
    seed_connection()
    with respx.mock:
        respx.post(sp.API_URL + "/me/playlists").mock(side_effect=httpx.ReadTimeout("unknown"))
        client.post("/api/music/playlists", json={"connection_id": "generation-1", "request_id": "unknown", "name": "Chill"})
        response = client.post("/auth/spotify/connect", json={})
        assert response.json()["error"]["code"] == "spotify_outcome_unknown"
    assert client.delete("/api/connections/spotify").status_code == 204
    assert asyncio.run(db.sql("select * from koe_music_mutations")) == []


def test_revocation_does_not_delete_unknown_journal_evidence(client):
    seed_connection()
    with respx.mock:
        respx.post(sp.API_URL + "/me/playlists").mock(side_effect=httpx.ReadTimeout("unknown"))
        client.post("/api/music/playlists", json={"connection_id": "generation-1", "request_id": "unknown", "name": "Chill"})
        respx.get(sp.API_URL + "/search").mock(return_value=httpx.Response(401, json={}))
        assert client.get("/api/music/search?q=typed").json()["error"]["code"] == "spotify_reconnect_required"
    assert len(asyncio.run(db.sql("select * from koe_music_mutations"))) == 1
    status = client.get("/api/music/status").json()
    assert status["connection_id"] == "generation-1" and status["reconnect_required"] is True
    result = client.get("/api/music/mutations/unknown?connection_id=generation-1")
    assert result.status_code == 202 and result.json()["state"] == "outcome_unknown"


@pytest.mark.parametrize("url", ["http://i.scdn.co/image/a", "https://i.scdn.co.evil.test/a", "https://user:secret@i.scdn.co/a", "https://[invalid", "https://i.scdn.co:invalid/a"])
def test_untrusted_artwork_urls_are_not_returned(url):
    assert sp.artwork({"images": [{"url": url}]}) is None

@pytest.mark.parametrize('response', [httpx.Response(204), httpx.Response(200, json={'is_playing': False, 'device': {'id': 'old'}})])
def test_audio_recovery_observes_stopped_without_playback_write(client, response):
    seed_connection()
    with respx.mock:
        respx.get(sp.API_URL + '/me/player').mock(return_value=response)
        result = client.post('/api/music/recover-audio', json={'connection_id': 'generation-1'})
        assert result.json() == {'state': 'stopped', 'connection_id': 'generation-1'}
        assert all(call.request.method == 'GET' for call in respx.calls)


def record_transfer(client, unknown=False):
    respx.get(sp.API_URL + '/me/player/devices').mock(return_value=httpx.Response(200, json={'devices': [
        {'id': 'old-browser', 'name': 'Koe Web Player', 'type': 'Computer', 'is_restricted': False}]}))
    body = {'connection_id': 'generation-1', 'device_id': 'old-browser'}
    assert client.post('/api/music/device', json=body).status_code == 200
    route = respx.put(sp.API_URL + '/me/player')
    if unknown:
        route.mock(side_effect=httpx.ReadTimeout('lost'))
    else:
        route.mock(return_value=httpx.Response(204))
    assert client.post('/api/music/playback', json={**body, 'request_id': 'old-transfer', 'operation': 'transfer'}).status_code == (202 if unknown else 200)


def test_audio_recovery_pauses_only_durably_recorded_koe_device_after_restart(client):
    seed_connection()
    with respx.mock:
        record_transfer(client)
        sp.devices.clear()  # backend process/device registration gone; durable evidence remains
        respx.get(sp.API_URL + '/me/player').mock(side_effect=[
            httpx.Response(200, json={'device': {'id': 'old-browser'}, 'is_playing': True}),
            httpx.Response(200, json={'device': {'id': 'old-browser'}, 'is_playing': False})])
        pause = respx.put(sp.API_URL + '/me/player/pause').mock(return_value=httpx.Response(204))
        result = client.post('/api/music/recover-audio', json={'connection_id': 'generation-1'})
        assert result.json()['state'] == 'stopped'
        assert pause.call_count == 1 and pause.calls[0].request.url.params['device_id'] == 'old-browser'


def test_audio_recovery_refuses_unrelated_device_and_unknown_sent_intent(client):
    seed_connection()
    with respx.mock:
        respx.get(sp.API_URL + '/me/player').mock(return_value=httpx.Response(200, json={'device': {'id': 'phone'}, 'is_playing': True}))
        result = client.post('/api/music/recover-audio', json={'connection_id': 'generation-1'})
        assert result.status_code == 409
        assert all(call.request.method == 'GET' for call in respx.calls)
        record_transfer(client, unknown=True)
        count = len(respx.calls)
        result = client.post('/api/music/recover-audio', json={'connection_id': 'generation-1'})
        assert result.json()['error']['code'] == 'spotify_outcome_unknown'
        assert len(respx.calls) == count  # never replay or hide an unresolved sent request


def test_artist_suggestions_are_bounded_and_sanitized(client):
    seed_connection()
    with respx.mock:
        search = respx.get(sp.API_URL + '/search').mock(return_value=httpx.Response(200, json={'artists': {'items': [
            {'id': 'a'*22, 'name': 'Kesha', 'images': [{'url': 'https://i.scdn.co/image/cover'}], 'private_field': 'hidden'}], 'total': 1}}))
        result = client.get('/api/music/search?kind=artist&q=Kes&limit=5')
        assert search.calls[0].request.url.params['type'] == 'artist'
        assert result.status_code == 200 and result.json()['items'][0]['name'] == 'Kesha'
        assert 'hidden' not in result.text
    assert client.get('/api/music/search?kind=artist&q=x&limit=100').status_code == 400


def test_unknown_shuffle_does_not_block_verified_audio_recovery(client):
    seed_connection()
    with respx.mock:
        record_transfer(client)
        asyncio.run(db.sql("update koe_music_mutations set operation='playback_shuffle',state='outcome_unknown'"))
        respx.get(sp.API_URL + '/me/player').mock(return_value=httpx.Response(204))
        result = client.post('/api/music/recover-audio', json={'connection_id': 'generation-1'})
        assert result.json()['state'] == 'stopped'
    assert asyncio.run(db.sql('select state from koe_music_mutations'))[0]['state'] == 'outcome_unknown'


@pytest.mark.parametrize('payload', [{}, {'is_playing': None}, {'is_playing': 'false'}])
def test_audio_recovery_does_not_treat_malformed_success_as_stopped(client, payload):
    seed_connection()
    with respx.mock:
        respx.get(sp.API_URL + '/me/player').mock(return_value=httpx.Response(200, json=payload))
        result = client.post('/api/music/recover-audio', json={'connection_id': 'generation-1'})
        assert result.status_code == 503
        assert result.json()['error']['code'] == 'spotify_unavailable'
