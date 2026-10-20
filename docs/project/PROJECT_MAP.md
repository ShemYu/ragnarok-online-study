# Supervision, plan and current position

Date: **2026-10-20 JST**. Functionality comes first. The map scan, core-file checks and first model/ground-texture request catalog are complete.
Use this map for a short view of [Status](STATUS.md), [Tasks](TASKS.md) and
[Phases](PHASES.md). Status gives the current next action.
Update this map after each important change. Keep the dated evidence.

Language: short English sentences and consistent terms, using
[ASD-STE100 writing principles](https://www.asd-ste100.org/STE_faq.html).
The user requested this style for the progress map only.
This is a simple overview, not a formal standard-conformity review.

## Goal and supervision

Goal: play Modern/Renewal Ragnarok Online (RO) alone on this Mac.
The goal is the full Modern/Renewal game, with its maps, monsters and story.
The game must save progress and use Traditional Chinese text and user interface (UI).
Party-only activities and their solo adaptations belong to the next phase.
We must verify the actual game version, content coverage and gaps.
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
     -> T05 Chinese pilot; remaining language/input deferred   [~]
             |
             +-- T05.009 Navigation UI: ready for you
             +-- T05.010 Active quest sample: ready for you
             +-- T05.011 Quest window: ready for you
             +-- T05.012 One mixed story line: ready for you
             +-- Remaining language/input checks: later

P2  VERIFY FULL-GAME COVERAGE
    T06 World/text inventory; functional checks first           [~] <-- NOW
        Early source-only inventory runs alongside P1.
        Raw text catalog: ready. Native story coverage stays open.
     -> T07 Actual version, full content list, gaps and estimate     [ ]
             |
P3  COMPLETE THE AGREED CONTENT AND LANGUAGE
             +-- T10 Gameplay gaps: first                       [ ]
             +-- T08 Client/launcher localization: later         [ ]
             +-- T09 NPC/story localization: later               [ ]
             |
P4  QUALIFY AND HAND OVER
    T12 Required-content, persistence, recovery, performance     [ ]
     -> T13 Reproducible play guide and your acceptance          [ ]

LATER PHASE: PARTY-ONLY CONTENT
    T11 Party activities and solo adaptations                    [ ] deferred
```

Four of the 14 main tasks are accepted or ready for you: T00 and T01-T03.
This gives **4/14 = 28.6%, approximately 29%**, when we count main tasks equally.
T04-T06 are active. The other seven main tasks remain planned.
This project ledger includes T11 in the later phase. It does not measure milestone content.
We exclude child tasks from this count. The figure does not measure time, translation or playable content.
We need the content list and gap list before we can give a reliable full cost or delivery date.

## Current functionality checkpoint: all cached-map resources

```text
Freeze all 1,296 cached map names and source inputs               [V]
Compare actual Claude and Grok plans; correct the procedure       [V]
Run one isolated reader; keep the game and save untouched         [V]
Check every saved response, map record and reader cleanup         [V]
Record 1,213 header chains and 83 resource gaps                    [V]
Diagnose the 82 failed requests from retained filename data      [V]
Observe the larger file with a new limit; preserve the first run  [V]
Compare actual Claude and Grok constructor runners               [V]
Repair the runner; pass 27 tests and all 26 fixture cases          [V]
Check all 2,761 core-file jobs and all worker exits                [V]
Build the first model and ground-texture request catalog          [V]
Compare both actual asset-scanner implementations                [V]
Repair selected scanner; repeat the required checks              [V]
Prepare and verify a guard for both owned process groups         [V]
Check all 11,134 model and texture request paths                  [V]
Admit all 8,194 model targets as 8,166 distinct body jobs          [V]
Pass 13 authored cases and the shared model summary              [V]
Compare both actual model-constructor runners                    [~] <-- NOW
Check all actual model jobs and nested texture declarations      [ ]
Investigate eight files with NaN values and twelve unread tails   [ ]
Check compilation, rendering, travel and play                     [ ]
Find compatible assets for the 82 unresolved requests             [ ]
```

The original scan checker refused an extra diagnostic log.
Codex kept that failure and checked the log and all saved evidence separately.
The log matches the 82 failed requests. The separate evidence check passes.
The separate follow-up reads the complete 21.4 MB ground file.
Codex checks its data, prior context, input files and reader cleanup.
The combined evidence now has 1,214 header chains and 82 unresolved gaps.
The first run stays unchanged at 1,213 chains and 83 gaps.
The corrected runner now observes all 2,761 unique core-file jobs.
All constructors return. Their summaries match both raw candidates.
The final constructor run takes about 2 minutes 47 seconds and samples about 526 MB of RAM.
Both providers have submitted the next catalog tool. Their workers are released.
Codex passes 12 tests for each and checks both complete catalogs against the reference.
All 1,296 roots, 2,761 jobs and 11,134 request paths match.
Grok passes the file-checking case that fails in Claude's tool.
Codex integrates Grok and passes the final tests and complete data checks.
The request catalog is ready for you. The asset-scan brief and shared tests are set.
Both providers submit their scanners. Their workers are released.
Codex reads and tests both. Both pass all 48 shared checks and metadata checks.
Extra checks find cleanup, deadline and byte-count faults.
Claude scores 15/20. Grok scores 13/20. Both need repairs.
Codex integrates Claude, then adds a separate correction.
All 42 tests, 48 shared checks and 11 production controls now pass.
The 11 new regression methods expose failures in the original source.
The guard passes six tests with owned Python processes and identity checks.
Time, memory, output, crash and forced cleanup cases behave as expected.
All test processes exit. A separate unrelated test process stays untouched.
The real scan is complete. Codex checks every saved body and reference.
11,132 requests return data with the expected file headers. Two textures return 404.
Both missing textures belong to one ground file. All 8,194 model headers match.
The scan takes about 24 seconds and samples about 873 MB of RAM.
No guard acts. The reader exits cleanly. Inputs stay unchanged.
The scan does not write to the running game or save.
Codex rehashes all 8,194 model bodies twice and checks the 28 duplicate pairs.
The shared model summary passes all 13 authored cases.
Both runners use the same frozen inputs. Claude has submitted its runner.
Its normal fixtures pass, but Codex finds a false pass in a fault test.
Grok continues its own runner. Codex will verify both, then check all 8,166 jobs.
Nested texture retrieval, rendering and travel still follow.
See the [scanner comparison](reviews/2026-10-20-T06.003.003.005.md#paired-decision-and-next-correction-gate).
Before the scan, Codex checks the size metadata.
10,704 asset paths have size candidates. Their declarations total about 290 MB.
The scan includes all 430 paths that had no size candidate.
That earlier metadata uncertainty does not mean 430 files are missing.
Six world files and two collision files have NaN values. Check them further.
Twelve ground files have unread tails. Their meaning is not yet known.
Older ground files omit water as the client code specifies.
These results do not prove that a map renders or plays correctly.
The scan took about 5.5 minutes. It kept about 4.85 GiB of response data.
No purchase or goal change is needed for this check. The full cost is still unknown.
See the [map scan](reviews/2026-10-19-T06.003.003.001.md#independent-corpus-audit-and-bounded-readiness), [qualified follow-up](reviews/2026-10-19-T06.003.003.002.md#actual-targeted-observation-and-independent-root-qualification) and [final constructor checks](reviews/2026-10-19-T06.003.003.003.md#final-integrated-qualification-and-bounded-readiness).

## Completed task: T05.012 one mixed story sentence

```text
Observe all six real dialogue pages and the English line         [V]
Compare Claude and Grok; preserve both raw candidates             [V]
Integrate selected source; check exact output and unchanged logic [V]
Preserve newest save, full backup and old pilot                   [V]
Install -> check six pages and the same link target               [V]
Check save and normal re-entry                                   [V]
Check full-app cold start                                        [V]
Test old-pilot rollback                                          [V]
Reapply the new pilot                                            [V]
Final checks and game-running handoff                            [V]
Task ready for your evaluation                                  [V] <-- DONE
```

The real six-page dialogue and save/re-entry pass.
Cold start, old-pilot rollback and Chinese reapply pass.
Final checks pass. The normal game is left running.
Next: whole-world resource and functional checks.
Remaining Chinese input checks are deferred.
See the [story repair checks](reviews/2026-10-19-T05.012.md).

## Completed task: T05.011 Quest window

```text
Fixed inputs and independent expected output                    [V]
Claude and Grok source checks; raw candidates kept                [V]
Compare both: tied17/20. Select Claude as the correction basis.    [V]
Fix error messages and test runner -> integrate                  [V]
Separate browser: four tabs, text fit and original handlers      [V]
Install and browser integrity positive/refusal checks            [V]
Actual quest tabs, controls, save and normal re-entry             [V]
Same-ON cold restart                                             [V]
Quest-only rollback                                              [V]
Chinese Quest reapply                                            [V]
Remove test files -> check normal game page                      [V]
Task ready for your evaluation                                  [V] <-- DONE
```

The separate browser uses sample data and exact source fragments.
It does not change your game or prove that the installed window works.
The first Quest build is installed. Chinese Navigation stays enabled.
The browser loads the correct file and refuses the opposite file pin.
Actual Chinese quest tabs, controls and save/re-entry now pass.
Cold restart, Quest-only rollback and Chinese reapply pass.
Test files are gone. The normal game page and saved progress pass.
The Quest delivery passed. The later story repair also passes.
The normal page is now running after the T05.012 handoff.
See the [Quest checks](reviews/2026-10-19-T05.011.md).

## Completed task: T05.009 Navigation

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

Chinese Navigation, Quest and prior overlays are ON. Pilot0.2 is ON.
The current app process is58655. Its asset process is67357. The server is Ready.
Read-only resumed UI shows newer progress at Izlude136,181, Chinese Quest and active7472.
The earlier verified logged-out save starts withff3ec892. It predates newer resumed progress.
At T05.012, all earned fields survived repair, restart, rollback and reapply.
Only the normal login time changes between qualified story checks.
No database check is claimed while the game is live.
Their full alias/protected/runtime checks passed at that checkpoint; no fresh full check is claimed here.
Backup O contains earlier progress and the old pilot. Preserve newer progress; do not restore O over it.

Earlier Navigation, quest-grant and Quest-window checkpoints remain historical evidence.
Their process IDs and save hashes are not the current runtime or latest save.
See the [Navigation delivery](reviews/2026-10-19-T05.009-delivery.md#final-owned-cleanup-and-ordinary-page-handoff-qualified),
[active quest](reviews/2026-10-19-T05.010.md#ordinary-active7472sample-and-persistence-qualified),
[Quest window](reviews/2026-10-19-T05.011.md#final-cleanup-and-ordinary-page-qualified) and
[current story handoff](reviews/2026-10-19-T05.012.md#final-handoff-and-readiness).
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
| 2026-10-19,e747286 | Exact test-page cleanup and normal-page Chinese search/save pass; T05.009 ready for you | [Final proof](reviews/2026-10-19-T05.009-delivery.md#final-owned-cleanup-and-ordinary-page-handoff-qualified) |
| 2026-10-19,4f815df | Ordinary Active tab is empty; earned progress unchanged; normal story sample still needed | [Quest finding](reviews/2026-10-19-T05-active-quest-preparation.md#ordinary-active-tab-precondition-inspection) |
| 2026-10-19,d9ece6c | T05.010 plan comparison defined; current Taiwan quest table and literal7472 source verified | [Next task](reviews/2026-10-19-T05.010.md) |
| 2026-10-19,21b967f | Actual Claude/Grok plan workers started from the same frozen inputs | [Pair](reviews/2026-10-19-T05.010.md#actual-independent-pair-launched) |
| 2026-10-19,26470e3 | Fresh full M backup verified and newest saved tables unchanged | [Backup](reviews/2026-10-19-T05.010.md#independent-fresh-full-m-backup-qualified) |
| 2026-10-19,9915079 | Both plans checked18/20; corrected Grok procedure selected | [Comparison](reviews/2026-10-19-T05.010.md#both-plans-settled-and-source-comparison-complete) |
| T05.010 checkpoint | Normal7472Chinese Active/full text/save/re-entry verified; ready for you | [Quest proof](reviews/2026-10-19-T05.010.md#ordinary-active7472sample-and-persistence-qualified) |

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
| T05.012 one mixed story sentence | 18/20 | 18/20 | Both exact source results pass; Claude selected in tie; native/save/cold/rollback/reapply and handoff pass |
| T06 declared-reference actual implementation | 16/20 | 13/20 | Claude selected; root still corrected and independently verified the integration |

Grok scored higher on several source analysis and plan tasks.
Claude supplied stronger implementations and tests in several recent tasks.
The tasks differ. These results do not establish a general winner or a speed or cost advantage.
We did not observe exact model versions, API tokens or billing.

At 2026-10-19T00:06:24Z, Orca listed 55 worker records: 53 released and two older user-retained records.
It listed 54 successful records and one earlier failed attempt. The failed attempt is released.
We could not verify whether the two retained worker contexts were still active.
Both Navigation workers are complete and released. Codex controls the current serial game tests.
That earlier fleet receipt SHA starts with 3410ccca.
The newer T05.010 wave adds two actual plan workers. The startup fleet has 57 records.
Both workers were live at startup. Claude has since finished and been released.
Both plan workers are now complete and released. No reclaimable worker remains.
Both scored18/20. The normal quest sample now passes. Full-language work remains.

## Remaining decisions and phase gates

- P1: the active-quest sample passes. Defer input and remaining UI samples until after functional work.
  Record the offline and display limits. You can already try basic play, but the phase remains open.
- P2: verify the actual Renewal version and full-game coverage. List the language and gameplay gaps.
  Confirm game behavior separately from source data. Use the gap list to estimate the remaining work.
- P3: repair functional gameplay gaps first, then remaining language/input gaps.
- Later phase: address party-only activities and define their solo adaptations.
- P4: test every required content entry. Rehearse setup and recovery. Then give you the game for final evaluation.
  A task changes from ready_for_user to accepted only after you explicitly accept it.

You confirmed the full-game goal and deferred party-only content.
The inventory will show the actual version, coverage and gaps.
See the [scope decision](reviews/2026-10-19-scope-clarification.md).
