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

## Current action — repair the compiler's interpreter-report capture

The qualified dependency-v4 closure and original26-package base remain fixed.
The2560MiB retry compiles **both full server variants**, exits0/no timeout
in844.1s and exports271896576bytes. Root independently re-extracts104 files,
checks exact hashes,47 raw/PLAN/installed identities, base26, native cgroups,
Renewal/builtin markers, distinct binaries and tar owners/modes.

**Overall build qualification is refused.** guest_build.sh captures only the
first two wrapped INTERP lines from readelf, omitting the interpreter path.
Root and independent review directly parse both ELF program-header tables and
find the expected /lib/ld-musl-aarch64.so.1. This is a report-producer defect;
the strict validator and original refused evidence stay unchanged. Exec54479
is terminal, phase5 is consumed/failed, and neither may be replayed. See
[actual compiler result](reviews/2026-11-04-T10.010.004-root.md#both-variants-compile-interpreter-report-refuses-qualification).

Both owned containers are deleted/404; VM shutdown exits0, daemon departs and
personal five-service projections are byte-identical. Root confirms the owned
stopped binding. No images, game, SQL or saves were changed. The earlier1536MiB
OOM remains preserved separately. The [equal narrow repair](tasks/T10.010.004-interpreter-report.md)
changes only guest capture, focused regression tests and its source report.
Root must verify/select it, then prepare/review/commit a fresh admission before
another serial actual compiler run. No goal change is indicated.

The [ordinary fixtures](tasks/T10.010.004-ordinary-fixtures.md) comparison is
closed after both suppliers correct the200-row source-budget counterexample.
Root verifies both on isolated archives with all15 protected files unchanged.
Claude fbf1fcc6 is selected/integrated as four exact blobs: simpler while loop,
426-goto bound, adjacent probes and the additional enchant-grade field. Grok
48cb6e39 also passes source review with conservative44624-command/1729-goto
bounds. Both workers are released and branches retained. This is a task-local
source choice; actual parsing,200-row completion/capture, effective items,
probe purity and persistence remain open. See [selection](reviews/2026-11-04-T10.010.004-root.md#ordinary-fixture-comparison-closed-claude-selected).

Root also corrects the ordinary-item runbook: omitting the image bundle does
not disable successful up's final pruning of unused untagged images. Retain
owned A/B tags and admit that Engine-wide side effect. The complete fresh
supervisor/config/SQL/mod/client payload and actual image/port/mount bindings
remain to be qualified; source inspection does not initialize a world.

## Four audit tasks remain open

- **T10.010.004 — full binaries and ordinary items.** Selected exact-fetch
  source is integrated as `73014940`; dependency closure is now Root-qualified.
  Both variants compile, but report capture refuses qualification. Correct the
  producer, verify a fresh comparable pair, then export/read back
  immutable images, start in isolated state and verify ordinary stack/new-slot,
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
