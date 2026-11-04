"""Focused tests for build_recipe.py and build/guest_lib.sh (T10.010.003).

  python3 -I -B tools/renewal/native_capacity/test_build_recipe.py

A FAKE Unix-socket Engine implements only the slim routes the recipe calls,
plus fault modes (lost/5xx/409 create, slow and truncated bodies, refused
delete, wrong owners). guest_lib.sh functions run under the host's /bin/sh
against fixture files. Nothing here uses a real Engine, VM, compiler or
image: these prove request order, ownership, bounds, cancellation/cleanup
and validation logic only -- not real guest behavior, limit enforcement or
a compiled binary.
"""

import base64
import gzip
import hashlib
import http.server
import io
import json
import os
from pathlib import Path
import shutil
import signal
import socketserver
import subprocess
import sys
import tarfile
import tempfile
import threading
import time
import unittest
from unittest import mock
import uuid
import zlib

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_recipe as br  # noqa: E402
import prepare_source as ps  # noqa: E402
from test_prepare_source import Fixture, PATCH_OK  # noqa: E402

BASE = "sha256:" + "ab" * 32
# Root's reproduced case: the stock runtime image already has bash, so the
# delta lock legitimately lacks it and the frozen base covers it.
BASE_LOCK = "bash=5.3-r0\nlibstdc++=15.2.0-r2\nmusl=1.2.5-r23\n"
LOCK = "".join(f"{n}={v}\n" for n, v in sorted({
    "binutils": "2.45-r0", "cmake": "4.1.2-r0", "g++": "15.2.0-r2", "gcc": "15.2.0-r2",
    "git": "2.52.0-r0", "libunwind-dev": "1.8.1-r0", "linux-headers": "6.16-r0", "make": "4.4.1-r3",
    "mariadb-dev": "11.8.3-r0", "patch": "2.8-r0", "zlib-dev": "1.3.1-r2"}.items()))
APK_BEFORE = sorted(x.replace("=", "-", 1) for x in BASE_LOCK.split())


def fake_elf(marker):
    head = bytearray(64)
    head[:4] = b"\x7fELF"
    head[4], head[5] = 2, 1
    head[18:20] = br.EM_AARCH64.to_bytes(2, "little")
    return bytes(head) + b"npc/re/scripts_main.conf\0" + marker


KEYS_EVIDENCE = b"0123  ./alpine-devel@lists.alpinelinux.org-stock.rsa.pub\n"


# Synthetic architecture-independent repository additions (T10.010.004 noarch).
NOARCH_REPO = {"synthetic-noarch-data=1.0-r0"}


def fake_apk_bytes(nv):
    """Synthetic stand-in (tar.gz with .PKGINFO, see pkg_bytes): NOT a signed APK."""
    return pkg_bytes(*nv.split("=", 1), arch="noarch" if nv in NOARCH_REPO else "aarch64")


def dep_evidence(plan, delta, local_data=None):
    """Coherent T10.010.004 dependency evidence for a synthetic export."""
    local_data = local_data or {}
    nv = lambda x: x.replace("=", "-", 1)  # noqa: E731
    base = BASE_LOCK.split()
    locals_ = {f"{e['name']}={e['version']}": e for e in plan["inputs"].get("apk_local") or []}
    files = {"apk-before.txt": "".join(x + "\n" for x in APK_BEFORE).encode(),
             "apk-names-before.txt": "".join(x.split("=")[0] + "\n" for x in base).encode(),
             "apk-after.txt": "".join(x + "\n" for x in sorted(APK_BEFORE + [nv(d) for d in delta])).encode(),
             "apk-names-after.txt": "".join(x + "\n" for x in sorted(
                 [b.split("=")[0] for b in base] + [d.split("=")[0] for d in delta])).encode(),
             "apk-simulate.delta": "".join(d + "\n" for d in delta).encode(),
             "apk-keys-before.txt": KEYS_EVIDENCE, "apk-keys-after.txt": KEYS_EVIDENCE,
             }
    closure, verify, manifest, idents, k = [], [], [], [], 0
    for d in delta:
        if d in locals_:
            e = locals_[d]
            data, f, h, b = local_data.get(d, b""), e["member"], e["sha256"], e["bytes"]
            src = "local"
        else:
            data, f, src = fake_apk_bytes(d), f"repo-{k}.apk", "repo"
            h, b = hashlib.sha256(data).hexdigest(), len(data)
            k += 1
        closure.append(f"{d} {h} {b} {f} {src}\n")
        try:
            idn = br.apk_identity(data)
            idents.append(f"{d} {idn['q1']}\n")
            arch = idn["arch"]  # the guest reports the signed control's ACTUAL arch
        except br.RecipeError:
            idents.append(f"{d} Q1{'A' * 27}=\n")  # unparseable bytes: only for negative fixtures
            arch = "aarch64"
        verify.append(f"{f[:-4]} {h} {d.replace('=', ' ', 1)} {arch} OK\n")
        name, ver = d.split("=", 1)
        manifest.append({"file": f, "name": name, "version": ver, "bytes": b, "sha256": h})
        if plan["mode"] == "resolve" or src == "repo":
            files[f"apk-closure/{f}"] = data
    files["apk-installed-identity.txt"] = "".join(idents).encode()
    files["apk-closure.txt"] = "".join(sorted(closure)).encode()
    files["apk-verify.txt"] = "".join(verify).encode()
    if plan["mode"] == "resolve":
        files["apk-closure/MANIFEST.json"] = json.dumps({"schema": br.LOCAL_SCHEMA, "packages": manifest}).encode()
    return files


def export_tar(plan, cid, tamper=None, owner=(0, 0), delta=None, local_data=None):
    cg = plan["expected_cgroup"]
    if delta is None:
        delta = plan["inputs"]["apk_lock"] if plan["mode"] == "build" else LOCK.split()
    files = {"RESULT": b"PASS\n", "toolchain.txt": b"gcc 15\n", "environment.txt": b"nproc=4\n",
             "apk.base.current": BASE_LOCK.encode(),
             "cgroup.txt": ("".join(f"{k}={v}\n" for k, v in cg.items()) + f"id={cid}\n").encode(),
             "logs/steps.log": b"x PASS\n"}
    files.update(dep_evidence(plan, delta, local_data))
    if plan["mode"] == "resolve":
        files["apk.lock.candidate"] = "".join(d + "\n" for d in delta).encode()
        files["apk.base.candidate"] = BASE_LOCK.encode()
    for v, marker in (("unpatched", b""), ("patched", b"ros_ch1_coin_capacity\0")):
        files[f"{v}/map-server"] = fake_elf(marker)
        files[f"{v}/map-server.debug"] = b"dbg" + v.encode()
        files[f"{v}/BUILD_ID"] = hashlib.sha1(v.encode()).hexdigest().encode() + b"\n"
        files[f"{v}/interp.txt"] = b"  [Requesting program interpreter: /lib/ld-musl-aarch64.so.1]\n"
        files[f"{v}/dynamic.txt"] = b" (NEEDED) Shared library: [libz.so.1]\n (NEEDED) Shared library: [libunwind.so.8]\n"
    if tamper:
        tamper(files)
    if "SHA256SUMS" not in files:
        files["SHA256SUMS"] = "".join(f"{hashlib.sha256(d).hexdigest()}  ./{k}\n" for k, d in sorted(files.items())
                                      if k != "RESULT").encode()
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as t:
        for k, d in sorted(files.items()):
            info = tarfile.TarInfo("out/" + k)
            info.size = len(d)
            info.mode = 0o755 if k.endswith("/map-server") else 0o644
            info.uid, info.gid = owner if k.endswith("/map-server") else (0, 0)
            t.addfile(info, io.BytesIO(d))
    return raw.getvalue()


class FakeEngine:
    """modes: ok | fail | hang. faults: {(method, route-tail): behaviour}."""

    def __init__(self, mode="ok", preexisting=None, faults=None, import_owner=(0, 0, 0o755), export=None):
        self.mode, self.faults, self.import_owner = mode, faults or {}, import_owner
        self.export_fn = export
        self.containers, self.calls, self.polls, self.creates = {}, [], 0, 0
        for cid, c in (preexisting or {}).items():
            self.containers[cid] = dict(c, status="exited")
        self.dir = Path(tempfile.mkdtemp(prefix="fe-", dir="/tmp"))
        self.sock = str(self.dir / "e.sock")
        engine = self

        class H(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def address_string(self):
                return "unix"

            def log_message(self, *a):
                pass

            def handle_any(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else b""
                path = self.path.removeprefix(br.API)
                engine.calls.append((self.command, path.split("?")[0]))
                out = engine.route(self.command, path, body)
                if out == "drop":  # close without any response
                    self.close_connection = True
                    return
                code, payload, ctype, headers, behaviour = (list(out) + [None] * 5)[:5]
                if isinstance(payload, (dict, list)):
                    payload = json.dumps(payload).encode()
                payload = payload or b""
                try:
                    self.send_response(code)
                    self.send_header("Content-Type", ctype or "application/json")
                    for k, v in headers or ():
                        self.send_header(k, v)
                    declared = len(payload) + (1000 if behaviour == "truncate" else 0)
                    self.send_header("Content-Length", str(0 if self.command == "HEAD" else declared))
                    self.end_headers()
                    if self.command == "HEAD":
                        return
                    if behaviour == "slow":
                        for b in payload:
                            self.wfile.write(bytes([b]))
                            self.wfile.flush()
                            time.sleep(0.2)
                    else:
                        self.wfile.write(payload)
                    if behaviour == "truncate":
                        self.close_connection = True
                except (BrokenPipeError, ConnectionResetError):
                    pass

            do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = handle_any

        class S(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
            daemon_threads = True

        self.server = S(self.sock, H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def route(self, m, path, body):
        p, _, q = path.partition("?")
        parts = p.strip("/").split("/")
        tail = parts[2] if len(parts) > 2 else ""
        fault = self.faults.get((m, tail or parts[-1]))
        if m == "GET" and p == "/containers/json":
            return 200, [{"Id": k, "Names": ["/" + c.get("name", k)], "Labels": c["labels"]}
                         for k, c in self.containers.items()]
        if m == "POST" and p == "/containers/create":
            self.creates += 1
            name = q.split("name=", 1)[1] if "name=" in q else "anon"
            if any(c.get("name") == name for c in self.containers.values()):
                return 409, {"message": "Conflict. name in use"}
            req = json.loads(body)
            labels = dict(req.get("Labels", {}))
            if fault == "foreign-labels":
                labels[br.RUN_LABEL] = "someone-else"
            cid = "c%d" % self.creates
            self.containers[cid] = {"name": name, "labels": labels, "status": "created",
                                    "hc": req.get("HostConfig", {})}
            if fault == "delay":
                time.sleep(0.8)
            if fault in ("drop", "foreign-labels"):
                return "drop"
            if fault == "500":
                return 500, {"message": "internal"}
            return 201, {"Id": cid}
        cid = parts[1] if len(parts) > 1 else ""
        c = self.containers.get(cid)
        if c is None:
            return 404, {"message": "no such container"}
        if m == "GET" and tail == "json":
            if c["status"] == "running":
                self.polls += 1
                if fault == "slow":
                    return 200, {"State": {"Running": True, "Status": "running"}, "pad": "x" * 200}, None, None, "slow"
                if self.mode in ("ok", "fail") and self.polls >= 2:
                    c["status"], c["exit"] = "exited", 0 if self.mode == "ok" else 1
            return 200, {"Config": {"Labels": c["labels"]}, "HostConfig": c.get("hc", {}),
                         "State": {"Running": c["status"] == "running", "Status": c["status"],
                                   "ExitCode": c.get("exit", 0)}}
        if m == "PUT" and tail == "archive":
            return 200, b""
        if m == "POST" and tail == "start":
            c["status"] = "running"
            return 204, b""
        if m == "POST" and tail == "kill":
            c["status"], c["exit"] = "exited", 137
            return 204, b""
        if m == "GET" and tail == "logs":
            return 200, b"log\n", "application/octet-stream"
        if tail == "archive" and m in ("GET", "HEAD"):
            if fault == "delay":
                time.sleep(0.8)
            if "path=/work/out" in q:
                data = self.export_fn(cid) if self.export_fn else b""
                return 200, data, "application/x-tar", None, "truncate" if fault == "truncate" else None
            uid, gid, mode = self.import_owner
            data = fake_elf(b"ros_ch1_coin_capacity\0")
            raw = io.BytesIO()
            with tarfile.open(fileobj=raw, mode="w") as t:
                info = tarfile.TarInfo("map-server-t10-010-patched")
                info.size, info.mode, info.uid, info.gid = len(data), mode, uid, gid
                t.addfile(info, io.BytesIO(data))
            stat = base64.b64encode(json.dumps({"mode": mode}).encode()).decode()
            return 200, raw.getvalue(), "application/x-tar", [("X-Docker-Container-Path-Stat", stat)]
        if m == "DELETE" and len(parts) == 2:
            if fault == "refuse":
                return 500, {"message": "device busy"}
            del self.containers[cid]
            return 204, b""
        return 501, {"message": "not in fake"}

    def close(self):
        self.server.shutdown()
        self.server.server_close()
        shutil.rmtree(self.dir, ignore_errors=True)


class Clock:
    def __init__(self):
        self.t = 0.0

    def now(self):
        return self.t

    def sleep(self, s):
        self.t += 1000.0


class RecipeBase(unittest.TestCase):
    """Shared prepared fixture, fake engines and plan helper (no tests)."""
    @classmethod
    def setUpClass(cls):
        cls.fx = Fixture({"0001-ok.patch": PATCH_OK})
        cls.fx.fetch()
        cls.fx.discover()
        ps.prepare(cls.fx.cache, cls.fx.out, cls.fx.manifest, "patch", pins={})
        # Give the fixture a crash verify.sh of the pinned shape, pin it, re-pin the digest.
        cls.verify_src = (b"#!/bin/sh\ncd /rathena/ragnarok-crash-tests\nmkdir -p /symbols/trace-tests\n"
                          b"cp a /symbols/trace-tests/\n")
        cls.fx.manifest["crash_verify_sha256"] = hashlib.sha256(cls.verify_src).hexdigest()
        crash = cls.fx.out / "source" / "ragnarok-crash-tests"
        crash.mkdir()
        (crash / "verify.sh").write_bytes(cls.verify_src)
        rows = ps.tree_listing(cls.fx.out / "source")
        cls.fx.manifest["prepared_tree"]["sha256"] = ps.digest(rows)
        cls.fx.manifest["prepared_tree"]["files"] = len(rows)
        rec = json.loads((cls.fx.out / ps.MARKER).read_text())
        rec["prepared_tree_sha256"] = ps.digest(rows)
        (cls.fx.out / ps.MARKER).write_text(json.dumps(rec))

    @classmethod
    def tearDownClass(cls):
        cls.fx.close()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="t10-010-003-recipe-"))
        self.engines = []
        self.lock = self.tmp / "apk.lock"
        self.lock.write_text(LOCK)
        self.base = self.tmp / "apk.base"
        self.base.write_text(BASE_LOCK)

    def tearDown(self):
        for e in self.engines:
            e.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def engine(self, **kw):
        e = FakeEngine(**kw)
        self.engines.append(e)
        return e

    def plan(self, name="run", mode="build", **kw):
        args = dict(mem_available=4 << 30, host_cpus=4, mode=mode, apk_lock=self.lock if mode == "build" else None,
                    apk_base=self.base if mode == "build" else None, manifest=self.fx.manifest, pins={})
        args.update(kw)
        p = br.plan(self.fx.out, self.tmp / name, BASE, "1.2.5-r23", "15.2.0-r2", **args)
        path = self.tmp / name / "PLAN.json"
        return p, path, hashlib.sha256(path.read_bytes()).hexdigest()

    def run_ok(self, **engine_kw):
        holder = {}
        e = self.engine(export=lambda cid: export_tar(holder["p"], cid), **engine_kw)
        p, path, admit = self.plan()
        holder["p"] = p
        return e, p, path, admit


class RecipeTests(RecipeBase):
    # ---------------------------------------------------------------- plan
    def test_plan_deterministic_mounts_limits_and_cgroup(self):
        p1, _, _ = self.plan("a")
        p2, _, _ = self.plan("b")
        self.assertEqual(p1["inputs"]["upload_tar_sha256"], p2["inputs"]["upload_tar_sha256"])
        hc = p1["create"]["HostConfig"]
        self.assertNotIn("Binds", hc)
        self.assertEqual(hc["Mounts"], [{"Type": "bind", "Source": "/sys/fs/cgroup/slim",
                                         "Target": "/run/root-cgroup-view", "ReadOnly": True}])
        self.assertEqual((hc["Memory"], hc["MemorySwap"], hc["NanoCpus"], hc["PidsLimit"]),
                         (1536 << 20, (1536 << 20) + (1 << 20), 2 * 10**9, 1024))
        self.assertEqual(p1["expected_cgroup"], {"memory.max": str(1536 << 20), "memory.swap.max": str(1 << 20),
                                                 "cpu.max": "200000 100000", "pids.max": "1024"})
        with tarfile.open(self.tmp / "a" / "upload.tar") as t:
            self.assertEqual(sorted(t.getnames()), ["apk.base", "apk.lock", "coin_capacity.patch", "crash_verify.sh",
                                                     "guest_build.sh", "guest_lib.sh", "inputs.env", "source.tar.gz"])
            cv = t.extractfile("crash_verify.sh").read().decode()
            self.assertNotIn("/rathena", cv)
            self.assertIn("cd /work/crash/ragnarok-crash-tests", cv)
            self.assertEqual(cv.count("/work/crash/symbols/trace-tests"), 2)

    def test_slim_cgroup_formula(self):
        self.assertEqual(br.expected_cgroup(100, 100, 10**9, 64)["memory.swap.max"], "100")  # swap==mem -> mem
        self.assertEqual(br.expected_cgroup(100, 150, 25 * 10**7, 64)["memory.swap.max"], "50")
        self.assertEqual(br.expected_cgroup(100, 150, 25 * 10**7, 64)["cpu.max"], "25000 100000")

    def test_plan_positive_bounds(self):
        cases = [dict(memory_mib=0), dict(memory_mib=-1), dict(memory_mib=10**6), dict(cpus=0), dict(cpus=5),
                 dict(jobs=0), dict(jobs=3), dict(pids=0), dict(reserve_mib=0), dict(deadline=0),
                 dict(step_timeout=10), dict(step_timeout=7200, deadline=3600), dict(cleanup_budget=0),
                 dict(post_budget=0), dict(mem_available=1 << 30), dict(host_cpus=0), dict(memory_mib=True)]
        for i, kw in enumerate(cases):
            with self.subTest(kw), self.assertRaises(br.RecipeError):
                self.plan(f"bad{i}", **kw)
            self.assertFalse((self.tmp / f"bad{i}").exists())

    def test_dependency_inputs_explicit(self):
        for kw in (dict(apk_lock=None), dict(apk_base=None)):
            with self.subTest(kw), self.assertRaises(br.RecipeError) as cm:
                self.plan("missing", **kw)
            self.assertIn("requires explicit", str(cm.exception))
        bad_locks = {
            "format": "gcc\n",
            "libunwind": LOCK.replace("libunwind-dev=1.8.1-r0", "libunwind-dev=1.9.0-r0"),
            "missing patch": LOCK.replace("patch=2.8-r0\n", ""),
            "unsorted": "zz=1-r0\n" + LOCK,
            "duplicate": LOCK + LOCK.splitlines()[0] + "\n",
            "re-pins base (upgrade)": "bash=5.3-r1\n" + LOCK,
        }
        for name, bad in bad_locks.items():
            self.lock.write_text(bad)
            with self.subTest(name), self.assertRaises(br.RecipeError):
                self.plan("badlock")
        self.lock.write_text(LOCK)
        bad_bases = {
            "bash in neither": BASE_LOCK.replace("bash=5.3-r0\n", ""),
            "abi musl": BASE_LOCK.replace("musl=1.2.5-r23", "musl=1.2.5-r24"),
            "empty": "",
        }
        for name, bad in bad_bases.items():
            self.base.write_text(bad)
            with self.subTest(name), self.assertRaises(br.RecipeError):
                self.plan("badbase")
        self.base.write_text(BASE_LOCK)
        p, _, _ = self.plan("ok")  # preinstalled bash: covered by base, absent from delta
        self.assertNotIn("bash=5.3-r0", p["inputs"]["apk_lock"])
        self.assertIn("bash=5.3-r0", p["inputs"]["apk_base"])
        p, _, _ = self.plan("resolve", mode="resolve")
        self.assertIsNone(p["inputs"]["apk_lock"])
        with self.assertRaises(br.RecipeError):
            self.plan("resolve2", mode="resolve", apk_lock=self.lock)

    def test_all_wanted_preinstalled_empty_delta(self):
        base = {w: "1-r0" for w in br.WANT}
        base.update({"libunwind-dev": "1.8.1-r0", "musl": "1.2.5-r23", "libstdc++": "15.2.0-r2"})
        self.base.write_text("".join(f"{k}={v}\n" for k, v in sorted(base.items())))
        self.lock.write_text("")
        p, _, _ = self.plan("empty-delta")
        self.assertEqual(p["inputs"]["apk_lock"], [])

    def test_resolve_export_with_preinstalled_bash_validates(self):
        e = self.engine()
        p, path, admit = self.plan("res", mode="resolve")

        def resolve_files(f):
            f.pop("unpatched/map-server")
            f["apk.lock.candidate"] = LOCK.encode()      # delta: no bash
            f["apk.base.candidate"] = BASE_LOCK.encode()  # base: has bash
        e.export_fn = lambda cid: export_tar(p, cid, resolve_files)
        br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        r = br.validate_export(path, self.tmp / "res" / "export.tar", self.tmp / "res-v")
        self.assertNotIn("bash=5.3-r0", r["lock_candidate"])
        self.assertIn("bash=5.3-r0", r["base_candidate"])

    def test_build_export_base_freeze_and_no_upgrade(self):
        e, p, path, admit = self.run_ok()
        br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        cid = json.loads((self.tmp / "run" / "EXECUTION.json").read_text())["container_id"]
        cases = {
            "base drift": lambda f: f.__setitem__("apk.base.current", b"bash=5.3-r1\nlibstdc++=15.2.0-r2\nmusl=1.2.5-r23\n"),
            "base upgraded by install": lambda f: f.__setitem__(
                "apk-after.txt", f["apk-after.txt"].replace(b"bash-5.3-r0", b"bash-5.3-r1")),
            "base removed by install": lambda f: f.__setitem__(
                "apk-after.txt", f["apk-after.txt"].replace(b"bash-5.3-r0\n", b"")),
        }
        for name, tamper in cases.items():
            with self.subTest(name):
                tar = self.tmp / f"{name}.tar"
                tar.write_bytes(export_tar(p, cid, tamper))
                with self.assertRaises(br.RecipeError):
                    br.validate_export(path, tar, self.tmp / f"x-{name}")

    def test_crash_verify_transform_refuses_drift(self):
        with self.assertRaises(br.RecipeError):
            br.crash_verify(b"cd /rathena/x\n", br.sha256(b"cd /rathena/x\n"))
        with self.assertRaises(br.RecipeError):
            br.crash_verify(self.verify_src)  # not the pinned real sha
        for v in (HERE.parents[2] / ".tools").glob("*/prepared*/source/ragnarok-crash-tests/verify.sh"):
            out = br.crash_verify(v.read_bytes()).decode()  # the real pinned app fixture
            self.assertNotIn("/rathena", out)
            break

    # ---------------------------------------------------------------- execute
    def test_execute_success_then_validate_and_import(self):
        e, p, path, admit = self.run_ok()
        res = br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        self.assertEqual((res["exit_code"], res["deleted"]), (0, True))
        self.assertEqual(e.containers, {})
        self.assertEqual(e.calls, [
            ("GET", "/containers/json"), ("POST", "/containers/create"), ("GET", "/containers/c1/json"),
            ("PUT", "/containers/c1/archive"), ("PUT", "/containers/c1/archive"), ("POST", "/containers/c1/start"),
            ("GET", "/containers/c1/json"), ("GET", "/containers/c1/json"), ("GET", "/containers/c1/logs"),
            ("GET", "/containers/c1/archive"), ("DELETE", "/containers/c1"), ("GET", "/containers/c1/json")])
        art = br.validate_export(path, self.tmp / "run" / "export.tar", self.tmp / "art")
        self.assertEqual(art["artifacts"]["patched"]["owner"], br.ARTIFACT_OWNER)
        ctx = br.image_context(self.tmp / "art", "patched", BASE, self.tmp / "ctx")
        self.assertEqual((self.tmp / "ctx" / "Dockerfile").read_text(),
                         f"FROM {BASE}\nCOPY map-server /rathena/map-server-t10-010-patched\n")
        imp = br.import_check(e.sock, "sha256:" + "cd" * 32, "patched", ctx["sha256"])
        self.assertTrue(imp["ok"], imp)
        self.assertEqual(e.containers, {})
        with self.assertRaises(br.RecipeError):
            br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)  # plan consumed

    def test_import_wrong_owner_or_mode_rejected(self):
        data = fake_elf(b"ros_ch1_coin_capacity\0")
        for owner in ((1000, 1000, 0o755), (0, 1000, 0o755), (0, 0, 0o644), (0, 0, 0o4755)):
            e = self.engine(import_owner=owner)
            imp = br.import_check(e.sock, "sha256:" + "cd" * 32, "patched", hashlib.sha256(data).hexdigest())
            self.assertFalse(imp["ok"], owner)
            self.assertEqual(e.containers, {})

    def test_export_wrong_owner_rejected(self):
        e, p, path, admit = self.run_ok()
        br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        cid = json.loads((self.tmp / "run" / "EXECUTION.json").read_text())["container_id"]
        bad = self.tmp / "owner.tar"
        bad.write_bytes(export_tar(p, cid, owner=(1000, 1000)))
        with self.assertRaises(br.RecipeError) as cm:
            br.validate_export(path, bad, self.tmp / "x-owner")
        self.assertIn("owner", str(cm.exception))

    def test_create_response_lost_recovers_exact_owned_object(self):
        e, p, path, admit = self.run_ok(faults={("POST", "create"): "drop"})
        with self.assertRaises(br.RecipeError) as cm:
            br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        self.assertIn("ambiguous", str(cm.exception))
        self.assertEqual(e.creates, 1)  # never retried
        self.assertEqual(e.containers, {})  # our orphan found by name+labels and deleted
        rec = json.loads((self.tmp / "run" / "EXECUTION.json").read_text())
        self.assertEqual((rec["recovered_owned_id"], rec["deleted"]), ("c1", True))

    def test_create_5xx_is_ambiguous_too(self):
        e, p, path, admit = self.run_ok(faults={("POST", "create"): "500"})
        with self.assertRaises(br.RecipeError):
            br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        self.assertEqual((e.creates, e.containers), (1, {}))

    def test_create_lost_with_foreign_labels_never_touched(self):
        e, p, path, admit = self.run_ok(faults={("POST", "create"): "foreign-labels"})
        with self.assertRaises(br.RecipeError) as cm:
            br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        self.assertIn("UNRESOLVED", str(cm.exception))
        self.assertEqual(list(e.containers), ["c1"])  # not ours by label: left alone
        self.assertNotIn(("DELETE", "/containers/c1"), e.calls)

    def test_name_conflict_refused_without_retry_or_delete(self):
        e, p, path, admit = self.run_ok()
        e.containers["x"] = {"name": p["container_name"], "labels": {}, "status": "exited"}
        with self.assertRaises(br.RecipeError) as cm:
            br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        self.assertIn("single-owner", str(cm.exception))
        self.assertEqual((e.creates, list(e.containers)), (0, ["x"]))

    def test_single_owner_refusal(self):
        e, p, path, admit = self.run_ok(preexisting={"old": {"name": "old", "labels": {br.ROLE_LABEL: "compiler"}}})
        with self.assertRaises(br.RecipeError):
            br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        self.assertEqual((e.calls, list(e.containers)), ([("GET", "/containers/json")], ["old"]))

    def test_deadline_counts_from_admission_kills_and_deletes(self):
        e = self.engine(mode="hang")
        _, path, admit = self.plan(deadline=600, step_timeout=300)
        clock = Clock()
        with self.assertRaises(br.RecipeError) as cm:
            br.execute(path, e.sock, admit, poll=1, now=clock.now, sleep=clock.sleep)
        self.assertIn("deadline", str(cm.exception))
        self.assertIn(("POST", "/containers/c1/kill"), e.calls)
        self.assertEqual(e.containers, {})

    def test_slow_response_hits_absolute_request_deadline(self):
        e, p, path, admit = self.run_ok(faults={("GET", "json"): "slow"})
        t = time.monotonic()
        with self.assertRaises(br.RecipeError):
            # each byte arrives within the idle timeout, but the whole body never
            # within the absolute per-request budget
            br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None, idle=0.5, req_budget=2.0)
        self.assertLess(time.monotonic() - t, 30)
        self.assertEqual(e.containers, {})

    def test_truncated_export_fails_and_cleans_up(self):
        e, p, path, admit = self.run_ok(faults={("GET", "archive"): "truncate"})
        with self.assertRaises(br.RecipeError):
            br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None, idle=1.0)
        self.assertEqual(e.containers, {})
        self.assertFalse((self.tmp / "run" / "export.tar").exists())

    def test_body_cap(self):
        e, p, path, admit = self.run_ok()
        old = br.BODY_CAP["export"]
        br.BODY_CAP["export"] = 100
        try:
            with self.assertRaises(br.RecipeError):
                br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        finally:
            br.BODY_CAP["export"] = old
        self.assertEqual(e.containers, {})

    def test_sigterm_unwinds_through_owned_cleanup(self):
        e, p, path, admit = self.run_ok()
        e.mode = "hang"
        before = signal.getsignal(signal.SIGTERM)

        def sleep(_):
            os.kill(os.getpid(), signal.SIGTERM)
            time.sleep(0.05)

        with self.assertRaises(br.Cancelled):
            br.execute(path, e.sock, admit, poll=0, sleep=sleep)
        self.assertEqual(e.containers, {})
        self.assertIn(("POST", "/containers/c1/kill"), e.calls)
        rec = json.loads((self.tmp / "run" / "EXECUTION.json").read_text())
        self.assertEqual((rec["state"], rec["deleted"], rec["cancelled"]), ("finished", True, "SIGTERM"))
        self.assertIs(signal.getsignal(signal.SIGTERM), before)

    def test_cleanup_refusal_is_unresolved_not_success(self):
        e, p, path, admit = self.run_ok(faults={("DELETE", "c1"): "refuse"})
        with self.assertRaises(br.RecipeError) as cm:
            br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        self.assertIn("UNRESOLVED", str(cm.exception))
        self.assertIn("c1", e.containers)
        rec = json.loads((self.tmp / "run" / "EXECUTION.json").read_text())
        self.assertFalse(rec["deleted"])

    def test_guest_failure_still_cleans_up(self):
        e, p, path, admit = self.run_ok(mode="fail")
        with self.assertRaises(br.RecipeError) as cm:
            br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        self.assertIn("exit=1", str(cm.exception))
        self.assertEqual(e.containers, {})

    def test_admission_and_upload_tamper(self):
        e, p, path, admit = self.run_ok()
        with self.assertRaises(br.RecipeError):
            br.execute(path, e.sock, "0" * 64)
        with open(self.tmp / "run" / "upload.tar", "ab") as fh:
            fh.write(b"x")
        with self.assertRaises(br.RecipeError):
            br.execute(path, e.sock, admit)
        self.assertEqual(e.calls, [])

    def test_export_validation_failures(self):
        e, p, path, admit = self.run_ok()
        br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        cid = json.loads((self.tmp / "run" / "EXECUTION.json").read_text())["container_id"]

        def wrong_machine(f):
            b = bytearray(f["patched/map-server"])
            b[18:20] = (62).to_bytes(2, "little")
            f["patched/map-server"] = bytes(b)

        def late_log(f):
            # the old defect: checksums taken, then the final log line appended
            f["SHA256SUMS"] = "".join(f"{hashlib.sha256(d).hexdigest()}  ./{k}\n" for k, d in sorted(f.items())
                                      if k != "RESULT").encode()
            f["logs/steps.log"] += b"y PASS\n"

        cases = {
            "hash": lambda f: f.__setitem__("SHA256SUMS", b"0" * 64 + b"  ./toolchain.txt\n"),
            "late-log": late_log,
            "machine": wrong_machine,
            "builtin-in-unpatched": lambda f: f.__setitem__("unpatched/map-server", fake_elf(b"ros_ch1_coin_capacity")),
            "abi": lambda f: f.__setitem__("apk-after.txt", b"musl-1.2.5-r24\n"),
            "result": lambda f: f.__setitem__("RESULT", b"FAIL patched-make-map\n"),
            "interp": lambda f: f.__setitem__("patched/interp.txt", b"/lib/ld-linux-aarch64.so.1\n"),
            "cgroup-value": lambda f: f.__setitem__("cgroup.txt", f["cgroup.txt"].replace(b"pids.max=1024", b"pids.max=max")),
            "cgroup-id": lambda f: f.__setitem__("cgroup.txt", f["cgroup.txt"].replace(cid.encode(), b"other")),
            "closure": lambda f: f.__setitem__("apk-after.txt", f["apk-after.txt"] + b"zzz-extra-1.0-r0\n"),
        }
        for name, tamper in cases.items():
            with self.subTest(name):
                tar = self.tmp / f"{name}.tar"
                tar.write_bytes(export_tar(p, cid, tamper))
                with self.assertRaises(br.RecipeError):
                    br.validate_export(path, tar, self.tmp / f"x-{name}")
        evil = io.BytesIO()
        with tarfile.open(fileobj=evil, mode="w") as t:
            info = tarfile.TarInfo("../escape")
            info.size = 1
            t.addfile(info, io.BytesIO(b"x"))
        with self.assertRaises(br.RecipeError):
            br.safe_extract(evil.getvalue(), self.tmp / "evil")
        self.assertFalse((self.tmp / "escape").exists())


class CancellationTests(RecipeBase):
    """Cancellation at every create/known-ID boundary, for execute and import_check."""

    @staticmethod
    def _cancel_after_create(real):
        def call(self, method, path, *a, **k):
            out = real(self, method, path, *a, **k)
            if method == "POST" and path.startswith("/containers/create"):
                raise br.Cancelled("SIGTERM")  # object exists daemon-side; caller never sees the ID
            return out
        return call

    @staticmethod
    def _cancel_before_create(real):
        def call(self, method, path, *a, **k):
            if method == "POST" and path.startswith("/containers/create"):
                raise br.Cancelled("SIGTERM")  # nothing sent
            return real(self, method, path, *a, **k)
        return call

    def _sigterm_in(self, delay):
        t = threading.Timer(delay, lambda: os.kill(os.getpid(), signal.SIGTERM))
        t.start()
        return t

    def test_execute_cancel_raised_after_daemon_create(self):
        e, p, path, admit = self.run_ok()
        before = signal.getsignal(signal.SIGTERM)
        with mock.patch.object(br.Engine, "call", self._cancel_after_create(br.Engine.call)):
            with self.assertRaises(br.Cancelled):
                br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        self.assertEqual((e.creates, e.containers), (1, {}))  # recovered by name+labels, deleted, no retry
        rec = json.loads((self.tmp / "run" / "EXECUTION.json").read_text())
        self.assertEqual((rec["recovered_owned_id"], rec["deleted"], rec["state"]), ("c1", True, "finished"))
        self.assertIs(signal.getsignal(signal.SIGTERM), before)

    def test_execute_cancel_before_create_records_possible_orphan(self):
        e, p, path, admit = self.run_ok()
        with mock.patch.object(br.Engine, "call", self._cancel_before_create(br.Engine.call)):
            with self.assertRaises(br.Cancelled):
                br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        self.assertEqual((e.creates, e.containers), (0, {}))
        rec = json.loads((self.tmp / "run" / "EXECUTION.json").read_text())
        self.assertIsNone(rec["recovered_owned_id"])
        self.assertIn("UNRESOLVED", rec["orphan_unresolved"])

    def test_execute_real_sigterm_during_create_is_deferred_until_id_known(self):
        e, p, path, admit = self.run_ok(faults={("POST", "create"): "delay"})
        t = self._sigterm_in(0.2)
        try:
            with self.assertRaises(br.Cancelled):
                br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        finally:
            t.cancel()
        self.assertEqual((e.creates, e.containers), (1, {}))
        rec = json.loads((self.tmp / "run" / "EXECUTION.json").read_text())
        self.assertEqual((rec["container_id"], rec["deleted"]), ("c1", True))
        self.assertNotIn("create_ambiguous", rec)  # the shield let create finish; ID known directly

    def test_import_cancel_raised_after_daemon_create(self):
        e = self.engine()
        before = signal.getsignal(signal.SIGTERM)
        with mock.patch.object(br.Engine, "call", self._cancel_after_create(br.Engine.call)):
            with self.assertRaises(br.Cancelled):
                br.import_check(e.sock, "sha256:" + "cd" * 32, "patched", "0" * 64)
        self.assertEqual((e.creates, e.containers), (1, {}))
        self.assertIs(signal.getsignal(signal.SIGTERM), before)

    def test_import_real_sigterm_during_create(self):
        e = self.engine(faults={("POST", "create"): "delay"})
        t = self._sigterm_in(0.2)
        try:
            with self.assertRaises(br.Cancelled):
                br.import_check(e.sock, "sha256:" + "cd" * 32, "patched", "0" * 64)
        finally:
            t.cancel()
        self.assertEqual((e.creates, e.containers), (1, {}))

    def test_import_real_sigterm_with_known_id(self):
        e = self.engine(faults={("HEAD", "archive"): "delay"})
        t = self._sigterm_in(0.2)
        try:
            with self.assertRaises(br.Cancelled):
                br.import_check(e.sock, "sha256:" + "cd" * 32, "patched", "0" * 64)
        finally:
            t.cancel()
        self.assertEqual(e.containers, {})
        self.assertIn(("DELETE", "/containers/c1"), e.calls)

    @staticmethod
    def _two_failures(real, body_exc, cleanup):
        """Root's reproduction: HEAD (body) fails, then cleanup fails too."""
        def call(self, method, path, *a, **k):
            if method == "HEAD":
                raise body_exc
            if cleanup == "delete" and method == "DELETE":
                raise br.RecipeError("DELETE refused (injected)")
            if cleanup == "confirm" and method == "GET" and path.endswith("/json"):
                raise br.EngineStatusError(200, "still present (injected)")
            return real(self, method, path, *a, **k)
        return call

    def test_import_cancel_plus_cleanup_failure_keeps_ownership_detail(self):
        for cleanup in ("delete", "confirm"):
            with self.subTest(cleanup):
                e = self.engine()
                rec = self.tmp / f"import-{cleanup}.json"
                cause = br.Cancelled("SIGTERM")
                before = signal.getsignal(signal.SIGTERM)
                with mock.patch.object(br.Engine, "call", self._two_failures(br.Engine.call, cause, cleanup)):
                    with self.assertRaises(br.CancelledUnresolved) as cm:
                        br.import_check(e.sock, "sha256:" + "cd" * 32, "patched", "0" * 64, record=rec)
                exc = cm.exception
                self.assertIsInstance(exc, br.Cancelled)  # still a cancellation (exit 143)
                self.assertIs(exc.__cause__, cause)        # original cause preserved
                d = exc.detail
                self.assertEqual(d["container_id"], "c1")
                self.assertTrue(d["name"].startswith("t10-010-003-import-"))
                self.assertIn("UNRESOLVED", d["message"])
                self.assertIn("injected", d["cleanup_error"])
                self.assertIn("Cancelled: SIGTERM", d["primary"])
                saved = json.loads(rec.read_text())  # durable, written before propagation
                self.assertEqual((saved["deleted"], saved["unresolved"]["container_id"]), (False, "c1"))
                if cleanup == "delete":
                    self.assertIn("c1", e.containers)  # refused delete: the object really remains
                else:
                    self.assertNotIn("c1", e.containers)  # deleted, but absence never confirmed
                self.assertIs(signal.getsignal(signal.SIGTERM), before)

    def test_import_error_plus_cleanup_failure_chains_cause(self):
        e = self.engine()
        cause = br.EngineIOError("HEAD transport failure (injected)")
        with mock.patch.object(br.Engine, "call", self._two_failures(br.Engine.call, cause, "delete")):
            with self.assertRaises(br.CleanupUnresolved) as cm:
                br.import_check(e.sock, "sha256:" + "cd" * 32, "patched", "0" * 64)
        self.assertIs(cm.exception.__cause__, cause)
        self.assertEqual(cm.exception.detail["container_id"], "c1")
        self.assertIn("original failure", str(cm.exception))

    def test_import_cancel_with_confirmed_cleanup_is_plain_cancel(self):
        e = self.engine()
        rec = self.tmp / "import-ok.json"
        cause = br.Cancelled("SIGTERM")
        with mock.patch.object(br.Engine, "call", self._two_failures(br.Engine.call, cause, None)):
            with self.assertRaises(br.Cancelled) as cm:
                br.import_check(e.sock, "sha256:" + "cd" * 32, "patched", "0" * 64, record=rec)
        self.assertIs(cm.exception, cause)
        self.assertNotIsInstance(cm.exception, br.CancelledUnresolved)
        saved = json.loads(rec.read_text())
        self.assertEqual((saved["deleted"], "unresolved" in saved), (True, False))
        self.assertEqual(e.containers, {})

    def test_import_cli_cancel_unresolved_exit_143(self):
        e = self.engine()
        rec = self.tmp / "cli.json"
        with mock.patch.object(br.Engine, "call", self._two_failures(br.Engine.call, br.Cancelled("SIGTERM"),
                                                                      "delete")):
            rc = br.main(["import-check", "--engine-socket", e.sock, "--image", "sha256:" + "cd" * 32,
                          "--variant", "patched", "--expect-sha256", "0" * 64, "--record", str(rec)])
        self.assertEqual(rc, 143)
        self.assertEqual(json.loads(rec.read_text())["unresolved"]["container_id"], "c1")

    def test_import_cleanup_refusal_unresolved(self):
        e = self.engine(faults={("DELETE", "c1"): "refuse"})
        with self.assertRaises(br.RecipeError) as cm:
            br.import_check(e.sock, "sha256:" + "cd" * 32, "patched", "0" * 64)
        self.assertIn("UNRESOLVED", str(cm.exception))

    def test_import_lost_create_no_retry(self):
        e = self.engine(faults={("POST", "create"): "drop"})
        with self.assertRaises(br.RecipeError):
            br.import_check(e.sock, "sha256:" + "cd" * 32, "patched", "0" * 64)
        self.assertEqual((e.creates, e.containers), (1, {}))


class RawUnixServer:
    """Real Unix-socket HTTP peer with byte-exact scripted responses, so the
    framing (Connection: close, EOF-framed, drip, stall, truncation) is what
    the test says -- not what http.server would choose."""

    def __init__(self, respond):
        self.respond, self.requests = respond, []
        self.dir = Path(tempfile.mkdtemp(prefix="raw-", dir="/tmp"))
        self.sock_path = str(self.dir / "e.sock")
        self.srv = __import__("socket").socket(__import__("socket").AF_UNIX)
        self.srv.bind(self.sock_path)
        self.srv.listen(8)
        self.stop = threading.Event()
        threading.Thread(target=self.loop, daemon=True).start()

    def loop(self):
        while not self.stop.is_set():
            try:
                c, _ = self.srv.accept()
            except OSError:
                return
            threading.Thread(target=self.serve, args=(c,), daemon=True).start()

    def serve(self, c):
        try:
            buf = b""
            while b"\r\n\r\n" not in buf:
                d = c.recv(65536)
                if not d:
                    return
                buf += d
            head, _, rest = buf.partition(b"\r\n\r\n")
            line = head.split(b"\r\n")[0].decode()
            n = 0
            for h in head.split(b"\r\n")[1:]:
                if h.lower().startswith(b"content-length:"):
                    n = int(h.split(b":", 1)[1])
            while len(rest) < n:
                rest += c.recv(65536)
            self.requests.append(line)
            self.respond(c, line)
        except OSError:
            pass
        finally:
            try:
                c.close()
            except OSError:
                pass

    def close(self):
        self.stop.set()
        self.srv.close()
        shutil.rmtree(self.dir, ignore_errors=True)


VERSION = b'{"ApiVersion":"1.43","Os":"linux","Arch":"arm64"}'


class CloseFramedTests(unittest.TestCase):
    """Root's first real probe failed on a close-framed GET /version
    (AttributeError: NoneType.settimeout). These run real HTTP over Unix sockets."""

    def setUp(self):
        self.servers = []

    def tearDown(self):
        for sv in self.servers:
            sv.close()

    def serve(self, respond):
        sv = RawUnixServer(respond)
        self.servers.append(sv)
        return sv

    def test_connection_close_with_length_succeeds(self):
        sv = self.serve(lambda c, line: c.sendall(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nConnection: close\r\n"
            b"Content-Length: %d\r\n\r\n" % len(VERSION) + VERSION))
        st, hdr, body = br.Engine(sv.sock_path).call("GET", "/version")
        self.assertEqual((st, json.loads(body)["ApiVersion"]), (200, "1.43"))
        self.assertEqual(sv.requests, ["GET /v1.43/version HTTP/1.1"])

    def test_eof_framed_body_succeeds(self):
        def respond(c, line):
            c.sendall(b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n")
            for i in range(0, len(VERSION), 7):
                c.sendall(VERSION[i:i + 7])
                time.sleep(0.01)
        sv = self.serve(respond)
        st, _, body = br.Engine(sv.sock_path).call("GET", "/version")
        self.assertEqual((st, body), (200, VERSION))

    def test_close_framed_drip_hits_absolute_deadline(self):
        # every byte arrives well inside the idle timeout; the whole body never fits the budget
        def respond(c, line):
            c.sendall(b"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: 400\r\n\r\n")
            for _ in range(400):
                c.sendall(b"x")
                time.sleep(0.05)
        sv = self.serve(respond)
        t = time.monotonic()
        with self.assertRaises(br.EngineIOError) as cm:
            br.Engine(sv.sock_path, idle=1.0).call("GET", "/version", budget=1.0)
        self.assertLess(time.monotonic() - t, 3.0)
        self.assertIn("absolute request deadline", str(cm.exception))

    def test_eof_framed_drip_hits_absolute_deadline(self):
        def respond(c, line):
            c.sendall(b"HTTP/1.0 200 OK\r\n\r\n")
            for _ in range(400):
                c.sendall(b"x")
                time.sleep(0.05)
        sv = self.serve(respond)
        t = time.monotonic()
        with self.assertRaises(br.EngineIOError):
            br.Engine(sv.sock_path, idle=1.0).call("GET", "/version", budget=1.0)
        self.assertLess(time.monotonic() - t, 3.0)

    def test_close_framed_stall_hits_idle_timeout(self):
        def respond(c, line):
            c.sendall(b"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: 10\r\n\r\nab")
            time.sleep(3)
        sv = self.serve(respond)
        t = time.monotonic()
        with self.assertRaises(br.EngineIOError):
            br.Engine(sv.sock_path, idle=0.3).call("GET", "/version", budget=30)
        self.assertLess(time.monotonic() - t, 2.0)

    def test_slow_headers_hit_absolute_deadline(self):
        def respond(c, line):
            for b in b"HTTP/1.1 200 OK\r\nConnection: close\r\n":
                c.sendall(bytes([b]))
                time.sleep(0.05)
        sv = self.serve(respond)
        t = time.monotonic()
        with self.assertRaises(br.EngineIOError):
            br.Engine(sv.sock_path, idle=1.0).call("GET", "/version", budget=0.8)
        self.assertLess(time.monotonic() - t, 3.0)

    def test_close_framed_truncation_detected(self):
        sv = self.serve(lambda c, line: c.sendall(
            b"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: 100\r\n\r\nshort"))
        with self.assertRaises(br.EngineIOError) as cm:
            br.Engine(sv.sock_path).call("GET", "/version")
        self.assertIn("truncated", str(cm.exception))

    def test_close_framed_cap(self):
        def respond(c, line):
            c.sendall(b"HTTP/1.0 200 OK\r\n\r\n" + b"y" * 5000)
        sv = self.serve(respond)
        with self.assertRaises(br.EngineIOError) as cm:
            br.Engine(sv.sock_path).call("GET", "/version", cap=1000)
        self.assertIn("exceeds", str(cm.exception))

    def test_close_framed_head_and_error_status(self):
        stat = base64.b64encode(b'{"mode":493}').decode().encode()

        def respond(c, line):
            if line.startswith("HEAD"):
                c.sendall(b"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: 12345\r\n"
                          b"X-Docker-Container-Path-Stat: " + stat + b"\r\n\r\n")
            else:
                msg = b'{"message":"no such container"}'
                c.sendall(b"HTTP/1.1 404 Not Found\r\nConnection: close\r\nContent-Length: %d\r\n\r\n"
                          % len(msg) + msg)
        sv = self.serve(respond)
        e = br.Engine(sv.sock_path)
        st, hdr, body = e.call("HEAD", "/containers/x/archive?path=/a", ok=(200,))
        self.assertEqual((st, body, hdr["X-Docker-Container-Path-Stat"]), (200, b"", stat.decode()))
        with self.assertRaises(br.EngineStatusError) as cm:
            e.call("GET", "/containers/x/json")
        self.assertEqual(cm.exception.status, 404)
        st, _, _ = e.call("GET", "/containers/x/json", ok=(404,))  # lifecycle 404-confirmation contract
        self.assertEqual(st, 404)

    def test_close_framed_create_keeps_lifecycle_semantics(self):
        created = []

        def respond(c, line):
            if line.startswith("POST /v1.43/containers/create"):
                created.append(line)
                body = b'{"Id":"real1","Warnings":[]}'
                c.sendall(b"HTTP/1.1 201 Created\r\nConnection: close\r\nContent-Length: %d\r\n\r\n"
                          % len(body) + body)
            elif line.startswith("GET /v1.43/containers/json"):
                c.sendall(b"HTTP/1.0 200 OK\r\n\r\n[]")
        sv = self.serve(respond)
        res, holder = {}, {}
        cid, ambiguous = br.create_owned(br.Engine(sv.sock_path), "n", {"Image": "x"}, "r", "compiler",
                                         time.monotonic() + 10, 5, res, holder)
        self.assertEqual((cid, ambiguous, holder["cid"], len(created)), ("real1", False, "real1", 1))

    def test_no_descriptor_leak(self):
        sv = self.serve(lambda c, line: c.sendall(
            b"HTTP/1.1 200 OK\r\nConnection: close\r\nContent-Length: %d\r\n\r\n" % len(VERSION) + VERSION))
        e = br.Engine(sv.sock_path)
        e.call("GET", "/version")
        fds = len(os.listdir("/dev/fd"))
        for _ in range(50):
            e.call("GET", "/version")
        self.assertLessEqual(len(os.listdir("/dev/fd")), fds + 2)


class GuestLibTests(unittest.TestCase):
    """Run the real guest_lib.sh functions under /bin/sh on fixture files."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="t10-010-003-guest-"))
        self.out = self.tmp / "out"
        (self.out / "logs").mkdir(parents=True)
        self.view = self.tmp / "view"
        self.id = "0123456789ab" * 2
        (self.view / self.id).mkdir(parents=True)
        for leaf, v in (("memory.max", "1610612736"), ("memory.swap.max", "1048576"),
                        ("cpu.max", "200000 100000"), ("pids.max", "1024")):
            (self.view / self.id / leaf).write_text(v + "\n")
        # parent-level leaves that must NOT be read
        (self.view / "memory.max").write_text("max\n")
        (self.tmp / "self").write_text(f"0::/slim/{self.id}\n")
        self.mounts = self.tmp / "mountinfo"
        self.mounts.write_text(f"40 30 0:27 /slim {self.view} ro,nosuid,nodev,noexec,relatime shared:9 - cgroup2 cgroup2 rw\n")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def sh(self, script, **env):
        base = {"OUT": str(self.out), "CG_SELF": str(self.tmp / "self"), "CG_MOUNTS": str(self.mounts),
                "CG_VIEW": str(self.view), "CONTAINER_ID": self.id, "EXPECT_MEMORY_MAX": "1610612736",
                "EXPECT_SWAP_MAX": "1048576", "EXPECT_CPU_MAX": "200000 100000", "EXPECT_PIDS_MAX": "1024",
                "STEP_TIMEOUT": "5", "PATH": os.environ["PATH"], "LC_ALL": "C"}
        base.update(env)
        return subprocess.run(["/bin/sh", "-c", f'set -eu; . "{br.GUEST_LIB}"; {script}'], env=base,
                              capture_output=True, text=True, timeout=30)

    def test_check_cgroup_pass(self):
        r = self.sh("check_cgroup")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertIn(f"id={self.id}", (self.out / "cgroup.txt").read_text())

    def test_check_cgroup_fails_closed(self):
        for name, env in (("other id", dict(CONTAINER_ID="f" * 24)), ("wrong pids", dict(EXPECT_PIDS_MAX="32"))):
            with self.subTest(name):
                r = self.sh("check_cgroup", **env)
                self.assertNotEqual(r.returncode, 0)
                self.assertTrue((self.out / "RESULT").read_text().startswith("FAIL"))
        mutations = (
            ("zero memory", lambda: [(self.view / self.id / "memory.max").write_text("0\n")], dict(EXPECT_MEMORY_MAX="0")),
            ("rw mount", lambda: self.mounts.write_text(self.mounts.read_text().replace(" ro,", " rw,")), {}),
            ("not cgroup2", lambda: self.mounts.write_text(self.mounts.read_text().replace("- cgroup2", "- tmpfs")), {}),
            ("no mount", lambda: self.mounts.write_text(""), {}),
            ("parent leaves only", lambda: shutil.rmtree(self.view / self.id), {}),
            ("host cgroup", lambda: (self.tmp / "self").write_text("0::/\n"), {}),
            ("max pids", lambda: (self.view / self.id / "pids.max").write_text("max\n"), {}),
        )
        for name, mutate, env in mutations:
            with self.subTest(name):
                self.tearDown()
                self.setUp()
                mutate()
                self.assertNotEqual(self.sh("check_cgroup", **env).returncode, 0)

    def test_finalize_checksums_include_final_log(self):
        (self.out / "a.txt").write_text("a")
        r = self.sh("log hello; finalize")
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((self.out / "RESULT").read_text(), "PASS\n")
        self.assertTrue((self.out / "logs/steps.log").read_text().rstrip().endswith("PASS"))
        br.check_sums(self.out)  # the exact host-side check: no file changes after hashing
        listed = (self.out / "SHA256SUMS").read_text()
        self.assertIn("./logs/steps.log", listed)
        self.assertNotIn("SHA256SUMS.tmp", listed)

    def test_check_deps_and_lock(self):
        lock = self.tmp / "lock"
        lock.write_text("g++=15.2.0-r2\nmake=4.4.1-r3\n")
        before, after = self.tmp / "b", self.tmp / "a"
        before.write_text("musl-1.2.5-r23\n")
        after.write_text("g++-15.2.0-r2\nmake-4.4.1-r3\nmusl-1.2.5-r23\n")
        self.assertEqual(self.sh(f'check_lock_file "{lock}"; check_deps "{before}" "{after}" "{lock}"').returncode, 0)
        after.write_text("extra-1-r0\ng++-15.2.0-r2\nmake-4.4.1-r3\nmusl-1.2.5-r23\n")
        self.assertNotEqual(self.sh(f'check_deps "{before}" "{after}" "{lock}"').returncode, 0)
        after.write_text("g++-15.2.0-r2\nmake-4.4.1-r3\nmusl-1.2.5-r24\n")
        self.assertNotEqual(self.sh(f'check_deps "{before}" "{after}" "{lock}"').returncode, 0)
        lock.write_text("make=4.4.1-r3\ng++=15.2.0-r2\n")
        self.assertNotEqual(self.sh(f'check_lock_file "{lock}"').returncode, 0)

    def test_check_coverage_base_plus_delta(self):
        base, delta = self.tmp / "base", self.tmp / "delta"
        want = "bash git make cmake gcc g++ zlib-dev mariadb-dev linux-headers libunwind-dev binutils patch"
        base.write_text("bash=5.3-r0\nmusl=1.2.5-r23\n")
        delta.write_text("".join(sorted(f"{w}={'1.8.1-r0' if w == 'libunwind-dev' else '1-r0'}\n"
                                        for w in want.split() if w != "bash")))
        self.assertEqual(self.sh(f'check_lock_file "{base}" nonempty; check_lock_file "{delta}" empty-ok; '
                                 f'check_coverage "{base}" "{delta}" {want}').returncode, 0)
        base.write_text("musl=1.2.5-r23\n")  # bash in neither
        self.assertNotEqual(self.sh(f'check_coverage "{base}" "{delta}" {want}').returncode, 0)
        base.write_text("bash=5.3-r0\nmusl=1.2.5-r23\n")
        delta.write_text("bash=5.3-r1\n" + delta.read_text())  # re-pin (upgrade) of a base package
        self.assertNotEqual(self.sh(f'check_coverage "{base}" "{delta}" {want}').returncode, 0)
        empty = self.tmp / "empty"
        empty.write_text("")
        self.assertEqual(self.sh(f'check_lock_file "{empty}" empty-ok').returncode, 0)
        self.assertNotEqual(self.sh(f'check_lock_file "{empty}" nonempty').returncode, 0)

    def test_base_freeze_from_lock_candidate(self):
        empty, names, vers = self.tmp / "e", self.tmp / "n", self.tmp / "v"
        empty.write_text("")
        names.write_text("bash\nmusl\n")
        vers.write_text("bash-5.3-r0\nmusl-1.2.5-r23\n")
        r = self.sh(f'lock_candidate "{empty}" "{names}" "{vers}"')
        self.assertEqual((r.returncode, r.stdout), (0, "bash=5.3-r0\nmusl=1.2.5-r23\n"))

    def test_lock_candidate(self):
        nb, na, va = self.tmp / "nb", self.tmp / "na", self.tmp / "va"
        nb.write_text("musl\n")
        na.write_text("g++\nlibunwind-dev\nmusl\n")
        va.write_text("g++-15.2.0-r2\nlibunwind-1.8.1-r0\nlibunwind-dev-1.8.1-r0\nmusl-1.2.5-r23\n")
        r = self.sh(f'lock_candidate "{nb}" "{na}" "{va}"')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout, "g++=15.2.0-r2\nlibunwind-dev=1.8.1-r0\n")

    def test_guest_script_contract(self):
        self.assertEqual(subprocess.run(["sh", "-n", str(br.GUEST)]).returncode, 0)
        s = br.GUEST.read_text()
        for needle in ('CXXFLAGS="-g -O2 -fno-omit-frame-pointer -fno-optimize-sibling-calls"',
                       'CPPFLAGS="-DRAGNAROK_CRASH_TRACE"', 'LIBS="-lunwind"', 'LDFLAGS="-Wl,--build-id=sha1 -rdynamic"',
                       '--enable-packetver="$PACKETVER"', 'make -j"$JOBS" map', "-F 0", "CG_VIEW=/run/root-cgroup-view",
                       "chown 0:0"):
            self.assertIn(needle, s)
        self.assertNotIn("ln -sfn", s)
        self.assertNotIn("rm -f /rathena", s)
        self.assertLess(s.index("check_cgroup\n"), s.index("deps_transaction \""))  # every check precedes install


# ====================================================================== T10.010.004
# Scope of everything below: synthetic fixtures. The "APK" files are tar.gz
# stand-ins holding only a .PKGINFO; they carry no signature. FAKE_APK models
# apk's verify/simulate/fetch/add/info results from fixture files. These prove
# the recipe's binding, ordering, constraint and refusal logic -- they do NOT
# authenticate any package, resolve a real repository or run a transaction.

def _pax_record(kv):
    body = f" {kv}\n"
    n = len(body) + 1
    while len(str(n)) + len(body) != n:
        n += 1
    return f"{n}{body}".encode()


def _tar_member(entries, pax=True):
    """Concatenated ustar entries without end-of-archive blocks (abuild-tar
    --cut style), each preceded by a local pax header with time records only,
    like the actual Alpine files."""
    out = b""
    for name, body in entries:
        if pax:
            recs = b"".join(_pax_record(r) for r in ("ctime=0", "atime=0"))
            x = tarfile.TarInfo("PaxHeaders/" + name.lstrip("."))
            x.type, x.size = tarfile.XHDTYPE, len(recs)
            out += x.tobuf(tarfile.USTAR_FORMAT) + recs + bytes(-len(recs) % 512)
        ti = tarfile.TarInfo(name)
        ti.size, ti.mtime = len(body), 0
        out += ti.tobuf(tarfile.USTAR_FORMAT) + body + bytes(-len(body) % 512)
    return out


def pkg_bytes(name, version, arch="aarch64", pkgname=None, sig=True, pkginfo=None, extra_ctl=(), data=True,
              datahash="ab" * 32):
    """Synthetic APK v2 with the supported layout: gzip(signature tar) +
    gzip(control tar with .PKGINFO) + gzip(data tar). The signature entry is
    a placeholder, NOT a real signature: these files authenticate nothing."""
    info = pkginfo if pkginfo is not None else (
        f"# synthetic\npkgname = {pkgname or name}\npkgver = {version}\narch = {arch}\n"
        f"datahash = {datahash}\n").encode()
    parts = []
    if sig:
        parts.append(gzip.compress(_tar_member([(".SIGN.RSA.synthetic-not-a-key.rsa.pub", b"\0" * 64)]), mtime=0))
    parts.append(gzip.compress(_tar_member([(".PKGINFO", info)] + list(extra_ctl)), mtime=0))
    if data:
        parts.append(gzip.compress(_tar_member([("usr/share/synthetic", b"payload " + name.encode())]), mtime=0))
    return b"".join(parts)


def q1_of(data):
    return br.apk_identity(data)["q1"]


LOCAL_DEV = {"musl-dev": "1.2.5-r23", "openssl-dev": "3.5.8-r0", "zlib-dev": "1.3.2-r0"}


def write_manifest(d, pkgs, arches=None, **override):
    """pkgs: {name: version}; writes <name>-<version>.apk + MANIFEST.json in d.
    arches: optional {name: control arch} (default aarch64)."""
    d.mkdir(parents=True, exist_ok=True)
    entries = []
    for n, v in sorted(pkgs.items()):
        data = pkg_bytes(n, v, arch=(arches or {}).get(n, "aarch64"))
        f = f"{n}-{v}.apk"
        (d / f).write_bytes(data)
        entries.append({"file": f, "name": n, "version": v, "bytes": len(data),
                        "sha256": hashlib.sha256(data).hexdigest()})
    m = {"schema": br.LOCAL_SCHEMA, "packages": entries}
    m.update(override)
    (d / "MANIFEST.json").write_text(json.dumps(m))
    return d / "MANIFEST.json", entries


class LocalInputPlanTests(RecipeBase):
    """--apk-local binding: bytes/SHA-256, safe regular single-link identity,
    strict manifest, conflicts; refusal before any run directory exists."""

    def setUp(self):
        super().setUp()
        self.ld = self.tmp / "local"
        # build-mode delta that includes the local development packages
        lock = dict(line.split("=", 1) for line in LOCK.split())
        lock.update(LOCAL_DEV)
        self.lock.write_text("".join(f"{k}={v}\n" for k, v in sorted(lock.items())))

    def refuse(self, name, mode="resolve", text=None, **kw):
        with self.assertRaises(br.RecipeError) as cm:
            self.plan(name, mode=mode, **kw)
        self.assertFalse((self.tmp / name).exists(), "a partial plan was created")
        if text:
            self.assertIn(text, str(cm.exception))
        return cm.exception

    def test_no_local_input_callers_unchanged(self):
        p, _, _ = self.plan("plain")
        self.assertIsNone(p["inputs"]["apk_local"])
        self.assertIn("LOCAL_LIST_SHA256='none'", p["inputs"]["inputs_env"])
        self.assertTrue(p["apk_package_network"])
        with tarfile.open(self.tmp / "plain" / "upload.tar") as t:
            self.assertFalse([n for n in t.getnames() if n.startswith("local-") or n == "apk-local.list"])

    def test_local_inputs_both_modes_bound_into_upload(self):
        man, entries = write_manifest(self.ld, LOCAL_DEV)
        for mode in ("resolve", "build"):
            with self.subTest(mode):
                p, _, _ = self.plan(mode, mode=mode, apk_local=man)
                got = p["inputs"]["apk_local"]
                self.assertEqual([(e["member"], e["name"], e["sha256"]) for e in got],
                                 [(f"local-{i}.apk", e["name"], e["sha256"]) for i, e in enumerate(entries)])
                with tarfile.open(self.tmp / mode / "upload.tar") as t:
                    lst = t.extractfile("apk-local.list").read()
                    self.assertEqual(hashlib.sha256(lst).hexdigest(), p["inputs"]["apk_local_list_sha256"])
                    self.assertIn(f"LOCAL_LIST_SHA256='{p['inputs']['apk_local_list_sha256']}'",
                                  p["inputs"]["inputs_env"])
                    for i, e in enumerate(entries):
                        self.assertEqual(hashlib.sha256(t.extractfile(f"local-{i}.apk").read()).hexdigest(),
                                         e["sha256"])
                        self.assertEqual(lst.decode().splitlines()[i],
                                         f"{i} {e['sha256']} {e['bytes']} {e['name']} {e['version']} {got[i]['q1']} "
                                         f"{got[i]['arch']}")
                        self.assertEqual(got[i]["q1"], q1_of((self.ld / e["file"]).read_bytes()))
                self.assertTrue(p["apk_package_network"])  # partial closure: repository additions remain
        a, _, _ = self.plan("again", mode="build", apk_local=man)
        b, _, _ = self.plan("again2", mode="build", apk_local=man)
        self.assertEqual(a["inputs"]["upload_tar_sha256"], b["inputs"]["upload_tar_sha256"])

    def test_missing_changed_unsafe_inputs_refused(self):
        def fresh():
            shutil.rmtree(self.ld, ignore_errors=True)
            return write_manifest(self.ld, LOCAL_DEV)
        man, entries = fresh()
        f0 = self.ld / entries[0]["file"]
        cases = {
            "missing file": lambda: f0.unlink(),
            "changed bytes": lambda: f0.write_bytes(f0.read_bytes()[:-1] + b"X"),
            "size mismatch": lambda: f0.write_bytes(f0.read_bytes() + b"X"),
            "symlink": lambda: (f0.rename(self.ld / "real.apk"), f0.symlink_to(self.ld / "real.apk")),
            "hard link": lambda: os.link(f0, self.ld / "second-link"),
            "directory": lambda: (f0.unlink(), f0.mkdir()),
            "fifo": lambda: (f0.unlink(), os.mkfifo(f0)),
        }
        for i, (name, mutate) in enumerate(cases.items()):
            with self.subTest(name):
                man, entries = fresh()
                mutate()
                self.refuse(f"unsafe{i}", apk_local=man)

    def test_manifest_strictness_and_conflicts(self):
        man, entries = write_manifest(self.ld, LOCAL_DEV)
        good = json.loads(man.read_text())

        def with_(mut):
            m = json.loads(json.dumps(good))
            mut(m)
            return json.dumps(m)
        e0 = dict(good["packages"][0])
        bad = {
            "caller verified flag": with_(lambda m: m["packages"][0].__setitem__("verified", True)),
            "top-level extra": with_(lambda m: m.__setitem__("trusted", True)),
            "schema": with_(lambda m: m.__setitem__("schema", "other")),
            "empty": with_(lambda m: m.__setitem__("packages", [])),
            "traversal": with_(lambda m: m["packages"][0].__setitem__("file", "../x.apk")),
            "subdir": with_(lambda m: m["packages"][0].__setitem__("file", "a/x.apk")),
            "bool bytes": with_(lambda m: m["packages"][0].__setitem__("bytes", True)),
            "bad version": with_(lambda m: m["packages"][0].__setitem__("version", "1.2.5")),
            "duplicate entry": with_(lambda m: m["packages"].append(dict(e0))),
            "duplicate name": with_(lambda m: m["packages"].append(dict(e0, file="other.apk", sha256="0" * 64))),
            "duplicate file": with_(lambda m: m["packages"].append(dict(e0, name="x-dev", sha256="0" * 64))),
            "duplicate sha": with_(lambda m: m["packages"].append(dict(e0, name="x-dev", file="o.apk"))),
            "duplicate json key": man.read_text().replace('"schema"', '"schema": "x", "schema"', 1),
        }
        for i, (name, text) in enumerate(bad.items()):
            with self.subTest(name):
                man.write_text(text)
                self.refuse(f"strict{i}", apk_local=man)
        man.write_text(json.dumps(good))
        (self.ld / "notgz.apk").write_bytes(b"PK\x03\x04 not gzip")
        h = hashlib.sha256(b"PK\x03\x04 not gzip").hexdigest()
        (self.ld / "ng.json").write_text(json.dumps({"schema": br.LOCAL_SCHEMA, "packages": [
            {"file": "notgz.apk", "name": "x-dev", "version": "1-r0", "bytes": 13, "sha256": h}]}))
        self.refuse("notgz", apk_local=self.ld / "ng.json", text="gzip")
        # conflicts with the frozen base / delta / ABI / libunwind requirement
        conflicts = {"base package": ({"bash": "5.3-r0"}, "build"), "abi musl": ({"musl": "1.2.5-r23"}, "resolve"),
                     "version vs lock": ({"musl-dev": "1.2.5-r24"}, "build"),
                     "not in lock": ({"curl-dev": "8.0-r0"}, "build"),
                     "libunwind": ({"libunwind-dev": "1.9.0-r0"}, "resolve")}
        for i, (name, (pkgs, mode)) in enumerate(conflicts.items()):
            with self.subTest(name):
                d = self.tmp / f"c{i}"
                m, _ = write_manifest(d, pkgs)
                self.refuse(f"conflict{i}", mode=mode, apk_local=m)

    def test_change_during_read_and_replacement_refused(self):
        man, entries = write_manifest(self.ld, LOCAL_DEV)
        target = str(self.ld / entries[0]["file"])
        real_read = os.read
        state = {"grown": False}

        def growing_read(fd, n):
            out = real_read(fd, n)
            if not state["grown"] and os.fstat(fd).st_size == entries[0]["bytes"]:
                state["grown"] = True
                with open(target, "ab") as fh:
                    fh.write(b"appended while reading")
            return out
        with mock.patch.object(br.os, "read", growing_read):
            self.refuse("grow", apk_local=man)
        man, entries = write_manifest(self.ld, LOCAL_DEV)
        real_lstat = os.lstat

        def swapped_lstat(name, *a, **k):
            st = real_lstat(name, *a, **k)
            if name == entries[0]["file"]:
                return os.stat_result((st.st_mode, st.st_ino + 1) + tuple(st)[2:])
            return st
        with mock.patch.object(br.os, "lstat", swapped_lstat):
            self.refuse("swap", apk_local=man, text="replaced")


FAKE_APK = r"""#!/bin/sh
# Modelled apk (synthetic): records argv, answers from $FAKE fixture files.
printf '%s\n' "$*" >> "$FAKE/calls"
while :; do
    case "$1" in --no-network|--no-cache|--simulate) shift ;; --repositories-file) shift 2 ;; *) break ;; esac
done
cmd=$1; shift
case "$cmd" in
verify)
    for f; do
        h=$(sha256sum "$f" | cut -d' ' -f1)
        if grep -qx "$h" "$FAKE/badsig" 2>/dev/null; then echo "$f: UNTRUSTED signature"; exit 1; fi
        echo "$f: OK"
    done ;;
add)
    case " $* " in *" --simulate "*) sim=1 ;; *) sim=0 ;; esac
    if [ "$sim" = 1 ]; then
        [ ! -e "$FAKE/sim_fail" ] || { echo "ERROR: unable to select packages"; exit 1; }
        cat "$FAKE/simulate"
    else
        cat "$FAKE/adds" >> "$FAKE/installed"
        LC_ALL=C sort -o "$FAKE/installed" "$FAKE/installed"
        while IFS= read -r nv; do
            c=$(awk -v nv="$nv" '$1 == nv { print $2 }' "$FAKE/ident")
            printf 'C:%s\nP:%s\nV:%s\n\n' "${c:-Q1AAAAAAAAAAAAAAAAAAAAAAAAAAA=}" "${nv%%=*}" "${nv#*=}"
        done < "$FAKE/adds" >> "$FAKE/db"
    fi ;;
fetch)
    # Models apk-tools 44dcdfc app_fetch.c/query.c selection (synthetic):
    # default --match name compares the NAME with the whole argument, so
    # "name=version" never matches; --match package compares the serialized
    # "name-version" exactly; any unmatched argument -> nothing downloaded.
    match=name; d=
    while :; do
        case "${1:-}" in
        --no-cache) shift ;;
        --match) match=$2; shift 2 ;;
        --output) d=$2; shift 2 ;;
        -*) echo "fake: unsupported fetch option $1"; exit 9 ;;
        *) break ;;
        esac
    done
    [ -n "$d" ] && [ -d "$d" ] || exit 9
    : > "$FAKE/fetch.sel"; err=0
    for q; do
        hit=
        for f in "$FAKE"/repo/*.apk; do
            nv=$(basename "$f" .apk); n=${nv%%=*}; v=${nv#*=}
            case "$match" in
            package) [ "$n-$v" = "$q" ] && hit=$f ;;
            name) [ "$n" = "$q" ] && hit=$f ;;
            *) exit 9 ;;
            esac
        done
        if [ -z "$hit" ]; then echo "${q%%[=<>~]*}: unable to select package (or its dependencies)"; err=$((err + 1)); fi
        [ -z "$hit" ] || printf '%s\n' "$hit" >> "$FAKE/fetch.sel"
    done
    [ "$err" = 0 ] || exit "$err"
    while IFS= read -r f; do
        nv=$(basename "$f" .apk)
        cp "$f" "$d/${nv%%=*}-${nv#*=}.apk"
    done < "$FAKE/fetch.sel"
    [ ! -e "$FAKE/fetch_fault" ] || . "$FAKE/fetch_fault"
    exit 0 ;;
info)
    if [ "${1:-}" = -v ]; then sed 's/=/-/' "$FAKE/installed"; else cut -d= -f1 "$FAKE/installed"; fi ;;
*) exit 8 ;;
esac
"""

def simulate_rows(delta, pad=True):
    """apk-tools 3.0.8 simulate rows: the counter is space-padded to the
    total's width, as in Root's captured log ("( 1/47) Installing ...")."""
    n = len(delta)
    w = len(str(n)) if pad else 0
    return "".join(f"({i + 1:>{w}}/{n}) Installing {d.split('=', 1)[0]} ({d.split('=', 1)[1]})\n"
                   for i, d in enumerate(delta))


WANT_S = " ".join(br.WANT)


class GuestDependencyTests(unittest.TestCase):
    """Real guest_lib.sh deps_transaction/retain_closure under /bin/sh with a
    modelled APK. Proves ordering, exact-base constraints, refusals and the
    retained closure format only (see the scope note above)."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="t10-010-004-deps-"))
        self.fake, self.inn, self.out, self.stage = (self.tmp / x for x in ("fake", "in", "out", "stage"))
        for d in (self.fake / "repo", self.inn, self.out / "logs", self.tmp / "bin", self.tmp / "keys"):
            d.mkdir(parents=True)
        (self.tmp / "bin" / "apk").write_text(FAKE_APK)
        (self.tmp / "bin" / "timeout").write_text('#!/bin/sh\nshift\nexec "$@"\n')  # host has no timeout(1)
        for x in ("apk", "timeout"):
            os.chmod(self.tmp / "bin" / x, 0o755)
        (self.tmp / "keys" / "alpine-stock.rsa.pub").write_text("stock key\n")
        self.base_lines = BASE_LOCK.split()
        (self.tmp / "base").write_text(BASE_LOCK)
        (self.fake / "installed").write_text(BASE_LOCK)
        (self.fake / "db").write_text("".join(f"C:Q1{'B' * 27}=\nP:{x.split('=')[0]}\nV:{x.split('=')[1]}\n\n"
                                              for x in self.base_lines))
        (self.out / "apk-before.txt").write_text("".join(x + "\n" for x in APK_BEFORE))
        delta = {line.split("=", 1)[0]: line for line in LOCK.split()}
        delta.update({n: f"{n}={v}" for n, v in LOCAL_DEV.items()})  # the local zlib-dev replaces the repo one
        self.set_delta(delta.values())
        self.local = {f"{n}={v}" for n, v in LOCAL_DEV.items()}
        self.write_local(LOCAL_DEV)
        for d in self.delta:
            if d not in self.local:
                n, v = d.split("=", 1)
                (self.fake / "repo" / f"{d}.apk").write_bytes(pkg_bytes(n, v))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def set_delta(self, delta, extra_sim=""):
        self.delta = sorted(delta)
        (self.fake / "simulate").write_text(simulate_rows(self.delta) + extra_sim + "OK: simulated\n")
        (self.fake / "adds").write_text("".join(d + "\n" for d in self.delta))

    def write_local(self, pkgs, tamper=None, arches=None):
        rows = []
        for i, (n, v) in enumerate(sorted(pkgs.items())):
            a = (arches or {}).get(n, "aarch64")
            data = pkg_bytes(n, v, arch=a)
            (self.inn / f"local-{i}.apk").write_bytes(data)
            rows.append(f"{i} {hashlib.sha256(data).hexdigest()} {len(data)} {n} {v} {q1_of(data)} {a}\n")
        (self.tmp / "local.list").write_text("".join(rows))
        if tamper:
            tamper()

    def write_ident(self):
        """Modelled apk records, per installed package, the control identity
        of the file that provided it (derived from those bytes)."""
        rows = {}
        for f in list(self.inn.glob("local-*.apk")) + list((self.fake / "repo").glob("*.apk")):
            try:
                i = br.apk_identity(f.read_bytes())
            except br.RecipeError:
                continue
            rows[f"{i['name']}={i['version']}"] = i["q1"]
        rows.update(getattr(self, "ident_override", {}))
        (self.fake / "ident").write_text("".join(f"{k} {v}\n" for k, v in sorted(rows.items())))

    def run_deps(self, lock="", offline=0, extra=""):
        self.write_ident()
        env = {"OUT": str(self.out), "IN": str(self.inn), "STAGE": str(self.stage), "FAKE": str(self.fake),
               "APK": str(self.tmp / "bin" / "apk"), "APK_KEYS_DIR": str(self.tmp / "keys"),
               "APK_DB": str(self.fake / "db"), "WANT": WANT_S, "EXPECT_ARCH": "aarch64", "STEP_TIMEOUT": "30",
               "PATH": f"{self.tmp / 'bin'}:{os.environ['PATH']}", "LC_ALL": "C"}
        script = (f'set -eu; . "{br.GUEST_LIB}"; exec 0<&-; check_local_list "{self.tmp / "local.list"}"; '
                  f'deps_transaction "{self.tmp / "base"}" "{self.tmp / "local.list"}" "{lock}" {offline}; {extra}')
        return subprocess.run(["/bin/sh", "-c", script], env=env, capture_output=True, text=True, timeout=60)

    def calls(self):
        p = self.fake / "calls"
        return p.read_text().splitlines() if p.exists() else []

    def real_adds(self):
        return [c for c in self.calls() if c.startswith("add ") and "--simulate" not in c.split()]

    def test_success_orders_verification_before_transaction_and_pins_whole_base(self):
        r = self.run_deps(extra="retain_closure")
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self.calls()
        sim = [i for i, c in enumerate(calls) if c.startswith("add --simulate ")]
        add = [i for i, c in enumerate(calls) if c in self.real_adds()]
        ver = [i for i, c in enumerate(calls) if " verify " in f" {c} "]
        local_ver = [i for i in ver if "/local-" in calls[i]]
        self.assertEqual((len(sim), len(add), len(local_ver), len(ver)), (1, 1, 3, len(self.delta)))
        self.assertLess(max(local_ver), sim[0])      # local inputs authenticated before the solver sees them
        self.assertLess(max(ver), add[0])            # every closure file authenticated before installation
        for i in ver:
            self.assertTrue(calls[i].startswith("--no-network verify "), calls[i])
        self.assertTrue(calls[add[0]].startswith("add --no-network --no-cache --repositories-file /dev/null "))
        for i in (sim[0], add[0]):
            toks = calls[i].split()
            for b in self.base_lines:                # every exact frozen base pin is a solver constraint
                self.assertIn(b, toks)
            for w in br.WANT:
                self.assertIn("libunwind-dev~1.8.1" if w == "libunwind-dev" else w, toks)
        joined = "\n".join(calls)
        for forbidden in ("--allow-untrusted", "--keys-dir", "--no-scripts", "--force", "--arch", "upgrade"):
            self.assertNotIn(forbidden, joined)
        fetches = [c for c in calls if c.startswith("fetch ")]
        self.assertEqual(len(fetches), 1)  # one batched exact selection: one index load
        toks = fetches[0].split()
        self.assertEqual(toks[:6], ["fetch", "--no-cache", "--match", "package", "--output", toks[5]])
        self.assertEqual(toks[6:], [d.replace("=", "-", 1) for d in sorted(set(self.delta) - self.local)])
        self.assertFalse([t for t in toks[6:] if "=" in t or "*" in t or "?" in t])
        closure = (self.out / "apk-closure.txt").read_text().splitlines()
        self.assertEqual([c.split()[0] for c in closure], self.delta)
        self.assertEqual(sorted(c.split()[4] for c in closure).count("local"), 3)
        ident = (self.out / "apk-installed-identity.txt").read_text().splitlines()
        self.assertEqual([x.split()[0] for x in ident], self.delta)
        # the retained manifest is the documented local-input format, bound by bytes/hash
        raw, ents = br.load_local_manifest(self.out / "apk-closure" / "MANIFEST.json")
        self.assertEqual(sorted(f"{e['name']}={e['version']}" for e in ents), self.delta)
        for line in closure:
            nv, h, b, f, _ = line.split()
            self.assertEqual(hashlib.sha256((self.out / "apk-closure" / f).read_bytes()).hexdigest(), h)

    def test_conflicting_repository_refuses_before_any_transaction(self):
        # the solver proposes a base upgrade: refused from its plan, nothing installed
        n = len(self.delta) + 1  # the upgrade is the last row of a padded, otherwise valid plan
        self.set_delta(self.delta, extra_sim=f"({n:>{len(str(n))}}/{n}) Upgrading musl (1.2.5-r23 -> 1.2.5-r24)\n")
        r = self.run_deps()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("changes existing packages", (self.out / "RESULT").read_text())
        self.assertEqual(self.real_adds(), [])
        self.assertEqual((self.fake / "installed").read_text(), BASE_LOCK)
        # the solver itself cannot satisfy the exact base pins
        self.tearDown(), self.setUp()
        (self.fake / "sim_fail").write_text("")
        r = self.run_deps()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("apk-simulate", (self.out / "RESULT").read_text())
        self.assertEqual(self.real_adds(), [])

    def relist(self, i):
        """Rebind list row i to the current file bytes, so only the signed identity differs."""
        rows = (self.tmp / "local.list").read_text().splitlines()
        data = (self.inn / f"local-{i}.apk").read_bytes()
        f = rows[i].split()
        rows[i] = " ".join([f[0], hashlib.sha256(data).hexdigest(), str(len(data))] + f[3:5] + [q1_of(data)] + f[6:])
        (self.tmp / "local.list").write_text("\n".join(rows) + "\n")

    def test_local_input_refusals_before_solver(self):
        def bad_sig():
            h = hashlib.sha256((self.inn / "local-1.apk").read_bytes()).hexdigest()
            (self.fake / "badsig").write_text(h + "\n")

        def flip_byte():  # the planned list keeps its hash; the uploaded bytes change
            b = bytearray((self.inn / "local-0.apk").read_bytes())
            b[len(b) // 2] ^= 0xFF
            (self.inn / "local-0.apk").write_bytes(bytes(b))

        def other_name():
            (self.inn / "local-2.apk").write_bytes(pkg_bytes("zlib-dev", "1.3.2-r0", pkgname="zlib"))
            self.relist(2)

        def other_arch():
            (self.inn / "local-0.apk").write_bytes(pkg_bytes("musl-dev", "1.2.5-r23", arch="x86_64"))
            self.relist(0)
        cases = {
            "untrusted signature": (LOCAL_DEV, bad_sig, "apk-verify-local-1"),
            "bytes changed after planning": (LOCAL_DEV, flip_byte, "local-0 sha256 changed"),
            "signed identity differs": (LOCAL_DEV, other_name, "identity"),
            "wrong arch": (LOCAL_DEV, other_arch, "local-0 arch"),
            "replaces base": ({"bash": "5.3-r0"}, None, "frozen base"),
        }
        for name, (pkgs, tamper, needle) in cases.items():
            with self.subTest(name):
                self.tearDown(), self.setUp()
                self.write_local(pkgs)
                if tamper:
                    tamper()
                r = self.run_deps()
                self.assertNotEqual(r.returncode, 0)
                self.assertIn(needle, (self.out / "RESULT").read_text())
                self.assertFalse([c for c in self.calls() if "--simulate" in c], "solver ran after a refusal")
                self.assertEqual(self.real_adds(), [])

    def test_repository_fetch_identity_and_install_drift_refused(self):
        repo = sorted(set(self.delta) - self.local)
        n, v = repo[0].split("=", 1)
        (self.fake / "repo" / f"{repo[0]}.apk").write_bytes(pkg_bytes(n, "0.0-r0"))  # mirror serves other bytes
        r = self.run_deps()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("fetch delivered unrequested", (self.out / "RESULT").read_text())
        self.assertEqual(self.real_adds(), [])
        self.tearDown(), self.setUp()
        (self.fake / "adds").write_text((self.fake / "adds").read_text() + "zzz-extra=1-r0\n")
        r = self.run_deps()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("closure differs from the lock", (self.out / "RESULT").read_text())

    def test_build_lock_mismatch_and_offline_completeness(self):
        lock = self.tmp / "lock"
        lock.write_text("".join(d + "\n" for d in self.delta if d != self.delta[0]))
        r = self.run_deps(lock=str(lock))
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("differs from the qualified lock", (self.out / "RESULT").read_text())
        self.assertFalse([c for c in self.calls() if c.startswith("fetch ")])
        self.assertEqual(self.real_adds(), [])
        # offline flag with an incomplete local closure refuses instead of reaching for the network
        self.tearDown(), self.setUp()
        lock = self.tmp / "lock"
        lock.write_text("".join(d + "\n" for d in self.delta))
        r = self.run_deps(lock=str(lock), offline=1)
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("offline closure lacks", (self.out / "RESULT").read_text())
        self.assertFalse([c for c in self.calls() if c.startswith("fetch ")])
        self.assertTrue(all("--no-network" in c.split() for c in self.calls() if not c.startswith("info")))

    def test_fd0_closed_is_replaced_by_dev_null_for_steps(self):
        env = {"OUT": str(self.out), "STEP_TIMEOUT": "5", "PATH": f"{self.tmp / 'bin'}:{os.environ['PATH']}"}
        bare = subprocess.run(["/bin/sh", "-c", "exec 0<&-; cat"], env=env, capture_output=True, timeout=10)
        self.assertNotEqual(bare.returncode, 0)  # control: a child with closed fd0 fails to read it
        r = subprocess.run(["/bin/sh", "-c", f'set -eu; . "{br.GUEST_LIB}"; exec 0<&-; step fd0 cat'],
                           env=env, capture_output=True, text=True, timeout=10)
        self.assertEqual(r.returncode, 0, r.stderr)
        g = br.GUEST.read_text()
        first_apk = min(g.index(x) for x in ("apk --print-arch", "deps_transaction \"", "apk info"))
        self.assertLess(g.index("exec 0< /dev/null"), first_apk)
        self.assertLess(g.index("exec 0< /dev/null"), g.index('. "$IN/guest_lib.sh"'))


HYPHENATED = ["acl-libs=2.3.2-r1", "git-init-template=2.52.0-r0", "libstdc++-dev=15.2.0-r2",
              "mariadb-connector-c-dev=3.4.6-r0", "zstd-libs=1.5.7-r2"]


class FetchSelectionTests(unittest.TestCase):
    """Repair 4: exact full-package-field fetch (modelled apk; see FAKE_APK).
    Proves the call shape, the exact file-set/identity/signature gates and
    refusal paths -- NOT the real apk-tools 3.0.8 behaviour, which is only
    source-supported (query.c/app_fetch.c at 44dcdfc)."""

    def setUp(self):
        self.g = GuestDependencyTests("test_fd0_closed_is_replaced_by_dev_null_for_steps")
        self.g.setUp()
        delta = {line.split("=", 1)[0]: line for line in LOCK.split()}
        delta.update({n: f"{n}={v}" for n, v in LOCAL_DEV.items()})
        delta.update({d.split("=", 1)[0]: d for d in HYPHENATED})
        for d in HYPHENATED:
            n, v = d.split("=", 1)
            (self.g.fake / "repo" / f"{d}.apk").write_bytes(pkg_bytes(n, v))
        self.g.set_delta(delta.values())
        self.repo = sorted(set(self.g.delta) - self.g.local)

    def tearDown(self):
        self.g.tearDown()

    def fake(self, *args):
        d = self.g.tmp / f"fresh-{uuid.uuid4().hex}"
        d.mkdir()
        r = subprocess.run([str(self.g.tmp / "bin" / "apk"), "fetch", "--no-cache", *args[:-1], "--output", str(d),
                            *args[-1]], env={"FAKE": str(self.g.fake), "PATH": os.environ["PATH"]},
                           capture_output=True, text=True, timeout=30)
        return r, sorted(x.name for x in d.iterdir())

    def test_full_package_field_differs_from_old_name_version_call(self):
        # the modelled pinned semantics: old call refuses, as on Root's actual run
        r, files = self.fake(["acl-libs=2.3.2-r1"])
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("acl-libs: unable to select package (or its dependencies)", r.stdout)
        self.assertEqual(files, [])
        r, files = self.fake("--match", "package", ["acl-libs-2.3.2-r1"])
        self.assertEqual((r.returncode, files), (0, ["acl-libs-2.3.2-r1.apk"]), r.stdout)
        # exact field only: a wrong version or bare name selects nothing, and one miss downloads nothing
        for q in (["acl-libs-2.3.2-r0"], ["acl-libs"], ["acl-libs-2.3.2-r1", "libstdc++-dev-15.2.0-r9"]):
            r, files = self.fake("--match", "package", q)
            self.assertNotEqual(r.returncode, 0, q)
            self.assertEqual(files, [], q)

    def test_batched_hyphenated_exact_fetch_installs_once(self):
        r = self.g.run_deps()
        self.assertEqual(r.returncode, 0, r.stderr)
        calls = self.g.calls()
        fetches = [c for c in calls if c.startswith("fetch ")]
        self.assertEqual(len(fetches), 1)
        q = fetches[0].split()[6:]
        self.assertEqual(q, [d.replace("=", "-", 1) for d in self.repo])
        for h in HYPHENATED:
            self.assertIn(h.replace("=", "-", 1), q)
        self.assertNotIn("--recursive", fetches[0].split())
        self.assertNotIn("-R", fetches[0].split())
        self.assertEqual(len(self.g.real_adds()), 1)
        fetch_i = calls.index(fetches[0])
        add_i = calls.index(self.g.real_adds()[0])
        repo_verifies = [i for i, c in enumerate(calls) if c.startswith("--no-network verify ") and "/repo-" in c]
        self.assertEqual(len(repo_verifies), len(self.repo))
        self.assertTrue(all(fetch_i < i < add_i for i in repo_verifies))
        closure = (self.g.out / "apk-closure.txt").read_text().splitlines()
        for line in closure:  # each repo-K file really is the package its row names
            nv, h, b, f, src = line.split()
            if src == "repo":
                data = (self.g.stage / f).read_bytes() if (self.g.stage / f).exists() else None
                if data is not None:
                    self.assertEqual(f"{br.apk_identity(data)['name']}={br.apk_identity(data)['version']}", nv)

    def test_wrong_missing_extra_files_refuse_even_with_exit_zero(self):
        first = self.repo[0].replace("=", "-", 1)
        other = '"$FAKE/other.apk"'  # written into each fresh fixture below
        faults = {
            "missing file": (f'rm -f "$d/{first}.apk"', "different file set"),
            "extra file": (f'cp {other} "$d/busybox-1.37.0-r30.apk"', "different file set"),
            "wrong package bytes": (f'cp {other} "$d/{first}.apk"', "unrequested busybox"),
            "duplicate identity": (f'cp "$d/{self.repo[1].replace("=", "-", 1)}.apk" "$d/{first}.apk"',
                                   "not exactly the wanted"),
            "hidden entry": (f'mv "$d/{first}.apk" "$d/.{first}.apk"', "non-regular, hidden"),
            "symlink": (f'mv "$d/{first}.apk" "$d/../real.apk"; ln -s ../real.apk "$d/{first}.apk"',
                        "non-regular, hidden"),
            "subdirectory": (f'mkdir "$d/sub"; mv "$d/{first}.apk" "$d/sub/"', "different file set"),
            "non-apk name": (f'mv "$d/{first}.apk" "$d/{first}.tar"', "non-regular, hidden"),
            "signature fails": (None, "apk-verify-repo-0"),
        }
        for name, (script, why) in faults.items():
            with self.subTest(name):
                self.tearDown(), self.setUp()
                (self.g.fake / "other.apk").write_bytes(pkg_bytes("busybox", "1.37.0-r30"))
                if script:
                    (self.g.fake / "fetch_fault").write_text("set -e\n" + script + "\n")
                else:
                    data = (self.g.fake / "repo" / f"{self.repo[0]}.apk").read_bytes()
                    (self.g.fake / "badsig").write_text(hashlib.sha256(data).hexdigest() + "\n")
                r = self.g.run_deps()
                self.assertNotEqual(r.returncode, 0, name)
                self.assertIn(why, (self.g.out / "RESULT").read_text())
                self.assertEqual(self.g.real_adds(), [])

    def test_unavailable_exact_package_refuses_without_fallback(self):
        (self.g.fake / "repo" / f"{self.repo[0]}.apk").unlink()
        n = self.repo[0].split("=", 1)[0]
        other = f"{n}=99.0-r0"  # a different version exists: must not be chosen
        (self.g.fake / "repo" / f"{other}.apk").write_bytes(pkg_bytes(n, "99.0-r0"))
        r = self.g.run_deps()
        self.assertNotEqual(r.returncode, 0)
        self.assertIn("apk-fetch", (self.g.out / "RESULT").read_text())
        self.assertEqual(len([c for c in self.g.calls() if c.startswith("fetch ")]), 1)  # no retry/fallback
        self.assertEqual(self.g.real_adds(), [])

    def test_forbidden_transaction_forms_still_refuse_before_fetch(self):
        n = len(self.g.delta)
        w = len(str(n))
        for extra in (f"({n + 1:>{w}}/{n}) Upgrading musl (1.2.5-r23 -> 1.2.5-r24)\n",
                      f" ({n + 1}/{n}) Frobbing zlib (1.3.2-r0)\n",
                      "Upgrading musl (1.2.5-r23 -> 1.2.5-r24)\n"):
            with self.subTest(extra.strip()):
                self.tearDown(), self.setUp()
                self.g.set_delta(self.g.delta, extra_sim=extra)
                r = self.g.run_deps()
                self.assertNotEqual(r.returncode, 0)
                self.assertFalse([c for c in self.g.calls() if c.startswith("fetch ")])
                self.assertEqual(self.g.real_adds(), [])


class ClosureFixture(RecipeBase):
    """Shared local manifest + resolve-run helper (no tests)."""

    def setUp(self):
        super().setUp()
        self.ld = self.tmp / "local"
        self.man, self.entries = write_manifest(self.ld, LOCAL_DEV)
        self.local_data = {f"{e['name']}={e['version']}": (self.ld / e["file"]).read_bytes() for e in self.entries}
        delta = {line.split("=", 1)[0]: line for line in LOCK.split()}
        delta.update({n: f"{n}={v}" for n, v in LOCAL_DEV.items()})
        self.delta = sorted(delta.values())

    def resolve_run(self, name="res"):
        e = self.engine()
        p, path, admit = self.plan(name, mode="resolve", apk_local=self.man)

        def files(f):
            f.pop("unpatched/map-server")
        e.export_fn = lambda cid: export_tar(p, cid, files, delta=self.delta, local_data=self.local_data)
        br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        cid = json.loads((self.tmp / name / "EXECUTION.json").read_text())["container_id"]
        return p, path, cid


class ClosureReplayAndExportTests(ClosureFixture):
    """Resolve export -> strict join -> build plan from the retained closure ->
    offline guest transaction from exactly those bytes (modelled APK)."""

    def test_complete_closure_replays_offline_in_build(self):
        p, path, cid = self.resolve_run()
        r = br.validate_export(path, self.tmp / "res" / "export.tar", self.tmp / "res-v")
        self.assertIn("candidate only", r["note"])
        self.assertEqual(sorted(r["closure"]), self.delta)
        self.assertEqual(r["lock_candidate"], self.delta)
        (self.tmp / "qlock").write_text("".join(d + "\n" for d in r["lock_candidate"]))
        (self.tmp / "qbase").write_text("".join(d + "\n" for d in r["base_candidate"]))
        bp, bpath, _ = self.plan("b-offline", mode="build", apk_lock=self.tmp / "qlock", apk_base=self.tmp / "qbase",
                                 apk_local=Path(r["retained_closure"]["manifest"]))
        self.assertFalse(bp["apk_package_network"])
        self.assertIn("needs no package network", bp["network"])
        by_nv = {f"{e['name']}={e['version']}": e for e in bp["inputs"]["apk_local"]}
        self.assertEqual(sorted(by_nv), self.delta)
        for nv, c in r["closure"].items():
            self.assertEqual(by_nv[nv]["sha256"], c["sha256"])  # bound by full hash, not by name
        # replay: run the real guest transaction on exactly the uploaded bytes, offline, modelled APK
        g = GuestDependencyTests("test_fd0_closed_is_replaced_by_dev_null_for_steps")
        g.setUp()
        try:
            with tarfile.open(self.tmp / "b-offline" / "upload.tar") as t:
                for m in t.getmembers():
                    if m.name.startswith("local-") or m.name in ("apk-local.list", "apk.lock"):
                        (g.inn / m.name).write_bytes(t.extractfile(m).read())
            shutil.copy(g.inn / "apk-local.list", g.tmp / "local.list")
            g.set_delta(self.delta)
            res = g.run_deps(lock=str(g.inn / "apk.lock"), offline=1)
            self.assertEqual(res.returncode, 0, res.stderr)
            calls = g.calls()
            self.assertFalse([c for c in calls if c.startswith("fetch ")])
            self.assertTrue(all("--no-network" in c.split() for c in calls if not c.startswith("info")), calls)
            self.assertEqual(len([c for c in calls if " verify " in f" {c} "]), len(self.delta))
            self.assertEqual({x.split()[4] for x in (g.out / "apk-closure.txt").read_text().splitlines()}, {"local"})
            replay_ident = (g.out / "apk-installed-identity.txt").read_text()
        finally:
            g.tearDown()
        # host qualification of that offline build: every package's identity is
        # derived from the plan's own uploaded bytes (nothing re-exported)
        with tarfile.open(self.tmp / "b-offline" / "upload.tar") as t:
            up = {m.name: t.extractfile(m).read() for m in t.getmembers() if m.name.startswith("local-")}
        ldata = {f"{e['name']}={e['version']}": up[e["member"]] for e in bp["inputs"]["apk_local"]}
        self.assertEqual(replay_ident, "".join(f"{k} {q1_of(v)}\n" for k, v in sorted(ldata.items())))
        e = self.engine(export=lambda cid: export_tar(bp, cid, local_data=ldata))
        badmit = hashlib.sha256(bpath.read_bytes()).hexdigest()
        br.execute(bpath, e.sock, badmit, poll=0, sleep=lambda s: None)
        bcid = json.loads((self.tmp / "b-offline" / "EXECUTION.json").read_text())["container_id"]
        good = self.tmp / "bo-good.tar"
        good.write_bytes(export_tar(bp, bcid, local_data=ldata))
        art = br.validate_export(bpath, good, self.tmp / "bo-good-v")
        self.assertEqual({c["source"] for c in art["dependency_closure"].values()}, {"local"})
        bad = self.tmp / "bo-bad.tar"
        bad.write_bytes(export_tar(bp, bcid, lambda f: set_ident(f, "gcc=15.2.0-r2", q1_of(pkg_bytes("busybox", "1-r0"))),
                                   local_data=ldata))
        with self.assertRaises(br.RecipeError) as cm:
            br.validate_export(bpath, bad, self.tmp / "bo-bad-v")
        self.assertIn("installed C:", str(cm.exception))

    def test_contradictory_exports_fail_with_coherent_checksums(self):
        p, path, cid = self.resolve_run()
        nvd = [d.replace("=", "-", 1) for d in self.delta]

        def sub(name, old, new):
            return lambda f: f.__setitem__(name, f[name].replace(old, new, 1))

        def drop_line(name, line):
            return lambda f: f.__setitem__(name, b"".join(x + b"\n" for x in f[name].splitlines() if x != line))
        first_closure = None

        def closure_hash(f):
            line = f["apk-closure.txt"].splitlines()[0].split()
            f["apk-closure.txt"] = f["apk-closure.txt"].replace(line[1], b"0" * 64, 1)
        cases = {
            "lock candidate vs solver delta": lambda f: f.__setitem__("apk.lock.candidate",
                                                                      f["apk.lock.candidate"] + b"zzz=1-r0\n"),
            "base candidate vs base current": sub("apk.base.candidate", b"bash=5.3-r0", b"bash=5.3-r1"),
            "base upgraded with consistent names": sub("apk-after.txt", b"musl-1.2.5-r23", b"musl-1.2.5-r24"),
            "delta package missing after": drop_line("apk-after.txt", nvd[0].encode()),
            "names-before contradiction": drop_line("apk-names-before.txt", b"bash"),
            "closure lacks a delta package": lambda f: f.__setitem__(
                "apk-closure.txt", b"".join(x + b"\n" for x in f["apk-closure.txt"].splitlines()[1:])),
            "closure hash differs from retained bytes": closure_hash,
            "retained extra file": lambda f: f.__setitem__("apk-closure/repo-99.apk", fake_apk_bytes("x=1-r0")),
            "verification missing": lambda f: f.__setitem__(
                "apk-verify.txt", b"".join(x + b"\n" for x in f["apk-verify.txt"].splitlines()[1:])),
            "verification for other identity": sub("apk-verify.txt", b" aarch64 OK", b" x86_64 OK"),
            "installed identity missing": lambda f: f.__setitem__(
                "apk-installed-identity.txt", f["apk-installed-identity.txt"].split(b"\n", 1)[1]),
            "trusted keys changed": lambda f: f.__setitem__("apk-keys-after.txt", b"other key\n"),
            "manifest differs": sub("apk-closure/MANIFEST.json", b'"bytes": ', b'"bytes": 1'),
            "local input substituted": lambda f: f.__setitem__(
                "apk-closure.txt", f["apk-closure.txt"].replace(b" local-0.apk local", b" local-0.apk repo")),
        }
        self.assertIsNone(first_closure)
        for name, tamper in cases.items():
            with self.subTest(name):
                tar = self.tmp / f"{abs(hash(name))}.tar"
                tar.write_bytes(export_tar(p, cid, lambda f, t=tamper: (f.pop("unpatched/map-server"), t(f)),
                                           delta=self.delta, local_data=self.local_data))
                with self.assertRaises(br.RecipeError):
                    br.validate_export(path, tar, self.tmp / f"x-{abs(hash(name))}")
        # the untampered export with the same generator validates
        good = self.tmp / "good.tar"
        good.write_bytes(export_tar(p, cid, lambda f: f.pop("unpatched/map-server"), delta=self.delta,
                                    local_data=self.local_data))
        self.assertEqual(br.validate_export(path, good, self.tmp / "good-v")["lock_candidate"], self.delta)


# ---------------------------------------------------------------- repair 2
def split_members(data):
    """Independent test-side split of concatenated gzip members (raw bytes)."""
    out, off = [], 0
    while off < len(data):
        d = zlib.decompressobj(31)
        d.decompress(data[off:])
        end = len(data) - len(d.unused_data)
        out.append(data[off:end])
        off = end
    return out


def regzip_control(data, mutate_raw):
    """Rebuild a package whose control tar bytes were changed by mutate_raw."""
    sig, ctl, *rest = split_members(data)
    raw = gzip.decompress(ctl)
    return sig + gzip.compress(mutate_raw(raw), mtime=0) + b"".join(rest)


class ApkIdentityTests(unittest.TestCase):
    """Bounded APK v2 identity parser (identity only, never authentication)."""

    def test_q1_is_sha1_of_compressed_control_member(self):
        data = pkg_bytes("gcc", "15.2.0-r2", extra_ctl=[(".post-install", b"#!/bin/sh\n")])
        i = br.apk_identity(data)
        sig, ctl, dat = split_members(data)
        want = hashlib.sha1(ctl).digest()
        self.assertEqual(i["q1"], "Q1" + base64.b64encode(want).decode())
        self.assertEqual(i["control_sha1"], want.hex())
        self.assertEqual((i["name"], i["version"], i["arch"], i["signature_entries"]), ("gcc", "15.2.0-r2", "aarch64", 1))
        for other in (hashlib.sha1(data).digest(), hashlib.sha1(gzip.decompress(ctl)).digest(),
                      hashlib.sha1(sig).digest()):  # never conflated with whole-file/inflated/signature hashes
            self.assertNotEqual(i["control_sha1"], other.hex())
        self.assertEqual(i["sha256"], hashlib.sha256(data).hexdigest())
        # data member is never inflated: a corrupt payload does not change the identity
        bad_data = sig + ctl + b"\x1f\x8b\x08" + b"\xff" * 40
        self.assertEqual(br.apk_identity(bad_data)["q1"], i["q1"])

    def test_unsupported_truncated_ambiguous_layouts_refuse(self):
        good = pkg_bytes("gcc", "15.2.0-r2")
        sig, ctl, dat = split_members(good)
        flip = bytearray(ctl)
        flip[len(flip) // 2] ^= 0xFF

        def chk(raw):  # corrupt one tar header's checksum
            b = bytearray(raw)
            b[148:156] = b"0000000\0"
            return bytes(b)
        dup = "pkgname = gcc\npkgname = busybox\npkgver = 1-r0\narch = aarch64\ndatahash = " + "ab" * 32 + "\n"
        cases = {
            "truncated control member": sig + ctl[:len(ctl) // 2],
            "corrupted control bytes": sig + bytes(flip) + dat,
            "no data member": sig + ctl,
            "no signature member": pkg_bytes("gcc", "15.2.0-r2", sig=False),
            "tar header checksum": regzip_control(good, chk),
            "truncated tar entry": regzip_control(good, lambda r: r[:600]),
            "repeated pkgname": pkg_bytes("gcc", "1-r0", pkginfo=dup.encode()),
            "missing datahash": pkg_bytes("gcc", "1-r0", pkginfo=b"pkgname = gcc\npkgver = 1-r0\narch = aarch64\n"),
            "two .PKGINFO": pkg_bytes("gcc", "1-r0", extra_ctl=[(".PKGINFO", b"pkgname = x\n")]),
            ".INSTALL": pkg_bytes("gcc", "1-r0", extra_ctl=[(".INSTALL", b"x")]),
            "payload in control": pkg_bytes("gcc", "1-r0", extra_ctl=[("usr/bin/gcc", b"x")]),
            "not gzip": b"PK\x03\x04" + good,
            "unsupported pax key": regzip_control(good, lambda r: r.replace(b"ctime=0\n", b"path=xx\n", 1)),
        }
        for name, data in cases.items():
            with self.subTest(name), self.assertRaises(br.RecipeError):
                br.apk_identity(data)
        with mock.patch.dict(br.APKV2_CAP, {"ctl_raw": 512}):  # inflation bound
            with self.assertRaises(br.RecipeError):
                br.apk_identity(good)

    @unittest.skipUnless(os.environ.get("T10_APK_IDENTITY_DIR"), "private retained APKs not provided")
    def test_known_actual_busybox_identity(self):
        """Root-only/private: the retained BusyBox APK's identity (values from the brief)."""
        data = (Path(os.environ["T10_APK_IDENTITY_DIR"]) / "busybox-1.37.0-r30.apk").read_bytes()
        i = br.apk_identity(data)
        self.assertEqual((i["name"], i["version"], i["arch"]), ("busybox", "1.37.0-r30", "aarch64"))
        self.assertEqual(i["q1"], "Q1ikqlwHVQiBbHyd5Y5R6TMlf4pN8=")
        self.assertEqual(i["control_sha1"], "8a4aa5c075508816c7c9de58e51e933257f8a4df")
        self.assertEqual(i["sha256"], "d3c919f1f142e41ba83c7dbcc392388f23f840dda6867719e660ebb9cc681254")
        # Root's counterexample 2 on the actual bytes: claimed as a compiler package -> refused
        d = Path(tempfile.mkdtemp(prefix="t10-010-004-bb-"))
        try:
            (d / "gcc.apk").write_bytes(data)
            (d / "m.json").write_text(json.dumps({"schema": br.LOCAL_SCHEMA, "packages": [
                {"file": "gcc.apk", "name": "gcc", "version": "15.2.0-r2", "bytes": len(data), "sha256": i["sha256"]}]}))
            with self.assertRaises(br.RecipeError) as cm:
                br.load_local_manifest(d / "m.json")
            self.assertIn("control identity busybox=1.37.0-r30", str(cm.exception))
        finally:
            shutil.rmtree(d, ignore_errors=True)


def rebind(f, nv, data):
    """Coherently substitute the bytes behind closure entry nv: closure hash/size,
    verification row, manifest entry and retained file all agree afterwards."""
    lines = f["apk-closure.txt"].decode().splitlines()
    for i, line in enumerate(lines):
        k, h, b, fn, src = line.split()
        if k == nv:
            lines[i] = f"{k} {hashlib.sha256(data).hexdigest()} {len(data)} {fn} {src}"
            f["apk-closure.txt"] = ("\n".join(lines) + "\n").encode()
            f["apk-verify.txt"] = f["apk-verify.txt"].replace(h.encode(), hashlib.sha256(data).hexdigest().encode())
            f[f"apk-closure/{fn}"] = data
            if "apk-closure/MANIFEST.json" in f:
                m = json.loads(f["apk-closure/MANIFEST.json"])
                for e in m["packages"]:
                    if e["file"] == fn:
                        e["sha256"], e["bytes"] = hashlib.sha256(data).hexdigest(), len(data)
                f["apk-closure/MANIFEST.json"] = json.dumps(m).encode()
            return
    raise AssertionError(nv)


def set_ident(f, nv, q1):
    f["apk-installed-identity.txt"] = b"".join(
        (f"{nv} {q1}".encode() if x.split()[0].decode() == nv else x) + b"\n"
        for x in f["apk-installed-identity.txt"].splitlines())


class IdentityJoinTests(ClosureFixture):
    """Root's coherent-export counterexamples and the raw-byte identity join."""

    def _expect(self, p, path, cid, tamper, ok=False, mode_files=None):
        tag = uuid.uuid4().hex  # unique per call: a reused path would refuse for the wrong reason
        tar = self.tmp / f"j{tag}.tar"

        def t(f):
            if p["mode"] == "resolve":
                f.pop("unpatched/map-server")
            tamper(f)
        tar.write_bytes(export_tar(p, cid, t, delta=self.delta if p["mode"] == "resolve" else None,
                                   local_data=self.local_data))
        dest = self.tmp / f"v{tag}"
        if ok:
            return br.validate_export(path, tar, dest)
        with self.assertRaises(br.RecipeError) as cm:
            br.validate_export(path, tar, dest)
        return str(cm.exception)

    def test_counterexamples_refused_in_resolve(self):
        p, path, cid = self.resolve_run()
        self._expect(p, path, cid, lambda f: None, ok=True)  # baseline still validates
        busybox = pkg_bytes("busybox", "1.37.0-r30", extra_ctl=[(".trigger", b"#!/bin/sh\n")])
        other_q1 = q1_of(busybox)
        x86 = pkg_bytes("gcc", "15.2.0-r2", arch="x86_64")
        cases = {  # name: (tamper, the join that must refuse it)
            # Root 1: a different, valid Q1 in the installed DB; everything else coherent
            "wrong installed C": (lambda f: set_ident(f, "gcc=15.2.0-r2", other_q1), "installed C:"),
            # Root 2: a validly structured package of another identity relabeled as the compiler
            "unrelated package relabeled": (lambda f: rebind(f, "gcc=15.2.0-r2", busybox), "own control identity"),
            "relabeled and C rebound too": (lambda f: (rebind(f, "gcc=15.2.0-r2", busybox),
                                                       set_ident(f, "gcc=15.2.0-r2", other_q1)), "own control identity"),
            "wrong version": (lambda f: rebind(f, "gcc=15.2.0-r2", pkg_bytes("gcc", "15.2.0-r3")),
                              "own control identity"),
            "wrong arch, C rebound": (lambda f: (rebind(f, "gcc=15.2.0-r2", x86),
                                                 set_ident(f, "gcc=15.2.0-r2", q1_of(x86))), "control arch"),
            "corrupted control": (lambda f: rebind(f, "gcc=15.2.0-r2", regzip_control(
                pkg_bytes("gcc", "15.2.0-r2"), lambda r: r[:600])), "apk control member"),
            "truncated file": (lambda f: rebind(f, "gcc=15.2.0-r2", pkg_bytes("gcc", "15.2.0-r2")[:300]), "apk "),
            "local relabeled": (lambda f: rebind(f, "musl-dev=1.2.5-r23", pkg_bytes("musl-dev", "1.2.5-r24")),
                                "differs from the plan"),  # bound to the plan's bytes before any parse
        }
        for name, (tamper, why) in cases.items():
            with self.subTest(name):
                self.assertIn(why, self._expect(p, path, cid, tamper))

    def test_counterexamples_refused_in_build_and_local_join_uses_upload(self):
        # build with planned local inputs (+ repository additions retained in the export)
        (self.tmp / "qlock").write_text("".join(d + "\n" for d in self.delta))
        p, path, admit = self.plan("bld", mode="build", apk_lock=self.tmp / "qlock", apk_local=self.man)
        e = self.engine(export=lambda cid: export_tar(p, cid, local_data=self.local_data))
        br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        cid = json.loads((self.tmp / "bld" / "EXECUTION.json").read_text())["container_id"]
        art = self._expect(p, path, cid, lambda f: None, ok=True)
        self.assertEqual(art["dependency_closure"]["musl-dev=1.2.5-r23"]["source"], "local")
        busybox = pkg_bytes("busybox", "1.37.0-r30")
        x86 = pkg_bytes("gcc", "15.2.0-r2", arch="x86_64")
        for name, (tamper, why) in {
            "wrong installed C (repo)": (lambda f: set_ident(f, "gcc=15.2.0-r2", q1_of(busybox)), "installed C:"),
            "wrong installed C (local)": (lambda f: set_ident(f, "musl-dev=1.2.5-r23", q1_of(busybox)),
                                          "installed C:"),
            "repo bytes relabeled": (lambda f: rebind(f, "gcc=15.2.0-r2", busybox), "own control identity"),
            "relabeled, C rebound": (lambda f: (rebind(f, "gcc=15.2.0-r2", busybox),
                                                set_ident(f, "gcc=15.2.0-r2", q1_of(busybox))), "own control identity"),
            "wrong arch, C rebound": (lambda f: (rebind(f, "gcc=15.2.0-r2", x86),
                                                 set_ident(f, "gcc=15.2.0-r2", q1_of(x86))), "control arch"),
        }.items():
            with self.subTest(name):
                self.assertIn(why, self._expect(p, path, cid, tamper))
        # the plan's own upload is the source for local bytes; a changed upload refuses
        with open(self.tmp / "bld" / "upload.tar", "ab") as fh:
            fh.write(b"\0" * 512)
        self.assertIn("upload.tar", self._expect(p, path, cid, lambda f: None))

    def test_plan_refuses_relabeled_or_corrupt_local_inputs(self):
        d = self.tmp / "relabel"
        d.mkdir()
        cases = {"busybox as gcc": pkg_bytes("busybox", "1.37.0-r30"),
                 "wrong arch": pkg_bytes("gcc", "15.2.0-r2", arch="x86_64"),
                 "corrupt control": regzip_control(pkg_bytes("gcc", "15.2.0-r2"), lambda r: r[:600])}
        for i, (name, data) in enumerate(cases.items()):
            with self.subTest(name):
                (d / "gcc.apk").write_bytes(data)
                (d / "m.json").write_text(json.dumps({"schema": br.LOCAL_SCHEMA, "packages": [
                    {"file": "gcc.apk", "name": "gcc", "version": "15.2.0-r2", "bytes": len(data),
                     "sha256": hashlib.sha256(data).hexdigest()}]}))
                with self.assertRaises(br.RecipeError):
                    self.plan(f"rl{i}", mode="resolve", apk_local=d / "m.json")
                self.assertFalse((self.tmp / f"rl{i}").exists())

    def test_guest_refuses_installed_identity_not_planned(self):
        g = GuestDependencyTests("test_fd0_closed_is_replaced_by_dev_null_for_steps")
        g.setUp()
        try:
            g.ident_override = {"musl-dev=1.2.5-r23": q1_of(pkg_bytes("busybox", "1.37.0-r30"))}
            r = g.run_deps()
            self.assertNotEqual(r.returncode, 0)
            self.assertIn("not its planned control identity", (g.out / "RESULT").read_text())
        finally:
            g.tearDown()


# ---------------------------------------------------------------- noarch repair
NOARCH_LOCAL = {"git-init-template": "2.52.0-r0"}
ACTUAL_NOARCH = {"file": "git-init-template-2.52.0-r0.apk", "nv": "git-init-template=2.52.0-r0",
                 "sha256": "186a00427cc7ea94ad05b0831320d2a77f757743033392998a28b7247e410e63",
                 "bytes": 10347, "q1": "Q10b47slZtNgJtx4xoEbWIPstc52o="}
ACTUAL_NATIVE = {  # Root's frozen five-APK packet: four historically authenticated aarch64 files
    "busybox-1.37.0-r30.apk": "d3c919f1f142e41ba83c7dbcc392388f23f840dda6867719e660ebb9cc681254",
    "musl-dev-1.2.5-r23.apk": "19032a762b8c6967d3789de1bf540754a0121e517402022eebd3ae6f1c9965a4",
    "openssl-dev-3.5.8-r0.apk": "cfd5c8ca8f12817a869e445b474bae8395afeab3029eb0b0f4bae7703f0163b1",
    "zlib-dev-1.3.2-r0.apk": "18a7f594ad7439629cb5889e4f0ad71075dd9f0cd4729a0461ba1501e21bc583"}


def set_verify_arch(f, tag, arch):
    """Change only the arch field of one verification row (hash/identity untouched)."""
    rows = []
    for x in f["apk-verify.txt"].decode().splitlines():
        parts = x.split(" ")
        if parts[0] == tag:
            parts[4:5] = [arch] if arch else []
        rows.append(" ".join(parts) + "\n")
    f["apk-verify.txt"] = "".join(rows).encode()


class NoarchDependencyTests(ClosureFixture):
    """T10.010.004 noarch repair: a dependency package may declare the native
    target (aarch64) or noarch; its ACTUAL value is retained and must agree
    across verification row, raw control bytes and the local plan. Synthetic
    bytes authenticate nothing; the private case reads Root's frozen packet
    only through isolated copies."""

    def setUp(self):
        super().setUp()
        self.nld = self.tmp / "nlocal"
        pkgs = dict(LOCAL_DEV, **NOARCH_LOCAL)
        self.nman, self.nentries = write_manifest(self.nld, pkgs, arches={"git-init-template": "noarch"})
        self.ndata = {f"{e['name']}={e['version']}": (self.nld / e["file"]).read_bytes() for e in self.nentries}
        self.ndelta = sorted(set(self.delta) | {"git-init-template=2.52.0-r0"} | NOARCH_REPO)
        (self.tmp / "nlock").write_text("".join(d + "\n" for d in self.ndelta))

    def run_plan(self, name, mode, man, ldata, delta):
        kw = {"apk_lock": self.tmp / "nlock"} if mode == "build" else {}
        p, path, admit = self.plan(name, mode=mode, apk_local=man, **kw)
        e = self.engine(export=lambda cid: export_tar(p, cid, (lambda f: f.pop("unpatched/map-server"))
                                                      if mode == "resolve" else None, delta=delta, local_data=ldata))
        br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        cid = json.loads((self.tmp / name / "EXECUTION.json").read_text())["container_id"]
        return p, path, cid

    def export(self, p, path, cid, delta, ldata, tamper=None, plan_edit=None):
        """Validate one export; plan_edit rewrites a COPY of the run directory's PLAN.json."""
        tag = uuid.uuid4().hex
        if plan_edit:
            run = self.tmp / f"run-{tag}"
            shutil.copytree(path.parent, run)
            q = json.loads((run / "PLAN.json").read_text())
            plan_edit(q)
            (run / "PLAN.json").write_text(json.dumps(q))
            path = run / "PLAN.json"

        def t(f):
            if p["mode"] == "resolve":
                f.pop("unpatched/map-server")
            if tamper:
                tamper(f)
        tar = self.tmp / f"e{tag}.tar"
        tar.write_bytes(export_tar(p, cid, t, delta=delta, local_data=ldata))
        return br.validate_export(path, tar, self.tmp / f"v{tag}")

    def refused(self, *a, **kw):
        with self.assertRaises(br.RecipeError) as cm:
            self.export(*a, **kw)
        return str(cm.exception)

    def test_local_plan_retains_actual_noarch_and_refuses_other_arches(self):
        for mode in ("resolve", "build"):
            with self.subTest(mode):
                kw = {"apk_lock": self.tmp / "nlock"} if mode == "build" else {}
                p, _, _ = self.plan(f"np-{mode}", mode=mode, apk_local=self.nman, **kw)
                arch = {e["name"]: e["arch"] for e in p["inputs"]["apk_local"]}
                self.assertEqual(arch, {"git-init-template": "noarch", "musl-dev": "aarch64",
                                        "openssl-dev": "aarch64", "zlib-dev": "aarch64"})
                self.assertEqual(p["abi_expect"]["arch"], "aarch64")  # native target unchanged
                self.assertIn("EXPECT_ARCH='aarch64'", p["inputs"]["inputs_env"])
                with tarfile.open(self.tmp / f"np-{mode}" / "upload.tar") as t:
                    lst = t.extractfile("apk-local.list").read().decode().splitlines()
                self.assertEqual([x.split()[6] for x in lst], [arch[x.split()[3]] for x in lst])
        d = self.tmp / "badarch"
        d.mkdir()
        bad = {"x86_64": "x86_64", "unknown": "riscv64", "empty": "", "case": "Noarch", "trailing": "noarch ",
               "list": "aarch64,noarch", "all": "all"}
        for i, (name, a) in enumerate(bad.items()):
            with self.subTest(name):
                info = (f"pkgname = git-init-template\npkgver = 2.52.0-r0\narch = {a}\ndatahash = {'ab' * 32}\n").encode()
                data = pkg_bytes("git-init-template", "2.52.0-r0", pkginfo=info)
                (d / "g.apk").write_bytes(data)
                (d / "m.json").write_text(json.dumps({"schema": br.LOCAL_SCHEMA, "packages": [
                    {"file": "g.apk", "name": "git-init-template", "version": "2.52.0-r0", "bytes": len(data),
                     "sha256": hashlib.sha256(data).hexdigest()}]}))
                with self.assertRaises(br.RecipeError):
                    self.plan(f"ba{i}", mode="resolve", apk_local=d / "m.json")
                self.assertFalse((self.tmp / f"ba{i}").exists())
        for native in ("noarch", "x86_64", ""):  # the native target itself is never relaxed
            with self.subTest(native=native), self.assertRaises(br.RecipeError):
                br.load_local_manifest(self.nman, arch=native)

    def test_guest_verifies_noarch_with_actual_arch_bound_to_plan(self):
        g = GuestDependencyTests("test_fd0_closed_is_replaced_by_dev_null_for_steps")

        def fresh(local_arches, repo_noarch=True):
            g.tearDown(), g.setUp()
            pk = dict(LOCAL_DEV, **NOARCH_LOCAL)
            g.write_local(pk, arches=local_arches)
            g.local = {f"{n}={v}" for n, v in pk.items()}
            extra = set(NOARCH_REPO) if repo_noarch else set()
            g.set_delta(set(g.delta) | g.local | extra)
            for nv in extra:
                n, v = nv.split("=", 1)
                (g.fake / "repo" / f"{nv}.apk").write_bytes(pkg_bytes(n, v, arch="noarch"))
        g.setUp()
        try:
            fresh({"git-init-template": "noarch"})
            r = g.run_deps(extra="retain_closure")
            self.assertEqual(r.returncode, 0, r.stderr)
            rows = {x.split()[2] + "=" + x.split()[3]: x.split()[4] for x in (g.out / "apk-verify.txt").read_text().splitlines()}
            self.assertEqual(rows.pop("git-init-template=2.52.0-r0"), "noarch")
            self.assertEqual(rows.pop("synthetic-noarch-data=1.0-r0"), "noarch")
            self.assertEqual(set(rows.values()), {"aarch64"})
            self.assertFalse([c for c in g.calls() if "--arch" in c or "--allow-untrusted" in c])
            _, ents = br.load_local_manifest(g.out / "apk-closure" / "MANIFEST.json")
            self.assertEqual({e["name"]: e["identity"]["arch"] for e in ents}["git-init-template"], "noarch")

            def list_arch(i, a):
                rows = (g.tmp / "local.list").read_text().splitlines()
                f = rows[i].split(" ")
                rows[i] = " ".join(f[:6] + ([a] if a is not None else []))
                (g.tmp / "local.list").write_text("\n".join(rows) + "\n")
            gi = 0  # sorted: git-init-template is local-0, musl-dev is local-1

            def badsig():
                h = hashlib.sha256((g.inn / f"local-{gi}.apk").read_bytes()).hexdigest()
                (g.fake / "badsig").write_text(h + "\n")

            def x86_bytes():
                (g.inn / "local-0.apk").write_bytes(pkg_bytes("git-init-template", "2.52.0-r0", arch="x86_64"))
                g.relist(0)
            cases = {  # name: (tamper, refusal text)
                "noarch bytes planned as aarch64": (lambda: list_arch(gi, "aarch64"), "is not the planned aarch64"),
                "aarch64 bytes planned as noarch": (lambda: list_arch(1, "noarch"), "is not the planned noarch"),
                "planned arch missing": (lambda: list_arch(gi, None), "local list 0 arch"),
                "planned arch unknown": (lambda: list_arch(gi, "x86_64"), "local list 0 arch"),
                "planned arch quoted-empty token": (lambda: list_arch(gi, "''"), "local list 0 arch"),
                "unsigned noarch input": (badsig, "apk-verify-local-0"),
                "x86_64 bytes, coherent list hash": (x86_bytes, "local-0 arch x86_64"),
            }
            for name, (tamper, needle) in cases.items():
                with self.subTest(name):
                    fresh({"git-init-template": "noarch"})
                    tamper()
                    r = g.run_deps()
                    self.assertNotEqual(r.returncode, 0)
                    self.assertIn(needle, (g.out / "RESULT").read_text())
                    self.assertFalse([c for c in g.calls() if "--simulate" in c], "solver ran after a refusal")
                    self.assertEqual(g.real_adds(), [])
            with self.subTest("repository addition with a foreign arch"):
                fresh({"git-init-template": "noarch"})
                (g.fake / "repo" / "synthetic-noarch-data=1.0-r0.apk").write_bytes(
                    pkg_bytes("synthetic-noarch-data", "1.0-r0", arch="x86_64"))
                r = g.run_deps()
                self.assertNotEqual(r.returncode, 0)
                self.assertRegex((g.out / "RESULT").read_text(), r"repo-\d+ arch x86_64")
                self.assertEqual(g.real_adds(), [])
            with self.subTest("native target cannot become noarch"):
                env_bad = subprocess.run(["/bin/sh", "-c", f'. "{br.GUEST_LIB}"; EXPECT_ARCH=noarch; '
                                          'dependency_arch noarch && echo accepted || echo refused'],
                                         capture_output=True, text=True, timeout=10, env={"PATH": os.environ["PATH"]})
                self.assertEqual(env_bad.stdout.strip(), "refused")
        finally:
            g.tearDown()

    def _arch_counterexamples(self, p, path, cid, delta, ldata, local_nv, native_nv):
        """Coherent hashes/C/Q1; only an architecture record differs."""
        def tag_of(f, nv):
            return next(x.split()[3][:-4] for x in f["apk-closure.txt"].decode().splitlines() if x.split()[0] == nv)

        def row(nv, a):
            return lambda f: set_verify_arch(f, tag_of(f, nv), a)
        x86 = pkg_bytes(*native_nv.split("=", 1), arch="x86_64")
        aarch_for_noarch = pkg_bytes("synthetic-noarch-data", "1.0-r0", arch="aarch64")
        cases = {
            "local noarch row says aarch64": (row(local_nv, "aarch64"), "verification arch 'aarch64' != control arch 'noarch'"),
            "native row says noarch": (row(native_nv, "noarch"), "verification arch 'noarch' != control arch 'aarch64'"),
            "repo noarch row says aarch64": (row("synthetic-noarch-data=1.0-r0", "aarch64"), "verification arch"),
            "row arch unknown": (row(local_nv, "riscv64"), "verification line"),
            "row arch x86_64": (row(native_nv, "x86_64"), "verification line"),
            "row arch missing": (row(local_nv, ""), "verification line"),
            "noarch repo bytes swapped for aarch64, C and hash rebound": (
                lambda f: (rebind(f, "synthetic-noarch-data=1.0-r0", aarch_for_noarch),
                           set_ident(f, "synthetic-noarch-data=1.0-r0", q1_of(aarch_for_noarch))),
                "verification arch 'noarch' != control arch 'aarch64'"),
            "x86_64 bytes, row/C/hash all rebound": (
                lambda f: (rebind(f, native_nv, x86), set_ident(f, native_nv, q1_of(x86)),
                           set_verify_arch(f, tag_of(f, native_nv), "x86_64")), "verification line"),
            "x86_64 bytes, aarch64 row": (
                lambda f: (rebind(f, native_nv, x86), set_ident(f, native_nv, q1_of(x86))), "control arch"),
        }
        for name, (tamper, why) in cases.items():
            with self.subTest(name):
                self.assertIn(why, self.refused(p, path, cid, delta, ldata, tamper=tamper))

        def plan_arch(nv, a):
            def edit(q):
                for e in q["inputs"]["apk_local"]:
                    if f"{e['name']}={e['version']}" == nv:
                        if a is None:
                            del e["arch"]
                        else:
                            e["arch"] = a
            return edit
        musl = "musl-dev=1.2.5-r23"
        for name, (edit, why) in {
            "plan arch missing": (plan_arch(local_nv, None), "plan arch None"),
            "plan noarch changed to aarch64": (plan_arch(local_nv, "aarch64"), "plan arch 'aarch64' != control arch 'noarch'"),
            "plan aarch64 changed to noarch": (plan_arch(musl, "noarch"), "plan arch 'noarch' != control arch 'aarch64'"),
            "plan arch unknown": (plan_arch(local_nv, "x86_64"), "plan arch 'x86_64'"),
        }.items():
            with self.subTest(name):
                self.assertIn(why, self.refused(p, path, cid, delta, ldata, plan_edit=edit))

    def test_resolve_export_binds_actual_arch_across_row_raw_and_plan(self):
        p, path, cid = self.run_plan("nres", "resolve", self.nman, self.ndata, self.ndelta)
        r = self.export(p, path, cid, self.ndelta, self.ndata)
        arch = {k: v["arch"] for k, v in r["derived_identity"].items()}
        self.assertEqual(arch.pop("git-init-template=2.52.0-r0"), "noarch")
        self.assertEqual(arch.pop("synthetic-noarch-data=1.0-r0"), "noarch")
        self.assertEqual(set(arch.values()), {"aarch64"})
        self.assertEqual(r["closure"]["git-init-template=2.52.0-r0"]["arch"], "noarch")
        self.assertEqual(r["closure"]["git-init-template=2.52.0-r0"]["source"], "local")
        self.assertEqual(r["closure"]["synthetic-noarch-data=1.0-r0"]["source"], "repo")
        self.assertEqual(r["lock_candidate"], self.ndelta)
        # the retained manifest replays as a build-mode local input with the same actual arches
        _, ments = br.load_local_manifest(Path(r["retained_closure"]["manifest"]))
        self.assertEqual({f"{e['name']}={e['version']}": e["identity"]["arch"] for e in ments},
                         {k: v["arch"] for k, v in r["derived_identity"].items()})
        self._arch_counterexamples(p, path, cid, self.ndelta, self.ndata, "git-init-template=2.52.0-r0",
                                   "gcc=15.2.0-r2")

    def test_build_export_binds_actual_arch_from_upload(self):
        p, path, cid = self.run_plan("nbld", "build", self.nman, self.ndata, None)
        art = self.export(p, path, cid, None, self.ndata)
        dc = art["dependency_closure"]
        self.assertEqual((dc["git-init-template=2.52.0-r0"]["source"], dc["git-init-template=2.52.0-r0"]["arch"]),
                         ("local", "noarch"))
        self.assertEqual((dc["synthetic-noarch-data=1.0-r0"]["source"], dc["synthetic-noarch-data=1.0-r0"]["arch"]),
                         ("repo", "noarch"))
        self.assertEqual(dc["musl-dev=1.2.5-r23"]["arch"], "aarch64")
        self._arch_counterexamples(p, path, cid, None, self.ndata, "git-init-template=2.52.0-r0", "gcc=15.2.0-r2")

    @unittest.skipUnless(os.environ.get("T10_APK_IDENTITY_DIR") and os.environ.get("T10_APK_SIMULATE_LOG"),
                         "private frozen noarch packet not provided")
    def test_actual_retained_noarch_input(self):
        """Root-only/private: the frozen five-APK packet and its actual 47-row
        simulate log. Read once, then used only through isolated copies. This
        binds bytes/derived identity only: the noarch file has NO stock-key
        authentication here (the modelled guest apk verifies nothing)."""
        src = Path(os.environ["T10_APK_IDENTITY_DIR"])
        raw = {f: (src / f).read_bytes() for f in [ACTUAL_NOARCH["file"]] + sorted(ACTUAL_NATIVE)}
        log_text = Path(os.environ["T10_APK_SIMULATE_LOG"]).read_text()
        self.assertEqual(hashlib.sha256(log_text.encode()).hexdigest(),
                         "8f6f1f2e7004cdbfbdaa0c90645b8ccc85cb23b589b078a4c7a47dfc0ce7cfec")
        for f, h in ACTUAL_NATIVE.items():
            i = br.apk_identity(raw[f])
            self.assertEqual((i["sha256"], i["arch"]), (h, "aarch64"), f)
        ni = br.apk_identity(raw[ACTUAL_NOARCH["file"]])
        self.assertEqual((f"{ni['name']}={ni['version']}", ni["arch"], ni["q1"], ni["sha256"], ni["bytes"]),
                         (ACTUAL_NOARCH["nv"], "noarch", ACTUAL_NOARCH["q1"], ACTUAL_NOARCH["sha256"],
                          ACTUAL_NOARCH["bytes"]))
        # isolated manifest directory: the actual noarch file + the three actual development files
        d = self.tmp / "actual"
        d.mkdir()
        files = [ACTUAL_NOARCH["file"], "musl-dev-1.2.5-r23.apk", "openssl-dev-3.5.8-r0.apk", "zlib-dev-1.3.2-r0.apk"]
        ents = []
        for f in files:
            (d / f).write_bytes(raw[f])
            i = br.apk_identity(raw[f])
            ents.append({"file": f, "name": i["name"], "version": i["version"], "bytes": len(raw[f]),
                         "sha256": i["sha256"]})
        (d / "MANIFEST.json").write_text(json.dumps({"schema": br.LOCAL_SCHEMA, "packages": ents}))
        ldata = {f"{e['name']}={e['version']}": raw[e["file"]] for e in ents}
        # actual solver plan, parsed by the real guest parser
        ps_ = ParseSimulateTests("test_captured_padded_47_row_format")
        ps_.setUp()
        try:
            res, delta = ps_.parse(log_text)
        finally:
            ps_.tearDown()
        self.assertEqual(res.returncode, 0, res.stderr)
        self.assertEqual(len(delta), 47)
        self.assertIn(ACTUAL_NOARCH["nv"], delta)
        p, path, cid = self.run_plan("actual-res", "resolve", d / "MANIFEST.json", ldata, delta)
        got = {f"{e['name']}={e['version']}": e for e in p["inputs"]["apk_local"]}
        self.assertEqual((got[ACTUAL_NOARCH["nv"]]["arch"], got[ACTUAL_NOARCH["nv"]]["q1"]),
                         ("noarch", ACTUAL_NOARCH["q1"]))
        # modelled guest transaction from exactly the plan's upload and the ACTUAL simulate log
        g = GuestDependencyTests("test_fd0_closed_is_replaced_by_dev_null_for_steps")
        g.setUp()
        try:
            with tarfile.open(self.tmp / "actual-res" / "upload.tar") as t:
                for m in t.getmembers():
                    if m.name.startswith("local-") or m.name == "apk-local.list":
                        (g.inn / m.name).write_bytes(t.extractfile(m).read())
            shutil.copy(g.inn / "apk-local.list", g.tmp / "local.list")
            g.set_delta(delta)
            (g.fake / "simulate").write_text(log_text)  # the actual captured solver output
            for x in g.fake.glob("repo/*.apk"):
                x.unlink()
            for nv in delta:
                if nv not in ldata:
                    (g.fake / "repo" / f"{nv}.apk").write_bytes(fake_apk_bytes(nv))
            r = g.run_deps(extra="retain_closure")
            self.assertEqual(r.returncode, 0, r.stderr)
            rows = {x.split()[2] + "=" + x.split()[3]: x.split()[4] for x in (g.out / "apk-verify.txt").read_text().splitlines()}
            self.assertEqual(rows[ACTUAL_NOARCH["nv"]], "noarch")
            self.assertEqual(set(rows), set(delta))
            self.assertEqual(set(v for k, v in rows.items() if k != ACTUAL_NOARCH["nv"]), {"aarch64"})
            # the guest refuses the actual noarch bytes when planned as aarch64
            lst = (g.tmp / "local.list").read_text().splitlines()
            gi = next(i for i, x in enumerate(lst) if x.split()[3] == "git-init-template")
            lst[gi] = lst[gi].rsplit(" ", 1)[0] + " aarch64"
            g.tearDown(), g.setUp()
            with tarfile.open(self.tmp / "actual-res" / "upload.tar") as t:
                for m in t.getmembers():
                    if m.name.startswith("local-"):
                        (g.inn / m.name).write_bytes(t.extractfile(m).read())
            (g.tmp / "local.list").write_text("\n".join(lst) + "\n")
            g.set_delta(delta)
            (g.fake / "simulate").write_text(log_text)
            r = g.run_deps()
            self.assertNotEqual(r.returncode, 0)
            self.assertIn(f"local-{gi} arch noarch is not the planned aarch64", (g.out / "RESULT").read_text())
            self.assertEqual(g.real_adds(), [])
        finally:
            g.tearDown()
        # host export join on the actual bytes; then the actual-arch counterexamples
        r = self.export(p, path, cid, delta, ldata)
        self.assertEqual(r["derived_identity"][ACTUAL_NOARCH["nv"]]["arch"], "noarch")
        self.assertEqual(r["installed_identity"][ACTUAL_NOARCH["nv"]], ACTUAL_NOARCH["q1"])
        tag = got[ACTUAL_NOARCH["nv"]]["member"][:-4]
        self.assertIn("verification arch 'aarch64' != control arch 'noarch'",
                      self.refused(p, path, cid, delta, ldata, tamper=lambda f: set_verify_arch(f, tag, "aarch64")))

        def relabel(q):
            for e in q["inputs"]["apk_local"]:
                if e["name"] == "git-init-template":
                    e["arch"] = "aarch64"
        self.assertIn("plan arch 'aarch64' != control arch 'noarch'",
                      self.refused(p, path, cid, delta, ldata, plan_edit=relabel))
        # the canonical frozen packet was only read
        for f, data in raw.items():
            self.assertEqual(hashlib.sha256((src / f).read_bytes()).hexdigest(), hashlib.sha256(data).hexdigest())


# ---------------------------------------------------------------- repair 3
CAPTURED_SHAPE = (  # synthetic rows in the exact shape of Root's captured 47-row log
    ["jansson=2.14.1-r0", "zstd-libs=1.5.7-r2", "binutils=2.45.1-r0", "acl-libs=2.3.2-r1",
     "libbz2=1.0.8-r6", "libexpat=2.10.0-r0", "lz4-libs=1.10.0-r0", "libarchive=3.8.11-r0",
     "rhash-libs=1.4.6-r0"] + [f"synthetic-{i:02d}=1.{i}.0-r0" for i in range(10, 48)])


class ParseSimulateTests(unittest.TestCase):
    """Real guest_lib.sh parse_simulate under /bin/sh on solver-output text.
    Text fixtures only; no APK is run."""

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="t10-010-004-sim-"))
        (self.tmp / "out" / "logs").mkdir(parents=True)

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def parse(self, text):
        log = self.tmp / "sim.log"
        log.write_text(text)
        for f in (self.tmp / "delta", self.tmp / "out" / "RESULT", self.tmp / "out" / "apk-simulate.refused"):
            f.unlink(missing_ok=True)
        r = subprocess.run(["/bin/sh", "-c", f'set -eu; . "{br.GUEST_LIB}"; parse_simulate "{log}" "{self.tmp / "delta"}"'],
                           env={"OUT": str(self.tmp / "out"), "PATH": os.environ["PATH"], "LC_ALL": "C"},
                           capture_output=True, text=True, timeout=30)
        rows = (self.tmp / "delta").read_text().splitlines() if r.returncode == 0 else None
        return r, rows

    def test_captured_padded_47_row_format(self):
        text = simulate_rows(CAPTURED_SHAPE) + "OK: 341.3 MiB in 73 packages\n"
        self.assertTrue(text.startswith("( 1/47) Installing jansson (2.14.1-r0)\n( 2/47) "))
        self.assertIn("(10/47) Installing synthetic-10", text)
        r, rows = self.parse(text)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(rows, sorted(CAPTURED_SHAPE))  # all 47, incl. the 9 the old parser dropped
        self.assertIn("binutils=2.45.1-r0", rows)

    def test_supported_counter_forms(self):
        cases = {
            "single digit": simulate_rows(CAPTURED_SHAPE[:3]),
            "two-digit padded": simulate_rows(CAPTURED_SHAPE[:12]),
            "two-digit unpadded": simulate_rows(CAPTURED_SHAPE[:12], pad=False),
            "three-digit padded": simulate_rows([f"p{i:03d}=1-r0" for i in range(101)]),
            "empty plan": "OK: 73 packages, nothing to do\n",
        }
        for name, text in cases.items():
            with self.subTest(name):
                r, rows = self.parse(text)
                self.assertEqual(r.returncode, 0, r.stderr)
                self.assertEqual(len(rows), text.count("Installing"))

    def test_forbidden_and_malformed_rows_refuse(self):
        ok = simulate_rows(CAPTURED_SHAPE[:12]).splitlines(keepends=True)

        def at(i, line):
            rows = list(ok)
            rows[i] = line
            return "".join(rows)
        cases = {
            "padded upgrade": at(0, "( 1/12) Upgrading musl (1.2.5-r23 -> 1.2.5-r24)\n"),
            "unpadded upgrade": at(9, "(10/12) Upgrading musl (1.2.5-r23 -> 1.2.5-r24)\n"),
            "padded downgrade": at(1, "( 2/12) Downgrading zlib (1.3.2-r1 -> 1.3.2-r0)\n"),
            "padded reinstall": at(2, "( 3/12) Reinstalling busybox (1.37.0-r30)\n"),
            "padded replace": at(3, "( 4/12) Replacing libssl3 (3.5.8-r0)\n"),
            "padded purge": at(4, "( 5/12) Purging zlib (1.3.2-r0)\n"),
            "padded remove": at(5, "( 6/12) Removing zlib (1.3.2-r0)\n"),
            "unknown action": at(6, "( 7/12) Frobbing zlib (1.3.2-r0)\n"),
            "wrong padding width": at(0, "(  1/12) Installing jansson (2.14.1-r0)\n"),
            "tab padding": at(0, "(\t1/12) Installing jansson (2.14.1-r0)\n"),
            "zero counter": at(0, "( 0/12) Installing jansson (2.14.1-r0)\n"),
            "out of order": at(1, "( 3/12) Installing zstd-libs (1.5.7-r2)\n"),
            "changing total": at(1, "( 2/13) Installing zstd-libs (1.5.7-r2)\n"),
            "missing parens": at(1, "( 2/12) Installing zstd-libs 1.5.7-r2\n"),
            "extra field": at(1, "( 2/12) Installing zstd-libs (1.5.7-r2) extra\n"),
            "double space": at(1, "( 2/12) Installing  zstd-libs (1.5.7-r2)\n"),
            "bad name": at(1, "( 2/12) Installing -zstd (1.5.7-r2)\n"),
            "bad version": at(1, "( 2/12) Installing zstd-libs (1.5.7)\n"),
            "duplicate package": at(1, "( 2/12) Installing jansson (2.14.1-r0)\n"),
            "truncated plan": "".join(ok[:-1]),
            "row beyond total": "".join(ok) + "(13/12) Installing extra (1-r0)\n",
            "uncounted action": "".join(ok) + "Upgrading musl (1.2.5-r23 -> 1.2.5-r24)\n",
            "malformed counter": at(1, "(2/x) Installing zstd-libs (1.5.7-r2)\n"),
            "paren line not a row": "".join(ok) + "(note) something\n",
            # Root's 90365e35 control: an indented unknown row appended to a valid plan
            "indented unknown appended": "".join(ok) + " (13/12) Frobbing zlib (1.3.2-r0)\n",
            "indented valid-looking row": at(1, " ( 2/12) Installing zstd-libs (1.5.7-r2)\n"),
            "tab-indented upgrade": "".join(ok) + "\t(13/12) Upgrading musl (1.2.5-r23 -> 1.2.5-r24)\n",
            "indented malformed counter": "".join(ok) + "  (x/12) Installing extra (1-r0)\n",
        }
        for name, text in cases.items():
            with self.subTest(name):
                r, rows = self.parse(text)
                self.assertNotEqual(r.returncode, 0, f"{name} accepted: {rows}")
                self.assertTrue((self.tmp / "out" / "RESULT").read_text().startswith("FAIL solver plan refused"))

    def test_padded_upgrade_never_reaches_install(self):
        g = GuestDependencyTests("test_fd0_closed_is_replaced_by_dev_null_for_steps")
        g.setUp()
        try:
            g.set_delta(g.delta)
            rows = (g.fake / "simulate").read_text().splitlines()
            n = len(g.delta)
            self.assertTrue(rows[0].startswith(f"({1:>{len(str(n))}}/{n}) "))  # modelled apk pads like the real log
            rows[0] = f"({1:>{len(str(n))}}/{n}) Upgrading musl (1.2.5-r23 -> 1.2.5-r24)"
            (g.fake / "simulate").write_text("\n".join(rows) + "\n")
            r = g.run_deps()
            self.assertNotEqual(r.returncode, 0)
            self.assertEqual(g.real_adds(), [])
            self.assertFalse([c for c in g.calls() if c.startswith("fetch ")])
        finally:
            g.tearDown()

    @unittest.skipUnless(os.environ.get("T10_APK_SIMULATE_LOG"), "private captured log not provided")
    def test_actual_captured_log_replay(self):
        """Root-only/private: the actual failed-phase simulate log (diagnostic only, not a PASS)."""
        log = Path(os.environ["T10_APK_SIMULATE_LOG"])
        self.assertEqual(hashlib.sha256(log.read_bytes()).hexdigest(),
                         "8f6f1f2e7004cdbfbdaa0c90645b8ccc85cb23b589b078a4c7a47dfc0ce7cfec")
        r, rows = self.parse(log.read_text())
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(rows), 47)
        for nv in ("binutils=2.45.1-r0", "jansson=2.14.1-r0", "zstd-libs=1.5.7-r2", "libunwind-dev=1.8.1-r0",
                   "musl-dev=1.2.5-r23", "openssl-dev=3.5.8-r0", "zlib-dev=1.3.2-r0"):
            self.assertIn(nv, rows)
        self.assertFalse([x for x in rows if x.split("=")[0] in ("musl", "libstdc++", "zlib", "libcrypto3", "libssl3")])
        # Root's control on the actual log: an appended indented unknown row must refuse
        r, rows = self.parse(log.read_text() + " (48/47) Frobbing zlib (1.3.2-r0)\n")
        self.assertNotEqual(r.returncode, 0, rows)
        self.assertIn("indented transaction row", (self.tmp / "out" / "apk-simulate.refused").read_text())


if __name__ == "__main__":
    unittest.main(verbosity=2)
