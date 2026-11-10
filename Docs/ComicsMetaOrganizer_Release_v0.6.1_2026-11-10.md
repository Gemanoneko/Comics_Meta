# Comic Metadata 0.6.1 released — November 10, 2026

Published [v0.6.1](https://github.com/Gemanoneko/Comics_Meta/releases/tag/v0.6.1) at 15:45:28 UTC through the canonical `scripts/release.mjs` / `publish-held.py` promotion path. The approved installer was promoted without rebuilding. No live installation, app restart or library migration was performed by the release manager.

## Identity and delivered changes

- Local and remote named tag `v0.6.1` identify the actual built app commit `516c812d90b9482f5cd63003d660f178e0c65444`.
- Publication-time `main` was `4ba975fdafd05798bd2f8aa13df7b51d1ad8ea2d`; its later QA tooling/documentation is separately pinned. Closure documentation advances main without changing the released tag or app.
- Accepted 378-file raw source manifest: `1fcb6ac83fd9218c83387519cfd115c548703bc0c85770b2772031ab7d383a9a`.
- Naming corrections cover padded underscore issue numbers, explicit collection volume/subtitle labels, Book labels, and the supported trailing scan-credit suffix. Legacy filename-derived catalog identities can benefit without rewriting embedded metadata. Existing ambiguity, edition, language, Legends, provenance and write safeguards remain.
- Windows window restoration reapplies the validated saved outer bounds once before maximize/show. This addresses Electron constructor/SetPosition rounding at fractional display scale. Actual upgrades preserved native 900×600 bounds and identical persisted window-state bytes.

## Accepted validation

The current app's full canonical sender and independent receiver receipts matched. Both ran 1,075 Python tests with zero failures/errors and one Windows symlink-capability skip. Shell discovery ran 56 tests: 54 passed, zero failed, two existing explicit opt-in skips; all six window-restoration tests were included.

Both genuine isolated 0.6.0 → 0.6.1 processing and user-paused installation/update flows passed, including real prior/new worker actions, exact window state, credentials/config/manual metadata/recovery/history preservation, production updater/helper/NSIS, natural app Quit and authoritative guest/client closure. Paused processing remained paused until explicit Resume.

A fresh hidden run of the exact 621-file package exercised the actual enabled native tray Quit callback, exited naturally with code 0, and proved complete native ownership zero. Every package member and hash remained unchanged. No host profile installation or real-library write was part of these tests. The bounded collection sample does not establish population-wide physical/digital edition or identifier precision.

Formal [QA GO](ComicsMetaOrganizer_QA_v0.6.1_2026-11-10.md) is pinned by SHA-256 `635233d3d941193d6dbd69134f5bb730c4706eda5f894649a6cdaf89892baa98`. [Code review RELEASE CLEAR](ComicsMetaOrganizer_CodeReview_v0.6.1_2026-11-10.md) is pinned by `a4abea9c0641ea879c0f1e85a69e4497ef3f505055b2c18f9a4e9b13aa8f9922`, with zero Critical findings and two inherited Major/one Minor advisories retained.

## Publication proof

All five actual mechanical preconditions passed without skips after the canonical QA-role selector correction in studio commit `88b8658c8df22694373e66f199062505a0668412`.

The one canonical check returned `validated; not published`, version 0.6.1, three artifacts and `rebuild:false`. The one canonical publication returned the real release URL, three artifacts, `rebuild:false` and four owned commands. Both original bounded owners completed normally with exit 0, complete output, no force/timeout and complete native zero. Publication took 29.806 seconds; all 1,858 publication ownership observations were complete.

Frozen promotion SHA-256: `1484b280d0f00b04d80e4cee6fde8faef969a9cb47dc16bc279fc685aae71ddf`. Strict QA receipt: `3cc8343ef07cd73258580a38e141a1ed7333a6e9f09c6ac9f5157496639560f7`. Build receipt: `99631893210793462526866955f5ae1dc537ecd76152a442fdad0e21d5a7ceb6`. Release notes: `05bcf1d6d284f6acbd453545587c54dcce44c3eb867c4ea3508b28d4c9ac4d3e`.

Independent post-publication GitHub metadata verification found exactly these public, non-prerelease assets. Sizes and server SHA-256 digests match the approved build/promotion/QA lists; no independent remote byte download is claimed.

| Asset | Bytes | SHA-256 |
|---|---:|---|
| `Comic-Metadata-Setup-0.6.1.exe` | 149,538,531 | `888fb8c71aab605afb5201b534b37c54510c40f85a2396f0917befbe49a17aca` |
| `Comic-Metadata-Setup-0.6.1.exe.blockmap` | 156,930 | `3943d19eae2b4a975bc41df82672dd1b04687d833ce0da774c67d77bba94fdcc` |
| `latest.yml` | 357 | `2b0ab3a6d44aff22e369718a78c6ad5e07ac55f4150397b43640c6e5f0af88b1` |

Canonical cleanup completed and independent listing confirmed exactly four GitHub releases: 0.6.1, 0.6.0, 0.5.0 and 0.4.1. The canonical cleanup deletes releases without deleting historical Git tags; those tags remain. Only the exact new named tag was pushed.

Compact selected semantic/ownership records, raw-record hashes, bundle/report bindings and remote verification are retained in [release evidence](ComicsMetaOrganizer_ReleaseEvidence_v0.6.1_2026-11-10.json), SHA-256 `1fe9e79776139c9d0c31d9ebabda963a280e146f4177d0a0e3df660a5e2f0615`. No credential/token values or raw authentication output were copied.

## Retained output and closure limits

The verified current installer/build and required pinned evidence remain preserved while the cleanup owner prepares exact disposable-output work. Earlier automatic-policy-rejected folders and their parents were not retried. The QA report retains the three earlier Futaba roots (819 files / 61,609,739 logical bytes) and the current native-tray private profile (47 files / 1,903,491 bytes): previously measured total 866 files / 63,513,230 bytes, not a fresh disk inventory. The separately rejected empty developer scratch folder and empty external QA container also remain. No deletion of those paths or blanket cleanup is implied by successful publication.

App main was clean and synced immediately after publication; the released tag remains fixed at `516c812`. This closure adds documentation only.
