# Comic Metadata 0.6.6 — Release Receipt

- Release: https://github.com/Gemanoneko/Comics_Meta/releases/tag/v0.6.6 (published, not a draft; latest)
- Tag `v0.6.6` (lightweight, as for 0.6.5) -> source commit `30e55c40d2bf0d91e9f395d262598fe5fb53ff20` (the built commit). Main carries docs-only commits on top (QA report, MangaBaka pilot doc, QA evidence in promotion schema, review naming the built commit).
- Path: promotion profile `packaged-smoke-manual-update`; `create-local-promotion.mjs`, then `release.mjs --check` and `--publish` under the owned supervisor (closed, native-zero each time); no rebuild. Installed update verification deferred to Sergei's manual update.
- Assets, verified on GitHub against local digests:
  - `Comic-Metadata-Setup-0.6.6.exe` 150076425 bytes, sha256 `f97bb8d9a234beb1e0d242aabf9257983dc321795c4753563491707f0ae07c91`
  - `Comic-Metadata-Setup-0.6.6.exe.blockmap` 157803 bytes, sha256 `a0f167561532ddd0abfab2c98e491c12f026f439a98d63a0024790f1183f4db0`
  - `latest.yml` 357 bytes, sha256 `5fb659c6f1e124c47e9fdd3aa4ea45e74a7db9e00fd02787da0ab6f1a40ca7ef`
- Promotion receipt (`promotion.json`) sha256 `d0998d864c898b691bc20bae45510e551017783c40a6ca627d07cc20d08b3c11`.
- Clearances: Senua RELEASE CLEAR (`ComicsMetaOrganizer_CodeReview_v0.6.6_2026-11-18.md`, amended to name 30e55c4); Futaba Tray-smoke GO (`ComicsMetaOrganizer_TrayQA_v0.6.6_2026-11-18.md`, promotion-schema evidence). Evidence kept at `I:/AI Projects/Temp/futaba-066/evidence/`.
- Gate: `check_release_preconditions.mjs` run with no `--skip-qa` and no `--skip-review`; all 5 checks passed.
- Keep-last-4: GitHub holds 4 releases (v0.6.6, v0.6.5, v0.6.4, v0.6.3); local tags match the remote after `fetch --prune --prune-tags`.
