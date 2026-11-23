# Comics Meta Organizer 0.6.10 packaged QA — 2026-11-23 (second build)

**Verdict:** GO

**Tray-smoke verdict: GO**

This report is for the rebuilt 0.6.10 at source commit `7eacdff5962b216a765d837e968cb97208ec3d70`. The earlier report, `ComicsMetaOrganizer_TrayQA_v0.6.10_2026-11-22.md`, stays as the record of the retired `86425b1` build; its blocker (no tray in a private QA profile) is fixed here and verified. All three parts passed: identity, the private packaged smoke with native tray Quit, and the Unicode file-name check with its positive control. Lean verification: build confirmed by hash, the suites were not re-run.

Which report counts: both 0.6.10 reports stay in `Docs/`. The release precondition check takes the later-dated one. Checked with its own selection helper: latest is this file (GO), older is the 2026-11-22 file (NO-GO).

Interruption: the session was paused once by a usage limit, after every step below had finished and this report was written. On resuming (09:33:47) I checked the state before anything else: no process of mine, no private desktop left, Explorer's tray records identical to the pre-launch snapshot. The packaged app had been launched with `"tray": true` exactly once, through the helper, whose record says `trayRecordsUnchanged: true`. No step had been cut off part-way, so nothing was cleared or repeated; what remained was the gate replay against this report, the parser check and the cleanup.

## 1. Candidate identity — pass

Recomputed from the files on disk and compared with the brief, the build record and the builder log.

| File | SHA-256 (measured) | Matches |
| --- | --- | --- |
| `Comic-Metadata-Setup-0.6.10.exe` (150096422 bytes) | `004471bd6a58dbd8f0d0b37f277bd5363a6493a56408dd3d3f2ea521ae7b5be4` | brief, build receipt, builder log |
| `latest.yml` (360 bytes) | `35588d5997e0c50f4968c6b270c50a11425c8930389cb13c02b39546f2440be5` | brief, builder log |
| `Comic-Metadata-Setup-0.6.10.exe.blockmap` | `1869184f2cf228c60428167495724c17489ff03fb973e3fbff5bd445acc27654` | builder log |
| `build-owned-v0.6.10.json` | `003c65287bc0f8b335a293d8b519bbd10e444835052d5f27736678dc47bbd034` | builder log |
| `check-python-owned.json` | `63ff286533c00fe4e2311453efeb7e2e17d85df89b6e0d6871527bc2b9897779` | builder log |
| `check-shell-owned.json` | `9f3f679c3dfe0dbfcd9ccfb8f397fc75bebeb17b168a49a05fc509d3119fe16d` | builder log |
| `source-manifest-7eacdff.json` | `7743383944d90716bc7c1fa1d454e6462e9ae213c995834434a8ff696f5d5266` | build record |
| `source-7eacdff.tar` | `fd647e1cdceaa90d5e67061b4989d33a5afea6f2553b9e5107e9e55508156647` | build record |
| `ComicMetadata.exe` (extracted) | `895e3b6e135aa09811dd89e33b7a98d3d74ebd8e9433ce6d9ad444f2a0cea173` | two-file and full extraction, and the running app |
| `resources/app.asar` (extracted) | `53bc7902608c306a1a3e41b26760f75fa6e6b8de1ebc3136a891bb003dec9d32` | two-file and full extraction, the running app, builder log |

- The `rc-0610b` worktree is at the source commit and clean. `latest.yml` names version 0.6.10 and the installer's size.
- Builder check record (last record line of `ender-entry.log`): source `7eacdff…`, not dirty. Python: `Ran 1396 tests`, `OK (skipped=117)`, so 1279 passed, 0 failed. Shell: 129 tests, 128 pass, 0 fail, 1 skipped. Both exit 0 under the owned supervisor with a closed, empty Job. The build-record check reports 18 of 18.
- Static binding, measured here: the pinned 7za (`b0cfdeaf…`, equal to `toolchain-lock.json`) extracted the installer under a private Job, twice. Whole payload: 623 files, tree digest `22738d538ee60b3f29c884265fe7b25b54dae0e1ea81f6e5c25785ed12cb0d38`. Packaged engine files: 75 of 75 equal to the source manifest (one generated file has no source entry). Packaged `desktop/` files, read with Ender's corrected check on the installer's own `app.asar`: 34 of 34 equal, the eight tray PNGs among them. The shipped `main.cjs` carries `if(!qa||qaPolicy.tray===true)`; the `86425b1` form is absent.

## 2. Private packaged smoke with native tray Quit — pass

Route: the 0.6.9 release's `promotion-smoke`, repointed, with the same `observer.cjs` byte for byte (`138af862…`). Two changes, as `7eacdff` requires: the QA policy carries `"tray": true` before hashing, and the app is started only through `scripts/qa/private-desktop.py run` (the copy at `7eacdff`), on a separate Win32 desktop that has no shell tray. The unmodified payload ran from `I:\AI Projects\Temp\cmo-qa0610b\extract` (39 characters), in a private QA profile with private state, locks, ports and stubs, all under a private kill-on-close Job. One attempt, 2026-11-23 09:16:21 to 09:16:43 local.

The items that were unproven until this run:

| Item | Outcome |
| --- | --- |
| Electron's `Tray` when Explorer cannot be reached | Works. `new Tray` did not throw. A tray object exists, with Electron's own tray host window on the private desktop. |
| The observer's tray hooks | Saw everything: 7 images, 7 tooltips, 7 menus. Icon sequence processing, processing, processing, paused, processing; each bitmap exact at both sizes. |
| Tray Pause and Resume | Real menu callbacks. Pause gave the paused icon and "Pausing. Finishing the current operation."; Resume gave the processing icon back. |
| Native tray Quit | The real enabled `&Quit` item. Engine exit 0, then main exit 0, 3.4 s after the click. |
| Complete process closure | Engine port closed, no claim left, none of the recorded processes alive at 3 s and 12 s. Owned Job: closed, not forced, not timed out, 0 active, accounting complete, 0 incomplete queries of 1411. |
| Offscreen window on a never-shown desktop | Setup screen and dashboard loaded. Window invisible, unfocused, offscreen. 28 of 28 guards installed, 0 violations, 0 unexpected child processes. |
| GPU process and sandboxed children | One GPU process, sandboxed, the same one from ready to Quit; GPU compositing enabled. Renderer sandboxed. No renderer lost. |
| The helper under my owned Job | Works (its own Job nested inside mine). Its check passed from inside the desktop; it released its Job when the app exited by itself; exit code 0 passed through. |
| Bitdefender | No visible reaction. Nothing was blocked, ended or removed in any run. |
| Sergei's desktop and Explorer's tray records | 0 app windows on his desktop (14 on the private one). Input desktop unchanged, foreground window unchanged. The helper's `trayRecordsUnchanged` is true and its record-state digest is identical before and after. |

Also seen: the app reported 0.6.10 (shell, engine, `/api/state`, and the dashboard's version row). Private engine owned and answering 200. Payload after the run: 623 files, the same tree digest, no `__pycache__`.

Promotion-shaped evidence, in `I:\AI Projects\Temp\cmo-qa0610b\evidence\` (the paths inside these files are absolute, so the folder must stay where it is until the release is promoted):

| File | SHA-256 |
| --- | --- |
| `tray-evidence-v0.6.10-promotion.json` | `dc000fc7351736dbdb733c5e7f847eaceaeabead44a9fa024c0c8d70fd7cb25c` |
| `tray-owned-v0.6.10-promotion.json` | `2c4da8353e2753324d7dc676086d351376333b286d93861756d5b7a46e4ec4a8` |
| `package-binding-v0.6.10-promotion.json` | `6e0d3ad1021daab2e812e38f1d789a6da5cdf9f2b42f9cdbc164d10f31bec9d0` |
| `extraction-owned-v0.6.10-promotion.json` | `2ea7a46fd59eb5d02243a4f8d1e3d74dd6df081b7334722a44b2d65e100d19d2` |
| `asar-evidence-v0.6.10-promotion.txt` | `a2bb9cd5e390f5f9dc69f0f27e7e7b9e4ba1657e33b09b2f5fe57c589266193d` |

The smoke evidence names installer `004471bd…5be4`, feed `35588d59…0be5`, exe `895e3b6e…a173`, asar `53bc7902…9d32` and source manifest `77433839…5266` (all in full in the table above). A replay of `create-local-promotion.mjs` lines 57 to 63 over these files passes, and 12 of 12 negative controls are rejected. The eight tray PNGs the running app read equal the source manifest.

## 3. The delta: Unicode file names on this cp1251 host — pass

Form of the check: **the full thing.** A real ordinary pass of the packaged app, driven by the app itself, in a private QA profile, offline. No tray was needed, so these runs carried no `"tray"` flag and started the app directly, offscreen. The fixture library held five tiny CBZs: two plain names, `Youth² 001 (2021).cbz`, `Café Noir 001 (2021).cbz` and `東京 Tales 001 (2021).cbz`, each with a matching series in a synthetic offline index. Three of the names cannot be encoded in cp1251. The host's Python without the variable reports `cp1251`, UTF-8 mode 0.

| Run | Payload and launch | Result |
| --- | --- | --- |
| Candidate | The unmodified 0.6.10 payload | **5 of 5 written**, the "²", "é" and CJK names included. One batch, state `complete`. No "Stopped" card. No `charmap` or traceback line in `engine.log`. 4.4 s. |
| Positive control | A labelled control copy: the 0.6.9 release's engine files, and the broker started as 0.6.9 started it (the harness removes `PYTHONUTF8` from the shell's engine launch, the one key 0.6.10 added) | **Fails as 0.6.9 did.** The batch stopped after the first Unicode name: `'charmap' codec can't encode character '\xe9' in position 3: character maps to <undefined>`. Batch state `needs_attention`. The dashboard shows "Stopped: this batch hit an error." 1 of 5 written. |
| 0.6.9 engine, shipped launch | The same control copy under the shell's own unchanged 0.6.10 launch | **5 of 5 written.** The 0.6.9 engine still prints each name to the worker's discarded output, so this passing shows by its effect that the real worker runs in UTF-8 mode. |

UTF-8 mode, measured on the candidate:

- The shell hands `PYTHONUTF8=1` to the broker launch (read at the real spawn call), with `-B` only.
- All four real engine processes carry it in their own environment and are started with `-B` only, no `-I` or `-E`: `engine_host.py`, `app.py`, `worker.py`, `browser_worker.py`.
- The packaged Python, started the same way from its packaged folder: UTF-8 mode 1, output encoding utf-8, all three names print. The same start without the variable: UTF-8 mode 0, cp1251, and the print of the "²" name raises `UnicodeEncodeError: 'charmap' codec can't encode character '\xb2' in position 5` — the reported error. With `-I` added the variable is ignored, as the code comment warns.

The control copy's engine equals the 0.6.9 release byte for byte (74 of 75 files against the 0.6.9 source manifest; only `VERSION` was left at 0.6.10 so the shell would start it). Each of the three runs ended through the app's own Quit (File > Exit) with exit 0, the engine port closed, no claim and no process left, and an owned Job closed and empty.

Limits, stated plainly:

- The app-level control stopped on the "é" name, which sorts first; the "²" name was never reached there. The "²" error text itself is reproduced at the runtime level above, and the candidate wrote the "²" comic.
- Nothing in the pass sent a file name to `engine.log`, and the write-ledger backfill did not fail, so those two changelog lines rest on the builder's unit tests and on the runtime probe (UTF-8 bytes reach a file stream).

## Explorer tray records (registry) — unchanged

My own read-only snapshot of `HKCU\Control Panel\NotifyIconSettings`, subkey names and count:

| When | Subkeys | SHA-256 of the sorted names |
| --- | ---: | --- |
| Before the first launch (09:11:27) | 157 | `684d270c74a57ba8da85f0ea4b32719a9b54b4558192e252972355e9c0b4ab5d` |
| After the tray smoke | 157 | identical |
| After the last launch (09:25:43) | 157 | identical |
| On resuming after the pause (09:33:47) | 157 | identical |

No new record. One record names Sergei's installed `ComicMetadata.exe` (his own, there before); none names a QA path. The helper's own digest of the records' state is the same before and after. No private `cmo-qa-*` desktop is left in the window station.

## Findings

No Blocker. No Major.

- **Minor. The Explorer side of the tray is no longer exercised by any private smoke.** On the private desktop there is no shell tray, so Windows cannot show the icon there. What was exercised is the app's side: the tray object, the four icon states, the menu callbacks and Quit. The tray line is the same one the installed app runs. Suggested for the manual update check: one glance that the icon is in the notification area and its right-click menu shows Open, Pause and Quit. Status: open, deferred to the manual update.
- **Minor. Only convention keeps `"tray": true` off Sergei's own desktop.** The app honours the flag in any valid QA policy and does not check where it runs. My harness refuses the flag outside the helper, but the harness is not in the repository. Status: logged.
- **Minor. Windows on the private desktop.** Two Windows input-indicator windows owned by the app process carry the visible flag there, and the engine broker has a hidden console window. That desktop never has the screen and Sergei's desktop held none of them. Recorded so nobody is surprised by the listing.
- **Minor.** The builder's `check-python-owned.json` again shows 9 incomplete process-accounting samples (of 7423). The final accounting is complete and zero. Same as the first build.
- **Minor (limits of this pass).** See the two limits under section 3.

Pattern alerts: one, carried from the 2026-11-22 report.

- **The release smoke lives outside the repository.** `7eacdff` put the desktop helper and a unit test for the QA tray branch into the repo, which closes the gap that hid the first build's blocker from the suite. The smoke harness itself is still copied from the previous evidence archive and changed by hand: three more hand changes this time (the policy flag, the helper launch, the app PID from the helper's record). No disposition has been recorded yet. Recommended: **fix**; the owner decides how.

## Not done, and why

- Quit from the startup, setup and failure screens, and the window-close-keeps-tray check: not re-run. That code is unchanged since 0.6.9 and this pass tests only what changed. Tray Quit ran from the dashboard; File > Exit ran from the dashboard three times.
- Tray icon as Explorer shows it: not possible on the private desktop (first Minor).
- Anything needing focus or the mouse: none attempted. Installed-update check: deferred to a manual update, as before.
- No installer was run. Sergei's installed app (four `ComicMetadata.exe` processes, PIDs 20188, 24052, 5880, 7736, identical before and after), `%LOCALAPPDATA%\ComicsMeta`, port 8765 and `Y:\Comix` were not touched. No external-source traffic: every source off except the synthetic offline index, no keys in any profile.

## Personal-folder check (list only)

The builder's log carries no personal-folder listing (it is an owned-supervisor record, not an entry-check receipt), so there is none to copy. My own list-only look: nothing changed in the real `%APPDATA%\Comic Metadata` during this pass, and the redirected private `appdata` and `localappdata` folders stayed empty. One thing I cannot attribute: the real `%APPDATA%` folder itself shows a change at 09:16:16, five seconds before my first app launch. No entry of ours is in it, repeating my commands of that minute does not move the time, and it did not move during any launch. Nothing was deleted or moved there.

## Evidence kept

`I:\AI Projects\Temp\cmo-qa0610b\evidence\` (61 files, about 530 KB): the five promotion files above, `smoke/` (scenario result, the helper's records, events), `binding/` (extraction records, tree digests before and after, engine and asar comparisons), `delta/` (the three pass results with their owned records, the runtime probe, the control copy's label and comparisons), `registry/` (the four snapshots) and `harness/`.

| File | SHA-256 |
| --- | --- |
| `smoke/sPromo.result.json` | `19ec078021f025dd6ca6321e665806fdb2ac6d4bac00fd06437bd7e914203e4e` |
| `smoke/sPromo.desktop-record.json` | `8fb3c9b7c81fafd850e1c7ad1d48c6a9a914009bc9d4772d2a6bddd118004eff` |
| `delta/dCand.result.json` | `e9b65bdf67db9e763cdca65ca013c93c52e4ca4b72c034fe8ea3591a196a16c6` |
| `delta/dCtl.result.json` | `e226d03bea0969b53627c9233bea94e2cedd19a289ec6f4f8481cc9631eef29e` |
| `delta/dE69u.result.json` | `e342b347ae92fd7ae6912de088272ca6013362362baadb9f7c7cf561389b508b` |
| `delta/dProbe.result.json` | `dbcdf8009db6dc608d9c18171187104dd669c1e112eae16ba47017bec58bafac` |
| `harness/smoke0610b.mjs` | `4ddded1dc3cc0fc3468aafa5edbf1d95d26acecad843a3c20e21598a422edfc5` |
| `harness/delta0610b.mjs` | `a4e4cda58db7c35fea75e73e1a3db35b29354f19b12f7178fe32c9bec03cee06` |
| `harness/lib.mjs` | `69eed3f9b03bb843e968b42c89e1dd5e2f2fbd0d7aa467a7cc33970abbaa9992` |
| `harness/observer.cjs` | `138af86201edd7379d716bc6aa556de503bba68877bfc24ac009685b64e90d30` |

The first run's evidence stays in `I:\AI Projects\Temp\cmo-qa0610\evidence\`.

## Cleanup

Removed through the studio sweep: the extracted payload, the control copy, the run scratch, the private QA profiles with their fixture libraries, and my unpacked copy of the 0.6.9 evidence ZIP. The `rc-0610b` worktree's `dist/`, `I:\AI Projects\Temp\cmo-rc0610b` and the pinned Node are unchanged. No process of mine is running.
