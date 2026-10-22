#!/usr/bin/env python3
"""T07.007.011.004 bounded in-memory fruit transport capture.

Standalone observer data module. ``TransportCapture().record(kind, connection,
**fields)`` validates one of eight fixed event kinds and appends one bounded
row; ``finish()`` seals and returns a strict-JSON-ready dict. Nothing here opens
files, touches sockets, starts threads or calls back into the caller.

Connections are opaque objects compared by identity only. The module never
reads their attributes, hashes them, compares them for equality, formats them
or calls fileno/close. Active objects are keyed by ``id()`` while a reference
is held, so a CPython id cannot be recycled until the terminal close (or finish)
releases it; every accept allocates a fresh never-reused connection_id.

Limits are fixed: 8192 rows and 1048576 bytes for the entire finish() result
under ``json.dumps(result, ensure_ascii=True, allow_nan=False,
separators=(',', ':'))``. A cap or invalid observation returns False, latches
first_fault and leaves state unchanged; a cap refuses every later call.

A close with confirmed=False, an accept_error or a handler/log error is an
observation, not proof of physical closure or cause. Integration into the lease
is later ROOT work; no hooks are provided here.
"""

import copy
import json
import time

SCHEMA = "root011-fruit-transport-capture-1"
MAX_ROWS = 8192
MAX_RESULT_BYTES = 1048576
KINDS = (
    "listener_ready",
    "accept",
    "accept_error",
    "request",
    "native",
    "handler_error",
    "log_error",
    "close",
)
DIRECT_WIRES = ("/api/health", "/api/cache-stats")
LOG_CATEGORIES = ("timeout", "http_error", "other")
# Types that can never be an accepted socket object.
_PRIMITIVE_TYPES = (type(None), bool, int, float, complex, str, bytes)
# Upper bound for every envelope counter/attempt rendered as a JSON integer.
_COUNTER_PLACEHOLDER = 10 ** 19
_FAULT_CODE_MAX = 64

# Connection rules per kind: "none", "new" (not active), "required" (active)
# or "optional" (None or active).
_CONNECTION_RULE = {
    "listener_ready": "none",
    "accept": "new",
    "accept_error": "none",
    "request": "required",
    "native": "optional",
    "handler_error": "optional",
    "log_error": "optional",
    "close": "required",
}
_FIELDS = {
    "listener_ready": (),
    "accept": (),
    "accept_error": ("error_type", "errno"),
    "request": ("method", "path"),
    "native": ("row_index", "wire"),
    "handler_error": ("error_type", "errno"),
    "log_error": ("category", "error_type", "errno"),
    "close": ("confirmed",),
}


def _dumps(value):
    return json.dumps(value, ensure_ascii=True, allow_nan=False, separators=(",", ":"))


def _utf8_len(value):
    try:
        return len(value.encode("utf-8"))
    except UnicodeEncodeError:
        return -1


def _bounded_str(value, limit):
    return type(value) is str and 1 <= _utf8_len(value) <= limit


def _exact_int(value, low=None, high=None):
    return (type(value) is int
            and (low is None or low <= value)
            and (high is None or value <= high))


def _check_fields(kind, fields):
    """Return None or a fixed fault code for the kind's primitive fields."""
    if any(type(name) is not str for name in fields):
        return "fields_mismatch"
    if tuple(sorted(fields)) != tuple(sorted(_FIELDS[kind])):
        return "fields_mismatch"
    if kind in ("accept_error", "handler_error"):
        if not _bounded_str(fields["error_type"], 128):
            return "error_type_invalid"
        if fields["errno"] is not None and not _exact_int(fields["errno"]):
            return "errno_invalid"
    elif kind == "log_error":
        if type(fields["category"]) is not str or fields["category"] not in LOG_CATEGORIES:
            return "category_invalid"
        if fields["error_type"] is not None and not _bounded_str(fields["error_type"], 128):
            return "error_type_invalid"
        if fields["errno"] is not None and not _exact_int(fields["errno"]):
            return "errno_invalid"
    elif kind == "request":
        if type(fields["method"]) is not str or fields["method"] not in ("GET", "POST"):
            return "method_invalid"
        if type(fields["path"]) is not str:
            return "path_invalid"
        if not 1 <= _utf8_len(fields["path"]) <= 8192:
            return "path_length_invalid"
    elif kind == "native":
        if not _exact_int(fields["row_index"], 0, 1023):
            return "row_index_invalid"
        if type(fields["wire"]) is not str:
            return "wire_invalid"
        if not 1 <= _utf8_len(fields["wire"]) <= 8192:
            return "wire_length_invalid"
    elif kind == "close":
        if type(fields["confirmed"]) is not bool:
            return "confirmed_invalid"
    return None


def _envelope(rows, complete, first_fault, counts):
    return {
        "schema": SCHEMA,
        "limits": {"rows": MAX_ROWS, "serialized_result_bytes": MAX_RESULT_BYTES},
        "complete": complete,
        "first_fault": first_fault,
        "counts": counts,
        "rows": rows,
    }


def _counts(attempted, retained, by_kind, closed_true, closed_false):
    return {
        "attempted": attempted,
        "retained": retained,
        "rejected": attempted - retained,
        "accepted": by_kind["accept"],
        "closed_confirmed": closed_true,
        "closed_unconfirmed": closed_false,
        "active_at_finish": by_kind["accept"] - closed_true - closed_false,
        "by_kind": dict(by_kind),
    }


def _worst_envelope_bytes():
    big = _COUNTER_PLACEHOLDER
    counts = _counts(big, big, dict.fromkeys(KINDS, big), big, big)
    counts.update(rejected=big, active_at_finish=big)
    fault = {"code": "x" * _FAULT_CODE_MAX, "attempt": big}
    return len(_dumps(_envelope([], False, fault, counts)))


# Worst-case bytes for everything except row text, reserved before any row.
ENVELOPE_RESERVE = _worst_envelope_bytes()


class _Active(object):
    __slots__ = ("connection", "connection_id", "method", "native_seen")

    def __init__(self, connection, connection_id):
        self.connection = connection
        self.connection_id = connection_id
        self.method = None
        self.native_seen = False


class TransportCapture(object):
    """One bounded in-memory event list; see the module docstring."""

    def __init__(self):
        self._origin_ns = time.monotonic_ns()
        self._rows = []
        self._row_bytes = 0
        self._attempted = 0
        self._first_fault = None
        self._capped = False
        self._sealed = None
        self._active = {}
        self._next_id = 1
        self._native_rows = set()
        self._by_kind = dict.fromkeys(KINDS, 0)
        self._closed_true = 0
        self._closed_false = 0

    def _reject(self, code):
        if self._first_fault is None:
            self._first_fault = {"code": code, "attempt": self._attempted}
        return False

    def _lookup(self, connection):
        entry = self._active.get(id(connection))
        if entry is not None and entry.connection is connection:
            return entry
        return None

    def record(self, kind, connection=None, **primitive_fields):
        if self._sealed is not None:
            return False
        self._attempted += 1
        if self._capped:
            return self._reject("capacity_exhausted")
        try:
            return self._record(kind, connection, primitive_fields)
        except Exception:
            # Never raise into the observed server path; refuse honestly.
            return self._reject("observer_internal_error")

    def _record(self, kind, connection, fields):
        if type(kind) is not str or kind not in KINDS:
            return self._reject("unknown_kind")
        rule = _CONNECTION_RULE[kind]
        entry = None
        if connection is None:
            if rule in ("new", "required"):
                return self._reject("connection_required")
        elif issubclass(type(connection), _PRIMITIVE_TYPES):
            return self._reject("connection_primitive")
        elif rule == "none":
            return self._reject("connection_not_allowed")
        elif rule == "new":
            if self._lookup(connection) is not None:
                return self._reject("connection_already_active")
        else:
            entry = self._lookup(connection)
            if entry is None:
                return self._reject("connection_unknown")
        fault = _check_fields(kind, fields)
        if fault is not None:
            return self._reject(fault)
        if kind == "listener_ready" and self._by_kind["listener_ready"]:
            return self._reject("listener_ready_duplicate")
        if kind == "request" and entry.method is not None:
            return self._reject("request_duplicate")
        if kind == "native":
            if fields["row_index"] in self._native_rows:
                return self._reject("native_row_duplicate")
            if entry is not None:
                if fields["wire"] in DIRECT_WIRES:
                    return self._reject("native_direct_wire_associated")
                if entry.method != "GET":
                    return self._reject("native_without_get")
                if entry.native_seen:
                    return self._reject("native_duplicate_connection")

        connection_id = self._next_id if kind == "accept" else (entry.connection_id if entry else None)
        row = {
            "sequence": self._attempted,
            "elapsed_ns": time.monotonic_ns() - self._origin_ns,
            "kind": kind,
            "connection_id": connection_id,
            "fields": {name: fields[name] for name in _FIELDS[kind]},
        }
        if len(self._rows) >= MAX_ROWS:
            self._capped = True
            return self._reject("row_cap")
        size = len(_dumps(row)) + (1 if self._rows else 0)
        if ENVELOPE_RESERVE + self._row_bytes + size > MAX_RESULT_BYTES:
            self._capped = True
            return self._reject("byte_cap")

        # Commit: the row and its state change happen together.
        self._rows.append(row)
        self._row_bytes += size
        self._by_kind[kind] += 1
        if kind == "accept":
            self._active[id(connection)] = _Active(connection, connection_id)
            self._next_id += 1
        elif kind == "request":
            entry.method = fields["method"]
        elif kind == "native":
            self._native_rows.add(fields["row_index"])
            if entry is not None:
                entry.native_seen = True
        elif kind == "close":
            if fields["confirmed"]:
                self._closed_true += 1
            else:
                self._closed_false += 1
            del self._active[id(connection)]
        return True

    def finish(self):
        if self._sealed is None:
            counts = _counts(self._attempted, len(self._rows), self._by_kind,
                             self._closed_true, self._closed_false)
            complete = (
                self._first_fault is None
                and self._by_kind["listener_ready"] == 1
                and counts["active_at_finish"] == 0
                and self._closed_false == 0
            )
            result = _envelope(self._rows, complete, self._first_fault, counts)
            # Release every retained socket reference; no physical cleanup.
            self._active.clear()
            self._sealed = copy.deepcopy(result)
            self._rows = None
        return copy.deepcopy(self._sealed)
