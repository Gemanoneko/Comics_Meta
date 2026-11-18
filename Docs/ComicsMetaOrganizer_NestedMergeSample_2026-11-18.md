# Comics Meta Organizer - nested ComicInfo merge, dry-run sample check (Futaba, 2026-11-18)

Checked: the dry run `ComicsMetaOrganizer_NestedMergeDryRun_2026-11-18` (.md, .csv, .json) and the tool `tools/nested_comicinfo_merge.py`, read with `git show` from branch `ender/0.6.7-nested-holds` at `704cb526b7816a0a932f34d48b0a5bf996281a2d` (no checkout; the main checkout was not touched). Library `Y:\Comix`; the dry run was made 2026-11-18 22:10:08.

**Dry-run sample verdict: GO**

In plain words: on 33 sampled merges and the held archive, my own independent reading of both ComicInfo copies agrees with the plan on every fill, every dropped value, every date left out and every "None". No root value is lost and nothing valuable falls outside the dropped-values record. The summary counts match the CSV and JSON exactly. Nothing breaks the core flow (no Blocker, nothing data-losing). One thing needs Sergei's explicit yes or no before he OKs the real run: finding F1 (dates taken from the nested copy where the root has none). Findings F2 to F6 are smaller and optional.

## What Sergei needs to decide

1. **F1, dates.** 29 archives get a date part (22 of them a Year) copied from the nested copy where the root has no full date. Those nested dates look like store release dates, not cover dates, and the apply records filled values as Sergei's own ("manual", per the tool's description), so the app would not correct them later. In 4 of the 20 Year fills that have a year in the file name, the year is one off (for example Adventure Time 007 (2026) would get 2025). Keep as planned, or leave nested dates out whenever the root has no complete date? Appendix A lists all 29.

## Method (what I did, and how the numbers were counted)

- **Read-only.** Archives were opened through a shared read handle (read, write and delete sharing, so the app is never blocked). Only each archive's central directory and its ComicInfo entries were read, in memory. Nothing was written to any comic, the catalog, the config or the app. The app was not stopped. No window, focus or mouse was used. Bash and the app's bundled Python (`-I -B`); scripts in files.
- **Independent derivation.** I re-implemented the rule from the dry-run doc in my own code (no import of the app or of the tool): fill-empty element by element with exact tag names, root wins, nested "None" is blank, a conflicting date leaves out the nested Year, Month and Day together. For each archive I compared my result with the plan entry (fills, dropped values with their text, date skip, "None" list), then simulated the resulting root copy and checked that every filled root element is still there unchanged. A nested element counts as "not lost" only if it is copied, recorded as dropped with its exact text, or equal to the root's value. Because my derivation implements the same rule, agreement shows the tool does what the rule says; whether the rule's results are good for the library is what findings F1 to F6 are about.
- **Sample.** Seeded (`random.Random(20261118)`), stratified, drawn without replacement per stratum. Pools (merge set of 356): plain fills 179 (standard tags, no note, no date skip, no "None"); Series/Number differs 65; date left out 24; nested "None" 13; only the nested copy goes (nothing to fill) 24; odd-tag fills 81; Pages block filled 76. Quotas 6 / 6 / 5 / 4 / 4 / 6 / 2 = 33 merges, one of the two "Number named differently" cases forced in, plus the held archive = 34. An archive that belongs to several strata is counted once, and its table row names the other strata. After the first pass I added 3 hand-picked archives from the riskiest names in the Series/Number stratum (rows 35 to 37).
- **Beyond the sample (read-only, cheap, labelled where used).** A stat-only check of all 357 plan paths (exists, size, modified time); plan-level scans over the JSON and CSV for dates, Volume, odd tags and Titles (no archive reads); the YACReader parser source, fetched read-only from its public repository.
- **Counting method for the summary counts.** Python `json` over the plan's 357 entries, Python `csv` module over the CSV (not line counts: the CSV has 4,001 physical lines but 2,537 records, because 368 rows hold line breaks inside quoted values), `Counter` over (tag, why), sets of distinct archive names for per-archive counts, and the markdown tables parsed by script and compared to the JSON and CSV tallies.

## 1. The planned merges: sample table

PASS = my derivation equals the plan entry exactly, every root value stays, nothing is lost. PASS (note) = the same, plus an observation listed under Findings. "Dropped" always means the nested value goes and the root value stays.

| # | Archive | Case type | Verdict | Notes |
|---|---|---|---|---|
| 1 | Creatures on the Loose 031 (1974) (Digital) (Shadowcat-Empire).cbz | plain fill | PASS | Fills PageCount 16 (absent in root; the archive holds 16 images). Dropped: Web, Volume (1971 vs root 1), Notes, Genre. Root 1974-09-01 untouched. |
| 2 | Excalibur 005 (2004) (Digital) (Shadowcat-Empire).cbz | plain fill | PASS | Fills Volume 2004, Genre, PageCount 24 (24 images). Dropped: Web, Summary, Notes. |
| 3 | Elvira's House of Mystery 002 (1986) (Digital) (Shadowcat-Empire).cbz | plain fill | PASS | Fills Summary, Genre, PageCount 23 (23 images). Dropped: Web, Volume, Notes, Publisher (DC vs DC Comics). |
| 4 | Second Chances (2022) (Digital) (XRA-Empire).cbz | plain fill | PASS | Fills Title, Genre, LanguageISO. Dropped: Web, Notes, ScanInformation. Root Number 1 and 2022-3-1 stay. |
| 5 | Indiana (Europe Comics 2023) (webrip) (MagicMan-DCP).cbz | plain fill | PASS | Fills LanguageISO, Summary, Publisher. Dropped: Notes. Neither copy has a number or date. |
| 6 | Breathers (2023) (Digital) (XRA-Empire).cbz | plain fill | PASS | Fills LanguageISO "EN" (upper case; F6). Dropped: Web, Summary, Notes, Publisher, ScanInformation. |
| 7 | Age Of Conan - Belit - Queen Of The Black Coast 01.cbz | Series/Number differs, Pages block filled | PASS | Flagged for Number: nested "01 (of 05)" vs root "1" (the same issue written differently; Series differs only in punctuation). Root Series and Number stay. Fills 14 fields incl. Pages (26 Page elements, 26 images, Image index 0 to 25 in order). Root had no date, so nested 2019-05 is filled (F1). Dropped: Series, Number, Notes. |
| 8 | Heat Seeker - Combustion - A Gun Honey Series 002 (2024) (Digital Rip) (Hourman-DCP).cbz | Series/Number differs | PASS | Series differs ("... A Gun Honey Series" vs "Heat Seeker: Combustion (2024)"); root Series stays. Fills Summary. Dropped: Series, Notes. |
| 9 | Godzilla - Kingdom of Monsters v02 (2012) (digital) (Dr.Vink).cbz | Series/Number differs, odd tag | PASS (note) | Fills Title, Summary, Genre, PageCount 91, ScanInformation, Writer, and `Artist` copied as-is (root has no Penciller, so `Artist` is the only carrier; F3). PageCount 91 vs 92 images (F2). Root also carries `ISBN`, a non-standard tag already there. Dropped: Series, Web, Notes, Publisher. |
| 10 | Step by Bloody Step - A Wordless Fantasy (2022) (Digital) (XRA-Empire).cbz | Series/Number differs | PASS | Root Series "...: A Wordless Fantasy" stays. Fills Title, Genre, ScanInformation. Dropped: Series, Web, Notes, Publisher, Writer (Simon Spurrier vs root Si Spurrier), Penciller. |
| 11 | Plunge (2020) (digital) (Son of Ultron-Empire) (Fan Made TPB).cbz | Series/Number differs | PASS (note) | Root Series "Plunge" stays (nested "Plunge (2020)"). Root had no Number, so nested Number 1 is filled. Fills 9 fields. PageCount 170 vs 172 images (F2). Dropped: Series, Notes. |
| 12 | Chilling Adventures Presents... Truth or Dare (OS) (2024) (Forsythe-DCP).cbz | Series/Number differs, only nested goes | PASS | Nothing to fill; the root holds it all. Dropped: Series ("(One Shot)" suffix), Summary, Publisher, Notes. Root 2024-09-01 stays. |
| 13 | King Conan 001 (1980) (Digital) (Shadowcat-Empire).cbz | date left out, Pages block filled | PASS | Nested date 2022-6-28 (Year, Month, Day) left out; root 1980-3 stays. Fills Volume 1980, Summary, Genre, PageCount 36, ScanInformation, Pages (36 Page elements, 36 images). Dropped: Web, Notes, CoverArtist, and the three date parts. |
| 14 | King Conan 017 (1983) (Digital) (Shadowcat-Empire).cbz | date left out, Pages block filled | PASS | Nested 2022-6-28 left out; root 1983-7 stays. Fills Volume 1980, Summary, Genre, PageCount 40, ScanInformation, Pages (40 and 40). Dropped: Web, Notes, date parts. |
| 15 | Bishop 003 (2026) (Digital) (Kileko-Empire).cbz | date left out | PASS (note) | Nested Month 8, Day 19 left out; root 2026-10 stays (Year equal). Fills Volume 2026, Summary, PageCount 24, AgeRating. PageCount 24 vs 25 images (F2). Dropped: Penciller (root has more names), Publisher. |
| 16 | King Conan 002 (1980) (Digital) (Shadowcat-Empire).cbz | date left out, Pages block filled | PASS | Nested Year and Day left out (Month 6 is equal to the root's); root 1980-6 stays. Fills 6 fields incl. Pages (36 and 36). Dropped: Web, Notes, CoverArtist (Ernie Chan vs John Buscema), date parts. |
| 17 | King Conan 012 (1982) (Digital) (Shadowcat-Empire).cbz | date left out, Pages block filled | PASS | Nested 2022-6-28 left out; root 1982-9 stays. Fills 6 fields incl. Pages (40 and 40). Dropped: Web, Notes, CoverArtist, date parts. |
| 18 | Betsy Braddock - Captain Britain (2024) (Digital) (Shan-Empire).cbz | "None", Series/Number differs | PASS | Nested `<Number>None</Number>` is not copied; root Number 1 stays. Root Series (a word swap of the nested one) stays. Fills Summary, PageCount 145 (145 images), LanguageISO. Dropped: Series, Web, Notes, Month (4 vs root 01). |
| 19 | Grimm Tales of Terror Quarterly - 2023 Halloween Special (2023) (digital) ( Li'l-Empire) (HD-Upscaled).cbz | "None", Series/Number differs | PASS (note) | Nested Number "None" is not copied; the root's blank Number stays blank (not "None"). Root Year 2023 only, nested Year equal, so Month 12 is filled beside it (F1). Fills Summary, PageCount 75 (75 images), Month. Dropped: Series (nested drops "Grimm"), Web, Notes, Publisher, LanguageISO. |
| 20 | Proxima Centauri (2019) (Digital) (XRA-Empire).cbz | "None" | PASS | Number "None" not copied; root Number stays blank. Fills Summary, PageCount 156 (156 images), ScanInformation. Dropped: Web, Publisher, LanguageISO, Month (3 vs root 1). |
| 21 | Edge of Spider-Verse (2023) (Digital) (Shan-Empire).cbz | "None" | PASS | Number "None" not copied; root Number stays blank. Fills Summary, PageCount 163 (163 images). Dropped: Series (case only), Web, Notes, Publisher (Marvel vs Panini UK), LanguageISO, Month. |
| 22 | Wonder Woman - The Adventures of Young Diana (2024) (webrip) (MagicMan-DCP).cbz | only nested goes | PASS | Nothing to fill. Dropped: Series, Summary (both differ from the root's). Root 2024-10 stays. |
| 23 | Druuna 00 Anima (of 9) (2016)(2 covers)(GN)(digital)(cbf-dcp).cbz | only nested goes | PASS | The nested copy holds only PageCount 102 (equal to the root's) and a Pages block; the root already has a Pages block, so the nested one is dropped (the CSV and JSON show it as a placeholder, `<Pages: 1 element(s), 102 child element(s)>`; the whole copy is kept by the apply's record). The only archive where the root copy is first in ZIP order and not the last entry (F7). |
| 24 | Mawrth Valliis OGN (2021) (Digital) (XRA-Empire).cbz | only nested goes, Series/Number differs | PASS | Nothing to fill. Dropped: Series ("... OGN"), Web, Summary, Notes, Genre, ScanInformation, Day (21 vs root 25). Root 2021-7-25 stays. |
| 25 | S.I.R. 003 (2024) (Digital Rip) (Hourman-DCP).cbz | only nested goes, Series/Number differs | PASS | Nothing to fill. Dropped: Series ("S.I.R. (2024)"), Publisher, Notes. |
| 26 | Star Wars - Darth Vader 049 (2024) (Digital) (Kileko-Empire).cbz | odd tag | PASS | Copies `Issue` 49 and `writer` Greg Pak as-is. The root already holds Number 49 and Writer Greg Pak, so both are duplicates (F3). Nested Month 8 loses to root Month 10. Dropped: Publisher, Notes, Month. |
| 27 | Secret Wars By Jonathan Hickman Omnibus (2025) (Digital) (EricJGriffin-Empire).cbz | odd tag | PASS (note) | Copies `writer` (root already has Writer). PageCount 833 vs 834 images (F2). Dropped: Series (case), Notes, Month (2 vs 02). |
| 28 | Lazarus - Fallen 004 (2025) (Digital) (Forever-Empire).cbz | odd tag | PASS (note) | Copies `Issue` 4 and `writer` (root has Number and Writer). PageCount 32 vs 33 images (F2). |
| 29 | G.O.D.S. (2024) (Digital) (EricJGriffin-Empire).cbz | odd tag | PASS (note) | Copies `writer` (root has Writer). PageCount 273 vs 274 images (F2). Summary fill starts "Collects G.O.D.S. #1-8." |
| 30 | Adventure Time 001 (2025) (digital) (Bean-Empire).cbz | odd tag | PASS | Copies `Issue` 1 and `writer`: root Writer "Derek Ballard, Nick Winn" and nested "Nick Winn, Derek M Ballard" (same people, different spelling and order); both end up in the root. |
| 31 | Star Wars - Jango Fett - Trail Of Lost Hope (2025) (Digital) (Kileko-Empire).cbz | odd tag | PASS | Copies `writer` (root has Writer). Fills LanguageISO. Dropped: Series (case), Notes. |
| 32 | King Conan 014 (1983) (Digital) (Shadowcat-Empire).cbz | Pages block filled, plain fill | PASS | Root date is complete (1983-01-01), so no nested date is filled; nested 2022-6-28 are plain "root wins" drops here, not date left out. Fills Summary, PageCount 40, ScanInformation, Pages (40 and 40). Root Volume 1 stays (nested 1980 dropped; compare row 14, F4). |
| 33 | Savage Sword Of Conan 05.cbz | Pages block filled, plain fill | PASS | Fills Genre, PageCount 28, ScanInformation, Pages (28 and 28). Root Volume 2 stays (nested 2019 dropped). Dropped: Web, Volume, Summary, Notes. |
| 34 | Ms. Tree v04 - Deadline (2022) (Digital) (XRA-Empire).cbz | HELD | PASS (the hold is right) | See section 3. |
| 35 | Harley Quinn - Uncovered 001 (2023) (Digital) (Walkabout-DCP).cbz | extra: Series/Number differs | PASS | Nested Series "Harley Quinn" and Title "Uncovered" describe the same art-book issue (summary: variant-cover art book for Harley Quinn #25). Root Series stays. Fills Title, PageCount 45, ScanInformation. |
| 36 | 21st Century Tank Girl (2015) (Digital) (XRA-Empire).cbz | extra: Series/Number differs | PASS | Nested Series is the franchise "Tank Girl", nested Title is the book title; same book. Root Series stays. Fills Title, Genre, ScanInformation, Writer, Penciller. |
| 37 | Dirty Old Tank Girl (2019) (Digital) (XRA-Empire).cbz | extra: Series/Number differs | PASS (note) | Same pattern. Fills Title **"Dirty Old"** (a fragment of the book title; F6), Summary, Genre, PageCount 244 vs 246 images (F2). |

Totals for rows 1 to 33 (the stratified merges): 112 fills, all into tags that were absent in the root (none replaced a blank element), each also present and filled in the nested copy; 126 dropped tags, each with root value kept and the dropped text exactly as in the plan; 530 filled root elements, all still present and unchanged in the simulated result; root Series, Number and date unchanged in all 33; plan, CSV and my derivation differ in 0 places. For every archive in rows 1 to 37 the file size, modified time, and the nested entry's name, CRC and size still match the plan. ZIP order: nested copy first in 32 of 33 (row 23 is the exception).

Also checked, stat only, no archive reads: all 357 plan paths still exist with the planned size and modified time (0 missing, 0 changed), including the paths with non-ASCII characters.

**Stratum results.** Plain fills: all fills really empty in the root and filled in the nested copy. Series/Number differs: in 64 of the 65 the shorter name is contained in the longer (subtitle, volume, year or franchise suffix); the 65th is a word swap (Betsy Braddock / Captain Britain). All 13 I read (10 drawn plus 3 extras) describe the same book as the root, so the nested copy's fills belong to the right comic. Date left out: 5 of 24 read, all behave as the doc says, root date stays. "None": 4 of 13 read, "None" never copied, root Number untouched (blank stays blank). Only the nested copy goes: 5 read; everything dropped is recorded, nothing valuable is silently lost.

## 2. The resulting root copy: would it be sane for the reader?

**Well-formed and complete.** All 33 simulated results serialise and parse again as XML. Filled elements are appended after the root's existing elements, in the nested copy's order. Tag order is not the ComicInfo schema's order; I did not validate against the XSD, and YACReader's parser does not care about order (below).

**What YACReader does with it (from its source, not run).** `YACReaderLibrary/xml_info_parser.cpp` loops over the XML elements and compares each name with exact-case strings (`Number`, `Writer`, `Penciller`, `Year` and so on); an element it does not know is skipped, children and all. The file is identical (blob `29ed0620`) at tag 10.5.1 and on the default branch (HEAD `8e59015459`, 2026-11-17). Consequences:

- Odd tags (`writer`, `Issue`, `Artist`) are copied as-is, because the merge matches tag names exactly; a root without `writer` counts as empty. YACReader ignores them, so they are harmless to display and add no information it can show. Today YACReader reads the nested copy first, where the same odd tags are ignored too, so the merge is not a regression for them. See F3 for the counts: `Issue` is redundant in all 22 archives (the JSON shows the root already has a Number), `writer` was redundant in 5 of 5 sampled, `Artist` was the only carrier in the 1 sampled (its content is kept, in a tag no reader shows).
- `PageCount` and `Pages` are not read by YACReader at all; its library import sets the page count from the archive's file list. A stale PageCount (F2) does not show there.
- Where the nested copy held the data under standard tag names (`Writer`, `Penciller`, `Summary`, `Genre`, ...), the fills do show in YACReader after the merge, from the root copy. Where both copies hold a value, YACReader switches from showing the nested value to showing the root's (Publisher "Marvel" instead of "Marvel Entertainment, Inc.", the ComicTagger Notes instead of the scrape Notes, and so on). That is the intended effect of "root wins".
- No odd tag collided with a standard tag holding a different value in my sample (writer/Writer: same people in all 6, order and spelling differ in 1).
- Summary text copied with literal HTML entities (`&rsquo;`, `&#8211;`, `&apos;`) in 6 fills shows as typed; YACReader shows the same text today from the nested copy (F6).

## 3. The held archive: Ms. Tree v04 - Deadline

- **The hold is correct.** The nested copy is not well-formed. My independent parse fails at the same place the dry run reports: "mismatched tag: line 21, column 2". Cause: on line 5 the closing tag of the Web element is damaged, `<Web>https://www.amazon.com/Ms-Tree-Vol-Deadline-ebook/dp/B0B1JLM4TQ/Web>` (no `</Web>`), so `<Web>` is never closed before `</ComicInfo>`.
- The plan entry carries action "hold" with no fills and no drops, so nothing would be written or removed. File size, modified time and the nested entry's name, CRC and size match the plan. The archive has 257 images; the copies are: nested first in ZIP order, root last.
- The root copy holds Series Ms. Tree, Number 4, Year 2022, Month 10, Publisher, CoverArtist, Editor, Title, GTIN, ISBN, Count, LanguageISO, Web, Notes.
- If someone repaired the missing `<` by hand, my reading is that the merge would fill Summary, Genre, ScanInformation, Writer and Penciller and drop Title, Web, Notes and Publisher; the date would not conflict (Year 2022 equals the root's). I did not run that.
- **The dry-run doc's Held line is wrong about the root:** it prints "root: - #-, no date; nested: - #-" although the root is Ms. Tree #4, 2022-10 (hold records carry no identity fields). A reader could take the root to be empty (F5).
- Unverified: YACReader reads the first ComicInfo in ZIP order, and for v04 that is the broken nested copy. Its parser returns false on an XML error; I did not trace whether the fields read before the break (Title, Series) are kept. Leaving v04 held leaves it as it is today; v01 to v03 in the same folder are fixed.

## 4. Summary counts versus the CSV and JSON

| Count in the .md | .md | JSON | CSV | Result |
|---|---:|---:|---:|---|
| Library layouts add up to the CBZ total | 40,650 | (not in the plan) | (not in the plan) | The six layout rows sum to 40,650 (11212 + 28929 + 150 + 357 + 1 + 1). Only the 357 root+nested archives are in the three files; the other layouts were not re-counted. |
| Root + one nested | 357 | 357 entries | 357 distinct archives | match |
| Merge, then remove the nested entry | 356 | 356 | 356 | match |
| of which fill at least one field | 332 | 332 | 332 archives with a fill row | match |
| of which fill nothing | 24 | 24 | 24 (356 minus 332) | match; each of the 24 also drops at least one value (none is an empty merge); 7 other merges, which do fill, drop nothing |
| Series or Number differs | 65 | 65 (63 Series, 2 Number, no overlap) | 65 | match |
| Nested date left out | 24 | 24 | 24 archives with a "root date stays" row | match |
| Held | 1 | 1 | 1 | match |
| Fields filled in all | 1,159 | 1,159 | 1,159 fill rows | match |
| Nested values dropped / in archives | 1,377 / 349 | 1,377 / 349 | 1,377 rows (1,315 root wins + 62 root date stays) / 349 | match |
| Fields filled per type (27 types) | table | tally | tally | all 27 rows identical |
| Nested values dropped per type (24 rows) | table | tally | tally | all 24 rows identical |
| Nested "None" in the merge set | Number 13 | 13 archives | not carried in the CSV | match (JSON) |
| ZIP order | 356 nested, 1 root (of 357) | 356 nested, 1 root | n/a | match; the root-first archive is Druuna 00, which is also the only one whose root is not the last entry (356 of 357 root-last) |
| Largest archive | 4.70 GB | 4.7005 GB | n/a | match |
| Per-archive table; section bullets | 357 rows (356 merge, 1 hold); 65 / 24 / 1 | same | same | match |

Per-archive agreement between JSON and CSV: 0 differences in fills; 0 in dropped values once line endings are normalised. The committed CSV uses a bare line feed where the JSON has a carriage return plus line feed inside 8 archives' root Summary text (Cyn, Danger Street, 6 Firefly): cosmetic, and the apply works from the plan, not the CSV.

Two readings to keep in mind, neither a defect: (1) "dropped" is counted per tag, and 157 of the 1,377 (11%) are values equal bar case, punctuation or spacing (134, mostly Series 62 and LanguageISO "EN" vs "en" 36) or a leading zero (23, Month "8" vs "08"); the number does not mean 1,377 different pieces of information. (2) The ZIP-order table counts all 357 including the held one ("356 nested" covers the hold).

## Findings by severity

**Blocker: none.** **Data loss: none found.** The apply path, and with it the dropped-values CSV and the removed-nested-copies record, was not exercised (it only exists after a real run), so "nothing is lost" holds for the plan, not yet for the write.

**Major**

- **F1. Dates copied from the nested copy where the root has no full date (decision for Sergei).** 29 archives get a Year, Month or Day filled from the nested copy: 22 where the root has no date at all (so the whole nested date is taken), 7 where the root has a Year (or Year and Month) and the nested copy adds the rest. The dry run lists only the 24 conflicts it leaves out; these 29 are only in the CSV as "fill" rows for Year, Month or Day. Evidence that the nested dates are store dates: King Conan (1980) nested 2022-6-28 against a 1980 cover; Bishop 003 nested 2026-8-19 against root 2026-10. Of the 20 Year fills with a year in the file name, 4 disagree by a year: Mythos (2009) gets 2008; Adventure Time 007 (2026) and 008 (2026) get 2025; Lazarus - Fallen 006 (2026) gets 2025. Month fills could be off too (Grimm Tales of Terror Quarterly 2023 Halloween Special gets Month 12, which looks late for a Halloween special; I did not verify the real date). This follows Sergei's rulings (fill-empty everywhere; existing dates stay; the DC-year row in the Decision Log), but it is the one case the dry run does not show him. The merged values are recorded as "manual" (from the tool's own description of the apply, not tested), so the app's later cover-date writes would not replace them. Reader view: no change from today for these (YACReader already shows the nested date); the difference is that it becomes permanent. Options for Sergei: keep as planned; or leave nested dates out whenever the root has no complete date, as for the 24; or fill only when the Year matches the file name. Appendix A has the list.

**Minor**

- **F2. Filled PageCount disagrees with the archive.** 7 of 23 sampled PageCount fills (30%; rows 9, 11, 15, 27, 28, 29, 37) differ from the archive's image count, always by 1 or 2 and always lower than the archive (24 vs 25, 170 vs 172, 833 vs 834); I did not identify what the extra pages are. Across the plan there are 241 PageCount fills, so roughly 70 could be off if the sample is typical (an extrapolation, not measured). In the 9 archives where both copies hold a PageCount and the root wins, they also disagree (nested/root: 103/104, 360/370, 160/162, 250/254, 256/240, 125/119, 218/209, 214/211, 214/210), by 1 to 16 pages in both directions, so the nested count is not a reliable page count. The apply records filled values as "manual" (tool description, not tested), so a wrong count would stay. YACReader ignores PageCount and the app never reads or writes it; other tools may use it. Option: do not take PageCount from the nested copy, or recompute it from the archive (Ender's call).
- **F3. Odd-case tags copied as-is: 81 archives (`writer` 69, `Issue` 22, `Artist` 12).** Clutter, not harm (section 2). `Issue` is redundant in 22 of 22 (the root already has a Number, proven from the JSON); `writer` redundant in 5 of 5 sampled, creating a `Writer`/`writer` pair in the root; `Artist` was the only carrier in 1 of 1 sampled. Option: skip a nested tag whose standard spelling is the same word in another case, or map it (Ender's call; Sergei decides if the odd content should be kept).
- **F4. Volume holds a year in the nested copy and a number in the roots.** 38 of the 39 Volume fills are four-digit years (1980, 2004, 2026); in all 45 Volume drops the nested year loses to a root number (1 to 5). Inside one series: King Conan 014 keeps Volume 1 while King Conan 017 would get Volume 1980 (rows 32 and 14). Filled values are recorded as "manual", so the enrichment would not correct them.
- **F5. Held line misreports the root (doc defect), and v04 stays as it is.** See section 3. One-character repair would let it merge like v01 to v03; not my call.
- **F6. Cosmetic fills.** LanguageISO "EN" in upper case in 8 fills (72 are "en"; 36 drops differ only by case). Of the 48 Title fills, 19 just repeat the Series, 18 are bare volume labels ("v01", "Vol. 1", "Vol. 2"), and one is a fragment, "Dirty Old" for Dirty Old Tank Girl. 6 Summary fills carry literal HTML entities (`&rsquo;`, `&#8211;`, `&apos;`); YACReader already shows the same text from the nested copy today.

**Info**

- **F7.** Druuna 00 Anima is the only archive with the root copy first and not last in ZIP order; its root was written by something else, while the doc notes the app always writes its own copy last; worth a look when the apply runs. Counting notes in section 4 (CRLF in the CSV, "dropped" includes equal values, "356 nested" includes the hold).
- **F8.** The installed app's engine is 0.6.5; the tool's docstring says the apply refuses an engine without the nested merge, so the app must be updated before the apply. Not a sample finding.

**Pattern alerts: none**

## What this sample does not cover

- 323 of the 356 planned merges were not read by hand; for them the evidence is the 33 + 3 sampled, the plan-level scans, and the plan's own self-consistency (JSON and CSV equal, counts equal). I can run my independent derivation over all 356 (read-only, about a minute) if wanted.
- The apply (write, verify, backup deletion, the two record files) was not run and not reviewed here; that is a write test and Senua's construction view.
- No YACReader run (no focus or mouse); its behaviour is from reading its parser source. The Ms. Tree v04 outcome in YACReader is unverified.
- No ComicInfo XSD validation of the resulting root copies.

## Housekeeping

Personal-folder listing (list only, counts, nothing moved or deleted): entries to depth 2 modified in the last 4 hours: Desktop 0, Documents 0, Downloads 4, Pictures 16, Videos 1, Music 4. This session wrote only under `I:/AI Projects/Temp/futaba-nested/`; I did not look into what changed in those folders.

Cleanup: my plan copies, scripts and result files (27 files, 2.06 MB) were removed with the studio sweep's approved mode (`--approved` per folder, dry run first, then `--apply`; 0 refused). Only this report remains in `I:/AI Projects/Temp/futaba-nested/Docs/`; once it is committed, that folder can be removed the same way.

## Appendix A. Archives that get a date part filled from the nested copy (29)

Root date today is from the plan's root fields; "Filled" is what the plan copies from the nested copy.

| Archive | Root date today | Filled from nested | Year in file name | Year agrees |
|---|---|---|---|---|
| Match Point! (2023) (Digital) (XRA-Empire).cbz | none | Year 2023-Month 9 | 2023 | yes |
| Parachute Kids (2023) (Digital) (XRA-Empire).cbz | none | Year 2023-Month 4 | 2023 | yes |
| The Fall of the House of Usher (2023) (Ablaze) (Digital-Empire).cbz | none | Year 2023-Month 11 | 2023 | yes |
| Weeaboo (2021) (Digital) (XRA-Empire).cbz | none | Year 2021-Month 11-Day 17 | 2021 | yes |
| Mythos (2009) (Digital) (EricJGriffin-Empire).cbz | none | Year 2008-Month 11 | 2009 | **NO** |
| Hellcat (2023) (Digital) (Shan-Empire).cbz | none | Year 2023-Month 12 | 2023 | yes |
| Hellhunters (2025) (Digital) (EricJGriffin-Empire).cbz | 2025 | Month 8 | 2025 | root has the Year |
| Lockjaw - Who's A Good Boy 001 (2018) (digital) (Marika-Empire).cbz | none | Year 2018-Month 8 | 2018 | yes |
| Pixels of You (2022) (Digital) (XRA-Empire).cbz | 2022 | Month 2-Day 8 | 2022 | root has the Year |
| Cutting Edge (2021) (Digital) (XRA-Empire).cbz | none | Year 2021 | 2021 | yes |
| Grimm Tales of Terror Quarterly - 2023 Halloween Special (2023) (digital) ( Li'l-Empire) (HD-Upscaled).cbz | 2023 | Month 12 | 2023 | root has the Year |
| Adventure Time 007 (2026) (digital) (Bean-Empire).cbz | none | Year 2025-Month 11 | 2026 | **NO** |
| Adventure Time 008 (2026) (digital) (Bean-Empire).cbz | none | Year 2025-Month 12 | 2026 | **NO** |
| Beware the Eye of Odin (2022) (Digital) (XRA-Empire).cbz | 2022-12 | Day 20 | 2022 | root has the Year |
| Black Star (2021) (Digital) (XRA-Empire).cbz | 2021 | Month 5 | 2021 | root has the Year |
| Age Of Conan - Belit - Queen Of The Black Coast 01.cbz | none | Year 2019-Month 5 | none in name | n/a |
| Age Of Conan - Belit - Queen Of The Black Coast 02.cbz | none | Year 2019-Month 6 | none in name | n/a |
| Canto - The Hollow Men (2024) (Digital-Empire).cbz | none | Year 2024-Month 7 | 2024 | yes |
| The Cowboy Wally Show (2016) (Digital) (FatNerd).cbz | none | Year 2016-Month 9-Day 21 | 2016 | yes |
| Daphne Byrne (2020) (digital) (Dr.Vink).cbz | none | Year 2020 | 2020 | yes |
| The Disciples (2016) (digital) (Dr.Vink).cbz | none | Year 2016 | 2016 | yes |
| Eros - Psyche (2021) (Digital) (XRA-Empire).cbz | none | Year 2021-Month 12 | 2021 | yes |
| Firefly Holiday Special 001 (2021) (Digital) (Pirate-Empire).cbz | none | Year 2021-Month 12-Day 15 | 2021 | yes |
| KISS - Zombies (2021) (Digital) (XRA-Empire).cbz | none | Year 2021 | 2021 | yes |
| Lazarus - Fallen 006 (2026) (Digital) (Forever-Empire).cbz | none | Year 2025-Month 11 | 2026 | **NO** |
| Memorial (2014) (Digital) (XRA-Empire).cbz | none | Year 2014-Month 12-Day 10 | 2014 | yes |
| Planet of the Apes Artist Tribute (2019) (Digital) (Bean-Empire).cbz | 2019-4 | Day 10 | 2019 | root has the Year |
| Spectacle, Book 02 (2019) (Digital) (Relic-Empire).cbz | 2019-5 | Day 22 | 2019 | root has the Year |
| Star Wars - Dark Droids (2026) (Digital) (Kileko-Empire).cbz | none | Year 2026-Month 8-Day 19 | 2026 | yes |
