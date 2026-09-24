# Revision 3 — Prontera South Field

The field now uses the actual **`prt_fild08`** terrain and scenery. The change addresses the two main review points: the previous procedural meadow did not resemble Ragnarok's familiar fields, and the actors looked too small beside it.

## Map and actor scale

`field_world_ro.gd` is the active field implementation. It reads the native GND terrain geometry, texture coordinates and baked lighting; GAT supplies navigation and elevation; RSW placements and RSM meshes supply the gate, stone walls, guardpost, trees and benches. The reference set contains 49 ground and model textures.

The playable navigation area is **49 × 49 cells**, including the source map's blocked cells. A larger visual crop preserves the surrounding scenery rather than ending the landscape at the walking boundary. Actors follow the native terrain height, ground clicks resolve elevation, and the HUD minimap represents the same native area.

Sprite scale changed from **0.022 to 0.03125 world units per source pixel**, an increase of approximately **42%**. This applies consistently to player, instructor and monsters, preserving their source proportions. The standing Novice is about **139 pixels tall in the default preview**; this is a framing measurement, not a fixed height at every zoom level. It deliberately exceeds the roBrowser default scale of 1/35 slightly to address the requested visibility improvement.

The original eight-direction animation, combat, character progression, equipment, training quest, controls and `progress-v2.json` saves remain in place. The instructor and six monsters are local training content, not the original field's complete NPC and spawn population.

## Before and after

Revision 2 used authored procedural terrain and scenery:

![Revision 2 field before map replacement](v2/field-preview.png)

Revision 3 loads the native Prontera field crop and larger actors:

![Revision 3 native Prontera field](v3/field-preview.png)

These captures support direct visual comparison. User acceptance of the revised art and scale is still pending. Current runtime checks and limitations are recorded in [QA_V3.md](QA_V3.md); the captures alone do not establish navigation or combat correctness.

## Implementation coordinates

| Setting | Value |
| --- | --- |
| Source field | `prt_fild08` |
| Source GND / GAT dimensions | 200 × 200 / 400 × 400 |
| Local origin in source GAT coordinates | (172.5, 371.5) |
| Initial player source GAT position | (172.5, 368.5) |
| Playable local grid | X/Z −24 through 24 |
| Visual source crop | `Rect2i(100, 295, 145, 105)` |
| Source north | Local negative Z |
| Actor pixel scale | 0.03125 world units |

The ground remains registered to the source map; height is offset so the initial player position begins at local Y = 0. The scene keeps each supported model's source position, rotation and scale. Visual crop dimensions are larger than the playable grid because surrounding walls and foliage remain visible from the camera.

| File | Purpose |
| --- | --- |
| `scripts/field_world_ro.gd` | Active field assembly, crop, navigation, elevation and minimap |
| `scripts/ro_map_data.gd` | GND/GAT decoder and terrain renderer |
| `scripts/ro_model_data.gd` | RSM model decoder and renderer |
| `scripts/ro_sprite_actor.gd` | Shared actor scale and native sprite animation |
| `assets/reference-ro/map-study/texture-map.json` | Original texture paths mapped to local PNGs |
| `assets/reference-ro/map-study/world.json` | Decoded scene placement, lighting and water metadata |
| `assets/reference-ro/map-study/provenance.json` | Exact source URLs, versions, sizes and hashes |
| `scripts/field_world.gd` | Preserved revision 2 procedural field |

## Scope and source

This is an authentic **map crop used for a standalone learning game**. It does not load the complete field, reproduce every original client effect, or replace the local training rules with the complete original game simulation. No game server is needed.

Map files came from the public asset endpoint configured by the [roBrowserLegacy demo](https://github.com/MrAntares/roBrowserLegacy/blob/master/applications/browser-examples/demo.html). They remain local Ragnarok reference assets with recorded provenance. See [native map research](MAP_V3_RESEARCH.md) for the source-format evidence, source scale calculation and download details, and [sprite research](RO_ASSET_RESEARCH.md) for actor formats and registration.
