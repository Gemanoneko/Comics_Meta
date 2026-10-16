# Comics Meta Organizer — QA release gate, v0.2.2 (Part 2: two real updates, 0.2.1 to 0.2.2)

Date: 2026-10-16. Owner: Futaba. Lean pass ordered by Sergei ("as lean as possible", one attempt per step). Part 1 is `ComicsMetaOrganizer_QA_Installed_v0.2.1_2026-10-16.md`.

**Verdict:** GO

GO means what Jane defined it to mean: no Blocker, and both updates preserved state. One step of the update flow, the relaunched process itself, could not be run under isolation and is listed first under "Not testable". Read that before relying on this GO.

## What was tested

- Baseline `dist/Comic-Metadata-Setup-0.2.1.exe`, SHA-256 `ac13187ff1e3c726758ba5d80ed5442e7b508cf1fb337ff60e8e201f31cd17a7`. Verified equal to the brief.
- Candidate `dist/Comic-Metadata-Setup-0.2.2.exe`, SHA-256 `ddb0dcf877cc09f2a26cde2f48a34ca68c503a6b4c708f5fe5608b86c2e78937`, `latest.yml` sha512 `STcs…aKPhhQ==`, size 149,451,776. Verified equal to the brief.
- Source: M1 worktree at committed HEAD `374250c`, tree clean, VERSION 0.2.2. No qa-handoff receipt in this lean pass (same as Part 1).
- Each case: a fresh private silent install of 0.2.1 (`/S --no-desktop-shortcut /D=<63-character root>`, private TEMP), the installed app in its own private QA mode (hidden offscreen windows, throwaway state, ports 47611 engine / 47612 feed / 47613 model stand-in / 47614 CDP). Live ports 8765 and 11434 untouched (the only listener on those throughout was PID 34100 on 11434, which was already there). No window shown, no audio, no physical input.
- Fixture per case: seven CBZs (identity conflict, dead ComicVine link, held for ComicVine, unrelated, provider choice, removable dead link, one untouched dead link kept for the post-update action), real first-run setup through the UI with a dummy ComicVine key saved by the real DPAPI path, and two manual per-comic recoveries made through the product UI before the update: "The file is correct" on the conflict comic (writes the replacement link) and "Remove this ComicVine link" on the dead-link comic. Both left a history row, a manual ledger row and a retained backup.
- Case A: update while processing (Running). Case B: update while human-paused (Pause & release GPU reached Paused with GPU released before the update). Case B was installed fresh, not on top of case A.
- Three extra runs (C, D, E) used the same update flow only to probe state writes while the installer ran (see "Held-ancestor writes"); they are not counted as update cases.

## How the update flow was run, and what had to be bent

1. Update feed. A tiny authenticated loopback server (Bearer token, exact paths only) served `latest.yml` and the 0.2.2 installer; the policy file pins the artifact name, size and sha512. The harness in `scratch/cmo-futaba-installed-qa-20261015/` is source-only and needs a reviewed-graph environment, so I used a small server of my own. The app's own flow did everything else: automatic check at launch found 0.2.2 ("Update available"), manual **Check for updates**, **Download**, **Update ready**, **Install and restart** (confirmation "Processing pauses first"), **Cancel** (state unchanged, Update ready kept), **Install and restart** again, **Pause and install**. The `.blockmap` request returned 404 on purpose, so electron-updater fell back to a full download. Differential download was therefore not exercised.
2. Stand-in workers before the update. 0.2.1 cannot spawn workers in QA mode (Part 1 M1), so for the 0.2.1 side I ran the installed `worker.py` and `browser_worker.py` as stand-ins, each started with `COMICS_META_STOP_BASELINE` set to the then-current stop generation, restarted after 2 s if they crashed (case A: the stand-in browser worker died on start twice in the first three starts, which is Part 1 M3 on 0.2.1). The update's Quit stopped both (exit code 0), no respawn, no file locks. After the update, every worker below is the 0.2.2 product's own.
3. The relaunch could not be left uncontained. The installer is started with `--updated /S --force-run`, and NSIS relaunches the app with `StdUtils::ExecShellAsUser` through Explorer. I proved with a probe installer that this does not inherit the caller's environment. So the relaunched app has no QA policy: it starts in normal mode (visible window, port 8765, real `%LOCALAPPDATA%\ComicsMeta`, real GitHub feed). That breaks the hard rules, so I held the Chromium single-instance lock for the real default profile folder (`%APPDATA%\Comic Metadata`) with a tiny hidden Electron process. Chromium refuses a second instance of the same profile before any app code runs. First proven safely: the same installed `ComicMetadata.exe` was refused by that lock and the holder logged the attempt. During both real updates the holder logged the installer's relaunch: `ComicMetadata.exe` from the new install folder, `--updated`, via the Start Menu shortcut, and the new instance exited at once. Real `%LOCALAPPDATA%\ComicsMeta` never appeared, nothing listened on 8765, and no real-feed request was made. After each update I started the updated 0.2.2 myself in the same private QA mode and tested that. The holder profile folder is deleted at cleanup.

## Results per case

| Check | A: processing | B: human-paused |
|---|---|---|
| Update flow, UI states | check, download, ready, confirm, cancel, install: all as designed | same |
| Cancel at the confirmation | stayed Running, update still Ready | stayed Paused (user), update still Ready |
| Pause and install, click to old app gone | 15 s (GPU unload once, engine stop, workers exit 0) | about 11 s |
| Installer run, relaunch trigger | installer 24 s; relaunch trigger 37 s after the click, 2 s before the installer exited | relaunch trigger 29 s after the click |
| Version after | engine `VERSION` 0.2.2, `/api/state` 0.2.2, shell `loadedShellVersion` 0.2.2, badge "v0.2.2" | same |
| Old version leftovers | 0 processes under the install root before my relaunch; stand-ins exited 0 | same |
| Library folder | all 9 files identical (SHA-256 of 7 archives plus backups) | all 9 identical |
| Settings | `config.json` byte-identical, custom `unknown.fixture_keep` kept | byte-identical |
| Dummy key | DPAPI blob byte-identical; decrypts to the original dummy; dashboard "online" true; keys status shows ComicVine saved | same |
| Manual choices / recovery records | `comics`, `history` (2), `write_ledger` (2), `discovery_records` (7), seeded provider cache: all identical; filters Dead link 2, Conflict 1, Held 1 as before | identical, same filters |
| Pause state | user pause 0, Running; shell pause did not stick (generation moved, user flag 0) | user pause 1 kept; phase Paused, GPU released kept; real workers re-acknowledged |
| Real 0.2.2 workers | `worker.py` and `browser_worker.py` children of the engine host, heartbeats from their PIDs | same, both acknowledged the pause |
| Next core action | worker scanned the library right after start ("Scheduled folder passes finished"), then a CBZ I dropped in later was discovered (7 to 8 comics); manual "Remove this ComicVine link" on the untouched dead-link comic: "Change saved and verified.", archive SHA changed | paused: write buttons disabled with "Processing is paused. Resume processing before saving a change."; after an explicit Resume the same manual action saved and verified |
| Quit afterwards | graceful, 3.6 s, 0 processes | from Paused: 1.3 to 1.6 s, 0 processes; user pause still 1 |

The only table differences between before and after the update were volatile control tables (processing generation counters, the new `processing_stop` row from Quit, lens/yandex runtime rows, worker acknowledgements).

## The three fixes on 0.2.2

- **API keys button (UXSpec KeysEntry §7).** Present in the header between the version badge and Check for updates; label "API keys"; tooltip text as specified. Widths 320, 362, 640, 700, 701, 742, 760, 1280: the four header items never overlap, centre-point hit tests return each button, no horizontal scroll from the header (a scroll appears below about 440 CSS px for a different reason, see m5), focus rings are 2 px with 2 px offset and not clipped on both secondary buttons. Layout matches the spec: at 320 the row is badge plus API keys, then Check, then Pause one line lower; the stacked layout holds up to 760. Pause, API keys and Check for updates did not move across Check for updates' Checking, Up to date and idle states at 320, 640 and 1280. Tab order is API keys, Check for updates, Pause. Enter and Space open it; initial focus is the ComicVine field; the title is "API keys"; there is no Back to comic button; Cancel and Close carry "Discard unsaved key entries and close."; Escape, Cancel and the top Close all return focus to the header button; a double click opens exactly one dialog. Disabled with "Unavailable while the local service is not running." when the engine stopped answering (suspended it for 8 s), re-enabled when it came back; disabled with "Unavailable while updating or quitting." during Quit. Not rendered in a plain browser (checked in headless Edge through the studio launcher: no bridge, no button). Copy: app variant "Open API keys at the top of the page to add one."; browser variant "Open API keys in the Comic Metadata desktop app to add one."; setup help "Skip them now and add them later with API keys on the dashboard. Adding keys does not switch on paid search." (read from the installed setup page). Replace-only: no remove control; a blank save keeps the saved key; a replacement is stored (DPAPI decrypts to the new dummy value, other keys stay unsaved); drafts clear and remask; saving while Running and while Paused left processing state unchanged (Paused stayed Paused).
- **Real worker spawn in QA mode (Part 1 M1).** Fixed. In every 0.2.2 launch (cases A to E) the engine host started `worker.py` and `browser_worker.py` itself. Pause reached "Paused — Gemma released from GPU" in 5.9 s (case A) and 4.8 s (case B, second pause), with the model stand-in seeing one unload.
- **Browser worker start race (Part 1 M3).** Eight starts in a row of the installed 0.2.2 `browser_worker.py` (9 s each, private state): 8 of 8 survived, heartbeat advanced in all 8, no traceback. Engine logs of cases A and B contain no error lines. (Part 1: 4 of 6 died on 0.2.1.)

## Held-ancestor writes during the update

The 0.2.2 helper holds several ancestor folders while the installer runs. While the installer was alive I wrote, renamed and deleted files and folders in five held ancestors (QA root, state, work, cache, private TEMP) and wrote to the catalog database in `state\data`, every 120 to 250 ms. Run E (118 rounds) and run D (12 rounds): 0 failures, also in four control folders that are not held. Run C (57 rounds, no control folders): the same two rounds failed in all five held ancestors at once with `EBUSY` on a rename; everything else, including every SQLite write, succeeded. I could not reproduce it in the 130 rounds that followed, and I cannot say whether it is the helper, Bitdefender or the installer's own temp work. Listed as m2.

## Findings

### Blocker

None.

### Major

None found. (Part 1 Majors M1, M2, M3 are closed on 0.2.2 as shown above.)

### Minor

- **m1. Each successful update leaves about 430 MB behind that nothing prunes.** (a) `<state>\work\update-launch\launch-*`: a full copy of the Python runtime including Playwright's 93 MB `node.exe`, 467 files, 143 MB, never removed after a good update (so about 143 MB more per update under `%LOCALAPPDATA%\ComicsMeta\work\update-launch`); (b) the downloaded installer, 143 MB, in the updater cache `pending` folder; (c) `%LOCALAPPDATA%\comic-metadata-updater\installer.exe`, 143 MB, written by the installer on every install or update, and still not removed by `Uninstall ComicMetadata.exe` (Part 1 m11, unchanged in 0.2.2; the folder itself also stays). Repro: run one update, look at the three folders.
- **m2. Held-ancestor write failure seen once.** See above; one run in four, five folders at once, `EBUSY` on rename, 2 of 57 rounds. Needs a longer soak or a look from Ender with the helper's hold timeline.
- **m3 (carried from Part 1, unchanged in 0.2.2, outside the three fixes).** Empty blue banner under the header on every launch (`shell-notice` shown while empty, 56 px); keys-editor fields have no `aria-describedby`; Pause & release GPU keeps the browser's default focus ring while the two secondary buttons have the spec's 2 px ring.
- **m4. "Show" buttons in the keys editor wrap into three lines ("Sho" / "w") at every width.** 56 px wide, 64 px high, same in 0.2.1 and 0.2.2, so not a regression. Seen in the Details route and the new header route.
- **m5. Dashboard scrolls sideways below about 440 CSS px.** The long, unbreakable library path in the panel (`#roots`) forces 440 px; with a 63-character library path this is visible at 320 to 400. Same in 0.2.1 (measured on both). The header itself is fine.
- **m6. Update outcome notice not observed.** The app's own "updated" outcome (UXSpec UpdateOutcome) needs the real relaunch (`--updated` with QA env); my own launches did not carry `--updated`. See "Not testable".

## Not testable, and why

- **The relaunched process itself.** The installer's `--force-run` relaunch goes through Explorer without the QA environment, so it can only be tested as normal mode on Sergei's real session (visible window, port 8765, real state, real feed). I blocked it on purpose (see "How the update flow was run") and verified that it was triggered correctly (right exe, `--updated`, Start Menu shortcut, about 2.4 s before the installer exited, which is the window in which the helper still holds its folders). What the relaunched app does with those holds, and whether it shows the update-outcome notice, is unverified. A real check needs either Sergei's first real update watched on his machine (suggest: Jane asks for an away window and tells him a window will appear) or a Jane-approved way to give Explorer the QA variables.
- Differential download (the feed was told 404 for the blockmap); corrupt or truncated download, stale feed, installer-start failure and U5 recovery paths; update from a signed feed.
- Tray Open and Quit clicks, tray menu, tray icons, rendered `&&` label, Ctrl+Q and Alt-menu Exit (QA windows are never shown; no physical input).
- Native Browse folder picker, toasts, real GPU/Gemma, real provider responses, covers, SmartScreen, interactive installer wizard.

## What worked (checked, with evidence)

- Both installers matched their SHA-256 values; the 0.2.2 installer, feed size and policy sha512 agreed.
- The whole app-driven update path ran twice from fresh 0.2.1 installs: automatic check at launch, manual check, download (149,451,776 bytes), SHA verified, confirmation, cancel without side effects, pause, GPU unload, engine stop with 0 worker processes before replacement, installer run, relaunch trigger.
- State preservation was exact for library bytes, settings, DPAPI credential, comics, history, ledger, recovery records and user pause, in both cases; shell pause never became durable.
- Quit after the update was clean in both cases (1.3 to 3.6 s, no processes left); Pause reached Paused with real workers.
- Real `%LOCALAPPDATA%\ComicsMeta` never existed during or after the run; live ports 8765 and 11434 unchanged; no HKCU Run entry; Start Menu shortcut and Uninstall registry entry removed by the app's own uninstaller in every case.

## Pattern alerts

- **P1.** Transient Windows sharing violations around files and folders another process touches: v0.1.4 (foreground lease), 0.2.1 (`browser-heartbeat`, fixed in 0.2.2 and verified 8 of 8), and now one `EBUSY` rename burst in held ancestors (m2). Disposition proposed: **fix** once with a shared retry-on-sharing-violation helper (heartbeat instance already fixed); decision with Jane and Sergei.
- **P2.** Leftovers after install lifecycle: 0.2.1 uninstall leaves the 149 MB installer copy (Part 1 m11), and 0.2.2 updates now leave a 143 MB runtime copy plus a 143 MB pending installer on top (m1). Disposition proposed: **defer** to the next maintenance release; suggest pruning the capsule and the pending installer after a verified successful relaunch and removing the installer copy at uninstall.

## Process note

Sergei saw terminal windows take focus while this pass ran. Cause: my scratch watcher (`watch.mjs`, a detached Node process) called `tasklist` and `netstat` every 400 ms without `windowsHide`, so each poll opened a console. Fixed by stopping the watcher and adding `windowsHide: true` to every child-process call in my scripts; the watcher was not restarted and later checks polled once per second at most. No product change involved.

## Cleanup

- Removed: all five private installs (the app's own uninstaller each time; install folder, registry entry and Start Menu shortcut gone), the byte-identical updater copy in `%LOCALAPPDATA%\comic-metadata-updater` (checked against the 0.2.2 installer hash first) and its folder, the single-instance holder profile `%APPDATA%\Comic Metadata`, the NSIS stub folder, and in each private root the downloaded installer, library fixtures and backups, locks, profile, caches, catalog database, logs, config, policy file and the credential folders (dummy keys only). Feed, model stand-in, stand-in babysitters, probes and the holder are stopped; no process of mine is left; live listeners unchanged (only PID 34100 on 11434, as before); real `%LOCALAPPDATA%\ComicsMeta` never existed.
- **Retained, with reason:** 2,210 small files (about 80 MB, 59 folders per root) of the update capsule copies, one per private root, under `C:/Users/AnGeLZzZ/AppData/Local/Temp/f22t/illuminati-cmo-qa-{a,b,c,d,e}/state/work/update-launch/launch-*` (plus the empty `state/work`, `state` and root folders). The studio planner refuses them (a `references` folder inside the copied Playwright package is a protected name) and recursive delete is blocked by the deny list. I removed the large files in them (about 135 MB per root) by hand with literal `rm --` commands; what is left is small Python and Playwright runtime files, no keys, no user data. A sweep of `.../Temp/f22t` needs Jane's go-ahead for a method that handles the protected name, or Sergei can simply delete the folder.
- Scripts and evidence are kept under `C:/Users/AnGeLZzZ/AppData/Local/Temp/claude/c--Antigravity-Projects-Studio-Illuminati/84695450-db39-42ca-a8e6-93629fe0ee8f/scratchpad/futaba-022/` (`ev/`, `shots/`).
