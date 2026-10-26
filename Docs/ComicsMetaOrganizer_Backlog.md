# Comics Meta Organizer — Backlog

Items Sergei has approved for a future version. Not started unless marked.

## Next version

### False "GPU release could not be confirmed" when Ollama is off (Sergei, 2026-10-24)
- **Seen in:** v0.3.0, while paused. The banner reads "Workers paused, but Gemma GPU release could not be confirmed. Retrying." It never clears.
- **Cause (Jane's read, not yet confirmed by Ender):** `pause_control.unload_model()` asks Ollama to unload Gemma. With Ollama not running, the request fails, and `checkpoint()` turns any exception into this error ([pause_control.py:184-188](../pause_control.py)). It retries about every 10 s, and every retry fails the same way.
- **Wanted (Sergei):** if Ollama isn't running, count that as "GPU released". No false alarm.
- **Also check (Sergei's question):** what the app does when it is resumed with Ollama off. Sergei resumed on 2026-10-24 and couldn't tell what the app was doing. The app never starts Ollama itself. `local_model.available()` returns False, and credits reading returns None when the model call fails. Find out whether Gemma-dependent comics get skipped, retried later or marked as failed, and whether the dashboard should say "Ollama not running".
- **Owner:** Ender (fix). Judy reviews any new dashboard wording. Futaba verifies.

### App starts and stops Ollama itself (Sergei, 2026-10-24)
- **Wanted (Sergei):** the app starts Ollama when it needs Gemma and stops it again. Sergei shouldn't have to start Ollama by hand.
- **Stop timing (Sergei):** stop Ollama when the app quits. Pausing doesn't stop Ollama; it only unloads Gemma, as today.
- **Stops it even if Sergei started it (Sergei):** on quit, the app stops Ollama even if Sergei started Ollama himself.
- **Owner:** Ender. Judy reviews any status wording. Futaba verifies. Our tooling never steals focus (ProcessRules § Desktop App / GUI Rules), so Ollama has to start hidden.

### Update statistics graph above Live library (Sergei, 2026-10-26) — in progress
- **Wanted (Sergei):** a graph above the Live library panel showing how many comics the app updated in a period.
- **Periods (Sergei):** since counting began, calendar year, calendar week, calendar day, last hour, and a custom from–to date range. **Default: the current calendar day.**
- **Count unit (Sergei):** distinct comics, not write events. A comic written several times in a period counts once.
- **Breakdown (Sergei):** total only. No split by source.
- **Week start (Sergei):** Monday.
- **Scope (Sergei):** live library only.
- **Existing "Updated by this app" counter (Sergei):** keep both numbers. Judy relabels them so the difference is clear: the counter is the comics in that state now, while the graph is every comic the app wrote in the period.
- **Data (Ender's read-only check, 2026-10-26):** the `history` table already stores a timestamp for every successful write since the first commit and is never pruned. So "since counting began" starts at the earliest history row and includes past updates. "Last hour" is a rolling 60 minutes. Day, week and year boundaries are local time.
- **Owner:** Judy specs the graph, labels and period picker first. Ender builds it. Futaba verifies. Senua reviews. Sully releases.

### 0.4.1: update statistics fixes (Sergei, 2026-10-26)
- **Decided (Sergei):** 0.4.0 ships as is, and these go into 0.4.1 as one batch.
- **Count can be one short (Senua M1, Major):** in `update_stats.py`, `now` is taken before the history id is read. A write that lands in between is left out of the count, and the result is cached that way until the next write. Fix: take `now` after the id, and bound both queries by that id.
- **Slow long periods (Futaba QA-2):** cold Year, All time and Custom-from-2000 take 1.4–2.7 s on 200,000 history rows, against the brief's 0.22 s. The count is recomputed on every 15 s refresh while writes happen.
- **Future rows (Futaba QA-3):** `first_at` and `last_at` ignore the "now" cutoff, so a row dated in the future can show as the last update.
- **Minor, fix if cheap:**
  - Senua m1 / QA-6: a missing custom date returns the wrong message.
  - Senua m2 / QA-4: the Windows C library applies the wrong daylight-saving rules to past years; the first affected date is in 2028.
  - Senua m3: the docstring says "read-only", but the endpoint takes the write lock.
  - QA-1: the tooltip is too wide at 320 px in non-English locales.
  - QA-5: the README and CHANGELOG don't describe the panel or the relabels.
- **Sources:** `Docs/ComicsMetaOrganizer_CodeReview_v0.4.0_2026-10-26.md`, `Docs/ComicsMetaOrganizer_QA_v0.4.0_2026-10-26.md`.
- **Owner:** Ender fixes. Futaba checks what changed. Senua reviews. Sully releases.

### Make the entry check pass cleanly (Sergei, 2026-10-26)
- **Why:** the 0.4.0 entry check (`dd019cb`) ran 968 tests: 959 passed and all 48 update-stats tests passed. It still failed, because of the test setup, not product code. 0.3.0 had no entry receipt at all. Evidence: `C:\Antigravity Projects\Worktrees\Comics Meta Organizer\qa-040b\logs\ender-entry.log`.
- **Wanted (Sergei):** fix it later, as its own task. It does not hold 0.4.0.
- **What Ender found:**
  1. **Test Python:** the packaged app's Python ignores the working folder (`python314._pth`), so three tests that start a child Python fail with `ModuleNotFoundError` (`test_state_root`, `test_library_lock`, `test_qa_runtime`). Ender proposes a pinned test Python of the tool's own, like Books Arranger's QA runtime.
  2. **Non-UTF-8 output:** the checker fails the step with "Final supervisor output differs from streamed bytes" when test output is in the Windows code page. The fix is in the checker, or `-X utf8` in `check-python.cjs`, or both.
  3. **Time-sensitive tests:** two kept-backups tests fix their times when the module loads ("12 min ago" vs "13 min ago").
  4. **Old failures:** three failure-filter DOM tests already failed on clean HEAD.
  5. **Shell tests skipped:** `check:shell` never runs when `check:python` fails, because npm `&&` stops there.
  6. **Context builder:** CMO has no committed entry-check context builder. Ender's one-off is at `...\qa-040\assemble-context.mjs`.
- **Owner:** Ender. Senua reviews the context builder before it is committed.
