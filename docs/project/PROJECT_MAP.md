# Remaining work and supervision

Updated: 2026-11-04 JST. **Seven-task execution resumed.**
All three prerequisite source/tooling tasks are integrated. Root's actual
binary experiment is next; release-gate and reward/save source are integrated. See
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
|   [x] APK signatures / causal closed-vs-valid stdin diagnostic
|   [x] Exact-base dependency recipe repair [SOURCE VERIFIED]
|   [x] APK counter-format repair [SOURCE VERIFIED]
|   [x] Real guest parses all47 solver rows [ACTUAL VERIFIED]
|   [x] APK3 exact-fetch correction [SOURCE VERIFIED]
|   [ ] Stock-selected URLs / measured transfer / signed closure [CURRENT]
|   [ ] Qualified dependencies -> full builds -> ordinary-item A/B
|   [ ] Binary/mod/text gate [SOURCE INTEGRATED; RUNTIME OPEN]
|   [ ] Real EXP/callback/save [ANALYSIS INTEGRATED; RUNTIME OPEN]
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
stopped. Root authenticates all four APKs and reproduces the trigger-launch
failure with closed stdin; the same actual reinstall succeeds with /dev/null.
The repaired recipe is now integrated after Root76 tests and independent
identity controls. The first exact-base solve proposes47 installs without upgrades, but the
parser drops padded counter rows and refuses before installation. The format repair passes Root81 tests and now parses all47 rows
in the actual guest. The first exact package fetch then refuses before install;
Root identifies a pinned-source lookup defect. Its fetch repair now passes
Root86 tests with zero skips and unchanged candidate-copy/main identities;
the exact source is integrated. Actual resolve6/phase7 begins downloads but
hits its300s batch limit before installation. Next: capture stock-selected
URLs without payloads, measure host transfer, then qualify all47 signed local
inputs. Cleanup and personal projections pass. Claude's release-gate source is selected and
integrated; Root's113 integrated tests and real release/withdrawal refusals
pass with644 tracked files unchanged. All actual release/runtime gates remain open.
See [safe runner](reviews/2026-11-04-T00.006-root.md) and
[coverage verification](reviews/2026-11-04-T06.005.001-root.md) and
[native preparation](reviews/2026-11-04-T10.010.003-root.md); all 82 functional
gaps remain open. The historical private constructor suite remains 48/56.

[Current status](STATUS.md) is authoritative for pause state, the preserved
baseline and the next action. [Unfinished tasks](TASKS.md) gives task-level
ownership and dependencies. [History](HISTORY.md) preserves completed work,
model comparisons and the earlier detailed maps without crowding this queue.
