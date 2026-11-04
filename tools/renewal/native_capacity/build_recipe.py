"""Bounded Linux/arm64 map-server build/export recipe (T10.010.003).

Root executes this in T10.010.004; this task only implements and tests it.

  plan            verify a prepared tree, write deterministic inputs and PLAN.json
                  (no Engine contact). --mode resolve qualifies dependencies only;
                  --mode build requires an explicit exact apk lock. Optional
                  --apk-local MANIFEST.json (either mode, T10.010.004) adds bound,
                  stock-key-authenticated local APK inputs; see load_local_manifest.
  execute         ONE owned compiler container through the slim Engine API:
                  census -> create -> PUT inputs -> PUT owner.env -> start ->
                  poll -> [kill] -> logs -> GET /work/out -> delete -> 404
  validate-export check the exported artifact offline
  image-context   minimal no-ARG/no-RUN single-file COPY context for import
  import-check    create (never start) a container from an image, read back the
                  imported file's bytes, mode and owner, delete it

Engine facts used (pinned slim source, nebula 2e9cf43):
- This container recipe uses only containers json/create/inspect/start/kill/
  archive GET+PUT/logs/DELETE. It does not call /build, commit, image save,
  exec or pull. It avoids /wait because an HTTP disconnect does not cancel it.
  Separately, pinned slim source implements the no-RUN single-COPY /build
  path; that image-creation step needs its own admission and actual check.
- PUT archive buffers the whole body (2 GiB cap), does not decompress it and
  unpacks with preserved permissions; GET archive streams a tar (owners kept).
- mounts.rs: HostConfig.Binds creates a missing bind source; Mounts
  Type=bind refuses a missing source at create. Only Mounts is used.
- slim-runtime linux.rs cgroup_setup: memory.max=Memory; memory.swap.max =
  MemorySwap-Memory if larger, else Memory; cpu.max="NanoCpus/10000 100000";
  pids.max=PidsLimit if >0. Writes are best-effort (errors discarded), so the
  guest reads its own /slim/<id> leaves through a read-only cgroup2 view and
  fails before any install/build unless every value matches the plan.
- engine.rs create: a taken name is a Conflict; the cgroup ID is the container ID.
"""

import argparse
import base64
import gzip
import hashlib
import http.client
import io
import json
import os
from pathlib import Path
import re
import signal
import stat
import socket
import sys
import tarfile
import threading
import time
import uuid
import zlib

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prepare_source as ps  # noqa: E402

GUEST = HERE / "build" / "guest_build.sh"
GUEST_LIB = HERE / "build" / "guest_lib.sh"
PATCH = HERE / "coin_capacity.patch"
API = "/v1.43"
ROLE_LABEL = "t10.010.003.role"
RUN_LABEL = "t10.010.003.run"
MIB = 1 << 20
EM_AARCH64 = 183
SWAP_BYTES = MIB  # slim cannot express swap 0; MemorySwap=Memory+1MiB -> swap.max 1MiB
CGROUP_VIEW = "/run/root-cgroup-view"
CGROUP_SOURCE = "/sys/fs/cgroup/slim"
# Declared owners: exported binaries are written by root in the guest; the
# imported file is a COPY without --chown (root). Mode 0755 lets the image's
# unprivileged rathena user execute it. Both are verified, never assumed.
ARTIFACT_OWNER = {"uid": 0, "gid": 0, "mode": "0o755"}
IMPORT_OWNER = {"uid": 0, "gid": 0, "mode": "0o755"}
CRASH_VERIFY_ORIG = "d4b7295b16677e2417cf87316e70a211b6d58c90aece1cc43bbea3e65f8e8ebe"
CRASH_REWRITES = (("cd /rathena/ragnarok-crash-tests", "cd /work/crash/ragnarok-crash-tests", 1),
                  ("/symbols/trace-tests", "/work/crash/symbols/trace-tests", 2))
LIMITS = {  # positive bounds for every resource parameter
    "memory_mib": (512, 6144), "cpus": (1, 64), "jobs": (1, 64), "pids": (64, 4096),
    "reserve_mib": (256, 8192), "step_timeout": (60, 86400), "deadline": (600, 86400),
    "post_budget": (30, 3600), "cleanup_budget": (30, 3600),
}
BODY_CAP = {"json": 8 * MIB, "logs": 64 * MIB, "export": 1024 * MIB, "import": 256 * MIB}
LOCAL_SCHEMA = "t10.010.004/apk-local/v1"
LOCAL_CAP = {"manifest": MIB, "file": 128 * MIB, "total": 512 * MIB, "packages": 256}
DEPS_RECIPE = "t10.010.004/deps/v1"


class RecipeError(Exception):
    pass


class EngineIOError(RecipeError):
    """Transport failure: no complete response, so the request outcome is unknown."""


class EngineStatusError(RecipeError):
    def __init__(self, status, msg):
        super().__init__(msg)
        self.status = status


class Cancelled(BaseException):
    """SIGTERM/SIGINT: unwinds through owned cleanup, never swallowed."""


class CleanupUnresolved(RecipeError):
    """An owned object could not be deleted/confirmed absent. .detail holds
    the ownership record; __cause__ is the original failure, if any."""

    def __init__(self, detail):
        super().__init__(detail["message"])
        self.detail = detail


class CancelledUnresolved(Cancelled):
    """Cancellation whose owned-object cleanup also failed: still a
    cancellation (exit 143), carrying the same ownership record."""

    def __init__(self, detail):
        super().__init__(detail["message"])
        self.detail = detail


def sha256(b):
    return hashlib.sha256(b).hexdigest()


def bounded(name, value):
    lo, hi = LIMITS[name]
    if not isinstance(value, int) or isinstance(value, bool) or not lo <= value <= hi:
        raise RecipeError(f"{name}={value!r} outside {lo}..{hi}")
    return value


# ------------------------------------------------------------------ inputs
def deterministic_tar_gz(root, mtime):
    """Sorted, uid/gid 0, fixed mtime, 0644/0755 only, gzip mtime 0."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.PAX_FORMAT) as tar:
        for rel, ex, _, _ in ps.tree_listing(root):
            p = root / rel
            info = tarfile.TarInfo(rel)
            info.size = p.stat().st_size
            info.mode = 0o755 if ex == "755" else 0o644
            info.mtime = mtime
            info.uid = info.gid = 0
            info.uname = info.gname = ""
            with open(p, "rb") as fh:
                tar.addfile(info, fh)
    out = io.BytesIO()
    with gzip.GzipFile(fileobj=out, mode="wb", mtime=0, compresslevel=6) as gz:
        gz.write(raw.getvalue())
    return out.getvalue()


def wrapper_tar(members):
    """Upload body for PUT archive at /work/in: name -> (bytes, mode); root-owned."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name in sorted(members):
            data, mode = members[name]
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), mode, 0
            info.uid = info.gid = 0
            tar.addfile(info, io.BytesIO(data))
    return raw.getvalue()


def crash_verify(original, expect_sha=CRASH_VERIFY_ORIG):
    """Rewrite only the fixture's two hardcoded roots to owned /work/crash paths."""
    if sha256(original) != expect_sha:
        raise RecipeError("crash-trace verify.sh is not the pinned app version")
    text = original.decode()
    for old, new, count in CRASH_REWRITES:
        if text.count(old) != count:
            raise RecipeError(f"crash verify rewrite anchor {old!r} count {text.count(old)} != {count}")
        text = text.replace(old, new)
    if "/rathena" in text or re.search(r"(?<![\w/])/symbols", text):
        raise RecipeError("crash verify still references a non-owned root")
    return text.encode()


WANT = ("bash", "git", "make", "cmake", "gcc", "g++", "zlib-dev", "mariadb-dev", "linux-headers",
        "libunwind-dev", "binutils", "patch")
DEP_LINE = r"[A-Za-z0-9][A-Za-z0-9._+-]*=[0-9][A-Za-z0-9._+~-]*-r\d+"


def _dep_lines(data, what, allow_empty):
    lines = data.decode().splitlines()
    if not lines and not allow_empty:
        raise RecipeError(f"{what} must not be empty")
    if lines != sorted(set(lines)):
        raise RecipeError(f"{what} must be sorted and unique")
    for line in lines:
        if not re.fullmatch(DEP_LINE, line):
            raise RecipeError(f"{what} line {line!r} is not name=version-rN")
    return dict(line.split("=", 1) for line in lines)


def parse_deps(lock, base, abi=None):
    """Dependency model: BASE = exact name=version of every package the stock
    image already has (frozen; the guest refuses an image that differs);
    DELTA (lock) = exact name=version of every package the install adds.
    WANT is covered by BASE + DELTA, DELTA never re-pins a BASE package and
    libunwind-dev is 1.8.1 wherever it comes from. The guest then requires the
    install to add exactly DELTA and change no BASE package."""
    b = _dep_lines(base, "apk base", allow_empty=False)
    d = _dep_lines(lock, "apk lock", allow_empty=True)
    both = sorted(set(b) & set(d))
    if both:
        raise RecipeError(f"apk lock re-pins base packages {both} (base upgrades are refused)")
    full = {**b, **d}
    missing = [w for w in WANT if w not in full]
    if missing:
        raise RecipeError(f"required packages in neither base nor lock: {missing}")
    if not re.fullmatch(r"1\.8\.1-r\d+", full["libunwind-dev"]):
        raise RecipeError("libunwind-dev is not ~1.8.1")
    if abi:
        for name, want in (("musl", abi[0]), ("libstdc++", abi[1])):
            if b.get(name) != want:
                raise RecipeError(f"base {name}={b.get(name)!r} != runtime ABI {want!r}")
    return sorted(f"{k}={v}" for k, v in d.items()), sorted(f"{k}={v}" for k, v in b.items())


NAME_RE = r"[A-Za-z0-9][A-Za-z0-9._+-]*"
VERSION_RE = r"[0-9][A-Za-z0-9._+~-]*-r\d+"
LOCAL_FILE_RE = r"[A-Za-z0-9][A-Za-z0-9._+-]*\.apk"
LOCAL_KEYS = {"file", "name", "version", "bytes", "sha256"}


def _no_dup_keys(pairs):
    keys = [k for k, _ in pairs]
    if len(keys) != len(set(keys)):
        raise RecipeError(f"local manifest has duplicate keys {sorted(keys)}")
    return dict(pairs)


def read_bound(dirfd, name, cap, want_bytes=None):
    """Read one file named relative to dirfd: final component not a symlink,
    a regular file with exactly one link, at most cap bytes (and exactly
    want_bytes if given), unchanged while read and still the same inode at
    that name afterwards. Never blocks on a FIFO (O_NONBLOCK, then S_ISREG)."""
    flags = os.O_RDONLY | os.O_NOFOLLOW | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(name, flags, dir_fd=dirfd)
    except OSError as exc:
        raise RecipeError(f"local input {name!r}: cannot open safely ({exc.strerror})") from exc
    try:
        st = os.fstat(fd)
        if not stat.S_ISREG(st.st_mode):
            raise RecipeError(f"local input {name!r} is not a regular file")
        if st.st_nlink != 1:
            raise RecipeError(f"local input {name!r} has {st.st_nlink} links (single-link files only)")
        if st.st_size > cap:
            raise RecipeError(f"local input {name!r} is {st.st_size} bytes > cap {cap}")
        if want_bytes is not None and st.st_size != want_bytes:
            raise RecipeError(f"local input {name!r} is {st.st_size} bytes, manifest says {want_bytes}")
        chunks, total = [], 0
        while True:
            c = os.read(fd, min(1 << 20, cap + 1 - total))
            if not c:
                break
            total += len(c)
            chunks.append(c)
            if total > cap:
                raise RecipeError(f"local input {name!r} grew past cap {cap}")
        data = b"".join(chunks)
        st2 = os.fstat(fd)
    finally:
        os.close(fd)
    ident = lambda s_: (s_.st_dev, s_.st_ino, s_.st_size, s_.st_mtime_ns, s_.st_nlink)  # noqa: E731
    if len(data) != st.st_size or ident(st2) != ident(st):
        raise RecipeError(f"local input {name!r} changed while being read")
    try:
        after = os.lstat(name, dir_fd=dirfd)
    except OSError as exc:
        raise RecipeError(f"local input {name!r} vanished after reading") from exc
    if ident(after) != ident(st):
        raise RecipeError(f"local input {name!r} was replaced while being read")
    return data


APKV2_CAP = {"sig_gz": MIB, "sig_raw": MIB, "ctl_gz": 8 * MIB, "ctl_raw": 16 * MIB, "entries": 64,
             "pkginfo": MIB}


def _gzip_member(data, off, cap_gz, cap_raw, what):
    """One complete gzip member starting at data[off]: returns (end, inflated).
    Bounded: at most cap_gz compressed and cap_raw inflated bytes. A member
    that does not end inside the bound is truncated/oversized and refuses."""
    if data[off:off + 3] != b"\x1f\x8b\x08":
        raise RecipeError(f"apk {what}: not a gzip/deflate member")
    window = data[off:off + cap_gz]
    d = zlib.decompressobj(31)
    out, buf = [], window
    total = 0
    try:
        while True:
            chunk = d.decompress(buf, 1 << 16)
            total += len(chunk)
            if total > cap_raw:
                raise RecipeError(f"apk {what}: inflates past {cap_raw} bytes")
            out.append(chunk)
            if d.eof:
                break
            buf = d.unconsumed_tail
            if not buf and not chunk:
                raise RecipeError(f"apk {what}: truncated gzip member")
    except zlib.error as exc:
        raise RecipeError(f"apk {what}: corrupt gzip member ({exc})") from exc
    end = off + len(window) - len(d.unused_data)
    return end, b"".join(out)


PAX_TIME_KEYS = {"atime", "ctime", "mtime"}


def _pax_times_only(body, what):
    """A local pax header may only carry time records (what Alpine's APKs
    actually contain); path/size/link or any other key would change how the
    entry is read and is refused rather than interpreted."""
    off = 0
    while off < len(body):
        sp = body.find(b" ", off)
        if sp < 0 or not body[off:sp].isdigit():
            raise RecipeError(f"apk {what}: malformed pax record")
        n = int(body[off:sp])
        rec = body[off:off + n]
        if n <= sp - off + 1 or len(rec) != n or not rec.endswith(b"\n") or b"=" not in rec:
            raise RecipeError(f"apk {what}: malformed pax record")
        key = rec[sp - off + 1:].split(b"=", 1)[0].decode("ascii", "replace")
        if key not in PAX_TIME_KEYS:
            raise RecipeError(f"apk {what}: unsupported pax key {key!r}")
        off += n


def _tar_entries(raw, what):
    """Complete regular-file ustar entries, each optionally preceded by a
    local pax header holding only time records. No global pax, long names,
    links or directories. Header checksums are verified; zero blocks only
    at the end."""
    if len(raw) % 512:
        raise RecipeError(f"apk {what}: tar stream is not whole 512-byte blocks")
    entries, off, pax = [], 0, False
    while off < len(raw):
        h = raw[off:off + 512]
        if h == bytes(512):
            if raw[off:].strip(b"\0"):
                raise RecipeError(f"apk {what}: data after a zero tar block")
            break
        want = int(h[148:156].replace(b"\0", b" ").strip() or b"-1", 8)
        if want != sum(h[:148]) + 8 * 32 + sum(h[156:]):
            raise RecipeError(f"apk {what}: tar header checksum mismatch")
        kind = h[156:157]
        if kind not in (b"0", b"\0", b"x"):
            raise RecipeError(f"apk {what}: unsupported tar entry type {kind!r}")
        if kind == b"x" and pax:
            raise RecipeError(f"apk {what}: consecutive pax headers")
        name = h[:100].split(b"\0", 1)[0]
        if h[257:262] == b"ustar" and h[345:500].strip(b"\0"):
            raise RecipeError(f"apk {what}: tar prefix names are not supported")
        field = h[124:136]
        if field[:1] in (b"\x80", b"\xff"):
            raise RecipeError(f"apk {what}: base-256 tar size not supported")
        size = int(field.replace(b"\0", b" ").strip() or b"0", 8)
        body = off + 512
        if body + size > len(raw):
            raise RecipeError(f"apk {what}: truncated tar entry {name!r}")
        if kind == b"x":
            _pax_times_only(raw[body:body + size], what)
            pax = True
        else:
            try:
                entries.append((name.decode("ascii", "strict"), raw[body:body + size]))
            except UnicodeDecodeError as exc:
                raise RecipeError(f"apk {what}: non-ASCII tar name") from exc
            pax = False
        if len(entries) > APKV2_CAP["entries"]:
            raise RecipeError(f"apk {what}: too many tar entries")
        off = body + (size + 511) // 512 * 512
    if pax:
        raise RecipeError(f"apk {what}: pax header without an entry")
    if not entries:
        raise RecipeError(f"apk {what}: empty tar member")
    return entries


def apk_identity(data):
    """Package identity derived from an APK v2 file's own bytes (T10.010.004).

    Layout (apk-tools 44dcdfc extract_v2.c / io_gunzip.c): gzip member 1 holds
    only .SIGN.* tar entries; member 2 (the control member) holds dot-file
    entries including exactly one .PKGINFO; member 3+ is the data, which is
    never inflated here. apk's package identity (installed-db and index C:)
    is "Q1" + Base64(SHA1(complete compressed control gzip member bytes)) --
    not a whole-file hash and not a .PKGINFO hash (blob.c apk_blob_push_hash).

    This is IDENTITY PARSING ONLY. Signature entries are counted, never
    trusted: only the guest's real `apk verify` with the stock keys
    authenticates. Unsupported, truncated or ambiguous layouts refuse."""
    if not isinstance(data, (bytes, bytearray)) or len(data) > LOCAL_CAP["file"]:
        raise RecipeError("apk: input missing or over the file cap")
    data = bytes(data)
    s_end, s_raw = _gzip_member(data, 0, APKV2_CAP["sig_gz"], APKV2_CAP["sig_raw"], "signature member")
    sig = _tar_entries(s_raw, "signature member")
    if not all(n.startswith(".SIGN.") and "/" not in n for n, _ in sig):
        raise RecipeError("apk: first member is not signature-only (unsupported layout)")
    c_end, c_raw = _gzip_member(data, s_end, APKV2_CAP["ctl_gz"], APKV2_CAP["ctl_raw"], "control member")
    ctl = _tar_entries(c_raw, "control member")
    names = [n for n, _ in ctl]
    if any(not n.startswith(".") or "/" in n or n.startswith(".SIGN.") or n == ".INSTALL" for n in names):
        raise RecipeError(f"apk: control member has non-control entries {names}")
    if names.count(".PKGINFO") != 1 or len(set(names)) != len(names):
        raise RecipeError("apk: control member must hold exactly one .PKGINFO and unique entries")
    if data[c_end:c_end + 3] != b"\x1f\x8b\x08":
        raise RecipeError("apk: no data gzip member after the control member")
    info = dict(ctl)[".PKGINFO"]
    if len(info) > APKV2_CAP["pkginfo"]:
        raise RecipeError("apk: .PKGINFO too large")
    fields = {}
    for line in info.decode("utf-8", "strict").split("\n"):
        if not line or line.startswith("#") or " = " not in line:
            continue
        k, v = line.split(" = ", 1)
        if k in ("pkgname", "pkgver", "arch", "datahash"):
            if k in fields:
                raise RecipeError(f"apk: .PKGINFO repeats {k} (ambiguous)")
            fields[k] = v
    missing = [k for k in ("pkgname", "pkgver", "arch", "datahash") if k not in fields]
    if missing:
        raise RecipeError(f"apk: .PKGINFO lacks {missing}")
    if not re.fullmatch(NAME_RE, fields["pkgname"]) or not re.fullmatch(VERSION_RE, fields["pkgver"]):
        raise RecipeError("apk: .PKGINFO name/version malformed")
    if not re.fullmatch(r"[0-9a-f]{64}", fields["datahash"]):
        raise RecipeError("apk: .PKGINFO datahash malformed")
    control = data[s_end:c_end]
    digest = hashlib.sha1(control).digest()
    return {"name": fields["pkgname"], "version": fields["pkgver"], "arch": fields["arch"],
            "q1": "Q1" + base64.b64encode(digest).decode(), "control_sha1": digest.hex(),
            "datahash": fields["datahash"], "signature_entries": len(sig),
            "sha256": sha256(data), "bytes": len(data)}


def load_local_manifest(path, arch="aarch64"):
    """Explicit local APK inputs (T10.010.004). The manifest is a small JSON file:

      {"schema": "t10.010.004/apk-local/v1",
       "packages": [{"file": "musl-dev-1.2.5-r23.apk", "name": "musl-dev",
                     "version": "1.2.5-r23", "bytes": 2528533, "sha256": "<64 hex>"}]}

    "file" is a plain basename in the manifest's own directory; nothing else is
    discovered. Keys are exact (no caller "verified"/trust flag is accepted).
    Every file is read once, bounded, as a safe regular single-link file, and its
    byte count and SHA-256 must match, and apk_identity() must derive exactly the
    claimed name/version and the expected arch from the file's own control
    member before it can enter an upload. Duplicate files, names or hashes
    refuse. Only the guest's real stock-key verification authenticates a
    package; this binds bytes and derived identity only.
    Returns (manifest_bytes, [entry + "data"], sorted by name)."""
    path = Path(path)
    try:
        dirfd = os.open(str(path.parent), os.O_RDONLY | getattr(os, "O_DIRECTORY", 0))
    except OSError as exc:
        raise RecipeError(f"local manifest directory {path.parent}: {exc.strerror}") from exc
    try:
        raw = read_bound(dirfd, path.name, LOCAL_CAP["manifest"])
        try:
            m = json.loads(raw.decode(), object_pairs_hook=_no_dup_keys)
        except (UnicodeDecodeError, ValueError) as exc:
            raise RecipeError(f"local manifest is not JSON: {exc}") from exc
        if not isinstance(m, dict) or set(m) != {"schema", "packages"} or m["schema"] != LOCAL_SCHEMA:
            raise RecipeError(f"local manifest must be exactly {{schema: {LOCAL_SCHEMA}, packages}}")
        pk = m["packages"]
        if not isinstance(pk, list) or not 1 <= len(pk) <= LOCAL_CAP["packages"]:
            raise RecipeError("local manifest packages must be a non-empty bounded list")
        entries, total = [], 0
        for i, e in enumerate(pk):
            if not isinstance(e, dict) or set(e) != LOCAL_KEYS:
                raise RecipeError(f"local package {i} must have exactly keys {sorted(LOCAL_KEYS)}")
            f, n, v, b, h = e["file"], e["name"], e["version"], e["bytes"], e["sha256"]
            if not (isinstance(f, str) and re.fullmatch(LOCAL_FILE_RE, f) and f not in (".apk",)):
                raise RecipeError(f"local package {i} file {f!r} is not a plain .apk basename")
            if not (isinstance(n, str) and re.fullmatch(NAME_RE, n)):
                raise RecipeError(f"local package {i} name {n!r}")
            if not (isinstance(v, str) and re.fullmatch(VERSION_RE, v)):
                raise RecipeError(f"local package {i} version {v!r}")
            if not isinstance(b, int) or isinstance(b, bool) or not 0 < b <= LOCAL_CAP["file"]:
                raise RecipeError(f"local package {i} bytes {b!r}")
            if not (isinstance(h, str) and re.fullmatch(r"[0-9a-f]{64}", h)):
                raise RecipeError(f"local package {i} sha256 {h!r}")
            total += b
            if total > LOCAL_CAP["total"]:
                raise RecipeError(f"local inputs exceed {LOCAL_CAP['total']} bytes")
            entries.append(dict(e))
        for key in ("file", "name", "sha256"):
            vals = [e[key] for e in entries]
            if len(vals) != len(set(vals)):
                raise RecipeError(f"local manifest has duplicate/conflicting {key} entries")
        for e in entries:
            data = read_bound(dirfd, e["file"], LOCAL_CAP["file"], e["bytes"])
            if sha256(data) != e["sha256"]:
                raise RecipeError(f"local input {e['file']} sha256 differs from the manifest")
            ident = apk_identity(data)  # from the bytes themselves; not authentication
            if (ident["name"], ident["version"]) != (e["name"], e["version"]):
                raise RecipeError(f"local input {e['file']} control identity {ident['name']}={ident['version']} "
                                  f"is not the claimed {e['name']}={e['version']}")
            if ident["arch"] != arch:
                raise RecipeError(f"local input {e['file']} arch {ident['arch']!r} != {arch!r}")
            e["data"], e["identity"] = data, ident
    finally:
        os.close(dirfd)
    return raw, sorted(entries, key=lambda e: e["name"])


def local_conflicts(entries, base=None, lock=None, abi_names=("musl", "libstdc++")):
    """Refuse local inputs that would replace a frozen base/ABI package, that
    conflict with the build delta, or that put libunwind-dev off 1.8.1."""
    for e in entries:
        n, v = e["name"], e["version"]
        if n in abi_names or (base is not None and n in base):
            raise RecipeError(f"local input {n}={v} would replace a frozen base package")
        if lock is not None and lock.get(n) != v:
            raise RecipeError(f"local input {n}={v} conflicts with the delta lock ({lock.get(n)!r})")
        if n == "libunwind-dev" and not re.fullmatch(r"1\.8\.1-r\d+", v):
            raise RecipeError("local libunwind-dev is not ~1.8.1")


def local_list(entries):
    """Guest list: "<index> <sha256> <bytes> <name> <version> <Q1>"; index names
    local-<index>.apk; Q1 is the host-derived control identity, which the guest
    joins to the installed database after the transaction."""
    return "".join(f"{i} {e['sha256']} {e['bytes']} {e['name']} {e['version']} {e['identity']['q1']}\n"
                   for i, e in enumerate(entries)).encode()


def expected_cgroup(memory, memory_swap, nano_cpus, pids):
    """slim-runtime cgroup_setup, for the values this plan requests."""
    swap = memory_swap - memory if memory_swap > memory else memory
    return {"memory.max": str(memory), "memory.swap.max": str(swap),
            "cpu.max": f"{nano_cpus // 10_000} 100000", "pids.max": str(pids)}


def plan(prepared, rundir, base_image, expect_musl, expect_libstdcxx, mem_available, host_cpus, mode="build",
         apk_lock=None, apk_base=None, memory_mib=1536, cpus=2, jobs=1, pids=1024, step_timeout=3600, deadline=4 * 3600,
         reserve_mib=768, post_budget=300, cleanup_budget=180, packetver="20221005", manifest=None, pins=None,
         apk_local=None):
    manifest = manifest or ps.load_manifest(ps.MANIFEST)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", base_image or ""):
        raise RecipeError("base image must be an immutable local image ID sha256:<64 hex>")
    if not re.fullmatch(r"\d{8}", packetver):
        raise RecipeError("bad packet version")
    if mode not in ("resolve", "build"):
        raise RecipeError("mode must be resolve or build")
    for v in (expect_musl, expect_libstdcxx):
        if not re.fullmatch(r"[0-9][0-9A-Za-z._-]*-r\d+", v or ""):
            raise RecipeError(f"bad apk version {v!r}")
    for name, value in (("memory_mib", memory_mib), ("cpus", cpus), ("jobs", jobs), ("pids", pids),
                        ("reserve_mib", reserve_mib), ("step_timeout", step_timeout), ("deadline", deadline),
                        ("post_budget", post_budget), ("cleanup_budget", cleanup_budget)):
        bounded(name, value)
    if not isinstance(host_cpus, int) or isinstance(host_cpus, bool) or host_cpus < 1 or cpus > host_cpus:
        raise RecipeError(f"cpus {cpus} exceeds fresh host CPU count {host_cpus}")
    if jobs > cpus:
        raise RecipeError("jobs must not exceed cpus")
    if step_timeout > deadline:
        raise RecipeError("step timeout must not exceed the deadline")
    need = (memory_mib + reserve_mib) * MIB
    if not isinstance(mem_available, int) or mem_available < need:
        raise RecipeError(f"insufficient fresh MemAvailable {mem_available} < limit+reserve {need}")
    lock = base = b""
    if mode == "build":
        if apk_lock is None or apk_base is None:
            raise RecipeError("build mode requires explicit qualified --apk-lock and --apk-base "
                              "(run --mode resolve first)")
        lock, base = Path(apk_lock).read_bytes(), Path(apk_base).read_bytes()
        parse_deps(lock, base, (expect_musl, expect_libstdcxx))
    elif apk_lock is not None or apk_base is not None:
        raise RecipeError("resolve mode takes no lock or base")
    local_raw, local = None, []
    if apk_local is not None:
        local_raw, local = load_local_manifest(apk_local)
        if mode == "build":
            local_conflicts(local, _dep_lines(base, "apk base", False), _dep_lines(lock, "apk lock", True))
        else:
            local_conflicts(local)
    llist = local_list(local) if local else b""
    lock_map = _dep_lines(lock, "apk lock", True) if mode == "build" else {}
    offline = mode == "build" and set(lock_map.items()) <= {(e["name"], e["version"]) for e in local}
    rundir = Path(rundir).resolve()
    if rundir.exists():
        raise RecipeError(f"{rundir} exists; refuse to reuse run state")
    ver = ps.verify(Path(prepared), manifest, pins=pins)
    rec = json.loads((Path(prepared) / ps.MARKER).read_text())
    src_root = Path(prepared) / "source"
    src = deterministic_tar_gz(src_root, mtime=1760000000)
    orig_verify = (src_root / "ragnarok-crash-tests/verify.sh").read_bytes()
    cverify = crash_verify(orig_verify, manifest.get("crash_verify_sha256", CRASH_VERIFY_ORIG))
    patch, guest, lib = PATCH.read_bytes(), GUEST.read_bytes(), GUEST_LIB.read_bytes()
    memory, memory_swap, nano = memory_mib * MIB, memory_mib * MIB + SWAP_BYTES, cpus * 10**9
    cg = expected_cgroup(memory, memory_swap, nano, pids)
    env = "".join(f"{k}='{v}'\n" for k, v in (
        ("MODE", mode), ("SOURCE_SHA256", sha256(src)), ("PATCH_SHA256", sha256(patch)),
        ("CRASH_VERIFY_ORIG_SHA256", sha256(orig_verify)), ("CRASH_VERIFY_SHA256", sha256(cverify)),
        ("LOCK_SHA256", sha256(lock) if mode == "build" else "none"),
        ("BASE_SHA256", sha256(base) if mode == "build" else "none"), ("PACKETVER", packetver), ("JOBS", jobs),
        ("STEP_TIMEOUT", step_timeout), ("EXPECT_MUSL", expect_musl), ("EXPECT_LIBSTDCXX", expect_libstdcxx),
        ("EXPECT_ARCH", "aarch64"), ("EXPECT_MEMORY_MAX", cg["memory.max"]),
        ("EXPECT_SWAP_MAX", cg["memory.swap.max"]), ("EXPECT_CPU_MAX", cg["cpu.max"]),
        ("EXPECT_PIDS_MAX", cg["pids.max"]), ("LOCAL_LIST_SHA256", sha256(llist) if local else "none"))).encode()
    members = {"source.tar.gz": (src, 0o644), "coin_capacity.patch": (patch, 0o644),
               "guest_build.sh": (guest, 0o755), "guest_lib.sh": (lib, 0o644),
               "crash_verify.sh": (cverify, 0o644), "inputs.env": (env, 0o644)}
    if mode == "build":
        members["apk.lock"] = (lock, 0o644)
        members["apk.base"] = (base, 0o644)
    if local:
        members["apk-local.list"] = (llist, 0o644)
        for i, e in enumerate(local):
            members[f"local-{i}.apk"] = (e["data"], 0o644)
    upload = wrapper_tar(members)
    run_id = uuid.uuid4().hex[:12]
    create = {
        "Image": base_image,
        "User": "0:0",
        "Entrypoint": ["/bin/sh"],
        "Cmd": ["/work/in/guest_build.sh"],
        "WorkingDir": "/work",
        "Env": ["LC_ALL=C", "SOURCE_DATE_EPOCH=1760000000"],
        "Labels": {ROLE_LABEL: "compiler", RUN_LABEL: run_id},
        "HostConfig": {
            "Memory": memory, "MemorySwap": memory_swap, "NanoCpus": nano, "PidsLimit": pids,
            "AutoRemove": False, "RestartPolicy": {"Name": "no"},
            "Mounts": [{"Type": "bind", "Source": CGROUP_SOURCE, "Target": CGROUP_VIEW, "ReadOnly": True}],
        },
    }
    rundir.mkdir(parents=True)
    (rundir / "upload.tar").write_bytes(upload)
    p = {
        "schema": "t10.010.003/build-plan/v2",
        "mode": mode,
        "run_id": run_id,
        "container_name": f"t10-010-003-build-{run_id}",
        "prepared": {"tree_sha256": ver["prepared_tree_sha256"], "files": ver["files"],
                     "identity": rec["identity"]},
        "inputs": {"source_tar_gz_sha256": sha256(src), "source_tar_gz_bytes": len(src),
                   "coin_capacity_patch_sha256": sha256(patch), "guest_build_sh_sha256": sha256(guest),
                   "guest_lib_sh_sha256": sha256(lib), "crash_verify_orig_sha256": sha256(orig_verify),
                   "crash_verify_sha256": sha256(cverify), "apk_lock_sha256": sha256(lock) if mode == "build" else None,
                   "apk_lock": lock.decode().splitlines() if mode == "build" else None,
                   "apk_base_sha256": sha256(base) if mode == "build" else None,
                   "apk_base": base.decode().splitlines() if mode == "build" else None,
                   "inputs_env": env.decode(), "upload_tar_sha256": sha256(upload), "upload_tar_bytes": len(upload),
                   "apk_local_manifest_sha256": sha256(local_raw) if local else None,
                   "apk_local_list_sha256": sha256(llist) if local else None,
                   "apk_local": [{"member": f"local-{i}.apk", "name": e["name"], "version": e["version"],
                                  "bytes": e["bytes"], "sha256": e["sha256"], "manifest_file": e["file"],
                                  "arch": e["identity"]["arch"], "q1": e["identity"]["q1"],
                                  "control_sha1": e["identity"]["control_sha1"]}
                                 for i, e in enumerate(local)] or None},
        "dependency_recipe": DEPS_RECIPE,
        "apk_package_network": not offline,
        "packetver": packetver,
        "abi_expect": {"musl": expect_musl, "libstdc++": expect_libstdcxx, "arch": "aarch64"},
        "artifact_owner": ARTIFACT_OWNER,
        "import_owner": IMPORT_OWNER,
        "expected_cgroup": cg,
        "limits": {"memory_bytes": memory, "memory_swap_bytes": memory_swap, "nano_cpus": nano, "pids": pids,
                   "jobs": jobs, "host_cpus": host_cpus, "step_timeout_s": step_timeout, "deadline_s": deadline,
                   "post_budget_s": post_budget, "cleanup_budget_s": cleanup_budget,
                   "absolute_bound_s": deadline + post_budget + cleanup_budget,
                   "mem_available_at_plan": mem_available, "reserve_bytes": reserve_mib * MIB},
        "create": create,
        "network": ("default container networking is retained; the build's complete authenticated local closure "
                    "needs no package network (offline replay not yet exercised)" if offline else
                    "default container networking is required for the apk index and repository additions"),
    }
    (rundir / "PLAN.json").write_text(json.dumps(p, indent=1, sort_keys=True) + "\n")
    return p


# ------------------------------------------------------------------ engine
class UnixHTTPConnection(http.client.HTTPConnection):
    """HTTP over a Unix socket. `transport` keeps the connected socket for the
    whole request: for a close-framed response (Connection: close, or EOF
    framing) http.client's getresponse() calls self.close(), setting
    self.sock=None and handing the body to the HTTPResponse. CPython defers
    the descriptor's real close while the response's makefile reference is
    open, so settimeout()/shutdown() on the retained transport still govern
    the body read."""

    def __init__(self, path, timeout):
        super().__init__("localhost", timeout=timeout)
        self.unix_path = path
        self.transport = None

    def connect(self):
        s = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.transport = s  # retained before connect so the deadline timer can always reach it
        s.settimeout(self.timeout)
        s.connect(self.unix_path)
        self.sock = s


class Engine:
    """Every request has an absolute end time (its budget, capped by the
    caller's deadline), an idle timeout, and a body-size cap."""

    def __init__(self, sock, idle=30.0, budget=60.0):
        self.sock, self.idle, self.budget, self.log = sock, idle, budget, []

    def call(self, method, path, body=None, ctype="application/json", ok=(200, 201, 204), budget=None,
             cap=BODY_CAP["json"], until=None):
        end = time.monotonic() + (self.budget if budget is None else budget)
        if until is not None:
            end = min(end, until)

        def left():
            r = end - time.monotonic()
            if r <= 0:
                raise EngineIOError(f"{method} {path}: absolute request deadline exceeded")
            return min(self.idle, r)

        entry = {"method": method, "path": path}
        self.log.append(entry)
        conn = UnixHTTPConnection(self.sock, left())
        fired = threading.Event()
        r = None

        def expire():  # absolute bound regardless of how slowly bytes trickle in
            fired.set()
            t = conn.transport
            if t is not None:
                try:
                    t.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass

        capped = {"by_deadline": False}

        def arm():  # idle timeout for the next blocking operation, never past the absolute end
            t = left()
            capped["by_deadline"] = t < self.idle  # a timeout now IS the absolute deadline
            conn.transport.settimeout(t)

        timer = threading.Timer(max(0.0, end - time.monotonic()), expire)
        timer.daemon = True
        timer.start()
        try:
            data = json.dumps(body).encode() if isinstance(body, (dict, list)) else body
            headers = {"Content-Type": ctype} if data is not None else {}
            conn.request(method, API + path, body=data, headers=headers)
            arm()
            r = conn.getresponse()  # may close conn (conn.sock=None) for close-framed responses
            chunks, total = [], 0
            while True:
                arm()
                c = r.read1(65536) if method != "HEAD" else b""
                if not c:
                    break
                total += len(c)
                if total > cap:
                    raise EngineIOError(f"{method} {path}: body exceeds {cap} bytes")
                chunks.append(c)
            if fired.is_set():
                raise EngineIOError(f"{method} {path}: absolute request deadline exceeded")
            if method != "HEAD" and r.length not in (None, 0):
                raise EngineIOError(f"{method} {path}: truncated body ({r.length} bytes missing)")
            payload = b"".join(chunks)
            entry.update(status=r.status, bytes=len(payload), sha256=sha256(payload))
            if ok is not None and r.status not in ok:
                raise EngineStatusError(r.status, f"{method} {path}: HTTP {r.status} {payload[:300]!r}")
            return r.status, dict(r.getheaders()), payload
        except (socket.timeout, http.client.HTTPException, ConnectionError, OSError, ValueError) as exc:
            entry["error"] = type(exc).__name__
            if fired.is_set() or (isinstance(exc, socket.timeout) and capped["by_deadline"]):
                raise EngineIOError(f"{method} {path}: absolute request deadline exceeded") from exc
            raise EngineIOError(f"{method} {path}: {type(exc).__name__}: {exc}") from exc
        finally:
            timer.cancel()
            if r is not None:
                r.close()  # releases the body's reference to the transport
            conn.close()
            if conn.transport is not None:
                conn.transport.close()


def census(engine, name, until):
    _, _, body = engine.call("GET", "/containers/json?all=1", until=until)
    rows = json.loads(body)
    compilers = [c for c in rows if (c.get("Labels") or {}).get(ROLE_LABEL) == "compiler"]
    named = [c for c in rows if "/" + name in (c.get("Names") or [])]
    return compilers, named


def recover_owned(engine, name, run_id, role, until):
    """After an ambiguous create: exact name AND both labels, or nothing.
    Returns (owned_id_or_None, foreign_ids). Foreign objects are never touched."""
    _, named = census(engine, name, until)
    owned, foreign = [], []
    for c in named:
        labels = c.get("Labels") or {}
        if labels.get(ROLE_LABEL) == role and labels.get(RUN_LABEL) == run_id:
            owned.append(c["Id"])
        else:
            foreign.append(c.get("Id"))
    if len(owned) > 1:
        raise RecipeError(f"ambiguous ownership: {owned}")
    return (owned[0] if owned else None), foreign


SIGNALS = (signal.SIGTERM, signal.SIGINT)


class Shield:
    """Bounded section during which SIGTERM/SIGINT are recorded, not raised.

    Python runs signal handlers in the main thread even when another thread
    receives the signal, so a per-thread mask cannot defer them; swapping the
    handler can. On exit the previous handlers return and a recorded signal
    is raised as Cancelled -- after the section has stored what it learned
    (e.g. an owned container ID), so the caller's cleanup can act on it."""

    def __init__(self):
        self.pending = []

    def __enter__(self):
        self.prev = {s: signal.signal(s, lambda n, f: self.pending.append(n)) for s in SIGNALS}
        return self

    def __exit__(self, et, ev, tb):
        for s, h in self.prev.items():
            signal.signal(s, h)
        if self.pending and (et is None or issubclass(et, Exception)):
            raise Cancelled(signal.Signals(self.pending[0]).name) from ev
        return False


def create_owned(engine, name, body, run_id, role, until, recover_budget, res, holder):
    """Create once, inside a bounded signal shield. holder["cid"] is set as
    soon as an owned ID is known, so cleanup can delete it whatever happens
    next. A definite 4xx means nothing of ours exists. A transport failure,
    5xx, or a Cancelled raised from inside the call is ambiguous: recover
    exactly our object (exact name + role + run labels) for deletion only,
    then abort. Never retries. A deferred signal is raised as Cancelled
    after holder/res are recorded."""
    holder["cid"] = None
    cancelled = None
    with Shield():
        try:
            _, _, raw = engine.call("POST", f"/containers/create?name={name}", body, until=until)
            holder["cid"] = json.loads(raw)["Id"]
            return holder["cid"], False
        except EngineStatusError as exc:
            if exc.status < 500:
                raise
            res["create_ambiguous"] = str(exc)
        except (EngineIOError, ValueError, KeyError) as exc:
            res["create_ambiguous"] = str(exc)
        except Cancelled as exc:
            res["create_ambiguous"] = f"cancelled during create: {exc}"
            cancelled = exc
        try:
            cid, foreign = recover_owned(engine, name, run_id, role, time.monotonic() + recover_budget)
        except RecipeError as exc:
            res["recovery_error"] = str(exc)
            cid, foreign = None, []
        holder["cid"] = cid
        res["recovered_owned_id"], res["foreign_ids"] = cid, foreign
    if cancelled is not None:
        raise cancelled
    return cid, True


def _raise_cancel(signum, frame):
    raise Cancelled(signal.Signals(signum).name)


def execute(plan_path, sock, admit, poll=5.0, now=time.monotonic, sleep=time.sleep, idle=30.0, req_budget=60.0):
    plan_path = Path(plan_path).resolve()
    rundir = plan_path.parent
    raw = plan_path.read_bytes()
    if admit != sha256(raw):
        raise RecipeError("admission token must equal the PLAN.json sha256 (Root admits one plan)")
    p = json.loads(raw)
    upload = (rundir / "upload.tar").read_bytes()
    if sha256(upload) != p["inputs"]["upload_tar_sha256"]:
        raise RecipeError("upload.tar changed since planning")
    if (rundir / "EXECUTION.json").exists():
        raise RecipeError("plan already consumed")
    lim = p["limits"]
    t0 = now()
    build_until = time.monotonic() + lim["deadline_s"]  # absolute, from admission
    e = Engine(sock, idle=idle, budget=req_budget)
    res = {"run_id": p["run_id"], "container_name": p["container_name"], "state": "admitted",
           "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (rundir / "EXECUTION.json").write_text(json.dumps(res) + "\n")
    old = {s: signal.signal(s, _raise_cancel) for s in SIGNALS}
    cid, failure, cancelled = None, None, None
    holder = {"cid": None}
    try:
        try:
            compilers, named = census(e, p["container_name"], build_until)
            if compilers or named:
                raise RecipeError("single-owner admission: existing compiler/name "
                                  f"{[c.get('Id') for c in compilers + named]}")
            cid, ambiguous = create_owned(e, p["container_name"], p["create"], p["run_id"], "compiler",
                                          build_until, lim["cleanup_budget_s"], res, holder)
            if ambiguous:
                raise RecipeError("create response ambiguous; run aborted (no retry)")
            res["container_id"] = cid
            _, _, body = e.call("GET", f"/containers/{cid}/json", until=build_until)
            info = json.loads(body)
            labels = info.get("Config", {}).get("Labels") or {}
            if labels.get(RUN_LABEL) != p["run_id"] or labels.get(ROLE_LABEL) != "compiler":
                raise RecipeError("created container does not carry this run's labels")
            res["echoed_host_config"] = {k: info.get("HostConfig", {}).get(k)
                                         for k in ("Memory", "MemorySwap", "NanoCpus", "PidsLimit")}
            e.call("PUT", f"/containers/{cid}/archive?path=/work/in", upload, ctype="application/x-tar",
                   budget=600, until=build_until)
            owner = wrapper_tar({"owner.env": (f"CONTAINER_ID='{cid}'\n".encode(), 0o644)})
            e.call("PUT", f"/containers/{cid}/archive?path=/work/in", owner, ctype="application/x-tar",
                   until=build_until)
            e.call("POST", f"/containers/{cid}/start", until=build_until)
            res["timed_out"] = False
            while True:
                if now() - t0 > lim["deadline_s"] or time.monotonic() > build_until:
                    res["timed_out"] = True
                    break
                _, _, body = e.call("GET", f"/containers/{cid}/json", until=build_until)
                st = json.loads(body).get("State", {})
                if not st.get("Running") and st.get("Status") in ("exited", "dead"):
                    res["exit_code"] = st.get("ExitCode")
                    break
                sleep(poll)
        except RecipeError as exc:
            failure = exc
        except Cancelled as exc:
            cancelled = exc
            res["cancelled"] = str(exc)
        cid = cid or holder["cid"]  # an ID learned before an exception still gets cleaned up
        if cid:
            res.setdefault("container_id", cid)
        # Post phase (own budget): stop the container if needed, collect evidence.
        if cid:
            for s in old:
                signal.signal(s, signal.SIG_IGN)
            post_until = time.monotonic() + lim["post_budget_s"]
            try:
                if res.get("timed_out") or failure is not None or cancelled is not None:
                    e.call("POST", f"/containers/{cid}/kill", ok=(204, 404, 409), until=post_until)
                if "exit_code" in res or res.get("timed_out"):
                    _, _, logs = e.call("GET", f"/containers/{cid}/logs?stdout=1&stderr=1", ok=(200,),
                                        cap=BODY_CAP["logs"], until=post_until)
                    (rundir / "container.log").write_bytes(logs)
                    st, _, tarb = e.call("GET", f"/containers/{cid}/archive?path=/work/out", ok=(200, 404),
                                         cap=BODY_CAP["export"], budget=600, until=post_until)
                    if st == 200:
                        (rundir / "export.tar").write_bytes(tarb)
                        res["export_sha256"] = sha256(tarb)
            except RecipeError as exc:
                res["post_error"] = str(exc)
                failure = failure or exc
    finally:
        # Owned cleanup always runs; further signals are ignored until it ends.
        for s in old:
            signal.signal(s, signal.SIG_IGN)
        cid = cid or holder["cid"]
        try:
            if cid:
                cleanup_until = time.monotonic() + lim["cleanup_budget_s"]
                try:
                    e.call("DELETE", f"/containers/{cid}?force=1", ok=(204, 404), until=cleanup_until)
                    st, _, _ = e.call("GET", f"/containers/{cid}/json", ok=(404,), until=cleanup_until)
                    res["deleted"] = st == 404
                except RecipeError as exc:
                    res["deleted"] = False
                    res["cleanup_error"] = str(exc)
            if res.get("create_ambiguous") and not cid:
                res["orphan_unresolved"] = (f"no owned object found at recovery; a late-completing create could "
                                            f"leave {p['container_name']} (run label {p['run_id']}) -- UNRESOLVED")
            res["elapsed_s"] = round(now() - t0, 1)
            res["requests"] = e.log
            res["state"] = "finished"
            res["failure"] = None if failure is None else str(failure)
            (rundir / "EXECUTION.json").write_text(json.dumps(res, indent=1) + "\n")
        finally:
            for s, h in old.items():
                signal.signal(s, h)
    if cid and not res.get("deleted"):
        raise RecipeError(f"owned container {cid} cleanup UNRESOLVED: {res.get('cleanup_error')}")
    if cancelled is not None:
        raise cancelled
    if res.get("orphan_unresolved"):
        raise RecipeError("create response ambiguous: " + res["orphan_unresolved"])
    if failure is not None:
        raise failure
    if res.get("timed_out"):
        raise RecipeError("deadline exceeded; container killed and deleted")
    if res.get("exit_code") != 0:
        raise RecipeError(f"guest failed exit={res.get('exit_code')}; see container.log")
    return res


# ------------------------------------------------------------------ export
def safe_extract(tarb, dest):
    """Regular files/dirs only, no escape. Returns member metadata (owner/mode)."""
    dest = Path(dest).resolve()
    if dest.exists():
        raise RecipeError(f"{dest} exists")
    dest.mkdir(parents=True)
    meta = {}
    with tarfile.open(fileobj=io.BytesIO(tarb)) as tar:
        for m in tar.getmembers():
            target = (dest / m.name).resolve()
            if not str(target).startswith(str(dest) + os.sep) or not (m.isfile() or m.isdir()):
                raise RecipeError(f"unsafe export member {m.name}")
            meta[m.name.rstrip("/")] = {"uid": m.uid, "gid": m.gid, "mode": oct(m.mode & 0o7777)}
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile(m).read())
                os.chmod(target, m.mode & 0o777)
    return dest, meta


def elf_machine(data):
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        return None
    return int.from_bytes(data[18:20], "little")


def check_sums(out):
    sums = {}
    for line in (out / "SHA256SUMS").read_text().splitlines():
        h, rel = line.split(None, 1)
        sums[rel.removeprefix("./")] = h
    for rel, h in sums.items():
        if sha256((out / rel).read_bytes()) != h:
            raise RecipeError(f"export hash mismatch {rel}")
    listed = {str(f.relative_to(out)) for f in out.rglob("*") if f.is_file()} - {"SHA256SUMS", "RESULT"}
    if listed != set(sums):
        raise RecipeError(f"export file set differs from SHA256SUMS: {sorted(listed ^ set(sums))}")


def check_cgroup_evidence(out, plan, container_id):
    got = dict(line.split("=", 1) for line in (out / "cgroup.txt").read_text().splitlines() if "=" in line)
    for leaf, want in plan["expected_cgroup"].items():
        if got.get(leaf) != want:
            raise RecipeError(f"guest cgroup {leaf}={got.get(leaf)!r} != plan {want!r}")
    if not container_id or got.get("id") != container_id:
        raise RecipeError(f"guest cgroup id {got.get('id')!r} is not container {container_id!r}")


def _text_lines(path, what):
    try:
        lines = path.read_text().splitlines()
    except (OSError, UnicodeDecodeError) as exc:
        raise RecipeError(f"export lacks readable {what}") from exc
    if len(lines) != len(set(lines)):
        raise RecipeError(f"export {what} has duplicate lines")
    return lines


def _upload_members(upload_path, p):
    """The plan's own upload bytes (bound by the plan's upload SHA-256), for
    joining build-mode local inputs that are not re-exported."""
    if upload_path is None:
        raise RecipeError("build-mode local inputs need the plan's upload.tar to join identities")
    raw = Path(upload_path).read_bytes()
    if sha256(raw) != p["inputs"]["upload_tar_sha256"]:
        raise RecipeError("upload.tar differs from the plan")
    with tarfile.open(fileobj=io.BytesIO(raw)) as t:
        return {m.name: t.extractfile(m).read() for m in t.getmembers()
                if m.isfile() and re.fullmatch(r"local-\d+\.apk", m.name)}


def check_dependency_evidence(out, p, abi, upload_path=None):
    """Join every dependency inventory (T10.010.004). Contradictory exports fail
    even when SHA256SUMS is coherent: base-current vs base-candidate (or the
    plan's base), names/versions before and after, the solver delta, the lock
    candidate (or the plan's lock), installed identities, the authenticated
    closure (identity + full SHA-256 per file) and, in resolve mode, the
    retained signed bytes and their build-usable MANIFEST.json."""
    nv = lambda line: line.replace("=", "-", 1)  # noqa: E731
    base_cur = (out / "apk.base.current").read_bytes()
    sim = (out / "apk-simulate.delta").read_bytes()
    if p["mode"] == "resolve":
        cand, bcand = (out / "apk.lock.candidate").read_bytes(), (out / "apk.base.candidate").read_bytes()
        if bcand != base_cur:
            raise RecipeError("base candidate differs from the frozen base-current inventory")
        if cand != sim:
            raise RecipeError("lock candidate differs from the solver delta")
        delta_b, base_b = cand, bcand
    else:
        delta_b = "".join(line + "\n" for line in p["inputs"]["apk_lock"]).encode()
        base_b = "".join(line + "\n" for line in p["inputs"]["apk_base"]).encode()
        if base_cur != base_b:
            raise RecipeError("image packages differ from the plan's frozen base")
        if sim != delta_b:
            raise RecipeError("solver delta differs from the plan's delta lock")
    delta, base = parse_deps(delta_b, base_b, abi)
    bname = sorted(x.split("=", 1)[0] for x in base)
    dname = sorted(x.split("=", 1)[0] for x in delta)
    before = _text_lines(out / "apk-before.txt", "apk-before.txt")
    after = _text_lines(out / "apk-after.txt", "apk-after.txt")
    if sorted(before) != sorted(nv(x) for x in base):
        raise RecipeError("apk-before versions differ from the frozen base")
    if _text_lines(out / "apk-names-before.txt", "apk-names-before.txt") != bname:
        raise RecipeError("apk-names-before differs from the frozen base names")
    if sorted(after) != sorted(set(before) | {nv(x) for x in delta}) or len(after) != len(before) + len(delta):
        raise RecipeError("installed closure differs from base + exact delta (upgrade, removal or extra)")
    if _text_lines(out / "apk-names-after.txt", "apk-names-after.txt") != sorted(bname + dname):
        raise RecipeError("apk-names-after differs from base + delta names")
    keys = (out / "apk-keys-before.txt").read_bytes()
    if not keys or keys != (out / "apk-keys-after.txt").read_bytes():
        raise RecipeError("stock trusted-key evidence missing or changed")
    ident = {}
    for line in _text_lines(out / "apk-installed-identity.txt", "installed identities"):
        k, _, c = line.partition(" ")
        if not re.fullmatch(r"Q1[A-Za-z0-9+/]{27}=", c) or k in ident:
            raise RecipeError(f"installed identity line {line!r}")
        ident[k] = c
    if sorted(ident) != delta:
        raise RecipeError("installed database identities do not cover the delta exactly")
    closure = {}
    for line in _text_lines(out / "apk-closure.txt", "apk-closure.txt"):
        parts = line.split(" ")
        if len(parts) != 5 or not re.fullmatch(r"[0-9a-f]{64}", parts[1]) or not parts[2].isdigit():
            raise RecipeError(f"closure line {line!r}")
        k, h, b, f, src = parts
        if not re.fullmatch(rf"{src}-\d+\.apk", f) or src not in ("local", "repo") or k in closure:
            raise RecipeError(f"closure line {line!r}")
        closure[k] = {"sha256": h, "bytes": int(b), "file": f, "source": src}
    if sorted(closure) != delta:
        raise RecipeError("authenticated closure differs from the exact delta")
    if len({c["file"] for c in closure.values()}) != len(closure):
        raise RecipeError("closure reuses a file name")
    verified = {}
    for line in _text_lines(out / "apk-verify.txt", "apk-verify.txt"):
        parts = line.split(" ")
        if len(parts) != 6 or parts[5] != "OK" or parts[4] != p["abi_expect"]["arch"] or parts[0] in verified:
            raise RecipeError(f"verification line {line!r}")
        verified[parts[0]] = (parts[1], f"{parts[2]}={parts[3]}")
    for k, c in closure.items():
        if verified.get(c["file"][:-len(".apk")]) != (c["sha256"], k):
            raise RecipeError(f"{k}: no stock-key verification bound to its identity and full hash")
    planned = {f"{e['name']}={e['version']}": e for e in (p["inputs"].get("apk_local") or [])}
    got_local = {k: c for k, c in closure.items() if c["source"] == "local"}
    if sorted(planned) != sorted(got_local):
        raise RecipeError("closure local inputs differ from the plan's local inputs")
    for k, e in planned.items():
        c = got_local[k]
        if (c["sha256"], c["bytes"], c["file"]) != (e["sha256"], e["bytes"], e["member"]):
            raise RecipeError(f"local input {k} differs from the plan")
    # Independent raw-byte identity join (T10.010.004 repair 2): every closure
    # entry's bytes -- retained in the export, or the plan's own uploaded local
    # input -- are parsed for their control identity, which must equal the
    # claimed name=version, the expected arch, the full file hash/size, the
    # plan's identity and the installed database C:.
    cdir = out / "apk-closure"
    files = {f.name for f in cdir.iterdir()} if cdir.is_dir() else set()
    if p["mode"] == "resolve":
        want_files = {c["file"] for c in closure.values()} | {"MANIFEST.json"}
    else:
        want_files = {c["file"] for c in closure.values() if c["source"] == "repo"}
    if files != want_files:
        raise RecipeError("retained closure files differ from the closure record")
    uploaded = _upload_members(upload_path, p) if (p["mode"] == "build" and planned) else {}
    derived = {}
    for k, c in closure.items():
        if p["mode"] == "build" and c["source"] == "local":
            data = uploaded.get(c["file"])
            if data is None:
                raise RecipeError(f"{k}: planned local bytes missing from upload.tar")
        else:
            data = (cdir / c["file"]).read_bytes()
        if (sha256(data), len(data)) != (c["sha256"], c["bytes"]):
            raise RecipeError(f"{k}: raw bytes differ from the closure record")
        idn = apk_identity(data)
        if f"{idn['name']}={idn['version']}" != k:
            raise RecipeError(f"{k}: the file's own control identity is {idn['name']}={idn['version']}")
        if idn["arch"] != p["abi_expect"]["arch"]:
            raise RecipeError(f"{k}: control arch {idn['arch']!r}")
        if ident[k] != idn["q1"]:
            raise RecipeError(f"{k}: installed C: {ident[k]} != control identity {idn['q1']} of its bytes")
        if k in planned and planned[k].get("q1") not in (None, idn["q1"]):
            raise RecipeError(f"{k}: control identity differs from the plan's")
        derived[k] = {x: idn[x] for x in ("q1", "control_sha1", "arch", "datahash")}
    retained = None
    if p["mode"] == "resolve":
        _, ments = load_local_manifest(cdir / "MANIFEST.json", p["abi_expect"]["arch"])
        mview = sorted((f"{e['name']}={e['version']}", e["sha256"], e["bytes"], e["file"]) for e in ments)
        if mview != sorted((k, c["sha256"], c["bytes"], c["file"]) for k, c in closure.items()):
            raise RecipeError("retained MANIFEST.json differs from the closure record")
        retained = {"manifest": str(cdir / "MANIFEST.json"),
                    "manifest_sha256": sha256((cdir / "MANIFEST.json").read_bytes())}
    return {"delta": delta, "base": base, "closure": closure, "installed_identity": ident,
            "derived_identity": derived, "trusted_keys_sha256": sha256(keys), "retained": retained}


def validate_export(plan_path, export_tar, dest):
    plan_path = Path(plan_path)
    p = json.loads(plan_path.read_text())
    ex = plan_path.parent / "EXECUTION.json"
    cid = json.loads(ex.read_text()).get("container_id") if ex.exists() else None
    root, meta = safe_extract(Path(export_tar).read_bytes(), dest)
    out = root / "out"
    if (out / "RESULT").read_text().strip() != "PASS":
        raise RecipeError(f"guest RESULT: {(out / 'RESULT').read_text().strip()}")
    check_sums(out)
    check_cgroup_evidence(out, p, cid)
    apk_before = (out / "apk-before.txt").read_text().split()
    for name, want in (("musl", p["abi_expect"]["musl"]), ("libstdc++", p["abi_expect"]["libstdc++"])):
        if f"{name}-{want}" not in apk_before:
            raise RecipeError(f"base {name} != {want}")
    abi = (p["abi_expect"]["musl"], p["abi_expect"]["libstdc++"])
    deps = check_dependency_evidence(out, p, abi, plan_path.parent / "upload.tar")
    if p["mode"] == "resolve":
        cand, bcand = (out / "apk.lock.candidate").read_bytes(), (out / "apk.base.candidate").read_bytes()
        lines, blines = deps["delta"], deps["base"]
        result = {"schema": "t10.010.003/resolve/v2", "run_id": p["run_id"], "lock_candidate": lines,
                  "lock_candidate_sha256": sha256(cand), "base_candidate": blines,
                  "base_candidate_sha256": sha256(bcand), "dependency_recipe": DEPS_RECIPE,
                  "closure": deps["closure"], "installed_identity": deps["installed_identity"],
                  "derived_identity": deps["derived_identity"],
                  "trusted_keys_sha256": deps["trusted_keys_sha256"], "retained_closure": deps["retained"],
                  "note": "candidate only: Root must review and qualify it before a build plan uses it"}
        (Path(dest) / "RESOLVE.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
        return result
    apk = (out / "apk-after.txt").read_text().split()
    for name, want in (("musl", p["abi_expect"]["musl"]), ("libstdc++", p["abi_expect"]["libstdc++"])):
        if f"{name}-{want}" not in apk:
            raise RecipeError(f"{name} != {want}")
    if (out / "apk.base.current").read_text().splitlines() != p["inputs"]["apk_base"]:  # also in deps
        raise RecipeError("image packages differ from the plan's frozen base")
    locked = sorted(line.replace("=", "-", 1) for line in p["inputs"]["apk_lock"])
    added = sorted(set(apk) - set(apk_before))
    if added != locked:
        raise RecipeError("installed closure differs from the plan's delta lock")
    if sorted(set(apk_before) - set(apk)):
        raise RecipeError("install changed base packages")
    owner = p["artifact_owner"]
    art = {}
    for v in ("unpatched", "patched"):
        b = out / v / "map-server"
        m = meta.get(f"out/{v}/map-server")
        if m != owner:
            raise RecipeError(f"{v}: tar owner/mode {m} != declared {owner}")
        data = b.read_bytes()
        if elf_machine(data) != EM_AARCH64:
            raise RecipeError(f"{v}: not ELF64 little-endian AArch64")
        if (b.stat().st_mode & 0o777) != 0o755:
            raise RecipeError(f"{v}: mode {oct(b.stat().st_mode & 0o777)} != 0755")
        if b"npc/re/scripts_main.conf" not in data or b"npc/pre-re/scripts_main.conf" in data:
            raise RecipeError(f"{v}: era marker")
        if (b"ros_ch1_coin_capacity" in data) != (v == "patched"):
            raise RecipeError(f"{v}: builtin presence wrong")
        interp = (out / v / "interp.txt").read_text()
        if "/lib/ld-musl-aarch64.so.1" not in interp:
            raise RecipeError(f"{v}: interpreter {interp.strip()}")
        art[v] = {"sha256": sha256(data), "bytes": len(data), "owner": m,
                  "build_id": (out / v / "BUILD_ID").read_text().strip(),
                  "needed": sorted(re.findall(r"\[(.+?)\]", (out / v / "dynamic.txt").read_text())),
                  "debug_sha256": sha256((out / v / "map-server.debug").read_bytes())}
    if art["unpatched"]["needed"] != art["patched"]["needed"]:
        raise RecipeError("variants link different libraries")
    if art["unpatched"]["sha256"] == art["patched"]["sha256"]:
        raise RecipeError("variants are identical")
    result = {"schema": "t10.010.003/artifacts/v1", "run_id": p["run_id"], "artifacts": art,
              "toolchain": (out / "toolchain.txt").read_text().splitlines(),
              "environment": (out / "environment.txt").read_text().splitlines(),
              "cgroup": (out / "cgroup.txt").read_text().splitlines(),
              "prepared_tree_sha256": p["prepared"]["tree_sha256"],
              "dependency_closure": deps["closure"], "trusted_keys_sha256": deps["trusted_keys_sha256"]}
    (Path(dest) / "ARTIFACTS.json").write_text(json.dumps(result, indent=1, sort_keys=True) + "\n")
    return result


# ------------------------------------------------------------------ import
IMPORT_DEST = "/rathena/map-server-t10-010-{variant}"


def image_context(artifacts_dir, variant, base_image, dest):
    """No pre-FROM ARG, no stage ARG, no RUN, one literal single-file COPY."""
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", base_image) or variant not in ("patched", "unpatched"):
        raise RecipeError("bad base image or variant")
    dest = Path(dest)
    if dest.exists():
        raise RecipeError(f"{dest} exists")
    dest.mkdir(parents=True)
    data = (Path(artifacts_dir) / "out" / variant / "map-server").read_bytes()
    (dest / "map-server").write_bytes(data)
    os.chmod(dest / "map-server", 0o755)
    target = IMPORT_DEST.format(variant=variant)
    (dest / "Dockerfile").write_text(f"FROM {base_image}\nCOPY map-server {target}\n")
    return {"target": target, "sha256": sha256(data), "import_owner": IMPORT_OWNER,
            "dockerfile_sha256": sha256((dest / "Dockerfile").read_bytes())}


def import_check(sock, image, variant, expect_sha256, budget=300, owner=IMPORT_OWNER, cleanup_budget=120,
                 record=None):
    """Create (not start) a container, HEAD+GET the imported file and compare
    bytes, tar uid/gid/mode and stat mode with the declaration; delete it.
    Same rules as execute: one shielded create, exact name + labels recovery,
    no retry; SIGTERM/SIGINT unwind through deletion of any owned ID.

    Outcome (record, if given, is written before anything propagates):
      cleanup confirmed          -> result, or the original exception/Cancelled
      cleanup refused/unconfirmed-> CleanupUnresolved, or CancelledUnresolved
                                    if cancelled; __cause__ = original failure"""
    e = Engine(sock)
    until = time.monotonic() + budget
    run_id = uuid.uuid4().hex[:12]
    name = f"t10-010-003-import-{run_id}"
    target = IMPORT_DEST.format(variant=variant)
    res = {"ok": False, "name": name, "run_id": run_id}
    holder = {"cid": None}
    primary = None
    old = {s: signal.signal(s, _raise_cancel) for s in SIGNALS}
    try:
        try:
            cid, ambiguous = create_owned(e, name, {"Image": image, "Entrypoint": ["/bin/true"],
                                                    "Labels": {ROLE_LABEL: "import-check", RUN_LABEL: run_id}},
                                          run_id, "import-check", until, 60, res, holder)
            if ambiguous:
                raise RecipeError("create response ambiguous; aborted (no retry)" + (
                    "" if cid else f"; possible late orphan {name} (run label {run_id}) UNRESOLVED"))
            _, hdr, _ = e.call("HEAD", f"/containers/{cid}/archive?path={target}", ok=(200,), until=until)
            stat = json.loads(base64.b64decode(hdr.get("X-Docker-Container-Path-Stat", "")))
            _, _, tarb = e.call("GET", f"/containers/{cid}/archive?path={target}", ok=(200,),
                                cap=BODY_CAP["import"], until=until)
            with tarfile.open(fileobj=io.BytesIO(tarb)) as tar:
                members = tar.getmembers()
                if len(members) != 1 or not members[0].isfile():
                    raise RecipeError("import archive must hold exactly one regular file")
                m = members[0]
                data = tar.extractfile(m).read()
            got = {"uid": m.uid, "gid": m.gid, "mode": oct(m.mode & 0o7777)}
            res.update(sha256=sha256(data), tar=got, stat_mode=oct(stat.get("mode", 0) & 0o7777),
                       ok=sha256(data) == expect_sha256 and got == owner
                       and oct(stat.get("mode", 0) & 0o7777) == owner["mode"])
        except BaseException as exc:  # held, not swallowed: re-raised (or chained) below
            primary = exc
    finally:
        for s in old:
            signal.signal(s, signal.SIG_IGN)
        try:
            cid = holder["cid"]
            if cid:
                cu = time.monotonic() + cleanup_budget
                try:
                    e.call("DELETE", f"/containers/{cid}?force=1", ok=(204, 404), until=cu)
                    e.call("GET", f"/containers/{cid}/json", ok=(404,), until=cu)  # confirm absence
                    res["deleted"] = True
                except RecipeError as exc:
                    res["deleted"] = False
                    res["cleanup_error"] = str(exc)
            res["primary"] = None if primary is None else f"{type(primary).__name__}: {primary}"
            res["requests"] = e.log
            if holder["cid"] and not res.get("deleted"):
                res["unresolved"] = {
                    "message": (f"import-check container {holder['cid']} (name {name}, run label {run_id}) "
                                f"cleanup UNRESOLVED: {res.get('cleanup_error')}"
                                + (f"; original failure: {res['primary']}" if primary is not None else "")),
                    "container_id": holder["cid"], "name": name, "run_id": run_id,
                    "cleanup_error": res.get("cleanup_error"), "primary": res["primary"]}
            if record is not None:
                Path(record).write_text(json.dumps(res, indent=1, default=str) + "\n")
        finally:
            for s, h in old.items():
                signal.signal(s, h)
    if "unresolved" in res:
        if isinstance(primary, Cancelled):
            raise CancelledUnresolved(res["unresolved"]) from primary
        raise CleanupUnresolved(res["unresolved"]) from primary
    if primary is not None:
        raise primary
    return res


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("plan")
    a.add_argument("--prepared", required=True, type=Path)
    a.add_argument("--rundir", required=True, type=Path)
    a.add_argument("--mode", choices=("resolve", "build"), required=True)
    a.add_argument("--apk-lock", type=Path)
    a.add_argument("--apk-base", type=Path)
    a.add_argument("--apk-local", type=Path,
                   help="optional local APK manifest (t10.010.004/apk-local/v1); files beside it, bound by bytes/SHA-256")
    a.add_argument("--base-image", required=True)
    a.add_argument("--expect-musl", required=True)
    a.add_argument("--expect-libstdcxx", required=True)
    a.add_argument("--mem-available-bytes", required=True, type=int)
    a.add_argument("--host-cpus", required=True, type=int)
    for name, default in (("memory-mib", 1536), ("cpus", 2), ("jobs", 1), ("pids", 1024), ("reserve-mib", 768),
                          ("step-timeout", 3600), ("deadline", 4 * 3600), ("post-budget", 300),
                          ("cleanup-budget", 180)):
        a.add_argument("--" + name, type=int, default=default)
    x = sub.add_parser("execute")
    x.add_argument("--plan", required=True, type=Path)
    x.add_argument("--engine-socket", required=True)
    x.add_argument("--admit", required=True)
    v = sub.add_parser("validate-export")
    v.add_argument("--plan", required=True, type=Path)
    v.add_argument("--export", required=True, type=Path)
    v.add_argument("--dest", required=True, type=Path)
    i = sub.add_parser("image-context")
    i.add_argument("--artifacts", required=True, type=Path)
    i.add_argument("--variant", required=True)
    i.add_argument("--base-image", required=True)
    i.add_argument("--dest", required=True, type=Path)
    c = sub.add_parser("import-check")
    c.add_argument("--engine-socket", required=True)
    c.add_argument("--image", required=True)
    c.add_argument("--variant", required=True)
    c.add_argument("--expect-sha256", required=True)
    c.add_argument("--record", required=True, type=Path,
                   help="JSON outcome record, written before any failure/cancellation propagates")
    o = ap.parse_args(argv)
    try:
        if o.cmd == "plan":
            r = plan(o.prepared, o.rundir, o.base_image, o.expect_musl, o.expect_libstdcxx, o.mem_available_bytes,
                     o.host_cpus, o.mode, o.apk_lock, o.apk_base, o.memory_mib, o.cpus, o.jobs, o.pids, o.step_timeout,
                     o.deadline, o.reserve_mib, o.post_budget, o.cleanup_budget, apk_local=o.apk_local)
            r = {"run_id": r["run_id"], "mode": r["mode"], "inputs": r["inputs"], "limits": r["limits"],
                 "expected_cgroup": r["expected_cgroup"], "admit": sha256((o.rundir / "PLAN.json").read_bytes())}
        elif o.cmd == "execute":
            r = execute(o.plan, o.engine_socket, o.admit)
            r.pop("requests", None)
        elif o.cmd == "validate-export":
            r = validate_export(o.plan, o.export, o.dest)
        elif o.cmd == "image-context":
            r = image_context(o.artifacts, o.variant, o.base_image, o.dest)
        else:
            r = import_check(o.engine_socket, o.image, o.variant, o.expect_sha256, record=o.record)
            r.pop("requests", None)
            if not r["ok"]:
                print("FAIL", json.dumps(r, sort_keys=True))
                return 1
    except Cancelled as exc:
        print("FAIL cancelled", exc)
        if getattr(exc, "detail", None):
            print("UNRESOLVED", json.dumps(exc.detail, sort_keys=True))
        return 143
    except (RecipeError, ps.PrepError, OSError, KeyError, ValueError) as exc:
        print("FAIL", exc)
        return 1
    print("OK", json.dumps(r, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
