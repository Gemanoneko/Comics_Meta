# Verification button labels

Date: 2026-10-12. Owner: Judy. Baseline: `0f2df211f86a86618db235bbc8efeab71fe627ae`. Sully commits this exact spec before Ender implements it.
EXTEND only `static/index.html`'s existing Lens/Yandex verification button labels and tooltips, including static markup, polling, immediate click and error recovery; align the README's quoted Lens label.
Basis: NN/g recognition over recall and visibility of status; ProcessRules § Copy is short, specific, and has no memory. Each visible label names its engine; tooltip identifies cover search versus web search.

| Existing state | Google Lens label | Yandex label |
|---|---|---|
| Required / initial actionable | `Open Google Lens verification` | `Open Yandex verification` |
| Click submitted / queued / pending state not confirmed opening | `Google Lens verification queued` | `Yandex verification queued` |
| Confirmed opening | `Opening Google Lens verification…` | `Opening Yandex verification…` |
| Confirmed window open | `Google Lens window open` | `Yandex window open` |
| Failed request/session, retry currently actionable | `Retry Google Lens verification` | `Retry Yandex verification` |
| No challenge, verified, pause, ordinary provider wait | Preserve existing hidden/disabled rules; do not invent an action. | Preserve existing hidden/disabled rules. |

Open/Retry tooltip: `Open the dedicated Google Lens window for cover search verification.` / `Open the dedicated Yandex window for web search verification.`
Queued/Opening tooltip: `Google Lens verification has been requested. No further clicks are needed.` / `Yandex verification has been requested. No further clicks are needed.` Open-window tooltip: `Complete verification in the Google Lens window.` / `Complete verification in the Yandex window.`
If local status is unavailable, any retained label keeps its engine name; tooltip: `Google Lens status unavailable. Waiting for the local service.` / `Yandex status unavailable. Waiting for the local service.` Accessible name matches visible label; accessible description matches tooltip.
Preserve engine routing, distinct holds/profiles, pending duplicate prevention, pause/restart/window behavior and challenge safety. No new control/panel, layout/sizing/theme redesign, provider request, browser launch or unrelated copy change; state/API repair is independently authorized and owned by Ender. STOP and report if authoritative state cannot support truthful copy.
Acceptance: source-check every label assignment; offline fixture-check both engines' required, queued, opening, open, retry and unavailable labels/tooltips, including immediate click and recovery. At 320 and normal desktop CSS widths, measure visible button rects/text fit and same-plane overlap; evidence remains pending implementation. No disposable output created.

## Durable Lens outcome amendment — 2026-10-12

Use the existing Lens status paragraph for the current authoritative request outcome below; retain the label/tooltip table above. A submitted click immediately shows Queued with a disabled button. Ordinary cover progress, stale responses and general progress failures must not overwrite the current request's queued/opening/open/verified/failed outcome. Ender owns request identity, finite failure categories and independent status polling; no new surface or Yandex state rewrite.

| Confirmed Lens outcome | Exact existing-paragraph copy |
|---|---|
| Required, no active request | `Google Lens needs your verification. Other processing continues.` |
| Queued | `Google Lens verification queued. No further clicks needed.` |
| Opening | `Opening the Google Lens verification window.` |
| Open | `Complete Google Lens verification in the browser window.` |
| Verified, retained minimized window | `Google Lens verification complete. Keep its window open; it can stay minimized.` |
| Verified, retained open window | `Google Lens verification complete. You can minimize its window; keep it open for automatic cover searches.` |
| Failed before the window opened | `The Google Lens verification window could not open. Try again.` |
| Failed loading the page | `The Google Lens verification page could not load. Try again.` |
| Closed, timed out or other incomplete verification | `Google Lens verification did not finish. Try again when ready.` |
| Request interrupted by worker/service exit | `Google Lens verification was interrupted. Try again when ready.` |
| Independent Lens status unavailable | `Google Lens status unavailable. Waiting for the local service.` |

Failed outcomes persist until a new authoritative request/outcome or deliberate Pause; show `Retry Google Lens verification` only when that state is actionable. Use a stage-specific failure sentence only for a confirmed category; unknown failures use the incomplete-verification sentence. Never display raw exceptions, URLs, paths or internal stage names. Verified keeps the button hidden and the retained-session instruction; ordinary cover activity may coexist without replacing it. Pause retains its existing precedence and cannot claim verification success.
If independent status is unreachable, preserve the last engine-specific button face disabled, use the unavailable tooltip above and make no success/open claim. A failed general progress request alone cannot declare Lens unavailable. Offline acceptance adds sticky failed/queued outcomes under changing/slower progress, stale responses, confirmed success with open/minimized window, and independent status loss/recovery; no live or native test required for this copy contract.

Draft-review clarification — 2026-10-12: the aggregate `progress()` failure's existing queue-status paragraph says `Processing progress unavailable. Retrying.`; it must not say that the whole local service is unreachable when only aggregate progress failed. Existing `Status unavailable` progress-detail copy may remain.
An unactionable failed Lens Retry button must not use the queued/requested tooltip: if its window is not confirmed closed, use `Google Lens verification cannot restart until its window is confirmed closed.`; otherwise, if its owner is unavailable, use `Google Lens verification is unavailable. Waiting for its browser to become ready.`; any other unactionable failure uses `Google Lens verification cannot restart yet.` Mirror the chosen tooltip in its accessible description. Only a failed independent status fetch uses the local-service-unavailable tooltip.
Confirmed `closing` means the interrupted owned window/context is closing and cannot queue reopening: use disabled button `Closing Google Lens verification…`, status `Closing the Google Lens verification window.`, and tooltip/accessible description `Waiting for the Google Lens verification window to close.` Ender confirmed this state contract on 2026-10-12; it must not reuse Queued copy.
