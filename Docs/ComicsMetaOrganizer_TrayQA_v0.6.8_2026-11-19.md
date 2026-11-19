# Comic Metadata 0.6.8 tray QA · 2026-11-19

**Tray-smoke verdict: GO**

GO for the private packaged launch and the 0.6.8 delta at source `da503b3d45798bfb7142c377fe2db5704c509153` (full head; short `da503b3`). No Blocker and no Major. One Minor (finding 1) and five Info items are listed below; none stops the release. Senua's RELEASE CLEAR is on `a4d23f7a78f7e1f70bb910f3b6a4bbe92db3d0ca`. `git diff a4d23f7 da503b3` touches `CHANGELOG.md`, `VERSION`, `package.json`, `package-lock.json` and her review document only; no code file.

Scope was set by the brief: lean verification, test only what changed (CHANGELOG 0.6.8 and the nine-item list), on fixture or scratch state only. Ender's full suite was not re-run. No focus or mouse checks, nothing installed. 21 scenario runs, 260 recorded checks, every one `ok`; every run's owned record shows the Job closed, no forced close, native zero. The runs behind this report were made on 2026-11-19 between 16:13 and 16:30 UTC with the final harness; an earlier build-up pass the same day (11:25 to 12:07 UTC) produced the same results and was replaced so that the harness files are exactly those that produced the evidence. Checks I could not make are listed under "Skipped and not covered".

(Saved by Jane from Futaba's returned text; the subagent Write tool refuses this path.)

## Identity (all compared before the first launch)

| Item | Value |
| --- | --- |
| Source commit (full) | `da503b3d45798bfb7142c377fe2db5704c509153`, equal to the repo `HEAD` of `rc-068` and to the manifest `head` (read in the run) |
| Source manifest | `I:\AI Projects\Temp\cmo-rc068\source-manifest-da503b3.json`, SHA-256 `b3ff67e9cfab4d66c59341f5719ea23597070e88a0ac7e6e01d37a7f4eea262f` |
| Installer | `I:\AI Projects\Worktrees\Comics Meta Organizer\rc-068\dist\Comic-Metadata-Setup-0.6.8.exe`, SHA-256 `9d477604a1c143f642cc448686472ece3e83aa96a2496c9610bf9d1a9e93c2b4` |
| `latest.yml` | SHA-256 `437dab14be3e158b58bbf193d885a1bee23c38cbb7921a30fdc1fc7d413611a1` (the feed stub served exactly these bytes) |
| `ComicMetadata.exe` | SHA-256 `391a0737a36136e74a02d9dd2bd408a6f113aa090740e56cfb36ed71f5c9523a` |
| `resources/app.asar` | SHA-256 `d736d30719ae097a90f636189ed562146d59c363b3b45d06cf86a22c63c7072c` |
| Build record | `I:\AI Projects\Temp\cmo-rc068\build-owned-v0.6.8.json`, SHA-256 `6fda6a9b19e154abe878ab62cce8356184b449074781cb3e05b1162d695daf25` |
| Archiver | the pinned 7za, SHA-256 `b0cfdeaf429f5cc53f85123dd8f5a5feb92c19d31aa34df257edf9a26be05f95` (equals `toolchain-lock.json`), under its own private Job |
| Payload | the installer extracted whole (623 files, tree digest `fe8ea7332f8fd96e0a192800f8dbd8d214f89b5a30976f0c736d5b904927be14`) and, separately, `ComicMetadata.exe` plus `resources\app.asar` only; exe and asar hashes equal in both extractions and equal to the files the running app reported for itself |
| Packaged vs source | all 75 packaged engine files that have a source entry equal the manifest byte for byte (0 differing; the one file without a source entry is the build-generated `update-runtime-manifest.json`); all 16 `desktop/` files in the asar equal `git show da503b3:<path>` (0 differing) |
| Tools used from the source tree | `tools/nested_comicinfo_merge.py` `25306707dcf5848598d91fa00a8c719a23cd01889b87ac9cc20b178ebff1ec70` and `tests/debug_hold.py` `f30542e9a5c5743299bf6b8f5c42191d6f99904df22939bfc6c0b6ab11a84945`, both equal to the manifest. Neither is shipped; the tool ran under the packaged Python (`-B -I`) against the PACKAGED engine (`--engine <extract>/resources/engine`) |

The installer was not executed (it would write Sergei's per-user registry entry and install folder). The 7za-extracted payload stood in, as in 0.6.3 to 0.6.7. Every app run used it in private QA mode: private QA root, policy (prior 0.6.7, next 0.6.8, artifact from `latest.yml`), engine, feed, model and inspector ports; TEMP, LOCALAPPDATA and APPDATA redirected into the scratch folder. Every merge-tool run was given `--live <scratch state>` and `--engine <packaged engine>`; the default live folder was never used.

## 1. Q2: Quit cuts a manual Approve off; the next start finishes or undoes it: pass

Method. A scratch library with a 331,776,051-byte fixture comic (no ComicInfo, deflated random pages). The engine's own `/api/apply` endpoint (the one the dashboard's Approve calls) was posted from the harness; in private QA mode the engine answers provider calls from its cache only, so the cache was seeded with the issue and volume answers. Nothing in the app was stubbed.

- **Undone (the real Quit path).** QA policy `closureWaitSeconds` 2. Approve started; at 2.2 s the temporary archive was growing (27 MB; pending-write record on disk without an `after` signature; backup copy made). Tray Quit was pressed: the app exited 0 after 5.7 s with the Approve cut off (temporary archive 145.8 MB, pending record and backup left, comic byte-identical to the fixture). Next start: `engine.log` reads `Interrupted write recovery: Big Approve 001 (2020).cbz: undone; its backup was deleted.` After it: no `.metadata-tmp`, no pending record, no backup, no backup folder, comic byte-identical, History has no row, Kept backups is empty. Positive control: the same comic then takes a new Approve (200, verified, ComicInfo written, backup removed) and History shows that one write.
- **Recorded (after the rename, before the history row).** The harness held the catalog's write lock so the engine waited at its history insert after the rename (comic already the new 125,868,902-byte archive, no `.metadata-tmp`, pending record with `before` and `after`, backup on disk, 0 history rows), then every process of the app was ended at once (a crash). Next start: `Interrupted write recovery: Big Approve 001 (2020).cbz: recorded; its backup is kept.` After it: no `.metadata-tmp`, no pending record; the written ComicInfo is the Approve's (Series, Number, Summary, Web link); History shows the write (one row, ledger writer `manual`, origin `recovered`); the catalog row is `tagged` with the new size. Kept backups lists the backup with reason `delete_refused`, and the real panel code shows "Saved; backup could not be deleted" (panel summary "Kept backups · 1 · 126 MB").

## 2. The merge tool: apply, kill, `--resume`, `--recover`, `--help`, older engine, torn journal: pass

Fixture: four scratch archives, each with a root ComicInfo and one nested ComicInfo (the second, `Merge B`, 265 MB so a stop can land inside its write); scanned catalog; dry run planned 4 merges. All archives hold only scratch data.

| Case | What was done | Result |
| --- | --- | --- |
| `--resume`, killed mid-write | apply killed (TerminateProcess) while #2's temporary file was growing (21 MB); #1 written, #2 original, pending record and backup left | `--resume` exit 0, `Done: {'written': 4}`; #2's leftovers undone first, then merged as planned; every archive has ONE root ComicInfo, no nested copy, the merged Summary, Writer and Genre, the root's own Series and Number, no nested Year; no backup, temporary file or pending record left; 4 history rows (automatic, `nested-comicinfo-merge`); the removed nested copies saved once per archive in `<out>` (4) and in the state `data/removed-nested-copies.jsonl` (4, kind `merge`) |
| `--resume`, killed after the rename | catalog write lock held so #2 was already the new archive, history not recorded; tool killed | `--resume` exit 0, `written 4`; #2 result `written`, marked `resumed`, its history recorded by the app's recovery first (origin `recovered`) |
| `--recover`, mid-write kill | same kill, then `--recover` | exit 0, `recovered (left as it was) Merge B 002`; #2 as it was, temporary file and backup gone; nothing new started (#3 and #4 byte-identical, 1 result line); a later `--resume` carried on: written 4, 4 history rows, no backup left |
| `--recover`, post-rename kill | same, then `--recover` | exit 0, `written Merge B 002` (checked, saved, backup deleted); #3 and #4 untouched (2 result lines); a later `--resume` finished: written 4 |
| `--help` | read in full | exit 0; carries the recovery steps 1 to 5, the three cases (still the original, already rewritten, does not check out), the torn-line note, Kept backups and the state jsonl (14 phrases checked, 0 missing) |
| Older engine | the 0.6.7 source files (git `9d1ad1a`, VERSION 0.6.7) as `--engine` | refused: exit 1, `This app version cannot recover an interrupted write. Install 0.6.8 or later, then apply.`; no `--out` folder created, archives byte-identical, nothing pending. Positive control: the same plan with the packaged 0.6.8 engine applies (written 4) |
| Torn journal | after a mid-write kill, 48 zero bytes appended to `journal.jsonl` (no newline); no `.torn` file before | `--resume` exit 0, stderr `journal.jsonl ended with a torn line (48 bytes): moved to journal.jsonl.torn.`; the `.torn` file holds exactly the 48 zero bytes; `journal.jsonl` itself parses and ends with a newline; all 4 archives merged. Negative control: a damaged line BEFORE the end makes `--resume` refuse (`line 1 is damaged`), nothing written |

## 3. R2: a stopped or killed merge keeps its record and its backup is listed: pass

- **Stopped on a failed check (a real one, nothing patched).** A reader holding the written archive with `FILE_SHARE_READ` only made the tool's flush of #2 fail while the tool re-read it: result `stopped`, `backup kept: the written archive could not be flushed to disk: [WinError 32] ...`; #1 written, #3 and #4 not started. The scratch `data/removed-nested-copies.jsonl` has #2's line (kind `merge`, the whole nested copy byte for byte in `xml_base64`, what the root did not take: Year, "nested date never copied"). The backup is on disk (one copy equal to the original). The app started on that state lists it in Kept backups as `save_not_verified`, and the real panel code shows "Save not verified". The app's start had nothing to recover.
- **Killed mid-run, app started first (not the tool).** Killed after the rename: the line for #2 is already in the state jsonl (written before the rename); the app's recovery records the write (`recorded; its backup is kept`) and Kept backups lists the backup as `delete_refused` ("Saved; backup could not be deleted"), not "Save not verified" (finding 2). Killed mid-write: no line for #2 yet (the write had not reached its rename); the app undoes it, backup deleted, Kept backups empty. In both, `--resume` run afterwards finished the whole run (written 4, one history row per archive, no backup left).

## 4. R1: a read-only comic through Approve: pass

A read-only fixture comic (mode 444) through `/api/apply`: HTTP 400, `verified: false`, "The change was not verified. Check the file and retained recovery backup before trying again.", a retained backup named. The comic is unchanged (SHA-256 equal) and still read-only; no `.metadata-tmp`, no pending record; one backup, equal to the original. Kept backups lists it as `save_not_verified`; the real panel shows "Save not verified". History has no row. Positive control: a writable comic through the same Approve is verified and its backup removed.

## 5. q1: a read-only claim lock plus a shell-written leftover record: pass

Genuine claim files: the app was started and every process ended at once, which left the engine's own `engine-<owner>-<pid>-<id>.lock` and `.json` claims (3 of each). A shell-written leftover record (`members: null`, 1 day old, source `shell`) was written for that engine and all 3 claim locks were made read-only (nobody holds them).

- **Next start:** normal, 1.6 s, to the dashboard; the "previous session still closing" screen was never shown in any sample; the record is gone. `engine.log`: `... no process list, so its engine claims are checked: 0 held.` then `... nothing of that session is left; record removed.`
- **Positive control** (same files, but a live process really holds a claim lock, which is also read-only): the start shows `The previous session is still closing.` (failure `PREVIOUS_CLOSING`, detail "Part of the local service has not ended yet. Try again, or restart your PC to clear it.", buttons Try again / Open log folder / Quit), record kept. Tray Quit from that screen exits 0 in 0.2 s; the next start shows the same screen again; with the holder ended, Try again starts normally (1.3 s) and the record is removed.
- **Edge probe (not in the brief; finding 1):** the same read-only locks with their `.json` records missing: the start fails with `LIBRARY_BUSY` ("Could not start the local service").

## 6. q2: a nested-only comic with store dates: pass

Fixture: a nested-only comic whose nested ComicInfo has store dates 2019-12-31, `PageCount`, a year-like `Volume` 2019 and a `writer` letter-case twin, matched by the synthetic GCD index (issue 15), plus an unmatched control with the same kind of copy.

- **Read side (control comic):** status `embedded`; the catalog metadata has no Year, Month, Day, PageCount, Volume or `writer`; it does have Series, Number, Summary and Writer read from the nested copy. The archive is byte-identical afterwards.
- **Automatic write (matched comic):** `tagged`; ONE root ComicInfo, no nested copy; the root holds the COVER date (Year 2020, Month 1), not the store date; no Day, PageCount, Volume or `writer`; the nested Summary and Writer are kept.
- **`data/removed-nested-copies.jsonl` exists:** 3 lines (013, 014, 015, kind `nested-only`); 015's line holds the whole nested copy byte for byte and `left_out`: Year, Month, Day "nested date never copied", PageCount "PageCount never copied", Volume "Volume is a year", `writer` "same tag in another letter case".

## 7. Q3: a late exit of an old broker no longer stops the new engine: pass

My 0.6.7 scenario set had no frozen-broker Quit + Retry run to reuse, and a Quit ends the app, so there is no Retry after it. I ran the path Senua describes (the failed start, then Retry): QA policy `closureWaitSeconds` 12. The first broker was frozen (`tests/debug_hold.py --mode freeze`) 0.24 s after it was spawned and its engine process ended while the shell was still starting it. The start failed after 33 s (`START_UNRESPONSIVE`, unresponsive-start wait plus the forced stop that gives up). Retry (the failed screen's control, a DOM click) started a NEW broker beside the frozen one; it was ready in 14.3 s (HTTP 200, owned, version 0.6.8). The old broker was then thawed and exited 0.3 s later. For 25 s afterwards (sampled every second): still 2 brokers (no restart), the new broker never exited, the shell service stayed ready, `/api/shell/status` answered 200 every time. Positive control: ending the CURRENT broker from outside still makes the shell restart the engine (a third broker, ready, in 1.9 s). Tray Quit then exited 0.

## 8. Judy's Quit copy, rev 3 (checks C7 1 to 11): pass, one part skipped

Samples of the live dialog every 40 ms from inside the app (no OS key, mouse or focus); times from the Closing stage's start.

| Check | Result |
| --- | --- |
| **1. Default wait, frozen broker, tray Quit** | Closing `Gemma released from GPU. Closing…` shows with the detail empty; the detail becomes exactly `This can take up to 60 seconds.` 5.04 s after Closing began; the ending state `Stopping the local service…` / `This can take up to 30 seconds.` 30.02 s after Closing began; the 10 s sentence 9.99 s after that |
| **2. Stated-remaining test** | exit minus the time each text first appeared: `up to 60` 56.1 s (limit 62), `up to 30` 31.1 s (limit 32), the late ending text 21.1 s (limit 32). Exit 61.15 s after Closing began, 64.98 s after the click, with the broker still frozen. Same pass on the Quit now path (31.14 s after the ending began, limit 33) |
| **3. Policy 12** | Closing detail `This can take up to 24 seconds.` at 5.00 s, ending `This can take up to 12 seconds.` at 12.00 s, late sentence 9.99 s later; exit 25.1 s after Closing began (limit 27 s). No literal 30 or 60 as a stated time in the packaged `desktop/stopping.js` or `desktop/main.cjs` (positive control: the pattern matches `This can take up to 30 seconds.`) |
| **4. Healthy quit, five runs** | 5 tray Quits from the ready dashboard, exit 0 (6.5 to 6.9 s each): the Closing detail is empty in every sample, no number anywhere, no ending state. Positive control: check 1 shows the sentence |
| **5. Tooltips and suppressed lines** | live Closing: both buttons shown and disabled; titles exactly `Cannot cancel: the app is already closing.` and `The app is already closing and exits by itself.`; no `Waiting for`, no `Quit now exits without waiting`; the detail is a live region. DOM feed (elapsed 70000, `waiting_for: [metadata]`, late set): the detail is exactly `This can take up to 60 seconds.`. Positive control: the same feed on the 0.6.7 dialog shows `Waiting for: comic processing Quit now exits without waiting. An interrupted write keeps its recovery backup.` and the old tooltips |
| **6. Quit now during Pausing** | Quit now clicked (a DOM click, enabled at that moment) in the Pausing stage: no Closing stage; the ending state reads `up to 30 seconds`; the process ended 31.14 s after the ending began, exit 0 |
| **7. Ending-state regression** | action row hidden; Escape, the dialog's `close()` and a second File > Exit changed nothing (live probe); the 10 s sentence appears once; in the DOM feed Escape sends no action and a later Closing state changes nothing |
| **8. Install mode (DOM feed only)** | Closing reads `Gemma released from GPU. The app restarts to install.`, no time sentence even with the late flag, `Cancel install` with its tooltip `Stop the install. Processing resumes unless you had paused it.`, identical to the 0.6.7 page. A real install was not run |
| **9. Rects at 440 px** | measured offscreen, live dialog and DOM feed: before the sentence the detail is 0 px high, after it 21 px; the buttons (43 px high) move from y 132 to y 167; detail and buttons do not overlap, both buttons are inside the window, nothing scrolls. **The visible run is skipped** (needs a visible window and Sergei's permission) |
| **10. Number 1** | `waitSeconds: 1` in the ending state reads `This can take up to 1 second.`; with 1 in Closing it reads `up to 2 seconds.` |
| **11. Strings vs spec** | rows 1 to 5 equal the Rev 3 section character for character (each found verbatim in the spec file) |

Also unchanged: the Pausing stage (its text, both buttons enabled, the 0.6.7 tooltips) and the dialog's first appearance 1.6 s after the click.

## 9. Core smoke and every top-level screen: pass

- **Launch and ordinary pass.** The packaged app reported 0.6.8, packaged, one invisible, unfocused, offscreen window, a private authenticated engine (HTTP 200, owned), 28 guards with 0 violations and 0 other spawns. 12 plain fixtures, 3 nested-only fixtures and the cb7 (converted to cbz by the bundled 7-Zip) were processed in 8.2 s (15 `tagged`, 3 `embedded`, 2 `missing`); a tagged comic carries ComicInfo with Series "Futaba QA Fixture" and Number 1. Feed stub 0 requests in the promotion run; model stub 2; no provider call.
- **Tray.** The PNGs the running app read from its archive equal the source manifest for all 8 files; four icon states distinct at both sizes. Real Pause and Resume callbacks: processing, paused (tooltips "Pausing. Finishing the current operation." then "Paused. Gemma released from GPU."), processing.
- **Close button** on the setup screen, the dashboard and the failed screen kept the process alive and the window not destroyed (tray-resident).
- **Quit from every top-level screen** exited 0 with nothing left: dashboard 6.1 s, setup screen 1.0 s, startup screen 0.55 s, the failed screen (made by four outside broker ends; Try again brought a new broker and the dashboard back first), the "previous session still closing" screen (0.2 s, section 5).
- **Live app.** Before the first run: four `ComicMetadata.exe` processes (824, 71200, 71924, 109992) and the 8765 listener (PID 16320), as in 0.6.7. After a usage-limit break and at the end, none were running (finding 6). QA mode refuses 8765 and 11434. `%LOCALAPPDATA%\ComicsMeta` and `Y:\Comix` were not touched.

## 10. The promotion-schema evidence (for the release script)

`tray-evidence-v0.6.8-promotion.json`, `tray-owned-v0.6.8-promotion.json`, `package-binding-v0.6.8-promotion.json`, `extraction-owned-v0.6.8-promotion.json` and `asar-evidence-v0.6.8-promotion.txt` are written directly by the harness from the final promotion smoke (launch, ready dashboard, the real Pause and Resume callbacks, the real Quit callback). Same fields as the 0.6.7 files: I compared the leaf-field sets key by key: 74 (smoke), 35 (owned) and 17 (binding) fields, identical sets, none added or removed.

Every value was read in that run: the tray sequence is processing, processing, processing, paused, processing; `processing`, `paused` and `resumed` are each `exact` (32 by 32, 4096 and 1024 bytes); `markResources` 8 of 8, 4 and 4 distinct. `spec.sourceHead`, `spec.manifest`, `spec.installer`, `spec.feed`, `spec.exe` and `spec.asar` equal the Identity table. `quitRequested` is `actual tray Quit requested`; close code 0, nothing remaining, port refused, no claim; 2 model requests, 0 feed requests, 0 violations, 0 other spawns.

I replayed lines 57 to 64 of `create-local-promotion.mjs` (unchanged since 0.6.7; `git diff 9d1ad1a da503b3` touches no script) over these files, with the report-naming check of line 64 against the facts named here. They pass, and 12 negative controls are each rejected. I did not run the script itself (it needs the publication config).

**Pin these five** (SHA-256):

| File | SHA-256 |
| --- | --- |
| `tray-evidence-v0.6.8-promotion.json` (smoke evidence) | `f258483618a5c3f94b9189995d8ea324d0253d55377680bb0c21213de75ae98d` |
| `tray-owned-v0.6.8-promotion.json` (its Job closure) | `0916654b51d40598a95af559b055c83dab226a3276299585d5c8eab2117a2e45` |
| `package-binding-v0.6.8-promotion.json` | `ef45647fff814761c218dc487ef30a00e12346a84a26a62d5a0e482d861a1cc0` |
| `extraction-owned-v0.6.8-promotion.json` | `312c73486aea9f8bfbec8d7fc53ed507bb0e79fa51f6bcbe4501bb19776c8af3` |
| `asar-evidence-v0.6.8-promotion.txt` | `0e50d1f60278bcefe1e3d2e2618e9b0d38b224798b80386ffeebe28e5ea4f4b5` |

## Findings

1. **Minor, open, for Ender; defer is proposed (not on the core flow, low reachability).** `library_lock._overlapping_owner` (unchanged in 0.6.8) still treats an unopenable claim lock whose `.json` record is missing as a live foreign claim. With read-only claim locks and no records, the start fails with `LIBRARY_BUSY` ("Another Comics Meta copy is using this library (state folder: unknown)", screen "Could not start the local service."), and Try again does not help. The q1 fix (`engine_host.held_claims`) covers the broker's previous-session check and the realistic case where the claim records exist (section 5), but not this sibling path. The CHANGELOG line "An unreadable lock file no longer blocks startup" is true for the former, not for this variant. I only reached it by deleting the records on purpose; a normal crash leaves both files. Evidence: `scenario-q1-claims-v0.6.8.json`, `edgeProbe`.
2. **Info, for Jane (wording of item 3).** A merge killed mid-run does have its line in the state `data/removed-nested-copies.jsonl` when it was killed after the rename, but its backup is listed as "Saved; backup could not be deleted" (the app's recovery verified the write as planned), not "Save not verified". "Save not verified" is what a stopped merge gets (section 3). Killed before the rename: no line yet and nothing listed (the write is undone and its backup deleted). This matches the code and `--help`; I am flagging only that it is not the wording of the brief.
3. **Info, UX-shaped, for Judy.** After a recovered write the Kept backups reason reads "Saved; backup could not be deleted", though the deletion was never tried (the original's hash is not known there; by design per the code comment). A user may read it as a failed delete.
4. **Info, procedure.** The Q3 run is failed start plus Retry with a frozen broker (the path Senua describes: "twice on the failed-start-then-Retry path"), not a Quit followed by Retry (section 7). The "recorded" Q2 stop uses a harness-held catalog lock and ends every process (a crash analog); the "undone" stop is the real Quit path.
5. **Info.** The ending state's process end is 31.1 s after `up to 30 seconds` appears (both Quit and Quit now paths): inside Judy's allowance of N + 2 s and the shell's backstop (wait + 1 s + 0.5 s). The waits are unchanged by design.
6. **Info, for Jane to confirm with Sergei.** Sergei's live app (four `ComicMetadata.exe`, 8765 listener) was running before my first run and was not running when I next looked (after the usage-limit break) or at the end. Nothing I started could have ended it: every kill was by exact PID of my own scratch tree (recorded in the result files), my Jobs hold only my processes, and QA mode refuses 8765. Listing in `live-app-untouched-v0.6.8.txt`.

Pattern alerts: 1, carried. Stale `engine-*.json` claim files after an engine ended from outside (0.6.6 finding 4, 0.6.7 finding 5). In 0.6.8 every normal Quit left no claim file (promotion, core, the five healthy quits); stale files appeared only after the crashes I caused on purpose. Proposed disposition: **defer** (Info, harmless, no process outlives the app, claims are judged by their lock). Jane to confirm or change.

## Skipped and not covered

- **Skipped, needs Sergei's permission (focus or a visible window):** the visible run of C7 9 (the dialog with the added line shown on screen), rev 2 R5 checks 9 and 19 and every check that needs the real window shown or the OS focus, a screen reader. QA mode keeps every window offscreen.
- **Not run, unchanged code (run in 0.6.7):** the previous-session screens P1/P2/P3 in full (only the held-lock screen of section 5 was driven), the engine ended from outside with Retry, Quit during Retry, the start after a frozen-broker Quit, the 12-run absence check of the old banner states.
- **Not run:** a real install-mode Quit (C7 8 is a DOM feed), running the installer and an actual update, Windows sign-out and shutdown, live provider answers, GPU release, the Ctrl+Q chord itself (File > Exit, the same callback, was used), the full test suite (Ender's).
- Nothing was written outside `I:/AI Projects` by the QA processes. The personal-folder listing was not taken (the 2026-11-15 approved-root ruling supersedes it, as in 0.6.6 and 0.6.7). One cleanup command of mine (a recursive delete of old scratch folders) was refused by the recursive-delete guard and did not run; the cleanup was then done with the sweep's approved mode.
- Everything I started has exited (checked by command line and path against the live app's processes and the 8765 listener, at the start of this session and again after the last run). My scratch (extracted payload, private QA roots with their large fixture archives, run scratch) was removed with the sweep's approved mode in two passes: 2,048 files, 3.98 GB, then 2,446 files, 3.49 GB (free space on I: +3.98 GB and +3.50 GB). Only the evidence folder below remains.

## Evidence

Folder: `I:/AI Projects/Temp/futaba-068/evidence/` (outside the tool's repo by instruction; copy it into the tool's `scratch/` or the promotion config before anything sweeps it). The `harness/` folder is the 0.6.8 revision of the 0.6.7 harness, with the 0.6.8 scenarios and its README; the digest of its sorted `<name> <sha256>` lines (25 files) is `a9d518cb096808be8832afb99669516ec54a6363e5efc19f3202acc2f26e8b65`. The harness files are exactly those that produced the evidence (all 21 scenarios were re-run with the final harness; the console log of that pass is `run-all-console-v0.6.8.txt`).

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `asar-evidence-v0.6.8-promotion.txt` | 1171 | `0e50d1f60278bcefe1e3d2e2618e9b0d38b224798b80386ffeebe28e5ea4f4b5` |
| `asar-evidence-v0.6.8.txt` | 201 | `027af417be0ad20377e8933392ec289a156bc9b43c7a4d713c19a39b79c490e0` |
| `engine-manifest-evidence-v0.6.8.json` | 326 | `2c3cb26d0e12882d8c417087f62880f0a26e3b12554bd84e02386c986d359869` |
| `extraction-owned-full-v0.6.8.json` | 2040 | `9bc762e7bbf51aab890122788e44bf4ee9a8623c06cf8b16e3384a6b95ad0ccf` |
| `extraction-owned-v0.6.8-promotion.json` | 2724 | `312c73486aea9f8bfbec8d7fc53ed507bb0e79fa51f6bcbe4501bb19776c8af3` |
| `harness/asar-check.cjs` | 1386 | `e551e373690438684f8946cdd544bbe5d2534d461816a1a8f5edac383531d214` |
| `harness/assemble-promotion.cjs` | 4627 | `b4c2a55c9d5fbb733d155fd1a3869e45a8082fd27c1851a892ebf3a867b3ce2e` |
| `harness/c7_068.mjs` | 26585 | `7bb1b8cd404d113cf9b536be28df7948bd5fcd5967b98346e9ecd86bb3e6a541` |
| `harness/collect-evidence.cjs` | 1672 | `e6a07a835ee21e43f565e6e1bdc90024a9cce7c15aa7f130c865f2dce6c0711e` |
| `harness/engine-vs-manifest.cjs` | 1650 | `2a03a7a31da98c30d4d7f12a9ae7538ae348f0a9ba1d6b9df7793176043e7729` |
| `harness/extract-full-cfg.json` | 446 | `e00c9fea0dc9e9fcaad9836adee54f89fc2dca3cd3c8099b48a54db1350db721` |
| `harness/extract-two-cfg.json` | 499 | `ab42057f1a7005e7dbb254c212d808475513583bc81abc5e0a524aa1c3713caa` |
| `harness/fixture_approve.py` | 3007 | `be6ed30e95febf73ba8b983d88e16ba92f7daa603aa74dffd8de96f9347e118e` |
| `harness/fixture_merge.py` | 2748 | `e144718b440ac636abcee523c77a992d49edeafc8ec18028afdf068b4c8914ee` |
| `harness/fixture.py` | 7059 | `d877212e227cd764563041ab565db9d3269e7b13273276e117e33f2560fb9ef6` |
| `harness/holdclaim.py` | 648 | `b0d6891972634488f71946c31c921d159fb7fe60cb037566bd36748846152eff` |
| `harness/holdshare.py` | 1022 | `2053b3f6d05f5293cf0f10aea6ea75a58e047c0315578f439a44b9dc7979b051` |
| `harness/lib.mjs` | 14087 | `fae8fa8a77d8190b780f8635179c45e6a71ccd6742e6aa8514bad2e51dffc37b` |
| `harness/merge068.mjs` | 32895 | `4c781890417e4f19b2d947a2868ffaecfd81cbaae93992c2529328bdce519a96` |
| `harness/more068.mjs` | 18272 | `7c45bbc98a5720e5f3bc16ef22efe2e34f40cfc0cf8f878f54e4fbbacc97c324` |
| `harness/nested_probe.py` | 2433 | `15ddeafa19a6bf4fe6b0a7daee4c9918d19662df37997a6517eb4897304be61e` |
| `harness/new068.mjs` | 24934 | `d8a240d31898f0406bce0e436bec5c8f7abe221e3cc344df5ae9ca83454081d7` |
| `harness/observer.cjs` | 18861 | `138af86201edd7379d716bc6aa556de503bba68877bfc24ac009685b64e90d30` |
| `harness/owned-run.mjs` | 1835 | `8c255477e3a0dfe64b71041fde34f46b782d89ed1d58117c9b2444e3c85c721c` |
| `harness/pstree.py` | 1917 | `6b61d69911116f7f68f5f2ebb5c93d1fe2c5ce9344b337ca67559681dfbe7034` |
| `harness/README-harness.txt` | 6481 | `b8a1d0dc87bf3878387eba8ff2bed8b14512bdef946bff310a65729be181b122` |
| `harness/run-all.sh` | 1367 | `3f9590d90a0baa9739db08eba331b5b7365f82861e909e3968d15de780b295df` |
| `harness/run-scenario.sh` | 1098 | `3c190dd642674f66c635696d54d3332b5d4dcec82fd01d4f996055885ece3e0e` |
| `harness/scenarios.mjs` | 79078 | `b68117743567701706555562b451b91c6637fa346f791b7e9e66c18ac52aca2d` |
| `harness/validate-promotion.mjs` | 6655 | `6b9b932fa2a63feef90986b47a9c277ca6d329b53cd623efc800cc156a821e07` |
| `live-app-untouched-v0.6.8.txt` | 743 | `19d6423417aa1a461d88791af523337ccc57e8e2de0025576549abaec30ff775` |
| `package-binding-v0.6.8-promotion.json` | 1510 | `ef45647fff814761c218dc487ef30a00e12346a84a26a62d5a0e482d861a1cc0` |
| `run-all-console-v0.6.8.txt` | 8082 | `8bd7e24085060540f10e31b4d8fbaee11b88d955dc8c7f3f7290ed02759d14ee` |
| `scenario-c7-dom-feed-v0.6.8.json` | 16191 | `f1158568b802a0ca9c03002e5938d26624c117352423219b5286d4e21abcb75c` |
| `scenario-c7-healthy-quits-v0.6.8.json` | 17111 | `6af0b57315ac9b19f1177878dff6da1df144405c2c839407b95ffa062e485076` |
| `scenario-c7-quit-now-v0.6.8.json` | 13232 | `24e47f2986e90392741cc9a5b2866dc9aa33fe2a1508cb824ececc01072187fb` |
| `scenario-core-nested-q2-v0.6.8.json` | 64742 | `718ec3871b05a24a211d241bfc1178784296bfa54e188db12a1f875f7a8cc3d1` |
| `scenario-failed-screen-v0.6.8.json` | 10206 | `e3dec558909d44f9bee4bcb2434969e29bc411011f2b0a68237b0d3d0409ff81` |
| `scenario-merge-help-older-engine-v0.6.8.json` | 2425 | `d3f59b04cf93cf2c5171db7286c04a643560d8e79f01cb3c19441ea3afb8bfc2` |
| `scenario-merge-killed-app-v0.6.8.json` | 21424 | `f875129fb26507fd7a8ac92b5a5fd0ab8302fc3f6bc26fb8eb580c10fcc17730` |
| `scenario-merge-recover-v0.6.8.json` | 11210 | `f4e6982e4395fab213c66804f18a39278888945fa2ec950504f44ca2f781dd73` |
| `scenario-merge-resume-v0.6.8.json` | 16509 | `cfa3f7bd3b186aaca2e315619676f7fa4bd7f0cd825d697e9b60d423ecb72b58` |
| `scenario-merge-stopped-r2-v0.6.8.json` | 15161 | `6b457c0d52b91e06389c5b500e6bc42165b2271010515458cf6f7af29cf49a0c` |
| `scenario-merge-torn-v0.6.8.json` | 6690 | `fcb33e4c5792783273ce53d8c9024163db504ed8b5749c9499b4bcc96326abff` |
| `scenario-owned-c7-dom-feed-v0.6.8.json` | 5867 | `fcf0331557b061e576912260938ec2e526be8360f9fc7abe325e0bb772c29a4a` |
| `scenario-owned-c7-healthy-quits-v0.6.8.json` | 5847 | `adb1ea00dfdca408c51efd02243ebd324e33a3971958de3dc828d3597164fac7` |
| `scenario-owned-c7-quit-now-v0.6.8.json` | 2580 | `72bd3bac7767086399f58c065d89a7ed8a18a4e2c0c1a75d122148cf1a716537` |
| `scenario-owned-core-nested-q2-v0.6.8.json` | 10362 | `1784beab28bc46d17ae2101b28dd3186dbe15e018f10b600ef20ac0ab9227d2a` |
| `scenario-owned-failed-screen-v0.6.8.json` | 3577 | `2c929ea5698b6a8c2f7702d52171d1c70b63a9fbec2bb1a5fef3b3197134190a` |
| `scenario-owned-merge-help-older-engine-v0.6.8.json` | 2500 | `fe9d0042f01a9d82d5f104b8f0ad87144a6a2fbb0c5e8e80d32f074813138a5e` |
| `scenario-owned-merge-killed-app-v0.6.8.json` | 5211 | `243fe0862eabefd9b3ba5a8e86d8b25478fc59642acb69eba919cd1473ed3f6a` |
| `scenario-owned-merge-recover-v0.6.8.json` | 4519 | `3377aa719f3843067caa4e0e799ecc658697102200146fc063fa276ce8cb0add` |
| `scenario-owned-merge-resume-v0.6.8.json` | 6944 | `3e7cacdfb51ac05046d0dc229fd09517c96310eacc6e3a2bed47bb3d9a411be0` |
| `scenario-owned-merge-stopped-r2-v0.6.8.json` | 4275 | `2801102dce584a39608b449670ea1b5743f5969ced13b675010c7259307ae6a0` |
| `scenario-owned-merge-torn-v0.6.8.json` | 3992 | `b711f5c5d41f6088c2466d13a7a1b4fb377e7828637e73025e5da28ac8b50dd7` |
| `scenario-owned-promotion-smoke-v0.6.8.json` | 2819 | `0916654b51d40598a95af559b055c83dab226a3276299585d5c8eab2117a2e45` |
| `scenario-owned-q1-claims-v0.6.8.json` | 7436 | `02e351251393068ca9dca28499e8d21272f3a11a9970597ce1e2f6d92ee70e6f` |
| `scenario-owned-q2-after-rename-v0.6.8.json` | 5081 | `06204c7869d0d8e8ba8fb8a50d71cf819d615e725a518098e3fa1271c9de9d66` |
| `scenario-owned-q2-quit-cut-v0.6.8.json` | 4643 | `9a1b636a40942c7eb6a705515a99721504adb5d3d605001c0a83317b0f2e90e0` |
| `scenario-owned-q3-late-exit-v0.6.8.json` | 3841 | `56369e6a6295f7005681f566f2e49ce4e4110c9d18d16fe42c8b64378e05b410` |
| `scenario-owned-quit-frozen-closurewait-12-v0.6.8.json` | 8652 | `9eddbdd6ce8f87f6544b2507309e07bbebeb6be325de6ea8871152283b95e290` |
| `scenario-owned-quit-frozen-default-wait-v0.6.8.json` | 8688 | `0a30a3f57407cf69fe111f871a06da173b66bf77064391c8c986da66bb061494` |
| `scenario-owned-r1-readonly-v0.6.8.json` | 3657 | `29f4aeb00719cda2372c06b0fde3c70988311f0ad3cd12175eaa5fa035695df2` |
| `scenario-owned-setup-quit-v0.6.8.json` | 2500 | `10c46878d69b37bc636f1b70f01e23c77253fc941e090700cd66a07394fcd16f` |
| `scenario-owned-startup-quit-v0.6.8.json` | 1989 | `96692a12b45ae1e2eb3980e2ba2bc07dd8de0746d079544767c14ac4b016b762` |
| `scenario-promotion-smoke-v0.6.8.json` | 8062 | `298160bc1e8b361a71d6d478e6367a21ad4f62d7b83008ef6e9e894bec6d3b6c` |
| `scenario-q1-claims-v0.6.8.json` | 21891 | `a66987fff948705d52c4d0c1d39fb09d80a824c0c89c301e043f39a0c98351b3` |
| `scenario-q2-after-rename-v0.6.8.json` | 16737 | `fccee897c17151344db8299e41714aeeb06c5acc8370e6ccc69545d8b8494c29` |
| `scenario-q2-quit-cut-v0.6.8.json` | 14993 | `91c8e9f756c1bfc10bfad558394ce20487b4456b7ef65beeeaa54785cc04453f` |
| `scenario-q3-late-exit-v0.6.8.json` | 10025 | `425d723154d47f5464207ddfeec86d30ee579b83e5e38e8b8da6d22c091cc894` |
| `scenario-quit-frozen-closurewait-12-v0.6.8.json` | 32306 | `75c482b1627f8a902de7b35a1d872f9f4d1b2deb6852c9807dbc7b783268bb5b` |
| `scenario-quit-frozen-default-wait-v0.6.8.json` | 32362 | `c710c7fcf38859890fc9491a769e34c39e961976628f9d5a3604140caddb885f` |
| `scenario-r1-readonly-v0.6.8.json` | 14157 | `6ef3da6b506b4ca88f3c1667aa508ff2e0e624a2b12b7c66a1659aff3ff184d8` |
| `scenario-setup-quit-v0.6.8.json` | 7371 | `7fa1109bf88d1604974e3a78fb0b4755494bc616b2cdd5a58f756ba612d3f5e8` |
| `scenario-startup-quit-v0.6.8.json` | 6610 | `9676c6551d4a0c523b4bc045f45aca931eb9f9446965efe93d6ca0ee339e8cd4` |
| `tray-evidence-v0.6.8-promotion.json` | 3335 | `f258483618a5c3f94b9189995d8ea324d0253d55377680bb0c21213de75ae98d` |
| `tray-owned-v0.6.8-promotion.json` | 2819 | `0916654b51d40598a95af559b055c83dab226a3276299585d5c8eab2117a2e45` |
| `tray-png-source-hashes-v0.6.8.txt` | 798 | `4386ef3edc163d4fe66dede85e8cef6699099dc42404721da0433b34f342f5c8` |
