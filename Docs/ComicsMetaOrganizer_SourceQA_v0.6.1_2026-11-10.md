# Comics Meta Organizer 0.6.1 — focused source QA, November 10, 2026

**Verdict:** GO

Scope: focused source regression and a bounded read-only collection-identity sample only. This does not certify a packaged release, native app, automatic write results, population-wide match precision or exact physical/digital edition identifiers.

## Pinned source and checks

- Source commit: `500df00b4e2f19f036d28ed059cc2c4ffa09a6a4`, version `0.6.1`. Tested an independent `git archive` copy, never the shared working tree.
- Source archive SHA-256: `936da80049f7c606195e4eeede82e756cbc0a1525e6ab4f70a4accead7048719`. All 331 archived source files matched their archive bytes after testing; zero added files remained.
- Python: `3.14.10 (tags/v3.14.10:b703b2c, Oct 25 2026, 17:36:52) [MSC v.1944 64 bit (AMD64)]`; executable `C:/Python314/python.exe`, SHA-256 `d718435b892db4ad5b547d12fec61be7baa7faf7a58d857ea58053be24c7a000`. Pillow `12.2.0` was used only for independent static sample inspection.
- Invocation from the archived source root: `C:/Python314/python.exe -B tests/run_naming_checks.py --scratch <archived-source>/scratch/qa-checks`.
- Result: **100 tests passed; zero failures, errors or skips; exit 0**. unittest reported 3.021 s; runner reported 3.825 s including discovery. One independent run; no duplicate retry.
- Full discovery loaded real live-state isolation before application imports; filtering followed discovery and the live-state sentinel was last. Source runner forbids descendants and has a fixed 600000 ms watchdog. No formal qa-entry receipt was produced.
- Actual app parser, research identity refresh, GCD lookup and Metron integration are exercised, along with legacy cached identity, embedded overrides, unique editions, HC/TPB non-equivalence, issue-date requirement, language/Legends/Count guards, pointer-switch provenance and wake-once source stamps.

Git-archived LF byte hashes (working-copy CRLF hashes can differ):

| File | SHA-256 |
|---|---|
| `app.py` | `bca8da7dbccc016e847e844ea741b6cdfa9d2f630a11ae3dfbb2d6a5eaf7ea07` |
| `research.py` | `41cb9918cc67bc9de8c0e0dd047f4752b03721653b7472b5c5d1472c7fd3d985` |
| `gcd_matching.py` | `d9d811ee241e9d9b6a822ee198fd14b20233677d0a1d5e562cde9586bd4b68b1` |
| `gcd_offline.py` | `badf157008f8c6f8c2ae51ed7c159e9baabb17f75728445dfff8ac5f48e65e5c` |
| `metron.py` | `8b87aad2dba391b4ff8858806684f49e6151975ed76859d89b7b1c3c24149747` |
| `filename_identity.py` | `708dab3e3fc3ac53c7bb611dc4aece2a02ee03b87512ccf94cb663ae06f9cc53` |
| `tests/run_naming_checks.py` | `a343eb6948c6b51a84f0b6908972112d1276fe5b9cef2957b5350010857672bc` |
| `tests/test_filename_matching.py` | `a4579d6ad9d549f03925bd3634454cea8fafb09bfe37226e0afb9f7e8517e7e0` |
| `tests/test_metron_year_rules.py` | `746b5b248fa88f7acd597a476d2357c5bf101881da8751b1757ad7d174233f18` |

## Independent collection sample

The selection was supplied before archive inspection: all nine masked-control disagreements plus the first three new Vol and first three new Book candidates in the developer's path-ordered eligible-missing pass. This is a deterministic syntax/identity check, not a random precision estimate. Exact IDs and candidate records are also in `ComicsMetaOrganizer_NamingFixes_2026-11-10.md`.

Read-only catalog/index access used SQLite URI `mode=ro` and `PRAGMA query_only=ON`. Index: `C:/Users/AnGeLZzZ/AppData/Local/ComicsMeta/data/gcd-offline/index-1b1c9f01cf924fcf9f1582f60db02ed0.sqlite`, October 16 dump. Catalog: sibling `catalog.sqlite`. Query each exact catalog ID for its source path; GCD IDs below identify the proposed issue record. No library directory walk.

For each exact CBZ, stdlib ZipFile read only stored/deflated unencrypted members, at most 20 MiB expanded and 40 MiB compressed per image, one-MiB chunks, 40 million pixels maximum, raster decoder allow-list; optional ComicInfo was limited to one MiB with DTD/entity declarations rejected. Pillow decoded first frames to private resized JPEGs. No archive execution or external converter. The first three and last raster page were inspected for each of 15 archives (60 pages); the next adjacent page was inspected for ten of those same archives (10 more). No population expansion. Source size and nanosecond mtime were identical before/after every inspection. Sources were not copied or fully hashed.

Observed result: **15/15 collection titles agree** with the proposed records, **13/15 also print the expected volume/Book number** in the selected pages. The two Ms. Marvel files print their matching collection subtitles but not the ordinal in inspected pages. No wrong collection identity was observed. All seven disputed old single-issue ComicVine controls visibly contain collections; their prior metadata cannot serve as independent collection ground truth.

Publication year was independently printed as publication text for five sampled volumes: Snotgirl 1–4 and Star Wars Adventures 3. These five years agree with GCD; this is not a month/day precision claim. Copyright-only statements elsewhere were not treated as publication dates. Physical binding/print/digital edition identity was not established across the sample.

Star Wars Adventures 3 explicitly has digital eISBN `9781684064809`, while the GCD candidate carries print ISBN `1684052491`. This confirms the same titled collection, not identical ISBN editions. Senua confirmed that the inherited approved GCD field mapping can fill absent identifiers from its print record; existing human/external XML stays protected. This source change does not create that policy and this QA does not claim exact-edition precision. No blanket new ISBN requirement was inferred.

| Catalog ID | GCD issue | Observed collection | Explicit volume/Book | Source size | Source mtime ns |
|---:|---:|---|---|---:|---:|
| 13402 | 640117 | Ms. Marvel: Operation Lightning Storm | subtitle only | 503648743 | 1750152781258140400 |
| 13407 | 979029 | Ms. Marvel: War of the Marvels | subtitle only | 347775608 | 1750152639246990400 |
| 32836 | 1676735 | Snotgirl: Green Hair Don't Care | 1 | 169327132 | 1767883937541759000 |
| 32837 | 1810615 | Snotgirl: California Screaming | 2 | 158382607 | 1767883939661129500 |
| 32838 | 2632554 | Snotgirl: Is This Real Life? | 3 | 140290220 | 1767883941438483800 |
| 32839 | 2756738 | Snotgirl: Make It Make Sense | 4 | 380675225 | 1767883943609173200 |
| 33400 | 2742154 | Star Trek: Defiant: The Stars of Home | 4 | 363184846 | 1767863317417995400 |
| 33756 | 2489028 | Star Wars: Bounty Hunters: The Raid on the Vermillion | 5 | 145431729 | 1767881432474028400 |
| 34600 | 1872037 | Star Wars Adventures: Endangered | 3 | 92491060 | 1767898624764183600 |
| 7611 | 2816979 | Batgirl: Bloodlines | 2 | 542104742 | 1774726464557692300 |
| 7727 | 2514686 | Batman: Failsafe | 1 | 792101597 | 1743748863192745800 |
| 7728 | 2563250 | Batman: The Bat-Man of Gotham | 2 | 1074300464 | 1767629104906095000 |
| 7663 | 2658086 | Batman by Grant Morrison: Book One | 1 | 1633441313 | 1767628763356745200 |
| 40245 | 2869357 | Batman by Grant Morrison: Book Three | 3 | 1672921884 | 1792769079341528800 |
| 8904 | 1734642 | Harley Quinn: Rebirth Deluxe Edition Book One | 1 | 481446201 | 1767631200898454000 |

Reproduction: use the exact catalog/GCD ID pairs and the member ordering above (case-folded archive entry name), compare visible cover/title/indicia with candidate Series/Number/Title, and record uncertainty separately from agreement. Static images and raw embedded metadata were temporary inspection data; no copyrighted pages are retained in the repository.

## Limitations and closure

- No installer build, native launch, updater, full declared build checks, real writeback or live worker restart was performed. Existing installed 0.6.0 and live settings/catalog/library were not changed.
- The 601 developer candidate-stage opportunities are not 601 guaranteed or approved writes. This small sample cannot certify broad precision or resolve missing dates/ambiguous editions.
- Pattern alerts: none.
- Cleanup inventory: 435 owned files, 50,656,765 logical bytes, measured by recursively enumerating files in the exact owned `scratch/futaba-naming-20261110` root and summing file lengths. The transparent native PowerShell removal, with an exact resolved-path check, was rejected before launch by automatic execution policy with only `blocked by policy` supplied. The entire root remains; no alternate deletion was attempted. The separate empty Ender folder rejected by execution policy was not touched.
