# Failure filters and reasons

Date: 2026-10-13. Owner: Judy. Status: reviewable draft, all open questions closed; Sully commits this exact file before Ender is briefed. Written from the released v0.1.3 code (`1c34df2`) in the main checkout, read-only. Nothing was run, committed or contacted: no service, no live data, no provider. Source: Sergei 2026-10-13 (the request, and his answers to the six open questions, folded in the same day; decisions in section 11). Findings it closes: Futaba Q4-4 and P-4, Senua F20.

Classification: EXTEND of `static/index.html` (status filter, count chips, row reason, summary lines) plus read-side additions and three record changes Ender owns (`/api/comics` rows and filter values, `/api/progress` counts, section 9). One new control, `Try again`, with its own endpoint (section 6). This is the existing browser dashboard; the Electron shell only hosts the same page.

Basis: NN/g visibility of system status, recognition over recall, plain-language error recovery; Hick's Law; Jakob's Law (the page's own count-chip pattern and its "Your help is needed" wording); WCAG 2.2 AA; ProcessRules § Copy is short, specific, and has no memory, § A new control is born with its tooltip, § No UI element may cover another; the DashboardTooltips spec (numbering continues at row 27); the DesktopShell spec rule "a state word opens every message".

## 1. What Sergei gets

| He asked for | Answer |
|---|---|
| Find the comics | Five new options in the existing Status filter, in two labelled groups: **Needs your help** and **Retrying on its own**. Five count chips under the search row set the same filter. |
| A clear reason per comic | A badge plus one or two sentences under the series name. The raw last error sits in Details. |
| Stopped versus still retrying | They are different options, different chips and different badges. |
| A summary that is true | The two "no action needed" sentences go. Status lines take their place, including one for a missing ComicVine key. |
| Try again | Ships, as one attempt (section 6). |

```
[ Find a filename or series ...... ] [ Status v ] [Search] [Corrupted · 2] [Needs conversion · 1]   <- unchanged
Needs your help [Writes stopped · 2] [Dead ComicVine link · 1] [ComicVine conflict · 0]  Retrying on its own [Write failed · 3] [Held for ComicVine · 87]
12 live files · Showing 1–12
Spawn                                   112 / 1996   Existing metadata · Synopsis missing   [Details] [Folder]
[Needs a fix] Automatic writes stopped after 5 failed attempts. Close any program using the file
              or repair it, then use Try again.
[Try again]
> File location
```

## 2. What the record can say (code read, v0.1.3)

All state lives in the comic's discovery record (`discovery_records`, joined to the comic by `path`, as `coverage_priority.firstpass_folder` already does). `skipped.json` and `failed.json` are per-batch logs of the same events: they repeat once per attempt and carry no more than the record, so **the dashboard reads the record, never the batch files**.

| Reason | Where it is recorded | Exists today? |
|---|---|---|
| Write failed, attempt N | `outcome = write_failed`, `write_failures.count`, `retry_at`, `write_error` (raw last error) | Yes |
| Writes stopped | same, with `write_failures.stopped = true`, `retry_at = 0` | Yes |
| Held for ComicVine | `hold` (`count`, `wait_end`), `retry_at`, `provider_waits.comicvine.reason` | **Gap, required (R2):** `reason` is free text, includes a stale relative time ("retry in about 5 minutes") and says "metadata service". It cannot be shown. The page needs a structured retry time and a cause code. |
| Dead ComicVine link | Only in the `detail` sentence | **Gap, required (R1):** no structured marker. The issue number is not stored except inside that sentence. |
| ComicVine conflict | `outcome = identity_conflict`, `conflict_issue` (`id`, `volume.name`, `issue_number`) | **Gap, required (R3):** no `detail` sentence, unlike the other two reasons. The structured part exists. |
| Write skipped (`write_skipped`) | `outcome`, `write_error` | See finding B. Not shown (confirmed by Sergei). |

**A. The stop lifts only when the file changes, and closing a program does not change it.** `write_retries_stopped` holds the comic while the record's `signature` (size, mtime) equals the file's. Sergei's own example is a comic another program holds open for weeks. He closes that program and nothing happens: size and mtime are the same, so the stop stays. Without a control, the honest fix in the message would be "re-save or replace the file", which is hard while it is locked. This is why `Try again` (section 6) ships.

**B. Every reason counts only while its record still applies.** A record applies while its `signature` equals the comic's current `[size, mtime]` (the test `write_retries_stopped` and `held_before` already use). A changed file is due again at the next pass, so showing it as "stopped" would be false. Consequence for skipped writes: a skip happens because the file changed after the scan, and the end-of-batch rescan then gives the comic a new signature, so almost every skip stops applying at once. The rare remainder waits one day and resolves itself. **A skipped write is not a filter, a chip or a badge.** It is not a problem Sergei can act on.

**C. One reason per comic.** A record can carry several markers (a saved conflict plus a later failed write; a dead link plus a failure). Each comic counts in exactly one category, first match wins:

`Writes stopped` > `Write failed` > `ComicVine conflict` > `Dead ComicVine link` > `Held for ComicVine`

So chip counts add up, a comic never appears under two filters, and the row shows the most urgent reason. Held and dead link cannot coexist in the code; conflict suppresses held.

**D. Scope of the counts.** The live root only, the comic's catalog status is not `absent`. Not affected by the text search box (the chips show library totals, the list total below shows the filtered result).

## 3. Filters

### 3.1 The status filter (existing `<select id="status">`)

Extend it; do not add a second control. Reasons: the categories are mutually exclusive (section 2C), so one choice is the right model; two selects with an "All" each would hide which is active (Hick, error prevention); the existing warning chips already drive this same select.

- Add two `<optgroup>`s **after** the existing options; existing options, their order and their values stay (`test_dashboard_filter.py` pins `''`, `missing` first and unique values; the new values are appended and distinct).
- A collapsed select shows only the selected option's text, so **every label is self-contained**: `Problem · who acts`. This is the page's own pattern (`Corrupted · Needs reacquiring`).
- Native dropdown, dark scheme from `color-scheme: dark`; group labels are native.

| Group | Option text | `value` | Who acts |
|---|---|---|---|
| Needs your help | `Writes stopped · Needs a fix` | `write_stopped` | Sergei: close the program using the file, or repair it |
| Needs your help | `Dead ComicVine link · Needs a fix` | `dead_link` | Sergei: correct the link in the file |
| Needs your help | `ComicVine conflict · Needs a check` | `conflict` | Sergei: decide whether the file or the link is right |
| Retrying on its own | `Write failed · Retrying` | `write_failed` | The app, up to the limit |
| Retrying on its own | `Held for ComicVine · Retrying` | `held` | The app, when ComicVine answers |

"Needs attention" is already taken by the existing `error` status (an unreadable archive) and is **not** reused. Group names use "Needs your help", the page's existing phrase (`Your help is needed: …`).

Select amendments (Tooltips spec row 11): accessible name `Comic status` (was `Metadata status`); tooltip `Show only comics with this status.` (was `… this metadata status.`). Options still carry no tooltip.

### 3.2 Count chips (new row under the search row)

One in-flow row between the search row and `#total`. Always present, never hidden, so nothing below it moves when a count changes. Two groups, each `role="group"` with the group label as its name; a group wraps as a unit.

| Group label | Chips (text is `label · count`) |
|---|---|
| `Needs your help` | `Writes stopped · {n}`, `Dead ComicVine link · {n}`, `ComicVine conflict · {n}` |
| `Retrying on its own` | `Write failed · {n}`, `Held for ComicVine · {n}` |

- Native `<button>`. Click sets the select to the chip's value, resets paging, loads. A second click on the active chip returns the select to `All files`.
- `aria-pressed` is true when the select equals the chip's value, and follows the select when it changes by hand. The existing two warning chips (`Corrupted`, `Needs conversion`) stay where they are and are not changed; offering to fold them into this row is left to Sergei.
- Count `{n}` uses `toLocaleString()`. Before the first payload it is `–`. A failed poll keeps the last counts. Chips stay clickable at 0.
- Colour tells "act" from "wait": a `Needs your help` chip with `n > 0` takes the existing `.warning-filter` look; every other chip, including those at 0, is the neutral secondary look. Meaning never depends on colour: the group label and the chip text say it.
- Counts change by text write-on-change only (same habit as Tooltips spec § Mechanism 3), so a resting pointer keeps its tooltip and the open select is never rebuilt. The `<option>` texts are static and carry no counts.

## 4. The row: badge plus reason

Placed in the comic cell (column 1), between the series name and `File location`, so it survives the existing rule that hides column 3 at 700 px and narrower. Shown only when the comic has a reason. Rows without one do not change.

Structure: a badge (inline), then the sentences as text. The badge opens the message, so meaning never depends on colour. Two badge kinds, each three words at most:

| Badge | Used for | Look |
|---|---|---|
| `Needs a fix` | stopped, dead link | existing warning palette: fill `#594817`, text `#ffdf76`, 1 px border `#bd9735` |
| `Needs a check` | conflict | same |
| `Retrying` | write failed, held | existing `.badge` palette: fill `#24364c`, text `#bcd8f9`, 1 px border `#38445a` |

### 4.1 Copy

Every sentence follows the copy standard: one fact per sentence, two sentences at most, the second names the fix or the next step. `{limit}` is the failure limit the server reports (5 today), never typed into the page. `{time}` is defined in 4.2.

| State | Badge | Text |
|---|---|---|
| Stopped | `Needs a fix` | `Automatic writes stopped after {count} failed attempts. Close any program using the file or repair it, then use Try again.` |
| Write failed, retry due later | `Retrying` | `Attempt {count} of {limit} failed; nothing was written. Next try around {time}.` |
| Write failed, retry due now or past | `Retrying` | `Attempt {count} of {limit} failed; nothing was written. Next try at the next folder pass.` |
| Write failed, count missing | `Retrying` | `The write failed; nothing was written. Next try at the next folder pass.` |
| Dead link | `Needs a fix` | `The file's ComicVine link names issue {id}, which does not exist. Correct the Web link in the file.` |
| Conflict | `Needs a check` | `ComicVine issue {id} is {cvSeries} #{cvNumber}; the file says {series} #{number}. Check which is right, then correct the file or its link.` |
| Conflict, ComicVine's values unknown | `Needs a check` | `ComicVine's series or issue number for this link differs from the file's. Check which is right, then correct the file or its link.` |
| Held | `Retrying` | `{cause} Writes wait for its answer; next try around {time}.` |
| Held, missing key | `Retrying` | `No ComicVine key is set, so writes wait. Add COMICVINE_API_KEY to the .env file and restart the app.` |

The restart clause is the code's own instruction (`Set COMICVINE_API_KEY before starting the app`). `api_key()` re-reads the `.env` file on every call, so a restart may not be needed. Ender confirms; if it is not needed, `and restart the app` is dropped from this row and from summary line C (section 5), so the copy stays true.

Held `{cause}` (one per cause code; R2 in section 9 requires the code):

| Cause | Sentence |
|---|---|
| `cooldown` | `ComicVine is cooling down after an error.` |
| `limit` | `The ComicVine request limit is reached.` |
| `unreachable` | `ComicVine cannot be reached.` |
| `rejected` | `ComicVine did not accept the request.` |
| `empty` | `ComicVine returned no issue for this link.` |
| anything else, or no code yet | `ComicVine could not check this link.` |

The last row is the safe fallback for a record with no recognised cause (an older record, or a cause Ender does not map). It is never a guess at a cause: `ComicVine could not check this link. Writes wait for its answer; next try around {time}.`

Visibility rule (Sergei 2026-10-13): every category shows its line in **every** list except `Held`, whose line shows only while the `held` filter is active. A held comic is an ordinary, automatic wait (ComicVine's 180-request hourly budget alone can hold thousands of the roughly 4,400 linked comics for days), and a quiet-by-default line keeps the full list readable.

### 4.2 Time format

`{time}` is the next-try epoch in local time: `retry_at` for a failed write, `hold.next_try_at` for a held comic (R2). Same day: the time without seconds (`2:20 PM`). Another day: date and time without seconds (`Oct 15, 10:12 AM`). The existing `deadline()` in the Yandex block prints seconds; the new text drops them (the Yandex row is hidden in v0.1.3, so Ender may adopt the same format there; offered, not required). `around` is deliberate: a held comic is woken sooner when ComicVine answers, a failed write sooner when its file changes, and a busy queue can run it later, so "after" or "at" would sometimes be false. A value of 0 or in the past uses the "next folder pass" wording above. A stopped comic shows no time.

### 4.3 Details dialog

One extra block at the top of the dialog, shown only for a comic with a reason, held comics included (their list line is quiet, the dialog is on demand): the same badge and text as the row, then for write states `Last error: {write_error}` (the raw text, trimmed to 300 characters, in the existing `.preview` style). It is plain text, not a control: no tooltip. The existing line "This is an optional manual lookup. The automatic worker does not require you to review every comic." stays; it is still true. The raw error lives here because it is specific (`The process cannot access the file because it is being used by another process`) but too long and too technical for a list row.

## 5. Summary and the misleading lines

Futaba Q4-4 names one false line. There are three places that say "nothing to do", and the research count hides the fourth:

| Where | Today | After |
|---|---|---|
| `#liveDetail` while waiting | `Folder checks can finish while metadata research is still unresolved. No manual review is required unless a request appears above.` | `Folder checks can finish while metadata research is still unresolved.` |
| Live library panel | `Processing and checks for new comics run automatically. You only need to act when a specific request appears above.` | `Processing and checks for new comics run automatically.` |
| `#researchStatus` | `unresolved = wiki_candidates_found + needs_identity_lookup + identity_conflict` | `unresolved = wiki_candidates_found + needs_identity_lookup`. A conflict is not waiting for research; it moves to "Your help is needed". Held comics stay in this count on purpose (they still need research); that overlap is intended and is not a bug. |
| Comic details dialog | `This is an optional manual lookup…` | unchanged |

New status lines in `#problemSummary`, directly after `#queueAttention` (the other "Your help is needed" lines), `aria-live="polite"`, each line written only when its text changes:

| Line | Shown | Text |
|---|---|---|
| A | always, once the payload has `problems` | with help count `h > 0`: `Your help is needed: {h} comic(s). Filter by status below to see which.` (`1 comic`, `2 comics`; text colour `#ffdf76`). With `h = 0`: `No stopped writes, dead links or conflicts.` (default text colour) |
| C | only while the ComicVine key is missing: `providers.comicvine.status` is `not_configured` in the same `/api/progress` payload (`providers.comicvine_status()` already sets it from a live `api_key()` check, so no new data) | `No ComicVine key is set, so comics with a ComicVine link wait. Add COMICVINE_API_KEY to the .env file and restart the app.` (text colour `#ffdf76`, like A) |
| B | only when retrying count `r > 0` | `{r} comics are retrying on their own.` / `1 comic is retrying on its own.` |

Order on the page: A, C, B. `h` is stopped + dead link + conflict; `r` is write failed + held. Line C is a global cause, not a comic count: it is not part of `h` and has no chip. It names no count because every linked comic is held while the key is missing, and the held chip already carries that number. A rejected key (ComicVine answers but refuses) is not covered by this line (Sergei decided on a missing key only).

- The zero sentence is deliberately narrow. A universal "nothing needs you" would be false next to `Corrupted`, `Needs conversion`, `Needs attention` and an attention ticket, and that is exactly the mistake being fixed.
- **Absence is not zero.** If the payload has no `problems` object (older server, failed poll before the first answer), show no line A and no line B, never the zero sentence. If it has no `providers.comicvine`, show no line C.
- `Your help is needed: {folder} — {error}` lines for stopped tickets stay as they are. A stopped ticket is a folder-level state and is not a category here.

## 6. `Try again`

**Decided (Sergei 2026-10-13): it ships, and it is one attempt.** Without it the most likely fix in the message (close the program holding the file) does nothing (finding A), and the only recovery would be to touch the file. Cost: one button, one endpoint that clears a flag. Risk: low, because it schedules one attempt and every write still passes the same backup, read-back and SHA-256 chain.

- **Where:** inside the comic cell, on its own line under the reason sentence, on `Stopped` rows only. Not in the actions column: a third nowrap button would widen that column and force the table past 320 px; and the button belongs next to the sentence it acts on.
- **Look:** the existing row-button look (`Details`, `Folder`: 6×9 padding, 14 px), about 32 px high, 8 px below the sentence.
- **Label:** `Try again`. Not `Try again now`: the attempt runs when the folder is next checked, and "now" would promise more than the code does. If Ender confirms the attempt starts at once, `Try again now` is allowed.
- **Effect (Ender, requirement R4 in section 9):** clear the stop and set the retry time to now, **keeping the failure count**. One attempt follows; if it fails, the comic stops again at once with `after 6 failed attempts`. Only while the record still applies (same signature); otherwise it does nothing and the next poll shows the true state.
- **States:**

| State | Label | Tooltip |
|---|---|---|
| Ready | `Try again` | `Clear the stop and try writing this comic when its folder is next checked.` |
| Request sent (disabled) | `Retry requested` | `Retry requested. No further clicks are needed.` |

- After the poll the comic is `Write failed · Retrying` (`Attempt 5 of 5 failed; nothing was written. Next try at the next folder pass.`) and leaves the Stopped list, and the chip counts follow. A written comic simply drops out. A failed request shows the server's message in the existing `#error` banner and re-enables the button.
- **Focus:** if the click removes the row from a filtered list, focus moves to `#total` (give it `tabindex="-1"`), never to the page top. The row buttons are rebuilt when the list changes, so this is needed.
- **Not specified:** a bulk "try all stopped" (useful if one viewer held thirty files; offered, not fired) and `Try again` on `Write failed` rows.

## 7. Tooltips and accessible names

Continues the DashboardTooltips numbering (rows 1 to 26). Row 11 is amended in 3.1.

| # | Control | State | Tooltip |
|---|---|---|---|
| 27 | Chip `Writes stopped · {n}` | | `Show comics whose automatic writes stopped after {limit} failed attempts. They are tried again when the file changes.` |
| 28 | Chip `Dead ComicVine link · {n}` | | `Show comics whose ComicVine link names an issue that does not exist.` |
| 29 | Chip `ComicVine conflict · {n}` | | `Show comics where ComicVine's series or issue number differs from the file's.` |
| 30 | Chip `Write failed · {n}` | | `Show comics whose last write failed. The app tries again on its own.` |
| 31 | Chip `Held for ComicVine · {n}` | | `Show comics whose writes wait for a ComicVine check that cannot answer yet.` |
| 32 | `Try again` | Ready | `Clear the stop and try writing this comic when its folder is next checked.` |
| | `Try again` | Request sent | `Retry requested. No further clicks are needed.` |

- Chips: visible text is the accessible name, `aria-pressed` carries the state, the tooltip is the description. The tooltip text does not change with the count.
- Badges and the summary lines are plain text, not controls: no tooltip.
- `Try again`: accessible name `Try again: {series} {number}` (contains the visible label), because the list can hold many identical buttons.

## 8. Layout and measurable values

Palette is the page's own. Contrast ratios are **hand-computed from those hex values**, not measured from a render; Futaba re-measures from the rendered page.

| Element | Value |
|---|---|
| Chip, neutral | 32 px high, padding 4×12, 14 px text, radius 8, fill `#242c3b`, text `#eef2fb` (12.50:1), 1 px border `#aab4c6` (7.81:1 on the panel `#1b202b`). The DesktopShell secondary look. |
| Chip, `Needs your help` with `n > 0` | existing `.warning-filter`: `#ffdf76` on `#594817` (6.80:1), border `#bd9735` (5.93:1 on the panel) |
| Chip hover / pressed / focus | hover: inset 1 px `#bcd8f9`; pressed: inset 2 px `#bcd8f9` (6.06:1 on the warning fill, 9.60:1 on neutral); focus-visible: 2 px `#bcd8f9`, 2 px offset (11.14:1 on the panel). Pressed keeps its fill. |
| Chip gaps | 8 px between chips; group label 13 px `#9dacc2` (7.08:1), 8 px before the first chip; groups separated by 16 px |
| Badge | 13 px / 600, padding 2×8, pill radius, inline, not interactive. `Needs a fix`: `#ffdf76` on `#594817` (6.80:1). `Retrying`: `#bcd8f9` on `#24364c` (8.39:1) |
| Reason sentences | 14 px / 1.5, `#aab4c6` (7.81:1 on the panel), 6 px below the series name, wrap anywhere (the cell's existing rule) |
| `Try again` | existing row-button look, about 32 px high, 8 px below the sentence |
| Summary lines A (help) and C (missing key) | page `p` style, text `#ffdf76` (12.49:1 on the panel). Zero sentence of A and line B: page `p` colour |

- **Colour-blind safe:** yellow versus blue plus a text badge; no red or green. **Theme:** the dashboard declares dark only (`color-scheme: dark`) and has no light variant; there is nothing to check in light, and the native dropdown follows the dark scheme.
- **No covering:** every new element is in normal flow, nothing is positioned or sticky. The open select is the sanctioned overlay class. The chip row is always present so a count change never moves the table. Narrow widths: chips and group labels wrap; a chip may wrap its own text rather than overflow; column 3 is still hidden at 700 px and narrower, the reason line is not.
- **States Futaba measures:** all counts zero; one comic of every category; each filter active; widths 1450, 1024, 700, 640 and 320 CSS px and 200% zoom; a very long series name; the Details dialog open (modal, sanctioned); the select open; `Try again` pending. Expected before measuring: chip and `Try again` height about 32 px (at least 24), badge fully visible, no horizontal page scroll at 320.

## 9. For Ender

Spec states what the page needs; how it is built is Ender's.

1. **`/api/progress`** gains `problems`: `{write_stopped, dead_link, conflict, write_failed, held, limit}`, computed with the rules in section 2 (record still applies, one reason per comic by the precedence, live root, not `absent`). `limit` is `discovery_state.WRITE_FAILED_LIMIT`. Use the existing predicates (`write_retries_stopped`, `held_before`), not a second copy of their logic.
2. **`/api/comics`** accepts the five `status` values and returns a `problem` object on **every** row, not only filtered ones: `{code, count, retry_at, last_error, cause, issue_id, cv_series, cv_number}`, each present only when it exists. The page decides what to show (a held row shows its line only under the `held` filter, 4.1), so the data cannot depend on the filter.
3. **Record changes, required.** Three gaps in what the discovery record stores. Each is an implementation requirement, not a preference: the page may not parse free text, and may not guess where a field is missing. The save sites are in `automatic.discover` (the record built at its end, around the `dead_web`, `hold` and `conflict` branches) and `provider_wait.record_failure`.

   **R1. Dead-link marker.**
   - **What:** a structured field `dead_link` on the record, holding the ComicVine issue number the Web link names, as a string (for example `"123456"`).
   - **When:** set only on the record of a pass in which ComicVine answered Object Not Found for that number (the `dead_web` branch that writes the `detail` sentence today). Absent on every other record. The record is rebuilt each pass, so the marker clears when the link is corrected or the file changes.
   - **Page use:** the marker drives the count, the filter, the badge and `{id}` in the row sentence. The existing `detail` sentence stays for the research record; the page never parses it. `/api/comics` returns the number as `problem.issue_id`.
   - **Tests:** positive (a dead number: marker and number present, counted once) and negative (a live number, a hold, a conflict: marker absent). With a stopped or failed write on the same comic, only the write reason shows (section 2C).
   - **Size of the problem:** Ender's read-only count of 2026-10-12 found exactly 1 live comic with a dead link. The yellow help line will not be permanent; no triage change.

   **R2. Held-state structured retry time and cause.**
   - **What:** two fields inside the record's `hold` object (which already has `count` and `wait_end`):
     - `hold.next_try_at`: epoch seconds, the time the app will next try this comic. It is the same value the code stores as the record's `retry_at` after `hold_retry()`, written in the same statement. Never 0 for a held record.
     - `hold.cause`: one of `cooldown | limit | unreachable | rejected | empty | no_key`, set from the `ProviderDeferred` the pass recorded (cooling down, hourly budget or rate limit, cannot reach or HTTP error, did not accept, an empty answer, key not set). A held record with no mapped cause carries no `cause`; the page then shows the fallback sentence in 4.1.
   - **Why a second copy of the time:** the record's `retry_at` is rewritten by other code (`write_not_done`, the one-hour error cap) and the page needs one value that always means "next try of this held comic". The free text `provider_waits.comicvine.reason` and the `detail` sentence carry a relative time computed at save time ("retry in about 5 minutes"); they are never displayed.
   - **Page use:** `{time}` in the held row reads `hold.next_try_at`; `{cause}` reads `hold.cause`; the missing-key row shows no time. `/api/comics` returns them as `problem.retry_at` and `problem.cause`.
   - **Tests:** one held fixture per cause, repeated holds (5, 10, 20, 40, 60 minute steps: `next_try_at` follows `hold_retry`), the empty answer (daily), the missing key (no cause-specific time shown), a held comic whose file then changes (record no longer applies, so not counted).

   **R3. Conflict detail sentence.**
   - **What:** every record whose outcome is `identity_conflict` gets a `detail` sentence, as dead-link, hold and failed-write records already do. It is the same text as the first sentence of the row: `ComicVine issue {id} is {cvSeries} #{cvNumber}; the file says {series} #{number}.` built from `conflict_issue` (`id`, `volume.name`, `issue_number`) and the file's own Series and Number used in the comparison. When ComicVine's series or number is missing: `ComicVine's series or issue number for this link differs from the file's.`
   - **When:** written in the `conflict and match` block that saves `conflict_issue`, including a conflict kept from an earlier pass while ComicVine cannot answer. It replaces the dead-link or hold `detail` on the same record (section 2C precedence).
   - **Page use:** the row builds its sentence from the structured fields and adds the second sentence; the stored `detail` must read the same as that first sentence, so the record and the dashboard never disagree. Futaba compares them character for character.
   - **Tests:** a fresh conflict, a conflict kept through an outage, a conflict that also has a dead link (conflict sentence wins), ComicVine values missing.

   STOP and report if any of the three cannot be recorded truthfully at its save site: the page then shows the fallback sentence for that state and no invented detail.
4. **R4. `Try again` endpoint** (section 6). A same-origin POST like the other write routes, body `{comic: id}`. If the comic's record still applies (same signature) and is stopped: clear `write_failures.stopped`, set `retry_at` to now, keep `write_failures.count`; return the new state. Otherwise do nothing and return the current state. The one attempt then runs through the normal pass and the unchanged safety chain. If the route is refused while processing is paused, the existing "Processing is paused. Resume before starting manual work." message in the page's error banner is acceptable; Ender reports which it does.
5. **R5. Missing-key line.** Line C reads `providers.comicvine.status === 'not_configured'` from `/api/progress`; no new data. Ender confirms whether adding the key needs a restart (`api_key()` re-reads `.env` on every call) and drops `and restart the app` from line C and from the held-missing-key row if it does not.
6. **Optional write cause** (not required, not specified): the stopped sentence does not name why the file failed (locked or denied, damaged page, other). Windows reports "Access is denied" both for a file held open and for a read-only file, so a cause label would need hedged wording. The raw error in Details covers it.
7. **Page:** `index.html` changes only in the filter, the chip row, the row builder, `Try again`, `#problemSummary`, the three sentences in section 5 and the research sum. Do not touch the verification controls, `#appVersion`, `#error`, or the two existing warning chips.
8. **Docs that become false** (Ender or Sully, not this spec): README line 62 ("the dashboard does not show it yet, nor how many comics have a failed write"), `SOURCE_CONNECTORS.md` line 104, the Brief's "Failed writes" row (the dashboard clause and its revisit trigger), the Tooltips spec row 11, Futaba Q4-4 and Senua F20 on close.

## 10. Acceptance (Futaba)

Offline, with fixture records and synthetic payloads. No live service, no live data, no provider contact. Report measured values, not impressions.

- **Strings:** read every new string from the DOM and compare it character for character with sections 3 to 7: five option texts and values, five chip texts, five chip tooltips, `Try again` both states, badge texts, every row sentence, the four summary sentences (A with and without comics, B, C). Times: today, another day, past, zero.
- **States, one fixture comic each:** stopped (count 5 and 6), failed attempt 1 to 4, failed with the retry past, held with each cause plus no cause, held missing key, dead link, conflict with and without ComicVine's values, skipped, a record whose signature no longer matches (must appear nowhere), a comic with two markers (must appear once, by the precedence).
- **Record changes (R1 to R3):** each fixture comic's record carries the marker or field named in section 9 (`dead_link`, `hold.next_try_at`, `hold.cause`, the conflict `detail`), with the negative controls listed there; the conflict `detail` equals the row's first sentence character for character; `hold.next_try_at` equals the record's `retry_at` for a held record. The page does not read `detail` or `provider_waits.*.reason` (grep the page source: 0 hits for `reason` and `detail` in the problem code paths).
- **Held row visibility:** a held fixture shows no reason line in All files and under every other filter, and shows it under `Held for ComicVine · Retrying`.
- **Missing key (line C):** shown only while `providers.comicvine.status` is `not_configured`; absent when `configured`, `rate_limit_wait` and `hourly_budget_wait`; absent when `providers` or `providers.comicvine` is missing. Positive control: it appears for `not_configured`.
- **Counts:** sum of the chips equals the sum of the five filter totals; each comic appears under exactly one filter; held is a subset of the research line's `still need research`; a chip does not change when the search text does.
- **Absence:** a payload without `problems` shows no summary line and no zero sentence. Positive control: with `problems` all zero, the zero sentence appears.
- **Misleading lines:** count `No manual review is required` and `You only need to act when a specific request appears above` in the served page: 0 after, 1 each on v0.1.3 (a check that has not been seen to fail is not a gate).
- **Existing behaviour:** the old ten options still filter as before; `test_dashboard_filter.py` extended and passing; the two warning chips unchanged.
- **Polling:** during a 10 s pointer rest on a chip the tooltip stays; an open select is not closed by a poll; each summary line is announced once per change.
- **Layout (measured `getBoundingClientRect()`):** at each width and state in section 8, the chip row, the search row, `#total` and the table have disjoint rects; every chip and `Try again` is at least 24×24; no horizontal page scroll at 320; the badge and sentence are not clipped. Contrast measured from the rendered colours is at least the values in section 8.
- **Accessibility:** chip name equals its visible text; `aria-pressed` follows a chip click and a manual select change; the select's name is `Comic status`; description equals tooltip for one chip and for `Try again`.
- **`Try again`:** shown on stopped rows only; click disables it and shows `Retry requested`; the stop is cleared on a fresh record and not on a stale one; the failure count is kept; after one failure the comic is stopped again with `{count + 1}` (one attempt, not five); the request failing shows the banner and re-enables; focus lands on `#total` when the row leaves a filtered list.

## 11. Decisions (Sergei 2026-10-13); no open questions remain

| # | Question | Decision | Where it landed |
|---|---|---|---|
| 1 | Ship `Try again`? | Yes | Section 6, R4 |
| 2 | One attempt or a fresh five? | One attempt; the failure count is kept | Section 6, R4 |
| 3 | Held comics in All files | Quiet by default: the reason line shows only under the `Held for ComicVine` filter (the Details dialog still shows it) | 4.1 visibility rule, 4.3 |
| 4 | Missing ComicVine key | Yes, one summary line | Section 5 line C, R5 |
| 5 | Skipped writes | Not shown; confirmed | Section 2B |
| 6 | How many dead links? | Exactly 1 live comic (Ender's read-only count, 2026-10-12); no permanent yellow line; dead link stays in "Needs your help" as specified | R1 |

Still open for Ender, not Sergei: whether adding the key needs a restart (R5), and whether the `Try again` route is allowed while paused (R4). Neither changes the layout.

Not covered, by design: tickets stopped for `needs_attention` stay in the existing "Your help is needed: folder — error" lines, and the entries of such a ticket that were never attempted are invisible per comic (Futaba Q4-1); `excluded_language` comics (excluded on purpose, not an error); per-batch failed or skipped counts in "Previous write batches"; sorting, export and bulk actions; the existing statuses and their labels; grouping the existing options.

Exclusions of this spec: UI code, git and release operations, edits to any other file, the running service, and live data.
