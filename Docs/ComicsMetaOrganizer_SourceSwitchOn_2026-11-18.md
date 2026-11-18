# Comics Meta Organizer - source switch-on, live measurement (Ender, 2026-11-18)

Sergei's ruling: switch on both "ComicVine search" and VerseDB (VerseDB for now without a dashboard credit). The
v0.6.5 code review (Senua, Performance, S3) asked for real pass time and worker share on the real machine before a
switch goes on; Ender's 65% free-worker figure came from a simulated clock. This is that reading, taken before and
after the switch on Sergei's PC. Times are local (+0200).

**Verdict: keep.** No clear harm of the kind S3 describes. The switch stays on.

## App and version

- First check (11:20): the running app was **0.6.3** (`resources\engine\VERSION`, `app.asar` package version; no
  `comicvine_search.py`/`versedb.py`); the 0.6.5 installer sat in the updater's `pending\` folder. Stopped and reported.
- Sergei quit and restarted the app at 11:24:29. Re-check: `resources\engine\VERSION` = `0.6.5`, `app.asar`
  package version `0.6.5`, `comicvine_search.py` and `versedb.py` present. Measured from 11:57:59.

## Config change

Live `%LOCALAPPDATA%\ComicsMeta\config.json`, 12:58:08. One key added inside `"sources"`, after `"disabled"`;
everything else byte-identical (CRLF kept; verified by parsing both versions and comparing with `enabled` removed).
Written atomically (temp file in the same folder + `os.replace`).

```
    "disabled": [
      ...
      "Image Comics"
    ],
    "enabled": [
      "ComicVine search",
      "VerseDB"
    ]
```

Names are `pipeline_config.OPT_IN_SOURCES` exactly. Backup of the previous file (643 bytes, sha256 `6daaf6aa...3521`):
`%LOCALAPPDATA%\ComicsMeta\config.json.pre-sources-20261118`. New file: 713 bytes, sha256 `88c4e627...becf`.

## Picked up without a restart

Yes. `app.load_config` reads the file on every call (no cache) and `pipeline_config.source_enabled` is asked per comic;
`search_fingerprint` is keyed on the file's mtime and size. Observed: switch 12:58:08; first `ComicVine search` and
`VerseDB` stage calls 12:58:13; first name-search request 12:58:56; first VerseDB request 12:59:07; both status files
(`comicvine-search-status.json`, `versedb-status.json`) created and `available` by 12:59:11. VerseDB's credential is
present (it made requests); `.env` was not opened.

## Before / after

Two consecutive 60-minute windows: before 11:57:59-12:57:59, after 12:58:11-13:58:12.

| Metric | Before | After | Method |
|---|---|---|---|
| Passes in the hour | 255 | 144 | `stage_metrics` "Research pass" calls, end minus start (the app times every `automatic.discover` with `research_runtime.timed`) |
| Pass time mean / median / p90 | 9.5 / 5.4 / 19.2 s | 19.1 / 7.0 / 47.3 s | Each pass's own seconds: "Research pass" row read every 2 s; every pass landed alone in a sample (0 multi-pass samples), so each delta is one pass's monotonic time |
| Longest pass | 189.6 s (no fallback) | 108.0 s | Same per-pass deltas |
| Passes over 60 s / over 120 s | 2 / 1 | 9 / 0 | Same per-pass deltas |
| Passes that asked a fallback | - | 137 of 144; median 8.1 s, max 108.0 s | A pass is counted when the "ComicVine search" or "VerseDB" stage moved since the previous pass ended |
| Most fallback time in one pass | - | 43.6 s | Sum of both fallback stages' seconds between two pass ends. The 30 s budget caps pacing waits only; requests and cover downloads (3 s spacing) come on top |
| Worker share in passes | 67.3% | 76.4% | "Research pass" seconds / wall time |
| Worker share in write cycles | 0.0% (0 cycles) | 7.6% (22 cycles, 273 s) | "Archive write and verification" seconds / wall time |
| Worker free (neither) | 32.7% | 16.0% | 100% minus the two rows above. Includes folder selection between passes, which is busy work, not idle |
| Fallbacks' share of wall time | - | 36.4% (name search 22.2%, VerseDB 14.2%) | Stage seconds / wall time. That is 47.6% of all pass time |
| Metron's share of wall time | 24.9% (642 calls) | 10.0% (326 calls) | "Metron" stage. The comic mix changed: the switch woke comics whose Metron retry was not due, so Metron was not asked for them |
| Research checks per hour | 685 | 586 (-14.5%) | `throughput_buckets`, full minutes inside the window, scaled to an hour |
| Comics queued / written | 0 / 0 | 26 / 23 (26 history rows) | `throughput_buckets.queued`; `history` rows timestamped inside the window |
| Fallback calls and deferrals | - | name search 535 calls, 86 deferred; VerseDB 448 calls, 47 deferred | Stage calls / errors (`ProviderDeferred`, pacing included, counts as a stage error) |
| 60 s revisits (S3 pacing) | - | at window end 60 comics wait on name-search pacing, 34 on VerseDB pacing; about 1.1 calls per comic | `discovery_records`: `provider_waits.<source>.pacing`; calls / comics with an answer recorded (486 name search, 426 VerseDB) |
| ComicVine name-search requests | 0 | search 94, issues 82, issue 12 (own limits 150/150/15; both paths 190 per resource) | `comicvine_requests`, every row seen across 30 s snapshots, peak rolling hour |
| ComicVine ID path / cooldown | 0 requests, no cooldown | 0 requests, no cooldown | `api_requests` and `comicvine_requests` origin; `api_state.blocked_until` (last set 2026-10-14) never ahead of the sample time |
| VerseDB requests | 0 | 128 (limit 280 an hour) | `versedb_requests`, as above |
| Pass errors | 0 | 0 | "Research pass" errors |
| Worker phases (5 s samples of `progress.json`) | lookup 62.9%, advancing to next folder 32.4%, inventory 3.3% | lookup 75.3%, advancing 14.7%, writing 7.5%, folder complete 1.9% | Phase share of samples |

Harm criteria fixed before the after-window data was read: fallbacks above 50% of wall time; fallback passes several
times the baseline's longest (190 s); checks per hour down by more than half; a ComicVine cooldown or a refused ID-path
request; any pass error. None was met.

Compared with Ender's simulation (longest pass 37 s with 30 s asleep, worker 65% free): live passes are longer
because they also hold Metron, GCD offline and publisher research for up to 20 comics. The fallbacks' own time per
pass stayed bounded (43.6 s at most), and there was no repeat of the 696 s inline sleep from before S3. Free worker
time fell from 32.7% to 16.0%, and checks per hour fell 14.5%. Writes went from none to 23 comics.

## Matches the new sources wrote (all 23 planned entries were written)

ComicVine name search, 13 (rule: year 8, unnumbered 4, folder_year 1):
Batman - Shadows of the Bat - House of Gotham (2022) -> House of Gotham #1 (962467); Jungle Fantasy 001 -> #1 2002 (118967);
DC Sneak Peek - Catwoman (2015) -> #1 (489247); Jungle Fantasy - Ivory 005, 008 (569396, 591796); Jungle Fantasy -
Secrets 001-004 (677401, 680659, 690735, 694957); Jungle Fantasy - Survivors 003 (612093); Gotham City Sirens - Trigger
Happy (2025) -> #1 (1123518); Lobo-Deadman - The Brave and the Bald 001 (1995) (241003); Nubia - Queen of the Amazons
(2022) -> #1 (976752).

VerseDB, 10 (rule: year 10):
Immortal Legend Batman 005 (2026) -> #5 2025 (450981); Batman - Justice Buster 001, 002 (2023) (423751, 423752);
The Bat-Man - Second Knight 002 (2025) (83861); Batgirl and the Birds of Prey - Rebirth 01 (2016) (223689);
JSA 001 (2025) -> 2024 (433261); JSA 002 (2025) -> 2024 (433262); JSA 014 (2026) -> 2025 (69444);
Mr. Terrific - Year One 006 (2026) -> 2025 (451031); Poison Ivy 2025 Annual 001 (2026) -> 2025 (85994).

Flag only, not judged: in 6 of the 10 VerseDB writes, the year in the file name is one later than the matched year.
The matched year is the comic's existing ComicInfo Year, which was not among the updated fields, so the year rule worked
as designed. All six got Title and Web; four of them also got Day and Publisher, and three got Number. Whether the filename year or
the ComicInfo year is right is for Futaba and Sergei to decide. I did not check correctness: Futaba's sample is the
correctness gate.

## Method notes

- Every reading was read-only: the catalog was opened with `?mode=ro`, and the JSON state files were only read. No code
  changes, no git, no UI interaction, no restart.
- The windows ran one after the other, not side by side. The comic mix differs between them, because the switch woke
  comics newly searchable by VerseDB. A pass is counted in the window where it ended, so each window edge can be off by
  up to one pass.
- 3 of 1,362 phase reads failed with `PermissionError` when they landed on the app's atomic replace of `progress.json`.
  Those were my reads failing. The app's save waits for a reader in that case, and no app error followed.
- Scratch (`I:/AI Projects/Temp/cmo-switchon/`) was removed afterwards. Only the config backup was kept, moved into the
  live-state folder.

## Futaba check (2026-11-18, read-only, taken at about 14:15)

**Futaba check - VerseDB and ComicVine name search safe to leave on: YES.** All 23 writes are the right series and
issue, and the right cover. No wrong write found, nothing undone, nothing touched. Pattern alerts: none.

### The 6 year-off-by-one files: right matches, cover date versus on-sale date

In all six the file-name year is the **cover-date** year, and the ComicInfo Year the file already carried is the
**on-sale** year. VerseDB and GCD agree on both dates:

| File | File-name year | VerseDB on-sale / cover date | GCD on-sale / cover date | ComicInfo Year the file already had |
|---|---|---|---|---|
| Immortal Legend Batman 005 | 2026 | 24 Dec 2025 / Feb 2026 | 2025-12-24 / 2026-02 | 2025-12-24 |
| JSA 001 | 2025 | 6 Nov 2024 / Jan 2025 | 2024-11-06 / 2025-01 | 2024-11 |
| JSA 002 | 2025 | 4 Dec 2024 / Feb 2025 | 2024-12-04 / 2025-02 | 2024-12 |
| JSA 014 | 2026 | 3 Dec 2025 / Feb 2026 | 2025-12-03 / 2026-02 | 2025-12-03 (exact day, from the release's own ComicInfo) |
| Mr. Terrific - Year One 006 | 2026 | 12 Nov 2025 / Jan 2026 | 2025-11-12 / 2026-01 | 2025-11 |
| Poison Ivy 2025 Annual 001 | 2026 | 12 Nov 2025 / Jan 2026 | 2025-11-12 / 2026-01 | 2025-11 |

Why the code accepted them: `versedb.py` `issue_year_fits` takes the file's year if it equals the cover year or the
release year. Ender's reading ("matched year is the existing ComicInfo Year") is half right: the existing Year is the
release year, and the filename year matched the cover year. Same convention split inside the untouched siblings of the
same folder (JSA 003-012: ComicInfo month is the on-sale month, file name is the cover year; JSA 013: ComicInfo is the
cover month). So the library already mixes both; the app did not create the mismatch. Neither year is wrong. Which
one Sergei wants in the ComicInfo Year is his call (question 1 below).

One related case Ender did not flag, opposite direction: The Bat-Man - Second Knight 002. File name 2025 (on-sale
17 Dec 2025), but the file had no date, so VerseDB's cover date was written: 2026-02-01. Right match, and the Year now
reads one later than the name.

### All 23 writes

Verdict key: right = same series, same issue, same cover. Covers compared side by side; "dhash" is a 256-bit
fingerprint distance (0 = identical image, under about 30 = same art; the larger values are the file's own crop,
"DIGITAL" badge or missing price box). Written date is what the ledger says the app wrote; fields not listed were
left as they were.

| # | File (shortened) | Source | Written series / issue / date | Verdict | Evidence |
|---|---|---|---|---|---|
| 1 | Immortal Legend Batman 005 (2026) | VerseDB 450981 | Immortal Legend Batman #5, Title "Chapter 5"; date untouched (2025-12-24) | right | Cover same (dhash 8). GCD #5 on-sale 2025-12-24, cover 2026-02, barcode 76194138936300511 |
| 2 | Batman - Justice Buster 001 (2023) | VerseDB 423751 | Batman: Justice Buster #1 "Chapter One: The Boy Makes a Vow", 2023-09-01 | right | Cover same (4), printed "CHAPTER ONE". File is 44 pages: one digital chapter, the level VerseDB lists (GCD lists only the 200-page volumes). VerseDB cover date Sep 2023 |
| 3 | Batman - Justice Buster 002 (2023) | VerseDB 423752 | #2 "Chapter Two", 2023-10-01 | right | Cover same (3), printed "CHAPTER TWO", 36 pages. VerseDB cover date Oct 2023 |
| 4 | The Bat-Man - Second Knight 002 (2025) | VerseDB 83861 | The Bat-Man: Second Knight #2 "Book Two", 2026-02-01 | right | Cover same, "Book Two" (22; file has a 17+ box). GCD #2 cover 2026-02, on-sale 2025-12-17 |
| 5 | Batgirl and the Birds of Prey - Rebirth 01 (2016) | VerseDB 223689 | Batgirl & the Birds of Prey: Rebirth #1 "Who Is Oracle? Chapter One", 2016-09-01 | right | Cover same (3). GCD one-shot, cover 2016-09, on-sale 2016-07-20 |
| 6 | JSA 001 (2025) | VerseDB 433261 | JSA #1 "Ragnarok, Part One"; Day 01 added to existing 2024-11 | right | Cover same (8). GCD JSA (2025) #1, see table above |
| 7 | JSA 002 (2025) | VerseDB 433262 | JSA #2 "Ragnarok, Part Two"; Day 01 added to existing 2024-12 | right | Cover same (4). GCD #2 |
| 8 | JSA 014 (2026) | VerseDB 69444 | JSA #14 "Year One: Chapter Two"; date untouched (2025-12-03) | right | Cover same art (8). The file's own ComicInfo day (3 Dec 2025) equals GCD on-sale exactly. VerseDB's low-resolution image shows "13" in the issue box, but its barcode reads ...01411 = #14 and equals GCD's #14 barcode 76194138522801411. A VerseDB image quirk, not a CMO fault |
| 9 | Mr. Terrific - Year One 006 (2026) | VerseDB 451031 | Mr. Terrific: Year One #6 "The Harder They Fall"; Day 01 added to existing 2025-11 | right | Cover same art, box "6" (14). GCD #6 |
| 10 | Poison Ivy 2025 Annual 001 (2026) | VerseDB 85994 | Poison Ivy 2025 Annual #1 "Lake, Maiden, Sword"; Day 01 added to existing 2025-11 | right | Cover same (9), "Once Upon a Time...". VerseDB's slug has no series name, but the page is Poison Ivy 2025 Annual (2026) #1. GCD has the same series and date |
| 11 | Batman - Shadows of the Bat - House of Gotham (2022) | ComicVine 962467 | Batman: Shadows of the Bat: House of Gotham #1 "HC", 2022-12-31 | right | Cover identical (0). 151 pages = the collected book (GCD 152). CV store date 2022-12-27 = GCD on-sale |
| 12 | Jungle Fantasy 001 | ComicVine 118967 | Jungle Fantasy #1 "Maternal Instinct; The Slavers of Cordo", 2003-01-01 | right | Cover same (2), printed "Issue 1". GCD Jungle Fantasy (2003) #1, key date 2003-01. Folder says (2002); GCD dates #1 at Jan 2003 and also lists a 2002 Preview one-shot |
| 13 | DC Sneak Peek - Catwoman (2015) | ComicVine 489247 | DC Sneak Peek: Catwoman #1, 2015-05-20 | right (one source) | Cover same (8), "SNEAK PEEK .15", 12-page promo. GCD offline does not index this series, so identity rests on ComicVine plus the cover |
| 14 | Jungle Fantasy - Ivory 005 (2016) | ComicVine 569396 | Jungle Fantasy: Ivory #5, 2016-12-31 | right | Same art, "#5", credits Ortiz/Urdinola (26: DIGITAL badge versus price box). GCD Ivory (2016-17), 8 issues |
| 15 | Jungle Fantasy - Ivory 008 (2017) | ComicVine 591796 | Ivory #8, 2017-04-30 | right | Same art, "#8" (27). GCD Ivory has #8 |
| 16 | Jungle Fantasy - Secrets 001 (2018) | ComicVine 677401 | Jungle Fantasy: Secrets #1, 2018-06-01 | right | Same art, "#1" (26). GCD Secrets (2018), 5 issues |
| 17 | Jungle Fantasy - Secrets 002 (2018) | ComicVine 680659 | Secrets #2, 2018-07-01 | right | Same art, "#2" (22) |
| 18 | Jungle Fantasy - Secrets 003 (2018) | ComicVine 690735 | Secrets #3, 2018-09-01 | right | Same art, "#3" (32; the file is a 600 dpi scan) |
| 19 | Jungle Fantasy - Secrets 004 (2018) | ComicVine 694957 | Secrets #4, 2018-11-01 | right | Same art, "#4" (13) |
| 20 | Jungle Fantasy - Survivors 003 (2017) | ComicVine 612093 | Jungle Fantasy: Survivors #3 "Fauna: Lorelei; Ivory; Vixens; Faune: Lost Tales", 2017-07-31 | right | Same art, "#3", Silva/Urdinola (30). GCD Survivors (2017-18), 10 issues |
| 21 | Gotham City Sirens - Trigger Happy (2025) | ComicVine 1123518 | Gotham City Sirens: Trigger Happy #1 "TPB", 2025-03-01 | right | Same cover (25: file crop). 142 pages. GCD on-sale 2025-03-11 = CV store date. GCD holds two records (two ISBNs) for the same title and date, so either edition is the same book |
| 22 | Lobo-Deadman - The Brave and the Bald 001 (1995) | ComicVine 241003 | Lobo/Deadman: The Brave And The Bald #1 "[Untitled]", 1995-02-01 | right, with a write-path note | Same art (16). GCD one-shot, cover 1995-02, on-sale 1995-01-12 = CV. See finding 1 |
| 23 | Nubia - Queen of the Amazons (2022) | ComicVine 976752 (ledger source blank; id from the app's cache) | Nubia: Queen of the Amazons #1 "HC", 2022-12-01; Web kept as the existing Amazon link | right | Cover identical (1). 156 pages = the collected book (GCD 160 pages, on-sale 2022-12-20 = CV store date), not issue #1 of the 4-issue miniseries |

Every ledger write (all 26 history rows) matches the file's current root ComicInfo, field by field; Lobo-Deadman
matches on its root copy (finding 1). Every file's modification time equals its history time. All 23 archives open and
list cleanly (I did not run a full integrity test).

### Findings (Futaba flags, does not fix)

1. **Minor - Lobo-Deadman now holds two ComicInfo.xml.** The 2020 archive already had one inside a subfolder
   (`Lobo-Deadman ... 001 (1995)/ComicInfo.xml`, a Comixology scrape with Summary, Genre, Volume, Notes). The app
   wrote a second, root-level `ComicInfo.xml` at 13:45:38 that has none of those fields. The app and standard readers
   read the root one, so Sergei sees the new data; nothing is lost, but a tool that takes the first `ComicInfo.xml`
   it finds will show the old one, and the Summary exists only in the nested copy. It is the only one of the 23 with
   this layout, and it is the write path, not a new-source problem. Repro: open the .cbz listing of that file and
   search for `ComicInfo.xml`. Status: open, left as is. For Ender and Sergei to decide (question 2).
2. **Minor - Day 01 added to an existing on-sale Year/Month.** For JSA 001, JSA 002, Mr. Terrific 006 and Poison Ivy
   Annual 001, VerseDB's month-only cover date supplied Day 01. The result reads 2024-11-01 where the real on-sale day
   was 6 Nov and the cover date is Jan 2025. Harmless in practice: the untouched JSA 003-013 in the same folder already
   carry Day 01. Status: noted, no action needed unless Sergei wants exact days.
3. **Minor, cosmetic - Title field holds the format label.** Collected editions got Title "HC" (House of Gotham,
   Nubia), "TPB" (Gotham City Sirens), and Lobo-Deadman "[Untitled]". That is ComicVine's own issue name, correctly
   copied. Status: noted.

### Questions for Sergei

1. ComicInfo Year for DC comics: on-sale year (what these Pyrate releases carry, and what the app left alone) or
   cover-date year (what ComicVine and GCD use, and what the app writes when the file has no date)? Today it is both.
2. Lobo-Deadman: leave the two ComicInfo files, or have Ender look at how the writer treats nested ComicInfo?

### How this was checked, and its limits

- **Read-only.** The catalog was opened `mode=ro` with `query_only`; the GCD index with `immutable=1`; the comics
  with a read-only zip reader. Nothing written to Y:, `config.json`, the catalog or the app; the app was not stopped
  or restarted; no mouse or focus use; `.env` not opened; no token printed. Python was a copy of the bundled runtime,
  run with `-B -I`.
- **Independent sources.** ComicVine, GCD and Metron web pages are blocked from this PC (Cloudflare 403 or bot
  check), and I did not drive a browser (focus rule). Substitutes: (a) GCD's data through the app's offline index
  (dump 2026-10-16): independent of VerseDB and ComicVine, but it is a local copy, not the live GCD page; (b) the
  public VerseDB pages (no login, no API key, so no use of Sergei's credit or limit); (c) ComicVine's cover images from
  its image server, using the image addresses found in the app's cached ComicVine answers (addresses only, no key).
  GCD has no dates for the Jungle Fantasy online issues and no Sneak Peek series, so those 10 rest on series and issue
  count (GCD), ComicVine, and the cover art with its printed issue number.
- **Not covered.** Four more writes landed after the report's window (14:04-14:10: Kong - King of Skull Island 01, 03,
  05, and Superman vs. Meshi 001). I did not check them. Want me to?
- Scratch `I:/AI Projects/Temp/futaba-versedb-check/` (copied Python, covers, page copies) removed at the end. No helper
  processes were started.
