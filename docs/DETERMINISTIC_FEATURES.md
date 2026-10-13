# Deterministic integration features

Requested 2026-10-13. This checklist extends SPEC.md. Backend only; the existing UI is frozen.

## Contract

The LLM selects documented tools and extracts arguments. Python owns date boundaries, counting, typing, destination checks, API payloads, approval and execution. External content is untrusted data. Missing information is never fabricated. An incomplete read is reported as incomplete, never as zero or an exact total. No additional model, paid service or dependency is required.

Every Calendar, Sheets and Notion record/property change uses the existing persisted approval gate (the existing append-only daily log exception remains). Preview every changed field. Recheck the destination and schema before executing. Never automatically replay writes after timeouts. Keep old callers compatible through optional arguments. No real invitations, rows or pages are created during automated tests.

## Implementation order and acceptance

| ID | Feature | Feasibility / boundary | Status |
|---|---|---|---|
| G1 | Exact yesterday/date-range GitHub history | Selected repositories, authored default-branch commits, merged PRs; local-day boundaries and exclusive end | Implemented; synthetic tests pass |
| G2 | Counts by repository and total | Python deduplicates repository/SHA and PR numbers; commits and PRs are separate measures | Implemented; synthetic tests pass |
| G3 | Lines added/deleted/net changed | Opt-in commit detail reads, bounded concurrency and 50-commit cap; partial coverage explicitly reported; not total source LOC | Implemented; synthetic tests pass |
| G4 | Contribution calendar and streaks | GitHub contribution days, current/longest streak within a stated window; not a commit-only streak or lifetime claim | Implemented; synthetic tests pass |
| C1 | Event description and location | Optional validated strings; omission preserves existing fields when moving | Implemented; synthetic tests pass |
| C2 | Event notification reminders | Explicit minutes-before-start, popup/email, at most five; device delivery cannot be guaranteed | Implemented; synthetic tests pass |
| S1 | Discover actual timesheet headers | Read configured sheet only; validate unique headers and preserve required base columns | Implemented; synthetic tests pass |
| S2 | Fill optional existing columns | Named scalar fields, RAW input, leave unspecified cells blank in new rows; no arbitrary destination or formula execution | Implemented; synthetic tests pass |
| N1 | Discover editable Notion properties/options | Configured owner data source only; type and option validation; no arbitrary workspace traversal | Implemented; synthetic tests pass |
| N2 | Fill optional existing Notion properties | Text, finite number, checkbox, date, URL, email, select/multi-select/status; reserved workflow fields and computed results protected | Implemented; synthetic tests pass |
| C3 | Google Meet link creation | Unique new-event request; pending/success/failure separate from event save, actual links only | Implemented; see CALENDAR_EXTENSIONS.md |
| C4 | Recurring events / all-day creation / cancellation | Bounded daily/weekly creation, exclusive all-day dates, explicit versioned single/instance/whole-series cancellation | Implemented within documented bounds; series moves/monthly/unbounded rules excluded |
| S3 | Add optional columns / edit existing rows | Separate approvals; typed versions, stable row metadata, bounded scans and sparse literal edits | Implemented; see SCHEMA_ROW_EDIT_PLAN.md |
| N3 | Add new Notion properties | Additive schema approval; eight explicit types, existing schema/source checked and preserved | Implemented; see SCHEMA_ROW_EDIT_PLAN.md |
| N4 | Assign people / relations / advanced property schemas | Doable; verified user/page IDs and separate schema/type-specific contracts required | Queued |
| G5 | Additional branches and total repository source LOC | Doable; explicit branch/SHA, deduplication and generated/vendor file policy needed; expensive reads must be bounded | Queued |
| G6 | Commit-only streak / stars, forks, language and issue statistics | Doable; separate metric definitions and pagination/coverage tests | Queued |

Existing verified capabilities: PR/CI/review reads and PR summaries; approved PR comments; Calendar listing/free slots/individual booking and moving; approved timesheet entries; Notion daily logs and approved task/note/meeting-record save/archive.

Intentionally excluded: automatic PR merge/code push, guaranteed phone alarms, invented hours/attendee addresses, writing formula/rollup results, and claims of zero hallucinations or zero API latency.

## Verification gates

1. Add failing boundary tests before each implementation slice.
2. GitHub: timezone boundaries, exclusive end, duplicate evidence, pagination limits, permission failure, bounded line coverage, complete consecutive contribution dates and streak definition.
3. Calendar: exact approved reminders/details, omission versus explicit clearing, invalid values rejected before API access, overlap/version checks retained.
4. Sheets: real header mapping, unknown/duplicate/reserved columns rejected, RAW literal text, schema changes rejected before append.
5. Notion: actual property IDs/types/options, read-only/reserved protection, stale schema/page rejection and untouched unrelated properties.
6. Exercise the shared agent proposal → explicit approval → execution path with synthetic API responses; verify both Live and text use the same registry. Run the full backend suite before reporting completion.

## Using the implemented batch

- “What did I ship yesterday?” uses the exact previous local day, not yesterday through now.
- “Show yesterday's commits by repository, including lines added and removed.” uses `github_activity`; line details are opt-in, at most 50 commits with four concurrent reads and a 15-second detail budget. History has a 30-second total budget. Coverage flags accompany partial totals. Changed lines can include generated files and merge diffs; they are not unique source LOC.
- “What is my contribution streak for the last 30 days?” uses `github_contributions`. It follows GitHub's contribution day labels with UTC request bounds, not a reconstructed IST commit-only streak. Daily records are returned only when `include_calendar=true`. A streak reaching the window boundary is a lower bound; a one-day empty window cannot establish yesterday's streak and returns unknown.
- “Book a review tomorrow at 7 PM for 30 minutes, at the library, with a popup reminder 15 minutes before.” prepares exact event details/reminders for approval. Omitted fields preserve current/default settings; empty text clears a field and `reminders=[]` disables reminders.
- “Log one hour for Client tomorrow, Project Koe and Billable true.” reads `sheets_schema` and fills those optional headers if they exist after the five required columns. Up to 52 headers are inspected and 20 optional fields accepted; values remain RAW literals. `sheets_add_columns` creates missing headers after a separate approval. `sheets_find_rows` and `sheets_update_row` support an approved existing-row edit using verified identity/version; no user copies IDs or cell addresses manually.
- “Create a review task tomorrow with Priority High.” reads `notion_schema` and fills that existing property using its verified option ID, then asks for approval. Optional Notion values are limited to 20 supported existing properties. Text/number/date/URL/email/select can be cleared with null; checkboxes use false and multi-select uses []. Computed properties, people/relations and tracking overrides are not writable through this feature.

The existing chat and Live call use the same registry and persisted approval path. Every optional write value appears in the approval summary. UI layout, provider credentials, OAuth scopes and dependencies are unchanged. The 2026-10-14 phase adds `sheets_add_columns`, `sheets_find_rows`, `sheets_update_row` and `notion_add_properties`; schema creation and filling values have separate approvals. See [SCHEMA_ROW_EDIT_PLAN.md](SCHEMA_ROW_EDIT_PLAN.md) for exact types, bounds and concurrency limits.

## Evidence and remaining work

Latest phases, 2026-10-14: approved Sheets column creation, stable existing-row edits and additive Notion property creation passed **377 backend tests** plus real read-only schema/row probes ([SCHEMA_ROW_EDIT_PLAN.md](SCHEMA_ROW_EDIT_PLAN.md)). Subsequent Calendar extensions pass **424 backend tests**; contracts and evidence: [CALENDAR_EXTENSIONS.md](CALENDAR_EXTENSIONS.md). Standalone frontend assignment: [FRONTEND_BACKEND_HANDOFF.md](FRONTEND_BACKEND_HANDOFF.md). Work is published to GitHub at the user's request; Render rollout is handled by the user.

- Four implementation slices and a boundary-hardening follow-up are saved as separate local commits. Final verification: **334 backend tests passed**, with the existing Starlette/httpx deprecation warning. Synthetic tests exercise complete proposal → storage roundtrip → explicit approval → write, and reject replay for both optional Sheets and Notion values.
- Read-only acceptance succeeded against the configured GitHub, Sheets and Notion accounts: yesterday activity/count/line read (6.18 s), contribution calendar (4.02 s), Sheets header discovery (4.59 s), Notion property discovery (2.97 s). These are individual observations, not p50/p95 promises. No LLM quota or real writes were used.
- Remaining queued rows are Notion people/relations/advanced schema contracts and additional GitHub branch/LOC/statistic definitions. Meet creation and bounded recurrence/all-day/cancellation are implemented by the subsequent Calendar phase. Series moves, monthly/unbounded recurrence and “this and following” rewriting are explicitly excluded from its contract.
- Next write-acceptance step: the owner requests and approves one intended reminder or optional-field entry in the normal app. Synthetic approval tests verify execution and no replay without creating real test clutter.

## References

- [GitHub commits](https://docs.github.com/en/rest/commits/commits), [contribution data](https://docs.github.com/en/graphql/reference/users#contributionscollection).
- [Calendar event fields](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert), [reminders](https://developers.google.com/workspace/calendar/api/concepts/reminders).
- [Sheets values](https://developers.google.com/workspace/sheets/api/guides/values).
- [Notion properties](https://developers.notion.com/reference/page-property-values), [update page](https://developers.notion.com/reference/update-page).
