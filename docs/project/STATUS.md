# Current status — resume here

Updated: 2026-10-18. Coordinator: Codex. Active scope: **execute the documented strategy through the full milestone**.

## Where we are

- **Goal:** personally playable Mac-local Modern / Renewal RO, with the agreed episode's complete map/monster/story scope, Traditional Chinese game UI/text and persistent solo progression. See [Goal](GOAL.md).
- **Phase:** P1 foundation feasibility. **Task:** T02, `ready_for_user` for acquisition/extraction; next T03. T01 checkpoint is `8cb598d`; T02's checkpoint is discoverable with `git log -1 --format='%h %s' -- docs/project/ASSETS.md`. Later gameplay/user acceptance is still pending.
- **Runtime:** Ragnarok Offline v1.6.3 remains a candidate; app binary not yet acquired/installed. Actual Taiwan assets have been downloaded, extracted and hashed: [manifest](ASSETS.md). No game, Chinese, content or restore test has been run for this foundation.
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

T01–T02 are verified within their scopes: **two steps remain for a basic playtest, three for a Chinese playtest**. Current task status is in the opening section and [task board](TASKS.md). The planning budget remains 2–4 engineering hours for a basic feasibility trial **after compatible assets are available**, assuming no substantial runtime or encoding fix. Taiwan loading is not verified yet. This is not a delivery promise. Complete maps/monsters/story/Chinese coverage still needs T06–T13 and a gap-based estimate; a task row may expand into many implementation children.

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
| Exact Renewal episode / all-content contract | Unresolved | T06 inventory → T07 contract; no inferred cutoff |
| Taiwan/Big5 text compatibility and complete zh-TW story | Unverified | T02/T05 pilot, then inventory; client translation does not translate server scripts |
| Local GRF availability | Taiwan assets acquired and hashed | [Asset manifest](ASSETS.md): data.grf 3.0, data0/event 1.02; loading/load order pending |
| Companions/rule changes for party-only gates | Awaiting user decision | Optional scope question sent; no gameplay changes depend on an assumed answer |
| Full milestone time/cost | Unknown | T07 estimates from gap inventory; setup estimates are not full delivery estimates |

## Next action and owner

1. **Coordinator now:** from the committed T02 checkpoint, verify the pinned T03 app artifact/bundled reader, install and test the acquired client root. Both modern and legacy GRF formats/load order need an actual loading result.
2. **User:** the solo-gate decision remains open; it does not block source auditing, assets or baseline play. Gameplay evaluation follows coordinator verification.
3. **Next checkpoint:** T03 installed/identified app and startup/character-screen result. T01/T02 evidence is available; mechanical task reviews can be grouped at the P1 phase gate.

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

## Historical project

The repository still contains the Godot field prototype, native format readers and Character Lab source. Its older QA reports describe earlier local assets and are historical evidence. They do not establish the Renewal candidate's current behaviour. The source-only checkout does not include those old visual assets. See the root [README](../../README.md) and the preserved research links there.
