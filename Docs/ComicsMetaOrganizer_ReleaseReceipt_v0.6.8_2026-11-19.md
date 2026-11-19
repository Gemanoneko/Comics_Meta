# Comic Metadata 0.6.8 — Release Receipt

- Release: https://github.com/Gemanoneko/Comics_Meta/releases/tag/v0.6.8 (published, not a draft; latest)
- Tag `v0.6.8` (lightweight, as for 0.6.7) -> source commit `da503b3d45798bfb7142c377fe2db5704c509153` (the built commit). Main carries one docs-only commit on top (`5e24161`: review naming the built commit, Tray QA report).
- Path: promotion profile `packaged-smoke-manual-update`; `create-local-promotion.mjs`, then `release.mjs --check`, the named tag push (`git push origin v0.6.8`), and `--publish`, each under the owned supervisor (closed, native-zero each time); no rebuild. Installed update verification deferred to Sergei's manual update.
- Assets, verified on GitHub against local digests:
  - `Comic-Metadata-Setup-0.6.8.exe` 150094186 bytes, sha256 `9d477604a1c143f642cc448686472ece3e83aa96a2496c9610bf9d1a9e93c2b4`
  - `Comic-Metadata-Setup-0.6.8.exe.blockmap` 157627 bytes, sha256 `57d45ed2a71fcc5d3e751ed9cab003f14b09823b3239bb95b18cbfa2e1d6db36`
  - `latest.yml` 357 bytes, sha256 `437dab14be3e158b58bbf193d885a1bee23c38cbb7921a30fdc1fc7d413611a1`
- Promotion receipt (`promotion.json`) sha256 `9c9b4a8c8dbb67b28e5c01a25555dbc3af6d79e8a9c23f108be493971e5130f2`; source manifest sha256 `b3ff67e9cfab4d66c59341f5719ea23597070e88a0ac7e6e01d37a7f4eea262f`.
- Clearances: Senua RELEASE CLEAR (`ComicsMetaOrganizer_CodeReview_v0.6.8_2026-11-19.md`, names da503b3, sha256 `2cd82b96a65fb469b1cac428d881a02433d0e40b5c606d121184ae56a106e666`); Futaba Tray-smoke GO (`ComicsMetaOrganizer_TrayQA_v0.6.8_2026-11-19.md`, commit `5e24161`, sha256 `1dc41ee8f749c07e09f0f9c58fba579e0466a443c7397dd0eac9f52d58727596`, promotion-schema evidence; `harness/validate-promotion.mjs` passed, 12 of 12 negative controls rejected). Evidence kept at `I:/AI Projects/Temp/futaba-068/evidence/`.
- Gate: `check_release_preconditions.mjs` run with no `--skip-qa` and no `--skip-review`; all 5 checks passed.
- Keep-last-4: GitHub holds 4 releases (v0.6.8, v0.6.7, v0.6.6, v0.6.5); the publish step's cleanup removed the v0.6.4 release. Git tags remain on both local and remote (cleanup deletes releases, not tags); local tags match the remote after `fetch --prune --prune-tags`.
