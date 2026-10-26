# Code Review — Comics Meta Organizer v0.4.0

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-26
Tool: Comics Meta Organizer
Release: v0.4.0
Commit range: e61c9baf958a2f117a081e1ba10e8a8a86547e9c..dd019cb3f267e9c85864692d901e1138bb887eca
Files changed: 17 files, +2417 / -12 (code, tests and version: 10 files, +1591 / -8)
Stand-down dimensions: none
```

**Where the range starts.** The v0.3.0 review certified a frozen candidate, and that candidate was committed as `e61c9ba`. The working-tree SHA-256 of all seven pinned files at `dd019cb` still matches the table in that report, so `e61c9ba` is the right start.

**Commits in the range** (from `git log e61c9ba..dd019cb`):
- `a0897f6`, `24cc3b9`, `91543bd`, `2bc7947`, `bcfb387`, `a71795b`, `12f5d82`: documentation only.
- `ab93d8e`: the feature.
- `dd019cb`: the version bump.

**Tree state.** HEAD is `dd019cb`. While this review ran, the working tree picked up one uncommitted change that I did not make: 12 added lines in `Docs/ComicsMetaOrganizer_Backlog.md`. It is documentation, it is outside the range, and it is not reviewed here.

## Summary

v0.4.0 adds a read-only `GET /api/update-stats` endpoint and an "Update statistics" panel.

**The endpoint** (`update_stats.py`):
- counts distinct comics per bar and per period from `history`;
- keys each comic by `coverage_priority.path_key` and counts only comics inside the live library;
- builds bar edges in local time with the C library's `mktime` and `localtime`;
- picks the finest bar unit that fits in 60 bars;
- adds a `history_timestamp` index once per process;
- caches results by `MAX(history.id)`.

**The page** (`static/update-stats.js`) draws inline SVG and polls every 15 s while the period ends now.

I read every changed line. I also checked the endpoint's call paths:
- `app.db()`, `app.live_root()`, `coverage_priority.path_key`;
- the GET handler's catch-all error path;
- the page's `request()` helper.

Four targeted probes back the findings. No full suite was run.
1. A test-fixture repro of the cache race.
2. A check of Windows C-library time-zone behaviour.
3. A SQLite lock check on the statements `app.db()` runs.
4. A timing of the index build on 200,000 rows.

## Rubric

### 1. Security

- Status: Pass.
- **SQL.** Every value is a bound parameter. The only concatenation is `'ORDER BY timestamp ' + order`, where `order` is the code literal `ASC` or `DESC` (`update_stats.py:186`).
- **XSS.** `update-stats.js` has no `innerHTML`, `insertAdjacentHTML`, `eval` or `Function` sink. Every string reaches the DOM through `textContent` or `setAttribute`, including the server's error text. No path ever reaches the page, because the response carries only epochs, counts and constant strings.
- **Static files.** The allow-list change (`app.py:691`) is an exact-match tuple that serves a fixed file under `static/`, so there is no traversal.
- **Request guard.** The endpoint inherits the GET handler's Host check.
- No new shell-out, file delete, credential or Electron surface.

### 2. Correctness & Logic

- Status: Concerns.
- **M1 [Major] — the cached count can miss a comic: the cache key leaves out `now`, which bounds the count.**
  - **Where:** `update_stats.py:251`, `:255`, `:260` and `:196`.
  - **How it happens:**
    - `report()` takes `now` (`:251`) before it opens the catalog and reads `revision = MAX(id)` (`:255`).
    - `_count` leaves out rows dated at or after `now` (`upper = min(edges[-1], now)`, `:196`).
    - The result is cached under `(edges, current, revision)` (`:260`), and `now` is not part of that key.
    - So a history row committed between taking `now` and reading `MAX(id)` is inside the revision but outside the count.
    - That undercount is then served from the cache for later requests in the same bar, until the next write or the next bar.
  - **Why the window is real:** `app.db()` runs `INSERT OR IGNORE INTO api_state` (`app.py:104`) on every open. That statement needs the write lock (probe 3), so the request waits for exactly the writer commit that adds the new row.
  - **The same gap without any race:** a clock set back makes rows dated "after now" (the case `test_rows_after_now_never_count` covers). Those rows stay excluded from the cached count after `now` passes them.
  - **Related:** `_bounds` (`:182-190`) has no upper bound at `now`, so `last_at` can show a future "Last update" in that case.
  - **Likelihood:** low (a window of a few milliseconds per request), and it heals on the next write. It is still a verified wrong number from the feature's only new caching mechanism.
  - **Evidence (probe 1):** one row stamped 12:40, queried at `now` 12:30 and then 12:50, both in the 12:00 bar:

    | Query | Total |
    |---|---|
    | First, at 12:30 | 0 |
    | Again at 12:50, from the cache, same revision | 0 |
    | Again at 12:50, after clearing the cache | 1 |

  - **Fix direction:**
    - Take `now` after reading the revision, and bound both queries with `id <= revision`.
    - When the period's rows include any stamp at or after `now`, do not cache the count.
- **The rest checks out:**
  - `bar_count`, `span_frame`, `_next_cut` and `current_slot` match Addendum A1. The 60-bar search falls back to `year`, which is documented to hold through 2059.
  - `_member` memoises out-of-library paths as `''`, so they are not recomputed.
  - Custom dates are checked in the spec's message order.

### 3. Crash / Stability Safety

- Status: Pass.
- **Server errors.** Any exception from `report()` goes to the handler's catch-all and returns a 400. The page shows "Statistics unavailable. Retrying.", retries every 15 s, and never shows the global banner.
- **Client timeout.** `request()` aborts after 12 s.
- **Loops.**
  - `refresh()` clears the single timer before every fetch, and `schedule()` replaces it.
  - A sequence check drops stale responses and does not reschedule from them.
  - Timers never stack. At most one extra fetch is in flight per visibility change or selection change.
  - The 2 s poll does not drive this panel.

### 4. Performance

- Status: Pass.
- **First-call index build:** 0.144 s on a synthetic 200,000-row history (probe 4). Once the index exists, `CREATE INDEX IF NOT EXISTS` takes no write lock (probe 3).
- **Recompute cost:** bounds and the period count are recomputed once per new revision, which is two indexed scans of at most all of history. `Last hour` misses the cache by design. The cache is a 32-entry LRU.
- The work is small relative to Ender's measured 0.05–0.22 s.

### 5. State & Data Safety

- Status: Pass.
- **No row writes.** The endpoint never inserts or changes a row. Its one schema write is the additive index, built in autocommit, in about 0.1 s at realistic sizes, with the writer's 30 s busy timeout covering the wait.
- **History is append-only.** It has one insert site (`app.py:644`) and no `DELETE` or `UPDATE` anywhere in product code, so `MAX(id)` is a sound revision apart from M1.
- **Write-lock contention (observation, not new):** every `app.db()` open takes the write lock for its no-op `INSERT OR IGNORE`. So this endpoint, like `/api/state` on the existing 2 s poll, can wait up to 30 s behind a writer's transaction. The new 15 s poll adds about one extra open per seven existing ones.

### 6. Input Handling

- Status: Concerns (Minor only).
- **What holds:**
  - `period` comes from a fixed tuple, and unknown query keys are refused.
  - Dates must match an ASCII `[0-9]{4}-[0-9]{2}-[0-9]{2}` pattern before `fromisoformat`, so year 0000 and impossible dates are refused.
  - Future dates and dates before 2000 are refused before any edge arithmetic. That leaves no `last + 1 day` overflow and no huge loops.
  - `now` is never read from the query.
- **m1 [Minor] — a missing custom date gets the wrong message.**
  - **Where:** `update_stats.py:228-232`.
  - **What happens:** a missing or repeated `from` or `to` returns code `invalid_range` with the text `Choose a period.`. The page shows that text under the date inputs.
  - **Reachable?** Only with a hand-written URL; the page never sends it.
- **m2 [Minor] — on Windows, older years use the current daylight-saving rules.**
  - **Where:** `update_stats.py:51-59`.
  - **The cause:** Windows' C library applies the current year's rules to every year. Probe 2, on this machine (Israel time):

    | Time (UTC) | Correct local hour | `time.localtime` |
    |---|---|---|
    | 2012-10-10 12:00 | 14:00 (standard time) | 15:00, `isdst=1` |
    | 2005-10-20 12:00 | 14:00 (standard time) | 15:00, `isdst=1` |

  - **The effect:** the browser formats with full historical zone data. Custom ranges that reach years before a rule change (before 2013 in Israel) get server edges an hour off from the browser. A month bar can then start at 23:00 on the previous day, so it is labelled with the previous month, and its tooltip reads as a clipped range.
  - **Impact today:** cosmetic, because no history exists before 2026. If the zone's rules change in future, stored 2026+ history would be bucketed by the new rules. The "page never works out daylight saving" design assumes server and browser agree on zone rules, and on Windows they do not for past years.

### 7. Maintainability

- Status: Pass.
- The module is small and documented, its edge maths can be tested with an injectable `wall`, and the page's DST handling is local to `repeat` and `endClock`.

### 8. Doc/Code Drift

- Status: Concerns (Minor only).
- **m3 [Minor] — the docstring's "read-only" claim needs a qualifier.**
  - **Where:** `update_stats.py:16-17`.
  - **What it says:** "Read-only, apart from one additive index".
  - **What is missing:** every call opens the catalog through `app.db()`, which takes the write lock on open (`app.py:104`, probe 3). So the endpoint can be held up to 30 s behind the writer.
  - **Also affected:** the Brief's decision row repeats "nothing dated after now counts", which M1 breaks under the cache.

### 9. Build & Release Hygiene

- Status: Pass.
- **Versions:** VERSION, `package.json` and both `package-lock.json` entries read 0.4.0, and CHANGELOG has the entry.
- **Packaging:** `build-installer.cjs:46-48` globs `*.py` and `static/**`, so both new files are packaged without a list edit. The local staged and unpacked copies carry SHA-256 values identical to source.
- **Dependencies and secrets:** no new dependency, and no secret.

## Entry-check failures (Jane's question)

**Answer: none of the 8 failures is a product defect, and none comes from this range.** The receipt (`dd019cb`, `dirty: N`) shows 968 tests with 6 failures and 2 errors, and every changed-area test passed. No failing test file changed in `e61c9ba..dd019cb`. The fixtures in `test_failure_filters_dom.py` abort `/update-stats.js`, so the new script never loads there.

| Failing test(s) | Cause | Product defect? |
|---|---|---|
| `test_failure_filters_dom`: `test_summary_lines` and `test_row_sentences_and_held_visibility` | Stale expectations. The product strings (`index.html:190` and `:210`) match the later KeysEntry (2026-10-16) and PerComicRecovery (2026-10-14) specs. The dead-link sentence changed in `3e1cc04` (v0.2.0). | No |
| `test_failure_filters_dom`: `test_details_dialog_carries_the_reason_and_last_error` | The fixture aborts `/comic-recovery.js`. The `#close` handler calls `ComicRecovery.close()` first, so it throws and the dialog stays open and blocks clicks. | No (fixture) |
| `test_kept_backups_dom`, two tests | Times fixed when the module loads ("12 min ago" against "13 min ago"; "just now" against "2 min ago"). | No (time-sensitive) |
| `test_state_root`, `test_qa_runtime`, `test_library_lock` | The packaged runtime's `python314._pth` drops the working folder, so the child Python cannot import `qa_runtime` or `app`. | No (test Python) |

**Coverage gap:** `check:shell` never ran, because npm `&&` stops after the failing step. This diff does not touch `desktop/` or the shell, so this release is not exposed to it.

## Advisory: entry-check context builder (not in the repo or release; not counted in the verdict)

**File:** `C:\Antigravity Projects\Worktrees\Comics Meta Organizer\qa-040\assemble-context.mjs`. Its SHA-256, `c0c705480aec1c9b07128d08d8490d9b69ba3248c5c6fd3af9b50db806e10176`, matches the one in the brief.

**Safety floor intact:**
- It writes only under `<run>/context`, with exclusive create (`wx`), and refuses an existing folder.
- It deletes nothing.
- Git is read-only, runs with `GIT_*` removed and `GIT_OPTIONAL_LOCKS=0`, and is called through `execFileSync` argument arrays, with no shell.
- It re-checks HEAD and the clean state after assembly.
- An empty `--protect` list does not remove the default live-state guards in `tests/test_0_state_isolation.py:51-58`.

| # | Sev | Where | Finding |
|---|---|---|---|
| B1 | Major | `:55`, `:76-77` | It pins `COMICS_META_TEST_PYTHON` to the packaged runtime's `python.exe`. Its `._pth` causes 3 of the 8 failures, so a receipt built this way cannot pass this suite. Fix that before the builder is committed (Backlog item 1). |
| B2 | Minor | `:53`, `:67-68` | The source snapshot copies working-tree bytes and checks cleanliness only through `git status --porcelain`. It never compares the bytes to HEAD's blobs, so skip-worktree, assume-unchanged or filter differences pass silently. With `core.autocrlf=true`, the manifest records CRLF bytes that cannot be cross-checked against Git. Prefer `git archive HEAD` or a `hash-object` comparison. |
| B3 | Minor | `:94`, `:114` | `run-entry.sh` reads the context hash from `context.json.sha256`, which sits next to the context it attests. Tamper evidence therefore rests on the hash printed at assembly. Record it in the handoff, or pass it to the wrapper as an argument. |
| B4 | Minor | `:8` against `:30` | The usage line marks `--checker` optional, but the parser requires it. |

## Evidence

Scratch folder: `C:\Users\AnGeLZzZ\AppData\Local\Temp\claude\c--Antigravity-Projects-Studio-Illuminati\96c4ae72-6ee4-4c35-b5bd-1374a2290ff7\scratchpad\senua\`. Session scratch is temporary, so the results are recorded above.

| Probe | Script | Result |
|---|---|---|
| 1 | `repro_cache_race.py` | M1 reproduced: 0, 0, then 1 after clearing the cache. The 14 inherited `test_update_stats` catalog tests passed on system Python 3.14.9. |
| 2 | `tzprobe.py` | m2. Also `mktime(1970-01-01)` raises `OverflowError` here; not reachable from validated input. |
| 3 | `lockprobe.py` | SQLite 3.50.4, while another connection holds the write lock: `INSERT OR IGNORE` on an existing row fails with "database is locked". `CREATE TABLE IF NOT EXISTS`, `CREATE INDEX IF NOT EXISTS` (index already present) and `SELECT` do not need the lock. |
| 4 | `indexcost.py` | Index build on 200,000 rows: 0.144 s first time, 0.002 s after. |

## Verdict

- Total Critical: 0
- Total Major: 1 (M1)
- Total Minor: 3 (m1, m2, m3)
- Advisory, not counted: B1 Major, B2–B4 Minor (context builder outside the release)

**Verdict:** RELEASE CLEAR

The safety floor is intact: no machine harm, no secret exposure, and no change to the repository's history. M1 and the Minor findings are logged for Ender's next cycle. This report covers construction only, and Futaba's behaviour verdict is separate.
