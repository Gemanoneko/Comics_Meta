# Comic Metadata 0.6.7 — Release Receipt

- Release: https://github.com/Gemanoneko/Comics_Meta/releases/tag/v0.6.7 (published, not a draft; latest)
- Tag `v0.6.7` (lightweight, as for 0.6.6) -> source commit `9d1ad1af7c3e3f6c0db86b052d8372c8f1c5ad1b` (the built commit). Main carries docs-only commits on top (review naming the built commit `17c2168`, Tray QA report `02fb39a`).
- Path: promotion profile `packaged-smoke-manual-update`; `create-local-promotion.mjs`, then `release.mjs --check`, the named tag push, and `--publish`, each under the owned supervisor (qa-handoff `runOwned`; closed, native-zero each time); no rebuild. Installed update verification deferred to Sergei's manual update.
- Assets, verified on GitHub against local digests:
  - `Comic-Metadata-Setup-0.6.7.exe` 150087939 bytes, sha256 `ff3d740a5366892c1a4e940dc7b132a0220c2c8d42481135fef9de6ea842984b`
  - `Comic-Metadata-Setup-0.6.7.exe.blockmap` 157652 bytes, sha256 `52bbafbb8573448fc36ed598fa94be4a932fed749a4e728542623cbb8d71c1f3`
  - `latest.yml` 357 bytes, sha256 `0ea617cd773a71d6358edfe26a9cbd9dd35d947c7c0e9503c054c3492deb84ac`
- Promotion receipt (`promotion.json`) sha256 `99b587baf3a27c2a5f2cd71a8e0fe4813d47407fde4bca0f5fb1743e34620a5a`; source manifest sha256 `f27f3e9ed6045641da158af9db61e37779fda3f0618b2f25dad1ddb72c4fd3cd`.
- Clearances: Senua RELEASE CLEAR (`ComicsMetaOrganizer_CodeReview_v0.6.7_2026-11-18.md`, amended to name 9d1ad1a, sha256 `d15d59b2aebf491ef0afc893ad844ed3ae95f97fb2f231a8f65abbbc9d946905`); Futaba Tray-smoke GO (`ComicsMetaOrganizer_TrayQA_v0.6.7_2026-11-18.md`, commit `02fb39a`, sha256 `b13f448b3afd0ff6494a0dfcc11a5c573155e866c981fa62d1c2e7fc24a47e58`, promotion-schema evidence). Evidence kept at `I:/AI Projects/Temp/futaba-067/evidence/`.
- Gate: `check_release_preconditions.mjs` run with no `--skip-qa` and no `--skip-review`; all 5 checks passed (unlike 0.6.4 to 0.6.6, no skip was logged).
- Keep-last-4: GitHub holds 4 releases (v0.6.7, v0.6.6, v0.6.5, v0.6.4); the publish step's cleanup removed the v0.6.3 release. Git tags v0.6.1 and v0.6.3 remain on both local and remote (cleanup deletes releases, not tags); local tags match the remote after `fetch --prune --prune-tags`.
