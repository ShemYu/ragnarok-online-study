# Revision 2 validation — 23 September 2026

Environment: macOS, Apple M1 Max, official Godot **4.5.1.stable.f62fdbde1**, GL Compatibility renderer. Commands are listed in the project README. The V1 report and source snapshot are preserved under `docs/baseline-v1/`.

## Rule and native-animation checks

- `tests/rpg_rules_test.gd`: **68 checks passed**. Covers independent character factories, derived stats, EXP overflow/caps, allocation costs, inventory definitions, hit/critical behavior, First Aid, Bash and class transitions.
- `tests/ro_sprite_test.gd`: **352 checks passed**. Covers native file structure, known head/body anchor displacement, eight views and all dagger frames, equipment action groups, timing, camera-relative directions, fixed foot registration, job visual reconfiguration and holding the final death frame. The contact sheet and rendered floor comparison were inspected.

The animation tests exercise real downloaded fixtures. Unsupported format versions and malformed data are rejected by the parser. This is not an assertion that every historic RO file variant is supported.

## Gameplay integration

`tests/gameplay_test.gd`, invoked with `-- --qa`: **71 checks passed** against the real game scene. Automatic processing is paused while tests advance the actual command, combat and timer routines deterministically. Some cases deliberately prepare damage/position fixtures to isolate a condition; this suite does not claim a natural playthrough.

Covered behavior:

- Pending hits do not deliver damage on selection or wind-up. Moving, retargeting, leaving range or a target generation change prevents stale hits.
- A strike commits once; a repeated defeat call cannot duplicate rewards. Killing swings retain their follow-through.
- Monster retaliation has a wind-up, checks reach and stops on death. Displaced monsters return home after player knockout.
- Potions, First Aid, Bash, cooldowns and resource costs are enforced; Novices cannot learn/use Bash.
- Equipment updates damage and the visible armed/unarmed actor. Stat allocation immediately refreshes derived values.
- Instructor acceptance, species counts, one-time reward and Swordsman transition work. Those quest checks use prepared defeats; normal-combat progression is tested separately.
- Death, despawn, respawn generation and the four-second player return work. Sit cannot bypass the death timer; pickup cannot overwrite a pending attack.
- A versioned save round trip restores progression and equipment. Malformed nested fields and negative counters are handled without script errors.

Save checks use and delete a unique temporary file. They hash the existing player save before/after to verify that it is unchanged.

## Rendered and full-progression runs

The final rendered run passed **54 checks**: ground movement, NPC head selection and approach, dialogue acceptance, allocating STR, equipping/unequipping the Knife, real attack wind-up/damage, quest/EXP reward, cancelling an already-pending strike, sitting and rotating the camera. It also verifies that opaque panels prevent click-through. Ambient wandering is delayed for this capture fixture; combat HP, damage and retaliation remain normal. Saving is disabled.

The fresh-character progression run passed **47 checks** with **20 natural kills**, six potions and a final **Swordsman, Base 6 / Job 2, Bash 1**. It completed the instructor quest, promotion, ordinary job leveling, skill learning and a connecting Bash. It ran the ordinary frame loop at 8× time scale for 198.32 simulated seconds (25.06 wall seconds), with no injected stats, damage, XP, teleportation or skipped timers. Two Bash attempts legitimately missed before a third connected, so this run also checked the normal miss path. The existing save remained unchanged.

Exact results, timing, commands and fixture conditions are in [rendered-playthrough.json](v2/rendered-playthrough.json) and [progression-playthrough.json](v2/progression-playthrough.json). Check counts may differ between progression runs when the normal hit/miss sequence requires another Bash attempt.

The baseline comparison is `docs/baseline-v1/field.png`. Current screenshots include the starting field, native combat, trainer dialogue, character status and the compact 960×640 window. They were checked for sprite registration, foot placement, interface overlap and readability. The compact viewport really is 960×640 with unchanged 12 px UI text; it is not a scaled 1280×800 image. Damage numbers clear monster names and decorative ground continues beyond the walkable grid. The original plain placeholder art remains available for comparison; it is no longer used in the game.

An additional native-window check verified the physical 2 key enters the sitting pose, the Stand button returns to standing, and I opens the equipped inventory. A real mouse click on the instructor's head approached him and opened the training dialogue. The normal game was left running at that dialogue for user review.

## Scope

These checks establish a working local slice and verified interaction paths. They do not establish user approval of the art or combat feel. The map is original, the rules are simplified, audio and a full job/item system are absent, and neither other operating systems nor long-duration performance have been validated. The reference assets' provenance is documented separately in `RO_ASSET_RESEARCH.md`.
