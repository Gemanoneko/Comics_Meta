# Recovery backup location — save outcomes (0.2.4)

Date: 2026-10-16. Owner: Judy. Status: reviewable; Sully commits before Ender is briefed. EXTENDS PerComicRecovery_2026-10-14 §5 (response copy) and its 2026-10-16 supersession note. Adds one location block to two save outcomes. No new modal, no other copy changes. Sergei's decisions of 2026-10-16: show the backup location in the failure error, add a button that opens it in Explorer, give the retained-on-success message the same treatment.

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
| Copy button | None | The path is selectable text (§4). Offered as a question only if wanted. |

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
| Backup file missing, folder present | **This recovery backup is no longer at this location.** |
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

## 9. Questions for Sergei

1. The Lookup **Apply** message (`static/index.html:173`) already prints a retained backup as raw text, "Metadata saved. Recovery backup retained: {path}", with no button and probably the `\\?\` prefix. Give it this same block? Not in this spec.
2. Each failed attempt keeps its own backup, and the notice shows only the latest. Do you want any way to list or clear retained backups later (0.2.2 left 17 backups, 3.19 GB)? This spec only locates one.
3. Do you want a **Copy path** button? Not specced: the path is selectable text.
