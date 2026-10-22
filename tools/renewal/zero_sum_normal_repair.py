#!/usr/bin/env python3
"""T07.007.011.002 pinned exact-zero smooth-normal repair.

Pure transformation of the two admitted RSM bundles. Only the unguarded
class method ``calcNormal_SMOOTH(normal, groupUsed, group)`` changes: one guard
is inserted immediately before the original reciprocal-length line. When the
accumulated sum is exactly x===0&&y===0&&z===0 it stores numeric 0 into
norm[l..l+2] and continues the vertex loop; every other sum reaches the original
``len = 1 / Math.sqrt(...)`` and multiplies byte-for-byte unchanged. The free
``function calcNormal_SMOOTH(node, ...)`` helper (already isFinite-guarded) is
never touched.

Standard library only. No bundle is imported or evaluated here.
"""

import argparse
import hashlib
import json
import os
import stat
import sys
from datetime import datetime, timezone

PATCH_ID = "smooth-normal-zero-sum-1"
PATCH_VERSION = 1
TASK = "T07.007.011.002"

METHOD_HEADER = b"calcNormal_SMOOTH(normal, groupUsed, group) {"
LEN_LINE = b"len = 1 / Math.sqrt(x * x + y * y + z * z);"
MULTIPLY_LINES = (
    b"norm[l] = x * len;",
    b"norm[l + 1] = y * len;",
    b"norm[l + 2] = z * len;",
)
GUARD_CONDITION = b"if (x === 0 && y === 0 && z === 0) {"

# Full admitted inputs and the generated outputs/hunks they must produce.
PINS = {
    "worker": {
        "name": "ThreadEventHandler.js",
        "bytes": 624339,
        "sha256": "09a53f9da19689435e19e6e7ea026bc9344f5bda9ea91e9610762f3ad4e2b160",
        "method_indent": b"\t",
        "header_offset": 564336,
        "insert_offset": 565003,
        "method_end": 565140,
        "method_sha256": "eb72411ce7573df779a4bc2afb905157e56d608cfacd293bc42f224293c7d179",
        "patched_method_sha256": "62d2f342e18dc4a7566d64dcb44b7ff9c2d37dc2de6f44f324edcaf44175e8fc",
        "output_bytes": 624463,
        "output_sha256": "1501ca10336d91e4f8a0301101c43e5ca1a0ef1aa81212bbffb5690c68c13325",
    },
    "online": {
        "name": "Online.js",
        "bytes": 13174160,
        "sha256": "9c148d9e43384a2498f9074efd1603b4eda1ff36dac53998985cfdf5eaf6fadf",
        "method_indent": b"\t\t",
        "header_offset": 8850579,
        "insert_offset": 8851267,
        "method_end": 8851411,
        "method_sha256": "b2b10484d3ad5a040ac908a692d401d1b57bc37be943ed661fd71e6986a68586",
        "patched_method_sha256": "5079145f9c0e74699597e84b7560a4e9effb2299a123cda957994b3a562ef5dd",
        "output_bytes": 13174290,
        "output_sha256": "50b724b708393d7bb6d71b4f5102e62b16e340eb1bb54f05b1c8613af4116418",
    },
}


class PatchError(ValueError):
    """Input is not an admitted original bundle."""


class AlreadyPatchedError(PatchError):
    """Input already carries this repair."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def guard_text(loop_indent):
    """Inserted lines; loop_indent is the indent of the original len line."""
    inner = loop_indent + b"\t"
    return (
        loop_indent + GUARD_CONDITION + b"\n"
        + inner + b"norm[l] = 0;\n"
        + inner + b"norm[l + 1] = 0;\n"
        + inner + b"norm[l + 2] = 0;\n"
        + inner + b"continue;\n"
        + loop_indent + b"}\n"
    )


def locate(data, method_indent):
    """Return (header_offset, insert_offset, method_end, loop_indent).

    method_end is the offset just past the method's closing ``}\\n``. The
    insertion point is the start of the original len line.
    """
    header_at = data.find(method_indent + METHOD_HEADER)
    if header_at < 0 or data.find(method_indent + METHOD_HEADER, header_at + 1) >= 0:
        raise PatchError("class method header is missing or not unique")
    header_at += len(method_indent)
    close = b"\n" + method_indent + b"}\n"
    end = data.find(close, header_at)
    if end < 0:
        raise PatchError("class method end not found")
    end += len(close)
    loop_indent = method_indent + b"\t\t\t"
    block = b"\n".join(loop_indent + line for line in (LEN_LINE,) + MULTIPLY_LINES)
    at = data.find(b"\n" + block + b"\n", header_at, end)
    if at < 0 or data.find(b"\n" + block + b"\n", at + 1, end) >= 0:
        raise PatchError("original normalization block is missing or not unique")
    return header_at, at + 1, end, loop_indent


def transform(data, method_indent):
    """Insert the exact-zero guard into the unique class method; no pins."""
    if GUARD_CONDITION in data:
        raise AlreadyPatchedError("input already contains the exact-zero guard")
    _, insert_at, _, loop_indent = locate(data, method_indent)
    return data[:insert_at] + guard_text(loop_indent) + data[insert_at:]


def patch_bundle(data, bundle):
    """Return the repaired copy of an exact admitted original bundle."""
    if type(bundle) is not str:
        raise TypeError("bundle must be str")
    if bundle not in PINS:
        raise PatchError("unknown bundle selector: %r" % (bundle,))
    if type(data) is not bytes:
        raise TypeError("data must be bytes")
    pin = PINS[bundle]
    digest = sha256(data)
    if digest == pin["output_sha256"] or GUARD_CONDITION in data:
        raise AlreadyPatchedError("%s is already patched" % bundle)
    if len(data) != pin["bytes"] or digest != pin["sha256"]:
        raise PatchError("%s input does not match pinned bytes/sha256" % bundle)
    header_at, insert_at, end, loop_indent = locate(data, pin["method_indent"])
    if (header_at, insert_at, end) != (
        pin["header_offset"], pin["insert_offset"], pin["method_end"]
    ):
        raise PatchError("%s hunk location differs from pin" % bundle)
    if sha256(data[header_at:end]) != pin["method_sha256"]:
        raise PatchError("%s method bytes differ from pin" % bundle)
    inserted = guard_text(loop_indent)
    out = data[:insert_at] + inserted + data[insert_at:]
    if sha256(out[header_at:end + len(inserted)]) != pin["patched_method_sha256"]:
        raise PatchError("%s patched method differs from pin" % bundle)
    if len(out) != pin["output_bytes"] or sha256(out) != pin["output_sha256"]:
        raise PatchError("%s output does not match pinned bytes/sha256" % bundle)
    return out


def hunk_record(bundle):
    pin = PINS[bundle]
    inserted = guard_text(pin["method_indent"] + b"\t\t\t")
    return {
        "kind": "insert",
        "offset": pin["insert_offset"],
        "removed_bytes": 0,
        "inserted_bytes": len(inserted),
        "inserted_sha256": sha256(inserted),
        "inserted_text": inserted.decode("ascii"),
        "method_header_offset": pin["header_offset"],
        "original_method_end": pin["method_end"],
        "original_method_sha256": pin["method_sha256"],
        "patched_method_sha256": pin["patched_method_sha256"],
    }


def _identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns,
            st.st_ctime_ns, st.st_mode, st.st_nlink)


def read_source(path):
    """Read one regular, unlinked file without following symlinks."""
    pre = os.lstat(path)
    if not stat.S_ISREG(pre.st_mode):
        raise PatchError("%s is not a regular file" % os.path.basename(path))
    if pre.st_nlink != 1:
        raise PatchError("%s has hard links" % os.path.basename(path))
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    try:
        st = os.fstat(fd)
        if _identity(st) != _identity(pre):
            raise PatchError("%s changed while opening" % os.path.basename(path))
        chunks = []
        while True:
            chunk = os.read(fd, 1 << 20)
            if not chunk:
                break
            chunks.append(chunk)
        final_fd = _identity(os.fstat(fd))
        final_path = _identity(os.lstat(path))
        if final_fd != _identity(pre) or final_path != _identity(pre):
            raise PatchError("%s FD or current pathname changed while reading" % os.path.basename(path))
    finally:
        os.close(fd)
    return b"".join(chunks), _identity(pre)


def write_exclusive(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        while view:
            try:
                written = os.write(fd, view)
            except InterruptedError:
                continue
            if written <= 0 or written > len(view):
                raise PatchError("invalid output write progress")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def _unlink_owned(path, identity):
    """Finite current-name ownership check; never delete a different inode."""
    current = os.lstat(path)
    if not stat.S_ISREG(current.st_mode) or (current.st_dev, current.st_ino) != identity[:2]:
        raise PatchError("foreign publication entry retained: %s" % os.path.basename(path))
    os.unlink(path)


def _publish_manifest(partial, final, identity):
    if _identity(os.lstat(partial)) != identity:
        raise PatchError("staged manifest identity changed")
    # Linking cannot replace an existing marker; a same-directory stage stays
    # available until the final name has been created and its ownership checked.
    os.link(partial, final, follow_symlinks=False)
    try:
        current = os.lstat(final)
        if not stat.S_ISREG(current.st_mode) or (current.st_dev, current.st_ino) != identity[:2]:
            raise PatchError("final manifest is not the staged inode")
        _unlink_owned(partial, identity)
        current = os.lstat(final)
        if (not stat.S_ISREG(current.st_mode) or (current.st_dev, current.st_ino) != identity[:2]
                or current.st_nlink != 1 or stat.S_IMODE(current.st_mode) != 0o600
                or os.path.lexists(partial)):
            raise PatchError("final manifest did not reach the single-link private state")
    except Exception as original:
        try:
            _unlink_owned(final, identity)
        except FileNotFoundError:
            pass
        except (PatchError, OSError) as cleanup:
            raise PatchError("manifest failure (%s); owned revocation refused/failed: %s" % (original, cleanup)) from original
        raise


def build_manifest(results):
    files = []
    for bundle in ("worker", "online"):
        pin = PINS[bundle]
        files.append({
            "bundle": bundle,
            "name": pin["name"],
            "input": {"bytes": pin["bytes"], "sha256": pin["sha256"]},
            "output": {"bytes": len(results[bundle]), "sha256": sha256(results[bundle])},
            "hunks": [hunk_record(bundle)],
        })
    return {
        "schema": "T07.007.011.002-normal-repair-manifest-1",
        "task": TASK,
        "patch_id": PATCH_ID,
        "patch_version": PATCH_VERSION,
        "files": files,
    }


def run(input_root, output_dir):
    if os.path.lexists(output_dir):
        raise PatchError("output destination already exists")
    root_st = os.lstat(input_root)
    if not stat.S_ISDIR(root_st.st_mode):
        raise PatchError("input root is not a real directory")
    sources, identities, results = {}, {}, {}
    for bundle in ("worker", "online"):
        path = os.path.join(input_root, PINS[bundle]["name"])
        sources[bundle], identities[bundle] = read_source(path)
        results[bundle] = patch_bundle(sources[bundle], bundle)
    manifest = build_manifest(results)
    os.mkdir(output_dir, 0o700)
    os.chmod(output_dir, 0o700)
    for bundle in ("worker", "online"):
        write_exclusive(os.path.join(output_dir, PINS[bundle]["name"]), results[bundle])
    receipts = {}
    for bundle in ("worker", "online"):
        name = PINS[bundle]["name"]
        again, ident = read_source(os.path.join(input_root, name))
        if ident != identities[bundle] or sha256(again) != PINS[bundle]["sha256"]:
            raise PatchError("%s source changed during run" % name)
        written, _ = read_source(os.path.join(output_dir, name))
        if written != results[bundle]:
            raise PatchError("%s output readback mismatch" % name)
        receipts[name] = {
            "source_sha256_before": sha256(sources[bundle]),
            "source_sha256_after": sha256(again),
            "source_identity_unchanged": True,
            "output_readback_sha256": sha256(written),
        }
    # Everything above "runtime_receipts" is deterministic for the pinned inputs.
    manifest["runtime_receipts"] = {
        "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "sources": receipts,
    }
    body = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("ascii")
    partial = os.path.join(output_dir, "manifest.json.partial")
    write_exclusive(partial, body)  # Flush/fsync/close must all finish first.
    staged, staged_identity = read_source(partial)
    if staged != body:
        raise PatchError("staged manifest readback mismatch")
    # This final full pass is after stage creation AND readback, not just after
    # the two bundle writes. No source identity is inferred from stale receipts.
    for bundle in ("worker", "online"):
        again, ident = read_source(os.path.join(input_root, PINS[bundle]["name"]))
        if ident != identities[bundle] or sha256(again) != PINS[bundle]["sha256"]:
            raise PatchError("%s source changed after manifest staging" % bundle)
    _publish_manifest(partial, os.path.join(output_dir, "manifest.json"), staged_identity)
    return manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input-root", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)
    try:
        manifest = run(args.input_root, args.output_dir)
    except (PatchError, OSError) as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    for item in manifest["files"]:
        print("%s %d %s" % (item["name"], item["output"]["bytes"], item["output"]["sha256"]))
    return 0


if __name__ == "__main__":
    sys.exit(main())
