# Code Review — Comics Meta Organizer v0.1.2

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-12
Tool: Comics Meta Organizer
Release: v0.1.2 (patch)
Commit range: cb0ee1432f447c7847e228c0674721166fb3df21..30dad02abb8ce36e2b64da73b889e873afedc4f3
Worktree / branch: WIP/Comics Meta Organizer-lens-fix, fix/lens-v0.1.2 (clean tree at review time)
Files changed: 12 files, +855 / -48 (one commit, 30dad02)
Stand-down dimensions: none; Electron checks do not apply (Python service + local web dashboard)
```

Predecessor coverage: the v0.1.1 review certified `e197f97` plus the final-v2 patch, which became `2b5f975`. The commits `2b5f975..cb0ee14` change docs only (4 files under `Docs/`), so this range follows on directly from that review.

`VERSION` still reads `0.1.1` and `CHANGELOG.md` has no 0.1.2 entry in this range. This clearance covers `30dad02` plus Sully's version/changelog-only bump commit. Any other change to code or tests needs a fresh look.

## Summary

The single commit changes four things:
- **Write gate.** `research.verify_web_source` now also accepts any publisher and unnumbered books when the page matches the exact title, names one known creator in full, agrees on any known year, and the cover agrees.
- **Queue holds.** A Lens search that cannot run (cooldown, daily cap, human check, SerpApi cap) now gives its task back with its previous state and timestamp. Leads that fail verification are searched again after 30 days.
- **Post-check leads.** After a solved human check, the results page Google loads is read, and its links are saved as unverified leads for the comic whose search hit the check.
- **API redaction.** `verification_url` and `verification_task` are removed from the API responses.

I read every changed production line and the existing code it depends on: the `automatic.discover` write path, `covers_agree`, `parse_name`, `is_book`, `web_search.read`/`source`, GetComics and catalog provider accounting, `lens_verification.service`, and every HTTP GET handler. I read the four new test files. I ran two probe scripts from my scratchpad against the worktree's own modules, with network, archive and image reads mocked. I did not run the test suite, the service, any browser or any public request.

**Bottom line.** Every new route still needs a matching title, a creator hit and a cover agreement, and only empty fields are filled. I found no route where a search match alone authorizes a write, and nothing on the safety floor. But the evidence is weaker and less independent than the docs claim (F1). The new cover fetch inside the general web lookup also brings an unhandled exception class with it (F2).

## Focus-area answers (brief questions)

1. **Can a wrong comic be written?** Yes, in narrow cases, though not from a search match alone. The values written are limited:
   - `Series` and `Number` come from the local file.
   - `Publisher` is written only when it comes from a local hint (embedded metadata, the cover read or a folder alias) and the page names it.
   - The real risk is an empty `Summary` filled with text from a *different book's* page, plus a `Notes` line claiming identity was checked. The backup is removed once the write verifies.

   The routes that allow this are covered in F1: numbering without `#`, part, volume and series pages, unnumbered single issues, model-read "creators", and the fact that Lens leads get the cover check almost for free. Different-volume and same-number cases stay protected by the number, year and cover checks, because different volumes rarely share cover art. Collected edition vs. single issue is weakly protected (F1b).
2. **Queue: restore on blocked searches, 30-day leads with old timestamps, starvation?** No starvation. `claim()` serves the oldest last-touched task first. Every real search, empty result or failure stamps `updated=now` and moves the task to the back. A task is only given back unchanged under a hold that blocks every task equally. So a 30-day re-search jumps ahead of newer pending tasks exactly once, then goes to the back. The sleep-until-hold-ends logic is correct: it waits at most 1 hour, `browser-resume` and Pause still wake it, and a hold already in the past falls back to normal pacing. Remaining issues are small: F7 (misleading `browser_error`) and F6 (a check-then-write race).
3. **Post-check page attribution races.** The challenge URL and the task are written together in one status write by the single-threaded worker. Nothing can overwrite them while `service()` blocks. Archive signature and searchable-state checks reject changed or already-identified comics. One remaining race: a lookup and a write happen in two separate steps (F6). A stale post-check page can also replace earlier leads (F6).
4. **Redaction completeness.** Complete for both keys. Only `/api/browser-verification` and `/api/progress` serialize browser-search state, and both now go through `browser_search.public()`. `lens_verification.status()` and `yandex_verification.status()` carry no URL. Other GET handlers never read `browser-search.json`. The frontend never used either key.
5. **Wider Playwright error handling: hang or masking?** No new hang. The existing 600 s observe deadline and the new 20 s read deadline still bound everything, and a closed page is never treated as a temporary error. It does mask failures:
   - A persistent page error that has nothing to do with navigation now ends as a 10-minute `unfinished` outcome with no error class (F5).
   - The new read loop retries without pausing (F4).
   - A closed window during the read still reports `verified` with window `open` (F4).

## Rubric

Severity tags and the always-blocking safety floor: `Team/Docs/ProcessRules.md` § Severity definitions.

### 1. Security

- Status: Pass. No new shell-out, file-path or file-delete code. New cover fetches go through `web_search.validate_url` (public HTTPS only, redirects re-checked, 2 MB cap). Challenge URL and task redaction is verified complete (answer 4). No secrets added or logged.

### 2. Correctness & Logic

- Status: Concerns
- Findings:
  - F1: see dimension 5. The identity rule is put together in `research.py:225-301`.
  - F3 [Minor] `research.py:266-270`. `confirmed_publisher` matches a raw cover-read publisher as a single common word. Probes: `"Image"` is confirmed by "Click the image to enlarge", and `"Boom"` by "sales went boom". It then writes the raw OCR spelling (`Image` rather than the canonical `Image Comics`). The value still comes from this comic's own cover, but the "page names it" check proves nothing for one-word publishers.
  - F7 [Minor] `browser_worker.py:63-82`. The daily-cap skip goes through the generic `except Exception`. It writes `browser_error='Browser search could not finish; retrying after a cooldown.'` and a fresh 1 h `browser_retry_at`. That contradicts the README's "records the real reason" (the task detail itself is correct).

### 3. Crash / Stability Safety

- Status: Concerns
- Findings:
  - F2 [Major] `research.py:302-309`, reached from `research.py:377-384` (`general_lookup`) and `:348-355` (`resolve_leads`). The creator route forces `require_cover=True`, so `general_lookup` now downloads and decodes an og:image. Before this commit it never fetched images.
    - Both loops catch only `ValueError`. A non-image response (for example a hotlink-protection HTML page), an unsupported format or a truncated file raises `PIL.UnidentifiedImageError`/`OSError` from `covers_agree`.
    - Positive control (`probe_lookup.py`): the exception escaped `general_lookup`, the second hit was never fetched, and no evidence was saved, so `web_candidates` was lost.
    - `free_fallback` logs it as a provider error with backoff capped at 6 h. The cached hit list (7 days) replays the same bad hit first, so the comic is stuck on general web. In `resolve_leads` the same exception abandons every remaining lead.
    - The image fetch also goes through `web_search.read`'s provider accounting (`web_search.py:94-102`). One failed fetch of an image hosted on getcomics.org sets GetComics `access_blocked` permanently (no reset path exists). On a catalog host it marks that catalog unavailable for 1 h.
    - Fix: treat any read or decode failure of a candidate cover as "cover not verified" for that source, and keep cover-image fetches out of provider block marking.
    - Not Critical: the service does not crash, and no wrong data gets written.
  - F4 [Minor] `browser_search.py:255-272`. `verified_page_leads` retries temporary errors with no wait, which is a hot loop of up to 20 s, each pass making an SQLite read via `admitted()` plus a Playwright call. If the user closes the window during the read, it returns `[]` and `human_session` still returns `True`. `service()` then records `verified` with window `open`, because `minimize()` fails, and hands back a dead context. Every later `browser.search` fails inside `process()` (1 h cooldown each, one comic moved to `retry_wait`) until a Pause recreates the browser. The underlying cause is older (a `LensBrowser` is reused without a liveness check), but this commit adds a 20 s window for it.
  - F5 [Minor] `browser_search.py:243-248`. Inside the 600 s observe loop, any `PlaywrightError` while the page is open counts as temporary. A persistent error unrelated to navigation (a broken evaluate script, repeated `inner_text` timeouts) now surfaces as an `unfinished` timeout after 10 minutes with no `error_class`, instead of an immediate, classified failure. It never produces a false success.

### 4. Performance

- Status: Pass. Bounded: at most 8 leads and at most 9 hits per pass, 2 MB image cap. Remote cover images are not cached, so leads that pass the title and creator checks but fail the cover check are downloaded again on every daily pass, and each check decodes the local cover again. Acceptable at this scale.

### 5. State & Data Safety

- Status: Concerns
- Findings:
  - F1 [Major] `research.py:225-242`, `245-258` and `293-301`, with `app.py:113-122` and `providers.py:152-154`. The new identity route is weaker, and its evidence less independent, than `SOURCE_CONNECTORS.md:62` states. A wrong-book `Summary` can be written into an empty field of a live archive, the backup is removed once the write verifies, and the cover search is cancelled as `identified`. Probe-verified pieces:
    - **(a) Title match takes any segment between separators.** `title_matches` accepts every contiguous run of `|`, `::`, `-`, `–`, `—`, `·` segments and only rejects `#N`. Each of these returned `True`:
      - `"Saga - Issue 12 | Image Comics"` for `Saga`
      - `"Batman: The Killing Joke - Part 1 | DC"` for `Batman: The Killing Joke`
      - `"Hellboy: Seed of Destruction - Vol. 2 - Dark Horse"`
      - `"GCD :: Series :: Spawn"`
      - `"Venom (2018 - 2021) | Comic Series | Marvel"` for `Venom`
      - `"Ronin (2015) - Omnibus"`
      - `"The Sandman | Absolute Edition"`

      Issues, parts, volumes, omnibus or absolute editions and broad series pages all pass. The existing negative test only rejects `"Milkman Murders Vol. 2"` because it has no separator; `"The Milkman Murders - Vol. 2"` passes.
    - **(b) "Unnumbered" just means no number was found.** `parse_name` sets number `''` whenever there is no *terminal* number. That is not evidence of a one-shot, and `is_book()` (which exists so "single-issue series must not receive a collected edition's description") is never consulted. A single issue named without its number takes this route, and so do series pages.
    - **(c) Creator names are not validated.** `cover_hint['creators']` comes from the gemma3:4b model and is accepted if it is a string with at least two words and five letters. Probe: `['Marvel Comics','Spider-Man']` were both accepted as creators, and so was an echo of the title (`'Batman Year One'`). `Editor` counts as a creator field, so an editor-in-chief named on every page from that publisher satisfies the check.
    - **(d) For Lens leads, the checks are not independent.** Lens returns pages *because* their image looks like this cover, so "cover agrees" is close to automatic. The model-read creators come from the same image. Year is optional and matched anywhere in 24,000 characters of page text. For a Lens lead on a book with no known year and a stray model "creator", the only independent check left is the title-segment match from (a).

    Why Major, not Critical: every route still needs title, creator and `covers_agree`. Only empty fields are filled, and `Series`/`Number` values come from the local file, so no existing data is lost. Sergei's "search match alone" rule technically holds.

    Ender's starting points:
    - Accept a title segment only when the other segments are a site name, a format word or a year. Reject segments carrying issue, part, volume or chapter numbering, and series pages.
    - Require `is_book()` or an explicit one-shot signal before taking the unnumbered route.
    - Drop `Editor` from the creator fields.
    - Reject model "creators" that match the title, the publisher or a non-person shape.

    A product call for Sergei: should Lens-sourced leads need one signal that does not come from the cover?
  - F6 [Minor] `cover_tasks.py:106-124`. `record_verified_page` checks the task state in one transaction. `record()` then runs `INSERT OR REPLACE … 'leads_found'` (`:45`) in a separate one. A discovery `identified()` in between gets overwritten from `not_needed` to `leads_found`; the same check-then-write gap already exists in `process()`. `record()` also replaces any saved `reverse_image_matches`. So a stale or expired post-check results page can replace real leads and restart the 30-day clock. Impact is low: `claim()` ignores `leads_found`, and the leads stay unverified.

### 6. Input Handling

- Status: Concerns. Model output (`creators`, `publisher`) is type-checked but its content is not (F1c, F3). Post-check links go through `normalize_links` (HTTPS only, no Google hosts, no credentials, at most 10, titles cut to 300 characters) and are checked again in `record()`. A missing or malformed `verification_task` is rejected without raising an error.

### 7. Maintainability

- Status: Concerns
- Findings:
  - F8 [Minor] `browser_worker.py:52-114`. The outcome now depends on four interacting flags (`blocked`, `fallback_blocked`, `searched`, `failed`), a re-raise inside a nested `try` for the daily cap, and the order of the `elif` branches. An explicit outcome value (searched / failed / held) would make the "a search that never ran is not a result" rule enforceable by construction.

### 8. Doc/Code Drift

- Status: Concerns
- Findings:
  - F9 [Minor] `SOURCE_CONNECTORS.md:62`: "Issue identity checks reject broad series pages" and "a numbered issue title never matches an unnumbered book" do not hold for numbering written without `#` or for series and part pages (F1a). "A publisher is written only when the page names it" overstates the check for one-word publishers (F3).

### 9. Build & Release Hygiene

- Status: Pass. No secrets or generated files committed (`__pycache__`, `data/`, `work/` and `scratch/` are gitignored, and the tree was clean). `VERSION` and `CHANGELOG` move in Sully's bump commit, not in this range (see Header). Tool has no lockfile.

---

## Patterns

Both v0.1.x releases add more ways for the verifier to accept a match while the docs describe stricter guarantees. The pixel/edge cover check (`automatic.py:41-60`) carries most of the weight, yet it is not independent for reverse-image leads. A small table-driven test set of real page-title shapes would catch the next widening before release: numbering without `#`, `Part N`, `Vol. N`, series pages, omnibus and absolute editions, foreign editions.

---

## Verdict

- Total Critical: 0
- Total Major: 2 (F1, F2)
- Total Minor: 7 (F3, F4, F5, F6, F7, F8, F9)
- Safety-floor violations in the reviewed range: 0

Round-1 verdict for `30dad02`, superseded by Rounds 2-5 below: RELEASE CLEAR. The current verdict line is in Round 5.

Major and Minor findings go to Ender for the next cycle. F1 includes a product question for Sergei: should Lens-sourced leads need one signal that does not come from the cover before a write? Futaba's behavior verdict is separate.

| # | Sev | Dim | file:line | Finding | Next-cycle action |
|---|-----|-----|-----------|---------|-------------------|
| F1 | Major | 5 State & Data | `research.py:225-301` | Title match takes any separator segment; "unnumbered" means no number was found; creator names are not validated; the cover check is near-automatic for Lens leads | Limit title segments, require `is_book`/one-shot, drop `Editor`, validate model creators |
| F2 | Major | 3 Stability | `research.py:302-309` | `OSError` from cover decode escapes the `ValueError` handlers and aborts the lookup or leads; image-fetch failures can block GetComics or catalogs | Count any cover read/decode error as unverified; keep image fetches out of provider blocks |
| F3 | Minor | 2 Correctness | `research.py:266-270` | One-word publishers are "confirmed" by common words | Use the alias-canonical name; require a publisher-context match |
| F4 | Minor | 3 Stability | `browser_search.py:255-272` | Retries with no wait; a closed window still reports verified/open | Sleep on temporary errors; check `is_closed()` before reporting success |
| F5 | Minor | 3 Stability | `browser_search.py:243-248` | Persistent page errors masked as a 10-minute timeout | Limit how many temporary errors in a row are tolerated; keep the error class |
| F6 | Minor | 5 State | `cover_tasks.py:106-124` | Check-then-write race; stale post-check page replaces leads | Do the state check and write in one transaction |
| F7 | Minor | 2 Correctness | `browser_worker.py:63-82` | Daily cap reported as "could not finish" | Handle the cap outside the generic handler |
| F8 | Minor | 7 Maintainability | `browser_worker.py:52-114` | Four-flag outcome logic | Use an explicit outcome value |
| F9 | Minor | 8 Doc drift | `SOURCE_CONNECTORS.md:62` | Guarantees stated more strongly than the code enforces | Align the text after F1 and F3 |

## Method and limits

- Probes (my scratchpad only, run with `-B`, no bytecode written to the worktree):
  - `probe_titles.py`: `title_matches`, `creator_names`, `named` and `confirmed_publisher` cases above, with a stubbed `app` module.
  - `probe_lookup.py`: `general_lookup` with mocked search, page, image and local-cover reads, showing F2.
  - Pillow 12.2.0: `UnidentifiedImageError` is a subclass of `OSError`, not `ValueError`.
- Not run: the unit test suite, the service, any Playwright browser, any public request. The worktree's `data/` and `work/` were not touched. No live library or main-checkout file was read for testing.
- Not verified: real Google post-check redirect targets, and where GetComics hosts its og:image (F2's GetComics consequence applies only if that host is getcomics.org).

---

# Round 2 (937d7e1)

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-13
Tool: Comics Meta Organizer
Release: v0.1.2 (patch)
Fix-round range: 30dad02abb8ce36e2b64da73b889e873afedc4f3..937d7e1116c002666f59bef4c14a035242c003ae
  (one commit, 27 files, +1447 / -125)
Full re-check: cb0ee1432f447c7847e228c0674721166fb3df21..937d7e1 for F1-F9 (31 files, +2226 / -97)
Worktree / branch: WIP/Comics Meta Organizer-lens-fix, fix/lens-v0.1.2
  (clean except the two untracked review and QA reports)
Stand-down dimensions: none; Electron checks do not apply
```

`VERSION` still reads `0.1.1`. As in round 1, this clearance covers `937d7e1` plus Sully's version and changelog bump commit. Any other code or test change needs a fresh look.

## Summary

Round 1's two Majors are mostly fixed:
- F2 is closed. A candidate cover that cannot be fetched or decoded now counts as "not verified", the lookup continues, and no provider gets blocked.
- F1 is mostly closed. Issue, part, volume, series and edition page titles are rejected. A file with no issue number needs a whole-book signal. `Editor`, company names and echoes of the title no longer count as creators. One-word publishers are no longer written.

All seven round-1 Minors are closed or reduced. The new tests are real guards: run against `30dad02`, 30 of the 42 tests in the four new modules fail.

The fix round opens one new hole (F10, Major, probe-verified). A comic whose ComicVine issue disagrees with its embedded identity (`identity_conflict`) is supposed to get no field writes while the conflict stands. That holds only on the first pass. On the next pass, the remembered evidence is reused, ComicVine is never asked again, and empty fields are written.

The reuse hole is older than this round. But before `937d7e1` it was reachable only for conflict comics with an empty Summary. Now every conflict comic searches every source, so every conflict comic can reach it.

I found no Critical finding and nothing on the safety floor. F10 does not overwrite existing values, and what it writes is checked against the embedded identity, the same check every unconflicted comic gets. It is new exposure from this round and cheap to fix, so I recommend fixing it before the v0.1.2 deploy, even though it does not block.

## Focus-area answers

1. **F1: can a wrong-book page still fill Summary?** Only when the other page's cover agrees with the local cover.
   - **Rejected now (probe):** "Book Two", "Chapter Three", "Second Issue", "Act 1", "Part One", "Vol. 2", "(2018 - 2021)", "(2018-)", "Absolute Edition", "Hardcover Collection" and "The Complete Story".
   - **Whole-book signal works (tests):** a 24-image archive does not match an "HC" page, and a 60-image archive does.
   - **Still passes (F11, Minor):**
     - **Subtitles as site names.** A subtitle of another book counts as a "site name": "The Sandman - Overture \| DC" matches *The Sandman*, and "Spawn - Godslayer" matches *Spawn*.
     - **Person-shaped non-creators.** A cover-read "creator" only has to look like a person. Character names ("Bruce Wayne", "Harley Quinn"), places ("Gotham City") and blurbs ("New York Times Bestseller", "Eisner Award Winner") all pass.
     - **Ender's residual.** A book-signalled file can match a series landing page with no URL marker. Fandom pages and DC's `/comics/<slug>` pages are examples.
   - **End-to-end probe:** with cover agreement mocked, all four shapes verify.
   - **Ender's residual is Minor.** The page describes the right work. The field must be empty. The synopsis review still runs. The harm is a series-wide teaser on a Vol. 1 book.
   - **What now protects against a wrong book.** It needs the same cover art on the other page. The near-blank guard and the 0.94/0.80 correlation thresholds make that unlikely, except for same-art reprints and editions.
   - **Lens leads.** For a Lens lead, the cover check is near-automatic, and the creator check can be met by a name or blurb read from that same cover. So the checks that stay independent are the exact title and the file's whole-book signal.
   - **Open product question.** Round 1's question is still Sergei's to answer, though it matters less now: should Lens leads need one signal that does not come from the cover?
2. **F2 closed?** Yes.
   - `cover_agrees` (`research.py:447-460`) turns any read or decode error into "not verified" and logs the error class. It re-raises only `PauseRequested`.
   - `web_search.read(..., mark_failures=False)` raises a plain `ValueError` before any provider marking.
   - A successful image read still marks GetComics or a catalog `available`. That cannot clear a block, because `reserve()` refuses a blocked provider before any read.
   - GetComics's 5-minute interval means a GetComics-hosted image can never verify in the same pass as its page. That is a missed match only, and it predates this round.
3. **identity_conflict now searches everywhere: risk?** Two parts.
   - **(a) The write block does not survive the next pass** (F10, Major). See dimension 5.
   - **(b) Filling an empty Summary during a conflict** is the stated, documented behavior. Its risk is Minor (F12):
     - The Summary source is checked against the embedded identity. For a numbered comic, the general-web hinted route (`research.py:489`) needs no creator and no cover. So nothing tests which side of the conflict the archive's pages actually match.
     - After the Summary write, the outcome becomes `queued` (`automatic.py:370`). The comic leaves the dashboard's unresolved count until a later pass finds the conflict again.
     - `cover_tasks.identified` (`automatic.py:296`) also cancels its Lens search.
4. **`relabel_cover_tasks.py`: data safety.** Pass. Each property checked:
   - **Transaction.** One `BEGIN IMMEDIATE` with explicit `COMMIT`/`ROLLBACK`.
   - **Paused-only guard.** The paused-and-acknowledged check runs inside the write lock, so the workers cannot resume mid-run.
   - **Backup first.** Backup rows are inserted before the update, and the two counts are compared. A mismatch rolls everything back.
   - **Dry run.** Opens the catalog read-only (`mode=ro`), and refuses a missing catalog without creating one.
   - **Idempotence.** A second `--apply` is refused while a backup exists.
   - **Rollback.** Restores only rows still exactly as relabelled (`pending`, the queued detail and the same `updated`). Rows that moved on are left alone. The backup table is dropped in the same transaction.

   Ender's five tests pass. Nits are in F14.
5. **Holds and atomic writes: hang, starvation, lost update?** None found.
   - **Daily cap.** It holds until the next UTC midnight (`browser_worker.py:56-83`, cap at `:66-68`), with no cooldown and no `browser_error`. The worker sleeps at most 1 h per check (`browser_worker.py:245`), and Pause or a verification request wakes it.
   - **Queue order.** The head task is claimed again hourly. `release()` gives it back with its original state and `updated` (guarded by `state='searching'`), so it keeps its place.
   - **Bounded page errors.** 30 errors in a row, or 60 s of them, ends the session and records the error class. The counter resets after a clean read.
   - **Post-check read.** It waits 0.5 s between retries and stops after 20 s.
   - **Closed window.** A window closed after the check is recorded as `closed`, and the next search reopens the browser.
   - **Atomic record.** The state and signature check and the evidence merge share one `BEGIN IMMEDIATE` (`cover_tasks.py:51-69`). `merge_evidence` makes no database call, so it cannot deadlock itself. Discovery's `save_evidence` takes the same lock.
   - **Residuals (F13):** the merge keeps earlier leads only when the new page has fewer than 10 links, and `finish()` in `process()` still checks and writes in separate steps.

## Round-1 findings at 937d7e1

| # | Round 1 | Now | Evidence |
|---|---------|-----|----------|
| F1 | Major | Mostly closed; residual is F11 (Minor) | `probe_identity.py`, `probe_verify_e2e.py`, `test_identity_rules` (17 of 21 fail on `30dad02`) |
| F2 | Major | Closed | `research.py:447-460`, `web_search.py:99`, `test_cover_checks` (4 of 6 fail on `30dad02`) |
| F3 | Minor | Closed. "Image", "Boom", "Dark" and "marvelous" no longer confirm a publisher; canonical names are written | `probe_identity.py` |
| F4 | Minor | Closed. 0.5 s pause; a closed window is recorded `closed`; the browser reopens on the next search | `browser_search.py:284`, `lens_verification.py:164-168` |
| F5 | Minor | Closed. Capped at 30 errors or 60 s, error class kept | `browser_search.py:248-259` |
| F6 | Minor | Closed for `record()`; residual is F13 | `cover_tasks.py:34-68` |
| F7 | Minor | Closed. The cap is a `Held` outcome with no cooldown or error | `browser_worker.py:66-68` |
| F8 | Minor | Closed. Explicit `SEARCHED`, `FAILED` and `Held` outcomes | `browser_worker.py:38-48` |
| F9 | Minor | Replaced by F15 | — |

## Rubric (fix round)

Severity tags and the always-blocking safety floor: `Team/Docs/ProcessRules.md` § Severity definitions.

### 1. Security

- Status: Pass. No new shell-out or file-delete code. The relabel script's SQL is parameterized; the only interpolated name is its own constant table name. Cover fetches still go through `validate_url`. No secrets added or logged.

### 2. Correctness & Logic

- Status: Concerns. F10 (see dimension 5), F11, F12.
- Findings:
  - F11 [Minor] `research.py:298-303` (`site_segment`) and `research.py:382-386` (`person`). F1's remaining gaps, each probe-verified and each still needing a cover agreement:
    - **(a)** Any segment with no digits and no listed word counts as a site name, so a subtitle naming a different book passes.
    - **(b)** Cover-read "creators" that look like people but are not creators pass: characters, places, blurbs.
    - **(c)** A series landing page with no URL marker matches a book-signalled file whose cover is the first-issue art (Ender's residual).

    Starting points for Ender:
    - Accept a non-format, non-year segment only when it is a known site or publisher name, or appears in the page's host.
    - For model-read names, require that they appear near a credit word on the page ("by", "writer", "art"), not just anywhere.
  - F12 [Minor] `automatic.py:339-370`, `research.py:489`. Filling an empty Summary during a conflict: nothing tests which side of the conflict the pages match, the `identity_conflict` outcome is hidden after the write, and the Lens search is cancelled (answer 3b).
    - Suggest `require_cover=True` for any source used while a conflict stands.
    - Name the conflict in the `Notes` line.

### 3. Crash / Stability Safety

- Status: Pass. F2, F4 and F5 are closed. I found no new unhandled exception class.
- The new code catches what it should:
  - `archive_pages` catches `OSError`, `ValueError` and `BadZipFile`.
  - `cover_agrees` catches everything except Pause.
  - A JSON decode error inside `record()` comes back as a `ValueError`, which `record_verified_page` swallows. In `process()` it falls to the worker's generic handler.

### 4. Performance

- Status: Pass.
- `archive_pages` opens the zip once per candidate, and only for unnumbered files on a page with a format word.
- Conflict comics now share the 100-a-day Lens budget with unidentified ones. That is a product trade-off Sergei chose, noted here.

### 5. State & Data Safety

- Status: Concerns
- Findings:
  - F10 [Major] `automatic.py:190-199`, `:212`, `:330-331`. The `identity_conflict` write block is bypassed on the next pass by evidence reuse.
    - **Pass 1:** the conflict blocks field writes, but `research_runtime.remember` saves the verified result with `issue=None` (`:330`).
    - **Pass 2:** `research_runtime.reuse` returns that result (`:190`), and `issue` is read back as `None` (`:193`). ComicVine is skipped because `external` is already set (`:199`). So `conflict` is `False` (`:212`). The plan at `:331` writes the empty fields with `Notes: "Automatic verified lookup ... Issue or edition identity checked against the source."`
    - **Probe** (`probe_conflict_pass2.py`, real `reuse`/`remember`, real 2-image CBZ, sources and ComicVine mocked):
      - At `937d7e1`, a conflict comic that already has a Summary goes `identity_conflict` → `queued {Publisher}` on pass 2, with zero ComicVine calls.
      - At `30dad02`, the same comic stays `identity_conflict` on both passes, because it was never searched.
      - At both commits, a conflict comic with an empty Summary that a provider verifies writes on pass 2. So the hole predates this round; this round opens it to every conflict comic and to web, saved-lead and Lens sources.
    - **Which fields.** Any empty field the source verified. `Publisher` from web or leads; for a provider such as Metron, possibly more. When the embedded `Number` is empty, the filename's number.
    - **Why Major, not Critical:**
      - Only empty fields are filled, and no existing value is lost.
      - The values are checked against the embedded identity, the same standard any unconflicted comic gets.
      - It breaks Sergei's stated rule ("conflict still blocks field writes"), on live archives whose backup is deleted once the write verifies.
    - **Ender's starting points:**
      - Recompute the conflict on reuse whenever `Web` carries a ComicVine ID, or store the conflict in `verified_evidence` and refuse field plans from it.
      - Add a two-pass test with real `reuse`/`remember`. The current test mocks both, so it cannot see this.
  - F13 [Minor] `cover_tasks.py:57-62` and `browser_worker.py:140-143`. Two leftover gaps:
    - A post-check page that yields 10 links still pushes out every earlier lead, despite the comment at `cover_tasks.py:136-137`.
    - The `finish()` paths in `process()` still check and then write in separate steps. A source that identified the comic in between gets overwritten to `retry_wait`, which corrects itself at the next `claim()`.
  - F14 [Minor] `relabel_cover_tasks.py`. All are data-safe:
    - **(i)** v0.1.2 still writes the same legacy detail for genuine empty searches (`browser_worker.py:140`). The "run before starting v0.1.2" step is not enforced, and a late run relabels genuine results, costing one extra search each.
    - **(ii)** The `ROLLBACK` in the `except` can itself raise if SQLite already rolled back. That hides the original error behind a CLI traceback.
    - **(iii)** The backup table can only be retired by `--rollback`.

### 6. Input Handling

- Status: Concerns. Model output is now filtered by shape, but its meaning is not checked (F11b).

### 7. Maintainability

- Status: Pass. Outcomes are now explicit (F8 closed). `NOT_SITE_WORDS`, `NOT_PERSON_WORDS` and `PUBLISHERS` are block-lists that will need to grow with new page shapes. No finding.

### 8. Doc/Code Drift

- Status: Concerns
- Findings:
  - F15 [Minor] (replaces F9) Docs that still promise more than the code does:
    - `SOURCE_CONNECTORS.md:64` says other segments never match. Subtitles of other books do (F11a).
    - `SOURCE_CONNECTORS.md:66` says cover credits are "not ... a character". They can be (F11b).
    - `SOURCE_CONNECTORS.md:71` says "While that conflict stands no metadata fields are written". That holds only until the next pass (F10).
    - `SYNOPSIS_POLICY.md:8` says "series ... pages never supply a synopsis". Ender's residual is exactly that case.
    - `README.md:57` says the relabel requeues tasks "in their original order" and that `--rollback` "restores them exactly":
      - v0.1.1 had already reset each task's queue time, so the order kept is the order the searches were blocked in.
      - Rollback skips rows that have moved on.
    - The README's "fixtures in temporary folders they remove afterwards" is not fully true. `tests/test_manual_backup_cleanup.py` still leaves an empty `scratch/manual-backup-cleanup-2026-10-10` folder in the checkout. It is gitignored.

### 9. Build & Release Hygiene

- Status: Pass.
- Tests no longer touch `data/` (`test_suite_isolation`).
- The full suite on an isolated export of `937d7e1` ran 437 tests: OK, 33 skipped.
- No secrets or generated files are committed. `VERSION` and `CHANGELOG` move in Sully's bump commit.

---

## Verdict (Round 2, 937d7e1)

- Total Critical: 0
- Major open: 1 (F10)
- Minor open: 5 (F11, F12, F13, F14, F15)
- Closed since round 1: F2, F3, F4, F5, F7, F8. F1 is reduced to F11, F6 to F13, and F9 is replaced by F15.
- Safety-floor violations in the range: 0

Round-2 verdict for `937d7e1`, superseded by Rounds 3-5 below: RELEASE CLEAR. The current verdict line is in Round 5.

No Critical finding blocks. F10 is new exposure from this round and cheap to fix; I recommend Ender fixes it before the v0.1.2 deploy. Open product question for Sergei, carried from round 1: should Lens leads need one signal that does not come from the cover? Futaba's behavior verdict is separate.

| # | Sev | Dim | file:line | Finding | Next-cycle action |
|---|-----|-----|-----------|---------|-------------------|
| F10 | Major | 5 State & Data | `automatic.py:190-212`, `:330-331` | The conflict write block is bypassed on the next pass by reused evidence; ComicVine is not asked again | Recompute or store the conflict on reuse; add a two-pass test with real reuse |
| F11 | Minor | 2 Correctness | `research.py:298-303`, `:382-386` | Subtitles count as site names; characters and blurbs count as creators; series landing pages with no URL marker match | Limit site segments to known sites or the host; require a credit word near model-read names |
| F12 | Minor | 2 Correctness | `automatic.py:339-370`, `research.py:489` | A Summary written during a conflict has no cover check, hides the conflict outcome and cancels the Lens search | Require a cover check while a conflict stands; name the conflict in Notes |
| F13 | Minor | 5 State | `cover_tasks.py:57-62`, `browser_worker.py:140-143` | A 10-link post-check page still pushes out earlier leads; `finish()` still checks and writes in separate steps | Keep earlier leads first or raise the cap; add a state guard to `finish()` |
| F14 | Minor | 5 State | `relabel_cover_tasks.py:82-117` | "Run before v0.1.2" not enforced; `ROLLBACK` can hide the original error; no way to retire the backup | Filter by deploy time or a distinct detail; guard the `ROLLBACK` |
| F15 | Minor | 8 Doc drift | `SOURCE_CONNECTORS.md:64,66,71`, `SYNOPSIS_POLICY.md:8`, `README.md:57` | Docs promise more than the code enforces | Align after F10 and F11 |

## Method and limits (Round 2)

- **Read:** every line of the fix-round diff, plus the code it depends on:
  - `automatic.discover` (reuse, remember, conflict and Summary paths)
  - `research_runtime.reuse`/`remember`
  - `source_scheduling.useful`/`due`
  - `cover_tasks`, `browser_worker`, `lens_verification.service`
  - `LensBrowser` open, search and close
  - `getcomics` and `publisher_catalogs` `reserve` and `mark`
  - `pause_control`
  - the new and changed tests
- **Exports:** `git archive` of `937d7e1` and `30dad02` into my scratchpad. Nothing ran inside the worktree. No bytecode was written (`-B`, `PYTHONDONTWRITEBYTECODE`).
- **Suite:** the full suite on the `937d7e1` export ran 437 tests: OK, 33 skipped.
- **Negative control:** I ran the four new test modules against the `30dad02` code. 30 of their 42 tests fail or error there; all pass at `937d7e1`.
- **Probes:**
  - `probe_identity.py`: `title_format`, `SERIES_URL`, `creator_names`, `confirmed_publisher`.
  - `probe_verify_e2e.py`: the four F11 shapes, with cover agreement mocked.
  - `probe_conflict_pass2.py` and its `_base`, `_summary` and `_provider` variants: two `discover` passes with real `reuse`/`remember` on a real CBZ, run on both commits.
- **Not run:** the service, any browser, any public request. The relabel script was not run against any real catalog. The main checkout, the `-m1` worktree and live data were not touched.
- **Not verified:**
  - How many live comics are in `identity_conflict`.
  - Which fields a live provider (such as Metron) would return for them.
  - Whether real Fandom or publisher series pages use the first-issue cover as their og:image.

---

# Round 3 (b13c30c)

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-13
Tool: Comics Meta Organizer
Release: v0.1.2 (patch)
Fix-round range: 937d7e1116c002666f59bef4c14a035242c003ae..b13c30cce286444869a61a46033e49d9a7a78d4b
  (one commit, 9 files, +343 / -29)
Range covered by rounds 1-3: cb0ee1432f447c7847e228c0674721166fb3df21..b13c30c
Worktree / branch: WIP/Comics Meta Organizer-lens-fix, fix/lens-v0.1.2
  (HEAD b13c30c; clean except the two untracked review and QA reports)
Stand-down dimensions: none; Electron checks do not apply
```

`VERSION` still reads `0.1.1`. This clearance covers `b13c30c` plus Sully's version and changelog bump commit. Any other code or test change needs a fresh look.

## Summary

- **F10 is closed for the cause it reported.** When reused evidence has no saved issue and `Web` names a ComicVine issue, discovery now asks ComicVine again. A saved issue is reused only if its id matches `Web`. With the real `app.api` and its SQLite cache, pass 2 stays `identity_conflict` and makes no network request (S1 below).
- **F12 is mostly closed.** While a conflict stands, these all run with `strict`: saved and Lens leads, general web, wiki leads, GetComics, and the three publisher catalogs. That closes the hinted-publisher route and GetComics's book-only route. A Summary-only plan keeps the comic at `identity_conflict`.
- **F11 is reduced.** The blurbs and places on the new list are rejected.
- **No regression found.** The full suite passes (452 tests, OK, 33 skipped). 9 of the 15 new tests fail on `937d7e1`; the other 6 are positive controls. In every probe scenario, `b13c30c` behaves at least as safely as `937d7e1`.

**The outage question: yes, fields can still be written while a conflict stands (F16, Major, probe-verified).** The re-check fails open. When ComicVine raises, `issue` becomes `None` and `conflict` becomes `False`, so the comic is handled as unidentified:
- **With reused evidence,** the saved fields are written.
- **With no evidence,** every source runs without `strict`, and any hit is written.

This happens on any pass where the cache cannot answer and ComicVine cannot be reached:
- the cache entry is older than 30 days and the request fails;
- the global cooldown is active (5 minutes after any failure, 1 hour after a 429);
- the hourly budget is spent; or
- the API key is missing. A missing key also hides a fresh cached conflict, because `app.api` checks the key before it reads the cache.

The root cause predates v0.1.2. v0.1.1 (`2b5f975`) also writes when a lead verifies during an outage (S5). This fix narrows the bypass from every reuse pass to outage passes only. The docs now state the block without that condition.

**Why Major, not Critical:**
- Only empty fields are filled, and the values agree with the embedded identity.
- In the reuse case, those values passed the strict check on the pass that found the conflict.
- Nothing is overwritten, and nothing touches the safety floor.

I recommend fixing it this cycle. It is the same rule F10 was about, and the fix is small.

## Focus-area answers

1. **Is F10 closed?** Yes, for its reported cause.
   - **Round-2 probes** (`probe_conflict_pass2`, `_provider`, `_summary`). On `937d7e1`, pass 2 gives `queued {Publisher}` with 0 ComicVine calls. On `b13c30c`, pass 2 gives `identity_conflict` with no field plan, after asking ComicVine again.
   - **`probe_r3_outage.py` S1.** This uses the real `app.api`; only `urlopen` is replaced. Pass 2 is answered from the cache, with 0 network requests while the network is down. The "30-day cache" claim holds.
   - **Ender's new test cannot see this.** It mocks `app.api` entirely, so it covers neither the cache nor an outage.
2. **ComicVine outage.** Each scenario runs pass 1 then pass 2. Pass 1 found the conflict unless the row says otherwise:

   | Scenario | `937d7e1` | `b13c30c` | v0.1.1 `2b5f975` |
   |---|---|---|---|
   | S1 cache fresh, network down | queued {Publisher} | **identity_conflict**, 0 requests | identity_conflict |
   | S2 cache older than 30 days, network down | queued {Publisher} | queued {Publisher} | no write (no saved evidence) |
   | S3 cache older than 30 days, cooldown active | queued {Publisher} | queued {Publisher}, 0 requests | no write (no saved evidence) |
   | S4 cache fresh, API key missing | queued {Publisher} | queued {Publisher}, 0 requests | no write (no saved evidence) |
   | S5 no saved evidence; cache expired; a lead verifies while ComicVine is down | queued {Publisher}, leads non-strict | same | same |
   | S6 pass 1 verifies a lead non-strict during an outage; pass 2 ComicVine reports the conflict | queued {Publisher, Summary} | identity_conflict + Summary from that non-strict evidence | queued {Publisher, Summary} |

   - The v0.1.1 "no write" rows only mean that v0.1.1 never saved evidence for these comics. Given a lead on that pass, it writes, as S5 shows.
   - The ComicVine failure is recorded only in `provider_waits`. `lookup_error` stays `None`, so the record shows no error and the retry is not brought forward.
3. **Regressions from the fix.** None found.
   - **Matching comics.** A saved matching issue is still reused without a request (Ender's test). The positive controls still write.
   - **Extra requests.** Only reused evidence with no saved issue and a `Web` id is re-checked: conflict comics, and comics whose first ComicVine lookup failed. These are cache hits except about once per 30 days per comic.
   - **No strict leak.** Every call site passes `strict=conflict`. The non-conflict `free_fallback` at `automatic.py:296` stays non-strict, and the positive-control test confirms it.
   - **Strict only narrows matches.** In the catalog book branch (`publisher_catalogs.py:118`), strict drops the ISBN route, and a numbered "book" can no longer match there. Both only cost a missed match.
   - **The forced outcome is safe.** `identity_conflict` at `automatic.py:388` changes only the saved record. `worker.enqueue` and `record_check` still use the local `outcome`, so the Summary plan still runs.
   - **Lens and duplicates.** `cover_tasks.claim` (`cover_tasks.py:87`) no longer treats such a comic as identified, which is intended. `order_rows` excludes pending plans, so no duplicate plan is made.
4. **Does strict cover every route?** Two routes are missed, and the strict check itself is weak for Lens leads:
   - **(a) Coffin Comics shop.** `research.publisher_lookup` (`automatic.py:250` → `research.py:122-165`) still runs without `strict` during a conflict, and its page text can supply the Summary. It is narrow: Coffin Comics only.
   - **(b) Earlier evidence.** Reused evidence is not re-verified when a conflict appears after it was saved. That covers v0.1.1 live data (`MATCHER_VERSION` is still 9, and reuse lasts 30 days) and passes where ComicVine failed (S6). Its sources then supply the Summary during the conflict.
   - **(c) Lens leads.** A character name read from the cover can meet the named-creator check (F11b), and for a Lens lead the cover check is near-automatic. So strict adds little beyond the exact `#N` title.
   - **Notes.** The `Notes` line still does not name the conflict.
5. **F11.**
   - **Now rejected (probe):** "New York Times Bestseller", "Eisner Award Winner", "Gotham City", "Star City", "Harvey Award", "Bestselling Author".
   - **Still accepted:** "Mature Readers Only", "Parental Advisory", "First Printing", "Free Preview", "Netflix Original", "New York", "Los Angeles", and every character name.
   - **Unchanged:** subtitles still count as site names, and series landing pages still match. The docs now say both are not yet handled.

## Earlier findings at b13c30c

| # | Round 2 | Now | Evidence |
|---|---------|-----|----------|
| F10 | Major | Closed for its reported cause; the outage residual is F16 | Round-2 probes, S1; `test_identity_conflict_reuse` (2 of 4 fail on `937d7e1`) |
| F11 | Minor | Reduced; open | `probe_identity.py` diff, `probe_r3_creators.py`; `probe_verify_e2e.py` now rejects the blurb shape |
| F12 | Minor | Mostly closed; residuals (a)-(c) in answer 4; open | `test_identity_conflict_summary` (6 of 10 fail on `937d7e1`); S6 |
| F13 | Minor | Unchanged (outside this range) | — |
| F14 | Minor | Unchanged (outside this range) | — |
| F15 | Minor | Reduced; open | README relabel text fixed; `SOURCE_CONNECTORS.md:64,66` now name the subtitle and character gaps |

## Rubric (fix round)

Severity tags and the always-blocking safety floor: `Team/Docs/ProcessRules.md` § Severity definitions.

### 1. Security

- Status: Pass. No shell-out, path, delete, secret or network-surface change. `strict` only narrows verification.

### 2. Correctness & Logic

- Status: Concerns. F11 and F12 residuals (answers 4 and 5). No new finding.

### 3. Crash / Stability Safety

- Status: Pass. No new exception path. The re-check sits inside the existing `try`/`except Exception` (`automatic.py:199-210`). The new keyword arguments have defaults, and every caller is updated (grep).

### 4. Performance

- Status: Pass. At most one extra ComicVine request per affected comic per 30 days; all other re-checks are cache hits.

### 5. State & Data Safety

- Status: Concerns
- Findings:
  - F16 [Major] `automatic.py:199-218`, with `app.py:292-302`. The conflict write block fails open when ComicVine cannot answer.
    - **Mechanism.** The `except` sets `issue = None`, so `conflict` is `False` (`:217`). Reused evidence is then written at `:337-344`. Without evidence, every source runs non-strict and a hit is written.
    - **Ignored state.** The previous `identity_conflict` outcome is available in `previous` but is never checked.
    - **Key before cache.** `app.api` checks the key (`app.py:292-294`) before it reads the cache (`:296-302`).
    - **Probe:** S2-S5 in answer 2.
    - **Ender's starting points:**
      - When `Web` names a ComicVine issue and the lookup raised or returned nothing, make no field plans this pass and verify strictly. The provider wait already schedules the retry.
      - Alternatively, store the conflicting issue id and refuse field plans while `Web` still names it.
      - Read the cache before requiring the key.
      - Add tests with the real `app.api`, mocking only `urlopen`: an expired cache with `URLError`, an active cooldown, and a missing key.
  - F13 and F14: unchanged.

### 6. Input Handling

- Status: Concerns. The block-list for model-read creators is narrow (F11).

### 7. Maintainability

- Status: Pass. `strict` is threaded through each source by hand, so the next source added could miss it. Advisory only, no finding.

### 8. Doc/Code Drift

- Status: Concerns. F15, now narrower. Remaining overstatements:
  - `SOURCE_CONNECTORS.md:71`: "This also holds on later passes ... ComicVine is checked again first". This holds only while ComicVine answers (F16).
  - `SOURCE_CONNECTORS.md:71`: "A web page used for it needs a known creator and an agreeing cover". Not true for the Coffin Comics shop route or for reused evidence (F12 a, b).
  - `SOURCE_CONNECTORS.md:66`: "not ... a place or a cover blurb". Only the listed words are caught; "New York" and "Mature Readers Only" still pass.
  - Unchanged from round 2: `SYNOPSIS_POLICY.md:8` and the README sentence about test folders.

### 9. Build & Release Hygiene

- Status: Pass.
- Suite on an isolated export of `b13c30c`: 452 tests, OK, 33 skipped.
- No secrets or generated files are committed, and the commit has no attribution trailer.
- `VERSION` and `CHANGELOG` move in Sully's bump commit.

---

## Verdict (Round 3, b13c30c)

- Total Critical: 0
- Major open: 1 (F16)
- Minor open: 5 (F11, F12, F13, F14, F15)
- Closed this round: F10 (its reported cause)
- Safety-floor violations in the range: 0

Round-3 verdict for `b13c30c`, superseded by Rounds 4 and 5 below: RELEASE CLEAR. The current verdict line is in Round 5.

No Critical finding blocks. F16 is the same rule F10 was about, and the fix is small, so I recommend Ender fixes it before the v0.1.2 deploy.

Open product question for Sergei, carried from rounds 1 and 2: should Lens leads need one signal that does not come from the cover? F12(c) now makes it matter during conflicts too. Futaba's behavior verdict is separate.

| # | Sev | Dim | file:line | Finding | Next-cycle action |
|---|-----|-----|-----------|---------|-------------------|
| F16 | Major | 5 State & Data | `automatic.py:199-218`, `app.py:292-302` | Conflict block fails open when ComicVine cannot answer (expired cache plus outage, cooldown, budget, or missing key) | Hold field plans when the `Web` lookup fails, or persist the conflict id; read the cache before the key; add real-`app.api` tests |
| F11 | Minor | 2 Correctness | `research.py:255-261`, `:298-303` | Block-list catches only listed blurbs and places; characters, subtitles and series pages still pass | Require a credit word near model-read names; limit site segments |
| F12 | Minor | 2 Correctness | `automatic.py:250`, `:345-376` | Coffin Comics shop route not strict; reused pre-conflict evidence not re-verified; Notes do not name the conflict | Strict for `publisher_lookup`; store the strict flag with evidence; name the conflict |
| F13 | Minor | 5 State | `cover_tasks.py:57-62`, `browser_worker.py:140-143` | Unchanged from round 2 | As round 2 |
| F14 | Minor | 5 State | `relabel_cover_tasks.py:82-117` | Unchanged from round 2 | As round 2 |
| F15 | Minor | 8 Doc drift | `SOURCE_CONNECTORS.md:66,71`, `SYNOPSIS_POLICY.md:8` | Docs still overstate the outage case, strict coverage and the blurb filter | Align after F16 and F12 |

## Method and limits (Round 3)

- **Read:**
  - the whole fix-round diff and `automatic.discover` at `b13c30c`
  - `app.api`, `reserve_request`, `api_key` and `provider_wait`
  - `research_runtime.reuse` and `remember`
  - `research.publisher_lookup` and `verify_web_source`
  - `publisher_catalogs.verify` and `lookup`, and `getcomics.lookup`
  - outcome consumers: `coverage_priority`, `cover_tasks.claim` and the dashboard count
  - the three new or changed test modules
- **Exports:** `git archive` of `b13c30c`, `937d7e1` and `2b5f975` into my scratchpad (`senua_r2/r3_*`). Everything ran with `-B` and `PYTHONDONTWRITEBYTECODE`. Nothing ran inside the worktree.
- **Suite:** the `b13c30c` export ran 452 tests: OK, 33 skipped.
- **Negative control:** the three new or changed test modules on `937d7e1` code. 9 of the 15 new tests fail or error there; all pass on `b13c30c`.
- **Probes** (`senua_r2/probes/`):
  - The round-2 `probe_conflict_pass2`, `_provider` and `_summary`, run on `937d7e1` and `b13c30c`.
  - `probe_r3_outage.py`, scenarios S1-S6, run on `b13c30c`, `937d7e1` and `2b5f975`. It uses the real `app.api`, cache, cooldown and key lookup, with only `urllib.request.urlopen` replaced, plus real `reuse` and `remember` on a real CBZ.
  - `probe_identity.py` and `probe_verify_e2e.py` on both commits, with outputs diffed.
  - `probe_r3_creators.py`: 23 cover-read creator shapes.
- **Not run:** the service, any browser, any public request, any live catalog.
- **Not verified:**
  - how many live conflict comics have a ComicVine cache row close to expiry;
  - how often ComicVine cooldowns happen in Sergei's real runs;
  - whether v0.1.1 left live evidence for conflict comics that still have an empty Summary.

---

# Round 4 (6b5c876)

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-13
Tool: Comics Meta Organizer
Release: v0.1.2 (patch)
Fix-round range: b13c30cce286444869a61a46033e49d9a7a78d4b..6b5c876e0640f09b00635b542c5f0efd75828661
  (one commit, 7 files, +297 / -17)
Range covered by rounds 1-4: cb0ee1432f447c7847e228c0674721166fb3df21..6b5c876
Worktree / branch: WIP/Comics Meta Organizer-lens-fix, fix/lens-v0.1.2
  (HEAD 6b5c876; clean except the two untracked review and QA reports)
Stand-down dimensions: none; Electron checks do not apply
```

`VERSION` still reads `0.1.1`. This clearance covers `6b5c876` plus Sully's version and changelog bump commit. Any other code or test change needs a fresh look.

## Summary

- **F16 is closed.** No outage shape writes a field during a conflict any more. That covers an expired cache with the network down, an active cooldown, a spent hourly budget, and a missing key. A saved conflict is now known offline, and every other pass where ComicVine cannot answer holds every plan and searches strictly. My round-3 probe and a new real-`app.api` probe both confirm it, and Ender's tests now use the real client, as round 3 asked.
- **No write regression.** The full suite passes (463 tests, OK, 33 skipped). 9 of the 11 new tests fail on `b13c30c`; the other 2 are positive controls. The round-2 and round-3 probes give identical output on both commits.
- **New Major, F17: a held comic can starve (probe-verified).**
  - ComicVine answers a dead or mistyped Web id with "Object Not Found". `app.api` treats that as a provider failure: no cache entry and a 5-minute global cooldown.
  - That comic is asked again on every daily pass, so the cooldown starts again every day.
  - Any later comic in the same pass that needs a fresh ComicVine answer is deferred, and with a Web id it is now held.
  - Its retry is 24 h, so the next day the dead-id comic goes first again.
  - On `b13c30c`, a deferred comic with a verified lead sorted into the evidence tier the next day, got ahead, and was confirmed. `6b5c876` saves a held comic as `needs_identity_lookup`, which removes that escape.
  - The cooldown coupling itself predates this commit.
  - A missing key holds every Web-id comic for good once its cache entry expires.
  - Nothing is written wrongly. The cost is comics that never get written, and nothing tells Sergei why.

## Focus-area answers

### Ender's claims

1. **"`app.api` reads the cache before it requires the key."** True (`app.py:298-304`). R3 S4 and R4 day 3 (below) return a cached conflict with no key and 0 requests.
2. **"`conflict_issue` is persisted, known offline, dropped once ComicVine confirms a match."** True. This was checked with the real `discovery_state` over four simulated days:

   | Day | Condition | Outcome | Plan | `conflict_issue` |
   |---|---|---|---|---|
   | 1 | ComicVine reports the conflict | identity_conflict | none | saved |
   | 2 | Cache expired, network down | identity_conflict | none | carried |
   | 3 | Key removed, cache expired | identity_conflict (0 requests) | none | carried |
   | 4 | ComicVine up and now matching | queued {Title} | written | dropped |

   It is also dropped, safely, on any pass that is not a conflict:
   - Web removed: the comic then has no ComicVine id.
   - Web changed to another id: that pass holds.
   - An edit makes the embedded identity match the saved issue: that pass holds.
3. **"If the identity check can't answer, the pass holds every plan (fields and Summary), searches strictly, and the comic keeps its place."**
   - **Holds every plan: true.** Every plan site is gated:
     - the publisher plan, `automatic.py:268`;
     - the web plan, through the outcome change at `:349-350`;
     - the Summary, `:361`;
     - the ComicVine field plan, which needs `issue`.

     S2, S3 and S5 make no plan, and neither does S6 pass 1 with the local model available.
   - **Searches strictly: true.** In S5 and S6 pass 1, leads were called with `strict=True` (`False` on `b13c30c`). Every source call site passes `strict` (grep).
   - **Keeps its place: partly.** A held comic stays unwritten and stays eligible for Lens, since `cover_tasks.claim` skips only found outcomes. But a held comic with verified evidence is saved as `needs_identity_lookup`, so `order_rows` (`coverage_priority.py:61-68`) drops it out of the evidence tier. That is the second half of F17.
4. **"The Coffin shop lookup is strict during a conflict."** True (`research.py:134`). `publisher_lookup` has one caller, and it passes `strict`. The Sergei-approved exact-cover-hash list (`verified-sources.json`) still answers before the check, which is correct.

### Ender's open decisions

1. **An empty ComicVine answer counts as "can't check".** I agree; it fails closed.
   - **Probe.** A status-1 answer with empty results is cached for 30 days. The comic holds with 0 requests and does not affect other comics.
   - **A dead id is not this case.** ComicVine's documented "Object Not Found" status is 101, and `app.api` sends every status other than 1 (`app.py:333-334`) and every HTTP error (`:322`, `:326`) down the outage path. So a dead id gets no cache entry and a global cooldown (F17).
2. **A dead `Web` id now holds forever.** This is safe for that comic, but it has two costs the commit does not name:
   - **Cooldown.** One uncached request and a 5-minute global ComicVine cooldown every day, and later comics are held with it (F17).
   - **Visibility.** Nothing tells Sergei the Web link is dead. The record's `error` stays empty. The only trace is a provider wait reading "did not accept the request", and the dashboard shows ComicVine as "access rejected" after each try.

   Whether such a comic stays held for good is Sergei's call. The visibility and the cooldown are construction problems either way.

### Brief checks

1. **Can a held comic starve or loop?**
   - **Loop: no.**
     - A held comic never queues, so it never triggers the early `return True`.
     - A `ProviderDeferred` goes to `provider_waits`, not `error`, so the retry stays at 24 h. Other exceptions shorten it to 1 h (`provider_wait.retry_time`).
     - `cover_tasks.enqueue` does nothing when the signature is unchanged. The new-leads flag clears once the pass records `cover_leads`.
     - Per day, a held comic costs one ComicVine lookup, which is a cache hit unless the entry is expired or the id is dead. Its strict source searches are throttled by each source's own backoff.
   - **Starve: yes.** This is F17. Probe (`probe_r4_hold.py`, three simulated days):

     | Scenario | `b13c30c` | `6b5c876` |
     |---|---|---|
     | Control: B alone (valid Web id, uncached, ComicVine up) | queued day 1 | queued day 1 |
     | Dead-id A (status 101) sorts before B; B has a verified lead | Day 1: lead kept non-strict (`web_issue_found`). Day 2: B sorts ahead of A, ComicVine confirms it, queued | **Held all 3 days; B's ComicVine request is never made** |
     | Same, but B has no lead | Held all 3 days | Held all 3 days |
     | A answers status 1 with empty results | B queued day 1 | B queued day 1 |

   - The probe makes both comics due in the same pass. In real time, their retry clocks are set seconds to minutes apart in one pass, so B usually lands inside A's next cooldown as well. It escapes only if the gap drifts past 5 minutes. I did not measure this live.
2. **Does reading the cache before the key change any other caller?** Only when no key is set: cached answers now succeed instead of failing. I found no finding.
   - **Manual dashboard endpoints.** `/api/search`, `/api/issues`, `/api/preview` and `/api/apply` (`app.py:626-657`) now return cached results; uncached requests still get the key message. `/api/apply` can write from a cached issue. That data is the same a keyed run would use, and the write is still user-initiated.
   - **`lookup_unidentified`.** A fully cached search, issue list and issue chain can now identify a comic and queue the "Automatic match" write without a key. The checks are unchanged. The cover image fetch from ComicVine's image host now also runs without a key.
   - **Status displays.** `providers.comicvine_status` and `/api/state` still call `api_key()` directly, so they show not-configured while cached ComicVine data keeps feeding writes for up to 30 days. This is cosmetic.
   - **Nothing relied on the early raise.** No caller used it to detect a missing key, and the cache key never included the key.
3. **Is the `conflict_issue` persistence migration-safe for old records?** Yes.
   - **No schema change.** Records are JSON blobs (`discovery_state.save_one`); the new key is optional and is read with `.get`.
   - **Old records fail safe.** Probe on seven saved shapes, with ComicVine down and the cache expired:
     - These hold, with no plan and strict searches: no key (a pre-`6b5c876` record), a non-dict value, another id, and an issue that now matches the identity.
     - These keep the conflict: id only, `volume: None`, and an integer id.
     - Nothing raised.
   - **Lazy fill.** Conflict comics are due daily and the API cache lasts 30 days, so the first pass after deploy fills `conflict_issue` from cache for most of them.
   - **During an outage.** A legacy conflict record whose cache has already expired shows `needs_identity_lookup` until ComicVine answers. Both outcomes count as unresolved.
   - **Rollback.** An older build simply ignores the key.

## Earlier findings at 6b5c876

| # | Round 3 | Now | Evidence |
|---|---------|-----|----------|
| F16 | Major | Closed | R3 S2-S5 no longer write; S6 pass 1 is strict; R4 saved-conflict carry; 9 of 11 new tests fail on `b13c30c` |
| F11 | Minor | Unchanged; open | `probe_identity`, `probe_verify_e2e` and `probe_r3_creators` outputs identical on both commits |
| F12 | Minor | Reduced; open | (a) Coffin route closed. The S6 route is closed because outage passes are now strict. (b) remains for evidence saved before v0.1.2 or while the comic had no Web id. (c) unchanged. Notes still do not name the conflict |
| F13 | Minor | Unchanged (outside this range) | — |
| F14 | Minor | Unchanged (outside this range) | — |
| F15 | Minor | Changed; open | See dimension 8 |

## Rubric (fix round)

Severity tags and the always-blocking safety floor: `Team/Docs/ProcessRules.md` § Severity definitions.

### 1. Security

- Status: Pass. There is no shell-out, path, delete or secret change. The key check moved after the cache read, and the cache key never contained the key.

### 2. Correctness & Logic

- Status: Concerns. The F11 and F12 residuals remain. "Keeps its place" holds only partly (claim 3).

### 3. Crash / Stability Safety

- Status: Pass. `identity_matches` on a stripped saved issue reads only the two fields that are saved. Malformed saved shapes do not raise (probe). The new code sits outside the `try`, but every access is guarded (`isinstance`, `or {}`).

### 4. Performance

- Status: Concerns. F17: a dead Web id costs one uncached request and a 5-minute global cooldown per day.

### 5. State & Data Safety

- Status: Concerns
- Findings:
  - F17 [Major] `app.py:322-335`, `automatic.py:204-229`, `:349-350`, `coverage_priority.py:61-68`. A per-comic "not found" is handled as a provider outage, and the hold turns that into indefinite starvation.
    - **Mechanism.** ComicVine answers a dead or mistyped Web id with status 101 or an HTTP error. Either way, `app.api` starts a 5-minute global cooldown and caches nothing. The dead-id comic (A) is asked again on every daily pass. Any later comic (B) in that pass that needs a fresh answer is deferred by `reserve_request`. With a Web id, B is held (`:228`), and its retry is 24 h.
    - **Lost escape.** `order_rows` sorts by path within a tier. A held comic with evidence is saved as `needs_identity_lookup` (`:349-350`), so it no longer gets the `web_issue_found` tier that moved B ahead of A on `b13c30c`.
    - **Missing key.** The same shape applies when no key is set: once a Web-id comic's cache entry expires, nothing can ever answer, so it is held for good, with no field and no Summary from any source. A missing key is a recognised state (`not_configured`).
    - **Invisible.** The record's `error` stays empty. The provider wait reads as temporary.
    - **Pre-existing part.** The cooldown coupling: with no lead, B starves on `b13c30c` too.
    - **Why Major, not Critical.** It fails closed: no wrong write, no data loss, no crash.
    - **Probe:** brief check 1.
    - **Ender's starting points:**
      - Treat "Object Not Found" on `issue/4000-N` as a per-comic answer: no global cooldown, a cached negative entry, and a record saying "Web names a missing ComicVine issue".
      - Bring a comic held by a provider wait back at that wait's `retry_at`, not 24 h later. Alternatively, order held comics after the others in a folder.
      - Show the hold reason per comic.
      - Add a two-comic test with the real `app.api`.
  - F13 and F14: unchanged.

### 6. Input Handling

- Status: Concerns. The model-read creator block-list is narrow (F11).

### 7. Maintainability

- Status: Pass. `conflict`, `hold` and `strict` are named, and each is computed once. `strict` is still threaded through each source by hand, as noted in round 3.

### 8. Doc/Code Drift

- Status: Concerns. F15. This commit changes no docs.
  - `SOURCE_CONNECTORS.md:71`: "An empty Summary can still be filled". This is not true while a pass is held.
  - The hold itself is undocumented: no writes while ComicVine cannot answer for a Web-id comic, including the dead-id and missing-key cases.
  - The round-3 Coffin overstatement on `:71` is now resolved.
  - `SOURCE_CONNECTORS.md:87`: "ComicVine transient connection failures impose a shared five-minute cooldown". An "Object Not Found" answer also imposes it (F17).

### 9. Build & Release Hygiene

- Status: Pass.
- Suite on an isolated export of `6b5c876`: 463 tests, OK, 33 skipped.
- No secrets or generated files are committed, and the commit has no attribution trailer.
- `VERSION` and `CHANGELOG` move in Sully's bump commit.

---

## Verdict (Round 4, 6b5c876)

- Total Critical: 0
- Major open: 1 (F17)
- Minor open: 5 (F11, F12, F13, F14, F15)
- Closed this round: F16
- Safety-floor violations in the range: 0

Round-4 verdict for `6b5c876`, superseded by Round 5 below: RELEASE CLEAR. The current verdict line is in Round 5.

No Critical finding blocks. F17 fails closed. It costs writes that never happen, never a wrong write.

**Fix F17 before deploy?** That depends on whether the live library has comics with dead Web ids. A read-only count of records whose ComicVine provider wait reads "Metadata service did not accept the request." would settle it. I did not read live data.

**Open product questions for Sergei:**
- Should a dead Web id or a missing key hold a comic for good?
- Carried from rounds 1-3: should Lens leads need one signal that does not come from the cover?

Futaba's behavior verdict is separate.

| # | Sev | Dim | file:line | Finding | Next-cycle action |
|---|-----|-----|-----------|---------|-------------------|
| F17 | Major | 5 State & Data | `app.py:322-335`, `automatic.py:228`, `:349-350`, `coverage_priority.py:61-68` | A dead Web id's "not found" starts a daily global cooldown that holds later comics indefinitely; a missing key holds Web-id comics for good; neither is visible | Treat "Object Not Found" as a per-comic answer; retry held comics at the wait's time; show the hold reason; add a two-comic real-`app.api` test |
| F11 | Minor | 2 Correctness | `research.py:255-261`, `:298-303` | Unchanged from round 3 | As round 3 |
| F12 | Minor | 2 Correctness | `automatic.py:361-390` | Pre-v0.1.2 and no-Web-id evidence not re-verified when a conflict appears; Lens strictness weak; Notes do not name the conflict | Store the strict flag with evidence; name the conflict |
| F13 | Minor | 5 State | `cover_tasks.py:57-62`, `browser_worker.py:140-143` | Unchanged from round 2 | As round 2 |
| F14 | Minor | 5 State | `relabel_cover_tasks.py:82-117` | Unchanged from round 2 | As round 2 |
| F15 | Minor | 8 Doc drift | `SOURCE_CONNECTORS.md:66,71,87`, `SYNOPSIS_POLICY.md:8` | Hold undocumented; "empty Summary can still be filled" untrue while held; cooldown text omits the not-found case | Align after F17 |

## Method and limits (Round 4)

- **Read:**
  - the whole fix-round diff, and `automatic.discover` at `6b5c876`
  - `app.api`, `reserve_request`, `comicvine_status`, and the manual ComicVine endpoints
  - `provider_wait`, `source_scheduling.due`, `coverage_priority.order_rows` and `lookup_flags`
  - `discovery_state`, and `cover_tasks` `enqueue`, `claim` and `identified`
  - the new and changed test modules
- **Exports:** `git archive` of `6b5c876` into `senua_r2/r4_6b5c876`. The negative control `r4_negb13` is `b13c30c` code with the `6b5c876` tests. Everything ran with `-B` and `PYTHONDONTWRITEBYTECODE`; nothing ran inside the worktree.
- **Suite:** 463 tests, OK, 33 skipped.
- **Negative control:** of the 11 new tests, 9 fail or error on `b13c30c` code, and all 29 tests in the four conflict modules pass on `6b5c876`.
- **Probes** (`senua_r2/probes/`):
  - `probe_r3_outage.py`, S1-S6, on `6b5c876` and `b13c30c`.
  - `probe_r4_hold.py` (new). It uses the real `app.api`, `discovery_state`, `order_rows` and `due` logic, plus real reuse, remember and `cover_tasks`; only `urlopen`, the source calls and the local model are replaced. It covers:
    - the starvation variants;
    - the four-day saved-conflict carry;
    - seven saved-record shapes.
  - `probe_r4_nolead.py`: the starvation case with no lead, on both commits.
  - The round-2 and round-3 probes (`probe_conflict_pass2`, `_provider`, `_summary`, `probe_identity`, `probe_verify_e2e`, `probe_r3_creators`): output identical on `b13c30c` and `6b5c876`.
- **Not run:** the service, any browser, any public request, live data.
- **Not verified:**
  - **Status for a missing issue.** I did not check whether ComicVine serves "Object Not Found" with HTTP 200 or HTTP 404. Both reach a `cooldown(300)` branch.
  - **Dead Web ids.** How many live comics have one.
  - **Real retry gaps.** The real retry-clock gap between two comics checked in one pass.
- **Kept:** the exports and probes are kept for the follow-up round on F17.

---

# Round 5 (a73f43e)

## Header

```
Reviewer: Senua (Code Reviewer)
Date: 2026-10-13
Tool: Comics Meta Organizer
Release: v0.1.2 (patch)
Fix-round range: 6b5c876e0640f09b00635b542c5f0efd75828661..a73f43eaee9d0bb7ce9d928b877943b7131ea8a4
  (one commit, 3 files, +406 / -10)
Range covered by rounds 1-5: cb0ee1432f447c7847e228c0674721166fb3df21..a73f43e
Worktree / branch: WIP/Comics Meta Organizer-lens-fix, fix/lens-v0.1.2
  (HEAD a73f43e; clean except the two untracked review and QA reports)
Stand-down dimensions: none; Electron checks do not apply
```

`VERSION` still reads `0.1.1`. This clearance covers `a73f43e` plus Sully's version and changelog bump commit. Any other code or test change needs a fresh look.

## Summary

- **F17 is closed.** A dead Web id no longer starts a ComicVine pause, and the comics after it are no longer held behind it.
  - **Round-4 probe rerun.** The valid comic B is queued on day 1; on `6b5c876` it was held all 3 days. The dead id costs one request, then none for 7 days.
  - **Wait-end retry.** A held comic now comes back when its wait ends. After a 6-hour outage, all 40 held comics in the probe were queued within 57 minutes. On `6b5c876`, none were queued in the 3 hours after recovery.
- **No wrong-write regression found.**
  - A dead id is written only from a fresh lookup that passed strict checks, from the catalog providers' own checks, or from Sergei's approved exact-cover list. Evidence saved earlier is never written for it.
  - A saved conflict still blocks. Hold and conflict passes still write nothing.
  - The publisher-plan change affects only dead-id comics. Under strict, only the approved list can answer.
  - **Suite.** 475 tests, OK, 33 skipped. 10 of the 12 new tests fail on `6b5c876`; the other 2 are positive controls.
  - **Earlier probes.** The round-2 to round-4 probes give identical output on both commits.
- **New Major, F18: held comics are polled for as long as a fault lasts (probe-verified).**
  - **Trigger.** The shorter retry treats every ComicVine wait that has an end time as transient. That includes a revoked key (HTTP 401/403) and a machine that stays offline.
  - **Mechanism.** In each pass, one comic reaches ComicVine and then waits 1 hour. Every other held comic is turned away by the 5-minute pause, and is due again at the next 10-minute folder pass.
  - **Measured.** 40 held comics through a 6-hour outage: 1,315 comic passes instead of 40, and 76 ComicVine requests instead of 1.
  - **ComicVine is not hammered.** It gets about 6 requests an hour, inside the existing pause, pacing and budget. The cost is local work and uncached third-party cover downloads, repeated on every pass.
  - **No wrong write.** Nothing is written wrongly.
- **New Minor, F19: one "Object Not Found" answer is trusted for 7 days.**
  - If ComicVine ever sends one for a valid issue, the restored id stays hidden for up to 7 days.
  - During that time, a conflict that was never saved does not block.
- **New Minor, F20: the new `detail` text is not shown.** It is saved on the record, but nothing displays it.

## Focus-area answers

### Ender's claims

1. **"Status 101, or an HTTP 404 whose body is status 101, raises `ComicVineNotFound`: no global pause, a 7-day negative cache."** True, and narrowly. Probe `probe_r5_api.py` sends 18 answer shapes through the real `app.api`:

   | ComicVine answer | Result | Pause | Not-found cached |
   |---|---|---|---|
   | HTTP 200, status 101 (with or without error text) | not found | no | yes |
   | HTTP 404, JSON body with status 101 | not found | no | yes |
   | HTTP 404 with a gzip body, a body over 1 MiB, JSON status 1, a JSON list, HTML, an empty body, or no body | outage | yes | no |
   | HTTP 410 or 500 with a status-101 body; HTTP 502; HTTP 401 with status 100; HTTP 429; timeout | outage | yes | no |
   | HTTP 200 with status `"101"` as a string, or status 100 | outage | yes | no |

   - **Cache order.** A cached not-found still answers during an active pause and with no key, with 0 requests. A fresh positive cache row is read first, so a not-found row never hides a newer real answer.
   - **Dashboard.** It reads "available" after a not-found answer. On `6b5c876` it read "access rejected".
   - **Error body.** The error body is now closed.
2. **"A dead id with no saved conflict searches every source strictly and may write; reused evidence is not written."** True, with one wording caveat.
   - **Reused evidence.** `automatic.py:220-223` drops it on every dead-id pass. Probe P2:
     - Day 1: evidence that was remembered without strict checks wrote nothing.
     - Day 2: a lead that passed strict checks wrote.
   - **"Every source strictly."** This is true for every source that has a strict mode: the publisher catalogs, GetComics, the publisher lookup, saved and Lens leads, and general web search.
     - Metron, GCD, Google Books and the Open Library index have no strict mode. They keep their own checks.
     - That is also how a comic with no Web id is treated, and it matches `SOURCE_CONNECTORS.md:71` for conflicts.
   - **Cost.** Evidence that passed strict checks on one dead-id pass is also dropped on the next one. Until the write lands, the comic re-checks its lead each day. This costs work, not safety.
3. **"A saved `conflict_issue` still blocks."** True.
   - **Evidence.** The new test covers it. So do the probe P1 conflict rows: no plan, whether or not the approved list has the cover.
   - **One gap.** A record last checked by v0.1.1 has no `conflict_issue`. See F19.
4. **"Genuine outages hold and are retried when the wait ends."** True. Probe `probe_r5_holdloop.py`:

   | Fault | `a73f43e`: held comics queued after the fault ends | `6b5c876` |
   |---|---|---|
   | 6-hour outage, 8 comics | all within 52 min | none in the 3 h after; next try about 15 h later |
   | 6-hour outage, 40 comics | all within 57 min | none in the 3 h after |
   | Hourly budget spent | all at 1.0 h | none; next try about 21 h later |
   | Missing key, set again after 24 h | daily retry, unchanged | same |

   The cost of this faster retry is F18.
5. **"A new per-comic `detail` field explains dead ids and holds."** True on the record (`automatic.py:428-434`). A normal pass clears it.
   - **Not shown.** No endpoint or page reads it. The dashboard reads discovery records only for outcome counts (`discovery_state.counts`). See F20.
6. **"The publisher-plan check changed to `not (conflict or hold)`."** Safe.
   - **No change for conflict or hold.** On `6b5c876`, `strict` was exactly `conflict or hold`. The only new case is a dead id.
   - **Strict answers.** `research.publisher_lookup` (`research.py:126-135`) then returns only a record from the approved exact-cover list (`verified-sources.json`), and only on an exact cover-hash match. It never reaches the Coffin shop.
   - **Probe P1.** It uses the real `publisher_lookup`, the real cover hash and a real approved file:

   | State | Approved list has this cover | Approved list absent | Coffin shop requests |
   |---|---|---|---|
   | Dead id | plan (Writer) | no plan | 0 |
   | Outage (hold) | no plan | no plan | 0 |
   | Conflict | no plan | no plan | 0 |
   | Control: no Web id, so not strict | — | no plan | 1 |

### Brief checks

1. **Can a dead-id comic be wrongly written?**
   - **Not from saved evidence or unchecked sources.**
     - Saved evidence is dropped.
     - Every source that has a strict mode runs strictly.
     - Plans fill empty fields only, so the dead `Web` link itself is never rewritten.
   - **What can write it.**
     - A fresh source that passes strict checks.
     - The catalog providers' own checks.
     - Sergei's approved exact-cover list.

     That is no looser than a comic with no Web id, which is searched with no strict checks at all.
   - **Residual (F19).** The check only knows conflicts that were saved.
     - **Probe P4.** A conflicting id answers "not found" on its first check, and a strict lead writes Publisher and Writer. When ComicVine answers the conflict 7 days later, the comic turns `identity_conflict`, but the write has already happened.
     - **Probe P4b.** A v0.1.1 record with `outcome: identity_conflict` and no `conflict_issue`, whose id has since died, ignores the old conflict. A strict lead writes.
2. **Could a transient 404 or 101 be mistaken for a dead id?**
   - **From transport or HTTP failures: no.** Every transient shape in the claim-1 table stays an outage. That covers 5xx, 410, timeout, 429, HTML, empty, gzip and oversized bodies.
   - **From ComicVine itself: yes, and it cannot be told apart.** If ComicVine ever answers 101 for a valid issue, during an incident or a merge, that one answer is trusted for 7 days. I could not check offline whether ComicVine does this.
3. **Can the negative cache mask a later-fixed id?**
   - **Fixed by Sergei (Web edited to a new id): no.** The new id has its own cache key, and the file change makes the comic due at once. Probe P3-B: one hour later, 1 request, queued.
   - **Fixed at ComicVine (the same id comes back): yes, for up to 7 days.** Probe P3:
     - Days 1-6: 0 requests; the comic stays `needs_identity_lookup`.
     - Day 7: it asks again and is queued.
   - **No early reset.** Nothing clears a not-found entry early. Maintenance pruning removes cache rows only after 30 days or when the cache is over its size limit.
4. **Can the shortened hold retry loop or hammer ComicVine?**
   - **Hammer ComicVine: no.**
     - Every request still passes the shared pause, the 20-second pacing and the 180-per-hour budget.
     - During a fault, that is about 6 requests an hour, with 8 or with 40 held comics.
     - A missing key keeps the daily retry and makes 0 requests.
   - **Loop: yes, for as long as the fault lasts (F18).** Probe `probe_r5_holdloop.py`:

     | Scenario | Comic passes | ComicVine requests | Lead re-checks and local-model cover reads (each) |
     |---|---|---|---|
     | 8 comics, 6-hour outage | 131 (`6b5c876`: 8) | 44 (1) | 123 (8) |
     | 40 comics, 6-hour outage | 1,315 (40) | 76 (1) | 1,275 (40) |
     | 8 comics, revoked key (HTTP 401) for 24 h | 455 (16) | 152 (9) | 447 (8) |
     | 8 comics, missing key for 24 h | 16 (16) | 8 (8) | 8 (8) |

     - **Steady.** With the revoked key, the rate stays at 18 comic passes an hour through hour 23.
     - **Not repeated.** Source lookups are not repeated; each source's own backoff holds.
     - **Repeated.** On every held pass, the work with no per-comic schedule runs again:
       - a cover read and hash for the approved list (`research.py:129-130`);
       - a local-model cover read, when no hint is saved (`automatic.py:298`);
       - saved-lead re-verification (`automatic.py:303`), which downloads each qualifying lead's cover image with no cache (`research.py:460`);
       - evidence-file and record writes.
5. **Is the publisher-plan change safe?** Yes. See claim 6.

## Earlier findings at a73f43e

| # | Round 4 | Now | Evidence |
|---|---------|-----|----------|
| F17 | Major | Closed | Round-4 probe rerun: B is queued on day 1, and the dead id makes 0 requests on days 2-3 and starts no pause. 10 of 12 new tests fail on `6b5c876`. The visibility part continues as F20 |
| F11 | Minor | Unchanged; open | `probe_identity`, `probe_verify_e2e` and `probe_r3_creators` give identical output on both commits |
| F12 | Minor | Unchanged; open | (b) is now also reachable through F19 |
| F13 | Minor | Unchanged (outside this range) | — |
| F14 | Minor | Unchanged (outside this range) | — |
| F15 | Minor | Grown; open | See dimension 8 |

## Rubric (fix round)

Severity tags and the always-blocking safety floor: `Team/Docs/ProcessRules.md` § Severity definitions.

### 1. Security

- Status: Pass. There is no shell-out, path, delete or secret change. The not-found cache key reuses the existing resource key under a prefix. The keys in the tests are fake.

### 2. Correctness & Logic

- Status: Concerns. F19, plus the F11 and F12 residuals.

### 3. Crash / Stability Safety

- Status: Pass.
  - **404 body.** It is read inside `try`, capped at 1 MiB, and closed in `finally`. An `HTTPError` with no body reads as empty and stays an outage (probe).
  - **Handler order.** Both `ComicVineNotFound` handlers sit before the generic `except Exception`.
  - **Retry time.** The hold retry reads `retry_at` only when it is above 0. Every ComicVine wait sets a number (grep).
  - **Manual routes.** A dead id now returns HTTP 400 with "does not exist", and nothing is written.

### 4. Performance

- Status: Concerns. F18.

### 5. State & Data Safety

- Status: Concerns
- Findings:
  - F18 [Major] `automatic.py:420-425`, `app.py:264-266`. The hold retry polls held comics for as long as a ComicVine fault lasts.
    - **Mechanism.**
      - A held comic is retried when its ComicVine wait ends, but never sooner than 5 minutes.
      - In each pass, only one comic reaches ComicVine. Its wait is usually 1 hour.
      - Every other held comic in that pass is turned away by the pause, so its wait is the pause end, about 5 minutes away.
      - Each of those comics is due again at the next 10-minute folder pass (`scheduler.finish`).
    - **Cost.**
      - Each held comic runs up to about 6 times an hour (5.25 with 40 comics), for as long as the fault lasts. That covers a revoked key (HTTP 401/403) or a machine offline for days.
      - The number of held comics grows as Web-id comics' 30-day cache entries expire during the fault. This is reasoned, not measured live.
      - Each pass repeats the work that has no per-comic schedule (brief check 4).
    - **What it does not do.** It writes nothing, and it stays inside ComicVine's pause, pacing and budget. A missing key is excluded.
    - **Why Major, not Critical.** It is a performance bottleneck, not a wrong write, data loss or crash.
    - **Probe:** brief check 4.
    - **Ender's starting points:**
      - **Back off.** Either back off per comic (5 min, then doubling up to 24 h), or shorten the retry only for a pause, budget or rate-limit wait, not for HTTP 401/403 or a connection failure.
      - **Skip.** On a pass that is only waiting for ComicVine, skip lead re-verification and the local-model cover read.
      - **Test.** Add a test with many held comics, a persistent fault and a virtual clock.
  - F19 [Minor] `app.py:366-373`, `automatic.py:210-244`. One "Object Not Found" answer is trusted for 7 days, and only a saved conflict blocks.
    - **Mechanism and probes:** brief checks 1-3 (P3, P4, P4b).
    - **Why Minor.** It needs either ComicVine itself to send a wrong 101, or an old record whose id has since died. Every write is still strict, and no looser than for a comic with no Web id.
    - **Starting points:**
      - Treat a previous `identity_conflict` outcome without `conflict_issue` as a saved conflict while the id answers "not found".
      - Consider holding on a first not-found answer, and allowing writes only once a second answer on a later day agrees.
  - F20 [Minor] `automatic.py:428-434`. `detail` is saved, but no endpoint or page reads it.
    - **Effect.** "Check the Web link" and the hold reason exist only in SQLite. This is the visibility half of round-4 F17.
    - **Also cosmetic.** `research_runtime.stage` counts every not-found answer as a "ComicVine" stage error in the timing metrics.
  - F13 and F14: unchanged.

### 6. Input Handling

- Status: Pass for this range.
  - The 404 body is parsed only as JSON, capped at 1 MiB, and accepted only as a dict whose integer status is 101.
  - The Web id stays digits only, enforced by the regex.
  - F11 is unchanged.

### 7. Maintainability

- Status: Pass.
  - `dead_web`, `conflict`, `hold` and `strict` are each computed once and commented.
  - The not-found cache shares the API cache table under a prefix, so the existing maintenance pruning covers it.

### 8. Doc/Code Drift

- Status: Concerns. F15 has grown, and this commit changes no docs.
  - **Now wrong.** `SOURCE_CONNECTORS.md:87` says provider-wide outages "retain the normal research retry (one day for unresolved identity ...), rather than shortening it". Held comics now retry when the wait ends.
  - **Undocumented:**
    - the dead-id behavior: strict search, writes allowed;
    - the 7-day not-found cache;
    - the hold itself (carried from round 4).
  - **Unchanged.** The round-4 caveat on `:71` ("An empty Summary can still be filled") still applies.

### 9. Build & Release Hygiene

- Status: Pass.
- Suite on an isolated export of `a73f43e`: 475 tests, OK, 33 skipped.
- No secrets or generated files are committed, and the commit has no attribution trailer.
- `VERSION` and `CHANGELOG` move in Sully's bump commit.

---

## Verdict (Round 5, a73f43e)

- Total Critical: 0
- Major open: 1 (F18)
- Minor open: 7 (F11, F12, F13, F14, F15, F19, F20)
- Closed this round: F17
- Safety-floor violations in the range: 0

**Verdict:** RELEASE CLEAR

No Critical finding blocks. F17's starvation is gone. F18 is the cost of the faster retry; it never writes wrongly.

**Fix F18 before deploy?** I recommend it; the change is small. It matters most if Sergei's machine is often offline for long stretches, or if the ComicVine key could be revoked. A short outage costs little.

**Open product questions for Sergei:**
- **Dead ids.** Ender's design answers round 4's dead-id question: a dead Web id is searched strictly and may be written, without waiting for Sergei to fix the link. Does Sergei agree?
- **Missing key.** Carried from round 4: should a missing key hold Web-id comics for good? It still does. The record now says why, but nothing shows it (F20).
- **Lens leads.** Carried from rounds 1-4: should Lens leads need one signal that does not come from the cover?

Futaba's behavior verdict is separate.

| # | Sev | Dim | file:line | Finding | Next-cycle action |
|---|-----|-----|-----------|---------|-------------------|
| F18 | Major | 5 State & Data, 4 Performance | `automatic.py:420-425`, `app.py:264-266` | Held comics re-run up to about 6 times an hour for as long as a ComicVine fault lasts (revoked key, offline); 33x the passes over a 6-hour outage | Back off per comic, or shorten only for pause, budget and rate-limit waits; skip lead re-checks and the local model on wait-only passes; add a many-comic test |
| F19 | Minor | 2 Correctness | `app.py:366-373`, `automatic.py:210-244` | One not-found answer is trusted for 7 days. A conflict that was never saved, or exists only in a v0.1.1 record, does not block a dead id. A restored id stays hidden for up to 7 days | Treat a legacy `identity_conflict` outcome as saved; consider confirming not-found on a later day before writes |
| F20 | Minor | 8 Doc drift, 5 State | `automatic.py:428-434` | `detail` is saved but shown nowhere; not-found is counted as a stage error | Show `detail` in the comic's details or status view |
| F11 | Minor | 2 Correctness | `research.py:255-261`, `:298-303` | Unchanged | As round 3 |
| F12 | Minor | 2 Correctness | `automatic.py` evidence reuse and Notes | Unchanged; (b) also reachable through F19 | As round 4 |
| F13 | Minor | 5 State | `cover_tasks.py:57-62`, `browser_worker.py:140-143` | Unchanged | As round 2 |
| F14 | Minor | 5 State | `relabel_cover_tasks.py:82-117` | Unchanged | As round 2 |
| F15 | Minor | 8 Doc drift | `SOURCE_CONNECTORS.md:71,87`, `SYNOPSIS_POLICY.md:8` | Hold, dead-id behavior and the not-found cache are undocumented; the `:87` retry text is now wrong | Align with the code |

## Method and limits (Round 5)

- **Read:**
  - the whole fix-round diff, and `automatic.discover` at `a73f43e`
  - `app.api`, `reserve_request`, and the manual ComicVine routes
  - `research.publisher_lookup`, `resolve_leads` and `cover_agrees`, plus `web_search.read` and `web_search.source`
  - `source_scheduling.due`, `ready` and `record`
  - `scheduler.finish`, the maintenance cache pruning, and `research_runtime.stage`
  - the new test module
- **Exports:** `git archive` of `a73f43e` into `senua_r2/r5_a73f43e`. The negative control `r5_neg6b5` is `6b5c876` code with the new test module. Everything ran with `-B` and `PYTHONDONTWRITEBYTECODE`; nothing ran inside the worktree.
- **Suite:** 475 tests, OK, 33 skipped.
- **Negative control:** 10 of the 12 new tests fail or error on `6b5c876` code. The 2 that pass are the positive controls.
- **Probes** (`senua_r2/probes/`):
  - `probe_r4_hold.py`: rerun on `a73f43e`.
  - `probe_r5_api.py` (new): 18 ComicVine answer shapes against the real `app.api`.
  - `probe_r5_deadid.py` (new): P1-P5, on both commits.
    - **Real parts.** It uses the real `app.api`, `discover`, `discovery_state`, ordering, due logic, reuse and remember.
    - **P1.** It also uses the real `publisher_lookup`, the real cover hash and a real approved file. `research.fetch` is replaced and counted.
    - **P5.** A not-found inside `lookup_unidentified` leaves no error, no wait and no hold.
  - `probe_r5_holdloop.py` (new): virtual clock, on both commits.
    - **Folder passes.** They are emulated as `scheduler.finish` does: 5 s after a pass that returns True, 600 s otherwise.
    - **Sources.** Source fakes report through the real `completed`, so the real per-source backoff applies.
  - **Earlier probes.** The round-2 to round-4 probes (`probe_conflict_pass2`, `_provider`, `_summary`, `probe_identity`, `probe_verify_e2e`, `probe_r3_creators`, `probe_r3_outage`) give identical output on `6b5c876` and `a73f43e`.
- **Probe limits:**
  - **Queue.** `worker.enqueue` is replaced, so a queued plan is never applied. A pending set stands in for the queue ticket.
  - **Local model.** In `probe_r5_holdloop`, the local model is available and never returns a hint. This is the worst case for local-model cover reads.
- **Not run:** the service, any browser, any public request, live data.
- **Not verified:**
  - **Spurious not-found.** Whether ComicVine ever answers 101 for a valid issue.
  - **Held-comic count.** How many comics a real offline day or revoked key would hold.
  - **Pass cost.** How long one held-comic pass takes in real time.
- **Kept:** the probes, the `a73f43e` and `6b5c876` exports and the probe outputs, for the F18 and F19 follow-up.
