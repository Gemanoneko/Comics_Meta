# Code Review — Comics Meta Organizer v0.6.1

## Header

```text
Reviewer: Senua (Code Reviewer)
Date: 2026-11-10
Tool: Comics Meta Organizer (Python engine / Electron desktop)
Release: v0.6.1
App commit range: e21e0fcdab7227fa58a367301019123c56628153..8e66ca4d14ec5a052e9967d6af2590ef957142aa
App endpoint tree: 563e6e735ac45a3c3cbb794c41907e680a6ed90d
Committed app-range diff: 40 files, +5183 / -51 (includes documentation)
Separately reviewed unshipped tooling: exact SHA-256 table below
Tooling/documentation base HEAD: f77f041b9dc37faf348a94ce15f5469331825bf1
Final tooling commit: pending; byte hashes below are authoritative until bound to its commit
Stand-down dimensions: none
```

The baseline is the previous release review's endpoint. v0.6.0 points to later documentation-only commit `11ae3c64d4101969526e388ac9da331948dc4f57`. This report extends this release's earlier review through the final QA repairs at `8e66ca4`; it does not move the accepted app/tag/build source to a later QA-tooling commit. The app snapshot has 345 files and raw source-manifest SHA-256 `11b971aef5739c9e2e8e3b46094509728b87e2bee98e685237e29116c05e6ad3`. Exact raw archive bytes, including line endings, define that identity.

## Summary

Reviewed the four conservative filename-matching fixes, captured-index evidence stamping, cache/catalog refresh, focused-runner refusal controls, isolated Python UTF-8 launcher and eight QA repair files. Extended construction review to the separately pinned Sandbox lifecycle, genuine installed updater observer, fixture, data-only build/QA/promotion adapters and unchanged publisher interface. The final geometry fixture measures settled native and persisted state; it does not tolerate a changed rectangle. No open Critical finding or safety-floor violation remains in these bytes. Two inherited Major advisories and one inherited Minor remain. This construction verdict does not assert that either final Sandbox phase has passed.

Severity follows `Team/Docs/ProcessRules.md` § Severity definitions.

## Rubric

### 1. Security

- Status: Pass — product renderer/IPC privileges are unchanged; reviewed tooling uses fixed argv and pinned helpers, validates actual inspector targets before observer/cleanup mutation, limits maps to read-only inputs and owned output, and confines shutdown to an authenticated disposable WDAG guest.

### 2. Correctness & Logic

- Status: Concerns.
- **I1 [Major, inherited field policy]: content identity does not prove digital/print identifiers.** `gcd_matching.py:128` (`Matcher.gcd_fields`) emits qualifying ISBN/GTIN; `automatic.py:223` onward fills empty fields and can replace provenance-eligible app-written values. The new collection match cannot compare an eISBN visible only in archive indicia. The sampled digital collection indicia eISBN `9781684064809` differs from candidate print ISBN `1684052491`. Title/volume agreement does not establish edition-specific identifier equivalence. Existing human/external ComicInfo identifiers remain protected. This is the established approved field policy, not a newly demonstrated false content match; do not claim exact digital/print edition precision.
- **I2 [Major, inherited 0.6.0 M1]: mixed-provider synopsis Notes can omit GCD attribution.** `automatic.py:674` still relies on `outcome == 'queued'`, although the queued metadata may come from ComicVine; unchanged and not repaired here.
- New collection fallback requires explicit structured syntax, collection record, volume, actual issue publication/sale year, subtitle agreement where supplied, and a unique candidate. Existing matches/ambiguity take precedence. HC/TPB evidence remains distinct.
- QA adapters require both real processing and paused phases, actual owner success/closure and pinned producer evidence. They do not infer a successful install/update from a pass flag alone.

### 3. Crash / Stability Safety

- Status: Pass — reviewed error paths preserve failed outcomes, bound inspector calls and settlement waits, attempt graceful Quit only on the exact verified connection, and abort only the captured real private app Job; independent guest shutdown and strict host VM/client closure remain outside that Job.

### 4. Performance

- Status: Pass — filename fallback reuses indexed queries only after the prior series lookup is empty; source pacing remains, geometry polls are capped at five seconds inside the original deadline, and each Sandbox session retains its original 600000 ms bound.

### 5. State & Data Safety

- Status: Pass — filename refresh preserves deliberate catalog overrides and embedded identity; index evidence uses the captured pointer; existing archive backup/provenance/readback paths are unchanged; isolated fixtures exercise actual state, four decrypted synthetic credentials, geometry, history/manual/recovery preservation and real updater handoff without mapping host profiles.

### 6. Input Handling

- Status: Concerns.
- **i1 [Minor, inherited 0.6.0 m1]: GIF/BMP credits enumeration is incomplete.** `local_model.py:99` and `local_model.py:194` omit native GIF/BMP names from opening/credits enumeration despite supported decoders.
- Unknown scanner suffixes, unpadded title digits, nested Book/Part/Chapter forms, language/Legends/Count conflicts and ambiguous collection identities retain conservative handling. Tooling manifest members reject traversal, duplicate paths and links; output creation uses fresh owned locations.

### 7. Maintainability

- Status: Pass — filename syntax is shared, the focused runner preserves discovery failures, QA adapters separate construction facts from behavior verdicts, and reusable inspector/geometry helpers have meaningful negative controls.

### 8. Doc/Code Drift

- Status: Concerns — `automatic.py:652` says “Issue or edition identity checked”; this is not proof of digital/print equivalence for I1. Retained failed Sandbox attempts are correctly described as failed or partial observations, not QA acceptance or proven causes. I1/I2 are counted once under Correctness.

### 9. Build & Release Hygiene

- Status: Pass — version/lockfile agree at 0.6.1; accepted production source remains 8e66; build inclusion covers the new root Python module; data-only adapters bind the actual source/build/artifacts and versioned reports, while the existing publisher checks the exact remote tag before publication and exact assets before cleanup.

## Fixed during review

- Captured-index provenance race: return stamps now use the already captured active index; pointer-switch regression retained.
- Collection-year fallback no longer substitutes series start when actual issue date is absent.
- Focused runner no longer drops `unittest.loader._FailedTest` or silently accepts absent/empty requested modules.
- The isolated production Python launcher explicitly supplies `-X utf8`; its regression executes the real launcher with a meaningful negative control.
- QA repairs use the real Recovery dependency/copy, actual accessible names, stable integer clock, explicit isolated child import paths, approved measured typography and retained DST/layout vectors.
- Sandbox preparation corrected the actual registration display name, ledger fixture shape, OS-backed shutdown identity, four-key decryption and real paused Resume/core-action assertions.
- Host identity moved from an unsupported pretty-list assumption to exact successful event2500 nonce/session/manifest/guest-PID binding, raw HCS inventory and exact pinned packaged AppModel201 UI activation. Closure still requires SystemExited result zero, raw absence/full baseline restoration and retained UI signal.
- Inspector failure cleanup initially could resume/quit a connection whose identity check had failed. The final code requires the same verified connection and resets verification on connection switch/close; negative controls exercise the actual cleanup helper.
- Setup/dashboard readiness now observes completed frames and preload capabilities. Once-only dashboard action submission does not depend on the old renderer promise surviving navigation.
- Running-main expressions use actual `process.getBuiltinModule('module').createRequire` anchored at the verified installed app after read-only PID/image/resources/profile checks, rather than nonexistent global CommonJS `require`.
- Geometry no longer treats immediate `setBounds` output as persisted state. A fresh actual window.json must agree with native normal/maximized state for 600 ms, is recaptured before replacement, and must restore exact bytes/hash and bounds under unchanged display workArea/scale. Real two-DIP changes still fail.

## Exact accepted app and artifact identity

The following hashes are from the accepted raw 345-file snapshot, not a CRLF-normalized working-tree comparison:

| File | SHA-256 |
|---|---|
| app.py | bca8da7dbccc016e847e844ea741b6cdfa9d2f630a11ae3dfbb2d6a5eaf7ea07 |
| research.py | 41cb9918cc67bc9de8c0e0dd047f4752b03721653b7472b5c5d1472c7fd3d985 |
| filename_identity.py | 708dab3e3fc3ac53c7bb611dc4aece2a02ee03b87512ccf94cb663ae06f9cc53 |
| gcd_matching.py | d9d811ee241e9d9b6a822ee198fd14b20233677d0a1d5e562cde9586bd4b68b1 |
| gcd_offline.py | badf157008f8c6f8c2ae51ed7c159e9baabb17f75728445dfff8ac5f48e65e5c |
| metron.py | 8b87aad2dba391b4ff8858806684f49e6151975ed76859d89b7b1c3c24149747 |
| scripts/check-python.cjs | 6f359e57fdb270ac78abeeb61323b26661f4e233646e684ef33a181f2ad2e03d |
| tests/test_check_python.py | 36e41b746f9c7253f76b5217d97d5082a890fa75546ad89e3dce951d4a446552 |

Actual production installer: `Comic-Metadata-Setup-0.6.1.exe`, 149538466 bytes, SHA-256 `718590fb3524cf2ba9b7544c92ca94a2698a47fd26e64185cf3aae18af7f736d`. Blockmap SHA-256 `00698173e8cb3b8807ab0a3c32a885bab27d9ef327c499366d39bd398d31fcf4`; latest.yml SHA-256 `b6e75f57692123ec1a709ea750228dc7de5e30c829e2dd6917e44301d45fa18a`. These identify reviewed build mapping, not a claim of final install/update QA acceptance.

## Separately pinned unshipped tooling

Paths below are relative to `scripts/packaging/install-update-qa/`. They are not added to the accepted 8e66 app artifact by this report. Current documentation base is f77f041; final tooling commit must later be recorded without substituting it for the tested app source.

| File | SHA-256 |
|---|---|
| binding.test.mjs | c6a7354b1d10e883ddf951a1c29a17923a742b2c00f493467de341dd0c3f29c1 |
| build-receipt.mjs | 4cd272b0c2d4d95df9bf5b6e238c671b329462410fc03397da9a016b3fd79abd |
| build-receipt.test.mjs | 98852ce076ae420b2168f9990d1d54064528b2772a1dd8d133545c9c8e456a94 |
| common.mjs | d878a4609ef52f2393b91196a67bfb639e764c024c14a238c82a9724fd04d533 |
| common.test.mjs | f323d3e77396267a68cee643a723804a985650c9a25db00ccfe8dc701172123d |
| create-promotion.mjs | ffb596e6317df05e5557055a9853b8d63e41aad357f4475448a7653327e6edcd |
| failure-abort-native-probe.mjs | dce8619ace4c7d44d17dd8419e2f3b84267a9d176d0bbed4dea7e54d02c224d4 |
| geometry.test.mjs | f0d72b1b777db5442c5863a05c5af2840f0832af2b54601b0a74f9d667055eba |
| guest-entry.mjs | 960acc654c866797096803810688fa135f4b40554aacbb83fe29db3f0f36c96f |
| guest-update.mjs | fc978e0fea5d233696648cfbe1cd3c1cc7b4eaf968407422ff8f4f34fddd0fa4 |
| host-run.mjs | 279a6075a55445d87566304bf52e14ecad9297e75e52b82517ccf267d6ff1f65 |
| host-session.mjs | cb672f833f8a78916c85149940c82d5dc2508176616966eb702c04607d8778da |
| inspector-failure.test.mjs | cd9fa084aa09b94539f283def40144a1a1a59844ef281acb6006e68253ae1a39 |
| module-access.test.mjs | 0bf70532784c7e1a713b4f21dd2db9c207e1976f1caab47c10e656318797b058 |
| observer.cjs | ad3c0b61b7e35846d7bd14c686b603ae2ffb1334475d10bfb81ff4a922b4751c |
| prepare-input.mjs | 18f5923c7d766b276f300f23408cbd974bdb186c1f217b16e5ae0b1aadab9fdb |
| qa-receipt.mjs | 3f37a063b541bed2c0219a081f73baa9626389766a9aa679813c32cceb656aef |
| qa-receipt.test.mjs | 5682a49fdc23ed8219e27c6b07777e3e172ae8fc23d8178d80adde80e8d14e3f |
| state-fixture.py | 855ab20b11da8ce2fe307b25497d27a2864fe0897ee842522f97abf5d4e81e6d |

Final reviewed runtime staging: retry07/input, 2046-file manifest SHA-256 `75e740c2eb289363483ff9e3ee718146d488bcc5ff02536e5c643860fb6b1355`. It differs from retry06 only in common.mjs, guest-update.mjs and fresh plan. `prepare-input.mjs` is the original data-only staging tool and refuses the already populated original input; it is not a retry07 launch route.

Unchanged publisher interface and helpers under `scripts/packaging/`:

| File | SHA-256 |
|---|---|
| publish-held.py | 189596c6bbb508981d5f1828ec802c67be70a70b2da4ce796f9f114a974ea3c5 |
| held-paths.py | 55cb91c66dacd9e74ca8152ea899c6ac4f109397f09b8838146c31437a15c511 |
| owned-job.py | 8ba5c37a2c6f3fc87478ac1d34c6c7235738a8a27a420dbb2ce34a20549dec15 |

Canonical owner `bounded-check.mjs` SHA-256 `89ecbd30698cae696ba52d677f31bfaa505c87227c22f85e0bb6a2103475fcbc`, child `240a6a96a32f08989439387d5d6ab75d17e1bcf243863d31d2ff7287f68d1e42`, and 92-file ownership addon manifest `122eca8f1ad057bd86867f8e302c60fcaa5b6dba5ff4e660cfd860cf40769617` remain unchanged.

## Verification and limitations

Senua performed source/diff/hash and producer/consumer contract review, not application, test, build, inspector, installer or VM execution. Committed app-range `git diff --check` passed. Existing successful focused/full entry and build records were read or attributed; their behavior acceptance belongs to Futaba.

The actual native-abort probe was audited at `native-probe.json` SHA-256 `906dfbe4c22770fb05b18e5348620cadb5b4c6047cb3443bfd7cf7f4fa6216ab` and outer-owned SHA-256 `0ce73335b53725fec697cc6fe627d4061cfad7c60cbd405cbf0951be342ed8ec`: inner six live members were terminated through the captured Job, root/leaf signaled and native complete/zero, while the unrelated outer sibling remained alive and then quit normally. The inner forced/output-incomplete result is correctly retained as failed by design; outer owner is normal/complete/zero. This proves that tested API path, not final app QA.

The data-only build translation was audited against actual source/build/artifacts: receipt SHA-256 `3ceb3255106376e3dbe3b5ffd76473de432ddaeb575287111018daaed13e0b65`; four actual controls include equal-size installer tampering, wrong version and incomplete owner refusal. QA's six early controls originally comprised four common controls and two missing/synthetic-evidence refusals; later runtime controls do not substitute for real successful phase records.

Literal producer/consumer contract checks cover: session request/start digest and nonce; host/guest normal native closure; kernelLaunch/kernelExit/clientActivation/finalObservation; prior registration, old-engine helper receipt and old natural exit; next identity/version/registration/one engine; actual four-key decryption and manual/history/recovery state; before/after exact settled geometry; paused no-write then actual rendered Resume/core action; actual packaged Quit and process absence. Some assertions, including 621 installed file hashes, no-write timing and natural next exit, are established by the pinned guest producer before its successful record, rather than independently reconstructed by the adapter.

At this report's preparation, final processing/paused Sandbox acceptance, actual QA receipt translation, final promotion config/pins and the publisher's read-only check are pending. Previous attempts are partial/failed evidence only. No successful QA record was fabricated to exercise the publisher. Final promotion must pin actual versioned GO/review report bytes, exact runtime/helper/cleanup/notes/artifact bytes and tested source; a later tooling commit is not the app tag target. Original source/build receipts referenced by derived evidence must be retained or moved with updated pinned references before scratch cleanup. No Senua scratch was created.

## Verdict

- Total open Critical: 0.
- Total open Major: 2 inherited (I1, I2).
- Total open Minor: 1 inherited (i1).
- New unresolved findings in reviewed construction: 0.
- Safety floor: intact in the reviewed final bytes.

**Verdict:** RELEASE CLEAR

Construction clearance covers the explicit app range and separately hashed tooling above. It does not waive independent version-matched QA, two genuine installed update phases, actual receipt/promotion validation or Sully's release procedure.

