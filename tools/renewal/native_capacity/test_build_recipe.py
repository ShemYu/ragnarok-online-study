"""Focused tests for build_recipe.py against a FAKE Unix-socket Engine.

  python3 -I -B tools/renewal/native_capacity/test_build_recipe.py

No real Engine, VM, compiler or image is used. The fake implements only the
slim routes the recipe calls, so these prove request order, admission,
deadline/kill/cleanup and export/import validation logic -- not real guest
behavior, limit enforcement or a compiled binary.
"""

import base64
import hashlib
import http.server
import io
import json
from pathlib import Path
import shutil
import socketserver
import sys
import tarfile
import tempfile
import threading
import unittest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import build_recipe as br  # noqa: E402
import prepare_source as ps  # noqa: E402
from test_prepare_source import Fixture, PATCH_OK  # noqa: E402

BASE = "sha256:" + "ab" * 32


def fake_elf(marker):
    head = bytearray(64)
    head[:4] = b"\x7fELF"
    head[4], head[5] = 2, 1
    head[18:20] = br.EM_AARCH64.to_bytes(2, "little")
    return bytes(head) + b"npc/re/scripts_main.conf\0" + marker


def export_tar(tamper=None):
    files = {"RESULT": b"PASS\n", "toolchain.txt": b"gcc 15\n", "environment.txt": b"memory.max=1610612736\n",
             "apk-after.txt": b"libstdc++-15.2.0-r2\nmusl-1.2.5-r23\n"}
    for v, marker in (("unpatched", b""), ("patched", b"ros_ch1_coin_capacity\0")):
        files[f"{v}/map-server"] = fake_elf(marker)
        files[f"{v}/map-server.debug"] = b"dbg" + v.encode()
        files[f"{v}/BUILD_ID"] = hashlib.sha1(v.encode()).hexdigest().encode() + b"\n"
        files[f"{v}/interp.txt"] = b"  [Requesting program interpreter: /lib/ld-musl-aarch64.so.1]\n"
        files[f"{v}/dynamic.txt"] = b" 0x1 (NEEDED) Shared library: [libz.so.1]\n 0x1 (NEEDED) Shared library: [libunwind.so.8]\n"
    if tamper:
        tamper(files)
    sums = "".join(f"{hashlib.sha256(d).hexdigest()}  ./{k}\n" for k, d in sorted(files.items())
                   if k not in ("RESULT",))
    files.setdefault("SHA256SUMS", sums.encode())
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w") as t:
        for k, d in sorted(files.items()):
            info = tarfile.TarInfo("out/" + k)
            info.size = len(d)
            info.mode = 0o755 if k.endswith("/map-server") else 0o644
            t.addfile(info, io.BytesIO(d))
    return raw.getvalue()


class FakeEngine:
    def __init__(self, mode="ok", export=None, preexisting=False, import_mode=0o755):
        self.mode, self.export, self.import_mode = mode, export or export_tar(), import_mode
        self.containers, self.calls, self.polls = {}, [], 0
        if preexisting:
            self.containers["old"] = {"labels": {br.ROLE_LABEL: "compiler"}, "status": "exited"}
        self.dir = Path(tempfile.mkdtemp(prefix="fake-engine-", dir="/tmp"))
        self.sock = str(self.dir / "e.sock")
        engine = self

        class H(http.server.BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def address_string(self):
                return "unix"

            def log_message(self, *a):
                pass

            def reply(self, code, body=b"", ctype="application/json", headers=()):
                if isinstance(body, (dict, list)):
                    body = json.dumps(body).encode()
                self.send_response(code)
                self.send_header("Content-Type", ctype)
                for k, v in headers:
                    self.send_header(k, v)
                self.send_header("Content-Length", str(0 if self.command == "HEAD" else len(body)))
                self.end_headers()
                if self.command != "HEAD":
                    try:
                        self.wfile.write(body)
                    except BrokenPipeError:  # client already closed; fake-only race
                        pass

            def handle_any(self):
                n = int(self.headers.get("Content-Length") or 0)
                body = self.rfile.read(n) if n else b""
                path = self.path.removeprefix(br.API)
                engine.calls.append((self.command, path.split("?")[0]))
                self.reply(*engine.route(self.command, path, body))

            do_GET = do_POST = do_PUT = do_DELETE = do_HEAD = handle_any

        class S(socketserver.ThreadingMixIn, socketserver.UnixStreamServer):
            daemon_threads = True

        self.server = S(self.sock, H)
        threading.Thread(target=self.server.serve_forever, daemon=True).start()

    def route(self, m, path, body):
        p, _, q = path.partition("?")
        parts = p.strip("/").split("/")
        if m == "GET" and p == "/containers/json":
            return 200, [{"Id": k, "Labels": c["labels"]} for k, c in self.containers.items()]
        if m == "POST" and p == "/containers/create":
            req = json.loads(body)
            cid = "c%d" % len(self.containers)
            self.containers[cid] = {"labels": req.get("Labels", {}), "status": "created", "hc": req.get("HostConfig", {}),
                                    "uploaded": None}
            return 201, {"Id": cid}
        cid = parts[1] if len(parts) > 1 else ""
        c = self.containers.get(cid)
        if c is None:
            return 404, {"message": "no such container"}
        tail = parts[2] if len(parts) > 2 else ""
        if m == "GET" and tail == "json":
            if c["status"] == "running":
                self.polls += 1
                if self.mode in ("ok", "fail") and self.polls >= 2:
                    c["status"], c["exit"] = "exited", 0 if self.mode == "ok" else 1
            return 200, {"Config": {"Labels": c["labels"]}, "HostConfig": c.get("hc", {}),
                         "State": {"Running": c["status"] == "running", "Status": c["status"],
                                   "ExitCode": c.get("exit", 0)}}
        if m == "PUT" and tail == "archive":
            c["uploaded"] = body
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
                return 200, self.export, "application/x-tar"
            data = fake_elf(b"ros_ch1_coin_capacity\0")
            raw = io.BytesIO()
            with tarfile.open(fileobj=raw, mode="w") as t:
                info = tarfile.TarInfo("map-server-t10-010-patched")
                info.size, info.mode = len(data), self.import_mode
                t.addfile(info, io.BytesIO(data))
            stat = base64.b64encode(json.dumps({"mode": self.import_mode}).encode()).decode()
            return 200, raw.getvalue(), "application/x-tar", [("X-Docker-Container-Path-Stat", stat)]
        if m == "DELETE" and len(parts) == 2:
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
        self.t += max(s, 1000.0)


class RecipeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fx = Fixture({"0001-ok.patch": PATCH_OK})
        cls.fx.fetch()
        cls.fx.discover()
        ps.prepare(cls.fx.cache, cls.fx.out, cls.fx.manifest, "patch", pins={})

    @classmethod
    def tearDownClass(cls):
        cls.fx.close()

    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="t10-010-003-recipe-"))
        self.engines = []

    def tearDown(self):
        for e in self.engines:
            e.close()
        shutil.rmtree(self.tmp, ignore_errors=True)

    def engine(self, **kw):
        e = FakeEngine(**kw)
        self.engines.append(e)
        return e

    def plan(self, name="run", **kw):
        args = dict(mem_available=4 << 30, manifest=self.fx.manifest, pins={})
        args.update(kw)
        p = br.plan(self.fx.out, self.tmp / name, BASE, "1.2.5-r23", "15.2.0-r2", **args)
        path = self.tmp / name / "PLAN.json"
        return p, path, hashlib.sha256(path.read_bytes()).hexdigest()

    def test_plan_is_deterministic_and_bounded(self):
        p1, _, _ = self.plan("a")
        p2, _, _ = self.plan("b")
        self.assertEqual(p1["inputs"]["source_tar_gz_sha256"], p2["inputs"]["source_tar_gz_sha256"])
        self.assertEqual(p1["inputs"]["upload_tar_sha256"], p2["inputs"]["upload_tar_sha256"])
        hc = p1["create"]["HostConfig"]
        self.assertEqual((hc["Memory"], hc["MemorySwap"], hc["NanoCpus"]), (1536 << 20, 1536 << 20, 2 * 10**9))
        self.assertNotIn("PidsLimit", hc)
        with tarfile.open(self.tmp / "a" / "upload.tar") as t:
            self.assertEqual(sorted(t.getnames()), ["coin_capacity.patch", "guest_build.sh", "inputs.env",
                                                     "source.tar.gz"])

    def test_plan_refusals(self):
        for kw, text in ((dict(mem_available=1 << 30), "insufficient"), (dict(jobs=3), "jobs"),
                         (dict(step_timeout=10), "step timeout")):
            with self.subTest(text), self.assertRaises(br.RecipeError) as cm:
                self.plan("r-" + text, **kw)
            self.assertIn(text, str(cm.exception))
        with self.assertRaises(br.RecipeError):
            br.plan(self.fx.out, self.tmp / "tag", "alpine:3.23", "1.2.5-r23", "15.2.0-r2", 4 << 30,
                    manifest=self.fx.manifest, pins={})
        self.plan("dup")
        with self.assertRaises(br.RecipeError):
            self.plan("dup")
        (self.fx.out / "source" / "dirty").write_text("x")
        try:
            with self.assertRaises(ps.PrepError):
                self.plan("dirty")
        finally:
            (self.fx.out / "source" / "dirty").unlink()

    def test_execute_success_then_validate_and_import(self):
        e = self.engine()
        p, path, admit = self.plan()
        res = br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        self.assertEqual(res["exit_code"], 0)
        self.assertTrue(res["deleted"])
        self.assertEqual(e.containers, {})
        self.assertEqual([c for c in e.calls], [
            ("GET", "/containers/json"), ("POST", "/containers/create"), ("GET", "/containers/c0/json"),
            ("PUT", "/containers/c0/archive"), ("POST", "/containers/c0/start"), ("GET", "/containers/c0/json"),
            ("GET", "/containers/c0/json"), ("GET", "/containers/c0/logs"), ("GET", "/containers/c0/archive"),
            ("DELETE", "/containers/c0"), ("GET", "/containers/c0/json")])
        art = br.validate_export(path, self.tmp / "run" / "export.tar", self.tmp / "art")
        self.assertNotEqual(art["artifacts"]["patched"]["sha256"], art["artifacts"]["unpatched"]["sha256"])
        ctx = br.image_context(self.tmp / "art", "patched", BASE, self.tmp / "ctx")
        df = (self.tmp / "ctx" / "Dockerfile").read_text()
        self.assertEqual(df, f"FROM {BASE}\nCOPY map-server /rathena/map-server-t10-010-patched\n")
        self.assertNotIn("ARG", df)
        self.assertNotIn("RUN", df)
        imp = br.import_check(e.sock, "sha256:" + "cd" * 32, "patched", ctx["sha256"])
        self.assertTrue(imp["ok"], imp)
        with self.assertRaises(br.RecipeError):
            br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)  # plan consumed

    def test_import_mode_not_assumed(self):
        e = self.engine(import_mode=0o644)
        data = fake_elf(b"ros_ch1_coin_capacity\0")
        imp = br.import_check(e.sock, "sha256:" + "cd" * 32, "patched", hashlib.sha256(data).hexdigest())
        self.assertFalse(imp["ok"])
        self.assertEqual(e.containers, {})

    def test_admission_token_required(self):
        e = self.engine()
        _, path, _ = self.plan()
        with self.assertRaises(br.RecipeError):
            br.execute(path, e.sock, "0" * 64)
        self.assertEqual(e.calls, [])

    def test_single_owner_refusal(self):
        e = self.engine(preexisting=True)
        _, path, admit = self.plan()
        with self.assertRaises(br.RecipeError) as cm:
            br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        self.assertIn("single-owner", str(cm.exception))
        self.assertEqual(e.calls, [("GET", "/containers/json")])
        self.assertEqual(list(e.containers), ["old"])  # foreign object untouched

    def test_deadline_kills_and_deletes(self):
        e = self.engine(mode="hang")
        _, path, admit = self.plan(deadline=600, step_timeout=300)
        clock = Clock()
        with self.assertRaises(br.RecipeError) as cm:
            br.execute(path, e.sock, admit, poll=1, now=clock.now, sleep=clock.sleep)
        self.assertIn("deadline", str(cm.exception))
        self.assertIn(("POST", "/containers/c0/kill"), e.calls)
        self.assertEqual(e.containers, {})
        rec = json.loads((self.tmp / "run" / "EXECUTION.json").read_text())
        self.assertTrue(rec["timed_out"] and rec["deleted"])

    def test_guest_failure_still_cleans_up(self):
        e = self.engine(mode="fail")
        _, path, admit = self.plan()
        with self.assertRaises(br.RecipeError) as cm:
            br.execute(path, e.sock, admit, poll=0, sleep=lambda s: None)
        self.assertIn("exit=1", str(cm.exception))
        self.assertEqual(e.containers, {})
        self.assertTrue((self.tmp / "run" / "container.log").exists())

    def test_upload_tamper_refused(self):
        e = self.engine()
        _, path, admit = self.plan()
        with open(self.tmp / "run" / "upload.tar", "ab") as fh:
            fh.write(b"x")
        with self.assertRaises(br.RecipeError):
            br.execute(path, e.sock, admit)
        self.assertEqual(e.calls, [])

    def test_export_validation_failures(self):
        _, path, _ = self.plan()

        def wrong_machine(f):
            b = bytearray(f["patched/map-server"])
            b[18:20] = (62).to_bytes(2, "little")
            f["patched/map-server"] = bytes(b)

        cases = {
            "hash": lambda f: f.__setitem__("SHA256SUMS", b"0" * 64 + b"  ./toolchain.txt\n"),
            "machine": wrong_machine,
            "builtin-in-unpatched": lambda f: f.__setitem__("unpatched/map-server", fake_elf(b"ros_ch1_coin_capacity")),
            "pre-re": lambda f: f.__setitem__("patched/map-server", fake_elf(b"ros_ch1_coin_capacity npc/pre-re/scripts_main.conf")),
            "abi": lambda f: f.__setitem__("apk-after.txt", b"musl-1.2.5-r24\nlibstdc++-15.2.0-r2\n"),
            "result": lambda f: f.__setitem__("RESULT", b"FAIL patched-make-map\n"),
            "interp": lambda f: f.__setitem__("patched/interp.txt", b"/lib/ld-linux-aarch64.so.1\n"),
        }
        for name, tamper in cases.items():
            with self.subTest(name):
                tar = self.tmp / f"{name}.tar"
                tar.write_bytes(export_tar(tamper))
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


class GuestScriptTests(unittest.TestCase):
    def test_guest_script_syntax_and_contract(self):
        import subprocess
        self.assertEqual(subprocess.run(["sh", "-n", str(br.GUEST)]).returncode, 0)
        s = br.GUEST.read_text()
        for needle in ('CXXFLAGS="-g -O2 -fno-omit-frame-pointer -fno-optimize-sibling-calls"',
                       'CPPFLAGS="-DRAGNAROK_CRASH_TRACE"', 'LIBS="-lunwind"',
                       'LDFLAGS="-Wl,--build-id=sha1 -rdynamic"', "--enable-packetver=\"$PACKETVER\"",
                       "make -j\"$JOBS\" map", "-F 0", "npc/pre-re/scripts_main.conf", "musl-$EXPECT_MUSL"):
            self.assertIn(needle, s)
        app_df = None
        for c in (HERE.parents[2] / ".tools").glob("*/prepared/source/Dockerfile.ragnarokmac"):
            app_df = c.read_text()
            break
        if app_df:  # flags must match the app's pinned Dockerfile when a prepared tree is present
            for flag in ("-g -O2 -fno-omit-frame-pointer -fno-optimize-sibling-calls", "-DRAGNAROK_CRASH_TRACE",
                         "-lunwind", "-Wl,--build-id=sha1 -rdynamic", "libunwind-dev~1.8.1"):
                self.assertIn(flag, app_df)


if __name__ == "__main__":
    unittest.main(verbosity=2)
