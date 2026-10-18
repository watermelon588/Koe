# Google Docs in Koe

## Connection
Enable Google Docs API and Google Drive API in the same Google Cloud project as Koe's existing Web OAuth client. Add `https://www.googleapis.com/auth/documents` and `https://www.googleapis.com/auth/drive.file` to the consent screen. Keep the existing `/auth/google/callback` redirect for each local/production origin; no new secrets or callback are needed. In testing mode, add each invited person's Google account as a test user.

In Koe, open Settings → Connections → Google Docs → Enable Docs. Consent to the additional permissions. Reconnecting upgrades the encrypted Google connection for the signed-in person; it does not change the app's sign-in scopes. Calendar and Sheets continue to work with their existing grants. Existing users must explicitly grant Docs permission; deployment cannot grant it for them. The optional local CLI supports `python -m scripts.google_auth --with-sheets --with-docs --reauthorize`.

## Agent workflow
The frontend and backend must both include Docs support. Settings detects a backend that omits `docs_ready` and asks for a backend update instead of repeatedly offering consent that the old server cannot process. Successful Docs consent returns `connected=docs`; the saved grant determines the button state. Reconnecting preserves previously granted scopes. Text, fallback and live voice sessions receive current connection metadata, and the agent can refresh it with `connection_status`.

- Ask “Create a Google Doc called Weekly update with this text …”. Review and confirm the exact title/content.
- Ask “Find my Koe documents” or search by title. This lists app-accessible Docs, not all Drive files. Paste a `https://docs.google.com/document/d/.../edit` link to work with another document you can access.
- Ask Koe to read a document. It returns tab names/IDs, plain-text body content and a revision. Headers, footers, drawings and comments are outside this text view. Pending suggestions are disclosed and must be resolved in Google Docs before editing through Koe. Large reads are marked truncated.
- Ask to append text or replace an exact passage. Koe reads first, asks which tab if ambiguous, then proposes the precise change. Every edit needs confirmation. A repeated passage is rejected rather than guessing which occurrence to change.
- Chat and voice use the same tools and approval gate. The live workspace shows previews, authoritative errors and saved links on desktop and phones.

## Reliability
Edits use Google's requiredRevisionId, not merge-based targetRevisionId, so collaborator changes invalidate the proposal. No automatic write retry. A timed-out write is uncertain: inspect the Doc before proposing again. Creation is two provider operations; if the blank document was created but text insertion was not confirmed, Koe returns its link and does not create another copy. Content is plain text; existing formatting outside the edited text is retained. Sharing, trashing, arbitrary formatting and Drive file management are not agent tools.

## Sources
- https://developers.google.com/workspace/docs/api/auth
- https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/get
- https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/create
- https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/batchUpdate
- https://developers.google.com/workspace/docs/api/reference/rest/v1/documents/request
- https://developers.google.com/workspace/drive/api/reference/rest/v3/files/list

## Verification
Automated integration tests use synthetic Google responses and isolated storage. Real Google consent, actual provider writes and live microphone/model tool selection require separate authenticated acceptance; do not interpret mocked tests as those checks.

No database migration or new runtime dependency is required. The existing durable approval store must be configured for writes. Deploy backend and frontend together; existing Google users then use Enable Docs to upgrade consent. Readiness in Connections reflects granted scopes, not a live API health check.


Automated checks completed on 2026-10-18: GitHub audit (80 checks); related backend suite (167), followed by the final Docs/Google rerun (41); frontend regressions and the added Docs workspace-state check; production build; desktop/375px Edge consent, preview, confirm, saved-link and cancellation flow. Existing lint warnings and mascot bundle advisory remain. Browser runner: `backend/tests/docs_ui_browser.mjs`, using an existing Playwright installation via KOE_E2E_NODE_MODULES. It runs an isolated preview on port 5188 and blocks external requests. Output screenshots/reports are ignored under backend/data/docs-ui-browser.
