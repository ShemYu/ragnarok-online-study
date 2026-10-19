# First-level map dependency catalog (T06.003.003.004)

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

- `catalog_map_dependencies.mjs`: pure `buildCatalog(input)` and CLI `main(argv, {stdout})`.
- `test_catalog_map_dependencies.mjs`: authored payload, 14 refusals, admission and write controls.
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

## Limitations

- First-level declared RSW models and GND ground textures only.
- Constructed relative HTTP strings; no GET, asset availability, browser URL resolution or archive winner observed.
- No RSM/RSM2 body parsing, embedded/mesh-used/animated textures, sounds/effects, hooks, water or dynamic asset closure.
- All 1296 roots and 82 missing RSW roots remain explicit. Numeric anomalies, unread tails, and full art, render, travel, content and language acceptance remain open.

## Rollback

Revert this task commit on the task branch. Do not reset or force-push.
Git does not remove private catalogs; delete this checkout's
`.tools/renewal/t06-004-fixture-1` and `.tools/renewal/t06-004-corpus-1` only
if those private artifacts must go too. No game, save, SQL, browser, network
or preference state is changed here.
