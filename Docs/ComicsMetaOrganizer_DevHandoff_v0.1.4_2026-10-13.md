# Comics Meta Organizer v0.1.4 — development handoff

Final candidate: `319202243fe7296f985c318a7b08cb5a0f05d140`, VERSION `0.1.4`. Production edits stopped; feature branch clean and pushed before report writing.

All handoff findings and Sergei’s four decisions are implemented. F39 additionally prevents an unknown source imprint from accompanying a retained Publisher when the house is missing or differs. Human values remain protected.

Final sender: 682 tests passed in 67.999 seconds, 47 browser tests skipped. Final receiver: 682 tests passed in 67.643 seconds, the same 47 skipped. Both independent receipts match exactly; full before/after manifests are byte-identical. Futaba verifies the browser controls separately; the final browser result is recorded in her QA report. Source manifest SHA-256: `1cae84149648282b9edfcd091524a269b3ba9a160c8deeb2bec8f0f101a57092`.

Live v0.1.3 code, service, catalog and comic archives remain untouched. The decimal-number catalog refresh has not run on live. Deployment requires Sergei’s separate approval.

The development record below retains the earlier candidate and failed-run history. Its older verification and “Left” sections describe those stages; the final candidate and receipts above supersede them. Current QA/review verdicts are in the separate versioned reports.

---

# Comics Meta Organizer v0.1.4 developer handoff

Frozen candidate: 8e19c665a28e32af494e924b3f63fb3c251e834f, VERSION 0.1.4, clean and pushed by Sully. Live code/data/service never modified. No deploy performed.

## Changes and root causes

- F32: end trimming removed meaningful title dots; one cover reading could invent accents; punctuation-insensitive contraction corroboration treated Mr T as Mr'T. Preserve dots/ellipses, require separate indicia corroboration for accents, use explicit apostrophe spelling. Filename wording remains.
- F35: stripping every leading zero changed 0.5 to .5. Preserve decimal zero; transactional idempotent catalog migration repairs only rows still holding that exact old filename parse. Archives and embedded metadata untouched. Migration has never run on live.
- F37: progress rescanned unchanged records each poll. Cache counts by SQLite data_version on an owned connection. Files.close/context manager and Snapshot.close release it; root reconfiguration closes the former catalog. Discard fallback handles short-lived collectors.
- F38: credits output had no generation/response cap; socket timeouts alone could reset during trickles. Cap 1,024 tokens, 32,000 response bytes and 4,000 chars/field; owned raw socket watchdog shuts down at a total 30-second deadline across headers/body. Expired/malformed/overlong reads mean no reading. Pilot uses same bounded transport.
- Canonical Publisher aliases now agree. Automatic and manual preview/apply use guarded plans: a new Imprint must belong to the Publisher that will remain; historical parents use the retained/effective Year. WildStorm Image before 1999/DC from 1999; Archaia independent before 2013/BOOM! thereafter; missing dates preserve uncertainty.
- Pilot comparisons use imprint parents, including Vertigo/DC and Skybound/Image. Letter-case-only and punctuation-only Series changes keep existing text.
- Worker library_root fallback no longer eagerly evaluates missing root.
- Judy's committed amendment implemented: stacked actions <=400px, 12px Details error gap, honest Write attempt N failed copy without denominator. Rendered acceptance remains Futaba's task.

## Exact owned changed paths

app.py, automatic.py, imprints.py, in_book.py, local_model.py, pilot_credits.py, problems.py, progress_snapshot.py, provenance.py, worker.py, static/index.html; tests/test_api_redaction.py, tests/test_failure_filters.py, tests/test_failure_filters_dom.py, tests/test_imprints.py, tests/test_progress_cap.py, tests/test_publisher_agreement.py, tests/test_series_spelling.py, tests/test_v014_review_fixes.py; README.md, SOURCE_CONNECTORS.md, Docs/ComicsMetaOrganizer_Brief.md.

## Verification

102 affected tests passed in 13.216s after the lifecycle correction. Final frozen graph ran identity-before, complete unittest discovery, identity-after under one 600-second Windows Job deadline. 680 tests passed in 67.760s, 47 DOM tests skipped. Native process exit 0; full before/after identity JSON byte-identical. 144 source files, 3 harness files, 12,119 bundled runtime files, 9,997 supervisor runtime files, 418 dependency files bound. Exact actual manual receipt is ender-manual-receipt-8e19c66.txt; full identities and log are ender-final-before-8e19c66.json, ender-final-after-8e19c66.json, ender-final-8e19c66.log. This is the separately audited manual Python contract, not an automated package protocol-2 receipt.

Prior failed frozen suite: 678 tests, 1 stale pilot expectation and 3 SQLite fixture cleanup errors, 47 skips; corrected before final pass. Evidence retained in scratch/owned-test-job/final-15269b46-unittest-failed.log. Earlier precheck failures and stale exported scalar status are preserved; no successful receipt was claimed for them.

## Execution and cleanup

Task-local runner establishes an atomic non-inherited kill-on-close Windows Job before resuming the child; normal completion, deadline, owner exit and supervisor termination close descendants. Seven containment fault probes passed. Fixed offline graph only; no general execution/deploy permission. Manual foreground lease renewals target <=15s; abrupt tool loss cleanup is bounded 60s plus scheduling/poll tolerance, not immediate; absolute 600s never extends. Native ChildProcess.exitCode and mutable status object are authoritative.

No owned process remains from sender (native exit 0 and Job closed). Keep scratch harness/controller/identity source, task-local dependency target, receipt identities/logs, failed-run evidence and leftover generated fixtures until Futaba finishes independent receiver and rendered/adversarial QA. Disposable fixture remnants can then be reviewed and removed from the explicitly owned Temp/ender/fixtures root; preserve durable reports and unresolved evidence. Do not delete shared bundled runtimes.

## Left

Futaba independently repeats the identical final graph and derives matching receipt, then fresh UI/adversarial QA (including real socket-pair deadline probe). Senua final review, Sully release. Live deploy requires Sergei's separate OK. No production edits pending.

## F39 follow-up

New frozen candidate319202243fe7296f985c318a7b08cb5a0f05d140 supersedes8e19. An unmapped explicit Imprint uses the verified source Publisher as house evidence; when a Publisher remains, missing or mismatched source house suppresses the new brand. Mapped parents take precedence, populated human values stay, and an unknown standalone brand without Publisher stays. Exact3paths automatic.py, tests/test_imprints.py, tests/test_v014_review_fixes.py.104targetedtests passed13.351s; new final graph682tests passed67.999s,47skips, nativeexit0, completebefore/afterJSONbyteidentical. New receipt/identities/log end with3192022; prior8e19results retained as historicalevidence. No live changes.

## Verified task cleanup

Ender removed only his verified disposable fixtures: 13 files and 8 empty directories, 738,471 logical bytes. Frozen planner checks, literal nonrecursive Bash removal, and final absence verification covered all 21 paths. Futaba confirmed no active use. Unique runner/probe sources, receipts, full manifests, logs, dependencies and shared runtimes are retained. No source, live data or Git history was removed.
