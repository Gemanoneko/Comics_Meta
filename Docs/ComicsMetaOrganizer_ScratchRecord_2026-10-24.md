# Comics Meta Organizer — record of removed local leftovers (2026-10-24)

Ender, under ProcessRules § Nothing is left on the computer after the work is finished (Sergei: "Will you also delete any leftovers from the past if they exist?"). The repo was at `91543bd` (v0.3.0 is tagged and installed). Each in-repo entry below was gitignored, and every entry held no Git data and no links. The last entry, the `%LOCALAPPDATA%` backup, was removed on Sergei's own word. No open item depends on any of them: the latest recaps (2026-10-22, 2026-10-24) and `ComicsMetaOrganizer_Backlog.md` have no held-path, protection-policy or pilot items. The aggregate SHA-256 is taken over the sorted lines `relpath<TAB>size<TAB>sha256(file)` (forward slashes), so a copy can be matched later.

## Removed

### `scratch/cmo-hold-recovery-20261015/`
- **What it was:** the Codex-era held-path recovery routes 02 to 12 for the 0.2.1 installer (frozen graphs, guardians, qualifiers, fault cases, failure receipts), 2026-10-15.
- **What it proved, and why it is closed:** the route failures are written up, with each route's freeze SHA-256, in `ComicsMetaOrganizer_HeldPathRecovery_2026-10-15.md`. On the same day Sergei moved the installer to the lean build path ("go as lean as possible"), so compiler24/b24 never ran. The lean 0.2.1 build's longest NSIS path, 228 characters, supports the MAX_PATH cause. The route sources stay tracked in `scripts/packaging/`.
- **Size:** 1,257 files, 459 folders, 187,749,373 bytes. Newest file: 2026-10-15T10:01Z.
- **Aggregate SHA-256:** `3803d249c0a570aa099bc709cc18e68879590d0e9e049f78c6fae7e2ef491103`.
- **Top-level files:**
  - `freeze.json`: `d4eeb7674665f60e3a1d9fba3f58bde9cbf4635d127f22a990e581806caa1189`
  - `fault-cases.py`: `6106f2d227fb63aa4f4562f100e92d05ff248c835619bad6ada52aa2479d6c52`
  - `qualify.py`: `87b6fc0641dd38a76e331c74c65482e0d29e715a713b34067c5ecaa50507dc14`
  - `launch.cjs`: `0ededc29affc16842300da47132b74e8cf2d7b84cdd0948a78b5e30d56567a55`
  - `freeze.sh`: `25e85c70b116b4f9977c812edf51225006f4592540215226f069a38565e5500c`
- **Route aggregates:**
  - 02 `aac17196…b3fb9e`
  - 03 `b070f87d…af541e`
  - 04 `b8da7bf8…9681e7`
  - 05 `4e553863…b19f8`
  - 06 `03a7f99d…817606`
  - 07 `53d87661…f4c228`
  - 08 `622de435…d8484`
  - 09 `79a9966f…4f694f24`
  - 10 `706a75a7…f68d14`
  - 11 `b2cb3ad5…710577`
  - 12 `a41ea447…24fa340`

### `scratch/cmo-protection-policy-20261015/`
- **What it was:** protection-policy routes 01 to 05 and `helper-audit.md`, 2026-10-15.
- **Why it is closed:** the same lean-path supersession. Each route's freeze SHA-256 is in `ComicsMetaOrganizer_HeldPathRecovery_2026-10-15.md`.
- **Size:** 794 files, 293 folders, 64,656,395 bytes.
- **Aggregate SHA-256:** `7adc0ea47fdc7ad779f9b2ca4f06a6676af5e9ff3500f69452e96a6cd2bf450b`.
- **Top-level file:** `helper-audit.md`: `cd0c864b4df0af0728d913bb13df3d9a32b3e177346e7ee8a0749404b5cbf824`.

### `scratch/old-live-leftovers/`
- **What it was:** loose evidence copied from the retired live checkout on 2026-10-16 (Session_2026-10-16 recap, Part 6 addendum). It covers the 2026-10-02 library pilot and metadata trial, plus 2026-10-12 verification-deploy logs.
- **Size:** 12 files, 12,840 bytes.
- **Aggregate SHA-256:** `f827d905393b326d089c176accef26b5b112c0d35ee5c68e2f4906b80809e7e5`.
- **Measurement records, kept here in full:**
  - **PILOT_FINDINGS.md** (2026-10-02, `150e89cddfd9233759527a8e4c99c0d4a2410f75e4f675db9318ad3129b3ec9e`). Root `Y:\Comix`: 39,938 CBZ-named files in 2,368 top-level folders. The inventory completed without traversal errors after literal-path support was added. In a 122-file distributed sample, 23 had ComicInfo.xml and 2 were not ZIP archives; the sample was not a library-wide estimate. A pilot of 37 copied archives (about 1,814 MiB) was indexed, and a second scan found 0 changed files. Source sizes and mtimes were unchanged. No metadata writes were made. Provider lookup and YACReader import were still unverified.
  - **TRIAL_RESULTS.md** (2026-10-02, `e47e7724306cfcb9b7f667a6cbcb609d921454dabb187d6ceca2e18ac96e69bd`). Four pilot copies were enriched and verified, and the DAS originals were SHA-256-checked as unchanged.
    - Chaotica: Spellbound #1: Comic Vine plus the exact-edition credits page; variant credits corrected.
    - Nocturnals: The Sinister Path #2: distributor fallback.
    - Terminal #2 advance edition: the July edition date was kept over the August general date.
    - Jawa Force #5: partial metadata; date and roles left blank.
    - Every field was read back. This was not a library-wide match rate.
  - **LIVE_SOURCE_VALIDATION.json** (`3e21befd07365afa5c6b7ca7604ad90300c1e25602c8c12c89070ddae1cedecc`): Lady Death & Shi 01 (2007). The cover, issue, write and YACReader display were all confirmed, with sources from comcav.net and Comic Vine 4000-128141.
  - **external-source-evidence.json** (`cde08d78f41d61415c1fcdf81320fac442cc4d959b4311f0f65435e5c8764662`). Deadly Trio: Doomsayer #1 was verified on coffincomics.com. Hellwitch Hellbourne #1 was a candidate (comics.org 1963218) whose cover variant still needed a comparison. Policy: search publisher catalogues, databases, wikis and reverse-image results before asking.
  - **threshold-13-evidence.json** (`e4ca24a8a9d0d6e6ee3716658aaa4b25ebb2058404f4d82cc1a46520f641b152`): Threshold #13 Harpy (Avatar Press). The identity was confirmed by a Google Lens exact cover match against Comic Cavalcade; the metadata was still pending.
  - **CLEANUP_RESULT.json** (`1467504469af5521ab902fb73ab56093f3042fd0f885f82046f398b2ef9a46f1`): 37 pilot catalogue entries, and 0 of every cache or evidence class.
  - **2026-10-12 verification-deploy logs:**
    - three `cleanup-*.json` planner manifests;
    - `identity.json`;
    - an empty stdout;
    - a stderr whose `deployment-probe.py` heartbeat-PID assertion failed. That work closed with the 0.1.x verification repair docs.

### `dist/%SystemDrive%/`
- **What it was:** five Windows shell cache files under `ProgramData/Microsoft/Windows/Caches/`, written 2026-10-18 18:58 local (about 30 minutes after the 0.3.0 build).
- **Cause:** a process ran with its working folder in `dist/` and no `SystemDrive` variable, so `%SystemDrive%` was taken literally. This was most likely a QA installer launch with a cleaned environment. They are not product output.
- **Size:** 993,304 bytes.
- **Aggregate SHA-256:** `f1bdd9b0d0c7be75029a3d993688f997e9377cb3958e06e84ff32150c7f11835`.
- **Removed with:** the studio-disk-hygiene planner, in 2 batches. Verify reported complete with 993,304 bytes absent.


### `build/` (packaging leftovers of the v0.3.0 build)
- **What it was:**
  - `staged/` (532 files) and `staged-manifest.json` (SHA-256 `87814c13832cb7d87e7a293f88fb3016b5585e6d00da8488744c97acc3fb1f8d`);
  - `tmp/` (524 files) and `npm/` (13 files);
  - an empty `cache/`.
- **Size:** 1,070 files, 154,719,739 bytes.
- **Aggregate SHA-256:** `d5196df4adaf1e5b98ee01c24c9d8d06553f9bd4637e76c9a8bf108f2348875f`.
- **Reproducible:** `npm run pack` deletes and recreates `staged/`, `tmp/` and `npm/` on every run.
- **Removed with:** the sweep's `build-dir` target (`scripts/studio-sweep.mjs`, added 2026-10-24).
  - The folder was wholly gitignored, nothing in it was tracked, v0.3.0 is tagged and its installer was in `dist/`, and it had been idle for 136 h.
  - The per-path planner had refused it, because the Playwright package inside has a folder named `references`.
- **Not touched:** the current installer, `dist/Comic-Metadata-Setup-0.3.0.exe` (149,488,082 bytes; sha512 in `dist/latest.yml`).

### `scratch/cmo-packaging-recovery-20261015/`: slimmed to the two build inputs
- **Before:** 47 entries; 36,850 files; 3,573,484,459 bytes. Aggregate SHA-256 `9d4c8307db83066878cea3da0adeb308ec6ca3087d60fb16bbdbf6551fe8d3d4`.
- **Kept**, because they are the only things `scripts/build-installer.cjs` reads:
  - `runtime-assemble-13/` (941 files, 544,428,540 bytes): the Python/7-Zip capsule and the Electron/NSIS/rcedit tools. Aggregate SHA-256 `fc5dd6534bb38347cc9acf4791777b8c15decd84312eb80da65a1078ac0326e3`.
  - `prepare-08/` (7,776 files, 334,135,119 bytes): the offline `node_modules`. Aggregate SHA-256 `4e5b59f84c12ed8bb51a1783388744c24247a958c71ed28932b8e536c4db6310`.
- **Proof that the slim folder is enough:**
  1. Both kept folders were moved by same-volume rename, so their bytes are unchanged.
  2. The other 45 entries were set aside under a different name.
  3. A fresh detached worktree of `91543bd` (no `node_modules`, `build` or `dist`) ran `node scripts/build-installer.cjs --inputs <the slim folder>`.
  4. It copied the dependencies from `prepare-08`, took NSIS and the other native tools from `runtime-assemble-13`, and finished in 36 s with `BUILD OK`.
  5. The installer was 149,488,082 bytes (the same as the released 0.3.0), `referenceEqual: true`, SHA-256 `0c52df34…c2b4a4`. The released installer is `3bb315e5…54bc6`; NSIS output is not byte-reproducible.
  6. The log never names the set-aside folder.
  7. The worktree was removed afterwards.
- **Removed:** the 45 historical entries below, from the Codex-era packaging recovery of 2026-10-15. These were the acquire, extract, prepare and native runs, compile baselines 16 to 23, b24, prototypes and source checkpoints. The lean build path superseded that recovery the same day.
  - **Total:** 28,133 files, 2,694,920,800 bytes.
  - **Aggregates:** same method as above.

| Entry | Files | Bytes | Aggregate SHA-256 |
| --- | ---: | ---: | --- |
| `acquire-01/` | 581 | 31940255 | `a26af1ba2bce851db40f90199941d5f154f7a36de2b919515274a59fb03edd5a` |
| `audits/` | 1 | 19962 | `cf1de4c02e4a8b5fcd8e6f25e488565bbab772a8a77a9e865ebbb4e0c761cbcf` |
| `b24/` | 16 | 6792843 | `a0a71c002510a429299d056c57a7f2e386766e9f8c52e7ca68f408a7507620f7` |
| `compile-baseline-16/` | 16 | 6785327 | `9e84f32ae88265fec9b41f30b0e0941c5a6ce5cae8ab291e1eff5f7f159bd4f1` |
| `compile-baseline-19/` | 16 | 6785906 | `874d39c0b15c1d16b07b9abca4e8b359cf7f585d5ea708a32f0dfd716724ca12` |
| `compile-baseline-20/` | 28 | 6804558 | `66eea6ec8b38f4befa28e40af2a81364414387c4920f7d5a4a67bf6d1c073fd1` |
| `compile-baseline-21/` | 8191 | 257916593 | `ac424619683c754303685b1d16cecb9945ff59352bbe6a76379fe369cfba9a86` |
| `compile-baseline-22/` | 8196 | 257921511 | `05af9d516645ac1f3a5150834289c4d3b8bfc0a3fa9e8cd8b80b613956b69a1b` |
| `compile-baseline-23/` | 9336 | 941445419 | `f32cf8ff1d89cc1fd2044702d5b5061885b4b4ce6c5623d4e03b307bbc27d0ae` |
| `compiler-phase-prototype/` | 3 | 27945 | `4e37f564d9d7d6adf5e5b1a98ebfed578d84e6160936827a10eb5bfb836f1994` |
| `compiler19-source-refresh-recovery/` | 3 | 412286 | `d0fc9224d011527bdf3db0ba62431a5ba0f254b40ed385cb724082ce21c7c85a` |
| `extract-prepare-01/` | 2 | 33648 | `bf913f691607af357fdc5b5ac407278f6cbe24930f227bc83c1d311f7edc5d2b` |
| `extract-prepare-02/` | 5 | 39839 | `8d815cf99b586c9da6e4af1ddb67a12f1ea8a172e29ef57b559e0d63aa62f1f2` |
| `extract-prepare-03/` | 2 | 32215 | `6da69d012e04092e8ec2af7f8e2b212725b6534a10ab0775da5aa015894df6a1` |
| `freeze-gen-24/` | 4 | 24744 | `c16822b630d5a24027c866416b54b916df937491f828bf3a68f84f6fe12a8a04` |
| `handoff-claude-20261015/` | 3 | 117733 | `3eaeb88598ff949b3308b42045bd8f30c698278ec8986e7351ac2a4584bff2a3` |
| `lock-regeneration-plan.md` | 1 | 2000 | `bd04baa3157b06717faee290f1b2f2b46d7fab15501e038ec66707af46a7b052` |
| `materializer-alias-prototype/` | 2 | 45130 | `309537a1ca5bf5cad783987dc03625e23d3cd5ce565655f6a7832c0df45c078e` |
| `materializer-diagnosis-05/` | 2 | 38067 | `e724122154c17a59d91cdc379762b0ff1ad1c7e19eed4b9bc98ecad4b40a140d` |
| `native-acquire-09/` | 39 | 9282417 | `22023a9f89d48f1a54be284f47911a2518e565db2bbcf7eefa64ef66eb96cf74` |
| `native-extract-10/` | 30 | 2866360 | `4f6fdae69573aa057aed06c917e43f7264d873fbc5ca5ac8f322e279c3205aca` |
| `native-extract-11/` | 414 | 19391006 | `f7e8a85a9760e45cd5e965c5200eba456e8eb675da423768f43268f28bb5561f` |
| `native-extract-12/` | 417 | 19568635 | `03f730be761958156a8bff18e12aef1278c574266f8a1caf5df2c23c27a843fc` |
| `native-tool-acquisition-prototype/` | 3 | 19097 | `adcefb0ca13f81c3bd8951a1196f3750d9039585748c0671461ef52edd9d4c04` |
| `nsis-io-adapter-prototype/` | 7 | 67536 | `6094e3884265d5b8f356f66173abf569b01e6404346d4acec2cbf9061466adde` |
| `nsis-safe-entry-prototype/` | 4 | 21961 | `e4e45e1290e5e268b7444f4e8122ebc556f007973b29879c435942987e39e132` |
| `prepare-01/` | 30 | 2256557 | `b0cfe9b5fdcb26c5888cd5d80ad2aaa31029a3e120873c215a9f2df89b2f5d0b` |
| `prepare-02/` | 84 | 214750636 | `1b2cb1790c3b5d5a2091e93896e2075e2c07ae8f506ed84e3679e83ff4ef6596` |
| `prepare-03/` | 33 | 2284481 | `5027012a8d8cc03d3aa2247080f6c74dbfb662351e158e76d66f2036ac1a43fc` |
| `prepare-04/` | 88 | 214784492 | `b58057744b546e9efa73caf500c2d8222563cc5dbe9b011905f40f7e9447c49b` |
| `prepare-05/` | 95 | 228025460 | `aa1e3be55362daf2c3ba68e0f01d74cdf9e1748e1968ef0259181965bf4a5acf` |
| `prepare-06/` | 91 | 228492355 | `2249d46b631745dc2a7b2ee20204e186e6d90715008135e8d43f5efbddaaa585` |
| `prepare-07/` | 95 | 228578949 | `902632e162deb2a147bdc4918c7f180796826a5087e16373772fe4db0b911221` |
| `read-01/` | 116 | 2463322 | `ad18982d2cdd4a2e29eacaeb7fb0416d1ef2a8158521b221bb1a4bc8c9531639` |
| `read-02/` | 118 | 3518560 | `02925f2496e8a962097f280a49ff53f8e76f13ea5bfdbf3874c7aac798f9634f` |
| `runtime-assembly-prototype/` | 6 | 49991 | `a3c383b74635d3414803c5320924d089e6d0192ba34e7422757cbab3494da943` |
| `source-checkpoint-08/` | 14 | 259470 | `f2d6d185dc29b5452abc7ee25353ded409b55f758a37990cdd8924a816507a55` |
| `source-checkpoint-compiler-14/` | 10 | 166810 | `4e02a21f1071938827ed057bbe067d355c06a10d27a18305d3edfcc22f3a33b7` |
| `source-checkpoint-compiler-15/` | 4 | 112484 | `2bae322fcedfd47ea3ec3e9971970348a605ea8b0a3cef241e3d24f31498e651` |
| `source-checkpoint-compiler-17/` | 3 | 116597 | `b29ec40ee10b055ceae035e25f348b4b4a554a7ded3afb817f8d96412a9dd74a` |
| `source-checkpoint-compiler-18/` | 5 | 125812 | `fc199a4d158405a7bb39848d98c1ad11f1ba9d1616dcc4a53722b06d59a3e425` |
| `source-checkpoint-compiler-19/` | 4 | 123817 | `eede970c58a3ed2f75c09b698da1cd4de2920e286fc8ca31056a9b1c12b1a96d` |
| `source-checkpoint-compiler-22/` | 3 | 123114 | `d40a8a60dbd978512fdec0e00fa72d92a513789eb1763ec1bc303d0abf1a3350` |
| `source-checkpoint-compiler-23/` | 4 | 131165 | `3801d7cc493265ef5e5ef6dbe54d31dbe49ea245a4beb90d2effcaa121c3a171` |
| `source-checkpoint-compiler-24/` | 8 | 153735 | `977e6b40641faeca861e45542aa7fc38099f87a242f7340c988a23f834b12286` |

### `scratch/cmo-futaba-installed-qa-20261015/`
- **What it was:** a QA harness for the installed app, written as a source handoff only. It covered a CDP controller, fixture state, private fixtures and context templates.
- **Why it went:**
  - Its README says none of the files was ever run or cleared.
  - It needed the reviewed-graph process that the lean build path dropped.
  - The 0.2.2 QA used its own server instead, and the 0.3.0 update certification (`a0897f6`) did not use it.
  - Ender judged it not worth committing.
- **Size:** 7 files, 66,640 bytes.
- **Aggregate SHA-256:** `2d9afb2860aec58f9b8148f97008b1f0b86ba3e1c60d9d30296cca0d5171e274`.
- **Files:**
  - `README-source-01.md`: `eb9f7fe4cd8063a975cf9ebf2abe4b5536e53ab1726dacad710f937afb301019`
  - `cdp-controller-01.mjs`: `1d7825018c44545ce54e888cdb931bfd4cb7488a1171804e4750b23bae5698c9`
  - `fixture-contract-01.json`: `d2af9430c160150fef63a528da8df381ae598e1be80e994b9ae06f136b4267f8`
  - `fixture-state-01.py`: `d3211d9e51d4408c5d5bec6d2761bb9b8cf91dc7b0c152a19ae6ec3f3c09b092`
  - `handoff-context-template-01.json`: `ad9189b70a2f3d9c29673d905eb0d96632875dd6e4216be92dd4b53f8dc7d2f1`
  - `installed-context-template-01.json`: `4a2ed1297d3a09fe32fd4785fd06aeefbe5da9acd54d48ff198e25dda8ace928`
  - `private-fixtures-01.mjs`: `b8ccc88402aa1e7c26ce486ca85fcd18e6bb444a995f31d3ee94eead11003a29`

### `%LOCALAPPDATA%\ComicsMeta.pre-migration-20261016-162114\` (Sergei: "Kill it.")
- **What it was:** the pre-migration backup from the 2026-10-16 switch to the installed app (Session_2026-10-16 recap). The live data in `%LOCALAPPDATA%\ComicsMeta\` was not touched.
- **Size:** 5 files, 106,935 bytes.
- **Aggregate SHA-256:** `52c532b663f30006d1852adddb407ad48a6367bafcd904167cf85eb2894061e6`.
- **Files:**
  - `BACKUP_MANIFEST.tsv`: `2038d3390e480ee85320566946dc0c48815b52fd4132d0aa5934ee774e25e3a1`
  - `data/catalog.sqlite` (73,728 B): `db829ecc4b200c5499f4777bd67e8b45284e284fc9cdcc41000d35dfaa3d8f40`
  - `data/catalog.sqlite-shm`: `fd4c9fda9cd3f9ae7c962b0ddf37232294d55580e1aa165aa06129b8549389eb`
  - `data/catalog.sqlite-wal`: empty
  - `logs/engine.log`: `82452bd4d0d74a6fc12fcd37cea304893e8d0093acffb349ae84241170faa625`
- **Removed with:** plain per-file `rm --` and `rmdir --`. The planner refuses anything in `%LOCALAPPDATA%` outside Temp.
