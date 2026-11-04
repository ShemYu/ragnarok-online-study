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

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_recipe as br  # noqa: E402
import prepare_source as ps  # noqa: E402
from test_prepare_source import Fixture, PATCH_OK  # noqa: E402

BASE = "sha256:" + "ab" * 32
LOCK = "".join(f"{n}={v}\n" for n, v in sorted({
    "bash": "5.3-r0", "binutils": "2.45-r0", "cmake": "4.1.2-r0", "g++": "15.2.0-r2", "gcc": "15.2.0-r2",
    "git": "2.52.0-r0", "libunwind-dev": "1.8.1-r0", "linux-headers": "6.16-r0", "make": "4.4.1-r3",
    "mariadb-dev": "11.8.3-r0", "patch": "2.8-r0", "zlib-dev": "1.3.1-r2"}.items()))
APK_BEFORE = ["libstdc++-15.2.0-r2", "musl-1.2.5-r23"]


def fake_elf(marker):
    head = bytearray(64)
    head[:4] = b"\x7fELF"
    head[4], head[5] = 2, 1
    head[18:20] = br.EM_AARCH64.to_bytes(2, "little")
    return bytes(head) + b"npc/re/scripts_main.conf\0" + marker


def export_tar(plan, cid, tamper=None, owner=(0, 0)):
    cg = plan["expected_cgroup"]
    locked = sorted(x.replace("=", "-", 1) for x in plan["inputs"]["apk_lock"] or [])
    files = {"RESULT": b"PASS\n", "toolchain.txt": b"gcc 15\n", "environment.txt": b"nproc=4\n",
             "apk-before.txt": "\n".join(APK_BEFORE).encode() + b"\n",
             "apk-after.txt": "\n".join(sorted(APK_BEFORE + locked)).encode() + b"\n",
             "cgroup.txt": ("".join(f"{k}={v}\n" for k, v in cg.items()) + f"id={cid}\n").encode(),
             "logs/steps.log": b"x PASS\n"}
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


class RecipeTests(unittest.TestCase):
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
                    manifest=self.fx.manifest, pins={})
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
            self.assertEqual(sorted(t.getnames()), ["apk.lock", "coin_capacity.patch", "crash_verify.sh",
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
        with self.assertRaises(br.RecipeError) as cm:
            self.plan("nolock", apk_lock=None)
        self.assertIn("requires an explicit", str(cm.exception))
        for bad in ("gcc\n", LOCK.replace("libunwind-dev=1.8.1-r0", "libunwind-dev=1.9.0-r0"),
                    LOCK.replace("patch=2.8-r0\n", ""), "zz=1-r0\n" + LOCK, LOCK + LOCK.splitlines()[0] + "\n"):
            self.lock.write_text(bad)
            with self.subTest(bad[:20]), self.assertRaises(br.RecipeError):
                self.plan("badlock")
        p, _, _ = self.plan("resolve", mode="resolve")
        self.assertIsNone(p["inputs"]["apk_lock"])
        with self.assertRaises(br.RecipeError):
            self.plan("resolve2", mode="resolve", apk_lock=self.lock)

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
        self.assertLess(s.index("check_cgroup\n"), s.index("step apk-"))  # every check precedes install


if __name__ == "__main__":
    unittest.main(verbosity=2)
