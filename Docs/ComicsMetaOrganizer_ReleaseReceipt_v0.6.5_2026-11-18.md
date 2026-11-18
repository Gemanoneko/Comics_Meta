# Comic Metadata 0.6.5 — Release Receipt

- Release: https://github.com/Gemanoneko/Comics_Meta/releases/tag/v0.6.5 (published, not a draft; latest)
- Tag `v0.6.5` -> source commit `1ba12722da19630fd03cdc7111b21a667a1369c9` (the built commit). Main fast-forwarded to the branch `ender/comicvine-name-search` tip `2a6dbaa` (docs-only commits on top of the tagged build; the branch had already merged main).
- Path: promotion profile `packaged-smoke-manual-update`; `release.mjs --check` then `--publish` under the owned supervisor (native-zero closure both times); no rebuild. Installed update verification deferred to Sergei's manual update.
- Assets, verified on GitHub against local digests:
  - `Comic-Metadata-Setup-0.6.5.exe` 150074593 bytes, sha256 `7272187e04d0d74243d958d203b489c7349aaf7f3a5488a794bbe9343af3c1c5`
  - `Comic-Metadata-Setup-0.6.5.exe.blockmap` 157684 bytes, sha256 `7e0e83deb7ba0985075e27cfa02b11976d29b8f932d7b9f431beea4e540a0da7`
  - `latest.yml` 357 bytes, sha256 `1b6b525c1de8cb5d34921d08ec11cd475a1d1a1bbe572513f68b6f19f2564703`
- Promotion receipt (`promotion.json`) sha256 `84bd09a0e34951fca44272a09bbffde6fb2f3b41db8af0caa1564a656e270093`.
- Clearances: Senua RELEASE CLEAR (`ComicsMetaOrganizer_CodeReview_v0.6.5_2026-11-18.md`, names 1ba1272); Futaba Tray-smoke GO (`ComicsMetaOrganizer_TrayQA_v0.6.5_2026-11-18.md`, landed in commit 2a6dbaa). Packaged evidence: `scratch/qa-065-evidence-v0.6.5/` (cited by the QA report).
- Logged `--skip-qa` (Jane, under Sergei's overnight authorisation): "Tool-specific Tray-smoke GO report (Docs/ComicsMetaOrganizer_TrayQA_v0.6.5_2026-11-18.md, commit 2a6dbaa); the generic precondition script can't parse that format; the tool's own publish-held.py/create-local-promotion.mjs check it."
- Keep-last-4: GitHub holds 4 releases (v0.6.5, v0.6.4, v0.6.3, v0.6.1); local tags match the remote after `fetch --prune --prune-tags`.
- v0.6.4 assets re-verified against its local digests (see the v0.6.4 receipt).
