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

## Current action — managed client, then ordinary items

**Actual process and generated-mount startup readbacks pass Root verification.**
After admission43dba540 is committed/pushed, initialized restart85017 exits0:
supported up0/11.944s, five exact-image services and1265 registered maps. Complete
API capture proves map executable/cwd, UID/GID1000 and both binary hashes;
all17 generated conf/NPC/Kafra files are read with matching bytes as the game
user. Exact existing volume/network/images are retained. Five ordered TERM/
exited0 checks precede down0/0.864s; the VM is stopped. See
[Root's qualified result](reviews/2026-11-04-T10.010.004-root.md#initialized-process-and-mounts-personally-qualified).

Root independently replays nine resource files, service projection/three
negative controls, both strict raw API captures/terminal execs and shutdown
request/log joins. All1978 protected inputs and88 terminal files remain unchanged.
The1107-file world has no additions/deletions;18 admitted generated files change
stat only, with all content unchanged. Fresh current stopped/personal checks
pass. Registration and reads do not qualify saved DB content or full-world
functionality. Four map/one character startup errors remain to classify;
all-NPC/parser acceptance, rendering, items, probe purity and saves stay open.

**Next:** commit this checkpoint, then complete/admit the managed-client
controller. Source/Node preparation passes: exact helper loads on pinned Node
v24.20.0 without Electron/npm. Actual managed identity/readiness, allowed writes,
cache/log bounds, static routing and owned stop still require verification.
Start with the bounded host-only protocol/static check while the VM remains
off, then integrate the owned client with the same disposable game for rendering
and ordinary-item A/B. Do not infer gameplay from HTTP health. Preserve Chinese
inputs, existing DB/network,4GiB/CPU2 limits and all personal state; internet stays
connected. See [client preparation](reviews/2026-11-04-T10.010.004-root.md#managed-client-source-plan-and-node-import).

Completed prerequisites stay in dated evidence:

- [Full artifacts](reviews/2026-11-04-T10.010.004-root.md#compiler6-full-artifacts-personally-qualified),
  [images/original loaders](reviews/2026-11-04-T10.010.004-root.md#image-pair-and-original-loaders-personally-qualified),
  [host assets/Chinese bytes](reviews/2026-11-04-T10.010.004-root.md#ordinary-host-assets-linked-and-personally-read-back)
  and [four diagnostic bind/user reads](reviews/2026-11-04-T10.010.004-root.md#read-only-user-mount-diagnostic-personally-qualified)
  pass their scoped Root checks. None proves gameplay/persistence.
- [Ordinary fixtures](reviews/2026-11-04-T10.010.004-root.md#ordinary-fixture-comparison-closed-claude-selected)
  are source-selected/integrated; actual parsing/200-row capture, effective items,
  ordinary A/B, capacity-probe purity and saves remain open. Settled suppliers
  are released; branches retained.
- Earlier OOM/report/DB-cwd refusals and incomplete CLI output are preserved.
  The bounded Engine capture restores the missing readbacks without relaxing
  assertions. No verified finding requires changing the goal.

## Four audit tasks remain open

- **T10.010.004 — full binaries and ordinary items.** Both full artifacts and
  their exact dependency closure, immutable images and original-library loaders
  pass Root's fresh offline replay. Process/generated-mount readbacks are also
  qualified. Admit the managed client, then verify ordinary stack/new-slot,
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
