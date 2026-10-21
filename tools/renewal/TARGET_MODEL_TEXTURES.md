# Supplementary nested model-texture route (T07.007.009)

Adds one second exact profile route to the existing texture catalog for the four-root supplement (`mu_fild01`, `ygg_edge`, `ygg_fruit`, `ygg_roots`). It links the texture declarations of all 273 Model constructor jobs to their models, RSW parents and placements, using only the qualified T07.007.008 production metadata. It reads no asset bodies and does not fetch, construct, compile or render anything. A declaration is not an availability, decode or render fact.

Frozen task: [T07.007.009](../../docs/project/tasks/T07.007.009.md). New profile `docs/project/fixtures/T07.007.009-profile.json` (4711 bytes, `c8e0a1aa…a7787`). The old route is unchanged: [MODEL_TEXTURE_CATALOG.md](MODEL_TEXTURE_CATALOG.md) still describes it, and its profile `432354b1…1b0c68` (4231 bytes), API, flags, exit codes and output bytes are the same.

## Changes

The task owns three files: `catalog_model_textures.mjs`, `test_catalog_model_textures.mjs` and this note. The core, old `admitCorpus`, authored fixture, profiles, producer, worker, summary and rule sources are not edited.

- **Route selection.** `ROUTES` holds exactly two descriptors, keyed by exact profile path. Each pins task, bytes and SHA256, and both are checked before the profile is parsed. An unknown path, a `./` or trailing-slash alias, or `__proto__`/`constructor` gives `path_refused`. Swapping profile contents between the two paths gives `size_limit` or `pin_mismatch`.
- **Profile.** The new profile's 13 fields must match exactly. That includes `constructor_producer{task,commit,program,worker}`, the four fixed rule names and pins, the `.008` constructor profile pin, an 18-key `expected_counts`, and the unchanged policy and six limitations.
- **Fixture mode.** The new profile uses the unchanged `T06.003.003.007-authored.json`. It reads the profile, the `.008` constructor profile, the summary, four rules, the implementation and the authored file. It does not read corpus, producer or worker files. The envelope differs from the old fixture output only in `task`, `profile_sha256` and `constructor_profile_sha256`. Cleanup keeps three keys, and none of the four corpus-only fields appear.
- **Corpus mode.** All four existing flags must equal the exact profile paths under the canonical `--input-root`. Ten files get full bounded reads before parsing: the constructor profile, summary, four rules, the implementation, the four inputs, and the producer program and worker. The same reads repeat after build and after publication.
- **`admitSupplementCorpus`.** This new export validates the complete unmodified documents before the core runs:
  - **Constructor profile.** Pins for summary, manifest, catalog, worker and rules; `client_source` revision and path; counts against the 18 expected counts.
  - **Catalog** (`T07.007.005`). Jobs are dense with `source_row_index = index`. Root edges join their jobs. Four subset roots keep `original_gap_root_ordinal = null`. All 337 referrers join exactly once, splitting the targets into 273 model and 38 ground targets.
  - **Manifest** (`T07.007.008`). Exactly 14 keys. Availability, catalog and ledger descriptors are checked as decimal-string identities. All 273 targets are re-derived from catalog indexes, the availability record and the body descriptor. The 273 jobs are re-derived by byte-equality grouping, and the header histogram is checked. The 38 carried BMP pairs carry 40 ground referrers, and model plus carried bytes total 7575328. All 297 `root_model_references` are rebuilt with their sparse catalog job, source-row, loader, root, edge, pointer and occurrence joins, for 4922 placements.
  - **Report.** Exactly 39 keys, task `T07.007.008`, `qualified === true`. The input, common summary, client sources and rules, and the producer `own_sources` (program and worker) must equal the actual identities read. The nine `pinned_inputs` roles must match exactly, in order. `source_postchecks` must be `21/21` with `failed: []`, and the 273 body postchecks must pass. Cleanup must be 273/273 with `unverified: []` and `halted: null`. Jobs-file bytes, SHA256, records and completion must match, with storage clean. Other required fields: RSS bounds, effective policy, full job/target outcome dictionaries, targets with `constructor_outcome`, `availability_admission`, and `functional` all-returned with no open failures. The `qualified` flag alone is never trusted.
  - **Rows.** There must be exactly 273 JSONL rows in manifest order, each within the 4 MiB row cap. Each row's keys must match exactly; only an extra `log` key is tolerated. Each row needs `worker_started`, `returned` and `phase: summary`. Timing must be in bounds, and `summary_json_bytes` must equal the summary's serialized length. The seven module keys must match, with `seek_globals [1,2,3]` and no dynamic imports. Cleanup must have exactly five typed facts: `{exit_observed:true, exit_code:0, terminated_by_parent:false, stdout_eof_observed:true, stderr_eof_observed:true}`. A missing, false, string, null or `1` EOF fact refuses, as does a nonzero or null exit, so no EOF result is ever inferred from exit 0. Each `job_accounting` row must equal the row without `summary`/`log`, plus `summary_payload_in_jsonl_only`.
- **Projection and restore.** Admission returns fresh row copies with exactly the three historical cleanup facts to the unchanged `buildCatalog`. It never edits the parsed rows. `restoreCleanups` returns a new output whose jobs carry the verified original five facts. It joins them by exact `source_row_index` AND `job_id`, and refuses on any mismatch.
- **Output.** The schema is still `T06-model-texture-catalog-1`, with task `T07.007.009`. `input_pins` equals the four `profile.inputs`. Four corpus-only fields are appended: `root_model_references`, `carried_ground_targets`, `world_gap_ledger_reference` (1296 roots, 82 gaps, `reconciled_by_this_subset:false`) and `constructor_producer`.
- **Test seams.** `hooks.afterPinnedJson(role, value)` runs on the new corpus route only, after the CLI's own complete pinned read and parse. `hooks.afterBuild` receives the pin roles. `Refusal` gains an optional private `detail`, while stdout still carries only `reason`. The CLI never sets these seams.

## Commands

```sh
NODE=/Users/shem/.local/bin/node      # v24.20.0
ROOT=/Users/shem/orca/workspaces/game-reverse-engineering/reverse-the-Ragnarok-Online-to-play-by-myself
OUT=$PWD/.tools/renewal               # this checkout; fresh child per run

$NODE --test tools/renewal/test_catalog_model_textures.mjs
$NODE tools/renewal/catalog_model_textures.mjs --input-root "$ROOT" \
  --profile docs/project/fixtures/T07.007.009-profile.json \
  --fixtures docs/project/fixtures/T06.003.003.007-authored.json --output "$OUT/<fresh>"
$NODE tools/renewal/catalog_model_textures.mjs --input-root "$ROOT" \
  --profile docs/project/fixtures/T07.007.009-profile.json \
  --report .tools/renewal/t07-007-008-integrated-cli-1/corpus/output/report.json \
  --jobs .tools/renewal/t07-007-008-integrated-cli-1/corpus/output/jobs.jsonl \
  --manifest .tools/renewal/t07-007-008-constructor-preparation-1/root-input-reference-1/input.json \
  --catalog .tools/renewal/t07-007-006-integrated-actual-1/output/catalog-input.json --output "$OUT/<fresh>"
```

Exit codes: `2` means refused before output, `1` means a failure after the output directory was created (the output is kept), and `0` means full publication with passing postchecks.

## Candidate results (Claude, base eb3eaa2)

Run on 2026-10-21 with `/Users/shem/.local/bin/node` v24.20.0. The tested implementation is 77142 bytes `1161cd5c…6d991`; the test file is 59779 bytes `268fcd5a…2447e`. Evidence is private, under the ignored `.tools/renewal/t07-007-009-claude-evidence-2/`, with directories `0700` and files `0600`.

1. `node --test`: 26 tests, 26 pass, 0 fail, 0 skipped, about 9.3s. That is the 17 original tests, byte-unchanged, plus 9 new ones.
2. Fresh old fixture CLI: exit 0, 14342 bytes `a7de2bc0…842196`.
3. Fresh new fixture CLI: exit 0, 14338 bytes `e4fe398b…b3ac4`.
4. Actual new metadata corpus CLI, run twice: exit 0 both times, 1346475 bytes `9b7bca8176959ce25b05c090a75cf5b815945bc2480121675331515f9e2c1bd2`, byte-identical. Counts are exactly the 18 expected counts: 4 roots, 273 jobs and targets, 273 returned (0 empty, 0 exceptions), 397 declarations (397 target-expanded), 178 nested targets, 297 parent links, 4922 placements (4922 root-expanded), 401 resolved and 0 unresolved slots, animation 3 true / 270 false / 0 unknown, and 0 subset and prior gaps.
5. Old metadata-only corpus regression: exit 0, 90271141 bytes `ea2c9423…dc10a`.
6. Both old-route outputs are byte-identical to the base `eb3eaa2` implementation run privately. Its implementation SHA256 equals the baseline pin `8d5ac1f5…`.
7. The 15 canonical input, producer, summary, profile, authored and rule files had identical SHA256, dev/ino/size/mtime/ctime/nlink and mode before and after every run.

The new tests cover:

- the exact two routes and baseline pins;
- new-fixture envelope equality with old except the three fields, plus an `fs.openSync` sentinel showing no corpus, producer or worker opens, from a private root holding no corpus files;
- cross-route, unknown, alias and child-path substitutions and mixed or duplicate flags;
- the actual corpus CLI: repeats, full 273/297/4922 joins, provenance equality, cleanup restored per row, carried BMP and world-gap separation, unchanged input/source hashes and identities, in-process FD closure, and the 14 rechecked pin roles;
- 74 table-driven admission faults on genuine pinned documents, each asserting its private `detail`: EOF, cleanup, accounting, rows, report, storage, outcomes, functional, pinned roles, producer, source identity, provenance, manifest, carried, ledger, null-world, catalog and constructor profile;
- seven CLI faults through `afterPinnedJson`, with positive hook activation on all five parsed documents;
- pure projection and restore: exact source-row and job-id join, no mutation of frozen inputs, three-key authored cores;
- post-build and post-publish drift of private-copy inputs and rules, and of a private implementation copy on the actual corpus route;
- complete short writes, partial-then-zero, zero, overlong, EIO and close failures (exit 1, output kept, FD count unchanged), and late and early deadlines.

## Limitations

- These are metadata declarations only. Nested texture availability, BMP/TGA decode, `createInstance`, compile, render, travel and play are later gates. Declarations are not GETs, and the hook, instancing, static-mesh, GL, cache and local-before-HTTP predicates remain unobserved.
- Only the four-root supplement is covered. The 1296-root world ledger and its 82 gap roots stay open; this subset cannot close them.
- Producer drift is checked by full rereads after build and publish. The CLI tests can mutate only a private implementation copy, not canonical inputs, so producer and worker rechecks are shown through the recheck role set and the generic recheck path.
- This is a worker candidate. Root separately runs withheld full typed audits and common controls, then scoring and integration. No user acceptance is claimed.

## Rollback

Revert the candidate commit. The old route keeps byte-identical outputs and no external state changes. Private outputs under `.tools/renewal` are ignored and can be deleted.
