# First-level map dependency catalog (T06.003.003.004, T07.007.005)

Builds the declared first-level request catalog for cached-map constructors.
RSW `summary.model_dependencies` filenames are prefixed once with `data\model\`
and deduplicated by that exact string in first-occurrence order. GND
`summary.textures` is already the unique first-use table; each entry is
prefixed once with `data\texture\` and is not deduplicated again. FileManager
whitespace trimming and slash-segment `encodeURIComponent` then produce a
relative HTTP string. GAT rows stay in the catalog with null dependency
fields. A target is that constructed string. It is not a GET, browser URL,
archive winner, asset-availability result or playable map.

Frozen task: [T06.003.003.004](../../docs/project/tasks/T06.003.003.004.md).
Profile pin `304e9da6ad4369ba96f30f71229de56581aedf6ee0789cc3d6261beb7e219df4`
(3379 bytes). Authored fixture `3848febb48ca112029024d9885498236037e94d436cf372d6a38d0d8e20cf24f`
(165420 bytes).

## Files

- `catalog_map_dependencies.mjs`: pure `buildCatalog(input)`, pure T07.007.005
  `admitConstructorBridge(...)` and CLI `main(argv, {stdout})`.
- `test_catalog_map_dependencies.mjs`: authored payload, 14 refusals, admission and write controls
  for both profile routes.
- This runbook.

Only these three tracked paths belong to the task. Private catalogs and the
candidate report stay under this checkout's `.tools/renewal/` at 0700/0600.

## Use

Node builtins only. No install, build, client execution or asset-body read.

```sh
node tools/renewal/catalog_map_dependencies.mjs \
  --input-root /canonical/repository \
  --profile docs/project/fixtures/T06.003.003.004-profile.json \
  --fixtures docs/project/fixtures/T06.003.003.004-authored.json \
  --output /own/checkout/.tools/renewal/fresh-output
```

Corpus mode replaces `--fixtures` with `--report` and `--jobs`. Both paths must
be the profile input paths resolved under `--input-root`. Exactly one mode is
required. Optional `--max-output-bytes N` is lower-only, from 0 through
`policy.max_catalog_bytes`. A complete catalog that does not fit is refused
before the output directory is created.

Stdout is one JSON line of at most 4096 bytes: `complete` with counts, or
`refused` / `error` with a generic reason. It does not include raw names.
Exit 0 follows a published `catalog.json` and unchanged input identities.
Exit 2 is an admission, usage, pin, link, output-budget or existing-output
refusal before publication. Exit 1 is a publication or post-create failure.
`main` returns that code; the executable entry sets `process.exitCode`.

## Projection rules

- Caller data is not mutated. Roots and the gap-ordinal array are copied.
- Row identity requires a nonempty id, 64 lowercase hex SHA, a nonnegative safe
  `input_bytes`, two header bytes, `outcome=returned`, `constructor_returned=true`,
  `worker_started=true` and `cleanup.exit_observed=true`. Booleans are not numbers.
- Every root ordinal is a unique nonnegative integer. Each root has `rsw`, `gnd`
  and `gat` edges whose `job_id` is null or a string of the same kind. Every job
  has at least one root reference. The gap list is exactly the root-array order
  of null `rsw.job_id` values. Missing edges do not become jobs.
- RSW `object_index` must equal the model-array index. Filename and nodename
  are strings. The loader keeps every placement through `occurrence_loader_indexes`.
  Hook matching is not applied.
- GND indexes are nonnegative integers in range. First appearances are
  `0,1,...`, every table entry is used, and table strings are unique. Range
  checking alone is not enough.
- Trim is `replace(/^\s+|\s+$/g, '')` on the whole prefixed name. Interior
  whitespace remains. Backslashes become slashes, then each non-empty segment
  is `encodeURIComponent`. Case, repeated slashes, dot segments and `!'()*`
  stay. Existing `%` is encoded again. A lone surrogate refuses the whole
  catalog with `reason=uri_encoding_unsupported`.
- Global targets deduplicate the exact HTTP string in job then loader order.
  Every loader entry has one referrer. Post-trim collisions stay visible.

`buildCatalog` returns `counts`, `roots`, `remaining_gap_root_ordinals`, `jobs`
and `targets`. The file envelope adds `schema=T06-map-dependency-catalog-1`,
`task=T06.003.003.004`, `mode`, profile/constructor/summary SHA values,
`input_pins`, `rule_sources` and `limitations` copied from the profile.
Fixture `input_pins` is `{authored: profile.authored}`. Corpus `input_pins` is
`profile.inputs`. There is no timestamp, absolute output path or random id.

## Admission

The profile SHA is pinned in code. Constructor profile, common summary, the
three rule sources (`MapLoader.js`, `FileManager.js`, `Ground.js`) and the
selected fixture or report/jobs files are regular files. No ancestor may be a
symlink. Each open uses `O_NOFOLLOW|O_NONBLOCK`, checks size before allocation,
and requires the same dev/ino/size/mtime/ctime across lstat, open, read and
relstat, plus the pinned size and SHA. Identities are checked again after the
catalog is built and after it is published. Fixture mode does not open the
production jobs or report and does not follow `body_path`.

Corpus mode also binds the report's jobs bytes/SHA/records, constructor-profile
and summary SHA values, all nine reported client-source pins, verified cleanup,
zero unverified exits and 2761 returned jobs. JSONL must end in LF, contain no
empty line, and stay within the 4MiB row and 128MiB file caps. The complete
counts must equal `profile.expected_counts` before publication. Rule files use
their pinned sizes. Output is one fresh directory below this checkout's
`.tools/renewal`, created exclusively at 0700, with `catalog.json` at 0600.
Writes use explicit positions. A zero-length write throws once and still closes
the descriptor. Failure after the directory exists returns nonzero and does not
label the artifact complete.

## Candidate checks

From the task child, `node --test tools/renewal/test_catalog_map_dependencies.mjs`
passed 12 tests and 0 failures. The tests cover the full authored payload,
caller immutability, all 14 frozen refusals, JSONL/path rejection, short and
zero-progress writes, deterministic fixture bytes, existing output, a too-small
cap, a raised cap, usage, symlink profile, symlink output ancestor, a changed
profile pin, and the executable entry.

Fresh fixture CLI: `.tools/renewal/t06-004-fixture-1/catalog.json`, 11429 bytes,
SHA256 `d124ea94302768657d4ce06db0e8d674603691e1cecebbfe840e7a7d6e766b5f`,
mode 0600, directory 0700. External wall about 0.04s; maximum resident set
about 54MB. Counts match the authored expected object, including 5 roots,
6 jobs, 12 edge references, 10 model occurrences, 9 model loader entries,
6 ground slots, 5 ground loader entries and 12 HTTP targets.

Fresh corpus CLI: `.tools/renewal/t06-004-corpus-1/catalog.json`, 32959912 bytes,
SHA256 `3c6b9707d2b9f8093d9e7ce21b7e320791d2b9d5ca4d3d6728e3f915356f64a3`,
mode 0600, directory 0700. External wall about 0.85s; maximum resident set
about 527MB. Counts equal the profile: 1296 roots, 1214 core chains, 82 RSW
gaps, 2761 jobs, 3642 edge references, 726296 model occurrences to 48980 loader
entries, 14577 ground slots to 14577 entries, and 11134 HTTP targets
(8194 model and 2940 ground at every name stage). A second fresh run matched
those bytes and was then removed. An independent read of the preserved file
found 63557 loader entries and 63557 referrers, no occurrence or target-link
miss, GAT dependency fields null, and the gap ordinals equal to the null RSW
roots. Report and jobs SHA values were unchanged after the run.

These checks do not read model or texture bodies and do not show that a name
exists in an archive or renders.

## T07.007.005 bridge route

Frozen task: [T07.007.005](../../docs/project/tasks/T07.007.005.md). Profile
`docs/project/fixtures/T07.007.005-profile.json`, 4649 bytes, SHA256
`c0dccf5d0f74eecbcf772c560820dc3e0b4e5b26986243255085701136117034`.
It binds the integrated T07.007.004 constructor output (producer commit
`68ec8ac9fbddac3dff273460498df36a9bcfc60a`). The old profile, old envelope and
`buildCatalog`/`assertCatalogLinks` semantics are unchanged.

The code holds two trusted descriptors. The profile's exact size picks one
before allocation and its full SHA must match before any profile field is
read. The bridge descriptor fixes report/jobs, authored fixture, constructor
profile, summary, the three rule sources, constructor task, manifest, worker
and producer pins. The profile must equal each of them.

```sh
node tools/renewal/catalog_map_dependencies.mjs \
  --input-root /canonical/repository \
  --profile docs/project/fixtures/T07.007.005-profile.json \
  --report /canonical/repository/.tools/renewal/t07-007-004-integrated-root-qualification-1/output-1/report.json \
  --jobs /canonical/repository/.tools/renewal/t07-007-004-integrated-root-qualification-1/output-1/jobs.jsonl \
  --output /own/checkout/.tools/renewal/fresh-output
```

Fixture mode on this route uses `--fixtures docs/project/fixtures/T06.003.003.004-authored.json`.
It publishes the same full authored payload with `task=T07.007.005` and
`input_pins={authored}`. It does not open the report, jobs or manifest.

Admission on both modes of the new route also:

- reads the constructor profile and binds it: schema `T06-map-constructor-profile-1`,
  task `T07.007.004`, same manifest, worker and summary pins, counts
  4 roots/4 observed/0 unavailable/12 jobs/12 edges, exactly nine source pins, and
  `Ground.js` equal to the rule pin;
- reads `map_constructor_worker.mjs` and `probe_map_constructors.mjs` from this
  checkout as pinned text. Neither is imported or run.

Corpus mode additionally reads the pinned report, jobs, input manifest and all
nine client-source texts with the same bounded no-symlink reader. The manifest
is metadata only; `body_path` and nested reference paths are never followed.
`admitConstructorBridge` then requires:

- Manifest: schema `T06-map-constructor-input-1`, task `T07.007.004`, counts equal
  to the constructor profile, unique job IDs, valid kind/SHA/bytes/two header bytes,
  every root edge linking a job of its own kind, no orphan job, and job order
  equal to first appearance across roots in GAT, GND, RSW order. The gap list must
  equal the roots with a null RSW edge.
- Rows: exactly 12 physical rows. Row `i` must match `manifest.jobs[i]` for id,
  kind, `complete_sha256`, `input_bytes` (manifest `bytes`) and
  `header_version_bytes` (manifest `header.version_bytes`). Rows are never sorted,
  dropped or replaced.
- Report: schema `T06-map-constructor-report-1`, task `T07.007.004`, mode
  `corpus`. `input` is the resolved manifest path with its bytes/SHA. Constructor
  profile and summary SHA must match. `worker` must equal the worker pin with
  `verified=true`. `client_source.root` and `profile_revision` must match, with
  nine unique verified sources equal to the constructor profile. Also required:
  preservation `true`; verified cleanup with 12 started and 12 exits, nothing
  unverified and `halted=null`; 12 expected/records/attempted/returned and every
  other outcome 0; and `jobs_file` resolving to the admitted jobs path with its
  bytes, SHA and 12 records.
- Roots: a deep copy of `manifest.roots`, with each non-null edge given
  `parse_outcome` from its linked row, must deep-equal `report.roots`. All original
  fields stay, including `parse_status=not_run`, scope and the null/unknown
  world ordinal.
- `report.input_manifest` has exactly the preserved manifest keys, each equal
  to the manifest. `parser_execution_performed_in_input` equals the manifest's
  `parser_execution_performed`.

Each row's archive ordinal and name hex stay in the pinned manifest at the same
`source_row_index`. They are not copied or reparsed. Corpus `input_pins` is the
report/jobs pins plus `constructor_manifest`. The envelope keeps every old key
and adds `constructor_task`, `constructor_worker` and `constructor_producer` after
`summary_sha256`, on this route only. New refusal reasons are
`manifest_invalid` and `jobs_mismatch`. Identities are checked again before
and after publication. A failed post-publication check exits 1 even though
`catalog.json` exists.

### T07.007.005 candidate checks

From the task child with the canonical input root present,
`node --test tools/renewal/test_catalog_map_dependencies.mjs` passed 25 tests
with 0 failures and 0 skipped. The 12 original tests are unchanged apart from
the private temp directory (`.tools/renewal/T07.007.005`). The 13 new tests
cover:

- the new fixture route, the old fixture bytes and the actual corpus payload
  against an independent restatement of the rules from the rows, repeated
  byte-identically;
- 55 report, manifest, row, link and root-augmentation faults on in-memory
  copies, plus a returned-row fault caught by `buildCatalog`;
- unknown, reshaped, oversized, directory and symlink profiles, and
  cross-substituted report/jobs/profile paths;
- a private copy of the admitted inputs with symlink, symlinked-ancestor,
  directory, resized, rehashed, source-hash and missing-file faults;
- lstat drift during admission and after publication;
- the output sentinel, lower, exact and raised budgets;
- short, zero, fsync and close write faults, and the executable entry.

Without the canonical input root, the corpus tests skip and the fixture tests
fail, because the rule sources live under the input root.

Fresh corpus CLI, run twice: `catalog.json` 169411 bytes, SHA256
`0a6d44ec22de3c54f5195c32d6fd253ef5f51a74feb212181181ab5d9570c362`, both runs
byte-identical. Wall time was about 0.06s and maximum RSS about 63MB. The counts
equal the profile:

- 4 roots, 4 core chains and 0 subset gaps;
- 12 jobs (4/4/4) and 12 edge references;
- 4922 model placements to 297 loader entries, and 40 ground slots to 40 entries;
- 273 model names and 38 ground-texture names at every stage;
- 311 HTTP targets.

The new fixture route gives 12437 bytes, SHA256
`3502b9e64ad5e40acaf82899b9650c0b76199f878f0babc9e5eb3dac0373ee5d`. The old
fixture route still gives `d124ea94…6b5f`.

This subset does not close any of the 82 world-level gaps or change the
1296-root ledger.

## Limitations

- First-level declared RSW models and GND ground textures only.
- Constructed relative HTTP strings; no GET, asset availability, browser URL resolution or archive winner observed.
- No RSM/RSM2 body parsing, embedded/mesh-used/animated textures, sounds/effects, hooks, water or dynamic asset closure.
- All 1296 roots and 82 missing RSW roots remain explicit. Numeric anomalies, unread tails, and full art, render, travel, content and language acceptance remain open.

## Rollback

Revert this task commit on the task branch. Do not reset or force-push.
Git does not remove private catalogs; delete this checkout's
`.tools/renewal/t06-004-fixture-1` and `.tools/renewal/t06-004-corpus-1`, or the
T07.007.005 private `.tools/renewal/T07.007.005`, only if those private artifacts
must go too. No game, save, SQL, browser, network
or preference state is changed here.
