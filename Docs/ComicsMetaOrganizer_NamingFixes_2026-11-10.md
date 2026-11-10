# Naming fixes — source handoff, November 10, 2026

Source base: `11ae3c64d4101969526e388ac9da331948dc4f57` (0.6.0). This handoff is source-only; no installer, formal entry receipt, installed-app or native UI certification is claimed. Sully owns the source milestone commit/version; Futaba owns independent checks on that pinned commit.

## Findings and changes

The live history showed 1,489 distinct updates on November 4, 23 on November 8 and 17 on November 9 (UTC), while the latter two days still ran 20,550 and 16,675 research checks. No identity-conflict/ComicVine hold records or readable pending/running write tickets were found. Bulk matching yield had declined; this was not evidence of an approval backlog. A separate possible historical stall remains unproved: progress/checks stopped November 9 at 19:27 UTC, but a heartbeat thread continued until the November 10 pause. No process was running at inspection; no restart or live fix was attempted.

Filename parsing failed to recognize padded underscore issues, retained collection volume/subtitle text inside the series name, misinterpreted Book numbering, and retained a demonstrated trailing scan-credit suffix. The source changes extend existing behavior:

- `filename_identity.py`: conservative terminal zero-padded underscore issue syntax; internal title digits and unpadded ambiguous underscores remain untouched. Exact `KFRONE HAMPTA` scanner suffix is removed only after an annotation boundary; unknown suffixes remain intact. Explicit single Vol/Book syntax is parsed separately; nested labels, parts/chapters and fan-made labels remain held.
- `app.py` delegates filename parsing. `research.py` refreshes unchanged legacy filename-derived catalog parsing in memory; deliberate catalog overrides and embedded metadata retain precedence. No migration, live catalog update or archive rewrite was performed by the team.
- `gcd_matching.py`: only after the old matcher finds neither candidates nor a matching series, a new collection-label fallback uses a shortened explicit Vol/Book series. It requires a book/collection record, corresponding volume number, an actual issue cover/sale year, exact subtitle agreement when present, and the existing unique-candidate gate. Explicit HC/TPB requires positive matching format evidence; generic collected-edition records do not prove HC/TPB equivalence. Existing matches/ambiguities are preserved.
- `gcd_offline.py` and `metron.py`: matching-code stamps wake prior misses once. GCD stamps include the captured active-index identity, so an index switch during lookup cannot label old-index evidence as new-index evidence. The source index is unchanged. Existing language/Legends, Count, GTIN, signature, backup, provenance and write verification guards remain.

No new global ISBN requirement is present. A temporary ISBN gate was removed before the final test run after Jane clarified that it would change the existing approved collection policy. Collection matching has no claim of statistical precision from the weak masked controls below; independent archive inspection is pending.

Cross-consumer grep: `app.parse_name` is used by scanning, fractional-number maintenance, recovery filename display and in-book comparison; `research.query_identity` feeds GCD, Metron, publisher/free/GetComics/provider searches, scheduling and verified-evidence cache identity. Build staging dynamically includes root Python modules, covering the new helper.

## Bounded measurements and limitations

Population: 11,742 catalog rows marked missing; after 201 filename-language exclusions and 744 Legends exclusions, 10,797 eligible rows. All queries used SQLite `mode=ro` plus `PRAGMA query_only=ON`. No archive contents, GPU, remote API or paid source was used during developer diagnosis.

Initial representative sample: six filename-shape/year strata, eight rows each, selected by ascending SHA-256 of the case-folded full path. Of 48 rows, 43 had no GCD series-key match, four had series but no qualifying issue/edition, and one correctly remained ambiguous. Saved discovery signatures matched catalog signatures for all 48; actual on-disk source signatures were not reread.

The broad terminal-underscore shape appeared on 247 eligible missing rows; an exploratory extraction yielded 161 unique candidates. The implemented padded-only grammar is narrower. Comparing the final filename/matcher behavior with unchanged original matching against the existing October 16 index yielded potential new unique candidates: **113 padded underscores, 412 Vol labels, 76 Book labels, zero scanner-suffix recoveries**. These 601 are candidate-stage opportunities, not approved/guaranteed writes. Existing live identity, provenance, signature and write gates were not executed. Unknown scanner suffixes, missing source titles, absent dates, nested editions and ambiguous candidates remain unresolved.

Independent masked-control method: select non-app-written embedded rows carrying ComicVine/Metron issue URLs and populated Series/Number/Year (2,413 rows; 240 with relevant syntax). Feed filename parsing alone to the matcher; do not leak the embedded identity through catalog parse columns. Of 34 newly recovered candidates, eight were underscore cases and all eight agreed on Series/Number/Year. Twenty-six were collection cases: 24 agreed on Series/Number, 17 agreed on all three. The other nine cannot be called a precision pass or automatically classified as wrong GCD editions. Two Ms. Marvel files use a subtitle series/#1 in ComicVine while GCD uses collection #3/#8. The other seven contain single-issue ComicVine titles/links on collection-labelled files; they are unreliable collection ground truth. None of these nine has embedded ISBN/GTIN proof. A bounded follow-up read of their metadata and exact GCD records confirmed these disagreements; no archive contents were inspected by Ender.

The first exploratory control pass incorrectly reused catalog columns populated from embedded metadata; its apparent precision is discarded. The corrected filename-only probe printed all counts and 34 new controls; printing an unrelated full mismatch list then hit a host cp1251 Unicode error. This is an output-format failure, not a successful precision certification. No broad probe was rerun after the bounded nine-case check.

## Focused verification

Final command, from the tool root:

```text
python -B tests/run_naming_checks.py --scratch "C:/Antigravity Projects/Studio Illuminati/WIP/Comics Meta Organizer/scratch/naming-fixes-20261110"
```

Final result: **100 tests, zero failures/errors/skips, 2.913 seconds** (3.682 seconds including discovery/startup), exit 0. The reusable runner first discovers the full suite, then filters the declared source modules; real state isolation loads first and its sentinel runs last. Process creation is refused and an in-process 600,000 ms watchdog bounds the run. No formal build gate is claimed.

Coverage includes repaired filenames, ordinary fractions/numbered titles, embedded/catalog override retention, cache identity and rules wake-once, actual-date requirement, collection versus ordinary issue, HC/TPB non-equivalence, ambiguous editions, language/Legends/Count preservation, pointer-switch provenance and existing research/scheduling/in-book controls. Earlier focused runs exposed an obsolete expectation that an underscore issue was never searched and a new fixture mistakenly defaulting an ordinary issue to book type. Only those fixture expectations/setup were corrected; final guards were not weakened to pass tests.

## Fifteen-row independent archive-inspection handoff

Catalog: `C:/Users/AnGeLZzZ/AppData/Local/ComicsMeta/data/catalog.sqlite`.
Index: `C:/Users/AnGeLZzZ/AppData/Local/ComicsMeta/data/gcd-offline/index-1b1c9f01cf924fcf9f1582f60db02ed0.sqlite`; dump October 16, 2026. Read both with mode=ro/query_only. Query exact catalog ID for full source path and catalog size/mtime; do not search or walk unrelated library folders. GCD IDs below identify exact issue records, whose series type is book/collected edition. No source file is changed by this handoff.

First nine rows are all masked-control disagreements. Last six are the first three new Vol and first three new Book candidates in the prior path-ordered eligible-missing pass; this is a deterministic balanced syntax check, not a random precision estimate.

| Catalog ID | GCD issue ID | Filename/identity to verify | GCD volume/year |
|---:|---:|---|---|
| 13402 | 640117 | Ms. Marvel — Operation: Lightning Storm | 3 / 2007 |
| 13407 | 979029 | Ms. Marvel — War of the Marvels | 8 / 2010 |
| 32836 | 1676735 | Snotgirl — Green Hair Don't Care | 1 / 2017 |
| 32837 | 1810615 | Snotgirl — California Screaming | 2 / 2018 |
| 32838 | 2632554 | Snotgirl — Is This Real Life? | 3 / 2020 |
| 32839 | 2756738 | Snotgirl — Make It Make Sense | 4 / 2025 |
| 33400 | 2742154 | Star Trek: Defiant — The Stars of Home | 4 / 2025 |
| 33756 | 2489028 | Star Wars: Bounty Hunters — The Raid on the Vermillion | 5 / 2023 |
| 34600 | 1872037 | Star Wars Adventures — Endangered | 3 / 2018 |
| 7611 | 2816979 | Batgirl — Bloodlines | 2 / 2026 |
| 7727 | 2514686 | Batman — Failsafe | 1 / 2023 |
| 7728 | 2563250 | Batman — The Bat-Man of Gotham | 2 / 2023 |
| 7663 | 2658086 | Batman by Grant Morrison — Book 1 | 1 / 2024 |
| 40245 | 2869357 | Batman by Grant Morrison — Book 3 | 3 / 2026 |
| 8904 | 1734642 | Harley Quinn: Rebirth Deluxe Edition — Book 1 | 1 / 2017 |

Safe extraction route: Python `C:/Python314/python.exe` has Pillow. Read each exact source with stdlib `ZipFile` only. Existing `reverse_image.read_image` demonstrates bounded stored/deflated reads: at most 20 MB decoded member bytes, 40 MB compressed member size, 1 MB read chunks. `reverse_image.thumbnail` enforces a raster decoder allow-list, 40-million-pixel ceiling and 480×720 output. For standalone QA, reproduce those bounds without importing a live app instance. Limit inspection to the first three and last raster page per comic initially (maximum 60 pages for 15 comics), and optional ComicInfo.xml at most 1 MB. Never execute archive content or external image decoders; no GPU/model/API. Source size/mtime before/after suffices for this read-only inspection; do not copy or fully hash multi-GB archives. Stop/report corrupt, unsupported or oversized members rather than expanding the bounds. Any private resized page evidence belongs to Futaba's owned scratch and must be cleaned after compact findings are retained.

## Ownership and cleanup

Developer did not start/restart/pause the app, change live settings/catalog/archives, refresh the dump, approve comics, use GPU/APIs, take focus, package, version, commit or push. Only the source/test files and this maintained handoff doc were changed. Test fixtures self-removed. The exact owned `scratch/naming-fixes-20261110` folder is empty (read-only enumeration returned no entries). A PowerShell command containing verified empty-folder removal was rejected by automatic execution policy before launch, with only "blocked by policy" supplied; no alternative deletion was attempted. That empty folder remains. Independent archive inspection and pinned-source QA remain Futaba's work.
