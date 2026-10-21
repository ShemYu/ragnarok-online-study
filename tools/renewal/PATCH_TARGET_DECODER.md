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
python3 -I tools/renewal/test_decode_patch_targets.py
```

Standard library only. Exit 0 prints one path-free JSON status line on stdout
(`status`, `targets`, `decoded_bytes`, `manifest_sha256`); refusal exits 2 with
`{"status": "refused", "reason": <code>}` on stderr; wrong argument count exits 64.
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

## Not claimed

Native reader/binary parity, publisher application or winner order, dependency
closure, supported terrain versions, constructor/render/travel/save success and
full-map/full-game acceptance do not follow from twelve decoded bodies.
