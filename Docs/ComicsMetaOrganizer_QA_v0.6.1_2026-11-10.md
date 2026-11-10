# Comics Meta Organizer 0.6.1 — QA, November 10, 2026

**Verdict:** NO-GO

Status: focused source regression and the actual packaged native smoke pass. The declared full entry failed before any checks because the headless Edge fixture did not publish DevTools within 30 seconds; no formal receipt was produced. Release clearance remains blocked pending that route's diagnosis; no inherited failure exception is assumed. This NO-GO does not assert a product failure.

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

Ender's single declared full-entry attempt used its own canonical headless lease, but the Edge fixture failed to publish DevTools within 30 seconds before any declared checks. There is no formal receipt and no full-check result to certify. Its context SHA-256 was `211869a1a4a0441d3564ff5c1fda4f0cb541cbe0bd2cd9c13cb7815ac89419c2`, bound to source `f7cc220d2eda160fea5c3ba3a8b6898c55938119`. Ender owns scoped diagnosis; no duplicate full invocation was performed by Futaba. The focused 103 source tests and packaged smoke do not replace the missing entry result; no failed check is called passed or n/a, and no historical exception is inherited automatically.

The native smoke covers safe private first-run startup and actual tray Quit. It does not certify installed-profile processing, real comic writeback, native mouse/keyboard/file-picker behavior, installation/update transitions or every dashboard page. No live settings/catalog/library, installed app, registry cleanup or published release was changed by Futaba.

Pattern alerts: none.

## Owned output

The active build/artifact and adapter evidence are preserved for release. The private native policy/profile root contains 47 files / 1,903,509 logical bytes (measured by recursive file enumeration and summing lengths). After durable evidence archival, one transparent native PowerShell removal of that exact UUID policy/profile root, with a resolved-path check, was rejected before launch by automatic execution policy with only `blocked by policy` supplied. The root remains; no alternate deletion or retry was attempted. Active build inputs were excluded. Earlier source-QA cleanup rejections remain recorded in the source report and were not retried.
