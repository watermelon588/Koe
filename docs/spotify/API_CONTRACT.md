# Koe Spotify API — v1

**Additive same-page Music extension:** `music_control.action=play_match` requires an artist and/or title copied from the user's request (each up to 200 characters). Selection runs outside AI context and yields generic `not_found`, `unavailable`, `ambiguous`, or queued playback. The Music socket may send `{type:'suggestion', query, state, connection_id, playlist_id}` to its authorized browser only. Matched commands include `position` and `snapshot_id`; play accepts optional `snapshot_id` and rejects a stale match before sending playback. Existing transport commands are unchanged. Manual Add is a deliberate direct action with the same durable mutation journal; no automatic missing-song writes.

Published 2026-10-15 by Codex. Version `1.0.0`. Paths and JSON below are frozen for frontend integration; implementation progress is in BACKEND_STATUS.md. Use same-origin cookie requests (`credentials: 'same-origin'`), `Content-Type: application/json`, and the browser's Origin for writes. Spotify routes require a real signed-in Koe owner session, including in development; bearer credentials alone are insufficient. All responses are `Cache-Control: no-store`, `X-Koe-Music-Contract: 1.0.0`. Do not cache music data/tokens or send it to AI, transcripts, activity, analytics, or push.

Live access is off by default. Backend settings: `SPOTIFY_CLIENT_ID`, `SPOTIFY_CLIENT_SECRET`, `SPOTIFY_REDIRECT_URI` (exact canonical Koe origin + `/auth/spotify/callback`), existing `KOE_SECRET_KEY`, and `SPOTIFY_ENABLED=true` only after policy/setup acceptance. HTTPS required except explicit `127.0.0.1`/`[::1]` loopback; `localhost` callbacks are rejected. `KOE_LOCAL_URL` optionally replaces the existing localhost development origin for all Koe sign-in/CSRF checks; configure it deliberately before using IP loopback. No automatic developer-console/account changes.

## Shared shapes

Additive extension published 2026-10-16: [approved voice transport](VOICE_CONTROL.md). Existing v1 paths and envelopes are unchanged. `status.capabilities.voice_control` is true only when Spotify is usable and `SPOTIFY_VOICE_APPROVED=true`; it does not itself grant a playlist.

| Method/path | Contract |
|---|---|
| `GET /api/music/voice-permission` | Owner cookie; `{available: boolean, enabled: boolean, grant: {connection_id, playlist_id} \| null}` |
| `PUT /api/music/voice-permission` | Owner cookie + Origin; `{enabled: boolean, connection_id, playlist_id}`; returns `{enabled}`. Enabling verifies the selected owned/private playlist; disabling closes its player channel. |
| `POST /api/music/voice-ticket` | Owner cookie + Origin + current grant; `{ticket}` single-use, 30 seconds, session/grant-bound. |
| `/ws/music-control` | Exact approved Origin; first frame `{ticket}`. One player per owner. Server sends `ready`, `command` or `release`; browser sends `ping` or `{type:'result', id, state}`. States: `applied`, `deferred`, `queued`, `failed`, `outcome_unknown`. |
| `POST /api/music/voice-release` | Owner cookie + Origin; `{id}` 64-character opaque handoff ID. Consumes a queued command once within 30 seconds; returns `{state}`. |

Command frames carry `id`, `connection_id`, `playlist_id`, `action`, and optional `volume_percent`. Supported actions are play/pause/next/previous/set_volume/volume_up/volume_down; strict volume 0–100 only for set_volume. No metadata is acknowledged. The live-call adapter removes the private handoff ID before returning a generic outcome to the model and sends it only to the browser as `music_handoff`. Play/next/previous release follows PCM drain and actual voice AudioContext close. Unknown outcomes must not be retried automatically. In-memory delivery requires one backend worker.

```ts
type Playlist = { id: string; name: string; spotify_url: string;
  snapshot_id: string; total: number; image_url: string | null };
type Track = { id: string | null; uri: string | null; name: string;
  artists: string[]; album: string; image_url: string | null;
  spotify_url: string | null; duration_ms: number; playable: boolean;
  unavailable_reason: string | null };
type Page<T> = { items: T[]; offset: number; limit: number; total: number;
  next_offset: number | null };
type Mutation = { request_id: string; state: 'confirmed' | 'outcome_unknown';
  result: { snapshot_id?: string; playlist?: Playlist; accepted?: boolean } | null };
type ErrorBody = { error: { code: string; message: string;
  outcome: 'not_sent' | 'unknown'; retry_after_seconds?: number } };
```

`image_url` may be null. Missing/local/episode/unavailable playlist entries remain visible as unplayable tracks. Spotify URLs always link to `https://open.spotify.com`; artwork is original provider artwork. Render strings as text. Never infer Premium or availability from absent profile fields. Offset bounds: 0–5000; page size 1–50 (search 1–10). Use returned numeric offsets, never upstream URLs.

## Connection and capabilities

| Method/path | Input | Success body |
|---|---|---|
| `GET /api/music/status` | — | See below; no Spotify request |
| `POST /auth/spotify/connect` | `{}` | `{authorize_url: string}`; navigate after explicit click |
| `GET /auth/spotify/callback` | provider `code`, `state` or `error` | 303 to `/app/music?spotify=connected`, `/app/music?spotify=cancelled`, or `/app/music?spotify=error`; code/state stripped |
| `POST /api/music/sdk-token` | `{connection_id: string}` | `{access_token: string, expires_at: number, connection_id: string}`; expiry Unix seconds |
| `DELETE /api/connections/spotify` | — | 204; allowed while disabled/misconfigured |

```json
{
  "contract_version": "1.0.0", "configured": false, "enabled": false,
  "connected": false, "reconnect_required": false, "connection_id": null,
  "selected_playlist_id": null,
  "capabilities": { "connect": false, "playlist_read": false,
    "playlist_write": false, "playback": false, "remove_occurrence": false,
    "remove_all_occurrences": false, "voice_control": false },
  "unavailable_reason": "spotify_not_configured",
  "external_url": "https://open.spotify.com/"
}
```

Configured means credentials, valid redirect, and encryption configuration present, not proven provider access. Connected means encrypted connection exists, not verified Premium/playback. `unavailable_reason` is null or a stable error code; disabled → `spotify_disabled`; revoked/corrupt → reconnect required. A connected account may still need renewed scopes. Connect is enabled when configured+enabled. Other capabilities also require a usable connection/scopes. `remove_occurrence` and `voice_control` are always false in v1. Generic `/api/connections` also lists Spotify, but `/api/music/status` is authoritative for music capability.

## Playlist and typed search

Every write (except disconnect/selection) carries `connection_id` and a stable `request_id` generated once per user intent (`crypto.randomUUID()`). Persist that intent ID through retry/reload. Never generate a new ID to retry an uncertain write. Mutation bodies reject unknown fields and arbitrary playlist destinations. All operations target the backend-selected owned, private, noncollaborative playlist.

| Method/path | Input | Success body |
|---|---|---|
| `GET /api/music/playlists` | `offset=0&limit=20` | `Page<Playlist>`; only eligible entries; offsets/total describe upstream page, filtered items may be fewer |
| `PUT /api/music/playlist` | `{connection_id, playlist_id}` | `{playlist: Playlist}`; explicit selection, no creation/playback |
| `POST /api/music/playlists` | `{connection_id, request_id, name}` (1–100 chars) | `Mutation`; create private playlist and select it after verified response |
| `GET /api/music/playlist/items` | `offset=0&limit=50` | `Page<{position: number, track: Track}> & {playlist: Playlist}` |
| `GET /api/music/search` | `q=...&offset=0&limit=10&kind=track` (q 1–100 chars; kind `track` default or `artist`) | `Page<Track>` or `Page<{id, name, image_url, url}>`; artist suggestions use ordinary Spotify search, never AI recommendations |
| `POST /api/music/playlist/items` | `{connection_id, request_id, snapshot_id, uri}` | `Mutation`; add one track at end |
| `DELETE /api/music/playlist/items` | `{connection_id, request_id, snapshot_id, uri, remove_all_occurrences: true}` | `Mutation`; preview/confirm removal of ALL matching occurrences |
| `PUT /api/music/playlist/items/order` | `{connection_id, request_id, snapshot_id, range_start, insert_before, range_length: 1}` | `Mutation`; move one occurrence, positions refer to pre-move order |
| `GET /api/music/mutations/{request_id}` | `connection_id=...` | `Mutation`; durable recorded outcome, never resends |

Use the latest playlist `snapshot_id` in previews. Stale selection/snapshot errors require a fresh read and a new explicit preview. The provider doesn't offer atomic compare-and-swap for add; backend serializes its writes and checks the snapshot before send, but external Spotify edits can still race. Duplicate songs are allowed. Single-occurrence deletion is intentionally unavailable until supported provider schema is verified. `state=outcome_unknown` may mean sent before a crash, timeout, or an unverified response: keep visible, do not resend. Replaying the same request ID/body returns recorded outcome; changing the body/operation/destination with that ID returns conflict. Journal capacity is 1000 per connection generation; active entries are never evicted to permit replay.

## Browser device and manual playback

| Method/path | Input | Success body |
|---|---|---|
| `POST /api/music/device` | `{connection_id, device_id}` (SDK ready ID) | `{device_id, connection_id, expires_at}`; registration tied to Koe session, 15 minutes |
| `POST /api/music/playback` | `{connection_id, request_id, device_id, operation: 'transfer'}` | `Mutation`; transfer with `play:false` |
| same | `{connection_id, request_id, device_id, operation: 'play', position: 0}` | `Mutation`; selected playlist only, position optional default 0 |
| same | `{connection_id, request_id, device_id, operation: 'shuffle', state: boolean}` | `Mutation` |
| same | `{connection_id, request_id, device_id, operation: 'repeat', state: 'off'|'context'|'track'}` | `Mutation` |
| `GET /api/music/playback` | `connection_id=...&device_id=...` | `{state: 'unknown'|'observed', is_playing: boolean|null, device_id: string|null}`; only registered target, no remote data |
| `POST /api/music/recover-audio` | `{connection_id}`; explicit Call/Pause/playlist-change gesture while browser holds exclusive audio ownership | `{state: 'stopped', connection_id}` only after observing stopped/no active playback. May pause an exact device recorded in this generation's durable play/transfer evidence; never transfers, starts music or pauses an unrelated device. |

Device registration validates against Spotify's current available devices and a Koe SDK player name, then binds to the session+generation; this is accidental-remote-control protection, not cryptographic attestation. Instantiate SDK with name `Koe Web Player`. Renew registration after expiry/readiness or foreground reconciliation. No arbitrary context URI, track URI, remote device list, or automatic takeover. Check local SDK state to confirm transfer/playback; accepted provider responses alone do not prove audible playback. Use SDK for pause/resume/seek/previous/next/volume and honor `disallows`.

Registration discovery may wait up to four seconds/eight read attempts for the exact SDK ID to appear. It never sends transfer/play during discovery and still rejects a renamed, restricted or wrong-type device. Discovery failure returns `spotify_device_unavailable` with a specific not-listed/identity message. A clean frontend player remains idle if preparation fails before any playback command; previously observed playback or unresolved evidence remains unknown until verified paused. An explicit next Play retries SDK connection/registration; no uncertain playback write is automatically repeated.

Transfer detail: Spotify documents `play:false` as preserving the current playback state, not as forcing pause. Acquire audio ownership before explicit transfer, treat an in-flight transfer as a possible start, and verify local SDK pause before voice. See [Transfer Playback](https://developer.spotify.com/documentation/web-api/reference/transfer-a-users-playback). Refresh retains an omitted replacement refresh token and handles invalid_grant without retry; the original authorization timestamp is preserved because refresh does not extend the provider's six-month grant lifetime ([refresh reference](https://developer.spotify.com/documentation/web-api/tutorials/refreshing-tokens)).

Frontend owns serialization of all SDK/backend playback commands and the verified pause-before-voice barrier across calls, recordings and stored replies. An unresolved sent Play/transfer remains a barrier until settled; null/unknown is never paused. No automatic resume. Backend requests run independently of the existing voice/agent pipeline. External Spotify links open a destination and cannot prove playback/stop.

Recovery added 2026-10-17: serialize with other owner API mutations, reject any unresolved sent/unknown play or transfer, then query current playback. Only confirmed stopped/no active playback clears persisted uncertainty. Unknown shuffle/repeat outcomes remain recorded and are never replayed, but do not block independent playlist/play actions or this pause check. A browser command still in flight remains a barrier. A 35-second client write deadline exceeds the backend's 30-second bound, reducing abandoned responses without adding retries.

## Errors and frontend integration

Music/auth endpoints normalize errors to `ErrorBody`, including validation, auth and storage/provider failures. Callback errors redirect with a bounded marker. HTTP mapping:

- 401 `spotify_sign_in_required`; 403 `spotify_owner_required`, `spotify_origin_invalid`, `spotify_scope_missing`.
- 409 `spotify_disabled`, `spotify_not_configured`, `spotify_not_connected`, `spotify_reconnect_required`, `spotify_generation_stale`, `spotify_playlist_required`, `spotify_playlist_stale`, `spotify_device_unavailable`, `spotify_request_conflict`, `spotify_journal_full`, `spotify_outcome_unknown` (unresolved earlier operations block reconnect until inspected or explicitly disconnected).
- 400 `spotify_invalid_request`, `spotify_playlist_ineligible`, `spotify_unsupported_operation`.
- 403 provider `spotify_premium_required` or `spotify_forbidden`; 429 `spotify_rate_limited` (bounded Retry-After); 503 `spotify_quota_exceeded`, `spotify_unavailable`, `spotify_storage_unavailable`.
- Sent transport/response uncertainty is HTTP 202 `Mutation` with `state=outcome_unknown`. Read/validation errors are `not_sent`. Error text never includes provider bodies, tokens, codes, SQL, or track titles.

Read requests are bounded and may be canceled; writes are never automatically retried, including refresh failures after an ambiguous token exchange. Revocation clears usable credentials but retains journal evidence and the previous `connection_id` in reconnect status, so the owner can still read recorded outcomes. Definitively rejected provider writes replay the same ErrorBody without resending; their mutation-status result is `{accepted:false}`. A prepared action that failed preflight returns an ErrorBody with `outcome:not_sent` from the status endpoint. Disconnect invalidates pending OAuth, selected preference, device registrations, tokens and journal evidence locally; already-issued provider tokens may remain valid. Frontend must stop/disconnect SDK locally, and offer [Spotify app access](https://www.spotify.com/account/apps/) for provider revocation.

Frontend owner: record consumed `1.0.0` in FRONTEND_STATUS.md before live wiring, report any required contract change there, and keep labeled mocks until backend status marks route readiness. Real-account acceptance and combined-app policy approval remain separate from mock/test success.

Reference basis: [Authorization Code](https://developer.spotify.com/documentation/web-api/tutorials/code-flow), [2026 migration](https://developer.spotify.com/documentation/web-api/tutorials/february-2026-migration-guide), [current removal schema](https://developer.spotify.com/documentation/web-api/reference/remove-items-playlist), [policy](https://developer.spotify.com/policy). Checked 2026-10-15; v1 restricts rather than guessing undocumented occurrence removal.
