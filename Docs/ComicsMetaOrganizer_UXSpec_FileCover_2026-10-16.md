# Cover in this file — compare covers side by side

Date: 2026-10-16. Owner: Judy. Target: 0.2.3. Status: reviewable; Sully commits before Ender is briefed. EXTEND PerComicRecovery_2026-10-14 §2 and §3; nothing else in that spec changes. Presentation only: no backend change is required (see Notes for Ender).

Request (Sergei, on installed 0.2.2): on **Review this issue**, show the cover from the comic's own archive next to the ComicVine cover, so he can compare the two.

Basis: NN/g visibility and recognition over recall; Gestalt proximity (things compared must sit together); WCAG 2.2 AA; existing dark dialog palette. Sizes below are calculated from the CSS, not measured. The app was not run (Futaba measures, see §7).

## 1. Specced vs implemented

| Spec | Says | Code today (static/comic-recovery.js, index.html, reverse-image.js) |
|---|---|---|
| §2 table, **In this file** card | Local cover labelled "Cover in this file" | Not implemented. The card has Series, Issue, Year, Web link only (comic-recovery.js line 26). |
| §3 dead-link Details | "file identity/year/cover" | Identity and year yes. Cover only through the older `#localCover` block at the bottom of the dialog (index.html line 15): alt text only, no visible label, below the whole recovery section and the actions. |
| §1 | "current local cover (existing)" before the action options | Same older block, so it comes after the actions. Order differs from the spec. Not changed here (see §8). |
| §2 **ComicVine cover** | Labelled "ComicVine cover" | Implemented (line 29): 120 px wide, at the bottom of the ComicVine card. No loading state, no failure state. |

The older block is driven by the "Archive image" picker (reverse-image.js lines 6-8). It stays exactly as it is. Do not hide, move, relabel or reuse it.

## 2. Decisions

1. **Both covers move into one comparison strip** at the top of the evidence, above the two cards. The file cover sits at the centre line on the left, the ComicVine cover at the centre line on the right. Gap between them 12 px at every width. Reason: in the cards they would sit about 320 px apart at 1280 and a different distance in each card, and the longer ComicVine card would push its cover out of line.
2. **Same size and shape for both:** a 160 px wide box with a 2:3 shape (160 x 240). Reason: 120 px is a thumbnail; the only job of this change is comparison. This grows the ComicVine cover from 120 to 160 px. To go back, change the one width value, both covers follow.
3. **The ComicVine cover leaves its card.** That and the size are the only changes to existing ComicVine UI. The card keeps its fields, link and "Saved result / Checked just now" line.
4. **Non-interactive.** No click, no enlarge, no tab stop, so no tooltip (ProcessRules: tooltip for every new interactive control; none here).

## 3. Layout values for Ender

Strip (new container, first child of the evidence, before the cards):
- Two equal columns, 12 px gap, same as the cards grid. Bottoms aligned across the row (so a wrapped caption cannot misalign the boxes). 12 px vertical margin, like the cards. Stays two columns at every width; the 640 px card-stacking rule does not apply to it.
- File figure pushed to the right edge of column 1, ComicVine figure to the left edge of column 2. If there is no ComicVine figure (dead link, no provider), the file figure sits at the left edge.

Figure (one per cover):
- Reset the browser default figure margins to 0 (the default 40 px side margins would break 320 px).
- Width 160 px, never wider than its column.
- Caption (`figcaption`) above the box: 14 px, line 1.5, colour #aab4c6 (the existing label colour; 8.7:1 on #12151c, 7.8:1 on #1b202b), 4 px below.

Box:
- Full figure width, 2:3 shape, so its height follows the width.
- Background #12151c, 1 px border #485771 (the dialog border colour; decorative, the caption carries the meaning), 4 px radius.
- Image: fills the box, whole image visible (letterboxed, never cropped), no stretching.
- Placeholder text: centred, 14 px, #aab4c6 on #12151c (8.7:1), 8 px padding, wraps.
- The box is the same size in every state. Nothing moves when the image arrives or fails.
- No animation, no spinner, no fade.

## 4. Labels, alt text, states

| Item | Exact text |
|---|---|
| Caption, file | **Cover in this file** (same words as PerComicRecovery §2) |
| Caption, ComicVine | **ComicVine cover** (unchanged) |
| Image alt | Same as its caption: "Cover in this file" / "ComicVine cover" (matches the existing ComicVine alt; the repeat is minor and not worth test churn in a patch) |
| Loading, file | Reading cover… |
| Loading, ComicVine | Loading cover… |
| File cover unreadable (damaged archive, no images, anything else) | No cover could be read from this file. |
| ComicVine has no cover URL | ComicVine has no cover for this issue. |
| ComicVine cover failed to load | The ComicVine cover could not be loaded. |

Rules:
- Captions are always visible, in every state, so the label is never lost.
- One copy for every file failure on purpose. The cover reader cannot tell a damaged archive from "no images", from a RAR/7-Zip file (see Notes), or from an oversized first image, so a more specific sentence would sometimes be false. It does not diagnose, same stance as PerComicRecovery §4.
- Loading and failure text are plain text in the box, no live region: the cover is supporting evidence and must not interrupt the announcement of the screen. Set the figure `aria-busy` while loading.
- The ComicVine failure never changes the file side, and the reverse.
- Focus order is unchanged. Focus still lands on the "Help with this comic" heading after render. The strip adds no focus stop.
- State never depends on colour: every state has its own sentence.

## 5. Where the file cover appears

| Screen | Covers strip | Why |
|---|---|---|
| **Review this issue** (both entry routes: search and pasted link) | Yes, file + ComicVine | This is the comparison Sergei asked for. |
| **Help with this comic, conflict** | Yes, file + ComicVine | Identity decision between two issues. |
| **Help with this comic, dead link** | Yes, file only, left; no ComicVine slot | No provider issue exists, but the cover helps him recognise the right replacement. |
| Held, write stopped, write failed | No | No identity decision here. It would add about 270 px above the recovery buttons and one needless archive read per refresh. |
| **Review this change** table | No | Text diff after the choice is made. |
| Search and issue result lists | No (not in this spec) | They show text only today. Offered in §8. |
| Plain Details (no problem) | Unchanged | Already shows the older `#localCover`. |

The strip is requested by the caller, not by the evidence card: Help screens pass it for dead link and conflict, Review this issue always passes it.

The file cover is always the first image in the archive (the same image the older block starts on). It is not wired to the "Archive image" picker; changing the picker changes only the lower preview. Both can show at once; by default they are the same image.

## 6. Width check, no overlap

Dialog is min(1000 px, 95vw) with 24 px padding. Worst case below also takes off 15 px for the dialog's own scrollbar and 2 px for the border.

| Viewport (CSS px) | Strip column | Cover box | Result |
|---|---|---|---|
| 1280 | 461 | 160 x 240 | Covers touch the centre line, 12 px apart. Cards two columns below. |
| 641 | 265 | 160 x 240 | Same. Cards still two columns. |
| 640 (also 1280 at 200%) | 265 | 160 x 240 | Strip unchanged, cards stack file first. |
| 320 (also 640 at 200%, 1280 at 400%) | 113 | 113 x 170 | Both covers still side by side. "Cover in this file" may wrap to two lines; boxes stay level because the row is bottom-aligned. |

No fixed heights, no absolute positioning: the strip is normal flow, so nothing can sit over a card, caption or action row. At 320 the cards and actions simply move further down; the dialog already scrolls.

## 7. Futaba: measured checks (isolated fixtures only)

1. Measured rects at 320 / 640 / 1280 and at 100% / 200%: two boxes equal width and height (±1 px), bottoms level (±1 px), gap 12 px (±1 px), rects disjoint from captions, cards and buttons, no horizontal scroll in the dialog.
2. Fixtures: zero-image CBZ, corrupt ZIP, RAR renamed .cbz, real .cbr. File slot shows the exact copy, ComicVine slot is unaffected.
3. ComicVine issue with no cover, and with an unreachable cover URL: exact copy each; file slot unaffected.
4. Slow cover: "Reading cover…" shows, box does not change size when the image arrives.
5. Conflict and dead link show the strip; held, stopped, failed, Review this change and plain Details do not.
6. Changing "Archive image" changes only the lower preview; the strip does not move or reload.
7. No new Tab stop; after Review this issue renders, focus lands where it did before.
8. Screen reader: each figure reads its caption once, plus the image alt.

## 8. Questions for Sergei, and offers

1. Is "the first image in the file" good enough as the file's cover? That is what the app treats as the cover today. If a file starts with a credits or ad page, the comparison would mislead. Using the page the file itself marks as the front cover would be an engineering change, not a presentation one.
2. Cover reading works only for real ZIP/CBZ files today. For .cbr, .cb7, or a RAR file named .cbz, the slot will say "No cover could be read from this file." Is that acceptable for 0.2.3?

Offers, not fired: enlarge a cover on click; cover thumbnails in the search and issue result lists; fix the §1 order so the file's cover and path come before the action buttons on Help screens.

## Notes for Ender

- Evidence for the two entry points is built in one function (comic-recovery.js `appendEvidence`, called from `render` and `candidate`); the strip belongs there, requested by the caller as in §5.
- The cover endpoint (`/api/cover`) reads the first image by file name from a ZIP, refuses a first image over 20 MB, and answers failures with an HTTP error. A plain image error is enough to drive the unreadable state. If the endpoint later returns a reason, the exact variants would be "This file has no images." and "The first image is too large to preview."; they are not required now.
- Update tests that look up the ComicVine cover inside its card; it now lives in the strip.

## 9. Copy review: SerpApi removal (commit 69298f3, read-only review)

Verdict: all four copy changes are right. No wording changes, nothing for Ender to redo.

| # | Change | Verdict |
|---|---|---|
| 1 | Setup: SerpApi field, help and tooltip removed (desktop/setup.js) | Approved. Four fields remain, each with its own help and tooltip. |
| 2 | Dashboard keys editor: SerpApi row removed (static/comic-recovery.js) | Approved. Same four fields as setup. |
| 3 | Identify by cover: "Unresolved comic identities are researched automatically using Google Lens." (static/reverse-image.js) | Approved. Short, true, names only what runs. |
| 4 | Setup line "Adding keys does not switch on paid search." | **Keep unchanged.** Still true: web_search.py runs the paid Brave route only when `web_search.provider` is `brave` (default `free`), and Brave is now the only paid search. The sentence answers the worry that matters (does adding a key cost money) and matches the approved KeysEntry copy and the Brave field help. A reword would churn the spec and tests for no gain. |

Superseded in older specs (not edited here): FirstRunSetup_2026-10-13 ("Five fields below", the SerpApi row in the field table, the SerpApi input tooltip) and PerComicRecovery §4a, which reuses that field list. The field list is now four: ComicVine, Metron, Google Books, Brave Search.

Futaba, one extra fixture: a saved legacy SerpApi key is left intact by a keys-only save from the dashboard editor (PerComicRecovery §4a: unrelated keys are preserved) and is not shown anywhere in the UI.
