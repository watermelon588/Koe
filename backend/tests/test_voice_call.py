import asyncio
import os
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

    with TestClient(app).websocket_connect("/ws/call") as ws:
        for chunk in (b"\x01\x02" * 640, b"\x03\x04" * 640):  # two 40 ms mic chunks
            ws.send_bytes(chunk)
            assert ws.receive_bytes() == b"reply:" + chunk  # works across several model turns
        ws.send_bytes(b"BARGE")
        assert ws.receive_json() == {"type": "interrupted"}  # browser must flush its playback queue

    assert connected["model"] == voice_call.LIVE_MODEL
    assert connected["config"]["response_modalities"] == ["AUDIO"]
    assert {a.mime_type for a in session.sent} == {"audio/pcm;rate=16000"}
