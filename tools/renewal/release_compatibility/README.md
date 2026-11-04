# 0.3.2 release compatibility gate (T10.010.005)

This is a read-only gate that runs outside the app, before install. It checks
one coherent release: story `ro-solo-ch1-entry` 0.3.2 plus text
`tc-true-quest-text` 0.1.0. It must pass before either folder is installed
through the app. The app's `requires` field only understands `app`, `era`,
`mods` and `client`, so it cannot express a native-capability requirement.
Also, an app refusal can still leave a folder installed and enabled. That is
why the check lives outside the app and comes first. This is source-phase
work only: **real admission refuses today**, and only Root can supply the
runtime facts it needs (after T10.010.004).

| File | Purpose |
| --- | --- |
| `release_gate.py` | Python standard library only. Reads explicit regular files and prints one JSON result to stdout. Writes nothing. |
| `release_manifest_0.3.2.json` | The external release manifest: frozen source pins plus `null` runtime slots. |
| `test_release_gate.py` | Authored synthetic controls (75 cases). |

```sh
python3 -I tools/renewal/release_compatibility/release_gate.py --packet /abs/packet.json
python3 -I -W error tools/renewal/release_compatibility/test_release_gate.py
```

Exit codes: `0` means `admitted` (real mode only). `1` means `refused`. `2` means
a usage error. In synthetic mode the best result is `synthetic_consistent`,
and that is never an admission.

## Modes and separation

- **Real mode** always uses the bundled manifest. It refuses `--manifest`
  overrides, synthetic manifests, packets or records, and any `null` runtime
  pin. The current manifest leaves these slots `null`: executable bytes and
  SHA-256, stock executable, image ID, ABI/libraries and effective
  configuration. Root fills them in a separately reviewed commit after .004.
- **Synthetic mode** needs `--synthetic --manifest <abs>` with
  `manifest_class: synthetic`. It also refuses `actual` records. Tests build
  their whole packet in a fresh temporary directory. Only the tracked story
  source and the native patch come from the checkout, and those are read-only.

## Input safety

The packet lists every input as `role -> {path, bytes, sha256}`. The gate
does no discovery, never lists a directory and accepts no unknown role.

Each path must meet these conditions:

- It is absolute and normalized, with no symlink in any component.
- It is a regular file with `nlink == 1`.
- It is opened with `O_NOFOLLOW|O_NONBLOCK`.
- Its `dev/ino` must match after opening, and it must not change size while
  being read.

Reads are bounded:

| Input | Size limit |
| --- | --- |
| JSON records | 1 MiB |
| Story/app source | 1 MiB |
| Text table | 8 MiB |
| Parser log | 16 MiB |
| Executable | 512 MiB (streamed, hash only) |

Every file must match both its packet pin and, where one exists, its manifest
pin. Refusal reasons are capped at 64 entries of 240 characters each, plus a
truncation count. The result also reports the gate, manifest, packet and
per-role input hashes.

## Required roles

- `story.mod_json`, `story.quest_db`, `story.npc.entry`,
  `story.npc.first_edge`, `story.npc.fruit_village`: exact staged 0.3.2
  bytes. These are pinned to frozen source `0a2a2494`.
- `text.mod_json` (equal to the frozen T10.008 manifest) and `text.table`
  (2248204 bytes, `49264cdd…bb805c00`).
- Six `app.*` sources, pinned to app `2c3b2612…`, tree `8cab4674…`.
- `native.patch`: `coin_capacity.patch`, pinned. `native.executable` is the
  actual patched map-server binary.
- `native.parser_log`: the raw log from the isolated load.
- `native.qualification`, `effective.facts`, `text.reference` and
  `text.effective`: the records described below.

## Evidence contract (Root supplies after .004)

Every record must have all of the following, or it is refused:

- `record_class` set to `actual` (or `synthetic` in synthetic mode).
- `qualified_by: "Root"`.
- A non-empty qualification or reference ID.
- The manifest `release_id`.

**`ro-solo-native-qualification.v1`**

- `qualification_kind: isolated_runtime`. Host fixtures do not qualify.
- `source`: rAthena revision `0693b8c6…`, prepared tree `b64e850b…`, patch
  SHA, app commit and app tree.
- `executable`: `{bytes, sha256, patched: true}`, matching the supplied
  binary.
- `image`: `{id: sha256:…, platform: linux/arm64}`.
- `packet_version: 20221005`.
- `abi`: `{libc, loader, libraries[{soname, sha256}]}`.
- `effective_config_sha256`.
- `parser`:
  - `method: isolated_map_server_load`.
  - `log_sha256` equal to the supplied log.
  - `loaded: true`, `errors: 0`, `release_warnings: 0`.
  - `scripts`: exactly the three staged NPC files plus `db/quest_db.yml`,
    with their hashes.
- `builtin`: `ros_ch1_coin_capacity`, `registered: true`, `arguments: 0`,
  plus `probe_observations {fits: 1, no_fit: 0}`.
- `stock_control`: a different executable with `builtin_registered: false`
  and `release_rejected: true`.
- `stack_restrictions`.
- `max_amount`.

The gate also refuses a log containing a rejection marker such as `parse_line`,
`undeclared function`, `Unknown command`, `script error` or `unknown item`
(the full list is `PARSER_REJECT_MARKERS` in the gate). This is a consistency
screen only.

**`ro-solo-effective-facts.v1`**

- `environment`: same executable, image and configuration as the native
  record.
- `item`:
  - At least two `alias_resolutions` from distinct sources, all giving
    `Ch1_Root_Coin -> 1001972`.
  - `type Etc`, `weight 1`, `stackable true`, `guid false`, `pet false`.
  - `stack_restrictions {amount, inventory, cart, storage, guild_storage}`
    and `max_amount`. Both must equal the native record. There is no modeled
    30000 default.
- `maps`: `prt_fild05`, `ygg_edge` and `ygg_fruit`, all `loaded`.
- `connections`: the three exits from `first_edge.txt` lines 129–138, each
  exactly once.
- `npc_imports`: the three staged files by hash, each exactly once.
- `quest_db`:
  - `layers`, each with a boolean `clear`. Any `true` refuses, and one layer
    must be the staged file.
  - `rows`: exactly one effective row for each of 18368–18371, with the
    pinned Title hash.
- `collisions`: `[]`, or entries that are `resolved` and `identical`.

**`ro-solo-quest-text-reference.v1`**

This is the explicit full-reference packet.

- `complete: true`.
- `source_table` equal to the pinned True table.
- `hash_basis`: SHA-256 of the UTF-8 encoding of each Big5-decoded field.
- For each of the four IDs: a Title and Summary equal to the frozen public
  hashes, plus a non-empty list of `description_sha256` element hashes.

The manifest holds no Description hash. If this record is absent or
incomplete, the gate refuses.

**`ro-solo-text-effective.v1`**

- Same executable and configuration as the native record.
- `generated_resource` is the staged table at
  `System/OngoingQuestInfoList-tc-true-quest-text.lub`.
- `selected_server` and the full ordered `custom_quest_info` both equal the
  packet's `expected` value, which names the resource exactly once.
- `decoder {langtype: 4}`.
- `diagnostic_quest_ids` is exactly `[18368, 18369, 18370, 18371]`. A
  diagnostic for 21001/16912 from `quest_registration_tail.js` does not
  count.
- `records`: the four records' Title, Summary and Description hashes equal
  the reference.

These records come from Root's isolated qualification of the same staged
bytes, not from the live install. The post-apply journal and rendering
checks are a separate Root gate (see the
[0.3.2 runbook](../../../docs/project/runbooks/T10.010.005-0.3.2-release.md)).

## What a pass does and does not mean

The gate checks that the evidence is recorded consistently. It does not
establish the facts behind it. A forged `actual` record can only be caught by
Root's qualification and pinning. A pass is the precondition for supported
installation. It is not install, journal, save, restart, withdrawal or play
acceptance.
