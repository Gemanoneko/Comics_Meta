# Comics Meta Organizer — Brief

**What it does.** A local background service for Sergei's YACReader comic library. It scans the library folder by folder, identifies each comic from external sources (ComicVine, Metron, GCD, Google Books, publisher/web research, an optional Open Library dump, Google Lens cover search with an optional SerpApi fallback), and writes verified `ComicInfo.xml` into CBZ archives. A backup is removed only after the written file reads back correctly and passes a SHA-256 check. **What Sergei does with it:** keeps it running, watches the dashboard, presses **Pause & release GPU** when he needs the computer, completes Google Lens or Yandex human verification when the dashboard asks, then runs YACReader's **Rescan library for XML info**. **What it does not do:** edit YACReader's database; solve CAPTCHAs or spoof browser fingerprints; write metadata from a cover or search match alone; overwrite a conflicting CBZ; start itself after a reboot; correct every existing populated field (unfinished).

## Facts

| | |
|---|---|
| Version | 0.1.1 (`VERSION`; tag `v0.1.1`, 2026-10-12) |
| Repo | https://github.com/Gemanoneko/Comics_Meta.git, branch `main` |
| Phase | Daily Use (confirmed by Sergei 2026-10-12) |
| Stack | Python 3.11+ on Windows; local web dashboard (stdlib `ThreadingHTTPServer`) on http://127.0.0.1:8765; Pillow; Playwright driving installed Microsoft Edge; local catalog and state in `data/` (gitignored). Optional: Ollama `gemma3:4b`, 7-Zip (CBR/CB7 conversion), SerpApi key |
| Launcher | `run.cmd` → `start-app.ps1` registers and starts the on-demand scheduled task `ComicsMeta-Local-8765`, which runs `server_host.py` → `app.py` |

## How to start and stop

1. Double-click `run.cmd`. The dashboard is at http://127.0.0.1:8765. The launcher window can be closed.
2. After a reboot, double-click `run.cmd` again. There is no sign-in or startup trigger.
3. To stop: press **Pause**, wait for **Paused**, then end `ComicsMeta-Local-8765` in Windows Task Scheduler.

## Commands

- Dev run: `python app.py`
- Tests: `python -m unittest discover -s tests -v`
- Build: none (no installer or build step)
- Release: Sully bumps `VERSION` and `CHANGELOG.md`, commits, creates a named tag and pushes it. No `package.json` or lockfile.

## Decision Log

| Decision | Chosen | Alternatives | Revisit trigger |
|---|---|---|---|
| Tech stack | Python service + local browser dashboard | Not recorded | Not recorded |
| Launcher | On-demand scheduled task, no auto-start | Not recorded | Not recorded |
| Human verification | Sergei completes Lens/Yandex checks himself in a dedicated window; the app never solves them | Not recorded | Not recorded |
