import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware

from koe import app_channel, auth, backend_status, connections, dashboard, github_hooks, voice_call, whatsapp, notion_api, people, store
from koe.config import settings  # import = fail fast on missing config
from koe import music_api, spotify_auth

# Show Koe's own INFO lines (latency stages, delivery failures) next to uvicorn's in the host logs.
logging.basicConfig(level=logging.INFO, format="%(levelname)s:     %(name)s: %(message)s")
@asynccontextmanager
async def lifespan(app):
    try:
        yield
    finally:
        await store.drain_background()


app = FastAPI(title="Koe", lifespan=lifespan)
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
app.include_router(notion_api.router)
app.include_router(auth.router)
app.include_router(spotify_auth.router)
app.include_router(music_api.router)
app.include_router(connections.api)
app.include_router(backend_status.router)
app.include_router(people.router)


@app.get("/health")
def health(response: Response):
    response.headers['X-Koe-Revision'] = backend_status.revision()
    response.headers['Cache-Control'] = 'no-store'
    return {"ok": True}
