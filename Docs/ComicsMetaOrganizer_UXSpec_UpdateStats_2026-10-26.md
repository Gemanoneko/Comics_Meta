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
