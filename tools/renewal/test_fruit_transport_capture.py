#!/usr/bin/env python3
"""Authored controls for fruit_transport_capture (T07.007.011.004).

Only the adjacent owned module, the standard library and authored opaque fakes
run here: no sockets, HTTP, parser, native or acquired source. The single
private evidence file goes under the mandatory RO_FRUIT_TEST_ROOT, which must be
a fresh 0700 directory below .tools/renewal/t07-007-011-004-candidate-1.

Run: RO_FRUIT_TEST_ROOT=<abs dir> /usr/bin/python3 -I -B tools/renewal/test_fruit_transport_capture.py -v
"""

import ast
import copy
import gc
import importlib.util
import json
import math
import os
import stat
import sys
import time
import unittest
import weakref

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(os.path.dirname(HERE))
MODULE_PATH = os.path.join(HERE, "fruit_transport_capture.py")
CANDIDATE_BASE = os.path.join(REPO, ".tools", "renewal", "t07-007-011-004-candidate-1")
LIMIT = 1048576

_spec = importlib.util.spec_from_file_location("fruit_transport_capture", MODULE_PATH)
ftc = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ftc)

KINDS = ["listener_ready", "accept", "accept_error", "request", "native",
         "handler_error", "log_error", "close"]
VIOLATIONS = []


def fixture_root():
    """Return the validated private root or exit; it is mandatory."""
    root = os.environ.get("RO_FRUIT_TEST_ROOT")
    problems = []
    if not root or not os.path.isabs(root):
        problems.append("RO_FRUIT_TEST_ROOT must be an absolute path")
    else:
        info = os.lstat(root) if os.path.lexists(root) else None
        if info is None or not stat.S_ISDIR(info.st_mode):
            problems.append("root is not a real directory")
        elif stat.S_IMODE(info.st_mode) != 0o700 or info.st_uid != os.getuid():
            problems.append("root must be owned 0700")
        base = os.path.realpath(CANDIDATE_BASE) + os.sep
        if not os.path.realpath(root).startswith(base):
            problems.append("root must be below " + CANDIDATE_BASE)
    if problems:
        sys.stderr.write("refusing to run: %s\n" % "; ".join(problems))
        sys.exit(2)
    return root


def strict(result):
    return json.dumps(result, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def _forbidden(name):
    def method(self, *args, **kwargs):
        VIOLATIONS.append(name)
        raise TypeError("opaque fake forbids " + name)
    return method


class OpaqueSocket(object):
    """Accepted-socket stand-in: any inspection is logged and raises."""

    __slots__ = ("_fd", "__weakref__")

    def __init__(self, fd):
        object.__setattr__(self, "_fd", fd)

    def __getattribute__(self, name):
        VIOLATIONS.append("getattr:" + name)
        raise AttributeError(name)

    def fileno(self):  # reachable only through __getattribute__
        return self._fd

    def close(self):
        VIOLATIONS.append("close")


for _name in ("__setattr__", "__delattr__", "__eq__", "__ne__", "__lt__", "__le__",
              "__gt__", "__ge__", "__hash__", "__repr__", "__str__", "__format__",
              "__bool__", "__len__", "__index__", "__int__", "__float__", "__iter__",
              "__contains__", "__fspath__", "__reduce__", "__reduce_ex__",
              "__copy__", "__deepcopy__", "__dir__", "__sizeof__", "__getstate__"):
    setattr(OpaqueSocket, _name, _forbidden(_name))


class UnhashableSocket(object):
    __hash__ = None
    __eq__ = _forbidden("__eq__")
    __repr__ = _forbidden("__repr__")


def drive(capture, events):
    """Record (kind, connection, fields) tuples; return the bool results."""
    return [capture.record(kind, conn, **fields) for kind, conn, fields in events]


def shape(result):
    """Rows without genuine elapsed times, for literal comparison."""
    return [(r["sequence"], r["kind"], r["connection_id"], r["fields"]) for r in result["rows"]]


class ModuleShape(unittest.TestCase):
    def test_import_is_actionless_stdlib_only(self):
        with open(MODULE_PATH, "r", encoding="utf-8") as handle:
            tree = ast.parse(handle.read())
        imports = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom):
                imports.add(node.module)
        self.assertEqual(imports, {"copy", "json", "time"})
        banned = {"open", "print", "exec", "eval", "compile", "__import__", "socket", "os",
                  "sys", "subprocess", "threading", "fileno", "close", "shutdown", "repr",
                  "hash", "getattr", "setattr", "hasattr", "vars", "isinstance", "callback"}
        names = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}
        attrs = {n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)}
        self.assertEqual((names | attrs) & banned, set())
        for node in tree.body:
            self.assertIsInstance(node, (ast.Expr, ast.Import, ast.Assign, ast.FunctionDef,
                                         ast.ClassDef))
            if isinstance(node, ast.Expr):
                self.assertIsInstance(node.value, ast.Constant)
        self.assertEqual(ftc.MAX_ROWS, 8192)
        self.assertEqual(ftc.MAX_RESULT_BYTES, LIMIT)

    def test_empty_capture_is_incomplete_and_strict(self):
        result = ftc.TransportCapture().finish()
        self.assertEqual(result, {
            "schema": "root011-fruit-transport-capture-1",
            "limits": {"rows": 8192, "serialized_result_bytes": 1048576},
            "complete": False, "first_fault": None,
            "counts": {"attempted": 0, "retained": 0, "rejected": 0, "accepted": 0,
                       "closed_confirmed": 0, "closed_unconfirmed": 0, "active_at_finish": 0,
                       "by_kind": dict.fromkeys(KINDS, 0)},
            "rows": []})
        self.assertEqual(json.loads(strict(result)), result)


class EventAccounting(unittest.TestCase):
    def setUp(self):
        del VIOLATIONS[:]

    def tearDown(self):
        self.assertEqual(VIOLATIONS, [])

    def test_all_eight_kinds_exact_result(self):
        cap = ftc.TransportCapture()
        a, b = OpaqueSocket(5), UnhashableSocket()
        caller_fields = {"method": "GET", "path": "/native/data/地圖.gat?x=1"}
        results = drive(cap, [
            ("native", None, {"row_index": 0, "wire": "/api/health"}),
            ("native", None, {"row_index": 1, "wire": "/api/cache-stats"}),
            ("listener_ready", None, {}),
            ("accept_error", None, {"error_type": "ConnectionAbortedError", "errno": 53}),
            ("accept", a, {}),
            ("request", a, caller_fields),
            ("native", a, {"row_index": 2, "wire": "/data/地圖.gat"}),
            ("log_error", a, {"category": "timeout", "error_type": "timeout", "errno": None}),
            ("handler_error", a, {"error_type": "BrokenPipeError", "errno": 32}),
            ("close", a, {"confirmed": True}),
            ("accept", b, {}),
            ("log_error", None, {"category": "other", "error_type": None, "errno": None}),
            ("close", b, {"confirmed": True}),
        ])
        self.assertEqual(results, [True] * 13)
        self.assertEqual(caller_fields, {"method": "GET", "path": "/native/data/地圖.gat?x=1"})
        result = cap.finish()
        self.assertEqual(shape(result), [
            (1, "native", None, {"row_index": 0, "wire": "/api/health"}),
            (2, "native", None, {"row_index": 1, "wire": "/api/cache-stats"}),
            (3, "listener_ready", None, {}),
            (4, "accept_error", None, {"error_type": "ConnectionAbortedError", "errno": 53}),
            (5, "accept", 1, {}),
            (6, "request", 1, {"method": "GET", "path": "/native/data/地圖.gat?x=1"}),
            (7, "native", 1, {"row_index": 2, "wire": "/data/地圖.gat"}),
            (8, "log_error", 1, {"category": "timeout", "error_type": "timeout", "errno": None}),
            (9, "handler_error", 1, {"error_type": "BrokenPipeError", "errno": 32}),
            (10, "close", 1, {"confirmed": True}),
            (11, "accept", 2, {}),
            (12, "log_error", None, {"category": "other", "error_type": None, "errno": None}),
            (13, "close", 2, {"confirmed": True}),
        ])
        for row in result["rows"]:
            self.assertEqual(sorted(row), ["connection_id", "elapsed_ns", "fields", "kind", "sequence"])
        self.assertTrue(result["complete"])
        self.assertIsNone(result["first_fault"])
        self.assertEqual(result["counts"], {
            "attempted": 13, "retained": 13, "rejected": 0, "accepted": 2,
            "closed_confirmed": 2, "closed_unconfirmed": 0, "active_at_finish": 0,
            "by_kind": {"listener_ready": 1, "accept": 2, "accept_error": 1, "request": 1,
                        "native": 3, "handler_error": 1, "log_error": 2, "close": 2}})
        text = strict(result)
        self.assertEqual(json.loads(text), result)
        self.assertTrue(text.isascii())

    def test_duplicate_active_accept_and_unhashable_identity(self):
        cap = ftc.TransportCapture()
        a, b = UnhashableSocket(), UnhashableSocket()
        self.assertTrue(cap.record("accept", a))
        self.assertFalse(cap.record("accept", a))
        self.assertTrue(cap.record("accept", b))
        self.assertTrue(cap.record("close", b, confirmed=True))
        self.assertTrue(cap.record("close", a, confirmed=True))
        result = cap.finish()
        self.assertEqual(shape(result), [(1, "accept", 1, {}), (3, "accept", 2, {}),
                                         (4, "close", 2, {"confirmed": True}),
                                         (5, "close", 1, {"confirmed": True})])
        self.assertEqual(result["first_fault"], {"code": "connection_already_active", "attempt": 2})
        self.assertEqual(result["counts"]["accepted"], 2)

    def test_fake_fd_reuse_gets_new_id_without_reading_fd(self):
        cap = ftc.TransportCapture()
        cap.record("listener_ready")
        first = OpaqueSocket(7)
        self.assertTrue(cap.record("accept", first))
        self.assertTrue(cap.record("close", first, confirmed=True))
        second = OpaqueSocket(7)
        self.assertTrue(cap.record("accept", second))
        self.assertFalse(cap.record("close", first, confirmed=True))  # retired object
        self.assertTrue(cap.record("close", second, confirmed=True))
        self.assertFalse(cap.record("accept", 7))  # a descriptor number is not a socket
        result = cap.finish()
        self.assertEqual([r["connection_id"] for r in result["rows"] if r["kind"] == "accept"], [1, 2])
        self.assertEqual(result["first_fault"], {"code": "connection_unknown", "attempt": 5})

    def test_recycled_python_id_gets_new_id(self):
        cap = ftc.TransportCapture()
        old = OpaqueSocket(9)
        old_id = id(old)
        cap.record("accept", old)
        cap.record("close", old, confirmed=True)
        del old
        gc.collect()
        fresh = None
        keep = []
        for _ in range(1000):
            candidate = OpaqueSocket(9)
            if id(candidate) == old_id:
                fresh = candidate
                break
            keep.append(candidate)
        if fresh is None:
            self.skipTest("CPython did not recycle the retired id within 1000 objects")
        self.assertFalse(cap.record("close", fresh, confirmed=True))
        self.assertTrue(cap.record("accept", fresh))
        self.assertTrue(cap.record("close", fresh, confirmed=True))
        ids = [r["connection_id"] for r in cap.finish()["rows"] if r["kind"] == "accept"]
        self.assertEqual(ids, [1, 2])

    def test_accept_error_allocates_no_connection(self):
        cap = ftc.TransportCapture()
        cap.record("listener_ready")
        self.assertTrue(cap.record("accept_error", error_type="OSError", errno=None))
        self.assertFalse(cap.record("accept_error", OpaqueSocket(3), error_type="OSError", errno=24))
        a = OpaqueSocket(3)
        cap.record("accept", a)
        cap.record("close", a, confirmed=True)
        result = cap.finish()
        self.assertEqual(shape(result)[1], (2, "accept_error", None, {"error_type": "OSError", "errno": None}))
        self.assertEqual(shape(result)[2][2], 1)
        self.assertEqual(result["counts"]["accepted"], 1)
        self.assertEqual(result["first_fault"], {"code": "connection_not_allowed", "attempt": 3})

    def test_unknown_and_duplicate_rejections_leave_state(self):
        cap = ftc.TransportCapture()
        a, stranger = OpaqueSocket(4), OpaqueSocket(4)
        outcomes = drive(cap, [
            ("listener_ready", None, {}),
            ("request", stranger, {"method": "GET", "path": "/x"}),     # 2 unknown
            ("close", stranger, {"confirmed": True}),                   # 3 unknown
            ("native", stranger, {"row_index": 0, "wire": "/data/x"}),  # 4 unknown
            ("handler_error", stranger, {"error_type": "E", "errno": None}),  # 5
            ("accept", a, {}),
            ("request", a, {"method": "GET", "path": "/a"}),
            ("request", a, {"method": "POST", "path": "/b"}),           # 8 duplicate
            ("native", a, {"row_index": 3, "wire": "/data/a"}),
            ("native", None, {"row_index": 3, "wire": "/api/health"}),  # 10 duplicate index
            ("native", a, {"row_index": 4, "wire": "/data/b"}),         # 11 second native
            ("listener_ready", None, {}),                               # 12 duplicate
            ("close", a, {"confirmed": True}),
            ("close", a, {"confirmed": True}),                          # 14 retired
            ("request", a, {"method": "GET", "path": "/a"}),            # 15 retired
        ])
        self.assertEqual(outcomes, [True, False, False, False, False, True, True, False, True,
                                    False, False, False, True, False, False])
        result = cap.finish()
        self.assertEqual(result["first_fault"], {"code": "connection_unknown", "attempt": 2})
        self.assertEqual([r["sequence"] for r in result["rows"]], [1, 6, 7, 9, 13])
        self.assertEqual(result["rows"][2]["fields"], {"method": "GET", "path": "/a"})
        self.assertEqual(result["counts"]["attempted"], 15)
        self.assertEqual(result["counts"]["rejected"], 10)
        self.assertEqual(result["counts"]["by_kind"]["request"], 1)
        self.assertEqual(result["counts"]["by_kind"]["native"], 1)
        self.assertEqual(result["counts"]["closed_confirmed"], 1)
        self.assertFalse(result["complete"])

    def test_accepted_then_closed_without_request_is_complete(self):
        cap = ftc.TransportCapture()
        a = OpaqueSocket(6)
        drive(cap, [("listener_ready", None, {}), ("accept", a, {}),
                    ("close", a, {"confirmed": True})])
        result = cap.finish()
        self.assertTrue(result["complete"])
        self.assertEqual(result["counts"]["by_kind"]["request"], 0)
        self.assertEqual(shape(result)[2], (3, "close", 1, {"confirmed": True}))
        self.assertNotIn("path", strict(result))

    def test_unconfirmed_and_missing_close_are_incomplete(self):
        cap = ftc.TransportCapture()
        a, b, c = OpaqueSocket(1), OpaqueSocket(2), OpaqueSocket(3)
        drive(cap, [("listener_ready", None, {}), ("accept", a, {}), ("accept", b, {}),
                    ("accept", c, {}), ("close", a, {"confirmed": False}),
                    ("close", b, {"confirmed": True})])
        self.assertFalse(cap.record("close", a, confirmed=True))
        result = cap.finish()
        self.assertFalse(result["complete"])
        self.assertEqual(result["first_fault"], {"code": "connection_unknown", "attempt": 7})
        counts = result["counts"]
        self.assertEqual((counts["accepted"], counts["closed_confirmed"], counts["closed_unconfirmed"],
                          counts["active_at_finish"]), (3, 1, 1, 1))
        # Without any fault, only the missing close / false close decide incompleteness.
        for confirmed, closes in ((False, True), (True, False)):
            cap = ftc.TransportCapture()
            a = OpaqueSocket(1)
            cap.record("listener_ready")
            cap.record("accept", a)
            if closes:
                cap.record("close", a, confirmed=confirmed)
            result = cap.finish()
            self.assertIsNone(result["first_fault"])
            self.assertFalse(result["complete"])
        # A successful close never asked the fake to close (tearDown checks VIOLATIONS).

    def test_native_association_rules(self):
        cap = ftc.TransportCapture()
        get, post, early = OpaqueSocket(1), OpaqueSocket(2), OpaqueSocket(3)
        outcomes = drive(cap, [
            ("listener_ready", None, {}),
            ("accept", early, {}),
            ("native", early, {"row_index": 10, "wire": "/data/a"}),       # 3 before GET
            ("accept", post, {}),
            ("request", post, {"method": "POST", "path": "/_viewer/report"}),
            ("native", post, {"row_index": 11, "wire": "/data/b"}),        # 6 POST
            ("accept", get, {}),
            ("request", get, {"method": "GET", "path": "/native/data/c"}),
            ("native", get, {"row_index": 12, "wire": "/api/health"}),     # 9 direct wire
            ("native", get, {"row_index": 12, "wire": "/api/cache-stats"}),  # 10 direct wire
            ("native", get, {"row_index": 12, "wire": "/data/c"}),
            ("native", None, {"row_index": 13, "wire": "/api/health"}),
            ("native", None, {"row_index": 14, "wire": "/api/cache-stats"}),
            ("close", early, {"confirmed": True}),
            ("close", post, {"confirmed": True}),
            ("close", get, {"confirmed": True}),
        ])
        self.assertEqual(outcomes, [True, True, False, True, True, False, True, True, False,
                                    False, True, True, True, True, True, True])
        result = cap.finish()
        natives = [(r["connection_id"], r["fields"]["row_index"]) for r in result["rows"]
                   if r["kind"] == "native"]
        self.assertEqual(natives, [(3, 12), (None, 13), (None, 14)])
        self.assertEqual(result["first_fault"], {"code": "native_without_get", "attempt": 3})
        self.assertEqual(result["counts"]["by_kind"]["native"], 3)

    def test_error_events_need_no_handler_attributes(self):
        cap = ftc.TransportCapture()
        a = OpaqueSocket(8)
        outcomes = drive(cap, [
            ("listener_ready", None, {}),
            ("accept", a, {}),
            ("handler_error", a, {"error_type": "RuntimeError", "errno": None}),
            ("log_error", a, {"category": "http_error", "error_type": None, "errno": None}),
            ("log_error", a, {"category": "timeout", "error_type": "TimeoutError", "errno": 60}),
            ("handler_error", None, {"error_type": "ValueError", "errno": -1}),
            ("close", a, {"confirmed": True}),
        ])
        self.assertEqual(outcomes, [True] * 7)
        result = cap.finish()
        self.assertTrue(result["complete"])
        self.assertEqual(result["counts"]["by_kind"]["request"], 0)
        for row in result["rows"]:
            self.assertFalse({"path", "command", "request_version"} & set(row["fields"]))

    def test_invalid_fields_and_connections_reject_without_state(self):
        long_type = "香" * 43  # 129 UTF-8 bytes
        cases = [
            ("unknown_kind", ("connect", None, {})),
            ("unknown_kind", (b"accept", None, {})),
            ("connection_required", ("accept", None, {})),
            ("connection_required", ("close", None, {"confirmed": True})),
            ("connection_primitive", ("accept", 12, {})),
            ("connection_primitive", ("accept", True, {})),
            ("connection_primitive", ("accept", "sock", {})),
            ("connection_primitive", ("accept", b"sock", {})),
            ("connection_primitive", ("accept", 1.5, {})),
            ("connection_not_allowed", ("listener_ready", OpaqueSocket(1), {})),
            ("fields_mismatch", ("listener_ready", None, {"extra": 1})),
            ("fields_mismatch", ("accept_error", None, {"error_type": "OSError"})),
            ("fields_mismatch", ("accept_error", None, {"error_type": "E", "errno": 1, "args": "x"})),
            ("error_type_invalid", ("accept_error", None, {"error_type": "", "errno": None})),
            ("error_type_invalid", ("accept_error", None, {"error_type": long_type, "errno": None})),
            ("error_type_invalid", ("handler_error", None, {"error_type": ["E"], "errno": None})),
            ("error_type_invalid", ("handler_error", None, {"error_type": "\ud800", "errno": None})),
            ("errno_invalid", ("accept_error", None, {"error_type": "E", "errno": True})),
            ("errno_invalid", ("accept_error", None, {"error_type": "E", "errno": 1.0})),
            ("errno_invalid", ("accept_error", None, {"error_type": "E", "errno": math.nan})),
            ("errno_invalid", ("accept_error", None, {"error_type": "E", "errno": math.inf})),
            ("errno_invalid", ("log_error", None, {"category": "other", "error_type": None, "errno": "5"})),
            ("category_invalid", ("log_error", None, {"category": "bogus", "error_type": None, "errno": None})),
            ("category_invalid", ("log_error", None, {"category": None, "error_type": None, "errno": None})),
            ("error_type_invalid", ("log_error", None, {"category": "other", "error_type": 3, "errno": None})),
            ("row_index_invalid", ("native", None, {"row_index": 1024, "wire": "/api/health"})),
            ("row_index_invalid", ("native", None, {"row_index": -1, "wire": "/api/health"})),
            ("row_index_invalid", ("native", None, {"row_index": False, "wire": "/api/health"})),
            ("row_index_invalid", ("native", None, {"row_index": 1.0, "wire": "/api/health"})),
            ("wire_invalid", ("native", None, {"row_index": 0, "wire": b"/api/health"})),
            ("wire_length_invalid", ("native", None, {"row_index": 0, "wire": ""})),
            ("wire_length_invalid", ("native", None, {"row_index": 0, "wire": "w" * 8193})),
            ("fields_mismatch", ("native", None, {"row_index": 0})),
        ]
        for code, (kind, conn, fields) in cases:
            with self.subTest(code=code, kind=kind, fields=sorted(fields)):
                cap = ftc.TransportCapture()
                self.assertFalse(cap.record(kind, conn, **fields))
                result = cap.finish()
                self.assertEqual(result["first_fault"], {"code": code, "attempt": 1})
                self.assertEqual(result["rows"], [])
                self.assertEqual((result["counts"]["attempted"], result["counts"]["rejected"]), (1, 1))

        request_cases = [
            ("method_invalid", {"method": "HEAD", "path": "/x"}),
            ("method_invalid", {"method": b"GET", "path": "/x"}),
            ("path_invalid", {"method": "GET", "path": None}),
            ("path_length_invalid", {"method": "GET", "path": ""}),
            ("path_length_invalid", {"method": "GET", "path": "香" * 2731}),  # 8193 bytes
            ("path_length_invalid", {"method": "GET", "path": "/\udc80"}),
            ("fields_mismatch", {"method": "GET", "path": "/x", "headers": "h"}),
            ("fields_mismatch", {"path": "/x"}),
        ]
        for code, fields in request_cases:
            with self.subTest(code=code, fields=sorted(fields)):
                cap = ftc.TransportCapture()
                a = OpaqueSocket(1)
                cap.record("accept", a)
                self.assertFalse(cap.record("request", a, **fields))
                # The connection is still un-requested: a valid request now succeeds.
                self.assertTrue(cap.record("request", a, method="GET", path="/ok"))
                self.assertFalse(cap.record("close", a, confirmed=1))
                self.assertTrue(cap.record("close", a, confirmed=True))
                result = cap.finish()
                self.assertEqual(result["first_fault"], {"code": code, "attempt": 2})
                self.assertEqual(result["counts"]["by_kind"]["request"], 1)
        # Exact boundaries accept.
        cap = ftc.TransportCapture()
        a = OpaqueSocket(1)
        cap.record("listener_ready")
        cap.record("accept", a)
        boundary = "香" * 2730 + "/a"  # 8192 bytes
        self.assertTrue(cap.record("request", a, method="GET", path=boundary))
        self.assertTrue(cap.record("native", a, row_index=1023, wire="w" * 8192))
        self.assertTrue(cap.record("handler_error", a, error_type="香" * 42 + "xx", errno=2 ** 80))
        self.assertTrue(cap.record("close", a, confirmed=False))
        result = cap.finish()
        self.assertIsNone(result["first_fault"])
        self.assertEqual(result["rows"][2]["fields"]["path"], boundary)

    def test_sticky_fault_then_valid_close(self):
        cap = ftc.TransportCapture()
        a = OpaqueSocket(1)
        cap.record("listener_ready")
        cap.record("accept", a)
        self.assertFalse(cap.record("request", a, method="PUT", path="/"))
        self.assertFalse(cap.record("bogus"))
        self.assertTrue(cap.record("close", a, confirmed=True))
        result = cap.finish()
        self.assertEqual(result["first_fault"], {"code": "method_invalid", "attempt": 3})
        self.assertFalse(result["complete"])
        self.assertEqual(result["counts"]["active_at_finish"], 0)
        self.assertEqual(result["counts"]["rejected"], 2)


class ContractRegressions(unittest.TestCase):
    def test_exact_errno_above_and_below_signed64(self):
        for kind in ("accept_error", "handler_error", "log_error"):
            for value in (2 ** 64, 2 ** 80, -(2 ** 80)):
                with self.subTest(kind=kind, value=value):
                    cap = ftc.TransportCapture()
                    self.assertTrue(cap.record("listener_ready"))
                    fields = {"error_type": "E", "errno": value}
                    if kind == "log_error":
                        fields["category"] = "other"
                    self.assertTrue(cap.record(kind, **fields))
                    result = cap.finish()
                    self.assertTrue(result["complete"])
                    self.assertEqual(result["rows"][1]["fields"], fields)
                    self.assertEqual(json.loads(strict(result)), result)

    def test_equal_buffers_and_containers_are_opaque_identity_tokens(self):
        cap = ftc.TransportCapture()
        tokens = [bytearray(b"a"), bytearray(b"a"),
                  memoryview(bytearray(b"a")), memoryview(bytearray(b"a")),
                  [1], [1], {"a": 1}, {"a": 1}]
        self.assertTrue(cap.record("listener_ready"))
        for token in tokens:
            self.assertTrue(cap.record("accept", token))
        for token in reversed(tokens):
            self.assertTrue(cap.record("close", token, confirmed=True))
        result = cap.finish()
        self.assertTrue(result["complete"])
        self.assertEqual(result["counts"]["accepted"], 8)
        self.assertEqual([r["connection_id"] for r in result["rows"] if r["kind"] == "accept"], list(range(1, 9)))
        self.assertEqual([r["connection_id"] for r in result["rows"] if r["kind"] == "close"], list(range(8, 0, -1)))

    def test_subclass_keyword_names_reject_before_state_change(self):
        class Name(str):
            pass
        for changed in (("method",), ("path",), ("method", "path")):
            with self.subTest(changed=changed):
                cap = ftc.TransportCapture()
                token = OpaqueSocket(1)
                self.assertTrue(cap.record("listener_ready"))
                self.assertTrue(cap.record("accept", token))
                fields = {(Name(k) if k in changed else k): v
                          for k, v in {"method": "GET", "path": "/invalid"}.items()}
                self.assertFalse(cap.record("request", token, **fields))
                self.assertTrue(cap.record("request", token, method="GET", path="/valid"))
                self.assertTrue(cap.record("close", token, confirmed=True))
                result = cap.finish()
                self.assertFalse(result["complete"])
                self.assertEqual(result["first_fault"]["attempt"], 3)
                self.assertEqual([r["sequence"] for r in result["rows"]], [1, 2, 4, 5])
                self.assertEqual(result["counts"]["rejected"], 1)
                self.assertEqual(result["rows"][2]["fields"]["path"], "/valid")


class Limits(unittest.TestCase):
    def setUp(self):
        del VIOLATIONS[:]

    def tearDown(self):
        self.assertEqual(VIOLATIONS, [])

    def test_row_cap_is_sticky_and_bounded(self):
        cap = ftc.TransportCapture()
        self.assertTrue(cap.record("listener_ready"))
        retained = 1
        socks = []
        while retained < 8192:
            s = OpaqueSocket(retained)
            self.assertTrue(cap.record("accept", s))
            socks.append(s)
            retained += 1
        self.assertEqual(len(socks), 8191)
        self.assertFalse(cap.record("close", socks[0], confirmed=True))  # 8193rd attempt
        self.assertFalse(cap.record("listener_ready"))
        result = cap.finish()
        counts = result["counts"]
        self.assertEqual((counts["attempted"], counts["retained"], counts["rejected"]), (8194, 8192, 2))
        self.assertEqual(result["first_fault"], {"code": "row_cap", "attempt": 8193})
        self.assertEqual(counts["active_at_finish"], 8191)
        self.assertEqual(counts["closed_confirmed"], 0)
        self.assertFalse(result["complete"])
        size = len(strict(result).encode("ascii"))
        self.assertLess(size, LIMIT)  # the row cap, not the byte cap, was reached

    def test_full_result_byte_cap_with_multibyte_paths(self):
        cap = ftc.TransportCapture()
        cap.record("listener_ready")
        path = "/native/data/" + "香" * 2725  # 8188 UTF-8 bytes, 16363 JSON bytes
        events = 1
        refused_at = None
        for index in range(200):
            last = OpaqueSocket(index)
            if not cap.record("accept", last):
                refused_at = ("accept", events + 1)
                break
            events += 1
            if not cap.record("request", last, method="GET", path=path):
                refused_at = ("request", events + 1)
                break
            events += 1
        self.assertIsNotNone(refused_at, "premise: byte cap was reached")
        self.assertFalse(cap.record("close", last, confirmed=True))  # sticky after cap
        result = cap.finish()
        text = strict(result).encode("ascii")
        self.assertLessEqual(len(text), LIMIT)
        self.assertGreater(len(text), LIMIT - 2 * 16500)  # genuinely near the cap
        self.assertEqual(result["first_fault"], {"code": "byte_cap", "attempt": refused_at[1]})
        counts = result["counts"]
        self.assertEqual(counts["retained"], events)
        self.assertEqual(counts["attempted"], events + 2)
        self.assertLess(counts["retained"], 8192)
        self.assertGreater(counts["by_kind"]["request"] * 16363, LIMIT - 70000)
        for row in result["rows"]:
            if row["kind"] == "request":
                self.assertEqual(row["fields"]["path"], path)  # never truncated
        evidence = os.path.join(fixture_root(), "byte-cap-result.json")
        fd = os.open(evidence, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "wb") as handle:
            handle.write(text)
        self.assertEqual(os.stat(evidence).st_size, len(text))
        self.assertEqual(stat.S_IMODE(os.stat(evidence).st_mode), 0o600)

    def test_envelope_reserve_covers_worst_case(self):
        # Independent check: a maximal fault/counter envelope fits the reserve.
        big = 10 ** 19
        envelope = {"schema": "root011-fruit-transport-capture-1",
                    "limits": {"rows": 8192, "serialized_result_bytes": 1048576},
                    "complete": False, "first_fault": {"code": "c" * 64, "attempt": big},
                    "counts": {k: big for k in ("attempted", "retained", "rejected", "accepted",
                                                "closed_confirmed", "closed_unconfirmed",
                                                "active_at_finish")},
                    "rows": []}
        envelope["counts"]["by_kind"] = {k: big for k in KINDS}
        self.assertLessEqual(len(strict(envelope)), ftc.ENVELOPE_RESERVE)


class SealingAndTime(unittest.TestCase):
    def setUp(self):
        del VIOLATIONS[:]

    def tearDown(self):
        self.assertEqual(VIOLATIONS, [])

    def test_finish_twice_independent_and_post_finish_rejects(self):
        cap = ftc.TransportCapture()
        a = OpaqueSocket(1)
        drive(cap, [("listener_ready", None, {}), ("accept", a, {}),
                    ("request", a, {"method": "GET", "path": "/p"}),
                    ("close", a, {"confirmed": True})])
        first = cap.finish()
        pristine = copy.deepcopy(first)
        first["rows"][2]["fields"]["path"] = "/mutated"
        first["rows"].append({"x": 1})
        first["counts"]["by_kind"]["accept"] = 99
        first["complete"] = False
        second = cap.finish()
        self.assertEqual(second, pristine)
        self.assertIsNot(second["rows"], first["rows"])
        b = OpaqueSocket(2)
        self.assertFalse(cap.record("accept", b))
        self.assertFalse(cap.record("listener_ready"))
        third = cap.finish()
        self.assertEqual(third, pristine)
        self.assertEqual(third["counts"]["attempted"], 4)

    def test_finish_releases_active_references(self):
        cap = ftc.TransportCapture()
        a = OpaqueSocket(1)
        ref = weakref.ref(a)
        cap.record("listener_ready")
        cap.record("accept", a)
        del a
        gc.collect()
        self.assertIsNotNone(ref())  # held while active
        result = cap.finish()
        gc.collect()
        self.assertIsNone(ref())
        self.assertEqual(result["counts"]["active_at_finish"], 1)
        self.assertFalse(result["complete"])
        self.assertNotIn("OpaqueSocket", strict(result))

    def test_close_releases_reference(self):
        cap = ftc.TransportCapture()
        a = OpaqueSocket(1)
        ref = weakref.ref(a)
        cap.record("accept", a)
        cap.record("close", a, confirmed=True)
        del a
        gc.collect()
        self.assertIsNone(ref())

    def test_monotonic_elapsed_and_sequence_gaps(self):
        before = time.monotonic_ns()
        cap = ftc.TransportCapture()
        a = OpaqueSocket(1)
        cap.record("listener_ready")
        cap.record("nope")
        cap.record("accept", a)
        time.sleep(0.002)
        cap.record("close", None, confirmed=True)
        cap.record("close", a, confirmed=True)
        after = time.monotonic_ns()
        result = cap.finish()
        seqs = [r["sequence"] for r in result["rows"]]
        self.assertEqual(seqs, [1, 3, 5])
        self.assertEqual(result["counts"]["attempted"] - result["counts"]["retained"], 2)
        elapsed = [r["elapsed_ns"] for r in result["rows"]]
        for value in elapsed:
            self.assertIs(type(value), int)
            self.assertGreaterEqual(value, 0)
            self.assertLessEqual(value, after - before)
        self.assertEqual(elapsed, sorted(elapsed))
        self.assertGreaterEqual(elapsed[2] - elapsed[1], 2000000)

    def test_record_rejects_caller_supplied_timing(self):
        cap = ftc.TransportCapture()
        self.assertFalse(cap.record("listener_ready", elapsed_ns=0))
        self.assertFalse(cap.record("listener_ready", sequence=1))
        self.assertEqual(cap.finish()["first_fault"]["code"], "fields_mismatch")


if __name__ == "__main__":
    fixture_root()
    unittest.main()
