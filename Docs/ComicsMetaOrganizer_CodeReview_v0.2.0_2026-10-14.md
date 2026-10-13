# Code Review — Comics Meta Organizer v0.2.0

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-14
Tool: Comics Meta Organizer
Release: v0.2.0 source checkpoint
Commit range: 319202243fe7296f985c318a7b08cb5a0f05d140..3e1cc04f2aea7f0fe724a6062c53b9d5bcfe407b
Files changed: 133 files, +9419 / -455 (includes package lock, docs and binary assets)
Worktree: WIP/Comics Meta Organizer-m1
Reviewed HEAD: 3e1cc04f2aea7f0fe724a6062c53b9d5bcfe407b
Tree at review entry: clean
Stand-down dimensions: none; Electron-specific security checks apply
```

This range begins at the exact executable endpoint of the preceding v0.1.4 review. Its later reporting/release integration commits are included. This report certifies committed source construction, not a packaged artifact. Its own subsequent Docs-only addition does not change the reviewed executable endpoint; build and QA owners must bind their actual fresh input inventories independently. Any executable, test, version, package/native/runtime or execution-contract change after this endpoint requires a scoped recheck.

## Summary

The accumulated change separates mutable state from installed code, adds overlapping-library ownership locks and an Electron shell with setup, tray, graceful shutdown and explicit updates, introduces encrypted contextual key editing and server-owned per-comic recovery, and prepares held-input packaging and exact-artifact publication. Review covered the committed implementation and its approved setup/recovery/update contracts across all nine dimensions. No open Critical or safety-floor finding was established. One advisory Major and one new Minor are recorded below. Historical v0.1.4 Minor items remain carried unless their owner separately records closure.

The first actual standalone installer, native shell operation and installed prior→next update have not been certified. Source clearance must not be presented as meeting those release requirements. Futaba's separate actual artifact QA and the independently reviewed execution graph remain required.

## Evidence and limits

- Read-only Git status established clean HEAD above. Git log/stat and the accumulated production/test/doc diff were inspected; no test, application, native broker, build, provider, GPU, installer, release, live library or live service operation was executed by this reviewer.
- Read the committed FirstRunSetup, PerComicRecovery, UpdateOutcome, InstallerMilestones, PackagingHandoff and InstallerQAAcceptance contracts. The acceptance matrix explicitly requires real packaged installation, two actual installed update transitions, state preservation, verified recovery and native ownership evidence; mocks do not replace them.
- Inspected retained development evidence at `C:/Users/AnGeLZzZ/AppData/Local/Temp/illuminati-codex-cmo-installer-resume-20261013/ender/resume-offline-09-success-receipt.json` and its native receipt. Offline09 reports 788 Python tests: 736 passed, 52 explicitly deferred (47 DOM + 5 native conversion), 23 mocked Node tests, syntax checks of 135 Python / 28 Node files; actual outer/owner root exits and descendants are zero; elapsed 92,242 ms. This is development evidence, not final QA handoff or installer proof.
- Independently compared all 231 offline09 source file hashes with the checkpoint: changes are CHANGELOG, Brief, VERSION, package.json, package-lock.json and two packaging Python regex literals. Parsed package/lock differences are solely root version metadata. The two lexical regex changes match the retained qualification record and preserve the decoded regular expressions. No other listed tested source bytes differ. A fresh final artifact/source identity is still needed; historical test HEAD was 3283b74e6a614c3e5a03d2c4785798e1d8833b47 with pending source changes captured by its manifest.
- PackagingHandoff records runtime08's authenticated embedded CPython/package import and full7Zip format-listing proof, with actual zero native/root/descendant exits and complete before/after inventories. This proves a runtime preparation stage, not a built application, actual RAR fixture extraction, packaged launch or updater transition. Exact runtime/build execution clearance belongs to the independently assigned execution reviewer and is not inferred here.
- New recovery tests cover constrained fields/link retention, substantive/case/punctuation identity decisions, rejected URLs and malformed provider evidence, single-use confirmation, stale archive/evidence and post-write mismatch. Most confirmation/installer tests use mocked boundaries. Actual archive preview→save→read-back, Electron DOM and native installed workflows remain in Futaba's acceptance matrix.

## Rubric

Severity definitions and the always-blocking safety floor: Team/Docs/ProcessRules.md § Severity definitions.

### 1. Security

- Status: Pass. Electron renderer uses context isolation, sandboxing and no Node integration; main-frame sender checks and fixed IPC actions bound the bridge. Shell endpoints authenticate a private token, mutation endpoints check origin/Host, and recovery accepts provider IDs/allowed issue URLs rather than fetching arbitrary input URLs. Untrusted renderer strings use textContent. DPAPI stores user-bound ciphertext and public presence flags; saved keys are not returned to the renderer. Native child invocations use argument arrays or Windows command-line quoting; installer launch rehashes a held payload and refuses device/UNC/ADS/reparse paths. No secret or safety-floor leakage was established in this diff.

### 2. Correctness & Logic

- Status: Concerns.
- **F40 [Major] — `app.py:845`, `setup_state.py:157`, `setup_state.py:170`: setup commits config/credential generation and then releases its library claim before the server reacquires it in activate_setup.** A second state-root copy can claim that library in the interval; the response becomes library_busy although the durable setup already changed. The claim refuses processing safely, but the UI presents an ordinary failed save and lacks a distinct saved-but-not-started state. This is a static cross-process interleaving, not an observed native failure. Suggested next-cycle remedy: transfer/retain the setup claim across activation, or return an explicit durable-save/activation-failed result with safe retry semantics. Keep the existing fail-closed ownership and durable credential generation.
- Recovery correctness otherwise uses server-owned plans, bounded lifetime, explicit confirmation, signature/full metadata/evidence revisions and identity-only consequences; unrelated populated metadata and other Web entries are not intentionally replaced. Case-only and punctuation-only Series spelling is preserved through the existing provenance comparison.

### 3. Crash / Stability Safety

- Status: Pass. Broker owns an atomic kill-on-close Job and authenticated shell-owner pipe; root exit is followed by descendant closure before success. Startup has typed failure and bounded restart attempts. Graceful Quit and update installation are separate: installation has no force path; unknown installer startup remains stopped and explicitly unconfirmed. Setup, quit and installer native behavior still require actual packaged QA.

### 4. Performance

- Status: Pass. Shell polls lightweight status with one poll in flight; update operations serialize checks/download/install, progress updates are throttled, and pending recovery plans have a count/TTL bound. No measured new performance regression is established by the available development evidence. Large real libraries, runtime packaging and native update performance were not benchmarked here.

### 5. State & Data Safety

- Status: Pass. Runtime config/database/batches/work are under selected state root; resources/version/static code stay separate. Cross-state overlapping-library claims protect writers/conversion/backup removal, per-archive OS locks serialize same-state writers, and recovery checks full metadata before writing, records manual provenance and verifies read-back while retaining backup. A transient shell pause expires without overwriting durable user pause. Config/credential generation switches atomically; contextual keys use a generation-bound encrypted overlay without changing library/source settings. Real installed state preservation remains untested. F40 concerns outcome reporting after a durable commit, not permission to run a competing writer.

### 6. Input Handling

- Status: Pass. Library inputs must be absolute, existing and locally readable; optional keys reject multiline/NUL and trim only outer whitespace. Recovery schema, issue IDs, provider identity/date/image shape and preview token confirmation are validated. Invalid or stale evidence refuses mutation, and approved old/new fields are shown before the single-use write. Held build contracts bind exact source/runtime/native inputs and output inventories; actual execution approval remains separate.

### 7. Maintainability

- Status: Concerns.
- **F41 [Minor] — `desktop/main.cjs:65`, `static/comic-recovery.js:59`: multi-stage lifecycle/IPC and recovery/key form branches are compressed into very long lines.** This makes security-sensitive async context, save outcomes and cancellation paths harder to audit and extend. Suggested next-cycle remedy: format and extract named handlers without changing behavior, then run the existing focused checks. The concern is construction clarity; it is not an additional release gate.

### 8. Doc/Code Drift

- Status: Concerns. Carried F28 remains: historical brief/app descriptions and milestone intake wording predate the new desktop implementation (for example `app.py:1` still claims standard-library-only; InstallerMilestones:19 says no shell exists). Current Brief and acceptance docs accurately label installer/update certification as pending. Historical phase notes should be clearly treated as dated intake, not launch instructions. No new duplicate finding is added for this carried drift.

### 9. Build & Release Hygiene

- Status: Pass for source construction. VERSION/package/lock identify 0.2.0 and parsed lock differences from tested input are version-only. Legacy direct preparation/build paths refuse unreviewed execution; supported packaging stages snapshot held source/runtime/native closures, disable publication during build and require matching staged versions and source mappings. Promotion requires exact QA-cleared production artifacts, named version reports, a matching remote named-tag commit and remote digest verification before bounded keep-four cleanup. The source checkpoint is published; an actual installer, real installed update and final matching QA receipt/report remain absent and must precede an installer-ready claim or promotion. This Pass does not authorize any build/publication command or clear its external execution graph.

## Finding dispositions

| Finding | Severity | State | Start point |
|---|---|---|---|
| F40 | Major | New, advisory | app.py:845; setup_state.py:157 |
| F41 | Minor | New, advisory | desktop/main.cjs:65; static/comic-recovery.js:59 |
| F11–F15, F19, F25–F28, F30, F31 | Minor | 12 carried from the v0.1.4 report; no claimed closure in this review | Prior versioned report |
| F32–F39 | Prior findings | Remain closed at the previous reviewed endpoint; no reopening established | Prior versioned report |

## Verdict

- Total Critical: 0
- Total Major: 1 new advisory
- Total Minor: 13 (12 carried + 1 new)
- Safety-floor violations: 0

**Verdict:** RELEASE CLEAR

This is the source construction verdict for the exact range and endpoint above. It is not installer readiness, artifact certification, final QA GO, runtime/build execution approval, update-install authorization or live-state migration clearance. The actual first standalone artifact and user-required installed prior→next transitions remain pending independent evidence and Futaba's verdict. Only the review report was written; no executable source, Git/config/hooks/trust, native/user state or live process was changed. No disposable build/probe output was created by this review.
