# Calendar extension contract — 2026-10-14

Next backend phase after approved schema/row edits. Frontend source stays unchanged; the frontend handoff will receive the final contracts. The owner handles Render. No new dependency, provider secret, model or OAuth scope is needed.

## Thin slices

1. **Bounded event plans:** optional `all_day` uses YYYY-MM-DD with an exclusive end. Optional `recurrence` is `{frequency:daily|weekly,interval:1..4,count:2..20}`; interval defaults to1. Python generates every occurrence, a canonical RRULE and exact dates for approval. Only creation supports recurrence; existing recurring-series/instance moves remain refused. At most90 days through the final end and31 days per individual event. Recurring timed windows spanning a UTC-offset transition are refused rather than guessing provider expansion. No raw RRULE, unbounded recurrence, monthly rules or “this and following” edits.
2. **Meet and event reads:** optional `create_meet:true` requests a unique Google Meet using the persisted approval UUID, `conferenceDataVersion=1` and `hangoutsMeet`. Never reuse another event's conference. Account support is decided by Google; conference creation can remain pending or fail after the event itself is created. Return a separate conference status and only an actual HTTPS meet.google.com URL. Read-only `calendar_get_event(event_id)` retrieves etag, instance/series identity, attendees and current conference status. No automatic mutation retry/polling loop.
3. **Safe cancellation:** `calendar_cancel_event(event_id,expected_etag,scope)` requires an exact read version and explicit `single`, `instance` or `series`. Preflight reads the event, validates scope, previews actual title/times/attendees/recurrence and freezes destination/timezone/version. Approval rereads, checks scope/version and sends DELETE with If-Match/sendUpdates=all. An instance ID is never silently promoted to its whole series. A series cancellation removes the entire series, including past occurrences; it is not “this and following”.
4. **Shared gate and display:** all Calendar proposals freeze configured calendar/timezone. Moving an individual event also freezes the read etag. Exact optional values, dates and guest-notification behavior appear in the summary. At execution recheck every planned occurrence against a complete bounded event read, ignoring only the moved event. Call projections expose bounded Calendar plan/conference/cancellation data; executed cancellations invalidate dashboard availability. Text confirmations distinguish a cancelled event from a rejected proposal and a pending Meet from a ready link.

## Bounds and failure semantics

Calendar operations have a45-second total budget including lock/credential work; event scans have30 seconds, at most10 pages and1000 expanded events, with repeated-page-token detection. Requests have20-second timeouts and a4 MB response cap; TLS setup/credential lookup run off the audio event loop. Invalid/incomplete evidence fails closed. Conflict checks are optimistic: Google has no atomic insert-if-free transaction; another organizer can race after the final read. If-Match protects updates/deletes, not concurrent bookings. Cancelled/transparent/self-declined events don't block slots.

No retry after an uncertain effect. Provider rejection, unsupported Meet, pending/failure conference state, stale etag, invalid scope, partial attendee data or oversized cancellation previews must remain truthful errors/states. Only regular `eventType=default` events are changed through this phase. Recurring instances and series can be read/cancelled, not moved/rewritten. Existing reminder/detail omission and explicit clearing semantics remain compatible.

## Verification gates

- Failing tests for typed recurrence/date bounds, exact RRULE/preview, all-day exclusive end and DST refusal.
- Conflict at a later recurrence, adjacent slots and scan/page/deadline limits; no write with incomplete evidence.
- Stable unique Meet request, provider pending/success/failure, unsafe URL refusal and no request replay.
- Full persisted proposal → JSON roundtrip → explicit approval → execution for new creation/cancellation; wrong context/version/scope, destination changes, duplicate decisions and internal-argument injection refused.
- DELETE204, If-Match412, cancelled/missing/malformed events, guest notification behavior, uncertain transport failure.
- Call projection and deterministic text result tests. Full backend regression suite and SDK declaration serialization. No real invitations/bookings/cancellations during verification.

## References

- [Events insert and fields](https://developers.google.com/workspace/calendar/api/v3/reference/events/insert).
- [Conference status](https://developers.google.com/workspace/calendar/api/v3/reference/events).
- [Recurring instances and series](https://developers.google.com/workspace/calendar/api/guides/recurringevents).
- [Delete](https://developers.google.com/workspace/calendar/api/v3/reference/events/delete).
- [Conditional modifications](https://developers.google.com/workspace/calendar/api/guides/version-resources).
