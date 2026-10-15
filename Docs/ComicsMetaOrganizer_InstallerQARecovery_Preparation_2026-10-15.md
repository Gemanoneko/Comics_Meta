# Installer QA recovery — preparation only

Date: 2026-10-15. Owner: Futaba. Scope: source-only recovery planning from retained committed contracts. No tests, builds, browser/native launches, dependency installation/downloads or installed-app operations were performed.

**Verdict:** NO-GO

This verdict records missing execution evidence, not a newly observed application failure. No installer readiness is established. The latest recap records source v0.2.1 at f39812fc082a3e406854b0a29ba7ca4248ef1d97, with Docs-only descendant 97e2b15a284e8240ccd8adc4abfdaf37c237a22d; Ender's source corrections are in progress. These identities do not freeze the next candidate.

## Blockers

1. The original Temp evidence/dependency/harness root and archive29 were absent at session recovery. Historical success claims do not supply present input bytes, a runnable graph, original screenshots, or authenticated closure receipts. The expected historical audit and replacement-graph hashes remain unverified. New measurements must be recorded as new evidence.
2. Directory/file sharing and logger identity protection remain under correction and independent review. Native work stays held until a fresh exact graph proves denied replacement through held access rights and sharing, ancestor identity, and final logger FileID continuity. Hash equality alone cannot prove pathname protection or explain renderer09's historical changed FileID.
3. There is no qualified current standalone installer or actual installed prior-to-next transition. Distinct baseline and candidate versions/artifacts must be selected and frozen by Sully; v0.1.4 live is not an installer baseline and must not be touched.
4. Committed build-entry.cjs calls the normal Windows NSIS target. The committed packaging wrapper is not, by itself, the lost archive-only interception plus pure-JS uninstaller-extraction route. Reconstruct and independently review those exact boundaries before invoking any packaging command. No generated NSIS uninstaller stub may execute.
5. The rendered recovery harness and its native ownership/closure evidence are absent. A fresh isolated harness must cover actual setup/recovery/keys integration; synthetic five-state DOM evidence cannot certify archive writes, installed IPC, tray, or installed update behavior.
6. The protocol2 qa-handoff identity/invocation record is required by InstallerQAAcceptance but was not recovered in this bounded read. Ender must supply the fresh canonical receipt and reproducible invocation; Futaba must independently produce the identical canonical receipt against the same immutable inputs before behavior acceptance.

## Retained dependency and input contracts

Paths below are relative to the installer worktree. They describe reproducible inputs; they are not claims those payloads are currently available or authenticated on this machine.

| Input | Retained prerequisite | Recovery requirement |
|---|---|---|
| JS packages | package.json and package-lock.json: electron-updater 6.8.9; Electron 43.7.9; electron-builder 26.15.3; 7zip-bin 5.2.0 | Recreate isolated locked dependency tree with lifecycle scripts disabled through a separately cleared acquisition graph; inventory complete paths, types and SHA256. The historical 290-package/7589-file inventory is not a current receipt. |
| Embedded Python | scripts/packaging/runtime-lock.json: CPython 3.14.8 win32-x64 embedded ZIP | Authenticate the exact lock SHA256 and full extracted tree; preserve nested runtime/python layout and ._pth containment. |
| Python dependencies | requirements.txt and runtime-lock.json: Pillow 12.2.0, playwright 1.63.0, greenlet 3.5.6, pyee 13.0.1, typing_extensions 4.16.0 | Authenticate exact wheel bytes. Reconstruct reviewed greenlet header relocation and RECORD mapping; unknown schemes stop. Test actual bundled imports only after graph clearance. |
| Archive engine | runtime-lock.json: full 7-Zip 26.04 x64 payload | Authenticate full executable/library tree. Format listing alone does not pass fixture CBR/image conversion. Retain source/provenance of an owned synthetic or official permissible RAR fixture. |
| Offline native tools | build-owned.py/build-entry.cjs require electronDist, nsisRoot, nsisPlugins, rcedit and builderCache | Fresh full native manifests, exact selected native binaries/versions and provenance are required. No implicit downloads; do not load electron/index.js during setup. No historical native-resources14 inventory is present. |
| Supervisors | scripts/packaging/held-paths.py, owned-job.py, build-owned.py; approved outer owner; pinned host Python/Node | Freeze corrected sources and host executable/dependency closure. One total 600000ms deadline must begin before setup, with atomic Job assignment and owned descendants queried to zero. Tool yield intervals are not deadlines. |
| Browser/render route | studio scripts/qa/headless-browser.mjs plus newly reconstructed harness and pinned isolated browser/runtime | Independently clear entire route; no direct browser spawn or signed-in profile. Native/physical checks remain separately pending. |
| State/update fixtures | desktop/qa-policy.cjs and InstallerQAAcceptance | Create nonsecret synthetic state, library, catalog, metadata, providers and private update feed under one new owned root. No live state/accounts/providers or shared GPU. |

## Minimum next route and pending matrix

| Gate | Work that can be prepared independently now | Evidence required before advancing |
|---|---|---|
| G0 sharing/logger | Ender constructs fresh corrected source and fail/pass qualification graph; Senua reviews exact bytes | Actual replacement/sharing challenges and continuous held logger identity, fail-closed errors, unchanged complete input inventories, bounded owner/native exits and descendant-zero receipts. No packaging before this passes. |
| G1 acquisition | Reconstruct dependency provenance/lock manifests and native resource plan as source only | Separately reviewed acquisition graph and authenticated staged runtime/dependency/native trees; all output identities held through consumers. Missing original bytes cannot be replaced by copied historical hashes. |
| G2 freeze | Sully names source commit/version(s), graph snapshots and baseline/candidate pairing; Ender prepares complete source selection manifest | Immutable source snapshots, version agreement across VERSION/package/lock/packaged service, complete path/type/byte closure and corrected helper inclusion. No QA against mutable shared worktree. |
| G3 archive/compiler | Reconstruct archive-only stop point and pure-JS uninstaller extraction, then literal compiler graph | Separate exact Senua clearances, fresh actual archive hash/size and computed NSIS definitions, real compiler output and closure evidence. Never run uninstaller stub. Do not reuse compiler-plan30 without its missing bytes. |
| G4 baseline/candidate | Prepare separate empty installation and state roots and private feed metadata | Actual distinct installed baseline and candidate installers, byte hashes/sizes, source/version/runtime identities and manifests; feed SHA512 matches exact candidate bytes. Both installed cases start from independently restored fixture seeds. |
| G5 rendered/integration | Prepare I1–I6, R1–R6, K1, V1 acceptance fixtures from InstallerQAAcceptance | Actual packaged setup/keys/recovery flows and archive read-back, explicit no-write preview/cancel checks, logged safe failures and measured screenshots. Screenshots of mocks do not establish integration. |
| G6 updater | Prepare U1–U5 feeds, corrupt/stale payload fixtures and expected state comparisons | Real prior→next download/stop/install/relaunch twice: initially processing and initially durable human-paused. Actual on-disk and running next version, old owned processes zero and successful next core fixture operation. |
| G7 final acceptance | Versioned evidence report and explicit limits | Futaba GO plus independent Senua final source review; required native-input checks completed only in authorized away window or explicitly dispositioned. Sully alone commits/pushes/releases exact cleared artifact bytes. |

## Private QA policy prerequisites

desktop/qa-policy.cjs requires COMICS_META_QA=1, an existing absolute TEMP-contained root whose basename starts illuminati-cmo-qa-, an in-root policy file and its exact SHA256. Policy schema1 binds root, different priorVersion/nextVersion, expiration within 24 hours, isolated enginePort, installDirectory and the candidate artifact. The feed must be http://127.0.0.1:<isolated-port>/feed/<32 lowercase hex>/ with a 64-hex authentication token. Feed and engine ports must differ and exclude 8765/11434. Artifact name must be Comic-Metadata-Setup-<nextVersion>.exe with exact positive size and canonical base64 SHA512. Profile/cache/state/locks are rooted under the same QA root. Do not publish private token or synthetic secret values in reports.

## State-preservation assertions for both update cases

Capture safe before/after manifests and semantic database checks with explicit expected differences. Catalog runtime/checkpoint changes may be expected during processing; list them instead of incorrectly requiring byte-identical databases.

- Preserve selected library and state roots, unknown config fields, source switches, optional keys and other saved key values (private sentinel comparisons only), remembered window bounds and manual choices.
- Preserve durable human pause when initially paused; running case returns running. Temporary shell pause must never become durable. Cancel and installer-start failure restore the prior pause state before claiming recovery.
- Preserve manual resolution/provenance/history ledgers, pending work, retained recovery backups and their disposition; verify next processing respects chosen human values and does not replay old signature-bound conflicts.
- Verify exact expected ComicInfo/Web entry changes by archive read-back; unrelated metadata, URLs and files remain equal. Preview/cancel/search/selection never writes; stale evidence revokes confirmation; double actions serialize once.
- No replacement begins until owned engine/browser/workers reach zero. Real installed payload changes, next process version and a successful next fixture action establish update success. A mocked launch, feed-only check, version label or installer exit alone cannot pass.
- Install resources remain immutable; mutable config/catalog/secrets/cache/locks/logs remain outside installation. One owned engine after relaunch, with no startup trigger or accidental import of the live library.

## Read coverage and limits

Successfully read AGENTS.md, DelegationPrimer, Futaba profile, relevant ProcessRules sections, latest appended recap, InstallerMilestones, PackagingHandoff, InstallerQAAcceptance, package/requirements/runtime lock, qa-policy and committed build supervisor/entry contracts. A subsequent read-only combined request for builder configuration, updater and main/engine source was refused before command launch by studio-command-safety P9 because the literal builder configuration filename matched its measured long-command rule and the tool schema had no hard timeout field. The refused route was stopped and not repackaged; no settings or safeguards changed. Those files and the protocol2 handoff implementation are outside this preparation's verified read coverage.

No disposable probes/output were created. Preserve this unresolved preparation record and all recovered original evidence. No deletions, git mutations, version changes, shared hooks/settings/trust edits, live access, physical input, sleep/resume, build or deployment occurred.

Pattern alert: repeated source-only and synthetic successes have not closed the installer/integration gate. Disposition: keep NO-GO until actual installed prior-to-next evidence and required rendered flows pass; do not roll historical receipts forward as new execution proof.
