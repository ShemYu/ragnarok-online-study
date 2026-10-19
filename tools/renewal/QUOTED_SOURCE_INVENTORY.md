# Raw quoted occurrences in selected NPC sources (T06.004.001)

`quoted_source_inventory.py` scans every one of the 839 ordered
`npc_sources.files` entries of the pinned T06.002.001 selection, using the
verified bytes of the pinned T06.001 snapshot. It records each raw double-quoted
byte span under one frozen byte policy. Python 3.9+ standard library only. It
builds, runs, installs and changes nothing, and reads no app, VM, SQL, browser,
save, cache or network state.

This is a **source inventory**, not dialogue extraction. It does not model native
script framing, compilation, loading, event ownership, reachability, displayed
text, encoding or translation quality. Raw occurrence counts are not NPC, story,
quest or translation coverage.

```sh
python3 -I -B tools/renewal/quoted_source_inventory.py \
  --snapshot /abs/canonical/snapshot \
  --selection-dir /abs/canonical/selection \
  --output /abs/private-parent/new-output
TMPDIR=/abs/private/tmp QUOTED_SOURCE_FROZEN_ROOT=/abs/frozen-root \
  python3 -I -B tools/renewal/test_quoted_source_inventory.py
```

`QUOTED_SOURCE_FROZEN_ROOT` is used by tests only. Its `snapshot` and
`selection` children are the CLI inputs. Without it, the five actual-data tests
are skipped. The worker and the root reviewer must run them with it set. Tests
write only `mkdtemp` directories, so set `TMPDIR` to a private ignored
directory, for example under `.tools/`. The CLI has no pin, profile, limit or
input override.

## Input admission

| Input | Bytes | SHA-256 |
| --- | ---: | --- |
| `snapshot/snapshot-manifest.json` | 810498 | `79ee4eff2ed1621aa3be6247d0aedefc5f44abd65025617de652f41644c1dbd0` |
| `selection/selection-manifest.json` | 953299 | `d62e31fd601a879a9020eb0cbc79273cdaa38f11d6119af056b36727631aec9a` |
| `selection/selection-complete.json` | 185 | `26b9e804bd613fbf4ed1886d69ca8cf08ffc9c8b559db56b52c8bedd95ebb197` |
| `tools/renewal/server_selection.py` (reader) | 36455 | `22a3f4c8016e4e38608039084eb762440f9c56dd611e2af44be151fdf3c24417` |

- Every CLI path must be absolute, normalized and canonical. If `realpath` would
  change the path, it is refused, so a link anywhere in it is refused.
- The reader's bytes are read through a no-follow descriptor and must match the
  pin. The module is then compiled from those exact bytes. Only its
  `read_snapshot` is used: it walks the whole snapshot (1683 files /
  68752782 bytes) without following links and checks every size and hash.
- The selection directory must hold exactly the two files above as regular
  files. Links, FIFOs, extra entries (including `.DS_Store`) and missing files
  are refused. Reads are bounded, no-follow and nonblocking, and descriptors
  are closed on failure as well as on success. Both files are bound to their
  pins before JSON is parsed. Duplicate keys and NaN/Infinity are refused.
- The tool checks `status == "complete"`,
  `profile.name == "rathena-0693b8c-renewal-default-cli"`, that
  `input.snapshot_manifest_sha256` equals the snapshot manifest hash, and that
  the completion record's `selection_manifest`/`selection_manifest_sha256` bind
  that manifest. `npc_sources.files` must hold exactly 839 entries. Each entry
  has exactly `bytes,file,line,manifest_path,phase,sha256,source`, and its
  snapshot bytes must match `bytes` and `sha256`. Entries are copied unchanged,
  in order, into `selection`.

## Scanner policy (`scan_source`)

`scan_source(raw, *, max_bytes=8388608, max_occurrences=250000)` takes exact
`bytes`. The limits must be exact non-boolean `int`s from 0 through their
defaults; any other value raises `InventoryError`. It returns
`{occurrences, known_prefix_end, gap}`. Each occurrence is
`{literal_index, span, content_span, content_hex}`: offsets are zero-based and
end-exclusive, and the hex is the lowercase, undecoded content bytes.

1. Outside quotes, `//` runs through LF or the actual EOF. A bare CR does not end
   it. `/*` runs through the first `*/`, without nesting.
2. Byte `0x22` opens and closes a quote. Inside a quote, comment markers are
   content, and `'` is always plain.
3. Inside a quote, `0x5c` shields the next byte only when the **raw byte before
   the backslash** is `<= 0x7e`. The pair is consumed once. This means a Big5
   trail byte `0x5c` after a high lead byte is not an escape. No escape is
   decoded.
4. LF, CR, NUL, BOM and high bytes are plain data.

On true EOF, an open quote (including a trailing eligible backslash) gives
`unterminated_quote` from the opening quote. An open block comment gives
`unterminated_block_comment` from `/*`. Only `raw[:max_bytes]` is examined. A
comment opener split by the boundary is a plain slash. A shorter budget gives
`byte_limit`, starting at the unfinished quote or comment, or else at the
boundary. If `max_occurrences` is already reached, the next quote opener gives
`occurrence_limit`. Every gap ends at `len(raw)`, and `known_prefix_end` equals
the gap start.

Under this policy, an unquoted header `//` can hide later quotes, and a quoted
span can cross a native newline or NUL. Most unquoted names and all dynamic
text are outside this slice.

## Output

The output is a new `0700` directory with `0600` files. It is created
exclusively under an existing parent that you own, that has mode `0700`, and
that lies outside both inputs:

```
quoted-sources.jsonl      839 rows {source_index,selection,known_prefix_end,gap,occurrence_count}
quoted-occurrences.jsonl  global rows {occurrence_index,source_index,literal_index,span,
                          content_span,content_hex,start_line,end_line}
quoted-manifest.json      schema/task/profile/state/producer/inputs/outputs/counts/limits/claims
quoted-complete.json      written last; binds the manifest bytes/hash and both outputs
```

`start_line` and `end_line` are 1 plus the number of LFs strictly before the
opening and closing quote bytes. All JSON is compact, uses sorted keys, is
ASCII-only, contains no NaN and ends each object with one LF. The output holds
no timestamps or machine paths. `state` is `complete` only when every source
has `gap: null`. The marker records whether a report was published; it does not
make an incomplete report complete. Global caps are fatal and never truncate
the output: 2000000 total occurrences, and 536870912 bytes across the two
streams.

Each file is created `O_EXCL|O_NOFOLLOW`, written, fsynced, closed and read back
(size and SHA-256), and the marker is written last. On failure, the tool
removes, marker first, only the files this run created whose `(dev, ino)` still
match. It then removes the directory if it is empty. Foreign or replaced data is
kept and reported.

Exit codes: `0` means a published report (stdout is a JSON summary with `state`,
`counts` and `manifest_sha256`). `2` means admission, cap or publication
failure (`error:` on stderr), with no usable marker.

## Tests

- All 38 authored fixture cases match as whole objects (the fixture's bytes and
  SHA-256 are checked). They also match an independent byte-at-a-time reference
  scanner in the test file.
- Five textual mutations of the real scanner must each fail at least one fixture
  case: unconditional escape, quotes inside comments, deduplication, an ignored
  byte budget and a last-`*/` block close.
- The tests cover invalid types and limits; distinctions between escapes,
  comments, headers, CR/LF/NUL/BOM and high bytes; every byte boundary of a
  mixed sample; both limit boundaries and their coincidence; and 4000 seeded
  random inputs compared with the reference.
- Producer tests cover line, index, count and hash conservation; document
  shapes; fatal caps; selection field refusals; strict JSON; the reader pin and
  links; selection directory refusals with descriptor-leak checks; output path
  refusals; and failure injection: write failure, read-back mismatch, foreign
  data and a replaced artifact.
- The actual-data tests run the real CLI on all 839 entries. Every source row
  and every occurrence row is compared with the reference scanner and the
  snapshot bytes. They also cover a deterministic rerun, eleven CLI refusals
  (existing output, relative paths, linked roots and members, a tampered pin,
  an extra member, a fake snapshot, swapped inputs, output inside inputs),
  in-process marker write failure, and mutants that change actual results.

Observed on the pinned inputs: all 839 sources complete, with 402809
occurrences. Only 7 backslashes occur inside quoted content, and none follows a
byte `> 0x7e`. The escape-eligibility rule is therefore pinned by the fixture,
not exercised by the actual data.
