# Yandex web search — verification UX

Date: 2026-10-12. Owner: Judy. Status: reviewable draft; Sully must commit this exact file before Ender is briefed to implement from it.

This is an EXTEND of the existing Google Lens human-verification interaction. Add ordinary Yandex whole-web search and its human-verification action; preserve the Lens cover-search flow and every unrelated control. Sergei authorized human verification “same as Lens.” Ender owns the implementation and worker architecture.

## Placement and controls

Keep the current Live enrichment progress panel. Immediately after its existing Lens status/action pair, add one Yandex status paragraph and one conditional Yandex action button, before Previous write batches. No new panel, dialog, engine selector, settings surface, popup notification or redesign.

- Status always begins `Yandex web search:`. Show it when the backend supplies a recognized Yandex state; an older backend without Yandex supplies no row.
- The existing Lens action remains routed only to `/api/browser-resume`. Do not reuse that endpoint or its `browser-resume` marker for Yandex. Keep the Lens status/action pair intact; the Yandex button names its engine in every state.
- Yandex button: existing Segoe UI/system font, 10px vertical/14px horizontal padding, minimum height 40 CSS px and minimum target 24×24 CSS px, natural width limited to its container. Text can wrap. Status sits above the action with an 8px gap; do not place the two engines' controls over or inside each other.
- Use existing dark panel/text colors. The Yandex button uses `#385ea1` with `#eef2fb` text for normal and hover backgrounds; hover adds an inset 1px `#bcd8f9` outline. Focus-visible uses a 2px `#bcd8f9` outline with a 2px offset. Scope these styles to the new control. Do not inherit the current lighter `#4776c6` hover background.
- The dashboard currently declares `color-scheme: dark`; retain that behavior under either Windows theme. This request does not add a light theme.

## States and exact copy

The backend supplies authoritative engine-specific state. The UI never treats a cleared challenge as proof of a usable search result, verified comic, or completed metadata write.

| State | Text after `Yandex web search:` | Button / behavior |
|---|---|---|
| Ready / idle | `Ready.` | Hidden. |
| Normal search in flight | `Searching.` | Hidden. |
| Human verification required | `Yandex needs your verification. Other processing continues.` | `Open Yandex verification`, enabled. |
| Click submitted / queued | `Verification queued. No further clicks needed.` | `Yandex verification queued`, disabled immediately, before awaiting the response. |
| Queued behind a current operation | `Verification queued until the current operation finishes.` | Same queued button, disabled. |
| Queued behind known pacing/budget deadline | `Verification queued until {local date/time}.` | Same queued button, disabled. Use a date as well as time when the deadline is not today. |
| Opening | `Opening the Yandex verification window.` | `Opening Yandex verification…`, disabled. |
| Window open / verifying | `Complete Yandex verification in the browser window.` | `Yandex window open`, disabled. |
| Verified, retained minimized window | `Verification complete. Keep the Yandex window open; it can stay minimized.` | Hidden. Show this copy only if the backend confirms that the retained verified session requires an open window. |
| Verified, session safely closed | `Verification complete. Automatic searches will continue.` | Hidden. Do not tell the user to keep a window open when none is retained. |
| Shared pacing wait after verification | `Verification complete. Next search after {local date/time}.` | Hidden. |
| Shared budget wait | `Web search budget reached. Next search after {local date/time}.` | Hidden unless a previously submitted verification is still queued, in which case show the queued state. |
| Verification failed / timed out / user closed the window before completion | `Yandex verification did not finish. Open a new window when ready.` | `Retry Yandex verification`, enabled while a genuine challenge is still pending. |
| Could not open the window | `The Yandex verification window could not open. Try again.` | `Retry Yandex verification`, enabled when the request is no longer pending. |
| Ordinary search failure / cooldown | `Yandex search unavailable. Retry after {local date/time}.` | Hidden. An unavailable browser or missing result cards must not be mislabeled human verification. |
| Global pause requested | `Pausing; closing the Yandex window safely.` | Hidden. |
| Globally paused | `Paused. Resume processing to continue.` | Hidden. |
| Local status unavailable | `Status unavailable. Waiting for the local service.` | Disable any visible action; do not launch from a stale state. |

Do not show technical exception text, challenge URLs, queries, local paths, profile paths, credentials, or raw internal state names in these strings. A verified state is shown once through the ordinary status paragraph, then yields to the next truthful engine state.

## User action and interruption rules

1. A genuine Yandex challenge stops that engine's automatic requests and exposes its action. Other available sources continue under their own gates. A Yandex challenge must not replace the Google Lens request or clear another provider's hold.
2. One click requests one Yandex verification session. The response acknowledges queued or already requested; repeated clicks, repeated polling, or a second tab must not create duplicate windows. Queuing wakes an idle owner and waits for safe ownership/current operation as needed. The UI must not promise that a window is already open while it is queued.
3. Only this explicit user click permits a visible verification window. Detecting a challenge, refreshing the dashboard, reopening the service, completing verification, or resuming processing must not open or foreground a window. An agent/test must not activate this action on the real desktop without the separately required away-window authorization.
4. The user completes the challenge in the dedicated Yandex session. The app observes completion; it never solves the challenge, spoofs fingerprints, transfers cookies from another browser, or attaches to Sergei's real browser, Lens profile, DDG profile or Bing profile.
5. On confirmed success, the Yandex human-verification hold alone may clear. Preserve its successful session in the way Ender can safely support: retain/minimize the owned window as Lens does, or close it after persisting the same dedicated profile if session continuity is demonstrably supported. Report the actual lifecycle in the state; no reopen/focus on success. All ordinary search, evidence and write verification still applies.
6. Global Pause takes precedence over queued/opening/verifying. Cancel the unconsumed open request and close the owned Yandex window/context safely before acknowledging Paused. Keep the challenge, research queue and saved session data. Resume does not replay an old visible-window request; if verification is still needed, show a fresh action.
7. Service/worker restart similarly does not replay a saved visible-window request. A dead owner cannot leave `opening` or `open` indefinitely: reconcile to required/retry while retaining the challenge. A successful session retained in its dedicated profile remains eligible for ordinary background searches.
8. Keep all DDG/Bing/Yandex app-initiated real provider attempts behind the existing combined 300-per-rolling-24-hour ceiling and at least 120-second spacing, including app-initiated verification navigation. Queue transparently when that gate delays opening. Completion must not erase ledger history, shorten a longer hold, grant an immediate extra search, or turn manual challenge observation into repeated app requests. Preserve lower configured limits and longer configured spacing.

## Notification, tooltip and keyboard behavior

Use only the persistent status paragraph, with `role="status"`/`aria-live="polite"` and atomic reading. Write/announce it only when the displayed state or meaningful deadline changes; the existing two-second poll must not repeat the same announcement. No sound, repeating toast, badge counter, alert dialog, or automatic browser focus. Both Lens and Yandex requests can remain visible simultaneously in separate rows.

The enabled Open/Retry button ships with this tooltip in its creating commit: `Open the dedicated Yandex window to complete its verification.` The queued/opening tooltip is `Yandex verification has been requested. No further clicks are needed.` The open-window tooltip is `Complete verification in the Yandex window.` Provide the purpose through `aria-describedby` as well as pointer tooltip; the accessible name matches the full engine-specific button label.

Use a native button in normal tab order. Enter/Space activates it; disabled states cannot submit. Do not add a global accelerator or move keyboard focus on polling. If a focused action disappears on verification success, retain a sensible nearby focus target; do not jump to the page top. Any displayed tooltip must not obstruct another control or be the sole source of required information.

## Ender's consumer checklist

These are the current literal consumer paths found by `rg` over the tool's Python, HTML and JavaScript files. Ender must grep the final endpoint/state/engine literals again and report every producer and consumer after implementation; technical module choices remain his.

| Existing boundary / file | Yandex responsibility |
|---|---|
| `static/index.html` — `progress()`, `showProviders()`, `browserResume.onclick` | Consume `p.providers.free_web.engines.yandex` or the equivalent explicit Yandex status Ender chooses; render the separate status/action. Read pause from `p.control`. Keep the existing Lens click contract intact. Do not duplicate the Yandex request message in the flattened provider line. |
| `app.py` — `/api/progress`, POST dispatch, pause guard | Expose engine-specific state and a separately routed Yandex request that rejects paused/stale/no-challenge attempts and is idempotent. The UI request must carry explicit `yandex` identity; never accept an arbitrary URL/profile from the browser client. |
| `providers.py` — `statuses()` → `web_search.free_status()` | Carry Yandex under the free-web engine dictionary while preserving aggregate availability when another engine remains usable. |
| `web_search.py` — `FREE_ENGINES`, `cached()`, `free_state_id()`, `free_engine_status()`, `free_status()`, `search()` | Give Yandex distinct cache and persisted hold identity; preserve the shared ledger, normal scheduling and Yandex-specific human-verification signal. A hold must not alias a legacy DDG/Bing/paid-vendor row. |
| `free_search_browser.py` — `ENGINES`, `search()`, profile ownership/closure | Ordinary Yandex result rendering, challenge observation and the dedicated verification lifecycle. Distinct Yandex profile/session/request state; retain ownership safeguards and fail closed if ownership/closure cannot be established. |
| `worker.py` — owner registration, idle/pause lifecycle | Consume the pending user request on the owning worker safely, acknowledge opening/open/verified/failed, reconcile dead requests, and close the Yandex context before pause acknowledgement. No new process architecture is prescribed here. |
| `research.py` — `general_lookup()`; `source_scheduling.py` — `attempt_status()`, `record()` | Preserve explicit Yandex engine tags and ordinary comic retry behavior; the current scheduling whitelist names DDG/Bing and must account for Yandex. Search matches remain leads only. |
| `browser_search.py`, `browser_worker.py`, `pause_control.py` | Existing Lens state fields and cooperative pause are reference contracts. Do not redirect or reuse Lens markers/holds/profile for Yandex, or change Google Books/GetComics holds. |
| `README.md`, `SOURCE_CONNECTORS.md`, browser/free-search/source-scheduling tests | Document the actual Yandex action/session lifecycle and offline limitations; preserve the frozen Bing guard work. Add focused checks for routing, duplicates, pause, stale owner, real challenge vs ordinary error, and shared gates. |

Minimum UX-facing fields: explicit engine identity, genuine `human_verification` flag, lifecycle (`required`, `queued`, `opening`, `open`, `verified`, `failed`), `verification_pending`, actual window lifecycle (`closed`, `open`, `minimized`), authoritative availability/deadline, and safe plain-language failure category. Equivalent field names are acceptable if Ender reports the final contract and all consumers.

## Acceptance and evidence limits

- Offline/mock cases cover both engines challenged together; only Yandex challenged; no challenge; duplicate requests; queued behind work/pacing/cap; opening; open; success with each supported window lifecycle; timeout; close; launch failure; pause in every pending state; resume; restart/dead owner; unavailable local service. No live provider or native desktop launch is required for this spec.
- Futaba measures `getBoundingClientRect()` for all visible status/action pairs, controls and tooltips in those mock states at 320 CSS px width and the normal desktop viewport, including an open Comic details dialog and 200% zoom/text spacing. Report the viewport, target rects, focus rects and any same-plane intersections. The minimum target is 24×24 CSS px; controls must remain reachable, nonoverlapping and readable.
- Contrast measured from sRGB relative luminance `(lighter + 0.05)/(darker + 0.05)`: existing status `#aab4c6` on panel `#1b202b` = **7.80:1**; proposed button `#eef2fb` on `#385ea1` = **5.70:1**; focus outline `#bcd8f9` on panel = **11.12:1**. Existing generic hover `#eef2fb` on `#4776c6` = **4.01:1**, hence the isolated Yandex hover treatment above. No rendered hit rects or native focus behavior have yet been measured; this draft is not a QA verdict.

Framework basis: [studio desktop-utility UX reference](../../../Team/Research/UX_AppBestPractices.md): NN/g visibility/status, control/freedom and error recovery; Hick's Law (one direct engine action); Fitts's Law (existing comfortable target); WCAG 2.2 AA text contrast, target size, focus and keyboard operability. Process pointers: [ProcessRules](../../../Team/Docs/ProcessRules.md) § Copy is short, specific, and has no memory; § A new control is born with its tooltip; § No UI element may cover another; § Our tooling must not intrude on Sergei's machine.

Scope exclusions: no UI code in this draft; no git/release/lifecycle operations, provider requests or browser launches; no unrelated UI changes, hooks, studio infrastructure, sibling tools, frozen Bing files, archive behavior, metadata policy, paid search, Google Books/GetComics/Lens hold changes, quota reset, bypass or cookie transfer. If implementing this interaction requires a wider feature/product decision or cannot preserve safe browser ownership and truthful status, STOP and report to Jane.

Disk hygiene: no probe/export/log/cache output was created. Preserve this spec as active reviewable source.
