#!/usr/bin/env python3
"""Package the retained True quest table as the fixed tc-true-quest-text mod (T10.008).

    python3 -I -B tools/renewal/quest_true_text_mod.py --source FILE --output NEW_DIR

FILE must be the exact retained OngoingQuestInfoList_True.lub (pinned length
and SHA-256 below). NEW_DIR must not exist; its parent must be an existing
ordinary directory owned by the caller. No path component may be a symlink.
The result is:

    NEW_DIR/tc-true-quest-text/mod.json
    NEW_DIR/tc-true-quest-text/System/OngoingQuestInfoList-tc-true-quest-text.lub
    NEW_DIR/RESULT.json   (outside the mod, written last)

Only the inner folder is a mod. The table is copied as bytes; it is never
decoded, parsed or executed. Both mod files are read back before RESULT.json
is published. On failure nothing is deleted: the incomplete output this run
created is reported for review and no successful receipt exists.
Standard library only (Python 3.9). See docs/project/runbooks/T10.008-quest-true-text-mod.md.
"""

import argparse
import hashlib
import json
import os
import stat
import sys

SLUG = "tc-true-quest-text"
INPUT_BYTES = 2248204
INPUT_SHA256 = "49264cdd9b30ecad3416c721d153f91688455daa243e6af6ae04ad49bb805c00"

# Exact objects from docs/project/fixtures/T10.008-profile.json.
MANIFEST = {
    "name": SLUG,
    "version": "0.1.0",
    "author": "RO solo project",
    "description": "Traditional Chinese True quest-text overlay",
    "requires": {"app": ">=1.6.3", "era": "renewal"},
}
RECEIPT_SCHEMA = "ro-solo-true-quest-text-mod.v1"

MANIFEST_PATH = SLUG + "/mod.json"
TABLE_PATH = SLUG + "/System/OngoingQuestInfoList-" + SLUG + ".lub"
RESULT_NAME = "RESULT.json"
PARTIAL_NAME = "RESULT.json.partial"

CHUNK = 1 << 20


class Refused(Exception):
    """An input or destination this tool will not touch."""


class Incomplete(Exception):
    """An I/O or readback failure after this run created the output."""


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def check_no_symlink_components(path):
    """Refuse a symlink anywhere in the existing part of `path`."""
    # Inspect raw components before '..' can erase a symlink from the path.
    raw = os.fspath(path)
    if not os.path.isabs(raw):
        raw = os.path.join(os.getcwd(), raw)
    current = os.sep
    for part in raw.split(os.sep)[1:]:
        if not part or part == ".":
            continue
        if part == "..":
            current = os.path.dirname(current)
            continue
        current = os.path.join(current, part)
        try:
            st = os.lstat(current)
        except (FileNotFoundError, NotADirectoryError):
            break
        if stat.S_ISLNK(st.st_mode):
            raise Refused("symlink path component: " + current)


def read_bounded(path, limit):
    """Read at most limit + 1 bytes of an ordinary nonsymlink file."""
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise Refused("not an ordinary file: " + path)
        chunks, total = [], 0
        while total <= limit:
            chunk = os.read(fd, min(CHUNK, limit + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
        return b"".join(chunks)
    finally:
        os.close(fd)


def load_source(path):
    """Return the pinned table bytes, checking type and size before opening."""
    check_no_symlink_components(path)
    try:
        st = os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        raise Refused("source does not exist: " + path)
    if not stat.S_ISREG(st.st_mode):
        raise Refused("source is not an ordinary file: " + path)
    if st.st_size != INPUT_BYTES:
        raise Refused("source is %d bytes, expected %d" % (st.st_size, INPUT_BYTES))
    data = read_bounded(path, INPUT_BYTES)
    if len(data) != INPUT_BYTES:
        raise Refused("source read %d bytes, expected %d" % (len(data), INPUT_BYTES))
    if sha256(data) != INPUT_SHA256:
        raise Refused("source SHA-256 does not match the pinned True table")
    return data


def check_output(path):
    """The output must be new, under an existing owned ordinary directory."""
    check_no_symlink_components(path)
    try:
        os.lstat(path)
    except (FileNotFoundError, NotADirectoryError):
        pass
    else:
        raise Refused("output already exists: " + path)
    parent = os.path.dirname(os.path.abspath(path))
    try:
        st = os.lstat(parent)
    except (FileNotFoundError, NotADirectoryError):
        raise Refused("output parent does not exist: " + parent)
    if not stat.S_ISDIR(st.st_mode):
        raise Refused("output parent is not a directory: " + parent)
    if st.st_uid != os.geteuid():
        raise Refused("output parent is not owned by this user: " + parent)


def make_dir(path):
    os.mkdir(path, 0o700)
    os.chmod(path, 0o700)


def write_new(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        while view:
            written = os.write(fd, view)
            if written <= 0:
                raise OSError("write made no progress")
            view = view[written:]
        os.fsync(fd)
    finally:
        os.close(fd)


def read_back(path, expected):
    """Independently reread a written file; return its observed record."""
    st = os.lstat(path)
    if not stat.S_ISREG(st.st_mode) or stat.S_IMODE(st.st_mode) != 0o600:
        raise OSError("readback: %s is not an ordinary 0600 file" % path)
    data = read_bounded(path, len(expected))
    if data != expected:
        raise OSError("readback: %s differs from the bytes written" % path)
    return {"bytes": len(data), "sha256": sha256(data)}


def manifest_bytes():
    return (json.dumps(MANIFEST, indent=2, ensure_ascii=True) + "\n").encode("ascii")


def generate(source, output):
    """Refuse or build the output; return the published receipt."""
    data = load_source(source)
    check_output(output)
    try:
        os.mkdir(output, 0o700)
    except FileExistsError:
        raise Refused("output already exists: " + output)
    try:
        os.chmod(output, 0o700)
        return build(data, output)
    except (OSError, Refused) as e:
        raise Incomplete(str(e))


def build(data, output):
    mod_dir = os.path.join(output, SLUG)
    make_dir(mod_dir)
    make_dir(os.path.join(mod_dir, "System"))
    files = []
    for rel, body in ((MANIFEST_PATH, manifest_bytes()), (TABLE_PATH, data)):
        full = os.path.join(output, *rel.split("/"))
        write_new(full, body)
        files.append(dict(path=rel, **read_back(full, body)))
    receipt = {
        "schema": RECEIPT_SCHEMA,
        "status": "ok",
        "slug": SLUG,
        "input": {"bytes": len(data), "sha256": sha256(data)},
        "files": files,
    }
    body = (json.dumps(receipt, indent=2, ensure_ascii=True) + "\n").encode("ascii")
    partial = os.path.join(output, PARTIAL_NAME)
    write_new(partial, body)
    read_back(partial, body)
    os.rename(partial, os.path.join(output, RESULT_NAME))
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--source", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        generate(args.source, args.output)
    except Refused as e:
        print("refused: %s" % e, file=sys.stderr)
        return 2
    except Incomplete as e:
        print("failed: %s" % e, file=sys.stderr)
        print("incomplete output retained for review: %s" % args.output, file=sys.stderr)
        return 1
    except OSError as e:
        print("failed before creating output: %s" % e, file=sys.stderr)
        return 1
    # RESULT.json is the success channel; no stdout I/O follows publication.
    return 0


if __name__ == "__main__":
    sys.exit(main())
