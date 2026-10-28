# GCD offline index — UX spec for 0.6.0

Date: 2026-10-28. Owner: Judy. Status: implementation-ready; amended within this same pass with Sergei's **14-day reminder and download guidance** ruling. **EXTEND** the current dashboard; preserve every other panel, control, matching rule and shell flow. The initial spec was the prerequisite handoff; this amendment rides the next code/bump commit, with no second doc-only commit. No code changes, builds, app launches, UI automation or library/profile access were part of this pass.

Inputs: `ComicsMetaOrganizer_GCDOffline_UIBrief_2026-10-27.md`; Backlog § GCD data dump as an offline source, including the latest reversals; current `static/index.html` and `static/shell-ui.js`. The later Backlog rulings bind: allow same-name series one year off; GCD may replace a cover-read Publisher; skip Star Wars Legends Marvel reissues; filename `(of N)` wins. This panel adds no matching settings or per-comic controls.

Basis: Fluent native file selection; NN/g visibility of status, error recovery and user control; Hick's Law (one file, one preview, one build action); WCAG 2.2 AA. Apply ProcessRules § Lean verification, including item 7: this is the one batched Judy pass. Its prerequisite spec commit is the stated exception to doc-only commit rounds.

## 1. Placement and layout

Add a full-width `.panel` **after Live library and before the collection search/table**. Inside it use a native disclosure with a 40 px minimum-height summary: **GCD offline** (20 px heading) followed by a 14 px status. Keep the native disclosure marker. The complete summary is the target; its text wraps in normal flow.

First status render: open for no index, an active build or an undismissed failed/interrupted attempt; closed for ready. Thereafter respect the user's open/closed choice. Choosing a file opens it. Polling never opens it or moves focus. Progress and effective source availability remain visible in the summary when closed.

Expanded content order:

1. Effective index details, or the empty-state sentence.
2. Current operation: preview, build progress or last-attempt notice, when applicable.
3. Actions for that state.
4. Download/replacement guidance and attribution links (section 3a).

```text
▾ GCD offline                         Ready · dump 16 Oct 2026

Dump       16 Oct 2026 · 12 days old    Built      28 Oct 2026, 10:42
Last file  current.zip

[ Choose GCD file ]

▸ How to download and replace
Grand Comics Database · CC BY-SA 4.0
```

Reuse `.panel`: 22 px padding, 14 px radius, existing fill/border and 20 px bottom margin. Expanded body starts 16 px below the summary; 12 px between related rows, 16 px before actions. Body text and values: 14 px/1.5; labels muted. Use a two-column definition grid when space permits and one column below 600 px of **panel content width**. Actions wrap with 8 px gaps. No fixed body height, absolute positioning, ellipsis or horizontal scrolling. Long filenames and paths wrap anywhere and remain selectable. Show the last filename, not a full path, in ready state; show the full selected path in preview.

Use existing dark theme only; there is no light theme in this dashboard. Text `#e7eaf1`, muted `#aab4c6`, warning/error `#ffd697`, panel `#1b202b`. New controls: minimum 32 px high, 14 px text, 4 px 12 px padding, 8 px radius, border `#aab4c6`; primary fill `#385ea1`/text `#eef2fb`, secondary fill `#242c3b`. Keep primary fill on hover and add an inset 1 px `#bcd8f9` outline. All controls get a 2 px `#bcd8f9` focus outline, offset 2 px. No meaning depends on colour.

Contrast calculated from sRGB values: body/panel 13.54:1; muted/panel 7.80:1; primary text/fill 5.70:1; warning/panel 11.89:1; focus/panel 11.12:1; progress fill `#bcd8f9` against track `#242c3b` 9.56:1. These are token calculations, not a claim that rendered hit areas have been verified.

## 2. State and copy contract

`GET /api/gcd-offline` is the source of truth. Keep the effective index separate from the latest attempt: a failed new build must never replace a ready old index with an unavailable label.

| State | Summary status | Expanded content and actions |
|---|---|---|
| Initial status loading | `Checking…` | `Checking GCD index…` No build action until status is known. |
| No index | `No index` | `No GCD index yet. Choose a GCD SQLite .zip or extracted .db.` **Choose GCD file**. |
| Ready | `Ready · dump {date}` | Dump date and age, built date/time, last filename. **Choose GCD file**. Omit optional series/issue counts. |
| Inspecting selection | `Checking file…` | Keep effective-index details; `Checking {filename}…` and **Cancel**. No build has started. |
| Valid preview | `File ready to build` | Section 3. Keep effective-index details visible above the candidate. |
| Building, old index present | `Updating · {overall}%` | Section 4; `Matching uses dump {current date}.` |
| Building, no index | `Building · {overall}%` | Section 4; `GCD matching starts when the index is ready.` |
| Cancel requested | `Cancelling…` | Keep progress and effective-index sentence. **Cancelling…**, unavailable until terminal result. |
| Success | `Ready · dump {new date}` | Replace effective details from server. Polite one-time notice: `GCD index ready. Comics missed by the earlier index will be checked again.` On first index: `GCD index ready.` **Choose GCD file**. |
| Cancelled | ready/no-index summary | Neutral one-time notice `GCD update cancelled.` Keep effective details. **Choose GCD file**, **Dismiss**. |
| Failed/interrupted | `Ready · update failed` if an index exists, otherwise `No index · update failed` | Error from section 5; effective details remain. If ready: `Matching uses dump {date}.` Otherwise: `GCD matching is unavailable until an index is built.` **Choose GCD file**, **Dismiss**. |
| Status request unavailable | `Status unavailable` | `Could not check GCD status. Try again.` **Try again**. If retaining details, label them `Last known index` and freeze progress with `Last checked {time}`. Disable starting another build until status is recovered. |

Dates use the OS locale with an unambiguous month/year; built time is local and includes the date. Age: `1 day old` / `{n} days old`; missing age/date is `Unknown`, never zero or today's date. Summary and source line use dump date, never build date. No automatic toast, notification, focus change or sound on completion.

**14-day reminder (Sergei-approved):** when the effective dump's engine-reported age is **14 days or more**, show the in-flow warning `This dump is {age} days old. Download a newer SQLite dump when available.` above the existing choose action. Put the **Download SQLite dump** link immediately below the warning, using the destination in section 3a, and show its expanded instructions on first render. This is the same download link as in the help block, not a second duplicate. Age stays visible regardless. No reminder for unknown age or no index. It does not disable matching or change Ready to an error; dismissal of an attempt notice does not hide it. Rebuilding the same dated dump does not reset its age. No new threshold setting or reminder-dismiss control.

## 3. Picker, preview and rebuilding

**Choose GCD file** opens one native file picker, title **Choose GCD dump**, starting in Downloads. Accept a single `.zip` or `.db`; filter label **GCD SQLite dump (*.zip; *.db)**. The app reads the selected file and keeps it. Cancelling the picker leaves the current panel/preview unchanged.

If the desktop picker is absent or fails, reveal an in-flow text field labelled **GCD file path**, helper `Full path to a GCD .zip or .db on this computer.`, and **Check file**. Use a text field, not an HTML upload: the engine needs a local path. Field min-width 0, width 100%, 32 px minimum height. This fallback invokes the same inspect/preview flow.

Every selection calls `/inspect` before `/build`. The preview is in-flow, with no modal:

```text
Build GCD index?
File       C:\Users\…\Downloads\current.zip     [full actual path, wrapping]
Dump       28 Oct 2026
File size  {size}
Disk space {needed} needed · {free} free on {drive}
Usually 2–3 minutes. The selected file is kept.
[ Build index ] [ Choose another file ] [ Cancel ]
```

Label the old effective record **Current index** and this block **Selected file** when both exist. The disk row uses inspected values and the actual index drive, with explicit units; never hard-code 7.5 GB or assume C:. Inspection alone changes nothing. Insufficient space or an invalid file suppresses the build action and shows the mapped error plus **Choose another file** and **Cancel**. Cancel dismisses selection/preview, restores ready/empty state and returns focus to Choose GCD file. A cancelled inspection ignores its eventual response.

| Inspection result | Preview heading / extra sentence | Primary action |
|---|---|---|
| First/newer dump | `Build GCD index?` | **Build index**; normal build, `force=false`. |
| Same dump | `Rebuild GCD index?` / `This dump is already in use.` | **Rebuild index**; intentional `force=true`. |
| Older dump | `Use older GCD dump?` / `This replaces the index dated {current date} with {selected date}.` | **Use older dump**; intentional `force=true`. |

The preview is the confirmation; no extra confirmation dialog or checkbox. Retain disk information and the effective-index sentence in all three variants. Rebuilding is available only by choosing a file and accepting its explicit preview; no persistent force toggle. If `/build` finds `same_dump` or `older_dump` after a normal preview, refresh inspection and require the corresponding explicit action. Never retry with force automatically.

Submit once; keep the pressed control focused with `aria-disabled=true` while awaiting the start result, and ignore repeats. Then show server progress. If the start response is lost, read status before allowing another start; never submit a second build to discover whether the first began. `busy` attaches to the running update and says `A GCD update is running. Showing its progress.`

## 3a. Download and replacement guidance

Keep the **Download SQLite dump** link visible in the expanded GCD panel in every non-busy state, directly above a native disclosure **How to download and replace**. At age 14+ the link sits directly below the reminder instead, with the disclosure/instructions following the actions. It opens `https://www.comics.org/download/` through existing external-link handling, only on activation; no automatic download or account action. The disclosure opens on first render with no index or at age 14+, and is otherwise closed. Thereafter respect the user's choice; passive polling never opens it or takes focus. Same text in all states, normal flow, 14 px/1.5 and 12 px row gaps; no modal.

Exact in-app instruction copy, as a short numbered list:

1. `Open Download SQLite dump and sign in to your comics.org account. If you need an account, use the site's registration link.`
2. `On the Downloads page, check the SQLite date under Data last updated. Private use is an optional purpose; the usage description is optional too.`
3. `Read the licensing terms and tick the acceptance checkbox, then press Download SQLite Dump.`
4. `Save the ZIP to Downloads and wait for the download to finish. Keep it zipped; no extraction is needed. If the name is already taken, give the new ZIP a dated name so you can keep both files.`
5. `Here, press Choose GCD file and select the downloaded ZIP. Check its dump date and disk space, then press Build index.`
6. `Wait for Ready with the newer dump date. Matching uses the current index until the new one is ready.`

After the list, show these two short paragraphs:

`You do not need to delete the old download. After the newer index shows Ready, you may delete the old ZIP yourself to free space.`

`The app stores its index separately and never changes or deletes your ZIP or extracted database. Keep a downloaded file if you want to rebuild from that exact dump later.`

The required format is **SQLite inside a ZIP**; a particular filename is not required. The official download handler returns `current.zip` even when the SQLite button is used, and a browser may rename it. An already extracted `.db` remains accepted as in section 3. Keep the full source file throughout inspection/build; Ready means ongoing matching no longer needs it. Ender confirmed the source is opened read-only/copied to owned staging, and the active trimmed index is independent after the pointer swap. No app-side delete button or automatic deletion.

**Primary evidence, checked 2026-10-28:** the live downloads page returned HTTP 403 to research access, so the exact labels above were verified in GCD's own website source at commit `7ebbe62a07fec1ee022c058922600817f0e59ce1`, rather than inferred from third-party instructions:

- [Download template](https://github.com/GrandComicsDatabase/gcd-django/blob/7ebbe62a07fec1ee022c058922600817f0e59ce1/apps/stats/templates/stats/download.html): Downloads, Data last updated, SQLite and Download SQLite Dump. The old explanatory prose mentions MySQL alone, but the actual form has a dedicated SQLite submit button; guide users by that button.
- [Download form](https://github.com/GrandComicsDatabase/gcd-django/blob/7ebbe62a07fec1ee022c058922600817f0e59ce1/apps/stats/forms.py): Private use and usage are optional; licence/credit acceptance is required.
- [Download handler](https://github.com/GrandComicsDatabase/gcd-django/blob/7ebbe62a07fec1ee022c058922600817f0e59ce1/apps/stats/views.py): login required; SQLite selection uses the SQLite dump; ZIP response is named current.zip.
- [Official setup guide](https://github.com/GrandComicsDatabase/gcd-django/blob/beta/docs/development/CORE_SETUP.md#full-gcd-catalog-dump): manual download from comics.org/download after accepting the terms. Its developer setup commands are not instructions for this app and do not appear in the product.

## 4. Build progress and cancellation

One 8 px native progress bar for **Overall progress**, width 100%, followed by `Overall {n}% · Elapsed {m:ss}`. Above it: `{stage number} of 6 · {stage label}` and `Stage {n}%`. Stage names, in order:

1. `Checking file`
2. `Unpacking`
3. `Reading series and issues`
4. `Reading credits and synopses`
5. `Checking index`
6. `Switching index`

Use actual engine percentages; unknown stage progress says `Stage progress unavailable`, and unknown overall progress uses an indeterminate bar with `Overall progress unavailable`. Never infer one-sixth per stage or show 100% before the index is in use. Elapsed time is engine time, tabular numerals; no countdown or promised completion time. For an extracted database, follow actual engine stages without pretending unpacking took place.

**Cancel update** is the only action during a build. On click, request `/cancel` once; show `Cancelling…` and `Waiting for the update to stop.` Keep that button in place, unavailable. Terminal cancelled returns to ready/empty with the neutral notice. Do not say temporary files are removed until the server confirms cancellation/cleanup. A rejected cancel restores the truthful running state and displays `Could not cancel the update. Try again.` During the atomic switching stage, the action is unavailable with label **Finishing update…**; completion may win a cancel race and must then show success. No false cancelled state.

No new library pause, quit or app-update controls. Preserve the existing shell behavior. Returning to the dashboard reconnects to the running build; it never restarts it. A build interrupted by a real shutdown is shown using `interrupted` on next status load.

## 5. Errors and recovery

Show errors in this panel next to the affected operation, never in the dashboard's global sticky error. Error text is at most two sentences; a separate effective-index sentence from section 2 identifies what remains usable. Preserve candidate details where valid. An unexpected detail is plain wrapping text, never HTML, a traceback, local credentials or internal implementation names.

| Code | Exact user copy / action |
|---|---|
| `zip_missing` | `The selected file cannot be read. Choose it again or select another GCD file.` |
| `not_a_zip` | For a rejected archive: `This file is not a ZIP archive. Choose a GCD SQLite .zip or extracted .db.` An accepted `.db` must bypass this archive-only error. |
| `not_gcd_dump` | `This file does not contain one GCD SQLite database. Choose the SQLite download from GCD.` |
| `schema_unsupported` | `This GCD database format is not supported. Check for an app update, then try again.` Keep existing index; do not offer force. |
| `disk_space` | `{drive} has {free} free; {needed} is needed. Free space on that drive, then check the file again.` Include units on both amounts; **Check file again** reruns inspect. |
| `same_dump` / `older_dump` | The explicit preview variants in section 3, rather than a failure banner. |
| `busy` | Attach to running progress; copy in section 3. No second build action. |
| `cancelled` | Neutral outcome in section 2; no error colour or alert. |
| `interrupted` | `The GCD update was interrupted. Choose the file again to rebuild the index.` |
| `build_failed` | `The GCD index could not be built. Choose the file again to retry.` Optional safe detail below; keep it short and wrapping. |
| Picker failure | `Could not open the file picker. Enter the file path below.` Show fallback from section 3. |
| Inspect request failure | `Could not check this file. Try again.` **Check file again**; no build action. |

Dismiss removes only that attempt's notice, never the index. Key dismissal to the attempt identity so normal polls do not resurrect it during the session. Starting a new inspection clears the dismissed/replaced attempt's copy. Do not repeatedly announce unchanged errors.

## 6. Source status and attribution

Extend the existing `providerStatus` line with exactly one **GCD offline** entry. Preserve other source entries and separators; do not relabel an online GCD connector as offline or render duplicate offline entries.

| Effective state | Source-line text |
|---|---|
| Ready | `GCD offline: Ready (dump {date})` |
| Building with usable index | `GCD offline: Ready (dump {date}); updating {n}%` |
| Building without index | `GCD offline: Building {n}%; no index yet` |
| No index | `GCD offline: No index` |
| Failed attempt with index | `GCD offline: Ready (dump {date}); update failed` |
| Failed attempt without index | `GCD offline: No index; update failed` |
| Unknown status | `GCD offline: Status unavailable` |

Use `updating` / `Building` without a number if progress is unknown; use `cancelling` while requested. The panel has the detailed recovery copy; this line stays short and is plain text.

The download link and instructions are in section 3a. Panel attribution footer links: **Grand Comics Database** → `https://www.comics.org/`; **CC BY-SA 4.0** → `https://creativecommons.org/licenses/by-sa/4.0/`. Use existing external-link handling, only on activation. Each link, including Download SQLite dump, gets a minimum 24 px hit height and visible focus. For comics using GCD data, retain the existing Notes credit, CC BY-SA 4.0 and actual GCD issue URL; do not substitute the download URL or local file path. No new per-comic UI.

## 7. Tooltips, focus and lean acceptance

Every new control has a tooltip at introduction; use the same text as an accessible description where needed.

| Control | Tooltip |
|---|---|
| Disclosure summary | `Show or hide the GCD index details and update controls.` |
| How to download and replace | `Show the SQLite download steps and when you can delete old downloaded files.` |
| Choose GCD file / Choose another file | `Choose a GCD SQLite ZIP or database file to check before building an index.` |
| GCD file path | `Full path to a GCD SQLite ZIP or database file on this computer.` |
| Check file / Check file again | `Check the selected GCD file and available disk space without building an index.` |
| Build index | `Build a GCD index from this file; matching keeps using the current index until the new one is ready.` With no index: `Build a GCD index from this file for offline matching.` |
| Rebuild index | `Build the index again from the dump already in use.` |
| Use older dump | `Replace the current index with an index built from this older dump.` |
| Cancel (inspection/preview) | `Close this file preview without building an index.` |
| Cancel update | `Stop this index build and keep the current index, if one exists.` |
| Cancelling… | `Waiting for the index build to stop.` |
| Finishing update… | `The checked index is switching into use; wait for it to finish.` |
| Dismiss | `Hide this update notice.` |
| Try again (status) | `Check the current GCD index and update status again.` |
| Download / source / licence links | Respectively: `Open GCD downloads in your browser.` / `Open the Grand Comics Database website.` / `Read the Creative Commons Attribution-ShareAlike 4.0 licence.` |

Native buttons, Enter/Space activation, normal Tab order. On file selection, focus the preview heading (`tabindex=-1`), not the force action; Tab reaches actions in visual order. On explicit start, focus the progress heading. If Cancel update becomes unavailable while focused, retain focus there; if its node must disappear on completion, move focus to the resulting status, only when focus was inside the replaced operation. Passive polling never takes focus. No full-panel DOM replacement on every tick.

Progress has an accessible label and numeric value, but no live region that announces each percentage or elapsed second. A separate polite, atomic status announces stage transitions and terminal outcomes once. New errors use `role=alert` once. Paths are outside live regions. Collapsed content is absent from the Tab order.

**Implementation acceptance, once in the existing targeted headless checks:** cover empty, ready, inspecting, all three previews, insufficient space, each distinct error layout, progress (known/unknown), cancelling, switching, cancelled, success and status unavailable, with the disclosure open and closed. Reminder is absent at 13 days and present at 14; same-dump rebuild keeps its original age. Include help open/closed and the reminder's download link in the rect check. Record `(x,y,width,height)` for visible interactive rects: each is at least 24×24, buttons at least 32 high, and same-plane rects are disjoint and contained by the panel. Confirm wrapped long path/error/help content at 320 CSS px and normal 640 px minimum app width without horizontal overflow or clipped focus. Check one keyboard path through inspect → confirm → cancel and focus restoration. Stub native pickers/external links; no focus-taking check or app launch is authorized by this spec. Reuse the candidate's existing verification run; no extra full suite, repeated Judy pass or broad measurement sweep. No scratch output was created by this design pass.

## 8. Same-batch copy consistency — manual ComicVine approval

Ender's authorized Critter fix replaces the selected ComicVine issue link while preserving other populated metadata. Update these existing strings in `static/index.html`; no layout, control or action-label changes. This is a copy correction within the same 0.6.0 pass and rides the next code/bump commit.

| Existing location | Exact replacement |
|---|---|
| `#applyHint` (whole paragraph) | `The selected ComicVine issue link replaces the saved link. Other metadata is filled only when empty. A recovery backup is kept until the update is verified, then deleted. Writing can take time for large comics.` |
| `#apply` tooltip, both initial HTML `title` and the JavaScript `finally` restoration | `Replace the saved ComicVine issue link with the selected issue and fill empty metadata fields.` |

Keep **Approve issue and write metadata** as the button label and the in-flight writing tooltip unchanged. Both resting-tooltip consumers must use the same new sentence so a completed/failed attempt cannot restore the obsolete empty-fields-only claim. Verification is a literal check of these three locations in the existing change review; no new UI round or test suite.
