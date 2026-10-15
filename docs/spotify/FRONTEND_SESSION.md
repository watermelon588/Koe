# Session 2 — Spotify frontend / Plotcode

Create a fast, polished Spotify experience that feels native to Koe. Read [coordination](CURRENT_STATUS.md), both status files, and [the architecture](../SPOTIFY_MUSIC_ARCHITECTURE.md) first.

**Your files:** `frontend/` and [FRONTEND_STATUS.md](FRONTEND_STATUS.md). Backend, its API contract, and its status are read-only.

Own the visual direction, dedicated music surface, persistent mini player, playlist/search interactions, connection UI, responsive laptop/phone behavior, SDK integration, and browser audio coordination. Choose the layout and styling yourself; make it sleek, accessible, responsive, and consistent with Koe. Avoid adding dependencies when existing React/CSS/components suffice.

Prefer an in-app Spotify surface where permitted and supported. If unavailable, present clear manual Open Spotify / Open web player actions: desktop app or web on laptop, app with web fallback on phone. Do not promise that launching the app starts a song, exposes its state, or lets Koe pause it. No third-party voice control, audio mixing, or music-reactive mascot.

Keep the voice agent fast. Music networking/state must not block the mic, voice socket, or rendering. Coordinate every Koe audio entry point: calls, voice-note capture, and recorded replies. In-app music must be confirmed stopped before voice begins; unknown state blocks that handoff. Preserve manual resume and the architecture's pending-play command barrier.

Build against clearly labeled mocks until Codex publishes `API_CONTRACT.md`; wire only the agreed version. Record frontend-needed routes or contract changes in your own status instead of editing backend files. Keep shared project-doc updates queued there for final consolidation.

**First implementation slice:** design and build the music surface plus external-launch fallback; then connect SDK/API and audio coordination as backend capabilities become ready. This setup brief itself is not a request to start implementation.

**Done:** responsive, accessible UI; truthful loading/error/fallback behavior; smooth controls; cleanup and audio races tested; frontend build/lint/tests and browser checks recorded. No invented playback success or fake live data.
