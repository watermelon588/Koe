import os

os.environ.setdefault("GEMINI_API_KEY", "test")  # tests never need the real key

from fastapi.testclient import TestClient  # noqa: E402

from koe.main import app  # noqa: E402


def test_health():
    assert TestClient(app).get("/health").json() == {"ok": True}


def test_cors_allows_only_the_configured_frontend(monkeypatch):
    import importlib
    from fastapi.testclient import TestClient
    from koe import main
    from koe.config import settings
    monkeypatch.setattr(settings, "frontend_origins", "https://koe.vercel.app/")
    app = importlib.reload(main).app
    c = TestClient(app)
    ok = c.options("/api/app/messages", headers={"Origin": "https://koe.vercel.app", "Access-Control-Request-Method": "GET",
                                                 "Access-Control-Request-Headers": "authorization"})
    other = c.options("/api/app/messages", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "GET"})
    assert ok.headers.get("access-control-allow-origin") == "https://koe.vercel.app"
    assert "access-control-allow-origin" not in other.headers
    monkeypatch.setattr(settings, "frontend_origins", "")
    importlib.reload(main)  # leave the module as the other tests expect it
