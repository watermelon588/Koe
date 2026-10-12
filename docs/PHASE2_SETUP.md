# Phase 2 setup: Supabase and Google

The code can be tested against fakes without your credentials. Real use needs the steps below.
Do not paste passwords, keys, credentials.json, or token.json into chat. Keep them in the local files.

## 1. Supabase (database)

1. Open [Supabase](https://supabase.com/dashboard), create/select a Free project, and choose a region near the backend you expect to host. Choose a database password and keep it in your password manager.
2. In the project Connect dialog copy **Project URL**. In **Settings → API Keys**, create/copy a backend **secret key** (`sb_secret_...`). The legacy `service_role` key also works. A publishable/anon key does not have the required database privileges.
3. Add these lines to **backend/.env**, preserving your existing Gemini/GitHub values:

   ```dotenv
   SUPABASE_URL=https://YOUR-PROJECT.supabase.co
   SUPABASE_SECRET_KEY=YOUR-BACKEND-SECRET-KEY
   KOE_OWNER_ID=rohit
   ```

4. In Supabase → **SQL Editor**, open a new query, paste the entire contents of `backend/migrations/001_phase2.sql`, and Run. It creates four `koe_` tables and restricted database functions. It is safe to re-run; it does not clear existing rows.
5. Generate a private **Koe app access token**, locally:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

   Save that generated value as `KOE_ACCESS_TOKEN` in backend/.env. Enter the same value into the password field on Koe's home screen before calling. This token is distinct from the Supabase key. Supabase secrets must never enter the browser.

We use Supabase's HTTPS REST API, so **no database connection string is required**. Tables have RLS enabled and no direct browser access. The backend service key bypasses RLS, so access is also checked at the application boundary. Supabase Auth login is a future UI/auth slice; Phase 2 keeps the app single-user and protects browser calls with the private token. The configurable owner namespace prepares the tables for an eventual Auth user ID without introducing multi-user behavior now.

[API key documentation](https://supabase.com/docs/guides/getting-started/api-keys) · [SQL function privileges](https://supabase.com/docs/guides/database/functions)

## 2. Google: one project and OAuth client for Calendar and Sheets

**An API key cannot authorize access to your private Calendar.** OAuth opens Google's consent screen; you approve access, and Koe saves a refreshable token. The Gemini API key remains separate.

1. Go to [Google Cloud Console](https://console.cloud.google.com/). In the project selector at the top, create a project named **Koe**, or select an existing project. Keep that project selected throughout these steps.
2. Go to **APIs & Services → Library**. Search for **Google Calendar API** and Enable it. You can also enable **Google Sheets API** in the same project now, or wait until Phase 4.
3. Open **Google Auth Platform → Branding**. If prompted, choose Get Started. Set app name **Koe**, your email for user support, and your email for developer contact.
4. Under **Audience**, select **External** for a personal Gmail account. Keep publishing status **Testing** and add the Google account you want Koe to use under **Test users**. Internal is only suitable when your Workspace organization supports it.
5. Under **Data Access**, add the scopes you intend to authorize:

   | Purpose | Scope |
   |---|---|
   | Read and create/move Calendar events | `https://www.googleapis.com/auth/calendar.events` |
   | Sheets, optional until Phase 4 | `https://www.googleapis.com/auth/spreadsheets` |

6. Open **Clients → Create Client**. Choose **Desktop app**, name it **Koe local**, and Create. Download the JSON file.
7. Rename the downloaded file to **credentials.json** and place it in **backend/**. Do not choose an API key or service-account credential. Desktop OAuth uses a local loopback redirect; no manually entered web redirect URL is needed for this client.
8. From a terminal in **backend/** run:

   ```powershell
   uv run python -m scripts.google_auth
   ```

   To authorize Calendar **and** Sheets together instead:

   ```powershell
   uv run python -m scripts.google_auth --with-sheets
   ```

9. The command opens Google's login/consent screen. Choose your test-user account and grant the requested permissions. It saves **backend/token.json**. Both files are ignored by Git. If Google displays an unverified-app warning, only continue after verifying that this is your own Koe project/client; do not bypass warnings for an unfamiliar app.

Google's **External / Testing** refresh tokens generally expire after seven days for these scopes. Reconnect with:

```powershell
uv run python -m scripts.google_auth --reauthorize
# Add --with-sheets if you want both permissions again.
```

For the current single-owner deployment, credentials and token files must be provided securely on the hosted backend too. A Desktop OAuth client is for this developer-managed connection. A public user-facing Connect Google flow later needs a Web OAuth client and HTTPS callback; Supabase login alone does not grant Calendar permissions or manage Google's provider refresh tokens for us.

[Google credential setup](https://developers.google.com/workspace/guides/create-credentials) · [Calendar scopes](https://developers.google.com/workspace/calendar/api/auth) · [Refresh-token expiration](https://developers.google.com/identity/protocols/oauth2#expiration)

## 3. Choose a calendar and verify the integration

`GOOGLE_CALENDAR_ID=primary` uses your primary calendar. For initial booking tests, create a separate **Koe Test** calendar in Google Calendar → Settings → Add calendar → Create new calendar. Copy its Calendar ID from Settings → Integrate calendar, and set it in backend/.env. This keeps test meetings apart from your real schedule.

From backend/:

```powershell
uv run python -m scripts.check_setup
uv run python -m scripts.chat
```

The setup check only reads configuration, the database and Calendar; it does not book or send invitations. In chat, try “What's on my calendar today?”, then “Find 30 minutes free tomorrow between 09:00 and 12:00.”

For an approved write, request an explicit slot on the test calendar, inspect the displayed title/time/attendees, then type **yes**. Type **no** to reject. If you want to invite someone, provide their exact email address; the app has no contact directory. The server re-checks overlaps before writing. Moving recurring events is deliberately refused in v1. Moving an event without specifying attendees preserves them, and may notify those existing attendees; the proposal says that they are kept.

Run the backend and frontend:

```powershell
# backend/
uv run uvicorn koe.main:app --reload --port 8000
# frontend/, in another terminal
npm run dev
```

In Koe enter your app access token, start a call, and request a meeting. The live call panel shows the real pending proposal with **Confirm / Cancel**, plus spoken or typed yes/no. The home dashboard's sample approvals remain mock data until Phase 3.

## 4. Limits and recovery

- Supabase Free currently includes 500 MB database storage, can pause for low activity over a week, and does not include automatic backups. Make regular exports; upgrading is not part of this phase. [Pricing](https://supabase.com/pricing) · [Pausing](https://supabase.com/docs/guides/platform/free-project-pausing)
- The atomic database claim prevents two confirmations from executing the same action. Supabase and Google cannot share one transaction: if Google succeeds but saving the final audit fails, check the calendar before doing anything else. A create uses a stable event ID derived from its approval ID. The app never automatically retries an uncertain write.
- If a process stops with an action in `executing`, it is not automatically re-executed. Inspect the calendar and database record before manually resolving/reproposing it.
- Approval expires after ten minutes and is scoped to its owner and original conversation. A new call does not silently inherit the previous call's proposal. Expired rows are marked on the next resolution/proposal; there is no cleanup scheduler in Phase 2.
- The final overlap check and one-process write lock protect Koe's own requests. Google offers no atomic “reserve this free slot” API; another app could create an event between the check and the write. We cannot claim a cross-application lock.
- SQL migration rollback: stop the app and retain the tables/data. To remove the API, revoke `service_role` EXECUTE on the four `koe_*` functions listed at the bottom of the migration, or drop those functions explicitly after backup. Do not drop populated tables as a routine rollback.

## What to tell the assistant

Send **“Supabase migration done, env filled, Google consent done”** when ready. No secret values are needed in chat. If something fails, share the error message with keys/tokens removed.


## Live dashboard (Phase 3)

Enter `KOE_ACCESS_TOKEN` in the home screen's password field and press **Connect dashboard**. This loads today's Calendar, your review queue and open PRs without opening the microphone or calling Gemini. Missing credentials show a setup message in the affected panel. The dashboard refreshes automatically every minute; manual refreshes are limited to once per 30 seconds across clients.

While a call is open, choose **Day** to inspect panels, approvals, activity and latency; **Chat** returns to the transcript. A proposal from the current call can be approved or rejected there. CLI/other-conversation proposals must be resolved in their original conversation. Disconnects keep the last received data clearly marked offline. The access token stays in component memory and is sent in the first WebSocket frame, never a URL or browser storage.

No extra environment variables, migration, dependency, account or paid service is needed for Phase 3. Live data still requires the corresponding Phase 2 account setup. The event hub currently requires a single backend worker.
