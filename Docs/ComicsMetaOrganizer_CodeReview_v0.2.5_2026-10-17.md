# Code Review — Comics Meta Organizer v0.2.5

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-17
Tool: Comics Meta Organizer
Release: v0.2.5
Commit range: e2db1c39c2d0f4353977f782f1ee1282184effdd..39211f0bde39f12fef23a17259fa9812515a3179
              (the 0.2.4 bump to the 0.2.5 bump; continues the v0.2.4 record, which ended at e2db1c3)
Files changed: 19 files, +3036 / -33 (code only, Docs excluded: 15 files, +2310 / -27, of which tests 2 files, +1137)
Checkout: C:/Antigravity Projects/Studio Illuminati/WIP/Comics Meta Organizer, fresh clone, main, tree clean before and after
Artifact examined (not run): dist/Comic-Metadata-Setup-0.2.5.exe, 149,482,763 B,
              sha256 f7a1d169a54b8a51c6dd186477bfae2e79d2406598d420030f7af8e1f17b1134
Stand-down dimensions: none
Mode: lean, one focused pass (Sergei asleep; release unless something serious turns up)
```

---

## Summary

The range adds actions to the folder "Your help is needed" lines (UXSpec FolderHelpActions 2026-10-16 and its Amendment):

- `folder_help.py`: the check, **Check and requeue**, **Delete backup and requeue**, **Close and recheck folder**, **Open folder** / **Show in folder**.
- Four routes in `app.py`: `/api/attention/check`, `/delete-backups`, `/close` and `/reveal`. They take a ticket id and server-issued ids only.
- `discovery_state.due_now()`: makes research records due. `folders.json` is not touched.
- `kept_backups.delete_one()`: split out of `delete()` and given a `before_unlink` hook.
- `worker.py`: stores a reason `code` on `needs_attention`.
- `progress_snapshot.queue_named()`, plus the keyed `static/folder-help.js` render in `index.html`.

I read the whole code diff red-team style, and the code it leans on: `worker.py`, `batch.apply`, `write_metadata`, `comic_write_guard`, `coverage_priority.pending_paths`, `scheduler`, `storage.save`, and the POST origin check. I ran the touched test modules once under the isolation modules. I checked the artifact against HEAD.

**No Critical findings, and the safety floor is intact.** Answers to the brief:

- **Races with the worker: none that write the wrong thing.**
  - Actions are refused while paused or pausing (`pause_control.requested()`). They are allowed while the worker runs a batch. That is by design (A3).
  - Every action requires the ticket to be `needs_attention`. The worker never writes a ticket in that state: `run_one` touches only `pending`, and the startup sweep touches only `running`.
  - A `needs_attention` ticket's write comics are in `coverage_priority.pending_paths()`, so no new plan can include them while the line is open. No batch can be mid-write on them.
  - A manual save can still be mid-write. Delete re-checks under `app.comic_write_guard`, which is an OS file lock taken without waiting. A held lock raises `ArchiveChanged`, the route reports `delete_failed`, and nothing is deleted.
- **Ticket file edits: atomic, with no lost update.**
  - `storage.save` writes a temporary file and then replaces the ticket. Its temporary names end in `.tmp`, so they never match `*.json`.
  - The dashboard and the worker write disjoint states. `enqueue` never overwrites an existing stem.
  - `_close` reads the ticket and the pause state again just before saving, under `_BUSY`.
  - The one side effect is that the worker can now meet a replace in progress when it reads a ticket. See **m2**.
- **Id forgery, path traversal, cross-origin: nothing found.**
  - A ticket id is a file stem. Separators, `:`, wildcards, edge dots and edge spaces, and non-printable characters are refused, and the path is checked to stay in `QUEUE`.
  - Problem and backup ids are HMAC-SHA256 under a per-process secret. They resolve only through the in-process map, and only for the ticket they were issued for.
  - Every POST pins `Origin` and `Host`, and the server is threaded. The page sets all text with `textContent`.
  - Reveal uses `SHOpenFolderAndSelectItems` on a validated regular file, or `os.startfile` on a folder checked to be a directory inside the library. Nothing is spawned, so there is nothing to inject into.
- **Can Delete backup and requeue delete the only good copy?**
  - **Not the only copy of the comic as it stands.** The comic must match the plan's size, mtime and a SHA-256 read in the same request. This holds at the check, before any delete, and again under the write guard before each unlink.
  - **But it never looks at the backup.** Every `<comic>.<digits>.bak` for that comic name is offered and deleted. That includes an older backup from an earlier write, whose contents are a different version. That backup can be the only copy of that version, while the confirm text says "there is nothing to undo". See **M1 [Major]**.
- **Can requeue cause a write that bypasses the plan guards? No.**
  - A closed ticket is never `pending`, so its plan never runs again.
  - Requeue only moves `retry_at` on research records. The next folder pass builds a new plan from the disk, with a new SHA-256 and signature, under a new ticket stem. `batch.apply` re-checks that plan (`changed_since_planning`, the expected `before` fields, the write guard).
  - `due_now` skips stopped writes (`retry_at` 0) and keeps `write_failures`. Comics in `skipped.json` or `failed.json` keep their own wait.

**Evidence:**

- **Python tests, run 1.** One process, `python -I -B`, my runner in scratch: `test_0_state_isolation`, `test_folder_help`, `test_folder_help_dom`, `test_kept_backups`, `test_kept_backups_dom`, `test_discovery_state`, `test_progress_snapshot`, `test_zz_state_isolation`. Result: **76 run, 50 passed, 24 skipped, 2 errors.**
  - The skips are the DOM classes. `COMICS_TEST_CDP` was not set, so no browser started and focus was never taken.
  - Both errors are `ModuleNotFoundError: PIL`, because `-I` hides the user site. They are not code failures.
- **Python tests, run 2.** Those two modules again with the isolation modules, using `python -E -B -P`: **14 run, 14 passed.**
- **Guard active (positive control), in both runs.**
  - The extra protected roots were `Y:\Comix`, `%LOCALAPPDATA%\comic-metadata-updater` and a scratch canary. The built-in roots include `%LOCALAPPDATA%\ComicsMeta`.
  - An `open()` for write on the canary was refused, and no file appeared. `VIOLATIONS == []`.
  - `os.startfile`, `kept_backups._select` and `_open_folder` were replaced by recording stubs. They recorded **0** unstubbed calls.
  - State, locks, `COMICS_META_TEST_SCRATCH` and `COMICS_TEST_EVIDENCE` were all in scratch.
  - `git status --porcelain` was empty before and after.
- **Artifact.**
  - Installer: sha256 `f7a1d169…1b1134` matches. The `latest.yml` sha512 (`8Oglb0l8…TANZg==`) matches, recomputed with `openssl dgst -sha512 | base64`. The size, 149,482,763, matches.
  - Extracted `$PLUGINSDIR/app-64.7z` with 7-Zip into scratch: all **60** files in `resources/engine` that git tracks equal the HEAD blobs after CRLF normalization (`core.autocrlf=true`), and are byte-equal to the clean working tree. **0 differ.**
  - `folder_help.py` and `static/folder-help.js` are present. `installer_launch.py` equals `desktop/installer_launch.py`@HEAD. `update-runtime-manifest.json` is generated. The engine `VERSION` and the `package.json` inside `app.asar` both say 0.2.5.

---

## Rubric

### 1. Security

- Status: Pass. Routes take ids only. Ids are HMAC-bound to their ticket. POSTs pin `Origin` and `Host`. No subprocess, no new path input, no `innerHTML`. No Electron or `desktop/` change in range. No secrets.

### 2. Correctness & Logic

- Status: Concerns
- Findings:
  - `folder_help.py:174-206` **[Minor] m3.** `_plan` treats every exception as `plan_unreadable`, including a short-lived `OSError`. It also reads `plan.json` with `Path.read_text`, not `storage.read_text`, which retries Windows reader locks. A sharing violation on `plan.json` therefore offers **Close and recheck folder**, and that close skips the backup and temp-file inspection. The route reads again at the click, so the error must hit twice. Nothing on disk is changed.
  - `folder_help.py:518-521` **[Minor] m5.** After backups are deleted, if the ticket is `gone` at the final read, `gone` is raised again without the `deleted` count. The page then says "This folder is not waiting for help." and never says that backups were deleted.
  - Note, not a finding: `after_state()` is always `None`, because `batch.apply` records no output hash. The `basis:'written'` branch is therefore unreachable. That is conservative and documented in the docstring.

### 3. Crash / Stability Safety

- Status: Concerns
- Findings:
  - `worker.py:59`, `worker.py:123` **[Minor] m2.** Before 0.2.5 only the worker wrote queue tickets. Now the dashboard replaces them too, but the worker still reads them with a plain `read_text`. On Windows that read can hit the dashboard's replace and get a sharing violation. In `run_one` this is caught and the worker waits 10 s. In discovery (`coverage_priority.pending_paths`) the broad `except` records it as a folder error, so that folder waits an hour. In the startup sweep (`worker.py:123`) nothing catches it, so the worker exits and the supervisor restarts it. Rare, because closes are user clicks taking milliseconds. Fix: `storage.read_text` at both sites.
  - `folder_help.py:330-335`, `:303` **[Minor] m6.** A comic that disappears between `is_file()` and `stat()`, or a backup that disappears during `scandir`, raises outside `HelpError`. The page gets the generic "Could not finish" or an "other" refusal. Nothing is changed.

### 4. Performance

- Status: Pass, with one note. The check runs `testzip` and SHA-256 over every write comic in the plan on the library drive. On a large plan over the network that takes minutes while `_BUSY` is held. The spec allows for this ("This can take a few minutes"), and the server is threaded, so the 2 s poll is not blocked. Closed tickets are not cached by `worker.tickets()` (only `complete` is), so each one is read again on every worker loop. With tens of closed tickets that is negligible. It is included in **m1** below.

### 5. State & Data Safety

- Status: Concerns
- Findings:
  - `folder_help.py:287-306`, `:350-353`, `:493-506` with `kept_backups.py:270-289` **[Major] M1.** Delete backup and requeue proves the comic but never the backup, so it can delete the only copy of an earlier version of a comic.
    - **What happens.** `_kept_backups` picks every `<comic>.<digits>.bak` for the comic's *name*, whatever write made it. The offer, and the delete, need only the comic to match this plan's before-fingerprint (A8.1).
    - **How an older backup gets there.** A kept backup from an *earlier* write holds a different version of the comic. These can come from:
      - a manual save that kept its backup (`save_not_verified` or `delete_refused` in `/api/apply` and `comic_recovery`);
      - a batch comic skipped after its backup was made (`ArchiveChanged` after the copy).
    - **How it gets offered.** A later plan can include that comic, planned from its current bytes. If that batch then stops before writing it (an interrupted batch), the check shows the old backup as "exactly as it was before the write, so there is nothing to undo". The confirm then deletes it permanently.
    - **Worse case.** For a comic in `skipped.json` or `failed.json`, `_inspect` also skips the zip test (`:329`). So a comic damaged *before* planning (F23 lists a bad page CRC as a failure reason) still "proves". An older good backup of it would be deleted as redundant.
    - **What is not at risk.** The comic file itself is never touched, and it is always byte-equal to the plan state.
    - **Why Major, not Critical.** It needs an older kept backup for the same comic, plus a later batch that planned that comic and stopped before writing it, plus Sergei's confirm. Kept backups would delete the same file on request.
    - **Fix next cycle.** Before offering, and again inside `again()` under the guard, hash each backup and require it to equal the comic digest just read. That is the rule `app.remove_verified_backup` already uses. The common case still passes (an interrupted batch's backup is a byte copy of the untouched comic), and an older version is never offered. The alternative is to accept only backups this plan's batch made.
    - **Test that shows it:** two backups for one unwritten, unchanged comic, one byte-equal and one differing. Today both are offered and both are deleted.
    - The spec (A5: "A1 proves the comic, not the backup's contents") accepted the first half of this. The confirm copy "nothing to undo" does not hold for an older backup, so Judy and Sergei should see this finding too.
  - **[Minor] m1.** Closed tickets are never pruned, and the worker reads them from disk on each loop (see 4). Their batch folders (plan, results) stay as well.
  - Otherwise sound:
    - Delete re-derives targets from what is on disk now, and refuses ids it did not issue for this ticket.
    - It proves every comic before any delete (all before any).
    - It proves again and runs `checked()` under the write guard before each unlink. The write guard refuses rather than waits.
    - It runs the full check before closing.
    - **Close and recheck** touches no comic, temp or backup file.

### 6. Input Handling

- Status: Pass. Exact body key sets per route. Ticket stems are validated. Backup ids are a list of 1 to 20 distinct 32-hex strings. `problem` that is not a string resolves to `not_found`. The 100 KB body cap is unchanged.

### 7. Maintainability (no Critical findings on its own)

- Status: Concerns
- Findings:
  - `worker.py:11` **[Minor] m7.** The worker imports the dashboard actions module `folder_help` for `classify` and `INTERRUPTED`, and `folder_help` imports `worker` lazily. The reason classifier belongs in a small module of its own. `folder_help` also calls the private `kept_backups._select` and `_open_folder`.

### 8. Doc/Code Drift (no Critical findings on its own)

- Status: Concerns
- Findings:
  - Spec §8.3 and A8.6 vs `folder_help.py:409-417` **[Minor] m4.** The spec says requeue has "the `scheduler.finish(..., queued=True)` effect". The code makes the research records due and leaves `folders.json` to the worker, which is the safer choice: no second writer of scheduler state. The folder is reached at its own next pass (`scheduler.finish` sets about 10 minutes after a pass). The spec text should say so, so Futaba measures the right thing.

### 9. Build & Release Hygiene

- Status: Pass.
  - The bump to 0.2.5 is in `VERSION`, `package.json` and `package-lock.json` together.
  - The artifact hashes and size match `latest.yml`. The packaged engine and static files equal HEAD, and the new files are present.
  - No secrets or tests in the package. No Electron configuration change.

---

## Patterns

Two reviews running, the backup-delete paths use a weaker proof than the app's own cleanup. `remove_verified_backup` hashes the *backup*. Kept backups (0.2.4) relied on Sergei's explicit choice. FolderHelp (0.2.5) hashes only the *comic*. Any future path that deletes a backup should prove the backup's own bytes.

---

## Verdict

- Total Critical: 0
- Total Major: 1
- Total Minor: 7

**Verdict:** RELEASE CLEAR

| # | Sev | Dim | file:line | Finding | Next cycle |
|---|-----|-----|-----------|---------|------------|
| M1 | Major | 5 State & Data | `folder_help.py:287-306, 350-353, 493-506` | Delete backup and requeue never proves the backup's contents. An older backup of the same comic (another version) is offered as "nothing to undo" and deleted permanently, and for a skipped or failed comic without a zip test. | Require backup SHA-256 == the comic digest just read, at the offer and under the guard (as `remove_verified_backup` does); add the two-backup test. |
| m1 | Minor | 5 / 4 | `worker.py:56-63` | Closed tickets are never pruned and are read again on every worker loop. | Cache `closed` like `complete`; decide on retention. |
| m2 | Minor | 3 | `worker.py:59, 123` | The worker reads tickets the dashboard now replaces without the reader-lock retry. The startup sweep is unprotected. | Use `storage.read_text`. |
| m3 | Minor | 2 | `folder_help.py:174-206` | Any exception, including a short-lived lock, reads as `plan_unreadable` and offers a close without inspection. | Use `storage.read_text`; treat `OSError` as "could not read", not unreadable. |
| m4 | Minor | 8 | spec §8.3, A8.6 | The spec says `scheduler.finish` effect; the code uses `due_now`. | Update the spec text. |
| m5 | Minor | 2 | `folder_help.py:518-521` | `gone` after deletes loses the deleted count. | Return `deleted` with `gone`. |
| m6 | Minor | 3 | `folder_help.py:303, 330-335` | A file disappearing mid-check escapes `HelpError`, so the page shows a generic error. | Map `OSError` to `HelpError('other')`. |
| m7 | Minor | 7 | `worker.py:11` | The worker depends on the UI-actions module. | Move `classify` to its own module. |

---

## Addendum — 93d031f (2026-10-17)

```
Commit range: 39211f0bde39f12fef23a17259fa9812515a3179..93d031f1cb5ac2f5eaf87a6ed03cbf03461a837a
              (one commit: "fix: Delete backup and requeue only for an identical backup")
Files changed: 2 files, +95 / -12 (folder_help.py +30 / -12, tests/test_folder_help.py +65)
Checkout: main at 93d031f; only the two untracked v0.2.5 reports, before and after
Artifact examined (not run): dist/Comic-Metadata-Setup-0.2.5.exe (rebuilt), 149,483,033 B,
              sha256 7530d0758152ded51f94ee9979d6bf4212c74cd3844ed729eadcb497c2676798
```

**M1 is closed.**

- **New rule.** `backup_proved()` hashes the backup and requires it to equal the plan's before-hash, `entry['sha256']`. `prove()` must also return `original`, which requires the comic to hash to that same value. Together they make the backup byte-equal (SHA-256) to the comic on disk.
- **Where it applies.** All three places the brief named:
  - when the offer is built (`_inspect`): an unproved backup gets `basis` None, so there is no offer and the row reads "Do not delete it until the comic is checked";
  - in the all-before-any loop, before the first delete;
  - inside `again()`, which runs under the comic's write guard, after `checked()`, immediately before the unlink.
- **Older backups.** An older backup holding another version now never matches. It is not offered, and a crafted request naming its id is refused with `changed`, with nothing deleted. A test covers both the forced single id and the mixed pair.
- **Skipped and failed comics** that have a backup now take the zip test, so a damaged one stops the offer.

**New paths to deleting a non-identical backup: none found.**

- The only route that deletes is `delete_backups`. Its targets are ids issued for this ticket with code `backup_left` that are still on disk now, and every target passes both proofs twice, the second time under the guard.
- A backup swapped after the offer is caught. The test rewrites it between the check and the click, and again after the all-before-any pass, just before the unlink inside `delete_one`. Both times nothing is deleted and the ticket stays open.
- The greedy name regex cannot map a backup to the "wrong" comic in a way that matters: whichever comic it maps to, the backup must equal that comic's current bytes.
- Remaining gap, not new and not reachable today: the A1 `written` basis would still allow deleting a backup that differs from the comic (the backup equals the original, the comic the verified result), as the spec intends. `after_state()` is always `None`, because `batch.apply` records no output hash, so that basis never occurs.
- Side effects, not findings:
  - The check now reads each kept backup of a proved comic once more, and the click reads each offered backup twice (at most 20). On a network library that adds time, not risk.
  - A skipped comic with a backup that another program holds open now fails the check with "could not be read". That is a refusal; nothing changes.

**Tests.** I ran `test_folder_help` once in one process with `python -I -B`, between `test_0_state_isolation` and `test_zz_state_isolation`, using my runner in scratch. Result: **32 run, 32 passed** (29 folder-help tests, including the 3 new ones, plus the 3 isolation tests).

- The new tests have real positive controls. Removing the older backup restores the offer, and the delete then succeeds. An intact failed comic is offered before the damaged one is not.
- Guard active: a write to the scratch canary was refused, and no file appeared.
  - The protected roots were `Y:\Comix`, `%LOCALAPPDATA%\comic-metadata-updater`, the canary, and the built-in `%LOCALAPPDATA%\ComicsMeta`.
  - `VIOLATIONS == []`.
  - `os.startfile`, `_select` and `_open_folder` were stubbed and recorded 0 calls.
  - `git status` was identical before and after.

**Artifact.**

- **Installer:** sha256 `7530d075…2676798` matches Jane's value. `latest.yml` matches it:
  - sha512 `g9F57CXg…CeZi0A==`, recomputed with `openssl dgst -sha512 | base64`;
  - size 149,483,033;
  - both written at 01:45 local, after the fix commit.
- **Package contents:** I extracted `$PLUGINSDIR/app-64.7z` with 7-Zip into scratch.
  - All **60** files in `resources/engine` that git tracks equal the HEAD `93d031f` blobs after CRLF normalization, and are byte-equal to the working tree. **0 differ.**
  - `folder_help.py` carries `backup_proved`. `installer_launch.py` equals `desktop/installer_launch.py`@HEAD, and `update-runtime-manifest.json` is generated.
  - The engine `VERSION` and the `package.json` inside `app.asar` both say 0.2.5.

**Counts after the addendum:** Critical 0, Major 0 open (M1 closed in 93d031f), Minor 7 (m1 to m7, unchanged). This addendum certifies the range `e2db1c3..93d031f` and the rebuilt artifact above. It supersedes the artifact hash in the header.

**Verdict:** RELEASE CLEAR
