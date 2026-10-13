# Changelog

## [v0.1.3] - 2026-10-13

### Added

- Comics are identified from their own covers: Series and Number when the cover reading agrees with the filename, and whole books by Series. This applies to empty fields only, with provenance recorded. The publisher-from-cover switch is off by default.
- Multi-comic write plans per pass, with a per-comic edit guard and failure isolation.
- Metron name variants and variant covers.
- Yield ordering of lookups.
- A credits-page reader is built but off.

### Changed

- Folder selection is much faster.
- Yandex is removed; zero-yield sources are switched off by default (reversible in config).
- Held comics back off without repeating work.
- A failed write removes only its own backup, and write retries are capped (1/2/4/7 days, stop after 5 until the file changes).
- The progress payload is capped; the library walk runs every 6 h.

### Validation

- Futaba GO and Senua RELEASE CLEAR on d3e9723. This entry records the release only; it does not claim the running service has been restarted or updated.

## [v0.1.2] - 2026-10-13

### Fixed

- Blocked Google Lens searches keep their place in the queue instead of losing it.
- Any publisher, and unnumbered books, can now be confirmed, under stricter title, creator and cover checks.
- Results are read after a solved Google check.
- The Google verification URL is no longer exposed.
- Lens verification timeouts are fixed, and there is no permanent "no result" state.
- Identity conflicts keep searching but block field writes, including during ComicVine outages.
- Dead ComicVine ids no longer pause lookups.
- The dashboard status filter works correctly.

### Added

- A one-time relabel script for mislabelled cover tasks. It is not run by this release.

### Validation

- Futaba GO and Senua RELEASE CLEAR on a73f43e. This entry records the release only; it does not claim the running service has been restarted or updated.

## [v0.1.1] - 2026-10-12

### Changed

- Serialize dashboard polling and serve bounded progress snapshots while preserving full stored history and its revision, so slow progress requests do not overlap.
- Acknowledge Google Lens verification requests promptly and retain explicit queued, opening, open, closing, failed and verified outcomes. Verification controls name Google Lens and explain blocked retries.
- Give Google Lens browser ownership an exclusive profile lease and a private Windows Job, with guarded release while owned descendants remain alive.

### Validation

- Frozen-candidate offline validation: 180 Python checks, 33 rendered DOM/UI checks and a real Windows Job ownership proof passed, with no owned processes remaining after each run.
- Real headed Google Lens opening remains unverified. The original native verification-window failure remains unattributed; this entry does not claim native launch success or a service deployment.

## [v0.1.0] - 2026-10-12

### Added

- Ordinary Yandex browser search as a fallback after DuckDuckGo and Bing, with a dedicated profile, cache and provider hold.
- User-requested Yandex human verification with duplicate-request protection, truthful waiting states and safe cancellation on pause or restart. Existing holds, the shared rolling request cap and minimum navigation spacing remain effective.
- A visible application version captured from `VERSION` once when the local server starts, so the display identifies the running build.

### Validation

- Offline validation: 119 Python checks and 17 rendered DOM/UI fixture checks passed with no skips. Normal live Yandex result markup, real challenge persistence and new verified comic writes remain unconfirmed.
- Deployment is pending; this entry records the implementation milestone and does not claim the running service has been updated. No release tag has been created.
