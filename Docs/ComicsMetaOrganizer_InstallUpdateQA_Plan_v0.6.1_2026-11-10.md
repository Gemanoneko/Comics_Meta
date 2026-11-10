# 0.6.1 isolated installation/update QA plan

Status: preparation only. No Sandbox, installer or updater has been launched by this plan. The final candidate, input manifest and execution route still require independent review.

## Available environment

Read-only inventory found Windows 11 Pro build 26300, the Windows Sandbox and Hyper-V features enabled, and their compute services running. The classic `C:/Windows/System32/WindowsSandbox.exe` exists. The modern Store Sandbox package/`wsb` CLI is absent. Registered VirtualBox machines are inaccessible and are not repair targets. Ordinary, system and Codex-owned Windows accounts are not QA accounts and remain untouched.

The classic Sandbox client can open a desktop window. Jane must obtain permission to open/minimize/close that **Sandbox window only**, before execution. No normal ComicsMeta installation, real library, host registry, Windows account creation, feature enablement or reboot is part of the test. The maximum is two sequential sessions of 600000 ms each (20 minutes total); normal completion is expected sooner. No standing future focus permission follows.

## Two fresh guest sessions

The existing acceptance matrix's U4 requires both initially processing and initially user-paused updates. Use a fresh disposable Windows Sandbox for each, rather than downgrading/reusing a product registration between phases.

Each reviewed `.wsb` disables networking, vGPU, audio/video input, printer and clipboard redirection. It maps only a contained, authenticated installer/runtime/harness input directory read-only, plus that phase's empty owned output directory writable. Host profiles, drives, repositories, NAS paths and credentials are not mapped. The guest receives no outbound network; its authenticated loopback feed and model stub exist entirely inside the guest.

1. Authenticate the genuine published 0.6.0 installer and final 0.6.1 installer/feed bytes. Copy the prior installer into the guest, then run its actual silent per-user installer to a short guest-only install path. Verify installed version/resources and actual guest product registration. A separate installed Python or 7-Zip must not be needed by the app.
2. Run the actual installed 0.6.0 app with its existing private QA policy. Complete its real setup workflow with synthetic keys and a guest-only library. Seed a small synthetic local GCD dump/index and synthetic comics so a real app worker produces a verified fixture write and has remaining work. Do not substitute a seeded `processing` status for worker activity.
3. For the paused phase, invoke the real pause workflow and observe durable user-pause acknowledgement. For the processing phase, observe actual worker/queue activity and a pending fixture. Preserve config/source settings, credential-generation hashes plus successful private decryption, selected catalog/manual provenance/history records and recovery sentinels before updating. Secret values never enter the report.
4. Use the installed app's actual Check/Download/Confirm/Install actions against the authenticated guest-loopback feed. Do not replace its updater, production installer helper or NSIS process. Observe exact downloaded artifact hashes, actual old engine exit before replacement, the helper's real accepted installer PID, natural old-shell exit and actual next-version relaunch.
5. Verify real installed 0.6.1 version/resources, preserved state and user-pause semantics, one new engine and a subsequent real fixture action where processing is enabled. Invoke the actual packaged Exit/Quit action and require natural exit and complete guest-owned descendant closure. Changes expected from genuine completed fixture writes are distinguished from preservation losses.

The guest account owns all NSIS HKCU/Start Menu effects. A private `/D=` path by itself is not claimed as user isolation.

## Ownership and shutdown

Use the existing byte-pinned canonical private Windows Job owner inside the guest, with one original deadline. Host work also uses the reviewed bounded owner. A watchdog reserves time for evidence and shutdown. **Any shutdown command exists only in guest code**, after verifying the exact mapped guest path/nonce, `WDAGUtilityAccount`, and a guest hostname distinct from the captured host. No host shutdown command is permitted.

Normal completion requires the guest to shut itself down, its exact client/session to exit, and the host's baseline compute-session inventory to be restored. The existing saved template is never a stop target. On uncertainty, fail QA, preserve actual evidence and ask for help closing only the owned Sandbox window; do not claim VM closure or kill unrelated processes/compute systems.

## Publication receipts

Only after real success may a narrowly reviewed data adapter create legacy publication receipts. It binds the accepted source/build/artifact manifests, actual successful ownership records, formal QA/review report hashes, both guest install/update observations and state-preservation comparisons. Missing installation/update or closure proof remains a refusal, never a passed boolean. The publisher's requirements remain unchanged.

## Prepared launch files

Owned root: `C:/Antigravity Projects/Studio Illuminati/WIP/Comics Meta Organizer/scratch/install-update-061-20261110`.

- `processing.wsb` and `paused.wsb`: reviewable launch configurations.
- `input/`: read-only mapping; final pinned Node, ownership runtime, prior/new installer bytes and guest scripts are staged before launch. It is not yet executable acceptance evidence.
- `output-processing/` and `output-paused/`: each phase's sole writable host mapping.

Cleanup removes only verified owned outputs after durable evidence is saved and consumers finish. Earlier automatically rejected cleanup targets and their parents are not retried. Current candidate/toolchain/needed forensic evidence stays preserved until release consumers finish.

Primary references: [Microsoft Sandbox configuration](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-configure-using-wsb-file), [Microsoft Sandbox CLI](https://learn.microsoft.com/en-us/windows/security/application-security/application-isolation/windows-sandbox/windows-sandbox-cli), and `ComicsMetaOrganizer_InstallerQAAcceptance_2026-10-14.md` U4. This plan does not approve its own execution.
