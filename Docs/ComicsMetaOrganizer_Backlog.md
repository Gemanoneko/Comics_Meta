# Comics Meta Organizer — Backlog

Items Sergei has approved for a future version. Not started unless marked.

## Next version

### False "GPU release could not be confirmed" when Ollama is off (Sergei, 2026-10-24)
- **Seen in:** v0.3.0, while paused. The banner reads "Workers paused, but Gemma GPU release could not be confirmed. Retrying." It never clears.
- **Cause (Jane's read, not yet confirmed by Ender):** `pause_control.unload_model()` asks Ollama to unload Gemma. With Ollama not running, the request fails, and `checkpoint()` turns any exception into this error ([pause_control.py:184-188](../pause_control.py)). It retries about every 10 s, and every retry fails the same way.
- **Wanted (Sergei):** if Ollama isn't running, count that as "GPU released". No false alarm.
- **Also check (Sergei's question):** what the app does when it is resumed with Ollama off. Sergei resumed on 2026-10-24 and couldn't tell what the app was doing. The app never starts Ollama itself. `local_model.available()` returns False, and credits reading returns None when the model call fails. Find out whether Gemma-dependent comics get skipped, retried later or marked as failed, and whether the dashboard should say "Ollama not running".
- **Owner:** Ender (fix). Judy reviews any new dashboard wording. Futaba verifies.

### App starts and stops Ollama itself (Sergei, 2026-10-24)
- **Wanted (Sergei):** the app starts Ollama when it needs Gemma and stops it again. Sergei shouldn't have to start Ollama by hand.
- **Stop timing (Sergei):** stop Ollama when the app quits. Pausing doesn't stop Ollama; it only unloads Gemma, as today.
- **Stops it even if Sergei started it (Sergei):** on quit, the app stops Ollama even if Sergei started Ollama himself.
- **Owner:** Ender. Judy reviews any status wording. Futaba verifies. Our tooling never steals focus (ProcessRules § Desktop App / GUI Rules), so Ollama has to start hidden.

### Update statistics graph above Live library (Sergei, 2026-10-26) — shipped in 0.4.0
- **Wanted (Sergei):** a graph above the Live library panel showing how many comics the app updated in a period.
- **Periods (Sergei):** since counting began, calendar year, calendar week, calendar day, last hour, and a custom from–to date range. **Default: the current calendar day.**
- **Count unit (Sergei):** distinct comics, not write events. A comic written several times in a period counts once.
- **Breakdown (Sergei):** total only. No split by source.
- **Week start (Sergei):** Monday.
- **Scope (Sergei):** live library only.
- **Existing "Updated by this app" counter (Sergei):** keep both numbers. Judy relabels them so the difference is clear: the counter is the comics in that state now, while the graph is every comic the app wrote in the period.
- **Data (Ender's read-only check, 2026-10-26):** the `history` table already stores a timestamp for every successful write since the first commit and is never pruned. So "since counting began" starts at the earliest history row and includes past updates. "Last hour" is a rolling 60 minutes. Day, week and year boundaries are local time.
- **Owner:** Judy specs the graph, labels and period picker first. Ender builds it. Futaba verifies. Senua reviews. Sully releases.

### 0.4.1: update statistics fixes (Sergei, 2026-10-26) — shipped in 0.4.1 (22fcbf2), except Senua m2 / QA-4 (daylight saving in past years), which was skipped: it needs IANA time-zone data in the runtime
- **Decided (Sergei):** 0.4.0 ships as is, and these go into 0.4.1 as one batch.
- **Count can be one short (Senua M1, Major):** in `update_stats.py`, `now` is taken before the history id is read. A write that lands in between is left out of the count, and the result is cached that way until the next write. Fix: take `now` after the id, and bound both queries by that id.
- **Slow long periods (Futaba QA-2):** cold Year, All time and Custom-from-2000 take 1.4–2.7 s on 200,000 history rows, against the brief's 0.22 s. The count is recomputed on every 15 s refresh while writes happen.
- **Future rows (Futaba QA-3):** `first_at` and `last_at` ignore the "now" cutoff, so a row dated in the future can show as the last update.
- **Minor, fix if cheap:**
  - Senua m1 / QA-6: a missing custom date returns the wrong message.
  - Senua m2 / QA-4: the Windows C library applies the wrong daylight-saving rules to past years; the first affected date is in 2028.
  - Senua m3: the docstring says "read-only", but the endpoint takes the write lock.
  - QA-1: the tooltip is too wide at 320 px in non-English locales.
  - QA-5: the README and CHANGELOG don't describe the panel or the relabels.
- **Sources:** `Docs/ComicsMetaOrganizer_CodeReview_v0.4.0_2026-10-26.md`, `Docs/ComicsMetaOrganizer_QA_v0.4.0_2026-10-26.md`.
- **Owner:** Ender fixes. Futaba checks what changed. Senua reviews. Sully releases.

### Install offer reappears during pause-and-install (Sergei bug, 2026-10-26) — fixed in 0.4.1 (b4f022d)
- **Repro (Sergei, 0.3.0 → 0.4.0):** he checked for updates and pressed Install, then "Pause and install". The Install button came back. The install itself carried on and succeeded; 0.4.0 is running.
- **Root cause (Ender):** `desktop/updates.cjs:56` puts the update state back to `'ready'` as soon as "Pause and install" is pressed, and `static/shell-ui.js` draws `'ready'` as "Install and restart". The DesktopShell spec §4 "After confirm" says "Banner returns to Ready underneath", which is now out of date.
- **Fix (Ender, b4f022d):** a new `'parking'` state. The banner shows a waiting status with no buttons, Check for updates and API keys are disabled, and the tray says "Installing update…".
- **Wanted (Sergei):** no second install offer. Show a waiting message instead, something like "Please wait while we park the process and install the new version". Judy sets the final wording.
- **No Cancel on the waiting message (Sergei):** cancel stays in the Installing window.
- **Timeout message says why (Sergei):** after the 10-minute timeout, the banner says that processing didn't pause in time, not just "did not start".
- **Lock "Pause & release GPU" (Sergei, ruled "Yes, lock it"):** the dashboard's "Pause & release GPU" button is disabled from the press of "Pause and install" until the app restarts, so a stray click can't leave a user pause behind. Ender confirms it is feasible.
- **Copy:** Judy's revision of the DesktopShell spec §4 (2026-10-26) has the final wording.
- **Note:** the running version drives its own update, so the 0.4.0 → 0.4.1 update will still show the old button once.
- **Owner:** Judy sets the copy, the spec row and focus. Ender fixes. Futaba verifies, including the tray tooltip.

### "This month" period in update statistics (Sergei, 2026-10-26) — shipped in 0.4.1 (5f41744)
- **Wanted (Sergei):** add a "This month" period to the update statistics panel, as seen on the running 0.4.0.
- **Rule (by analogy with Sergei's other rulings):** the current calendar month in local time. Judy specs placement, bar unit and copy.
- **Owner:** Judy specs. Ender builds it in the same batch as the updater bug and the 0.4.1 fixes. Futaba verifies.

### Enrichment effectiveness, A–E (Sergei, 2026-10-26)
- **Source:** `Docs/ComicsMetaOrganizer_EnrichmentDiagnosis_2026-10-26.md` (Ender). Nothing is broken; the easy matches are used up. About 30,000 comics remain, and about 3,000–5,500 more look matchable.
- **Approved (Sergei, "yes" to each):**
  - **A:** give refinement a fixed share of passes, and stop re-asking comics no source can search.
  - **B:** match comics with no printed year: more year formats, searching without the year, or the folder's year.
  - **C:** treat an unnumbered book as issue #1.
  - **D:** audit the cover comparison, and loosen it where the evidence supports that. Sergei accepts that it may get looser.
  - **E:** switch off the zero-yield sources (GCD, Dark Horse, Google Books, Open Library) and Lens.
- **Research (Sergei, "Absolutely"):** Makoto looks for new sources, starting with an offline GCD data dump.
- **Open:** the catalog holds 40,207 comics, while Sergei's library may be about 60,000. Check whether files never reach the catalog.
- **Owner:** Ender builds A–E in one batch. Futaba checks what changed. Senua reviews. Sully releases. Makoto researches.

### GCD data dump as an offline source (Sergei, 2026-10-27) — 0.6.0 batch PARKED, not started in code
- **Parked 2026-10-27:** Sergei paused until the token reset. Done so far:
  - **UI brief:** written as `Docs/ComicsMetaOrganizer_GCDOffline_UIBrief_2026-10-27.md`. Judy has not started.
  - **Engine design:** settled by Ender, see "Next session" below. No code exists yet.
  - **Pilot scripts:** saved in `tools/gcd_pilot/`. They hold the exact matching rules to port.
- **The 0.6.0 batch:**
  1. The GCD offline provider.
  2. Language tags: `[rus]`, `(rus)` and other languages, for all sources.
  3. The conversion-leftover cause and the 19 CBR files.
  4. Senua's m12 (GIF/BMP cover allow-list) and m11 (disable Pillow's Ghostscript/EPS plugin at startup).
  6. **Bug: a manual ComicVine pick doesn't stick** (Sergei, 2026-10-27, on 0.5.0).
     - **Repro:** Critter (`8 / 2025`) shows "Needs a check: ComicVine issue 1117156 is Critter #7; the file says Critter #8." Sergei picks the correct ComicVine issue manually. The row leaves the list, then comes back a few seconds later with the same check.
     - **Expected:** a manual pick settles the conflict for good, until the file changes.
     - **To find:** whether the pick isn't saved or written, whether the next research pass or the 2 s poll rebuilds the conflict from the old ComicVine id in the file or in evidence, or whether the A–E refinement turn re-raises it.
     - **Fix:** root cause in the commit message, plus a test that fails first.
  5. **The build toolchain must be rebuildable** (Sergei, 2026-10-27: "Fold to 0.6.0").
     - Today `scratch/cmo-packaging-recovery-20261015/` (858 MB, gitignored, on this machine only) is the only installer toolchain, and the entry check's test Python lives in it. See the Brief's "Do not delete" note and Senua's v0.5.0 note.
     - Make it reproducible on either machine: a pinned download plus a build script, or another route Ender picks.
     - Prove that a clean rebuild produces a working installer, then delete the folder. Sergei wants it gone.
     - Update the Brief's "Inputs" section.
     - This also helps the entry-check repair item, which needs a pinned test Python.
- **Next session:**
  1. **Judy:** one pass on the UI brief. It includes one open question for Sergei: a "dump is old" reminder after N days.
  2. **Ender:** port `tools/gcd_pilot/pilot.py` (`match_guarded`, `gcd_fields`, guard G5) and `build_index.py` into a new `gcd_offline.py`:
     - each index is written under a new name and a pointer is switched to it;
     - the rules stamp includes the dump date;
     - it runs after Metron in `automatic.py` (around line 509);
     - the Notes attribution is added around line 645;
     - a GTIN-count table;
     - build progress and cancel;
     - a free-disk-space check (about 7.5 GB);
     - the endpoints from the UI brief and a desktop file-picker call.

     Then items 2–4, failing tests first.
  3. **Ender:** re-measure the per-rule counts on a fresh read-only snapshot against the pilot's 12,689.
  4. **Then:** the entry check, Futaba and Senua, and Sully releases 0.6.0.
- **Check in the build:** Ender reads "skip Star Wars Legends Marvel reissues" as skipping Dark Horse matches inside a `Star Wars Legends` folder. This is not yet measured, so confirm it covers the 217 files.
- **Source:** `Docs/ComicsMetaOrganizer_GCDTrial_2026-10-26.md` (Ender). Sergei downloads `current.zip` from comics.org himself, about every 2 weeks (CC BY-SA 4.0). The dump has no covers.
- **Rulings (Sergei, "yes" to each):**
  1. A single GCD match on series + number + year counts as verified, with no cover check.
  2. The year may come from the folder or the file name.
  3. Comics with no year, no number, or collected volumes may also match. The trial measured 1–7% wrong for these.
  4. GCD synopses feed the existing synopsis review.
  5. Pilot first: Ender produces a read-only "would write" list, Futaba samples it, and only then do writes start.
- **Pilot result (2026-10-27):** GCD would write to 12,689 of the 30,094 unmatched comics. The sample is in `Docs/ComicsMetaOrganizer_GCDPilot_Sample_2026-10-27.md`, and Futaba is checking it.
- **Pilot rulings (Sergei, 2026-10-27):**
  - Keep the guard that skips file names made only of a number, unless the folder confirms the title.
  - When a Series was read from the cover and GCD only adds "The" or a prefix, keep the cover's Series.
  - Skip folder-year matches where a same-name series starts one year earlier or later. Example: Savage Sword of Conan matched the Marvel UK weekly.
  - Never let GCD replace a Publisher that was read from the cover.
- **Futaba's sample check (2026-10-27): GO.** 2 of 200 random rows were wrong (1.0%; 95% upper bound 3.1%). The verdicts are in `Docs/ComicsMetaOrganizer_GCDPilot_Sample_2026-10-27.md`.
- **Rulings after the sample (Sergei, 2026-10-27). Two of these reverse rulings above:**
  - **Star Wars Legends Marvel reissues (about 217 files):** skip them. Don't tag them with the Dark Horse original.
  - **Same-name series one year off:** allow these matches. This reverses the earlier skip; all six sampled rows were right.
  - **Publisher:** GCD may replace a Publisher read from the cover. This reverses the earlier "keep the cover's Publisher"; all 19 replacements were right.
  - **Count:** when a file name says "(of N)" and GCD disagrees, write the file name's N.
- **Holds adopted from Futaba (they make writing more careful):**
  - Don't write unnumbered or collection rows whose name contains `(Complete Vol)`, `N of M` or a doubled bracket until the parser reads those names correctly.
  - Don't write a GTIN that more than one GCD issue shares (51% of GTINs are series-level codes).
- **Known gap:** untagged Russian scans, such as the Han Solo folder, aren't caught by the language-tag fix. A real match can also look unique when the true record is filed under another name (the X-Files Topps / Trielle case).
- **To settle at build time:**
  - a publisher alias table (GCD uses short names such as "DC" and "Titan");
  - the free-text fields that are left out: Characters, Genre, Day, AgeRating and Format.
- **Language bug:** the language-tag bug also misses `(rus)` in round brackets. See the entry below.
- **Licence:** credit GCD in Notes with its issue link, and never commit the index.
- **Owner:** Ender (pilot, then build), Futaba (samples the pilot), Senua, Sully.

### Square-bracket language tags are missed (Sergei approved logging, 2026-10-27)
- In the GCD trial, two `[rus]` files matched the English issue: the app's language rule misses tags in square brackets. It also misses `(rus)` in round brackets, because only `(ru)` is listed. The pilot found 193 square-bracket files and 22 round-bracket ones. This affects every source, not only GCD.
- **Owner:** Ender, batched with the next change.

### Leftover conversion folder in the library (found 2026-10-27)
- `Y:\Comix\!Titan Comics\The Michael Moorcock Library\Michael Moorcock's Multiverse 01-12\.comic-metadata-convert-3cf321636f084dc88e78deeaa54569ed\` held 25 JPGs of issue #010, left by a CBR-to-CBZ conversion that didn't clean up. The real `Michael Moorcock's Multiverse 010.cbz` sits beside it, intact.
- **Deleted 2026-10-27 at Sergei's request** ("Just delete this"). Jane removed the 25 files and the 2 empty folders with literal `rm`/`rmdir`, after confirming the .cbz was present.
- **Still open:** the cause, which was not investigated before deletion. Ender also found 19 CBR files that aren't in the catalog. Find out why conversion can leave its staging folder behind, and whether it is related to those 19.
- **Owner:** Ender, in the 0.6.0 batch.

### Non-comic files under Y:\Comix (Sergei, 2026-10-27)
- 514 EPUB (D&D novels), 150 MOBI (Conan, John Carter, Assassin's Creed and others), 1 DJVU and about 650 loose JPGs (wallpapers, extras, a few image-folder comics). Sergei: "The books are fine." No action.

### Updater waiting banner confirmed (Sergei, 2026-10-27)
- During the 0.4.1 → 0.5.0 update, Sergei saw the waiting message and no second Install offer. The 0.4.1 fix works in real use.

### Minor follow-ups from the 0.5.0 review and QA (logged 2026-10-27; not started)
- **Senua m1–m10** (`Docs/ComicsMetaOrganizer_CodeReview_v0.5.0_2026-10-27.md`):
  - Lens verification can still be requested while Lens is off.
  - Archive reads block renames: up to 30 opens per comic.
  - The combined false-accept rate across 3 pages × 10 covers was not measured.
  - The folder-year rule has no one-year-off check. Sergei's later GCD ruling allows these matches, so keep the two consistent.
  - The refinement turn reads every written comic.
  - Pages are decoded twice per remote cover.
  - Year-range parsing edge cases: `(1993 - 1995 Dark Horse)` and `(2010-12)`.
  - Roman numerals and number words are treated as unnumbered.
  - `can_search` duplicates source checks.
  - Four mismatches between the docs and the code.
- **Futaba Minor 1:** the cover check rejects a cover scaled into a margin on all four sides. It fails safe.
- **Senua re-review at b2bfaef (2026-10-27):**
  - **m11:** the Ghostscript guard test only scans the text of top-level files. Disable Pillow's Ghostscript plugin when the engine starts, so every decode path is covered.
  - **m12:** a side effect of F1. A page 1 that is really a GIF or BMP named `.jpg` now fails, and its Metron lookup is retried as an error every few hours. Fix: add GIF and BMP to the cover allow-lists. Do this first.
  - **m13:** when Metron's list image and detail image differ, only the detail check is recorded in `cover_match`.
- **Owner:** Ender, batched with the next change.

### Minor follow-ups from the 0.4.1 review and QA (logged 2026-10-26; not started)
- **Senua m1:** in `desktop/updates.cjs:84`, pressing Try again while a manual Check for updates is still running leaves the state and the banner out of step. Try again and × do nothing until the check returns; it then settles on "Update ready" by itself.
- **Senua m2:** in `update_stats.py:361-362` and `:372`, one history row dated in the future turns off the fast refresh for every period until real time catches up. Refreshes then take 0.5–2 s; the counts stay correct.
- **Senua m3:** the unused 0.4.0 `history_timestamp` index is still updated on every write, and the catalog grows about 41%. Consider dropping it.
- **Futaba QA-1:** the Confirm banner is 67 px, not the spec's 64, so the content moves 11 px instead of 8.
- **Futaba QA-2:** the desktop Node tests need `COMICS_META_TEST_SCRATCH` set, otherwise 21 of 50 fail. Fold this into the entry-check repair below.
- **Sources:** `Docs/ComicsMetaOrganizer_CodeReview_v0.4.1_2026-10-26.md`, `Docs/ComicsMetaOrganizer_QA_v0.4.1_2026-10-26.md`.
- **Owner:** Ender, on the lean path, batched with the next change.

### Make the entry check pass cleanly (Sergei, 2026-10-26)
- **Why:** the 0.4.0 entry check (`dd019cb`) ran 968 tests: 959 passed and all 48 update-stats tests passed. It still failed, because of the test setup, not product code. 0.3.0 had no entry receipt at all. Evidence: `C:\Antigravity Projects\Worktrees\Comics Meta Organizer\qa-040b\logs\ender-entry.log`.
- **Wanted (Sergei):** fix it later, as its own task. It does not hold 0.4.0.
- **What Ender found:**
  1. **Test Python:** the packaged app's Python ignores the working folder (`python314._pth`), so three tests that start a child Python fail with `ModuleNotFoundError` (`test_state_root`, `test_library_lock`, `test_qa_runtime`). Ender proposes a pinned test Python of the tool's own, like Books Arranger's QA runtime.
  2. **Non-UTF-8 output:** the checker fails the step with "Final supervisor output differs from streamed bytes" when test output is in the Windows code page. The fix is in the checker, or `-X utf8` in `check-python.cjs`, or both.
  3. **Time-sensitive tests:** two kept-backups tests fix their times when the module loads ("12 min ago" vs "13 min ago").
  4. **Old failures:** three failure-filter DOM tests already failed on clean HEAD.
  5. **Shell tests skipped:** `check:shell` never runs when `check:python` fails, because npm `&&` stops there.
  6. **Context builder:** CMO has no committed entry-check context builder. Ender's one-off is at `...\qa-040\assemble-context.mjs`.
  7. **Release cleanup guard (2026-10-26, v0.4.1):** `scripts/cleanup-releases.js --apply` refused to run with "Held fixed GitHub executable/publication supervisor required" (it needs `COMICS_META_HELD_PUBLICATION=1` and an absolute executable path). The same step ran during the v0.4.0 release. Five releases are now live (v0.2.5 to v0.4.1), one over the keep-4 limit. Make the lean release path able to run it, then remove v0.2.5.
- **Owner:** Ender. Senua reviews the context builder before it is committed.
