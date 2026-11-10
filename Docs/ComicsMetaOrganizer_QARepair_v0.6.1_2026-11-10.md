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

Sully pinned the repaired source at `8e66ca4d14ec5a052e9967d6af2590ef957142aa` (tree `563e6e735ac45a3c3cbb794c41907e680a6ed90d`). The clean detached clone and immutable exported snapshot each matched all 345 raw CRLF source files; the unrelated in-progress install/update adapter was excluded. Raw source-manifest SHA256 is `11b971aef5739c9e2e8e3b46094509728b87e2bee98e685237e29116c05e6ad3`; this is the legacy publication sourceIdentity, distinct from the canonical entry's normalized source digest.

Fresh unchanged lean build: **BUILD OK**, outer 53.019 seconds, normal closure/native zero, no generated BUILD_UNINSTALLER execution, reference equality true. Installer: 149,538,466 bytes, SHA256 `718590fb3524cf2ba9b7544c92ca94a2698a47fd26e64185cf3aae18af7f736d`. Unpacked engine version is 0.6.1. The install/update owner measured all 621 packaged files once: no changed/missing/extra member versus the earlier native-QA package by path, size, and SHA256. The new installer is still a distinct artifact and requires genuine installation/update testing. [Actual build evidence](ComicsMetaOrganizer_BuildEvidence_v0.6.1_Repaired_2026-11-10.json).

Fresh canonical full gate: **check pass**. Python ran 1,075 tests in 119.134 seconds, zero failures/errors; one file-link subtest skipped for unavailable Windows symlink privilege (WinError 1314). The subsequent actual shell check ran 50 tests: 48 pass, zero failures, two existing opt-in controls skipped because COMICS_META_TEST_BUILDER_MODULES and COMICS_META_TEST_ACTUAL23_JOBROOT were not set. No exclusions, assertion masking, guard weakening, or prior failing-gate exception was used. Report these limits explicitly. Outer runtime 185.205 seconds; inner and outer normal code zero, complete output, and native zero. Headless closure verified remaining zero; personal folders clean. [Actual full output](ComicsMetaOrganizer_EntryEvidence_v0.6.1_Repaired_2026-11-10.json), [closure](ComicsMetaOrganizer_EntryClosure_v0.6.1_Repaired_2026-11-10.json).

Actual sender receipt:

```text
Entry-check receipt v2: comic-metadata v0.6.1 @ 8e66ca4d14ec5a052e9967d6af2590ef957142aa (dirty: N) [source:0d809a5da511d8e48b5c501f46e7af92dad38bc0ab3247fc4eee9d4cf1629dd2; harness:6b193dc7e214f17fc2277715b2c27e9785018b961b2e1e6e24dbf211f3398bb5; runtime:9c4dc46eb53a36a2b99bc517128c2c58c31464bc261890133dd97be30571fc14; checker:4bae2cde4e4cdd2f22fb3060571730ec32fec1dd5403ea070086973b18b695e4] — pre-qa n/a, post-build n/a, check-electron n/a, check pass, test:smoke n/a; personal-folders clean
```

Preserve all four naming fixes and all safety guards. A receiver must independently obtain the same canonical receipt; genuine isolated install/update QA and the publisher's required evidence still remain. Tag/source identity must stay on the actual built 8e66ca4 source even if later tooling/docs commits advance main. No tag, publication, installation, live app restart, or GCD refresh occurred in this repair work.
