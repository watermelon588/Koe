import math
import os
import struct

os.environ.setdefault("GEMINI_API_KEY", "test")

from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

from koe.main import app  # noqa: E402


def test_call_streams_one_second_of_24khz_pcm16_le():
    chunks = []
    with TestClient(app).websocket_connect("/ws/call") as ws:
        try:
            while True:
                chunks.append(ws.receive_bytes())
        except WebSocketDisconnect:
            pass

    assert all(len(c) == 1920 for c in chunks)  # 40 ms of 24 kHz PCM16
    pcm = b"".join(chunks)
    assert len(pcm) == 24000 * 2  # 1 s
    samples = struct.unpack("<24000h", pcm)  # little-endian, like Gemini
    expected = round(0.3 * 32767 * math.sin(2 * math.pi * 440 * 6 / 24000))
    assert samples[6] == expected  # big-endian bytes would decode to garbage here
