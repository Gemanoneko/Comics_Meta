# Comic Metadata 0.6.5 tray QA · 2026-11-18

**Tray-smoke verdict: GO** for the private packaged launch and the 0.6.5 delta at source `1ba12722da19630fd03cdc7111b21a667a1369c9` (Senua RELEASE CLEAR is on 0b2c844, plus Sully's version-and-changelog bump).

The installer SHA-256 `7272187e04d0d74243d958d203b489c7349aaf7f3a5488a794bbe9343af3c1c5`, unpacked executable SHA-256 `850addfe5c621538c0023f90d1fcfd554c78ca2fb7ab9a8e9864e26bb9daa59b`, app.asar SHA-256 `39df362e7fbf242aad77b86ea78e9491e6e8caddb5beb9ac8c66523e4103e630` and feed SHA-256 `1b6b525c1de8cb5d34921d08ec11cd475a1d1a1bbe572513f68b6f19f2564703` matched the frozen package identity before the first launch and again at the start of both packaged runs. The read-back source candidate manifest SHA-256 was `73ff2e65624781447d5c9cb0caaba949fd796855b05393aee5ef19adc90a5c6c` (Sully's `source-manifest-1ba1272.json`, head 1ba1272). All 74 packaged engine files that exist in the source matched it byte for byte (`installer_launch.py` is copied from `desktop/`); the `win-unpacked` tree is 623 files, digest `a23ae3a309c10fd30c161096ddcfd3d1144b6beae3d9aaa5d4b341e05dcaf912`. Scoped QA verdict: no entry-check receipt, so this is not formal release clearance (same limit as 0.6.3 and 0.6.4).

## 6. Smoke and no regression (packaged app, private QA mode)

- The actual packaged app reported 0.6.5 and opened one invisible, unfocused, offscreen window. Private authenticated engine status was HTTP 200 and owned for broker PID 16868. All 17 visibility, focus, dialog, notification and spawn guards were installed and stayed clear (0 violations at start and at the end).
- Tray: the preview observer called through to the real `Tray.setImage` and compared SHA-256 of its decoded pixel buffers with the PNGs read from the app archive. The actual Processing, Pause and Resume tray menu callbacks selected the right bitmaps at scale factors 1 and 0.5. All 8 packaged PNG hashes equal the source manifest and the four icon states are distinct at both sizes (`asar-evidence-v0.6.5.txt`). The pause used a private model stub, as before.
- The enabled native tray Quit callback exited normally with code 0 (the whole run took 6.2 s); the private engine port then refused connections and no claims remained. The bounded Windows Job returned complete zero active processes and zero unsignaled handles, with 18 retained handles, after 6.176 s. Two private model requests, no feed request, no provider call.
- Installer to tested runtime: the pinned 7za (SHA-256 `b0cfdeaf429f5cc53f85123dd8f5a5feb92c19d31aa34df257edf9a26be05f95`), under its own private Job, extracted `ComicMetadata.exe` and `resources\app.asar` from the installer; both hashes equal the files the smoke ran (`package-binding-v0.6.5.json`, owner record `extraction-owned-v0.6.5.json`).
- Switches 2, 3 and 4 (`metron_spellings`, `collection_label`, `yearless`) read off with no `"matching"` key and Metron's rules stamp is still `3:cover_rule_v2,filename_year_formats,folder_year,unnumbered_as_one`; option 5's defaults are unchanged.
- One Fix B check in the running packaged app: progress.json overwritten with 263 zero bytes while the engine ran; the dashboard went from the newer phase to the saved one ("Folder complete", no "Status unavailable"), `progress.json.unreadable` holds the zero bytes, the file equals its `.bak`, and `logs/engine.log` has exactly one restore line. Quit exited 0 again (second packaged run, same checks, zero leftovers).
- Raw packaged observations are in `tray-evidence-v0.6.5.json`. Native Job close proof is in `tray-owned-v0.6.5.json`.

## 1 and 2. The two new sources, off by default and switched on: pass

102 checks against the packaged engine modules, in a private QA policy (the packaged QA audit hook refusing every non-private socket, plus a counter on `urllib`; the counter read 0 in every scenario) with answers placed in the private cache.
- **Off by default.** With no `sources.enabled`, with a `disabled` list that does not name them, and with `"disabled": []`, ComicVine search and VerseDB are both off; Metron and GCD offline stay on. With the answers sitting in the cache and Metron and GCD offline missing, a real discovery pass planned nothing, recorded neither source, made no request and the record carries no ComicVine or VerseDB mention. Neither status file is created.
- **Switch on.** `["ComicVine search"]` turns on only that source, `["VerseDB"]` only VerseDB, both together both; the marker fingerprint is unchanged by switching the name search with Metron on (nothing wakes).
- **QA mode answers from the cache only.** With nothing cached the name search records `unavailable` with cause `no_key`; with the search and issues answers cached but the detail missing it still stops at `no_key`. No request in any case.
- **VerseDB without a token** is `unavailable` (cause `no_key`, not an error) even with all its answers cached.
- **Order.** The name search waits while GCD offline has not answered and runs once Metron and GCD offline both missed. VerseDB waits for the name search (also while it is `unavailable`), and runs only after Metron, GCD offline and the name search all missed. If Metron or GCD offline found the comic, neither fallback is asked; if the name search found it, VerseDB is not asked. In a full discovery pass a Metron hit leaves both fallbacks unrecorded.
- **Cites.** Comics already citing Metron, GCD or ComicVine (`metron.cloud`, `comics.org`, ComicVine URL, `cvdb`) are skipped by both sources with nothing asked; VerseDB also skips a comic that cites VerseDB (finding 1).
- **One full match from recorded answers each.** ComicVine search: search, issues and issue answers in the cache, a real cbz and the real cover comparison (identical image bytes, no download), planned with `match_rule year`, cover `today` page 1, the name-search evidence block with issue id and rules stamp, Publisher and Series trimmed, Notes "Automatic verified lookup: ComicVine." with the issue page. VerseDB (placeholder token, cache only): planned, Notes carry the VerseDB credit and the issue page, Publisher kept outside `!BD`; under `!BD` a number with no year is accepted as an identity and outside it is not. The token appears in no record or plan entry.

## 3. S1, saved results behind a switch: pass

`reusable()` over 13 saved-result cases: VerseDB and Image Comics results are dropped while their source is off and kept when on; Metron results by `collection_label`, `yearless`, `unnumbered` (with `unnumbered_as_one` off), a spelling and an aligned cover (with `cover_rule_v2` off) are dropped; a plain `year` result and a `today`-cover result are kept. In a discovery pass a saved VerseDB result while VerseDB is off was not planned (no entry), and with VerseDB switched back on the same result was planned again. Saved evidence was fed through a patched `research_runtime.reuse`, as Senua's and Ender's tests do.

## 4. Metron rule C: pass

"(part 2 of 2)", "(2 of 3)", "(Book 14)", "[02 of 04]" and "(Volume 2)" are no longer an unnumbered book and are not asked as issue 1; each also fails the control (the 0.6.4 `metron.py`, loaded side by side, accepts every one). Plain one-shots with a year or a scan tag (`Saga Special (2019)`, `The One Shot (2020) (Digital)`, `Some Tale [2004]`, `Old Tale (2010) (GroupName)`) still qualify. `RULES_VERSION` is still 3, so nothing is woken.

## 5. ComicVine trim: pass

The field builder shared by the ID path, the name search and manual apply (`app.metadata_from_issue`, called from two dashboard routes in `app.py` and from `automatic.py`) trims every value ("Blade: First Bite Infinity Comic " and a trailing-space series both come out clean) and drops whitespace-only values; the ID path's `verified_issue_fields` and the name search's written fields are trimmed too. The manual-apply HTTP routes themselves were not clicked; they call the same function.

## Findings

1. **Minor, open.** The ComicVine name search's cite list (`comicvine_search.CITES`) has no VerseDB: a comic whose Notes already say "Comic data from VerseDB" is still asked of the name search (it runs before VerseDB), while VerseDB itself skips it. The test brief lists VerseDB among the citations that skip a comic. Fix: one shared cite list.
2. **Info, already known (Senua s11).** Rule C's bracket guard refuses some harmless names ("(Best of 2016)", "(Chapter Ill)") and does not refuse "(Part of the Story)" or "(Book Club Edition)". Refusal is the safe direction; no wrong match is possible.
3. **Info.** The probes drive real `automatic.discover` passes and the real lookups, with Metron and GCD offline patched to miss (or hit), the cover download replaced by the recorded bytes and saved evidence supplied through a patched `reuse`; nothing ran through the live app's worker beyond the smoke.

Pattern alerts: none

## Not covered

Live behaviour of either source (the pilots and Futaba's write sample covered it; no live keys or requests here), the ComicVine ID path's shared allowance under load (S2) and the pass-time and worker-share reading Senua says is owed on the real machine before a switch goes on (S3), a real GCD offline index, a real VerseDB token, the dashboard's manual-apply clicks, Windows Explorer's icon raster, installer execution, an actual update, GPU release, and power-loss durability. All runs used private state roots, private ports and private model and feed stubs; Sergei's profile, `%LOCALAPPDATA%\ComicsMeta` and the installed app were not touched, and no focus was taken.

## Evidence

Folder: `I:/AI Projects/Studio Illuminati/WIP/Comics Meta Organizer/scratch/qa-065-evidence-v0.6.5/` (in the tool's ignored `scratch/` folder; name it in the promotion config or release notes before the 48-hour idle sweep reaches it).

| File | SHA-256 |
| --- | --- |
| `tray-evidence-v0.6.5.json` | `9b85b25f2b1d8463313bbe7e98e8b1d6ffc91eceacd3f78ac65ce3c14fce68c7` |
| `tray-owned-v0.6.5.json` | `9e72b6c69c99fe10915664bf5245a5c43ca266368ddb7ca72de3f0d1bd8c3d89` |
| `package-binding-v0.6.5.json` | `a6f3aff5727f8b3e569df154c53d73a2773c223cf3ef201434a47f8d56a99f68` |
| `extraction-owned-v0.6.5.json` | `29e787a6a63aa8e81504ca9438f7f40b31c38496afea1acd0d18c26a26b83c88` |
| `asar-evidence-v0.6.5.txt` | `d65de056b0583d522a6b5b64976cdd28205542858fea2a4a623e4139c278f6de` |
