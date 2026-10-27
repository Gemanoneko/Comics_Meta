# Code Review — Comics Meta Organizer v0.5.0

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-27
Tool: Comics Meta Organizer (comic-metadata)
Release: v0.5.0
Commit range: e793693..e0c4a69
Files changed: 46 files, +1907 / -55 (product code: 21 files, +473 / -38; tests: 15 files, +770 / -10; the rest docs and version files)
Stand-down dimensions: none
```

`30263f0` landed on `main` while this review ran. It changes only `tests/test_state_root.py`, `tests/test_identity_conflict_summary.py` and two Docs files, with no product code, so it changes nothing this review certifies.

---

## Summary

The range is Enrichment A–E (`668a141`) and the 0.5.0 bump (`e0c4a69`), plus one docs commit (`7bcd05c`):

- **A:** refinement turns (`scheduler.select`, `coverage_priority.refinement_folder`), and an `unsearchable` stamp that stops re-asking comics no source can search.
- **B:** years from file-name dates and the folder (`year_hints.py`, `metron.identity`).
- **C:** an unnumbered book is searched as issue 1 of a one-shot, graphic novel or collection.
- **D:** a looser cover comparison (`cover_match.py`) that tries archive pages 1–3.
- **E:** five sources switched off, and their screens hidden.

I read every changed product line, and I traced the scheduler and `due()` paths by hand. I checked B, C and D with probes in my scratch folder:

- year parsing on 14 file names and 9 folders;
- `unnumbered_book` on 11 names;
- `cover_match` on blank, black and tiny images and on decode failures;
- an EPS-in-archive probe, which intercepts Ghostscript and never runs it;
- the `unsearchable` fingerprint with Lens off and on.

Every probe used synthetic data under the scratch state root.

I found **one Critical**, on the safety floor. Archive pages can reach Ghostscript 10.03.1 through Pillow. The exposure existed before this release, and 0.5.0 widens it. The fix is a one-line allow-list at each of seven call sites. I also found three Majors and ten Minors.

**Not reviewed or not run:**
- the live catalog, Metron's real API answers (for example whether issue lists carry `series.year_began`) and real covers, which are off-limits or offline;
- the desktop Node suite, which `npm run check` never reached (see dimension 9);
- an actual Ghostscript exploit, which I did not attempt.

Ender's entry log is at `C:\Antigravity Projects\Worktrees\Comics Meta Organizer\qa-050b\logs\`, not `qa-050`. It covers `30263f0`. Its remaining `test_state_root` error is a different test (`StateRootSelectionTests`, a `-S` subprocess). That test failed the same way in the 0.4.0 run (`qa-040b`).

---

## Rubric

### 1. Security

- Status: Fail (F1).
- **F1 [Critical, safety floor: machine harm] Archive pages reach Ghostscript.** `cover_match.py:78` and `automatic.py:55` call `Image.open()` on archive and downloaded bytes with no `formats=` allow-list.
  - **How it happens.** Pillow chooses the decoder from the content, not from the `.jpg` name. So a page that holds PostScript opens as EPS, and decoding it launches Ghostscript.
  - **Why it is reachable here:**
    - Ghostscript 10.03.1 is on this machine's PATH (`C:\Program Files\gs\gs10.03.1\bin\gswin64c.exe`).
    - The packaged engine passes PATH to its children (`desktop/engine.cjs:29`, `env:{...process.env,...}`).
    - The packaged runtime ships `PIL/EpsImagePlugin.py` (`dist/win-unpacked/resources/runtime/python/...`).
  - **Probe** (`subprocess` intercepted, Ghostscript never ran). A `.cbz` with a non-matching cover as `000.jpg` and a six-line EPS as `001.jpg`, run through `metron.verified_cover`, gave one launch of `gswin64c ... -dSAFER -sDEVICE=pnmraw`.
  - **Why `-dSAFER` does not protect.** Ghostscript 10.03.1 predates the 10.04.0 security release. That release's advisories include code-execution bugs reachable from PostScript input, for example CVE-2024-46951 and CVE-2024-46956.
  - **Why it matters.** The library is comics downloaded from the internet.
  - **What 0.5.0 changes.** The exposure already existed: 0.4.1's `covers_agree` decodes page 1, and five other call sites decode pages too. 0.5.0 adds `cover_match.agree` and decodes pages 2–3 of every comic that Metron finds a candidate for.
  - **Fix:** see the Verdict table.
  - **Aside for Sergei, not code:** updating Ghostscript on this machine reduces the risk for every program that uses it.
- **m1 [Minor] Lens verification can be requested while Lens is off.** `lens_verification.request()` (`lens_verification.py:120`) does not check `lens_on()`.
  - The stored `human_verification` is kept on purpose while Lens is off. So `POST /api/browser-resume` still queues a request, and the idle worker ignores it.
  - When Lens is switched back on, that stale request opens the Lens window at once.
  - The dashboard hides the button, so only a stale page or a direct call can reach this. Refuse the request while Lens is off.
- **m2 [Minor] Cover reads block renames and deletes.** `reverse_image.cover` (`reverse_image.py:40`) opens the archive with plain `zipfile.ZipFile(path)`. On Windows that handle lacks `FILE_SHARE_DELETE`, so another program's rename or delete fails while the read lasts.
  - This existed before 0.5.0.
  - D now opens each archive up to 30 times per comic: 3 pages × (preview + detail + 8 variants).
  - `reverse_image.open_shared` already exists for this. Each read is still read-only and bounded.
- **Checked and clear:**
  - Archive reads are read-only and bounded to 20 MB of stored or deflated data per page (`read_image`).
  - Entry names are only sorted and suffix-checked, never used as paths, so a zip entry that points outside the archive has nothing to escape.
  - Every new DOM string goes through `textContent`. `reverse-image.js` sets a constant `innerHTML`.
  - No new IPC channel, shell-out, delete or credential. `setup-status` passes the engine's answer through.
  - The Google Books key: see dimension 5.

### 2. Correctness & Logic

- Status: Concerns.
- **F2 [Major] Switching Lens back on never reaches comics marked unsearchable.**
  - **Cause.** `source_scheduling.search_fingerprint` (`source_scheduling.py:77`) is built from the rules stamp and the switched-on sources in `KEYS`. Lens is in neither.
  - **Probe.** The fingerprint is identical with `browser_search.lens` false and true.
  - **Effect.** A comic marked `unsearchable` while Lens is off returns not-due at `source_scheduling.py:92` forever. So `queue_cover_search` (`automatic.py:296`) never runs for it.
  - **Who is affected.** These are exactly the comics with no searchable text identity, which is what a cover search is for. The Brief counts 9,816 such comics on one day (2026-10-21).
  - **Mismatch with the docs.** The Brief's Decision Log promises a wake-up when "the switched-on sources" change.
  - **Fix:** add the Lens switch (`pipeline_config.lens_enabled()`) to the fingerprint, with a test.
- **m3 [Minor] Comparisons multiply with D.** D compares up to 3 archive pages with up to 10 Metron covers (preview, detail and 8 variants): 30 chances to pass a looser rule.
  - The Brief's hard-negative set (0/1,228) does not say whether it covered pages 2–3 or variant covers.
  - The near-blank guard, unchanged, lets logo-on-white pairs through under both rules. In a synthetic probe, a title page with a logo band against a blank sketch variant gave True under both `covers_agree` and `agree`. Metron lists such variants.
  - **Fix:** measure the 3 × 10 family-wise rate, or skip variants that fail a stronger detail test.
- **m4 [Minor] `folder_year` lacks the guard Sergei ruled for GCD.** Sergei ruled a ±1-year same-name guard for the GCD pilot. The example was Savage Sword of Conan matching the Marvel UK weekly.
  - Metron's `folder_year` (`metron.py:253`, `year_agrees`) has no such guard. Only the cover check, now looser, stands between them.
  - Reprint runs often reuse the original cover art.
  - **Fix:** apply the same skip.
- **Checked and clear:**
  - **Scheduler.** No starvation or livelock:
    - a refinement turn follows only a first-update pass that found work, and it falls through when it finds none;
    - "never refined since the last write" rows are always due, so they cannot pin the 64-row probe;
    - a finished refinement pass delays its folder by at most 10 minutes (`scheduler.finish`).
  - **Metron re-ask under new rules.** The rules stamp is written in `completed()` (`automatic.py:433`), the only writer of `source_schedule`. So "asked once more" happens once.
  - **B and C still need everything they needed before:** a unique candidate, a truncated list failing closed, the detail re-check, the series-type gate for C, and cover agreement.
  - **D fails closed** for all-black, blank, 1×1, 2×1 landscape and 4×6 images (probe).

### 3. Crash / Stability Safety

- Status: Concerns.
- **F3 [Major] A bad page 2 or 3 turns a miss into a repeating error.**
  - **Cause.** `metron.verified_cover` (`metron.py:111-116`) catches only `ValueError` from `reverse_image.cover`. Any decode failure on page 2 or 3 escapes `cover_match.agree`:
    - a truncated JPEG raises `OSError`;
    - a non-image raises `UnidentifiedImageError`;
    - a bad CRC raises `zipfile.BadZipFile`;
    - a page over about 179 MP raises `DecompressionBombError`.
  - **Probe.** Page 1 was a non-matching cover and page 2 was truncated: the call raised. With `cover_rule_v2` switched off, the same archive returned False.
  - **Effect:**
    - The Metron lookup stops before the variant covers are tried.
    - `source_scheduling.record` files the failure as `error` (probe). `due()` wakes the comic again after 1, 2, 4, then every 6 hours.
    - Each retry downloads the Metron cover again, because cover downloads are not cached.
    - Truncated JPEGs are common in scanned archives.
  - **Fix:** on pages 2–3, treat any exception as "no match" and keep page 1's current behaviour.

### 4. Performance

- Status: Concerns (Minor only).
- **m5 [Minor] Each refinement turn reads every written comic.** `coverage_priority.refinement_folder` (`coverage_priority.py:168`) reads every written comic in scope (`c.*` with metadata, plus `json_extract` on each discovery record), with no `LIMIT`. That happens every other folder selection.
  - The first-update probe was cut to 256-row slices for this reason; its docstring records 13.8 s per probe before.
  - I did not measure it: the live catalog is off-limits. About 10,500 or more written comics will be read.
- **m6 [Minor] Repeated decodes and config reads.**
  - **Decodes.** `verified_cover` reopens the archive and decodes each page twice, once in `covers_agree` and once in `agree`, for every remote cover. That is up to 60 full-resolution decodes for one comic. Caching the 3 local pages per lookup, or a `draft()` decode, would cut it.
  - **Config reads.** `metron.identity` reads and parses `config.json` up to 4 times per call. It now runs per row in `order_rows` ranking and in the lookahead.

### 5. State & Data Safety

- Status: Concerns.
- **F4 [Major] Writes accepted only by the new comparison leave no trace.** `metron.py:324` records `match_rule` (B/C) only. `verified_cover` returns a bare bool.
  - So a write accepted only by D cannot be told apart from one today's rule accepted. D accepts by an aligned crop, a wraparound half, or page 2 or 3.
  - D is the largest loosening measured: single-candidate rejections accepted went from 3/706 to 455/706, with no ground truth for the 455.
  - The Decision Log's revisit trigger is "a wrong write is reported". Without this record, that trigger cannot be scoped to D's writes.
  - **Fix:** record which comparison passed and which page matched, beside `match_rule`, in the evidence and the plan entry.
- **Checked and clear:**
  - Nothing in the range deletes anything.
  - Hiding the Google Books row keeps the saved key: `save` and `save_keys` merge with `saved.update(replacements)`.
  - The page receives only key names and booleans.
  - `sources.enabled` restores a source cleanly, and it wakes unsearchable comics, because those sources are in the fingerprint.
  - `enabled` on `/api/browser-verification` is computed by the server from `config.json`, so it is right when the worker is down.

### 6. Input Handling

- Status: Concerns (Minor only).
- **m7 [Minor] Some year ranges are read as cover years.** `year_hints.YEAR_WITH_WORDS` (`year_hints.py:18`) reads a range that is followed by words as its start year:
  - `(1993 - 1995 Dark Horse)` gives 1993;
  - `(1993- 1995, Dark Horse)` gives 1993;
  - `(1999 - 2000 printing)` gives 1999.

  `\s*` can match nothing, which lets the year look-ahead pass on the space. The docstring says ranges are never read. Separately, `(2010-12)` reads as December 2010 although it can be a 2010–12 run. A wrong year mostly fails closed: the exact cover-year match misses.
- **m8 [Minor] Roman numerals and number words count as unnumbered.** `metron.unnumbered_book` (`metron.py:193`) treats `Star Wars - Episode IV (1977)` and `Batman One Hundred (2010)` as unnumbered. Its docstring says "no number of any kind". The series-type gate and the cover check still apply.
- **Checked and clear:**
  - `(2007-02)`, `(2007-02-15)`, `[2004]`, `(1993-1995)` and `(1993-95)` behave as documented, and `2099` / `2000 AD` are never read.
  - Folder years from `(1994-1996)`, `(1992-)` and `(1994 - )` give the start year, and two bracketed years give none.

### 7. Maintainability (no Critical findings on its own)

- Status: Concerns (Minor only).
- **m9 [Minor] Hand-copied gates and duplicated helpers.**
  - `source_scheduling.can_search` (`source_scheduling.py:48`) copies each lookup's early gate by hand. If one lookup later loosens its gate without a matching change here, or without a `MATCHER_VERSION` bump, comics stay unsearchable without any sign. A note at each gate, or one shared predicate, would stop that drift.
  - `cover_match._detailed` and `_correlation` duplicate `automatic.detailed` and the nested `correlation`.

### 8. Doc/Code Drift (no Critical findings on its own)

- Status: Concerns (Minor only).
- **m10 [Minor] Four places where the docs and the code disagree:**
  - `year_hints.py:4` names `metron.identity_year`, which does not exist (it is `metron.identity`).
  - The `metron.lookup` docstring (`metron.py:268`) says cover agreement is required "exactly as before", but D loosened it.
  - The `metron.py:323` comment says writes under a looser rule "can be found", which is not true for D (F4).
  - The Brief's "Unsearchable comics" row says the stamp wakes when "the switched-on sources" change, which is not true for Lens (F2).

### 9. Build & Release Hygiene

- Status: Pass.
  - `VERSION`, `package.json` and `package-lock.json` all move to 0.5.0 in one commit (`e0c4a69`).
  - CHANGELOG has a v0.5.0 entry.
  - No secrets were added.
  - In the entry run, `check:shell` did not run, because `check:python` failed: known Backlog item 5. No desktop `.cjs` file changed in this range. `desktop/setup.js` is covered by the Python DOM tests (`test_sources_off_dom`), which passed.
  - The entry check runs its tests with a Python from `scratch/cmo-packaging-recovery-20261015/...` inside the tool folder. If that folder is ever swept, the entry check breaks.

---

## Patterns

Pillow is called on untrusted bytes without a format allow-list in seven places. The one place written with a safety review in mind (`reverse_image.thumbnail`, from the cover-preview work) restricts formats. The others predate that and were never brought in line. Two other details of 0.5.0 have the same shape: the "never re-ask" fingerprint and `can_search` both copy facts from elsewhere by hand. Each copy is a place where drift silently strands comics.

---

## Verdict

- Total Critical: 1
- Total Major: 3
- Total Minor: 10

**Verdict:** RELEASE BLOCKED

| # | Sev | Dim | file:line | Finding | Must fix before release |
|---|-----|-----|-----------|---------|--------------------------|
| F1 | Critical | 1 Security (safety floor) | `cover_match.py:78`, `automatic.py:55` (start); also `local_model.py:107`, `:199`, `:227`, `browser_search.py:72`, `archive_conversion.py:107` | Archive or downloaded bytes open with no format allow-list, so a page holding PostScript launches Ghostscript 10.03.1, which is on PATH (probe confirmed the launch). | Pass `formats=('JPEG','PNG','WEBP')` at every listed site (`'GIF'` too in `archive_conversion`), as `reverse_image.py:135` already does. Add one test: a `.cbz` with PostScript as page 2 gives no match and launches no Ghostscript. |

Majors and Minors for Ender's next cycle: F2 (fingerprint omits Lens), F3 (page 2/3 decode errors), F4 (no record of D-accepted writes), m1–m10.
