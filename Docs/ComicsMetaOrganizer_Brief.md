# Comics Meta Organizer — Brief

**What it does.** A local background service for Sergei's YACReader comic library. It scans the library folder by folder, identifies each comic from external sources (ComicVine, Metron, GCD, Google Books, publisher/web research, an optional Open Library dump, Google Lens cover search with an optional SerpApi fallback), and writes verified `ComicInfo.xml` into CBZ archives. A backup is removed only after the written file reads back correctly and passes a SHA-256 check. **What Sergei does with it:** keeps it running, watches the dashboard, presses **Pause & release GPU** when he needs the computer, completes Google Lens or Yandex human verification when the dashboard asks, then runs YACReader's **Rescan library for XML info**. **What it does not do:** edit YACReader's database; solve CAPTCHAs or spoof browser fingerprints; write metadata from a cover or search match alone; overwrite a conflicting CBZ; start itself after a reboot; correct every existing populated field (unfinished).

## Facts

| | |
|---|---|
| Version | 0.1.1 (`VERSION`; tag `v0.1.1`, 2026-10-12) |
| Repo | https://github.com/Gemanoneko/Comics_Meta.git, branch `main` |
| Phase | Daily Use (confirmed by Sergei 2026-10-12) |
| Stack | Python 3.11+ on Windows; local web dashboard (stdlib `ThreadingHTTPServer`) on http://127.0.0.1:8765; Pillow; Playwright driving installed Microsoft Edge; local catalog and state in `data/` (gitignored). Optional: Ollama `gemma3:4b`, 7-Zip (CBR/CB7 conversion), SerpApi key. Dependencies pinned exactly in `requirements.txt` |
| State | `config.json`, `.env`, `data/`, `batches/`, `work/` live in the state root: this folder unless `COMICS_META_STATE_ROOT` names another absolute folder (the packaged app will use `%LOCALAPPDATA%\ComicsMeta`) |
| Library lock | `%LOCALAPPDATA%\ComicsMeta\locks` — one copy of the app per library (see Decision Log) |
| Launcher | `run.cmd` → `start-app.ps1` registers and starts the on-demand scheduled task `ComicsMeta-Local-8765`, which runs `server_host.py` → `app.py` |

## How to start and stop

1. Double-click `run.cmd`. The dashboard is at http://127.0.0.1:8765. The launcher window can be closed.
2. After a reboot, double-click `run.cmd` again. There is no sign-in or startup trigger.
3. To stop: press **Pause**, wait for **Paused**, then end `ComicsMeta-Local-8765` in Windows Task Scheduler.

## Commands

- Dev run: `python app.py`
- Tests: `python -m unittest discover -s tests -v` — always the whole discovery run: `tests/test_0_state_isolation.py` loads first, points state and locks at a throwaway folder, and refuses any access to this folder's `data/`, `batches/`, `config.json`, `.env` and to `%LOCALAPPDATA%\ComicsMeta`; `test_zz_state_isolation.py` fails the run if a refusal was swallowed. A single module run (`-p test_x.py`) bypasses that net. Set `COMICS_META_TEST_SCRATCH` to an absolute folder (with the exact letter case Windows reports) to keep test folders out of the checkout.
- Build: none (no installer or build step)
- Release: Sully bumps `VERSION` and `CHANGELOG.md`, commits, creates a named tag and pushes it. No `package.json` or lockfile.

## Decision Log

| Decision | Chosen | Alternatives | Revisit trigger |
|---|---|---|---|
| Tech stack | Today: Python service + local browser dashboard. Standalone app (decided 2026-10-12, milestones M1–M5): **Electron shell** (window, tray, installer, through the electron-builder release path the studio already runs for QuickLaunch and ComixManagementTool) **+ embedded CPython** running the Python service unchanged | pywebview — tray needs a second library and there is no studio installer/update path for it. PyInstaller / Nuitka — the supervisor relaunches `worker.py` and `browser_worker.py` with `sys.executable`, and the browser owners check `sys.argv[0]` against those files; a frozen executable breaks both, and packed executables are often flagged by antivirus. Tauri — new Rust toolchain, and Python would still run as a sidecar | Embedded CPython cannot run Playwright/Edge or the worker processes from the install folder |
| Launcher | Today: on-demand scheduled task, no auto-start. Standalone app: Sergei starts it himself | Not recorded | Not recorded |
| Auto-start | **None** — no sign-in or startup trigger (Sergei, 2026-10-12) | Start at sign-in (declined) | Sergei asks for it |
| Window close | **Tray-resident** (Sergei, 2026-10-12): closing the window hides it and processing continues. Tray menu: **Open / Pause & release GPU / Quit**. This is a **recorded exception to ProcessRules § The close button must always quit the process**, in the same form as QuickLaunch's: the invariant moves to the tray's **Quit**, which must need no renderer round-trip. One difference: Quit here is a **graceful stop** (Sergei's choice), so it is not instant. The Python side finishes its current safe step (at most one archive write or conversion) before exiting. The wait is settled (Sergei, 2026-10-12): the wait runs in the main process only, **Quit now** is offered from 1.5 s, the process exits immediately when idle, Quit also waits for Gemma to release the GPU, and a **10-minute** force-quit fallback replaces the rule's 1.5–30 s range for this tool only (a conversion can take up to 600 s). Details: `ComicsMetaOrganizer_UXSpec_DesktopShell_2026-10-12.md` §3 and §11 | Quit on window close (processing would stop whenever the window closes) | A Quit that does not end, or Sergei wants close to quit |
| Version line | Continues from 0.1.1; the standalone app does not jump to 1.0.0. Sully picks each bump (Sergei, 2026-10-12) | Restart at 1.0.0 (declined) | Sergei asks |
| State location (M1) | Code and state are separate. `COMICS_META_STATE_ROOT` (absolute) selects the state root for `config.json`, `.env`, `data/`, `batches/`, `work/`; the packaged app will set `%LOCALAPPDATA%\ComicsMeta`. Unset, state stays in this folder, so the running checkout is unchanged and nothing moved in M1 | State beside the code (an installed app's folder is replaced on update); a config file naming the state folder (that file would itself be state) | The M5 data move |
| One writer per library (M1) | A claim per process (dashboard, metadata worker, cover worker, batch command), held as an OS file lock in `%LOCALAPPDATA%\ComicsMeta\locks` and tagged with the state root; every archive write, backup removal and conversion re-checks it. A live claim from another state root on the same, a parent or a child folder is refused: the dashboard exits with code 75, a worker exits and the supervisor retries every 30 s. Copies sharing a state root never block each other. Locks end with the process, so a crash or a killed leftover worker leaves nothing to clear | Lock file inside the library (writes into the library and misses parent/child overlaps); `%ProgramData%` (an elevated and a normal process of the same user cannot share files there); PID files (stale after crashes, PIDs are reused) | The app runs as another Windows account or as a service, or the library is shared between machines |
| Quit vs Pause (M1) | Quit (`POST /api/quit`) is transient: no new workers start, running workers stop at the next safe step (the same checkpoints Pause uses) and exit, the server waits for an in-flight manual write and for both worker leases, then exits. The saved Pause setting is untouched, so the next launch carries on as before | Pause, then exit (the app would come back paused) | Quit regularly takes too long |
| Secrets lookup (M1) | `.env` in the state root, then config `env_file` (a relative path is read from the state root). The fallback to the studio root (`BASE.parents[1]/.env`) was removed: no such file exists on the live machine and the live config names an absolute `env_file` | Keep it (for an installed app, two folders above the code is an arbitrary folder) | — |
| Human verification | Sergei completes Lens/Yandex checks himself in a dedicated window; the app never solves them | Not recorded | Not recorded |
