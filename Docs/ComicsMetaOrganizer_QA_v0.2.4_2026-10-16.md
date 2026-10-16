# Comics Meta Organizer — QA release gate, v0.2.4

Date: 2026-10-16. Owner: Futaba. Lean pass ordered by Sergei (one attempt per step, failures recorded not looped). Previous gate: `ComicsMetaOrganizer_QA_v0.2.3_2026-10-16.md` (GO).

**Verdict:** GO

GO means: no Blocker. The build under test behaves as specified in the five areas below, and the unpacked build is the one tested. **One Major (M1) is not a defect in 0.2.4 but changes what Sergei should expect:** the in-app update check runs in the app that is already installed, so 0.2.4's .pyc fix cannot rescue the 0.2.2 to 0.2.4 hop he is stuck on. Jane should plan that hop (see M1) before telling him to "just update". The real install/update flow was **not tested** (see "Not tested").

## Build under test

- Comics Meta Organizer 0.2.4, committed HEAD `e2db1c3` ("chore: bump version to 0.2.4"), worktree `C:/Antigravity Projects/Worktrees/Comics Meta Organizer/installer`. Tree clean when the pass began. One untracked file appeared during the pass: `Docs/ComicsMetaOrganizer_CodeReview_v0.2.4_2026-10-16.md` (Senua's, not mine). No qa-handoff receipt script run (lean).
- Installer `dist/Comic-Metadata-Setup-0.2.4.exe`, SHA-256 `0492626650fe202cc15a9acaaa9677f5458fc271e8096e7f50b132fd979d1da9`, equal to the brief, re-checked at the end. SHA-512 and size (149,466,701) equal `latest.yml`. **Never executed.** I did not re-extract the installer payload this round (done in 0.2.3); instead the packaged `app.asar` was read with `@electron/asar`: its `desktop/update-capsule.cjs` is byte-identical to HEAD (sha256 `1892a1ee…4543`), and its `engine.cjs` contains `PYTHONDONTWRITEBYTECODE:'1'`.
- Baseline of the build tree before anything ran: `dist/win-unpacked` held 0 `.pyc` and 0 `__pycache__`.

## How it was run (isolation)

- `dist/win-unpacked/ComicMetadata.exe` in private QA mode, as in 0.2.3. `desktop/main.cjs`, `qa-policy.cjs` and `preload.cjs` are unchanged since 0.2.3 (git diff stat empty), so the 0.2.3 confirmation stands: `app.setPath('userData', …)` runs before `requestSingleInstanceLock()`, so the lock is keyed to the private profile and cannot hand off to Sergei's app. Observed: the QA main process ran with `--user-data-dir` under my private root; windows `show:false`, offscreen.
- Private root `%TEMP%\f24t\illuminati-cmo-qa-x`, engine 47621, feed and model stand-in 47622/47623, CDP 47624. Proxies pointed at a dead port with loopback excluded. Every child process `windowsHide:true`; no polling loops (one-off hidden process-table reads only).
- Sergei's live app: baseline main PID 11104, listeners 8765 (PID 73392) and 11434 (PID 34100). After: identical. Nothing read or wrote `%LOCALAPPDATA%\ComicsMeta`, `Y:\Comix`, the updater folder, or ports 8765/11434. No installer or uninstaller was run. No real network update check (the QA policy allows only loopback).
- QA app launched four times (first-run setup; seeded run; resume and quit from Running; API fuzz), each quit through the product. Total running time about 22 minutes with the engine and two real worker processes.
- Fixture library: 13 seed comics plus 12 added (stored, bzip2, LZMA, LZMA with a 1.5 GiB dictionary property, lying-size deflate, honest 30 MB entry; two recovery and four Lookup comics) and 8 synthetic kept backups in 4 folders (132-character folder, non-Latin and bracket folder, 70-character unbroken folder). Dummy keys only.

## Results

### 1. Update prepare against a USED runtime (no-install method)

Copy of `resources/{runtime,engine}` in scratch; bundled Python run **without** `-B` importing PIL (plugins, a PNG to JPEG round trip), greenlet, pyee, playwright (sync and async), then the worker modules (`worker`, `browser_worker`, `browser_search`, `free_search_browser`, `supervisor`, `app`), then Playwright driver start and stop (state redirected to scratch).

| Step | Result |
|---|---|
| Drift reproduced | Pass. 95 `.pyc` in 7 `__pycache__` folders under `runtime/python` (greenlet, PIL, playwright x4, pyee) and 17 in `engine/__pycache__`. Before the run: 0. |
| 0.2.4 packaged `prepareUpdateCapsule` on the used copy | Pass. SUCCESS in 6.3 s. Capsule has 465 files = the 465 in the manifest, 0 SHA-256 mismatches, **0 `.pyc`, 0 `__pycache__`**, helper copied. Repeated after the variants below: same. |
| Control, one non-.pyc file (`junk.txt`) in a `__pycache__` | Refused: "Update runtime source closure differs". |
| Control, the 0.2.3 build's `update-capsule.cjs` on the same used copy | Refused with the **old error**, "Update runtime source closure differs" (module taken from the 0.2.3 installer payload; identical to `git show 6f43d4d`). |
| Extra: subfolder in `__pycache__`; a `.py` in it; `name.pyc.tmp`; `.pyc` beside the source (not in `__pycache__`); a listed source file changed by one byte; a listed file removed; a new unlisted folder | All refused, same message. |
| Extra: interpreter temporary name `name.pyc.<digits>` in `__pycache__` | Accepted (as the code comment says); capsule 0 `.pyc`. |
| Extra: `.pyc` that is a symbolic link | Could not set up (EPERM creating a link without privilege). Untested. |
| 0.2.4 in QA mode with real workers: its own `dist/win-unpacked/resources/runtime` (521 entries, 468 files) and `engine` (61 entries) compared by name, size and mtime before, during, and after all four sessions | Pass. 0 added, 0 removed, 0 changed, **0 `.pyc`, 0 `__pycache__`** anywhere under `win-unpacked`. Engine peak commit 37 MB. |
| Control for that measurement | Same method sees 95 + 17 new files after the no-`-B` run above, so a write would have shown. |
| Env variable alone (no `-B`), the same imports plus Playwright driver start and stop, fresh copy | Pass. 0 new files in `runtime` and in `engine`. So the environment variable `engine.cjs` sets reaches a Python that has no `-B`. |

Limit: browser search is off in the fixtures and a real browser would be launched on Sergei's desktop, so the Playwright import path was exercised in the copy, not inside the running app.

### 2. Backup location, Kept backups

**Failed or unverified recovery save.** The failure was a real sharing violation: another process held the comic open, so the write failed after the backup copy was made.

| Check | Result |
|---|---|
| Message and block | Pass. Alert "The change was not verified. Check the file and retained recovery backup before trying again." Below it the block: label "Recovery backup", the **full path of the real `.bak`** (equal to the one file on disk), button **Show backup in folder** with the specified tooltip. Block is a sibling after the status node, not inside a live region; focus on the message; path is not a tab stop. |
| Path text | Pass. No `\\?\` prefix; `<wbr>` after each backslash (10); no hidden characters; selecting the paragraph and reading the selection gives exactly the displayed text. |
| Comic file | Unchanged (SHA-256), no `.metadata-tmp` leftover. |
| Geometry at 320, 640, 1280 CSS px (dialog scrolled to the block) | Pass. Label, path, button rects pairwise disjoint (0.5 px tolerance for 0.1 px rounding); `#problemDetail` scrollWidth equals clientWidth; button 164 x 32. |
| Hostile paths through the same component (client side): 230 characters with spaces and `[ ]`, non-Latin, one 90-character segment, `\\?\D:\…`, `\\?\UNC\srv\share\…` | Pass at all three widths: no overlap, no overflow, copy equals shown, prefix stripped (`\\srv\share\…` for UNC), button 164 x 32. |
| Button: two clicks in the same tick (reveal stubbed) | One request; `aria-disabled` set while in flight (not `disabled`); label unchanged; no in-app text on success; request body is `{"id":<32 hex>}`, never a path. |
| Button: backup file removed, real server answer | Error line (role alert) "Could not find this backup. Check the path above."; focus stays on the button; original message and path intact; one error line after a second click; error rect disjoint from the button. See m2 for the wording. |
| Read-only archive, recovery save | Pass. Message "The change was not saved because this comic file is read-only. The file was not changed. Turn off Read-only in the file's Properties, then try again." plus the block; file byte-identical (hash and mtime); the new copy is listed as **"Not saved; file was not changed"**. |
| Failure before any backup copy (leftover `.metadata-tmp`) | Pass. "The change was not verified. No recovery backup was made. Check the file before trying again."; no block; no backup on disk. |
| Saved and verified, backup deleted | Pass. "Change saved and verified."; no block; no backup folder. |
| Saved and verified, backup kept (a process held the backup open so delete failed) | Pass. **status** role (not alert): "Change saved and verified. The recovery backup could not be deleted and was retained." plus the block. |
| Block removed on a different status message or on closing the dialog | Pass (close checked). |

**Lookup Apply** (Details, Find series, Select, Select, Approve):

| Outcome | Result |
|---|---|
| Saved, backup deleted | "Metadata saved and verified. Recovery backup deleted."; no block. |
| Saved, backup kept | Pass. "Metadata saved and verified. The recovery backup could not be deleted and was retained." plus block as sibling after `#lookupMessage` (not in the live region), real path, button; focus moved to `#lookupMessage` (tabindex -1). |
| Failed after the backup copy (comic held open) | Pass. "The change was not verified. Check the file and retained recovery backup before trying again." plus block; file unchanged. |
| Block removal | Pass. Gone after a new search (message rewritten) and after closing the dialog. |
| Geometry 320, 640, 1280; copy equals shown | Pass. No overlap; block inside the dialog. |
| Read-only comic | See m1. |

**Kept backups list** (second `<details>` in Live library):

| Check | Result |
|---|---|
| Summaries | Both summaries 32 px high (`min-height:32px`). Summary text "Kept backups · 15 · 453 MB" (1024 base, three digits) with 7 backups made by real flows and 8 synthetic. |
| Rows | Pass. Newest first. Name, folder (no `\\?\`, `<wbr>`), "size · age · reason". Ages "just now", "1 min ago", "12 min ago", "2 hours ago", "1 day ago", "5 days ago", "1 Sep 2026" (45 days); `<time>` carries the full time. Sizes "1.20 KB", "41.2 MB", "412 MB", "0 bytes". All four reason labels seen: Save not verified, Saved; backup could not be deleted, **Not saved; file was not changed**, Reason not recorded. Accessible names "Show in folder: {name}, {age}" and "Delete: {name}, {age}". 200+ character name and folder, brackets, non-Latin, 70-character segment: wrap, no overflow. |
| Layout at 320, 640, 701, 1280 | Pass. No overlap between items, text, buttons, confirm, error line; 8 px gaps; buttons 32 high; below 700 px the buttons drop below the text, from 701 px they sit beside it; no overflow inside the panel. Open panel adds no sideways scroll of its own (see P3). |
| Row Delete | Pass. Opens a confirm with focus on **Keep it**, opener `aria-expanded=true`, one confirm at a time. Copy per reason matches the spec and the not-saved variant ("only an extra copy"). Buttons 40 high, 115 and 100 wide; box `#402b29`, 4 px `#e08a7e` left border, 8 px radius. Enter on Delete opens it; Shift+Tab reaches Delete backup; Esc closes it and returns focus to Delete. |
| **Delete is permanent** | Pass. "Deleting…" then "Backup deleted."; the file is gone; summary and row count update; focus moves to the next row's Show in folder; the Recycle Bin listing for my profile is unchanged (84 entries before and after). |
| Delete all | Pass. Shown only for 2 or more (hidden with exactly 1). Confirm "Delete all 14 kept backups (453 MB)?", "They are the only way to undo those changes. Deleting is permanent.", "6 are from saves that were not verified.", "1 is a copy of a file that was not changed."; buttons "Delete 14 backups" / "Keep them" (40 high). Esc and Keep them return focus to Delete all and delete nothing. |
| Partial delete | Pass. One backup held open, one added after the list was read: "Deleted 13 of 14 backups. 1 could not be deleted and is still listed." (alert); the late file was not deleted (the counted set is exact); focus on the summary. |
| Final delete and empty state | "Deleted 2 backups. 1.51 KB freed." (status); summary "Kept backups · none"; "No kept backups" (tabindex -1); Delete all hidden, Refresh kept; empty backup folders removed. Geometry at 3 widths clean. |
| Bounded list | 501 files: summary "Kept backups · 500+", "Showing the newest 500. Delete some to see the rest.", confirm "Delete the 500 listed backups (499 KB)?", exactly 500 deleted, the 501st survives. List call 0.5 s. |
| Row error lines (role alert, inside the row, focus back on Delete) | Pass for each: not found "Backup not found. Use Refresh to update the list."; held open "Could not delete this backup. Close any program using it, then try again."; comic being written "This comic is being updated. Try again in a minute."; folder renamed "Folder is unavailable. Check that the library drive is connected."; junction swapped in for the backup folder "Not deleted. This is not a recovery backup in your library." (**the file behind the junction survived**). A backup whose comic is being written is not listed at all. Refresh clears row errors. |
| Show in folder errors | Not found and folder unavailable as above; junction gives the generic "Could not open File Explorer. The backup is in the .comic-metadata-backups folder inside the folder above." and opened nothing. |
| While processing is Paused | Show in folder and Delete reach the server and work (spec: allowed while paused). |
| Endpoint fuzz (GET `/api/backups`; POST delete and reveal) | Pass. `Sec-Fetch-Site` same-site and cross-site: 403; POST with Origin `evil.test` or no Origin: 403 and the fixture survived; path, traversal, absolute, 32 zeros, uppercase, trailing newline, number, object, extra key, duplicates, 501 ids, wrong method: refused or not_found, nothing deleted, file outside the library survived; no Explorer window opened by any of them. |

**Real Show in folder (authorised once).** Clicked Show in folder on a fixture row. A new Explorer window titled ".comic-metadata-backups - File Explorer" opened on the fixture folder in my private root; the Shell COM query showed the selection was exactly the intended `.bak`. **Focus:** the foreground window was unchanged at 0.5, 1.3 and 2.6 s and became the new Explorer window by the 5.1 s sample, so it did take the foreground, a few seconds late. I closed only that window (WM_CLOSE to its handle); Sergei's own Explorer window was untouched and the foreground returned to the previous application.

### 3. Cover reader

| Check | Result |
|---|---|
| Stored and deflate covers | Pass. `/api/cover` 200 JPEG; Details shows the picture (480 x 720). |
| bzip2 and LZMA covers | Pass. 400 "No cover could be read from this file."; Details file slot shows that sentence; the ComicVine slot is unaffected. |
| Crafted entries: deflate with a declared size of 1000 bytes but 30 MB inside; honest 30 MB entry; LZMA with a 1.5 GiB dictionary property | Pass. Same sentence, no picture. |
| Memory of the QA engine | Peak commit 36 MB before the requests and 36 MB after (37 MB at the end of the pass). |
| Positive control (separate Python process, plain `archive.read` of the member, as a stand-in for the old path; I did not run the 0.2.3 build) | LZMA 1.5 GiB dictionary on a 1.4 KB file: peak commit 17 to **1556 MB**; 30 MB entry and the lying-size entry: 17 to 75 MB. The new `read_image` path: 17 to 18 or 19 MB. Note the real 0.2.3 `cover()` also checked the declared size up front, so the honest 30 MB case would already have been refused there; the exposure is the LZMA dictionary and the lying size. |

### 4. Link removal and `/api/cover`

- `; ;` fixed. Preview "remaining value: https://example.test/keep; https://other.test/keep"; saved file Web field is that exact value, zip clean, members intact, backup deleted.
- Matrix through the packaged `plan_fields` (15 inputs: link first, middle, last, alone, comma and space and newline separators, trailing separator, two CV links): no double separator left anywhere; a second ComicVine link stays; ambiguous input refused.
- `/api/cover?id=abc`: **400 `{"error":"Choose a comic."}`**. Also `id=`, `id=1&id=2`, `-1`, `1e3`, a space, 20 digits, Arabic-Indic digit, `0x1`, `1.5`, missing id, and `abc` with an index: all the same clean 400. `id=999999` "Comic not found." `id=1&index=abc` gets the picture sentence. Valid requests still 200.

### 5. Quick regression

- Cover strip: Details of a dead-link comic shows "Cover in this file" and "ComicVine cover" ("could not be loaded" under the QA network policy), as in 0.2.3.
- API keys button present with its tooltip; dialog shows ComicVine, Metron, Google Books, Brave only; Save keys works ("Keys saved. Source settings and processing state are unchanged."). Header: API keys, Check for updates, Pause and release GPU. Version v0.2.4.
- Pause: Paused with GPU released in 4.1 s; button reads "Resume processing"; pause persists across launch (by design); Resume goes back to Running.
- Quit leaves zero processes: from Paused (renderer closed 1.0 s) and from Running (5.1 s), 0 QA processes after each; listeners back to Sergei's two plus my stand-in, which I then stopped.

## Findings

### Blocker

None.

### Major

- **M1. The .pyc fix cannot help the update Sergei is stuck on.** `desktop/updates.cjs` requires `./update-capsule.cjs` from the **running** app, so an in-app update from version X runs X's inventory check. Sergei's installed app is 0.2.2 (the failed 0.2.2 to 0.2.3 attempt left a 0.2.3 installer pending); its workers were started without `-B`, so its installed runtime holds `.pyc`, and 0.2.2's check refuses it exactly as the 0.2.3 module did in my control. By code reading plus that control: an in-app update from 0.2.2 (or from 0.2.3, whose workers also run without `-B`) to 0.2.4 will fail with "Update runtime source closure differs" again. 0.2.4 protects hops **from** 0.2.4 onward. Not verified on his real runtime (I do not touch his app). Not a defect in the build under test, so the verdict stays GO. Options for Sergei to choose, via Jane: run the 0.2.4 installer by hand for this one hop (installer behaviour over a running app untested, see Not tested), or clear the `__pycache__` folders in the installed runtime with the app closed and then update in-app. Release notes should say which.

### Minor

- **m1. Lookup Apply on a read-only comic still says "not verified".** Repro: set the read-only attribute on a comic, Details, Find series, Select, Select, Approve. Observed: file untouched (hash and mtime), message "The change was not verified. Check the file and retained recovery backup before trying again." plus block; the kept copy is listed as **"Save not verified"** (not "Not saved; file was not changed") and its delete confirm says "this may be its only good copy". The recovery path got the read-only fix; `/api/apply` did not. Same sentence problem as 0.2.3 m1, on the other save route.
- **m2. Copy differs from the spec in three places.** Block, file missing: shipped "Could not find this backup. Check the path above." Spec section 5: "This recovery backup is not at this location." Row Show in folder: shipped "Backup not found. Use Refresh to update the list." (the delete sentence); the amendment says Show in folder uses the section 5 errors. A refused reveal (junction) shows the generic Explorer line. The tests assert the shipped wording, so it may be deliberate; Judy to confirm or correct the spec.
- **m3. "1 bytes".** A one-byte backup shows "Kept backups · 1 · 1 bytes"; Explorer says "1 byte".
- **m4. Raw Python text on hand-made requests.** `/api/cover?id=25&index=0` (the legacy index form, used by the Archive image picker) answers `Bad CRC-32 for file '001.png'` for the lying-size archive; POST `/api/backups/reveal` with a non-JSON body answers `Expecting value: line 1 column 1 (char 0)`. Loopback only. The picker path in the UI was not exercised for this archive.
- **m5. The sideways-scroll finding from 0.2.3 is unchanged** (P3 below): page 440 px wide in a 305 px viewport at 320, with the Kept panel closed or open (no element inside the panel overflows); Details dialog 426 in 250 at 320 and 645 in 570 at 640, with or without the new block (same numbers as 0.2.3 m4).

## Not tested

- **The real end-to-end install and update.** Impossible on this profile without touching Sergei's app ID, updater folder or state. What was tested is the update-prepare module against a copy, and the capsule's content. Not tested: `installer_launch.py` running from the capsule, the NSIS replacement, relaunch, an installer run over a running app, uninstall, leftovers, first launch of an installed 0.2.4.
- A symbolic-link `.pyc` (no privilege to create one).
- Playwright imported inside the running app (browser search off on purpose; launching a real browser would take focus). Covered only in the copy.
- Explorer: the `failed` row (Explorer cannot address the file), the MAX_PATH fallback to opening the folder (my 460-character fixture paths were listed but never revealed), the junction case with a live Explorer, and a second real launch. Only one launch was authorised.
- "Show in folder stays enabled while a delete confirm is open": by code reading only. Tab and Esc used synthetic key events into the hidden renderer (no physical input); no real screen reader.
- 200% as a device pixel ratio (covered as CSS widths 320, 640, 1280); a real library on `Y:` (long paths, a slow network drive during the list scan).
- The recovery block while Paused (the Kept rows were tested paused; same route).
- Installer payload equality with `win-unpacked` was not re-extracted this round.
- Real GPU/Gemma (stand-in), real providers (seeded cache), unit tests (Ender's), a loaded ComicVine image (QA network policy), a real RAR.

## Pattern alerts

- **P3 (third build).** Long unbreakable paths and wide content force sideways scrolling: dashboard (0.2.1, 0.2.2), Details dialog (0.2.3), and still both in 0.2.4 (m5). The new block and Kept panel do not add to it. Proposed disposition: **fix** in the next maintenance release (one `overflow-wrap:anywhere` rule on the path elements and a check of what makes the page 440 px wide at 320); not a gate. Needs Jane/Sergei's call, since "defer" was proposed twice.
- **P4 (new).** A save that failed on a read-only file reads as "not verified" (0.2.3 m1, fixed on the recovery route, still present on Lookup Apply, m1 here). Proposed disposition: **fix** by giving `/api/apply` the same read-only check; Judy to confirm the wording.
- P1 and P2 from 0.2.2 (sharing violations, install-lifecycle leftovers): not re-examined; dispositions stand. M1 above is the install-lifecycle family again.

## Focus

One line: no focus was taken by the app, helpers or probes (hidden offscreen windows, `windowsHide` on every child, no polling loops, no physical input), except the single authorised Show in folder launch, where the new Explorer window became the foreground window between 2.6 s and 5.1 s after the click and I closed it.

## Process notes

- Harness artefacts, not findings: my first backup watcher gave up when it hit the product still writing the copy (retried, then it held the file); rect rounding made a touching label and path read as 0.1 px overlap (tolerance added); my first LZMA-dictionary fixture patched the wrong bytes and decoded as corrupt (rebuilt, memory control re-run); the rebuilt fixture needed its recorded size and mtime resynced before its problem screen appeared.
- Evidence and scripts: `C:/Users/AnGeLZzZ/AppData/Local/Temp/claude/C--Antigravity-Projects-Studio-Illuminati/84695450-db39-42ca-a8e6-93629fe0ee8f/scratchpad/futaba-024/` (`ev/` JSON and file-list snapshots, `shots/`, the test scripts). Cleanup manifest in `scratchpad/futaba-024-manifests/`.

## Cleanup

- Stopped: the QA app (each launch quit through the product), the feed and model stand-in, my helper processes. No process of mine remains; live listeners are Sergei's two only; his app untouched (main PID 11104 throughout).
- Closed: the one Explorer window I caused. Sergei's Explorer window was left alone.
- Removed: the whole private root `%TEMP%\f24t` (profile, cache, library fixtures and kept backups, locks, state, dummy-key files) with the planner-checked per-path `rm --` / `rmdir --` method (manifest `f24t-root.json`, SHA-256 `2a209702…dd09f`, 127 files and 38 folders, 2,975,949 logical bytes, `complete: true`). The dummy `.env` and two credential blobs were removed first by exact path because the planner refuses those names.
- Removed by exact path (the planner refuses the Playwright package's `references` folder): the seven largest files in each of my five scratch copies of the build runtime and capsules (35 files, about 625 MB). Retained: the smaller files of those copies (about 100 MB, public build files, no keys, no user data) under `scratchpad/futaba-024/{used,used2,capwork-A024-used,capwork-A2,capwork-var5}`, plus `ev/`, `shots/` and scripts as evidence. Sergei or Jane can delete the copies.
