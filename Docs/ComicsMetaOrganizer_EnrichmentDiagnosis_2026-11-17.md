# Comics Meta Organizer — Enrichment Diagnosis (2026-11-17)

Ender, read-only diagnosis of the installed 0.6.3 app (repo `main` @ bc261f4) against one snapshot of the live state. No code, config or live data was changed, no source API was called, and the app was not paused or restarted.

## Summary for Sergei

1. **Nothing broke. A one-off catch-up ended.** Version 0.6.1 (installed 11-10 18:01) changed the matching-rules version for Metron and GCD. That makes the app ask once more about every comic it had failed on, which is by design. That re-ask wrote 2,713 comics on 11-11 to 11-13. About 700 of them were newly identified; the rest were summaries and extra fields. By the morning of 11-13 it had been through the whole list.
2. **The same happened before.** The 0.5.0/0.6.0 catch-up wrote 1,400–4,800 comics a day from 10-27 to 11-04. On 11-05 it fell to 3–22 newly identified comics a day.
3. **The fall looked worse because of an outage.** On 11-13 at about 15:00, three status files were found filled with zero bytes and the app could not start until the 0.6.2 fix on 11-14 at about 21:00. When it came back, it checked about 1,100 comics an hour, as fast as during the catch-up, but wrote 0–5 an hour. The work it could do was already done.
4. **What is left is hard for the current rules.** 16,818 comics have no identification from Metron, GCD or ComicVine:
   - 58% cannot be searched on Metron at all (no year, or no number).
   - 30% have no Metron series under that name.
   - The cover check, the big blocker last time, now rejects only about 140.
   - Every one of them was asked again under today's rules on 11-10 or 11-11.
5. **Steady state without changes: about 5–15 newly identified comics a day.** That is new comics arriving (56–128 a week) plus Metron adding issues.
6. **Getting more needs looser rules or new data.** Four changes are worth doing; together they might add roughly 350–1,150 comics once. Two of them (a newer GCD file, and Metron name spellings) carry little or no extra risk. Two of them loosen a matching rule and should be measured first. Six other loosenings were measured or checked and are not worth it.
7. **The app is about to re-ask everything again.** About 33,000 comics come due for Metron between today and 11-19, a week after the 11-10 re-ask. Metron allows 5,000 requests a day, so this will take several days and write almost nothing. It costs no writes today, but it delays new comics, and it would delay the gains from any rule change.

## Data and method

- **Snapshot:** online backup of `catalog.sqlite` through a read-only `mode=ro` connection at 2026-11-17 18:58 local. It took 1.3 s and passed `quick_check`. `folders.json` was copied at 19:07.
- **Read-only files read in place:** `config.json`, the provider status files (`metron-`, `comicvine-`, `gcd-`, `google_books-status.json`), `progress.json`, `progress-history.jsonl`, `maintenance.json`, `browser-search.json`, `gcd-offline/current.json`, `logs/desktop.log`, `logs/engine.log`, the update-attempt receipts, the queue ticket states, and every batch `plan.json`/`results.json` since 10-20 (29,200 written entries). `.env` was not opened.
- **Live trace:** `progress.json` was read every 3 s for 7 minutes (19:13–19:20), read-only.
- **Comics written per day:** distinct comics per local day in `history` (paths compared as `coverage_priority.path_key` does). This is what the dashboard's update statistics count.
- **Newly identified:** a batch plan entry, verified on read-back, whose write set the comic's first source link (`Web`) or its Series/Number. Everything else is an **other write**: summaries, extra fields, imprint and so on. These counts are plan entries, so a comic written twice in a day counts twice.
- **Checks and active minutes:** `throughput_buckets`. It covers only the last 7 days (from 11-10 18:58).
- **Metron API fetches:** `cache` rows by fetch day. The cache is size-capped and starts at 11-05 05:21. A URL fetched again keeps only its newest time, so earlier days undercount.
- **Research attempts per source:** each record's latest attempt per source, rebuilt as `next_at` minus the retry delay in `source_scheduling.record`. Only the newest attempt per comic survives, so older days undercount.
- **Identity replay:** copies of `research.query_identity`, `filename_identity`, `year_hints`, `metron.identity`, `name_variants`, `same_series`, `year_agrees` and `filename_identity.collection` (scratch only, no app module imported), run against the cached Metron answers.
- **Unresolved pool:** live comics, not excluded by language, whose ComicInfo `Web` or Notes cites none of Metron, GCD or ComicVine.

---

## 1. The slowdown, measured

| Day | Comics written | Newly identified | Other writes | Checks | Active min | Metron fetches | Event |
|---|---:|---:|---:|---:|---:|---:|---|
| 10-27 → 11-02 | 1,385–4,766 / day | 904–3,152 / day | 255–2,735 / day | — | — | — | 0.5.0 (10-27), 0.6.0 GCD offline (10-28) |
| 11-03 | 2,117 | 1,343 | 973 | — | — | — | |
| 11-04 | 1,697 | 739 | 1,142 | — | — | — | |
| 11-05 | 472 | 22 | 439 | — | — | 1,866 | catch-up over |
| 11-06 | 112 | 9 | 103 | — | — | 1,691 | |
| 11-07 | 407 | 21 | 387 | — | — | 2,609 | |
| 11-08 | 26 | 5 | 21 | — | — | 573 | |
| 11-09 | 17 | 3 | 14 | — | — | 2,751 | |
| 11-10 | 78 | 35 | 49 | 4,147 (from 18:58) | 295 | 1,594 | 0.6.1 installed 18:01 |
| 11-11 | **726** | **560** | 348 | 21,438 | 1,342 | 2,891 | re-ask under new rules |
| 11-12 | **1,097** | 123 | 1,490 | 15,855 | 958 | 4,761 | Metron's 5,000/day cap reached |
| 11-13 | **890** | 18 | 1,063 | 9,815 | 602 | 2,099 | list exhausted ~09:00; outage from ~15:00 |
| 11-14 | **5** | 0 | 5 | 3,032 | 161 | 375 | app back ~21:00; 0.6.3 at 21:57 |
| 11-15 | 15 | 12 | 3 | 3,818 | 408 | 477 | |
| 11-16 | 6 | 1 | 5 | 4,885 | 677 | 1,514 | |
| 11-17 (to 18:58) | 33 | 8 | 25 | 5,350 | 708 | 2,402 | weekly re-ask echo starts |

- **Where the "other writes" came from:** on 11-12 and 11-13, 1,486 of them were summaries the local model wrote from verified sources ("Synopsis composed from verified information"). The dashboard counts these the same way as new identifications, so a catch-up looks bigger than it is, and its end looks steeper.
- **When the drop started:** 11-13 at about 09:00 local. Writes per hour went from 117–196 (03:00–08:59) to 7–33 (09:00–14:59).
- **Outage:** no checks at all from 11-13 about 15:00 to 11-14 about 21:00.
- **Proof that the list was used up:** after the restart (11-14 21:00 to 11-15 00:59), the app checked 737–1,179 comics an hour, the same pace as the catch-up, and wrote 0–5 an hour.

**Research attempts per source** (newest attempt per comic, by day; Metron results in brackets: verified with new data / verified, nothing new / no match):

| Day | Metron | GCD offline | Image Comics catalog |
|---|---|---:|---:|
| 11-11 | 15,088 (46 / 2,009 / 13,033) | 18,464 | 6,327 |
| 11-12 | 7,458 (17 / 1,923 / 5,518) | 8,483 | 7,835 |
| 11-13 | 1,390 (2 / 819 / 569) | 1,158 | 6,760 |
| 11-14 | 593 (4 / 501 / 88) | 547 | 2,086 |
| 11-15 | 1,250 (7 / 756 / 478) | 957 | 2,401 |
| 11-16 | 2,239 (5 / 1,507 / 710) | 901 | 1,915 |
| 11-17 | 2,186 (3 / 1,304 / 872) | 362 | 2,522 |

Since 11-14, Metron finds something new for 3–7 comics a day out of 600–2,200 asked.

## 2. Why

### 2.1 Main cause: the 0.6.1 re-ask finished (confidence: high)

- **What 0.6.1 changed:** `metron.RULES_VERSION` went from 2 to 3 ("Corrected filename identities wake misses once"), and `gcd_offline.RULES` went from `gcd-offline-1` to `gcd-offline-2` (diff v0.6.0..v0.6.1). `source_scheduling.ready` and `due` re-ask any miss recorded under another stamp, once.
- **Evidence that it ran to the end:**
  - Of the 34,732 live records still marked `needs_identity_lookup`, 34,246 carry the current GCD stamp and 33,237 the current Metron stamp.
  - The newest Metron attempt for the unresolved comics falls on 11-10/11-11 for nearly all of them (table above).
- **Same shape as before:** the 0.5.0/0.6.0 catch-up ended on 11-05. New identifications fell from 739 (11-04) to 3–22 a day (11-05 → 11-09).

### 2.2 Not a regression

- **Releases:** 0.6.2 and 0.6.3 changed no matching or scheduling code. The engine diff v0.6.1..v0.6.3 covers the progress-file guard, status-file handling, the library lock and Lens verification; the rest is the icon, tray and release tooling.
- **Metron is available:** its status file reads `available`, with 2,155 of its rolling 5,000-per-day requests left at 18:57. The cap was hit in the 24 h from 11-12 08:53: 5,000 cache rows, the most in any 24 h since 11-05. The status file's numbers (2,843 fetched in the current window, 2,155 left) put the cap at about 4,998.
- **Nothing is stuck:**
  - no held comics;
  - 1 failed write;
  - the newest 38 queue tickets are `complete`;
  - no web requests since 10-13. "Searching the web" in the progress line is only a label shown before a switched-off step.

### 2.3 Contributing: the 11-13/14 outage (confidence: high)

- **What happened:** `progress.json`, `folders.json` and `browser-search.json` were found filled with zero bytes (`Docs/ComicsMetaOrganizer_StartupEvidence_2026-11-14.md`). The app could not start until 0.6.2. Sergei approved deleting the files at 11-14 21:12, and `folders.json` was rebuilt from empty: 8,182 folders, all due again.
- **Cost:** about 30 hours with no processing. Most of the catch-up was already over by then.
- **Open:** the cause of the zero-filled files is not known. If it happens again, the app stalls again.

### 2.4 Why checks are slower between catch-ups (confidence: medium)

- **The numbers:** checks per active minute were about 16 on 11-11 to 11-13 and about 7.5 on 11-15 to 11-17. Active minutes per hour fell from 55–60 to 25–45. Since 11-16 00:00, 69% of the time fell in gaps of 60 s or more between finished comics.
- **The backlog is real:** at the snapshot, 5,691 identified comics and 1,346 unresolved ones were past their Metron date, 3,214 of them by more than two days.
- **Most likely cause:** the work changed. On 11-15 to 11-17, most due comics were re-checks of identified comics (1,304 of 2,186 Metron attempts on 11-17 found nothing new). Each one costs a name search, an issue-detail request and cover downloads at Metron's 3.2 s spacing. Refinement also gets only every other folder turn.
  - The catch-up's checks were mostly cache hits and local GCD lookups.
  - The live trace (19:13–19:20, when the cheaper re-ask echo had started) showed 120 status changes in 417 s: about one comic every 3 s, a new folder every 3–60 s, and no pause longer than 9 s.
- **What I could not measure:** how the slow minutes split between Metron spacing, cover downloads and the local model. That needs a timing log per step.
- **What it costs in writes:** little today. The overdue comics are re-checks that write about 0.5% of the time.

### 2.5 The weekly echo (confidence: high)

- **Why it happens:** every unresolved comic was re-asked on 11-10/11, and misses wait 7 days (the cap in `source_scheduling.record`). So they all come due together.
- **Size:** Metron `next_at` falls on 11-17 for 10,704 comics (overdue included), on 11-18 for 15,498 and on 11-19 for 7,269. That is about 33,000 comics, identified and unresolved together.
- **Cost:** the 7-day Metron cache has just expired for these, so each Metron-searchable comic costs at least one fresh request against the 5,000-per-day cap. Without a change, the echo repeats every week.
- **Enrichment A's "unsearchable" skip no longer works:**
  - It was meant to stop these re-asks.
  - Since 0.6.0, GCD offline counts as able to search any comic with a series (`source_scheduling.can_search`), so almost no comic qualifies.
  - Only 1,348 records carry the marker, while 9,721 unresolved comics cannot be searched on Metron.

## 3. What is left

Unresolved pool: **16,818** comics.
- **By group:** 3,347 tagged from the comic itself only, 2,306 with ComicInfo from another tool, 11,165 bare.
- **For comparison:** externally identified comics went from 6,233 on 10-26 to 23,420.
- **Caveat:** about 1,016 of the pool are comics Metron verified but had nothing to add, because another tool already filled them. Their `Web` points elsewhere.
- **Method:** one reason per comic, from the identity replay against cached Metron answers. "Stage unknown" means the answer came from a cache row that has since been evicted; the app did ask on 11-10/11.

| Reason | Comics | Notes |
|---|---:|---|
| Numbered, **no year** in name or folder | 4,389 | B3 (yearless) territory. Top: !Dark Horse 858, Star Wars 746, !BD 662. Metron already lists the series name for ≥ 831 |
| **No number, no year** | 3,072 | Chapters, variant packs, magazines. No rule fixes these |
| No number, has a year, but the name has a digit, "v01", "Book 2" and so on | 2,260 | 1,155 carry an explicit Vol/vN/Book label |
| Metron has **no series by that name** (that year) | 4,965 | ≥ 330 reach a Metron series with a spelling change (§4) |
| Stage unknown (evicted cache row) | 1,643 | Asked on 11-10/11; answer not kept |
| Series found, no issue with that number in that year | 338 | Mostly 2025–26 issues Metron has not listed yet |
| One candidate, **cover rejected** | 138 | Was 1,998 on 10-26; the 0.5.0 comparison took most of them |
| Several candidates | 13 | |

- **GCD offline** has already said no to 16,381 of these under its current rules. 421 have no GCD attempt recorded.
- **Recent comics:** 1,102 of them are dated 2025 or 2026.
- **The active GCD file** is from 2026-10-16, 32 days old. Your reminder was set at 14 days.

## 4. Options

Gains are one-off estimates for the pool above, not promises. "Loosens a rule" marks changes that accept a match the current rules refuse.

| # | Option | Loosens a rule? | Reach | Expected gain | Precision risk (method) | Effort | Undo by config? |
|---|---|---|---:|---:|---|---|---|
| 1 | **Load a newer GCD file.** You download it; the app builds the index and asks again once | No | 1,102 comics from 2025–26, plus every GCD miss asked once | 50–300 (not measured) | Same rules as now: Futaba's pilot sample had 2 wrong of 200 (1.0%; at most 3.1%) | S, no build | Mostly: keep the old ZIP to rebuild |
| 2 | **Metron spellings:** leading "The", "&"/"and", a trailing "(2021)" or "vN" in the Series. The identity checks stay the same | Spelling only | ≥ 330 | 100–250 | Low. A single candidate with the same number, year and cover is still required. It can be measured on identified comics before release | S | Yes (new `matching` switch) |
| 3 | **Metron collection label:** "Vol 2", "v01", "Book 3" plus a year → issue N of a series Metron types as TPB, Hardcover, Graphic Novel or Omnibus. Same idea as GCD's rule in 0.6.1 | **Yes** (C) | 1,155 | 100–300 (rule C writes about 20% of its pool) | Not measured for Metron. Same gates as rule C (10/10 candidates right, 403/416 tagged unnumbered books are issue 1) plus the label's number. Needs a pilot: about 300 comics, about 600 Metron requests, and a Futaba sample | M | Yes (new switch) |
| 4 | **B3 yearless, re-opened only through a measurement:** search series and number in every year; accept one candidate whose cover agrees | **Yes** (B) | 4,389 (≥ 831 with a series name Metron lists) | 100–300 | Rejected 10-26 at 57–85%, but that was the candidate stage only. With the cover stage: 0 of 130 "same name and number, other run" pairs passed the cover check (95% upper bound about 2.3%), which gives an **estimated** 98.2–99.6% worst case. Not measured: reprints can share covers. Pilot: about 500 identified comics with the year hidden, through the full cover stage, about 1,000 Metron requests plus cover downloads | S (switch exists) + M (pilot) | Yes (`matching.yearless`) |
| 5 | **Spread the weekly re-asks and slow down old misses:** add random spread to retry times; after 6 misses under the same rules wait 30 days; treat a GCD-offline miss under the same index and rules as final (this restores Enrichment A) | No | About 33,000 re-asks a week | About 0 directly. It frees Metron's 5,000 a day and pass time for new comics and for options 2–4. Metron additions would reach old misses up to 3 weeks later | None: a file, rules or index change still wakes everything | M | Partly (needs code; the delays can be config values) |
| 6 | **Switch off the Image Comics catalog** | No | — | 0. Removes 1,900–2,500 Image attempts a day (11-15 to 11-17); 2,328 comics since 11-16 were re-checked by Image alone. Also removes its 300 requests a day. It can search only 2,654 of the 35,612 comics it has a schedule for | None: 1 history row ever, 14 comics cite it | S (`sources.disabled`) | Yes |

**Measured or checked, not worth it:**

| Idea | Reach | Why not (method) |
|---|---:|---|
| Read a number followed by " - subtitle" ("Captain's Log 002 - Harriman") | 369 | Right on **1 of 6** identified comics with this pattern. "Lone Wolf 2100" and "Evil Dead 2" are titles, and Metron files "Captain's Log: Harriman" as its own #1 |
| Drop the subtitle to reach the main series ("Lady Death - Abandon All Hope" → "Lady Death") | 470 | A mini-series is its own Metron series. Only the cover check would stop a wrong match |
| Allow the year to be off by one | ≤ 590 | On 14,937 identified comics the filename "(YYYY)" equals the verified year 98.8% of the time (±1: 0.6%). Little to gain, and same-name relaunches in back-to-back years add risk |
| Looser cover thresholds | ~140 | Small reach. Re-measuring needs Metron cover downloads for a labelled set |
| Treat digits in a title as unnumbered ("Spider-Man 2099", "78 MPH") | 420 | No safe way to tell a title from a number |
| Re-measure B3 without the cover stage | — | Already done on 10-26 (57–85%). Only option 4's full-stage measurement adds anything |

**A new source, not a rule:** the 10-26 report's item 6, a read-only ComicVine name-search pilot, is still undecided. It is the only lever on the 4,965 comics Metron has no series for and on the Dark Horse, Star Wars and Conan comics with no year. Gain unknown.

## 5. Recommendation

1. **Now, no build:**
   - load a newer GCD file (option 1);
   - switch off the Image Comics catalog (option 6).
2. **One batch, each piece behind a switch:**
   - options 2 and 3, each first as a read-only "would write" list with a Futaba sample before writes start, the way the GCD pilot ran;
   - option 5 in the same batch, so the re-ask that 2 and 3 trigger does not turn into another weekly echo.
3. **B3:** run option 4's pilot. Switch it on only if the measured precision is near the 99% you accepted for GCD.
4. **Expect:** a one-off of roughly 350–1,150 comics from options 1–4, then about 5–15 newly identified comics a day. More than that needs a new source.

## Unknowns and what each needs

- **Precision of options 3 and 4:** needs Metron requests, about 1,600 in all (a third of one day's cap), plus cover downloads, with your OK. Not run under this brief.
- **Gain of option 1:** needs the newer GCD file.
- **Where the slow minutes go between catch-ups:** needs a timing log per step.
- **Why the three status files were zero-filled on 11-13:** not investigated here.
- **Library size:** the catalog holds 40,610 rows (40,403 live). The 10-26 question of whether about 60,000 comics exist and some never reach the catalog is still open. The 6-hour inventory walk reports 0 errors over 8,857 directories.
