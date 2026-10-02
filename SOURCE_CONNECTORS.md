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

46 automated checks passed, including wrong-issue rejection, edition ambiguity, redirect refusal, local ISBN/work linkage, synopsis write/read-back, archive-content preservation and verified-backup cleanup. GCD and Google Books also returned real API JSON through these connectors.

Processing remains scoped to `Y:\Comix\!Coffin Comics`. This release has not yet demonstrated a newly discovered GCD or Google Books match being written to a live archive, or a new synopsis displayed in YACReader. The write-and-read-back regression check uses an isolated test archive.

The oversized automatic lookup cache was rebuilt from 49 recoverable records. Comic archives and source evidence were retained. Cache reads now have a size guard, per-file errors are bounded, and queue/storage errors cannot silently end the worker's main loop.

The server now supervises the worker and retries an exited process every 30 seconds. The queue lock prevents concurrent writers; interrupted writes remain flagged for inspection. The dashboard reports the next folder check time.
