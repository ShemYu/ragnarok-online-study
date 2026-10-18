#!/usr/bin/env python3
"""Publish an immutable snapshot of the shipped rAthena conf/db/npc/sql-files tree.

The input is the app's packaged Docker-save/OCI image archive (`images.tar.gz`).
It is read into memory, checked against the pinned size and SHA-256, and never
extracted with tarfile's extract helpers. The one image tagged
`ragnarokmac/rathena:20221005` is selected; its config and every layer blob are
hashed before use. Layers are applied in manifest order with replacement and
OCI whiteout semantics (`.wh.<name>`, `.wh..wh..opq`), and only final regular
files below `rathena/{conf,db,npc,sql-files}/` are written, byte for byte,
together with a deterministic provenance manifest.

File presence says nothing about which files the server selects, loads or
exercises. Standard library only. Output directories are never overwritten.
"""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import stat
import sys
import tarfile
import tempfile
import unicodedata

VERSION = "1.0.0"
PINNED_OUTER = {"bytes": 95222524,
                "sha256": "d2487c4047bca8451155939d3f9778777279d07e4bdf7faeeabf5f1ea91f7dd8"}
PINNED_TAG = "ragnarokmac/rathena:20221005"
PINNED_IMAGE = {
    "config": "dc015ffa72b9bc848b0ab3115f3d4e45d4b8f95c475dbe10c810b8ca190f79f2",
    "layers": (
        "18932007cc273c0541920263e57c02d40013c4730d7db35437a4ffcc31422eda",
        "50d87e28e2dc84464a2f331f7190fec2ab7d673c46abf5b1c686afaa9a01acb1",
        "5f70bf18a086007016e948b04aed3b82103a36bea41755b6cddfaf10ace3c6ef",
        "9b663d9f899d3cc69891859cc39e6b1a6a0a2dc6e7b1f13274de007b9d88b33f",
        "d4294518116649d5313d3253b6ef8155955b1590ec905906e9e031896cce9c66",
        "4466a9c329dabf10bbb8640ad0f07488d707a01cdd4fb05cb30882de4aad0418",
        "5fd8afb703822a56c244eff4ce950658a425d16279d81d8e1bb53446cef24ea2",
    ),
}
SCOPE_ROOT = "rathena"
SCOPE_DIRS = ("conf", "db", "npc", "sql-files")
MANIFEST_NAME = "snapshot-manifest.json"
MAX_JSON = 1 << 20
MAX_BLOB = 1 << 30
BLOB_REF = re.compile(r"blobs/sha256/([0-9a-f]{64})\Z")
WHITEOUT = ".wh."
OPAQUE = ".wh..wh..opq"
LIMITS = (
    "Snapshot of one packaged image archive matching the installed release; not an "
    "independently reproduced build of rAthena or of the image.",
    "File presence is not selected-for-load, actually-loaded, exercised or verified "
    "content, and file counts are not monster, map, quest or story counts.",
    "Only final regular files below rathena/{conf,db,npc,sql-files}/ are published. "
    "Empty directories, binaries, logs, saves and all other trees are counted, not written.",
    "Archive ownership, modes and timestamps are not restored; output uses private "
    "permissions (directories 0700, files 0600, further reduced by umask).",
    "Archive links and special files are never followed or recreated. Any final link or "
    "special entry at or above a selected path is an error; elsewhere they are counted.",
    "Out-of-scope entries under a non-directory (for example a symlinked ancestor) are "
    "skipped and listed as unresolved instead of being resolved through the link.",
    "Layer blobs must be uncompressed tar named blobs/sha256/<digest>, with config "
    "rootfs.diff_ids equal to the layer digests. Legacy <id>/layer.tar saves are refused.",
    "Member names with backslashes, NUL, non-UTF-8 bytes, absolute paths, empty, '.' or "
    "'..' components are refused anywhere in the outer archive or any applied layer.",
    "Tar data after a layer's end-of-archive marker is ignored, as tar readers do.",
    "Published paths that collide under case or Unicode normalization are refused, "
    "because the default macOS filesystem would merge them.",
    "Publication reserves the destination with an exclusive mkdir, then moves the staged "
    "tree in and writes the manifest last. A concurrent writer running as the same user "
    "could interfere between those steps; without the manifest the output is incomplete.",
)


class SnapshotError(ValueError):
    """Input or output that cannot be snapshotted without guessing."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def normalize_member(name, where):
    """Return a safe relative archive path ('' for the root) or raise."""
    if "\\" in name or "\0" in name:
        raise SnapshotError(f"{where}: unsafe member name {name!r} (backslash or NUL)")
    try:
        name.encode("utf-8")
    except UnicodeEncodeError:
        raise SnapshotError(f"{where}: member name {name!r} is not UTF-8") from None
    if name.startswith("/"):
        raise SnapshotError(f"{where}: absolute member name {name!r}")
    path = name
    while path.startswith("./"):
        path = path[2:]
    path = path.rstrip("/")
    if path in ("", "."):
        return ""
    if any(part in ("", ".", "..") for part in path.split("/")):
        raise SnapshotError(f"{where}: unsafe member name {name!r}")
    return path


def open_tar(data, mode, where):
    try:
        return tarfile.open(fileobj=io.BytesIO(data), mode=mode)
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise SnapshotError(f"{where}: not a readable tar archive: {exc}") from None


def tar_members(tf, where):
    try:
        return tf.getmembers()
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise SnapshotError(f"{where}: unreadable tar archive: {exc}") from None


def read_regular(tf, info, where, limit):
    if not info.isreg() or info.sparse is not None or info.type == tarfile.GNUTYPE_SPARSE:
        raise SnapshotError(f"{where}: {info.name!r} is not a regular file")
    if info.size > limit:
        raise SnapshotError(f"{where}: {info.name!r} is larger than {limit} bytes")
    try:
        data = tf.extractfile(info).read()
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise SnapshotError(f"{where}: cannot read {info.name!r}: {exc}") from None
    if len(data) != info.size:
        raise SnapshotError(f"{where}: {info.name!r} is truncated")
    return data


# --- Outer archive and image selection ------------------------------------------

def read_outer(path, pin=PINNED_OUTER):
    """Read the outer archive once and return its bytes after the size/hash pin."""
    with open(path, "rb") as handle:
        info = os.fstat(handle.fileno())
        if not stat.S_ISREG(info.st_mode):
            raise SnapshotError(f"input is not a regular file: {path}")
        if info.st_size != pin["bytes"]:
            raise SnapshotError(f"input is {info.st_size} bytes, pinned archive is {pin['bytes']}")
        data = handle.read(pin["bytes"] + 1)
    if len(data) != pin["bytes"]:
        raise SnapshotError("input changed size while being read")
    digest = sha256(data)
    if digest != pin["sha256"]:
        raise SnapshotError(f"input SHA-256 {digest} is not the pinned archive {pin['sha256']}")
    return data


class OuterArchive:
    """Validated member index of the outer image archive."""

    def __init__(self, data):
        self.tf = open_tar(data, "r:*", "outer archive")
        self.members = {}
        for info in tar_members(self.tf, "outer archive"):
            path = normalize_member(info.name, "outer archive")
            if path in self.members:
                raise SnapshotError(f"outer archive: duplicate member {path!r}")
            self.members[path] = info

    def read(self, path, limit):
        info = self.members.get(path)
        if info is None:
            raise SnapshotError(f"outer archive: missing member {path!r}")
        return read_regular(self.tf, info, "outer archive", limit)

    def blob(self, ref, what):
        """Return (digest, bytes) of a referenced blob after checking its digest."""
        match = BLOB_REF.match(ref) if isinstance(ref, str) else None
        if not match:
            raise SnapshotError(f"{what}: unsupported blob reference {ref!r}")
        data = self.read(ref, MAX_BLOB)
        digest = sha256(data)
        if digest != match.group(1):
            raise SnapshotError(f"{what}: blob {ref} has SHA-256 {digest}")
        return digest, data


def load_json(data, what):
    try:
        return json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise SnapshotError(f"{what}: invalid JSON: {exc}") from None


def select_image(manifest, tag):
    if not isinstance(manifest, list) or not all(isinstance(e, dict) for e in manifest):
        raise SnapshotError("manifest.json is not a list of image entries")
    matches = [e for e in manifest
               if isinstance(e.get("RepoTags"), list) and tag in e["RepoTags"]]
    if len(matches) != 1:
        raise SnapshotError(f"manifest.json has {len(matches)} images tagged {tag!r}, expected 1")
    entry = matches[0]
    if not isinstance(entry.get("Layers"), list) or not entry["Layers"]:
        raise SnapshotError(f"image {tag!r} has no layer list")
    return entry


# --- Layer resolution -------------------------------------------------------------

def selected(path):
    """True for paths strictly below rathena/<scope dir>/."""
    parts = path.split("/")
    return len(parts) >= 3 and parts[0] == SCOPE_ROOT and parts[1] in SCOPE_DIRS


def affects_selection(path):
    """True for the root, rathena, a scope dir, or anything below a scope dir."""
    parts = path.split("/") if path else []
    return (not parts or (parts[0] == SCOPE_ROOT and (len(parts) == 1 or parts[1] in SCOPE_DIRS)))


def entry_kind(info):
    if info.isdir():
        return "dir"
    if info.isreg() and info.sparse is None and info.type != tarfile.GNUTYPE_SPARSE:
        return "file"
    if info.issym() or info.islnk():
        return "link"
    return "special"


class Tree:
    """Merged filesystem view. Paths map to dicts with a 'kind' and provenance."""

    def __init__(self):
        self.nodes = {}
        self.defined = {}
        self.unresolved = []
        self.layers = []

    def _remove(self, path, with_self=True):
        if path == "":
            removed = list(self.nodes)
        else:
            prefix = path + "/"
            removed = [p for p in self.nodes if p.startswith(prefix)]
            if with_self and path in self.nodes:
                removed.append(path)
        for p in removed:
            del self.nodes[p]
        return len(removed)

    def _replace(self, path):
        node = self.nodes.get(path)
        if node is None:
            return
        if node["kind"] == "dir":
            self._remove(path)
        else:
            del self.nodes[path]

    def _parents(self, path):
        """Ensure ancestor directories exist. Return False if one is not a directory."""
        parts = path.split("/")
        for depth in range(1, len(parts)):
            ancestor = "/".join(parts[:depth])
            node = self.nodes.get(ancestor)
            if node is None:
                self.nodes[ancestor] = {"kind": "dir"}
            elif node["kind"] != "dir":
                if affects_selection(ancestor) or selected(path):
                    raise SnapshotError(f"{path!r} lies under non-directory {ancestor!r} "
                                        f"({node['kind']}); links are never followed")
                self.unresolved.append(path)
                return False
        return True

    def apply_layer(self, index, digest, data):
        """Apply one uncompressed layer tar on top of the current tree."""
        where = f"layer {index} ({digest[:12]})"
        tf = open_tar(data, "r:", where)
        entries, seen = [], {}
        stats = {"index": index, "digest": digest, "members": 0, "whiteouts": 0,
                 "opaque": 0, "removed_by_whiteout": 0, "selected_files": 0}
        for ordinal, info in enumerate(tar_members(tf, where)):
            path = normalize_member(info.name, where)
            seen[path] = seen.get(path, 0) + 1
            entries.append((ordinal, seen[path], path, info))
        stats["members"] = len(entries)

        # Whiteouts hide lower layers only, so apply them before this layer's entries.
        for _, _, path, info in entries:
            parent, _, base = path.rpartition("/")
            if not base.startswith(WHITEOUT):
                continue
            stats["whiteouts"] += 1
            if base == OPAQUE:
                stats["opaque"] += 1
                stats["removed_by_whiteout"] += self._remove(parent, with_self=False)
            elif base.startswith(WHITEOUT + WHITEOUT) or base[len(WHITEOUT):] in ("", ".", ".."):
                if affects_selection(parent):
                    raise SnapshotError(f"{where}: unsupported whiteout marker {path!r}")
                self.unresolved.append(path)
            else:
                target = (parent + "/" if parent else "") + base[len(WHITEOUT):]
                stats["removed_by_whiteout"] += self._remove(target)

        for ordinal, occurrence, path, info in entries:
            base = path.rpartition("/")[2]
            if path == "":
                if not info.isdir():
                    raise SnapshotError(f"{where}: archive root entry is not a directory")
                continue
            if base.startswith(WHITEOUT):
                self._parents(path)
                continue
            if not self._parents(path):
                continue
            kind = entry_kind(info)
            existing = self.nodes.get(path)
            self.defined[path] = self.defined.get(path, 0) + 1
            if kind == "dir":
                if existing is None or existing["kind"] != "dir":
                    self._replace(path)
                    self.nodes[path] = {"kind": "dir"}
                continue
            self._replace(path)
            node = {"kind": kind, "layer": index, "layer_digest": digest,
                    "member": info.name, "ordinal": ordinal, "occurrence": occurrence,
                    "earlier_definitions": self.defined[path] - 1}
            if kind == "link":
                node["linkname"] = info.linkname
            if kind == "file" and selected(path):
                node["data"] = read_regular(tf, info, where, MAX_BLOB)
                stats["selected_files"] += 1
            self.nodes[path] = node
        self.layers.append(stats)

    def selected_files(self):
        """Check the final tree and return {path: node} for published files."""
        for path in [SCOPE_ROOT] + [f"{SCOPE_ROOT}/{d}" for d in SCOPE_DIRS]:
            node = self.nodes.get(path)
            if node is not None and node["kind"] != "dir":
                raise SnapshotError(f"final {path!r} is a {node['kind']}, not a directory")
        files = {}
        for path, node in self.nodes.items():
            if not selected(path) or node["kind"] == "dir":
                continue
            if node["kind"] != "file":
                raise SnapshotError(f"final selected path {path!r} is an unsupported "
                                    f"{node['kind']} entry")
            files[path] = node
        return files

    def ignored_counts(self):
        counts = {}
        for path, node in self.nodes.items():
            if selected(path) and node["kind"] == "file":
                continue
            group = "selected_directories" if selected(path) else f"out_of_scope_{node['kind']}"
            counts[group] = counts.get(group, 0) + 1
        return dict(sorted(counts.items()))


def resolve_layers(layers):
    """Apply [(digest, uncompressed tar bytes), ...] in order. Return the Tree."""
    tree = Tree()
    for index, (digest, data) in enumerate(layers):
        tree.apply_layer(index, digest, data)
    return tree


def check_collisions(paths):
    seen = {}
    for path in paths:
        key = unicodedata.normalize("NFC", path).casefold()
        if key in seen:
            raise SnapshotError(f"paths {seen[key]!r} and {path!r} collide on a "
                                "case/normalization-insensitive filesystem")
        seen[key] = path


# --- Snapshot build ---------------------------------------------------------------

def build_snapshot(data, tag=PINNED_TAG, expect=PINNED_IMAGE, generator_sha256=None):
    """Return (files {path: bytes}, manifest dict) from verified outer archive bytes."""
    outer = OuterArchive(data)
    manifest_bytes = outer.read("manifest.json", MAX_JSON)
    entry = select_image(load_json(manifest_bytes, "manifest.json"), tag)
    config_digest, config_bytes = outer.blob(entry.get("Config"), "image config")
    config = load_json(config_bytes, "image config")
    refs = entry["Layers"]
    digests = []
    for ref in refs:
        match = BLOB_REF.match(ref) if isinstance(ref, str) else None
        if not match:
            raise SnapshotError(f"layer: unsupported blob reference {ref!r}")
        digests.append(match.group(1))
    if expect is not None and (config_digest != expect["config"]
                               or tuple(digests) != tuple(expect["layers"])):
        raise SnapshotError("selected image config/layers differ from the pinned image")
    rootfs = config.get("rootfs") if isinstance(config, dict) else None
    diff_ids = rootfs.get("diff_ids") if isinstance(rootfs, dict) else None
    if diff_ids != ["sha256:" + d for d in digests]:
        raise SnapshotError("config rootfs.diff_ids do not equal the uncompressed layer digests")
    sources = entry.get("LayerSources") or {}
    if not isinstance(sources, dict):
        raise SnapshotError("LayerSources is not an object")

    tree, layer_records = Tree(), []
    for index, ref in enumerate(refs):
        digest, layer = outer.blob(ref, f"layer {index}")
        source = sources.get("sha256:" + digest, {})
        if source and (not isinstance(source, dict)
                       or source.get("digest") != "sha256:" + digest
                       or source.get("size") != len(layer)):
            raise SnapshotError(f"layer {index}: LayerSources entry disagrees with the blob")
        tree.apply_layer(index, digest, layer)
        layer_records.append({"index": index, "digest": "sha256:" + digest,
                              "bytes": len(layer), "media_type": source.get("mediaType")})
        del layer

    nodes = tree.selected_files()
    if not nodes:
        raise SnapshotError("no regular files below the selected rathena directories")
    check_collisions(nodes)
    files = {path: node["data"] for path, node in nodes.items()}
    by_dir = {d: {"files": 0, "bytes": 0} for d in SCOPE_DIRS}
    records = []
    for path in sorted(nodes):
        node, body = nodes[path], files[path]
        group = by_dir[path.split("/")[1]]
        group["files"] += 1
        group["bytes"] += len(body)
        records.append({
            "path": path, "bytes": len(body), "sha256": sha256(body),
            "source": {"layer": node["layer"], "layer_digest": "sha256:" + node["layer_digest"],
                       "member": node["member"], "member_ordinal": node["ordinal"],
                       "occurrence_in_layer": node["occurrence"],
                       "earlier_definitions": node["earlier_definitions"]},
        })
    tree_digest = sha256("".join(f"{r['sha256']}  {r['path']}\n" for r in records).encode("utf-8"))
    for stats in tree.layers:
        stats["digest"] = "sha256:" + stats["digest"]
    manifest = {
        "generator": {"tool": "tools/renewal/server_snapshot.py", "version": VERSION,
                      "source_sha256": generator_sha256},
        "input": {
            "outer": {"bytes": len(data), "sha256": sha256(data)},
            "tag": tag,
            "manifest_json_sha256": sha256(manifest_bytes),
            "config": {"digest": "sha256:" + config_digest, "bytes": len(config_bytes)},
            "layers": layer_records,
        },
        "scope": [f"{SCOPE_ROOT}/{d}/" for d in SCOPE_DIRS],
        "counts": {"by_dir": by_dir,
                   "files": len(records), "bytes": sum(r["bytes"] for r in records)},
        "ignored": tree.ignored_counts(),
        "layer_stats": tree.layers,
        "unresolved_out_of_scope": sorted(set(tree.unresolved)),
        "unsupported_selected": [],
        "files": records,
        "output": {"layout": f"{SCOPE_ROOT}/<scope dir>/...", "manifest": MANIFEST_NAME,
                   "file_list_sha256": tree_digest},
        "limits": list(LIMITS),
    }
    return files, manifest


def render_manifest(manifest):
    return (json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


# --- Publication ------------------------------------------------------------------

DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW


def _subdir(fd, name, create):
    if create:
        try:
            os.mkdir(name, 0o700, dir_fd=fd)
        except FileExistsError:
            pass
    return os.open(name, DIR_FLAGS, dir_fd=fd)


def _walk_to_parent(root, path, create):
    """Open the parent directory of `path` below `root` without following links."""
    fds = [os.open(root, DIR_FLAGS)]
    try:
        for name in path.split("/")[:-1]:
            fds.append(_subdir(fds[-1], name, create))
        return fds.pop()
    finally:
        for fd in fds:
            os.close(fd)


def _write_new(dir_fd, name, data):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=dir_fd)
    with os.fdopen(fd, "wb") as handle:
        handle.write(data)


def _read_back(root, path):
    parent = _walk_to_parent(root, path, create=False)
    try:
        fd = os.open(path.rpartition("/")[2], os.O_RDONLY | os.O_NOFOLLOW, dir_fd=parent)
    finally:
        os.close(parent)
    with os.fdopen(fd, "rb") as handle:
        return handle.read()


def trusted_parent(out_dir):
    out_dir = Path(os.path.abspath(out_dir))
    if out_dir.name in ("", ".", ".."):
        raise SnapshotError(f"invalid output directory name: {out_dir}")
    parent = Path(os.path.realpath(out_dir.parent))
    try:
        info = os.lstat(parent)
    except FileNotFoundError:
        raise SnapshotError(f"output parent does not exist: {parent}") from None
    if not stat.S_ISDIR(info.st_mode):
        raise SnapshotError(f"output parent is not a directory: {parent}")
    if info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise SnapshotError(f"output parent must be owned by you and not group/world "
                            f"writable: {parent}")
    return parent / out_dir.name


def write_output(out_dir, files, manifest_bytes):
    """Publish files and manifest into a new directory; never replace anything."""
    target = trusted_parent(out_dir)
    if os.path.lexists(target):
        raise SnapshotError(f"output already exists, refusing to overwrite: {target}")
    staging = tempfile.mkdtemp(prefix=".snapshot-staging-", dir=target.parent)
    reserved = False
    try:
        for path in sorted(files):
            parent = _walk_to_parent(staging, path, create=True)
            try:
                _write_new(parent, path.rpartition("/")[2], files[path])
            finally:
                os.close(parent)
        os.mkdir(target, 0o700)  # exclusive: refuses any file, dir or (dangling) symlink
        reserved = True
        os.rename(os.path.join(staging, SCOPE_ROOT), os.path.join(target, SCOPE_ROOT))
        for path in sorted(files):
            if _read_back(str(target), path) != files[path]:
                raise SnapshotError(f"published {path!r} differs from the archive bytes")
        root = os.open(target, DIR_FLAGS)
        try:
            _write_new(root, MANIFEST_NAME, manifest_bytes)
        finally:
            os.close(root)
    except (OSError, SnapshotError) as exc:
        note = ("; incomplete output without a manifest may remain, inspect it before "
                "retrying" if reserved else "")
        raise SnapshotError(f"could not publish output to {target}: {exc}{note}") from None
    finally:
        shutil.rmtree(staging)
    return target


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("input", type=Path, help="pinned packaged images.tar.gz (read-only)")
    parser.add_argument("output", type=Path, help="new output directory (must not exist)")
    args = parser.parse_args(argv)
    try:
        target = trusted_parent(args.output)
        if os.path.lexists(target):
            raise SnapshotError(f"output already exists, refusing to overwrite: {target}")
        data = read_outer(args.input, PINNED_OUTER)
        generator = sha256(Path(__file__).read_bytes())
        files, manifest = build_snapshot(data, PINNED_TAG, PINNED_IMAGE, generator)
        del data
        manifest_bytes = render_manifest(manifest)
        target = write_output(target, files, manifest_bytes)
    except (SnapshotError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(target), "manifest_sha256": sha256(manifest_bytes),
                      "files": manifest["counts"]["files"],
                      "file_list_sha256": manifest["output"]["file_list_sha256"],
                      "by_dir": {d: v["files"] for d, v in manifest["counts"]["by_dir"].items()}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
