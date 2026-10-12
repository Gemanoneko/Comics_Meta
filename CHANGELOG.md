# Changelog

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
