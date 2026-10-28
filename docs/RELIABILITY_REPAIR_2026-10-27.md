# Reliability repair — 27 October 2026

The application defects identified by the October 26 audit have code fixes and regression coverage. Database connectivity recovered on the final retest; Google consent and Meta's WhatsApp account restriction still block those connected features. These changes have not been deployed.

## Changes

- Live calls load cold credentials in a worker thread with a ten-second wait budget. Initial transient connection failures get bounded retries; permanent setup failures stop immediately. An established session can recover only with its provider resume handle, preserving the no-replay rule for tool turns. Each upstream connection attempt has a fifteen-second handshake budget. Client close messages do not include provider exception details.
- Text generation tries the next configured model for transport failures within the existing total generation budget. The app's existing rules still decide whether an optional provider fallback is safe.
- Database reads have a ten-second application deadline, PostgreSQL queries use a transaction-local statement timeout, and shared database queues have five-second waits that accommodate a healthy cold handshake. Writes are not replayed. Storage outages return a sanitized HTTP 503 with Retry-After. Optional approval-preview hydration has a two-second budget so unavailable previews do not hold up the entire chat history.
- Google invalid-grant failures produce an explicit reconnect state without deleting credentials or falling back to another person's account. Settings has Check connection and Reconnect actions. The new authenticated `/api/connections/google/health` read distinguishes working access, missing connection, revoked consent and an unavailable check. Additional Docs permission remains a deliberate consent step.
- GitHub history scans independent branches concurrently through four shared read slots, retaining sequential pagination within each branch, existing SHA deduplication, partial-result reporting and the total read deadline.
- Landing service counts derive from the integration list. Guide reflects the six navigation pages, Music, owner-configured Notion and Google recovery. Mei uses the same display name in the 3D accessibility/loading UI while retaining the deployed model ID. React effect/render warnings are resolved.
- Three.js core, renderer and VRM code are split into reusable chunks. The largest generated JavaScript chunk is approximately 397 kB, down from the previous approximately 760 kB combined mascot chunk; the build no longer emits the large-chunk warning.

## Verification

- Frontend: 76 tests passed; lint completed without warnings; TypeScript and production build passed.
- Focused backend call/storage, Google recovery, transport fallback and GitHub history regressions passed. New tests were observed failing before their corresponding fixes.
- Final full backend suite: **653 passed** in 496.09 seconds. The only warning is the existing Starlette/httpx TestClient dependency deprecation. GitHub refresh/invite tests pass in the complete run. Machine-readable results are in `artifacts/qa-2026-10-26/repairs/backend-final.xml`.
- Production preview browser: the six-service count is correct, Mei's 3D model loads from the split production chunks, the accessible name says Mei, and the revised Guide renders. Captured console warning/error logs were empty. Evidence: `artifacts/qa-2026-10-26/repairs/production-mei.jpg`.
- `git diff --check` passed. Existing changes from the other GitHub authorization work were preserved; this task did not commit, push, migrate or deploy them.

## Live provider status

1. **Google:** the saved refresh grant returns `invalid_grant`; it must be reconnected by the account holder. The saved grant also lacks Docs and Drive-file scopes. Use Settings → Connections → Reconnect, then Enable Docs. Do not remove or silently replace the user's saved authorization. Google's [OAuth documentation](https://developers.google.com/identity/protocols/oauth2/web-server) describes invalidated refresh grants.
2. **WhatsApp:** Meta's read-only health response still reports sending blocked. The business/phone restriction needs resolution in Meta before actual delivery can pass. No messages were sent during verification.
3. **Neon/network recovered during the follow-up:** earlier probes timed out on every resolved IPv4 and IPv6 address. A later TLS-only probe succeeded on all six addresses. An immediate comparison then succeeded with the original configuration as well as each alternate negotiation mode, so this is evidence of recovered/intermittent connectivity, not proof that GSS negotiation was the cause. No database transport configuration or TLS protections were changed. The final live run passed database health, chat history, GitHub activity and Spotify reads. Keep observing the intermittent transport issue; the app now reports bounded, recoverable failures when it recurs.

The final actual `/ws/call` greeting returned 174,720 audio bytes, transcripts, latency and turn-complete events in approximately 16 seconds. The dashboard socket refreshed GitHub panels successfully; its Calendar panel correctly reported the invalid Google grant. Chat history returned successfully in approximately 11 seconds, versus approximately 62 seconds in the original audit. These measured results cover API/WebSocket transport, not physical microphone or audible playback acceptance.

The direct Gemini-only probe still exhausted its 30-second budget, but a subsequent greeting through the application's complete text/fallback loop passed in approximately 32 seconds with zero tool executions and no pending approval. This distinguishes raw provider availability from the application's working fallback path. The authenticated Google health endpoint returned HTTP 200 with `ready=false`, `reconnect_required=true` and a sanitized reconnect instruction.

The repair does not claim physical-phone installation/push/microphone acceptance, audible Spotify playback, a real provider write, fresh Google consent or hosted rollout. The earlier denial of browser access to the separate fixture origin was respected; it was not bypassed through another origin or automation surface.

## Evidence

Sanitized post-change provider results, WebSocket outcomes and both database transport probes are under `artifacts/qa-2026-10-26/repairs/`. The original audit is `artifacts/qa-2026-10-26/QA_REPORT.md`; it describes the earlier state and should be read together with this repair note.
