# Comics Meta Organizer v0.3.0 — QA

Futaba, 2026-10-18. Correctness regression only; no speed benchmark or throughput comparison.

**Source correctness:** GO for the frozen candidate and tested scope below.

**Verdict:** GO

Final clearance follows the successful actual 0.2.6-to-0.3.0 installer upgrade, state preservation audit and installed-runtime checks recorded below. Earlier pending/NO-GO statements are historical checkpoints superseded by the final continuation. No speed improvement is claimed.

## Candidate identity

Baseline HEAD: `72cb04fce03c6958db217ba713727248adefe430`; candidate working-tree changes were uncommitted when frozen (dirty). Tested the immutable snapshot, never the live working tree:

`C:/Users/AnGeLZzZ/AppData/Local/Temp/codex-comics-perf-20261018/shared/source`

Complete source-manifest SHA-256: `b97233062ec72a221250c4ccc0280f6a775310555d56de2d991a24de34f54e57`. The runner verifies every snapshot file before and after execution. Later documentation edits are outside this tested identity. A future commit must preserve these implementation/test bytes or receive another regression assessment.

| Input | SHA-256 |
|---|---|
| automatic.py | 34959660faf94099f67a7911c461a708ddd0acff0f1010374e2cfa4a0396f832 |
| source_scheduling.py | e64df30a728adce1f0c4d9ce6bcf1e5d8ddea54feec17a5d3364b942d1a407a9 |
| research_runtime.py | ca7c1118aaffe1ebbd67a79d6793e3e4fc64b995043b513b75682cd0b896aca3 |
| metron.py | d4d7cfa56daa5c399c3f5f0be5835af4dbc08427a0303d4c1de09e3175f082fa |
| tests/test_comic_lookahead.py | cc95deeb2ca810e69153f5dca3f315787e9c5cd4f806c28e503cf023bfd78564 |
| tests/test_yield_order.py | da368d1b96e41609e51a484318a770ad6c0a7215717fa82c786091bb5cebe391 |
| tests/test_source_switches.py | 18ab16d1516c375215f70e41f84665bd58417fb5b36d6d89616fa2af28cb2013 |

## Independent execution

After Ender's full run closed, Futaba ran the Senua-reviewed `suite_controller.py focused` once, using hidden `C:/Python314/python.exe -I -B`, a fresh nonce/counter lease initialized and renewed with atomic Python `os.replace`, and original 600000ms deadline. The unchanged Windows Job owner enforces descendant closure. State, locks, temporary files and synthetic comics stayed under session scratch; live state/library/keys, real provider requests, browsers and GPU were excluded. No live app was stopped, launched or installed.

Actual runner result:

```text
CORRECTNESS_RESULT {"mode": "focused", "tests": 94, "failures": 0, "errors": 0, "skipped": 0, "launch_refusals": [], "isolation_violations": []}
```

Controller: `reason=completed`, `root_exit=0`, `active_after=0`, `lease_failure=null`. Counts are the unittest runner's reported totals, not inferred from log lines. No runtime timing is interpreted as a speed measurement.

Verified behaviors include all-source wait suppression; changed comic/new evidence/matcher/provider-recovery wakeups; legacy/hold/untried-source eligibility; two-comic maximum lookahead; exceptions delivered without duplicate retries; pause preventing submission and result consumption; cooperative cancellation before the next provider step; scope exit draining work; stale archive rejection; ordinary lookup fallback; provider quota/cache conservation; source ordering/switches; conflict and dead-link guards; and serial plan/application regressions against synthetic archives. Provider pacing and single-writer safety also remain covered by Senua's source review. Actual network-provider integration was not exercised.

Two prior full-run assertions came from test catalogs using fabricated `mtime=1` for real temporary files. Ender corrected those fixtures to actual file stats; both modules passed independently here. Production stale-result rejection was preserved.

## Broader evidence and limitations

Ender reports full discovery completed 918 tests, 0 assertion failures, 11 errors and 75 skips: 10 native-launch refusals and one consequential cleanup error. It therefore did not pass as a whole. Controller root exit was 1, descendants 0, with no isolation violations. Two earlier developer runs stopped fail-closed on ownership lease expiry; their evidence remains preserved. These are developer results, not a second independent full-suite claim.

Canonical protocol-2 qa-handoff receipt: **unavailable**. The legacy/shared pipeline remains held; this task-local correctness run is not a formal receipt and none is fabricated or copied from Ender. Packaged installer validation is also pending; the parent reports the available packaging inspection route blocked by the deployed guard. Source GO does not clear those release gates.

## Reproduction and retained evidence

Reviewed fixed command: hidden `C:/Python314/python.exe -I -B <shared>/suite_controller.py focused`, with the reviewed foreground lease procedure above. The output paths are single-use: do not rerun over `logs-focused` or `result-focused.json`; a fresh reviewed output slot is required.

| Evidence under session `shared/` | SHA-256 |
|---|---|
| controller-pins.json | 98cafdf0b49143e36f41f3a408b285deaf826c47239117225bdcf95226112323 |
| suite_controller.py | 703164c62dd89c78cc0d1178b8aa962b62b60edb186baa05857338aaac26e59a |
| suite_runner.py | 4cc37bf84a17d8cff2f5c90d0b81399f33cd0dd5ce0182f7fd6058634f1f9abd |
| result-focused.json | 3da7449413228844eb11785ca3eabcc1411cfd243fe49fe793e507ad67a6aaed |

Pinned Python executable SHA-256: `434b361fe0c5960d404974feed493db47f2603a1ace2574312104fbed0182c6f`; unchanged `scripts/packaging/owned-job.py`: `8ba5c37a2c6f3fc87478ac1d34c6c7235738a8a27a420dbb2ce34a20549dec15`.

Pattern alert: repeated developer lease termination during this session. Disposition: defer shared-runner investigation; preserve evidence, retain fail-closed behavior. Full03 and independent focused subsequently completed with no lease failure; no claim of a proven repair to the earlier cause.

Session scratch is retained for Sergei under `C:/Users/AnGeLZzZ/AppData/Local/Temp/codex-comics-perf-20261018`, per the per-session cleanup exception. No QA artifacts were created elsewhere outside this report.

## Packaged runtime continuation — 2026-10-18

Candidate is now committed as `e61c9baf958a2f117a081e1ba10e8a8a86547e9c`. The earlier source-test scratch was deleted by the user; the durable source results above remain historical evidence. New build/package evidence occupies the rebuilt session scratch.

Build02 produced `dist/Comic-Metadata-Setup-0.3.0.exe`, 149,488,082 bytes, independently verified SHA-256 `3bb315e591aa2c51e7c4d9cf2a115e16a2ff325149d804df9db4acfc2da54bc6`. `latest.yml` names 0.3.0 and matching size. No rebuild is authorized by this report.

Independent packaged runtime check: **PASS**. Actual `dist/win-unpacked/ComicMetadata.exe` launched twice under its existing private QA policy, with isolated profile/state/library/ports, offscreen windows, blocked external provider traffic and a local model stand-in. Dashboard displayed v0.3.0 and the desktop bridge was present. Durable pause, config bytes and a preservation marker survived ordinary restart. Both product Quit calls exited successfully; engine/CDP ports closed; the external 600000ms Job owner reported `completed`, `root_exit=0`, `active_after=0`, and no lease failure. This proves the dashboard Quit path (same implementation as tray Quit), not every top-level screen. No physical input, real browser, GPU inference or real comic was used. Existing QA mode still creates a tray icon, which was not interacted with.

The first harness attempt had a JavaScript syntax error before any app launched; Ender corrected its missing brace and syntax-checked it. Senua approved the corrected runner and fresh output slot before QA ran it. No product files were changed for this correction.

Retained SHA-256 identities under rebuilt session `shared/`:

| File | SHA-256 |
|---|---|
| package-qa.cjs | 8a7a1562499932906225553549a0448f9278b3e4cca6d33b6e69ef32310ae771 |
| package-controller.py | 68ef8088c3eac2ec87a94563f8d40143593127c5527da5f6cd7c0b7faeae94ce |
| package-qa-pins.json | 1f64acdeb6fb82382604b608483ce5e8a7707d0ced93dbfe45e9b80e5450ee52 |
| result-package-02.json | 4a8fdb1000386c4a8d8f7273ecc3a0b865effdce1820a78ca93f53c5e716334d |
| package-qa-result.json | 5d843ef6d86444a8f9c3b36073cf892dc50806e8633e54b9611eddd1ed83d7a4 |

The installer was not executed in this packaged-runtime pass; ordinary restart is not an old-to-new update. Sergei subsequently authorized checking his closed installed app. Read-only preflight found installed version 0.2.6, no installed app/engine family or port 8765 listener, and durable pause set. Actual installer-based upgrade requires a separately reviewed bounded route and verified state preservation before release clearance. No in-app updater UI coverage is claimed.

## Final actual upgrade and installed-runtime acceptance — 2026-10-18

**PASS.** With Sergei's explicit authorization after he closed the app, the exact installer above upgraded the existing per-user installation from **0.2.6 to 0.3.0**, using silent NSIS `/S` without `--force-run`. This is actual installer-based update evidence; **the in-app updater UI was not exercised**. Senua checked the exact publication contract and confirmed it requires the real version transition/relaunch, not that particular transport.

Before replacement, the reviewed route proved the installed process family and production engine port were closed. It preserved and verified **85,808 files** across the real engine state, shell profile and updater roots under `shared/live-state-backup030`. The manifest SHA-256 is `c2087ab93ef496798d9b13b7df9f77b0d42607275198966abcbcd31efc48e1c9`. Counts come from the complete hashed manifest. The initial combined run stopped before installation at its internal deadline while validating the completed backup; root exited 1 and owned descendants were zero. The approved split continuation verified and reused every copied file (0 recopied), then independently checked the live preimage before installation. No backup was silently assumed complete.

Silent installation exited 0, installed `resources/engine/VERSION` became 0.3.0, and no app automatically launched. The separate post-audit passed: all backed-up user state remained byte-identical with unchanged recorded metadata, except the expected generated updater `installer.exe`, which exactly matched the pinned new artifact. Configuration, credentials, catalog, recovery data and saved pause were preserved. No real comic was opened or written by QA.

The actual newly installed `ComicMetadata.exe` then passed two independent private QA-mode launch/Quit cycles. All **609 pinned packaged files** matched before launch; the real installed server displayed v0.3.0; private configuration, marker and user pause survived restart; both product Quit calls exited 0 and engine/CDP ports closed. Its external Job ended with `completed`, `root_exit=0`, `active_after=0`. The same results held for backup-resume, installation and post-audit stage owners, each using its own original 600000ms deadline and foreground lease. The real profile remains closed and paused; the installed binary was tested against a private empty library to avoid comic mutations. No foreground input or in-app updater UI coverage is claimed.

Sully's parity check additionally matched 61 staged engine source mappings against the committed candidate and installed package inputs, and all 609 package pins. Staged manifest SHA-256: `87814c13832cb7d87e7a293f88fb3016b5585e6d00da8488744c97acc3fb1f8d`. Source identity `a9369126d9d96627b60a9571e56cedcea1881e9294ce2a23f554fd858f8b1f10` binds the exact committed Git tree; file parity supplements that identity.

Final evidence SHA-256 under session `shared/`:

| File | SHA-256 |
|---|---|
| backup-resume-proof.json | d1c7827bb4bc84780397a3db002325dd74ba06bb4950cceeb9a787a626721861 |
| install-stage-proof.json | 7fef33e4862d93f68cfa42b837140d2d79134808d6048a1b72bc811f4578283d |
| install-proof.json | 2f7ee8bce4829da5d0b732fa7ff815375b98927b44c63cbb60292a93ed56fe3e |
| result-install-stage-01.json | b2c081dc64b57f2d6a457673ff7c8d384c0c0f0fa86592aacd20046b326e88dc |
| result-install-post-01.json | ffda8eab5bab0366937f606263846c89d2fd7d92057e4ff99747d6454bad9b86 |
| result-installed-package-01.json | 42fdbf55a34f3171acd0546da4159edafd53bf796abccaf5e9d2213ad900c3d1 |
| installed-package-qa-result.json | 0254e04ba257d62ec6247f2a8c26bbe69d459d5fe92f802e560681d5ac3bab00 |
| release-parity.json | 268a619b6c8cedd1547ec5af63d9004c24360748ba9df265466d6bf1ff3e630a |
| release-qa-receipt.json | f006866cfcc03e7eb7deb25b2d7af161706c9924a1f860e0f153e03159c21f41 |

The final machine-readable receipt records actual installed upgrade/relaunch, preserved state, exact artifact hashes and the explicit `transport: silent NSIS installer`, `updaterUIExercised: false` limitation. It is a publication QA receipt, not an invented canonical protocol-2 handoff receipt. Sergei's requested lean scope is satisfied by the reviewed native and source evidence above. Native every-screen interactions, full live-library processing and in-app updater UI are not claimed.

No new product Blocker/Major was found. Existing QA tray-visibility limitation remains deferred. The retained state backup contains private user data; keep it local and exclude it from commits/publication. Session scratch is left for Sergei as instructed; no further QA execution or edits are pending.
