"""/ws/call: browser <-> Koe live audio.

Slice 2 (Phase 1): echo. The browser sends mic audio as 16 kHz PCM16 LE chunks
(Gemini Live's input format) and we send the same bytes straight back, proving
the capture path before Gemini is involved. Slice 3 replaces the echo with Gemini.
"""
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/call")
async def call(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            await ws.send_bytes(await ws.receive_bytes())
    except WebSocketDisconnect:
        pass
