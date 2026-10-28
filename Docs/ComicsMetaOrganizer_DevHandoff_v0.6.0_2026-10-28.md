# 0.6.0 development handoff — 2026-10-28

Status: the first clean 0.6.0 installer built successfully from `b14375aa057e1dfa900a608484bd4855392e29a7`; its formal gate found four unexpected test failures and stopped handoff. The minimal correction below passes its focused checks. A replacement build and entry run await Sergei’s explicit exception to the one-build constraint. No release or QA acceptance is claimed. Final candidate identity and acceptance belong in the QA/release reports.

## Scope and behavior

- GCD offline joins the existing source order after Metron, with the existing two-source concurrency and priority selection. The old online GCD provider remains switched off. Exact, filename-year, folder-year, yearless, unnumbered and collection matches use the approved pilot rules and later reversals. A result still needs exactly one candidate. Sergei’s final ruling, “Yes, skip GCD for all Legends files,” excludes every path explicitly labelled `Star Wars Legends`, including the folder tree and named files elsewhere, for every publisher; other sources remain unchanged. Generic unrelated `Legends` titles are not excluded. Existing conflict, ComicVine hold, provenance, archive-signature and per-field write checks remain authoritative. A new dump/rules identity wakes unresolved misses once.
- The index is built under a fresh UUID name. A single OS lock owns construction, progress and cancellation. The active pointer changes atomically only after schema checks, index integrity verification and staging cleanup. An interrupted, failed or cancelled build retains the previous index. Old indexes are removed only from the app’s owned, non-linked index directory; busy old readers can finish. No source ZIP or DB is changed or removed.
- The dashboard implements Judy’s single pass: independent current-index and build-attempt states, inspect before build, explicit confirmation for same/older dumps, cancellation, errors with actions, elapsed/stage progress, source status and attribution. At age **14 days**, the reminder links to the GCD download page. Help specifies **Download SQLite Dump** (all formats can be named `current.zip`), accepts that ZIP as downloaded, and explains that an old download may be deleted manually after a newer index reaches Ready. No automatic download or source deletion occurs. The native picker uses the existing trusted-renderer boundary.
- GCD Publisher aliases reuse the application’s date-aware imprint rules. A cover Series is retained when its series key or GCD sort key agrees; filename `(of N)` wins for Count. Shared GTINs are omitted using a count across the complete dump, including variants/non-English records. Unnumbered/collection names with `Complete Vol`, `N of M`, or doubled opening brackets remain held. Characters, Genre, Day, AgeRating and Format remain omitted; their free text has no approved normalization. Synopses enter the existing quote/spoiler review. GCD issue URL, dump date and CC BY-SA 4.0 credit accompany metadata or synopsis-only writes.
- Every source shares the expanded bracket-language gate. `language_tags.py` records the Library of Congress ISO 639-2 table URL/hash and includes its B/T/alpha-2 codes and English/French names, plus existing scan aliases. Both `[]` and `()` work. English and unknown tags remain eligible; untagged foreign-language scans remain a known limitation.
- GIF/BMP are accepted consistently for archive covers and image comparisons. Pillow’s EPS reader/Ghostscript entry point is disabled at startup as defense in depth; every existing image callsite retains an explicit raster allow-list.
- Manual ComicVine approval now replaces the saved ComicVine issue URL with the selected issue’s URL while preserving unrelated Web links and other populated metadata. The previous fill-empty-only write left the old issue ID in `Web`; the next automatic identity check read it again and recreated Critter #8’s conflict. Preview and apply use the same plan, existing backup/verification/guard behavior remains, and Judy’s copy states the URL replacement explicitly.

## Conversion diagnosis

7-Zip can preserve a page’s read-only attribute in the app’s staging directory. The former plain `rmtree` can then fail after conversion verification and original removal. Maintenance also required the original to remain, so it could not safely clean that later state. Future staging cleanup clears a read-only attribute only within the exact verified, non-linked owned staging tree. Before removing a converted original, the ledger now stores the verified CBZ path and SHA-256. Maintenance accepts either the unchanged original or that verified output as proof; unknown/unproved directories remain untouched.

The historical Michael Moorcock folder had already been deleted at Sergei’s request, so its exact historical failure cannot be proved retrospectively. The reachable failure mode above is covered with a copied fixture. This session did not clean the live library. The fresh snapshot has no staging ledger rows; a positive read-only walk of 8,755 library directories found **40,199 CBZ and zero CBR**. The historical 19 CBR files are no longer present; there is no current 19-file failure to reproduce. The snapshot contains 208 conversion records, which do not establish what happened to each historical file.

## Read-only measurement

Inputs live only under `C:/Antigravity Projects/Studio Illuminati/scratch/cmo-060-20261028/`:

- `shared/catalog.sqlite`: one fresh SQLite backup from a `mode=ro` connection. No other LocalAppData/ComicsMeta data was opened. Catalog rows: 40,338 total, 40,236 non-absent in the pilot classification.
- `shared/inventory.json` and `shared/library-inventory.json`: snapshot diagnostics and positive library walk; library access was read-only.
- Source `C:/Users/AnGeLZzZ/Downloads/comics DB/current.zip`: read-only, unchanged size and modification signature before/after construction. Dump member date: 2026-10-16. The source remains in place.
- `gcd-state/data/gcd-offline/index-6b378eaf0bba4e1b9cc0bb11ab93060b.sqlite`: 325,873,664 bytes. One real index construction reached Ready in 101 seconds; reserved free-space requirement 7,551,043,584 bytes, initial free space 105,555,718,144 bytes. The temporary expanded DB was removed by the successful lifecycle. Evidence: `owned-1793180200022.json`, `shared/gcd-ready.json`.

Method: run the unchanged pilot’s B/D/E population selection and historical in-book-field eligibility on the fresh snapshot, then run the production matcher on that same population and same index. These are **potential writes before live conflict/hold/signature gates**, matching the original pilot’s measurement method. Historical population 30,094 / potential writes 12,689; current comparable population 28,973 / old-rule writes 11,672. The population change must not be described as a matcher regression.

**Final production rules yield 11,291 potential writes.** The initial Dark Horse-only interpretation yielded 11,354 and held only 152 potential rows; it was not shipped. Sergei then ruled to skip GCD for **all Legends files**. The final guard covers all **1,151 explicitly Star Wars Legends-labelled catalog rows**, including all **215 current old-rule potential matches** (152 Dark Horse, 63 other publishers, including the unrelated CrossGen `Vector` match). This covers the current equivalent of the historical approximately 217 rather than silently treating that historical estimate as today’s count.

The exact `Star Wars Legends` folder component alone contains 1,118 rows / 192 potential matches. Another 33 labelled files live elsewhere, 23 of them potential collection matches. One final matcher measurement on the saved snapshot/index returned 11,314 for the exact-folder interpretation; applying the acknowledged all-labelled-files scope filtered those 23 saved results to **11,291**, without another matcher run or DB/library read. The provisional and exact-folder artifacts are retained with corresponding suffixes. Final per-rule counts below are from the actual filtered output, not subtraction assumed in advance.

| Matching rule | Original rules, fresh snapshot | Production rules, final |
|---|---:|---:|
| Exact | 4,776 | 4,651 |
| Filename year | 360 | 345 |
| Folder year | 784 | 665 |
| No year | 3,152 | 3,126 |
| Unnumbered | 1,586 | 1,538 |
| Collection | 1,014 | 966 |
| Total | 11,672 | 11,291 |

Evidence: `shared/measurements.json`, `shared/would-write.json`, `shared/pilot-comparison-final/`, `shared/legends-coverage.json`; final matcher `owned-1793185975665.json`, saved-output filter `owned-1793186122013.json`. Earlier diagnostic records `1793180403521`, `1793180569849`, `1793180612646` remain historical/provisional. No new live snapshot or inventory was taken for this final measurement.

## Targeted development evidence

All tests ran with isolated state under the session folder, the state-isolation import first and sentinel last. Windows descendants were owned by the existing audited private Job Object wrapper, with a 600,000 ms wall deadline and proved zero descendants on return. The wrapper re-verifies the preserved qa-050c ownership manifest/native addon and canonical helper hashes; it does not install an ownership addon. No live app was launched, stopped, paused or focused.

| Check | Result and evidence |
|---|---|
| Critter failure first; language failure first | Original implementation: the actual mocked-provider manual apply retained the old Web URL, and 64 bracket-language subcases failed. The initial red output is in the session tool transcript. |
| Raster/EPS/cleanup red | `owned-1793179841070.json`: 6 tests, 1 failure and 3 errors; the already-fixed manual/language checks passed. |
| Bug/raster targeted green | `owned-1793179920112.json`: 10 tests passed, including old Ghostscript regression checks and the isolation sentinel. |
| GCD lifecycle/matching/scheduling | `owned-1793180046071.json`: 6 tests passed. Initial fixture run exposed a missing URI connection flag in the port and fixture connection cleanup; both were fixed before this green run. |
| GCD UI | `owned-1793180834932.json`: 3 tests passed. Covers 320/640 px, 13/14-day boundary, help, newer/same/older previews, keyboard selection/build/cancel, backend error codes and unavailable status. A first fixture attempt used a scrollbar-inclusive overflow comparison and omitted UTF-8; corrected fixture then passed through the unchanged canonical headless host. |
| Date-aware imprint + read-only cleanup | `owned-1793181433323.json`: 3 tests passed, including isolation. WildStorm before/after 1999, Archaia before/after 2013, and unknown dates retain the established behavior. |
| Final Legends guard | `owned-1793186114446.json`: 2 tests passed, including isolation. Every publisher is held inside the tree and for explicitly labelled files elsewhere; a generic unrelated Legends title stays eligible. |

UI evidence: `tests/gcd-ready-14-days.png`, `tests/gcd-ui-rects.json`. Jane visually inspected the 14-day screenshot and found the panel/reminder/download instructions readable, with no visible clipping or overlap. Fixtures use an artificial 14-day date; this is boundary coverage, not the current dump’s actual age.

These targeted runs are not the full acceptance suite or a formal entry-check receipt. Do not sum their totals as unique tests; several include the same isolation sentinel.

## Reproducible toolchain and final gate contract

Second Ender owns the build-toolchain implementation and Brief Inputs subsection. Fresh inputs were downloaded/assembled independently of `scratch/cmo-packaging-recovery-20261015`:

- Root: `C:/Antigravity Projects/Studio Illuminati/scratch/cmo-060-20261028/shared/toolchain`.
- Manifest SHA-256: `c3cc8421b03a2254ffe570f089fa60a5884c3c03dcfafdb91816054ff6ff9e66`.
- Runtime: `capsule/runtime/python/python.exe`, `capsule/runtime/7zip/7z.exe`; Electron: `native/electron/electron.exe`.
- Eleven archive downloads authenticated against committed pins; Python imports and 7-Zip 26.04 verified. Native: 442 files / 390,382,116 bytes; capsule: 468 / 152,310,536; dependencies: 7,589 / 96,893,188. Pin JSON hashing is stable across CRLF checkout conversion. Final source-aware preparation tests: six passed (`owned-1793180367740.json`); full-tree readback and unchanged safe-NSIS pins: `owned-1793180292095.json`. Both returned code 0, closed true and zero active descendants.
- The clean candidate must have no `node_modules`. One coordinated build, after Sully commits version 0.6.0: `node scripts/build-installer.cjs --inputs <absolute prepared-input root>`, under the audited 600,000 ms owner. The build driver verifies inputs and supplies prepared dependencies.

**Recovery deletion remains held** until that clean-input installer’s identity and isolated packaged smoke prove a working rebuild. Only then may the exact old recovery directory be removed; qa-040b, qa-050c and ownership evidence remain preserved. Preparation alone is not installer proof.

The builder runs the complete entry check **once** using `.claude/skills/qa-handoff/scripts/run_entry_checks.mjs`, a reviewed protocol-2 context and pinned source/runtime/tooling manifests. Futaba compares the actual receipt/hashes and tests changed behavior, per Lean verification §7; no duplicate full gate. Accepted inherited failures are exactly: three failure-filter DOM tests, two clock-sensitive kept-backups tests, three `._pth` child-Python tests, and the checker’s non-UTF-8 mismatch. **Any other official entry failure is STOP/report.** Futaba runs desktop Node tests separately with `COMICS_META_TEST_SCRATCH` because they do not execute after the known Python check failure. The first actual failed receipt is recorded below; it is not acceptance evidence for the corrected source.

## First clean build, gate stop and minimal correction

The single clean build from `b14375aa057e1dfa900a608484bd4855392e29a7` copied the independently prepared dependencies into a candidate with no `node_modules`, verified the pins, and completed in 36.5 seconds. Installer: 149,536,532 bytes, SHA-256 `30da4afb691f07026c1a7b72f72262b8faf9d47dd2dedb4056c27c097fffa1fd`. Build evidence: `owned-1793186365553.json` (code 0, closed true, zero descendants, `bootstrapExecuted: false`). All 543 staged resources matched the packaged copies. Complete 620-file package identity: `candidate-identity.json` and `packaged-files.json`, latter SHA-256 `23b9c5b69aeccca829e0a7ffbb608454c436e2725f16b63cf68c17c58d71362d`. This establishes clean construction, not a working packaged smoke or release acceptance.

Formal gate: 1,051 tests in 167.241 seconds, eight failures, two errors, one skip. Saved evidence: `owned-1793186719642.json`, `gate-evidence.json`, `gate-summary.json`, `entry-receipt.txt`. Observed inherited failures: three failure-filter DOM, two clock-sensitive kept-backup, one `._pth` state-root case; the canonical supervisor also reported its accepted non-UTF-8 output mismatch. The inner supervisor used forced closure for that mismatch; both inner and outer ownership reports proved zero remaining descendants. The four additional failures triggered the required stop; no repeat full suite or replacement installer was run.

Actual original-candidate receipt:

```text
Entry-check receipt v2: comic-metadata v0.6.0 @ b14375aa057e1dfa900a608484bd4855392e29a7 (dirty: N) [source:daf27f74ab63811807a2f91afe887f21600804950acad8e57755c9b05c66251b; harness:6d41f867be74a15ad8b4ff85e3071dbc75ffd56bf767890dff2d26924d7de7e5; runtime:155d34fb8640b0582895ae2f971156e3683c2b0deb6209e4fcf9dd8bcc494c23; checker:a448c08c150e63019cfd6e49ceed5ec5b8652a97078abde197e7a50882b759cf] — pre-qa n/a, post-build n/a, check-electron n/a, check fail (owned check), test:smoke n/a
```

Read-only diagnosis classified the unexpected failures before edits:

- `test_comic_lookahead.EligibilityTests.test_expired_comic_retry_does_not_override_all_source_deadlines` and `test_recovered_provider_wakes_waiting_comic`: **production regression**. A missing/old GCD rules stamp differed from `gcd-offline-1:none`, making the source ready before its deadline even though no index existed. The correction requires an active index before a rules mismatch can override the deadline. The original fixture’s all-source wait remains valid.
- `test_library_lock.WriteGuardTests.test_maintenance_keeps_conversion_staging_in_a_library_it_does_not_own`: **stale fixture**. Its `.comic-metadata-convert-fixture` name is never produced by the converter, which uses 32 hex UUID characters. The fixture now uses a real owned-name shape; both the busy-library refusal and later positive cleanup assertion remain. Production cleanup stays strict.
- `test_reverse_image.FileCoverPreviewTests.test_every_unreadable_file_has_one_answer`, subcase `other format under an image name`: **stale fixture**. It used GIF bytes named `.jpg`; GIF is deliberately supported in this batch. The negative fixture now uses unsupported TIFF bytes, keeping the renamed-format refusal and archive-unchanged assertions. Production raster behavior is unchanged by the repair.

Correction scope: `source_scheduling.py`, `tests/test_gcd_offline.py`, `tests/test_library_lock.py`, `tests/test_reverse_image.py`. Focused run `owned-1793187096787.json`: **7/7 passed**—the four previously failing cases, a no-index missing/old-stamp deadline test (plus active-new-index ready/settled controls), the existing new-index wake-once test, and the isolation sentinel. Native closure was normal, code 0, zero descendants. No full-suite repetition occurred.

The staged manifest proves `source_scheduling.py` is shipped as `engine/source_scheduling.py` (original SHA-256 `93cdbc093501471168ab4bcc1b3fd737fa61150b9795e3c30d4f54eb9e940966`); the three test files are absent from the installer. Consequently a tests-only reconciliation cannot preserve the original installer. The corrected production line requires a new source identity and an explicitly authorized replacement build. The unreleased version remains 0.6.0. The original candidate, receipt, package manifest and recovery folder remain intact while that exception is pending.

All per-session leftovers stay at `C:/Antigravity Projects/Studio Illuminati/scratch/cmo-060-20261028` for Sergei’s manual deletion after acceptance; they are not a cleanup target during this handoff.
