# App version display

Date: 2026-10-12. Owner: Judy. Status: reviewable draft; Sully commits this exact document before Ender implements from it.

This is an EXTEND of the Comics header using Books Arranger's existing header version-badge pattern. Sergei requested an app version “like in Book Arranger.” Add one read-only label; preserve the title, subtitle, Pause/Resume control, control status and Yandex verification spec.

## Display

- Place the badge in the existing right-hand header group, immediately above Pause/Resume, right aligned with that button and separated from it by 8 CSS px. It stays in normal document flow.
- Reuse Comics' existing `.badge` colors/padding/radius: text `#bcd8f9`, background `#24364c`, padding 8px 14px. Use its system font at 14px, normal weight, 1.5 line height and default cursor. It is selectable text, with no button role, click action, hover animation or tab stop.
- At narrow widths, let the header wrap with a 16px gap: title/subtitle first, then the existing control group with the badge above it. Left align that group on the wrapped row. Long badge text wraps inside the available width. Nothing overlaps, hides, or reduces the Pause target.
- Valid version text: `v{version}`, for example `v0.1.0`. Do not add a second `v` if the authoritative field already includes one. Do not append build hashes, “latest,” upgrade advice or extra release-stage copy.
- Initial text: `Version loading…`. Missing/empty/invalid field, older backend, or initial request failure: `Version unavailable`. A later failed state request changes the label to `Version unavailable`; keep the last value only in frontend memory if needed. A successful later response restores its reported version. No alert/toast or special retry action.

Tooltip: `Version reported by the running local server.` Supply the accessible description as well as the pointer tooltip; required meaning is visible in the label itself. Accessible name for a valid label: `App version {version}`. Treat it as ordinary text, without a live region. Update text only when the displayed value changes; polling must not announce it repeatedly or move focus.

## Technical boundary agreed with Ender

Sully owns the tracked `VERSION` and initial version assignment. Ender captures it once at server process startup and exposes it as `/api/state` → `version: string`. `static/index.html`'s existing `state()` consumes only that field. A server still running the old build reports its own captured version after the disk source changes. Do not read current Git/disk version in the UI or on each status request, and do not infer a new version from HTML, a tag or this document. This display does not restart the server.

The Books reference is read-only: `web/index.html` has the header badge, `web/app.js` renders `state.version`, and `web_server.py` captures `loaded_version` once and returns it through health/state. No Books files change. Ender greps the final `VERSION`, `version` response field and badge ID, reporting every producer/consumer; no other endpoint needs a version field for this feature.

## Acceptance

Offline/mock checks: valid version, optional leading `v`, unavailable/missing/invalid field, initial failure, successful response followed by failure/recovery, and unchanged repeated polling. Startup-capture check proves changing `VERSION` on disk cannot relabel the existing server.

Measure badge/title/Pause/control-status `getBoundingClientRect()` at normal desktop width and 320 CSS px, including 200% zoom, long fallback copy, both Pause labels and an open Comic details dialog. Report viewport and measured rects; no same-plane overlap or obscured focus. Badge text/background contrast is **8.39:1**, measured with the sRGB relative-luminance formula; existing dark theme remains in use on either Windows theme. No real browser/provider/native launch is required. Rendered rects remain pending implementation.

Basis: [studio utility UX reference](../../../Team/Research/UX_AppBestPractices.md), NN/g visibility of status, consistency and minimalism, WCAG 2.2 AA contrast/reflow; [ProcessRules](../../../Team/Docs/ProcessRules.md) § No UI element may cover another and § Copy is short, specific, and has no memory.

Exclusions: UI code, git/version/lifecycle operations, Books edits, Yandex-spec amendments, source/provider/metadata changes, settings, About dialog, update checks and unrelated UI. STOP and report if the backend cannot identify the running build truthfully. No disposable output was created.
