from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from koe import app_channel, dashboard, github_hooks, voice_call, whatsapp
from koe.config import settings  # import = fail fast on missing config

app = FastAPI(title="Koe")
# The frontend on Vercel is another origin: allow only the configured ones, Bearer token in a header (no cookies).
# https://fastapi.tiangolo.com/tutorial/cors/
origins = [o.strip().rstrip("/") for o in settings.frontend_origins.split(",") if o.strip()]
if origins:
    app.add_middleware(CORSMiddleware, allow_origins=origins, allow_methods=["GET", "POST", "DELETE"],
                       allow_headers=["Authorization", "Content-Type"])
app.include_router(voice_call.router)
app.include_router(dashboard.router)
app.include_router(whatsapp.router)
app.include_router(github_hooks.router)
app.include_router(app_channel.router)


@app.get("/health")
def health():
    return {"ok": True}
