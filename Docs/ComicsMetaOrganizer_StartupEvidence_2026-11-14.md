# Comic Metadata 0.6.1 startup evidence, 2026-11-14

All live checks used file reads, process/listener metadata, an immutable SQLite connection, or HTTP routes verified to return without opening the database. The authenticated status route runs write-capable SQLite setup and was exercised only on isolated state.

## Installed baseline

- Installed `ComicMetadata.exe` version 0.6.1.0. The installed Python app, broker, pause, setup and supervisor modules and the ASAR main and engine files matched Git tag `v0.6.1` (`516c812d90b9482f5cd63003d660f178e0c65444`) after CRLF normalization. Installed ASAR SHA-256 `b2a7c47757450b1f05b0327dd9d6557c9113b279d188b349b3da1cec17ffe494`.
- Comic shell PID 44792 started at 20:32:41.668450 local. The desktop log reports `Engine start timed out` at 20:33:12.202, again at 20:33:42.811, then approximately every 30.6 s through at least 20:41:52.933. In one attempt, its owned broker PID 39100 began at 20:39:50.910206 and its app PID 102240 at 20:39:51.059089. That app owned listener 8765 within the same second and the attempt still timed out at 20:40:20.995. During a subsequent attempt, loopback static GET returned HTTP 200 in 20.037 ms and the non-mutating no-token status branch returned 403 in 2.979 ms.
- Books Arranger shell PID 16520 started at 20:31:46.156329, with engine child present by 20:31:47.134464. Its `I:/Books Arranger/Profile/last-load.json` recorded 122,641 ms and was written at 20:33:54.201191. The application writes that file after observing completed load. The estimated overlap from Comic shell start to the observed Books completion is 72.53 s, with the Books completion observer polling about every second. The repeated Comic failures continued many minutes after Books completed.
- Read-only `Y:/Comix` folder checks took 0.14–0.34 ms combined across five warm samples. Both live dotenv sources decoded as UTF-8-SIG in under 0.8 ms. The live config had an absolute dotenv fallback and no DPAPI config pointer, overlay or credential directory. The fraction catalog migration marker already existed in the checkpointed SQLite view.

## Isolated result

Read-only production checks found all NUL bytes in `data/browser-search.json` (1,644), `data/progress.json` (30,283), and `data/folders.json` (1,659,323). `browser-heartbeat`, `automatic.json`, and `maintenance.json` were valid JSON objects. No live contents or secrets were copied.

Exact installed Python sources and a 40,583-row sanitized catalog were run with owned private state, an ordinary fixture root and private lock directory, a dynamically selected loopback port, and a fresh synthetic shell nonce. The phase harness invoked actual application initialization and handler functions, without Electron or worker launch, and exited after the local server was shut down.

| Replica phase | ms |
| --- | ---: |
| App import | 123.884 |
| Auxiliary imports | 27.080 |
| First catalog init | 28.418 |
| Fraction migration marker check within catalog init | 0.044 |
| Begin run | 2.317 |
| Clear shell pause | 9.119 |
| Claim fixture library | 4.002 |
| Initialize local server | 25.667 |
| HTTP GET status, authentication and first full response | 16.580 |
| Lens status within GET | 7.853 |
| Pause status within GET | 2.561 |
| Setup status within GET | 3.608 |

A/B/A on that same replica with no shell or worker changes confirmed the trigger. Missing `browser-search.json` yielded authenticated HTTP 200 in 19.3 ms. Adding 1,644 NUL bytes yielded HTTP 400 in 2.32 ms with `Expecting value: line 1 column 1 (char 0)` while the static page returned HTTP 200 in 2.56 ms. Replacing the private fixture file with `{}` restored HTTP 200 in 9.66 ms. The installed shell swallows those HTTP failures until its 30-second startup deadline, then force-stops and retries on the owned engine exit; the individual status response is fast.

## Catalog provenance

Original state read from `%LOCALAPPDATA%/ComicsMeta/data/catalog.sqlite` at 267,956,224 bytes. Verified unchanged identity, size, modification time and change time throughout extraction. No WAL, SHM or rollback journal was present at checks before, during or after extraction. Source SHA-256 before and after matched `5355caa6003a00747bcf61c6e1ef1aee6fafc7aed4795078ece1af52ae7e0724`. The SQLite `mode=ro&immutable=1` source was backed up into memory and passed `integrity_check`. Only sanitized data was persisted.

The sanitized copy preserves 40,583 comics, 47,461 history rows, 47,383 write entries, 34,762 cover tasks and 40,572 discovery rows. Fixture paths replace live paths. Recognized catalog metadata fields keep their approximate value lengths and presence with synthetic strings. Opaque values and other state tables were cleared. The historical 8,115 roots were replaced with one fixture root. Queue, progress, jobs and credentials were never cloned. The 67,211,264-byte copy and the exact-size 267,956,224-byte alternate pass `integrity_check`. The exact-size copy uses 49,010 inert SQLite freelist pages and does not reproduce the live DB's logical page placement or query distribution. SHA-256 `25e10f2e53fa6bae90dc9f487a5b6808227bb55503337a20639a45b44c904a5c`.

## Independent startup controls

Futaba ran the installed 0.6.1 engine against the exact-size sanitized copy using private state, under a Windows Job. First authenticated full status came 646 ms after broker spawn with no competing fixture startup and 633 ms during the installed Books Arranger 0.28.5 backend's real startup loader on a 45,000-row Books fixture. These are single runs with the user's original sessions still present. The loader reported 10.734 s overall. The local contention controls isolated a separate issue: holding a private Comic catalog's SQLite write transaction for about 28 seconds delayed readiness to 28.22 s. With a 35-second hold the installed broker exited at about 33.24 s, reporting a locked database. This is independent of the corrupt-status rejection.

The actual installed Electron shell, run offscreen on private fixture state with the three exact-size NUL-only files, showed `START_TIMEOUT` about 30.15 s after native broker spawn. Authenticated status had returned 400 while the static page returned 200. Retry actions appeared after broker code 125 confirmed termination. Tray Quit closed all owned processes.

## Private Windows build

The stock offline packaging path completed from the physical `I:/AI Projects/Studio Illuminati` tree with pinned Node 26.12.1 and the prepared Electron and NSIS inputs. The NSIS path preflight passed. The private installer reported no uninstaller bootstrap execution and matched its final receipt by byte size and SHA-256. The corrected build is still labelled 0.6.1 and was neither published nor installed.

- Installer, 149,541,692 bytes, SHA-256 `f8eb301838edb8ae360ccdbf6d6e01775d0225af537ee62c4e1b1f2a1e1c2a09`
- Unpacked executable SHA-256 `cec7e99b188bf8ed5ec20ff0fa8513ed5af9f9eae71ffa94874e4718845a86a4`
- Packaged `app.asar` SHA-256 `5bfec9e893b8577e4edbd8c531f7c07eeef92d9e98d05a5fd074e9e1b4567bc8`

## Candidate behavior and final private tests

- The authenticated startup route can answer while catalog initialization runs. It publishes coarse phases and blocks full dashboard operations until initialization completes. It gives the endpoint 20 seconds to answer and caps startup work at 600 seconds. The user sees a long-wait notice after 10 seconds. Transient SQLite BUSY/LOCKED retries are restricted to idempotent initialization. An established dashboard tolerates brief repeat failures in its richer status poll.
- Starts share one in-flight attempt. Retry is enabled after native broker closure confirmation. Claim pairs unique to that engine generation are retired under the library gate once its Windows Job is empty. A failed initial start does not schedule another engine automatically.
- Unreadable browser status, saved progress and folder schedule are reported without removing or replacing the original files. Browsing and automatic processing that depend on those records wait for recovery. Status and inventory remain usable. Ender verified targeted tests with 57 Python and 15 Node passes, including corrupted status, library admission, exit/force and polling recovery. These are targeted checks, separate from the formal release gate.
- The packaged app on the full-size sanitized catalog reported authenticated startup at about 0.62 s after broker spawn and full status at about 0.64 s. Books Arranger was in its real authenticated catalog loader on a 45,000-row Books fixture. The dashboard presented 40,583 items, `/api/progress` returned 200 with damaged status markers, and twelve authenticated status samples returned 200. All three supplied corrupt inputs retained their SHA-256 hashes.
- Under a separate 35-second writer-lock test, the packaged shell showed the catalog phase within about 0.59 s of broker spawn, displayed the long-wait notice, and reached full owned status about 34.37 s after broker spawn. The lock began before the broker. One broker served the case and twelve subsequent samples returned 200. The live short-path smoke was offscreen at 640x480 and 1280x860.
- A real conflicting fixture library claim caused the first broker to exit with code 75. After confirmed exit and release of the other claimant, two Retry calls produced one replacement broker. The test exited normally and left zero library claim files and zero processes in its private Windows Job. Other final cases also ended with zero owned processes and claim residue.
- The packaged shell also passed the independent synthetic Comic fixture during Books Arranger's own fixture startup. Authenticated startup and full status answered at about 0.60 and 0.62 s after broker spawn, respectively. The Books catalog sample's progress age showed its catalog phase spanned Comic readiness. Twelve owned status samples returned 200, and the private quit left no claims.

## Live-install boundary

The candidate was packaged but not installed, and no test launched it against the original catalog or Y:/Comix. The exact-size test catalog derived from real SQLite rows and used private fixture data and paths. A normal live start writes catalog control and verification rows, worker leases/heartbeats/logs and maintenance state. If automatic processing is enabled, it may resume archive activity on Y:/Comix. The copied-catalog proof does not verify that live-write path. A live test also needs a fresh Books startup or must be reported as testing alongside an already running Books session.

The failure/retry starts were separated by 687 ms from the first job broker's recorded exit to the second broker's spawn. The double Retry used the actual offscreen retry button. Native closure was independently checked after the test series. Two preliminary harness attempts required cleanup: one closed through its guarded private inspector, the other via its verified outer Job owner's kill-on-close handle. All test process trees subsequently disappeared. The packaged runs ended normally.

The startup and retry captures were inspected at the minimum requested size. Status and late copy were readable, and the three failure controls did not overlap. Offscreen viewport scaling produced 642x481 and 1282x861 pixels. Detailed measurements, hashes, and retained screenshots are in `scratch/startup-20261114-qa/QA.md` and `scratch/startup-20261114-qa/evidence/`.

## Approved live install and concurrent start

Sergei approved the candidate installation and startup against the actual catalog with processing paused, the three damaged files preserved, and no archive changes. Before installation the existing saved pause changed from off (generation 132) to on (133) through the product pause function. The silent installer exited 0 in 17.94 seconds. The installed executable and ASAR matched the package hashes above.

Books Arranger 0.28.5 started at 21:08:13.784 local. Comic Metadata started at 21:08:16.869, and the actual dashboard route returned HTTP 200 at 21:08:18.225 after first returning 503. That is 1.36 seconds from Comic Metadata shell launch, or about 1.08 seconds after its native broker was created. The real inventory returned HTTP 200 at 1.65 seconds with 40,415 comics in the configured library scope, with no job running. The live check measured the gated dashboard and actual inventory responses, with native listener ownership verified. It did not sample the private shell authentication token or the exact first authenticated `/api/shell/startup` response.

Books Arranger's native backend was already starting when Comic Metadata launched, and at 21:10:02 its authenticated state was still loading books. A fresh `last-load.json` was written at 21:10:28.825, with 129,692 ms recorded by Books Arranger and about 135 seconds elapsed from its shell launch. Comic Metadata stayed available through completion. Its observer found zero page failures after readiness, with 49 paused status samples and no new desktop startup timeouts. The desktop log recorded one transient shell API request timeout at 21:09:43.912. The Comic broker did not restart.

Both Comic Metadata workers acknowledged generation 133. The catalog retained 40,583 total rows, 47,461 history rows and 47,383 write-ledger entries, with the same maximum record IDs. All three NUL-only files retained sizes, hashes and modification times. The worker pause was confirmed. The optional Gemma GPU release was not confirmed. Comic Metadata was left running with processing paused. Books Arranger recorded load completion and subsequently launched its own 0.28.6 updater before the final process check. The run made no archive changes and did not perform a full filesystem audit of Y:/Comix. Evidence is in `scratch/startup-20261114-live/`.

## Authorized removal after live proof

After preservation was verified for the live test, Sergei authorized direct deletion of the three zero-filled files. At 21:12:29 local, each exact path was verified as an ordinary file with the expected size, SHA-256 and all-zero contents, then removed and checked absent. The cover worker recreated a valid `browser-search.json` with state `paused`. The progress and schedule files remain absent while paused. The dashboard's three unavailability flags cleared. The saved pause and both worker acknowledgements remained in force. No backup copies of the damaged files were kept.
