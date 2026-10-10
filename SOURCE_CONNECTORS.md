# Automatic metadata sources

Metron, GCD and Google Books are connected to automatic discovery. Credentials remain in the configured `.env`; dashboards, request errors and cache keys exclude secrets.

- Metron: exact series, issue number and cover year, unique result, local/remote cover agreement.
- GCD: exact series and number plus cover agreement; check the key date when present. If a cover cannot be retrieved, no identity-dependent write is made.
- Google Books: graphic novels and collected editions only. Match an existing ISBN, or an exact title and matching cover; reject ambiguous results.
- Open Library: local dump index, exact ISBN matching. This avoids bulk API harvesting. The dashboard reports that bulk data is required until an index exists.
- GetComics: metadata-only fallback after database sources. A shared SQLite gate permits at most one uncached HTTP request per five minutes across workers and restarts, including followed pages and redirects. Search results and source pages are cached for seven days. Exact issue checks or exact book title/year/known publisher checks must pass before synopsis review; ambiguous candidates are rejected. Human verification and access failures stop further site requests and are shown on the dashboard. No challenge bypass or comic-download links are used. Contact the assistant after manually verifying access to arrange a controlled retry.

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

## Provider waits and research priority

Dark Horse and Image use their public catalog searches; PREVIEWSworld uses targeted web-search results and accepts only product catalog pages. No accounts or credentials are used. Each catalog has a shared 300-request rolling daily budget and five seconds between uncached requests, including redirects; pauses interrupt pacing. Search results and product evidence are cached for seven days. Site challenges stop requests and other access failures cool down for one hour. Verified issues require exact series/number, available release year and cover agreement. Collected editions require exact volume/title, available release year and existing ISBN agreement or matching cover. Only missing publisher/identity fields and reviewed synopsis evidence are supplied; variant credits and unverified edition details are excluded. A synthetic match check is not a demonstration of a live archive write. PREVIEWSworld was inaccessible in the initial live probe and remains subject to public-web search availability.

Provider-wide request budgets, verification blocks and service outages are recorded separately from comic-specific errors. They retain the normal research retry (one day for unresolved identity, 30 days for current verified identity), rather than shortening it to an hour. Actual per-comic errors still use the shorter retry. Cached responses remain usable before provider cooldown checks. A one-time migration repairs old GetComics-only hourly retry records without changing comic archives or hiding other errors. Within each folder, unresearched comics are preferred, followed by verified source leads, then unresolved retries. ComicVine transient connection failures impose a shared five-minute cooldown instead of being repeated for each comic.

## Stage timing, verified evidence reuse, and bounded research

The dashboard shows cumulative stage calls, average seconds and total minutes from this update onward. Inventory, source research, local model, synopsis review, and archive writing/verification are measured separately. Parent stages include child stages and concurrent source time overlaps; adding all rows is not elapsed processing time. Evidence reuse and accepted/rejected synopsis reviews have separate counters. These small aggregate records persist across restart.

Newly verified source evidence can be reused for 30 days when the matcher version, comic identity, and sorted archive image names/CRC/size still agree. The record accepts the original identity and the identity produced by filling verified missing fields, so an app XML update does not invalidate it. Changed pages, issue, year, ISBN, title or format reject reuse. Legacy search leads alone are not reusable verified evidence. A reused synopsis source still passes the ordinary quotation and spoiler checks before writing; synopsis text is not inferred from story pages.

For each comic, up to two independent fallback sources run concurrently after ComicVine. Each source retains its existing match verifier and request budgets/pacing/cooldowns. Same-provider API calls remain serialized. Once a verified source succeeds, no additional sources are scheduled; already-running work finishes, with deterministic source priority. Pause stops new scheduling and drains in-flight lookups before acknowledging. Local model work and verified archive writes remain serial. This does not create parallel writers or increase API quotas.

The rolling throughput line counts completed comic research checks separately from distinct comics updated and archive writes. It observes up to the last hour from measurement activation, includes paused/offline time, and uses minute buckets for checks. Multiple writes to one comic count as one updated comic. Check buckets are retained for only seven days; no archive copies or unbounded event logs are created.

In the initial live timing sample, Metron consumed 523 of 899 measured research-pass seconds (overlapping source times are not additive), while the first roughly ten-minute sample checked 202 comics without a new write. Metron now shares complete series/year candidate responses through its existing seven-day request cache. Incomplete lists fall back to the original issue-specific search, and truncated issue-specific results still cannot verify uniqueness. A candidate cover is compared before fetching issue details; detail identity, release year and any changed detail cover are checked again. Request pacing, provider cooldowns and limits are unchanged. A synthetic three-issue rejected-cover check requires one uncached candidate request and no issue-detail requests, versus up to six metadata requests in the original sequence. This is a request reduction, not an established whole-library speed multiplier or evidence of newly written live metadata.

## Source scheduling and fair folder retries

Verified identity alone no longer ends fallback research: a result must supply a populated missing field or at least 20 words of source text when the synopsis is missing. This is a scheduling test, not synopsis approval; the same quotation, narrative and spoiler review still gates writes. Thin cached evidence also cannot block richer sources. ISBN lookups prefer the local Open Library index and Google Books; collected editions favor Google Books, and known Dark Horse/Image hints favor their catalogs. All ordinary fallback sources remain available, with at most two concurrent lookups and unchanged request limits.

Per-source retry state is stored with the existing comic research checkpoint. Repeated misses or verified matches without useful new data back off from one day to two, four and at most seven days. Real source errors back off from one hour to at most six hours. Provider-wide blocks remain provider waits, not comic errors: recovery reported as available can wake waiting research early, while an expired but still-unavailable status does not create hourly per-comic retries. A first source attempt still permits its ordinary cached responses. New/changed archive signatures, matcher changes and fresh cover leads reset source backoff. Research already checkpointed before this update gains the new source schedule on its next normally due pass; it is not mass-reset.

Changed files rank alongside new files ahead of unchanged retries in a folder. Continued folder work is placed behind older due folders, rather than monopolizing selection with a zero timestamp. Writes still run before the next research pass, and checkpoints remain durable across pause/restart. A synthetic end-to-end check verifies that a thin cached match is bypassed and useful fields from another verifier enter the serial write queue; it does not demonstrate a new live write.

## Metron enrichment and synopsis diagnostics

After exact issue/date/cover verification, Metron supplies supported issue-wide dates, title, publisher/imprint, series volume, interior creator roles, characters, teams, arcs, genres, language, format, age rating, ISBN and compatible GTINs when available. Cover credits remain excluded because primary issue records can mix variant artists. Publisher page counts and unsupported roles/types are not guessed. Existing populated archive fields remain protected. Older thin Metron evidence is refreshed through the verifier on one bounded upgrade attempt, without resetting the entire library or changing request budgets.

A live diagnostic of Hell to Pay #1 showed that free-form Gemma responses paraphrased an excerpt and sometimes used narrative prose in a boolean field. Selection now chooses an ID from at most 24 literal contiguous source spans of 20–100 words. Ollama JSON schemas constrain selection and audit responses; exact source matching, supported quotes and independent narrative/spoiler checks still gate every synopsis. A diagnostic on the same saved internet source then passed those checks. This diagnostic itself did not write a comic. Rejection categories and bounded review reasons are saved per comic as `synopsis_diagnostics`, with aggregate rejection-category timings/counters; unbounded raw model-output logs are not retained. ComicVine status events now allow retry timestamps without duplicate-key errors, so HTTP rejection/cooldown statuses remain visible. This repairs reporting, not external HTTP 403 access restrictions.

## Same-pass synopsis completion and exact XML readback

Verified metadata and a separately accepted internet synopsis now share one per-comic plan, digest, archive rewrite and verification. Synopsis review runs in the same pass instead of waiting for a later folder rotation. A rejected synopsis or model error does not discard independently verified metadata. Pause retains an already prepared metadata plan without starting a write. Provider pacing, budgets, identity/cover checks and independent spoiler/quotation review are unchanged.

Jim Henson's Presents #3 failed strict batch readback because its accepted source excerpt contained CRLF paragraph breaks: XML normalizes literal carriage returns to line feeds. The writer now encodes carriage returns as XML character references, preserving the exact text through parsing. It also verifies every supplied field in the temporary archive before replacing the live original or recording a successful write. The live issue was repaired using its previously accepted synopsis; full archive CRCs and unchanged non-XML contents passed. Its retained 65 MB original backup and the repair backup were removed only after verification. The failed queue ticket now records the verified recovery.

Regression checks cover exact CRLF/lone-CR readback, backup cleanup, preservation of the original on temporary metadata verification failure, and one combined plan with an accepted synopsis or metadata alone when review rejects the synopsis. These changes remove a scheduling delay; sustained synopsis completion still depends on sufficient verified internet text and the existing spoiler review.
