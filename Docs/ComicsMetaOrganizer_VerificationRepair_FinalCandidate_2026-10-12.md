# Verification repair — final-v2 candidate handoff

Ender, 2026-10-12. Final verification complete; independent Futaba QA, Senua review and Judy UX acceptance remain separate gates. This record supersedes the test status in the interrupted handoff, whose historical failures remain preserved. No deployment/reload, release, version edit or production-state change was performed by this finalization pass.

## Frozen identity

- Baseline HEAD: `e197f97bc77adb5154fed8bbe364bea9212a0957`; candidate VERSION: `0.1.1`; working source dirty as expected.
- Evidence root: `data/verification-click-evidence-2026-10-12/`.
- Immutable snapshot: `scratch/verification-click-2026-10-12/candidate-final-v2/`.
- Complete source manifest: `candidate-final-v2-manifest.json`, SHA256 `9ed37fff47dda418d539e85736605059e2d1a2a308e8064d5e68abe7b110a80d`.
- Exact 14-file patch: `final-v2.patch`, SHA256 `794c647ec7317bd5fc52152264cd8cdb075cc12afec2b300abacd59d1a1ec3d1`.
- Final identity and receipt index: `final-v2-identity.json`, SHA256 `38af62ae4926ed0895277908a8b19e535140bc55974781636c79931e698abbd5`.
- All 86 manifest source entries match both the frozen snapshot and current working files. All 399 pinned dependency files and the recorded harnesses, canonical browser launcher helpers, ownership runner, Python and Node executables match their manifest hashes.

Every production byte is identical to final-v1 (manifest `89835c5da3a9b65b865c28c34c82cd68fe353914ed5decfaa881bcad7cf7aa46`, patch `40543108fa22e8de22d06bcdd2eb59ba75051178bcffcaeb18eaada1c25c247f`). The sole v1-to-v2 source difference is `tests/test_verification_dom.py`: remove the route callback's default `body` argument because Playwright supplies its Request as the second positional argument. That Request replaced the intended HTML body and caused the two fixture errors in v1. The existing v2 Python/DOM suites had already completed before this finalization turn; their receipt identities were checked without repeating them. Only the inert-child ownership proof was repeated to bind it directly to v2.

## Verification receipts

All runs use the reviewed Windows owned-command runner with one total `600000` ms wall deadline and descendant closure. `yield_time_ms` is not that deadline. Counts below are unittest invocation counts from the preserved suite summaries, including inherited shared cases.

| Check | Receipt | Result | Suite / owned-wrapper time |
|---|---|---|---|
| Isolated Python regressions | `mock-results-1791800785178209600.json` | 180 passed; exit 0; active_after 0 | 13.495 s / 14.281 s |
| Canonical offline rendered DOM | `dom-results-1791800770289200600.json` | 33 passed; exit 0; active_after 0; canonical closure remaining 0 | 20.957 s / 28.864 s |
| Real private Windows Job, inert children, isolated app.DATA/profile lock | `ownership-results-1791801187821741500.json` | Passed; exit 0; active_after 0 | 5.752 s |

Receipt SHA256 values, respectively:

1. `9afc12786b42d8129f36458bb2fa2f4fe5b56b8b44f56a75eb18474377249260`
2. `69c18515ce804107d093054dd5be76760918681ece942e7a68b5ff074310ac19`
3. `6b1b3ccbf6cb08dab78d40723a202ac4325f11464099c4b951d17213ad4c1c28`

The ownership proof records private-Job admission active=1, an exclusive profile lease, rejection of release while an inert descendant is alive, graceful release after it exits, and owner-exit termination of a second inert child. Windows also created a console-host descendant (active=3 with a child); the invariant is no active descendants at release, not a fixed child count. The release guard waited 5.035823 seconds before refusing the live-child release. The outer owner then verified active_after=0.

DOM lease `6019bda32249` used only the canonical `scripts/qa/headless-browser.mjs`, a fresh owned offline profile beneath `C:/Users/AnGeLZzZ/AppData/Local/Temp/illuminati-headless-comics-visible-2026-10-12`, local route fulfillment and network restrictions. Its explicit closure receipt has remaining=0. No actual application verification browser, production Lens profile, public provider or CAPTCHA was used.

## Reproduce the same manual input contract

Run sequentially from `C:/Antigravity Projects/Studio Illuminati/WIP/Comics Meta Organizer` with Git Bash. Each existing audited wrapper enforces the total 600-second deadline. Do not launch a duplicate while one is active; on a long failure stop and report.

```bash
C:/Python314/python.exe -I -S -X utf8 data/verification-click-evidence-2026-10-12/check-final.py data/verification-click-evidence-2026-10-12/candidate-final-v2-manifest.json 9ed37fff47dda418d539e85736605059e2d1a2a308e8064d5e68abe7b110a80d
C:/Python314/python.exe -I -S -X utf8 data/verification-click-evidence-2026-10-12/run-dom.py data/verification-click-evidence-2026-10-12/candidate-final-v2-manifest.json 9ed37fff47dda418d539e85736605059e2d1a2a308e8064d5e68abe7b110a80d
C:/Python314/python.exe -I -S -X utf8 data/verification-click-evidence-2026-10-12/run-ownership.py data/verification-click-evidence-2026-10-12/candidate-final-v2-manifest.json 9ed37fff47dda418d539e85736605059e2d1a2a308e8064d5e68abe7b110a80d
```

This Python tool has no package.json. These are explicit pinned manual-contract receipts, not a package-based canonical qa-handoff receipt and not an independent QA or release verdict. Futaba must derive her own results on receipt; Senua confirms the manual contract and frozen code independently. The manifest pins full source/harness/runtime files, not merely the live HEAD. This handoff document and the interrupted handoff are outside the 14-file production/test patch.

## Render and behavior evidence for Judy

`dom-1791800770289200600/` retains `lens-320-focused.png`, `lens-1440-focused.png`, `lens-rectangles.json`, the existing dashboard/dialog renders and `ui-rects.json`. Lens rectangle measurements cover required, queued, opening, open, closing, failed, verified and paused states at 320 and 1440 CSS pixels. The passing DOM cases additionally cover blocked Retry explanations, rejected POST reconciliation with healthy authoritative status, sticky outcomes, stale replies, unavailable/recovered independent status, keyboard submission/focus, hidden completion controls and full-history revision behavior. The slow-progress fixture invokes progress 20 times while one response is held and confirms one request plus an independently accepted Lens click.

## Exact changed-file hashes

| Path | SHA256 |
|---|---|
| README.md | `4c33aa735b58ea6d11205221e1d90d39acc30c7c6e5f99ba04f627cb772bdb06` |
| app.py | `6b9760eff05470aa5f0589317ed75d48607807fd720ac9c3694a25b312590e11` |
| browser_search.py | `061bf6c18cb9b8b4f7307bb8c467d726f30f097aa2d750dfd6b0a95518a58f9a` |
| browser_worker.py | `6af2c1fd23b0df4230c8f3c4e4f61c4c9a43ce23a801412285dd498fe081370b` |
| static/index.html | `73221e620ec84ddd4c9bc16f301bf228b75744c294a179f2b8a3d06de1260259` |
| tests/test_browser_search.py | `dfff6145c6c4f4afd9930ccfab4f615631a331a540176c1be988a2dc2ca1fbaf` |
| tests/test_yandex_dom.py | `1772ad3c0a73de8fbfa316bb2c8999d30621c056afd370a05e0bec7a5b84eea9` |
| lens_verification.py | `9bde31fa1a0a558355e8992c72e42ecaeb5b073e8cf5770d0b4d89028c37aaae` |
| lens_browser_owner.py | `11c6136f44d354527d1b182d16a16cfb011a3ffdf030dc6a3b71e23407b21e56` |
| progress_snapshot.py | `47a93b7882ea4a554f8643ce48d661dcd22416731bd8e8c7df06ac6a509cf032` |
| static/lens-control.js | `ec452a95f200e2ba829582ef8611c72b426a145347ca69713ad7266ddc9a7a53` |
| tests/test_lens_verification.py | `fe1f597908681df6684a1b30324567fdc12c82d36c238ac712c05d33bd2a2bc6` |
| tests/test_progress_snapshot.py | `2537a26cf8e23213a1ccd2569e51c978c872ed0c86757aca823ca9aafcc18abf` |
| tests/test_verification_dom.py | `ffd4ca1d9bb82a6d93986501621ceb57e4dbc674a87248c063d98393ace2142c` |

Patch method: `git diff --binary --no-ext-diff BASE --` the seven tracked paths, followed by sorted `git diff --no-index --binary --no-ext-diff -- /dev/null PATH` output for each of the seven new files (expected exit 1 for each). No unrelated dirty document or sibling-repository work is included.

## Remaining limits and preservation

The original user's missing native Lens window cannot be retrospectively attributed: the old path had no durable per-click launch receipt. The observed 27.878-second progress response and two-second overlapping polling are documented evidence, not proof of a native browser failure. Real headed Google Lens opening remains unverified; no claim of native launch success is made from offline/inert tests.

Production service reload, pause/drain and restoration are for the subsequent cleared deployment step. The parent reports the currently running service as 0.1.0; this pass did not query or alter its state, database, plan, challenge/profile, provider quotas/backoffs or worker processes. No commit, version/changelog edit, tag or push occurred.

Studio-cleanup review: all candidate snapshots, failed/unfinished receipts and successful raw evidence still support active independent QA/review, so they remain protected. The new ownership fixture also remains active evidence. No files deleted and zero bytes reclaimed in this pass. After QA closes, inventory exact disposable successful output under the named scratch root before any literal-file cleanup; preserve unresolved failures and compact identity/results. Never sweep production data or the shared scratch parent.
