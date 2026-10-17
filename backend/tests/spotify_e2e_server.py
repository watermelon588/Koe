"""Local-only browser fixture: real music/auth routes + SQLite + simulated Spotify.

Run explicitly: python tests/spotify_e2e_server.py
Never imported by koe.main; never reads or changes hosted data or Spotify accounts.
"""
import argparse
import io
import json
import secrets
import sys
import tempfile
import time
import uuid
import wave
from types import SimpleNamespace
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import httpx
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import RedirectResponse, FileResponse, Response

from koe import auth, connections, db, music_api, spotify_auth, spotify_service as sp, music_voice, identity, voice_call
from koe.config import settings

PLAYLIST = "p" * 22
TRACKS = ["t" * 22, "u" * 22, "v" * 22, "w" * 22]


class Provider:
    def __init__(self):
        self.order = TRACKS[:3]
        self.name = "TEST — simulated Spotify (no sound)"
        self.snapshot = 1
        self.devices = {}
        self.device = None
        self.playing = False
        self.position = 0
        self.index = 0
        self.volume = .6
        self.shuffle = False
        self.repeat = "off"
        self.calls = []
        self.music_results = []
        self.unknown_next_write = False
        self.pause_unknown = False
        self.hidden_devices = False
        self.voice_connections = 0

    def track(self, identifier):
        return {"id": identifier, "uri": "spotify:track:" + identifier, "type": "track",
                "name": "Test track " + str(TRACKS.index(identifier) + 1), "is_playable": True,
                "artists": [{"name": "Simulated artist"}], "duration_ms": 180000,
                "album": {"name": "Test album — no sound", "images": []}}

    def playlist(self):
        return {"id": PLAYLIST, "name": self.name, "public": False,
                "collaborative": False, "owner": {"id": "test-spotify-owner"}, "images": [],
                "snapshot_id": str(self.snapshot), "items": {"total": len(self.order)}}

    def playback(self):
        return {"device": {"id": self.device}, "is_playing": self.playing}

    async def respond(self, request):
        host, path, method = request.url.host, request.url.path, request.method
        if host not in ("api.spotify.com", "accounts.spotify.com"):
            raise AssertionError("The E2E fixture blocks external providers")
        body = json.loads(request.content) if request.content and request.headers.get("content-type", "").startswith("application/json") else {}
        self.calls.append({"method": method, "path": path})
        if host == "accounts.spotify.com" and path == "/api/token":
            return httpx.Response(200, json={"access_token": "simulated-access", "refresh_token": "simulated-refresh",
                "expires_in": 3600, "token_type": "Bearer", "scope": " ".join(sp.SCOPES)})
        if path == "/v1/me":
            return httpx.Response(200, json={"id": "test-spotify-owner", "account_id": "test-immutable-owner"})
        if path == "/v1/me/playlists":
            if method == "POST":
                self.name = body["name"]
                self.order = []
                self.snapshot += 1
                return httpx.Response(201, json=self.playlist())
            return httpx.Response(200, json={"items": [self.playlist()], "total": 1})
        if path == "/v1/playlists/" + PLAYLIST:
            return httpx.Response(200, json=self.playlist())
        if path == "/v1/playlists/" + PLAYLIST + "/items":
            if method == "GET":
                offset = int(request.url.params.get("offset", 0))
                limit = int(request.url.params.get("limit", 50))
                return httpx.Response(200, json={"items": [{"item": self.track(i)} for i in self.order[offset:offset + limit]], "total": len(self.order)})
            if method == "POST":
                self.order.extend(uri.rsplit(":", 1)[-1] for uri in body["uris"])
            elif method == "DELETE":
                remove = {item["uri"].rsplit(":", 1)[-1] for item in body["items"]}
                self.order = [i for i in self.order if i not in remove]
            elif method == "PUT":
                start, target = body["range_start"], body["insert_before"]
                value = self.order.pop(start)
                self.order.insert(target - 1 if target > start else target, value)
            self.snapshot += 1
            if self.unknown_next_write:
                self.unknown_next_write = False
                raise httpx.ReadTimeout("Simulated accepted write with lost response", request=request)
            return httpx.Response(200, json={"snapshot_id": str(self.snapshot)})
        if path == "/v1/search":
            if request.url.params.get('type') == 'artist':
                return httpx.Response(200, json={'artists': {'items': [{'id': 'a'*22, 'name': 'Simulated artist', 'images': []}], 'total': 1}})
            return httpx.Response(200, json={"tracks": {"items": [self.track(TRACKS[3])], "total": 1}})
        if path.startswith("/v1/tracks/") and path.rsplit("/", 1)[-1] in TRACKS:
            return httpx.Response(200, json=self.track(path.rsplit("/", 1)[-1]))
        if path == "/v1/me/player/devices":
            return httpx.Response(200, json={"devices": [] if self.hidden_devices else list(self.devices.values())})
        if path == "/v1/me/player":
            if method == "GET":
                return httpx.Response(200, json=self.playback()) if self.device else httpx.Response(204)
            self.device = body["device_ids"][0]
            # play:false preserves state, including a remotely-playing state.
            return httpx.Response(204)
        if path == "/v1/me/player/play":
            self.device = request.url.params["device_id"]
            self.index = body.get("offset", {}).get("position", 0)
            self.playing = True
            return httpx.Response(204)
        if path == "/v1/me/player/pause":
            if not self.pause_unknown:
                self.playing = False
            return httpx.Response(204)
        if path == "/v1/me/player/shuffle":
            self.shuffle = request.url.params["state"] == "true"
            return httpx.Response(204)
        if path == "/v1/me/player/repeat":
            self.repeat = request.url.params["state"]
            return httpx.Response(204)
        return httpx.Response(404, json={"error": {"reason": "TEST_UNSUPPORTED_ENDPOINT"}})


def create_app(origin="http://127.0.0.1:5174"):
    # Settings are overwritten before any DB access. No live storage is used.
    root = Path(__file__).resolve().parents[1] / "data"
    root.mkdir(exist_ok=True)
    data = Path(tempfile.mkdtemp(prefix="spotify-e2e-", dir=root))
    for key, value in {"database_url": "", "koe_owner_id": "spotify-e2e-owner", "koe_admin_email": "e2e@koe.invalid",
        "koe_access_token": "", "koe_secret_key": secrets.token_urlsafe(48), "koe_local_url": origin,
        "koe_public_url": origin, "google_web_client_id": "simulated-google-client",
        "google_web_client_secret": "simulated-google-secret", "spotify_client_id": "simulated-spotify-client",
        "spotify_client_secret": "simulated-spotify-secret", "spotify_redirect_uri": origin + "/auth/spotify/callback",
        "spotify_enabled": True, "spotify_voice_approved": True}.items():
        setattr(settings, key, value)
    db.DB, db.DATA = data / "app.db", data
    auth.SESSION_COOKIE = "koe_spotify_e2e_session"  # cannot overwrite the real local Koe session
    connections._prefs = {}
    sp.devices = {}
    provider = Provider()
    original_client = httpx.AsyncClient

    def isolated_http(*args, **kwargs):
        kwargs["transport"] = httpx.MockTransport(provider.respond)
        return original_client(*args, **kwargs)

    httpx.AsyncClient = isolated_http
    app = FastAPI(title="Koe Spotify E2E — simulated data, no sound")
    app.state.provider = provider
    session = secrets.token_urlsafe(32)
    now = auth._now().isoformat()
    db._run("insert into koe_users (id,google_sub,email,name,created) values (%s,%s,%s,%s,%s)",
            (settings.koe_owner_id, "e2e-sub", settings.koe_admin_email, "E2E test owner", now))
    db._run("insert into koe_sessions (token_hash,user_id,created,expires) values (%s,%s,%s,%s)",
            (auth._hash(session), settings.koe_owner_id, now, "2099-01-01"))

    @app.middleware("http")
    async def local_only(request: Request, call_next):
        if request.client and request.client.host not in ("127.0.0.1", "::1", "testclient"):
            return sp.JSONResponse({"error": "Local test fixture only"}, status_code=403)
        response = await call_next(request)
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Koe-E2E"] = "simulated-spotify-no-sound"
        return response

    @app.get("/__e2e/login")
    @app.get("/auth/google/start")
    async def login():
        response = RedirectResponse(origin + "/#music", 303)
        response.set_cookie(auth.SESSION_COOKIE, session, httponly=True, samesite="lax")
        return response

    @app.get("/__e2e/player.js")
    async def player_script():
        return FileResponse(Path(__file__).with_name("spotify_e2e_sdk.js"), media_type="application/javascript")

    @app.get("/__e2e/demo")
    async def demo():
        # Explicitly labelled local preview; the separate OAuth browser test still uses the real flow.
        row = await sp.io(connections.load, settings.koe_owner_id, "spotify")
        if not row:
            token = {"access_token": "simulated-access", "refresh_token": "simulated-refresh", "expires_at": time.time() + 3600,
                     "authorized_at": time.time(), "connection_id": uuid.uuid4().hex,
                     "spotify_account_id": "test-immutable-owner", "spotify_user_id": "test-spotify-owner"}
            await sp.io(connections.save, settings.koe_owner_id, "spotify", "Spotify", sp.SCOPES, token)
        return await login()

    @app.get("/__e2e/state")
    async def test_state():
        index = min(provider.index, max(0, len(provider.order) - 1))
        return {"mode": "simulated-spotify-no-sound", "order": provider.order, "snapshot": str(provider.snapshot),
                "playing": provider.playing, "device_id": provider.device, "position": provider.position,
                "index": index, "volume": provider.volume, "pause_unknown": provider.pause_unknown,
                "track": provider.track(provider.order[index]) if provider.order else None,
                "calls": provider.calls, "voice_connections": provider.voice_connections,
                "music_results": provider.music_results}

    @app.get("/api/app/messages")
    async def messages():
        return {"messages": [{"id": 1, "ts": "2026-10-15T00:00:00Z", "role": "koe",
            "text": "TEST — simulated stored reply (silent)", "voice": "e2e-silent.wav", "action_id": None, "action_status": None}]}

    @app.get("/api/app/voice/e2e-silent.wav")
    async def silent_reply():
        output = io.BytesIO()
        with wave.open(output, "wb") as sound:
            sound.setnchannels(1); sound.setsampwidth(2); sound.setframerate(16000)
            sound.writeframes(bytes(16000 * 2 * 10))
        return Response(output.getvalue(), media_type="audio/wav")

    @app.post("/__e2e/control")
    async def control(request: Request):
        body = await request.json()
        if body.get("reset") is True:
            provider.__init__()
        for key in ("unknown_next_write", "pause_unknown", "hidden_devices"):
            if key in body:
                setattr(provider, key, body[key] is True)
        return {"ok": True}

    @app.post("/__e2e/sdk")
    async def sdk(request: Request):
        body = await request.json()
        operation, identifier = body["operation"], body["device_id"]
        if operation == "connect":
            provider.devices[identifier] = {"id": identifier, "name": "Koe Web Player", "type": "Computer", "is_restricted": False}
        elif operation == "disconnect":
            provider.devices.pop(identifier, None)
            if provider.device == identifier:
                provider.playing = False
        elif operation == "pause" and not provider.pause_unknown:
            provider.playing = False
        elif operation == "resume":
            provider.device, provider.playing = identifier, True
        elif operation == "seek":
            provider.position = body["value"]
        elif operation == "volume":
            provider.volume = body["value"]
        elif operation == "next":
            provider.index = min(provider.index + 1, len(provider.order) - 1)
        elif operation == "previous":
            provider.index = max(0, provider.index - 1)
        return {"ok": True}

    @app.websocket("/ws/events")
    async def events(socket: WebSocket):
        await socket.accept()
        try:
            await socket.receive_json()
            await socket.send_json({"type": "snapshot", "panels": {}, "activity": [], "pending": [], "latencies": [], "storage": "E2E simulation"})
            while True:
                await socket.receive()
        except (WebSocketDisconnect, RuntimeError):
            pass

    @app.websocket("/ws/call")
    async def voice(socket: WebSocket):
        await socket.accept()
        provider.voice_connections += 1
        if provider.playing:
            await socket.close(1008, "E2E: music was not paused before voice")
            return
        context = voice_call.CallState()
        owner_token = identity.OWNER.set(settings.koe_owner_id)
        class Session:
            async def send_tool_response(self, function_responses):
                provider.music_results.extend(item.response for item in function_responses)
        try:
            while True:
                message = await socket.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message.get('text'):
                    data = json.loads(message['text'])
                    if data.get('type') == 'auth':
                        context.music_session = auth.consume_ticket_session(data.get('token'))
                        if auth.ws_owner(data.get('token')) != settings.koe_owner_id:
                            await socket.close(1008, 'Invalid fixture owner ticket')
                            break
                    if data.get('type') == 'text' and data.get('text', '').startswith('E2E_MUSIC '):
                        # Only this isolated fixture simulates Gemini's function selection.
                        args = json.loads(data['text'].removeprefix('E2E_MUSIC '))
                        call = SimpleNamespace(name='music_control', args=args, id=uuid.uuid4().hex)
                        await voice_call._run_tools(socket, Session(), [call], context)
                        await socket.send_json({'type': 'transcript', 'role': 'koe', 'text': 'Simulated tool response. Music handoff will follow this reply.'})
                        await socket.send_bytes(bytes(4800))  # 100ms of silent 24kHz PCM through the real playback queue
                        await socket.send_json({'type': 'turn_complete'})
        except (WebSocketDisconnect, RuntimeError):
            pass  # Microphone bytes are discarded and never stored or sent to a model.
        finally:
            music_voice.end_session(context.context.session_id)
            identity.OWNER.reset(owner_token)

    app.include_router(spotify_auth.router)
    app.include_router(music_api.router)
    app.include_router(music_voice.router)
    app.include_router(auth.router)
    app.include_router(connections.api)
    return app


if __name__ == "__main__":
    import uvicorn
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--origin", default="http://127.0.0.1:5174")
    args = parser.parse_args()
    if not args.origin.startswith("http://127.0.0.1:"):
        raise SystemExit("The fixture requires a 127.0.0.1 browser origin")
    (Path(__file__).resolve().parents[1] / "data").mkdir(exist_ok=True)
    uvicorn.run(create_app(args.origin), host="127.0.0.1", port=args.port, access_log=False)
