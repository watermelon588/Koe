from fastapi import FastAPI

from koe.config import settings  # noqa: F401  (import = fail fast on missing config)

app = FastAPI(title="Koe")


@app.get("/health")
def health():
    return {"ok": True}
