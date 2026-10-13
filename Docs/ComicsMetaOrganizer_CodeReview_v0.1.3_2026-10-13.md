# Code Review — Comics Meta Organizer v0.1.3

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-13
Tool: Comics Meta Organizer
Release: v0.1.3
Commit range: 31798b6..f6771933e757229b43c5bbb93211b598b9f7d065
  (one commit, f677193; 38 files, +2,732 / -125; 18 test files, +1,605 / -11)
Worktree / branch: WIP/Comics Meta Organizer-v013, feat/v0.1.3-throughput (clean tree at review time)
Stand-down dimensions: none. Electron checks do not apply (Python service + local web dashboard)
```

Predecessor: the v0.1.2 review (rounds 1-5) certified `cb0ee14..a73f43e`. `31798b6` is Sully's v0.1.2 release commit on top of it, so this range follows on directly.

`VERSION` still reads `0.1.2` and `CHANGELOG.md` has no 0.1.3 entry. This clearance covers `f677193` plus Sully's version/changelog-only bump commit. Any other code or test change needs a fresh look.

**Round 3 (at the end of this report) reviews `7dcfe0e..d3e9723` and carries the current verdict.** Rounds 1 and 2 are kept as history; their verdicts are superseded.

## Summary

The single commit does eleven things. The ones that matter most for safety:

- **In-book cover tier (new, on by default).** A saved local-model cover reading writes Series and Number when its title and issue number agree with the filename. An unnumbered file gets Series only. A canonical publisher is added from the reading's `publisher` field.
- **Multi-comic pass plans.** One plan and one queue ticket per folder pass, up to 50 comics. A comic changed since planning is skipped; the rest are written.
- **Metron before ComicVine.** ComicVine is now asked only by an embedded Web issue ID, as the identity check.
- **F18 hold backoff.** Held comics retry after 5, 10, 20 and 40 minutes, then hourly. Repeat held passes skip local work. ComicVine answering wakes them.
- **Smaller changes.** Fast catalog probe (temp table + `comics_path_nocase` index), ticket cache, Yandex removal, `sources.disabled` switches, a capped progress payload, a 6-hour library walk, and the credits/indicia tier (built, off) with a read-only pilot.

**Verdict in short:** no Critical, nothing on the safety floor. The v0.1.2 identity rules hold: conflict, hold and dead-ID comics get no in-book write, and the earlier probes give identical write behaviour. Three new Majors:

- **F21. Publisher from the cover reading is wrong about 4-5% of the time.** Measured on the live snapshot. A wrong value is sticky, because later sources fill only empty fields.
- **F22. An edit Sergei makes during a pass can be overwritten, and the backup is then deleted.** Probe-verified. Pre-existing, but the window is now the whole pass.
- **F23. One failing archive now strands up to 49 other comics in its plan, with no recovery path.** Probe-verified.

F18 is closed for its reported cause. Its residual is F24 (Minor).

## Focus-area answers (brief questions)

### 1. In-book tier

**Can a wrong Series/Number/Publisher be written?**

- **Number: very rarely.** The filename number must equal the cover number (`in_book.py:169`).
  - **Measured.** Embedded ComicInfo values serve as ground truth: I blanked them and re-judged 2,579 comics that have a current cover reading. Number agreed in 2,089 of 2,102 cases.
  - **The 13 differences.** 11 are only embedded "(of N)" formatting, and 1 is an embedded error. One is a real wrong write: `Yucatan 1512 (2025)` gets Series "Yucatan", Number 1512. The filename parser and the model both read the title's number as the issue. It is in the library twice. See F26.
  - **Volume and chapter guards.** A volume/book/part word, a `vN` suffix, a digit in a reading-order prefix or chapter name, and a translation tag all block the write (`in_book.py:89-96`, `:133`). The tests and my spot checks agree.
- **Series: correct identity, imperfect string.** Series is always the filename's text, and the cover only corroborates it.
  - **Against embedded truth.** 2,333 of 2,579 agree exactly. Of the 246 differences, 128 are formatting only: a year in parentheses, "&" versus "and", GN/OGN. The other 83 differ in substance. They are mostly a filename prefix the cover does not show: an imprint, event or reading-order label.
  - **The weaker route.** The rule that accepts a cover title found inside a longer filename series differs in substance 29 of 435 times (6.7%). An exact match differs 54 of 2,109 times (2.6%).
  - **Examples.** "Chilling Adventures Presents ... Betty the Final Girl", "Another universe exclusive Star wars", "Assassin_s Creed - Awakening" (an underscore standing for the apostrophe; 27 such Series), and "B.P.R.D. - 1947" next to "B.P.R.D. 1947" in the same series. See F26.
- **Publisher: yes, about 4-5% (F21).** The "canonical name in full" rule checks the model's `publisher` string, not the printed cover. So it stops partial readings, but not wrong ones.
  - **Against embedded truth.** 194 agree and 12 differ. Two of the 12 are only an alias mismatch, which leaves 10 of 206 (4.9%).
  - **Against folder peers.** 543 projected writes can be compared with publishers already embedded in the same folder. 34 disagree; 12 are a BOOM alias, which leaves 22 (4.1%).
  - **Ender's own figure.** 7 of 146 (4.8%).
  - **Clear wrong writes.**
    - `Kill Shakespeare 01 (of 12) [IDW]` gets Dark Horse Comics.
    - `Prometheus in Chains #002` (embedded: Red 5) gets Dark Horse Comics.
    - `Brainworms (AAM-Markosia)` gets Dark Horse Comics.
    - `Second Coming - Only Begotten Son 005` (embedded: AHOY) gets DC Comics.
    - `Shadowman 002 (1999)` gets Dark Horse Comics, and `Shadowman 003` gets Image Comics.
    - `Monster High - Boomuda Triangle` (embedded: IDW) gets BOOM! Studios.
  - **Scale.** The projection plans 2,865 publisher writes, so roughly 115-140 would disagree.
- **Collections / whole-book signal.** An unnumbered file is judged a whole book and gets Series only, on an exact title. That gives 882 projected writes. I found no wrong identity, only the digit-in-title case covered by F26.
- **Translations.** No projected write has a translated filename; the library is English. The tag list differs from `language_eligible` (F25).

**Provenance recorded?** Yes, in four places: the plan entry (`source` plus per-field `evidence`), `history.source = 'in-book:cover'`, appended Notes, and research evidence `in_book`. The small gaps are in F27.

**"Empty fields only" enforced?** At plan time, yes (`in_book.py:171-187`). At write time, `overwrite_fields=set(changes)` trusts the plan. The plan's `old` comes from the scan at pass start, while its digest is taken later. So an edit made between the two is overwritten (F22).

**Identity gate complete?** Yes.

- **Cover tier.** `identity_blocked` runs first in `identify`, so it covers discovery, `ready`, ordering and the coverage probe.
- **What it blocks.** Any Web that names a ComicVine issue (held, dead or conflicting all qualify), plus any recorded `identity_conflict` outcome or saved `conflict_issue`.
- **Same regex as discovery.** It uses the same pattern as `automatic.py:286`, so nothing ComicVine-linked by discovery escapes it.
- **Credits tier.** It adds `not strict` (`automatic.py:442`).
- **Tests.** Ender's positive and negative tests pass.
- **Live snapshot.** 4,415 comics are blocked, and none of the 8,566 projected writes has a ComicVine Web.

### 2. Multi-comic plans (`batch.apply`)

- **Per-comic digest and skip.** These work. A changed comic is skipped with nothing written, `skipped.json` records it, and the next pass re-plans it from its new signature (Ender's test plus reading).
- **Backup, read-back and SHA-256 chain.** Intact per comic:
  - `write_metadata`'s temp-archive checks are unchanged;
  - the read-back compares every planned change;
  - `digest(backup) == entry.sha256`;
  - `remove_verified_backup` is called per entry.
- **`catalog_row`.** It rescans only on a size or mtime mismatch. `write_metadata` re-checks the row against disk, so a stale row cannot write.
- **Partial failure (F23).** Any other per-entry error raises out of `apply`, and the whole ticket becomes `needs_attention`.
  - **Remaining entries stranded.** Entries after the failure are never written. `pending_paths` keeps them out of discovery for good, and nothing in the code requeues a ticket.
  - **Probe P1.** Comic 2 has duplicate ZIP entry names, which the scan does not detect. Comic 3 is then never written and never offered again.
  - **Base rate.** 0 of the live queue's 6,141 tickets ever needed attention. But the in-book tier is about to write about 8,500 archives the app has never written.

### 3. v0.1.2 safety preserved

Yes. I reran ten earlier probes (`senua_r2/probes`) on `31798b6` and `f677193`:

- **Eight give identical output.** `probe_conflict_pass2`, `_provider`, `_summary`, `probe_r3_outage`, `probe_r5_api`, `probe_identity`, `probe_verify_e2e` and `probe_r3_creators`. They cover F10 (conflict on reuse), F16 (conflict during outages), strict verification and dead-ID answer handling.
- **Two differ only as designed.**
  - `probe_r4_hold`: repeat held passes no longer re-check leads.
  - `probe_r5_deadid`: no ComicVine search for comics without a Web ID.
  - Plans, outcomes and writes are unchanged in both.

The key spots Ender named:

- **Metron before ComicVine.** Metron's answer is written only after ComicVine agrees (`automatic.py:471-472`). A conflict or hold sends the outcome to `identity_conflict` or `needs_identity_lookup` before the web-fields write. A dead ID still drops reused evidence.
- **`wait_only`.** It skips every write route as well as the local work. Hold already blocked the publisher plan, Summary and the credits tier; `wait_only` adds nothing that writes.
- **`comicvine_answered_since_hold`.** It needs a real answer: `comicvine_event('available')` is set only on status 1 or 101. It also needs the comic's own wait to have ended.
- **`research.lead_context`.** It includes the strict flag, so a strict rejection never suppresses a later non-strict check. Rejection caching only skips URLs and never accepts one.

### 4. F18 backoff

**Closed for its reported cause.** Probe `probe_r5_holdloop` on `f677193`, with `a73f43e` from round 5 in brackets:

| Scenario | Comic passes | ComicVine requests | Local cover reads and lead re-checks (each) |
|---|---|---|---|
| 8 comics, 6 h outage | 74 (131) | 32 (44) | 8 (123) |
| 40 comics, 6 h outage | 394 (1,315) | 64 (76) | 40 (1,275) |
| 8 comics, revoked key 24 h | 218 (455) | 104 (152) | 8 (447) |
| 8 comics, missing key 24 h | 16 (16) | 8 (8) | 8 (8) |

- **Steady state.** One pass per comic per hour.
- **Wake rule.** It works: all 40 comics recovered in the first hour after the outage ended.
- **Starvation.** None found. The interval caps at one hour and never exceeds the ordinary retry.
- **Residual (F24).** `source_scheduling.due` still makes a held comic due whenever a source entry carried from its first held pass is `error`, or is `unavailable` with its provider now up. `wait_only` passes never re-run that source, so the entry stays past due.
  - **Probe.** `probe_f18_error`: GCD raises once per comic on the first held pass. The result is 5.5 passes per comic per hour, against 1.4 in the control, for the whole outage.
  - **Cost.** These passes are cheap: no local work.

### 5. Fast selection

Safe. Probe `probe_index` ran on a copy of the live catalog snapshot (40,039 comics, 6,195 history rows):

- **Index build.** `CREATE INDEX` took 0.13 s.
- **Same results.** The old and new probe queries returned identical results on 40 consecutive 256-row cursors.
- **Speed.** About 0.06 s per probe for the old query once indexed (7.2 s cold, before the index) and 0.01 s for the new one.
- **Integrity.** `quick_check` passes.

The index is additive and ignored by v0.1.2 on rollback. It is created in autocommit; the temp table locks only `temp`, and WAL readers do not block writers.

### 6. Source switches

**Disabled sources send no requests (code read plus Ender's tests).**

- **The switches.** General free web and Wikipedia/wiki are gated in `free_fallback` and `resolve_leads`, which covers the extlinks request. GetComics and PREVIEWSworld are gated in the source list. Saved-lead re-checks skip only URLs rejected in the same context.
- **No other route.** I found no other automatic call into the disabled sources. `providers.statuses()` only reads local state.
- **Yandex.** It is out of `FREE_ENGINES`, the worker and the API route, and the dashboard row is hidden. What remains (`cancel`/`initialize`/`server_started`, legacy-attempt handling in `source_scheduling`) is local only. Nothing dangles.

### 7. Progress cap and history move

**No data loss.**

- **What moves.** Older batch summaries are appended to `progress-history.jsonl` before `progress.json` is rewritten. A crash in between duplicates history lines and loses nothing.
- **Payload.** The payload cap is display-only, and `completed_revision` is computed over the capped list.
- **First deploy.** About 5,900 of the 6,141 live summaries move on the first v0.1.3 write.

### 8. `pilot_credits.py`

**Read-only for archives, catalog, evidence and queue: yes.**

- **Archives.** It opens them only with `zipfile.ZipFile` reads.
- **Pure parts.** `judge_credits` and `filename_identity` are pure. The module has no import-time side effects (`app`, `research`, `local_model`).
- **Writes.** It writes only `<out>/pilot-credits-<UTC>.json`.
- **GPU.** It skips the pause gate by design, as documented ("run while paused").

## Earlier findings at f677193

| # | v0.1.2 round 5 | Now | Evidence |
|---|---|---|---|
| F18 | Major | Closed for its reported cause; residual is F24 (Minor) | Hold-loop table above; local work runs once per comic |
| F10, F16, F17 | Closed | No regression | 8 of 10 earlier probes identical; 2 differ only as designed |
| F15 | Minor | Narrowed; open | Hold, dead-ID, not-found cache and the `:87` retry text are now documented, and test scratch no longer litters the checkout. The F11-tied lines (`SOURCE_CONNECTORS.md:64,66`, `SYNOPSIS_POLICY.md:8`) remain |
| F11, F12, F13, F14, F19 | Minor | Unchanged (outside this range) | — |
| F20 | Minor | Unchanged; now documented as "not shown yet" | `README.md:62`, `SOURCE_CONNECTORS.md:104` |

## Rubric

Severity tags and the always-blocking safety floor: `Team/Docs/ProcessRules.md` § Severity definitions.

### 1. Security

- Status: Pass.
  - **No shell-outs or deletes.** The range adds no shell-out and no delete beyond the existing verified-backup removal.
  - **New network fetch.** Metron variant covers go through `verified_cover`: https only, `static.metron.cloud`, no redirect, 20 MB cap.
  - **Pilot.** It talks only to localhost Ollama, and its `--out` is a single report file.
  - **Secrets.** None in the diff. No attribution trailer.

### 2. Correctness & Logic

- Status: Concerns
- Findings:
  - F21 [Major] `in_book.py:139-151`, `:182-186`. The in-book Publisher trusts the local model's `publisher` field.
    - **What the rule checks.** "Named in full" checks the model's string, so it stops partial readings ("Dark", "Image"), not invented ones.
    - **Measured disagreement.** 4.9% against embedded publishers, 4.1% against same-folder peers, and 4.8% in Ender's Metron sample.
    - **Hallucinations.** Dark Horse is named for IDW, Red 5, Markosia and Acclaim books.
    - **Why it matters.** The value is sticky: external sources fill only empty fields. Roughly 115-140 of the 2,865 projected publisher writes.
    - **Why Major, not Critical.** It is a wrong value in an empty field, at a rate already in the decision table.
    - **Starting points.** Ender's own decision table already names this: "revisit if Sergei wants path corroboration".
      - Require corroboration: a publisher tag in the filename or folder, or agreement with publishers already embedded in the folder.
      - Or veto on a disagreeing tag or majority.
      - Or switch `in_book.publisher` off until Sergei decides.
  - F25 [Minor] `coverage_priority.py:60`, `:104` versus `automatic.py:268`, `:283`. `in_book.ready` ignores `language_eligible`.
    - **Mechanism.** A comic excluded for language that also has an agreeing reading is made due and ranked first on every pass. It uses one of the 20 checks and is saved `excluded_language` again.
    - **Probe P3.** 22 such comics pin their folder: discovery returns True on every pass, and an ordinary comic in the same folder is never checked.
    - **Live count.** 0 today, so latent.
    - **Second mismatch.** `LANGUAGE_TAG` (`in_book.py:46`) and `language_eligible` (`coverage_priority.py:44`) use different lists. "(it)" is only in the second, and Ukrainian or accented names are in neither.
    - **Fix.** Gate `ready` on the same language check, and share one tag list.
  - F26 [Minor] `in_book.py:78-97`, `:113-136`, `:176-178`. Series is the filename's raw text.
    - **Contamination.** Imprint, event or reading-order words the cover does not show are written into Series: 763 projected writes carry a word prefix. Against embedded truth, the cover-within-filename route differs in substance 6.7% of the time.
    - **Other string problems.**
      - Apostrophes saved as `_` (27 Series).
      - Two spellings within one series ("B.P.R.D. - 1947" / "B.P.R.D. 1947").
      - A number inside a title parsed as the issue (`Yucatan 1512`: Series "Yucatan", Number 1512; the cover reading agreed).
    - **Why it matters.** It is sticky for the same reason as F21.
    - **Starting points.** Write the cover's shorter title, or skip the write, when a word prefix is left over; map `_s` to `'s`; require the cover title to be more than the bare series when the filename number has 4 digits.

### 3. Crash / Stability Safety

- Status: Pass.
  - **Malformed input.** `in_book.judge`, `cover_number`, `cover_publisher` and `ready` tolerate non-string and missing reading fields and bad metadata JSON.
  - **Pause.** A pause mid-pass leaves a valid pending ticket.
  - **Stale data.** A stale catalog row is rescanned before writing.
  - **Live snapshot.** No crash over all 40,029 rows and their evidence.
  - F23's failure mode is fail-closed (dimension 5).

### 4. Performance

- Status: Concerns
- Findings:
  - F24 [Minor] `source_scheduling.py:49-51`, with `automatic.py:292` and `:373-376`. The hold backoff is bypassed by stale source-schedule entries.
    - **Mechanism.** A held comic's first pass may record a source `error`, or an `unavailable` entry whose provider later recovers. Repeat held passes never re-run that source, so `due()` makes the comic due at every folder pass for as long as ComicVine stays down.
    - **Probe.** `probe_f18_error`: 5.5 passes per comic per hour against 1.4.
    - **Why Minor.** The passes are cheap: no local work.
    - **Fix.** On `wait_only` passes, ignore or refresh carried source entries in `due()`, or push their `next_at` to the hold retry.
  - Fast selection: confirmed. On the snapshot the new probe takes 0.01 s and matches the old query.

### 5. State & Data Safety

- Status: Concerns
- Findings:
  - F22 [Major] `automatic.py:234-268`, `:165`, `batch.py:139-140`. A field edited after the pass's folder scan is overwritten, and its backup deleted.
    - **Mechanism.** `old` (which decides "empty") comes from the scan at pass start. The plan digest is taken later, in `PassPlan.add`, from the file as it is then. If another tool writes ComicInfo in between, apply sees a matching digest and writes with `overwrite_fields`. It then verifies the read-back and removes the backup.
    - **Probe P2.** Series "Spawn (Sergei)", written after the scan, became "Spawn"; the ticket completed and no backup was left.
    - **Not new.** The same pattern existed in v0.1.2 for every plan type.
    - **What v0.1.3 changes.** The window now runs to the end of the pass, up to 50 plans and 20 research checks, instead of the first queued comic. Write volume also grows by about 8,500 in-book writes.
    - **Why Major, not Critical.** It needs another program to write ComicInfo into that exact archive during the pass; YACReader does not write archives.
    - **Fix (cheap).** In `PassPlan.add`, refuse the entry when the file's size or mtime differs from the row signature. Or, in `apply`, check that each `changes[k].before` matches the archive before writing.
  - F23 [Major] `batch.py:118-152`, `worker.py:81-85`, `coverage_priority.py:33`. One failing archive strands the rest of its plan.
    - **Mechanism.** Any per-entry error other than a changed digest ends the whole plan as `needs_attention`. That covers duplicate ZIP names, a leftover `.metadata-tmp` and a read-back mismatch. Later entries are never written and stay out of discovery for good. Nothing in the code requeues the ticket, and requeuing by hand fails again at the same entry.
    - **Probe P1.** Confirmed.
    - **Impact.** It grows from 1 comic to up to 50 per failure. The live base rate so far is 0 of 6,141 tickets.
    - **Fix.** Record a per-entry failure, as `skipped` does, then continue. Keep `needs_attention` only for interrupted or partly written archives.
  - F27 [Minor] `batch.py:141-144`, `automatic.py:179-182`. Provenance has small gaps.
    - **History source.** `history.source` is set in a separate transaction after `write_metadata` commits. A crash in between leaves `''`; Notes still carry the provenance.
    - **Plan-time records.** The `in_book` evidence and the cover task's `not_needed` state are recorded when the comic is planned. They stay that way if the write is skipped or fails, so the Lens task is lost.

### 6. Input Handling

- Status: Pass for this range.
  - **Filename and reading parsing.** Bounded regexes (`LANGUAGE_TAG`, `PAREN_NUMBER`, `COVER_NUMBER`, `INDICIA_ISSUE` with `{0,80}` bounds), with no catastrophic backtracking found.
  - **Credits text.** Capped at 4,000 characters.
  - **Config.** `sources.disabled` accepts only a list. A typo in a source name silently leaves that source on (cosmetic).
  - The language-list mismatch is under F25.

### 7. Maintainability

- Status: Pass.
  - **Structure.** `in_book.py` is self-contained and documented. `PassPlan` replaces five copies of plan-writing code, and the switches live in one module.
  - **Duplication.** The ComicVine regex is duplicated (`in_book.py:52`, `automatic.py:286`). They match today, so consider sharing one.

### 8. Doc/Code Drift

- Status: Concerns
- Findings:
  - F28 [Minor] The docs promise more than the code does.
    - `README.md:41` says "a known publisher is added only when its full name is on the cover". It is added when the model says so (F21).
    - `README.md:41` also says a "reading-order prefix the cover does not show" is not written. Only numeric prefixes are blocked (F26).
    - `SOURCE_CONNECTORS.md:99-100`, `README.md:59` and Brief `:46` say later held passes ask only ComicVine and follow 5/10/20/40/60 minutes.
      - Metron is asked again on a held pass when its own schedule is due (`automatic.py:310-320`).
      - Stale source entries can make the comic due at every pass (F24).
  - F15: narrowed (see the earlier-findings table).

### 9. Build & Release Hygiene

- Status: Pass.
  - **Suite.** On an isolated `git archive` export of `f677193`: 550 tests, OK, 33 skipped (`python -B -m unittest discover -s tests`). The run left no `data/` or `work/` in the export.
  - **Existing tests.** Changes only switch sources back on where kept code is under test, and move scratch folders. No safety assertion was weakened.
  - **Repository.** No secrets or generated files. `.env.example` only. No attribution trailer.
  - **Version.** `VERSION` and `CHANGELOG` move in Sully's bump commit.

---

## Patterns

This is the second release in a row where the risk sits in what counts as enough evidence, not in the write chain. The backup, read-back and SHA-256 chain held in every probe. The issues were trust in model output (F21, and F11 earlier) and timing between reading state and acting on it (F22; F10/F16 earlier). A cheap guard pays for both: re-confirm "empty" and "same file" at the last moment before writing, and do not let a single model field decide a sticky value.

---

## Verdict

- Total Critical: 0
- Total Major: 3 open (F21, F22, F23)
- Total Minor: 12 open (F24, F25, F26, F27, F28; carried F11, F12, F13, F14, F15, F19, F20)
- Closed this range: F18 (its reported cause)
- Safety-floor violations in the range: 0

Round 1 verdict for f677193 (superseded; Round 3 below holds the current verdict line): RELEASE CLEAR.

No Critical finding blocks. The v0.1.2 identity rules are intact, and the write chain is intact for every comic in a multi-comic plan.

**Recommended before deploy (not blocking):**

- **F22.** A small guard (a stat check in `PassPlan.add`, or a `before` check in `apply`) closes the only data-loss path I found.
- **F21.** This is Sergei's call. With publisher on, the first in-book wave writes about 2,865 publishers, of which roughly 4-5% disagree with other evidence, and they stick. `"in_book": {"publisher": false}` keeps Series and Number until he decides.

**Open product questions for Sergei:**

- **In-book publisher (F21).** Should it need path or folder corroboration, or stay off?
- **Filename Series (F26).** Should Series stay the filename's full text (event and imprint prefixes included), or be the cover's shorter title when the filename has extra words?
- **Carried from v0.1.2.** Dead-ID writes, the missing-key hold, and Lens leads needing one signal that does not come from the cover.

Futaba's behavior verdict is separate.

| # | Sev | Dim | file:line | Finding | Next-cycle action |
|---|-----|-----|-----------|---------|-------------------|
| F21 | Major | 2 Correctness | `in_book.py:139-151`, `:182-186` | Publisher taken from the model's reading; 4-5% disagree with embedded or folder evidence; sticky | Corroborate with path or folder evidence, or veto on disagreement; or default `in_book.publisher` off |
| F22 | Major | 5 State & Data | `automatic.py:234-268`, `:165`; `batch.py:139-140` | An edit made after the pass's scan is overwritten and its backup deleted (probe P2); pre-existing, window widened | Check size/mtime against the row signature in `PassPlan.add`, or check `before` against the archive in `apply` |
| F23 | Major | 5 State & Data | `batch.py:118-152`; `worker.py:81-85`; `coverage_priority.py:33` | One failing archive strands up to 49 others permanently (probe P1) | Fail per entry and continue; keep `needs_attention` for interrupted or partial writes |
| F24 | Minor | 4 Performance | `source_scheduling.py:49-51`; `automatic.py:292`, `:373-376` | Stale source entries bypass the hold backoff (5.5 passes per comic per hour against 1.4) | Ignore or refresh carried entries on held passes |
| F25 | Minor | 2 Correctness, 6 Input | `coverage_priority.py:60`, `:104`; `in_book.py:46`; `coverage_priority.py:44` | `ready` ignores the language exclusion, so a folder can be pinned (probe P3; 0 live); tag lists differ | Gate `ready` on `language_eligible`; share one list |
| F26 | Minor | 2 Correctness | `in_book.py:78-97`, `:113-136`, `:176-178` | Series string carries prefixes, `_` for apostrophes and varying spellings; `Yucatan 1512` gets the wrong Number | Prefer the cover title when a word prefix is left over; normalize `_s`; guard 4-digit title numbers |
| F27 | Minor | 5 State & Data | `batch.py:141-144`; `automatic.py:179-182` | `history.source` set after the write commits; evidence and cover task marked at plan time | Write the source inside `write_metadata`'s insert; mark the task after the write |
| F28 | Minor | 8 Doc drift | `README.md:41`, `:59`; `SOURCE_CONNECTORS.md:99-100`; Brief `:46` | Publisher "on the cover", "reading-order prefix" and held-pass claims overstate the code | Align with the code and the F21, F24 and F26 outcomes |
| F11, F12, F13, F14, F19 | Minor | — | as in v0.1.2 | Unchanged | As before |
| F15 | Minor | 8 Doc drift | `SOURCE_CONNECTORS.md:64,66`; `SYNOPSIS_POLICY.md:8` | Narrowed to the F11-tied lines | Align after F11 |
| F20 | Minor | 8 Doc drift, 5 State | `automatic.py` `detail` | Still not shown; now documented as such | Show `detail` |

## Method and limits

- **Read:**
  - the whole diff;
  - `in_book.py` and `pilot_credits.py` in full;
  - `automatic.discover`, `batch.apply`, `app.write_metadata`, `app.api`, `worker.run_one`/`main`/`tickets`, `scheduler.select`/`finish`;
  - `coverage_priority` (ordering, due, probe), `source_scheduling.due`/`ready`/`record`;
  - `research.resolve_leads`/`lead_context`/`general_lookup`/`publisher_lookup`/`cover_agrees`, `metron.lookup`/`metadata_fields`;
  - the yandex and web_search changes, and the changed tests.
- **Exports:** `git archive` of `f677193` and `31798b6` into the session scratchpad (`senua_v013/exp_*`). All runs used `-B` and `PYTHONDONTWRITEBYTECODE`; nothing ran inside the worktree.
- **Suite:** 550 tests, OK, 33 skipped.
- **Live snapshot (read-only).**
  - **Copied.** `data/catalog.sqlite` (with no WAL or SHM present at the time) and `data/research/` (52,959 evidence files) were copied from the main checkout into the scratchpad. The copy was opened with `mode=ro`.
  - **Not touched.** The service, the queue and the library archives.
  - **Probes.**
    - `project_in_book.py`: the real `in_book.identify`, `ready` and `language_eligible` over all 40,029 rows. Result: 8,566 projected writes (Series 8,204, Number 7,445, Publisher 2,865).
    - `blank_and_judge.py`: embedded values as ground truth.
    - `publisher_peers.py`: folder-peer publishers.
    - `probe_index.py`: run on a separate copy.
- **New probes** (`senua_v013/probes/`):
  - `probe_v013.py`: P1 partial failure, P2 edit race, P3 language pin.
  - `probe_f18_error.py`: the backoff bypass, on the real `app.api` and `discover` with a virtual clock, reusing Ender's harness.
- **Earlier probes rerun** (`senua_r2/probes/`, on both commits): the ten listed in focus answer 3, plus `probe_r5_holdloop` in four modes and with 40 comics.
- **Not run:** the service, any browser, any public request, Ollama, the credits pilot itself.
- **Not verified:**
  - **Publisher ground truth.** Embedded values and folder peers can themselves be wrong. The 4-5% rate is a disagreement rate, not a proven error rate.
  - **Duplicate ZIP entries.** How many library archives have them (F23); counting would mean opening live archives.
  - **Concurrent edits.** How often Sergei edits archives with another tool during a pass (F22).

---

# Round 2 (7dcfe0e)

## Header (Round 2)

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-13
Tool: Comics Meta Organizer
Release: v0.1.3
Commit range: f6771933e757229b43c5bbb93211b598b9f7d065..7dcfe0e174ecac0d00edd2e4c6146e7fe86d9922
  (one commit, 7dcfe0e; 13 files, +465 / -41; 4 test files, +302 / -6)
Cumulative range certified: 31798b6..7dcfe0e
Worktree / branch: WIP/Comics Meta Organizer-v013, feat/v0.1.3-throughput (HEAD 7dcfe0e, no tracked changes)
```

## Summary (Round 2)

- **Closed.** F22 and F23 for their reported causes (P2 and P1 now pass). F24 (the probe is back to the control rate). F21 as a default: publisher is off, and the product question stays with Sergei.
- **Narrowed.** F27 (history source is now in the same insert) and F28 (the publisher wording is fixed).
- **One new Major, F29.** A write that fails after the backup step leaves a full-size backup in the library folder. The daily retry then makes another one each day. There is no cap and no dashboard signal. Probe-verified: 5 backups in 5 virtual days.
- **No Critical, nothing on the safety floor.** The ten v0.1.2 identity probes and the F18 hold-loop probe give identical output on f677193 and 7dcfe0e.

## Ender's claims

| Claim | Result | Evidence |
|---|---|---|
| F22: plans record the scan-time signature | Yes, at all five `plan.add` sites (`automatic.py:183`, `:414`, `:499`, `:517`, `:545`) | Diff read; P2's plan entry carries it |
| F22: `expected` is checked "on the same read used for the write" | The check is real, but not on the same read. It re-opens the file through `read_metadata` (`app.py:460`). The XML comes from the first handle (`:466`) and the pages from a third open (`:486`). All three sit inside the size/mtime window `:443` to `:505`, so the effect is the same apart from the residuals in answer 1 | Code read; T1, T4, T5 |
| F22: a changed comic is skipped and no backup is created | True for both new guards (signature and ComicInfo); both run before the backup. The older "changed while preparing" check (`app.py:507`) runs after the backup and now also skips, leaving that one backup | P2, T1; code read |
| F23: a byte-identical failure goes to `failed.json` and the rest is written | Yes | P1 (Example 003 written, ticket complete); T6, T8 |
| F23: the comic becomes `write_failed` and retries normally | Yes: daily, with no cap (F29) | T7 |
| F23: a possibly-replaced archive still stops the ticket, backup kept | Yes | Ender's readback test; T9 (catalog locked after the replace); T4 |
| F21: publisher off by default | Yes. `ready` follows the switch, so publisher-only comics are no longer made due | Projection: 8,326 writes and 0 Publisher (was 8,566 and 2,865). The live `config.json` has no `in_book` key, so the default applies on deploy |
| F24: leftover source errors ignored for held comics on the same archive | Yes, and only in the due decision | `probe_f18_error`: 1.4 passes per comic per hour, the control rate (5.5 at f677193) |
| F27: `history.source` stored in the same insert | Yes (`app.py:520-521`) | Ender's test; code read |

## Answers to the brief's questions

### 1. Does `write_metadata`'s `expected` check have a TOCTOU gap?

**No new one.** After the check, the write is guarded by the size/mtime comparison at `app.py:505` and by the backup SHA chain.

- **A same-size, mtime-restored edit between the check and the backup (T4).**
  - The edit is lost from the archive but kept in the backup.
  - `remove_verified_backup` then refuses ("Backup verification failed"), the ticket stops and the backup stays. Fail-closed.
- **Any edit that completes between the final stat and `os.replace` (T5).**
  - The edit is lost and the backup is removed.
  - The window is two statements wide and unchanged since v0.1.2.
  - A tagger that is still writing holds the file open, and Windows then refuses `os.replace` (T8), which is safe.
- **Not a finding.** Both cases need an injected edit to reproduce.

### 2. Can the size/mtime signature be fooled by an edit that keeps both?

**Yes, but the signature is not load-bearing.** T1 and T2 rewrite ComicInfo at the same size and restore the mtime; the signature still matches.

- **Planned field edited (T1).** The ComicInfo check catches it: skipped, Sergei's value kept, no backup.
- **Only another field edited (T2).** The comic is written and the other field is kept, because the write starts from the archive's current XML.
- **Any byte change after the plan's digest.** The digest catches it.
- **Side effect.** Such an edit leaves the catalog row stale, because the scan skips files whose size and mtime match. The comic is then re-planned and skipped once a day until the archive changes. Nothing is written and no backup is made, so this is noise only.

### 3. Is the byte-identical check reliable?

**Yes, as a test of whether the archive was replaced.**

- **How it works.** It compares a full SHA-256 with the plan digest, which `changed_since_planning` re-verified moments before. A read error counts as changed (`batch.py:126-131`).
- **Classification held in every probe.**
  - Before the replace: a CRC-damaged page (T6), duplicate entries (P1) and a refused replace (T8) all become `write_failed`.
  - After the replace: a locked catalog (T9) and a readback mismatch (Ender's test) stop the ticket.
  - Another program's edit mid-write (T4) also stops the ticket. That is a conservative false positive.
- **Its limit.** It speaks only for the archive, not for the backup the attempt already made (F29).

### 4. Can `write_failed` loop?

**Not tightly. It repeats daily, forever.**

- **Probe T7.** 720 ten-minute passes over 5 virtual days gave 5 plans and 5 tickets, all complete.
- **Why it is not tight.** `write_retry_waiting` holds the comic for 24 hours. The folder probe uses the same `lookup_flags`, so the comic does not pin its folder.
- **What is wrong with it.**
  - There is no retry cap.
  - A failure after the backup step leaves one full backup per retry (F29).
  - `write_failed` is counted in `discovery_state.counts`, but the dashboard's "still need research" line sums three other outcomes (`static/index.html:136`). Before this commit, the same failure showed as an attention ticket.

### 5. Does F24 hide a real new error?

**No.**

- **Nothing is dropped.** The source entries stay in the record; only the due decision in `lookup_flags` ignores them (`coverage_priority.py:66-67`).
- **Narrow condition.** It is the same condition as `held_before`. So it applies exactly when the next pass would be `wait_only`, and that pass would not re-run those sources anyway.
- **Wake-ups kept.** A changed archive, a new matcher version, new cover leads, ComicVine answering, or the hold's own retry still make the comic due.
- **The one change.** A Metron error on a held pass now waits for the hold retry (at most an hour; a day for a missing key) instead of Metron's own retry. Metron's answer cannot be written before ComicVine answers, so nothing is lost.

## Probes (Round 2)

All ran on a `git archive` export of 7dcfe0e, with every source mocked and nothing run in the worktree.

| Probe | f677193 (round 1) | 7dcfe0e |
|---|---|---|
| P1: duplicate entries in comic 2 of 3 | Ticket needs attention; comic 3 never written or offered again | Ticket complete; comics 1 and 3 written; comic 2 is `write_failed` and retried daily |
| P2: edit after the scan, before the plan | "Spawn (Sergei)" overwritten, backup deleted | Kept; skipped ("changed after the folder scan"); no backup, no history row |
| `probe_f18_error` (error / control) | 5.5 / 1.4 passes per comic per hour | 1.4 / 1.4 |
| `probe_r5_holdloop` as passes / ComicVine requests / local reads (8 comics 6 h; 40 comics 6 h; revoked 24 h; missing key 24 h) | 74/32/8; 394/64/40; 218/104/8; 16/8/8 | Identical |
| Ten v0.1.2 identity probes | (baseline) | Identical to f677193 |
| T1 to T9 (new, `probe_r2.py`) | (new) | As cited above; T6 to T8 show the F29 backups |

## Findings at 7dcfe0e

### New

- F29 [Major] Dimension 5, State & Data. `app.py:481-484`, `:486-508`; `batch.py:193-199`; `discovery_state.py:61`. A failed write leaves its backup, and the daily retry adds another one each day.
  - **Mechanism.**
    - `write_metadata` copies the whole archive to `.comic-metadata-backups` before it builds the temporary archive.
    - A failure after that point leaves the archive untouched, so `apply` records `write_failed` and moves on. Nothing removes that attempt's backup.
    - After 24 hours the comic is planned again, fails the same way and leaves another copy.
  - **What triggers it.**
    - A page with a bad CRC (T6). The scan reads only ComicInfo, so the catalog calls such a comic `missing` or `embedded`.
    - An encrypted entry, or one with an unsupported compression method.
    - A failed temporary-archive check.
    - `os.replace` refused because another program has the comic open (T8).
  - **What does not trigger it.** Duplicate ZIP entries and a leftover temporary file fail before the backup is made. Those are the two cases Ender's tests cover, which is why the tests show no backups.
  - **Probe T7.** Over 5 virtual days it left 5 backups, each a full copy of the damaged comic. Nothing else in the code cleans them up.
  - **No signal.** `write_failed` is not shown on the dashboard. The Brief's revisit trigger ("one archive keeps failing its daily retry") has nothing that would tell Sergei.
  - **Why Major, not Critical.** No data is lost: each backup is a byte copy of an archive that is still in place. The cost is unbounded disk growth in the library folders.
  - **Base rate.** Unknown. 0 of 6,141 live tickets ever needed attention, but about 8,300 archives the app has never opened are about to be written.
  - **Starting points.**
    - Delete the backup made by a failed attempt once the archive is confirmed unchanged and the backup's digest equals the plan's.
    - Or make the backup only after the temporary archive is built and checked.
    - Stop retrying after a few failures on the same archive, and list the comic on the dashboard.
  - **Related.** The "changed while preparing" skip (`app.py:507`) also leaves its backup. That happens once per event, not daily, because the archive has changed.

### Status of earlier findings

| # | Round 1 | Now | Evidence |
|---|---|---|---|
| F21 | Major | Closed as a default; the product question stays with Sergei | Projection; config check |
| F22 | Major | Closed | P2, T1, T2; residual windows in answer 1 |
| F23 | Major | Closed for its reported cause; the residual is F29 | P1, T6, T8, T9 |
| F24 | Minor | Closed | `probe_f18_error` |
| F27 | Minor | Narrowed, still open. The history half is closed. The in-book evidence and the cover task's `not_needed` are still set at plan time. A skipped comic whose archive changed gets a fresh Lens task; one on an unchanged archive does not | `app.py:520-521`; `cover_tasks.enqueue` |
| F28 | Minor | Narrowed, still open. The publisher wording is fixed. "Later held passes only ask ComicVine" (`README.md:59`, `SOURCE_CONNECTORS.md:99`, Brief `:46`) still leaves out Metron. The reading-order-prefix claim (`README.md:41`) still overstates F26 | Doc read |
| F25, F26 | Minor | Unchanged | — |
| F11, F12, F13, F14, F15, F19, F20 | Minor | Unchanged | — |

## Rubric (Round 2 range)

Severity tags and the always-blocking safety floor: `Team/Docs/ProcessRules.md` § Severity definitions.

1. **Security: Pass.** No shell-out, network or delete change. `ArchiveChanged` is a `ValueError`, so manual-write callers still catch it. No secrets, no attribution trailer.
2. **Correctness & Logic: Pass.** The guards and the classification match the claims (claims table).
3. **Crash / Stability Safety: Pass.** An error inside `not_written` itself (for example a locked catalog) escapes and stops the ticket, which is fail-closed.
4. **Performance: Pass.** One extra stat per entry; a full digest only on failure.
5. **State & Data Safety: Concerns.** F29.
6. **Input Handling: Pass.** `in_book.publisher` accepts only a literal `true`.
7. **Maintainability: Pass.** `write_not_done`, `changed_since_planning` and `unchanged` are small and documented.
8. **Doc/Code Drift: Concerns.** F28 (narrowed). `README.md:51` and the Brief's "Pass plans" row are accurate that a failed comic is retried and no backup is removed. Neither says that a backup is left on each attempt (F29).
9. **Build & Release Hygiene: Pass.** 558 tests, OK, 33 skipped (550 at f677193, plus 8 new). The export was left clean. `VERSION` and `CHANGELOG` still move in Sully's bump commit.

## Verdict (Round 2, superseded)

- Total Critical: 0
- Total Major: 1 open (F29)
- Total Minor: 11 open (F25, F26, F27, F28; carried F11, F12, F13, F14, F15, F19, F20)
- Closed in Round 2: F21 (as a default), F22, F23 (its reported cause), F24
- Safety-floor violations in `31798b6..7dcfe0e`: 0

Round 2 verdict for 7dcfe0e (superseded; Round 3 below holds the current verdict line): RELEASE CLEAR.

This Round 2 clearance covered `31798b6..7dcfe0e` plus Sully's version/changelog-only bump commit. It is replaced by Round 3's clearance of `31798b6..d3e9723`.

**Recommended before deploy (not blocking).** The cheap half of F29: remove the backup a failed attempt made, once the archive is confirmed unchanged. Without it, each comic that keeps failing adds one full copy of itself to its folder every day, unseen.

**Open product questions for Sergei (unchanged):** the in-book publisher (on, off, or with corroboration; F21) and the filename Series string (F26).

| # | Sev | Dim | file:line | Finding | Next-cycle action |
|---|-----|-----|-----------|---------|-------------------|
| F29 | Major | 5 State & Data | `app.py:481-508`; `batch.py:193-199`; `discovery_state.py:61` | A failed write leaves its full backup, and the uncapped daily retry adds one more each day; not shown on the dashboard (T6, T7, T8) | Remove a failed attempt's verified backup, or back up only after the temporary-archive checks pass; cap retries and show `write_failed` |
| F27 | Minor | 5 State & Data | `automatic.py:179-185` | History half fixed; evidence and cover-task state still set at plan time | Mark the cover task after the write |
| F28 | Minor | 8 Doc drift | `README.md:41`, `:59`; `SOURCE_CONNECTORS.md:99`; Brief `:46` | Held-pass "only ComicVine" and the reading-order-prefix claim remain | Align with the code and the F26 outcome |
| F25, F26, F11-F15, F19, F20 | Minor | — | as in Round 1 | Unchanged | As before |

## Method and limits (Round 2)

- **Read:**
  - the whole diff;
  - `app.write_metadata`, `remove_verified_backup`, `read_metadata` and `scan`;
  - `batch.apply` and `catalog_row`;
  - `automatic.discover`: the plan sites, the hold, record saving and the pause returns;
  - `coverage_priority.lookup_flags`, `order_rows` and `pending_paths`; `source_scheduling.due`;
  - `in_book.judge`, `identify`, `ready` and `entry`; `cover_tasks.enqueue` and `identified`;
  - `worker.run_one`, and the dashboard's research line.
- **Export.** A `git archive` of 7dcfe0e in the session scratchpad (`senua_v013/exp_7dce`), run with `-B` and `PYTHONDONTWRITEBYTECODE`.
- **Projection.** `project_in_book.py`, run with the 7dcfe0e code over the same read-only catalog snapshot as round 1.
- **Live config.** Only the `in_book` key of the main checkout's `config.json` was checked; it is absent.
- **Not run:** the service, any browser or public request, Ollama.
- **Not verified:** how many library archives have a damaged page, an encrypted entry or an unsupported compression method (F29's base rate). Counting them would mean opening live archives.

---

# Round 3 (d3e9723)

## Header (Round 3)

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-13
Tool: Comics Meta Organizer
Release: v0.1.3
Commit range: 7dcfe0e174ecac0d00edd2e4c6146e7fe86d9922..d3e972369d29c833d1db7a4719841a28a0783225
  (one commit, d3e9723; 7 files, +423 / -22; 1 test file, +301 / -1)
Cumulative range certified: 31798b6..d3e9723
Worktree / branch: WIP/Comics Meta Organizer-v013, feat/v0.1.3-throughput (HEAD d3e9723, no tracked changes)
```

## Summary (Round 3)

- **F29 is closed.** A failed attempt's own backup is now removed, but only when that is safe, and retries back off and then stop.
  - T6, T7 and T8 now leave 0 backups.
  - Over 40 virtual days, T7 stops after 5 attempts.
- **No path deletes the only good copy of an archive**, among the paths this code controls. The backup is kept in every case where the archive may have changed: replaced, truncated, deleted or unreadable.
- **Two new Minors. Neither loses data.**
  - **F30.** The link check misses junctions, and `rmdir` then removes a junctioned backup folder. This is old code that every successful write also reaches.
  - **F31.** The new cleanup runs even when the caller asked to keep backups.
- **No Critical, nothing on the safety floor.**

## Ender's claims (Round 3)

| Claim | Result | Evidence |
|---|---|---|
| `write_metadata` reports the exact backup it created | Yes. `attempt['backup']` is set only after the copy completes (`app.py:490-492`). A copy that fails part-way is not reported, so nothing is deleted for it | Code read; T6, T8 |
| It refuses to reuse an existing name | Yes (`app.py:488-489`). The refusal comes before the copy and before `attempt` is filled, so nothing is deleted | R4: three cases (an existing name holding the same bytes, one holding different bytes, one in other letter case) all refused, with the existing file untouched |
| A backup is removed only when a write fails and the archive digest is unchanged | Yes. `unchanged()` (full SHA-256) runs first. Any other result re-raises and keeps the backup (`batch.py:213-214`) | T9, R6a, R6b; Ender's replaced-archive tests |
| Only that path is removed, after location, name and link checks and a digest match | Location, name and digest: yes. The link check misses junctions (F30) | R3; Ender's test with older backups beside it |
| In every other case the backup is kept | Yes. Any error in the cleanup keeps the backup and appends "Backup kept: ..." to the reason (`batch.py:134-146`) | Ender's mismatched-digest test |
| Retries back off 1/2/4/7 days and stop after 5 until the file changes | Yes | T7L: gaps of 1, 2, 4 and 7 days; stopped with `retry_at` 0; held for the remaining 26 days. A repaired file is planned and written at the next pass |
| A visible `detail` is recorded | It is recorded in the research record but not shown on the dashboard yet, as the README and Brief say (F20) | T7L |

## Answers to the brief's questions (Round 3)

### 1. Can any path delete a backup that is the only good copy?

**No, among the paths this code controls.** A backup is deleted only when all three of these hold:

- The archive's full SHA-256, re-read after the failure, equals the plan digest.
- The path is the one this attempt created, under a name that was free before the copy.
- The backup's own full SHA-256 equals the same plan digest.

Case by case:

- **The archive was replaced.** A failure after `os.replace` (T9, or a readback mismatch) fails the digest check. The ticket stops and the backup is kept.
- **A partial replace.**
  - A replace that deletes the destination and then fails (R6a) leaves no archive. The `finally` clause also removes the temporary file, so the backup is the only copy. It is kept.
  - A replace that truncates the destination (R6b) fails the digest check. The backup is kept.
- **The archive is unreadable.** `unchanged()` treats any `OSError` as a change, so the backup is kept.
- **An older backup with the same name, or with a name that differs only in case.**
  - The write is refused before the copy (R4); on NTFS, `exists()` ignores case.
  - On this Python, names are unique to 100 ns (`GetSystemTimePreciseAsFileTime`). The gap between `exists()` and `CopyFile2` cannot be hit in practice.
- **A plan path spelled in another case.** `resolve()` returns the case on disk, so the write and the cleanup work (R5).
- **A junction.** The guard misses it (F30), but the file deleted is still this attempt's digest-checked copy. Other backups in the junction's target survive (R3).
- **A directory symlink.** Not run, because this account cannot create one. In the code, `is_symlink()` rejects it and the backup is kept.
- **A race with another writer (R2) is the one residual.**
  - The archive is hashed before the backup. If another program rewrites the archive while the backup is being hashed, its edit is kept, and the backup holding the pre-edit bytes is still deleted.
  - That copy existed only because of this attempt, so Sergei is never worse off than if the write had not been tried. **Not a finding.**
  - Cheap hardening: hash the backup first, then check the archive, then unlink. That shrinks the window to a single stat.

### 2. Is the digest comparison done on the right bytes?

**Yes.**

- **Two full-file reads.** Each compares a full SHA-256 of raw file bytes with `entry['sha256']`:
  - the archive, in `unchanged`;
  - the exact backup path the attempt reported, in `remove_verified_backup`.
- **The plan digest is current.** It was taken when the comic joined the plan, and `changed_since_planning` re-checked it at the start of the same entry.
- **What equality proves.** Backup = plan = archive means the backup is a byte copy of an archive that is still in place. File bytes, rather than ZIP members, is the strictest comparison available.
- **The same file.** Both paths go through `filesystem_path`, so the write and the check touch the same file.

### 3. Is the retry count kept correctly across re-plans?

**Yes.**

- **Every save path carries the run.**
  - All three `save_one` call sites in `automatic.py` (`:191`, `:287`, `:582`) go through `with_write_failures`.
  - `with_write_failures` reads the run from the stored row, not from the pass's in-memory copy. It keeps the run only when the `[size, mtime]` lists match.
  - `write_not_done` counts up from the stored record.
- **T7L.**
  - 160 passes over 40 days gave 5 attempts and then a stop.
  - At most one backup existed at any moment, and none was left.
  - A repaired file dropped the run and was written.
- **Skips.** Ender's test covers a skipped write in between: it is not counted.
- **Two consequences of keying the run on `[size, mtime]`. Neither is a finding.**
  - A change to the modification time alone restarts the count, for example a sync tool touching the file. That allows at most 5 more attempts, and each removes its own backup.
  - A file held open long-term looks the same as a damaged one. For example, a torrent client that seeds without delete sharing refuses every replace, so the comic stops after 14 days. Jane's brief accepts this. The stop is not shown on the dashboard (F20).

## Probes (Round 3)

Every probe ran on a `git archive` export of d3e9723 (`senua_v013/exp_d3e9`), with `-B` and `PYTHONDONTWRITEBYTECODE` and every source mocked. Nothing ran in the worktree or the library.

| Probe | 7dcfe0e (Round 2) | d3e9723 |
|---|---|---|
| T6: CRC-damaged page in a 3-comic plan | Comics 1 and 3 written; 1 backup left | Comics 1 and 3 written; 0 backups left |
| T7: 5 days of 10-minute passes | 5 plans, 5 backups left | 3 plans (days 0, 1 and 3), 0 backups left, next attempt in 48.5 h |
| T7L (new): 40 days of 6-hour passes, then a repair | — | 5 attempts with gaps of 1/2/4/7 days, then stopped (`retry_at` 0). At most 1 backup at once, 0 left. Written after the repair |
| T8: replace refused (file open) | Comic 2 written; 1 backup left | Comic 2 written; 0 backups left |
| T9: failure after the replace (catalog locked) | Ticket needs attention, backup kept | Same |
| R2 (new): another program rewrites the archive inside the cleanup window | — | Pre-edit backup deleted; the other program's edit kept (answer 1) |
| R3 (new): the backup folder is a junction holding an older backup | — | This attempt's backup deleted in the junction's target; older backup kept; **junction removed** (F30) |
| R3W (new): the same junction, successful write | Junction removed | Junction removed (F30 is old code) |
| R4 (new): backup name already in use (same bytes / different bytes / other case) | — | All three refused; the existing file untouched; no `backup` key in `failed.json` |
| R5 (new): plan path in another case | — | Comic 1 written and comic 2 failed, as normal; the failed attempt's backup removed |
| R6 (new): a non-atomic replace that (a) deletes or (b) truncates the destination, then fails | — | (a) Archive gone, backup kept, ticket needs attention. (b) Archive truncated to half length, backup kept, ticket needs attention |
| R9 (new): `batch.py apply` without `--remove-verified-backups` | — | Written comic's backup kept; failed attempt's backup removed (F31) |

## Findings at d3e9723

### New

- F30 [Minor] Dimension 1, Security (delete validation). `app.py:413-414`, `:422`. The link check in `remove_verified_backup` misses a junction, and the cleanup then removes the junction itself.
  - **Mechanism.** The check reads the reparse-point flag through `stat()`. `stat()` follows a junction, so the flag is never seen. `lstat()` and `is_junction()` both show it. `is_symlink()` is false for a junction.
  - **Effect.** A junctioned `.comic-metadata-backups` passes the check. After the backup is deleted, `intended.rmdir()` removes the junction itself, even when its target still holds other backups (R3).
  - **What is not lost.** The deleted file is this attempt's digest-checked copy, and the target's other backups survive.
  - **Cost.** A redirect Sergei set up is undone without notice, and later backups land in the library folder.
  - **Age.** The same happens after every successful write at 7dcfe0e (R3W). This commit adds a second caller.
  - **Starting point.** Use `lstat()`, or `is_junction()` on Python 3.12 and later, for both checks.
- F31 [Minor] Dimension 5, State & Data. `batch.py:221-228`. The failure-path cleanup ignores `remove_verified_backups`.
  - **Mechanism.** `batch.py apply` without `--remove-verified-backups` keeps the backups of written comics. It still removes a failed attempt's backup (R9).
  - **Why it is harmless.** That backup is a byte copy of an archive that is still in place.
  - **Why log it.** It overrides the caller's explicit choice, and `README.md:92` says only automatic failures remove their backup.
  - **Starting point.** Gate the cleanup on the flag, or say in the CLI help and the README that a failed attempt's copy is always removed.

### Status of earlier findings

| # | Round 2 | Now | Evidence |
|---|---|---|---|
| F29 | Major | Closed: the cleanup works and the retries are capped. The dashboard half belongs to F20: `detail` is recorded but not shown, as the README and Brief say | T6, T7, T7L, T8, R2 to R6 |
| F20 | Minor | Still open; now also covers `write_failed` and the stop | `README.md:62`; Brief "Failed writes" row |
| F27, F28 | Minor (narrowed) | Unchanged | — |
| F25, F26, F11-F15, F19 | Minor | Unchanged | — |

## Rubric (Round 3 range)

Severity tags and the always-blocking safety floor: `Team/Docs/ProcessRules.md` § Severity definitions.

1. **Security: Concerns.** F30. No shell-out or network change, and no secrets. d3e9723 has no attribution trailer.
2. **Correctness & Logic: Pass.** The backoff and the stop match the claims (T7L). The classification is unchanged from Round 2.
3. **Crash / Stability Safety: Pass.** Every cleanup error is caught and recorded, and the backup is kept.
4. **Performance: Pass.** One more full hash per failed attempt, at most 5 per archive, and one more `SELECT` per record save.
5. **State & Data Safety: Concerns.** F31. No path that loses data was found (answer 1).
6. **Input Handling: Pass.** A malformed `write_failures` value (not a dict, or a different signature) starts a fresh run.
7. **Maintainability: Pass.** `discard_failed_backup`, `failed_write` and `with_write_failures` are small and documented. Ender's tests mirror the probes.
8. **Doc/Code Drift: Concerns.** F28 (carried) and the README half of F31. The new README and Brief text on failed writes matches the code.
9. **Build & Release Hygiene: Pass.** 566 tests, OK, 33 skipped (558 at 7dcfe0e, plus 8 new). The export was left clean. `VERSION` still reads `0.1.2`; Sully's bump commit moves it.

## Verdict (current)

- Total Critical: 0
- Total Major: 0 open
- Total Minor: 13 open (F30 and F31 new; F25, F26, F27, F28; carried F11, F12, F13, F14, F15, F19, F20)
- Closed in Round 3: F29
- Safety-floor violations in `31798b6..d3e9723`: 0

**Verdict:** RELEASE CLEAR

This clearance covers `31798b6..d3e9723` plus Sully's version/changelog-only bump commit. Any other code or test change needs a fresh look.

**Nothing needs to land before deploy.** F30 and F31 can wait for the next cycle.

**Open product questions for Sergei.**

- **Unchanged:** the in-book publisher (F21) and the filename Series string (F26).
- **New, low priority:** should a comic whose automatic writes have stopped get a "try again" control and a dashboard count? This is the Brief's "Failed writes" revisit trigger, and it needs a UX spec.

| # | Sev | Dim | file:line | Finding | Next-cycle action |
|---|-----|-----|-----------|---------|-------------------|
| F30 | Minor | 1 Security | `app.py:413-414`, `:422` | The reparse-point check uses `stat()`, which follows junctions. A junctioned backup folder passes, and `rmdir` then removes the junction even when its target is not empty (R3, R3W) | Check with `lstat()` / `is_junction()` |
| F31 | Minor | 5 State & Data | `batch.py:221-228`; `README.md:92` | A failed attempt's backup is removed even without `--remove-verified-backups` (R9) | Gate it on the flag, or document it |
| F20 | Minor | 8 Doc drift, 5 State | `detail` in `automatic.py` and `discovery_state.py` | Hold, dead-link and failed-write details, including the stop, are recorded but not shown | Show `detail` and a `write_failed` count (UX spec) |
| F25-F28, F11-F15, F19 | Minor | — | as in Round 2 | Unchanged | As before |

## Method and limits (Round 3)

- **Read:**
  - the whole diff;
  - `app.write_metadata`, `remove_verified_backup` and `filesystem_path`;
  - `batch.apply`, `unchanged`, `changed_since_planning`, `catalog_row`, `digest` and the CLI;
  - all of `discovery_state.py`;
  - `coverage_priority.lookup_flags`, `write_retry_waiting` and `firstpass_folder`;
  - the three `save_one` sites in `automatic.discover`, and `PassPlan.add`;
  - `in_book.ready`;
  - `shutil.copy2` on Python 3.14, which uses `CopyFile2`.
- **Suite:** 566 tests, OK, 33 skipped.
- **Probes:** in `senua_v013/probes/`:
  - `probe_r2.py` for T6 to T9, unchanged;
  - the new `probe_r3.py` and `probe_r3w.py`.
- **Not run:** the service, any browser or public request, Ollama, the library.
- **Not verified:**
  - **A directory symlink (R3S).** This account lacks the privilege to create one. The code rejects it through `is_symlink()`.
  - **Network shares.** R6 only simulates a non-atomic replace; it was not run on a real SMB share.
  - **How many live archives fail to write.** Unchanged from Round 2.
