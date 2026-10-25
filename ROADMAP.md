# Roadmap

## Active milestone — Modern / Renewal solo RO

The user prioritizes playing the full Modern/Renewal game locally on a Mac, with maps, monsters, story, Traditional Chinese and persistent personal progress. Party-only activities and their solo adaptations are deferred to the next phase. The local emulator/browser baseline is playable in tested scenarios; exact complete coverage and full Chinese story remain unverified. **Game execution is paused at the2026-10-25 handoff.** Documentation cleanup and current feature-branch commit/push are authorized.

1. **P0:** document goal, feasibility, task ownership, paired model comparison, root verification and Git/state recovery.
2. **P1:** establish a version-pinned local runtime, compatible assets, basic gameplay/persistence/recovery, measured resources and a Chinese pilot.
3. **P2:** prioritize functional content inventory, identify actual version/coverage and gameplay gaps, and produce a gap-based estimate without narrowing the full-game goal.
4. **P3:** verify/repair ordinary gameplay first, then remaining localization/input gaps using existing resources where possible; keep party-only entries and dependencies explicit.
5. **P4:** qualify required coverage, rehearse setup/restore, and hand over a root-verified build for user acceptance.
6. **Later phase (T11):** address deferred party-only activities and define any solo adaptations. This does not block first-milestone delivery.

Read [current status](docs/project/STATUS.md), [remaining-work map](docs/project/PROJECT_MAP.md), [unfinished tasks](docs/project/TASKS.md), [phase gates](docs/project/PHASES.md) and [Git/model workflow](docs/project/WORKFLOW.md). [History](docs/project/HISTORY.md) preserves completed work. After resumption, the immediate step is the native0.3.2build, followed by isolated story/reward/save checks and supported normal integration. A worker result requires Root verification before user evaluation.

## Preserved historical Godot / artwork roadmap — deferred

The following baseline and tasks describe the earlier learning study. They are retained for provenance and possible later custom-engine/artwork work, not the active first-milestone queue.

### Saved baseline

- Local Godot field, native sprite/map readers and a small offline combat/progression loop.
- Character Lab compares original native actions with replacement clothing and a separate head.
- `native-art-poc-v0.1.0`: one male Swordsman dagger attack, one facing, nine frames; source timing and registration retained.
- Public source checkpoint with documented local asset boundaries and source-only checks.

The [milestone review](docs/character-lab/native-art-poc-v0.1.0.md) separates the clothing feedback, pending head review, technical checks and performance limitations.

### Former next steps: make the successful process reusable

1. Review the current head without a hat and under both native hats.
2. Move job-specific paths, slot sizes and crop coordinates out of the body/head import scripts into validated configuration.
3. Reproduce the saved body and head from that configuration without changing native actions or output bytes.
4. Prove reuse with a second action in the same facing, then extend to additional facings and direction-dependent draw order.
5. Connect an accepted complete action set to the Godot actor and test equipment swaps during gameplay.

### Former later work

- Replace reference headgear, weapon, trail and environment art with independently authored assets.
- Build reusable source-independent fixtures for native format and composition tests.
- Expand the small local game based on observed gameplay needs.

In that historical study, a complete RO client, server emulation, online service and exact battle-formula parity were outside scope. The current milestone now evaluates a **local** emulator/client integration; it does not request a public online service or a full engine reconstruction.
