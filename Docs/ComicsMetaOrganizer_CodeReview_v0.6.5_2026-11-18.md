# Code Review — Comics Meta Organizer v0.6.5

## Header

```text
Reviewer: Senua (Code Reviewer)
Date: 2026-11-18
Tool: Comics Meta Organizer (Comic Metadata)
Release: v0.6.5 (version bump not yet made; Sully's version-only bump commit follows)
Commit range: 445bd36c79af3565f31ce1a66be4ee89466064c6 (v0.6.4)..0b2c8448e671a961985cabbcbf8f7718c32cf147
              round 1: 445bd36..0ca864e (sources, tools, tests, Brief)
              round 2: c253521..0b2c844 (e714685 fixes S1/S2/S3/N2, 9e7ed54 Brief, 0b2c844 Futaba sample F2/F3)
Candidate commit: 0b2c844 (ender/comicvine-name-search)
Files changed: 21 files, +3212 / -25 over the whole range (product source: comicvine_search.py, versedb.py,
               cover_match.py, app.py, automatic.py, metron.py, pipeline_config.py, provider_wait.py,
               research_runtime.py, source_scheduling.py; tools/*_would_write.py; tests; Brief)
Stand-down dimensions: none
```

---

## Summary

**Round 1 (0ca864e).** The range adds two opt-in fallback sources, both **off by default** (`pipeline_config.OPT_IN_SOURCES`): the ComicVine name search (after Metron and GCD offline miss; Metron's live identity rules; its own per-resource rolling-hour ledger `comicvine_requests`, 10 s spacing, 190 per resource from both paths) and VerseDB (after those and the name search; bearer token from the environment or `.env`; 280 per rolling hour, 12 s spacing; `!BD`-only no-year rule; French/English preference; Notes credit). Also: an additive `cover_match.archive_match`, the ID path's `reserve_request` logging its resource, long-miss scheduling for the two sources, two read-only "would write" tools, tests and Brief rows. Round 1 found three Majors (S1 saved results outlive the switch, S2 one-sided ComicVine headroom, S3 inline pacing) and cleared the release with them logged.

**Round 2 (c253521..0b2c844).** Ender's fixes for S1, S2, S3 and the inherited N2, plus a commit from Futaba's write sample: a stricter unnumbered-book guard shared with Metron's rule C (F2) and trimmed ComicVine values for every ComicVine path (F3). Red-team focus per brief: S1's gate now also governs Metron and GCD offline reuse, which are on today — could it drop valid results, wake many comics or stall writes; and whether S1/S2/S3 are resolved for switch-on.

Verified across both rounds: `cover_match.compare` is untouched and `archive_match` is additive; the name search's cache key and stored shape match `app.api`'s, `field_list` requests get distinct keys, VerseDB's keys are namespaced — no cache poisoning path; every new API parameter goes through `urlencode`, ids are `int()`-coerced, VerseDB paths are `fullmatch`ed, slugs regex-checked, cover hosts allow-listed with redirects re-checked; the bearer token goes only to `versedb.com` with redirects refused; no token or key reaches a status file, cache key, evidence entry, exception message or tool output; comics whose Web names a ComicVine issue are always excluded by `cites()`; lookup exceptions are caught per comic by `research_runtime.first_verified`.

Tests, run with the suite's isolation net loaded first and checked last. Round 1: 153 run, 152 passed, 1 environment error (`test_state_root` starts `python -S`; this review's system Python keeps Pillow in site-packages; unrelated). Round 2 on 0b2c844: `test_source_sample_fixes`, `test_review_065_fixes`, `test_comicvine_search`, `test_versedb`, `test_source_scheduling`, `test_source_switches`, `test_enrichment_options_20261117`, `test_metron`, `test_metron_year_rules`, `test_metron_variants`, `test_unnumbered_any_publisher`, `test_identity_rules`, `test_gcd_offline`, `test_identity_conflict_reuse`, `test_hold_backoff`, `test_research_runtime`, `test_comicvine_dead_id`, `test_app`, `test_automatic` plus probes — **276 run, all passed**. Probes (isolated state, repo's gitignored `scratch/`, removed afterwards) are cited per finding. `git diff --check` clean; no secret-shaped strings in the diff. No live state, live app, library or provider API was touched.

---

## Round 2 — the fixes

| Finding | Fix (e714685) | Status for switch-on |
|---|---|---|
| **S1** saved results outlive the switch | `source_scheduling.reusable` gates `research_runtime.reuse` (`automatic.py:424`): a saved result is dropped when its source is switched off; GCD offline, name-search and VerseDB results also need their current rules stamp; a Metron result is dropped when its rule's switch, `metron_spellings` (for a spelling) or `cover_rule_v2` (for an aligned/wraparound cover) is off | **Resolved.** Round 1's reuse probe re-run as a test (`SavedResultDiscoveryTests`, with positive control) |
| **S2** one-sided ComicVine headroom | `app.reserve_request` counts both paths per resource and refuses its own request locally (no shared cooldown) at 198 (`app.py:343-350`); the name search keeps 190 overall and steps aside from `search`/`issues` for 10 minutes after any manual dashboard request (`comicvine_search.py:195-199`) | **Resolved.** Probe: name search 150 `search`, then the ID path every 20 s: 48 more allowed, the 49th refused locally, **198** in the hour (was 241), `blocked_until` stays 0. On `issue` the name search's 15 plus the ID path's 180 stay at or below 195, so automatic ID-path lookups are never refused by the new check |
| **S3** inline pacing | Each discovery pass may sleep at most 30 s on fallback spacing (`research_runtime.pacing_wait`, budget set in `automatic.discover`); a longer wait raises `PacingDeferred`, nothing is asked, the comic's retry becomes ~60 s; VerseDB waits for the name search's final answer in that pass (`automatic.py:556-559`). Tools run outside a pass and keep full pacing | **Resolved for switch-on**, with a measurement still owed on the real machine (see Performance). Ender's simulated-clock measurement: longest pass 37 s (was 696 s), worker free 65% between passes |
| **N2** (inherited) snapshot URI | `tools/metron_would_write.readonly_uri`: `Path.as_uri()` + `?mode=ro`, shared by all three tools | **Resolved** (`SnapshotUriTests`, `#` and `%` in the folder) |

**S1 on the live paths that are on today (Metron, GCD offline).** Probe of `reusable` under the default switches: Metron results by `year`, `filename_year`, `folder_year`, `unnumbered`, with `today`, `aligned` or `wraparound` covers, and older results with no `match_rule`, all stay reusable; a current-stamp GCD offline result, the ID path's own ComicVine issue text, web research and Coffin Comics results stay reusable; only `yearless`, `collection_label` and spelling results (switches off today, so none can have been saved live) and an old GCD stamp are dropped — the last exactly as before (`automatic.py:421-423` in 0.6.4 already dropped it). Answers to the brief's three questions:
- *Drop valid results?* Not under today's switches: a Metron or GCD offline result is dropped only when the rule or source that accepted it is off now. Live, the newly dropped set is saved, unwritten results from sources already switched off: Image Comics (off since 11-17, 14 comics cite it) and results from the sources retired on 10-26 whose 30-day reuse window has not yet run out (by 11-25). Approved-list (`verified-sources.json`) results are recomputed by `publisher_lookup` in the same pass, so dropping their reuse loses nothing.
- *Wake many comics?* No. `reusable` is evaluated only for a comic already due; `due()`, `search_fingerprint()` and every rules stamp are untouched by e714685 (Metron's `RULES_VERSION` stays 3 in 0b2c844 as well).
- *Stall writes?* No. A dropped result only means the comic is researched normally on that pass (its sources by their own schedules); plan entries already written to `plan.json` are applied by the write cycle independently. Held comics keep their reused Metron evidence (Metron on, rules on).

**0b2c844 (Futaba's sample).** F2: `metron.BRACKETED_PART` refuses a bracketed part label as an unnumbered book. It is shared, so Metron's rule C (on today) becomes stricter in the safe direction only: fewer files are asked as issue 1, nothing new is accepted, `RULES_VERSION` is unchanged so nothing is woken; Ender's read-only live count says 62 files change and none carries a Number (not re-checked here: no live access). F3: `app.metadata_from_issue` trims values and drops whitespace-only ones for the ID path, the name search and manual apply; identity checks use the raw issue and `series_key` already ignored spaces, and `external_plan` fills only empty fields, so existing comics are not rewritten.

---

## Rubric

Findings carry their round-1 numbers. Round-2 additions are s9–s11.

### 1. Security

- Status: Pass. N2 resolved (see Round 2). Token and key handling pass (see Summary). No shell-outs; no Electron change in range.

### 2. Correctness & Logic

- Status: Concerns.
- **S2 [Major] — resolved in e714685** (see Round 2).
- **s1 [Minor]** `comicvine_search.py:372` (was `:358`): with no ComicVine key the name search returns `None`, which is stored as a 30-day long miss; the rules stamp does not include the key, so comics touched while the key was missing wait 30–45 days after it returns. VerseDB reports the same situation as `unavailable` (`versedb.py:403`); the name search should too.
- **s2 [Minor]** `comicvine_search.py` `lookup` (series key and detail re-check): `research.series_key` drops every non-ASCII character, so a series name with no Latin letters or digits has key `''`, every non-Latin volume counts as "the same name", and only the cover gate remains. VerseDB refuses this case (`versedb.py:133`); Metron has the same gap (`metron.py:176`).
- **s3 [Minor]** `comicvine_search.py` `lookup` search request, `versedb.py:407`: uniqueness is established within the first page only (100 volumes; 50 series); the pilot measured it but lists the second page as not verified, and the evidence cannot show that a write came from a truncated list. Record a `truncated` flag.
- **s4 [Minor]** `comicvine_search.py` `lookup` Publisher: the name search writes the volume's Publisher under `!BD`, while VerseDB withholds it there (`versedb.py:449`). Sergei's call, to be made once for both.
- **s9 [Minor]** `source_scheduling.py` `reusable`: a Metron result whose cover was accepted on archive page 2 or 3 (only possible with `cover_rule_v2` on) but with comparison `today` stays reusable after `cover_rule_v2` is switched off; the check looks at the comparison only. Add `(cover_match.page or 1) > 1` to the condition. `cover_rule_v2` is on today.
- **s10 [Minor]** `research.py:474` (`verify_web_source`): results from the free-web and wiki routes are labelled `Verified web research`, which names no switch, so `reusable` keeps them after `General free web` or `Wikipedia/wiki` is switched off — the Brief's "every switchable source" does not quite hold. Both are off today, so nothing live is affected.
- **s11 [Minor]** `metron.py:268-269` (`BRACKETED_PART`): the Roman-numeral branch also matches ordinary words built from i/v/x/l/c, and `of <digit>` matches any bracket with "of" and a number. Probe: "(Part Civil War)", "(Chapter Ill)" and "(Best of 2016)" are refused; "(Book Club Edition)", "(Volume Collection)", "(Part of the Story)" and scan-group tags are not. Refusal is the safe direction (lost recall for Metron rule C and both fallbacks, never a wrong match).
- **Inherited, unchanged in range:** **M1 [Major]** `app.py` case-sensitive scan range (now about `app.py:295`); **I1 [Major]** `gcd_matching.py:128`; **I2 [Major]** `automatic.py` mixed-provider synopsis attribution (now about `automatic.py:702`); **n3 [Minor]** errors count toward the long-miss streak; **n4 [Minor]** a rules-stamp change wakes every miss at once (also for the two new sources' stamps, bounded by their allowances).

### 3. Crash / Stability Safety

- Status: Concerns.
- No worker crash path: lookups run inside `first_verified`; `PacingDeferred` is a `ProviderDeferred`, recorded as `unavailable` with `next_at` a few seconds ahead, never as an error.
- **s5 [Minor]** `versedb.py:319`, `:322`, `:431-432`: a non-dict `name_i18n`, `aliases_i18n` or `meta` raises `AttributeError`; the comic records `error` and is retried every 1–6 hours on the same cached answer for up to 30 days. `versedb.py:260`: a 404 for one series' issues pauses all of VerseDB for 5 minutes on each retry of that comic. Treat an unexpected shape as no match and a 404 as an answer.
- **Inherited:** **M3 [Major]** `engine_host.py:182`.

### 4. Performance

- Status: Pass, conditional.
- **S3 [Major] — resolved in e714685** (see Round 2). The 30 s budget is shared by both fallbacks per pass; spacing (10–12 s) is below it, so every pass makes progress and no comic can be starved. Cover downloads still sleep 3 s inline outside the budget (at most two per comic). Each 60 s revisit re-runs the comic's local preamble (in-book check, approved-list cover hash when that list exists, evidence and record saves) — small per comic, but the 65% free-worker figure comes from a simulated clock. Before a switch goes on for real, Futaba or Ender should read pass times and worker share on the real machine, as the Brief row itself says.
- S2's new per-resource count adds one indexed-free query per ID-path reservation over at most a few hundred rows.

### 5. State & Data Safety

- Status: Concerns.
- **S1 [Major] — resolved in e714685** (see Round 2, including the live Metron and GCD offline paths).
- Ledger reservations are atomic across processes (`BEGIN IMMEDIATE`); the ID path's new refusal is a local wait and never writes `blocked_until`; status files go through `storage.save`. F3's trimming changes only values not yet written.
- **Inherited:** **N1 [Major]** `progress_snapshot.py:54`; **M2 [Major]** `archive_conversion.py:161`; **n1 [Minor]** `storage.py:88-95`.

### 6. Input Handling

- Status: Concerns.
- **s6 [Minor]** `tools/comicvine_would_write.py:27-28`, `tools/versedb_would_write.py:24-26`: "run it while the app's source is off" is still procedure only, though each tool holds `live_config` and could refuse when `sources.enabled` names its source. Same pattern as v0.6.4 n2.
- **Inherited:** **n2 [Minor]** `tools/metron_would_write.py` live `retry_at`/`last_request`; **i1 [Minor]** `local_model.py:99`.

### 7. Maintainability (no Critical findings on its own)

- Status: Concerns.
- **s7 [Minor]** `cover_match.py:161-183`: `archive_match` is a copy of `metron.verified_cover`'s loop, not shared with it; a change to one silently diverges the measured gates.

### 8. Doc/Code Drift (no Critical findings on its own)

- Status: Concerns.
- **s8 [Minor]** Round 1's items (a) and (c) are fixed (the name search's docstring and the Brief now describe S2's headroom, S1's gate and S3's pacing). Still open: (b) the Brief's name-search row says it writes "not Summary", yet the issue description goes to the synopsis model and `source_scheduling.useful` accepts a name-search result with no new field when the comic has no Summary, so a model-written Summary can follow (as on the ID path). New: the S1 Brief row says every switchable source is covered; see s10.
- **Inherited:** **n5 [Minor]** v0.6.4 doc items.

### 9. Build & Release Hygiene

- Status: Pass, conditional. `VERSION`, `package.json` and the lockfile still read 0.6.4 — this clearance assumes Sully's next commit changes only the version fields, lockfile and CHANGELOG (which should also name F2's stricter rule C, a behaviour change on a source that is on). `git diff --check` clean; no secrets in the diff or tests; the new modules are top-level `*.py` and ship, `tools/` does not; both sources ship off.

---

## Patterns

Round 1's pattern held: a switch has to gate every path a source's result can take to a write, not only the request, and the fix now does that for every source. What recurs is procedure standing in for a check the code could make (s6 here, n2 in v0.6.4).

---

## Verdict

- Total Critical: 0
- Total Major: 6, all inherited and untouched in range (N1, M1, M2, M3, I1, I2). Round 1's S1, S2, S3 and the inherited N2 are resolved.
- Total Minor: 17 (s1–s11, of which s8 is partly fixed; inherited n1–n5, i1)
- Safety floor: intact. No secret reaches a log, cache, evidence entry, exception or tool output; no shell-out; no write outside the state folder, the snapshot or the comics the pipeline already writes; N2's stray-file path is closed; no repository-integrity change.

**Verdict:** RELEASE CLEAR

Construction clearance for source commit 0b2c844 (range 445bd36..0b2c844) plus a version-and-changelog-only bump — not proof of installer behavior, the QA entry gate or publication. This supersedes the round-1 verdict for 0ca864e. For switch-on: S1, S2 and S3 are resolved in code; the one thing still owed before a switch goes on is a pass-time and worker-share reading on the real machine (S3's 65% is a simulation). No live state, live app, library, installer or provider API was touched by this review; test and probe scratch stayed in the repo's gitignored `scratch/` and was removed.

Built commit covered: v0.6.5 build `1ba12722da19630fd03cdc7111b21a667a1369c9` (version-and-changelog/docs only). Checked with `git diff 0b2c844 1ba1272`: between the reviewed source and it are only this review (fc37ac7, identical at 1ba1272), the docs-only merge of origin/main f0034b2 (five `Docs/` files: the v0.6.2 and v0.6.4 code reviews, the v0.6.4 release receipt and tray QA report, the 2026-11-15 scratch-cleanup record) and Sully's bump (`VERSION`, `package.json` and both `package-lock.json` version fields 0.6.4 → 0.6.5, CHANGELOG v0.6.5 naming the stricter rule C). No source, test, tool or build-config change.
