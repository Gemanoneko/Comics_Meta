# Code Review — Comics Meta Organizer v0.2.2

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-16
Tool: Comics Meta Organizer
Release: v0.2.2 (first public standalone installer)
Commit range: f39812fc082a3e406854b0a29ba7ca4248ef1d97..047a1381408da3bb128ebf85d4b7cd7449854a57
Files changed: 40 files, +2945 / -101 (code only, Docs excluded: 34 files, +2001 / -100)
Worktree: WIP/Comics Meta Organizer-m1, branch feat/m1-state-split, tree clean at review
Artifact examined (not run): dist/Comic-Metadata-Setup-0.2.2.exe, 149,449,509 B, sha256 53e8485722c3cf537453aaa16e67bb605c97b031193f186c720bd8c3ec2bdd68
Stand-down dimensions: none
```

---

## Summary

The range swaps the held build supervisor for a lean build (`npm run pack` → `scripts/build-installer.cjs` → `scripts/packaging/build-lean.cjs`). It adds a pure-JS NSIS uninstaller route (`nsis-safe/`), a MAX_PATH preflight (`nsis-path-bound.cjs`) and the exit-code fix (`failure-exit.cjs`). It also rewrites private QA isolation (`qa_runtime.py`, `qa-policy.cjs`, the Electron session filter, model-port routing), the engine owner handshake (`engine_host.py`) and directory holds in the update helper (`installer_launch.py`), then bumps the version to 0.2.2.

I read the whole code diff red-team style. I also ran the Node shell tests and the Python tests for the changed areas, using f39812fc as a baseline to compare against. On top of that I checked the built artifact against HEAD and ran three small probes in scratch: QA guard behaviour, the effect of a held directory on renames, and the effect of a different share mode.

There are no Critical findings and the safety floor is intact. There are four new Major findings. The most important is N1: the update helper's new directory holds block renames into the user-profile folders system-wide while the installer runs.

**Evidence (summary):**
- **Node tests.** 41 tests: 39 passed, 0 failed, 2 skipped. The 2 skips are optional actual-vendor/actual23 variants whose environment variables were not set.
- **Python tests, per module, each in its own process.** test_installer_launch 15/15, test_comic_recovery 17/17, test_setup_state 20/20, test_library_lock 17/17, test_research 8/8, test_pause 5/5, test_v014_review_fixes 13/13 and test_server_host 2/2 all passed. test_qa_runtime has **2 errors at HEAD, 0 at f39812fc**; this is N4.
- **Python full-suite `discover` (791 tests).** 13 failures and 125 errors. The baseline is not clean: the same suite at f39812fc gives the same failures and errors, except the two test_qa_runtime errors. Per module, test_app, test_write_safety, test_manual_backup_cleanup, test_credits_tier and test_state_root show identical counts at both commits. This is an environment or test-order problem that predates this range, not something this range introduced. As a result, I could not exercise those write-safety tests in this environment. Their production code is untouched by the range.
- **Artifact vs HEAD.** All 57 packaged engine files equal the 047a138 blobs. The file set is identical, with no stray `.py`. All 34 `desktop/` files in `app.asar` equal HEAD; only the builder-rewritten `package.json` differs, as expected. No secret-like strings were found in `app.asar`. The exe's sha256 matches the brief, and its sha512 and size match `dist/latest.yml`.
- **Disclosure: an unguarded first test run.** My first Python run had a malformed `COMICS_META_TEST_PROTECTED_ROOTS` value. `test_0_state_isolation` therefore failed at line 55. By that point it had already pointed the state root and lock folder at scratch, but it had not yet installed its audit or socket guard.
  - I found no path from the -m1 tests to the live checkout.
  - The live `data/` writes in that 28-second window match the live service's own ongoing write rhythm.
  - Later runs used a valid guard.
  - My assessment is that no live state was touched. I cannot prove it afterwards.

---

## Rubric

### 1. Security

- Status: Concerns
- Findings:
  - **N1 [Major]** `desktop/installer_launch.py:163-168` (used at `:250` and `:333`).
    - **What changed.** Directory holds went from READ_ATTRIBUTES, which takes no part in sharing checks, to GENERIC_READ with FILE_SHARE_READ only. The helper applies this to every ancestor of the capsule and the payload: `C:\`, `C:\Users`, the profile folder, `AppData`, `AppData\Local`, `%LOCALAPPDATA%\ComicsMeta\…` and `%LOCALAPPDATA%\comic-metadata-updater\pending`. The holds last for the whole installer run.
    - **Measured with the shipped `Windows.hold` in scratch.** While a directory is held, these all fail with ERROR_SHARING_VIOLATION (32): moving a file in, renaming a file inside, `os.replace` (atomic save), and renaming the directory itself. Creating a file in it still works. After release, renames succeed.
    - **Effect.** During an update, every process on the machine fails to atomically save into the profile root or `AppData\Local` root. Examples are `~/.claude.json` and `.gitconfig`.
    - **The relaunched app is also exposed.** The installer's `--force-run` relaunch overlaps the holds on `%LOCALAPPDATA%\ComicsMeta`. A state write at engine startup can fail until the helper releases.
    - **The hold itself can fail.** Acquiring it fails if any process has one of those directories open with write or delete access. That fails safe: the update does not start.
    - **Fix (measured).** FILE_SHARE_READ|FILE_SHARE_WRITE still refuses rename and delete of the held directory, so the names stay protected, while child moves and renames succeed. Use that share mode for directory holds, or use metadata-only holds above the app-owned roots.
    - **Why Major, not Critical.** The effect is temporary, happens only when Sergei installs an update, writes nothing out of scope, and this app fails safe.
    - **Note for Futaba.** Installed update QA cannot see the effect on other processes, so a GO does not cover this.
  - Pass otherwise:
    - BrowserWindow keeps contextIsolation, nodeIntegration off and sandbox. IPC is unchanged.
    - The new QA session filter runs only when `qa` is true (`main.cjs:86`). The updater filter skips itself when it would replace the default-session filter (`main.cjs:98`).
    - Every spawn in the range uses argv with `shell:false`. The PowerShell `-EncodedCommand` reroute re-encodes and compares the exact upstream args before running `node npm-cli.js` (`build-lean.cjs` routeNpm, `npm-query-route.cjs`).
    - GH/CSC tokens are removed from the build child's environment, and the scan found no secrets.
    - The update feed is GitHub `Gemanoneko/Comics_Meta`, releaseType `release`, with no `publisherName`. The installer is unsigned, so update trust rests on GitHub TLS plus the sha512 in `latest.yml`. That predates this range and is accepted.

### 2. Correctness & Logic

- Status: Pass.
  - The `engine_host.py:105-135` handshake reads exactly `token+"\n"`, never reads past it, and matches what `engine.cjs:31` writes. Any later byte (`force\n`) or a broken pipe (109) stops the owned tree.
  - The `model_address`/`model_request` URLs in production are identical to the old hard-coded `127.0.0.1:11434`.
  - A probe confirmed the following:
    - In production, `policy()` returns `None` and the model address is `127.0.0.1:11434`.
    - In QA, the model goes to `modelPort`.
    - The QA audit hook refuses 11434, 8765, 443, `localhost` and external hosts, and allows only the engine, feed and model ports.

### 3. Crash / Stability Safety

- Status: Concerns. See N1's relaunch overlap. Otherwise:
  - `failure-exit.cjs` keeps exit 1 under the async-exit-hook `process.exit(0)`. The modelled positive-control test passes.
  - The lean driver requires exit 0, the final `leanBuild` receipt (`bootstrapExecuted:false`, version) and a matching installer size and sha256 (`build-installer.cjs:86-93`).

### 4. Performance

- Status: Pass. `qa_runtime.policy()` per call is an environment lookup in production. The owner pipe is peeked every 100 ms. Build-time hashing is bounded.

### 5. State & Data Safety

- Status: Pass. **QA→real:**
  - The Electron profile, cache and session live under the QA root.
  - Python independently re-validates the pinned policy: state equals `root/state`, the lock directory equals `root/locks`, and VERSION matches.
  - ComicVine and research go cache-only under QA (`app.py:357`, `research.py:55`).
  - Electron requests are confined to the owned engine and feed (`qa-policy.cjs` `requestAllowed`).

  **Real→QA:** nothing activates without `COMICS_META_QA=1` and a hash-pinned policy.

  The range does not touch per-comic recovery, backups, setup or key storage; test_comic_recovery and test_setup_state pass. Deletes in the range are fixed paths under the checkout (`build/staged`, `build/tmp`, `dist/*__uninstaller.exe`) or exact handle-held anchors.

### 6. Input Handling

- Status: Pass.
  - Both QA policy validators now require a complete, distinct, non-shared port set and well-formed versions.
  - The decoder is bounds-checked: PE ranges, section overlap, inflate caps and block count, with synthetic reject cases.
  - **N7 [Minor]** `installer_launch.py:178-183`. The exact `GetFinalPathNameByHandleW` match refuses 8.3, subst or mapped-drive spellings of a path. That fails closed, but it would block updates if `%LOCALAPPDATA%` were ever spelled short.

### 7. Maintainability

- Status: Concerns.
  - **N5 [Minor]** About 1,300 lines of held-build machinery are no longer reachable from `npm run pack`: `build-owned.py`, `held-paths.py`, `owned-job.py`, `nsis-safe/lease-rpc.py`, `build-entry.cjs` and `npm-query-route.cjs`. They are kept only because `publish-held.py` uses them; see N3. The audit's D2 defence-in-depth (requiring a positive success receipt) was not applied at `build-owned.py:260`. That is harmless while the path is dormant, but becomes a trap if it is revived. Remove the code or mark it retired.
  - **N6 [Minor]** `engine_host.py:105-135`. The new native owner-pipe protocol has no unit test, so it relies on installed QA.
  - **N8 [Minor]** Two small problems in the lean driver:
    - `build-installer.cjs:18-19`: `--inputs` with no value throws a TypeError.
    - `:46`: the driver stages every top-level `*.py` in the worktree, with no clean-tree or HEAD check. For 0.2.2 I confirmed by comparing artifact to HEAD that nothing extra shipped.
  - **N9 [Minor]** `scripts/check-shell.cjs:5`. `npm run check:shell` now refuses to run outside an isolated supervisor that is not in the repo. Before, it was a plain `node --test`. This makes the developer and handoff check loop harder.
  - Carried **F41 [Minor]**: compressed long lines. It has grown: `main.cjs:86/98` added more long lines.

### 8. Doc/Code Drift

- Status: Concerns.
  - **N10 [Minor]** `Docs/ComicsMetaOrganizer_Brief.md` has two problems:
    - It calls the lean inputs an "authenticated offline toolchain", but the lean driver authenticates nothing; see N2.
    - Line 51 says `npm run release` promotes the artifact, which the lean path cannot feed; see N3.
  - Carried **F15, F28**: unchanged.

### 9. Build & Release Hygiene

- Status: Concerns.
  - **N2 [Major]** `scripts/build-installer.cjs:18-22, :41, :67` and `build-lean.cjs:88-90`.
    - **What is unverified.** The release build takes its Python/7-Zip capsule, Electron, NSIS, rcedit and `node_modules` from the gitignored `scratch/cmo-packaging-recovery-20261015/`. Nothing checks them against `runtime-lock.json` or the prepare/assemble manifests. `verify-staged.cjs` only checks the staging against a manifest the driver generated itself.
    - **Consequences.** The installer cannot be built on Sergei's other machines. Routine scratch cleanup would delete the only release toolchain.
    - **Mitigation for 0.2.2.** The artifact-to-HEAD check above.
    - **Fix.** Verify inputs against committed manifests and move them to a declared non-scratch location.
  - **N3 [Major]** `scripts/release.mjs:6-9` with `scripts/packaging/publish-held.py`.
    - **What is broken.** The tool's release command still requires a held `build-receipt.json`, a QA promotion receipt and an outer Job. The lean build produces none of these. The single release path is therefore broken, and publishing 0.2.2 needs an out-of-band upload.
    - **What the feed needs.** Exactly `Comic-Metadata-Setup-0.2.2.exe`, `Comic-Metadata-Setup-0.2.2.exe.blockmap` and `latest.yml`, on a non-prerelease release in `Gemanoneko/Comics_Meta`.
    - **Watch out.** `dist/` also holds a stale `Comic-Metadata-Setup-0.2.1.exe` and its blockmap. Do not upload them.
  - **N4 [Major]** `tests/test_qa_runtime.py:18`.
    - **What broke.** `qa_runtime.py` was rewritten: full-policy validation, required `modelPort`, and module-level `_POLICY`/`_INSTALLED` caching. The test fixture was not updated, so 2 of its 4 tests error with "Private QA policy is invalid" at HEAD; they pass at f39812fc.
    - **Why it matters.** The Python QA exclusion hook, which keeps private QA off Ollama, live ports and providers, has no passing automated check in this release. My probe shows the code behaves correctly. A red check cannot act as a gate.
  - **N11 [Minor]** `dist/win-unpacked/resources/default_app.asar` from the offline Electron dist ships in the installer. It is inert while `app.asar` loads; this is hygiene only.
  - Pass:
    - VERSION, `package.json` and the lockfile are 0.2.2, with version-only changes.
    - `devDependencies.electron` is the exact `43.7.9`.
    - NSIS inputs are bounded at 254 characters before compiling, with a positive control.
    - The uninstaller stub is never executed; the pure decoder is checked byte-for-byte against upstream's reader.
    - CHANGELOG has no v0.2.2 entry yet. That is Sully's pipeline step, not a code finding.

---

## Prior-finding dispositions

| Item | Disposition |
|---|---|
| Actual23 audit **D1** (exit misattribution) | **Addressed.** `failure-exit.cjs` attributes the cause correctly and adopts upstream `cli-util.js:26-29` verbatim. It is used at `build-entry.cjs:64` and `build-lean.cjs:126`, with a modelled positive control (passes). |
| Actual23 audit **D2** (exit 0 accepted without a success receipt) | **Addressed on the release path.** `build-installer.cjs:86-93` requires exit 0, the final `leanBuild` receipt and matching installer bytes. **Not applied** in the now-dormant `build-owned.py:260`; tracked under N5. Audit recommendation 3, the mechanical MAX_PATH assertion, is implemented in `nsis-path-bound.cjs`. |
| F11, F12, F13, F14, F15, F19, F25, F26, F27, F28, F30, F31 [Minor] | **Still open.** This range does not touch their code regions; the `app.py` and `research.py` edits are QA gates at `:357` and `:55` only. |
| F41 [Minor] | **Still open, grown.** See section 7. |

## Out-of-range note (advisory, no severity)

QA installs use the production appId (`electron-builder.config.cjs`). electron-builder's NSIS `uninstallOldVersion` finds the registered install and uninstalls it, whatever `/D=` says. I am basing this on upstream behaviour; I did not run it. If that holds, a private QA install on a Windows profile that also has Sergei's real install would uninstall the real program files (app data is kept) and take over its shortcuts and registry entry. Keep installed QA off any profile with a real install.

---

## Verdict

- Total Critical: 0
- Total Major: 4 new (N1, N2, N3, N4), 0 carried
- Total Minor: 7 new (N5–N11), 13 carried (F11–F15, F19, F25–F28, F30, F31, F41)
- Safety-floor violations: 0

**Verdict:** RELEASE CLEAR

This certifies the source range above and confirms that the examined 0.2.2 artifact's engine and desktop bytes equal HEAD 047a138. It does not certify installed behaviour, the prior→next update, or publication; those belong to Futaba and Sully. Major and Minor findings are logged for Ender's next cycle and do not gate this release.
