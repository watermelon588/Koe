# Deploying Koe (声)

For now: the **backend on Render** (free, from `render.yaml`) and the **frontend on Vercel** (free, from `frontend/vercel.json`). Both get stable HTTPS URLs, and both redeploy by themselves on every push to `main`. Local development with a cloudflared tunnel is unchanged (last section).

```
phone / laptop ──https──▶ Vercel  (static app: https://<app>.vercel.app)
       │
       └──https + wss──▶ Render  (FastAPI: https://<backend>.onrender.com)  ◀── Meta + GitHub webhooks
```

## Render free tier: what to expect
Checked 2026-10-13 against https://render.com/docs/free:
- **It sleeps** after 15 minutes with no inbound HTTP or WebSocket traffic, and waking takes up to about a minute. The first request after a quiet spell is slow, and a webhook that arrives while it's asleep can time out (GitHub waits about 10 s and doesn't retry by itself).
- **The disk is wiped** on every deploy, restart and sleep. The app's chat history, voice notes and push subscriptions (SQLite in `backend/data/`) start empty again. Activity, approvals and memory live in Neon (`DATABASE_URL`), so they survive. The phone re-registers for notifications each time the Koe app opens.
- 750 free instance hours a month, which is enough for one service running all month.
- The free card-less plan is ₹0. Render's paid plans are not used.

## 1. Prepare the secrets (on the laptop)
You need values for these. Never commit them and never paste them in chat.

| Variable | Where it comes from |
|---|---|
| `GEMINI_API_KEY` | AI Studio (same as `backend/.env`) |
| `KOE_ACCESS_TOKEN` | Your app password (same as `.env`, or a new long random string) |
| `VAPID_PRIVATE_KEY` | `uv run python -m scripts.vapid_key` (from `backend/`). Generate it once and keep it, because changing it means turning notifications off and on again on the phone |
| `DATABASE_URL` | Neon (same as `.env`) |
| `FRONTEND_ORIGINS` | Your Vercel URL, e.g. `https://koe.vercel.app` (no trailing slash). Leave it empty until step 3 |
| `WHATSAPP_TOKEN`, `WHATSAPP_PHONE_NUMBER_ID`, `WHATSAPP_APP_SECRET`, `WHATSAPP_VERIFY_TOKEN`, `ALLOWED_WHATSAPP_NUMBERS` | Meta app (WhatsApp → API Setup, App settings → Basic → App secret) |
| `GITHUB_TOKEN`, `GITHUB_REPOS`, `GITHUB_LOGIN`, `GITHUB_WEBHOOK_SECRET` | Same as `.env` |
| `NOTION_TOKEN`, `NOTION_DATABASE_ID`, `GOOGLE_SHEETS_ID` | Same as `.env` |

Anything you don't use yet can stay empty; that feature then reports "not set up".

## 2. Backend on Render
1. Sign in at https://dashboard.render.com with GitHub (no card needed for the free plan).
2. **New → Blueprint**, then pick the `watermelon588/Koe` repo. Render reads `render.yaml`: one free Python web service, `koe-backend`, built from `backend/` with uv.
3. Render asks for every `sync: false` variable **once**, at this step. Fill them in from the table above. To change them later, use the service's **Environment** page.
4. **Google (Calendar/Sheets):** on the service's **Environment** page, under **Secret Files**, add two files named exactly `credentials.json` and `token.json`, and paste in the contents of the files in `backend/`. Render places secret files in the service's root directory (`backend/`), which is where Koe looks. If Google says consent expired (Testing-mode tokens last about 7 days), run `uv run python -m scripts.google_auth --reauthorize` on the laptop and paste the new `token.json`.
5. Wait for the deploy, then open `https://<backend>.onrender.com/health`. It should show `{"ok":true}`. That's your **backend URL**.

## 3. Frontend on Vercel
1. At https://vercel.com, use **Add New → Project** and import the repo. Set **Root Directory** to `frontend` (`vercel.json` handles the rest).
2. Under **Environment Variables**, set `VITE_BACKEND_URL` to the backend URL from step 2 (no trailing slash). Then deploy.
3. Back on Render, set `FRONTEND_ORIGINS` to the Vercel URL. Render redeploys, and from then on the browser is allowed to call the backend (CORS).

## 4. Webhooks (stable URLs now)
Open `/health` first so the backend is awake. Meta checks the URL immediately.
- **Meta (WhatsApp → Configuration → Webhook):**
  - Callback URL: `https://<backend>.onrender.com/webhooks/whatsapp`
  - Verify token: the exact value of `WHATSAPP_VERIFY_TOKEN`
  - Then subscribe to the `messages` field.
- **GitHub (repo Settings → Webhooks → Add):**
  - URL: `https://<backend>.onrender.com/webhooks/github`
  - Content type: `application/json`
  - Secret: `GITHUB_WEBHOOK_SECRET`
  - Events: Workflow runs, Pull requests, Pull request reviews.

## 5. Phone
1. Open the Vercel URL in Chrome.
2. Go to **Settings**: enter `KOE_ACCESS_TOKEN`, then **Install app**, then turn on **Notifications**. If notifications were turned on earlier against the laptop, turn them off and on once, because the push key changed.
3. Go to **Chat** and send a voice note.

## 6. Google sign-in and Connections
Sign-in replaces the access token (ACCOUNTS_SPEC.md). Connections lets each person link their own Google Calendar and Sheets.
1. **Google Cloud** (the project that owns the *Web application* OAuth client):
   - Redirect URIs: `https://koe-pi.vercel.app/auth/google/callback` and `http://localhost:5173/auth/google/callback`.
   - **Enable the APIs:** Google Calendar API and Google Sheets API.
   - Consent screen: Privacy `https://koe-pi.vercel.app/privacy`, Terms `https://koe-pi.vercel.app/terms`. Add yourself, and later friends, as **test users**.
2. **Render → Environment**, using the same values as `backend/.env`:

   | Variable | Value |
   |---|---|
   | `GOOGLE_WEB_CLIENT_ID`, `GOOGLE_WEB_CLIENT_SECRET` | from the downloaded client JSON |
   | `KOE_ADMIN_EMAIL` | the owner's Gmail |
   | `KOE_PUBLIC_URL` | `https://koe-pi.vercel.app` |
   | `KOE_SECRET_KEY` | **exactly the value in `.env`**: both read the same Neon tokens; a different key can't decrypt them |
3. Vercel already proxies `/api` and `/auth` to Render (`frontend/vercel.json`), so the sign-in cookie belongs to `koe-pi.vercel.app`.

Until these are set, the site keeps using the access token, so nothing breaks in the meantime.

## Updating
Push to `main`, and both Render and Vercel rebuild by themselves. The URLs stay the same.

## Local development with a cloudflared tunnel (unchanged)
```bash
# backend (from backend/)
uv run uvicorn koe.main:app --reload --port 8000
# frontend (from frontend/)
npm run dev
# public URL for webhooks (dev); the URL changes every run, so update the Meta/GitHub webhook URLs
cloudflared tunnel --url http://localhost:8000
```
To try the app on the phone from the laptop, tunnel the frontend instead: `cloudflared tunnel --url http://localhost:5173`. Vite proxies `/api` and `/ws` to the backend.
