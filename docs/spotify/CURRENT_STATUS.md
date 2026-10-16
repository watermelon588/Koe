# Spotify feature — two-session coordination

Updated 2026-10-16: manual and separately approved voice/music pipelines are implemented locally. With explicit user approval, migration 007 is applied to Neon and both local flags are enabled. App credentials/configuration checks pass; owner Spotify consent, real audible playback and spoken-command acceptance remain pending. The new voice extension is not deployed. See [current review](../REVIEW_2026-10-16.md), [local setup](../../backend/SPOTIFY_LOCAL_SETUP.md) and [voice transport](VOICE_CONTROL.md).

Verification: 564 backend tests, 60 frontend tests, 15 manual-pipeline + 9 voice-pipeline browser scenarios, 9 original-app + 15 retained-homepage checks passed; production build passed. Browser pipeline providers/SDK audio/Gemini function selection are simulated. Four existing lint warnings remain. The session records below describe earlier implementation coordination and do not supersede this update.

Later local acceptance update: owner Spotify connection now exists, and live read-only Spotify metadata requests succeed. The saved playlist is owned but public; all nine listed playlists are public (five owned). The UI now preserves the connection and returns to private-playlist choose/create controls for this rejection, with selected-playlist and refresh actions. No Spotify privacy/content change or audible playback acceptance has been performed. Frontend suite is now 61 tests; four targeted recovery browser scenarios cover transient failure/session expiry and invalid selection with populated/empty eligible lists.

| Session | Agent | Owns | Live status |
|---|---|---|---|
| [Backend session](BACKEND_SESSION.md) | Codex | `backend/`, Spotify API contract | [Backend status](BACKEND_STATUS.md) |
| [Frontend session](FRONTEND_SESSION.md) | Codex takeover after Plotcode stopped | `frontend/`, player UI, browser audio coordination | [Frontend status](FRONTEND_STATUS.md) |

This file is the stable entry point. The user explicitly confirmed that the frontend agent stopped and assigned its remaining work to Codex. Codex completed the SDK, edits, cross-tab handoff and integration, then consolidated the status and shared documentation. The original separate-ownership rules below describe the parallel implementation period.

Created Codex chat IDs:

- Backend: `01a13e07-bddc-79d2-8300-7257fc5e08e9`.
- Frontend handoff for Plotcode: `01a13e17-d30c-7003-8855-8eda2f067430`. This chat stores the handoff; it does not launch the external Plotcode agent. Give that agent [FRONTEND_SESSION.md](FRONTEND_SESSION.md).

## Working agreement

- Read both status files before starting work, after resuming, and before integration. Update your own status at the start/end of each slice, when publishing an interface, or when blocked. Record a request for the other agent in your own status; the recipient answers in theirs. No dependence on ephemeral chat messages.
- Edit only your owned paths and your own status. Backend also owns `docs/spotify/API_CONTRACT.md`, which it will create before frontend integration. Frontend may build against the proposed architecture or temporary mocks meanwhile, clearly marked as such.
- Freeze API paths, payloads, and errors in that contract before live frontend wiring. Backend publishes a version; frontend records the consumed version in its status. Proposed changes go through the status files before either side adopts them.
- Do not edit the other agent's files, run repository-wide formatters, stage/commit unrelated files, reset the checkout, or switch the shared branch. Request cross-boundary work through status. Both sessions share this checkout so status is immediately visible.
- Keep feature build notes and decisions in your owned status during parallel work. Consolidate shared `SPEC.md`, `DECISIONS.md`, and `BUILD_LOG.md` after both sessions finish; neither agent writes those shared files concurrently.
- Preserve pre-existing/unrelated changes. At setup these included `backend/koe/main.py`, `backend/koe/people.py`, and `backend/tests/test_people.py`, plus existing documentation changes. Recheck the working tree before implementation; backend merges only its own router addition into the current `main.py`.

## Product direction

Use Rohit's existing Spotify Premium and dedicated chill playlist. Prefer a sleek Spotify surface in Koe if permitted and supported. Otherwise offer explicit buttons to open the official Spotify app or its web player: desktop app/web on laptop, Spotify app/web fallback on phone. External launch opens a destination; it does not guarantee autoplay or prove playback state.

Keep music HTTP/SDK work out of the agent's microphone/WebSocket/model path. No periodic Spotify work inside a voice turn, no music-to-model data flow, and no unsupported Spotify voice commands. The manual player and verified voice/audio handoff remain subject to the policy boundary in [the architecture](../SPOTIFY_MUSIC_ARCHITECTURE.md). An external Spotify app is outside Koe's audio control; do not pretend Koe can confirm it paused.

The architecture is technical guidance. The original session briefs preserve the split; the user's later implementation and frontend-takeover instructions supersede their initial prepare-only state. See [local setup and simulated preview](../../backend/SPOTIFY_LOCAL_SETUP.md).
