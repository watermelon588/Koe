# Frontend handoff: mascot profiles and Settings

Updated: 13 October 2026 (Asia/Kolkata). Original implementation: 12 October 2026.

## Latest revision: visual companion studio

Follow-up fix (13 October): removed vertical camera panning from pointer dragging and Up/Down keys. It allowed users to move the figure out of the preview pane. Dragging now only rotates the model, while vertical framing remains centered in both portrait and full-body views, at every zoom level. Updated the visible hint and screen-reader instructions accordingly. Rotation, turntable and zoom remain available.

The first Settings layout was too text-heavy, used letter placeholders, and left the full-body avatar in a small fixed-height card. The current page replaces that layout with one viewport-adaptive studio, real screenshots of all four VRMs, and a compact overlay toolbar. Full body automatically expands the existing canvas; the user can rotate through 360 degrees and zoom up to 2.5×. The portrait strip moves from the left edge to the bottom on phones. The sidebar, introductory paragraphs, character descriptions, footer slogans, and separate expression/mood button groups have been removed.

Controls now live inside the viewer: Portrait / Full body, expand / close, Say hi, auto rotate, zoom and Choose. Expanded view contains keyboard focus, makes background navigation inert, closes with Escape and restores focus. The canvas supports left/right arrow-key rotation and Home to reset rotation. Expanding does not reload the model or create a second canvas. Selection and Home behavior are unchanged.

Portraits are screenshots of the real loaded VRMs (not generated artwork), saved in `frontend/public/mascot/portraits/{kami,miku,aoi,kobashi}.jpg`. All four total approximately 96 KiB. Settings inspection measures actual mesh bounds for tighter framing; Home keeps its previous framing and spring-back interactions.

This is the handoff for the paused coding session. Read the current working tree before continuing: there were already substantial uncommitted frontend, backend and documentation changes when this task started. This task builds on those changes; it does not replace them or treat HEAD as the complete application. No commit or deployment was made by this task.

## User request

Add Aoi and Kobashi alongside Kami and Miku. Move mascot selection into a dedicated Settings page with a Profile section and interactive previews. Home renders the chosen mascot and keeps its theme/layout controls. Document the previous and current frontend state for the other coding session.

## Before → now

| Area | Before this task | Current state |
| --- | --- | --- |
| Available mascots | Kami and Miku were served from `frontend/public/mascot`. Aoi and Kobashi existed only among source assets. | All four are served from `public/mascot` and listed in a shared catalog. |
| Mascot picker | Kami/Miku segmented buttons in the Home header. | Settings → Profile contains the four choices. No mascot selector on Home. |
| Applied choice | App read `?model=` and rewrote that query parameter on a switch. | App reads `koe-mascot` from localStorage. Settings explicitly saves a choice. Old `?model=` is ignored and removed. Missing, obsolete or unreadable stored preferences fall back to Kami. |
| Preview | Switching the Home picker immediately changed the live mascot. | Selecting a portrait opens a live preview. It does not affect Home until Choose is pressed. |
| Settings | No dedicated page. | `#settings` is a compact Profile studio: one large visual pane, four portrait thumbnails, on-canvas controls, explicit application state and short save feedback. |
| Preview interactions | Existing gestures/moods were primarily driven by pointer interaction and live calls. | Say hi and direct tap reactions; portrait/full-body framing; persistent 360° rotation, fixed vertical framing, turntable and 1–2.5× zoom. Full body automatically expands. Arrow keys and Home provide keyboard inspection. |
| Rendering lifecycle | App directly imported and constructed the Home renderer. | `MascotView` owns lazy loading, actual model readiness, retry/error UI and disposal. Home and Settings share it; only one canvas is mounted at a time. |
| Appearance | Shoji/Engawa and dark/light controls on Home. | Both remain on Home. Settings inherits the current theme. Aoi and Kobashi gain their own accent colors in both themes. |
| Navigation during calls | Only Home/call composition existed. | Settings navigation is blocked during an active call, including hash/history navigation, so a preview cannot replace the live-call mascot. End the call before changing the profile. |
| Asset packaging | `.gitignore` ignored all public VRMs. | Explicit exceptions make the four runtime VRMs eligible for Git. Source experiments and VRoid project files remain ignored. |

## Files changed by this task

| File | Purpose |
| --- | --- |
| `frontend/src/App.tsx` | Home/Settings navigation, saved mascot state, explicit selection callback, URL cleanup, shared Home view, page focus and call navigation guard. Removed the Home mascot picker and App-owned renderer setup. Preserves the current dashboard and call integration. |
| `frontend/src/mascot/catalog.ts` (new) | Four profiles, names, portrait paths and IDs; validated localStorage reads and save-result handling. Add future mascots here, then supply their public VRM, screenshot and ignore exception. |
| `frontend/src/mascot/MascotView.tsx` (new) | Shared React renderer lifecycle, asynchronous loading, framing, ready callback, load/error states, retry and cleanup on switching/unmount. |
| `frontend/src/settings/SettingsPage.tsx` (new) | Compact studio, screenshot strip, preview-only selection, framing/expansion, overlay toolbar, zoom/turntable state, explicit Choose button and short save feedback. |
| `frontend/src/settings/useExpandedPreview.ts` (new) | Expanded-view focus containment/restoration, Escape handling, inert background header and body scroll lock with cleanup. |
| `frontend/src/settings/settings.css` (new) | Adaptive studio using existing tokens; overlay controls; left portrait rail becomes a bottom strip on phones; expanded pane fills the available window; shared navigation/load states and Aoi/Kobashi accents. Imported by SettingsPage and applies shared styles to Home too. |
| `frontend/src/mascot/mascot.ts` | Exposes `ready`, `inspect`, `zoom` and `spin`. Inspection uses actual mesh bounds, persistent full rotation, fixed vertical framing, pointer capture and keyboard controls. Home retains its existing camera/drag behavior. Optional-bone guards and pointer-cancellation cleanup remain. |
| `frontend/public/mascot/portraits/*.jpg` (new) | Four screenshots cropped from the live VRM viewer, approximately 96 KiB combined. These are normal tracked runtime assets. |
| `frontend/public/mascot/aoi.vrm` (new runtime copy) | Copied unchanged from `frontend/assets/mascot/aoi.vrm`; 16,226,988 bytes. |
| `frontend/public/mascot/kobashi.vrm` (new runtime copy) | Copied unchanged from `frontend/assets/mascot/kobashi.vrm`; 17,827,224 bytes. |
| `.gitignore` | Adds public asset exceptions for Kami, Miku, Aoi and Kobashi. All four public models now need to accompany the source when committing. Kami/Miku binaries were already present locally. |
| `frontend/tests/mascot-preferences.test.mjs` (new) | Tests missing/invalid preferences, all four save/reload round trips, VRM/portrait availability, and blocked storage. Uses the existing Node test setup. |
| `docs/SPEC.md`, `docs/DECISIONS.md` | Append the profile behavior contract and implementation decision. |
| `docs/BUILD_LOG.md` | Append a learning/handoff entry for this slice. |
| `change log.md` | This handoff. |

This task adds no dependencies, changes no backend API, and makes no changes to `useCall`, dashboard modules, access-token handling or write-approval logic. The Home header and main rendering integration in App changed, while the existing call panel behavior was preserved.

## Current architecture and preference contract

```text
App (applied MascotId, theme, layout, token, useCall, useDashboard)
  Home → MascotView → createMascot(public VRM)
  SettingsPage (temporary preview MascotId, framing, zoom, turntable, expansion)
    → MascotView → createMascot(public VRM)
    → Choose → App state + localStorage
```

- Preference key: `koe-mascot`; values: `kami`, `miku`, `aoi`, `kobashi`.
- Existing theme key: `koe-theme`. Layout still uses `?ui=shoji` / `?ui=engawa`.
- Routes: `#home` and `#settings`. Direct reload on Settings works without a new server route or router dependency.
- Only the applied mascot persists. Preview framing, zoom, turntable, expansion and pending preview reset when Settings unmounts; revisiting opens the applied mascot.
- If writing storage fails, the selection works for the current visit and the user is told that it was not saved. Preferences are browser/device-local, with no account synchronization.
- A preview opens no microphone, socket or Gemini session. Mascot choice changes the visual companion, not Koe’s voice, tools or assistant identity.
- Choose and preview interaction buttons wait for model readiness; a failed load offers Retry. Home remains usable while its VRM loads or fails.
- VRM rendering remains a lazy chunk. Browsing the page does not preload all four models simultaneously.

## Concurrent dashboard work: preserve this

At initial inspection, Home still displayed sample agenda/GitHub/approval lists. During implementation, another session’s dashboard changes became visible: `dashboard/Dashboard.tsx`, `dashboard/useDashboard.ts`, dashboard tests, a dashboard verification Vite config, updated package scripts, and Home’s **Connect dashboard** plus the call panel’s **Chat/Day** tabs. These changes are not authored by this task. The mascot work was adapted to preserve them, rather than restoring the earlier sample-data App.

In the current Home, missing dashboard data is shown as offline/waiting states until the existing token connection is used. Do not put the old sample lists back while integrating this change. Other backend and docs edits already in the working tree also belong to the other session.

## Verification

- `npm test`: 7 passed (4 existing dashboard tests + 3 mascot preference/asset tests).
- `npm run build`: passed, including TypeScript and Vite production asset packaging.
- `npm run lint`: passes with the existing App `new Date()` render-purity warning. No new mascot/settings lint warnings.
- Browser: Kami, Miku, Aoi and Kobashi reach ready state in the live preview. Real portraits load for all four. Framing, zoom, turntable, horizontal drag and keyboard rotation work. Expanded view closes with Escape and restores focus; Tab/Shift+Tab stay within it.
- Browser: applied Aoi, returned Home, and reloaded; Aoi remained selected. Applied Kobashi; previewed Miku without applying; Home still rendered Kobashi.
- Browser: Settings has one canvas before and after expansion, with the model still ready. Checked 320, 375, 768, 1024 and 1440 pixel viewports with no horizontal overflow or overlapping top/bottom controls. A 1440×1000 expanded pane gives the canvas 832 px of height; at 375×844 the expanded phone canvas is 592 px tall. Light/dark styling and retained Home layout/theme controls were checked.
- `git diff --check` for the edited tracked files is clean. Intermediate Vite hot-reload messages during file creation were resolved; no subsequent mascot runtime error was observed.

Vite still reports the large lazy Three.js/VRM chunk (about 758 kB minified). The four runtime binaries total about 65.3 MiB; only the chosen/previewed model is requested. Live authenticated audio calls and backend integrations were not re-tested in this frontend slice; no credentials were entered or external writes performed.

## Resume notes

1. Read this file and current App before cherry-picking or committing: the working tree contains contributions from both sessions.
2. Include the new settings/catalog/view/test files and **all four public VRMs** when committing. Do not accidentally include source VRoid projects or unrelated backend work in a mascot-only commit.
3. Run `npm test`, `npm run build` and `npm run lint` from `frontend` after integrating more work.
4. Add later settings sections alongside Profile. Keep mascot application explicit and retain the rule that Home only renders the saved choice.
5. The existing Graphify report was consulted, but its executable/interpreter path was stale and its graph predates the current frontend. It was not regenerated by this task; inspect source or rebuild it before using it as current architecture evidence.

## Update from the mascot UI session (13 October)

Built on top of this handoff; nothing above was reverted.
- `mascot.ts`: Home's half figure is now hair to waist, framed so her waist sits on a **desk card** (`DESK = 0.24` ↔ `--desk-h` in index.css). Inspection framing in Settings is unchanged. New `chin` (played automatically on `mood('thinking')`) and `stretch` gestures. Gesture blending now covers any bone a gesture or pose touches (fingers rest pose moved into a `still` map, blended like the rest).
- `vroidpose.ts` (new) + `src/mascot/poses/` (new, with README): `.vroidpose` files from VRoid Studio become idle poses. Tests: `tests/vroidpose.test.mjs`.
- `App.tsx`: the Home stage renders the desk (name, status, Say hi) under the mascot, positioned by `--x`. `index.css`: desk styles, phone variant.
- `public/mascot/kami.vrm` replaced by Rohit's updated export; previous copy at `assets/mascot/kami-2044.vrm`. The Settings portrait `portraits/kami.jpg` was taken from the old model and may need a re-shot.

## Settings redesign (13 October, mascot UI session)
Rohit asked for a slick, minimal Settings page. SettingsPage.tsx and settings.css were rewritten: companion list left (round portraits, "Current" tag, one "Use …" button), flat viewer right with one toolbar (Portrait / Full body, Say hi, Rotate). Zoom is now the scroll wheel (native non-passive listener); expanded mode and `useExpandedPreview.ts` were removed. Selection contract (`onSelect`, `koe-mascot`, preview-only browsing) is unchanged; `MascotView`, `catalog.ts` and inspection framing are untouched.

## Engawa only, Phosphor icons, tabbed dashboard (13 October, mascot UI session)
Shoji and the layout switch are gone (`?ui=` is stripped from the URL). Header nav is icon buttons (`House`, `GearSix`, `Sun`/`Moon`) via `@phosphor-icons/react` (new dependency, approved by Rohit). `Dashboard.tsx` was rewritten as one tabbed card with the same props and the same `useDashboard` state; `.block`/`.dashboard` styles were replaced by `.dash*`. The token input is now a single Connect row on Home that hides once connected. Settings toolbar buttons gained icons; old `.page-nav` styles were removed.
