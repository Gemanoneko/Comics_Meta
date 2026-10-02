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

## Local model

Install Ollama and download the optional model:

```powershell
ollama pull gemma3:4b
```

Gemma reads cover identification text and selects exact narrative excerpts and checks them for spoilers using internet evidence. Archive story inference is disabled. Cover hints alone do not authorize metadata writes.

## Automatic processing

The scheduler progresses folder by folder, checks new or changed files, persists retries and uses a serial write queue. Library traversal is checkpointed in small steps, so discovered folders can be processed before the entire tree has been inventoried. The service retries an exited worker every 30 seconds; its lock prevents concurrent writers. Interrupted writes are flagged for inspection instead of blindly replayed.

ComicVine, Metron, GCD, Google Books and publisher/web research are supported. Open Library uses an optional local dump index. See [source connectors](SOURCE_CONNECTORS.md) and [synopsis policy](SYNOPSIS_POLICY.md).

The dashboard shows the configured live scope, working/waiting state, unresolved research and whether a synopsis exists. A completed folder pass or existing metadata does not prove completeness or accuracy. Manual lookups are optional.

## Automatic cover search

Reverse-image searches are an identity fallback after database, publisher and web/wiki lookups fail to identify the comic. Missing a synopsis alone does not trigger a reverse search. Outstanding requests are cancelled when another source identifies the comic; stale archive requests are discarded before uploading.

Automatic browser cover search is available through `browser_search.enabled`. The independent supervised worker uses Playwright and installed Microsoft Edge (`channel: "msedge"`), with a dedicated profile under `data/lens-profile`. Normal searches run in the background. Only the first archive image is uploaded as a resized cover; archive filenames, folder paths and interior pages are not uploaded.

Searches are paced at least 30 seconds apart (60 by default), capped at 100 attempts per UTC day by default, and successful results are cached for 30 days. Changed archives are rejected. If Google requests human verification, use **Open browser verification** on the dashboard and complete it yourself in the dedicated window. The worker observes completion and resumes; it does not solve challenges or spoof fingerprints. Other metadata processing continues.

Optional `SERPAPI_API_KEY` enables the configured SerpApi fallback when browser search fails or yields no candidates. The app uploads a resized cover via SerpApi's Image API and uses its Lens API. All attempts count conservatively against the app's cap of at most 250 per UTC calendar month. The provider's billing period and usage outside this app may differ; stay on its free plan and leave paid renewal disabled. Candidate links pass through the ordinary identity and cover verifier; search matches alone never authorize writes.

## Writes and recovery

Use **Pause & release GPU** whenever you need the computer's resources, for games or other work. **Pausing** means the current operation is finishing; a comic write completes verification and backup cleanup before stopping. **Paused** means both workers have stopped processing. The dashboard separately confirms when Gemma has been unloaded from the GPU. Other applications and other Ollama models are unaffected.

The pause setting survives service restarts. Queues, completed writes, research evidence and folder progress are retained. **Resume processing** continues the saved queue and loads Gemma again only when needed. A partially completed batch skips its verified archives after checking that they have not changed. Manual processing actions are blocked while paused. This is a manual control, with no automatic game detection.

ZIP-backed CBZ archives receive metadata writes. Installed 7-Zip enables automatic conversion of CBR/CB7 and RAR/7-Zip containers named CBZ. Conversion checks original archive integrity, decodes comic images, and compares every extracted member's SHA-256 and size against the resulting ZIP before removing the original. A conflicting CBZ is never overwritten. Failed conversions retain originals; same-name replacement rolls back if final readback fails. Each folder pass converts at most one archive.

Existing populated fields are generally preserved; automatic correction of all existing fields is unfinished. Writes preserve page contents and verify the resulting XML and archive integrity. Verified automatic-write backups are removed; failed or interrupted writes retain recovery material. Unescaped ampersands in otherwise valid metadata XML are recovered when reading; later metadata writes serialize valid XML.

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

Tests cover archive preservation, safe writes, delta scans, matching rejection, quotas, encoding and worker supervision. Browser layout changes and human-verification challenges can interrupt free cover searches. Uncertain identities remain unresolved; source availability and coverage vary.
