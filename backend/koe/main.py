from fastapi import FastAPI

from koe import voice_call
from koe.config import settings  # noqa: F401  (import = fail fast on missing config)

app = FastAPI(title="Koe")
app.include_router(voice_call.router)


@app.get("/health")
def health():
    return {"ok": True}
