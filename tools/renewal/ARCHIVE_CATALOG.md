# Pinned raw GRF table catalog (T06.003.001)

`archive_catalog.py` verifies the pinned client inputs and the three acquired
archives and publishes every raw file-table record of `event.grf`, `data0.grf`
and `data.grf`, in that pinned order and in table order. It follows RemoteClient
`src/grf.rs` and `src/des.rs` at the pinned revision and reads source only. Python
3 standard library only. It builds and runs nothing from RemoteClient. It does not
touch the installed app, game, VM, SQL, browser or network, and it never reads,
decrypts or decompresses an entry's payload.

```sh
python3 -I tools/renewal/archive_catalog.py \
  /abs/path/to/.tools/renewal/t06-client-inputs \
  /abs/path/to/.tools/renewal/assets/tw-20260409/app \
  .tools/renewal/T06.003.001/catalog
T06_CLIENT_INPUTS=/abs/path/to/.tools/renewal/t06-client-inputs \
T06_ARCHIVE_ROOT=/abs/path/to/.tools/renewal/assets/tw-20260409/app \
  python3 -I -m unittest discover -s tools/renewal -p test_archive_catalog.py
```

The actual-input test runs only when both variables hold absolute paths to
existing directories. Otherwise it is reported as skipped. No option bypasses a
pin. Lower-level routines (`parse_header`, `plan_table`, `inflate_table`,
`modern_records`, `legacy_records`, `catalog_archive_bytes`) take small
in-memory synthetic fixtures for tests.

```
catalog/                         0700, new
├── event.grf.records.jsonl      0600, one raw record per line, streamed, read back
├── data0.grf.records.jsonl      0600
├── data.grf.records.jsonl       0600
├── catalog-manifest.json        0600, deterministic, written and read back after them
└── catalog-complete.json        0600, written last: manifest and record-file SHA-256s
```

Exit `0` means published with `status: complete`. Exit `2` means refused. The
error names its category: `input_pin`, `source_rejection`, `validator_refusal`,
`unsupported`, `output` or `unexpected`. A refusal never leaves
`catalog-complete.json`. Any record files already written stay, together with a
best-effort, path-free `catalog-failed.json`. Treat that directory as failed:
inspect it, then delete it before retrying.

## Input checks

- The input directory, opened without following links, must hold exactly
  `DATA.INI` (453 bytes) and `archive-input-manifest.json` (2358 bytes). Each is a
  regular file read through a no-follow descriptor and must match its SHA-256
  pin. DATA.INI is only hash-checked. It is never parsed, echoed or copied,
  because it contains host paths.
- The manifest must bind that DATA.INI size and hash. Its `ordered_basenames`
  must be exactly `event.grf`, `data0.grf`, `data.grf`. Its archive list must
  carry the three pinned names, sizes and hashes, and its INI bindings must name
  the same acquired files. After parsing, each archive's header facts (signature,
  header hash, declared/effective version, record count, table start) must agree
  with the manifest.
- The archive root and each archive are opened without following links. Each
  archive must be a regular file of its pinned size. The header (and, for modern
  layouts, the 8-byte table header) is read and planned first. Then one sequential
  pass hashes the whole file and captures the header and the stored table range.
  Only those captured bytes are parsed. The pass must match the SHA-256 pin and
  the early header reads. Device, inode, size, mtime and ctime must be unchanged
  afterwards, and the path must still name the same regular file. Memory holds one
  table plus small buffers. The 2 GB archives are never buffered whole.

Input identity is separate from the installed loose/cache/override state. That
state is not read.

## Modelled source behaviour (RemoteClient `66ba94e`)

| Source | SHA-256 |
| --- | --- |
| `src/grf.rs` | `4646514140bc7688bbc91e0bac7d1ee9a83aab5e1e17df20c1eb30668bd5edf5` |
| `src/des.rs` | `8f0189340eab708993a493ff7300d08e0151a3c8c539a046656f3e350e01856f` |
| `src/encoding.rs` | `0014c18c2ab7211b68b8dff84c66b5bbd0aa3bb68593bca2bd5e46b28973c9ad` |

- Header (grf.rs:167–239). The header is 46 bytes. The signature is
  `bytes[0..15]` up to the first NUL and must equal `Master of Magic` or
  `Event Horizon`. Bytes after an `Event Horizon` NUL are ignored but kept as
  `signature_field_hex`. The version is u32@42.
  - 0x1xx and 0x200: offset = u32@30 + 46, count = max(u32@38 − u32@34 − 7, 0).
  - 0x300: offset = (u32@34 << 32) + u32@30 + 46, count = u32@38, then a 4-byte
    skip before the table.
  - A 0x300 header whose high word >> 8 is not 0 is read as 0x200, using that
    layout, count and version. Its provenance is recorded.
  - A count above 500000 is rejected.
- Implemented versions: legacy 0x102 (the actual archives) and 0x200/0x300. The
  source also accepts the other 0x1xx versions with the same layout. Those are
  refused as `unsupported` because this child neither implements nor verifies
  them. Any other version is a source rejection.
- Tables (grf.rs:484–551).
  - Legacy: the table runs from the table position to EOF. It must be non-empty
    and at most 512 MiB.
  - Modern: compressed/real u32 sizes followed by zlib. Zero sizes, a real size
    above 512 MiB and a range past EOF are rejected.
- Modern records (grf.rs:266–327). Each record is the name bytes up to NUL, then
  compressed/aligned/real u32, a kind u8 and a u32 offset (0x200) or u64 offset
  (0x300).
  - The tool reads exactly the declared count. A name without a NUL, or entry data
    cut short, is a source rejection.
  - Leftover table bytes are not rejected. Their length and hash are recorded.
  - Kind 0 with real_size > 0 and compressed == real is promoted to kind 1. Both
    kinds and the promotion are recorded.
- Legacy records (grf.rs:334–455).
  - The full u32 block length places the metadata at p+4+len. The name length is
    the low byte minus 6, saturating at 0. The name starts at p+6, and every slice
    is bounded first.
  - Each 8-byte block that starts below the name length and fits before the
    metadata is nibble-swapped, then given its own one-round transform. Names
    longer than 20 blocks are therefore fully decoded. A trailing block that does
    not fit stays as stored.
  - The clear name runs to the first NUL in the derived length, or covers the
    whole derived range if there is none (grf.rs:418–421).
  - Lengths: compressed = u32 − real − 715 and aligned = u32 − 37579, in signed
    arithmetic. An underflow clears the file bit, clamps the size and keeps the
    name.
  - Otherwise, file entries gain header encryption (4) for case-insensitive
    `.gnd/.gat/.act/.str` and mixed encryption (2) for any other or no suffix.
    This only sets flags. Payloads are not decrypted.
- Block transform (des.rs:100–179). The transform is IP, one round (expansion, 4
  S-boxes, P transposition, XOR into the left half), then FP. It uses lookup
  tables built from the source's constant tables.
  - Literal checks: raw `0000000000000000` → `0404015555015455` (one round and
    filename decode). Raw `0123456789abcdef` → `5176057698ead9eb` (one round) and
    `4067146789fbc8fa` (nibble swap, then one round).
  - Tests also compare 500 random blocks with an independent bit-loop
    reimplementation.
- Metadata filter (grf.rs:573–579). An advertised real_size above 256 MiB is
  filtered first, then a missing file bit. Bad name bytes are kept. Eligibility is
  not key reachability, requestability or payload readability.

## Native rejections versus strict policy

The source decompresses its table with an unbounded `read_to_end`. It surfaces
decompression errors and a final size mismatch as `CorruptTable`
(grf.rs:535–548), so this tool reports both as **source rejections**. An overlong
stream is stopped early by the output cap and reported as that native size
mismatch. This follows the coordinator's identical clarification to both workers,
which narrows brief section 3.

The following are **validator refusals**, stricter than the source:

- Output is capped at the declared real size + 1, with no flush.
- A stream that yields exactly the declared bytes must also reach its end, with
  complete framing and checksum.
- No trailing compressed bytes may follow the stream.
- The compressed table must stay within 512 MiB.
- Each record file must stay within 1 GiB, and all three archives within 1.5M
  records in total.

## Output

Each JSONL line has `archive`, `archive_sha256`, `ordinal` and `table_offset` (a
legacy line also has `archive_offset`), plus `record_bytes`, `name_hex`,
`name_length`, `name_terminated`, `original_kind`, `effective_kind`,
`compressed_size`, `length_aligned`, `real_size`, `payload_offset_field` and
`metadata_filter`. It also has a diagnostic `diagnostic_body_range` (offset + 46
to + aligned), with an in-archive flag that is arithmetic only. Format-specific
fields:

- Modern: `kind_promotion`.
- Legacy: `block_length` and `block_low_byte`, plus
  `derived_name_length`, `name_start`, `metadata_offset`, the encoded region/name
  sizes and SHA-256s, and `transformed_blocks` and `untransformed_name_bytes`.
  Also the raw `size_field`/`aligned_field`, the signed derived lengths,
  underflow flags and `header_encryption_flag`.

The manifest holds:

- the generator version and source hash, and the input, archive and source pins
- the source rules, profile and assumptions, unsupported boundaries, validator
  policy and exclusions
- per archive: the header fields, declared/effective version and provenance
- per archive: the table stored/compressed/real sizes, hashes, consumed and
  trailing bytes
- per archive: counts of raw records, metadata-eligible records, filter reasons,
  original/effective kinds, effective flag bits, promotions, underflows,
  unterminated/empty/high-byte names and duplicate raw names
- each record file's size, line count and SHA-256
- the work limits and usage

It never holds table bodies, payloads, raw INI content or host paths. Raw filename
hex is the intended ignored inventory.

## Publication safety

The output parent must exist, be a real directory owned by you and not be
group/world writable. The target is created with an exclusive `mkdir` (0700), so
an existing file, directory, or live or dangling symlink is refused unchanged.

Files are created with `O_EXCL|O_NOFOLLOW` (0600). Records are streamed and
hashed as they are written. Each file is then read back by no-follow descriptor
and checked for size, hash, mode and owner before the next step. The completion
record comes last. A directory listing must then show only files this run wrote.

On any refusal, I/O error or ordinary unexpected exception after the completion
record exists, that record is removed. If its removal fails, the error says so.
Foreign files are never removed. Reverting the source commit and deleting an
output directory are separate rollbacks. No installed or external state is
changed, so none needs restoring.

## What this is not

`status: complete` means only that the bounded raw catalog was produced. It does
not provide human filename spelling (CP949/UTF-8/Latin-1) or Unicode/path
normalisation. It does not settle duplicate-key precedence or merging across
archives, or a payload's readability or decryption. It does not cover installed
loose/cache/override state, rendering, maps, monsters, story, playability, the
episode or coverage. Raw-table agreement with another implementation does not
imply filename-codec or native-reader parity.
