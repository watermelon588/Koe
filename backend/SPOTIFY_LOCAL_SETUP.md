# Spotify local setup for Koe — 2026-10-16

Use **http://127.0.0.1:5173** consistently. Google and Spotify cookies from localhost are not shared with 127.0.0.1.

## Current local state

The owner explicitly approved migration 007 and local enablement. It has been applied to Neon, both new tables have RLS enabled, and Spotify is accepted by the connection-provider constraint. Migration 006 was already present and was not rerun. The existing credentials, encryption key and other settings were retained. The application credentials grant returns HTTP 200; this verifies the app credentials, **not user consent or streaming**.

Ignored `backend/.env` now has `SPOTIFY_ENABLED=true` and `SPOTIFY_VOICE_APPROVED=true`, following the user's confirmation of written Spotify approval. Both flags default to false in the example configuration. The normal local backend runs at 127.0.0.1:8000, through Vite's 5173 proxy. No hosting settings or production deployment were changed. A later read-only check confirms the owner has connected Spotify. The saved playlist is public and therefore ineligible under Koe's private-playlist contract; this now returns to the chooser rather than an incorrect connection error. No playlist privacy or content was changed automatically.

## Connect and try it

1. Open [Koe Music](http://127.0.0.1:5173/app#music). Sign in to Koe with the owner's Google account on this exact origin.
2. Click **Connect Spotify**, use the Premium Spotify account allowed in the developer app, and accept its scopes.
3. Choose a private playlist you own. If none are listed, use **Create private playlist**, then **Confirm change**, or **Open selected playlist in Spotify**, make it private there, and return to **Refresh playlists**. Koe does not change privacy automatically. Press **Play** once after adding tracks and verify audible music in this browser. This activates browser playback. Confirm **Pause** works.
4. Click **Allow voice controls** for this playlist. Keep this Music window open; wait for **Voice controls connected**.
5. Click **Open voice agent** to open a separate window. Start **Call Koe**. Verify music pauses before microphone audio starts. Try “set volume to 30 percent,” “turn it down,” “play my playlist,” “pause the music,” “next track” and “previous track.”

Play/next/previous wait for Koe's spoken response to finish, end the call, release voice audio ownership, and then start the requested music. Ordinary hang-up never resumes music. A volume change while the player is inactive is saved for the next playback. Only the explicitly selected playlist is allowed; search and playlist edits stay manual. Disable voice controls to revoke permission immediately. After a disconnected service/restart, reopen Music and start a new call rather than repeatedly issuing an uncertain command.

Spotify streams through its official browser SDK; Koe does not download or control an extracted audio file. Its external Spotify app/web links remain available, but Koe cannot verify or pause music playing there. Pause that external audio yourself before a call.

## If consent or playback fails

In [Spotify Developer Dashboard](https://developer.spotify.com/dashboard), verify the existing app's exact redirect URI:

```text
http://127.0.0.1:5173/auth/spotify/callback
```

The Premium Spotify account must be allowed under the developer app's user management. The SDK requires Premium and user activation; development mode has additional account restrictions. Do not create a second app or rotate keys unnecessarily.

For Google sign-in, the existing Google Web client must allow:

```text
http://127.0.0.1:5173/auth/google/callback
```

If JavaScript origins are listed, include `http://127.0.0.1:5173`. Keep existing hosted entries and secrets. These console entries have not been automatically changed. Credentials belong only in ignored backend `.env`, never frontend variables or chat. Keep `KOE_SECRET_KEY` unchanged.

From `backend`, run `.venv/Scripts/python.exe -m scripts.check_spotify_setup` for a read-only setup report. Real consent, playback and microphone/device acceptance remain pending. The voice flag records the written approval the user confirmed; separating services/windows does not bypass Spotify policy.

## Reproduce the isolated pipeline

From `backend`, with an existing Playwright package directory and Edge installed:

```powershell
.venv/Scripts/python.exe -m scripts.test_music_pipeline --node-modules 'PATH/TO/node_modules'
```

This starts its own test backend on 8002 and Vite on 5176, runs manual OAuth/playback/edit and separate voice/music browser suites, then stops only those processes. Reports/screenshots are under `backend/data/spotify-e2e-browser` and `backend/data/spotify-voice-e2e-browser` (ignored). It uses isolated SQLite, a test cookie, simulated Spotify/SDK and simulated Gemini function selection. No real songs, account writes or speech recognition are claimed.

For interactive simulation only, start `tests/spotify_e2e_server.py` from backend, and Vite from frontend with `KOE_BACKEND=http://127.0.0.1:8001`, `VITE_BACKEND_URL` empty and `KOE_SPOTIFY_E2E=true`; use port 5174 with `--strictPort`. Open `http://127.0.0.1:8001/__e2e/demo` so the fixture redirects to the configured frontend. Clear the test flag before normal development. Fixture routes are never registered by the normal application.

[Voice pipeline and boundaries](../docs/spotify/VOICE_CONTROL.md), [current review](../docs/REVIEW_2026-10-16.md), [SDK setup](https://developer.spotify.com/documentation/web-playback-sdk/tutorials/getting-started), [redirect requirements](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri), [2026 development-mode migration](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide), [policy](https://developer.spotify.com/policy). References checked 2026-10-16.
