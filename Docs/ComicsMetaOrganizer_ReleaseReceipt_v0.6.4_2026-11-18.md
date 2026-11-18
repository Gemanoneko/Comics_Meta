# Comic Metadata 0.6.4 — Release Receipt

- Release: https://github.com/Gemanoneko/Comics_Meta/releases/tag/v0.6.4 (published, not a draft; latest)
- Tag `v0.6.4` -> source commit `445bd36c79af3565f31ce1a66be4ee89466064c6` (the built commit). Main fast-forwarded to `a4d3ae2` (docs-only commits on top).
- Path: promotion profile `packaged-smoke-manual-update`; `release.mjs --check` then `--publish` under the owned supervisor (native-zero closure both times); no rebuild. Installed update verification deferred to Sergei's manual update.
- Assets, verified on GitHub against local digests:
  - `Comic-Metadata-Setup-0.6.4.exe` 150055860 bytes, sha256 `2cc0f597dada56756af044c5554c1402136ece2c9051ae6cd8192ccf9fca157f`
  - `Comic-Metadata-Setup-0.6.4.exe.blockmap` 157759 bytes, sha256 `30b35fb270c80c03b0d6e50539e5699e5e3fb028e6defec10cd67ce5df862d13`
  - `latest.yml` 357 bytes, sha256 `560ba838f4c4ba0d6ce9477912742c102b9e8b8958d5d072ff8161e2db8dccc2`
- Promotion receipt (`promotion.json`) sha256 `e5cc68eb89f96b7ad0bb5481ffa515b6d15c72c6981dff2cfc9057221b109427`; source manifest sha256 `8507a3806a30537ef43f10ed28b7739803d3ed6d54b81859909912085961ddf5`.
- Clearances: Senua RELEASE CLEAR (`ComicsMetaOrganizer_CodeReview_v0.6.4_2026-11-18.md`); Futaba Tray-smoke GO (`ComicsMetaOrganizer_TrayQA_v0.6.4_2026-11-18.md`, commit 7047c56).
- Logged `--skip-qa` (Jane, under Sergei's overnight authorisation): "Tool-specific Tray-smoke GO report (Docs/ComicsMetaOrganizer_TrayQA_v0.6.4_2026-11-18.md, commit 7047c56); the generic precondition script can't parse that format; the tool's own publish-held.py/create-local-promotion.mjs check it."
- Keep-last-4: GitHub now holds 4 releases (v0.6.4, v0.6.3, v0.6.1, v0.6.0); local tags match the remote after `fetch --prune --prune-tags`.
