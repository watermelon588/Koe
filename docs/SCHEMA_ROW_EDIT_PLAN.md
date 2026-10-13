# Approved schema changes and Sheets row edits

Requested 2026-10-14. Backend only. Render deployment belongs to the user; UI stays frozen.

## Contract and order

1. **Sheets column creation:** `sheets_add_columns` proposes 1–10 new optional header names in the connected timesheet. Validate unique names and reserved base headers; freeze sheet ID, tab ID and current headers. Insert new physical columns after the existing headers and write literal header strings in one atomic Sheets batch. Existing cells, formatting and formulas shift with their columns rather than being overwritten. Verify the resulting headers. No renaming, deletion or arbitrary ranges.
2. **Sheets row discovery/editing:** `sheets_find_rows` reads the configured tab, returns bounded matches and a version of each row. `sheets_update_row` requires the exact existing Koe action ID and version, then previews every old/new value. Refuse missing/duplicate IDs, stale rows/headers, formula targets and tracking-field changes. At approval, recheck, attach/reuse a Google row metadata anchor, verify its actual row identity and version, then write only requested cells using a metadata DataFilter with RAW values and null skips. Reread to verify. Row numbers are display hints, never the durable edit identity.
3. **Notion property creation:** `notion_add_properties` proposes 1–10 new named properties with supported explicit types and select options. Freeze the configured source and schema. Recheck after approval; patch only new property definitions, never existing ones. Verify the response/retrieved schema. People, relations, formula, rollup, title and status schema creation are excluded from this slice.

All three writers use the existing persisted proposal → explicit approval → atomic claim → execution → recorded result path, shared by chat and Live calls. No model-supplied request IDs, snapshots, raw API objects, cell addresses or destinations. No automatic mutation retries. Disconnect/destination/source changes invalidate the proposal. New schema creation and row edits are separate approvals; neither silently includes the other.

## Bounds and concurrency

- Existing first five Sheets headers remain Date, Client, Hours, Note, Koe action ID. At most 52 named columns, 500 physical columns and 5000 data rows in the editable dedicated tab; refuse reads beyond bounds rather than claiming a complete identity scan. Discovery returns at most 20 matches and explicitly reports additional matches.
- Sheets API response bodies are streamed with a 4 MB cap. Row discovery returns at most 24 KB; long display strings are labeled truncated while versions still use complete typed cells. Requested old/new edit values are never silently truncated: oversized target cells/previews are refused and must be edited directly or split into smaller approvals. Each Sheets API operation has a 45-second budget, and TLS client construction/credential lookup stay off the voice event loop.
- Serialize Koe's Sheets append/schema/edit writers per spreadsheet/tab within this single-process backend. Row metadata follows structural row moves. Before/after fingerprints and identity checks reject detected stale changes.
- Google Sheets and Notion do not expose an atomic compare-and-set for these operations. An external edit in the short interval between the final read and write can still race. This implementation provides optimistic concurrency checks and stable addressing, not a distributed lock over human editors. Atomic Sheets batches keep each column insertion/header write together; partial multi-request updates are not claimed to be atomic.
- Existing formula cells are never editable through the row tool. Unrequested cells, formulas, formatting and tracking IDs are preserved. Existing rows without a unique stable action ID cannot be edited through Koe in this slice.
- Notion supports new rich_text, number, checkbox, date, url, email, select and multi_select properties. Types/options come from the user's explicit request; the model asks when missing. Select options have exact unique names. No implicit type conversion, option expansion or deletions.

## Verification

- [x] Column creation: exact preview, atomic literal header batch, destination/tab/header changes, reserved/duplicate names and preservation of existing columns. Nine new regressions first failed; 43 focused Sheets/tool tests passed. Uncertain-result cases are included in final review.
- [x] Row discovery: bounded full identity scan, duplicate IDs, actual typed cell data, versions and match limits; final review extends malformed-response coverage.
- [x] Row edits: approval/storage roundtrip, stale versions, moved rows, formula targets, protected fields, sparse RAW update and readback. Nine new regressions first failed; 52 focused Sheets/approval/tool tests passed. Final review extends uncertain/anchor coverage.
- [x] Notion properties: supported types/options, name/type validation, existing names, source/schema changes, owner restriction, exact additive patch, response verification and no replay. Twelve new regressions failed before implementation; 73 focused Notion/API/tool tests then passed.
- [x] Final full backend suite: **377 passed**, one existing Starlette/httpx deprecation warning, 128.69 seconds. All 21 SDK declarations validated/serialized. Git diff and credential scan found no frontend edits, exposed secrets, new dependencies or deployment changes. Read-only real-account probes passed; no actual mutations were used for acceptance.

## Examples

1. “Add Billable and Project columns to my timesheet.” Koe previews names/destination; Confirm inserts blank columns without filling any row.
2. “Find my Client entry from October 14.” Koe reads actual rows and resolves ambiguous matches with the user. “Change its hours to 1.5 and note to Release review.” The old/new preview identifies the record and requires Confirm. IDs/versions are handled internally.
3. “Add a Priority select property to Notion with High, Medium and Low options.” Confirm adds only that definition. “Set Priority High on my review task.” This is a separate approved value change.

The backend is saved locally; this build does not push, restart or deploy the application. The user handles Render rollout. No actual columns, metadata, row edits or Notion properties are created during automated verification. Read-only real-account probes succeeded for typed row discovery (3.29 s) and Notion schema identity (1.31 s); these are individual measurements, not percentile promises.

Final streamed row read and SDK serialization also passed (4.42 s combined, 578-byte tool result for the current sheet). Twelve review cases cover disconnected OAuth, API deadlines, malformed evidence, wrong anchors, uncertain writes, readback disagreement, internal-argument injection and oversized input/output. Real write acceptance remains an intended action approved by the owner in the app; synthetic adapter tests cover the complete approval flow without modifying their data.

## References

- [Sheets developer metadata](https://developers.google.com/workspace/sheets/api/guides/metadata).
- [Sheets batch update and collaboration semantics](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/batchUpdate).
- [Metadata value updates](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/batchUpdateByDataFilter).
- [Notion additive schema updates](https://developers.notion.com/reference/update-a-data-source).
