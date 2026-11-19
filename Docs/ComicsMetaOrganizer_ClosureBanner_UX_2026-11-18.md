# Comics Meta Organizer — Quit wait and "previous session still closing" (UX spec), rev 3

Author: Judy. Date: 2026-11-18 (rev 3: 2026-11-19). Branch: `ender/0.6.7-fixes`. Status: rev 2 draft for Sergei, uncommitted (Sully commits it before Ender is briefed). Rev 3 (copy fix for 0.6.8) is the first section below; uncommitted.
Rev 2 replaces rev 1 (the refused-Quit banner and startup screen). Sergei approved a design change today that removes the refused Quit. Rev 1 stays at the bottom as history. **Where the two differ, rev 2 wins, and nothing under "History" is built.** **Rev 3 changes only the quit dialog's wording; where it differs from rev 2, rev 3 wins.**

## Rev 3 (copy fix), 2026-11-19

**Source.** Futaba's TrayQA v0.6.7 finding 1: with the engine frozen, Quit takes about 65 s from the click. The Closing stage waits up to 30 s with both buttons disabled and no time shown; then the ending state says `This can take up to 30 seconds.` and waits up to 31 s more. **Sergei's ruling:** fix the wording; the waits stay as they are. Nothing in this section changes timing, controls, sizes or colors.

### C1. What happens, what the user read (default wait, measured in TrayQA v0.6.7 §1)

| From the click | Dialog showed | What was true |
|---|---|---|
| 1.6 s | Pausing text | Pause and GPU stages, about 3.4 s here; no time limit stated (unchanged, C6 item 2). |
| 3.4 s | `Gemma released from GPU. Closing…`, both buttons disabled, no time | Up to 30 s more, then the ending state. Nothing said so. |
| 33.4 s | `Stopping the local service…` / `This can take up to 30 seconds.` | True: up to 30 s more (31.2 s measured). But a user who had waited 30 s already read it as the whole wait. |
| 64.6 s | Process ends | Closing 30 s plus ending 31 s: about 61 s after Closing began. |

**The gap is the Closing stage.** The ending text is a true remaining time; the Closing stage states no time, and the 30 s it holds is never accounted for. Rev 2 R4 item 3 and R5 item 1 also read as one 30 s / 31 s wait from the click (corrected in C5).

### C2. The rule

**Every stage that waits states the longest time remaining from the moment it appears.** Not time elapsed, not time from the click. Each string then stands alone and the numbers count down: 60, then 30.

- **Ending state:** `closureWaitSeconds` (the broker's wait). Unchanged.
- **Closing stage:** `2 × closureWaitSeconds`: the Closing wait, then the ending wait.
- **The source of the number** is the policy field `closureWaitSeconds` (default 30; `CLOSURE_WAIT_S` in `engine.cjs`, overridden by `qaPolicy.closureWaitSeconds`; the shell's `engine.closureWaitS`). The shell sends `waitSeconds` with the closing state, as it already does with the ending state; the dialog shows `2 × waitSeconds` in Closing and `waitSeconds` in the ending state. No literal `30` or `60` appears in any string. With the policy at 12 the dialog says 24, then 12. Ender comments the `2` in code: it is the two waits of `graceful-stop.cjs`.
- **The shell's extra second** (`wait + 1 s`, R4 item 3) is a backstop for a broker that never answers. It is not shown, as in rev 2: the text states the broker's wait, and the 1 s is under what a person can tell. Futaba allows 2 s (C7).
- **Singular:** the number 1 reads `1 second`. Only a QA policy of 1 can produce it; the default never does.

### C3. Exact strings, before → after (quit mode)

| # | Where | Before | After |
|---|---|---|---|
| 1 | Closing, detail (`#detail`) | empty | empty for the first 5 s of the Closing stage; from 5 s: `This can take up to 60 seconds.` |
| 2 | Closing, `Cancel quit` tooltip (button disabled) | `Stop quitting. Processing resumes unless you had paused it.` | `Cannot cancel: the app is already closing.` |
| 3 | Closing, `Quit now` tooltip (button disabled) | `Exit without waiting. An interrupted write keeps its recovery backup.` | `The app is already closing and exits by itself.` |
| 4 | Ending state, status and detail | `Stopping the local service…` / `This can take up to 30 seconds.` | **Unchanged.** The 10 s sentence and everything else in rev 2 R1 stay. |
| 5 | Closing, status line | `Gemma released from GPU. Closing…` or `GPU release not confirmed. Closing…` | **Unchanged.** |

**In the Closing stage the detail is only row 1.** Today `stopping.js` can add `Waiting for: …` (from 5 s) and, when the quit has run 60 s or more, `Quit now exits without waiting. An interrupted write keeps its recovery backup.` to the Closing detail: the second is false there, because Quit now is disabled. In Closing neither is shown. The Pausing and GPU stages keep their detail lines exactly.

**Why 5 s.** It is the dialog's own threshold for `Waiting for` (`elapsed >= 5000`). A healthy quit leaves Closing quickly, so the number never flashes there; a stuck one shows it at 5 s, which is early in a 30 s wait. The sentence appears by the same mechanism as the ending state's 10 s sentence (shell-driven, so the QA clock controls it). It is announced once: the detail is a live region before its text is set (`role="status"`, as the ending state does).

**Tooltips.** Rows 2 and 3 replace tooltips that promise actions a disabled button cannot do; they say why the button is off. Native `title`, set in the commit that changes the dialog. A disabled button is skipped by Tab, so the detail line, not the tooltip, carries the time.

**How it reads, default wait:**

| From Closing's start | Dialog |
|---|---|
| 0 s | `Gemma released from GPU. Closing…`, buttons disabled |
| 5 s | + `This can take up to 60 seconds.` |
| 30 s | `Stopping the local service…` / `This can take up to 30 seconds.`, buttons hidden |
| 40 s | + ` An interrupted write keeps its recovery backup.` |
| up to about 61 s | Process ends |

### C4. Not chosen, and why

| Option | Verdict | Reason |
|---|---|---|
| Ending says `up to 60 seconds` or `30 more seconds` | No | False when the ending state comes first (Quit now, the error path, engine not ready): no earlier wait exists. `more` also refers back to a state the string does not show. |
| Closing shows the number at once | No | A healthy quit passes through Closing and would flash a 60 s warning it does not need. |
| Closing says only `This may take a while.` | No | Not specific; the user cannot decide anything from it. |

### C5. Rev 2 lines this corrects

- **R4 item 3:** the shell exits within `wait + 1 s` of the *ending state* beginning, not of the click. From the click, a silent broker gives: pause stages + `wait` (Closing) + `wait + 1 s` (ending): 64.6 s measured at the default.
- **R5 item 1** "the time the process ends (at most 31 s)": at most `wait + 1 s` after the ending state begins; at most `2 × wait + 1 s` after Closing begins (about 61 s at the default). From the click, add the pause stages.
- **R1 table, row "Pausing, GPU, closing stages | Unchanged":** Closing now carries rows 1 to 3 above; Pausing and GPU are unchanged.
- **R6 item 1** (end Closing after one wait) is built (`graceful-stop.cjs`); this section is what makes it visible.

### C6. Not specified here (offered, not started)

1. **Install mode.** Its Closing stage ends only at the pause cap, with no forced path, so no number is true there; its text is unchanged. Its disabled `Cancel install` carries the same promising tooltip as row 2. Not specified.
2. **Pausing and GPU stages** state no time because they can last up to the 10-minute cap; `Quit now` is live there and says what it does. Unchanged.
3. **Exact-to-the-second text** (`31`) would cost a number that looks like a bug. Not recommended.

### C7. Checks for Futaba (measured)

Harness as in 0.6.7: freeze the broker (`tests/debug_hold.py --pid <broker python.exe> --mode freeze`), hold at least `2 × wait + 40` s (100 s at the default), sample the dialog's text and tooltips from inside the app every 100 ms (no OS key, mouse or focus). Times in ms from the click. A string check run with `closureWaitSeconds` below 5 never shows row 1 (Closing ends first): use 30 or 12.

1. **Default wait, tray Quit.** The Closing status shows with the detail empty; the detail becomes exactly `This can take up to 60 seconds.` 5.0 s after Closing began (±0.5 s); the ending state shows `Stopping the local service…` / `This can take up to 30 seconds.` about 30 s after Closing began; the 10 s sentence 10.0 s after that.
2. **Stated-remaining test, the measure that fails if the copy lies.** For every sampled text with a number N at time t: `exit time − t ≤ N + 2 s`. 0.6.7's own run (Closing at 3.4 s, ending at 33.4 s, exit at 64.6 s) is the input: with the new text it must pass; with the 0.6.7 text there is no number in Closing, so the check has nothing to hold there, which is the defect.
3. **Policy 12.** Closing detail `This can take up to 24 seconds.`, ending `This can take up to 12 seconds.`; exit within `2 × 12 + 1 + 2` s of Closing beginning. No literal 30 or 60 in `desktop/stopping.js` or the shell's stage state.
4. **Healthy quit, five runs** (tray Quit from the ready dashboard): the Closing detail is empty in every sample; row 1 never shows. Positive control: check 1 shows it.
5. **Tooltips in Closing:** read `title` on both disabled buttons: rows 2 and 3 character for character; both buttons disabled; no `Quit now exits without waiting` and no `Waiting for` in the detail. Feed the DOM test a closing state with `elapsed: 70000`, `waiting_for: ['metadata']` and the late flag set, and confirm the detail is exactly row 1. **Positive control:** the same feed on the 0.6.7 dialog shows the old suffix.
6. **Quit now during Pausing** (no Closing stage): the ending state reads `up to 30 seconds`; process ends within 31 s + 2 s of the ending beginning.
7. **Ending-state regression:** buttons hidden, Escape and the window's close button do nothing, the 10 s sentence appears once (rev 2 R5 items 2 and 4 still pass).
8. **Install mode regression:** Closing reads `Gemma released from GPU. The app restarts to install.`, no time sentence, `Cancel install` tooltip unchanged.
9. **Rects at 440 px, before and after the sentence appears:** detail and buttons do not overlap, both buttons at least 40 px high and fully inside the window, nothing scrolls. Strings and rects are measured offscreen; because a line is added to a visible dialog, one visible run is needed before Sergei sees it (focus checks need his permission, as in rev 2 R5).
10. **Number 1:** DOM feed with `waitSeconds: 1` in the ending state reads `This can take up to 1 second.`
11. Compare the shipped strings in rows 1 to 3 with this section character by character.

## Current spec (rev 2)

**The design this serves (Sergei, 2026-11-18, Ender's):** Quit always closes the app. The broker waits up to 30 s for every engine part to end, re-terminating every 5 s. If a part is still finishing a disk operation, the app exits anyway and leaves `locks/leftover-<owner>.json`. At the next start the broker reads the record: parts gone means a normal start; parts alive means the start fails with exit code 123 and the shell shows "previous session still closing". A reboot clears the record; a corrupt record falls back to checks and never blocks for good. The `CLOSURE_UNCONFIRMED` guard is removed.

**Read for this spec** (working tree of `ender/0.6.7-fixes`): `desktop/main.cjs`, `graceful-stop.cjs`, `engine.cjs`, `stopping.html`, `stopping.js`, `startup.html`, `startup.js`, `static/shell-ui.js`. Nothing was run or changed.

### R0. What changed from rev 1

| Rev 1 | Rev 2 |
|---|---|
| Option C and banner states B1–B3 | Removed. Nothing remains on the dashboard (R3). |
| B4 / S4 "cannot be checked", the Task Manager line, `closureFinal` | Removed with the guard. |
| Startup states S1–S3 (refused Quit) | Replaced by P1–P3 (R2): a different cause (a previous session), a different action (Try again re-checks it). |
| Tray label `Local service could not be stopped…` | Replaced by a P label (R2). |
| §4 "a refused action must show the refusal in words" | Kept as a general rule. Try again in P obeys it: every check shows a new check time. |
| §7 item 1 (Quit anyway) and item 2 (a refused tray Quit shows nothing) | Resolved by the design: Quit always ends the process, and its wait is shown (R1). |
| §7 item 3 (Task Manager line) | Void. |
| §7 item 4 (the banner's Open log folder ignores a failed open) | Still open, still not specified (R6). |

### R1. Quit's wait (up to 30 s)

**What exists today.** Quit already has a surface: the modal quit dialog (`stopping.html`, 440 px, parent = main window). Its stages are pausing and GPU (shown from 1.5 s) and closing (shown at once), with Cancel quit and Quit now. When the main window is hidden, the window is shown without focus (`showInactive`); the dialog itself is shown with `show()`, which takes focus. Both are unchanged for the existing stages. Two gaps matter once the forced wait can reach 30 s:

1. Forced paths have no ending state. With the engine not ready or on the setup page there is no dialog at all. With Quit now, the 10-minute cap or two failed status calls, an open dialog keeps its pausing text and live buttons for the whole wait.
2. On the error path the stopper's `finished` event closes the dialog and clears `state.stopping` before `forceStop` starts. The tray Quit item re-enables and nothing is on screen for the whole wait.

**Rule: one continuous Quit state, on one surface.** From the moment Quit is accepted until the process exits, `state.stopping` stays set and the quit dialog is the only surface. This holds on every path and from every origin: tray Quit, File > Exit, Ctrl+Q, the window close button when there is no tray, and the Quit button on the startup and installer screens. The dashboard needs nothing: it already locks its update and pause controls with `Unavailable while updating or quitting.`

| Moment | User sees |
|---|---|
| Quit accepted | Tray tooltip and menu read `Quitting…` and tray Quit is disabled (existing). The window is unchanged. |
| Pausing, GPU, closing stages | Unchanged: the dialog shows them as today. |
| Ending begins (forced termination, any path) | An open dialog switches to the ending state in the same frame, including when Quit now is pressed. With no dialog yet (engine not ready, setup page, error path), one appears no later than 1.5 s after Quit was accepted, and not at all if the app has already exited. If the window was hidden (tray Quit), it is shown without focus. |
| Ending, 10 s in | The detail line gains the recovery-backup sentence. |
| Process exits | Dialog and tray icon disappear. No message: the app is gone, and the next start tells the user if anything is left (R2). |

**Ending state of the quit dialog** (no new sizes, colors or controls):

| Element | Content |
|---|---|
| Title | `Quitting Comic Metadata` (existing) |
| Status line | `Stopping the local service…` (existing string; the startup screen uses it for the same state) |
| Detail, first 10 s | `This can take up to 30 seconds.` The number comes from the broker's wait constant, not a literal. |
| Detail, from 10 s | `This can take up to 30 seconds. An interrupted write keeps its recovery backup.` (second sentence is existing copy, see R6 item 3) |
| Buttons | None. Cancel quit cannot work once termination has begun, and Quit now has nothing left to skip. The action row is hidden, not emptied, so no gap remains. |
| Escape and the window's close button | Do nothing. The current Escape handler tests only `cancel.disabled`, which a hidden button is not, so the handler must test the state. |
| Tooltips | None needed: no control is born here. Existing Cancel quit and Quit now tooltips are unchanged in their stages. |

**Focus and announcements.** If the focused button (Quit now) disappears, focus moves to the status line, which gets `tabindex="-1"`. A dialog first created in the ending state is shown with `showInactive()` and takes no focus: the user pressed Quit seconds earlier and may be in another app. The status line is `role="status"` (existing); the 10-second detail change is announced once.

**Tray, hidden window.** The tray gives the immediate answer (`Quitting…`, disabled item). The dialog at 1.5 s is the persistent answer. A toast is not used: it can be suppressed and cannot show the time limit.

**Install mode** keeps its own title and flow; this spec does not change it. If an install path also waits on forced termination, it shows the same status and detail under its own title (Ender flags it if so).

### R2. Startup state: "previous session still closing"

**Where it shows.** The startup screen only. Every failed start loads `startup.html` (`start()` catch in `main.cjs`), including a start begun by the dashboard banner's Try again or an automatic restart. So the state needs no dashboard surface (R3).

**Screen** (existing page, existing styles; one new line, `#checked`, a plain `<p>` in the detail's style between detail and buttons, no live role):

| # | State | When | Heading (`#status`) | Detail (`#detail`) | Check time (`#checked`) | Buttons |
|---|---|---|---|---|---|---|
| P1 | Closing | Start failed with exit 123; the record is under 2 min old | `The previous session is still closing.` | `Part of the local service has not ended yet. Try again in a moment.` | `Checked at 14:32:07.` | `Try again` (primary), `Open log folder`, `Quit`. All enabled. |
| P2 | Checking | Try again pressed on P1 or P3 | `Checking the previous session…` | Text kept but `visibility:hidden`. From 10 s it shows `This is taking longer than usual.` | Text kept, `visibility:hidden` | `Try again` disabled with `aria-busy="true"`, `Open log folder` and `Quit` enabled |
| P3 | Closing for a long time | As P1, record 2 min old or older | `The previous session is still closing.` | `Part of the local service has not ended yet. Try again, or restart your PC to clear it.` | as P1 | as P1 |

- **The check time is the visible result.** Without it a re-check that finds the same thing looks like a dead button, the defect rev 1 was written to fix. Format: the viewer's locale time with seconds (`toLocaleTimeString`), so every check changes it. It is also set on the first display.
- **P2 holds at least 0.5 s** before the result shows, so a fast check is still seen. Hiding with `visibility:hidden` keeps the text and so keeps the buttons where they are (rects equal across P1, P2, P3 at any width of 640 px or more).
- **P2 shows only after Try again on a P screen.** A normal start never shows `Checking the previous session…`.
- **After a check:** parts gone means the normal start phases (`Starting the local service…` and on; the buttons hide as in any start). Exit 123 again means P1 or P3 with the new time. Any other failure shows its own existing screen (`PORT_BUSY`, `LIBRARY_BUSY`, …), unchanged.
- **The 2-minute line is mine.** Ender's appendix puts the normal tail at up to about 60 s, so 2 minutes marks "abnormal". A reboot always clears the record, so the PC-restart line is true. Ender may move the number only with measured data.
- **Try again is disabled exactly while P2.** The page's `retry.disabled=false` on every state update must not undo it.
- **Button face is `Try again`**, the existing control (Sergei's "Retry"). Order is today's: Try again, Open log folder, Quit.

**Tooltips** (native `title`, in the commit that changes each control):

| Control | Tooltip |
|---|---|
| `Try again` (P1, P3) | `Check the previous session again. The app starts once it has ended.` |
| `Try again` (P2, disabled) | `Checking the previous session…` |
| `Open log folder` | `Open the local app's log folder.` (existing) |
| `Quit` | `Close Comic Metadata.` (existing) |

**Quit on every P state exits at once.** No wait, no dialog: this run owns no engine parts, and the previous session's parts are not ours to end (their broker is gone). It also works during P2 and from the tray. The next start re-checks the same record.

**Focus and announcements.** The heading takes focus on arrival and when Try again is pressed (existing handler). It stays there through P2 and P1, so Tab reaches Try again next. The heading and detail keep `role="status"`; the check time is not live (the detail already announces the result). No `role="alert"`.

**Tray label** (window may be hidden): when the failure is this state, `Previous session still closing. Open the window for details.` with the error icon. Quit stays enabled.

### R3. Dashboard banner: nothing remains

B1–B3 are removed with the failure they described, and B4 is gone with the Task Manager line. No new banner is added. The generic banner (`The local service is not responding. Try again or open the log folder.`, with Try again and Open log folder) stays exactly as it is for `RESTART_EXHAUSTED` and repeated poll misses. Its Try again can end in the P screen, because a failed start always moves the window to the startup screen. Nothing changes in `static/shell-ui.js`; the repaint key needs no `stopping` or `closureFinal`.

### R4. What Ender must supply (shell facts, not UI)

1. **`state.stopping` is held from Quit accepted to exit, on every path.** Do not let the stopper's `finished` clear it or close the dialog on the way to `exit()`. Emit the ending stage before any `forceStop` that Quit starts: Quit now, the 10-minute cap, two status failures, the error path, engine not ready, the setup page. The dialog is created or updated from the shell, not only from stopper events, and exists by 1.5 s.
2. **One wait constant** (30) shared by the broker call and the dialog text.
3. **The shell exits by wait + 1 s even if the broker never answers.** Quit always ends the process (ProcessRules § Desktop App / GUI Rules). If the broker is silent the record may not be written; what the next start does then is Ender's call.
4. **The new failure** (code name Ender's, for example `PREVIOUS_CLOSING`) with two timestamps in `state`: `checkedAt` (this check) and `leftoverSince` (the record's own write time; if unavailable, the time this shell first saw it, which only delays the restart-PC line). And `startupPhase:'previous'` while a re-check runs after Try again on a P screen. The 0.5 s hold of P2 is applied before the result is shown, including the page reload a failed start does today (`loadFile` in the `start()` catch), with no blank frame.
5. **`forceStop` on a broker that already exited 123 returns at once.** Today `treeEnded` could wait up to 10 s and then refuse.
6. **Delete** the `CLOSURE_UNCONFIRMED` failure, the `start()` guard, the Retry-hiding line and the closure heading and detail in `startup.js`, and the closure wrapping in `startOwned`. No string `could not be stopped` or `Task Manager` remains in `desktop/` or `static/`.
7. **Every check logs** each record's members, whether each is alive, and the record's age, so `Open log folder` holds the answer.

### R5. Checks for Futaba (measured, every state)

Window-show, focus and real-window checks need a visible run: the QA profile's offscreen mode skips them (`if(!qa)`), a headless GO is not enough for a visual change, and focus checks need Sergei's permission first.

**Quit wait** (Ender's harness holds an engine part so the wait runs its 30 s):
1. Quit from the window (Ctrl+Q), from File > Exit, and from the tray with the window hidden. Record the time the dialog appears (at most 1.5 s plus render) and the time the process ends (at most 31 s).
2. The ending text matches R1 character for character. The 10-second sentence appears at 10 s, not before. Changing the constant in the harness changes the number in the text.
3. Press Quit now during Pausing: the dialog is in the ending state within 100 ms, buttons hidden, no gap where the row was.
4. In the ending state Escape and the window's close button do nothing; the process still ends.
5. Error path (make the status calls fail twice): the dialog stays open through the whole wait, tray Quit stays `Quitting…` and disabled, a second Ctrl+Q does nothing.
6. Quit with the engine not ready (during startup) and from the setup page: the dialog appears by 1.5 s if the wait lasts.
7. A forced close that ends within 1.5 s (no stuck part) shows no ending-state dialog.
8. Start a second copy during the wait: no second app starts, the dialog comes forward. After the exit, a new start works.
9. Tray Quit with the window hidden and the engine not ready (so the dialog is first created in the ending state): the window and dialog appear and the app that had focus keeps it (visible run, with permission).
10. `leftover-<owner>.json` exists after a stuck-part exit and not after a clean one.

**Previous session screen** (harness: a leftover record naming a live dummy process):
11. Start: P1, strings exact, `Checked at` present, buttons in the order Try again, Open log folder, Quit, all enabled, tooltips exact.
12. Press Try again five times with the part still alive: P2 is on screen at least 0.5 s each time, Try again disabled with `aria-busy="true"` and the same label, then P1 with a different time each time. No blank flash or page flicker between.
13. Measure rects for P1, P2 and P3 at 640, 1000 and 1280 px: each button at least 40 px high, no overlap among text and buttons, and the buttons do not move between P1, P2 and P3. At 640 px nothing scrolls sideways.
14. End the dummy process, press Try again: the normal start phases run, the dashboard opens, the record is gone.
15. Set the record's age to 3 minutes: P3 text. Set it to 1 minute: P1 text.
16. Press Quit in P1, P2 and P3, and Quit from the tray: the process ends within 1 s each time, and the next start still shows P1 while the dummy lives.
17. Corrupt record, and a record from before a reboot: normal start, never a stuck screen.
18. A start failure whose cleanup leaves a record (harness), then Try again on that failure screen: P1.
19. Focus after each transition; a screen reader reads each change once.

**Unchanged and removed:**
20. `PORT_BUSY`, `LIBRARY_BUSY`, `START_TIMEOUT` and the other failure screens keep their text and buttons. The dashboard banner for `RESTART_EXHAUSTED` and poll misses still reads `The local service is not responding. Try again or open the log folder.` and Try again still works.
21. Close the app from every top-level screen (dashboard, setup, every startup phase, P1–P3, every quit-dialog stage): the process ends. This is the standing close-button check.
22. Absence check with a positive control: search `desktop/` and `static/` for `could not be stopped`, `Task Manager` and `CLOSURE_UNCONFIRMED`. Run the same search on the 0.6.6 tree first and confirm it finds them; then the new build finds none.
23. Compare every string in R1 and R2 with the shipped files character by character.

### R6. Not specified here (offered, not started)

1. **A longer dead end in the closing stage.** After the GPU is released, the stage `Closing…` disables both buttons while the engine exits gracefully, for up to the rest of the 10-minute cap. That is a wait longer than 30 s with no way out, against "Quit always ends the process". I recommend ending the stage after 30 s by moving to the forced path (the ending state above). It is a data-safety call for Sergei and Ender, so I did not design it.
2. **Automatic re-check on the P screen** (for example every 10 s). It would save presses but starts a broker each time and opens the dashboard unprompted. I recommend not doing it unless the screen proves annoying.
3. **The recovery-backup sentence** in the ending state is existing copy from Quit now. Ender confirms it holds for the broker's forced termination; if not, the sentence is dropped and the 10-second detail stays `This can take up to 30 seconds.`
4. **Windows log-off and shutdown** (`query-session-end`) waits on `forceStop` after 2.5 s with no screen. With a 30 s wait the shell must still exit by the OS deadline. Ender's call.
5. **The 0.5 s hold and the 2-minute line** are my choices from the Doherty threshold and Ender's 60 s tail. Both can move.
6. **The banner's Open log folder ignores a failed open** (the startup screen shows `Could not open the log folder.`). Carried from rev 1, still not specified.

---

# History — rev 1 (void, kept for the reasoning only)

Everything below describes a design with a refused Quit and a `CLOSURE_UNCONFIRMED` guard. That design no longer exists. Do not build, check or quote it.

Author: Judy. Date: 2026-11-18. Branch: `ender/0.6.7-fixes`. Status then: draft for Sergei, uncommitted.
Source: TrayQA v0.6.6 finding 2 ("Try again does nothing") plus the startup-screen dead Retry after exit code 124.
Section 1 (dashboard banner) and Section 2 (startup screen) were approved separately. Each was self-contained.

## 0. Recommendation (void)

**Option C, with the startup screen's wording.** The banner stops saying "not responding", loses Try again, and offers **Quit** (which re-runs the closure check and exits once it passes) next to **Open log folder**. Two things make it honest:

1. The check has a visible wait ("Stopping the local service…") and a visible refusal ("still could not be stopped"). The real defect is silence, not the label.
2. When no later check can ever pass (broker exit 124), the shell says so, drops Quit, and names the one way out (Task Manager). This needs one boolean from the shell (section 5).

Why not the others:

| Option | Verdict | Reason |
|---|---|---|
| A. Startup wording, drop Try again, keep log folder | Fallback, not recommended | Honest and smallest, but it strips the only in-window action that can still succeed (re-check). The user would have to go back to the tray menu they just used. |
| B. Rename to "Check again" and restart the engine | Reject | Lifts the guard in `start()` (`main.cjs:94`) that stops a second engine starting while the first is unconfirmed. After a refused Quit it starts the engine the user just asked to stop. "Check again" does not say what it does. After a 124 it needs the same refusal message C needs anyway. |
| C. Offer Quit | **Recommend** | The only recovery that matches the user's last intent. Same button pair as the installer-uncertain banner and the startup screen, so no new pattern. |
| D. Keep Try again, disabled, with tooltip | Reject | A control that can never enable. Its reason shows on mouse hover only; a disabled button is skipped by Tab and screen readers. No way out is offered. |

## 1. Section 1 — Dashboard banner (approve separately) (void)

### Facts from the code

- `static/shell-ui.js:30` draws one banner for every `service==='failed'`: "The local service is not responding. Try again or open the log folder." with Try again (`retryService`) and Open log folder.
- A refused Quit sets `state.service='failed'`, `state.failure='CLOSURE_UNCONFIRMED'` (`main.cjs:81`). `start()` then returns at once for that failure (`main.cjs:94`), so Try again does nothing and shows nothing.
- Other failures that use this banner (`RESTART_EXHAUSTED`, repeated poll misses) keep Try again, and it works for them. **They are not changed.**
- After a refused Quit, TrayQA v0.6.6 saw the refusal take 20.6 s (two 10 s closure waits). A re-check needs a visible wait.
- A refusal after broker exit 124 is instant and final (`engine.cjs:101`); so is a broker ended by signal (`engine.cjs:91`). A held port or held claim can pass later.

### States and buttons

Only when `state.failure==='CLOSURE_UNCONFIRMED'`. Button order is the installer-uncertain banner's order: Open log folder, then Quit.

| # | State | When | Message line | Detail line | Buttons |
|---|---|---|---|---|---|
| B1 | Can still be checked | Quit was refused; no check running | `The local service could not be stopped.` | `Quit tries to stop it again.` | `Open log folder`, `Quit` (primary) |
| B2 | Checking | `state.stopping` is set | `Stopping the local service…` (after 10 s add detail `This is taking longer than usual.`) | none until 10 s | `Open log folder`, `Quit` (disabled, `aria-busy="true"`) |
| B3 | Refused again | A check ended and the failure stayed, not final | `The local service still could not be stopped.` | `Quit tries to stop it again.` | as B1 |
| B4 | Cannot be checked | `closureFinal` is true (section 5) | `The local service could not be stopped, and the app cannot check again.` | `End Comic Metadata in Task Manager, then start it again.` | `Open log folder` only |

Notes:
- If the check passes, the app exits. There is no success state to design.
- B3 stays until the state changes; it is not timed.
- B4 has no Quit and no Try again: a button the shell knows will be refused is not shown.
- "Stopping the local service…" and "This is taking longer than usual." are the startup screen's own strings (`startup.js`), so the same state reads the same on both surfaces.
- Task Manager line: it is the only exit after a 124, but whether ending the app there leaves nothing writing to the library is Ender's fact to confirm (section 7, item 3).

### Tooltips (native `title`, in the commit that creates each control)

| Control | Tooltip |
|---|---|
| `Quit` (B1, B3) | `Try to stop the local service again. The app closes once it has stopped.` |
| `Quit` (B2, disabled) | `Stopping the local service…` |
| `Open log folder` (all four) | `Open the local app's log folder.` (existing, unchanged) |

### Layout, focus, announcements

- No new colors or sizes. Failure variant (`.shell-notice.failure`), 40 px buttons, banner in flow above the dashboard header. Nothing overlaps; B4's longer text wraps, and below 640 px the buttons drop under the text as today.
- The shell forces a dark theme, so there is no light-theme variant. Meaning is carried by words, not color.
- Message line keeps `role="status"` (polite). No `role="alert"` (a user just pressed the button; the change is announced as their result).
- Focus: pressing Quit moves focus to the message line (the banner's rule when a pressed button changes); when the check ends refused (B3), focus returns to Quit. B4 appearing with focus inside the banner goes to Open log folder.
- Banner repaint key must include `state.stopping` and `closureFinal`, or B2 and B4 will not draw.

### Tray label (same state, droppable)

`main.cjs:43` says `Local service not responding. Open the window for details.` for this state too. Change it only when `failure==='CLOSURE_UNCONFIRMED'` to:

`Local service could not be stopped. Open the window for details.`

Tray Quit stays enabled in B1 to B3 (it is the same action as the button). Section 1 works without this row.

## 2. Section 2 — Startup screen (approve separately) (void)

### Facts from the code

- `startup.js` already hides Retry and shows `The local service could not be stopped.` / `Open the log folder for details.` for `CLOSURE_UNCONFIRMED`. Its Quit says `Close Comic Metadata.`, which promises an exit a refusal will not give, and a refused Quit changes nothing on screen.
- After a 124 the screen can instead read `Could not start the local service.` with a Retry that fails at once. My reading, to be confirmed by Ender: when the broker exits 124 while running, the automatic restart runs `startOwned`, whose own `forceStop()` (`engine.cjs:36`) throws a plain Error with no code; `start()` stores it as `ENGINE_EXIT` (`main.cjs:97`), so the generic screen shows. Retry then repeats the same refusal. Tray Quit is refused too. Only Task Manager ends the app.

### Rule

When a start attempt fails because the closure check was refused, the screen must show the closure states below, never `Could not start the local service.` with Retry. All other start failures keep today's screens and buttons (`Try again`, `Open log folder`, `Quit`), unchanged.

### States and buttons

Try again is hidden in all four. Button order is today's: Open log folder, then Quit.

| # | State | When | Heading | Detail | Buttons |
|---|---|---|---|---|---|
| S1 | Can still be checked | Closure refused, not final | `The local service could not be stopped.` | `Quit tries to stop it again.` | `Open log folder`, `Quit` (primary) |
| S2 | Checking | `state.stopping` is set | `Stopping the local service…` | `This is taking longer than usual.` after 10 s, else empty | `Open log folder`, `Quit` (disabled, `aria-busy="true"`) |
| S3 | Refused again | A check ended, still refused, not final | `The local service still could not be stopped.` | `Quit tries to stop it again.` | as S1 |
| S4 | Cannot be checked | `closureFinal` is true, including the 124 path above | `The local service could not be stopped, and the app cannot check again.` | `End Comic Metadata in Task Manager, then start it again.` | `Open log folder` only |

### Tooltips

| Control | Tooltip |
|---|---|
| `Quit` in S1, S3 | `Try to stop the local service again. The app closes once it has stopped.` |
| `Quit` in S2 (disabled) | `Stopping the local service…` |
| `Quit` in every other failure screen | `Close Comic Metadata.` (unchanged) |
| `Open log folder` | `Open the local app's log folder.` (existing, unchanged) |

Focus: heading takes focus on arrival (existing behavior). After a check ends refused (S3), focus goes to Quit. The heading stays `role="status"`.

## 3. Words used, one place (void)

Both surfaces use the same strings for the same state. They live in two files (`shell-ui.js`, `startup.js`), so Futaba compares them across the two surfaces (section 6).

## 4. What a refused action must always do (void)

Any shell button the shell can refuse shows the refusal in words. A button whose refusal is known in advance is not shown. This is the rule the old Try again broke; it is not new copy.

## 5. What Ender must supply (shell facts, not UI) (void)

1. `state.closureFinal` (boolean). True when no later check can pass for this engine: broker exit code 124, or broker ended by signal (the two unconditional throws in `forceStopOwned`). False for a held port, held claims, or the 45 s exit wait (they can pass later). Set wherever `failure` becomes `CLOSURE_UNCONFIRMED`.
2. Start-failure routing (Section 2): a refused closure inside `startOwned` must end as `CLOSURE_UNCONFIRMED`, not `ENGINE_EXIT`.
3. The busy signal is `state.stopping`, which `quit()` already broadcasts. The "still could not be stopped" result needs no new field: the page sees `stopping` go from set to empty while the failure stays, not final.

If Ender cannot add `closureFinal`: show B1 or B3 and S1 or S3 always, and in B3 and S3 replace the detail with `If it keeps failing, end Comic Metadata in Task Manager, then start it again.` Quit stays and a 124 refuses it every time, visibly. This is worse than the recommendation but never silent.

## 6. Checks for Futaba (measured, every state) (void)

- Draw B1 to B4 and S1 to S4 with the DOM test's mock state feed. Compare the two surfaces' strings character by character.
- Measure rects, not impressions: each button at least 40 px high; message, detail and buttons do not overlap at 640, 1000 and 1280 px; B2 and S2 do not move the buttons when Quit disables (label unchanged, so width is unchanged).
- Real run with the engine port held by another process: Quit shows B2 for about 20 s, then B3. After the port is freed, Quit exits.
- Real run of a broker exit 124 (Ender's harness): the dashboard shows B4, a started app shows S4, tray Quit refuses, Task Manager ends it, and the next start works. Confirm Task Manager lists the app as `Comic Metadata`.
- Focus after each transition; screen reader reads each state once.
- RESTART_EXHAUSTED and poll-miss banners still show `The local service is not responding. Try again or open the log folder.` and Try again still works.

## 7. Not specified here (for Sergei, offered not started) (void)

1. **Quit anyway after a final refusal.** After a 124 the only exit is Task Manager, which breaks the studio's rule that Quit always ends the process. A "Quit anyway" in B4 and S4 would exit the shell with closure unconfirmed, the same result as Task Manager. That is a data-safety decision for Sergei and Ender (the next start's library claim check is the safety net), not a copy one. I did not design it.
2. **A refused tray Quit with the window hidden shows nothing** except the tray icon turning to error. Showing the window on a refused tray Quit would put the banner in front of the user. Not specified.
3. **Task Manager line needs Ender's confirmation** that ending the app there is enough. If a process kept in the Job can survive it, the line should name a PC restart instead.
4. The banner's Open log folder ignores a failed open (the startup screen shows `Could not open the log folder.`). Not specified.
