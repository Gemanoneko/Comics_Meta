# Comics Meta Organizer 0.6.1 — QA, November 10, 2026

**Verdict:** NO-GO

Status: focused source regression and the actual packaged native smoke pass, but the corrected canonical full entry **failed: 1,074 Python tests, nine failures, six errors and one skip**. The actual receipt reports `check fail (owned check)`; the shell check did not run. Release remains blocked. No old failing-gate exception is inherited, no failure is waived by the focused/native successes, and no release or live installation occurred.

## Identity and source regression

- Built source: `f7cc220d2eda160fea5c3ba3a8b6898c55938119`, version `0.6.1`. The earlier source product fixes and corrected source-check runner are certified at `f64441e95a1381daa9a0448901d46f85cd2951b7` in `ComicsMetaOrganizer_SourceQA_v0.6.1_2026-11-10.md`; later source commits preserve product bytes and QA/review records.
- Independent focused source result: **103 passed, zero failures/errors/skips**, with real live-state isolation and final sentinel, no descendants and a 600000 ms watchdog. Tested a pinned git-archive copy; all 333 archived source files remained byte-identical, no extras.
- Bounded read-only collection sample: 15/15 titles agree, 13 print the matching volume/Book number. Only five explicit publication-year controls were available; physical/digital binding and ISBN precision are not globally established. No wrong collection identity was observed. The sample is deterministic, not a statistical population-wide precision estimate; the detailed source report records digital-versus-print identifier limitations and the inherited approved GCD policy.

## One actual packaged native smoke — PASS

The exact `candidate/dist/win-unpacked/ComicMetadata.exe` was launched once through the Senua-cleared adapter and the unchanged canonical private Windows Job owner. No installed app was launched, stopped or updated.

- Installer: `Comic-Metadata-Setup-0.6.1.exe`, **149,538,471 bytes**, SHA-256 `bf4fe3babcf5eb7a717102d7f220e2ff8b193e7913b527fe26310341224bec6f`.
- Package inventory: **621 files**, every file hash and membership identical before/after the native run.
- Durable complete 621-file inventory and adapter pins: `Docs/ComicsMetaOrganizer_NativeQA_Package_v0.6.1.json`, SHA-256 `c00dc5af107f9998364fb3d763e78f1ccff7be5f14b2f114a4cb2f814c8283a4`.
- Pinned outer invocation: `C:/Program Files/nodejs/node.exe <release-root>/native-qa-adapter/run-native.mjs`, with no arguments. Outer Node SHA-256 `14319838b3f355e0398c13569a90270bce4fc68f25189f58c59b03dadae0e6d5`. Release root: `C:/Antigravity Projects/Studio Illuminati/WIP/Comics Meta Organizer/scratch/release-061-20261110`.
- Reviewed adapter hashes: outer `cd4cd4503b4b8bad124f215bbc44e7747016ecd4c69a05238e27903fc08757cb`; adapter manifest `c00dc5af107f9998364fb3d763e78f1ccff7be5f14b2f114a4cb2f814c8283a4`; smoke `3adf1758f4a14069420949878f376da72a292fbeccc84db4d8943110b7a174f0`; guards `bac42d0c230500f173d537352ea1920a67d662f158c55abc6a11f8ba61fafeee`.
- The inspector target was bound to the exact spawned PID/executable and private QA policy before guard installation. Native app PID **55304**, real engine-host PID **57896**. Production shell reported `packaged: true`, version **0.6.1**; its one actual `resources/app.asar/desktop/setup.html` window was loaded, `offscreen: true`, `visible: false`, `focused: false`. Real private engine status returned HTTP 200, `owned: true`, `configured: false`.
- All profile, state, cache, locks and TEMP paths were inside a fresh private policy root. Private service/model/feed ports excluded the live service/model ports. Visibility/focus/shell guards recorded **zero violations**. Feed requests **0**; model requests **0**. No library workers, live library processing, desktop input or GPU/model use were requested.
- The captured actual native tray menu contained enabled Quit. The harness invoked that real menu callback. App exited naturally **code 0, signal null**. The outer owned run also returned **code 0**, `closed: true`, `forced: false`, `timedOut: false`, `outputComplete: true`.
- Final native ownership: active/assigned/listed/unsignaled **0**; `complete: true`, `zero: true`, 12 retained descendants. All 2,043 ownership queries were complete. This establishes natural Quit and complete owned closure.
- Actual semantic run timestamps: `2026-11-10T10:17:23.161Z` to `2026-11-10T10:17:25.560Z`. Policy SHA-256 `d562d7af2642ecbec24136b0bb2ea9abb4e5754dbe94593b7bd29845863c0da7`.
- Durable raw native evidence: `Docs/ComicsMetaOrganizer_NativeQA_v0.6.1.json`, SHA-256 `44ef33ecc674b2628cad641f1c82d28f8bd68f642fd9aaeb25af0a9fdd024fca`. Original: `<release-root>/native-qa-adapter/native-owned.json`.

## Full declared entry and limits

The initial Edge lease failed to publish DevTools within 30 seconds, before any checks. A narrowly reviewed Chrome alternative started correctly, but the checker refused unreviewed ancestor npm configuration before checks. Neither produced a formal receipt. The supported working-location correction then reached the **one actual full suite**. No full gate was repeated after tests ran; Futaba performed no additional full invocation.

The final immutable context SHA-256 was `4c92e35761396ec6f9a20757e7e6764db41b5666a27f0c399a7d7dfb8838856c`, bound to the same tested source `f7cc220d2eda160fea5c3ba3a8b6898c55938119` (dirty N). Later documentation HEADs do not change that tested build identity. Its run parent was `C:/Antigravity Projects/Illuminati-QA/CMO-061-20261110`.

Actual full result: **1,074 Python tests in 174.007 seconds; nine failures, six errors, one skip**. The declared `check:shell` did not execute because the Python check failed. The canonical inner check also reported `Final supervisor output differs from streamed bytes`, `outputComplete:false` and forced closure, with a final complete native zero observation. That output proof is failed, not passed.

The outer invocation took **220.279 seconds**, exited 1 and closed normally with complete output and final complete native zero (active 0, unsignaled 0). Two intermediate incomplete membership observations remain in the raw record; they are not earlier zero proofs. Canonical Chrome lease `27e5fba7b7c5` closed with `verified:true`, `remaining:0`, and a clean personal-folder comparison.

The following is the actual developer receipt, retained from the observed full invocation; Futaba did not independently rerun that full gate or manufacture a receiver receipt:

```text
Entry-check receipt v2: comic-metadata v0.6.1 @ f7cc220d2eda160fea5c3ba3a8b6898c55938119 (dirty: N) [source:985ba6cf7e14de464de4abd509bff49d029d6a9786cc9b0d6ffb1d14ba15c85a; harness:6b193dc7e214f17fc2277715b2c27e9785018b961b2e1e6e24dbf211f3398bb5; runtime:9c4dc46eb53a36a2b99bc517128c2c58c31464bc261890133dd97be30571fc14; checker:4bae2cde4e4cdd2f22fb3060571730ec32fec1dd5403ea070086973b18b695e4] — pre-qa n/a, post-build n/a, check-electron n/a, check fail (owned check), test:smoke n/a; personal-folders clean
```

Raw final evidence under the release root: `entry-chrome-location-owned.json`, SHA-256 `45c6570b540d41e6b76d1628c0c454a182392cffa742356be4dabf8da12a7c43`; `entry-chrome-location-result.json`, SHA-256 `73972f89da00bd165eda3e681676c0a73eb543338ce85330f9eb7454708d3768`. The developer handoff records the complete exact fifteen-case list and saved-output classification: `Docs/ComicsMetaOrganizer_DevHandoff_v0.6.1_2026-11-10.md`.

Failure disposition from saved output, without new execution:

- **Six exact historical cases:** the three failure-filter DOM cases, two clock-sensitive kept-backup cases and embedded-Python state-root child case. Their historical identity does not grant acceptance for 0.6.1.
- **Three concrete controller omissions:** folder-help, verification and Yandex DOM rectangle tests lacked required `COMICS_TEST_EVIDENCE`. These are harness errors, not an app diagnosis.
- **Six other new observations remain unaccepted:** update-stat label-count timeout; library-lock child handshake; QA-runtime child `qa_runtime` import failure; and three daylight-saving chart H-versus-HH formatting failures. A suspected common runtime family is not a proven cause or historical waiver.

No failed case names a new filename-matching test. The focused 103 source controls remain passed, but the full result does not establish release acceptance. Correcting the harness omissions, diagnosing the remaining observations and resolving the failed output proof require a separately scoped follow-up, not automatic reruns or test exclusions.

Publication is also blocked by missing actual isolated installation/update proof. The unpacked private first-run smoke is not an installed-update or ordinary-profile sandbox test.

The native smoke covers safe private first-run startup and actual tray Quit. It does not certify installed-profile processing, real comic writeback, native mouse/keyboard/file-picker behavior, installation/update transitions or every dashboard page. No live settings/catalog/library, installed app, registry cleanup or published release was changed by Futaba.

Pattern alerts: none.

## Owned output

The actual build/artifact, prepared inputs and failed full-entry evidence are preserved for diagnosis; they are not published or declared verified disposable. The private native policy/profile root contains 47 files / 1,903,509 logical bytes (measured by recursive file enumeration and summing lengths). After durable evidence archival, one transparent native PowerShell removal of that exact UUID policy/profile root, with a resolved-path check, was rejected before launch by automatic execution policy with only `blocked by policy` supplied. The root remains; no alternate deletion or retry was attempted. Active build inputs were excluded. Earlier source-QA cleanup rejections remain recorded in the source report and were not retried. Across all three rejected Futaba QA roots, **819 files / 61,609,739 logical bytes** remain; the separately rejected empty Ender folder also remains. No alternative deletion against those roots or parents was attempted.
