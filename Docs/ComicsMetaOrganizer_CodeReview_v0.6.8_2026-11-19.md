# Code Review — Comics Meta Organizer v0.6.8

## Header

```text
Reviewer: Senua (Code Reviewer)
Date: 2026-11-19
Tool: Comics Meta Organizer (Comic Metadata)
Release: v0.6.8 (version bump not yet made; Sully's version-only bump commit follows)
Commit range: 0771691f8ad5607e73988b4fb97998d2a0c62548 (main, "Docs: v0.6.7 release receipt")
              ..a4d23f7a78f7e1f70bb910f3b6a4bbe92db3d0ca (ender/0.6.8-fixes, "r1: a torn last line never stops --resume or --recover")
Reviewed head: a4d23f7a78f7e1f70bb910f3b6a4bbe92db3d0ca
Reviewed in two passes:
              1. 0771691..c3553138d9c65ed8ac00c0042039f6b1f20cd993: 10 commits (141af30 .. c355313), the Summary and Rubric below.
              2. c355313..a4d23f7: 4 commits (643dd9c, c302e3e, f059556, a4d23f7), the answers to this review's R1, R2
                 and r1; § Delta review.
Commits: 14 (141af30 .. a4d23f7)
Files changed: 19 files, +1614 / -113 in all.
               Without Docs/: 17 files, +1518 / -106.
               Product: app.py, storage.py, provenance.py, engine_host.py, tools/nested_comicinfo_merge.py,
               desktop/engine.cjs, graceful-stop.cjs, main.cjs, stopping.js (9 files, +793 / -95).
               The delta alone: app.py and the tool +162 / -30; tests and the Brief besides.
               Tests: tests/test_review_067_fixes.py (new), test_nested_comicinfo.py, test_nested_comicinfo_merge.py,
               test_engine_host.py, test_write_safety.py; desktop/tests/engine-spawn, quit-always, quit-pages.
               Docs: Brief, Judy's Quit spec rev 3.
Base check: 0771691 is docs-only on top of the v0.6.7 build 9d1ad1a (git diff 9d1ad1a 0771691: the v0.6.7 review,
            Tray QA and release receipt). The range is the whole of 0.6.8's code.
Stand-down dimensions: none
```

---

## Summary

The first pass (to c355313) is below. The second pass (to a4d23f7), which fixes R1, R2 and r1, is in § Delta review. The Verdict covers both passes.

The range answers the v0.6.7 review and two Sergei items:

1. **Q1:** the writer flushes the temporary archive and renames it with write-through (`storage.replace_durably`). The merge tool flushes the archive and its folder before it deletes a backup (`make_durable`).
2. **q4:** `--resume` and `--recover` for the merge tool, a journal in `--out`, and written recovery steps.
3. **Q2:** a durable pending-write record per write. The next start, or that comic's next write, finishes or undoes a half-done write.
4. **Q3:** only the current broker's exit changes the shell's engine state.
5. **q1:** only a real lock conflict counts as a held claim.
6. **q2:** a nested-only copy follows the merge's left-out rules. The whole removed copy goes to `data/removed-nested-copies.jsonl` before the rename.
7. **Sergei 2026-11-19:** values with ledger source `nested-comicinfo-merge` are correctable by enrichment.
8. Judy's rev 3 Quit copy.

**Answers to the brief's questions, short:**

- **Can the pending-write recovery wrongly undo a completed write?** No.
  - A completed write is recognized by the archive's signature, which equals the `after` saved before the rename. Probe A shows the flush keeps the signature.
  - "Undone" needs the signature to equal `before`. Even then it deletes only the temporary file. It deletes the backup only when the backup's SHA-256 equals the comic's current bytes, through `remove_verified_backup`, which also checks the folder and name.
  - A signature that is neither leaves the comic and the backup alone.
- **Can it delete a backup or the only good copy?** No path found. Every deletion, in the app's and the tool's recovery, is SHA-gated against bytes that are still in place.
  - But the backup that recovery keeps is never flushed (R1; fixed in the delta).
  - And on any "stopped" result, the merge tool's dropped nested values live only in that backup (R2; fixed in the delta).
- **Races with the running app:** sound. The app's recovery takes the comic's write guard and gives up on a held one (record kept). It re-reads the record under the guard.
  - Probed with two processes (probe C). A start's recovery ran while a real write was paused at its rename in another process. The record was left alone ("kept for the next start"). The write then finished with its history, and the record was removed.
- **Tool and app recovering the same write:** they serialize on the same guard. The second one finds the record gone. The tool's own steps after that are SHA-gated against the start's `original_sha256`.
- **A crash at each step:** the app writer's steps are recoverable, except that the backup's bytes may not be on disk after a power cut (R1; fixed in the delta). The tool's steps are recoverable while the journal reads.
  - A power cut that tears the journal's or results' last line makes `--resume` and `--recover` die (r1, probed; fixed in the delta, residual r7).
- **Does the write-through rename make the data durable on Windows?** For the comic, yes:
  - `FlushFileBuffers` on the temporary file, then `MoveFileExW(REPLACE_EXISTING | WRITE_THROUGH)`.
  - The NTFS log is sequential, so a later backup deletion cannot reach the disk without the rename.
  - Probe B confirms the comic is flushed before the write returns, and the backup is not (R1; at a4d23f7 both are, probe E).
  - The same fix was not carried to archive conversion, which deletes the original CBR outright (R3, outside the range).
- **Does item 7 let enrichment overwrite anything other than merged values?** No.
  - `provenance.correctable` matches only `in-book:*` or exactly `nested-comicinfo-merge`.
  - Only the tool writes that source, with writer `automatic`.
  - Its ledger `written` lists only the tags `merge_comicinfo` filled into an empty root (`fields={}`, and the root fields are pinned by `expected`).
  - The chain still breaks at the first manual write or signature gap.
  - Nested-only values carried into a root copy are not in any `written`, so they stay frozen, as the Brief says.
- **Q3, q1, q4 (as written), q5(a), q5(b):** resolved. **Q1, Q2, q2:** resolved, with the residuals below.

**Targeted tests** (scratch `I:/AI Projects/Temp/senua-068/`, removed afterwards):

| Set | Interpreter | Result |
|---|---|---|
| Python: `test_0_state_isolation`, `test_review_067_fixes`, `test_nested_comicinfo`, `test_nested_comicinfo_merge`, `test_engine_host`, `test_write_safety`, `test_in_book_replacement`, `test_storage_durable`, `test_kept_backups`, `test_zz_state_isolation` | System Python 3.14.10, `COMICS_META_HELD_TEST=1`, `COMICS_META_TEST_PROTECTED_ROOTS=[]`, `COMICS_META_TEST_SCRATCH` in scratch | 139 run, all passed |
| Shell: `engine-spawn`, `quit-always`, `quit-pages`, `engine`, `graceful-stop` | Node 26.13.1 | 68 run, 67 passed. The 1 failure is environmental: `engine.test.cjs`'s lock-holder test needs `COMICS_META_TEST_PYTHON`. Re-run with it: 20 of 20. |

**Probes** (scratch only; no live app, `%LOCALAPPDATA%\ComicsMeta`, library or installer touched; state root and lock folder set to scratch before `app` was imported):

- **A. Windows facts on the scratch volume (NTFS):**
  - `storage.flush_file` and the tool's `make_durable` keep the archive's size and mtime.
  - After `replace_durably`, the comic's signature equals the temporary file's pre-flush signature, so recovery's `after` match holds.
  - `flush_directory` works on an NTFS folder.
  - With a reader holding the comic open with `FILE_SHARE_READ` only, `make_durable` raised `PermissionError` (Windows error 32) (r2).
  - The tool's `read_lines` on a `journal.jsonl` with a NUL-filled tail raised `JSONDecodeError` (r1).
- **B. What a write flushes.** A real Approve-style write (`overwrite_fields=('Writer',)`, `verify_readback=True`), with `os.fsync` recorded:
  - comic flushed before return: True;
  - backup flushed before return: False;
  - the replaced value ("Keith Giffen") is then only in the backup (R1).
- **C. Recovery beside a live write.** Two processes, as above: the record was kept, the write completed with 1 history row and the new value, and no record was left.

---

## Delta review: c355313..a4d23f7

Four commits answer R1, R2 and r1 below. I read them red-team style for data safety.

**R1, resolved** (`643dd9c`, `f059556`; `app.py:814-826` `_flush_copy`, called at `:1101`):

- The backup is flushed right after `shutil.copy2`, before the temporary archive is written. The order is now: record on disk, then backup on disk, then archive flushed, then write-through rename.
- `attempt['backup']` is set before the flush. So if the flush fails, the caller still knows which backup this call made, and its F29 handling removes or keeps it as before (the comic is unchanged).
- **A read-only comic:** `copy2` copies the read-only bit to the backup. The bit is lifted only for the flush and then put back in a `finally`. A kill in between leaves a writable backup, which is harmless.
- **Probe E:**
  - A writable comic's backup was flushed before the write returned (it was not in probe B).
  - A read-only comic's backup was flushed, reported in `attempt`, and still read-only afterwards. The write then failed at the rename, as it did before 0.6.8, and the comic was unchanged.
- Also checked: the flush adds no new deletion; a failed flush is a failure before the rename, with the record removed.

**R2, resolved** (`c302e3e`; `app.py:276-330` `merge_left_out` and `removed_nested_copy`, called at `:1135`; the tool's `label_kept_backup`, `tools/nested_comicinfo_merge.py:603-613`):

- **The record now comes before the rename.** For a merge, the writer itself appends the whole nested copy (`xml_base64`) and each value the root did not take (with why and the root value kept) to `data/removed-nested-copies.jsonl`, fsync'd, before the rename. This is the same place and order as q2's nested-only copies.
- **No path leaves a value only in a backup.** On every path that can rewrite the archive (interrupted, stopped, failed check), every nested value is recorded before the archive changes. The record is on the app's own drive (`%LOCALAPPDATA%`), flushed before the library drive's rename.
- **What the extra steps change:** `merge_root` is a deep copy taken before `merge_comicinfo`. `nested_raw` is read after the planned name, CRC and size were matched, so its size is the dry run's, under the 2 MB cap. Neither changes what is written. If the record cannot be written, the write fails before the rename, with nothing written.
- **A stopped archive's backup** is now listed as "Save not verified". When only its deletion failed after verification, recording and flushing, it is listed as "Saved; backup could not be deleted". The misleading label from R2 is gone. A backup labelled that way now really holds nothing that is not recorded elsewhere.
- **Appends from several processes:** the dashboard, the worker and the tool can all append to that file. I checked that concurrent appends do not lose lines. Two processes appended about 7,900 lines with the writer's exact `'ab'` pattern, and none was lost or damaged (probe D).
- **A torn line in the app's file** is now set apart by a newline before the next line, so a power-cut tail no longer swallows the next record.

**r1, resolved, with a small residual** (`a4d23f7`; `tools/nested_comicinfo_merge.py:767-817`, and `check_resume_folder`):

- **How it works:**
  - `read_lines` leaves out the bytes after the last newline, which are an append that was torn.
  - A damaged line before that refuses, and nothing is changed.
  - `--resume` and `--recover` first check every `.jsonl` in `--out`. Only then do they move each torn tail to `<name>.torn` (kept as evidence) and cut it off.
  - `run.json` is now written with `x`, flushed and fsync'd.
- **Probe A's case now passes:** a NUL-filled tail is left out.
- **r7 [Minor, new]** (residual), `tools/nested_comicinfo_merge.py:770-817`:
  - (a) A torn **last** line that still ends in a newline (its middle zero-filled, for example an append that crossed a page boundary) counts as "damaged" and refuses. A hand edit is then needed again. Probed.
  - (b) `cut_torn_tail` also runs on `dropped-nested-values.csv`, whose quoted values (a "root wins" Summary) can contain newlines. A tear inside such a value is cut at its inner newline, which leaves an open quote. A CSV reader then swallows every later row into that value. Probed. The bytes are all still in the file and `.torn`, and the JSON records are complete.
  - **Fix:** treat a bad *last* line the way a torn tail is treated. Leave the CSV alone, or cut it only at a row boundary.

**Targeted tests (delta):** `test_0_state_isolation`, `test_review_067_fixes`, `test_nested_comicinfo`, `test_nested_comicinfo_merge`, `test_write_safety`, `test_storage_durable`, `test_kept_backups`, `test_manual_backup_cleanup` and `test_zz_state_isolation`. 118 run, all passed (same interpreter and isolation as above). No shell file changed in the delta, so no shell tests were re-run.

**Probes (delta)** (scratch only, as above):

- **D.** Two processes appending to one file, each opening it with `'ab'`, checking the last byte, writing and flushing per line (the writer's pattern): about 7,900 lines, 0 lost, 0 damaged.
- **E.** The R1 and r1 cases above.

---

## Rubric

### 1. Security

- Status: Pass.
- **Electron:** no preference or IPC change. The rev 3 Quit copy is set with `textContent` only, and the numbers are the shell's own (`engine.closureWaitS`).
- **New writes are in scope:** `data/pending-writes/` and `data/removed-nested-copies.jsonl` are in the app's state folder. The temporary file and backup sit beside the comic in the library. The tool writes only its `--out`.
- **Record names** are the SHA-256 of the path's identity, so a path never reaches a file name.
- **Flush handles:** they are opened `OPEN_EXISTING` with all sharing, and nothing is written through them.
- **No shell-outs.** No secrets in the diff (`git diff --check` is clean). The tool is not packaged.

### 2. Correctness & Logic

- Status: Concerns.
- **r4 [Minor]** `app.py:151-170` (no 0.6.8 counterpart), with `automatic.py:386`: **q2 does not re-read catalog rows read under 0.6.7.**
  - Nested-only rows that 0.6.7 read (its `nested_recheck` and ordinary scans) keep the nested Year/Month/Day, PageCount, twins and year-Volume in `comics.metadata`. The folder scan re-reads only changed files.
  - The worker plans from that stored metadata. Fill-empty therefore still skips the cover date, while the 0.6.8 write leaves the nested Year out.
  - The first 0.6.8 write of such a comic leaves it with **no Year** until that folder's next pass. Imprint splitting also uses the stale store-date year. The dashboard shows the dropped values meanwhile.
  - Nothing is lost: the nested copy goes to `removed-nested-copies.jsonl`.
  - **Fix:** queue those rows once, like `queue_nested_recheck` (for example rows whose stored metadata came from a nested-only copy, or every `embedded` CBZ row once).
- **r2 [Minor]** `tools/nested_comicinfo_merge.py:538` (`make_durable`, called from `finish`): **a reader that does not share write access stops the whole apply.**
  - `FlushFileBuffers` needs a handle with write access. A reader that opened the comic with `FILE_SHARE_READ` only makes `CreateFileW` fail at once (probe A). A thumbnailer reacting to the change during `verify_written` is the likely case.
  - The result is "stopped". The values are already saved and the backup is kept. But the run ends, and `--resume` then refuses.
  - The flush is redundant with the ≥0.6.8 engine the tool now requires: that engine already flushes before its write-through rename.
  - **Fix:** retry a sharing violation for a few seconds. Or keep only the folder flush, and fail only on errors other than a sharing violation.
  - **Since the delta:** `storage.flush_file` (no retry either) also opens the fresh backup with write access. A scanner holding a `.bak` open without sharing write fails that write before the rename. The comic is unchanged and the comic is retried later, so this costs time, not data.
- **Resolved:**
  - **Q3:** `desktop/engine.cjs:62-63` captures the child, and the exit handler returns unless `this.child===child`. The test has a positive control: the current broker's exit still counts.
  - **q2:** in substance, with the residual r4.
- **Verified clean:**
  - **Recovery classification** (`app.py:850-866`): `after` is checked before `before`, so equal signatures cannot undo a renamed write. A renamed write whose fields do not read as planned is "not verified": no history, backup kept. A history row already present is never duplicated (`already recorded`).
  - **The writer's ordering** (`app.py:1033-1078`): the record is saved before the backup. Its `after` is saved before the rename. It is unlinked only after the history commit, or on a failure before the rename.
  - **The tool's resume:** `done` skips paths with any result; `--recover` starts nothing new; a `stopped` last result refuses both modes; the plan is pinned by SHA-256 in `run.json`.
  - **Item 7**, per the summary.

### 3. Crash / Stability Safety

- Status: Concerns.
- **r1 [Minor; resolved in the delta, residual r7, § Delta review]** At c355313: `tools/nested_comicinfo_merge.py:754-760` (`read_lines`), `:579-585` (`already_saved`), `:768-780`: **a torn last line makes `--resume` and `--recover` die.**
  - The journal and results are appended and fsync'd line by line. A power cut during an append can still leave a cut-short or NUL-filled tail: the same zero-fill seen on 2026-11-13.
  - `json.loads` then raises an uncaught `JSONDecodeError`, both at the start of `--resume`/`--recover` and in `finish` (probe A).
  - That is exactly the "power cut" case RECOVERY step 2 sends Sergei to. Then RECOVERY step 1 forbids touching `--out`, so only a hand edit unblocks it.
  - `run.json` is written without a flush. If it is lost, `--resume` refuses, and a fresh apply refuses the non-empty folder.
  - `data/removed-nested-copies.jsonl` has the same tail problem: the next append joins the torn line, so that record cannot be parsed line by line.
  - Nothing is deleted on any of these paths.
  - **Fix:** skip an unparseable **last** line with a warning (and refuse on any other bad line). Flush `run.json` like the journal.
- **Bounded:** recovery at start runs inside the shell's `library` phase, so the 600 s start budget applies and the 20 s reachability check keeps getting answers. The terminal path recovers before it binds, as designed.
- **Recovery is idempotent:** a stop during it repeats the same outcome, or gives `already recorded` or `gone`.
- **Inherited, untouched:** **q3 [Minor]** `desktop/main.cjs:107`, `desktop/engine.cjs:46`. A frozen broker leaves the engine running headless after Quit, and the next start reports a port conflict.

### 4. Performance

- Status: Pass.
- **Per write:** two durable record saves (each an fsync plus a write-through rename), one unlink, and a `FlushFileBuffers` of the temporary archive. The flush waits for bytes that are written anyway; on the worker's write rate this is tens of ms per comic.
- **The tool:** `already_saved` re-parses the whole `--out` jsonl for each archive. That is quadratic, but bounded at 356 archives of a few KB each.

### 5. State & Data Safety

- Status: Concerns.
- **R1 [Major; resolved in the delta, § Delta review]** At c355313: `app.py:1036` (`shutil.copy2(path, backup)`, never flushed), with `app.py:1078`: **the backup is not on disk when the write-through rename makes it the only copy of the original.**
  - Q1 now flushes the new archive before the rename. But the backup is a cached copy.
  - The rename's write-through flushes the NTFS log, including the backup's creation and size, but not its bytes.
  - After a power cut or BSOD in the lazy writer's window, the comic is correct, but the backup can come back full size and zero-filled (the 2026-11-13 pattern).
  - What is lost: every value the write replaced (Approve's `Web` and the batch's `changes`). For the merge tool, it is also the dropped nested values until `save_record` runs, after a full CRC re-read that takes minutes on large archives.
  - Recovery would then record history pointing at a zero-filled backup and label it "Saved; backup could not be deleted".
  - Probe B shows that no flush is ever made on the backup.
  - **Grade:** Major per the brief's floor for backups. It is not Critical: it needs a power loss inside a window of seconds, the comic itself is intact, and 0.6.8 is strictly safer than 0.6.7 here.
  - **Fix:** `storage.flush_file(backup)` right after `copy2`, before the temporary archive is written. The order is then: backup on disk, then comic replaced.
- **R2 [Major; resolved in the delta, § Delta review]** At c355313: `tools/nested_comicinfo_merge.py:648-651` and `:742-749` (`save_record` runs only inside `finish`, after `verify_written` passes), with RECOVERY step 4: **on any "stopped" result the dropped nested values live only in a kept backup, and the documented path abandons them there.**
  - **Where the values are:** the tool writes the dropped values and the removed nested copy to `--out` only after the check passes. A failed check, "no backup equal to the original", or an interruption between the rename and `save_record` (Ctrl+C during the long `verify_written`, a kill, a power cut) leaves them only in the backup.
  - **Item 7 widens it:** with the app running between the interruption and `--resume`, enrichment may now replace a merged value of that comic. `verify_written` then fails, and the result is "stopped".
  - **The documented path:** after a "stopped", `--resume` and `--recover` refuse. RECOVERY step 4 says to make a new dry run with a new `--out`. That dry run no longer plans the archive, because it is root-only now. Nothing ever writes those values to `--out`, against the Brief's "the `--out` folder keeps the record of every dropped nested value".
  - **The label:** the backup is listed in Kept backups as "Reason not recorded". If the app's start recovered the tool's pending record, it is listed as "Saved; backup could not be deleted" (`app.py:866-869`, `record_backup=True`), which reads as safe to delete.
  - **What it takes to lose them:** the code never deletes the backup. The loss needs a manual delete, against RECOVERY step 1, of a backup labelled redundant.
  - **Fix (preferred):** in `_write_metadata_guarded`, call `removed_nested_copy` for a merge drop too, before the rename, as q2 already does for nested-only copies. Then no nested value ever exists only in a backup, for the app or the tool. At the least, run `save_record` from the backup before `verify_written`, and tell step 4 to save it.
- **R3 [Major, outside the range: `archive_conversion.py` is untouched since 0.6.0]** `archive_conversion.py:134-147`: **Q1's pattern, unfixed, in CBR/CB7→CBZ conversion, and worse.**
  - The new CBZ is written, `os.replace`d (no flush, no write-through) and verified from the OS cache. Then the **original is deleted** (`(retained if same else source).unlink()`). There is no backup at all.
  - After a power cut in that window, the CBZ can be zero-filled while the deletion is kept.
  - Conversion runs automatically from the worker (`automatic.py:349`). The Brief's last inventory found no CBR in the library, so reachability today is low.
  - **Fix:** `storage.replace_durably(temporary, final)`, so the bytes are flushed before the rename, before the original goes. This is distinct from the inherited M2 (an identity gap at `:161`). It was missed in the v0.6.7 review's list of Q1 sites.
- **r3 [Minor]** `app.py:822-838` (c355313): **the set-aside treats transient errors as permanent.**
  - Any `OSError` reading a record moves it to `.unreadable` for good. That includes a `PermissionError` lasting longer than `read_text`'s 1 s retry.
  - So does a name mismatch, and `pending_write_path` depends on `realpath`, which resolves links, mapped drives and junctions only while they are reachable.
  - It is never retried. A second set-aside of the same record overwrites the first `.unreadable`.
  - The comic falls back to 0.6.7's state: a temporary file that blocks writes until Folder help, or a written comic without history. No data is lost.
  - **Fix:** set aside only on a parse or schema failure. On `OSError`, keep the record (as "kept for the next start"). Compare names only when the comic's path resolves.
- **Resolved:**
  - **Q1** for the archive. Every caller that deletes a backup (Approve, the worker's batch, `remove_verified_backups`, comic recovery, the tool) now does so after `replace_durably` returned. The tool also flushes the archive and its folder first.
  - **Q2:** the Closing cap may still stop a manual write, but recovery covers it. The comment and the Brief no longer claim otherwise.
  - **q4.**
- **Verified clean:**
  - **The tool's undo path** deletes only backups of that archive, made since the attempt began, whose SHA-256 equals both the original and the current comic.
  - **`finish`** saves the record once (`already_saved`), flushes, journals `verified`, and only then deletes.
  - **The app's `undone`** deletes the temporary file only under the guard, with the comic's signature equal to `before`.
  - **The nested-only write** saves the whole nested copy, fsync'd, before the rename.
- **Inherited, untouched in range:**
  - **M2 [Major]** `archive_conversion.py:161`.
  - **t3 [Minor]** `progress_snapshot.py:83/:110`.
  - **n1 [Minor]** `storage.py:162-165`.

### 6. Input Handling

- Status: Concerns.
- The new readers check their input:
  - the pending record: schema, types, and its name against its own path;
  - `run.json`: the plan's SHA-256;
  - records are written with `ensure_ascii=True`, so unpaired surrogates in paths save.
- The torn-line case is r1 (§3).
- **Inherited, untouched:** **q6 [Minor]** `engine_host.py:361` (a non-finite `written` is never checked or retired); **n2**, **s6**, **i1 [Minor]**.

### 7. Maintainability (no Critical findings on its own)

- Status: Concerns.
- **r5 [Minor]**
  - (a) The tool's `make_durable` (`tools/nested_comicinfo_merge.py:507-553`) duplicates `storage.flush_file`/`flush_directory`, Win32 declarations included. The tool now requires an engine that has them.
  - (b) `HISTORY_SOURCE` (`tools/nested_comicinfo_merge.py:85`) and `provenance.NESTED_MERGE_SOURCE` are two copies of one string. Renaming either one silently turns item 7 off; nothing tests the two against each other.
  - (c) `recover_entry` repeats the hand-driven `guard.__enter__`/`__exit__` (q7(d)).
- **Inherited:** **q7 [Minor]** (a)–(d); **s7**, **t4 [Minor]**.

### 8. Doc/Code Drift (no Critical findings on its own)

- Status: Concerns.
- **r6 [Minor]**
  - (a) `automatic.py:247-255` `replacement_record` still writes "Replaced in-book values with <provider>…" into the comic's **Notes**, and the ledger source `replaced-in-book:`, when the replaced value was a merged one. The `external_plan` docstring (`:213`) still says only in-book values are replaceable.
  - (b) RECOVERY step 3 says "each backup this run made of it". The code deletes any backup of that archive made since the attempt began with the original's SHA-256, the app's included. That is harmless (the bytes are equal), but not what the text says.
- **Resolved:** **q5(a)** (the Brief and `graceful-stop.cjs:50` now say a manual write can be stopped) and **q5(b)** (with q1 fixed, "a reboot clears every record" holds).
- **Inherited, untouched:** **q5(c)** (the Brief's "Broker ended from outside" row still says "twice for a forced stop, `CLOSURE_WAIT` 5 s each") and **q5(d)** (the tool docstring's "same library claim", `tools/nested_comicinfo_merge.py:37`); **s8**, **n5 [Minor]**.

### 9. Build & Release Hygiene

- Status: Pass, conditional.
- **Pending bump:** `VERSION`, `package.json` and the lockfile still read 0.6.7, and `CHANGELOG.md` has no 0.6.8 entry. This clearance assumes Sully's next commit changes only those, plus a CHANGELOG naming the items in the Summary.
- **Diff and tree:** `git diff --check` is clean. The tool is not packaged. The working tree was clean at review start; this report is its only change, uncommitted. No test output was left in the checkout.

---

## Patterns

Again a proof stops one step short. At c355313, Q1's flush made the new archive durable but not the backup that then held the old values (R1). The tool's record of dropped values was written only on the success path (R2). Q1's fix reached the metadata writer, but not the converter, which deletes the original outright (R3). The delta closes R1 and R2 the right way, by moving each record and flush before the moment its file becomes the only copy. R3 is the one site of that pattern left open.

---

## Verdict

- **Total Critical:** 0.
- **Total Major:** 5 open.
  - New and open: R3 (outside the range).
  - Inherited, untouched: M1, M2, I1, I2.
  - Resolved: from v0.6.7, Q1 (the archive part), Q2 and Q3; from this review, R1 and R2 (in the delta).
- **Total Minor:** 29 open.
  - New and open: r2–r7.
  - Inherited, untouched: q3, q5 (c and d), q6, q7, s1–s11, n1–n5, i1, t3, t4.
  - Resolved: from v0.6.7, q1, q2 (residual r4), q4 and q5 (a and b); from this review, r1 (residual r7).
- **Safety floor:** intact.
  - No Electron preference or IPC change.
  - Every new write is in scope: the app's state folder, the user's library through the app's writer, and the tool's `--out`.
  - Every new deletion is SHA-gated against bytes still in place and location-checked (`remove_verified_backup`). The temporary file is deleted only under the comic's write guard, with the comic proven unchanged.
  - The delta adds no deletion. The only bytes it removes are a torn tail cut from `--out` files, and it moves them to `<name>.torn` first. Its read-only toggle touches only the backup this write just made.
  - No secret handling, and no repository-integrity change.

**Verdict:** RELEASE CLEAR

This clears construction for source commit a4d23f7a78f7e1f70bb910f3b6a4bbe92db3d0ca (range 0771691f8ad5607e73988b4fb97998d2a0c62548..a4d23f7a78f7e1f70bb910f3b6a4bbe92db3d0ca), plus a bump that changes only the version and the changelog. It does not prove installer behaviour, the QA entry gate or publication.

- **Before the one-off apply run** (not a release gate): R1 and R2, the two items this review asked for first, are fixed at a4d23f7. Worth having, not required: r2, a retry on a sharing violation. Today a thumbnailer holding one comic can stop the whole apply.
- **First items for Ender's next cycle:** R3, then r4, r2 and r7.

**Built commit covered:** v0.6.8 build `da503b3d45798bfb7142c377fe2db5704c509153` (main). It is a4d23f7 plus two commits: 5deebf8 (this review) and da503b3 (Sully's bump). I checked this with `git diff a4d23f7 da503b3d45798bfb7142c377fe2db5704c509153`, which touches 5 paths:

- this review (added);
- `VERSION`: 0.6.7 to 0.6.8;
- `package.json`: the `version` field, 0.6.7 to 0.6.8;
- `package-lock.json`: its two version fields, 0.6.7 to 0.6.8;
- `CHANGELOG.md`: a v0.6.8 entry naming the durable saves and backups, the recovery of an interrupted save, the old engine's late exit, the unreadable lock file, the nested-only rules, the correctable merged values, the Quit wording, the merge tool's `--resume`/`--recover`, and `data/removed-nested-copies.jsonl`.

There is no source, test, tool or build-config change.
