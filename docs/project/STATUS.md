# Current status — expert-action execution

Updated: 2026-11-04 JST. Owner: coordinating Codex.

**The active thread goal resumes the seven expert-audit tasks with Orca workers.**
The first three independent lanes are safe test isolation, provisional content
coverage and reproducible native source/build preparation. They start with
isolated source work. Runtime execution remains serial under Root, after fresh
ownership/resource bindings and backup/restore checks. The installed game and
existing saves have not been changed by this activation checkpoint.

See [audit findings](reviews/2026-10-29-T00.005.md),
[the seven tasks](NEXT_ACTIONS.md) and the
[current execution record](reviews/2026-11-04-execution.md).
Feature-branch checkpoints/publication remain authorized; `origin/main` stays
unchanged. No additional local-main merge is part of this execution checkpoint.

Three of seven audit tasks are now `self_verified` and integrated:
[T00.006 safe verification](reviews/2026-11-04-T00.006-root.md) and
[T06.005.001 provisional ledger](reviews/2026-11-04-T06.005.001-root.md), and
[T10.010.003 native preparation/recipe](reviews/2026-11-04-T10.010.003-root.md).
Root checks the pairs, selects and rechecks integrated implementations. Fresh
native preparation reproduces all nine pins; 20 preparation/45 recipe tests
and the 133-case/9-mutant host check pass. All 82 functional gaps remain open.
All six original supplier terminals are released. No real compiler container
has started. The real private constructor suite remains 48/56 due to stale
historical admission; its safe runner reports failure without canonical changes.
The [release-gate source phase](tasks/T10.010.005.md) has submitted both equal
Claude/Grok candidates from `51f927a2`, independently of actual native execution.
Its real admission must refuse until missing runtime/text facts are qualified.
Root runs the first repaired candidates' 77/55 synthetic tests successfully.
[New independent controls](reviews/2026-11-04-T10.010.005-root.md#second-root-check-of-repaired-candidates)
still expose stale folder inventories and uncaught deep JSON. Both need the
[same second repair](tasks/T10.010.005-repair-2.md), including a concrete offline
withdrawal replacement procedure. Neither is selected/integrated. Root owns
serial runtime work; suppliers own isolated source repairs.
The [current .004 ownership correction](reviews/2026-11-04-T10.010.004-root.md#ownership-correction-before-further-admission)
finds four concurrent worlds. The completed resource probe and 1.27 GiB
headroom refusal apply to the default instance. The later
[target-bound personal probe](reviews/2026-11-04-T10.010.004-root.md#actual-personal-probe-and-save-preservation)
passes: 7.75 GiB total but only 1.20 GiB available. All five service projections
and four complete save-table outputs remain identical; three characters stay
offline. Attributed stats confirm the balloon holds 5847 MiB of an 8192 MiB
ceiling. The first separate 4 GiB VM boots, but a truncated macOS process
column causes identity refusal before import; Root resolves its exact owner
and gracefully stops it, preserving all personal service projections.
[The corrected new-target admission](tasks/T10.010.004-build-vm-probe-2.md)
uses full command/birth plus loaded-image descriptors and four focused controls.
The new target is absent; mandatory shutdown and balloon opt-out remain.
The unchanged 1536+768 MiB gate must pass actual readback
before resolve. No personal RAM adjustment/restart, compiler/package install
or progress write has occurred.

Pre-merge maintenance: lint/CI checkpoint `86e98d9` is verified. At the user's
subsequent request, the retired Godot/Character Lab source is preserved under
tag `archive/legacy-prototypes-2026-10-25` and removed from the active tree.
See [archive verification and recovery](reviews/2026-10-25-T00.003.md). The
Renewal implementation and unfinished game gates remain unchanged.

## Goal and current boundary

The goal remains the full Modern/Renewal game on this Mac: maps, monsters,
ordinary story/quests, persistent personal progress and eventual Traditional
Chinese throughout. Functionality comes first. Party-only activities and
solo adaptations remain a later phase. See [Goal](GOAL.md).

The local browser game is playable in tested scenarios. Complete world/story
coverage is unverified. The ledger remains **4/14 parent checkpoints qualified**
(one accepted, three ready for user review), with **82 resource gaps open**.
This is not a percentage of playable content, effort or translation.

## Unfinished work, in priority order

1. **Actual binary experiment.** T00.006, T06.005.001 and T10.010.003 are
   integrated within their documented limits. T10.010.004's tiny resource probe
   passed on both the default and correctly bound personal instance. Admit a
   fresh build-only VM, verify actual headroom/ABI and resolve dependencies
   before admitting a bounded actual build. Current personal recovery proof
   remains required before later existing-state mutations. Full content stays open.
   No broad discovery or stock
   `checkweight` substitution. These address confirmed verification/release
   gaps without changing the goal.
2. **Native build for the 0.3.2 story extension.** Qualify the bounded
   Linux/arm64 toolchain, exact dependencies/ABI, resource and deadline controls,
   cancellation/cleanup and binary export. Compile the exact prepared source.
   The project has not installed the compiler or built a custom image; fresh
   toolchain qualification is pending. The new builtin is unavailable in stock
   binaries.
   Personal ro4's fresh limit readbacks pass, but balloon-held memory leaves
   insufficient available RAM. The selected new build VM must pass the same
   limit/readback and reserve gates; no compiler is admitted yet.
   See [the current ownership correction](reviews/2026-11-04-T10.010.004-root.md#ownership-correction-before-further-admission).
3. **Native and normal story integration.** First qualify ordinary-item
   behavior because the patch touches general insertion. Check script parsing, four actors,
   state transitions, capacity/refusal cases, actual rewards, repeats, saves
   and withdrawal in isolation. Then supported installation/full Apply and
   normal journal/travel/progression checks. Source tests and isolated earlier
   scenes do not close these normal-game gates.
4. **Full world/content coverage.** Finish effective maps/spawns/monsters,
   items/skills, NPCs, quest chains, instances, dynamic resources and the 82-gap
   reconciliation. Declare the coherent version/content boundary and estimate
   remaining work from it. Do not silently narrow the full-game goal.
5. **Remaining Chinese and input coverage.** Keep current overlays enabled;
   finish the unresolved UI, NPC/story/system text and real macOS IME checks
   after functional work.
6. **Final qualification and handoff.** Complete required coverage, offline,
   performance and recovery checks, rehearse the user runbook and obtain
   explicit milestone acceptance. Keep the Mac's internet connected.

The [unfinished task board](TASKS.md) holds the remaining IDs, dependencies and
next actions. The [ASCII map](PROJECT_MAP.md) shows the execution order.

## Historical last runtime baseline — refresh before runtime work

- The user finished the personal playtest. Its tab is absent; all three
  characters are offline. Assassin's latest position and all complete
  character/quest/inventory/skill outputs are saved.
- The fresh 13.57 MB whole-world backup passes supported inspection and Root's
  exact 22-file manifest check. Backup and the later VM restart preserve all
  four complete save-table outputs. Private backups/assets/credentials stay
  outside Git.
- The supported RAM setting is persisted at 8192 MiB. The restarted guest
  reports 8318238720 bytes of kernel memory and four CPUs. All five new
  services retain the prior images, mounts, configuration, ports and arguments;
  the database volume and disk backing remain the same.
- The complete 0.3.2 source is integrated at `3931f8f`; its corrected capacity
  source passes 133 C++ cases and 120 NPC tests. This is source qualification,
  with native parsing/rewards/persistence still pending.
- At the pre-pause fleet check: 345 released, ten user-retained and zero
  reclaimable. No compiler worker was launched before the pause.

Evidence: [saved user state](reviews/2026-10-25-user-assassin-play.md#current-offline-saves-are-verified-after-the-test),
[source integration](reviews/2026-10-25-T10.010.md#corrected-exact-capacity-source-passes-and-the-complete-package-is-integrated),
[fresh backup](reviews/2026-10-25-T10.010.md#idle-saves-and-fresh-whole-world-backup-pass),
[8 GiB restart](reviews/2026-10-25-T10.010.md#supported-idle-ram-restart-and-save-preservation-pass).

## Current action and ownership

The three prerequisite source lanes are integrated. Root owns serial runtime
execution/verification for .004; both .005 source candidates need the frozen
second repairs before Root selection. Fresh build-only state initialization
uses the workflow's isolated-new-state allowance; it does not establish
current ro4 backup/restore qualification.
Refresh current Engine/socket/service/save bindings; old IDs, start times,
RAM assumptions and consumed probe admissions are not reusable authority.

The expert re-audit refines that next action: reproducible source preparation
and the full-binary/ordinary-item proof come before more story authoring.
Safe test isolation and provisional coverage can run in parallel. The current
model's no-replay reward alert is not persistent quarantine or crash-atomic
delivery; T10.010.006 qualifies the actual native save/EXP behavior.

Keep the frozen normal 0.2.0 staging separate from source 0.3.2. Do not install
0.3.2 against stock binaries. [The existing normal-apply runbook](runbooks/T10.008-T10.009-normal-apply.md)
is the frozen **0.2.0-only** reference; its three-row acceptance/withdrawal is
unsafe for 0.3.2 D-state progress. T10.010.005 must produce a separate matching
release/apply sheet retaining all four quest definitions and all three exits.

## Records and Git

- [Completed work and historical snapshots](HISTORY.md): prior verification,
  provider comparisons, failures and original task dispositions.
- [Workflow](WORKFLOW.md): equal model comparison, Root verification,
  documentation maintenance, checkpoints and external-state rollback.
- Branch: `ShemYu/reverse-the-Ragnarok-Online-to-play-by-myself`.
  The current user request authorizes committing and pushing this feature
  branch. Keep downloaded assets, raw evidence, accounts and saves local.
- Cleanup source checkpoint `9536d59` and the legacy archive tag are pushed.
  [Hosted CI passes](https://github.com/ShemYu/ragnarok-online-study/actions/runs/40192204732)
  on that source revision; subsequent maintenance only records the result.
  [The archive review](reviews/2026-10-25-T00.003.md)
  contains checks, recovery, provider-availability limits and the remaining
  paused game boundary.
- The user authorizes the local-main merge on 2026-10-28. The reviewed source
  fast-forwards from `c6314bb` to `7e527bd`; the documentation checkpoint is
  included by the same fast-forward process. Feature publication continues,
  while `origin/main` remains at `c6314bb`. See [merge verification and rollback](reviews/2026-10-28-T00.004.md).
