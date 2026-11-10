# Code Review — Comics Meta Organizer v0.6.1

## Header

```text
Reviewer: Senua (Code Reviewer)
Date: 2026-11-10
Tool: Comics Meta Organizer (Python engine / Electron desktop)
Release: v0.6.1
Commit range: e21e0fcdab7227fa58a367301019123c56628153..f64441e95a1381daa9a0448901d46f85cd2951b7
Files changed in committed range: 21 files, +807 / -33
Stand-down dimensions: none
```

The baseline is the preceding review's final endpoint. Tag v0.6.0 points to later documentation-only commit `11ae3c64d4101969526e388ac9da331948dc4f57`; the product delta from that tag is identical. Counts use `git diff --shortstat` over the stated range. Endpoint `f64441e` includes the exact reviewed two-file test-runner correction and source QA document; product source is unchanged from milestone `500df00`. Documentation-only acceptance/QA commits do not change the reviewed product. A different product or runner requires review of its delta.

## Summary

Reviewed the complete filename parser, in-memory legacy identity refresh, GCD collection fallback, cache/rules stamps, regressions, focused test runner, version/lockfile/changelog and packaging inclusion. The four naming cases remain conservative: padded underscore issues, explicit Vol/subtitle collections, Book labels and one exact demonstrated scanner suffix. Existing matches and ambiguities, embedded metadata, language/Legends exclusions and write safeguards remain authoritative. No new Critical finding or safety-floor violation was identified. Two inherited Major advisories and one inherited Minor remain; no statistical edition-precision or packaged/native QA claim is made by this code verdict.

Severity follows `Team/Docs/ProcessRules.md` § Severity definitions.

## Rubric

### 1. Security

- Status: Pass — the product delta adds no shell commands, native decoder, renderer privilege, credential handling or arbitrary executable path; SQL matching values remain parameterized and Electron security boundaries are unchanged.

### 2. Correctness & Logic

- Status: Concerns.
- **I1 [Major, inherited behavior exposed by the additional collection matches]: content identity does not prove a digital/print edition's identifiers.** `gcd_matching.py`, `Matcher.gcd_fields`, still emits any syntactically valid GCD ISBN and a qualifying GTIN. `automatic.py:223–229` fills empty fields and may replace provenance-eligible app-written in-book fields. The new collection-label path does not compare an eISBN visible only in the archive's indicia. Futaba reported a Star Wars Adventures digital collection with indicia eISBN `9781684064809` versus candidate print ISBN `1684052491`: matching title/volume does not establish identifier equivalence. Existing human/external ComicInfo identifiers are retained. This is the existing approved GCD field policy, not proof that the new collection/content match is wrong; prior pilot rows explicitly accepted digital collections and included ISBN/GTIN. Do not describe this sample as exact digital/print edition validation. A future field-policy decision can omit unproved edition-specific identifiers without imposing a global ISBN equality requirement on content matching.
- **I2 [Major, carried from 0.6.0 M1]: mixed-provider synopsis Notes can omit GCD attribution.** `automatic.py:674` still infers attribution from `outcome == 'queued'`, although the queued metadata may belong to ComicVine. This unchanged case remains documented in the 0.6.0 review and Backlog; no new reproduction or repair is claimed here.
- The new collection-label fallback requires explicit structured syntax, a book/collection record, volume, actual issue publication/sale year, subtitle agreement when present and a unique candidate. It does not replace a prior matching series or ambiguity. Explicit HC/TPB evidence remains distinct; a generic collected-edition description proves neither binding.

### 3. Crash / Stability Safety

- Status: Pass — the helper is pure filename processing, the new lookup adds no asynchronous owner or external request, and the source runner retains a finite watchdog with process creation refused.

### 4. Performance

- Status: Pass — shortened collection queries occur only after an empty prior series result, use the existing indexed key/number queries and do not scan archive contents; rule changes wake old misses once rather than removing source pacing.

### 5. State & Data Safety

- Status: Pass — legacy catalog identity is refreshed in memory only when it still equals the old filename parse; deliberate catalog overrides and embedded values retain precedence. Source-index lookup remains read-only. Captured-index stamping prevents old-index results being labelled with a replacement index. Archive write, backup, signature, provenance and readback paths are unchanged. I1 concerns field accuracy and is counted once under Correctness.

### 6. Input Handling

- Status: Concerns.
- **i1 [Minor, carried from 0.6.0 m1]: GIF/BMP credits enumeration remains incomplete.** `local_model.py:99` and `local_model.py:194` still omit native GIF/BMP names from opening/credits enumeration, despite supported decoders. This pre-existing limitation was outside the naming-fix scope.
- Padded underscore syntax does not globally replace underscores. Unpadded title digits, unknown scanner suffixes, nested Book/Part/Chapter labels and unsupported collection identities remain unresolved. Existing ordinary fractions and language/Legends/filename Count guards are covered by the focused regressions.

### 7. Maintainability

- Status: Pass — pure filename syntax has a shared helper, and the bounded cache/scheduler consumers and build inclusion were checked together.

### 8. Doc/Code Drift

- Status: Concerns — normal external-result Notes at `automatic.py:652` say “Issue or edition identity checked”; that is not independent proof of digital/print equivalence for I1. The handoff correctly labels 601 potential new candidates as opportunities, not approved writes or a precision certification. I2's attribution exception remains documented. These are counted under Correctness, not again here.

### 9. Build & Release Hygiene

- Status: Pass — VERSION, package.json and both package-lock version positions agree at 0.6.1; dependencies and release scripts are unchanged. Build staging dynamically includes root Python modules, covering `filename_identity.py`. The focused runner is explicitly not a formal entry/build gate. Exact artifact identity, full declared checks, packaged behavior and release promotion remain separate acceptance obligations, not conclusions of this source review.

## Fixed during review

- GCD lookup initially called `rules_stamp()` again when returning evidence. A concurrent pointer switch could label results from index A as belonging to B. The corrected return composes the code-rule prefix with the captured `active['rules']`; its pointer-switch regression requires a single active-pointer read.
- The collection fallback now requires an actual issue publication/sale year; it does not substitute series-start year when the issue date is unknown.
- The first focused test runner silently filtered out `unittest.loader._FailedTest` objects. The reviewed correction retains discovery failures and explicitly fails absent/empty requested modules. New tests create a genuinely broken requested module beside a passing control and separately check an absent requested module. This finding is resolved in the exact supplementary bytes below, not left as an advisory.

## Reviewed identity and verification limits

Product working-tree SHA-256 values independently read after the corrections and matching the reviewed source milestone:

| File | SHA-256 |
|---|---|
| app.py | bca8da7dbccc016e847e844ea741b6cdfa9d2f630a11ae3dfbb2d6a5eaf7ea07 |
| research.py | 41cb9918cc67bc9de8c0e0dd047f4752b03721653b7472b5c5d1472c7fd3d985 |
| filename_identity.py | 937978f1ad98743bde27fe9308539a31a04ee534847ce5e89b4d58e8754831fc |
| gcd_matching.py | 6b1b64203e039550ef32e2a1a4261c3f56781d10783d854e0634cf32bb904aa8 |
| gcd_offline.py | a98520f961e59bf8cbc7a4c817639df75745467430d3c9ac43a9debb69112f52 |
| metron.py | 8b87aad2dba391b4ff8858806684f49e6151975ed76859d89b7b1c3c24149747 |

Reviewed test-runner correction committed at the final endpoint, not a product change:

| File | SHA-256 |
|---|---|
| tests/run_naming_checks.py | ff3393e393a8ba594472e68cf632909f88c5bda3062f380841205d4cda9dd27e |
| tests/test_naming_runner.py | 62e38ebdda51c72035548ae9938a2bd536e8830ca7f28be05734549433f15559 |

Senua reviewed source and did not duplicate Ender's tests. Ender reported the final focused run as 103 tests, zero failures/errors/skips, 2.836 seconds, including the real isolation net and corrected runner's negative controls; this is attributed evidence, not an independently executed Senua result. `git diff --check` over the committed review range passed. Futaba owns independent pinned-source regression, archive sample, and packaged behavior verdicts. The developer's masked collection controls were explicitly insufficient as edition ground truth; they are not promoted to a successful precision measurement here.

No application launch, packaging, installer execution, live catalog/library/settings mutation, model/API access, or source/test modification was performed by Senua. No scratch output was created. This report does not certify a future artifact's hashes, native closure or updater behavior, and does not waive the required QA/promotion route.

## Verdict

- Total open Critical: 0.
- Total new unresolved Major/Minor in the changed construction: 0 / 0.
- Total inherited advisories carried: 2 Major (I1, I2), 1 Minor (i1).
- Safety floor: intact in the reviewed changes.

**Verdict:** RELEASE CLEAR

This is the construction verdict for the stated source range, including the corrected test runner. Sully still needs the independent version-matched QA clearance and exact accepted artifact/promotion evidence before publication.
