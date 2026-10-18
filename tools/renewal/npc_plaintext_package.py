#!/usr/bin/env python3
"""Generate the fixed npc-plaintext-zh-tw folder package (T05.006).

    python3 -I -B tools/renewal/npc_plaintext_package.py \
        LOADER_SOURCE CORE_SOURCE DICTIONARY_SOURCE OUTPUT

The three sources must be the exact root-qualified dictionary_loader.mjs, the
unchanged npc_plaintext_adapter.mjs core and the pinned dict.json. Arguments
only locate those bytes: name, metadata, pins, entry and policy are fixed
below and cannot be overridden. OUTPUT is a new private evidence envelope:

    OUTPUT/package-manifest.json, OUTPUT/COMPLETE.json (written last) and the
    mod folder OUTPUT/npc-plaintext-zh-tw/ (mod.json + client/ with index.js,
    the loader, the core and dict.json).

Only the inner folder is a mod. The dictionary is streamed, hashed and copied
as bytes; it is never decoded or parsed. Every package file is read back
before completion. On failure only the output this run created is removed.
Standard library only (Python 3.9). See NPC_PLAINTEXT_PACKAGE.md.
"""

import hashlib
import json
import os
import stat
import sys

TASK = "T05.006"
PROFILE_NAME = "npc-plaintext-package-v1"
PACKAGE_NAME = "npc-plaintext-zh-tw"

# Normative fixed data, copied from the frozen package-profile.json
# (1531 bytes, SHA-256 53f3ea8b754f8604062bedb19a79c71f36b3dea5d6a47c1c39d14b97b5dc98da).
PROFILE = {
    "acquisition": {
        "manifest_bytes": 2945,
        "manifest_sha256": "e852b653d162c978e074cc01c19de5a8f1b79d5bc9de008e9629bcbd6473e478",
        "revision": "485ceb2c11104a37f0dd87f5cd2ce3d527f87982",
    },
    "entry": {
        "config_path": "plugins/npc-plaintext-zh-tw/index",
        "core_relative": "./npc_plaintext_adapter.mjs",
        "default_export": "./dictionary_loader.mjs",
        "dictionary_relative": "./dict.json",
        "stage_prefix": "plugins/npc-plaintext-zh-tw",
    },
    "entry_utf8": "export { default } from './dictionary_loader.mjs';\n",
    "mod_json": {
        "author": "Project local integration",
        "default": "off",
        "description": "繁體中文 NPC 純文字對話與選單試用；僅限精確字典命中。",
        "name": "npc-plaintext-zh-tw",
        "requires": {"app": "=1.6.3", "era": "renewal"},
        "version": "1.0.0",
    },
    "package": {"name": "npc-plaintext-zh-tw", "version": "1.0.0"},
    "profile": PROFILE_NAME,
    "schema": 1,
    "sources": {
        "core": {
            "bytes": 14236,
            "file": "npc_plaintext_adapter.mjs",
            "sha256": "0dc77140f921925f7079dfdeaf6f674931f66a726f97b41bfab5f6b8e7f0089c",
        },
        "dictionary": {
            "bytes": 19706353,
            "file": "dict.json",
            "sha256": "be3825ca74db764f8d9ffbea9ba8f15ac17b1fd5bde49975d4b36c59ba704fc2",
        },
        "loader": {
            "bytes": 22648,
            "file": "dictionary_loader.mjs",
            "sha256": "5ef583b6bf7d15c285dc6c3ebde7c6e51ba1f8a9523228a2dd44a777e0a15ab4",
        },
    },
    "task": TASK,
}

SMALL_CAP = 1 << 20          # loader, core and generator source
CHUNK = 1 << 20              # dictionary streaming read size
MANIFEST = "package-manifest.json"
COMPLETE = "COMPLETE.json"
COMPLETE_PARTIAL = ".COMPLETE.json.partial"
DIR_MODE = 0o700
FILE_MODE = 0o600
CLIENT = PACKAGE_NAME + "/client"
DIRECTORIES = (".", PACKAGE_NAME, CLIENT)

_O_CLOEXEC = getattr(os, "O_CLOEXEC", 0)
_O_NOFOLLOW = getattr(os, "O_NOFOLLOW", 0)


class PackageError(Exception):
    """A refusal or failure with a bounded, path-free diagnosis."""


def canonical(value):
    """The one JSON serialization used for every file this tool writes."""
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _why(error):
    """OS error reason without the path the exception may carry."""
    return error.strerror or type(error).__name__


# ---------------------------------------------------------------- paths


def _components(path, what):
    """Absolute path of an ordinary argument, refusing dot/dot-dot/empty parts."""
    if not isinstance(path, str) or not path:
        raise PackageError(f"{what}: empty path")
    if "\0" in path:
        raise PackageError(f"{what}: path contains NUL")
    parts = path.split("/")
    if path.startswith("/"):
        parts = parts[1:]
        base = "/"
    else:
        base = os.getcwd()
    for part in parts:
        if part in ("", ".", ".."):
            raise PackageError(f"{what}: path has an empty, '.' or '..' component")
    return os.path.join(base, *parts)


def _no_symlink_ancestors(absolute, what, include_last):
    """lstat every prefix; refuse a symlink or a non-directory ancestor."""
    parts = absolute.split("/")[1:]
    current = "/"
    last = len(parts) - 1
    for index, part in enumerate(parts):
        current = os.path.join(current, part)
        if index == last and not include_last:
            break
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            raise PackageError(f"{what}: a path component does not exist") from None
        except OSError as error:
            raise PackageError(f"{what}: cannot inspect path ({_why(error)})") from None
        if stat.S_ISLNK(st.st_mode):
            raise PackageError(f"{what}: path has a symbolic link component")
        if index < last and not stat.S_ISDIR(st.st_mode):
            raise PackageError(f"{what}: an ancestor is not a directory")


def _resolve_source(path, what):
    absolute = _components(path, what)
    _no_symlink_ancestors(absolute, what, include_last=True)
    st = os.lstat(absolute)
    if not stat.S_ISREG(st.st_mode):
        raise PackageError(f"{what}: not a regular file")
    return absolute


def _resolve_output(path):
    absolute = _components(path, "OUTPUT")
    if absolute == "/":
        raise PackageError("OUTPUT: refusing the filesystem root")
    _no_symlink_ancestors(absolute, "OUTPUT", include_last=False)
    parent = os.path.dirname(absolute)
    try:
        st = os.lstat(parent)
    except OSError as error:
        raise PackageError(f"OUTPUT: parent cannot be inspected ({_why(error)})") from None
    if not stat.S_ISDIR(st.st_mode):
        raise PackageError("OUTPUT: parent is not a directory")
    try:
        os.lstat(absolute)
    except FileNotFoundError:
        return absolute
    except OSError as error:
        raise PackageError(f"OUTPUT: cannot inspect ({_why(error)})") from None
    raise PackageError("OUTPUT: already exists (including a dangling link); refusing to overwrite")


def _within(child, parent):
    return child == parent or child.startswith(parent.rstrip("/") + "/")


# ---------------------------------------------------------------- sources


def _identity(st):
    return (st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns, stat.S_IFMT(st.st_mode))


class Source:
    """One source held open on one owned descriptor for the whole run."""

    def __init__(self, role, path, pin):
        self.role = role
        self.path = path
        self.pin = pin
        self.fd = None
        self.identity = None

    def open(self):
        try:
            self.fd = os.open(self.path, os.O_RDONLY | _O_NOFOLLOW | _O_CLOEXEC)
        except OSError as error:
            raise PackageError(f"{self.role}: cannot open ({_why(error)})") from None
        st = os.fstat(self.fd)
        if not stat.S_ISREG(st.st_mode):
            raise PackageError(f"{self.role}: descriptor is not a regular file")
        self.identity = _identity(st)
        self.check_stable()
        if st.st_size != self.pin["bytes"]:
            raise PackageError(f"{self.role}: size differs from the pinned length")

    def check_stable(self):
        """The descriptor and the path still name the same unchanged file."""
        try:
            now_fd = _identity(os.fstat(self.fd))
            now_path = _identity(os.lstat(self.path))
        except OSError as error:
            raise PackageError(f"{self.role}: cannot re-inspect source ({_why(error)})") from None
        if now_fd != self.identity or now_path != self.identity:
            raise PackageError(f"{self.role}: source identity or metadata changed during the run")

    def read_small(self):
        """Whole bounded read of a loader/core source from offset 0."""
        if self.pin["bytes"] > SMALL_CAP:
            raise PackageError(f"{self.role}: pin exceeds the 1 MiB cap")
        os.lseek(self.fd, 0, os.SEEK_SET)
        data = bytearray()
        while len(data) <= SMALL_CAP:
            chunk = os.read(self.fd, SMALL_CAP + 1 - len(data))
            if not chunk:
                break
            data += chunk
        if len(data) > SMALL_CAP:
            raise PackageError(f"{self.role}: larger than the 1 MiB cap")
        if len(data) != self.pin["bytes"]:
            raise PackageError(f"{self.role}: read length differs from the pinned length")
        data = bytes(data)
        if _sha(data) != self.pin["sha256"]:
            raise PackageError(f"{self.role}: SHA-256 differs from the pin")
        self.check_stable()
        return data

    def close(self):
        fd, self.fd = self.fd, None
        if fd is not None:
            os.close(fd)


def _generator_identity():
    """Bytes/hash of the authored generator file actually being executed."""
    path = os.path.abspath(__file__)
    try:
        fd = os.open(path, os.O_RDONLY | _O_NOFOLLOW | _O_CLOEXEC)
    except OSError as error:
        raise PackageError(f"generator: cannot open own source ({_why(error)})") from None
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise PackageError("generator: own source is not a regular file")
        data = bytearray()
        while len(data) <= SMALL_CAP:
            chunk = os.read(fd, SMALL_CAP + 1 - len(data))
            if not chunk:
                break
            data += chunk
    finally:
        os.close(fd)
    if len(data) > SMALL_CAP:
        raise PackageError("generator: own source exceeds the 1 MiB cap")
    return {"file": os.path.basename(path), "bytes": len(data), "sha256": _sha(bytes(data))}


# ---------------------------------------------------------------- output


class Output:
    """The new OUTPUT tree. Records what this run created, by identity."""

    def __init__(self, root):
        self.root = root
        self.created = []  # (relative path, dev, ino, is_dir), creation order
        self.records = {}  # relative path -> {path, bytes, sha256, mode}

    def path(self, relative):
        return self.root if relative == "." else os.path.join(self.root, relative)

    def mkdir(self, relative):
        target = self.path(relative)
        try:
            os.mkdir(target, DIR_MODE)
        except OSError as error:
            raise PackageError(f"cannot create directory {relative} ({_why(error)})") from None
        st = os.lstat(target)
        if not stat.S_ISDIR(st.st_mode):
            raise PackageError(f"created directory {relative} is not a directory")
        self.created.append((relative, st.st_dev, st.st_ino, True))
        # A restrictive umask may have removed bits (even owner search/read,
        # so no descriptor can be opened yet): set the exact mode by path on
        # the directory just created, then confirm identity and mode.
        os.chmod(target, DIR_MODE)
        after = os.lstat(target)
        if (after.st_dev, after.st_ino) != (st.st_dev, st.st_ino) or not stat.S_ISDIR(after.st_mode):
            raise PackageError(f"directory {relative} was replaced")
        if stat.S_IMODE(after.st_mode) != DIR_MODE:
            raise PackageError(f"directory {relative} does not have mode 0700")

    def _create(self, relative):
        target = self.path(relative)
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | _O_NOFOLLOW | _O_CLOEXEC
        try:
            fd = os.open(target, flags, FILE_MODE)
        except OSError as error:
            raise PackageError(f"cannot create {relative} ({_why(error)})") from None
        try:
            st = os.fstat(fd)
            self.created.append((relative, st.st_dev, st.st_ino, False))
            os.fchmod(fd, FILE_MODE)
        except BaseException:
            os.close(fd)
            raise
        return fd

    @staticmethod
    def _write_all(fd, data, relative):
        view = memoryview(data)
        while view:
            try:
                written = os.write(fd, view)
            except OSError as error:
                raise PackageError(f"write failed for {relative} ({_why(error)})") from None
            if not isinstance(written, int) or written <= 0 or written > len(view):
                raise PackageError(f"write made no valid progress for {relative}")
            view = view[written:]

    def _finish(self, fd, relative):
        """fsync and close one written file; close is attempted exactly once."""
        try:
            try:
                os.fsync(fd)
            except OSError as error:
                raise PackageError(f"fsync failed for {relative} ({_why(error)})") from None
        finally:
            try:
                os.close(fd)
            except OSError as error:
                raise PackageError(f"close failed for {relative} ({_why(error)})") from None

    def write_bytes(self, relative, data):
        fd = self._create(relative)
        try:
            self._write_all(fd, data, relative)
        except BaseException:
            os.close(fd)
            raise
        self._finish(fd, relative)
        return self.read_back(relative, len(data), _sha(data))

    def copy_stream(self, relative, source):
        """Stream the dictionary source into a new file; never accumulate it."""
        expected = source.pin["bytes"]
        fd = self._create(relative)
        digest = hashlib.sha256()
        total = 0
        try:
            os.lseek(source.fd, 0, os.SEEK_SET)
            while total < expected:
                try:
                    chunk = os.read(source.fd, min(CHUNK, expected - total))
                except OSError as error:
                    raise PackageError(f"{source.role}: read failed ({_why(error)})") from None
                if not chunk:
                    raise PackageError(f"{source.role}: truncated before the pinned length")
                if len(chunk) > expected - total:
                    raise PackageError(f"{source.role}: more bytes than the pinned length")
                digest.update(chunk)
                total += len(chunk)
                self._write_all(fd, chunk, relative)
            if os.read(source.fd, 1):
                raise PackageError(f"{source.role}: more bytes than the pinned length")
        except BaseException:
            os.close(fd)
            raise
        self._finish(fd, relative)
        if digest.hexdigest() != source.pin["sha256"]:
            raise PackageError(f"{source.role}: streamed SHA-256 differs from the pin")
        source.check_stable()
        return self.read_back(relative, expected, source.pin["sha256"])

    def read_back(self, relative, size, sha256):
        """Reopen a closed file; check identity, mode, size and streamed hash."""
        target = self.path(relative)
        try:
            fd = os.open(target, os.O_RDONLY | _O_NOFOLLOW | _O_CLOEXEC)
        except OSError as error:
            raise PackageError(f"read-back cannot open {relative} ({_why(error)})") from None
        try:
            st = os.fstat(fd)
            owned = [c for c in self.created if c[0] == relative]
            if not owned or (st.st_dev, st.st_ino) != owned[-1][1:3] or not stat.S_ISREG(st.st_mode):
                raise PackageError(f"read-back of {relative} found a different file")
            if stat.S_IMODE(st.st_mode) != FILE_MODE:
                raise PackageError(f"read-back of {relative} found mode other than 0600")
            digest = hashlib.sha256()
            total = 0
            while True:
                try:
                    chunk = os.read(fd, CHUNK)
                except OSError as error:
                    raise PackageError(f"read-back of {relative} failed ({_why(error)})") from None
                if not chunk:
                    break
                total += len(chunk)
                if total > size:
                    break
                digest.update(chunk)
        finally:
            os.close(fd)
        if total != size or digest.hexdigest() != sha256:
            raise PackageError(f"read-back of {relative} does not match what was written")
        record = {"path": relative, "bytes": size, "sha256": sha256, "mode": "0600"}
        self.records[relative] = record
        return record

    def check_tree(self, expected_files):
        """Exactly the fixed directories (0700) and files; nothing else."""
        dirs = {d for d in DIRECTORIES}
        found_dirs, found_files = set(), set()
        for relative in sorted(dirs):
            target = self.path(relative)
            st = os.lstat(target)
            if not stat.S_ISDIR(st.st_mode) or stat.S_IMODE(st.st_mode) != DIR_MODE:
                raise PackageError(f"directory {relative} is not a 0700 directory")
            found_dirs.add(relative)
            for name in os.listdir(target):
                child = name if relative == "." else relative + "/" + name
                cst = os.lstat(self.path(child))
                if stat.S_ISDIR(cst.st_mode):
                    if child not in dirs:
                        raise PackageError("unexpected directory in the output tree")
                elif stat.S_ISREG(cst.st_mode):
                    found_files.add(child)
                else:
                    raise PackageError("unexpected non-regular entry in the output tree")
        if found_files != set(expected_files):
            raise PackageError("output tree files differ from the fixed list")

    def cleanup(self):
        """Remove only entries this run created, if the root is still ours.

        Returns None when everything owned is gone, else a short reason.
        """
        if not self.created:
            return None
        root_rel, dev, ino, _ = self.created[0]
        try:
            st = os.lstat(self.root)
        except FileNotFoundError:
            return None
        except OSError as error:
            return f"cannot inspect output root ({_why(error)})"
        if (st.st_dev, st.st_ino) != (dev, ino) or not stat.S_ISDIR(st.st_mode):
            return "output root was replaced by a foreign entry; it was left untouched"
        left = []
        for relative, dev, ino, is_dir in reversed(self.created):
            target = self.path(relative)
            try:
                st = os.lstat(target)
                if (st.st_dev, st.st_ino) != (dev, ino):
                    left.append(relative)
                    continue
                if is_dir:
                    os.rmdir(target)
                else:
                    os.unlink(target)
            except FileNotFoundError:
                continue
            except OSError:
                left.append(relative)
        if left:
            return f"{len(left)} owned or foreign entr{'y' if len(left) == 1 else 'ies'} could not be removed"
        return None


# ---------------------------------------------------------------- build


def _package_files(profile):
    client = CLIENT + "/"
    return sorted([
        PACKAGE_NAME + "/mod.json",
        client + "index.js",
        client + profile["sources"]["loader"]["file"],
        client + profile["sources"]["core"]["file"],
        client + profile["sources"]["dictionary"]["file"],
    ])


def build(loader_path, core_path, dictionary_path, output_path, profile=PROFILE):
    """Create OUTPUT. Returns the success stdout value. `profile` is fixed in production."""
    roles = (("loader", loader_path), ("core", core_path), ("dictionary", dictionary_path))
    resolved = {role: _resolve_source(path, role.upper() + "_SOURCE") for role, path in roles}
    output_root = _resolve_output(output_path)

    # Path overlap: distinct sources, and OUTPUT neither at nor around any source.
    if len(set(resolved.values())) != 3:
        raise PackageError("path overlap: the same path is given for two sources")
    for path in resolved.values():
        if _within(path, output_root) or _within(output_root, path):
            raise PackageError("path overlap: OUTPUT overlaps a source path")

    generator = _generator_identity()
    sources = {role: Source(role, resolved[role], profile["sources"][role]) for role, _ in roles}
    output = Output(output_root)
    failure = None
    try:
        for role, _ in roles:
            sources[role].open()
        keys = {(s.identity[0], s.identity[1]) for s in sources.values()}
        if len(keys) != 3:
            raise PackageError("path overlap: two source paths name the same file")
        loader = sources["loader"].read_small()
        core = sources["core"].read_small()

        for relative in DIRECTORIES:
            output.mkdir(relative)
        files = {}
        client = CLIENT + "/"
        files[PACKAGE_NAME + "/mod.json"] = output.write_bytes(
            PACKAGE_NAME + "/mod.json", canonical(profile["mod_json"]))
        files[client + "index.js"] = output.write_bytes(
            client + "index.js", profile["entry_utf8"].encode("utf-8"))
        name = client + profile["sources"]["loader"]["file"]
        files[name] = output.write_bytes(name, loader)
        name = client + profile["sources"]["core"]["file"]
        files[name] = output.write_bytes(name, core)
        name = client + profile["sources"]["dictionary"]["file"]
        files[name] = output.copy_stream(name, sources["dictionary"])

        # Source/copy hashes agree and every source is still the file first opened.
        for role, _ in roles:
            src = sources[role]
            copy = files[client + profile["sources"][role]["file"]]
            if (copy["bytes"], copy["sha256"]) != (src.pin["bytes"], src.pin["sha256"]):
                raise PackageError(f"{role}: copy identity differs from the source")
            src.check_stable()
        for role, _ in roles:
            sources[role].close()

        package_files = _package_files(profile)
        manifest = {
            "schema": 1,
            "task": TASK,
            "profile": profile["profile"],
            "generator": generator,
            "package": profile["package"],
            "acquisition": profile["acquisition"],
            "sources": profile["sources"],
            "entry": profile["entry"],
            "directories": [{"path": d, "mode": "0700"} for d in DIRECTORIES],
            "files": [files[path] for path in package_files],
        }
        manifest_bytes = canonical(manifest)
        manifest_record = output.write_bytes(MANIFEST, manifest_bytes)
        output.check_tree(package_files + [MANIFEST])

        complete = {
            "schema": 1,
            "task": TASK,
            "profile": profile["profile"],
            "state": "complete",
            "files": len(package_files),
            "manifest": {"file": MANIFEST, "bytes": manifest_record["bytes"],
                         "sha256": manifest_record["sha256"]},
        }
        # Written beside, read back, then linked into place (never over an entry).
        output.write_bytes(COMPLETE_PARTIAL, canonical(complete))
        try:
            os.link(output.path(COMPLETE_PARTIAL), output.path(COMPLETE), follow_symlinks=False)
        except OSError as error:
            raise PackageError(f"cannot finalize completion ({_why(error)})") from None
        st = os.lstat(output.path(COMPLETE))
        output.created.append((COMPLETE, st.st_dev, st.st_ino, False))
        try:
            os.unlink(output.path(COMPLETE_PARTIAL))
        except OSError as error:
            raise PackageError(f"cannot finalize completion ({_why(error)})") from None
        output.read_back(COMPLETE, len(canonical(complete)), _sha(canonical(complete)))
        output.check_tree(package_files + [MANIFEST, COMPLETE])
    except BaseException as error:
        failure = error
    finally:
        for src in sources.values():
            try:
                src.close()
            except OSError as error:
                if failure is None:
                    failure = PackageError(f"{src.role}: close failed ({_why(error)})")
    if failure is not None:
        problem = output.cleanup()
        if problem is not None:
            if isinstance(failure, PackageError):
                raise PackageError(f"{failure}; cleanup: {problem}") from None
            raise PackageError(f"internal {type(failure).__name__}; cleanup: {problem}") from None
        raise failure
    return {
        "task": TASK,
        "state": "complete",
        "output": os.path.basename(output_root),
        "package": PACKAGE_NAME,
        "files": len(_package_files(profile)),
        "manifest_sha256": manifest_record["sha256"],
    }


def main(argv=None):
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 4 or any(a.startswith("-") for a in args):
        sys.stderr.write("usage: npc_plaintext_package.py LOADER_SOURCE CORE_SOURCE "
                         "DICTIONARY_SOURCE OUTPUT\n")
        return 2
    try:
        result = build(*args)
    except PackageError as error:
        sys.stderr.write(f"npc_plaintext_package: refused/failed: {error}\n")
        return 1
    except OSError as error:
        sys.stderr.write(f"npc_plaintext_package: failed: {_why(error)}\n")
        return 1
    except Exception as error:  # bounded diagnosis, never a traceback
        sys.stderr.write(f"npc_plaintext_package: failed: internal {type(error).__name__}\n")
        return 1
    sys.stdout.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
    sys.stdout.flush()
    return 0


if __name__ == "__main__":
    sys.exit(main())
