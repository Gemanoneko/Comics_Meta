# Comics Meta Organizer: MangaBaka pilot (2026-11-18)

Ender. This was a read-only pilot. Nothing was written to any comic, the library, the live state folder or the live database. The pilot tools lived in scratch only and have been deleted. It builds on Makoto's `Team/Research/ComicsMetaOrganizer/MangaSources_2026-11-18.md`. Sergei decides what happens next.

## Short answer
- **The pool is 475 unidentified manga files, not 343.** They sit in 87 folders and cover about 60 series. Nobody recorded how the 343 was counted, so this pool uses the documented method in section 1.
- **MangaBaka would fill 92 of the 475 with 0 wrong, run the way the app would run it.** With a hand-corrected title, it would fill 97. That is 0.5% of the 16,926 unidentified comics.
- **Three series account for 67 of the 92:** The Drops of God (44), Blade of the Immortal (12) and Lone Wolf and Cub (11).
- **Coverage is the limit, not the cover gate.** 36 of the 59 series have no volume covers on MangaBaka. US floppy issues of manga, which make up half the pool, never match tankōbon covers.
- **Cost:** about 15 minutes of background time once, but only if the source is restricted to known manga. Without that restriction it is hours of searching.
- **Recommendation:** don't build a permanent source. If Sergei wants these comics, a one-off batch is the cheap route (section 4).

## 1. Counts

| Pool | Files | Method |
|---|---|---|
| Unidentified comics | 16,926 | Comics present in the live catalog (read once through an escaped `mode=ro` URI) whose ComicInfo Web and Notes cite none of Metron, GCD, ComicVine or VerseDB. This is the app's own `comicvine_search.CITES` pattern. |
| **Manga among them (the pool)** | **475** (87 folders) | Detector, then a hand label on every flagged folder (below). "Manga" means Japanese, Korean or Chinese comics in any edition. Western books drawn in a manga style are excluded (Adam Warren's Dirty Pair and Bubblegum Crisis, Ronin Rising Manga Edition, Mangaverse). |
| Book-volume number in the file name | **239** | A `v01`, `Vol.`, `Volume`, `Book` or `Том` label with no issue or chapter number after it. |
| Issue or chapter number only | **219** | US floppies (Oh My Goddess Part II #01, Shadow Lady #01, Blade of the Immortal 130), chapter splits (Batman: Justice Buster 001-032, Banya v01 01) and series-run labels (`Venus Wars v1 #01`). |
| Neither | **17** | One-shots and artbooks (Japan, Kwaidan, Akira Manga Artbook, Tokyopop Star Wars Manga Black and Silver). |
| Russian-only (Cyrillic) title | **0** | Cyrillic letters in the name and no Latin letters in the cleaned title. Across all 16,926 unidentified comics there are only 4 such names, all in the Russian fan comic `Зайчик`, which is not manga. The earlier "41 Russian" figure has no recorded method either. |

**Manga detection.**
1. I downloaded MangaBaka's nightly dump once (`series.jsonl.zst`, 393 MB). The licence names the dump as the route for bulk use. I built a local title index of 308,207 active series in all languages and deleted the dump afterwards.
2. Each unidentified comic was flagged on one of three signals:
   - Its series, file or folder title matches a manga, manhwa or manhua title and the publishers agree. Publisher hints come from `!Publisher` folders, `(Publisher)` groups and ComicInfo Publisher.
   - A local signal: ComicInfo `Manga=Yes`, a manga genre, a "manga/manhwa/манга/mangalib" word in the path, a manga publisher, or Russian `Том … Глава` naming.
   - The title alone matches a series that has an English publisher.
3. I reviewed every flagged folder by hand: 250 folders with a strong signal and 356 with a title match only. 87 of them are manga.

**Positive control.** I wrote down 24 known manga folders (429 files, identified and unidentified) before the detector ran. The detector flagged 419 of them (97.7%). It missed 3x3 Eyes (5 files), Digimon (4) and Appleseed Databook (1). Only the Appleseed Databook was unidentified, and I added it by hand.

**Negative control.** Out of 2,000 Metron-identified Marvel, DC and Image comics, the detector flagged 117 (5.9%). Examples: "Batman" matches *Bat-Manga!* (also DC), and "Star Wars" matches the Star Wars manga. The automatic detector alone is therefore not precise enough, which is why the folder labels are hand-made.

## 2. Pilot

**Method.**
- **Search:** one search per title derived from the file name, the way the app would see it. The pool produced 73 queries. Search used `/v1/series/search` with type manga, manhwa, manhua or oel.
- **Pick:** the first result with an exact title match (any language or alias), otherwise the top result.
- **Covers:** `/v1/series/{id}/images?type=volume` gave the covers. A book-volume file was compared with that volume's covers in every language, English first. A file without a volume number was compared with every English volume cover.
- **Gate:** CMO's real gate, `cover_match.compare`, on archive images 1-3, as `archive_match` does with `cover_rule_v2` on. The code is identical to tag v0.6.5, which Sergei runs.
- **"Right":** the picked series equals the hand-verified MangaBaka series for that title, and the accepted cover's volume number equals the file's.

**Picks.** Of the 73 queries:
- 55 had an exact title match and 9 fell back to the top result.
- 9 returned nothing: titles garbled by scan tags (`Blade Of The Immortal 130 Greengiant-DCP`), artbooks, and Shadow Lady Dangerous Love.
- 4 picks were wrong, affecting 13 files. "A New Hope", "Return of the Jedi" and "The Empire Strikes Back" picked a generic "Star Wars" manhwa. "Japan" picked Eiji Ootsuka's *Japan* instead of Buronson and Okamura's. All 4 wrong series had no volume covers, so nothing could be accepted.

| Outcome (files) | As the app would run it | Best case (hand-corrected series) | Book volume (239) | No book volume (236) |
|---|---|---|---|---|
| **Matched, right** | **92** | **97** | 87 | 5 |
| Wrong | **0** | **0** | 0 | 0 |
| Refused (a cover exists but the gate said no) | 122 | 125 | 43 | 79 |
| No cover available | 251 | 251 | 109 | 142 |
| Not found | 10 | 2 | 0 | 10 |

**By series (app run).**
- The Drops of God: 44 of 44.
- Blade of the Immortal TPBs: 12 of 16.
- Lone Wolf and Cub: 11 of 28.
- MPD-Psycho: 4 of 5.
- Banya: 4 of 15.
- Akira: 3 of 7.
- Eden: 3 of 3.
- Star Wars: A New Hope manga issues: 3 of 5.
- Old Boy: 2 of 2.
- Berserk, Kurosagi, Mother Sarah, Atom: The Beginning, Gannibal and Gantz: 1 each.
- Oh My Goddess: 0 of 66. They are all US floppies, and MangaBaka has only tankōbon covers.
- No volume covers at all: Batman: Justice Buster (32 files), Path of the Assassin (30), Superman vs. Meshi (23), Venus Wars (20), Gunsmith Cats (13), Samurai Executioner (10), New Lone Wolf and Cub (8), Vampire Hunter D (8), You're Under Arrest (7) and 27 smaller series.
- Shadow Lady (25 floppies) has only 3 Japanese covers.
- Covers seen by language: 93 of the 98 accepted covers were English.

**Correctness checks.**
- *Automatic:* all 92 (97) matches have the hand-verified series and the right volume number.
- *By eye:* 20 matched pairs, a seeded random sample, were laid side by side. All 20 show the same cover. They include 3 wraparound scans, 4 framing differences, and the US floppies Ghost in the Shell 1.5 #2 and Star Wars: A New Hope #1 and #2.
- *Hard negatives:* every matched file was compared with the same series' covers for other volumes, using covers already downloaded. That was 82 files against 5,296 covers in all languages, on the archive page that held the true match, and the gate accepted **0**. A further 3,740 comparisons of floppy covers against every English tankōbon cover of the right series accepted only 5, and all 5 are right.
- *Refusals (122):*
  - 79 are floppies or chapter splits compared against tankōbon covers, which is expected.
  - 12 are volumes where MangaBaka has only Japanese or Korean covers.
  - 31 are volumes that do have an English cover. I looked at 7 of them. Some are a different edition: the 1995 Appleseed against MangaBaka's later cover, and a Blade of the Immortal "Book 12" whose first page is a US floppy cover. The others are gate misses on the same cover: Lone Wolf wraparound scans that include the spine (volumes 1 and 4), and a dark scan of Blade of the Immortal Book 01. So these cost recall, not precision.

**MangaBaka's published pHash.** MangaBaka publishes a 64-bit pHash for every cover.
- A pure-Pillow pHash, which the app's runtime can run without numpy, reproduces MangaBaka's value: median distance 0 bits, maximum 2 (n=20).
- True pairs (the file's page against MangaBaka's hash): median 2, with 18 of 20 at 10 or below. The two outliers, at 22 and 32, are a wraparound and a framing difference.
- Same-series covers for other volumes: n=681, minimum distance 12, none at 10 or below.

So a pHash check against the published hashes could choose the cover to download, about one per file. The full gate would still be needed for wraparounds. The search endpoint also takes a `phash=` parameter, which I did not test.

**Traffic.**

| Traffic | Count | Peak per 60 s | Limit |
|---|---|---|---|
| Search requests | 74 (73 + 1 probe) | 18 | 30 |
| Other API requests (image lists) | 73 (72 + 1 probe) | 18 | 180 |
| Cover thumbnails (350 px CDN) | 377 (10.7 MB, about 28 KB each) | 60 | none stated |

- All 147 API requests and all 377 thumbnails answered 200. No refusal or 429 occurred.
- Other traffic: the dump (393 MB, rate-limited to 8 MB/s, plus its sha1) and three documentation pages (the API spec, the developer docs and the dumps page).
- The thumbnails were deleted with the scratch folder, as covers are third-party data under the licence.

## 3. Estimate

**What it would fill.**
- 92 comics as built, or 97 with better titles. If the gate's recall misses were fixed (the 31 refused with an English cover present), the ceiling is about 125.
- Fields: identity (series, volume number, MangaBaka link), authors and artists, the English publisher, genres and `Manga`.
- Nothing per volume: no release date, volume title, ISBN or page count. MangaBaka's works and editions endpoints are in beta and returned nothing for Berserk.
- A series description exists only at series level (check against SYNOPSIS_POLICY).

**How much it would slow the app (measured on this machine).**
- Unit costs: an API call takes 157 ms (median), one gate comparison 119 ms (pure Python, up to 3 pages), reading a comic's first 3 images 36 ms.
- *Manga pool only, book volumes only:*
  - 73 searches and about 60 image lists take about 8 minutes of waiting at a 3.5 s spacing.
  - 285 thumbnails take about 5 minutes at one per second.
  - CPU is about 35 s for 291 comparisons plus about 9 s of reads.
  - That is roughly 15 minutes of a background source's time, once. Afterwards only new manga cost anything.
- *Including floppies against every cover, as tested:* another 3,740 comparisons, about 7.5 minutes of CPU, for 5 more matches. A real source should skip files without a book-volume number.
- *Without a manga filter (all 16,926 unidentified):*
  - 9,791 distinct series names need at least 5.4 hours of searching at the hard 30-per-minute cap, or about 11 hours at a polite 15 per minute.
  - 4,750 of those files share a title with some MangaBaka series. Each would also cost image lists and downloads before the gate refused it.
  - Source pacing currently blocks the discovery thread (Senua's S3), so this would add hours to a pass. A manga filter is mandatory.
  - The dump index used here works offline but is 393 MB and refreshed nightly, which is too heavy to ship. A hand-kept list of manga folders is the practical filter.
- I don't have the other agent's pass-time figures, so these are absolute times, not percentages.

## 4. Recommendation (Sergei decides)
- **A. Skip.** About 95 comics, mostly 3 series. The licence question about writing fields into files is still open: MangaBaka data is CC BY-NC-SA, covers are third-party, and the licence says nothing about file writes. For comparison, the ComicVine name search fills about 850 and VerseDB about 400.
- **B. One-off batch (my pick, if he wants these comics).** Run this pilot's logic once over the 87 labelled folders, book volumes only, as a would-write listing for Futaba's sample. Then write the roughly 92 to 97 verified identities with a MangaBaka credit in Notes. Before any write, send MangaBaka one email asking about the licence (Makoto's suggestion). There is no permanent source, no new pacing and no effect on the app's pass.
- **C. Permanent source** that uses a manga folder list as its filter. This is only worth it if Sergei keeps adding English tankōbon manga.
- Whichever he picks, the gate is safe for MangaBaka covers: 0 wrong out of 97 accepts and 0 accepted out of 5,296 covers of other volumes in the same series.

## Notes
- The live catalog was read once through an escaped `mode=ro` URI. The read took 0.2 s and made no copy of the database.
- Comics were opened read-only through `reverse_image.open_shared`, which shares read, write and delete. A comic would have been skipped if the app was rewriting it at that moment (`.metadata-tmp` present), but none were.
- The gate code was imported from the CMO checkout with `-B` and a scratch state root. It ran on a scratch copy of the bundled Python after the first 150 files.
- The gate's pure-Python work used about an hour of single-core CPU in total while another agent was measuring the app: about 11 minutes for the gate stage and about 40 minutes for the hard-negative tests. A small amount of CPU contention is possible.
  - The first hard-negative run's output was lost when the tool moved it to the background, and its process kept running as an orphan. I killed it (PID 52776) and reran the test with its output going to a file.
- Python and `__pycache__`:
  - Three early one-line checks ran the toolchain's bundled Python without `-B`: `import PIL`, `import json` and `import compression.zstd`. The standard library is inside `python314.zip`, so the second and third could not write anything.
  - The only `__pycache__` in the runtime is `Lib/site-packages/PIL/__pycache__`, timestamped 11:22:45. My PIL check ran at about 11:52, so that folder was there first and is not mine.
  - From the coordinator's note onward, everything ran on a scratch copy of the runtime, made without `__pycache__`.
- No CMO code changed and nothing was committed. This report is uncommitted.

## Appendix: the 475-file manga pool (hand labels)
The folders I labelled manga, with the number of unidentified files in each, the hand-verified MangaBaka series id, and the best-case matched count. A one-off batch (option B) or a folder filter (option C) would start from this list. Folders whose MangaBaka series is "none" are not in MangaBaka's manga, manhwa, manhua or oel types.

| Folder (under the library root) | Files | MangaBaka id | Matched (best case) |
|---|---|---|---|
| `!Dark Horse\Akira (TPB) (Dark Horse)` | 8 | 5317 | 3 |
| `!Dark Horse\Appleseed Book (TPB) (Dark Horse)` | 4 | 19000 | 0 |
| `!Dark Horse\Banya The Explosive Delivery Man` | 15 | 10655 | 4 |
| `!Dark Horse\Berserk v1 (Dark Horse)` | 1 | 1692 | 1 |
| `!Dark Horse\Blade of the Immortal` | 18 | 5246 | 12 |
| `!Dark Horse\Cannon God Exaxxion (TPBs) (Dark Horse)` | 3 | 12767 | 0 |
| `!Dark Horse\Caravan Kidd` | 3 | 14314 | 0 |
| `!Dark Horse\Drakuun (TPBs) (Dark Horse)` | 4 | 23959 | 0 |
| `!Dark Horse\Eden - It's an Endless World (TPBs) (Dark Horse)` | 3 | 12038 | 3 |
| `!Dark Horse\Gantz (TPB) (Dark Horse)` | 2 | 4781 | 1 |
| `!Dark Horse\Ghost in the Shell` | 2 | 29386 | 2 |
| `!Dark Horse\Ghost Talker's Daydream (TPB) (Dark Horse)` | 2 | 12668 | 0 |
| `!Dark Horse\Godzilla v1 (Dark Horse)` | 1 | 28916 | 0 |
| `!Dark Horse\Gunsmith Cats` | 16 | 1578, 14905 | 0 |
| `!Dark Horse\Japan (TPB) (Dark Horse)` | 1 | 20120 | 0 |
| `!Dark Horse\Katsuya Terada's The Monkey King (TPB) (Dark Horse)` | 1 | 45825 | 0 |
| `!Dark Horse\Kurosagi Corpse Delivery Service (TPB) (Dark Horse)` | 1 | 4387 | 1 |
| `!Dark Horse\Kwaidan (TPB) (Dark Horse)` | 1 | 91298 | 0 |
| `!Dark Horse\Lady Snowblood (TPBs) (Dark Horse)` | 4 | 13236 | 0 |
| `!Dark Horse\Legend of Mother Sarah` | 1 | 17436 | 1 |
| `!Dark Horse\Lone Wolf\Lone Wolf & Cub (TPBs) (Dark Horse)` | 28 | 14288 | 11 |
| `!Dark Horse\Mail (TPB) (Dark Horse)` | 1 | 28943 | 0 |
| `!Dark Horse\MPD-Psycho (TPBs) (Dark Horse)` | 5 | 492 | 4 |
| `!Dark Horse\Oh My Goddess! Part` | 66 | 9427 | 0 |
| `!Dark Horse\Old Boy` | 2 | 10571 | 2 |
| `!Dark Horse\Orion (Dark Horse)` | 4 | 28797 | 0 |
| `!Dark Horse\Path of the Assassin (TPBs) (Dark Horse)` | 15 | 18283 | 0 |
| `!Dark Horse\Ring (TPB) (Dark Horse)` | 1 | 24602 | 0 |
| `!Dark Horse\Samurai Executioner (TPB) (Dark Horse)` | 10 | 27897 | 0 |
| `!Dark Horse\Satsuma Gishiden (OGN) (Dark Horse)` | 1 | 34166 | 0 |
| `!Dark Horse\Shadow Lady` | 27 | 9036 | 0 |
| `!Dark Horse\Star Wars\Star Wars - A New Hope (Manga) (Dark Horse)` | 4 | 79490 | 3 |
| `!Dark Horse\Star Wars\Star Wars - Episode I - The Phantom Menace - Manga (TPB) (Dark Horse)` | 2 | 79496 | 0 |
| `!Dark Horse\Star Wars\Star Wars - Return of the Jedi (Manga) (TPBs) (Dark Horse)` | 4 | 79495 | 0 |
| `!Dark Horse\Star Wars\Star Wars - Star Wars - Episode I (Manga) (Dark Horse)` | 1 | 79496 | 0 |
| `!Dark Horse\Star Wars\Star Wars - The Empire Strikes Back (Manga) (TPBs) (Dark Horse)` | 4 | 79494 | 0 |
| `!Dark Horse\Venus Wars` | 20 | 29119 | 0 |
| `!Dark Horse\XS Hybrid` | 3 | 12110 | 0 |
| `!Dark Horse\You're Under Arrest` | 7 | 19321 | 0 |
| `!DC\Batman\Justice Buster` | 32 | 45887 | 0 |
| `!DC\Superman\Superman vs. Meshi` | 23 | 105177 | 0 |
| `!Titan Comics\Atom - The Beginning (2022-)` | 1 | 24283 | 1 |
| `!Titan Comics\Sherlock - A Study in Pink (2017)` | 1 | 15903 | 0 |
| `!Titan Comics\Sherlock - The Great Game (2017-)` | 1 | 15903 | 0 |
| `!Marvel Universe\Spider-Verse\Octo-Girl` | 1 | 933 | 0 |
| `!Comixology Originals\Seven Shakespeares (2018-)` | 16 | 13214 | 0 |
| `!Comixology Originals\The Drops of God (2019-)` | 44 | 13004 | 44 |
| `Gannibal` | 1 | 35229 | 1 |
| `Godzilla\Godzilla (Dark Horse Vol 1 - 1988) 01-06` | 1 | 28916 | 0 |
| `Savage\Savage Garden Omnibus` | 2 | 24055 | 0 |
| `Star Wars\Guardians of the Whills` | 1 | 86534 | 0 |
| `Star Wars\High Republic\Edge of Balance` | 1 | 106752 | 0 |
| `Star Wars\Star Wars Legends\[20XX - 20XX] Miniseries, One-Shots\Manga` | 14 | 79496, 79490, 79494, 79495 | 3 |
| `Star Wars\Star Wars Legends\[20XX - 20XX] Miniseries, One-Shots\Tokyopop` | 5 | 79490, 79494, 79495, 86533 | 0 |
| `Star Wars\Star Wars Rebels\Star Wars Rebels v01` | 1 | 8432 | 0 |
| `Lone Wolf and Cub\New Lone Wolf and Cub` | 8 | 27898 | 0 |
| `Path of the Assassin v01-15 (2006-2009)` | 15 | 18283 | 0 |
| `Vampire Hunter D` | 8 | 9208 | 0 |
| `World of Warcraft\World of Warcraft - Shadow Wing Vol. 1 - 2 (2010-2011)` | 2 | 27714 | 0 |
| `!Dark Horse\Appleseed Databook (TPB) (Dark Horse)` | 1 | none | 0 |
| **Total** | **475** | | **97** |
