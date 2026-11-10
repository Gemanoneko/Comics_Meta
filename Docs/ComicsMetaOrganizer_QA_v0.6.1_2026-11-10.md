# Comics Meta Organizer 0.6.1 — QA, November 10, 2026

**Verdict:** NO-GO

Status: the repaired canonical full entry **passed independently for sender and receiver**, with identical actual receipts on source `8e66ca4d14ec5a052e9967d6af2590ef957142aa`. Both ran 1,075 Python tests with zero failures/errors and one Windows-capability skip, followed by 50 shell tests (48 pass, zero fail, two explicit opt-in skips). The earlier focused source and byte-identical unpacked native-payload proofs remain valid within their scope. Overall release clearance remains **NO-GO**: the first genuine Sandbox processing-phase attempt stopped before any installer because unique compute ownership could not be established; the unused paused phase was not launched. Both actual installation/update flows remain unverified. No historical failing-gate waiver is used.

## Identity and source regression

- Current built/tested source: `8e66ca4d14ec5a052e9967d6af2590ef957142aa`, version `0.6.1`, clean matching clone and immutable 345-raw-file snapshot. Canonical source digest: `0d809a5da511d8e48b5c501f46e7af92dad38bc0ab3247fc4eee9d4cf1629dd2`; raw publication source-manifest SHA-256: `11b971aef5739c9e2e8e3b46094509728b87e2bee98e685237e29116c05e6ad3`. Later documentation HEADs do not change this identity.
- Current installer: **149,538,466 bytes**, SHA-256 `718590fb3524cf2ba9b7544c92ca94a2698a47fd26e64185cf3aae18af7f736d`, under `scratch/qa-repair-061-20261110/candidate/dist/`. The build evidence and complete 621-file comparison establish identical unpacked path/size/hash membership versus the native-tested payload. This new installer is a distinct artifact and has no installation/update acceptance merely because its payload matches.
- Historical initial built source: `f7cc220d2eda160fea5c3ba3a8b6898c55938119`. The earlier naming fixes and corrected focused source-check runner were independently certified at `f64441e95a1381daa9a0448901d46f85cd2951b7` in `ComicsMetaOrganizer_SourceQA_v0.6.1_2026-11-10.md`. Old failed/full and native evidence below retain their actual tested identities.
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

## Repaired full declared entry — independent sender and receiver PASS

The actual canonical CLI argv, immutable context, full unfiltered check graph, source/runtime/checker/harness digests and exclusive lock were the same on both sides. Context SHA-256: `3a9638511c42f8c446cd9c9ea95ff1120173d698e5d84f7301d5e55261c5d246`. The receiver used fresh private profile, TEMP, browser lease, evidence and result paths; it did not copy the sender's pass result.

Futaba executed exactly one Senua-cleared independent receiver wrapper: authenticated private Node `scratch/release-061-20261110/node-v26.12.1-win-x64/node.exe` plus `scratch/qa-repair-061-20261110/receiver-owned.mjs`. Verified wrapper SHA-256 `e2cbb863ad5458988ccedfc978c49dcf9046d14fd1eaa53a1a3c69c602af7818`; controller `0ddb7a8dc67be05b474b002e33336b5fc399798462a91d1719a334e832b0980b`; successful sender record `7d19e7283c54211818cf8f158128d1b67dbf8cfea8811a1affb443a8d728b37a`. No duplicate or failure retry was performed.

- **Sender:** Python 1,075 tests in 119.134 s, zero failures/errors, one capability skip; shell 50 tests, 48 pass, zero fail, two opt-in skips. Outer 185.205 s, normal code 0, complete output, verified headless closure, native zero and personal folders clean. Actual proof: `ComicsMetaOrganizer_EntryEvidence_v0.6.1_Repaired_2026-11-10.json` and corresponding repaired closure record.
- **Independent receiver:** Python **1,075 tests in 119.853 s**, zero failures/errors, one capability skip; shell **50 tests in 5.256 s, 48 pass, zero fail, two opt-in skips**. Inner `check` code 0, `ok/closed/outputComplete:true`, `forced/timedOut:false`, complete native zero; 8,207 complete membership queries with none incomplete. Outer **187.109 s**, normal code 0, complete output, unforced/untimedout, final active/assigned/listed/unsignaled zero, complete true, zero true, 644 retained descendant handles. Three intermediate membership observations were incomplete while work was running and remain in raw evidence; they are not earlier zero proofs.
- Canonical receiver Chrome lease `de409a9a3f63` closed with `verified:true`, `remaining:0`; personal-folder comparison clean (seven folders, ten drive roots watched). The actual receiver environment's four non-creating KnownFolder queries (Local/Roaming, default/DONT_VERIFY) all returned HRESULT `0x0`, existing paths inside its private profile.

The **actual sender receipt**, read from its retained output:

```text
Entry-check receipt v2: comic-metadata v0.6.1 @ 8e66ca4d14ec5a052e9967d6af2590ef957142aa (dirty: N) [source:0d809a5da511d8e48b5c501f46e7af92dad38bc0ab3247fc4eee9d4cf1629dd2; harness:6b193dc7e214f17fc2277715b2c27e9785018b961b2e1e6e24dbf211f3398bb5; runtime:9c4dc46eb53a36a2b99bc517128c2c58c31464bc261890133dd97be30571fc14; checker:4bae2cde4e4cdd2f22fb3060571730ec32fec1dd5403ea070086973b18b695e4] — pre-qa n/a, post-build n/a, check-electron n/a, check pass, test:smoke n/a; personal-folders clean
```

The **independently generated receiver receipt**, read from Futaba's own retained output:

```text
Entry-check receipt v2: comic-metadata v0.6.1 @ 8e66ca4d14ec5a052e9967d6af2590ef957142aa (dirty: N) [source:0d809a5da511d8e48b5c501f46e7af92dad38bc0ab3247fc4eee9d4cf1629dd2; harness:6b193dc7e214f17fc2277715b2c27e9785018b961b2e1e6e24dbf211f3398bb5; runtime:9c4dc46eb53a36a2b99bc517128c2c58c31464bc261890133dd97be30571fc14; checker:4bae2cde4e4cdd2f22fb3060571730ec32fec1dd5403ea070086973b18b695e4] — pre-qa n/a, post-build n/a, check-electron n/a, check pass, test:smoke n/a; personal-folders clean
```

Comparison method: parse each actual outer record's output into lines, require exactly one `Entry-check receipt v2:` line per record, then compare those full strings case-sensitively. They are exactly equal, including all identity digests and check states. No sender line was substituted for receiver execution.

### Explicit skip assessment

- Python skipped only the file-link subcase of `test_folder_help.TemporaryFileTests.test_the_temp_name_as_a_folder_or_a_link_is_not_offered`, because Windows refused file-symlink creation with privilege error 1314. Other shapes in the same test ran. No privileges were enabled or link-safety pass invented; this capability limitation does not conceal a naming-rule failure.
- Shell skipped `actual pinned temp-file exit hook: old catch exits 0, seam exits 1, temp root removed`, because the opt-in authenticated `COMICS_META_TEST_BUILDER_MODULES` closure was not supplied. Its modeled vendor-exit positive/negative controls and the genuine build's existing exit proof ran separately. The optional actual dependency-hook variant is unverified, not counted as passed.
- Shell skipped `actual23 retained snapshot measures 285 and is refused at 254`, because the historical `COMICS_META_TEST_ACTUAL23_JOBROOT` snapshot was not supplied. The current materialized path-bound, positive one-character-over, reparse/missing-tree and split-role tests passed; no old snapshot or environment proof was fabricated.

These are explicit capability/opt-in scope limits, not excluded requested modules or a reason to demand zero skips automatically. They do not replace the required genuine installation/update matrix, which remains pending and blocks release.

Durable receiver evidence: `Docs/ComicsMetaOrganizer_EntryEvidence_v0.6.1_Receiver_2026-11-10.json`, SHA-256 `e5620374bf5e4cd806e57615249b6a6b0e5d571af683f05cba654379a4855f80`; closure `ComicsMetaOrganizer_EntryClosure_v0.6.1_Receiver_2026-11-10.json`, SHA-256 `1324c4b06a7ee1e1dab5ba6b49ef6c7c372518b325fec493c02b2c29161a2996`; KnownFolder proof `ComicsMetaOrganizer_KnownFolders_v0.6.1_Receiver_2026-11-10.json`, SHA-256 `1b352085326dcd103abeb3e21ad7e1d301361faf3c88c5260e68227238072fb5`.

## Genuine Sandbox processing attempt — FAILED before installation

Futaba invoked the processing phase **once**, using the exact Senua-cleared 2,046-file input manifest SHA-256 `6690c5aabdb730478261b5505d9c0e2bdd2018c2a3858e860c03bab3eab5b313`. All seven runtime scripts plus the authenticated Node were independently compared with that manifest before invocation; the host wrapper verifies the complete staged inventory and OS tool pins. Actual source remained `8e66ca4d14ec5a052e9967d6af2590ef957142aa`. Prior installer: 149,536,539 bytes, SHA-256 `f80b1192d6386ef533a5972d187e8e380501ae4ef52bc73aeec34e746603081a`; new installer: 149,538,466 bytes, SHA-256 `718590fb3524cf2ba9b7544c92ca94a2698a47fd26e64185cf3aae18af7f736d`.

The one approved classic Sandbox window booted. `guest-started.json` bound its `WDAGUtilityAccount`, Microsoft virtual-machine identity, guest hostname `C080ED3D-E72F-4`, processing mode, nonce `6a470c182cc84d84a6aa66b86c267e90`, source and original manifest. The host then failed `Cannot uniquely bind new compute session` at `host-session.mjs:34`, before any client/compute ownership proof or `go.json` permit. **No installer, app worker or updater test started.** `guest-owned.json` and `update-result.json` were never created.

The outer private Job exited 1 after **79.467 s**, normal closure, unforced/untimedout, complete output and native zero. This Job result was not treated as VM/client closure. With no host permit, the guest's 45-second go wait failed closed with `Host did not establish unique owned Sandbox identity; no installer started`. Its identity-guarded guest-only shutdown branch ran. The guest wrapper records `pass:false`, that exact failure and `shutdownRequested:true`.

Fresh independent read-only host observations after guest shutdown showed exactly the original saved-template compute system `a90a3ca5-cf2c-4aa3-8da2-e81e62eb3a71` and zero `WindowsSandbox.exe`/`WindowsSandboxClient.exe` processes. Ender's independent current inventory agreed. The template was not stopped, deleted or otherwise changed by QA. This is a factual post-shutdown baseline-restoration observation, **not** successful phase ownership or installation acceptance. No UI closure, privileged kill, retry, unused paused-window launch or host-profile change was performed.

Original runtime-script identities within that exact manifest:

| File | SHA-256 |
|---|---|
| `common.mjs` | `deb8d1ad947371ef684345a811ea955b657f1b64eeeadc2370306d60068ae6bc` |
| `guest-entry.mjs` | `10e0169f2c607115b2fb18d54504609f0fbda3f1d422bc821dec39b314ea0fef` |
| `guest-update.mjs` | `5ce30790da8113a1ee442f8cd7c1eaa922fbd09bbb183273185f04d0fdc171dc` |
| `host-run.mjs` | `279a6075a55445d87566304bf52e14ecad9297e75e52b82517ccf267d6ff1f65` |
| `host-session.mjs` | `cba1980f84635485cbf09b36c8537f057b035f627ee830d6bb560225b0513293` |
| `observer.cjs` | `3360e0b1f19ef9d8e2b2233fabcd5443123b6c3ae9223554638f602c5a2bab2a` |
| `state-fixture.py` | `855ab20b11da8ce2fe307b25497d27a2864fe0897ee842522f97abf5d4e81e6d` |

Original raw host-session SHA-256 `7cbb4909e8d2f561dd8d78e361705123bd9a538f0c1930b6e99129a82fc8209a`; host-owned record `93323f7202494731352a47116b0817bde8deb2b45272e4cb9899c0d79ca2d7a2`. Durable combined original attempt plus later read-only closure evidence: `Docs/ComicsMetaOrganizer_InstallUpdateAttempt_v0.6.1_Processing_2026-11-10.json`, SHA-256 `884701441307c5aa8b55372f17f312d83c1ddb5e0cfb197f56cf811b9efc4924`. The original failed scratch output and stage are retained; no cause or corrected role-ownership proof is invented. Ender owns binding diagnosis/fix. Any further sessions require a reviewed correction and the necessary additional user window permission; this QA did not reuse the unused phase authorization after failure.

## Historical initial full entry and limits — failed source f7cc220

The failure record below remains historical and is superseded for formal test acceptance by the repaired source's matching successful sender/receiver receipts above. No old result, identity or failure has been rewritten as a pass.

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

The current build/artifact, prepared inputs, repaired sender/receiver outputs, failed Sandbox phase and historical failed full-entry evidence are preserved for the active installation/update handoff and publication consumers; they are not published or declared verified disposable. Receiver output remains under its distinct `receiver-*` paths; durable copies are named above. Futaba opened one approved processing Sandbox window; its guest shut down after the pre-install ownership refusal and fresh host inventories restored the original template-only baseline with no Sandbox clients. No paused window was opened. Failed forensics remain intact for Ender; no new cleanup was attempted at this handoff. The private earlier native policy/profile root contains 47 files / 1,903,509 logical bytes (measured by recursive file enumeration and summing lengths). After durable evidence archival, one transparent native PowerShell removal of that exact UUID policy/profile root, with a resolved-path check, was rejected before launch by automatic execution policy with only `blocked by policy` supplied. The root remains; no alternate deletion or retry was attempted. Active build inputs were excluded. Earlier source-QA cleanup rejections remain recorded in the source report and were not retried. Across all three rejected Futaba QA roots, **819 files / 61,609,739 logical bytes** remain; the separately rejected empty Ender folder also remains. No alternative deletion against those roots or parents was attempted.
