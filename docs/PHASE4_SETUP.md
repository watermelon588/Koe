# Phase 4: connect when you have time

The code can be tested without account credentials. Live summaries need GitHub and Gemini; live writes additionally need the services below. Keep secrets in `backend/.env`, never in chat or frontend `VITE_*` variables. No new paid service or dependency is required.

## GitHub

Set `GITHUB_TOKEN`, `GITHUB_REPOS=your-name/your-repo` and `GITHUB_LOGIN=your-name`. Use a fine-grained token restricted to those repositories: Contents **read** for commits, Pull requests **read** for summaries; enable Pull requests **write** only when you want approved PR comments. The [comment endpoint](https://docs.github.com/en/rest/issues/comments#create-an-issue-comment) accepts Pull requests write (or Issues write). Metadata access is included by GitHub. Do not grant administration access; Koe has no merge tool.

`github_shipped` searches authored merged PRs and authored commits on each repository's default branch, from local midnight (or Monday for this week) until the read begins. These lists overlap; they are not billable-hours evidence. GitHub search indexing may lag. Searches and commit lists stop at 10 pages per repository and report partial results when capped/incomplete. A failure does not become an empty success.

PR summaries use the existing `GEMINI_API_KEY` and `GEMINI_TEXT_MODEL`. They analyze at most 30,000 UTF-8 bytes of source JSON, report omitted patches/truncation and identify the head SHA. Risk notes are AI inferences; they are not test results or a merge decision.

## Notion daily log

1. Create a database called **Koe Daily Log** with one title column (any name) and a **Date** column of type Date. Keep it for your own log.
2. Create an internal Notion integration/connection with read, insert and update content capabilities. In the database's Connections menu, connect that integration.
3. Put its token into `NOTION_TOKEN` and database ID into `NOTION_DATABASE_ID`. The ID is the UUID in the database URL; omit URL query parameters.
4. If the database has several data sources, set `NOTION_DATA_SOURCE_ID` explicitly from the [retrieve database API](https://developers.notion.com/reference/retrieve-a-database) response. Otherwise Koe resolves its single source automatically. Data sources have their own IDs; they are different from database IDs.

Koe queries Date before creating a daily page and appends plain-text bullets. Exact repeats are skipped. It never replaces existing content. Two pages for the same date cause a setup error. Run **one backend worker** so concurrent log requests serialize. After an uncertain timeout, check Notion before asking to write again; external writes cannot share a transaction with Supabase. API version: `2026-03-11` ([versioning](https://developers.notion.com/reference/versioning)).

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

Restart the backend after changing `.env`. Apply Phase 2's Supabase migration and set `SUPABASE_URL`, `SUPABASE_SECRET_KEY`, `KOE_ACCESS_TOKEN` before testing approvals. No additional Phase 4 migration is needed.

- “Summarize PR 42 in your-name/your-repo.”
- “What did I ship today?” — reads GitHub, then writes the factual Notion daily log; errors/partial history remain visible.
- “Comment on PR 42 in your-name/your-repo: please add a regression test.” — inspect the full preview, then approve or cancel.
- “Log 1.25 hours for Client A on 2026-10-13, note: fixed the login race.” — inspect the destination, hours and note, then approve or cancel.

Use your test repository and test spreadsheet for the first checks. PR comments notify real people; approve only an intended comment. The implementation has been verified against fake APIs; real account acceptance remains pending until you connect them.
