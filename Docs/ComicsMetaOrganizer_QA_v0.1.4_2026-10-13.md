# Comics Meta Organizer — QA v0.1.4

**Build under test:** 319202243fe7296f985c318a7b08cb5a0f05d140, VERSION 0.1.4, clean and pushed at entry. Date: 2026-10-13. Owner: Futaba.

**Verdict:** GO

No Blocker or Major found. This clears the frozen source above. Report-only release commits may follow; production changes require renewed verification. Deployment onto the live v0.1.3 app still requires Sergei's approval. Senua's independent construction verdict is in the CodeReview report.

Pattern alerts: none.

## Build identity and isolation

This Python tool has no package.json. The reviewed manual Python contract was used, not an automated npm/v2 handoff. Both sender and receiver independently ran the identical fixed identity-before / full unittest / identity-after graph. Full before/after JSONs are byte-identical, including all source, harness, runtime and dependency files, and receiver JSONs equal the sender's retained JSONs. The receiver derived the receipt from its own identity and actual test output; it exactly matches Ender's receipt:

manual-qa-receipt/v1 | tool=Comics Meta Organizer | version=0.1.4 | HEAD=319202243fe7296f985c318a7b08cb5a0f05d140 | dirty=false | source=1cae84149648282b9edfcd091524a269b3ba9a160c8deeb2bec8f0f101a57092 | harness=8cc97055b02176bbc2b21f5c56f126e2d34da5d8c5bd23db2d595aa4231b2658 | runtime=2f52bae6e69588fdb9a08026982bd698c86c53c6edc3c5734c5d49d6088714bf | supervisor_runtime=58648e79bcc186f53eac7d8d661ed4024bb13f8aebed6295b824b0e5b58baf5c | dependencies=d1479ba7e98b9ce00431df3c79f7fa0c184bd7a72f2eb326bb89167fd2237f90 | pre-qa=n/a | post-build=n/a | check-electron=n/a | check=n/a | test:smoke=n/a | unittest=pass(682;skipped=47)

All 144 source files, including input Docs, were copied to an owned snapshot and individually SHA256-verified before any report changed. Final source manifest: 1cae84149648282b9edfcd091524a269b3ba9a160c8deeb2bec8f0f101a57092. Comparing the complete 8e19c665 and 319202243 manifests shows exactly automatic.py, tests/test_imprints.py and tests/test_v014_review_fixes.py changed; renderer assets and other inputs are identical. Final metadata probes and the completed DOM pass used the final 319 snapshot.

Execution used Git Bash, the pinned Python 3.12.14 runtime (Pillow 12.3.0, Playwright 1.63.0), and reviewed task-local Windows Job supervisors. Maximum wall time was 600s, with a 60s foreground-renewed ownership lease. Browser launches used only scripts/qa/headless-browser.mjs, fresh profiles and locally fulfilled/aborted requests. No live port 8765, live data, model service, real source account, signed-in browser, library or real comic archive was accessed by this QA pass. Fake SQLite rows and generated fixture archives were isolated.

## Actual results

| Check | Result and method |
|---|---|
| Final receiver full suite | 682 tests in 67.643s, OK, skipped=47; native supervisor exit 0. Sender: 682 in 67.999s, same result. |
| All 47 skipped DOM checks | Executed all four DOM modules under the canonical offline headless harness; all passed on final source. No DOM skip remains unresolved. |
| Additional red-team/render pass | 67 tests in 28.288s, OK, no skips, native exit 0. This includes the 47 DOM methods plus independent probes and overlapping rendered checks; it is not 67 additional distinct repository tests. |
| Repeated manual retry | One further focused test in 0.131s, OK, native exit 0. Two separate real backend request/failure-state cycles on fake SQLite preserve counts 5→6→7; each failure stops writes again. A duplicate request while the first retry is pending is ignored. No archive write was used for this extra state-machine probe. |

The full suite covers the fraction parser and idempotent catalog refresh, aliases and pilot comparison, date-aware imprints, worker library_root, length/token/transport caps, existing write/ledger protection, filters and write scheduling. Independent probes deliberately tested meaningful trailing dots and ellipses, unsupported accents, letter case and punctuation preservation, real title/accent disagreements, date boundaries and missing years, parent conflicts, and final F39 planner inputs.

F39: an unmapped explicit brand is refused beside a retained publisher from another house, and when the source house is absent. A matching canonical/alias source house permits the brand; an empty publisher permits filling both fields. Both allow_replace states were exercised through automatic.external_plan, asserting fields, changes and replaced outputs.

F38: real socket-pair HTTP probes patched only connection creation and the fixture deadline. One peer continuously trickled incomplete HTTP headers; another sent valid headers and trickled an incomplete body through the actual HTTPConnection buffered read. With a 0.15s bound, both ended at approximately 0.156s in the final pass. The held client socket closed and the peer thread joined. No connection to Ollama was made. Overlong text/response and transport-token cases also pass in the full suite.

F37: 300 fake catalog rows and 101 cache reads caused exactly one full scan, measured by wrapping problems.counts; total measured time was 0.047s. A committed discovery-record update invalidated the cache and caused one further scan; subsequent unchanged reads reused it. Fixture cleanup/lifecycle regressions pass in the final suite.

## Fresh rendered acceptance

Measurements use getBoundingClientRect, scrollWidth/clientWidth, and elementFromPoint at action-button centers and near edges. All files plus all five failure filters were measured at five widths: 30 combinations. A visible long Series and a long synthetic path were included. Real classic scrollbars consumed 15 CSS px:

| Viewport | Usable clientWidth | scrollWidth in all six states |
|---|---:|---:|
| 305 | 290 | 290 |
| 320 | 305 | 305 |
| 360 | 345 | 345 |
| 400 | 385 | 385 |
| 1440 | 1425 | 1425 |

No horizontal page overflow in this matrix. Changed controls have at least 24×24 targets, no clipped control text, and unobstructed center/edge hits. Narrow Details/Folder stacking preserves desktop layout. Reason-to-Last-error gap measured exactly 12px at all five widths. Counts 1/4/5/6/7 and missing count were checked in rows and Details; no of-5 denominator returned. Chips, selected/pressed states, totals, held-only reason visibility, missing-key line, pending Retry requested, failed-request recovery and focus transfer to total pass.

Keyboard Space and Enter operate the chips. Polling retains chip focus. Enter opens Details; Escape closes it and returns focus to its Details button. Existing accessible names and tooltip strings pass the rendered contracts. Native tooltip popup rendering/dwell and the native select menu remain outside headless verification.

**Zoom limitation and retained diagnostic:** CSS zoom 200% at a 640px viewport measured client625/scroll628, a 3px overflow. The first strict CSS-only assertion failed and is retained as diagnostic evidence. CSS zoom preserves the wider media-query viewport, so this result was not relabelled as native browser-menu zoom. A separately labelled 320-CSS-pixel/DPR2 equivalent reflow measured client305/scroll305 and passed. The native browser-menu 200% zoom was not exercised. The historical long-path Details overflow remains a separate pre-existing layout limitation; the amendment did not authorize a general dialog rewrite.

## Review findings and historical round record

F32, F35, F37, F38, publisher aliases, known-parent guarding, date-aware decisions, imprint-aware pilot comparison and library_root regression checks pass. Judy's gap/stack/retry-copy amendments pass. F39 was fixed after the initial 8e19 pass and independently checked on 319.

The earlier eb64759 report is historical evidence, not this clearance. It remains in Git history and in the retained local historical report; its unresolved notes, corpus measurements and old screenshots were not deleted. Off-scope historical notes remain deferred: price-shaped filename decimals, malformed manual API error text, damaged Lens state handling, contrived underscore spellings and long unbroken library/dialog paths. Real provider/model accuracy, GPU pilot results and scheduler timing were not newly certified.

Earlier attempts are preserved rather than counted as passes:

- Pre-final sender: 678 tests with 1 failure, 3 errors and 47 DOM skips exposed counts-cache lifecycle and the stale pilot expectation; corrections and final 682-test pass supersede it. The sender's failed log/source identity remain retained.
- Some early receipt launches ended before tests because of identity/handle/lease plumbing; none generated a successful receipt.
- First independent pass: 18/19 passed; CSS-only zoom overflow failed. Second: 64/66 passed, two missing COMICS_TEST_EVIDENCE setup errors. The corrected 47-DOM run passed completely.
- A later render attempt exited 125 on a transient PermissionError reading the foreground lease. The copied QA runner was separately audited to keep the prior renewal deadline on such a denial; initial/malformed/expired leases still fail closed. The original receipt harness remained unchanged. Its owned browser lease was closed through the scoped canonical stop command, which reported remaining0 and folderLeft=false.
- The first focused repeated-retry fixture lacked its fake discovery schema; initialization was corrected only in the owned fixture. The final focused result is the passing 0.131s run above.

## Process closure, evidence and hygiene

Completed headless pass lease 60263938f467 and final retry lease dbfbfe2a3072 each reported stop-requested and 0 left. Aborted lease abf1f3adfd4d was separately verified remaining0/folderLeft=false. The owned headless root contains only its inert holder bin, no lease/profile folder. All owned supervisors have native completed exit codes. No process is left using the snapshot or fixture root. This localhost tool has no desktop close button at this milestone; no scheduled live server was launched in this offline pass. Installer/tray quit testing belongs to the later standalone-app milestone.

Retained privately under the task-local futaba folder: both final receiver JSONs/receipt/log, prior 8e19 identity evidence, complete source manifests, unique probe/runner sources, all failed-run logs, final render measurements/screenshots (including CSS diagnostic and equivalent reflow), DOM evidence, retry results, scoped lease-closure proof, and cleanup manifest/verification. None of these local screenshots or path-bearing artifacts was copied into the public repository. Ender retains sender manifests, receipts and failed/successful suite logs separately.

Routine disk hygiene used the studio-disk-hygiene planner. Only the finished, individually hash-verified snapshot was selected; no other agent's files, shared runtime, browser cache or user data was touched. The duplicate .env.example was individually reviewed against its source SHA and removed (225 bytes). Frozen cleanup manifest SHA256 57f2e46dccdb7358497d88cc1a342ce71a59ec1b2f55e8c4ddbcd23f1c6f1228 planned 143 files and four directories in five batches. Each batch was checked immediately before its exact literal Bash rm/rmdir command. Verification: complete, 147 absent paths, 0 remaining paths, 1,835,121 absent logical bytes, plus the separately removed 225 bytes. Total 1,835,346 logical bytes removed; this is recorded file size, not measured free disk space. The fixture parent is empty. Unique evidence and sources remain retained.
