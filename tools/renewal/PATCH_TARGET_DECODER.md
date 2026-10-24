# Bounded twelve-target patch payload decoder (T07.007.003)

Version1.0.1 is the root-corrected implementation following unchanged Claude
integration300404a. Root verifies52tests/zero skips, all twelve shared refusal
controls, a fresh actual CLI/public consumer and every full body/typed artifact.
See the [task review](../../docs/project/reviews/2026-10-21-T07.007.003.md#root-corrected-integration-qualified). The raw submission remains separately retained.

`decode_patch_targets.py` decrypts and strictly unframes exactly the twelve
profile-admitted terrain payloads (four maps × GAT/GND/RSW) of official patch
9298 and publishes them as private files. It is a body gate before any native
target request. It is not an archive updater, extractor, map constructor or
playable-game qualification.

```sh
python3 -I tools/renewal/decode_patch_targets.py SOURCE_ROOT PATCH_9298 FRESH_OUTPUT
python3 -I tools/renewal/decode_patch_targets.py SOURCE_ROOT PATCH_9298 FRESH_OUTPUT --chapter1-rsw
python3 -I tools/renewal/decode_patch_targets.py SOURCE_ROOT PATCH_9298 FRESH_OUTPUT --remaining-rsw
python3 -I tools/renewal/test_decode_patch_targets.py
```

Version1.1.0 (T07.007.014.001 worker candidate) adds only the fixed
`--chapter1-rsw` route and its `verify_chapter1_rsw(output)` consumer; see
[Chapter 1 RSW route](#chapter-1-rsw-route-t07007014001). The twelve-target CLI,
`verify_payloads(output)`, schemas, count and semantics are unchanged; only the
truthful generator pin/version in a new legacy manifest changes with the source.

Version1.2.0 (T07.007.014.006 Claude worker candidate) adds only the fixed
`--remaining-rsw` route and its `verify_remaining_rsw(output)` consumer; see
[Remaining RSW route](#remaining-rsw-route-t07007014006). The twelve-target and
`--chapter1-rsw` routes, their consumers, pins, profiles, limits, row meaning and
failure behaviour are unchanged apart from the truthful generator pin/version.

Standard library only. Exit 0 prints one path-free JSON status line on stdout
(`status`, `targets`, `decoded_bytes`, `manifest_sha256`); refusal exits 2 with
`{"status": "refused", "reason": <code>}` on stderr; any argument shape other than
three positionals optionally followed by exactly one literal `--chapter1-rsw` or
`--remaining-rsw` (including
a flag before or between positionals, a repeated, combined, cased or `=`-valued
flag, any other flag, or a positional starting with `--`) exits 64 before any contract,
input or output is touched.
No body bytes, proprietary names or paths are printed.

## Fixed inputs

| Input | Pin | Source of truth |
|---|---|---|
| Profile | 8474 bytes, SHA256 `06805b0a…ead2a` | `docs/project/fixtures/T07.007.003-profile.json` |
| Authored vectors | 49381 bytes, SHA256 `d7011b6b…49a04` | `docs/project/fixtures/T07.007.003-authored.json` |
| Patch 9298 | 306097616 bytes, SHA256 `70725f66…f9f0e`, 46-byte header pin | profile `patch` (repeated in code) |
| Five primary sources | profile `source_pins` at `66ba94e2` | read below SOURCE_ROOT |

Profile and vectors are resolved from this checkout (`Path(__file__)`), never
the working directory. There are no command-line pin, target or limit
overrides. SOURCE_ROOT supplies only the five fixed relative paths, opened
component by component with `O_NOFOLLOW`; the directory is never listed. The
producer hashes all five before reading bodies, before completion and after the
normal consumer returns. Each bounded read checks the retained descriptor and
reopened fixed path, regular/single-link status, size, full hash and stable
identity/metadata; SOURCE_ROOT pathname identity is also checked. No source
collection is enumerated.

All fixed pins and all 252 + 4 authored known answers are checked before the
output directory is created. The initial patch descriptor is retained through decoding (`O_NOFOLLOW`, regular,
single link, exact size); its full SHA-256 is computed through that descriptor
while each admitted range is hashed as it streams past; the descriptor/path
identity is rechecked; the 46-byte header must match its pin and its 0x1xx/0x200
fields (`table_offset + 46`, `count − seed − 7`) must equal the profile's
`table_start`/`record_count`. Only header fields are used; the file table, the
legacy filename codec, aliases and winners are not parsed or discovered. After
the normal consumer, a second descriptor repeats the full hash/header/range
checks and must match the admitted original identity. This is a postcondition
check, not another decoded target set; the frozen manifest usage field continues
to report the admitted patch byte count. Constructor refusals close their owned
descriptor, including size, hard-link and full-hash refusals.

## Decryption

Independent implementation of `grf.rs` `read_entry` (632–682) and `des.rs` at
`66ba94e2`. Literal IP/FP/transposition/S-box/shuffle tables are transcribed
from `des.rs` (a port of the reference loader's `des.ts`); bit indexing,
byte-indexed permutation tables, round and block loops are this module's own.

- Mixed bit (0x02) wins over header bit (0x04); kind 7 decrypts as mixed.
- Header mode: the first 20 whole 8-byte blocks are transformed.
- Mixed mode: blocks 0–19 are transformed; afterwards a block whose index is a
  multiple of the cycle is transformed, and among the other blocks the counter
  starts at −1, so the 8th, 15th, … non-transformed block is de-shuffled.
- Cycle from the decimal digit count of `compressed_size`:
  1–2 digits → 1, 3–4 → digits+1, 5–6 → digits+9, ≥7 → digits+15.
- The whole aligned buffer is decrypted with `compressed_size` as cycle input;
  a partial tail block is unchanged. Kind 1 is an identity (no nibble codec).

## Strict framing (validator policy, not native behaviour)

The native reader truncates stored entries and otherwise runs uncapped zlib over
the whole aligned buffer without checking the decoded size. This tool refuses
more:

- `real_size == compressed_size`: stored; the body is the first `real_size`
  decrypted bytes.
- Otherwise only the first `compressed_size` decrypted bytes are inflated with an
  output cap of `real_size + 1`, no flush; the result must be exactly
  `real_size` bytes at stream EOF with a valid Adler-32, no unconsumed tail and
  no unused data (trailing bytes or a second stream) inside the declared span.
- Bytes after `compressed_size` are alignment padding. Their length and raw and
  decrypted SHA-256 are recorded; their values are not constrained and are never
  fed to the stream.
- The first four decoded bytes must equal the loader signature for the target
  kind (`GRAT` Altitude.js, `GRGN` Ground.js, `GRSW` World.js). The next two
  version bytes are recorded only; no supported-version or constructor claim.

Per-target aligned/real limits, cumulative aligned/decoded budgets and the output
cap come from the pinned profile `work_limits`.

## Output and consumer

FRESH_OUTPUT must not exist; its parent must. It is created 0700, and every
file is created `O_EXCL|O_NOFOLLOW` 0600 through the directory descriptor with
checked writes (zero or over-long write counts refuse; positive short writes
continue), fsync, close and full readback compared by inode, link count, mode
and bytes:

```
target-000.body … target-011.body   decoded bodies in profile order
payload-manifest.json               canonical JSON: generator/profile/vectors/
                                    source/patch pins, policy, limits, all
                                    target metadata plus raw-range, decrypted-
                                    range, compressed, raw/decrypted padding and
                                    decoded SHA-256/sizes, cycle, framing,
                                    magic/version prefix, cumulative usage
payload-complete.json               written last; binds manifest size/SHA
payload-failed.json                 path-free reason code; overrides completion
```

Before completion the producer rechecks patch descriptor/path identity and
closes it, rehashes the five sources, profile, vectors and generator, and checks
the output directory pathname/inode/mode and the exact file set and identities.
After writing the marker it checks the set again and runs the consumer. After
that callback, it repeats the source/profile/vector/generator and patch bindings,
then re-reads every created output with its recorded size/hash/inode, current
privacy/link/owner checks and stable before/after observations, with exact file
set and directory pathname checks on both sides. Write counts are checked against
the actual submitted chunk, rather than the larger remaining payload.

On refusal, partial files and foreign replacements are preserved; only a
completion marker whose inode this run created is removed. A retained verified
owned directory FD can revoke its marker and write failure even if its pathname
has been renamed/replaced; the replacement directory is not changed. Failure
cleanup refuses foreign marker inodes. Unexpected producer-body exceptions
become `internal-error` refusals, never success.

`verify_payloads(output)` is the read-only production consumer: it builds the
production contract from this checkout and requires a 0700 directory with the
exact fourteen 0600 single-link regular files (no failure marker), canonical
marker/manifest bytes, a fixed manifest section equal to one rebuilt from the
checkout profile/vectors/generator and fixed source provenance, per-row
metadata equal to the profile, consistent derived fields, and each body's full
size/SHA/magic/version prefix. Equality is recursive and type-sensitive: bool,
int and float are distinct, including nested target ranges, fixed sections,
marker fields and usage. Nonfinite JSON constants and overflowing float tokens
refuse. Rehashing a changed manifest into the marker
cannot bless changed targets, limits, policy, profile or malformed rows. It does
not reopen the external source files or the patch. The synthetic contract used
by the tests is private (`_verify_payloads(output, contract)`), and the public
consumer rejects synthetic provenance.

The consumer checks checkout profile/vector/generator bytes and identities before
and after verification. Its marker is bounded at 64 KiB, manifest at 1 MiB,
checkout reads at 16 MiB (profile/vector reads also require their exact pinned
sizes), and each body must have its admitted declared size before allocation.
Reads check retained FD and named-file stability; a second full sweep compares
every file identity, size and SHA with its first observation. Final pathname,
0700 privacy and exact file set are rechecked. The consumer is read-only and
does not remove pre-existing completion markers when it refuses.

## Root synthetic checks and limits

Root runs `-I -B -W error::ResourceWarning` with the admitted real-input
environment:52tests pass, zero skips or ResourceWarnings. The same twelve shared
fault intents all refuse, with zero observed FD leaks and preserved foreign
replacements. The actual fresh CLI and a separate ordinary production consumer
pass. Every complete body and entire canonical typed manifest/marker matches a
root reconstruction based on the earlier independent cipher/body reference.

Final directory close is inside the producer's refusal handler. On an ambiguous
close error the original numeric FD is never retried; safe failure cleanup may
reopen the original directory pathname only after proving its original inode,
privacy and owner. A foreign directory is preserved. A regression closes the
real directory then raises and verifies revoked owned completion/failure marker.
Readback also bounds allocation at16MiB before reading and opens nonblocking.

These are finite observations, not an atomic snapshot, arbitrary concurrent
same-user attack protection, post-return or crash/power-loss guarantees. An
ambiguous OS close may leave descriptor cleanup unproven; no broad FD retry is
claimed. The public profile/CLI/schema and target metadata remain fixed apart
from generator identity/version. No native reader is invoked by this tool.

## Chapter 1 RSW route (T07.007.014.001)

Qualified ledger gap47/root1256/cache1248 `ch1_que01` has one eligible exact RSW
record (ordinal 23) in patch 9298. `--chapter1-rsw` decodes only that record so
Root can later observe its embedded terrain names. It reuses the unchanged
cipher, framing, Patch, source, output and consumer machinery; there is no new
parser, archive table/name reader, discovery or extractor.

Each route is an immutable internal `Route` descriptor. A contract admits only a
descriptor value-identical to one of the built-ins (three since1.2.0) (`route-unknown`
otherwise) and binds it before any profile byte is parsed. A production contract
must use this checkout, the route's own profile pin, the fixed vectors pin and
the fixed patch/revision/header pins. The route then applies to profile
validation, producer output set, manifest/marker/failure schemas, totals,
preservation checks and the consumer.

| | Twelve-target (default) | `--chapter1-rsw` |
|---|---|---|
| Task | T07.007.003 | T07.007.014.001 |
| Profile | `T07.007.003-profile.json`, 8474 B, `06805b0a…ead2a` | `T07.007.014.001-profile.json`, 3415 B, `c47c0ebe…a8e2` |
| Profile schema | `ro-twelve-patch-payload-profile/1` | `ro-patch-payload-profile/2` |
| Manifest/complete/failed | `ro-twelve-patch-payload-{manifest,complete,failed}/1` | `ro-patch-payload-{manifest,complete,failed}/2` |
| Count / output | 12 / `target-000.body`…`target-011.body` | 1 / `target-000.body` |
| Kind labels | gat, gnd, rsw | rsw only (`profile-target-label`) |
| Consumer | `verify_payloads(output)` | `verify_chapter1_rsw(output)` |

New-route limits are repeated in the descriptor and must equal the profile
exactly (type-sensitive): aligned per target 65536, decoded per target and total
262144, output 1048576, read chunk 1048576. The pinned profile expects aligned
28696 / decoded 182666 bytes (compressed 28693, mixed kind 3, range
3767998–3796694, GRSW magic). Neither CLI nor consumer accepts a profile, path,
pin, count or limit override; no environment variable is read.

Worker checks are synthetic only: the old non-body suite is unchanged, and new
controls use the built-in chapter descriptor with a private synthetic profile and
patch (never the production CLI/consumer as a bypass). They cover one-record
producer+consumer, stored/zlib/padding, adler/trailer/concatenated/overlong/
short/truncated framing, wrong kind/range, old/new profile/schema/task/count/
marker/manifest cross-substitution in both directions, forged/unknown routes,
row/name/ordinal/range/kind/size/output-set mutations, late source/profile/
generator/vectors/body drift before completion and after the consumer, symlink/
hard-link/FIFO paths, existing-output sentinel, failed-marker precedence and
write/fsync/close/readback/final-directory-close faults. Each asserts its exact
refusal code. The production chapter contract is built from the frozen profile
and vectors (text/JSON only); the real archive and body are not read, and the
actual new route has not been run. Root performs the actual-body gate.

## Remaining RSW route (T07.007.014.006)

Root's exact selection from the qualified82-gap ledger leaves seventeen eligible
patch9298 RSW records whose bodies are not yet decoded: `1@ch1a`, `1@ch1b`,
`ch1_dw`, `ch1_geffen`, `ch1_gef_in`, `ch1_gfn01`, `ch1_gfn03`, `ch1_sf01`,
`ch1_sf02`, `ch1_sf03`, `ch1_vrgef1`, `ch1_vrgef2`, `hem_dun01`, `hem_dun02`,
`hem_fild`, `uknw_ruin`, `uknw_ruin2` (physical range order, ordinals2–5637).
The five already qualified bodies are not regenerated, and the four October-GRF
candidates are outside this patch-only route (no absence claim). `--remaining-rsw`
is a third built-in descriptor; it reuses the unchanged cipher, framing, Patch,
source, output and consumer machinery. There is no new parser, table/name
reader, discovery, fallback or retry.

| | `--remaining-rsw` |
|---|---|
| Task | T07.007.014.006 |
| Profile | `T07.007.014.006-profile.json`, 10759 B, `286680e5…8c19c` |
| Schemas | `ro-patch-payload-{profile,manifest,complete,failed}/2` (same family as Chapter 1) |
| Count / output | 17 / `target-000.body`…`target-016.body` |
| Kind labels | rsw only (`profile-target-label`) |
| Consumer | `verify_remaining_rsw(output)` |

The descriptor repeats the fixed caps, which must equal the profile exactly
(type-sensitive): aligned per target131072, decoded per target1048576, decoded
total8388608, output16777216, read chunk1048576. The pinned profile expects
aligned666248 / decoded4806359 bytes; every record is mixed kind3, compressed
5 digits (cycle14), GRSW magic, with the existing patch/header/source/vector pins.
Older-route caps are unchanged. Chapter 1 and remaining outputs share schemas but
are kept apart by task, profile path/pin, marker/usage count and exact file set.

Worker checks are synthetic only and leave the old suite unchanged. Seventeen-
record producer+consumer; descriptor and production-profile binding (text/JSON
only); forged descriptors (16/18 names, task, pin, path, labels, caps); 3×3
production profile/route cross-substitution; synthetic schema/task/count/cap
substitution in both directions with the chapter route; 16/18 targets, row
order/output/ordinal/name/label/kind/range, each cap ±1/float, per-target
budget and totals; a 6-digit-cycle target near the aligned ceiling plus stored
and kind7 rows; broken adler/trailer/short/magic at a chosen index that refuses
at that target's framing gate (counted); wrong kind/range; marker/manifest
rebinding (counts1/16/17.0/18, chapter task/path/caps, 16/18 rows, row swap);
missing/extra/renamed bodies; chapter/legacy outputs against the new consumer and
back; late body change after the consumer, completion-write/fsync/close faults
and generator drift, each leaving a failure marker with no completion that both
the synthetic and public consumers refuse; unknown/combined/cased flags. The
actual archive and bodies are not read and the actual route has not been run.
Root alone admits the actual seventeen-body run and observes embedded names with
the qualified RSW header reader; no same-stem terrain name is assumed.

The old suite needs umask077 (Root's environment): under umask022 its existing
`Chapter1RswConsumerTests.test_output_set_and_privacy` rewrites a body as 0644
and refuses at the privacy gate before the size gate. Unchanged; noted only.

## Not claimed

Native reader/binary parity, publisher application or winner order, dependency
closure, supported terrain versions, constructor/render/travel/save success and
full-map/full-game acceptance do not follow from twelve decoded bodies. The
Chapter 1 RSW route claims no embedded terrain names, map access or repair and
closes none of the 82 functional gaps. The remaining RSW route likewise claims no
embedded terrain names, terrain bodies, map entry/travel, Chapter 1 story or
progression, and closes none of the 82 functional gaps.
