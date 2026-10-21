# T07.007.010 nested-texture availability route

Claude candidate for the [frozen task](../../docs/project/tasks/T07.007.010.md),
[profile](../../docs/project/fixtures/T07.007.010-profile.json) and
[baseline](../../docs/project/fixtures/T07.007.010-baseline.json). It adds one
second profile route to `observe_model_textures.py`. The route plans the 178
conditional nested texture paths (397 declaration referrers) of the qualified
.009 four-root catalog. Root alone later observes their byte availability and
BMP/TGA headers once through the current engine's owned loopback reader.
**Root has not qualified this candidate.** No availability or header success
count is predicted. No image decode, instance, compile, render, travel, save,
story or playability result is claimed.

The legacy T06.003.003.008 route is unchanged. That covers `load_metadata`,
`load_engine`, the three-function `BOUND_API`, `_observer_class`,
`make_observer`, the constants and the pure `build_plan`, `wire_target`,
`write_all`, `transfer` and `inspect_texture_header` APIs. The old runbook
[MODEL_TEXTURE_OBSERVATION.md](MODEL_TEXTURE_OBSERVATION.md) still describes
that route.

## Commands

```sh
ROOT=/Users/shem/orca/workspaces/game-reverse-engineering/reverse-the-Ragnarok-Online-to-play-by-myself
/usr/bin/python3 -I -B tools/renewal/observe_model_textures.py --preflight \
  --input-root "$ROOT" --profile docs/project/fixtures/T07.007.010-profile.json
CANONICAL_ROOT="$ROOT" /usr/bin/python3 -I -B tools/renewal/test_observe_model_textures.py \
  T07CanonicalPreflight T07Admission T07Dispatch T07Lifecycle
# Root only, after review/integration, under the unchanged external guard:
/usr/bin/python3 -I -B tools/renewal/observe_model_textures.py --execute \
  --input-root "$ROOT" --profile docs/project/fixtures/T07.007.010-profile.json \
  --output "$PWD/.tools/renewal/<fresh-name>" --root-reviewed-sha256 <sha256 of this driver>
```

The CLI semantics are unchanged. It takes exactly one mode, and unknown,
duplicate, mixed or `--flag=value` arguments refuse. `--profile` is an exact
relative path resolved under `--input-root`. Exactly two routes exist:

- the old path, which selects the legacy route;
- `docs/project/fixtures/T07.007.010-profile.json`, which selects the new one.

Any other spelling refuses with `profile_path` before the profile is statted.
Exit codes:

- `0`: preflight OK, or execution that qualified.
- `2`: refusal before output exists.
- `1`: failure after output was created. Evidence is retained.

## Admission (`load_metadata_t07`, 120 s budget)

The route is selected before parse by exact path, then exact bytes
(10533) and SHA-256 (`ebbed64c…cb8f`, literal in code). The admission reads 27
metadata paths. Each read is regular, single-link, no-follow, bounded to EOF
and checked against its full SHA-256 and stable identity:

- this driver, the profile, the authored controls and the catalog;
- the 23 ordered source pins.

All 27 are hashed again after planning. Postchecks re-admit them after
execution. Strict JSON refuses duplicate keys, non-finite values and
overflowing numbers. Typed comparisons never treat a bool as an int.

The profile check requires all of the following:

- the exact key order, schema, task and basis;
- the exact policy;
- the catalog, authored and producer descriptors;
- the 23 ordered source paths and every role pin: current engine 112136,
  producer 77142, .009/.008/.006 profiles, summary, and constructor program
  and worker;
- all six ordered `input_root` native descriptors;
- the 18 typed counts and 171/7/0 kinds.

The .006 engine profile supplies native and lifecycle authority only. Its 311-target
catalog is never followed. Preflight never resolves HOME, never stats or opens
native paths, launches a process, contacts HTTP or a socket, and creates no
output.

The catalog must be exactly the
`.tools/renewal/t07-007-009-integrated-new-corpus-a-1/catalog.json` pin. Its
checks:

- the 21 envelope keys in order;
- the .009/.008/summary bindings, `input_pins`, `rule_sources`, `limits` and
  counts against the pinned .009/.008 profiles;
- the exact upstream `constructor_producer`;
- all four corpus-only additions.

Every one of the 273 jobs keeps its five typed cleanup facts, including both EOF
booleans and integer exit 0. The catalog is never projected to cleanup3. These
are preserved and checked as provenance:

- **Roots:** four roots with null/unknown original world ordinals.
- **Root model references:** 297, joined to the parent links, model targets
  and root edges, with 4922 occurrences.
- **Carried ground pairs:** 38 BMP pairs with 40 ground referrers. They are
  provenance only, and one of their paths is also a nested target that is
  requested once.
- **World ledger:** the 1296-root/82-gap reference with `reconciled=false`.
  Its path and identity are strings only and are never opened.

The full original catalog goes unchanged to the unchanged pure `build_plan`.
The result is 178 ordered six-key rows (`index, catalog_pointer, http_path,
wire, kind, referrers`) with 397 referrers. `kind` comes from the final
FileManager basename: BMP 171, TGA 7, unknown 0. Serialized, the plan is
46000 bytes, ASCII, compact and without LF. The request is a slash plus the
unchanged encoded `http_path`. There is no decode, casefold, alias, retry,
dedup or extra GET.

## Current-engine adapter

`load_engine_t07` runs the exact admitted current engine bytes in a fresh
non-main namespace. It uses the engine's actual source path as `__file__`. It
never touches `sys.modules`, the engine `main` or the map `load_metadata`. In
that namespace only it binds exactly four functions:

- `wire_target`, `write_all`, `transfer`: the driver's pure APIs.
- `unattempted`: texture rows/suffixes with `header` and no `signature`. This
  is not an availability result.

Identities and every inherited method's `__globals__` are checked at load and
again in postchecks. The engine constants, routes and global policy are
untouched.

The new Observer gets an explicit `T07_ROUTE` with:

- task T07.007.010 and the new profile SHA;
- policy: 178 assets, cache 0/0, cache/diagnostic limits;
- the six native names and `split_root=True`;
- a child-owned container (the driver checkout's `.tools/renewal`).

`NestedTextureObserver` inherits these from the current engine and redefines
none of them: `run`, `request`, `scan`, `launch`/`_launch_piped`, `health`,
`cache_stats`, `shutdown`, `finish_diagnostics`, `retained_postverify`,
split-tree audits, `create_output`/`admit_output`, `hash_natives`,
`diag_check` and `environment`. The import refuses if any of them is
redefined. The narrow overrides:

- `__init__`: starts from the base report and keeps every split-route field.
  It sets schema `T06-nested-texture-observation-1` and task T07.007.010, and
  adds:
  - nested `catalog_refs`, with carried-ground, world-ledger and
    unknown-ordinal provenance;
  - the producers;
  - the header API;
  - the four-binding engine pin.
- `freeze` before every `checkpoint`: verifies schema, task, profile,
  launch task and profile, an environment without HOME, and every row's
  index, pointers, path, wire and kind. Rows may carry no `signature` and no
  leaked `_prefix`.
- `verify_stored`: runs the engine's full verification and retained-receipt
  registration first. It then re-reads the first 18 stored bytes. The receipt
  must equal the retained one, otherwise the result is a storage failure.
- `classify`: delegates availability to the engine with no signature kind. It
  applies `inspect_texture_header` only to complete, verified HTTP 200 bodies,
  including empty or HTML ones. Every other row stays `not_checked`.
- `postchecks`: covers the six natives, the 27 metadata paths, the driver and
  the four bindings. It never calls map metadata admission. It **always** runs
  the inherited `retained_postverify` as well.
- `audit_missing_log`: a read or close `OSError` becomes an invalid log, not a
  crash.
- `coverage`: tallies availability and header states separately.

Known inherited nuance: the driver's unchanged `transfer` maps any `read1`
exception to `transport_error`. That includes an engine `Fatal` raised by the
metering check. The engine still detects diagnostic failure through
`diag_check` after `transfer`. It detects deadlines through the `late` flag and
`classify`. So neither becomes a success.

## Runtime and report (root only)

The healthy order is:

1. health at index 0;
2. `cache_before` at index 1;
3. the 178 targets at indexes 2..179;
4. `cache_after` at index 180.

Health must report version 1.0.5. Both cache probes must return a typed integer
`index.grfCount=5` and `cache.size=0`/`maxSize=0`. The five startup lines, each
with two leading spaces, must match exactly and in order on one stream. The
policy, guard and cleanup rules are the frozen task's. The report keeps:

- the current health, cache, startup, diagnostic, server/evidence-tree,
  retained and cleanup fields;
- the exact full catalog copy;
- all 178 ordered rows.

Empty 200, HTML 200, 404, other status, partial, storage error and unattempted
rows stay distinct. Exit 0 may keep honest asset or header gaps.

## Provider evidence (this candidate)

Base `7c6337fb653046af43f23e486e6ce2763130e125`. The evidence, commands and
results are listed in the worker report. In summary:

- **Real canonical preflight:** exit 0. The result is 178/397/171+7+0, 46000
  bytes and 27 metadata paths. The plan SHA-256 equals the public admission
  value `f370447a…9651`. The current canonical OLD preflight still refuses with
  `admit_size`.
- **Focused new classes on current canonical metadata:** 30 tests pass,
  covering:
  - native/HOME/process/socket/output sentinels and the 27-path post-read
    count;
  - typed plan and admission mutations after the genuine pinned read;
  - dispatch and injection counts;
  - tiny fake-I/O lifecycle, header, storage, deadline, postcheck,
    publication and CLI controls.

  They use real tiny pipes and descriptors. The FD and thread baselines are
  checked before harness deletion.
- **Legacy regression:** a fresh child-owned snapshot of exactly the 25
  baseline files, with only the observer replaced by this driver before the
  final receipts. The unchanged 60221-byte test file runs there with
  `CHECKOUT == CANONICAL_ROOT`: 44 tests, OK, 0 skips. The snapshot and root
  baseline receipts are unchanged afterwards.

Fakes are not listener, process, network or native proof. The actual 181-response
scan, the full-body audit and the coverage counts belong to root.

## Limitations and rollback

This covers the four-root supplement only. The 82 world gaps, full
Modern/Renewal content, Traditional Chinese, solo/offline play and user
acceptance stay open. The five-archive order inherits T07.007.006. The RSS
guard is sampled, not containment. Source rollback is `git revert` of the
candidate commit. The new route writes nothing outside its private output.
