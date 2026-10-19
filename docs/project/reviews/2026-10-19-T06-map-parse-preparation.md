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
