# Comics Meta Organizer — Zero-Fill Diagnosis (2026-11-17)

Ender, read-only diagnosis. Code read at `main` @ bc261f4 and tag `v0.6.3` (61a3507); the state-file code is identical in both. No code, config or live state was changed, nothing was restarted, and no elevated command was run. Event logs and files were read in place. During this work another agent switched the shared checkout to `ender/enrichment-2026-11-17`; the state-file code on that branch is unchanged from bc261f4.

## Summary for Sergei

1. **The files:** `data/progress.json` (30,283 bytes), `data/folders.json` (1,659,323 bytes) and `data/browser-search.json` (1,644 bytes) under `%LOCALAPPDATA%\ComicsMeta`. They were **full size, every byte zero** — not emptied (recorded on 11-14 in `ComicsMetaOrganizer_StartupEvidence_2026-11-14.md`; the files were deleted at 11-14 21:12 with your OK, so they could not be re-checked today).
2. **Cause: the PC stopped without a proper shutdown on 11-13 between 14:49 and 14:52, while the app was writing those files** (confidence: high). Windows booted again at 14:52:47. The app saves these files in a way that lets the file's name and size reach the disk before its contents. When the power or the system stops at the wrong moment, the file comes back the right size but full of zeros.
3. **Not app-specific:** a Codex image written at 14:49:10 on the same disk is also full size and all zeros, while the images written before it are fine.
4. **Why the PC stopped (power cut, reset button or blue screen) is not known.** The proof sits in the old Windows event logs in `C:\Windows.old`, which need an administrator to read. By default Windows deletes that folder 10 days after the 11-14 upgrade (around 11-24).
5. **Can it recur in 0.6.3? Yes.** The save code has not changed since 10-16. 0.6.2 only stops the damage from blocking start-up. After the next unclean stop the app starts, but automatic processing and cover search wait until someone removes the damaged files by hand.
6. **Fix:** make the shared save write its data to disk before the rename, as the app's setup save already does, and keep the previous good copy to fall back on. Effort: the durable save alone is 1–2 hours with tests; with the fallback copy, about a day; then the usual QA and review for a patch release. Details in §4.

## 1. The files and who writes them

All three are written by `storage.save` (`storage.py:7`), the one JSON writer behind 28 call sites in the app.

| File | Size at damage | Rewritten | Writer processes |
|---|---:|---|---|
| `progress.json` | 30,283 | every progress step (about every 3 s while busy) — `batch.progress` | metadata worker (`worker.py`, `automatic.py`, `archive_conversion.py`) |
| `folders.json` | 1,659,323 | every folder pick and finish — `scheduler.save` / `scheduler.finish` | metadata worker only |
| `browser-search.json` | 1,644 | every cover-search status change — `browser_search.legacy_status` | cover worker (`browser_worker.py`); dashboard server via `lens_verification` |

**How `storage.save` writes (v0.6.1 = v0.6.3 = main):**

1. `temporary.write_text(...)` — writes `<name>.<uuid>.tmp` through the Windows file cache and closes it. **No flush, no fsync.**
2. `temporary.replace(path)` — `os.replace`, i.e. `MoveFileEx(MOVEFILE_REPLACE_EXISTING)` **without `MOVEFILE_WRITE_THROUGH`**.

The rename is atomic for other processes, so a concurrent reader never sees a half-written file. It is **not durable**: NTFS journals the rename and the new file size, but not the file's data. The data stays in the cache until Windows' lazy writer flushes it, usually seconds later. If the machine stops in that gap, the name and size survive and the contents read back as zeros. That is the pattern seen here.

**Concurrent writers are not the cause.** Every writer uses its own unique temp name and an atomic rename; a race between two processes can lose an update, never produce a zero-filled file. (`progress.json` and `browser-search.json` each have two writer processes doing read-modify-write without a lock, so a lost update is possible. That is a separate, minor issue.)

**The codebase already has the durable pattern:** `setup_state.py:98–113` writes with `flush()` + `os.fsync()` and renames with `MoveFileExW(MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)`. `storage.save` was never given the same treatment.

**Why only these three were hit:** they are the most frequently rewritten files over about 700 bytes. Files that small are normally stored inside NTFS's own file record, which is journaled with the name, so they survive. `browser-heartbeat` (56 bytes, rewritten every 2 s by the same `storage.save`) and `maintenance.json` (189 bytes) were valid on 11-14. `automatic.json` (56 KB) was valid because it was last written on 10-02. This size threshold is the usual NTFS default; confirming the exact record size needs an elevated `fsutil fsinfo ntfsinfo C:` (not run).

## 2. Evidence from the machine

### 2.1 Timeline (local time, +02:00)

| When | What | Source |
|---|---|---|
| 11-09 08:21:44 | Windows boots; stays up until 11-13 | `C:\Windows.old\Windows\INF\setupapi.dev.log` boot-session lines |
| 11-13 12:49–12:59 | Windows Setup prepares a feature upgrade in the background ("Setup PnP Migration – Gather", "Verify Driver Store Integrity") | same log |
| 11-13 14:21:35 | Last hourly line in the app's `logs/desktop.log` (lines are hourly from 02:19 onward without a gap) | `desktop.log` (UTC 12:21:35) |
| 11-13 14:47:10 | Last app batch, queue ticket and `progress-history.jsonl` writes; all intact (no zero bytes in `progress-history.jsonl`) | file times under `%LOCALAPPDATA%\ComicsMeta` |
| 11-13 14:48:35 | Codex image written; intact (valid PNG) | `%USERPROFILE%\.codex\generated_images\…` |
| 11-13 14:49:10 | Codex image written; **2,142,007 bytes, all zero** | same folder |
| 11-13 14:52:47 | **Windows boots** — with no shutdown steps logged before it | `setupapi.dev.log` |
| 11-13 23:24 → 23:25:49 | Normal restart (shutdown steps logged at 23:24:10) | `setupapi.dev.log`, `C:\Windows.old\Windows\Logs\WindowsUpdate\` |
| 11-14 10:21 → ~12:40 | Windows upgrade restarts ("Operating System: Upgrade (Planned)"); the new Windows starts with **fresh event logs** (all created 11-14 10:45) | current System log, `wevtutil gli` |
| 11-14 15:30:36 | First app start after the stop; "Engine start timed out" every 30 s | `desktop.log` (UTC 13:30:36) |
| 11-14 21:08 / 21:12 | 0.6.2 candidate installed; the three files deleted | StartupEvidence doc |

The app does not start at login (`desktop/main.cjs` sets no login item), which is why nothing was logged between the 14:52 boot and your first start on 11-14.

### 2.2 The stop on 11-13 was not a normal shutdown

- **Shutdown steps are missing.** In this PC's device log, every normal shutdown leaves three "Restart Device – SWD\WPDBUSENUM\…" entries about 1.5–2 minutes before the next boot. Of 24 boots since 09-30, 21 have them. The 14:52:47 boot does not: the last entry before it is the upgrade check at 12:59:38. (The other two without them: 10-03, which has a different shutdown-time device step 1.5 minutes before boot, and 10-10 16:59, whose cause is unknown.)
- **Zero-filled files outside the app.** The Codex image from 14:49:10 is all zeros; the six files written from 14:41 to 14:48:35 (five images and a 17 MB session log) are intact. So everything written in the last moments before the stop lost its contents, whatever program wrote it. That also rules out Bitdefender or anything else acting on the app's own files.
- **Together** these place the stop between 14:49:10 and 14:52:47, most likely seconds after 14:49:10 (cached data normally reaches the disk within seconds, so a file written 3 minutes before a stop would usually survive). The boot time is exact: the device log's boot times match the kernel's start time in the event log (checked on the 11-14 10:55:02 boot).
- **The app's own older files are intact.** The four app files last written between 14:40 and 14:53 (the 14:47 batch plan and results, its queue ticket, `progress-history.jsonl`) contain no zero bytes. Only the files the app kept rewriting after 14:47 were hit.
- **The 11-14 upgrade did not do it.** The upgrade left the app's folder in place (there is no copy under `C:\Windows.old\Users`), the app did not run between the 14:52 boot and the upgrade, and an upgrade cannot explain why the damage follows the last seconds before 14:52 across two unrelated programs.

### 2.3 What could not be checked

- **Old event logs.** The upgrade on 11-14 started all event logs fresh. The pre-upgrade System and Application logs are in `C:\Windows.old\Windows\System32\winevt\Logs\` and are readable only by an administrator, so Kernel-Power 41, EventLog 6008, BugCheck 1001 and disk/NTFS errors around 14:49 could not be read. These are what tell a power cut or reset (Kernel-Power 41 with bug-check code 0) from a blue screen (non-zero code, plus BugCheck 1001).
- **Crash dumps and error reports:** `C:\Windows.old\Windows\Minidump` is empty and the error-report archive starts on 11-14 (reset by the upgrade). No dump survives to read.
- **Bitdefender's own history** is in protected storage; not read. Not needed for the app's root cause (see the Codex image above).

If you want to know why the PC stopped, this one command, run from an **administrator** prompt before about 11-24, answers it:

```
wevtutil qe "C:\Windows.old\Windows\System32\winevt\Logs\System.evtx" /lf:true /rd:true /c:40 /f:text /q:"*[System[(EventID=41 or EventID=6008 or EventID=1001 or EventID=1074 or EventID=6006 or EventID=7 or EventID=51 or EventID=55 or EventID=129 or EventID=153)]]"
```

## 3. Does 0.6.2 / 0.6.3 prevent it?

**No. It tolerates it, partly.** `storage.py` and `scheduler.py` are byte-identical from v0.6.1 to `main`; the last change to `storage.py` was 10-16.

What 0.6.2 changed (`git diff v0.6.1 v0.6.3`):

- the dashboard and start-up treat an unreadable file as "status unavailable" instead of failing (`progress_snapshot.py`, `browser_search.legacy_status`), so the app starts;
- the metadata worker will not run queued batches while `progress.json` is unreadable (`worker.run_one` → `batch.progress_available`);
- the cover worker waits while `browser-search.json` is unreadable (`browser_worker.main`);
- folder selection still reads `folders.json` with a plain `json.loads`, fails, and retries every 10 minutes (`worker.main` → `scheduler.select`).

**After the next unclean stop during a write:** the app starts, the dashboard shows "Status unavailable", and automatic processing and cover search stay stopped until someone deletes or repairs the files. Nothing recovers on its own. This is the intended 0.6.2 behaviour ("never replace unknown data with guessed defaults") — it was built to tolerate damage, not to prevent it.

**Odds of a repeat:** any unclean stop while the app is busy. The three files are rewritten every few seconds, so at any moment at least one is likely to be in the at-risk gap. This PC has had one confirmed unclean stop (11-13) and one possible one (10-10) in about seven weeks of logs.

## 4. Proposed fix (not implemented)

**A. Make every save durable (prevents it).** In `storage.save`: write the temp file, `flush()`, `os.fsync()`, close, then rename with `MoveFileExW(MOVEFILE_REPLACE_EXISTING | MOVEFILE_WRITE_THROUGH)` — the same calls `setup_state.py` already uses. After that, a stop at any moment leaves either the complete old file or the complete new file. One function, covers all 28 call sites.

- Cost: one disk flush per save. The heaviest is `folders.json` (about 1.1–1.7 MB) once or twice per folder turn; on an SSD that is milliseconds. To be measured on the live library before release.
- Same weakness elsewhere, worth the same treatment in the same change: `research.py:76` (evidence files, temp + rename without a flush); `batch.py:87` (`plan.json` written in place); appends to `progress-history.jsonl` (a stop can leave a zero tail, so its reader should skip such lines). `catalog.sqlite` is safe — SQLite flushes its own writes.

**B. Keep the last good copy (recovers if it happens anyway).** Keep the previous version as `<name>.bak` on each save. When a file is unreadable or all zeros, the reader moves the damaged file aside (kept as evidence), restores the `.bak`, and logs it once. The app then carries on with at most one step lost, instead of waiting for a person. On 11-13 that would have kept the 8,182-folder schedule instead of rebuilding it from empty.

- This changes the 0.6.2 "preserve and wait" behaviour for these three files, so it is **your call**. Restoring a real earlier version is not a guessed default, which is what 0.6.2 set out to avoid.

**Effort:** A is about 1–2 hours with targeted tests (check the flush and the write-through flag are used; a replace under a concurrent reader still works). B is about half a day more (one shared read-with-fallback helper used by the three readers, tests that feed an all-zero file and expect recovery from `.bak`). Then Futaba's check on the build, Senua's review and a patch release (0.6.4). A real power-cut test is not practical; the tests check the mechanism.

**Not needed for this fix:** moving `folders.json` and `progress.json` into SQLite would remove the large rewrites altogether, but it is a structural change and would be a separate decision.

## Method

- Code: `git show`/`git diff` of `storage.py`, `batch.py`, `scheduler.py`, `browser_search.py`, `browser_worker.py`, `progress_snapshot.py`, `worker.py`, `setup_state.py` at `v0.6.1`, `v0.6.3` and `main`; `git grep` for every `storage.save`, `write_text`, `fsync` and rename.
- Live state: directory listings and file times under `%LOCALAPPDATA%\ComicsMeta`; NUL-byte count of `progress-history.jsonl`; `logs/desktop.log` and `logs/engine.log` read in place. `.env` not opened.
- Windows: `wevtutil gli` / `wevtutil qe` on the current System log (read-only); file times of the logs, update traces and minidump folder under `C:\Windows.old`; boot-session and section lines of `C:\Windows.old\Windows\INF\setupapi.dev*.log` (all boots since 03-28 compared for shutdown steps).
- Cross-app check: NUL-byte counts and file headers of every file under `%USERPROFILE%\.codex` written between 14:30 and 14:53 on 11-13 (PNG start and end markers checked), and of every app file written between 14:40 and 14:53. A wider scan of the whole user profile for 14:40–14:56 ran out of time (10-minute cap) and was dropped; it would only add more examples.
- Not done: anything needing administrator rights (old event logs, `fsutil`, Bitdefender history).
