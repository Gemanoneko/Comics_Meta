# Comic Metadata — API keys entry, always reachable

Date: 2026-10-16. Owner: Judy. Status: reviewable; Sully commits this file before Ender implements. Fixes installed-QA M2 (`ComicsMetaOrganizer_QA_Installed_v0.2.1_2026-10-16.md`): after first-run setup there is no way to add a key unless a comic is already "Held for ComicVine".

Classification: EXTEND. One new header button, one new mode of the existing Details dialog, two copy fixes. The keys editor itself is not redesigned: fields, labels, help, Show/Hide, Save keys, validation, success and failure copy stay exactly as in `PerComicRecovery_2026-10-14` §4a. No code, git or app launch was part of writing this. Widths below are computed from the CSS in `static/index.html` and `static/shell-ui.js`, not measured on a rendering.

## 1. Decision

| Item | Spec |
|---|---|
| Placement | Dashboard header, in the version row (the group `Check for updates` already sits in), inserted between the version badge and `Check for updates`. Shell only: not rendered when `window.comicDesktop` is absent (same rule as `Check for updates`). Not on the setup, startup or failure pages. |
| Label | `API keys` (the word the Details button and the held-comic copy already use, so one word means one thing). No ellipsis, no icon, no badge or dot for "key missing" (the dashboard notice already says it; no colour-only signal). |
| Tooltip (native `title`, also the accessible description) | `Add or replace the API keys used to look up comic information.` |
| Look | Same secondary style as `Check for updates`: 32 px high, padding 4×12, 14 px text, radius 8, `#242c3b` fill, `#eef2fb` text (12.50:1), 1 px `#aab4c6` border (8.74:1 on `#12151c`), hover inset 1 px `#bcd8f9`, focus-visible 2 px `#bcd8f9` with 2 px offset (figures from DesktopShell §4a). Pause stays the only blue primary. Label never changes, so the button width is fixed (about 82 px; Ender measures). |
| Keyboard | Native `<button>`: Tab, Enter or Space opens it. Tab order is visual order: `API keys`, `Check for updates`, `Pause & release GPU` (Pause is now two Tabs from the badge row; accepted for rarely used controls). No new global or window shortcut (set once, so an accelerator does not pay off). |
| Not added | Tray menu (stays at three items, DesktopShell §2: "No Settings"). Alt-menu item (hidden by default, so it cannot be the fix; the header button is the one visible route). |

```
Wide (right-aligned group, as today):
  Comic Metadata                      [ v0.2.1 ] [ API keys ] [ Check for updates ]
  Your collection, ...                                  [ Pause & release GPU ]
                                                                  status line
Narrow (left-aligned, wraps by width only):
  [ v0.2.1 ] [ API keys ]
  [ Check for updates ]
  [ Pause & release GPU ]
```

`Check for updates` keeps its right-edge position at wide widths (the new button goes to its left), so no existing hit area moves there.

## 2. Control states

| State | Look | Tooltip |
|---|---|---|
| Idle | Enabled | as §1 |
| Opening (reading which keys are saved) | `aria-busy`, further clicks ignored | `Opening API keys…` |
| Local service not running (starting, restarting, failed; the keys call needs the service) | Disabled, 50% opacity (existing) | `Unavailable while the local service is not running.` |
| Quitting or installing | Disabled, same as `Check for updates` | `Unavailable while updating or quitting.` |
| Dialog open | Behind the modal, not reachable (existing sanctioned class: modal, dismissible) | n/a |

Pause, resume and user-pause state do not affect this control; saving keys never starts or resumes processing (PerComicRecovery §4a).

## 3. What it opens

The existing Details dialog in a keys-only mode. Nothing else about it changes.

- Title (h2): `API keys`. Hidden: problem block, cover, path, manual lookup and every comic action. Shown: the §4a editor as it is today, with its intro `Add or replace keys for existing sources. Saving keys does not start processing or enable a source.`
- No duplicate heading: the h2 is the heading and receives the post-save focus (`tabindex="-1"`); the editor's own h3 is not drawn in this mode.
- Initial focus: ComicVine input. Order, Enter-to-save, Escape, per-field Show/Hide and remask rules: unchanged (§4a).
- Buttons: `Save keys` (unchanged tooltip). `Cancel`, tooltip `Discard unsaved key entries and close.` `Back to comic` is omitted (there is no comic). The dialog's top `Close` takes the same tooltip in this mode.
- Close, Cancel or Escape (not while saving): drafts cleared, dialog closes, focus returns to the header `API keys` button. If the button became disabled meanwhile, focus goes to `#pauseControl`.
- Reading saved-key status fails: the dialog opens with the intro and one alert line, `Could not read saved-key status. Close this and try again.`, no fields.
- Success and failure copy: unchanged (`Keys saved. Source settings and processing state are unchanged.` / `Could not save keys. Check access to the app's data folder, then try again.`).
- The dialog title returns to `Comic details` whenever a comic's Details opens. The held-comic `API keys` button in Details stays; both routes open the same editor.

## 4. Copy fixes

| Where | Now | New |
|---|---|---|
| Dashboard `MISSING_KEY` in the app (used by the page notice and the per-comic held status) | `Open API keys in the desktop app to add a ComicVine key.` | `Open API keys at the top of the page to add one.` |
| Same string in a plain browser (control absent) | same | `Open API keys in the Comic Metadata desktop app to add one.` |
| First-run setup, collapsed help under Optional API keys (FirstRunSetup, Layout item 2) | `You can leave these empty. Adding keys does not switch on paid search.` | `Skip them now and add them later with API keys on the dashboard. Adding keys does not switch on paid search.` |

Resulting sentences: `No ComicVine key is set, so comics with a ComicVine link wait. Open API keys at the top of the page to add one.` and `No ComicVine key is set, so writes wait. Open API keys at the top of the page to add one.` The setup line closes the skip-the-key trap at the point where the key is skipped. `Check your key in API keys.` (rejected key) and `No ComicVine key is saved.` need no change.

## 5. Layout, 320–1280 px

- The version row already wraps (`flex-wrap`, 8 px gap). Group width, estimated: badge about 78 + 8 + API keys about 82 + 8 + Check 156 = about 332 px (a `Version unavailable` badge is about 170 px; it still shares line 1 with `API keys` at 320 px). It was about 242 px.
- 320 CSS px (640 px window at 200% zoom; content 290 after 15 px padding): line 1 `v0.2.1` + `API keys`, line 2 `Check for updates`. Below about 362 px viewport the row is two lines, so Pause sits one row (about 40 px) lower. That move depends on width only, never on state.
- Wrap point: title block (about 330 px) + 16 + group 332 + 64 padding is about 742 px. Between 701 and about 742 px the header would wrap with the group half-aligned. So the existing narrow rules (header controls full width and left-aligned; version row left-aligned) apply up to 760 px instead of 700; Ender measures the real wrap point and uses the larger of it and 760 so no width shows a half-aligned stack.
- No overlap on any plane: all four header items are in flow; focus ring (2 + 2 px) is smaller than the 8 px gap; the only overlay is the existing modal dialog. The sticky `#error` behaviour is unchanged (DesktopShell §6).

## 6. Checked against the existing specs

| Spec | Result |
|---|---|
| DesktopShell | Tray stays at three items; Alt menu untouched; Ctrl+Q still works with the dialog open; §4a version row now holds three items (the "fixed by the badge" reason still holds per state; width-driven wrap added above); F2 tooltip rule met. |
| FirstRunSetup | Fields and rules reused as they are; one help sentence amended (§4). Setup itself is not re-run. |
| PerComicRecovery §4a | Editor reused. Two deltas: reachable with no comic open; `Back to comic` omitted in that mode. The Details route and its tooltip are unchanged. |

## 7. Futaba checks (isolated harness only, no live profile, no provider calls)

Per width 320, 362, 640, 700, 701, 742, 760, 1280 at 100% and 200%: measured rects of badge, `API keys`, `Check for updates`, `Pause & release GPU` are pairwise disjoint; no sideways scroll; centre-point hit test returns each button; focus ring not clipped; Pause and the other header items do not move across every `Check for updates` state and every `API keys` state. Keyboard: Tab order, Enter and Space open, initial focus on ComicVine, Escape and Cancel return focus to the header button, double-click opens one dialog. Absent in a plain browser; disabled with the service stopped; copy strings above read from the page, both app and browser variants. Editor confidentiality, blank-preserves-key, multiline rejection and no-restart behaviour: PerComicRecovery §4a acceptance, not repeated.

## 8. Notes for Ender

- The editor's staleness guard is bound to the open comic row; in this mode bind it to the dialog's open epoch.
- Map the keys call's "unavailable" failure to the disabled state, not an error toast.
- The notice clears on the next normal status refresh after a ComicVine key is saved. If the engine cannot reload keys without a restart, report that before implementing (PerComicRecovery §4a), do not restart silently.
- Ships with its tooltip in the creating commit (ProcessRules § A new control is born with its tooltip).

## 9. Question for Sergei

1. A saved key can be replaced but never removed (nothing offers it, per the earlier approved spec). With this always-reachable button that gap is easier to notice. Add a remove-key action, or leave replace-only? Default if no answer: leave replace-only.

Basis: Jakob (version/update/settings cluster in one app-level spot; same label for the same action), Fitts (existing control keeps its edge position), Hick (no tray or menu growth), NN/g visibility of system status and recovery from errors (the notice names a control that exists), WCAG 2.2 AA (2.5.8 target size, 2.4.11 focus not obscured, 1.4.10 reflow, 1.4.1 no colour-only signal).
