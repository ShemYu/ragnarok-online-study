# Declared monster fields and conditional prefix operations (T06.002.003.002)

Version `1.0.0`, an independent Claude implementation of the frozen brief
[T06.002.003.002](../../docs/project/tasks/T06.002.003.002.md). It bridges the selected
raw YAML catalog ([T06.002.003.001](YAML_GRAPH_INVENTORY.md), 1.0.1) to later
monster, spawn, client and text inventories. It is **not** an accepted or
effective monster database and not a generic rAthena emulator.

`monster_projection.py` verifies the canonical snapshot and the selected raw
catalog, reparses the MOB_DB visit files with the unchanged selected Psych
adapter, proves every raw MOB row is reproduced exactly, and then records ten
declared fields and two conditional prefix branches per raw declaration,
following `MobDatabase::parseBodyNode` at rAthena
`0693b8c69911d5ca42269684aa036b67d67f4d3e`. It reads source only, uses the
Python 3 standard library and the existing `/usr/bin/ruby` (2.6.10, Psych 3.1.0,
libyaml 0.2.1) through the selected adapter. Nothing is installed, built or
executed from rAthena. It does not touch the app, game, VM, SQL, browser,
network or saves.

```sh
python3 -I tools/renewal/monster_projection.py \
  /abs/coordination-root/.tools/renewal/t06-candidates/integrated-2 \
  /abs/coordination-root/.tools/renewal/t06-yaml-graph-candidates/integrated-1 \
  .tools/renewal/T06.002.003.002/<new-output>
T06_MONSTER_SNAPSHOT=/abs/.../integrated-2 \
T06_MONSTER_RAW_CATALOG=/abs/.../integrated-1 \
  python3 -I -m unittest discover -s tools/renewal -p test_monster_projection.py
```

The CLI takes only the snapshot, the raw catalog and a new output directory. Pins,
profile, parser, source metadata and limits are fixed constants with no option to
change them. The actual-input test runs only when both variables are absolute
paths to existing directories; otherwise it is skipped. `execute`, `publish`,
`project`, `simulate`, `interpret`, `decimal_value` and `name_bytes` accept
small fixture inputs, pins, profiles or caps for tests; `run`/`main` never do.

```
<output>/                            0700, new (exclusive mkdir)
├── monster-declarations.jsonl       0600, one record per MOB raw row, streamed, read back
├── monster-id-history.jsonl         0600, one line per supported decimal first Id, read back
├── monster-projection-manifest.json 0600, written and read back after both records
└── monster-projection-complete.json 0600, only when status is complete, written last
```

| Exit | Status | Meaning |
| --- | --- | --- |
| `0` | `complete` | every MOB declaration reconstructed, matched and projected without a projection gap; marker present |
| `1` | `qualified` | every declaration projected, at least one reached field is a policy/extraction gap; no marker |
| `1` | `unsupported` | a parser, provenance or work-limit stop; emitted rows are a qualified prefix, the rest is listed as unresolved; no marker |
| `2` | — | input identity/relationship refusal (nothing created) or publication refusal/failure |

Known Id-range, null and missing-mandatory outcomes are fully described source
prefixes and do not block `complete`. An ignored duplicate or an excluded later
field never does either. `complete` means projection completeness in this
bounded profile; membership and later parsing stay unresolved by design.

## Identity bridge

1. **Selected tools.** `yaml_graph_inventory.py` (73057 bytes,
   `7962cb6e…8990`) and `server_selection.py` (36455 bytes, `22a3f4c8…4417`) are
   read no-follow, size- and hash-checked, and the inventory module is executed
   from exactly those verified bytes. The snapshot reader hash it reports is
   rechecked.
2. **Snapshot.** The unchanged `server_selection.read_snapshot` default pins verify
   the whole snapshot (manifest `79ee4eff…1dbd0`, 1683 files, 68752782 bytes,
   regular files only, every size and hash). The three MOB files must also equal
   their brief pins.
3. **Prerequisite files.** The catalog directory is opened no-follow and must hold
   exactly the three selected files. Each is opened with
   `O_NOFOLLOW|O_NONBLOCK` (a FIFO never blocks), must be a regular file of the
   pinned size with stable descriptor identity, and must match its SHA-256:
   manifest 56125 / `60fc99c4…f98a`, completion 428 / `a666d99d…f12c41c`,
   records 49723211 / 38538 lines / `a9366bcd…6230`. JSON is strict (duplicate
   keys and NaN/Infinity refused) and must be the selected rendering byte for byte.
4. **Relationships.** Completion → manifest SHA, completion → records SHA,
   manifest `records_file` → streamed bytes/lines/hash; status complete; generator
   tool/version/source hash; parser executable/versions plus the selected adapter
   SHA-256 against a fresh parser identity check; profile and source equal the
   selected constants; `input` equals the freshly verified snapshot identity
   (manifest hash, counts, reader and reader hash); no stop, unresolved work or
   known failures.
5. **Whole stream.** The full records file is hashed and read one line at a time
   (16 MiB line cap). Every line must be the canonical selected encoding with the
   exact row key set, `global_ordinal` equal to its line number, a visit whose
   Body range contains it, and matching database, root order, file, file hash,
   epoch, local and per-database ordinals. Per-visit and per-database row counts
   must equal the manifest. Only `database == "MOB_DB"` rows are kept, in global
   order (no glob, sort or dedupe).
6. **Derived MOB selection.** Visits, row count, first/last global ordinals,
   epochs, Clear events and distinct files are derived from the bound manifest and
   stream and, in the CLI, must equal the canonical selection (visits 9, 10, 11;
   2699 rows; ordinals 30991–33689; epoch 0; no Clear). These are raw
   declarations, not entity totals.
7. **Reparse and exact reconstruction.** Each distinct MOB visit file is parsed
   once (whole-file context) with the selected `precheck_bytes`, `parse_yaml`,
   `check_syntax`, `LineIndex` and `row_record`. Header Type/Version, Clear,
   duplicate-site count, Body presence and row count must equal the visit record.
   Every Body row is rebuilt as the complete raw row object (visit metadata,
   ordinals, marks, spans, fields, raw ids, node count, fingerprint) and must equal
   the prerequisite row exactly. Repeated visits of a file reuse its immutable
   parsed rows but attach their own visit/epoch/ordinals. A mismatch, parser
   refusal or limit is a qualified `unsupported` stop, never a projection.

Import selection is not rerun or extended; the prerequisite's conditional
callback-return assumption is inherited. Raw catalog completeness does not attest
native parser parity or native row acceptance.

## Ten field declarations

Fields in source parser order: `Id`, `AegisName`, `Name`, `JapaneseName`, `Level`,
`Hp`, `Sp`, `BaseExp`, `JobExp`, `MvpExp`. Every declaration has ten entries,
including absent ones:

- `occurrences`: every exact top-level key match in mapping order, with
  `field_ordinal`, the key record (marks, byte span, span hash, text, style) and the
  value record. A scalar value has full decoded `text`, `style` and `null`; a
  container has kind, marks, span, span hash, ordered semantic fingerprint and node
  count, never its body.
- `role`: the first is `selected_first` (rapidyaml `find_child`), later ones are
  `ignored_duplicate`. No dict last-wins conversion. An invalid later duplicate
  never blocks a valid first one, and a valid later one never rescues an invalid
  first one.
- `case_variant_keys`: keys that match only case-insensitively (`id`, `NAME`).
  They are not aliases and not counted as present.
- `selected`: `absent`, `null` (plain `''`, `~`, `null`, `Null`, `NULL`),
  `container`, `supported` or `unsupported`.

**Numeric subset.** Nonempty ASCII `[0-9]+` within the target width (Id, Hp, Sp:
uint32; Level: uint16; EXP: uint64). The full decoded text of plain, quoted and
block scalars is used without trimming or YAML coercion. Leading zeroes stay in
provenance and convert as decimal. Conversion strips zeroes, compares length and
lexical order against the maximum, then converts at most 20 digits; arbitrary
long text is never passed to `int`. Everything else is a projection-policy gap
with a reason: `empty_text`, `whitespace`, `sign`, `base_prefix`,
`non_ascii_digit`, `decimal_overflow`, `other_text`. c4 natively accepts other
bases and may wrap overflow; this is not emulated.

**Name bytes.** The selected non-null text (quoted, plain or block, including an
empty string or a quoted `"null"`) is encoded as UTF-8. `stored_bytes_hex` is the
authoritative 48-character lowercase hex of `raw[:24]` plus NUL padding to 24
(`std::string::resize(NAME_LENGTH)`, `NAME_LENGTH = 23 + 1`). `utf8_length` is the
original byte length; `truncated` and `warning` are true only above 24 bytes
(exactly 24 is neither). There is no clip at 23, no character-wise clipping, no
Unicode normalization, embedded NULs from escapes are kept, and a split multibyte
sequence is flagged (`multibyte_split_at_limit`) rather than decoded. No text
preview is emitted. This is the stored prefix under this parser profile, not a
rendered label or an asset path.

## Id stage and conditional branches

`id_stage` follows mob.cpp:5025–5031: missing or plain-null Id is a known
`known_return0`; supported decimal outside 1001..3998 and 20021..31998 is
`known_range_failure` (no find, name or default mutation); container or
unsupported text is `unresolved` (a projection gap). Only `gate_passed`
reaches `find`.

Each declaration then has `if_existing` and `if_fresh`, both conditional on the
inherited graph and the Id gate. Neither is selected from earlier declarations:
there is no membership map, and a later same-Id row stays conditional because
this child cannot know whether an earlier fresh object reached insertion.

Operation order follows C++, not YAML:

| Step | if_fresh | if_existing |
| --- | --- | --- |
| mandatory | `AegisName` and `Name` **presence** before any conversion/write (mob.cpp:5036–5038); presence does not imply convertible text | — |
| construct | temporary object, `id`, `vd.look[LOOK_BASE]`, constructor defaults (names empty, lv 1, max_hp 1, max_sp 1, EXP 0) | — |
| names | provided → 24-byte write; absent `JapaneseName` copies the resized `name` | provided → write; absent → prior bytes retained (even if `Name` changed) |
| Level/Hp/Sp | supported → declared value assigned (zero allowed); absent → constructor value retained | supported → assigned; absent → prior value retained |
| EXP | `rate_dependent_assignment`: declared uint64, rate name and expression; **no stored value is computed** | same |
| later | `later_parser_unchecked` (mob.cpp:5143–5574) | same |
| put | conditional on all later parsing succeeding (mob.cpp:5576–5577) | not applicable: shared storage |

Each operation has a `reachability`: `reached`, `not_reached_after_return0`,
`unresolved_after_gap` or `not_reached_id_stage`. Unreached operations carry no
effect; field observations stay in `fields`. A reached plain null returns 0
before that field's assignment. In `if_existing` the earlier writes survive and
are listed in `earlier_writes_survive`; in `if_fresh` the temporary object is
discarded (`not_reached_temporary_object_discarded`, or
`not_reached_no_object_constructed` for a mandatory failure). A gap stops the
certain sequence; later fields stay catalogued with no claim that native
execution reached them.

Every declaration also records `projection_gaps` (which block `complete`) and
`excluded_by_design`: membership unresolved, later parser state per branch,
insertion state per branch, EXP runtime value not computed, native row acceptance
not certified.

## Output records

- `monster-declarations.jsonl`: `projection_ordinal`, the unchanged complete
  `raw_declaration`, the ten `fields`, `id_stage`, `branches`, `projection_gaps`,
  `excluded_by_design`, `projection_status` (`modelled` or `gap`). Canonical JSON
  (sorted keys, ASCII escapes), original order.
- `monster-id-history.jsonl`: one entry per supported decimal first Id, sorted
  numerically, including out-of-range Ids with `source_gate`. Every declaration
  reference in original order carries projection/global/database/local ordinals,
  visit, epoch, file and hash, row span and hash, fingerprint and the Id
  occurrence's text, style, span and hash. Missing/unsupported Ids appear only
  in declaration records and manifest counts. It is a declared-Id history index,
  not one accepted entity per Id.
- `monster-projection-manifest.json`: generator, selected tool bytes, reader,
  parser and profile identity, the fresh snapshot identity, the verified
  prerequisite file hashes and relationships, fixed pins, source hashes and rules,
  MOB visits with epochs and the Clear history, both record files (size, lines,
  hash, read back), counts, per-file parser attempts and work usage (unknown
  totals stay null), stop, unresolved suffix, diagnostics, limits, exclusions and
  measured `timings_seconds` (these vary between runs; everything else is
  deterministic).
- `monster-projection-complete.json`: binds the manifest hash, version, status and
  both record hashes; written last and only for `complete`.

Counts separate absence from null, duplicates from first lookup,
supported/out-of-range/unsupported Ids, declared values from conditional
operations, and projection gaps from permanent exclusions. There is no accepted,
effective or merged monster count.

## Limits and publication

Parser limits are the selected `LIMITS` (16 MiB input, 1 MiB scalar, depth 64,
2,000,000 nodes per file and 8,000,000 total, 20 s CPU, 30 s wall, 192 MiB stdout,
64 KiB stderr). At most three MOB files are parsed, one at a time, each once;
failed attempts keep exact observed work and null unknown totals, and there is no
retry. Projection caps: 100,000 declarations, 1,000,000 target occurrences,
256 MiB declarations, 64 MiB history, 16 MiB manifest, 10,000 diagnostics, 16 MiB
raw line. Writers reserve bytes before each write; counts, diagnostics and history
advance only after a record is written. Caps are refusal policy, not native
behaviour. **There is no hard memory bound**: Psych builds its AST before
node/scalar checks, and the snapshot reader keeps all verified bytes.

The output parent must exist, be owned by you and not be group/world writable. The
output is an exclusive `mkdir` at 0700, refusing existing files, directories,
live or dangling links and FIFOs. Files are created exclusively, no-follow, at
0600, and each is read back through a no-follow descriptor (owner, mode,
identity, size, SHA-256). The directory must then hold only this run's files,
and its final close is part of publication. On an ordinary failure after the
marker exists, only this run's marker inode in the reserved directory is
removed; a replaced marker or directory is preserved and reported, and a cleanup
failure is reported. Partial records/manifest may remain without the marker:
inspect and delete them before retrying. A same-user concurrent writer could
still race between steps.

Rollback: revert the source commit. Deleting a verified owned output directory is
a separate step. No installed state, save or database is touched.

## Tests

`test_monster_projection.py` builds real selected catalogs over small authored
fixtures (the unchanged `yaml_graph_inventory.publish` with the real Ruby
adapter), re-pins them, and projects them. It covers Id boundaries
1000/1001/3998/3999/20020/20021/31998/31999; integer width limits, zeros,
leading and very long zero text, and no unbounded `int`; sign, base, whitespace,
non-ASCII and superscript digits and overflow as gaps; absent, plain null, quoted
null, quoted empty, block scalars and containers; duplicate first lookup in both
directions; exact key case; all ten occurrence histories; fixed parser order
against reversed YAML order; name lengths 0/short/24/25, NUL padding,
composed/decomposed text, multibyte split, escaped NUL; fresh mandatory presence
before any write; JapaneseName copy versus retention; existing earlier writes
surviving a later null or gap versus a discarded fresh object; absent/constructor
/prior separation; zero values; declared EXP without a computed stored value; and
malformed later fields staying unchecked.

Provenance tests cover MOB-only selection after an ITEM root, the same Id across
repeated visits and a Clear epoch without merging, the repeated file parsed
once, unchanged raw rows, Unicode/CRLF key/value/row spans, nested duplicate
keys, a tampered row detected as a provenance stop, and refusals for swapped,
missing, extra or non-canonical lines, marker/manifest/records relationship
tampering, wrong generator, adapter, profile, snapshot or reader identity, wrong
visit hash or epoch, every wrong pin, an extra file, a missing marker, a symlink
or FIFO record file, a linked catalog directory and the line cap. Parser tests
cover a mid-graph parser stop with unknown work and no retry, a node budget,
projection caps, child setup failure with the child reaped, the parser identity
refusal and selected-tool byte checks. Publication tests cover private
deterministic output, existing destinations (file, directory, dangling link,
FIFO) and unsafe parents, readback tamper, a real final directory-close failure,
a replaced foreign marker while the old inode is kept open, owned-marker removal,
cleanup failure and unexpected errors. The CLI test checks there is no pin,
profile, parser or source option.

The actual-input test runs a fresh CLI and re-derives every declaration from the
actual inputs: every raw row equals the catalog's MOB rows, every key and value
span hashes to the snapshot bytes, occurrence counts match the raw field list,
every name hex is recomputed, every supported number equals its text, no EXP
stored value exists, and the history and manifest/marker hashes match.

## Actual result

Recorded in the [attempt report](#attempt-report) at the end of this file.

## What this is not

Not native rapidyaml parity, c4 numeric conversion, full-row parsing, accepted or
merged membership, final object values, a positive native load return,
loadingFinished/rates/status calculation, runtime EXP, spawned or visible
monsters, rendered names or sprite paths, Traditional-Chinese quality, episode or
playable coverage, or user acceptance.

## Attempt report

Independent Claude attempt, Task `task_f8feb6bbdd2c`, Dispatch `ctx_13c1bfb24ae2`,
branch `ShemYu/t06-002-003-002-claude`, common base
`47fa08ea8d5d6ddfe61d31cbc84e7de679ef3de5` (brief SHA-256 `d945287f…8699`
checked). This is a worker candidate, not coordinator verification or acceptance.

Fresh actual CLI (`monster_projection.py` SHA-256 `bda979b2…a71e`), output under the
ignored attempt root `.tools/renewal/T06.002.003.002/actual-1`: exit `0`,
status `complete`, real 4.35 s (manifest timings: snapshot 0.127 s, prerequisite
1.198 s, projection 2.765 s, history 0.044 s; these vary).

| File | Bytes | Lines | SHA-256 |
| --- | --- | --- | --- |
| `monster-declarations.jsonl` | 40733741 | 2699 | `32e88cbf8111be5be17739ca7170bd8f1568b6bba0edbb14c84582c73ceebcb4` |
| `monster-id-history.jsonl` | 2135829 | 2699 | `def51761c55bdcaa68e9b9b30eeeead37d23d74e682dedfa9e6fb89399be9075` |
| `monster-projection-manifest.json` | 20320 | — | `65797c3e17f50a4864d2cc0602011ea323e13f2fd4d1bb87287f9a0bd6437e89` |
| `monster-projection-complete.json` | 601 | — | `ede44379286dd49e174ccbc43ebeb250d0c3fab56e49c6eb1b2bdeb33a3c9928` |

Relationships checked after the run: the marker binds the manifest hash and both
record hashes; the manifest binds both records (size, lines, hash, read back), the
generator source hash equals the committed tool bytes, the selected tool and
reader hashes, the fresh snapshot identity (`79ee4eff…1dbd0`, 1683 files,
68752782 bytes), parser 2.6.10/3.1.0/0.2.1 with adapter `1d60171e…b80f`, and the
three prerequisite files at their pinned sizes and hashes. The derived MOB
selection equals the canonical one: visits 9, 10, 11; 2699 rows; ordinals
30991–33689; epoch 0; no Clear. Three parser attempts (26, 242427 and 9 exact
nodes, 242462 total), no unknown totals, no stop, nothing unresolved, no
diagnostics.

Actual projected counts (raw declarations, not entities): all 2699 Ids are
supported decimal and pass the source gate; 2699 distinct in-range declared Ids,
none declared twice, none out of range; both branches `prefix_modelled` for every
declaration; no projection gaps, no duplicate top-level target keys and no case
variants.

| Field | Present / absent | Observations |
| --- | --- | --- |
| AegisName | 2699 / 0 | all under 24 bytes, NUL-padded |
| Name | 2699 / 0 | 45 exactly 24 bytes, 2654 under, none truncated; 2 with non-ASCII stored bytes |
| JapaneseName | 353 / 2346 | 1 exactly 24 bytes, 352 under |
| Level | 2695 / 4 | 41 zeros |
| Hp | 2683 / 16 | 103 zeros |
| Sp | 389 / 2310 | 349 zeros |
| BaseExp / JobExp / MvpExp | 1736 / 1738 / 121 present | declared uint64 only; stored values not computed |

These agree with the committed preparation distributions, which are only an
aggregate cross-check. They do not replace the coordinator's comparison of every row.

Tests (`test_monster_projection.py` SHA-256 `1bf12b04…c8ae`):
`python3 -I -m unittest discover -s tools/renewal -p test_monster_projection.py`
ran 39 tests, OK, with 1 skip (the actual-input test without variables). With
`T06_MONSTER_SNAPSHOT` and `T06_MONSTER_RAW_CATALOG` set to the two read-only
inputs (and `-W error::ResourceWarning`), it ran 39 tests, OK, with no skips, in
11.8 s. That test makes its own temporary fresh output and re-derives every
declaration. A scratch mutation check (copies outside Git, not committed) changed
the tool nine ways: clip at 23, last-wins lookup, inclusive Id range, no fresh
mandatory check, copying JapaneseName in existing, no canonical-line check, no
row comparison, quoted null as null, and a computed EXP value. The suite failed
for every mutation. The canonical-line case was caught only after a test was
added for it.

Limitations: the actual input exercises only the all-supported path (no gaps,
duplicates, Clear or repeated Ids). Those paths are covered by authored fixtures
only. Psych is not rapidyaml; c4 bases/overflow are not emulated; there is no
hard memory bound. An earlier smoke output from a pre-final revision,
`.tools/renewal/T06.002.003.002/smoke-1`, is superseded and has not been deleted.
Provider/model: Claude Opus 5.5 (`claude-opus-5-5`); effort, tokens and cost were
not observed. Next owner: root, for independent verification of both submissions.
