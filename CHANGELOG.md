# Changelog

## [v0.4.1] - 2026-10-26

### Added

- "This month" period in update statistics.

### Changed

- The update banner no longer offers Install again while it pauses and installs. It shows a waiting message, and Pause & release GPU is locked during the wait.

### Fixed

- Update statistics never miss a write that happens while counting, and long periods load faster.

## [v0.4.0] - 2026-10-26

### Added

- Update statistics panel above the Live library.
- Relabeled "Updated by this app" to "Currently tagged by this app", and the row label "Updated by this tool" to "Tagged by this app".

## [v0.3.0] - 2026-10-18

### Changed

- Prioritize comics with fresh evidence or sources ready to retry, avoiding repeated checks while providers are waiting.
- Research comics with bounded parallel lookahead while retaining provider pacing, daily limits, pause handling and serialized metadata writes.
- Preserve metadata verification, archive-change guards and recovery-backup safety checks.

### Validation

- Independent focused correctness checks: 94 passed, with no errors or skips; source review RELEASE CLEAR.
- Source-only candidate checkpoint. Full discovery remains limited by native-launch refusals; packaged installation/update and formal handoff certification are pending. No installer release or live deployment.

## [v0.2.1] - 2026-10-14

### Fixed

- Source checkpoint fixes F40 setup/library ownership handling and strengthens update helper capsules, module paths and staged manifest validation.

### Validation

- F40 independently rechecked: 77 checks passed. Capsule18 passed 18 Python and 19 Node checks plus all source parsing; complete 234-input identities remained unchanged, with native/root/descendant exit zero.
- Actual offline lock regeneration changed only the two version fields; all 290 dependency records stayed unchanged.
- This is a source-only patch checkpoint. Native shell/rendered UI, actual packaged install/update transition, final QA and release review remain pending. No installer release, tag, live deployment or migration.

## [v0.2.0] - 2026-10-14

### Added

- Source checkpoint for the standalone Windows shell, embedded Python/7-Zip runtime, in-app library/API-key setup, and manual verified update installation and restart.
- Per-comic identity and dead-link recovery actions with preview, explicit confirmation, guarded writes and retained recovery evidence.

### Changed

- Isolated application state and library ownership, cooperative quit and updater launch outcomes preserve user pause and distinguish uncertain installation results.

### Validation

- Development offline09 passed 736 Python and 23 Node checks plus source parsing; 52 native/DOM checks are explicitly deferred. Two subsequent raw-regex literal changes are qualified as equivalent. Isolated embedded-runtime and RAR fixture checks passed.
- This is an unfinished source/version milestone, not a tagged release or installer readiness verdict. Native shell and rendered UI, packaged installer, actual prior-to-new update transition, independent QA and final code review remain pending. No live deployment or state migration occurred.

## [v0.1.4] - 2026-10-13

### Added

- Publisher writes require agreement between cover and credits readings; Imprint uses an explicit parent map with date-aware WildStorm and Archaia ownership.
- Filename issue numbers may fill unread cover numbers when the cover title agrees.
- A per-field write ledger permits verified external values to replace the tool's own in-book values while preserving human edits, letter case and punctuation-only Series differences.
- Failure filters show counts, reasons, Details and a one-attempt Try again action, with a missing-key message.

### Changed

- Google Lens resumes five minutes after a solved check and backs off 10/20/40/60 minutes after repeated challenges.
- Failure counts use a revision-aware cache; credits readings have length and time limits.
- Narrow action buttons stack; Details has clear error spacing; retry copy reports cumulative attempts without a misleading limit.

### Fixed

- Series spelling preserves meaningful trailing punctuation and requires corroborated accent changes.
- Fractional filename numbers retain their leading zero; a one-time idempotent catalog refresh repairs affected rows.
- Publisher aliases retain canonical names, and imprint writes respect existing publisher and date evidence.
- The credits pilot compares imprint parents; the worker accepts library_root without a root key.

### Removed

- Public pilot JSONL files containing library paths from the current branch; earlier public history remains unchanged.

### Validation

- Futaba GO and Senua RELEASE CLEAR on 319202243fe7296f985c318a7b08cb5a0f05d140. Independent sender and receiver each passed 682 tests; the 47 DOM checks skipped there passed in the separate 67-check QA run, with repeated manual retries also checked. The release commit changes documentation only. Live deployment remains pending approval; the running service is still v0.1.3.

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
