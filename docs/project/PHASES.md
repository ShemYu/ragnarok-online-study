# Supervisory phases and end-user gates

Read [Goal](GOAL.md), [Tasks](TASKS.md), [Workflow](WORKFLOW.md) and [Status](STATUS.md) together. These are staged evidence gates, not a claim that the entire goal already works.

Every task gets paired Claude/Grok candidate work and coordinator verification. The coordinator updates the evidence and task state before offering a phase to the user. The user accepts the experience; a technical pass cannot stand in for that acceptance.

| Phase | Outcome | Coordinator must establish | What the user evaluates | Stop / reconsider condition |
| --- | --- | --- | --- | --- |
| P0 — scope, feasibility and handoff | Current goal, unknowns, task ownership and Git recovery are explicit | Read-only source claims checked; model proposals reviewed; docs/links/branch controls verified | Can understand what will be built, what remains unknown, the next task and how to roll back | Docs imply the app, all content or Chinese are already verified |
| P1 — executable and Chinese feasibility | One pinned local Renewal installation is a viable foundation | Artifact hash/version recorded; baseline combat/save/restart/offline play tested; Chinese UI and server dialogue pilot; 30-minute resource observation; backup/restore rehearsal | Launch a character, fight/loot, relaunch into saved progress, read a short Chinese interaction and use input | App cannot run, compatible assets unavailable, unresolvable Chinese encoding, or recovery fails within the bounded trial |
| P2 — episode and coverage contract | An exact content manifest and localization gap inventory define “all” | Match client/server versions; inventory maps, spawns, monsters, items/skills, NPCs, quest chains, instances and text; identify a defensible supported episode | Review the world/story list and visible exclusions; play a representative early and later section; judge a Chinese terminology sample | No coherent episode fits available content, or discovered gaps exceed an acceptable plan |
| P3 — complete and adapt the scoped build | Missing in-scope content, localization and approved solo barriers are resolved | Per-gap tasks reproduce failures and independently prove fixes; script logic/IDs intact; solo changes documented; evidence tied to commits and runtime backups | Review changed areas and Chinese story in context; confirm solo pacing, terminology and intended deviations | A critical quest chain or required area remains broken, untested or unintelligible |
| P4 — qualify and hand over milestone 1 | A reproducible, recoverable solo Renewal build meets the content contract | Every required coverage entry has a stated verification method/result; full required quest-chain qualification; persistence/offline/performance/restore checks; known-gap report; installation and rollback instructions | Follow the play guide without agent assistance; evaluate core game flow and agreed story/late-game scenarios; accept or return specific issues | Samples are presented as full coverage, required content is missing, or recovery/persistence fails |

## Gate rules

1. The phase can be `ready_for_user` only after coordinator self-verification. Each review packet names the task IDs, candidate/version/commit, checks, actual results and remaining limitations.
2. A source-only audit may pass P0. It cannot pass P1 or establish content/translation completeness.
3. P1 proves foundation feasibility, not “all maps and story.” P2 determines coverage. P4 requires the agreed coverage to be verified rather than extrapolated from a few scenes.
4. For each required quest chain, record whether verification is automated, a coordinator playthrough, or both. A skipped or unknown entry stays open; document precisely what automated checks establish.
5. User decisions at a gate may change the content contract. Record the decision and update dependent tasks before continuing; do not silently drop requested content.
6. A failed candidate remains evidence. Preserve its source revision and failure record; roll back source and external state using their separate procedures.

## First end-user evaluation packet

P0 is a documentation evaluation: [Goal](GOAL.md), the phase table above, [Tasks](TASKS.md), [current status](STATUS.md) and the first paired planning review. No game demonstration is claimed for this gate. P1 must later provide an actual playable demonstration and measured results.
