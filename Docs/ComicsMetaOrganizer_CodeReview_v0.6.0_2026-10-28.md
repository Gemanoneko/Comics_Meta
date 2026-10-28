# Code Review — Comics Meta Organizer v0.6.0

## Header

```text
Reviewer: Senua (Code Reviewer)
Date: 2026-10-28
Tool: Comics Meta Organizer (Python engine / Electron desktop)
Release: v0.6.0
Commit range: b2bfaef6d97aeca2637f6884e230d836f6184887..e21e0fcdab7227fa58a367301019123c56628153
Commits: 7
Files changed: 47 files, +2929 / -72
Stand-down dimensions: none
```

The baseline is the final F1–F4 clearance in `ComicsMetaOrganizer_CodeReview_v0.5.0_2026-10-27.md`, not that report's earlier blocked candidate. Counts come from `git rev-list --count` and `git diff --shortstat` over the exact range above; they include documentation, tests and the non-shipped pilot. The reviewed source is the clean detached `scratch/cmo-060-20261028/candidate-fixed` checkout. No product source was edited for this review.

## Summary

Reviewed the GCD provider, index construction/replacement, scheduler integration, source preservation, cancellation and schema checks; the all-labelled Star Wars Legends exclusion; shared language gate; manual ComicVine URL replacement; raster/EPS changes; conversion recovery proof; and reproducible packaging inputs. There are no new Critical findings or identified safety-floor violations. One Major and one Minor remain for the next cycle. The Major is a GCD credit omitted when its synopsis is combined with a ComicVine metadata write; the Minor is a remaining GIF/BMP enumeration gap in local credits pages.

Severity follows `Team/Docs/ProcessRules.md` § Severity definitions. Advisory findings below do not request another 0.6.0 build.

## Rubric

### 1. Security

- Status: Pass — the new picker retains the trusted sender boundary, external links have a bounded HTTPS allow-list, POST routes retain the origin/Host check, SQL values and subprocess arguments are parameterized, and no credentials or executable archive paths were added to renderer control.

### 2. Correctness & Logic

- Status: Concerns.
- **M1 [Major] GCD synopsis credit is lost when ComicVine metadata is already queued.** `automatic.py:674` assumes any `outcome == 'queued'` entry already contains GCD attribution. That is false when `automatic.py:610–634` queues verified ComicVine fields while the external GCD result supplies the missing synopsis. The final Notes retain the GCD issue URL, but omit the Grand Comics Database credit, CC BY-SA 4.0 and dump date. This violates the release's explicit Notes contract.
  - **Reproduction:** an isolated `Example #1` has a matching ComicVine Web ID and no Title or Summary. ComicVine supplies Title; the actual discovery path calls the mocked GCD lookup once and receives the synopsis source plus attribution. A reviewed-synopsis fixture is accepted. The resulting plan contains ComicVine Title and GCD Summary, with no `CC BY-SA 4.0`. The positive control, GCD metadata plus GCD Summary without a ComicVine ID, contains the credit.
  - **Next cycle:** add the GCD attribution whenever its synopsis contributes to the final entry, deduplicating against that entry's actual Notes rather than inferring presence from `queued`. Preserve the one-plan/one-write behavior and include the mixed-provider regression.
- Exact, year, folder, yearless, collection and unnumbered matching retain the approved pilot rules and reversals. Date-aware publisher mapping, retained cover Series, filename Count and complete-dump GTIN counting are present. A known ComicVine conflict/hold continues to block metadata-field writes; this review does not redefine the approved no-cover GCD identity rule.

### 3. Crash / Stability Safety

- Status: Pass — schema/build/cancel errors preserve the active pointer, SQLite cancellation uses a progress handler, the build lock releases in `finally`, and the source-level GCD deadline correction prevents a missing index from repeatedly bypassing existing source waits.

### 4. Performance

- Status: Pass — inspection reads archive metadata/header, matching uses trimmed indexed tables, construction runs separately from the request handler, and source concurrency remains bounded at two; no new benchmark or timing claim was made by this review.

### 5. State & Data Safety

- Status: Pass — source DB attachment is read-only, ZIP extraction uses an app-chosen staging filename, active-index publication follows validation and staging cleanup, and deletion is restricted to validated owned paths. Conversion cleanup retains unproved staging; its new fallback requires the recorded CBZ path and matching SHA-256 before cleanup after source removal. Manual approval uses the selected Web URL with the existing guarded snapshot/backup/readback path.

### 6. Input Handling

- Status: Concerns.
- **m1 [Minor] Native GIF/BMP credits pages are still skipped.** `local_model.py:99` and `local_model.py:194` enumerate only `.jpg`, `.jpeg`, `.png` and `.webp`, although their decoders now allow GIF/BMP. Three-page archives named `001.gif`–`003.gif` or `001.bmp`–`003.bmp` therefore return zero opening and zero credits pages. The cover route correctly reads both. With identically generated PNG pages, the same calls return three opening pages and two credits pages.
  - **Next cycle:** share the supported raster extension list with the cover reader, and cover native filenames as well as raster bytes disguised under another extension. This is a residual limitation, not a recurrence of the EPS safety issue or the fixed GIF/BMP cover regression.
- The language check is shared by automatic sources, recognizes both bracket styles and regional codes, and keeps English/unknown filename tags eligible. The explicit Star Wars Legends label check applies to every publisher and to filenames outside the exact folder; generic unrelated `Legends` titles remain eligible.

### 7. Maintainability (no Critical findings on its own)

- Status: Concerns — m1 demonstrates remaining drift between separate raster extension lists. Counted once, under Input Handling.

### 8. Doc/Code Drift (no Critical findings on its own)

- Status: Concerns — the Brief/handoff's blanket GCD Notes attribution statement has the mixed-provider exception in M1. Counted once, under Correctness & Logic. Historical build/gate-stop sections are retained as history; current candidate acceptance belongs to the release/QA record.

### 9. Build & Release Hygiene

- Status: Pass — the pinned preparation path disables lifecycle scripts, authenticates downloads before extraction, rejects unsafe archive members and linked trees, publishes the input manifest last, and validates prepared trees before building. Cleanup of staging/temp paths checks their ancestors and children first. The safe NSIS route is unchanged; VERSION/package/lockfile agree at 0.6.0. The old recovery folder remains held until independent packaged QA proves the rebuild.

## Verification and limits

- Source review used the pinned checkout, the approved Backlog reversals, Judy's amended GCD spec, the developer handoff and corrected-candidate identity. The source manifest and every listed source file, plus the packaged-runtime manifest and every listed runtime file, were rehashed immediately before the review probes. Both manifests matched the canonical identity. Candidate status remained clean afterwards.
- Installer SHA-256 was independently read back: `f80b1192d6386ef533a5972d187e8e380501ae4ef52bc73aeec34e746603081a` (`Comic-Metadata-Setup-0.6.0.exe`, 149,536,539 bytes per identity bundle).
- **Review probes: 5/5 cases confirmed**, one bounded run: two attribution paths plus PNG/GIF/BMP page enumeration. They exercised the real discovery/plan code and real raster readers with synthetic local archives and mocked provider/model answers. No full suite, mutation sweep, application launch, real profile, live library, live model or network access occurred. State isolation loaded before `app`; there were zero isolation violations. The existing audited owner enforced the 600,000 ms ceiling and returned code 0, normal closure, `native.zero: true` with zero active descendants. Evidence: `scratch/cmo-060-20261028/owned-1793189878918.json`; readable results and exact probe sources: `scratch/cmo-060-20261028/senua/`.
- **Canonical entry result, read rather than repeated:** 1,052 tests; five failures, one error, one skipped subcase. The six failing cases are the three failure-filter DOM cases, two kept-backups DOM cases and the inherited child-Python state-root case. The known supervisor non-UTF-8 comparison mismatch also remains. These are the already accepted inherited exceptions; this is not a clean-suite claim. The skipped subcase could not create a Windows file symlink. Both inner and outer owners proved zero remaining descendants. `gate-fixed-summary.json`, `gate-fixed-evidence.json` and `QA_HANDOFF_FIXED.md` bind this evidence to `e21e0fc`.
- The corrected `ready()` requires a current GCD index before using a changed rule stamp to bypass the deadline; `due()` has the same current-index requirement. Its focused controls cover no index before/at deadline, a new index waking a miss, and an already recorded index honoring the wait. The four unexpected cases from the first candidate are explicitly `ok` in the corrected canonical run. The replacement build/run was authorized; neither was duplicated here.
- Futaba owns the separate desktop tests and packaged launch/Quit behavior verdict. This code verdict does not replace her GO or authorize recovery deletion on its own.

### Packaged-smoke route safety review

The concrete session harness `scratch/cmo-060-20261028/packaged-smoke/smoke.mjs`, SHA-256 `ce3b572e7aec8207fd25d20a1f1641a3389774892aaf59c0ccb662fe8f653d64`, is cleared for Futaba's single bounded run through the existing audited `run-owned.mjs`. This is prelaunch route clearance, not a claim that the smoke has passed.

The harness checks all 620 packaged files before and after execution; uses the unmodified packaged EXE; provides the production hash-bound QA policy with fresh private profile/state/cache/locks and a sanitized environment; and opens the first-run setup from an empty config, with no real library or worker workload. The app starts paused on a loopback inspector. Before installing runtime guards, the revised harness reads and checks the exact child PID/executable. Guards refuse window show/focus/restore/maximize, external shell opens and unexpected main-process child launches. The renderer must be hidden and offscreen, report 0.6.0, use the private paths and confirm unconfigured setup through the real preload/server bridge. The harness captures the real tray menu while delegating its native setup, invokes its actual enabled Quit callback, detaches the inspector and requires natural code-0 exit. A 90-second internal bound sits within the audited owner's 600,000 ms deadline and descendant-closure requirement.

The original harness installed its prototype guards before checking inspector identity; Ender corrected that ordering in session scratch before clearance. No product code or package bytes changed and no app was launched by Senua. The native tray may appear transiently and Windows may retain ordinary tray history; the route does not edit the registry, send desktop input, install to a user profile, launch signed-in accounts or touch the running app. Futaba must record the actual exit, unchanged package and native-zero receipt.

**Focused harness correction:** the first QA attempt at `ce3b572e…` failed with inspector error `Promise was collected` before saving readiness or Quit proof (`futaba/packaged-smoke-y1AM4C/result.json`); it is not a successful smoke. The owner proved descendant closure. Ender's revised harness, SHA-256 `6141e35f112e403d00d1af39a7bfa499cdc44bbaff7f115582e6b46ac4499b47`, retains the readiness Promise by remote object ID/object group until `Runtime.awaitPromise` settles, waits for the main frame to finish loading, and records the inspector identity and operation stage. Senua reviewed only that diff against the preserved first source and cleared the revised route for Jane's one focused retry. All identity/isolation guards, complete-package checks, actual tray Quit callback, natural code-0 requirement and time bounds are preserved. This correction does not change the product verdict or prove that the retry succeeds; the actual result belongs to Futaba's report.

Actual receipt:

```text
Entry-check receipt v2: comic-metadata v0.6.0 @ e21e0fcdab7227fa58a367301019123c56628153 (dirty: N) [source:560e8ef8e2a9a1ad57681336feaaf89556f097e18d5da585f376b541171d72e7; harness:254b1bad928b1e741cbd7bef9a1c347d94b760893df925a9823b53fdb5583944; runtime:155d34fb8640b0582895ae2f971156e3683c2b0deb6209e4fcf9dd8bcc494c23; checker:a448c08c150e63019cfd6e49ceed5ec5b8652a97078abde197e7a50882b759cf] — pre-qa n/a, post-build n/a, check-electron n/a, check fail (owned check), test:smoke n/a
```

## Prior review follow-through

- Prior **m11:** addressed. `app.py` imports `image_safety` before cover handling; startup removes EPS registration and disables the Ghostscript function itself. Per-call raster allow-lists remain. The committed regression calls Pillow without an allow-list and verifies no Ghostscript invocation.
- Prior **m12:** the cover/comparison regression is addressed throughout the callsites and `reverse_image` extension/MIME handling. The remaining opening/credits-page enumeration limitation is new report m1 above.
- Prior F1–F4 remain cleared by the baseline review. Prior m1–m10 and m13 were not the requested repair scope and remain carried by the existing Backlog; they are not counted as new findings here.

## Patterns

Both findings cross a boundary that local happy-path checks miss: a queued plan can belong to a different provider, and accepting image bytes does not ensure the file enumerator reaches them. Keep the next-cycle regressions at those boundaries.

## Verdict

- Total new/open Critical: **0**.
- Total new Major: **1** (M1, next cycle).
- Total new Minor: **1** (m1, next cycle).
- Safety floor: intact in the reviewed changes.

**Verdict:** RELEASE CLEAR

No source repair is required by this review before the authorized 0.6.0 release. Preserve the session evidence for Sergei's manual cleanup; no session scratch sweep was performed.
