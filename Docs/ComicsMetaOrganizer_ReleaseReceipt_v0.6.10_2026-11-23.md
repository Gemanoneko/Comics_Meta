# Comic Metadata 0.6.10 release receipt

The production installer was promoted from source commit `7eacdff5962b216a765d837e968cb97208ec3d70`, tagged `v0.6.10`. GitHub serves it as the latest published release. [GitHub release](https://github.com/Gemanoneko/Comics_Meta/releases/tag/v0.6.10)

| Asset | Bytes | SHA-256 verified locally and on GitHub |
| --- | ---: | --- |
| `Comic-Metadata-Setup-0.6.10.exe` | 150096422 | `004471bd6a58dbd8f0d0b37f277bd5363a6493a56408dd3d3f2ea521ae7b5be4` |
| `Comic-Metadata-Setup-0.6.10.exe.blockmap` | 157572 | `1869184f2cf228c60428167495724c17489ff03fb973e3fbff5bd445acc27654` |
| `latest.yml` | 360 | `35588d5997e0c50f4968c6b270c50a11425c8930389cb13c02b39546f2440be5` |

- All five release gates passed, with no skip flag. Senua cleared the exact source (`67c7b53..7eacdff`). Futaba gave the packaged build a tray-smoke GO on 2026-11-23; her 2026-11-22 NO-GO is for the retired `86425b1` build and stays as history. The packaged app was launched once in a private profile on a separate desktop and closed by native tray Quit. Installed-update verification is deferred to a manual update.
- Sergei approved the release on 2026-11-22. Published 2026-11-23T07:39:22Z. The update feed downloaded from the release's latest-download address names version 0.6.10 and has the SHA-256 above.
- Promotion profile `packaged-smoke-manual-update`. Receipt SHA-256 `a4e6433f43bc460f0f03dac55a576541903c826e981a17d4cf1ad845676b06e5`; source manifest SHA-256 `7743383944d90716bc7c1fa1d454e6462e9ae213c995834434a8ff696f5d5266`. Creation, `--check`, named tag push and `--publish` all completed under the owned process supervisor with empty process trees. Publication uploaded the same assets without rebuilding.
- The tag names the built commit. Main carries one docs-only commit on top of it before publication (`d3ea418`: the code review and the two packaged-QA reports), as for 0.6.8 and 0.6.9.
- GitHub retains four releases, v0.6.10 through v0.6.7. The retention command removed the v0.6.6 release. It retained the tag, consistent with the existing Comics Meta Organizer publisher. After tag pruning, the 23 local tag names matched the remote.

[Packaged QA](ComicsMetaOrganizer_TrayQA_v0.6.10_2026-11-23.md) · [Earlier NO-GO, retired build](ComicsMetaOrganizer_TrayQA_v0.6.10_2026-11-22.md) · [Code review](ComicsMetaOrganizer_CodeReview_v0.6.10_2026-11-22.md) · [Release evidence](ComicsMetaOrganizer_ReleaseEvidence_v0.6.10_2026-11-23.zip)

The evidence ZIP is 9171 bytes, SHA-256 `d1337d1d8326f26a93b73d25d74a819f1cae08fc826a4f00b15ae248e3737b05`. It holds the nine publication records: the promotion configuration, the promotion, build and QA receipts, the release notes, and the four owned-run records (create, check, tag push, publish). All nine were opened from the ZIP and matched their original SHA-256. Its paths record the original run on this machine.
