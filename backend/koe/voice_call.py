"""/ws/call: browser <-> Gemini Live, relaying audio both ways.

Browser sends mic audio as 16 kHz PCM16 LE chunks; Gemini replies with 24 kHz PCM16 LE.
Gemini's server-side voice activity detection decides when you've stopped talking.
Live API (Python SDK): https://ai.google.dev/gemini-api/docs/live-api/get-started-sdk

Messages to the browser: binary = Koe's audio; text = JSON control events:
  {"type": "interrupted"}        user talked over Koe: drop queued audio
  {"type": "latency", "ms": 1093} you stopped speaking -> Koe's first audio, per turn
  {"type": "tool", "name": "github_my_prs", "phase": "start"}           a tool began (Koe is "thinking")
  {"type": "tool", "name": "github_my_prs", "phase": "end", "ms": 640, "ok": true}
  {"type": "transcript", "role": "user" | "koe", "text": "..."}  a piece of what was said (chunks arrive in order)
  {"type": "turn_complete"}       Koe finished its reply
Text frames from the browser: {"type": "text", "text": "..."} = a typed chat message (same conversation).
"""
import asyncio
import contextlib
import json
import logging
import math
import statistics
import struct
import time

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import errors, types

from koe import agent, auth, events, identity, store
from koe.config import settings

router = APIRouter()
log = logging.getLogger("uvicorn.error")

# Verified 2026-10-12 on https://ai.google.dev/gemini-api/docs/models (stable, free tier).
LIVE_MODEL = "gemini-3.8-live"

CONFIG = {
    "response_modalities": ["AUDIO"],
    "system_instruction": agent.SYSTEM_PROMPT,
    # Same tool registry as every other channel. https://ai.google.dev/gemini-api/docs/live-api/tools
    "tools": [{"function_declarations": agent.declarations()}],
    # Lifts the 15 min audio-session cap: old context is trimmed instead of ending the session.
    # https://ai.google.dev/gemini-api/docs/live-api/session-management
    "context_window_compression": types.ContextWindowCompressionConfig(sliding_window=types.SlidingWindow()),
    # Text of both sides of the conversation, for the chat panel.
    # https://ai.google.dev/gemini-api/docs/live-api/capabilities#audio-transcription
    "input_audio_transcription": {},
    "output_audio_transcription": {},
}
MAX_TEXT = 2000  # characters per typed message; the browser is untrusted input
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
        self.context = agent.Conversation("web")
        self.user_text = ""
        self.koe_text = ""
        self.activity = asyncio.Queue(maxsize=100)


def _log_message(state: CallState, text: str, role: str):
    _log_activity(state, "message", text, {"role": role})


def _log_activity(state: CallState, kind: str, summary: str, payload: dict):
    if summary and store.configured():
        try:
            state.activity.put_nowait((kind, summary, payload))
        except asyncio.QueueFull:
            log.warning("Activity buffer full; transcript logging skipped")


async def _save_activity(state: CallState):
    while True:
        kind, summary, payload = await state.activity.get()
        await store.record_best_effort("web", state.context.session_id, kind, summary, payload)


async def _approval_result(ws: WebSocket, state: CallState, approve: bool, action_id: str | None = None) -> dict:
    result = await agent.confirm(state.context, approve, action_id)
    remaining = state.context.pending
    await ws.send_json({"type": "approval_result", **result,
                       "pending_action": {k: remaining[k] for k in ("id", "summary", "expires_ts")} if remaining else None})
    return result


def _outcome(result: dict) -> str:
    return "Application approval result (do not execute the action again): " + json.dumps(result)


async def _read_mic(ws: WebSocket, mic: asyncio.Queue, state: CallState):
    # Reading is decoupled from uploading: if the upload to Gemini stalls, chunks are still
    # taken off the socket (and timestamped) on arrival, so the latency metric includes the stall.
    # Binary frames = mic audio (bytes on the queue); text frames = typed chat (str on the queue).
    while True:
        frame = await ws.receive()
        if frame["type"] == "websocket.disconnect":
            raise WebSocketDisconnect(frame.get("code", 1000))
        if frame.get("bytes") is not None:
            pcm = frame["bytes"]
            if rms(pcm) > VOICE_RMS:
                state.last_voice = time.perf_counter()
            mic.put_nowait(pcm)
        else:
            raw = frame.get("text")
            if text := _typed_text(raw):
                state.last_voice = time.perf_counter()
                _log_message(state, text, "user")
                decision = agent.confirmation(text)
                if decision is not None and state.context.pending:
                    result = await _approval_result(ws, state, decision)
                    mic.put_nowait(_outcome(result))
                else:
                    mic.put_nowait(text)
            else:
                try:
                    event = json.loads(raw or "")
                except ValueError:
                    continue
                if (isinstance(event, dict) and event.get("type") == "approval" and
                    type(event.get("approve")) is bool and isinstance(event.get("action_id"), str)):
                    # A UI click explicitly names the proposal shown on that client's card.
                    if state.context.pending and event["action_id"] == state.context.pending["id"]:
                        state.context.approval_ready = True
                    result = await _approval_result(ws, state, event["approve"], event["action_id"])
                    mic.put_nowait(_outcome(result))


def _typed_text(raw: str | None) -> str | None:
    """{"type": "text", "text": "..."} -> the message; anything else is ignored, never fatal."""
    try:
        event = json.loads(raw or "")
    except ValueError:
        return None
    text = event.get("text") if isinstance(event, dict) and event.get("type") == "text" else None
    if not isinstance(text, str):
        return None
    return text.strip()[:MAX_TEXT] or None


async def _upload_mic(mic: asyncio.Queue, session):
    while True:
        item = await mic.get()
        if isinstance(item, str):
            await session.send_realtime_input(text=item)
        else:
            await session.send_realtime_input(audio=types.Blob(data=item, mime_type="audio/pcm;rate=16000"))


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
            if sc and sc.input_transcription and sc.input_transcription.text:
                await ws.send_json({"type": "transcript", "role": "user", "text": sc.input_transcription.text})
                state.user_text += sc.input_transcription.text
            if sc and sc.input_transcription and getattr(sc.input_transcription, "finished", False):
                await _finish_user_turn(ws, session, state)
            if msg.tool_call:
                await _run_tools(ws, session, msg.tool_call.function_calls, state)
            if sc and sc.output_transcription and sc.output_transcription.text:
                await ws.send_json({"type": "transcript", "role": "koe", "text": sc.output_transcription.text})
                state.koe_text += sc.output_transcription.text
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
                            events.publish("latency", ms=ms, session_id=state.context.session_id, channel="web")
                            _log_activity(state, "latency", f"Turn latency: {ms} ms",
                                          {"latency": {"speech_end_to_first_audio_ms": ms}})
                        first_audio = False
            if sc and sc.turn_complete:
                # Fallback for models that omit Transcription.finished. Check before arming a new proposal.
                await _finish_user_turn(ws, session, state)
                if state.context.pending:
                    state.context.approval_ready = True
                _log_message(state, state.koe_text, "koe")
                state.koe_text = ""
                await ws.send_json({"type": "turn_complete"})


async def _finish_user_turn(ws: WebSocket, session, state: CallState):
    text, state.user_text = state.user_text, ""
    _log_message(state, text, "user")
    decision = agent.confirmation(text)
    if decision is not None and state.context.pending and state.context.approval_ready:
        result = await _approval_result(ws, state, decision)
        await session.send_realtime_input(text=_outcome(result))


async def _run_tools(ws: WebSocket, session, calls, state: CallState):
    """Gemini asked for tools. Calls are blocking by default: it waits for our answer.
    ponytail: runs them one after another; gather() them if Gemini starts asking for several at once."""
    responses = []
    for fc in calls:
        await ws.send_json({"type": "tool", "name": fc.name, "phase": "start"})
        t = time.perf_counter()
        result = await agent.run_tool(fc.name, fc.args, context=state.context)
        ms, ok = round((time.perf_counter() - t) * 1000), "error" not in result
        log.info("tool %s(%s) %d ms ok=%s", fc.name, fc.args or "", ms, ok)
        await ws.send_json({"type": "tool", "name": fc.name, "phase": "end", "ms": ms, "ok": ok})
        if "pending_action" in result:
            await ws.send_json({"type": "approval_pending", **result["pending_action"]})
        responses.append(types.FunctionResponse(id=fc.id, name=fc.name, response=result))
    await session.send_tool_response(function_responses=responses)


async def _relay_gemini(ws: WebSocket, mic: asyncio.Queue, state: CallState, client):
    """Keeps one logical conversation alive across Gemini connections using session resumption.
    https://ai.google.dev/gemini-api/docs/live-api/session-management"""
    quick_drops = 0
    while True:
        # handle=None on the first connection still switches on resumption updates.
        config = {**CONFIG, "system_instruction": agent.system_prompt(),
                  "session_resumption": types.SessionResumptionConfig(handle=state.resume_handle)}
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
    if store.configured() and not auth.ws_required():
        await ws.close(code=1008, reason="Set up Google sign-in or KOE_ACCESS_TOKEN in backend/.env before enabling browser writes.")
        return
    if auth.ws_required():
        try:
            first = await asyncio.wait_for(ws.receive_json(), timeout=10)
            owner = auth.ws_owner(first.get("token")) if isinstance(first, dict) and first.get("type") == "auth" else None
            if not owner:
                raise ValueError("Unauthorized")
            identity.OWNER.set(owner)  # the call's activity, approvals and tools are this person's
        except (ValueError, asyncio.TimeoutError, WebSocketDisconnect):
            await ws.close(code=1008, reason="Sign in to Koe again.")
            return
    client = genai.Client(api_key=settings.gemini_api_key)
    state = CallState()
    mic: asyncio.Queue[bytes | str] = asyncio.Queue()
    try:
        # The browser side lives for the whole call; the Gemini side may reconnect underneath it.
        # If either fails (e.g. user hangs up), the other is cancelled.
        async with asyncio.TaskGroup() as tg:
            tg.create_task(_save_activity(state))
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
