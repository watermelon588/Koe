from fastapi import FastAPI

from koe import dashboard, github_hooks, voice_call, whatsapp
from koe.config import settings  # noqa: F401  (import = fail fast on missing config)

app = FastAPI(title="Koe")
app.include_router(voice_call.router)
app.include_router(dashboard.router)
app.include_router(whatsapp.router)
app.include_router(github_hooks.router)


@app.get("/health")
def health():
    return {"ok": True}
