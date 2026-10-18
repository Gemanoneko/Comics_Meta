# Code Review — Comics Meta Organizer v0.3.0

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-18
Tool: Comics Meta Organizer
Release: v0.3.0
Commit range: 7b3d93a09e96aa498b82240f1eb33fa5ba64e27e..72cb04fce03c6958db217ba713727248adefe430
              plus the frozen working-tree candidate identified below.
Changes: 7 implementation/test files (+270/-6), plus version/lockfile/changelog changes.
Stand-down dimensions: none
```

The intervening committed change is the v0.2.6 QA/review documentation. This review extends the previous review's endpoint and certifies the following candidate bytes; a later release commit must contain these bytes or receive a follow-up review.

| File | SHA-256 |
|---|---|
| automatic.py | 34959660faf94099f67a7911c461a708ddd0acff0f1010374e2cfa4a0396f832 |
| source_scheduling.py | e64df30a728adce1f0c4d9ce6bcf1e5d8ddea54feec17a5d3364b942d1a407a9 |
| research_runtime.py | ca7c1118aaffe1ebbd67a79d6793e3e4fc64b995043b513b75682cd0b896aca3 |
| metron.py | d4d7cfa56daa5c399c3f5f0be5835af4dbc08427a0303d4c1de09e3175f082fa |
| tests/test_comic_lookahead.py | cc95deeb2ca810e69153f5dca3f315787e9c5cd4f806c28e503cf023bfd78564 |
| tests/test_yield_order.py | da368d1b96e41609e51a484318a770ad6c0a7215717fa82c786091bb5cebe391 |
| tests/test_source_switches.py | 18ab16d1516c375215f70e41f84665bd58417fb5b36d6d89616fa2af28cb2013 |

## Summary

Unchanged unresolved comics stop repeating an expired comic-level retry when every enabled recorded source is still waiting. A folder pass can prefetch two eligible Metron lookups; the discovery owner consumes results, records evidence and constructs plans, and the pool drains before discovery returns to the serial writer. I reviewed the entire implementation/test diff and its scheduling, coverage-priority, Metron pacing, pause, plan and worker call paths. No speed benchmark was run or requested.

An initial Major finding was corrected during review: cancellation of speculative work was invisible inside Metron's multi-request lookup. The final patch installs a thread-local cancellation event and checks it at API and cover boundaries, clearing it in `finally`. An already active network request still finishes under its existing timeout; this is cooperative cancellation, not immediate interruption.

## Rubric

### 1. Security

- Pass. No new shell, Electron, credential-output or filesystem-delete surface. Metron requests retain their existing endpoint/redirect validation and credential handling.

### 2. Correctness & Logic

- Pass. Suppression applies only to unchanged `needs_identity_lookup` records with all enabled sources represented and not ready. New cover leads, archive/matcher changes, holds, legacy records and recovered providers retain their eligibility paths. Lookahead excludes Web-linked, held, reusable-evidence, in-book-ready and non-Metron-first candidates; ordinary source ordering and acceptance still decide results.

### 3. Crash / Stability Safety

- Pass. Provider exceptions return through the existing source-result handler. Pause and cancellation stop submissions and consumption; scope exit cancels queued work and joins running work before discovery returns.

### 4. Performance

- Pass by construction review only. Pending speculative jobs are capped at two, selection stays within the bounded research pass, and Metron's shared request lock, spacing and retry limits remain in force. No throughput improvement is claimed. Only eligible Metron lookups gain cross-comic concurrency.

### 5. State & Data Safety

- Pass. Speculative workers return lookup results without publishing plans or archive writes. Archive size/mtime is checked before research, after research and before result consumption. Existing digest/signature, verification and backup guards remain unchanged. Worker discovery and archive application remain serial.

### 6. Input Handling

- Pass. Candidate selection retains CBZ/root/language/identity restrictions. Missing or changed archives cannot supply prefetched metadata; existing provider-result verification remains authoritative.

### 7. Maintainability

- Pass. Concurrency ownership is contained in `ComicLookahead`; cancellation is thread-local and removed after each lookup. No browser or local-model concurrency is added.

### 8. Doc/Code Drift

- Pass. Changelog describes bounded lookahead and preserved safety/provider controls without claiming a measured speedup. Existing v0.2.6 advisory documentation findings are unchanged.

### 9. Build & Release Hygiene

- Pass for reviewed source. VERSION, package.json and both package-lock version entries agree on 0.3.0. Build/packaging scripts and dependencies are unchanged. This report does not certify a packaged installer or substitute for Futaba's behavioral verdict.

## Test-route audit and evidence

The independently reviewed task-local route is under `C:/Users/AnGeLZzZ/AppData/Local/Temp/codex-comics-perf-20261018/shared/`. It reuses `scripts/packaging/owned-job.py` unchanged. Approved pins:

| Input | SHA-256 |
|---|---|
| controller-pins.json | 11595deba39432aac6ece675ba32e4a6d5eeeade51fecf159070709dd94c9b10 |
| suite_controller.py | 62fd6e5aeab30ddd226517bb084844f8b938bcec659073c85c53948679dfbaf3 |
| suite_runner.py | a5a2aa139311e54dbe3d412acffa92cb7032198bfe31cfd9d7966274de284a23 |
| source-manifest.json | b97c32b98700ae88c699b09077f0e558d9f14a3f8a54285419f8489fb37690ae |
| unchanged owned-job.py | 8ba5c37a2c6f3fc87478ac1d34c6c7235738a8a27a420dbb2ce34a20549dec15 |

The hidden controller uses an original 600000ms monotonic deadline, atomic Windows Job assignment, kill-on-close, bounded pipe drains and a zero-descendant postcondition. It holds the launching parent handle and requires explicit foreground nonce/counter lease renewals, expiring after 60 seconds without advancement. The runner checks the frozen source manifest before and after tests, removes the installed engine from import paths, loads state isolation before application imports, redirects state/locks/temp, protects live roots, and refuses native launches. Existing socket isolation permits only suite-owned local fixtures. No shared tooling or guard was disabled.

Full discovery completed on the final diagnostic graph: **918 tests, 0 assertion failures, 11 error records, 75 existing skips**. Ten distinct tests errored (833 passed); ten errors are explicit native-launch refusals, and one additional cleanup error belongs to an already failing setup test. This is **not a passing full suite**. Native receipt: `reason=completed`, `root_exit=1`, `active_after=0`, `lease_failure=null`; `isolation_violations=[]`. I independently read `result-full-03.json` and the error summaries in `logs-full-03/stderr.log`. Manifest verification ran before and after discovery. No new skips were introduced.

The unavailable coverage is native 7-Zip conversion (five tests), cross-process library ownership (one), QA worker spawn (one), setup/claim transfer (two), and cross-process state-root selection (one). The extra setup cleanup error is WinError 32 on an owned scratch lock. These are limitations of the intentionally no-native-launch graph, not demonstrated passing integration checks. All changed-area tests, including both corrected provider-order modules, completed without assertion failures or errors. Independent focused QA remains a separate required verdict.

The first full attempt ended fail-closed with `reason=owner-exited`, `root_exit=125`, `active_after=0`; no suite verdict was produced. Ender had renewed the lease with PowerShell Move-Item instead of the approved atomic replacement. A transient lease-read gap is a plausible cause, not an established diagnosis. Evidence is preserved as `result-full.json` and `logs-full/`.

The reviewed retry changes only full-run output names to `logs-full-02` and `result-full-02.json`. Updated controller SHA-256: `4d2d29566551c9ffb8e273e8c5a34666132dfad825142622ae6542f8156382ba`; pins SHA-256: `af706c3631c1bb3b54cd814509cb6deea636165954eb2ac74db27b597b97f498`. Runner, owner and snapshot manifest are unchanged. Explicit foreground lease renewals now write a sibling JSON and atomically replace `lease.json` using Python `os.replace`. Focused-mode filenames are unchanged and reserved for independent QA.

That second attempt also failed closed (`owner-exited`, root 125, active descendants 0), despite atomic renewals. Its exact lease failure was not recorded; neither a sharing violation nor parent death is established by those artifacts. QA confirms it did not write the lease. A third diagnostic attempt preserves every refusal but adds explicit parent/nonce/counter/expiry/read-error evidence. Approved diagnostic pins: `98cafdf0b49143e36f41f3a408b285deaf826c47239117225bdcf95226112323`; controller `703164c62dd89c78cc0d1178b8aa962b62b60edb186baa05857338aaac26e59a`; runner `4cc37bf84a17d8cff2f5c90d0b81399f33cd0dd5ce0182f7fd6058634f1f9abd`; source manifest `b97233062ec72a221250c4ccc0280f6a775310555d56de2d991a24de34f54e57`.

The diagnostic run completed without any lease failure. The first two interruptions therefore remain unexplained; their cause is not retroactively assigned to atomic file replacement or parent death. All three native receipts prove zero remaining owned descendants.

Two existing provider-order fixtures had mocked scanning while storing a fictional mtime of 1 for a real temporary comic. They now store actual size/mtime, so the new archive-change guard can reach the provider mocks; assertions are unchanged, not skipped. I independently reviewed both fixture changes. The focused graph includes both modules. An actual changed archive still cannot supply a prefetched result; the existing source error handling continues other sources and a later scan obtains its fresh identity. A non-prefetched unchanged comic retains direct lookup.

The initial packaging inspection was rejected by `studio-command-safety` P9 because a read-only command's filename matched the long-command list while the supported execution API has no timeout field. On the authorized follow-up, the deployed guard's existing literal `rg` reader path successfully read that same configuration without hiding its filename or disabling the guard. The configuration, fixed lean builder, pinned Node and ordinary output directories were then checked.

## Authorized packaging follow-up

Source candidate commit: `e61c9ba` (the reviewed implementation/test bytes and source QA are retained). Independent focused QA passed **94/94, no skips**, with root exit 0 and zero owned descendants; see the version-matched QA report. Native installer/update certification remains distinct.

The Brief's approved lean build entry remains `node scripts/build-installer.cjs`; historical held build graphs are not reinstated. A task-local outer command controller provides only execution ownership required by the current API: fixed entry and pinned inputs, hidden launch, original 600000ms deadline, held parent, foreground nonce/counter lease, and zero-descendant closure. It does not publish or execute the installer. Initial controller SHA-256 `657929dad241e20adf1c161aa56ef01d5f3606b32b70b1dd056052d3075ea154` was approved after inspection.

Build attempt 01 closed safely with root exit 125, descendants 0, and an explicit lease-read `PermissionError(13, 'Permission denied')`. This establishes that attempt's cause; earlier test interruptions remain unproven. The reviewed build-02 controller (`0df64f833e8761626f8bc392c3fe92d9421bb76e48ec00bef1d9bd5e0b7b59ac`) tolerates only a transient PermissionError after an initially valid lease, credits no renewal, and still requires the held parent alive and the last accepted lease younger than 60 seconds. Initial read, missing file, malformed JSON, nonce/counter failures and the 600-second deadline remain fail-closed. Fresh outputs preserve attempt 01.

The user separately authorized the narrow cross-studio P9 correction. Its candidate changes only literal PowerShell file-read classification; a smart-quote delimiter escape identified during review was corrected before deployment by excluding U+2018–U+201F. Actual guard assertions passed **37/37** and actual lease-function assertions passed **10/10**, both with native root exit 0 and zero remaining descendants; I read both receipts independently. No general command exemption or timeout weakening is approved.

Canonical guard deployment encountered a further pinned-checker hash mismatch. Ender restored the exact original guard (`2e5a9ba57033d7fce6333a3ddb5035fc6a6af894bab3f9c39d0ac6a0cc6c1720`), and normal tool execution was verified restored. The safe candidate is **not deployed**; deployment was deferred, with no hash-validation bypass. The supported literal `rg` read route remains available.

Build 02 completed successfully: `reason=completed`, `root_exit=0`, `active_after=0`, `lease_failure=null`, `lease_read_denials=0`. Its actual lean receipt and final `BUILD OK` agree on installer size **149,488,082 bytes** and SHA-256 **3bb315e591aa2c51e7c4d9cf2a115e16a2ff325149d804df9db4acfc2da54bc6**. The receipt reports `bootstrapExecuted=false` and `referenceEqual=true`, preserving the pure uninstaller extraction rule. I independently read `result-build-02.json`; this certifies a successful build, not execution of the installer or native update QA.

The user subsequently authorized checking the closed installed app. The reviewed actual upgrade runner (`17309fb1e31cc8ffc7a28c492cff08f73700992d6501d460db45cee6a177750d`) and controller (`25b761ae5c6b258e73b57c4c17f60752e3bd414776ea74803467ce5d26684bb4`) permit only the pinned installer with `/S`, under the same 600-second owned Job. Before replacement they require closed installed processes, successful process enumeration, a complete hash-verified backup and unchanged rescan, and at least 120 seconds remaining. The expected generated `Local/comic-metadata-updater/installer.exe` cache replacement must equal the pinned new installer; every other state file remains under strict equality. No automatic app launch is requested.

The installed-binary private QA adaptation was also reviewed: harness `d75b68bd461f3db3fe7851fda7253c351838477840db70b64cc328d36b2dd5de`, controller `80cce140a44bebcfb86880b0dbc31be7a56f1ddd8ed17820e2f4c6fbd8c9cfa3`. It checks all 609 package hashes at the actual installed location and exercises launch, product Quit and restart with a fresh private state root and empty library. Execution approval is conditional on successful installation; this paragraph records route review, not an execution result. Publisher inspection confirms actual old-to-new silent NSIS replacement can satisfy its update fields; evidence must explicitly state silent NSIS transport and `updaterUIExercised=false`, without claiming an in-app updater test.

The large live-state backup required a reviewed split into sequential bounded stages rather than extending the original deadline. Approved task-local controllers: backup resume `f51e6b95dc8b69e7b8bf6d84a04a2b46fa57e96cd74dba6d2e879eaab281e2f8`, installation `329dfa60c24d1177e72af80de251cba244435ac6ff53ab87b068af5add5a3172`, and post-install audit `370bfdc2416ca6ddfe93cafe507b000297f3e91530f38d5f820e71e1566b2c7e`. Each retains an independent original 600-second owned deadline. Resume requires original closure and rehashes every reused partial-backup file; a truncated copy is preserved separately, never silently discarded. Installation requires the completed verified manifest and a full live-state equality scan before replacement. Post-install verification must pass before state-preservation or release QA is marked successful. Stage advancement requires actual completed/root-zero/zero-descendant receipts; approval alone is not execution evidence.

Actual follow-up evidence is now complete. The original combined attempt stopped during backup validation, before installation, with root exit 1 and zero descendants. Resume verified all **85,808** existing backup files without copying them again; verified preimage SHA-256 is `c2087ab93ef496798d9b13b7df9f77b0d42607275198966abcbcd31efc48e1c9`. The actual silent NSIS upgrade changed installed version **0.2.6 to 0.3.0**, exited zero and did not auto-launch. The separate post-install audit confirmed preservation of all captured user-state files, with only the explicitly expected generated installer cache replacement. The installed binary then completed two private launch/product-Quit cycles; its second dashboard visibly reported v0.3.0 and retained pause state. I independently read these proofs and all four native stage receipts: each completed with root exit 0 and active descendants 0. This is actual installation plus private installed-runtime validation, not in-app updater UI coverage or processing against the live comic library.

Release evidence binds the tag to the actual built commit `e61c9baf958a2f117a081e1ba10e8a8a86547e9c`; final evidence documents may be committed separately on main. All three artifact SHA-256 hashes were independently rechecked against the build receipt. Publication uses the unchanged exact-artifact publisher and requires the final pinned QA/promotion contract; no rebuild or fabricated runtime evidence is needed.

## Verdict

- Total open Critical: 0
- Total open Major introduced: 0 (one corrected during review)
- Total open Minor introduced: 0
- Earlier v0.2.6 advisory findings remain outside this change and are carried forward.

**Verdict:** RELEASE CLEAR

Safety floor intact for the reviewed candidate. Release still requires the independent QA result and ordinary release checks.
