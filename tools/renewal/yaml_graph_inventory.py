#!/usr/bin/env python3
"""Catalog the four-root stock rAthena YAML import graph and every raw Body declaration.

The input is the canonical T06.001 snapshot directory. It is verified in full
(manifest pin, exact file set, every size and hash, no links) through the
unmodified server_selection.read_snapshot before anything else happens; only
those verified bytes are used afterwards.

The graph follows YamlDatabase::load at the pinned rAthena revision under one
fixed source profile (db_path=db, RENEWAL, RENEWAL_ASPD, generator off, YAML
item/monster branch): ITEM_DB, SKILL_DB, MOB_DB and QUEST_DB roots in that
order, Header Type/Version before Clear, ordered Body rows, then depth-first
ordered Footer.Imports with literal server-root paths and Mode/Generator gates.
Row callbacks (parseBodyNode) are deliberately excluded: the graph is the
conditional initial load assuming every callback returns normally, and no row
is accepted, rejected, merged, defaulted or counted as an entity.

YAML is parsed one file at a time by the existing /usr/bin/ruby Psych
parse_stream AST only (an authored adapter embedded below), in a bounded child
process. No object construction, alias resolution or script execution. Psych
is not rapidyaml: constructs whose native meaning is not modelled (tags,
anchors, aliases, merge keys, complex keys, several documents, directives,
unsupported control shapes, parser refusals, work limits, unsafe paths, cycles)
stop certain traversal and leave the rest unresolved.

Output: raw-declarations.jsonl (one record per Body row, streamed), the
yaml-graph-manifest.json and, only when the status is complete,
yaml-graph-complete.json written last. Standard library only. Output
directories are never overwritten.
"""

import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import resource
import selectors
import signal
import stat
import subprocess
import sys
import time

VERSION = "1.0.1"
TOOL = "tools/renewal/yaml_graph_inventory.py"
OUTPUT_RECORDS = "raw-declarations.jsonl"
OUTPUT_MANIFEST = "yaml-graph-manifest.json"
OUTPUT_COMPLETE = "yaml-graph-complete.json"
SERVER_ROOT = "rathena/"
SCOPE_DIRS = ("conf", "db", "npc", "sql-files")

RUBY = "/usr/bin/ruby"
PARSER_PINS = {"ruby": "2.6.10", "psych": "3.1.0", "libyaml": "0.2.1"}

SOURCE = {
    "repository": "rathena",
    "revision": "0693b8c69911d5ca42269684aa036b67d67f4d3e",
    "files": {
        "src/common/database.cpp": "03d394aa9ed809557fb4ce50419776e34214220504ef1229ec864a4b10be0011",
        "src/common/database.hpp": "1b54c493748f34907cd26e5be27959fc4bdbb2ea041ef32637dc01dd98fbad3e",
        "src/map/itemdb.hpp": "c7fb0224d54797f8271c3423cf90b1db9e7c179771423a2f1145b153c47faff0",
        "src/map/skill.hpp": "b0615002f0322e5a82a2482adcaad6bc3b7154683ad48c1ee3f7cbbece8266f1",
        "src/map/mob.hpp": "7e931afe57d0e9436356d68c4f5a528ab57daa996f600d57f9a4a191175b1da4",
        "src/map/quest.hpp": "7386a141206cd11e5243ced09e730275d67bfd56ebded2ebc78f8a4a071b65ae",
        "src/map/itemdb.cpp": "3b51a2bbcb44c5ffbdb5dc04683dd4f567c2da92f56a4bc0008aa9a93de5efe5",
        "src/map/skill.cpp": "d50e4fdc00a4b2471992b2224393ad77ce194fd4cf149ce28aad6be0aaa5ad40",
        "src/map/mob.cpp": "0e0ded18ebeeca1ab9071ff6d50882ea2325882274fc734a44a7c3c62d89a090",
        "src/map/quest.cpp": "ffaa8072ab705c7976933014ed165b59b120cdd3cd5ed8ff794e0bf9e56d216d",
        "src/map/map.cpp": "2ec53a19360b2363d6bcb1401f71bfdf130d72e74a624676e4a25f17de21a189",
        "3rdparty/rapidyaml/src/c4/yml/tree.hpp": "37891f845f593a2e0c9748ab27c5e6d2987168e2714b7a52787f3bad3308601e",
        "3rdparty/rapidyaml/src/c4/yml/tree.cpp": "9639cbb9aaeb4bcb418f237f02a7f0284f63ba32f59c4be153216e4f5a4e4834",
    },
    "rules": {
        "load": "database.cpp:92-146 fopen -> parse -> verifyCompatibility -> Clear -> parse(Body) "
                "-> parseImports; fopen/parse/Header failures return false",
        "header": "database.cpp:37-76 Header exists, asString Type == type, asUInt16 Version; "
                  "> current or < minimum fails, older >= minimum warns",
        "clear": "database.cpp:132-138 Clear present and asBool true -> clear()",
        "as_bool": "database.cpp:253-277 val_is_null fails; ASCII tolower; 'true'/'false' only",
        "as_type": "database.cpp:230-251 missing node or val_is_null fails with a warning",
        "body": "database.cpp:152-174 every Body child in order -> parseBodyNode (excluded)",
        "imports": "database.cpp:176-228 Footer.Imports in order: Path, optional Mode "
                   "(RENEWAL 'Renewal', job_aspd.yml without RENEWAL_ASPD 'Prerenewal'), optional "
                   "Generator (load only if shouldLoadGenerator && true); load() return ignored",
        "node_exists": "database.cpp:15-17 num_children() > 0 && has_child(name)",
        "find_child": "tree.cpp:1580-1600 first mapping child whose key equals the name",
        "val_is_null": "tree.hpp:584 unquoted (VALQUO covers '', \"\", |, >) empty, ~, null, Null, NULL",
        "constructors": "itemdb.hpp:3571 ITEM_DB 3/1; skill.hpp:335 SKILL_DB 4/4; "
                        "mob.hpp:292 MOB_DB 5/1; quest.hpp:60 QUEST_DB 3/1",
        "default_locations": "itemdb.cpp:40 skill.cpp:14751 mob.cpp:4862 quest.cpp:33 "
                             "db_path + '/<name>_db.yml'",
        "root_order": "map.cpp:5485-5502 itemdb -> skill -> mob -> quest init order",
    },
}

ROOTS = (
    {"database": "ITEM_DB", "path": "db/item_db.yml", "version": 3, "minimum_version": 1},
    {"database": "SKILL_DB", "path": "db/skill_db.yml", "version": 4, "minimum_version": 4},
    {"database": "MOB_DB", "path": "db/mob_db.yml", "version": 5, "minimum_version": 1},
    {"database": "QUEST_DB", "path": "db/quest_db.yml", "version": 3, "minimum_version": 1},
)
PROFILE = {
    "name": "rathena-0693b8c-stock-renewal-yaml-four-roots",
    "db_path": "db",
    "renewal": True,
    "renewal_aspd": True,
    "should_load_generator": False,
    "item_monster_sql_branch": False,
    "roots": [dict(r) for r in ROOTS],
    "server_working_root": SERVER_ROOT,
    "filesystem": "case-sensitive, literal paths against exact snapshot keys",
    "graph": "conditional initial load; database-specific row callbacks assumed to return "
             "normally, their acceptance, errors and side effects are not checked",
}

# Work limits. Exhausting one is an unsupported state, never a native result.
LIMITS = {
    "max_input_bytes": 16 << 20,
    "cpu_seconds": 20,
    "wall_seconds": 30,
    "max_stdout_bytes": 192 << 20,
    "max_stderr_bytes": 64 << 10,
    "max_nodes_per_file": 2_000_000,
    "max_nodes_total": 8_000_000,
    "max_depth": 64,
    "max_scalar_bytes": 1 << 20,
    "max_visits": 256,
    "max_import_depth": 16,
    "max_edges": 4096,
    "max_rows_total": 1_000_000,
    "max_record_file_bytes": 512 << 20,
    "max_diagnostics": 10_000,
    "max_listed_sites": 1000,
}

PSYCH_STYLES = {1: "plain", 2: "single_quoted", 3: "double_quoted", 4: "literal", 5: "folded"}
NULL_PLAIN = frozenset(("", "~", "null", "Null", "NULL"))
FORBIDDEN_CHARS = ("\r", "\u0085", " ", " ")  # checked after CRLF removal

ASSUMPTIONS = (
    "Source profile, not installed-config or build attestation: db_path=db, RENEWAL and "
    "RENEWAL_ASPD defined, shouldLoadGenerator=false, YAML (not SQL) item/monster branch.",
    "The server runs from rathena/ on a case-sensitive filesystem; import paths are literal "
    "server-root snapshot keys. A canonical path under conf/db/npc/sql-files that is not in the "
    "snapshot is a known fopen failure; any other unresolvable path is unsupported.",
    "Every database-specific row callback returns normally. Rows are raw declarations; "
    "positive native load return values are not certified.",
)
EXCLUSIONS = [
    "native rapidyaml parser parity (Psych AST is used; differences are refused, not guessed)",
    "parseBodyNode typed row parsing, defaults, references, merges and row acceptance",
    "accepted, effective, loaded, spawned or playable entity counts",
    "loadingFinished, reload clear, constructor side effects and post-processing",
    "installed overlays, import directory contents beyond the stock snapshot, SQL branches",
    "script execution or interpretation of block scalars",
    "episode, content or runtime readiness",
]
LIMIT_NOTES = (
    "Hard controls: fixed verified input bytes per file, child CPU seconds (RLIMIT_CPU), "
    "wall-clock termination, capped stdout/stderr capture, node/depth traversal budgets in "
    "the adapter and Python, a scalar-byte budget in Python, and graph/output budgets. "
    "Psych constructs its AST before these traversal/scalar checks; they are not AST "
    "construction or hard memory limits.",
    "There is no hard memory bound: address-space/data limits are not set because they fail "
    "on macOS before the parser launches. Peak memory follows the verified input size.",
    "Psych marks are zero-based Unicode character line/column; they are converted to UTF-8 "
    "byte offsets against LF/CRLF lines. Lone CR, NEL, LS, PS, a BOM, NUL and invalid UTF-8 "
    "are refused as unsupported input.",
    "Publication reserves the output with an exclusive private mkdir and writes the "
    "completion record last. A same-user concurrent writer could interfere between steps; "
    "without yaml-graph-complete.json the output is not complete.",
)

# Authored Psych adapter: parse_stream AST only, flattened in preorder. It never calls
# to_ruby/load, never resolves aliases and never evaluates input text.
ADAPTER = r'''
require "psych"
require "json"
max_nodes = Integer(ARGV[0])
max_depth = Integer(ARGV[1])
out = {"ruby" => RUBY_VERSION, "psych" => Psych::VERSION, "libyaml" => Psych::LIBYAML_VERSION}
if ARGV[2] == "versions"
  $stdout.binmode
  $stdout.write(JSON.generate(out))
  exit 0
end
begin
  src = $stdin.binmode.read
  src.force_encoding(Encoding::UTF_8)
  raise ArgumentError, "invalid UTF-8" unless src.valid_encoding?
  stream = Psych.parse_stream(src)
  nodes = []
  stack = [[stream, 0]]
  until stack.empty?
    node, depth = stack.pop
    if nodes.size >= max_nodes
      out["outcome"] = "budget"; out["budget"] = "max_nodes_per_file"
      out["nodes_observed"] = nodes.size; nodes = nil; break
    end
    if depth > max_depth
      out["outcome"] = "budget"; out["budget"] = "max_depth"
      out["nodes_observed"] = nodes.size; nodes = nil; break
    end
    loc = [node.start_line, node.start_column, node.end_line, node.end_column]
    kids = nil
    case node
    when Psych::Nodes::Scalar
      nodes << ["S", *loc, node.value, node.style, node.tag, node.anchor]
    when Psych::Nodes::Alias
      nodes << ["A", *loc, node.anchor]
    when Psych::Nodes::Mapping
      kids = node.children
      nodes << ["M", *loc, kids.size, node.style, node.tag, node.anchor]
    when Psych::Nodes::Sequence
      kids = node.children
      nodes << ["Q", *loc, kids.size, node.style, node.tag, node.anchor]
    when Psych::Nodes::Document
      kids = node.children
      nodes << ["D", *loc, kids.size, node.version, node.tag_directives.size,
                node.implicit, node.implicit_end]
    when Psych::Nodes::Stream
      kids = node.children
      nodes << ["T", *loc, kids.size]
    else
      raise ArgumentError, "unexpected node class"
    end
    kids.reverse_each { |c| stack.push([c, depth + 1]) } if kids
  end
  stream = nil
  if nodes
    out["outcome"] = "ok"; out["nodes"] = nodes
  end
rescue Psych::SyntaxError => e
  out["outcome"] = "syntax_error"
  out["problem"] = e.problem.to_s[0, 200]; out["context"] = e.context.to_s[0, 200]
  out["line"] = e.line; out["column"] = e.column
rescue ArgumentError, EncodingError => e
  out["outcome"] = "adapter_refusal"; out["problem"] = e.message.to_s[0, 200]
end
$stdout.binmode
$stdout.write(JSON.generate(out))
'''


class InventoryError(ValueError):
    category = "error"


class InputError(InventoryError):
    """Snapshot, parser identity or argument refusal (exit 2, nothing published)."""
    category = "input"


class OutputError(InventoryError):
    """Publication refusal or failure (exit 2)."""
    category = "publication"


class Stop(Exception):
    """An unsupported state: certain traversal stops here; the rest is unresolved."""

    def __init__(self, kind, detail, **extra):
        super().__init__(f"{kind}: {detail}")
        self.record = {"kind": kind, "detail": detail, **extra}


class ChildFailure(Exception):
    """Ordinary child setup/I/O/finalization failure after all cleanup is attempted."""

    def __init__(self, detail, adapter):
        super().__init__(detail)
        self.adapter = adapter


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def canonical_json(value):
    """Fingerprint encoding: sorted keys, compact separators, ASCII escapes (UTF-16 pairs)."""
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"),
                      allow_nan=False)


def _load_sibling(name):
    path = Path(__file__).resolve().with_name(name + ".py")
    spec = importlib.util.spec_from_file_location("_yaml_graph_" + name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, sha256(path.read_bytes())


def read_snapshot(root):
    """Verify the full pinned snapshot with the unmodified server_selection reader."""
    selection, reader_sha = _load_sibling("server_selection")
    try:
        manifest_bytes, files = selection.read_snapshot(root)
    except selection.SelectionError as exc:
        raise InputError(f"snapshot refused: {exc}") from None
    return manifest_bytes, files, {
        "reader": "tools/renewal/server_selection.py read_snapshot (default pins)",
        "reader_sha256": reader_sha,
        "manifest_sha256": selection.PINNED_MANIFEST_SHA256,
        "pinned_counts": dict(selection.PINNED_COUNTS),
    }


# --- Bounded Psych child -----------------------------------------------------------

def _child_limits(cpu):
    def apply():
        resource.setrlimit(resource.RLIMIT_CPU, (cpu, cpu))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return apply


def run_child(args, data, limits, ruby=RUBY, script=ADAPTER, *, stats=None):
    """Run the adapter with stdin=data under CPU/wall/stdout/stderr caps.

    Returns (returncode, stdout bytes, stderr bytes, failure or None)."""
    out, err = bytearray(), bytearray()
    observed = {"stdout": 0, "stderr": 0}
    eof = {"stdout": False, "stderr": False}
    failure = error = None
    sel = None
    code = None
    cleanup_errors = []
    proc = subprocess.Popen(
        [ruby, "--disable-gems", "-W0", "-e", script, "--", *args],
        stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={"PATH": "/usr/bin:/bin", "LC_ALL": "C"}, cwd="/",
        preexec_fn=_child_limits(limits["cpu_seconds"]), close_fds=True)
    # Everything after successful Popen is covered, including selector setup.
    try:
        deadline = time.monotonic() + limits["wall_seconds"]
        sel = selectors.DefaultSelector()
        pending = memoryview(data)
        os.set_blocking(proc.stdin.fileno(), False)
        sel.register(proc.stdin, selectors.EVENT_WRITE)
        sel.register(proc.stdout, selectors.EVENT_READ)
        sel.register(proc.stderr, selectors.EVENT_READ)
        if not pending:
            sel.unregister(proc.stdin)
            proc.stdin.close()
        while sel.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                failure = "wall_timeout"
                break
            for key, _ in sel.select(min(remaining, 1.0)):
                if key.fileobj is proc.stdin:
                    try:
                        written = os.write(proc.stdin.fileno(), pending[:1 << 16])
                    except BrokenPipeError:
                        written = len(pending)
                    pending = pending[written:]
                    if not pending:
                        sel.unregister(proc.stdin)
                        proc.stdin.close()
                    continue
                chunk = os.read(key.fileobj.fileno(), 1 << 16)
                stream_name = "stdout" if key.fileobj is proc.stdout else "stderr"
                observed[stream_name] += len(chunk)
                if not chunk:
                    eof[stream_name] = True
                    sel.unregister(key.fileobj)
                    continue
                buf, cap, name = ((out, limits["max_stdout_bytes"], "stdout_cap")
                                  if key.fileobj is proc.stdout else
                                  (err, limits["max_stderr_bytes"], "stderr_cap"))
                if len(buf) + len(chunk) > cap:
                    buf += chunk[:max(0, cap - len(buf))]
                    failure = name
                    break
                buf += chunk
            if failure:
                break
    except BaseException as exc:
        error = exc
    finally:
        # One cleanup error must not bypass killing/reaping or the other pipes.
        if sel is not None:
            try:
                sel.close()
            except BaseException as exc:
                cleanup_errors.append(exc)
        aborted = failure is not None or error is not None or bool(cleanup_errors)
        if aborted:
            try:
                proc.kill()
            except BaseException as exc:
                cleanup_errors.append(exc)
        try:
            timeout = 1.0 if aborted else max(1.0, deadline - time.monotonic())
            code = proc.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            failure = failure or "wall_timeout"
            try:
                proc.kill()
            except BaseException as exc:
                cleanup_errors.append(exc)
            try:
                code = proc.wait(timeout=1.0)
            except BaseException as exc:
                cleanup_errors.append(exc)
        except BaseException as exc:
            cleanup_errors.append(exc)
            try:
                proc.kill()
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
            try:
                code = proc.wait(timeout=1.0)
            except BaseException as cleanup_exc:
                cleanup_errors.append(cleanup_exc)
        for stream in (proc.stdin, proc.stdout, proc.stderr):
            try:
                if not stream.closed:
                    stream.close()
            except BaseException as exc:
                cleanup_errors.append(exc)
    info = {"stdout_bytes": len(out), "stderr_bytes": len(err), "exit": code,
            "stdout_observed_bytes": observed["stdout"],
            "stderr_observed_bytes": observed["stderr"],
            "stdout_complete": eof["stdout"], "stderr_complete": eof["stderr"]}
    if cleanup_errors:
        info["cleanup_errors"] = [type(exc).__name__ for exc in cleanup_errors]
    if stats is not None:
        stats.update(info)
    if error is not None or cleanup_errors:
        primary = error if error is not None else cleanup_errors[0]
        primary = next((exc for exc in ([error] if error is not None else []) + cleanup_errors
                        if not isinstance(exc, Exception)), primary)
        if not isinstance(primary, Exception):
            raise primary
        raise ChildFailure(type(primary).__name__ + ": " + str(primary)[:200], info) from primary
    if failure is None and code == -signal.SIGXCPU:
        failure = "cpu_limit"
    elif failure is None and code is not None and code < 0:
        failure = f"signal_{-code}"
    return code, bytes(out), bytes(err), failure


def _strict_json(data, what):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError(f"duplicate key {key!r}")
            result[key] = value
        return result
    try:
        return json.loads(data.decode("utf-8"), object_pairs_hook=pairs)
    except (UnicodeDecodeError, ValueError) as exc:
        raise ValueError(f"{what}: malformed adapter output ({exc})") from None


def check_parser(limits=LIMITS, ruby=RUBY):
    """Confirm the existing Ruby/Psych/libyaml identity before any parse."""
    if not os.path.isfile(ruby):
        raise InputError(f"parser {ruby} is not present")
    try:
        code, out, _err, failure = run_child([str(limits["max_nodes_per_file"]),
                                              str(limits["max_depth"]), "versions"], b"", limits,
                                             ruby)
    except (ChildFailure, OSError) as exc:
        raise InputError(f"parser identity check failed ({exc})") from None
    if failure or code != 0:
        raise InputError(f"parser identity check failed ({failure or code})")
    try:
        found = _strict_json(out, "versions")
    except ValueError as exc:
        raise InputError(str(exc)) from None
    if found != PARSER_PINS:
        raise InputError(f"parser identity {found} is not the pinned {PARSER_PINS}")
    return dict(found)


class Node:
    """Psych AST node: kind S/M/Q/A/D/T, zero-based character marks."""
    __slots__ = ("kind", "start", "end", "value", "style", "tag", "anchor", "children", "extra")

    def __init__(self, kind, start, end):
        self.kind, self.start, self.end = kind, start, end
        self.value = self.style = self.tag = self.anchor = self.extra = None
        self.children = None


def _int(value, what):
    if type(value) is not int or value < 0:
        raise ValueError(f"adapter output: bad {what}")
    return value


def build_tree(flat, limits):
    """Rebuild the preorder flat list into Nodes; validate shape. Returns (stream, counts)."""
    if not isinstance(flat, list) or not flat:
        raise ValueError("adapter output: empty node list")
    if len(flat) > limits["max_nodes_per_file"]:
        raise Stop("work_limit", "max_nodes_per_file", limit=limits["max_nodes_per_file"])
    counts = {k: 0 for k in "SMQADT"}
    root = None
    scalar_stop = None
    stack = []  # [node, remaining children]
    for item in flat:
        if (not isinstance(item, list) or len(item) < 5
                or not isinstance(item[0], str) or item[0] not in counts):
            raise ValueError("adapter output: malformed node")
        kind = item[0]
        node = Node(kind, (_int(item[1], "mark"), _int(item[2], "mark")),
                    (_int(item[3], "mark"), _int(item[4], "mark")))
        counts[kind] += 1
        want = 0
        if kind == "S":
            if len(item) != 9 or not isinstance(item[5], str):
                raise ValueError("adapter output: malformed scalar")
            node.value, node.style, node.tag, node.anchor = item[5], item[6], item[7], item[8]
            if (type(node.style) is not int or node.style not in PSYCH_STYLES
                    or any(v is not None and not isinstance(v, str)
                           for v in (node.tag, node.anchor))):
                raise ValueError("adapter output: malformed scalar metadata")
            if len(node.value.encode("utf-8", "surrogatepass")) > limits["max_scalar_bytes"]:
                # Validate the entire protocol before calling its node count exact.
                scalar_stop = scalar_stop or Stop("work_limit", "max_scalar_bytes",
                                                   limit=limits["max_scalar_bytes"],
                                                   mark=list(node.start))
        elif kind == "A":
            if len(item) != 6 or not isinstance(item[5], str):
                raise ValueError("adapter output: malformed alias")
            node.anchor = item[5]
        elif kind in "MQ":
            if len(item) != 9:
                raise ValueError("adapter output: malformed container")
            want = _int(item[5], "child count")
            if kind == "M" and want % 2:
                raise ValueError("adapter output: odd mapping child count")
            node.style, node.tag, node.anchor = item[6], item[7], item[8]
            if (type(node.style) is not int or node.style not in (1, 2)
                    or any(v is not None and not isinstance(v, str)
                           for v in (node.tag, node.anchor))):
                raise ValueError("adapter output: malformed container metadata")
            node.children = []
        elif kind == "D":
            if len(item) != 10:
                raise ValueError("adapter output: malformed document")
            want = _int(item[5], "child count")
            if want != 1:
                raise ValueError("adapter output: document must have one child")
            if (not isinstance(item[6], list) or len(item[6]) not in (0, 2)
                    or any(type(n) is not int or n < 0 for n in item[6])
                    or type(item[7]) is not int or item[7] < 0
                    or type(item[8]) is not bool or type(item[9]) is not bool):
                raise ValueError("adapter output: malformed document metadata")
            node.extra = {"version": item[6], "tag_directives": item[7],
                          "implicit": item[8], "implicit_end": item[9]}
            node.children = []
        else:
            if len(item) != 6:
                raise ValueError("adapter output: malformed stream")
            want = _int(item[5], "child count")
            node.children = []
        if stack:
            parent = stack[-1]
            if ((parent[0].kind == "T" and kind != "D")
                    or (parent[0].kind != "T" and kind in "TD")):
                raise ValueError("adapter output: invalid stream/document nesting")
            parent[0].children.append(node)
            parent[1] -= 1
        elif root is None:
            root = node
        else:
            raise ValueError("adapter output: several roots")
        if len(stack) > limits["max_depth"] + 1:
            raise Stop("work_limit", "max_depth", limit=limits["max_depth"])
        if want:
            stack.append([node, want])
        while stack and stack[-1][1] == 0:
            stack.pop()
    if stack or root is None or root.kind != "T":
        raise ValueError("adapter output: incomplete tree")
    if scalar_stop is not None:
        scalar_stop.record["validated_node_counts"] = counts
        raise scalar_stop
    return root, counts


def parse_yaml(data, limits=LIMITS, ruby=RUBY):
    """Bounded Psych parse of verified bytes. Returns (stream Node, info) or raises Stop."""
    info = {"input_bytes": len(data), "stdout_bytes": 0, "stderr_bytes": 0,
            "stdout_observed_bytes": 0, "stderr_observed_bytes": 0,
            "stdout_complete": False, "stderr_complete": False, "exit": None,
            "node_total": None, "node_count_lower_bound": 0}
    if len(data) > limits["max_input_bytes"]:
        raise Stop("work_limit", "max_input_bytes", limit=limits["max_input_bytes"],
                   bytes=len(data), adapter=info)
    try:
        code, out, err, failure = run_child([str(limits["max_nodes_per_file"]),
                                             str(limits["max_depth"])], data, limits, ruby,
                                            stats=info)
    except ChildFailure as exc:
        info.update(exc.adapter)
        raise Stop("parser_failure", str(exc), adapter=info) from None
    except OSError as exc:
        raise Stop("parser_failure", type(exc).__name__ + ": " + str(exc)[:200],
                   adapter=info) from None
    info.update(stdout_bytes=len(out), stderr_bytes=len(err), exit=code)
    info["stdout_observed_bytes"] = max(info["stdout_observed_bytes"], len(out))
    info["stderr_observed_bytes"] = max(info["stderr_observed_bytes"], len(err))
    if failure is not None:
        raise Stop("parser_limit", failure, adapter=info)
    if code != 0:
        raise Stop("parser_failure", "adapter exited abnormally", adapter=info)
    try:
        doc = _strict_json(out, "parse")
    except ValueError as exc:
        raise Stop("parser_failure", str(exc), adapter=info) from None
    if not isinstance(doc, dict):
        raise Stop("parser_failure", "adapter response is not an object", adapter=info)
    versions = {k: doc.get(k) for k in PARSER_PINS}
    if versions != PARSER_PINS:
        raise Stop("parser_failure", "parser identity changed", adapter=info)
    outcome = doc.get("outcome")
    if outcome == "budget":
        observed = doc.get("nodes_observed")
        if type(observed) is not int or not 0 <= observed <= limits["max_nodes_per_file"]:
            raise Stop("parser_failure", "malformed adapter budget count", adapter=info)
        info["node_count_lower_bound"] = observed
        raise Stop("work_limit", str(doc.get("budget")), adapter=info)
    if outcome in ("syntax_error", "adapter_refusal"):
        raise Stop("parser_refusal", "Psych refused the input (not a native rapidyaml result)",
                   psych={k: doc.get(k) for k in ("problem", "context", "line", "column")
                          if k in doc}, adapter=info)
    if outcome != "ok":
        raise Stop("parser_failure", "unknown adapter outcome", adapter=info)
    try:
        tree, counts = build_tree(doc.get("nodes"), limits)
    except Stop as stop:
        counts = stop.record.pop("validated_node_counts", None)
        if counts is not None:
            info["node_total"] = info["node_count_lower_bound"] = sum(counts.values())
            info["nodes"] = {"stream": counts["T"], "document": counts["D"],
                             "mapping": counts["M"], "sequence": counts["Q"],
                             "scalar": counts["S"], "alias": counts["A"]}
        stop.record["adapter"] = info
        raise
    except (ValueError, TypeError, KeyError, IndexError) as exc:
        raise Stop("parser_failure", str(exc), adapter=info) from None
    del doc
    info["nodes"] = {"stream": counts["T"], "document": counts["D"], "mapping": counts["M"],
                     "sequence": counts["Q"], "scalar": counts["S"], "alias": counts["A"]}
    info["node_total"] = sum(counts.values())
    info["node_count_lower_bound"] = info["node_total"]
    return tree, info


# --- Input checks, marks and byte spans ---------------------------------------------

def precheck_bytes(data):
    """Refuse bytes the mark conversion or the native reader cannot be trusted with."""
    if b"\0" in data:
        raise Stop("unsupported_input", "NUL byte (native reading would truncate)")
    if data.startswith(b"\xef\xbb\xbf"):
        raise Stop("unsupported_input", "UTF-8 byte order mark")
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise Stop("unsupported_input", f"invalid UTF-8 at byte {exc.start}") from None
    bare = text.replace("\r\n", "\n")
    for char in FORBIDDEN_CHARS:
        if char in bare:
            raise Stop("unsupported_input", f"line break U+{ord(char):04X} other than LF/CRLF")
    return text


class LineIndex:
    """Map Psych (line, character column) marks to byte offsets of the original bytes."""

    def __init__(self, data):
        self.data = data
        self.starts = [0]
        at = data.find(b"\n")
        while at >= 0:
            self.starts.append(at + 1)
            at = data.find(b"\n", at + 1)
        self._cache = {}

    def content(self, line):
        start = self.starts[line]
        end = self.starts[line + 1] - 1 if line + 1 < len(self.starts) else len(self.data)
        if end > start and self.data[end - 1:end] == b"\r" and line + 1 < len(self.starts):
            end -= 1
        return start, end

    def offset(self, mark):
        line, col = mark
        if line >= len(self.starts):
            raise Stop("mark_out_of_bounds", f"line {line} beyond input", mark=list(mark))
        start, end = self.content(line)
        raw = self.data[start:end]
        if raw.isascii():
            if col > len(raw):
                raise Stop("mark_out_of_bounds", f"column {col} beyond line", mark=list(mark))
            return start + col
        chars = self._cache.get(line)
        if chars is None:
            chars = raw.decode("utf-8")
            self._cache = {line: chars}
        if col > len(chars):
            raise Stop("mark_out_of_bounds", f"column {col} beyond line", mark=list(mark))
        return start + len(chars[:col].encode("utf-8"))

    def span(self, node):
        begin, finish = self.offset(node.start), self.offset(node.end)
        if finish < begin:
            raise Stop("mark_out_of_bounds", "end before start", mark=list(node.start))
        return begin, finish


def node_kind(node):
    return {"S": "scalar", "M": "mapping", "Q": "sequence", "A": "alias"}[node.kind]


def check_syntax(stream):
    """Refuse constructs outside the bounded profile, file-wide. Return (root map, report)."""
    duplicates = []
    if len(stream.children) != 1:
        raise Stop("unsupported_syntax", f"{len(stream.children)} documents (exactly one "
                   "supported)")
    document = stream.children[0]
    if document.extra["version"] or document.extra["tag_directives"]:
        raise Stop("unsupported_syntax", "YAML/TAG directive")
    if len(document.children) != 1 or document.children[0].kind != "M":
        raise Stop("unsupported_syntax", "document root is not a mapping", mark=[0, 0])
    stack = [document.children[0]]
    while stack:
        node = stack.pop()
        if node.kind == "A":
            raise Stop("unsupported_syntax", "alias", mark=list(node.start))
        if node.tag is not None:
            raise Stop("unsupported_syntax", "explicit tag", mark=list(node.start))
        if node.anchor is not None:
            raise Stop("unsupported_syntax", "anchor", mark=list(node.start))
        if node.kind == "S":
            if node.style not in PSYCH_STYLES:
                raise Stop("unsupported_syntax", f"scalar style {node.style!r}",
                           mark=list(node.start))
            continue
        if node.kind == "M":
            if len(node.children) % 2:
                raise Stop("parser_failure", "odd mapping child count", mark=list(node.start))
            seen = {}
            for key in node.children[0::2]:
                if key.kind != "S":
                    raise Stop("unsupported_syntax", "complex (non-scalar) mapping key",
                               mark=list(key.start))
                if key.style == 1 and key.value == "<<":
                    raise Stop("unsupported_syntax", "merge key '<<'", mark=list(key.start))
                seen[key.value] = seen.get(key.value, 0) + 1
            for name, times in seen.items():
                if times > 1:
                    duplicates.append({"key": name, "occurrences": times,
                                       "mapping_start_mark": list(node.start)})
        stack.extend(reversed(node.children))
    return document.children[0], duplicates


# --- Control-field lookup (first exact key, as Tree::find_child) ----------------------

def find(mapping, name):
    for i in range(0, len(mapping.children), 2):
        if mapping.children[i].value == name:
            return mapping.children[i], mapping.children[i + 1]
    return None


def is_null(scalar):
    return scalar.style == 1 and scalar.value in NULL_PLAIN


def scalar_record(node, lines, cap=256):
    begin, finish = lines.span(node)
    record = {"start_mark": list(node.start), "end_mark": list(node.end),
              "byte_span": [begin, finish], "span_sha256": sha256(lines.data[begin:finish])}
    if node.kind == "S":
        text = node.value
        record.update({"kind": "scalar", "style": PSYCH_STYLES[node.style],
                       "text": text if cap is None else text[:cap], "null": is_null(node)})
        if cap is not None and len(text) > cap:
            record["text_truncated_from_chars"] = len(text)
    else:
        record["kind"] = node_kind(node)
    return record


def control_scalar(mapping, name, where):
    """Return (key, value) for a control field; refuse non-scalar values (unsupported)."""
    found = find(mapping, name)
    if found is not None and found[1].kind != "S":
        raise Stop("unsupported_control_shape", f"{where}.{name} is a {node_kind(found[1])}",
                   mark=list(found[1].start))
    return found


def as_bool(scalar):
    """database.cpp asBool on a scalar: (ok, value, reason)."""
    if is_null(scalar):
        return False, None, "null"
    text = scalar.value
    lowered = "".join(chr(ord(c) + 32) if "A" <= c <= "Z" else c for c in text)
    if lowered == "true":
        return True, True, None
    if lowered == "false":
        return True, False, None
    return False, None, "unknown_boolean_text"


def parse_version(scalar):
    """Bounded Version profile: ASCII decimal 0..65535, quoted or plain, base 10."""
    text = scalar.value
    if text and all("0" <= c <= "9" for c in text):
        significant = text.lstrip("0") or "0"
        if len(significant) <= 5:
            value = int(significant, 10)
            if value <= 0xFFFF:
                return value
    raise Stop("unsupported_version_text", "Version is not ASCII decimal 0..65535 (native c4 "
               "conversion accepts other bases and wraps; not modelled)", mark=list(scalar.start))


# --- Body rows ------------------------------------------------------------------------

def normalize(node):
    """Semantic fingerprint form: kind, ordered children, scalar decoded text and style."""
    if node.kind == "S":
        return {"k": "s", "t": node.value, "y": node.style}
    return {"k": "m" if node.kind == "M" else "q", "c": [normalize(c) for c in node.children]}


def count_nodes(node):
    total, stack = 0, [node]
    while stack:
        current = stack.pop()
        total += 1
        if current.children:
            stack.extend(current.children)
    return total


def row_record(row, lines):
    begin, finish = lines.span(row)
    fields, raw_ids = [], []
    for ordinal in range(len(row.children) // 2):
        key, value = row.children[2 * ordinal], row.children[2 * ordinal + 1]
        fields.append({"key": key.value, "key_style": PSYCH_STYLES[key.style],
                       "kind": node_kind(value)})
        if key.value == "Id":
            raw_ids.append({"field_ordinal": ordinal, **scalar_record(value, lines, cap=None)})
    return {
        "start_mark": list(row.start), "end_mark": list(row.end),
        "byte_span": [begin, finish], "span_sha256": sha256(lines.data[begin:finish]),
        "fields": fields, "field_count": len(fields), "node_count": count_nodes(row),
        "fingerprint_sha256": sha256(canonical_json(normalize(row)).encode("ascii")),
        "raw_ids": raw_ids,
    }


# --- Graph -----------------------------------------------------------------------------

def check_path(text):
    """Literal server-root import path: canonical relative printable ASCII only."""
    if not text or len(text) > 4096 or any(not (" " <= c <= "~") for c in text):
        return "non-printable, non-ASCII or empty path"
    if "\\" in text:
        return "backslash in path"
    if text.startswith("/"):
        return "absolute path"
    parts = text.split("/")
    if any(p in ("", ".", "..") for p in parts):
        return "empty, '.' or '..' path component"
    return None


class Graph:
    def __init__(self, files, emit, roots=ROOTS, profile=PROFILE, limits=LIMITS, ruby=RUBY):
        self.files, self.emit, self.roots = files, emit, roots
        self.profile, self.limits, self.ruby = profile, limits, ruby
        self.visits, self.edges, self.clears, self.diagnostics = [], [], [], []
        self.known_failures, self.unresolved, self.reads = [], [], {}
        self.stop = None
        self.rows = 0
        self.db = {}
        self.usage = {"visits": 0, "edges": 0, "nodes": 0, "input_bytes_parsed": 0,
                      "input_bytes_examined": 0, "parser_attempts": 0,
                      "exact_ast_nodes": 0, "unknown_node_count_attempts": 0,
                      "adapter_stdout_bytes": 0, "adapter_stderr_bytes": 0,
                      "adapter_stdout_observed_bytes": 0, "adapter_stderr_observed_bytes": 0,
                      "rows": 0}
        self.dirs = None

    def diag(self, record):
        if len(self.diagnostics) >= self.limits["max_diagnostics"]:
            raise Stop("work_limit", "max_diagnostics", limit=self.limits["max_diagnostics"])
        self.diagnostics.append(record)

    def is_dir(self, key):
        if self.dirs is None:
            self.dirs = set()
            for path in self.files:
                parts = path.split("/")
                for i in range(1, len(parts)):
                    self.dirs.add("/".join(parts[:i]))
        return key in self.dirs

    def run(self):
        for order, root in enumerate(self.roots):
            state = {"database": root["database"], "root_order": order, "epoch": 0,
                     "rows": 0, "root_visit": None, "root_return": None}
            self.db[root["database"]] = state
            if self.stop is not None:
                self.unresolved.append({"kind": "root_not_started", "root_order": order,
                                        "database": root["database"], "path": root["path"]})
                continue
            try:
                state["root_return"] = self.load(root, state, root["path"], None, None, 0, [])
            except Stop as stop:
                self.stop = dict(stop.record)
                state["root_return"] = None
        return self

    def load(self, root, state, path, parent, edge, depth, active):
        """YamlDatabase::load(path). Returns True/False (modelled) or raises Stop."""
        if self.usage["visits"] >= self.limits["max_visits"]:
            raise Stop("work_limit", "max_visits", limit=self.limits["max_visits"],
                       path=path, parent_visit=parent)
        self.usage["visits"] += 1
        visit = {"visit": len(self.visits), "database": root["database"],
                 "root_order": state["root_order"], "path": path, "parent_visit": parent,
                 "parent_edge": edge, "depth": depth, "epoch_at_start": state["epoch"],
                 "status": None, "modeled_graph_return": None, "diagnostics": []}
        self.visits.append(visit)
        if state["root_visit"] is None:
            state["root_visit"] = visit["visit"]
        try:
            return self._load(root, state, path, visit, depth, active)
        except Stop as stop:
            if visit["status"] is None:
                visit["status"] = "unsupported"
                visit["unsupported"] = stop.record
            else:
                visit["traversal"] = "stopped by an unsupported state in its imports"
            raise

    def _load(self, root, state, path, visit, depth, active):
        problem = check_path(path)
        if problem:
            raise Stop("unsupported_path", problem)
        if path in active:
            raise Stop("import_cycle", "path is already being loaded on the active import stack",
                       active=list(active))
        if depth > self.limits["max_import_depth"]:
            raise Stop("work_limit", "max_import_depth", limit=self.limits["max_import_depth"])
        key = SERVER_ROOT + path
        data = self.files.get(key)
        if data is None:
            if self.is_dir(key):
                raise Stop("unsupported_path", "path names a snapshot directory")
            if path.split("/")[0] not in SCOPE_DIRS:
                raise Stop("unsupported_path", "outside the snapshot scope directories")
            visit["status"] = "known_failure_missing_file"
            visit["modeled_graph_return"] = False
            self.known_failures.append({"visit": visit["visit"], "kind": "missing_file",
                                        "path": path, "source": "database.cpp:94-98 fopen"})
            return False
        digest = sha256(data)
        visit.update({"bytes": len(data), "sha256": digest})
        read = self.reads.setdefault(path, {"path": path, "bytes": len(data), "sha256": digest,
                                            "visits": []})
        read["visits"].append(visit["visit"])
        self.usage["input_bytes_examined"] += len(data)
        precheck_bytes(data)
        self.usage["input_bytes_parsed"] += len(data)
        self.usage["parser_attempts"] += 1
        try:
            tree, info = parse_yaml(data, self.limits, self.ruby)
        except Stop as stop:
            info = stop.record.get("adapter")
            if info is not None:
                self.charge_parser(visit, info, stop.record["kind"])
            raise
        self.charge_parser(visit, info, "ok")
        visit["ast"] = {"nodes": info["nodes"], "node_total": info["node_total"],
                        "adapter_stdout_bytes": info["stdout_bytes"]}
        if self.usage["nodes"] > self.limits["max_nodes_total"]:
            raise Stop("work_limit", "max_nodes_total", limit=self.limits["max_nodes_total"])
        root_map, duplicates = check_syntax(tree)
        del tree
        visit["duplicate_key_sites"] = {"count": len(duplicates),
                                        "sites": duplicates[:self.limits["max_listed_sites"]]}
        lines = LineIndex(data)
        if not self.header(root, root_map, visit, lines):
            visit["status"] = "known_failure_header"
            visit["modeled_graph_return"] = False
            return False
        self.clear(state, root_map, visit, lines)
        self.body(state, root_map, visit, lines)
        visit["status"] = "read_compatible"
        self.imports(root, state, root_map, visit, lines, depth, active + [path])
        visit["modeled_graph_return"] = True
        return True

    def charge_parser(self, visit, info, outcome):
        """Charge a parse exactly once, including refusals and observed prefix work."""
        visit["parser_attempt"] = {**info, "outcome": outcome}
        total = info["node_total"]
        self.usage["nodes"] += info["node_count_lower_bound"]
        if total is None:
            self.usage["unknown_node_count_attempts"] += 1
        else:
            self.usage["exact_ast_nodes"] += total
        for name in ("stdout_bytes", "stderr_bytes", "stdout_observed_bytes",
                     "stderr_observed_bytes"):
            self.usage["adapter_" + name] += info[name]

    def header(self, root, root_map, visit, lines):
        found = find(root_map, "Header")
        failure = None
        record = visit["header"] = {}
        if found is None:
            failure = "no Header node"
        else:
            node = found[1]
            if node.kind != "M":
                raise Stop("unsupported_control_shape", f"Header is a {node_kind(node)}",
                           mark=list(node.start))
            if not node.children:
                failure = "no Header node (empty mapping has no children)"
            else:
                type_ = control_scalar(node, "Type", "Header")
                if type_ is None:
                    failure = "missing Type"
                else:
                    record["type"] = scalar_record(type_[1], lines)
                    if is_null(type_[1]):
                        failure = "Type has no value"
                    elif type_[1].value != root["database"]:
                        failure = "Type mismatch"
                if failure is None:
                    version = control_scalar(node, "Version", "Header")
                    if version is None:
                        failure = "missing Version"
                    else:
                        record["version"] = scalar_record(version[1], lines, cap=None)
                        if is_null(version[1]):
                            failure = "Version has no value"
                        else:
                            value = parse_version(version[1])
                            record["version_value"] = value
                            if value > root["version"]:
                                failure = "Version above current"
                            elif value < root["minimum_version"]:
                                failure = "Version below minimum"
                            elif value < root["version"]:
                                record["compatibility"] = "older_warning"
                                self.diag({"visit": visit["visit"], "kind": "older_version",
                                           "version": value, "current": root["version"],
                                           "source": "database.cpp:66-68 warning, continues"})
                            else:
                                record["compatibility"] = "current"
        if failure is not None:
            record["failure"] = failure
            self.known_failures.append({"visit": visit["visit"], "kind": "header",
                                        "detail": failure, "path": visit["path"],
                                        "source": "database.cpp:37-76,124-128"})
            return False
        return True

    def clear(self, state, root_map, visit, lines):
        header = find(root_map, "Header")[1]
        found = control_scalar(header, "Clear", "Header")
        if found is None:
            visit["clear"] = {"present": False}
            return
        ok, value, reason = as_bool(found[1])
        record = visit["clear"] = {"present": True, "value": scalar_record(found[1], lines)}
        if not ok:
            record["result"] = "invalid_no_clear"
            self.diag({"visit": visit["visit"], "kind": "clear_invalid", "reason": reason,
                       "source": "database.cpp:253-277 warning, database kept"})
        elif value:
            state["epoch"] += 1
            record["result"] = "clear_event"
            record["epoch_after"] = state["epoch"]
            self.clears.append({"database": state["database"], "visit": visit["visit"],
                                "path": visit["path"], "epoch_after": state["epoch"]})
        else:
            record["result"] = "false_no_clear"

    def body(self, state, root_map, visit, lines):
        found = find(root_map, "Body")
        record = visit["body"] = {"present": found is not None, "rows": 0,
                                  "epoch": state["epoch"]}
        if found is None:
            return
        node = found[1]
        if node.kind != "Q":
            raise Stop("unsupported_control_shape", f"Body is a {node_kind(node)}",
                       mark=list(node.start))
        record["first_global_ordinal"] = self.rows
        for local, row in enumerate(node.children):
            if row.kind != "M":
                raise Stop("unsupported_control_shape",
                           f"Body child {local} is a {node_kind(row)}", mark=list(row.start))
            if self.rows >= self.limits["max_rows_total"]:
                raise Stop("work_limit", "max_rows_total", limit=self.limits["max_rows_total"])
            declaration = {
                "database": state["database"], "root_order": state["root_order"],
                "visit": visit["visit"], "file": visit["path"], "file_sha256": visit["sha256"],
                "epoch": state["epoch"], "local_ordinal": local,
                "database_ordinal": state["rows"], "global_ordinal": self.rows,
                **row_record(row, lines),
            }
            self.emit(declaration)
            self.rows += 1
            self.usage["rows"] += 1
            state["rows"] += 1
            record["rows"] += 1

    def imports(self, root, state, root_map, visit, lines, depth, active):
        footer = find(root_map, "Footer")
        visit["imports"] = []
        if footer is None:
            return
        if footer[1].kind != "M":
            raise Stop("unsupported_control_shape", f"Footer is a {node_kind(footer[1])}",
                       mark=list(footer[1].start))
        found = find(footer[1], "Imports")
        if found is None:
            return
        node = found[1]
        if node.kind != "Q":
            raise Stop("unsupported_control_shape", f"Footer.Imports is a {node_kind(node)}",
                       mark=list(node.start))
        for index, entry in enumerate(node.children):
            try:
                self.edge(root, state, visit, lines, depth, active, index, entry)
            except Stop:
                visit["imports_unresolved_from"] = index + 1
                if index + 1 < len(node.children):
                    self.unresolved.append({"kind": "import_siblings_not_traversed",
                                            "visit": visit["visit"], "path": visit["path"],
                                            "from_edge": index + 1,
                                            "edges": len(node.children) - index - 1})
                raise

    def edge(self, root, state, visit, lines, depth, active, index, entry):
        if self.usage["edges"] >= self.limits["max_edges"]:
            raise Stop("work_limit", "max_edges", limit=self.limits["max_edges"])
        self.usage["edges"] += 1
        edge = {"edge": len(self.edges), "visit": visit["visit"], "index": index,
                "start_mark": list(entry.start)}
        self.edges.append(edge)
        visit["imports"].append(edge["edge"])
        if entry.kind != "M":
            edge["decision"] = "unsupported"
            raise Stop("unsupported_control_shape", f"import entry {index} is a "
                       f"{node_kind(entry)}", mark=list(entry.start))

        def skip(reason, source):
            edge["decision"] = "skip"
            edge["skip_reason"] = reason
            edge["source"] = source
            self.diag({"visit": visit["visit"], "edge": edge["edge"], "kind": "import_skipped",
                       "reason": reason})

        path = control_scalar(entry, "Path", "import") if entry.children else None
        if path is None:
            return skip("path_missing", "database.cpp:186-188 asString fails, continue")
        edge["path"] = scalar_record(path[1], lines, cap=4096)
        if is_null(path[1]):
            return skip("path_null", "database.cpp:186-188 asString fails, continue")
        target = path[1].value
        mode = control_scalar(entry, "Mode", "import")
        if mode is None:
            edge["mode"] = "absent"
        else:
            edge["mode"] = scalar_record(mode[1], lines)
            if is_null(mode[1]):
                return skip("mode_null", "database.cpp:193-195 asString fails, continue")
            compiled = "Renewal" if self.profile["renewal"] else "Prerenewal"
            if (self.profile["renewal"] and not self.profile["renewal_aspd"]
                    and "job_aspd.yml" in target):
                compiled = "Prerenewal"
            edge["compiled_mode"] = compiled
            if mode[1].value != compiled:
                edge["decision"] = "skip"
                edge["skip_reason"] = "mode_mismatch"
                edge["source"] = "database.cpp:197-212"
                return None
        generator = control_scalar(entry, "Generator", "import")
        if generator is None:
            edge["generator"] = "absent"
        else:
            edge["generator"] = scalar_record(generator[1], lines)
            ok, value, reason = as_bool(generator[1])
            if not ok:
                return skip(f"generator_{reason}", "database.cpp:215-219 asBool fails, continue")
            if not (self.profile["should_load_generator"] and value):
                edge["decision"] = "skip"
                edge["skip_reason"] = "generator_false" if not value else "generator_not_enabled"
                edge["source"] = "database.cpp:220-221"
                return None
        edge["decision"] = "load"
        edge["target"] = target
        child = len(self.visits)
        edge["child_visit"] = child
        try:
            returned = self.load(root, state, target, visit["visit"], edge["edge"], depth + 1,
                                 active)
        finally:
            edge["child_status"] = self.visits[child]["status"] if child < len(self.visits) \
                else "not_started"
        edge["child_return_ignored"] = returned
        return None


def summarize(graph):
    """Status and counts for a finished (or stopped) Graph."""
    if graph.stop is not None:
        status = "unsupported"
        meaning = ("an unsupported or unknown state stopped certain traversal; the published "
                   "rows and visits are a qualified prefix and the rest is unresolved")
    elif graph.known_failures:
        status = "incomplete"
        meaning = ("traversal is determinate under the profile but some selected visits are "
                   "known fopen/Header failures")
    else:
        status = "complete"
        meaning = ("bounded Psych-AST source-profile conditional graph: every selected visit "
                   "was read and header-compatible and every Body row was catalogued, assuming "
                   "row callbacks return normally; not native execution, parser parity, row "
                   "acceptance, content or episode readiness")
    per_db = {}
    for name, state in graph.db.items():
        visits = [v for v in graph.visits if v["database"] == name]
        per_db[name] = {"root_order": state["root_order"], "visits": len(visits),
                        "raw_rows": state["rows"], "final_epoch": state["epoch"],
                        "clear_events": sum(1 for c in graph.clears if c["database"] == name),
                        "modeled_root_return": state["root_return"]}
    return status, meaning, per_db


# --- Publication -----------------------------------------------------------------------

DIR_FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
FILE_FLAGS = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK


def render(document):
    return (json.dumps(document, ensure_ascii=True, indent=1, sort_keys=True,
                       allow_nan=False) + "\n").encode("ascii")


def render_row(row):
    return (canonical_json(row) + "\n").encode("ascii")


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


def _identity(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


class RecordFile:
    """Exclusive, no-follow, 0600 streaming JSONL writer with a running hash."""

    def __init__(self, dir_fd, name, created, limit):
        fd = os.open(name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
                     dir_fd=dir_fd)
        created[name] = None
        info = os.fstat(fd)
        created[name] = (info.st_dev, info.st_ino)
        self.name, self.limit = name, limit
        self.handle = os.fdopen(fd, "wb")
        os.fchmod(self.handle.fileno(), 0o600)
        self.digest = hashlib.sha256()
        self.bytes = self.lines = 0

    def write(self, row):
        line = render_row(row)
        if self.bytes + len(line) > self.limit:
            raise Stop("work_limit", "max_record_file_bytes", limit=self.limit)
        self.handle.write(line)
        self.digest.update(line)
        self.bytes += len(line)
        self.lines += 1

    def close(self):
        self.handle.flush()
        os.fsync(self.handle.fileno())
        self.handle.close()
        return {"file": self.name, "bytes": self.bytes, "lines": self.lines,
                "sha256": self.digest.hexdigest()}


def _write_new(dir_fd, name, data, created):
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


def _verify_published(dir_fd, name, size, digest, expected_identity):
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


def build_manifest(graph, provenance, records):
    status, meaning, per_db = summarize(graph)
    id_occurrences = rows_without_id = rows_multi_id = non_scalar_ids = 0
    for count in graph.id_stats.values():
        id_occurrences += count["occurrences"]
        rows_without_id += count["rows_without_id"]
        rows_multi_id += count["rows_with_several_ids"]
        non_scalar_ids += count["non_scalar_ids"]
    skipped = [e for e in graph.edges if e.get("decision") == "skip"]
    return {
        "kind": "four-root YAML import graph and raw Body declaration history "
                "(source profile, Psych AST)",
        "status": status,
        "status_meaning": meaning,
        **provenance,
        "source": SOURCE,
        "profile": graph.profile,
        "assumptions": list(ASSUMPTIONS),
        "records_file": records,
        "fingerprint": {
            "form": "scalar {k:'s',t:decoded text,y:Psych style 1-5}; mapping {k:'m',c:[key,"
                    "value,...] in order}; sequence {k:'q',c:[...] in order}; no marks/paths",
            "encoding": "json.dumps(sort_keys=True, separators=(',',':'), ensure_ascii=True) "
                        "-> ASCII bytes -> SHA-256 (non-BMP text as UTF-16 escape pairs)",
            "styles": {str(k): v for k, v in PSYCH_STYLES.items()},
        },
        "row_record": {
            "marks": "zero-based Psych (line, Unicode character column)",
            "byte_span": "[start, end) UTF-8 byte offsets of the original file bytes",
            "span_sha256": "SHA-256 of exactly those bytes, original quoting and line endings",
            "raw_ids": "every top-level 'Id' field in order; none collapsed, cast or resolved",
            "ordinals": "local (Body), database_ordinal (per database), global_ordinal",
        },
        "visits": graph.visits,
        "edges": graph.edges,
        "clear_events": graph.clears,
        "exact_reads": [graph.reads[p] for p in sorted(graph.reads)],
        "databases": per_db,
        "counts": {
            "visits": len(graph.visits),
            "read_compatible_visits": sum(1 for v in graph.visits
                                          if v["status"] == "read_compatible"),
            "distinct_files_read": len(graph.reads),
            "edges": len(graph.edges),
            "edges_loaded": sum(1 for e in graph.edges if e.get("decision") == "load"),
            "edges_skipped": len(skipped),
            "skip_reasons": {r: sum(1 for e in skipped if e["skip_reason"] == r)
                             for r in sorted({e["skip_reason"] for e in skipped})},
            "raw_rows": graph.rows,
            "raw_id_occurrences": id_occurrences,
            "rows_without_id": rows_without_id,
            "rows_with_several_ids": rows_multi_id,
            "non_scalar_id_values": non_scalar_ids,
            "clear_events": len(graph.clears),
            "duplicate_key_sites": sum(v.get("duplicate_key_sites", {}).get("count", 0)
                                       for v in graph.visits),
            "ast_nodes": (None if graph.usage["unknown_node_count_attempts"]
                          else graph.usage["exact_ast_nodes"]),
            "known_failures": len(graph.known_failures),
            "unresolved": len(graph.unresolved),
            "diagnostics": len(graph.diagnostics),
        },
        "raw_id_stats": graph.id_stats,
        "known_failures": graph.known_failures,
        "stop": graph.stop,
        "unresolved": graph.unresolved,
        "diagnostics": graph.diagnostics,
        "work_limits": graph.limits,
        "work_usage": graph.usage,
        "limits": list(LIMIT_NOTES),
        "exclusions": EXCLUSIONS,
        "not_counts_of": "accepted, effective, loaded, spawned or playable entities",
    }


def catalog(files, writer, roots=ROOTS, profile=PROFILE, limits=LIMITS, ruby=RUBY):
    """Pure graph over {snapshot path: bytes}; rows go to writer(row). Returns the Graph."""
    stats = {}

    def emit(row):
        writer(row)
        count = stats.setdefault(row["database"], {"occurrences": 0, "rows_without_id": 0,
                                                   "rows_with_several_ids": 0,
                                                   "non_scalar_ids": 0})
        ids = row["raw_ids"]
        count["occurrences"] += len(ids)
        count["rows_without_id"] += not ids
        count["rows_with_several_ids"] += len(ids) > 1
        count["non_scalar_ids"] += sum(1 for i in ids if i["kind"] != "scalar")

    graph = Graph(files, emit, roots, profile, limits, ruby)
    graph.id_stats = stats
    return graph.run()


def run(snapshot, output, limits=LIMITS):
    """CLI pipeline. Returns (target, manifest dict, hashes). Pins/profile are fixed."""
    target = trusted_target(output)
    if os.path.lexists(target):
        raise OutputError(f"output already exists, refusing to overwrite: {target}")
    manifest_bytes, files, reader = read_snapshot(snapshot)
    parser = check_parser(limits)
    provenance = {
        "generator": {"tool": TOOL, "version": VERSION,
                      "source_sha256": sha256(Path(__file__).read_bytes())},
        "input": {"snapshot_manifest_sha256": sha256(manifest_bytes),
                  "files": len(files), "bytes": sum(len(b) for b in files.values()),
                  "verification": reader},
        "parser": {"executable": RUBY, **parser, "api": "Psych.parse_stream AST only",
                   "adapter_sha256": sha256(ADAPTER.encode("utf-8")),
                   "native_parity": "not established (rapidyaml 0.4.0 is the native parser)"},
    }
    return publish(target, files, provenance, limits)


def publish(target, files, provenance, limits=LIMITS, roots=ROOTS, profile=PROFILE, ruby=RUBY):
    """Catalog verified files into a new private directory. Returns (target, manifest, hashes).
    The CLI calls this only with the fixed roots/profile; tests pass small fixtures."""
    target = trusted_target(target)
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
        writer = RecordFile(out_fd, OUTPUT_RECORDS, created, limits["max_record_file_bytes"])
        graph = catalog(files, writer.write, roots, profile, limits, ruby)
        closing, writer = writer, None
        records = closing.close()
        _verify_published(out_fd, OUTPUT_RECORDS, records["bytes"], records["sha256"],
                          created[OUTPUT_RECORDS])
        records["readback"] = "verified size, SHA-256, private mode and identity"
        manifest = build_manifest(graph, provenance, records)
        data = render(manifest)
        _write_new(out_fd, OUTPUT_MANIFEST, data, created)
        _verify_published(out_fd, OUTPUT_MANIFEST, len(data), sha256(data),
                          created[OUTPUT_MANIFEST])
        hashes = {"manifest_sha256": sha256(data), "manifest_bytes": len(data),
                  "records_sha256": records["sha256"], "records_bytes": records["bytes"]}
        if manifest["status"] == "complete":
            complete = render({
                "generator_version": VERSION, "status": manifest["status"],
                "manifest": OUTPUT_MANIFEST, "manifest_sha256": sha256(data),
                "records_file": OUTPUT_RECORDS, "records_sha256": records["sha256"],
                "relationship": "the manifest binds the records file size/hash; this record "
                                "binds the manifest; written last",
            })
            hashes["complete_sha256"] = sha256(complete)
            _write_new(out_fd, OUTPUT_COMPLETE, complete, created)
            _verify_published(out_fd, OUTPUT_COMPLETE, len(complete), hashes["complete_sha256"],
                              created[OUTPUT_COMPLETE])
        if sorted(os.listdir(out_fd)) != sorted(created):
            raise OutputError("output directory holds files this run did not write")
        closing_fd, out_fd = out_fd, None
        os.close(closing_fd)  # part of publication: a close error must fail before success
    except Exception as exc:
        note = "; partial output remains (not complete); inspect it before deleting or retrying"
        if writer is not None:
            try:
                writer.handle.close()
            except Exception:
                pass
        if OUTPUT_COMPLETE in created:
            cleanup_fd, reopened = out_fd, False
            try:
                if cleanup_fd is None:
                    cleanup_fd = os.open(target, DIR_FLAGS)  # only the directory we reserved
                    reopened = True
                    current = os.fstat(cleanup_fd)
                    if (current.st_dev, current.st_ino) != identity:
                        raise OutputError("reserved output directory was replaced")
                marker = os.stat(OUTPUT_COMPLETE, dir_fd=cleanup_fd, follow_symlinks=False)
                if not stat.S_ISREG(marker.st_mode) or \
                        (marker.st_dev, marker.st_ino) != created[OUTPUT_COMPLETE]:
                    raise OutputError("completion was replaced; foreign file preserved")
                os.unlink(OUTPUT_COMPLETE, dir_fd=cleanup_fd)
            except FileNotFoundError:
                pass
            except Exception as cleanup:
                note = (f"; could not remove {OUTPUT_COMPLETE} ({cleanup}); treat this output "
                        "as failed and incomplete despite the record")
            finally:
                if reopened:
                    try:
                        os.close(cleanup_fd)
                    except Exception:
                        pass
        prefix = "" if isinstance(exc, InventoryError) else "unexpected: "
        raise OutputError(f"{prefix}{exc}{note}") from None
    finally:
        if out_fd is not None:
            try:
                os.close(out_fd)
            except Exception:
                pass
    return target, manifest, hashes


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("snapshot", type=Path, help="canonical T06.001 snapshot (read-only)")
    parser.add_argument("output", type=Path, help="new private output directory")
    args = parser.parse_args(argv)
    try:
        target, manifest, hashes = run(args.snapshot, args.output)
    except (InventoryError, OSError) as exc:
        category = getattr(exc, "category", "os_error")
        print(f"error [{category}]: {exc}", file=sys.stderr)
        return 2
    print(json.dumps({"output": str(target), "status": manifest["status"],
                      "counts": manifest["counts"], "databases": manifest["databases"],
                      **hashes}, sort_keys=True))
    return 0 if manifest["status"] == "complete" else 1


if __name__ == "__main__":
    sys.exit(main())
