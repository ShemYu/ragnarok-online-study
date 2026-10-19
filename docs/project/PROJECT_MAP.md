# Supervision, plan and current position

Snapshot: **2026-10-19 JST**, after the personally verified English Navigation
rollback. This is a short index of [Status](STATUS.md), [Tasks](TASKS.md),
[Phases](PHASES.md) and their linked evidence. It is not a new completion claim.
Update this map when the current gate changes; preserve dated evidence below.

Format: plain ASCII diagrams. The requested **AES-STD100** definition/example
has not been supplied or identified in project records. Its interpretation is
pending the user's reply; no compliance with that named standard is claimed.

## Goal and supervision

Goal: personally playable Mac-local Modern/Renewal RO, with maps, monsters,
story/quests, Traditional Chinese UI/text and persistent solo progress. The
finite episode/content denominator and party-only solo policy remain open.
The current approach integrates an existing RO-compatible stack; a new-engine
rewrite remains deferred research.

```text
YOU: goal, scope decisions, final experience evaluation
 |
 v
CODEX: supervisor / sole owner of shared game and database actions
 |
 +-- Freeze one task: same inputs, base commit, scope and checks
 |       |
 |       +--> CLAUDE: independent candidate, isolated branch/worktree
 |       +--> GROK:   independent candidate, isolated branch/worktree
 |                    (plan-only where shared state prevents isolation)
 |
 +-- Read both -> personally verify -> compare and select
 |                                  |
 |                    failure ------+--> fix/retest, retain evidence
 |
 +-- Integrate -> verify again -> document -> Git checkpoint
 |
 +-- User evaluation -> accepted OR a new issue task

Critical goal-changing issue -> notify you -> decision before scope change
```

The actual Claude/Grok comparison is distinct from internal verification
helpers. Codex remains responsible for verification; a worker's PASS is not
user acceptance. Work stays on the coordination/task branches, with no push or
default-branch merge. Git recovers source; private app/save backups recover
external state. Never restore an old save over newer earned progress.

## Full plan and where we are

```text
Legend: [A] user accepted   [V] root verified / ready for user
        [~] active/partial [ ] planned; not yet qualified

P0  DEFINE THE PROJECT
    T00 Goal, documentation, supervision and Git controls        [A]
     |
P1  PROVE A PLAYABLE CHINESE FOUNDATION
    T01 Source/version manifest                                 [V]
     -> T02 Acquire/extract assets                              [V]
     -> T03 Install and launch the local stack                  [V]
     -> T04 Play, save/recovery, resources and offline trial     [~]
     -> T05 Chinese UI, dialogue, active quest and input pilot   [~] <-- NOW
             |
             +-- T05.009 Navigation UI: verification below

P2  DEFINE WHAT "ALL" COVERS
    T06 World/text inventory                                   [~]
        Early source-only inventory runs alongside P1.
     -> T07 Episode/content contract, gaps and full estimate     [ ]
             |
P3  COMPLETE THE AGREED CONTENT AND LANGUAGE
             +-- T08 Client/launcher localization               [ ]
             +-- T09 NPC/story/system localization              [ ]
             +-- T10 Missing/broken gameplay content             [ ]
             +-- T11 Approved solo-progression changes           [ ]
             |
P4  QUALIFY AND HAND OVER
    T12 Required-content, persistence, recovery, performance     [ ]
     -> T13 Reproducible play guide and your acceptance          [ ]
```

Top-level checkpoint accounting: **4/14 = 28.6%, approximately29%** are accepted
or ready_for_user: T00 plus T01-T03. T04-T06 are active; seven later parents are
planned. Child tasks are excluded to avoid double counting. This is **not** an
engineering-effort, translation, story or playable-world percentage. No full
delivery date or cost is established while the denominator/gaps remain open.

## Current task: T05.009 Navigation

```text
Same-base Claude/Grok implementations -> root selection          [V]
Integrated source and exact inverse                              [V]
Detached real-browser controls                                   [V]
Fresh full backup and newest-save preservation                    [V]
Chinese installation and native integrity positive/refusal        [V]
Live Chinese search, filters, reset/minimize, command              [V]
Normal logout/re-entry and saved progress                          [V]
Same-Chinese full cold restart                                    [V]
English rollback: native UI/data/save checks                       [V] <-- DONE
Chinese reapply                                                   [ ] <-- NEXT
Remove two temporary entries; normal game-page/save checks         [ ]
Task ready for your evaluation                                    [ ]
```

Current runtime is deliberately the **English Navigation rollback control**,
app86629/asset86948, Ready and logged out at character selection. Chinese
navigation data and existing NPC/item/story overlays remain ON. Earned progress
is unchanged; test logins changed only last_login. Next root action is Chinese
reapply, then cleanup and the ordinary api.html handoff. This temporary English
stage is not a change to the Traditional Chinese goal.

Latest newest-save receipt SHA begins1b5639f0; root rollback qualification begins
9805763c. Full details, rollback limits and exact private resume paths are in
the [delivery record](reviews/2026-10-19-T05.009-delivery.md#english-bundle-rollback-qualified).
Native keyboard/IME, full UI/story/world/solo and full host/browser offline
qualification remain open. The Mac's internet remains ON by user instruction.

## Verification history

| Checkpoint | Result | Evidence |
| --- | --- | --- |
| 2026-10-18,35ad527 | Goal/phase/task/Git protocol established; user authorized execution | [Goal](GOAL.md), [Workflow](WORKFLOW.md) |
| T01-T03 | Pinned sources, acquired assets, installed local stack/character screen | [Foundation](FOUNDATION.md), [Assets](ASSETS.md), [Installation](INSTALLATION.md) |
| T04 and early T05 children | Ordinary play/save/recovery and narrow Chinese dialogue/item pilots | [Baseline](BASELINE.md), [T05.006](reviews/2026-10-18-T05.006.md) |
| T05.007-.008 | Chinese navigation data repair, real original/repaired browser rollback and cleanup | [T05.008](reviews/2026-10-19-T05.008.md) |
| 2026-10-19,42e6336 | Selected Navigation source integrated unchanged | [Source selection](reviews/2026-10-19-T05.009.md#raw-pair-comparison-and-source-selection) |
| 2026-10-19,6706adf | Fresh full backup L qualified before localization | [Backup](reviews/2026-10-19-T05.009.md#fresh-full-backup-l-qualified) |
| 2026-10-19,afc1f87 | Driver preflight error caught before mutation; corrected artifact-role pin qualified | [Preparation](reviews/2026-10-19-T05.009-delivery.md#reviewed-serial-preparation) |
| 2026-10-19,4af13c2 | Chinese installed; correct native integrity loads, opposite pin refuses | [Installed proof](reviews/2026-10-19-T05.009-delivery.md#chinese-installed-and-native-execution-qualified) |
| 2026-10-19,3bde669 | Live Chinese UI and normal logout/re-entry preserve earned state | [Live proof](reviews/2026-10-19-T05.009-delivery.md#live-chinese-ui-normal-logout-and-re-entry-qualified) |
| 2026-10-19,77615ab | Full same-Chinese cold restart preserves UI/data/save | [Cold proof](reviews/2026-10-19-T05.009-delivery.md#same-chinese-cold-relaunch-qualified) |
| This documentation checkpoint | English rollback/native reverse refusal/live data/save pass; Chinese reapply pending | [Rollback proof](reviews/2026-10-19-T05.009-delivery.md#english-bundle-rollback-qualified) |

Independent T06 source-inventory children are also verified, including archive
tables, ordered source selection, map-index/cache reconciliation, YAML and
bounded monster/spawn/reference catalogs. These are inventories/tools, not
proof that all corresponding maps, monsters or story chains are playable.

## Claude/Grok profile: observed results, not a blanket ranking

| Task and comparison type | Claude | Grok | What this supports |
| --- | ---: | ---: | --- |
| T01 foundation source audit | 17/20 | 18/20 | Grok supplied the stronger audited proposal here |
| T03 installation plans | 14/20 | 17/20 | Grok supplied the stronger plan; root executed the install |
| T04.005 fog diagnosis/design | 14/20 | 17/20 | Grok's diagnosis scored higher; permanent repair remains open |
| T05.009 actual fixed-source transform | 19/20 | 18/20 | Both exact outputs/common178checks pass; Claude selected for stronger tests/simpler implementation |
| T06 declared-reference actual implementation | 16/20 | 13/20 | Claude selected; root still corrected and independently verified the integration |

Grok has useful evidence on source analysis/planning and work with exact
mechanical contracts. Claude has supplied stronger implementations/tests in
several recent tasks. These few heterogeneous comparisons do not establish a
general model winner, speed or cost advantage. Exact underlying model versions,
API tokens and billing were not observed.

Fresh Orca read at2026-10-19T00:06:24Z lists55recorded worker rows:53released,
two older user-retained;54succeeded and one historical failed/released attempt.
The two retained contexts' current liveness is unverifiable, so no stopped/live
claim is inferred for them. The current Navigation pair is settled/released;
Codex owns the present serial game verification. No new comparison wave is
launched by this overview. Private fleet receipt SHA begins3410ccca.

## Remaining decisions and phase gates

- P1: finish current reapply/cleanup plus the remaining active-quest/input/UI
  samples and documented offline/rendering boundaries. You can already try
  provisional ordinary play; this does not close P1 or the full milestone.
- P2: identify the finite Renewal episode/content list and enumerate actual
  language/gameplay gaps. Data presence is separate from effective runtime and
  normal solo completion. This supplies the defensible remaining estimate.
- P3: repair/localize per gap and apply only approved solo-rule changes.
- P4: verify every required coverage entry, rehearse recovery/unassisted setup
  and give you the final experience evaluation. Only your explicit evaluation
  changes ready_for_user to accepted.

AES-STD100 formatting remains pending its definition. The episode/content target
and companion/rule policy remain the earlier open scope questions; none is
silently assumed by this map.
