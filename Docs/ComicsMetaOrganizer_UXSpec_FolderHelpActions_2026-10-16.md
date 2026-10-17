# Folder help lines: Check and requeue, Open folder (0.2.5)

Date: 2026-10-16. Owner: Judy. Status: reviewable; Sully commits before Ender is briefed. **Amended 2026-10-16 with Sergei's §11 answers (Amendment 1; where it differs from §1 to §10, the Amendment wins). Amended again 2026-10-17: Amendment 2 at the very end (a leftover temp file no longer blocks Delete backup and requeue; copy fixes from the 0.2.5 QA); where it differs from anything above, Amendment 2 wins.** EXTENDS FailureFilters_2026-10-13 (which left the folder-level "Your help is needed" lines as text; Sergei chose on 2026-10-16 to add actions). Adds two buttons and a result area to each line. No modal, no other copy changes.

Basis: Sergei's standing rule (recap 2026-10-13: everything that needs his help offers concrete choices); NN/g (error prevention, visibility of status, plain-language recovery, user control); Jakob (Explorer's Show in folder); Hick (two buttons per line, none per reason); WCAG 2.2 AA (1.4.3, 1.4.10, 1.4.11, 2.4.7, 2.5.3, 2.5.8, 4.1.3); ProcessRules § Copy is short, specific, and has no memory, § A new control is born with its tooltip, § No UI element may cover another. Read from: `static/index.html` (line 135, `#queueAttention`, `renderControl`, `request`), `worker.py`, `batch.py`, `app.py` (`write_metadata`, `remove_verified_backup`, `/api/open-folder`), `progress_snapshot.py`, `library_lock.py`, the BackupLocation spec (Kept backups components and conventions).

## 1. Findings that shape the spec

1. **The line is rebuilt every 2 seconds.** `index.html:135` calls `replaceChildren` on `#queueAttention` at each poll. A button placed there would lose keyboard focus, its in-flight state and any result list within 2 s. The lines must be updated in place, keyed by ticket (section 8.1).
2. **The payload carries no ticket id, and `folder` is the full plan path.** The page needs an opaque `id` per ticket and a reason `code` (section 5). The browser sends only the id; the server derives the folder from the ticket and never opens a browser-supplied path (same rule as the BackupLocation reveal route).
3. **`/api/open-folder` cannot open a ticket's folder.** It takes a catalog comic id (`app.py:890`), and a ticket has none. The localhost precedent still holds: the dashboard binds to 127.0.0.1 and the route runs `os.startfile` on the same machine, so a plain browser behaves exactly like the shell, with no gate and no separate case. A new ticket-addressed route follows it (section 8.3).
4. **Per-comic "open the folder" would be useless here.** Every comic of a ticket sits in the one plan folder (`batch.py:187`). Problem rows therefore reveal the exact file the finding is about (the comic, a leftover temp file or a kept backup), not the folder.
5. **The raw error text is not fit to be the line.** It is `str(exc)`: fixed sentences, field names, Windows error text, a bare `'entries'` from a KeyError, or an empty string, which today renders "folder — " with a dangling dash. Section 5 maps it to a code and plain copy and keeps the raw text as a labelled detail.
6. **Success removes the line.** Closing the ticket drops it from the next poll, so the confirmation and the focus target cannot live in the line (section 4.3, 7).
7. **The check will not pass for the commonest interruption.** A write stopped mid-comic leaves that comic's recovery backup (and sometimes a temp file), and any leftover blocks the requeue. Sergei then has to delete it by hand first. See question 1 (answered 2026-10-16, Amendment A1 to A8).

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
- Paused note, one per line, directly under the buttons, not a live region (the pause is Sergei's own action): **Paused. Resume processing to check and requeue.** Shown only while `processingControl.requested`. (Text replaced 2026-10-16: Amendment A2.)

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

Summary in the line's status node: **Not requeued: {k} problems found, and nothing was changed. Fix them, then check again.** (Variant when a backup offer shows: Amendment A6.)

Problem list directly below it, ordered by comic name (case-insensitive), then by the order of the table. At most 20 rows; if `k` exceeds the rows shown, a plain line under the list: **{k-20} more not shown. Fix these first, then check again.**

| Finding code | Row finding (one fact) | **Show in folder** reveals |
|---|---|---|
| `zip_failed` | **Failed the zip test. The archive is damaged.** | the comic |
| `written_changed` | **Does not match what was written and verified.** | the comic |
| `unwritten_changed` | **Does not match the file this batch planned.** | the comic |
| `missing` | **Not found in this folder.** | the folder (no file to select) |
| `temp_left` | **A leftover temporary file is next to this comic: {temp file name}.** | the temp file |
| `backup_left` | **A recovery backup is kept. Do not delete it until the comic is checked.** (wording by what was proved: Amendment A6, amended by Amendment 2 B6) | the `.bak` file |

The row heading is always the comic's file name. A comic with two findings gets two rows; each is self-contained. The backup row carries the only safety sentence: with a damaged or mismatched comic that backup may be the only good copy. Deleting a backup is done in the existing Kept backups panel; nothing here deletes anything. (Amended 2026-10-16: except **Delete backup and requeue**, Amendment A5 and A8; verified-backup row wording: A6.)

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
| `plan_unreadable` | **Not checked: the saved plan for this folder cannot be read, and nothing was changed. Open the folder to check its comics.** (Text replaced 2026-10-16, with a **Close and recheck folder** offer: Amendment A6.) |
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
- **After a failure or a refusal:** move focus to the line's status node (`tabindex="-1"`) so the summary is read first, then the next Tab reaches the first **Show in folder** (with an offer showing, it reaches the offer button first: Amendment A7).
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

## 11. Questions for Sergei: ANSWERED 2026-10-16

All three answered by Sergei on 2026-10-16. The options are kept below for the record; the answer is marked on each.

1. **Leftover backups block the requeue.** An interrupted write usually leaves one recovery backup, so the check fails until you delete it in Kept backups. (a) Keep as proposed: safest (default). (b) When the comic itself is verifiably unchanged, offer a second button, **Delete backup and requeue**. **ANSWERED (b).** Specified in A1 to A8.
2. **Pause.** The check only reads, but Ender blocks it while paused. (a) Blocked while paused, with the reason shown (default). (b) Allow the check while paused and block only the requeue. **ANSWERED (a).** The two new buttons follow the same rule (A2, A3).
3. **Unreadable plan.** If a ticket's saved plan is missing or damaged, the check cannot run and the line stays with the message. (a) Leave it (default). (b) Offer **Close and recheck folder**, which closes the line and makes the folder due. **ANSWERED (b).** Specified in A2, A3, A6, A8.

---

## Amendment 1 — Sergei answers 2026-10-16

Date: 2026-10-16. Owner: Judy. Status: reviewable; Sully commits before Ender is briefed. Adds two buttons, **Delete backup and requeue** and **Close and recheck folder**. Both exist only inside a check result: a card with no result still shows exactly two buttons (§3 unchanged until a check returns). Palette, states, tooltip mechanics and focus rules of §2 to §8 apply unless this section replaces them; where it does, this section wins.

Basis: NN/g (error prevention: a permanent delete is confirmed with the safe button focused; visibility of status; plain-language recovery), Hick (the new buttons appear only in the one result that needs them, never as standing buttons), Jakob (Windows confirm pattern; the Kept backups precedent in `ComicsMetaOrganizer_UXSpec_BackupLocation_2026-10-16.md` §A4, A5), WCAG 2.2 AA (1.4.3, 1.4.10, 1.4.11, 2.4.3, 2.4.7, 2.5.3, 2.5.8, 4.1.3), ProcessRules § Copy is short, specific, and has no memory, § A new control is born with its tooltip, § No UI element may cover another.

### A1. What "verifiably unchanged" means

In user terms: the app can prove the comic file is still **exactly one of two files it already knows**.

1. **The original.** Byte for byte the comic as it was before the app began writing. The write never reached it.
2. **The verified result.** Byte for byte the comic as the app wrote it and verified it.

"Prove" means the file on disk now has the same **size**, the same **last-modified time** and the same **content fingerprint (hash)** the app recorded for that state. It does not mean "it opens", "the zip test passes", "same name" or "looks the same". If the app has no recorded fingerprint, or any one of the three differs, the comic is not verifiably unchanged and the button is not offered. The check proves it to decide whether to offer; the click proves it again before anything is deleted (A8).

### A2. Controls and exact copy

| Control | Visible label | Tooltip (`title`) | Accessible name |
|---|---|---|---|
| Offer, 1 backup | **Delete backup and requeue** | **Delete this folder's kept recovery backup, then close this item and queue the unwritten comics again. You are asked to confirm first.** | Delete backup and requeue: {folder name} |
| Offer, {n} backups (n of 2 or more) | **Delete backups and requeue** | **Delete this folder's {n} kept recovery backups, then close this item and queue the unwritten comics again. You are asked to confirm first.** | Delete backups and requeue: {folder name} |
| Confirm, 1 | **Delete and requeue** | **Delete the backup permanently, then requeue.** | visible text |
| Confirm, {n} | **Delete {n} backups and requeue** | **Delete the {n} backups permanently, then requeue.** | visible text |
| Confirm, back out | **Keep it** (n of 2 or more: **Keep them**) | **Go back. Nothing is deleted.** | visible text |
| Offer, unreadable plan | **Close and recheck folder** | **Close this item and have this folder checked again at the next folder pass. No comic or backup file is changed.** | Close and recheck folder: {folder name} |

- The singular label is Sergei's wording. The plural label and the count on the plural confirm face are Judy's extension: backups from several comics can be left in one folder, and the confirm face repeats the count so it cannot be confirmed blind (Kept backups rule). The opener and its confirm face never read the same, so two identical buttons are never on screen.
- Visible label first in every accessible name (2.5.3). `title` set with the page's compare-before-set helper (the card is touched by the 2 s poll).
- Blocked or busy, all `aria-disabled="true"`, clicks ignored, never `disabled`; labels never change, only the tooltip:

| State | Delete backup and requeue, and its confirm face | Close and recheck folder |
|---|---|---|
| Paused or pausing | **Processing is paused. Resume processing to delete the backup and requeue.** (n of 2 or more: "backups") | **Processing is paused. Resume processing to close and recheck.** |
| Another folder is working | **Another folder is being checked. Wait for it to finish.** | same |
| This card's own operation running | the running control: **Deleting the backup, then checking again.** (n of 2 or more: "backups") | the running control: **Closing this item.** |
| ...every other action button in the same card (this operation not a check) | **This folder is being worked on. Wait for it to finish.** | same |

- While paused, both new buttons get `aria-describedby` pointing at the line's paused note, as **Check and requeue** does (§7). **Keep it** and **Open folder** stay enabled.
- **Paused note replaced** (§2), one per line, same place, same rule (only while `processingControl.requested`, not a live region): **Paused. Resume processing to requeue or recheck this folder.** It now covers all three blocked buttons; **Open folder** and **Show in folder** still work while paused.
- "Another folder is working" keeps the word "checked" (§2): the only operation long enough to be seen is a check; **Close and recheck folder** is instant.

### A3. When each appears, when it is blocked

| | Delete backup and requeue | Close and recheck folder |
|---|---|---|
| **Appears** | After a check on this line returned problems where **every** finding is a kept backup, every one of those comics is verifiably unchanged (A1), and all of them are in the visible list (20 rows or fewer). The server says so with an `offer`; the page never infers it. | After a check on this line returned `plan_unreadable` (the saved plan is missing or cannot be read; one code for both), **or (Sergei's 2a, 2026-10-16) returned problems where every finding is `unwritten_changed`** (the comics changed after the batch was planned). The server says so with an `offer`. Same placement, style, label, tooltip, success text, failure strings and focus rules in both cases; no confirm. The route re-runs the inspection at the click and closes only if the plan is still unreadable or every finding is still `unwritten_changed`; otherwise it refuses with `plan_readable`: **Not closed: this folder changed since the check, and nothing was changed. Use Check and requeue.**, and the page removes the button. §4.2 summary with this offer: **Not requeued: 1 problem found, and nothing was changed. The comic changed after this batch was planned. Close this item to have the folder checked again at the next folder pass.** ({k} problems: **...{k} problems found, and nothing was changed. These comics changed after this batch was planned. Close this item...**). The row finding is unchanged. |
| **Never appears** | Before any check. With any other finding on the line, including a leftover temporary file (`temp_left`) (**amended 2026-10-17: a temporary file no longer blocks the offer when Amendment 2 B2 covers it**). With one unverifiable backup among several (all or none). With more than 20 problems. | Before any check, and on any other result, including a list with any finding other than `unwritten_changed`. Not guessed from the reason code `other`: the plan is only known to be unreadable after the check says so. |
| **Hidden again** | A new check starts on this line; the ticket leaves; the page reloads (the result lives in the page, not on disk: after a reload, press **Check and requeue** again). | same |
| **Blocked (shown, `aria-disabled`)** | Paused or pausing; any operation running on any line (one at a time across all lines, shared with the check); this card's own operation running. | same |

- Open confirm plus a change of state: if processing is paused, or another folder starts working, while a confirm is open, the confirm **stays open**, its **Delete and requeue** face becomes `aria-disabled` with the matching tooltip from A2, and **Keep it** stays enabled. A confirm never closes under the pointer.
- Starting a new check on this line (**Check and requeue**) clears the offer, the confirm and the list, as §4.2 already says for the list.

### A4. Placement and layout

New **offer block** in the card, directly under the status node: head, reason, Last error, button row, paused note, status node, **offer block**, confirm, problem list, error line. The two original buttons never move: the new buttons are below them.

```
▌Not requeued: 1 problem found, and nothing was      status node (§4.2 variant, A6)
▌changed. Delete the kept backup to requeue, or
▌check again.
▌[ Delete backup and requeue ]                       offer block: flex, wrap, 8 px gap, 40 px high
▌┃Delete this backup and requeue?                    confirm, only when open; full card width
▌┃Batman 003 (2019).cbz was written and verified.    14 px #e7eaf1, max-width 72ch
▌┃The backup is the only way to undo that change.
▌┃Deleting is permanent.
▌┃[ Delete and requeue ] [ Keep it ]                 40 px high, 100 px minimum width
▌ ───────────────────────────────────────────────    problem list (§4.2), unchanged, still shown
▌ Batman 003 (2019).cbz                [Show in folder]
▌ A recovery backup is kept. The comic was written and verified; the backup is the only way to undo that.
```

Plan unreadable: status node, then **[ Close and recheck folder ]**; there is no list.

- **Opener buttons** (both): the **Open folder** style (#242c3b, 1 px #aab4c6 border, text #eef2fb 12.5:1), `min-height:40px`, `max-width:100%`, label may wrap. One blue primary stays per card (**Check and requeue**).
- **Confirm** (Kept backups style): #402b29, 4 px left border #e08a7e, 12 px padding, 8 px radius, 8 px above and below. Heading 16 px 600 #e7eaf1; body 14 px #e7eaf1; `overflow-wrap:anywhere` on names. **Delete and requeue** is #402b29 with a #e08a7e border and #eef2fb text; **Keep it** is the secondary style; both 40 px high, 100 px minimum width, 8 px gap, wrap. Same colour pairs as BackupLocation A5, so its computed ratios carry over: #e7eaf1 on #402b29 10.93:1, #aab4c6 6.30:1, #eef2fb 11.74:1, #e08a7e border on the card 6.29:1, focus ring #bcd8f9 on #402b29 8.98:1 and on the card 11.12:1. Colour carries no meaning; the sentences do.
- The offer block is `hidden` when empty (no stray gap). The confirm is a `role="group"` labelled by its heading, not a live region (focus moves into it). The opener has `aria-expanded` and `aria-controls`.
- Nothing is positioned, sticky or absolute. The confirm pushes the list down; no box resizes another.

| Width | Layout |
|---|---|
| 1280 (and 700 or more) | Offer block one row, left-aligned. Confirm spans the card; its text is capped at 72ch so lines stay readable; its two buttons on one row. |
| 640 | Same: one row of buttons; list rows in one column (§3, below the 700 breakpoint). |
| 320 (about 215 px of text width in the card, about 187 px inside the confirm) | Opener label wraps to two lines (`min-height`, never a fixed height); confirm buttons wrap to two rows, each full-width at most; no horizontal scroll. Expected, not yet measured: Futaba measures (A10). |
| 320 at 200% zoom | Single column holds; confirm text wraps; nothing clipped (the card padding keeps the focus ring visible). |

### A5. Confirm step

- **Delete backup and requeue: always a confirm**, because the delete is permanent. No native dialog, no modal. It opens inside the card (A4) and is the Kept backups confirm in this card's form.
- **Close and recheck folder: no confirm.** It deletes nothing, moves nothing and touches no comic or backup file; Kept backups still lists any backup. The plan it discards is already unreadable. The tooltip and the sentence above the button state the effect, and the same folder can be rechecked at will, so a wrong press costs nothing.
- Confirm text, by what A1 proved. `{comic}` is the comic's file name.

| Case | Heading | Body |
|---|---|---|
| 1 backup, comic is **the original** | **Delete this backup and requeue?** | **{comic} is exactly as it was before the app started writing, so there is nothing to undo. Deleting is permanent.** |
| 1 backup, comic is **the verified result** | **Delete this backup and requeue?** | **{comic} was written and verified. The backup is the only way to undo that change. Deleting is permanent.** |
| {n} backups (n of 2 or more) | **Delete {n} backups and requeue?** | One line per group, only for a group above 0: **{a} comics are exactly as they were before the app started writing; there is nothing to undo.** and **{b} comics were written and verified; their backups are the only way to undo those changes.** (singular: "1 comic is", "its backup is"), then **Deleting is permanent.** |

**Updated 2026-10-17 (Amendment 2): the backup's contents are proved too.** Since the 0.2.5 M1 fix a backup is offered and deleted only if its SHA-256 equals the plan's before-hash, at the check, before the first delete and again under the write guard (A8.1 as amended). "There is nothing to undo" is therefore true of the backup as well as the comic, and the earlier restriction (never "a spare copy", because only the comic was proved) is lifted; no shipped confirm wording has to change. What the copy still must not do is claim more than was proved: a backup that is not proved is never described as a copy (B6).

### A6. Progress, success and failure copy

**Replaced and amended strings** (everything else in §4 stands):

| Where | Text |
|---|---|
| §4.2 summary when the offer shows (all findings are verified kept backups) | **Not requeued: {k} problems found, and nothing was changed. Delete the kept backup to requeue, or check again.** (k of 2 or more: "backups"; k = 1: **1 problem found**) |
| §4.2 `backup_left`, comic is **the original** | **A recovery backup is kept. The comic is exactly as it was before the write, so there is nothing to undo.** |
| §4.2 `backup_left`, comic is **the verified result** | **A recovery backup is kept. The comic was written and verified; the backup is the only way to undo that.** |
| §4.2 `backup_left`, **not proved** | Three wordings by `unproved` (Amendment 2 B6). Only "the comic itself is not proved" keeps: **A recovery backup is kept. Do not delete it until the comic is checked.** |
| §4.4 `plan_unreadable` | **Not checked: the saved plan for this folder cannot be read, and nothing was changed. Check its comics in the folder, then close this item to recheck the folder.** (plus the offer button below it) |

**In flight** (line status node, `role="status"`, same node as §4.1; the confirm stays visible with every button `aria-disabled`, so focus is not dropped):

| Action | Text |
|---|---|
| Delete backup and requeue | **Deleting the backup, then checking this folder's comics again. This can take a few minutes.** ({n} backups: **Deleting {n} backups, then checking...**) No spinner (§4.1). |
| Close and recheck folder | **Closing this item.** |

**Success** (written to `#attentionDone`, the card leaves on the next poll, §4.3; composed as a prefix plus the §4.3 sentence):

| Outcome | Text |
|---|---|
| Deleted, `n` unwritten comics | **Backup deleted. Requeued {folder name}: {n} unwritten comics will be checked at the next folder pass.** (`{b} backups deleted.` for 2 or more; `1 unwritten comic will be`) |
| Deleted, `n` = 0, `w` written | **Backup deleted. Closed {folder name}: all {w} comics in the batch were written and verified.** |
| Deleted, nothing planned | **Backup deleted. Closed {folder name}: the batch had nothing left to write.** |
| Closed and made due | **Closed {folder name}: the folder will be checked again at the next folder pass. No comic or backup file was changed.** |
| Ticket already closed | **This folder is not waiting for help.** (as §4.3; not a failure) |

**Failure, Delete backup and requeue** (line status node; the confirm closes; the page never uses `error()`):

| Server code | Text |
|---|---|
| `paused` | **Nothing was deleted: processing is paused. Resume processing, then try again.** |
| `busy` | **Nothing was deleted: this folder is already being checked. Wait for it to finish.** |
| `folder_unavailable` | **Nothing was deleted: this folder is unavailable. Check that the library drive is connected.** |
| `library_busy` | **Nothing was deleted: another copy of the app is using this library. Close it, then try again.** |
| `changed` (a comic or one of its files no longer matches at the click) | **Nothing was deleted: a comic or one of its files changed since the check. The list below is updated.** (Replaced 2026-10-17, B5: the old text said "a comic changed" also when a backup was simply gone; that is now `file_gone`.) The route returns the fresh check; the page replaces the list and re-evaluates the offer. |
| `delete_failed`, none deleted | **Nothing was deleted: the backup could not be deleted. Close any program using it, then try again.** (plural: "a backup", "using them") |
| `delete_failed`, {d} of {n} deleted | **Deleted {d} of {n} backups. {n-d} could not be deleted, so nothing was requeued. Close any program using them, then check again.** |
| `not_requeued` (the backups are gone; the re-check or the close then failed) | **Backup deleted, but not requeued: {reason}. Use Check and requeue to finish.** {reason}: "processing was paused", or "the check found {k} problems" (the list below is updated), or the server message with its final full stop removed. (plural: **{b} backups deleted, but not requeued...**) |
| No answer | **No answer from the app. The backup may already be deleted. Use Check and requeue to see the current state.** |
| Any other error | **Could not finish: {server message, final full stop removed}. Use Check and requeue to see what was changed.** |

**Failure, Close and recheck folder** (line status node; nothing was changed in every case, so a repeat press is safe):

| Server code | Text |
|---|---|
| `paused` | **Not closed: processing is paused, and nothing was changed. Resume processing, then try again.** |
| `busy` | **Not closed: this folder is already being checked. Wait for it to finish.** |
| `folder_unavailable` | **Not closed: this folder is unavailable, and nothing was changed. Check that the library drive is connected.** |
| `library_busy` | **Not closed: another copy of the app is using this library, and nothing was changed. Close it, then try again.** |
| `gone` | success row **This folder is not waiting for help.** |
| Any other error, or no answer | **Not closed: {server message, final full stop removed, or "the app did not answer"}. Try again.** (an unanswered press may have closed it; the retry then answers `gone`) |

(Amended 2026-10-17: `file_gone` and `writing` are new, `delete_failed`, `not_requeued` and the unanswered line are worded for a temporary file too, B5.) All of these sit in the same status node (`role="status"`). Focus moves to that node after a failure (A7), so the result, including a partial delete, is read at once; if focus is elsewhere the live region announces it politely.

### A7. Focus and keyboard

Tab order per card: **Check and requeue**, **Open folder**, the offer button, then (confirm open) **Delete and requeue**, **Keep it**, then each row's **Show in folder**. Enter and Space native; no new accelerator.

| Event | Focus goes to |
|---|---|
| Offer button pressed (Delete backup and requeue) | **Keep it** (**Keep them**), the safe button. The opener gets `aria-expanded="true"`. |
| **Keep it**, or **Esc** inside the confirm | the offer button; `aria-expanded="false"`. |
| **Delete and requeue** pressed | stays on it (`aria-disabled`, in flight). |
| **Close and recheck folder** pressed | stays on it (`aria-disabled`, in flight). |
| Success (the card leaves) | `#attentionDone` (`tabindex="-1"`); the next Tab reaches the first remaining card. |
| Failure, refusal or partial delete | the line's status node (`tabindex="-1"`); the next Tab reaches the offer button if it is still offered, else the first **Show in folder**. |

- The moves in the last two rows happen only if focus is still on the pressed button, inside the confirm or card that was changed, or on the page body (§7). Operations can take minutes; if Sergei has moved elsewhere, nothing steals focus.
- The 2 s poll never closes a confirm, drops focus from **Keep it** or hides an offer: `confirmOpen`, the offer and the last result live in the keyed `Map` of §8.1 and are cleared only when a new check starts or the ticket leaves.

### A8. Safety requirements for Ender (requirements, not design)

1. **The one deletion rule.** A comic's backup is deleted **only if that comic matches the plan's before-fingerprint, or the verified after-state recorded in `results.json`, by size, mtime and hash.** All three must match. Size and mtime alone never suffice, and the hash is computed from the file bytes read now, never a cached value. No recorded fingerprint means no match. (Amended 2026-10-17, as shipped in 0.2.5 after M1: the backup's own SHA-256 must also equal the plan's before-hash.)
2. **Proved twice.** In the check (to decide the `offer`), and again inside the click's route, immediately before each delete. The click trusts nothing from the page but the ticket id and the backup ids the check issued (the same ids as the rows' problem ids).
3. **No paths from the browser.** The delete removes only the ids that the server **now** re-derives as that ticket's kept backups; a backup that appeared after the check is not deleted. Same refusals as Kept backups delete: a `.bak` file inside a `.comic-metadata-backups` folder inside the configured library, no links or reparse points on the file or its folder, the same library-ownership check as `remove_verified_backup`. Reuse that delete path if it fits; a second implementation is Ender's call to justify.
4. **Offer only when all of it holds:** every finding is `backup_left`, each is verified, and all fit in the 20 visible rows. No `temp_left`, no unverifiable backup, so no backup is deleted that is not on the screen. (Amended 2026-10-17: a `temp_left` is allowed when Amendment 2 B2 covers it.)
5. **All before any.** Prove every comic first; if one fails, delete none (`changed`). Only then delete; a delete that fails stops the loop and reports `delete_failed` with the counts.
6. **Order and guards.** Pause guard, single flight shared with the check, ticket must be `needs_attention`, folder inside the live library, then prove, delete, run the **full** check again, and close and requeue only if that check is clean (the `scheduler.finish(..., queued=True)` effect of §8.3). Re-read the ticket and the pause state immediately before closing. If any step fails, the later ones do not run, and the code names the step reached (`not_requeued` after a delete).
7. **Payload.** The check result gains `offer`: `{kind:'delete_backup', backups:[{id, name, basis:'original'|'written'}], unwritten}` or `{kind:'close_recheck'}`, otherwise absent. The page renders from it and never infers. `basis` selects the A5 and A6 wording per row.
8. **Close and recheck folder** touches no comic, temp or backup file. It does not need a readable plan (that is its purpose). It runs the same guards (pause, single flight, `needs_attention`, folder inside the library), closes the ticket and makes the folder due so the next folder pass re-plans it from the files on disk, then returns `{ok}`. A missing plan and an unreadable plan both return `plan_unreadable` from the check.
9. **Tooltips** ship in the same commit as the controls (A2), with the compare-before-set helper.
10. **Tests that matter:** a comic one byte different with the same size and mtime gets no offer and no delete; a changed mtime gets no offer; matches the before-fingerprint gives `basis:'original'`; matches the after-state gives `basis:'written'`; the comic changes between check and click and nothing is deleted; two backups with one unverifiable give no offer; `temp_left` plus `backup_left` gives no offer; 21 problems of kept backups give no offer; the delete fails on the second of three (partial copy); paused is refused by the server and not only by the page; no request body carries a path; a missing and an unreadable plan both offer **Close and recheck folder** and a new check clears it; a card survives two polls with the confirm open and focus on **Keep it**.

### A9. Offered, not built (resolved 2026-10-17: Sergei said yes; specified in Amendment 2 at the end of this file)

A write interrupted mid-comic "sometimes" leaves a temporary file beside the backup (finding 7). With a `temp_left` finding the offer does not appear, as Sergei's answer reads ("the check's only finding is a leftover recovery backup"), so that case still means deleting the temp file by hand. Offer for Sergei: include a verified-leftover temp file in the same action. **Sergei, 2026-10-17: "Let's fix this: a temp file left next to a backup blocks the delete button." Superseded by Amendment 2; the sentence above describes 0.2.5 as shipped, not the behaviour to build.**

### A10. Acceptance (Futaba, isolated QA; adds to §9)

Measured rects at 320, 640 and 1280 CSS px, 100% and 200% zoom, in each state: offer showing (1 backup, 3 backups); confirm open (original, verified result, mixed); in flight; each failure line; **Close and recheck folder** offer; success with and without remaining cards.
1. Status node, offer block, confirm, buttons, list, rows and error line are pairwise disjoint; the first two buttons do not move when the offer appears; no horizontal overflow; targets at least 24 px wide and 40 px high; focus ring fully visible on the confirm buttons too.
2. Keyboard-only: **Check and requeue**, Enter, hear the result, Tab to the offer button, Enter (focus on **Keep it**), Esc (back on the offer button), Enter again, Tab to **Delete and requeue**, Enter; success lands focus on `#attentionDone`. Repeat with the unreadable plan and **Close and recheck folder**. Repeat with focus moved elsewhere during the operation: focus must not move.
3. Matrix: every row of A2 (blocked states, with a confirm open), A5 and A6; paused while a confirm is open; a second card checking; a backup's comic changed between check and click (`changed`); a backup file locked (none deleted, then partial); no answer.
4. **Fixture library only.** Delete backup and requeue deletes real files. Futaba lists the backup folder before and after and confirms that exactly the offered backups are gone and nothing else changed, and that a comic differing by one byte at the same size and mtime gets no offer. Never against Sergei's real queue.

### A11. Brief Decision Log row (append for Ender)

Append to the Decision column of the §10 row: "...and, inside a check result, **Delete backup and requeue** (only when every finding is a verified kept backup; confirmed) and **Close and recheck folder** (only for an unreadable or missing plan; Sergei 2026-10-16)."

---

## Amendment 2 — leftover temp file (Sergei 2026-10-17)

Date: 2026-10-17. Owner: Judy. Status: reviewable; Sully commits before Ender is briefed. Resolves A9. Sergei, 2026-10-17: "Let's fix this: a temp file left next to a backup blocks the delete button." Also carries the copy fixes the 0.2.5 QA asked for (Futaba m1 and m4, and the "Do not delete it" sentence after M1) and the A5 update. Where this section differs from anything above, this section wins. Layout: no change (B8). **Close and recheck folder** is untouched.

Basis: NN/g (match between system and the real world: a button names what it deletes; error prevention; plain-language recovery), Hick (no new button: the same offer, a longer label), WCAG 2.2 AA (2.5.3 label in name, 4.1.3), ProcessRules § Copy is short, specific, and has no memory, § A new control is born with its tooltip, and the 0.2.5 pattern P5 (a sentence may claim only what the check proved). Read 2026-10-17 from `folder_help.py` (`_inspect`, `_problems`, `delete_backups`, `prove`, `backup_proved`), `app.py` (`_write_metadata_guarded`, `comic_write_guard`), `kept_backups.delete_one`, QA_v0.2.5 (M1, m1, m2, m4).

What the code does: the app copies the comic to `.comic-metadata-backups\{comic}.{time}.bak`, **then** writes its new archive to `{comic file name}.metadata-tmp` beside the comic, then swaps it in; a normal failure removes the temp file in a `finally`, so only a hard stop (power loss, killed process) leaves one, and it sits next to a backup copied just before it. Today `temp_left` is a finding like any other, so the offer never shows and Sergei deletes the temp file by hand first.

### B1. Decisions

| Question | Decision | Why |
|---|---|---|
| Same button, or a new label | **New label naming both files** (B3). Same place, style, states, focus and confirm as A2 to A7. | The label is the accessible name and the first thing Sergei reads. "Delete backup and requeue" over a button that also deletes a second file understates a permanent delete. The exact counts are on the confirm. |
| Confirm | **Always**, the A5 confirm plus one sentence naming the temporary file (B4). | Permanent delete. |
| What is deleted | The kept backups A3 already covers, plus the app's own temporary file for the same comics. Nothing else. | Sergei's sentence. |
| Order | Per comic: **temporary file first, then its backup(s)**. Every proof before the first delete. | A failure between the two leaves a verified backup alone: the state the existing offer already handles. The reverse leaves a temp file with no backup, which has no offer (unless Question 1 is yes). |
| A temporary file with no backup | **Recommend yes**, B7. Question 1 (B11). | Rare, low risk, same standing rule as everything else on the card: a blocker Sergei can only clear by hand should be a button. |

### B2. When it is offered

In Sergei's terms: **the app offers the delete when, for every comic on the line, it can show that the comic is untouched, its backup is an identical copy, the only other thing beside it is the app's own temporary file, and the app is not writing that comic right now.** If any one thing is unproved there is no offer; the rows say what is there and nothing is deleted.

The offer shows after a check on this line when **every** finding is covered, at least one covered finding is a `temp_left`, and all findings are in the visible list (20 rows or fewer; each temporary file is a row, so a line with a backup and a temp file per comic covers at most 10 comics). The server says so with an `offer`; the page never infers. A finding is covered when its comic meets all five:

1. **The comic is untouched.** *Ender:* size, mtime and SHA-256 (bytes read in this request) all equal the plan's before-state: `prove(...)` returns `original`. A comic with a verified result (`written`) never qualifies (a temp file beside a written comic is not from the write that made it).
2. **Every kept backup of the comic is an identical copy.** *Ender:* its SHA-256 equals the plan's before-hash (`backup_proved`, the 0.2.5 M1 rule, unchanged). One unproved backup of that comic uncovers the whole line.
3. **The temporary file is the app's own, for this comic.** *Ender:* the path is exactly `{comic file name}.metadata-tmp` in the comic's own folder (the name `_write_metadata_guarded` builds); a regular file, not a folder, link or reparse point. Its contents are not read: with 1 and 2 proved it holds nothing the comic lacks. The app's own order (temp check, backup copy, temp file) means a temp file beside a backup comes from that write or a later one, so no timestamp test is added.
4. **Nothing is writing that comic.** *Ender:* the comic's write guard (`comic_write_guard`) can be taken, tried without waiting. Probed at the check (a held guard means no offer: the temp file may belong to a live write) and taken for real at the click (B9.2).
5. **It has no other finding.** No `zip_failed`, `unwritten_changed`, `written_changed` or `missing` for the comic.

**Everything is proved again at the click** (B9.1). The page sends only the ticket id and the ids the check issued; the server recomputes the whole offer from disk and refuses unless the ids sent are exactly the files it now offers.

**Never appears:** before any check; with any finding not covered (a different-version or unreadable backup, an unproved or missing comic, a temporary file with any other name or place, a temporary file whose comic is not untouched); while the comic's write guard is held; with more than 20 findings; with Question 1 answered no, a temporary file whose comic has no proved backup. The A3 rows for *Hidden again* and *Blocked* are unchanged.

### B3. Controls and exact copy

Let `b` = backups and `t` = temporary files in the offer, `total = b + t`, and `{P}` = the counts joined by "and", a zero part dropped, each noun singular at 1: **1 backup and 1 temporary file**, **3 backups and 3 temporary files**, **2 backups and 1 temporary file**. With no temporary file (`t = 0`) every A2 string stands as shipped. With one (`t >= 1`; `b = 0` is B7):

| Control / string | Exact copy |
|---|---|
| Offer, visible label | **Delete backup and temporary file, then requeue** (1 comic). Each noun is plural by its own count: **Delete backups and temporary files, then requeue** (3 comics), **Delete backups and temporary file, then requeue** (b 2, t 1). |
| Offer, tooltip | **Delete {P} left in this folder, then close this item and queue the unwritten comics again. You are asked to confirm first.** |
| Offer, accessible name | the visible label, then **: {folder name}** (2.5.3) |
| Confirm face | total 1: **Delete and requeue** (as A2). Otherwise **Delete {total} files and requeue** (**Delete 2 files and requeue**, **Delete 6 files and requeue**). The face repeats the total so it cannot be confirmed blind, and never reads the same as the label. |
| Confirm face, tooltip | **Delete {P} permanently, then requeue.** |
| Back out | **Keep it** when total is 1, else **Keep them**. Tooltip unchanged: **Go back. Nothing is deleted.** |
| Paused or pausing (offer and face) | **Processing is paused. Resume processing to delete {P}, then requeue.** |
| This card's own operation running (offer and face) | **Deleting {P}, then checking again.** |
| Other blocked states | unchanged (A2): **Another folder is being checked. Wait for it to finish.**; **This folder is being worked on. Wait for it to finish.** |
| Status summary when the offer shows (replaces A6) | **Not requeued: {k} problems found, and nothing was changed. Delete the kept {backup\|backups} and leftover temporary {file\|files} to requeue, or check again.** (k = rows; 1 problem: **1 problem found**; each noun plural by its own count) |
| Problem rows | unchanged: `temp_left` **A leftover temporary file is next to this comic: {temp file name}.**; `backup_left` by basis (A6). Both rows keep **Show in folder**. |

Names and paths in all of these are `textContent` with `overflow-wrap:anywhere`, as everywhere in the card.

### B4. Confirm (extends A5)

Heading: **Delete {P}, then requeue?** Body, `{comic}` and `{temp name}` being file names:

| Case | Body |
|---|---|
| 1 comic with 1 backup and 1 temporary file | **{comic} is exactly as it was before the app started writing, so there is nothing to undo. Left beside it: {temp name}, a temporary file made by the app. Deleting is permanent.** |
| Any other mix | The A5 group lines, counted by comics, not files (**{a} comics are exactly as they were before the app started writing; there is nothing to undo.**, **1 comic is exactly as it was...**; the `written` line is kept for completeness and is never produced today), then **Left beside them: {t} temporary files made by the app (listed below).** (**1 temporary file made by the app**), then **Deleting is permanent.** |

Examples. One comic: heading **Delete 1 backup and 1 temporary file, then requeue?**, buttons **Delete 2 files and requeue** and **Keep them**. Three comics: heading **Delete 3 backups and 3 temporary files, then requeue?**, body **3 comics are exactly as they were before the app started writing; there is nothing to undo. Left beside them: 3 temporary files made by the app (listed below). Deleting is permanent.**, buttons **Delete 6 files and requeue** and **Keep them**.

Every sentence states only what was proved: the comic is the plan's before-state (hash), the backup is identical (hash), the temp file has the app's own name for this comic (name) and sits beside it. The copy does not say why the temp file is there.

### B5. In flight, success and failure

In flight (same node and rules as A6): **Deleting {P}, then checking this folder's comics again. This can take a few minutes.** No spinner.

Success: prefix **{P} deleted.** replaces "Backup deleted." / "{b} backups deleted.", then the §4.3 sentence unchanged. For example **1 backup and 1 temporary file deleted. Requeued Batman: 1 unwritten comic will be checked at the next folder pass.** The same prefix goes on the `n` = 0 and "nothing planned" rows of A6. If this click removed nothing (every file was already gone and the check is clean), the prefix is left out.

Failure (line status node; the confirm closes; the page never uses `error()`). Rows not listed stand as in A6 (`paused`, `busy`, `folder_unavailable`, `library_busy`, "Any other error").

| Server code | Text |
|---|---|
| `changed` (a comic or one of its files no longer matches) | **Nothing was deleted: a comic or one of its files changed since the check. The list below is updated.** (all offers; replaces A6) |
| `file_gone` (new, Futaba m1: a file the check offered is no longer there, or the backup folder was replaced) | No temporary file in the offer: **Nothing was deleted: a backup from the check is no longer there. The list below is updated.** With one: **Nothing was deleted: a file from the check is no longer there. The list below is updated.** The route returns the fresh check, as for `changed`. |
| `writing` (new: the comic's write guard is held) | None deleted: **Nothing was deleted: a comic in this folder is being written now. Wait for it to finish, then try again.** Some deleted: **Deleted {d} of {total} files. A comic in this folder is being written now, so nothing was requeued. Wait for it to finish, then check again.** (backups only: "backups", as A6). Today a held guard falls into `delete_failed` and tells Sergei to close a program that is not the cause. |
| `delete_failed`, none deleted | With a temporary file: **Nothing was deleted: a file could not be deleted. Close any program using it, then try again.** |
| `delete_failed`, {d} of {total} deleted | With a temporary file: **Deleted {d} of {total} files. {total-d} could not be deleted, so nothing was requeued. Close any program using them, then check again.** |
| `not_requeued` (the files are gone; the re-check or close then failed) | **{P} deleted, but not requeued: {reason}. Use Check and requeue to finish.** (reasons as A6) |
| No answer | With a temporary file: **No answer from the app. The files may already be deleted. Use Check and requeue to see the current state.** |

### B6. Copy fixes from the 0.2.5 QA

**A backup that is not proved no longer says "Do not delete it until the comic is checked" for every cause.** After the M1 fix that sentence is wrong when the comic was checked and is fine: the backup holds another version. The row wording follows what was proved. Priority when several apply: `comic`, then `backup`, then `unread`.

| `unproved` (server, per `backup_left` row with no `basis`) | What was found | Row finding (replaces A6) |
|---|---|---|
| `comic` | The comic itself is not proved: changed, damaged, missing or never recorded. | **A recovery backup is kept. Do not delete it until the comic is checked.** (unchanged: the backup may be the only good copy) |
| `backup` | The comic is proved untouched, but this backup's SHA-256 differs from the plan's. | **A recovery backup is kept. It is not a copy of this comic, so it may hold another version. Decide in Kept backups.** |
| `unread` | The comic is proved untouched, but the backup could not be read to compare. | **A recovery backup is kept, but the app could not read it to compare it with the comic. Check again.** |

*Kept backups* is the panel's own name. **Show in folder** on the row is unchanged. The summary line keeps **Fix them, then check again.**

**Futaba m1: "a comic changed" when the backup is simply gone.** `changed` now means a comic, or one of its files, no longer matches. A file that is no longer there is its own code, `file_gone` (B5), and the page words it from the offer it holds: a backup, or a file when a temporary file was in the offer. The swapped-folder case (a junction after the check) reads the same, which is true: the app can no longer see the file. **A5** is updated in place above.

### B7. A temporary file with no backup (Sergei 2026-10-17: (a), build it)

**Recommendation: yes, the same action.** A temp file alone next to a comic proved untouched holds nothing the comic lacks. It can only appear if the backup was removed first (Sergei in Kept backups, a cleaner), so it is rare, but it blocks **Check and requeue** exactly like the paired case, and with the order of B1 it is also what a half-failed delete could leave. The check already shows a temp file as a finding; the standing rule is that a blocker Sergei can only clear by hand becomes a button. It is Sergei's call because it deletes a file with no backup beside it.

If yes, the offer uses B2 with condition 2 vacuous (the comic has no kept backup; an unproved one still uncovers the line) and the same route, order, guard and confirm. Only these strings differ from B3 and B4; all others are the B3 templates with `{P}` = `1 temporary file` or `{t} temporary files`:

| String | Copy |
|---|---|
| Label | **Delete temporary file, then requeue** (t = 1), **Delete temporary files, then requeue** |
| Summary | **Not requeued: {k} problems found, and nothing was changed. Delete the leftover temporary {file\|files} to requeue, or check again.** (k = 1: **1 problem found**) |
| Confirm body, 1 comic | **{comic} is exactly as it was before the app started writing. Beside it: {temp name}, a temporary file made by the app. Deleting is permanent.** |
| Confirm body, several | **{a} comics are exactly as they were before the app started writing. Beside them: {t} temporary files made by the app (listed below). Deleting is permanent.** |
| Confirm face | total 1: **Delete and requeue**; else **Delete {t} files and requeue** |

If Sergei says no, or has not answered: not built. A temporary file is then covered only when its comic also has a proved backup in the same offer; a lone one keeps today's behaviour (rows, no offer).

### B8. Layout

No change. The offer block, confirm, list and rows keep A4. Only the strings are longer. The opener label already wraps (`min-height`, never a fixed height); the longest, **Delete backups and temporary files, then requeue** (48 characters), takes two lines at 320 and about three at 320 at 200% zoom. The confirm body gains one sentence and the temp file name (`overflow-wrap:anywhere`, inside the 72ch cap); the confirm face is at most **Delete {total} files and requeue**. Futaba measures (B10).

### B9. Requirements for Ender (requirements, not design)

1. **The click recomputes the offer.** After the guards (A8.6) the route re-derives the offer from disk and requires the ids sent, `backups` and `temps`, to be exactly the ids now offered. An id that is no longer a file of this ticket: `file_gone`, nothing deleted. A file present now that the ids sent leave out, or an offer that no longer exists: `changed`, nothing deleted. Both return the fresh check. Closes Futaba m4 (a hand-made request with a backup id from a check that had a temp file and no offer deleted the backup).
2. **One guard hold per comic.** The comic's write guard covers that comic's proofs (comic hash, each backup hash, the temp file's identity) and the deletes of its temp file and backups, with no release between them. A temp file is never deleted without the guard held: a live writer owns its temp file and removes it itself. `kept_backups.delete_one` takes the guard on its own, so a nested call would fail: restructure it or add a sibling, Ender's call. Guard not available: `writing`, in the loop as well as before it (today an `ArchiveChanged` becomes `delete_failed`).
3. **Order and counts.** All proofs for all comics first; then comics in name order, each its temp file first, then its backups. A delete that fails stops the loop and reports `delete_failed` with `deleted` and `total` in files, temp files included. A file already gone at its own delete counts as done, not failed; `deleted` counts only files this click removed. Reuse the Kept backups refusals for the temp file: inside the comic's folder, regular file, no links or reparse points, library ownership as A8.3.
4. **Payload.** `offer` gains `temps: [{id, name, file}]` beside `backups` (`kind` stays `delete_backup`; `backups` may be empty if Question 1 is yes). The request body is `{ticket, backups:[ids], temps:[ids]}`, never a path. A `backup_left` row with no `basis` carries `unproved: 'comic'|'backup'|'unread'` (B6). New codes: `file_gone`, `writing`. The page counts comics by `basis` once per comic (a comic with a backup and a temp file counts once).
5. **Tooltips** ship in the same commit as the strings (B3), set with the compare-before-set helper.
6. **Tests that matter** (A8.10 stands): a backup plus the app's temp file on an untouched comic gives the offer, and a delete removes both, temp first; a comic one byte different at the same size and mtime gives no offer; a changed mtime gives no offer; a different-version backup plus a temp file gives no offer and the `backup` row wording; an unreadable backup gives the `unread` wording; a temp file named `{comic}.metadata-tmp2`, another comic's temp name, one in a subfolder or in `.comic-metadata-backups`, one that is a folder, one that is a link: no offer; the write guard held: no offer at the check and `writing` at the click, nothing deleted; a temp file that appears after a backups-only check: the old ids give `changed`, nothing deleted; a backup removed after the check, and a temp file removed after the check: `file_gone`; the temp delete succeeds and the backup delete fails: the fresh check offers the backup alone and the message counts "1 of 2"; 11 comics with a backup and a temp file each (22 findings): no offer; Question 1 yes: a lone temp file gives the offer and a lone temp file with an unproved backup gives none; no request body carries a path.

### B10. Acceptance (Futaba, isolated QA; adds to A10)

Fixture library only: **Delete backup and temporary file, then requeue deletes real files.** Measured rects at 320, 640 and 1280 CSS px, 100% and 200% zoom: offer showing (1 comic; 3 comics; the longest label), confirm open (1 comic; 3 comics), in flight, each new or changed failure line (`changed`, `file_gone` with and without a temp file, `writing` none and partial, partial delete, `not_requeued`).
1. A10.1 and A10.2 apply unchanged: disjoint boxes, first two buttons do not move, no horizontal overflow, targets at least 24 px wide and 40 px high, focus ring visible, keyboard run with focus on **Keep them** and back, focus not stolen when elsewhere.
2. Futaba lists the backup folder and the comic's folder before and after: exactly the backups and temp files offered are gone, the emptied backup folder is gone, nothing else changed, Recycle Bin 0. Temp deleted before backup (hold the backup open to see "1 of 2").
3. Every B2 "never" shape, and every row of B3 to B6: label per (b, t), tooltips in each blocked state, the three `unproved` row texts (include a backup locked by another program for `unread`), `file_gone` (the m1 repro: delete the backup in Kept backups, then press the offer), `changed`, `writing` (hold the guard).
4. Backups-only offers still read exactly as in A2 to A6 (regression), and **Close and recheck folder** is unchanged.

### B11. Questions for Sergei

1. **A temp file alone.** If a leftover temp file sits next to a comic that is unchanged and there is no backup, should the same button delete it, and requeue? **(a) Yes: button "Delete temporary file, then requeue", with a confirm (recommended).** (b) No: only a temp file next to a backup is cleaned; a lone one is still deleted by hand. **ANSWERED 2026-10-17 by Sergei: (a). Build B7.**

### B12. Brief Decision Log row (append for Ender)

Append to the Decision column of the §10 row, after A11's text: "...; a leftover temporary file the app made no longer blocks **Delete backup and requeue** when its comic and backup are proved (the button then names both files; Sergei 2026-10-17; `Docs/ComicsMetaOrganizer_UXSpec_FolderHelpActions_2026-10-16.md` Amendment 2)."
