# Recovery backup location — save outcomes (0.2.4)

Date: 2026-10-16. Owner: Judy. Status: reviewable; amended 2026-10-16 with Sergei's answers (final section); Sully commits before Ender is briefed. EXTENDS PerComicRecovery_2026-10-14 §5 (response copy) and its 2026-10-16 supersession note. Adds one location block to two save outcomes. No new modal, no other copy changes. Sergei's decisions of 2026-10-16: show the backup location in the failure error, add a button that opens it in Explorer, give the retained-on-success message the same treatment.

Basis: NN/g error recovery and recognition over recall; Jakob (Explorer's own "Show in folder"); WCAG 2.2 AA (1.4.10 reflow, 2.4.7 focus visible, 2.5.8 target size, 4.1.3 status messages). Read from: `static/comic-recovery.js/.css`, `comic_recovery.py`, `app.py` (`/api/open-folder`, `write_metadata`, `filesystem_path`), DesktopShell spec.

## 1. Findings that shape the spec

1. **A plain browser can open Explorer here.** The dashboard binds to 127.0.0.1 and the existing **Open folder** button (`comic-recovery.js:52`) calls `/api/open-folder`, where the server runs `os.startfile`. It is not shell-gated. The new button follows that precedent, so the browser needs no separate case (§4).
2. **Today's path string has a `\\?\` prefix.** `result.backup` is built from `filesystem_path()`, which adds `\\?\` on Windows. It must be cleaned before display (§2).
3. **The failure message can be false.** `backup` is null when the write failed before the backup copy was made. The current text still says "retained recovery backup". It needs a second variant (§3).
4. **The client drops the data.** The failure path throws `result.message` and discards `result.backup`; the success path ignores `backup_retained`. `status()` also reuses one node and rewrites its text, so the block cannot live inside it (§6).

## 2. Decisions

| Question | Decision | Why |
|---|---|---|
| Show folder or full `.bak` path | **Full path** to the `.bak` file | It contains the requested folder (`...\.comic-metadata-backups`). That folder holds one `.bak` per attempt per comic in the same directory, and 0.2.2 kept every one. The file name (`{comic}.{time_ns}.bak`) is the only thing that separates this attempt's backup from its neighbours'. What is shown equals what the button selects. The cost is length, solved by wrapping. |
| Open folder or select file | **Select the `.bak` file** in a File Explorer window | Same reason, and it is Explorer's own "Show in folder" behaviour. Without it Sergei hunts through sibling backups. |
| Display form | Absolute Windows path, backslashes, **no `\\?\` prefix** (`\\?\UNC\srv\share\x` shows as `\\srv\share\x`), complete, never truncated or ellipsised | Recognition, and the path stays pasteable into Explorer's address bar. |
| Copy button | None (Sergei confirmed, 2026-10-16) | The path is selectable text (§4). |

## 3. Visible states

| Outcome (confirm result) | Live region | Message | Location block |
|---|---|---|---|
| Not verified, `backup` set | alert | **The change was not verified. Check the file and retained recovery backup before trying again.** (server text unchanged) | Yes |
| Not verified, `backup` null or empty | alert | **The change was not verified. No recovery backup was made. Check the file before trying again.** | No |
| Saved and verified, `backup_retained` | status (never alert; a kept backup is not an error) | **Change saved and verified. The recovery backup could not be deleted and was retained.** | Yes |
| Saved and verified, backup deleted | status | **Change saved and verified.** (unchanged) | No |
| Any 400 (stale, paused, link problems) | existing | existing | No: no write began |

This supersedes my earlier inline form "…was retained: {path}". Reason: a long path inside a live region is read aloud character by character, and one block serves both outcomes. The path is now the labelled block below.

## 4. Location block

Order inside `#problemDetail`, directly after the status line, normal flow, nothing positioned:

```
Recovery backup                                   label, 14px, #aab4c6
D:\Comics\<Series>\.comic-metadata-backups\       path, 14px, #e7eaf1,
<Comic>.cbz.<19 digits>.bak                       wraps, selectable
[ Show backup in folder ]                         secondary button, 32px high
(error line, only after a failed click)           14px, role=alert
```

- Container reuses the evidence-card tokens: `#1b202b`, 12px padding, 8px radius, 12px block margin. Contrast on that panel: #e7eaf1 13.5:1, #aab4c6 7.8:1, focus ring #bcd8f9 11.1:1. No colour carries meaning; the sentences do.
- Path is its own block-level `p`, so a triple-click selects exactly the path. `overflow-wrap:anywhere`, no fixed width or height, no horizontal scroll. Add break opportunities with `<wbr>` after each `\`, never U+200B, which would be copied into the pasted path.
- The path is plain text, set with `textContent`, never parsed as HTML. It is outside the live region and is not a Tab stop. Screen-reader users reach it in reading order, immediately before the button.
- Button row reuses `.recovery-actions` (wrap, 8px gap). At 320 px or 200% zoom the button wraps below the path; it never sits beside it.

**Button.** Label **Show backup in folder** (names the object, so it cannot be confused with the existing **Open folder** for the comic's own folder). Tooltip (title): **Show this recovery backup file in File Explorer. Nothing is changed.** Secondary styling; same 2px #bcd8f9 focus ring as the other Details buttons.

**Browser and shell are identical.** Both show the path and the button. If Ender instead routes through an Electron bridge (the preload has no open-path call today), the browser shows the block without the button and with no extra explanation: the path is the primary information, the button is the accelerator.

## 5. Button behaviour and errors

- Click asks the server to reveal the backup. No write, no state change. Enabled while processing is paused. Not available mid-save (the notice does not exist then).
- In flight (one request): set `aria-disabled="true"` and ignore clicks. Do not use `disabled`, which can drop keyboard focus. Label does not change. A double click makes one request.
- Success: Explorer opens with the file selected; no in-app text. Focus stays on the button.
- Errors appear in the block's own error line under the button, **never through `status()`**, which would overwrite the original failure message and the path. Cleared on the next click and when the notice is replaced.

| Server finding | Error line |
|---|---|
| Backup file missing, folder present | **This recovery backup is not at this location.** |
| Library folder unavailable | **Folder is unavailable. Check that the library drive is connected.** (existing `/api/open-folder` wording) |
| Anything else, including select failing | **Could not open File Explorer. Use the path above.** |

The visible path is the safety net for every error row.

## 6. Lifecycle, focus, keyboard

- The block is created only by a save outcome in §3, after `setBusy(false)`. (`setBusy` snapshots and disables every button in the dialog; a button built earlier would stay disabled.)
- It is a **sibling after the status node**, never a child. `status()` rewrites its node's text, which would wipe a child and put the button in the live region.
- It is removed whenever `status()` writes a different message (including the next "Saving this change…"), `render()`/`open()` rebuilds the box, or the dialog closes. It survives the user opening another recovery section, as today's message does.
- Focus lands on the message, as today (tabindex -1). The button is not auto-focused: it launches another app and the message should be read first. One Tab reaches the button. Enter and Space activate it (native button). Esc keeps its existing meaning.
- Scroll-on-focus brings the message into view; the path and button follow within one Tab. If the dialog is scrolled, Tab scrolls the button into view; the focus ring must not be clipped (the panel's 12px padding covers the 2px offset).

## 7. Acceptance (Futaba, isolated QA)

Measured rects, not impressions, at 320/640/1280 CSS px, 100% and 200%, with the Details dialog scrolled, in both block states:
1. Label, path, button and error-line rects are pairwise disjoint; the block does not intersect any other Details control.
2. `#problemDetail` has no horizontal overflow (`scrollWidth <= clientWidth`). Test paths: 200+ characters, spaces, `[ ]`, non-Latin characters, one unbroken 60+ character segment, a `\\?\`-prefixed input (must display without it) and a `\\?\UNC\` input.
3. Button rect at least 24x24, 32 high; focus ring fully visible.
4. Selecting the path paragraph and copying yields exactly the displayed string (no hidden characters).
5. Matrix: backup null (no block, second failure copy); backup deleted (no block); retained on success (status role, no alert); file missing and folder missing (each error row, focus stays on the button, original message and path intact); paused (button enabled); double click (one request); browser without `comicDesktop` (same as shell).
6. Explorer launch is stubbed. A live Explorer window is native focus and needs separate authorisation.

## 8. For Ender

1. Carry `backup` and `backup_retained` from the confirm result to the notice on both outcomes (§1.4).
2. New route modelled on `/api/open-folder`: same Origin/Host checks, placed before the pause guard. The request names the comic id and the backup file name only. The server rebuilds `<comic folder>\.comic-metadata-backups\<name>`, applies the same containment checks as `remove_verified_backup` (no links, `.bak`, comic-name prefix), checks existence, and returns a code per row in §5. It never opens a browser-supplied path.
3. Explorer's select needs a normal path without `\\?\` and quoting for names that contain commas. A path over MAX_PATH may not select: fall back to opening the folder, else the generic error row.
4. The failure copy needs two strings (`comic_recovery.py:275` today has one).
5. Flag, no UI change: if `shutil.copy2` fails partway, `attempt['backup']` is never set but a partial `.bak` may remain, so "No recovery backup was made" is slightly untrue for that case.

## 9. Questions for Sergei — answered 2026-10-16 (see Amendment)

1. The Lookup **Apply** message (`static/index.html:173`) already prints a retained backup as raw text, "Metadata saved. Recovery backup retained: {path}", with no button and probably the `\\?\` prefix. Give it this same block? Not in this spec.
2. Each failed attempt keeps its own backup, and the notice shows only the latest. Do you want any way to list or clear retained backups later (0.2.2 left 17 backups, 3.19 GB)? This spec only locates one.
3. Do you want a **Copy path** button? Not specced: the path is selectable text.

---

# Amendment — Sergei answers 2026-10-16

Owner: Judy. Status: reviewable; Sully commits before Ender is briefed. EXTENDS the spec above. Sergei's answers to §9: (1) yes, the Lookup Apply message gets the same path block and **Show backup in folder** button; (2) yes, a way to list and clear kept backups; (3) no Copy path button.

Basis: NN/g (user control and freedom, error prevention, recognition over recall), Hick (one surface, two buttons per row), Jakob (Explorer's Show in folder; Windows confirm with the safe button focused), WCAG 2.2 AA (1.4.3, 1.4.10, 1.4.11, 2.4.7, 2.5.3, 2.5.8, 4.1.3). Read from: `static/index.html`, `static/comic-recovery.css`, `static/shell-ui.js`, `app.py` (`/api/apply`, `/api/open-folder`, `write_metadata`, `remove_verified_backup`), `maintenance.py`.

Edits made in the body above: §2 Copy button row (decided: none); §5 first error row reworded, because "no longer" broke the copy standard's no-history clause; §9 marked answered.

## A1. Lookup Apply gets the same block (answers §9.1)

**Finding.** The retained branch at `index.html:173` cannot run today. `/api/apply` always answers `backup_removed_after_verification: true`. When deleting the backup is refused after a good save, `write_metadata` raises, so the page prints the raw server error ("Backup verification failed.") with no path and no hint that the metadata was saved. A failure after the backup copy also loses the path, because `/api/apply` passes no `attempt`. The outcomes below need small server changes (A7.1).

| Apply outcome | `#lookupMessage` text | Block |
|---|---|---|
| Saved, backup deleted | **Metadata saved and verified. Recovery backup deleted.** (unchanged) | No |
| Saved, backup kept | **Metadata saved and verified. The recovery backup could not be deleted and was retained.** (replaces "Metadata saved. Recovery backup retained: {path}") | Yes |
| Not verified, backup made | **The change was not verified. Check the file and retained recovery backup before trying again.** (same sentence as §3 row 1) | Yes |
| Any other error | server text, as today (nothing was changed, no backup) | No |

- **Block** = the §4 component unchanged: label, path (no `\\?\`, `<wbr>` after each `\`), **Show backup in folder**, error line (§5 table), same tooltip. One component, two hosts: its styling must not depend on `#problemDetail`, where it lives today (that scope is what gives the button its 32 px height).
- **Placement:** sibling directly after `#lookupMessage`, before `#candidates`. Never a child of the live region.
- **Removed** when `#lookupMessage` is rewritten by anything else (new search, issue list, preview, next Apply), when `review()` rebuilds the dialog, and when it closes.
- **Focus:** give `#lookupMessage` `tabindex="-1"` and focus it on the two block outcomes only. The Approve button hides on a successful save, which would otherwise drop focus; the failure case matches §6. The button is never auto-focused. The live region stays polite as today.
- Acceptance is §7 again, inside the dialog (at 320 px the path block has about 230 px of text width).

## A2. Where the kept-backups list lives (answers §9.2)

| Option | Verdict | Reason |
|---|---|---|
| Header button, beside Version, API keys, Check for updates, Pause | No | The header already reflows below 790 px. This is a rare cleanup, not a daily control (Fitts, Hick). API keys is shell-only; this must also work in a plain browser. |
| Details dialog in a third mode (the API keys precedent) | No | A modal makes the page behind inert, a 1000 px dialog is narrow for a long list, and the dialog is built around one comic. |
| New page | No | The app has no navigation. |
| **Second `<details>` in the Live library panel, directly under Manual scan controls** | **Yes** | It is the only housekeeping area the UI has (`maintenance.py` cleans automatically and has no UI). Collapsed by default, native keyboard behaviour, full panel width up to 1450 px, no modal on a modal. |

Both summaries in that panel get `min-height:32px` (4 px padding, 24 px line height): the default summary line is shorter than the 32 px target, and the pair must match. Futaba measures it.

```
Live library
 ▸ Manual scan controls
 ▾ Kept backups · 17 · 3.19 GB                             summary, always shows count and size
   Copies of comics from before a change. A copy is kept when the
   change did not verify or the copy could not be deleted.
   [ Refresh ] [ Delete all ]                              toolbar, wraps
   Deleted 17 backups. 3.19 GB freed.                      status line (role=status)
   ┌──────────────────────────────────────────────────────────────┐
   │ Batman 003 (2019).cbz            [ Show in folder ] [ Delete ]│  ≥ 700 px: buttons right
   │ D:\Comics\Batman                                              │
   │ 412 MB · 3 days ago · Save not verified                       │
   └──────────────────────────────────────────────────────────────┘
   (one item per backup, newest first, 8 px apart)
 ≤ 700 px: the buttons drop below the three text lines, left-aligned, wrapping.
```

Everything is in normal flow. No popover, no sticky bar, no inner scroll box (the page scrolls). Native `title` tooltips only.

## A3. What the list shows

Summary (collapsed and open): **Kept backups · 17 · 3.19 GB**. Zero: **Kept backups · none**. First read: **Kept backups · checking…**. Failed read: **Kept backups · unavailable**. Size is Explorer-style (1024 base, three significant digits: 412 MB, 41.2 MB, 3.19 GB). Count and size cover every listed backup. The summary is the only total; the open panel does not repeat it.

| Per-item line | Content | Rules |
|---|---|---|
| 1 | **Comic file name** (the backup name without its `.{digits}.bak` tail) | 16 px, 600, #e7eaf1, wraps anywhere |
| 2 | **Folder**: the comic's own folder (not the hidden backup folder), no `\\?\` | 14 px, #aab4c6, wraps, `<wbr>` after each `\` |
| 3 | **Size · age · why kept** | 14 px; size and age #aab4c6, reason #e7eaf1 |

- **Age** is relative and static until the next read: **just now**, **12 min ago**, **3 hours ago**, **4 days ago** up to 30 days, then a date (**12 Aug 2026**). Wrap in `<time datetime>` with the full local time as `title`, as a bonus only.
- **Why kept** has three values: **Save not verified** (failed save), **Saved; backup could not be deleted** (delete refused), **Reason not recorded**.
- **Sort:** newest first, ties by name. No sort control and no grouping (Hick). Several backups of one comic are told apart by age.
- Text is plain, set with `textContent`. Name and folder are selectable and not Tab stops.

**When it reads.** Page load (summary only), when the panel opens, **Refresh**, after a delete, and after any save outcome that keeps a backup (§3, A1). Never on the 2-second poll.

| State | Text | Role |
|---|---|---|
| Reading | **Checking for kept backups…** | status |
| Read failed | **Could not check for kept backups. Use Refresh to try again.** | alert |
| Empty | **No kept backups** (toolbar keeps Refresh; Delete all is hidden) | plain text |
| List bounded | **Showing the newest 500. Delete some to see the rest.** (summary reads **Kept backups · 500+**) | plain text |

## A4. Actions

| Control | Visible label | Tooltip (`title`) | Accessible name |
|---|---|---|---|
| Panel summary | Kept backups · … | **Show or hide the recovery backups the app has kept.** | visible text |
| Refresh | **Refresh** | **Look for kept backups again. Nothing is changed.** | Refresh |
| Delete all (shown only when 2 or more are listed) | **Delete all** | **Delete every backup listed here. You are asked to confirm first.** | Delete all kept backups |
| Row: show | **Show in folder** | **Show this recovery backup file in File Explorer. Nothing is changed.** (same as the existing button) | Show in folder: {name}, {age} |
| Row: delete | **Delete** | **Delete this backup file. You are asked to confirm first.** | Delete: {name}, {age} |
| Confirm: row | **Delete backup** / **Keep it** | **Delete this backup file permanently.** / **Go back. Nothing is deleted.** | visible text |
| Confirm: all | **Delete {n} backups** / **Keep them** | **Delete all listed backup files permanently.** / **Go back. Nothing is deleted.** | visible text |

- **Show in folder** behaves as the existing button: same route as §8.2, same errors as the §5 table, error line inside the item, nothing through the status line. It stays enabled while a delete confirm is open, so Sergei can look at the file first.
- **Delete** never deletes on its own click. It opens a confirm.

**Confirm copy.** Always a confirm, per row and for all. Safety copy says deleting removes the only undo.

Row, below the item's buttons, full item width:

```
Delete this backup?
It is the only way to undo the change to Batman 003 (2019).cbz. Deleting is permanent.
[ Delete backup ] [ Keep it ]
```

- Reason is **Save not verified**: the second line becomes **The save to Batman 003 (2019).cbz was not verified, so this may be its only good copy. Deleting is permanent.**
- Delete all, directly under the toolbar:

```
Delete all 17 kept backups (3.19 GB)?
They are the only way to undo those changes. Deleting is permanent.
3 are from saves that were not verified.     (only if above 0; "1 is from a save that was not verified.")
[ Delete 17 backups ] [ Keep them ]
```

- If the list is bounded, the heading reads **Delete the 500 listed backups (…)?**.
- The count and size come from the exact set Delete all will remove (A7.5). The button face repeats the count so it cannot be confirmed blind.
- Confirm box: #402b29, 4 px left border #e08a7e, 12 px padding, 8 px radius (the shell failure-notice style). Buttons 40 px high, 100 px minimum width (the recovery confirm style). **Delete backup** is #402b29 with a #e08a7e border and #eef2fb text; **Keep it** is the secondary style. One confirm at a time: opening another replaces the open one.

**Results.**

| Outcome | Text | Role |
|---|---|---|
| Row deleted | **Backup deleted.** The row leaves; the summary updates. | status |
| All deleted | **Deleted 17 backups. 3.19 GB freed.** | status |
| Partly deleted | **Deleted 15 of 17 backups. 2 could not be deleted and are still listed.** | alert |
| In flight | **Deleting…** / **Deleting 17 backups…** | status |

Row delete failures appear in an error line inside that item (14 px, `role="alert"`, cleared on the next action on that item or on Refresh):

| Server finding | Error line |
|---|---|
| The comic is being written | **This comic is being updated. Try again in a minute.** |
| File in use or access denied | **Could not delete this backup. Close any program using it, then try again.** |
| Refused (not a recovery backup in the library) | **Not deleted. This is not a recovery backup in your library.** |
| Not found | **Backup not found. Use Refresh to update the list.** |
| Library drive missing | **Folder is unavailable. Check that the library drive is connected.** |
| Anything else | **Could not delete this backup. Try again.** |

## A5. Layout, no overlap, keyboard

- Item card: border 1 px #38445a (decorative, not relied on), 12 px padding, 10 px radius, 8 px between items. Item grid: text column `minmax(0,1fr)`, buttons column `auto` at ≥ 700 px (the page's own breakpoint); one column below. Confirm and error line span the full item width (`grid-column:1/-1`).
- Per-row buttons: 14 px, `min-height:32px`, `min-width:24px`, 8 px gap (the chip metrics). Toolbar buttons the same. Focus ring 2 px #bcd8f9, offset 2 px; the 12 px item padding keeps it unclipped.
- At 320 px the item text width is about 218 px: **Show in folder** and **Delete** fit on one row or wrap; **Delete backup** and **Keep it** (100 px minimum each) fit or wrap. No fixed widths or heights, no horizontal scroll, `overflow-wrap:anywhere`. At 200% zoom the single column holds.
- Contrast (computed from the hex values): #e7eaf1 on #1b202b 13.54:1; #aab4c6 on #1b202b 7.80:1; on the confirm #402b29, #e7eaf1 10.93:1, #aab4c6 6.30:1, #eef2fb 11.74:1; #aab4c6 button border on #1b202b 7.80:1; #e08a7e border on #1b202b 6.29:1; focus ring #bcd8f9 on #1b202b 11.12:1 and on #402b29 8.98:1. Colour carries no meaning; the sentences do.
- **Keyboard:**
  - The summary is a native Tab stop; Enter or Space toggles it and focus stays on it. Opening starts the read.
  - Tab order: Refresh, Delete all, then per item Show in folder, Delete. Items are not stops.
  - **Delete** and **Delete all** open the confirm and move focus to **Keep it** or **Keep them**, the safe button. The opener gets `aria-expanded="true"` while its confirm is open. **Esc** closes the confirm and returns focus to the opener. Tab order inside: delete button, then keep button.
  - In flight, buttons get `aria-disabled="true"` and ignore clicks (never `disabled`, which can drop focus).
  - After a row is deleted, focus moves to the next item's **Show in folder** (the previous item's if it was last); with an empty list it moves to the empty-state text (`tabindex="-1"`). After Delete all it goes to the summary.
  - The modal Details dialog makes this panel inert while open; the summary refreshes in the background after a dialog outcome.

## A6. Acceptance (Futaba, isolated QA)

Measured rects at 320/640/1280 CSS px, 100% and 200%, in each state: collapsed, open with 17 items, row confirm open, Delete all confirm open, an error line showing, empty, bounded.
1. Summary, toolbar, items, buttons, confirm and error-line rects are pairwise disjoint; no item box intersects its neighbour; no horizontal overflow in the panel.
2. Targets at least 24 px and 32 px high; confirm buttons 40 px; summaries 32 px; focus ring fully visible.
3. Test names and folders: 200+ characters, spaces, `[ ]`, non-Latin, one unbroken 60+ character segment, a `\\?\`-prefixed folder (must display without it).
4. Keyboard-only run: open the panel, reach Show in folder, open a confirm, Esc back, delete one row, confirm focus lands as in A5, then Delete all.
5. Reason matrix (all three labels), plus every error row in A4 and the partial-delete alert.
6. **Delete runs only against a throwaway fixture library.** Sergei's real kept backups (0.2.2 left 17, 3.19 GB) are real undo copies and are never touched by a test. Explorer launch is stubbed (§7.6).

## A7. For Ender (requirements, not design)

1. **`/api/apply` (A1):** return real `backup` and `backup_retained` values instead of a hardcoded `true`; answer delete-refused-after-save as a success with `backup_retained: true`, not a 400; on a failure after the backup copy, return `backup` in the error response. The page must be able to tell the outcomes apart.
2. **Source of the list:** the app's own record of retained backups, or a bounded scan of `.comic-metadata-backups` folders inside the configured library, never outside it. The bound is at least 500 and is disclosed (A3), never silent. A scan must not run on the 2-second poll. If the app keeps its own record, count and size may ride the existing progress response.
3. **Per backup the page needs:** an opaque id issued by the list; comic file name; comic folder; size in bytes; created time; reason (`save_not_verified`, `delete_refused`, or none, which shows **Reason not recorded**). The reason has to be recorded at the moment the backup is retained (failed recovery save, refused cleanup, the A1 outcomes); a scan alone cannot know it.
4. **Only finished retentions are listed.** A backup that belongs to a write still in progress is neither listed nor deletable; delete takes the same per-comic writer guard as a save, and answers the "being written" row in A4.
5. **Delete accepts the id, never a path from the browser, and refuses anything that is not a `.bak` file inside a `.comic-metadata-backups` folder inside the configured library.** Checked after resolving the path, with no links or reparse points on the file or its folder, and the same library-ownership check as `remove_verified_backup`. It returns one code per A4 row. **Delete all** sends the ids the confirm counted and removes exactly those; a backup that appeared after the list was read is not deleted.
6. **Show in folder** for rows goes through the §8.2 reveal route, id-based, with the same containment checks as delete.

## A8. Questions for Sergei

1. Delete: permanent, or move to the Recycle Bin? Default: permanent (matches the app's existing backup cleanup and actually frees the space). If Recycle Bin, the confirm copy changes to say so and the only-undo warning softens.
2. Should **Delete all** include backups from saves that were not verified? Default: yes, and the confirm counts them. Alternative: it skips them and clears only leftovers of verified saves; those are then deleted one by one.
