# Code Review — Comics Meta Organizer v0.6.10

## Header

```text
Reviewer: Senua (Code Reviewer)
Date: 2026-11-22 (first pass); delta pass 2026-11-23
Tool: Comics Meta Organizer (Comic Metadata)
Release: v0.6.10
Commit range: 67c7b53008609f7f88879abb0ab339fa4577958e (main, tag v0.6.9, "Release prep v0.6.9")
              ..7eacdff5962b216a765d837e968cb97208ec3d70 (main, "fix: let a QA policy ask for the tray, for a run on
              a private desktop")
Reviewed head: 7eacdff5962b216a765d837e968cb97208ec3d70 (branch main, pushed)
Reviewed in two passes:
              1. 67c7b53..86425b131e7b8b341b52ccc994fb433940beef69: 6 commits. The Summary and Rubric below.
              2. 86425b1..7eacdff: 1 commit, made after Futaba's NO-GO on the 86425b1 build; § Delta review.
Commits: 7
              224614c  Docs: clear and verify the exact 0.6.9 build            (Docs only)
              262fb74  Docs: record 0.6.9 release and QA evidence              (Docs only, one 173 KB ZIP)
              68ad095  Keep development and QA writes under the approved projects root
              19c87e7  fix: prevent Unicode filenames from stopping background batches
              3fe018c  fix: run the engine in UTF-8 mode; report a failed ledger backfill on stderr
              86425b1  Release prep v0.6.10: version bump, lockfile sync
              7eacdff  fix: let a QA policy ask for the tray, for a run on a private desktop   (delta)
Files changed: 28 files, +669 / -28 in all. First pass: 23 files, +160 / -22. Delta: 8 files, +511 / -8
               (desktop/main.cjs +4 / -2, desktop/qa-policy.cjs +3, scripts/qa/private-desktop.py new, 443 lines,
               three test files, CHANGELOG, the Brief). The lines below describe the first pass.
               Product: batch.py, worker.py, provenance.py, desktop/engine.cjs, desktop/main.cjs (5 files, +20 / -8).
               Build and dev tooling: .npmrc (new), scripts/build-installer.cjs, scripts/packaging/prepare-runtime.mjs,
               scripts/packaging/install-update-qa/host-run.mjs.
               Tests: tests/test_write_safety.py, tests/test_fast_selection.py, desktop/tests/engine-spawn.test.cjs,
               scripts/packaging/install-update-qa/common.test.mjs and qa-receipt.test.mjs.
               Version: VERSION, package.json, package-lock.json. Docs: CHANGELOG, the Brief, four v0.6.9 records.
How the range was established:
               1. The v0.6.9 report's reviewed head is 105a25a. Its closing section extends the clearance to the
                  built commit 67c7b53 after `git diff 105a25a 67c7b53`. Re-run today: the same 5 paths (that
                  review, VERSION, package.json, package-lock.json, CHANGELOG).
               2. Tag v0.6.9 resolves to 67c7b53, and the v0.6.9 release receipt names 67c7b53 as the built source.
               3. 67c7b53 is an ancestor of 86425b1 with no merge commit between them.
               So 67c7b53 is the last commit the previous review certified, and the range is everything after it.
               The delta: 86425b1 is the parent of 7eacdff, the one commit after my first verdict (no merge).
Stand-down dimensions: none
```

---

## Summary

The first pass (to 86425b1) is below. The second pass (to 7eacdff), which answers Futaba's NO-GO on the 86425b1 build, is in § Delta review. The Verdict covers both passes.

0.6.10 fixes one production failure. On a cp1251 Windows host a worker printed a file name containing "²" to its discarded output, Python refused to encode it (`'charmap' codec can't encode character '\xb2'`), and the folder's batch stopped (0.6.7 to 0.6.9). The range fixes it twice over: the worker no longer prints those lines (19c87e7, and the ledger-backfill line in 3fe018c), and the shell starts the engine with `PYTHONUTF8=1` (3fe018c). It also carries 68ad095, which moves some development and QA writes under the projects root.

**Headline.** The fix is sound and I found nothing that blocks the release. Both halves work, the regression test is real, and UTF-8 mode changes nothing the engine relies on besides its streams. Two Major findings sit beside the fix, not in it:

- **U1:** the `.npmrc` added by 68ad095 is refused by the studio's own QA entry check.
- **U2:** the hand-run merge tool, which this release leaves out, still fails the same way whenever its output is captured or redirected.

**Answers to the brief's questions, short:**

- **Does `PYTHONUTF8=1` change anything besides the streams?** Not for this engine.
  - *Default text encoding* (`open()`, `read_text`, `write_text`, text pipes) changes from cp1251 to UTF-8. My own AST pass over the 61 engine modules found no call that depends on it: no text-mode open without `encoding=`, no `text=True` subprocess, no `os.fdopen`, `TextIOWrapper`, `tempfile`, `logging.FileHandler`, `configparser` or `locale` use. The one aliased opener (`open_library.py:13-14`) passes `encoding='utf-8'`. Ender's claim holds: the only hit is `desktop/installer_launch.py:304`, which reads the ASCII `python314._pth` and runs with `-I` and every `PYTHON*` variable stripped (`desktop/installer-launch.cjs:10-12`).
  - *Measured in each process* (probe P3): `locale.getencoding()` stays cp1251; the file-system encoding stays utf-8/surrogatepass; stdin and stdout become utf-8/surrogateescape and stderr utf-8/backslashreplace.
  - *Archive member names:* `zipfile` uses its own rules. All three 7-Zip commands pass `-sccUTF-8` and are read as bytes and decoded explicitly (`archive_conversion.py:26`, `:36`, `:119`, `:120`).
  - *State and catalog files:* every text read and write names `utf-8`; the catalog is SQLite.
  - *Child processes:* 7-Zip, the Playwright driver and Edge inherit a variable they ignore. The engine uses no Playwright call that writes a text file.
  - *`engine.log`:* no product code reads it. New lines are UTF-8; lines written by older versions stay cp1251, so the file is mixed from the upgrade on. Cosmetic.
- **Can a launch in the chain drop or override the variable?** Not as the code stands. See P3: all four processes (broker, `app.py`, both workers) ran in UTF-8 mode, through the real `desktop/engine.cjs`, `engine_host.py` and `supervisor.py`.
  - No launch has `-I` or `-E` (`engine.cjs:60`, `engine_host.py:184`, `supervisor.py:38`). The broker passes no environment block, so `app.py` inherits its own; the supervisor copies `os.environ`. Nothing in the engine edits the environment.
  - The runtime's `._pth` isolation does not cancel it: the processes reported `isolated=1`, `ignore_environment=1` and `utf8_mode=1` together.
  - An inherited `PYTHONUTF8=0`, or the same name in another letter case, loses to the app's value.
  - **Inherited variables that do undo it** (u1): `PYTHONIOENCODING`, `PYTHONLEGACYWINDOWSSTDIO`, `PYTHONLEGACYWINDOWSFSENCODING`. None is set on this machine (user and machine environment in the registry, and this session). Rated Minor: nothing reachable prints a file name to stdout any more, so undoing the stream encoding breaks nothing today.
- **Any remaining stdout print with non-ASCII data on the worker or service path?** None. The engine's stdout prints are: the startup banner (`app.py:1736`, `:1783`, an ASCII address), `batch.py:192`, `:272`, `:277` (now off in the worker), and command-line entry points only (`batch.py:101-102`, `worker.py:224`, `open_library.py:63`, `pilot_credits.py:187-188`, `relabel_cover_tasks.py:140-141`). Everything else already goes to stderr.
- **Is the regression test real?** Yes, for both print changes (P2). With the worker's prints switched back on it fails with the production message on the ticket; with the backfill line sent to stdout again it errors with the same `charmap` exception. The environment-variable half has no behaviour test, only an assertion on the first launch's settings (u2).
- **68ad095:** the `TMPDIR` additions and the two tests' move to `<repo>/scratch/` are correct and leave nothing behind. The new `.npmrc` is the problem (U1, u4). The commit also turns the tray off for QA profiles (u3).
- **Lockfile in 86425b1:** two changed lines, both version fields (`package-lock.json:3`, `:9`). VERSION, `package.json` and the lockfile move together in that commit.

**Tests (targeted, per § Lean verification). The full suite was not run.**

| What | How | Result |
|---|---|---|
| Python: `test_0_state_isolation`, `test_write_safety`, `test_fast_selection`, `test_batch_060`, `test_supervisor`, `test_worker`, `test_zz_state_isolation` | System Python 3.14.10, `-X utf8 -B`, scratch in the tool's `scratch/` | 37 run, 36 passed, 1 failed for an environment reason (below) |
| Shell: `engine-spawn`, `quit-always`, `window-restore`, `previous-session` | System Node 26.13.1, `node --test` | 34 passed |
| Packaging: `install-update-qa/common.test.mjs`, `qa-receipt.test.mjs` (changed by 68ad095) | same | 9 passed; `scratch/` listing identical before and after |

- **The one failure is the interpreter, not the code.** `test_supervisor.WorkerLogTests.test_a_workers_restore_line_reaches_the_app_log_and_its_stdout_does_not` starts a child with `-I`. This interpreter keeps Pillow in the per-user site-packages, which `-I` hides, so the child ends with `ModuleNotFoundError: No module named 'PIL'`. The bundled runtime has Pillow in its own tree. I could not use it: `build/` was off limits while the release build ran. **This test has to pass in the build's entry check**, like the rest of the full suite.

**Probes (in the tool's `scratch/`, removed afterwards).**

- **P1, AST pass.** 66 files (61 engine modules, `desktop/installer_launch.py`, 4 tools), 11,572 calls. It lists every text-mode open, `read_text`/`write_text`, subprocess, stdlib text helper and `print` without an explicit destination. Result as in the answers above.
- **P2, mutation of the regression test.** No source edit; the old behaviour was patched in at run time. Control: pass. Worker prints on again: `'needs_attention' != 'complete' : 'charmap' codec can't encode character '\xc6'`. Backfill line to stdout again: `UnicodeEncodeError: 'charmap' codec can't encode character '\xc6' in position 31`.
- **P3, the launch chain.** The real `desktop/engine.cjs` started a scratch copy of the real `engine_host.py`, which started a stand-in `app.py`, which started stand-in workers through the real `supervisor.py`. Each process recorded its own settings. Five runs:

  | Run | Broker, app, worker, browser worker | Print of `x².cbz` to stdout |
  |---|---|---|
  | As 0.6.10 launches | utf8_mode 1, stdout utf-8 | ok (log bytes `c2 b2`) |
  | `PYTHONUTF8` removed (0.6.9) | utf8_mode 0, stdout cp1251 | `'charmap' codec can't encode character '\xb2'` |
  | Inherited `PYTHONIOENCODING=cp866` | utf8_mode 1, stdout cp866, strict | the same `charmap` error |
  | Inherited `PythonUtf8=0` (other case) | utf8_mode 1, stdout utf-8 | ok |
  | Inherited `PYTHONUTF8=0` | utf8_mode 1, stdout utf-8 | ok |

  - **Limit of P3:** the interpreter was CPython 3.14.10 copied beside a `python314._pth` of the shipped shape, not the shipped 3.14.8 embeddable build (`build/` was off limits). The `._pth` isolation was in effect (`isolated=1`). It agrees with Ender's measurement on the shipped runtime.
- **P4, one process, more inherited variables.** With `PYTHONUTF8=1` set: `PYTHONLEGACYWINDOWSFSENCODING=1` gives utf8_mode 0, cp1251 streams and an `mbcs` file-system encoding; `PYTHONLEGACYWINDOWSSTDIO=1` gives cp866 streams; `PYTHONIOENCODING=utf-8` keeps UTF-8 but makes stdout strict. `-X utf8` on the command line does not beat an inherited `PYTHONIOENCODING` either, so the Brief was right to reject it as the fix.
- **P5, the merge tool's console line** (`tools/nested_comicinfo_merge.py:990`) on a stdout that is not a console, with the isolated runtime as the Brief's apply command runs it: `'charmap' codec can't encode character '\xb2'`. With `PYTHONUTF8=1`: printed.
- **P6, the committed evidence ZIP** (262fb74, 54 members, read in memory): no token, key, password, private key, e-mail address or user-profile path. The long hex strings are SHA-256 values; `feedToken` is generated at run time.
- **P7, `.npmrc`.** `npm config get cache` from the repo root answers `<repo>\scratch\npm-cache`; from `desktop/` it answers `<repo>\desktop\scratch\npm-cache`, and creates that folder (u4).

---

## Delta review: 86425b1..7eacdff

One commit, `7eacdff`, 8 files, +511 / -8. Futaba's smoke of the 86425b1 build was NO-GO: since 68ad095 a QA profile has no tray (my u3), so the release's required native tray Quit could not be run. A tray made in a QA run on Sergei's own desktop registers with Explorer under his logon, which his standing rule forbids. The commit's answer:

1. **`desktop/main.cjs:169`:** the tray is created outside QA, or when the QA policy has `"tray": true`.
2. **`desktop/qa-policy.cjs:17`:** `tray` is an optional boolean; any other value makes the policy invalid.
3. **`scripts/qa/private-desktop.py`** (new, 443 lines, QA tooling): runs a program on a separate Win32 desktop that has no shell tray, after checking that from inside it, and refuses (exit 250) otherwise.
4. Tests (`qa-tray.test.cjs` new, `qa-policy.test.cjs`, the shell fixture), CHANGELOG and a Brief row.

**Headline.** Nothing in the delta blocks the release. The installed app's behaviour is untouched, the new key is strictly validated and reachable only through an authenticated QA policy, the helper is not packaged, and its launch code fails safe. Four Minor findings, all on the QA route (d1 to d4). The one thing that matters most is not a code defect: **nothing in the repo shows that a tray made on such a desktop stays out of Explorer's records** (d2). Until that is measured, the first run with the app is the experiment.

**Answers to the brief's questions:**

- **Can anything outside a deliberate QA policy turn this on, or change a real user's app?** No.
  - *The non-QA path equals 0.6.9.* `git diff 67c7b53 7eacdff -- desktop/main.cjs` changes one statement: the tray block gains the prefix `if(!qa||qaPolicy.tray===true)`. Outside QA `!qa` is true, the policy is never read, and the block that runs is character for character 0.6.9's. `qa-tray.test.cjs:41` pins it (probe D1).
  - *How a QA policy is loaded* (`qa-policy.cjs:5-12`, unchanged). Only when the process environment has `COMICS_META_QA=1`; without it no file is opened (`:5`). Then: the root must be an existing folder inside `%TEMP%` named `illuminati-cmo-qa-*` with no link on its path; the policy file must lie inside it and be at most 32 KB; its SHA-256 must equal `COMICS_META_QA_POLICY_SHA256` from the environment; it must name that root, this app version and an expiry at most 24 hours ahead, with loopback-only ports and feed.
  - *So a stray or hostile policy file in a normal install does nothing.* Whoever can set the app's environment and write into `%TEMP%` already runs as the user, and all `"tray": true` gives them is the tray the app normally has.
  - *Inside a QA policy:* `"tray": true` gives the QA behaviour of 0.6.0 to 0.6.9 (a tray; the close button hides to it). Without it, 86425b1's (no tray; the close button quits).
- **`qa-policy.cjs` validation.** Sound.
  - `:17` accepts a missing key or a real boolean and refuses everything else (`1`, `0`, `'true'`, `null`, `{}` are tested). `main.cjs:169` compares with `=== true`, and the policy object is frozen (`:19`).
  - Prototype tricks give nothing: `JSON.parse` makes `__proto__` an ordinary own key, so a policy cannot inherit a `tray`; and the author of an accepted policy can simply write the key.
  - The engine's own policy check (`qa_runtime.py:49-116`) ignores unknown keys, as it does `closureWaitSeconds`, so it accepts the same file.
- **`private-desktop.py`.**
  - *Does it ship?* No. The installer stages only root-level `*.py`, `static/` and `desktop/installer_launch.py` (`scripts/build-installer.cjs:48-52`) and packs `desktop/**` and `package.json` (`electron-builder.config.cjs:5`). If it did ship it would widen nothing: it needs no privilege and starts a program the caller names, as the caller.
  - *Focus and input.* It uses 32 Win32 functions. None switches a desktop, sets the foreground, shows a window, sends input or posts a message (probe D2). Its desktop handle has no switch right (`:64`, access 0x20043). The only window it makes is one never-shown `Static` window inside the private desktop (`:182`); the control pass on the caller's desktop makes none. It reads two HKCU keys and writes no registry key.
  - *The refusal check.* Sound at the moment it runs: a control on the caller's own desktop must find the tray there (`:309-310`); the probe must find a window of its own two ways before "nothing else found" counts (`:314-315`); a probe that does not report is a refusal (`:302-304`); and `run` has no switch to skip it (`:370-375`). Its limits are d2.
  - *Child left running.* While the program runs it sits in a kill-on-close Job (`:376-383`). The Job handle is not inheritable and the child is created suspended and assigned before it runs, so ending the helper ends the whole tree. Every error before the resume terminates the child or lets the Job do it. After the program exits by itself the Job is released on purpose (`:396-399`), so a leftover child stays for the caller's own closure check.
  - *Handle and desktop leaks.* None that outlives the helper. The program's process and thread handles, the three duplicated standard handles (`:233-237`) and, on the error path, the Job handle are not closed explicitly; the helper returns right after. The desktop handle is closed on every path that returns (`:326-328`), and the desktop object goes when its last process does.
  - *Exit code and stdio.* The child gets duplicates of the helper's own standard handles, so nothing is pumped or buffered (`:231-240`). The exit code is passed on unchanged, NTSTATUS values included (`:405`). What the code alone cannot tell is d3.
  - *Quoting and paths.* The program must be an absolute, existing file (`:367`) and is passed as the application name, so nothing is searched or re-parsed (`:242`). Arguments go through `subprocess.list2cmdline`; no shell is involved. Spaces, brackets, trailing backslashes, quotes, an empty argument, non-ASCII names, `&`, `%`, `^` and a tab all came back unchanged through Windows' own parser (D2).
- **Are the new tests real?** Yes. Each of the four fails when its part of the change is absent (D1).

**Findings in the delta:**

- **d1 [Minor]** `desktop/main.cjs:166-169`, `scripts/qa/private-desktop.py:40`: **nothing ties `"tray": true` to a private desktop.**
  - The rule is a code comment and a docstring line. A QA policy with the key, started directly, makes the tray on the user's own desktop: what 68ad095 set out to stop, and what every QA run did until 0.6.9.
  - **Fix:** let the helper mark the child (for example an environment variable naming the desktop) and have the shell honour `"tray": true` only with that mark; add the case to `qa-tray.test.cjs`.
- **d2 [Minor]** `scripts/qa/private-desktop.py:272-322`, `:333-336`, `:400-405`: **the no-tray guarantee is checked once and then reported, not enforced.**
  - (a) The check runs before the program starts. Nothing watches the desktop while it runs, although the helper's handle can enumerate it. I found no path in the app that starts a shell there, so reachability is very low.
  - (b) After the run, `trayRecordsUnchanged` goes into the record, but the exit code is the program's (`:405`). A caller that reads only the exit code passes a run that registered a tray.
  - (c) That comparison has no positive control: nothing has shown it changes when a tray does register. It compares key names only (`:334-335`). Both keys exist on this machine (157 and 1 subkeys), but whether Explorer writes a new one at once is not measured.
  - (d) The Brief and the docstring (`:42-43`) say the desktop was proven "with harmless programs". Neither says one of them tried to add a tray icon. If none did, "records unchanged" says nothing about a tray, and the first run with the app is the first test, in Sergei's own session.
  - **Fix:** a distinct exit code when the records changed; a look at the desktop during the wait; and one proof of the mechanism where a record does not matter (for example Windows Sandbox) with a program that really adds a tray icon, the same program on that machine's own desktop being the control.
- **d3 [Minor]** `scripts/qa/private-desktop.py:65`, `:364-367`, `:394`: **the exit code alone cannot be trusted.**
  - The helper's own codes (250, 251, 252, and 1 for a usage error or any uncaught error) share the range with the program's.
  - An uncaught `OSError` from the record write (`:267`), the registry read (`:216`) or the wait (`:255`) ends the helper with 1 and leaves the record at an earlier phase.
  - `ResumeThread`'s result is not checked (`:394`). If it failed, the child would stay suspended and the helper would wait for ever.
  - All of these fail safe: the program never runs unsupervised.
  - **Fix:** have callers read `phase` and `exitCode` from the record, check the resume, and guard the bookkeeping after the run.
- **d4 [Minor]** `scripts/qa/private-desktop.py:34`: **the documented Node launch has no `windowsHide: true`.**
  - `python.exe` is a console program. Started from a parent that has no console, it opens a console window on the user's desktop, and that window takes focus. Every other launch in this repo passes the flag.
  - Also: the helper has no automated test, and the 2026-11-22 proof left no record in the repo.

**Earlier findings after the delta:**

- **u3: resolved.** The QA tray is now opt-in, tested (`qa-tray.test.cjs`), in the CHANGELOG (`:12-13`) and in the Brief's Decision Log.
- **U1: still open, and it did not stop this build.** Futaba's report on the 86425b1 build (uncommitted, not mine) says the builder's own check log stood in for the entry-check receipt, "as in 0.6.9". So this release path does not go through `run_entry_checks.mjs`, and the refusal I described does not arise on it. I keep the grade: while the file is tracked, the tool cannot pass the studio's standard entry check.
- The same report gives the builder's full run at 86425b1: Python 1396 run, OK, 117 skipped; shell 125 run, 0 failed. I did not verify it, and I did not check whether the supervisor test I could not run is among the skipped ones. **7eacdff needs its own run** from the rebuild.
- U2, u1, u2, u4, u5, u6: unchanged. The delta touches none of their files.

**Tests and probes for the delta (scratch removed afterwards).**

- **Shell tests at 7eacdff:** `qa-tray`, `qa-policy` and the three other users of the changed fixture (`previous-session`, `quit-always`, `session-end`), on system Node 26.13.1: 34 passed.
- **D1, the new tests against the code without the change** (copies in scratch; no source edit):

  | New test | Run against | Result |
  |---|---|---|
  | `"tray": true` gets the tray (`qa-tray.test.cjs:16`) | `main.cjs` of 86425b1 | fails, `0 !== 1` |
  | no tray without it (`:32`) | `main.cjs` of 67c7b53 (0.6.9) | fails |
  | the installed app always has its tray (`:41`) | a copy with the installed-app tray removed | fails |
  | optional boolean tray (`qa-policy.test.cjs:12`) | `qa-policy.cjs` of 86425b1 | fails |

- **D2, static checks of the helper.** It parses and is ASCII only. Importing it only loads two system libraries and declares signatures. Structure sizes match Win64 (`STARTUPINFO` 104, `PROCESS_INFORMATION` 24, the Job limits 144). The quoting round trip and the function list are as stated above.
- **Not run, as instructed:** `check`, `run`, `probe` and `windows`. No desktop, window or tray was created, and no app was started. So the helper's behaviour on this machine is read, not measured.

---

## Rubric

### 1. Security

- Status: Pass. No shell-out changed. No Electron preference or IPC change: `desktop/main.cjs` changes only whether a tray is created. The one new environment variable carries no secret. The committed evidence ZIP and the added doc lines hold no credential (P6).

### 2. Correctness & Logic

- Status: Pass. `print_progress` is keyword-only and defaults to on, so `batch.py`'s own command line prints as before (`batch.py:166`, `:300`); the worker is the only other caller (`worker.py:85`). Removing the prints removes no side effect: progress and results are saved by separate calls.

### 3. Crash / Stability Safety

- Status: Concerns.
- **U2 [Major, outside the changed lines]** `tools/nested_comicinfo_merge.py:988`, `:990` (also `:968`): **the failure this release fixes is still in the merge tool.**
  - The tool prints each comic's file name to stdout. The Brief's apply command runs it on the installed runtime with no `PYTHONUTF8`. In a console window that works. When the output is captured or redirected (an agent's shell, `> log.txt`, a pipe), stdout is cp1251 and a name with a character outside it raises (P5).
  - It raises *after* the archive is written and its line is fsync'd to `results.jsonl` (`:983-986`). So the run stops with a traceback, `summary.json` is not written, and `label_kept_backup` (`:991-992`) is skipped for that comic: a backup the run decided to keep stays out of Kept backups. `--resume` treats the comic as done, carries on, and stops again at the next such name.
  - Nothing is lost: the write is verified and recorded before the print.
  - The Brief says tools run by hand are not covered. I rate it Major anyway because the library is known to hold such names (that is how the worker bug was found) and the real-library merge run is the tool's whole purpose.
  - **Fix:** at the top of `main()`, `sys.stdout.reconfigure(errors='backslashreplace')` (or `encoding='utf-8'`), and move the print after `label_kept_backup`. **Until then:** run the tool in a real console window, or with `PYTHONUTF8=1` set.
- **u5 [Minor]** `provenance.py:208`: the new log line is not guarded. An `OSError` from a full or unwritable `engine.log` now leaves `ensure_backfilled`, whose docstring (`:193`) says a failure never stops discovery. The broker and the supervisor guard the same kind of line (`engine_host.py:229-232`, `supervisor.py:49-52`). Reachability is very low, and the worker's loop retries the folder.

### 4. Performance

- Status: Pass. No hot path changed.

### 5. State & Data Safety

- Status: Pass. No write, rename or delete path changed. No new deletion: the two changed tests remove only the temporary folder each one made (`common.test.mjs:18`, `qa-receipt.test.mjs:12`, `:21`). UTF-8 mode reaches no state file (P1).

### 6. Input Handling

- Status: Concerns.
- **u1 [Minor]** `desktop/engine.cjs:60`: **the engine inherits every `PYTHON*` variable the shell was started with, and three of them undo the fix's stream encoding** (P3, P4).
  - `PYTHONIOENCODING` (any legacy code page), `PYTHONLEGACYWINDOWSSTDIO` and `PYTHONLEGACYWINDOWSFSENCODING`. The last one switches UTF-8 mode off altogether.
  - Exposure: a user-level or machine-level variable. None is set on this machine. With one set, the engine is back to 0.6.9's streams, but since 19c87e7 and 3fe018c no reachable line prints a file name to stdout, so nothing fails. It would matter for the next print someone adds.
  - **Fix:** drop inherited `PYTHON*` variables before adding the two the engine needs, as the update helper's launch already does (`desktop/installer-launch.cjs:10`), and assert it in the spawn test.

### 7. Maintainability (no Critical findings on its own)

- Status: Concerns.
- **u2 [Minor]** **The mechanism the fix rests on is proven by a one-off measurement, not by a test.**
  - `engine_host.py:184-187` (the broker starting `app.py`: no `-I`/`-E`, no environment block) is not pinned by any test. `tests/test_supervisor.py:103` does pin the worker's arguments.
  - `desktop/tests/engine-spawn.test.cjs:29-30` checks the first launch only. It looks for `-I` or `-E` as whole arguments, so a combined flag such as `-IB` passes. If the test runner itself has `PYTHONUTF8=1`, the first assertion passes without the fix.
  - The warning that no launch may gain `-I` or `-E` is written at `engine.cjs:55-58` and in the Brief, but not at the two Python launch sites (`engine_host.py:184`, `supervisor.py:38`), where the next editor would need it.
  - **Fix:** in `tests/test_engine_host.py`, have the stand-in `app.py` report `sys.flags.utf8_mode` with the variable set; put a one-line comment at both launch sites.
- **u3 [Minor]** `desktop/main.cjs:166-167` (68ad095): **an unrelated behaviour change inside a write-locations commit.** Under a QA policy no tray is created. A window close then quits (`:156`), and QA-profile runs no longer exercise the tray menu or close-to-tray. No test covers the branch (the fixture's `loadPolicy` returns null). Production is unchanged. The commit message does not mention it. **Resolved in the delta** (7eacdff); see § Delta review.

### 8. Doc/Code Drift (no Critical findings on its own)

- Status: Concerns.
- **u6 [Minor]**
  - (a) `supervisor.py:16` still explains that stdout stays out of the log because "batch.apply prints a line per comic". The worker no longer prints those lines.
  - (b) "take any file name" (`engine.cjs:56`, `CHANGELOG.md:8`, the Brief's Decision Log row): true for stderr. Stdout in UTF-8 mode still refuses a name with an unpaired surrogate, which Windows allows (P3: `'utf-8' codec can't encode character '\ud800'`). Moot while no stdout line names a file.
  - (c) The Brief's "Not covered" list omits the old `run.cmd` → `start-app.ps1` → `server_host.py` launch, which starts `app.py` and the workers without the variable.

### 9. Build & Release Hygiene

- Status: Concerns.
- **U1 [Major]** `.npmrc:1` (68ad095): **the studio's QA entry check refuses a project that tracks an `.npmrc`.**
  - `.claude/skills/qa-handoff/scripts/entry-main.mjs:65` (`verifyProjectConfiguration`) throws `Unreviewed project/workspace npm configuration` when the source manifest lists a file named `.npmrc`. The manifest must equal `git ls-files` (`entry-identity.mjs:53-54`), so a tracked file cannot be left out. `:73` refuses it again in the run folder. The rule is deliberate: `entry-check.test.mjs:28` tests it.
  - The refusal comes at line 190, before any test runs. 0.6.10 is the first build whose tree has the file; 0.6.9 was built from a tree without it.
  - This is a release-path conflict, not a product risk: the file is not packaged (`electron-builder.config.cjs:5`), and the build's own npm calls set the cache through the environment, which outranks it.
  - I did not run the entry check (it runs the full suite). **If the 0.6.10 build goes through `run_entry_checks.mjs`, expect `Entry-check REFUSED` there.**
  - **Update in the delta pass:** the 86425b1 build did not go through that script, so the refusal did not arise; see § Delta review.
  - **Fix, one of:** remove the file and set `npm_config_cache` in the development commands that need it; or teach the entry check to accept a reviewed `.npmrc` (for example one `cache=` line only). The second changes a studio gate, so it is Sergei's and Ender's call.
- **u4 [Minor]** `.npmrc:1`: **the cache path is relative to the folder npm is run from, not to the file** (P7). Any npm command run inside `desktop/` creates `desktop/scratch/npm-cache`, inside the tree the installer packages whole (`electron-builder.config.cjs:5`, `desktop/**/*`). Git ignores it, so nothing would show in `git status`. A held build works from tracked files only and QA compares the packed `desktop/` files with the commit, so a stray folder would be caught. My probe created that folder; I removed it.
- **Verified clean:**
  - Version: `VERSION`, `package.json` and both lockfile fields read 0.6.10, in one commit. `CHANGELOG.md` has the v0.6.10 entry.
  - First two-digit patch number in this tool's history. Nothing compares versions as text: `build-entry.cjs:19` splits to numbers, `cleanup-releases.js:13` sorts by publication date, and every pattern uses `\d+` or `[0-9]+` (`updates.cjs:23`, `app.py:1642`, `cleanup-releases.js:12`). The studio's precondition script compares numerically too.
  - `git diff --check 67c7b53..86425b1` is clean. No attribution trailer in the six commit messages.
  - `TMPDIR` now follows `TEMP`/`TMP` at all three places that redirect them (`build-installer.cjs:88`, `prepare-runtime.mjs:112`, `host-run.mjs:26`). Python's `tempfile` reads `TMPDIR` first, so this closes a real gap.
- **Hygiene of this review.** Working tree clean and at 86425b1 at the start; this report is my only change, left uncommitted. `Docs/ComicsMetaOrganizer_TrayQA_v0.6.10_2026-11-22.md` appeared during the review and is not mine. Probe scratch (52 files, 7.3 MB, mostly the copied interpreter) was removed with the studio's per-path planner; the stray `desktop/scratch` from P7 was removed too. Nothing was written under `build/`, `dist/`, `node_modules/`, the release worktree or any app-data folder, and no app was started.
- **Delta pass.** Tree clean at 7eacdff apart from this report and Futaba's. The delta leaves VERSION, `package.json`, the lockfile and `.npmrc` untouched; `git diff --check 67c7b53..7eacdff` is clean; the commit message carries no attribution trailer. Probe scratch (12 files, 120 KB: copies of earlier shell sources and one script) was removed the same way. Same limits kept; the helper was read and imported, never run.

---

## Patterns

The same shape as the last three reviews: a fix that is correct where it was measured, with the proof not carried into a test. Here the stream fix depends on one variable surviving three launches, and only the first launch has an assertion (u2). The second recurring shape is a fix scoped to the app while the hand-run merge tool keeps the old behaviour (U2 now; w9 and the `verify_written` note in v0.6.9).

The delta breaks the first pattern for the product code: every part of that change has a test that fails without it. The unmeasured part has moved into the QA route instead (d2): an absence, "no tray record", with no case yet where the check was seen to fail.

---

## Verdict

Both passes, range 67c7b53..7eacdff.

- Total Critical: 0
- Total Major: 2 new and open (U1, U2), plus 4 inherited and untouched (M1, M2, I1, I2). The delta adds none.
- Total Minor: 9 new and open.
  - First pass: u1, u2, u4, u5, u6. Resolved in the delta: u3.
  - Delta: d1, d2, d3, d4.
  - Inherited: the list in the v0.6.9 report (w1, w2, w4 to w9 and earlier), none of which this range touches.
- Safety floor: intact.
  - No Electron preference or IPC change. The delta changes only whether a tray is created, and outside QA that is as in 0.6.9.
  - No new write location outside the tool's own folders; 68ad095 moves test and build temp files into `<repo>/scratch` and the build's own temp folder. The new helper writes its record where the caller names it and reads the registry only.
  - No new deletion path in product code.
  - No credential in the range, the evidence ZIP included.
  - No repository-integrity change.

**Verdict:** RELEASE CLEAR

This clears construction for source commit 7eacdff5962b216a765d837e968cb97208ec3d70 (range 67c7b53008609f7f88879abb0ab339fa4577958e..7eacdff5962b216a765d837e968cb97208ec3d70). It does not prove installer behaviour, the entry check or publication.

- **Not covered by this review, and needed before release:**
  - The full suite on the bundled runtime at 7eacdff, including the one supervisor test this interpreter could not run.
  - The packaged build with a real "²" file name. P3 used a stand-in interpreter of the same shape, not the shipped one.
  - The tray on a private desktop. Three things are unmeasured: that Electron keeps a working tray with no shell to reach, that the smoke's tray Quit still fires there, and that such a tray leaves Explorer's records alone (d2). The first two are Futaba's to find out. The third decides whether Sergei's rule is kept, so it is better measured before the app's first run than by it.
- **For Futaba's run:** start the app only through the helper when the policy has `"tray": true` (d1), pass `windowsHide: true` when starting the helper from Node (d4), and judge the run by the record's `phase`, `exitCode` and `trayRecordsUnchanged`, not by the exit code alone (d2, d3).
- **Before the real-library merge run** (not a release gate): run `tools/nested_comicinfo_merge.py` in a console window or with `PYTHONUTF8=1`, or fix U2 first.
- **First items for Ender's next cycle:** U1 (decide the `.npmrc` route), U2, then d1 and d2 (the QA tray's interlock and proof), then u1 and u2 together (they touch the same launch line and its test).
