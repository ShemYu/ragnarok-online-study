# October physical GRF inventory facade (T07.007.001)

Version **1.0.1** contains separately credited root corrections to the unchanged
selected Claude implementation integrated at `5d1140f`. The raw implementation's
successful census did not qualify its consumer or final publication guards.
Root corrections enforce the complete typed contract and final ownership/input
checks below. This attribution is not additional Claude/Grok benchmark credit.

`archive_inventory_october.py` inventories every physical file-table record of
the three October archives `data.grf`, `data0.grf` and `event.grf`. It is an
additive facade over the unchanged core `archive_catalog.py`. It reuses the
core's `read_archive`, `catalog_table`, `render`, `trusted_target`,
`_verify_published` and work limits, so it has no GRF parser of its own. It never
calls the core's INI-oriented `run`/`build_manifest` and never fabricates a
DATA.INI. It uses only the Python 3 standard library. It does not touch the
installed app, game, worlds, SQL, browser, network or host settings, and it never
reads, decrypts or decompresses entry payloads.

```sh
python3 -I tools/renewal/archive_inventory_october.py \
  /abs/path/to/inner-manifest.json \
  /abs/path/to/inner/app \
  .tools/renewal/T07.007.001/inventory
python3 -I -B -W error::ResourceWarning -m unittest discover \
  -s tools/renewal -p test_archive_inventory_october.py
T07_EXTRACTED_MANIFEST=/abs/path/to/inner-manifest.json \
T07_ARCHIVE_ROOT=/abs/path/to/inner/app \
T07_OUTPUT_PARENT=/abs/path/to/private/0700/dir \
  python3 -I -m unittest discover -s tools/renewal -p test_archive_inventory_october.py
```

The production test runs only when all three variables are set. Otherwise it is
reported as skipped. The CLI takes exactly three positional arguments and has no
pin, profile or core override. The fixed public profile
`docs/project/fixtures/T07.007.001-profile.json` is found relative to this
checkout, not the current directory. Tests use a private `_Contract` with a
synthetic profile through `_run` / `_verify_inventory`. Production code never
builds one from user input.

```
inventory/                         0700, new and exclusive
├── data.grf.records.jsonl         0600, core render_record lines, unchanged schema
├── data0.grf.records.jsonl        0600
├── event.grf.records.jsonl        0600
├── inventory-manifest.json        0600, deterministic ASCII, read back
└── inventory-complete.json        0600, written last; binds manifest and record files
```

Exit `0` means published and self-verified with `status: complete`. Exit `2`
means refused. Errors print `error [category]: message` to stderr, at most 1000
characters. Supplied paths are replaced by placeholders, and the only asset names
that can appear are the three archive basenames. Categories are `input_pin`,
`source_rejection`, `validator_refusal`, `unsupported`, `output`, `verification`
and `unexpected`. Success prints one JSON line with totals, record-file hashes and
manifest/completion hashes. That line contains no paths.

## Enumeration is not priority

The order `data.grf, data0.grf, event.grf` is the profile's fixed ASCII basename
order. It is **not** a client lookup priority. The manifest states
`lookup_priority: null`, `priority_status: "not_established"` and
`semantics.winning_archive: null`. Every physical record is kept in table order,
including duplicates within one archive and names that also appear in another
archive. `totals.cross_archive_shared_raw_names` and
`per_archive_shared_name_presence` count shared names. No winner is chosen. Names
are raw table bytes in hex, with no alias, filename codec, case folding or Unicode
normalisation. The reconciled tree has no loose `DATA.INI`
(`loose_data_ini_entries: 0`). That fact does not mean all client configuration
is absent.

## Input checks (all before archive body reads or output creation)

1. **Profile.** The profile is read without following links. It must be a
   regular, single-link file of exactly 3180 bytes with its pinned SHA-256. Its
   typed contract is checked next: exact keys, schema/task, enumeration order,
   null priority, core pin, integer (non-boolean) fields, layout-consistent
   nullable sizes, range arithmetic, GRF path list and record total.
2. **Core.** The core is read without following links as a regular, single-link
   file. It must match the profile's pin (54783 bytes). Those exact verified bytes
   are compiled and executed into a private module. The importable
   `archive_catalog` module is never patched or used.
3. **Extracted manifest.** The manifest is a single-link regular file that must
   match its pin. It must hold the profile's file and directory counts
   (4976 + 115 = 5091 unique entries). Every path must be safe and relative (no
   absolute path, `..`, empty segment, backslash or NUL), carry an exact typed
   key set and have a raw-hex path equal to its path. Every entry needs a directory
   parent. The `.grf` set (any case) must be exactly the three profile paths, each
   with the pinned size and hash, `single_link: true` and a matching reported
   prefix. No other file body is read or rehashed.
4. **Archive root metadata.** The archive root is opened without following
   links. Its listing must hold exactly three `.grf` entries of any case and kind,
   so an extra `.grf` is refused. The listing must also equal the manifest's
   entries directly below the archive directory, and each entry's kind and file
   size are checked by `lstat`. This refuses mixed trees, symlinks, FIFOs and
   other special files. Each archive must also be a regular single-link file
   (hard links are refused). The output must be new, below a parent you own that
   is not group/world writable, and outside the archive root.

## Archive reading

Each archive goes through the core `read_archive`. The core opens the file
without following links and checks its size. It plans the header and table, then
makes one sequential pass that computes the full SHA-256 and captures the header
and stored table from the same descriptor. The core checks identity before, after
and at the path. The facade also checks that the archive's `lstat` identity is
unchanged from examination to read. It then compares every frozen profile fact
with the parsed one: signature, header hash, versions, layout, record count,
table offset/pos/skip, stored range and modern compressed/real sizes.
**Range semantics:** for modern layouts the profile's `stored_start` is the start
of the compressed bytes. That is `table_pos + 8`, after the compressed/real u32
header, while the core plan's `stored_start` equals `table_pos`. Legacy tables
start at `table_pos` in both, and `stored_end` is the same in both.

The core `catalog_table` parses with all of the core's parsing, decompression and
record limits. The facade checks that the emitted ordinals are sequential and
that each archive's line count equals its header count. It also checks that the
total equals the profile's 248908. Usage keeps the core counters
(`archive_bytes_hashed`, `table_bytes_captured`, `records`, `record_file_bytes`)
and adds the manifest bytes read and the root entries examined. The total-record
and per-file byte limits come from the core `WORK_LIMITS`.

## Publication

- The output directory is created exclusively with mode 0700. Its identity is
  retained, and it must be private to you.
- Every file is created exclusively, without following links, with mode 0600.
  Writes are buffered and checked for progress, so a short write is continued and
  a zero or invalid write fails. Each file is fsynced and closed with checking,
  then read back by the core `_verify_published` (size, hash, mode, owner,
  identity).
  If writer construction fails after opening a descriptor (including `fstat`
  or `fchmod`), it closes that owned descriptor before propagating the failure.
- After the last archive the root descriptor is closed inside the transaction.
  The manifest is then published. Before the completion record, the facade
  rehashes the profile, core, extracted manifest and generator and compares their
  identities. It reopens the archive root, checks its identity, and checks every
  retained archive identity and that each is still single-link. The exact root
  entry set, kinds and sizes are reconciled again with the rehashed metadata,
  including refusal of any extra `.grf`. No archive descriptor is open at
  completion.
- `inventory-complete.json` is written last. After it, the output set must equal
  the created set, the path must still name the reserved directory, and the
  consumer gate runs over the published tree. **After** that consumer returns,
  the producer repeats input/source checks, then rechecks every created file's
  original device/inode, mode, owner, single-link status, size and full hash.
  Thus even a byte-identical different-inode completion replacement is refused.
  The output path must still identify the owned0700directory before and after
  its checked final close.
- **Failure:** the run removes a completion record only when it is the file it
  created (same device/inode). A foreign replacement is preserved. When the
  reserved directory can still be verified, a path-free `inventory-failed.json`
  is written, and it overrides any leftover completion. OS errors report only
  `strerror`, and unexpected exceptions report only the type name.

## Consumer gate

`verify_inventory(output)` is read-only. It returns the validated manifest or
raises `VerificationError`. It refuses a missing directory, a failure marker, a
missing or extra file, and any file that is not a private, single-link, bounded
regular file. It checks the completion record's exact keys and contract, then the
completion → manifest byte/hash binding and the canonical JSON form. It requires
the manifest's schema/task/status, its generator identity (this file's current
bytes), its core and profile pins and its extracted-manifest identity. It requires
the complete non-priority/source/policy/exclusion/work-limit contract. Limits
come from freshly verified unchanged core bytes, not from the output being
checked. All frozen header/table facts and the exact agreement key set must
hold. Reported raw header fields are checked with the unchanged core; this does
not reconstruct unreported header bytes or independently recalculate the frozen
header hash from them.

Every record line is streamed and checked, including its exact key set, strict
integer versus boolean/float types, raw name hex, contiguous ordinal/table
offsets, length/kind/promotion/encryption relations and diagnostic range. The
consumer recomputes per-archive summaries, cross-archive totals and cumulative
usage, and checks table consumption/trailing lengths and all file bindings.
Signed legacy underflows remain signed observations; diagnostic out-of-archive
ranges are not incorrectly rejected as native failures. A zero-byte record file
is valid when its declared count is zero. Duplicate JSON keys, nonfinite values,
extra fields and self-consistently rebound contract contradictions are refused.

The consumer retains every checked file identity, rehashes/rechecks current
profile/core/generator sources, and checks file bindings plus the directory's
current pathname, owner and0700mode at its final boundary. Its final path check
also occurs after directory close. It performs no writes. Finding a completion
record alone is never a pass.

Root-authored regressions use real synthetic files, rename-retained inodes,
late mode/input/set changes and constructor descriptor faults. They cover the
eight independently reproduced raw-candidate fault classes, both empty and
nonempty baselines, every-row typed validation and post-consumer checks. The
optional production test is not a synthetic-suite pass; root must separately
run a fresh actual CLI, audit all artifacts/records and establish April parity.

## Not covered

This inventory says nothing about lookup priority, a winning archive, filename
decoding, payload readability, maps, render, playability or full-game coverage.
Parent T07.007 map, dependency and runtime work remains open.

Checks are bounded observations, not an atomic guarantee against concurrent
same-user modification after the final check. Ambiguous close errors are fatal
and are not blindly retried on a potentially reused descriptor. A consumer with
only this output and the public profile cannot authenticate arbitrarily
rewritten, self-consistent raw names or opaque table hashes; independent full
record/artifact comparison remains root's separate evidence. The metadata root
entry count is bounded and reconciled to usage; it is not independently recovered
from the original metadata body by this output-only consumer. Producer admission
and final reconciliation do read and hash that exact metadata body. No original
archives or unrelated extracted bodies are opened by the consumer.
