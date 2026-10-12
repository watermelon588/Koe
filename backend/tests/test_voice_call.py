import asyncio
import os
import struct
from contextlib import asynccontextmanager
from types import SimpleNamespace

os.environ.setdefault("GEMINI_API_KEY", "test")

from fastapi.testclient import TestClient  # noqa: E402

from koe import voice_call  # noqa: E402
from koe.main import app  # noqa: E402


class FakeSession:
    """Stands in for a Gemini Live session: answers every audio chunk with b'reply:' + chunk,
    except b'BARGE', which it answers like Gemini does when the user talks over it."""

    def __init__(self):
        self.sent = []
        self.replies = asyncio.Queue()

    async def send_realtime_input(self, audio):
        self.sent.append(audio)
        await self.replies.put(None if audio.data == b"BARGE" else b"reply:" + audio.data)

    async def receive(self):  # like the SDK: yields one model turn, then ends
        data = await self.replies.get()
        if data is None:
            yield SimpleNamespace(server_content=SimpleNamespace(interrupted=True, model_turn=None))
            return
        part = SimpleNamespace(inline_data=SimpleNamespace(data=data))
        yield SimpleNamespace(server_content=SimpleNamespace(interrupted=None, model_turn=SimpleNamespace(parts=[part])))


def test_call_relays_mic_to_gemini_and_gemini_audio_back(monkeypatch):
    session = FakeSession()
    connected = {}

    class FakeClient:
        def __init__(self, api_key):
            self.aio = SimpleNamespace(live=SimpleNamespace(connect=self.connect))

        @asynccontextmanager
        async def connect(self, model, config):
            connected.update(model=model, config=config)
            yield session

    monkeypatch.setattr(voice_call.genai, "Client", FakeClient)

    silent, voiced = b"\x00\x00" * 640, struct.pack("<640h", *[3000] * 640)  # 40 ms mic chunks
    with TestClient(app).websocket_connect("/ws/call") as ws:
        ws.send_bytes(silent)
        assert ws.receive_bytes() == b"reply:" + silent  # no speech heard yet -> no latency event
        for _ in range(2):  # works across several model turns
            ws.send_bytes(voiced)
            assert ws.receive_bytes() == b"reply:" + voiced
            event = ws.receive_json()
            assert event["type"] == "latency" and event["ms"] >= 0
        ws.send_bytes(b"BARGE")
        assert ws.receive_json() == {"type": "interrupted"}  # browser must flush its playback queue

    assert connected["model"] == voice_call.LIVE_MODEL
    assert connected["config"]["response_modalities"] == ["AUDIO"]
    assert {a.mime_type for a in session.sent} == {"audio/pcm;rate=16000"}


def test_rms_tells_speech_from_silence():
    assert voice_call.rms(b"\x00\x00" * 640) == 0
    assert voice_call.rms(b"\x00\x00\x00") == 0  # odd length must not crash the call
    assert voice_call.rms(struct.pack("<4h", 3000, -3000, 3000, -3000)) == 3000
    assert voice_call.rms(struct.pack("<640h", *[3000] * 640)) > voice_call.VOICE_RMS


def test_summarize_percentiles():
    assert voice_call.summarize([]) == "no turns"
    assert voice_call.summarize([900]) == "1 turns, p50 900 ms, p95 900 ms"
    assert voice_call.summarize(list(range(100, 2100, 100))) == "20 turns, p50 1050 ms, p95 1995 ms"
