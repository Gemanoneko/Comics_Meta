# Update statistics panel — UX spec

Date: 2026-10-26. Owner: Judy. Status: reviewable; Sully commits this exact file before Ender is briefed. Classification: EXTEND of `static/index.html` (one new panel, one relabelled tile and its footnote). Everything else on the page is preserved. No code, no commit and no running-app contact was part of writing this; values come from the page's own CSS. Rulings it implements: `Docs/ComicsMetaOrganizer_Backlog.md` § "Update statistics graph above Live library" (Sergei, 2026-10-26). They are not revisited here.

**Sergei, 2026-10-26:** approved this spec as written ("Build it"). He also ruled that the comic-row label "Updated by this tool" becomes **"Tagged by this app"**, so the row, the filter and the counter ("Currently tagged by this app") all say "tagged".

Basis: Fluent segmented picker, NN/g visibility of system status and error prevention, WCAG 2.2 AA (1.4.3 text, 1.4.11 graphics, 2.1.1 keyboard, 2.4.7 focus), ProcessRules § No UI element may cover another, § A new control is born with its tooltip, § Copy is short, specific, and has no memory.

## 1. Decisions in one screen

| Topic | Decision |
|---|---|
| Placement | New `<section class="panel" id="statsPanel">` directly after "Live enrichment progress" (`index.html:12`) and before "Live library" (`:13`). Full width, same `.panel` look. About 470 px tall. |
| Title | `Update statistics` |
| Period picker | Six single-select chips: `Last hour`, `Today`, `This week`, `This year`, `All time`, `Custom`. **Default: `Today`**, selected on every page load. Not remembered between launches. |
| Custom | Selecting `Custom` reveals `From` and `To` date inputs in-flow under the chips. No Apply button: the chart updates when both dates are valid. |
| Headline | Big number plus `comics updated {period}`, then a muted line with the exact dates. |
| Chart | Hand-drawn SVG vertical bars, one series, one colour, 192 px tall. Bar size by period (section 5). |
| Bars vs total | The bar unit is always named above the chart. A one-line note under the chart appears only when the bars add up to more than the total (section 8). |
| Existing counter | Label `Updated by this app` becomes `Currently tagged by this app`. Its footnote sentence and a tile tooltip change with it (section 2). |
| Theme | The page is dark only (`color-scheme:dark`, no light styles anywhere). This spec is dark only. |

## 2. Existing UI that changes

The only edits outside the new panel. All in `static/index.html:12`.

| Element | Now | New |
|---|---|---|
| Tile label under `#comicCounter` | `Updated by this app` | `Currently tagged by this app` |
| Tile tooltip (`title` on `.live-counter` that holds `#comicCounter`; none today) | none | `Comics tagged by this app right now; the number can go down. Update statistics below counts every comic updated in a period.` |
| First sentence of the `<small>` footnote | `Updated is write history and overlaps the other counters.` | `Tagged overlaps the other counters.` |

The rest of the footnote (`Present means fields exist…` and `Folder totals cover…`) is unchanged. `#comicCounter` keeps its id and its value.

Why this pair of words: the tile is a state ("tagged", now) and the graph is an event count ("updated", in a period). The graph's headline always carries its period (`comics updated today`), so the two numbers cannot read as the same thing. `Tagged by this app` is already the name of the status filter, so the tile reuses an existing word.

Dependency for Ender: the tooltip says the number can go down. That is true only if `totals.updated` is the count of comics in the tagged state now, which is what the code check reported. If it is not, tell Judy and the two strings are rewritten.

## 3. Panel layout

Default state (Today, 15:20, 24 hourly bars, 17 comics; two comics were updated in two different hours, so the bars sum to 19 and the note shows):

```
+--------------------------------------------------------------------------------------+
| Update statistics                                                                    |
|                                                                                      |
| ( Last hour ) [[ Today ]] ( This week ) ( This year ) ( All time ) ( Custom )        |
|                                                                                      |
| 17  comics updated today                                                             |
| Mon 26 Oct 2026                                                                      |
|                                                                                      |
| Comics per hour                                                                      |
|   4 |.. .. .. .. .. .. .. .. ## .. .. .. .. .. .. .. .. .. .. .. .. .. .. ..         |
|     |                     ## ##          ##                                          |
|   2 |.. .. .. .. .. .. .. ## ## ## .. ## ## .. ## .. .. .. .. .. .. .. .. ..         |
|     |                  ## ## ## ##    ## ## ## ## ##                                 |
|   0 +------------------------------------------------------------------------        |
|      00    02    04    06    08    10    12    14    16    18    20    22            |
|                                                                                      |
| A comic updated in several bars counts once in the total.                            |
+--------------------------------------------------------------------------------------+
  [[ ]] = selected chip. Hours after 15:00 are empty and inert. Labels follow the OS locale.
```

Hover on the 08:00 bar:

```
        +--------------------------+
        | Mon 26 Oct, 08:00-09:00  |
        | 4 comics                 |
        +--------------------------+
                  ##
```

Custom selected (adds one in-flow row; chart moves down 44 px):

```
| ( Last hour ) ( Today ) ( This week ) ( This year ) ( All time ) [[ Custom ]]         |
| From [ 28/09/2026 ]  To [ 26/10/2026 ]                                                |
```

### Vertical stack (top to bottom, all in flow, nothing positioned except the tooltip)

| Row | Content | Spec |
|---|---|---|
| Panel | `.panel` as the neighbours | `#1b202b` fill, 1 px `#303848` border, 14 px radius, 22 px padding, 20 px bottom margin |
| Title | `<h2 id="statsTitle">` | the page's default `h2` (20 px), default margins, same as the other panels |
| Picker | `#statsPeriod`, `role="radiogroup"`, `aria-labelledby="statsTitle"` | flex row, `flex-wrap:wrap`, gap 8 px; chips 32 px high |
| Custom row `#statsCustom` | only when `Custom` is selected | margin-top 12 px; flex, gap 8 px 12 px, wrap; items 32 px high |
| Custom message `#statsRangeError` | only when the range is invalid | margin-top 8 px; 14 px / 1.5; colour `#ffd697` |
| Headline `#statsHead` | number, label, dates | margin-top 16 px; see section 6 |
| Unit label `#statsUnit` | `Comics per hour` etc. | margin-top 16 px; 13 px / 20 px; `#9dacc2` |
| Chart `#statsChart` | focusable wrapper, `position:relative`, holds the SVG and the tooltip | margin-top 4 px; height 192 px |
| Note `#statsNote` | status and note line | margin-top 8 px; `min-height:21px`; 14 px / 1.5; always present so nothing below it jumps |

Height rule: only the custom row (+44 px) and the custom message (+29 px) change the panel's height. No other state may change it. Loading, empty, error and refresh all keep 192 px for the chart and 21 px for the note.

Elements are `div`s, not `p`s, so the page's `p{color:#aab4c6;line-height:1.6}` and margins do not leak in.

## 4. Period picker

### Chips

Reuse the look of the existing `.chip` (32 px min height, 4 px 12 px padding, 14 px text, 8 px radius, 1 px `#aab4c6` border, `#242c3b` fill, `#eef2fb` text, hover inset 1 px `#bcd8f9`, focus outline 2 px `#bcd8f9` offset 2 px). The status chips are found by `#problemChips .chip`, so reusing the class elsewhere does not collide with their handlers.

Markup: six `<label class="chip">` each holding a visually hidden native `<input type="radio" name="statsPeriod">` and the text. Native radios give one Tab stop, arrow-key movement and correct screen-reader grouping with no extra script. Labels use `display:inline-flex; align-items:center`.

| State | Look |
|---|---|
| Unselected | as `.chip` above |
| Hover, unselected | inset 1 px `#bcd8f9` (as `.chip:hover`); fill stays `#242c3b` |
| **Selected** | fill `#385ea1`, text `#eef2fb`, border 1 px `#bcd8f9` plus inset 1 px `#bcd8f9` (a 2 px ring). Hover changes nothing. |
| Keyboard focus | outline 2 px `#bcd8f9`, offset 2 px, on the label (key off `input:focus-visible`) |

Selected is told apart by fill, ring weight (2 px against 1 px) and the ring's lighter colour, so it never depends on colour alone. Text on selected fill is 5.70:1. Selected style may be keyed off `input:checked` through `label:has(...)` or a class set by the change handler; Ender's choice, same result.

Order is ascending scale. The chips are a single choice, never a toggle: clicking the selected chip does nothing.

| Order | Label | Period | Tooltip (`title` on the label) |
|---|---|---|---|
| 1 | `Last hour` | the 60 minutes ending now | `Comics updated in the last 60 minutes.` |
| 2 | `Today` (default) | local midnight to now | `Comics updated since midnight today.` |
| 3 | `This week` | Monday 00:00 to now | `Comics updated since Monday this week.` |
| 4 | `This year` | 1 Jan 00:00 to now | `Comics updated since 1 January this year.` |
| 5 | `All time` | from the first recorded update to now | `Every comic updated since counting began on {d MMM yyyy}.` If the start date is not known: `Every comic updated since counting began.` |
| 6 | `Custom` | From 00:00 to To 24:00, local, both days included | `Pick the first and last day to count.` |

All six fit on one line from 640 px window width (the window minimum) up; below about 600 px of panel width they wrap in flow.

### Custom range controls

| Control | Spec |
|---|---|
| `#statsFrom`, `#statsTo` | `<input type="date">`. Width 176 px, min-height 32 px, padding 4 px 12 px, 14 px text, fill `#242c3b`, border 1 px `#aab4c6`, text `#eef2fb`. The page rule `input{flex:1;min-width:180px}` must be overridden to `flex:0 0 auto;min-width:0` here, or the inputs stretch. Native dark picker comes from `color-scheme:dark`. |
| Labels | visible text `From` and `To`, 13 px `#9dacc2`, 8 px from their input. The inputs also carry `aria-label="From date"` and `aria-label="To date"`. |
| Limits | `max` on both = today. No `min`: a date before the first update is allowed and returns zero. |
| Prefill on first selection | To = today, From = today minus 29 days (30 days). Later selections restore the last values used in this page session. |
| When it applies | on `change` of either input, when both hold a date and From is not after To. No Apply button. |
| Tooltips | From: `First day of the range.` To: `Last day of the range. The whole day counts.` |
| Focus | outline 2 px `#bcd8f9`, offset 2 px |

Invalid input (chart keeps its last good data; nothing is fetched; `aria-invalid="true"` on the offending input, border `#e08a7e`, 5.41:1 on the fill; message in `#statsRangeError`, `role="status"`):

| Case | Message |
|---|---|
| To before From | `End date is before the start date.` |
| A date is empty | `Pick both dates.` |
| A date is after today (typed) | `Dates after today are not available.` |

The message clears as soon as the range is valid.

Tab order: picker (one stop) → From → To (only when shown) → chart (one stop).

## 5. Bar size, per period

One bar is the number of distinct comics updated inside that bar's slot. Every period except `Last hour` uses fixed local-calendar slots; `Last hour` uses 12 equal slots counted back from now.

| Period | Slots | Unit label (`#statsUnit`) |
|---|---|---|
| Last hour | 12 bars of 5 minutes, the 60 minutes ending now | `Comics per 5 minutes` |
| Today | one bar per clock hour of the day: 24 (23 or 25 on a daylight-saving change, never hardcoded) | `Comics per hour` |
| This week | 7 bars, Monday to Sunday | `Comics per day` |
| This year | 12 bars, January to December | `Comics per month` |
| All time, Custom | by span, rule below | the matching unit |

Span rule for **All time** and **Custom** (span = local calendar days from the first day to the last day, both included):

| Span | Bars | Unit label |
|---|---|---|
| 1 day | hourly (a one-day custom range, or the first day of history) | `Comics per hour` |
| 2 to 60 days | daily | `Comics per day` |
| 61 to 420 days | weekly, Monday start | `Comics per week` |
| 421 days or more | monthly | `Comics per month` |

No span ever draws more than 60 bars. Today the history is about 25 days, so All time draws daily bars; it switches to weekly bars at 61 days and to monthly bars past 14 months. The unit label always says which one is on screen.

Slot rules:

- **Partial edge slots.** A weekly or monthly slot cut by the period's start or end counts only the part inside the period. Its tooltip names the clipped dates.
- **Current slot.** The slot that contains now is drawn like any other; its tooltip adds `so far`.
- **Future slots** (hours after now today, days after today this week, months after this one this year) draw no bar, no hover highlight and no tooltip, and arrow keys skip them. The axis still spans the whole period so bars do not move as the day goes on.
- **Zero slots** in the past draw no bar but still hover and read `0 comics`.
- **Midnight roll.** If the local date changes while `Today`, `This week` or `This year` is selected, the next refresh moves the chart to the new period without any user action.

### Axis labels

Labels are 13 px, `#9dacc2`, centred under their slot (text-anchor middle), formatted with the OS locale like the rest of the page (`toLocaleDateString`, `toLocaleTimeString`, `Intl.DateTimeFormat` with no locale argument). The mockup shows a 24-hour locale.

| Unit | Label text | Format options |
|---|---|---|
| 5 minutes | five fixed labels on the slot *boundaries* 0, 3, 6, 9, 12: `−60 min`, `−45`, `−30`, `−15`, `now`. The last one is right-aligned to the plot edge, the first is centred on the plot's left edge. | static strings |
| Hour | hour the slot starts | `{hour:'numeric'}` |
| Day, 14 bars or fewer | weekday and day | `{weekday:'short', day:'numeric'}` |
| Day, more than 14 bars | day of month; the first label and any slot that is the 1st of a month use day and month | `{day:'numeric'}` / `{day:'numeric', month:'short'}` |
| Week | the Monday | `{day:'numeric', month:'short'}` |
| Month | month; the first label and every January add the year | `{month:'short'}` / `{month:'short', year:'numeric'}` |

Thinning (all units except 5 minutes): pitch = plot width / slot count. Label every Nth slot, starting at the first slot, where N is the smallest of 1, 2, 3, 4, 6, 12, 24, 48 such that N × pitch is at least 72 px. If none fits, label only the first slot. Keep label x inside the SVG (right-align the last label if it would clip). No tick marks.

## 6. Headline

Inline row, `display:flex; align-items:baseline; gap:10px; flex-wrap:wrap`:

- Number `#statsTotal`: 28 px / 1.2, weight 600, `#e7eaf1`, `font-variant-numeric:tabular-nums`, `toLocaleString()`.
- Label `#statsLabel`: 16 px / 1.5, `#e7eaf1`.
- Dates `#statsRange`, on its own line, margin-top 2 px: 14 px / 1.5, `#aab4c6`.

The whole block carries `title="Every comic updated in this period, each counted once."`

Singular: `1 comic updated today`. Zero: `0 comics updated today`.

| Period | Label after the number | Dates line |
|---|---|---|
| Last hour | `comics updated in the last hour` | `{time}–{time}`, the exact window, e.g. `14:20–15:20` |
| Today | `comics updated today` | `Mon 26 Oct 2026` |
| This week | `comics updated this week` | `Mon 26 Oct – Sun 1 Nov 2026` (year on both ends only if the week crosses New Year) |
| This year | `comics updated this year` | `2026` |
| All time | `comics updated, all time` | `Since 2 Oct 2026` (`Since counting began` if the date is unknown) |
| Custom | `comics updated in this range` | `12 Oct – 26 Oct 2026`; one date if From = To; year on both ends if they differ |

Date formats: weekday `{weekday:'short', day:'numeric', month:'short', year:'numeric'}`, times `{hour:'numeric', minute:'2-digit'}` (the format `problemTime()` already uses). The headline block, chart and unit label always update together from one response, so the label never describes a different period than the number.

## 7. Chart drawing

The SVG is `aria-hidden="true"`, drawn at 1 SVG unit = 1 CSS px with its width taken from its container (re-draw on width change or new data only, not on every poll). Fixed measures:

| Measure | Value |
|---|---|
| SVG height | 192 px |
| Left gutter (y labels) | 44 px |
| Right padding | 8 px |
| Plot top / bottom | y = 8 / y = 152 (plot height 144 px) |
| X-label baseline | y = 172 |
| Plot width | container width − 52 px |
| Slot pitch | plot width / slot count |

Scale and axes:

- **Linear**, zero-based. `yMax` = the smallest value of the form m × 10^k with m in 1, 2, 4, 6, 8 that is at least the tallest bar and at least 4 (so 4, 6, 8, 10, 20, 40, 60, 80, 100, 200 …). Mid line is `yMax / 2`, always a whole number.
- Y labels at 0, mid and `yMax`: 13 px, `#9dacc2`, text-anchor end at x = 36, vertically centred on their line, `toLocaleString()`.
- Grid lines at mid and `yMax`: 1 px `#303848`, full plot width, drawn first. Baseline at 0: 1 px `#485771`, drawn over the bars' feet. Grid and baseline are decoration; the labels carry the values.

Bars:

- Width = pitch × 0.7, clamped to 2–48 px, centred in the slot. Corner radius 2 px.
- Fill `#4776c6` (3.63:1 on `#1b202b`, passes 1.4.11).
- Any count of 1 or more is at least 3 px tall, so a single comic stays visible on a tall axis. Zero draws nothing.
- Hover or keyboard-active slot: slot background `#242c3b` (full plot height) and the bar turns `#bcd8f9`. This is a lightness change, so it survives colour-blind viewing.
- One series, one hue, no red or green, no animation of any kind (no bar growth, no fade).

Hit area: no per-bar rectangles. One `pointermove` handler on the plot area maps x to a slot index (`floor((x − 44) / pitch)`); the active region is the full slot column from y = 8 to y = 152, so empty and short bars are as easy to hit as tall ones. Nothing is clickable: bars are not buttons, the cursor stays default.

## 8. Hover, keyboard and the "bars do not add up" problem

### Tooltip (`#statsTip`)

The chart's own hover tooltip is the tooltip for the chart control. The native `title` is not set on the chart, so the two never stack. (If Ender must cut scope, native `<title>` elements with the same text are an acceptable first cut, with no keyboard path.)

| Property | Value |
|---|---|
| Appears | immediately when the pointer enters an active slot; no delay, no fade |
| Hides | when the pointer leaves the plot, on `Escape`, on chart blur |
| Position | above the bar, 8 px gap, centred on the slot; for an empty slot, 8 px above the baseline. Clamped so it stays inside the chart wrapper horizontally. If there is no room above (tooltip top would be above the wrapper), move it beside the slot instead: right of the slot, or left if the right side clips. |
| Style | fill `#242c3b`, 1 px `#485771` border, 8 px radius, padding 8 px 12 px, shadow `0 4px 16px #000a`, `white-space:nowrap` |
| Text | line 1 14 px / 1.5 weight 600 `#eef2fb`; line 2 14 px / 1.5 `#e7eaf1` (12.5:1 and 13:1 on the fill) |
| Layering | `position:absolute`, `z-index:1` (the sticky error banner is 2), **`pointer-events:none`** so it never steals a hover from the slot beneath it |

Line 1 by unit (the clipped part of the slot for edge slots):

| Unit | Format | Example |
|---|---|---|
| 5 minutes | time–time | `14:37–14:42` |
| Hour | `ddd d MMM, time–time` | `Mon 26 Oct, 08:00–09:00` |
| Day | `ddd d MMM yyyy` | `Mon 26 Oct 2026` |
| Week | `ddd d MMM – ddd d MMM yyyy` | `Mon 19 Oct – Sun 25 Oct 2026` |
| Month | `MMMM yyyy` | `October 2026` |

Line 2: `{n} comics`, `1 comic`, `0 comics`; the slot that contains now adds ` so far` (`4 comics so far`). The word "distinct" is never shown.

### Keyboard

`#statsChart` is one Tab stop (`tabindex="0"`, `role="group"`, `aria-label` = unit label + period, e.g. `Comics per hour, today. Left and right arrows read each bar.`). Focus ring: outline 2 px `#bcd8f9`, offset 2 px, on the wrapper (the panel must not clip it with `overflow:hidden`).

| Key | Action |
|---|---|
| `←` `→` | previous / next active slot; shows its tooltip |
| `Home` `End` | first / last active slot |
| `Esc` | hides the tooltip, focus stays |
| Tab in | active slot = the last active slot (the one that contains now, if the period includes now) |

The tooltip text is also written to a visually hidden `#statsAnnounce` (`aria-live="polite"`, `aria-atomic="true"`) on keyboard moves, and the headline sentence is written there when the period changes. Pointer hover does not announce.

### Making bars versus total look right

Why they differ: one comic updated on Monday and Tuesday is in both daily bars and in the weekly total once.

1. The unit is always stated above the chart (`Comics per hour`), so each bar reads as "comics in that slot", not as a share of the headline.
2. The headline says `comics updated {period}` and never `total` or `sum`; tooltips say `{n} comics` for their slot.
3. When, and only when, the bars add up to more than the total, `#statsNote` shows: `A comic updated in several bars counts once in the total.` When they add up to exactly the total, the line stays empty (the slot is still reserved). Bars can never add up to less than the total.

## 9. States

| State | Number | Chart area | `#statsNote` |
|---|---|---|---|
| **Loading, first** (no data yet) | `–` | empty 192 px box, no axes, no bars | `Loading statistics…` |
| **Loading, period change** | keeps the old content until the new response arrives; if still pending after 250 ms: `–` and content at 60% opacity | as the old chart, 60% opacity | `Loading statistics…` |
| **Normal** | the total | bars, axes | the bars note (section 8) or empty |
| **Empty** (total 0) | `0` with the normal label | grid, y labels 0 / 2 / 4, x labels, no bars; hover still reads `0 comics` | `Last update: {when}.` (see below). With no update on record at all: `No updates yet.` |
| **Error** (request fails) | keeps the last good number (`–` if there is none) | last good chart at 60% opacity (empty box if none) | `Statistics unavailable. Retrying.` in `#ffd697` (11.9:1). Inline, never the page's sticky `#error` banner, matching the existing progress line. |
| **Invalid custom range** | unchanged | unchanged | unchanged; message sits under the date inputs (section 4) |

`Last update: {when}`: time only if the last update was today (`Last update: 08:14.`), otherwise weekday, date and time (`Last update: Sun 25 Oct, 22:14.`), formatted as `problemTime()` does. This is the most common empty case, first thing in the morning, where the next question is whether the app is stuck; the answer is one line. It needs one extra field from the server (section 10). If Ender cannot supply it cheaply, drop the line and leave the note empty; nothing else depends on it.

Refresh behaviour (all states):

- Fresh within 15 s for any period whose end is now (every preset, and a custom range that ends today). Pause while `document.hidden`; refresh at once when visible again and on every selection change. A custom range that ends before today is fetched once per selection.
- The latest selection wins: a response for an earlier selection is discarded (same guard `load()` uses with `wanted`). Do not drop a selection change because a fetch is in flight.
- Write-on-change, as the page does elsewhere: if a response equals the last one drawn, touch nothing.
- A refresh never moves focus, never scrolls, never closes a hovered tooltip (keep the active slot if the slot list is the same length and starts, otherwise clear it), and never resets the picker or the date inputs.
- The existing 2 s poll does not drive this panel.

## 10. What the panel needs from the server

Names are Ender's. These are the facts the screen has to be right about:

- One `now`, with the window, the bar slots and the total all computed from it, so the headline and the bars agree. For `Last hour`: window = `now − 60 min` to `now`, 12 equal slots.
- The resolved period (start, end, unit) and the slot list as `[start, end, count]`, built in local time, so the browser never recomputes daylight-saving boundaries. The distinct total is its own query, not a sum of the slots.
- `first_at` (earliest history row) for the `All time` tooltip and dates line.
- `last_at` (latest history row, any period) for the empty-state line.
- Weeks start Monday. Boundaries are local time.

## 11. Colour tokens (all existing page hexes)

| Use | Hex | Contrast on `#1b202b` unless noted |
|---|---|---|
| Panel fill | `#1b202b` | – |
| Bar | `#4776c6` | 3.63 |
| Bar, hover or active | `#bcd8f9` | 11.12 |
| Slot highlight | `#242c3b` | decoration |
| Axis and unit text | `#9dacc2` | 7.08 |
| Dates line, note | `#aab4c6` | 7.80 |
| Headline, tooltip text | `#e7eaf1`, `#eef2fb` | 13.54, 12.50 on `#242c3b` |
| Chip border | `#aab4c6` | 7.80 |
| Selected chip | `#385ea1` fill, `#eef2fb` text | 5.70 text; `#bcd8f9` ring 11.12 |
| Focus ring | `#bcd8f9` | 11.12 (12.46 on the page fill) |
| Warning and error text | `#ffd697` | 11.89 |
| Invalid input border | `#e08a7e` | 5.41 on `#242c3b` |
| Grid, baseline | `#303848`, `#485771` | decoration |

Colour-blind check: one data hue (blue), highlight by lightness, selection by fill plus ring weight, no red/green pairing. Light theme: not applicable, the page has none. If one is added later, lift these hexes into it in one pass.

## 12. Every new control and its tooltip

| Control | Tooltip |
|---|---|
| `Last hour` | `Comics updated in the last 60 minutes.` |
| `Today` | `Comics updated since midnight today.` |
| `This week` | `Comics updated since Monday this week.` |
| `This year` | `Comics updated since 1 January this year.` |
| `All time` | `Every comic updated since counting began on {d MMM yyyy}.` |
| `Custom` | `Pick the first and last day to count.` |
| From date | `First day of the range.` |
| To date | `Last day of the range. The whole day counts.` |
| Chart (every active slot, pointer and keyboard) | the hover tooltip in section 8 |
| Not controls, explanatory only: headline block, the relabelled tile | strings in sections 6 and 2 |

## 13. No element covers another

Nothing in the panel is positioned except `#statsTip`. Rows are block or flex flow; the chart wrapper's rect starts 4 px below the unit label's rect. The tooltip is the sanctioned transient overlay class and is `pointer-events:none`, so it takes no hit area from any slot, chip or input. The native date picker is a browser overlay.

Hit rects to measure, at a 1280 px window (panel inner width about 1150 px, plot width about 1100 px, 24 bars, pitch about 46 px) and at the 640 px minimum (inner width about 550 px, plot about 497 px, pitch about 21 px):

| Rect | Expected |
|---|---|
| Each chip | 32 px high, no two chips overlapping, 8 px gap |
| `#statsFrom`, `#statsTo` | 176 × 32 px, 12 px apart (the `To` label sits between) |
| Active region of the chart | x = 44 to container width − 8, y = 8 to 152; slot columns tile it exactly, pitch wide each, no gap, no overlap |
| `#statsTip` | any size, but zero hit area |
| Chart focus ring | fully visible, not clipped by the panel |

States to measure in: default; each of the six periods; `Custom` valid; `Custom` invalid with the message; tooltip on the first slot, the last slot and the tallest bar; empty; loading; error; Details dialog open over the page (the chart keeps refreshing behind it and must not take focus); the sticky `#error` banner showing (tooltip stays under it); widths 640, 700, 1000, 1280; 200% zoom.

Bars as a pointer target: they perform no action, so WCAG 2.5.8 target size does not apply; the arrow-key path gives the same information.

## 14. Acceptance, for Futaba (source and static fixtures; no live catalog)

1. Default load: `Today` chip selected, headline `{n} comics updated today`, 24 hourly bars (23 or 25 on a daylight-saving date), future hours empty.
2. All six chips: label, dates line, unit label and bar count match sections 5 and 6; tooltips match section 12.
3. Span rule: custom ranges of 1, 2, 60, 61, 420 and 421 days give hourly, daily, daily, weekly, weekly, monthly; never more than 60 bars.
4. Weeks start Monday: the `This week` dates line runs Monday to Sunday, and weekly bars start on a Monday.
5. Bars versus total: a fixture where one comic appears in two slots shows the note; a fixture where it does not leaves `#statsNote` empty with no layout shift.
6. Empty state: 0 comics today shows `0`, the axes, `Last update: …`, and hovering a past hour reads `0 comics`.
7. Loading (first and slow period change) and error states as in section 9; panel height unchanged between them.
8. Custom: prefill is the last 30 days; To before From, empty date and a future date each give their message and no request; the range applies on its own when valid.
9. Keyboard only: Tab reaches picker, dates, chart; arrows move the radio selection; chart arrows, `Home`, `End`, `Esc` work; focus rings visible and unclipped.
10. Refresh: leave the pointer on a bar for 30 s; the tooltip stays and focus never moves.
11. Relabel: tile reads `Currently tagged by this app`, footnote starts `Tagged overlaps the other counters.`, tile tooltip as section 2, `#comicCounter` value unchanged.
12. Section 13 rects measured in the listed states.

## 15. Notes for Ender and Jane

- Old strings: `Updated by this app` and `Updated is write history` occur only in `static/index.html:12`. No test asserts them. `tests/test_failure_filters_dom.py:122` asserts the filter option `Tagged by this app`, which does not change.
- `README.md:102` calls `Tagged by this app` a "write-history filter". If the tagged count can drop, that sentence is inaccurate and the README needs Ender's check. Not part of this spec.
- Row labels in the table still read `Updated by this tool` for the same state (`index.html:166`). Left alone here; see question 1.
- No dependency is added: inline SVG and plain DOM only.

## Questions for Sergei

1. The table rows say `Updated by this tool` for the state the counter now calls `Currently tagged by this app`, and the status filter says `Tagged by this app`. Rename the row label to `Tagged by this app` so all three match? (yes / no)

## § Addendum 2026-10-26 (post-build)

Owner: Judy. Written after reading Ender's uncommitted build (`update_stats.py`, `static/update-stats.js`, the `static/index.html` diff) and measuring his nine screenshots pixel by pixel (panel crops at device pixel ratio 1; 1201 px wide at the 1280 window, 595 px at 640; x and y are counted from the image's top-left, so the panel's inner left edge is x = 23). Where this addendum and the sections above disagree, the addendum wins; each rule names the section it amends. Everything else stands. Sergei's backlog rulings are untouched. Question 1 above is closed by Sergei's ruling in the header (the row label is `Tagged by this app`), so the third bullet of section 15 is out of date.

### A1. Long ranges: the 60-bar rule (replaces the span table and the "never more than 60 bars" paragraph in section 5)

**Rule.** For `All time` and `Custom`: a range of one calendar day is hourly, as before. Any longer range uses the **finest unit, tried in this order, whose bar count for those exact dates is 60 or fewer: day, week (Monday start), month, year.** The count includes the partly covered slot at each end. The unit label always names the unit on screen. Ender tries the units in order and keeps the first that fits; no day thresholds are hardcoded, so the 60-bar limit holds by construction.

What that means (every count includes the edge slots):

| Range | Unit | Bars |
|---|---|---|
| 1 day | hour | 24 (23 or 25 on a clock-change day) |
| 2 to 60 days | day | 2 to 60 |
| 61 to 414 days, any start day | week | 9 to 60 |
| 415 to 420 days | week if the range touches 60 or fewer Monday-start weeks, otherwise month | 14 to 60 |
| 421 days up to 60 calendar months touched | month | 14 to 60 |
| 61 or more calendar months touched | year | 6 to 60 |

Why 414: a week-based range starting on a Sunday touches one extra week, so 414 days is the longest range that stays at 60 weekly bars from any start day. Before this rule a 420-day range starting on a Sunday drew 61 bars.

Test dates (all checked): Sun 4 Jan 2026 to Sun 21 Feb 2027 is 414 days, 60 weekly bars. Sun 4 Jan 2026 to Sat 27 Feb 2027 is 420 days, 61 weeks touched, so monthly (14 bars). Mon 5 Jan 2026 to Sun 28 Feb 2027 is also 420 days, 60 weeks, so weekly. 1 Jan 2021 to 31 Dec 2025 is 60 months, monthly, 60 bars. 1 Jan 2021 to 1 Jan 2026 touches 61 months, yearly, 6 bars, the last one holding one day.

**Year bars (new unit).** The server unit is `year`, slots cut at 1 January local, partial first and last years clipped like months.

| Item | Spec |
|---|---|
| Unit label (`#statsUnit`) | `Comics per year` |
| Axis label | `{year:'numeric'}`, thinned by the rule in A3 row 2 |
| Tooltip line 1 | the year, `2024`; a year clipped by the range names its dates exactly as a clipped month does (`Sun 12 Jan – Thu 31 Dec 2020`) |
| Headline, dates line, notes | unchanged (the period's own wording) |

**Date limits (amends section 4, "Limits").** `#statsFrom` and `#statsTo` get `min="2000-01-01"` as well as `max` = today. The server's own floor moves from 1970-01-02 to 2000-01-01 with the same message. Reason: the app cannot have updated a comic before it existed, and with 2000 as the floor the yearly rule stays at 60 bars or fewer through 31 Dec 2059. A 1970 floor would have broken the 60-bar rule in 2030. Rejected alternatives: a hard cap with a message (blocks a legitimate range, against user control) and a quarterly unit (a fifth unit for ranges the history cannot reach before 2031).

New row in the invalid-input table (amends section 4); no request is made, `aria-invalid="true"` goes on the offending input:

| Case | Message |
|---|---|
| A date is before 1 Jan 2000 (typed) | `Dates before 2000 are not available.` |

When several inputs are wrong, one message shows, in this order: `Pick both dates.`, `Dates after today are not available.`, `Dates before 2000 are not available.`, `End date is before the start date.` (the build already uses this order for the other three).

**A server refusal is not an outage.** `update-stats.js:96-103` sends every failed request to the Error state, so a refused date today shows `Statistics unavailable. Retrying.` and retries every 15 s for ever. Rule: an HTTP 400 whose `code` is `invalid_range` shows its `error` text in `#statsRangeError` (same style and `role="status"` as above), keeps the last good data, marks no outage and schedules no retry. Every other failure stays as section 9.

**What 60 bars looks like (accepted, no change).** At the 640 window the plot is 497 px, pitch 8.28 px, bar 5.8 px; at 1280 pitch 18.4 px, bar 12.9 px. The pointer column is 8.3 px wide at the minimum window; the arrow-key path reads the same tooltips, so this stays.

### A2. Daylight saving (amends section 5 axis labels and section 8 tooltip line 1)

Cause: the build formats a slot's end instant on its own. On the autumn day the first copy of the repeated hour ends at the second copy's start, so it reads `02:00–02:00`.

Rules (these also hold for 5-minute slots; day, week, month and year slots show dates and are unaffected):

1. **The end time is read on the clock that was running at the slot's start**: start clock plus the slot's length. Never format the end instant alone.
2. **Repeated hour.** Two consecutive hourly slots with the same start clock time are the repeated hour. Line 1 is identical for both except a suffix: ` (first time)` on the first, ` (second time)` on the second. Line 2 is unchanged (`4 comics`, `4 comics so far`). The keyboard announcement is the tooltip text, suffix included.
3. **Spring day.** The missing hour has no slot (23 bars). The slot that spans the jump reads `01:00–02:00`; no suffix.
4. **Hourly axis labels** are aligned to the clock, not to the slot number: label a slot when its start hour is a multiple of N (N from A3 row 2). On the repeated hour only the first copy qualifies. If a clock change removes an aligned hour, that label is simply absent. (Slot-number alignment would flip every label after the change to odd hours.)
5. **`Last hour` dates line** (section 6): when the two times are equal because the clocks went back inside the window, append ` (clocks went back)`: `02:10–02:10 (clocks went back)`. The 5-minute slot that spans the change reads by rule 1, for example `02:55–03:00`.

How the page learns this is Ender's choice (a per-slot `repeat` of 1 or 2 plus the end clock from the server, or comparing neighbouring slots' local hours). The page still computes no zone boundaries.

Test vectors, hourly, Europe/Berlin, Sun 25 Oct 2026, 24-hour clock (with an en-US OS locale the first reads `Sun, Oct 25, 2:00 AM–3:00 AM (first time)`):

| Slot starts at | Line 1 |
|---|---|
| 01:00 CEST | `Sun 25 Oct, 01:00–02:00` |
| 02:00 CEST | `Sun 25 Oct, 02:00–03:00 (first time)` |
| 02:00 CET | `Sun 25 Oct, 02:00–03:00 (second time)` |
| 03:00 CET | `Sun 25 Oct, 03:00–04:00` |

Spring, Sun 29 Mar 2026: slots `00:00–01:00`, `01:00–02:00`, `03:00–04:00`; no `02:00` slot.

### A3. Red-team of the nine screenshots

**Matches the spec (measured; no action).**

| Measure | Spec | Measured |
|---|---|---|
| Panel size | about 470 tall; inner 1150 / 550 | 1201 × 474 (inner 1155) and 595 × 473 (inner 549) |
| Chips | 32 px high, 8 px gaps | y 84–115 (32 rows); gaps x 106–113, 176–183, 271–278, 359–366, 440–447 (8 px each); selected ring 2 px `#bcd8f9`, fill `#385ea1` |
| Custom row, message | +44 px, +29 px | 474 → 518 → 547 |
| Date inputs | 176 × 32, 12 px apart | x 61–236 and 270–445, y 128–159; ring on `To` outer x 266–449, y 124–163; invalid border `#e08a7e` 2 px inside the ring |
| Plot | 44 px gutter, 8 px right pad, 144 px high | x 67–1169 (1103 px) and 67–563 (497 px); grid y 236 and 308, baseline y 380 |
| Bar width | pitch × 0.7, 2 to 48 px | 31–32 px (pitch 46.0), 13–14 px (pitch 20.7), 47–48 px with 7 bars; one comic on an 8 axis is 17 px tall |
| Tooltip (shot 02) | centred, 8 px above the bar | 224 × 60, centre x 457.5 against slot centre 457.7, 8 clear rows above the bar (301–308) |
| Tooltip, no room above (shot 08) | beside the slot, 8 px | slot ends x 137, tooltip starts x 146 (8 clear), top y 229 = wrapper top |
| Chart focus ring (shot 08) | 2 px, offset 2, unclipped | outer x 19–575, y 225–424: 4 px outside the wrapper, 19 px inside the panel edge |
| `Last hour` labels | first centred on the plot edge, `now` right-aligned | first centre x 67.0 (edge 67); `now` ends x 563 (edge 563) |
| Label centring | centred under the slot | 12 AM centre 89.5 against slot centre 90.0; `20 Tue` 145.5 against 145.8 |

**Deviations and things that get in the way.** Rows 1 to 4 and 6 amend the sections named; row 5 is latent (not visible in the shots) and measured from the widest label there.

| # | Finding and measurement | Rule |
|---|---|---|
| 1 | **Tooltip shadow dims the hovered bar** (shot 02). `0 4px 16px #000a` reaches 20 px below the box. Down the hovered bar the first row is `#98aec9` (red channel 152 of 188, 19% dark) and only reaches `#bcd8f9` at y = 330, 21 rows down. The lightness highlight is weakest at the bar's top, where the eye lands. | `#statsTip` shadow becomes `0 2px 6px #0008` (reaches 8 px, stops at the gap). Amends section 8. |
| 2 | **Week labels at 640 lose half their labels** (shot 08). Pitch is 71.0 px against a fixed 72 px threshold, so only `26 Mon`, `28 Wed`, `30 Fri`, `1 Sun` show. The widest label is 43 px; all seven would leave 28 px between neighbours. | Amends section 5 thinning. N = the smallest of 1, 2, 3, 4, 6, 12, 24, 48 with N × pitch at least **the widest label as drawn plus 16 px** (measured with `getBBox`, which the clip guard already uses); the fixed 72 px goes. Effects: the week at 640 labels all 7 days; `Today` at 640 moves from every 4th hour to every 3rd (widest label 35 px, N = 3 gives 62 px); `Today`, `All time` and the year at 1280, and the year at 640, keep today's labels. If none fits, only the first slot is labelled, as before. |
| 3 | **Focus ring crowds the unit label** (shot 08). Descenders of `Comics per day` end at y = 222; the ring's top edge is y = 225: 2 clear rows. Offset 2 plus width 2 uses up the 4 px gap. | `#statsChart` margin-top 4 px becomes **8 px** (6 clear rows). The panel grows by 4 px (478 and 477). Amends the section 3 stack table and section 13 ("starts 4 px below" becomes 8 px). |
| 4 | **Y labels sit about 2 px low.** The `8` occupies rows 234–242 (centre row 238) on a grid line at row 236; the `0` occupies rows 378–386 (centre 382) against the baseline at row 380. `dominant-baseline:central` centres the em box, not the digits. Cosmetic. | Draw y labels 2 px higher than their line (y − 2). |
| 5 | **Y labels clip from 10,000** (latent). `2,000` is 31 px wide (x 28–58) in a 36 px gutter, 5 px spare; `10,000` is about 38 px and loses about 2 px of its leading digit. Reachable on a monthly or yearly axis after a large rescan. | When `yMax` is 10,000 or more, the three y labels use compact notation: `0`, `5K`, `10K`; `0`, `10K`, `20K`; `0`, `500K`, `1M` (`Intl.NumberFormat` compact, no decimals; every mid is whole at those steps). Tooltips and the headline keep full numbers. Below 10,000 nothing changes. Amends section 7. |
| 6 | **Empty note on a range before counting began** (shot 05). Custom 1–10 Sep shows `Last update: 4:02 PM.` It is true but does not answer "why 0?". | Amends section 9 Empty: when the period is `Custom`, the total is 0 and the range ends before `first_at`, the note is `Counting began on {d MMM yyyy}.` (the format of the `All time` tooltip). Every other empty case keeps `Last update: …` / `No updates yet.` |
| 7 | **Clipped first week label** (spec gap, build behaves one way). Section 5 says the week label is "the Monday"; when the first week is cut by the range start, the build labels its first day. | Codified: a week's axis label is its first day inside the range, the Monday for every full week. Showing a Monday before the range starts would claim data the range does not cover. |

**Looked at and left as built.** The tooltip covers neighbouring bars (shot 02: box x 346–569, bottom y 300, covers the top 28 rows of the taller 9 AM bar); it is transient and `pointer-events:none`. An invalid custom range keeps the last good headline (shot 04 reads `Oct 20 – Oct 26` over inputs `10/20` and `10/19`), as section 4 says, and the message sits between them. The slot highlight `#242c3b` on `#1b202b` is about 1.2:1 and stays decoration; the lightened bar and the tooltip carry the state. Panel height 474 at 1280 and 473 at 640 is 1 px of rounding (baseline is y = 380 in both).

### A4. Screenshots I want next

Method: stub `/api/update-stats` in the browser with a hand-built payload (Playwright `page.route`); for the clock-change shots also set the browser context to `timezone_id: Europe/Berlin`. No server clock tricks. Same panel crop at 1280 and 640 unless noted. In priority order:

1. Autumn day, `Today`: 25 bars; hover the first and the second `02:00` slot; keyboard onto both; the axis labels (A2).
2. Spring day, `Today`: 23 bars; hover the `01:00–02:00` slot.
3. Long ranges: Custom 1 Jan 2021 – 31 Dec 2025 (60 monthly bars; hover first, middle, last); Sun 4 Jan 2026 – Sun 21 Feb 2027 (60 weekly bars, first slot one day); Sun 4 Jan 2026 – Sat 27 Feb 2027 (monthly); 1 Jan 2021 – 1 Jan 2026 (6 yearly bars, last clipped). Checks pitch, labels and the year tooltip.
4. Counts up to 12,000 on a monthly axis at 640 (compact y labels, no clipping), and one at 9,000 (`8,000` fits).
5. Tooltip placement at 1280: first active slot, last active slot (right clamp), the tallest bar (beside-the-slot fallback), a zero slot (8 px above the baseline).
6. Empty states: Custom range before counting began (new note); empty `Today` with `Last update:` on the same day and on an earlier day.
7. Keyboard focus rings: Tab onto the picker (a middle chip and the last chip), `From` and `To` valid, the chart at 1280.
8. States with the panel height measured: first load, a slow period change (60% opacity, `–`), a failed request (60% and the amber note), `Pick both dates.` and a 1999 date.
9. 200% zoom at the 640 window (320 CSS px, device scale factor 2): chips and the custom row wrap, nothing clipped, ring visible.
10. Details dialog open over the page, and the sticky error banner over a tooltip (layering only; Futaba's live pass can cover these two).

### A5. Acceptance changes (amends section 14)

- **Item 3 replaced:** hourly for 1 day; daily for 2 and 60 days; weekly for 61 and 414 days (the 414-day Sunday start draws 60 bars); monthly for 421 days; the 420-day pair in A1 gives monthly for the Sunday start and weekly for the Monday start; 1 Jan 2021 – 31 Dec 2025 monthly with 60 bars; 1 Jan 2021 – 1 Jan 2026 yearly with 6 bars. A range test over every start date from 2000-01-01 to today shows no result above 60 bars.
- **New:** a typed 1999 date gives `Dates before 2000 are not available.` and no request; a 400 `invalid_range` shows its message in `#statsRangeError`, never `Statistics unavailable. Retrying.`
- **New:** the A2 test vectors, for tooltip text, the keyboard announcement and the hourly axis labels.
- **New:** y labels compact from 10,000; label thinning by measured width; tooltip shadow stops at the gap; chart margin 8 px; empty-range note.
- **Item 12:** the focus ring keeps at least 6 clear rows from the unit label's glyphs.

## § Addendum 2 2026-10-26 (This month)

Owner: Judy. Classification: EXTEND of the Update statistics panel. One new period chip, `This month`; everything else stands. Request: Sergei, 2026-10-26, `Docs/ComicsMetaOrganizer_Backlog.md` § "This month" period in update statistics (the current calendar month in local time). Written against v0.4.0 (`static/index.html:9` and `:14`, `static/update-stats.js`, `update_stats.py`); no code, no commit, no app launch. Where this addendum disagrees with the sections above or with Addendum 1, this one wins; each rule names what it amends. Basis: § A new control is born with its tooltip, § Copy is short, specific, and has no memory, § No UI element may cover another; Hick's Law (seven options is the ceiling for a chip row; an eighth period would move the picker to a select).

**How the widths were measured.** Not from a screenshot of this chip (it does not exist yet). Segoe UI (the page font) at 14 px, from the font file, plus the chip box (24 px padding, 2 px border, so text + 26 px). The method reproduces the five chips in Ender's screenshots to within 2 px each: computed 83.1 / 63.7 / 86.2 / 80.5 / 73.2 against measured 83 / 62 / 87 / 80 / 73. Page geometry is from the page's own CSS: body padding 32 px (15 px at a viewport of 700 px or less), panel border 1 px plus padding 22 px; the 640 window has a 15 px scrollbar, so its viewport is 625 px and the panel's inner width 549 px (the 595 px crop in Addendum 1 minus 46). Every expected rect below is plus or minus 2 px per chip; B8 asks Ender for screenshots that replace the estimates with measurements.

### B1. Decisions in one screen

| Topic | Decision |
|---|---|
| Chip | Label `This month`, fourth of seven, between `This week` and `This year`. Radio value `month`. |
| Period | The 1st of the current month 00:00 to now, local time. Default stays `Today`; the selection is still not remembered. |
| Tooltip | `Comics updated since the 1st of this month.` |
| Bars | Daily, one per calendar day of the month: 28, 29, 30 or 31. Unit label `Comics per day`. No new unit. |
| Axis | The existing "day, more than 14 bars" labels (`1 Oct`, then day numbers) and the Addendum 1 thinning rule. Step: 2 at 1280, 3 or 4 at 640, 12 at 320 CSS px. |
| Headline | `{n} comics updated this month`; dates line `October 2026`. |
| Keyboard | Tab stops unchanged; arrow order is reading order with the new chip fourth. |
| Seven chips | One row from an inner width of 604 px. Narrower, the existing flex-wrap wraps them: at the 640 window `Custom` drops to a second row; at 200% zoom there are four rows. No CSS change needed for the wrap. |

Layout, 1280 window, 26 Oct 2026, `This month` selected (illustrative numbers: the 26 bars add up to 95, the total is 89, so the note shows; days 27 to 31 are future and inert; 31 slots, label step 2):

```
+------------------------------------------------------------------------------------------------------+
| Update statistics                                                                                    |
|                                                                                                      |
| ( Last hour ) ( Today ) ( This week ) [[ This month ]] ( This year ) ( All time ) ( Custom )         |
|                                                                                                      |
| 89  comics updated this month                                                                        |
| October 2026                                                                                         |
|                                                                                                      |
| Comics per day                                                                                       |
|   8 |                      ##                ##                   ##                                 |
|     |       ##          ## ##             ## ## ##             ## ##       ##    ##                  |
|   4 | ## ## ##          ## ## ## ##       ## ## ##          ## ## ## ##    ## ## ##                  |
|     | ## ## ## ##    ## ## ## ## ## ##    ## ## ## ## ##    ## ## ## ## ## ## ## ##                  |
|   0 +----------------------------------------------------------------------------------------------  |
|      1 Oct   3     5     7     9    11    13    15    17    19    21    23    25    27    29    31   |
|                                                                                                      |
| A comic updated in several bars counts once in the total.                                            |
+------------------------------------------------------------------------------------------------------+
  [[ ]] = selected chip. Labels follow the OS locale.
```

### B2. The chip (amends section 4 order table and section 12)

New order: 1 `Last hour`, 2 `Today` (default), 3 `This week`, **4 `This month`**, 5 `This year`, 6 `All time`, 7 `Custom`. The other six keep their labels, tooltips and behaviour. The new chip is built exactly like its neighbours, directly after `This week`:

`<label class="chip" title="Comics updated since the 1st of this month."><input class="sr-only" type="radio" name="statsPeriod" value="month" autocomplete="off">This month</label>`

| Item | Spec |
|---|---|
| Label | `This month` (sentence case, as `This week` and `This year`) |
| Tooltip (`title` on the label) | `Comics updated since the 1st of this month.` |
| Look and states | As every period chip (section 4): unselected, hover, selected (`#385ea1` fill, 2 px `#bcd8f9` ring), keyboard focus (2 px outline, offset 2). Selecting never changes the chip's box, so nothing reflows on a click. |

Tooltip copy check: one fact, names the start of the period, no history, no legality, no role names. It is a fixed string, like the other five, so there is no month-change logic to get wrong; the dates line already names the month.

### B3. Bars, axis and the new period's edge cases (amends sections 5 and 8)

Add to the section 5 table: `This month` | one bar per day, 28 to 31 | `Comics per day`. Slots are the local calendar days from the 1st to the last day of the current month. On a clock-change day the slot is 23 or 25 hours long; its label and tooltip are dates, so Addendum 1 A2 does not apply.

Geometry (plot = inner width minus 52 px; bar = 0.7 × pitch, clamped 2 to 48 px):

| Window | Inner | Plot | Pitch, 31 days / 28 days | Bar |
|---|---|---|---|---|
| 1280 | 1155 | 1103 | 35.6 / 39.4 | 24.9 / 27.6 |
| 640 | 549 | 497 | 16.0 / 17.8 | 11.2 / 12.4 |
| 200% zoom (320 CSS px) | 229 to 244 | 177 to 192 | 5.7 to 6.2 / 6.3 to 6.9 | 4.0 to 4.8 |

Axis labels: Addendum 1 A3 row 2 applies unchanged. A label is shown every N-th slot from the first, N the smallest of 1, 2, 3, 4, 6, 12, 24, 48 with N × pitch at least the widest drawn label plus 16 px. For a calendar month the widest label is always the first one, `1 {month}` at 13 px: 25.7 px (`1 Jan`) to 36.3 px (`1 Sept`), 30.8 px for `1 Oct`, so the threshold is 42 to 52 px. A day number such as `31` is 14 px wide.

| Window | N | Labelled days |
|---|---|---|
| 1280 | 2 in every month (2 × 35.6 = 71 clears 52; 1 × 39.4 does not clear 42) | `1 Oct`, 3, 5 … : 14 to 16 labels |
| 640 | 3 or 4. 28 days: 3 (53.3). 31 days: 3 for `1 Oct` (48.1 against 46.8, a 1.3 px margin), 4 for a longer first label such as `1 Aug` (50.0) | N = 3: `1 Oct`, 4, 7 … (10 or 11 labels); N = 4: 1, 5, 9 … (8 labels) |
| 200% zoom | 12 in every month and every scrollbar case (12 × 5.7 = 68 clears 52; 6 × 6.9 = 41 does not clear the narrowest threshold, 42) | `1 Oct`, 13, 25 |

Ender does not hard-code N; the rule picks it. Because the 640 case sits within measurement error of N = 3 versus 4 for some months, Futaba checks the rule on screen (N × pitch at least the widest drawn label plus 16, no label clipped), not a fixed N. Thinning starts at the first slot, so 1280 labels odd days and 640 labels 1, 4, 7 or 1, 5, 9; a 30-day Custom range already behaves this way and it stays as is.

Slot rules, section 5 extended:

- **Future days** (after today) draw no bar, no highlight and no tooltip, and the arrow keys skip them. The axis spans the whole month, so bars do not move as the month goes on.
- **Today's slot** is drawn like any other; its tooltip adds `so far` (`Mon 26 Oct 2026` / `6 comics so far`). Line 1 for every slot is the section 8 day format.
- **Midnight roll** (amends section 5): the list is now `Today`, `This week`, `This month`, `This year`. At midnight on the 1st the next refresh switches the chart to the new month (headline, dates line, bar count, axis) with no user action.
- **First days of a month.** Early on the 1st the total is often `0`: the normal Empty state (section 9) shows `0`, the axes, one active slot and `Last update: {when}.`. On the first days of a month `This month` can be lower than `This week` (a week from Mon 26 Oct to Sun 1 Nov counts October days that the new month does not). Both are right; neither is a defect.
- **Bars versus total** (section 8): unchanged. Daily bars add up to more than the total when a comic was updated on two days, and the note `A comic updated in several bars counts once in the total.` shows then.

### B4. Headline, dates line, announcements (amends section 6)

| Period | Label after the number | Dates line |
|---|---|---|
| This month | `comics updated this month` | `October 2026` (`{month:'long', year:'numeric'}`, OS locale) |

Singular `1 comic updated this month`, zero `0 comics updated this month`. The headline block's `title` is unchanged. Chart `aria-label`: `Comics per day, this month. Left and right arrows read each bar.` On a period change the headline sentence goes to `#statsAnnounce`, as for every period.

Why a month name and not the span `1 Oct – 31 Oct 2026`: a calendar month is a named period, like `This year` with `2026`; the span repeats what the label and the bars already say, and `October 2026` is the same string the month-bar tooltip uses. At 200% zoom the headline row may wrap its label under the number (`63` + `comics updated this month` is 233 px against 229 to 237 px inner); the row is already flex-wrap and `comics updated in the last hour` (223 px) behaves the same, so nothing new.

### B5. Keyboard order (sections 4 and 8 unchanged except as listed)

- **Tab order is unchanged:** picker (one stop, on the checked chip), then From, then To (only when `Custom` is shown), then the chart.
- **Arrows in the picker** move and select in DOM order, which is reading order: Last hour, Today, This week, This month, This year, All time, Custom. Right and Down step forward, Left and Up step back, wrapping from `Custom` to `Last hour` (native radio group). Up and Down step like Left and Right; they do not jump between wrapped rows. Each step selects and requests that period; the latest selection wins (section 9). From `This week`, one press of Right now reaches `This month`.
- **Focus ring:** unchanged, 2 px at offset 2. At 8 px chip spacing the ring leaves 4 px clear to the next chip, across a row and between rows.
- **Chart:** unchanged. Tab in lands on today; `Home` is day 1, `End` is today, the left and right arrows skip future days.

### B6. Do seven chips fit? (amends the "all six fit" sentence in section 4)

Box widths (text at 14 px + 26 px):

| Chip | Last hour | Today | This week | This month | This year | All time | Custom |
|---|---|---|---|---|---|---|---|
| Computed, px | 83.1 | 63.7 | 86.2 | 95.3 | 80.5 | 73.2 | 73.5 |
| Measured in Ender's screenshots | 83 | 62 | 87 | not built yet | 80 | 73 | not built yet |

The rects in B7 use the measured width where there is one and the computed width (rounded) for `This month` and `Custom`. Six chips with five 8 px gaps: 500 px, which is why six fitted at 640. Seven chips with six gaps: **603 px**.

| Where | Inner width | Seven in one row? | Rows |
|---|---|---|---|
| 1280 window | 1155 | Yes, 552 px spare | 1 |
| 700 px window | 609 | Borderline, about 6 px spare, within measurement error; not asserted | 1 or 2 |
| 640 window (the minimum) | 549 | **No**, 54 px short. Row 1 holds six chips (520 px, 28 px spare); `Custom` needs 82 px | 2: six chips, then `Custom` |
| 200% zoom, 640 window (320 CSS px) | 229 to 237 (scrollbar 15 or 7.5 CSS px) | No | 4: `Last hour` `Today` / `This week` `This month` / `This year` `All time` / `Custom` |

640 window (inner 549 px), `This month` selected:

```
| ( Last hour ) ( Today ) ( This week ) [[ This month ]] ( This year ) ( All time )    |
| ( Custom )                                                                           |
| From [ date ]  To [ date ]      <- only when Custom is selected, 12 px below row 2   |
```

200% zoom (320 CSS px, inner about 236 px), `This month` selected:

```
| ( Last hour ) ( Today )          |
| ( This week ) [[ This month ]]   |
| ( This year ) ( All time )       |
| ( Custom )                       |
```

The seven chips share one row from an inner width of about 604 px: a window of about 695 to 715 px, and 730 px and wider. Between 716 and 728 px the page's own 700 px breakpoint (body padding 15 px to 32 px) takes 34 px back and the row wraps once more; it is an existing page rule and the wrap rule below covers it. At 200% zoom the third row is 243 px against 244 px available if the scrollbar is zero thickness, so a 3-row result (`This year` `All time` `Custom`) is possible there; 3 or 4 rows are both accepted.

**Wrap rule (every width, no breakpoints):**

1. `#statsPeriod` keeps `display:flex; flex-wrap:wrap; gap:8px` (already built). The wrap needs no new CSS.
2. Chips keep their natural width. No `flex-grow`, no equal-width columns, no change of padding or font at narrow widths: the target stays 32 px high (24 px is the WCAG 2.5.8 minimum) and the label stays whole. Rows are left-aligned.
3. Reading order equals DOM order. No `order:` rearranging, no balancing of rows; a chip moves to the next row when it would overflow, so at 640 `Custom` is alone on row 2, directly above the From/To row it opens (12 px below it).
4. 8 px between chips in a row and 8 px between rows (row step 40 px).
5. **Height** (amends the section 3 height rule): each extra chip row adds 40 px (32 + 8) to the panel. This depends on window width only, never on the period, the data or a state. The old statement that only the custom row and its message change the height holds at any one width. Expected: 640 window about 517 px (477 + 40); 200% zoom, about 120 px more than a single row.
6. Nothing is clipped: chips are in-flow, `max-width:100%` as built.

Rejected: abbreviating labels (`Mon`, `Yr`) loses meaning; shrinking padding to about 9 px would only just fit 640 and fails at 200% zoom anyway; a select below some width swaps the control by window size.

### B7. Nothing covers anything (amends section 13)

All chips are in-flow flex items. The only positioned things are each chip's hidden 1 × 1 px radio, inside its own label, and `#statsTip` (unchanged). Expected rects, crop coordinates as in Addendum 1 (panel inner left x = 23, chip row top y = 84; plus or minus 2 px per chip):

| Window | Chip rects (x range, all 32 px high) |
|---|---|
| 1280, one row, y 84 to 115 | Last hour 23–105, Today 114–175, This week 184–270, This month 279–373, This year 382–461, All time 470–542, Custom 551–624 |
| 640, row 1 at y 84 to 115 | the same six chips, Last hour to All time (23–542); right edge of the inner box x = 571 |
| 640, row 2 at y 124 to 155 | Custom 23–96 |
| 200% zoom, CSS px, rows at y 84, 124, 164, 204 | row 1: 23–105, 114–175. Row 2: 23–109, 118–212. Row 3: 23–102, 111–183. Row 4: 23–96 |

What Futaba measures (relations first, absolute x second): no two chips overlap; horizontal and vertical gaps are exactly 8 px; row step is 40 px; every chip is 32 px high; each chip's width is within 2 px of the B6 table; reading order is the B2 order; the focus ring (outer edge 4 px outside the chip) is fully visible, unclipped by the panel, and touches no neighbouring chip; selecting any chip changes no chip's rect; the chart wrapper starts 8 px below the unit label (Addendum 1 A3 row 3) at every width; the panel's height changes between windows only by multiples of 40 px. States: `This month` selected at 640, 700, 1000, 1280 and 200% zoom; `Custom` selected (the From/To row moves with the chips); loading, empty and error states with the seven-chip row; Details dialog open.

### B8. What the server needs and the screenshots I want next

Facts, names are Ender's: a `month` period; the resolved unit is `day`; slots are the local calendar days from the 1st 00:00 to the 1st of the next month, `[start, end, count]`, future days inactive as for `week`; the window ends now; the distinct total counts comics updated from the 1st 00:00 to now, its own query. `first_at`, `last_at` unchanged. The page learns the label, aria phrase and tooltip from this addendum; no other new string exists.

Screenshots, same stub method as A4 (`page.route` on `/api/update-stats`), panel crop, priority order:

1. `This month` selected, 31 bars with a few future days, at 1280 and 640: hover on today and on an earlier day (tooltip `so far`; axis step).
2. The picker at 200% zoom (320 CSS px, device scale factor 2) with a keyboard focus ring on the second and the last chip; the 640 window with the focus ring on `Custom`.
3. The 1st of a month with zero comics: `0`, `Last update:`, one active slot.
4. February with 29 bars (Feb 2028) at 640, for the axis step and bar width.

### B9. Acceptance (amends section 14)

1. Chip row: seven chips in the B2 order; `Today` still the default and selected on load; the six old chips unchanged.
2. `This month`: tooltip string exactly as B2; headline `{n} comics updated this month` (`1 comic`, `0 comics`); dates line `October 2026` in the OS locale; unit `Comics per day`; bar count equals the days in the month (fixtures: Feb 2026 28, Feb 2028 29, Apr 2026 30, Oct 2026 31); future days empty and inert; today's tooltip ends `so far`; chart `aria-label` as B4.
3. Axis: labels follow the Addendum 1 rule at 1280, 640 and 200% zoom (B3: 2, 3 or 4, 12); no label clipped; the first label carries the month.
4. First of the month: `0` with `Last update:`; midnight roll from the 30th or 31st to the 1st switches the chart without action; `This month` below `This week` on a week that spans two months is accepted.
5. Keyboard: Tab stops unchanged; arrows step through the seven chips in DOM order and wrap; Up and Down step like Left and Right; focus ring visible and unclipped.
6. Fit and wrap: B6 and B7 measured at 640 (two rows), 1280 (one row) and 200% zoom (3 or 4 rows); the panel height changes only by 40 px per row; no overlap in any state listed in B7.
7. Existing behaviour: `All time` and `Custom` (including the From/To row) work as before; section 14 items 1 to 12 still hold with six replaced by seven.

### Questions for Sergei

None.
