# Raw static-spawn declaration pilot (T06.002.003.005.001)

`static_spawn_pilot.py` produces a lossless raw-byte inventory and a bounded
declared-field projection for exactly two selected Renewal NPC sources, in this
order: AntHell (`npc/re/mobs/dungeons/anthell.txt`, selection index 691) and
Prontera (`npc/re/mobs/fields/prontera.txt`, selection index 772). Profile
`static-spawn-raw-v1`; the frozen contract is
[the task brief](../../docs/project/tasks/T06.002.003.005.001.md). Python 3.9
standard library plus the unchanged `server_selection.py` reader. It compiles,
executes, decodes and joins nothing, and reads no app, VM, SQL, browser, cache,
save or network state.

```sh
python3 -I -B tools/renewal/static_spawn_pilot.py \
  --snapshot /abs/path/to/.tools/renewal/t06-candidates/integrated-2 \
  --selection-dir /abs/path/to/.tools/renewal/t06-selection-candidates/integrated-1 \
  --output /abs/path/to/.tools/renewal/T06.002.003.005.001/output
python3 -I -B tools/renewal/test_static_spawn_pilot.py
STATIC_SPAWN_FROZEN_ROOT=/abs/frozen-root \
  python3 -I -B tools/renewal/test_static_spawn_pilot.py
```

Roots may be relocated (for example to an immutable frozen copy with `snapshot/`
and `selection/` beneath one root); the pins and the two-file profile cannot.
There is no pin, file-list, limit, overwrite or environment option.
`STATIC_SPAWN_FROZEN_ROOT` is read only by the tests, which report the two
real-input tests as skipped without it.

## Exit status and files

The output directory must not exist; it is created `0700` beneath an existing
parent owned by you and not group/world writable, and must not lie inside an
input root. Keep it under the ignored `.tools/`; stock-derived output is never
committed.

```
output/                              0700, only 0600 regular files
├── source-lines.jsonl               every physical line, raw hex, span, terminator
├── static-spawn-pilot.jsonl         event partition of each source
├── static-spawn-pilot-manifest.json producer, input pins, sources, counters, limits
└── static-spawn-pilot-complete.json complete runs only, written last
```

| Exit | State | Files |
| --- | --- | --- |
| 0 | `complete`: both reconstructions exact, framing complete, every static declaration supported | all four |
| 1 | `qualified`: a local cutoff or a projection gap | both streams and manifest, **no marker** |
| 2 | fatal: prerequisite, admission, output cap or I/O failure | no usable output; an owned marker/manifest is revoked |

Exit status and files are authoritative; stdout is an incidental summary.
The 837 intentionally unscanned selected sources do not make the profile
qualified. Diagnostics are bounded and replace the given roots and home path.

## Prerequisite bridge

1. `server_selection.py` beside the producer must be 36455 bytes /
   `22a3f4c8…3c24417`. It is read once without following links and executed from
   those verified bytes; `read_snapshot` then runs with its default pins (all
   1683 files / 68752782 bytes, manifest `79ee4eff…41644c1dbd0`).
2. `selection-manifest.json` (953299 / `d62e31fd…631aec9a`) and
   `selection-complete.json` (185 / `26b9e804…b197`) are bounded no-follow
   regular-file reads, hash/size-checked before strict JSON decoding (duplicate
   keys, `NaN`/`Infinity`, exponent overflow such as `1e309` at any nesting
   depth, and bool-as-integer are refused).
3. The selection's generator, `source`, `profile` and `input` must bind the
   unchanged reader and the verified snapshot; status `complete`; exactly 839
   `npc_sources.files`, each with exactly the seven entry keys.
4. Each pilot source must occur exactly once (by source and manifest path) at its
   pinned index, equal its pinned entry, be selected by config line 21/104 of
   `npc/re/scripts_monsters.conf` (4089 / `c9d9e809…8a74`), and its snapshot
   bytes must match both the entry and the fixed pin.

`unscanned_selection_indices` lists the other 837 indices ascending. Map-cache
and monster-history joins are recorded as `not_performed`; neither artifact is
read.

## Framing summary

Physical lines end at each LF inclusive (CRLF kept together, a final unterminated
row is `none`). Events partition each nonempty source exactly once:
`whitespace` (maximal ASCII 09/0a/0b/0c/0d/20 runs), `line_comment` (`//` up to
the LF, including a CR), `block_comment` (nonnested `/* … */`), `static`
(`monster`/`boss_monster` header through its terminator), `opaque`
(`-<TAB>script<TAB>Name<TAB>-1,{` with header/open/body/close parts) and
`suffix` (everything from the first uncertified byte to EOF, with a reason and
detection cursor `fault_offset`).

- Global preflight: an initial UTF-8 BOM, any NUL or a bare CR turns the whole
  file into one suffix at the earliest hazard offset; the other file is still
  scanned.
- A header needs three TABs (`malformed_columns`), columns of at most 2047 bytes
  (`column_width`, fault at field start + 2047), and either a static keyword or
  the exact opaque form; anything else is `unsupported_construct`.
- The opaque body follows `npc_skip_script`/`skip_space` at the pinned revision:
  braces inside strings and comments are ignored; a backslash escapes the next
  byte only when the preceding raw byte is `<= 0x7e`. Authored stops:
  `unterminated_string|comment|brace` and escaped EOF at the file size,
  `escape_boundary`/`string_linebreak` at the LF, `nesting_cap` at the brace that
  would exceed 64.
- `line_width` is checked when classification first reaches a physical row whose
  payload exceeds 65536 bytes (fault row start + 65536). A whitespace run ends at
  that row; a comment or opaque block reaching it is cut from its opener/header.
- Caps reserve one suffix slot for every unfinished nonempty source:
  a candidate is admitted iff `emitted + 1 + unfinished_after ≤ framing_events`.
  A denied first candidate makes the whole file `not_scanned` (fault 0);
  otherwise `event_cap` at the candidate. `static_cap` stops at the next static
  candidate (checked before the event cap). Lexical stops keep their reason.

## Projection summary

Supported projections have all eleven slots (`declared`, `default` with null
span, or `absent` for an omitted event); a gap has `values: null` and exactly
one gap, the first failing check in the order `map_form, name_form, w4_form,
sprite_form, amount_form, delay_form, variance_form, event_form`.

| Field | Accepted (raw bytes, never decoded) |
| --- | --- |
| w1 | `map`, `map,x,y` or `map,x,y,xs,ys`; map `[A-Za-z0-9_]{1,11}` with optional case-insensitive `.gat` (literal kept); coordinates canonical int16, ≤ 6 bytes |
| w3 | 1–23 bytes, no comma/TAB/CR/LF/NUL |
| w4 | 2–5 comma tokens, no TAB: sprite (canonical unsigned ≤ 2147483647), amount (canonical int32), delay and variance (canonical unsigned ≤ 2147483647), event (1–76 bytes) |

Omitted coordinates default to 0, delay to 5000 and variance to 0; empty present
tokens are gaps, never defaults. Amount 0, negative or above 1000 is kept as a
declaration. A fifth token `1` is the event value `31`, not a boss flag; the
`boss_monster` keyword is source text, not database boss status.

## Limits

```json
{"completion_bytes":1048576,"each_jsonl_bytes":8388608,"framing_events":8192,"manifest_bytes":4194304,"nesting":64,"raw_lines":8192,"scanner_line_payload_bytes":65536,"source_file_bytes":262144,"source_total_bytes":524288,"static_declarations":4096}
```

These are authored bounds, not native limits or a memory promise. Per-file
size, total size, total physical lines (across both sources) and an event cap
below 2 are refused before any output; output-cap overruns are fatal.

## Publication

Every owned file is created with `O_EXCL|O_NOFOLLOW` mode `0600`, written with a
short-write loop (zero progress is an error), fsynced, closed and read back.
Readback checks the regular-file type, owned inode and exact `0600` mode before
and after the read. Before the final directory fsync/close, the publisher checks
the owned directory identity and `0700` mode, exact entry set and all file modes
and identities again. A late permission change is fatal, not silently repaired.
The marker binds the read-back manifest bytes and the stream pins and is written
last. On any later failure the marker and manifest are unlinked only if their
inode is still the one this run created; foreign replacements stay untouched.

A close error always fails publication. Before opening anything else, cleanup
checks whether the descriptor was released, still identifies the owned inode,
or is foreign/unknown. In the still-owned case it makes at most one guarded
additional close attempt; a final directory close failure retains that owned
handle for marker/manifest revocation before the additional close. An already
released directory may be reopened and rechecked for revocation. Foreign or
unknown descriptor slots are left untouched and reported; a persistent close
failure is reported as unresolved cleanup. These checks cover the authored
serial before/after-close and different-inode-reuse fixtures. Inode identity is
captured on entry to the close helper, which assumes its supplied descriptor
is still owned then. Post-error foreign/unknown preservation is not a guarantee
against reuse before that initial close. Inode identity is not descriptor-generation
proof against arbitrary concurrent or reentrant same-inode reuse, and the
metadata checks do not establish atomic protection
against all external races or universal native close-error recovery.

These are coordinator corrections to the selected Claude submission. Grok's
independent candidate already checked readback file modes; that useful control
is retained here alongside the additional identity and final-set checks.

## Tests

`test_static_spawn_pilot.py` covers families F01–F10 of the brief against the
real scanner and publication sinks: the three exact authored goldens (records,
sources, counters, stream pins, file modes, producer/input/marker binding),
defaults, opaque context, physical hazards, headers/columns, numeric/byte
subset, cutoffs, caps and reservations, prerequisite binding and publication
faults injected through the producer's raw OS-operation attributes (short and
zero writes, write/fsync errors, close before and after the real close, open/readback
failures, directory fsync/close, foreign collisions and replacements). Negative
controls run real tests under deliberate producer faults (CRLF normalization,
empty-token defaulting, event `1` as boss, suffix byte loss, opaque-body
monsters counted as static, deduplication, character-based name clipping) and
require each to fail before passing again on the baseline. With
`STATIC_SPAWN_FROZEN_ROOT`, the canonical run and tampered-copy refusals
(selection marker, one snapshot byte, one extra snapshot file) are exercised.

Coordinator-added regressions hold actual exception tracebacks while observing
owned descriptors before fixture cleanup. They cover before/after close on
source reads, stream readback, marker write/readback and final directory close;
combined read/close errors; controlled different-inode descriptor reuse;
readback permission changes; and nested positive/negative exponent overflow.
Foreign reuse fixtures check that the foreign descriptor remains open with its
original bytes. These controls do not certify arbitrary concurrent reuse.

## Not established

This is inspectable source evidence for two files only. It is not native
acceptance or membership, effective population or respawn, map-cell eligibility,
script-created/event/instance population (for example AntHell's opaque
`monster` command), rendered or Chinese names, story or episode completeness,
ordinary encounters, solo feasibility or full-milestone coverage. The other 837
selected sources and the map-cache/monster-history joins remain open.
