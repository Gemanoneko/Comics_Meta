# Code Review — Comics Meta Organizer v0.4.1

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-26
Tool: Comics Meta Organizer (comic-metadata)
Release: v0.4.1
Commit range: 7eddddd..6d601de
Files changed: 21 files, +990 / -87 (product code: desktop/graceful-stop.cjs, desktop/main.cjs, desktop/updates.cjs, static/index.html, static/shell-ui.js, static/update-stats.js, update_stats.py)
Stand-down dimensions: none
```

---

## Summary

The range is 7 commits on top of the v0.4.0 review: the updater's new `parking` phase, a `PAUSE_TIMEOUT` code, and the Pause lock in the tray and on the dashboard (b4f022d); the "This month" period (5f41744); the stats fixes for M1, QA-1/2/3, m1 and m3 (22fcbf2); and docs plus the version bump.

I read every changed product line and traced each updater transition by hand: park, cancel, timeout, other failures, Try again, and quit during the park. I checked the M1 fix under moving and jumping clocks with a kept-versus-fresh fuzz, and gave that fuzz a positive control. I timed the covering index and the kept periods on synthetic catalogs of 200,000 and 1,000,000 rows. All of this ran in throwaway catalogs under my scratch folder. I did not open the installed app or `%LOCALAPPDATA%\ComicsMeta`.

The M1 fix is correct. The updater has no stuck state and no lock that fails to release. I found four Minor issues and nothing Critical or Major.

**Not reviewed or not run:** the desktop Node tests (Futaba is running them), real Electron behaviour, and Sergei's real catalog size. The 0.4.0 → 0.4.1 update is driven by 0.4.0's updater, as the Backlog notes. So the new parking path first runs on the update after this one.

---

## Rubric

### 1. Security

- Status: Pass. No new IPC channel, shell-out, file delete or credential. Every new string reaches the DOM through `textContent`, `title` or `dataset`: the version (semver-validated), `pauseMinutes` (a number from the main process) and the month label from `Intl`. All SQL takes bound parameters; the only concatenations are the constants `INDEX` and `ASC`/`DESC`.

### 2. Correctness & Logic

- Status: Concerns (Minor only).
- **Updater state machine: verified.**
  - Every exit from `install()` (`desktop/updates.cjs:55-81`) leaves `parking`:
    - a failed check or prepare goes to `damaged` or `installer-failed`;
    - a cancel, or a stopper already owned by a quit, goes back to `ready` (`:64`);
    - a timeout or other stopper throw goes to `installer-failed`;
    - a launch throw goes to `installer-uncertain`;
    - a successful launch goes to `installing`, then `exit()`.
  - The dashboard lock (`static/shell-ui.js:315-317`) is re-evaluated on every state broadcast. It releases on any phase other than `parking`, `installing` and `installer-uncertain`.
  - The tray item (`desktop/main.cjs:47`) and Check for updates (`shell-ui.js:330`) follow the same phases. `state.stopping` clears on the stopper's `finished` event.
  - So after a cancel or a failure, Pause & release GPU and Check for updates are always re-enabled.
  - On a timeout, the stopper sends `cancel-pause` before the failure is published, so the unlocked button shows the true pause state.
  - The two in-flight Pause paths are both guarded: the tray click (`main.cjs:50`) and the dashboard click (`static/index.html:161`).
  - The only remaining way to set a user pause during the wait is a Pause request already in flight when Pause and install is pressed (a window of milliseconds). The server does not enforce the lock. That is acceptable for a single-user shell.
  - **Quit during the park:**
    - Before the stopper starts, Quit takes the stopper and the install falls back to `ready`.
    - While the stopper runs, Quit is disabled or ignored, as in 0.4.0.
- **M1 fix: verified correct.**
  - `revision` is read before `now` (`update_stats.py:358-360`), and every query is bounded by `id <= revision`.
  - `history` has one insert site (`app.py:644`), stamps `time.time()` inside the write transaction, and has no DELETE or UPDATE.
  - The incremental read (`_Aggregate.extend`, `:257-273`) works by id range, not timestamp order. A row whose id is out of time order is still read. If it lands before the newest bar, the period is rebuilt.
  - A request that sees a revision older than the kept one recomputes without keeping (`:297-299`).
  - The cache key includes the catalog path and the live-library prefix (`:288`), so changing the library folder or catalog starts fresh.
  - **Fuzz (probe 1):**
    - 25 seeds × 120 steps, with the clock moving forward, set back by up to 3 days, and set forward by up to 40 days, and the writer stamping from the same clock.
    - All seven periods, plus two custom ranges.
    - Result: 2,878 kept-versus-fresh comparisons, 0 mismatches.
    - Positive control: the same fuzz with the "row dated after now" guard forced off gives 830 mismatches.
- **m1 [Minor] — Try again can leave the updater's internal phase different from the one it published.**
  - **Where:** `desktop/updates.cjs:84`.
  - **What happens:**
    - `retry()` sets `this.state.phase='confirm'` directly, without `patch()`, then calls `install()`.
    - If another operation is running, `install()` returns at its guard (`:56`), and the internal phase stays `confirm`, unpublished.
    - A manual Check for updates counts: it stays enabled on the `installer-failed` banner.
    - Until that check returns, the banner still reads `installer-failed`, but both Try again and the × do nothing. `dismiss()` refuses `confirm`, and a second Try again goes to `download()`.
    - When the check returns, the state heals to `ready`.
  - **Evidence (probe 4):**

    | Moment | Internal phase | Last published | × works? |
    |---|---|---|---|
    | After Try again, check in flight | `confirm` | `installer-failed` | no |
    | After the check returns | `ready` | `ready` | n/a |

  - **Fix direction:** in `retry()`, return early when `this.operation` is set before changing the phase. Or let `install()` accept `installer-failed` as an entry phase, so the state is never written outside `patch()`.

### 3. Crash / Stability Safety

- Status: Pass.
  - Every awaited call in the park is bounded except the capsule copy: engine calls 2.5 s, engine stop at the remaining cap, launch 12 s, stopper 10 min. The capsule copy is local file work, and Quit stays available during it.
  - `extend()` can stop part-way, by returning False or by throwing. Its set operations are idempotent and a lower bar forces a rebuild, so the next request heals.
  - The recursion in `_count` is one level deep: its `keep=False` branch never recurses.

### 4. Performance

- Status: Concerns (Minor only).
- **First call on a large catalog (probes 2 and 3): acceptable.** The covering index is built once, with the write lock held:

  | History rows | Index build | Writer arriving 0.3 s in waited |
  |---|---|---|
  | 200,000 | 0.74 s | 0.34 s |
  | 1,000,000 | 4.3 s | 3.28 s |

  - No writer hit "database is locked". Writers have a 30 s busy timeout, which this build would only reach at about 7 million rows.
  - With nothing competing, the first request took 0.87 s at 200,000 rows, 0.80 s of it the index.
  - Kept periods work as intended. At 200,000 rows and 60,000 comics, after 10 new writes:

    | Period | Cold | Refresh after writes |
    |---|---|---|
    | Year | 0.64 s | 0.025 s |
    | All time | 1.13 s | 0.014 s |
    | Custom from 2000 | 1.40 s cold | not measured |

  - The kept sets for six periods take about 12 MB, counting the set containers only.
  - These times are indicative: Futaba's parallel run shared the machine. My cold All time is about 4 times the Brief's figure of 0.28–0.30 s, and I did not chase the difference.
- **m2 [Minor] — one history row dated in the future turns off the incremental path for every period until real time reaches that row.**
  - **Where:** `update_stats.py:361-362` and `:372`.
  - **What happens:**
    - `keep` is one global check: is any row up to `revision` dated at or after `now`?
    - A single row written while the clock ran fast, then corrected, makes it false for every period.
    - That holds even for periods whose bars end long before the row, and it lasts until the wall clock passes that row: minutes, or a year.
    - Every 15 s refresh then re-reads the whole period. That is QA-2's cost again, with nothing logged.
    - The docstring (`:27`) presents this as a passing "clock set back" case.
  - **Evidence (probe 5):** 200,000 rows, then one row dated 400 days ahead.

    | Refresh after a write | Year | All time |
    |---|---|---|
    | Normal | 0.028 s | 0.041 s |
    | With the future row | 0.48–0.62 s | 1.34–1.96 s |

  - **Why Minor:** counts stay correct, the trigger needs the PC clock to be ahead during a verified write, and the cost is capped at 0.4.0's behaviour.
  - **Fix direction:**
    - Scope the check per period: look only for rows with `now <= timestamp < edges[-1]`. Only those would wrongly enter a kept count.
    - Leave the cheap first/last-update lookup uncached when any future row exists.
- **m3 [Minor] — the 0.4.0 index is orphaned, and the new one makes the catalog much larger.**
  - **Where:** `update_stats.py:321-326`.
  - **What happens:**
    - `history_timestamp` is no longer read, but it stays on every catalog that has it, and every history insert keeps updating it.
    - The covering index copies every path once more. At 200,000 rows, the catalog grew from 60.1 MB to 85.0 MB (+41%).
  - **Fix direction:** drop `history_timestamp` in the same one-time step that creates `history_timestamp_path`. Both need the write lock, and the drop is cheap.

### 5. State & Data Safety

- Status: Pass.
  - The endpoint still writes no rows; its one schema write is the additive index, built in autocommit.
  - The kept sets live in memory only and are capped at 8 periods (LRU).
  - The bundled CPython 3.14.8 frees `sys.intern` strings once nothing uses them, so interning does not pin memory beyond the number of distinct history paths.

### 6. Input Handling

- Status: Pass. `month` was added to the fixed `PERIODS` tuple. The m1 message fix (`update_stats.py:333-335`) separates a missing date from a bad period. The rest of the checks are unchanged from 0.4.0.

### 7. Maintainability

- Status: Pass. The direct state write in `retry()` is the one case where state changes outside `patch()`; it is logged as m1 under Correctness. The module and the updater comments explain the why and cite the spec.

### 8. Doc/Code Drift

- Status: Concerns (Minor only).
- **m4 [Minor] — the Backlog still describes the shipped updater fix as unfinished.**
  - **Where:** `Docs/ComicsMetaOrganizer_Backlog.md:45` and `:48`.
  - **What it says:** "fix in progress" and "Fix (Ender, uncommitted)". Its root-cause pointer `desktop/updates.cjs:56` is now `:59`.
  - **What matches:** the docstring (m3 from 0.4.0 is fixed), the README, the CHANGELOG, and DesktopShell spec §2/§4 and UpdateStats Addendum 2: Waiting text, the lock, focus, the timeout copy, the month headline and dates line.

### 9. Build & Release Hygiene

- Status: Pass.
  - `VERSION`, `package.json` and both `package-lock.json` entries read 0.4.1, and the CHANGELOG has a 0.4.1 entry.
  - No new files, dependencies or secrets.
  - The entry receipt names `v0.4.1 @ 6d601de`, not dirty. It shows 986 tests: 977 pass, 6 fail, 2 error and 1 is skipped. All 8 failures and errors are in the known environment set. None are in `test_update_stats*` or `test_shell_ui_dom`.

---

## Patterns

Both stats findings in a row (0.4.0 M1, 0.4.1 m2) come from the same thing: the kept stats answer depends on the wall clock, which the cache cannot see. The fix is correct now, but the guard is one global switch.

Still open from the v0.4.0 review: m2 (Windows applies today's daylight-saving rules to past years). It was outside this range and is not counted here.

---

## Evidence

Scripts are in `C:\Users\AnGeLZzZ\AppData\Local\Temp\claude\c--Antigravity-Projects-Studio-Illuminati\96c4ae72-6ee4-4c35-b5bd-1374a2290ff7\scratchpad\senua-041\`. Their throwaway catalogs were deleted after the run, and each script rebuilds its own.

| # | Script | Shows |
|---|---|---|
| 1 | `probe_fuzz_clock.py`, `probe_fuzz_control.py` | M1 fix: 2,878 kept-versus-fresh comparisons with a moving and jumping clock, 0 mismatches. Control with the guard off: 830 mismatches. |
| 2 | `probe_large.py`, `probe_profile_first.py` | Cold and warm period times, catalog size before and after the index, kept-set size. First request with nothing competing: 0.87 s. |
| 3 | `probe_index_lock.py` | Index build and writer wait at 200,000 and 1,000,000 rows. |
| 4 | `probe_retry_divergence.cjs` | m1: internal `confirm` against published `installer-failed`; × swallowed until the check returns. |
| 5 | `probe_future_row.py` | m2: refresh cost before and after one future-dated row. |

---

## Verdict

- Total Critical: 0
- Total Major: 0
- Total Minor: 4 (m1, m2, m3, m4)

**Verdict:** RELEASE CLEAR

The safety floor is intact: no machine harm, no secret exposure, and no change to the repository's history. The Minor findings are logged for Ender's next cycle. This report covers construction only, and Futaba's behaviour verdict is separate.
