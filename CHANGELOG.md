# Changelog

## [Unreleased]

### Changed

- In progress for `0.1.1`: serialize dashboard polling and bound progress-response history while preserving stored history, so slow progress requests do not overlap.
- In progress: acknowledge Google Lens verification requests promptly with durable request states, and name Google Lens explicitly in verification labels.
- Implementation, QA and deployment are pending. The specific native cause of the reported verification-window failure remains unproven; this entry does not claim the issue is fixed or the running service updated.

## [v0.1.0] - 2026-10-12

### Added

- Ordinary Yandex browser search as a fallback after DuckDuckGo and Bing, with a dedicated profile, cache and provider hold.
- User-requested Yandex human verification with duplicate-request protection, truthful waiting states and safe cancellation on pause or restart. Existing holds, the shared rolling request cap and minimum navigation spacing remain effective.
- A visible application version captured from `VERSION` once when the local server starts, so the display identifies the running build.

### Validation

- Offline validation: 119 Python checks and 17 rendered DOM/UI fixture checks passed with no skips. Normal live Yandex result markup, real challenge persistence and new verified comic writes remain unconfirmed.
- Deployment is pending; this entry records the implementation milestone and does not claim the running service has been updated. No release tag has been created.
