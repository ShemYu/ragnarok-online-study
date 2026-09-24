# Willow Field environment, revision 2

The field is an original countryside study inspired by the layered 3D scenery and textured ground of classic Ragnarok Online. It is not an exact recreation of a named RO map. All environment geometry and procedural material code in this revision are authored in this project; there is no downloaded environment art.

## What changed

- One continuous ground surface blends meadow patches, dry turf, dirt, compacted wheel traces, tiny gravel and irregular soft path edges. The path layout retains the previous crossroad and southern branch.
- Oaks have tapered roots, branching trunks, overlapping broad irregular crown planes and a leaf-scale surface pattern. The earlier four spherical canopy lobes are removed.
- Rocks, bark, bridge planks and shore have world-space surface variation. Water has restrained moving ripples and shallow-bank color.
- A small stone clearing west of the spawn contains a roofed noticeboard, pinned papers, supply barrel and wooden practice target. These are scenery; the target does not itself implement combat interaction.
- Ground foliage, flowers and small stones add scale without blocking the open center.
- The meadow, river and dirt roads continue into a 90×90 visual-only skirt, so following the player or orbiting at maximum zoom does not expose a hard tile edge. The walkable area and all interactive contents stay 29×29. The skirt adds no nodes or triangles.
- Static meshes are combined by shared material after construction to reduce scene nodes and rendering submissions.

## Coordinates and navigation contract

The map still spans integer cells X/Z -14 through 14, with a flat walking plane at Y = 0. River cells X 8–10 are blocked except bridge rows Z -1, 0, 1. `build()`, `is_walkable()`, `world_to_cell()`, `cell_to_world()` and the `navigation` grid remain available with their previous signatures. All original start cells remain clear.

The noticeboard is centered at (-4.4, 3.3), with blocking cells (-5, 3) and (-4, 3). The barrel is at (-5.7, 4.4), and the target is at (-3.6, 5.4); their base footprints are marked in the navigation grid. Cobblestones remain walkable. The original QA destination (-3, 2) is preserved.

## Verification

Godot 4.5.1 editor import and script compilation passed. A separate rendered environment scene used the existing camera (orthographic size 18) and the current directional/ambient energies (0.18 / 0.35). The resulting field was visually inspected, including canopy winding, ground blending, bridge, camp and water. Rendering was performed on the Apple M1 Max with the GL Compatibility renderer.

The isolated environment reports:

| Measurement | Result |
| --- | ---: |
| Authored mesh pieces | 496 |
| Batched mesh nodes / materials | 19 |
| Triangles, including indexed surfaces | 89,854 |
| Render calls, including the shadow pass | 38 |

These are environment-only measurements, not a whole-game frame-rate claim. The field stores these counts in `environment_metrics` for inspection.

Navigation checks passed for every original spawn, the bridge rule across all 87 river cells, and routes from the player spawn to (-3, 2), (12, 4), (-6, -5) and (4, 5). Main-game playthrough, new character scale and artistic acceptance must be verified with the integrated scene.

## Files and tuning

- `scripts/field_world.gd`: placement, original mesh generation, navigation and static material batching.
- `assets/environment/ground.gdshader`: meadow/path blending and surface detail.
- `assets/environment/foliage.gdshader`: layered crown colors and small leaf groups.
- `assets/environment/surface.gdshader`: world-space stone, bark and timber grain.
- `assets/environment/water.gdshader`: local river color and animated ripples.

The material inputs are deterministic and use no external textures, sockets or services. Shader timing only animates the river; navigation is static.

A follow-up boundary check uses perspective FOV 15, camera distance 80, pitch 35 degrees, focus (-8, 0, 7), and yaw -90 degrees. The entire view is covered by the continuous terrain/river skirt; navigation rejects all tested cells outside the original map. Mesh and triangle counts remain unchanged; the extreme camera view reports 41 render calls including its shadow passes (the initial view reports 38).
