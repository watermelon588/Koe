import os

os.environ.setdefault("GEMINI_API_KEY", "test")

from fastapi.testclient import TestClient  # noqa: E402

from koe.main import app  # noqa: E402


def test_call_echoes_audio_bytes_unchanged():
    chunk = bytes(range(256)) * 5  # 1280 bytes = 40 ms of 16 kHz PCM16
    with TestClient(app).websocket_connect("/ws/call") as ws:
        for _ in range(3):
            ws.send_bytes(chunk)
            assert ws.receive_bytes() == chunk
