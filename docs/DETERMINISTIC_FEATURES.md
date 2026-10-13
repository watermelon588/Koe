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
| N1 | Discover editable Notion properties/options | Configured data source only; type and option validation; no arbitrary workspace traversal | Pending |
| N2 | Fill optional existing Notion properties | Text, finite number, checkbox, date, URL, email, select/multi-select; reserved workflow fields and computed results protected | Pending |
| C3 | Google Meet link creation | Doable; requires supported conference type, asynchronous result handling and exact proposal semantics | Queued |
| C4 | Recurring events / all-day creation / cancellation | Doable; separate series/instance approval, recurrence conflict checks and cancellation previews required | Queued |
| S3 | Add optional columns / edit existing rows | Doable; separate schema-change approval, row identity and concurrent-edit protection required | Queued |
| N3 | Add properties / assign people / relations | Doable; schema-change approval and verified user/page IDs required | Queued |
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

## Sources

- [GitHub commits](https://docs.github.com/en/rest/commits/commits), [contribution data](https://docs.github.com/en/graphql/reference/users#contributionscollection).
- [Calendar event fields](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert), [reminders](https://developers.google.com/workspace/calendar/api/concepts/reminders).
- [Sheets values](https://developers.google.com/workspace/sheets/api/guides/values).
- [Notion properties](https://developers.notion.com/reference/page-property-values), [update page](https://developers.notion.com/reference/update-page).
