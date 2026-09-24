# Native Prontera field map study

Verified on 2026-09-23 against downloaded native files. This research supplies the map revision with actual Ragnarok ground and props, rather than trying to approximate the original with generic procedural materials.

## Concrete reference and available source

The [official Japanese Prontera field guide](https://ragnarokonline.gungho.jp/gameguide/worldmap/prontera-field.html) identifies the surrounding field maps. The selected source is **`prt_fild08`**, the field outside Prontera's south gate. The [roBrowserLegacy public demo](https://github.com/MrAntares/roBrowserLegacy/blob/master/applications/browser-examples/demo.html) supplies `https://grf.robrowser.com/` as its remote asset endpoint. Direct GET requests return the native terrain and models; no game account or game server is involved.

The complete downloaded study set is in `assets/reference-ro/map-study/`:

| Asset | Native layout | Verified size / count |
| --- | --- | --- |
| `prt_fild08.gnd` | GND 1.7 | 5,272,734 bytes; 200 × 200 ground cells; 21 diffuse texture paths |
| `prt_fild08.gat` | GAT 1.2 | 3,200,014 bytes; 400 × 400 navigation cells |
| `prt_fild08.rsw` | RSW 2.1 | 219,402 bytes; 621 scene objects, including 570 model placements |
| Twelve `.rsm` files | RSM 1.4 | Tree, bush, mushroom, stump, bench, signpost, gate, wall, pillar, guardpost, banner |
| `textures/*.png` | Endpoint-served PNG | All 21 ground textures and all 28 textures referenced by the selected models |

`provenance.json` records each source URL, original client path, size, SHA-256 and binary version where relevant. `world.json` contains parsed model placement, lighting and water metadata. `texture-map.json` maps original texture names to local `res://` resources; keys include normalized CP949-decoded Korean names, Latin-1 byte-preserving names, and basenames.

**File-extension caveat:** the public endpoint converts requested `.bmp` textures into PNG RGBA data. The local files use `.png` to match the actual format. Their bytes were preserved. Foliage still contains opaque magenta background, so the model renderer must apply the original color-key transparency. The endpoint conversion does not make all foliage automatically transparent.

This is a local reference set. Ragnarok Online artwork remains owned by Gravity and the respective rightsholders. Public availability does not establish redistribution permission or make it original project art; see the existing [sprite research](RO_ASSET_RESEARCH.md) for the shared provenance policy.

## Selected south-gate area

The native gate instance has RSW position `(-150, 0, 900)` before scaling. With geometry divided by five and the map center added, its GAT coordinates are **(170, 380)**. Two native benches sit around (135, 363) and (139, 367). A visual crop roughly spanning X 130–210, Y 310–390 includes:

- 20 copies of `tree01.rsm` and two of `tree02.rsm`;
- ten wall sections, the actual south gate and a guardpost;
- two benches.

Every model in that crop has been downloaded with its referenced textures. The nearby source tree positions include (184.29, 362.31), (185.71, 369.37), and (164.64, 335.77).

For a modest playable area, a **29 × 29 GAT crop centered at (170, 350)** contains 837 walkable and four blocked cells. Its native corner heights range from −1 to 10 before dividing by five and flipping the vertical sign. Centering at (170, 360) puts the gate closer to the opening view, but the same area has 27 blocked cells. Pick the spawn and camera after rendering the actual terrain; these counts do not prove a final composition or gameplay path.

Keep the native texture UVs, height variation and baked shading. The distinctive visual cues are the pale worn road with authored irregular grass borders, foliage assembled from textured polygon cards, natural olive grass, and the pale stone gate. Replacing the native canopy with smooth spheres or the ground with procedural noise loses precisely the visual identity the user requested.

## Scale and rendering evidence

The [roBrowser sprite renderer](https://github.com/MrAntares/roBrowserLegacy/blob/master/src/Renderer/SpriteRenderer.js) computes sprite dimensions as pixels divided by 175, multiplied by the default entity size of five. That gives **1 / 35 = 0.028571 world units per source pixel**, when one GAT navigation cell equals one world unit. The existing prototype's 0.022 scale is about 23% below that reference; moving to 1/35 enlarges the same source sprite by about 30%. Camera distance is a separate choice and should be tuned after restoring this actor-to-map relationship.

The [ground loader](https://github.com/MrAntares/roBrowserLegacy/blob/master/src/Loaders/Ground.js) stores two GAT units per GND cell and divides raw elevation by five. The [world loader](https://github.com/MrAntares/roBrowserLegacy/blob/master/src/Loaders/World.js) supplies instance position, Euler rotation and scale. Keep instance scale dimensionless if model vertices are already converted from raw units; dividing both the mesh and instance scale by five would shrink props twice.

Native map lighting metadata is longitude 45°, latitude 45°, white diffuse, ambient (0.3, 0.3, 0.3), shadow opacity 0.5. These parameters describe the reference data, not a requirement to feed the same numbers directly into Godot's different lighting model.

## Parser references and cautions

Use the primary roBrowser loader implementations above, plus [Model.js](https://github.com/MrAntares/roBrowserLegacy/blob/master/src/Loaders/Model.js), as the working layout reference. Cross-check against [Research Lab's GND description](https://ragnarokresearchlab.github.io/file-formats/gnd/) and [RSW description](https://ragnarokresearchlab.github.io/file-formats/rsw/). Some documentation tables have offset discrepancies, so native headers and the running parser are the decisive evidence.

For this GND 1.7 file, texture count is at byte 18, texture-name length at byte 22, and the first name starts at byte 26. The lightmap format is global: count, width, height, cell size, then pixel data. Each textured surface definition is 40 bytes: eight UV floats, texture index, lightmap index, and four BGRA color bytes. A ground cell carries four heights and three surface indices. These statements were checked against the actual downloaded bytes.

The data can be retrieved much faster with `Accept-Encoding: gzip`: the 5.27 MB GND response compressed to 454,185 bytes. Preserve hashes of decompressed native bytes in provenance, not transfer-compressed bytes.
