# Spotify verification report — 15 October 2026

Latest verification: approximately 15:00 IST. **Verdict: automated regressions and available live preflight checks pass; authenticated live Spotify acceptance is blocked, not passed.**

The user configured the developer app and environment, then requested rigorous verification. This report distinguishes fresh results from earlier simulated integration coverage. No Spotify account playlist or playback changes were made in this run, and no hosted migration was applied.

## Results from this verification run

| Area | Result | Evidence and limit |
|---|---|---|
| Spotify credentials | PASS after correction | Initial configured Client ID had 37 characters and Spotify returned HTTP 400 `invalid_client`. The user corrected it locally. A fresh client-credentials grant then returned HTTP 200 with a token. Token values and secrets were never printed or saved in the report. This validates the credential pair, not user consent, Premium or SDK streaming. |
| Exact callback/origin | PASS | Spotify callback is `http://127.0.0.1:5173/auth/spotify/callback`; local origin is `http://127.0.0.1:5173`. Configured callback validation and origin comparison pass. Registration inside Spotify's dashboard still requires successful user authorization to verify end to end. |
| Encryption configuration | PASS | Existing encryption key meets the 32-character minimum; its value was not displayed or changed. |
| Live Neon connectivity | PASS | Read-only transaction connects successfully; `transaction_read_only=on` verified. The initial probe used a startup option unsupported by the pooler. The checker was corrected; that initial failure was not an established database outage. |
| Live Spotify schema | BLOCKED | `koe_spotify_flows` and `koe_music_mutations` are absent. The existing provider constraint does not allow Spotify. Existing users, sessions, connections, prefs and usage tables are present. Migration 007 is prepared and previously tested, but hosted execution was rejected by automatic approval review and is awaiting explicit user approval. |
| Google callback | PASS on fresh retry | First real browser redirect returned `redirect_uri_mismatch`. After the user confirmed the URI was registered, a fresh flow reached Google's normal sign-in page for the configured existing OAuth app, labelled Tripverse. |
| Completed Koe owner session | NOT VERIFIED | The user reported signing in. The last observed automated test tab remained at Google's password challenge and had not returned to Koe. No password field contents were read, and no credentials were requested in chat. A completed owner session is still necessary. |
| Live signed-out authorization | PASS: 10/10 | GET status, playlists, playlist items, search and mutation inspection were tested without credentials and with the configured development bearer token. Every request returned HTTP 401 `spotify_sign_in_required`, `Cache-Control: no-store`, and contract version 1.0.0. A bearer token does not bypass owner-cookie requirements. |
| Test-route separation | PASS: 3/3 | Real backend GETs for `/__e2e/state`, `/__e2e/demo` and `/__e2e/player.js` returned 404. The real frontend HTML did not inject the simulated SDK or contain the configured Spotify client secret. |
| Google OAuth start protections | PASS | HTTP 302 to accounts.google.com; exact local callback; PKCE S256, state and nonce present; flow cookie HttpOnly and SameSite=Lax; response no-store. |
| Backend regression | PASS: 479/479 | Full suite freshly rerun, no skips, 360.43 seconds. Includes 41 Spotify mocked tests and disposable PostgreSQL migration/journal/OAuth/RLS checks. One existing Starlette/httpx deprecation warning. |
| Diagnostic-tool regression | PASS: 1/1 | New focused test proves the preflight tool does not print/save Client ID, secret, access token or database error credentials, and does not use the rejected Neon startup option. This was a separate focused run after the 479-test full suite. |
| Frontend regression | PASS: 49/49 | Fresh full frontend suite, including audio ownership, persisted uncertainty, request-ID replay, SDK state/queue and timed-out resume barriers. |
| TypeScript and production build | PASS | `npm run build` completes successfully. Existing large-chunk advisory remains: main JS about 653 KB and mascot JS about 760 KB before gzip. |
| Lint | PASS with 4 existing warnings | No errors. Existing warnings in App, ChatPage, Connections and InstallPage; no new warnings from this work. |
| Frontend dependency audit | PASS | `npm audit --json`: zero reported info/low/moderate/high/critical vulnerabilities. |
| Syntax / whitespace | PASS | Diagnostic Python compilation, existing browser-fixture JavaScript syntax checks, and git diff whitespace checks pass. Git prints existing LF/CRLF notices. |

## Browser checks freshly exercised with simulated Spotify

These used the in-app browser at `127.0.0.1:5174`, the isolated SQLite fixture at port 8001 and a local fake SDK. They do not establish real Spotify playback.

- Explicit Play changes the UI to Pause and registers/targets the fixture player.
- Next selects Test track 2; Previous returns to Test track 1.
- Shuffle switches on and Repeat changes to context.
- Typed search returns Test track 4. Add preview names the track, destination and one-copy behavior before confirmation.
- Confirmed add, one-position reorder and remove-all each produced exactly one corresponding provider write. The playlist returned to three tracks afterward.
- Removal preview explicitly says every occurrence of the track will be removed.
- Reload while playing does not erase audio uncertainty. Call is blocked with the recovery message; the fixture records zero voice connections. Explicit Play and a later confirmed Pause restore the recoverable state.
- A second tab trying Play is refused with “Another Koe tab owns audio.” It does not start a competing player.
- A verified fixture-only pause fault keeps music playing and blocks Call with “Couldn’t confirm the music stopped”. Backend voice connection count stays zero. One browser wait exceeded its internal deadline; its diagnostics and the immediate accessibility snapshot both showed the expected error visibly present. The backend evidence confirmed the safety result.
- The pause fault was cleared, music was explicitly paused, and temporary test tabs were closed.

The earlier complete 15-scenario browser run remains documented in FRONTEND_STATUS.md and its ignored JSON report. It also covered OAuth callback/selection/disconnect, seek/volume, private creation, accepted write with lost response across reload, verified cross-tab voice handoff, recording/stored replies and the 375px layout. Those earlier results must not be presented as newly completed live Spotify tests.

## Live acceptance still required

1. Approve migration `backend/migrations/007_spotify_music.sql` for the configured hosted Neon database. It transactionally creates the two Spotify tables, widens the provider constraint, enables RLS and removes public privileges. Existing connection rows must be checked before and after. No broad migration replay is needed.
2. Finish Google owner sign-in in the automated in-app browser and return to Koe. Google flow cookies expire after ten minutes; start a fresh flow if the pending one expires. Sign-in in another browser does not establish a session in this test browser.
3. Complete Spotify authorization for the configured app and verify the returned owner identity, allowlist access and scopes.
4. Use a dedicated private test playlist for real search/create/add/reorder/remove and request-ID inspection. Preserve the user's existing playlists and selected playlist preference.
5. Verify actual SDK readiness/device registration, explicit transfer/play/skip/seek/volume/shuffle/repeat and confirmed local pause, then call/recording/reply handoff and no auto-resume. Test real playback uncertainty/reconnect/reload carefully without retrying sent writes.
6. Check SDK/Premium/browser behavior, real voice transport and physical mobile/background operation. None is established by client-credentials validation or fake-provider success.

Automatic review also rejected a proposed live POST/DELETE negative-authorization matrix because it could mutate hosted data. That matrix was not executed. The safer live GET matrix was completed, and mutation rejection remains covered by isolated tests. No authentication bypass, synthetic live owner session or copied browser cookie was used to avoid these boundaries.

## Runtime and artifacts

- The real local test frontend runs on `http://127.0.0.1:5173`, with backend port 8000. Spotify was enabled only in that controlled process so the normal `.env` default could remain false. The corrected Client ID was reloaded into that process.
- Separate simulated preview remains on 5174/8001 with a distinct session cookie and SQLite data. Its state is labelled TEST/no sound.
- `.env` credentials were not edited by the agent; the user corrected the Client ID. Hosted data was read only. No playlists were created, edited or deleted in the real Spotify account.
- Reusable read-only checker: `backend/scripts/check_spotify_setup.py`. Run from backend with `.venv/Scripts/python.exe -m scripts.check_spotify_setup`.
- Sanitized machine-readable evidence: ignored `backend/data/spotify-live-checks/preflight.json` and `http-security.json`.

Policy/setup context and real-device acceptance remain as described in the architecture. References checked against the official [Spotify profile API](https://developer.spotify.com/documentation/web-api/reference/get-current-users-profile), [development-mode access rules](https://developer.spotify.com/documentation/web-api/concepts/quota-modes), [SDK reference](https://developer.spotify.com/documentation/web-playback-sdk/reference) and [Developer Policy](https://developer.spotify.com/policy). No simulated result is a claim of Spotify policy approval.
