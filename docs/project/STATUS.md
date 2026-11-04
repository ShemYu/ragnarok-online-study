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
Normal feature publication recovers after a GitHub server-error retry:
selected source/checkpoint47bfe3d is pushed, with origin/main unchanged.
[Hosted source CI](https://github.com/ShemYu/ragnarok-online-study/actions/runs/41816752719)
passes on107e352, including the explicit release-gate step; later HEAD CI
is not yet checked. No rules/config/force changes are made.

Three of seven audit tasks are now `self_verified` and integrated:
[T00.006 safe verification](reviews/2026-11-04-T00.006-root.md) and
[T06.005.001 provisional ledger](reviews/2026-11-04-T06.005.001-root.md), and
[T10.010.003 native preparation/recipe](reviews/2026-11-04-T10.010.003-root.md).
Root checks the pairs, selects and rechecks integrated implementations. Fresh
native preparation reproduces all nine pins; 20 preparation/45 recipe tests
and the 133-case/9-mutant host check pass. All 82 functional gaps remain open.
All six original supplier terminals are released. No full map-server build
has started. The real private constructor suite remains 48/56 due to stale
historical admission; its safe runner reports failure without canonical changes.
The [release-gate source phase](tasks/T10.010.005.md) is now integrated from
Claude candidate `b9038ee6` as `efa9af82` after Root compares both repaired
candidates. Its common release/withdrawal reader and inventory machinery
provide the simpler maintenance boundary. Root's integrated113 synthetic
tests and real-mode refusals pass, with all644 tracked files unchanged.
Runtime pins remain null; actual .005 release qualification is still open.
The synthetic gate checks are added to the explicit public CI list; no
installed-game action is performed. See [Root selection](reviews/2026-11-04-T10.010.005-root.md).
The [current .004 ownership correction](reviews/2026-11-04-T10.010.004-root.md#ownership-correction-before-further-admission)
finds four concurrent worlds. The completed resource probe and 1.27 GiB
headroom refusal apply to the default instance. The later
[target-bound personal probe](reviews/2026-11-04-T10.010.004-root.md#actual-personal-probe-and-save-preservation)
passes: 7.75 GiB total but only 1.20 GiB available. All five service projections
and four complete save-table outputs remain identical; three characters stay
offline. Attributed stats confirm the balloon holds 5847 MiB of an 8192 MiB
ceiling. The [actual separate 4 GiB build VM characterization](reviews/2026-11-04-T10.010.004-root.md#actual-build-only-vm-characterization-passes)
now passes after correcting macOS process-column truncation: local image
import, identity, own cgroup/limit readbacks,3.61 GiB available RAM and owned
cleanup all pass. The unchanged1536+768 MiB gate is met. The VM is gracefully
stopped, its probe deleted, and five personal service projections are identical.
[The actual dependency attempt](reviews/2026-11-04-T10.010.004-root.md#actual-dependency-failure-and-next-diagnostic)
then fails: the repository upgrades four frozen base packages and APK's trigger
launcher exits127. Both owned containers are deleted and VM shutdown passes;
no lock or full build is qualified. Astra/primary-source review identifies
separate package-drift and closed-stdin leads. Matching APK candidates are
now authenticated by the actual stock-key verifier. After removing a config
file confound, the real closed/null control reproduces fchdir/child127 only
with closed stdin; /dev/null completes the real reinstall and trigger. All26
versions, personal service projections and owned cleanup pass. Next: the
[equal dependency-recipe repair](tasks/T10.010.004-dependency-repair.md), then
exact-base resolution with retained signed package bytes before a full build.
Claude/Grok source-only repairs are now dispatched from the same30439b1 base;
both report ready. Root retains serial runtime ownership and the VM is stopped.
The corrected dependency recipe is now selected/integrated from Claude
ada8cd77 as f1a3ee80. Root's76 tests (including all four retained APKs) pass,
all638 tracked files stay unchanged, and both independent coherent-export
counterexamples now refuse while the valid baseline passes. Grok35d7f3a
lacks that join and predates delivery of the common correction; its
continuation timeout is kept separate from candidate quality. Its correction
continues as an alternative, with no main-path dependency. Next: one fresh
exact-base resolution, then separately admit full builds. No real closure
or full build is qualified.
The [EXP/callback/save source analysis](reviews/2026-11-04-T10.010.006-root.md)
is selected/integrated from Claude2f2a610f as a75eeb2e after Root/Astra
checks both repaired analyses. All17 pins and the5121-file source digest
remain unchanged. The selected runbook preserves conditional ID collisions,
carry contributors/save windows and native EXP expectations, distinguishes
achievement callbacks from queued events, and leaves C4 skipped/not captured
without a qualified observation method. .006 is still in_progress: actual
reward/save/re-entry/restart/level-up remain unqualified.
[Image source readiness](reviews/2026-11-04-T10.010.004-image-source.md)
also finds the existing single-COPY build path is implemented; actual image
creation and all runtime reward/save checks remain open.
No personal RAM adjustment/restart, game/DB service or progress write occurs.

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
   passed on both the default and correctly bound personal instance. A separate
   build-only VM now passes actual headroom/ABI/cleanup. Diagnose the failed
   dependency transaction, authenticate matching APKs and qualify exact-base
   resolution before admitting a bounded actual build. Current personal recovery proof
   remains required before later existing-state mutations. Full content stays open.
   No broad discovery or stock
   `checkweight` substitution. These address confirmed verification/release
   gaps without changing the goal.
2. **Native build for the 0.3.2 story extension.** Qualify the bounded
   Linux/arm64 toolchain, exact dependencies/ABI, resource and deadline controls,
   cancellation/cleanup and binary export. Compile the exact prepared source.
   One discarded dependency container installs toolchain packages but fails its
   trigger; no compiler closure, custom game image or binary is qualified.
   The new builtin is unavailable in stock
   binaries.
   Personal ro4's balloon-held memory remains untouched. The separate build
   VM passes actual limits/headroom and is stopped. Actual dependency closure
   and full-build fit remain unproved; no full build is admitted yet.
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
execution/verification for .004; .005 source is integrated, with runtime
pins deliberately unqualified. The .004 dependency recipe and .006 analysis
source are selected/integrated; real exact-base closure is the next experiment. Fresh build-only state initialization
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
