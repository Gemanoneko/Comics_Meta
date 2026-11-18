# Code Review — Comics Meta Organizer v0.6.5

## Header

```text
Reviewer: Senua (Code Reviewer)
Date: 2026-11-18
Tool: Comics Meta Organizer (Comic Metadata)
Release: v0.6.5 (version bump not yet made; Sully's version-only bump commit follows)
Commit range: 445bd36c79af3565f31ce1a66be4ee89466064c6 (v0.6.4)..0ca864e0037b99292d524c03b253b4c844f77a1d
Candidate commit: 0ca864e (ender/comicvine-name-search)
Files changed: 14 files, +2531 / -17 (product source: comicvine_search.py, versedb.py, cover_match.py, app.py,
               automatic.py, pipeline_config.py, source_scheduling.py; tools/comicvine_would_write.py,
               tools/versedb_would_write.py; tests; Brief)
Stand-down dimensions: none
```

---

## Summary

The range adds two opt-in fallback sources, both **off by default** (`pipeline_config.OPT_IN_SOURCES`): the ComicVine name search (after Metron and GCD offline miss; Metron's live identity rules; its own per-resource rolling-hour ledger `comicvine_requests`, 10 s spacing, 190 per resource from both paths) and VerseDB (after those and the name search; bearer token from the environment or `.env`; 280 per rolling hour, 12 s spacing; `!BD`-only no-year rule; French/English preference; Notes credit). Also: an additive `cover_match.archive_match`, the ID path's `reserve_request` now also logging its resource, long-miss scheduling for the two sources, two read-only "would write" tools, tests and Brief rows. Red-team focus per brief: wrong-write paths, token leakage, rate-limit math under concurrency, switch-off, path/URL escaping, API shapes crashing a worker.

Verified: `metron.py` and `cover_match.compare` are untouched (the cover helper is an additive copy, not a refactor), so Metron's behaviour cannot have changed; the name search's cache key builder and stored shape (`results`) are identical to `app.api`'s, requests with `field_list` get distinct keys, the 101 not-found entry uses the same prefix and format, and VerseDB's keys are namespaced `versedb:` — no cache poisoning path found; every new API parameter goes through `urlencode`, ids are `int()`-coerced, VerseDB paths are `fullmatch`ed, slugs are regex-checked, cover hosts are allow-listed with redirects re-checked, and the bearer token is sent only to `versedb.com` with redirects refused; no token or key reaches a status file, cache key, evidence entry, exception message (`from None`, fixed messages; the tools record only `type(exc).__name__`) or tool output; saved ComicVine keys stay DPAPI-encrypted outside the snapshot. Comics whose Web names a ComicVine issue are always excluded by `cites()`, so the fallback never meets the hold/conflict/strict paths. Lookup exceptions are caught by `research_runtime.first_verified` and recorded per comic; no worker crash path was found.

Targeted tests, run with the suite's isolation net loaded first and checked last (`test_0_state_isolation` … `test_zz_state_isolation`; `test_comicvine_search`, `test_versedb`, `test_source_switches`, `test_state_root`, `test_source_scheduling`, `test_enrichment_options_20261117`, `test_cover_match`, `test_metron_year_rules`): 153 run, 152 passed, 1 environment error — `test_state_root.test_every_process_derives_all_state_paths_from_the_root` starts `python -S`, and this review's system Python 3.14 keeps Pillow in site-packages (`ModuleNotFoundError: PIL` at `image_safety` import; unrelated to the range). Two probes, same isolation net, in the repo's gitignored `scratch/` (removed afterwards): the budget probe (S2) and the reuse probe (S1). `git diff --check` clean; no secret-shaped strings in the diff. No live state, live app, library or API was touched.

---

## Rubric

### 1. Security

- Status: Concerns.
- **N2 [Major, inherited, wider reach]** `tools/metron_would_write.py:91`: the unescaped `'file:' + path + '?mode=ro'` snapshot URI is not copied but **reused** by both new tools (`tools/comicvine_would_write.py:79`, `tools/versedb_would_write.py:87` call `shared.snapshot`). A `#`, `?` or `%xx` in `--live` or `%LOCALAPPDATA%` still opens a truncated path read-write and creates a stray file; the new tools then read an empty catalog and report pool 0. One fix in `snapshot` covers all three tools. Not triggered on Sergei's profile path; `tools/` is not packaged (`assemble-runtime.py` globs top-level `*.py`).
- Token and key handling pass (see Summary). The ComicVine key travels in the query string as on the ID path; the `HTTPError` that carries that URL is closed and suppressed (`from None`). No shell-outs; no Electron change in range.

### 2. Correctness & Logic

- Status: Concerns.
- **S2 [Major]** `comicvine_search.py:186` with `app.py:317-342`: the protection of the ID path is one-sided. The name search stops when both paths together reach 190 on a resource, but the ID path's `reserve_request` counts only its own 180 across all resources and never reads `comicvine_requests`. The dashboard's manual search (`app.py:1078`, `app.py:1086`) uses `search` and `issues` through the ID path, so after the name search has spent its 150, about 50 manual searches in the same rolling hour take the resource past ComicVine's 200. Probe (isolated state, real `reserve` / `reserve_request`): name search 150 `search`, then the ID path at 20 s spacing reserved 120 more — **241** `search` requests in one rolling hour. ComicVine's refusal then lands on the ID path's own request, and `app.api` sets the shared cooldown (`app.py:423` 5 minutes on HTTP 420; 1 hour on status 107), so every ID-path lookup and held comic waits, against the docstring's "cannot delay or use up the ID path" (`comicvine_search.py:26`) and the Brief. Likeliest in the 2–4 days after the switch goes on, when the name search runs at its allowance. Fix: have the ID path refuse a manual `search`/`issues` request (with a message) before both paths reach 200 on that resource, or lower the name search's `search`/`issues` share to what manual use cannot push over.
- **s1 [Minor]** `comicvine_search.py:358`: with no ComicVine key the name search returns `None`, which `source_scheduling.record` stores as a 30-day long miss; the rules stamp does not include the key, so comics touched while the key was missing are not asked again for 30–45 days after it returns. VerseDB reports the same situation as `unavailable` (`versedb.py:399-400`); the name search should too.
- **s2 [Minor]** `comicvine_search.py:368-371`, `:402`: `research.series_key` drops every non-ASCII character, so a series name with no Latin letters or digits has key `''`, every non-Latin ComicVine volume then counts as "the same name", and the detail re-check passes `'' == ''`; only the cover gate remains. VerseDB refuses this case (`versedb.py:133`); Metron has the same gap (`metron.py:176`). The language gate (`coverage_priority.language_eligible`) does not look at script.
- **s3 [Minor]** `comicvine_search.py:370`, `versedb.py:404`: uniqueness is established only within the first page (100 volumes; 50 series). The pilot measured it (31 of 43 pool accepts came from truncated first pages, all right) and lists "whether a second page would find exact-name volumes" as not verified. `request()` caches only `results`, so `number_of_total_results` is lost and the `name_search` evidence cannot show that a write came from a truncated list. Record a `truncated` flag in the evidence so a wrong write can be traced.
- **s4 [Minor]** `comicvine_search.py:411-413`: the name search writes the volume's Publisher for `!BD` comics too, while VerseDB withholds Publisher under `!BD` because those files are translations (`versedb.py:446`). The two sources disagree on the same folder (the pilot's two `!BD` accepts were Magnetic Press editions; the content language of `!BD` files is listed as not verified). Sergei's call; flagged so it is made once for both.
- **Inherited, unchanged in range:** **M1 [Major]** `app.py` case-sensitive scan range (now `app.py:295`); **I1 [Major]** `gcd_matching.py:128`; **I2 [Major]** `automatic.py` mixed-provider synopsis attribution (now `automatic.py:695`); **n3 [Minor]** `source_scheduling.py:216-219` errors count toward the long-miss streak; **n4 [Minor]** `source_scheduling.py:176-184` a rules-stamp change wakes every miss at once — it now applies to the two new sources' stamps as well, bounded by their allowances.

### 3. Crash / Stability Safety

- Status: Concerns.
- No worker crash path: lookups run inside `first_verified`, which records any exception against the comic; `fetch` maps HTTP, connection, timeout and JSON failures to `ProviderDeferred`; non-list answers are skipped by `isinstance` checks.
- **s5 [Minor]** `versedb.py:316`, `:319`, `:428-429`: a non-dict `name_i18n`, `aliases_i18n` or `meta` raises `AttributeError`; the comic records `error` and is retried every 1–6 hours on the same cached answer for up to 30 days (errors never take the long-miss path). And `versedb.py:257`: a 404 for one series' issues (a series removed while its search answer is cached) pauses all of VerseDB for 5 minutes on each retry of that comic. Treat an unexpected shape as no match and a 404 as an answer.
- **Inherited:** **M3 [Major]** `engine_host.py:182` (untouched).

### 4. Performance

- Status: Concerns.
- **S3 [Major]** `comicvine_search.py:229-232`, `versedb.py:220-223`: the pacing waits (10 s and 12 s between requests) are slept inline in the single discovery thread, inside a folder pass of up to 20 checked comics. At the pilots' rates (name search about 1.4 requests per comic; VerseDB about 2.8, fewer once a series' search answer is cached) a fresh comic that reaches both fallbacks costs roughly 25–50 s of sleep, so a 20-comic pass can take 10–17 minutes. VerseDB's allowance never releases the worker: 280 an hour at 12 s apart is 56 minutes of spacing, so while VerseDB comics are due the worker sleeps most of each hour on VerseDB alone, plus up to 25 min/h on the name search. Switching either on makes thousands of comics due once (VerseDB: 7,566 pass the gate), so this lasts about 1–3 days, during which Metron, GCD offline, new comics and writes get a small share of the worker. Not measured — arithmetic from the code's constants and the pilots' request counts; the Brief rows do not mention it. Metron already avoids this with `lookahead`. Fix options: when `reserve` asks for more than a few seconds, defer the comic (`unavailable` until then) instead of sleeping; or cap fallback asks per pass. Measure pass time with a switch on before it goes on for real.
- New SQLite work is small (a few unindexed queries over at most a few hundred ledger rows per reservation).

### 5. State & Data Safety

- Status: Concerns.
- **S1 [Major]** `automatic.py:420-424` (via `research_runtime.py:223-232`): switching a source off does not stop its **saved** results from being written. `research_runtime.reuse` returns a verified result saved within 30 days whenever the archive pages are unchanged and the comic's identity equals the identity before or after the write; `_discover` then drops it only for a GCD offline rules-stamp change or old Metron metadata, never for a switched-off source or a changed name-search / VerseDB rules stamp, and writes it. Probe (isolated state, `reuse` returning a VerseDB result as `remember` saves it, `"sources": {"enabled": []}`): `source_enabled('VerseDB')` False, 0 VerseDB requests, and a plan entry "Automatic verified lookup: VerseDB" with the VerseDB Web link. Path to harm: a wrong write from either new source → Sergei switches it off and restores the comic's kept backup (or the write failed) → the next pass writes the same result again, for up to 30 days. A RULES_VERSION bump meant to stop a wrong-match class is bypassed the same way. Both sources are off by default, so nothing in this release triggers it until a switch goes on; fix before then. Fix: beside the GCD offline check, drop reused evidence whose source is switched off or whose `name_search.rules` differs from the source's current `rules_stamp()` (the name search's results carry provider `ComicVine` plus a `name_search` key). The same reuse rule also applies to Metron and GCD offline when switched off (pre-existing).
- Ledger reservations are atomic across processes (`BEGIN IMMEDIATE`, spacing read from the ledger); status files go through `storage.save`; damaged status JSON reads as no wait. The tools write their ledger, cache and status only into `<out>/state`.
- **Inherited:** **N1 [Major]** `progress_snapshot.py:54` dashboard read path writes on restore; **M2 [Major]** `archive_conversion.py:161`; **n1 [Minor]** `storage.py:88-95` stale `.bak` after a deleted file (all untouched).

### 6. Input Handling

- Status: Concerns.
- External inputs are handled (see Summary: `urlencode`, `int()` ids, `PATHS.fullmatch`, slug regex, image host allow-lists, size caps on answers and covers).
- **s6 [Minor]** `tools/comicvine_would_write.py:27-28`, `tools/versedb_would_write.py:24-26`: "run it while the app's source is off" (the copy's ledger is invisible to the app, and both share the provider's hourly limit) is procedure only, although each tool already holds `live_config` (`:73`, `:81`) and could refuse when `sources.enabled` names its source. Same pattern as v0.6.4 n2, still open for the Metron tool.
- **Inherited:** **n2 [Minor]** `tools/metron_would_write.py:195-219`; **i1 [Minor]** `local_model.py:99`.

### 7. Maintainability (no Critical findings on its own)

- Status: Concerns.
- **s7 [Minor]** `cover_match.py:161-183`: `archive_match` is a second copy of `metron.verified_cover`'s comparison loop (`metron.py:107-126`), not shared with it; a later change to one silently diverges the measured gates. Have Metron call `archive_match` (under a test that pins Metron's results), or note the twin in both docstrings.

### 8. Doc/Code Drift (no Critical findings on its own)

- Status: Concerns.
- **s8 [Minor]** (a) `comicvine_search.py:25-27` and the Brief's name-search row say the name search "cannot delay or use up the ID path" — see S2. (b) The Brief's name-search row says it writes the ID path's fields "not Summary"; the issue description it keeps as source text still goes to the synopsis model, and `source_scheduling.useful` accepts a name-search result with no new field when the comic has no Summary and the description has 20+ words, so a model-written Summary can follow (as on the ID path). (c) Neither Brief row mentions the inline pacing cost (S3) or that saved results outlive the switch (S1).
- **Inherited:** **n5 [Minor]** v0.6.4 doc items (untouched).

### 9. Build & Release Hygiene

- Status: Pass, conditional. `VERSION`, `package.json` and the lockfile still read 0.6.4 — this clearance assumes Sully's next commit changes only the version fields, lockfile and CHANGELOG. `git diff --check` clean; no secrets in the diff or tests (synthetic tokens only); the two new modules are top-level `*.py` and ship with the runtime, `tools/` does not; both sources ship off.

---

## Patterns

Second review in a row where a read-only tool's safety rests on "run it while the app is …" in the Brief instead of a check the tool could make itself (v0.6.4 n2, now s6). And the release's main safety story — "off by default, switch it off after a wrong write" — holds for new asks but not for evidence already saved (S1): a switch should gate every path a source's result can take to a write, not only the request.

---

## Verdict

- Total Critical: 0
- Total Major: 10 (new S1, S2, S3; inherited N1, N2, M1, M2, M3, I1, I2)
- Total Minor: 14 (new s1–s8; inherited n1–n5, i1)
- Safety floor: intact. No secret reaches a log, cache, evidence entry, exception or tool output; no shell-out; no write outside the state folder, the snapshot or the comics the pipeline already writes; N2 (stray file on a URI-metacharacter path, tools only, not shipped) unchanged in kind; no repository-integrity change.

**Verdict:** RELEASE CLEAR

Construction clearance for source commit 0ca864e plus a version-and-changelog-only bump — not proof of installer behavior, the QA entry gate or publication. Both new sources ship switched off, so S1–S3 cannot act until Sergei switches one on; S1 and S2 should be fixed, and S3 measured, before either switch goes on. No live state, live app, library, installer or provider API was touched by this review; test and probe scratch stayed in the repo's gitignored `scratch/` and was removed.
