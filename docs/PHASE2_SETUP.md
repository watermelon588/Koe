# Phase 2 setup: Neon and Google

The code can be tested against fakes without your credentials. Real use needs the steps below.
Do not paste passwords, keys, credentials.json, or token.json into chat. Keep them in the local files.

## 1. Neon (database)

1. Create a Free project in [Neon](https://console.neon.tech/), using AWS Singapore for the current India-based development setup. Only Postgres is required.
2. Click Connect and copy the PostgreSQL connection string. Preserve its SSL and channel-binding parameters. Pooled connections work for the runtime; direct connections can also be used for administrative migrations.
3. Add these values to `backend/.env`, preserving your other credentials:

   ```dotenv
   DATABASE_URL=postgresql://ROLE:PASSWORD@HOST/DATABASE?sslmode=require
   KOE_OWNER_ID=rohit
   KOE_ACCESS_TOKEN=YOUR-PRIVATE-DEVELOPMENT-APP-PASSWORD
   ```

4. From `backend/`, install dependencies and apply the additive schema:

   ```powershell
   uv sync
   uv run python -m scripts.migrate_store
   ```

   This creates four `koe_` tables and atomic approval functions. Re-running retains existing rows. The backend database role owns the objects; PUBLIC has no table or function privileges. RLS is enabled, but the owning backend role has implicit access. This is single-owner backend-only storage, not browser-accessible or multi-user RLS.

5. Generate a development app password if needed:

   ```powershell
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```

   Set it as `KOE_ACCESS_TOKEN`. Enter it into Koe for current local testing. This is distinct from the database password. The browser must never receive `DATABASE_URL`.

6. Verify without calling external write tools:

   ```powershell
   uv run python -m scripts.verify_neon_store
   ```

   This uses a fresh synthetic owner namespace, checks proposal/claim/finish, four simultaneous claims, replay, rejection, expiry and owner/conversation isolation, then removes only its synthetic rows. No meetings, messages or PR comments are created. For a fully local disposable PostgreSQL check, run `uv run python -m scripts.verify_store_sql` (PostgreSQL binaries required).

Manual token entry is temporary. Final owner-only provider sign-in and secure browser sessions are described in [AUTH_FLOW.md](AUTH_FLOW.md); they are not implemented by the storage migration. Existing local app chat, push subscriptions and voice files are retained and still require persistent backend disk.

[Connection instructions](https://github.com/neondatabase/website/blob/main/content/docs/get-started/connect-neon.md) · [Psycopg transactions](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)

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

For the current single-owner deployment, credentials and token files must be provided securely on the hosted backend too. A Desktop OAuth client is for this developer-managed connection. A public user-facing Connect Google flow later needs a Web OAuth client and HTTPS callback; Provider sign-in alone does not grant Calendar permissions or manage Google's provider refresh tokens for us.

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

In Koe enter your app access token, start a call, and request a meeting. The live call panel shows the real pending proposal with **Confirm / Cancel**, plus spoken or typed yes/no. The dashboard shows real data and approval cards; write controls remain bound to their original conversation.

## 4. Limits and recovery

- Neon Free currently offers 100 projects and 1 GB database storage per project; compute quotas still apply and compute scales to zero when idle. The first query after inactivity can be slower. Stay on Free and monitor quota usage. [Storage update](https://neon.com/blog/neon-free-plan-1-gb-per-project).
- The atomic database claim prevents two confirmations from executing the same action. PostgreSQL and Google cannot share one transaction: if Google succeeds but saving the final audit fails, check the calendar before doing anything else. A create uses a stable event ID derived from its approval ID. The app never automatically retries an uncertain write.
- If a process stops with an action in `executing`, it is not automatically re-executed. Inspect the calendar and database record before manually resolving/reproposing it.
- Approval expires after ten minutes and is scoped to its owner and original conversation. A new call does not silently inherit the previous call's proposal. Expired rows are marked on the next resolution/proposal; there is no cleanup scheduler in Phase 2.
- The final overlap check and one-process write lock protect Koe's own requests. Google offers no atomic “reserve this free slot” API; another app could create an event between the check and the write. We cannot claim a cross-application lock.
- SQL migration rollback: stop the app and retain the tables/data. To remove the API, revert the application change while retaining the database; if retiring the store, revoke any explicitly granted runtime-role privileges or drop only its functions after backup. The current backend role owns the objects, so revoking PUBLIC does not revoke owner access. Do not drop populated tables as a routine rollback.

## What to tell the assistant

Send **“Neon schema applied, DATABASE_URL filled, Google consent done”** when ready. No secret values are needed in chat. If something fails, share the error message with keys/tokens removed.


## Live dashboard (Phase 3)

Enter `KOE_ACCESS_TOKEN` in the home screen's password field and press **Connect dashboard**. This loads today's Calendar, your review queue and open PRs without opening the microphone or calling Gemini. Missing credentials show a setup message in the affected panel. The dashboard refreshes automatically every minute; manual refreshes are limited to once per 30 seconds across clients.

While a call is open, choose **Day** to inspect panels, approvals, activity and latency; **Chat** returns to the transcript. A proposal from the current call can be approved or rejected there. CLI/other-conversation proposals must be resolved in their original conversation. Disconnects keep the last received data clearly marked offline. The access token stays in component memory and is sent in the first WebSocket frame, never a URL or browser storage.

No extra environment variables, migration, dependency, account or paid service is needed for Phase 3. Live data still requires the corresponding Phase 2 account setup. The event hub currently requires a single backend worker.
