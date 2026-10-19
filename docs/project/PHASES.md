# Supervisory phases and end-user gates

Read [Goal](GOAL.md), [Tasks](TASKS.md), [Workflow](WORKFLOW.md) and [Status](STATUS.md) together. These are staged evidence gates, not a claim that the entire goal already works.

Every task gets paired Claude/Grok candidate work and coordinator verification. The coordinator updates the evidence and task state before offering a phase to the user. The user accepts the experience; a technical pass cannot stand in for that acceptance.

Current order: **functionality first**, per the [user decision](reviews/2026-10-19-functionality-first.md). Remaining T05 language/input checks do not block functional T06/T07/T10 work. Existing Chinese support stays enabled; deferred language checks and full Chinese coverage are still required before final milestone acceptance.

| Phase | Outcome | Coordinator must establish | What the user evaluates | Stop / reconsider condition |
| --- | --- | --- | --- | --- |
| P0 — scope, feasibility and handoff | Current goal, unknowns, task ownership and Git recovery are explicit | Read-only source claims checked; model proposals reviewed; docs/links/branch controls verified | Can understand what will be built, what remains unknown, the next task and how to roll back | Docs imply the app, all content or Chinese are already verified |
| P1 — executable and Chinese feasibility | One pinned local Renewal installation is a viable foundation | Artifact hash/version recorded; baseline combat/save/restart/offline play tested; Chinese UI and server dialogue pilot; 30-minute resource observation; backup/restore rehearsal | Launch a character, fight/loot, relaunch into saved progress, read a short Chinese interaction and use input | App cannot run, compatible assets unavailable, unresolvable Chinese encoding, or recovery fails within the bounded trial |
| P2 — full-game coverage contract | Actual version/content manifest and gap inventory make the full-game goal verifiable | Match client/server versions; inventory maps, spawns, monsters, items/skills, NPCs, quest chains, instances and text; identify the actual edition and gaps without reducing the full-game goal | Review the world/story list and visible exclusions; play a representative early and later section; judge a Chinese terminology sample | No coherent episode fits available content, or discovered gaps exceed an acceptable plan |
| P3 — complete first-milestone content and language | Missing ordinary solo content and localization are resolved; party-only activities are later-phase work | Per-gap tasks reproduce failures and independently prove fixes; script logic/IDs intact; party-only entries/dependencies explicitly deferred; evidence tied to commits and runtime backups | Review changed areas and Chinese story in context; confirm ordinary personal-play progression, terminology and intended deviations | A critical quest chain or required area remains broken, untested or unintelligible |
| P4 — qualify and hand over milestone 1 | A reproducible, recoverable solo Renewal build meets the content contract | Every required coverage entry has a stated verification method/result; full required quest-chain qualification and explicit party-only deferral ledger; persistence/offline/performance/restore checks; known-gap report; installation and rollback instructions | Follow the play guide without agent assistance; evaluate core game flow and agreed story/late-game scenarios; accept or return specific issues | Samples are presented as full coverage, required content is missing, or recovery/persistence fails |
| Later phase — party-only activities (T11) | Deferred activities and any solo adaptations become playable under a defined plan | Verify actual multi-player gates, prerequisites, mechanics, rewards and save state; compare bounded Claude/Grok candidates and personally verify integration | Complete affected activities and judge proposed solo behaviour | A party label hides an ordinary story blocker or an adaptation changes the goal without a decision |

## Gate rules

1. The phase can be `ready_for_user` only after coordinator self-verification. Each review packet names the task IDs, candidate/version/commit, checks, actual results and remaining limitations.
2. A source-only audit may pass P0. It cannot pass P1 or establish content/translation completeness.
3. P1 proves foundation feasibility, not “all maps and story.” P2 verifies the full-game content list and gaps. Party-only activities/adaptations are explicitly deferred by the user; T11 does not block milestone1. P4 requires the agreed coverage to be verified rather than extrapolated from a few scenes.
4. For each required quest chain, record whether verification is automated, a coordinator playthrough, or both. A skipped or unknown entry stays open; document precisely what automated checks establish.
5. User decisions at a gate may change the content contract. Record the decision and update dependent tasks before continuing; do not silently drop requested content.
6. A failed candidate remains evidence. Preserve its source revision and failure record; roll back source and external state using their separate procedures.

## First end-user evaluation packet

P0 is a documentation evaluation: [Goal](GOAL.md), the phase table above, [Tasks](TASKS.md), [current status](STATUS.md) and the first paired planning review. No game demonstration is claimed for this gate. P1 must later provide an actual playable demonstration and measured results.
