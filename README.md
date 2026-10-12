# Comics Meta

A local comic metadata tool for YACReader libraries. It scans folders, identifies comics using external sources, writes ComicInfo.xml into CBZ archives, and verifies archive contents before removing temporary backups.

## Setup

Use Python 3.11 or newer on Windows.

```powershell
python -m pip install -r requirements.txt
Copy-Item config.example.json config.json
Copy-Item .env.example .env
```

Fill in the credentials you want to use in `.env`. Set `automatic.root` to your comic folder in `config.json`, then set `automatic.enabled` to true. Start with a small folder of copies to check results before enabling a live library.

```powershell
python app.py
```

The dashboard opens at http://127.0.0.1:8765. Keep the service running. Local configuration, credentials, comics, generated plans and runtime state are excluded from Git.

The header version comes from the running server, captured once from `VERSION` at startup. Editing the checkout cannot relabel an older running process. A backend without version reporting shows **Version unavailable**. This lightweight Python tool uses `VERSION` and `CHANGELOG.md`; Sully owns milestone version changes, commits and pushes. There is no installer/build step. Run offline Python checks with `python -m unittest discover -s tests`; actual DOM fixtures require the separately owned headless test harness and make no public requests.

Ordinary free research can fall back from DuckDuckGo to Bing and Yandex using the same comic query. They share the300/rolling24hour cap and minimum120second navigation spacing. Yandex human verification has its own dashboard action beside Lens. Click once when requested, wait for any displayed budget/pacing deadline, and complete verification in the dedicated window. The app closes that window after observing success; later searches use the same dedicated profile. Pause or service restart cancels pending visible-window intent, so Resume cannot unexpectedly open it. Search links remain leads and never bypass exact comic/source verification. See `SOURCE_CONNECTORS.md` for provider and live-validation limits.

On Windows, double-click `run.cmd` for the persistent launcher. It registers an on-demand task named `ComicsMeta-Local-8765` under your current Windows account and starts the server independently of the launching terminal or client. You can close the launcher window. Windows retries a failed task up to three times, one minute apart. There is no automatic sign-in/startup trigger; start it again after reboot. The saved pause setting remains in effect. Server logs retain one bounded tail from the previous run, and `data/server-exit.json` records observed server exit codes. Pause processing and wait for Paused before stopping the task in Windows Task Scheduler.

## Local model

Install Ollama and download the optional model:

```powershell
ollama pull gemma3:4b
```

Gemma reads cover identification text and selects exact narrative excerpts and checks them for spoilers using internet evidence. Archive story inference is disabled. Cover hints alone do not authorize metadata writes.

## Automatic processing

The scheduler progresses folder by folder, checks new or changed files, persists retries and uses a serial write queue. Library traversal is checkpointed in small steps, so discovered folders can be processed before the entire tree has been inventoried. The service retries an exited worker every 30 seconds; its lock prevents concurrent writers. Interrupted writes are flagged for inspection instead of blindly replayed.

Eligible comics without an app update in the database write history take priority across folders and within each folder. Coverage passes skip refinements, including in mixed folders. Bounded catalog checks retain the existing research retry windows; refinements resume when no eligible first-update work is found in the inventoried catalog. Waiting readiness snapshots last at most 60 seconds, expire at earlier known retries, and are invalidated by new catalog entries, write history, active tickets, inventory or source availability changes. Existing embedded metadata alone does not count as an app update. Queued work and the current write finish normally.

ComicVine, Metron, GCD, Google Books and publisher/web research are supported. Open Library uses an optional local dump index. See [source connectors](SOURCE_CONNECTORS.md) and [synopsis policy](SYNOPSIS_POLICY.md).

The dashboard shows the configured live scope, working/waiting state, unresolved research and whether a synopsis exists. A completed folder pass or existing metadata does not prove completeness or accuracy. Manual lookups are optional.

## Automatic cover search

Reverse-image searches are an identity fallback after database, publisher and web/wiki lookups fail to identify the comic. Missing a synopsis alone does not trigger a reverse search. A comic whose ComicVine issue disagrees with its embedded series and number is searched like an unidentified one. Outstanding requests are cancelled when another source identifies the comic; stale archive requests are discarded before uploading.

Automatic browser cover search is available through `browser_search.enabled`. The independent supervised worker uses Playwright and installed Microsoft Edge (`channel: "msedge"`), with a dedicated profile under `data/lens-profile`. Normal searches run in the background. Only the first archive image is uploaded as a resized cover; archive filenames, folder paths and interior pages are not uploaded.

Searches are paced at least 30 seconds apart (60 by default), capped at 100 attempts per UTC day by default, and successful results are cached for 30 days. Changed archives are rejected. A search that cannot run (cooldown, daily cap, Google human check, or a SerpApi cap during one of these) is not a result: the comic keeps its queue place and retry wait, records the real reason, and is searched when the hold ends. The daily cap holds searches until the UTC day resets; it starts no cooldown. A search that ran and found nothing usable is retried after one day. Candidate links that all fail identity verification lead to a fresh cover search after the 30-day cache expires; the saved links are re-checked on each daily research pass meanwhile. No cover search ends in a final no-result state. If Google requests human verification, click **Open Google Lens verification** once and complete it yourself in the dedicated window. The request wakes an idle worker; an in-flight search must finish first. The dashboard acknowledges queued/opening requests and disables duplicate clicks. After verification, the window is minimized while its verified session continues automatic searches. Leave it open; no manual action on the uploaded cover is needed. Pause closes it safely. The worker does not solve challenges or spoof fingerprints. Other metadata processing continues. Once you complete the check, the results page Google loads is read, and its links are added as unverified candidates for the comic whose search hit the check. A brief page error while Google redirects after the check no longer fails the attempt; a page error that persists for about a minute ends it with its error class. If you close the window after completing the check, the next search starts a new browser from the same profile.

Upgrading from 0.1.1: 0.1.1 saved searches that never ran as empty results. With processing paused, run `python relabel_cover_tasks.py` (counts only), then `python relabel_cover_tasks.py --apply` to requeue them in the order their searches were blocked. `--rollback` restores the requeued rows that have not changed since.

Lens verification now keeps a durable request receipt separately from ordinary cover progress. The dashboard names the engine and reports queued, opening, open, or failed outcomes; a failed window can be retried after closure is confirmed. Pause generations and service/worker replacement cancel pending intent. The browser worker owns a private Windows Job and exclusive Lens profile lease, and verifies descendant closure before cache maintenance or another launch. Human verification does not reset request counts or provider cooldowns.

Dashboard polls cannot overlap within each endpoint. `/api/browser-verification` reports Lens intent independently of aggregate progress. `/api/progress` uses one refresh at a time and retains complete legacy history; clients may send `completed_revision` to omit an unchanged `completed` array, which leaves their existing history intact. A preparing snapshot returns 503 for a later retry; a failed refresh retains the last full snapshot with `snapshot_stale`. No queue, plan, archive or historical row is dropped by this cache. Neither endpoint returns the Google challenge URL or the comic whose search hit it. Local diagnostic tables `lens_verification` and `lens_verification_events` retain request IDs, timestamps, phases, stages and error classes without raw exception text or challenge URLs.

Optional `SERPAPI_API_KEY` enables the configured SerpApi fallback when browser search fails or yields no candidates. The app uploads a resized cover via SerpApi's Image API and uses its Lens API. All attempts count conservatively against the app's cap of at most 250 per UTC calendar month. The provider's billing period and usage outside this app may differ; stay on its free plan and leave paid renewal disabled. Candidate links pass through the ordinary identity and cover verifier; search matches alone never authorize writes.

## Writes and recovery

Use **Pause & release GPU** whenever you need the computer's resources, for games or other work. **Pausing** means the current operation is finishing; a comic write completes verification and backup cleanup before stopping. **Paused** means both workers have stopped processing. The dashboard separately confirms when Gemma has been unloaded from the GPU. Other applications and other Ollama models are unaffected.

The pause setting survives service restarts. Queues, completed writes, research evidence and folder progress are retained. **Resume processing** continues the saved queue and loads Gemma again only when needed. A partially completed batch skips its verified archives after checking that they have not changed. Manual processing actions are blocked while paused. This is a manual control, with no automatic game detection.

ZIP-backed CBZ archives receive metadata writes. Installed 7-Zip enables automatic conversion of CBR/CB7 and RAR/7-Zip containers named CBZ. Conversion checks original archive integrity, decodes comic images, and compares every extracted member's SHA-256 and size against the resulting ZIP before removing the original. A conflicting CBZ is never overwritten. Failed conversions retain originals; same-name replacement rolls back if final readback fails. Each folder pass converts at most one archive.

Existing populated fields are generally preserved; automatic correction of all existing fields is unfinished. Writes preserve page contents and verify the resulting XML and archive integrity. Automatic and manual dashboard updates remove backups after final metadata readback and original-file SHA-256 verification; failed or interrupted writes retain recovery material. Unescaped ampersands in otherwise valid metadata XML are recovered when reading, and forbidden XML control characters are normalized to newlines; later metadata writes serialize valid XML. Cover search uses the supervised Google Lens browser worker and optional SerpApi fallback.

The list has separate filters for metadata with a synopsis, metadata lacking a synopsis, and a synopsis without other descriptive metadata. These indicate which fields exist, not that every possible field is complete. **Tagged by this app** remains a separate write-history filter. **Corrupted · Needs reacquiring** is separate from metadata syntax errors and unsupported containers.

## Disk cleanup

The serial worker performs hourly housekeeping. Expired lookup responses are removed, database response payloads and regenerable research caches are each capped at 64 MB, and browser disk/media caches are limited to 64/16 MB. Browser cache directories are cleaned when its context is closed; cookies and session data are preserved. Catalog records, queues, completed write audit records, source evidence, model weights and recovery backups are retained.

Completed conversion attempts remove extraction files immediately. Interrupted conversion staging is eligible for cleanup after 24 hours only when its registered original is still present and unchanged; possible recovery copies remain protected. Stale project temporary files and abandoned test folders are cleaned after 24 hours. Conversion reserves room for extraction and the new CBZ before starting. `data/maintenance.json` records routine cleanup; `conversions` and `conversion_staging` in the catalog record archive conversion and recovery state.

YACReader needs a **Rescan library for XML info** after metadata changes. The app does not directly edit YACReader's database.

`data/` contains the catalog, progress, evidence, quotas and queue. Keep it for continuity; this Git repository backs up code, not local library state. Never publish `.env` or `config.json`.

## Development

```powershell
python -m unittest discover -s tests -v
```

Tests cover archive preservation, safe writes, delta scans, matching rejection, quotas, encoding and worker supervision. Tests keep their catalogs and fixtures in temporary folders they remove afterwards; no test writes this checkout's `data/`. Browser layout changes and human-verification challenges can interrupt free cover searches. Uncertain identities remain unresolved; source availability and coverage vary.
