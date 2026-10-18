# Current status — resume here

Updated: 2026-10-18. Coordinator: Codex. Active scope: **documentation only**.

## Where we are

- **Goal:** personally playable Mac-local Modern / Renewal RO, with the agreed episode's complete map/monster/story scope, Traditional Chinese game UI/text and persistent solo progression. See [Goal](GOAL.md).
- **Phase:** P0 documentation and feasibility planning. **Task:** T00. State: `ready_for_user`; coordinator documentation verification completed. User acceptance remains pending.
- **Runtime:** Ragnarok Offline v1.6.3 is a researched candidate. Nothing installed/downloaded; no game, Chinese, content or restore test has been run for this foundation.
- **Git:** coordination branch `ShemYu/reverse-the-Ragnarok-Online-to-play-by-myself`; starting commit `c6314bbd85caa01f54fdcc38d62168e101e2c5a4`. Current documentation checkpoint: locate with `git log -1 --format='%h %s' -- AGENTS.md docs/project` after commit.
- **First paired benchmark:** independent Claude/Grok documentation-planning proposals on the same brief. Both scored 12/20 and needed corrections; the coordinator integrated a synthesis. This is a proposal comparison, not a runtime or coding benchmark. See [Planning review](reviews/2026-10-18-planning.md).

## Confirmed versus pending

| Item | State | Evidence / next action |
| --- | --- | --- |
| User selected Modern / Renewal | Confirmed user decision | Current conversation, 2026-10-18; reflected in GOAL |
| Docs, stateless handoff, model comparison, root verification and Git rollback required | Confirmed user decision | Current conversation, 2026-10-18 |
| Current pass changes documentation only | Confirmed user constraint | Current conversation, 2026-10-18 |
| Mac M1 Max / 64 GB RAM / 500+ GiB free | Locally inspected | Read-only hardware/disk inspection; private serial/UUID excluded from records |
| Candidate release, published requirements and Taiwan download page | Source-checked | [Versioned sources and limits](GOAL.md#evidence-sources) |
| Exact Renewal episode / all-content contract | Unresolved | T06 inventory → T07 contract; no inferred cutoff |
| Taiwan/Big5 text compatibility and complete zh-TW story | Unverified | T02/T05 pilot, then inventory; client translation does not translate server scripts |
| Local GRF availability | No match in bounded search | [Search scope](GOAL.md#known-local-starting-state); T02 identifies actual inputs |
| Companions/rule changes for party-only gates | Awaiting user decision | Optional scope question sent; no gameplay changes depend on an assumed answer |
| Full milestone time/cost | Unknown | T07 estimates from gap inventory; setup estimates are not full delivery estimates |

## Next action and owner

1. **Coordinator completed:** read both model proposals, resolved planning defects, verified documentation and recorded the comparison/check results in the local P0 checkpoint.
2. **User now:** evaluate P0's goal/phase/task/rollback packet; answer the solo-gate question when convenient. No installed game is presented for this documentation gate.
3. **Next execution task:** T01, pin the foundation/source manifest. It remains planned; app installation and game asset acquisition are outside this documentation-only pass.

Do not restart the older Character Lab roadmap. Do not assume a previous worker's PASS is current coordinator verification. Read the [task board](TASKS.md) and [workflow](WORKFLOW.md) before dispatching work.

## Decision and progress log

| Date | Change | Evidence / effect |
| --- | --- | --- |
| 2026-10-18 | Reframed milestone from a small custom Godot game to a full-content personal Renewal build | Existing emulator/client integration is the proposed foundation; Godot/art factory deferred |
| 2026-10-18 | Recorded feasibility as conditional | Episode coverage, Chinese text and solo story completion remain unverified |
| 2026-10-18 | Added P0–P4, T00–T13, root-first verification and paired task comparison | [Phases](PHASES.md), [Tasks](TASKS.md), [Workflow](WORKFLOW.md) |
| 2026-10-18 | Added Git source checkpoints and separate runtime-state recovery | Local commits after verification; no default-branch merge or publication in this pass |
| 2026-10-18 | Completed T00 coordinator review and documentation checks | 16 Markdown files; introduced links/anchors and task IDs checked; staged public-tree guard passed; user evaluation pending |

## Historical project

The repository still contains the Godot field prototype, native format readers and Character Lab source. Its older QA reports describe earlier local assets and are historical evidence. They do not establish the Renewal candidate's current behaviour. The source-only checkout does not include those old visual assets. See the root [README](../../README.md) and the preserved research links there.
