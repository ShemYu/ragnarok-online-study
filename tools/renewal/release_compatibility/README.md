# 0.3.2 release compatibility gate (T10.010.005)

This is a read-only gate that runs outside the app, before install. It checks
one coherent release: the staged story folder `ro-solo-ch1-entry` 0.3.2 plus
the staged text folder `tc-true-quest-text` 0.1.0. It must pass before either
folder is installed through the app.

- The app's `requires` field only understands `app`, `era`, `mods` and
  `client`, so it cannot express a native-capability requirement.
- An app refusal can still leave a folder installed and enabled.

That is why the check lives outside the app and comes first. This is
source-phase work only: **real admission refuses today**. Only Root can
review and pin the runtime facts and records it needs.

| File | Purpose |
| --- | --- |
| `release_gate.py` | Python standard library only. Reads explicit regular files plus a bounded census of the two explicit staged roots, and prints one JSON result to stdout. Writes nothing. |
| `release_manifest_0.3.2.json` (schema v2) | The external release manifest: frozen source pins plus `null` expected pins. |
| `test_release_gate.py` | Authored synthetic controls (77 cases). |

```sh
python3 -I -B tools/renewal/release_compatibility/release_gate.py --packet /abs/packet.json
python3 -I -B -W error tools/renewal/release_compatibility/test_release_gate.py
```

Exit codes:

| Code | Meaning |
| --- | --- |
| `0` | `admitted` (real mode only), or `synthetic_consistent` |
| `1` | `refused` |
| `2` | Usage error |

`synthetic_consistent` is the best result in synthetic mode, and it is never
an admission.

## Trust model: independent expected pins

The caller's packet, record self-hashes, `qualified_by` labels, booleans and
provenance strings never qualify anything. Every file is compared against
the **manifest's own** expected pin:

- **Staged story files:** exact frozen 0.3.2 bytes.
- **Staged text table:** exact True-table bytes (2248204 B, `49264cdd…`).
- **Text `mod.json`:** pin is `null` until Root pins the qualified bytes.
- **App sources and native patch:** pinned.
- **Native subject:** `native.executable` bytes and SHA-256, stock
  executable, image ID and ABI/libraries.
- **`qualification_pins`:** the exact bytes of each Root-reviewed record:
  - `native.parser_log`, `native.qualification`, `effective.config`;
  - `effective.facts`, `text.reference`, `text.effective`.

Any `null` pin refuses, in both modes. In the checked-in real manifest, every
runtime and record pin is `null` today. Root fills them only in a separately
reviewed commit, after .004/.006 and .007's isolated qualification.

Because the record bytes themselves are pinned, a coherent change still
refuses as `release_pin_mismatch`, even when both records change together.
Examples are replacing or truncating a Description list, changing the
qualification ID, or swapping the executable or configuration in every
record. The semantic checks below then make sure the pinned records describe
the same subject:

- the executable, image, configuration and patch;
- the prepared source, scripts and quest DB;
- the item and import facts;
- the text table.

Synthetic tests author their own explicit pins in a synthetic manifest.
Real mode never accepts a substitute manifest.

## Packet (`ro-solo-release-admission-packet.v2`)

```json
{"schema": "ro-solo-release-admission-packet.v2", "record_class": "actual",
 "release_id": "ro-solo-ch1-entry@0.3.2+tc-true-quest-text@0.1.0",
 "roots": {"story": "/abs/…/ro-solo-ch1-entry", "text": "/abs/…/tc-true-quest-text"},
 "inputs": {"<role>": {"path": "/abs/file", "bytes": 0, "sha256": "…"}},
 "expected": {"selected_server": "…", "custom_quest_info": ["…"]}}
```

### Staged roots

The gate takes a bounded census of exactly the two named roots: at most 64
entries and a depth of 4. Nothing else is listed.

The root folder's name must be the mod name, because the app installs the
folder under its own name. Each root must hold exactly the following, with
no other file or directory:

| Root | Directories | Files |
| --- | --- | --- |
| story | `db`, `npc` | `mod.json`, `db/quest_db.yml`, `npc/entry.txt`, `npc/first_edge.txt`, `npc/fruit_village.txt` |
| text | `System` | `mod.json`, `System/OngoingQuestInfoList-tc-true-quest-text.lub` |

The census refuses:

- extra files or directories;
- missing files;
- symlinks (including the root or a parent of it);
- special files;
- an over-deep tree;
- a wrong folder name or layout.

It also refuses era or client overrides:

- any path segment named `re`, `pre-re`, `renewal`, `pre-renewal`,
  `prerenewal`, `when` or `client`;
- a `renewalFolder`, `prerenewalFolder` or `clientFolders` key in either
  `mod.json`.

The leaves are read from those roots. They are never taken from separately
listed paths.

### Explicit roles

- Six `app.*` sources.
- `native.patch`.
- `native.executable`, streamed.
- `native.parser_log`.
- `native.qualification`.
- `effective.config`, streamed: Root's exported effective map-server
  configuration artifact.
- `effective.facts`.
- `text.reference`.
- `text.effective`.

Unknown roles refuse.

## Input safety

Each input path must meet these conditions:

- It is absolute and normalized, with no symlink in any component.
- It is a regular file with `nlink == 1`.
- It is opened with `O_NOFOLLOW|O_NONBLOCK`.

A read refuses with `input_changed` on any observed change. The gate
compares three identities: the path's `lstat`, the descriptor before and
after the read, and a final path `lstat`. Each covers dev, inode, mode, size,
mtime and ctime, and the byte count read must match the size.

Reads are bounded:

| Input | How it is read | Size limit |
| --- | --- | --- |
| JSON records | buffered | 1 MiB |
| Story/app source | buffered | 1 MiB |
| Text table | buffered | 8 MiB |
| Parser log | buffered | 16 MiB |
| Effective configuration | streamed hash | 64 MiB |
| Executable | streamed hash | 1 GiB |

Numeric observations and pins must be exact integers. `true`/`false` or
`1.0` never equal `1`/`0`, because comparison is structural on canonical
JSON. Refusal reasons are capped at 64 entries of 240 characters each, plus a
truncation count. The result reports the gate, manifest, packet and every
input hash.

The image is bound by its pinned ID across the manifest and records. Pinned
Slim exposes no image save or export (`build_recipe.py` header), so the gate
does not hash an image archive.

## Record contract (Root supplies, reviews and pins)

Every record has `record_class` (`actual`; `synthetic` only in synthetic mode)
and the manifest `release_id`.

**`ro-solo-native-qualification.v1`**

- `qualification_kind: isolated_runtime`.
- `source`: rAthena `0693b8c6…`, prepared tree `b64e850b…`, patch, app
  commit and app tree.
- `executable`: `{bytes, sha256, patched: true}`, matching the supplied file.
- `image`: `{id, platform: linux/arm64}`.
- `packet_version: 20221005`.
- `abi`.
- `effective_config_sha256`: the supplied artifact.
- `parser`:
  - `method: isolated_map_server_load`.
  - `log_sha256`: the supplied log.
  - `loaded: true`, `errors: 0`, `release_warnings: 0`.
  - `scripts`: exactly the three staged NPC files and `db/quest_db.yml`, by
    hash.
- `builtin`: `ros_ch1_coin_capacity`, `registered: true`, `arguments: 0`,
  plus `probe_observations {fits: 1, no_fit: 0}`.
- `stock_control`: a different executable, `builtin_registered: false`,
  `release_rejected: true`.
- `stack_restrictions`.
- `max_amount`.

The gate also refuses a log containing a rejection marker such as
`parse_line` or `undeclared function` (`PARSER_REJECT_MARKERS`). This is a
screen only.

**`ro-solo-effective-facts.v1`**

- `environment`: the same executable, image and configuration.
- `item`:
  - Two distinct `alias_resolutions` of `Ch1_Root_Coin`, both giving
    1001972.
  - Etc, weight 1, stackable, non-GUID, non-pet.
  - Actual `stack_restrictions` and `max_amount`, equal to the native record.
- `maps`: the three maps, loaded.
- `connections`: the exact three exits.
- `npc_imports`: the three staged files.
- `quest_db.layers`: with boolean `clear` (no `true`), including the staged
  file.
- `quest_db.rows`: one each for 18368–18371, with the pinned Title hashes.
- `collisions`: none unresolved or non-identical.

**`ro-solo-quest-text-reference.v2`** is the separate full-reference
expectation.

- `complete: true`.
- `source_table` equal to the pinned and staged True table.
- `records` keyed by exactly the four IDs. Each has:
  - `title_sha256` and `summary_sha256`, equal to the frozen public hashes;
  - `description_sha256`: every Description element's hash, in order;
  - `description_elements`, equal to the list length.

The record's exact bytes are pinned independently. The manifest contains no
Description hash, and none is invented here.

**`ro-solo-text-effective.v1`**

- Same executable and configuration.
- `generated_resource` is the staged table.
- `selected_server` and the full ordered `custom_quest_info` equal the
  packet's `expected` values, which name the resource exactly once.
- `decoder {langtype: 4}`.
- `diagnostic_quest_ids` is exactly the four IDs.
- `records`: the four records' Title, Summary and Description hashes equal
  the pinned reference.

These records come from Root's isolated qualification of the same staged
bytes, not from the live install. Post-apply journal and rendering stays a
separate Root gate (see the
[0.3.2 runbook](../../../docs/project/runbooks/T10.010.005-0.3.2-release.md)).

## What a pass does and does not mean

The gate checks that independently pinned evidence is recorded
consistently. Root's review and pinning of actual records is the trust
anchor; the gate cannot tell whether an `actual` record is true. A pass is
the precondition for supported installation. It is not install, journal,
save, restart, withdrawal or play acceptance.
