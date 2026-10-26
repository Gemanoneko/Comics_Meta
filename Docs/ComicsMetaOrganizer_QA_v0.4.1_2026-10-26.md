# Comics Meta Organizer v0.4.1 — QA

Futaba, 2026-10-26. Scope: what changed since 0.4.0 plus a short smoke test, per ProcessRules § Lean verification. Mid-pass, Sergei cut the scope further under the same rule: my own speed benchmark, the tooltip-overlap measurements, locale sweeps, exhaustive range sweeps and extra screenshots were dropped. Anything I had already measured before the cut is kept below and not extended. Headless only; Sergei was at the machine; no Electron, no installer run, no focus taken.

**Verdict:** GO

GO for the tested scope: the 0.4.1 engine, dashboard page and updater banner, run from the exact files inside the 0.4.1 installer, and the installer's contents and version. **Not exercised, and not claimed:** launching the packaged Electron app, the tray text and tray item 2 lock in a real tray (code read only), the tray Quit and close-button process exit, the NSIS install or upgrade, and the real in-app updater end to end (reasons under "Not run"). No Blocker, no Major. Two Minor findings and two pattern alerts below. Entry receipt `check fail` from known items only, accepted under Sergei's lean ruling.

## Build identity

| Item | Value | Confirmed by |
|---|---|---|
| Source | `main` @ `6d601de7e4454d0a15a14ce3df7deb5383e57e75`, tree `ba00e9670aa57f3ad314284fbf79dec44596ef81`, clean at the start | `git rev-parse`, `git status` |
| Installer | `dist\Comic-Metadata-Setup-0.4.1.exe`, 149,502,584 bytes | size equals `latest.yml` |
| Installer SHA-256 | `c9872a4b4edcfbcaf2ccf63ceff7b42fc6d6664117fcadc46f31b821efeac9db` | recomputed, equals Jane's hash |
| Installer SHA-512 (base64) | `y0rcRZnJ…mvDg==` | recomputed, equals `latest.yml` |
| `dist\latest.yml` SHA-256 | `f83a2f377f94065312980f72b0281dcb27319185eb35c533d3e8ee39ae0f7b5f` | recomputed, equal |
| Blockmap SHA-256 | `bad11be6ab66cc0c6a8a5177f74174477e8f6aeadc49a17dd46d59595c03a318` | recomputed, equal |
| `build\staged-manifest.json` SHA-256 | `54dcdb798eacc5f67a7f4ddb02d3048d6f9ce86fc63031f1e65151cf5cd7845b` | recomputed, equal |
| Version | installer file and product version 0.4.1; `engine\VERSION` 0.4.1; `app.asar` package.json 0.4.1; `ComicMetadata.exe` string table 0.4.1 / 0.4.1.0; the running engine answers `"version": "0.4.1"` | PE strings scanned (never executed), asar read, `/api/state` |
| Packaged contents | 534 of 534 files of `staged-manifest.json` found in the extracted installer with identical SHA-256; 0 missing; the only files under `resources\` outside the manifest are `app-update.yml`, `app.asar`, `default_app.asar` | `pkg_check.mjs` over a 7-Zip extraction (installer never executed) |
| Packaged engine = committed source | 63 engine sources: 4 byte-identical to the `6d601de` blobs, 59 identical after CRLF to LF, 0 differ; `engine\update-runtime-manifest.json` is packaging-only. Five `desktop\*.cjs` files inside `app.asar` (main, updates, graceful-stop, installer-launch, preload) identical to the blobs after CRLF to LF | same script |

**Entry receipt:** entry receipt `check fail` from known items only, accepted under Sergei's lean ruling. Ender's log (`C:\Antigravity Projects\Worktrees\Comics Meta Organizer\qa-041\logs\ender-entry.log`): `comic-metadata v0.4.1 @ 6d601de… (dirty: N) … check fail (owned check)`; 986 tests, 6 failures, 2 errors, 1 skipped, so 977 passed. I compared the eight failing test names with the 0.4.0 log (`qa-040b`): the same eight (`diff` of the sorted lists is empty); no new failure, 18 more tests than 0.4.0 (968 to 986). I did not re-run the entry check.

## Desktop Node tests (the coverage gap)

`check:shell` never ran in the entry check (skipped once `check:python` failed), so I ran the desktop tests once against the committed tree: `git archive 6d601de` into scratch, then `node --test desktop/tests/*.test.cjs`.

| Run | Result |
|---|---|
| As briefed (bare command) | 50 tests, 27 pass, **21 fail**, 2 skipped. All 21 are `assert.ok(scratch)`: the tests need `COMICS_META_TEST_SCRATCH` (an absolute folder), which `scripts/check-shell.cjs` normally sets. Not a product failure (finding QA-2). |
| With `COMICS_META_HELD_TEST=1`, `COMICS_META_TEST_SCRATCH=<absolute scratch>`, `COMICS_META_TEST_PROTECTED_ROOTS=[]` | **50 tests, 48 pass, 0 fail, 0 cancelled, 2 skipped**, 5.2 s. The two skips are the tests that need `COMICS_META_TEST_BUILDER_MODULES` and `COMICS_META_TEST_ACTUAL23_JOBROOT` (pinned harness inputs I do not have). |

The 0.4.1 tests are among the passes: park publishes a waiting phase and never re-offers Install, cancel returns to Ready and starts nothing, a failed park ends in `installer-failed` with the engine kept, only the pause timeout carries a reason and its minutes come from the cap, Try again goes straight back to Waiting and clears the reason, and the changed pause-deadline test (`PAUSE_TIMEOUT` code). No test covers `desktop/main.cjs` (the tray label and item 2).

## Changed behaviour, one check each

Page checks ran on the packaged engine's real `LocalServer` and `Handler` (packaged Python 3.14.8, temp state root, 400 comics, 4,000 history rows, no worker, no supervisor) in headless Edge through `scripts/qa/headless-browser.mjs` (leases ended, 0 left), with the real `static/shell-ui.js` and a stub desktop bridge that records actions and lets the script push shell states. `ui.py`: 41 checks, 37 pass, 4 fail; the four failures are explained under findings and "Looked at".

| Behaviour | Result | Evidence |
|---|---|---|
| No second Install offer | Pass. From the press of "Pause and install" the banner reads `Installing v0.4.1… Processing pauses first, then the app restarts.`, no buttons, no `×`, no empty actions box, not the failure look. A MutationObserver recorded every button label shown after the press: "Install and restart" never appeared. Same banner node through two stopping-window stages and `installing` (not rebuilt). Focus on the message line, which is not a tab stop. | `ui.out` |
| Locks while waiting | Pass. Check for updates, API keys and Pause & release GPU are disabled, all three with `Unavailable while updating or quitting.`; the API keys description in the accessibility tree is the same string. After the page's own 2 s poll ran, Pause was still locked, and a click sent no `/api/pause` or `/api/resume` request. Header, Pause and version badge did not move between Confirm and Waiting. | `ui.out` |
| Locks released after failure | Pass. After the timeout and after a generic launch failure, Check, API keys and Pause are enabled again with their own tooltips ("Look for a newer version now.", the keys tooltip, "Finish the current operation, then pause and release Gemma from the GPU."). | `ui.out` |
| Locks released after cancel | Pass. Cancel (state back to `ready`) shows `Update ready — v0.4.1`, focus on "Install and restart", all three controls unlocked. The updater side of cancel (`['parking','ready']`, nothing started) is a passing Node test. | `ui.out`, Node run 2 |
| Timeout message | Pass. Exactly `The installer for v0.4.1 did not start because processing did not finish pausing within 10 minutes.`, detail `The downloaded installer is kept. You can try installing again.`, buttons Try again, Open log folder, `×`, failure look, focus on Try again. Try again returns to Waiting (no second Confirm, focus on the message line, locked again). A failure with no reason shows the generic `The installer for v0.4.1 did not start.` (no stale reason). | `ui.out` |
| "This month" renders | Pass. Seven chips in the spec order, fourth `This month`, tooltip `Comics updated since the 1st of this month.`. Headline `398 comics updated this month` (equals the API total 398), dates line `October 2026`, unit `Comics per day`, chart label `Comics per day, this month. Left and right arrows read each bar.`. 31 slots, 26 bars drawn (26 days so far), none for future days. End key lands on today, tooltip `Mon, Oct 26, 2026 / 76 comics so far`; the right arrow stays on today (skips future days). | `ui.out` |
| Chips do not overlap | Pass. 1280 (client 1265): one row of 7. **640 (client 625): two rows, six chips then `Custom` alone**, no overlap, 32 px high, 8 px gaps, row step 40, inside the panel, no horizontal scroll, panel 516.2 px (476.2 + 40); with Custom selected 560.2 px. 320 CSS px (device scale 2, client 305): four rows of 2, 2, 2, 1, no overlap, 8 px gaps, step 40, inside the panel (`diag.out`). Chart starts 8 px under the unit label at every width. | `ui.out`, `diag.out` |
| A write landing during the count is counted (M1) | Pass. Race: a separate writer process (UPDATE then INSERT stamped `time.time()`, as `app.write_metadata`) wrote 201 rows in 8 s while the reader called `report()` on the real clock: 308 responses over 131 distinct revisions (10,000 to 10,166), checked after the fact against the catalog at each response's own revision and `now` (counts per bar, total, first and last update): **0 mismatches**. Fuzz: 8 seeds x 150 operations = 1,578 queries and 1,182 inserts (writes in the same bar, an earlier bar, exactly now, after now, NULL stamp, a 1998 stamp, outside the library, three path spellings; clock moved forward and set back; library switched) against a brute-force oracle: **0 mismatches**. Positive control (same fuzz on an engine whose incremental step drops the new rows): 135 mismatches in 4 seeds, so the oracle can fail. This also covers QA-3 (first and last update respect "now": rows dated after now were inserted). | `race.out`, `fuzz.out`, `fuzz-control.out` |
| m1 "Pick both dates." | Pass. `period=custom` with no dates, only `from`, or only `to`: 400 `invalid_range`, `Pick both dates.`; a missing or invalid period still says `Choose a period.`. | `m1.out` |

### Speed (QA-2), kept from before the cut, not extended

Packaged Python 3.14.8, synthetic catalog of 60,000 comics and 199,500 history rows over two years, two id orders (ids in time order, ids shuffled as in the 0.4.0 QA-2 catalog). Method: a fresh process per cold sample, 5 samples each; "after a write" is 20 rounds of one `INSERT` then `report()` in one process.

| Request | Cold, fresh process | After one write |
|---|---|---|
| All time | 0.25 to 0.30 s (both id orders) | 4.2 ms median, 6.8 max |
| Year | 0.22 to 0.27 s | 4.9 ms median |
| Custom 2000 to today | 0.26 to 0.50 s | not run |
| This month | 0.15 to 0.19 s | 3.6 ms median |
| Today / This week / Last hour | 18 to 36 ms / 18 to 34 ms / 13 to 24 ms | Today 5.7 ms |

First request after upgrading a 0.4.0 catalog (the new index is built then): 0.77 to 0.99 s. Ender's figures (cold All time 0.3 s, refresh about 5 ms) hold; 0.4.0 measured 1.4 to 2.7 s for the same requests.

## Smoke test

On the same host: `/api/state` answers 0.4.1; version badge `v0.4.1`; list `400 live files · Showing 1–100`; counters left "Checking…"; the Update statistics panel opens on Today with bars drawn (76 comics updated today in the synthetic data); no script errors. The only HTTP errors on load were `/api/backups` 400 and `/api/progress` 503, which my host causes (no worker, a library folder that does not exist). The close button and tray Quit from each screen were not exercised (no Electron launch).

## Findings

No Blocker. No Major. Status of all: open, for Jane to route.

| ID | Severity | Finding | Evidence and repro |
|---|---|---|---|
| QA-1 | Minor | **The Confirm banner is 67 px high, not the spec's 64**, so Confirm to Waiting moves the content below up **11 px, not 8** (spec § "Height and gaps": Waiting is 56 px, "content moves up 8 px"). Waiting itself is exactly 56. The header, Pause and version badge do not move. Cosmetic and not harmful; the 67 is the existing size of the Confirm and Ready banners (their 43 px buttons), unchanged in this release, so the spec number is what is off. | At 1280 px: banner heights Confirm 67, Ready 67, Waiting 56, Downloading 83, Failed 72; first panel top 268.6 to 257.6. `diag.out`; the one failed `waiting:` line in `ui.out`. |
| QA-2 | Minor | **The Node test command as briefed fails 21 of 50 tests until an isolation variable is set.** Without `COMICS_META_TEST_SCRATCH` (absolute folder) every test that makes a temp folder fails; with it, 0 fail. Two more tests skip without `COMICS_META_TEST_BUILDER_MODULES` and `COMICS_META_TEST_ACTUAL23_JOBROOT`. Anyone running the bare command (or a briefing that quotes it) will read 21 false failures. | `evidence\node-tests-run1-no-scratch-env.out` (21 failures) against `evidence\node-tests.out` (0). Suggest the briefs and `check:shell`'s header name the variables. |

### Looked at, not raised

- **Page scrolls sideways at 320 CSS px** (`scrollWidth` 465 against `clientWidth` 305). It is identical on Today, This month, This week and This year, the stats panel itself stays inside the window (panel 15 to 290, chips inside), and the `index.html` changes in this release touch only the stats tooltip CSS, the new chip and the Pause lock, so the new chip and the month view are not the cause. I did not isolate the cause (my synthetic 80-character file names in the list may be it). My `ui.py` "no horizontal scroll" criterion therefore failed twice at 320; not a 0.4.1 defect on this evidence.
- **Tooltip wrap and the tooltip covering the hovered bar at 320 px** (the 0.4.0 QA-1 fix): not measured (dropped by Sergei's cut). The CSS change is in the diff and Judy accepted the overlap in her ruling. Not re-verified.
- **No-reuse path:** one history row dated after "now" (a clock set back) makes every request re-read the period until now passes it: 0.15 to 0.39 s per request at 199,500 rows (All time 0.27 s median, Year 0.34 s median, This month 0.16 s median). Slow, not wrong.
- **Disk:** on the 199,500-row catalog the upgrade's new covering index grew `catalog.sqlite` from 78.3 MB to 104.5 MB (+26 MB), and 0.4.0's `history_timestamp` index stays beside it, unused (the Brief says so; the growth is not stated).
- **Measured against the Brief:** Year cold 0.22 to 0.27 s (Brief: 0.12 s); six kept periods held 32.5 MB by `tracemalloc` (Brief: about 23 MB, revisit trigger 50 MB). Different method and Python build; both inside the Brief's own triggers.
- A custom range with only one date, or a month request carrying a stray `from`, never comes from the page.
- QA status of the 0.4.0 findings the 0.4.1 commits address: QA-2 (speed) fixed on my numbers; QA-3 (first and last "now") fixed (fuzz oracle); QA-5 (docs) fixed (README describes the panel and "Tagged by this app"; CHANGELOG lists the relabels); QA-6 ("Pick both dates.") fixed; QA-1 (tooltip wrap) not re-measured; QA-4 (C-library edges, first affected year 2028) unchanged and latent.

## Not run, and why

| Item | Why |
|---|---|
| Launch of the packaged Electron app; tray Quit; close button from every top-level screen; process exit | Would create real windows and a tray icon while Sergei is at the machine and his own copy is running; no maintained packaged-app harness. |
| Tray tooltip `Comic Metadata — Installing update…` and tray item 2 disabled across the wait | Code read only (`desktop/main.cjs`: `installPending()` covers `parking` and `installing`; the label branch comes before the setup, uncertain and ready branches; item 2's `enabled` includes `!installPending()` and its click returns at once; `updates.on('state')` broadcasts and refreshes the tray). No test covers `main.cjs`. |
| NSIS install or upgrade; real in-app updater end to end (including the real `Updates` class driving the banner) | Never run the installer. The banner was driven with synthetic states; the updater's own transitions are the passing Node tests. |
| Lock span with the real stopping window and the 10-minute timeout | The 10 minutes is the constant `PAUSE_LIMIT_MS` (the Node test passes it through the `PAUSE_TIMEOUT` code to the banner); a real 10-minute wait was not run. |
| Sergei's real catalog and history volume | Hard limit: his profile folder is not opened. |

## Pattern alerts

Pattern alerts: 2, each with a disposition.

1. **The packaged shell is still not exercised by QA** (second build in a row, same as the 0.4.0 alert, now covering the tray label and item 2 lock too, which rest on a code read). Disposition: defer to the release pipeline's packaged smoke test for 0.4.1; re-proposed for Jane and Sergei: a committed lane for the packaged app (like QuickLaunch's lane 2) so QA does not depend on a code read.
2. **The entry check fails on the same eight known tests for the second build in a row, and its shell suite never runs** (`check:shell` is skipped once `check:python` fails, so the desktop tests were unrun in both entry logs; I closed that gap by hand this time, and the bare test command also needs an isolation variable, QA-2). Disposition: defer under Sergei's lean ruling to the existing Backlog item "Make the entry check pass cleanly"; suggested addition to that item: run the shell tests whether or not the Python ones pass.

## Process deviations (mine, disclosed)

- I started one empty `python - <<'EOF'` heredoc, which the brief forbade (a leftover in a command that also edited my script). It hung, as the stdin-python note warns. I checked its command line (`C:\Python314\python.exe -`, started when I ran the command) and stopped it by PID. Nothing else was affected.
- To find that process I listed the command lines of all `python.exe` processes, which include Sergei's installed app and other tools'. I read command lines only and stopped nothing but my own: that process and two of my own test hosts (PIDs verified by `host.py` in my scratch path) that had outlived their timers.
- Two `rm -rf` commands were refused by the delete guard, so nothing was deleted that way; scratch is removed through `studio-sweep.mjs` with explicit paths. I did not open or list anything under `%LOCALAPPDATA%\ComicsMeta`; every state root and lock folder I used is in my scratch (`COMICS_META_LOCK_DIR` set).
- The first full page pass hit connection-refused errors because my test host's own timer expired mid-run; I reran with a fresh host and the results above are from that run.

## Cleanup and evidence kept

All hosts, headless leases (0 left) and every process of mine are stopped; no listener of mine remains. Large scratch (the 7-Zip extraction, the source snapshot, six synthetic catalogs of up to 105 MB, fuzz state roots) (1.63 GB) was removed by one `studio-sweep.mjs --apply` run with each folder named by `--path`. Kept for this verdict (small), in `C:\Users\AnGeLZzZ\AppData\Local\Temp\claude\c--Antigravity-Projects-Studio-Illuminati\96c4ae72-6ee4-4c35-b5bd-1374a2290ff7\scratchpad\futaba-041\evidence\`: `node-tests.out`, `node-tests-run1-no-scratch-env.out`, `pkg_check.out`, `pe_version.out`, `perf-cold.out`, `perf-refresh.out`, `idx_sizes.out`, `fuzz.out`, `fuzz-control.out`, `race.out`, `ui.out`, `diag.out`, `diag2.out`, `m1.out`, `names-qa-040b.txt`, `names-qa-041.txt`; and the scripts in `..\scripts\` (`pkg_check.mjs`, `pe_version.mjs`, `mkcat.py`, `perf.py`, `fuzz.py`, `race.py`, `host.py`, `ui.py`, `diag.py`, `diag2.py`). The session sweep removes that folder when the session ends.

Regression verification against the fix commits: `b4f022d` (updater banner and locks), `5f41744` ("This month") and `22fcbf2` (stats fixes) checked as in the table above; no fix commit remains unchecked except the tooltip wrap (not re-measured, see "Looked at").
