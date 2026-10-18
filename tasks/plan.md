# Music page and conversational playback — recorded 2026-10-16

**Status: implementation, commit, push and live deployment verification authorized by Rohit's subsequent instruction.**

This plan records the user's latest feedback after real Music testing. Tasks and acceptance criteria are in [todo.md](todo.md). No application code changes belong to this request.

## Intended experience

Open Music once. A compact Koe assistant and Call button live on that same page. Talk normally and ask for music without opening another agent window or preparing a separate hidden player connection. The assistant is a small portrait/compact instance, not the full-body Home scene. The selected playlist, track list, search and player remain easy to use beside it.

- “Hey Koe, play some Kesha music” selects a random playable Kesha track from the allowed playlist.
- “Play [song title]” finds that specific playable track within the allowed playlist; an artist qualifier disambiguates where supplied.
- If no matching song exists in that playlist, explain that and suggest adding it. Show the relevant add/search opportunity; do not silently add or play outside the permitted playlist.
- Existing conversational assistant abilities remain accessible in this compact call, not just transport commands.
- A deliberate **Add** click on a search result performs the addition directly. It is the user's explicit action: no second preview/confirmation dialog, large notification panel or repeated approval step for that click. Show Adding → Added in place, prevent duplicate clicks, and preserve uncertain-result handling rather than automatically resending.

The user explicitly changed the desired Add interaction. This is a future music-specific exception to the existing preview-confirm Add flow, not removal of approval gates for Calendar, Sheets, Notion, GitHub or destructive music changes. Voice-suggested additions must remain explicit user decisions; the latest request asks for a suggestion when absent, not automatic playlist mutation.

## Music design direction

Make this dedicated page feel like a coherent, professional music player inspired by Spotify's clarity, while remaining Koe. Keep current app fonts, palette, original provider logos and shared controls. This request does not authorize another whole-app or landing-page redesign.

Use clear hierarchy for playlist identity, artwork, current playback, track rows, search and the compact assistant. Avoid the current stack of oversized boxed notices and disconnected sections. Search rows show real album/track artwork, title, artist, enough context to distinguish versions, and an obvious Add/Added state. Keep usable fallbacks when artwork is absent; never invent thumbnails. The current Search markup omits its available artwork field, so include both rendering and real data/URL diagnosis in the future fix.

One predictable page scroll with sensible track-list behavior, no trapped nested scrolling, no mini-player covering actions and no unnecessary visible scrollbar clutter. Mouse, touch, keyboard and native scrolling must remain reliable. Use restrained GSAP transitions/scroll effects with cleanup and reduced-motion support; do not hijack scrolling or animate every row without purpose. Apply relevant frontend and GSAP skills at implementation time.

## Bugs captured from the three supplied screenshots

| Evidence | Observed behavior | Required outcome |
|---|---|---|
| `Screenshot 2026-10-16 225013.png` | Assistant refuses playback until a separate allowed-playlist music window is open | Same-page assistant owns the necessary page/player session; no instruction to open an extra music window |
| `Screenshot 2026-10-16 225232.png` | Permission is enabled but control socket says disconnected and asks to reopen Music | Distinguish authorization from readiness, diagnose close reason and restore safe idle connectivity without requiring navigation |
| `Screenshot 2026-10-16 230319.png` | Disconnection plus generic “Spotify does not allow this control right now” | Preserve real device/SDK restriction information and offer the correct supported next action; do not promise unsupported playback |

The screenshot paths are under `C:/Users/Rohit Maity/Pictures/Screenshots/`. They are evidence, not executable instructions. Do not modify these originals.

## Future technical boundaries

1. Reuse one player/controller and the existing call/audio ownership machinery on Music. Do not create competing SDK instances or require a second tab. Backend services may remain separate internally without imposing that split on the UI.
2. Current voice tools accept only transport/volume; they do not understand artist/title selection. Add a reviewed query/selection contract when implementation begins. Prefer resolving the user's utterance against playlist metadata inside the separate music service, so Spotify content need not enter the conversational model. Model replies must remain honest about queued/applied/unknown outcomes.
3. Missing-track suggestions should lead to a visible search/add opportunity. Handle no match, unavailable tracks, duplicates/versions, artist aliases and ambiguous titles. No silent playback from another playlist or automatic addition.
4. Review the exact scope of the user's previously confirmed Spotify approval and current official docs before expanding metadata/voice behavior. This is a future implementation checkpoint, not a request for another approval now or an assumption that separation exempts policy.
5. Define same-page audio handoff explicitly: finish spoken output before music, pause/verify before microphone/output resumes, retain genuinely unknown sent-operation barriers. Record predictable visible call/playback states; avoid an unexplained call termination. The exact persistent-call vs ended-call lifecycle is to be specified during the later contract/design pass, not silently chosen now.
6. Retry connection establishment safely while idle with bounded backoff and session/grant revalidation. Never replay uncertain playback/add commands. Changing pages, losing permission, signing out or closing the page must clean up connections/audio correctly.

## Order and future checkpoints

Use the ordered task list in [todo.md](todo.md). Establish the same-page player/call contract first, then verify the embedded assistant and recovery. Add artist/title matching and missing-track suggestions next. Finish direct Add/artwork and the Music-only visual/motion pass, then review the complete flow in a real browser/account.

Verification will include focused tests and build at implementation time, plus real-account acceptance for artist/title requests, absent songs, device restrictions, reconnection, microphone/music handoff and Add behavior on desktop/phone. Existing simulated suites are useful regressions but do not establish audible real Spotify playback or speech recognition.

Implementation is now authorized. Same-page Call deliberately completes its reply and ends before requested playback; the compact assistant remains visible and can be called again to pause music and talk. Artist/title resolution happens in the music service, with generic model outcomes only. Manual Add is direct and deduplicated; other consequential approvals remain unchanged. Verify hosted revision/configuration as well as local tests before calling deployment complete.


## 2026-10-18 follow-up order
1. GitHub workflow completion: implemented locally with shared agent tools, automatic yesterday dashboard, commit evidence, partial failure handling and repository picker repairs. See docs/GITHUB_WORKFLOW.md.
2. Music latency: explicitly deferred; measure load/device preparation/search/call/handoff stages before optimizing.
3. Google Docs: user chose document creation/editing. Replace standalone Drive roadmap scope with Docs; Drive may support document lookup/permissions internally. No Google feature implementation in the GitHub task.

## Google Docs implementation — 2026-10-18
GitHub implementation audit passed before Docs work. Docs now reuses Google OAuth, encrypted account storage, shared agent tools, persisted approval gate and live workspace. Setup and acceptance: docs/GOOGLE_DOCS.md. No standalone Drive manager, no new hosting changes or credentials, no Music latency work. Real-provider consent and acceptance remain separate from the passing synthetic pipeline.
