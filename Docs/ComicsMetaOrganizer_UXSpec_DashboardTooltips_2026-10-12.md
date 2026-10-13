# Dashboard tooltips — audit of existing bare controls

Date: 2026-10-12. Owner: Judy. Status: reviewable draft; Sully commits this exact file before Ender is briefed. No code, no commit, no running-service contact was part of writing it. Source of the request: Sergei 2026-10-12 (A10 in `ComicsMetaOrganizer_UXSpec_DesktopShell_2026-10-12.md`).

Classification: EXTEND of `static/index.html` (attributes, and one small helper for the controls whose text changes). This is the schedulable audit that ProcessRules § A new control is born with its tooltip allows for controls that already exist. Controls added later, including the shell's banner and `Check for updates` button, carry their own tooltips in their creating commit and are specified in the DesktopShell spec, not here.

## Count and method

Measured on the working-tree `static/index.html` (29,538 bytes, 2026-10-12). Method, repeatable by Futaba: list every `<button>`, `<input>`, `<select>` and `<summary>` in the file, plus every `node('button', …)` and `node('summary', …)` creator in its script, then check each for a `title`.

| Group | Count |
|---|---|
| Static controls with an id: 13 buttons, 4 inputs, 1 select | 18 |
| Static `<summary>` (Stage timing, Previous write batches, Manual scan controls) | 3 |
| Dynamic creators (row `Details`, row `Folder`, row `File location`, candidate `Select`) | 4 |
| Interactive controls in total | 25 |
| Already covered (Google Lens button, Yandex button, each with its own state-aware tooltip) | 2 |
| **Bare, specified below** | **23** |

The version badge `#appVersion` already has a title and is not interactive. Native `<option>` items get no tooltip: the select's own tooltip and the option text cover them. The two verification buttons keep their existing mechanism untouched.

The table holds 26 base strings (the Pause button has three, the candidate `Select` has two) and 3 disabled-state strings, 29 in all.

## Mechanism

1. **Static controls:** a `title` attribute in `index.html`.
2. **Controls whose text depends on state or context:** one helper, `tip(element, text)`, that sets `title` only when the value differs (the same write-on-change habit as `set()` in `lens-control.js`). Call it wherever the label or disabled state changes.
3. **Write only on change, including the existing label.** `renderControl` rewrites `#pauseControl`'s text on every 2 s poll. Replacing a button's text node while the pointer rests on it can dismiss or restart its tooltip, so the label write also becomes write-on-change. Futaba rests the pointer on the Pause button for 10 s to confirm the tooltip stays.
4. **No screen-reader duplicate spans.** The Lens and Yandex buttons mirror their tooltip into a hidden span. For controls that already have their own name (visible text or `aria-label`), the browser exposes `title` as the accessible description, so the span is not needed. Futaba confirms in the accessibility tree for one control of each kind: button, input, select, summary.
5. **Delivery limit, same as today's tooltips:** the native tooltip appears on mouse hover after a short delay and not on keyboard focus. Labels stay the primary name for everyone. The tooltip is browser-drawn, so it is the sanctioned overlay class, not a covered element.
6. **Disabled controls:** where a disabled state has its own reason, the tooltip says it. This relies on the browser showing a tooltip on a disabled button, which the Lens and Yandex buttons already depend on; Futaba confirms.

## Tooltips by control (page order)

Every string follows ProcessRules § Copy is short, specific, and has no memory. Reuses the dashboard's own words ("live library", "inventory", "Gemma", "verified writes").

### Header

| # | Control | State | Tooltip |
|---|---|---|---|
| 1 | `#pauseControl` `Pause & release GPU` | Running | `Finish the current operation, then pause and release Gemma from the GPU.` |
| 2 | `#pauseControl` `Resume processing` | Pausing (request made, not yet paused) | `Cancel the pause and keep processing.` |
| 3 | `#pauseControl` `Resume processing` | Paused | `Allow new lookups and comic writes to start again.` |

Row 2 depends on the service accepting a resume while it is still pausing (the dashboard already sends one). Ender confirms; if it is refused, tell Judy and the button's pausing state is re-specced instead.

### Live enrichment progress panel

| # | Control | Tooltip |
|---|---|---|
| 4 | `Stage timing` (summary) | `Show average and total time per processing stage.` |
| 5 | `Previous write batches` (summary) | `Show completed write batches and their verified write counts.` |

### Live library panel

| # | Control | State | Tooltip |
|---|---|---|---|
| 6 | `Manual scan controls` (summary) | | `Show controls to scan a folder or rescan the live library.` |
| 7 | `#root` (Library folder) | | `Full path of the folder to scan.` |
| 8 | `#scan` `Scan folder` | Ready | `Scan the folder in the box and add its comics to the inventory.` |
| 9 | `#rescan` `Rescan live library` | Ready | `Check all live library folders again for new or changed comics.` |
| | `#scan` and `#rescan` | Disabled (a scan is running) | `A scan is already running.` |

### Collection panel

| # | Control | Tooltip |
|---|---|---|
| 10 | `#query` (Search collection) | `Part of a filename or series name. Press Enter to search.` |
| 11 | `#status` (Metadata status) | `Show only comics with this metadata status.` |
| 12 | `#filter` `Search` | `Search with this text and status.` |
| 13 | `#corruptedCount` `Corrupted · {n}` | `Show only corrupted comics. They need reacquiring.` |
| 14 | `#conversionCount` `Needs conversion · {n}` | `Show only comics in an unsupported archive format. They need converting.` |
| 15 | Row `Details` | `Show this comic's metadata and look up a match.` |
| 16 | Row `Folder` | `Open the folder that contains this comic.` |
| 17 | Row `File location` (summary) | `Show where this comic is on disk.` |
| 18 | `#previous` `Previous` | `Show the previous 100 files.` |
| 19 | `#next` `Next` | `Show the next 100 files.` |

Rows 18 and 19: the 100 is the page size already used by the paging code (`offset ± 100`); Ender reads it from that constant rather than typing it twice. Their disabled states (first and last page) keep the same tooltip: the reason is self-evident.

### Comic details dialog

| # | Control | State | Tooltip |
|---|---|---|---|
| 20 | `#close` `Close` | | `Close without writing metadata.` |
| 21 | `#series` (Series search) | | `Series name to search for.` |
| 22 | `#number` (Issue number) | | `Issue number. Leave empty to list up to 100 issues.` |
| 23 | `#lookup` `Find series` | Ready | `Search ComicVine for this series.` |
| | `#lookup` | Disabled (searching) | `Searching. New requests may take 20 seconds or more.` |
| 24 | Candidate `Select`, series stage | | `Choose this series and list its issues.` |
| 25 | Candidate `Select`, issue stage | | `Show this issue's metadata for review. Nothing is written yet.` |
| 26 | `#apply` `Approve issue and write metadata` | Ready | `Write the metadata shown into the comic file. Only empty fields are filled.` |
| | `#apply` | Disabled (writing) | `Writing. Large comics can take a while.` |

- Rows 24 and 25 share one `card()` builder, which today does not know which stage it serves. Ender passes the tooltip in from the caller.
- Row 26 keeps the visible hint above it (`Only empty fields will be filled…`); the tooltip repeats the one fact that matters at the moment of the click.
- Row 23's disabled text matches the line the dialog already shows (`Searching; new requests may take 20 seconds or more.`), so the two say the same thing.

## Notes for Ender

- Order of work: 18 static controls have a fixed string and take a plain attribute (rows 4–7, 10–14, 18–19, 20–22, and the Ready texts of 8, 9, 23 and 26). The rest go through `tip()` or the row builders: the Pause button (rows 1–3, one more static control, which makes 19 static in all), the three disabled texts, rows 15–17 and rows 24–25 (the 4 dynamic creators).
- Row buttons are rebuilt whenever the list changes (`replaceChildren`), so their tooltips are set at creation, which is enough.
- Do not touch `#browserResume` or `#yandexVerification` (already covered) or `#appVersion`.

## Acceptance (Futaba)

- Re-run the count method: 23 formerly bare controls each have a non-empty `title` that matches this table exactly, character for character; the two verification buttons are unchanged.
- Hover each control in the Electron window and in a plain browser: the tooltip shows in full, not clipped, at 640 px width and at 200% zoom.
- State changes: the Pause button's tooltip follows Running, Pausing and Paused (rows 1–3); the disabled texts appear while a scan, a search and a write run, and revert afterwards.
- Pointer rests 10 s on the Pause button: the tooltip is not dismissed or restarted by the 2 s poll.
- Accessibility tree: for one button, one input, one select and one summary, the accessible description equals the tooltip.
- Report measured values (the tooltip text read from the DOM), not impressions.

## Observed while auditing (not changed here)

The status filter's second option appears malformed in `index.html`: `<option value="">All files</option value="missing">No embedded metadata</option>`. The first option is closed by a stray `</option value="missing">`, so the `No embedded metadata` choice (`value="missing"`) is probably missing from the rendered dropdown. Read from the source only; not confirmed in a rendered page. Offered, not fixed: Ender or Futaba can confirm it in the live dropdown. It does not affect any tooltip above.

Basis: ProcessRules § Desktop App / GUI Rules (a new control is born with its tooltip; copy is short, specific, and has no memory); NN/g recognition over recall and help and documentation; WCAG 2.2 AA 4.1.2 name, role, value (the description is exposed, the label stays the name) and 1.4.13, whose hover exception covers browser-drawn tooltips.

Exclusions: UI code, git and release operations, edits to any other file, the running service, Ender's concurrent code changes, the shell's own controls (DesktopShell spec), keyboard-focus tooltips (a custom tooltip widget is not proposed: it would add a second mechanism for 23 controls).
