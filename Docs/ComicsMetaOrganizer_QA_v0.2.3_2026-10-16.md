# Comics Meta Organizer — QA release gate, v0.2.3

Date: 2026-10-16. Owner: Futaba. Lean pass ordered by Sergei (one attempt per step, failures recorded not looped). Previous gate: `ComicsMetaOrganizer_QA_v0.2.2_2026-10-16.md` (Part 2, GO).

**Verdict:** GO

GO means: no Blocker, no Major. The four changes in 0.2.3 (file cover on review screens, backup removal after a verified recovery save, SerpApi removal, case-insensitive key names) behave as specified in the unpacked build, and that build is byte-identical to the installer payload. The updater/installer flow was **not tested** this round (see "Not tested").

## Build under test

- Tool Comics Meta Organizer, version 0.2.3, committed HEAD `6f43d4d`, worktree `C:/Antigravity Projects/Worktrees/Comics Meta Organizer/installer`. Tree was clean when the pass began. During the pass an untracked `Docs/ComicsMetaOrganizer_CodeReview_v0.2.3_2026-10-16.md` appeared (Senua's, not mine). No qa-handoff receipt script run (lean, same as Parts 1 and 2).
- Installer `dist/Comic-Metadata-Setup-0.2.3.exe`, SHA-256 `0907c11210c6a16c37c91bc04c6a7b21b896cb9769e91beab64511a325d91d8e`. Verified equal to the brief. **Not executed.** `latest.yml` says size 149,453,847 and sha512 `+kXYefYP…aDLg==` (the policy file used these).
- Payload check: I extracted the installer's `app-64.7z` with the bundled 7-Zip (hidden, scratch) and compared every file with `dist/win-unpacked`: 605 of 605 identical (SHA-256). The 87 engine files that exist in the committed tree are equal to HEAD (56 identical, 0 differ, the rest are build-staged files: `installer_launch.py`, `update-runtime-manifest.json`). So tests on `win-unpacked` stand for the installer.

## How it was run (isolation)

- `dist/win-unpacked/ComicMetadata.exe` in private QA mode. **Separation confirmed from the code before launch:** `desktop/main.cjs` lines 9 to 11 load the QA policy, call `app.setPath('userData', <private profile>)`, `cache` and `sessionData`, and only then call `app.requestSingleInstanceLock()`. The lock is keyed by userData, so it cannot hand off to Sergei's app. State root, lock folder, engine port, feed and model ports all come from the policy; windows are `show:false`, `offscreen:true`; `show()` and `notify()` skip focus in QA mode.
- Private root `%TEMP%\f23t\illuminati-cmo-qa-x` (policy, state, library, locks, profile, cache), engine 47621, feed 47622 (also the model stand-in), model 47623, CDP 47624. `ELECTRON_RUN_AS_NODE` and `VSCODE_*` unset. HTTP(S)_PROXY pointed at a dead port with loopback excluded, as defence in depth for the Python engine. Every spawned child has `windowsHide:true`. No process polling loops: about a dozen one-off hidden process-table reads (baselines and "is anything left" checks), each a single call.
- Sergei's live app was never touched. Baseline before: his main process PID 11104 (`%LOCALAPPDATA%\Programs\comic-metadata`), listeners 8765 (PID 73392) and 11434 (PID 34100). After: same processes, same PIDs, same listeners. No installer or uninstaller was run. Nothing read or wrote `%LOCALAPPDATA%\ComicsMeta`, `Y:\Comix`, ports 8765 or 11434.
- Fixture library: 14 comics (seven valid CBZs with real pictures covering conflict, dead link, held, plain, landscape cover and two ordering cases; then zero-image, corrupt ZIP, RAR-signature stubs as .cbz and .cbr, oversized first image, 49-megapixel first image, garbage first image), provider answers seeded into the cache, dummy keys only. Network: the engine and renderer reach only loopback; the QA policy blocks every other URL in the renderer.
- **Took no focus:** every window was hidden and offscreen, every child process hidden, no polling loop spawned console programs, no physical input was used, and the QA process set was gone after each Quit.

## Results

### 1. Archive cover on review screens (FileCover spec §7)

| Check | Result |
|---|---|
| Review this issue shows the file cover beside the ComicVine cover | Pass, both routes. Search route (from the conflict comic) and pasted-link route (from the dead-link comic): strip with "Cover in this file" and "ComicVine cover", both 160 x 240. |
| Conflict and dead-link Details | Pass. Conflict: both figures. Dead link: file figure alone, left (single strip). |
| Not shown on Held, plain Details, Review this change | Pass. Held (id 3), plain Details (id 4) and the Review this change table: no strip. "Write stopped" and "write failed" screens were not reproduced (see Not tested). |
| No-cover state | Pass. Zero-image CBZ (conflict), valid ZIP with a garbage first image, first image over 20 MB, first image of 49 MP: the file slot reads "No cover could be read from this file." in the same 160 x 240 box; the ComicVine slot is unaffected. CBR and RAR-as-CBZ stubs: the product itself classes them "File is not a zip file" (problem screen, no strip); `/api/cover` answers 400 with the same sentence (see Not tested for the real-RAR limit). |
| ComicVine slot states | "Loading cover…" (observed in the DOM sequence), "The ComicVine cover could not be loaded." (https cover blocked by the QA policy) and "ComicVine has no cover for this issue." (issue with no image) all seen. A **loaded** ComicVine image could not be shown (see Not tested). |
| Loading state | Pass. With the cover request held: "Reading cover…", `aria-busy="true"`, box 160 x 240. After release: image shown, `aria-busy` gone, every box rect identical (x, y, w, h). |
| Geometry (320, 640, 641, 1280 CSS px; 640 and 320 stand for 200% of 1280 and 640) | Pass. Two boxes equal size (0 px difference), bottoms level (0 px), gap 12 px, no overlap with captions, cards or buttons, strip never causes sideways scroll. At 320 the boxes are 95 x 142.5 and "Cover in this file" wraps to two lines; still level and side by side. |
| Landscape first image | Pass. 900 x 600 image shown whole, letterboxed, not cropped (screenshot `shots/30-matrix-5.png`). |
| First image = first by file name | Pass. Archive with `010.png` and `002.png`: served JPEG equals the thumbnail of `002.png`. |
| "Archive image" picker changes only the lower preview | Pass. Strip image src, rect and request count unchanged; lower preview moved to `index=1`. |
| Focus and tab stops | Pass. Focus lands on the "Help with this comic" heading; 0 tab stops inside the strip. Accessibility tree: image named "Cover in this file", figcaption present. |
| File bytes and mtime unchanged after viewing | Pass. SHA-256, size and `mtime_ns` of all 14 fixtures identical before and after all cover viewing (0 differences). |
| Extra: image modes through the preview (scratch zips) | CMYK JPEG, 16-bit PNG, palette-with-transparency, fully transparent RGBA, WebP, EXIF-rotated JPEG, 1 x 1 and 6000 x 20 all produced a JPEG; truncated PNG and GIF-named-PNG gave the "no cover" answer. Files unchanged. Heaviest accepted image (39.7 MP) decodes in well under a second; 8 parallel previews finished in 0.3 s. |
| Extra: endpoint origin check | `Sec-Fetch-Site` absent, `same-origin`, `none`: 200. `same-site`, `cross-site`: 403 "Untrusted origin". `/api/cover?id=1&x=1`: 400 "Choose a comic." Old `?id=&index=` form still 200. |

### 2. Recovery save deletes its backup

| Check | Result |
|---|---|
| Save A (dead link, "Remove this ComicVine link") with two other backups already in `.comic-metadata-backups` (another comic's, and an older retained one for the same comic) | Pass. Message "Change saved and verified."; the new backup (recorded in the history row) no longer exists; the two other backups and the folder stay. |
| Save B (conflict, "The file is correct" then Keep the file identity) with the folder otherwise empty | Pass. "Change saved and verified."; backup gone; the `.comic-metadata-backups` folder is gone. |
| Archives after both saves | `testzip` clean, members intact (`001.png`, `unchanged.txt`, `ComicInfo.xml`), Web field as previewed; history and ledger rows present for both. |
| Red-team: save on a read-only archive | Archive byte-identical (SHA-256 and mtime), no history row, backup **kept** in the folder, UI alert "The change was not verified. Check the file and retained recovery backup before trying again." See m1. |

### 3. SerpApi gone

- Setup page (first run): fields are ComicVine, Metron, Google Books, Brave Search, nothing else; no "serp" anywhere in the page. Help line reads "Skip them now and add them later with API keys on the dashboard. Adding keys does not switch on paid search."
- Dashboard API keys editor (header button, keys mode): the same four fields. No "serp" in the dialog.
- "Identify by cover" panel: "Unresolved comic identities are researched automatically using Google Lens."
- Whole shipped payload searched (engine, `app.asar`, licences): the only hit is the retired-key constant and its comment in `credential_store.py`.
- Legacy state: config with `browser_search.serpapi_fallback: true` and `serpapi_monthly_limit`, a saved 0.2.2-style credential overlay containing a retired SerpApi value, a `SERPAPI_API_KEY` line in the state-root `.env`, and `SERPAPI_API_KEY` in the process environment. The app started, service "ready", no notice, no failure, no error in the engine log (two relaunches). A keys-only save from the editor kept the retired key exactly as saved (by name: `COMICVINE_API_KEY`, `METRON_API_TOKEN`, `SERPAPI_API_KEY`), and left the config's legacy keys alone; the editor never showed it.

### 4. Mixed-case key names in the state-root `.env`

By name only, dummy values. `.env` held `metron_api_token=…` and `Brave_Search_Api_Key = "…"` (spaces and quotes), none for Google Books. The app's own saved-key status (`window.comicDesktop.keys()`) and the editor showed Metron: saved, Brave: saved, Google Books: no key saved (absence control), ComicVine: saved (DPAPI). `unrelated_key` and the retired `SERPAPI_API_KEY` line produced nothing visible.

### 5. Quick regression

- First-run setup through the UI with a dummy ComicVine key: service ready, shell 0.2.3, processing Running.
- API keys button: present (tooltip as specified), opens "API keys", Save keys works ("Keys saved. Source settings and processing state are unchanged.").
- Pause & release GPU: Paused with GPU released in 2.6 s (stand-in saw the unload); button reads "Resume processing". The pause persisted across the next launch (by design).
- Quit: from Running 5.1 s, from Paused 1.5 s (twice); QA process count 0 afterwards each time; listeners back to Sergei's two only.

## Findings

### Blocker

None.

### Major

None.

### Minor

- **m1. A failed save on a read-only archive says "not verified" although nothing was written.** Repro: set the read-only attribute on a comic file, open its Details, "Remove this ComicVine link", Save and verify. Observed: file untouched (hash and mtime unchanged), no history row, one retained backup, alert "The change was not verified. Check the file and retained recovery backup before trying again." The wording suggests the file may have changed. By code reading (not run): every failed manual attempt keeps one more backup copy, so repeated retries on a locked comic could leave one full copy per attempt. Same code path as 0.2.2, not new in 0.2.3; README documents "failed manual writes retain recovery material".
- **m2. Removing a link between two others leaves an empty entry.** `https://example.test/keep; https://comicvine.gamespot.com/issue/4000-999/; https://other.test/keep` becomes `https://example.test/keep; ; https://other.test/keep` (the review table shows the same text before saving). Cosmetic, pre-existing.
- **m3. After "Review this issue" renders, keyboard focus is on the page body** (the heading that held it is replaced). Matches FileCover §7.7 ("where it did before"), so not a regression, but a keyboard or screen-reader user loses their place.
- **m4. The Details dialog scrolls sideways at 640 CSS px and below** (75 px at 640, 176 px at 320) when the file path is long and unbreakable (`p#localPath`). It also happens on a comic with no cover strip (Held), and the strip itself never overflows, so this is not caused by 0.2.3. Same cause as Part 2 m5 (dashboard).
- **m5. FileCover §6 arithmetic is off at 320 px.** Spec says 113 x 170 covers; measured 95 x 142.5 because the dialog is 267 px wide at a 320 px viewport, not about 304. The layout still holds (equal, level, 12 px gap, side by side). A correction for Judy's spec, not a defect.
- **m6. `/api/cover?id=abc` returns the raw Python text** `invalid literal for int() with base 10: 'abc'` (400). Loopback only, no UI path produces it, pre-existing.

## Not tested

- **The updater and installer flow**: unchanged since 0.2.2's GO, not re-run. The installer was only hash-verified and its payload compared by extraction; it was never executed. Installed-package behaviours for 0.2.3 (first launch from the installer, uninstall, leftovers) are untested.
- A **loaded ComicVine image** in the ComicVine slot. The cover URL must be https and the QA network policy blocks every non-loopback URL before devtools interception can answer it, so only the Loading, failed and no-cover states were seen. The loaded path shares its code with the file slot, which does show images.
- A **real RAR or `.cbr`**. No tool here builds one; the fixtures are stubs with a RAR signature. The product classes them as unreadable before any strip appears, so the "No cover could be read" sentence was reached through the UI only for valid ZIPs (no image, bad image, oversized, huge) and checked on the endpoint for the stubs.
- The **write stopped** and **write failed** problem screens (strip must be absent); only Held was checked.
- The backup-removal **refusal branches** (hash mismatch, symlinked backup folder): only the failed-write branch was exercised.
- Tray menu and Open/Quit clicks, the window Close button, Ctrl+Q, Alt-menu Exit (QA windows are never shown, no physical input); Quit ran through the product's own quit action.
- 200% as device pixel ratio: covered as CSS widths 320 and 640.
- Real screen reader (accessibility tree only), real GPU/Gemma (stand-in), real providers (seeded cache), unit tests (Ender's), repeated failed saves, `.env` files with duplicate key spellings.

## Pattern alerts

- **P3.** A long, unbreakable file path forces sideways scrolling: the dashboard (0.2.1 and 0.2.2, Part 2 m5) and now the Details dialog (m4). Real library paths on `Y:` are long. Disposition proposed: **defer** to the next maintenance release; one `overflow-wrap:anywhere` rule on path elements would likely close both.
- P1 and P2 from Part 2 (sharing violations, install-lifecycle leftovers) were not re-examined this round, their dispositions stand.

## Process notes

- Running the unpacked build writes `__pycache__` into the build folder (the workers start without `-B`): 29 files under `resources/engine` and 9 under `PIL`. Mine were removed afterwards; the build folder has no file newer than the installer.
- My first cover matrix hit a few "Reading this comic's current evidence…" hangs. Cause: my script closed the dialog and re-opened another comic within the same tick; the dialog's close event then bumped the open counter and the new open's reply was dropped as stale. With a 300 ms pause between close and open, 0 hangs in the later runs. It needs a programmatic close, so I treat it as a harness artifact, not a finding.
- Evidence and scripts: `C:/Users/AnGeLZzZ/AppData/Local/Temp/claude/C--Antigravity-Projects-Studio-Illuminati/84695450-db39-42ca-a8e6-93629fe0ee8f/scratchpad/futaba-023/` (`ev/`, `shots/`, scripts).

## Cleanup

- Stopped: the QA app (three launches, each quit through the product), the feed and model stand-in. No process of mine is left; live listeners are Sergei's two only; his app untouched.
- Removed (planner-checked literal `rm --` / `rmdir --`, manifests in `scratchpad/futaba-023-manifests/`): the whole private root `%TEMP%\f23t` (profile, cache, library fixtures and backups, locks, state data and logs) and my 38 `__pycache__` files in the build folder. The remaining dummy-key files in the private state (`.env`, `config.json`, `setup.lock`, two credential blobs, policy file) were removed by exact path, because the planner refuses protected names (`credentials`, `.env`).
- Retained: scratch `futaba-023/inst-extract` shrunk from 652 MB to about 149 MB (the five largest extracted files removed by exact path); the planner refuses the rest because the extracted Playwright package contains a folder named `references`. It holds only small runtime files from the public build, no keys, no user data. Sergei or Jane can delete the folder.
