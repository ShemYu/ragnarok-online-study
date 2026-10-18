# Shipped rAthena data snapshot (T06.001)

`server_snapshot.py` reads the app's packaged image archive
(`Ragnarok Offline.app/Contents/Resources/payload/dist/images.tar.gz`) and
publishes the final `rathena/{conf,db,npc,sql-files}` files of the image tagged
`ragnarokmac/rathena:20221005`, byte for byte, with a deterministic provenance
manifest. Python 3 standard library only. It runs no app, VM, container, SQL or
network step and installs nothing.

```sh
python3 -I tools/renewal/server_snapshot.py \
  "/path/to/Ragnarok Offline.app/Contents/Resources/payload/dist/images.tar.gz" \
  .tools/renewal/T06.001/output
RENEWAL_IMAGES_TAR=/path/to/images.tar.gz python3 -I -m unittest discover -s tools/renewal
```

The output directory must not exist yet; its parent must exist, be owned by you
and not be group/world writable. Keep it under the ignored `.tools/`. Generated
stock files must never be committed. It holds:

```
output/
├── snapshot-manifest.json     written last; its absence means incomplete output
└── rathena/
    ├── conf/ db/ npc/ sql-files/   final regular files only
```

## What it checks

- The input must be exactly 95222524 bytes with SHA-256 `d2487c40…f7dd8`, and
  the selected image must have the pinned config and seven layer digests. The
  CLI has no flag to bypass these pins.
- Every outer member name is checked: absolute paths, `..`, `.`, empty
  components, backslashes, NUL and non-UTF-8 names are refused, as are
  duplicate names after `./` normalization. Exactly one manifest entry may carry
  the tag. Config and layers must be regular `blobs/sha256/<digest>` members
  whose bytes hash to that digest, and config `rootfs.diff_ids` must equal the
  layer digests. `LayerSources`, when present, must agree.
- Layers are applied in manifest order. Within a layer, whiteouts are applied
  first and hide lower layers only: `.wh.<name>` removes that path and its
  subtree, `.wh..wh..opq` removes the lower children of its directory. Then the
  layer's entries apply in tar order: a directory merges into a lower directory;
  any other entry replaces what was there, including a whole directory subtree;
  the last definition in a layer wins.
- All whiteout markers must be empty, nonsparse regular files. Malformed
  types, payloads and unsupported marker names reject before changing lower-layer state,
  including out-of-scope markers. Duplicate JSON keys and
  nonobject `LayerSources` metadata reject explicitly. Input symlinks and
  nonregular files are refused without following them or blocking on a FIFO.
- Links and special files are never followed or created. A final link,
  hardlink, device, FIFO or sparse entry at `rathena`, a scope directory or any
  selected path is an error, as is a selected entry below a non-directory. The
  same out of scope is counted, and entries beneath such a non-directory are
  listed under `unresolved_out_of_scope` rather than resolved through the link.
- Paths that would collide on a case/normalization-insensitive filesystem are
  refused, including aliased directory prefixes and file/directory aliases.
  Both the resolver and publication preflight enforce this. Files are written
  into a private staging directory with
  `O_EXCL|O_NOFOLLOW` through directory handles, the destination is reserved with
  an exclusive `mkdir`, the tree is moved in, every file is read back and
  compared, and the manifest is written last.

`tarfile.extract`/`extractall` are never used. Archive modes, owners and times
are not restored: directories are created 0700 and files 0600.

## Manifest

Sorted JSON, no timestamps or host paths. It records the generator version and
source SHA-256; outer size/hash, tag, `manifest.json` hash, config digest and
each layer's digest, size and media type in order; per-layer member, whiteout
and selected-file counts; every published file's path, size and SHA-256 with
its source layer, original member name, member ordinal, occurrence within that
layer and number of earlier definitions; counts by scope directory; ignored
entry counts; unresolved paths; a `file_list_sha256` over `sha256  path` lines;
and the limits below.

## Pinned result

For the pinned archive the final layer defines every selected file:
96 conf, 293 db, 1182 npc and 112 sql-files regular files. These numbers are
comparison sentinels for this archive only. The tool does not enforce them, and
they are not monster, map, quest or story counts.

## Limits

- A snapshot of one packaged archive matching the installed release, not an
  independently reproduced build.
- File presence is not selected-for-load, actually-loaded, exercised or
  verified content.
- Empty directories, binaries, logs, saves and other trees are not written.
- Legacy `<id>/layer.tar` saves and compressed layers are refused.
- Tar data after a layer's end-of-archive marker is ignored.
- Within one layer, a child listed before its replacing directory entry, below
  a lower non-directory, is refused (selected) or unresolved (elsewhere).
- A concurrent writer running as the same user could interfere between the
  exclusive `mkdir` and the manifest write. On failure after the reservation,
  incomplete output without a manifest may remain; inspect or remove it before
  retrying. Staging is always removed.
- The whole outer archive, one layer and the selected file bytes are held in
  memory (487 MB peak resident size observed for the pinned input on macOS).
