# Comic Metadata 0.6.4 tray QA · 2026-11-18

**Tray-smoke verdict: GO** for the private packaged launch and the 0.6.4 delta at source `445bd36c79af3565f31ce1a66be4ee89466064c6` (Senua RELEASE CLEAR is on a00c39e, docs only on top).

The installer SHA-256 `2cc0f597dada56756af044c5554c1402136ece2c9051ae6cd8192ccf9fca157f`, unpacked executable SHA-256 `4d669fae4a0a84965512a74b2e7e7c7215bff5f7df5d9d88dbd663d0f9040938`, app.asar SHA-256 `065ac7a680bfbb4c0ac006f9d6aed0858232a03d5bde7532c99b0d267b187ca2` and feed SHA-256 `560ba838f4c4ba0d6ce9477912742c102b9e8b8958d5d072ff8161e2db8dccc2` matched the frozen package identity before the first launch. The read-back source candidate manifest SHA-256 was `8507a3806a30537ef43f10ed28b7739803d3ed6d54b81859909912085961ddf5` (Sully's `source-manifest-445bd36.json`, head 445bd36). All 72 packaged engine files that exist in the source (top-level `*.py`, `static/**`, `VERSION`) matched it byte for byte; `installer_launch.py` matches `desktop/installer_launch.py`. The 621-file `win-unpacked` tree hashed the same before and after every run (tree digest `9ede77064dca723d73cdf1bb99544954981b69262ecfff7470509f00af474722`). Scoped QA verdict: there was no entry-check receipt, so this is not formal release clearance (same limit as 0.6.3).

## 5. Smoke (packaged app, private QA mode)

- The actual packaged app reported 0.6.4 and opened one invisible, unfocused, offscreen window. Private authenticated engine status was HTTP 200 and owned for broker PID 74112. Every visibility, focus, dialog, notification and spawn guard stayed clear (17 guards installed, 0 violations at start and at the end).
- Tray: the preview observer called through to the real Electron `Tray.setImage` and compared SHA-256 of its decoded pixel buffers with the exact PNGs read from the app archive. The actual Processing, Pause and Resume tray menu callbacks selected the right bitmaps at scale factors 1 and 0.5 (4096-byte 32 px and 1024-byte 16 px buffers). All 8 packaged PNG hashes equal the source manifest, and the four decoded icon states are distinct at both sizes (`asar-evidence-v0.6.4.txt`). The pause used a private model stub, as in 0.6.3.
- The enabled native tray Quit callback exited normally with code 0 within 3 s of the click; the private engine port then refused connections, no claims remained in the private lock folder and none of the recorded PIDs survived. The bounded Windows Job returned complete zero active processes and zero unsignaled handles, with 18 retained handles, after 6.094 s. The pass used two private model requests, no feed request and no provider call (QA mode refuses every non-private socket).
- Installer to tested runtime: the pinned 7za (SHA-256 `b0cfdeaf429f5cc53f85123dd8f5a5feb92c19d31aa34df257edf9a26be05f95`), under its own private Job, extracted `ComicMetadata.exe` and `resources\app.asar` straight from the installer; both hashes equal the files the smoke ran (`package-binding-v0.6.4.json`, owner record `extraction-owned-v0.6.4.json`).
- Raw packaged observations are in `tray-evidence-v0.6.4.json`. Native Job close proof is in `tray-owned-v0.6.4.json`.

## 1. Re-ask scheduling (idea 5), default on: pass

64 checks against the packaged engine modules, all pass.
- Misses 1 to 5 wait 1, 2, 4, 7 and 7 days, each stretched by a random 0 to 50% (1,500 draws per step: every one inside the window, means 1.25 x the base). From the 6th miss in a row, 30 to 45 days (steps 6, 7 and 8 checked). A draw of 0 gives exactly 1/2/4/7/7/30 days; a draw near 1 gives 1.5 x each.
- A miss under a changed rules stamp restarts at miss 1 (1 to 1.5 days); the same stamp keeps counting; a stored count with no stamp carries over, as the Brief says.
- Verified, error and provider-wait records are identical to the 0.6.3 module for every prior state tried (the 0.6.3 `source_scheduling.py` was run side by side); 0.6.3 misses were 1,2,4,7,7,7,7,7 days with no spread.
- A GCD-offline miss (or verified-nothing-new) under the active index and rules stamp makes `nothing_can_search` true (the unsearchable marker applies) and a marked comic is not due; an error is not a settled miss; a new dump wakes it.
- `retry_spread: 0` gives exact waits, `long_miss_after: 0` never exceeds 10.5 days (spread still on), `gcd_offline_miss_final: false` stops the marker and changes the marker fingerprint so marked comics wake (switching back restores it). Controls that the numbers are honoured (`long_miss_after: 3`, `long_miss_days: 10`, `retry_spread: 0.25`) also pass.
- Bad values (string, negative, boolean, null, list, object, NaN, Infinity, a non-object section) fall back to the default for every setting. For the boolean setting only a JSON boolean counts; `0`, `1` and `"false"` fall back to on.

## 2. Fix A, durable saves: pass

- 40 rounds of every writer (progress, folders, browser-search, plain and keep-previous saves) left no `*.tmp` anywhere. One save was traced: bytes fsync-ed first, then `MoveFileExW` with REPLACE_EXISTING | WRITE_THROUGH (0x9).
- 30 hard kills (TerminateProcess) of a process saving 1 MB state files in a loop: all 30 landed inside a save (an orphan temp file was left each time), and after every kill all three state files and their `.bak` copies read back as complete JSON of the right shape; none zero-filled, cut short or mixed. A clean restart followed each kill: every reader read, nothing was put back, no `.unreadable`, no log line, and a further save worked.
- Real packaged engine: killing the engine's server process (the realistic crash; the broker reports 126) brought the engine back in about 1 s with service ready, all three state files intact and tray Quit exiting 0. Killing the whole app tree (shell, broker, server, workers) and relaunching the packaged app on the same state root gave a clean start: no recovery screen, no restore, no `.unreadable`, files intact, tray Quit exit 0.
- The 30 kills left 26 temp files (31 MB) in the test folder. Existing maintenance removes `*.tmp` older than a day; not changed in 0.6.4.

## 3. Fix B, unreadable state files: pass, with one Minor gap (finding 1)

Checked twice: against the packaged modules (18 cases), and in the running packaged app through its real engine, HTTP dashboard and dashboard page (19 cases, processing paused).
- progress.json, folders.json and browser-search.json, each replaced with all-zero, truncated and non-JSON content: `<name>.unreadable` holds the damaged bytes exactly, the `.bak` content is put back, and the dashboard shows the saved record, never "Status unavailable" (older phase, folder counter 0 / 500, cover status). All three at once (the 2026-11-13 picture) also recovers.
- A missing file starts afresh and is not restored from `.bak` (the dashboard shows the default: phase Ready, 0 / 0 folders; `.bak` untouched).
- No readable `.bak` (absent, or all zeros): the 0.6.2 preserve-and-wait behaviour; the damaged file is left untouched, nothing is written or guessed, and the dashboard says unavailable ("Status unavailable", folder counter "Unavailable").

## 4. Options 2, 3 and 4 off with no "matching" key: pass

`metron_spellings`, `collection_label` and `yearless` read false with no config, with a config that has no `matching` key, with an empty section and with wrongly typed values; `metron.rules_stamp()` stays `3:cover_rule_v2,filename_year_formats,folder_year,unnumbered_as_one`, the 0.6.3 value computed from the 0.6.3 source, so shipping wakes nothing. Behaviour while off: no spelling variants, no collection-label identity, no yearless identity. Positive controls: each switch turned on changes behaviour and the stamp.

## Findings

1. **Minor, open (Fix B diagnostic gap).** The one `could not be read; its previous copy was put back` line reaches `logs/engine.log` only when the engine process does the restore. When a worker process restores first it is lost: browser-search.json showed 0 lines in 4 of 4 restore events in the final run (2 of 4 in an earlier run); progress.json and folders.json logged exactly 1 each (the engine restored them). `.unreadable` and the restore itself were correct every time. Cause: `supervisor.py` starts workers with no stderr argument and CREATE_NO_WINDOW, and a probe with the same call shape showed the child's stderr is not the parent's log file. Repro: with the app running, overwrite `data\browser-search.json` with zeros and compare `.unreadable` against the engine log.
2. **Major, open, inherited and outside the 0.6.4 delta (`desktop/`, `engine_host.py`, `static/` unchanged since 0.6.3).** If something ends the engine broker `python.exe` itself (exit code 1, not the broker's own 0/75/125/126), the app shows the failed screen, Retry starts no new engine and tray Quit (enabled) does not end the app (the shell fails closed as CLOSURE_UNCONFIRMED); only ending the process tree closes it. Repro: terminate the python process that Electron started for `engine_host.py`, wait 1 s, click Retry, then tray Quit; after 45 s the app was still running. The realistic crash path (server process killed) recovers and quits normally. Not a release blocker for 0.6.4; touches the close-button rule, so Jane and Sergei should decide the disposition.
3. **Info.** Senua's N1 is visible in the live app: the dashboard poll is the process that restores progress.json and folders.json (it logged the lines). The worker-versus-dashboard overwrite race she describes was not exercised.

Pattern alerts: none

## Not covered

Power-loss and OS-crash durability (a process kill proves atomic replacement, not that the bytes reached the disk), Windows Explorer's displayed icon raster, physical UI input, running the installer, an actual old-to-new update, GPU release, the real GCD index and real Metron or ComicVine answers. All runs used a private state root, private ports and a private model and feed stub; Sergei's profile, `%LOCALAPPDATA%\ComicsMeta` and the installed app were not touched, and no focus was taken. A debugger left attached kept the Electron process alive after Quit in two early attempts of this pass; the harness now closes its private inspector at Quit (as the reviewed install/update harness does), and the passing runs exit by themselves. That was a harness artifact, not a product behaviour.

## Evidence

Folder: `I:/AI Projects/Studio Illuminati/WIP/Comics Meta Organizer/scratch/qa-064-evidence-v0.6.4/` (kept for the promotion check; it lives in the tool's ignored `scratch/` folder, so name it in the promotion config or release notes before the 48-hour idle sweep reaches it).

| File | SHA-256 |
| --- | --- |
| `tray-evidence-v0.6.4.json` | `d0d049109eabf7810526a5c93e23535edf870d57d6a9cb8f5e122d820d2eec19` |
| `tray-owned-v0.6.4.json` | `1e3ca60e64bec6c2b35cfab5a33f2f2f953b8727ed911d011aa80e1ab9d5e6c3` |
| `package-binding-v0.6.4.json` | `550416a75680003506efc55fab907de4a11accc526b2d097ce5fa204f7bb1456` |
| `extraction-owned-v0.6.4.json` | `51e9be176276191d6fd7f9dbef87f019a5e598dd270c558b4a513ebe945440b7` |
| `asar-evidence-v0.6.4.txt` | `11217e13bdfa4c6b921d21ff526b91a852ddadb80f4e19a6a8cff2d7fee885ff` |
