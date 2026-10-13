# Notion workflow completion — 2026-10-13

The user authorized implementation, workspace/navigation changes and reasonable model fallback choices. Calendar remains the authority for real availability, invitations and bookings. Notion records notes, tasks and meeting records; saving a Notion record never claims to reserve a Calendar slot.

## Audit

- Existing `notion_log(date, entries)` only appends daily bullets. It cannot list/read records, manage tasks or meeting notes, or show connection health and a preview.
- Agent tool results are visible only in generic activity. Navigation disappears in chat and is blocked during calls.
- Live database access works; Date and title properties now exist. Additional workflow properties are absent. No live records exist at the audit point.
- Daily-log queries must distinguish daily logs from other records on the same date. Read/write timeouts must disclose uncertain outcomes and never replay writes automatically.

## Capability map and build order

1. `notion-data`: shared bounded Notion client, schema inspection, scoped page listing/details and safe workflow writes. Existing daily log consumes shared schema rules.
2. `notion-agent`: register read/save/archive tools and bind mutations to the existing durable proposal/claim/finish gate. Log writes remain the existing low-risk own-log exception. New records bind the configured destination and idempotency ID; edits check the presented last-edited timestamp and never erase body content.
3. `notion-api`: authenticated status/list/detail/propose/decide routes. UI proposals have their own conversation; explicit action IDs restore pending UI proposals after restart. No arbitrary database IDs from the client.
4. `notion-ui`: dedicated Notion route, real list/detail preview, search/filter/pagination, new/edit/archive forms, explicit confirmation and honest operation states. Persistent navigation across Home/Chat/Notion/Settings; a call stays mounted while moving between workspaces.
5. `text-fallback`: optional OpenRouter free text/tool fallback before any tool has executed; direct workspace operations require no model. Voice remains Gemini Live. Missing keys are optional, never fabricated. No paid model routing.
6. `acceptance`: HTTP/API tests, agent approval tests, live isolated synthetic Notion record create/read/update/archive and daily-log deduplication, frontend tests/build, real desktop/mobile browser verification.

## Data contract

- Existing title property (any name), `Date` (date). Add only missing properties: `Koe type` (select: Daily log/Task/Meeting/Note), `Koe status` (select: Open/In progress/Done), `Koe action ID` (rich_text). Never change or remove existing user properties. Report incompatible schemas.
- One configured data source. Explicit source ID required for multiple sources. Every page detail/edit/archive verifies its parent source. Treat Notion text as untrusted data, never model instructions.
- Task/meeting/note create/update and trash require a full preview and explicit approval. Update metadata; body updates append a labeled revision rather than replacing/deleting existing blocks. Trash is reversible and never hard-delete.
- Meeting records require explicit start/end offsets with end after start. The Date property stores the range; this is documentation, not Calendar booking. A Calendar event URL can be included in notes after the Calendar operation succeeds.
- Create dedupes by durable approval ID; uncertain external outcomes are surfaced for inspection. No automatic POST/PATCH retry. Single backend worker remains required.
- Lists are bounded to 25 rows with a server-validated cursor; page block preview pagination is bounded and discloses truncation/unsupported blocks. Render text, never arbitrary HTML or an authenticated Notion iframe. Provide Open in Notion links.

## Verification references

- Notion `POST /v1/data_sources/{id}/query`, `GET/PATCH /v1/data_sources/{id}`, `POST /v1/pages`, `GET/PATCH /v1/pages/{id}`, `GET/PATCH /v1/blocks/{id}/children`; pinned API version 2026-03-11.
- [Query](https://developers.notion.com/reference/query-a-data-source), [schema update](https://developers.notion.com/reference/update-a-data-source), [page update](https://developers.notion.com/reference/patch-page), [append blocks](https://developers.notion.com/reference/patch-block-children).
- Existing `agent.prepare_write`, `agent.confirm`, `store.propose/claim/finish`, `app_channel.authorized`, hash route and CSS tokens are the implementation patterns.

## Acceptance

- [x] Read-only connection diagnostics explain missing token/access/schema.
- [x] Daily logs coexist with task/meeting/note records and skip exact repeats.
- [x] Agent and UI can read records; mutations wait for a preview and explicit confirmation.
- [x] Wrong database/page, changed destination, stale revision, expired/duplicate approval and uncertain writes fail safely.
- [x] Direct workspace remains usable when LLM quota is exhausted; optional fallback never replays tools.
- [x] Navigation, call controls, loading/empty/error states and mobile layout verified.
- [x] Live checks use uniquely labeled synthetic records and trash them afterward. No Calendar bookings, invites or messages to other people are created.

## Delivered and verified

231 backend tests and 12 frontend tests pass; production build passes. Desktop and 390px mobile browser checks covered listing, record preview, create preview, explicit confirmation and persistent Chat/Notion navigation against an isolated API fixture. No browser console errors or horizontal overflow. Existing lint warnings and the existing mascot bundle-size warning remain. Call continuity is verified by component ownership/code inspection; live microphone/audio continuity still needs a listening check.

`python -m scripts.verify_notion_workflow` passed against the configured real Notion database and Neon: additive schema, no write before approval, create/read/update with original notes retained, duplicate confirmation rejection, reversible trash, Meeting date range, Note, and daily-log exact-repeat deduplication. Temporary pages were moved to trash and isolated verification audit/approval rows removed. The missing Koe type/status/action ID properties were added; existing user properties retained.

Limits: one backend worker; one configured source; preview up to 500 top-level blocks with nested/non-text labels; append-only note revisions. Notion has no atomic conditional page update, so revision checks cannot eliminate edits racing from another Notion client. Metadata update and appended notes are separate requests: an error can mean partial success; inspect the record before proposing again. Neon and Notion cannot commit together. Approved external writes are never automatically retried.

OpenRouter free text fallback is implemented and covered by mocked tests, but inactive until the owner supplies `OPENROUTER_API_KEY`. No live OpenRouter verification or voice fallback is claimed. Direct workspace operations do not need any LLM key.

Live Gemini tool-selection verification (`scripts.verify_notion_agent`, synthetic responses only) returned 503 UNAVAILABLE. Conversational selection remains unverified with a live provider; registry, validation and approval execution are covered by tests. Rerun that read-only check when Gemini recovers. Private Notion contents were not transmitted by this check.

The daily-log coexistence filter uses at most two compound nesting levels, per [Notion filter limits](https://developers.notion.com/reference/filter-data-source-entries). The optional fallback follows [free routing](https://openrouter.ai/docs/guides/routing/routers/free-router) and [tool calling](https://openrouter.ai/docs/guides/features/tool-calling).


## Live workspace (2026-10-13)
Notion work now also appears in the app chat's and the call's live workspace (SPEC §2 "Live workspace"): a `notion_save`/`notion_archive` proposal as a pending record, the saved record re-read from `GET /api/notion/records/{id}`, and own daily-log appends with the exact entries and how many were new. Notion pages can't be framed (`X-Frame-Options: SAMEORIGIN`, measured), so there is no live view for Notion, only Koe's rendering plus **Open in Notion**.
