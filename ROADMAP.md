# Roadmap

## Active milestone — Modern / Renewal solo RO

The user prioritizes playing the full Modern/Renewal game locally on a Mac, with maps, monsters, story, Traditional Chinese and persistent personal progress. Party-only activities and their solo adaptations are deferred to the next phase. The local emulator/browser baseline is playable in tested scenarios; exact complete coverage and full Chinese story remain unverified. **Game execution is paused at the2026-10-25 handoff.** Conservative source cleanup, legacy archival and current feature-branch commit/push are authorized. The 2026-10-28 request also authorizes the fast-forward merge into local `main`; `origin/main` stays unchanged.

1. **P0:** document goal, feasibility, task ownership, paired model comparison, root verification and Git/state recovery.
2. **P1:** establish a version-pinned local runtime, compatible assets, basic gameplay/persistence/recovery, measured resources and a Chinese pilot.
3. **P2:** prioritize functional content inventory, identify actual version/coverage and gameplay gaps, and produce a gap-based estimate without narrowing the full-game goal.
4. **P3:** verify/repair ordinary gameplay first, then remaining localization/input gaps using existing resources where possible; keep party-only entries and dependencies explicit.
5. **P4:** qualify required coverage, rehearse setup/restore, and hand over a root-verified build for user acceptance.
6. **Later phase (T11):** address deferred party-only activities and define any solo adaptations. This does not block first-milestone delivery.

Read [current status](docs/project/STATUS.md), [remaining-work map](docs/project/PROJECT_MAP.md), [unfinished tasks](docs/project/TASKS.md), [phase gates](docs/project/PHASES.md) and [Git/model workflow](docs/project/WORKFLOW.md). [History](docs/project/HISTORY.md) preserves completed work. After resumption, the immediate step is the native0.3.2build, followed by isolated story/reward/save checks and supported normal integration. A worker result requires Root verification before user evaluation.

## Retired research

The earlier Godot prototype and Character Lab are retired from the active
repository at the user's request. The complete source/report snapshot remains
under [the archive tag](https://github.com/ShemYu/ragnarok-online-study/tree/archive/legacy-prototypes-2026-10-25).
See [verified archive and recovery](docs/project/reviews/2026-10-25-T00.003.md).
These historical projects are no longer part of the execution queue.
