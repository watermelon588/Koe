"""/ws/call: browser <-> Gemini Live, relaying audio both ways.

Browser sends mic audio as 16 kHz PCM16 LE chunks; Gemini replies with 24 kHz PCM16 LE.
Gemini's server-side voice activity detection decides when you've stopped talking.
Live API (Python SDK): https://ai.google.dev/gemini-api/docs/live-api/get-started-sdk

Messages to the browser: binary = Koe's audio; text = JSON control events:
  {"type": "interrupted"}        user talked over Koe: drop queued audio
  {"type": "latency", "ms": 1093} you stopped speaking -> Koe's first audio, per turn
"""
import asyncio
import contextlib
import logging
import math
import statistics
import struct
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import errors, types

from koe.config import settings

router = APIRouter()
log = logging.getLogger("uvicorn.error")

# Verified 2026-10-12 on https://ai.google.dev/gemini-api/docs/models (stable, free tier).
LIVE_MODEL = "gemini-3.8-live"

# ponytail: prompt lives here until Phase 2 moves it into agent.py with the tools.
SYSTEM_PROMPT = (
    "You are Koe (声, 'voice'), a warm, upbeat voice assistant for Rohit, a developer founder "
    "in India (timezone Asia/Kolkata). This is a live voice call: answer in one to three short "
    "spoken sentences, no lists or markdown. You have no tools yet, so if asked to check GitHub, "
    "the calendar or Notion, say that's coming soon."
)
CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": SYSTEM_PROMPT,
    # Lifts the 15 min audio-session cap: old context is trimmed instead of ending the session.
    # https://ai.google.dev/gemini-api/docs/live-api/session-management
    "context_window_compression": types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
}
MAX_QUICK_DROPS = 3  # consecutive connections that die within STABLE_SECS before we give up
STABLE_SECS = 30

# ponytail: naive energy check to timestamp "user stopped speaking"; only used for the latency
# metric (Gemini's own VAD drives the conversation). Ceiling: loud background noise counts as speech.
VOICE_RMS = 500  # PCM16 units; browser noise suppression keeps silence far below this


def rms(pcm: bytes) -> float:
    n = len(pcm) // 2  # ignore a stray odd byte rather than crash the call on bad input
    samples = struct.unpack(f"<{n}h", pcm[: n * 2])
    return math.sqrt(sum(s * s for s in samples) / len(samples)) if samples else 0.0


def summarize(latencies_ms: list[int]) -> str:
    if not latencies_ms:
        return "no turns"
    p95 = statistics.quantiles(latencies_ms, n=20)[18] if len(latencies_ms) > 1 else latencies_ms[0]
    return f"{len(latencies_ms)} turns, p50 {statistics.median(latencies_ms):.0f} ms, p95 {p95:.0f} ms"


class CallState:
    """Per-call state shared by the relay tasks; survives Gemini reconnects."""

    def __init__(self):
        self.last_voice: float | None = None  # when the last mic chunk with speech arrived
        self.latencies_ms: list[int] = []
        self.resume_handle: str | None = None  # latest Gemini session-resumption handle


async def _read_mic(ws: WebSocket, mic: asyncio.Queue, state: CallState):
    # Reading is decoupled from uploading: if the upload to Gemini stalls, chunks are still
    # taken off the socket (and timestamped) on arrival, so the latency metric includes the stall.
    while True:
        pcm = await ws.receive_bytes()
        if rms(pcm) > VOICE_RMS:
            state.last_voice = time.perf_counter()
        mic.put_nowait(pcm)


async def _upload_mic(mic: asyncio.Queue, session):
    while True:
        pcm = await mic.get()
        await session.send_realtime_input(audio=types.Blob(data=pcm, mime_type="audio/pcm;rate=16000"))


async def _gemini_to_browser(ws: WebSocket, session, state: CallState):
    """Relays one Gemini connection. Returns on GoAway (time to reconnect); raises if it breaks."""
    while True:  # session.receive() ends after each model turn, so loop for the next one
        first_audio = True
        async for msg in session.receive():
            update = msg.session_resumption_update
            if update and update.resumable and update.new_handle:
                state.resume_handle = update.new_handle
            if msg.go_away:
                log.info("Gemini GoAway (time left %s): resuming on a new connection", msg.go_away.time_left)
                return
            sc = msg.server_content
            if sc and sc.interrupted:
                # User talked over Koe: tell the browser to drop queued audio (barge-in).
                # https://ai.google.dev/gemini-api/docs/live-api/capabilities
                await ws.send_json({"type": "interrupted"})
                first_audio = True
            if sc and sc.model_turn:
                for part in sc.model_turn.parts:
                    if part.inline_data:
                        await ws.send_bytes(part.inline_data.data)
                        if first_audio and state.last_voice is not None:
                            ms = round((time.perf_counter() - state.last_voice) * 1000)
                            state.latencies_ms.append(ms)
                            log.info("turn latency: speech end -> first audio %d ms", ms)
                            await ws.send_json({"type": "latency", "ms": ms})
                        first_audio = False


async def _relay_gemini(ws: WebSocket, mic: asyncio.Queue, state: CallState, client):
    """Keeps one logical conversation alive across Gemini connections using session resumption.
    https://ai.google.dev/gemini-api/docs/live-api/session-management"""
    quick_drops = 0
    while True:
        # handle=None on the first connection still switches on resumption updates.
        config = {**CONFIG, "session_resumption": types.SessionResumptionConfig(handle=state.resume_handle)}
        connected_at = time.monotonic()
        try:
            async with client.aio.live.connect(model=LIVE_MODEL, config=config) as session:
                # TaskGroup (not a loose task) so the uploader is always finished before we
                # reconnect or exit, and its errors aren't silently lost.
                async with asyncio.TaskGroup() as tg:
                    upload = tg.create_task(_upload_mic(mic, session))
                    await _gemini_to_browser(ws, session, state)  # returns on GoAway
                    upload.cancel()
            quick_drops = 0
        except* (errors.APIError, OSError) as eg:  # dropped connection / network blip
            stable = time.monotonic() - connected_at > STABLE_SECS
            quick_drops = 1 if stable else quick_drops + 1
            if state.resume_handle is None or quick_drops > MAX_QUICK_DROPS:
                raise
            log.warning("Gemini connection lost (%s): resuming, attempt %d", eg.exceptions[0], quick_drops)
            await asyncio.sleep(0.5 * quick_drops)


@router.websocket("/ws/call")
async def call(ws: WebSocket):
    await ws.accept()
    client = genai.Client(api_key=settings.gemini_api_key)
    state = CallState()
    mic: asyncio.Queue[bytes] = asyncio.Queue()
    try:
        # The browser side lives for the whole call; the Gemini side may reconnect underneath it.
        # If either fails (e.g. user hangs up), the other is cancelled.
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_read_mic(ws, mic, state))
            tg.create_task(_relay_gemini(ws, mic, state, client))
    except* WebSocketDisconnect:
        pass  # user hung up
    except* Exception as eg:
        log.exception("call failed")
        with contextlib.suppress(Exception):  # the browser may already be gone
            await ws.close(code=1011, reason=f"Gemini error: {eg.exceptions[0]}"[:120])
    finally:
        log.info("call ended: %s", summarize(state.latencies_ms))
    # If we're being cancelled (server shutdown) at the same moment the user hangs up, the
    # TaskGroup reports only the hang-up, which we just swallowed. Never swallow a cancel.
    # https://docs.python.org/3/library/asyncio-task.html#task-cancellation
    if asyncio.current_task().cancelling():
        raise asyncio.CancelledError
