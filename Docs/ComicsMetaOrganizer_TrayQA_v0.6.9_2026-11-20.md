# Comics Meta Organizer 0.6.9 packaged QA — 2026-11-20

**Tray-smoke verdict: GO**

The retained Futaba runs covered the private packaged app and the release changes. I independently matched the run and extraction receipts to the candidate bytes. The test ran with offscreen windows, private app state and synthetic archives. The live library was outside the test. Installed update verification is deferred to a manual update under the no-VM release contract.

## Candidate identity

Source commit `67c7b53008609f7f88879abb0ab339fa4577958e`. The detached release checkout was clean. SHA-256 values below were measured from the retained files and compared with the builder and smoke records.

| File | SHA-256 |
| --- | --- |
| `Comic-Metadata-Setup-0.6.9.exe` | `468f1772151a547549744a6941391d0836a0c7e51611e6984961a45f77be57c2` |
| `Comic-Metadata-Setup-0.6.9.exe.blockmap` | `0f5226243c0dceebb0b67f34248e666f11716441160a4dbf53bc92891a81c694` |
| `latest.yml` | `38da45e23fae7e64bbd1a9a9e3d892f91e24cd7a7e71093691182fe4253bb67e` |
| `source-manifest-67c7b53.json` | `6419469e892915a89d0a157ee7a879a2c4417d5b3d2101e0ded601e159c36c0b` |
| `source-67c7b53.tar` | `03f00766ca69456b811a36c255b6d46f78c619ffa37cc074a95948bcbf87da05` |
| `ComicMetadata.exe` | `a6a65d499b332e58da14d7779dd33e7d52c3481b4bff14e748e0c370fdde8c47` |
| `resources/app.asar` | `1d6566285691c9a94563263512da655d0eba33d5eb61b03df3cc88768f1d8ea0` |
| `fPromo.promotion.json` | `599be6cafa34c7637c2cb11ed121bec4cbbe558b703a5ae0f9ee1dc7e96a838f` |
| `fPromo.owned.json` | `8c9a38c0be53893cbb7a53b6285f35b0e25ea7f7e4840cb85407e265ec16a5fa` |
| `fPromo.asar.txt` | `09dabcde361bd054bf4e9d50843e6b37f63a4d5864ee941c1e684dda0c125d2a` |
| `package-binding-v0.6.9-promotion.json` | `2940ef945df16281a8a427dedb79ff6666edb1c92a2374d149dd421f01816951` |

The pinned 7-Zip was run under a private Windows Job. Its targeted extraction and full extraction both produced the executable and ASAR hashes recorded by the running app. The full extraction contained 623 regular files. The SHA-256 of sorted lines containing relative path, tab and file SHA-256 was `2520dd650a07e7593ba0a01b620f77876444bf861176398583fd8bb85d805dd1`. Both digests in the feed matched the installer's SHA-512. The eight packaged tray PNG hashes matched the source manifest and the checked-out files.

The builder's retained private-job check records for this checkout show 1,395 Python tests with 117 skipped, and 125 Node tests with 124 passed and one skipped. Both commands exited 0 with complete final process accounting. The capsule verified again after the checks. I used the retained owned records and did not rerun the suites.

## Packaged smoke and regression

- The app reported packaged version 0.6.9 and an owned, ready engine. The native tray callbacks exercised processing, pause and resume. Quit exited 0 in 6.581 s with no surviving process, engine listener or claim. The Job was empty at exit, with zero incomplete process queries during the promotion smoke. Separate scenarios also closed from startup, setup, the dashboard, and failure or claim-hold screens. Window close kept the app in the tray as designed.
- All 17 retained scenario result files reported a pass, with matching owned runs reporting exit 0 and complete, empty Job closure. The ordinary metadata pass wrote 12 plain and three nested fixtures. Conversion checks reopened the resulting ZIPs, compared every page to its source and checked that staging and originals were retired. The packaged conversion scenarios used CB7 and a 7-Zip archive named CBZ. No separate packaged CBR fixture was run.
- Approve, worker and merge tests preserved an edit made by a second process during the rename wait. An unchanged comic held briefly succeeded after release. A comic held through the app's deadline was left intact with its backup. The merge negative control on the older source reproduced the overwrite.
- The merge continued after a held rewritten archive timed out, reported `written_unverified` and kept the backup. It also continued after a held backup could not be deleted. A non-sharing flush failure stopped the run and preserved the backup. The torn-CSV test recovered a row interrupted inside a quoted multiline value. The older tool failed that control.
- A read-only unheld claim lock allowed startup, including when its record was missing. A genuinely held read-only lock refused startup and allowed it after release.

## Findings

- **Major, recovery friction.** If another process holds the app's *temporary* archive past the flush deadline, the Approve attempt safely refuses. The original and backup remain intact and History stays empty. The temporary file still blocked a second Approve after release and after restart. The case was reproduced with a fixture process opening the temporary archive during the write.
- **Minor.** Kept backups displayed “Reason not recorded” for the worker and merge cases where a second process changed the comic during the rename wait. The backup and the second process's changes were intact.

Pattern alerts: The retained temporary file makes retries fail across restart after this specific flush refusal. QA recommends deferring cleanup of that failure state to a follow-up. The held-comic workflows, archive safety and tray shutdown passed.
