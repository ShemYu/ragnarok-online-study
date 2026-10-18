# Stock map/NPC configuration selection (T06.002.001)

`server_selection.py` reads the canonical T06.001 snapshot
(`snapshot-manifest.json` plus `rathena/{conf,db,npc,sql-files}`) and publishes
the ordered map and NPC source selection that the rAthena map server's startup
configuration passes would build from those stock files. Python 3 standard
library only. It builds and runs nothing from rAthena, reads no installed app,
VM, SQL, browser or network state, and installs or removes nothing.

```sh
python3 -I tools/renewal/server_selection.py \
  /path/to/.tools/renewal/t06-candidates/integrated-2 \
  .tools/renewal/T06.002.001/output
RENEWAL_SELECTION_SNAPSHOT=/abs/path/to/integrated-2 \
  python3 -I -m unittest discover -s tools/renewal -p test_server_selection.py
```

Without `RENEWAL_SELECTION_SNAPSHOT` the pinned-input test looks for
`.tools/renewal/t06-candidates/integrated-2` in this checkout and is reported as
skipped when it is absent. The output directory must not exist; its parent must
exist, be owned by you and not be group/world writable. Keep it under the
ignored `.tools/`; stock-derived output is never committed.

```
output/
├── selection-manifest.json   deterministic selection (written and read back first)
└── selection-complete.json   written last: manifest SHA-256 and generator version
```

Without `selection-complete.json` the publication is incomplete. A published
report still needs `status: complete`: exit `0` means complete selection, exit `1`
means a published selection with missing/unsupported references, and exit `2`
means integrity/input/publication refusal. A failed run is never accepted merely
because a completion filename exists.

## Input checks

- `snapshot-manifest.json` must have SHA-256 `79ee4eff…41644c1dbd0` and list
  1683 files / 68752782 bytes. The CLI has no option to bypass the pin; lower
  level routines take a pin argument only for synthetic tests.
- The snapshot root must be a real directory. It is walked through no-follow
  directory descriptors: the regular-file set must equal the manifest's paths
  exactly (a stray `.DS_Store` fails), every size and SHA-256 must match, and any
  symlink, FIFO or other special entry is refused without being followed.
- All bytes are read once into memory; the model reads only those verified
  bytes. Logical paths are looked up as exact manifest keys, so a reference that
  differs only in case is reported as `case_mismatch` (Linux would not find it)
  instead of resolving through the case-insensitive macOS filesystem.

## Source profile

Pinned rAthena revision `0693b8c69911d5ca42269684aa036b67d67f4d3e`, read only:

| Rule | Source |
| --- | --- |
| Startup order: `map_config_read(MAP_CONF_NAME)` then `map_reloadnpc(false)` | `src/map/map.cpp:5414`, `5420` |
| Default map config `conf/map_athena.conf` | `src/common/cli.cpp:24` |
| Renewal NPC root `npc/re/scripts_main.conf`, no clear at startup | `src/map/map.cpp:4274–4284` |
| Map-config parser (`w1[32]`) and keys | `src/map/map.cpp:4130–4230` |
| NPC-config parser (`w1[1024]`), only `npc`/`delnpc`/`import` | `src/map/map.cpp:4232–4271` |
| `map_addmap` (`clear`, `MAX_MAP_PER_SERVER - 1` slots) / `map_delmap` (`all`, first match) | `src/map/map.cpp:3735–3778` |
| `mapindex_getmapname` (`.gat`, 11 bytes, case kept) | `src/common/mapindex.cpp:24–42`, `src/common/mmo.hpp:42,163–164` |
| `npc_addsrcfile` / `npc_delsrcfile`, `check_filepath` | `src/map/npc.cpp:3674–3709`, `src/common/utils.cpp:182–196` |

`db_path[12]` (`src/common/core.cpp:50`), `config_switch`
(`src/common/strlib.cpp:239–247`) and `vector_exists`/`vector_erase_if_exists`
(`src/common/utilities.hpp:211–251`) were also read; their hashes are recorded
as supplementary, not root-pinned. The source hashes are embedded in the report. The profile is the Renewal,
default-CLI, server-root working directory build described by that source; it
is **not** proof of the installed binary's compile options or command line.

## Modelled behaviour

- **Order.** The map pass reads `conf/map_athena.conf`; each `import:` is read
  recursively at its line position. Then the NPC pass reads
  `npc/re/scripts_main.conf` the same way, adding to the NPC list the map pass
  started (no clear). Import and NPC paths resolve relative to the server root
  (`rathena/`), never the importing file's directory.
- **Lines.** Exactly as the C code: a line starting `//` is skipped; otherwise
  the first `//` is replaced by a newline; `sscanf("%31[^:]: %1023[^\t\r\n]")`
  (width 1023 in the NPC pass) splits key and value; trailing spaces only are
  stripped. Keys compare ASCII case-insensitively but must match exactly, so
  ` map` and `map ` are unknown keys. A key that reaches the width without `:`
  is silently ignored (`ignored_key_overflow`). A `//` before the colon makes
  the key itself contain a newline and become unknown.
- **Refused input** (no output): physical records over 1023 bytes **including the
  newline** (fgets would split them), NUL or control bytes other than tab/CR/LF in a visited config
  file, non-ASCII recorded values, absolute paths, `..`, backslashes, import
  cycles, nesting deeper than 32 and more than 4096 visits.
- **Settings.** Values are kept only for `map`, `delmap`, `npc`, `delnpc`,
  `import`, `db_path` (also the effective 11-byte value) and `use_grf` (also the
  `config_switch` result, `null` for a numeric value not modelled). Every other
  key, whether recognised by the parser (including `userid`/`passwd`) or
  unknown, is recorded by key, count and locations only.
- **Maps.** Every addition is kept in order with its file and line, including
  duplicates. `map: clear` and `delmap: all` (any case) empty the list;
  `delmap` removes only the first exact normalized match. Names strip a final
  `.gat` in any case only when it is the full remaining C-string tail, then
  clip to 11 bytes and keep their case. A bounded prefix ending in .gat followed
  by more bytes is not a stripped suffix. The 1499-slot limit
  rejects further additions, which are listed separately. Distinct names are a
  separate list. These are configuration candidates, not loaded maps.
- **NPC sources.** `npc: clear` and `delnpc: all` (any case) empty the list. An
  existing regular file is added once per exact raw string, so `npc/x.txt`,
  `./npc/x.txt` and `npc/./x.txt` are distinct entries for one file (reported
  under `same_file_aliases`). `delnpc` removes only the identical raw string.
  A regular file followed by `/` or `/.` fails directory traversal and is not
  opened/selected. Valid directory aliases such as ./npc/./x.txt remain valid.
  Missing files, directories, case mismatches and paths outside the snapshot's
  four directories are not added and are reported with provenance.

## Report

`selection-manifest.json` (sorted keys, ASCII, no timestamps or host data)
contains the generator version and source hash, snapshot manifest hash, source
profile and assumptions, `status` (`complete` or `incomplete`), every config
visit (phase, raw and resolved path, depth, importing file/line, SHA-256, line
counts), every relevant event in order, the final map candidates and distinct
names, the NPC source files with manifest path, SHA-256 and provenance, the
`db_path`/`use_grf` settings, ignored settings, diagnostics and limits.

`incomplete` means at least one reference was missing, case-mismatched, a
directory, or outside the snapshot scope; the lists are still the modelled
result but must not be read as a full selection. Map capacity rejections are
modelled server behaviour and do not by themselves make the result incomplete.

## Limits

- Stock snapshot only: the installed Chinese pilot, app-generated
  configuration and any installed modification are not included.
- Counts of selected NPC source files are not NPC entity, spawn, monster, quest,
  warp, map-loaded or coverage totals. Script bodies are never parsed or copied.
- No map_index, map cache or GRF validation; no claim that any map loads.
- OnInit effects, visibility, YAML database definitions/imports and runtime
  exercised content are outside this child.
- Publication creates a private staging file, reserves the destination with an
  exclusive `mkdir`, moves the manifest in through directory descriptors, reads
  it back, and writes the completion record last. A concurrent writer running
  as the same user could interfere between those steps; on failure after the
  reservation an incomplete directory may remain for inspection. On write or
  readback failure the tool removes its completion marker through the owned
  directory descriptor. If the operating system also refuses that cleanup,
  the error explicitly says the marker could not be removed; that failed output
  must remain incomplete regardless of a filename's presence.

Version 1.0.1 includes coordinator fixes to the Claude candidate: terminal-file-dot,
fgets boundary, full-tail .gat diagnostics and completion failure regressions
were reproduced against the source profile before correction. Grok's correct
boundary/name behavior and explicit incomplete exit informed those corrections;
its independent candidate and comparison remain in project review history.
