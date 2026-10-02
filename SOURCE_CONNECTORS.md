# Automatic metadata sources

Metron, GCD and Google Books are connected to automatic discovery. Credentials remain in the configured `.env`; dashboards, request errors and cache keys exclude secrets.

- Metron: exact series, issue number and cover year, unique result, local/remote cover agreement.
- GCD: exact series and number plus cover agreement; check the key date when present. If a cover cannot be retrieved, no identity-dependent write is made.
- Google Books: graphic novels and collected editions only. Match an existing ISBN, or an exact title and matching cover; reject ambiguous results.
- Open Library: local dump index, exact ISBN matching. This avoids bulk API harvesting. The dashboard reports that bulk data is required until an index exists.

New descriptions pass the existing quotation, claim and spoiler checks before being queued. The serial writer verifies metadata and archive page integrity before removing a full backup. Existing populated fields are retained by these fallback connectors.

GCD uses a conservative application budget of 1,000 requests per rolling day; Google Books uses 500. Both cache successful responses for seven days and honor server retry delays. Metron reads the server's burst and sustained quota headers.

## Open Library local data

Download a works or editions dump from https://openlibrary.org/developers/dumps when sufficient temporary space is available. From this folder, run:

```powershell
python open_library.py "D:\Downloads\ol_dump_editions_latest.txt.gz"
python open_library.py "D:\Downloads\ol_dump_works_latest.txt.gz"
```

The importer streams compressed data and retains only current catalog title/ISBN matches in `data/open-library.sqlite`. It does not decompress the whole dump. Import editions and works for edition identification plus work descriptions. Source dump files are not deleted by the importer. Re-import when the catalog expands; no dump has been downloaded automatically.

## Validation and current scope

62 automated checks passed, including wrong-issue rejection, edition ambiguity, redirect refusal, local ISBN/work linkage, synopsis write/read-back, archive-content preservation, verified-backup cleanup and checkpointed folder traversal. GCD and Google Books also returned real API JSON through these connectors.

Initial validation used `Y:\Comix\!Coffin Comics`. The user has since confirmed a live synopsis in YACReader and authorized broader rollout. A newly discovered GCD or Google Books live write has not yet been demonstrated. The write-and-read-back regression check uses an isolated test archive.

The oversized automatic lookup cache was rebuilt from 49 recoverable records. Comic archives and source evidence were retained. Cache reads now have a size guard, per-file errors are bounded, and queue/storage errors cannot silently end the worker's main loop.

The server now supervises the worker and retries an exited process every 30 seconds. The queue lock prevents concurrent writers; interrupted writes remain flagged for inspection. The dashboard reports the next folder check time.

## Lead resolution and cover research

Saved web results and relevant Wikipedia external references are followed automatically. Unrelated wiki hits are discarded. Issue identity checks reject broad series pages, wrong issue numbers and Reddit-only identity claims. Cover verification compares layout and edges to tolerate scan brightness, in addition to the existing pixel check. Fractional issue numbers remain distinct.

Unresolved cover searches are persisted in the catalog. A supervised project-owned browser worker uploads covers to Google Lens independently of the chat, with a dedicated profile, pacing and daily limits. Human-verification pages stop browser searches and surface a dashboard action; the user completes verification in a dedicated window. SerpApi's Image and Lens APIs provide an optional monthly-capped fallback. Lens candidates enter the ordinary verifier and do not directly authorize writes. General free search can still be blocked or capped.

70 automated checks passed after adding browser queue exclusivity, persistent request limits, stale-archive rejection, safe result extraction and key-redacted API errors. A real browser cover upload reached Google Lens and encountered a human-verification page, correctly reported without attempting to solve it. A real SerpApi fallback for Lady Death - Sacrilege #2 returned six candidate links and persisted them for ordinary verification; these search results alone did not trigger an archive write.

Per-file research state now lives in SQLite and is loaded one folder at a time. Legacy JSON state is migrated once. A 25,000-record regression check verifies that only the current folder is loaded.

A live Lady Death / Shi #1 commemorative cover was found through Google Lens, independently compared with its catalog cover, and paired with the exact ComicVine issue. Issue-wide credits and an agent-reviewed internet synopsis were written and read back successfully; verified backups were removed. The user confirmed the synopsis appears correctly in YACReader. Folder-by-folder rollout is now configured for Y:\Comix; explicitly non-English comics are skipped, while unknown languages are not guessed.
