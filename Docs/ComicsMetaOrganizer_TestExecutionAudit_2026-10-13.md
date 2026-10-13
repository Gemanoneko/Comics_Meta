# CMO v0.1.4 task-local test execution audit

Status: ROUTE ACCEPTED for the fixed final/targeted Python manual handoff graphs. Current original supervisor SHA256: f560cc53ab0e0c535f16d56321d841f16963ec3bd0904190278e7e040b2fb00b; current identity helper SHA256: 1faef0479e9ff4017cb5b9a22fa814b57d4982cac675f78d6f210a3cd8c6d727. Current foreground lease is 60 seconds; total Job deadline remains 600000ms. Earlier hashes, interpreter attempts, 30-second lease and scope statements below are retained history and superseded by the final section. This is an execution audit, not a QA or release verdict.

Reviewed source: scratch/owned_test_job.py SHA256 aa3cf9a052c0d49aca70d759a79458aff438c2930a14c278ad3838686bdd7bd0; scratch/probe_owned_test_job.py SHA256 6ccbdc086f0f0a834ed2a16ca73fb7dd1254cd7a5c309e392060c9e61a476d5d.

The route is scoped to WIP/Comics Meta Organizer-v014. Git Bash launches the fixed command /c/Python314/python.exe -B -m unittest discover -s tests. Fixture writes and logs go under scratch/owned-test-job; no live app, accounts, data, port, or deployment operations are authorized.

Mechanism: native Windows Job with KILL_ON_JOB_CLOSE, unnamed noninheritable handle, no breakaway flags, atomic STARTUPINFOEX JOB_LIST at CreateProcess, suspended child membership verification before resume. Parent process handle is opened once before spawn. Startup-inclusive monotonic deadline is 600000ms. Root exit, errors, timeout, parent death, or supervisor death close/terminate the Job and descendants. API failures fail closed.

Foreground ownership: suite requires a fresh 32-hex nonce and atomic lease JSON counter. Explicit foreground calls renew the counter at most every 20 seconds; no background automatic renewals. Supervisor measures time since changed counter using its own monotonic clock. Without renewal it closes the Job after 30 seconds plus polling/scheduling tolerance. Tool cancellation is therefore bounded cleanup, not immediate cleanup. Host process persistence alone is not treated as caller lifetime.

Evidence: scratch/owned-test-job/containment-probes.json. Seven modes passed in Ender's measured 17.3 seconds: normal exit, shortened deadline (exit124), actual rejected attribute API (WinError50, exit125 before child), missing executable (WinError2, exit125), shortened lease expiration (exit125), abrupt supervisor termination, and exact disposable parent exit. Child/grandchild process HANDLEs were opened before termination and verified signaled; no foreign process-tree kill. Probe controller uses bounded waits and disposable helper with self-expiration20s. Outer controller invocation has hard execFile timeout600000ms.

Limit: parent-mode log contains leading NUL bytes because supervisor and fixture redirect shared parent.log. Held-handle containment observations are independent of that logging defect. This route does not certify test correctness, grant generic infrastructure deployment, or clear a release. Changes to reviewed runner hashes require another audit. Preserve source and JSON evidence through handoff.

Primary mechanism references: [Microsoft Job Objects](https://learn.microsoft.com/en-us/windows/win32/procthread/job-objects), [Microsoft atomic process Job assignment](https://devblogs.microsoft.com/oldnewthing/20230209-00/?p=107812/), [UpdateProcThreadAttribute](https://learn.microsoft.com/en-us/windows/win32/api/processthreadsapi/nf-processthreadsapi-updateprocthreadattribute).

## Parent identity correction

Before suite creation, an externally sampled parent PID was stale and OpenProcess failed with WinError87; no test child was started. The reviewed follow-up resolves --parent-pid 0 as os.getppid() inside the supervisor and immediately holds that exact process handle. Current supervisor SHA256: 0cce24ad250edfc54926c31f1c4f68b467a0e9ec766c14ead621fe7729fe8a36. Controller hash unchanged. Existing seven probes use explicit owned parent IDs and retain their recorded mechanism evidence; the sentinel is a reviewed identity-acquisition correction, not an alternate cleanup route.

## Bundled runtime and scoped dependency extension

The Python3.14 suite route failed before useful validation because PIL was unavailable; this is not a passing suite. Reaudited runner SHA256 d9bc9b039b7d551a51e3e15d81017a03904031fba71f3f7dc1e5e0acfe178d44 changes only fixed work modes, interpreter and isolated fixture paths; Job/lease ownership mechanism remains unchanged. Tests now use the installed bundled Python at C:/Users/AnGeLZzZ/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/python.exe (reported Python3.12.14/Pillow12.3.0).

Parent authorized task-local dependency installation. Fixed dependency mode is python -B -m pip --isolated install --disable-pip-version-check --no-cache-dir --only-binary=:all: --no-warn-script-location --target <absolute task Temp/ender/dependencies> playwright>=1.55,<2. It refuses unavailable wheels, ignores user pip configuration, writes no global pip cache, and installs no browsers. Exact installed versions and complete dependency/runtime manifests must bind the final manual receipt; the version range alone is not reproducible. Fixed targeted mode runs test_v014_review_fixes, test_series_spelling, test_imprints, test_app, test_progress_snapshot and test_worker. Full suite command remains unittest discover -s tests. All work modes require fresh nonce/foreground lease, hard600000ms deadline and audited Job containment. Test fixtures use absolute task-local Temp/ender/fixtures; PYTHONPATH is fixed to candidate, tests and dependencies.

## Final reviewed manual contract and actual outcomes

This is the separately reviewed non-package manual contract permitted by qa-handoff. It is not the package-based automated protocol-2 checker. The original final graph is fixed: identity-before → `python -B -m unittest discover -s tests` → identity-after, under one startup-inclusive 600000ms native Job. Bash grouping redirects the whole graph’s stdout/stderr and stdin `/dev/null`; identity Git subprocesses explicitly use DEVNULL/STDOUT. Parent PID zero resolves `os.getppid()` inside the supervisor and opens that exact handle before child creation.

### Current pinned original harness

| File | SHA256 |
|---|---|
| scratch/owned_test_job.py | f560cc53ab0e0c535f16d56321d841f16963ec3bd0904190278e7e040b2fb00b |
| scratch/manual_identity.py | 1faef0479e9ff4017cb5b9a22fa814b57d4982cac675f78d6f210a3cd8c6d727 |
| scratch/probe_owned_test_job.py | 6ccbdc086f0f0a834ed2a16ca73fb7dd1254cd7a5c309e392060c9e61a476d5d |

Containment is unchanged from the seven probes recorded above: atomic JOB_LIST, noninherited kill-on-close Job, no breakaway, held parent identity, bounded child closure, fail-closed setup. Source-only follow-ups audited fixed command graphs, grouping/stdin plumbing, PID acquisition and lease constant; these are not new ownership mechanisms.

Foreground renewal is only an explicit atomic fresh-nonce/counter update from a foreground tool call. Target interval is <=15 seconds. No automatic timer refreshes the lease. Original work modes close the Job after 60 seconds plus poll/scheduling tolerance without a new counter, or earlier on held-parent death, supervisor death, root completion, error, or hard600s deadline. Tool cancellation cleanup is bounded60s after last renewal, not immediate. The shortened5s containment lease probe is historical evidence of the unchanged algorithm.

The identity helper binds complete tracked/nonignored source paths (including absence markers), re-samples the Git path list, re-hashes source bytes and checks full HEAD/dirty before emission. It binds all three harness files, the complete bundled Python runtime tree, complete Python3.14 supervisor runtime tree and complete task dependency target. File/directory/root reparse points are refused. Optimization retains every path and byte: one lstat per check, unique ancestor checks cached per manifest and revalidated at the end. No unrelated package/runtime bytes were silently omitted.

### Final independent handoff identity

Both agents independently ran the same original final graph sequentially on the frozen candidate; no Docs/source/harness write happened between their identity checks. VERSION was bumped before QA. Before/after JSON is byte-identical within each run and between sender/receiver; separately derived receipt strings are identical. The reviewer inspected the actual files and success lines.

| Field | Value |
|---|---|
| HEAD | 319202243fe7296f985c318a7b08cb5a0f05d140 |
| VERSION / dirty | 0.1.4 / false |
| source | 1cae84149648282b9edfcd091524a269b3ba9a160c8deeb2bec8f0f101a57092 |
| harness | 8cc97055b02176bbc2b21f5c56f126e2d34da5d8c5bd23db2d595aa4231b2658 |
| runtime | 2f52bae6e69588fdb9a08026982bd698c86c53c6edc3c5734c5d49d6088714bf |
| supervisor_runtime | 58648e79bcc186f53eac7d8d661ed4024bb13f8aebed6295b824b0e5b58baf5c |
| dependencies | d1479ba7e98b9ce00431df3c79f7fa0c184bd7a72f2eb326bb89167fd2237f90 |
| declared manual check | unittest pass, 682 tests, 47 DOM skips |
| undeclared npm names | pre-qa/post-build/check-electron/check/test:smoke all n/a |

Actual versions: bundled CPython3.12.14, Pillow12.3.0, Playwright1.63.0, pyee13.0.1, greenlet3.5.6, typing_extensions4.16.0. Package installation was scoped wheel-only to the declared task target, with isolated pip and no global cache/browser installation.

- Sender actual suite: 682 tests in67.999s, OK47skips, native exit0. Evidence: absolute task Temp `ender/ender-final-before-3192022.json`, `ender-final-after-3192022.json`, `ender-final-3192022.log`, `ender-manual-receipt-3192022.txt`.
- Receiver actual suite: 682 tests in67.643s, OK47skips, native exit0. Evidence: absolute task Temp `futaba/futaba-final-before-3192022.json`, `futaba-final-after-3192022.json`, `futaba-final-3192022.log`, `futaba-manual-receipt-3192022.txt`.
- Both agents verified final complete source snapshot files; Futaba’s own copy contains all144 sender-manifest files. Source/harness evidence stays separate from generated report output.

Exact independently derived receipt:

```
manual-qa-receipt/v1 | tool=Comics Meta Organizer | version=0.1.4 | HEAD=319202243fe7296f985c318a7b08cb5a0f05d140 | dirty=false | source=1cae84149648282b9edfcd091524a269b3ba9a160c8deeb2bec8f0f101a57092 | harness=8cc97055b02176bbc2b21f5c56f126e2d34da5d8c5bd23db2d595aa4231b2658 | runtime=2f52bae6e69588fdb9a08026982bd698c86c53c6edc3c5734c5d49d6088714bf | supervisor_runtime=58648e79bcc186f53eac7d8d661ed4024bb13f8aebed6295b824b0e5b58baf5c | dependencies=d1479ba7e98b9ce00431df3c79f7fa0c184bd7a72f2eb326bb89167fd2237f90 | pre-qa=n/a | post-build=n/a | check-electron=n/a | check=n/a | test:smoke=n/a | unittest=pass(682;skipped=47)
```

### Earlier failures and their disposition

Early runs did not produce a usable handoff: stale externally sampled PID (WinError87 before child); unavailable PIL under Python3.14; malformed first-stage logging/stdin plumbing; and a native125 lease stop during model/tool latency. These failures were visible, fail-closed, and never counted as passes. Native ChildProcess.exitCode/mutable status replaced a stale copied scalar status. Initial30s lease became reviewed fixed60s; all original hard600s deadlines stayed in force. A678-test candidate exposed three count-cache fixture handle errors and one stale pilot expectation; explicit cache lifetime and approved imprint-aware expectations were repaired before final runs. Intermediate clean8e19 receipts were real historical validation (680 tests/47 skips), not final319 clearance. Preserved logs/status artifacts distinguish setup refusal, expiry, test failure and final success.

### Separate rendered QA copy (not the formal receipt harness)

Futaba’s current copied wrapper SHA256 a8dd306d67e888124d2afd88e78938b5bc08be7c99d29023cfbec00cd589d9b4 is accepted only for fixed `qa` and `close` modes, outside the original harness. Fixed QA invokes the existing canonical headless-browser.mjs gate with own Temp profile/root, TTL570s, and its fixed Python fixture. Outer Job remains600s, manual work lease60s. On a transient PermissionError reading that copy’s lease AFTER a valid initial read, no renewal is credited and the prior counter/timestamp remain binding; first-read, malformed/nonce/count and expired failures remain fatal. This narrow compatibility handling changes no shared receipt-harness file. Other copied modes, including its5s probe exception path, are not accepted by this audit.

An earlier QA125 sharing-denial stop closed its owned Job; canonical exact CLI stop for owned lease `abf1f3adfd4d` then reported native0, killed0, remaining0, folderLeftfalse. Evidence remains in Futaba owned-job/close.log. No broad process-name/tree kill or new browser launch was used for closure.

Current independent QA fixture SHA256 28d9333a7d7bc9ca8ba514485c1b141abe28c1909a5c2ff0a5765d8868e6a0ec is accepted for the verified319 snapshot: four DOM modules, visible long Series fixture, F39 negative/positive planner cases, cache invalidation and real socket-pair slow headers/body; every public browser request is locally fulfilled or aborted. F39 fixture is synthetic, no live/Ollama connection. CSSzoom-only overflow, equivalent viewport/device-scale reflow and unsupported native UI zoom are recorded separately. That exact rendered graph subsequently passed 67 tests in 28.288s, no skips, native exit0; canonical lease60263938f467 ended with remaining0. Its rendered measurements remain preserved separately. Final behavioral GO is still Futaba’s report.

No current unique harness, receipt, unresolved QA image or failure evidence was removed by this reviewer. They remain active handoff evidence. Only these two owned Docs outputs were edited; no release source, live code/data, browser profile or account was modified.

### Final isolated repeated-retry check

Accepted copied wrapper SHA256 `573f312806486cb691365597d413773cba3321f5dfd0a1b6cf11077a9c448db6`, fixed `retry` mode only, and fixture SHA256 `79c90690564ca3652b6b0b3890209e14e8e0765fe9c666e240bd447051bc5b94`. This adds only the fixed `--retry-only` argument to the same canonical gated command; it selects exactly one new backend test, preserving the passed rendered evidence. The test uses owned fake SQLite rows, rejects duplicate retry requests, preserves count5, and verifies failure transitions5→6→7 stop after each failure. It performs no archive write. Job600s, manual lease60s, parent ownership, logging and sharing-denial rules are unchanged. Its result is pending in Futaba’s final QA report. No other mode in that copied supervisor is authorized by this audit.
