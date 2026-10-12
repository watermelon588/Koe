"""/ws/call: browser <-> Gemini Live, relaying audio both ways.

Browser sends mic audio as 16 kHz PCM16 LE chunks; Gemini replies with 24 kHz PCM16 LE.
Gemini's server-side voice activity detection decides when you've stopped talking.
Live API (Python SDK): https://ai.google.dev/gemini-api/docs/live-api/get-started-sdk
"""
import asyncio
import contextlib
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from google import genai
from google.genai import types

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
CONFIG = {"response_modalities": ["AUDIO"], "system_instruction": SYSTEM_PROMPT}


async def _mic_to_gemini(ws: WebSocket, session):
    while True:
        pcm = await ws.receive_bytes()
        await session.send_realtime_input(audio=types.Blob(data=pcm, mime_type="audio/pcm;rate=16000"))


async def _gemini_to_browser(ws: WebSocket, session):
    while True:  # session.receive() ends after each model turn, so loop for the next one
        async for msg in session.receive():
            sc = msg.server_content
            if sc and sc.interrupted:
                # User talked over Koe: tell the browser to drop queued audio (barge-in).
                # https://ai.google.dev/gemini-api/docs/live-api/capabilities
                await ws.send_json({"type": "interrupted"})
            if sc and sc.model_turn:
                for part in sc.model_turn.parts:
                    if part.inline_data:
                        await ws.send_bytes(part.inline_data.data)


@router.websocket("/ws/call")
async def call(ws: WebSocket):
    await ws.accept()
    client = genai.Client(api_key=settings.gemini_api_key)
    try:
        async with client.aio.live.connect(model=LIVE_MODEL, config=CONFIG) as session:
            # Both directions run at once; if either fails (e.g. user hangs up), the other is cancelled.
            async with asyncio.TaskGroup() as tg:
                tg.create_task(_mic_to_gemini(ws, session))
                tg.create_task(_gemini_to_browser(ws, session))
    except* WebSocketDisconnect:
        pass  # user hung up
    except* Exception as eg:
        log.exception("call failed")
        with contextlib.suppress(Exception):  # the browser may already be gone
            await ws.close(code=1011, reason=f"Gemini error: {eg.exceptions[0]}"[:120])
