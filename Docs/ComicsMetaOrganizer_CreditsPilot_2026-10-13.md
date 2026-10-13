# Comics Meta Organizer — credits/indicia reader pilot, 2026-10-13

Futaba (QA). Measured against the live v0.1.3 build (tag `v0.1.3`, HEAD `1c34df251749aed9703f9689fe119a995a4f77fe`, model `gemma3:4b`, RTX 5080), during the away window Sergei stated at 2026-10-13 ("I'm off the computer now"). Read-only: no archive, catalog, config, quota, profile or Lens write by the pilot; no code fix; no git write.

This is a pilot measurement, not a release QA report, so it carries no GO / NO-GO line.

## 1. The answer

Sergei's rule: write Publisher only when the cover reading and the credits-pages reading agree.

| | Result against Metron truth |
|---|---|
| **Cover AND credits agree: precision** | **164/165 = 99.4%** (95% CI 96.7–100.0%) strict. **165/165 = 100%** (95% CI 97.8–100%) after I adjudicated the one miss as an imprint-label difference (section 4). |
| Same, with the credits tier's own gate also passing (indicia names this series and issue) | 47/48 = 97.9% (95% CI 88.9–99.9%) strict; 48/48 after the same adjudication (95% CI 92.6–100%). |
| How often they agree | 165 of the 1,878 Metron-verified comics = **8.8%** (48.7% of the 339 whose cover reading names a known publisher in full). With the gate: 48 = **2.6%**. |
| Cost | credits read 2.7 s, cover read 0.9 s, per comic (3.6 s together, GPU not shared). |

**The observed number clears the 99% bar. The confidence interval does not prove it.** With 165 agreements and zero real errors the 95% lower bound is 97.8%. Showing at least 99% at 95% confidence (exact, two-sided) needs about 370 error-free agreements; one-sided about 300. Nobody can claim "99%" from this pilot, only "99.4% observed, lower bound 96.7% strict / 97.8% adjudicated".

Recommendation (a recommendation only; Sergei decides) is in section 9. Short version: the agreement rule works as a veto. It is safe on the evidence we have, for the slice we could measure. Three things stop me calling it proven: the sample is the Metron-verified slice, not the comics the rule would actually write on; agreement can only ever happen for a small set of publishers; and one imprint convention (Image vs Skybound) needs Sergei's ruling first.

Everything else the credits tier writes is not safe: creators 42.5% correct, Year 23.5% correct on 2024–2026 books. Details in section 6.

## 2. What was run

**Truth.** The research evidence files (`data/research/evidence-*.json`) hold 1,878 comics with a `verified_evidence` result from Metron carrying Series, Number and Publisher, whose archive is a `.cbz` that exists now. Truth for every field is that Metron record. (No ComicVine or web row passed the filters; all 1,878 are Metron. The Metron match itself was scoped "Exact issue identity and cover verified", so the cover reading and the truth are not fully independent; see caveats.)

**The cover reading** is the one the live app already saved for each comic (`cover_identification`). I also re-read every cover fresh with the same code path (`local_model.identify_cover`); saved and fresh agree on the publisher in 322 of 341 comics (94.4%), and the conclusion holds with the fresh reading (cover == credits: 161/162 = 99.4%).

**The credits reading** is `local_model.read_credits` verbatim: pages 2–5 plus the last page, one prompt, JSON out. I left the model's raw text and all derived decisions in the results file.

**Two runs, one list of results.**

| Run | Comics | Selection |
|---|---|---|
| A (the ~100 asked for) | 104 | All 9 comics whose cover reading names the wrong publisher; 28 cover-right (≤4 per publisher); 46 cover-empty by round-robin across publishers (A spans all 35 publishers in the verified set, indie heavy; 6 Marvel in total); 9 collections (TPB/HC/GN/volume); 8 pre-2005; 4 extra Marvel. |
| B (extension, my call) | 299 | **Every other comic whose cover reading names a known publisher in full.** Run A took 3.5 s a comic, so the full census of that slice fitted well inside the 90-minute window. A + B contain all 339 such comics. |

Why B: agreement can only happen where the cover reading names a publisher, so that slice is the whole denominator of "precision when both agree". With A alone there were 14 agreements and the interval was 66–100%. I flag this as a choice beyond "about 100"; it cost 22 extra paused minutes inside the window Sergei authorised.

**Wrapper.** `pilot_credits.py` cannot take a list and reports only the filename-gated tier, so I wrote a wrapper in the scratchpad that imports the v0.1.3 functions unchanged, with two in-process overrides: `local_model.chat` replaced by the pilot's own `ask` (no pause gate, no stage_metrics write), and `pipeline_config.in_book_publisher` forced true (so `judge`/`judge_credits` show what the tiers would write with Publisher on). Nothing is changed on disk.

**Window.** Pause requested 14:12:00 → Paused with GPU released 14:12:02 (2 s). Run A 14:12:10–14:18:17, run B 14:18:18–14:40:45. Resume 14:40:51. **Paused 28 min 49 s of the 90 allowed.**

## 3. Publisher: all numbers

n = 403 (A + B). "Named" = a known publisher named in full under the production rule (`cover_publisher`), which only knows 16 publishers.

| Reading | Named | Precision vs Metron |
|---|---|---|
| Cover alone (saved reading), the 339 cover-named comics = census of that slice | 339 | 330/339 = 97.3% (95% CI 95.0–98.8%); adjudicated 334/339 = 98.5% |
| Credits alone (indicia text) | 193 | 183/193 = 94.8% (95% CI 90.7–97.5%) |
| Credits alone, tier's own gate (indicia names this series and issue) | 50 | 49/50 = 98.0% (95% CI 89.4–99.9%) |
| Cover == credits, both named | 165 | 164/165 = 99.4% (95% CI 96.7–100.0%) |
| Cover == credits and tier gate passes | 48 | 47/48 = 97.9% (95% CI 88.9–99.9%) |

Joint table (cover reading by credits reading):

| | credits right | credits wrong | credits names nothing |
|---|---|---|---|
| cover right (330) | 164 | 8 | 158 |
| cover wrong (9) | 2 | 2 | 5 |
| cover names nothing (64, sample A only) | 17 | 0 | 47 |

Reading the table: cover wrong and credits wrong, both named, happened 2 times (Kroma, Bloodshot 016). They agreed once (Kroma) and disagreed once (Bloodshot: cover "Image", credits "DC Comics", truth Valiant). Where exactly one reading is wrong and the other right (10 comics), they disagree and nothing is written. That is the veto working: of the 17 comics where either reading was wrong, 16 produced no agreement.

**Sample A only (n = 104, what was asked for):** agreement 13/14 = 92.9% (95% CI 66.1–99.8%); gated 3/4; credits alone 32/34; cover alone 31/40 (inflated, because all 9 wrong covers were forced into A). Use the census numbers above, not these.

**Slices.**
- Agreements by publisher: BOOM! 57, Dark Horse 41, Image 33 (32 right), DC 19, Titan 10, IDW 4, Dynamite 1. None for Marvel, Valiant, Oni, Fantagraphics, Avatar or Archie.
- Why: the cover reading must name the publisher in full. Of the 1,878 verified comics, the saved cover reading does so for DC 109 of 667, Image 46 of 233, BOOM! 95 of 154, Dark Horse 55 of 77, Titan 14 of 28, IDW 8 of 18, **Valiant 5 of 130, Marvel 0 of 127, Dynamite 1 of 103, Fantagraphics 0 of 16, Oni 0 of 12**. Marvel covers read "MARVEL", not "Marvel Comics". Those publishers are effectively unreachable by the rule.
- 307 of the 1,878 (16.3%) have a publisher the rule does not know (Mad Cave 65, Vault 51, Zenescope 43, AfterShock 35, Ahoy 20, Antarctic 19, Skybound 18 and others). For these any named publisher is wrong by construction. Observed: the cover names a known publisher for 6 of 307 (2.0%), always wrong (all 6 were read); the credits reading, run on 36 of the 307, did so once; they agreed once (Kroma). So the rule's false-positive exposure on unknown publishers was 1 in 307.
- Collections (11): cover named 2, credits named 2, all right; the gated tier cannot fire for unnumbered books.
- Pre-2005 (52): credits alone named 15, 11 right (73%): four wrong readings (Catwoman 020, Lobo 021, Lobo 027, Bloodshot 016); none became an agreement. Agreements there: 8/8.

## 4. Every wrong agreement and every wrong single reading

**Wrong agreements: one.**

| Comic | Cover | Credits | Metron | Adjudication |
|---|---|---|---|---|
| Kroma 001 (2022) | Image Comics | Image Comics | Skybound | Not a misread. The indicia prints "Image Comics, © 2022 Image Comics, Ltd." Skybound is an Image imprint, and Metron lists the imprint as publisher. Same pattern on Dark Ride 010, Manifest Destiny 048, Capes 010 (cover says Image, Metron says Skybound). A convention question for Sergei, not a model error. I counted it as an error in the strict figure. |

**Wrong cover-alone readings: 9 of 339** (4 imprint-label cases as above; 5 real):
- PunchLine 010 and 011: the cover shows only a small "AP" logo (Antarctic Press); the model invented "Image Comics" and "DC Comics". Credits named nothing, so no write.
- Bloodshot 016 (1998): cover "Image Comics" (truth Valiant).
- DC K.O. - Boss Battle 001: cover "Archie Comics" (truth DC); credits right.
- Monster High - Boomuda Triangle 003: cover "BOOM! Studios" (the word "Boomuda" in the title; page 2 shows the IDW logo and credits); truth IDW; credits right.

**Wrong credits-alone readings: 10 of 193.** One is Kroma. Nine are fabricated indicia in the template shape "Title #1 / Cover Date: October 2019 / Publisher: Dark Horse Comics / Copyright: …", naming an unrelated publisher:
- House of Slaughter 009, 010, 012, 024, 029 (last page `zzz-mephisto.jpg`, a scan-group page): "Dark Horse Comics" ×3, "Image Comics", "DC Comics". Truth BOOM!.
- Catwoman 020 (last page `zzz-nahga-empire.jpg`): "Marvel Comics".
- Lobo 021 and 027 (last page is an ordinary numbered page, not a scan-group page): "Dark Horse Comics", "Marvel Comics". Truth DC.
- Bloodshot 016: I looked at page 2: the real indicia is tiny print ("Published by Acclaim Comics…"); the model wrote "BLOODSTORM #10 … DC Comics, Inc.".

All nine disagreed with a right cover reading, so none was written. The rule's safety depends on that cover reading being independent of the credits reading. Observed joint failures where both are wrong: 2 of 339, and they agreed on a wrong value once.

## 5. Series and Number (credits alone)

| Reading | Result |
|---|---|
| Indicia contains a "<title> #<number>" candidate | 170/395 = 43.0% |
| First candidate: series agrees with Metron | 106/170 = 62.4% |
| First candidate: number agrees | 88/170 = 51.8% |
| First candidate: both agree | 63/170 = 37.1% (95% CI 29.8–44.8%) |
| Tier fires (indicia names the FILENAME series and number) | 64/395 = 16.2% (95% CI 12.7–20.2%) |
| Written Series / Number equals Metron, when it fires | 64/64 = 100% (95% CI 94.4–100%) |

The tier writes the filename's series and number once the indicia confirms them, so those 64 are right because the filenames are right. The indicia reading adds confirmation, not new information. Read independently of the filename the credits reading gets the series and number right in about a third of the comics where it finds a candidate.

## 6. Year, Month and creators

**Year and Month** (written only when the tier fires and a cover date follows the issue number; 42 of 64 fires):

| | Result |
|---|---|
| Year right | 28/42 = 66.7% (95% CI 50.5–80.4%) |
| Month right | 40/42 = 95.2% (95% CI 83.8–99.4%) |
| Year right, truth year 2000–2023 | 23/24 = 95.8% |
| **Year right, truth year 2024–2026** | **4/17 = 23.5% (95% CI 6.8–49.9%)** |

13 of the 14 wrong years are 2024–2026 books read as an earlier year (2026 as 2020, 2019 or 2022; 2025 as 2023 or 2022; 2024 as 2012, 2016 or 2022); the month is nearly always right. I checked one: He-Man and the Masters of the Universe - The Wings of Fate 003 prints "September 2026" at the foot of page 2 in tiny type, and the model wrote "September 2020". The filename carries the right year in every one of these cases; the tier does not compare against it.

**Creators** (credits page, labelled lines, written when the credits tier is run with `credits_creators`; compared with Metron where Metron has the role):

| Role | Written field has only Metron names |
|---|---|
| Writer | 76/167 = 45.5% |
| Penciller | 44/156 = 28.2% |
| Inker | 8/25 = 32.0% |
| Colorist | 60/147 = 40.8% |
| Letterer | 92/164 = 56.1% |
| **All roles** | **280/659 = 42.5% (95% CI 38.7–46.4%)**; names: 341/842 = 40.5% |

Strict (subset of Metron's names), so Metron gaps count against it, but the misses are mostly real: letter-level misreads ("Tamara Bonvillian" for "Tamra Bonvillain", "Xavier Dorson" for "Dorison", "TRAVIS LUNDAN" for "Lanham"), another person's name under a role (Wonder Man 001: Penciller "Rachelle Rosenberg" against Metron's "Mark Buckingham"), label text swallowed into a name ("Shawn Lee, Edits by Tyler Jirik, Packaged by Tiny Onion" as Letterer; "Bob Hall, Penciled by Jose Delbo, Don Perlin" as Writer), and invented text ("Chris Chucky Color, Rob Steem" for Penciller and Inker; "No creator credits found" accepted as a Penciller name on VIGIA 04).

## 7. Time per comic

| | mean | median | p90 | max |
|---|---|---|---|---|
| Credits read (395 successful) | 2.71 s | 2.62 s | 3.30 s | 5.99 s |
| Cover read (403) | 0.91 s | 0.90 s | 1.05 s | 1.43 s |
| Both | 3.63 s | 3.49 s | 4.30 s | |

First comic (cold model load) 7.0 s. Including failures, 4.22 s per comic overall (1,703 model-seconds for 403 comics). About 1,000 comics per 45 minutes (credits only) to 60 minutes (credits and cover) with the GPU to itself; the live workers share the GPU, so expect slower.

**Failures: 8 of 403 (2.0%).** 7 credits reads ran about 37 s and then died on unterminated JSON (Catwoman 037, 038, 039, Lobo 024, Lumberjanes 015, Assassin's Apprentice II 003, 004): the model ran on until cut off, there is no output cap. 1 read failed instantly because one page could not be opened (LIFE 003, "7 covers"), which drops the whole comic's reading. All were safe (nothing written), but each long failure costs 37 s.

## 8. False-read patterns

- **The model never says "nothing here".** Empty indicia in only 10 of 395 readings (2.5%). Where a page carries no indicia it transcribes whatever is there (scan-group credit text, "SON OF ULTRON / THIS FAN… THIS MONSTER!") or fabricates a template-shaped indicia with a plausible publisher (the 9 in section 4).
- **The last page is a scan-group tag page in 270 of 395 archives (68.4%).** The "last page" slot of the reading is spent on `zWater.jpg`, `zzz-mephisto.jpg`, `zSoU-Nerd.jpg` and similar, which carries no credits. 318 of the 403 filenames carry the "Empire" scan tag, so this is how this library's files are built. Only one archive had a named variant cover among the pages read.
- **Ads and other titles.** 52 of the 165 agreements (32%) rest on an indicia text that does not contain the comic's own series title: 9 look like collected-edition or house-ad text (Catwoman 004, 009 and 034 read "BATMAN: HUSH / DC Comics" ad pages), 2 carry a scan-group name fused into the text ("Dark Horse Comics, Son of Ultron #4"), 41 are garbled or different titles. The publisher was still right in all 52 (the ads are the same publisher's), so they did no harm here, but they are right for the wrong page. Ad, web or ISBN wording appears in 54 of 395 readings (13.7%); recap wording in 1.
- **Tiny type.** Real indicia is often a few lines of small print at the foot of page 2; at the 1400×1800 thumbnail the model misreads digits and invents words (Bloodshot, He-Man). It also invents a second publisher inside a correct reading (He-Man's indicia gains "Marvel Comics, LLC"). The existing rule (skip when a second publisher is named) correctly dropped that one.
- Saved and fresh cover readings agree on the named publisher in 94.4% of comics, so the cover reading is not perfectly repeatable across runs.

## 9. Recommendation

For Sergei to decide. This is what the data supports.

1. **Publisher, cover AND credits agree: safe enough on the evidence, with the limits below.** Observed 99.4% strict (164/165), 100% adjudicated (165/165); no real misread became an agreement; the one strict miss is an imprint-label convention. The bar was "at least 99%, or state the observed number with its interval": observed 99.4% (CI 96.7–100%), adjudicated lower bound 97.8%. Not statistically proven at 99%.
2. **Before switching on, settle the imprint question.** Where the printed publisher is Image and Metron says Skybound, the rule writes "Image Comics" and later sources fill only empty fields, so the first writer wins. Sergei picks the convention.
3. **Expect small coverage.** 8.8% of the verified comics, 2.6% with the series/issue gate, and almost none for Marvel, Valiant, Dynamite, Oni, Fantagraphics or any publisher outside the 16 the rule knows. The gate removes the 52 right-for-the-wrong-page cases at a cost of two thirds of the coverage; both variants met the bar here, the gated one with a thinner sample (48).
4. **The sample is not the target population.** The rule would write on comics that have no Publisher today, mostly comics Metron has not matched. Those are unmeasured. The nearest proxy is the cover-empty slice of sample A (credits alone named 17, all right), which is small.
5. **To prove 99%:** about 370 error-free agreements, i.e. a second census of roughly 500 cover-named comics from outside the Metron-verified set, with a truth source (embedded publisher or a Metron match made later).
6. **Do not switch on creators or Year from the credits tier.** Creators are right 42.5% of the time. Year is right for 2000–2023 books and wrong for most 2024–2026 books, and the filename year was right in all of them.

## 10. Findings (flag only; I fix nothing)

The credits tier is off by default, so none of these touches Sergei's daily flow today. None is a Blocker. Severity applies if the tier is switched on.

| # | Finding | Severity |
|---|---|---|
| 1 | Creators: 42.5% of written role fields contain only truth names; role mix-ups, label text swallowed into names, invented names, "No creator credits found" accepted as a name | Major |
| 2 | Year written by the credits tier is wrong on 13 of 17 books from 2024–2026 (the filename year was right) | Major |
| 3 | Credits read has no output cap: 7 of 403 ran ~37 s then failed on unterminated JSON | Minor |
| 4 | One unreadable page (LIFE 003) drops the whole comic's credits reading | Minor |
| 5 | The reading's "last page" is a scan-group page in 68% of archives | Minor |
| 6 | Imprint convention: Skybound (Metron) vs Image (printed) on four comics in this set | Question for Sergei |

**Pattern alerts.** One, filed separately from the findings above.
- *Browser worker respawn while paused, now seen on v0.1.3.* The 2026-10-13 deploy receipt records the v0.1.1 browser worker being respawned while paused (twice: 2026-10-12 and 2026-10-13) and says the v0.1.3 worker was stable over an 11.5-minute watch (running, not paused). During this 28-minute pause the supervisor (server PID 24880) replaced the v0.1.3 browser worker: PID 62424 → 74864, created 14:37:47, about 25 minutes into the pause. After resume the new worker's heartbeat is current. Cause not established. **Proposed disposition: defer** (harmless so far; the worker re-acks). Needs Jane's/Sergei's confirmation; I have not touched it.

## 11. Caveats

- **Truth is not perfect.** It is Metron's record for a match the app made with cover evidence. A comic whose cover reading disagreed with Metron's publisher may have been less likely to get verified, which would flatter the cover and agreement figures. Metron also lists imprints (Skybound) where the page prints the parent.
- **The set is the Metron-verified slice:** mostly 2000s and later. The 1,878 hold 320 comics from before 2005 and 1 from before 1990; the 403 read here hold 52 from before 2005, 6 Marvel and 11 collections.
- **Scan-group heavy:** 256 of the 299 census comics carry the "Empire" tag, so patterns such as the 68% scan-group last page describe this library's files, not comics in general.
- Creator and Year comparisons are strict, and Metron can lack a role (46 Writer, 69 Penciller cases where Metron had no role were excluded from the creator percentages).
- Timings were taken with processing paused and the GPU free.

## 12. Operations log

**Pre-flight** (read-only), saved in `preflight-before.txt`: `/api/state` version 0.1.3, online, job idle, 40,029 comics, tagged 5,192; control phase running; Lens `human_verification` false, window minimized; Ollama had no model loaded; processes: host 48288, server 24880, metadata worker 47464, browser worker 62424.

**Catalog snapshot.** SQLite backup API through a `mode=ro` connection into the scratchpad (188 MB); removed at the end.

**Pause.** First attempt 14:08:23 returned HTTP 403 "Untrusted origin" (my POST lacked the `Origin` header the API requires); state did not change (control stayed `running` throughout). Second attempt 14:12:00 with `Origin: http://127.0.0.1:8765` and a `{}` body: `pausing` → `paused` with `gpu_released true` after 2 s; Ollama showed no model loaded.

**Resume.** `POST /api/resume` 14:40:51, phase `running` immediately. Watch 14:41–14:46: version 0.1.3, online, control running, metadata worker 47464 unchanged, browser heartbeat current (PID 74864), history rows 6,539 (14:42) → 6,547 (14:46) and still writing (latest 16–41 s old), `server-error.log` 0 bytes, `server-output.log` the 2-line banner, tagged 5,192 before the pause and 5,217 at the end of the watch. Processing was never left paused. The Lens window reads `closed` after resume against `minimized` before; the deploy receipt records the same close on pause. I did not touch the Lens browser or its state.

**Windows and focus.** The pilot is console-less Python run from Git Bash: it opened no window. I ran `powershell.exe -NoProfile -File` three times for the read-only process inventory; I cannot rule out a console flash from those, and I observed no focus change (I cannot see the screen).

**Hard limits.** No archive opened for write (zip read only). No catalog write by me (my SQLite connections were `mode=ro`; the wrapper bypassed `local_model.chat` so the pilot wrote no stage metrics). No config, quota, profile or Lens change. No git write; the live checkout is still at `1c34df2` with only the same three untracked UX specs. No code fix.

## 13. Evidence and reproduction

In the session scratchpad `C:\Users\AnGeLZzZ\AppData\Local\Temp\claude\C--Antigravity-Projects-Studio-Illuminati\f34a159a-afd4-4cc3-8efb-fbb74a16f69e\scratchpad\credits-pilot\` (kept, not copied into this worktree):
- `results\per-comic.jsonl` (sample A, 104 comics, 321 KB) and `results-b\per-comic.jsonl` (census extension, 299 comics, 1.0 MB): per comic the Metron truth, saved and fresh cover readings, the raw credits and indicia text, the pages read, timings, and every derived decision.
- `sample.json`, `sample_b.json`: the comic lists. `preflight-before.txt`, `preflight-after.txt`, `pause-response.json`, `resume-response.json`.
- Method: `run_pilot.py` (wrapper), `analyse.py`, `analyse_fields.py`, `analyse_extra.py`, `common.py` (Clopper-Pearson), `build_sample.py`, `build_sample_b.py`.
- Run: `python -B run_pilot.py --sample sample.json --out results` with processing paused. The `Origin` header is required for pause and resume.
- Removed at the end with `studio-disk-hygiene` (12 files, 3 directories, 200,068,764 logical bytes; manifest `scratchpad\hygiene-manifests\credits-pilot-disposable.json`, verify `complete: true`): the 188 MB catalog snapshot, `verified_evidence_scan.json` (7.6 MB, regenerated by `scan_evidence.py`; `build_sample*.py` read it), the page contact sheets, and the mock dry-run output.
