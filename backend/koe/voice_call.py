"""/ws/call: browser <-> Koe live audio.

Slice 1 (Phase 1): streams a test tone in Gemini Live's output format, so the
browser playback path can be proven before any AI is involved.
Gemini Live output = raw PCM16, 24 kHz, mono, little-endian (https://ai.google.dev/gemini-api/docs/live).
"""
import math
import struct

from fastapi import APIRouter, WebSocket

router = APIRouter()

OUT_RATE = 24000
CHUNK_SAMPLES = OUT_RATE // 25  # 40 ms per WebSocket message


def tone(freq=440, secs=1.0, volume=0.3) -> bytes:
    n = int(OUT_RATE * secs)
    return struct.pack(f"<{n}h", *(round(volume * 32767 * math.sin(2 * math.pi * freq * i / OUT_RATE)) for i in range(n)))


@router.websocket("/ws/call")
async def call(ws: WebSocket):
    await ws.accept()
    pcm = tone()
    step = CHUNK_SAMPLES * 2  # 2 bytes per sample
    for i in range(0, len(pcm), step):
        await ws.send_bytes(pcm[i : i + step])
    await ws.close()
