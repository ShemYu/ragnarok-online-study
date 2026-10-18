# Current status — resume here

Updated: 2026-10-18. Coordinator: Codex. Active scope: **execute the documented strategy through the full milestone**.

## Where we are

- **Goal:** personally playable Mac-local Modern / Renewal RO, with the agreed episode's complete map/monster/story scope, Traditional Chinese game UI/text and persistent solo progression. See [Goal](GOAL.md).
- **Phase:** P1 foundation feasibility. **Task:** T04, `in_progress` after T03 checkpoint `022ab07`. T03 is `ready_for_user` for supported headless/browser startup; T01/T02 were checkpointed at `8cb598d` / `2523fd4`. Gameplay and user acceptance remain pending.
- **Runtime:** Ragnarok Offline v1.6.3 is Ready in supported headless/browser mode. Root verified ordinary tutorial combat/quest rewards, natural travel to Izlude, equipment, full relaunch and A → B → A → B recovery. Missing ground-item art is traced to literal damaged names in the older Taiwan table: [T04.002 diagnosis](reviews/2026-10-18-T04.002.md); T04.003 will implement a compatibility overlay. Guest/container internet denial with actual login/walk/save/re-entry passed and all trial rules were removed; host/browser offline verification remains open: [T04.001](reviews/2026-10-18-T04.001.md). The [30-minute resource observation](RESOURCES.md) is complete. Native window control, full Chinese/story/content scope and ordinary pickup remain unverified.
- **Git:** coordination branch `ShemYu/reverse-the-Ragnarok-Online-to-play-by-myself`; starting commit `c6314bbd85caa01f54fdcc38d62168e101e2c5a4`. Current documentation checkpoint: locate with `git log -1 --format='%h %s' -- AGENTS.md docs/project` after commit.
- **First paired benchmark:** independent Claude/Grok documentation-planning proposals on the same brief. Both scored 12/20 and needed corrections; the coordinator integrated a synthesis. This is a proposal comparison, not a runtime or coding benchmark. See [Planning review](reviews/2026-10-18-planning.md).

## How many steps until play?

The first playtest is an intermediate checkpoint within the full milestone. T01–T04 lead to basic gameplay; T05 adds a verified Traditional Chinese sample. Do not wait for the later complete-world qualification to offer the user this trial once the coordinator has verified it.

| Step | Task | Visible result |
| --- | --- | --- |
| 1 | T01 | Source and release versions are pinned; remaining foundation risks are explicit |
| 2 | T02 | Actual game assets are downloaded, extracted and identified |
| 3 | T03 | Installed app launches to the character screen |
| 4 | T04 | Coordinator verifies walking, combat, loot, map travel, save/reload, offline operation and recovery; basic playtest can be offered |
| 5 | T05 | Coordinator verifies Chinese UI/input and a server story-dialogue sample; Chinese playtest can be offered |

T01–T03 are verified within their scopes: **one step remains for a basic playtest, two for a Chinese playtest**. Current task status is in the opening section and [task board](TASKS.md). The planning budget remains 2–4 engineering hours for a basic feasibility trial **after compatible assets are available**, assuming no substantial runtime or encoding fix. Taiwan login/character-screen loading passed; map/gameplay and comprehensive text loading are pending. This is not a delivery promise. Complete maps/monsters/story/Chinese coverage still needs T06–T13 and a gap-based estimate; a task row may expand into many implementation children.

## Confirmed versus pending

| Item | State | Evidence / next action |
| --- | --- | --- |
| User selected Modern / Renewal | Confirmed user decision | Current conversation, 2026-10-18; reflected in GOAL |
| Docs, stateless handoff, model comparison, root verification and Git rollback required | Confirmed user decision | Current conversation, 2026-10-18 |
| Every completed/verified step needs a Git checkpoint; critical goal-changing issues require prompt user notification and a decision before scope changes | Confirmed user clarification | Current conversation, 2026-10-18; enforced in [Workflow](WORKFLOW.md#critical-issues-and-goal-changes) |
| Execute the strategy and finish all steps | Confirmed latest user instruction | Active thread goal, 2026-10-18; supersedes the T00-only boundary |
| Mac M1 Max / 64 GB RAM / 500+ GiB free | Locally inspected | Read-only hardware/disk inspection; private serial/UUID excluded from records |
| Candidate release, published requirements and Taiwan download page | Source-checked | [Versioned sources and limits](GOAL.md#evidence-sources) |
| Tagged app/dependency pins and official Taiwan installer URL | Coordinator source checks completed and paired T01 review integrated | [Foundation trial manifest](FOUNDATION.md), [T01 review](reviews/2026-10-18-T01.md); no binary/gameplay result |
| Installed app and local server/browser startup | Verified within T03 scope | [Installation](INSTALLATION.md): signed/notarized exact ZIP, generated settings, loopback listeners, character slots and graceful shutdown; native UI, gameplay and restore still open |
| Ordinary trial play/save/recovery | Partial coordinator verification; T04 open | [Baseline](BASELINE.md): group 0, natural map travel, quest, equipment, full relaunch and A database restore; reverse restore/pickup/offline/full resources pending |
| Exact Renewal episode / all-content contract | Unresolved | T06 inventory → T07 contract; no inferred cutoff |
| Taiwan/Big5 text compatibility and complete zh-TW story | Unverified | T02/T05 pilot, then inventory; client translation does not translate server scripts |
| Local GRF availability | Taiwan assets acquired, hashed and used for initial browser loading | [Asset manifest](ASSETS.md), [installation](INSTALLATION.md): mixed GRF families source-supported; explicit event → data0 → data order; native Taiwan precedence/exhaustive retrieval still unverified |
| Companions/rule changes for party-only gates | Awaiting user decision | Optional scope question sent; no gameplay changes depend on an assumed answer |
| Full milestone time/cost | Unknown | T07 estimates from gap inventory; setup estimates are not full delivery estimates |

## Next action and owner

1. **Coordinator now:** commit the T04.002 diagnosis and guest-trial results, then freeze T04.003's implementation brief and launch real Claude/Grok candidates in separate Orca branches/worktrees. Root verifies both locally before serial runtime integration. Continue independent T04.001 host/browser offline checks without changing the user's general networking. The resource sampler is complete and must not be restarted. Current ordinary character is in Izlude 183,211; state C remains the pre-trial backup at 188,211.
2. **User:** the solo-gate decision remains open; it does not block source auditing, assets or baseline play. Gameplay evaluation follows coordinator verification.
3. **Next checkpoint:** T04 baseline report and basic playtest. Native desktop-window usability remains an open observation; the documented browser entry point is verified. Mechanical task reviews can be grouped at the P1 phase gate.

Do not restart the older Character Lab roadmap. Do not assume a previous worker's PASS is current coordinator verification. Read the [task board](TASKS.md) and [workflow](WORKFLOW.md) before dispatching work.

## Decision and progress log

| Date | Change | Evidence / effect |
| --- | --- | --- |
| 2026-10-18 | Reframed milestone from a small custom Godot game to a full-content personal Renewal build | Existing emulator/client integration is the proposed foundation; Godot/art factory deferred |
| 2026-10-18 | Recorded feasibility as conditional | Episode coverage, Chinese text and solo story completion remain unverified |
| 2026-10-18 | Added P0–P4, T00–T13, root-first verification and paired task comparison | [Phases](PHASES.md), [Tasks](TASKS.md), [Workflow](WORKFLOW.md) |
| 2026-10-18 | Added Git source checkpoints and separate runtime-state recovery | Local commits after verification; no default-branch merge or publication in this pass |
| 2026-10-18 | Completed T00 coordinator review and documentation checks | 16 Markdown files; introduced links/anchors and task IDs checked; staged public-tree guard passed; user evaluation pending |
| 2026-10-18 | User activated full execution: follow the strategy and finish all steps | P0 go-ahead recorded; T01 active; no runtime result inferred from authorization |
| 2026-10-18 | Completed paired T01 source audit and coordinator manifest verification | Claude 17/20, Grok 18/20 on research only; tagged source/dependencies pinned, no installed app or gameplay claim |
| 2026-10-18 | Recorded first-play checkpoints and stronger user checkpoint/escalation requirement | Three steps after T01 for basic play, four for Chinese pilot; commit every completed/verified step and seek a user decision before a critical goal change |
| 2026-10-18 | Completed T02 paired plans and actual coordinator acquisition/extraction | 4936 files hashed, three GRFs identified, 203 BGM files; mixed versions/load order and Chinese remain untested; two steps to basic play, three to Chinese pilot |
| 2026-10-18 | Completed T03 installation and supported browser character-screen verification | Claude 14/20, Grok 17/20 on plans; root verified artifact/signature/configuration/server readiness/loopback/login/shutdown. Native control unavailable; T04 gameplay/recovery and T05 Chinese pending. Corrected GRF 3.0 header count, documented preparation-order deviation |
| 2026-10-18 | Checkpointed partial T04 verification; task remains open | Claude/Grok plans 14/20 each. Actual group-0 tutorial travel/quest/equipment, full relaunch persistence and A database restore; B safety archive preserved. Thirty-minute sampler running; remaining gates explicit in Baseline |
| 2026-10-18 | Verified reverse-B recovery in SQL and actual game | Exact saved-state match, unequipped shirt, retained quest/location and normal re-equipping; [Baseline](BASELINE.md) |
| 2026-10-18 | Verified natural tutorial combat and quest turn-in | Captain 21001 → 21008, two quest Wood from natural kills, Sailor consumed them and granted five Magnifiers; ordinary ground pickup remains separate |
| 2026-10-18 | Completed the scheduled resource observation and host helper restriction control | 181 samples / 1800 seconds; state C backed up; external helper denied while localhost and unrestricted controls succeeded. App/VM/browser offline proof remains open |
| 2026-10-18 | Verified guest-isolated play/save and precise Taiwan table diagnosis | All five guest/container IPv4 external controls denied, actual UI login/walk/save/re-entry passed, rules restored exactly. Modern item table and four resource GETs verified; T04.003 implementation next |

## Historical project

The repository still contains the Godot field prototype, native format readers and Character Lab source. Its older QA reports describe earlier local assets and are historical evidence. They do not establish the Renewal candidate's current behaviour. The source-only checkout does not include those old visual assets. See the root [README](../../README.md) and the preserved research links there.
