# Approved schema changes and Sheets row edits

Requested 2026-10-14. Backend only. Render deployment belongs to the user; UI stays frozen.

## Contract and order

1. **Sheets column creation:** `sheets_add_columns` proposes 1–10 new optional header names in the connected timesheet. Validate unique names and reserved base headers; freeze sheet ID, tab ID and current headers. Insert new physical columns after the existing headers and write literal header strings in one atomic Sheets batch. Existing cells, formatting and formulas shift with their columns rather than being overwritten. Verify the resulting headers. No renaming, deletion or arbitrary ranges.
2. **Sheets row discovery/editing:** `sheets_find_rows` reads the configured tab, returns bounded matches and a version of each row. `sheets_update_row` requires the exact existing Koe action ID and version, then previews every old/new value. Refuse missing/duplicate IDs, stale rows/headers, formula targets and tracking-field changes. At approval, recheck, attach/reuse a Google row metadata anchor, verify its actual row identity and version, then write only requested cells using a metadata DataFilter with RAW values and null skips. Reread to verify. Row numbers are display hints, never the durable edit identity.
3. **Notion property creation:** `notion_add_properties` proposes 1–10 new named properties with supported explicit types and select options. Freeze the configured source and schema. Recheck after approval; patch only new property definitions, never existing ones. Verify the response/retrieved schema. People, relations, formula, rollup, title and status schema creation are excluded from this slice.

All three writers use the existing persisted proposal → explicit approval → atomic claim → execution → recorded result path, shared by chat and Live calls. No model-supplied request IDs, snapshots, raw API objects, cell addresses or destinations. No automatic mutation retries. Disconnect/destination/source changes invalidate the proposal. New schema creation and row edits are separate approvals; neither silently includes the other.

## Bounds and concurrency

- Existing first five Sheets headers remain Date, Client, Hours, Note, Koe action ID. At most 52 named columns, 500 physical columns and 5000 data rows in the editable dedicated tab; refuse reads beyond bounds rather than claiming a complete identity scan. Discovery returns at most 20 matches and explicitly reports additional matches.
- Serialize Koe's Sheets append/schema/edit writers per spreadsheet/tab within this single-process backend. Row metadata follows structural row moves. Before/after fingerprints and identity checks reject detected stale changes.
- Google Sheets and Notion do not expose an atomic compare-and-set for these operations. An external edit in the short interval between the final read and write can still race. This implementation provides optimistic concurrency checks and stable addressing, not a distributed lock over human editors. Atomic Sheets batches keep each column insertion/header write together; partial multi-request updates are not claimed to be atomic.
- Existing formula cells are never editable through the row tool. Unrequested cells, formulas, formatting and tracking IDs are preserved. Existing rows without a unique stable action ID cannot be edited through Koe in this slice.
- Notion supports new rich_text, number, checkbox, date, url, email, select and multi_select properties. Types/options come from the user's explicit request; the model asks when missing. Select options have exact unique names. No implicit type conversion, option expansion or deletions.

## Verification

- [x] Column creation: exact preview, atomic literal header batch, destination/tab/header changes, reserved/duplicate names and preservation of existing columns. Nine new regressions first failed; 43 focused Sheets/tool tests passed. Uncertain-result cases are included in final review.
- [x] Row discovery: bounded full identity scan, duplicate IDs, actual typed cell data, versions and match limits; final review extends malformed-response coverage.
- [x] Row edits: approval/storage roundtrip, stale versions, moved rows, formula targets, protected fields, sparse RAW update and readback. Nine new regressions first failed; 52 focused Sheets/approval/tool tests passed. Final review extends uncertain/anchor coverage.
- [ ] Notion properties: supported types/options, name/type validation, existing/ambiguous names, source/schema changes, owner restriction, exact additive patch, response verification and no replay.
- [ ] Full backend tests, SDK declaration serialization, no frontend/secrets/dependency/deployment changes. Optional read-only real-account probes; no real writes during automated acceptance.

## Sources

- [Sheets developer metadata](https://developers.google.com/workspace/sheets/api/guides/metadata).
- [Sheets batch update and collaboration semantics](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets/batchUpdate).
- [Metadata value updates](https://developers.google.com/workspace/sheets/api/reference/rest/v4/spreadsheets.values/batchUpdateByDataFilter).
- [Notion additive schema updates](https://developers.notion.com/reference/update-a-data-source).
