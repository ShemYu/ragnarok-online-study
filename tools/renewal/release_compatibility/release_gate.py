#!/usr/bin/env python3
"""Read-only external pre-install compatibility gate for ro-solo 0.3.2 (T10.010.005).

    python3 -I release_gate.py --packet ABS_PACKET.json
    python3 -I release_gate.py --synthetic --manifest ABS_MANIFEST.json --packet ABS_PACKET.json

The gate binds the two staged installable folders (story ro-solo-ch1-entry
0.3.2 and text tc-true-quest-text 0.1.0) to the pinned app/server sources,
the native patch, one actual executable, an explicit effective-configuration
artifact and Root-qualified evidence records, before any supported folder
installation. Every qualification record and the full text reference must
equal an independent expected digest in the manifest; caller self-hashes,
labels and booleans never qualify by themselves.

It reads only the explicit packet, the regular files it names and a bounded
census of the two explicit staged roots (no other listing, no discovery, no
network, no writes) and prints one bounded JSON result.

Real mode uses the bundled release_manifest_0.3.2.json; while any expected
pin there is null (runtime facts and qualification records Root has not yet
reviewed), real mode always refuses. Synthetic mode needs an explicit
synthetic manifest and synthetic records; its best outcome is
"synthetic_consistent", never an admission. The gate checks recorded
consistency only: Root establishes and pins the underlying runtime facts.

Exit codes: 0 admitted / synthetic_consistent, 1 refused, 2 usage.
"""

import argparse
import hashlib
import json
import os
import re
import stat
import sys

RESULT_SCHEMA = "ro-solo-release-gate-result.v2"
PACKET_SCHEMA = "ro-solo-release-admission-packet.v2"
MANIFEST_SCHEMA = "ro-solo-release-compatibility-manifest.v2"
NATIVE_SCHEMA = "ro-solo-native-qualification.v1"
FACTS_SCHEMA = "ro-solo-effective-facts.v1"
REFERENCE_SCHEMA = "ro-solo-quest-text-reference.v2"
TEXT_EFFECTIVE_SCHEMA = "ro-solo-text-effective.v1"

HERE = os.path.dirname(os.path.abspath(__file__))
BUNDLED_MANIFEST = os.path.join(HERE, "release_manifest_0.3.2.json")

MAX_REASONS = 64
MAX_DETAIL = 240
JSON_CAP = 1 << 20
TEXT_CAP = 1 << 20
TABLE_CAP = 8 << 20
LOG_CAP = 16 << 20
CONFIG_CAP = 64 << 20
EXECUTABLE_CAP = 1 << 30
CHUNK = 1 << 16
CENSUS_MAX_ENTRIES = 64
CENSUS_MAX_DEPTH = 4
QUEST_IDS = (18368, 18369, 18370, 18371)
SHA_RE = re.compile(r"[0-9a-f]{64}\Z")
IMAGE_RE = re.compile(r"sha256:[0-9a-f]{64}\Z")
STACK_KEYS = ("amount", "inventory", "cart", "storage", "guild_storage")
# Directory names and manifest keys through which the app would load
# era/client-specific copies (mods.rs era_folder/client_folders, db/re, db/pre-re).
ERA_DIR_NAMES = frozenset(("re", "pre-re", "renewal", "pre-renewal", "prerenewal", "when", "client"))
ERA_MANIFEST_KEYS = ("renewalFolder", "prerenewalFolder", "clientFolders")
# Streamed (hash-only) roles and their caps; everything else is buffered.
STREAMED = {"native.executable": EXECUTABLE_CAP, "effective.config": CONFIG_CAP}
# Records whose exact bytes must equal an independent manifest pin.
QUALIFIED_ROLES = ("native.parser_log", "native.qualification", "effective.config",
                   "effective.facts", "text.reference", "text.effective")
PARSER_REJECT_MARKERS = (
    "parse_line", "parse_callfunc", "undeclared function", "Unknown command",
    "script error", "Script error", "unknown item", "Unknown item",
)


class Malformed(Exception):
    pass


class Reasons:
    def __init__(self):
        self.items = []
        self.dropped = 0

    def add(self, code, detail=""):
        detail = str(detail)
        if len(detail) > MAX_DETAIL:
            detail = detail[: MAX_DETAIL - 3] + "..."
        if len(self.items) >= MAX_REASONS:
            self.dropped += 1
            return
        self.items.append({"code": code, "detail": detail})

    def __bool__(self):
        return bool(self.items) or self.dropped > 0


class InputError(Exception):
    def __init__(self, code, detail):
        super().__init__(detail)
        self.code = code
        self.detail = detail


def canon(value):
    return json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":"))


def same(a, b):
    """Structural equality that distinguishes bool from int (True != 1)."""
    return canon(a) == canon(b)


def is_int(value):
    return type(value) is int


def is_bool(value):
    return type(value) is bool


def is_sha(value):
    return isinstance(value, str) and SHA_RE.match(value) is not None


def _role_cap(role):
    if role in STREAMED:
        return STREAMED[role]
    if role == "native.parser_log":
        return LOG_CAP
    if role == "text.table":
        return TABLE_CAP
    if role.startswith(("app.", "story.")):
        return TEXT_CAP
    return JSON_CAP


def _check_path_shape(path):
    if not isinstance(path, str) or not path:
        raise InputError("input_path_invalid", "path must be a non-empty string")
    if "\0" in path:
        raise InputError("input_path_invalid", "path contains NUL")
    if not os.path.isabs(path):
        raise InputError("input_path_not_absolute", path)
    if os.path.normpath(path) != path:
        raise InputError("input_path_not_normalized", path)
    current = os.sep
    st = None
    for part in path.split(os.sep)[1:]:
        current = os.path.join(current, part)
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            raise InputError("input_missing", path)
        except OSError as exc:
            raise InputError("input_unreadable", "%s: %s" % (path, exc.strerror))
        if stat.S_ISLNK(st.st_mode):
            raise InputError("input_symlink", current)
    return st


def _ident(st):
    return (st.st_dev, st.st_ino, st.st_mode, st.st_size, st.st_mtime_ns, st.st_ctime_ns)


def read_explicit(path, cap, keep=True):
    """Bounded read of one explicit regular file. Returns (data|None, size, sha256).

    The path's lstat identity, the opened descriptor's identity before and
    after the read, and a final path lstat must agree on dev/ino/mode/size/
    mtime/ctime; any observed change refuses."""
    st = _check_path_shape(path)
    if not stat.S_ISREG(st.st_mode):
        raise InputError("input_not_regular", path)
    if st.st_nlink != 1:
        raise InputError("input_hardlinked", "%s has %d links" % (path, st.st_nlink))
    if st.st_size > cap:
        raise InputError("input_too_large", "%s: %d > %d bytes" % (path, st.st_size, cap))
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
    try:
        fd = os.open(path, flags)
    except OSError as exc:
        raise InputError("input_unreadable", "%s: %s" % (path, exc.strerror))
    try:
        before = os.fstat(fd)
        if _ident(before) != _ident(st):
            raise InputError("input_changed", "%s changed before open" % path)
        digest = hashlib.sha256()
        parts = []
        total = 0
        while True:
            chunk = os.read(fd, min(CHUNK, cap + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > cap:
                raise InputError("input_too_large", path)
            digest.update(chunk)
            if keep:
                parts.append(chunk)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if _ident(after) != _ident(before) or total != before.st_size:
        raise InputError("input_changed", "%s changed during read" % path)
    try:
        final = os.lstat(path)
    except OSError:
        raise InputError("input_changed", "%s vanished after read" % path)
    if _ident(final) != _ident(before):
        raise InputError("input_changed", "%s replaced after read" % path)
    return (b"".join(parts) if keep else None), total, digest.hexdigest()


def _no_duplicates(pairs):
    out = {}
    for key, value in pairs:
        if key in out:
            raise Malformed("duplicate key %r" % key)
        out[key] = value
    return out


def _reject_constant(name):
    raise Malformed("non-finite number %s" % name)


def parse_json(data, what):
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise Malformed("%s is not UTF-8" % what)
    try:
        value = json.loads(text, object_pairs_hook=_no_duplicates, parse_constant=_reject_constant)
    except Malformed:
        raise
    except ValueError as exc:
        raise Malformed("%s is not JSON: %s" % (what, exc))
    if not isinstance(value, dict):
        raise Malformed("%s is not a JSON object" % what)
    return value


def _get(obj, key, kind=dict):
    value = obj.get(key) if isinstance(obj, dict) else None
    return value if isinstance(value, kind) else kind()


# --------------------------------------------------------------------- staging


def census(root, spec, label, reasons):
    """Bounded census of one explicit staged root.

    spec = {"name", "directories": [...], "files": {role: {relpath, ...}}}.
    Returns {role: absolute path} for the expected files that exist, or None
    when the root itself is unusable. Only this root is listed."""
    try:
        st = _check_path_shape(root)
    except InputError as exc:
        reasons.add("staged_" + exc.code, "%s root: %s" % (label, exc.detail))
        return None
    if not stat.S_ISDIR(st.st_mode):
        reasons.add("staged_root_not_directory", "%s root %s" % (label, root))
        return None
    if os.path.basename(root) != spec["name"]:
        reasons.add("staged_root_name", "%s root is %r, the app installs the folder name; expected %r" % (
            label, os.path.basename(root), spec["name"]))
    files, dirs = set(), set()
    pending = [("", root, 0)]
    count = 0
    while pending:
        rel, path, depth = pending.pop()
        try:
            entries = sorted(os.scandir(path), key=lambda e: e.name)
        except OSError as exc:
            reasons.add("staged_unreadable", "%s %s: %s" % (label, rel or ".", exc.strerror))
            return None
        for entry in entries:
            count += 1
            if count > CENSUS_MAX_ENTRIES:
                reasons.add("staged_too_many_entries", "%s exceeds %d entries" % (label, CENSUS_MAX_ENTRIES))
                return None
            erel = entry.name if not rel else rel + "/" + entry.name
            est = entry.stat(follow_symlinks=False)
            if stat.S_ISLNK(est.st_mode):
                reasons.add("staged_symlink", "%s %s" % (label, erel))
            elif stat.S_ISDIR(est.st_mode):
                dirs.add(erel)
                if depth + 1 >= CENSUS_MAX_DEPTH:
                    reasons.add("staged_too_deep", "%s %s" % (label, erel))
                else:
                    pending.append((erel, entry.path, depth + 1))
            elif stat.S_ISREG(est.st_mode):
                files.add(erel)
            else:
                reasons.add("staged_special_file", "%s %s" % (label, erel))
            if set(erel.split("/")) & ERA_DIR_NAMES:
                reasons.add("staged_era_override", "%s %s" % (label, erel))
    by_rel = {f["relpath"]: role for role, f in spec["files"].items()}
    for erel in sorted(files - set(by_rel)):
        reasons.add("staged_extra", "%s %s" % (label, erel))
    for erel in sorted(dirs - set(spec["directories"])):
        reasons.add("staged_extra", "%s %s/" % (label, erel))
    found = {}
    for erel, role in sorted(by_rel.items()):
        if erel in files:
            found[role] = os.path.join(root, *erel.split("/"))
        else:
            reasons.add("staged_missing", "%s %s" % (label, erel))
    return found


# --------------------------------------------------------------------- static


def parse_quest_db(text):
    """Minimal exact reader for the story's QUEST_DB v3 layout (Id/Title only)."""
    header = {}
    rows = []
    section = None
    for raw in text.split("\n"):
        line = raw.rstrip("\r")
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith((" ", "\t")):
            section = line.strip()
            if section not in ("Header:", "Body:", "Footer:"):
                raise Malformed("unexpected top-level line %r" % line[:60])
            continue
        if section == "Header:":
            m = re.fullmatch(r"\s+(\w+):\s*(.*?)\s*", line)
            if not m:
                raise Malformed("unreadable header line %r" % line[:60])
            header[m.group(1)] = m.group(2)
        elif section == "Body:":
            m = re.fullmatch(r"\s+- Id:\s*(\d+)\s*", line)
            if m:
                rows.append({"Id": int(m.group(1))})
                continue
            m = re.fullmatch(r"\s+(\w+):\s*(.*?)\s*", line)
            if not m or not rows:
                raise Malformed("unreadable body line %r" % line[:60])
            rows[-1][m.group(1)] = m.group(2)
        else:
            header.setdefault("_footer", "present")
    return header, rows


def _check_requires_and_era(mod, story, label, reasons):
    req = mod.get("requires")
    if not isinstance(req, dict):
        reasons.add("%s_requires_malformed" % label, repr(req))
    else:
        extra = sorted(set(req) - set(story["requires_supported_keys"]))
        if extra:
            reasons.add("%s_requires_unsupported_key" % label, ", ".join(extra))
    for key in ERA_MANIFEST_KEYS:
        if key in mod:
            reasons.add("staged_era_override", "%s mod.json declares %s" % (label, key))


def check_story_static(manifest, data, reasons):
    story = manifest["story"]
    try:
        mod = parse_json(data["story.mod_json"], "story mod.json")
    except Malformed as exc:
        reasons.add("story_manifest_malformed", exc)
        mod = None
    if mod is not None:
        version = mod.get("version")
        if mod.get("name") != story["name"]:
            reasons.add("story_name_mismatch", repr(mod.get("name")))
        if version in story["superseded_versions"]:
            reasons.add("story_superseded_staging", "staged %s; current release is %s" % (version, story["version"]))
        elif version != story["version"]:
            reasons.add("story_version_mismatch", repr(version))
        _check_requires_and_era(mod, story, "story", reasons)
        if isinstance(mod.get("requires"), dict) and not same(mod["requires"], story["requires"]):
            reasons.add("story_requires_mismatch", canon(mod["requires"]))
    try:
        header, rows = parse_quest_db(data["story.quest_db"].decode("utf-8"))
    except (UnicodeDecodeError, Malformed) as exc:
        reasons.add("quest_db_malformed", exc)
        header, rows = None, []
    if header is not None:
        if header.get("Type") != manifest["quests"]["db_type"] or header.get("Version") != str(manifest["quests"]["db_version"]):
            reasons.add("quest_db_header_mismatch", canon(header))
        if "Clear" in header and header["Clear"].strip().lower() != "false":
            reasons.add("quest_db_clear", "staged quest_db.yml header Clear: %s" % header["Clear"])
        if "_footer" in header:
            reasons.add("quest_db_footer", "staged quest_db.yml has a Footer/Imports section")
        ids = [r.get("Id") for r in rows]
        expected = {r["id"]: r["title_sha256"] for r in manifest["quests"]["rows"]}
        for qid in expected:
            if qid not in ids:
                reasons.add("quest_row_missing", "staged quest_db.yml lacks %d" % qid)
        for row in rows:
            qid = row.get("Id")
            if ids.count(qid) > 1:
                reasons.add("quest_row_duplicate", str(qid))
            if qid not in expected:
                reasons.add("quest_row_unexpected", str(qid))
                continue
            if sorted(row) != ["Id", "Title"]:
                reasons.add("quest_row_fields", "%d: %s" % (qid, ",".join(sorted(row))))
            if hashlib.sha256(row.get("Title", "").encode("utf-8")).hexdigest() != expected[qid]:
                reasons.add("quest_row_title_mismatch", str(qid))
    npc_text = {}
    for role in ("story.npc.entry", "story.npc.first_edge", "story.npc.fruit_village"):
        try:
            npc_text[role] = data[role].decode("utf-8")
        except UnicodeDecodeError:
            reasons.add("story_npc_not_utf8", role)
            npc_text[role] = ""
    joined = "\n".join(npc_text.values())
    for name in manifest["routes"]["maps"]:
        if not re.search(r"(?m)^%s,\d+,\d+," % re.escape(name), joined) and ('"%s"' % name) not in joined:
            reasons.add("route_map_missing", "staged scripts do not reference %s" % name)
    block = manifest["routes"]["first_edge_block"]
    lines = data[block["role"]].split(b"\n")
    piece = b"\n".join(lines[block["first_line"] - 1: block["last_line"]]) + b"\n"
    if len(piece) != block["bytes"] or hashlib.sha256(piece).hexdigest() != block["sha256"]:
        reasons.add("connection_block_changed", "first_edge.txt lines %d-%d differ" % (block["first_line"], block["last_line"]))
    edge = npc_text["story.npc.first_edge"]
    for conn in manifest["routes"]["connections"]:
        (fm, fx, fy), (tm, tx, ty) = conn["from"], conn["to"]
        if conn["name"].startswith("ROSOLO_"):
            pattern = r"(?m)^%s,%d,%d,\d+\twarp\t%s\t\d+,\d+,%s,%d,%d$" % (
                re.escape(fm), fx, fy, re.escape(conn["name"]), re.escape(tm), tx, ty)
            found = re.search(pattern, edge)
        else:
            head = re.search(r"(?m)^%s,%d,%d,\d+\tscript\t%s\t" % (re.escape(fm), fx, fy, re.escape(conn["name"])), edge)
            found = head and ('warp "%s",%d,%d;' % (tm, tx, ty)) in edge[head.end():head.end() + 200]
        if not found:
            reasons.add("route_exit_missing", conn["name"])


def check_text_static(manifest, data, reasons):
    text = manifest["text"]
    try:
        mod = parse_json(data["text.mod_json"], "text mod.json")
    except Malformed as exc:
        reasons.add("text_manifest_malformed", exc)
        return
    if not same(mod, text["mod_manifest"]):
        reasons.add("text_manifest_mismatch", "staged text mod.json differs from the frozen %s %s manifest" % (text["name"], text["version"]))
    _check_requires_and_era(mod, manifest["story"], "text", reasons)


# --------------------------------------------------------------------- records


def _common_record(rec, schema, label, mode, manifest, reasons):
    if rec.get("schema") != schema:
        reasons.add("%s_schema" % label, repr(rec.get("schema")))
    want_class = "synthetic" if mode == "synthetic" else "actual"
    if rec.get("record_class") != want_class:
        reasons.add("%s_record_class" % label, "%r in %s mode" % (rec.get("record_class"), mode))
    if rec.get("release_id") != manifest["release_id"]:
        reasons.add("%s_release_mismatch" % label, repr(rec.get("release_id")))


def _stack(value, label, reasons):
    if not isinstance(value, dict) or sorted(value) != sorted(STACK_KEYS):
        reasons.add("%s_stack_unknown" % label, "stack_restrictions must state exactly %s" % ",".join(STACK_KEYS))
        return None
    if not (value["amount"] is None or (is_int(value["amount"]) and value["amount"] > 0)):
        reasons.add("%s_stack_unknown" % label, "amount must be null (no item stack) or a positive int")
        return None
    for key in STACK_KEYS[1:]:
        if not is_bool(value[key]):
            reasons.add("%s_stack_unknown" % label, "%s must be a boolean" % key)
            return None
    if value["amount"] is None and any(value[k] for k in STACK_KEYS[1:]):
        reasons.add("%s_stack_contradiction" % label, "a restricted location without an amount")
        return None
    if value["amount"] is not None and not any(value[k] for k in STACK_KEYS[1:]):
        reasons.add("%s_stack_contradiction" % label, "an amount without any restricted location")
        return None
    return value


def _int_eq(value, want):
    return is_int(value) and value == want


def check_native(manifest, rec, ctx, mode, reasons):
    nat = manifest["native"]
    _common_record(rec, NATIVE_SCHEMA, "native", mode, manifest, reasons)
    if rec.get("qualification_kind") != "isolated_runtime":
        reasons.add("native_unqualified_kind", "qualification_kind=%r; host fixtures and assertions do not qualify" % rec.get("qualification_kind"))
    src = _get(rec, "source")
    expect_src = {
        "rathena_revision": nat["source_revision"],
        "prepared_source_tree_sha256": nat["prepared_source_tree_sha256"],
        "patch_sha256": nat["patch"]["sha256"],
        "app_commit": manifest["app"]["commit"],
        "app_tree": manifest["app"]["tree"],
    }
    for key, want in expect_src.items():
        if src.get(key) != want:
            reasons.add("native_source_mismatch", "%s=%r" % (key, src.get(key)))
    exe = _get(rec, "executable")
    if exe.get("patched") is not True:
        reasons.add("native_stock_evidence", "executable.patched is not true")
    if exe.get("sha256") != ctx["executable_sha256"] or not _int_eq(exe.get("bytes"), ctx["executable_bytes"]):
        reasons.add("native_executable_mismatch", "record does not describe the supplied executable")
    if nat["stock_executable_sha256"] is not None and exe.get("sha256") == nat["stock_executable_sha256"]:
        reasons.add("native_stock_evidence", "record executable is the stock executable")
    image = _get(rec, "image")
    if not isinstance(image.get("id"), str) or IMAGE_RE.match(image.get("id")) is None:
        reasons.add("native_image_malformed", repr(image.get("id")))
    elif nat["image_id"] is not None and image["id"] != nat["image_id"]:
        reasons.add("native_image_mismatch", image["id"])
    if image.get("platform") != nat["platform"]:
        reasons.add("native_platform_mismatch", repr(image.get("platform")))
    if not _int_eq(rec.get("packet_version"), nat["packet_version"]):
        reasons.add("native_packet_mismatch", repr(rec.get("packet_version")))
    abi = rec.get("abi")
    if not isinstance(abi, dict) or not isinstance(abi.get("libraries"), list) or not abi.get("libraries") \
            or not all(isinstance(x, dict) and isinstance(x.get("soname"), str) and is_sha(x.get("sha256")) for x in abi["libraries"]) \
            or not isinstance(abi.get("libc"), str) or not isinstance(abi.get("loader"), str):
        reasons.add("native_abi_malformed", "abi needs libc, loader and libraries[{soname, sha256}]")
    elif nat["abi"] is not None and not same(abi, nat["abi"]):
        reasons.add("native_abi_mismatch", "recorded ABI/libraries differ from the release binding")
    cfg = rec.get("effective_config_sha256")
    if cfg != ctx["config_sha256"]:
        reasons.add("native_config_mismatch", "record does not cite the supplied effective configuration")
    parser = _get(rec, "parser")
    if parser.get("method") != "isolated_map_server_load":
        reasons.add("native_parser_unqualified", "parser.method=%r" % parser.get("method"))
    if parser.get("log_sha256") != ctx["parser_log_sha256"]:
        reasons.add("native_parser_log_mismatch", "record does not cite the supplied parser log")
    if parser.get("loaded") is not True or not _int_eq(parser.get("errors"), 0) or not _int_eq(parser.get("release_warnings"), 0):
        reasons.add("native_parser_failed", "loaded/errors/release_warnings = %r/%r/%r" % (
            parser.get("loaded"), parser.get("errors"), parser.get("release_warnings")))
    want_scripts = {ctx["relpath"][r]: ctx["staged_sha"].get(r) for r in
                    ("story.npc.entry", "story.npc.first_edge", "story.npc.fruit_village", "story.quest_db")}
    got = {}
    for item in _get(parser, "scripts", list):
        if isinstance(item, dict) and isinstance(item.get("path"), str):
            got[item["path"]] = item.get("sha256")
    if not same(got, want_scripts):
        reasons.add("native_script_mismatch", "parser.scripts must be exactly the staged scripts and quest DB by hash")
    builtin = _get(rec, "builtin")
    want_b = nat["builtin"]
    if builtin.get("name") != want_b["name"] or builtin.get("registered") is not True \
            or not _int_eq(builtin.get("arguments"), want_b["arguments"]):
        reasons.add("native_builtin_unproven", "builtin %s registration not recorded for this executable" % want_b["name"])
    probe = _get(builtin, "probe_observations")
    if not _int_eq(probe.get("fits"), want_b["fits"]) or not _int_eq(probe.get("no_fit"), want_b["no_fit"]):
        reasons.add("native_builtin_unproven", "probe_observations must record integer fits=%d and no_fit=%d" % (want_b["fits"], want_b["no_fit"]))
    stock = rec.get("stock_control") if isinstance(rec.get("stock_control"), dict) else None
    if stock is None:
        reasons.add("native_stock_control_missing", "no stock executable control")
    else:
        if not is_sha(stock.get("executable_sha256")) or stock.get("executable_sha256") == exe.get("sha256"):
            reasons.add("native_stock_control_invalid", "stock control must name a different executable")
        elif nat["stock_executable_sha256"] is not None and stock["executable_sha256"] != nat["stock_executable_sha256"]:
            reasons.add("native_stock_control_invalid", "stock control executable differs from the release binding")
        if stock.get("builtin_registered") is not False or stock.get("release_rejected") is not True:
            reasons.add("native_stock_control_invalid", "stock control must show no builtin and a rejected release")
    ctx["native_stack"] = _stack(rec.get("stack_restrictions"), "native", reasons)
    max_amount = rec.get("max_amount")
    ctx["native_max_amount"] = max_amount if is_int(max_amount) and max_amount > 0 else None
    if ctx["native_max_amount"] is None:
        reasons.add("native_max_amount_unknown", repr(max_amount))
    ctx["native_image"] = image.get("id")


def check_parser_log(data, reasons):
    text = data.decode("utf-8", errors="replace")
    for marker in PARSER_REJECT_MARKERS:
        if marker in text:
            reasons.add("native_parser_log_rejection", "parser log contains %r" % marker)


def check_facts(manifest, rec, ctx, mode, reasons):
    _common_record(rec, FACTS_SCHEMA, "facts", mode, manifest, reasons)
    env = _get(rec, "environment")
    if env.get("executable_sha256") != ctx["executable_sha256"]:
        reasons.add("facts_environment_mismatch", "executable differs from the supplied executable")
    if env.get("image_id") != ctx.get("native_image"):
        reasons.add("facts_environment_mismatch", "image differs from the native record")
    if env.get("effective_config_sha256") != ctx["config_sha256"]:
        reasons.add("facts_environment_mismatch", "effective configuration differs from the supplied artifact")
    item = _get(rec, "item")
    want = manifest["item"]
    res = item.get("alias_resolutions")
    if not isinstance(res, list) or len(res) < 2:
        reasons.add("item_alias_unproven", "need at least two independent alias resolutions (item DB and script)")
    else:
        sources = set()
        for entry in res:
            if not isinstance(entry, dict) or entry.get("alias") != want["alias"] or not is_int(entry.get("id")):
                reasons.add("item_alias_malformed", canon(entry)[:120])
                continue
            sources.add(entry.get("source"))
            if entry["id"] != want["id"]:
                reasons.add("item_alias_wrong", "%s resolves to %d via %r" % (want["alias"], entry["id"], entry.get("source")))
        if len(sources) < 2:
            reasons.add("item_alias_unproven", "alias resolutions need two distinct sources")
    if not _int_eq(item.get("id"), want["id"]):
        reasons.add("item_alias_wrong", "effective item id %r" % (item.get("id"),))
    for key in ("type", "weight", "stackable", "guid", "pet"):
        value = item.get(key)
        if key in ("stackable", "guid", "pet") and not is_bool(value):
            reasons.add("item_fact_unknown", "%s=%r" % (key, value))
        elif key == "weight" and not is_int(value):
            reasons.add("item_fact_unknown", "weight=%r" % (value,))
        elif key == "type" and not isinstance(value, str):
            reasons.add("item_fact_unknown", "type=%r" % (value,))
        elif value != want[key]:
            reasons.add("item_%s_wrong" % key, "%r, expected %r" % (value, want[key]))
    stack = _stack(item.get("stack_restrictions"), "item", reasons)
    if stack is not None and ctx.get("native_stack") is not None and not same(stack, ctx["native_stack"]):
        reasons.add("item_stack_contradiction", "effective stack restrictions differ from the native qualification")
    if stack is not None and item.get("stackable") is False and stack["amount"] is not None:
        reasons.add("item_stack_contradiction", "a stack limit on a non-stackable item")
    max_amount = item.get("max_amount")
    if not (is_int(max_amount) and max_amount > 0):
        reasons.add("item_max_amount_unknown", repr(max_amount))
    elif ctx.get("native_max_amount") is not None and max_amount != ctx["native_max_amount"]:
        reasons.add("item_stack_contradiction", "max_amount %d differs from native %d" % (max_amount, ctx["native_max_amount"]))
    maps = _get(rec, "maps")
    for name in manifest["routes"]["maps"]:
        entry = maps.get(name)
        if not isinstance(entry, dict) or entry.get("loaded") is not True:
            reasons.add("route_map_not_loaded", name)
    by_name = {}
    for c in _get(rec, "connections", list):
        if isinstance(c, dict) and isinstance(c.get("name"), str):
            by_name.setdefault(c["name"], []).append(c)
    for want_c in manifest["routes"]["connections"]:
        got = by_name.get(want_c["name"], [])
        if len(got) != 1 or got[0].get("loaded") is not True or not same(got[0].get("from"), want_c["from"]) \
                or not same(got[0].get("to"), want_c["to"]):
            reasons.add("route_exit_not_effective", want_c["name"])
    got_imports = [(i.get("path"), i.get("sha256"), i.get("loaded")) for i in _get(rec, "npc_imports", list) if isinstance(i, dict)]
    role_of = {f["relpath"]: role for role, f in manifest["story"]["files"].items()}
    for rel in manifest["npc_imports"]:
        hits = [g for g in got_imports if g[0] == rel]
        if len(hits) != 1 or hits[0][1] != ctx["staged_sha"].get(role_of[rel]) or hits[0][2] is not True:
            reasons.add("npc_import_not_effective", rel)
    qdb = _get(rec, "quest_db")
    layers = qdb.get("layers")
    if not isinstance(layers, list) or not layers:
        reasons.add("quest_db_layers_unknown", "effective quest DB layers are not recorded")
    else:
        for layer in layers:
            if not isinstance(layer, dict) or not is_bool(layer.get("clear")):
                reasons.add("quest_db_layers_unknown", canon(layer)[:120])
            elif layer["clear"]:
                reasons.add("quest_db_clear", "effective layer %r clears QUEST_DB" % layer.get("source"))
        if not any(isinstance(x, dict) and x.get("sha256") == ctx["staged_sha"].get("story.quest_db") for x in layers):
            reasons.add("quest_db_import_missing", "no effective layer is the staged quest_db.yml")
    expected = {r["id"]: r["title_sha256"] for r in manifest["quests"]["rows"]}
    seen = {}
    for row in _get(qdb, "rows", list):
        if isinstance(row, dict) and is_int(row.get("id")):
            seen.setdefault(row["id"], []).append(row)
    for qid, title in expected.items():
        got = seen.get(qid, [])
        if not got:
            reasons.add("quest_row_not_effective", str(qid))
        elif len(got) > 1 or got[0].get("title_sha256") != title:
            reasons.add("quest_row_effective_mismatch", str(qid))
    collisions = rec.get("collisions")
    if not isinstance(collisions, list):
        reasons.add("collisions_unknown", "collision evidence is not recorded")
    else:
        for c in collisions:
            if not isinstance(c, dict) or c.get("identical") is not True or c.get("resolved") is not True:
                reasons.add("collision_unresolved", canon(c)[:160])


def check_reference(manifest, rec, ctx, mode, reasons):
    """The full-reference expectation record. Its bytes are independently
    pinned by the manifest, so a coherent change refuses as a pin mismatch;
    these checks make the pinned record internally complete."""
    _common_record(rec, REFERENCE_SCHEMA, "text_reference", mode, manifest, reasons)
    tex = manifest["text_expectations"]
    if rec.get("complete") is not True:
        reasons.add("text_reference_incomplete", "complete is not true")
    if rec.get("hash_basis") != tex["hash_basis"]:
        reasons.add("text_reference_basis", repr(rec.get("hash_basis")))
    src = _get(rec, "source_table")
    table = manifest["text"]["files"]["text.table"]
    if not _int_eq(src.get("bytes"), table["bytes"]) or src.get("sha256") != table["sha256"] \
            or src.get("sha256") != ctx["staged_sha"].get("text.table"):
        reasons.add("text_reference_source_mismatch", "reference is not derived from the pinned and staged True table")
    records = _get(rec, "records")
    if sorted(records) != sorted(str(q) for q in QUEST_IDS):
        reasons.add("text_reference_incomplete", "records must be exactly %s" % list(QUEST_IDS))
    out = {}
    for qid in QUEST_IDS:
        r = records.get(str(qid))
        if not isinstance(r, dict):
            reasons.add("text_reference_incomplete", "no record for %d" % qid)
            continue
        desc = r.get("description_sha256")
        count = r.get("description_elements")
        if not isinstance(desc, list) or not desc or not all(is_sha(d) for d in desc) \
                or not is_int(count) or count != len(desc):
            reasons.add("text_reference_incomplete", "%d lacks a complete counted Description element list" % qid)
            continue
        if r.get("title_sha256") != tex["public_title_sha256"][str(qid)]:
            reasons.add("text_reference_title_mismatch", str(qid))
        if r.get("summary_sha256") != tex["public_summary_sha256"][str(qid)]:
            reasons.add("text_reference_summary_mismatch", str(qid))
        out[qid] = {"title_sha256": r.get("title_sha256"), "summary_sha256": r.get("summary_sha256"), "description_sha256": desc}
    ctx["reference"] = out


def check_text_effective(manifest, rec, packet, ctx, mode, reasons):
    _common_record(rec, TEXT_EFFECTIVE_SCHEMA, "text_effective", mode, manifest, reasons)
    tex = manifest["text_expectations"]
    table = manifest["text"]["files"]["text.table"]
    env = _get(rec, "environment")
    if env.get("executable_sha256") != ctx["executable_sha256"] or env.get("effective_config_sha256") != ctx["config_sha256"]:
        reasons.add("text_environment_mismatch", "text evidence is from a different executable/configuration")
    gen = _get(rec, "generated_resource")
    if gen.get("path") != tex["resource"] or not _int_eq(gen.get("bytes"), table["bytes"]) or gen.get("sha256") != table["sha256"] \
            or gen.get("sha256") != ctx["staged_sha"].get("text.table"):
        reasons.add("text_resource_mismatch", "generated resource is not the staged/pinned table")
    expected = _get(packet, "expected")
    server = expected.get("selected_server")
    array = expected.get("custom_quest_info")
    if not isinstance(server, str) or not server or not isinstance(array, list) or not all(isinstance(x, str) for x in array):
        reasons.add("text_expectation_missing", "packet.expected needs selected_server and custom_quest_info")
    else:
        if array.count(tex["resource"]) != 1:
            reasons.add("text_expectation_missing", "expected customQuestInfo must name the resource exactly once")
        if rec.get("selected_server") != server:
            reasons.add("text_server_mismatch", repr(rec.get("selected_server")))
        if not same(rec.get("custom_quest_info"), array):
            reasons.add("text_array_mismatch", "effective customQuestInfo array/order differs")
    if not same(rec.get("decoder"), tex["decoder"]):
        reasons.add("text_decoder_mismatch", canon(rec.get("decoder")))
    if not same(rec.get("diagnostic_quest_ids"), list(QUEST_IDS)):
        reasons.add("text_diagnostic_scope", "diagnostics must cover exactly %s" % list(QUEST_IDS))
    records = _get(rec, "records")
    ref = ctx.get("reference", {})
    for qid in QUEST_IDS:
        r = records.get(str(qid))
        if not isinstance(r, dict):
            reasons.add("text_record_missing", str(qid))
            continue
        if qid not in ref:
            continue
        for key in ("title_sha256", "summary_sha256", "description_sha256"):
            if not same(r.get(key), ref[qid][key]):
                reasons.add("text_record_mismatch", "%d %s" % (qid, key.split("_")[0]))


# --------------------------------------------------------------------- driver


def load_manifest(path, mode, reasons):
    try:
        raw, size, digest = read_explicit(path, JSON_CAP)
        manifest = parse_json(raw, "manifest")
    except InputError as exc:
        reasons.add("manifest_" + exc.code, exc.detail)
        return None, None
    except Malformed as exc:
        reasons.add("manifest_malformed", exc)
        return None, None
    info = {"path": path, "bytes": size, "sha256": digest}
    if manifest.get("schema") != MANIFEST_SCHEMA:
        reasons.add("manifest_malformed", "schema %r" % manifest.get("schema"))
        return None, info
    want = "synthetic" if mode == "synthetic" else "actual"
    if manifest.get("manifest_class") != want:
        reasons.add("manifest_class", "%r in %s mode" % (manifest.get("manifest_class"), mode))
        return None, info
    return manifest, info


def unpinned(manifest):
    """Every expected value Root has not pinned yet. Any gap refuses in both modes."""
    nat = manifest["native"]
    gaps = []
    for key in ("stock_executable_sha256", "image_id", "abi"):
        if nat.get(key) is None:
            gaps.append("native." + key)
    for key in ("bytes", "sha256"):
        if nat["executable"].get(key) is None:
            gaps.append("native.executable." + key)
    for section in ("story", "text"):
        for role, pin in manifest[section]["files"].items():
            if pin.get("bytes") is None or pin.get("sha256") is None:
                gaps.append(role)
    for role in QUALIFIED_ROLES:
        pin = manifest["qualification_pins"].get(role) or {}
        if pin.get("bytes") is None or pin.get("sha256") is None:
            gaps.append("qualification_pins." + role)
    return gaps


def _pin_of(manifest, role):
    for section in ("story", "text", "app"):
        if role in manifest[section]["files"]:
            return manifest[section]["files"][role]
    if role == "native.patch":
        return manifest["native"]["patch"]
    if role == "native.executable":
        return manifest["native"]["executable"]
    return manifest["qualification_pins"].get(role)


def _read_role(role, path, manifest, reasons, inputs, data, declared=None):
    try:
        body, size, digest = read_explicit(path, _role_cap(role), keep=role not in STREAMED)
    except InputError as exc:
        reasons.add(exc.code, "%s: %s" % (role, exc.detail))
        return
    inputs[role] = {"bytes": size, "sha256": digest}
    if declared is not None and (not _int_eq(declared.get("bytes"), size) or declared.get("sha256") != digest):
        reasons.add("packet_pin_mismatch", role)
        return
    pin = _pin_of(manifest, role)
    if pin is not None and pin.get("sha256") is not None and (not _int_eq(pin.get("bytes"), size) or pin["sha256"] != digest):
        reasons.add("release_pin_mismatch", role)
    data[role] = body


def evaluate(mode, manifest_path, packet_path):
    reasons = Reasons()
    result = {
        "schema": RESULT_SCHEMA,
        "mode": mode,
        "status": "refused",
        "admitted": False,
        "boundary": "Consistency of explicit evidence against independently pinned expectations only; "
                    "Root establishes runtime facts. No install, journal, save or play acceptance is implied.",
    }
    try:
        _, gsize, gsha = read_explicit(os.path.abspath(__file__), TEXT_CAP, keep=False)
        result["gate"] = {"bytes": gsize, "sha256": gsha}
    except InputError:
        result["gate"] = None
    manifest, minfo = load_manifest(manifest_path, mode, reasons)
    result["manifest"] = minfo
    inputs = {}
    result["inputs"] = inputs
    if manifest is None:
        return _finish(result, reasons, mode)
    for gap in unpinned(manifest):
        reasons.add("manifest_unpinned", "%s awaits Root's reviewed pin" % gap)
    try:
        if packet_path is None:
            raise InputError("input_missing", "no --packet")
        raw, size, digest = read_explicit(packet_path, JSON_CAP)
        packet = parse_json(raw, "packet")
        result["packet"] = {"path": packet_path, "bytes": size, "sha256": digest}
    except InputError as exc:
        reasons.add("packet_" + exc.code, exc.detail)
        return _finish(result, reasons, mode)
    except Malformed as exc:
        reasons.add("packet_malformed", exc)
        return _finish(result, reasons, mode)
    if packet.get("schema") != PACKET_SCHEMA:
        reasons.add("packet_malformed", "schema %r" % packet.get("schema"))
    if packet.get("record_class") != ("synthetic" if mode == "synthetic" else "actual"):
        reasons.add("packet_record_class", "%r in %s mode" % (packet.get("record_class"), mode))
    if packet.get("release_id") != manifest["release_id"]:
        reasons.add("packet_release_mismatch", repr(packet.get("release_id")))
    declared = packet.get("inputs") if isinstance(packet.get("inputs"), dict) else None
    roots = packet.get("roots") if isinstance(packet.get("roots"), dict) else None
    if declared is None or roots is None:
        reasons.add("packet_malformed", "packet needs roots {story, text} and inputs role -> {path, bytes, sha256}")
        return _finish(result, reasons, mode)
    for key in sorted(set(roots) - {"story", "text"}):
        reasons.add("packet_unknown_role", "roots." + key)
    required = manifest["required_roles"]
    for role in sorted(set(declared) - set(required)):
        reasons.add("packet_unknown_role", role)
    data = {}
    staged_roles = []
    for label in ("story", "text"):
        spec = manifest[label]
        staged_roles.extend(spec["files"])
        if label not in roots:
            reasons.add("input_missing", "staged %s root not supplied" % label)
            continue
        found = census(roots[label], spec, label, reasons)
        if found is None:
            continue
        result.setdefault("roots", {})[label] = roots[label]
        for role, path in sorted(found.items()):
            _read_role(role, path, manifest, reasons, inputs, data)
    for role in required:
        entry = declared.get(role)
        if entry is None:
            reasons.add("input_missing", "role %s not supplied" % role)
            continue
        if not isinstance(entry, dict) or not is_int(entry.get("bytes")) or not is_sha(entry.get("sha256")):
            reasons.add("packet_entry_malformed", role)
            continue
        _read_role(role, entry.get("path"), manifest, reasons, inputs, data, declared=entry)
    if all(r in data for r in manifest["story"]["files"]):
        check_story_static(manifest, data, reasons)
    if "text.mod_json" in data:
        check_text_static(manifest, data, reasons)
    ctx = {
        "executable_sha256": inputs.get("native.executable", {}).get("sha256"),
        "executable_bytes": inputs.get("native.executable", {}).get("bytes"),
        "parser_log_sha256": inputs.get("native.parser_log", {}).get("sha256"),
        "config_sha256": inputs.get("effective.config", {}).get("sha256") if "effective.config" in data else None,
        "staged_sha": {r: v["sha256"] for r, v in inputs.items() if r in data},
        "relpath": {r: f["relpath"] for r, f in manifest["story"]["files"].items()},
    }
    if "native.parser_log" in data:
        check_parser_log(data["native.parser_log"], reasons)
    for role, check in (("native.qualification", check_native), ("effective.facts", check_facts),
                        ("text.reference", check_reference)):
        if role not in data:
            continue
        try:
            rec = parse_json(data[role], role)
            check(manifest, rec, ctx, mode, reasons)
        except Malformed as exc:
            reasons.add("evidence_malformed", "%s: %s" % (role, exc))
        except (TypeError, KeyError, AttributeError, ValueError) as exc:
            reasons.add("evidence_malformed", "%s: %s" % (role, type(exc).__name__))
    if "text.effective" in data:
        try:
            rec = parse_json(data["text.effective"], "text.effective")
            check_text_effective(manifest, rec, packet, ctx, mode, reasons)
        except Malformed as exc:
            reasons.add("evidence_malformed", "text.effective: %s" % exc)
        except (TypeError, KeyError, AttributeError, ValueError) as exc:
            reasons.add("evidence_malformed", "text.effective: %s" % type(exc).__name__)
    return _finish(result, reasons, mode)


def _finish(result, reasons, mode):
    result["reasons"] = reasons.items
    result["reasons_truncated"] = reasons.dropped
    if reasons:
        result["status"] = "refused"
        result["admitted"] = False
    elif mode == "synthetic":
        result["status"] = "synthetic_consistent"
        result["admitted"] = False
    else:
        result["status"] = "admitted"
        result["admitted"] = True
    return result


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--packet", help="absolute path of the admission packet JSON")
    ap.add_argument("--synthetic", action="store_true", help="authored-fixture mode; never admits")
    ap.add_argument("--manifest", help="synthetic mode only: absolute path of a synthetic manifest")
    args = ap.parse_args(argv)
    if args.synthetic and not args.manifest:
        ap.error("--synthetic requires --manifest")
    if args.manifest and not args.synthetic:
        ap.error("real mode uses the bundled manifest; --manifest is synthetic-only")
    mode = "synthetic" if args.synthetic else "real"
    manifest = args.manifest if args.synthetic else BUNDLED_MANIFEST
    result = evaluate(mode, manifest, args.packet)
    sys.stdout.write(json.dumps(result, ensure_ascii=False, indent=1) + "\n")
    return 0 if result["status"] in ("admitted", "synthetic_consistent") else 1


if __name__ == "__main__":
    sys.exit(main())
