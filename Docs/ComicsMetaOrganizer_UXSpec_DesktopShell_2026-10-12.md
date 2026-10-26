# Desktop shell — window, tray, quit, update banner, startup, app icon

Date: 2026-10-12, revision 2 (same day). Owner: Judy. Status: reviewable draft; Sully commits this exact file before Ender is briefed (M2–M4). No code, no commit, no running-service contact was part of writing it.

Revision 2 folds in Sergei's answers of 2026-10-12 to the ten open questions. Each place an answer changed the spec is tagged `(Sergei 2026-10-12, A{n})`; the full record is §11. Nothing else in the first draft changed.

**Revised 2026-10-26 (Sergei bug).** `Install and restart` was offered again while Pause and install was still running. §4 now has a Waiting state (the "After confirm" row is replaced) and a timeout failure that says why; the focus rule in §4, the Installing rows in §2, the Cancel line in §3, the §4a blocked row, §6, §9 and §11 follow. Every changed place is tagged `(Revised 2026-10-26, Sergei bug)`. Sergei's rulings are in §11; the copy, look and focus are Judy's.

Classification: NEW shell surfaces (window, tray, stopping dialog, startup/failure page, app icon) plus one EXTEND of `static/index.html`: one banner slot under the header and one `Check for updates` button in the header, both rendered only inside the app shell. Dashboard content, the verification rows and the earlier specs (Yandex, VerificationLabels, Version) are unchanged. Tooltips for the existing bare dashboard controls are a separate doc: `ComicsMetaOrganizer_UXSpec_DashboardTooltips_2026-10-12.md`.

Sergei's decisions applied. Round 1: close hides to the tray and processing continues; tray menu is Open, Pause & release GPU, Quit; Quit pauses, waits for Paused, then exits; no start at sign-in; update check only, and installing pauses and stops processing first. Round 2 (2026-10-12): §11.

Settled with Ender (A8): the app starts and stops the bundled Python engine itself; Python ships inside the app. The name shown everywhere is **Comic Metadata** (A2).

```
┌ Comic Metadata ─────────────────────────── ─  □  ✕ ┐   close = hide to tray
│ Comic Metadata            [ v0.1.1 ] [Check for updates]   header: one new button (§4a)
│ Your collection, with better info.   [Pause & release GPU]
│                                      status line    │
│ ┌ shell banner — one at a time, in flow ──────────┐ │   NEW slot (§4, §5)
│ │ Update available — v0.2.0   [Download]  [×]     │ │
│ └─────────────────────────────────────────────────┘ │
│ #error (existing, sticky)                           │
│ Live enrichment progress / Live library / list …    │   unchanged
└─────────────────────────────────────────────────────┘
Tray icon:  base | + pause badge | + "!" badge | + "×" badge      menu: Open · Pause & release GPU · Quit
Modal (own window, only while stopping): Quitting / Installing — Cancel · Quit now
```

## 1. Window

| Property | Spec |
|---|---|
| Title | `Comic Metadata`, fixed; ignore page-title changes. |
| Frame | Standard Windows frame with minimize, maximize, close. Not frameless (this is a dashboard, not a popup). |
| Menu bar | Hidden; Alt shows Electron's default menu. Reload, zoom (Ctrl +, −, 0) and DevTools keep working (ProcessRules § Never silently strip dev/debug tooling). Any Quit or Exit item in that menu, or any other `app.quit()` route (including an installer-triggered quit), runs the §3 flow. |
| Ctrl+Q (Sergei 2026-10-12, A6) | Window-level shortcut that runs the §3 Quit flow, the same as tray Quit. Works with focus anywhere in a shell window: the dashboard (including a focused text box and the open comic-details dialog), the startup page and the failure page. Not global, and not active while the window is hidden. No visible control; the hidden Alt menu's Exit item carries `Ctrl+Q` as its accelerator label, the Windows-native place to learn it (Jakob). A second press during a quit does nothing (it does not mean Quit now); while the stopping dialog is open it does nothing. On the startup or failure page nothing is running, so it exits at once. |
| Background | `#12151c` before first paint; show the window on `ready-to-show`. No white flash. |
| Theme | Force `nativeTheme.themeSource = 'dark'`. The dashboard is dark under both Windows themes (Yandex spec); title bar, scrollbars and native menus follow. |
| Default size | 1280×860 DIP, clamped to 90% of the work area of the display it opens on, never below the minimum. |
| Minimum size | 640×480. At 200% zoom 640 px is 320 CSS px, the reflow target used by the earlier specs. |
| First-run position | Centred on the primary display's work area. |
| Remembered | `x, y, width, height, maximized` in the app's user-data folder (Ender picks the file; not the repo's `data/`). Save 400 ms after the last move, resize or maximize change. Save `getNormalBounds()`; never save while minimized (Windows reports −32000). Restore normal bounds plus the maximized flag. Never restore minimized or hidden: launch always shows the window. |
| Saved-bounds guard | Same rules as QuickLaunch `src/main/window.js` `initialBounds` (read-only reference): integers only, at least 100×50 px overlapping a connected display's work area, size fits that work area; otherwise default size, centred. |
| Show on launch | Always. Every launch is Sergei's own (no start at sign-in), so there is no hidden-start mode. |
| Close (✕, Alt+F4) | Hides the window; processing continues. First time ever: the §2 notice. If the tray icon could not be created, close runs the §3 Quit flow instead. Never hide to a tray that does not exist. |
| Minimize | Normal taskbar minimize. Only close hides to the tray. |
| Single instance | Second launch restores a minimized window, shows a hidden one and focuses it. Same while Starting or Quitting (focus the existing window or dialog). It never starts a second service. If Windows refuses foreground and only flashes the taskbar button, report it; no always-on-top tricks. |
| Taskbar | Button while the window is visible, the §10 app icon, no overlay badge, no progress. |
| Toasts | Set the AppUserModelId equal to the installer's appId, or §2's notifications will not show. |
| Refresh on show | On show/focus, the dashboard refreshes state, progress and verification immediately, once; hidden windows are throttled by Chromium, so do not rely on the 2 s timers catching up. Do not disable background throttling. |
| Start at sign-in | None. No HKCU Run value, no startup shortcut, no scheduled-task trigger, no installer checkbox for it. |

## 2. Tray

### Icon states (four, meaningful only)

| State | Icon | Shows when |
|---|---|---|
| Processing | Base icon, no badge | Service reachable, not paused, no verification waiting. Idle waiting counts as Processing. |
| Paused | Base + grey pause badge (two bars) | Pause requested (Pausing and Paused share the icon so a click is acknowledged at once; the tooltip says which). |
| Needs verification | Base + amber "!" badge | A Lens or Yandex verification button is visible and enabled in the dashboard. Clicking it (queued, opening, open) returns the tray to Processing. |
| Error | Base + red "×" badge | Service unreachable on 3 consecutive polls, or restart attempts exhausted (§5). Optional: the worker reports stopped for 60 s or longer (two missed 30 s restarts), if the light status source carries that field. |

Precedence: Error, then Paused, then Needs verification, then Processing. Pause outranks verification because the dashboard already hides verification actions while paused. Starting and Quitting keep the base icon and change only the tooltip. No badge for updates (the badge slot belongs to state); an update only adds a tooltip suffix.

Badge rules: shape plus colour plus tooltip, never colour alone. Compose at runtime from the §10 base icon (QuickLaunch's approach), at 32 px with a 16 px representation, in the base icon's reserved badge zone with a white ring (§10). Badge fill luminance must sit between 0.143 and 0.265 so it holds at least 3:1 on both a dark `#202020` and a light `#f3f3f3` taskbar without knowing the theme; glyphs are white. Starting palette (measured, sRGB): pause `#707070` (3.29:1 dark, 4.46:1 light; white glyph 4.95:1), verification `#b87300` (4.26:1, 3.45:1; glyph 3.82:1), error `#d13438` (3.30:1, 4.44:1; glyph 4.93:1). Judy reviews rendered 16, 24 and 32 px crops on both taskbars before Futaba (not rendered yet).

State source: the **main process** polls a light status call every 3 s whether or not the window is visible (a hidden window's timers are throttled). It must not call `/api/progress` (heavy, serialised). Fields: pause control (`requested`, `phase`, `gpu_released`, `error`), both verification engines, and reachability. Update the icon and tooltip only when the derived state changes.

### Tooltip (single line, at most 127 characters, format `Comic Metadata — {state}`)

| State | Text after the dash |
|---|---|
| Starting | `Starting…` |
| Processing | `Processing enabled` |
| Pausing | `Pausing. Finishing the current operation.` |
| Paused, GPU released | `Paused. Gemma released from GPU.` |
| Paused, release pending | `Paused. Releasing Gemma from GPU…` |
| Paused, release failed (`control.error`) | `Paused. GPU release not confirmed.` |
| Needs verification | `Needs your verification: Google Lens` / `…: Yandex` / `…: Google Lens and Yandex` |
| Service unreachable | `Local service not responding. Open the window for details.` |
| Worker stopped (optional) | `Worker stopped. Open the window for details.` |
| Quitting | `Quitting…` |
| Installing (from `Pause and install` until the app closes; Revised 2026-10-26, Sergei bug) | `Installing update…` |

Suffix ` · Update available` on Processing, Paused and Needs verification while an update is available and not dismissed. Reuses the dashboard's own words ("Processing enabled", "Pausing", "Paused") so the same word means the same thing.

### Menu (right-click)

| # | Label | Behaviour |
|---|---|---|
| 1 | `&Open` | Shows, restores and focuses the window. |
| 2 | `&Pause && release GPU` / `&Resume processing` | Label mirrors the dashboard button (follows `requested`, so it reads Resume while Pausing). Disabled while Starting, Quitting, Installing or service unreachable. Installing means the whole span from `Pause and install` until the app closes, not only while the stopping flow runs: the installer check and the update-helper copy come first and take time (Revised 2026-10-26, Sergei bug). |
| | separator | |
| 3 | `&Quit` | Starts §3. While stopping it reads `Quitting…` and is disabled. |

- `&&` is required: on Windows a single `&` in a menu label is a mnemonic marker, so `Pause & release GPU` would render `Pause  release GPU`. Futaba checks the rendered label.
- Item 2 is bound to its intent at build time. If the state changed while the menu was open (label says Pause, service is already paused), the click does nothing rather than flipping the state.
- Three items (Hick). No Settings, no start-with-Windows toggle, and no Check for updates: that control lives in the window header (§4a, A7). Native menu items cannot carry tooltips; the label is the copy and the tray icon tooltip is the status (flag F2).
- The Quit item shows no `Ctrl+Q`: that key works only with a shell window focused, and a hint on the tray menu would promise a key that does nothing there.
- Legible under both Windows themes (Ender verifies; `themeSource` dark should carry the menu).

### Click behaviour

- Left click and double-click: Open (same as menu item 1). Idempotent: if the window is already visible and focused, nothing happens. Never hides. This differs from QuickLaunch (double-click toggles) on purpose: QuickLaunch is a launcher popup, this is a dashboard people check and leave; the single-click-opens convention is what Windows users expect from tray apps (Jakob).
- Right click: the menu.
- Recommended: when Open is used while the tray state is Needs verification, scroll the verification row into view (`block: 'nearest'`, no focus move). The Lens and Yandex rows sit well down the first panel and are likely below the fold at the default size (to be measured, not yet).

### Notifications (two, both silent)

Common rules: OS notification (Fluent: OS API, respects Focus Assist). `silent: true`, no actions, no timeout override, never focuses a window, no audio. Clicking one runs Open. Title is always `Comic Metadata`.

**1. First-time notice (once, ever).**
- Trigger: the first time the window is closed to the tray. Not at launch, not on quit or update.
- Title `Comic Metadata is still running`. Body `Processing continues in the tray. Right-click the icon to pause or quit.`
- Persist "shown" only when the notification's `show` event fires; a `failed` event leaves it unset so the next close retries. Never repeated after one success.

**2. Tray-started pause finished (Sergei 2026-10-12, A3b: yes).**
- Trigger: a pause started from the tray menu's item 2 reaches its end: Gemma released from GPU, or the release failed. One notification per pause.
- Does not fire for: the dashboard's Pause button (Sergei is already looking at the status line), the shell pause that Quit or install places (§3), a pause cancelled with Resume before it finished, or once quitting has begun.
- Suppressed when the main window is visible and focused at that moment (Judy's call; the dashboard already says it).
- Body `Paused. Gemma released from GPU.` or, on release failure, `Paused. GPU release not confirmed.` Same words as the tray tooltip.
- No retry on a `failed` event: the tray tooltip is the persistent record.

**Not provided (Sergei 2026-10-12, A3a: no).** No toast when a verification is needed while the window is hidden. The amber "!" badge and the tooltip carry it.

Agent and QA launches never raise either notification on Sergei's machine (§7, F5).

## 3. Quit flow (tray Quit, Ctrl+Q, the Alt menu's Exit, or any `app.quit()` route)

Everything below runs in the **main process**: it talks to the service directly and does not wait on the renderer (see F1).

### Pause ownership and the next start (Sergei 2026-10-12, A1: auto-resume, yes)

Two kinds of pause exist. A **user pause** is one Sergei set: the dashboard Pause button or the tray item. A **shell pause** is the temporary one Quit and install place. Only a user pause survives a restart: the next start comes up Processing unless a user pause is on record. If Sergei had paused before quitting, the next start stays paused and the tray and dashboard say so (no extra copy needed).

- Cancel returns to whichever existed at the moment the flow began (user pause stays, processing resumes).
- The record must survive a cut-short quit: `Quit now`, the 10-minute fallback and a sign-out must never leave a shell pause stored as a user pause. The mechanism is Ender's; the service's pause persistence today treats every pause alike.
- The same rule covers the relaunch after an update install (§4).

### Timeline

| Time | What happens | What Sergei sees |
|---|---|---|
| 0 s | Menu closes. Record the state: user-paused or processing, and whether Gemma is already released. If Paused and Gemma already released: stop the engine and exit now. If the service is unreachable: exit after at most 3 s. Otherwise request a shell pause (skip if a pause is already requested). | Tray tooltip `Comic Metadata — Quitting…`; menu item 3 reads `Quitting…` (disabled). |
| to 1.5 s | Poll pause status every 0.5 s. When Paused and `gpu_released` (or a release error) arrives, exit. | Nothing; no window flash on the fast path. |
| 1.5 s | Not finished: `showInactive()` the window (no focus change) and open the stopping dialog at whatever stage it has reached. | Dialog below. |
| Paused, Gemma still unloading (A5) | Keep waiting for `gpu_released` or an error. Quit now is available. | `Paused. Releasing Gemma from GPU…` |
| Gemma released | Stop the engine, then exit. Buttons disabled from here (nothing left to cancel). | `Gemma released from GPU. Closing…` for at most 1 s. |
| Release error | The wait is over: stop the engine, then exit. | `GPU release not confirmed. Closing…` for at most 1 s. |
| 60 s, still not Paused | Pausing stuck copy. Keep waiting; do not kill. | Stuck copy below. |
| 30 s after Paused, Gemma not released | GPU stuck copy. Keep waiting; do not kill. | Stuck copy below. |
| 10 min from 0 s (A4) | Force exit (the force-quit fallback of ProcessRules § The close button; conflict noted in F1). Placeholder: Ender measures the longest legitimate time to Paused (large archive write, in-flight search) and sets the cap above it. | Window closes. |
| Windows sign-out or shutdown | Request a shell pause, exit within about 3 s, no dialog, no GPU wait. Interrupted writes keep their recovery backup by design. | Nothing. |

Ender measures two things to replace placeholders: the longest legitimate time to Paused (sets the 60 s and 10 min figures) and Gemma's unload time (5 unloads, record the p95; sets the 30 s figure above it). Ender also confirms where Gemma runs (inside the engine process or beside it): it decides what `Quit now` does to the GPU, and the GPU-stage `Quit now` tooltip below assumes Gemma may stay loaded.

### Stopping dialog (shared with §4 install)

Dialog-styled to match the dashboard's `dialog` (`#1b202b`, 1px `#485771`, 16px radius), 440 px wide, auto height, centred over the main window, not resizable, no minimize or maximize. Modal: while it is open nothing in the dashboard is reachable, so Resume or a manual action cannot undo the pause the quit is waiting for. It is the sanctioned class in ProcessRules § No UI element may cover another (modal, dismissible). It must work when the dashboard page is hung or failed to load; a modal child window owned by the main process fits, Ender's call.

Install reuses every stage below, including the GPU release (Judy's extension of A5, which named Quit only: one dialog, one set of words; it adds seconds, not steps).

| Element | Quit | Install |
|---|---|---|
| Title (h2, 20 px) | `Quitting Comic Metadata` | `Installing v{X}` |
| Status line (`role="status"`, polite), stage 1 | `Pausing — finishing the current operation. Progress is saved.` | same |
| Detail, after 5 s, only while `waiting_for` is non-empty | `Waiting for: comic processing · browser search` | same |
| Stage 2: Paused, Gemma unloading | `Paused. Releasing Gemma from GPU…` | same |
| Stage 3: Gemma released | `Gemma released from GPU. Closing…` | `Gemma released from GPU. The app restarts to install.` |
| Stage 3: release error | `GPU release not confirmed. Closing…` | `GPU release not confirmed. The app restarts to install.` |
| Stage 1 stuck, 60 s | `Still pausing. A comic write or search is taking longer than usual.` plus `Quit now exits without waiting. An interrupted write keeps its recovery backup.` | `Still pausing. A comic write or search is taking longer than usual.` |
| Stage 2 stuck, 30 s | `Still releasing Gemma from GPU.` plus `Quit now exits without waiting. Gemma may stay on GPU.` | `Still releasing Gemma from GPU.` |
| Service unreachable | `The local service is not responding. Closing…` | not applicable (install needs the service to pause) |
| Buttons | `Cancel quit` (primary, default focus, Esc), `Quit now` (secondary), both from the moment the dialog opens | `Cancel install` (primary, default focus, Esc). No force option: the installer must not replace a live service. |

- `waiting_for` values map `metadata` to `comic processing` and `browser` to `browser search` (Ender confirms the mapping; internal names never reach the screen). The detail line is plain text, written only when its content changes.
- Both buttons are disabled once the engine stop has begun (stage 3), so no click can race the exit.
- Cancel returns to the state at the moment the flow began (see Pause ownership): if processing was running it resumes; if Sergei had paused it, it stays paused. Dialog closes, tray tooltip and menu restore, focus returns to the window's `#pauseControl` for Quit. For Install the banner is back at Ready and focus goes to its `Install and restart`, where Sergei started (§4; Revised 2026-10-26, Sergei bug).
- `Quit now` stops the service immediately and exits. No further confirmation: it is the escape hatch and the dialog already names the consequence. It sits in the same place in every stage.
- Second launch during the dialog focuses it. Tray Open focuses it.

| Button | Tooltip |
|---|---|
| Cancel quit | `Stop quitting. Processing resumes unless you had paused it.` |
| Cancel install | `Stop the install. Processing resumes unless you had paused it.` |
| Quit now, stage 1 | `Exit without waiting. An interrupted write keeps its recovery backup.` |
| Quit now, stage 2 | `Exit without waiting. Gemma may stay on GPU.` |

The Quit now tooltip changes with the stage and is written only when the stage changes. If Ender finds Gemma lives inside the engine process (so stopping it always frees the GPU), the stage 2 tooltip and stuck copy drop the Gemma sentence.

## 4. Update banner

### Placement and layout

One in-flow block directly after `</header>` and before `#error`. Header and Pause button never move; only content below shifts, and only when the banner appears, changes state or goes away. It never covers another element and has no sticky or fixed positioning. Not at the bottom (off-screen on a long page) and not in the header group (it would crowd the version badge and Pause).

- `<section aria-label="App notices">`; inside it a `<p role="status" aria-live="polite" aria-atomic="true">`. The same slot serves §5's service banner. One banner at a time: service problem first, then update. A dismissed update stays dismissed until the app restarts, a newer version appears, or Sergei runs `Check for updates` (§4a).
- Box: background `#24364c`, 4 px left bar `#bcd8f9`, radius 14 px, padding 12×16, margin-bottom 20 px (same rhythm as `.panel`), min height 56 px. Text 16 px / 1.5, `#e7eaf1` on `#24364c` = **10.21:1**. Failure variant: background `#402b29` (the existing `#error` colour), left bar `#e08a7e` (5.08:1 on that background), text `#e7eaf1` = **10.93:1**.
- Row: text grows (`min-width: 0`, wraps anywhere), actions on the right with an 8 px gap; at narrow widths actions drop below the text, left aligned. A state word opens every message, so meaning never depends on colour.
- Buttons: native `<button>`, tab order after the header, Enter and Space activate. Primary: 10×14 padding, min height 40, `#385ea1` fill, `#eef2fb` text (**5.70:1**), 1 px `#bcd8f9` border (**8.39:1** on the banner). Hover keeps the fill and adds an inset 1 px `#bcd8f9` (do not inherit `#4776c6`, 4.01:1). Focus-visible: 2 px `#bcd8f9`, 2 px offset. Secondary: `#242c3b` fill, `#eef2fb` text (12.50:1), 1 px `#aab4c6` border (**5.89:1** on the banner). Dismiss: 32×32, `×` glyph, transparent, 1 px `#aab4c6` border, `aria-label="Dismiss update notice"`.
- Focus never moves on its own. After a click removes the focused button, focus goes to the banner's next button; if the banner has no button left (Waiting, below), to the banner's message line; only if the banner itself goes away, to `#pauseControl`. Do not jump to the page top. (Revised 2026-10-26, Sergei bug: the middle clause is new.) Download is the same case (Judy 2026-10-26, Ender's question: keep): Downloading has no button, so focus goes to its message line, not `#pauseControl`, where a repeated Enter would pause processing; when it becomes Ready or Failed, focus follows to that state's first button, because the focused line is replaced.
- Download progress uses a native `<progress>` (6 px high, fill `#bcd8f9`, track `#12151c`, accessible name `Update download`) under the text. Update it at most twice a second and do not announce percentages; announce only the state changes (start, ready, failed).

### States

| State | Text | Buttons (tooltip) |
|---|---|---|
| Available | `Update available — v{X}` | `Download` (`Download v{X}. Installing is a separate step.`); `×` (`Hide this notice until the app restarts.`) |
| Downloading | `Downloading v{X} — {n}%` plus the progress bar | none |
| Ready | `Update ready — v{X}` | `Install and restart` (`Pause processing, install v{X} and restart the app.`); `×` (same dismiss tooltip) |
| Confirm (after Install and restart) | `Install v{X}? Processing pauses first, then the app restarts.` | `Pause and install` (`Pause processing, then install and restart.`); `Cancel` (`Go back. The update stays downloaded.`). Default focus on Cancel. |
| Waiting: from `Pause and install` until the installer starts (Revised 2026-10-26, Sergei bug) | `Installing v{X}… Processing pauses first, then the app restarts.` The §3 stopping window (Install column) opens over it if the pause runs past 1.5 s. | none, and no `×`. No Cancel here: Cancel lives in the stopping window (`Cancel install`), by Sergei's ruling. Detail in "Waiting and timeout" below. |
| Failed, download | `Could not download v{X}. Check your connection and try again.` | `Try again` (`Download v{X} again.`); `×` |
| Failed, damaged download | `The download of v{X} is damaged. Download it again.` | `Try again` (`Download v{X} again.`); `×` |
| Failed, installer | `Could not start the installer. Try again.` Processing is resumed to its earlier state first. The wording of this row is superseded by `ComicsMetaOrganizer_UXSpec_UpdateOutcome_2026-10-14.md` ("Proved not started": `The installer for v{X} did not start.`, `Try again`, `Open log folder`). | `Try again` (`Install v{X} again.`); `×` |
| Failed, installer: processing did not pause in time (Revised 2026-10-26, Sergei bug) | `The installer for v{X} did not start because processing did not finish pausing within 10 minutes.` Detail line as UpdateOutcome: `The downloaded installer is kept. You can try installing again.` | `Try again` (`Try starting the downloaded installer for v{X} again.`); `Open log folder` (`Open the logs for this update attempt.`); `×`. Detail in "Waiting and timeout" below. |
| Failed, unknown | `The update failed. Try again.` | `Try again` (`Try the update again.`); `×` |
| Check failed (manual check only, §4a) | `Could not check for updates. Check your connection and try again.` | `Try again` (`Check for updates again.`); `×` |

"Checking" and "Up to date" are not banner states: the manual check shows them on its own button (§4a), so a result that needs no action never moves the page.

- Raw updater messages go to the log, never the screen (QuickLaunch prints `UPDATE ERROR: {msg}`; do not copy that).
- Automatic checks are silent when up to date or when they fail (offline is not news). Cadence: once at launch after the service is ready (QuickLaunch checks 5 s after launch), then every 24 h while running; the manual check is in addition (A7). A long-running tray app that checks only at launch would sit on stale versions.
- Update states survive the window being hidden; the banner reflects the current state on show. Dismiss clears the tray suffix too.
- Check only, no auto-install, no install on quit: electron-updater `autoDownload` and `autoInstallOnAppQuit` stay off, as in QuickLaunch. Ender verifies the downloaded file before quitting; on any failure resume the earlier state and show the matching Failed row.
- Install sequence after confirm: pause, wait for Paused and the GPU release (same stuck copy, Cancel only), stop the service, install, relaunch. The relaunched window opens at its remembered bounds. Processing resumes on that start unless Sergei had paused it himself (§3 pause ownership; Sergei 2026-10-12, A1). The banner shows Waiting from the press to the app closing (Revised 2026-10-26, Sergei bug).

### Waiting and timeout (Revised 2026-10-26, Sergei bug)

Why it exists. Until 0.3.0 the banner went back to Ready the moment `Pause and install` was pressed, so `Install and restart` was offered a second time while the pause ran. Sergei's rulings: no second offer; no Cancel on the waiting banner (Cancel stays in the stopping window); the timeout banner says why.

**Waiting.**

- **Text.** `Installing v{X}… Processing pauses first, then the app restarts.` Why not Sergei's interim sentence (`Please wait while we park the process and install the new version.`): the copy standard cuts "Please wait" (the banner has no control, so waiting is the only thing there is to do), "we" (nobody to name) and "park the process" (internal word; the dashboard says pause). What stays is the state word first (§4 rule), the same verb as the stopping window's title and the tray (`Installing…`), and the restart promise from the Confirm banner, which is the one thing Sergei must expect. The version is always known in this state, as in Confirm.
- **One banner for both updater phases.** The updater publishes `parking` (until the installer launches) and `installing` (launched, app about to exit). They render identically and the banner is not rebuilt between them: same render key, so nothing is re-announced and focus is not re-placed.
- **Look.** The default variant (`#24364c`, 4 px left bar `#bcd8f9`; not the failure variant), text 16 px `#e7eaf1` (**10.21:1**), min height 56 px. No buttons, no `×`, no progress bar, no spinner; no new colour or token. Why no spinner: the Downloading bar shows measurable progress and this wait has none; the other no-button waiting banner (service Restarting, §5) is text only, so Sergei meets one idiom; a loop running for up to 10 minutes is the ambient animation this studio avoids; and liveness belongs to the stopping window, which opens after 1.5 s with stage text and the stuck copy. The `…` is the only motion cue. If Sergei wants motion anyway, the §5 spinner applies unchanged.
- **Height and gaps.** Confirm is 64 px high (40 px buttons); Waiting is 56 px. Content below moves up 8 px, which the placement rule allows; the header and Pause never move. The actions container is not rendered when it has no buttons (Waiting, and Downloading, which has none either): an empty flex item still adds the 16 px column gap beside the text, and at 640 px and narrower its 100% basis puts it on its own line and adds 8 px of dead space under the text (read from the CSS; Futaba measures).
- **Announcement.** The existing `role="status"` message, once, on entering the state. The text has no percent or count, so nothing changes while it is shown.

**Controls while Waiting** (the set Downloading, Confirm and Quitting already lock; Sergei sees one rule):

| Control | State | Tooltip |
|---|---|---|
| `Check for updates` | label unchanged, disabled | `Unavailable while updating or quitting.` |
| `API keys` | disabled | `Unavailable while updating or quitting.` |
| Tray menu item 2 | disabled from the press (§2) | none: native menu items carry none (F2); the tray tooltip is `Comic Metadata — Installing update…` |

Both header strings are the existing ones; Futaba hovers each disabled control and reads the tooltip as rendered, since a native `title` on a disabled button is the case §4a already relies on. **Decided 2026-10-26 (Sergei: "lock it"; Judy: copy kept):** the dashboard's own `Pause & release GPU` is disabled for the whole Waiting span, until the installer starts or the attempt ends, with the same tooltip `Unavailable while updating or quitting.` as the two controls above (one reason, one string); an unlocked click would set a user pause that survives the restart (§3 pause ownership). Futaba hovers it too.

**Focus after `Pause and install`: the banner's message line** (`tabindex="-1"`, focused by script, not in the tab order). The press removes the focused button and Waiting has no other, so the §4 rule applies. Why not `#pauseControl`, where 0.3.0 lands: Space or Enter there pauses or resumes processing, and a pause set by a stray key during the wait is a user pause that survives the restart. Why not `body`: the keyboard and screen-reader position is lost. The message line is inert (stray keys do nothing), sits where Sergei was looking, and matches the §5 failure page (after Try again, focus goes to the status line). It happens only when focus was inside the banner, which is always true after pressing a banner button, so it never takes focus from anywhere else. From the message line focus follows the rest of the flow by the same rule: a failure puts it on `Try again`; `Cancel install` in the stopping window leaves the banner at Ready with focus on `Install and restart`; an installer start closes the app.

**Timeout (10 minutes without a pause).** The install gives up, processing returns to the state it had (the §3 Cancel rule), the service is restarted if it was stopped, and the banner changes to the failure variant:

| Part | Text |
|---|---|
| Message (`role="status"`, announced) | `The installer for v{X} did not start because processing did not finish pausing within 10 minutes.` |
| Detail | `The downloaded installer is kept. You can try installing again.` Only when the service did not restart, add: `The local service did not restart. Processing stays stopped.` (both as UpdateOutcome) |
| Buttons | `Try again` (primary; `Try starting the downloaded installer for v{X} again.`), `Open log folder` (`Open the logs for this update attempt.`), `×` (`Hide this notice until the app restarts.`) |

- **Reason in the message, not the detail.** The detail line is not a live region, so a reason there is not announced, and "did not start" alone leaves Sergei nothing to decide on.
- **"Did not finish pausing", not "did not pause".** The same cap covers the GPU release after Paused, where the stopping window says `Paused. Releasing Gemma from GPU…`; "did not pause" would contradict what he just read. "Pausing" here is the whole pause-and-release that the dashboard button names.
- **The number is the cap.** `10` comes from the constant that sets the cap, not a second copy. If Ender retunes the cap (§3 placeholder), the string follows.
- **Other pre-launch failures** (installer check fails, service not responding, launch refused) keep the generic UpdateOutcome title with no reason until a reason is known and written for each.
- **Try again** returns to Waiting without a second Confirm (Sergei already confirmed) and focus moves to the message line again.
- **For Ender.** The failed state carries a reason, and the timeout throw gets a code so the banner does not match on message text (today a bare `Error`). The 10-minute figure and its cap share one constant.

**Nothing covers anything.** Checked from the code and CSS, not measured: the app was not launched. The Waiting banner is in flow under the header, has no control and adds no overlay. The stopping window (§3) is the one sanctioned modal over it, with its own `Cancel install`. `#error` can still slide over the banner's text when the page scrolls (§6, existing risk); the banner holds no hit area for it to steal. Futaba measures rects at 640 and 1280 px: banner box, both disabled buttons, `#pauseControl`, the version badge, and that the header and Pause do not move on the Confirm to Waiting change.

### 4a. Check for updates control (Sergei 2026-10-12, A7: yes)

**Placement.** In the header, on the version row: a wrapper `<div class="version-row">` holds the existing `#appVersion` badge and the new button side by side, 8 px gap, right-aligned like the rest of `.header-controls`; at 700 px and narrower it left-aligns with them (wrapping under the badge if it must). Reasons: version and update belong together (Jakob: an About-style spot); the row's height is fixed by the badge, so no state change here moves Pause or the status line, whereas a button under the status line would drop whenever that line wraps to two lines. Pause stays the only blue primary in the header (one primary). Tab order follows the visual order, so the check comes before Pause: one extra Tab to reach Pause, accepted for a rare action.

**Look.** Secondary style, 32 px high, padding 4×12, 14 px text, radius 8: `#242c3b` fill, `#eef2fb` text (12.50:1), 1 px `#aab4c6` border (8.74:1 on the page `#12151c`). Hover keeps the fill and adds an inset 1 px `#bcd8f9`; focus-visible 2 px `#bcd8f9` (12.46:1 on `#12151c`), 2 px offset. It overrides the global `button` fill. Disabled uses the existing 50% opacity. Minimum width equals the idle label's rendered width (Ender measures), so no label change alters the row.

**States** (feedback stays on the control; nothing moves the page unless the result needs reading):

| State | Label | Tooltip | Also |
|---|---|---|---|
| Idle | `Check for updates` | `Look for a newer version now.` | |
| Checking | `Checking…` (disabled, `aria-busy`) | `Checking for updates…` | Live region: `Checking for updates…` |
| Up to date | `Up to date` for 5 s, then Idle | `You have the latest version.` | Live region: `Comic Metadata is up to date.` |
| Update found | Idle at once | as Idle | Banner shows Available (§4), even if it was dismissed; the tray suffix returns. |
| Check failed | Idle at once | as Idle | Banner shows the Check failed row (§4). Its `Try again` runs a check and the button shows Checking until the result replaces the banner. |
| Downloading, Confirm, Waiting, Installing or Quitting | `Check for updates`, disabled | `Unavailable while updating or quitting.` | Waiting is the span from `Pause and install` until the installer starts (§4; Revised 2026-10-26, Sergei bug). |
| Ready | Idle (enabled) | as Idle | A check re-shows the Ready banner if dismissed; it never downloads again. |

- Live region: `<span id="updateCheckStatus" class="sr-only" role="status" aria-live="polite">` beside the button, written only on a state change.
- A manual check never downloads or installs by itself: a found update goes to the Available row and Sergei presses Download.
- The service banner keeps precedence over update banners (one at a time); a result waits behind it, and the tray suffix updates at once.
- The button and the banner slot are rendered only when the shell bridge is present (Ender), so the dashboard opened in an ordinary browser shows no dead control.
- Native tooltip shown on hover; the accessible description is the same string (§6).

## 5. Startup and service failure

### Startup page (local page in the main window until the service answers)

Dark page (`#12151c`), content centred in a column of at most 480 px, 16 px side gutter. `h1` `Comic Metadata` (30 px, as the dashboard), status line 16 px `#e7eaf1` (**15.17:1**), detail line 14 px `#aab4c6` (**8.74:1**). A 16 px spinner `#bcd8f9` beside the status line, rotating, replaced by a static `…` under `prefers-reduced-motion`; it exists only while Starting and ends at the failure timeout. The page navigates to the dashboard when the service answers; no intermediate flash. Tray: base icon, tooltip `Starting…`. Window title unchanged.

| Time | Status line | Detail |
|---|---|---|
| 0 s | `Starting the local service…` | none |
| 10 s | same | `This is taking longer than usual.` |
| 30 s | failure page (below) | |

The 30 s failure threshold is a placeholder. Ender measures cold-start time on Sergei's real catalog (a method for the count: 5 starts, record the p95) and sets the threshold above it.

### Failure page (same page, same width)

`h2` (20 px) + one paragraph + button row. Focus goes to the heading on arrival (`tabindex="-1"`); the heading is `role="alert"`, read once.

| Cause | Heading | Paragraph (two sentences at most, the second names the fix) |
|---|---|---|
| Process exited before answering | `The local service did not start.` | `It stopped while starting. Exit code {n}.` |
| No answer by the threshold | `The local service did not start.` | `It did not respond within {30} seconds. Try again.` |
| Port 8765 held by another program | `The local service did not start.` | `Another program is using port 8765. Close it, then try again.` |
| Service files missing (Python is bundled, A8) | `The local service did not start.` | `Its files were not found. Reinstall the app.` |
| Dashboard page fails to load although the service answers | `The dashboard did not load.` | `Try again.` |
| Unknown | `The local service did not start.` | `Open the log folder for details.` |

Note for Ender, not copy: on Sergei's machine the likeliest holder of port 8765 is the old `run.cmd` or scheduled-task copy of this service. Retire that route, or the port row will fire on first launch.

| Button | Tooltip |
|---|---|
| `Try again` (primary, first in order) | `Start the local service again.` |
| `Open log folder` (secondary) | `Open the folder with the local service logs.` |
| `Quit` (secondary) | `Close Comic Metadata.` Exits at once: nothing is running to pause. |

After Try again, buttons vanish, so focus moves to the status line. Never show raw exception text, paths or tracebacks. Tray shows Error here.

### Service stops while the dashboard is open

Keep the dashboard on screen (no navigation away: filters, scroll and open dialogs stay). Show the shell banner (failure variant), `role="status"` while restarting, `role="alert"` once on the final failure. The dashboard's own messages (`Processing progress unavailable. Retrying.`, `Status unavailable`) keep appearing; its polling recovers by itself when the service returns.

| State | Text | Buttons |
|---|---|---|
| Restarting | `The local service stopped. Restarting — attempt {n} of 3.` | none |
| Gave up | `The local service stopped and did not restart.` | `Try again` (`Start the local service again.`); `Open log folder` (`Open the folder with the local service logs.`) |

Three attempts, spaced as today's scheduled-task behaviour (README: up to three retries, one minute apart).

## 6. Hit areas and focus (every state)

No new element overlaps another on the same plane. The banner, the header's version row, the startup page and the failure page are in flow. The only overlay is the stopping dialog, a modal and dismissible. Existing `#error` is `position: sticky` and can slide over the banner while the page scrolls; this spec does not change it, Futaba measures it (§9). New controls: banner buttons, `×` dismiss, `Check for updates`, failure-page buttons, dialog buttons. Each ships with the tooltip above in its creating commit, as the native `title`, which the browser also exposes as the accessible description when the control already has its own name; Futaba confirms that in the accessibility tree. Dismiss and dialog buttons have `aria-label` or visible text that matches. Ctrl+Q has no control. Waiting banner (Revised 2026-10-26, Sergei bug): in flow, no control of its own, no overlay; the stopping window is the sanctioned modal over it; the two disabled header buttons keep `Unavailable while updating or quitting.`; focus sits on the banner's message line (§4).

## 7. Process flags (ProcessRules)

F1. **Close button must always quit** (§ The close button...). This is the recorded tray-resident exception, and it has a second condition: Quit "must end the process immediately with no renderer round-trip". Sergei's Quit waits for Paused and then for the GPU release (A4, A5), which is a deliberate delay. **Conflict noted:** the same section sets a force-quit fallback timer of 1.5–30 s for any close interceptor; Sergei chose 10 minutes (A4) because a legitimate comic write can run for minutes, and a 30 s kill would cut it mid-write. This spec continues with his choice and keeps the rule's intent: the wait is main-process only and never depends on the renderer; a visible `Quit now` exists from the moment the dialog opens (1.5 s); Quit on an already Paused and released, or dead, service exits at once; no dashboard state can wedge it; the 10-minute cap bounds everything including the GPU wait. Needs routing (Jane): a Decision Log row in `ComicsMetaOrganizer_Brief.md` (tray-resident exception, revisit trigger: a Quit or close hang), and the ProcessRules tray-resident clause should record the 10-minute cap as this tool's approved value. Judy does not edit either file.
F2. **A new control is born with its tooltip.** Native tray menu items cannot show tooltips. Treated as satisfied by self-describing labels that mirror the dashboard button plus the icon's state tooltip. The existing bare dashboard controls are audited in the separate tooltips spec (A10).
F3. **No UI element may cover another.** Modal dialog is the sanctioned class; the banner and the version row are in flow. Existing sticky `#error` is the one risk (§6).
F4. **Copy.** Every string here follows the six clauses. QuickLaunch's banner (all caps, raw updater text) is not the copy model. "Gemma" and "Google Lens" are product names the dashboard already shows.
F5. **Our tooling must not intrude.** The shell adds a single-instance lock that focuses the existing window, a service on fixed port 8765, a tray icon and two notifications. An agent or QA launch must not: focus Sergei's window, attach to his running service, fire either notification, or touch his saved window state. Required before Futaba launches anything: a safe-launch harness like `scripts/qa/quicklaunch-safe-launch.mjs` that forces a scratch user-data folder (which also isolates the single-instance lock) and a non-default service port, switches both notifications off (Ender names the switch), refuses the real profile and port, and ends only what it started. QA reports say which instance was tested. Real-launch checks, notifications included, happen in an away window Sergei states in chat. Notifications are `silent: true`; the app plays no audio.
F6. **No auto-start.** Matches the Brief ("does not start itself after a reboot"); there is no Run key to diff, unlike QuickLaunch.

## 8. Consistency with QuickLaunch (read-only reference)

| Topic | QuickLaunch | Here | Why |
|---|---|---|---|
| Tray icon state | one update dot | four states, shape plus colour | the dashboard has real states Sergei must act on |
| Update dot | magenta dot bottom right | none; tooltip suffix | the badge slot belongs to state |
| Tray tooltip | `QuickLauncher — Update available` | `Comic Metadata — {state}` | same dash pattern |
| Menu | Show/Hide, Settings, toggles, Check for Updates, Quit | Open, Pause & release GPU, Quit | Sergei's list; Hick |
| Check for updates | tray menu item | header button beside the version | keeps the tray menu at three; version and update sit together |
| Quit | `app.exit(0)` at once | pause, release GPU, exit, with escape | Sergei's decision; F1 |
| Click | double-click toggles | click opens | dashboard, not launcher |
| Update flow | Download, then Install now, banner at the bottom, 38 px, all caps | Download, then Install and restart plus confirm, banner under the header, sentence case | long page; confirm requested |
| Banner dismiss | ✕ 24×24 clears the tray dot | `×` 32×32 clears the tray suffix | same effect |
| Window | frameless popup, bottom right | framed window, centred, remembered | different job |
| Saved bounds guard | `initialBounds` | same rules | reuse the proven guard |
| App icon | illustrated laptop (pink, purple) | flat comic-page mark (teal, white) | distinct from QuickLaunch and ComixManagementTool |

## 9. Acceptance and evidence limits

Nothing here is rendered or measured yet. Futaba, per state, reports viewport, measured rects (`getBoundingClientRect()` for in-page parts, window bounds for the shell) and focus rects.

- Window: first launch, relaunch at remembered bounds, maximized restore, second monitor unplugged, a corrupt state file (each opens at defaults), second launch from hidden/minimized/Starting/Quitting, close with and without a tray icon, Alt+F4. Minimum size 640×480 and 200% zoom: header (including the version row with `Check for updates`), banner, Pause, `#error` visible, comic-details dialog open; no same-plane overlap, no obscured focus. The version row and Pause button do not move across every Check state.
- Ctrl+Q: from the dashboard, from a focused text box, with the comic-details dialog open, on the startup page and the failure page, with the window hidden (does nothing), twice in a row (second ignored), while the stopping dialog is open (does nothing). The Alt menu's Exit shows `Ctrl+Q`.
- Banner: every §4 state and §5 service state at 640 and 1280 px and at 200% zoom with long copy. Banner above `#error` visible and while scrolled, with the sticky alert in each position; buttons at least 24×24 (primary 40 high). Transitions: appear, change, go away; confirm that the Pause button never moves. `role="status"` announces on state change only, never per poll or per percent.
- Check for updates: every §4a state against a local mock feed (idle, checking, up to date and its 5 s revert, update found, dismissed then re-found, failed, blocked, Ready re-show); button width identical in every label state; live-region text announced once per change; absent in a plain browser.
- Tray: all four icon states on a light and a dark taskbar at 100% and 200% scale (crops, pixel-sampled badge contrast); each tooltip at or below 127 characters; menu labels as rendered, including `Pause & release GPU` with the ampersand visible; stale-label click does nothing; left click, double-click, right click, keyboard (Win+B, Enter, Shift+F10).
- Quit: already Paused and released (exits at once, no window), running (dialog at 1.5 s, stages 1 to 3 in order), Paused with Gemma still unloading (inject a slow unload: stage 2 copy, then stage 3), release error (stage 3 error copy, exits), Pausing already requested, service dead, Cancel from running, from stage 2 and from manually paused, Quit now in stage 1 during an in-flight write (recovery backup retained) and in stage 2, 60 s and 30 s stuck copy (inject), 10-minute fallback (inject), renderer crashed, dashboard failed to load, shutdown. Next-start state after each exit path: Processing, except after a user pause, which stays paused (A1), including after Quit now, the fallback and a sign-out. A force-kill invalidates any shutdown claim (ProcessRules § Verification Discipline). Close-timing runs use a clean profile and the real data moved aside, restored byte-identical. The shell's Quit through the tray path is the smoke path. Observe each check fail once on a known-bad input.
- Update: against a local mock feed only (no real release, no real install): available, downloading, ready, confirm, cancel, failed (three kinds), dismiss, relaunch at remembered bounds, relaunch state per A1.
- Waiting and timeout (Revised 2026-10-26, Sergei bug), same mock feed: press `Pause and install` and read the banner at every state the updater publishes (before the stopping window opens, with a slow installer check to widen that gap; window open at each stage; installer launch). Expect the exact Waiting text, no buttons and no `×`, `Check for updates` and `API keys` disabled (hover each and read the tooltip as rendered), the tray tooltip `Comic Metadata — Installing update…` with tray item 2 disabled, and no `Install and restart` at any moment. Focus lands on the message line, Space and Enter there do nothing, and nothing is announced again between the two updater phases. End states: `Cancel install` (Ready returns, focus on `Install and restart`); a 10-minute timeout, injected (exact timeout message and detail, `Try again` returns to Waiting); a launcher refusal (generic did-not-start title, no reason). Rects at 640 and 1280 px, including the 640 px dead-space check under the text. Run the no-second-offer check once against 0.3.0 behaviour as the known-bad input and see it fail.
- Startup: slow start, exit-code start, port taken, missing files, dashboard load failure, Try again, reduced-motion.
- Notifications: first close shows the first-time notice once (silent, no focus change); the `failed` path retries; second close shows nothing. Tray-started pause: one toast on finish (released, and a forced release error), none for the dashboard button, none for a shell pause, none when the window is visible and focused, none after Resume mid-pause; verification-needed raises no toast.
- Icon: §10 review gates.
- Contrast quoted above from sRGB relative luminance: `#e7eaf1` on `#24364c` 10.21; `#aab4c6` on `#24364c` 5.89; `#eef2fb` on `#385ea1` 5.70; `#bcd8f9` on `#24364c` 8.39; `#e7eaf1` on `#402b29` 10.93; `#e08a7e` on `#402b29` 5.08; `#e7eaf1` on `#12151c` 15.17; `#aab4c6` on `#12151c` 8.74; `#eef2fb` on `#242c3b` 12.50; `#bcd8f9` on `#12151c` 12.46.

## 10. App icon (Sergei 2026-10-12, A9: Judy designs, Ender produces)

**The mark.** A comic page: a tall teal plate holding three white panels, one wide on top and two below, divided by gutters. It reads as comics by shape alone. No letters, no text, no glyph. One mark at every size; nothing to learn twice.

**Why this one.** ComixManagementTool's icon is a blue book with a yellow burst; QuickLaunch's is an illustrated laptop in pink and purple. A teal page grid differs from both in hue and in silhouette, so Sergei can tell the three apart in the taskbar. It also keeps clear of the tray badge vocabulary: no red, amber or grey, and no "!", "×", pause bars or check mark. Identity rests on shape, not hue, so it holds for colour-blind viewers.

**Colour (one icon serves both taskbars, no theme variants).**

| Part | Hex | Measured contrast |
|---|---|---|
| Plate (silhouette, border, gutters) | `#1f8a80`, luminance 0.2003 (inside the 0.143–0.265 band) | 3.88:1 on dark `#202020`; 3.78:1 on light `#f3f3f3`; 5.01:1 on black |
| Panels | `#ffffff` | 4.20:1 against the plate |

Computed from the hex values with the sRGB luminance formula, not measured on a rendering. If Sergei prefers the dashboard blue, `#4776c6` passes the same test (3.63:1 dark, 4.05:1 light) but sits close to ComixManagementTool's blue. Known limit: on a Windows accent-coloured taskbar the plate can match the background; the white panels still show the layout.

**Geometry, 32×32 master** (transparent canvas, flat fills, no gradient, shadow or outline effect):

- Plate x 6–25, y 0–31 (20×32), corner radius 3. Border 2 px, gutters 2 px.
- Top panel x 8–23, y 2–13 (16×12). Horizontal gutter y 14–15.
- Bottom-left panel x 8–13, y 16–29 (6×14). Vertical gutter x 14–15. Bottom-right panel x 16–23, y 16–29 (8×14). Panel corner radius 1.

**16 px, hand-pixeled** (`.` transparent, `B` plate, `W` white; fully opaque pixels, no anti-aliasing):

```
col     0123456789012345
row  0  ....BBBBBBBB....
row  1  ...BWWWWWWWWB...
row  2  ...BWWWWWWWWB...
row  3  ...BWWWWWWWWB...
row  4  ...BWWWWWWWWB...
row  5  ...BWWWWWWWWB...
row  6  ...BWWWWWWWWB...
row  7  ...BBBBBBBBBB...
row  8  ...BWWWBWWWWB...
row  9  ...BWWWBWWWWB...
row 10  ...BWWWBWWWWB...
row 11  ...BWWWBWWWWB...
row 12  ...BWWWBWWWWB...
row 13  ...BWWWBWWWWB...
row 14  ...BWWWBWWWWB...
row 15  ....BBBBBBBB....
```

20 and 24 px are drawn on their own pixel grids from the same proportions (top panel about 40% of the height, bottom panels about 45%, 1 px border and gutters, bottom-left panel narrower than bottom-right), pixel-snapped, with no anti-aliased gutters. 32 px and larger come from the vector master.

**Badge zone.** The bottom-right 14×14 of the 32 canvas (x 18–31, y 18–31; x 9–15, y 9–15 at 16 px) holds only the plain white bottom-right panel; never put detail there. The tray composes its badge over that zone with a white ring (2 px at 32, 1 px at 16). The ring is needed: the badge fills have only 1.10–1.18:1 against the teal plate (`#707070` 1.18, `#d13438` 1.18, `#b87300` 1.10), so without it a badge would dissolve at the plate's edge. The ring against the badge fills is 4.95, 3.82 and 4.93:1 (the white-glyph figures in §2).

**Files Ender produces.**

- `icon.svg`: the 32 master, kept with the app's assets (Ender picks the folder).
- `icon.ico` containing 16, 20, 24, 32, 40, 48, 64 and 256 px frames (16–24 the hand-pixeled bitmaps, 32 and up rendered from the master, 256 PNG-compressed). Used for the window, taskbar, installer, shortcuts and the executable.
- The tray base at 32 px with its 16 px representation, from the same master, for §2's badge composition.
- No separate dark and light versions, no per-state app icon (the taskbar button never takes a badge), no animation.

**Review gates.** Before Futaba: Judy reviews crops of 16, 20, 24, 32 and 48 px on `#202020` and `#f3f3f3` at 100% scale, plus the three badged tray icons at 16 and 32 px on both. Pixel-sample the plate edge against each background (at least 3:1) and confirm the panels and gutters are distinguishable at 16 px. An accent-coloured taskbar is checked only if Sergei uses one.

## 11. Decisions record: Sergei, 2026-10-12

The ten open questions are closed. Source for every row: Sergei's answers of 2026-10-12, relayed by Jane.

| # | Question | Answer | Applied in |
|---|---|---|---|
| A1 | Resume automatically after Quit or an update install? | Yes. Only a pause Sergei set himself survives a restart. | §3 pause ownership; §4 install sequence |
| A2 | Product name | `Comic Metadata` | everywhere |
| A3 | Silent notifications | (b) tray-started pause finished: yes. (a) verification needed while hidden: no. | §2 notifications |
| A4 | `Quit now` and a 10-minute forced fallback | Yes | §3; F1 (conflict with ProcessRules noted) |
| A5 | Quit waits for Gemma to leave the GPU, not just Paused | Yes; waiting copy and state specified | §3 timeline and dialog |
| A6 | `Ctrl+Q` window-level quit | Yes | §1, §3 |
| A7 | Manual `Check for updates` control | Yes, in addition to launch and every 24 h; placement, tooltip and result states specified | §4a |
| A8 | Does the app own the engine; is Python bundled? (settled by Ender) | The app starts and stops the bundled Python engine itself | §5 |
| A9 | App icon | Judy designs; Ender produces; must read at 16 px on light and dark taskbars | §10 |
| A10 | Tooltip pass over bare dashboard controls | Yes, as a separate spec | `ComicsMetaOrganizer_UXSpec_DashboardTooltips_2026-10-12.md` |

**Judy's calls beyond the answers** (Sergei can overrule any; none blocks Ender): install also waits for the GPU release (§3); the tray-pause toast is suppressed while the window is visible and focused (§2); the tray's Quit item shows no `Ctrl+Q` (§2); Check for updates reports Checking and Up to date on its own button instead of the banner, to avoid a page jump when the notice vanishes (§4a); the icon is teal, to stand apart from ComixManagementTool (§10).

### Revision 2026-10-26 (Sergei bug)

Sergei's rulings: the waiting banner has no Cancel (Cancel stays in the stopping window), and after the 10-minute timeout the banner says why processing did not pause in time. His interim sentence was a placeholder; the final copy, the look and the focus rule are in §4 "Waiting and timeout". The question of locking the dashboard's own Pause button during the wait is answered (2026-10-26): locked, copy unchanged (§4 "Controls while Waiting").

**Remaining items** (none needs Sergei):

- Ender measures or confirms: cold-start p95 (30 s threshold); longest legitimate time to Paused (60 s and 10-minute figures); Gemma unload p95 (30 s threshold); where Gemma runs (what `Quit now` does to the GPU); how a shell pause is kept apart from a user pause across a cut-short quit; the idle width of the Check button; the safe-launch harness switch for notifications.
- Jane routes: the Brief Decision Log row for the tray-resident exception, and the ProcessRules wording for the 10-minute cap (F1).
- Judy: icon crop review once Ender renders the files.

Basis: [studio desktop-utility UX reference](../../../Team/Research/UX_AppBestPractices.md) § Tray / menu-bar apps and § System integration; Jakob (Windows tray conventions, About-style version spot, `Ctrl+Q`), Hick (3-item menu), Fitts (banner and primary actions at standard sizes), NN/g visibility of status, user control and freedom (Cancel quit, Cancel install, Quit now), error prevention (confirm), recover from errors; WCAG 2.2 AA (contrast, 1.4.11 non-text contrast for the icon, 2.5.8 target size, 2.4.11 focus not obscured, 4.1.3 status messages, 1.4.10 reflow, 2.2.2 for the spinner); Fluent (OS notifications, Focus Assist). Process pointers: [ProcessRules](../../../Team/Docs/ProcessRules.md) § Desktop App / GUI Rules (close button, no UI element covers another, tooltip at birth, copy standard, tooling must not intrude).

Exclusions: UI code, git and release operations, edits to any other file, the running service, QuickLaunch and ComixManagementTool (read only, icons viewed from the scratchpad), the Brief's Decision Log and ProcessRules (Jane routes), product scope beyond the items briefed. Disk hygiene: contrast scripts and two decoded icon previews were left in the session scratchpad and are removed at task end.
