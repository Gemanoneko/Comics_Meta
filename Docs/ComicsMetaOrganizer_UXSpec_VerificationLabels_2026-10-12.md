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
Preserve engine routing, distinct holds/profiles, pending duplicate prevention, pause/restart/window behavior and challenge safety. No new control/panel/state/API, layout/sizing/theme redesign, provider request, browser launch or unrelated copy change; STOP and report if the existing state cannot support truthful copy.
Acceptance: source-check every label assignment; offline fixture-check both engines' required, queued, opening, open, retry and unavailable labels/tooltips, including immediate click and recovery. At 320 and normal desktop CSS widths, measure visible button rects/text fit and same-plane overlap; evidence remains pending implementation. No disposable output created.
