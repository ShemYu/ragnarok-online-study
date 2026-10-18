# Four-root YAML graph and raw declaration catalog (T06.002.003.001)

Coordinator-corrected version `1.0.1`, based on selected Claude `573127d`.
Raw provider comparison and the coordinator's separate correction/verification
are recorded in [the task review](../../docs/project/reviews/2026-10-18-T06.002.003.001.md).
Corrections preserve full Id/Version text, cover child cleanup, qualify malformed
protocol, charge failed work with explicit unknown totals, and count only rows
successfully written. Source-only conditional graph; no native/entity acceptance.

`yaml_graph_inventory.py` verifies the canonical T06.001 snapshot and catalogs
the stock rAthena YAML import graph of `ITEM_DB`, `SKILL_DB`, `MOB_DB` and
`QUEST_DB`, plus every raw `Body` row those visits declare, in load order. It
follows `YamlDatabase::load` at rAthena `0693b8c69911d5ca42269684aa036b67d67f4d3e`
and reads source only. It uses the Python 3 standard library and the existing
`/usr/bin/ruby` (2.6.10, Psych 3.1.0, libyaml 0.2.1) through an authored
`Psych.parse_stream` AST adapter embedded in the tool. Nothing is installed,
built or executed from rAthena. It does not touch the app, game, VM, SQL,
browser, network or saves.

```sh
python3 -I tools/renewal/yaml_graph_inventory.py \
  /abs/path/to/.tools/renewal/t06-candidates/integrated-2 \
  .tools/renewal/T06.002.003.001/<new-output>
T06_YAML_SNAPSHOT=/abs/path/to/.tools/renewal/t06-candidates/integrated-2 \
  python3 -I -m unittest discover -s tools/renewal -p test_yaml_graph_inventory.py
```

The CLI takes only the snapshot and a new output directory. The profile, roots,
pins, parser and limits are fixed constants; there is no option to change them.
The actual-input test runs only when `T06_YAML_SNAPSHOT` is an absolute path to
an existing directory; otherwise it is skipped. Pure functions (`catalog`,
`publish`, `parse_yaml`, `run_child`) accept small alternate roots, profiles,
limits or adapter scripts for tests.

```
<output>/                     0700, new (exclusive mkdir)
├── raw-declarations.jsonl    0600, one raw Body row per line, streamed, read back
├── yaml-graph-manifest.json  0600, deterministic, written and read back after it
└── yaml-graph-complete.json  0600, only when status is complete, written last
```

| Exit | Meaning |
| --- | --- |
| `0` | published with `status: complete` (marker present) |
| `1` | published with `status: incomplete` (known fopen/Header failures) or `unsupported` (a stop); no marker |
| `2` | input or publication refusal: bad snapshot, wrong parser identity, unsafe/existing output, or a failure while publishing |

## Input and parser identity

- The snapshot is verified by the unmodified `server_selection.read_snapshot`
  with its default pins: manifest SHA-256 `79ee4eff…1dbd0`, exactly 1683 files and
  68752782 bytes, each size and SHA-256 checked, no links or special files. The
  reader's own SHA-256 is recorded. Graph paths are then looked up only in those
  verified bytes.
- Before the output directory is created, the adapter reports Ruby, Psych and
  libyaml versions; anything other than 2.6.10 / 3.1.0 / 0.2.1 is refused.
  Every parse result repeats and rechecks the identity.
- The adapter runs as `ruby --disable-gems -W0 -e <adapter>` with a two-entry
  environment (`PATH=/usr/bin:/bin`, `LC_ALL=C`), cwd `/`, the YAML on stdin.
  It calls `Psych.parse_stream` only: no `load`, `safe_load`, `to_ruby`, object
  construction, alias resolution or evaluation. It emits a flat preorder node
  list (kind, marks, scalar text/style, tag, anchor, child counts).
  Every operation after successful `Popen`, including selector setup and
  registration, is cleanup-protected. An unexpected setup/I/O/finalization
  error attempts kill, reap and independent closure of every pipe and becomes
  a qualified parser stop; interrupts clean up and then propagate. Cleanup
  failures are reported rather than converted to success.

## Source profile (`rathena-0693b8c-stock-renewal-yaml-four-roots`)

Assumed, not attested from an installed build or configuration: `db_path=db`,
`RENEWAL` and `RENEWAL_ASPD` defined, `shouldLoadGenerator=false`, YAML (not SQL)
item/monster branch. Ordered roots (map.cpp init order, constructors and
`getDefaultLocation`):

| Order | Type | Root | Current / minimum version |
| --- | --- | --- | --- |
| 0 | `ITEM_DB` | `db/item_db.yml` | 3 / 1 |
| 1 | `SKILL_DB` | `db/skill_db.yml` | 4 / 4 |
| 2 | `MOB_DB` | `db/mob_db.yml` | 5 / 1 |
| 3 | `QUEST_DB` | `db/quest_db.yml` | 3 / 1 |

The graph is the conditional initial load: database-specific row callbacks
(`parseBodyNode`) are assumed to return normally and are never emulated.
`loadingFinished`, `reload`, constructor side effects and post-processing are
outside it.

## Modelled source rules (database.cpp)

- **Lookup.** Control fields use the first mapping child whose key text equals
  the name (`Tree::find_child`). Later duplicates are kept as data.
- **load (92–146).** A canonical path under `conf/db/npc/sql-files` that is not
  in the snapshot is a known `fopen` failure: the visit returns `false`. Then
  Header compatibility, Clear, Body, imports, in that order.
- **Header (37–76).** A missing `Header`, an empty Header mapping, a missing or
  null `Type`/`Version`, a different `Type`, a version above current, or one below
  minimum is a known Header failure: no Body or imports for that visit, return
  `false`. A version from minimum up to below current warns and continues. Null
  means a plain scalar `''`, `~`, `null`, `Null` or `NULL`. Quoted, literal and
  folded scalars are never null.
- **Clear (132–138, asBool 253–277).** The scalar text is ASCII-lowercased
  without trimming. `true` adds a clear event and starts a new per-database
  epoch before Body. `false` does nothing. Null or other text warns and does not
  clear, and parsing continues. `Clear: |-` with text `true` is a valid true.
  Clear events are history only: no earlier row is erased.
- **Body (152–174).** Every row of the first `Body` sequence is catalogued in
  order.
- **Imports (176–228).** `Footer.Imports` entries are processed in order and
  depth first. `Path` comes first: missing or null skips the edge. Then optional
  `Mode`: null skips; otherwise it must equal `Renewal`, or `Prerenewal` when
  `RENEWAL_ASPD` is off and the path contains `job_aspd.yml` (case-sensitive).
  Then optional `Generator`: absent is unmarked; null or non-boolean text skips
  with a diagnostic; the import loads only if `shouldLoadGenerator` and the value
  is true, so explicit `false` always skips. Skipped targets are never opened or
  hashed. A child's return value is ignored: later siblings continue after a
  known missing-file or Header failure. Repeated acyclic imports are separate
  visits.

`modeled_graph_return` is `false` for known fopen/Header failures, `true` for a
visit whose Body and imports were fully modelled (conditional on callbacks), and
`null` when an unsupported state stopped it. No positive native return is
certified.

## Bounded parser and policy refusals (unsupported, never native)

These states stop certain traversal. The qualified prefix (visits, rows and
edges already modelled) is kept. The remaining import siblings and later roots
are listed in `unresolved`. No later clear, row or edge is invented.

- **Input bytes.** Over 16 MiB, NUL (native reading would truncate), invalid
  UTF-8, a UTF-8 BOM, and line breaks other than LF/CRLF (lone CR, NEL, LS, PS).
- **Parser.** A Psych refusal (`parser_refusal`, with Psych's problem/context
  and position only), adapter failure, CPU/wall/stdout/stderr limits.
- **Syntax.** Exactly one document with a mapping root is supported. Refused:
  `%YAML`/`%TAG` directives, several or zero documents, explicit tags, anchors,
  aliases, the plain merge key `<<`, and non-scalar (complex) keys. These checks
  cover the whole file before any field is read.
- **Control shapes.** Non-mapping `Header`, `Footer` or import entry; non-sequence
  `Body` or `Footer.Imports` (including null); non-mapping Body rows; non-scalar
  `Type`, `Version`, `Clear`, `Path`, `Mode` or `Generator`.
- **Version text.** Only ASCII decimal digits with a value of 0–65535 are
  accepted, quoted or plain, in base 10. A leading zero stays decimal. Native
  c4 conversion also accepts other bases and wraps overflow; those forms are
  refused rather than guessed.
- **Paths.** The import path is a literal server-root key (`rathena/` + path),
  never relative to the importer. Refused: empty, non-printable or non-ASCII,
  backslash, absolute, empty/`.`/`..` components, a snapshot directory, or a
  path outside `conf/db/npc/sql-files`. An import of a path already on the
  active stack is an `import_cycle`.
- **Work limits.** Per file: 2,000,000 nodes, depth 64, 1 MiB per scalar. Total:
  8,000,000 nodes, 256 visits, import depth 16, 4096 edges, 1,000,000 rows,
  512 MiB of records, 10,000 diagnostics. Each child gets 20 s CPU (`RLIMIT_CPU`),
  30 s wall clock and 192 MiB stdout and 64 KiB stderr capture, then is killed.
  The Ruby adapter checks node/depth budgets while walking the already-built
  Psych AST. Python repeats those checks and checks scalar UTF-8 byte size;
  it does not prevent Psych from first constructing an AST or the adapter from
  serializing a large scalar. Input, CPU, wall and capture caps remain the
  construction/transport controls. Failed attempts retain exact input reads,
  captured/observed child bytes and known node work; unknown full counts are
  explicitly null, rather than reported as zero. A refusal stops the certain
  suffix, so uncounted parser work cannot be followed by more graph parsing.
  **There is no hard memory bound.** Address-space/data limits fail on macOS
  before launch and are not used. Memory follows the fixed verified input size.

## Output records

`raw-declarations.jsonl` holds one compact JSON object per Body row (sorted
keys, ASCII escapes), in global load order:

- `database`, `root_order`, `visit`, `file`, `file_sha256`, `epoch`.
- `local_ordinal` (in that Body), `database_ordinal`, `global_ordinal`.
- `start_mark`/`end_mark`: zero-based Psych (line, Unicode character column).
- `byte_span`: `[start, end)` UTF-8 byte offsets in the original file, converted
  against LF/CRLF lines. `span_sha256` hashes exactly those bytes, with their
  original quoting, comments and line endings. A block row's span runs to where
  Psych ends the mapping, usually the indentation of the next `- `.
- `fields`: every top-level key in order, including repeats, with key style and
  value kind. `field_count` and `node_count` (all nodes of the row, keys
  included).
- `raw_ids`: every top-level `Id` field in order with `field_ordinal`, value kind,
  marks, byte span and span hash. A scalar also has decoded `text`, `style` and
  `null`. The full decoded text is retained within the scalar and output caps;
  there is no 1024-character preview. Nothing is cast, deduplicated or collapsed.
  A row without `Id` has `[]`.
- `fingerprint_sha256`: SHA-256 of
  `json.dumps(form, sort_keys=True, separators=(",", ":"), ensure_ascii=True)`.
  In `form`, a scalar is `{"k":"s","t":<decoded text>,"y":<Psych style 1-5>}`, a
  mapping is `{"k":"m","c":[key, value, …]}` with children in order, and a
  sequence is `{"k":"q","c":[…]}`. Non-BMP characters become UTF-16 escape pairs.
  No marks or paths are included. Duplicate pairs stay, so `yes`, `010` and
  `null` remain text with their style.

Decoded scalar text is not the raw lexeme; the byte span is the raw source.
Block scripts are opaque text: a `Footer:`/`Path:`-looking line inside one
creates no edge, and no script is executed. Full ASTs and source bodies are not
published; the immutable snapshot remains the source for later field
projections.

`yaml-graph-manifest.json` binds the generator version and source SHA-256,
snapshot manifest and verification reader, pinned source files and rules,
parser identity and adapter SHA-256, the profile, and the records file (size,
lines, SHA-256, read back). It also holds every visit (status, header records,
Clear, Body row range, duplicate-key sites, AST node counts), every edge
(Path/Mode/Generator records and decision), Clear events, exact reads (path,
bytes, SHA-256, visits), per-database counts, raw `Id` statistics, known
failures, the stop record, unresolved work, diagnostics, limits, usage and
exclusions. It has no timestamps and no host paths except the pinned
`/usr/bin/ruby` identity. `yaml-graph-complete.json` binds the manifest SHA-256,
version, status and the records SHA-256.

### Work accounting

`visits[].parser_attempt` is present for every attempt that passed byte-profile
prechecks and reached `parse_yaml`, including failures. It records input bytes,
exit, outcome, stdout/stderr captured bytes, observed bytes, whether each pipe
reached EOF, `node_total` and `node_count_lower_bound`. Observed bytes include a
cap-crossing read even when capture retains only the cap-sized prefix. Neither
count claims all bytes a killed child might otherwise have emitted.

`node_total` is exact only after the complete flat-node protocol is validated;
a scalar-budget refusal still retains this exact count. Parser traversal budget
refusals retain their observed node prefix as a lower bound, with null total.
Syntax refusal, timeout, malformed protocol and setup/I/O failure likewise keep
the full total null. A max-input refusal records an attempted file, without
claiming that a child parsed it. These are work observations, not native-parser
or accepted-record counts.

`work_usage.input_bytes_examined` includes byte-profile failures;
`input_bytes_parsed` is the legacy name for bytes offered to `parse_yaml`,
including attempts refused by its input cap. `parser_attempts` counts those
calls. `nodes` is the charged known/lower-bound sum, `exact_ast_nodes` sums only
exact attempts, and `unknown_node_count_attempts` counts null-total attempts.
Captured and observed stdout/stderr bytes aggregate both successes and failures.
`counts.ast_nodes` is null if any attempt has an unknown total; otherwise it is
the exact sum. A zero lower bound on an unknown attempt is not an exact zero.

Header Version records retain their full decoded scalar text, including all
leading zeroes; decimal conversion strips those zeroes before bounded integer
conversion. Emitted-row and raw-Id statistics advance only after the row writer
succeeds. An output-cap refusal therefore does not count an un-emitted row.

## Publication safety

The output parent must exist and be owned by you and not group/world writable.
The output is created with an exclusive `mkdir` at mode 0700, which refuses any
existing file, directory, link or dangling link. Files are created exclusively
and no-follow at 0600. Each is read back through a no-follow descriptor (owner,
mode, identity, size, SHA-256) before the next is written. The directory must
then hold only this run's files, and its close is part of publication. On any
failure after the marker exists, only the marker this run created (same
device/inode, same reserved directory) is removed. A replaced marker or
directory is preserved and reported, and a cleanup failure is reported
explicitly. Partial records/manifest may remain without the marker; inspect and
delete them before retrying. A same-user concurrent writer could still race
between steps.

Rollback: revert the source commit; delete a verified owned output directory
separately. No installed state, save or database is touched, so none needs
restoring.

## Canonical result (original raw counts; corrected rerun recorded in task review)

Status `complete` (exit 0). 15 visits, all read and current-version compatible:
four roots, their `db/re` and `db/import` leaves, and the three item leaves
`usable`, `equip`, `etc`. 15 edges: 11 loaded and 4 skipped (`Mode: Prerenewal`
of each root; those targets were not opened). 1,132,170 AST nodes, no Clear
events, no diagnostics, no known failures, nothing unresolved.

| Database | Visits | Raw Body rows | Raw `Id` occurrences |
| --- | --- | --- | --- |
| `ITEM_DB` | 6 | 29,356 (usable 6,415 / equip 12,982 / etc 9,959) | 29,356 |
| `SKILL_DB` | 3 | 1,635 | 1,635 |
| `MOB_DB` | 3 | 2,699 | 2,699 |
| `QUEST_DB` | 3 | 4,848 | 4,848 |
| Total | 15 | 38,538 | 38,538 |

Every row has exactly one scalar `Id`. There are two duplicate-key sites, both
kept: top-level `Trade` twice in item `400276` (`db/re/item_db_equip.yml`), and
`RaceGroups.EP172ALPHA` in `db/re/mob_db.yml`. These numbers are raw
declarations, not accepted, effective, loaded, spawned or playable entities.

## What this is not

Not native rapidyaml parity, typed row parsing, defaults, reference
resolution, merges, Clear side effects, accepted/effective/spawn counts,
installed overlays, runtime loading, content readiness or episode acceptance.
Row callbacks are excluded by design. A later projection must read the
immutable source for its fields.
