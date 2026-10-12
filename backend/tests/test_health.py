import os

os.environ.setdefault("GEMINI_API_KEY", "test")  # tests never need the real key

from fastapi.testclient import TestClient  # noqa: E402

from koe.main import app  # noqa: E402


def test_health():
    assert TestClient(app).get("/health").json() == {"ok": True}
