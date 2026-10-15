# Session 1 — Spotify backend / Codex

Build the backend foundation for a smooth personal Spotify Premium experience. Read [coordination](CURRENT_STATUS.md), both status files, and [the architecture](../SPOTIFY_MUSIC_ARCHITECTURE.md) first.

**Your files:** `backend/`, [BACKEND_STATUS.md](BACKEND_STATUS.md), and `docs/spotify/API_CONTRACT.md`. Frontend and the other status are read-only. Preserve unrelated in-progress backend work.

Own Spotify account linking, encrypted tokens and refresh, authenticated routing, dedicated-playlist access, playback/device requests where permitted, database migrations, error handling, and backend tests. Publish the small versioned API contract before Plotcode connects real requests. Keep provider calls independent of voice latency; do not add Spotify tools or content to the model pipeline.

Support the frontend's preferred in-app player where allowed and its official Spotify app/web fallback without treating link opening as verified playback. Preserve the architecture's policy boundary. Existing Premium does not authorize Spotify voice control.

Implement in thin slices, decide routine backend details yourself, and report evidence and interface changes in your status. Ask the frontend owner through status when a change needs frontend work; do not edit it yourself. Keep shared project-doc updates queued in your status for final consolidation.

**First implementation slice:** settle/publish the API contract, then account connection and storage with mocked tests. Continue through the backend phases when the user starts this session. This setup brief itself is not a request to start implementation.

**Done:** tested owner-isolated routing, secure token lifecycle, replay-safe migrations, robust playlist writes, accurate failure states, and a contract the frontend has consumed. Real-account acceptance and unresolved policy/setup dependencies must be reported separately from mock success.
