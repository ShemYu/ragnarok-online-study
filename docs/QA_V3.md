# Revision 3 validation — 24 September 2026

Environment: macOS, Apple M1 Max, Godot **4.5.1**, GL Compatibility renderer. The active scene uses native `prt_fild08` terrain and props. The [revision 2 report](QA.md), procedural field implementation and [previous field capture](v2/field-preview.png) remain preserved.

## Verified checks

| Suite | Result | Main coverage |
| --- | ---: | --- |
| `tests/map_integration_test.gd` | **2,614 passed** | Native crop, navigation, spawn routes, terrain height, camera ray picking, minimap and actor scale |
| `tests/ro_map_data_test.gd` | **16 passed** | GND/GAT parsing, coordinates, surface geometry, UVs, textures and malformed input |
| `tests/ro_model_data_test.gd` | **179 passed** | Native RSM fixtures, mesh registration, source scale, textures, hierarchy and invalid input |
| `tests/gameplay_test.gd` | **71 passed** | Timed combat, cancellation, retaliation, recovery, equipment, quest, class transition and saves |
| `tests/rendered_playthrough.gd` | **61 passed** | Rendered input, movement, instructor dialogue, stats, equipment, combat, panels and camera interaction |
| `tests/ro_sprite_test.gd` | **352 passed** | Native sprite decoding, registration, eight directions, equipment actions and timing |
| `tests/progression_playthrough.gd` | **39 passed** | Complete training quest, promotion, job leveling, Bash learning and connecting attack through ordinary combat |

The rendered run's conditions and results are recorded in [rendered-playthrough.json](v3/rendered-playthrough.json). Gameplay integration uses prepared states to isolate behavior and does not substitute for the full progression run.

The [revision 3 progression run](v3/progression-playthrough.json) completed **20 natural kills**, used seven potions and finished as **Swordsman, Base 6 / Job 2, Bash 1**. It took 180.37 simulated seconds at 8× time scale, or 29.26 wall seconds. The existing player save remained unchanged.

## Map measurements

The 49 × 49 navigation crop contains **1,434 walkable and 967 blocked cells**, matching the native GAT cell types. Its source-coordinate origin is **(172.5, 371.5)**. The scene uses source terrain relief and props; the training instructor and monsters are local content within that crop.

All **60 terrain-ray cases** passed across the supported camera test positions, with maximum position error **0.00008 world units**. The largest sampled difference between the GAT navigation height and the rendered GND terrain across walkable cells was **0.075 world units**. The files encode distinct navigation and visual surfaces; the measured difference remains within the test's tolerance.

Actor scale is now **0.03125 world units per source pixel**, approximately **42% larger** than revision 2's 0.022. The default Novice preview is approximately 139 screen pixels tall. This screen measurement changes with camera framing and zoom.

## Visual evidence and limits

Current captures include the [starting field](v3/field-preview.png), [combat](v3/combat-preview.png), [trainer dialogue](v3/training-preview.png), [status](v3/status-preview.png) and [compact viewport](v3/compact-preview.png). The native map includes its authored texture UVs, baked shading and source prop placements. Ground clicks and actor placement account for elevation; the minimap represents the same native area.

The normal game was launched through `Play.command`; `logs/v3-live.log` reported no errors. A further physical mouse/keyboard check could not run because the Mac was locked. The 61 rendered checks used injected input in the actual game; they are not a claim of a revision 3 physical-input session.

These checks establish the tested local map and interaction paths. Visual QA does **not** establish the user's aesthetic approval. The complete source field, original NPC population, full client effects, audio, complete job/item systems and other operating systems remain outside this revision's validation. Rules are still simplified. Source details are in [map research](MAP_V3_RESEARCH.md) and [map revision notes](MAP_V3.md).
