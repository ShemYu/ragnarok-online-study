# T06.003.003.007 nested model-texture declaration catalog

Selected Claude implementation for the [frozen brief](../../docs/project/tasks/T06.003.003.007.md),
integrated unchanged as5c0eb08, followed by a separately attributed root copy correction.
It links every declared Model texture table entry to its original model, RSW
parents and placements using only qualified .004/.006 metadata. It does not read
asset bodies, fetch, run constructors, compile or render. A declaration does not
show that a texture is available or renders. Current verification and source
checkpoints are in the [root review](../../docs/project/reviews/2026-10-20-T06.003.003.007.md).

## Files

- `catalog_model_textures.mjs`: pure `buildCatalog(input[, policy])`, the exported
  `Refusal`, `admitCorpus`, and the CLI `main(argv, { stdout })`. Uses only Node
  builtins. Importing it runs no CLI and does no file I/O. Only the direct entry
  sets `process.exitCode`.
- `test_catalog_model_textures.mjs`: 17 `node:test` tests, including the root
  regression for opaque own `__proto__` metadata.
- This runbook.

## Commands

```sh
NODE=/Users/shem/.local/opt/node-v24.20.0-darwin-arm64/bin/node   # v24.20.0
ROOT=/Users/shem/orca/workspaces/game-reverse-engineering/reverse-the-Ragnarok-Online-to-play-by-myself
OUT=$PWD/.tools/renewal      # this checkout; directory 0700

$NODE tools/renewal/catalog_model_textures.mjs --input-root "$ROOT" \
  --profile docs/project/fixtures/T06.003.003.007-profile.json \
  --fixtures docs/project/fixtures/T06.003.003.007-authored.json \
  --output "$OUT/claude-a1-fixture"

$NODE tools/renewal/catalog_model_textures.mjs --input-root "$ROOT" \
  --profile docs/project/fixtures/T06.003.003.007-profile.json \
  --report .tools/renewal/root006-corrected-full-corpus-2/report.json \
  --jobs .tools/renewal/root006-corrected-full-corpus-2/jobs.jsonl \
  --manifest .tools/renewal/t06-map-dependency-preparation-1/root-model006-input-preparation-1/input.json \
  --catalog .tools/renewal/t06-map-dependencies-actual-1/catalog-input.json \
  --output "$OUT/claude-a1-corpus-1"

$NODE --test tools/renewal/test_catalog_model_textures.mjs   # CANONICAL_ROOT overrides $ROOT
```

Optional flags can only lower limits: `--max-output-bytes 0..134217728` and
`--run-timeout-ms 1..120000`. Flags must form exactly one mode. Unknown,
duplicate, missing or mixed flags are refused.

Exit codes: `0` means the full catalog was published and every postcheck passed.
`2` means refusal before the output directory was created. `1` means a failure
after creation; the failed fresh directory is kept as evidence. Stdout is one
generic JSON line of at most 4096 bytes, with no names, paths or stacks.

## Behavior

- Admission: the profile SHA is pinned in code. The CLI reads and hashes the
  full profile, the .006 constructor profile, the common summary, the four rule
  sources, the selected authored or four corpus inputs, and its own source.
  Every read follows the same sequence: link-free ancestors; lstat as a regular
  single-link file; open with `O_NOFOLLOW|O_NONBLOCK`; fstat; size check before
  allocation; bounded full read with EOF check; close; then re-lstat to confirm
  identity. The CLI never chmods inputs. Fixture mode does not open production
  inputs or bodies.
- Rechecks: after building, and again after publication, the CLI fully re-reads
  and re-hashes every input and its own source, then compares identities.
- Corpus binding: the report, jobs, manifest and catalog are bound to the
  qualified .006 premises (schema, task, mode, qualified flag, profile and
  summary SHAs, counts, expected IDs, jobs bytes/SHA/records, clean workers,
  storage, 18/18 source postchecks). Each report target equals its manifest
  target plus `constructor_outcome`. Each report accounting row equals its JSONL
  row without `summary`/`log`, plus `summary_payload_in_jsonl_only`. Manifest
  roots and gaps equal the catalog's. Each target binds `/targets/<target_index>`
  with the same `http_path` and full referrers. The corpus core input is built
  from these, and its counts must exactly equal `profile.expected_counts`.
- Core: implements the brief's validation and output contract. This includes
  the full parent bijection, first-occurrence pointers, RSW-array placement
  indexes, model and texture stages (prefix once, whole-name ECMAScript trim,
  per-segment `encodeURIComponent`), and strict `Number.isInteger` slot
  resolution. It recomputes rotation/position/scale node-key animation and
  dedups nested targets by exact `http_path` only. A lone surrogate refuses with
  `uri_encoding_unsupported`. Raw NaN/Infinity, cycles, holes, accessors,
  symbols, BigInt, undefined, functions, non-plain objects and depth >64 are
  refused. Explicit marker objects are data. Whole-input caps for
  declarations, nodes, slots, parent links and placements refuse; nothing is
  truncated.
- Copying: opaque own keys, including nested `__proto__`, remain ordinary data
  properties. Output objects keep their ordinary prototypes and do not alias
  caller data. The root regression fails on the unchanged raw candidate.
- Publication: the serialized size is checked before any output exists. The CLI
  creates one exclusive fresh directory directly below this checkout's
  `.tools/renewal` (0700), containing only `catalog.json` (0600, `O_EXCL`). It
  writes until every byte is written, fsyncs, closes once and fsyncs the
  directory. Zero progress, a write error or a close error is never reported as
  complete.

## Historical raw provider results (2026-10-20, base e89e894)

The following records the raw provider handoff. Root separately reproduces
the complete outputs, finds defects, compares both candidates and validates
the corrected integration in the linked review. Do not treat this table alone
as current qualification or owned-descriptor proof.

| Check | Result |
| --- | --- |
| `node --test` | 16 tests, 16 pass, 0 fail, 0 skipped (≈4.7 s) |
| Literal payload | `buildCatalog(input)` equals `expected` deeply and as identical `JSON.stringify` bytes; caller input unchanged, including a deep-frozen copy |
| Stage cases | 10/10 exact declarations plus one nested target and one referrer |
| Refusal cases | 20/20 throw `Refusal`; R20 has reason `uri_encoding_unsupported` |
| Fixture CLI | exit 0, 14342 bytes, SHA `a7de2bc088e9d44664c8490aae508c245b4ab8b6f62c5d0c81b2011e2a842196`; core equals authored `expected` |
| Corpus CLI ×2 | exit 0 both, 90271141 bytes, SHA `ea2c942315275e67cbd5b89618b1fa8bd80fc380c0c2f59a06b11b48911dc10a`, byte-identical; ≈2.0 s real, 1.06–1.08 GB max RSS (`/usr/bin/time -l`) |
| Corpus counts | all 18 equal the profile: 1296 roots, 8166 jobs (8165 returned / 1 exception), 8194 targets, 16142 declarations, 16181 target-expanded, 8119 nested targets, 48980 parent links, 726296 placements, 871959 root-expanded, 21475/0 node slots, animation 602/7563/1, 82 gap roots, 2 prior gaps |
| Inputs | all 12 pinned files have identical SHA-256 before and after the test and CLI runs (local `pre-hashes.txt` / `post-hashes.txt`) |

Fault controls in the tests:

- Short writes (97-byte chunks, hook fired >100 times): byte-identical to a normal run.
- Zero progress or a throwing write: exit 1, exactly one write attempt, no retry.
- A close that fails after closing the descriptor: exit 1, close not retried.
- In all three faults the `/dev/fd` count is unchanged and the output is kept.
- Drift after build: refused with exit 2 and no output.
- Same-size input drift after publication, with mtime restored: exit 1 `source_drift`.
- Own-source drift after publication: exit 1 `source_drift`.
- Every drift hook is counted, so each one is proved to have fired.

Path controls in the tests: symlinked ancestor, symlinked leaf, hard link,
FIFO, pin mismatch, wrong or `..` path, existing output and output outside
`.tools/renewal` are all refused. The import test proves the module makes zero
file-system calls from its own frames, and the same counter observes the calls
`main` makes.

## Limitations

- These are declarations only, under the six profile limitations. No GET,
  image, compile, render, travel or playability claim is made.
- The model with the constructor exception keeps an unknown table. The 82 RSW
  core gaps and 2 prior ground gaps are carried unchanged.
- Full node transforms and boxes stay in the pinned JSONL row (`source_row_index`).
  They are not copied here.
- Numeric fields are type-checked and copied; they are not recomputed.
- Corpus RSS is about 1.1 GB because all four inputs are parsed in one process.
  This was sampled once with `time`, not contained.
- Providers did not access root's private reference. Root's independent full
  typed comparisons and actual fault observations are recorded in the review.

## Rollback

Revert the separate root correction before reverting unchanged integration
5c0eb08 and dependent changes; the linked review records their exact commits.
Git does not restore ignored outputs or installed state. Keep private failed
outputs as evidence. No input, installed game, save or setting is changed.
