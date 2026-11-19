# Code Review — Comics Meta Organizer v0.6.9

## Header

```text
Reviewer: Senua (Code Reviewer)
Date: 2026-11-19 (first pass, finished just after midnight); delta pass 2026-11-20
Tool: Comics Meta Organizer (Comic Metadata)
Release: v0.6.9 (version bump not yet made; Sully's version-only bump commit follows)
Commit range: 27647d8e56732c490a697eabfc0ea14687c83b76 (main, "Docs: v0.6.8 release receipt")
              ..105a25abcacf4d31d34e0700e693c12947f4cc57 (ender/0.6.9-fixes, "w3(b): a held, rewritten archive is
              'written_unverified', never counted as skipped")
Reviewed head: 105a25abcacf4d31d34e0700e693c12947f4cc57
Reviewed in two passes:
              1. 27647d8..4874894fe36381ea095b5df35d83310537c74cbf: 6 commits (9e0510e r2, e20b9ee R3, f49034e Futaba
                 finding 1, 1eecf0a r7, 572fa9a r2 held backup, 4874894 r2 rename). The Summary and Rubric below.
              2. 4874894..105a25a: 3 commits (eb71d0d W1, ec56d8a w3, 105a25a w3(b)), the answers to W1 and w3;
                 § Delta review.
Commits: 9 (9e0510e .. 105a25a)
Files changed: 10 files, +804 / -47 in all.
               Product: storage.py, app.py, archive_conversion.py, library_lock.py, tools/nested_comicinfo_merge.py
               (5 files, +203 / -33).
               The delta alone: app.py, storage.py and the tool +41 / -16; tests and the Brief besides.
               Tests: tests/test_review_068_fixes.py (new), test_nested_comicinfo_merge.py, test_nested_comicinfo.py,
               test_review_067_fixes.py.
               Docs: the Brief.
Base check: 27647d8 is docs-only on top of the v0.6.8 build da503b3 (git diff da503b3 27647d8: the v0.6.8 review,
            Tray QA and release receipt). The range is the whole of 0.6.9's code.
Stand-down dimensions: none
```

---

## Summary

The first pass (to 4874894) is below. The second pass (to 105a25a), which fixes W1 and w3, is in § Delta review. The Verdict covers both passes.

The range answers the v0.6.8 review (r2, R3, r7) and Futaba's TrayQA v0.6.8 finding 1:

1. **r2:** the app's flushes (`storage._open_handle`) wait out a sharing violation (Windows error 32) for 10 s. The merge tool's `make_durable` waits 30 s, then reports the archive `skipped`, keeps its backup and carries on.
2. **572fa9a:** the merge tool waits 30 s for a held backup. If the backup is still held, the archive is reported `written` and its backup is kept.
3. **4874894:** the app writer's final rename (`storage.replace_durably`) waits up to 10 s on error 32, or on error 5 when the comic is not read-only.
4. **R3:** conversion uses `storage.replace_durably` and `flush_directory` before it deletes the original.
5. **Futaba finding 1:** a claim lock that cannot be opened for writing is tested through a read-only handle. A lock that cannot be opened at all is not counted.
6. **r7(b):** a torn tail in `dropped-nested-values.csv` is cut at the last complete row.

**Headline.** One fix opens a new hole: the rename wait (3). The writer checks that the comic is unchanged, then waits up to 10 s for another program to close the comic, then renames over it. Nothing checks the comic again after the wait. If the program holding the comic changes it during that wait, the change is overwritten without any error. The backup was copied before the change, so it doesn't hold the change either. I reproduced this in the app writer and through the merge tool. The tool reported `written` and deleted the backup, so the change was lost completely (W1, Major). The other fixes do what they claim.

**Answers to the brief's questions, short:**

- **Can a retry mask a real failure, or let a stale plan write over a changed comic?**
  - The flush and backup-delete retries retry only error 32, and they never write anything. They can't put stale data over a comic.
  - **The rename retry can:** see W1.
  - Masking: after its wait, `make_durable` turns *any* `OSError` into `skipped` and carries on, an I/O or network error included. `summary.json` then counts that rewritten archive with the untouched `skipped` ones (w3).
- **Can treating a held backup as `written` lose the only copy of anything?** No.
  - That branch is reached only after all of these have happened: the archive is checked against its backup (`verify_written`); the dropped values and the nested copy are saved to `--out`; the archive and its folder are flushed; `verified` is journaled; and `remove_verified_backup` has matched the backup's SHA-256 to the original. Only then is the delete refused with error 32.
  - Nothing is deleted on that branch, and the backup is listed as "Saved; backup could not be deleted".
  - A holder that blocks *reading* the backup never reaches this branch. It stops the run at once (w2), which fails safe.
- **Can the 10 s rename wait race the running app or the worker?** Not CMO itself.
  - Every CMO writer (Approve, the worker, Kept backups restore, comic recovery, Folder help, the merge tool) and the app's own recovery take `comic_write_guard`, so they queue behind a waiting write.
  - The race is with an *outside* program that edits the comic (W1).
  - The waits add up to as much as 3 × 10 s per write. That can push a Quit past its 30 s Closing cap, which then kills the process mid-write. The Q2 pending-write recovery covers that, so no data is at risk (w5).
- **Can conversion now delete an original whose CBZ isn't proven?** No.
  - The original is deleted only after five steps: the CBZ is flushed, renamed into place with write-through, its folder is flushed, every entry is re-read and checksummed against the manifest built from the extracted files, and its SHA is recorded.
  - Any failure before the delete keeps the original. In the same-name case the set-aside original is moved back.
  - w4 is about the CBZ's destination, not the original.

**Before the real-library run (356 comics), at the first pass** (superseded: the current advice is in the Verdict):

1. **No other program that *edits* comics may run during the apply.** That means ComicRack, ComicTagger, Mylar, or any other tagger, until W1 is fixed. Readers such as YACReader, thumbnailers and antivirus are safe: they hold the file but don't change it, and the wait helps with them.
2. **After the run, read `results.jsonl`, not just the `Done:` counts.** A `skipped` line with `kept_as: save_not_verified` means the archive **was rewritten**, and its backup is the copy to keep (w3).

**Tests (targeted, per § Lean verification).** `test_0_state_isolation`, `test_review_068_fixes`, `test_nested_comicinfo_merge`, `test_library_lock`, `test_storage_durable`, `test_conversion`, `test_write_safety`, `test_kept_backups` and `test_zz_state_isolation` ran on the bundled runtime (`build/toolchain/capsule/runtime/python/python.exe`, 3.14.8): **117 run, all passed, none skipped** (7-Zip present, so the R3 tests ran). I did not re-run the full suite (Ender: 1391 OK).

- Environment note: the system Python 3.14.10 fails `test_library_lock.test_leftover_process_of_another_copy_blocks_until_it_ends`. That test starts a subprocess with `-S`, and that interpreter keeps PIL in site-packages, so the import fails. It is an environment problem, not code.

**Probes (scratch, deleted after).** Seven probe tests, run on the bundled runtime:

- **P1:** an outside program edits the comic during the rename wait (it opens the comic `r+b`, rewrites it, and closes it 0.4 s later). Result: no error; the edit is gone from both the comic and its backup. Positive control with `RENAME_HELD_WAIT = 0` (0.6.8 behaviour): the rename is refused and the edit survives.
- **P1b:** the same through `tools/nested_comicinfo_merge.py --apply`. Result: `{'written': 2, 'held': 1}`, and the backup is deleted, so the edit exists nowhere.
- **P2:** a holder that shares nothing. Python's `open()` raises errno 13 with `winerror` None, and `os.unlink()` raises winerror 32. `tool.remove_backup` raises after 0.000 s, without waiting.
- **P3:** `csv_rows_end` at all 17,200 cut points of random `csv.writer` output (quotes, commas, CR, LF, CRLF, non-ASCII text, a BOM), with and without a zero-filled tail. Every cut lands at the last complete row.
- **P4:** a live claim from another state root, with its lock made unopenable for both write and read. The second copy now acquires the same library, so both hold it.

---

## Delta review: 4874894..105a25a

Three commits answer W1 and w3: eb71d0d (W1), ec56d8a (w3), 105a25a (w3(b)). The product change is `app.py`, `storage.py` and the tool, +41 / -16. Tests and the Brief changed too.

- **W1: resolved.**
  - `replace_durably(source, destination, check=None)` now calls `check()` after the flush of the temporary archive and before *every* rename attempt, the first one included.
  - The writer passes `unchanged()`. It compares the comic's size and mtime with the signature taken when the write began, the same one `app.py:1128` checks. A difference, or a missing comic, raises `ArchiveChanged`, and nothing is renamed.
  - The closure reads `stat` before the writer reassigns it after the rename, so it compares against the right signature.
  - Every caller keeps the backup:
    - the worker records `write_skipped`;
    - Approve lists the backup as "Save not verified";
    - the merge tool reports `skipped`. `discard_unused_backup` hashes the comic, finds it differs from the original, and keeps the backup.
  - **My probes, re-run at 105a25a:**
    - **P1** (an edit that changes the size, made at the rename and held 0.4 s): `ArchiveChanged`. The comic keeps the edit, and the backup equals the original.
    - **P1b** (the same, through `--apply`): that comic is `skipped` with "Comic changed while preparing metadata", its backup is kept, and the other comic is `written`. Counts `{'skipped': 1, 'written': 1, 'held': 1}`.
    - **P1c** (a same-size edit in place, held 0.4 s, then closed): refused. NTFS moved the mtime by the time the holder let go, and the rename can't succeed before that.
    - **P1e** (the comic moved away once its holder closed): refused. Nothing is recreated at the old path, and the moved file is unchanged.
    - Ender's two new tests cover the same ground, including an edit made during the temporary archive's flush.
- **w3: resolved.**
  - After its wait, `make_durable` now splits by error. Error 32 still held after 30 s gives `written_unverified`, with the backup kept and labelled "Save not verified", and the run goes on. Any other error gives `stopped`, the backup labelled the same way, and the run ends (`--resume` refuses).
  - **P3** (a non-held error, errno 1117 with no winerror): `stopped`, labelled `save_not_verified`, and the run ended.
  - `written_unverified` is its own key in `results.jsonl`, `summary.json` and the `Done:` line.
  - `--resume` treats it as done. It refuses only after `stopped`. Recovery (`recover_entry` → `finish`) can return it too.
  - No other code reads merge-tool outcomes; I grepped the app, the tools and the shell.
- **New in the delta:**
  - **w8 [Minor]** `app.py:1142-1153` (residual of W1, inherited limit): the size-and-mtime signature can't see a same-size edit whose file date is put back (P1d: overwritten). The gap between `check()` and `MoveFileExW` is microseconds.
    - This is the same signature the app has used for every change check since 0.1.x (`:1128`, the plan's `PLAN_KEYS`, recovery). A tagger that rewrites ComicInfo almost always changes the size.
    - No fix needed for this release. A content hash at the rename would cost a full read of every comic.
  - **w9 [Minor]** `tools/nested_comicinfo_merge.py:575-586`, `batch.py:230-252`: **a write refused because another program changed the comic leaves an unlisted, full-size backup.** This path existed before, at `:1128`; W1 now also leads to it.
    - The merge tool prints only `skipped <name>`. The kept backup is mentioned only as a `note` in `results.jsonl`, and is not in Kept backups. The worker doesn't list it either.
    - Approve does list it, as "Save not verified", although CMO never wrote the comic.
    - Nothing is lost: it is a copy of the comic as it was before the other program's edit.
    - **Fix:** label it in Kept backups with its own reason (for example "Not saved; another program changed the comic"), and print the note on the console.
- **Unchanged by the delta, still open:** w1, w2, w4, w5, w6, w7 and the §3 note outside the range. w7(c) still stands: the `make_durable` comment still says "the engine it writes through (0.6.8) does not retry".
- **Remaining ways the real-library merge could overwrite or lose data.** I looked for more after the fix and found none beyond w8.
  - Before the write: the tool compares the plan keys and hashes the original under the write lock. The writer then re-checks the root values and the nested entry, the signature after the temporary archive is built, and the signature before every rename.
  - After the write: the archive is checked against its backup and its records are saved. The backup is deleted only after the archive and its folder are flushed and the backup's hash matches the original.
  - Under recovery: an archive another program changed after a crash fails `verify_written` or is classed as "changed" by the app's recovery. Either way it is `stopped`, and nothing is deleted.
  - Throughout, the tool holds the comic's write lock from its hash to its backup's deletion, so the app's worker can't write in between.
- **Targeted tests at 105a25a.** `test_0_state_isolation`, `test_review_068_fixes`, `test_review_067_fixes`, `test_nested_comicinfo`, `test_nested_comicinfo_merge`, `test_storage_durable`, `test_conversion`, `test_write_safety`, `test_kept_backups`, `test_batch_060` and `test_zz_state_isolation`: **145 run, all passed, none skipped** (bundled runtime). `git diff --check 4874894..105a25a` is clean. Ender's full suite: 1395 OK at ec56d8a.

---

## Rubric

### 1. Security

- Status: Pass. No shell-out changed (7-Zip arguments untouched), there is no new path interpolation, no Electron or IPC change, and no secrets are involved. The one new log line (`library_lock.py:138`) names a lock file and an OS error, and goes to `engine.log`.

### 2. Correctness & Logic

- Status: Concerns.
- **w2 [Minor]** `tools/nested_comicinfo_merge.py:633-648` (`remove_backup`): **the wait misses a holder that does not share read access.**
  - `remove_verified_backup` hashes the backup through Python's `open()`. On a sharing violation that raises `PermissionError` errno 13 with `winerror` None (P2). Only `os.unlink` sets winerror 32.
  - So a holder that blocks reading is not waited out, although the docstring says it is ("without sharing read or delete"). The archive gets `stopped` and the run ends at once, which is 0.6.8 behaviour.
  - This fails safe: the backup is kept and so is the stop.
  - **Fix:** also wait on `PermissionError` with errno 13 from the hash read, or correct the docstring.
- **w3 [Minor]** `tools/nested_comicinfo_merge.py:607-616`, `:988`: **`skipped` covers more than a held archive, and the totals hide rewrites.**
  - (a) After the wait, *any* `OSError` from `make_durable` becomes `skipped`, and the run carries on. That includes a file gone, an I/O error, or a network drive dropping. Until 0.6.8 every flush failure stopped the run. The Brief and RECOVERY step 3 do say "or another error", so this is documented. But it is wider than "held", and a non-held flush failure usually points to the drive itself. The next archive's write will then fail on that drive (usually `stopped`), so the blast radius is one more archive. Nothing is lost: the backup was flushed before the rename (0.6.8 R1).
  - (b) `summary.json` and the `Done:` line count a rewritten-but-unproven archive under the same `skipped` key as archives the run never touched. The console line and `results.jsonl` do carry the reason and `kept_as`.
  - **Fix:** stop the run on a flush error that is not error 32, and give the held case its own outcome or count key (for example `written_unverified`).
  - **Resolved in the delta** (ec56d8a, 105a25a); see § Delta review.
- Also see W1 (§5): the rename retry's missing re-check is a correctness gap as well as a data-safety one.
- **Verified clean:**
  - `replace_durably` and `_open_handle` retry only error 32 (and error 5 on a comic that isn't read-only). Any other error is raised at once. `left` is always set before the sleep. A rename that never goes through leaves the comic unchanged, with the temporary file and the pending record cleaned up (tests cover this).
  - A read-only comic is refused at once.
  - The `apply` loop labels a kept backup for both `skipped` and `written` with `kept_as`. `--resume` treats both as done, and does not refuse.

### 3. Crash / Stability Safety

- Status: Concerns.
- **w5 [Minor]** `storage.py:76-86`, `:121-132`; `app.py:1101-1142`: **the waits add up.**
  - One app write can now wait 10 s on the backup's flush, 10 s on the temporary archive's flush and 10 s on the rename, on top of its own work. A Quit during that can pass the 30 s Closing cap and end in a forced kill mid-write.
  - The Q2 pending-write record recovers it at the next start, so this costs time, not data.
  - None of the waits checks pause or stop.
- **Outside the range (r2 residual), [Minor]** `tools/nested_comicinfo_merge.py:705` (`merge`): `verify_written` has no `try` around it.
  - A holder that blocks reading the archive or backup *during the check* still raises out of `apply` with a traceback, and `summary.json` is not written.
  - The journal has `start` and `written`, so `--resume` finishes the archive. This is data-safe, but it is still a run-stopper of the same kind r2 set out to remove.

### 4. Performance

- Status: Concerns.
- **w5 (cont.) [Minor]** `tools/nested_comicinfo_merge.py:640-648`: each retry in `remove_backup` calls the whole `remove_verified_backup` again. That re-hashes the full backup (hundreds of MB for some comics) up to every 0.5 s for 30 s, while another program holds that file.
  - **Fix:** hash once, then retry only the `unlink`. The folder and name checks can run again; they are cheap.

### 5. State & Data Safety

- Status: Concerns.
- **W1 [Major]** `storage.py:66-86` (`replace_durably`), with `app.py:1128-1142` (`_write_metadata_guarded`): **the rename wait overwrites a change another program makes during the wait.**
  - The writer checks the comic's size and mtime at `app.py:1128`. After that it saves the nested record and the pending record, flushes the temporary archive (up to 10 s on a held temporary archive), and renames. The rename now retries for up to 10 s while another program has the comic open.
  - Nothing compares the comic again before a retried rename succeeds. Whatever the holder wrote during the wait is replaced by an archive built from the comic as it was before.
  - The backup was copied before the change, and Approve, the worker and the merge tool all delete it once its SHA-256 matches the pre-write original. So the change exists nowhere afterwards.
  - Reproduced: P1 (the app writer) and P1b (the merge tool: `written`, backup deleted). The positive control shows 0.6.8 refused the rename and kept the edit.
  - **Reachability.** It needs a program that writes the comic and holds it open across the rename (a tagger such as ComicRack, ComicTagger or Mylar, or a sync tool). The wait is triggered only when someone holds the file, which is exactly when a concurrent edit is possible. CMO's own writers can't trigger it because they take `comic_write_guard`. Graded Major, not Critical, on the same basis as v0.6.8's R3 (a narrow window, a rare precondition).
  - **Fix:** pass `replace_durably` the destination's expected `(size, mtime_ns)`, or a check callback. Re-stat the comic before every attempt after the first, and after the temporary file's flush. Raise `ArchiveChanged` if the comic differs or is gone. That brings the window back to the pre-0.6.9 microseconds. A test like P1 should fail before the fix and pass after it.
  - **Resolved in the delta** (eb71d0d); see § Delta review. Its residual is w8.
- **w1 [Minor]** `library_lock.py:117-140` (`_open_claim`): **a mutual-exclusion check that now fails open.**
  - A claim lock that can't be opened even read-only is now "not counted". If its owner is alive, a second state root claims an overlapping library (P4: both held).
  - The old comment ("Unopenable is not proof that its owner has gone") was right for a gate. `engine_host.held_claims` can fail open because it only decides how long to wait at start.
  - Futaba's case (a read-only, unheld lock) is fully fixed by the read-only fallback alone. The "not counted" branch isn't needed for that case.
  - Reachability is very low: the locks live in a per-user `%LOCALAPPDATA%` folder, and owners open them with shared access. It is irrelevant to the merge run, which uses the app's own state root, where `comic_write_guard` does the separating. Nothing unique would be lost either: each writer keeps a backup of the original, and the ledger records the values.
  - **Fix:** keep the read-only fallback, and treat a lock that can't be opened at all as live (`LibraryBusy` has Try again), at least for a sharing violation.
- **w4 [Minor]** `archive_conversion.py:142` (R3): **conversion now renames through `replace_durably`, which replaces an existing file and waits for a held one.**
  - Conversion's target must not exist, but that is checked only at `:101` and `:136`. If a file appears there and is held in that gap, it is now waited for and then overwritten. `os.replace` refused it at once. Reachability is negligible.
  - **Fix:** use a write-through rename without `MOVEFILE_REPLACE_EXISTING` for conversion.
- **Verified clean:**
  - **R3** (see the Summary). The test's Disk model puts the CBZ on the disk, renamed with write-through and its folder flushed, before the unlink. A flush failure keeps the original and puts no CBZ in place.
  - **The held-backup `written` branch** deletes nothing (see the Summary).
  - **The `skipped` (unflushed) branch** keeps the backup. That backup was flushed by the 0.6.8 R1 change. The dropped values and the nested copy are in `--out` and in the app's `data/removed-nested-copies.jsonl` before the flush. `--resume` leaves the archive alone.
  - **New deletions:** none. `remove_backup` reuses `remove_verified_backup`, which is SHA-gated and checks the folder and name. Conversion's delete is unchanged and now runs after a durable rename.

### 6. Input Handling

- Status: Pass. **r7(b) is resolved:** `csv_rows_end` holds at all 17,200 cut points (P3), because `csv.writer` always quotes a value that holds a quote, comma or line break, and doubles the quotes inside it.
- **Inherited, open:** **r7(a) [Minor]** `read_lines` still refuses a torn *last* line that ends in a newline (its middle zero-filled). Not touched in this range.

### 7. Maintainability (no Critical findings on its own)

- Status: Concerns.
- **w6 [Minor]** The same deadline-and-backoff loop is now written out four times: `storage.replace_durably`, `storage._open_handle`, the tool's `open_for_flush` and the tool's `remove_backup`. The tool's `make_durable` copy of the flush (r5(a), inherited) now has its own retry too.
  - **Fix:** one `storage.retry_while(predicate, wait)` helper. The tool could call `storage.flush_file`/`flush_directory` now that it requires an engine that has them.

### 8. Doc/Code Drift (no Critical findings on its own)

- Status: Concerns.
- **w7 [Minor]**
  - (a) The `remove_backup` docstring and the Brief say it waits out a holder "without sharing read or delete". It waits only for a delete refusal (w2).
  - (b) "Waited out for 30 s" (RECOVERY step 3, the Brief, the reason text) is per handle. `make_durable` opens the archive and then its folder, each with its own 30 s deadline, so the worst case is 60 s.
  - (c) The `make_durable` comment says "the engine it writes through (0.6.8) does not retry". That stops being true once 0.6.9 is installed, and `--engine` defaults to the installed app.

### 9. Build & Release Hygiene

- Status: Pass, conditional.
- **Pending bump:** `VERSION` still reads 0.6.8, and `CHANGELOG.md` has no 0.6.9 entry. This clearance assumes Sully's next commit changes only the version, the lockfile and a CHANGELOG naming the items in the Summary.
- **Diff and tree:** `git diff --check 27647d8..105a25a` is clean, and the tool is not packaged. The working tree was clean at the start of both passes. This report is its only change, left uncommitted. No test output was left in the checkout: test scratch went to `I:/AI Projects/Temp/senua-069/`, and that folder was removed after each pass with the approved sweep.

---

## Patterns

The same shape as v0.6.7 Q1 and v0.6.8 R1, R3. A fix proves one step and leaves the next step resting on an old proof. Here the wait was added between the check that the comic is unchanged and the rename that relies on that check. Any wait added in front of a destructive step should re-check that step's precondition. The delta does exactly that: `check=` runs before every attempt.

---

## Verdict

- Total Critical: 0
- Total Major: 4 open.
  - New and open: none.
  - Inherited, untouched: M1, M2, I1, I2.
  - Resolved: R3 (from v0.6.8); W1 (from this review, in the delta).
- Total Minor: 8 new and open (w1, w2, w4–w9), plus 1 outside the range (`verify_written`, §3).
  - Inherited, untouched: r3, r4, r5, r6, r7(a); q3, q5 (c and d), q6, q7, s1–s11, n1–n5, i1, t3, t4.
  - Resolved: r2 (residuals w2 and the §3 note) and r7(b), from v0.6.8; w3, from this review, in the delta.
- Safety floor: intact.
  - No Electron preference or IPC change.
  - Every write is in scope: the app's state folder, the user's library through the app's writer and the converter, and the tool's `--out`.
  - The range adds no new deletion path. The backup delete stays SHA-gated and location-checked. Conversion's delete now follows a durable rename and a full content check.
  - No secret handling, and no repository-integrity change.

**Verdict:** RELEASE CLEAR

This clears construction for source commit 105a25abcacf4d31d34e0700e693c12947f4cc57 (range 27647d8e56732c490a697eabfc0ea14687c83b76..105a25abcacf4d31d34e0700e693c12947f4cc57), plus a bump that changes only the version, the lockfile and the changelog. It does not prove installer behaviour, the QA entry gate or publication.

- **Before the real-library apply run** (not a release gate):
  - W1 is fixed: an outside program's edit during the wait is now refused, and both the edit and the backup are kept.
  - Prudent, not required: don't run another tagger during the apply. The only thing the signature can't see is a same-size edit that also puts the file date back (w8).
  - Read `results.jsonl`, not just the `Done:` counts:
    - `written_unverified` means rewritten but not proven flushed; its backup is kept and listed.
    - `skipped` with a `note` "backup kept" means another program changed that comic, and its pre-edit backup is left unlisted in that folder's `.comic-metadata-backups` (w9).
    - Any other flush error now ends the run with `stopped`, and `--resume` refuses: make a new dry run and use a new `--out`.
- **First items for Ender's next cycle:** w1 (claim lock fails open), w9, w2, then w4.
