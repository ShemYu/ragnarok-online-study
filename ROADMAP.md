# Roadmap

## Saved baseline

- Local Godot field, native sprite/map readers and a small offline combat/progression loop.
- Character Lab compares original native actions with replacement clothing and a separate head.
- `native-art-poc-v0.1.0`: one male Swordsman dagger attack, one facing, nine frames; source timing and registration retained.
- Public source checkpoint with documented local asset boundaries and source-only checks.

The [milestone review](docs/character-lab/native-art-poc-v0.1.0.md) separates the clothing feedback, pending head review, technical checks and performance limitations.

## Next: make the successful process reusable

1. Review the current head without a hat and under both native hats.
2. Move job-specific paths, slot sizes and crop coordinates out of the body/head import scripts into validated configuration.
3. Reproduce the saved body and head from that configuration without changing native actions or output bytes.
4. Prove reuse with a second action in the same facing, then extend to additional facings and direction-dependent draw order.
5. Connect an accepted complete action set to the Godot actor and test equipment swaps during gameplay.

## Later

- Replace reference headgear, weapon, trail and environment art with independently authored assets.
- Build reusable source-independent fixtures for native format and composition tests.
- Expand the small local game based on observed gameplay needs.

This is an offline game-development study. A complete RO client, server emulation, online service and exact battle-formula parity are outside the current milestones.
