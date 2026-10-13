# Comic Metadata — First-run setup UX spec

Date: 2026-10-13. Owner: Judy. Status: ready for Sully commit before Ender implementation. NEW first-run surface; EXTEND the existing standalone shell, not its dashboard. Sergei approved an in-app setup screen for library selection and optional API keys. The committed DesktopShell_2026-10-12 §§1–7 and §11 governs window/tray/quit/theme; DashboardTooltips_2026-10-12 governs existing controls. No onboarding tour or new provider is added.

## Entry and processing contract

Show setup in the ordinary Comic Metadata shell window when a new selected state has no valid completed library configuration. Existing usable configured states continue through the approved startup path; never copy/import another installation's state automatically. Detecting first-run and validating configuration are Ender's implementation responsibility. An inaccessible existing library is a startup failure, not a reason to overwrite existing configuration with new defaults.

Heading: Set up Comic Metadata. Intro: Choose your comic library. API keys are optional.

First successful setup saves the selected folder and explicitly starts ordinary processing, consistent with DesktopShell §3/A1: launches process unless a user pause is recorded. Primary action therefore reads Save and start processing. Above the action row: Processing starts after you save. The app writes verified metadata into eligible comics in this folder and its subfolders. First-run must not write a durable user pause. Any existing user pause and unrelated config/provider settings are preserved; if such a state reaches setup, primary action is Save and open dashboard and the sentence is Your saved pause stays in effect. Resume processing from the dashboard when you are ready.

Ender reconciles template automatic.enabled=false with this approved explicit start contract using the existing automatic configuration consumer. Save is the user's start action; there is no automatic sign-in/startup, paid-source activation or restart-policy change. Engine research/writes and provider requests do not start before a successful save. Local validation does not require provider contact. Failure leaves processing inactive and setup open.

## Layout and controls

Normal page in the existing framed dark window, no new modal or wizard steps. Centred column max640 CSS px, side gutter24px (16px at400px and narrower), vertical page scrolling allowed. Heading30px, section headings20px, labels/body16px, help14px/1.5. Use existing dark palette: background#12151c, input#242c3b, text#eef2fb, secondary#aab4c6, border#aab4c6, focus#bcd8f9. Secret/input text contrast12.50:1 and help8.74:1 against page. Primary#385ea1/#eef2fb,5.70:1; hover retains fill with visible inset border. Every field/button min40px high; show/hide controls min32×32; visible2px focus outline,2px offset. No ambient animation.

Order:

1. Library folder, required. Label Library folder, full-width editable text input, no sample personal path. Browse… button beside it with8px gap, dropping below at narrow widths. Native folder picker owned by this shell; cancelling picker keeps existing input. Help: Includes comics in subfolders. Pick the folder you want this app to process.
2. Optional API keys, native expandable details section, initially collapsed. Summary Optional API keys. Collapsed help remains visible: You can leave these empty. Adding keys does not switch on paid search. Five fields below, each label above a masked password input with separate Show button to the right (wrap action below if needed). No GCD account/password fields or Open Library contact field: these are credentials/contact details, outside the approved key-only scope.
3. Start-effect sentence above Save and start processing (primary), Quit (secondary),8px gap, wrap left-aligned. No Next/Back/Skip tour, settings page or source toggles.

| Visible field label | Existing consumer name | Help |
|---|---|---|
| ComicVine API key | COMICVINE_API_KEY | Linked comics wait for a ComicVine check if this key is missing. |
| Metron API token | METRON_API_TOKEN | Optional access to Metron. |
| Google Books API key | GOOGLE_BOOKS_API_KEY | Optional access to Google Books. |
| Brave Search API key | BRAVE_SEARCH_API_KEY | Used only when Brave search is configured. Paid search stays off unless already enabled. |
| SerpApi API key | SERPAPI_API_KEY | Used only when the existing search fallback is enabled. |

Internal names in the table are for Ender and tests, never visible field labels. Do not add external account links or credential examples. Existing quotas, disabled sources and model switches remain unchanged. A saved key is not a claim it works or that its service is enabled. No Check key button or provider/network test in setup.

## Validation and saving

Allow typing/pasting an absolute Windows library folder or selecting through Browse. Validate nonempty, absolute directory, exists/readable, and one-writer library-overlap claim before processing starts. Never create the folder from a typo or silently select a parent/child. Ender owns OS path rules and archive write safety; do not require writing a test file into the chosen library. If write permission cannot be known safely, leave existing per-archive verified write/error handling in place rather than claim the entire library is writable.

Validate optional keys locally only: empty is allowed; trim surrounding whitespace once, preserve internal characters. Reject newline/NUL values that cannot be safely saved as one credential value. Do not invent provider length/character rules or minimum-key requirements. No masked secret placeholders become literal saved keys. First-run has empty entries. Existing saved secrets, if encountered, show Key saved plus a blank replacement input with help Leave empty to keep the saved key; never return the actual saved value to the renderer. Removing saved credentials is outside this first-run surface.

On save, keep the library/key controls disabled and show Saving… on the primary action (fixed minimum width equal to idle button width); aria-busy true. One save request only. On successful durable save of config and secrets, clear secret fields from renderer memory, then enter the approved Starting the local service… path; no fake success dashboard. Save only this folder and supplied key values, preserving unknown config fields, existing .env values and unrelated settings. Technical storage/location/atomicity/permission scheme belongs to Ender. Config root consumer is automatic.library_root; legacy automatic.root behavior is Ender's compatibility responsibility. If a split save fails, do not start processing or claim Setup complete; report the failure and keep existing state safe.

Plain inline error under the affected field, attached by aria-describedby and aria-invalid. No raw paths/tracebacks/keys in alerts or logs. Examples:

| Failure | Copy |
|---|---|
| Missing folder | Choose your library folder. |
| Relative/invalid folder | Choose an absolute folder path or use Browse. |
| Missing/not a directory | This folder was not found. Choose another folder. |
| Unreadable folder | This folder cannot be opened. Check its permissions or choose another folder. |
| Overlapping live library claim | Another copy is processing this library. Quit that copy, then try again. |
| Key contains unsupported line breaks | Enter this key on one line. |
| Config/secret save failed | Could not save setup. Check access to the app's data folder, then try again. |
| Unknown local validation failure | Could not check this folder. Choose it again or try later. |

Save failures re-enable controls and retain unsaved entries only in this open setup session; do not echo any key or return persisted secrets. Show an error summary (role=alert, announced once per failure) above the action row; focus first invalid field on validation failure, or summary tabindex=-1 on save failure. Focus/scroll only after user action, never on a background poll. Error message/status writes occur only when changed. Retry uses the same Save action; no new recovery button.

## Cancel, keyboard and tooltips

Quit exits without saving draft values; nothing is running to pause. Ctrl+Q and Alt-menu Exit match it. Window close/Alt+F4 follows the existing shell hide-to-tray rule; setup draft remains until reopened or Quit, with processing inactive. During incomplete setup tray shows base icon with tooltip Comic Metadata — Setup required; Open returns to setup, Pause/Resume disabled, Quit exits. This one new state describes the already-approved first-run surface, not an auto-start policy. Never start engine or create a processing badge just because the setup window was hidden. If no tray exists, Close exits as in the base spec.

Tab order follows visual order: library input, Browse, optional summary, expanded key inputs and Show buttons in listed order, Save, Quit. Enter in library/key fields submits Save only when no folder picker is open; Enter/Space activate buttons, Space/Enter expand summary; Escape cancels native picker and restores Browse focus, but does not discard form or save. Focus library input on first setup arrival; after expanding keys leave focus on summary (next Tab reaches first input). Native picker owns its sanctioned overlay. No background window focus change, audio, toast or new notification. Testing must use approved isolated no-focus harness.

| Control | Tooltip / accessible description |
|---|---|
| Library input | Full path of the comic library to process. |
| Browse… | Choose your comic library folder. |
| Optional API keys summary | Show optional keys for existing sources. |
| ComicVine key input | Optional ComicVine API key. Leave empty to skip. |
| Metron input | Optional Metron API token. Leave empty to skip. |
| Google Books input | Optional Google Books API key. Leave empty to skip. |
| Brave Search input | Optional Brave Search API key. Adding it does not enable Brave search. |
| SerpApi input | Optional SerpApi API key. Adding it does not enable its search fallback. |
| Show / Hide per field | Show this key. / Hide this key. |
| Save and start processing | Save this library and optional keys, then start processing. |
| Save and open dashboard, saved user pause | Save setup and open the dashboard. Your saved pause stays in effect. |
| Saving…, disabled | Saving setup. No further clicks are needed. |
| Quit | Close Comic Metadata without saving these changes. |

Show accessible name Show {provider} key, changing to Hide {provider} key; contains visible label. Show toggles only that input, leaves caret/value, aria-pressed true while revealed. No copy-to-clipboard button. Re-mask on focus leaving that key row, page hidden, or submission. Native tooltip uses title and same accessible description, no duplicate reading spans. Labels remain visible; placeholder is never the only label. Status and error announcements contain no secret. Clear draft credentials on Quit and successful save; no localStorage, URLs or history serialization. Storage tech remains Ender's decision.

## Acceptance and handoff

Futaba: scratch state/library only, provider requests refused, no live state/locks/profile/port or OS focus. Test320/640/1280 CSS px and200% zoom, keys collapsed/expanded, long path, field errors, saving disabled, failed save, reveal/hide, picker cancellation, incomplete setup closed/reopened, successful save/start, existing saved user pause, and overlapping library refusal. Measure control rectangles, target sizes and hit tests, no intersections or sideways page scroll; Show controls must not cover input text. Read names/descriptions/alerts from DOM/accessibility tree; verify keyboard order, visible focus, error focus and picker focus restoration. Validate blank optional keys allow completion, mixed newline key fails locally, no provider request occurs before or during validation, and source enable switches are unchanged. Never display/log/serialize actual test key values except owned saved secret storage; check with synthetic sentinel, never real credentials. Confirm exactly one save/engine launch and no processing before successful persistence. Existing dashboard/shell regressions follow their specs.

No unique source/evidence or scratch output created for this specification. Exact owned file: Docs/ComicsMetaOrganizer_UXSpec_FirstRunSetup_2026-10-13.md. Sully commits it before Ender implements new controls. No code/git/live mutations by Judy.
