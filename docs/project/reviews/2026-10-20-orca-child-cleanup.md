# Orca child cleanup and recovery checkpoint

2026-10-20. Root. **Completed:35 inactive children removed;22 retained.**
The user explicitly authorized removal of unused children and parallel work.
This housekeeping does not complete another game-content checkpoint.

## Selection and independent recovery verification

The repository had59 worktrees: this coordinator, the unrelated main checkout
and57 direct children. Exactly35 clean, completed/succeeded, released/exited,
terminal-free children qualified for preservation. The other22 remain: the two
current .008 review trees, two older user-retained workers and18 trees with
connected or uncertain terminal ownership. No unknown terminal was closed.

Internal preservation copies all3770 regular ignored files/2172340382 bytes
and three symlink strings into explicit leaf-only tar archives, then rehearses
recovery. Root personally reviews the helpers and retry diff, then independently
full-hashes all35 archives, every logical payload, every original source and
every completed restored regular file. Exact member order/set/type/size, source
identities, link strings/modes, restored directory/leaf sets and clean Git/
ignored-file sets match. No symlink target is followed.

The initial helper incorrectly assumed symlink mode0777; two rows failed and
were retained. Fresh retries apply the observed source modes with no-follow
lchmod and pass. The completed index uses33 original positives and two retry
positives. Initial failures, partial outputs and executed helpers remain intact.

Recovery scope is file bytes and links. Restored regular files are private0600;
1731 originally0644 files retain their original modes in manifests. Empty
directories, ACLs and extended attributes are outside this leaf-only archive
scope. All three links use absolute original-child paths; functional recovery
requires the exact preserved Git checkout at that original path, followed by
the recorded ignored leaves. A relocated restore alone does not resolve them.

## Git protection and removal

Before the first removal, root creates35 independently verified safety refs
under refs/ro-preserved/20261020-1/ and a portable Git bundle containing all35
exact commit refs and their reachable history. git bundle verify and list-heads
match. Every original branch remains at its exact original SHA after cleanup.

Each removal freshly checks authoritative worker identity/released/exited
state, an empty untruncated terminal list, original HEAD/branch, clean tracked
state, no untracked files, exact ignored leaf set and unchanged source
identities. A separate process-cwd census finds no selected worktree in use.
Root invokes only orca worktree rm for those exact IDs, with no archive hooks.

The first command returns removed=true/removing=true before filesystem removal
finishes. Root's immediate absence assertion fails; no duplicate removal is
sent. Fresh Git/filesystem/Orca observations prove it settled, and a separate
resume helper continues the remaining34 while observing asynchronous removal.
Both helper versions and the failed assertion remain preserved.

Final authoritative Orca and Git state has24 worktrees: the same coordinator,
same unrelated main checkout and exactly the22 protected children. All35 removed
paths are absent. All35 original branches and safety refs resolve correctly.
Coordinator branch/HEAD8ea9a5933b70689b5f97c6bccb6255f7fb97b022 and clean working
tree remain unchanged at the cleanup boundary. Game, saves, network and
preferences were not accessed or changed.

## Private evidence and recovery

All receipts, archives and rehearsed restores remain under ignored
.tools/renewal/orca-child-archives-20261020-1,0700 directory/0600 regular files.

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| completion.json |41784|a27f214a39ee22821ea7249c620b7c79110bb36378687f06729a72a67bcf8464|
| root-independent-verification.json |11450|b102cc9ada1c6b294c579371325414f1d0f48ba3f07b810f1694ec704e4ae997|
| root-cleanup-completion.json |16651|a839e58a2bdd84fa513a5251e3bca48ec5c6e3eb4bcb2aef7c98b9dd2e16b8ed|
| preserved-commits.bundle |2849701|4c2c622818cc3be149ccb5b1eb79ba04c26b529e0ba3eab2663d90c10102318f|

For recovery, use the exact original path/branch/HEAD from the completed index
and safety refs or bundle, then validate and restore only that row's archived
relative leaves without following links. Reapply recorded original regular
modes only as a separately inspected recovery step. Git alone does not restore
ignored evidence. No game/database restore occurred. The requested full
Modern/Renewal milestone remains active.
