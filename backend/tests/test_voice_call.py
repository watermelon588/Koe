import asyncio
import os
import struct
from contextlib import asynccontextmanager
from types import SimpleNamespace

os.environ.setdefault("GEMINI_API_KEY", "test")

from fastapi.testclient import TestClient  # noqa: E402
from google.genai import errors  # noqa: E402

from koe import voice_call  # noqa: E402
from koe.main import app  # noqa: E402


def msg(server_content=None, go_away=None, handle=None):
    update = SimpleNamespace(resumable=True, new_handle=handle) if handle else None
    return SimpleNamespace(server_content=server_content, go_away=go_away, session_resumption_update=update)


def audio(data):
    part = SimpleNamespace(inline_data=SimpleNamespace(data=data))
    return msg(SimpleNamespace(interrupted=None, model_turn=SimpleNamespace(parts=[part])))


class FakeSession:
    """Stands in for a Gemini Live session. Each mic chunk gets a reply turn:
    b'BARGE' -> interrupted, b'GOAWAY' -> new resume handle + GoAway,
    b'DROP' -> connection breaks, anything else -> audio b'reply:' + chunk."""

    def __init__(self, name):
        self.name, self.sent, self.replies = name, [], asyncio.Queue()

    async def send_realtime_input(self, audio):
        self.sent.append(audio)
        await self.replies.put(audio.data)

    async def receive(self):  # like the SDK: yields one model turn, then ends
        data = await self.replies.get()
        if data == b"BARGE":
            yield msg(SimpleNamespace(interrupted=True, model_turn=None))
        elif data == b"GOAWAY":
            yield msg(handle=f"handle-from-{self.name}")
            yield msg(go_away=SimpleNamespace(time_left="5s"))
        elif data == b"DROP":
            yield msg(handle=f"handle-from-{self.name}")
            raise errors.APIError(1006, {"message": "abnormal closure"})
        else:
            yield audio(b"reply:" + data)


SILENT = b"\x00\x00" * 640
VOICED = struct.pack("<640h", *[3000] * 640)  # 40 ms mic chunks


def test_call_relays_audio_latency_and_barge_in(monkeypatch):
    connections = []
    monkeypatch.setattr(voice_call.genai, "Client", _client_class(connections))
    with TestClient(app).websocket_connect("/ws/call") as ws:
        ws.send_bytes(SILENT)
        assert ws.receive_bytes() == b"reply:" + SILENT  # no speech heard yet -> no latency event
        for _ in range(2):  # works across several model turns
            ws.send_bytes(VOICED)
            assert ws.receive_bytes() == b"reply:" + VOICED
            event = ws.receive_json()
            assert event["type"] == "latency" and event["ms"] >= 0
        ws.send_bytes(b"BARGE")
        assert ws.receive_json() == {"type": "interrupted"}  # browser must flush its playback queue

    config, session = connections[0]
    assert config["response_modalities"] == ["AUDIO"]
    assert config["session_resumption"].handle is None  # resumption on from the first connection
    assert {a.mime_type for a in session.sent} == {"audio/pcm;rate=16000"}


def test_goaway_resumes_on_new_connection_with_latest_handle(monkeypatch):
    connections = []
    monkeypatch.setattr(voice_call.genai, "Client", _client_class(connections))
    with TestClient(app).websocket_connect("/ws/call") as ws:
        ws.send_bytes(b"GOAWAY")  # Gemini: here's a handle, and I'm closing soon
        ws.send_bytes(SILENT)  # the call carries on, answered by the second connection
        assert ws.receive_bytes() == b"reply:" + SILENT

    assert len(connections) == 2
    assert connections[1][0]["session_resumption"].handle == "handle-from-conn1"


def test_unexpected_drop_resumes_with_handle(monkeypatch):
    connections = []
    monkeypatch.setattr(voice_call.genai, "Client", _client_class(connections))
    with TestClient(app).websocket_connect("/ws/call") as ws:
        ws.send_bytes(b"DROP")  # handle arrives, then the connection breaks (0.5 s back-off)
        ws.send_bytes(SILENT)
        assert ws.receive_bytes() == b"reply:" + SILENT

    assert connections[1][0]["session_resumption"].handle == "handle-from-conn1"


def test_rms_tells_speech_from_silence():
    assert voice_call.rms(SILENT) == 0
    assert voice_call.rms(b"\x00\x00\x00") == 0  # odd length must not crash the call
    assert voice_call.rms(struct.pack("<4h", 3000, -3000, 3000, -3000)) == 3000
    assert voice_call.rms(VOICED) > voice_call.VOICE_RMS


def test_summarize_percentiles():
    assert voice_call.summarize([]) == "no turns"
    assert voice_call.summarize([900]) == "1 turns, p50 900 ms, p95 900 ms"
    assert voice_call.summarize(list(range(100, 2100, 100))) == "20 turns, p50 1050 ms, p95 1995 ms"


def _client_class(connections):
    class FakeClient:
        def __init__(self, api_key):
            self.aio = SimpleNamespace(live=SimpleNamespace(connect=self.connect))

        @asynccontextmanager
        async def connect(self, model, config):
            assert model == voice_call.LIVE_MODEL
            session = FakeSession(f"conn{len(connections) + 1}")
            connections.append((config, session))
            yield session

    return FakeClient
