# Comics Meta Organizer — QA Report v0.1.4 (candidate eb64759)

**Tool:** Comics Meta Organizer (Python, local dashboard + workers)
**Build under test:** branch `feat/v0.1.4-in-book-rules`, commit `eb64759cba3d4563650b6b157a69fac90c8353c8` (tree `d1df20547ecba5f9f93fb42cdb4c8357f436b675`), on the released v0.1.3 (`1c34df2`). `git diff 1c34df2..eb64759`: 35 files, +3,999 / -191.
**Date:** 2026-10-13. **Tester:** Futaba (QA / Dogfooder). Reports to Jane. Senua's construction verdict is a separate document. An untracked `Docs/ComicsMetaOrganizer_CodeReview_v0.1.4_2026-10-13.md` appeared in the worktree while I tested; I did not open it.

## 0. Summary

- **GO for eb64759.** No Blocker and no Major. The seven changes work as the README, SOURCE_CONNECTORS and the Brief describe them, and the red-team found no way to make the build write a value it promised not to write, or to replace a value a human or another program wrote.
- **What I tried hardest, and what held.**
  - *Replacement of in-book values (item 3).* Eight ledger-gap scenarios plus four imprint scenarios, through the real discovery, worker and batch code: a v0.1.3-style manual write, a stale catalog, a manual write between plan and apply, a v0.1.3 reference batch, no flip-flop between sources, and a same-size same-mtime edit. A human value was never replaced. The same-size edit is invisible to the signature chain, and the second-line ComicInfo guard caught it.
  - *Wrong filename numbers (item 2).* 76 hostile cases (dates, prices, `0.5`, part/vol/chapter, `c2c 17689`, annuals, other scripts, bracket numbers, translation tags, collections) and all 13,756 already-tagged comics in a read-only copy of the live catalog. With a perfect cover reader the filename-number path writes the same Number the existing ComicInfo holds in **9,654 of 9,665** comparable cases (99.89%). The 11 differences are 10 volume-issue forms (`2.1`) and one real renumbering.
  - *Publisher (item 1).* 27 cases including fabricated indicia, scan-tag pages, second-publisher house ads, partial names and failed readings. No publisher is written without two readings that agree. Year and creators stay off by default.
  - *Failure filters (item 6).* Counts, filters, row sentences, tooltips and accessible names match Judy's spec character for character on the real rendered page. "Try again" gives exactly one real attempt through the real pass, and works while paused.
  - *Lens (item 7).* Five/ten/twenty/forty/sixty-minute waits under six adversarial schedules. There is no loop, and every re-solve needs Sergei.
- **Minor findings for Ender/Judy/Sergei (section 7), none blocking.** The most visible:
  - Real titles that end in a dot lose it (`Hunt. Kill. Repeat.`: 6 live comics).
  - Publisher spelling variants (`Image Comics, Inc.`) replace the canonical in-book name, which the README says they do not.
  - An Imprint can be written beside a human's Publisher from another house.
  - The pilot script's publisher comparison is not imprint-aware.
  - The Details block has no gap between the reason and the "Last error" box.
  - The copy reads "Attempt 6 of 5 failed" after a second "Try again".
- **The 7 px of sideways scroll at 320 px is real and measured** (section 5). It is the comics table's fixed 145 px actions column. It is 0 px from 360 px up and at 1440 px, and it is **not new**: on the same fixture v0.1.3 scrolls 69 px at 320 and 29 px at 360, because its status select is 351 px wide.
- **Real screenshots for Judy** are in the scratchpad (section 5).
- **The GPU pilot was not run.** Its new report fields were verified on fixtures only (section 3, item 1).

Pattern alerts: none.

Scope of the verdict: the content of commit eb64759. `VERSION` reads `0.1.3`, `CHANGELOG.md` has no 0.1.4 entry, and the dashboard badge shows v0.1.3 at this commit. That is Sully's bump. Any release must be a version-and-changelog-only commit on top of a commit that gets a GO.

---

## 1. Build identity and isolation

- **qa-handoff entry check: not applicable.** The tool has no `package.json`, and the skill's script needs a package contract. Recorded by hand as in v0.1.2 and v0.1.3: worktree HEAD `eb64759cba3d4563650b6b157a69fac90c8353c8`, branch `feat/v0.1.4-in-book-rules`, `git status --porcelain --ignored` empty at the start. Code under test is byte-identical to the committed content.
- **Tested from committed content only.** `git archive eb64759` extracted into `snap` (suite and DOM tests), `probe` (probes), `smoke`, `smoke2`, `smoke3` (real-app runs), plus `git archive 1c34df2` into `base` (v0.1.3 controls) and `mix` (v0.1.3 source with the v0.1.4 tests, to prove the new tests can fail).
  - Verification: all 138 blobs of `snap` and all 123 of `base` equal the commit's blob hashes. The archive comes out CRLF (`core.autocrlf=true`), so the hash is taken through the clean filter.
  - Every end-to-end run used its own copy and its own data folder. Nothing was written to git or to the worktree except this report. The worktree's tracked tree is still clean at eb64759.
- **Real app, isolated.** Ports 18841 (v0.1.4 fixture), 18842 (v0.1.3 control) and 18851 (v0.1.4 core-flow smoke). The 8765 live service was not touched (listener PID 24880 at the start and at the end).
  - Every real-app process tree ran under a socket guard (`sitecustomize.py`) that allows connections only to its own port. Positive control: it refuses 127.0.0.1:8765, 127.0.0.1:11434 (Sergei's model service) and `comicvine.gamespot.com`.
  - No API key. HTTP and HTTPS proxies pointed at a dead port.
  - The guard logs show the only refused attempts were 3 calls to 127.0.0.1:9 (my dead proxy) from the Pause button's model-unload call. The unload is attempted by design and never left the machine.
- **Live contact, disclosed.**
  1. A read-only (`?mode=ro`, `query_only`) copy of the live catalog's `comics` table (40,039 rows: path, size, mtime, series, number, year, status, metadata) into my scratchpad, used for the filename-side measurements in sections 3 and 4.
  2. A directory listing of the main checkout's `data/` to find the catalog file.
  3. `netstat`, process listings and `git worktree list`, to identify my own processes and confirm the live listener was unchanged.
  I did **not** read the live `data/research` evidence, the queue, any profile or quota, Y:\Comix, or any other worktree. Nothing was sent to ComicVine, Metron, Google or any other provider. `pilot_credits.py` was never run against live archives.
- **Screenshot and measurement substitution, disclosed.** My fixture library sits under a 160-character scratch path. The "Live library" panel prints it as one unbreakable string, which on its own scrolls the page 84 px sideways at 320 px (same on v0.1.3). To show what Sergei would see, the screenshot and measurement scripts replace only the text of that one paragraph (`#roots`) with `Y:\Comix` in the DOM before measuring or shooting. Nothing else is altered. The raw measurement (84 px) is reported in section 5.
- **Processes I started and ended** (each verified by its listener or command line as mine): servers 30012, 67072, 45808, 37424, 39892 with their worker children, and one script, 77572. A `subst R:` mapping was made and removed (it did not help: the app resolves real paths). No headless lease is left (`list`: none).
- **One tool refusal.** A Bash `rm -rf` of a folder that did not yet exist was refused by the studio's delete guard. I used a different folder name instead.

## 2. Suite results

| Run | Where | Result |
|---|---|---|
| `python -B -m unittest discover -s tests` (eb64759) | `snap` | **Ran 665 tests in 103.1 s, OK (skipped=47)**, exit 0 |
| The 47 skipped DOM tests | `snap`, canonical `scripts/qa/headless-browser.mjs run`, `COMICS_TEST_CDP` = the lease's HTTP endpoint, `COMICS_TEST_EVIDENCE` set | **Ran 47 tests in 14.6 s, OK**; `list` afterwards: no leases |
| Positive control: the v0.1.4 tests against v0.1.3 source | `mix` | **Ran 639, FAILED (failures=19, errors=49, skipped=47)**: the new tests fail without the change |
| Positive control, DOM: the same 47 against the v0.1.3 page | `mix` through the harness | **Ran 47, FAILED (errors=12)** |

- 665 of 665 executed and passed. Test methods: v0.1.3 has 560, v0.1.4 has 655 (96 added, 1 removed). The 10 further executed tests are inherited or parameterised (the new DOM class subclasses the Yandex DOM tests); I did not trace them one by one.
- Suite debris: a full run in the pristine copy left the file count unchanged (138) and no empty directories.
- One `ResourceWarning` (unclosed `HTTPError 429`) is printed, as in earlier rounds.

## 3. Change-by-change verification (against eb64759)

| # | Change | Result | Evidence |
|---|---|---|---|
| 1 | Publisher only when cover and credits agree; Year and creators off; a failed credits read is no reading | **PASS** | 27 publisher cases (`pB`), the credits-tier defaults (`pU`), and a 15-comic real-service run (section 6). Details below. |
| 2 | Filename number when the cover number is unread and the title agrees (`in-book:filename-number`) | **PASS** (V4-5, Minor) | 76 hostile cases (`pA`), corpus ceiling (section 4.2), real-service run |
| 3 | Verified outside sources may replace in-book values; write ledger; human and other-program edits protected | **PASS** (V4-2, V4-3, Minor) | Section 4.3 |
| 4 | Series spelling fixes | **PASS** (V4-1, Minor; V4-15, Note) | Section 4.4, 12,740 real filenames |
| 5 | Imprint in its own field from the imprint-to-parent table; Kroma 001 gives Image Comics + Skybound | **PASS** (V4-3, V4-4, Minor) | Section 4.5 |
| 6 | Failure filters, chips, reasons, Details block, Try again, missing-key line, misleading line removed | **PASS** (V4-7, V4-8, V4-9, Minor) | Section 4.6, section 5 |
| 7 | Lens resumes 5 minutes after a solve, backs off 10/20/40/60 | **PASS** | Section 4.7 |

**Item 1 details.**
- Writes Publisher only when the cover reading and the credits/indicia reading both name the same one known publisher in full. A cover of `Image`, `Dark`, `Marvel` or `DC` alone, a credits text of `Image`, or empty credits writes nothing. A second publisher in either reading writes nothing (a house ad for Marvel in a DC book; `Printed by Dark Horse Printing` in an Image book; `DC Dark Horse Comics` on a cover). A scan-tag page naming another publisher makes the text ambiguous and writes nothing. A story page that merely mentions the same publisher the cover names does agree and writes it, which is the rule as written.
- With `credits_pages` on and the year and creators switches at their defaults, a full indicia and credits page yields only Series, Number and Publisher. `credits_year` adds Year and Month; `credits_creators` adds creators; neither is on by default.
- Malformed or empty credits readings return nothing. In the real run, a failed read is covered by Ender's tests, which I positive-controlled in `mix`.
- **`pilot_credits.py` on fixtures only.** `run()` was called with injected readers and an explicit fixture data folder under the socket guard: no connection attempted, fixture archives and evidence byte-identical afterwards, only the report file written. Every new field is present and equals my hand count for a 9-comic fixture.

  | Report field | Measured | Hand count |
  |---|---|---|
  | `publisher_agreement.cover_named` / `credits_named` / `both_same` / `both_different` | 7 / 7 / 5 / 1 | 7 / 7 / 5 / 1 |
  | `would_write`: agree / disagree / not_in_source | 2 / 2 / 1 | 2 / 2 / 1 |
  | `cover_alone`, `credits_alone` | 4/2/1 and 3/3/1 | 4/2/1 and 3/3/1 |
  | `publisher_gate` | checked 4, disagreements 2, rate 0.5, passed false | same |
  | `errors` (reader raised) | 1 | 1 |
  | Per-comic `cover_reading` | `saved` or `read now` | same |

  See V4-6 for one limitation of this report.

## 4. Red-team results

### 4.1 Publisher
Covered in section 3, item 1. No wrong Publisher was written by any case. Residual risks I cannot probe without the model:
- A hallucinated credits reading that happens to repeat the cover's publisher would agree.
- Both readings are mock-free only in the 2026-10-13 pilot (164 of 165 agreed with Metron), which I did not re-run.

### 4.2 Filename numbers
- **Hostile cases.** 76 cases, 20 writes, 56 refusals. Every refusal class from the README fires: date codes (`Previews 0315`), four-digit numbers, `c2c 17689`, `Naruto Vol 12`, `v12`, `Ch 12`, `Part 2`, `Episode`, `Season`, bracket numbers (`(180)`, `[12]` alongside another number), reading-order prefixes, `[rus]` and `(fr)` tags, `TPB`/`HC`/`Compendium`/`Omnibus`, annuals and specials the filename does not name, `Part 1 of 3`, `Vol 2`, a price or year as the cover number, Cyrillic and Japanese cover text, a boolean/list/object cover issue, `UNIT 731`.
- **The writes are right.** `Spawn 001` with an unread cover number, `Issue One`, a cover price, a cover date, `1 OF 4`, `Batman No 5`, `Batman #5`, `Batman 5A` (written as `5a`), and `Batman Annual 1` whose cover title is `BATMAN`.
- **Doubtful but by design (V4-5).** `Batman 2.99` writes Number `2.99`; `Spawn 0.5` and `Spawn 1.5` write `0.5` and `1.5` (the code comment says the `0.5` handling is deliberate). A price-shaped decimal cannot be told from a real decimal issue number.
- **Corpus ceiling, real filenames.** A perfect cover reader (cover title = the comic's existing ComicInfo Series, cover issue unread) on all 13,756 already-tagged comics in the read-only copy, with empty metadata so the tier writes:

  | Path | Written | Number equals ComicInfo | Number differs | Series equals ComicInfo | Series equals by title key only | Series differs |
  |---|---|---|---|---|---|---|
  | filename number (cover unread) | 11,059 | 9,654 | **11** | 8,637 | 2,347 | 75 |
  | cover number read | 11,105 | 9,711 | 0 | 8,645 | 2,359 | 101 |

  The 11 Number differences: 10 where ComicInfo uses the volume-issue form (`2.1`, `3.1`, `4.2`) for the filename's `001`, and `You've Been Cancelled 004` against ComicInfo `3`. 193 comics had no comparable ComicInfo Number. The 75 Series differences are the known Q3-2 pattern (arc or subtitle after a dash in the filename, such as `Lady Death - Pirate Queen`), not new.
- **The guards fire on real names.** Among ComicInfo-tagged comics the number doubt filter refused 39 chapter/episode/part names, 13 year-or-code numbers, 9 bracket numbers, 3 collections, 2 date codes and 1 zero-padded decimal.

### 4.3 Replacement of in-book values, and the write ledger
All through the real `discover`, worker and `batch.apply` (Ender's harness, sources mocked), asserting the safe outcome.

| # | Scenario | Result |
|---|---|---|
| C1a | v0.1.3 manual dashboard write after an in-book write; the ledger wiped as v0.1.3 left it; backfill runs | Not replaced (the manual history row has no ledger row, so the chain stops) |
| C1b | the manual write came before the in-book write | In-book Series replaced, Sergei's Title kept: intended |
| C1c | a v0.1.3 reference batch whose plan says `in-book:cover` | Counted manual; nothing replaceable |
| C2 | archive edited by another program, catalog never rescanned | Series kept; only Year and Publisher planned |
| C3 | manual dashboard write between plan and apply | Skipped (`Source changed after planning`); nothing replaced; nothing replaceable afterwards |
| C4 | a second verified source after a replacement | Cannot flip the replaced Series (source is now `replaced-in-book:Metron`) |
| C5 | a tagger re-saves with identical Series and Number | Not replaceable |
| C8 | a human edit that keeps the archive's size and mtime (crafted: same size, mtime restored) | The signature chain cannot see it, but the ComicInfo guard (`before` must still match) kept the human value (`Amazing Spider-Max`) |
| K1-K4 | Kroma: in-book Image Comics plus Metron `Skybound`; Metron Publisher+Imprint; a second pass; Image against a verified Dark Horse | Publisher stays Image Comics and Imprint fills with Skybound; no loop on a second pass; a different house replaces and the Notes record it |

- **Unproven edge, not a defect I can demonstrate:** a program that edits a field other than the replaced one, in place, preserving size and mtime, would leave the in-book values replaceable. All the app's guards share that signature limit.
- A replaced in-book Marvel against a verified `Vertigo` gives Publisher `DC Comics` plus Imprint `Vertigo`: by design (the source disagrees about the house).
- Not found: any path where a human or other-program value is replaced.

### 4.4 Series spelling
- **Spec behavior.** `Don_t Look Back` becomes `Don't Look Back`; `Wolverine_s Revenge` becomes `Wolverine's Revenge`; underscores and repeated spaces collapse; `S.H.I.E.L.D.`, `Dr. Strange`, `.hack//Sign` and `Vs.` keep their dots; accents come from the cover only when the cover title is the same text ignoring accents; `Midlife (or How to Hero at Fifty)` keeps its bracketed title; `Alison (Lizzy Stewart)`, `(One-shot)` and `(2016)` are dropped as before.
- **Real filenames.** 12,740 usable filenames. The normaliser changed 220 (142 underscores plus spaces, 46 underscores, 14 apostrophes, 12 trimmed separators, 5 bracketed titles, 1 mixed). Against the ComicInfo Series the new text matches 8,797, the raw filename 8,794: **+9 improvements, -6 regressions**.
- **The 6 regressions share one cause (V4-1).** A real title ending in a dot loses it: `Hunt. Kill. Repeat.` (4 comics), `Beware...`, `Midnight, Mass.`. `KEPT_FINAL_DOT` protects initialisms and abbreviations, not a title ending in a sentence dot. The real-service run writes `Hunt. Kill. Repeat` for `Hunt. Kill. Repeat. 001`. A later verified source would replace it, since any Series difference counts as disagreement.
- Underscore-only filenames with no spaces (`Vampirella_V3_001`) are read as an unnumbered whole book, so nothing is written for them unless the cover title equals the whole name. Same as v0.1.3.
- Contrived outputs (V4-15, Note): `X_Men` becomes `X Men` (the hyphen is not restored; v0.1.3 wrote `X_Men`), `Don_T Stop` becomes `Don'T Stop`, `Marvel Zombies_s` becomes `Marvel Zombies's`.

### 4.5 Imprint
- Kroma-style cases pass (section 4.3, K1-K4). Imprint is never written by the in-book tiers; it comes only from outside sources, and an imprint named as Publisher is split before anything is written or compared.
- **V4-3.** A human Publisher of another house is not contradicted by the code: human `Dark Horse Comics` plus a verified Metron `Skybound` leaves Publisher alone and writes Imprint `Skybound` beside it. Human value kept, but the record now pairs Dark Horse with an Image imprint. v0.1.3 wrote nothing here.
- **V4-4.** The imprint table has no dates. `WildStorm` gives `DC Comics` even for the Image-era books (Gen13 1994, Stormwatch), `Shadowline` gives `Image Comics` even for the 1980s Epic-era books, and `Archaia` gives `BOOM! Studios` for pre-2013 books. I could not check what Metron actually returns for these (no live contact), so this is unconfirmed.
- Table behaviors: `icon`, `Max` and ` Vertigo ` match case-insensitively and after trimming; an Imprint already given by the source is kept; unknown names are left as they came.

### 4.6 Failure filters
- **API, real server, 24-comic fixture with 18 problem comics** (stopped, failed with each count and retry state, conflict with and without ComicVine values, dead link, one held comic per cause plus none, plus a stale record, a skipped write, a two-marker comic and plain comics):
  - Each chip equals its filter's total (4/1/2/4/7); the sum is 18; **no comic appears under two filters**.
  - The stale-signature comic and the skipped-write comic appear nowhere.
  - The two-marker comic (stopped plus a saved conflict) appears once, as stopped.
  - Searching narrows the list and leaves the chips alone.
  - The old ten filters return identical totals on v0.1.3 and v0.1.4 for the same library; their order and values are preserved, and the five new ones are appended.
  - The record shapes were created through the real `discovery_state.write_not_done` for failures. The core-flow run (section 6) produced a real `write_failed` record and a real `held` record with cause `no_key`, and the page rendered them.
- **Strings, from the real rendered page, against the spec typed fresh:** five option texts, values and group names; the select's accessible name `Comic status` and tooltip; five chip texts per group; five chip tooltips; the summary lines (`Your help is needed: 7 comics. Filter by status below to see which.`, the zero sentence `No stopped writes, dead links or conflicts.`, `11 comics are retrying on their own.`, the key line); every row sentence variant (attempt N of 5 with a later time, with a past time, with the count missing, stopped, dead link, conflict with and without values, held with each cause and with no cause, held with no key); `Try again` and its accessible name `Try again: {series} {number}`. All equal. Held rows show no reason line under All files.
- **The misleading lines.** `No manual review is required` and `You only need to act when a specific request appears above`: 1 each on the served v0.1.3 page, **0 each** on v0.1.4. The research sum no longer contains `identity_conflict`. This closes the Q4-4 and P-4 observation named in Judy's spec.
- **Missing-key line.** Shown on the real server while no key is set. Adding a `.env` key makes the progress feed say `configured` within 1.0 s and the line disappears; removing it brings the line back within 3.0 s. **No restart is needed**, matching the copy. The suite's DOM tests cover the absent cases (`rate_limit_wait`, `hourly_budget_wait`, missing `providers`).
- **Try again, record side (real server).** One POST clears the stop, keeps the failure count, sets the retry to now, and moves the comic from Writes stopped to Write failed. A second click changes nothing. It is allowed while paused (200, changed) while another write route returns `Processing is paused. Resume before starting manual work.` Cross-origin and Origin-less POSTs get 403. A stale record, a plain comic, a held comic and a conflict comic are unchanged.
- **Try again, real pass.** Through the real discovery, worker and batch code with a held-open file (writes really refused), counting calls to `write_metadata`:
  - Fail to count 4, one pass makes count 5 and the comic is stopped (calls 2).
  - A pass with no click makes no attempt (calls 2).
  - **Click: exactly one attempt** (calls 3), stopped again at count 6 with `Automatic writes stopped after 6 failed attempts`.
  - Another pass makes no attempt (calls 3).
  - After releasing the file, one click lets the write through (calls 4) and the comic leaves every list.
  - Gap noted: the existing test fakes the failed attempt with a direct `write_not_done` call, so the one-attempt-per-click behavior was not covered through a real pass until now. I did not exercise it through the scheduler. My attempt to force a pass by editing the scheduler state made it pick a first-update pass, a distortion of mine, so the folder timing (about 10 minutes per folder) is taken from the code.
- **Page behavior (real page, 1440 px).** Click: one POST, the button becomes `Retry requested`, the row leaves the filtered list, **focus lands on `#total`** (`tabindex=-1`). A refused request shows the server's message in the `#error` banner and re-enables the button. Chips and line A follow within about 0.5 s of the click.
- **Contrast from the rendered colours** (computed, backgrounds composited): neutral chip text 12.50, neutral chip border 7.80, warning chip text 6.80 and border 5.93, group labels 7.08, badges 6.80 and 8.39, reason sentences 7.80, `Try again` 5.70. All equal Judy's hand values to rounding. Lines A and C measure 12.47 against the spec's 12.49. Pressed chip: 2 px inset `#bcd8f9`; hover: 1 px inset; keyboard focus: 2 px `#bcd8f9` outline, 2 px offset.
- **Hostile text.** Planted `<img onerror>` and `<script>` in a conflict record's series, number and id, a dead-link id and a write error: all render as literal text, no element is created, nothing executes (`window.__pwn` stays 0).
- **Performance.** On a synthetic 40,000-comic catalog with realistic problem volumes (4,328 held, 207 failed, 95 stopped): the whole counts set (run on every progress refresh) takes **78 ms**; one filter 75 to 82 ms; the 100 rows of a page 6 ms; a searched filter 15 ms.

### 4.7 Lens backoff
- The real `lens_verification.solved_hold` under six schedules, each with ten solves:

  | Schedule | Waits in minutes |
  |---|---|
  | Google asks again 30 s, or 1 s, after each pause | 5, 10, 20, 40, 60, 60, 60, 60, 60, 60 |
  | asks again at 1 h 59 m after each solve (streak kept) | 5, 10, 20, 40, 60, 60 ... |
  | asks again at exactly 2 h 00 m 00 s | 5, 10, 20, 40, 60, 60 ... |
  | asks again at 2 h 00 m 01 s (streak resets) | 5, 5, 5, 5 ... |

- Never longer than a hold already running (120 s stays 120 s); an ended hold stays ended; no hold stays no hold. A solve shortens a daily-limit hold to 5 minutes, but the daily count is re-checked at the next search (Ender's test covers it).
- The most frequent resume Google can cause is a 5-minute pause after each solve, and only when its checks are more than two hours apart; closer checks back off to 10, 20, 40 and 60 minutes. Every solve needs Sergei. **No spin, no automatic loop.** The existing tests of the real `service` and worker wake-up pass.
- V4-14 (Note): a damaged `solved_checks` value (a string count) would raise a TypeError on the next solve. The app only writes that record itself.

## 5. Visual (real rendered screenshots)

All taken in headless Edge through the canonical harness (one lease per run, none left), on the isolated real server with a fixture library. Folder:

`C:\Users\AnGeLZzZ\AppData\Local\Temp\claude\C--Antigravity-Projects-Studio-Illuminati\f34a159a-afd4-4cc3-8efb-fbb74a16f69e\scratchpad\f014\evidence\shots\`

| What | Files (prefix `v014_`) |
|---|---|
| Dashboard, All files, 1440 and 320 | `1440_all_viewport.png`, `1440_all_full.png`, `320_all_viewport.png`, `320_all_full.png` |
| Each of the five filters (chips, row reasons), 1440 | `1440_filter_write_stopped.png`, `1440_filter_dead_link.png`, `1440_filter_conflict.png`, `1440_filter_write_failed.png`, `1440_filter_held.png` |
| The same five, 320 | `320_filter_write_stopped.png`, `320_filter_dead_link.png`, `320_filter_conflict.png`, `320_filter_write_failed.png`, `320_filter_held.png` |
| Details block (stopped, held, conflict, failed), 1440 and 320 | `1440_details_write_stopped.png`, `1440_details_held.png`, `1440_details_conflict.png`, `1440_details_write_failed.png`, `320_details_write_stopped.png`, `320_details_held.png`, `320_details_conflict.png`, `320_details_write_failed.png`, `320_details_stopped_2x.png` |
| The missing-key line shown and gone | `1440_all_viewport.png` (shown), `1440_keyed_viewport.png` (key set, line absent) |
| Real records from the core-flow run | `pipeline_real_records_1440_all.png`, `pipeline_real_records_1440_write_failed.png`, `pipeline_real_records_1440_held.png` |
| v0.1.3 for comparison at 320 | `v013_320_pathfixed_full.png` |
| Crops used in this report | `crop_1440_held.png`, `crop_320_chips.png`, `crop_320_all_a.png`, `crop_320_all_b.png` |
| Measurements | `v014_report.json`, `v014_widths.json`, `v013_widths.json`, `details_geometry.json` |

The native dropdown popup cannot be rendered headless. Its five options, groups and values were read from the DOM instead (section 4.6).

**Measurements** (`getBoundingClientRect`, library-path text replaced as disclosed in section 1):
- **1440 px:** 0 px sideways scroll in every state (All files, each filter, each Details dialog). Chip row, search row, `#total` and the table have disjoint rectangles. All five chips are 32 px high.
- **320 px, the sideways scroll.** The comics table is 327 px wide in a 320 px viewport (columns Comic 94, Issue 50, actions 145 plus the panel padding), so the page scrolls **7 px**. The overflowing element is the `td.file-actions` column (Details plus Folder, 145 px, nowrap); the Folder button's text ends 3 px past the edge.
  - It shows in All files, Write failed and Held; it is 0 px in Writes stopped, Dead link and Conflict (those lists are narrower).
  - **0 px at 360, 400, 480, 700, 1024 and 1440.**
  - With a classic 15 px scrollbar (as on a real desktop window) the same table overflows by 22 px, because the usable width is 305 px.
  - **Not a regression:** on the same fixture v0.1.3 scrolls **69 px at 320 and 29 px at 360** (its status select is 351 px wide). v0.1.4's select no longer forces that.
- **Layout at 320 px.** Nothing is clipped or covered. Chips wrap in two groups; each is at least 32 px high. The Comic column is only 94 px wide, so reason sentences wrap to about 12 characters per line (a conflict reason is about 11 lines tall).
- **Details dialog** (stopped comic, 1440 / 700 / 320 px): badge, sentence and the `Last error:` box do not overlap, but the two blocks touch: the sentence block's bottom edge equals the error box's top edge (**0 px** between the blocks at every width), and the last sentence line's text ends 3 px above the box at 1440 and 1 px above it at 700 and 320. At 320 px the dialog scrolls sideways internally, caused by the file path text in my long scratch path.

## 6. Smoke test (the real service, core flow)

Real `app.py --no-browser --port 18851` (supervisor and workers) from a pinned copy, automatic processing on, every outside source disabled, a 15-comic fixture library with a saved cover reading and a saved credits reading per comic, and one archive held open by another process.

- First attempt: the worker raised `KeyError: 'root'` and the dashboard sat in "Automatic lookup waiting". My fixture config had only `automatic.library_root`; `worker.py:155` evaluates `automatic['root']` even when `library_root` is present. Same line in v0.1.3 (V4-11). With both keys set the run below worked.
- **Result: 15 of 15 archives as required.** The first pass had finished within seconds of the service starting (the batch of 7 writes ran in under 0.3 s).

| Comic | Expected | Result |
|---|---|---|
| `Spawn 001` (cover `#1`, both readings Image Comics) | Series, Number, Publisher | wrote `Spawn` / `1` / `Image Comics`, source `in-book:cover` |
| `Spawn 002` (cover issue unread) | the same, number from the filename | wrote them, source `in-book:filename-number` |
| `Saga 003` (cover issue `JUNE 2012`) | the same | wrote them, source `in-book:filename-number` |
| `Batman 004` (cover DC, credits Marvel) | Series and Number only | wrote only those |
| `Don_t Look Back 001` | `Don't Look Back` | wrote it |
| `Midlife (or How to Hero at Fifty) 001` | bracketed title kept | wrote it |
| `Hunt. Kill. Repeat. 001` | (see V4-1) | wrote `Hunt. Kill. Repeat` without the final dot |
| `Daredevil 005` (cover `ANNUAL #1`), `Naruto Vol 12`, `Spawn c2c 17689`, `Superman 001` (cover says Batman), `X-Men 001 [rus]` | nothing | byte-identical |
| `Hellboy 001` with Sergei's ComicInfo (Publisher Dark Horse) | nothing | byte-identical |
| `Linked 001` (ComicVine link, no key) | nothing | byte-identical; a real `held` record, cause `no_key` |
| `Locked 001` (held open by another process) | write refused | byte-identical; a real `write_failed` record, `Attempt 1 of 5`, retry in 24 h |

- For the 7 written archives: Series, Number and Publisher exactly as expected, no other field except Notes; page bytes unchanged; the Notes carry the in-book line; one history row with the right source and one ledger row (`automatic`, fields exactly as written). No backup, temp or leftover file remained anywhere in the library.
- Problems feed: `write_failed` 1, `held` 1, all others 0. The dashboard showed the zero sentence, the key line, and `2 comics are retrying on their own`.
- **Quit.** This is a localhost server with no tray or close button, so quitting is ending the process. Ending each server's process tree left 0 processes and a closed port every time. The CTRL_BREAK orphan-worker behavior (Q3-9, pre-existing) was not retested.
- **A first-contact `503 Progress snapshot is preparing`** and a one-poll-behind snapshot are the existing design (V4-12).

## 7. Findings

No Blockers. No Majors.

| ID | Severity | Where | What | Repro |
|---|---|---|---|---|
| V4-1 | Minor | `in_book.normalize_series`, `KEPT_FINAL_DOT` | **A real title that ends in a dot loses it.** `Hunt. Kill. Repeat.` (4 live comics), `Beware...`, `Midnight, Mass.` Of 12,740 live filenames: 6 regressions against 9 improvements. Self-corrects only if a verified source later answers. Suggest: keep a final dot or ellipsis unless it is a separator. | `pG`, real-service run (`Hunt. Kill. Repeat. 001`) |
| V4-2 | Minor | `provenance.disagrees` -> `imprints.publisher_key` | **Publisher spelling variants replace the canonical in-book name**, which README and SOURCE_CONNECTORS say they do not. `Image Comics` against `Image Comics, Inc.`, `Marvel` against `Marvel Comics Group`, `Marvel Entertainment`, `DC Comics` against `DC Comics Inc.`, `DC Entertainment`, `Dark Horse Comics, Inc.`, `IDW Publishing, LLC`, `Oni Press, Inc.`, `Archie Comic Publications`: all `disagrees=True`. Effect is cosmetic, but it costs an archive rewrite and mixes spellings in the library. Only exact aliases (`Image`, `DC`, `Dark Horse`) count as the same. | `pD` |
| V4-3 | Minor | `automatic.external_plan`, `imprints.split` | **An Imprint can be written beside a human's Publisher of another house.** Human `Dark Horse Comics` plus verified `Skybound` gives Imprint `Skybound` and Publisher unchanged. v0.1.3 wrote nothing. Human value kept. | `pC` C7 |
| V4-4 | Minor (for Sergei) | `imprints.IMPRINT_PARENTS` | **The imprint table is date-blind.** `WildStorm` gives `DC Comics` for Image-era books; `Shadowline` gives `Image Comics` for 1980s Epic-era books; `Archaia` gives `BOOM! Studios` before 2013. Unconfirmed against real source data. | `pB` |
| V4-5 | Minor | `in_book.filename_number_doubt` | **Price-shaped decimals are accepted as filename numbers** (`Batman 2.99` writes Number `2.99`). `0.5` and `1.5` are also written (intended, per the code comment). 0 of the 11 corpus mismatches were this kind. | `pA` |
| V4-6 | Minor (for Sergei and Ender, before the GPU pilot) | `pilot_credits.compare` | **The pilot's Publisher comparison is not imprint-aware.** A Kroma-type comic (cover and credits `Image Comics`, source `Skybound`) counts as a disagreement, while the product now treats it as agreeing. With `max_disagreements` 0 the gate fails on any imprint book. | `pM` (fixture `Kroma 001`) |
| V4-7 | Minor (Judy) | `static/index.html`, Details block | **No gap between the reason line and the `Last error:` box** (0 px at 1440, 700 and 320 px). No overlap. | `dlg320`, `v014_1440_details_write_stopped.png` |
| V4-8 | Minor (Judy, copy) | `problemMessage` | **`Attempt 6 of 5 failed`** after a second Try again (count 6 against limit 5). The template is literal. | `v014_report.json`; `pI` (Hellblazer) |
| V4-9 | Minor (Judy) | `td.file-actions` | **7 px sideways scroll at 320 px** (22 px with a classic scrollbar); 0 px from 360 px up. Not a regression (v0.1.3: 69 px). The Comic column is 94 px wide at 320, so reasons wrap very narrow. | section 5 |
| V4-10 | Note | `VERSION`, `CHANGELOG.md` | Still `0.1.3`; no 0.1.4 entry; the badge shows v0.1.3. Sully's bump. | `v014_1440_all_viewport.png` |
| V4-11 | Minor, **pre-existing** (same line in v0.1.3) | `worker.py:155` | `automatic.get('library_root', automatic['root'])` evaluates `automatic['root']` anyway, so a config with only `library_root` raises `KeyError: 'root'` and processing silently never starts. `app.live_root()` accepts either key, so the dashboard looks normal; only the progress line says "Automatic lookup waiting" with detail `'root'`. | `pQ` first attempt |
| V4-12 | Note, pre-existing | `progress_snapshot.Snapshot.get` | Request-driven refresh: each poll returns the previous refresh, so after an external change the chips can be one poll behind (I saw 2 to 3 s, once about 20 s after an idle gap). The first request after start returns 503 `preparing`. | `pT`, `pL` |
| V4-13 | Note | `/api/try-again` | Malformed bodies return raw Python exception text (`'comic'`, `invalid literal for int()...`); a float id (`1.5`) is truncated to comic 1. Same-origin only; the page sends valid ids. | `pI` |
| V4-14 | Note | `lens_verification.solved_hold` | A damaged `solved_checks` value (string count or time, float count) raises a TypeError on the next solve. Only the app writes that record. | `pP` |
| V4-15 | Note | `in_book.normalize_series` | `X_Men` gives `X Men` (hyphen not restored); `Don_T` gives `Don'T`; `Zombies_s` gives `Zombies's`. Contrived. | `pD` |
| V4-16 | Note, pre-existing | `#roots` text | A long unbroken library path overflows the page sideways at 320 px (84 px with my 160-character scratch path). `Y:\Comix` is fine. | `diag320` |

Pattern alerts: none.

## 8. What I did not test

- **The real models and sources.** No cover or credits reading by the local model (no model use at all), no real Metron, GCD, Google Books or ComicVine answers; replacement ran against mocked sources only. The 99.4% publisher agreement figure is the 2026-10-13 pilot's, not mine. **The GPU pilot (`pilot_credits.py`) was not run**; it needs its own away window.
- **The folder scheduler's timing for Try again.** Each pass was driven directly; the "next folder pass" delay (about 10 minutes per folder) comes from the code.
- **Lens windows.** No Lens or verification window was opened; the solved-check logic ran as unit logic and as my simulation, plus Ender's service tests.
- **Buttons that call out:** `Folder` (opens Explorer), `Find series` and `Approve` (ComicVine), `Pause & release GPU` against a real model (the unload was attempted and refused by the guard).
- **The live library and live queue** (`Y:\Comix`), the packaged build or scheduled task, and Sergei's own browser. YACReader's display of the Imprint.
- **Scrollbar variants.** The 7 px figure is with scrollbars hidden (Ender's method). I also computed 22 px with a classic scrollbar. Light theme: none exists. 200% zoom was not measured.
- **The native dropdown popup** (headless cannot render it).

## 9. Regression verification and records

- **Verified against eb64759:** the v0.1.3 misleading summary lines are gone (1 to 0, positive control on v0.1.3); the old ten status filters give identical totals; the v0.1.3 safety behaviors in the core-flow run (ComicVine-linked, human-tagged, translation-tagged and mismatched comics byte-identical; backup removed after verified read-back; no leftovers).
- **Evidence.** Scripts, logs and results: `scratchpad\f014\probes\` (every probe and rig), `logs\` (suite, DOM, probe and server logs, the guard logs, the three cleanup manifests), `evidence\` (screenshots, the DOM tests' evidence, `pipe_expectations.json`, and the corpus result files `series_corpus.json`, `number_wrong.json`, `e2e_wrong.json`, which hold real filenames from the read-only catalog copy).

## 10. Cleanup (studio-disk-hygiene)

Owner: Futaba, this session. Purpose: pinned extractions, fixtures, fixture app data and the read-only catalog copy, all finished. Retained: this report, screenshots, probe scripts, logs, corpus result files.

- **Removed individually, after hash verification:** 12 files with protected names (`.env.example` in 7 copies, `provenance.py` in 5), each byte-identical to the committed blob.
- **Planner runs:** `cleanup_manifest_fx_perf.json` (SHA256 `6362f173ee7cc4871a12792d8bcaaa12f9022fdc19c1fcaffa955a0935cfc2d5`): complete, 18,497,536 logical bytes. `cleanup_manifest_dropall.json` (SHA256 `b1f085677c944683a3aa9bf0100386f922153439409e6d864088b2857683eada`): 1,065 files and 57 directories, 40,924,478 logical bytes, 37 batches. Final state is recorded in the last paragraph of this section.
- **Left on purpose, mine, small, inert:** `probes\` (the scripts), `guard\sitecustomize.py`, `logs\`, `evidence\`, the three cleanup manifests.

**Final state: complete, verified.**
- `cleanup_manifest_fx_perf.json`: `verify` complete, 18,497,536 logical bytes absent.
- `cleanup_manifest_dropall.json`: batches 0 to 2 were removed (95 files, 1,275,132 logical bytes). Each printed `rm` batch is about 6,000 characters because of my scratchpad's long path, so I renamed the remaining root (a rename, no deletion) to a short folder of my own, `...\Temp\claude\fd14`, and planned it again rather than run 34 more long batches. That manifest, `cleanup_manifest_dropall.json`, is frozen for the old root path, so its own `verify` is no longer meaningful.
- `cleanup_manifest_fd14.json` (SHA256 `0d803e16f6fbc40537c10282ac1376ba26c19773d554605f57844934e6c84865`, recomputed with `sha256sum` before the first removal): 970 files and 57 directories, 39,649,346 logical bytes, 17 batches (16 file batches, 1 directory batch). Each batch was checked immediately before its removal and the printed command was run exactly as printed. `verify`: **complete**, 1,027 absent paths, 0 remaining.
- These are recorded sizes of planned files, not measured free disk space. About 59.4 MB of logical bytes were removed through the planner, plus the 12 individually verified files.
- The temp container `...\Temp\claude` is shared with other sessions; the planner only ever touched `fd14` there, a folder I created. It no longer exists.
- Afterwards: no process of mine running, ports 18841, 18842 and 18851 closed, no headless lease, no `subst` mapping; the live service on 8765 (PID 24880) never touched; the worktree's tracked tree clean at eb64759.

**Verdict:** GO
