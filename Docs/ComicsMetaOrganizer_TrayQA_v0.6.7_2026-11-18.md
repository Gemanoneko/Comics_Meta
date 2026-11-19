# Comic Metadata 0.6.7 tray QA · 2026-11-18

**Tray-smoke verdict: GO**

GO for the private packaged launch and the 0.6.7 delta at source `9d1ad1af7c3e3f6c0db86b052d8372c8f1c5ad1b` (full head; short `9d1ad1a`). No Blocker and no Major. One Minor and five Info findings are listed below; none stops the release. Senua's RELEASE CLEAR is on `880f305`; the only change after it is Sully's version, lockfile and changelog bump (checked: `git diff 880f305 9d1ad1a` touches `CHANGELOG.md`, `VERSION`, `package.json` and `package-lock.json` only, no code file).

Scope was set by the brief: lean verification, test only what changed (CHANGELOG 0.6.7 and the five-item list), Ender's full suite not re-run, no focus or mouse checks, nothing installed. 155 recorded checks across 12 scenario runs, every one `ok`; every run's owned record shows the Job closed, no forced close, native zero. Checks I could not make are listed under "Skipped and not covered", with the reason. Runs were made 2026-11-19 between 06:20 and 06:48 UTC (the harness and extractions were done on 2026-11-18, before a usage-limit break).

(Saved by Jane from Futaba's returned text; the subagent Write tool refused the path.)

## Identity (all compared before the first launch)

| Item | Value |
| --- | --- |
| Source commit (full) | `9d1ad1af7c3e3f6c0db86b052d8372c8f1c5ad1b`, equal to the repo `HEAD` of `rc-067` and to the manifest `head` (read in the run) |
| Source manifest | `I:\AI Projects\Temp\cmo-rc067\source-manifest-9d1ad1a.json`, SHA-256 `f27f3e9ed6045641da158af9db61e37779fda3f0618b2f25dad1ddb72c4fd3cd` |
| Installer | `I:\AI Projects\Worktrees\Comics Meta Organizer\rc-067\dist\Comic-Metadata-Setup-0.6.7.exe`, SHA-256 `ff3d740a5366892c1a4e940dc7b132a0220c2c8d42481135fef9de6ea842984b` (equals the build receipt) |
| `latest.yml` | SHA-256 `0ea617cd773a71d6358edfe26a9cbd9dd35d947c7c0e9503c054c3492deb84ac` (the feed stub served exactly these bytes) |
| `ComicMetadata.exe` | SHA-256 `727bfd63f4847c3cb85661403286ad3fbe74e53bc8363bf32edcf613eff74561` |
| `resources/app.asar` | SHA-256 `782535e5a122962631ddf32a859c35bc912a18f77a45c2675bfabf6a4dad7040` |
| Build record | `I:\AI Projects\Temp\cmo-rc067\build-owned-v0.6.7.json`, SHA-256 `7141e542842769b43afba19ea26cd9990994f5642fc2c30d8e8ca618c040c511` |
| Archiver | the pinned 7za, SHA-256 `b0cfdeaf429f5cc53f85123dd8f5a5feb92c19d31aa34df257edf9a26be05f95` (equals `toolchain-lock.json`), under its own private Job |
| Payload | the installer extracted whole (623 files, tree digest `442831d40848d41e2ae4d2979f1f0ac4ee2e082de622fc6e940ca1b734642299`) and, separately, `ComicMetadata.exe` plus `resources\app.asar` only; exe and asar hashes equal in both extractions and equal to the files the running app reported for itself (`process.execPath`, `app.asar`) |
| Packaged vs source | all 75 packaged engine files that have a source entry equal the manifest byte for byte (0 differing; the one file without a source entry is the build-generated `update-runtime-manifest.json`); all 16 `desktop/` files in the asar equal `git show 9d1ad1a:<path>` (0 differing) |

The installer was not executed (it would write Sergei's per-user registry entry and install folder). The 7za-extracted payload stood in, as in 0.6.3 to 0.6.6. Every run used it, in private QA mode: private QA root, policy (prior 0.6.6, next 0.6.7, artifact from `latest.yml`), engine, feed, model and inspector ports; TEMP, LOCALAPPDATA and APPDATA redirected into the scratch folder.

## 1. Quit always closes: pass

**Normal Quit.** Tray Quit from the ready dashboard exited 0 in the promotion smoke (6.8 s, includes the pause and GPU stages) and in the core run (5.7 s); from the setup screen 1.1 s; from the startup screen 0.7 s; after the broker was ended from outside 0.9 s. After each: engine port refused, no recorded PID alive at 12 s, no claim left (except the stale claim files in finding 5).

**Frozen broker** (`tests/debug_hold.py --pid <broker python.exe> --mode freeze`). The broker `python.exe` was held. The engine's HTTP server is a child process of the broker (PIDs recorded), so `/api/shell/status` keeps answering while the broker is frozen. That is why the pause and GPU stages still run first.

| Run | Click to dialog | Dialog states, ms after the click | Exit |
| --- | --- | --- | --- |
| Default wait, hold 100 s, tray Quit | 1.6 s (first sample 1.57 s), pausing text | 1570 `Pausing — finishing the current operation. Progress is saved.` · 3419 `Gemma released from GPU. Closing…` (both buttons disabled) · 33449 `Stopping the local service…` / `This can take up to 30 seconds.`, action row hidden · 43458 detail gains ` An interrupted write keeps its recovery backup.` (10.0 s into the ending state) | exit code 0 at 64.6 s after the click, 31.2 s after the ending state began, with the broker still frozen; `leftover-<owner>.json` left in the QA locks folder |
| `closureWaitSeconds: 12` in the QA policy, hold 64 s, File > Exit | 1.6 s, pausing text | 1552 pausing · 3326 closing · 15332 `Stopping the local service…` / `This can take up to 12 seconds.` · 25336 second sentence (10.0 s in) | exit code 0 at 28.5 s, 13.2 s after the ending state began; leftover record left |
| Literal brief, hold 40 s, tray Quit | 1.7 s, pausing text | same as the first row up to 33377 (ending) | exit 0 at 38.6 s, which is 5.3 s after the ending began: the hold released at about 40 s and the thawed broker ended the wait; no leftover record (see finding 2) |

- The ending text, title and numbers match R1 character for character; the number follows the policy field (30 by default, 12 when set). The second sentence appears 10.0 s after the ending began, not before.
- In the ending state, from inside the app (no OS key, mouse or focus): an Escape keydown on the dialog, the dialog's `close()` (what its window close button calls) and a second File > Exit (the Ctrl+Q callback) changed nothing: same text, same window count (2), and the app kept waiting and still ended by itself.
- Tray: tooltip `Comic Metadata — Quitting…` and menu item `Quitting… (disabled)` within 35 ms of the click; 0 guard violations through every quit.
- The leftover record written after a quit the broker never answered is `schema 1`, `source: "shell"`, `members: null`. After the frozen broker and its engine parts were gone (hold ended, 10 s later: all four recorded PIDs dead, port refused), the next start on that root was a normal start (dashboard, no previous-session screen) and removed the record. Tray Quit then exited 0 in 7.6 s with nothing left.
- Not leftover by accident: after clean quits (promotion, core, normal start after a previous session) no `leftover-*.json` existed (R5 item 10, both halves).

## 2. The previous-session screens: pass

Harness: a dummy process held with `tests/debug_hold.py --mode exit --write-record <QA locks> [--age N]` (record `--age 0` for P1, a second record `--age 180` for P3). Samples of the startup page (text, hidden, disabled, `aria-busy`, titles, rects) were taken every ~25 ms from the main process. Nothing was focused or clicked with a mouse: Try again and Quit were DOM clicks in the offscreen renderer, and tray Quit is the app's own menu callback.

- **P1.** Heading `The previous session is still closing.`; detail `Part of the local service has not ended yet. Try again in a moment.`; a `Checked at 08:41:31.`-style line present; buttons `Try again`, `Open log folder`, `Quit` left to right, all enabled; tooltips exact (`Check the previous session again. The app starts once it has ended.`, `Open the local app's log folder.`, `Close Comic Metadata.`). Tray: error icon and `Previous session still closing. Open the window for details.`; Quit enabled. Window invisible, unfocused, offscreen, 0 guard violations.
- **Try again x5.** Each press: P2 `Checking the previous session…` with Try again disabled, `aria-busy="true"`, same label, detail and `Checked at` hidden (`visibility:hidden`), Open log folder and Quit enabled, tooltip `Checking the previous session…`. Then P1 again with a new time every time (08:41:38, :45, :52, :59, 08:42:06). P2 lasted 5.6 to 5.7 s each time (the check starts a broker, which finds the record and exits 123). No blank frame in any sample window.
- **P3 and ages.** Record age 3 minutes (rewritten between checks, by text edit) gave P3 at all four sizes; age 1 minute gave P1. A fresh start with the tool's `--age 180` record showed P3 at once: `Part of the local service has not ended yet. Try again, or restart your PC to clear it.`, `Checked at …`, tooltips exact.
- **Layout (his check 13, and the 640 px wrap question).** Measured P1, P2 (after P1 and after P3) and P3 at content width 1280, 1000 and 640 px, and at the narrowest window the app allows (outer 640 px, inner 641 px). The three buttons have identical rects in every state (`Try again` x 24, w 93.3; `Open log folder` x 125.3, w 141.9; `Quit` x 275.3, w 60.4; all y 187, h 43). None is under 40 px high, text and buttons stack without overlap, and there is no sideways scroll (`scrollWidth` = `clientWidth`). **The P3 detail line does not wrap at 640 px:** its height is 21 px (one line) in P1 and in P3 at every size, so the buttons do not move. Nothing to flag for Judy.
- **Quit in every state.** Page Quit in P1: 0.16 s. Tray Quit in P1 (next start, dummy still alive, P1 again): 0.15 s. Page Quit while P2 was on screen (P2 seen at +99 ms, Quit at +251 ms, no result before it): process ended 0.26 s after the click. Page Quit in P3: 0.21 s. Tray Quit in P3: 0.19 s. All exit 0, port refused, no PID left. The leftover record stayed after each Quit (the next start re-checks it).
- **Normal start after the dummy is released.** The dummy was ended with `TerminateProcess` while the debugger held its exit: Try again still gave P1 with a new time (a part still finishing counts as alive). With the hold released and the dummy gone, Try again showed P2, then the start phases `Preparing the local service…`, `Opening the dashboard…`, `Opening setup…`. The setup page opened, the engine was private, authenticated and owned, and the record was gone. After setup the dashboard opened and tray Quit exited 0 (7.1 s, includes the pause) with nothing left.

## 3. The old banner states (B1 to B4) are gone: pass

- **Absence check with a positive control** (`absence-check-v0.6.7.txt`). The strings `could not be stopped`, `Task Manager` and `CLOSURE_UNCONFIRMED` are found 7 times in `desktop/` of the 0.6.6 source commit `30e55c40d2bf0d91e9f395d262598fe5fb53ff20` (positive control). In `desktop/` and `static/` of `9d1ad1a` there are none outside `desktop/tests/`. Inside it there are three lines (a comment and the absence test's own word list in `quit-absence.test.cjs`), and `desktop/tests` is not in the shipped asar (0 hits for both test file names). A raw-byte search of the extracted payload (`resources/engine` including `static/`, and `app.asar`) finds none; the same search finds `The previous session is still closing` 4 times in the asar (method control).
- **On screen.** The core run's dashboard text (first 4000 characters) carries none of `could not be stopped`, `Task Manager` or `still closing`. The generic banner for `RESTART_EXHAUSTED` still reads `The local service is not responding. Try again or open the log folder.` with Try again and Open log folder, and Try again from it brought a new broker and the dashboard back (section 6).

## 4. Nested ComicInfo (QA fixture library only): pass

A private library of 12 plain cbz, one cb7, two matched fixtures whose only ComicInfo is `Scans/ComicInfo.xml`, and three unmatched controls, with a synthetic GCD offline index. The app ran its ordinary pass; after the Quit the archives and the catalog were read read-only.

- **Read as metadata.** Control Alpha (only ComicInfo in a subfolder, no source can match it): catalog status `embedded`, metadata `Series` "QA Nested Alpha", `Number` "1", `Summary` "Alpha nested summary." read from the nested copy. Negative control Beta (two nested copies): status `missing`, nothing read (ignored, as specified). All three controls are byte-identical to the fixture afterwards (the app wrote nothing).
- **A write merges and removes.** Fixture 013 (nested `Series`, `Number` 13, `Summary`, `Writer`, `Genre`): status `tagged`. The archive now holds `cover.png` and one root `ComicInfo.xml`, no nested ComicInfo. The root copy carries the nested `Summary`, `Writer` and `Genre` once each beside the app's own `Year`, `Month`, `Publisher`, `Title`, `Count`, `LanguageISO`, `Web` and `Notes` (GCD offline credit).
- **A nested "None" Number is blank.** Control Gamma (nested `<Number>None</Number>`): `embedded`, metadata has `Series` and `Summary` and no `Number`. Fixture 014 (nested `Number` None, `Summary`): tagged; one root ComicInfo, nested removed, `Number` is the app's `14` (never "None"), the nested `Summary` merged, and no field equals "None".
- Counts at the end of the pass: `tagged` 14 (12 plain + 2 nested), `embedded` 2, `missing` 2 (Beta and the converted cb7). The cb7 was converted to cbz by the bundled 7-Zip.

## 5. Core smoke: pass

- **Launch.** The packaged app reported 0.6.7, packaged, with one invisible, unfocused, offscreen window and a private authenticated engine (HTTP 200, owned). The 28 guards (window show, focus and flash; app and web-contents focus; notifications; dialogs; `shell.*`; every child-process API) stayed clear: 0 violations and 0 other spawns through the core run.
- **Tray.** The PNGs the running app read from its archive equal the source manifest for all 8 files; four icon states are distinct at both sizes (4096-byte 32 px and 1024-byte 16 px bitmaps). The real `Tray.setImage` showed processing on the ready dashboard. The real Pause callback gave the paused icon and tooltips `Pausing. Finishing the current operation.` then `Paused. Gemma released from GPU.`; the real Resume callback gave processing again. Menu: Open, Pause (disabled on setup, enabled on the dashboard), Quit.
- **Close button.** `window.close()` on the setup screen, on the dashboard and on the failed screen kept the process alive and the window not destroyed (hidden, tray-resident); tray Quit then exited 0 each time.
- **Ordinary pass.** First-run setup through the real shell IPC; all matched fixtures tagged in 7.2 s; a tagged comic carries ComicInfo with Series "Futaba QA Fixture" and Number 1. Feed stub: 1 request (the update check, answered with 0.6.7's `latest.yml`, so no update offered). Model stub: 48. No provider call (the QA hook refuses every non-private socket).
- **Normal Quit dialog.** From the ready dashboard the quit dialog appeared 1.54 s after the click showing the existing pausing, then closing, stages (unchanged by 0.6.7).
- **Live app untouched.** Sergei's four `ComicMetadata.exe` processes (824, 71200, 71924, 109992) and the 8765 listener (PID 16320) were identical before the first run and after the last. QA mode refuses ports 8765 and 11434. `%LOCALAPPDATA%\ComicsMeta` and `Y:\Comix` were not touched.

## 6. CHANGELOG items beyond the list: pass

- **Engine stopped from outside.** The broker was ended by exact PID (exit code 1). Retry (the same IPC the button sends) brought a new broker and the dashboard back; a second outside end then tray Quit: exit 0 in 0.9 s. Four outside ends in the restart window gave `RESTART_EXHAUSTED` with the unchanged banner and a working Try again (new broker 5, dashboard back). After one more end the failed screen came again, tray Quit from it exited 0 in 0.2 s, and the close button on it kept the process.
- **A Quit during Retry cancels Retry.** With the engine port held by the harness so Retry's wait lasts, Retry was clicked and tray Quit 2 s later; the port was released 3.5 s after that. The app exited 0 (3.8 s) and no new broker was started after the Quit (0.6.6 started one 14 ms before exit). Every recorded PID was gone at the exit and the port refused. 2 stale claim files remain (finding 5).

## 7. The promotion-schema evidence (for the release script)

`tray-evidence-v0.6.7-promotion.json`, `tray-owned-v0.6.7-promotion.json`, `package-binding-v0.6.7-promotion.json`, `extraction-owned-v0.6.7-promotion.json` and `asar-evidence-v0.6.7-promotion.txt` are written directly by the harness from the final run of the promotion smoke (launch, ready dashboard, the real Pause and Resume callbacks, the real Quit callback), with the same fields as the 0.6.6 `-promotion` files. I checked key by key: 82, 36 and 41 fields match exactly, and the binding file has 16 fields in 0.6.6 and 17 now. The only difference is one added informational field, `fullExtraction.treeDigestMethod`; `treeFiles` and `treeDigest` are now computed by the script, not copied.

Every value was read in that run. The tray sequence is processing, processing, processing, paused, processing. `processing`, `paused` and `resumed` are each `exact` (32 by 32, 4096 and 1024 bytes); `markResources` is 8 of 8 matches, with 4 and 4 distinct. `spec.sourceHead`, `spec.manifest`, `spec.installer` and `spec.feed` equal the values in the Identity table. `quitRequested` is `actual tray Quit requested`; close code 0, nothing remaining, port refused, no claim; 2 model requests, 0 feed requests, 0 violations, 0 other spawns.

I replayed lines 57 to 64 of `create-local-promotion.mjs` (the 0.6.7 copy) over these files. They pass, and 12 negative controls (a violation, a wrong hash, `pass` false, a missing field and so on) are each rejected. I did not run the script itself (it needs the publication config).

Pin these: `tray-evidence-v0.6.7-promotion.json` (smoke evidence), `tray-owned-v0.6.7-promotion.json` (its Job closure), `package-binding-v0.6.7-promotion.json`, `extraction-owned-v0.6.7-promotion.json` and `asar-evidence-v0.6.7-promotion.txt`. Their hashes are in the evidence table.

## Findings

1. **Minor, open, UX-shaped (for Judy and Ender).** With a silent broker the Quit takes about 65 s from the click, not 31 s. The shell first waits up to the closure wait in the `Closing…` stage (30 s, both buttons disabled, no time stated). Then it shows the ending state, whose text says `This can take up to 30 seconds.`, for up to 31 s more. The brief's "exits at about 31 s" is true measured from the start of the ending state (31.2 s; 13.2 s with a 12 s wait), not from the click (64.6 s; 28.5 s). The Judy spec (R4 item 3, R5 item 1) reads as 31 s at most from Quit. The code comment in `graceful-stop.cjs` shows the two waits are intended (closing up to one wait, then the forced path), so this may be a spec wording gap rather than a defect. It is theirs and Sergei's to call. Quit always ended, every time, with the broker still frozen.
2. **Info, procedure.** The brief's `--seconds 40` is shorter than the shell's own wait (about 3.4 s of pause stages, 30 s closing, then 31 s ending). The hold released at about 40 s and the thawed broker ended the wait (exit 5.3 s after the ending began, no leftover record). To see the app end by itself and the leftover record, hold for at least `2 x wait + 40` s (100 s by default). Both runs are in the evidence.
3. **Info.** The leftover record a silent-broker quit leaves is written by the shell (`source: "shell"`, `members: null`), not by the broker. The next start was normal and removed it (section 1), so nothing sticks.
4. **Info, for Judy.** Try again with the part alive shows P2 for 5.6 to 5.7 s each press (the broker has to start and exit 123); the spec only needs 0.5 s. After a passing re-check the visible phases were `Preparing the local service…`, `Opening the dashboard…`, `Opening setup…`. `Starting the local service…` and the catalog phase do not show, because the earlier phases are held back during the 0.5 s P2 hold (R2 describes the phases as starting at `Starting the local service…`). Neither is a fault.
5. **Info, inherited (0.6.6 finding 4), now seen in three more runs.** After the engine was ended from outside, two `engine-*.json` claim files remained in the locks folder in each of the broker-ended, failed-screen and Quit-during-Retry runs. All holders were dead and nothing outlived the app. The CHANGELOG says claims are now judged by their lock.

Harness notes (not app findings): my first frozen-broker check assumed the status endpoint stops answering when the broker freezes. It does not (child server process), so the check was replaced by the effect (the broker is gone only when the hold ends). The first previous-session runs also failed on two harness faults of mine: a JSON number round trip corrupted the record's creation time (above 2^53), and a classifier counted the page's own 6 ms "button disabled, heading not yet changed" frame as a result. Both are fixed; the numbers above are from the final runs.

Pattern alerts: 1. Stale `engine-*.json` claim files after an outside-ended engine (0.6.6 finding 4; 0.6.7 finding 5). Proposed disposition: **defer** (Info, harmless, no process outlives the app, claims are now judged by their lock). Jane to confirm or change.

## Skipped and not covered

- **Skipped, needs Sergei's permission (focus):** R5 checks 9 and 19, and every check that needs the real window shown or the OS focus (the quit dialog shown with `show()` versus `showInactive()`, focus after each transition, a screen reader). QA mode keeps every window offscreen, so none of these ran.
- **Not run, outside the brief's list:** the Ctrl+Q key chord itself (File > Exit, the same callback, was used); Quit now and Cancel quit pressed during the pausing stage (R5 3); status calls failing twice (R5 5); Quit with the engine not ready or from the setup page when the wait lasts (R5 6; setup and startup Quit exits were measured, 1.1 s and 0.7 s); a forced close under 1.5 s showing no dialog (R5 7); a second copy started during the wait (R5 8); a corrupt record or one from before a reboot (R5 17); a start failure that leaves a record (R5 18); the whole-file string comparison of R5 23 (the strings shown on screen were compared against the spec's text in code).
- **Not run:** Windows sign-out and shutdown always closing the app (needs a real sign-out); worker messages reaching `engine.log` (CHANGELOG; the restore lines); running the installer and an actual update; live provider answers; GPU release; the full test suite (Ender's).
- Nothing was written outside `I:/AI Projects` by the QA processes. My own slip: two empty placeholder files in Git Bash's `/tmp` were created and removed within the session (checked absent). The personal-folder listing was not taken (the 2026-11-15 approved-root ruling supersedes it, as in the 0.6.6 report).
- Everything I started has exited (checked by command line and path against the live app's four processes and the 8765 listener). My scratch (extracted payload, private QA roots, run scratch) was removed with the sweep's approved mode: 2,403 files, 797.16 MB, free space +798.54 MB. Only the evidence folder below remains.

## Evidence

Folder: `I:/AI Projects/Temp/futaba-067/evidence/` (outside the tool's repo by instruction; copy it into the tool's `scratch/` or the promotion config before anything sweeps it). The `harness/` folder is the 0.6.7 revision of the 0.6.6 harness plus its README; the digest of its sorted `<name> <sha256>` lines (16 files) is `84883becf815f729ee0519e0ce97e01b388088c4fbf8242c6d2eeb266ed5cb1d`. The harness files are exactly those that produced the evidence, except two later additions: the `next-start-after-frozen` scenario (run once, separately, as `scenario-next-start-after-frozen-v0.6.7.json`) and its entries in `run-all.sh` and `collect-evidence.cjs`.

| File | Bytes | SHA-256 |
| --- | --- | --- |
| `absence-check-v0.6.7.txt` | 2826 | `adf4d99825785fd54eeeac2ce53b0b2d2cc29fad33e953cc3b16e678d514c05c` |
| `asar-evidence-v0.6.7-promotion.txt` | 1171 | `7e28ad00cecca1c4e35cb2a407b5769e65d5f2772c99a7441e657c420a723173` |
| `asar-evidence-v0.6.7.txt` | 201 | `9ae353c257a0ac9e1e28340afb8cbb03ef2b7d2682c08dab146dcd4690e388f9` |
| `engine-manifest-evidence-v0.6.7.json` | 326 | `7756883f9ae1de89c2b0a6464b6be71cd5187d133f19d41a827b7390fef7ba91` |
| `extraction-owned-full-v0.6.7.json` | 2050 | `dcbdd158ecf634677f2a12eacd90045d8fece481f54d299c7491128d62b37a81` |
| `extraction-owned-v0.6.7-promotion.json` | 2725 | `0ac57accc2403d65b6d49b4ce537c09afc43eeb3b014f7e3671cd5c978f68e61` |
| `harness/asar-check.cjs` | 1386 | `19f96d6ad24c8980f12508fae47386802801460ac17b3b4b5db5492c938424cc` |
| `harness/assemble-promotion.cjs` | 4627 | `eec43ebbd1bb37c950ec6c02e60c2cf058efb49874f80374cf6a8f900ee949df` |
| `harness/collect-evidence.cjs` | 1490 | `6a53423422b3620a5425e829eaa56d3e3819cfc2b62d8b044032adb874d7adac` |
| `harness/engine-vs-manifest.cjs` | 1650 | `2a03a7a31da98c30d4d7f12a9ae7538ae348f0a9ba1d6b9df7793176043e7729` |
| `harness/extract-full-cfg.json` | 446 | `1c24613ae898b0c3b04d349c1db9a6842b7c07d44cb4485d38cc92f7c840a999` |
| `harness/extract-two-cfg.json` | 499 | `632f908dcbad43c173259aa26f91c241e0640cf3d0cece229133b1b572627c86` |
| `harness/fixture.py` | 6153 | `f9f0606fa608782c6f8dc0e4300423f6007b62210159b44f12f64596e005371b` |
| `harness/lib.mjs` | 14087 | `79e35f26cfc51c04711d430b26d901d624ad806c03ef2b75f97a788d575f6ad6` |
| `harness/nested_probe.py` | 2433 | `15ddeafa19a6bf4fe6b0a7daee4c9918d19662df37997a6517eb4897304be61e` |
| `harness/observer.cjs` | 17352 | `27f428986f8f274052c5ce5a6fa274647cbaebe045dd1d2822aa817e661d1ea9` |
| `harness/owned-run.mjs` | 1835 | `8c255477e3a0dfe64b71041fde34f46b782d89ed1d58117c9b2444e3c85c721c` |
| `harness/README-harness.txt` | 4994 | `a838d84ab591aa80e9ac6e1384ae573528aa828acc5e67bf909a56c9dcbe2db1` |
| `harness/run-all.sh` | 1099 | `33593f9851c67a863aaa755eaf93608fd118d71717f3676ea0b499642da4a082` |
| `harness/run-scenario.sh` | 1098 | `14fc3dfc2160191129b8f663049015ca01e0ae08ce43c5612e47f5d302f0b063` |
| `harness/scenarios.mjs` | 74434 | `5bcedf147b77e54f7afb82d8789487130e5841d115bdb5276750b4c90292bf44` |
| `harness/validate-promotion.mjs` | 6655 | `6505693b863def9779271bf048f2d5ba8623a22835e889da1e450b5245b99f8e` |
| `live-app-untouched-v0.6.7.txt` | 435 | `50b303974612ef76b0a5a28723382608e3be940c31052ce2315754eee1b3009c` |
| `package-binding-v0.6.7-promotion.json` | 1510 | `e4606acb9bcf0b8e1b5c733152303fb031b5d28a94ddf60cf547f01d9e6a9054` |
| `scenario-broker-ended-outside-v0.6.7.json` | 10419 | `1cfcba3d2de8495f0ed778b01823bf22c39df584c1438a268a72a198dd66b3c0` |
| `scenario-core-nested-v0.6.7.json` | 56864 | `03ca85b16ded5bc7691231863e5d8600bf3d40fa06c1b45011d5a0fd3268394d` |
| `scenario-failed-screen-v0.6.7.json` | 9346 | `c4152810bdd7bd9bd3ac8a3a631c2b9ff152e258164c318748b8ef32c9bc7232` |
| `scenario-next-start-after-frozen-v0.6.7.json` | 10989 | `8ff645babb719d11fc1957eee0ed38e8c6a49271f175231d5e19f805f5bfcdf8` |
| `scenario-owned-broker-ended-outside-v0.6.7.json` | 4405 | `6c759ae274b621abadac5741ecff08e40227e5638e60781d6200d7085af795ae` |
| `scenario-owned-core-nested-v0.6.7.json` | 8917 | `d951710949e9191be6fe2cc65f0e8f8f32acb3eae8d63dcdb395523dd066b3dd` |
| `scenario-owned-failed-screen-v0.6.7.json` | 3584 | `e3f0ec1a429e695df42248947583883cf36f63efac11134a94f034fa5fd7ed28` |
| `scenario-owned-next-start-after-frozen-v0.6.7.json` | 2455 | `6135aadf1b41eb741b6f7abd089124bcc90c1b09851c67ff6c393985b4f65fc2` |
| `scenario-owned-previous-session-v0.6.7.json` | 12285 | `f5d62171e0ef6b56289486aeeff77726fddee80ece3473998d41308c81ff3ff5` |
| `scenario-owned-promotion-smoke-v0.6.7.json` | 2818 | `1cab9bdf04efc29c51604cf03f96dc16dcae96e9dde7d6f69628ac5a764e3aa5` |
| `scenario-owned-quit-during-retry-v0.6.7.json` | 2539 | `ef277247895942349041e378f81d77e13124023bc5d9616703498ff8af8d10de` |
| `scenario-owned-quit-frozen-30s-long-hold-v0.6.7.json` | 5572 | `51da38da2eb32ddbc285b31cde78f1ef0938c4b501876d14f94ff933a68207d3` |
| `scenario-owned-quit-frozen-closurewait-12-v0.6.7.json` | 5543 | `5b23dccc565f6b9f94660b04414bc1630d763024a4788f7c7c14a2ddb1397a79` |
| `scenario-owned-quit-frozen-literal-40s-hold-v0.6.7.json` | 5577 | `2fd4cc1011e6f6d3447e6374fda5dd8e0ebe624d84e0683d43d0b32751a5badb` |
| `scenario-owned-setup-quit-v0.6.7.json` | 2490 | `3158351aa755043a62be0334ba1a031eb7780666ac0d678d1c41db84ec5c37cf` |
| `scenario-owned-startup-quit-v0.6.7.json` | 1989 | `f97c9c9b760915d2615a373334f4e7e38347415fbf2618a4ae221dcf43c8a9af` |
| `scenario-previous-session-v0.6.7.json` | 37349 | `91c4c0a8add47c79d5ccb868a2adff1a15a69867c9bb520c325adc0937f3a649` |
| `scenario-promotion-smoke-v0.6.7.json` | 8059 | `51bbad2adfedd23fa0e42571537de95401c90041ea5f4c83c184c6ebe60e1e06` |
| `scenario-quit-during-retry-v0.6.7.json` | 8966 | `505dab819503a5441c714ae70425d0ea1e037c9d9a09e487a40019c8d447708c` |
| `scenario-quit-frozen-30s-long-hold-v0.6.7.json` | 23258 | `29dd34f02f7dccd5caecd8d1b09e6b942fce60a95c931bc997efadb1689266bd` |
| `scenario-quit-frozen-closurewait-12-v0.6.7.json` | 23222 | `23dce60d28a0e3730b74cddce859e4abdd3d50474659fca265a33c98e5dea6b2` |
| `scenario-quit-frozen-literal-40s-hold-v0.6.7.json` | 20696 | `0f2f80f0e4c02a110416a612886cd134c4245f1e3010b76d794f3ca44c84ca08` |
| `scenario-setup-quit-v0.6.7.json` | 7369 | `d0311f8130aeb17b15a85f9bd1682dd1009d794a4019521ee0c18161d222880d` |
| `scenario-startup-quit-v0.6.7.json` | 6610 | `e9d6071f94d56ba80dd6849135db79c8d74e8d021113fa5a8d2ada691a24979b` |
| `tray-evidence-v0.6.7-promotion.json` | 3333 | `c1e19c9120bff00a5b537c74ae801695e49dc0724ecffe02071e9544983b6770` |
| `tray-owned-v0.6.7-promotion.json` | 2818 | `1cab9bdf04efc29c51604cf03f96dc16dcae96e9dde7d6f69628ac5a764e3aa5` |
