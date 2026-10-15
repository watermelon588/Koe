# Spotify backend — current status

- Agent: Codex.
- Updated: 2026-10-15 (Asia/Kolkata).
- State: Backend v1 implemented; remaining frontend completed here after the user confirmed its agent stopped. Integrated and isolated-tested. Live Spotify remains disabled pending acceptance. No staging, commit, branch switch or deployment.
- API contract: **1.0.0**, consumed by the full frontend. Paths and payload shapes remain frozen.

## Delivered

Session-bound one-time owner OAuth; real cookie/session/origin enforcement; encrypted token refresh/disconnect; reconnect status and preserved previous journal evidence; bounded private playlist selection/reads/search/create/add/remove-all/reorder; session-bound SDK registration and targeted manual playback; durable atomic sent claims, replay/body conflicts/capacity protection; encrypted intent/destination/result evidence; no-store errors and privacy/access-log filters. Optional configuration defaults off. SQLite schema and replay-safe 006/007 PostgreSQL migrations support Spotify without dropping old providers.

Provider calls stay outside the microphone/WebSocket/model path. No Spotify tools, voice commands or music data flows were added to agent, voice_call, text_agent or tools. Existing unrelated backend changes were preserved. QUOTA_EXCEEDED on HTTP 429 is distinguished from transient rate limits.

All v1 auth, status, playlist, search, SDK token, device, playback, mutation-inspection and disconnect routes are registered. Status is ErrorBody 401 for signed-out and 403 for invited non-owners. Items wrapper is final: Page<{position,track}> plus playlist. SDK name is **Koe Web Player**. Remove-all requires explicit confirmation. Transfer play:false preserves current playback state and must be inside the audio barrier.

## Verification

- Final full backend regression: **479 passed, no skips**, one existing Starlette/httpx deprecation warning, 381.46 seconds during concurrent browser/build work.
- Includes 41 Spotify mocked tests and disposable local PostgreSQL verification: all migrations replay twice with old providers and Spotify; real journal prepare/claim/replay; OAuth conditional consumption; journal preservation; RLS/public privileges through the PostgreSQL DB branch. Temporary PostgreSQL stopped by fixture cleanup.
- Final frontend: **49 tests**, build/typecheck and lint passed (four existing warnings).
- Integrated Edge browser: **15 checks**, no uncaught errors; real Vite/auth/music/storage routes and isolated SQLite, simulated Spotify provider/SDK and voice transport. Includes playlist edits/create, full controls, cross-tab handoff, unknown pause, reload barrier, microphone/stored reply gates, unknown write inspection without duplication, disconnect and 375px layout.
- Preview entry also verified without SDK/OAuth browser stubs and with real Spotify requests blocked. Test routes never enter koe.main; test SDK injection is dev-only and absent from production build.
- Compile/diff whitespace checks passed. Tests used isolated data and automatically approved local loopback execution because Windows sandbox blocks asyncio/browser sockets.

## Ready to try / remaining live acceptance

[Local simulated preview and exact setup instructions](../../backend/SPOTIFY_LOCAL_SETUP.md). Local preview runs on 127.0.0.1:5174 with fixture backend 8001; distinct test cookie and isolated SQLite. It cannot play real music or call Gemini.

Local Spotify client ID/secret/redirect were absent; the user has no developer app and received registration/allowlist/callback instructions. .env and existing encryption key remain untouched. Real setup uses the exact 127.0.0.1:5173 callback origin and Google sign-in configuration.

No hosted Neon migration or Spotify account action occurred. Live enablement still requires developer setup, owner session, hosted 006/007 schema acceptance, policy resolution for a manual player within a voice product, and controlled real-account/browser acceptance. Passing mocked/browser tests is not proof of policy permission or real streaming/mobile-background behavior.

Shared SPEC, architecture clarification, Guide, Privacy, BUILD_LOG and DECISIONS are consolidated. The original frontend ownership reservation ended when the user explicitly authorized takeover.

## Live verification follow-up — 2026-10-15

The user configured developer credentials and requested rigorous live verification. See [detailed live test report](LIVE_TEST_REPORT_2026-10-15.md). The corrected Client ID/secret pair is accepted by Spotify (HTTP 200); canonical origin/callback and encryption checks pass. Neon is reachable read only, but Spotify tables and provider widening are not applied. Automatic review rejected hosted migration execution pending explicit user approval. Google initially rejected the callback, then accepted a fresh flow; the last observed test tab remains at its password step, so owner-session/live Spotify acceptance is incomplete. No hosted mutation or real Spotify playlist/playback change occurred.

Fresh verification: full backend 479 passed, new diagnostic redaction test separately 1 passed, frontend 49 passed, build/lint passed with existing warnings, npm audit reports zero vulnerabilities, live GET authorization/test-route separation 13/13 passed. Selected simulated browser scenarios were repeated, including two-tab music refusal and rejected/reload-uncertain pause keeping voice connections at zero. Live write-negative tests were rejected by automatic review and replaced with read-only live checks plus isolated mutation tests.
