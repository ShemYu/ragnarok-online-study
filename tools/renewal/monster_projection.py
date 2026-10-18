#!/usr/bin/env python3
"""Project ten declared MOB_DB fields and conditional prefix operations from the raw catalog.

Inputs are the canonical T06.001 snapshot (verified in full by the unmodified
server_selection.read_snapshot default pins) and the selected T06.002.003.001
raw YAML catalog 1.0.1 (manifest, completion record and the whole 38538-line
raw-declarations.jsonl, each pinned by size and SHA-256). The catalog's
marker -> manifest -> records relationships, generator/parser/profile identity
and snapshot identity are checked against the fresh snapshot; every raw line,
ordinal and visit range is validated, and only MOB_DB rows are kept, in their
original global order.

The distinct MOB visit files are reparsed once each by the unchanged selected
Psych AST adapter (whole-file context), and every complete raw row object is
reconstructed with the selected helpers and must equal its prerequisite row.

For each raw declaration the tool records every exact top-level occurrence of
Id, AegisName, Name, JapaneseName, Level, Hp, Sp, BaseExp, JobExp and MvpExp,
the first-key selected value, the exact 24-byte stored name prefix and two
conditional branches (if_existing / if_fresh) following MobDatabase::
parseBodyNode (mob.cpp 5022-5141) at rAthena 0693b8c. Database membership,
later parsing (Attack .. Drops), fresh insertion and runtime EXP are never
decided: they stay explicit gaps. Nothing is merged into an accepted or
effective monster table.

Output: monster-declarations.jsonl (streamed), monster-id-history.jsonl,
monster-projection-manifest.json and, only when the status is complete,
monster-projection-complete.json written last. Standard library only. Output
directories are never overwritten.
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import time
import types

VERSION = "1.0.0"
TOOL = "tools/renewal/monster_projection.py"
OUTPUT_DECLARATIONS = "monster-declarations.jsonl"
OUTPUT_HISTORY = "monster-id-history.jsonl"
OUTPUT_MANIFEST = "monster-projection-manifest.json"
OUTPUT_COMPLETE = "monster-projection-complete.json"
DATABASE = "MOB_DB"
SERVER_ROOT = "rathena/"

# Selected, unchanged prerequisite tools (checked before import/invocation).
SELECTED_TOOLS = {
    "yaml_graph_inventory.py": (73057,
                                "7962cb6e2b6fe4a6762f703263ff8afaff6f1abf6e6ad6be1d73915ac7678990"),
    "server_selection.py": (36455,
                            "22a3f4c8016e4e38608039084eb762440f9c56dd611e2af44be151fdf3c24417"),
}
SELECTED_GENERATOR = {
    "tool": "tools/renewal/yaml_graph_inventory.py",
    "version": "1.0.1",
    "source_sha256": SELECTED_TOOLS["yaml_graph_inventory.py"][1],
}

# Selected raw catalog outputs (integrated-1, corrected 1.0.1 from e10398a).
PREREQ_PINS = {
    "manifest": {"name": "yaml-graph-manifest.json", "bytes": 56125,
                 "sha256": "60fc99c4259743170e2239648539e1bc1757299f4168484b96ac7c736b76f98a"},
    "complete": {"name": "yaml-graph-complete.json", "bytes": 428,
                 "sha256": "a666d99d56143c8b38e6558da180b922f26275dad08463af192b3d771a12f41c"},
    "records": {"name": "raw-declarations.jsonl", "bytes": 49723211, "lines": 38538,
                "sha256": "a9366bcd9c36d4747996d44b804a62aecde6bef1e4feb4252a1ff110a41d6230"},
}
# Canonical MOB selection, derived from the bound catalog and cross-checked (not entity totals).
CANONICAL_MOB = {"visits": [9, 10, 11], "rows": 2699, "first_global_ordinal": 30991,
                 "last_global_ordinal": 33689, "epochs": [0], "clear_events": 0,
                 "files": ["db/mob_db.yml", "db/re/mob_db.yml", "db/import/mob_db.yml"]}
MOB_FILE_PINS = {
    "db/mob_db.yml": (5219, "4ea93a5f2be879cead5a066605fa156156781a6d4f7e18df8e6c156678ac6feb"),
    "db/re/mob_db.yml": (2317420,
                         "ee239d4777d571bad2fc3f6e4710e04aea954ff0a7dfea6c32bffd9f458d8dc6"),
    "db/import/mob_db.yml": (26972,
                             "5dc1d1d2517f1c0e82c4e465855ee908a6fb22da27a69ba779d7f363a9b22da3"),
}

SOURCE = {
    "repository": "rathena",
    "revision": "0693b8c69911d5ca42269684aa036b67d67f4d3e",
    "files": {
        "src/map/mob.cpp": "0e0ded18ebeeca1ab9071ff6d50882ea2325882274fc734a44a7c3c62d89a090",
        "src/map/mob.hpp": "7e931afe57d0e9436356d68c4f5a528ab57daa996f600d57f9a4a191175b1da4",
        "src/common/database.cpp":
            "03d394aa9ed809557fb4ce50419776e34214220504ef1229ec864a4b10be0011",
        "src/common/database.hpp":
            "1b54c493748f34907cd26e5be27959fc4bdbb2ea041ef32637dc01dd98fbad3e",
        "src/common/mmo.hpp": "883ec2048b726d51f897218989ca66c476bcdbc969d683025fe09a0bf280fa6d",
        "3rdparty/rapidyaml/src/c4/yml/tree.cpp":
            "9639cbb9aaeb4bcb418f237f02a7f0284f63ba32f59c4be153216e4f5a4e4834",
        "3rdparty/rapidyaml/src/c4/yml/tree.hpp":
            "37891f845f593a2e0c9748ab27c5e6d2987168e2714b7a52787f3bad3308601e",
        "3rdparty/rapidyaml/src/c4/yml/node.hpp":
            "ee3cb79d3e7138e59d82942a662c4875008fa80cd83cade16f502a66a3b601e9",
        "3rdparty/rapidyaml/ext/c4core/src/c4/charconv.hpp":
            "878d25a17bb4f4221a4d16585d1b3a88e027cbc0aa89fac5a6844feef5382d2c",
        "3rdparty/rapidyaml/ext/c4core/src/c4/std/string.hpp":
            "3415592bc19d77b56e0d326132e19284d1ee9140ea9d4f49deb4f826611e9f21",
    },
    "rules": {
        "id_ranges": "mob.cpp:62-65 MIN_MOB_DB 1000, MAX_MOB_DB 3999, MIN_MOB_DB2 20020, "
                     "MAX_MOB_DB2 31999; mob.cpp:5028 strict (1000 < Id < 3999) || "
                     "(20020 < Id < 31999)",
        "constructor": "mob.cpp:4979-5015 s_mob_db(): names empty, base/job/mvp exp 0, lv 1, "
                       "status.max_hp 1, status.max_sp 1",
        "parse_body_node": "mob.cpp:5022-5141 Id asUInt32 -> range -> find -> (fresh: "
                           "nodesExist AegisName+Name, make_shared, id, LOOK_BASE) -> AegisName "
                           "-> Name -> JapaneseName (fresh absent: copy name) -> Level asUInt16 "
                           "-> Hp/Sp asUInt32 -> BaseExp/JobExp/MvpExp asUInt64 * rate",
        "names": "mob.cpp:5045-5087 asString, warning when size() > NAME_LENGTH, "
                 "resize(NAME_LENGTH) (truncate or NUL-pad) then assign",
        "exp": "mob.cpp:5116-5141 static_cast<t_exp>(cap_value((double)exp * "
               "(double)battle_config.<base|job|mvp>_exp_rate / 100., 0, MAX_EXP))",
        "later_parser": "mob.cpp:5143-5574 Attack .. Drops, any can return 0",
        "insertion": "mob.cpp:5576-5577 if (!exists) put(mob_id, mob)",
        "mob_struct": "mob.hpp:261-299 sprite/name/jname std::string, t_exp, uint16 lv; "
                      "MobDatabase(\"MOB_DB\", 5, 1), TypesafeCachedYamlDatabase<uint32,...>",
        "name_length": "mmo.hpp:154 NAME_LENGTH (23 + 1)",
        "node_exists": "database.cpp:15-17 num_children() > 0 && has_child(name)",
        "nodes_exist": "database.cpp:19-34 every name checked, any missing -> false",
        "as_type": "database.cpp:230-251 missing -> false; val_is_null -> false; >> may throw",
        "find_put": "database.hpp:95-123,164-175 find by key, put overwrites map entry",
        "find_child": "tree.cpp:1580-1600 first mapping child whose key equals the name",
        "val_is_null": "tree.hpp:584 not quoted and (nullptr, ~, null, Null, NULL)",
        "c4_read": "node.hpp read / c4 charconv atou: other bases and overflow behaviour "
                   "exist natively and are not emulated (policy gap)",
    },
}

FIELDS = ("Id", "AegisName", "Name", "JapaneseName", "Level", "Hp", "Sp",
          "BaseExp", "JobExp", "MvpExp")
NAMES = ("AegisName", "Name", "JapaneseName")
NUMERIC = {
    "Id": ("uint32", str(0xFFFFFFFF)),
    "Level": ("uint16", str(0xFFFF)),
    "Hp": ("uint32", str(0xFFFFFFFF)),
    "Sp": ("uint32", str(0xFFFFFFFF)),
    "BaseExp": ("uint64", str(0xFFFFFFFFFFFFFFFF)),
    "JobExp": ("uint64", str(0xFFFFFFFFFFFFFFFF)),
    "MvpExp": ("uint64", str(0xFFFFFFFFFFFFFFFF)),
}
NAME_LENGTH = 24
ID_RANGES = ((1001, 3998), (20021, 31998))
TARGETS = {"AegisName": "sprite", "Name": "name", "JapaneseName": "jname", "Level": "lv",
           "Hp": "status.max_hp", "Sp": "status.max_sp", "BaseExp": "base_exp",
           "JobExp": "job_exp", "MvpExp": "mexp"}
EXP_RATES = {"BaseExp": "battle_config.base_exp_rate", "JobExp": "battle_config.job_exp_rate",
             "MvpExp": "battle_config.mvp_exp_rate"}
CONSTRUCTOR = {"sprite": "empty string", "name": "empty string", "jname": "empty string",
               "lv": 1, "status.max_hp": 1, "status.max_sp": 1, "base_exp": 0, "job_exp": 0,
               "mexp": 0}
LINES = {"Id": "mob.cpp:5025-5026", "gate": "mob.cpp:5028-5031", "find": "mob.cpp:5033-5034",
         "mandatory": "mob.cpp:5036-5038", "construct": "mob.cpp:5040-5042",
         "AegisName": "mob.cpp:5045-5057", "Name": "mob.cpp:5059-5071",
         "JapaneseName": "mob.cpp:5073-5087", "Level": "mob.cpp:5089-5096",
         "Hp": "mob.cpp:5098-5105", "Sp": "mob.cpp:5107-5114", "BaseExp": "mob.cpp:5116-5123",
         "JobExp": "mob.cpp:5125-5132", "MvpExp": "mob.cpp:5134-5141",
         "later": "mob.cpp:5143-5574", "put": "mob.cpp:5576-5577"}

# Projection caps (refusal policy, not native behaviour). Parser caps are the selected LIMITS.
CAPS = {
    "max_mob_files": 3,
    "max_declarations": 100_000,
    "max_target_occurrences": 1_000_000,
    "max_declaration_file_bytes": 256 << 20,
    "max_history_file_bytes": 64 << 20,
    "max_manifest_bytes": 16 << 20,
    "max_diagnostics": 10_000,
    "max_raw_line_bytes": 16 << 20,
}

REACH = {"reached": "reached", "return0": "not_reached_after_return0",
         "gap": "unresolved_after_gap", "id_stage": "not_reached_id_stage"}

EXCLUSIONS = [
    "database membership: no membership map; each declaration has if_existing and if_fresh "
    "branches and neither is selected from earlier declarations",
    "later parsing mob.cpp:5143-5574 (Attack onwards, constants, references, status, "
    "collections, drops) and therefore full-row success and native accepted row counts",
    "fresh insertion mob.cpp:5576-5577 (conditional on all later parsing succeeding)",
    "runtime EXP: battle_config rates, double arithmetic, MAX_EXP cap and cast",
    "loadingFinished (HP/SP minimum 1, rates, status_calc_misc, cache), reload, constructor "
    "and global-cache side effects",
    "SQL branches, installed configuration, auxiliary chat/skill/appearance/summon/drop-ratio "
    "databases, spawned names and runtime data",
    "native rapidyaml parity and c4 numeric conversion of other bases/overflow",
    "rendered labels, sprite/ACT paths (AegisName is a server identifier), Traditional-Chinese "
    "quality, episode or playable coverage",
]
LIMIT_NOTES = (
    "Parser caps are inherited unchanged from the selected yaml_graph_inventory LIMITS; at "
    "most the selected MOB files are parsed, one at a time, each once. Projection caps are "
    "refusal policy, not native behaviour.",
    "There is no hard memory bound: Psych builds its AST before node/scalar checks and the "
    "full snapshot reader retains verified bytes.",
    "Publication reserves the output with an exclusive private mkdir and writes the "
    "completion record last. A same-user concurrent writer could interfere between steps; "
    "without monster-projection-complete.json the output is not complete.",
)
STATUS_MEANING = {
    "complete": "every prerequisite MOB raw declaration was reconstructed from the reparsed "
                "source, matched its raw row exactly, and its ten fields and both conditional "
                "prefix branches were projected without a projection gap; membership, later "
                "parsing, insertion and runtime values stay unresolved by design",
    "qualified": "every declaration was projected, but at least one reached field is outside "
                 "the bounded projection profile (policy/extraction gap); no marker",
    "unsupported": "a parser, provenance or work-limit stop prevented projecting the suffix; "
                   "the emitted declarations are a qualified prefix; no marker",
}

DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


class ProjectionError(ValueError):
    category = "error"


class InputError(ProjectionError):
    """Input identity, prerequisite relationship or selected-tool refusal (exit 2)."""
    category = "input"


class OutputError(ProjectionError):
    """Publication refusal or failure (exit 2)."""
    category = "publication"


class Halt(Exception):
    """A qualified stop: certain projection ends here; the suffix is unresolved."""

    def __init__(self, kind, detail, **extra):
        super().__init__(f"{kind}: {detail}")
        self.record = {"kind": kind, "detail": detail, **extra}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical_json(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def render(document):
    return (json.dumps(document, ensure_ascii=True, indent=1, sort_keys=True,
                       allow_nan=False) + "\n").encode("ascii")


def render_row(row):
    return (canonical_json(row) + "\n").encode("ascii")


def strict_json(data, what):
    """Strict JSON: UTF-8, duplicate keys and NaN/Infinity refused."""
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key {key!r}")
            result[key] = value
        return result

    def constant(name):
        raise ValueError(f"non-finite number {name}")
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs,
                          parse_constant=constant)
    except (UnicodeDecodeError, ValueError) as exc:
        raise InputError(f"{what}: invalid strict JSON ({exc})") from None


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def _read_fd(fd, size, what):
    """Read exactly a pinned size from a verified regular descriptor; refuse growth/changes."""
    info = os.fstat(fd)
    if not stat.S_ISREG(info.st_mode):
        raise InputError(f"{what}: not a regular file")
    if info.st_size != size:
        raise InputError(f"{what}: {info.st_size} bytes, pinned {size}")
    chunks, total = [], 0
    while total <= size:
        chunk = os.read(fd, min(1 << 20, size + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
    after = os.fstat(fd)
    if total != size or _identity(info) != _identity(after):
        raise InputError(f"{what}: changed while being read")
    return b"".join(chunks)


def read_pinned(path, size, digest, what, dir_fd=None):
    """No-follow, nonblocking open; regular file of the pinned size and SHA-256."""
    try:
        fd = os.open(path, FILE_FLAGS, dir_fd=dir_fd)
    except OSError as exc:
        raise InputError(f"{what}: cannot open without following links ({exc.strerror})") \
            from None
    try:
        data = _read_fd(fd, size, what)
    finally:
        os.close(fd)
    if digest is not None and sha256(data) != digest:
        raise InputError(f"{what}: SHA-256 {sha256(data)} is not the pinned {digest}")
    return data


# --- Selected tools ----------------------------------------------------------------------

_SELECTED = {}


def selected(directory=None):
    """Load the unchanged selected yaml_graph_inventory after checking both tools' bytes."""
    here = Path(directory or Path(__file__).resolve().parent)
    key = str(here)
    if key not in _SELECTED:
        identities, code = {}, None
        for name, (size, digest) in SELECTED_TOOLS.items():
            data = read_pinned(str(here / name), size, digest, f"selected {name}")
            identities[name] = {"path": "tools/renewal/" + name, "bytes": size,
                                "sha256": digest}
            if name == "yaml_graph_inventory.py":
                code = data
        module = types.ModuleType("_monster_projection_yaml_graph")
        module.__file__ = str(here / "yaml_graph_inventory.py")
        exec(compile(code, module.__file__, "exec"), module.__dict__)  # verified bytes only
        if module.VERSION != SELECTED_GENERATOR["version"]:
            raise InputError(f"selected tool version {module.VERSION} is not 1.0.1")
        _SELECTED[key] = (module, identities)
    return _SELECTED[key]


def expected_parser(yg, versions):
    """The parser record the selected generator writes (yaml_graph_inventory.run)."""
    return {"executable": yg.RUBY, **versions, "api": "Psych.parse_stream AST only",
            "adapter_sha256": sha256(yg.ADAPTER.encode("utf-8")),
            "native_parity": "not established (rapidyaml 0.4.0 is the native parser)"}


def fresh_input_identity(manifest_bytes, files, reader):
    return {"snapshot_manifest_sha256": sha256(manifest_bytes), "files": len(files),
            "bytes": sum(len(b) for b in files.values()), "verification": reader}


# --- Prerequisite identity bridge ----------------------------------------------------------

RAW_KEYS = frozenset(("byte_span", "database", "database_ordinal", "end_mark", "epoch",
                      "field_count", "fields", "file", "file_sha256", "fingerprint_sha256",
                      "global_ordinal", "local_ordinal", "node_count", "raw_ids", "root_order",
                      "span_sha256", "start_mark", "visit"))


def _int(value):
    return type(value) is int and value >= 0


class Prerequisite:
    """Verified selected catalog: manifest, marker relationship and the MOB raw rows."""

    def __init__(self):
        self.manifest = self.complete = None
        self.identity = {}
        self.mob_rows = {}      # global ordinal -> unchanged raw row dict
        self.mob_visits = []
        self.mob_clears = []
        self.selection = {}
        self.stream = {}


def check_marker_and_manifest(complete, manifest, manifest_sha, pins, fresh_input, profile,
                              yg, parser):
    if not isinstance(complete, dict) or not isinstance(manifest, dict):
        raise InputError("prerequisite marker/manifest is not an object")
    want = {"generator_version": SELECTED_GENERATOR["version"], "status": "complete",
            "manifest": pins["manifest"]["name"], "manifest_sha256": manifest_sha,
            "records_file": pins["records"]["name"], "records_sha256": pins["records"]["sha256"]}
    for key, value in want.items():
        if complete.get(key) != value:
            raise InputError(f"prerequisite completion {key} is {complete.get(key)!r}, "
                             f"expected {value!r}")
    if set(complete) != set(want) | {"relationship"}:
        raise InputError("prerequisite completion record has unexpected keys")
    checks = {
        "status": "complete",
        "generator": SELECTED_GENERATOR,
        "parser": parser,
        "profile": profile,
        "input": fresh_input,
        "source": yg.SOURCE,
        "stop": None,
        "unresolved": [],
        "known_failures": [],
    }
    for key, value in checks.items():
        if manifest.get(key) != value:
            raise InputError(f"prerequisite manifest {key} does not match the selected/fresh "
                             f"identity")
    records = manifest.get("records_file")
    rec = pins["records"]
    if not isinstance(records, dict) or (records.get("file"), records.get("bytes"),
                                         records.get("lines"), records.get("sha256")) != \
            (rec["name"], rec["bytes"], rec["lines"], rec["sha256"]):
        raise InputError("prerequisite manifest records_file does not bind the pinned records")
    counts = manifest.get("counts")
    if not isinstance(counts, dict) or counts.get("raw_rows") != rec["lines"]:
        raise InputError("prerequisite manifest raw_rows does not equal the records lines")
    if not isinstance(manifest.get("visits"), list) or \
            not isinstance(manifest.get("clear_events"), list) or \
            not isinstance(manifest.get("databases"), dict):
        raise InputError("prerequisite manifest has no visits/clear_events/databases")


def select_mob(manifest, files, file_pins):
    """MOB visits in original order with header/body/epoch records, checked against bytes."""
    visits = manifest["visits"]
    for index, visit in enumerate(visits):
        if not isinstance(visit, dict) or visit.get("visit") != index:
            raise InputError(f"prerequisite visit {index} is malformed or out of order")
    mob = [v for v in visits if v.get("database") == DATABASE]
    for visit in mob:
        if visit.get("status") != "read_compatible" or visit.get("modeled_graph_return") \
                is not True:
            raise InputError(f"MOB visit {visit['visit']} is not read_compatible")
        path = visit.get("path")
        data = files.get(SERVER_ROOT + path) if isinstance(path, str) else None
        if data is None or len(data) != visit.get("bytes") or sha256(data) != visit.get("sha256"):
            raise InputError(f"MOB visit {visit['visit']} file does not match the snapshot")
        if file_pins is not None:
            pin = file_pins.get(path)
            if pin is None or pin != (len(data), sha256(data)):
                raise InputError(f"MOB visit file {path} is not a pinned MOB source file")
        body = visit.get("body")
        if not isinstance(body, dict) or not _int(body.get("rows")) or \
                not _int(body.get("epoch")):
            raise InputError(f"MOB visit {visit['visit']} body record is malformed")
        if body["rows"] and not _int(body.get("first_global_ordinal")):
            raise InputError(f"MOB visit {visit['visit']} has rows without an ordinal range")
    clears = [c for c in manifest["clear_events"] if isinstance(c, dict)
              and c.get("database") == DATABASE]
    return mob, clears


class RecordScan:
    """Validate every raw catalog line: canonical encoding, keys, ordinals and visit ranges."""

    def __init__(self, manifest):
        self.visits = manifest["visits"]
        self.per_db = {}
        self.per_visit = {}
        self.mob_rows = {}

    def line(self, index, data):
        row = strict_json(data, f"raw record {index}")
        if not isinstance(row, dict) or set(row) != RAW_KEYS:
            raise InputError(f"raw record {index} does not have the selected row keys")
        if render_row(row) != data:
            raise InputError(f"raw record {index} is not the selected canonical encoding")
        if row["global_ordinal"] != index:
            raise InputError(f"raw record {index} has global_ordinal {row['global_ordinal']}")
        number = row["visit"]
        if not _int(number) or number >= len(self.visits):
            raise InputError(f"raw record {index} names an unknown visit")
        visit = self.visits[number]
        body = visit.get("body") or {}
        first, rows = body.get("first_global_ordinal"), body.get("rows")
        if not (_int(first) and _int(rows) and first <= index < first + rows):
            raise InputError(f"raw record {index} lies outside visit {number}'s Body range")
        database = row["database"]
        want = {"database": visit.get("database"), "root_order": visit.get("root_order"),
                "file": visit.get("path"), "file_sha256": visit.get("sha256"),
                "epoch": body.get("epoch"), "local_ordinal": index - first,
                "database_ordinal": self.per_db.get(database, 0)}
        for key, value in want.items():
            if row[key] != value:
                raise InputError(f"raw record {index} {key} is {row[key]!r}, expected {value!r}")
        self.per_db[database] = self.per_db.get(database, 0) + 1
        self.per_visit[number] = self.per_visit.get(number, 0) + 1
        if database == DATABASE:
            self.mob_rows[index] = row


def scan_records(dir_fd, pin, line_cap, on_line):
    """Stream the whole records file through one verified descriptor, line by line."""
    what = f"prerequisite {pin['name']}"
    try:
        fd = os.open(pin["name"], FILE_FLAGS, dir_fd=dir_fd)
    except OSError as exc:
        raise InputError(f"{what}: cannot open without following links ({exc.strerror})") \
            from None
    hasher, total, lines = hashlib.sha256(), 0, 0
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode):
            raise InputError(f"{what}: not a regular file")
        if info.st_size != pin["bytes"]:
            raise InputError(f"{what}: {info.st_size} bytes, pinned {pin['bytes']}")
        buffer = bytearray()
        while True:
            chunk = os.read(fd, min(1 << 20, pin["bytes"] + 1 - total))
            if not chunk:
                break
            total += len(chunk)
            if total > pin["bytes"]:
                raise InputError(f"{what}: grew while being read")
            hasher.update(chunk)
            buffer += chunk
            start = 0
            while True:
                end = buffer.find(b"\n", start)
                if end < 0:
                    break
                if end + 1 - start > line_cap:
                    raise InputError(f"{what}: line {lines} exceeds {line_cap} bytes")
                on_line(lines, bytes(buffer[start:end + 1]))
                lines += 1
                start = end + 1
            del buffer[:start]
            if len(buffer) > line_cap:
                raise InputError(f"{what}: line {lines} exceeds {line_cap} bytes")
        if buffer:
            raise InputError(f"{what}: final line has no newline")
        after = os.fstat(fd)
        if _identity(info) != _identity(after):
            raise InputError(f"{what}: changed while being read")
    finally:
        os.close(fd)
    digest = hasher.hexdigest()
    if total != pin["bytes"] or digest != pin["sha256"] or lines != pin["lines"]:
        raise InputError(f"{what}: {total} bytes/{lines} lines/{digest} is not the pinned "
                         f"{pin['bytes']}/{pin['lines']}/{pin['sha256']}")
    return {"file": pin["name"], "bytes": total, "lines": lines, "sha256": digest}


def load_prerequisite(raw_catalog, files, fresh_input, yg, parser, pins=PREREQ_PINS,
                      profile=None, expected=CANONICAL_MOB, file_pins=MOB_FILE_PINS,
                      line_cap=CAPS["max_raw_line_bytes"]):
    """Verify the selected catalog relationships and return a Prerequisite (or InputError)."""
    profile = yg.PROFILE if profile is None else profile
    try:
        info = os.lstat(raw_catalog)
    except OSError as exc:
        raise InputError(f"raw catalog: {exc.strerror}") from None
    if not stat.S_ISDIR(info.st_mode):
        raise InputError(f"raw catalog is not a directory (or is a link): {raw_catalog}")
    try:
        dir_fd = os.open(raw_catalog, DIR_FLAGS)
    except OSError as exc:
        raise InputError(f"raw catalog: {exc.strerror}") from None
    prereq = Prerequisite()
    try:
        complete_bytes = read_pinned(pins["complete"]["name"], pins["complete"]["bytes"],
                                     pins["complete"]["sha256"],
                                     f"prerequisite {pins['complete']['name']}", dir_fd)
        manifest_bytes = read_pinned(pins["manifest"]["name"], pins["manifest"]["bytes"],
                                     pins["manifest"]["sha256"],
                                     f"prerequisite {pins['manifest']['name']}", dir_fd)
        complete = strict_json(complete_bytes, "prerequisite completion")
        manifest = strict_json(manifest_bytes, "prerequisite manifest")
        if render(complete) != complete_bytes or render(manifest) != manifest_bytes:
            raise InputError("prerequisite marker/manifest is not the selected rendering")
        manifest_sha = sha256(manifest_bytes)
        check_marker_and_manifest(complete, manifest, manifest_sha, pins, fresh_input, profile,
                                  yg, parser)
        mob_visits, clears = select_mob(manifest, files, file_pins)
        scan = RecordScan(manifest)
        stream = scan_records(dir_fd, pins["records"], line_cap, scan.line)
        names = sorted(os.listdir(dir_fd))
    finally:
        os.close(dir_fd)
    expected_names = sorted(p["name"] for p in pins.values())
    if names != expected_names:
        raise InputError(f"raw catalog holds {names}, expected exactly {expected_names}")
    for visit in manifest["visits"]:
        rows = (visit.get("body") or {}).get("rows", 0)
        if scan.per_visit.get(visit["visit"], 0) != rows:
            raise InputError(f"visit {visit['visit']} declares {rows} rows, stream has "
                             f"{scan.per_visit.get(visit['visit'], 0)}")
    for name, record in manifest["databases"].items():
        if not isinstance(record, dict) or scan.per_db.get(name, 0) != record.get("raw_rows"):
            raise InputError(f"database {name} raw_rows does not match the stream")
    if set(scan.per_db) - set(manifest["databases"]):
        raise InputError("stream holds a database the manifest does not list")
    ordinals = sorted(scan.mob_rows)
    selection = {
        "visits": [v["visit"] for v in mob_visits],
        "rows": len(ordinals),
        "first_global_ordinal": ordinals[0] if ordinals else None,
        "last_global_ordinal": ordinals[-1] if ordinals else None,
        "epochs": sorted({r["epoch"] for r in scan.mob_rows.values()}),
        "clear_events": len(clears),
        "files": list(dict.fromkeys(v["path"] for v in mob_visits)),
    }
    if expected is not None and selection != expected:
        raise InputError(f"derived MOB selection {selection} is not the canonical {expected}")
    if len(selection["files"]) > CAPS["max_mob_files"]:
        raise InputError("more MOB files than the selected profile allows")
    prereq.manifest, prereq.complete = manifest, complete
    prereq.mob_rows, prereq.mob_visits, prereq.mob_clears = scan.mob_rows, mob_visits, clears
    prereq.selection, prereq.stream = selection, stream
    prereq.identity = {
        "directory_files": names,
        "manifest": {"file": pins["manifest"]["name"], "bytes": len(manifest_bytes),
                     "sha256": manifest_sha},
        "complete": {"file": pins["complete"]["name"], "bytes": len(complete_bytes),
                     "sha256": sha256(complete_bytes)},
        "records": stream,
        "relationships": [
            "completion.manifest_sha256 == SHA-256(manifest bytes)",
            "completion.records_sha256 == manifest.records_file.sha256 == SHA-256(stream)",
            "manifest.records_file bytes/lines == streamed records",
            "manifest.generator == selected yaml_graph_inventory 1.0.1 bytes",
            "manifest.parser == fresh Ruby/Psych/libyaml identity + selected adapter SHA-256",
            "manifest.profile/source == selected profile/source",
            "manifest.input == freshly verified snapshot identity",
            "every line: canonical encoding, global/database/local ordinals, visit range, "
            "file/hash/epoch",
        ],
        "status": "complete",
        "generator": manifest["generator"],
    }
    return prereq


# --- Field observations --------------------------------------------------------------------

def decimal_value(text, maximum):
    """Bounded ASCII decimal: (value, None) or (None, reason). No unbounded int()."""
    if text and all("0" <= c <= "9" for c in text):
        significant = text.lstrip("0") or "0"
        if len(significant) < len(maximum) or (len(significant) == len(maximum)
                                               and significant <= maximum):
            return int(significant[:20], 10), None
        return None, "decimal_overflow"
    if text == "":
        return None, "empty_text"
    if text != text.strip(" \t\r\n\f\v") or any(c.isspace() for c in text):
        return None, "whitespace"
    if text[0] in "+-":
        return None, "sign"
    if len(text) > 1 and text[0] == "0" and text[1] in "xXbBoO":
        return None, "base_prefix"
    if any(c.isdigit() or c.isnumeric() for c in text if not ("0" <= c <= "9")):
        return None, "non_ascii_digit"
    return None, "other_text"


def name_bytes(text):
    """Exact std::string resize(NAME_LENGTH) of the UTF-8 bytes under this AST profile."""
    try:
        raw = text.encode("utf-8")
    except UnicodeEncodeError:
        return None
    stored = raw[:NAME_LENGTH] + b"\0" * max(0, NAME_LENGTH - len(raw))
    split = False
    if len(raw) > NAME_LENGTH:
        try:
            raw[:NAME_LENGTH].decode("utf-8")
        except UnicodeDecodeError:
            split = True
    return {"utf8_length": len(raw), "stored_bytes_hex": stored.hex(),
            "truncated": len(raw) > NAME_LENGTH, "warning": len(raw) > NAME_LENGTH,
            "nul_padding_bytes": max(0, NAME_LENGTH - len(raw)),
            "multibyte_split_at_limit": split,
            "embedded_nul_in_text": "\0" in text}


def interpret(field, value):
    """Selected first-occurrence value record -> declared status (no native acceptance)."""
    if value is None:
        return {"status": "absent"}
    if value["kind"] != "scalar":
        return {"status": "container", "kind": value["kind"]}
    if value["null"]:
        return {"status": "null"}
    if field in NUMERIC:
        target, maximum = NUMERIC[field]
        number, reason = decimal_value(value["text"], maximum)
        if reason is not None:
            return {"status": "unsupported", "target_type": target, "reason": reason}
        return {"status": "supported", "target_type": target, "value": number,
                "value_decimal": str(number)}
    projected = name_bytes(value["text"])
    if projected is None:
        return {"status": "unsupported", "reason": "text_not_utf8_encodable"}
    return {"status": "supported", **projected}


def observe(row, lines, yg):
    """Every exact top-level occurrence of the ten fields, first-key selection, case variants."""
    found = {name: [] for name in FIELDS}
    variants = {name.lower(): name for name in FIELDS}
    case_variants = {name: [] for name in FIELDS}
    for ordinal in range(len(row.children) // 2):
        key, value = row.children[2 * ordinal], row.children[2 * ordinal + 1]
        if key.value in found:
            record = yg.scalar_record(value, lines, cap=None)
            if value.kind != "S":
                record["fingerprint_sha256"] = sha256(
                    yg.canonical_json(yg.normalize(value)).encode("ascii"))
                record["node_count"] = yg.count_nodes(value)
            found[key.value].append({"field_ordinal": ordinal,
                                     "key": yg.scalar_record(key, lines, cap=None),
                                     "value": record})
        elif key.value.lower() in variants:
            case_variants[variants[key.value.lower()]].append(
                {"field_ordinal": ordinal, "key_text": key.value})
    fields = []
    for order, name in enumerate(FIELDS):
        occurrences = found[name]
        for index, occurrence in enumerate(occurrences):
            occurrence["role"] = "selected_first" if index == 0 else "ignored_duplicate"
        selected = occurrences[0]["value"] if occurrences else None
        fields.append({"field": name, "parser_order": order, "present": bool(occurrences),
                       "occurrence_count": len(occurrences),
                       "ignored_duplicates": max(0, len(occurrences) - 1),
                       "occurrences": occurrences, "case_variant_keys": case_variants[name],
                       "selected": interpret(name, selected)})
    return fields


# --- Conditional prefix operations ---------------------------------------------------------

def _convert(sel):
    """Reached conversion of a provided node: ('ok'|'return0'|'gap', reason)."""
    status = sel["status"]
    if status == "supported":
        return "ok", None
    if status == "null":
        return "return0", "val_is_null: asType returns false (database.cpp:233-236)"
    if status == "container":
        return "gap", "selected_container_extraction_gap"
    return "gap", "projection_policy_gap:" + sel["reason"]


def simulate(branch, sel, gate_passed, mob_id=None):
    """One conditional branch; sel is {field: selected interpretation}."""
    fresh = branch == "if_fresh"
    result = {"assumption": ("Id not found at this point (fresh object)" if fresh else
                             "Id already found (existing shared object)") +
                            "; additionally conditional on the inherited graph and Id gate",
              "operations": []}
    ops = result["operations"]
    state = "reached" if gate_passed else "id_stage"
    stop, writes, constructed = None, [], False

    def add(op, field=None):
        op = {"step": len(ops), **op}
        if field is not None:
            op["field"] = field
            op["source"] = LINES[field]
        op["reachability"] = REACH[state]
        ops.append(op)
        return op

    if fresh:
        op = add({"op": "check_mandatory_nodes", "nodes": ["AegisName", "Name"],
                  "source": LINES["mandatory"]})
        if state == "reached":
            missing = [n for n in ("AegisName", "Name") if sel[n]["status"] == "absent"]
            op["presence_only"] = "presence does not imply non-null or convertible text"
            if missing:
                op["result"] = "return0"
                op["missing"] = missing
                state, stop = "return0", {"step": op["step"], "reason": "missing mandatory "
                                          "node(s) " + ",".join(missing) + " (database.cpp:19-34)"}
            else:
                op["result"] = "present"
        op = add({"op": "construct_object", "source": LINES["construct"]})
        if state == "reached":
            constructed = True
            op["effect"] = {"id": mob_id, "vd.look[LOOK_BASE]": mob_id,
                            "constructor_defaults": CONSTRUCTOR,
                            "note": "source operations on a temporary object, not declared "
                                    "values or table membership"}
    for field in FIELDS[1:]:
        s = sel[field]
        if s["status"] == "absent":
            op = add({"op": "absent_declaration"}, field)
            if state == "reached":
                if field == "JapaneseName" and fresh:
                    op["op"] = "copy_name_to_jname"
                    op["effect"] = {"target": "jname", "copies": "name",
                                    "stored_bytes_hex": sel["Name"]["stored_bytes_hex"]}
                    writes.append({"field": field, "target": "jname", "kind": "copy_of_name"})
                elif fresh:
                    op["effect"] = {"target": TARGETS[field],
                                    "constructor_value_retained": CONSTRUCTOR[TARGETS[field]]}
                else:
                    op["effect"] = {"target": TARGETS[field], "prior_value_retained": True}
            continue
        if field in NAMES:
            op = add({"op": "as_string_resize_assign"}, field)
        elif field in EXP_RATES:
            op = add({"op": "as_uint64_rate_dependent_assign"}, field)
        else:
            op = add({"op": f"as_{NUMERIC[field][0]}_assign"}, field)
        if state != "reached":
            continue
        outcome, reason = _convert(s)
        if outcome == "return0":
            op["result"] = "return0"
            op["reason"] = reason
            state, stop = "return0", {"step": op["step"], "field": field, "reason": reason}
            continue
        if outcome == "gap":
            op["result"] = "unresolved"
            op["reason"] = reason
            state, stop = "gap", {"step": op["step"], "field": field, "reason": reason}
            continue
        op["result"] = "assigned"
        target = TARGETS[field]
        if field in NAMES:
            op["effect"] = {"target": target, "stored_bytes_hex": s["stored_bytes_hex"],
                            "length_warning": s["warning"]}
        elif field in EXP_RATES:
            op["result"] = "rate_dependent_assignment"
            op["effect"] = {"target": target, "declared_uint64": s["value"],
                            "rate": EXP_RATES[field],
                            "operation": f"static_cast<t_exp>(cap_value((double){s['value']} * "
                                         f"(double){EXP_RATES[field]} / 100., 0, MAX_EXP))",
                            "stored_value": "not computed (rate, double rounding and "
                                            "build-dependent MAX_EXP are outside this profile)"}
        else:
            op["effect"] = {"target": target, "assigned_value": s["value"]}
        writes.append({"field": field, "target": target})
    later = add({"op": "later_parser", "fields": "Attack and every later field",
                 "source": LINES["later"]})
    if state == "reached":
        later["result"] = "later_parser_unchecked"
    if fresh:
        put = add({"op": "put", "source": LINES["put"]})
        if state == "reached":
            put["result"] = "conditional_on_all_later_parsing_succeeding"
    if state == "id_stage":
        result.update(outcome="not_reached_id_stage", later_parser="not_reached",
                      insertion="not_reached" if fresh else "not_applicable")
    elif state == "reached":
        result.update(outcome="prefix_modelled", later_parser="later_parser_unchecked",
                      insertion=("conditional_on_later_parser" if fresh else
                                 "not_applicable_existing_shared_object"))
    elif state == "return0":
        result.update(outcome="known_prefix_return0", stop=stop,
                      later_parser="later_parser_not_reached",
                      insertion=("not_reached_temporary_object_discarded" if constructed else
                                 "not_reached_no_object_constructed") if fresh else
                      "not_applicable_existing_shared_object")
    else:
        result.update(outcome="unresolved_projection_gap", stop=stop,
                      later_parser="unresolved_not_asserted",
                      insertion="unresolved" if fresh else "not_applicable_existing_shared_object")
    if not fresh and state in ("return0", "gap"):
        result["earlier_writes_survive"] = writes
    elif state != "id_stage":
        result["writes_before_later_parser"] = writes
    return result


def project(fields):
    """Id stage plus both conditional branches for one declaration's field observations."""
    sel = {f["field"]: f["selected"] for f in fields}
    id_sel = sel["Id"]
    stage = {"source": LINES["Id"], "gate_source": LINES["gate"]}
    status = id_sel["status"]
    gaps = []
    if status == "absent":
        stage.update(outcome="known_return0", reason="missing Id node (database.cpp:247-249)")
    elif status == "null":
        stage.update(outcome="known_return0",
                     reason="val_is_null: asType returns false (database.cpp:233-236)")
    elif status in ("container", "unsupported"):
        _, reason = _convert(id_sel)
        stage.update(outcome="unresolved", reason=reason)
        gaps.append({"scope": "id_stage", "field": "Id", "reason": reason})
    else:
        value = id_sel["value"]
        stage["id"] = value
        if any(low <= value <= high for low, high in ID_RANGES):
            stage.update(outcome="gate_passed", find="conditional: if_existing / if_fresh")
        else:
            stage.update(outcome="known_range_failure",
                         reason="Id outside 1001..3998 and 20021..31998: return false, no "
                                "find/name/default mutation for this row")
    passed = stage["outcome"] == "gate_passed"
    branches = {b: simulate(b, sel, passed, stage.get("id")) for b in ("if_existing", "if_fresh")}
    for name, branch in branches.items():
        if branch["outcome"] == "unresolved_projection_gap":
            gaps.append({"scope": name, "field": branch["stop"]["field"],
                         "reason": branch["stop"]["reason"]})
    by_design = {
        "membership": "unresolved_by_design (no database membership map; branch not selected)",
        "later_parser": {b: branches[b]["later_parser"] for b in branches},
        "insertion": {b: branches[b]["insertion"] for b in branches},
        "exp_runtime_value": "not_computed_rate_dependent",
        "native_row_acceptance": "not_certified",
    }
    return stage, branches, gaps, by_design


# --- Projection over the reparsed MOB files ------------------------------------------------

class Projection:
    def __init__(self, files, prereq, emit, yg, limits, caps=CAPS, ruby=None):
        self.files, self.prereq, self.emit, self.yg = files, prereq, emit, yg
        self.limits, self.caps = limits, caps
        self.ruby = ruby or yg.RUBY
        self.stop = None
        self.unresolved = []
        self.parsed = {}
        self.parser_attempts = []
        self.diagnostics = []
        self.history = {}
        self.ordinal = 0
        self.occurrences = 0
        self.usage = {"parser_attempts": 0, "input_bytes_parsed": 0, "nodes": 0,
                      "exact_ast_nodes": 0, "unknown_node_count_attempts": 0,
                      "adapter_stdout_bytes": 0, "adapter_stderr_bytes": 0,
                      "adapter_stdout_observed_bytes": 0, "adapter_stderr_observed_bytes": 0,
                      "declarations": 0, "target_occurrences": 0}
        self.counts = Counts()

    def run(self):
        visits = self.prereq.mob_visits
        for position, visit in enumerate(visits):
            try:
                self.visit(visit)
            except Halt as halt:
                self.stop = dict(halt.record, visit=visit["visit"])
                for later in visits[position + 1:]:
                    self.unresolved.append({"kind": "visit_not_projected",
                                            "visit": later["visit"], "path": later["path"],
                                            "rows": later["body"]["rows"]})
                break
        return self

    def parse_file(self, visit):
        yg, path = self.yg, visit["path"]
        if len(self.parsed) >= self.caps["max_mob_files"]:
            raise Halt("work_limit", "max_mob_files", limit=self.caps["max_mob_files"])
        data = self.files[SERVER_ROOT + path]
        attempt = {"path": path, "bytes": len(data), "sha256": sha256(data)}
        self.parser_attempts.append(attempt)
        try:
            yg.precheck_bytes(data)
        except yg.Stop as stop:
            attempt["outcome"] = "byte_profile_refusal"
            raise Halt("parser_" + stop.record["kind"], stop.record["detail"]) from None
        self.usage["parser_attempts"] += 1
        self.usage["input_bytes_parsed"] += len(data)
        try:
            tree, info = yg.parse_yaml(data, self.limits, self.ruby)
        except yg.Stop as stop:
            info = stop.record.get("adapter")
            if info is not None:
                self.charge(attempt, info, stop.record["kind"])
            raise Halt("parser_" + stop.record["kind"], stop.record["detail"],
                       selected_stop=stop.record) from None
        self.charge(attempt, info, "ok")
        if self.usage["nodes"] > self.limits["max_nodes_total"]:
            raise Halt("work_limit", "max_nodes_total", limit=self.limits["max_nodes_total"])
        try:
            root_map, duplicates = yg.check_syntax(tree)
            del tree
            lines = yg.LineIndex(data)
            header = yg.find(root_map, "Header")
            if header is None or header[1].kind != "M":
                raise Halt("provenance_mismatch", "reparsed Header is not a mapping")
            shape = {"duplicate_key_sites": len(duplicates)}
            for name, cap in (("Type", 256), ("Version", None)):
                found = yg.control_scalar(header[1], name, "Header")
                shape[name] = None if found is None else yg.scalar_record(found[1], lines, cap)
            clear = yg.control_scalar(header[1], "Clear", "Header")
            shape["Clear"] = None if clear is None else yg.scalar_record(clear[1], lines)
            body = yg.find(root_map, "Body")
            rows = []
            if body is not None:
                if body[1].kind != "Q":
                    raise Halt("provenance_mismatch", "reparsed Body is not a sequence")
                for local, row in enumerate(body[1].children):
                    if row.kind != "M":
                        raise Halt("provenance_mismatch", f"reparsed Body row {local} is not "
                                   "a mapping")
                    fields = observe(row, lines, yg)
                    used = sum(f["occurrence_count"] for f in fields)
                    if self.occurrences + used > self.caps["max_target_occurrences"]:
                        raise Halt("work_limit", "max_target_occurrences",
                                   limit=self.caps["max_target_occurrences"])
                    self.occurrences += used
                    rows.append((yg.row_record(row, lines), fields))
            shape["body_present"] = body is not None
        except yg.Stop as stop:
            raise Halt("parser_" + stop.record["kind"], stop.record["detail"],
                       selected_stop=stop.record) from None
        return {"shape": shape, "rows": rows}

    def charge(self, attempt, info, outcome):
        attempt["parser_attempt"] = {**info, "outcome": outcome}
        self.usage["nodes"] += info["node_count_lower_bound"]
        if info["node_total"] is None:
            self.usage["unknown_node_count_attempts"] += 1
        else:
            self.usage["exact_ast_nodes"] += info["node_total"]
        for name in ("stdout_bytes", "stderr_bytes", "stdout_observed_bytes",
                     "stderr_observed_bytes"):
            self.usage["adapter_" + name] += info[name]

    def visit(self, visit):
        path = visit["path"]
        if path not in self.parsed:
            self.parsed[path] = self.parse_file(visit)
        parsed = self.parsed[path]
        shape, header, clear = parsed["shape"], visit.get("header") or {}, visit.get("clear")
        if header.get("type") != shape["Type"] or header.get("version") != shape["Version"] \
                or (visit.get("duplicate_key_sites") or {}).get("count") != \
                shape["duplicate_key_sites"]:
            raise Halt("provenance_mismatch", "reparsed header/duplicate sites differ from the "
                       "prerequisite visit")
        if (clear or {}).get("present", False) != (shape["Clear"] is not None) or \
                (shape["Clear"] is not None and clear.get("value") != shape["Clear"]):
            raise Halt("provenance_mismatch", "reparsed Clear differs from the prerequisite")
        body = visit["body"]
        if body["present"] != shape["body_present"] or body["rows"] != len(parsed["rows"]):
            raise Halt("provenance_mismatch", "reparsed Body row count differs from the "
                       "prerequisite visit")
        for local, (record, fields) in enumerate(parsed["rows"]):
            index = body["first_global_ordinal"] + local
            expected = self.prereq.mob_rows.get(index)
            declaration = {
                "database": visit["database"], "root_order": visit["root_order"],
                "visit": visit["visit"], "file": path, "file_sha256": visit["sha256"],
                "epoch": body["epoch"], "local_ordinal": local,
                "database_ordinal": None if expected is None else expected["database_ordinal"],
                "global_ordinal": index, **record,
            }
            if expected is None or declaration != expected:
                raise Halt("provenance_mismatch", "reconstructed raw row differs from the "
                           "prerequisite row", global_ordinal=index)
            self.declare(expected, fields)

    def declare(self, raw, fields):
        if self.ordinal >= self.caps["max_declarations"]:
            raise Halt("work_limit", "max_declarations", limit=self.caps["max_declarations"])
        stage, branches, gaps, by_design = project(fields)
        record = {"projection_ordinal": self.ordinal, "raw_declaration": raw,
                  "fields": fields, "id_stage": stage, "branches": branches,
                  "projection_gaps": gaps, "excluded_by_design": by_design,
                  "projection_status": "gap" if gaps else "modelled"}
        diags = []
        for gap in gaps:
            diags.append({"projection_ordinal": self.ordinal, "kind": "projection_gap", **gap})
        for field in fields:
            if field["field"] in NAMES and field["selected"].get("warning"):
                diags.append({"projection_ordinal": self.ordinal, "kind": "name_length_warning",
                              "field": field["field"],
                              "utf8_length": field["selected"]["utf8_length"]})
        if len(self.diagnostics) + len(diags) > self.caps["max_diagnostics"]:
            raise Halt("work_limit", "max_diagnostics", limit=self.caps["max_diagnostics"])
        self.emit(record)
        # Counts, diagnostics and history advance only after the record is written.
        self.diagnostics.extend(diags)
        self.counts.add(record)
        self.usage["declarations"] += 1
        self.usage["target_occurrences"] += sum(f["occurrence_count"] for f in fields)
        if stage.get("id") is not None:
            entry = self.history.setdefault(stage["id"], {
                "id": stage["id"], "id_decimal": str(stage["id"]),
                "source_gate": "in_range" if stage["outcome"] == "gate_passed"
                else "out_of_range", "declarations": []})
            first = fields[0]["occurrences"][0]
            entry["declarations"].append({
                "projection_ordinal": self.ordinal, "global_ordinal": raw["global_ordinal"],
                "database": raw["database"], "database_ordinal": raw["database_ordinal"],
                "local_ordinal": raw["local_ordinal"], "visit": raw["visit"],
                "epoch": raw["epoch"], "file": raw["file"], "file_sha256": raw["file_sha256"],
                "row_byte_span": raw["byte_span"], "row_span_sha256": raw["span_sha256"],
                "fingerprint_sha256": raw["fingerprint_sha256"],
                "id_text": first["value"]["text"], "id_style": first["value"]["style"],
                "id_byte_span": first["value"]["byte_span"],
                "id_span_sha256": first["value"]["span_sha256"],
                "projection_status": record["projection_status"]})
        self.ordinal += 1


class Counts:
    """Aggregates advanced per emitted declaration (not accepted/effective entities)."""

    def __init__(self):
        self.declarations = 0
        self.status = {}
        self.id = {}
        self.fields = {name: {"present_rows": 0, "absent_rows": 0, "occurrences": 0,
                              "rows_with_ignored_duplicates": 0, "case_variant_keys": 0,
                              "selected": {}} for name in FIELDS}
        self.branches = {b: {"outcomes": {}, "stops": {}} for b in ("if_existing", "if_fresh")}
        self.gaps = {}

    @staticmethod
    def bump(table, key, by=1):
        table[key] = table.get(key, 0) + by

    def add(self, record):
        self.declarations += 1
        self.bump(self.status, record["projection_status"])
        self.bump(self.id, record["id_stage"]["outcome"])
        for field in record["fields"]:
            entry = self.fields[field["field"]]
            entry["present_rows" if field["present"] else "absent_rows"] += 1
            entry["occurrences"] += field["occurrence_count"]
            entry["rows_with_ignored_duplicates"] += field["ignored_duplicates"] > 0
            entry["case_variant_keys"] += len(field["case_variant_keys"])
            sel = field["selected"]
            key = sel["status"] + (":" + sel["reason"] if "reason" in sel else "")
            self.bump(entry["selected"], key)
            if sel["status"] == "supported":
                if field["field"] in NUMERIC and sel["value"] == 0:
                    self.bump(entry, "zero_values")
                if field["field"] in NAMES:
                    n = sel["utf8_length"]
                    self.bump(entry, "exactly_24_bytes" if n == NAME_LENGTH else
                              "over_24_bytes_truncated" if n > NAME_LENGTH else
                              "under_24_bytes_nul_padded")
                    if n == 0:
                        self.bump(entry, "empty_text")
                    if any(b > 127 for b in bytes.fromhex(sel["stored_bytes_hex"])):
                        self.bump(entry, "non_ascii_stored_bytes")
        for name, branch in record["branches"].items():
            self.bump(self.branches[name]["outcomes"], branch["outcome"])
            if "stop" in branch:
                stop = branch["stop"]
                self.bump(self.branches[name]["stops"],
                          f"{stop.get('field', 'mandatory')}:{stop['reason']}")
        for gap in record["projection_gaps"]:
            self.bump(self.gaps, f"{gap['scope']}:{gap['field']}:{gap['reason']}")

    def render(self, history):
        in_range = sum(1 for e in history.values() if e["source_gate"] == "in_range")
        return {
            "raw_declarations": self.declarations,
            "projection_status": self.status,
            "id_stage_outcomes": self.id,
            "distinct_supported_declared_ids": len(history),
            "distinct_in_range_declared_ids": in_range,
            "distinct_out_of_range_declared_ids": len(history) - in_range,
            "declared_ids_with_several_declarations": sum(
                1 for e in history.values() if len(e["declarations"]) > 1),
            "fields": self.fields,
            "branches": self.branches,
            "projection_gaps": self.gaps,
            "not_counts_of": "accepted, effective, merged, loaded, spawned or playable "
                             "monsters; membership and later parsing are excluded by design",
        }


# --- Publication ---------------------------------------------------------------------------

def trusted_target(out_dir):
    out_dir = Path(os.path.abspath(out_dir))
    if out_dir.name in ("", ".", ".."):
        raise OutputError(f"invalid output directory name: {out_dir}")
    parent = out_dir.parent
    try:
        info = os.lstat(parent)
    except FileNotFoundError:
        raise OutputError(f"output parent does not exist: {parent}") from None
    if not stat.S_ISDIR(info.st_mode):
        raise OutputError(f"output parent is not a directory (or is a link): {parent}")
    if info.st_uid != os.geteuid() or info.st_mode & 0o022:
        raise OutputError(f"output parent must be owned by you and not group/world "
                          f"writable: {parent}")
    return out_dir


class RecordFile:
    """Exclusive, no-follow, 0600 streaming JSONL writer; reserves bytes before writing."""

    def __init__(self, dir_fd, name, created, limit, cap_name):
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                     dir_fd=dir_fd)
        created[name] = None
        try:
            info = os.fstat(fd)
            created[name] = (info.st_dev, info.st_ino)
            os.fchmod(fd, 0o600)
        except BaseException:
            os.close(fd)
            raise
        self.name, self.limit, self.cap_name = name, limit, cap_name
        self.handle = os.fdopen(fd, "wb")
        self.digest = hashlib.sha256()
        self.bytes = self.lines = 0

    def write(self, row):
        line = render_row(row)
        if self.bytes + len(line) > self.limit:
            raise Halt("work_limit", self.cap_name, limit=self.limit)
        self.handle.write(line)
        self.digest.update(line)
        self.bytes += len(line)
        self.lines += 1

    def close(self):
        handle, self.handle = self.handle, None
        try:
            handle.flush()
            os.fsync(handle.fileno())
        finally:
            handle.close()
        return {"file": self.name, "bytes": self.bytes, "lines": self.lines,
                "sha256": self.digest.hexdigest()}

    def abandon(self):
        if self.handle is not None:
            handle, self.handle = self.handle, None
            try:
                handle.close()
            except Exception:
                pass


def write_new(dir_fd, name, data, created):
    fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                 dir_fd=dir_fd)
    created[name] = None  # never unlink an unverified identity during cleanup
    with os.fdopen(fd, "wb") as handle:
        info = os.fstat(handle.fileno())
        created[name] = (info.st_dev, info.st_ino)
        os.fchmod(handle.fileno(), 0o600)
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def verify_published(dir_fd, name, size, digest, expected_identity):
    """Read back by no-follow descriptor: owned private regular file, size and hash."""
    fd = os.open(name, FILE_FLAGS, dir_fd=dir_fd)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or stat.S_IMODE(info.st_mode) != 0o600 or \
                info.st_uid != os.geteuid() or info.st_size != size or \
                (info.st_dev, info.st_ino) != expected_identity:
            raise OutputError(f"published {name} is not the owned private regular file")
        hasher, total = hashlib.sha256(), 0
        while total <= size:
            chunk = os.read(fd, min(1 << 20, size + 1 - total))
            if not chunk:
                break
            hasher.update(chunk)
            total += len(chunk)
        after = os.fstat(fd)
    finally:
        os.close(fd)
    if total != size or hasher.hexdigest() != digest or _identity(info) != _identity(after):
        raise OutputError(f"published {name} differs from the generated bytes")


def build_manifest(projection, prereq, provenance, records, history_file, timings, caps):
    status = ("unsupported" if projection.stop is not None else
              "qualified" if projection.counts.gaps else "complete")
    return {
        "kind": "MOB_DB declared ten-field projection and conditional prefix operations "
                "(source profile, Psych AST; not an accepted/effective monster table)",
        "status": status,
        "status_meaning": STATUS_MEANING[status],
        **provenance,
        "prerequisite": prereq.identity,
        "mob_selection": {
            **prereq.selection,
            "visits_detail": [{"visit": v["visit"], "path": v["path"], "sha256": v["sha256"],
                               "bytes": v["bytes"], "parent_visit": v["parent_visit"],
                               "epoch_at_start": v["epoch_at_start"],
                               "body_epoch": v["body"]["epoch"], "rows": v["body"]["rows"],
                               "first_global_ordinal": v["body"].get("first_global_ordinal"),
                               "clear": v.get("clear")} for v in prereq.mob_visits],
            "clear_history": prereq.mob_clears,
            "clear_meaning": "history/rule references only; no earlier declaration is erased "
                             "and no deletion of world entities is claimed",
            "meaning": "derived from the bound manifest/stream; raw declarations, not entities",
        },
        "source": SOURCE,
        "fields": {name: {"parser_order": i, **({"target_type": NUMERIC[name][0],
                                                  "maximum": NUMERIC[name][1]}
                                                 if name in NUMERIC else
                                                 {"projection": "UTF-8 bytes [:24] + NUL "
                                                  "padding to 24"})}
                   for i, name in enumerate(FIELDS)},
        "id_ranges": [list(r) for r in ID_RANGES],
        "numeric_subset": "nonempty ASCII [0-9]+ within the target unsigned width, full decoded "
                          "text (quoted/plain/block), leading zeroes decimal; other text is a "
                          "projection-policy gap, not a native rejection",
        "records_file": records,
        "history_file": history_file,
        "counts": projection.counts.render(projection.history),
        "parser_attempts": projection.parser_attempts,
        "work_usage": projection.usage,
        "work_limits": {"parser": projection.limits, "projection": caps},
        "stop": projection.stop,
        "unresolved": projection.unresolved,
        "diagnostics": projection.diagnostics,
        "timings_seconds": timings,
        "timings_note": "measured observations; they vary between runs",
        "limits": list(LIMIT_NOTES),
        "exclusions": EXCLUSIONS,
        "not_counts_of": "accepted, effective, merged, loaded, spawned or playable monsters",
    }


def publish(target, files, prereq, provenance, yg, limits, caps=CAPS, ruby=None, timings=None):
    """Project into a new private directory. Returns (target, manifest, hashes)."""
    target = trusted_target(target)
    timings = dict(timings or {})
    try:
        os.mkdir(target, 0o700)  # exclusive: refuses any file, dir or (dangling) symlink
    except OSError as exc:
        raise OutputError(f"output exists or cannot be created, refusing: {target}: "
                          f"{exc.strerror}") from None
    out_fd, identity, created, writer = None, None, {}, None
    try:
        out_fd = os.open(target, DIR_FLAGS)
        info = os.fstat(out_fd)
        identity = (info.st_dev, info.st_ino)
        if info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077:
            raise OutputError("reserved output directory is not private to you")
        started = time.monotonic()
        writer = RecordFile(out_fd, OUTPUT_DECLARATIONS, created,
                            caps["max_declaration_file_bytes"], "max_declaration_file_bytes")
        projection = Projection(files, prereq, writer.write, yg, limits, caps, ruby)
        projection.run()
        closing, writer = writer, None
        records = closing.close()
        verify_published(out_fd, OUTPUT_DECLARATIONS, records["bytes"], records["sha256"],
                         created[OUTPUT_DECLARATIONS])
        records["readback"] = "verified size, SHA-256, private mode and identity"
        timings["projection_and_declarations"] = round(time.monotonic() - started, 3)
        started = time.monotonic()
        writer = RecordFile(out_fd, OUTPUT_HISTORY, created, caps["max_history_file_bytes"],
                            "max_history_file_bytes")
        try:
            for key in sorted(projection.history):
                entry = projection.history[key]
                writer.write({**entry, "declaration_count": len(entry["declarations"]),
                              "meaning": "declared-Id history index, not one accepted entity"})
        except Halt as halt:
            projection.stop = projection.stop or dict(halt.record)
        closing, writer = writer, None
        history_file = closing.close()
        verify_published(out_fd, OUTPUT_HISTORY, history_file["bytes"], history_file["sha256"],
                         created[OUTPUT_HISTORY])
        history_file["readback"] = "verified size, SHA-256, private mode and identity"
        timings["history"] = round(time.monotonic() - started, 3)
        manifest = build_manifest(projection, prereq, provenance, records, history_file,
                                  timings, caps)
        data = render(manifest)
        if len(data) > caps["max_manifest_bytes"]:
            raise OutputError("manifest exceeds max_manifest_bytes")
        write_new(out_fd, OUTPUT_MANIFEST, data, created)
        verify_published(out_fd, OUTPUT_MANIFEST, len(data), sha256(data),
                         created[OUTPUT_MANIFEST])
        hashes = {"manifest_sha256": sha256(data), "manifest_bytes": len(data),
                  "declarations_sha256": records["sha256"], "declarations_bytes": records["bytes"],
                  "history_sha256": history_file["sha256"], "history_bytes": history_file["bytes"]}
        if manifest["status"] == "complete":
            complete = render({
                "generator_version": VERSION, "status": manifest["status"],
                "manifest": OUTPUT_MANIFEST, "manifest_sha256": sha256(data),
                "declarations_file": OUTPUT_DECLARATIONS, "declarations_sha256": records["sha256"],
                "history_file": OUTPUT_HISTORY, "history_sha256": history_file["sha256"],
                "relationship": "the manifest binds both record files' size/hash; this record "
                                "binds the manifest and both records; written last",
            })
            hashes["complete_sha256"] = sha256(complete)
            write_new(out_fd, OUTPUT_COMPLETE, complete, created)
            verify_published(out_fd, OUTPUT_COMPLETE, len(complete), hashes["complete_sha256"],
                             created[OUTPUT_COMPLETE])
        if sorted(os.listdir(out_fd)) != sorted(created):
            raise OutputError("output directory holds files this run did not write")
        closing_fd, out_fd = out_fd, None
        os.close(closing_fd)  # part of publication: a close error must fail before success
    except Exception as exc:
        note = "; partial output remains (not complete); inspect it before deleting or retrying"
        if writer is not None:
            writer.abandon()
        if OUTPUT_COMPLETE in created:
            note = _remove_owned_marker(target, out_fd, identity, created, note)
        prefix = "" if isinstance(exc, ProjectionError) else "unexpected: "
        raise OutputError(f"{prefix}{exc}{note}") from None
    finally:
        if out_fd is not None:
            try:
                os.close(out_fd)
            except Exception:
                pass
    return target, manifest, hashes


def _remove_owned_marker(target, out_fd, identity, created, note):
    """Unlink only this run's completion inode in the reserved directory; else report."""
    cleanup_fd, reopened = out_fd, False
    try:
        if cleanup_fd is None:
            cleanup_fd = os.open(target, DIR_FLAGS)
            reopened = True
            current = os.fstat(cleanup_fd)
            if (current.st_dev, current.st_ino) != identity:
                raise OutputError("reserved output directory was replaced")
        marker = os.stat(OUTPUT_COMPLETE, dir_fd=cleanup_fd, follow_symlinks=False)
        if created[OUTPUT_COMPLETE] is None or not stat.S_ISREG(marker.st_mode) or \
                (marker.st_dev, marker.st_ino) != created[OUTPUT_COMPLETE]:
            raise OutputError("completion was replaced; foreign file preserved")
        os.unlink(OUTPUT_COMPLETE, dir_fd=cleanup_fd)
    except FileNotFoundError:
        pass
    except Exception as cleanup:
        note = (f"; could not remove {OUTPUT_COMPLETE} ({cleanup}); treat this output as "
                "failed and incomplete despite the record")
    finally:
        if reopened:
            try:
                os.close(cleanup_fd)
            except Exception:
                pass
    return note


# --- Pipeline ------------------------------------------------------------------------------

def execute(files, fresh_input, raw_catalog, output, *, pins=PREREQ_PINS, expected=CANONICAL_MOB,
            file_pins=MOB_FILE_PINS, profile=None, limits=None, caps=CAPS, ruby=None,
            reader_identity=None, timings=None):
    """Verify the prerequisite against the fresh snapshot identity, then project and publish.
    The CLI passes only the fixed pins/profile; tests pass small verified fixtures."""
    yg, tools = selected()
    limits = yg.LIMITS if limits is None else limits
    timings = dict(timings or {})
    target = trusted_target(output)
    if os.path.lexists(target):
        raise OutputError(f"output already exists, refusing to overwrite: {target}")
    try:
        versions = yg.check_parser(limits, ruby or yg.RUBY)
    except yg.InputError as exc:
        raise InputError(str(exc)) from None
    parser = expected_parser(yg, versions)
    started = time.monotonic()
    prereq = load_prerequisite(raw_catalog, files, fresh_input, yg, parser, pins, profile,
                               expected, file_pins, caps["max_raw_line_bytes"])
    timings["prerequisite_verification"] = round(time.monotonic() - started, 3)
    provenance = {
        "generator": {"tool": TOOL, "version": VERSION,
                      "source_sha256": sha256(Path(__file__).read_bytes())},
        "selected_tools": tools,
        "selected_reader": reader_identity or fresh_input.get("verification"),
        "input": fresh_input,
        "parser": {**parser, "limits_source": "selected yaml_graph_inventory LIMITS"},
        "profile": prereq.manifest["profile"],
        "fixed_pins": {"prerequisite": pins, "mob_files": file_pins,
                       "canonical_mob_selection": expected},
    }
    return publish(target, files, prereq, provenance, yg, limits, caps, ruby, timings)


def run(snapshot, raw_catalog, output):
    """CLI pipeline with fixed pins, profile, parser and limits."""
    yg, _tools = selected()
    target = trusted_target(output)
    if os.path.lexists(target):
        raise OutputError(f"output already exists, refusing to overwrite: {target}")
    started = time.monotonic()
    try:
        manifest_bytes, files, reader = yg.read_snapshot(snapshot)
    except yg.InputError as exc:
        raise InputError(str(exc)) from None
    if reader["reader_sha256"] != SELECTED_TOOLS["server_selection.py"][1]:
        raise InputError("snapshot reader is not the selected server_selection.py")
    timings = {"snapshot_verification": round(time.monotonic() - started, 3)}
    fresh = fresh_input_identity(manifest_bytes, files, reader)
    return execute(files, fresh, raw_catalog, target, timings=timings)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("snapshot", type=Path, help="canonical T06.001 snapshot (read-only)")
    parser.add_argument("raw_catalog", type=Path,
                        help="selected T06.002.003.001 raw catalog directory (read-only)")
    parser.add_argument("output", type=Path, help="new private output directory")
    args = parser.parse_args(argv)
    try:
        target, manifest, hashes = run(args.snapshot, args.raw_catalog, args.output)
    except (ProjectionError, OSError) as exc:
        category = getattr(exc, "category", "os_error")
        print(f"error [{category}]: {exc}", file=sys.stderr)
        return 2
    counts = manifest["counts"]
    print(json.dumps({"output": str(target), "status": manifest["status"],
                      "raw_declarations": counts["raw_declarations"],
                      "id_stage_outcomes": counts["id_stage_outcomes"],
                      "projection_status": counts["projection_status"],
                      "stop": manifest["stop"], **hashes}, sort_keys=True))
    return 0 if manifest["status"] == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
