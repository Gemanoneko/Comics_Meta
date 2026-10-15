# Packaging protection contract — technical proposal

**AGREED DOMAIN CONTRACT — 2026-10-15. Implementation and release remain blocked.**

This defines the Ender/Senua-agreed compatibility-preserving protection contract for the installer qualification worktree, recorded at HEAD `444bf23`, version `0.2.1`. Senua agreed the semantic content at SHA256 `7782cb044bce03db6ffa431267088225bbc9736360fe4e6fcf58953db4f5ff41`; the present label/evidence-status update is administrative. It is not an implementation, source clearance, QA verdict, native execution approval, or readiness claim. Sully must commit the agreed contract before implementation cites it. Sully exclusively owns commits, pushes, versions, releases and deployment. Product requirements remain Sergei's.

## Required protection and its limits

Retain protection against replacing, renaming or deleting protected path components while their contents are consumed. Directory handles need read-bearing access and must omit delete sharing; zero-access or attributes-only holds do not establish this protection. Protected input files retain strict read access and read sharing. Reject every reparse component encountered during acquisition, validate object type and canonical path using the acquired handle, and record its volume/file identity. A pathname check before opening is not the authoritative check.

Expected child operations must remain possible in mutable parents: creating files/subdirectories, opening intended writers, and renaming temporary outputs into place. A denied child operation is not evidence that the protected object itself resisted replacement. Qualification controls must distinguish denial caused by the object hold from denial caused by the destination parent or the attack runner's own logger.

The contract does not claim that sharing modes prevent every concurrent metadata change. Microsoft’s [sharing algorithm](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-fsa/8c0e3f4f-0729-49f4-a14d-7f7add593819) does not apply its sharing gate to `FILE_WRITE_ATTRIBUTES` alone. Its [reparse-setting algorithm](https://learn.microsoft.com/en-us/openspecs/windows_protocols/ms-fsa/4aeefef8-92c3-4abc-af7a-a610caf8a165) accepts that access, prohibits setting a reparse point on a nonempty directory, and gives separate restrictions for mountpoint and symbolic-link tags on regular files. Nonempty-file protection must not be inferred from the directory rule. Microsoft also documents [standard-user junction creation outside a sandbox](https://www.microsoft.com/en-us/msrc/blog/2025/06/redirectionguard-mitigating-unsafe-junction-traversal-in-windows).

The retained requirement is pathname replacement/sharing protection, no out-of-scope producer writes, and reparse rejection when acquiring each component. The reviewed studio rules do not separately require defense against an independent hostile same-user native actor setting arbitrary reparse metadata during consumption. That stronger attacker was introduced during this recovery analysis, rather than demonstrated as an admitted producer capability. This does not excuse a real graph writer capable of changing protected inputs: such a writer must be identified and excluded or constrained before admission. Arbitrary tags, filter behavior and later executable pathname reopening are not certified here. Acquisition-time rejection and before/after observations do not establish uninterrupted metadata immutability.

The current held-paths.py docstring's “deletion/redirection until work completes” is overbroad. This contract supersedes that wording with protection against pathname deletion/replacement through continuously held chains and acquisition-time reparse rejection. A later scoped source/doc correction must remove the blanket continuous-redirection claim after the pinned12 route and agreed-contract commit. Historical receipts remain unchanged. No claim of regular-file/all-tag immutability follows from a nonempty-directory anchor.

## Proposed directory policy

For a mutable directory, permit write sharing only after a direct child is held against deletion and remains present for the entire permitted-write interval. Retain read-bearing directory access and deny-delete sharing throughout. The direct child may be an explicitly owned anchor or an authenticated real child. Merely enumerating a nonempty directory, holding a deeper descendant without the intervening chain, or remembering an earlier nonempty observation is insufficient.

For newly owned output directories, create a uniquely named anchor and retain its handle until a real direct child is acquired and verified. Anchor retirement requires overlapping holds: acquire the real child first, then release and remove only the known owned anchor. The directory must never pass through an unprotected empty interval. If that child is a directory, apply the same invariant recursively or retain its stricter policy. Do not retire protection based on a child the build can legitimately delete or replace later.

This is a proposal requiring source design for the creation/acquisition transition. Pathname-based `mkdir`, later anchor creation, and later validation must not be described as an atomic bootstrap. The implementation must define how it detects and fails closed on interference before admitting a child producer. Unsupported transitions stop; they do not silently fall back to broad write sharing.

For immutable input trees, prefer already authenticated real children. Do not add placeholders to vendor/source inputs, silently alter authenticated manifests, or introduce generic inventory exclusions. An empty protected input directory needs an explicit assessed policy; strict sharing alone is not a universal reparse defense. Every mutable ancestor still needs a continuously held direct-child chain.

Anchors must not enter the final staged package. Before packaging consumes the stage, remove each temporary anchor only after an authenticated real child supplies the overlapping hold, then verify the complete anchor-free path/type/hash inventory. An intentionally empty staged directory cannot satisfy that handoff and must be resolved explicitly rather than hidden from inventory. Cache, log and output roots require compatibility checks against their actual consumers.

## Pinned inputs, logger and sealing

Trusted inputs comprise the pinned runtime, selected source, dependency and native-tool closure, with exact filenames, types and hashes. Verify manifests and held inputs before use and after the owned operation. Hash equality does not replace handle identity, reparse/type checks or complete inventory checks. Shared ancestors used by both immutable inputs and mutable outputs must have one explicit compatible policy; first-open caching must not accidentally select the policy.

Live stdout/stderr writers retain their original handles, omit delete sharing and capture exact native byte counts. A legitimate concurrent reader must share the existing writer's access; opening another writer, truncating evidence, or reopening by pathname to repair a mismatch is prohibited. Short writes, drain failures, output overflow and incomplete stream closure must fail closed with the appropriate bounded result and native root/descendant closure evidence. Held-stream bytes are authoritative; a stable FileID alone does not certify unchanged reparse metadata.

After producer and descendant termination and completed stream drains, convert live evidence to the stronger sealing phase. The conversion must acquire and verify the intended read-only evidence objects without releasing their pathname/ancestor protection during a gap. Compare held bytes, identities, types, reparse state and the declared inventory; preserve failure evidence. Any unavailable stronger hold, unexplained extra member, mismatch or unknown process/stream closure blocks sealing and further work.

## Consumers and bootstrap boundaries

The source assessment must cover each producer and consumer of these invariants:

| Component | Required assessment |
| --- | --- |
| `scripts/packaging/held-paths.py` | `hold`, `_open`, `mkdir`, `tree`; explicit immutable/mutable policies, ancestor chains, anchor ownership and handoff. |
| `scripts/packaging/owned-job.py` | `LockedFiles`, log-parent/log-directory creation, live writer/reader compatibility, exact writes/drains, process closure and sealing handoff. |
| `scripts/packaging/build-owned.py` | Owned root/snapshot/stage/cache/dist creation, copy sequence, complete input inventories, anchor-free staging and post-build closure. |
| `scripts/packaging/publish-held.py` | Evidence-root creation, nested command logs, artifact holds and publication receipts; publication remains Sully's responsibility. |
| `scripts/packaging/verify-staged.cjs` | Exact staged/Python path/type/hash inventory and manifest interpretation; no implicit anchor exception. |
| `desktop/installer_launch.py` | `Windows.hold`, `hold_capsule`, payload ancestors, immutable files and lifetime through the exact installer process. |
| `desktop/update-capsule.cjs` | Preparation, directory/file creation, exact runtime/capsule inventory and module paths before helper launch. |

Include the `build-entry.cjs`, `installer-launch.cjs` and `updates.cjs` handoffs wherever their assumptions or request/manifest formats change. Report literal contract consumers when implementing a format change.

Stock supervisor startup, imported guard source, copied interpreter/helper startup, capsule preparation and later executable pathname opens are distinct bootstrap boundaries. State which inputs are trusted before holds begin and which process owns each interval. A helper that acquires handles after interpreter startup cannot retroactively protect that startup or earlier capsule copying. Do not replace a disclosed trusted bootstrap with an unsupported cold-start safety claim.

### Producer capability and admission phases

This is the intended admitted graph contract; the absent packaging graph still needs reconstruction and exact review. Merely naming a producer here does not qualify its implementation.

| Producer / owner phase | Permitted writes and trust boundary | Admission condition |
| --- | --- | --- |
| Stock pinned Python/Node supervisor bootstrap | Trusted interpreter and standard initialization before holds; creates only fresh owned evidence/guard state. This initial trust is disclosed. | Authenticate copied guard bytes before loading them; complete runtime/source membership, type, hash and held-identity checks before admitting downstream code. |
| build-owned / build-entry supervisor | Creates owned snapshot, stage, cache, dist and logs; copies declared inputs. Cannot modify original source/runtime or arbitrary external paths. | Exact graph enumerates every path/writer; create each mutable directory under an already protected parent, acquire strict directory handle, validate type/canonical identity, create and hold direct anchor, revalidate identity/reparse state, then permit child operations. Any interference before admission stops. |
| Pinned electron-builder / native compiler and archive tools | Trusted pinned implementations with declared create/write/rename capabilities only in admitted output/cache trees; no authorized FILE_WRITE_ATTRIBUTES/reparse mutation of protected objects. Normal API capability is not OS sandbox enforcement. | Exact executable/dependency closure and command/options/environment reviewed; native Job owns all descendants; immutable inputs held and mutable chains anchored before launch; output inventories checked afterwards. A tool needing undeclared metadata mutation is a blocker, not an implicit exception. |
| Capsule preparation / update-capsule owner | Creates only its fresh owned capsule and copies declared payload/runtime; excludes live library, credentials and unrelated application state. | Authenticate copied closure, hold and verify all components before helper admission; no input placeholders or inventory exemptions; explicit bootstrap-copy trust boundary. |
| installer-launch / Windows helper | Holds authenticated capsule and launches only its reviewed exact installer; intended installed-program/state writes are separately qualified in isolated QA. | Capsule handle/type/reparse/inventory checks and exact installer identity before launch; native lifetime evidence and explicit installed/update QA scope. This contract does not pretend the installer is a read-only build child. |
| Logger and evidence sealer | Only declared CREATE_NEW live logs and protocol files; convert completed bytes to strong no-write holds. | Native writes/drains bounded, writer closure and held-byte/ID checks, overlapping strong-reader handoff; fail closed on another writer or mismatch. |

Creation precedes anchor acquisition, which precedes producer admission. The initial creation window is a disclosed owned-bootstrap interval, not atomic filesystem isolation. Before granting child-operation-compatible sharing, recheck the same acquired directory and direct child's identities/type/reparse state under retained handles; refuse unexpected members or changed canonical paths. No untrusted producer runs in that interval. These checks detect interference at the admission boundary; they do not promise prevention of every hostile concurrent same-user metadata operation. Downstream producers are trusted pinned code restricted by this explicit authorized-write contract, not adversarial executable payloads. If source review finds arbitrary native mutation, dynamic unpinned imports or out-of-root writes in an admitted path, this contract is unsatisfied until that concrete capability is removed or separately contained.

## Current evidence and proposed qualification

The parent’s current frozen11 graph reports **8,097 total file entries**, covering stock runtime, Node and source/helper/qualifier inputs; these are not all runtime files. Its runtime directory array has **350 entries**. The inventory walk omits the `site-packages` subtree entirely from files and directories; the chosen graph uses isolated Python with site initialization disabled (`-I -S`). That omitted subtree is outside this inventory claim.

The parent’s read-only comparison found no declared empty directories: each directory has a declared child entry. Method: compare directory entries against file paths and declared descendant directories in those arrays. This drafting task ran no new filesystem scan. The result supports investigating held real-child anchors for this frozen input; it does not prove that direct child handles are acquired before sharing conversion. Historical packaged runtime evidence is unavailable, so this observation cannot certify older installers or future runtimes.

Actual junction fixture creation succeeded in qualification routes 09 and 10; those overall runs failed. Route12 then completed its sole bounded invocation with exit0 and qualification PASS, including the fixture, faults, owner-death and sealed handoffs; independent Senua actual audit remains pending at this update. That result does not qualify the proposed mutable-directory implementation, a generic runtime reparse immutability claim, packaging or installation/update readiness.

Before any further native execution, review the proposed source graph and tests. Proposed cases must distinguish object replacement from parent-side child operations; include independent same-operation controls without attack-runner parent interference; exercise each ancestor/leaf and live logger; cover reparse rejection, anchor deletion attempts and overlapping retirement; confirm exact inventories and bootstrap assumptions; and exercise short-write/drain/overflow/deadline/lease failures with owned root/descendant and stream closure evidence. Attributes-only metadata attacks require an explicitly scoped result, including unresolved regular-file/tag behavior, rather than an all-tag claim.

Only a reviewed, pinned and explicitly cleared qualification route may then run. Successful protection/logger qualification must precede packaging and rendered QA. Actual installation and prior-to-next update/state-preservation tests, Futaba's QA and Senua's source re-review remain outstanding release gates. The live application remains outside this work.
