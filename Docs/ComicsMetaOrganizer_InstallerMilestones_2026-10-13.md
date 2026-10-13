# Standalone installer milestones — 2026-10-13

Status: development plan for the isolated M1 worktree; no installer or live-state migration has been performed. Base requirement: extend released v0.1.4 while preserving metadata identity, provenance, write guards, recovery backups, pause behavior, and failure filters.

## Required first installer release

Sergei explicitly requires: “Make sure that the build can check for updates and install them (like QuickLauncher).” Checking, manual download, verified installation, and relaunch are required for the first standalone installer release. An executable with check-only updates is not a substitute. Existing approved DesktopShell §4/4a already specifies this flow; Judy confirmed it on2026-10-13. No new controls or UX decisions are introduced by this requirement.

## Milestones

1. M1: integrate the existing state-split branch with released v0.1.4 without rewriting history; validate that all runtime state/config/secrets remain under the selected state root, global library overlap locks prevent another state root from writing, and transient quit never persists a shell pause as a user pause. Use complete isolated unittest discovery, including the fail-closed suite-wide state guard.
2. M2: add the approved Electron window/tray shell, single-instance and owned-service lifecycle, lightweight state polling, genuine graceful quit/GPU release/cancel, approved dashboard tooltips, icon production and Judy crop review. No startup trigger. Any missing fresh-install config UX goes back to Iris/Sergei rather than inventing a wizard.
3. M3: package the unchanged Python service with embedded CPython, exact wheel dependencies, and bundled7-Zip in a Windows installer. Installed resources must be read-only; all mutable state belongs outside the install folder. Verify subprocesses, Playwright/installedEdge and conversion paths in an isolated profile/port/library.
4. M4: implement and verify update check→manual download→verified Ready→user confirmation→temporary shell pause→Paused/GPU release or error→owned engine stop→installer→relaunch. Preserve the prior user pause and recovery data; never replace a running service, auto-download, or install on quit. Include actual packaged installer and update-path QA; Sully handles release/versioning and keep-last4 heavy releases.
5. M5: migrate real state to %LOCALAPPDATA%\ComicsMeta only in a window Sergei chooses. No live data move is authorized by installer preparation.

## Technical baseline and gaps

Existing M1 supplies app_paths.py state selection, file_lock.py/library_lock.py claims, transient quit generations and worker leases, pinned requirements, and test_0_state_isolation.py/test_zz_state_isolation.py. No Electron package, shell, embedded runtime, updater, or installer currently exists.

After release integration, pipeline_config.py currently reads app.BASE/config.json and must join the state-root boundary; test_suite_isolation.py assumes DATA follows BASE and must reflect selected STATE_ROOT while preserving its cleanup assertion. Verify new release modules and every plan path with the same boundary, not a regex-only claim.

M1 request_stop is transient and safe but does not implement the shell’s cancelable pause/GPU-release sequence: pause_control.status/checkpoint derive acknowledgement and GPU unload from the durable pause row. M2 must add a separately owned temporary shell-pause mechanism before irreversible stop while retaining an existing user pause.

archive_conversion.py currently names installed C:/Program Files/7-Zip/7z.exe; M3 must support the pinned bundled resource. Runtime/installer versions and download provenance will be selected against primary official sources during that milestone.

QuickLaunch src/main/updater.js is a read-only implementation reference for electron-updater manual download/install events and flags. Do not copy its immediate quitAndInstall route: Comic Metadata must finish the approved pause, GPU and owned-service safety flow first. Raw updater errors stay in logs, not the UI.

## Verification and exclusions

Long tests/builds have one600000ms total deadline and reviewed owned-descendant closure; no duplicate or silent background runs. Use isolated state, locks, temp, app profile, fixtures and non-live port, with notifications/audio/focus disabled. No real comic/library writes or signed-in browser access.

Ender implements, Judy confirms any changed controls, Futaba tests, Senua reviews, and Sully owns all git/version/release operations. No changes to the live WIP/Comics Meta Organizer code/data/service/task/port8765, hook repair, QuickLaunch source, unrelated tools, or original real library.
