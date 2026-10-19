# All cached-map core-resource observation

`observe_cache_map_cores.py` is a coordinator-operated source tool for the
fixed [T06.003.003.001 task](../../docs/project/tasks/T06.003.003.001.md).
It requires the pinned private metadata, alias proof, roots manifest, native
reader and acquired archives. A source-only clone has no assets and should
refuse these missing inputs. Outputs stay in ignored `.tools/renewal/`.

```sh
python3 -I -B tools/renewal/observe_cache_map_cores.py --preflight
```

Preflight reads source/metadata and authored synthetic checks only. It does
not read native binary/archive bytes, open a port or prove any map works.

Actual acquisition requires a completed paired plan review, root's independent
failure controls and a source checkpoint. Root supplies the exact personally
reviewed source SHA to `--execute --root-reviewed-sha256 <SHA>`. This starts
one isolated loopback reader in a fresh exclusive private directory; the
default destination refuses reuse. It never contacts the running game reader
or writes installed state, saves, host Internet settings or original assets.

The fixed profile covers1296cached names, including31not configured. It
records RSW and embedded GAT/GND resource/header observations, exact alias/
filename/HTTP provenance and explicit failures/unattempted roots. It streams
bodies with16MiB/body,8GiB aggregate,3889asset-GET and1200second acquisition
limits plus5second I/O limits. An incomplete body has no complete-body pin.
These limits do not bound native internal inflate memory or log size.

Root independently verifies every output/root/request/body/header and the
prior eleven-case results. A valid acquisition with gap rows is not an all-map
PASS. Header/body availability does not establish geometry, models/textures,
rendering, installed overrides, full client parsing or playable coverage.
See the [chronological verification record](../../docs/project/reviews/2026-10-19-T06.003.003.001.md).

The first execution at source9caeafe retained all1296root observations but
exited1: its strict inventory omitted the native reader's expected
`logs/missing-files.log`. Preserve that original failure. Root separately
audited this exact diagnostic and every retained response/root/input, obtaining
1213observed header chains and83explicit gaps. This qualifies the bounded
observation corpus, not the original CLI run or map playability. Do not rerun
over its existing output. Any future acquisition must review a fresh destination
and diagnostic-log policy first; see the linked audit for exact evidence.
