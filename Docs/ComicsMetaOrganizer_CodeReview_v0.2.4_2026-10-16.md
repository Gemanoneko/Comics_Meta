# Code Review — Comics Meta Organizer v0.2.4

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-16
Tool: Comics Meta Organizer
Release: v0.2.4
Commit range: 6f43d4d99e9a85f56825dbc2ef3d3a8cace11b36..e2db1c39c2d0f4353977f782f1ee1282184effdd
              (the 0.2.3 bump to the 0.2.4 bump; continues the v0.2.3 record, which ended at 6f43d4d)
Files changed: 25 files, +2202 / -38 (code only, Docs excluded: 21 files, +1586 / -38)
Worktree: C:/Antigravity Projects/Worktrees/Comics Meta Organizer/installer, branch feat/m1-state-split, tree clean at review
Artifact examined (not run): dist/Comic-Metadata-Setup-0.2.4.exe, 149,466,701 B, sha256 0492626650fe202cc15a9acaaa9677f5458fc271e8096e7f50b132fd979d1da9
Stand-down dimensions: none
```

---

## Summary

The range makes four changes:

1. **Update fix.** Engine children get `PYTHONDONTWRITEBYTECODE=1`. Supervisor workers start with `-B`. The installed-runtime check in `update-capsule.cjs` now leaves out an unlisted `__pycache__` that holds only regular `.pyc` files. The capsule copy is still checked strictly.
2. **Kept backups.** New `kept_backups.py`, the routes `GET /api/backups`, `POST /api/backups/reveal` and `POST /api/backups/delete`, and `static/kept-backups.js`. `/api/apply` now reports each save outcome separately.
3. **Bounded cover reader.** `reverse_image.read_image()` reads stored and deflate members only, in 1 MB pieces, with a cap on the bytes actually decompressed.
4. **Small fixes.** The `; ;` link removal, a clean 400 on a bad cover id, and the read-only `not_saved` outcome in recovery.

I read the whole code diff red-team style. I ran the touched test modules with the isolation modules and the Node desktop tests. I ran one small probe on `os.path.abspath`, and I compared the built artifact with HEAD.

There are no Critical findings, and the safety floor is intact. Answers to the brief's questions:

- **(1) Can the relaxed check let a tampered runtime into the capsule? No.**
  - The capsule is built from the manifest alone. Each listed file is re-hashed as it is copied, and the finished capsule is checked strictly against the manifest. An unlisted `.pyc` is never copied.
  - A skipped folder must be named exactly `__pycache__`, must not be listed in the manifest, and must hold only regular, non-link files named `*.pyc` or `*.pyc.<digits>`. Anything else (a link, a subfolder, a `.py`, a `.txt`) keeps the folder in, and the check refuses. A junction `__pycache__` is refused before the skip is considered. A *file* named `__pycache__` is inventoried and refused.
  - The helper runs from the capsule with `-I -S -B`, and its `_pth` paths are proven to stay inside the capsule (`modulePaths`). No installed-runtime `.pyc` is ever on its path. Also, Python never imports a `__pycache__` `.pyc` that has no source beside it.
  - What the relaxation does give up: a planted `.pyc` in the *installed* runtime is no longer noticed at update time. That is not a security boundary. The engine would already have loaded it, and anyone who can write there can replace `python.exe`.
- **(1) But the fix cannot deliver itself over the in-app route from 0.2.3.** That is **M1 [Major]**, below.
- **(2) Kept backups: no path traversal, forgery, CSRF or injection found.**
  - No route takes a path. An id is HMAC-SHA256 under a 32-byte secret made once per process, truncated to 128 bits. It resolves only through the in-process map of ids the server itself issued. After a restart the secret and the map are new, so every old id returns `not_found`.
  - `checked()` runs twice: once on resolve, and again under the comic's write guard just before the unlink. It requires a `<name>.<1-20 digits>.bak` regular file, in a non-reparse `.comic-metadata-backups` folder, inside the configured library after `realpath`.
  - A write in progress makes `delete` fail with `writing`. The OS byte-range lock conflicts across handles, including in the same process, and the test covers it.
  - POST pins `Origin` and `Host`. GET pins `Host` and refuses cross-site `Sec-Fetch-Site`. No CORS header is sent.
  - Reveal calls `ILCreateFromPathW` and `SHOpenFolderAndSelectItems` in-process, from KnownDLLs. Its fallback is `os.startfile` on the already-validated `.comic-metadata-backups` folder. Nothing is spawned, so there is nothing to inject into.
  - The page sets all text with `textContent`.
  - What is left is a narrow same-user TOCTOU window, **m4**.
- **(3) Bounded reader: sound.** The decompressor comes from the central directory's `compress_type`, and only stored and deflate are allowed. `ZipExtFile` stops at the declared size, which is checked to be at most 20 MB. Each `decompress` call is limited to 1 MiB. The new tests measure this with `tracemalloc` and include a positive control (`archive.read` on the same lying fixture goes over the real size).

**Evidence:**

- **Python tests.** One process, with `python -I -B`: `test_0_state_isolation`, `test_comic_recovery`, `test_kept_backups`, `test_kept_backups_dom`, `test_supervisor`, `test_zz_state_isolation`. Result: **57 run, 47 passed, 10 skipped, 0 failed.**
  - The 10 skips are the DOM classes. `COMICS_TEST_CDP` was not set, so no headless browser started.
  - `test_reverse_image` did not import in that run: `-I` hides Pillow, which is in the user site. I ran it once on its own with the isolation modules, using `python -E -B -P`: **14 run, 14 passed** (11 reverse-image tests plus the 3 isolation tests).
- **Guard active (positive control), in both runs.**
  - The extra protected roots were `Y:\Comix`, the live checkout `WIP\Comics Meta Organizer`, `%LOCALAPPDATA%\comic-metadata-updater` and a scratch canary. The built-in roots were the worktree's `data/`, `batches/`, `config.json` and `.env`, and `%LOCALAPPDATA%\ComicsMeta`.
  - An `open()` for write on the canary was refused, and no file appeared.
  - `VIOLATIONS == []`.
  - The state root, the lock folder, `COMICS_META_TEST_SCRATCH` and `COMICS_TEST_EVIDENCE` were all in scratch.
  - `os.startfile`, `kept_backups._select` and `_open_folder` were replaced by recording stubs. They recorded **0** unstubbed calls, so File Explorer was never opened.
  - `git status` was identical before and after (clean).
- **Node tests.** `node --test desktop/tests/` with the scratch in `COMICS_META_TEST_SCRATCH`: **45 tests, 43 passed, 2 skipped, 0 failed.** Both skips are opt-in, gated on `COMICS_META_TEST_BUILDER_MODULES` and `COMICS_META_TEST_ACTUAL23_JOBROOT`. The three new capsule tests and the engine-spawn test passed.
- **Artifact vs HEAD.**
  - **Hashes.** The exe's sha256 equals the brief. `latest.yml` gives version 0.2.4, and both its top-level and `files[0]` sha512 (`kjpJHV4H…q/KiIA==`) and size 149,466,701 equal the exe. Measured with `openssl dgst -sha512 | base64` and `stat`.
  - **Installer payload.** I extracted `resources/engine`, `resources/app.asar` and `resources/runtime` from the exe with the repo's `7za`. They are byte-identical to `dist/win-unpacked` (`diff -rq`, `cmp`).
  - **Engine.** It holds 60 files:
    - 59 equal their HEAD blobs after CRLF normalisation (`core.autocrlf=true`; the working tree is clean). Every top-level `.py` and every `static/*` in HEAD is present.
    - The 60th, `update-runtime-manifest.json`, is generated (sha256 `f0d830f5…`).
    - `engine/VERSION` is `0.2.4`.
  - **app.asar.** All 16 `desktop/` code files equal HEAD. All 18 `desktop/assets` files match HEAD by the asar header's SHA-256 and size. `package.json` differs only by electron-builder's removal of `scripts` and `devDependencies`. `desktop/tests` is not packaged.
  - **Runtime.** The packaged `runtime/python` equals its manifest under the strict inventory: 465 files, 51 folders, **0 `.pyc`, 0 `__pycache__`**. The manifest's `helperSha256` equals `engine/installer_launch.py`.
- **Probe (outside range).** Python 3.14.8 `os.path.abspath('\\?\Y:\Comix\Foo.\bar.cbz')` returns `'\\?\Y:\Comix\Foo\bar.cbz'`. See O2.

---

## Rubric

### 1. Security

- Status: Pass
- Findings:
  - `kept_backups.py:276-281` — A same-user process could swap `.comic-metadata-backups` for a junction between the under-guard `checked()` and `unlink()`. The unlink would then follow it to a same-named `<comic>.<digits>.bak` elsewhere. This needs local same-user write access, so it crosses no privilege boundary. **m4 [Minor]**

### 2. Correctness & Logic

- Status: Concerns
- Findings:
  - `desktop/update-capsule.cjs:46` and `supervisor.py:23` (both as shipped in **0.2.3**, `6f43d4d`) — The in-app update *from* 0.2.3 still runs 0.2.3's strict check. 0.2.3's workers start without `-B` and write `__pycache__` under `runtime/python/Lib/site-packages`; Futaba's 0.2.3 QA measured 9 `.pyc` under `PIL`. So Sergei's 0.2.3 → 0.2.4 in-app update is expected to refuse again with "Update runtime source closure differs". This is the same failure he hit, and 0.2.4 cannot fix it, because the updating code is 0.2.3's. Only updates *from* 0.2.4 benefit. To reach 0.2.4, Sergei must run the 0.2.4 installer by hand, or clear those `__pycache__` folders first. The release handoff must say so, or it will announce a fix he cannot get through the button. (Inferred from the code and Futaba's 0.2.3 measurement. Sergei's install was not inspected, per the brief.) **M1 [Major]**
  - `app.py:996-1003` — Lookup Apply does not tell the read-only case apart. A read-only comic fails at `os.replace` after the backup copy and is reported as "not verified … may be its only good copy" (`save_not_verified`), although the file is unchanged. Recovery uses `not_saved` for the same case. This errs on the safe side; it is wording only. **m1 [Minor]**

### 3. Crash / Stability Safety

- Status: Pass. New route errors go to 400 codes, `record()`/`_forget()` never raise, and the COM init/uninit pairing is correct (S_OK/S_FALSE only).

### 4. Performance

- Status: Pass. On page load and panel open, `listing()` checks one `.comic-metadata-backups` folder per catalog comic folder, on 8 threads, in a request thread. It never runs on the 2-second poll. This is acceptable for a NAS library; watch it if `Y:\Comix` grows into tens of thousands of folders.

### 5. State & Data Safety

- Status: Concerns
- Findings:
  - `kept_backups.py:133-146` — The listing's `writing()` probe briefly takes the comic's real write lock. A writer, including an automatic worker in another process, that starts in that instant is refused with "Another metadata write is in progress" and skips that comic for the pass. Nothing is lost. **m2 [Minor]**
  - `kept_backups.py:284-288` — `path.parent.rmdir()` runs outside the comic's guard. Another comic in the same folder can be mid-write between its `backup_dir.mkdir` and `shutil.copy2`. Its copy then fails, so that write fails before any change. This is the same pattern as the existing `app.remove_verified_backup`. **m3 [Minor]**
  - `kept_backups.py:262-267` — If the retry unlink fails after `chmod` (the file is in use), the backup is left with its read-only attribute cleared. **m5 [Minor]**
  - File-delete validation (Illuminati focus): Pass. Delete goes by id only and is re-validated under the guard. It requires the backup name pattern, refuses links and reparse points, contains the path in the library after `realpath`, and holds the library claim.

### 6. Input Handling

- Status: Pass. Bodies must have exactly the allowed keys. `ids` must be 1-500 unique strings and an id must match `[0-9a-f]{32}`. `/api/backups` refuses any query string. The cover `id`/`index` must match `[0-9]{1,18}`, which is ASCII-only.

### 7. Maintainability (no Critical findings on its own)

- Status: Pass. `kept_backups` follows the existing `import app` pattern of `comic_recovery` and `library_lock`, which is consistent, though it inherits that pattern's `__main__`-vs-`app` double module. Its OS-level locks keep the guard correct across both copies.

### 8. Doc/Code Drift (no Critical findings on its own)

- Status: Concerns
- Findings:
  - `CHANGELOG.md` — The last entry is v0.2.1. There is nothing for 0.2.2, 0.2.3 or 0.2.4, including 0.2.4's permanent-delete feature. **m6 [Minor]**
  - The Brief's decision rows for the cover reads and the backup routes match the code.

### 9. Build & Release Hygiene

- Status: Pass. The version moves in `VERSION`, `package.json` and `package-lock.json` (both version fields) in the bump commit. The artifact equals HEAD, and the packaged runtime has no bytecode. No secrets were found in the diff or in the packaged engine. **M1** is a release-path note, recorded under dimension 2.

---

## Outside the range (not counted; for Ender's next cycle)

- **O1. The same declared-size trust remains in sibling readers.** These were not touched by the range and are not part of 0.2.4's change. Severity if fixed in range: Major, as 0.2.3 P1.
  - `local_model.py:107` and `:199` (`opening_images`, `credits_pages`) and `app.py:195-197` (`read_metadata`, ComicInfo) check the *declared* `file_size`, then call `archive.read()`.
  - These run automatically on library comics. A lying member is decompressed in full before the CRC check fails.
  - `read_image()` is the fix pattern to reuse.
- **O2. `app.filesystem_path` does not keep trailing-dot folder names, despite its docstring.**
  - `os.path.abspath` normalises `Foo.` to `Foo` even under `\\?\` (probe above). Comics in such folders resolve to a sibling path.
  - `kept_backups` inherits this consistently: it lists and deletes the file it actually found.
  - The defect is pre-existing (since `fedfea7`) and has no test.

---

## Patterns

The rmdir-outside-guard (m3) and the not-read-only-aware failure wording (m1) repeat earlier shapes: `remove_verified_backup` has the same rmdir, and 0.2.3's m1 was about read-only wording. Fixes go to one path, and the sibling path keeps the old behaviour. O1 is the same shape. A grep for the sibling call sites when closing a finding would catch these.

---

## Verdict

- Total Critical: 0
- Total Major: 1
- Total Minor: 6

**Verdict:** RELEASE CLEAR

No Critical findings; the safety floor is intact. M1 is not a code defect in 0.2.4, but it must be in the release handoff: to get from 0.2.3 to 0.2.4, Sergei installs by hand, not through the in-app update.
