# Comics Meta Organizer v0.3.0 — QA

Futaba, 2026-10-18. Correctness regression only; no speed benchmark or throughput comparison.

**Source correctness:** GO for the frozen candidate and tested scope below.

**Verdict:** NO-GO

The overall verdict is for installer release: native installation/update, packaged behavior and tray Quit/descendant exit are not certified. No product correctness failure remains in this focused pass. This report does not authorize publishing or replacing the running app.

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
