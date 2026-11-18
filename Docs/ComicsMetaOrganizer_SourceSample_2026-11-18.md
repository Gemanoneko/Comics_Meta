# Comics Meta Organizer - source sample before switch-on (Futaba, 2026-11-18)

Sergei's overnight bar (2026-11-17): a source goes on only with at least 99% correct on at least 50 known comics (met in the pilots) AND a clean Futaba sample of what it would write. This is that sample, for **ComicVine name search** and **VerseDB**. Flag-only: nothing was fixed, committed or written to a comic.

## Build and method

- Worktree `I:/AI Projects/Worktrees/Comics Meta Organizer/comicvine-name-search`, branch `ender/comicvine-name-search` @ `0ca864e`, tree clean (git status empty) when the runs started.
- **The branch moved while I ran.** Both runs loaded `0ca864e` (09:19 is after they started at 08:45 and ended at 09:05 and 09:15). At 09:19 (+0200) the branch got `e714685` (v0.6.5 review fixes S1, S2, S3, N2) and `9e7ed54` (Brief row); `c253521` (the Senua docs commit) landed at 09:02. I read the code delta of `comicvine_search.py`, `versedb.py` and `source_scheduling.py` since `0ca864e`: it changes request pacing (a wait the pass may not spend is deferred instead of slept), the ComicVine name search stepping aside after a manual dashboard search, and which saved results may be reused after a source is switched off or its rules change. It does not touch the identity, candidate, cover or detail checks, so I expect the sample to stand, but I did not re-run it against `9e7ed54`; these verdicts belong to `0ca864e`.
- Interpreter: system `C:\Python314\python.exe` 3.14.10 with Pillow 12.2.0.
- Commands, exactly as briefed (started 08:45, local):
  - `python -B tools/comicvine_would_write.py --out "I:/AI Projects/Temp/futaba-cv-sample" --limit 200 --max-requests 150`
  - `python -B tools/versedb_would_write.py --out "I:/AI Projects/Temp/futaba-vdb-sample" --limit 150 --max-requests 150`
  - Run in parallel (different sources). The tools read the live catalog through a read-only SQLite backup into their own copy; keys never printed.
- Judging, every would-write row (all of them, none sampled down): extracted archive page 1 read-only from the library (`Y:\Comix`), fetched the matched issue's cover from the source's image host (ComicVine `comicvine.gamespot.com`, VerseDB `media.versedb.com`; cover URL read from the run's cached answer, so no extra API request), built a side-by-side picture and compared by eye: cover art, issue number, volume/run, year, edition. Then compared the would-write values with the comic's existing metadata.
- Right = same issue (a variant cover of the same issue counts), correct volume/run, correct year. Wrong = different issue, run, collection-vs-single or edition. Unsure = could not tell.

## Result

| Source | Pool | Asked | Would write | Right | Wrong | Unsure | Stopped because | Verdict |
|---|---|---|---|---|---|---|---|---|
| ComicVine name search | 6,904 | 77 of 200 sampled | 15 | 15 | 0 | 0 | the name search's own hourly allowance for `issue` was used (117 API requests, 18 cover comparisons) | **GO (clean sample)** |
| VerseDB | 7,566 | 94 of 150 sampled | 23 | 23 | 0 | 0 | `--max-requests 150` reached (31 covers compared) | **GO (clean sample)** |

Clean = 0 wrong: both met. Sample size, honestly: 15 of 15 and 23 of 23 right give a 95% lower bound of about 82% and 88% on their own; they cannot prove 99%. They are a clean look at what would be written, and the 99% bar rests on the pilots, as the brief says.

The would-write rate among comics actually asked: ComicVine 15 of 77 (19%, pilot said 17%), VerseDB 23 of 94 (24%).

## ComicVine name search - 15 would-write rows

| # | File | Matched issue (ComicVine id) | Verdict | Reason |
|---|---|---|---|---|
| 1 | Robotech - Invid War Aftermath 002 (1993) (1920px).cbz | Robotech Invid War: Aftermath #2, 1993, Eternity (145479) | right | Same cover art, "2"; the 1993 Aftermath run, not the 1992 Invid War run |
| 2 | Alien - The Friendliest Facehugger - Infinity Comic 011 (2026) (digital-mobile-Empire).cbz | Alien: The Friendliest Facehugger Infinity Comic #11, 2026, Marvel (1180616) | right | Identical cover, "11" badge |
| 3 | Memorial - Imaginary Fiends 006 (2012) (digital) (Minutemen-Excelsior).cbz | Memorial: Imaginary Fiends #6, 2012, IDW (372627) | right | Identical cover, "#6" |
| 4 | Ezra - Evoked Emotions 001 (2006) (Digital) (K6-Empire).cbz | Ezra: Evoked Emotions #1, 2006, Arcana (178272) | right | Identical cover, "1" |
| 5 | Lurker 02 (2023) (Digital) (Leifman-Empire).cbz | Lurker #2, 2023 (volume began 2022), Wild River (980307) | right | Identical cover, "Issue 02" |
| 6 | The Life of Captain Marvel (2019) (Digital) (Zone-Empire).cbz | The Life of Captain Marvel #1, 2019, one-issue volume, Marvel (697637) | right | The file is the 2019 collected edition; its cover is identical to the one-issue 2019 record (not the 2018 five-issue series) |
| 7 | Warhammer Monthly 020 (1999) (raynor ni).cbz | Warhammer Monthly #20, 1999 (volume 1998), Games Workshop (238771) | right | Identical cover, "20", "The Redeemer" |
| 8 | Tarot Witch of the Black Rose 043 (3 covers)(2007)(Digital)(Tyrant Lizard King-EMPIRE).cbz | Tarot: Witch of the Black Rose #43, 2007 (volume 2000), Broadsword (121832) | right | Page 1 is cover A; accepted on page 2, which is the matched "Dead Leaves" variant. Same issue (March, #43); the file says "3 covers" |
| 9 | Grimm Fairy Tales Short Story Collection (2010) (YZ1).cbz | Grimm Fairy Tales: Short Story Collection #1, 2010, Zenescope, one-issue volume (209390) | right | Identical cover, "Volume One / Short Story Collection" |
| 10 | Grimm Fairy Tales Annual 02 (2008) (Cover A) (GreenGiant-DCP).cbz | Grimm Fairy Tales Annual #2, 2008 (volume 2007), Zenescope (148693) | right | Identical cover, "2008 Annual" |
| 11 | Blade First Bite - Infinity Comic 004 (2023) (digital-mobile-Empire).cbz | Blade: First Bite Infinity Comic #4, 2023, Marvel (1002188) | right | Identical cover, "004" (note F3: trailing space in the series name) |
| 12 | Hex11 004 (2015) (Digital) (DR & Quinch-Empire).cbz | Hex11 #4, 2015, HexComix (494842) | right | Identical cover, "#4" in the logo; CV has two Hex11 volumes, the 2015 one was taken |
| 13 | EC Terror - Epitaphs from the Abyss 001 (2024) (digital) (DrVink-HD-DCP).cbz | EC: Epitaphs from the Abyss #1, 2024, Oni Press (1064316) | right | Identical cover (same art, brighter scan) |
| 14 | Fantasy World of Bettie Page 002 (2017) (digital-Empire).cbz | Fantasy World of Bettie Page #2, 2017 (volume 2016), TidalWave (580834) | right | Identical cover, "2" |
| 15 | Project ARKA - Into the Dark Unknown (2023) (digital) (Mr Norrell-Empire).cbz | Project ARKA: Into the Dark Unknown #1, 2023, Humanoids, one-issue volume (1002668) | right | Identical cover (graphic novel) |

Rules seen: year 12, unnumbered 3 (rows 6, 9, 15). Cover accepted on page 1 for 14 rows, page 2 for row 8. No same-name wrong-run, variant-vs-other-issue or collection-vs-single case among the 15.

## VerseDB - 23 would-write rows

| # | File | Matched issue (VerseDB id) | Verdict | Reason |
|---|---|---|---|---|
| 1 | Nenetl of the Forgotten Spirits 003 (2015) (Digital) (DR & Quinch-Empire).cbz | Nenetl of the Forgotten Spirits #3, 2015, Greentea (142309) | right | Identical cover, "Part Three" |
| 2 | Hope Falls 002 (2007) (Digital) (DR & Quinch-Empire).cbz | Hope Falls #2, 2007, AAM/Markosia (283779) | right | Identical cover, "2", Dec 2007 |
| 3 | Batman - Justice Buster 003 (2023) (digital) (Son of Ultron-Empire).cbz | Batman: Justice Buster #3, 2023, DC (423753) | right | Identical cover, "Chapter Three" |
| 4 | Mister X - Condemned 04 (of 4) (c2c) (2009) (Archangel-DCP).cbz | Mister X: Condemned #4, 2009, Dark Horse (235200) | right | Identical cover, "Part 4 of four" |
| 5 | La Muerta (Chapter 08) - Primeval 001 (2022) (Digital) (DR & Quinch-Empire).cbz | La Muerta: Primeval #1, 2022, Coffin Comics (576183) | right | Identical cover, "Chapter 8", "#1 Primeval" (note F5) |
| 6 | Naja 04 (of 10) (2014) (Digital) (BlurPixel-Empire).cbz | Naja #4, 2014, Magnetic Press (533569) | right | Identical cover, "4" in the logo |
| 7 | La Muerta (Chapter 07) - Onslaught 001 (2021) (Digital) (DR & Quinch-Empire).cbz | La Muerta: Onslaught #1, 2021, Coffin Comics (575141) | right | Identical cover, "7", "#1 Onslaught" (note F5) |
| 8 | Robotech - Clone 004 (1995) (F) (1920px).cbz | Robotech Clone #4, 1995, Academy (136032) | right | Identical cover, "4" |
| 9 | Distant Worlds 05 (2017).cbz | Distant Worlds #5, 2017, Europe Comics (859630) | right | Identical cover, "Episode 5" |
| 10 | Youth² 001 (2021) (Digital-Empire).cbz | Youth #1, 2021, Self Published (408158), matched by alias | right | Identical art, "N 1", "Badlands"; VerseDB's series name is "Youth" (see F5) |
| 11 | Buffy the Last Vampire Slayer - The Lost Summers (2023) (Digital-Empire).cbz | Buffy the Last Vampire Slayer: The Lost Summers #1, 2023, Boom! (426748) | right | Identical cover; unnumbered book matched to its single-issue series |
| 12 | Omega Kids 003 (2026) (Digital) (Kileko-Empire).cbz | Omega Kids #3, 2026, Marvel (83898) | right | Same art, "3"; matched copy is the direct edition with a barcode (existing Year 2025 vs 2026, see F5) |
| 13 | Trick 'R Treat 01 (of 04) (2009) (digital-Empire).cbz | Trick 'r Treat #1, 2009, DC/Wildstorm (412427) | right | Identical cover, "#1 of 4, Oct 09" |
| 14 | Robotech - Clone 002 (1995) (F) (1920px).cbz | Robotech Clone #2, 1995, Academy (136030) | right | Identical cover, "2" |
| 15 | Lady Death Origins 009 (2015) (Digital) (Kingpin-Empire).cbz | Lady Death Origins #9, 2015, Avatar (215920) | right | Identical cover, "09" |
| 16 | Blood Sword Dynasty 030 (1992.Jademan) (rescan).cbz | Blood Sword Dynasty #30, 1992, Jademan (602074) | right | Identical cover (rescan), "30"; folder-year rule |
| 17 | Destiny, NY 008 (2019) (digital-Empire).cbz | Destiny, NY #8, 2019, Space Between (370746) | right | Identical cover, "#8" |
| 18 | The King in Yellow (2015) (digital-Empire).cbz | The King in Yellow #1, 2015, SelfMadeHero (537706) | right | Identical cover; unnumbered graphic novel |
| 19 | Robotech II - The Sentinels Book II 007 (1991) (1920px).cbz | Robotech II: The Sentinels - Book II #7, 1991, Eternity (322366) | right | Identical cover, "Book Two", "#7" |
| 20 | Tarot Witch of the Black Rose 040 (2006) (2 covers) (Digital) (Tyrant Lizard King-EMPIRE).cbz | Tarot: Witch of the Black Rose #40, 2006, Broadsword (497159) | right | Page 1 is cover A; accepted on page 2, the "Lover's Card" variant. Same issue (#40, Sept), file says "2 covers" |
| 21 | Kajko i Kokosz 003.cbz | Kajko i Kokosz #3, Polish original, no year, no publisher (933010), `yearless_bd` | right (note F4) | Same album art and "Part 3"; the file is the Russian translation (Zolotoy kubok, "Chast 3"), the matched record is the Polish original (Zloty puchar, "Czesc 3"). Same album; the language differs by design |
| 22 | Ninjak - The Complete Classic Omnibus (part 1 of 2) (2018) (digital) (Verbal-DCP).cbz | Ninjak: The Complete Classic Omnibus #1, 2018, Valiant (562292) | right (note F2) | Identical omnibus cover; the file is half of the one omnibus record, so Number 1 holds, but see F2 |
| 23 | Nottingham 014 (2024) (digital) (Knight Ripper-Empire).cbz | Nottingham #14, 2024, Mad Cave (406594) | right | Identical cover, "#14" |

Rules seen: year 18, unnumbered 3 (rows 11, 18, 22), folder_year 1 (row 16), yearless_bd 1 (row 21). Cover accepted on page 1 for 22 rows, page 2 for row 20. The only `!BD` row is 21. No same-name wrong-run, collection-vs-single or different-issue-variant case turned up; the two variant cases (rows 20 and the ComicVine Tarot row) were the same issue with another cover.

## Findings (flagged, not fixed)

- **F1 - ComicVine sample is capped at 15 by design (informational).** The run ended at 77 of 200 sampled comics because the name search used its own hourly allowance for the `issue` detail read (15 an hour, per the brief). That allowance also caps would-writes at about 15 an hour once the source is on. The 15 rows above are every would-write it produced; a larger ComicVine sample needs another run an hour later (the fixed seed re-asks the same first comics, so it would need a different `--limit` or seed). Offered, not run.
- **F2 - Minor, latent: the `unnumbered` guard does not see a bracketed "(part N of M)".** `metron.unnumbered_book` (used by the ComicVine search and VerseDB) strips bracketed text before looking for part/vol/chapter words and only refuses an "(of N)" it finds on its own. Demonstrated on a copy of its logic: both "Ninjak ... Omnibus (part 1 of 2) (2018)" and "... (part 2 of 2) (2018)" pass as unnumbered and would be searched as issue 1; unbracketed "part 2 of 2" is refused. Row 22 is the part-1 file and came out right by coincidence. Its sibling "(part 2 of 2)" is in the catalog too and would be given Number 1 of the same omnibus record if its first pages pass the cover check. The catalog holds 6 files with a bracketed "(part N of M)". Not seen wrong in this sample; Ender's call whether the guard should refuse them.
- **F3 - Minor, cosmetic: ComicVine's volume name can carry a trailing space.** Row 11 would write Series "Blade: First Bite Infinity Comic " (trailing space, visible as a double space before "#4" in the CSV). Written as-is when the Series is empty.
- **F4 - Minor, by design (Sergei's call): a Russian-edition `!BD` file takes the Polish original's Title.** Row 21 would fill Series "Kajko i Kokosz", Number 3, Title "Zloty Puchar. Czesc 3" (Polish) and Web onto a file whose cover is the Russian translation. The brief says `!BD` files are translations of the matched edition and Year/Publisher are left out for them, so this is the documented behaviour; flagging it because Sergei named the edition-language case.
- **F5 - Minor, the listing does not show replacements.** The `fills` column lists what would be filled into empty fields; the real pipeline can also replace a value the in-book tiers wrote (`automatic.external_plan`, `replaceable`), which the listing does not model. Where the source's value differs from existing ComicInfo, a replacement would be visible: VerseDB row 5 and 7 (Series "La Muerta" to "La Muerta: Primeval"/"Onslaught", Title "Primeval"/"Onslaught" to "La Muerta Chapter 08"/"Chapter 7" - the new Title is worse), row 10 (Series "Youth Season Two" to "Youth", Publisher "Curt Pires" to "Self Published"), row 12 (Year 2025 to 2026), row 17 (Number "008" to "8"), rows 8/14/19/20 and ComicVine rows 1/2/3/11/13 (hyphen-style Series to the source's colon style). Whether those old values count as in-book-written I could not tell from the listing; the issue identity is right in every case.
- **F6 - environment note.** The brief said the live app was closed. At 08:44:30 (a minute before my runs) a packaged `ComicMetadata.exe` with engine Python from the `rc-064` build was running (four processes). I did not touch it; when I looked again at about 09:20 it was gone. The live `catalog.sqlite`, its WAL (0 bytes), `config.json` and `.env` were not modified (catalog last written 2026-11-17 22:39); only the `-shm` file's time moved, which is a read-only open's footprint. Neither source is switched on in the live config, so it did not meet my request ledger.

Pattern alerts: none.

## Verdicts (sample bar only; Sergei decides the switch)

- **ComicVine name search: GO.** 15 would-write, 15 right, 0 wrong, 0 unsure. Caveat: 15 is a small look (F1).
- **VerseDB: GO.** 23 would-write, 23 right, 0 wrong, 0 unsure.
- Neither verdict covers F2 to F5, which are Minor and not Blockers; F2 and F5 are worth Ender's look before either source runs over the whole library.

## Cleanup

Both output folders (`I:/AI Projects/Temp/futaba-cv-sample`, `I:/AI Projects/Temp/futaba-vdb-sample`, each with a ~270 MB catalog copy) and my scratch (`I:/AI Projects/Temp/futaba-scratch`: logs, helper scripts, cover pictures) were removed through `node scripts/studio-sweep.mjs --apply --approved ...` (Sergei's 2026-11-15 cleanup ruling cited; 66 files, 522.96 MB; `I:/AI Projects/Temp` is empty again); both tool processes had already exited. Nothing was committed. Personal-folder listing: not taken (superseded 2026-11-15; everything I wrote was under `I:/AI Projects/Temp`).
