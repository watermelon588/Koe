# Spotify frontend — current status

- Agent: Codex integration takeover. The user confirmed Plotcode stopped and explicitly assigned the remaining frontend work to Codex.
- Updated: 2026-10-15 (Asia/Kolkata).
- State: Implemented and integrated; isolated browser acceptance passed. Real Spotify remains disabled pending live acceptance. Nothing staged or committed.
- Consumed API contract: **1.0.0**, all status/auth/selection/read/search/edit/device/playback/journal routes.

## Delivered

Preserved the original Music page, app-level mini player, Settings entry, official app/web fallback and dev mock. Finished the SDK adapter, private playlist creation, typed search, preview-confirm add/remove-all/reorder, shuffle/repeat and recovery UI. A remove action explicitly removes all copies; previews freeze the playlist snapshot used for the write.

The SDK connects only after an explicit playback click and exclusive audio acquisition. `activateElement` runs directly in the click. Register the actual **Koe Web Player** device, transfer with play:false, confirm the target, then play the server-selected playlist. Transfer preserves playback state; it does not force pause. Null state, errors, unconfirmed writes and unsettled SDK commands remain unknown.

The SDK serializes commands. A final pause follows already-sent starts; timed-out SDK promises still block voice until they settle and a later pause is verified. Tokens stay in memory. Request IDs and exact pending mutation bodies survive reload in sessionStorage; status inspection never resends a write. Definitive not-sent evidence permits a new explicit action.

Calls, microphone voice notes and stored replies share the coordinator. Web Locks provide cross-tab ownership; BroadcastChannel requests a verified pause/release. No ACK or timeout is not permission. A durable localStorage generation marker preserves the audio barrier across reload/closed tabs. Only verified pause clears that generation. Voice takeover disposes the paused SDK device; resuming is an explicit Play. Unexpected SDK playback while voice owns audio interrupts voice. Recording interruption discards the note.

Guide and Privacy describe music, browser storage, token boundaries, uncertain outcomes and disconnect retention. Phone playlist headers wrap properly without compressing titles to a narrow column.

## Verification

- **49/49 frontend tests passed**, including coordinator, persisted evidence, intent replay and SDK command/barrier tests.
- `npm run build`: TypeScript and Vite passed. Existing large-chunk advisory remains.
- `npm run lint`: zero errors, four pre-existing warnings in App/ChatPage/Connections/InstallPage, no new warnings.
- Real Edge browser, Vite proxy, owner OAuth routes, real music routes and isolated SQLite: **15 scenario checks passed**, no uncaught browser errors. Simulated Spotify SDK/provider and voice transport; fake microphone and silent stored-reply audio.
- Scenarios: signed-out response; connect/callback; selection/reads; registration/transfer/play/skip/seek/volume/shuffle/repeat; typed search/add/reorder/remove-all; two-tab conflict and pause-before-call; no auto-resume; rejected pause; reload barrier/recovery; actual browser recording and stored reply gating; lost accepted write/reload/inspection with exactly one provider write; 375px layout; disconnect; private create/selection.
- The separate user-preview smoke test passed without OAuth/SDK response interception and with real Spotify requests blocked: entry/login/select/local SDK play/pause/phone layout.
- Reports/screenshots: ignored `backend/data/spotify-e2e-browser/`. Production build contains no test SDK/proxy routes.

## Acceptance limits

Live credentials, Spotify allowlist, Google/Spotify callback setup, hosted Neon migration and combined-app policy interpretation remain unresolved. No live account/data changes were made. Real streaming, real Gemini calls, physical mobile devices and mobile background behavior are not verified. Voice's AudioContext is created silently on the click to preserve activation; microphone/socket/output begin only after the barrier. An orphaned uncertain generation deliberately stays blocked rather than claiming disconnect or a released lock proves silence.

See [setup and ready local simulated preview](../../backend/SPOTIFY_LOCAL_SETUP.md). Backend questions are resolved in contract 1.0.0 and BACKEND_STATUS.md. Shared specification/build/decision notes are consolidated after takeover.

## Live verification follow-up — 2026-10-15

Fresh 49-test suite, build/typecheck and lint pass; npm audit reports zero vulnerabilities. Repeated browser checks verified manual playback/skip/shuffle/repeat, preview-confirm search/add/reorder/remove-all, two-tab refusal, reload uncertainty and failed pause blocking voice with zero fixture voice connections. Real frontend has no simulated SDK injection. Google accepts the canonical callback on fresh retry, but the last observed live test tab is still at Google’s password step. Live owner/Spotify authorization, actual streaming and voice/mobile acceptance remain incomplete. Full evidence and approval blockers: [live test report](LIVE_TEST_REPORT_2026-10-15.md).
