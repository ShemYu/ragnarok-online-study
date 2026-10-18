# Declared-reference sidecar for the raw spawn pilot (T06.002.003.005.002)

`static_spawn_references.py` annotates **every** framed event of the qualified
two-file raw spawn pilot (AntHell, Prontera; 354 events) with its declared map
and monster references. Profile `static-spawn-declared-reference-v1`; the frozen
contract is [the task brief](../../docs/project/tasks/T06.002.003.005.002.md) and
its [authored fixture](../../docs/project/fixtures/T06.002.003.005.002-authored.json).
Python 3.9+ standard library only, self-contained (`dependencies: []`; the optional
raw-producer helper dependency is not used). It reads no app, VM, SQL, browser,
cache, save, settings or network state, runs no subprocess, and never reruns an
upstream generator, scanner or CLI.

```sh
python3 -I -B tools/renewal/static_spawn_references.py \
  --raw-dir /abs/frozen/raw --map-dir /abs/frozen/map \
  --monster-dir /abs/frozen/monster --output /abs/private/new-output
python3 -I -B tools/renewal/test_static_spawn_references.py
STATIC_SPAWN_REFERENCE_FROZEN_ROOT=/abs/frozen-root \
  python3 -I -B tools/renewal/test_static_spawn_references.py
```

All four paths must be absolute. Bundles may be relocated; their names, sizes,
hashes and relationships cannot. There is no pin, limit, config, overwrite or
environment option. `STATIC_SPAWN_REFERENCE_FROZEN_ROOT` (a root holding `raw/`,
`map/` and `monster/`) is read only by the tests; without it the real-input
classes are reported as skipped.

## Input chain

Exactly ten regular files, 45347934 bytes in total, each read without following
links (`O_NOFOLLOW|O_NONBLOCK`, bounded by its pinned size) and checked against
its byte/SHA-256 pin **before** any JSON decoding:

| Bundle/file | Bytes | SHA256 |
| --- | ---: | --- |
| raw/source-lines.jsonl | 80085 | `c09c1b7ede612d6bad9ac914a906bbe60440491310918538be00f6aef641c6dd` |
| raw/static-spawn-pilot.jsonl | 260948 | `a624cf9833e9e4cf096c04f45e8782f21d2792a3446ec3c911a0406d855e4e9a` |
| raw/static-spawn-pilot-manifest.json | 6543 | `4fcf34b5076c79590e54850ba729941e920219c078c5c30d607b7c8211e5b1c5` |
| raw/static-spawn-pilot-complete.json | 462 | `4bef03ad0af29edb14b7c12bf90ed2f2b8f537ee17b2e25ec3b1e3a01e10e4aa` |
| map/map-cache-manifest.json | 2109200 | `fd49368cc132ad7a1303d1eba8705b89da1548b293265094b69dc7e80ea240f5` |
| map/map-cache-complete.json | 205 | `d8afaebd76958d8213347fd4f765cd2a226bcd0d0761c2c2e6d4db85c6742a11` |
| monster/monster-projection-manifest.json | 20320 | `71220de66e81869cb955fb0b2ad47775b79a10953d866ab8ad70189aa77b3ce1` |
| monster/monster-projection-complete.json | 601 | `8cee77900a4832cadad00f509e0b6b37ad48c6e649e8af36fa5777642386d1de` |
| monster/monster-declarations.jsonl | 40733741 | `32e88cbf8111be5be17739ca7170bd8f1568b6bba0edbb14c84582c73ceebcb4` |
| monster/monster-id-history.jsonl | 2135829 | `def51761c55bdcaa68e9b9b30eeeead37d23d74e682dedfa9e6fb89399be9075` |

A root that is or passes through a link,
a missing/extra entry, a linked, directory or special (FIFO) artifact, a wrong
byte, or swapped/duplicate roots is refused. After the pins, admission checks the
integrity graph using the existing upstream field names:

1. **Raw**: schema 1 / task T06.002.003.005.001 / profile `static-spawn-raw-v1` /
   state complete; the marker binds the actual manifest and both streams'
   bytes/hash/rows (311/354); producer `static_spawn_pilot.py` 46367 /
   `14690614…81cbd`; `inputs.reader`, `snapshot_manifest`, `selection_manifest`
   and `selection_complete` identities; counters 311 lines / 354 events / 192
   declared and supported / 0 gaps / 0 suffixes; both sources complete framing
   and projection, certified to their end; per-source event counts and terminal
   offsets cross-checked against the stream; the 837 unscanned selection indices
   are exactly `0..838` minus 691/772.
2. **Map**: status complete; marker `{generator_version 1.0.1, map_cache_manifest,
   map_cache_manifest_sha256, status complete}` binds the actual manifest;
   generator `map_cache_inventory.py` 1.0.1 `996a0cb8…08b56d`, snapshot verifier
   `22a3f4c8…24417`; `inputs.snapshot.manifest_sha256`, both
   `inputs.selection[...]` pins and `source.revision`; profile
   `rathena-0693b8c-renewal-use_grf-off`, `renewal true`, `required_use_grf` the
   integer 0, `required_db_path "db"`, name lengths 12/16, `max_mapindex` 2000;
   exact-integer `reverse_count` equals the reverse rows; no `unresolved_*` candidate.
3. **Monster**: status complete, `stop null`, `unresolved []`; the marker binds
   the actual manifest and both streams; `records_file`/`history_file` bind
   actual bytes/hash and 2699 LF rows each; generator `monster_projection.py`
   1.0.1 `45272a36…64d9`; profile `rathena-0693b8c-stock-renewal-yaml-four-roots`,
   `renewal true`, `db_path "db"`, `item_monster_sql_branch false`,
   `should_load_generator false`; `input.snapshot_manifest_sha256`,
   `input.verification.reader_sha256`, `source.revision`,
   `prerequisite.manifest.sha256` (`60fc99c4…f98a`).
4. Map and monster share revision `0693b8c6…4d3e`; all three share the snapshot
   manifest/reader identities. The three profile objects are checked separately
   and never equated. Raw has no `source.revision`; its compatibility follows from
   its fixed producer/reader/snapshot identities.

**Bridge depth is fixed.** The 40 MB declaration stream is hashed, size-checked
and LF-row counted only; it is not decoded or re-parsed. References come from the
already-qualified history stream, whose keys, types, count and order are
validated and whose rows are copied whole. This tool does not independently
revalidate every declaration/history link.

Strict JSON refuses duplicate keys, `NaN`/`Infinity` and exponent overflow
(`1e309`, nested `-1e400`). IDs, ordinals, counts and spans must be non-bool
integers; finite floats and booleans elsewhere in upstream manifests (timings,
profile flags) are accepted as data.
Fixed binding dictionaries compare scalar types as well as values: equal-valued
floats cannot stand in for raw output bytes/rows, producer/selection bytes,
source selection indexes/certified offsets or map reverse counts. Authored
post-admission tests exercise these helpers behind the production byte pins;
they are not a way to admit changed artifact bytes through the CLI.

## Core semantics

`join_events(events, reverse, candidates, histories, limits=None)` returns
exactly `{rows, counters}` and mutates nothing (copied evidence is deep-copied).
`normalise_map(raw_hex)` performs one `mapindex_getmapname` operation: the
lowercase-hex map slot is decoded to `[A-Za-z0-9_]{1,11}` with optional
case-insensitive `.gat`, one terminal `.gat` is removed and base case is kept.

One row per event, in input order, with copied indexes and raw pointer:
`{schema, source_index, event_index, raw:{kind, span, sha256}, map, monster, unjoined}`.

- **Supported static** (`projection_state supported`, empty gaps, nonnull values):
  `map` looks up the normalised name in the exact final `index.state.reverse`
  (case-sensitive). Absent → `missing`/null, stored 0 → `zero`/0 (both
  `not_applicable`, no candidates); otherwise `nonzero` with **all** candidates
  whose `index_lookup.id` equals it, in ordinal order, whole (retained,
  duplicate, discarded or unsafe alike) → `present`, or `none` if no match.
  `monster` copies the whole history row whose `id` equals the sprite (sprite 0
  included) with every declaration in order, or `no_declared_history`. The two
  links are independent.
- **Unjoined**: static gap → `static_projection_gap` with the original gaps;
  opaque → `opaque_script`; suffix → `uncertified_suffix` with its original
  detail; whitespace/line/block comments → `not_static`. Nothing is recovered
  from opaque bodies, suffix bytes or gap fields.
- Unknown kinds, malformed slots/spans, bad ordering (non-contiguous
  `event_index`, decreasing `source_index`, nonadjacent or zero-length spans,
  an event after a suffix in its source), duplicate reverse names, non-increasing
  candidate ordinals or history IDs, `id_decimal != str(id)`, count mismatches and
  bool/float/string IDs are fatal `ReferenceError`s.

Counters (15 keys) are **occurrence counts**: `events` = all rows =
static_supported + static_gap + opaque + suffix + not_static; map
missing/zero/nonzero partition supported lookups; candidate none/present
partition nonzero lookups; `map_candidate_occurrences` sums attached candidates;
monster present/missing partition supported lookups;
`monster_declaration_occurrences` sums copied declarations. They are never
distinct maps/monsters, amounts or population. The frozen real run has 354
events, 192 supported, 161 not_static, 1 opaque, 192 nonzero/present map
lookups with 192 candidate occurrences, and 192 present histories with 192
declaration occurrences.

## Limits

```json
{"completion_bytes":65536,"events":8192,"history_references":20000,"history_rows":10000,"input_total_bytes":67108864,"jsonl_bytes":16777216,"manifest_bytes":1048576,"map_candidates":10000,"map_reverse_rows":2000}
```

Authored work bounds, not native limits or a memory guarantee. Input row counts
(not copied attachments) are bounded in the core; `jsonl_bytes` accumulates
canonical row bytes as rows are admitted; `input_total_bytes` is checked before
reading and again on actual bytes; manifest/completion bytes are checked at
publication. The API accepts a complete exact mapping with every value a
nonnegative integer no greater than its default; `None` uses the defaults.
Over-limit work is refused, never truncated.

## Output and failure semantics

```
output/                                     0700, exactly three 0600 files
├── static-spawn-references.jsonl           one row per raw event
├── static-spawn-references-manifest.json   producer, inputs, provenance, raw scope, counters
└── static-spawn-references-complete.json   binds read-back manifest and stream; written last
```

Canonical JSON (sorted keys, compact, ASCII, no NaN, one LF per object); no
timestamps, absolute paths, host or timing data. `complete` means every framed
event received its defined annotation from admitted inputs, **not** that every
reference exists or native content works.

| Exit | Meaning |
| --- | --- |
| 0 | complete private publication |
| 2 | any prerequisite, type, order, bound or I/O failure; no usable owned manifest/completion |

There is no exit 1 or partial success. The output must not exist (links
included, left unchanged); its parent must be yours, not group/world writable and
outside every input root. Files are created `O_EXCL|O_NOFOLLOW` 0600 with a
short-write loop (zero progress fails), fsynced, closed and read back with owned
inode/regular/mode checks. Before and again after the directory fsync, while its
owned FD is retained, check the directory identity/owner/0700 mode, its target
pathname's non-link identity/owner/mode, the exact entries and every owned file's
regular identity/0600 mode. On late failure the run's own completion record and
manifest are unlinked only if still the owned inode. A renamed owned directory
is cleaned through its retained FD; a foreign replacement target is left
untouched. Foreign file replacements and preexisting state stay untouched.

Close errors are always fatal. Cleanup first observes whether a failed
descriptor was released, is still owned (at most one guarded extra close) or is
foreign/unknown (left untouched and reported). Tests cover before-real and
after-real close, different-inode reuse and final directory close. Identity is
captured on entry to the close helper; it is not descriptor-generation proof
against concurrent or same-inode reuse, and no universal native close-error
recovery or atomic protection against same-user races is claimed.
The final checks establish the observed state before close, not an atomic
guarantee against changes after that check or arbitrary concurrent pathname/FD
replacement.

## Tests

`test_static_spawn_references.py` covers F01–F10: the whole authored fixture with
type-tagged comparison and immutability, the five normalisation cases,
reverse-versus-forward and case rules, eleven-byte `.GAT`, configured
double-normalisation, every candidate disposition in order, history references
across visits/epochs/Clear with leading-zero Id text and sprite 0, independent
map/monster outcomes, all unjoined reasons and malformed shapes, ordering, bounds
at/over/lowered, empty inputs, counter conservation and strict JSON. Publication
faults are injected through the raw OS-operation attributes, with every
producer-opened descriptor checked before fixture cleanup. Nine structural
admission refusals run without frozen input. With the frozen root: the production
CLI is run twice (byte-identical), each of its 354 rows is compared with an
independent recomputation, and the full manifest/marker is checked; same-length
mutations in each bundle, link/relative/swapped roots and existing outputs exit
2. **Authored post-admission bridge mutations** mutate in-memory copies and
rebind their markers to reach the semantic checks behind the pins; they are not a
production byte-pin bypass. Nine negative controls replace real producer
functions (base lowercasing, last-candidate, retained-only, latest declaration,
span deduplication, gap and opaque recovery, sprite-0 sentinel, a counter fault)
and require the golden or conservation check to fail, then pass again.

## Separate unselected correction trial

This revision is an internal correction trial based on unchanged Claude commit
`df0a6c54b7b9cd85836aa1a08f71a120fe45d723`. It does not select a provider,
qualify the task for the coordinator or change the independent raw comparison.
Only this producer, its tests and this runbook change.

The trial's explicit frozen-root run with `-W error::ResourceWarning` passes
**74 tests, zero skips/failures**. Four new regression methods cover sixteen
equal-valued float binding controls; the existing descriptive timing float and
profile boolean positive; five final-directory-fsync metadata controls
(directory mode, each of three file modes, extra entry); and directory/symlink
target replacement. Both replacement controls verify owned stash marker and
manifest revocation, exact foreign target preservation and producer FD release
before fixture cleanup. Existing tests now cover all six regular write/readback
close stages before/after real close, explicitly bind different-inode FD reuse,
retain the original foreign-replacement inode and check intruder-case FD release.

Loading the exact unchanged raw producer from that Git commit into a separate
in-memory module and running these four methods gives **23 expected subtest
failures, zero errors/skips** (16 binding, five metadata, two replacement); the
descriptive-value positive passes. The raw provider checkout is never edited.
Private 0600 receipts are under the trial's ignored
`.tools/renewal/root-correction-trial-1/`. The coordinator must review this diff
and personally rerun applicable checks before considering adoption. These finite
serial controls do not extend the concurrency or close-recovery guarantee.

## Rollback

Source rollback: revert this task's commit (three files). Generated output lives
only under the private ignored `.tools/`; delete that directory. No database,
save, install or runtime state is touched.

## Not established

Two raw sources only; the other 837 selected sources, script-created/opaque
spawns (AntHell's opaque block is unjoined), native map/database membership,
effective population or respawn, map-cell eligibility, rendered or Traditional
Chinese names, story, solo feasibility, world/episode coverage and user
acceptance all remain open.
