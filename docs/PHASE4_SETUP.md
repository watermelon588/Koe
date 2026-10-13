# Phase 4: connect when you have time

Schema/row extension (2026-10-14): Koe can now propose new optional Sheets columns, find and edit existing rows with stable IDs/versions, and add supported Notion property definitions. Each mutation has its own approval; see [SCHEMA_ROW_EDIT_PLAN.md](SCHEMA_ROW_EDIT_PLAN.md) for commands, supported types, bounds and concurrency limits. Existing Google/Notion credentials suffice. No manual cell addresses or ID copying is required by the user.

The implemented integration extensions and remaining work are tracked in [DETERMINISTIC_FEATURES.md](DETERMINISTIC_FEATURES.md). Existing connections suffice; no additional AI key or OAuth scope is required. Discover exact names with `sheets_schema` / `notion_schema`; create missing fields through a separately approved schema tool before proposing values. Every changed value appears in the existing approval summary.

The code can be tested without account credentials. Live summaries need GitHub and Gemini; live writes additionally need the services below. Keep secrets in `backend/.env`, never in chat or frontend `VITE_*` variables. No new paid service or dependency is required.

## GitHub

Set `GITHUB_TOKEN`, `GITHUB_REPOS=your-name/your-repo` and `GITHUB_LOGIN=your-name`. Use a fine-grained token restricted to those repositories: Contents **read** for commits, Pull requests **read** for summaries; enable Pull requests **write** only when you want approved PR comments. The [comment endpoint](https://docs.github.com/en/rest/issues/comments#create-an-issue-comment) accepts Pull requests write (or Issues write). Metadata access is included by GitHub. Do not grant administration access; Koe has no merge tool.

`github_shipped` searches authored merged PRs and authored commits on each repository's default branch. Today/this week run from local midnight/Monday until the read begins; yesterday stops at today's local midnight. Optional `until` is exclusive. These lists overlap; they are not billable-hours evidence. GitHub search indexing may lag. Searches and commit lists stop at 10 pages per repository and report partial results when capped/incomplete. A 30-second total deadline returns an error rather than a fabricated total. `github_activity` calculates counts and opt-in bounded changed-line totals in Python. `github_contributions` calculates contribution streaks within a stated calendar window, with daily rows opt-in. A failure does not become an empty success.

PR summaries use the existing `GEMINI_API_KEY` and `GEMINI_TEXT_MODEL`. They analyze at most 30,000 UTF-8 bytes of source JSON, report omitted patches/truncation and identify the head SHA. Risk notes are AI inferences; they are not test results or a merge decision.

## Notion workspace and daily log

1. Create or use your own Notion database with one title column (any name) and a **Date** column of type Date. It can hold daily logs, tasks, meeting records and notes together.
2. Create an internal Notion integration/connection with read, insert and update content capabilities. In the database's Connections menu, connect that integration.
3. Put its token into `NOTION_TOKEN` and database ID into `NOTION_DATABASE_ID`. The ID is the UUID in the database URL; omit URL query parameters.
4. If the database has several data sources, set `NOTION_DATA_SOURCE_ID` explicitly from the [retrieve database API](https://developers.notion.com/reference/retrieve-a-database) response. Otherwise Koe resolves its single source automatically. Data sources have their own IDs; they are different from database IDs.

5. Restart the backend, open **Notion** in the app navigation, and connect this device with your existing Koe access token if needed. Connection diagnostics show access/schema problems. If prompted, **Add missing properties** adds `Koe type` (select), `Koe status` (select), and `Koe action ID` (rich text), plus Date if missing. Existing fields are retained; incompatible types require fixing the schema yourself. This step has already succeeded for the current configured database.

Search/filter records, select one for its notes preview, or choose **New record** → Note/Task/Meeting → **Preview change** → **Confirm change**. Edits append additional notes and preserve existing blocks. Trash also requires a preview and is reversible in Notion. The Recent activity section shows persisted tool/approval outcomes. Pending workspace approvals survive a backend restart and cannot be confirmed by another chat/call.

Meeting records save a start/end range using your browser's local time. They do **not** reserve availability or invite anyone; ask Koe to book in Google Calendar for that. The preview supports top-level text/checklist blocks and labels nested/non-text content, with an **Open in Notion** link for full editing.

Koe queries Date and daily-log type (or the legacy daily-log title) before creating a daily page and appends plain-text bullets. Exact repeats are skipped. Two matching daily-log pages for the same date cause a setup error; tasks on that date do not. Run **one backend worker** so concurrent writes serialize. After an uncertain timeout, inspect Notion before proposing another write; metadata and notes can partially succeed, and external writes cannot share a transaction with Neon. API version: `2026-03-11` ([versioning](https://developers.notion.com/reference/versioning)).

## Optional free text fallback

Gemini remains the default. Later, save `OPENROUTER_API_KEY` in `backend/.env`, optionally set `OPENROUTER_MODEL=openrouter/free` (or a model ending `:free`), and restart the backend. Never put provider keys in frontend variables. On an initial Gemini 429/503, text chat can use that provider with the same tools and approval gate. It never switches providers after tools have started executing. Voice remains Gemini Live; free providers still have quotas. Without the optional key, the Notion workspace still works directly.

## Google Sheets hours

Use the **same Google Cloud project and OAuth desktop client** as Calendar. You do not need another API key.

1. In that Cloud project, open APIs & Services → Library → enable **Google Sheets API**. Calendar API remains enabled.
2. In Google Auth Platform → Data Access, add `https://www.googleapis.com/auth/spreadsheets` if your consent setup requires declaring scopes. Keep your account listed as a test user while the app is in Testing.
3. Keep the downloaded OAuth client file at `backend/credentials.json` (or `GOOGLE_CREDENTIALS_FILE`). From `backend/`, run:

   ```powershell
   .\.venv\Scripts\python.exe -m scripts.google_auth --with-sheets --reauthorize
   ```

   Sign in with your account and grant Calendar and Sheets access. This saves `token.json` locally; never commit it. Missing Sheets consent returns a setup error rather than opening a browser inside the server. See [Phase 2 setup](PHASE2_SETUP.md) for the full OAuth walkthrough and Testing-mode token expiry.
4. Create a spreadsheet with a tab named **Hours** and exactly these five cells in row 1:

   | A | B | C | D | E |
   |---|---|---|---|---|
   | Date | Client | Hours | Note | Koe action ID |

5. Set `GOOGLE_SHEETS_ID` to the part between `/d/` and `/edit` in its URL. Set `GOOGLE_SHEETS_TAB=Hours` (or your exact tab name). Your authorized account needs edit access.

Every row requires its own confirmation. The preview contains the full note and destination; changing that destination invalidates an existing proposal. The model cannot select a different sheet. Hours must be positive, at most 24, with at most two decimal places. Koe appends [RAW values](https://developers.google.com/workspace/sheets/api/reference/rest/v4/ValueInputOption), so text beginning with `=` stays text. The action ID is an audit field; it is not a Google idempotency key. Koe does not retry an uncertain append; check the sheet for that ID first.

## Try later, after setup

Restart the backend after changing `.env`. Apply Phase 2's Neon migration and set `DATABASE_URL`, `KOE_ACCESS_TOKEN` before testing approvals. No additional Phase 4 migration is needed.

- “Summarize PR 42 in your-name/your-repo.”
- “What did I ship today?” — reads GitHub, then writes the factual Notion daily log; errors/partial history remain visible.
- “List my Notion tasks.” / “Create a task to review PRs tomorrow.” — reads immediately; creating/updating/trashing waits for your confirmation.
- “Comment on PR 42 in your-name/your-repo: please add a regression test.” — inspect the full preview, then approve or cancel.
- “Log 1.25 hours for Client A on 2026-10-13, note: fixed the login race.” — inspect the destination, hours and note, then approve or cancel.

Use your test repository and test spreadsheet for the first checks. PR comments notify real people; approve only an intended comment. Notion acceptance passed against the connected real account using temporary records that were moved to trash afterward; GitHub/Sheets account acceptance remains separate. See [NOTION_PLAN.md](NOTION_PLAN.md) for coverage and limits.
