# Spotify local setup for Koe

Local browser origin: `http://127.0.0.1:5173`. Use this origin consistently for Google sign-in and Spotify; a localhost cookie is not shared with 127.0.0.1.

## 1. Register your Spotify app

Open [Spotify Developer Dashboard](https://developer.spotify.com/dashboard) using your existing Premium account. Choose Create app:

- Name: **Koe Personal**.
- Description: **Personal manual playlist controls in Koe, with music paused before voice calls.**
- Redirect URI: **http://127.0.0.1:5173/auth/spotify/callback**.
- If API choices appear, select Web API and Web Playback SDK.
- If Website is optional, leave it blank for local setup.

After creation, Settings → Users Management → Add new user: add your own Spotify account name and email. Settings also contains your Client ID and the option to view the Client Secret.

[App registration reference](https://developer.spotify.com/documentation/web-api/concepts/apps), [allowlist reference](https://developer.spotify.com/documentation/web-api/concepts/quota-modes), [redirect reference](https://developer.spotify.com/documentation/web-api/concepts/redirect_uri).

## 2. Store the settings locally

Edit the existing `backend/.env`. Add or update these keys without changing other settings:

```dotenv
SPOTIFY_CLIENT_ID=your_client_id
SPOTIFY_CLIENT_SECRET=your_client_secret
SPOTIFY_REDIRECT_URI=http://127.0.0.1:5173/auth/spotify/callback
KOE_LOCAL_URL=http://127.0.0.1:5173
SPOTIFY_ENABLED=false
```

Replace the two credential placeholders with the values from Spotify Settings. Keep the existing KOE_SECRET_KEY unchanged. The existing .gitignore excludes .env. Credentials belong in this local file, not frontend variables or chat. The assistant can verify presence without displaying values.

SPOTIFY_ENABLED stays false during setup. Registering an app does not by itself verify Spotify's treatment of a manual player inside a voice-assistant product. Combined live playback also requires the frontend's verified cross-tab audio handoff and controlled account/browser acceptance. The integrated test environment uses simulated Spotify and cannot play real songs.

## 3. Let Google sign-in return to the same local origin

In [Google Auth Platform → Clients](https://console.cloud.google.com/auth/clients), open the Web application client already used by Koe's GOOGLE_WEB_CLIENT_ID. Add this Authorized redirect URI and keep the existing entries:

```text
http://127.0.0.1:5173/auth/google/callback
```

If that client lists Authorized JavaScript origins, add `http://127.0.0.1:5173` there as well. Do not replace the client, secret, admin email, or encryption key. Koe's server-side OAuth flow uses the registered redirect URI.

## 4. Test when the integrated app is ready

The backend and remaining frontend implementation are integrated. The isolated browser run covers connect/callback, playback controls, preview-confirm playlist edits, two-tab handoff, reload safety, voice-note recording and stored replies. BACKEND_STATUS.md and FRONTEND_STATUS.md under docs/spotify record verification and live acceptance limits. Use the exact local origin above for live setup; sign in to Koe before connecting Spotify. Spotify routes require an owner cookie session, not the development access token alone.

Live database migrations are a separate acceptance step: this project currently has a Neon configuration. The 006/007 provider/schema migration was tested on disposable local PostgreSQL, but has not been applied to the hosted database. Browser test fixtures use isolated SQLite and do not modify your Neon data.

The official Spotify app/web fallback remains available without connecting Koe. Opening it does not verify playback or pause; pause external music manually before using voice.

References checked 2026-10-15. No Spotify app, user allowlist or Google console changes are performed automatically by this guide.

## Try the local simulated preview now

While the test servers are running, open [the integrated preview](http://127.0.0.1:5174/__e2e/demo). Choose the playlist if prompted, press Play, search for Test track 4, and preview/confirm edits. Call and voice-note transport are simulated; no real songs, Gemini calls or Spotify account changes occur. The playlist is labelled TEST and no sound.

To restart it, run these commands in separate PowerShell terminals from the project folder:

```powershell
cd backend
.venv/Scripts/python.exe tests/spotify_e2e_server.py
```

```powershell
cd frontend
$env:KOE_BACKEND='http://127.0.0.1:8001'
$env:VITE_BACKEND_URL=''
$env:KOE_SPOTIFY_E2E='true'
npm run dev -- --host 127.0.0.1 --port 5174 --strictPort
```

The fixture overrides settings before accessing storage, uses separate SQLite data and a separate session cookie, and blocks external backend provider calls. Its routes are never registered by koe.main. The Vite test SDK/proxy runs only with this explicit flag in development and is not added to production builds. Stop both terminals before returning to a normal local backend; clear the test environment flag in that frontend terminal.
