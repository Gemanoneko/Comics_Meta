# Code Review — Comics Meta Organizer v0.2.6

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-17
Tool: Comics Meta Organizer
Release: v0.2.6
Commit range: 93d031f..7b3d93a09e96aa498b82240f1eb33fa5ba64e27e
              (the v0.2.5 code to the 0.2.6 bump; continues the v0.2.5 record, which ended at 93d031f)
Files changed: 9 files, +970 / -173 (code only, Docs excluded), of which tests 2 files, +537 / -31
Checkout: C:/Antigravity Projects/Studio Illuminati/WIP/Comics Meta Organizer, main, tree clean before and after
Artifact examined (not run): dist/Comic-Metadata-Setup-0.2.6.exe, 149,486,506 B,
              sha256 a8fd6fe191d8468dcd2ec5456134dbc6826752769985491f6dfb9bf17c2d7a83
Stand-down dimensions: none
Mode: lean, one focused pass, red-team
```

---

## Summary

The range builds Amendment 2 (B1 to B12) of `Docs/ComicsMetaOrganizer_UXSpec_FolderHelpActions_2026-10-16.md`. **Delete backup and temporary file, then requeue** and **Delete temporary file, then requeue** now also delete the app's leftover `{comic}.metadata-tmp`.

- `folder_help.py`: `Finding` rows, `temporary_path`, `_temporary_checked`, `_delete_temporary`, `_matched` (the click recomputes the offer and refuses unless the ids match), and a rewritten `delete_backups`. It holds every comic's write guard over all proofs and deletes, and deletes the temp file before the backups.
- `kept_backups.py`: `delete_held` and `_tidy`.
- `app.py`: `write_guard_held`, and the delete route accepts `temps`.
- `static/folder-help.js`: labels, confirm text and the new codes `file_gone`, `writing` and `changed`.

I read the whole code diff, and the code it relies on: `comic_write_guard`, `write_metadata`, `_write_metadata_guarded`, every caller of `write_metadata` (`app.py:1029`, `batch.py:209`, `comic_recovery.py:291`), `file_lock`, `library_lock.identity`/`contains`/`require`, `kept_backups.checked`/`writing`/`_unlink`, and `folder_help.prove`/`_plan`/`_folder`/`_issue`/`_issued`.

**Evidence.**

- **Tests, one run.** One process, `python -E -B -P`, using my runner in scratch. Modules: `test_0_state_isolation`, `test_folder_help`, `test_folder_help_dom`, `test_zz_state_isolation`.
  - Result: **66 run, 48 passed, 18 skipped, 0 failed, 0 errors.**
  - 17 skips are the DOM classes, 13 of them plus 2 × 2 inherited from `YandexDOMTests`. `COMICS_TEST_CDP` was unset, so no browser started and focus was never taken.
  - 1 skip is the "file link" subtest of `test_the_temp_name_as_a_folder_or_a_link_is_not_offered`. This account cannot make symlinks; I checked with a probe in scratch, which got WinError 1314. The folder and junction shapes ran. I checked the symlink refusal by reading the code: `lstat` gives `S_ISLNK` and the reparse bit, so the file is not covered.
- **Guard active (positive control).**
  - Protected roots: `Y:\Comix`, `%LOCALAPPDATA%\comic-metadata-updater`, a scratch canary, and the built-in `%LOCALAPPDATA%\ComicsMeta`.
  - A write to the canary was refused, and no file appeared. `VIOLATIONS == []`.
  - `os.startfile`, `kept_backups._select` and `_open_folder` were recording stubs. They recorded **0** calls.
  - State, locks, `COMICS_META_TEST_SCRATCH` and `COMICS_TEST_EVIDENCE` were all in scratch.
  - `git status --porcelain` was empty before and after.
- **Artifact.**
  - The installer sha256 `a8fd6fe1…c2d7a83` matches. The size, 149,486,506, matches `latest.yml`.
  - The `latest.yml` sha512 `e/Vq7bG6…nn++k4g/Q==` matches, recomputed with `openssl dgst -sha512 -binary | base64`.
  - The exe was written at 09:29:38, after the bump commit (09:29:04).
  - I extracted `$PLUGINSDIR/app-64.7z` with 7-Zip into scratch. All **60** git-tracked files in `resources/engine` equal the HEAD blobs after CRLF normalization, and are byte-equal to the clean working tree. **0 differ.**
  - The only untracked files are `installer_launch.py`, which equals `desktop/installer_launch.py`@HEAD, and the generated `update-runtime-manifest.json`. There is no `.env` or `config.json`.
  - `app.py`, `folder_help.py`, `kept_backups.py` and `static/folder-help.js` are byte-equal to HEAD.
  - The engine `VERSION` and the `package.json` inside `app.asar` both say 0.2.6. The bundled runtime is Python 3.14, so `str | None` in the `NamedTuple` is fine.

**The five focus questions.**

1. **Can a temp file be deleted while a real write uses it?** No.
   - Every writer goes through `write_metadata`. It takes `comic_write_guard`, or refuses unless the thread already holds it (`guard_held=True`, `app.py:524-527`). That is the only place the `.metadata-tmp` name is created (`app.py:561`; `reverse_image.py:100` only tests that it exists).
   - The writer creates the temp file and removes it in `finally`, both under the guard.
   - A new writer refuses when a temp file already exists (`temporary.exists()`). So a leftover is never taken over by a later write.
   - The guard is an OS byte lock (`msvcrt.locking LK_NBLCK`). It is held per handle and works across processes, so a second handle in the same process is refused too. The held-guard test exercises exactly this.
   - The click takes the guard for real before any proof, and keeps it through the unlink (`folder_help.py:665`). `_delete_temporary` refuses unless `write_guard_held(comic)`.
   - Another copy of the app, with another state root and so other write-lock files, is kept out by the machine-wide library claim. `_guarded` claims the library, and `require(temp)` runs again before the unlink.
2. **Can anything outside the exact temp name be deleted?** No.
   - The target is never taken from the request. It is `temporary_path(comic)` from the plan's resolved comic path, rechecked as `temp == temporary_path(comic)` and `comic.parent == folder`.
   - `_temporary_checked` requires the folder, by `lstat`, to be a directory with no reparse bit. It requires the temp, by `lstat`, to be a regular file with no reparse bit. It checks containment in the library on `realpath` identities, so a junction in an ancestor folder is resolved.
   - **8.3 names:** the name always ends in the 12-character `.metadata-tmp`, so it is never a valid 8.3 name. NTFS cannot match it to another file's short name. Plan paths are `resolve()`d to long names.
   - **Trailing dots and spaces:** all I/O uses the `\\?\` form, so names are literal, and the name ends in `tmp`.
   - **Case:** NTFS finds `X.CBZ.METADATA-TMP` as well. That file blocks the app's writer in exactly the same way, so deleting it is the intended action. Only the displayed spelling differs; this is cosmetic.
   - **Hard links:** deleting one only removes that name. A symlink or junction swapped in after the last `lstat` is unlinked as a link, or refused for a directory. Its target is never touched.
3. **Deadlock from holding several guards?** No.
   - Every write-guard acquisition in the code is a non-blocking try. A refusal raises at once: `writing` for the click, `ArchiveChanged` for the worker. No one ever waits on a guard, so no lock order can deadlock.
   - The ExitStack releases every guard on any exit. The fresh check runs only after the release.
   - Under the guards, the only waits are on locks that never wait on a guard: the library claim, already held by `_guarded`, and SQLite in `_forget`.
4. **Is the id-mismatch refusal complete?** Yes.
   - `_matched` builds the set of (code, normcased target) for every finding of this click's own inspection. Every sent id must resolve, for this ticket, to the code of the list it came in.
   - The sent set must equal that whole set, and `_deletable` must hold: every finding is covered, and there are 20 or fewer.
   - An unknown, wrong-ticket or wrong-list id, a missing file, an extra finding, or no offer each refuses before any guard is taken or any file deleted. Duplicates and empty requests are refused earlier.
   - A 0.2.5 page that sends no `temps` is refused as `changed` when a temp file is in the offer.
5. **Can deleting the temp destroy the only good copy?** No.
   - A temp file is covered only when its comic proves `original`: size, mtime and SHA-256 equal the plan's before-state. This is proved again under the guard immediately before the delete.
   - A damaged or changed comic has another finding, so there is no offer. A written comic is never `original`.
   - `os.replace` is atomic. A temp file beside an `original` comic is therefore an aborted write: at most the comic plus a new `ComicInfo.xml`, which the requeue makes again. The comic itself is never touched.

---

## Rubric

### 1. Security

- Status: Pass. The route takes ids only, and no target comes from the request. Folder, link and reparse checks are done by `lstat` before the delete, and there is no shell-out. Electron, IPC and secrets are not touched. See focus answers 1, 2 and 4.

### 2. Correctness & Logic

- Status: Pass, with two notes.
- Findings:
  - `folder_help.py:490-494` with `kept_backups.py:133-146` **[Minor] m1.** The B2.4 probe at the check briefly takes each listed comic's write lock (try, then unlock). A writer of that comic that arrives in that microsecond window gets "Another metadata write is in progress" and skips the comic instead of writing. The primitive existed already (A7.4); this is a new call site that runs on every check with an offer. Nothing is lost: the comic is planned again.
  - `folder_help.py:665-669` **[Minor] m2.** When a guard cannot be taken, the code calls `kept_backups.writing()` again to choose the code. A writer that finishes in between turns `writing` into `other` ("a comic could not be locked"). An `OSError` from `comic_write_guard` (lock folder or `open_lock`) is not mapped and reaches the generic handler. In both cases nothing is deleted.

### 3. Crash / Stability Safety

- Status: Pass. Every failure before the first delete deletes nothing. After the first delete, the page reports `delete_failed`/`writing` with the counts. The guards are released by the ExitStack on every path. The unmapped `OSError` is m2.

### 4. Performance

- Status: Concerns (Minor).
- Findings:
  - `folder_help.py:646` and `:717` **[Minor] m3.** The click now runs a full `_inspect` before the guards: `testzip` and SHA-256 over every write comic in the plan, not only the offered ones. Then come the proofs under the guards and the full closing `_check`. That is roughly one more full pass than in 0.2.5, all under `_BUSY`. B9.1 requires it ("recomputes the whole offer from disk"), and the page warns "a few minutes". On a large plan on a network library, expect the click to take about twice as long.

### 5. State & Data Safety

- Status: Pass.
  - Deletes are proved under the guard before they run.
  - The temp file goes before the backups, so a partial failure keeps the recovery copy.
  - A file that is already gone counts as done but is not counted as deleted.
  - Backups keep the 0.2.5 M1 hash rule.
  - `_tidy` empties the backup folder exactly as `delete_one` did before.
  - See focus answer 5.

### 6. Input Handling

- Status: Pass.
  - The route accepts exactly `{ticket, backups}` or `{ticket, backups, temps}`.
  - The ids must match `[0-9a-f]{32}`, with no duplicates and 1 to 20 in total.
  - `temps: null` is read as an empty list. That is harmless: it can only shrink the sent set, which then fails the equality check.

### 7. Maintainability (no Critical findings on its own)

- Status: Concerns (Minor).
- Findings:
  - `kept_backups.py:278-289`, `folder_help.py:362` **[Minor] m4.** `delete_one(before_unlink=)` no longer has a caller that passes the hook. `_delete_temporary` calls the private `kept_backups._unlink`. Drop the hook, or make `_unlink` public as a shared "delete one regular file" helper.

### 8. Doc/Code Drift (no Critical findings on its own)

- Status: Pass. The module and function docstrings match B2, B9.1, B9.2 and B9.3. The `app.py` route comment names B9.4. B9.1 says an id "no longer a file of this ticket" should give `file_gone`; an id evicted from the in-process map (more than 1,000 issued, or after a restart) gives `changed` instead. Both refuse, so this is not a finding.

### 9. Build & Release Hygiene

- Status: Pass.
  - `VERSION`, `package.json` and both `package-lock.json` entries move to 0.2.6 in one commit, 7b3d93a.
  - The artifact, `latest.yml` and the packaged engine match HEAD. See the evidence above.
  - No secrets are packaged.

---

## Patterns

The v0.2.5 Minors m1 to m7 are untouched by this range and remain open; for example, spec §8.3 and A8.6 still say `scheduler.finish`. As in v0.2.5, the new error mapping leaves a few rare `OSError` paths unmapped, which show the generic message (m2, as v0.2.5 m6).

---

## Verdict

- Total Critical: 0
- Total Major: 0
- Total Minor: 4 new (m1 to m4); v0.2.5 m1 to m7 carried

**Verdict:** RELEASE CLEAR

| # | Sev | Dim | file:line | Finding | Next cycle |
|---|-----|-----|-----------|---------|------------|
| m1 | Minor | 2 | `folder_help.py:490-494` | The check-time `writing()` probe briefly takes the write lock, so a writer arriving in that instant skips the comic. | Accept, or probe by trying to open the lock file without locking it. |
| m2 | Minor | 2 / 3 | `folder_help.py:665-669` | A failed guard is classified by a second probe that can race (`writing` becomes `other`), and an `OSError` from `comic_write_guard` is unmapped. | Map every guard failure to `writing` or `other` in one step; catch `OSError`. |
| m3 | Minor | 4 | `folder_help.py:646, 717` | The click runs one more full inspection of every plan comic, under `_BUSY`. | Accept per B9.1, or skip `testzip` for comics with no temp or backup finding. |
| m4 | Minor | 7 | `kept_backups.py:278-289`, `folder_help.py:362` | A dead `before_unlink` hook, and a private `_unlink` used across modules. | Remove the hook; make the unlink helper public. |
