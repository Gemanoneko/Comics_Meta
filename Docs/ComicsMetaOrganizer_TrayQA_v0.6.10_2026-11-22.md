# Comics Meta Organizer 0.6.10 packaged QA — 2026-11-22

**Verdict:** NO-GO

**Tray-smoke verdict: NO-GO**

The pass stopped at the private packaged smoke, as the brief's failure rule requires. The candidate is the build Ender handed over (hashes match). It starts, its dashboard answers and it shows 0.6.10. But the packaged 0.6.10 app creates **no tray in a private QA profile**, so the release's required check — native tray Quit with complete process closure — cannot be run on this build, and the evidence the promotion step demands cannot be produced honestly. The Unicode delta check (the actual 0.6.10 fix) was **not run**.

Source commit `86425b131e7b8b341b52ccc994fb433940beef69`. Lean verification: build confirmed by hash, the suites were not re-run.

## 1. Candidate identity — pass

Recomputed from the files on disk and compared with the brief, the build record and the builder log.

| File | SHA-256 (measured) | Matches |
| --- | --- | --- |
| `Comic-Metadata-Setup-0.6.10.exe` (150096264 bytes) | `51db415c3a76159cbdac4372f81b0d88b805f84c1b63e66a7ea954c8e0cb2ffd` | brief, build receipt, builder log |
| `latest.yml` (360 bytes) | `69f13025347fe9f262288959e0d352b4dab6f5f5963e40c25d0a9cceaf3c2ac2` | brief, builder log |
| `Comic-Metadata-Setup-0.6.10.exe.blockmap` | `a30f7bc4e096e827c0f4bd256866567bd77ccdeb49af947941a20acf718066e3` | builder log |
| `build-owned-v0.6.10.json` | `fcd7044ac5b2574357aaa57fbfe849b8877fd404826d3f75005cd2d2fcdcae80` | builder log |
| `check-python-owned.json` | `86395d8e7720ed813680682a6db14abb95b52ade266aae268ea1ab8a4c0f0a10` | builder log |
| `check-shell-owned.json` | `b5fb8284a2243374ac9b4f24f7c5f058787b86ca09ede676aa6611aa62eb96c0` | builder log |
| `source-manifest-86425b1.json` | `4a903119bd79795499ed3efbaa8f3c7ca19a828b09146791119f9b7f3a464581` | build record |
| `source-86425b1.tar` | `745ba7dec9ce7803a316fc2d30a1f2d3f0ed8f2589297bd18714f8e35f120c3a` | build record |
| `ComicMetadata.exe` (extracted) | `492872071df5d898a390764e60f018c8c260ded3edd229401c4bcd91e0aa33a9` | two-file and full extraction, and the running app |
| `resources/app.asar` (extracted) | `6314cb8a421ebf3c9d52cbabd990da6fd63af8db5b40414d61488643bb5ac926` | two-file and full extraction, and the running app |

- The `rc-0610` worktree is at the source commit and clean. `latest.yml` names version 0.6.10 and the installer's size.
- Builder check record (last line of `ender-entry.log`, standing in for the receipt line as in 0.6.9): source `86425b1…`, not dirty. Python: `Ran 1396 tests`, `OK (skipped=117)`, so 1279 passed, 0 failed. Shell: 125 tests, 123 pass, 0 fail, 2 skipped. Both exit 0 under the owned supervisor with a closed, empty Job. The build-record check reports 18 of 18.
- Static binding, measured here: the pinned 7za (`b0cfdeaf…`, equal to `toolchain-lock.json`) extracted the installer under a private Job, twice. Whole payload: 623 files, tree digest `11f3a673db5f9e1e824d16898dd5df6e14a160c9bc3e1b79d9f88bb80fbb48f0`. Packaged engine files: 75 of 75 equal to the source manifest (one generated file, `update-runtime-manifest.json`, has no source entry). Packaged `desktop/` code: 16 files, 0 differing from the commit. The eight packaged tray PNGs equal the source manifest.

## 2. Private packaged smoke — failed, stopped

Route: the 0.6.9 release's route, repointed only (the `promotion-smoke` scenario and library of the 0.6.9 harness, the same `observer.cjs` byte for byte, sha256 `138af862…`). The unmodified payload was extracted to `I:\AI Projects\Temp\cmo-qa0610\extract` (38 characters), launched in a private QA profile with private state, locks, ports, feed and model stubs, under a private kill-on-close Job. One attempt, 2026-11-22 23:24:51 to 23:25:04 local.

What passed before the stop:

- The packaged app started. `app.getVersion()` 0.6.10, packaged true, running from the extracted folder.
- Private engine owned and answering (`/api/shell/status` 200, engine version 0.6.10, phase ready), on a private port.
- Dashboard loaded from the private engine, service ready, `/api/state` 200 with version 0.6.10. The dashboard's version row reads "v0.6.10 API keys Check for updates".
- The window stayed invisible, unfocused and offscreen. 28 of 28 guards installed, 0 violations, 0 unexpected child processes. Model stub: 0 requests. No source traffic (all sources off, empty library, no keys in the profile).

Where it failed:

- **No tray exists.** Live `Tray` objects in the main process: **0** (the same query finds 2 `BrowserWindow` objects, so the query works). No tray image, tooltip or context menu was ever set, although the observer's three tray hooks were installed. Tray context menu: none.
- **Tray Quit could not be requested.** The one request, the same call the 0.6.9 smoke made, found no menu item (`found: false`). Eight seconds later the app was still running and its engine still answered 200.
- I stopped there. The app was ended by the harness (main process terminated), not by a Quit. Nothing was quit another way to manufacture a closure result.

Positive control: the same observer on 0.6.9 recorded five tray images, an enabled Quit, "actual tray Quit requested" and exit 0 with nothing left (`qa/fPromo.promotion.json` in the committed 0.6.9 evidence ZIP, sha256 `599be6ca…`).

Cause, as far as QA can see it: commit `68ad095` (2026-11-20, "Keep development and QA writes under the approved projects root") changed `desktop/main.cjs` so the tray is created only outside QA mode (`if(!qa)try{…tray=new Tray(icon)…}`), with the comment "QA profiles are offscreen. Windows Sandbox exercises the ordinary installed shell." That line is in the shipped `app.asar`. In the same file a window close with no tray now quits the app, so the QA profile no longer behaves like the installed app on close either. 0.6.10 is the first release that carries this.

Closure and payload after the stop (not a Quit result):

- Owned Job record: closed, not forced, not timed out, 0 active, 0 assigned, accounting complete, 0 incomplete queries out of 887. Engine broker gone, engine port refused.
- No process with an image under my private folder remained (read-only image-path check of every process I may query).
- Payload after the run: 623 files, the same tree digest, line for line. No `__pycache__`.
- Three stale claim files stayed in the private locks folder, as expected when the main process is terminated rather than quit. They went with the private profile.

Promotion-shaped smoke evidence: **not produced.** `create-local-promotion.mjs` (lines 57 and 62) requires the tray Quit request, the three tray icon states read from a real tray and exit 0 after that Quit. None of these can be observed on this build in a private profile. No `tray-evidence`, `tray-owned`, `package-binding` or `asar-evidence` promotion files exist for 0.6.10.

## 3. The delta (Unicode file names on this cp1251 host) — not run

Stopped before this step, under the brief's rule that any blocker ends the pass. The fix is therefore **unverified by QA on the packaged build**. No fixture library was created. No positive control was run.

Seen in passing, and not a substitute for the check: the shipped `desktop/engine.cjs` starts the broker with `PYTHONUTF8:'1'` and only `-B` (no `-I`, no `-E`); the packaged engine files equal the commit. The host's ANSI code page is cp1251 (OEM 866); the packaged Python is 3.14.8.

## Findings

- **Blocker. The release's required smoke cannot be run on this build.** The packaged 0.6.10 app creates no tray in a private QA profile, so native tray Quit, tray Pause and Resume and the four tray icon states cannot be exercised, and complete closure after a tray Quit cannot be shown. The tray's Quit is this tool's recorded close invariant (Brief, "Window close"), and the Brief's Release line requires this exact smoke. It is unverified on these bytes. The promotion step will refuse for lack of evidence. Repro: launch the extracted 0.6.10 payload with `COMICS_META_QA=1` and a valid private policy; read the tray menu. The other way to see the tray, the ordinary (non-QA) profile, is not usable on this machine while Sergei's app runs: it binds port 8765 and shows its window. Status: open.
- **Major. The fix this release exists for is unverified by QA.** Item 3 was not run (see section 3). Status: open, waits on the blocker.
- **Major. The release contract, the gate and the build disagree.** Brief line 60 and `create-local-promotion.mjs` require a native tray Quit in a private packaged smoke. The build's own comment sends tray testing to Windows Sandbox, which Sergei ruled on 2026-11-14 is not required for normal releases. The change arrived in a commit titled as a write-location cleanup, with no changelog entry, no Brief row and no test that names it. Status: open, needs an owner decision.
- **Minor.** The builder's `check-python-owned.json` shows 9 incomplete process-accounting samples out of 11519 during the run. The final accounting is complete and zero, and the gate does not read the samples. Recorded for the record only.
- **Minor (my own tooling).** The inherited static `asar-check.cjs` silently skips the tray PNGs (it reports "16 files compared" and lists none). I read the eight PNGs with a separate reader. The check that matters for the gate has always been the running app's own read, which did not happen this time.

Pattern alerts: one.

- **A product change broke the release smoke and nobody found out until release QA.** The tray-smoke harness is not in the repository. Each release it is copied out of the previous release's evidence ZIP and repointed by hand, so nothing ran it against `68ad095` when that commit changed the shell. The gate's expectations live in the repo; the only thing that can satisfy them does not. Disposition recommended: **fix** — the owner decides how (for example, keep the smoke where a shell change runs into it, or settle the contract first). Until then the same surprise can recur with any shell change.

## Not done, and why

- Native tray Quit, tray Pause/Resume, tray icon states, closure after Quit: not possible on this build (blocker).
- Close from each top-level screen: not attempted after the stop. Note the QA profile's close now quits, unlike the installed app.
- The Unicode delta and its positive control: stopped before it.
- Promotion-shaped evidence: not produced.
- Anything needing focus or the mouse: none attempted. Installed-update check: deferred to a manual update, as before.
- No installer was run. Sergei's installed app (four `ComicMetadata.exe` processes, the same PIDs before and after), `%LOCALAPPDATA%\ComicsMeta`, port 8765 and `Y:\Comix` were not touched.

## Personal-folder check (list only)

The builder's log carries no personal-folder listing (it is an owned-supervisor record, not an entry-check receipt), so there is none to copy. My own list-only look: during my run nothing changed at the top level of the real `%APPDATA%` or `%LOCALAPPDATA%` that belongs to this pass. The real `%APPDATA%\Comic Metadata` folder last changed at 23:14:14 to 23:14:17 (`window.json`, `DIPS-wal`), ten minutes before my app started at 23:24:51; that is Sergei's running app, not this pass. The redirected private `appdata` and `localappdata` folders stayed empty. Nothing was deleted or moved there.

## Evidence kept

`I:\AI Projects\Temp\cmo-qa0610\evidence\` (26 files, about 231 KB):

| File | SHA-256 |
| --- | --- |
| `smoke/sPromo.result.json` | `3f0feb737245faf4db00856a6450018508607359e3ea91e77df0b5832ef57e36` |
| `smoke/sPromo.owned.json` | `eff77a71c64421146f815f399555950405afe81cc2da9a40d7e00a489722f5a5` |
| `smoke/sPromo.events.jsonl` | `033441e840ad3c656c0b49a5decbb42f1dc5541bcaf82f13f7daf5544e0d9726` |
| `binding/extraction-two-owned.json` | `5ce18d682cb0a9d550f7f88a2f907786b4adcd33481aff36f0bf87b4c604007c` |
| `binding/extraction-full-owned.json` | `e56704ccfb35a1f4d641752099bfb0bf0e69603485f39a0d10800e9900d6a71d` |
| `binding/tree-before.lines.txt` | `11f3a673db5f9e1e824d16898dd5df6e14a160c9bc3e1b79d9f88bb80fbb48f0` |
| `binding/asar-static.txt` | `472a90b3b54332092e8c7bb2934f77b416fc25fe49eae466bbef5ad25d3b1cb2` |
| `binding/asar-tray-png-static.txt` | `e258146f1091255e01c94221324cd0ca467aca43d817cc1978b61579d8d3ac0d` |
| `binding/engine-vs-manifest.json` | `5389acff6b50804a47bedd2395083db4a429077e0986e0febe938232530ecbef` |
| `harness/smoke0610.mjs` | `71c6a35bf734cdbf987c24b6e6caaa650690fa46fb597b1970897c78eaca47d7` |
| `harness/lib.mjs` | `6bb51aae71a7482abef4cb2f9d4c0448c2c0d40cab395d0b0f308ea56375ed08` |
| `harness/observer.cjs` | `138af86201edd7379d716bc6aa556de503bba68877bfc24ac009685b64e90d30` |

Also there: the process lists before and after, the own-process check, the tree digests before and after, and the small harness helpers.

## Cleanup

Removed through the studio sweep: my extracted payload, the two-file extraction and run scratch, the private QA profile/state/library, and my unpacked copy of the 0.6.9 evidence ZIP — 780 files, 743.04 MB. The `rc-0610` worktree's `dist/` and `I:\AI Projects\Temp\cmo-rc0610` are unchanged (hashes re-measured after the pass; the pinned Node is in place). No process of mine is running.
