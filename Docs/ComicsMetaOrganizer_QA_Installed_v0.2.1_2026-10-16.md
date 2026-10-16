# Comics Meta Organizer — installed-build QA, v0.2.1 (Part 1 of 2)

Date: 2026-10-16. Owner: Futaba. Lean pass ordered by Sergei: real use of the installed app, no evidence ceremony. Part 2 (0.2.1 to 0.2.2 update tests) and the GO/NO-GO come after this.

## What was tested

- Installer `Comic-Metadata-Setup-0.2.1.exe`, SHA-256 `ac13187ff1e3c726758ba5d80ed5442e7b508cf1fb337ff60e8e201f31cd17a7` (verified equal to the brief). App content M1 `47ba7ad` per the brief (not re-derived; no qa-handoff receipt in this lean pass).
- One private silent install (`/S --no-desktop-shortcut`), 68-character root under a private TEMP, launched in the product's own private QA mode: hidden/offscreen windows, throwaway state and profile, private ports 47611 (engine), 47612, 47613 (model stand-in), 47614 (CDP). Live app on 8765/11434 never touched (same listener PIDs before and after). No physical input, no window ever shown, no audio.
- Fixtures: a handful of scratch CBZs (plain, no-metadata, conflict, dead link, held), two with an apostrophe, `&`, `[ ]` and accented characters in the path. Dummy keys only. Provider answers were seeded into the private catalog cache; the app never reached a real provider.
- Screenshots (each looked at): `C:/Users/AnGeLZzZ/AppData/Local/Temp/claude/c--Antigravity-Projects-Studio-Illuminati/84695450-db39-42ca-a8e6-93629fe0ee8f/scratchpad/futaba-021/shots/`.

## How private QA mode had to be bent (read this first)

The product's QA mode never starts the processing worker, so a stand-in was needed (finding M1). I started the installed `worker.py` and `browser_worker.py` with the installed Python under a copy of the QA network guard that allows the worker spawn, and a tiny loopback stand-in for the model server on 47613. Anything below that depends on a running worker (Pause reaching Paused, graceful Quit) ran with these stand-ins and says so. The stand-ins ran outside the app's job object and were killed by me; they are not product behaviour.

## Findings

### Blocker

None found in what could be exercised. One core path could not be exercised at all (see "Not testable": the real worker spawn in normal mode). Do not read "no Blocker" as "core processing proven".

### Major

**M1. Private QA mode cannot run the worker, so processing, Pause and graceful Quit cannot be tested through it. Part 2 will hit the same wall.**
Repro: install, launch in QA mode, complete setup. Dashboard says "Stopped — automatic restart is being attempted" forever; no `python.exe` worker ever appears; nothing is scanned. Direct proof: installed Python, `import qa_runtime; qa_runtime.install(); subprocess.Popen([sys.executable, ...])` raises `PermissionError: Private QA native child refused`. Cause: the audit hook compares `args[0]` of the `subprocess.Popen` audit event to the allowed Python, but on Windows that value is `None` when the executable is passed inside the command line, so the allowed `sys.executable` is refused. The supervisor catches `OSError` and retries silently every 30 s, so nothing is logged.
Effect: the 0.2.2 acceptance row "observe a successful next core fixture action after restart" cannot pass in QA mode; with no worker acknowledging, Pause never reaches Paused and Quit waits for the 10-minute cap or Quit now. Owner: Ender (QA hook), before Part 2.

**M2. A user who skips or fumbles the ComicVine key at first run has no way to add one.**
The dashboard says "No ComicVine key is set, so comics with a ComicVine link wait. Open API keys in the desktop app to add a ComicVine key." There is no API keys control on the dashboard and none in the Alt menu (File/Edit/View). The only entry is the **API keys** button inside Details of a comic that is already "Held for ComicVine". With zero held comics the instruction points at nothing. (Screenshot `33-dashboard-no-key-notice`.) Removal of a saved key is not offered anywhere; that matches the spec but is worth Sergei knowing.

**M3. `browser_worker.py` intermittently crashes at start on a Windows file-sharing race.**
`PermissionError: [Errno 13] ... state\data\browser-heartbeat` raised from `browser_search.legacy_status` (reads the heartbeat file while its own heartbeat thread replaces it). 4 of 6 starts I made died this way; it also killed one worker that had been running for minutes. Under the real supervisor it restarts after the 30 s back-off, so it should heal, but until then Pause cannot reach Paused (needs the browser acknowledgement) and Quit waits: I saw a Quit sit in "Pausing" until I restarted the worker. I could not run the real supervisor (M1), so the real-world frequency is unverified; this machine runs Bitdefender, which may widen the window. Same family as the v0.1.4 "transient PermissionError reading the foreground lease" (see Pattern alerts).

### Minor

- **m1. Empty blue bar on every dashboard launch.** `<section class="shell-notice" hidden>` is injected with `display:flex` (static/shell-ui.js), which overrides `hidden`, so a 56 px empty banner shows under the header even when there is nothing to say. (`03`, `06`)
- **m2. Dead-link Details opens with an error nobody earned.** First line under the badge is "ComicVine could not find this issue. Check the link or search by series." before any check was run. The row's definitive "returned Not found for linked issue 999" sentence, the dead issue id as its own labelled value, and the observed check time are not shown in Details (id appears only inside the Web link). "Find a replacement link" tooltip reads "Search ComicVine and review another issue before changing this comic." instead of the spec text.
- **m3. Stale error survives success.** After a failed "Check link" ("ComicVine cannot check this issue now…"), a later successful check shows the new identity but the old error stays, and it is still there in the removal preview.
- **m4. Same-identity replacement asks a confusing question.** Dead link, pasted/searched issue whose Series/Issue/Year equal the file: instead of a Web-link-only preview, the dialog shows only Month/Day differences and asks "Keep the file identity / Use this ComicVine identity". "Use…" would also write Month/Day; "Keep…" is the one that replaces the link. Spec §3 expects the link-replacement preview directly.
- **m5. Link removal leaves a stray empty entry.** `https://example.test/keep; https://comicvine.gamespot.com/issue/4000-999/; https://other.test/keep` becomes `https://example.test/keep; ; https://other.test/keep`. Other URLs are preserved, but the dangling `; ;` stays in the file's Web field.
- **m6. Save-progress copy.** While writing, the confirm button keeps the label "Save and verify" (disabled) instead of "Saving…". Confirmation reads "Save these 1 changes". "Recovery backup retained." never says where; the backups sit in a hidden `.comic-metadata-backups` folder inside the library and accumulate (3 after 3 writes).
- **m7. After a stale-evidence message the dialog is stuck.** I edited the archive between preview and confirm: the write was correctly refused ("This comic or its evidence changed…", archive untouched). But re-clicking the action then does nothing visible, the "existing metadata" block under the path still shows the old Summary, and Refresh status removes the whole "Help with this comic" section with no explanation (the problem record is signature-bound, so the edit cleared it).
- **m8. Focus drops to the page body** after "List issues" and after "Review this issue" (the clicked button is replaced). Spec wants focus on the new subsection heading.
- **m9. Wording/structure drift from Judy's spec.** Conflict row reads "ComicVine issue 123 is Another Series #7; the file says Good #1." (spec: file first, then the ComicVine link). "Remove this ComicVine link" appears twice at once in a conflict dialog (top level and inside "The file is correct"). Details shows only the badge "ComicVine conflict" as the cause line; both identities are otherwise clearly shown.
- **m10. Missing `aria-describedby`** on the dead-link "ComicVine issue link" field (helper text not tied) and on the keys-editor fields and their help lines (first-run setup does have it).
- **m11. Uninstall leaves 149 MB behind.** `%LOCALAPPDATA%\comic-metadata-updater\installer.exe`, byte-identical to the installer, is created at install time and not removed by `Uninstall ComicMetadata.exe` (the app folder, registry entry and Start Menu shortcut are removed). I removed it by hand. The NSIS stub dir `~nsu.tmp\Un_A.exe` also stayed in the TEMP I had redirected.
- **m12. Engine log noise.** Each start writes the console banner "Keep this window open. Ctrl+C stops the app." into `engine.log`.
- **m13. Unsigned.** Installer and `ComicMetadata.exe` are `NotSigned` (expect a SmartScreen prompt on first run); install is 510 MB on disk, 665 files, longest path 210 characters at a 68-character root.

## What worked (checked, with evidence)

- **Install.** Silent install 23 s, exit 0, nothing started by the installer, no desktop shortcut, no autostart entry. Registry entry "Comic Metadata 0.2.1", Start Menu shortcut pointing at the installed exe, bundled Python 3.14 and 7-Zip present. Install folder stayed read-only in use (only a `__pycache__` file I caused myself).
- **First run.** Setup shows with focus in the library field, copy and labels match the spec, Tab order is exactly the specified one, nothing but a database file exists in state before Save (no worker, no scan, no provider). Validation messages match the spec table for: empty, whitespace, relative, drive-relative, missing folder, a file instead of a folder, and unreadable folder (deny ACL, restored). No typo folder was created. Error summary plus field error plus focus to the field. Layout clean at 320/400/640/1280 CSS px and 200% zoom: no sideways scroll, no overlaps, all targets at least 32 px (Show buttons 69x43). Window close during setup keeps the draft and the process; Quit from setup exits cleanly.
- **Save.** Blank keys: library saved, no credential file, dashboard opens. With a key: saved, DPAPI file written, no plaintext in state, profile, library or cache. Config written with `automatic.enabled=true` and the library path only.
- **Keys editor (Held comic Details).** Opens with ComicVine focused; "Key saved / Leave empty to keep the saved key" vs "No key saved"; blank preserves the saved key; whitespace trimmed (19 characters stored from a padded sentinel); replace works; unsaved keys add. Newline, CRLF, NUL, non-string and unknown-field payloads are all refused by the backend ("key_invalid"). Show/Hide toggles one field with `aria-pressed` and a provider-specific name, and re-masks when focus leaves the row. Cancel and Back to comic clear drafts and return focus to the trigger; Escape cancels the editor first. Persisted across restarts. Not testable: the DOM cannot carry a newline into a password input at all (the browser strips it), so the newline path was proven through the IPC.
- **Per-comic help (cached ComicVine evidence).** Row, "Review options", Details with "In this file" and "ComicVine link" cards side by side, filename identity labelled separately, Differences list, no preselected option. "ComicVine issue is correct": exact Field / In the file / After table. "The file is correct": prefilled search, results, "Review this issue", then a Web-entry-only preview. Cancel change writes nothing (hash unchanged). Save this change opens the final confirmation with focus on Go back; Save and verify writes once (double-click and a third click produced one backup and one write), controls disabled during the write, live status text "Saving this change and verifying the comic…". Archives re-read: only the listed fields changed, Publisher/Summary/other URLs preserved, extra members preserved, zip test clean, XML-special text (`<Summary> & more`) and accented text intact, apostrophe/`&`/bracket/accented paths all fine. Resolved rows leave the filter and focus returns to the count line. Paused: write buttons disabled with "Processing is paused. Resume processing before saving a change." Arbitrary and malformed links are refused locally with the spec copy; nothing is fetched.
- **Pause and release GPU** (stand-in workers and model stand-in): Pausing to "Paused — Gemma released from GPU" in about 5 s, exactly one unload request and one `/api/ps` check, Resume restores Processing, user pause survives a restart, and a Quit-time shell pause does not stick after a forced exit.
- **Window, tray, Quit.** The tray host window exists. A WM_CLOSE to the main window did not end the process (hides to tray; the QA window is never shown, so the hide itself is not visible). Second launch exits in about 1.5 s with code 0 and starts no second engine. Quit (the same function the tray item calls) from dashboard, open Details dialog, setup screen and the startup-failure page ends every process under the install root and frees the engine port; stopping dialog shows "Quitting Comic Metadata / Pausing — finishing the current operation. Progress is saved." with Cancel quit and Quit now; Quit now closes everything in about 5 to 7 s. Quit from a paused, GPU-released state takes about 2.5 s. Launch to ready: 1.7 s.
- **Startup failure.** Engine port occupied: failure page "Could not start the local service. Another app is using the local service port. Close the other copy, then try again." with Try again, Open log folder, Quit. Try again after freeing the port starts normally.
- **Uninstall.** The app's own uninstaller removed the app folder, registry entry and Start Menu shortcut in 8 s (leftover: m11).

## Not testable, and why

- Native **Browse…** folder picker (modal native dialog; focus and input) — only typed paths tested.
- **Tray Open, tray menu clicks, tray tooltips/badge icons, rendered `&&` label** — need a physical click or a visible shell. Only the tray's existence and the close-does-not-exit behaviour were observed.
- **Ctrl+Q and the Alt-menu Exit** — QA mode never shows windows and the Ctrl+Q handler requires a visible window.
- **Toasts** (first-close notice, tray-pause finished) — disabled in QA mode.
- **Normal-mode launch and the real worker spawn.** Starting the installed app outside QA mode would bind the live port 8765 and use the real `%LOCALAPPDATA%\ComicsMeta`. That is the path Sergei actually uses and it is unverified here (see M1).
- **Real ComicVine "Object Not Found" and real search results.** The network is blocked in QA mode. The identity cards, search results and dead-link state came from answers I seeded into the private cache, so the provider-parsing side is unexercised; an uncached issue correctly reports "cannot check now".
- **Covers.** Fixture pages are 1x1 images and the cached issues have no cover, so "Cover in this file" / "ComicVine cover" could not be judged visually.
- Overlapping-library refusal ("Another copy is processing this library") — would need a second engine owning the lock; single-instance blocks the setup.
- "Saving…" on the first-run Save button — the page navigates in about 100 ms; not captured.
- Interactive (non-silent) installer wizard, very long install path failure, SmartScreen behaviour.
- Real GPU/Gemma (only a loopback stand-in), real update flow (Part 2).

## Cleanup

Private install uninstalled with its own uninstaller; private state, profile, fixtures and caches removed (planner manifest `72f2f19e…`, 121 files, 56 directories, 3,461,935 logical bytes), plus the orphaned updater copy (149 MB). My stand-in workers, model stand-in and port blocker are stopped; no `ComicMetadata.exe` or install-root process remains; live ports 8765 and 11434 are unchanged. Kept: this report and the screenshots.

Pattern alerts: P1 — transient Windows `PermissionError` when one thread or process reads a status or lease file that another is replacing: v0.1.4 (foreground lease, QA 2026-10-13) and now 0.2.1 (`browser-heartbeat`, M3). Two builds, same shape, both handled case by case. Disposition proposed: **fix** once with a shared retry-on-sharing-violation read helper for status/lease/heartbeat files; decision with Jane and Sergei.

**Verdict:** PART 1 — ISSUES
