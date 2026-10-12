# Code Review — Comics Meta Organizer v0.1.1

## Header

```
Reviewer: Senua (Code Reviewer), fresh independent final pass
Date: 2026-10-12
Tool: Comics Meta Organizer
Release candidate: v0.1.1, final-v2, uncommitted frozen working tree
Commit range: e197f97bc77adb5154fed8bbe364bea9212a0957..e197f97bc77adb5154fed8bbe364bea9212a0957
Reviewed delta: that baseline plus the exact final-v2.patch identified below
Files changed: 14 files, +1118 / -111
Stand-down dimensions: none; Electron-specific checks do not apply to this Python/local-web tool
```

The committed range is empty; this report does not invent a final commit. It certifies the bounded Lens/progress stability delta represented by the patch and source hashes below. It does not recertify unrelated historical code or authorize deployment. Any production/test byte change requires reconciliation before relying on this exact candidate clearance.

## Summary

Reviewed the complete 14-file repair and relevant existing consumers for durable Lens intent, Windows ownership/profile cleanup, pause/restart cancellation, verification completion, independent polling, rejected-request reconciliation and complete progress history. No open Critical, Major or Minor finding was identified in this scoped candidate; the always-blocking safety floor is intact within the reviewed delta.

The prior reviewer conclusion was not used as proof. This pass independently read the changed production paths and regressions, reconstructed the patch byte-for-byte, hashed live/frozen sources and all pinned external inputs, and read the actual v2 receipts and fixture runners. Senua launched no tests, application processes, native windows, public requests or service lifecycle actions.

## Identity and scope

- Baseline and current HEAD: `e197f97bc77adb5154fed8bbe364bea9212a0957`.
- Frozen snapshot: `scratch/verification-click-2026-10-12/candidate-final-v2/`.
- Manifest: `candidate-final-v2-manifest.json`; SHA256 `9ed37fff47dda418d539e85736605059e2d1a2a308e8064d5e68abe7b110a80d`.
- Exact patch: `final-v2.patch`; SHA256 `794c647ec7317bd5fc52152264cd8cdb075cc12afec2b300abacd59d1a1ec3d1`.
- Identity/receipt index: `final-v2-identity.json`; SHA256 `38af62ae4926ed0895277908a8b19e535140bc55974781636c79931e698abbd5`.
- Independently matched: 86 live source files, 86 frozen source files, 399 dependency files and 11 additional harness/runtime files (410 external inputs). Zero mismatches.
- Patch reconstruction used `git diff --binary --no-ext-diff BASE --` the seven tracked paths, then sorted new-file `git diff --no-index --binary --no-ext-diff -- /dev/null PATH` outputs. Byte equality and SHA256 matched. Counts use tracked Git numstat plus the seven new files' complete line counts; 14 unique changed paths.
- Independent v1/v2 comparison found only `tests/test_verification_dom.py:65`: remove the route callback default parameter that Playwright overwrote with its Request argument. All production bytes match final-v1. Production was reviewed directly rather than inheriting v1 clearance.

Evidence names above are relative to `data/verification-click-evidence-2026-10-12/`. Provider quotas/backoffs, Yandex provider behavior, cookies/CAPTCHA, recovery/archive data, studio hooks, siblings and native desktop interaction are excluded. The interrupted handoff remains historical evidence; `Docs/ComicsMetaOrganizer_VerificationRepair_FinalCandidate_2026-10-12.md` is the current handoff. Both handoff documents are outside the 14-file patch.

## Rubric

Severity and safety-floor definitions follow `Team/Docs/ProcessRules.md` § Severity definitions.

### 1. Security

- Status: Pass — worker-only private Job admission precedes driver launch; profile/lock redirection guards, fixed local routes, Google URL validation and finite error categories preserve the scoped boundary.

### 2. Correctness & Logic

- Status: Pass — owner/request/generation checks prevent duplicate or replayed intent and late cancellation from committing success; completion requires an expected Google page with a rendered control.

### 3. Crash / Stability Safety

- Status: Pass — closure uncertainty ends the owner instead of permitting in-process reuse; retained outcomes remain truthful, and disconnected writes are handled without a second normal response attempt.

### 4. Performance

- Status: Pass — one aggregate refresh and one request per frontend endpoint remove poll multiplication; independent Lens status avoids the historical collector.

### 5. State & Data Safety

- Status: Pass — descendants must close and the leased profile be revalidated before cache cleanup, with the lease held; failed refreshes retain complete data and caching does not rewrite queue/history/archive sources.

### 6. Input Handling

- Status: Pass — invalid verification URLs cannot launch a browser, rejected POSTs reconcile with fresh state, and unchanged-history omission requires an explicit matching revision.

### 7. Maintainability

- Status: Pass — ownership, intent, snapshot and Lens rendering have bounded modules with focused state/lifecycle regressions.

### 8. Doc/Code Drift

- Status: Pass — amended engine labels, outcome/closing copy and README match the changed behavior; current handoff distinguishes offline proof from native launch uncertainty.

### 9. Build & Release Hygiene

- Status: Pass — the dirty v0.1.1 candidate is pinned by a full manifest, independently reconstructed patch and matching receipts; final commit/deployment remain subsequent owners' work.

## Reviewed invariants and locations

- `lens_verification.py:87` serializes admission, deduplication and receipt state with `BEGIN IMMEDIATE`; the marker alone is not launch authority. `:140` and `:173` recheck owner/request/generation/phase during launch and final success. `:180` closes failures before recording closed/unknown. `:59` cancels server-replaced pending intent; `:43` cancels stale worker-start intent.
- `lens_browser_owner.py:18` requires the browser-worker entry. `:25` assigns the worker to a private kill-on-close Job before Playwright. `:61` refuses closure with any descendant remaining; `:69` checks profile/lock ancestors for redirection; `:78` takes an exclusive profile lease. `browser_search.py:227` stops context/runtime, proves closure, revalidates the exact profile, cleans permitted caches and then releases the lease.
- `browser_search.py:104` and `:116` reject unrelated/error/challenge/blank pages and hidden, opacity-zero or aria-hidden controls. `:200` validates the URL before visible launch. `lens_verification.py:193` clears the challenge after success without resetting quota or cooldown.
- `app.py:514` serves independent verification/control state. `:522` reads the aggregate while obtaining current pause truth separately. `progress_snapshot.py:17`, `:35` and `:77` detect replacement/removal, preserve full legacy data, retain the previous snapshot on refresh failure and omit only explicitly unchanged completed history.
- `static/index.html:147` and `static/lens-control.js:63` invalidate pre-click responses, serialize polling, preserve independent outcomes and refresh authoritative state after rejected POSTs. `static/index.html:138` retains completed DOM for unchanged revisions.
- A rejected Lens POST reaches the existing HTTP 400 exception response at `app.py:662`; it does not exit the service. The DOM fixture uses a non-2xx response (503) to verify frontend recovery. It does not establish a new real-network HTTP 400 integration result.

## Verification receipts and limits

Accepted as bounded **manual-contract** evidence for this Python tool, which has no package.json. These are not package-based canonical qa-handoff receipts or an independent Futaba verdict. Exact input identities, result summaries, exit/closure fields and runner logic were inspected; Senua performed no rerun.

| Check | Receipt | Result |
|---|---|---|
| Mocked Python regressions | `mock-results-1791800785178209600.json` | 180 passed in 13.495 s; owner 14.281 s; completed, root_exit 0, active_after 0 |
| Canonical offline rendered DOM | `dom-results-1791800770289200600.json` | 33 passed in 20.957 s; owner 28.864 s; completed, root_exit 0, active_after 0; canonical closure remaining 0 |
| Windows Job/profile-lock proof with inert children | `ownership-results-1791801187821741500.json` | 5.752 s; completed, root_exit 0, active_after 0; exclusive lease, live-child refusal, graceful release and owner-exit child termination |

Counts are unittest invocations from preserved summaries, including inherited shared cases. All three receipts cite the exact v2 manifest. Receipt SHA256 values in table order:

1. `9afc12786b42d8129f36458bb2fa2f4fe5b56b8b44f56a75eb18474377249260`
2. `69c18515ce804107d093054dd5be76760918681ece942e7a68b5ff074310ac19`
3. `6b1b3ccbf6cb08dab78d40723a202ac4325f11464099c4b951d17213ad4c1c28`

The ownership fixture leaves a sleeping second child under the private Job when its owner exits. The inspected outer runner waits for the complete Job population before reporting `completed`; timeout termination would report `deadline`. Its short completed receipt therefore supports owner-exit termination rather than merely an outer cleanup kill. The proof uses inert children and isolated app.DATA, not Edge or the production profile.

The DOM fixture uses the canonical headless launcher, local route fulfillment and lease `6019bda32249`; explicit closure reports remaining=0. Transparent and aria-hidden completion cases execute against real rendered DOM. History regressions retain 6,000 rows, advance to 6,001, cover legacy/revision consumers and verify unchanged DOM is retained. This exceeds the 5,857 records in the initial audit but is not a post-deployment live-library benchmark. The delayed-progress fixture invokes progress 20 times and observes one request plus an independently accepted Lens click.

Actual headed Google Lens opening remains unverified. The original missing native window cannot be attributed retrospectively because the old flow kept no durable per-click launch receipt. Original progress latency is evidence of the dashboard problem, not proof of a specific native launch failure. This review claims no native success, current-service version or live throughput. Independent QA and cleared deployment remain separate.

## Hygiene and handoff

This review created only durable reports. No disposable probe, cache, export or test output was created; zero bytes removed. Candidate snapshots and failed/successful receipts remain active QA/review evidence. No source, challenge, provider state, worker lifecycle, commit, push or release changed.

## Verdict

- Total open Critical: 0
- Total open Major: 0
- Total open Minor: 0
- Safety-floor violations found in the reviewed delta: 0

**Verdict:** RELEASE CLEAR

Construction clearance applies only to baseline `e197f97bc77adb5154fed8bbe364bea9212a0957` plus exact patch `794c647ec7317bd5fc52152264cd8cdb075cc12afec2b300abacd59d1a1ec3d1` and the pinned final-v2 sources. Futaba's independent behavior verdict and native-opening limitation remain separate.

## Exact changed-file hashes

| Path | SHA256 |
|---|---|
| `README.md` | `4c33aa735b58ea6d11205221e1d90d39acc30c7c6e5f99ba04f627cb772bdb06` |
| `app.py` | `6b9760eff05470aa5f0589317ed75d48607807fd720ac9c3694a25b312590e11` |
| `browser_search.py` | `061bf6c18cb9b8b4f7307bb8c467d726f30f097aa2d750dfd6b0a95518a58f9a` |
| `browser_worker.py` | `6af2c1fd23b0df4230c8f3c4e4f61c4c9a43ce23a801412285dd498fe081370b` |
| `static/index.html` | `73221e620ec84ddd4c9bc16f301bf228b75744c294a179f2b8a3d06de1260259` |
| `tests/test_browser_search.py` | `dfff6145c6c4f4afd9930ccfab4f615631a331a540176c1be988a2dc2ca1fbaf` |
| `tests/test_yandex_dom.py` | `1772ad3c0a73de8fbfa316bb2c8999d30621c056afd370a05e0bec7a5b84eea9` |
| `lens_verification.py` | `9bde31fa1a0a558355e8992c72e42ecaeb5b073e8cf5770d0b4d89028c37aaae` |
| `lens_browser_owner.py` | `11c6136f44d354527d1b182d16a16cfb011a3ffdf030dc6a3b71e23407b21e56` |
| `progress_snapshot.py` | `47a93b7882ea4a554f8643ce48d661dcd22416731bd8e8c7df06ac6a509cf032` |
| `static/lens-control.js` | `ec452a95f200e2ba829582ef8611c72b426a145347ca69713ad7266ddc9a7a53` |
| `tests/test_lens_verification.py` | `fe1f597908681df6684a1b30324567fdc12c82d36c238ac712c05d33bd2a2bc6` |
| `tests/test_progress_snapshot.py` | `2537a26cf8e23213a1ccd2569e51c978c872ed0c86757aca823ca9aafcc18abf` |
| `tests/test_verification_dom.py` | `ffd4ca1d9bb82a6d93986501621ceb57e4dbc674a87248c063d98393ace2142c` |

## Complete frozen source manifest

All 86 entries were independently matched against both live and frozen files. The SHA256-pinned JSON manifest also contains the complete dependency/harness/runtime hashes.

| Path | Bytes | SHA256 |
|---|---:|---|
| `.env.example` | 216 | `60f79463d837dc2fded310fac49cec5e46e439de2cd7a67eb3316ada60792353` |
| `.gitignore` | 299 | `ffe9f41d314fbaaff88297d1e6bba3fe7c16014588f03aefc29839a43257695e` |
| `CHANGELOG.md` | 1509 | `09f767b62c80ded199945b978b8c5e9f982b6c3a28765554321109027d4f7dd3` |
| `Docs/ComicsMetaOrganizer_UXSpec_VerificationLabels_2026-10-12.md` | 6871 | `022bcc5ba27f7cb98943c2916a902335276edea5351b14f682591137fad2c0ee` |
| `Docs/ComicsMetaOrganizer_UXSpec_Version_2026-10-12.md` | 4546 | `566c75ba434e801653701fec0086931cdec7ee5fbbb65c0f8899752d992b4389` |
| `Docs/ComicsMetaOrganizer_UXSpec_Yandex_2026-10-12.md` | 15860 | `a595cfa25cfe74bd626cbc412d59960bbd77a9b5357c5b886f4ff0b71bd6e0a3` |
| `README.md` | 12092 | `4c33aa735b58ea6d11205221e1d90d39acc30c7c6e5f99ba04f627cb772bdb06` |
| `SOURCE_CONNECTORS.md` | 23804 | `8bdc89374cbfc3cba0634cd586a0f379d9f84f8848eb8e8ff000ecd172d7b4c5` |
| `SYNOPSIS_POLICY.md` | 2868 | `83bef3393f3f800f2d45b15b209f0be3327dc51cdef08c71adf367dcd9d1325a` |
| `VERSION` | 6 | `80447316529fc62014fbaa047fb67c51ac30e32830cda370405349d8d66d196c` |
| `app.py` | 37944 | `6b9760eff05470aa5f0589317ed75d48607807fd720ac9c3694a25b312590e11` |
| `archive_conversion.py` | 8639 | `54f2880a39d9af8f7bf66bcb7aa266e64b1705dec203602aa3c24099fc8611dc` |
| `automatic.py` | 23690 | `e6defccc35075e7c28e11de2b94ac9eeed69f02812b311d6f600f6166130a4d4` |
| `batch.py` | 7180 | `e82ea7a240497690f2d3da12a87e18d029e5e2e55491731e16188d39d9075eb1` |
| `browser_search.py` | 13492 | `061bf6c18cb9b8b4f7307bb8c467d726f30f097aa2d750dfd6b0a95518a58f9a` |
| `browser_worker.py` | 7890 | `6af2c1fd23b0df4230c8f3c4e4f61c4c9a43ce23a801412285dd498fe081370b` |
| `config.example.json` | 317 | `6a97806568bab967d195f7992a642f53c1787dc70c6c10e9881b943b4bf16ec3` |
| `cover_tasks.py` | 4459 | `dfbd8b78cbaa1a9ceab67ad6d6d19ccc7f3816a79ffa559c835a2008ce902ad5` |
| `coverage_priority.py` | 6749 | `36e22b270d7aa72f465e2aa5349120596a2f1ec4cfdfced4245bc1e329b7c2f4` |
| `discovery_state.py` | 2564 | `c599941ced52afab8a0298508149204b950ab19a5e0bae3895f9ceb268d59d2a` |
| `free_search_browser.py` | 20426 | `0ab5faa1f460d64721833e0b61055c9f45f27dfe7250e88077277bfa1aacab97` |
| `getcomics.py` | 4655 | `f336c2e8c392380ddc1783c8e0c895836d83a98a1c78e94c0fb7c558a7c1c914` |
| `lens_browser_owner.py` | 4362 | `11c6136f44d354527d1b182d16a16cfb011a3ffdf030dc6a3b71e23407b21e56` |
| `lens_verification.py` | 10924 | `9bde31fa1a0a558355e8992c72e42ecaeb5b073e8cf5770d0b4d89028c37aaae` |
| `local_model.py` | 9765 | `6fb50ba48fab5adf054647fa21747e33fca06a3a54e986904f8579ecc39d9b99` |
| `maintenance.py` | 4356 | `a4000a32152e5ad1e5181c79ddb997009a21181c890f0267701405380caa5109` |
| `metron.py` | 10445 | `10ecf5f67be719d90e5655a90944786d84f95042f30c9bd675139ed478d0fdac` |
| `open_library.py` | 3260 | `c4a53e99815aad84e6ac2a6acd5b373ecf9ab4dadc3051ad30147cfda4287c86` |
| `pause_control.py` | 3501 | `bb5ee1c616be83cdc72d9c9580cb279561c602fbda678e02d30b0c816ebd0d23` |
| `progress_snapshot.py` | 4556 | `47a93b7882ea4a554f8643ce48d661dcd22416731bd8e8c7df06ac6a509cf032` |
| `provider_wait.py` | 1288 | `b20cde0626bf4b0ad5a4c1e96cd1f5ad5956c63c450d7acca7800da13822b911` |
| `providers.py` | 13082 | `1783d9dfaaf589d0f7d2898d10aaf5509412ecc842e1298af1801475381b066b` |
| `publisher_catalogs.py` | 8670 | `c92042f9d52e9f1f7c98e55f29dd01a65af1cc3b2be9c6e10b192041ccf3ea1e` |
| `requirements.txt` | 31 | `03df19e0ea2a0e40f0d41b356cc4869ceded5c7b2ca0d76c52f8848ec92f71a3` |
| `research.py` | 15866 | `28e500f5cb3d099251e2d6dacf52866971d66ed75442eadf9f0fb24605c41f37` |
| `research_runtime.py` | 6996 | `8e336075ac9663c52f5d4fc73308cba2fe9a67569f5f2d4b596f2343813809aa` |
| `reverse_image.py` | 786 | `00cb40c7a73157c9caffd424c4b9240f71b480d76822283f11de3411319c3ad8` |
| `run.cmd` | 103 | `6e80ec6a3dfd837e8d3a23cbac6f62d6f295a3a1e6f1562598d31002c494245e` |
| `scheduler.py` | 5532 | `7e6dcfd13ac664ab1d2388c3748985b1c3bb5bded0a75d4d1cf2355b1f8b77d0` |
| `server_host.py` | 1235 | `910505632fb7c0bb85837a2daf37184ffa8a74aa8849afb1bc8ef05c96dca447` |
| `source_scheduling.py` | 4830 | `6e07cc5dfe3b61dfd7233bf7970fbd7908d293e6cd71a145d864a10d4f6d908a` |
| `start-app.ps1` | 1435 | `b897b9a083bb230c3bc3ee2c6d9ff6090fedabf23f43328cfc9e5e25924138ff` |
| `static/index.html` | 29538 | `73221e620ec84ddd4c9bc16f301bf228b75744c294a179f2b8a3d06de1260259` |
| `static/lens-control.js` | 4906 | `ec452a95f200e2ba829582ef8611c72b426a145347ca69713ad7266ddc9a7a53` |
| `static/reverse-image.js` | 1144 | `93051886dd3ffd8ccd3ad1a1a6370ce3c16a1b6441cba3b72d9a2c7b88528c59` |
| `storage.py` | 625 | `7d805948fe30f6f765838f27a5735bda9d61c007e236e89c1379f45285444ae2` |
| `supervisor.py` | 1002 | `f55cf41f4d75de0f73690b055ab77fe0251b49349b5cfd36a4037d22563e8b5c` |
| `tests/test_app.py` | 13660 | `20e81074ff6e48fad8dc9f6329ac71aec44737c3048276ef477e6d03e394e03f` |
| `tests/test_automatic.py` | 2470 | `29ac3ab6a3b280313557ccc33951dc0051d91708c74592454752eae31104a0b7` |
| `tests/test_browser_cooldown.py` | 5268 | `a159af17c8455984f62e44e3c8df3ae7b8e035b9a0d38603ed661cb69a69a92f` |
| `tests/test_browser_search.py` | 11457 | `dfff6145c6c4f4afd9930ccfab4f615631a331a540176c1be988a2dc2ca1fbaf` |
| `tests/test_conversion.py` | 3506 | `c6cd351088ee785ee3642e02db96351d42e2fd4bc9f7509c9bf28adc30bbda5f` |
| `tests/test_coverage_priority.py` | 11920 | `e4fb8a44c490d8770398df246d0ffd33a7203ddf1ead8b23737fff8e0bdc6dd3` |
| `tests/test_discovery_state.py` | 2573 | `c09b09899e45b059e99d31531782b178b792aa0923581e45031bc76f199061f3` |
| `tests/test_free_research.py` | 34600 | `8350e0ec268b3328088e4e60adb0bdda766e3846fd58722f9a9dc204ea3fd254` |
| `tests/test_free_search_browser.py` | 14027 | `251aa8754ab79472005f5cfe9ab79d8bcc1aaa8127ca77bbf49f998a0a7bb5a2` |
| `tests/test_free_search_dom.py` | 5944 | `7e24da1e2d848ab90b1c2bbb88201decd51b6d70bbe27ad9fd9c29e121d0df99` |
| `tests/test_getcomics.py` | 2247 | `130cddb64d6ee9fc06e598dfbd938fa80f35e2a878dfe81657bf272e0a4123dd` |
| `tests/test_inventory_totals.py` | 1814 | `8d57d71b02b8534f26ff8940238296143f1fadcf94ba1882a97429a559c51fe4` |
| `tests/test_lead_verification.py` | 4176 | `7d4338f167837f186d2771e6bb3a2639f755d6042a1ff096f9148a3b281836f7` |
| `tests/test_lens_verification.py` | 15531 | `fe1f597908681df6684a1b30324567fdc12c82d36c238ac712c05d33bd2a2bc6` |
| `tests/test_live_scope.py` | 797 | `60a27fd507c6d35c2941d01d66b1af8f5144053af0748fdc7c10fa90e0623b70` |
| `tests/test_maintenance.py` | 2227 | `20a8e0a8f99f599431be68eee4b055b11b2a94aa89d944ccfc771f9e2337d841` |
| `tests/test_manual_backup_cleanup.py` | 5911 | `c3f4388591d944f0b57c148213c817c3f70ae8c21ed6951477ec0a1845e3da79` |
| `tests/test_metron.py` | 6388 | `c60824cdb79ba026e28c335092a97a705652e8f17c796b887c0378b8a714ba78` |
| `tests/test_pause.py` | 4202 | `b22106b7380d1b73e85b6813fbebc928aaf7da90f40be86cda67ab643ffb5c0e` |
| `tests/test_pipeline.py` | 3241 | `994d60e3f3c64bc71a8df02ebe71c105be6a1605c2322c0b6e338724cb11abbf` |
| `tests/test_progress_snapshot.py` | 4672 | `2537a26cf8e23213a1ccd2569e51c978c872ed0c86757aca823ca9aafcc18abf` |
| `tests/test_provider_wait.py` | 1702 | `3f63c9064110c12404c736a1ddaa27aeee15d2f20c09b52a44e7e5ade18ddb4e` |
| `tests/test_providers.py` | 6222 | `2b2a9617d098813b15a5f8349885b470d2aee4a9705a416346531a3775809fa4` |
| `tests/test_publisher_catalogs.py` | 8617 | `9f51f8611668f45015fc3fc8ea3bc617eb976eac8c18b8000f2c481b59ad8e9f` |
| `tests/test_research.py` | 2803 | `0c96333fc2cd81cb4bbc77056faa3691edaa2e31161a55137f344230e823fb2b` |
| `tests/test_research_runtime.py` | 10327 | `8ada50208e5973514ffde2faab3d9c56fdeff94db7f08c8cc120ee8b701542de` |
| `tests/test_reverse_image.py` | 714 | `e60101686f7b742048a84e8a12b8fa89228680d6621d19e09d0702a6936edbb4` |
| `tests/test_server_host.py` | 1309 | `30f4997753689393c8e757b3ff7eaa5c0e846b315ce4406fcc8b44b9c9910ff6` |
| `tests/test_source_scheduling.py` | 7185 | `513481e268e289c905a2fbf51ac2c46e7c3850c70fca2ee30511fc127acd8100` |
| `tests/test_state_encoding.py` | 1070 | `453a66578a4d2731cd5271cfb9f9f9ca1a924348e246428d633f0caaa3e33e39` |
| `tests/test_supervisor.py` | 1367 | `a068213a530e072387732e55328377f30922352c8caa9b49622d251518da88a3` |
| `tests/test_synopsis_diagnostics.py` | 3572 | `ee7533696c8bf101c625ba4cf0e5110024ad2294343b3bfd8d3e993d153cc87e` |
| `tests/test_verification_dom.py` | 12767 | `ffd4ca1d9bb82a6d93986501621ceb57e4dbc674a87248c063d98393ace2142c` |
| `tests/test_worker.py` | 2594 | `b596d001cd6435b3ebba5e200f64642cb4a5b299bbfc2eecf27366735c1c304b` |
| `tests/test_yandex.py` | 20375 | `d2f63f96a72d68d9b940a326e76565b09313cff38f4bd6e0df2634e9094867ff` |
| `tests/test_yandex_dom.py` | 13661 | `1772ad3c0a73de8fbfa316bb2c8999d30621c056afd370a05e0bec7a5b84eea9` |
| `web_search.py` | 17377 | `c3b92645e352a6168df0e33bdf00b91e252d2360e424724f0f01f11c4e855e7e` |
| `worker.py` | 7785 | `e7ef6e86ebe473f2c9c68fd5f9b68af46615a8efded7f77ad888224521d4776f` |
| `yandex_verification.py` | 9272 | `4e2e346d67bf000554c275d7265b4743c9ccc3c5bba8bee76e737369c1f7711d` |
