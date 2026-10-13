# Code Review — Comics Meta Organizer v0.1.4

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-13
Tool: Comics Meta Organizer
Release: v0.1.4
Commit range: 1c34df251749aed9703f9689fe119a995a4f77fe..eb64759cba3d4563650b6b157a69fac90c8353c8
  (one commit, eb64759; 35 files, +3,999 / -191)
  code 15 files +1,100 / -130; tests 12 files +1,896 / -35; docs 7 files +955 / -15; dashboard 1 file +48 / -11
Worktree / branch: WIP/Comics Meta Organizer-v014, feat/v0.1.4-in-book-rules (clean tree at review time)
Stand-down dimensions: none. Electron checks do not apply (Python service + local web dashboard)
```

Predecessor: the v0.1.3 review (Round 3) certified `31798b6..d3e9723`. `1c34df2` is Sully's v0.1.3 release commit on top of it, so this range follows on directly.

`VERSION` still reads `0.1.3` and `CHANGELOG.md` has no 0.1.4 entry. This clearance covers `eb64759` plus Sully's version/changelog-only bump commit. Any other code or test change needs a fresh look.

## Summary

The commit implements Sergei's seven decisions of 2026-10-13:

- **Write ledger and in-book replacement.** New `write_ledger` table, written with each history row. New `provenance.py`. A verified external source may now replace a value the in-book tiers wrote.
- **Publisher agreement.** Publisher only when the cover and credits readings agree. On by default; the credits pages are read once per eligible comic.
- **Imprints.** Imprint is split out through an explicit table (`imprints.py`), including the manual ComicVine preview and apply.
- **Filename number.** A numbered file whose cover number is unread takes its Number from the filename (`in-book:filename-number`), behind a classifier.
- **Series spelling fixes.**
- **Failure filters.** `problems.py`, `/api/try-again` and the dashboard's chips and reasons.
- **Lens.** Searching resumes 5 minutes after a solved Google check.

**Verdict in short: no Critical, no Major, nothing on the safety floor.**

- **Ledger.** I found no path by which a value Sergei or another program wrote, or a manual dashboard write, can be replaced. The chain, the v0.1.3 backfill and the F22 guard all held under probes (focus answer 1).
- **v0.1.2 and v0.1.3 safety.** The earlier probes give identical write behaviour on `1c34df2` and `eb64759`.
- **Seven new Minors (F32 to F38).** Three of them want Sergei's attention:
  - **F36.** 1.3 MB of pilot data, with about 400 full library paths, is committed to a **public** repository and already pushed.
  - **F34.** A Series that differs only in letter case counts as a disagreement and replaces the in-book value.
  - **F33.** The imprint table ignores dates: WildStorm and Archaia map to the wrong parent for older books.

## Focus-area answers (brief questions)

### 1. Write ledger and in-book replacement

**Can a human edit, another tool's write, or a manual dashboard write be replaced? No, in every case I could construct.**

| Case | Result | Evidence |
|---|---|---|
| Sergei or another tool saves the archive (new size or mtime) | The chain breaks at the newest link; nothing older is replaceable | Ender's tests; `chain()` stops when a write's output signature differs from the next one's input |
| Another program rewrites the in-book field at the **same size and mtime** (catalog row stays stale) | Replacement is planned from the stale value. The F22 ComicInfo guard then refuses it ("ComicInfo changed since planning (Series)"). Sergei's value is kept and no history row is added | Probe Q2 |
| A v0.1.3 dashboard write (no batch folder, so no ledger row after backfill) on top of a v0.1.3 in-book write | The chain is empty and nothing is replaceable. Metron fills only Year and Publisher | Probe Q1 |
| A v0.1.4 dashboard write (`writer='manual'`, default) | `in_book_values` stops at the manual link, so every older in-book value counts as Sergei's | Ender's test; code (`app.py:440`, `:769`) |
| A reviewed reference batch (`batch.py prepare`) | Recorded as `manual` | Ender's test; backfill uses the same rule |
| A source replaces the in-book Series, then a second source disagrees again | No flip-flop. The replaced value's source is `replaced-in-book:<provider>`, so it is never in-book again; the second source only fills Title | Probe Q3 |
| An imprint versus its parent (Metron "Skybound" against in-book "Image Comics") | No replacement; Imprint is filled instead | Ender's test; `provenance.disagrees` uses `imprints.publisher_key` |

- **Ledger integrity.**
  - The ledger row is inserted in the same transaction as the history row and the catalog update (`app.py:540-548`).
  - Its input signature is the one `write_metadata` checked against the row at entry. Its output signature is the stat after `os.replace`.
  - A write that fails after the replace adds neither row, so the next scan breaks the chain. This is fail-safe.
  - Only two callers exist: `batch.apply` (automatic unless a reference plan) and `/api/apply` (manual). `writer` is never read from the request.
- **v0.1.3 backfill (live snapshot, scratchpad copy).**
  - **Matched.** 6,490 batch folders and 6,667 results gave 6,594 ledger rows, in 3.1 s.
  - **Unmatched.** 73 older results carry no `output_signature`, so they are correctly left out.
  - **Replaceable after the backfill.** 174 comics (Series 173, Number 140), exactly the 174 in-book writes v0.1.3 has made. 55 comics with history have no chain (changed since the app wrote them).
  - **Re-runs.** INSERT OR IGNORE and the marker make it idempotent. A failure leaves no marker and retries at the next process start; until then nothing is replaceable.
- **Chain check against the current file.** `chain()` starts from the catalog row's `[size, mtime]`. Where the row is stale (an edit that keeps size and mtime), the F22 `expected` check at write time is the real guard. Q2 shows it holds.
- **Race with F22.** Replacements carry the in-book value as `before`. Ender's mid-pass test and Q2 cover both windows: an edit after the scan, and an edit that keeps the signature.
- **Conflict and hold rules.**
  - **Conflict or hold.** `allow_replace` is false on the publisher-catalog and web paths. The ComicVine path passes `True`, but it is reachable only when the fresh issue's identity matches, so conflict, hold and dead ID are all false there.
  - **Dead ID.** It allows replacements from strictly verified sources, as documented.
  - **Probes.** Ender's conflict and hold tests pass, and the ten identity probes are unchanged (answer 7).

### 2. Publisher agreement and imprint split

- **A failed read is never agreement.**
  - **Exception.** `read_credits_for_publisher` catches any read error, saves `credits_reading_error` for the signature, and returns no reading. `publisher_agreement` needs a dict on both sides.
  - **Blank reading.** An empty reading names no publisher.
  - **No pages.** A comic with fewer than 3 pages returns `None` without using the GPU and is re-checked cheaply on later passes.
  - **Pin risk.** `ready()` does not ask for a credits read, so nothing pins a folder.
- **Fabricated indicia.** The code does not detect them; the veto does. Futaba's pilot:
  - 9 fabricated readings, all of them disagreeing with a correct cover reading, so nothing was written;
  - 1 wrong agreement of 165 (Kroma, the imprint case, now handled by the split).
  - The independence of the two readings is the stated assumption. Pages 2-5 can hold variant covers or house ads of the same publisher, so some agreements are "two reads of a logo" rather than cover plus indicia. The pilot measured precision with that included.
- **Parent mapping.** F33: WildStorm maps to DC Comics, and Archaia to BOOM! Studios, regardless of year. I found no date problem in the other entries.
- **Flip-flop between sources.** None (answer 1, Q3).
- **Manual ComicVine apply.** Preview and apply split the same way. Apply re-fetches from ComicVine and never trusts browser fields. It fills empty fields only, so a Publisher Sergei typed stays and only an empty Imprint is added.

### 3. Filename-number rule: classifier false positives

**Measured with embedded ComicInfo as ground truth.** I blanked the fields and re-judged every comic that has an embedded Number and a current cover reading.

- **Agreement.** The filename-number route fired on 539 comics, and Number agreed on 526.
- **The 13 differences. None is a wrong issue number.**
  - **Formatting.** 2 are embedded "04 (of 08)" text.
  - **Numbering convention.** 10 are a convention difference: the file is named "Life Is Strange - Settling Dust 001" and the embedded value is "Life is Strange #4.1". Under the filename-series convention Sergei chose, the write is right.
  - **ComicVine-linked.** 1 (`Lady Death 01 (1994)`, embedded #2) has a ComicVine Web, so the identity rule blocks it anyway.
- **Projection on the live snapshot.**
  - **Volume.** 2,352 filename-number writes, beside 8,048 cover-route writes.
  - **Hand review.** I read 80 of the 210 writes with suspicious names, 40 of the 60 with three-digit or zero numbers, a random 70, and all 102 whose cover text holds a number other than the filename's. Apart from the two cases below, each such number was a date, a price, a two-digit year, a subtitle or a title number ("13 Coins", "Hex11").
  - **Collection tag.** One `(GN)` in brackets passes the collection check, because that check reads series words only: `Elektra Lives Again 01 (1996) (GN)` gets Number 1.
- **Residual class (not a finding).** "MONTH NN" is read as a date, so a cover printing "MAY 15" counts as unread. A misnamed file would then take its wrong filename number, where v0.1.3 wrote nothing. Two projected writes show a month followed by a one- or two-digit number that is neither a plausible year nor a price and differs from the filename. I could not verify either without opening the archives: `Unusual Tales 023`, cover "APR 19"; `House of Mystery #38`, cover "June 17".

### 4. Failure filters and Try again

- **CSRF and Origin.** `/api/try-again` sits behind the existing `do_POST` guard. Probe results:
  - Missing, foreign, `null` and `localhost` Origins, and a rebinding Host, all got 403 with the record unchanged.
  - The correct Origin cleared the stop.
  - Non-integer and unknown IDs got 400.
- **Wrong comic.**
  - **The stop it clears.** `try_again` acts only on the record at that comic's catalog path. It requires the code `write_stopped` at the current signature, inside `BEGIN IMMEDIATE`.
  - **One attempt.** The count is kept, so one more failure stops it again. Each attempt removes its own backup (F29 path).
  - **Live scope.** It does not check that the comic is in the live library, unlike `open-folder`. That is harmless: a comic outside the live library is never processed.
- **Categories.** One reason per comic, by precedence, and only while the record's signature matches the file. `held` and `write_stopped` use the processing code's own predicates. Live snapshot: 49 conflicts and nothing else. The v0.1.3 conflict records lack `conflict_file` and show the fallback sentence until their next pass.
- **XSS.** None. Every reason, the last error, ComicVine series names and the chip counts are set through `textContent`, `createTextNode` or attributes. `index.html` has no `innerHTML`. The page never renders free-text `detail`.
- **Cost.** F37: the counts query runs at every 2-second snapshot refresh.

### 5. Lens solved-check resume

**No loop, no spam, no cap bypass.**

- **Only a real solve shortens the hold.** `solved_hold` runs only on a successful verification, and `service` refuses unless a human check is pending (`lens_verification.py:182`).
- **It only shortens.** The hold becomes at most 5, 10, 20, 40, then 60 minutes per solve within 2 hours of the last one, and is never longer than the hold already running.
- **The daily cap is untouched.** It is enforced by `search.reserve` per search, outside `browser_retry_at`.
- **Worker wake-up.** `after_solve` can only bring the next search forward to the shortened hold. A solve without a running hold makes at most one immediate claim, and the cap or cooldown check still applies to it.

### 6. `provider_wait.py` and `source_scheduling.py`

- **`cause`.** An optional, whitelisted fourth argument. Every other `ProviderDeferred` call site is unchanged.
- **`useful()`.** It now counts an Imprint split or a replaceable disagreement as new data. That makes such a source "verified" (next try in a day) instead of backing off, until the write lands. After the write the value is no longer replaceable, so this is bounded.
- **Hold record.** It gains `next_try_at` and `cause`. The F18 hold arithmetic is unchanged (answer 7, hold-loop rows).

### 7. Regression against v0.1.2 and v0.1.3 safety

All probes ran on `git archive` exports of `1c34df2` and `eb64759`, with every source mocked.

| Probe | 1c34df2 → eb64759 |
|---|---|
| Ten v0.1.2 identity probes (`conflict_pass2`, `_provider`, `_summary`, `identity`, `r3_creators`, `r3_outage`, `r4_hold`, `r5_api`, `r5_deadid`, `verify_e2e`) | Same plans and outcomes. The only text changes are by design: the missing-key wording, and the new conflict `detail` sentence on dead-ID conflicts |
| F18 hold loop as passes / ComicVine requests / local reads (8 comics 6 h; 40 comics 6 h; revoked 24 h; missing key 24 h; budget) | Identical: 74/32/8; 394/64/40; 218/104/8; 16/8/8; 16/8/8 |
| `probe_v013` P1 (F23), P2 (F22), P3 (F25) | Identical. P3 still pins its folder (F25 open) |
| `probe_r2` T1-T9 (F22 guards, F23/F29 classification) | Identical (skips, classification, failed-write backups) |
| `probe_r3` T7L, R2-R9 (F29 cleanup, retry cap, F30, F31) | Identical (backoff 1/2/4/7 days, stop after 5, 0 backups left; F30 and F31 still reproduce) |
| `probe_f18_error` error / control | Identical: 1.4 / 1.4 passes per comic per outage hour |

## Ender's open decisions

1. **Fix `app.parse_name` globally ("0.5" → ".5")? Yes.**
   - **Why.** `row['number']` feeds external identity: `research.query_identity` and the Metron lookup. `research.issue_number(".5")` is `"5"`, so the 22 live half-issue files are searched as issue 5. Today only cover agreement stands in the way of a wrong match (F35).
   - **How.** Keep one zero before a decimal point in `parse_name`. Then refresh the 22 existing rows, which a scan only updates when the file changes: either rescan them once, or make `issue_number` read a leading "." as "0.".
   - **Afterwards.** The local patch in `in_book.filename_parts` (`in_book.py:98`) becomes a no-op and can go.
2. **Drop the last-page slot from credits reads? Not unconditionally, and not in this release.**
   - **The precision was measured with that slot.** 164 of 165 agreed in the pilot.
   - **The data does not single it out.** Scan-tag last pages occur in 68% of archives, and 6 of the 9 fabricated readings had one, which is the same rate.
   - **Most of the extra text is safe.** A second publisher vetoes.
   - **If the time matters.** Skip the last page only when it sorts as a scan-tag file (`z…` after the numbered run), and re-run the pilot's 339-comic census before shipping the change.
3. **The 7 px sideways scroll at 320 px.** Not a construction issue. Nothing is covered or unreachable, and a 320 px window is unlikely for a desktop dashboard. Log it for Judy; it does not block. Not verified in a browser (the DOM tests need the CDP fixture).

## Rubric

Severity tags and the always-blocking safety floor: `Team/Docs/ProcessRules.md` § Severity definitions.

### 1. Security

- Status: Pass.
  - **No shell-outs or deletes.** The range adds no shell-out and no file delete.
  - **New POST route.** It is behind the existing Origin and Host guard (answer 4).
  - **XSS.** No injection path in the new dashboard code.
  - **SQL.** Statements are parameterized, and the status filter is whitelisted (`problems.CODES`).
  - **Secrets.** None in the diff. No attribution trailer.
  - **Privacy.** F36 is a privacy and hygiene item, not a credential leak (dimension 9).

### 2. Correctness & Logic

- Status: Concerns
- Findings:
  - F32 [Minor] `in_book.py:307`, `:309`, `:313-327`, `:397-398`. Some "obvious" Series fixes are wrong.
    - **Title punctuation stripped.** Trailing separators are trimmed even when they belong to the title. Snapshot: "Hunt. Kill. Repeat." loses its final dot (cover: "Hunt. Kill. Repeat."). "Aliens - What If..." and "Terry Moore After Dark..." lose their ellipsis.
    - **Accent from one misreading.** Accents come from one model transcription: "Minor Arcana" becomes "Minor Arcanà", almost certainly a misread stylised logo.
    - **Apostrophe rule too broad.** `_t`, `_d` and `_m` after any letter become apostrophes. "Mr_T and the T-Force" becomes "Mr'T and the T-Force" (probe Q7; no such file in this library).
    - **Scale.** About 7 of the 62 projected fixes are wrong. The values are in-book, so an external source can still replace them.
    - **Fix.**
      - Trim only separators that stand apart (" -", "_", ","), and keep "...", "…" and a final "." when the cover title ends the same way.
      - Take an accent only when the credits/indicia reading spells the title the same way, or drop the accent fix (4 of the 62 projected fixes; 1 wrong).
      - Limit the apostrophe rule to `_s`, `n_t`, `_ll`, `_re`, `_ve`.
  - F33 [Minor] `imprints.py:19`, `:22`; `provenance.py:120-122`. The imprint table ignores dates.
    - **Wrong parent for older books.** WildStorm books of 1992-1998 were published by Image, and Archaia was independent until 2013. The table maps them to DC Comics and BOOM! Studios whatever the year.
    - **Can replace an agreement.** A source naming either fills an empty Publisher with the wrong parent. `disagrees('Publisher', 'Image Comics', 'WildStorm')` is True (probe Q4), so a 1990s WildStorm book's in-book "Image Comics", from the cover and indicia agreeing, would be replaced by "DC Comics".
    - **Live exposure.** 0 WildStorm in embedded or verified evidence. 13 embedded Archaia, 3 dated before 2013.
    - **Fix.** Bound both entries by year (WildStorm → Image before 1999; Archaia unmapped before mid-2013), or drop them.
  - F34 [Minor] `provenance.py:131`. Any Series text difference counts as disagreement, including case only.
    - **Probe Q5.** A source returning "AMAZING SPIDER-MAN" replaced "Amazing Spider-Man" and rewrote the archive.
    - **Documented in part.** The README covers punctuation-only replacement, not casing.
    - **Fix.** Sergei's call. Either treat case-only (and dash-versus-colon) differences as agreement, or accept the source's casing.
  - F35 [Minor, pre-existing] `app.py:126`; `research.py:85`, `:104-110`. `parse_name` turns "0.5" into ".5", and `issue_number(".5")` is "5".
    - **Exposure.** 22 live half-issue files are searched as issue 5 by Metron and the other sources.
    - **What prevents a wrong write.** Only cover agreement. 0 wrong writes so far: none of the 22 has an embedded Number.
    - **Ender's question.** See open decision 1.

### 3. Crash / Stability Safety

- Status: Pass.
  - **Ledger reads.** `provenance` tolerates malformed ledger `fields` (it breaks the chain).
  - **Backfill.** It skips unreadable batch folders, and any other exception leaves the marker unset.
  - **Dashboard counts.** `problems` counts are best-effort in the snapshot.
  - **Credits reads.** A failure is recorded and never repeated for the same pages.
  - **Live snapshot.** `identify`, `in_book_values`, `needs_credits_for_publisher` and the classifier ran over all 40,029 rows without an exception.

### 4. Performance

- Status: Concerns
- Findings:
  - F37 [Minor] `problems.py:75-100`, `progress_snapshot.py:58`, `app.py:633-645`. The problem counts scan every discovery record each time.
    - **Measured.** Every progress snapshot refresh (every 2 s while the dashboard is open) and every problem-filtered list request runs `json_extract` over all ~40,000 discovery records. 0.17-0.2 s each on the live snapshot.
    - **Fix.** Cache the counts per snapshot key, or keep a small indexed problem column written by `save_one` and `write_not_done`.
  - F38 [Minor] `local_model.py:26-27`, `:145-152`. Credits reads have no output cap (Futaba's pilot finding 3), and that matters now that publisher agreement is on by default.
    - **Projected volume.** About 3,590 comics get one credits read, about 2.7 h of GPU, once.
    - **Wasted time.** At the pilot's 2% runaway rate, about 70 reads run about 37 s and then fail.
    - **Fix.** Set `num_predict` (for example 1,024) for this prompt.
  - **No issue found.**
    - **Ledger lookups.** `in_book.ready` over the 5,353 written comics took 1.1 s (0.2 ms each, 417 short-lived connections).
    - **Backfill.** 3.1 s, once.

### 5. State & Data Safety

- Status: Pass.
  - **No new loss path.** The write chain (backup, temporary-archive checks, read-back, SHA-256) is unchanged, and the ledger rides in its transaction.
  - **Protection.** Every replacement goes through the F22 signature and ComicInfo guards (answer 1).
  - **Rollback.** v0.1.3 ignores the new table and index. Writes made during a rollback get no ledger row, so their values are never treated as in-book (fail-safe).
  - **M1 note.** If M1's state split lands before this backfill runs, `STATE_ROOT/batches` will not hold the v0.1.3 folders. The backfill then records 0 rows and marks itself done. That is safe, but the 174 values would never become replaceable. Merge order, not a defect.

### 6. Input Handling

- Status: Pass.
  - **Request input.** Try-again IDs are parsed with `int()`; bad input gets 400.
  - **Regexes.** The new ones (`COVER_DATE_TEXT`, `OTHER_NUMBERING_TEXT`, `COVER_ISSUE_MARK`, `TITLE_GROUP`, the trailing-group pattern) are linear on filenames and model strings. No catastrophic backtracking found.
  - **Reading types.** Non-string `issue` and `title` values and odd types return `unclear` or `unread`.

### 7. Maintainability

- Status: Pass.
  - **Structure.** `provenance.py`, `imprints.py` and `problems.py` are small, documented modules. Ender's tests mirror each decision and include positive controls.
  - **Dead code.** `in_book.cover_number_unread` (`in_book.py:222`) has no caller.

### 8. Doc/Code Drift

- Status: Concerns
- Findings:
  - **Brief row "Publisher agreement (v0.1.4)" contradicts itself** (`Docs/ComicsMetaOrganizer_Brief.md:40`). It says both "off until the read-only pilot passes" and "On by default since Sergei's decision". The code is on by default. Logged under F28 (no new number).
  - **The pilot report says its result files were "kept, not copied into this worktree"** (`Docs/ComicsMetaOrganizer_CreditsPilot_2026-10-13.md:208`). They are committed (F36).
  - **F28 carried.** `README.md:41` (reading-order prefix), `README.md:67` and Brief `:54` ("later held passes only ask ComicVine") are unchanged.
  - **Accurate.** The new README and SOURCE_CONNECTORS text on replacement, the ledger, imprints, failure filters and Lens matches the code.

### 9. Build & Release Hygiene

- Status: Concerns
- Findings:
  - F36 [Minor] `Docs/ComicsMetaOrganizer_CreditsPilot_2026-10-13_runA.jsonl` (321 KB) and `_runB.jsonl` (1.0 MB). Pilot data is committed to a public repository.
    - **What they hold.** 403 per-comic records: full library paths with scan-group tags, Metron truth, and the raw transcribed indicia and credits text.
    - **Where.** Committed to `Gemanoneko/Comics_Meta`, which GitHub reports as **PUBLIC**. The branch is already on `origin`.
    - **Severity.** Not a credential, so not on the safety floor. It does publish a listing of Sergei's library, and it is generated data in `Docs/`.
    - **Sergei decides.**
      - Keep the files.
      - Or remove them in a follow-up commit, so they never reach `main`'s tree.
      - Removing them from the pushed history needs a rewrite of that branch, which only Sergei can authorize.
  - **Suite.** On an isolated export of `eb64759`: 665 tests, OK, 47 skipped (`python -B -m unittest discover -s tests`, 102 s). The export was left clean.
    - **Skips.** All 47 are DOM tests that need the `COMICS_TEST_CDP` headless fixture: 12 failure-filter, 14 verification, 14 Yandex, 7 free-search. So the 12 new dashboard tests were not exercised here.
    - **Range.** v0.1.3 ended at 566 tests and 33 skipped.
  - **Existing tests.** Assertions changed only where Sergei's decisions changed behaviour: publisher, Year from credits, unread numbers, the Lens hold and the dead-ID conflict detail. Every identity assertion (ComicVine Web, conflict, hold) is kept.
  - **Repository.** No secrets. No attribution trailer.
  - **Version.** `VERSION` and `CHANGELOG` move in Sully's bump commit.

---

## Earlier findings at eb64759

| # | v0.1.3 Round 3 | Now | Evidence |
|---|---|---|---|
| F20 | Minor | Closed. The dashboard shows hold, dead-link, conflict and failed-write reasons, counts and Try again from structured fields. Behaviour is Futaba's to confirm | Answer 4; Ender's DOM tests (not run here: CDP fixture) |
| F21 | Closed as a default; product question open | Closed. Sergei chose two-reading agreement, and an external source can now replace a wrong in-book value | Pilot; answer 2 |
| F26 | Minor | Narrowed. Underscored apostrophes are fixed, and prefixes stay by Sergei's decision. The cover route still writes `Yucatan 1512` as Number 1512 (the 4-digit guard covers only the filename route). Stickiness is now mitigated by replacement. New string issues are filed as F32 | Blank-and-judge |
| F25 | Minor | Unchanged | `probe_v013` P3 still pins the folder |
| F27, F28 | Minor | Unchanged; F28 gains the Brief contradiction above | — |
| F30, F31, F11-F15, F19 | Minor | Unchanged (outside this range) | — |

## Patterns

Third release running: the write chain held in every probe, and the residual risk sits in how much one model reading may decide.

v0.1.4 answers that at the right layer:

- Two readings must agree for Publisher.
- A ledger lets a better source correct the model later.
- The F22 guard re-checks at the last moment.

The new Minors are string- and table-level (F32, F33, F34). They are cheap now, because in-book values are no longer final.

One process pattern is new: generated pilot data reached a public repository (F36).

---

## Verdict

- Total Critical: 0
- Total Major: 0
- Total Minor: 7 new (F32-F38), plus carried F25, F26 (narrowed), F27, F28, F30, F31, F11, F12, F13, F14, F15, F19
- Closed this range: F20, F21
- Safety-floor violations in `1c34df2..eb64759`: 0

**Verdict:** RELEASE CLEAR

This clearance covers `1c34df2..eb64759` plus Sully's version/changelog-only bump commit. Any other code or test change needs a fresh look.

**Nothing has to land before deploy.**

**For Sergei (not blocking):**

- **F36.** Public pilot data. Keep it, or remove it from the branch before it reaches `main`.
- **F34.** Should a case-only or punctuation-only Series difference replace an in-book value?
- **F33.** Bound WildStorm and Archaia by date, or drop them from the table.

Futaba's behaviour verdict is separate.

| # | Sev | Dim | file:line | Finding | Next-cycle action |
|---|-----|-----|-----------|---------|-------------------|
| F32 | Minor | 2 Correctness | `in_book.py:307`, `:309`, `:313-327`, `:397-398` | Series "fixes" strip real title punctuation, add an accent from one misreading, and over-match `_t`/`_d`/`_m` (about 7 of 62 projected) | Narrow the trim, accent and apostrophe rules |
| F33 | Minor | 2 Correctness | `imprints.py:19`, `:22`; `provenance.py:120-122` | WildStorm and Archaia map to the wrong parent for older books; can replace an in-book "Image Comics" | Year-bound or drop both entries |
| F34 | Minor | 2 Correctness | `provenance.py:131` | Case-only Series differences count as disagreement and rewrite the archive (Q5) | Sergei's call; compare casefolded |
| F35 | Minor | 2 Correctness (pre-existing) | `app.py:126`; `research.py:85`, `:104-110` | "0.5" parsed as ".5", which reads as issue 5; 22 live files | Fix `parse_name` globally and refresh the 22 rows |
| F36 | Minor | 9 Hygiene | `Docs/…CreditsPilot_2026-10-13_runA.jsonl`, `_runB.jsonl` | 1.3 MB of pilot data with library paths in a public repository, already pushed | Sergei decides keep or remove |
| F37 | Minor | 4 Performance | `problems.py:75-100`; `progress_snapshot.py:58` | Problem counts scan all discovery records every 2 s (0.2 s) | Cache per snapshot or index a problem column |
| F38 | Minor | 4 Performance | `local_model.py:26-27`, `:145-152` | No output cap on credits reads; about 70 runaway reads of about 37 s across the default-on publisher pass | Set `num_predict` |
| F25-F28, F30, F31, F11-F15, F19 | Minor | — | as in v0.1.3 | Unchanged (F26 narrowed, F28 extended) | As before |

## Method and limits

- **Read:**
  - the whole diff;
  - `provenance.py`, `imprints.py` and `problems.py` in full;
  - `app.write_metadata`, `remove_verified_backup`, `do_POST`, `/api/comics`, `parse_name` and `filesystem_path`;
  - `batch.apply` and `prepare`;
  - `automatic.discover` (replacement sites, hold and conflict records), `PassPlan` and `held_before`;
  - `in_book`: identity rules, `filename_parts`, `cover_identity`, `judge`, `identify`, `ready`, `reading_applies` and the classifier;
  - `coverage_priority.lookup_flags`, `order_rows` and `firstpass_folder`;
  - `discovery_state`;
  - `lens_verification.service` and `solved_hold`, `browser_worker.lens_attempt` and the main loop;
  - `local_model.read_credits`;
  - the dashboard script.
- **Exports:** `git archive` of `eb64759` and `1c34df2` in the session scratchpad (`senua_v014/exp_*`), run with `-B`. Nothing ran in the worktree.
- **Live snapshot (read-only):**
  - **Copied.** The catalog, through the SQLite backup API over a `mode=ro` connection, plus `batches/` and `data/research/`, all into the scratchpad. The backfill ran only on that copy.
  - **Not touched.** The service, the queue, the library archives and the main checkout.
- **Probes** (`senua_v014/probes/`):
  - `proj014.py`: backfill, chain, replaceable values, projected writes and classifier states.
  - `blank_judge014.py`: the filename-number route against embedded truth.
  - `probe_v014.py`, Q1-Q7: the ledger cases, flip-flop, imprint dates, case-only replacement, classifier strings and Series fixes.
  - `probe_tryagain.py`: Origin variants and bad IDs.
  - `problems_time.py`, `ready_time.py`, `imprint_count.py`.
  - The v0.1.2 and v0.1.3 probes, rerun on both exports.
- **Not run:**
  - the service, any browser (the DOM tests need the CDP fixture), any public request, Ollama;
  - a fresh credits read, so the publisher figures come from Futaba's pilot.
- **Not verified:**
  - the covers of the two "MONTH NN" cases (answer 3);
  - the cause of the 7 px scroll.
