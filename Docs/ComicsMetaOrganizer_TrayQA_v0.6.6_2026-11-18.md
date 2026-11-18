# Comic Metadata 0.6.6 tray QA · 2026-11-18

**Tray-smoke verdict: GO**

GO for the private packaged launch and the 0.6.6 delta at source `30e55c40d2bf0d91e9f395d262598fe5fb53ff20`. Senua RELEASE CLEAR is on `acb567d`; the only change after it is Sully's version-and-changelog bump plus the review document (checked: `git diff acb567d 30e55c4` touches no code file).

The installer SHA-256 `f97bb8d9a234beb1e0d242aabf9257983dc321795c4753563491707f0ae07c91` matched the build hash before the first launch. The pinned 7za (SHA-256 `b0cfdeaf429f5cc53f85123dd8f5a5feb92c19d31aa34df257edf9a26be05f95`, under its own private Job) extracted the whole payload: 623 files, tree digest `e4a1695d5f8ef38ed5686970a1de145918c7fd012ef04fbcdf07dff433c5cabc`, identical to the `win-unpacked` tree. `ComicMetadata.exe` SHA-256 `55475f325fbd990b9d10839f10481b437ed1e225da2bff1cf93966e0886129c6` and `resources/app.asar` SHA-256 `b71ff27b2c3b74716c8ab163297ba80fef50e8c8620b5b1bbbf77d592eb71434` are the same in both. Every run below used the extracted payload. Of the 76 packaged engine files, 75 are byte-equal to the source worktree and equal to the commit's blobs once line endings are normalised (the worktree checks out CRLF); the 76th, `update-runtime-manifest.json`, is generated at build. The 16 `desktop/` files in the archive compared with the commit also show 0 differences. `latest.yml` SHA-256 `5fb659c6f1e124c47e9fdd3aa4ea45e74a7db9e00fd02787da0ab6f1a40ca7ef`. Scoped QA verdict: there is no entry-check receipt, and Ender's full suite was not re-run here (Jane reports one failure in it, the stale `test_library_lock … conversion_stops_the_folder_pass` since 0.6.2), so this is not formal release clearance (same limit as 0.6.3 to 0.6.5).

The 0.6.5 harness was not kept, so I rebuilt it to the same method: private QA root and policy, private engine, feed and model ports, a private inspector closed before Quit, every run inside the studio's owned-process supervisor. The harness sources are kept with the evidence. Its guard set is new (28 guards, 0.6.5's was 17), so numbers are not comparable one for one.

## 4. Core smoke (packaged app, private QA mode): pass

- **Launch.** The packaged app reported 0.6.6 and opened one invisible, unfocused, offscreen window. Private authenticated engine status was HTTP 200 and owned. The 28 guards (window show, focus and flash, app and web-contents focus, notifications, dialogs, `shell.*`, every child-process API) stayed clear: 0 violations and 0 other process spawns through the whole run.
- **Tray.** The PNGs read by the running app from its archive equal the source commit for all 8 files; the four icon states are distinct at both sizes (4096-byte 32 px and 1024-byte 16 px bitmaps). The real `Tray.setImage` showed processing on the ready dashboard. The real Pause callback gave the paused icon and the tooltips "Pausing. Finishing the current operation." then "Paused. Gemma released from GPU."; the real Resume callback gave processing again. The menu is Open, Pause (disabled on the setup screen, enabled on the dashboard) and Quit (always enabled).
- **Close button.** `window.close()` (the same close event the title-bar X sends) on the setup screen, on the dashboard and on the failed state kept the process alive and the window not destroyed (hidden, tray-resident). Tray Quit then exited 0 from the setup screen (1.0 s), from the startup screen while the engine was still starting (0.8 s), from the dashboard after a pass (3.1 s, includes the pause) and from the engine-ended cases in section 1. After every exit the engine port refused connections, no recorded PID survived 12 seconds and no claim holder was alive.
- **Ordinary pass.** First-run setup through the real shell IPC on a private library of 12 cbz plus one cb7, with a synthetic GCD offline index. All 12 were tagged in 7.1 s; the cb7 was converted to cbz by the bundled 7-Zip; a tagged comic carries `ComicInfo.xml` with Series "Futaba QA Fixture" and Number 1; the dashboard reads "Processing enabled". The model stub saw 42 requests and the feed stub 1 (the update check, answered with `latest.yml` for 0.6.6, so no update was offered). No provider call was made (the QA audit hook refuses every non-private socket).
- **Installer not executed.** Running it would write the per-user registry entry and the install folder that Sergei's live app uses, and its running-app check could touch that app. The payload extracted by 7za stands in, as in 0.6.3 to 0.6.5.
- **Live app untouched.** Sergei's four `ComicMetadata.exe` processes (71924, 71200, 824, 109992) and the 8765 listener (16320) were identical before the first run and after the last. QA mode refuses ports 8765 and 11434; TEMP, LOCALAPPDATA and APPDATA were redirected into the scratch folder for every process I started. No mouse, keyboard or focus action was used; the Retry and Try again clicks were DOM clicks inside the offscreen renderer, and the tray items were the app's own menu callbacks.
- Every run's owned record shows the Job closed, no forced close and native zero.

## 1. Retry and tray Quit after the engine broker is ended from outside: pass (0.6.4 finding 2 is fixed)

The broker `python.exe` the app started was ended from outside by exact PID (exit code 1, not 0/75/125/126), as `taskkill` and Task Manager do.

- **The 0.6.4 repro.** Ended; 1 s later the shell reads "starting" (the engine restarts itself 0.55 s after the exit; before 0.6.6 that restart hit the same refusal and left the failed screen). Retry sent at +1 s joined the restart already in flight: a new broker was ready and the dashboard was back about 1.7 s after the end, with 2 brokers started in all (no double start). Ended again; Quit at +1.2 s, while the second restart was still starting: exit 0 in 0.58 s, nothing left (0.6.4: still running after 45 s).
- **The failed screen.** Four outside ends within about 7 s spent the restart budget (`RESTART_EXHAUSTED`). The dashboard banner reads "The local service is not responding. Try again or open the log folder." with a Try again button. Engine port free, no claim holder alive. Try again started a new broker and brought the dashboard back in 1.25 s. Ended once more (no automatic restart left): tray Quit from that failed state exited 0 in 0.24 s.
- **Quit during Retry's wait (Senua t1): confirmed.** With the engine port held by the harness so the closure wait lasted, Retry was clicked at t=0 and tray Quit at t=2.1 s; the port was released at t=5.5 s. The wait ended, Quit exited the app with code 0, and a **new broker was started 14 ms before the shell exited** (t=5.758 s, exit at 5.772 s), together with its engine process, which took a library claim. Nothing outlived the app: every recorded PID was gone when the exit was seen, the port refused connections, no holder was alive. It left 2 stale claim files in the locks folder. The user sees nothing; it matches Senua's grade (Minor).
- **Fail-closed and recoverable.** With another process holding the engine port for the whole time, tray Quit is refused after 20.6 s (two 10 s waits): the app stays, no new broker, failure `CLOSURE_UNCONFIRMED`. Once the port was free, Quit exited 0 in 0.2 s. Before 0.6.6 an outside end alone reached this state; now it takes a real holder.

## 2. ComicVine name search skips comics already credited to VerseDB: pass (0.6.5 finding 1 is fixed)

Packaged modules and the packaged python, under the private QA policy; the audit hook refused a public-address connection (positive control), and the `urllib` counter read 0. Each result is paired with the 0.6.5 `comicvine_search.py` loaded as a control.

- **Cite list.** 15 cases: five VerseDB credits (attribution line, "Automatic verified lookup: VerseDB…", a versedb.com Web link, upper case, bare "versedb"), six already-cited sources (Metron, GCD, "Grand Comics Database", Comic Vine, ComicVine URL, `[CVDB…]`) and four uncredited controls ("Versed in lore" among them). 0.6.6 cites exactly the first eleven. The 0.6.5 control misses all five VerseDB credits. `versedb.cites` equals the name search's answer on every case and uses the same pattern object.
- **Lookup.** VerseDB-credited by Notes and by Web: 0 ComicVine requests, no match. The uncredited control: search, issues and issue requests, a ComicVine match. The 0.6.5 control asks 3 requests and matches for both credited cases.
- **A real discovery pass** (`automatic.discover`, Metron and GCD offline patched to miss, ComicVine search switched on): the credited comics made 0 requests and planned nothing (the name search records `no_verified_match`, as for any cited comic); the uncredited control made the 3 requests and planned one write. In the 0.6.5 control the credited comics were asked and planned a ComicVine write.

## 3. A restore of a damaged state file cannot overwrite a newer save: pass, as far as observable

The window the 0.6.5 code left (the `.unreadable` evidence write between the re-check and the put-back) was held open on purpose by slowing that one write, in the packaged `storage.py` and in the 0.6.5 `storage.py` side by side.

- **Race, threads and two real processes.** A newer save (step 99) lands during the restore. 0.6.6: the save waits for the restore (0.51 s in threads, 1.0 s across processes), then lands; final step 99 both times. 0.6.5 control: the save lands at once (0.002 s) and the put-back then rolls it back to step 1, both times.
- **150 randomised rounds** of a worker's read-then-save against a concurrent reader: 0.6.6 had 0 rollbacks and 0 errors; the 0.6.5 control had 1 (the window is narrow; the two deterministic cases are the proof).
- **The lock.** A holder in another process held the file's lock for 3 s: a `keep_previous` save waited 3.005 s and landed; a restore waited 2.0 s and returned the previous copy; another file was not blocked (0.003 s). With the wait set to 1 s, a save raised `TimeoutError` after 1.000 s leaving the file and its `.bak` byte-identical, and a restore raised `TimeoutError` after 1.001 s leaving the damaged file untouched and writing no `.unreadable`; both worked again once the holder ended. A holder killed while holding did not wedge the next save (0.007 s) and left no file behind.
- **The ordinary restore** (zeroed file, previous copy put back, `.unreadable` holds the damaged bytes, one log line) still works.
- **In the running app.** Zeroing `progress.json` (263 zero bytes) while the engine ran: restored, `.unreadable` holds the 263 zero bytes, dashboard state still served. Then 309 zeroing writes in 8 s across `progress.json`, `folders.json` and `browser-search.json` while an 80-comic pass was writing them: the pass finished with all 80 tagged, all three files read afterwards, `.unreadable` copies exist for all three, the app stayed up, Quit exited 0. A live restore from `.bak` is by design older than the damage, so the live run cannot show a newer save surviving; the probe is the evidence for that. (My first live attempt damaged the files before their first previous copy existed; the app preserved them and the pass waited, as documented for 0.6.2 and 0.6.4. A harness mistake, corrected, not a finding.)

## Findings

1. **Minor, open, Senua t1, now seen.** A tray Quit during Retry's closure wait lets Retry start a broker and its engine as the shell exits (details in section 1). No process outlives the app, no user effect; it leaves 2 stale claim files. Senua's fix (read the generation before awaiting the own `forceStop`) is a one-liner.
2. **Minor, open, inherited, UX-shaped (for Judy).** When closure cannot be confirmed and the dashboard is on screen, the banner still shows "The local service is not responding" with a Try again button that does nothing (the guard in `start()` returns at once; the startup screen hides Retry for this failure, the dashboard banner does not). Observed with the engine port held by another process. Before 0.6.6 this state came from any outside end of the broker; now only a foreign holder reaches it. Not in the 0.6.6 delta.
3. **Minor, open, inherited (0.6.4 finding 1, unchanged).** The restore log line is lost when a worker process restores the file: the zeroed `progress.json` in the core run produced 0 lines in `logs/engine.log` (0.6.5's pass saw 1), and during the live damage run `progress.json` and `folders.json` logged 2 lines each across hundreds of damage writes. The restore itself and `.unreadable` were correct every time.
4. **Info, Senua t2 in practice.** After an outside end the dead engine's claim files stay (the failed-screen run left 6, holders all gone) until the next engine sweeps them; the closure check does not trust them, but a reused PID would. No reuse seen.
5. **Info, not observable.** Senua T1 (exit code 1 also means the broker's own "descendants remain" failure, which the shell now overrides) needs a Job member that survives termination; I could not produce one.

Pattern alerts: none

## Not covered

Running the installer and an actual update (see section 4), Senua T1's second meaning of exit code 1, live provider answers, Windows Explorer's icon raster, GPU release, power-loss durability, physical mouse and keyboard input (nothing needed focus, so nothing was skipped for it), and the full test suite (Ender's, not re-run). All runs used private state roots, ports, model and feed stubs; Sergei's profile, `%LOCALAPPDATA%\ComicsMeta` and his running app were not touched. Everything I started has exited; the scratch folder holds only the evidence below. Nothing was written outside `I:/AI Projects`; the personal-folder listing was not taken (the 2026-11-15 approved-root ruling supersedes it).

## Evidence

Folder: `I:/AI Projects/Temp/futaba-066/evidence/` (outside the tool's repo by instruction; copy it into the tool's `scratch/` or the promotion config before anything sweeps it).

| File | SHA-256 |
| --- | --- |
| `tray-evidence-v0.6.6.json` | `9285fbbd9dcaa06b51b8a5b5b4a462e8ff400701ca79b832f35c7be6f4a2bbc0` |
| `tray-owned-v0.6.6.json` | `ab38df4dd7dd135204f5b09e967c99841cc0830acc52d47c03baea4fa2f294e2` |
| `engine-ended-evidence-v0.6.6.json` | `b714add9a507802db5e6b052b832c0458b93cf23feb32560c144a827cafbe9bc` |
| `cites-evidence-v0.6.6.json` | `434657c43598dbe5c9e3271b455b23fdaaafc72ab85f95639f3c79cd1d14abb5` |
| `restore-evidence-v0.6.6.json` | `2ee1d30adf0dbb0ba21f4db0df8b3e1dff02504fa246cc5cc982c848a90262da` |
| `scenario-owned-v0.6.6.json` | `da3b4c57898e782e3b7da75a7a2bf871f63f8c82414363750d63e1440a29c631` |
| `package-binding-v0.6.6.json` | `5ba14d16c6ae1f22e170eff98c45229fc7458db03d4f1a58005664f266dc2af8` |
| `extraction-owned-v0.6.6.json` | `f800e888d3dfec2e91b0bb924400e474d9ead31da6530a4d908c2cc8b5460881` |
| `asar-evidence-v0.6.6.txt` | `aee86ffe816a72c27653f7dceeaf6adc77322e539452e58c116c28a7a6018af0` |
| `harness/` (11 files: observer, scenarios, probes, fixture, supervisor wrapper; digest of the sorted per-file hashes) | `bded9d1fe584b70501e52b956ec537ed205af8c51f867f101e88b04b636f28fc` |
