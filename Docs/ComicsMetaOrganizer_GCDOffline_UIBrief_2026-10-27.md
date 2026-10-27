# GCD offline index panel: UI brief for Judy (one pass)

Ender sent this on 2026-10-27, for the 0.6.0 GCD batch. It lists what the screen needs, not the copy or the layout. Judy writes the spec, and Ender implements it in the same batch. The rulings are in the Backlog entry "GCD data dump as an offline source". Status: **parked**. Judy has not started.

## Purpose
About every 2 weeks, Sergei downloads `current.zip` from comics.org by hand (about 1.9 GB) and points the app at it. The app builds a local index from that file and matches comics against it.
- The build takes about 2–3 minutes and needs about 7.5 GB free on the app-data drive while it runs. The finished index is about 0.3 GB.
- Matching keeps using the old index until the new one has been checked and swapped in.
- Comics the old index missed get one more try after a swap.
- The app only reads the zip. It never changes or deletes it.

## States (engine: `GET /api/gcd-offline`)
1. **No index yet.** Nothing is matched from GCD offline. Action: choose a zip.
2. **Ready.** Shows:
   - the dump date, taken from the zip (e.g. 2026-10-16);
   - when the index was built;
   - the dump's age in days;
   - the file name of the last zip used;
   - optionally, series and issue counts.

   Action: choose a newer zip.
3. **Building.** Shows the stage, progress within that stage, overall progress and elapsed time. The stages are:
   1. checking the zip;
   2. unpacking;
   3. series and issues;
   4. credits and synopses;
   5. checking the index;
   6. switching over.

   Action: cancel. Cancelling keeps the old index and removes the temporary files.
4. **Last update failed or was interrupted** (for example, the app quit mid-build). Shows the reason, using the errors below; the old index stays in use if there is one. Actions: choose a zip again, or dismiss.
5. **Open question for Sergei and Judy:** should a "dump is old" reminder appear after N days? The engine exposes the age either way.

## Actions
- **Choose zip.** A native file dialog for one `.zip`, starting in Downloads. It needs a new desktop bridge call, like the existing library-folder picker. An extracted `.db` file is also accepted, and is then not deleted.
- **Optional confirm step.** `POST /api/gcd-offline/inspect` returns the dump date, file size, disk space needed and disk space free, without building anything. Judy decides whether to show a confirm step or start straight away.
- **Build.** `POST /api/gcd-offline/build {zip, force}`. The engine refuses a dump that is the same as or older than the current one unless `force` is set. Judy decides whether "rebuild anyway" is offered at all.
- **Cancel.** `POST /api/gcd-offline/cancel`.

## Errors (engine codes)
Each needs short wording and a next step for Sergei.

| Code | Meaning |
|---|---|
| `zip_missing` | The file is not found or not readable. |
| `not_a_zip` | The file is not a zip archive. |
| `not_gcd_dump` | The zip does not hold exactly one GCD SQLite database (e.g. the MySQL download was picked). |
| `schema_unsupported` | GCD changed its database layout. |
| `disk_space` | Not enough free space. The engine reports the GB needed, the GB free and the drive. |
| `same_dump` / `older_dump` | This dump is already in use, or is older than the one in use. |
| `busy` | An update is already running. |
| `cancelled` | The update was cancelled. |
| `interrupted` | The last update did not finish; the old index is still in use. |
| `build_failed` | Unexpected; shown with a short detail line. |

## Also visible elsewhere (Judy's call)
- The source status line gets a "GCD offline" entry, showing ready (with the dump date), building, or no index.
- **Licence:** Notes already credits GCD (CC BY-SA 4.0) with the issue link. A one-line credit or a link to comics.org/download in the panel is optional.

## Not needed
No settings for the matching rules (Sergei's rulings fix them) and no per-comic controls.
