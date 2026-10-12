"""/ws/call tests. Both sides are faked at the boundary and driven in one event loop:
FakeBrowser is the browser's WebSocket, FakeSession is a Gemini Live connection.
(Starlette's threaded TestClient cancels the app the instant it hangs up, a race real
servers don't have; that made these tests flaky, see BUILD_LOG Step 14.)"""
import asyncio
import os
import struct
from contextlib import asynccontextmanager
from types import SimpleNamespace

os.environ.setdefault("GEMINI_API_KEY", "test")

from fastapi import WebSocketDisconnect  # noqa: E402
from google.genai import errors  # noqa: E402

from koe import voice_call  # noqa: E402

SILENT = b"\x00\x00" * 640
VOICED = struct.pack("<640h", *[3000] * 640)  # 40 ms mic chunks
HANG_UP = None


class FakeBrowser:
    def __init__(self):
        self.to_backend, self.to_browser = asyncio.Queue(), asyncio.Queue()

    async def accept(self):
        pass

    async def receive_bytes(self):
        data = await self.to_backend.get()
        if data is HANG_UP:
            raise WebSocketDisconnect(1000)
        return data

    async def send_bytes(self, data):
        await self.to_browser.put(data)

    async def send_json(self, event):
        await self.to_browser.put(event)

    async def close(self, code=1000, reason=None):
        await self.to_browser.put(("closed", code, reason))

    def says(self, data):
        self.to_backend.put_nowait(data)

    async def hears(self):
        return await asyncio.wait_for(self.to_browser.get(), 2)


def msg(server_content=None, go_away=None, handle=None):
    update = SimpleNamespace(resumable=True, new_handle=handle) if handle else None
    return SimpleNamespace(server_content=server_content, go_away=go_away, session_resumption_update=update)


class FakeSession:
    """A Gemini Live connection. Each mic chunk gets a reply turn:
    b'BARGE' -> interrupted, b'GOAWAY' -> resume handle + GoAway,
    b'DROP' -> resume handle, then the connection breaks, else -> audio b'reply:' + chunk."""

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
            part = SimpleNamespace(inline_data=SimpleNamespace(data=b"reply:" + data))
            yield msg(SimpleNamespace(interrupted=None, model_turn=SimpleNamespace(parts=[part])))


def fake_gemini(monkeypatch):
    """Patches genai.Client; returns the list of (config, session) per Gemini connection."""
    connections = []

    class FakeClient:
        def __init__(self, api_key):
            self.aio = SimpleNamespace(live=SimpleNamespace(connect=self.connect))

        @asynccontextmanager
        async def connect(self, model, config):
            assert model == voice_call.LIVE_MODEL
            session = FakeSession(f"conn{len(connections) + 1}")
            connections.append((config, session))
            yield session

    monkeypatch.setattr(voice_call.genai, "Client", FakeClient)
    return connections


async def reconnected(connections):
    # Audio sent in the instant between GoAway/drop and the new connection can be lost
    # (documented ceiling), so speak again once the second connection exists.
    async with asyncio.timeout(3):
        while len(connections) < 2:
            await asyncio.sleep(0.01)


def run_call(scenario):
    """Starts /ws/call against a FakeBrowser, runs the scenario, hangs up, and requires the
    call to end cleanly (no exception, no hang)."""
    async def main():
        browser = FakeBrowser()
        call = asyncio.create_task(voice_call.call(browser))
        await scenario(browser)
        browser.says(HANG_UP)
        await asyncio.wait_for(call, 3)

    asyncio.run(main())


def test_call_relays_audio_reports_latency_and_barge_in(monkeypatch):
    connections = fake_gemini(monkeypatch)

    async def scenario(browser):
        browser.says(SILENT)
        assert await browser.hears() == b"reply:" + SILENT  # no speech heard yet -> no latency event
        for _ in range(2):  # works across several model turns
            browser.says(VOICED)
            assert await browser.hears() == b"reply:" + VOICED
            event = await browser.hears()
            assert event["type"] == "latency" and event["ms"] >= 0
        browser.says(b"BARGE")
        assert await browser.hears() == {"type": "interrupted"}  # browser must flush its playback queue

    run_call(scenario)
    config, session = connections[0]
    assert config["response_modalities"] == ["AUDIO"]
    assert config["session_resumption"].handle is None  # resumption on from the first connection
    assert {a.mime_type for a in session.sent} == {"audio/pcm;rate=16000"}


def test_goaway_resumes_on_new_connection_with_latest_handle(monkeypatch):
    connections = fake_gemini(monkeypatch)

    async def scenario(browser):
        browser.says(b"GOAWAY")  # Gemini: here's a handle, and I'm closing soon
        await reconnected(connections)
        browser.says(SILENT)  # the call carries on, answered by the second connection
        assert await browser.hears() == b"reply:" + SILENT

    run_call(scenario)
    assert len(connections) == 2
    assert connections[1][0]["session_resumption"].handle == "handle-from-conn1"


def test_unexpected_drop_resumes_with_handle(monkeypatch):
    connections = fake_gemini(monkeypatch)

    async def scenario(browser):
        browser.says(b"DROP")  # handle arrives, then the connection breaks (0.5 s back-off)
        await reconnected(connections)
        browser.says(SILENT)
        assert await browser.hears() == b"reply:" + SILENT

    run_call(scenario)
    assert connections[1][0]["session_resumption"].handle == "handle-from-conn1"


def test_route_is_mounted():
    assert [r.path for r in voice_call.router.routes] == ["/ws/call"]


def test_rms_tells_speech_from_silence():
    assert voice_call.rms(SILENT) == 0
    assert voice_call.rms(b"\x00\x00\x00") == 0  # odd length must not crash the call
    assert voice_call.rms(struct.pack("<4h", 3000, -3000, 3000, -3000)) == 3000
    assert voice_call.rms(VOICED) > voice_call.VOICE_RMS


def test_summarize_percentiles():
    assert voice_call.summarize([]) == "no turns"
    assert voice_call.summarize([900]) == "1 turns, p50 900 ms, p95 900 ms"
    assert voice_call.summarize(list(range(100, 2100, 100))) == "20 turns, p50 1050 ms, p95 1995 ms"
