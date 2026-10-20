# T06.003.003.008 nested model-texture observation

Claude candidate for the [frozen brief](../../docs/project/tasks/T06.003.003.008.md).
It builds an exact request plan for each of the 8119 nested texture paths in the
qualified .007 catalog. Root alone later runs it once against the owned loopback
reader. Byte availability, BMP prefix and TGA header fields are separate
observations. None of them shows image decode, rendering, travel or full-game
behaviour. **Root has not qualified this candidate.**

## Files

- `observe_model_textures.py`: Python stdlib only. Importing it defines constants
  and functions only. Exports `Refusal`, `build_plan`, `wire_target`,
  `write_all`, `transfer`, `inspect_texture_header`, `load_metadata`,
  `make_observer` and `main`. Only the direct entry calls `sys.exit(main())`.
- `test_observe_model_textures.py`: 44 unittest tests (authored controls,
  admission, full canonical metadata preflight, and production observer runs
  with fakes).
- This runbook.

## Commands

```sh
ROOT=/Users/shem/orca/workspaces/game-reverse-engineering/reverse-the-Ragnarok-Online-to-play-by-myself
python3 -I -B tools/renewal/observe_model_textures.py --preflight \
  --input-root "$ROOT" --profile docs/project/fixtures/T06.003.003.008-profile.json
python3 -I -B tools/renewal/test_observe_model_textures.py      # CANONICAL_ROOT overrides $ROOT
# Root only, after review/integration:
python3 -I -B tools/renewal/observe_model_textures.py --execute \
  --input-root "$ROOT" --profile docs/project/fixtures/T06.003.003.008-profile.json \
  --output "$PWD/.tools/renewal/<fresh-name>" --root-reviewed-sha256 <sha256 of this driver>
```

The CLI accepts exactly one mode. It refuses unknown, duplicate, missing, mixed
or `--flag=value` arguments. `--profile` must be exactly the relative path shown
and is resolved under `--input-root`. Input root and output must be absolute,
normalized and link-free. There are no alternate inputs, subsets or cap raises.
Exit codes: `0` preflight OK or qualified execute. `2` refusal before any output
exists. `1` failure after the output was created; the evidence is kept. Stdout
is one generic JSON line of at most 4096 bytes, with no names, paths or stacks.

## Design

- **Metadata admission** (`load_metadata`, 120 s monotonic budget). It reads
  this driver, the profile (SHA pinned in code), authored controls (≤1 MiB), all
  20 source pins (≤2 MiB each) and the catalog (≤128 MiB, 90271141 bytes). Each
  read has these checks:
  - link-free ancestors;
  - lstat as a regular file with `st_nlink == 1`;
  - `O_NOFOLLOW|O_NONBLOCK`;
  - fstat identity, a size check before allocation and a bounded read with an
    EOF check;
  - re-lstat for a stable dev/ino/size/mtime/ctime.

  JSON is strict UTF-8 and refuses duplicate keys, `NaN`/`Infinity` and
  overflowing numbers such as `1e309` (via `parse_float`). It checks the catalog
  envelope (schema, task, mode), its .007/.006/summary SHAs and `input_pins`,
  `rule_sources` and `limits` against the pinned .007 profile, and every typed
  count against the profile. After the plan is built, every metadata pin and
  this driver are hashed again. Preflight never stats native inputs and creates
  no output.
- **`build_plan(catalog, expected_counts)`**: a pure function that returns the
  six-key rows. It checks typed counts (bool is never an int), table lengths,
  the carried gaps and placements, and that the model-target referrers equal the
  parent links. It checks the returned tables and that exception jobs keep null
  `declarations`, `nodes` and `animation`. It checks the node-slot and animation
  tallies, declaration indexes, `http_path` (rebuilt once from the FileManager
  name), unique sequential targets and the ordered declaration↔referrer
  bijection. A referenced name with an ASCII `bmp` or `tga` extension (any case)
  gets that kind; every other name is `unknown`, and all referrers of a target
  must agree. Every literal wire must pass `wire_target`. Output never aliases
  the caller's data.
- **`inspect_texture_header`**: exact `str`/`bytes` arguments only, with a
  generic no-echo `ValueError` otherwise. It keeps at most 2 prefix bytes for BMP
  and 18 for TGA or unknown. For an 18-byte TGA prefix it reports the 12
  little-endian fields, the 3 derived flags, the 4 independent checks and
  `checks_all`. It has no magic check, decode or dimension-sized allocation.
- **`wire_target` / `write_all` / `transfer`**: the .005 contracts, unchanged.
- **Engine reuse (adapter).** The pinned .005 observer bytes
  (`565a42c3…3a35`) come from the admitted source pin. They are compiled and run
  in a fresh, non-`__main__` namespace that is never put in `sys.modules`. Only
  its `wire_target`, `write_all` and `transfer` names are rebound, to this
  module's functions. Admission checks that they are the same objects and that
  `Observer.request.__globals__` is that namespace. The engine's
  TASK/SCHEMA/PROFILE_SHA/POLICY are never rebound, and its
  `main`/`load_metadata`/`run` are never called.

  `make_observer` subclasses the engine `Observer` and keeps its
  request/transfer/lifecycle, launch, environment, shutdown, missing-log and
  tree code. It explicitly overrides:
  - `__init__`: new report;
  - `checkpoint`: runs `freeze()` before **every** persisted write;
  - `hash_natives`: single-link streamed hashes;
  - `verify_stored`: single-link, 18-byte prefix;
  - `classify`: header for every complete verified HTTP 200 response, including
    empty and HTML;
  - `health`: strict JSON;
  - `audit_tree`: plus a single-link catalog copy check;
  - `postchecks`: rehash natives, driver and all metadata pins, plus the
    bound-API identity;
  - `coverage` and `run`: new unattempted rows.

  `freeze()` normalizes the schema, task, mode and the launch profile SHA. It
  then refuses `signature` fields, wrong pointers or row drift by raising
  `Fatal('provenance_failure')`.
- **Report**: `T06-nested-texture-observation-1` with these parts:
  - `engine_pin`;
  - `catalog_refs`: file and the targets/roots/jobs/model_targets/parents/
    prior_gaps pointers, 1296 roots, 8119 targets, 16142 referrers and the 82
    gap ordinals;
  - each row: the target's `catalog_pointer`, `referrers_pointer`, `http_path`,
    `wire_target` and `header{kind,state,prefix_hex,tga}`. Unattempted rows keep
    their pointers and kind, with the halt reason.

  The coverage axes `complete_200_bytes_available`, `header_states` (summed over
  all rows) and `tga_header_checks` are independent of the other transfer,
  status and storage axes.

## Candidate results (worker run, 2026-10-20, base ed22f20)

| Check | Result |
| --- | --- |
| Unit tests | Raw candidate:42 OK. Root-corrected integration:44 OK/4.898 test seconds,6.022207 externally guarded seconds; sampled1239842816 bytes owned RSS (100ms target samples, not OS containment). |
| Authored controls | 34/34 header literals, 9/9 argument refusals, exact 4-target toy plan, 17/17 mutations refuse, 16/16 wire, 11/11 transport and 3/3 write vectors. Compared as typed full results. |
| Canonical preflight | exit 0, ≈1.9 s, ≈680 MB max RSS. 8119 targets (7902 bmp / 216 tga / 1 unknown), 16142 referrers, 1296 roots, 8166 jobs, 82 gap roots, 2 prior gaps, 20 source pins, 2435800-byte plan, 8119 unique once-decoded paths |
| No native access | Preflight runs under a guard on lstat/stat/open (native paths and their directories), mkdir/statvfs/Popen/socket/HTTPConnection. No guard was hit and no output was created. |
| Import / pure API | An audit-hook subprocess saw no open/mkdir/listdir/Popen/socket events during import or the pure plan/header/wire calls. |
| Production fakes | All of these run through the actual `make_observer().run()` with real tiny files and fake process/HTTP objects: complete run; empty/HTML 200; short writes; zero write; partial write then error; FD close fault; response and connection close faults; health-inclusive aggregate cap; late final read; header-verification tamper; reader loss; startup failure; final listener query failure; source/engine/catalog/native drift; forced kill, unknown exit, group and listener residue; absent log or extra log field; extra tree file; final publication failure; existing output. Each test asserts that its fault fired. It compares `/dev/fd` and the response/connection close flags **before** harness cleanup, and checks the provenance of every persisted checkpoint (prelaunch, launch and final). |
| Dispatch proof | A test spy in a fresh test-only engine namespace counts 5 `transfer` dispatches (health plus 4 targets). The production postcheck detects the rebinding and refuses qualification. |

## Limits

- No real execute scan has been run. Workers must not access native code, GRFs
  or HTTP. All execute evidence comes from fakes.
- The `cap_unresolved_eof`, timeout and redirect paths use the inherited engine
  code. They are not exercised here with production fakes, only by the authored
  transfer vectors.
- An observed TGA header, a BMP `BM` prefix or a complete 200 response does not
  show that the image decodes or renders. Unknown content stays unclassified.
- Exact model identity and billing were not observed.

Rollback: `git revert <candidate commit>`. Git does not restore private outputs
under `.tools/renewal`.
