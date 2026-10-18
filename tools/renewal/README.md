# Renewal project tools

Related tools have separate scope and input pins:

- [Immutable shipped-server snapshot](SERVER_SNAPSHOT.md) — T06.001.
- [Ordered stock map/NPC configuration selection](SERVER_SELECTION.md) — T06.002.001.
- [Traditional Chinese Carocc pilot](CAROCC_ZH_PILOT.md) — T05.001.

## Taiwan item table to UTF-8 source mod (T04.003)

`tw_iteminfo_utf8.py` turns the Taiwan client's compiled modern item table
(`System/iteminfo_new.lub`, Lua 5.1 bytecode) into a client-only mod whose
`System/itemInfo.lua` is plain UTF-8 Lua source. The client's loader then picks
its UTF-8 path for the whole file, so the Chinese text and Hangul resource names
(the item art) survive. Python 3 standard library only. Nothing is installed.

```sh
python3 -I tools/renewal/tw_iteminfo_utf8.py \
  /path/to/System/iteminfo_new.lub .tools/t04-003/out
python3 -I -m unittest discover -s tools/renewal
```

The output directory must not exist yet. Keep it under the ignored `.tools/`.
Publication creates the destination exclusively; an existing directory, file or
symlink is refused even if it appears during conversion. Use an output parent
you control. Staging is cleaned on failure; a copy I/O failure may leave an
incomplete new destination for inspection. Only use output after exit 0 and
manifest/hash verification; inspect or remove your failed output before retrying.
It holds:

```
out/
├── conversion-manifest.json      input hash, counts, output hashes, converter version
└── tw-iteminfo-utf8/             the mod folder
    ├── mod.json                  requires app >=1.6.3, era renewal, client twRO
    └── System/itemInfo.lua       tbl = { ... }, the final table
```

What it checks:

- Input must match the pinned SHA-256 `0c70abe6…2f19`. Any other file, including
  the legacy `iteminfo.lub`, is refused before parsing.
- The chunk header, every count and offset, and complete consumption are
  checked. Only literal table construction runs (`LOADK`, `NEWTABLE`,
  `SETTABLE`, `SETLIST`, `SETGLOBAL`, ...). Calls, jumps, upvalues and other
  instructions are refused. Function bodies are parsed but never run.
  An actual terminal no-value RETURN must be observed.
- Lua's last write wins for repeated keys, and assigning `nil` removes a key.
  Every string must be valid UTF-8. Shared or cyclic tables, non-finite numbers
  and badly shaped item entries are refused.
- For the pinned input it also requires 20442 items, 277 overwritten root
  assignments and 440663 UTF-8 strings.
- The written source is parsed back and compared with the rebuilt table
  before anything is written to disk.

Not checked here: actual loading in the app or in Lua (no Lua runtime is used),
icons, or gameplay. Root verifies those.
