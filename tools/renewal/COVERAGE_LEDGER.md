# Provisional coverage ledger — `coverage_ledger.py` (T06.005.001)

A small, source-only generator/validator that turns already qualified T06/T07
metadata into one provisional version/content ledger. It does not scan
assets, read raw JSONL streams, start any runtime, or requalify producers.

## Inputs (explicit only)

- `--inputs`: a pin file of schema `renewal-provisional-coverage-inputs-v1`
  (the frozen one is `docs/project/fixtures/T06.005.001-inputs.json`). Every
  entry gives a relative path, exact byte count, SHA-256 and the role
  `qualified_metadata_only`; anything else is refused.
- `--root`: an explicit absolute directory the relative paths resolve against.
  There is no default and no discovery. A relative or wrong root is refused.
- Each input is opened no-follow as a regular file, size-capped (16 MiB),
  hashed before parsing and again after generation. Any difference refuses
  (`PIN_DRIFT`, `PIN_MISSING`, `PIN_NOT_REGULAR`).
- Embedded paths/pointers inside manifests (raw streams, the original
  1296-root report, archive bodies) are recorded as inert identifiers only.

## Cross-input checks before any output

- Provenance: each downstream manifest must name the exact pinned upstream
  manifest SHA-256 (snapshot → selection → map cache / YAML / monster →
  static-spawn publication, quoted text). All server manifests must report one
  rAthena revision. The gap join's 83-input list must equal the profile's, and
  the profile must pin the admitted gap extract and corrected metadata.
- Root join: all profile gaps must have unique `gap_index` / `root_ordinal` /
  `map_name`, dense original `gap_index` order, and line up one-to-one with
  the extract rows filtered by exact `rsw.outcome == "http_404"` (original
  non-dense extract position kept), the corrected rows and the gap-join roots.
  Root/cache ordinal, cache file, RSW request index and configured flags must
  agree, and every root must hit exactly one map-cache entry and (if
  configured) exactly one stock-selection candidate.
- Counts: map-cache entries = profile world roots = per-file entries;
  configured candidates agree across selection/map cache/profile; static-spawn
  classes sum to events, raw counters agree and unknown bytes = raw − certified;
  NPC source counts agree; YAML database rows sum; MOB rows = monster
  declarations. The gap-join/corrected summaries must equal the ledger's own
  per-root totals.

## Output

Deterministic JSON (`sort_keys`, no timestamps or absolute paths). It holds the
admitted inputs, separate server/client/overlay version pins, per-category
facts and all 82 gap roots. Every fact and root slot carries:

- `state` ∈ expected, present, effective, loaded, exercised, verified,
  missing, unknown;
- `evidence_level` (for example `qualified_inventory_manifest`,
  `name_witness_metadata_only`, `prior_observed_request`,
  `documented_not_admitted`, `name_convention_only`, `not_observed`);
- `scope` ∈ server, client, overlay, cross; plus the source input/pointer.

`generate` also records `source_values` (each input-sourced fact's value as
read from its input pointer) and a fixed `reconciliation` table. Each
reconciliation entry names a binding (row count, configured rows, witness
totals, a fact) plus the input/pointer/value it must equal.

### What `validate` proves, and what it cannot

`validate` (also run by `generate`) checks **structure and internal
consistency only**. It refuses:

- unknown states or levels. Any non-`unknown` state at level `not_observed`.
  `effective`/`loaded`/`verified` without runtime or acceptance levels.
  `exercised` without an observation level (`prior_observed_request`,
  documented play or runtime). `expected` without a reserved
  `full_content_oracle`. Any reserved level when every input is metadata-only.
  A name-convention level on anything except `unknown`.
- the four full-content denominators (maps, monsters, story chains,
  instances) unless they are `unknown`, null, `not_observed` and unsourced.
  This holds even when the value or source is copied from cache entries or
  raw declarations.
- a category whose fact IDs differ from the fixed required list, or that has
  no visible `unknown`.
- duplicate or non-dense root identifiers, a closed `functional_gap`, a stock
  selection state that contradicts `configured`, and a gap RSW request that
  is not the observed HTTP404.
- an input-sourced fact without a matching recorded source value or with a
  different value. Row-derived facts that differ from the recomputed rows.
  Broken identities (spawn classes sum to framing events; cache-only equals
  cache entries minus configured). Recorded values without a fact.
- witness states/lists that disagree with occurrence counts, and a
  `gap_summary` that differs from `summarize_roots(rows)`.
- a reconciliation table whose keys, bindings or source pointers differ from
  the fixed specification, or whose recomputed rows/facts value differs from
  the recorded source value. For example, dropping a root and recomputing the
  summary still fails against the recorded 82.

`validate` **cannot prove input authenticity**. A coordinated edit of a fact
together with its recorded source value and every dependent fact/identity is
internally consistent by construction. Only `check`, which regenerates from
the pinned inputs and requires byte equality, proves reproducibility from the
frozen inputs.

Refusal codes include `UNBOUND_FACT` for a fact or reconciliation with no
fixed binding. Codes: exit 0 on success, 2 on refusal (the code is printed on stderr), 64 on
usage errors.

## Commands

```sh
python3 -I -B tools/renewal/coverage_ledger.py generate \
  --inputs docs/project/fixtures/T06.005.001-inputs.json \
  --root <canonical checkout> --out <new file> [--receipt <private file>]
python3 -I -B tools/renewal/coverage_ledger.py check \
  --inputs docs/project/fixtures/T06.005.001-inputs.json \
  --root <canonical checkout> --ledger docs/project/fixtures/T06.005.001-ledger.json
python3 -I -B tools/renewal/coverage_ledger.py validate \
  --ledger docs/project/fixtures/T06.005.001-ledger.json
python3 -I -B tools/renewal/test_coverage_ledger.py -v
```

`generate` refuses to overwrite (`O_EXCL`). `check` regenerates in memory and
requires byte equality with the committed ledger (`LEDGER_DRIFT` otherwise).

## Authored fixtures

`docs/project/fixtures/T06.005.001-cases.json` is a synthetic three-root
world, with non-dense root/cache ordinals, one cache-only root, one excluded
non-404 extract row, two catalog views and placeholder-resolved provenance.
It contains no real catalog row or asset data. It also holds 45 negative cases covering
duplicate/missing/extra root IDs, pin drift/missing/role/duplicate, relative
root, provenance and revision drift, input count reconciliation, and ledger
attacks. The ledger attacks are verification/exercise promotion,
denominators filled from metadata, inflated single facts (with and without
their recorded source value), removed bindings, row-pop with a recomputed
summary, and reconciliation rebinding. Multi-step cases use `ops`.

## Limits

These are metadata-level facts only. Name witnesses never close a gap. The
overlay and installed-runtime state are not admitted inputs and stay
`unknown`. Chapter 1 and instance tags are documentation or name-convention
hints, not classifications of story or party gates.
