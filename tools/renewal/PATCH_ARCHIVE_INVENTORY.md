# Patch GPF physical inventory facade (T07.007.007)

Version **1.0.1**, a separate root correction based on the selected independent Claude 1.0.0 candidate. See the [coordinator review](../../docs/project/reviews/2026-10-21-T07.007.007.md) for current verification and limitations. User acceptance remains separate.

`archive_inventory_patches.py` inventories every physical file-table record of the
28 selected patch GPFs listed in the frozen acquisition ledger. It is an additive
facade over the unchanged core `archive_catalog.py`
(54,783 B, SHA-256 `f785ced6…cdf15cda`). The facade verifies the core's exact bytes
and executes them into a fresh private module. It then reuses the core's
`read_archive`, `catalog_table`/`render_record`, `render`, `trusted_target` and
`_verify_published`. The consumer also uses `parse_header`, `Summary`,
`metadata_filter` and `header_encryption`. The facade has no GRF parser of its own.
It never calls the core's INI-oriented `run`/`build_manifest`/`read_inputs` and
never fabricates a DATA.INI. The October helper is not executed or imported, and the
manifest records `helper.executed: false`. The facade uses only the Python 3
standard library. It never extracts, decrypts or decompresses payloads. Opaque body
bytes are read only as full-hash input.

```sh
python3 -I -B tools/renewal/archive_inventory_patches.py \
  /abs/input-root/.tools/renewal/t07-007-007-frozen-input-1/input-manifest.json \
  /abs/input-root \
  .tools/renewal/T07.007.007/<run>/inventory
python3 -I -B -W error::ResourceWarning -m unittest discover \
  -s tools/renewal -p test_archive_inventory_patches.py
T07_007_007_INPUT_MANIFEST=/abs/manifest T07_007_007_INPUT_ROOT=/abs/root \
T07_007_007_OUTPUT_PARENT=/abs/private/0700/dir \
  python3 -I -B -m unittest discover -s tools/renewal -p test_archive_inventory_patches.py
```

The CLI takes exactly three positional arguments and has no profile, pin, core or
selection override. The fixed profile `docs/project/fixtures/T07.007.007-profile.json`
(101,983 B, SHA-256 `558363dd…19fff908681`) is resolved relative to this checkout, not
the current directory. Its descriptor is checked before its contents are trusted. Tests
use a private `_Contract` (synthetic checkout/profile, optional fault hooks) through
`_run`/`_verify_inventory`. The CLI never builds one.

## Admission (before any archive open or output creation)

1. Profile: no-follow ancestor walk, exact length/SHA, unambiguous finite JSON
   (duplicate keys and NaN/Infinity refused), full typed contract. The contract covers
   the 59-row ledger (2 already inventoried, 28 selected, 29 unresolved RGZ),
   enumeration order = selected ledger order, legacy 0x102 only, the zero-tail
   expectation, and totals that derive from the ledger. A bool is never an integer.
2. Core: exact bytes, then fresh `exec` into a private module; frozen limits checked.
3. Input manifest: profile pin, then exactly the seven required fields, each typed-equal
   to the profile (`ledger`, `source_evidence`, schema, task, basis, priority).
4. Input root and every ancestor are opened component by component with `O_NOFOLLOW`.
   Dot, dot-dot, relative and symlinked paths are refused. Only the parents of the 28
   selected rows are walked and retained as descriptors. Each storage file must be a
   regular single-link file of its ledger size, checked by `lstat`. The other 31 rows
   are never opened or examined.
5. Output: parent owned by you and not group/world writable, path absent, not inside
   the input root, then exclusive `mkdir 0700`.

## Inventory

For each selected row in ledger order, the downloaded `NN_<index>_<name>.gpf.body` is
passed to `core.read_archive` by its **storage basename** through the verified
parent descriptor. The parse uses the core's same-descriptor full SHA-256 and
header/table capture, with its single initial header `pread`. The identity is
compared before and after. Every frozen header and plan fact is reconciled
(signature, 46-byte hash, version/layout, offset/subtract/count words, table
start/end/bytes). `catalog_table` then receives the **original `.gpf` name** and full
SHA. Records are the core's `render_record` bytes unchanged. Table hashes,
consumption, tail and the full per-archive summary must equal the profile. A nonzero
tail is a `profile_mismatch` for this frozen corpus, not a general format rule.
Cross-archive distinct and shared raw-name counts are derived from the emitted rows,
then compared with the profile totals.

Bounds: the core keeps 500,000 records and 512 MiB of table per archive. The facade
adds 1.5 million **cumulative** records (not multiplied by 28), 1 GiB per record file,
2 GiB aggregate output and 4 MiB per JSON line. All of them are accounted before
writing. Exceeding a bound is a `resource_limit` failure, never a relaxation.

Before the manifest is written, every selected archive is **fully rehashed** through
its retained parent descriptor. Its identity is compared with the first read, not
with itself, and the root/parent chains are re-walked. Profile, core, generator and
manifest bytes and identities are rechecked before completion and again after the
consumer gate.

## Output

```
inventory/                    0700, new and exclusive
├── <index>.records.jsonl ×28 0600, unchanged core render_record lines (original GPF name)
├── inventory-manifest.json   0600, ro-patch-raw-inventory/1, canonical ASCII
└── inventory-complete.json   0600, written last; binds manifest bytes/SHA and record SHAs
```

The manifest binds:

- the task and the generator's bytes and SHA;
- the executed core identity, plus the non-executed helper pin;
- the profile and normalized-manifest pins;
- all 59 ledger rows and their dispositions (`opened` is true only for the selected rows);
- the enumeration basis/order, `lookup_priority: null` and `priority_status: not_established`;
- the core source rules, validator policy, input/publication rules and limits;
- for each archive: index, LF, source ordinal, storage path/basename, original name, URL,
  header, plan, table, profile agreement, counts and record-file pin;
- totals, work usage and the recheck lists.

The manifest stores no host paths or device/inode numbers.

Writes loop on legal positive short writes. Zero, negative or non-integer progress
fails, and EINTR is retried at most 16 times. Each file is fsynced, closed with
checking and read back. Directory membership, kind, link count, mode, identity and
all hashes are audited before and after the completion record. On failure the facade
removes only a positively verified owned `inventory-complete.json`. It preserves
foreign replacements and writes a path-free `inventory-failed.json` if the reserved
directory is still verifiable. That marker overrides any completion record. If the
marker cannot be written, the error says so and nothing claims completion. Exit `2`
prints `error [category]: …` (at most 1000 chars, paths replaced). The categories are
`input_pin`, `os_error`, `profile_mismatch`, `source_rejection`,
`validator_refusal`, `unsupported`, `resource_limit`, `output`, `verification` and
`unexpected`.

## Consumer

`verify_inventory(output)` is read-only and returns the validated manifest. It
refuses any of the following:

- a failure marker, or missing, extra, symlinked, hardlinked or special files;
- wrong modes or owner, or duplicate keys;
- non-canonical JSON or JSONL.

It re-reads the pinned profile, core and its own source. For every record it
type-checks every core field and recomputes the following relations rather than
trusting a rehashed chain:

- ordinal, table cursor and `archive_offset`;
- low byte, derived length, region, transformed and untransformed blocks;
- name termination and length;
- encoded-name SHA256 when zero blocks were transformed and the complete encoded
  prefix is known: an unterminated name, or a NUL exactly at the last derived byte;
- signed biases and underflows;
- kind, encryption suffix and filter;
- the diagnostic range.

The consumer then rebuilds the expected manifest from the profile, the recomputed
summaries and the cross-archive totals, and requires exact typed equality. Finally it
rechecks the source and output identities. It never opens archives and never imports
manifest-named code. Empty encoded ranges retain their existing exact hash checks.
Other encoded-region hashes remain bound observations. For a zero-block name the
consumer can hash the raw name, plus its NUL when that NUL is the last derived
byte. It does not invert transformed-name hashes or infer unknown padding after
an earlier NUL, and does not claim that hashes re-prove the original transformation.

## Tests (synthetic, private under `.tools/renewal/T07.007.007/`)

The test archives are literal authored legacy 0x102 GPFs. Names are encoded with an
independent bit-loop reference of the block transform written from literal tables and
checked against literal vectors. Expected records come from a literal dictionary and an
independent reference model. Non-selected ledger files exist with mode `000` to prove
they are never opened.

The controls cover:

- **Admission:** wrong profile, core or generator pins and the production profile
  against a synthetic manifest. Manifest variants: float, bool, extra or missing rows,
  a changed selection, a host key, duplicate keys and NaN. Profile variants: RGZ
  selected, unsupported version, nonzero tail, escape path, bool index, reordering.
- **Paths:** a symlinked root or parent; a symlink, hardlink, FIFO or directory in place
  of an archive; dot-dot or relative roots; existing output, output inside the root and
  an untrusted parent.
- **Archive changes:** a changed full hash; a replacement after admission; a
  modification after reading, caught by the rehash; header and tail profile mismatches;
  an unsupported version; a truncated record (source rejection).
- **Read faults:** at the core `os` boundary of a private module instance and at the
  facade's read indirection. A short initial header read keeps its honest refusal. The
  facade covers a zero-length streamed read, persistent and transient EINTR, and legal
  positive short reads, which must succeed.
- **Write faults:** positive short writes succeed. Zero, negative and bool progress
  fail, as do EIO and persistent EINTR. Further faults: fsync failure, close failure (no
  descriptor leak), readback growth, and failure-marker publication failure.
- **Publication:** an unexpected error after completion removes the owned marker. A
  foreign completion, an intruder file, a replaced directory and a replaced record file
  are all preserved and diagnosed.
- **Bounds:** the cumulative record bound across archives, the aggregate output bound
  and the line bound.
- **Consumer:** rehashed typed, kind, source, name, order, drop, duplicate, bias and
  extra-key forgeries; rehashed summary, totals, association, priority, ledger and
  helper forgeries; tree, mode and link refusals; source and profile changes; mutation
  during a read; and a read-only check.

The 1.0.1 regression adds two independently literal 139-byte archives: block8,
encoded region6, derived name2 and zero transformed blocks, with `A\0xxxx` and
`ABxxxx`. Each checks literal archive/name/region hashes, a full 28-archive baseline,
then a deliberately wrong encoded-name hash with the complete record/manifest/
completion chain rehashed. Verification must raise `VerificationError`, remain
read-only and retain the descriptor set. This defines the regression check;
the coordinator review records its execution result.

## Meaning and limits

Receipt-row enumeration is not publisher application order or client lookup
priority, and no duplicate is suppressed. A successful raw inventory does not prove
any of the following: RGZ grammar, patch installation, publisher order, payload
decoding or availability, maps, render, playability, full content, persistence, or
closure of the 82 old map gaps. The outer process-group guard used for the actual run
records sampled observations, not hard OS containment. Root alone compares every
record with its independent reference.
