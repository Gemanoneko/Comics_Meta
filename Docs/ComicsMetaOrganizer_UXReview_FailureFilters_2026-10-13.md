# Comics Meta Organizer — Failure Filters Rendered Review and Amendment

Date: 2026-10-13. Owner: Judy. Scope: failure filters only. Reviewed rendered evidence from candidate eb64759; this is not a fresh rendering of the later candidate or a release verdict. The original UXSpec_FailureFilters_2026-10-13.md remains the base; the three rulings below supersede its conflicting layout and retry wording.

## Evidence and method

Historical evidence remains at C:/Users/AnGeLZzZ/AppData/Local/Temp/claude/C--Antigravity-Projects-Studio-Illuminati/f34a159a-afd4-4cc3-8efb-fbb74a16f69e/scratchpad/f014/evidence/shots/ . I inspected v014_320_all_viewport.png, crop_320_chips.png and v014_1440_details_write_stopped.png, and read v014_widths.json, details_geometry.json and v014_report.json. Futaba's QA report sections 1, 4.6 and 5 describe the fixture and rendering method. Measurements are historical getBoundingClientRect()/document geometry, not my new measurements. The rig substituted only the long fixture #roots paragraph with Y:\Comix; all other rendered content was unchanged. Preserve these pixels and JSON as unresolved review evidence. They contain local paths and must not be copied into the public repo.

| Finding | Recorded geometry | Ruling |
|---|---|---|
| 320px table overflow (V4-9) | document clientWidth 320, scrollWidth 327; table right 327; columns Comic94, Issue50, actions145. All files, Write failed and Held overflow7px. Classic15px scrollbar would imply22px overflow; this is a calculation, not a render. | Fix before completing this requested pass. Improvement over v0.1.3 does not satisfy the base no-sideways-scroll criterion. |
| 360px and wider | 360 document/scrollWidth360; table right327. 400/480/700/1024 also zero overflow. QA reports1440 zero in all tested states. | Preserve desktop layout; confine the narrow change below. |
| Details gap (V4-7) | reason/Last error rectangles:1440 reason y131..155, error155..212;700 reason131..176, error176..258;320 reason179..266, error266..397. Gap0 at all three. | Real readability defect by proximity; no physical overlap. |
| Retry count (V4-8) | QA real pass keeps count5, one manual retry stops at6; rendered template says Attempt6 of5 while its next one-shot retry is pending. | Replace denominator copy; never imply six attempts fit a five-attempt automatic budget. |

## 1. Narrow action layout

At viewport widths400 CSS px and below, stack Details above Folder in the same existing actions cell, left aligned, in normal flow. Gap6px between their hit rectangles; remove the existing horizontal sibling margin in this state. Keep current button font/padding and measured target sizes (Details62×33, Folder59×33); minimum24×24. Actions column should fit the larger button plus existing cell padding (about80px rather than145px); do not set a minimum table width or shrink fonts/buttons to hide overflow. Keep Try again under its reason in the comic cell, with its existing8px gap. Above400px preserve side-by-side actions.

The67px approximate recovered width should let the comic text breathe and cover the22px classic-scrollbar case. Ender chooses implementation; these are required relationships and acceptance targets, not a claim of post-fix dimensions. No overflow:hidden on the page/table, clipped button text, absolute positioning or hit-area overlap. Table and page must fit available clientWidth at320px and360px, including a classic scrollbar. Existing metadata-column hiding at700px remains.

## 2. Details spacing

When Last error exists, insert12 CSS px of clear vertical space between the reason block's bottom rectangle and the Last error box's top rectangle. Apply after wrapping at every width, for stopped and retrying writes. Keep the raw error inside the existing preview box. If no Last error exists, add no empty12px block. Existing paragraph spacing below the problem block remains. This uses the studio reference's proximity principle and the page's current spacing scale.

## 3. Honest retry copy

For write_failed with a positive count, replace the opening sentence at every count with:

Write attempt {count} failed; nothing was written.

Keep the current truthful scheduling suffix: Next try around {time}. for a future retry time; otherwise Next try at the next folder pass. Thus count6 reads Write attempt6 failed; nothing was written. Next try at the next folder pass. Spaces around substituted numbers are required. Do not show an of{limit} denominator on retrying rows or their Details block. Missing count retains The write failed; nothing was written. Next try at the next folder pass.

The stopped sentence remains Automatic writes stopped after {count} failed attempts. Close any program using the file or repair it, then use Try again. It reports the retained cumulative count5,6,7 honestly. Keep the one-attempt behavior, limit5, Retry requested state, tooltip and accessible name. This amendment also replaces the quoted Attempt5 of5 pending sentence in base section6. It changes presentation only; never reset counters or alter scheduling to make the sentence fit.

## 4. Hit areas, keyboard, tooltips and theme

Historical sizes: five chips widths138/172/159/115/164px, height32; desktop Try again75×35; narrow wrapped Try again63×56; Details62×33, Folder59×33. The320 crop shows separated chips/search/count/row actions, with Folder extending toward the edge rather than another control covering it. At1440 chips y1305..1337 and total y1353..1378 are separated16px; query/status bottom1292/1293 precede chips by12/13px. The JSON's generic table selector measures a different earlier table (y806..847), so do not use it as proof of comics header clearance; the rows themselves begin1435. Historical screenshots show no new physical covering outside the sanctioned modal; this does not replace a fresh hit test after the stack change.

QA4.6 records accessible names, pressed states, rendered contrast, 2px focus-visible outline with2px offset, retry error recovery and focus transfer to #total after row removal. Neutral/warning chip text12.50/6.80:1, reasons7.80:1, Try again5.70:1. Preserve these values and existing yellow/blue plus text badges. Only a dark theme exists; no new palette/theme scope is authorized.

I have not newly exercised Tab/Enter/Space,10-second tooltip dwell, native select popup or200% zoom. Do not claim those passed from screenshots. Futaba must check keyboard activation of the stacked actions and chips, visible unclipped focus, retained focus after polling, modal Escape/focus restoration, and the existing retry-to-#total behavior. All tooltips and accessible names stay per the base spec; the Folder check should inspect/mock its request and not open Explorer. No new controls or tooltip content are required.

## 5. Post-fix acceptance for Futaba

On the fixed commit, with offline fixtures only, capture320/360/400/1440 CSS px and200% zoom; all files plus every failure filter, long name, error banner shown, Details open, pending Retry requested and failed retry request. Record document scrollWidth/clientWidth, action-cell and button rectangles,12px Details gap, intersections and hit-test results at button centers/edges. Test at least320 with usable clientWidth305px or a real classic scrollbar; distinguish simulated deduction from actual render. No sideways scroll caused by the changed controls, no clipped text or intercepted hit area, and minimum24×24 targets. Verify count1/4/5/6/7 plus missing count in row and Details; after two separate one-shot retries, count increases but denominator never returns. Preserve count and exactly-one-attempt safety checks. Confirm all original tooltip/accessibility contracts remain and disclose unsupported native-popup checks.

The existing long-path Details overflow is separate historical evidence (320 dialog clientWidth250, scrollWidth395). New failure controls must not worsen it; report it explicitly rather than conceal it by page clipping. Repairing the entire pre-existing Details layout is outside this amendment.

## Delivery and hygiene

Only new file: Docs/ComicsMetaOrganizer_UXReview_FailureFilters_2026-10-13.md. No code, data, existing docs or git operations changed. No browser, server or scratch files created in this pass; historical evidence retained. Sully must commit this spec before Ender is briefed to implement its rulings. Final rendered acceptance belongs to Futaba on the fixed candidate.
