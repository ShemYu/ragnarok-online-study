# Native coin capacity patch (T10.010.002)

`coin_capacity.patch` adds one read-only builtin for the ro-solo-ch1-entry mod
(0.3.2) to the app's map-server source: rAthena
`0693b8c69911d5ca42269684aa036b67d67f4d3e` plus the exact app
`2c3b2612973fb8d0ae6ad366a2b298686f2404cb` server overlays. It changes only
`src/map/pc.cpp`, `src/map/pc.hpp` and `src/map/script.cpp`
(apply with `patch -p1` from the source root).

## What it changes

- `pc_additem_plan(sd, item, amount, id, &index, &merge)`: the destination
  decision of `pc_additem`, moved out verbatim and made `const`. It scans all
  `MAX_INVENTORY` rows; the FIRST row matching ID, bound, zero expiry, unique
  ID and all card bytes decides (merge, or `ADDITEM_OVERAMOUNT` if full or
  beyond the usable slots); with no match the first physical blank decides
  (`ADDITEM_OVERITEM` if absent or inaccessible). No other field is compared.
- `pc_additem` calls it after its unchanged early checks and GUID generation,
  then commits exactly as before (merge amount/packet, or new copy, equip
  clearing, amount, favorite, data pointer, last index, nonstackable unique
  ID, packet; then log, weight, autoequip, rental, achievement, quest info).
- `pc_ch1_coin_capacity(sd, id)`: `1` fits / `0` native no-fit / `-1`
  unsupported, for an ordinary `Ch1_Root_Coin` x10 (identify 1, bound none).
  `-1` for a non-1001972, non-Etc, nonstackable or GUID item, usable slots
  over `MAX_INVENTORY`, any named physical row with amount outside 1..`MAX_AMOUNT`, or
  uint32 weight overflow. Otherwise the same `MAX_AMOUNT`/active stack limit/
  weight checks as `pc_additem` (`0` on refusal), then the shared plan. It
  generates no unique ID and changes nothing.
- `ros_ch1_coin_capacity()` registered with no arguments (`""`). It resolves
  the alias with `item_db.searchname` like `getitem`, requires ID 1001972
  and no `pet_db_search(id, PET_EGG)` mapping (never `pet_create_egg`), and
  pushes exactly one value. Every handled outcome returns
  `SCRIPT_CMD_SUCCESS`; extra arguments or no attached player push `-1`.
  `pc_checkadditem`, `pc_search_inventory`, `getitem` and all other builtins
  are unchanged.

Stock binaries do not know the builtin: the NPC fails to load until the
patched server is built and installed. That build/install/parser step is a
separate Root gate.

## Host check

```sh
python3 -I -B tools/renewal/native_capacity/test_coin_capacity.py \
    --native-source <prepared-subset> --clang /usr/bin/clang++
```

The driver verifies nine pinned source hashes, applies the patch in a fresh
temporary directory (no rejects), confirms `pc_search_inventory`,
`pc_generate_unique_id`, `pc_checkadditem` and `getitem` are byte-identical,
then extracts verbatim bodies: the UNCHANGED original `pc_additem` (the
oracle) and the patched `pc_additem_plan`/`pc_additem`/`pc_ch1_coin_capacity`
and builtin, plus `struct item`/options, enums and constants from `mmo.hpp`,
`pc.hpp`, `pet.hpp` and the `itemdb.cpp` stackability bodies.
`coin_capacity_fixture.cpp` compiles them in two namespaces and, per case,
runs the original and patched add on separate copies of one state, comparing
the enum, the whole session struct (inventory, counter, weight, data
pointers, last index), the mutable input item and the ordered trace; a third
copy is probed twice and must equal original success, with no trace and no
state change. The actual builtin body runs with minimal script/DB stubs.
Nine causal mutants must each fail: extra identify comparison, any-fit selector,
usable-only selector scan, GUID generated after the plan, coin-only/removed/
usable-only quantity guards, validating dirty blanks, and notifying before
the merge amount update. Domain cases cover malformed noncoin rows through
physical index199 after an early fitting coin, valid quantity boundaries and
dirty blank metadata. General original-versus-patched insertion still runs
on those same states; unsupported probe policy does not redefine that oracle.

Limits: host clang, not the server toolchain. `MAX_INVENTORY` is frozen at
200 (packet 20221005). `map_session_data`, `item_data`, the item/pet DB,
script stack, `ARR_FIND` (not in the subset), packets, logs, equip, delete,
rental, achievement, quest info and time are transparent typed stubs with
deterministic traces. This proves nothing about full headers, linking, the
script parser, real callbacks, persistence or the running game.
