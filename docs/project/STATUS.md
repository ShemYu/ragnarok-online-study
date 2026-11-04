# Current status — expert-action execution

Updated: 2026-11-05 JST. Owner: coordinating Codex.

**Seven-task execution is active. Root owns serial runtime verification.**
The goal remains the full Modern/Renewal game on this Mac: maps, monsters,
ordinary story/quests, persistent progress and Traditional Chinese throughout.
Functionality comes first; keep existing Chinese overlays enabled. Party-only
activities and solo adaptations remain later-phase work. The exact episode
and complete world/story coverage are unverified. See [Goal](GOAL.md).

**Only 3/7 audit tasks are `self_verified` and integrated:**

- [T00.006 safe verification](reviews/2026-11-04-T00.006-root.md).
- [T06.005.001 provisional coverage ledger](reviews/2026-11-04-T06.005.001-root.md).
- [T10.010.003 native source preparation/build recipe](reviews/2026-11-04-T10.010.003-root.md).

These scoped source/tooling completions do not close the four runtime audit
tasks below. The [task board](TASKS.md) has **41 unfinished rows**. The parent
ledger remains **4/14 checkpoints qualified**: one accepted and three ready
for user review, with **82 resource gaps open**. These are separate ledgers,
not percentages of playable content, translation or remaining effort.

## Current action — isolated startup and ordinary items

**Both full server artifacts now pass Root's offline qualification.** After
admission9f8c2bed is committed/pushed, compiler6 exits0/no timeout in844.4s.
The corrected interpreter capture passes the unchanged validator. Both ELF
hashes equal the earlier compiled pair; only the report capture changed.
Root independently reproduces105 saved artifact files and nine resource files,
checks exact47/base26, raw memory/cgroup evidence, native ELF interpreter,
nonempty matching loader/dependency reports, owners/modes and capability markers.
All342 protected source/evidence files remain unchanged. Both owned containers
are deleted/404, VM shutdown exits0, current stopped ownership passes and
personal five-service projections remain byte-identical. See
[actual qualification](reviews/2026-11-04-T10.010.004-root.md#compiler6-full-artifacts-personally-qualified).

**Both immutable images and original-library loaders now pass Root verification.**
After admission1f79acf4 is committed/pushed, the one image run exits0. Both
images contain the exact qualified binary at the supported /rathena/map-server
path, retain base Config/layer inheritance and resolve all five required
libraries against the unchanged original26 packages. Root's fresh offline
replay reproduces nine resource and14 files per loader; all93 terminal evidence
files are pinned and558 protected files remain unchanged. Five owned containers
are deleted/404, the VM is stopped and personal projections remain identical.
Whole-layer entry inspection and actual server/parser/game/SQL/probe-purity/save
results remain unqualified. See
[image qualification](reviews/2026-11-04-T10.010.004-root.md#image-pair-and-original-loaders-personally-qualified).

**Next:** admit supported startup in the disposable world using its own state
and the owned Engine. Fresh host state alone does not isolate an Engine's fixed
container names or DB volume. Verify their absence, images, mounts, six ports,
exact environment and graceful shutdown before initialization. Keep the4GiB/
CPU2 ceiling; actual game fit is unproved. Require positive map registration
and actual process/image/binary identity, then managed client and ordinary-item
A/B checks. A successful up/Ready label alone cannot qualify startup.

Host assembly is also verified in fresh owned state, after source/input
checkpoint57ae52be is committed/pushed: supported link-assets exits0/2.004s,
all1265 protected inputs retain content/stat and Root rehashes59 generated
files/66650497bytes. Selected itemInfo merge-layer, six navigation tables,
four plaintext-plugin files and moved Taiwan/Renewal configuration match.
No asset server/browser or DB/game starts; detection/endpoints remain absent.
The source-supported managed RemoteClient route still needs actual protocol,
owned-lifecycle and rendering checks. See
[host result](reviews/2026-11-04-T10.010.004-root.md#ordinary-host-assets-linked-and-personally-read-back).

The [ordinary fixtures](tasks/T10.010.004-ordinary-fixtures.md) are source-selected
and integrated. Both suppliers pass Root's isolated source/budget checks; Claude
fbf1fcc6 is retained for simpler controls and guard margin. Both worker terminals
are released, branches preserved. Actual parser/200-row completion, effective
items, ordinary A/B behavior, probe purity and persistence stay open. See
[fixture selection](reviews/2026-11-04-T10.010.004-root.md#ordinary-fixture-comparison-closed-claude-selected).

Earlier1536MiB OOM, refused compiler5 and the first qualifier's metadata-reader
refusal remain preserved. The corrected bounded8MiB reader replay passes;
no original run or evidence is overwritten. Source/game functionality has not
been reduced and no verified finding forces a goal change.

## Four audit tasks remain open

- **T10.010.004 — full binaries and ordinary items.** Both full artifacts and
  their exact dependency closure, immutable images and original-library loaders
  pass Root's fresh offline replay. Admit supported isolated service/client
  startup, then verify ordinary stack/new-slot,
  weight/full-bag, equipment/rental/GUID and save/re-entry behavior. The capacity
  probe must remain read-only. Use the [ordinary-item runbook](runbooks/T10.010.004-ordinary-item-verification.md)
  and [image source readiness](reviews/2026-11-04-T10.010.004-image-source.md).
- **T10.010.005 — coherent release and withdrawal.** Gate/manifests/runbooks
  are source-integrated as `efa9af82`; actual runtime pins remain unqualified.
  Bind .004/.006/isolated .007 evidence, then rehearse installation, full Apply,
  save/restart, journal/play and withdrawal. Preserve all four quest definitions
  and three exits. See [selected source and remaining gate](reviews/2026-11-04-T10.010.005-root.md#selected-source-and-integrated-verification).
- **T10.010.006 — real rewards and persistence.** Analysis/runbook are
  source-integrated as `a75eeb2e`; actual EXP, level-up, callback, reward,
  save/re-entry/restart and repeat behavior remain unqualified. C4 stays
  skipped/not captured without a qualified observation method; durable
  quarantine and crash atomicity are unproved. See [selected analysis](reviews/2026-11-04-T10.010.006-root.md#corrected-source-analysis-selected-and-integrated).
- **T10.010.007 — native story to normal play.** After .004–.006, verify the
  real parser/OnInit, four actors, quest states, capacity/refusal/retry, rewards,
  persistence and withdrawal in isolation, then supported normal installation,
  full Apply and ordinary journal/travel/progression with progress preserved.
  See [the frozen seven-task contracts](NEXT_ACTIONS.md#seven-bounded-tasks).

Keep frozen normal **0.2.0 staging** separate from **0.3.2 source**. Do not
install 0.3.2 against stock binaries or substitute stock `checkweight` for its
native capability. The [old normal-apply runbook](runbooks/T10.008-T10.009-normal-apply.md)
is 0.2.0-only; its three-row withdrawal is unsafe for 0.3.2 D-state progress.
Source tests and earlier isolated scenes do not close these runtime gates.

## Other unfinished milestone work

1. **Full-world coverage:** reconcile effective maps/spawns/monsters,
   items/skills, NPCs, quest chains, instances and dynamic resources; resolve
   the 82 gaps and declare a coherent version/content boundary and estimate.
   Basic local play is available in tested scenarios, not full-game proof.
2. **Chinese/input:** after functionality, finish remaining UI, NPC/story,
   system text and real macOS IME checks using existing resources first.
3. **Final qualification:** complete required coverage, offline/performance
   and recovery checks, rehearse the user guide and obtain explicit acceptance.
   T11 party-only adaptations do not block milestone 1.

Use [Tasks](TASKS.md) for IDs/dependencies, [Project map](PROJECT_MAP.md) for
the remaining flow and [Next actions](NEXT_ACTIONS.md) for audit acceptance.

## Ownership, preservation and Git

- Four game worlds were identified; the save-free build VM is separate.
  Their bindings are not interchangeable. Refresh the exact intended world,
  Engine/socket/service/save bindings and resource evidence before runtime.
  Root retains serial runtime ownership; source work can proceed independently.
- Before changing existing personal state, make a named current backup and
  prove restoration on isolated state under [Workflow](WORKFLOW.md#rollback).
  Fresh build-only initialization uses the isolated-new-state allowance;
  it does not qualify personal backup/restore or authorize personal RAM/restart.
- [Oct25 saves, backup inspection and RAM projections](reviews/2026-10-25-T10.010.md#idle-saves-and-fresh-whole-world-backup-pass)
  are historical evidence, not current ownership or restored-backup proof.
  Old IDs, start times, memory snapshots and admissions are not authority.
- Keep the Mac's internet connected. Keep assets, installers, raw evidence,
  backups, credentials and saves private; publish source and redacted evidence.
- Commit/push only the coordination feature branch,
  `ShemYu/reverse-the-Ragnarok-Online-to-play-by-myself`; `origin/main` remains
  unchanged at `c6314bbd`. No new local-main merge or history/rule changes are
  authorized. Record verified checkpoints before advancing; Git cannot restore
  external game state.

[History](HISTORY.md) and the [dated execution record](reviews/2026-11-04-execution.md)
retain completed results, comparisons and failed attempts. This STATUS is the
authority for execution state and next action; dated evidence retains its
original scope. Archiving `ready_for_user` work does not accept it.
