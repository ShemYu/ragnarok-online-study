# Stock map-index/cache reconciliation (T06.002.002)

`map_cache_inventory.py` takes the canonical T06.001 snapshot and the canonical
T06.002.001 selection and publishes, for every configured map occurrence in its
original order, whether the rAthena map server at the pinned source revision
would keep it after map-index and map-cache reading with `use_grf` off. Python 3
standard library only. It builds and runs nothing from rAthena and reads no
installed app, VM, SQL, browser or network state.

```sh
python3 -I tools/renewal/map_cache_inventory.py \
  /abs/path/to/.tools/renewal/t06-candidates/integrated-2 \
  /abs/path/to/.tools/renewal/t06-selection-candidates/integrated-1 \
  .tools/renewal/T06.002.002/output
MAP_CACHE_SNAPSHOT=/abs/path/to/integrated-2 \
MAP_CACHE_SELECTION=/abs/path/to/integrated-1 \
  python3 -I -m unittest discover -s tools/renewal -p test_map_cache_inventory.py
```

The pinned-input test runs only when both variables hold absolute paths to
existing directories and is reported as skipped otherwise. There is no option
that bypasses a pin; lower-level routines take synthetic fixtures for tests.

```
output/                       0700, new
├── map-cache-manifest.json   0600, deterministic, written and read back first
└── map-cache-complete.json   0600, written last: manifest SHA-256, status, version
```

Exit `0`: published, `status: complete`. Exit `1`: published, `status:
incomplete` (unsafe cache data, see `caches` and `unresolved_unsafe`
candidates). Exit `2`: input, profile or publication refusal; nothing is
claimed. Without `map-cache-complete.json` the output is not a result.

## Input checks

- Snapshot: the unmodified `server_selection.read_snapshot()` with its default
  pins (manifest SHA-256 `79ee4eff…41644c1dbd0`, 1683 files / 68752782 bytes,
  exact file set, every size and hash, no links or special files).
- Selection directory: exactly `selection-manifest.json` (953299 bytes,
  `d62e31fd…631aec9a`) and `selection-complete.json` (185 bytes,
  `26b9e804…bb197`; full pins are in the code), both regular files read
  without following links. The completion record must bind the manifest hash;
  the manifest must be `status: complete`, from `server_selection.py` 1.0.1
  (source `22a3f4c8…3c24417`), name the same snapshot hash/counts and the explicit
  Renewal profile. Candidate order and `file`/`line` provenance are kept.
- Profile: the final effective `db_path` must be `db` (not truncated) and the
  final `use_grf` must be the integer 0. Any other value, including nonzero
  `use_grf` (the GRF branch, `map_readgat`), is refused as unsupported; caches are
  not applied to it.

## Modelled source behaviour (rAthena `0693b8c`)

Source file hashes and line references are recorded in the manifest `source`.

**Map index** (`mapindex.cpp:131-178`). `db/map_index.txt` (missing: fatal
refusal) then `db/import/map_index.txt` (missing: warning, stop). Each file is
cut into `fgets(1024)` chunks: at most 1023 bytes including the newline, so an
overlong physical line becomes several chunks, each handled as a line (a
continuation chunk starting with `//` is skipped). Only chunks starting with `//`
in column zero are comments; nothing is stripped inline. `sscanf("%11s\t%d")` is
modelled byte for byte: skip C white space (space, tab, LF, VT, FF, CR), take up
to 11 non-space bytes, let the `\t` directive match any white space including
none, then a signed decimal prefix. So `abcdefghijk7` is `abcdefghijk`/7, `x010`
is one conversion, `x 010` requests 10, `x 0x10` requests 0. One conversion
requests `last_index+1`; two use the scanned value; the caller's `last_index`
always becomes the requested value, rejected or not. `-1` searches `[1,
max_index)` for an empty slot and otherwise uses `max_index` (1 at start).
Valid IDs are 0..1999; other values and names empty after normalisation are
rejected. Storing into an occupied slot removes the old name from the reverse
map before adding the new name, so `A/1, A/2, B/1` leaves slot 2 = `A` with no
reverse `A`. Only insertion grows `max_index`. ID 0 can be stored, but the later
lookup treats it as false.

**Name normalisation** (`mapindex.cpp:24-41`). `strnlen` to 16 (16 becomes 15),
case-insensitive `.gat` tail compared against the whole remaining string, clip to
11, case kept. The index lookup normalises the already-normalised candidate name
again, so a candidate `Foo.gat` (from `Foo.gat.gat`) compares to cache name
`Foo.gat` but looks up index name `Foo`.

**Map cache** (`map.cpp:3688-3731, 3927-4009`). Files are hardcoded, whatever
`db_path` is: `db/import/map_cache.dat`, `db/re/map_cache.dat`,
`db/map_cache.dat`. A missing file is logged and skipped. Layout assumption
(source profile, not attestation of the installed binary): little-endian,
native alignment, header `<IH2x` (8 bytes), entry `<12shhi` (20 bytes) followed by
`len` zlib bytes. Within one file the first exact, case-sensitive name match
wins (no `.gat` stripping). Nonpositive `xs`/`ys` or `xs*ys > 262144` makes that
file's lookup fail and the next file is tried, never a later duplicate in the
same file. `1×1024` is valid.

**Reconciliation** (`map.cpp:3970-4009`). For each candidate in order: cache
attempts first, then index lookup; missing or zero ID, or no successful read,
discards the occurrence (`discarded_not_found`, with reasons); an ID already
accepted discards it (`discarded_duplicate_index`, with the earlier ordinal);
otherwise it is `retained` with its compacted `slot`, cache file/ordinal and ID.
Every candidate keeps its original `ordinal`, `raw`, `config_file`,
`config_line` and every cache attempt.

## Strict validator policy (not performed by the C++ code)

The C++ code ignores `decode_zip`'s status and decoded size and performs no
bounds checks. The tool never invents a native result for data it cannot vouch
for:

- File: the header must fit; `file_size` must equal the length; padding bytes
  must be zero; every entry header and payload must be inside the file with
  `len >= 0`; the last entry must end exactly at end of file.
- Name: a NUL within 12 bytes, printable ASCII, zero bytes after the NUL.
- Payload, for every entry with valid dimensions (used or not): decoded one at a
  time with output capped at `xs*ys+1` and no flush; the zlib stream must end
  with a valid checksum, consume all input, have no trailing data, and yield
  exactly `xs*ys` bytes. Compressed and decoded SHA-256, dimensions and a raw
  cell histogram are recorded; payloads are never copied out.
- Cell values 0..6 are recognised; others are counted as unknown cells (the
  source warns and uses zero flags) without failing the record.
- Work limits: 65536 index chunks, 65535 records per file and in total, 512 MiB
  aggregate decoded output, 65536 candidates. Exceeding one is a refusal.

A structural or name rule failure makes the whole file `unsafe`; a candidate
whose attempt reaches it, or reaches a bad name, is `unresolved_unsafe`. A
payload failure is unsafe for that record; a candidate matching it is
`unresolved_unsafe`. Either makes `status: incomplete`. These are policy
refusals, not source-proven removals. Conservatively, a file broken only by
policy (for example trailing bytes) also leaves names found before the defect
unresolved.

## Output

The manifest holds generator version and source hash, the snapshot verifier
hash, every input pin, profile, source rules, exact reads with hashes, every index
event with file/line/chunk/offset, requested and resolved IDs, replacements and
rejections, the final `last_index`/`max_index`/forward/reverse state, the cache
catalog in file order, ordered candidate dispositions, summary counts,
diagnostics, validator policy, work limits used and `not_checked`. No
timestamps, absolute host paths, credentials or payload/script bodies.

## Publication safety

The parent must exist, not be a link, be owned by you and not be group/world
writable. The target is created with an exclusive `mkdir(0700)`, which refuses an
existing file, directory or live/dangling symlink and leaves it unchanged. Files
are created `O_EXCL|O_NOFOLLOW`, `0600`, fsynced and read back by descriptor; the
completion record is written only after the manifest is verified, and the
directory must then hold exactly the two files. On failure, a completion record
this run created is removed; if removal fails the error says so and the output
must be treated as failed. A partial directory without a completion record is
left for inspection. Another process running as the same user can still race
between steps; treat any output without a valid completion record, or whose
manifest hash differs from it, as failed.

## What this is not

A source-profile disposition per configured occurrence. Not a runtime load
result, installed-binary attestation, client map/render check, NPC/monster/quest
or playability check, episode definition or coverage claim, and it models only
the Renewal `use_grf 0`, `db_path db` branch.
