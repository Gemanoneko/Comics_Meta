# Comics Meta Organizer — GCD data dump trial (2026-10-26)

Ender, read-only trial of Sergei's GCD download as an offline match index. Code at `main` @ 7bcd05c. No repo code, comics or catalog were changed. No request went to comics.org.

## Summary for Sergei

1. The GCD file works offline: a 1–2 minute build makes a local index of about 0.4 GB that answers in under 1 ms, with no daily limit.
2. It finds exactly one matching issue for about 13,000 of the 30,085 unmatched comics: 5,600 by series, number and year, 4,700 with no year, and 2,600 with no number.
3. Checked against comics that are already verified, it picks the right issue 999 times in 1,000 when the year is known. Without a year, 8–57 in 1,000 are the wrong issue.
4. The file has no cover pictures. The app's rule that every GCD write needs a cover check cannot be met offline. You would either accept the match itself, or keep an online cover check, which has never passed so far.
5. Recommendation: pilot it. Read-only first, then series+number+year writes if you allow them.

---

## 1. The dump

| | |
|---|---|
| Format | **SQLite 3** (`SQLite format 3` header). One file in the zip: `2026-10-16.db`. No MySQL, so no conversion was needed |
| Size | zip 1,889,156,789 bytes; unzipped **6,751,043,584 bytes (6.75 GB)**; unzip took 34 s |
| Dump date | **2026-10-16** (the file name inside the zip; the newest `modified` timestamp in `gcd_issue`/`gcd_series` is 2026-10-16 21:58:09) |
| Contents | 233,635 series; 2,622,121 issue rows, of which 254,282 are variant covers; 4.57 M stories; 12.1 M story credits. English: 109,719 series, 691,974 issues that are not variants |
| Covers | **None.** No image table, no cover id and no cover URL. The online API's cover URL uses a cover id (`covers_by_id/1683/w400/1683832.jpg` for issue 2603206, from the app's own cache) that the dump does not carry. Only the flags `series.has_gallery` and `issue.variant_cover_status` exist |
| Licence file | None in the zip. Licence terms are from Makoto's notes (CC BY-SA 4.0), not re-checked here |

Sergei's `current.zip` was only read. It was not changed, moved or deleted.

## 2. Data and method

- **Catalog snapshot:** a SQLite online backup through a `mode=ro` connection to `%LOCALAPPDATA%\ComicsMeta\data\catalog.sqlite`, written to scratch. Taken 2026-10-26 23:48:23, 0.73 s, 205,586,432 bytes, `quick_check` ok. No other file there was opened.
- **Pool:** rebuilt with the diagnosis's rules, using copies of `query_identity`, `parse_name` columns, `language_eligible`, `path_key` and the Metron cache replay.
  - Groups match the diagnosis exactly: A 6,233 · B 10,529 · C 3,885 · D 3,981 · E 15,575 · X 4. **Pool B+D+E = 30,085.**
  - Reasons match for "no number" (9,777), "numbered, no year" (2,398 + 7,421) and every searchable row in D and E.
  - Two small differences:
    - Inside B's searchable rows, 355 comics moved from "no Metron answer" to answered. The app kept running between the two snapshots, which is the likely cause (not verified).
    - The diagnosis's "book format" regex was not recorded. Mine (`TPB|HC|GN|omnibus|Vol N`) gives 945 book and 8,832 other, against 1,293 and 8,484.
- **Index:** built from the dump into scratch (§5). The match ignores everything but English GCD series and drops variant-cover rows.
- **Match rules.** A "hit" means exactly one GCD issue. Two rule sets were run:
  - **Base:** exactly what the brief asked.
    - Series key (the app's `series_key`, compared against GCD's name or its article-free sort name, with a trailing `vN` also tried without it) plus number (`issue_number`) plus year (GCD key date, else on-sale date).
    - Without a year: the folder year must equal the series start year, or there is no year check at all.
    - Without a number: a one-issue series, an `[nn]` issue, or issue #1.
  - **Guarded:** the base rules plus four guards. They came from reviewing a first stratified draw, then were checked on a second, separate draw (below):
    - **G1.** A file named as a collection (TPB, HC, Collection, Omnibus…, or `v01`/`Vol 3`/`Book 2` without an issue number) matches only GCD collected-edition series, taking volume N as the number. A plain issue never matches a collected edition.
    - **G2.** An unnumbered file matches only a one-issue series or an `[nn]` issue, never #1 of a longer run.
    - **G3.** A `vN` series tail is dropped only when an issue or folder year is known. This stops `Venus Wars v2 05` from matching vol. 1 #5.
    - **G4.** A year written as `(2007-02)`, `(1993-Dark Horse)` or a bare year in the filename counts as the issue year.
  - The guarded rules are the ones a build would use.

## 3. Match rate (question 1)

### 3a. Stratified sample (as asked)

- **Draw:** 40 comics per diagnosis reason, or all 33 where fewer exist; seed 20261026; 353 comics.
- **Review:** every hit was checked by hand against the file name, folder and GCD record. "Wrong" means the wrong issue or edition. "Unsure" means it cannot be told from the name.

| Reason (diagnosis) | n | Base hits | Base wrong / unsure | Guarded hits | Guarded wrong / unsure |
|---|---:|---:|---:|---:|---:|
| Searchable — exactly one Metron candidate, rejected | 40 | 36 | 0 / 0 | 36 | 0 / 0 |
| Searchable — no Metron answer | 40 | 22 | 0 / 0 | 23 | 0 / 0 |
| Searchable — Metron has no such series that year | 40 | 15 | 0 / 0 | 15 | 0 / 0 |
| Searchable — series found, no such issue | 40 | 2 | 0 / 0 | 2 | 0 / 0 |
| Searchable — several Metron candidates | 33 | 20 | 1 / 2 | 30 | 0 / 2 |
| Numbered, no year — year in folder | 40 | 21 | 0 / 0 | 19 | 0 / 0 |
| Numbered, no year — none anywhere | 40 | 23 | 2 / 1 | 19 | 2 / 0 |
| No number — book format | 40 | 7 | 2 / 0 | 9 | 0 / 0 |
| No number — other | 40 | 6 | 0 / 0 | 8 | 0 / 0 |
| **Total** | **353** | **152** | **5 / 3** | **161** | **2 / 2** |

By class (guarded, sample):
- **Series + number + year: 106 of 193 (55%).**
- **Number but no year: 38 of 80 (48%).**
- **No number: 17 of 80 (21%).**

What the misses were:
- **Guarded, 2 wrong:** `The Walking Dead #035 [rus].cbz` and `#158 [rus]`. These are Russian files matched to the English issue. The app's language rule only catches `(rus)`-style tags in round brackets, so this is not a GCD error.
- **Guarded, 2 unsure:** two `(Dr.Vink)` files with no number in the name (`30 Days of Night - Return to Barrow (2004)`, `… Eben & Stella (2007)`). Their existing ComicInfo says #1, but they may be the collected editions.
- **Base wrong, fixed by the guards:**
  - `… Omnibus v03 (2019)` matched to Omnibus #1.
  - `Almost American (2021) (Fan-Made TPB)` matched to issue #1.
  - `Blade Runner 2019 v01 - Los Angeles` matched to issue #1.
- **First draw (used to design the guards):**
  - Collected volumes were matched to single issues (`Hillbilly v02`, `Coffin Bound v02`, `Red Sonja and Vampirella Meet Betty and Veronica v01`).
  - `Venus Wars v2 - 05` was matched to vol. 1.

### 3b. Whole pool (same rules, all 30,085)

| Class (pool size) | Base: one candidate | Guarded: one candidate | Guarded, how |
|---|---:|---:|---|
| Series + number + year (10,489) | 5,608 | **5,618 (54%)** | 5,536 issues + 82 collected volumes |
| Number, no year (9,819) | 4,881 | **4,738 (48%)** | 562 with a year from the filename (G4) · 823 with folder year = series start · 3,352 with no year at all · 1 volume |
| No number (9,777) | 2,286 | **2,616 (27%)** | 921 collected volumes · 1,364 one-shots/`[nn]` with a year · 331 with no year |
| **Total** | **12,775** | **12,972** | |

- By group (guarded): B 7,206 (already in-book; GCD would add year, credits, publisher), D 1,827, E 3,939 (bare comics).
- Of the 5,757 comics where **Metron has no such series that year**, GCD has a unique match for **2,104**.
- Of the 2,075 comics that **failed only Metron's cover check**, GCD names the same single issue for **1,861**.

## 4. Precision (question 2)

### Method

- **Truth sets:**
  - **T1:** 3,644 comics the app wrote from Metron (group A, Notes cite Metron, Series/Number/Year present). Metron verified series, number, year and cover.
  - **T2:** 4,333 other live comics whose ComicInfo `Web` is a ComicVine issue. These were tagged by other tools, or by the app through an embedded ID. Not verified by this app.
- **Input:** the **filename identity only** (catalog `series`/`number`/`year` from `parse_name`), as for an unmatched comic.
- **Agreement:** the GCD hit's series key (or sort key, or one containing the other), number and year are compared with the tag.
- **Independent cross-checks:** publisher (first significant word, imprint allowed), writer (any shared name) and cover month.
- **Stress tests:** the year is removed, the folder year replaces it, or the number is removed for books Metron/ComicVine call One-Shot/GN/TPB/HC.

### Results (guarded rules)

| Test | Found (per 1,000 asked) | Same series + issue + year (per 1,000 hits) | Wrong issue (per 1,000 hits) |
|---|---:|---:|---:|
| T1, as filed (series+number+year) | 3,353 of 3,644 (920) | **3,353 (1,000)**; zero errors, so ≥ 999.1 at 95% | 0 |
| T2, as filed | 2,579 of 4,333 (595) | **2,577 (999)**; the 2 others are the same issue (`Rose & Gunn` vs `Rose and Gunn`) | 0 |
| T1, year removed | 2,515 of 3,644 (690) | 2,410 (958) + GCD has no date 71 (28) + ±1 year 14 (6) | **20 (8)** |
| T2, year removed | 2,302 of 4,331 (531) | 1,921 (834) + no date 168 (73) + ±1 year 82 (36) | **131 (57)** |
| T1, folder year as series start | 844 of 1,266 (667) | 823 (975) + no date 18 + ±1 year 3 | **0** |
| T2, folder year as series start | 962 of 1,371 (702) | 880 (915) + no date 57 + ±1 year 13 | **12 (12)** |
| T1, number removed (whole books) | 115 of 139 | 114 (991) | 1 (9) |
| T2, number removed (whole books) | 94 of 339 | 87 (926) | 7 (74) |

What the rows mean:
- **"As filed" is close to a tautology on series, number and year.** The tag was matched on the same filename. What the row really proves is that GCD has no second same-name, same-number, same-year issue taking the place of the real one.
- **Cross-checks on T1 as filed:** publisher 970 per 1,000 (3,066/3,162), writer 920 (1,963/2,133), month equal 827, month within 2 months 995 (3,322/3,337).
  - I read 15 publisher and 15 writer mismatches. None was a different comic. They were imprint naming (`Acclaim / Valiant` vs `Valiant`, `Best Jackett Press` vs Dark Horse), name forms (`Steve Seagle` vs `Steven T. Seagle`, `Devin Grayson` vs `Devin K. Grayson`) or credit scope (anthology issues).
  - GCD's month is its key date, which differs from Metron's cover month by 1–2 months in about 17% of cases.
  - Barcodes (24 of 36 equal) are not a usable check: the mismatching ComicInfo GTINs are digital-store ids, not UPCs.
- **Wrong year without a year:** these are same-named series from other decades. Examples: `Fierce (2023, Europe Comics)` → `Fierce (2004, Dark Horse)`, `Brooklyn Dreams (2025, Dark Horse)` → `Brooklyn Dreams (1994, DC)`.
- **"No date" and "±1 year" are probably the same issue but unverified.** The key date is missing or cover-dated across a year end (`Dragonlance - The Legend of Huma 001 (2003)` vs GCD 2004-01).

**Per 1,000, summarised:**
- With a year: at most 1 wrong issue.
- With the folder year as series start: 0–12.
- With no year at all: 8–57.
- Unnumbered whole books: 9–74 (small samples).

T1 and T2 lean towards mainstream titles. The unmatched pool is older and more indie, so the sample review in §3a is the closer read: 2 wrong out of 161, both from the language rule.

## 5. Fields (question 3)

Coverage among the 12,972 guarded hits. "Would fill" means the comic's field is empty today.

| GCD source | ComicInfo field | Hits with it | Would fill | Note |
|---|---|---:|---:|---|
| `series.name` | Series | 100% | — | |
| `issue.number` | Number | 100% | — | `[nn]` = no printed number |
| `issue.key_date` (else on-sale) | Year / Month | 98.6% / 96.0% | 11,880 / 11,591 | Key date, not always cover month (§4) |
| `issue.on_sale_date` | Day | 65.4% | 8,138 | Day of sale, not cover day; skipping it is safer |
| `publisher.name` | Publisher | 100% | 9,978 | Run through `imprints.py` |
| brand emblem / indicia publisher | Imprint | 94.7% | 12,162 | Brand names need mapping (for example `DC [bullet]`) |
| story credits (comic stories: script/pencils/inks/colors/letters) | Writer / Penciller / Inker / Colorist / Letterer | 71% / 71% / 71% / 63% / 68% | 9,004 / 9,059 / 9,149 / 8,141 / 8,776 | Structured credits, with the old text fields as fallback |
| cover story credits | CoverArtist | 80.4% | 10,262 | Main cover only |
| issue editing credits | Editor | 77.1% | 9,942 | |
| `story.synopsis` | Summary | **21.5%** | 2,581 | Would go through the existing synopsis review (SYNOPSIS_POLICY); GCD text can contain spoilers |
| `story.characters` | Characters | 42.7% | 5,493 | Free text with notes; structured `gcd_story_character` also exists |
| `story.genre` | Genre | 60.8% | 7,358 | Lower-case GCD genres |
| issue title / story titles | Title | 54.6% | 6,806 | Story titles are per story, not the issue title |
| `issue.barcode` | GTIN | 71.2% | 9,236 | Main cover's barcode; wrong for a variant file, and that cannot be told without a cover check |
| `issue.valid_isbn` | ISBN | 16.1% | 2,084 | Mostly collected editions |
| `issue.rating` | AgeRating | 30.8% | 3,904 | |
| `series.publishing_format` / publication type | Format | 99.2% | 12,707 | Free text ("was ongoing series", "collected edition"); needs a small mapping |
| `series.issue_count` | Count | 100% | 12,863 | Only right for finished series (`year_ended` set) |
| `issue.page_count` | (PageCount) | 77.4% | — | Printed pages, not pages in the file; do not map |
| issue id | Web | 100% | 11,621 | `https://www.comics.org/issue/<id>/` |
| — | Notes | — | — | Attribution line (§6) |

Not in the dump: covers or cover links, Metron/ComicVine ids, and story arcs beyond 689 records.

## 6. Fit and cost (question 4)

**Index build.** Method: `build_index.py` over the extracted dump, wall time on this machine, OS cache warm after the unzip.

| Variant | Time | Size |
|---|---:|---:|
| All languages for matching + English fields (used in this trial) | 65 s | 562 MB |
| English only (what the app needs) | 97 s (stage 1: 14 s; credits/synopsis: 78 s) | **405 MB** (match tables alone: 99 MB) |

A refresh also needs the unzip (34 s) and about **6.8 GB free temporarily** for the extracted file. SQLite cannot read the database from inside the zip.

**Lookup time.** Method: `time.perf_counter` around every guarded lookup for all 30,085 pool comics, with SQL queries against the index on disk (warm). **Median 0.64 ms, 95th percentile 1.0 ms, max 18 ms.** The whole pool takes about 18 s.

**Refresh (about every 2 weeks; Sergei downloads by hand):**
1. Sergei saves `current.zip`. The app reads the dump date from the file name inside the zip.
2. It unzips the database to a temporary file, builds the new index next to the old one (~2 min) and checks it (row counts, `quick_check`).
3. It swaps the index in place, then deletes the temporary file.
4. It records the dump date. Comics whose last GCD-index answer was "no match" under an older dump become due once.

GCD issue ids are stable, so `Web` links survive refreshes. Sergei's zip is never touched.

**Licence (CC BY-SA 4.0, per Makoto; not legal advice):**
- **Attribution:** every write's Notes carries a line such as "Metadata from the Grand Comics Database (www.comics.org), CC BY-SA 4.0, data dump 2026-10-16", plus the GCD issue link in `Web`.
- **Share-alike:** the written fields, and any GCD synopsis text, are adapted material. Share-alike applies only when that material is shared. Personal files on his own disk carry no further duty.
  - If he ever shares the files or the index, they must go out under CC BY-SA 4.0 with that attribution.
  - The index lives in the gitignored state folder and must never be committed to the repo.

**Fit with the source and verification model:**
- **Does not fit as-is.** The Brief excludes "write metadata from a search match alone".
  - `SOURCE_CONNECTORS.md` sets the GCD rule as exact series and number plus cover agreement. With no cover, no identity-dependent write is made.
  - The dump has no covers, so an offline match is exactly a search match.
- **Ways it can fit:**
  1. **Index finds, online cover confirms.** The index replaces GCD's search and series calls with one issue request (for the cover link) plus the image. That is about 1 API request per comic against today's 2–4, inside the 1,000-a-day budget.
     - However, none of the 812 GCD cover checks has ever passed (diagnosis #4), so this path yields nothing until that is explained.
     - It also needs network calls to comics.org.
  2. **A rule change by Sergei:** a unique series+number+year match in the GCD index counts as verified, like an exact ISBN does for the Open Library index. This could be limited to the strict class first.
  3. **Corroboration rules** (also Sergei's call):
     - In-book comics: the comic's own cover already confirmed series and number. That covers 7,206 of the hits.
     - Two catalogs agreeing: Metron's single candidate plus GCD's single candidate covers 1,861 hits. Both read the same filename, so it is not fully independent.
  4. **Identifier match** (barcode or ISBN already in ComicInfo): only 281 live comics have a GTIN and 36 an ISBN, so this does nearly nothing.
- **Plumbing fits.** The app already has an offline index provider (`open_library.py`) and a result shape (`provider`, `fields`, `sources`, `status`) that a GCD-index provider can reuse. Budgets, pacing and caches do not apply offline.

## 7. Recommendation (question 5)

**Pilot it.**
- The data is good and cheap to run.
- The blocker is the verification rule, not the data. That is Sergei's decision, not a technical one.

**Pilot (effort S):**
- An offline GCD-index provider with the guarded rules, behind a switch that is off.
- A read-only report over the live library: what it would write, per comic and per field. This is the same shape as the 10-13 credits pilot.
- Futaba samples it before any write is switched on.

**Build after the pilot (effort M):**
- Index builder from the zip, with dump date and refresh flow.
- The provider and field mapping (imprints, Format, credits).
- Notes attribution, re-queue on refresh, a dashboard status line, and tests.
- Option 1 (online cover check) adds the GCD cover investigation from diagnosis #4 (M).

**Expected extra comics (correct, before overlap):**

| If Sergei allows | Comics | Expected wrong |
|---|---:|---|
| Unique series+number+year, including years from filenames | ~6,180 (5,618 searchable: B 3,549 · D 868 · E 1,201; plus 562 with a filename year) | ≤ 1 per 1,000 |
| + folder year as series start | +823 → ~7,000 | 0–12 per 1,000 on those |
| + no-year, unnumbered and collected volumes | +~5,970 → ~12,970 | 8–74 per 1,000 on those (about 60–400 comics in total) |
| A cover check is still required | **unknown** | GCD covers have never passed; needs diagnosis #4 first |

- **Overlap:** some of these comics will also be reached by enrichment items A–E, now being built: Metron year-less and unnumbered search, the cover audit and refinement. How many is **unknown** until those land.
- **Most likely unique to GCD:** the 2,104 comics where Metron has no such series that year, and most of the 921 collected volumes.
- **Group B** (7,206 hits) are already in-book tagged, so for them GCD enriches rather than adds a comic.

## Decisions for Sergei

1. Count a unique series+number+year match in the GCD file as verified, with no cover check? (yes/no)
2. Also allow matches that take the year from the folder or file name? (yes/no)
3. Also allow no-year, unnumbered and collected-volume matches, at 1–7% wrong? (yes/no)
4. Use GCD story synopses as synopsis sources, through the existing review? (yes/no)
5. If 1 is no: investigate GCD's cover check first? (yes/no)

## Outside this trial (offered, not done)

- `[rus]` (square-bracket) language tags pass the app's language rule, so Russian files can be matched to English issues by any source. Fixing it is a separate small change, if wanted.

## Unknowns

- **GCD cover check:** why it has never passed (download refused vs comparison). Needs network calls to comics.org, which this trial excluded.
- **Overlap with enrichment items A–E:** they are not built yet.
- **Licence wording, "Private Use" download terms and the official update rate:** comics.org was not contacted. Taken from Makoto's notes.
- **Cold-cache build and lookup times:** the dump was measured straight after unzip, with a warm cache.
- **Whether `(Dr.Vink)` unnumbered files with a ComicInfo #1 are issues or collected editions.**
