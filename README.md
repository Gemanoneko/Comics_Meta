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

## Writes and recovery

Only ZIP-backed CBZ archives are rewritten. Other formats are inventoried without modification. Existing populated fields are generally preserved; automatic correction of all existing fields is unfinished. Writes preserve page contents and verify the resulting XML and archive integrity. Verified automatic-write backups are removed; failed or interrupted writes retain recovery material.

YACReader needs a **Rescan library for XML info** after metadata changes. The app does not directly edit YACReader's database.

`data/` contains the catalog, progress, evidence, quotas and queue. Keep it for continuity; this Git repository backs up code, not local library state. Never publish `.env` or `config.json`.

## Development

```powershell
python -m unittest discover -s tests -v
```

Tests cover archive preservation, safe writes, delta scans, matching rejection, quotas, encoding and worker supervision. General web research and autonomous reverse-image fallback remain incomplete. Human-verification challenges can interrupt free web searches. Uncertain identities remain unresolved; source availability and coverage vary.
