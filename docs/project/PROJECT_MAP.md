# Remaining work and supervision

Updated: 2026-11-04 JST. **Seven-task execution resumed.**
All three prerequisite source/tooling tasks are integrated. Root's actual
binary experiment is next; release-gate source work runs in parallel. See
[the detailed next actions](NEXT_ACTIONS.md) and [audit](reviews/2026-10-29-T00.005.md).

```text
FULL MODERN / RENEWAL PERSONAL GAME
|
+-- Parallel prerequisites [3 OF 3 SELF-VERIFIED]
|   [x] T00.006: safe public/private test classification and isolated runner
|   [x] T06.005.001: provisional content ledger / 82-gap joins
|   [x] T10.010.003: reproducible native sources / bounded build recipe
|
+-- Story lane [AFTER SOURCE/BUILD RECIPE]
|   Exact 0.3.2 source is qualified; native runtime work remains:
|   [x] Isolated build VM resource/image/cleanup characterization
|   [ ] APK/base-version + stdin diagnostics [CURRENT]
|   [ ] Qualified dependencies -> full builds -> ordinary-item A/B
|   [ ] Binary/mod/text gate [SECOND SOURCE REPAIR; PARALLEL]
|   [ ] Real EXP/callback/save and uncertain-reward acceptance
|   [ ] Isolated native parser / actors / quest states / rewards
|   [ ] Save, re-entry, repeat and withdrawal checks
|   [ ] Supported normal installation and full settings Apply
|   [ ] Normal journal, travel and ordinary story progression
|
+-- World coverage [OPEN; independent work can run in parallel]
|   [ ] Effective maps / spawns / monsters / items / skills
|   [ ] NPCs / quest chains / instances / dynamic dependencies
|   [ ] Resolve and verify the 82 resource compatibility gaps
|   [ ] Coherent version/content contract and remaining estimate
|
+-- Traditional Chinese [OPEN; functionality first]
|   [ ] Remaining client/UI and system text
|   [ ] Remaining NPC/story/quest text
|   [ ] Actual macOS IME and input checks
|
+-- Final qualification [AFTER REQUIRED CONTENT]
|   [ ] Full required-coverage regression
|   [ ] Offline / performance / recovery qualification
|   [ ] Reproducible user guide and explicit acceptance
|
+-- Party-only activities [LATER PHASE; user-deferred]
```

The ledger remains **4/14 parent checkpoints qualified**, not 29% of the
world/story completed. The content denominator and full-milestone estimate
remain unfinished. Basic local play and saved progress are already available.
Three of seven audit tasks are self-verified (about 43% by task count only).
The personal resource probe passes with saves preserved. A separate 4 GiB
build VM now passes image/resources/cleanup with3.61 GiB available and is
stopped. Actual dependency installation fails on base-version drift and an APK
trigger-launch error; input authentication and a causal stdin check are next.
Grok's69-test repair closes the old edge cases; withdrawal/replacement
procedures still need correction. Claude is pending quota/report completion.
See [safe runner](reviews/2026-11-04-T00.006-root.md) and
[coverage verification](reviews/2026-11-04-T06.005.001-root.md) and
[native preparation](reviews/2026-11-04-T10.010.003-root.md); all 82 functional
gaps remain open. The historical private constructor suite remains 48/56.

[Current status](STATUS.md) is authoritative for pause state, the preserved
baseline and the next action. [Unfinished tasks](TASKS.md) gives task-level
ownership and dependencies. [History](HISTORY.md) preserves completed work,
model comparisons and the earlier detailed maps without crowding this queue.
