# Unfinished task board

Updated: 2026-10-25 JST. Owner: coordinator unless explicitly dispatched.
**Game execution is paused.** Status `in_progress` below retains the existing
unfinished task disposition; it does not mean a worker is currently running.

Only unfinished work is listed here. The 120 verified/ready/accepted rows have
moved out of the active view into [the historical ledger](HISTORY.md).
The 89 `ready_for_user` records still await explicit user acceptance; archiving
does not accept them. Thirty `self_verified` results retain their exact scoped
limits. Source-only completion does not close a parent's native/game gate.
Dependencies may refer to completed IDs in the historical ledger.
Each remaining ID's original brief, profile and evidence links are preserved
in its row of the [dated original task ledger](HISTORY-2026-10-25-TASKS.md).

## Resume order

1. T10.010: qualify/build the exact native source and export matching binaries.
2. T10.007–T10.010: isolated native verification, then supported normal
   integration and journal/progression/save checks.
3. T06/T07 and their independent children: complete world/content coverage,
   the 82-gap reconciliation and a coherent version/effort contract.
4. T05/T08/T09: finish remaining Chinese/input work after functionality.
5. T12/T13: full qualification, reproducible handoff and user acceptance.
   T11 is explicitly later-phase and does not block milestone 1.

## Open tasks

| Task | Phase | Pending scope | Dependencies | Status | Next action |
| --- | --- | --- | --- | --- | --- |
| T04 | P1 | Baseline play, persistence, offline and resource report | T03 | `in_progress` | Finish remaining offline/performance qualification; preserve the keep-internet-on constraint. |
| T04.001 | P1 | Calibrated offline verification design and trial | T04 partial | `in_progress` | Qualify the remaining offline scenario without disconnecting the Mac; quiet network counters are insufficient. |
| T04.005 | P1 | Field fog diagnosis and repair design | T04 field observation | `in_progress` | Verify a permanent fog/display fix on the current runtime and affected scenes. |
| T05 | P1 | Traditional Chinese encoding/UI/story pilot | T04 | `in_progress` | Finish remaining language/input pilot surfaces after functional work; retain the verified Chinese overlays. |
| T05.013 | P1 native verification, deferred | Actual macOS Traditional Chinese composition and candidate selection | Functional work takes priority; native routing/candidate gate remains open | `planned` | Exercise actual macOS composition, candidate selection and committed Traditional Chinese text in-game. |
| T06 | P2 | Full candidate content inventory; functionality first | T04 source/runtime baseline; T05 pilot evidence | `in_progress` | Reconcile expected, present, loaded, exercised and verified content into one complete inventory. |
| T06.002 | P2 | Selected server loaders and merged definition inventory | T06.001, frozen era/mod snapshot | `in_progress` | Finish selected native loaders and effective merged definitions; raw declarations alone do not close this. |
| T06.002.003 | P2 | Specialized merged server definition inventories | T06.001, actual YAML loader semantics | `in_progress` | Complete the remaining specialized definition catalogs and native/effective joins. |
| T06.002.003.003 | P2 | Item definitions and drop-reference catalogs | T06.002.003.001 | `planned` | Catalog effective item definitions and validate drop references. |
| T06.002.003.004 | P2 | Monster auxiliary databases and effective modifiers | T06.002.003.002–003, skill/config inputs | `planned` | Inventory auxiliary monster databases and their effective modifiers. |
| T06.002.003.005 | P2 | Selected static spawn declarations and reference checks | T06.002.001–002, T06.002.003.002 | `in_progress` | Finish whole-selection spawn/reference reconciliation and native loading checks. |
| T06.002.003.006 | P2 | Quest definition/objective/drop inventory | T06.002.003.001–003 | `planned` | Inventory quest definitions, objectives, drops and unresolved references. |
| T06.002.003.007 | P2 | Skill definition/per-level inventory | T06.002.003.001, frozen constants/config | `planned` | Inventory skill definitions and per-level effects. |
| T06.002.004 | P2 | Effective app overlays and runtime load reconciliation | T06.002.001–003, frozen installed state | `planned` | Reconcile app overlays with the actual runtime load order and effective content. |
| T06.003 | P2 | Client archive indexes and map render dependencies | T02, frozen overlays | `in_progress` | Finish archive-name winners and render/dependency reconciliation; retain all 82 open resource gaps. |
| T06.003.002 | P2 | Exact filename-codec/key-winner inventory | T06.003.001, frozen codec/resolver profile | `planned` | Resolve filename codecs and exact winning archive entries. |
| T06.003.003 | P2 | Static map geometry/model dependency closure | T06.002.002, T06.003.002, frozen overlays | `in_progress` | Extend qualified map repairs to the remaining geometry/model dependencies and real rendering. |
| T06.003.004 | P2 | Deferred/dynamic client resource dependencies | T06.003.003, selected server entities/config | `planned` | Inventory deferred/dynamic resources and their actual consumers. |
| T06.004 | P2 | Localization units and story-chain inventory | T06.002, T06.003 | `in_progress` | Complete text-unit, NPC and story-chain coverage; existing quoted-text extraction is only an input. |
| T06.006 | P2 ordinary gameplay verification | Isolated multi-stage quest and effective runtime-load evidence | .008 checkpoint; paired plan; proved fresh state isolation/preservation | `in_progress` | Complete effective-runtime and ordinary multi-stage quest evidence. |
| T06.006.003 | P2 root serial progression | Ordinary intro/Eden membership, hunt, rewards and persistence | Qualified .002separate world; corrected actual T07.001 paired scenario | `in_progress` | Finish the ordinary intro/Eden hunt, rewards and persistence scenario after the current story lane. |
| T06.005 | P2 | Reconciled content/gap report | T06.002–T06.004 | `planned` | Publish the reconciled required-content and gap report after its inventory inputs qualify. |
| T07 | P2 | Full-game version/coverage contract and gap-based estimate | Verified partial T06 inputs; full T06 completion still required | `in_progress` | Declare a coherent Renewal content/version contract and estimate the actual remaining gaps. |
| T07.007 | P2 modern asset acquisition | Official October Taiwan package, full extracted manifest and exact terrain/dependency catalog | Independent verified official metadata; common base6e05dfc | `in_progress` | Finish the official-package/dependency reconciliation and remaining production map gates. |
| T07.007.011 | P2 actual map loading/rendering | Four target maps through production image/instance/compile/GPU paths | Qualified .010 assets; exact actual client bundles and fresh viewer origin | `in_progress` | Complete the four target maps through genuine production render paths; isolated samples stay scoped. |
| T07.007.013.001 | P2 offline two-cell candidate | Fixed-hash client-only hypothesis normalizer; no production mapping | Qualified .013 source plan; independent of capture/world startup | `in_progress` | Finish the fixed-hash hypothesis normalizer; do not turn hypotheses into production filename mappings. |
| T07.007.014.004 | P2 compiled Chapter1 terrain | Genuine compiled parser/compile and complete dependency ledger; separate story-route readiness | Qualified .014.001/.003 bodies and unchanged normal worker architecture | `in_progress` | Finish the genuine compiled/parser/dependency ledger and separate ordinary story-route gates. |
| T08 | P3 | Client/launcher localization gaps resolved | T07 | `planned` | Resolve the remaining client/launcher text, layout, font and input gaps after functional inventory. |
| T09 | P3 | Server NPC/story/system localization gaps resolved | T07 | `planned` | Resolve remaining NPC/story/system text while preserving quest logic and rewards. |
| T10 | P3 | Missing/broken in-scope gameplay content resolved | T07 findings; repair children can prepare independently | `in_progress` | Repair missing/broken required gameplay and story content against the coverage contract. |
| T10.007 | P3 functional source | Persistent Chapter1 starter NPC registration/cancel/resume | T10.006 corrected research/source preparation; independent of normal-session resource binding | `in_progress` | Complete normal starter registration, refusal/cancel/resume and persistent ordinary progression gates. |
| T10.008 | P3 functional source | Supported Traditional Chinese True quest-text mod generator | Existing supported System-table route; independent source lane from T10.007, normal journal gate later uses actual server admission | `in_progress` | Install/relink the supported True quest-text overlay and verify the normal journal against its oracle. |
| T10.009 | P3 functional source | Chapter1 starter transport and checked18368→18369Messenger handoff | Integrated2734d8f starter, supported mechanics/commands and existing destination metadata; independent of broader geometry | `in_progress` | Complete supported normal integration of first-edge travel, Messenger handoff, fruit/return and saves. |
| T10.010 | P3 functional source | Fruit village arrival, Shasha/Maysel through18371, real rewards and resume | Qualified T10.009 source; retained mechanics/native binding; independent of pending normal installation | `in_progress` | NEXT: qualify/build the exact 0.3.2 native server, then test parser, actors, rewards, save and withdrawal before normal installation. |
| T11 | Later phase after P4 | Party-only activities and approved solo adaptations | T07 coverage; first-milestone T13 | `planned` | Later phase by user decision; inventory real party gates now. This does not block milestone 1. |
| T12 | P4 | First-milestone coverage qualification and recovery/performance report | T05 remaining + T08–T10; T07 explicit party-only deferral | `planned` | Qualify every required coverage entry plus recovery, offline and performance; account for explicit deferrals. |
| T13 | P4 | Reproducible user handoff and acceptance | T12 | `planned` | Rehearse the installation/play/rollback guide and obtain explicit milestone acceptance. |

## Acceptance contracts for unfinished parents

### T04 — basic play, persistence and resource baseline

- **Output:** character creation, walking, fighting, loot, inventory/equipment, map travel, save/quit/relaunch, offline operation and a 30-minute resource observation. Population starts disabled; optional companions are a separate scenario.
- **Coordinator verification:** personally play the scenarios; compare saved values before/after relaunch; check offline operation after initial setup; measure total host app/VM memory, CPU, frame rate/time and disk footprint with a stated method/resolution. Rehearse backup/restore on test progress.
- **User evaluation:** a short play/relaunch script shows the same character, items and quest progress. Performance is judged from an actual scene, not a published memory ceiling.

### T05 — Traditional Chinese pilot

- **Output:** separate results for menus, CJK fonts/input, monster/item/skill names and descriptions, quest log, one server-side story/NPC exchange, system message and launcher/settings; a terminology sample and encoding diagnosis.
- **Coordinator verification:** inspect actual rendered text and macOS input in game; test save/reload of relevant text; verify source strings/identifiers and demonstrate both client text and server dialogue. A screenshot of one menu cannot close the story/localization goal.
- **Pilot disposition:** unreadable/unsupported Chinese needs a bounded T05 child diagnosis/fix or a documented foundation alternative before P1 passes. Readable Chinese with incomplete translations can advance with the exact gaps tracked for T08/T09; the pilot does not require translating the whole world first.
- **User evaluation:** read and interact with the Chinese sample in context. Mark unreadable text, wrong terminology and remaining English/Korean explicitly.

### T06 — content and localization inventory

- **Output:** manifest of expected and present maps/warps, monsters/spawns/skills/drops, items/skills, NPCs, quest chains, instances and text units. Track `expected`, `present`, `loaded`, `exercised`, `verified`, `missing` and verification method separately; define denominator before any coverage percentage.
- **Coordinator verification:** reconcile client assets, server databases and actually loaded scripts; check validator results and negative/missing cases; manually inspect entries including early and later content. Sampling tests the inventory method; it does not certify all gameplay.
- **User evaluation:** review the world/story coverage report and play representative sections; understand the exact gaps and uncertainty.

### T07 — content contract and estimate

- **Output:** actual Renewal version/edition evidence, full-game required-content manifest, first-milestone/deferred-party classification, localization expectations, gap tasks and effort estimate from measured throughput and gap count. Keep Taiwan terminology and client/server revisions explicit. The user confirmed full-game intent; no shipped subset is automatically accepted as all content.
- **Coordinator verification:** audit the proposed boundary against T06; verify every exclusion is visible; record assumptions/ranges and unestimated work. Client date or rAthena commit alone is not episode completeness.
- **User evaluation:** inspect actual coverage/gaps and the concrete version recommendation. The full-game goal is already confirmed; any proposed reduction still needs an explicit user decision.

### T08 — client/launcher localization

- **Output:** child tasks for each missing text/UI group, consistent glossary, compatible fonts/input and versioned overlays where appropriate. Game UI and launcher coverage reported separately.
- **Coordinator verification:** compare candidate diffs and rendering; test long strings, substitutions, layout, fallback text, input and regression scenarios on the integrated version.
- **User evaluation:** judge Chinese terminology and readability in affected windows, including item/skill and quest information.

### T09 — server dialogue/story localization

- **Output:** child tasks for missing NPC/quest/system-message groups with a glossary and source mapping; preserve identifiers, control flow, variables, placeholders and quest rewards.
- **Coordinator verification:** inspect the translated script diff and exercise affected quest states; verify options, branches, variables/rewards and persistence; review consistency with client terminology. Machine translation output is a candidate, not an accepted story.
- **User evaluation:** play/read the affected story interactions and report meaning, tone or progression issues.

### T10 — gameplay/content gaps

- **Output:** one child task per missing or broken required feature/quest/instance, with a reproducible failure and bounded fix. Prioritize progression blockers.
- **Coordinator verification:** reproduce the old failure, test both candidate fixes in isolated state, test dependencies and integrated regression, and update each content manifest entry using actual evidence.
- **User evaluation:** play the corrected area or quest using a short scenario; verify the intended behaviour and report remaining friction.

### T11 — party-only activities and solo adaptations (later phase)

- **Output:** after first-milestone delivery, define a bounded plan for the deferred party-only activities: actual multi-player gates, original behaviour, proposed adaptations/companions, affected story/instances and verification. The user authorized deferral, not a specific gameplay change. T06/T07 list these entries and dependencies now; T11 does not block T12/T13.
- **Coordinator verification:** test with one real player account; check entry requirements, companion behaviour, mechanics, rewards and save state. An admin warp or forced quest completion is not normal solo progression.
- **User evaluation:** complete the affected progression naturally and judge difficulty/pacing and documented deviations.

### T12 — full qualification

- **Output:** final first-milestone required-content matrix with an explicit later-phase party-only ledger, root verification evidence, measured resources, regression report, recoverable backup and reproducible setup/upgrade/rollback procedure.
- **Coordinator verification:** account for every required entry; test required quest-chain progression, missing-asset and dependency failures, offline play, restart, backup/restore and applicable update regression. Mark unsupported/skipped entries open. Do not infer completeness from representative scenes.
- **User evaluation:** follow a compact tour plus agreed story/endgame scenarios; inspect coverage evidence and a restore demonstration.

### T13 — handoff and user acceptance

- **Output:** play/setup/recovery guide, pinned source/runtime manifest, selected task commits, known limitations and end-user acceptance record.
- **Coordinator verification:** rehearse the guide on the qualified state; verify links, versions and backups, and ensure the task/phase ledger agrees with actual evidence.
- **User evaluation:** launch, play, resume and recover using the guide. Record explicit acceptance or create issue tasks. Only this acceptance closes milestone 1.

## Task-specific evidence and history

The [dated original task ledger](HISTORY-2026-10-25-TASKS.md) preserves all 157
original rows, their briefs/profiles, comparisons, dependencies and evidence.
Frozen task briefs in `tasks/`, profiles in `fixtures/` and dated `reviews/`
remain unchanged. Consult the relevant ID there; do not repeat a finished
source check to satisfy a still-open integration gate.

## New gap-task template

Define the ID/phase, exact inputs/base, ownership, change, constraints,
dependencies, observable acceptance and end-user outcome in a frozen brief
under `tasks/`. Follow the [equal comparison protocol](WORKFLOW.md#paired-claudegrok-task-protocol)
and [handoff record](WORKFLOW.md#minimal-handoff-record). Root verifies the
actual integrated result before the user evaluates it.
