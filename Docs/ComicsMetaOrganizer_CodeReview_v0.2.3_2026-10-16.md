# Code Review — Comics Meta Organizer v0.2.3

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-16
Tool: Comics Meta Organizer
Release: v0.2.3
Commit range: 144adfcc6592e3ce7b92075e286c47cfacaeed45..6f43d4d99e9a85f56825dbc2ef3d3a8cace11b36
              (v0.2.2 tag commit to the 0.2.3 bump; continues the v0.2.2 record, whose Addendum 2 ended at 374250c; 374250c..144adfc is docs only)
Files changed: 29 files, +730 / -173 (code only, Docs excluded: 26 files, +590 / -171)
Worktree: C:/Antigravity Projects/Worktrees/Comics Meta Organizer/installer, branch feat/m1-state-split, tree clean at review
Artifact examined (not run): dist/Comic-Metadata-Setup-0.2.3.exe, 149,453,847 B, sha256 0907c11210c6a16c37c91bc04c6a7b21b896cb9769e91beab64511a325d91d8e
Stand-down dimensions: none
```

---

## Summary

The range makes four changes:

1. It removes the SerpApi fallback. `SERPAPI_API_KEY` becomes a retired name, so an older encrypted key store still opens.
2. Key names now match in any case in the environment, the state-root `.env` and config `env_file`.
3. A new `/api/cover?id=N` route returns a read-only, bounded JPEG preview of the archive's own cover (`reverse_image.preview`).
4. A per-comic recovery save now deletes its backup once the change is verified.

I read the whole code diff red-team style. I ran the touched test modules once, in one process, with the isolation modules. I ran two small probes in scratch: decompression bounds and replace-while-held. I also compared the built artifact with HEAD.

There are no Critical findings, and the safety floor is intact. Answers to the brief's focus questions:

- **(4) Recovery backups.** I found no path that deletes a backup before the comic is proven good. Deletion runs only after `write_metadata` (temporary `testzip`, page CRC/size equality, ComicInfo readback, `os.replace`, final readback) and the full `after == dict(old, **fields)` check. It deletes only a backup whose bytes still equal the SHA-256 taken under the writer guard.
  - Automatic writes cannot race it: the cross-process `comic_write_guard` and `app.LOCK` are held from the stale check through the deletion. An automatic writer for the same comic gets `ArchiveChanged`.
  - Every refusal keeps the backup.
- **(3) Cover preview.**
  - **No path or ID injection.** The route takes an integer id and gets the path from the catalog.
  - **Cross-origin access is refused**: Host pinning, `Sec-Fetch-Site`, and no CORS header.
  - **Read-only is proven by test**: bytes, size, mtime and the folder listing are unchanged.
  - **The "≤20 MB first image" bound is not real against a crafted archive.** That is P1 [Major], measured.
  - **A preview can make a concurrent write's `os.replace` fail.** The window is narrow and the failure is safe. That is P2 [Minor].
- **(2) Key-name case.** No key can be shadowed by a different key's name; near-miss names are refused, and the test covers this. A same-name, different-case line can shadow the exact one, and non-ASCII case folding widens the match. That is P4 [Minor].
- **(1) SerpApi.** No network path to serpapi.com is left, in the source or in the packaged engine and `app.asar`.

**Evidence:**

- **Tests.** `test_0_state_isolation` + `test_browser_cooldown`, `test_browser_search`, `test_comic_recovery`, `test_lens_holds`, `test_lens_skips`, `test_reverse_image`, `test_setup_state`, `test_state_root` + `test_zz_state_isolation`, in one process: **108 run, 108 passed, 0 failed, 0 skipped.** The Windows-only sharing test ran.
- **Guard active (positive control).**
  - The protected roots, as printed by the guard, were the worktree's `data/`, `batches/`, `config.json` and `.env`, `%LOCALAPPDATA%\ComicsMeta`, `Y:\Comix`, the live checkout `WIP/Comics Meta Organizer`, and a scratch canary folder.
  - An `open()` for write on the canary was refused by the guard ("Test isolation refused open on live state"), and no file was created.
  - The suite's own refusal test passed, and `test_zz` found `VIOLATIONS == []`.
  - The state root and lock folder pointed into scratch.
  - The guard refuses binds and connects to 8765/11434.
  - Bytecode writing was off.
- **Probe A, decompression.** The probe used a 300 MB zero-filled `01.jpg` whose local and central headers declare 1,000,000 bytes, run through the real `reverse_image.preview` in a child process. Peak commit went from about 20 MB to 622 MB (deflate, 306 KB archive), 625 MB (bzip2, **352 B** archive) and 630 MB (LZMA, 44 KB archive). Every case ended in `NoPreview` (cause `BadZipFile`, the CRC check), but only after the full decompression.
- **Probe B, replace while held.** While `reverse_image.open_shared` holds the archive, `os.replace(tmp, archive)` fails with `PermissionError` (winerror 5). A plain `open()` gives the same result. The original stays intact and the temporary file is left for the caller's cleanup.
- **Artifact vs HEAD.**
  - **Hashes.** The exe's sha256 equals the brief. `latest.yml` gives version 0.2.3, and both its top-level and `files[0]` sha512 (`+kXYefYP…ZaDLg==`) and size 149,453,847 equal the exe.
  - **Engine files.** From the exe's own `$PLUGINSDIR/app-64.7z`, `resources/engine` holds 58 files:
    - 56 are byte-identical to their HEAD 6f43d4d blobs (`git hash-object` run outside any repo, so there was no line-ending filter).
    - `installer_launch.py` equals the `desktop/installer_launch.py` blob.
    - `update-runtime-manifest.json` is generated. Its `helperSha256` equals that file's sha256.
    - The file set exactly equals HEAD's top-level `*.py`, `requirements.txt`, `VERSION` and `static/`: nothing extra, nothing missing.
  - **`app.asar`.** All 34 desktop files equal HEAD. Only the builder-rewritten `package.json` differs, and it reads version 0.2.3.
  - **No secrets or leftovers.** No secret-like strings were found. The only "serpapi" text in the packaged engine and asar is `credential_store.py`'s retired-name tuple and comment.

---

## Rubric

### 1. Security

- Status: Concerns
- Findings:
  - **P1 [Major]** `reverse_image.py:99-101`: preview decompression is bounded by nothing the file cannot lie about.
    - **What fails.** The 20 MB check reads `ZipInfo.file_size` from the central directory, and `archive.read()` then decompresses before that size is enforced.
      - Python's `ZipExtFile.read()` asks for up to 2 GiB of deflate output per call.
      - It decompresses bzip2 and LZMA entries with no output limit at all.
      - The `compress_size ≤ 40 MB` check does not help: a 352-byte bzip2 entry produced 300 MB (probe A).
    - **Worst case.** One crafted entry can drive a decode to about 2–4 GB (deflate), or to unbounded growth (bzip2/LZMA) until `MemoryError`. Two decode slots can run at once.
    - **Effect on writes.** The archive handle stays open during that decompression, so a concurrent write to that comic fails at `os.replace` (P2).
    - **Context.** `reverse_image.cover()` (`:18-26`) has the same pattern, before this range. Its callers already run it automatically on library comics: `research.py:132/464`, `providers.py:100`, `metron.py:99`, `automatic.py:101`, `browser_search.py:66`, `local_model.py:226` and `publisher_catalogs.py:133`. So this range does not widen the realistic exposure.
    - **Why Major, not Critical.** It needs a deliberately crafted archive in Sergei's own library. The path is read-only, nothing is written or lost, and `MemoryError` is caught and becomes `NoPreview`.
    - **Fix.** Use one shared bounded reader for `cover()` and `preview()`:
      - accept only `ZIP_STORED` and `ZIP_DEFLATED` entries (real comics use these);
      - read through `archive.open(info)` in chunks of 1 MB or less;
      - stop once the total passes `COVER_BYTES`.
  - **P3 [Minor]** `app.py:783-786`: the older `?id=N&index=K` route skips the new route's `Sec-Fetch-Site` and exact-arguments checks.
    - A cross-site page can make the engine open and read library archives through `<img>`. It can also reach P1's decompression this way.
    - It cannot read the pixels: there is no CORS header, and the Host pin blocks DNS rebinding.
    - This predates the range. The dashboard's own caller (`static/reverse-image.js`) is same-origin, so the same guard costs nothing.
  - Pass otherwise:
    - **(3) The new route.**
      - `int()` id, then a catalog lookup, so the path is never taken from the request.
      - An exact argument set.
      - `Sec-Fetch-Site` must be absent, `same-origin` or `none`.
      - `Content-Type: image/jpeg`, `nosniff`, `no-store`.
      - Errors are the fixed `NoPreview` text.
    - **`open_shared`.**
      - Win32 `CreateFileW` with GENERIC_READ and share READ|WRITE|DELETE, OPEN_EXISTING, not inheritable.
      - The handle is checked for both NULL and INVALID_HANDLE_VALUE.
      - The handle is closed if `open_osfhandle` fails.
    - **Pillow** is formats-restricted (JPEG/PNG/WEBP) and checks pixels from the header before any decode; the test proves `load()` is not called for 64 MP. Text and ICC chunks are bounded by Pillow 12.2.0.
    - **Renderer.** All new nodes are built with `createElement`/`textContent`. The ComicVine cover must be `https://` and loads with `no-referrer`.
    - **(1) SerpApi.** No `urllib` path, quota reservation or host exclusion remains. Old `browser_search.serpapi_fallback`/`serpapi_monthly_limit` settings are ignored. The retired key is never offered (`setup.js`, `comic-recovery.js`), never accepted on save (`setup_state.save`/`save_keys` check `ALLOWED_KEYS`; tested), and never reported.
    - **Electron.** Only the `setup.js` field list changed. IPC, CSP and BrowserWindow settings are untouched.

### 2. Correctness & Logic

- Status: Pass.
  - **`browser_worker.process`.** Without the fallback, the outcome branches reduce correctly: leads → record; `lens == SEARCHED` → one-day retry; not Held → could-not-finish; Held → release keeping the queue place. The tests cover this.
  - **`confirm()`.** It reports `backup_retained = not removed` and `backup_removed_after_verification`, with tests for removed, refused and failed verification. One of these tests uses a real archive and the real writer.

### 3. Crash / Stability Safety

- Status: Concerns. See P1's memory growth.
  - Every other preview failure becomes the one `NoPreview` (400). The decode slots are released in `finally`, and a slot wait gives up after 10 s.
  - `discard_verified_backup` swallows only the removal's own failure, after the save is verified.

### 4. Performance

- Status: Pass.
  - **Recovery save.** It now reads the archive twice more: the original hash and the backup re-hash. Both happen while `app.LOCK` and the writer guard are held. That is the same cost the automatic and `/api/apply` paths already pay, and it applies only to a save Sergei starts himself.
  - **Preview.** A JPEG is drafted at reduced scale. Pixels are capped at 40 MP (about 160 MB per decode) and at most two decodes run at once.

### 5. State & Data Safety

- Status: Concerns. Nothing here risks data, but P2 is a new in-app cause of a refused write.
- Findings:
  - **P2 [Minor]** `reverse_image.py:73-101`: the `.metadata-tmp` check cannot see a write that has not created its temporary file yet.
    - **The writer's order.** `_write_metadata_guarded` checks the stat, hashes the archive (on the paths that remove their own backup), parses it and copies the backup. Only then does it create the temporary file (`app.py:591` copies the backup, then the temporary is written, then `:617` replaces).
    - **The race.** A preview that opens during that phase and is still reading when the writer reaches `os.replace` makes the replace fail. Probe B measured winerror 5.
    - **How likely.** The window is narrow: after the temporary exists, the writer rewrites and `testzip`s the whole archive, while the preview reads one image.
    - **Effect.** The failure is safe in every caller:
      - the original stays intact;
      - recovery returns "not verified" and keeps its backup;
      - `batch.py` records `write_failed`, discards the redundant backup and offers the comic again later;
      - `/api/apply` shows the error and leaves its backup behind.
    - **Docstring.** The docstring's "Nothing is opened while a metadata write is under way" overstates this.
    - **Fix (either one).** Have the writer create its marker before hashing and copying the backup, or retry `os.replace` a few times on a sharing refusal.
  - Pass otherwise:
    - **(4) Order in `confirm()`** (`comic_recovery.py:251-288`):
      1. Guard and `app.LOCK` acquired.
      2. Pause check.
      3. Fresh `snapshot()`, which compares the on-disk stat with the planned row.
      4. Provider revision check.
      5. `archive_sha256`.
      6. `write_metadata(..., verify_readback=True, guard_held=True, remove_verified_backups=False)`. The test asserts `False`.
      7. Full-snapshot equality.
      8. Only then `remove_verified_backup`.
    - **What `remove_verified_backup` checks.** It re-checks the library claim. The backup must sit in the comic's own `.comic-metadata-backups` folder, carry the `<name>.<time_ns>.bak` shape, and be neither a symlink nor a reparse point. It must hash to the pre-copy SHA-256.
    - **When the archive changes in between.** If an outside program changes the archive between the hash and the copy, the write fails its stat check, or the hashes differ and the backup is kept. Both outcomes are safe.
    - **Other writers.** Automatic writers in any process are excluded by the OS-held per-archive lock for the whole sequence.
    - **The emptied backup folder.** `rmdir` can make a different comic's writer in the same folder fail at `copy2` (FileNotFoundError, before anything is written). That is the pre-existing automatic-path behaviour, safe, and not new to this range.
    - **Retired key.** The retired key stays in the DPAPI store exactly as saved; `save_keys` merges into it (tested).

### 6. Input Handling

- Status: Concerns.
- Findings:
  - **P4 [Minor]** `credential_store.py:128` (and `_environment`, `:98-106`): case-insensitive key names have two side effects.
    - **First match wins.** Within one env file the first line that matches in any case wins. A stale `comicvine_api_key=` line above the canonical `COMICVINE_API_KEY=` now shadows it, where 0.2.2 took the exact line. A lower-case line in the state-root `.env` likewise beats an exact one in `env_file`.
    - **Non-ASCII folding.** `str.upper()` folds non-ASCII letters: `'BRAVE_ſEARCH_API_KEY'.upper() == 'BRAVE_SEARCH_API_KEY'`, and `'COMıCVINE…'` matches the same way (verified).
    - **Limits.** This affects only Sergei's own files. No value leaves the process; key status is boolean only. A different key's name never matches.
    - **Fix.** Prefer an exact-case match within each source, and fold ASCII only, for example `key.isascii() and key.upper() == name`.
  - On Windows, `os.environ` is already case-insensitive, so the new environment scan is a no-op there.

### 7. Maintainability (no Critical findings on its own)

- Status: Pass.
  - **Code.** `reverse_image.images()` now gives every caller one definition of the archive cover. The SerpApi removal leaves no dead branches.
  - **F41 (carried) grew.** `static/comic-recovery.js:24-25` adds two more single-line functions (`coverFigure`, `coverStrip`) of several hundred characters each.

### 8. Doc/Code Drift (no Critical findings on its own)

- Status: Concerns, covered by findings elsewhere.
  - The `preview()`/`writing()` docstrings overstate the write exclusion (P2).
  - `Docs/ComicsMetaOrganizer_UXSpec_FileCover_2026-10-16.md:117` ("refuses a first image over 20 MB") holds only for honest headers (P1).
  - The Brief, README, `SOURCE_CONNECTORS.md`, `.env.example`, `config.example.json` and the PerComicRecovery spec's superseded note match the code.

### 9. Build & Release Hygiene

- Status: Pass. The artifact equals HEAD, as shown under Evidence.
  - **Versions.** `VERSION`, `package.json` and `package-lock.json` are 0.2.3, with version-only changes.
  - **For Sully:**
    - `CHANGELOG.md` has no v0.2.2 or v0.2.3 entry. That is the pipeline's step, not a code finding.
    - `dist/` also holds the 0.2.1 and 0.2.2 exes and blockmaps. Upload only the 0.2.3 exe, its blockmap and `latest.yml`.
  - **Carried Majors.** N2 (build inputs from gitignored scratch) and N3 (`scripts/release.mjs` expects held receipts) remain open per the v0.2.2 record. This range does not touch `scripts/`, and I did not re-examine them.

---

## Patterns

**Defences that trust the file.** The cover reader trusts sizes the file declares, both before this range in `cover()` and now in `preview()`. A single bounded reader would close P1 for every caller at once.

**Exclusion checks with gaps.** As in v0.2.2's N1, an exclusion check needs a positive control against its real counterpart. P2's marker can't see the writer's first phase, and P3 is a cross-origin guard applied to one route but not its sibling.

---

## Verdict

- Total Critical: 0
- Total Major: 1 new (P1); 2 carried open (N2, N3), not re-examined
- Total Minor: 3 new (P2, P3, P4); carried N5–N11, F11–F15, F19, F25–F28, F30, F31, F41 (F41 grown)
- Safety-floor violations: 0

**Verdict:** RELEASE CLEAR

**Scope.** This certifies the source range above. It confirms that the examined 0.2.3 artifact (sha256 0907c112…) carries exactly the HEAD 6f43d4d engine and desktop files.

**Not certified.** Installed behaviour, the 0.2.2→0.2.3 update, and publication; those belong to Futaba and Sully.

**Not done.**
- No app, installer or build was run, and nothing was written to git.
- I did not touch `%LOCALAPPDATA%\ComicsMeta`, `Y:\Comix`, port 8765 or the live checkout; the guard covered all of them during the test run.
- Scratch was removed afterwards, except my own `app.asar` extraction (`senua023/asar/`, about 2.5 MB). The cleanup planner refuses it because it contains `node_modules`, so it is left for Jane to decide.

**Next cycle.** P1 is the one to fix: one shared bounded reader for `cover()` and `preview()`.
