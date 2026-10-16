# Folder help lines: Check and requeue, Open folder (0.2.5)

Date: 2026-10-16. Owner: Judy. Status: reviewable; Sully commits before Ender is briefed. EXTENDS FailureFilters_2026-10-13 (which left the folder-level "Your help is needed" lines as text; Sergei chose on 2026-10-16 to add actions). Adds two buttons and a result area to each line. No modal, no other copy changes.

Basis: Sergei's standing rule (recap 2026-10-13: everything that needs his help offers concrete choices); NN/g (error prevention, visibility of status, plain-language recovery, user control); Jakob (Explorer's Show in folder); Hick (two buttons per line, none per reason); WCAG 2.2 AA (1.4.3, 1.4.10, 1.4.11, 2.4.7, 2.5.3, 2.5.8, 4.1.3); ProcessRules § Copy is short, specific, and has no memory, § A new control is born with its tooltip, § No UI element may cover another. Read from: `static/index.html` (line 135, `#queueAttention`, `renderControl`, `request`), `worker.py`, `batch.py`, `app.py` (`write_metadata`, `remove_verified_backup`, `/api/open-folder`), `progress_snapshot.py`, `library_lock.py`, the BackupLocation spec (Kept backups components and conventions).

## 1. Findings that shape the spec

1. **The line is rebuilt every 2 seconds.** `index.html:135` calls `replaceChildren` on `#queueAttention` at each poll. A button placed there would lose keyboard focus, its in-flight state and any result list within 2 s. The lines must be updated in place, keyed by ticket (section 8.1).
2. **The payload carries no ticket id, and `folder` is the full plan path.** The page needs an opaque `id` per ticket and a reason `code` (section 5). The browser sends only the id; the server derives the folder from the ticket and never opens a browser-supplied path (same rule as the BackupLocation reveal route).
3. **`/api/open-folder` cannot open a ticket's folder.** It takes a catalog comic id (`app.py:890`), and a ticket has none. The localhost precedent still holds: the dashboard binds to 127.0.0.1 and the route runs `os.startfile` on the same machine, so a plain browser behaves exactly like the shell, with no gate and no separate case. A new ticket-addressed route follows it (section 8.3).
4. **Per-comic "open the folder" would be useless here.** Every comic of a ticket sits in the one plan folder (`batch.py:187`). Problem rows therefore reveal the exact file the finding is about (the comic, a leftover temp file or a kept backup), not the folder.
5. **The raw error text is not fit to be the line.** It is `str(exc)`: fixed sentences, field names, Windows error text, a bare `'entries'` from a KeyError, or an empty string, which today renders "folder — " with a dangling dash. Section 5 maps it to a code and plain copy and keeps the raw text as a labelled detail.
6. **Success removes the line.** Closing the ticket drops it from the next poll, so the confirmation and the focus target cannot live in the line (section 4.3, 7).
7. **The check will not pass for the commonest interruption.** A write stopped mid-comic leaves that comic's recovery backup (and sometimes a temp file), and any leftover blocks the requeue. Sergei then has to delete it by hand first. See question 1.

## 2. Controls and exact copy

Label change from Ender's proposal: the line's folder button is **Open folder**, not "Show folder". The app already says Open folder for the same act (`comic-recovery.js:52`); a fourth wording for it is noise. Per-file buttons are **Show in folder** (Explorer's own wording, same as Kept backups rows). One verb opens a folder; the other reveals a file inside one.

| Control | Visible label | Tooltip (`title`) | Accessible name |
|---|---|---|---|
| Line, primary | **Check and requeue** | **Check this folder's comics without changing them. If all is in order, close this item and queue the unwritten comics again.** | Check and requeue: {folder name} |
| ...while checking (this line) | label unchanged | **Checking now. Nothing is changed.** | unchanged |
| ...while another line is checking | label unchanged | **Another folder is being checked. Wait for it to finish.** | unchanged |
| ...while paused or pausing | label unchanged | **Processing is paused. Resume processing to check and requeue.** | unchanged, plus `aria-describedby` the paused note |
| Line, secondary | **Open folder** | **Open this folder in File Explorer to check its comics. Nothing is changed.** | Open folder: {folder name} |
| Problem row | **Show in folder** | **Show this file in File Explorer. Nothing is changed.** | Show in folder: {file name it shows} |

- {folder name} is the last segment of the path.
- Disabled states use `aria-disabled="true"` and ignore clicks; never `disabled`, which drops keyboard focus when the pressed button is the one that disables. Labels never change.
- **Open folder** and **Show in folder** stay enabled while paused (the route sits before the pause guard, like `/api/open-folder` and `/api/try-again`). Only the check is blocked. One check runs at a time across all lines.
- Paused note, one per line, directly under the buttons, not a live region (the pause is Sergei's own action): **Paused. Resume processing to check and requeue.** Shown only while `processingControl.requested`.

## 3. Line layout (every width, one layout)

```
▌Your help is needed: D:\Comics\Marvel\X-Men          head: lead 600 #ffdf76, path #e7eaf1, wraps
▌Interrupted: the app stopped while writing this       reason, 16px #e7eaf1
▌folder, so some comics may be unwritten.
▌Last error: {raw, max 300}                            14px #aab4c6; omitted for "interrupted" or empty
▌[ Check and requeue ] [ Open folder ]                 40 px high, wrap, 8 px gap
▌Paused. Resume processing to check and requeue.       14px #aab4c6, only while paused
▌Not requeued: 2 problems found, and nothing was       result summary, role=status (section 4)
▌changed. Fix them, then check again.
▌ ───────────────────────────────────────────────      problem list: plain list, not live
▌ Batman 003 (2019).cbz                [Show in folder]
▌ Failed the zip test. The archive is damaged.
▌ ───────────────────────────────────────────────
▌ Batman 003 (2019).cbz                [Show in folder]
▌ A recovery backup is kept. Do not delete it ...
▌ {error line, only after a failed click}              14px, role=alert
```

- **Card**, one per ticket: `#1b202b` (the panel's own colour), 1 px #38445a border, 4 px left border #bd9735 (5.93:1 on the panel; the words "Your help is needed" carry the meaning, not the colour), 12 px padding, 10 px radius, 8 px between cards. The `p` with `Your help is needed: {folder} — {error}` is replaced by this card; its sentence stem is kept in the head.
- **Path** is its own span set with `textContent`, `overflow-wrap:anywhere`, a `<wbr>` after each `\` (never U+200B), no `\\?\` prefix (reuse `KeptBackups.clean` and its `<wbr>` splitter, now exported or extracted). Never truncated.
- **Primary** **Check and requeue**: the page's own button style (#385ea1, text #eef2fb, 5.70:1), `min-height:40px` as `#yandexVerification` and `#browserResume` in the same panel. **Open folder**: secondary (#242c3b, 1 px #aab4c6 border, #eef2fb 12.5:1), also 40 px. Row `display:flex;flex-wrap:wrap;gap:8px`; each button `max-width:100%`, label may wrap.
- Problem row: grid, text column `minmax(0,1fr)`, button column `auto` at 700 px and above (the page's own breakpoint); one column below, button under the text, left-aligned. Rows separated by a 1 px #38445a top rule, 8 px padding. File name 16 px 600 #e7eaf1, wraps anywhere; finding 14 px #e7eaf1. Row error line spans the full row.
- Focus ring on every button: 2 px #bcd8f9, offset 2 px (11.12:1 on the card); the card padding keeps it unclipped.
- Nothing is positioned, sticky or absolute inside the card. The existing sticky `#error` banner is not used by these actions (their failures go to the line, section 6), so it never covers a card.

## 4. Progress, success and failure copy

All states are written by the page from server codes (section 8.2). Plurals: `1 comic`, `2 comics`; `1 problem`, `3 problems`.

### 4.1 While checking (line's own status node, `role="status"`, present and empty from the card's creation)

**Checking this folder's comics. This can take a few minutes.**

No spinner or animation (a zip test reads every byte; there is no honest percentage). Written when the click is accepted; replaced by the outcome. If Ender can expose `{checked, total}` per ticket in the existing 2 s payload, the sentence becomes **Checking comic {n} of {total}.**; otherwise the static text stands.

### 4.2 Failure: the check ran and found problems (line stays, nothing changed)

Summary in the line's status node: **Not requeued: {k} problems found, and nothing was changed. Fix them, then check again.**

Problem list directly below it, ordered by comic name (case-insensitive), then by the order of the table. At most 20 rows; if `k` exceeds the rows shown, a plain line under the list: **{k-20} more not shown. Fix these first, then check again.**

| Finding code | Row finding (one fact) | **Show in folder** reveals |
|---|---|---|
| `zip_failed` | **Failed the zip test. The archive is damaged.** | the comic |
| `written_changed` | **Does not match what was written and verified.** | the comic |
| `unwritten_changed` | **Does not match the file this batch planned.** | the comic |
| `missing` | **Not found in this folder.** | the folder (no file to select) |
| `temp_left` | **A leftover temporary file is next to this comic: {temp file name}.** | the temp file |
| `backup_left` | **A recovery backup is kept. Do not delete it until the comic is checked.** | the `.bak` file |

The row heading is always the comic's file name. A comic with two findings gets two rows; each is self-contained. The backup row carries the only safety sentence: with a damaged or mismatched comic that backup may be the only good copy. Deleting a backup is done in the existing Kept backups panel; nothing here deletes anything.

The list is a snapshot of the last check and stays until the next check starts on this line or the ticket leaves. A row whose file is gone answers with the error line (section 6).

### 4.3 Success (ticket closed; the line leaves on the next poll)

Written to `#attentionDone`, a new persistent node directly above `#queueAttention` (`role="status"`, `tabindex="-1"`, hidden while empty). It stays until the next check starts on any line or the page reloads.

| Outcome | Text |
|---|---|
| Clean, `n` unwritten comics | **Requeued {folder name}: {n} unwritten comics will be checked at the next folder pass.** (`1 unwritten comic will be`) |
| Clean, `n` = 0, `w` written | **Closed {folder name}: all {w} comics in the batch were written and verified.** (`w` = 1: **the comic in the batch was written and verified.**) |
| Clean, nothing planned | **Closed {folder name}: the batch had nothing left to write.** |
| Ticket already closed | **This folder is not waiting for help.** (not a failure; the line leaves) |

### 4.4 The check could not run or finish (line's status node; nothing changed)

| Server code | Text |
|---|---|
| `paused` | **Not requeued: processing is paused, and nothing was changed. Resume processing, then check again.** |
| `busy` | **Not checked: this folder is already being checked. Wait for it to finish.** |
| `folder_unavailable` | **Not checked: this folder is unavailable, and nothing was changed. Check that the library drive is connected.** |
| `library_busy` | **Not checked: another copy of the app is using this library, and nothing was changed. Close it, then check again.** |
| `plan_unreadable` | **Not checked: the saved plan for this folder cannot be read, and nothing was changed. Open the folder to check its comics.** |
| Any other error, or no answer | **Not checked: {server message, final full stop removed, or "the app did not answer"}, and nothing was changed. Try again.** |

`role="status"` for 4.1 to 4.3; 4.4 uses the same node (a refused check is not data loss). The page never sends these through `error()`: the sticky banner is far from the button and would be wiped by the next successful poll.

## 5. Every reason that can reach a "Your help is needed" line

Only two sites set `needs_attention`: `worker.py:86` (any exception escaping `batch.apply`, text = `str(exc)`) and `worker.py:123` (a ticket found `running` at worker start). Reasons below come from grepping `raise` along `batch.apply`, `app.write_metadata`, `app.remove_verified_backup` and `library_lock`. A write error with the archive untouched does not stop a ticket (it goes to `failed.json`), so those strings never appear here.

**Both actions go to every reason.** No reason-specific buttons (Hick): the check inspects the real state, and what it finds is what tells Sergei what to do. The reason line is the only thing that differs.

| Code | Raw text it covers (source) | Reason line (16 px) | Last error line |
|---|---|---|---|
| `interrupted` | "Interrupted batch; inspect results and retained backups before requeuing." (`worker.py:123`) | **Interrupted: the app stopped while writing this folder, so some comics may be unwritten.** | No |
| `comic_changed` | "A completed archive changed before batch resume; inspect it before retrying." (`batch.py:192`) | **Stopped: a comic already written in this folder does not match what was verified.** | Yes |
| `outside_folder` | "Target must stay in the planned folder." (`batch.py:188`) | **Stopped: the saved plan names a file outside this folder.** | Yes |
| `not_verified` | "Archive validation failed.", "Archive contents changed unexpectedly.", "Temporary archive metadata verification failed for {field}", "Readback verification failed for {field}" (`app.py:612-631`, `batch.py:241`), "Backup verification failed." (`batch.py:243`, `app.py:453`) | **Stopped: a write could not be verified. The comic and its recovery backup need checking.** | Yes |
| `backup_kept` | "Backup cleanup target is outside the expected folder." (`app.py:450`) | **Stopped: a recovery backup could not be removed after a write.** | Yes |
| `library_busy` | The four `LibraryBusy` texts (`library_lock.py:103,196,204,216`) | **Stopped: this library was in use by another copy of the app.** | Yes |
| `other` | OS errors (`[WinError 5]`, disk full, drive missing), a locked database, an unreadable or incomplete plan (`'entries'`, a JSON error), any new exception | **Stopped: this batch hit an error.** (empty raw text: **Stopped: this batch hit an error with no details.**) | Yes, when not empty |

- **Last error line:** `Last error: ` + raw text cut at 300 characters (add `…` when cut), plain text, `overflow-wrap:anywhere`, same pattern as the per-comic "Last error". It carries the field name or the Windows message the reason line leaves out.
- A missing or unknown `code` is treated as `other`. The page never matches raw strings.
- State word first in every reason, per the DesktopShell rule.

## 6. Open folder and Show in folder errors

An error line inside the card (line button) or inside the row (row button), 14 px, `role="alert"`, cleared on the next click of any button in that card and when the ticket leaves. Never through `error()` or the status node.

| Server code | Line / row text |
|---|---|
| `folder_unavailable` | **Folder is unavailable. Check that the library drive is connected.** (existing wording) |
| `gone` | **This folder is not waiting for help.** |
| `not_found` (row) | **File not found. Check again to update this list.** |
| `failed` (line) | **Could not open File Explorer. Use the path above.** |
| `failed` (row) | **Could not open File Explorer. The folder is shown above.** |

Success: Explorer opens; no in-app text; focus stays on the button.

## 7. Keyboard and focus

- Tab order per card: **Check and requeue**, **Open folder**, then each row's **Show in folder**. Reason, path, findings and Last error are selectable text, not stops. Enter and Space are native. No accelerator (rare action; Hick).
- A click makes one request; a second click while in flight is ignored (`aria-disabled`). Focus stays on the button.
- **After a failure or a refusal:** move focus to the line's status node (`tabindex="-1"`) so the summary is read first, then the next Tab reaches the first **Show in folder**.
- **After success:** the line is removed, so move focus to `#attentionDone`; the next Tab reaches the first remaining card.
- **Both moves happen only if focus is still on the pressed button, inside the removed card, or on the page body.** The check can take minutes; if Sergei has gone elsewhere, nothing steals focus and the live region announces the result.
- The 2 s poll never moves or drops focus: the update is keyed, and it never rebuilds a card whose check is running or whose result is showing (8.1).
- `aria-describedby` links **Check and requeue** to the paused note while paused.

## 8. For Ender (requirements, not design)

1. **Keyed render.** Replace the `replaceChildren` at `index.html:135` with a keyed update: keep a card per `id`, rewrite only its reason or Last error text when it changes (use the page's `tip()` and a `setText`-style compare), remove cards whose ticket left, add new ones in queue order. Keep in-flight state, the problem list and the last status text in a `Map` keyed by `id`; clear an entry when its ticket leaves or a new check starts on it.
2. **Payload.** Each `attention` item in `progress_snapshot.py:66` gains `id` (the ticket file stem) and `code` (section 5); `error` stays. Classify at the two `needs_attention` sites, not in the page; `other` is the fallback.
3. **Routes, all naming a ticket id and, for rows, a problem id issued by the check; never a path.**
   - **Check and requeue.** After the pause guard (the `paused` code). Single flight per ticket (`busy`). Requires the ticket to be `needs_attention` and its folder inside the live library. Read-only until the end: zip test, written comics against `results.json` signatures, unwritten comics against the plan's size, mtime and `sha256`, no `.metadata-tmp` or kept `.bak` for any plan comic. Re-read the ticket and the pause state immediately before closing, and make the unwritten comics due with a fresh plan (the `scheduler.finish(..., queued=True)` effect). Return `{ok, unwritten, written}` or `{code:'problems', total, problems:[{id, name, finding, file}]}` limited to 20 rows in the section 4.2 order. The `unwritten` count must equal the comics that will really be re-planned; comics already in `skipped.json` or `failed.json` have their own wait records and are not problems.
   - **Reveal.** Same Origin and Host checks as `/api/open-folder`, placed before the pause guard. Body names the ticket (open the folder) or the ticket and a problem id (select that file; for `missing`, open the folder). Explorer's select needs a normal path without `\\?\`; over MAX_PATH, fall back to opening the folder. Codes per section 6.
4. **Tooltips** ship in the same commit as the controls (all in section 2), each written with the page's compare-before-set helper because the card is touched by a 2 s poll.
5. **Tests** that matter: a card survives two polls with focus on **Check and requeue**; a failure list survives two polls; `1 comic` and `1 problem` singulars; an empty raw error; each code in section 5; the 21-problem cap line.
6. Note, no UI change: `worker.py:86` stores `str(exc)` even when it is empty or a bare key name. Giving the code a better source than the message is Ender's call.

## 9. Acceptance (Futaba, isolated QA)

Measured rects, not impressions, at 320, 640 and 1280 CSS px, 100% and 200% zoom (about 215 px of text width at 320), in each state: one card idle; checking; paused; failure list with 1, 3 and 21 problems; every error line showing; two cards; success message with and without remaining cards.
1. Head, reason, Last error, buttons, paused note, status node, rows, row buttons and error lines are pairwise disjoint; cards do not touch; no horizontal overflow (`scrollWidth <= clientWidth`) in the panel.
2. Targets at least 24 px wide and 40 px high; focus ring fully visible on every button.
3. Test paths and names: 200+ characters, spaces, `[ ]`, non-Latin, one unbroken 60+ character segment, a `\\?\`-prefixed path (must display without it).
4. Keyboard-only run: Tab to **Check and requeue**, Enter, hear the progress, land on the summary on failure, Tab to a **Show in folder**, then recheck to success and confirm focus lands on `#attentionDone` and the next Tab reaches the next card. Also run it with focus moved elsewhere during the check: focus must not move.
5. Matrix: every code in sections 4.4, 5 and 6; paused (button blocked, tooltip, paused note, Open folder still works); two cards (second button blocked while the first checks); a ticket removed by the worker mid-check (`gone`); an empty raw error; the 2 s poll with a card focused.
6. A stub or throwaway fixture library only. **Check and requeue closes real tickets**, so it is never run against Sergei's real queue. Explorer launch is stubbed (native focus needs separate authorisation).

## 10. Brief Decision Log row (for Ender to paste)

```
| Help needs choices (Sergei 2026-10-13) | Anything that needs Sergei's help offers concrete choices he can press, with what each does, never a bare request. Applied to comics on 2026-10-13 (conflict and dead-link Review options) and, from 0.2.5, to folder-level "Your help is needed" lines: **Check and requeue** and **Open folder** on every line (Sergei 2026-10-16; `Docs/ComicsMetaOrganizer_UXSpec_FolderHelpActions_2026-10-16.md`) | A text-only "inspect before requeuing" line (declined 2026-10-16) | A new help line or message ships with nothing to press |
```

## 11. Questions for Sergei

1. **Leftover backups block the requeue.** An interrupted write usually leaves one recovery backup, so the check fails until you delete it in Kept backups. (a) Keep as proposed: safest (default). (b) When the comic itself is verifiably unchanged, offer a second button, **Delete backup and requeue**.
2. **Pause.** The check only reads, but Ender blocks it while paused. (a) Blocked while paused, with the reason shown (default). (b) Allow the check while paused and block only the requeue.
3. **Unreadable plan.** If a ticket's saved plan is missing or damaged, the check cannot run and the line stays with the message. (a) Leave it (default). (b) Offer **Close and recheck folder**, which closes the line and makes the folder due.
