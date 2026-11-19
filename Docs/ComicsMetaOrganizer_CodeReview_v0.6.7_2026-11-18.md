# Code Review — Comics Meta Organizer v0.6.7

## Header

```text
Reviewer: Senua (Code Reviewer)
Date: 2026-11-18
Tool: Comics Meta Organizer (Comic Metadata)
Release: v0.6.7 (version bump not yet made; Sully's version-only bump commit follows)
Commit range: bcc100930d20b272326134859718a9cb6127144d (main, after the v0.6.6 release docs)
              ..cc1292ee74f3c2753e6fe1f8aaaf7c377e5c6d58 (ender/0.6.7-fixes, "Merge nested ComicInfo work into 0.6.7")
Reviewed head: cc1292ee74f3c2753e6fe1f8aaaf7c377e5c6d58
Commits: 24 (4ba7b52 .. cc1292e)
Files changed: 36 files, +31157 / -138 in all.
               Without Docs/: 30 files, +3271 / -136.
               Product: app.py, engine_host.py, supervisor.py, desktop/engine.cjs, graceful-stop.cjs, main.cjs,
               qa-policy.cjs, startup.js/.html, stopping.js/.html, shell.css; tools/nested_comicinfo_merge.py.
               Tests: tests/test_engine_host.py, test_nested_comicinfo.py, test_nested_comicinfo_merge.py,
               test_supervisor.py, test_library_lock.py, debug_hold.py (QA harness); 10 files in desktop/tests/.
               Docs: Brief, Judy's Quit spec rev 2, the dry run (.md/.csv/.json), Futaba's sample.
Stand-down dimensions: none
```

---

## Summary

The range holds four pieces of work:

1. The v0.6.6 fixes: T1 + M3 (broker exit code 124), t1 (a Quit cancels Retry) and t2 (a claim is judged by its lock byte).
2. A stale test fix, and worker stderr now reaching `engine.log`.
3. "Quit always closes":
   - the broker waits 30 s, terminating its Job again every 5 s;
   - parts still running after that go into a leftover record, and the next start re-checks it (exit 123);
   - `CLOSURE_UNCONFIRMED` is gone, and the shell gives up after the wait + 1 s;
   - the Closing stage is capped at 30 s;
   - sign-out exits in about 4.5 s.
4. Nested ComicInfo:
   - a nested-only copy is read as the comic's metadata;
   - the writer's `merge_nested`;
   - a one-time catalog re-read;
   - the one-off merge tool, which deletes each backup once its write is verified.

**Answers to the brief's questions, short:**

- **Can the merge tool or the writer lose pages or metadata?** No page can go unnoticed:
  - The writer checks every entry but ComicInfo by name, CRC, size and order against the backup, and allows exactly the one planned removal.
  - The tool then re-reads the whole archive with CRCs.
  - The nested copy is saved whole, fsync'd, before its backup goes.
- **Can it delete a backup without a verified write?** Not without a *verified* write. Every deletion is gated by the backup's SHA-256 equalling the original read under the write lock.
  - But the write is verified only in the OS cache. Nothing fsyncs the rewritten archive before its backup is deleted (Q1).
- **TOCTOU against the running app:** sound.
  - The tool takes the same per-archive write lock as the app and a same-state library claim.
  - It re-checks the catalog signature, the nested entry's name/CRC/size and the planned root fields before any backup.
  - The app's worker is refused by its own signature check afterwards.
- **Crash or partial run:** the backup is always kept.
  - A crash between write and verify leaves the archive merged and its backup in place.
  - The re-run skips the archive. Its dropped values then exist only in that backup (q4).
- **Can the leftover check block startup for good?** Yes, in one narrow case: a record with no process list whose old claim lock cannot be opened. A reboot does not clear it (q1, probed).
- **Can it let two engines run at once?**
  - PID reuse is handled: PID plus creation time.
  - The clock is never used for a decision.
  - Its fail-open paths are documented: a record that cannot be checked; a record with no list whose leftover part holds no claim; no record yet. In each of them, the per-archive write lock and the port probe still stand.
  - One corrupt-record case is never checked or retired (q6).
- **Can Quit hang?** No unbounded path was found:
  - every forced path ends by 31.5 s;
  - the pausing stage stays capped at 10 min, with Quit now.
- **Can Quit exit while a write is in flight?** Yes. The 30 s Closing cap force-stops a manual Approve that was running when Quit was pressed. The code and the Brief say this cannot happen (Q2). The write is atomic, so the comic is not corrupted, but the write is left half-recorded.
- **New cross-talk:** a broker that outlives the shell's wait can, when it finally exits, mark the next healthy engine "not ready". Then the auto-restart force-stops that engine (Q3, probed).
- **T1, M3, t1, t2, t5 from v0.6.6:** resolved.

**Targeted tests** (scratch `I:/AI Projects/Temp/senua-067/`, removed afterwards):

| Set | Interpreter | Result |
|---|---|---|
| Python: `test_0_state_isolation`, `test_nested_comicinfo`, `test_nested_comicinfo_merge`, `test_engine_host`, `test_supervisor`, `test_quit`, `test_zz_state_isolation` | System Python 3.14.10, `COMICS_META_HELD_TEST=1`, `COMICS_META_TEST_PROTECTED_ROOTS=[]` | 80 run, 79 passed. The 1 failure (`test_supervisor` restore line) is environmental: the test's child runs `python -I`, which hides the user-site Pillow. |
| Same `test_supervisor`, re-run | Scratch venv of 3.14.10 with Pillow copied in | 9 run (with the isolation checks), all passed |
| Shell: `engine`, `engine-spawn`, `graceful-stop`, `previous-session`, `quit-always`, `quit-pages`, `session-end`, `quit-absence`, `qa-policy` | Node 26.13.1 | 77 run, all passed. `engine.test.cjs`'s lock-holder test needs `COMICS_META_TEST_PYTHON`; with it, 20 of 20. |

**Probes** (scratch only; no live app, `%LOCALAPPDATA%\ComicsMeta`, library or installer touched):

- **Stale exit (Q3).** Real `engine.cjs`, with `spawn` stubbed and a stub HTTP endpoint:
  - The old broker is alive and ignores `force`, with a closure wait of 1 s.
  - `start()` waited 2.05 s, then spawned and readied a new broker.
  - The old broker's later `exit(124)` then set `engine.ready=false` and emitted `exit` with `wasReady=true`, while `engine.child` was the new broker.
- **Unopenable claim lock (q1).** Real `engine_host.previous_session_closing`, with a lock folder in scratch:
  - The setup: a record with no process list, 1 day old, and a read-only `engine-<owner>-*.lock` that nobody holds.
  - Two checks in a row both returned "waiting" (exit 123) after 5 s each, and kept the record.
- **Non-finite record time (q6).** A record with `"written": NaN` and a member list raised `ValueError` in the age line. It was logged as "could not be checked; not waiting", and its members were never looked at.

---

## Rubric

### 1. Security

- Status: Pass.
- **Electron:** no new IPC action (`forceQuit` and `cancelStop` already existed). The quit dialog keeps `contextIsolation`, `sandbox` and no Node.
- **Pages:** the new text on both pages is set with `textContent` only.
- **Spawn:** `--closure-wait` is a number. The broker bounds it to (0, 600], and the QA policy to 1–120.
- **Tool and harness:** neither is shipped (the installer takes only top-level `*.py`).
  - The tool's apply checks that `app` loaded from `--engine` with the given live state, and that the plan's library is the app's.
  - `tests/debug_hold.py` attaches a debugger only to the PID it is given, for the same user.
- **Secrets:** none in the diff (`git diff --check` is clean).

### 2. Correctness & Logic

- Status: Concerns.
- **Q3 [Major]** `desktop/engine.cjs:59` (with `:38-43` and `desktop/main.cjs:167`): **a broker's late exit is applied to whichever broker is current.**
  - The `exit` handler that `startOwned` attaches clears `this.ready` and emits `exit(code, wasReady)` without checking that the exiting child is still `this.child`.
  - Before 0.6.7, `forceStop` threw when closure was unconfirmed, so `startOwned` never spawned a second broker beside a live one.
  - Now `forceStop` resolves false after closure wait + 1 s, and Retry goes straight on to the port probe and a new broker.
  - When the old broker finally exits, the new healthy engine is marked not ready. `main.cjs`'s handler sees `wasReady=true` and schedules a restart. `startOwned` then finds a live child that is not ready and **force-stops the healthy engine**, interrupting whatever it is writing.
  - Also, until then: `poll()` stops, and a Quit skips the graceful pause (`GracefulStop.run`: `!engine.ready` goes straight to the forced end).
  - **Reachability is low:** the old broker must outlive its own bounded 30 s wait by more than the shell's waits (≥ 31 s, twice on the failed-start-then-Retry path) plus the new engine's start. That needs the broker itself to hang or be frozen, which is exactly the case the 31 s give-up exists for.
  - Probed (§ Summary).
  - **Fix:** capture the child in the handler (`const child=this.child; child.once('exit',…{if(this.child!==child)return;…})`). Consider also refusing to spawn while the previous child is still alive.
- **Q2** (§5) is also a correctness finding: the Closing cap's premise "paused means no comic write is running" is false for manual writes.
- **q2 [Minor]** `app.py:246-248` `comicinfo_entry`: **a nested-only copy is taken whole, without the merge's left-out rules.**
  - For the 150 nested-only archives in the dry run, the nested Year/Month/Day (store dates, per Futaba's F1), PageCount, letter-case twins and year-like Volume are read as the comic's metadata. Only "None" is dropped.
  - The next app write (the worker's automatic ones included) moves all of them into the root copy.
  - A read store-date Year also makes fill-empty skip the cover date the app would otherwise write.
  - The Brief's ruling text says "no nested date is copied at all", but it was given for the merge.
  - YACReader already shows these nested values today, so nothing visible regresses there. This is Sergei's call, not a code defect.
- **Resolved from v0.6.6:**
  - **T1:** a forced stop's leftover is code 124, never self-confirmed (`engine.cjs:120`). The broker's own failures go through `close_job` on every path.
  - **M3:** a claim-retirement failure after a proven-empty Job is logged and keeps the closure code (`engine_host.py:209-216`).
  - **t1:** the generation is read before awaiting the shared `forceStop` (`engine.cjs:43`).
  - **t2:** a claim is judged by reading byte 0 of its `.lock`. The PID still counts only when no `.json` exists yet.
- **Verified clean:**
  - **Writer merge:** `merge_comicinfo` only fills tags the root leaves empty. The nested entry must match the planned name/CRC/size. Unplanned fills are refused. The temp archive's merged elements are compared element by element.
  - **One removal:** duplicate names were already refused, so "exactly one removal" cannot hide a second missing entry.
  - **Tool apply:** it compares the engine-computed plan (fills, dropped values, removal) with the dry run's, so an engine with other rules skips instead of writing.
  - **Provenance:** `in_book_values` replaces only links whose source starts with the in-book prefix. The tool's `nested-comicinfo-merge` source makes the merged fields non-replaceable while earlier in-book values stay correctable, as the docstring says.
  - **Catalog re-read:** `nested_recheck` deletes a queue row only after a successful read, and only rows that were `missing` and unchanged take that path.

### 3. Crash / Stability Safety

- Status: Concerns.
- **Bounded waits:**
  - Every forced path ends by `closureWaitS + 1` s in `forceStopOwned`. `beginEnding`'s backstop exits at +31.5 s.
  - Sign-out exits by about 4.5 s.
  - `engine.call` has a 2.5 s timeout.
  - No path where Quit waits forever was found.
- **q3 [Minor]** `desktop/main.cjs:107`, `desktop/engine.cjs:46`: **when the broker itself is frozen or hung, Quit now exits the shell and leaves the engine running headless.**
  - The broker holds the only Job handle, so kill-on-close never fires while it lives.
  - The next start's port probe then reports "Another app is using the local service port", not the previous-session screen.
  - This trade-off follows from Sergei's "Quit always closes" ruling; only the message is wrong.
- **q1 [Minor]** `engine_host.py:423-437` `held_claims` (used by `leftover_running`): **an old claim lock that cannot be opened counts as held, for good.**
  - For a record with no process list (every shell-written record, and every unreadable one), each start waits 5 s and exits 123.
  - No reboot clears it, because no lock is actually held. The startup screen's "restart your PC" advice cannot help; only deleting the record by hand does.
  - Probed with a read-only `.lock`.
  - The shell's own `lockState` treats the same file as free, so the two sides disagree.
  - **Fix:** count only a lock conflict as held. Log any other open error, and do not block on it, or block only for a bounded time.
- **Inherited, untouched:** none open in this dimension. M3 is resolved.

### 4. Performance

- Status: Pass.
- **Start-time check:** at most 5 s per record that still runs. Each `held_claims` poll opens, locks and unlocks the old owner's few claim files every 50 ms.
- **Catalog re-read:** one-time, one central-directory read per queued `missing` CBZ during the folder scan.
- **The tool:** one archive at a time. It reads each archive about 4 times (original hash, rewrite, CRC re-read, backup hash), which is acceptable for a one-off.

### 5. State & Data Safety

- Status: Concerns.
- **Q1 [Major]** `app.py:861-891` (temp archive written, closed, `os.replace`d, never fsync'd); `tools/nested_comicinfo_merge.py:553-558`; the same pattern in `batch.py:262` and `app.py:1350`: **a backup is deleted before the rewritten archive is known to be on disk.**
  - `verify_written` and the writer's readback almost certainly read the new archive from the OS cache.
  - `save_record` fsyncs the dropped-values record, but nothing fsyncs the archive itself before `remove_verified_backup` unlinks the only other copy.
  - After a power loss or BSOD in that window, NTFS can keep the rename and the unlink (journaled metadata) while the new archive's data never reached the disk. The comic would be unreadable and its backup gone.
  - The window is seconds per archive. It is widest for small archives, whose deletion follows quickly; the large ones spend minutes re-hashing first.
  - The pattern predates this range (the worker's and Approve's verified-backup removal). This range adds 356 back-to-back deletions on a drive the Brief calls 99% full.
  - **Grade:** Major per the brief's floor for backup deletion. It is not Critical, because it needs a crash inside a narrow window.
  - **Recommended before the apply run:** in the tool, open the written archive `r+b` and `os.fsync` it before `remove_verified_backup`. This needs no new release, because the tool runs from the checkout. Later, in the writer, fsync the temp file before `os.replace`.
- **Q2 [Major]** `desktop/graceful-stop.cjs:49-52` (with `app.py:1433` and `app.py:1318-1350`): **the 30 s Closing cap can force-stop a manual write that is still running.**
  - "Paused" means the metadata and browser workers acknowledged (`pause_control.status`). A dashboard Approve that started before Quit runs under `LOCK`, and its pause check passed at request entry. It makes two ComicVine requests (45 s timeout each), hashes the comic and rewrites it in full.
  - `finish_quit` waits for that `LOCK`. On a multi-GB comic (the library's largest is 4.70 GB) this easily exceeds 30 s, and the forced path then terminates the Job mid-write.
  - Before 0.6.7, Closing waited out the rest of the 10-minute pause budget.
  - **The comic is not corrupted** (temp file plus atomic replace). What remains:
    - killed before the replace: a `.metadata-tmp` that blocks later writes to that comic until Folder help clears it, plus an untracked backup on a full drive;
    - killed after the replace: a written comic with no history or ledger row, so its values lose their provenance.
  - The comment at `graceful-stop.cjs:50` and the Brief's "paused by then, so no comic write is interrupted" are both wrong.
  - **Fix:** report a manual write in flight in the status the pause waits on (for example in `waiting_for`), so that "paused" is true before Closing starts. Or do not cap Closing while `LOCK` is held.
- **q4 [Minor]** `tools/nested_comicinfo_merge.py:538-558`: **an interrupted apply has no written recovery story.**
  - A crash or Ctrl+C between the write and `save_record` leaves the archive merged, with its backup kept but no line in `--out`.
  - A re-run needs a new `--out` and skips the archive (now root-only).
  - That archive's dropped nested values then exist only in its kept backup, while the Brief says `--out` "is the only record" and the drive is short of space.
  - **Fix:** say in the Brief and the docstring that after an interrupted run, the backups listed in Kept backups for this source must be kept, or saved with the tool, before anyone cleans up.
- **Verified clean:**
  - The tool deletes a backup only (a) after a full CRC re-read, the entry-for-entry comparison and the root-unchanged check, with the backup's SHA-256 equal to the original's; or (b) after a failed write, when the archive's SHA-256 still equals the original's.
  - A write that changed the archive and then failed returns `stopped` with the backup kept, and the run stops.
  - **Nested-only writes:** the nested copy carries over completely, apart from "None" values (Sergei's ruling) and XML comments and spacing. Its removal is covered by the same one-removal entry check.
  - **Leftover records:**
    - Each check terminates only the exact process the record names (PID plus creation time, through the opened handle, with no reuse window).
    - Every record lives in the app's own lock folder.
    - The broker's record goes through a temp file and `os.replace`. The shell's record uses `wx`, so it never overwrites the broker's.
- **Inherited, untouched in range:**
  - **M2 [Major]** `archive_conversion.py:161`.
  - **t3 [Minor]** `progress_snapshot.py:83/:110`.
  - **n1 [Minor]** `storage.py:162-165`.

### 6. Input Handling

- Status: Concerns.
- **q6 [Minor]** `engine_host.py:361`: **a record with a non-finite `written` is never checked or retired.**
  - `json.loads` accepts `NaN` and `Infinity`, and `round()` then raises in the age line, before any member is looked at.
  - The record is logged as "could not be checked; not waiting" on every start. It stays, and the parts it names are never terminated or waited for. Probed.
  - It can come only from a damaged or hand-made file; both writers write a real time.
  - **Fix:** validate `written` with `math.isfinite`, or compute the age inside the same guard that falls back to the file time.
- Clean: member lists are type-checked (`int`, > 0); an owner outside the 64-hex pattern never reaches a claim path; a bad `--closure-wait` is refused before anything starts; and the tool's plan kind and version are checked.
- **Inherited:** **n2**, **s6**, **i1 [Minor]**.

### 7. Maintainability (no Critical findings on its own)

- Status: Concerns.
- **q7 [Minor]** small items:
  - (a) `desktop/engine.cjs` `leftoverSince` uses `/^leftover-.*.json$/` (unescaped dot).
  - (b) `engine_host.record_leftover`'s `leftover-<owner>.tmp` is never cleaned up if the broker dies mid-write.
  - (c) The broker's record and the shell's record are both checked by the same 5 s period, `RETERMINATE_EVERY`. The constant serves two meanings: the Job wait per termination and the start-time grace.
  - (d) The tool's `merge()` calls `guard.__enter__` and `__exit__` by hand, not with `with`. It is correct today, but fragile.
- **Inherited:** **s7**, **t4 [Minor]**.

### 8. Doc/Code Drift (no Critical findings on its own)

- Status: Concerns.
- **q5 [Minor]**
  - (a) The Brief's Quit row and `graceful-stop.cjs:50`: "paused by then, so no comic write is interrupted" (Q2).
  - (b) The Brief's Quit row and `engine_host.py:326`: "A reboot clears every record" (not for q1's case).
  - (c) The Brief's "Broker ended from outside" row still carries the pre-"Quit always closes" text: "terminated (twice for a forced stop, `CLOSURE_WAIT` 5 s each)" and "a forced stop whose Job empties only after the second termination is now a plain 125". The parenthesis after it supersedes this, so the row contradicts itself.
  - (d) The tool's docstring says it "takes the same library claim as the running app". It takes its own claim, which the app's claim allows because they share a state root.
- **Resolved:** **t5** (the claim check is now described as the lock byte, and the missing-folder rule is stated).
- **Inherited:** **s8**, **n5 [Minor]**.

### 9. Build & Release Hygiene

- Status: Pass, conditional.
- **Pending bump:** `VERSION`, `package.json` and the lockfile still read 0.6.6, and `CHANGELOG.md` has no 0.6.7 entry. This clearance assumes Sully's next commit changes only those, plus a CHANGELOG naming the four pieces of work above.
- **Diff:** `git diff --check` is clean. The tool and `tests/debug_hold.py` are not packaged (the installer copies only top-level `*.py`).
- **Working tree:** clean apart from this report. No test output was left in the checkout.

---

## Patterns

This range repeats the v0.6.4–v0.6.6 pattern: a proof stops at a proxy. Q1 verifies the archive in the cache and then deletes the only other copy as if the data were on disk. Q2 takes "workers paused" to mean "no write in flight". Q3 takes "the current child" to mean "the child that exited".

---

## Verdict

- **Total Critical:** 0.
- **Total Major:** 7.
  - New: Q1, Q2, Q3.
  - Inherited, untouched: M1, M2, I1, I2.
  - Resolved: T1.
- **Total Minor:** 26.
  - New: q1–q7.
  - Inherited, untouched: s1–s11, n1–n5, i1, t3, t4.
  - Resolved: M3, t1, t2, t5.
- **Safety floor:** intact.
  - No Electron preference or IPC change.
  - Every new write is in scope: the app's lock folder, the user's own library through the app's writer, and the tool's `--out`.
  - No secret handling.
  - No repository-integrity change.
  - Every backup deletion is gated by a SHA-256 match and, on success, a full verification (Q1 is a durability gap, not an unverified deletion).

**Verdict:** RELEASE CLEAR

This clears construction for source commit cc1292ee74f3c2753e6fe1f8aaaf7c377e5c6d58 (range bcc100930d20b272326134859718a9cb6127144d..cc1292ee74f3c2753e6fe1f8aaaf7c377e5c6d58), plus a bump that changes only the version and the changelog. It does not prove installer behaviour, the QA entry gate or publication.

- **Before the one-off apply run** (not a release gate): the tool-side half of Q1, an fsync of each written archive before its backup is deleted.
- **First items for Ender's next cycle:** Q2 and Q3.

**Built commit covered:** v0.6.7 build `9d1ad1af7c3e3f6c0db86b052d8372c8f1c5ad1b`. It is cc1292e plus two commits, 880f305 (this review) and 9d1ad1a (Sully's bump). I checked this with `git diff cc1292e 9d1ad1af7c3e3f6c0db86b052d8372c8f1c5ad1b`, which touches 5 paths:

- this review;
- `VERSION`: 0.6.6 to 0.6.7;
- `package.json`: the `version` field, 0.6.6 to 0.6.7;
- `package-lock.json`: its two version fields, 0.6.6 to 0.6.7;
- `CHANGELOG.md`: a v0.6.7 entry naming the Quit, broker, worker-log, nested ComicInfo and sign-out fixes, and the merge tool (not run).

There is no source, test, tool or build-config change.
