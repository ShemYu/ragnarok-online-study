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

## Current action — complete startup readbacks

**The disposable server starts; full startup qualification remains open.**
After admissiond7a21f3f is committed/pushed, supported up exits0 in21.182s.
All five services use the admitted immutable images. The current character
server registers1265 maps; captured process/file hashes match the qualified
unpatched binary. This is registration of that server's map set, not proof of
full-world coverage or working maps/quests.

The strict controller exits1 because bundled CLI exec captures only the two
SHA rows, omitting preceding cwd/UID/GID fields. Root keeps that failure:
process user/cwd and generated-mount reads remain unqualified. Astra identifies
client header-buffer loss in pinned source, consistent with the missing prefix;
no wire capture proves exactly which bytes were lost. The supported correction
is the existing bounded Engine API without Upgrade, strict complete-frame/EOF
capture and matching terminal exec inspection. Keep the original assertions.

**Clean shutdown and preservation pass the controller's actual checks.** All
five exact services receive ordered signal-only TERM, exit0 without escalation,
and supported down exits0/0.849s with the VM stopped. All1905 protected inputs
and personal projections are unchanged;28 generated host files/262737bytes are
retained. Root's fresh stopped/personal/input checks pass. Root
independently replays nine resource files, the service projection/three negative
controls and ordered shutdown; all64 terminal files remain unchanged. See
[the actual partial result](reviews/2026-11-04-T10.010.004-root.md#initialized-startup-partial-process-readback-incomplete).

**Capture source/local controls pass.** Partial-result checkpoint238937bd is
committed/pushed. The generic Engine-API helper passes Root review, Astra source
review, ten modeled cases and a real local Unix HTTP close-delimited prefix/EOF
test. No actual Engine exec follows from those controls. See
[capture checkpoint](reviews/2026-11-04-T10.010.004-root.md#non-upgrade-exec-capture-source-and-local-controls).

**Client source/module preparation also passes its scoped checks.** Root
reviews the direct managed launch plan, pins the existing Node v24.20.0 and
imports the exact helper definitions successfully. No asset method/child/
browser starts; actual protocol, write bounds, readiness and rendering stay
open. See [Node/source result](reviews/2026-11-04-T10.010.004-root.md#managed-client-source-plan-and-node-import).

**Next:** capture controls are committed/pushed as2faeb519. Review/admit the
same-version diagnostic restart controller for this initialized disposable world. Preserve
its DB volume/network and freeze the same Renewal/mod selection; ordinary up
repeats schema/grant/config operations. Refresh current world/output inventory,
not the old first-use loader. Complete API process/generated-mount readbacks,
then managed client and ordinary-item A/B. Keep4GiB/CPU2 and internet connected;
personal state remains untouched.

Completed prerequisites stay scoped in dated evidence:

- [Full server artifacts](reviews/2026-11-04-T10.010.004-root.md#compiler6-full-artifacts-personally-qualified),
  [immutable images/original loaders](reviews/2026-11-04-T10.010.004-root.md#image-pair-and-original-loaders-personally-qualified),
  [host assets/Chinese bytes](reviews/2026-11-04-T10.010.004-root.md#ordinary-host-assets-linked-and-personally-read-back)
  and [four read-only bind/user reads](reviews/2026-11-04-T10.010.004-root.md#read-only-user-mount-diagnostic-personally-qualified)
  pass Root's applicable checks. None proves gameplay or persistence.
- [Ordinary fixtures](reviews/2026-11-04-T10.010.004-root.md#ordinary-fixture-comparison-closed-claude-selected)
  are source-selected/integrated; real parsing/200-row capture, effective items,
  ordinary A/B behavior, probe purity and saves remain open. Both settled
  supplier terminals are released; branches retained.
- Earlier OOM/report refusals and the first pre-SQL DB-cwd refusal remain
  preserved. The corrected DB projection passes actual-metadata controls.
  No verified finding forces a goal change.

## Four audit tasks remain open

- **T10.010.004 — full binaries and ordinary items.** Both full artifacts and
  their exact dependency closure, immutable images and original-library loaders
  pass Root's fresh offline replay. Complete isolated startup readbacks, admit
  the managed client, then verify ordinary stack/new-slot,
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
