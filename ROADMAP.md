# Roadmap

## Saved baseline

- Local Godot field, native sprite/map readers and a small offline combat/progression loop.
- Character Lab compares original native actions with replacement clothing and a separate head.
- `native-art-poc-v0.1.0`: one male Swordsman dagger attack, one facing, nine frames; source timing and registration retained.
- Public source checkpoint with documented local asset boundaries and source-only checks.

The [milestone review](docs/character-lab/native-art-poc-v0.1.0.md) separates the clothing feedback, pending head review, technical checks and performance limitations.

## Reusable artwork milestone — 2026-10-02

The [2026-09-24 workflow inspection](docs/character-lab/INSPECTION-2026-09-24.md) lists the concrete fixes (palette discipline, import resampling, runtime integration, RO draw order and hit timing) and their order.

1. Generate and gate head v3 without a hat and under both native hats. *Technical and Codex visual checks pass:* five head drawings render with none/cap/hat. User artwork acceptance remains separate.
2. Move job-specific paths, slot sizes, crops, actions and fixture variants into validated configuration. *Done (D14):* the native importers are thin `art_import.gd` wrappers reading `importers/*.json`; generic boards use `slot-board-v2` recipes.
3. Reproduce the protected saved body and head without changing native actions or output bytes. *Verified:* `wayfarer-saved-art-v1.json` rebuilds body v3, historical head v2 and back preview v2 with **100/100 byte-identical PNGs** across three packs. The historical head failure remains recorded. See [the completion evidence](docs/character-lab/COMPLETION-2026-10-02.md).
4. Prove additional actions, views and a second character through configuration. *Verified:* the 12-module Wayfarer recipe and two-module Lantern Scholar recipe pass strict gates and imports with zero report problems. Scholar uses the same palette, style bible and native template without character-specific script edits. Direction-dependent draw order (C9) remains open.
5. Verify the completed slice through the Godot actor. *Verified and installed:* Wayfarer passes 139 checks over 624 frames for idle/walk/ready/attack in eight directions; Scholar passes 58 checks over 360 ready/attack frames with explicit native fallback. Independent composite review found no blocking issue. All 14 packs are installed; save-free field boot and a fresh local-viewer browser render pass. See [final acceptance](docs/character-lab/COMPLETION-QA-2026-10-02.md); new artwork is not user-accepted.

Source-independent native composition fixtures are also complete for this milestone (D13): 11 synthetic tests run in public CI. The selected Wayfarer art budget is 67 body drawings and head 0–4; the full 94-gameplay/118-total body budget and head 5–14 are later work.

## Later

- Replace reference headgear, weapon, trail and environment art with independently authored assets.
- Expand the synthetic native fixtures as additional format and animation behavior is studied.
- Resolve C8–C12: ACT-event hit timing, direction-specific draw order, unarmed-action mapping, tick length verification and missing-action warnings.
- Expand the small local game based on observed gameplay needs.

This is an offline game-development study. A complete RO client, server emulation, online service and exact battle-formula parity are outside the current milestones.
