# Next functional check: real client map parsers

Preparation only after [qualified target observation](2026-10-19-T06.003.003.002.md#actual-targeted-observation-and-independent-root-qualification)
at f311891. No parser adapter, full parse, geometry or renderer is qualified.
Keep all1296roots and82remaining resource gaps visible; do not replace the
full-game goal with the1214currently observed chains.

Root confirms FileManager.js452–461uses new World(buffer), new Ground(buffer)
and new Altitude(buffer). Import these constructors directly in a detached
runner rather than FileManager/MapLoader/ThreadEventHandler, which also load
other assets and compile map geometry. Root checks the primary constructor/
signature/typed-buffer paths and static import closure; an internal aide
supplies further source-reading preparation, not provider/runtime credit.

The closed static module set below is relative to private client-source/.
Recheck exact source pins and full parser behavior before freezing the next
brief; existing client files must remain unmodified.

| Source | SHA256 |
| --- | --- |
| src/Loaders/World.js | e1f6d5e52fe84c2a31c4f8f13e5be20cb6f93b2675c6f7615ac295be47f5a68e |
| src/Loaders/Ground.js | 8b82cf7321123054cf2bbeff1816931c7f3fc7833ae7af916077691d871f2db0 |
| src/Loaders/Altitude.js | e27f5b746bb8fa77aadb59633dfbc0339f922bc4df69615a066288a6cf160b95 |
| src/Utils/BinaryReader.js | bcf694b7034e36146eed1d5a2d7d5cf93d8a52aeafa74e62f0beed4c1ecc9215 |
| src/Utils/Struct.js | 03dedc9bf39943ff027c80d9a81ebfc2a15549c08ec3a1d7e725fb93e3ecf0b7 |
| src/Utils/CodepageManager.js | 35fc6861784c27ce417697f8c4f2e999a7703bb89741b2ddb3ea0afc44c7733e |
| src/Utils/gl-matrix.js | 46725df08241575dd60a98dbea9a035af0dc69d89c2538c2938018cfa091ea29 |
| src/Vendors/gl-matrix.js | bdf9ed62160fc270e995aa1a3c97eb8dac69fbd02d3141ed766a8306d2ce8f59 |
| src/Vendors/iconv-lite.js | a7663d70d99a455b964c223eb26db6c048bfd7977d6583e8e9fd7a79e17a0303 |

Root's read-only local probe confirms Nodev24.20.0has vm.SourceTextModule when
started with --experimental-vm-modules and exposes worker_threads.Worker.
This proves capability availability only. A closed SourceTextModule linker
is a candidate implementation: deny unknown/dynamic imports and give only
the browser-worker compatibility globals required by those exact sources.
Do not run the client builder, change packages or touch dist/installed state.

BinaryReader36–55accepts same-realm ArrayBuffer/Uint8Array; the Uint8Array
branch takes its whole underlying buffer. A Node Buffer slab or cross-realm
ArrayBuffer can therefore change the observed parse. Build the exact buffer
inside the VM realm and test offset/realm failures explicitly. Preserve the
SEEK globals installed by BinaryReader20–27. Ground stores fp; World/Altitude
keep their readers local. Do not invent a common EOF assertion or modify the
real constructors just to expose a cursor. World intentionally leaves a
quadtree unread; constructor return alone is not whole-format validation.

The next bounded task should freeze a combined manifest referencing qualified
old/target bodies and every original root edge, then compare actual Claude/
Grok implementations in separate task branches/worktrees. Share only read-only
canonical private inputs. Parse once per(kind,complete SHA), retaining every
root reference and explicit missing/failure/unattempted outcome. Separate
constructor return, exception, dimensions/counts, nonfinite values, trailing-
byte diagnostics and known source-version branches; none means rendered play.

Admit authored valid/truncated/bad-signature/realm/offset fixtures first, plus
bounded output and positively verified worker cleanup. Run serial isolated
parsers with explicit wall/heap/observed-RSS limits and account for timeouts,
allocation failures and unattempted inputs. V8 heap flags do not hard-cap typed
arrays or total native memory. Root must establish this procedure and common
oracles before dispatch, personally verify both submissions and actual corpus
results, then commit before advancing to model/texture/compile/render checks.

Compatible-asset/version investigation for82unresolved world entries remains
separate open functional work. No map deletion, invented alias, party-only
classification, goal change or user acceptance follows from this preparation.

## Root constructor and input admission checkpoint

After0d3ff0a, root executed the exact nine unmodified modules with Node's
experimental VM modules on authored data only. Four positive fixtures cover
GAT1.2, GND1.7, RSW1.9 and RSW2.7 with one model; their four final-byte
truncations throw RangeError and four bad signatures throw Error. Two further
constructor-return cases expose GAT unknown-type NaN and GND invalid-texture
undefined/NaN. The separate cross-realm and offset-view controls reproduce the
BinaryReader hazards above. All14fixture outcomes and two buffer controls
match root's source-derived checks; captured parser logs are empty. This is
real constructor execution on synthetic inputs, not retained-corpus parsing.

Private evidence, under ignored t06-map-parse-preparation-1/constructor-probe-1/:

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| probe.mjs |4426|374ee8b3eaa19d0d56464234d6e13969d0d51b7b17306cd70617a2f150b8691e|
| fixtures.json |35877|ed3ab386bb7bab04f6b56b6a89229464700dd4a3c4979c6e85e8ab7b4af22537|
| result.json |6795|319dc483ad1d8ddd1c093b0b82b5278da613871dc4368cd8f6b303c3111e071c|

Root reviewed the internal aide's metadata-only generator, then executed its
exact15045-byte draft4a0b1a6eb30257391521f1d744495e2ab67bf2bcb614e28692e3eeb934500910.
Its40,213,496-byte draft manifest a04ace8378b488a6b3391f552c0bc854965dd5e6924d103745ec3f9d0df430b8
repeats source request dictionaries. Root preserves that draft and makes a lean
canonical input using pinned report references rather than repeated copies.
The canonical retains every1296root, all3642observed core-edge references,
every82remaining gap and the sole qualified schg_dun01 GND overlay.

There are2761unique(kind,completeSHA) jobs:937RSW,889GAT and935GND, containing
5,166,030,083body bytes. Root independently rebuilt and compared every canonical
root membership/edge/original and selected source, job order/dedup/header/source
list and backreference directly against the original and target reports.
Root also freshly opened all2810selected physical body files without following
symlinks, checked regular-file type/size/full SHA and unchanged file identity:
5,227,319,159bytes in4.264seconds for the combined body-read and normalization
operation. All identities remain equal at the independent metadata check.
Original report validity remains false and unchanged; its separate prior
qualification is not rewritten. No parser ran on these retained bodies.

Private input/receipts, relative to t06-map-parse-preparation-1/:

| Artifact | Bytes | SHA256 |
| --- | ---: | --- |
| combined-parser-input-1.json |3711287|c2dd107007f21c6d12e46f93024137efea3967c9a9cb0614f37e4ecf9bbe09e7|
| root-body-audit-1.json |980974|f2a704531d35da97cab05b4a744f7300b803a4bcdf1b7057735a1553288d6a8d|
| root-manifest-admission-1.json |1102|010bd3c96c06e438746f15a2cd1b05576e72aababb412065588835893c1f428f|

The aide also supplied a source-only fixture plan (14198bytes,
242bb1731daf80b5a9eae53d432c7a5ea575e598727a3376562f1430d72aba47),
which root read. Its unexecuted recipes remain proposals except the separately
observed root cases above. Neither internal aide earns Claude/Grok credit.

A separate metadata aide reports zero draft relation errors across all1296roots,
3888edges,2761jobs,2810physical source records and3642backreferences. Root read
and pinned its2008-byte receipt manifest-metadata-aide-audit-1.json,
36ecc8980c67a5a3fe5a786fd47ee95d01d9c13abb0ba8192044b8395fb85516.
That aide did not read the generator implementation, canonical input or bodies;
its corroboration does not replace the root checks above.

Next owner root: freeze one bounded constructor-runner implementation task,
common summary/fixture oracles and resource/cleanup policy; dispatch independent
actual Claude/Grok implementations from the same committed base in separate
Orca worktrees. No .003 task is frozen or launched at this checkpoint. The
qualified input and authored probe save repeated acquisition/preparation work;
full parsing, compatible assets, dependencies, compile/render and ordinary
gameplay verification remain required. Parent T06 and the full goal stay open.
