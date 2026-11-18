# Code Review — Comics Meta Organizer v0.6.4

## Header

```text
Reviewer: Senua (Code Reviewer)
Date: 2026-11-18
Tool: Comics Meta Organizer (Comic Metadata)
Release: v0.6.4
Commit range: 61a3507a605afa4cb6e96320d7b42c4a2f137cd0 (v0.6.3)..445bd36c79af3565f31ce1a66be4ee89466064c6
Candidate commit: 445bd36 (ender/enrichment-2026-11-17, incl. Sully's version-only bump 445bd36 on top of 4f4f242)
Files changed: 31 files, +2754 / -69 (product source: storage, batch, scheduler, progress_snapshot, browser_search,
               worker, automatic, source_scheduling, pipeline_config, metron; tools/metron_would_write.py; tests; docs)
Stand-down dimensions: none
```

---

## Summary

The diff covers fix A (durable `storage.save`: flush + `os.fsync` + `MoveFileExW(REPLACE_EXISTING | WRITE_THROUGH)`, all 28 call sites), fix B (`<name>.bak` previous-good-copy save and `storage.read_json` restore for `progress.json`, `folders.json` and `browser-search.json`), option 5 (re-ask spread, 30-day long-miss back-off, settled GCD-offline miss counts toward Enrichment A's `unsearchable` marker; on by default), options 2/3 Metron matching switches (`metron_spellings`, `collection_label`; off by default; `yearless`/option 4 unchanged and off), the dev-only `tools/metron_would_write.py`, tests, Brief rows and diagnosis docs, and Sully's version bump. The publication tooling commits in range (d3c2678, 994e93b, bc261f4) carry the exact bytes cleared by `ComicsMetaOrganizer_LocalReleaseToolingReview_v0.6.3_2026-11-14.md` (SHA-256 re-checked: `create-local-promotion.mjs` b9c0e90…, `local-promotion.test.mjs` 54d862b…, `publish-held.py` 13c9eb9… with CRLF); `publish-namespace.test.py` is test-only. Red-team focus per brief: fix B restoring stale/wrong copies, rotation races, Windows fsync, option 5 starvation/never-waking, switches leaking on, Metron budget in the tool.

Verified, with probes in the repo's gitignored `scratch/` (removed afterwards): `ctypes.WinError` 5/32/33 all raise `PermissionError`, so the rename retry loop engages on sharing violations; the off switches leave `metron.rules_stamp()` at the 0.6.3 value and `matching()` accepts only a JSON boolean from `config.json` — no code path writes them on, and the tool's switch flip is an in-process monkeypatch; a GCD dump rebuild changes `gcd_offline.rules_stamp()` (`RULES:dump_date:attempt_id`) and wakes settled comics; a MATCHER_VERSION change discards stored source waits (`automatic.py:418`), so a 30-day back-off cannot outlive a matcher change; new comics have no failures and keep first-pass priority. Targeted tests: `test_storage_durable`, `test_storage_previous_copy`, `test_enrichment_options_20261117`, `test_source_scheduling`, `test_startup_recovery` — 57 passed. `git diff --check` clean. Cost probe: a 1.34 MB `folders.json`-sized save is 35 ms plain, 71 ms with `keep_previous` (I: drive).

---

## Rubric

### 1. Security

- Status: Concerns.
- **N2 [Major]** `tools/metron_would_write.py:91`: the live catalog is opened as `'file:' + path + '?mode=ro'` with the path unescaped. A `#` (or `?`, or a `%xx` sequence) in `--live` or `%LOCALAPPDATA%` truncates/rewrites the URI and drops `mode=ro`; SQLite then opens **read-write and creates** a file at the truncated path. Probe: live folder `…/live#1` → a new file `…/live` was created beside it, writable, and the "snapshot" was an empty database (pool silently 0). The real live catalog is never opened, so no live state is written, but the tool's stated read-only guarantee fails silently and a stray file is created outside `--out`. Not triggered on Sergei's current profile path; the tool is not packaged (`assemble-runtime.py` ships top-level `*.py` only). Fix: build the URI with `Path(...).as_uri()` or `urllib.parse.quote`, and refuse if the opened database has no `comics` table.
- No new shell-outs; `MoveFileExW` takes `str` paths through typed ctypes arguments (no interpolation). No secrets in the diff or in `Docs/ComicsMetaOrganizer_MetronPilot_2026-11-18.json`; provider cache keys exclude credentials. Electron surface untouched in range.

### 2. Correctness & Logic

- Status: Concerns.
- **n3 [Minor]** `source_scheduling.py:192-195`: the long-miss count is `failures`, which the error branch (line 193) also increments, and stored pre-0.6.4 counts carry over across older Metron rules stamps. "6 misses in a row under the same rules" (docstring, Brief, CHANGELOG) is really "6 non-success, non-deferred results"; a run of network errors plus one miss earns a 30–45 day wait. Brief documents the carry-over; the error case is not.
- **n4 [Minor]** `source_scheduling.py:162`: a rules-stamp change (switching option 2 or 3 on) makes every Metron `no_verified_match` ready at once — the same all-at-once wave option 5 was built to spread; the spread applies only to the wait recorded after the re-ask. Bounded by Metron pacing (3.2 s, ~5,000/day), so this is a multi-day Metron backlog rather than harm. Worth a staged wake before a switch goes on.
- **Inherited, unchanged in range:** **M1 [Major]** `app.py:289` case-sensitive scan range; **I1 [Major]** `gcd_matching.py:128` edition-specific ISBN/GTIN equivalence; **I2 [Major]** `automatic.py:674` mixed-provider synopsis attribution. (`app.py`, `gcd_matching.py` untouched; `automatic.py` changes are confined to option 5 and `name_spelling`.)

### 3. Crash / Stability Safety

- Status: Concerns.
- New paths fail closed: `read_json` raises `FileNotFoundError` for a missing file and `ValueError` when neither file nor copy reads (0.6.2 preserve-and-wait retained, `test_startup_recovery` passes); a `.bak` write failure aborts the save before the main file is touched; `gcd_offline_settled` only calls `gcd_offline.current()` after GCD offline has already answered, so it adds no new `GcdError` exposure.
- **Inherited:** **M3 [Major]** `engine_host.py:182` claim-retirement exception after Job empty (file untouched in range).

### 4. Performance

- Status: Pass. fsync cost measured by Ender (1.46 MB: 40 vs 39 ms) and by this review with `keep_previous` (71 ms per 1.34 MB save; `scheduler.select` saves up to ~4 times per call, so ≤ ~0.3 s per folder turn); extra `config.json` reads in `pipeline_config.scheduling` are a few per comic and match the existing `matching()` pattern.

### 5. State & Data Safety

- Status: Concerns.
- **N1 [Major]** `progress_snapshot.py:54` (via `storage.py:98-123`): the dashboard's read-only poll now **writes** `folders.json` and `progress.json` when it finds them unreadable. That makes the dashboard a second whole-file writer of `folders.json`, against the documented single-owner rule (`cover_tasks.py:66`: "Discovery owns folders.json … rather than racing a whole-file scheduler update"). `read_json`'s re-check at `storage.py:116` and its restore at `storage.py:121` are not atomic — the `.unreadable` evidence write (an fsync'd file of up to ~1.7 MB) sits between them — so if the worker restores first and saves its next step inside that window, the dashboard overwrites the newer record with the older `.bak`. Probe (interleaving injected at that point): a newer good save `B2` was replaced by `B0`. Consequence is a one-step rollback (a lost `scheduler.finish` record → folder re-scanned; a lost `completed` history entry; a lost `browser-search.json` challenge/cooldown field, the very data 0.6.2 refused to guess), only after a damage event. Fix: let the dashboard serve the `.bak` content in memory without writing, and leave the on-disk restore to the owning writer (or serialize restore and save under one file lock).
- **n1 [Minor]** `storage.py:88-95`: when the file is missing, `save(keep_previous=True)` keeps whatever `.bak` already exists. After Sergei deletes a state file (the 0.6.2 recovery step) or after an older run/downgrade, the first new file's `.bak` is a pre-deletion record; if that file is damaged before its second save, `read_json` restores it. Probe: two saves, delete, one fresh save, damage → the record from **two saves before the deletion** came back. Contradicts the Brief's "deleting one still starts afresh". Fix: when the file is missing, remove (or rename aside) a stale `.bak` before the first save.
- Copy rotation under concurrent writers is otherwise sound: `.bak` only ever receives bytes that parsed as a valid record, every write uses a unique temp name plus atomic rename, and the possible orders give at worst the pre-existing two-writer lost update (diagnosis §1), never an invalid `.bak` or a zero-filled file. fsync on Windows is correct (`os.fsync` → `FlushFileBuffers` on a write handle, before close and rename). No file-delete operations were added.
- **Inherited:** **M2 [Major]** `archive_conversion.py:161` source-replacement identity gap (file untouched in range).

### 6. Input Handling

- Status: Concerns.
- `pipeline_config.scheduling` rejects bool-as-number, NaN, inf and negatives (tested). A fractional `long_miss_after` such as `0.5` is accepted and makes every miss a long miss — `config.json` is Sergei-edited only, so no finding.
- **n2 [Minor]** `tools/metron_would_write.py:195-219`: the Brief's Metron rolling-window lesson ("run with the app paused or stopped; confirm `last_request` is not moving") stays procedure-only. The tool reads the live `metron-status.json` only for burst/daily remaining, ignores the live app's `retry_at` and `last_request`, and so can keep spending the shared Metron allowance while the app is busy or waiting out a 429 (which can push the app's own Metron wait up to `Retry-After`, default 3600 s). Bounded by `--max-requests` and `--floor`. Per Doc Governance, a lesson already violated once wants a mechanism: refuse to start (or stop) while live `last_request` is recent or live `retry_at` is in the future.
- **Inherited:** **i1 [Minor]** `local_model.py:99` GIF/BMP credits enumeration.

### 7. Maintainability (no Critical findings on its own)

- Status: Pass. One shared durable writer and one shared read-with-fallback helper; record validators (`batch.progress_record`, `scheduler.schedule_record`) are shared by writer and dashboard, so a valid file cannot be misread as damaged; switches are reversible and tested off and on.

### 8. Doc/Code Drift (no Critical findings on its own)

- Status: Concerns.
- **n5 [Minor]** Three statements do not match the code: (a) `storage.py:30` "the rename reaches the disk before this returns" — `MOVEFILE_WRITE_THROUGH` is documented to guarantee the flush only for copy-and-delete moves; zero-fill protection rests on the fsync before the rename, which is correct, but after a stop the app may come back one save behind. (b) `source_scheduling.py:112` "Markers from before option 5 keep their fingerprint" — with the setting off the fingerprint gains a key, so 0.6.3-era markers are also woken (harmless, one extra ask). (c) `CHANGELOG.md` v0.6.4 omits option 5's third part (settled GCD-offline misses now count toward the `unsearchable` marker, on by default), which changes which comics stop being re-asked. Brief "deleting one still starts afresh" — see n1.

### 9. Build & Release Hygiene

- Status: Pass. `VERSION`, `package.json` and both `package-lock.json` version fields read 0.6.4 in one commit (445bd36) with a changelog entry; no stray `0.6.3` outside docs/test comments; `git diff --check` clean over the range; `tools/` is not packaged; publication tooling bytes match the prior cleared review.

---

## Patterns

0.6.2 taught the state readers to tolerate damage; 0.6.4 teaches them to repair it, which quietly turns the dashboard's read path into a writer. Read paths that write deserve the same ownership check as the writers they stand in for.

---

## Verdict

- Total Critical: 0
- Total Major: 7 (new N1, N2; inherited M1, M2, M3, I1, I2)
- Total Minor: 6 (new n1–n5; inherited i1)
- Safety floor: intact. N2 creates a stray file only when the live path contains a URI metacharacter (not the case on Sergei's profile), never writes the live state or library, and the tool is not shipped; no secret handling, Electron or repository-integrity change in range.

**Verdict:** RELEASE CLEAR

Construction clearance for source commit 445bd36 only — not proof of installer behavior, the QA entry gate or publication. No live state, live app, library or installer was touched by this review; probes and test scratch stayed in the repo's gitignored `scratch/` and were removed. Major and Minor findings are for Ender's next cycle; N1 and N2 are the first two to pick up.
