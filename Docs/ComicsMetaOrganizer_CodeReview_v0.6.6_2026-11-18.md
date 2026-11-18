# Code Review — Comics Meta Organizer v0.6.6

## Header

```text
Reviewer: Senua (Code Reviewer)
Date: 2026-11-18
Tool: Comics Meta Organizer (Comic Metadata)
Release: v0.6.6 (version bump not yet made; Sully's version-only bump commit follows)
Commit range: b793d3acb8b3df64a958a9f8ccf78a1644f9ef76 (main, v0.6.5)..acb567debb1f6306480f736487097c6d9c6fa37a
              b4d9cb4 one cite list for both fallbacks (VerseDB added to the name search's)
              71115db N1: per-file save lock across threads and processes (storage.exclusive)
              acb567d broker ended from outside: the shell confirms closure itself (engine.cjs treeEnded)
Candidate commit: acb567d (ender/0.6.6-fixes, same as origin/ender/0.6.6-fixes)
Files changed: 9 files, +436 / -34 (product: storage.py, desktop/engine.cjs, comicvine_search.py, versedb.py;
               tests: test_restore_race.py, test_comicvine_search.py, engine.test.cjs, engine-spawn.test.cjs; Brief)
Stand-down dimensions: none
```

---

## Summary

Three fixes. (1) The ComicVine name search now skips comics that cite VerseDB, through one shared list. (2) N1 from v0.6.4: putting a `.bak` copy back and every `keep_previous` save of the same file now take a named Windows mutex for that file. The lock works across threads and processes. (3) TrayQA v0.6.4 finding 2: when the broker ends with an exit code that does not confirm closure, the shell checks closure itself before Retry or Quit continue. It waits up to 10 s for two things: the engine port is free, and no claim file of this engine names a live PID.

**The broker fix answers the brief's question with "mostly no".** Could the self-check say "closed" while an engine process is still alive and holds a library?

- **A claim holder that still runs code:** no. `process.kill(pid, 0)` only checks liveness, and a reused PID can only make a dead holder look alive.
- **A process that has been ended but not yet cleaned up:** yes, but this is harmless. It can run no more code.
- **A process in the Job that holds no claim (7-Zip, the Lens browser):** yes. This matters in one case, T1. Exit code 1 means either "ended from outside" or the broker's own "descendants remain" failure, and the shell now overrides the second one.
- **Leftover claim files of dead processes:** they never cause a false "closed". They can wrongly block Retry or Quit if their PID is reused (t2).
- **A free port while a process is still exiting:** the listener closes only during handle cleanup, after the threads have stopped. The probe saw the port free within 3 ms of the kill, even with keep-alive connections and `SO_EXCLUSIVEADDRUSE`.
- **Claims folder unreadable:** the check refuses, and a test covers this.
- **Claims folder missing:** the check counts this as "no claims". That is sound, because the folder cannot be renamed while a claim is held (probe: EPERM).

**M3:** Ender is right that the fix eases M3's symptom, and that is safe for M3's own case. There the broker had already proved the Job empty. The leftover claims are unlocked and the next claimant sweeps them up. Each new broker also gets a new owner identity. M3 is re-graded below.

**N1** is resolved. **The cite list** shows no regression: VerseDB's behaviour is unchanged, and the name search covers fewer comics, as intended.

**Ender's "pre-existing" claim holds.** Each targeted run was made on an exported `b793d3a` tree and on the branch checkout, with the same interpreter, the suite's isolation net loaded first and its check last:

| Interpreter | Settings | Run | Result | main vs branch |
|---|---|---|---|---|
| System Python 3.14.10 | no supervisor variables | 26 | 2 failures (`test_library_lock`: the leftover-process holder, and conversion `LibraryBusy`), 1 error (`test_check_python`) | identical |
| Packaged toolchain Python 3.14.8 | `COMICS_META_HELD_TEST=1`, `COMICS_META_TEST_PROTECTED_ROOTS=[]` | 26 | 1 failure (`test_library_lock` conversion) | identical |

- `test_api_redaction` passes on both sides in isolation, so Ender's import-path error depends on the full-suite run, not on this branch. That test goes through the new lock (`legacy_status`).
- The failing `test_library_lock` case exercises `archive_conversion`, which is untouched in this range.

**Branch, targeted:**

- **Python:** 14 modules, **159 run, all passed**: restore race, the storage tests, startup recovery, progress snapshot, browser search, ComicVine search, VerseDB, the 0.6.5 fix tests, API redaction, lens holds, progress cap.
- **Shell:** `engine`, `engine-spawn`, `graceful-stop`: **20 of 20 passed**.
- **Positive control for N1:** with `storage.exclusive` turned into a no-op, **3 of the 4** race tests fail. The fourth is the test's own positive control.

**Probes** (scratch under `I:/AI Projects/Temp/senua-066/`, random ports, deleted afterwards):

- Port release after a kill: the port is free within 1–3 ms.
- PID reuse: 3 × 400 process spawns (~17 s each) never reused the freed PID.
- Reading a held claim's lock byte returns `EBUSY`; it is readable after release.
- Renaming the claims folder while a claim is held fails with `EPERM`.
- A tray Quit during Retry's closure wait still lets Retry start a broker (t1).
- A `\\?\` path spelling gets a different save-lock name (t4).

No live app, live state, `%LOCALAPPDATA%\ComicsMeta`, library or installer was touched.

---

## Rubric

### 1. Security

- Status: Pass.
- No new IPC and no Electron preference change. Nothing new shells out. `process.kill(pid, 0)` is libuv's liveness check and never terminates the process (a test aims it at its own PID). The owner value is checked as 64 hex characters before it goes into the claim regex. The mutex name is a SHA-256 of the path. No secrets appear in the diff or tests.

### 2. Correctness & Logic

- Status: Concerns.
- **T1 [Major]** `desktop/engine.cjs:93-98` (with `engine_host.py:169` and `:188`): **exit code 1 has two meanings.**
  - It covers both an outside end (Task Manager and `taskkill` use code 1) and the broker's own `RuntimeError` ("Owned engine descendants remain", "Engine descendant closure unconfirmed"). An uncaught exception also exits with 1.
  - In the second case the broker has seen, through its own Job count, that a Job member survived 10 s of termination. `treeEnded` replaces that evidence with a weaker check.
  - **What the check misses:** it cannot see a Job member that holds no claim (`7z.exe`, the Lens browser). Its signal-0 check reads the exit code, so a process whose exit status is set already reads as gone. Its handles (claim lock, worker lease, an open archive) may still be closing.
  - **Why it is not Critical:** the surviving member has had `TerminateJobObject` twice plus kill-on-close, so it cannot run code again. A duplicate worker is still stopped by the worker lease. What remains is one in-flight kernel I/O.
  - **Why it is still Major:** 0.6.5 refused here on purpose, the Brief's own rollback trigger is "a process of the old engine found alive after a restart", and the fix is cheap.
  - **Fix:**
    1. `engine_host.main` catches its own closure failures and returns a distinct code (for example 124).
    2. The shell never self-confirms that code. It keeps `treeEnded` for an outside end only.
    3. In the same place, fix M3's cause: return the closure code when the Job was proven empty, even if claim retirement fails.
- **t1 [Minor]** `desktop/engine.cjs:29-34`: **a Quit during Retry's closure wait does not cancel Retry's broker start.**
  - Why: `startOwned` reads `stopGeneration` only after its own `forceStop` resolves. A tray Quit during `treeEnded` shares that promise and has already moved the generation on.
  - Effect: Retry then probes the port and starts a broker while the shell is exiting.
  - Probe on the real `engine.cjs`, with `spawn` stubbed: Quit resolved, then a broker was spawned.
  - This was unreachable before 0.6.6, because `forceStop` on a dead broker returned or threw at once. The 10 s wait opened the window.
  - Why it stays Minor: when the shell exits, the owner pipe closes, and the late broker ends its Job (125).
  - Fix: read the generation right after starting the own `forceStop` and before awaiting it (`const pending=this.forceStop(), generation=this.stopGeneration; await pending;`).
- **t2 [Minor]** `desktop/engine.cjs:113-121`: **liveness is judged by the PID in a claim's file name, not by the claim's lock.**
  - After an outside end, `retire_engine_claims` never runs, so the dead engine's claim files stay until a Python claimant sweeps them.
  - If one of their PIDs is reused first, Retry and Quit are refused again until the reusing process exits.
  - The probe saw no reuse within ~17 s, so the immediate auto-restart check is safe. Exposed: a late Retry or Quit, for example after `RESTART_EXHAUSTED`.
  - An authoritative check exists and was measured: claim locks are mandatory byte-range locks, so reading byte 0 of a held `.lock` returns `EBUSY`. That check ignores PID reuse and also stays correct while a process is still being cleaned up.
- Verified clean:
  - **Kill-on-close holds:** the Job is unnamed, its handle cannot be inherited, and `PROC_THREAD_ATTRIBUTE_HANDLE_LIST` passes only stdio. Breakaway is not allowed (`flags=0x2000`).
  - **Paths match:** the claim name pattern matches `library_lock.acquire` exactly. Workers inherit `COMICS_META_CLAIM_OWNER` and `COMICS_META_LOCK_DIR` (`supervisor.py` copies `os.environ`).
  - **Install never uses the self-check:** the `install` mode of `GracefulStop` never forces, so an update never relies on it.
  - **Cite list:** `comicvine_search.cites` reads Web and Notes with the regex 0.6.5's `versedb` used, so VerseDB is unchanged. The name search only narrows. Its `can_search` stays a subset of Metron's, so the assumption in `search_fingerprint` still holds. Narrowing can only mark more comics as having nothing left to ask, never leave a stale marker. There is no import cycle.
- **Inherited, untouched in range:** **M1 [Major]**, **I1 [Major]**, **I2 [Major]**, **s1–s4, s9–s11 [Minor]** (the name-search line numbers moved +1), **n3, n4 [Minor]**.

### 3. Crash / Stability Safety

- Status: Pass.
- **Bounded waits:** `forceStop` adds at most 10 s (200 ms polls), and only on an unconfirmed exit. An unconfirmed closure still throws, as before. `CLOSURE_UNCONFIRMED` stays sticky in `main.cjs:94`, unchanged.
- **Inherited, re-graded:** **M3 [Major → Minor]** `engine_host.py:182`. A claim-retirement exception after the Job was proven empty still masks the closure code. The shell's self-check now confirms that case, so M3's consequence ("strands the app until manual recovery") no longer follows. Fix it together with T1.

### 4. Performance

- Status: Pass.
- **Lock hold:** the lock covers a read, a JSON check and two fsync'd writes of one file (~80 ms at `folders.json` size, per the Brief). Writers of the same file wait for it. The dashboard's normal poll never takes it; only a damaged file makes the poll take it.
- **Closure wait cost:** `treeEnded` runs only on the failure path.

### 5. State & Data Safety

- Status: Concerns.
- **N1 [Major] — resolved in 71115db.**
  - **Logic:** the re-check, the `.unreadable` copy and the put-back all hold the file's lock, and so does every `keep_previous` save. A save landing in the window now waits.
  - **Positive control:** with the lock off, 3 race tests fail; with it on, all pass, including the cross-process race.
  - **No missed writer:** every writer of `progress.json`, `folders.json` and `browser-search.json` is a `keep_previous` save (`batch.progress`, `scheduler.save`, `browser_search.legacy_status`). The code never saves, deletes or renames these files any other way.
  - **No deadlock:** nothing takes another lock (gate, database, threading lock) while holding this one. The validators are pure functions. A Windows mutex is recursive per thread anyway.
  - **A holder that dies:** the mutex is abandoned and the next waiter takes it, as tested. Every step is a temp file plus an atomic rename, so an interrupted holder leaves at worst a stray `.tmp`.
  - **Windows details:** ownership is per thread and released in the same `with` block. `Local\` is per session, and every engine process shares the session.
- **browser-search.json:** its save and restore are now serialized. Its read-modify-write in `legacy_status` across the browser worker and `lens_verification` is still not covered. That is the known two-writer lost update from v0.6.4, unchanged and not new.
- **t3 [Minor]** `progress_snapshot.py:83` and `:110`: **the lock's timeout can fail a dashboard poll.**
  - `TimeoutError` from the lock is an `OSError`, which `collect` does not catch.
  - When a damaged file meets a lock held for over 30 s, the poll's request thread waits the full 30 s inside `read_json`. The poll then fails, instead of showing "Status unavailable".
  - This needs damage plus a stuck holder. The `PermissionError` path before 0.6.6 behaved the same way.
- **T1** (§2) is also a state-safety finding: the restart decision.
- **Inherited, untouched in range:**
  - **M2 [Major]** `archive_conversion.py:161`.
  - **n1 [Minor]** `storage.py:162-165` (was `:88-95`): a missing file still keeps a stale `.bak`.

### 6. Input Handling

- Status: Pass.
- Claim names outside the strict pattern are ignored. A PID too large for Node throws and counts as alive (fails closed). An unreadable claims folder, or a missing or malformed owner, is not proof.
- **Inherited:** **n2**, **s6**, **i1 [Minor]**.

### 7. Maintainability (no Critical findings on its own)

- Status: Concerns.
- **t4 [Minor]** `storage.py:79-85` `_lock_name`: **one path spelling gets its own lock.** A `\\?\`-prefixed spelling of a state file gets a different lock name (probe), against the docstring's "whatever its spelling". `library_lock.identity` strips the prefix; this function does not. Every current caller reaches the three files through `app.DATA` (an `abspath` state root), so the bug is latent.
- The non-Windows fallback lock cannot be re-entered, unlike the Windows mutex. Nothing nests it today, but a future fix that wraps `legacy_status`'s read-modify-write in `exclusive()` would deadlock for 30 s off Windows.
- `test_both_fallbacks_skip_the_same_citations` always passes now that `versedb.cites` delegates. It only guards against a re-split, which is acceptable.
- In `engine-spawn`'s Retry test, `port:0` makes the port check vacuous.
- **Inherited:** **s7 [Minor]**.

### 8. Doc/Code Drift (no Critical findings on its own)

- Status: Concerns.
- **t5 [Minor]** **the Brief's "Broker ended from outside" row and the comment at `engine.cjs:102-104` overstate the check.**
  - They say "no process lives that holds one of that engine's library claims". The code checks the PID named in each claim file.
  - A missing claims folder counts as none. That is sound (§ Summary), but not stated.
  - The row also lists "its own closure check failed" as a covered case without saying that this overrides the broker's own negative result (T1).
- The `storage.py` docstring and the N1 Brief text match the code.
- **Inherited:** **s8**, **n5 [Minor]**.

### 9. Build & Release Hygiene

- Status: Pass, conditional.
- **Pending bump:** `VERSION`, `package.json` and both lockfile version fields still read 0.6.5, and `CHANGELOG.md` has no 0.6.6 entry. This clearance assumes Sully's next commit changes only those, plus a CHANGELOG naming the three fixes.
- **Diff:** `git diff --check` is clean, with no secrets. All touched modules are top-level `*.py`, or `desktop/`, and both ship.
- **Working tree:** clean apart from this report. No test output was left in the checkout.

---

## Patterns

This repeats v0.6.4's N1: the fix trusts a proxy where a direct observation exists. T1 throws away the broker's own Job count, and t2 judges a claim by the PID in its name instead of its lock. In both places the stronger signal is already in hand (the broker's evidence; a byte-0 read returning `EBUSY`).

---

## Verdict

- **Total Critical:** 0.
- **Total Major:** 5.
  - New: T1.
  - Inherited, untouched: M1, M2, I1, I2.
  - N1 is resolved; M3 is re-graded to Minor.
- **Total Minor:** 23.
  - New: t1–t5.
  - Re-graded: M3.
  - Inherited, untouched: s1–s11, n1–n5, i1.
- **Safety floor:** intact.
  - No unsafe Electron change.
  - No write outside the state folder.
  - The restart path cannot start a second engine while an old claim holder still runs code.
  - The installer path never uses the new self-check.
  - No secret handling changed.
  - No repository-integrity change.

**Verdict:** RELEASE CLEAR

This clears construction for source commit acb567d (range b793d3a..acb567d), plus a bump that changes only the version and changelog. It does not prove installer behaviour, the QA entry gate or publication. T1, t1 and t2 are the first items for Ender's next cycle; T1 and M3 share one change in `engine_host.py`.
