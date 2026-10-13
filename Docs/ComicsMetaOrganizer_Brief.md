# Comics Meta Organizer — Brief

**What it does.** A local background service for Sergei's YACReader comic library. It scans the library folder by folder, identifies each comic from what the comic itself says (a saved cover reading that agrees with the filename) or from external sources (ComicVine, Metron, GCD, Google Books, publisher/web research, an optional Open Library dump, Google Lens cover search with an optional SerpApi fallback), and writes verified `ComicInfo.xml` into CBZ archives. A backup is removed only after the written file reads back correctly and passes a SHA-256 check. **What Sergei does with it:** keeps it running, watches the dashboard, presses **Pause & release GPU** when he needs the computer, completes Google Lens human verification when the dashboard asks (Yandex is no longer searched since 2026-10-12), then runs YACReader's **Rescan library for XML info**. **What it does not do:** edit YACReader's database; solve CAPTCHAs or spoof browser fingerprints; write metadata from a search match alone, or from a cover reading that disagrees with the filename or whose issue number is unread; take creators from a cover or a year from a copyright line; overwrite a conflicting CBZ; start itself after a reboot; correct every existing populated field (unfinished).

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
- Tests: `python -B -m unittest discover -s tests -v` (`-B` writes no `__pycache__`; test folders are removed, so the checkout is left as found)
- In-book credits pilot (read-only, run while paused): `python -B pilot_credits.py --out <folder> [--limit 40]`
- Build: none (no installer or build step)
- Release: Sully bumps `VERSION` and `CHANGELOG.md`, commits, creates a named tag and pushes it. No `package.json` or lockfile.

## Decision Log

| Decision | Chosen | Alternatives | Revisit trigger |
|---|---|---|---|
| Tech stack | Python service + local browser dashboard | Not recorded | Not recorded |
| Launcher | On-demand scheduled task, no auto-start | Not recorded | Not recorded |
| Human verification | Sergei completes Lens/Yandex checks himself in a dedicated window; the app never solves them | Not recorded | Not recorded |
| In-book identification (v0.1.3) | A saved cover reading writes Series and Number when the cover title and number agree with the filename; an unnumbered file is a whole book and gets Series only on an exact title; empty fields only; provenance in Notes, history source `in-book:cover` and per-field evidence (Sergei 2026-10-12: the comic itself is enough) | External source required for every write (v0.1.2) | A wrong in-book write is reported, or Futaba's sample finds one |
| In-book limits (v0.1.3) | Never creators or a year from a cover; no write when the cover number is unread or differs, the filename number is a volume/book/part, chapter naming or a reading-order prefix, or the filename is tagged as a translation (Jane's defaults 2026-10-12) | Writing unread-number files; creators from covers (46% wrong in the throughput review) | Sergei decides the unread-number files (about 3,900 saved readings) |
| In-book publisher (v0.1.3) | Off by default, pending Sergei's decision (Jane's interim default 2026-10-13, code review F21): the local model's publisher reading disagreed with embedded publishers 10 of 206 times (4.9%) and with same-folder peers 22 of 543 (4.1%), and a wrong value sticks because later sources fill only empty fields; Series and Number are unaffected. `"in_book": {"publisher": true}` switches it on: only a canonical publisher named in full in the reading, skipped when the reading names a second publisher. Applies to the credits tier too | On by default (v0.1.3 candidate; Metron agreed on 139 of 146); not built yet: write it only when a publisher tag in the filename or folder, or the publishers already embedded in the same folder, corroborate it (or veto on a disagreeing tag or folder majority) | Sergei decides: on, off, or the corroboration option |
| In-book versus external values (v0.1.3) | A later verified external match fills only empty fields; it never replaces an in-book value, because the safety chain never overwrites a populated field | Replace in-book values when series and number agree (Jane's permissive default) | Sergei asks for replacement |
| Pass plans (v0.1.3) | One plan and ticket per folder pass, up to 50 comics. Right before each write the archive must match the scan that planned it and its ComicInfo must still hold each planned field's earlier value; otherwise the comic is skipped without writing (`skipped.json`) and planned again (code review F22). A write that fails with the archive untouched is recorded (`failed.json`) and retried after the daily retry, or at once when the archive changes; the rest are written (F23). An archive that may have been written but did not verify still stops the ticket for inspection, backup kept | One plan per comic, one pass per write; one failing comic ending the whole plan as `needs_attention` (v0.1.3 candidate) | A batch needs inspection because of an entry, or one archive keeps failing its daily retry |
| Folder selection (v0.1.3) | Probe history through a keyed temporary table and an additive case-insensitive path index (`comics_path_nocase`, created once); completed queue tickets are cached until their file changes | Unindexed join (13.8 s per probe at 60,000 comics) | Probe slower than 1 s on the live catalog |
| Yandex (v0.1.3) | Removed from the regular engines; code, profile, state table and hold kept; dashboard row hidden | Keep as third engine | Sergei wants it back |
| Source switches (v0.1.3) | `sources.disabled` in config.json, default: general free web, Wikipedia/wiki, saved-lead re-checks, GetComics, PREVIEWSworld; code kept | Delete the sources | A switched-off source is needed again |
| ComicVine (v0.1.3) | Only after Metron and only by an embedded ComicVine issue ID; no ComicVine search without one. For a comic with an ID it is also the v0.1.2 identity check, asked even when Metron answered (30-day cache); Metron's fields wait for its answer | ComicVine search first for every comic (v0.1.2); Metron written without the identity check (v0.1.3 before the rebase) | ComicVine search yields return, or the identity check's requests limit throughput |
| In-book versus identity rules (v0.1.3, rebase onto v0.1.2) | The in-book tiers never write a comic whose `Web` names a ComicVine issue (agreeing, conflicting, held or dead), nor one recorded as an identity conflict; such a comic is not made due or ranked first by a saved reading either. A held comic always carries the conflict risk, because its ComicVine issue is unchecked | In-book for held comics without conflict risk (Jane's default, which no held comic meets) | Sergei wants Web-ID comics written in-book once ComicVine agrees |
| Held comics (F18, v0.1.3) | Retried after 5, 10, 20 and 40 minutes, then hourly, never before ComicVine's own wait ends; later held passes only ask ComicVine again; comics held by a ComicVine wait are woken when ComicVine answers any request; a missing key or an empty answer keeps the daily retry; source results carried from the first held pass no longer make a held comic due (code review F24) | Every 10-minute folder pass (v0.1.2); doubling up to 24 h (Senua's first option) | Recovery after an outage takes over an hour, or held passes show up in pass timing |
| Library walk (v0.1.3) | Whole-library walk every 6 hours (`automatic.inventory_interval_seconds`, at least 600); known folders keep their delta scans | Every 10 minutes | New folders need to appear sooner |
| Credits/indicia tier (v0.1.3 stretch) | Built, off by default (`in_book.credits_pages`, creators separately `in_book.credits_creators`); `pilot_credits.py` measures it read-only against Metron-verified comics | Enable now | Pilot results reviewed by Sergei |
