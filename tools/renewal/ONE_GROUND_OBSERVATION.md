# Targeted ground-resource observation

`observe_one_ground.py` is root-operated source for
[T06.003.003.002](../../docs/project/tasks/T06.003.003.002.md).
Private frozen metadata and the existing assets are required. A source-only
clone should refuse absent inputs.

```sh
python3 -I -B tools/renewal/observe_one_ground.py --preflight
```

Preflight checks source/metadata and authored synthetic checks only. It does
not read a native binary/archive, start a process or make a network request.
The actual acquisition needs root's paired-plan review, independent failure
controls and a source checkpoint first. Supply the exact reviewed source SHA
to `--execute --root-reviewed-sha256 <SHA>` only after those gates pass.

The driver loads the exact pinned old observer bytes into a separate module
namespace, overrides its output directory/caps, and supplies an explicit
24MiB cap to inherited transport. The original file and corpus stay unchanged.
Target accounting, context checks and diagnostic-log inventory are separate.
The new exclusive output directory refuses reuse.

Only the alias table and the observed `schg_dun01` RSW/GAT/GND chain are requested:
four asset GETs, one bounded health GET,24MiB/body,32MiB aggregate and120seconds
acquisition after health, with5second I/O. Complete alias/RSW/GAT hashes and
headers must match the prior audited context before the larger GND qualifies.
The target's former Content-Length is an expectation, not a prior body hash.

Require private outputs, no extraction, complete native input hash/identity
equality, owned reader exit0 without forced kill and absent process group/
listener. The known diagnostic log is accepted only after exact bounded
JSONL/request checks; any failure still leaves the target unqualified.
Native inflate memory/log growth and total pre/post-hash time are not bounded
by the client transfer/acquisition caps. The live game, SQL, installed files
and host Internet/audio/input preferences are untouched.

Root independently audits the actual retained evidence. Neither preflight,
source controls nor an observed header chain establishes full Ground parsing,
geometry/art, rendering, walking or complete-game coverage. See the
[chronological review](../../docs/project/reviews/2026-10-19-T06.003.003.002.md).
