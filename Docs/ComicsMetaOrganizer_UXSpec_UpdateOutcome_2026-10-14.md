# Installer launch outcomes — narrow shell UX amendment

Date: 2026-10-14. Owner: Judy. Status: reviewable; Sully commits before implementation. EXTEND DesktopShell_2026-10-12 §4 failure rows, §4a disabled states and §5 failure routing only. No installer, update or recovery action introduced. Basis: NN/g truthful status and error prevention; WCAG status/focus; existing shell controls and dark palette.

## Contract

Ender's reviewed receipt distinguishes three boundaries:

- Proved no installer creation: started:false,accepted:false. Restoring the old engine is allowed by the existing safe operational flow; only this state may say “did not start” and offer a deliberate installation retry.
- Process created, early exit: started:true,accepted:false,phase:observe,code:installer_exited_early. Exit0 or1 does not prove resources unchanged or update completion. Do not restart the stopped old engine or retry installation automatically.
- No trustworthy receipt (malformed, timeout, missing): started:null. Outcome unknown. Same hold as process-created failure.
- accepted:true,started:true proves process creation and400ms liveness only. Handoff to installer is not successful installation; no “Update installed” claim based on this receipt.

The visible error reflects this boundary, not a generic exception string. Pre-stop/download verification failures retain existing recovery semantics because no installer was launched. Raw diagnostic codes remain in retained logs; none shown as a supposed fix.

## Exact visible states

| Boundary | Main message | Supporting text | Actions |
|---|---|---|---|
| Proved not started | “The installer for v{target} did not start.” | “The downloaded installer is kept. You can try installing again.” | **Try again**: “Try starting the downloaded installer for v{target} again.” Existing safe restore of earlier processing state must finish first; if restore fails, do not imply processing resumed. **Open log folder**: “Open the logs for this update attempt.” Dismiss follows existing banner rule. |
| Created and exited early | “The installer for v{target} started, but the update did not finish normally.” | “Installation may be incomplete. Processing stays stopped. The downloaded installer and recovery evidence are kept.” | **Open log folder**: “Open the logs for this update attempt.” **Quit**: “Close this app window. The installer is not restarted.” No install Retry, service Try again, forced install or rollback. |
| Unknown | “The outcome of the v{target} installer could not be confirmed.” | “Installation may have started. Processing stays stopped. The downloaded installer and recovery evidence are kept.” | Same Open log folder and Quit; no retry/start/resume. |

Target is from the verified downloaded update metadata; if absent, omit v{target} rather than invent it. On uncertain branches display a version detail line: **This window: v{loadedShellVersion}. Installed version: not verified.** Loaded-shell version is the executable's startup identity, not a file that may already have been replaced. Only if Ender has independently verified the actual installed version may the latter say **Installed version: v{verifiedVersion}**; it does not assert update health or permit old-engine restart. If loaded-shell identity is missing, show **This window's version: not available. Installed version: not verified.** Never leave an old dashboard badge as evidence that old resources remain intact.

Current implementation has no coherent installed-payload version detector: use the not-verified line. The shell survives helper failures; app.getVersion identifies this running shell only. The sanitized retained receipt may record time, prior intended version, expected next version, installer hash/size and launch boundary, but these are not installed-version proof. No next-launch recovery screen is required by this amendment.

An accepted handoff may say **Installer started for v{target}.** while the existing app exits; it must not say installed, ready, verified or processing resumed. Normal next-launch health/version verification determines subsequent normal UI. This amendment does not add an installation progress monitor, persistent recovery workflow or new launch behaviour.

## Surface and interaction

Use the existing in-flow shell failure/banner style with two short paragraphs plus version detail. If stopping the engine makes the dashboard unavailable, render the same content in the existing local shell failure surface, not behind an unreachable service page. Uncertainty outranks generic service-restart error: no second competing “Try again” banner. No automatic service retry on this branch. Do not reclassify the update as download/check failed and replace these actions.

While the uncertain state is shown, suppress/don't expose install retry, manual update check, Resume and service Try again; no hidden accelerator/automatic timer may start them. Disabled Check tooltip: **“Unavailable while the installation outcome is unconfirmed.”** Unavailable controls get nearby plain explanation, not only tooltip. The uncertainty message cannot be dismissed into a normal dashboard that suggests processing is available; no × in these two states. Closing the window still follows the approved tray behaviour, if applicable, retaining the same state on show. Quit safely closes the app through Ender's existing hold-aware exit route, never kills a possibly running installer, resumes or starts the engine, retries installation, or removes evidence. Do not claim Quit stops that installer.

Focus on the failure heading (tabindex−1) once after the user-started install fails, rolealert once; no repeated focus/announcement per poll. Tab order Open log folder, Quit. Both existing32–40px controls with visible2px focus. Dialog/confirmation closes before this replacement surface appears; no covered focus. At320/640/1280CSSpx and200% zoom paragraphs/version wrap and actions remain in flow. Returning from log-folder action leaves focus on its button; folder-launch failure gives “Could not open the log folder.” without changing the installation boundary. Keyboard Escape does not discard the uncertain state. No audio/toast/forced foreground.

## Evidence and acceptance

Retain the already downloaded installer and launch receipt/log/recovery evidence under existing storage policy. UI log-folder action opens that attempt's actual safe folder; no automatic redownload, deletion, repair, rollback or second installer. The separate receipt/identity checks and recovery choice belong to Ender/Iris, not a UX-created “fix”. No new product decision is needed for truthful status and safe existing actions; STOP if implementation needs a new recovery action or assumes resources unchanged without proof.

Futaba isolated fixtures: provednotstarted with prior running/userpaused states; created earlyexit0/1; missing/malformed/timeoutreceipt; accepted400ms handoff; loadedversion differs from target; installedversion unknown/verified; generic service retry previously queued; dashboard unreachable; dismissed/reopened window. Assert exact text/knownversion provenance, no install Retry/resume/service-start/check actions in uncertain states, no automatic restore on those paths, no evidence cleanup, accepted receipt not completion claim. Verify logfolder/Quit don't run installer or engine, focus/alert once, keyboard and measured target/overlap/reflow. Source-only specification, no native execution, no live/state/secret/config/hook/trust mutation. Excludes broad redesign, install completion detection, rollback/recovery product scope and readiness claims.
