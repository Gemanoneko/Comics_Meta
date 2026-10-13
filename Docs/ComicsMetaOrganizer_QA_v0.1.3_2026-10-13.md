# Comics Meta Organizer — QA Report v0.1.3 (candidate f677193)

**Tool:** Comics Meta Organizer (Python, local dashboard + workers)
**Build under test:** branch `feat/v0.1.3-throughput`, commit `f6771933e757229b43c5bbb93211b598b9f7d065` (tree `09b3927b6abe214d99c3d04dcc3e5bdd1d973908`), on the released v0.1.2 (`31798b6`). `git diff 31798b6..f677193`: 38 files, +2,732 / -125.
**Date:** 2026-10-13. **Tester:** Futaba (QA / Dogfooder). Reports to Jane. Senua's construction verdict is a separate document; an untracked `Docs/ComicsMetaOrganizer_CodeReview_v0.1.3_2026-10-13.md` exists in the worktree and I did not open it.

## 0. Summary

- **NO-GO for f677193, on one Major (Q3-1): a single failed write strands the whole multi-comic plan.** One locked file, one failed read-back, one failed backup check, or one edit landing in the digest-to-write window puts the entire plan ticket into `needs_attention`. Every later comic in the plan (up to 49) is left unwritten, and all of them stay excluded from discovery, with no automatic recovery and no dashboard action. On v0.1.2 the same failure strands one comic. Reproduced three ways: a 10-comic plan with one locked file (6 innocent comics stranded, all 10 excluded), a real-app smoke run in which my own status poller happened to open one comic during the write (20 of 150 stranded), and injected read-back and backup-digest failures.
- **Everything else asked for holds.** The in-book tier never wrote anything it promised not to write (ComicVine-linked, identity-conflict, held, `[rus]`, `(fr)`, `LanguageISO`, unread or different cover number, volume/book/part, reading-order prefix with digits, "(180)", previews/ad pages, collections with inner numbers). Per comic, the backup, read-back and SHA-256 chain held in every plan, including under injected failures. A comic changed after planning is skipped and logged. The v0.1.2 safety probes (`p1`, `p2`, `p3`, `p5`, `p9`, `p11` to `p15e`) give the same results as on v0.1.2. Source switches stop requests and restore them. The suite (550) and the 33 DOM tests pass, and the real-app smoke is clean (21 of 21).
- **Throughput claim holds.** Per write, on my fixture with a 3,000-ticket queue backlog: v0.1.2 about 1.3 s of fixed cost (0.59 s write cycle + 0.76 s discovery pass); v0.1.3 about 0.04 s per comic in a 50-comic plan. With 25 MB comics the I/O floor is about 0.21 s per comic.
- **A measured accuracy ceiling for the Series string (Q3-2, Minor, for Sergei).** Against 13,389 already-tagged live filenames, assuming a perfect cover reader, 98.7% of the Series the tier would write equals the ComicInfo Series. 1.3% differ: arc or chapter words after the true title (0.8%), lost accents and underscores (0.5%). That is the Brief's own revisit trigger for the in-book decision ("Futaba's sample finds one"), so it is reported here as a decision for Sergei, not as a block.
- **The branch moved while I tested.** HEAD is now `7dcfe0e` ("fix: Guard each pass-plan write against mid-pass edits and isolate per-comic failures", committed 09:14). Its message names Q3-1. I did not test it. This verdict is for f677193 only and does not carry to 7dcfe0e, which needs its own regression pass.

Pattern alerts: 1 (P-3, section 11).

Scope of the verdict: the content of commit f677193. `VERSION` reads `0.1.2` and `CHANGELOG.md` has no 0.1.3 entry at this commit (the dashboard badge shows v0.1.2). That is Sully's bump, and any release must be a version-and-changelog-only commit on top of a commit that gets a GO.

---

## 1. Build identity and isolation

- qa-handoff entry check: **not applicable** (no `package.json`; recorded by hand as in v0.1.2).
- Tested from committed content only: `git archive f677193` extracted three times (`snap` for the suite and DOM tests, `probe` for probes and per-scenario copies, `smoke` kept pristine) plus `git archive 31798b6` (`base`) for controls, and `mix2` (v0.1.2 source with the v0.1.3 tests) to prove the new tests can fail. The extraction's tree hash equals the commit's tree. Every end-to-end scenario ran in its own copy of the pinned source, with the real `app.BASE` and `app.DATA` of that copy (nothing patched), a localhost-only socket guard and `urlopen` replaced by a recorder that raises. The rig-based probes (`p11` to `p15e`, `p30`, `p34`) patch the data paths to isolated folders, as in earlier rounds. The real app ran only from a pinned copy, on ports 18795 and 18796, with HTTP and HTTPS proxies pointed at a dead port and no API key.
- Nothing was written to git or to the worktree except this report. The tracked tree is clean; the only untracked files are Senua's review and this report. (One slip: I ran `python -I pilot_credits.py --help` with the worktree as the working directory. It failed on `import app` before doing anything, and I confirmed no `__pycache__` or other file appeared.)
- **Live contact, disclosed.** (1) A read-only `?mode=ro` copy of the live catalog's `comics` table (40,039 rows: path, size, series, number, year, status, metadata) into the scratchpad, used for the filename-side accuracy measurements. (2) A directory listing of the main checkout's `data/` to find the catalog file, and one `netstat` to confirm the live listener (PID 18392 on 8765) is unchanged. I did **not** read the live `data/research` evidence files (the saved cover readings), the queue, the live service, Y:\Comix, any profile or any quota. Nothing was sent to ComicVine, Metron, Google, Bing or any other provider.
- **The worktree moved during the pass.** At pinning HEAD was f677193. At about 09:19 HEAD was `7dcfe0e` (committed 09:14). I saw only `git diff --stat f677193..7dcfe0e` (13 files). I also read one stretch of `automatic.py` from the worktree after the move without noticing; nothing in this report depends on it, because every test and probe ran from the pinned extractions and every other source read was by commit hash or before 09:14.

## 2. Suite results

| Run | Where | Result |
|---|---|---|
| `python -B -m unittest discover -s tests` (f677193) | `snap` | **Ran 550 tests in 44.6 s, OK (skipped=33)**, exit 0 |
| Delta against v0.1.2 (475) | | 550 - 475 = +75 = the 75 `def test_` methods added in the diff (0 removed) |
| The 33 skipped DOM tests | `snap`, through the canonical `scripts/qa/headless-browser.mjs run` (lease `114d7583ea95`, offline), `COMICS_TEST_CDP` = the lease's HTTP endpoint, `COMICS_TEST_EVIDENCE` set | **Ran 33 tests in 13.3 s, OK**; `list`: no leases afterwards |
| Positive control: the v0.1.3 tests against v0.1.2 source (`mix2`) | | **Ran 504, FAILED (failures=9, errors=63)**; new modules fail to import or assert, so the new tests can fail |

550 of 550 executed and passed. Suite debris: a full run in the pristine copy added 0 files and 0 empty directories (v0.1.2 left two empty directories, R2-9; that item is now closed). One `ResourceWarning` (unclosed `HTTPError 429`) is printed, as in round 4.

## 3. Change-by-change verification (against f677193)

| # | Change | Result | Evidence |
|---|---|---|---|
| 1 | In-book tier | **PASS** with Q3-2 to Q3-5 (Minor) | Sections 5 and 6. Writes Series+Number when title and number agree, Series for an unnumbered whole book, Publisher only when a canonical publisher is named in full; Notes line, history source `in-book:cover`, per-field evidence all present; empty fields only; no Writer or Year in any entry (150-comic real-app run, 60-comic and 12-route runs). Credits tier default off: `identify` returns None and `ready` is False for a saved indicia reading. |
| 2 | Multi-comic plans, skip on change | **PASS for the change case; FAIL for the error case (Q3-1)** | 60 comics: pass 1 = one ticket with 50 entries, pass 2 = the remaining 10, pass 3 = nothing. Each entry has its own sha256, changes, source and evidence. Changed comic: skipped, `skipped.json` names it with the reason, the other three written, its file byte-identical to what the other program left. |
| 3 | Fast folder selection | **PASS** | Differential against v0.1.2 on real-shaped paths with legacy history variants (raw, `\\?\`, UNC, upper, lower): identical folder sequences at 5,000 paths (40 folders) and 12,000 paths (90 folders). Median probe 0.014 s vs 0.128 s (5,000) and 0.020 s vs 0.651 s (12,000); 40,039 paths: 0.040 s median, 0.120 s max. |
| 4 | Yandex removed; zero-yield sources off by default | **PASS** (Q3-5) | Real app: `/api/browser-verification` returns `yandex: null`; POST `/api/yandex-verification` with a trusted origin returns 400 "Yandex web search is switched off."; foreign or missing origin 403; dashboard text has no "Yandex" and the row is hidden, before and after a pass. v0.1.2 as control shows the Yandex state and a different POST error. Source switches: section 7. |
| 5 | Metron name variants and variant covers | **PASS** (Q3-6) | 17 checks on the real `metron.lookup` with stand-ins only at `candidates`, `request` and `verified_cover`: " - " and ": " swap both ways, "Vol. N" / "vN" / "(Vol N)" tail with the volume required to agree (volume 1 for a Vol. 2 file rejected, unknown volume accepted), two same-series candidates rejected, "Batman" never matches "Batman Beyond", wrong number, wrong year and non-English rejected, variant accepted (scope names it, GTIN dropped), only the first 8 variants tried. The real `verified_cover` refuses 8 hostile URL shapes without opening a connection. |
| 6 | Yield ordering; ComicVine as identity check after Metron | **PASS** | Real `discover()` and `app.api`, 10 checks: Metron answer plus agreeing ComicVine writes Metron's fields and asks ComicVine once, for the issue only; ComicVine conflict blocks Metron's verified fields; ComicVine outage holds them and a later matching answer writes the kept evidence; no Web link: ComicVine never asked (also not searched when Metron has nothing); Metron absent: ComicVine path as before. Row order: in-book-ready first, then Metron-untried, written last. |
| 7 | Held comics back off (F18) | **PASS** | 24 checks, section 4. |
| 8 | Progress payload capped; library walk every 6 h | **PASS** | 450 batches: payload lists the 100 most recent, `completed_total` is 450 (7.8 KB payload); `keep_recent_batches` keeps 200 and archives 250 to `progress-history.jsonl` in order, nothing lost, idempotent. Walk: a folder added after the walk is not seen at +10 min, +1 h, +5 h, +5 h 59 min, and is found at +6 h 05 s; `inventory_interval_seconds: 30` is clamped to 600 s. |
| 9 | Credits/indicia tier off by default | **PASS** | Default config: `cover` true, `publisher` true, `credits_pages` false, `credits_creators` false; the tier never fired in any run. `pilot_credits.py` is read-only and was not run. |

## 4. v0.1.2 safety re-run (my `p11` to `p15e`, adapted) and earlier-round probes

The same probe scripts ran against v0.1.2 (`base`, control) and v0.1.3 (`probe`).

| Probe | v0.1.2 | v0.1.3 | Note |
|---|---|---|---|
| `p12` conflict, reuse and outage matrix (85 checks) | 84 pass, 1 fail (S6) | **84 pass, 1 fail (S6)** | S6 asserts the old R3-1 defect and cannot pass (R4.0). On the unmodified script v0.1.3 shows 9 more failures; all 9 are the check `getcomics == [True]`, which is false because GetComics is off by default. With `sources.disabled = []`, or with that one test adapted, the result is again 84 of 85. Expectation drift, not a regression. |
| `p11` two-pass conflict (4) | 3 pass, 1 control line fails | same | The control expects an empty ComicVine answer to write; F16 holds it on purpose. |
| `p13` wiring and names (13) | 13 pass | **13 pass** | |
| `p14` dead-link cascade (3) | 3 pass | **3 pass** | |
| `p15a` API answer shapes (44) | 44 pass | **44 pass** | |
| `p15b` dead-id writes (40) | 40 pass | **40 pass** with all sources on; 36 pass, 4 fail by default | The 4 assert that GetComics ran strictly (drift, as above). `B0a` still writes for a no-link comic. |
| `p15c` neighbours and outages (85) | 85 pass | **85 pass** | |
| `p15d` publisher routes (8), `p15e` repeat cost (2) | all pass | **all pass** | |
| `p1` identity (37), `p2` covers (38), `p3` workers (47), `p5` Lens session (18), `p9` lifecycle (26), `p8` hit rate | all pass | **all pass, identical** | |

**F18 back-off (`p30`, 24 checks, real `discover`, `discovery_state`, `app.api`).** With ComicVine under a 5-minute pause at each pass, the retry intervals are 300, 600, 1,200, 2,400, 3,600, 3,600, 3,600 s for hold counts 1 to 7. The first held pass does the strict searches (4 lookups); passes 2 to 7 do **no** source search, no local-model cover read and no Lens task (counters 0). With the local model on, pass 1 reads the cover once and later passes do not. An unreachable service keeps its own hour (not earlier); a missing key keeps the daily retry (24 h, twice). Wake-up (`lookup_flags`): woken only when the comic's own wait has ended, ComicVine is `available` and answered after the hold; not woken for an unexpired wait, an earlier answer, an unavailable service or a hold with no known end. **Positive control:** on v0.1.2 every pass retries at 300 s and 14 of the 24 checks fail.

## 5. Red team of the in-book tier

### 5.1 Targeted cases (`p23`, 133 rows through the real `identify`)

Of 133 rows, 9 wrote where a no-write was expected (1 inconsistent reading and 8 translation-tag styles; Q3-3 and Q3-4). One more failed only because my expectation was wrong: the unnumbered "Daredevil by Frank Miller Omnibus" is a safe no-write. The rest behaved as expected or are recorded as observations:

| Class | Result |
|---|---|
| Misread covers | Wrong digit, price ("$3.99", "3.99" against file 399), "5A" against 5, bool, list and string readings, a different series with the same number, cover longer than the file's series ("Batman Beyond" on "Batman 001"): **no write**. Cover shorter than the filename series ("BATMAN" on "Batman Beyond 001", "SPIDER-MAN" on "Amazing Spider-Man 001", "JUSTICE LEAGUE" on "Justice League of America 001", "SPAWN" on "Curse of the Spawn 001"): **writes the filename's longer Series** by design (`cover_title_within_filename`); if the filename is wrong the cover cannot catch it. Title "BATMAN #2" with issue field "1": **writes Number 1** (Q3-4). |
| Reading-order prefixes | "003 Strange Academy - Blood Hunt 002" and "003 - Strange Academy 002": no write. "[003] Strange Academy 002" and "(003) ...": writes Series "Strange Academy" (correct, the bracket is stripped). A prefix made of words ("Marvel Reading Order - Avengers 012", "Part Two - Avengers 012"): **writes the prefixed string as Series** (Q3-2). |
| Number inside a chapter name | "Superman - Chapter 4 - The Return 012", "Batman Year One Part 3 004", "Batman Part 2", "Tome 5", "Bk 2": no write. "(Chapter 01) - Hellbourne 001" (the parenthetical is stripped before the digit guard looks): writes "Hellwitch - Hellbourne". "Superman - Chapter Four - ...", "Doctor Who Episode 4", "Fables Act 3", "Copra, Round 7", "Ask For Mercy Season Four 002": writes Series with the chapter word inside, e.g. "Doctor Who Episode" (Q3-2). |
| "(180)" | "(180)" against cover 75, "(180) (3)": no write. "(180)" with cover 180: writes Number 180 (control). "Watchmen (2)" with cover "2" writes Number 2 (a copy marker, Q3-5). |
| `[rus]` | `[rus]`, `[RUS]`, `(Rus)`, `(ru)`, `(russian)`, `{rus}`, "Russian Edition", `(fr)`: no write. **Not recognised:** Cyrillic `(Рус)`, `[RU-EN]`, `(rus-eng)`, `[Español]`, `[Deutsch]`, `(Portugues-BR)`, `[pt-br]`, `(Francais)`, and a language word in the folder (Q3-3). `LanguageISO: ru` is caught by discovery, not by `identify`. |
| Collections with inner numbers | Cover "#1" on an unnumbered "Batman - The Long Halloween": Series only. "Saga TPB 1", "Vol 1", "Volume 1", "Book 1", "Bk 2", "Y The Last Man Book One": no write. Ranges ("Saga #1-6", "01-06", "001-006"): no write. "Compendium 1", "Masterworks 12", "Archives 3", "Essential X-Men 2", "Library Edition 3": writes the volume number as Number (Q3-5). "Batman Annual 2018" with cover "2018": writes Number 2018 (Q3-5). |
| Previews and ads | Ad page for another series, "TODD McFARLANE TOYS", "FREE COMIC BOOK DAY", "PREVIEWS" with no number, and an ad for the next issue: no write. A house ad for the same series with the same number as the file would agree (inherent). |
| Near-identical names | "Batman and Robin" cover on "Batman 001": no write. File longer than cover: see misread covers. "The Flash" and "Flash" agree (article ignored). |
| "Book" as the last word | "Saga Book 1": no write. "The Jungle Book" (unnumbered): no write, safe false negative. |
| Existing metadata | Different Series, different Number, a year-suffixed Series ("Spawn (1992)"): no write. Everything populated: no write. Whitespace-only Series counts as empty. Writer present is never touched. Creators and year on the cover are never written. |
| ComicVine rules | `Web` naming `4000-N` (https, http, www, mixed with another URL): no write. Upper-case host, `comicvine.com`, a `4050-` volume URL, an ID only in Notes: write, **consistent with `discover`, which uses the identical case-sensitive test**. Previous record `identity_conflict` or a saved `conflict_issue`: no write. A held record without a Web link writes (a hold requires a link, so this state does not occur). |

### 5.2 Filename side against the live catalog (read-only snapshot, 40,039 comics; no cover readings used)

I assumed a **perfect** cover reader and compared what the tier would write with the ComicInfo already on tagged comics.

| Measure | Result |
|---|---|
| Tagged live comics (Series populated, ComicVine-linked ones included) | 13,389; the tier would write for 10,537 (2,852 refused by the filename rules) |
| Series equals the ComicInfo Series | **10,398 of 10,537 (98.7%)** |
| Series differs | **139 (1.3%)**: 79 arc, chapter or subtitle words after the true title and 7 other, all in the `within` agreement; 51 accents, underscores or punctuation ("The_Tale_of_One_Bad_Rat", "Betelgeuse" for "Bételgeuse", "Assassin_s Creed"); 2 other. No real Number difference (2 flagged rows come from ComicInfo Series strings that contain "#"). |
| Comics with an empty, non-ComicVine Series (the candidates for the tier) | 26,650; of these, if a reader agrees with the filename, 707 would get a Series containing underscores, 207 a Number that is a year (for example "Bikini Special 2005" would become Number 2005), 503 a Series carrying a scanner tag |
| Filenames with a language hint not caught by either rule | 122 of 335 hints; most are false positives (the "Ѕ" half glyph); the real group is about 35 files in folders named "(RU)" or "French Comics" |

The 8,334 live comics the Brief calls writable depend on the saved readings, which I did not read (excluded). The ceiling above is therefore a filename-side estimate, not a measured error rate of the real model.

## 6. Multi-comic plans and the safety chain

| Scenario (`e2e1` to `e2e9`) | Result |
|---|---|
| 60 comics, real discover and worker | Plans 50 + 10; 50 results each `metadata_readback_verified`, `backup_sha256_verified`, `backup_removed_after_verification`; history 50 rows with source `in-book:cover` and the backup path (file gone); no leftover backup or `.metadata-tmp`; Year untouched, no Writer or Summary; discovery record `queued` / `in_book` / 30-day retry. Pass 3 plans nothing (the saved readings no longer match the rewritten archives). 20 of 20 checks. |
| Mixed folder, 13 comics | Plan = exactly the four writable comics; NOT planned: ComicVine-linked, saved conflict plus link, held with link, `[rus]`, `(fr)`, `LanguageISO ru`, cover number differs, nothing to fill, stale reading. 26 of 26 checks. Files of every blocked comic are byte-identical afterwards. |
| One pass, six routes | In-book, Metron plus synopsis, ComicVine ID, ComicVine conflict, nothing found, in-book: no entry carries another comic's field, Note or Summary. 12 of 12. |
| Awkward files | No ComicInfo, utf-16 ComicInfo, accents and "&" in the name, brackets, a path over 260 characters, a CBR, duplicate ComicInfo entries (status `error`): written or excluded correctly. 8 of 8. |
| Safety chain under injected failure | Read-back mismatch on comic 2: ticket `needs_attention` "Readback verification failed for Series", comic 1 verified and its backup removed, comic 2's backup **retained and byte-identical to the original**, comics 3 to 5 unwritten. Corrupted backup copy on comic 2: "Backup verification failed.", backup retained and different from the original. Clean control: all five verified, no backup left. 17 of 17. |
| **Locked file (Q3-1)** | 10 comics in one plan, comic 4 open in another program (plain `open()` has no share-delete): `[WinError 5] Access is denied` at the replace; ticket `needs_attention`; comics 1 to 3 written; **6 comics (5 to 10) unwritten**; backup of comic 4 retained; after the lock is released a new discovery pass plans nothing: all 10 stay excluded (`pending_paths` counts `needs_attention`). **v0.1.2, same fixture with one plan per comic: 9 written, 1 stranded.** |
| Edit in the digest-to-write window | A comic edited by another program after the plan digest check and before the write is **rewritten** with our fields (the other program's edit is kept), and the failure is only caught afterwards by the backup digest ("Backup verification failed.", backup retained). Same on v0.1.2 (pre-existing; "never writes a changed comic" holds up to that small window). On v0.1.3 it also strands the rest of the plan (2 comics here). |

## 7. Source switches, Yandex, config

Real `discover()` over three comics with no link and no reading, with every network edge a recorder.

| Config | Requests made |
|---|---|
| Default (no `config.json`) | GCD 3, Google Books 3, Metron 3, Open Library 3, Dark Horse 3, Image 3. **General free web 0, Wikipedia 0, GetComics 0, PREVIEWSworld 0.** Attempts recorded as `switched_off` for GetComics and PREVIEWSworld. |
| `sources.disabled = []` | Everything back: GetComics 3, PREVIEWSworld 3, web search 6, wiki fetch 4. |
| `["Metron"]` | Metron 0, `switched_off`; all others as with `[]`. |
| `["GetComics", "PREVIEWSworld"]` | Those two 0; general web and wiki back on. |
| Saved lead re-checks (`resolve_leads`, 5 calls) | Default: a lead already rejected for the same archive, identity and strictness is not fetched again (a lead that failed to load is); a new lead is fetched; a changed archive or a strict flag re-checks all. With `[]`: everything is re-fetched every time. |

The recorders at the network edges returned nothing, and nothing reached `urlopen` in any of these runs, so nothing left the machine. `"in_book": {"cover": false}` plans nothing; `{"publisher": false}` drops Publisher from the entries.

## 8. Smoke test (the real app)

Real `app.py --no-browser --port 18795` (supervisor and workers) from the pinned copy, with a fixture library (163 comics: 150 Spawn with saved readings, 10 in `Mixed` and `Linked`, 3 `Plain`) and a fixture saved-reading catalog (160 readings, written through the real `research.save_evidence`), dashboard loaded in a headless browser (lease `4f8e82ea9e18`, three earlier runs of the same script under leases `df62c2e0bb28` and `d42023f56205`).

- Starts in 0.5 s; `/`, `/api/state`, `/api/progress`, `/api/browser-verification`, `/lens-control.js`, `/api/comics?status=missing` all 200; version badge **v0.1.2**.
- **The dashboard shows "In-book identification: Spawn 050 (1992).cbz"** (also 055, 100, ...), seen both through `/api/progress` and in the rendered DOM by a mutation observer. **No Yandex row and no "Yandex" text** before or after the pass; `/api/browser-verification` has `yandex: null`.
- 150 Spawn comics and the writable `Alpha` comic written in 45.5 s by the real worker: tickets of 1, 50, 50 and 50 entries took 0.05, 1.78, 1.67 and 1.74 s. Every file carries Series, Number, Publisher, the Notes line and the old Year; no backup left. `Bravo` (ComicVine link), `Echo` (`[rus]`), `Foxtrot` (cover number differs), `Golf` (`LanguageISO ru`), `India` (nothing to fill), all four `Linked` and all `Plain` comics are byte-identical afterwards.
- No `verification_url` or `verification_task` in any served payload.
- Quit: this is a localhost server with no tray or close button, so quitting is ending the process. `taskkill /T /F` ended the server and all its python descendants, 0 left, port closed, no headless lease left. A second run (port 18796) ended the server with CTRL_BREAK but **left its two worker processes running** (orphans); the same happens on v0.1.2, so it is not a regression (Q3-9). I ended those four orphan processes of mine by PID.
- A first real-app run with 150 comics ended with a stranded plan (Q3-1) because my own status poller opened `Spawn 031` while the worker was replacing it. I changed the poller to read only queue files and reran; the numbers above are from the clean rerun.

## 9. Performance (per write, fixture)

Fixture: one folder, a 3,000-ticket completed-queue backlog (Sergei's live queue keeps thousands), real `worker.run_one` and `automatic.discover`. "Discovery pass" is the fixed cost of one pass with nothing due.

| Case | v0.1.2 | v0.1.3 |
|---|---|---|
| 100 comics of 40 KB, one plan per comic: write cycle per comic | 0.587 s | 0.111 s |
| Same, discovery pass | 0.755 s | 0.395 s |
| 100 comics, plans of 50: write cycle per comic | 0.064 s | **0.031 s** |
| 12 comics of 25 MB, one plan per comic: write cycle per comic | 0.814 s | 0.280 s |
| Same, plans of 50 | | 0.214 s |
| Discovery pass, 12 comics | 0.495 s | 0.097 s |

In v0.1.2 every comic paid a write cycle plus a discovery pass (about 1.3 s of fixed cost on this fixture); in v0.1.3 a 50-comic plan pays one pass and one ticket scan (about 0.04 s per comic plus the I/O floor). One cost went the other way: a discovery pass over a 1,000-comic folder whose comics all carry 30 KB of saved evidence takes 5.74 s against 5.12 s on v0.1.2 (`order_rows` now reads each row's evidence), about 12% more (Q3-8).

## 10. Findings

Severity: Blocker / Major / Minor. No Blocker. One Major. Flag only: no code was changed.

| ID | Sev | Area | Finding | Repro | Status |
|---|---|---|---|---|---|
| Q3-1 | **Major** (new in this build) | `batch.apply`, `worker.run_one`, `coverage_priority.pending_paths` | **One failed write strands the whole plan.** Any exception for one entry (a locked file, an antivirus hold on the temp file, a failed read-back or backup digest, an edit in the digest-to-write window) sets the ticket to `needs_attention`. The remaining entries (up to 49) are not written, and `pending_paths` keeps counting `needs_attention` tickets, so those comics are also excluded from discovery. There is no automatic retry and no dashboard action; the dashboard shows only "Your help is needed: <folder> — <error>". The README says a changed comic is skipped and the others are still written; that holds for the digest check only. On v0.1.2 a plan held one comic, so the same failure stranded one. At 50 per plan and about 167 plans for the 8,334 comics the Brief expects, a handful of transient failures could strand several hundred comics that need a manual ticket edit. Backups are retained and files intact: delay, not data loss. | `e2e3_failures.py`: 10-comic plan, comic 4 held open with a plain `open()` while `worker.run_one()` runs; v0.1.3 leaves 6 innocent comics unwritten and 10 excluded, v0.1.2 leaves none unwritten. Also `e2e4_chain.py B` and `C`, `e2e8_race.py`, and the real-app run described in section 8 | Open, for Ender. **Blocks this build.** Commit 7dcfe0e names it; untested |
| Q3-2 | Minor (Sergei decision: the Brief's revisit trigger) | `in_book.title_agreement`, `filename_identity` | The Series written is the filename's, and the cover only has to start with the same words. So extra words in the filename reach ComicInfo without any support from the cover: arc or subtitle after a dash, a chapter in parentheses ("Hellwitch (Chapter 01) - Hellbourne" → "Hellwitch - Hellbourne"), chapter words not in `VOLUME_WORDS` ("Episode 4", "Act 3", "Round 7", "Season Four"), a word reading-order prefix ("Marvel Reading Order - Avengers"), underscores ("Feeding_Ghosts"), accents lost. Measured ceiling with a perfect reader: 1.3% of writes (section 5.2). Because later sources fill only empty fields, a wrong Series is never corrected by the pipeline. The digit-based guard for "chapter naming" cannot see a parenthesised chapter, because `parse_name` strips it first. | `p20`, `p21`, `p22`, `p23` | Open; Sergei to decide whether the `within` agreement, underscore cleanup or a wider word list is wanted |
| Q3-3 | Minor | `in_book.LANGUAGE_TAG`, `judge` | A translation is recognised only by the listed tags. `[RU-EN]`, `(rus-eng)`, `(Рус)`, `[Español]`, `[Deutsch]`, `(Portugues-BR)`, `[pt-br]`, `(Francais)` are not, and the folder name is never read ("(RU)" or "French Comics" folders, about 35 live files). A translation whose cover keeps the original logo would get Series, Number and the original **Publisher**. The documented `[rus]` and `(fr)` work. | `p23`, `p24` | Open |
| Q3-4 | Minor | `in_book.cover_number` | An inconsistent reading is accepted: title "BATMAN #2" with issue "1" writes Number 1. The issue field wins and the number in the title is ignored. | `p23` | Open |
| Q3-5 | Minor | `in_book` filename rules, `pipeline_config` | Number edge cases: a year as the number ("Batman Annual 2018" with cover "2018" → Number 2018; 207 of the 26,650 empty-Series live filenames end in a year), a volume as the number ("Marvel Masterworks 12", "Saga Compendium 1", "Archives 3"), "Watchmen (2)" copy markers, cover "1/2" read as 1. Config typing: `"in_book": {"cover": "no"}` or `"false"` as a string leaves the tier **on** (only the literal `false` switches it off); `"sources": {"disabled": "GetComics"}` (a string) is silently ignored and the default list applies; a malformed `config.json` makes `discover` raise (`web_search.config` already did on v0.1.2). | `p23`, `e2e9`, `e2e5b` | Open |
| Q3-6 | Minor (note) | `metron.lookup` | Name variants and variant covers add requests: up to 3 name searches plus the issue detail per comic (v0.1.2: 1 plus detail), and up to 9 cover downloads for one unmatched comic (primary, detail, 8 variants) with no pacing between downloads. Host and scheme are restricted to `https://static.metron.cloud`. | `p33` | Note |
| Q3-7 | Minor (doc) | README | "a comic that changed after planning is skipped ... and planned again on the next pass" is not true of an in-book entry: the saved reading no longer matches the changed archive, so the comic waits for a new cover reading. The skipped comic is not lost (its record is due, nothing else writes it). | `e2e2` | Open |
| Q3-8 | Note | `coverage_priority.order_rows` | A discovery pass reads the saved evidence of every row of the folder to rank it: +0.6 s (12%) on a 1,000-comic folder with 30 KB of evidence each. | `m2_pass_cost.py` | Note |
| Q3-9 | Note (pre-existing) | `supervisor` | Ending the server with CTRL_BREAK leaves its two worker processes running; same on v0.1.2. Ending the scheduled task's whole process tree was not tested. | `smoke2_http.py` | Note |
| Q3-10 | Note | `scheduler` | New folders can take up to 6 hours to appear (default walk interval); the manual scan still works. Version badge and changelog are Sully's. | `p32` | Note |

## 11. Pattern alerts

**P-3 (new).** A guarantee is proven for the failure its author thought of, and the sibling failures are left unproven. The change case ("a comic changed after planning is skipped") has a test and a clear fix, while the error case (a comic that fails during the write) was never enumerated and aborts the plan. This is the same annoyance as P-1 and P-2 in different clothes: R2-1 held on pass 1 but not on pass 2, R3-1 held for the comic reported but not for its neighbours, and now isolation holds for one failure type but not for the others. **Disposition (proposed, Jane to confirm): fix.** Before shipping multi-comic plans, add a failure matrix to the tests: locked file, read-back mismatch, backup digest mismatch, edit inside the digest-to-write window, each at the first, a middle and the last entry, asserting that the other entries are written and nothing is excluded from discovery. My `e2e3`, `e2e4` and `e2e8` are a ready seed.

P-1 and P-2 (v0.1.2): no recurrence in the identity and hold logic this round; the `p12` and `p15` matrices hold on v0.1.3. Dispositions unchanged (P-1 fixed for the gates, P-2 deferred).

## 12. Not tested (UNTESTED, with reason)

- **The real cover reader's output on Sergei's comics.** The saved readings live in the live `data/research`, which was excluded. Q3-2 and Q3-3 are filename-side estimates, and the "about 8,334 writable" figure is unverified. A read-only copy of those evidence files, if Jane allows it, would turn the 1.3% ceiling into a measured rate.
- **Real YACReader, antivirus or indexer locking.** I simulated the lock with a plain `open()`. Whether YACReader opens CBZs with share-delete, and how often Bitdefender holds a fresh temp file, is unknown; it decides how often Q3-1 bites.
- **The live queue.** How many `needs_attention` tickets exist today, and how large the real completed-ticket backlog is (I assumed 3,000 for the timings). Excluded (live data).
- **Real ComicVine, Metron, Google, Bing, Lens, SerpApi** and real model output: excluded by design; mocked or absent.
- **The scheduled task's stop behaviour** (Task Scheduler "End"), and the `Pause & release GPU` button against a real model service (the smoke did not press it, to avoid contacting a local Ollama).
- **Commit 7dcfe0e** (see section 1).
- **Real-input checks:** none needed (no UI file changed in this diff); none queued.
- **Credits/indicia tier**, deliberately not enabled.

## 13. Regression record

Verified against `f6771933e757229b43c5bbb93211b598b9f7d065`: the nine changes as in section 3. The v0.1.2 safety probes (`p1`, `p2`, `p3`, `p5`, `p9`, `p11` to `p15e`) are unchanged against v0.1.2 apart from the default-off GetComics expectation drift. New: Q3-1 (Major), Q3-2 to Q3-7 (Minor), Q3-8 to Q3-10 (notes), P-3. Positive controls: v0.1.3 tests fail on v0.1.2 source (72 failures or errors); the F18 probe fails on v0.1.2; the Yandex checks fail on v0.1.2; the locked-file scenario strands 0 on v0.1.2 and 6 on v0.1.3. Headless leases (canonical harness, all ended with 0 left): `114d7583ea95` (DOM, 33 OK), `df62c2e0bb28`, `d42023f56205`, `4f8e82ea9e18` (smoke runs).

**What would flip this to GO:** a committed fix for Q3-1 that I regression-check with the locked-file, read-back, backup-digest and edit-in-window cases at the first, a middle and the last entry (the other entries written, nothing excluded from discovery), with the shipped docs corrected to say what happens on an error; or Sergei explicitly accepting Q3-1 as is. Any other code change after f677193 also needs its own pass. Q3-2 and Q3-3 do not block; they need Sergei's decision.

## 14. Disk hygiene (ProcessRules § Routine disk hygiene, method: studio-disk-hygiene)

**Cleanup is partly complete: everything bulky or sensitive of mine is removed; one folder of small synthetic test environments is left because it is out of proportion to remove by hand. Nothing of anyone else's was touched.** Sizes are the planner's logical bytes, not measured free disk.

- **Removed, in two frozen plans** (before planning I renamed the chosen folders with `mv`, no deletion, to short paths in the system temp folder so the printed commands carry more paths, as in earlier rounds):
  - Plan 1 (`cleanup_manifest_run1.json`, SHA256 `8fa274ccafbd9e781e13f1c35ab4f1bb019021c225b27f69da7a12a5456fc3aa`, confirmed with `sha256sum`): the pinned extractions `snap`, `probe`, `smoke`, `base` and `mix2`, the fixture library `smoke_lib`, three 25 MB-comic test folders, and the read-only copy of the live catalog's `comics` table. 781 files and 34 directories, 975,047,478 logical bytes, 14 batches. Each batch was checked with `check-batch` and removed by its printed literal command. Final `verify`: `absentPaths` 815, `absentLogicalBytes` 975,047,478, `remainingPaths` 0, `complete` true.
  - Plan 2 (`cleanup_manifest_run2.json`, SHA256 `d9a25bcf2a4ae9981d1be02a343a49a02b1350c6b8f0c525ff2dcaae4b6990f7`, confirmed with `sha256sum`): eight probe environments built from that catalog copy (they hold real library file names). 400 files, 25 directories, 134,434,236 logical bytes, 8 batches. Final `verify`: `absentPaths` 425, `remainingPaths` 0, `complete` true.
  - Outside the helper, after individual review (the planner protects the name): the 13 `.env.example` copies in those folders, each with the same hash as the tracked 225-byte placeholder after line-ending normalisation and no non-empty value, removed by two literal `rm --` commands. My own `verify.json` outputs and the two empty containers were removed by literal `rm --` and `rmdir --`.
- **Left on purpose, mine, small, inert:** `scratchpad/futaba_v013/` holds `probes/` (56 files: every probe and rig script, including `rig13.py`, `e2e1` to `e2e9`, `p20` to `p35`, `m1`, `m2`, the adapted `p12v`, `smoke_app.py`, `smoke2_http.py`), `logs/` (58 files plus `old/`), `evidence/` (14 files, the two dashboard screenshots among them), `tools/` and the two manifests above. It is the evidence for Q3-1 to Q3-10. To re-run: extract f677193 into `futaba_v013/probe` and 31798b6 into `futaba_v013/base`, then run the scripts (the path constant is in `common.py` and `rig13.py`; `FUTABA_SRC=probe|base` picks the build). Delete it when the findings close. Also kept: the round-4 keep folder `futaba_r4_keep` (its scripts are copied into the new one, but I did not remove an earlier round's evidence unasked) and the earlier manifests.
- **Left because it is out of proportion:** `scratchpad/futaba_v013/e2e/` (about 30,000 files, 180 MB on disk) and `scratchpad/futaba_v013/state/` (1,960 files, 1,583 directories, 38 MB). They are throw-away copies of the pinned source and probe catalogs; most of the file count is the 3,000-ticket queue backlog I created for each timing run. At the planner's 64-path limit that is several hundred `check-batch` and `rm` pairs, so I did not start. All synthetic, safe to delete; Jane to decide how to finish.
- Two disclosures. A Python script of mine removed its own fixture folder `smoke_lib` with `shutil.rmtree` before recreating it (a recursive delete outside the helper, on my own scratch fixture). And one Bash `rm -rf` of a folder that did not yet exist was refused by the studio's delete guard; I used a different folder name and deleted nothing.
- **Processes and leases:** no headless lease left (`list`: none); no python process of mine running; ports 18795 and 18796 closed. I ended, by PID and only after confirming each was mine (command line under my scratch folder): one hung probe (`p35`, PID 88404), the server tree of a crashed smoke script (PID 96956), and four orphaned worker processes left behind by CTRL_BREAK (55088, 76604, 78064, 103128). The live service (PID 18392 on 8765) was not touched and its listener is unchanged. The worktree was not written to apart from this report; the tracked tree is clean, and the untracked files are Senua's review and this report, neither committed.

**What would void this verdict:** any code change after f677193 (7dcfe0e included until it has its own pass) other than a version-and-changelog-only commit.

Round 1 verdict for f677193 (superseded by Round 3): NO-GO

---

*Rounds 2 and 3 below were written by Futaba and appended verbatim in substance by Jane. Futaba's tool refused report-file writes from a subagent, so the text was handed back. Evidence is in the session scratchpad `futaba_v013\` (`probes_r2\`, `logs\r2\`, `evidence\`).*

# Round 2 (7dcfe0e)

**Build:** `7dcfe0e174ecac0d00edd2e4c6146e7fe86d9922` (F21, F22, F23, F24, F27). Round 2 verdict for 7dcfe0e (superseded by Round 3, because the branch moved before this was written up): GO, with Q4-2 (Major, no Blocker) logged.

- **Isolation:** tested from pinned `git archive` copies (121/121 blobs verified), with own state per scenario, a socket guard, dead proxies, isolated ports and no API key. **No live contact:** the live listener (PID 18392, :8765) was untouched, and live data, the main checkout and the other worktrees were not read or written.
- **Suite:** 558 tests OK (skipped=33). 33 DOM tests OK through the canonical harness.
- **Q3-1 repro: fixed.** A 10-comic plan with one held file at the first, middle and last position: 9 of 10 written, the held comic goes to `failed.json` byte-identical, ticket `complete`, 0 excluded, and it is written after a retry. Control f677193 (middle): 4 written, 5 stranded, 10 excluded.
- **Failure matrix (63 runs):**
  - **Isolated:** viewer open (every share mode), exclusive lock from the start, leftover tmp, bad CRC page, backup copy failure.
  - **Skipped:** a planned field edited elsewhere (no backup), archive changed after planning.
  - **Carve-out** (stops the ticket, backup kept): read-back mismatch or unreadable, corrupt backup copy, catalog locked after replace, file vanished, another program editing within ~10–300 ms.
  - **Pre-existing:** an edit in the microseconds before replace is lost.
- **Carve-out judgement:** right in principle, too wide in two places (Q4-1, Minor). A viewer never triggers it. UNTESTED: real YACReader and Bitdefender (simulated with `CreateFileW` share modes).
- **`write_failed` loop at 7dcfe0e:** yes, a daily retry with no end, leaving one full backup per attempt (13 in 13 days) → Q4-2 (Major). Fixed by F29 in d3e9723.
- **Poller smoke, real app:** 148 of 150 written, 2 isolated, nothing stranded. Control f677193: 11 of 150, `needs_attention`, 139 held out.
- **F21, F24 and F27 hold** (`e2e9`, `p31` 7/7, `p36` 7/7). Earlier probes unchanged.

# Round 3 (d3e9723)

**Build:** `d3e972369d29c833d1db7a4719841a28a0783225` ("fix: Remove a failed write's own backup and cap write retries", F29). Pinned `git archive` copies, 121/121 blobs verified. Isolation as in Round 2; no live contact.

## R3.1 Suite and DOM
- Suite: **566 tests, OK (skipped=33)**. That is 558 plus the 8 `FailedWriteBackupTests`.
- 33 DOM tests: **OK** (lease `1fbd1ddb36e6`, 0 left).

## R3.2 Multi-day failures (simulated clock, 3 passes a day)
| Case | 7dcfe0e | d3e9723 |
|---|---|---|
| Bad CRC page, 12–40 days | daily attempts, **13 backups in 13 days** | attempts on days **0, 1, 3, 7, 14**, **stops at the 5th**, nothing through day 40, **0 backups** |
| Leftover `.metadata-tmp` | n/r | same schedule, stop at day 14, 0 backups |
| Held open 30 days | n/r | same schedule, stop at day 14, 0 backups |
| Held until day 10, then released | n/r | 4 failures, **written at day 14**, 0 backups |
| Re-saved at day 10, still damaged | n/r | count restarts (10, 11, 13, 17, 24), stop at day 24 |
| Repaired at day 10 or 20 | n/r | leaves `write_failed` at the next pass. Not written until a new cover reading matches the new archive (Q3-7) |

Other comics in the plan are written in every run. The `detail` text reads "Write failed (attempt N of 5 on this archive): … Next attempt in N days…", and at the stop "Automatic writes stopped after 5 failed attempts…".

## R3.3 File held open by a viewer
- **Matrix:** every share mode → `failed.json`, 9 of 10 written, **0 backups**, 0 excluded.
- **Real app (two pollers plus one held file):**
  - Phase 1: **3 failures, 147 written, 0 backups**.
  - A day later: **150 of 150**, 0 backups.
  - `/api/progress`: `queue.attention` is `[]` and `research.write_failed` is 3. The dashboard does not render `write_failed` (Q4-4).
  - Control f677193: 11 of 150, `needs_attention`, 139 held out.

## R3.4 No backup deleted when the archive may have been replaced
- **`p37` (9/9, real `batch.apply`, a real open file):**
  - Only the attempt's own backup is removed. Older same-comic backups, other comics' backups and stray files survive.
  - On a name collision the comic is not written and the colliding file is untouched.
  - A corrupt backup copy plus a refused replace means the backup is **kept**.
  - Junctioned backup folder: only the attempt's own copy is removed.
  - A normal write keeps its chain.
- **`p37b`:** brackets, accents, `&` and 674-character paths all pass.
- **Matrix:** every post-replace or edit kind leaves its backup in place or never made one.

## R3.5 Failure matrix on d3e9723 (69 runs, 23 cases)
- **Isolated** (9/10 written, nothing excluded, retried):
  - viewer open (every share mode, **0 backups**);
  - exclusive lock from the start;
  - leftover tmp;
  - bad CRC page (**0 backups**);
  - viewer plus corrupt backup (backup **kept**);
  - backup copy fails from a full disk (a **partial file remains**, Q4-3).
- **Skipped, nothing excluded:**
  - archive changed after planning;
  - a planned field edited elsewhere (no backup);
  - touched during backup or temp (**backup kept**).
- **Carve-out, identical to 7dcfe0e** (`needs_attention`, 9/5/0 stranded at first/middle/last, backup kept):
  - exclusive lock after the planning check;
  - read-back mismatch or unreadable;
  - backup corrupt;
  - catalog locked after replace;
  - file vanished;
  - another program's edits.
- **Unchanged:** an edit in the microseconds before replace is lost (Q4-5).

## R3.6 F21, F24, F27, earlier probes
- F21, F24 and F27 hold. `p30` 24/24. Source switches identical.
- End-to-end: `e2e1` 20/20, `e2e2` 26/26, `e2e6` 12/12, `e2e7` 8/8 (publisher on).
- Earlier probes `p1`–`p15e` pass. `p12` is 84/85 and `p11` 3/4, with the same stale lines as Round 1.
- `save_one` takes about 5 ms per call on both builds.

## R3.7 Findings (current state)
| ID | Sev | Finding | Status |
|---|---|---|---|
| Q3-1 | Major (R1) | One failed write strands the plan | **Closed** for routine failures |
| Q4-1 | Minor (Major only if another tagger edits these folders during a pass) | The carve-out is wider than its reason. A stopped ticket keeps its never-attempted entries out of discovery, with no resume | Open, Ender |
| Q4-2 | Major in 7dcfe0e | Endless daily retries with a backup each | **Closed by F29** |
| Q4-3 | Minor | A backup copy that fails partway (disk full) leaves a partial file per attempt (≤5 per comic). A skipped comic keeps its backup, with no cap | Open |
| Q4-4 | Minor | The stop is silent and sticky. `write_failed` is not on the dashboard, and the live line says "No manual review is required" | Open, Judy spec |
| Q4-5 | Note | Edit in the microseconds before replace is lost (pre-existing) | Note |
| Q4-6 | Note | Reparse check follows a junction. Cleanup removes only the attempt's own copy, and the junction target is intact | Note |
| Q3-2 to Q3-10 | unchanged | `in_book.py` is not in the diff since f677193 | as Round 1 |

## R3.8 Pattern alerts
- **P-3 (update):** each fix closed the sibling that review found. Q4-1 and Q4-3 remain. Proposed: accept the residual carve-out, and keep `m_matrix.py` and `m_loop2.py` as the seed for a unit failure matrix.
- **P-4 (new):** failure states are invisible to Sergei. Holds, dead links and write failures are saved in `detail` but not shown. Proposed: a Judy UX spec ("Not written (n)" with the reason).

## R3.9 Not tested
- Real YACReader, Bitdefender and indexer locking (simulated).
- The five-failure stop in the real app (tested in-process with a simulated clock).
- The catalog's 30 s lock timeout against a 40k-comic scan.
- Filename probes that need the live-catalog snapshot (`in_book.py` is unchanged in this delta).
- Live queue, real providers, credits tier (off).

## R3.10 Disk hygiene
Removed through a frozen plan (`futaba_cmo_r3_plan_a.json`, SHA256 `d71427d5…eef`): 9 pinned archive copies, 1,065 files, 38 dirs, 11,181,561 logical bytes; verify complete. Kept for the morning: the synthetic `futaba_v013\e2e_r2` (256 MB) and `state_r2` (19 MB), plus probes and logs as evidence.

**What would void this verdict:** any code change after d3e9723 other than a version-and-changelog-only commit.

**Verdict:** GO
