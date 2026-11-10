# Comics Meta Organizer 0.6.1 — packaged candidate handoff

Status: **release blocked**. Candidate construction and private packaged smoke passed, but the actual formal entry failed. No installation or publication occurred. The old 0.6.0 failing-gate exception does not apply.

## Source identity

- Source commit: `f7cc220d2eda160fea5c3ba3a8b6898c55938119`; tree `b8a5c4fa1fac82d5f188a267a1a3188344bd6543`; version 0.6.1.
- Sully exported 334 tracked files. Archive `candidate-source.zip` SHA-256: `9ea1c9193228ade19aafc1f342c9a4abfa947a7c523036bc5355674786fd9fc8`.
- Complete source manifest SHA-256: `38e025854cff14551e21c5315c95065545a31fb3fb79eceb81faffe0f4c04c42`. Fresh build candidate and separate immutable source copy matched all 334 file sizes/hashes before building.
- The archive uses CRLF checkout formatting. Main's clean working tree contains mixed checkout line endings, so it cannot be the formal entry's raw-byte source identity. Sully made a separate local, no-hardlinks clone, with its own `core.autocrlf=true`, detached at the exact source commit. All 334 files match the archive/source manifest; Git status is clean. The first LF checkout differed only by 312 proven CRLF/LF transformations; no product or history changed. The formal entry points to this clean matching clone.

All paths below are under `C:/Antigravity Projects/Studio Illuminati/WIP/Comics Meta Organizer/scratch/release-061-20261110/` unless stated otherwise. Active build/runtime/QA inputs must remain until their consumers and publication are finished.

## Restored prerequisites

The prior October preparation scratch and ownership evidence were absent. The existing committed lean preparation route was reused, with no build/checker/hook changes and no implicit npm lifecycle scripts.

- Official Node release: `https://nodejs.org/dist/v26.12.1/`; SHASUMS read-only probe returned HTTP 200. Exact ZIP SHA-256: `b3efd5c70cba3308ed46e7e699a9b8aac075bbc6b027fcb39c84c31acc25e2b4`.
- Authenticated Node ZIP was extracted only into the owned scratch tree, with path/member/size bounds. Bundled npm is 11.20.0. Private Node executable SHA-256: `1c63f1417e2e26d83ca9a9ec1d548524ab1305bc7209d90ebca56257ff0d84ed`.
- Bootstrap records all 1,938 private Node/npm files. Tree manifest SHA-256: `793864aeb06568dbbb2dad2d2d47f334b601c8d35e2aa1482b794c64f6de2d03`. Both the authenticated archive and complete extracted tree were reverified before preparation/build.
- Existing studio ownership addon: `WIP/Books Arranger/build-cache/qa-ownership`, 92 files, exact manifest `122eca8f1ad057bd86867f8e302c60fcaa5b6dba5ff4e660cfd860cf40769617`, matching committed prior evidence with no missing, extra or changed files. No addon was installed.
- Unchanged canonical private-Job owner: `.claude/skills/qa-handoff/scripts/bounded-check.mjs`, SHA-256 `89ecbd30698cae696ba52d677f31bfaa505c87227c22f85e0bb6a2103475fcbc`; child `240a6a96a32f08989439387d5d6ab75d17e1bcf243863d31d2ff7287f68d1e42`.
- Senua reviewed the thin, fixed-command scratch dispatch and all consumed preparation pins. Each invocation retains one original 600,000 ms total budget including preflight, execution and closure, with the existing kill-on-close Job, private environment and bounded output.

Actual bootstrap completed in 4.695 seconds: exit 0, normal closure, complete output, native zero (active 0, unsignaled 0, complete true). Actual unchanged `prepare-runtime.mjs` completed in 68.084 seconds with the same successful closure properties. Receipts: `bootstrap-owned.json`, `bootstrap-result.json`, `prepare-owned.json`.

Prepared input manifest `toolchain/toolchain-manifest.json` SHA-256: `4ffbed69b072e617b942530f47f1587b179829eaa577c27de722648aca1adaeb`. The existing preparation verified all upstream pins, dependency lock integrity and complete native/capsule/dependency trees. Input runtime and dependency pins are unchanged from the source commit.

## Actual installer construction

The reviewed build invocation used authenticated private Node 26.12.1 and unchanged `candidate/scripts/build-installer.cjs --inputs <root>/toolchain`, from the clean fresh candidate. Senua cleared the exact dispatch after verifying source/archive/input manifests and the pure-JavaScript NSIS extraction/reference path. Generated BUILD_UNINSTALLER code was not executed; publication was disabled.

Build completed in **39.371 seconds**, exit 0, normal closure and complete output. Native closure was complete with active 0 and unsignaled 0. Evidence: `build-owned.json`.

- Installer: `candidate/dist/Comic-Metadata-Setup-0.6.1.exe`.
- Size: **149,538,471 bytes**.
- SHA-256: `bf4fe3babcf5eb7a717102d7f220e2ff8b193e7913b527fe26310341224bec6f` (independently read back).
- Actual child `leanBuild` receipt reports `bootstrapExecuted:false`, `referenceEqual:true`, one sign callback, and uninstaller SHA-256 `1008e168e6ff1b093205bd8946579eee4bf5eb6ee1b2d10cae27263c03a024e6`.
- Actual final `BUILD OK` line matches the installer version, size and hash. Exit 0 alone was not treated as build success.

This establishes construction, not acceptance. No copy was installed into the live app or library.

## Formal entry — initial refusals and corrected invocation

Canonical checker: `.claude/skills/qa-handoff/scripts/run_entry_checks.mjs`; immutable schema 2 / 600,000 ms context `entry-context/context-v2.json`, SHA-256 `211869a1a4a0441d3564ff5c1fda4f0cb541cbe0bd2cd9c13cb7815ac89419c2`.

The complete graph binds source, all five checker helpers, checker harness, dependencies, private Node/npm, bundled Python/7-Zip, ownership addon, Git, canonical headless helper scripts, PowerShell and Edge. `check:python` and `check:shell` keep their complete declared graph. A canonical private headless lease supplies CDP for DOM cases, preventing a misleading browserless skip run. Source state isolation loads first and its sentinel remains; the actual live ComicsMeta root, original tool state paths and installed app are explicitly protected despite redirected profiles. No test case is excluded and no old failing-gate acceptance is inherited.

Actual run copies live under the separately owned `C:/Users/AnGeLZzZ/AppData/Local/Temp/illuminati-cmo-061-entry-20261110`, because the checker refuses a run parent inside its source Git repository. Context and durable evidence remain in the owned tool scratch root.

Senua cleared exact dispatch `a1909d915b423894f780415f02bb0d975cfc3e3c1eba22e326faff0ab3cf5948` and controller `712ea7fc9265be1d06b17254474da97b0cd8dc672c62afed74120a28b12f37c1`, conditional on Sully's successful 334-file clean clone proof. That proof was received before the one actual entry invocation. The outer original deadline covers identity validation, browser lifecycle, canonical checks, postflight and native closure. Any failure must be reported; do not repeat the full gate against this build or substitute focused source QA for a receipt.

The one actual owned entry attempt completed unsuccessfully in **48.120 seconds**, exit 1, after complete context/source/runtime validation. The existing canonical headless launcher then reported `no DevTools port within 30000 ms`. Its retained message contains the holder's start record and `RELAYED 68232`, with no later browser-ready record. It closed its lease before throwing; the error did not report unconfirmed closure. The outer owner independently proved normal complete closure, active 0, unsignaled 0 and complete output. Records: `entry-owned.json` and `entry-result.json`.

**No canonical checker CLI, Python/Node check or formal receipt ran.** This is a pre-gate browser startup blocker, not an accepted failing gate or a successful browserless run. No retry, timeout extension, DOM exclusion, alternate launcher or guard change was attempted. Parent and reviewer received the blocker immediately. Any further attempt requires a narrowly reviewed resolution of that startup failure; historical 0.6.0 exceptions remain inapplicable.

Bounded read-only diagnosis found no retained causal stack: the canonical helper had removed the failed lease/profile after closure. Quoting and DevToolsActivePort parsing were consistent; no corresponding Edge debugging-policy value or Application crash event was found. No Edge configuration or helper code was changed. The existing canonical launcher explicitly supports installed Chrome, so Jane authorized one reviewed Chrome-only alternative. Complete Chrome runtime binding covers 270 files; manifest SHA-256 `68238d6d69d74e366c005578ed18afacf50fdcad3fa23407e5a6c3ca56cdae2c`; executable `96d69d49ba2b17da5a836b691f7c16b64e4da0f3d367631b414ba280bed9b2c2`.

That Chrome alternative completed in **33.622 seconds** with exit 2. Chrome started correctly and the actual canonical checker CLI ran, but it refused `Unreviewed ancestor npm configuration` before any check. Existence-only inspection identified `C:/Users/AnGeLZzZ/.npmrc`; its contents were not read or changed. Chrome closure was verified with zero remaining processes and personal-folder comparison clean; the outer owner independently reported complete native zero and complete output. Records: `entry-chrome-owned.json`, `entry-chrome-result.json`. There was no formal receipt or Python/Node test result.

Jane then authorized the concrete supported working-location correction. The fresh owned parent is `C:/Antigravity Projects/Illuminati-QA/CMO-061-20261110`. Read-only checks confirmed all ancestor `.npmrc` files absent, no ancestor npm workspace or executable shadow, and placement outside the user profile/source repository/studio-root scratch. Existing canonical `refuseStudioScratch`, `refusePersonalFolders` and `verifyScriptResolution` checks passed without creating a formal copy or running any test. No guard, npm configuration or project script changed.

Final context `entry-context/context-chrome-location.json` SHA-256 `4c92e35761396ec6f9a20757e7e6764db41b5666a27f0c399a7d7dfb8838856c` differs from the reviewed Chrome context only in `execution.runRootParent`. Senua cleared exact controller `f83bd18ed0099cb314b8269b9649d7ebaef2b081a52b7931d3f433dfdbc4e7b4` and dispatcher `4a95fe6fdbdf62b651ffc266dceb021561a78074031892e02a88b85ad46823b0`. The same source, runtime, full DOM/check graph and original 600-second owner remain. This corrected invocation has reached the actual bundled Python full-suite phase; no earlier attempt ran any test. Its final receipt/result must be appended when observed, without a duplicate invocation.

### Actual full-gate result — failed, not accepted

The corrected invocation completed in **220.279 seconds**. Python reported **1,074 tests in 174.007 seconds: nine failures, six errors, one skip**. The declared shell check did not execute because the Python check failed. No full gate was repeated.

The canonical inner check also reported `Final supervisor output differs from streamed bytes`, forced closure and `outputComplete:false`. This is the historical encoding/output family, not a passed owner result. Its final native observation was complete zero. The outer owner exited 1 with complete output, normal closure, final complete native zero (active 0, unsignaled 0); two intermediate membership observations were incomplete and are retained in its sampling record rather than represented as earlier zero proofs. Chrome lease `27e5fba7b7c5` closed with `verified:true`, `remaining:0`, and personal-folder comparison clean.

Actual receipt:

```text
Entry-check receipt v2: comic-metadata v0.6.1 @ f7cc220d2eda160fea5c3ba3a8b6898c55938119 (dirty: N) [source:985ba6cf7e14de464de4abd509bff49d029d6a9786cc9b0d6ffb1d14ba15c85a; harness:6b193dc7e214f17fc2277715b2c27e9785018b961b2e1e6e24dbf211f3398bb5; runtime:9c4dc46eb53a36a2b99bc517128c2c58c31464bc261890133dd97be30571fc14; checker:4bae2cde4e4cdd2f22fb3060571730ec32fec1dd5403ea070086973b18b695e4] — pre-qa n/a, post-build n/a, check-electron n/a, check fail (owned check), test:smoke n/a; personal-folders clean
```

Evidence: `entry-chrome-location-owned.json`, SHA-256 `45c6570b540d41e6b76d1628c0c454a182392cffa742356be4dabf8da12a7c43`; `entry-chrome-location-result.json`, SHA-256 `73972f89da00bd165eda3e681676c0a73eb543338ce85330f9eb7454708d3768`. No accepted-exception, QA GO or publication claim follows from this receipt.

### Failure classification from saved output only

No new execution was used for this classification. Git comparison from tested 0.6.0 product source `e21e0fc` to this source shows the affected static JS, existing failing-test modules, `qa_runtime.py` and `library_lock.py` unchanged. This establishes no change in those files; it does not prove every new observation existed in the old runtime. No failure names a new naming-rule test, and no new four-fix production regression is established.

| Result and exact case | Classification / saved evidence |
|---|---|
| ERROR `test_failure_filters_dom.FailureFilterDOMTests.test_details_dialog_carries_the_reason_and_last_error` | Exact historical case. Existing open review dialog intercepts the click; 30-second locator timeout. |
| FAIL `test_failure_filters_dom.FailureFilterDOMTests.test_row_sentences_and_held_visibility` | Exact historical copy/fixture discrepancy. |
| FAIL `test_failure_filters_dom.FailureFilterDOMTests.test_summary_lines` | Exact historical old `.env` instruction versus desktop-key-editor copy discrepancy. |
| FAIL `test_kept_backups_dom.KeptBackupsDOMTests.test_keyboard_confirm_and_row_delete_send_ids_only` | Exact historical clock-sensitive case: expected 12 versus observed 13 minutes. |
| FAIL `test_kept_backups_dom.KeptBackupsDOMTests.test_panel_text_states_and_layout_at_every_width` | Exact historical clock-sensitive case: just now versus one minute ago. |
| ERROR `test_state_root.StateRootSelectionTests.test_every_process_derives_all_state_paths_from_the_root` | Exact historical embedded-Python child/import-path case; child exits nonzero. |
| ERROR `test_folder_help_dom.FolderHelpDOMTests.test_layout_rects_at_every_width_and_zoom` | New harness error: required `COMICS_TEST_EVIDENCE` output destination omitted from the developer's entry environment. Not a product diagnosis. |
| ERROR `test_verification_dom.VerificationDOMTests.test_rectangles_and_copy_at_320_and_desktop` | Same omitted evidence-output environment variable. |
| ERROR `test_yandex_dom.DashboardDOMTests.test_rects_states_zoom_and_open_dialog` | Same omitted evidence-output environment variable. |
| ERROR `test_update_stats_dom.UpdateStatsDOMTests.test_label_thinning_by_measured_width` | New/unclassified: timed out waiting for expected chart label count 11. Not assigned to the naming fixes or called a historical baseline. |
| FAIL `test_library_lock.ClaimTests.test_leftover_process_of_another_copy_blocks_until_it_ends` | New/unclassified child handshake: blank stdout instead of `held`; no causal stderr in this assertion. Embedded-path family is only a suspicion. |
| FAIL `test_qa_runtime.QARuntimeTests.test_supervisor_spawns_the_worker_in_qa_mode_and_other_children_stay_refused` | New observed child import failure: `ModuleNotFoundError: No module named 'qa_runtime'`. Same runtime family as historical child imports, but not rolled into the old acceptance. |
| FAIL `test_update_stats_dom.UpdateStatsDaylightDOMTests.test_autumn_repeated_hour` | New observed formatting discrepancy under current Chrome: single-digit versus zero-padded hour labels. UI and fixture source unchanged. |
| FAIL `test_update_stats_dom.UpdateStatsDaylightDOMTests.test_last_hour_across_the_clock_change` | Same observed H versus HH formatting discrepancy. |
| FAIL `test_update_stats_dom.UpdateStatsDaylightDOMTests.test_spring_missing_hour` | Same observed H versus HH formatting discrepancy. |

The three missing-evidence errors are a concrete omission in this task's controller environment. They must not be attributed to the app. No controller repair, automatic full rerun, exclusion or product change was made after the failed full gate. Other unclassified/new observations and the failed canonical output proof remain blockers pending explicitly scoped disposition.

## Private packaged QA and cleanup

Futaba's separately reviewed private native adapter passed the actual unpacked 0.6.1 app smoke: private/offscreen startup, real production engine and version, the actual enabled tray Quit callback, natural exit 0, complete native closure and all 621 packaged files unchanged. This is recorded in `Docs/ComicsMetaOrganizer_QA_v0.6.1_2026-11-10.md`; its overall NO-GO while formal entry is missing is not replaced by this native success. Source-only 103-test QA is also separate from formal entry.

The developer's old empty `scratch/naming-fixes-20261110` path and Futaba's earlier removal-rejected paths remain protected against alternate deletion attempts. New release scratch, prepared inputs, matching entry clone, actual run root, package and receipts are active evidence/inputs. Remove only owned disposable outputs after their consumers finish and compact evidence is retained. No live app, library/NAS data, installed state or unrelated session output is a cleanup target.

## Publication preconditions and closeout

The supported `npm run release` calls `publish-held.py`, which requires a production build receipt with source/native/artifact bindings and a QA receipt proving actual packaged installation, state preservation, no old owned engine before replacement, and genuine prior-to-next installation/relaunch. The lean construction receipt and this private unpacked first-run smoke do not prove those missing behaviors. The Brief retains the actual installation/update acceptance requirement. The October 28 closeout records 0.6.0 publication under its then-accepted lean QA, but contains no standing waiver or retained lean-to-legacy promotion reconciliation authorizing invented proof for 0.6.1.

The production private policy can select a private install directory and the installer helper passes `/D=...`; this alone is not Windows-user isolation. The earlier 0.2.1 installed QA explicitly observed the product's registry entry and Start Menu registration. No normal-profile installation, registry mutation or current user-state replacement is authorized here. Genuine update QA needs a suitably isolated Windows account/VM or separately explicit authorization for a normal-profile cycle. Any future lean receipt adaptation must bind the real source/artifact/ownership records; it cannot fabricate installation/update booleans or relax the publisher. No release code, Git tag, publication, installation or new test attempt was made after the failed gate.

Durable evidence copies (exact original bytes):

- `Docs/ComicsMetaOrganizer_EntryEvidence_v0.6.1_2026-11-10.json`: full 215,606-byte outer record including actual check evidence/receipt; SHA-256 `45c6570b540d41e6b76d1628c0c454a182392cffa742356be4dabf8da12a7c43`.
- `Docs/ComicsMetaOrganizer_EntryClosure_v0.6.1_2026-11-10.json`: 688 bytes; SHA-256 `73972f89da00bd165eda3e681676c0a73eb543338ce85330f9eb7454708d3768`.
- `Docs/ComicsMetaOrganizer_BuildEvidence_v0.6.1_2026-11-10.json`: 5,571 bytes; SHA-256 `2ca33a64778af5569e2b3e67b3407111b9d6f5b6fb98a847031068451314c99d`.
- Futaba's native summary `Docs/ComicsMetaOrganizer_NativeQA_v0.6.1.json`: SHA-256 `44ef33ecc674b2628cad641f1c82d28f8bd68f642fd9aaeb25af0a9fdd024fca`; complete 621-file package proof `Docs/ComicsMetaOrganizer_NativeQA_Package_v0.6.1.json`: `c00dc5af107f9998364fb3d763e78f1ccff7be5f14b2f114a4cb2f814c8283a4`.
- Futaba's final overall QA report remains **NO-GO**; source 103-pass and native 621-file proof remain separately valid. No real credential was supplied to the isolated check environment; captured output contains fixture data and execution metadata, not live credential reads.

Cleanup inventory used `os.scandir` plus `lstat` file sizes, explicitly not following reparse points. Finished canonical copies under `C:/Antigravity Projects/Illuminati-QA/CMO-061-20261110` contained 431 files / 17 folders / 4,787,286 logical bytes and one dependency junction. The earlier precheck copy under `C:/Users/AnGeLZzZ/AppData/Local/Temp/illuminati-cmo-061-entry-20261110` contained 334 files / 13 folders / 4,400,620 bytes and one dependency junction. Source identity and failed execution/closure evidence had already been retained before cleanup.

One transparent exact-target PowerShell cleanup succeeded, exit 0: unlink both owned dependency junctions without recursion, then remove only the two named run roots. **765 files, 30 folders, two junctions and 9,187,906 logical bytes** were removed. No shared dependency target was a deletion target. Current installer/unpacked package, source/archive/clean clone, prepared toolchain/private Node and remaining run-specific source/receipt files stay contained under `scratch/release-061-20261110` as needed current deliverable, reproducible inputs and unresolved forensic evidence. All earlier rejected targets and their parents remain untouched. No further code, tests, browser launch or release attempt is in this closeout.

A later nonrecursive attempt to remove the now-empty `C:/Antigravity Projects/Illuminati-QA` container was rejected before command launch by automatic execution policy (`blocked by policy`, no further reason). That empty container remains; no alternate removal was attempted. The successful two run-root removals above are separate, completed operations. The rejected container and its parents are now also excluded from further cleanup attempts.
