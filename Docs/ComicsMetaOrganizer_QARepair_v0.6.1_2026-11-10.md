# 0.6.1 QA blocker repairs — 2026-11-10

Base: `3783bb611ea36c701bd169ef1c96e1eadd0312bd`, version remains 0.6.1. Source-only repairs; no matching rules, frontend behavior, installer, live state, or release policy changed.

## Causes and fixes

The prior actual 1,074-test failure receipt and exact 15 names remain in [DevHandoff](ComicsMetaOrganizer_DevHandoff_v0.6.1_2026-11-10.md) and [EntryEvidence](ComicsMetaOrganizer_EntryEvidence_v0.6.1_2026-11-10.json). These affected files were unchanged between that tested source and the repair base, so the saved failures are the red evidence.

- Three child-process fixtures relied on cwd imports. Embedded Python's intentional `._pth` ignores cwd/PYTHONPATH. Pass the controlled source root explicitly in the state-root, library-lock, and QA-runtime child bootstraps; preserve their state/lock/exclusion assertions.
- Failure-filter fixtures predated PerComicRecovery and KeysEntry. Serve the actual recovery JS/CSS plus offline evidence; assert current approved recovery actions, identity-specific accessible retry name, raw error and attempt count, close behavior, and no JavaScript exceptions. Update exact row/key text to the approved existing UI, without changing production copy.
- Backup fixtures used module-import timestamps with an advancing browser clock. Freeze the browser at the same whole-second fixture instant. This avoids both elapsed-suite drift and Date's fractional-millisecond truncation; retain the exact 12-minute assertion.
- UpdateStats fixtures assumed one ICU typography and a fixed label count. Preserve the fixed DST wall-clock vectors/order/repeat suffixes while formatting numeric hours as specified by Intl; verify the smallest label step against actual SVG/font measurements, exact labels, and clipping. Production frontend stays unchanged.
- Three DOM evidence tests lacked `COMICS_TEST_EVIDENCE` in the prior controller. The corrected owned route supplies a private evidence directory; the eventual formal controller must do the same.
- `-I` ignores `PYTHONUTF8`. Add explicit `-X utf8` in `scripts/check-python.cjs` so non-ASCII output satisfies the unchanged supervisor's strict byte comparison. New `tests/test_check_python.py` executes the real launcher's flags with real embedded Python, checks Unicode output, and removes the option as a negative control while leaving the environment variable set.

Approved UI references: PerComicRecovery (2026-10-14), KeysEntry (2026-10-16), UpdateStats including addenda (2026-10-26).

## Verification

- Non-browser focused run: **38 passed**, 2.274 seconds; no skips. Real first/last state isolation; normal owned closure, complete output, native zero.
- Post-environment-repair focused run: **130 tests**, 45.672 seconds, three fixture failures, no errors/skips. All prior import, Intl, measured-width, and evidence-directory cases passed. The three remaining exact failures exposed the retry accessible name, two conflict sentences, and fractional clock precision; corrected only those two fixture files.
- Final affected-module verification: **23 passed**, 7.903 seconds, no errors/failures/skips. Only the two changed DOM modules plus first/last isolation were selected after full discovery. The three remaining cases passed; actions, exact ages, copy, accessible names, and layout checks remain enforced. Source hashes matched before/after; normal owned closure, complete output, native zero, verified browser remaining zero, and personal folders clean.

Actual focused output, closure, source hashes, and OS before/after proof are retained in [QARepairEvidence](ComicsMetaOrganizer_QARepairEvidence_v0.6.1_2026-11-10.json). These are focused source results, not a formal gate or release acceptance.

All focused routes perform full discovery before filtering and retain loader failures, missing-module failures, and the live-state sentinel. They use the existing byte-pinned 600,000 ms private-Job owner, authenticated Node 26.12.1, prepared embedded Python 3.14.8, and canonical owned Chrome lease. No direct browser spawn or test exclusions replace the checks.

## Private profile environment

Two pre-test browser startups failed before Python ran; retain these separately from test failures. A read-only Windows KnownFolder probe then proved LocalAppData failed with `0x80070002`: the flat private `profile/Local` environment disagreed with the OS path `profile/AppData/Local`, which did not exist. Create only the owned standard AppData hierarchy and align environment variables. The same non-creating API queries then returned HRESULT zero, existing private paths for Local/Roaming, with both default and DONT_VERIFY flags.

Before the actual successful browser run, repeat the probe under its exact environment. The canonical relay does not override env; holder CreateProcessW inherits it. Keep the browser profile under the short owned TEMP parent, retain logging outside its automatically removed profile, and require verified headless closure, personal-folder cleanliness, and native zero. This demonstrates the repaired environment worked; it does not prove every earlier startup failure had one cause. The recorded all-process CPU-rate/memory sample is diagnostic, not a timing verdict.

## Remaining handoff

Sully must pin the repaired source before a fresh build and unchanged full entry gate. Preserve all four naming fixes and all safety guards. Prior source/native passes and the old installer do not substitute for a new full gate, genuine isolated install/update proof, or the publisher's actual required evidence. No tag, publication, installation, live app restart, or GCD refresh occurred in this repair work.
