# Code Review — Comics Meta Organizer v0.6.2

## Header

```text
Reviewer: Senua (Code Reviewer)
Date: 2026-11-14
Tool: Comics Meta Organizer (Comic Metadata)
Release: v0.6.2
Commit range: 516c812d90b9482f5cd63003d660f178e0c65444..117c6b5b84485a49e968ded430f0230d011472e4
Files changed: 79 files, +14183 / -129 (including historical documentation and previously reviewed tooling)
Candidate commit: 117c6b5b84485a49e968ded430f0230d011472e4
Stand-down dimensions: none
```

## Summary

Reviewed the committed startup recovery, scan/conversion reconciliation, dashboard and icon changes. The previous app review ended at 516c812; its separately hashed QA tooling was reviewed through d7c0e1415d5162887d99edb0b08e019635501c00. The actual new candidate commit on the subsequent documentation/tooling history is c4247e54bfa674af366830b95ea9177d4ee80873..117c6b5b84485a49e968ded430f0230d011472e4 (39 files, +627 / -99). This is construction review of the named source, not installed behavior QA, installer clearance, release promotion, or a claim of successful VM execution. The user prohibited VM use; no VM was allocated or run.

## Rubric

### 1. Security

- Status: Pass. The new recheck is explicit POST and retains exact loopback Origin and Host checks; the early startup endpoint requires the private shell token. Electron renderer isolation and fixed process argument boundaries are retained.

### 2. Correctness & Logic

- Status: Concerns.
- **M1 [Major]** `app.py:289`: scan reconciliation selects rows with a binary SQLite path range. A prior `C:\Library\...` row is not selected by an otherwise equivalent `c:\library\...` scan on case-insensitive Windows, so missing catalog entries can remain live. An in-memory SQLite positive control selected one row for the original spelling and zero for the alternate spelling. The conversion view's separate on-open recheck uses the case-insensitive scope and can reconcile unsupported rows independently.
- **I1 [Major, inherited]** `gcd_matching.py:128`: edition-specific ISBN/GTIN equivalence is not established by matching collection content; see the v0.6.1 review for the digital/print example and established field policy.
- **I2 [Major, inherited]** `automatic.py:674`: mixed-provider synopsis Notes can omit GCD attribution because `outcome == 'queued'` does not establish the provider supplying metadata.

### 3. Crash / Stability Safety

- Status: Concerns.
- **M3 [Major]** `engine_host.py:182`: a claim-retirement exception after the Job has emptied overrides the broker closure result and skips the remaining explicit handle cleanup; the shell sees unconfirmed closure and refuses automatic retry. The fail-closed outcome prevents an unsafe restart, but a transient claim-folder failure can strand the app until manual recovery.

### 4. Performance

- Status: Pass. Folder enumeration is grouped per parent; disk/share inspection occurs outside SQLite write transactions, and startup has distinct response and overall deadlines.

### 5. State & Data Safety

- Status: Concerns.
- **M2 [Major, inherited identity gap]** `archive_conversion.py:161`: a source may change after the new catalog signature check but before `convert()` captures its own signature. The pre-existing converter then works on the replacement and may remove it after its existing verified-CBZ checks; the stale catalog row can fail the later guarded update and skip the immediate rescan. The old conversion/removal sequence predates this release; this review did not establish a new path that removes a source without the existing CBZ verification. Bind the selected catalog identity through conversion and recheck before destructive transitions in the next cycle.
- Reconciliation only marks unchanged catalog rows absent; inaccessible parent enumeration or stat failures retain rows. The operation does not delete archive files or history. Claims are retired only after the broker observes its Job empty and only when matching unlocked owned records.

### 6. Input Handling

- Status: Concerns.
- **i1 [Minor, inherited]** `local_model.py:99`: GIF/BMP credits enumeration remains incomplete, as recorded in the v0.6.1 review.

### 7. Maintainability

- Status: Pass. Source and shell startup phases preserve an explicit authenticated readiness contract and a separate owned-process closure path.

### 8. Doc/Code Drift

- Status: Concerns. The prior review's edition identity qualification remains applicable to I1; historical QA and release evidence is not reused as evidence of a 0.6.2 installed flow.

### 9. Build & Release Hygiene

- Status: Pass. Version files and lockfile agree at 0.6.2; `git diff --check` passed for the stated range. Git, Chrome, and PowerShell runtime manifest files match their hashes in Sully's candidate configuration; their named installed executables match the respective manifest entries and have valid Authenticode signatures. This check did not independently rehash each complete runtime inventory or execute the entry gate.

## Verification and limits

Source and producer/consumer contract review covered same-origin POST, authenticated startup, failure and retry/closure paths, claims, changed catalog rows, inaccessible paths, scan filtering, rendering request invalidation, process ownership, and conversion verification. The SQLite casing control was in-memory. No full suite, installer, GUI, live-library write, VM, or promotion was performed for this review. Prior QA acceptance belongs to its named version and source. Exact product/source commit is 117c6b5b84485a49e968ded430f0230d011472e4; later code changes require renewed review.

## Verdict

- Total open Critical: 0.
- Total open Major: 5 (M1, M2, M3, I1, I2).
- Total open Minor: 1 (i1).
- Safety floor: intact within the reviewed source scope.

**Verdict:** RELEASE CLEAR
