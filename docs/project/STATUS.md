# Current status — paused handoff

Updated: 2026-10-25 JST. Owner: coordinating Codex.

**Execution is paused at the user's request.** The current authorization is
documentation cleanup, conservative pre-merge lint/trim, a local commit and
publication of the current feature branch. No default-branch merge is
authorized. Resume game implementation only when the user resumes it.

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

1. **Native build for the 0.3.2 story extension.** Qualify the bounded
   Linux/arm64 toolchain, exact dependencies/ABI, resource and deadline controls,
   cancellation/cleanup and binary export. Compile the exact prepared source.
   No compiler is installed, no custom image is built and the new builtin is
   not available in stock binaries.
2. **Native and normal story integration.** Check script parsing, four actors,
   state transitions, capacity/refusal cases, actual rewards, repeats, saves
   and withdrawal in isolation. Then supported installation/full Apply and
   normal journal/travel/progression checks. Source tests and isolated earlier
   scenes do not close these normal-game gates.
3. **Full world/content coverage.** Finish effective maps/spawns/monsters,
   items/skills, NPCs, quest chains, instances, dynamic resources and the 82-gap
   reconciliation. Declare the coherent version/content boundary and estimate
   remaining work from it. Do not silently narrow the full-game goal.
4. **Remaining Chinese and input coverage.** Keep current overlays enabled;
   finish the unresolved UI, NPC/story/system text and real macOS IME checks
   after functional work.
5. **Final qualification and handoff.** Complete required coverage, offline,
   performance and recovery checks, rehearse the user runbook and obtain
   explicit milestone acceptance. Keep the Mac's internet connected.

The [unfinished task board](TASKS.md) holds the remaining IDs, dependencies and
next actions. The [ASCII map](PROJECT_MAP.md) shows the execution order.

## Last verified baseline — preserve; do not repeat without a reason

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

## Resume action and ownership

After the user resumes execution, Root freezes one bounded native build recipe
with equal Claude/Grok inputs and acceptance criteria, compares both plans,
then owns the serial runtime execution and independent verification. Refresh
current Engine/socket/service/save bindings after the 8 GiB restart; old IDs,
start times and consumed probe admissions are not reusable authority.

Keep the frozen normal 0.2.0 staging separate from source 0.3.2. Do not install
0.3.2 against stock binaries. Use [the existing normal-apply runbook](runbooks/T10.008-T10.009-normal-apply.md)
with refreshed exact files and current-state checks when integration is ready.

## Records and Git

- [Completed work and historical snapshots](HISTORY.md): prior verification,
  provider comparisons, failures and original task dispositions.
- [Workflow](WORKFLOW.md): equal model comparison, Root verification,
  documentation maintenance, checkpoints and external-state rollback.
- Branch: `ShemYu/reverse-the-Ragnarok-Online-to-play-by-myself`.
  The current user request authorizes committing and pushing this feature
  branch. Keep downloaded assets, raw evidence, accounts and saves local.
