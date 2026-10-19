# Supervision, plan and current position

Date: **2026-10-19 JST**. Codex completed Navigation verification and cleanup.
Use this map for a short view of [Status](STATUS.md), [Tasks](TASKS.md) and
[Phases](PHASES.md). Status gives the current next action.
Update this map after each important change. Keep the dated evidence.

Language: short English sentences and consistent terms, using
[ASD-STE100 writing principles](https://www.asd-ste100.org/STE_faq.html).
The user requested this style for the progress map only.
This is a simple overview, not a formal standard-conformity review.

## Goal and supervision

Goal: play Modern/Renewal Ragnarok Online (RO) alone on this Mac.
The goal includes all maps, monsters and story in the agreed content version.
The game must save progress and use Traditional Chinese text and user interface (UI).
We must still agree on the exact episode and rules for content that requires a party.
We use an existing RO-compatible client and server. A new game engine remains a later research option.

```text
YOU: define the goal and scope. Evaluate the result.
 |
 v
CODEX: supervise all work. Control the shared game and database.
 |
 +-- Define one task: same inputs, base commit, scope and tests
 |       |
 |       +--> CLAUDE: separate candidate, branch and worktree
 |       +--> GROK:   separate candidate, branch and worktree
 |                    (compare plans if shared state prevents separate tests)
 |
 +-- Read both -> personally verify both -> compare and select
 |                                  |
 |                    failure ------+--> repair, test again, keep evidence
 |
 +-- Integrate -> test again -> document -> Git commit
 |
 +-- Your evaluation -> accept the result OR record a new issue

Critical issue that can change the goal -> tell you -> wait for your decision
```

Codex compares actual Claude and Grok results.
Internal assistants help with preparation and verification. They do not replace the Claude/Grok comparison.
Codex must verify each result before your evaluation. A worker cannot accept a task for you.
We use task branches and the coordination branch. We do not push or merge into the default branch.
Git can recover source files. Separate backups can recover the installed game and saved progress.
Do not replace newer progress with an older save.

## Full plan and where we are

```text
Legend: [A] you accepted   [V] Codex verified. Ready for you.
        [~] active        [ ] planned. Tests not complete.

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
             +-- T05.009 Navigation UI: ready for you

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

Four of the 14 main tasks are accepted or ready for you: T00 and T01-T03.
This gives **4/14 = 28.6%, approximately 29%**, when we count main tasks equally.
T04-T06 are active. The other seven main tasks remain planned.
We exclude child tasks from this count. The figure does not measure time, translation or playable content.
We need the content list and gap list before we can give a reliable full cost or delivery date.

## Latest completed task: T05.009 Navigation

```text
Same-base Claude/Grok implementations -> Codex selection        [V]
Integrated source and exact inverse                              [V]
Detached real-browser controls                                   [V]
Fresh full backup and newest-save preservation                    [V]
Chinese installation and native integrity positive/refusal        [V]
Live Chinese search, filters, reset/minimize, command              [V]
Normal logout/re-entry and saved progress                          [V]
Same-Chinese full cold restart                                    [V]
English rollback: native UI/data/save checks                       [V] <-- DONE
Chinese reapply                                                   [V]
Remove two temporary entries. Test normal game page and save.     [V]
Task ready for your evaluation                                    [V] <-- DONE
```

The game now uses the **Chinese Navigation version again**.
The app process is 96858. Its asset process is 97329. The server reports Ready.
The game is at character selection. All six Chinese navigation aliases remain ON.
The earlier Chinese NPC, item and story overlays also remain ON.
The tests changed only last_login. All earned progress remains the same.
Both temporary test pages are gone. The normal game page and saved progress pass.
Next, Codex will inspect the Active quest text and remaining Chinese UI samples.

The latest save receipt SHA starts with b71b67ed. The final receipt SHA starts with 7db72312.
See the full results, rollback limits and private resume paths in
the [delivery record](reviews/2026-10-19-T05.009-delivery.md#final-owned-cleanup-and-ordinary-page-handoff-qualified).
We must still test actual macOS input method editor (IME) composition and candidate selection.
Full UI, story, world, solo and offline tests remain open.
The Mac's internet remains ON, as you instructed.

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
| 2026-10-19,c04be3c | English rollback, reverse integrity refusal, live data and save tests pass; first ASCII map saved | [Rollback proof](reviews/2026-10-19-T05.009-delivery.md#english-bundle-rollback-qualified) |
| 2026-10-19,301bd0e | User corrected the standard name to ASD-STE100; map language simplified | This map and Git history |
| 2026-10-19,ffd154c | Chinese reapply, native integrity, live UI and saved progress pass | [Reapply proof](reviews/2026-10-19-T05.009-delivery.md#chinese-reapply-qualified) |
| Current checkpoint | Exact test-page cleanup and normal-page Chinese search/save pass; T05.009 ready for you | [Final proof](reviews/2026-10-19-T05.009-delivery.md#final-owned-cleanup-and-ordinary-page-handoff-qualified) |

Codex also verified several T06 tools for source inventories.
They cover archive tables, source order, map records, YAML, monsters, spawns and references within their stated limits.
These tools do not prove that all maps, monsters or story chains work in the game.

## Claude and Grok: observed task results

| Task and comparison type | Claude | Grok | What this supports |
| --- | ---: | ---: | --- |
| T01 foundation source audit | 17/20 | 18/20 | Grok supplied the stronger audited proposal here |
| T03 installation plans | 14/20 | 17/20 | Grok supplied the stronger plan; root executed the install |
| T04.005 fog diagnosis/design | 14/20 | 17/20 | Grok's diagnosis scored higher; permanent repair remains open |
| T05.009 actual fixed-source transform | 19/20 | 18/20 | Both exact outputs/common178checks pass; Claude selected for stronger tests/simpler implementation |
| T06 declared-reference actual implementation | 16/20 | 13/20 | Claude selected; root still corrected and independently verified the integration |

Grok scored higher on several source analysis and plan tasks.
Claude supplied stronger implementations and tests in several recent tasks.
The tasks differ. These results do not establish a general winner or a speed or cost advantage.
We did not observe exact model versions, API tokens or billing.

At 2026-10-19T00:06:24Z, Orca listed 55 worker records: 53 released and two older user-retained records.
It listed 54 successful records and one earlier failed attempt. The failed attempt is released.
We could not verify whether the two retained worker contexts were still active.
Both Navigation workers are complete and released. Codex controls the current serial game tests.
This map did not start new workers. The private fleet receipt SHA starts with 3410ccca.

## Remaining decisions and phase gates

- P1: finish the active-quest, input and remaining UI samples.
  Record the offline and display limits. You can already try basic play, but the phase remains open.
- P2: agree on the exact Renewal content version. List the language and gameplay gaps.
  Confirm game behavior separately from source data. Use the gap list to estimate the remaining work.
- P3: repair each agreed gap. Apply only the solo-rule changes that you approve.
- P4: test every required content entry. Rehearse setup and recovery. Then give you the game for final evaluation.
  A task changes from ready_for_user to accepted only after you explicitly accept it.

The episode target and rules for party-only content remain open decisions.
This map does not choose them for you.
