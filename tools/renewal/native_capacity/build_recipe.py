"""Bounded Linux/arm64 map-server build/export recipe (T10.010.003).

Root executes this in T10.010.004; this task only implements and tests it.

  plan            verify a prepared tree, write deterministic inputs and PLAN.json
                  (no Engine contact)
  execute         ONE owned compiler container through the slim Engine API:
                  census -> create -> PUT inputs -> start -> poll (deadline) ->
                  [kill] -> GET /work/out -> delete -> absence check
  validate-export check the exported artifact offline
  image-context   minimal no-ARG/no-RUN single-file COPY context for import
  import-check    create (never start) a container from an image, read back the
                  imported file's bytes and mode, delete it

Engine route, from pinned slim source (nebula 2e9cf43, slimd router/archive):
only containers create/json/start/kill/archive GET+PUT/logs/DELETE and
containers/json are used. No /build, commit or image save (501), no /wait
(an HTTP disconnect does not cancel it), no exec, no pull. PUT archive bodies
are buffered whole in Engine memory (2 GiB cap) and are not decompressed, so
the upload is a small wrapper tar holding source.tar.gz. Archive PUT
preserves modes; GET works on stopped containers. Requested HostConfig
limits are echoed by the API but enforcement must be read back in the guest
(environment.txt) -- PidsLimit is not advertised by the current Engine.
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
import socket
import sys
import tarfile
import time
import uuid

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import prepare_source as ps  # noqa: E402

GUEST = HERE / "build" / "guest_build.sh"
PATCH = HERE / "coin_capacity.patch"
API = "/v1.43"
ROLE_LABEL = "t10.010.003.role"
RUN_LABEL = "t10.010.003.run"
MIB = 1 << 20
EM_AARCH64 = 183


class RecipeError(Exception):
    pass


def sha256(b):
    return hashlib.sha256(b).hexdigest()


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
    """Upload body for PUT archive at /work/in: name -> (bytes, mode)."""
    raw = io.BytesIO()
    with tarfile.open(fileobj=raw, mode="w", format=tarfile.USTAR_FORMAT) as tar:
        for name in sorted(members):
            data, mode = members[name]
            info = tarfile.TarInfo(name)
            info.size, info.mode, info.mtime = len(data), mode, 0
            tar.addfile(info, io.BytesIO(data))
    return raw.getvalue()


def plan(prepared, rundir, base_image, expect_musl, expect_libstdcxx, mem_available, memory_mib=1536,
         cpus=2, jobs=1, step_timeout=3600, deadline=4 * 3600, reserve_mib=768, packetver="20221005",
         manifest=None, pins=None):
    manifest = manifest or ps.load_manifest(ps.MANIFEST)
    if not re.fullmatch(r"sha256:[0-9a-f]{64}", base_image):
        raise RecipeError("base image must be an immutable local image ID sha256:<64 hex>")
    if not re.fullmatch(r"\d{8}", packetver):
        raise RecipeError("bad packet version")
    need = (memory_mib + reserve_mib) * MIB
    if mem_available is None or mem_available < need:
        raise RecipeError(f"insufficient fresh MemAvailable {mem_available} < limit+reserve {need}")
    if jobs < 1 or jobs > cpus:
        raise RecipeError("jobs must be within 1..cpus")
    if not 60 <= step_timeout <= deadline:
        raise RecipeError("step timeout must be within 60s..deadline")
    rundir = Path(rundir).resolve()
    if rundir.exists():
        raise RecipeError(f"{rundir} exists; refuse to reuse run state")
    ver = ps.verify(Path(prepared), manifest, pins=pins)
    rec = json.loads((Path(prepared) / ps.MARKER).read_text())
    src = deterministic_tar_gz(Path(prepared) / "source", mtime=1760000000)
    patch = PATCH.read_bytes()
    guest = GUEST.read_bytes()
    env = (f"SOURCE_SHA256={sha256(src)}\nPATCH_SHA256={sha256(patch)}\nPACKETVER={packetver}\n"
           f"JOBS={jobs}\nSTEP_TIMEOUT={step_timeout}\nEXPECT_MUSL={expect_musl}\n"
           f"EXPECT_LIBSTDCXX={expect_libstdcxx}\nEXPECT_ARCH=aarch64\n").encode()
    for v in (expect_musl, expect_libstdcxx):
        if not re.fullmatch(r"[0-9][0-9A-Za-z._-]*-r\d+", v):
            raise RecipeError(f"bad apk version {v}")
    upload = wrapper_tar({"source.tar.gz": (src, 0o644), "coin_capacity.patch": (patch, 0o644),
                          "guest_build.sh": (guest, 0o755), "inputs.env": (env, 0o644)})
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
            "Memory": memory_mib * MIB,
            "MemorySwap": memory_mib * MIB,
            "NanoCpus": cpus * 10**9,
            "AutoRemove": False,
            "RestartPolicy": {"Name": "no"},
            "Binds": ["/sys/fs/cgroup/slim:/run/root-cgroup-view:ro"],
        },
    }
    rundir.mkdir(parents=True)
    (rundir / "upload.tar").write_bytes(upload)
    p = {
        "schema": "t10.010.003/build-plan/v1",
        "run_id": run_id,
        "container_name": f"t10-010-003-build-{run_id}",
        "prepared": {"tree_sha256": ver["prepared_tree_sha256"], "files": ver["files"],
                     "identity": rec["identity"]},
        "inputs": {"source_tar_gz_sha256": sha256(src), "source_tar_gz_bytes": len(src),
                   "coin_capacity_patch_sha256": sha256(patch), "guest_build_sh_sha256": sha256(guest),
                   "inputs_env": env.decode(), "upload_tar_sha256": sha256(upload),
                   "upload_tar_bytes": len(upload)},
        "packetver": packetver,
        "abi_expect": {"musl": expect_musl, "libstdc++": expect_libstdcxx, "arch": "aarch64"},
        "limits": {"memory_bytes": memory_mib * MIB, "memory_swap_bytes": memory_mib * MIB,
                   "nano_cpus": cpus * 10**9, "jobs": jobs, "step_timeout_s": step_timeout,
                   "deadline_s": deadline, "mem_available_at_plan": mem_available,
                   "reserve_bytes": reserve_mib * MIB, "pids_limit": "not advertised; not requested"},
        "create": create,
        "requests": [
            "GET /containers/json?all=1 (census; refuse any existing compiler role)",
            "POST /containers/create?name=<container_name>",
            "PUT /containers/<id>/archive?path=/work/in (upload.tar)",
            "POST /containers/<id>/start",
            "GET /containers/<id>/json (poll until exited or deadline)",
            "POST /containers/<id>/kill (deadline only)",
            "GET /containers/<id>/logs?stdout=1&stderr=1",
            "GET /containers/<id>/archive?path=/work/out",
            "DELETE /containers/<id>?force=1",
            "GET /containers/<id>/json (expect 404)",
        ],
        "network": "default container networking is required for apk add; no offline package set is pinned",
    }
    (rundir / "PLAN.json").write_text(json.dumps(p, indent=1, sort_keys=True) + "\n")
    return p


# ------------------------------------------------------------------ engine
class UnixHTTPConnection(http.client.HTTPConnection):
    def __init__(self, path, timeout):
        super().__init__("localhost", timeout=timeout)
        self.unix_path = path

    def connect(self):
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.settimeout(self.timeout)
        self.sock.connect(self.unix_path)


class Engine:
    def __init__(self, sock, timeout=120):
        self.sock, self.timeout, self.log = sock, timeout, []

    def call(self, method, path, body=None, ctype="application/json", ok=(200, 201, 204)):
        conn = UnixHTTPConnection(self.sock, self.timeout)
        try:
            data = json.dumps(body).encode() if isinstance(body, (dict, list)) else body
            headers = {"Content-Type": ctype} if data is not None else {}
            conn.request(method, API + path, body=data, headers=headers)
            r = conn.getresponse()
            payload = r.read()
            self.log.append({"method": method, "path": path, "status": r.status, "bytes": len(payload),
                             "sha256": sha256(payload)})
            if ok is not None and r.status not in ok:
                raise RecipeError(f"{method} {path}: HTTP {r.status} {payload[:300]!r}")
            return r.status, dict(r.getheaders()), payload
        finally:
            conn.close()


def census(engine):
    _, _, body = engine.call("GET", "/containers/json?all=1")
    return [c for c in json.loads(body) if (c.get("Labels") or {}).get(ROLE_LABEL) == "compiler"]


def execute(plan_path, sock, admit, poll=5.0, now=time.monotonic, sleep=time.sleep):
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
    e = Engine(sock)
    res = {"run_id": p["run_id"], "started": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())}
    (rundir / "EXECUTION.json").write_text(json.dumps({"state": "admitted", **res}) + "\n")
    existing = census(e)
    if existing:
        raise RecipeError(f"single-owner admission: compiler container(s) already exist {[c.get('Id') for c in existing]}")
    cid = None
    try:
        _, _, body = e.call("POST", f"/containers/create?name={p['container_name']}", p["create"])
        cid = json.loads(body)["Id"]
        res["container_id"] = cid
        _, _, body = e.call("GET", f"/containers/{cid}/json")
        info = json.loads(body)
        if (info.get("Config", {}).get("Labels") or {}).get(RUN_LABEL) != p["run_id"]:
            raise RecipeError("created container does not carry this run label")
        res["echoed_host_config"] = {k: info.get("HostConfig", {}).get(k) for k in ("Memory", "MemorySwap", "NanoCpus")}
        e.call("PUT", f"/containers/{cid}/archive?path=/work/in", upload, ctype="application/x-tar")
        e.call("POST", f"/containers/{cid}/start")
        t0 = now()
        res["timed_out"] = False
        while True:
            _, _, body = e.call("GET", f"/containers/{cid}/json")
            st = json.loads(body).get("State", {})
            if not st.get("Running") and st.get("Status") in ("exited", "dead"):
                res["exit_code"] = st.get("ExitCode")
                break
            if now() - t0 > p["limits"]["deadline_s"]:
                res["timed_out"] = True
                e.call("POST", f"/containers/{cid}/kill", ok=(204, 404, 409))
                for _ in range(12):
                    _, _, body = e.call("GET", f"/containers/{cid}/json")
                    if not json.loads(body).get("State", {}).get("Running"):
                        break
                    sleep(poll)
                break
            sleep(poll)
        res["elapsed_s"] = round(now() - t0, 1)
        _, _, logs = e.call("GET", f"/containers/{cid}/logs?stdout=1&stderr=1", ok=(200,))
        (rundir / "container.log").write_bytes(logs)
        st, _, tarb = e.call("GET", f"/containers/{cid}/archive?path=/work/out", ok=(200, 404))
        if st == 200:
            (rundir / "export.tar").write_bytes(tarb)
            res["export_sha256"] = sha256(tarb)
    finally:
        if cid:
            try:
                e.call("DELETE", f"/containers/{cid}?force=1", ok=(204, 404))
                st, _, _ = e.call("GET", f"/containers/{cid}/json", ok=(404,))
                res["deleted"] = st == 404
            except (RecipeError, OSError) as exc:
                res["deleted"] = False
                res["cleanup_error"] = str(exc)
        res["requests"] = e.log
        (rundir / "EXECUTION.json").write_text(json.dumps({"state": "finished", **res}, indent=1) + "\n")
    if res.get("timed_out"):
        raise RecipeError("deadline exceeded; container killed and deleted")
    if res.get("exit_code") != 0:
        raise RecipeError(f"guest build failed exit={res.get('exit_code')}; see container.log")
    if not res.get("deleted"):
        raise RecipeError("owned container cleanup unresolved")
    return res


# ------------------------------------------------------------------ export
def safe_extract(tarb, dest):
    dest = Path(dest).resolve()
    if dest.exists():
        raise RecipeError(f"{dest} exists")
    dest.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(tarb)) as tar:
        for m in tar.getmembers():
            target = (dest / m.name).resolve()
            if not str(target).startswith(str(dest) + os.sep) or not (m.isfile() or m.isdir()):
                raise RecipeError(f"unsafe export member {m.name}")
            if m.isdir():
                target.mkdir(parents=True, exist_ok=True)
            else:
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(tar.extractfile(m).read())
                os.chmod(target, m.mode & 0o777)
    return dest


def elf_machine(data):
    if data[:4] != b"\x7fELF" or data[4] != 2 or data[5] != 1:
        return None
    return int.from_bytes(data[18:20], "little")


def validate_export(plan_path, export_tar, dest):
    p = json.loads(Path(plan_path).read_text())
    out = safe_extract(Path(export_tar).read_bytes(), dest) / "out"
    if (out / "RESULT").read_text().strip() != "PASS":
        raise RecipeError(f"guest RESULT: {(out / 'RESULT').read_text().strip()}")
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
    art = {}
    for v in ("unpatched", "patched"):
        b = out / v / "map-server"
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
        art[v] = {"sha256": sha256(data), "bytes": len(data), "build_id": (out / v / "BUILD_ID").read_text().strip(),
                  "needed": sorted(re.findall(r"\[(.+?)\]", (out / v / "dynamic.txt").read_text())),
                  "debug_sha256": sha256((out / v / "map-server.debug").read_bytes())}
    if art["unpatched"]["needed"] != art["patched"]["needed"]:
        raise RecipeError("variants link different libraries")
    if art["unpatched"]["sha256"] == art["patched"]["sha256"]:
        raise RecipeError("variants are identical")
    apk = (out / "apk-after.txt").read_text().split()
    for name, want in (("musl", p["abi_expect"]["musl"]), ("libstdc++", p["abi_expect"]["libstdc++"])):
        if f"{name}-{want}" not in apk:
            raise RecipeError(f"{name} != {want}")
    result = {"schema": "t10.010.003/artifacts/v1", "run_id": p["run_id"], "artifacts": art,
              "toolchain": (out / "toolchain.txt").read_text().splitlines(),
              "environment": (out / "environment.txt").read_text().splitlines(),
              "prepared_tree_sha256": p["prepared"]["tree_sha256"]}
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
    src = Path(artifacts_dir) / "out" / variant / "map-server"
    data = src.read_bytes()
    (dest / "map-server").write_bytes(data)
    os.chmod(dest / "map-server", 0o755)
    target = IMPORT_DEST.format(variant=variant)
    (dest / "Dockerfile").write_text(f"FROM {base_image}\nCOPY map-server {target}\n")
    return {"target": target, "sha256": sha256(data), "dockerfile_sha256": sha256((dest / "Dockerfile").read_bytes())}


def import_check(sock, image, variant, expect_sha256):
    """Create (not start) a container, HEAD+GET the imported file, delete it."""
    e = Engine(sock)
    target = IMPORT_DEST.format(variant=variant)
    _, _, body = e.call("POST", f"/containers/create?name=t10-010-003-import-{uuid.uuid4().hex[:8]}",
                        {"Image": image, "Entrypoint": ["/bin/true"], "Labels": {ROLE_LABEL: "import-check"}})
    cid = json.loads(body)["Id"]
    try:
        _, hdr, _ = e.call("HEAD", f"/containers/{cid}/archive?path={target}", ok=(200,))
        stat = json.loads(base64.b64decode(hdr.get("X-Docker-Container-Path-Stat", "")))
        _, _, tarb = e.call("GET", f"/containers/{cid}/archive?path={target}", ok=(200,))
        with tarfile.open(fileobj=io.BytesIO(tarb)) as tar:
            members = [m for m in tar.getmembers() if m.isfile()]
            if len(members) != 1:
                raise RecipeError("import archive must hold exactly one file")
            data = tar.extractfile(members[0]).read()
            mode = members[0].mode & 0o777
    finally:
        e.call("DELETE", f"/containers/{cid}?force=1", ok=(204, 404))
        e.call("GET", f"/containers/{cid}/json", ok=(404,))
    ok = sha256(data) == expect_sha256 and mode == 0o755 and (stat.get("mode", 0) & 0o777) == 0o755
    return {"sha256": sha256(data), "tar_mode": oct(mode), "stat_mode": oct(stat.get("mode", 0) & 0o7777),
            "ok": ok, "requests": e.log}


def main(argv=None):
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("plan")
    a.add_argument("--prepared", required=True, type=Path)
    a.add_argument("--rundir", required=True, type=Path)
    a.add_argument("--base-image", required=True)
    a.add_argument("--expect-musl", required=True)
    a.add_argument("--expect-libstdcxx", required=True)
    a.add_argument("--mem-available-bytes", required=True, type=int)
    a.add_argument("--memory-mib", type=int, default=1536)
    a.add_argument("--cpus", type=int, default=2)
    a.add_argument("--jobs", type=int, default=1)
    a.add_argument("--step-timeout", type=int, default=3600)
    a.add_argument("--deadline", type=int, default=4 * 3600)
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
    o = ap.parse_args(argv)
    try:
        if o.cmd == "plan":
            r = plan(o.prepared, o.rundir, o.base_image, o.expect_musl, o.expect_libstdcxx, o.mem_available_bytes,
                     o.memory_mib, o.cpus, o.jobs, o.step_timeout, o.deadline)
            r = {"run_id": r["run_id"], "inputs": r["inputs"], "limits": r["limits"],
                 "admit": sha256((o.rundir / "PLAN.json").read_bytes())}
        elif o.cmd == "execute":
            r = execute(o.plan, o.engine_socket, o.admit)
            r.pop("requests", None)
        elif o.cmd == "validate-export":
            r = validate_export(o.plan, o.export, o.dest)
        elif o.cmd == "image-context":
            r = image_context(o.artifacts, o.variant, o.base_image, o.dest)
        else:
            r = import_check(o.engine_socket, o.image, o.variant, o.expect_sha256)
            r.pop("requests", None)
            if not r["ok"]:
                print("FAIL", json.dumps(r, sort_keys=True))
                return 1
    except (RecipeError, ps.PrepError, OSError, KeyError, ValueError) as exc:
        print("FAIL", exc)
        return 1
    print("OK", json.dumps(r, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
