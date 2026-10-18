# Roadmap

## Active milestone — Modern / Renewal solo RO

The user now prioritizes playing a complete, episode-scoped Renewal world/story locally on a Mac, with Traditional Chinese and persistent solo progress. An existing emulator/client stack is the proposed foundation. Exact episode coverage, Taiwan text compatibility and full story completion remain unverified. The documentation checkpoint is complete and the user has authorized executing all steps.

1. **P0:** document goal, feasibility, task ownership, paired model comparison, root verification and Git/state recovery.
2. **P1:** establish a version-pinned local runtime, compatible assets, basic gameplay/persistence/recovery, measured resources and a Chinese pilot.
3. **P2:** inventory content/localization, pin the exact episode and define the full required-content contract and gap-based estimate.
4. **P3:** fix the scoped gameplay/localization gaps and implement only the agreed solo progression changes.
5. **P4:** qualify required coverage, rehearse setup/restore, and hand over a root-verified build for user acceptance.

Read [current status](docs/project/STATUS.md), [phase gates](docs/project/PHASES.md), [task contracts](docs/project/TASKS.md), [feasibility](docs/project/GOAL.md) and [Git/model workflow](docs/project/WORKFLOW.md). A worker result must be independently verified by the coordinator before user evaluation. Existing source QA does not establish this runtime's playability.

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
