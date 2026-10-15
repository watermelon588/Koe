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

from koe.config import settings
from koe import gemini, voice_call  # noqa: E402

SILENT = b"\x00\x00" * 640
VOICED = struct.pack("<640h", *[3000] * 640)  # 40 ms mic chunks
HANG_UP = None


class FakeBrowser:
    def __init__(self):
        self.to_backend, self.to_browser = asyncio.Queue(), asyncio.Queue()

    async def accept(self):
        pass

    async def receive(self):  # like Starlette: bytes or text frames, then a disconnect message
        data = await self.to_backend.get()
        if data is HANG_UP:
            return {"type": "websocket.disconnect", "code": 1000}
        key = "text" if isinstance(data, str) else "bytes"
        return {"type": "websocket.receive", key: data}

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


def content(**fields):
    """A server_content with the SDK's defaults (everything None) plus the given fields."""
    base = dict(interrupted=None, model_turn=None, input_transcription=None, output_transcription=None,
                turn_complete=None)
    return SimpleNamespace(**{**base, **fields})


def msg(server_content=None, go_away=None, handle=None, tool_call=None):
    update = SimpleNamespace(resumable=True, new_handle=handle) if handle else None
    return SimpleNamespace(server_content=server_content, go_away=go_away,
                           session_resumption_update=update, tool_call=tool_call)


class FakeSession:
    """A Gemini Live connection. Each mic chunk gets a reply turn:
    b'BARGE' -> interrupted, b'GOAWAY' -> resume handle + GoAway,
    b'DROP' -> resume handle, then the connection breaks, b'TOOL' -> asks for github_my_prs and
    speaks once the tool result arrives, b'SPEAK' -> transcripts of both sides + audio + turn end,
    typed text -> a spoken answer with its transcript, else -> audio b'reply:' + chunk."""

    def __init__(self, name):
        self.name, self.sent, self.replies, self.tool_responses = name, [], asyncio.Queue(), []
        self.texts = []

    async def send_tool_response(self, function_responses):
        self.tool_responses.extend(function_responses)
        await self.replies.put(b"after-tool")

    async def send_realtime_input(self, audio=None, text=None):
        if text is not None:
            self.texts.append(text)
            return await self.replies.put(("text", text))
        self.sent.append(audio)
        await self.replies.put(audio.data)

    async def receive(self):  # like the SDK: yields one model turn, then ends
        data = await self.replies.get()
        if isinstance(data, tuple):  # typed text: Gemini answers out loud, with a transcript
            yield msg(content(output_transcription=SimpleNamespace(text="ok: " + data[1]), turn_complete=True))
        elif data == b"SPEAK":
            yield msg(content(input_transcription=SimpleNamespace(text="hi koe")))
            yield msg(content(output_transcription=SimpleNamespace(text="hello!"),
                              model_turn=SimpleNamespace(parts=[SimpleNamespace(inline_data=SimpleNamespace(data=b"hello-audio"))])))
            yield msg(content(turn_complete=True))
        elif data == b"BARGE":
            yield msg(content(interrupted=True))
        elif data == b"GOAWAY":
            yield msg(handle=f"handle-from-{self.name}")
            yield msg(go_away=SimpleNamespace(time_left="5s"))
        elif data == b"TOOL":
            call = SimpleNamespace(id="call-1", name="github_my_prs", args={"state": "open"})
            yield msg(tool_call=SimpleNamespace(function_calls=[call]))
        elif data == b"DROP":
            yield msg(handle=f"handle-from-{self.name}")
            raise errors.APIError(1006, {"message": "abnormal closure"})
        else:
            part = SimpleNamespace(inline_data=SimpleNamespace(data=b"reply:" + data))
            yield msg(content(model_turn=SimpleNamespace(parts=[part])))


def fake_gemini(monkeypatch):
    """Patches genai.Client; returns the list of (config, session) per Gemini connection."""
    connections = []

    class FakeClient:
        def __init__(self, api_key, http_options=None):
            self.aio = SimpleNamespace(live=SimpleNamespace(connect=self.connect))

        @asynccontextmanager
        async def connect(self, model, config):
            assert model == voice_call.LIVE_MODEL
            session = FakeSession(f"conn{len(connections) + 1}")
            connections.append((config, session))
            yield session

    monkeypatch.setattr(gemini.genai, "Client", FakeClient)  # clients are made in koe/gemini.py
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


def test_tool_call_runs_the_tool_and_returns_its_result_to_gemini(monkeypatch):
    connections = fake_gemini(monkeypatch)

    async def fake_my_prs(state="open"):
        return {"count": 1, "prs": [{"number": 42, "ci": "failing"}]}

    monkeypatch.setitem(voice_call.agent.TOOLS, "github_my_prs",
                        voice_call.agent.TOOLS["github_my_prs"]._replace(fn=fake_my_prs))

    async def scenario(browser):
        browser.says(b"TOOL")
        assert await browser.hears() == {"type": "tool", "name": "github_my_prs", "phase": "start"}
        end = await browser.hears()
        assert end["phase"] == "end" and end["ok"] is True and end["ms"] >= 0
        assert await browser.hears() == b"reply:after-tool"  # Gemini speaks after getting the result

    run_call(scenario)
    (response,) = connections[0][1].tool_responses
    assert (response.id, response.name) == ("call-1", "github_my_prs")
    assert response.response == {"count": 1, "prs": [{"number": 42, "ci": "failing"}]}
    declared = connections[0][0]["tools"][0]["function_declarations"]
    assert {d["name"] for d in declared} == set(voice_call.agent.TOOLS)


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


def test_transcripts_and_turn_end_reach_the_browser(monkeypatch):
    connections = fake_gemini(monkeypatch)

    async def scenario(browser):
        browser.says(b"SPEAK")
        assert await browser.hears() == {"type": "transcript", "role": "user", "text": "hi koe"}
        assert await browser.hears() == {"type": "transcript", "role": "koe", "text": "hello!"}
        assert await browser.hears() == b"hello-audio"
        assert (await browser.hears())["type"] == "latency"  # b"SPEAK" counts as speech
        assert await browser.hears() == {"type": "turn_complete"}

    run_call(scenario)
    config = connections[0][0]
    assert config["input_audio_transcription"] == {} and config["output_audio_transcription"] == {}
    from koe import events
    assert len(events.hub_for().latencies) == 1
    assert events.hub_for().latencies[0]["ms"] >= 0


def test_typed_text_goes_to_gemini_and_bad_frames_are_ignored(monkeypatch):
    connections = fake_gemini(monkeypatch)

    async def scenario(browser):
        browser.says("not json")  # ignored, the call carries on
        browser.says('{"type": "mute"}')  # unknown event: ignored
        browser.says('{"type": "text", "text": 42}')  # not a string: ignored
        browser.says('{"type": "text", "text": "   "}')  # empty after trimming: ignored
        browser.says('{"type": "text", "text": "  what is on today?  "}')
        assert await browser.hears() == {"type": "transcript", "role": "koe", "text": "ok: what is on today?"}
        assert await browser.hears() == {"type": "turn_complete"}
        browser.says('{"type": "text", "text": "' + "x" * 5000 + '"}')
        await browser.hears()
        await browser.hears()

    run_call(scenario)
    texts = connections[0][1].texts
    assert texts[0] == "what is on today?"
    assert len(texts) == 2 and len(texts[1]) == voice_call.MAX_TEXT


def test_browser_call_requires_access_token_when_storage_enables_writes(monkeypatch):
    monkeypatch.setattr(settings, "database_url", "postgresql://test@localhost/test?sslmode=require")
    async def scenario():
        browser = FakeBrowser()
        await voice_call.call(browser)
        assert (await browser.hears())[1] == 1008
    asyncio.run(scenario())


def test_invalid_access_token_never_opens_a_gemini_session(monkeypatch):
    monkeypatch.setattr(settings, "koe_access_token", "private-app-token")
    class Browser(FakeBrowser):
        async def receive_json(self):
            return {"type": "auth", "token": "wrong"}
    async def scenario():
        browser = Browser()
        await voice_call.call(browser)
        assert (await browser.hears())[1] == 1008
    asyncio.run(scenario())


def test_valid_access_token_allows_the_existing_voice_flow(monkeypatch):
    fake_gemini(monkeypatch)
    monkeypatch.setattr(settings, "koe_access_token", "private-app-token")
    async def receive_json(self):
        return {"type": "auth", "token": "private-app-token"}
    monkeypatch.setattr(FakeBrowser, "receive_json", receive_json, raising=False)
    async def scenario(browser):
        browser.says(SILENT)
        assert await browser.hears() == b"reply:" + SILENT
    run_call(scenario)
