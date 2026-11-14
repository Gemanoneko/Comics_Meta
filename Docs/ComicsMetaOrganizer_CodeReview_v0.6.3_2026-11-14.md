# Code Review — Comics Meta Organizer v0.6.3

## Header

```text
Reviewer: Senua (Code Reviewer)
Date: 2026-11-14
Tool: Comics Meta Organizer (Comic Metadata)
Release: v0.6.3
Commit range: 516c812d90b9482f5cd63003d660f178e0c65444..61a3507a605afa4cb6e96320d7b42c4a2f137cd0
Files changed: 87 files, +14189 / -129, including documentation and previously reviewed tooling
Candidate commit: 61a3507a605afa4cb6e96320d7b42c4a2f137cd0
Stand-down dimensions: none
```

## Summary

The previous 0.6.1 app review ended at 516c812; its separate QA tooling was reviewed through d7c0e14. The 0.6.2 source review covers the startup and conversion changes through 117c6b5 and remains applicable: 0.6.3 adds only eight tray PNGs, version and changelog changes in 117c6b5..61a3507. All eight PNGs decode at the expected 16×16 or 32×32 RGBA sizes and the unchanged loader selects their exact names and scale representations. The following findings carry forward from the 0.6.2 review; counts include inherited advisories once.

## Rubric

### 1. Security

- Status: Pass. The cumulative source review covers authenticated startup, same-origin POST, renderer isolation and process argument boundaries; the tray delta introduces no executable code.

### 2. Correctness & Logic

- Status: Concerns.
- **M1 [Major]** `app.py:289`: the scan's case-sensitive SQLite path range misses previously catalogued paths when the same Windows folder is scanned with different letter casing. Conversion-view recheck separately uses case-insensitive scope. An in-memory SQLite control selected the original case and missed the alternate case.
- **I1 [Major, inherited]** `gcd_matching.py:128`: content matching does not establish edition-specific ISBN/GTIN equivalence; see the 0.6.1 review for the digital/print example and established field policy.
- **I2 [Major, inherited]** `automatic.py:674`: mixed-provider synopsis Notes can omit GCD attribution because queued metadata does not establish its provider.

### 3. Crash / Stability Safety

- Status: Concerns.
- **M3 [Major]** `engine_host.py:182`: a claim-retirement exception after the Job has emptied overrides the broker closure result and skips remaining explicit handle cleanup; the shell then refuses automatic retry as closure unconfirmed. This preserves fail-closed behavior but a claim-folder failure can strand the app until manual recovery.

### 4. Performance

- Status: Pass. Reconciliation groups parent enumeration, leaves unrelated disk checks outside SQLite writes, and startup has separate reachability and overall deadlines.

### 5. State & Data Safety

- Status: Concerns.
- **M2 [Major, inherited identity gap]** `archive_conversion.py:161`: a source can change after the new catalog signature check but before the pre-existing converter captures its own signature. The converter can process and remove the replacement after existing verified-CBZ checks; a changed catalog row can prevent the guarded update and immediate rescan. Review did not establish a new path removing a source without the existing CBZ verification.
- The new reconciliation marks only unchanged rows absent; inaccessible directory/stat errors retain them and no archive or history is deleted. Claim retirement follows owned Job closure and checks matching unlocked claims.

### 6. Input Handling

- Status: Concerns.
- **i1 [Minor, inherited]** `local_model.py:99`: GIF/BMP credits enumeration remains incomplete, as recorded in the 0.6.1 review.

### 7. Maintainability

- Status: Pass. The tray change reuses the existing two-scale loading contract and startup retains an explicit process ownership contract.

### 8. Doc/Code Drift

- Status: Concerns. The edition-identity qualification underlying I1 remains applicable; prior-version QA evidence is not represented as 0.6.3 acceptance.

### 9. Build & Release Hygiene

- Status: Pass. VERSION, package and lockfile identify 0.6.3; `git diff --check` passed across the stated range. The 0.6.2 review independently checked candidate runtime-manifest hashes, the Git/Chrome/PowerShell executable hashes and valid signatures, but did not independently rehash full runtime inventories.

## Verification and limits

This is construction clearance for the exact source commit above, not proof of installer behavior, a completed entry gate, release promotion or GitHub publication. Eight tray files were decoded read-only; visual behavior belongs to QA. No live-library writes, installer launch or VM activity were performed. The existing ordinary installed update proof is tied to actual Windows Sandbox guest identity and lifecycle; its strict receipt rejects QA-mode profile isolation. No equivalent supported no-VM ordinary installed update proof was identified in the reviewed route, and historical 0.6.1 proof cannot be relabeled as a 0.6.3 run.

## Verdict

- Total open Critical: 0.
- Total open Major: 5 (M1, M2, M3, I1, I2).
- Total open Minor: 1 (i1).
- Safety floor: intact within the reviewed source scope.

**Verdict:** RELEASE CLEAR
