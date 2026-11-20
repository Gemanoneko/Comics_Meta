# Comic Metadata 0.6.9 release receipt

The production installer was promoted from source commit `67c7b53008609f7f88879abb0ab339fa4577958e`, tagged `v0.6.9`. GitHub serves it as the latest published release. [GitHub release](https://github.com/Gemanoneko/Comics_Meta/releases/tag/v0.6.9)

| Asset | Bytes | SHA-256 verified locally and on GitHub |
| --- | ---: | --- |
| `Comic-Metadata-Setup-0.6.9.exe` | 150095887 | `468f1772151a547549744a6941391d0836a0c7e51611e6984961a45f77be57c2` |
| `Comic-Metadata-Setup-0.6.9.exe.blockmap` | 157867 | `0f5226243c0dceebb0b67f34248e666f11716441160a4dbf53bc92891a81c694` |
| `latest.yml` | 357 | `38da45e23fae7e64bbd1a9a9e3d892f91e24cd7a7e71093691182fe4253bb67e` |

- All five release gates passed. Senua cleared the exact source. Futaba gave the packaged build a tray-smoke GO. All 17 owned QA scenarios passed. The packaged app displayed 0.6.9 and tray Quit closed its process tree in 6.581 s. The packaged conversion cases used CB7 and a 7-Zip archive named CBZ. Installed-update verification is deferred to a manual update.
- Promotion profile `packaged-smoke-manual-update`. Receipt SHA-256 `b4d838b116bf28e97cbdb598ca028bfb62df0484583b6be63468740581be16c2`. Creation, `--check`, named tag push and `--publish` all completed under the owned process supervisor with empty process trees. Publication uploaded the same assets without rebuilding.
- GitHub retains four releases, v0.6.9 through v0.6.6. The retention command removed the v0.6.5 release. It retained the tag, consistent with the existing Comics Meta Organizer publisher. After tag pruning, the 22 local tag names matched the remote.
- QA follow-up evidence. In scenario `app-flush-hold`, a fixture helper opened the temporary archive with `FILE_SHARE_READ` as the app closed its writer. A 4 s hold succeeded after release. A hold past the flush deadline returned HTTP 400 in 10.328 s. Original and retained backup were byte-identical, and History had no new entry. Retrying after the hold ended and after an app restart both returned “A temporary file already exists; inspect it before proceeding.” The pending record count was zero and the temporary archive persisted. The archive below includes the scenario harness, raw result, owned closure record and configuration.

[Packaged QA](ComicsMetaOrganizer_TrayQA_v0.6.9_2026-11-20.md) · [Code review](ComicsMetaOrganizer_CodeReview_v0.6.9_2026-11-19.md) · [Release evidence](ComicsMetaOrganizer_ReleaseEvidence_v0.6.9_2026-11-20.zip)

The evidence ZIP is 173292 bytes, SHA-256 `559780a2a0ed00a8b6f5800f0faa73a2601245b14377f34c0761eb6c319f4b27`. All 54 members were opened from the ZIP and matched their original SHA-256. Its paths record the original isolated Windows run. To reproduce the QA follow-up, see `harness/README-harness.txt` and adapt the recorded paths to a fresh private fixture root.
