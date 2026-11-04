"""Reproducible full map-server source preparation (T10.010.003).

Reconstructs pinned rAthena plus the app's ordered server overlays/transforms
from public repositories into a fresh owned directory, then verifies the
whole prepared tree against source_manifest.json and the nine native-capacity
pins in test_coin_capacity.py.

  python3 -I -B prepare_source.py fetch   --cache C
  python3 -I -B prepare_source.py prepare --cache C --out O [--patch-engine patch|git-apply]
  python3 -I -B prepare_source.py verify  --out O
  python3 -I -B prepare_source.py reference --cache C --out R

`fetch` downloads exactly one commit per repository into owned bare caches and
checks commit and tree identity. `prepare` refuses an existing output or any
leftover staging directory, builds in a sibling staging directory, verifies the
nine pins and the full-tree digest, writes PREPARED.json last and renames the
staging directory into place. `verify` recomputes the digest of a prepared
output, reporting dirty/partial state. `reference` runs the app's own
scripts/apply-server-mods.sh on a fresh export as a semantics cross-check.

No network access except `git fetch` of the pinned commits; no Engine, VM,
app, saves or shared canonical source are read or written.
"""

import argparse
import fnmatch
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
MANIFEST = HERE / "source_manifest.json"
MARKER = "PREPARED.json"
STAGING = ".staging-"
DIAG = re.compile(r"fuzz|fail|reject|reversed|ignor|malformed|already applied|skipp", re.I)


class PrepError(Exception):
    pass


def git(*args, cwd=None, env=None, timeout=900):
    e = dict(os.environ if env is None else env)
    e.setdefault("GIT_TERMINAL_PROMPT", "0")
    r = subprocess.run(["git", "-c", "core.autocrlf=false", "-c", "core.eol=lf", *args],
                       cwd=cwd, env=e, capture_output=True, text=True, timeout=timeout)
    if r.returncode:
        raise PrepError(f"git {' '.join(args[:3])}: {r.stderr.strip()[:500]}")
    return r.stdout.strip()


def load_manifest(path):
    m = json.loads(Path(path).read_text())
    if m.get("schema") != "t10.010.003/source-manifest/v1":
        raise PrepError("unknown manifest schema")
    for name, repo in m["repositories"].items():
        if not re.fullmatch(r"[0-9a-f]{40}", repo["commit"]) or not re.fullmatch(r"[0-9a-f]{40}", repo["tree"]):
            raise PrepError(f"manifest pin for {name} is not a full SHA-1")
    return m


def load_pins():
    sys.path.insert(0, str(HERE))
    try:
        import test_coin_capacity  # the existing oracle's pin table, read-only
    finally:
        sys.path.pop(0)
    return test_coin_capacity.PINS


# ---------------------------------------------------------------- fetch
def fetch(cache, manifest):
    cache.mkdir(parents=True, exist_ok=True)
    out = {}
    for name, repo in manifest["repositories"].items():
        bare = cache / f"{name}.git"
        if not bare.exists():
            git("init", "-q", "--bare", str(bare))
        sha = repo["commit"]
        have = subprocess.run(["git", "--git-dir", str(bare), "cat-file", "-t", sha],
                              capture_output=True, text=True).stdout.strip()
        if have != "commit":
            git("--git-dir", str(bare), "-c", "transfer.fsckObjects=true", "fetch", "-q", "--depth", "1",
                "--no-tags", repo["url"], sha)
            if git("--git-dir", str(bare), "rev-parse", "FETCH_HEAD") != sha:
                raise PrepError(f"{name}: fetched head is not the pinned commit")
        out[name] = check_identity(bare, name, repo)
        alt = repo.get("app_vendor_pin_url")
        if alt:
            # The app's own VENDOR_PINS names a different URL for this commit.
            # Fetch it independently and require the same commit and tree.
            alt_bare = cache / f"{name}-vendorpin.git"
            if not alt_bare.exists():
                git("init", "-q", "--bare", str(alt_bare))
                git("--git-dir", str(alt_bare), "-c", "transfer.fsckObjects=true", "fetch", "-q",
                    "--depth", "1", "--no-tags", alt, sha)
            out[name]["app_vendor_pin_url"] = check_identity(alt_bare, name, repo) == out[name]
            if not out[name]["app_vendor_pin_url"]:
                raise PrepError(f"{name}: vendor-pin URL disagrees")
    return out


def check_identity(bare, name, repo):
    sha = repo["commit"]
    if subprocess.run(["git", "--git-dir", str(bare), "cat-file", "-t", sha],
                      capture_output=True, text=True).stdout.strip() != "commit":
        raise PrepError(f"{name}: pinned commit {sha} absent from cache (bad revision)")
    tree = git("--git-dir", str(bare), "rev-parse", f"{sha}^{{tree}}")
    if tree != repo["tree"]:
        raise PrepError(f"{name}: tree {tree} != pinned {repo['tree']}")
    return {"commit": sha, "tree": tree}


def export(bare, sha, dest):
    """Checkout-equivalent export: honours .gitattributes eol rules like the
    app's `git checkout` of vendor/rathena, without a .git directory."""
    dest.mkdir(parents=True)
    idx = Path(tempfile.mkdtemp(prefix="t10-010-003-idx-")) / "index"
    try:
        env = dict(os.environ, GIT_INDEX_FILE=str(idx))
        git("--git-dir", str(bare), "--work-tree", str(dest), "read-tree", sha, env=env)
        git("--git-dir", str(bare), "--work-tree", str(dest), "checkout-index", "-a", "-f", env=env)
    finally:
        shutil.rmtree(idx.parent, ignore_errors=True)


# ---------------------------------------------------------------- digest
def tree_listing(root):
    rows = []
    root = Path(root)
    if root.is_symlink() or not root.is_dir():
        raise PrepError(f"{root} is not a real directory")
    for dirpath, dirnames, filenames in os.walk(root):
        for d in dirnames:
            if (Path(dirpath) / d).is_symlink():
                # os.walk does not descend into it, so it would otherwise go unseen
                raise PrepError(f"unexpected directory symlink {(Path(dirpath) / d).relative_to(root).as_posix()}")
        dirnames.sort()
        for fn in filenames:
            p = Path(dirpath) / fn
            rel = p.relative_to(root).as_posix()
            if p.is_symlink():
                raise PrepError(f"unexpected symlink {rel}")
            if not p.is_file():
                raise PrepError(f"unexpected non-regular entry {rel}")
            data = p.read_bytes()
            ex = "755" if os.stat(p).st_mode & 0o100 else "644"
            rows.append((rel, ex, hashlib.sha256(data).hexdigest(), len(data)))
    rows.sort(key=lambda r: r[0].encode())
    return rows


def digest(rows):
    h = hashlib.sha256()
    for rel, ex, sha, _ in rows:
        h.update(f"{ex}\t{sha}\t{rel}\n".encode())
    return h.hexdigest()


def check_pins(tree, pins):
    for rel, (size, sha) in pins.items():
        p = tree / rel
        if not p.is_file():
            raise PrepError(f"pin {rel}: missing")
        data = p.read_bytes()
        if len(data) != size or hashlib.sha256(data).hexdigest() != sha:
            raise PrepError(f"pin {rel}: size/sha256 mismatch")
    return len(pins)


# ---------------------------------------------------------------- steps
def sorted_glob(app, pattern):
    d, pat = pattern.rsplit("/", 1)
    names = sorted((n for n in os.listdir(app / d) if fnmatch.fnmatchcase(n, pat)), key=str.encode)
    return [app / d / n for n in names]


def run_checked(cmd, cwd=None, env=None, timeout=300):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True, timeout=timeout)
    return r.returncode, r.stdout + r.stderr


def apply_patch(tree, patch_file, engine, allow=None):
    """Apply one series patch. Zero fuzz is required unless the manifest
    allowlists this exact patch; then the zero-fuzz attempt must fail (else
    the allowlist is stale), the bounded fuzz is used and the touched file's
    resulting SHA-256 must equal the pinned value."""
    fuzz = allow["fuzz"] if allow else 0
    if engine == "patch":
        base = ["patch", "-p1", "--forward", "-s", "--no-backup-if-mismatch", "-r", "-",
                "-d", str(tree), "-i", str(patch_file)]
        if allow:
            rc0, _ = run_checked(base[:1] + ["--dry-run", "-F", "0"] + base[1:])
            if rc0 == 0:
                raise PrepError(f"stale fuzz allowlist: {patch_file.name} applies with zero fuzz")
        cmd, env = base[:1] + ["-F", str(fuzz)] + base[1:], None
    else:
        ctx = 3 - fuzz
        # Outside any repository: the ceiling stops discovery of the project repo.
        cmd = ["git", "apply", "-p1", f"-C{ctx}", "--whitespace=nowarn", "-v", str(patch_file)]
        env = dict(os.environ, GIT_CEILING_DIRECTORIES=str(tree.parent))
        if allow:
            rc0, _ = run_checked(["git", "apply", "--check", "-p1", str(patch_file)], cwd=tree, env=env)
            if rc0 == 0:
                raise PrepError(f"stale fuzz allowlist: {patch_file.name} applies with full context")
    rc, out = run_checked(cmd, cwd=tree, env=env)
    offsets = len(re.findall(r"\(offset -?\d+ lines?\)", out))
    if engine == "git-apply":
        out = "\n".join(l for l in out.splitlines()
                        if l.strip() and not re.match(
                            r"^(Checking patch |Applied patch .* cleanly\.|Applying patch |"
                            r"Hunk #\d+ succeeded at \d+ \(offset -?\d+ lines?\)\.)", l))
    rejects = list(tree.rglob("*.rej")) + list(tree.rglob("*.orig"))
    if rc or rejects or DIAG.search(out):
        raise PrepError(f"patch {patch_file.name} not clean (engine={engine} rc={rc} "
                        f"side_files={len(rejects)}): {out.strip()[:800]}")
    if allow:
        got = hashlib.sha256((tree / allow["file"]).read_bytes()).hexdigest()
        if got != allow["sha256_after"]:
            raise PrepError(f"fuzzed {patch_file.name}: {allow['file']} sha256 {got} != pinned "
                            f"{allow['sha256_after']}")
    return offsets


def run_steps(manifest, app, tree, engine, log):
    for step in manifest["steps"]:
        step_extra = {}
        before = {r[0]: r[2] for r in tree_listing(tree)}
        op = step["op"]
        if op == "app_python":
            args = [a.replace("{tree}", str(tree)) for a in step["args"]]
            rc, out = run_checked([sys.executable, "-I", "-B", "-X", "utf8", str(app / step["script"]), *args],
                                  cwd=str(app))
            if rc:
                raise PrepError(f"{step['id']}: {out.strip()[:800]}")
        elif op == "copy_tree":
            src = app / step["from"]
            files = sorted((p for p in src.rglob("*") if p.is_file()), key=lambda p: str(p).encode())
            if len(files) != step["expect_files"]:
                raise PrepError(f"{step['id']}: {len(files)} files != {step['expect_files']}")
            for f in files:
                dest = tree / f.relative_to(src)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(f, dest)
                shutil.copymode(f, dest)
        elif op == "patch_series":
            patches = sorted_glob(app, step["glob"])
            if len(patches) != step["expect_patches"]:
                raise PrepError(f"{step['id']}: {len(patches)} patches != {step['expect_patches']}")
            allow = step.get("fuzz_allowlist", {})
            unknown = set(allow) - {p.name for p in patches}
            if unknown:
                raise PrepError(f"{step['id']}: allowlist names absent patches {sorted(unknown)}")
            offsets = {}
            for p in patches:
                offsets[p.name] = apply_patch(tree, p, engine, allow.get(p.name))
            if engine == "git-apply":
                step_extra = {"offset_hunks": sum(offsets.values())}
        elif op == "stamp_concat_sha256":
            h = hashlib.sha256(b"".join(p.read_bytes() for p in sorted_glob(app, step["glob"])))
            (tree / step["to"]).write_text(h.hexdigest() + "\n")
        elif op == "copy_file":
            shutil.copyfile(app / step["from"], tree / step["to"])
        else:
            raise PrepError(f"unknown op {op}")
        after = {r[0]: r[2] for r in tree_listing(tree)}
        log.append({
            "step": step["id"],
            "added": sorted(set(after) - set(before)),
            "modified": sorted(k for k in set(after) & set(before) if after[k] != before[k]),
            "removed": sorted(set(before) - set(after)),
            **step_extra,
        })


def check_app_semantics(manifest, app_bare, sha):
    for rel, blob in manifest["app_semantics_blobs"].items():
        got = git("--git-dir", str(app_bare), "rev-parse", f"{sha}:{rel}")
        if got != blob:
            raise PrepError(f"app semantics changed: {rel} blob {got} != {blob}")


def leftover_staging(out):
    return sorted(p.name for p in out.parent.glob(out.name + STAGING + "*")) if out.parent.exists() else []


def prepare(cache, out, manifest, engine, allow_unpinned=False, pins=None):
    out = out.resolve()
    if out.exists():
        raise PrepError(f"output {out} already exists; refuse to reuse (run verify, or remove it)")
    left = leftover_staging(out)
    if left:
        raise PrepError(f"partial preparation present: {left}; remove it before preparing")
    expected = manifest["prepared_tree"]["sha256"]
    if not re.fullmatch(r"[0-9a-f]{64}", expected) and not allow_unpinned:
        raise PrepError("manifest prepared_tree.sha256 is not pinned")
    repos = manifest["repositories"]
    ident = {n: check_identity(cache / f"{n}.git", n, r) for n, r in repos.items()}
    check_app_semantics(manifest, cache / "app.git", repos["app"]["commit"])
    out.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=out.name + STAGING, dir=out.parent))
    try:
        app = stage / "app"
        tree = stage / "source"
        export(cache / "app.git", repos["app"]["commit"], app)
        export(cache / "rathena.git", repos["rathena"]["commit"], tree)
        base_rows = tree_listing(tree)
        if len(base_rows) != repos["rathena"]["files"]:
            raise PrepError(f"rathena export has {len(base_rows)} files != {repos['rathena']['files']}")
        log = []
        run_steps(manifest, app, tree, engine, log)
        shutil.rmtree(app)
        rows = tree_listing(tree)
        npins = check_pins(tree, pins if pins is not None else load_pins())
        got = digest(rows)
        if len(rows) != manifest["prepared_tree"]["files"]:
            raise PrepError(f"prepared files {len(rows)} != {manifest['prepared_tree']['files']}")
        if got != expected and not allow_unpinned:
            raise PrepError(f"prepared tree digest {got} != pinned {expected}")
        base = {r[0]: r[2] for r in base_rows}
        now = {r[0]: r[2] for r in rows}
        fp = footprint(base, now)
        check_footprint(manifest, fp, allow_unpinned)
        record = {
            "schema": "t10.010.003/prepared/v1",
            "identity": ident,
            "patch_engine": engine,
            "rathena_files": len(base_rows),
            "prepared_files": len(rows),
            "prepared_tree_sha256": got,
            "manifest_sha256": hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            "nine_pins_ok": npins,
            "footprint_paths": fp,
            "footprint": {
                "added": sorted(set(now) - set(base)),
                "modified": sorted(k for k in set(now) & set(base) if now[k] != base[k]),
                "removed": sorted(set(base) - set(now)),
            },
            "steps": log,
        }
        (stage / MARKER).write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
        os.rename(stage, out)
        return record
    except BaseException:
        shutil.rmtree(stage, ignore_errors=True)
        raise


def footprint(base, now):
    """Every path the overlays add, modify or remove, with its prepared bytes' sha256."""
    fp = {k: {"change": "added", "sha256": now[k]} for k in set(now) - set(base)}
    fp.update({k: {"change": "modified", "sha256": now[k]} for k in set(now) & set(base) if now[k] != base[k]})
    fp.update({k: {"change": "removed", "sha256": None} for k in set(base) - set(now)})
    return dict(sorted(fp.items()))


def check_footprint(manifest, fp, allow_unpinned=False):
    name = manifest.get("footprint_file")
    if not name:
        if allow_unpinned:
            return
        raise PrepError("manifest pins no footprint_file")
    path = Path(name) if Path(name).is_absolute() else HERE / name
    if not path.is_file():
        if allow_unpinned:
            return
        raise PrepError(f"footprint file {name} missing")
    pinned = json.loads(path.read_text())["paths"]
    diff = sorted(set(pinned) ^ set(fp)) + sorted(k for k in set(pinned) & set(fp) if pinned[k] != fp[k])
    if diff:
        raise PrepError(f"overlay footprint differs from {name} at {len(diff)} path(s): {diff[:10]}")


def reconcile(a, b, ignore_suffixes=(".orig",)):
    """Path-by-path comparison of two independently prepared source trees."""
    la = {r[0]: r[1:3] for r in tree_listing(a)}
    lb = {r[0]: r[1:3] for r in tree_listing(b) if not r[0].endswith(ignore_suffixes)}
    return {"only_a": sorted(set(la) - set(lb)), "only_b": sorted(set(lb) - set(la)),
            "differ": sorted(k for k in set(la) & set(lb) if la[k] != lb[k]), "files_a": len(la), "files_b": len(lb)}


def verify(out, manifest, pins=None):
    out = Path(out)
    if out.is_symlink():  # before resolve(), which would follow it
        raise PrepError(f"{out}: output root is a symlink")
    out = out.resolve()
    left = leftover_staging(out)
    if left:
        raise PrepError(f"partial preparation present: {left}")
    if out.is_symlink() or (out / "source").is_symlink() or (out / MARKER).is_symlink():
        raise PrepError(f"{out}: symlinked output entry")
    marker = out / MARKER
    if not marker.is_file():
        raise PrepError(f"{out}: no {MARKER}; partial or foreign directory")
    extra = sorted(p.name for p in out.iterdir() if p.name not in (MARKER, "source"))
    if extra:
        raise PrepError(f"{out}: unexpected entries {extra}")
    rec = json.loads(marker.read_text())
    rows = tree_listing(out / "source")
    got = digest(rows)
    if got != rec.get("prepared_tree_sha256") or got != manifest["prepared_tree"]["sha256"]:
        raise PrepError(f"dirty prepared tree: digest {got} (recorded {rec.get('prepared_tree_sha256')}, "
                        f"pinned {manifest['prepared_tree']['sha256']})")
    check_pins(out / "source", pins if pins is not None else load_pins())
    return {"prepared_tree_sha256": got, "files": len(rows)}


def reference(cache, out, manifest):
    """Run the app's actual apply-server-mods.sh + Dockerfile copy on a fresh export."""
    out = out.resolve()
    if out.exists():
        raise PrepError(f"{out} exists")
    repos = manifest["repositories"]
    for n, r in repos.items():
        check_identity(cache / f"{n}.git", n, r)
    check_app_semantics(manifest, cache / "app.git", repos["app"]["commit"])
    out.mkdir(parents=True)
    app, tree = out / "app", out / "source"
    export(cache / "app.git", repos["app"]["commit"], app)
    export(cache / "rathena.git", repos["rathena"]["commit"], tree)
    rc, log = run_checked(["sh", str(app / "scripts/apply-server-mods.sh"), str(tree)], cwd=str(app),
                          env=dict(os.environ, LC_ALL="C"), timeout=600)
    if rc:
        raise PrepError(f"reference apply-server-mods.sh rc={rc}: {log[-800:]}")
    shutil.copyfile(app / "containers/rathena/Dockerfile", tree / "Dockerfile.ragnarokmac")
    shutil.rmtree(app)  # the reference tree stays at <out>/source for `reconcile`
    side = sorted(p.relative_to(tree).as_posix() for p in tree.rglob("*") if p.suffix in (".orig", ".rej"))
    rows = [r for r in tree_listing(tree) if not r[0].endswith((".orig", ".rej"))]
    return {"digest_without_side_files": digest(rows), "files": len(rows), "side_files": side,
            "diagnostic_lines": [l for l in log.splitlines() if DIAG.search(l)]}


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=("fetch", "prepare", "verify", "reference", "reconcile", "footprint"))
    ap.add_argument("--against", type=Path, help="reconcile: independently prepared directory with source/")
    ap.add_argument("--cache", type=Path)
    ap.add_argument("--out", type=Path)
    ap.add_argument("--manifest", type=Path, default=MANIFEST)
    ap.add_argument("--patch-engine", choices=("patch", "git-apply"), default="patch")
    ap.add_argument("--allow-unpinned-digest", action="store_true",
                    help="discovery only: report the digest instead of requiring the pinned one")
    a = ap.parse_args(argv)
    try:
        m = load_manifest(a.manifest)
        if a.cmd == "fetch":
            res = fetch(a.cache.resolve(), m)
        elif a.cmd == "prepare":
            res = prepare(a.cache.resolve(), a.out, m, a.patch_engine, a.allow_unpinned_digest)
            res = {k: v for k, v in res.items() if k not in ("steps", "footprint", "footprint_paths")} | {
                "added": len(res["footprint"]["added"]), "modified": len(res["footprint"]["modified"]),
                "removed": len(res["footprint"]["removed"])}
        elif a.cmd == "verify":
            res = verify(a.out, m)
        elif a.cmd == "reference":
            res = reference(a.cache.resolve(), a.out, m)
        elif a.cmd == "reconcile":
            res = reconcile(a.out / "source", a.against / "source")
            if res["only_a"] or res["only_b"] or res["differ"]:
                print("FAIL", json.dumps(res, sort_keys=True))
                return 1
        else:  # footprint: print the per-path footprint of a verified output
            verify(a.out, m)
            res = json.loads((a.out / MARKER).read_text())["footprint_paths"]
            print(json.dumps({"schema": "t10.010.003/footprint/v1", "paths": res}, indent=1, sort_keys=True))
            return 0
    except (PrepError, OSError, subprocess.TimeoutExpired) as e:
        print("FAIL", e)
        return 1
    print("OK", json.dumps(res, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
