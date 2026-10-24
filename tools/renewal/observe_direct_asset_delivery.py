"""Root-bound normal delivery of the 1222 direct model/texture/water responses.

T07.007.014.011. Minimal derivative of the qualified GET34 terrain loop: one
sequential identity GET per selected query through http.client, exclusive
private evidence, pending-only settlement and one final preservation check.

Importing defines constants and functions only. ROOT_ADMITTED is False and
every binding/environment slot is unbound, so main() refuses with exit 2
before reading any binding, profile, target, process, listener or network.
There is no CLI admission switch: Root binds a fresh private copy of this file
by editing the seven SOURCE SLOTS below and supplying the pinned binding JSON
documented in docs/project/reviews/T07.007.014.011-direct-delivery-implementation.md.

Delivery is separate from materialization (materialization_required=false):
absent loose copies after HTTP 200 are recorded, never inferred as extraction
or cache provenance. Successful requests are never retried or replayed.
"""
import hashlib
import http.client
import json
import math
import os
import socket
import stat
import sys
import unicodedata
from urllib.parse import quote

# ---- SOURCE SLOTS (Root binds these in a fresh private copy only) ----
ROOT_ADMITTED = False
REQUIRED_HEAD = None
BINDING_PATH = None
BINDING_BYTES = None
BINDING_SHA256 = '0' * 64
ENV_SELECTION_BYTES = None
ENV_SELECTION_SHA256 = '0' * 64
# ---- end of source slots ----

TASK = 'T07.007.014.011'
BINDING_SCHEMA = 't07-014-011-direct-delivery-binding-v1'
RESULT_SCHEMA = 't07-014-011-direct-delivery-result-v1'
EVIDENCE_SCHEMA = 't07-014-011-direct-delivery-evidence-v1'
PILOT_AUDIT_SCHEMA = 't07-014-011-pilot-root-audit-v1'
PROFILE_SCHEMA = 't07-014-011-normal-direct-request-reuse-preparation-v1'
HOST = '127.0.0.1'
GUARD_PIN = {'bytes': 14021, 'sha256': 'c74f86a2f7f41aa5d468fe10c21cc4a837eea4b5684c4d12fef74d26f3a97a00'}
# Frozen domain from the brief/PLAN_UNBOUND_ROOT/ROOT_AUDIT; tests substitute a synthetic SPEC.
SPEC = {
    'profile_bytes': 5292194,
    'profile_sha256': '08dde887269c599a203323fd4dcb6731e5155f1f97d621a704dc5a7b318edaf5',
    'queries': 1222, 'maps': 21, 'relations': 2142,
    'roles': {'model': 936, 'texture': 222, 'water': 64},
    'retained': 115, 'new': 1107, 'nonascii': 452, 'slash_water': 64,
    'total_metadata_bytes': 24713759, 'max_body_bytes': 263220,
    'pilot': [124, 402, 439, 483, 564, 672, 1075, 1158], 'pilot_metadata_bytes': 612703,
    'remainder_count': 1214, 'remainder_metadata_bytes': 24101056,
    'alias_groups': [[483, 672], [516, 633], [522, 632]],
    'ambiguous_archive': [1158],
}
BODY_CAP = 1 << 20
AGGREGATE_CAP = 32 << 20
READ_BYTES = 64 << 10
IO_SECONDS = 3
BATCH_SECONDS = 60
SETTLE_SECONDS = 2
POLL_SECONDS = 0.05
STDOUT_BYTES = 4096
PREFIX_KEEP = 16
URI_SAFE = "-_.!~*'()"
ROLE_SIGNATURE = {'model': 'model', 'texture': 'bmp', 'water': 'jpeg'}
SIGNATURES = {'model': (b'GRSM', b'GRSX'), 'bmp': (b'BM',), 'jpeg': (b'\xff\xd8\xff',)}
FIELDS = ('st_dev', 'st_ino', 'st_size', 'st_mtime_ns', 'st_ctime_ns', 'st_mode', 'st_nlink', 'st_uid')
REQUEST_HEADERS = {'Accept-Encoding': 'identity', 'Connection': 'close'}
ATTEMPT_STATES = ('outside_batch', 'not_attempted', 'succeeded', 'failed')
MATERIALIZATION_STATES = ('unchanged', 'matched_new', 'shared_alias', 'absent', 'unsteady',
                          'mismatch', 'unverified', 'not_observed')
FATAL_MATERIALIZATION = ('unsteady', 'mismatch')
CLASSIFICATIONS = ('expected_match', 'new_observed', 'failed')
# Closed RESULT field types (checked before writing).
RESULT_TYPES = {
    'schema': str, 'task': str, 'batch': str, 'profile_pin': dict, 'binding_pin': dict,
    'pilot_audit_pin': (dict, type(None)), 'source_pin': dict, 'materialization_required': bool,
    'maps_unchanged': list, 'relations_unchanged': list, 'domain_provenance': dict, 'query_ledger': list,
    'counts': dict, 'verdict_authority': str,
    'delivery_complete': bool, 'materialization_complete': bool, 'preservation_complete': bool,
    'batch_complete': bool, 'first_error': (str, type(None)), 'postcheck_errors': list,
    'elapsed_seconds': float, 'ambiguous_archive_queries': list, 'archive_winner_claimed': bool,
}
LEDGER_KEYS = ('query', 'profile_record', 'wire_target', 'selected', 'attempt_state', 'expected_pin', 'metadata_bytes',
               'observed', 'materialization', 'alias_group', 'error')


class Refusal(Exception):
    """Preflight refusal: exit 2, no output directory."""


class Fail(Exception):
    """Attempted-request failure code."""


class Deadline(Exception):
    pass


class Unsafe(Exception):
    pass


class Unsteady(Exception):
    pass


def require(ok, code):
    if not ok:
        raise Refusal(code)


def is_int(v):
    return type(v) is int


def is_sha(v):
    return type(v) is str and len(v) == 64 and all(c in '0123456789abcdef' for c in v)


def closed(d, keys, code):
    require(type(d) is dict and set(d) == set(keys), code)


def digest(b):
    return hashlib.sha256(b).hexdigest()


def strict_json(data, code):
    """UTF-8 JSON with duplicate keys, NaN/Infinity and overflowing floats rejected."""
    def pairs(items):
        out = {}
        for k, v in items:
            require(k not in out, code)
            out[k] = v
        return out

    def flt(s):
        v = float(s)
        require(math.isfinite(v), code)
        return v

    def const(_):
        raise Refusal(code)
    try:
        text = data.decode('utf-8')
        return json.loads(text, object_pairs_hook=pairs, parse_float=flt, parse_constant=const)
    except Refusal:
        raise
    except Exception:
        raise Refusal(code)


def identity(path):
    s = os.lstat(path)
    return [getattr(s, k) for k in FIELDS]


def abs_path(p, code):
    require(type(p) is str and p and '\x00' not in p and os.path.isabs(p) and os.path.normpath(p) == p, code)
    return p


def pinned_read(path, n, sha, code):
    """GET34 pinned(): steady regular single-link file with exact bytes/SHA-256."""
    try:
        before = identity(path)
        require(stat.S_ISREG(before[5]) and before[6] == 1 and before[2] == n, code)
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
        try:
            data = _read_fd(fd, n + 1)
        finally:
            os.close(fd)
        require(identity(path) == before and len(data) == n and digest(data) == sha, code)
        return data
    except OSError:
        raise Refusal(code)


def _read_fd(fd, limit):
    chunks = []
    total = 0
    while total < limit:
        b = os.read(fd, min(READ_BYTES, limit - total))
        if not b:
            break
        chunks.append(b)
        total += len(b)
    return b''.join(chunks)


# ---- domain (profile -> 1222 typed rows) ----

def wire_from_raw(raw):
    """Latin1 bytes, backslash->slash, encodeURIComponent once per segment."""
    name = raw.decode('latin-1').replace('\\', '/')
    return name, '/' + '/'.join(quote(seg, safe=URI_SAFE, encoding='utf-8', errors='strict')
                                for seg in name.split('/'))


def safe_relative(rel):
    segs = rel.split('/')
    return all(s not in ('', '.', '..') and '\x00' not in s and '\\' not in s and not s.startswith('.')
               for s in segs) and len(segs) >= 2


def override_relative(rel):
    head, _, rest = rel.partition('/')
    return rest if head.lower() == 'data' else rel


def load_domain(profile, spec):
    """Validate the pinned profile into ordered rows; never alters a query object."""
    require(type(profile) is dict and profile.get('schema') == PROFILE_SCHEMA, 'profile_schema')
    queries, relations, maps = profile.get('queries'), profile.get('relations'), profile.get('maps')
    require(type(queries) is list and len(queries) == spec['queries'], 'profile_queries')
    require(type(relations) is list and len(relations) == spec['relations'], 'profile_relations')
    require(type(maps) is list and len(maps) == spec['maps'], 'profile_maps')
    rows, wires, roles = [], set(), {}
    nonascii = slash_water = retained = 0
    for i, q in enumerate(queries):
        require(type(q) is dict, 'query_type')
        query = q.get('query')
        require(type(query) is dict and is_int(query.get('query_index')) and query['query_index'] == i, 'query_index')
        role = query.get('role')
        require(role in ROLE_SIGNATURE and q.get('role') == role, 'query_role')
        require(q.get('signature_kind') == ROLE_SIGNATURE[role], 'signature_kind')
        ri = query.get('relation_indices')
        require(type(ri) is list and ri and all(is_int(x) and 0 <= x < spec['relations'] for x in ri), 'relation_indices')
        m = q.get('mapping')
        require(type(m) is dict, 'mapping')
        raw_hex = query.get('expected_name_hex')
        require(type(raw_hex) is str and m.get('raw_name_hex') == raw_hex, 'raw_name')
        try:
            raw = bytes.fromhex(raw_hex)
            rel, wire = wire_from_raw(raw)
        except (ValueError, UnicodeError):
            raise Refusal('raw_name')
        require(m.get('wire_target') == wire, 'wire_target')
        require(m.get('candidate_loose_relative_path') == rel and safe_relative(rel), 'unsafe_path')
        orel = override_relative(rel)
        require(m.get('candidate_override_relative_path') == orel and safe_relative('data/' + orel), 'override_path')
        require(wire not in wires, 'duplicate_wire')
        wires.add(wire)
        rng = q.get('metadata_real_size_range_current')
        require(type(rng) is list and len(rng) == 2 and all(is_int(x) for x in rng) and rng[0] == rng[1]
                and 0 < rng[0] <= spec['max_body_bytes'], 'metadata_size')
        cands = q.get('full_path_candidates')
        require(type(cands) is list and cands and all(type(c) is dict and is_int(c.get('real_size'))
                and c['real_size'] == rng[0] for c in cands), 'candidate_size')
        current = q.get('current_five_candidate_refs')
        require(type(current) is list and current and all(type(x) is str for x in current), 'current_candidates')
        reuse = q.get('reuse_expected')
        expected = None
        if reuse is None:
            require(q.get('new_body_expected_sha256') is None, 'new_expected_sha')
        else:
            body = reuse.get('retained_body') if type(reuse) is dict else None
            require(type(body) is dict and is_int(body.get('bytes')) and body['bytes'] == rng[0]
                    and is_sha(body.get('sha256')) and reuse.get('qualified_wire_target') == wire, 'retained_join')
            # Independent pin keeps its source join; a newly observed SHA never lands here.
            expected = {'bytes': body['bytes'], 'sha256': body['sha256'],
                        'qualified_wire_target': reuse['qualified_wire_target'],
                        'source_pointer': '/queries/%d/reuse_expected/retained_body' % i}
            retained += 1
        if any(c >= 0x80 for c in raw):
            nonascii += 1
        if role == 'water' and b'/' in raw:
            slash_water += 1
        roles[role] = roles.get(role, 0) + 1
        rows.append({'index': i, 'query': query, 'record': q, 'role': role, 'signature': ROLE_SIGNATURE[role], 'wire': wire,
                     'loose_rel': rel, 'override_rel': orel, 'metadata_bytes': rng[0], 'expected': expected,
                     'current_candidates': len(current)})
    require(roles == spec['roles'], 'role_counts')
    require(retained == spec['retained'] and len(rows) - retained == spec['new'], 'retained_counts')
    require(nonascii == spec['nonascii'] and slash_water == spec['slash_water'], 'mapping_counts')
    require(sum(r['metadata_bytes'] for r in rows) == spec['total_metadata_bytes']
            and max(r['metadata_bytes'] for r in rows) == spec['max_body_bytes'], 'metadata_total')
    for group in spec['alias_groups']:
        names = [rows[i]['loose_rel'] for i in group]
        require(len(set(names)) == len(names)
                and len({unicodedata.normalize('NFC', n).casefold() for n in names}) == 1, 'alias_group')
    for i in spec['ambiguous_archive']:
        require(rows[i]['current_candidates'] == 2, 'ambiguous_archive')
    pilot = spec['pilot']
    require(pilot == sorted(set(pilot)) and all(0 <= i < len(rows) for i in pilot), 'pilot')
    remainder = [i for i in range(len(rows)) if i not in set(pilot)]
    require(sum(rows[i]['metadata_bytes'] for i in pilot) == spec['pilot_metadata_bytes']
            and len(remainder) == spec['remainder_count']
            and sum(rows[i]['metadata_bytes'] for i in remainder) == spec['remainder_metadata_bytes'], 'batches')
    alias = {}
    for group in spec['alias_groups']:
        for i in group:
            alias[i] = list(group)
    for r in rows:
        r['alias_group'] = alias.get(r['index'])
    return {'rows': rows, 'batches': {'pilot': list(pilot), 'remainder': remainder},
            'maps': maps, 'relations': relations}


# ---- binding ----

PIN_KEYS = ('path', 'bytes', 'sha256')
BINDING_KEYS = ('schema', 'task', 'head', 'batch', 'profile', 'pilot_audit', 'environment', 'host', 'port',
                'asset_root', 'override_root', 'owners', 'guard', 'native', 'archives', 'targets', 'output')
OWNER_IDENTITY_KEYS = ('pid', 'ppid', 'pgid', 'uid', 'birth')
STATE_KEYS = ('present', 'identity', 'bytes', 'sha256')
AUDIT_KEYS = ('schema', 'task', 'auditor', 'batch', 'pilot_result_pin', 'pilot_query_indices',
              'pilot_response_bytes', 'admit_remainder')


def check_pin(p, code):
    closed(p, PIN_KEYS, code)
    abs_path(p['path'], code)
    require(is_int(p['bytes']) and p['bytes'] > 0 and is_sha(p['sha256']), code)
    return p


def check_identity(v, code):
    require(type(v) is list and len(v) == len(FIELDS) and all(is_int(x) for x in v), code)


def check_state(s, code):
    require(type(s) is dict, code)
    if s.get('present') is False:
        closed(s, ('present',), code)
    else:
        closed(s, STATE_KEYS, code)
        require(s['present'] is True and is_int(s['bytes']) and is_sha(s['sha256']), code)
        check_identity(s['identity'], code)


def check_binding(b, spec):
    closed(b, BINDING_KEYS, 'binding_keys')
    require(b['schema'] == BINDING_SCHEMA and b['task'] == TASK and b['head'] == REQUIRED_HEAD, 'binding_head')
    require(b['batch'] in ('pilot', 'remainder'), 'binding_batch')
    check_pin(b['profile'], 'binding_profile')
    require(b['profile']['bytes'] == spec['profile_bytes'] and b['profile']['sha256'] == spec['profile_sha256'],
            'binding_profile')
    if b['batch'] == 'pilot':
        require(b['pilot_audit'] is None, 'pilot_audit_unexpected')
    else:
        check_pin(b['pilot_audit'], 'pilot_audit_missing')
    closed(b['environment'], ('path',), 'binding_environment')
    abs_path(b['environment']['path'], 'binding_environment')
    require(b['host'] == HOST and is_int(b['port']) and 0 < b['port'] < 65536, 'binding_listener')
    for k in ('asset_root', 'override_root', 'output'):
        abs_path(b[k], 'binding_' + k)
    require(type(b['owners']) is dict and len(b['owners']) == 4 and 'asset' in b['owners'], 'binding_owners')
    for o in b['owners'].values():
        closed(o, ('identity', 'executable'), 'binding_owners')
        closed(o['identity'], OWNER_IDENTITY_KEYS, 'binding_owners')
        ident = o['identity']
        require(all(is_int(ident[k]) and ident[k] > 0 for k in ('pid', 'ppid', 'pgid')) and is_int(ident['uid'])
                and type(ident['birth']) is list and len(ident['birth']) == 2
                and all(is_int(x) for x in ident['birth']), 'binding_owners')
        abs_path(o['executable'], 'binding_owners')
    check_pin(b['guard'], 'binding_guard')
    require(b['guard']['bytes'] == GUARD_PIN['bytes'] and b['guard']['sha256'] == GUARD_PIN['sha256'], 'binding_guard')
    closed(b['native'], ('binary', 'ini'), 'binding_native')
    closed(b['native']['binary'], ('path', 'identity'), 'binding_native')
    abs_path(b['native']['binary']['path'], 'binding_native')
    check_identity(b['native']['binary']['identity'], 'binding_native')
    closed(b['native']['ini'], PIN_KEYS + ('identity',), 'binding_native')
    check_pin({k: b['native']['ini'][k] for k in PIN_KEYS}, 'binding_native')
    check_identity(b['native']['ini']['identity'], 'binding_native')
    require(type(b['archives']) is list and len(b['archives']) == 5, 'binding_archives')
    for k, a in enumerate(b['archives']):
        closed(a, ('order', 'path', 'identity'), 'binding_archives')
        require(is_int(a['order']) and a['order'] == k, 'binding_archives')
        abs_path(a['path'], 'binding_archives')
        check_identity(a['identity'], 'binding_archives')
    require(type(b['targets']) is list and len(b['targets']) == spec['queries'], 'binding_targets')
    for i, t in enumerate(b['targets']):
        closed(t, ('query_index', 'loose', 'override'), 'binding_targets')
        require(is_int(t['query_index']) and t['query_index'] == i, 'binding_targets')
        check_state(t['loose'], 'binding_targets')
        check_state(t['override'], 'binding_targets')
    out = b['output']
    for k in ('asset_root', 'override_root'):
        require(not (out + '/').startswith(b[k] + '/'), 'output_inside_live_root')
    return b


def check_pilot_audit(audit, spec):
    closed(audit, AUDIT_KEYS, 'pilot_audit')
    require(audit['schema'] == PILOT_AUDIT_SCHEMA and audit['schema'] != RESULT_SCHEMA
            and audit['task'] == TASK and audit['auditor'] == 'Root' and audit['batch'] == 'pilot', 'pilot_audit')
    pin = audit['pilot_result_pin']
    closed(pin, ('bytes', 'sha256'), 'pilot_audit')
    require(is_int(pin['bytes']) and is_sha(pin['sha256']), 'pilot_audit')
    require(audit['pilot_query_indices'] == spec['pilot'] and all(is_int(i) for i in audit['pilot_query_indices']),
            'pilot_audit')
    require(is_int(audit['pilot_response_bytes']) and audit['pilot_response_bytes'] == spec['pilot_metadata_bytes'],
            'pilot_audit')
    require(audit['admit_remainder'] is True, 'pilot_audit')
    return audit


# ---- live-file observation (GET34 snapshot, per logical row) ----

def check_ancestors(path, parents=None):
    """Every existing ancestor of path is a real directory (GET34 parent rule)."""
    head = os.path.dirname(path)
    while True:
        try:
            s = os.lstat(head)
        except FileNotFoundError:
            s = None
        if s is not None:
            if stat.S_ISLNK(s.st_mode) or not stat.S_ISDIR(s.st_mode):
                raise Unsafe('unsafe_parent')
            if parents is not None:
                parents.setdefault(head, [s.st_dev, s.st_ino, s.st_mode, s.st_uid])
        nxt = os.path.dirname(head)
        if nxt == head:
            break
        head = nxt


def sample(path, parents=None):
    """Return a state dict; refuse symlinks/nonregular/multi-link; Unsteady on identity drift."""
    check_ancestors(path, parents)
    try:
        s = os.lstat(path)
    except FileNotFoundError:
        return {'present': False}
    if not stat.S_ISREG(s.st_mode):
        raise Unsafe('unsafe_target')
    if s.st_nlink != 1:
        raise Unsafe('multilink_target')
    if s.st_size > BODY_CAP:
        raise Unsafe('oversize_target')
    before = [getattr(s, k) for k in FIELDS]
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW)
    except FileNotFoundError:
        raise Unsteady('vanished')
    try:
        data = _steady_read(fd, path)
    finally:
        os.close(fd)
    try:
        after = identity(path)
    except FileNotFoundError:
        raise Unsteady('vanished')
    if after != before or len(data) != before[2]:
        raise Unsteady('changed')
    return {'present': True, 'identity': before, 'bytes': len(data), 'sha256': digest(data)}


def _steady_read(fd, path):
    return _read_fd(fd, BODY_CAP + 1)


def observe(path):
    """Settlement/final sample: never raises; unsteady/unsafe become explicit states."""
    try:
        return sample(path)
    except Unsteady:
        return {'present': True, 'unsteady': True}
    except Unsafe as e:
        return {'present': True, 'unsafe': str(e)}
    except OSError as e:
        return {'present': True, 'sample_error': type(e).__name__}


def leaf_present(path):
    try:
        os.lstat(path)
        return True
    except FileNotFoundError:
        return False
    except OSError:
        return True


# ---- output ----

def write_new(directory, name, data):
    fd = os.open(os.path.join(directory, name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
    finally:
        os.close(fd)


def dump_bytes(value):
    return (json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, indent=1) + '\n').encode('ascii')


def emit(value):
    line = json.dumps(value, sort_keys=True, ensure_ascii=True, allow_nan=False, separators=(',', ':'))
    if len(line.encode('ascii')) + 1 > STDOUT_BYTES:
        line = json.dumps({'status': value.get('status'), 'truncated': True}, sort_keys=True, separators=(',', ':'))
    sys.stdout.write(line + '\n')
    sys.stdout.flush()


# ---- real runtime probes (constructed only after admission; tests inject fakes) ----

class RealIO:
    """Root-runtime probes: monotonic clock, http.client, pinned guard and lsof."""

    def __init__(self, binding):
        import ctypes
        import time
        import types
        self._time = time
        g = binding['guard']
        guard = types.ModuleType('owned_asset_read')
        exec(compile(pinned_read(g['path'], g['bytes'], g['sha256'], 'guard_pin'), g['path'], 'exec'),
             guard.__dict__)
        self._guard = guard
        self._kernel = guard.Kernel()
        lib = ctypes.CDLL('/usr/lib/libproc.dylib')
        lib.proc_pidpath.argtypes = [ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32]
        lib.proc_pidpath.restype = ctypes.c_int
        self._ctypes, self._lib = ctypes, lib
        self._owners = binding['owners']
        self._port = binding['port']

    def clock(self):
        return self._time.monotonic()

    def sleep(self, seconds):
        self._time.sleep(seconds)

    def connect(self, host, port, timeout):
        return http.client.HTTPConnection(host, port, timeout=timeout)

    def owners_check(self):
        for o in self._owners.values():
            ident = o['identity']
            if not self._guard.same_birth(self._kernel.get(ident['pid']), ident):
                raise Fail('owner_drift')
            buf = self._ctypes.create_string_buffer(4096)
            if self._lib.proc_pidpath(ident['pid'], buf, 4096) <= 0 or os.fsdecode(buf.value) != o['executable']:
                raise Fail('owner_drift')

    def listener_check(self):
        import subprocess
        pid = self._owners['asset']['identity']['pid']
        r = subprocess.run(['/usr/sbin/lsof', '-nP', '-a', '-p', str(pid), '-iTCP:%d' % self._port, '-sTCP:LISTEN'],
                           stdin=subprocess.DEVNULL, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                           timeout=IO_SECONDS, check=False)
        if r.returncode != 0 or r.stderr or len(r.stdout) >= 16384 \
                or ('%s:%d (LISTEN)' % (HOST, self._port)).encode() not in r.stdout:
            raise Fail('listener_drift')


# ---- admission and preflight ----

def admit(argv):
    """Source-slot authority only; performs no I/O."""
    require(list(argv) == [], 'argv')
    require(ROOT_ADMITTED is True, 'unbound')
    require(type(REQUIRED_HEAD) is str and len(REQUIRED_HEAD) == 40
            and all(c in '0123456789abcdef' for c in REQUIRED_HEAD), 'unbound_head')
    abs_path(BINDING_PATH, 'unbound_binding')
    require(is_int(BINDING_BYTES) and BINDING_BYTES > 0 and is_sha(BINDING_SHA256)
            and BINDING_SHA256 != '0' * 64, 'unbound_binding')
    require(is_int(ENV_SELECTION_BYTES) and ENV_SELECTION_BYTES > 0 and is_sha(ENV_SELECTION_SHA256)
            and ENV_SELECTION_SHA256 != '0' * 64, 'unbound_environment')
    return {'binding': {'bytes': BINDING_BYTES, 'sha256': BINDING_SHA256}}


def source_path():
    return os.path.abspath(__file__)


def source_pin():
    with open(source_path(), 'rb') as f:
        data = f.read()
    return {'bytes': len(data), 'sha256': digest(data)}


def target_paths(b, row):
    return (os.path.join(b['asset_root'], row['loose_rel']), os.path.join(b['override_root'], row['override_rel']))


def preflight(argv, io=None):
    admit(argv)
    spec = SPEC
    b = check_binding(strict_json(pinned_read(BINDING_PATH, BINDING_BYTES, BINDING_SHA256, 'binding_pin'),
                                  'binding_json'), spec)
    p = b['profile']
    domain = load_domain(strict_json(pinned_read(p['path'], p['bytes'], p['sha256'], 'profile_pin'),
                                     'profile_json'), spec)
    audit_pin = None
    base_bytes = 0
    if b['batch'] == 'remainder':
        a = b['pilot_audit']
        require(not (a['path'] + '/').startswith(b['output'] + '/')
                and os.path.basename(a['path']) != 'RESULT_ROOT.json', 'pilot_audit_self')
        audit = check_pilot_audit(strict_json(pinned_read(a['path'], a['bytes'], a['sha256'], 'pilot_audit_pin'),
                                               'pilot_audit'), spec)
        require(audit['pilot_result_pin']['sha256'] != a['sha256'], 'pilot_audit_self')
        audit_pin = {'bytes': a['bytes'], 'sha256': a['sha256']}
        base_bytes = audit['pilot_response_bytes']
    env = strict_json(pinned_read(b['environment']['path'], ENV_SELECTION_BYTES, ENV_SELECTION_SHA256,
                                  'environment_pin'), 'environment_json')
    sel = env.get('selected') if type(env) is dict else None

    def val(k):
        e = sel.get(k) if type(sel) is dict else None
        return e.get('value') if type(e) is dict else None
    require(val('CLIENT_AUTOEXTRACT') == 'true' and val('SERVER_ROOT') == b['asset_root']
            and val('HOST') == b['host'] and val('PORT') == str(b['port']), 'environment_selection')
    require(val('DATA_OVERRIDE_PATH') in (None, b['override_root']), 'environment_selection')
    pinned_read(b['guard']['path'], b['guard']['bytes'], b['guard']['sha256'], 'guard_pin')
    ini = b['native']['ini']
    pinned_read(ini['path'], ini['bytes'], ini['sha256'], 'native_pin')
    fixed = fixed_identities(b)
    require(fixed_errors(b, fixed) == [], 'native_or_archive_drift')
    if io is None:
        io = RealIO(b)
    try:
        io.owners_check()
        io.listener_check()
    except Fail as e:
        raise Refusal(str(e))
    except Exception as e:
        raise Refusal('probe_error:%s' % type(e).__name__)
    parents, before = {}, {}
    for row in domain['rows']:
        loose, override = target_paths(b, row)
        try:
            state = (sample(loose, parents), sample(override, parents))
        except (Unsafe, Unsteady, OSError):
            raise Refusal('unsafe_or_unsteady_target')
        bound = b['targets'][row['index']]
        require(state[0] == bound['loose'] and state[1] == bound['override'], 'target_drift')
        exp = row['expected']
        if state[0]['present'] and exp is not None:
            require((state[0]['bytes'], state[0]['sha256']) == (exp['bytes'], exp['sha256']), 'existing_wrong_bytes')
        before[row['index']] = state
    out = b['output']
    out_parent = os.path.dirname(out)
    try:
        check_ancestors(out)
        require(stat.S_ISDIR(os.lstat(out_parent).st_mode), 'output_parent')
    except (Unsafe, OSError):
        raise Refusal('output_parent')
    require(not os.path.lexists(out), 'output_exists')
    return {'binding': b, 'domain': domain, 'io': io, 'audit_pin': audit_pin, 'base_bytes': base_bytes,
            'parents': parents, 'before': before, 'fixed': fixed, 'source': source_pin()}


def fixed_identities(b):
    paths = [b['native']['binary']['path'], b['native']['ini']['path'], b['guard']['path'],
             b['environment']['path']] + [a['path'] for a in b['archives']]
    out = {}
    for p in paths:
        try:
            out[p] = identity(p)
        except OSError:
            out[p] = None
    return out


def fixed_errors(b, now):
    errs = []
    if now[b['native']['binary']['path']] != b['native']['binary']['identity'] \
            or now[b['native']['ini']['path']] != b['native']['ini']['identity']:
        errs.append('native_drift')
    if any(now[a['path']] != a['identity'] for a in b['archives']):
        errs.append('archive_drift')
    return errs


# ---- one attempted request (adapted GET34 HTTPConnection/read loop) ----

class Run:
    def __init__(self, ctx):
        self.ctx, self.io = ctx, ctx['io']
        self.started = self.io.clock()
        self.deadline = self.started + BATCH_SECONDS
        self.total = ctx['base_bytes']
        self.batch_bytes = 0
        self.first_error = None
        self.postcheck_errors = []

    def remaining(self):
        n = self.deadline - self.io.clock()
        if n <= 0:
            raise Deadline()
        return min(n, IO_SECONDS)

    def error(self, code, post=False):
        if self.first_error is None:
            self.first_error = code
        if post:
            self.postcheck_errors.append(code)


def signature_state(kind, prefix):
    return 'match' if any(prefix.startswith(s) for s in SIGNATURES[kind]) else 'mismatch'


def fetch(run, row, out):
    i = row['index']
    body_name = 'body-%04d.bin' % i
    ev = {'schema': EVIDENCE_SCHEMA, 'query_index': i, 'wire_target': row['wire'], 'status': None,
          'content_encoding': None, 'transfer_encoding': None, 'raw_declared_length': None, 'location': None,
          'bytes': 0, 'sha256': None, 'hash_scope': 'none', 'http_eof': False, 'body_file': None,
          'prefix_hex': '', 'signature': 'not_checked', 'classification': 'failed', 'error': None}
    h = hashlib.sha256()
    n = 0
    prefix = b''
    error = None
    conn = None
    resp = None
    fd = None

    def take(b):
        # Account, hash and store every returned byte before any later cap/deadline check.
        nonlocal n, prefix
        n += len(b)
        run.total += len(b)
        run.batch_bytes += len(b)
        h.update(b)
        if len(prefix) < PREFIX_KEEP:
            prefix += b[:PREFIX_KEEP - len(prefix)]
        view = memoryview(b)
        while view:
            view = view[os.write(fd, view):]
    try:
        conn = run.io.connect(run.ctx['binding']['host'], run.ctx['binding']['port'], run.remaining())
        conn.request('GET', row['wire'], headers=REQUEST_HEADERS)
        channel = conn.sock
        channel.settimeout(run.remaining())
        resp = conn.getresponse()
        ev['status'] = resp.status
        msg = resp.msg
        enc, te = msg.get_all('Content-Encoding') or [], msg.get_all('Transfer-Encoding') or []
        cl, loc = msg.get_all('Content-Length') or [], msg.get_all('Location') or []
        ev['content_encoding'] = ', '.join(enc) if enc else None
        ev['transfer_encoding'] = ', '.join(te) if te else None
        ev['raw_declared_length'] = ', '.join(cl) if cl else None
        ev['location'] = ', '.join(loc) if loc else None
        if resp.status != 200 or loc:
            raise Fail('redirect' if 300 <= resp.status < 400 or loc else 'http_status')
        if enc and enc != ['identity']:
            raise Fail('content_encoding')
        if (cl and te) or len(set(cl)) > 1 or (te and te != ['chunked']):
            raise Fail('conflicting_framing')
        if cl:
            if not cl[0].isascii() or not cl[0].isdigit():
                raise Fail('conflicting_framing')
            if int(cl[0]) > BODY_CAP:
                raise Fail('declared_over_cap')
            if int(cl[0]) != row['metadata_bytes']:
                raise Fail('declared_length_mismatch')
        fd = os.open(os.path.join(out, body_name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        os.fchmod(fd, 0o600)
        ev['body_file'] = body_name
        while True:
            # http.client closes a Connection:close response (and its socket) itself once the
            # declared length or final chunk is consumed; that is the complete end, not a fault.
            if getattr(resp, 'isclosed', lambda: False)():
                ev['http_eof'] = True
                break
            channel.settimeout(run.remaining())
            want = min(READ_BYTES, BODY_CAP + 1 - n)
            try:
                b = resp.read(want)
            except http.client.IncompleteRead as e:
                take(bytes(e.partial)[:want])
                raise
            take(b)
            if not b:
                ev['http_eof'] = True
            if n > BODY_CAP:
                raise Fail('body_over_cap')
            if run.total > AGGREGATE_CAP:
                raise Fail('aggregate_cap')
            run.remaining()
            if not b:
                break
    except Fail as e:
        error = str(e)
    except Deadline:
        error = 'deadline'
    except (TimeoutError, socket.timeout):
        error = 'io_timeout'
    except http.client.IncompleteRead:
        error = 'incomplete_read'
    except http.client.HTTPException:
        error = 'http_protocol'
    except OSError:
        error = 'transport'
    finally:
        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                error = error or 'close_failed'
        if resp is not None and hasattr(resp, 'close'):
            try:
                resp.close()  # releases the socket the response still holds
            except Exception:
                error = error or 'close_failed'
        if conn is not None:
            try:
                conn.close()
            except Exception:
                error = error or 'close_failed'
    ev['bytes'] = n
    ev['sha256'] = h.hexdigest() if ev['body_file'] else None
    ev['prefix_hex'] = prefix.hex()
    ev['hash_scope'] = 'none' if not ev['body_file'] else ('complete' if error is None else 'prefix')
    if error is None:
        ev['signature'] = signature_state(row['signature'], prefix)
        if cl and n < int(cl[0]):
            error = 'short_body'
        elif n != row['metadata_bytes']:
            error = 'size_mismatch'
        elif ev['signature'] != 'match':
            error = 'signature_mismatch'
        elif row['expected'] is not None and ev['sha256'] != row['expected']['sha256']:
            error = 'expected_sha_mismatch'
        else:
            try:
                stored = pinned_read(os.path.join(out, body_name), n, ev['sha256'], 'stored_body')
                del stored
            except Refusal:
                error = 'stored_body_mismatch'
    if error is None:
        ev['classification'] = 'expected_match' if row['expected'] is not None else 'new_observed'
    else:
        ev['hash_scope'] = 'prefix' if ev['body_file'] else 'none'
    ev['error'] = error
    try:
        write_new(out, 'response-%04d.json' % i, dump_bytes(ev))
    except OSError:
        error = error or 'write_failed'
        ev['error'] = error
        ev['classification'] = 'failed'
    return ev, error


# ---- materialization ----

def classify(row, before, after, ev, partner_after):
    if after.get('unsteady'):
        return 'unsteady'
    if after.get('unsafe') or after.get('sample_error'):
        return 'mismatch'
    if before['present']:
        if after != before:
            return 'mismatch'
        # Unchanged identity alone is not a match: stable bytes must equal the delivered response.
        if ev is not None and ev['classification'] != 'failed' \
                and (after['bytes'], after['sha256']) != (ev['bytes'], ev['sha256']):
            return 'mismatch'
        return 'unchanged'
    if not after['present']:
        return 'absent'
    if ev is None or ev['classification'] == 'failed':
        return 'unverified'
    if (after['bytes'], after['sha256']) != (ev['bytes'], ev['sha256']):
        return 'mismatch'
    for other in partner_after:
        if other.get('present') and other.get('identity') and other['identity'][:2] == after['identity'][:2]:
            return 'shared_alias'
    return 'matched_new'


def matches(after, ev):
    return (after.get('present') and 'identity' in after and ev is not None
            and ev['classification'] != 'failed' and (after['bytes'], after['sha256']) == (ev['bytes'], ev['sha256']))


def execute(ctx):
    b, domain, io = ctx['binding'], ctx['domain'], ctx['io']
    rows = domain['rows']
    out = b['output']
    try:
        os.mkdir(out, 0o700)
        os.chmod(out, 0o700)
    except OSError:
        emit({'status': 'refused', 'reason': 'output_exists', 'task': TASK})
        return 2
    run = Run(ctx)
    selected = domain['batches'][b['batch']]
    sel_set = set(selected)
    before = ctx['before']
    try:
        write_new(out, 'BEFORE_ROOT.json', dump_bytes({
            'schema': EVIDENCE_SCHEMA, 'task': TASK, 'batch': b['batch'], 'source_pin': ctx['source'],
            'targets': [{'query_index': i, 'loose': before[i][0], 'override': before[i][1]} for i in range(len(rows))],
            'parents': ctx['parents'], 'fixed_identities': ctx['fixed'], 'owners': b['owners'],
            'normal_auto_extraction_admitted': True, 'full_environment_retained': False}))
    except OSError:
        run.error('write_failed')
    attempts, evidence = {}, {}
    if run.first_error is None:
        for i in selected:
            row = rows[i]
            loose, override = target_paths(b, row)
            try:
                io.owners_check()
                now = (observe(loose), observe(override))
                if before[i][0]['present'] and now[0] != before[i][0] or now[1] != before[i][1]:
                    raise Fail('existing_mutation')
                if any(k in now[0] for k in ('unsteady', 'unsafe', 'sample_error')):
                    raise Fail('q%04d:unsafe_or_unsteady_target' % i)
            except Fail as e:
                run.error(str(e))
                break
            except Exception as e:
                run.error('owners_probe_error:%s' % type(e).__name__)
                break
            ev, err = fetch(run, row, out)
            attempts[i] = 'failed' if err else 'succeeded'
            evidence[i] = ev
            if err:
                run.error('q%04d:%s' % (i, err))
                break
    # Pending-only settlement inside the batch deadline: stable matches leave immediately.
    pending = [i for i in attempts if not before[i][0]['present']]
    polls = {i: 0 for i in attempts}
    settle_end = min(run.deadline, io.clock() + SETTLE_SECONDS)
    while pending and io.clock() < settle_end:
        still = []
        for i in pending:
            polls[i] += 1
            loose = target_paths(b, rows[i])[0]
            if not leaf_present(loose) or not matches(observe(loose), evidence[i]):
                still.append(i)
        pending = still
        if pending:
            io.sleep(POLL_SECONDS)
    # One final complete required-set check: attempted rows and every prior present target.
    after = {}
    for row in rows:
        i = row['index']
        if i in attempts or before[i][0]['present'] or before[i][1]['present']:
            after[i] = tuple(observe(p) for p in target_paths(b, row))
    materialization = {}
    for i in attempts:
        group = rows[i]['alias_group'] or []
        partners = [after[j][0] for j in group if j != i and j in after]
        state = classify(rows[i], before[i][0], after[i][0], evidence.get(i), partners)
        if after[i][1] != before[i][1]:
            state = 'mismatch'
        materialization[i] = {'before': before[i][0], 'after': after[i][0], 'override_before': before[i][1],
                              'override_after': after[i][1], 'state': state, 'polls': polls[i]}
        if state in FATAL_MATERIALIZATION:
            run.error('q%04d:materialization_%s' % (i, state), post=True)
    for i in after:
        if i not in attempts and after[i] != before[i] and (before[i][0]['present'] or before[i][1]['present']):
            run.error('q%04d:existing_mutation' % i, post=True)
    preserved = not any(m['state'] in FATAL_MATERIALIZATION for m in materialization.values())
    for name, check in (('owners', io.owners_check), ('listener', io.listener_check)):
        try:
            check()
        except Fail as e:
            run.error(str(e), post=True)
            preserved = False
        except Exception as e:  # e.g. TimeoutExpired/OSError: record, keep the remaining checks
            run.error('%s_probe_error:%s' % (name, type(e).__name__), post=True)
            preserved = False
    for code in fixed_errors(b, fixed_identities(b)):
        run.error(code, post=True)
        preserved = False
    if fixed_identities(b)[b['environment']['path']] != ctx['fixed'][b['environment']['path']] \
            or fixed_identities(b)[b['guard']['path']] != ctx['fixed'][b['guard']['path']]:
        run.error('environment_or_guard_drift', post=True)
        preserved = False
    for p, ident in ctx['parents'].items():
        try:
            s = os.lstat(p)
            ok = not stat.S_ISLNK(s.st_mode) and [s.st_dev, s.st_ino, s.st_mode, s.st_uid] == ident
        except OSError:
            ok = False
        if not ok:
            run.error('parent_drift', post=True)
            preserved = False
            break
    try:
        if source_pin() != ctx['source']:
            raise OSError()
    except OSError:
        run.error('source_drift', post=True)
        preserved = False
    if any(e.endswith('existing_mutation') for e in run.postcheck_errors):
        preserved = False
    elapsed = float(io.clock() - run.started)
    if elapsed >= BATCH_SECONDS:
        run.error('deadline', post=True)
    try:
        write_new(out, 'AFTER_ROOT.json', dump_bytes({
            'schema': EVIDENCE_SCHEMA, 'task': TASK, 'batch': b['batch'],
            'targets': [{'query_index': i, 'loose': after[i][0], 'override': after[i][1]} for i in sorted(after)],
            'parents': ctx['parents'], 'fixed_identities': fixed_identities(b),
            'observed_settling_only': True, 'outstanding_server_tasks_not_enumerated': True}))
    except OSError:
        run.error('write_failed', post=True)
    ledger = []
    for row in rows:
        i = row['index']
        state = attempts.get(i, 'not_attempted' if i in sel_set else 'outside_batch')
        mat = materialization.get(i)
        if mat is None:
            mat = {'state': 'not_observed', 'before': before[i][0], 'after': None, 'override_before': before[i][1],
                   'override_after': None, 'polls': 0}
        ledger.append({'query': row['query'], 'profile_record': row['record'], 'wire_target': row['wire'], 'selected': i in sel_set,
                       'attempt_state': state, 'expected_pin': row['expected'],
                       'metadata_bytes': row['metadata_bytes'], 'observed': evidence.get(i),
                       'materialization': mat, 'alias_group': row['alias_group'],
                       'error': evidence[i]['error'] if i in evidence else None})
    counts = {'queries': len(rows), 'selected': len(selected), 'attempted': len(attempts),
              'succeeded': sum(1 for v in attempts.values() if v == 'succeeded'),
              'failed': sum(1 for v in attempts.values() if v == 'failed'),
              'not_attempted': sum(1 for r in ledger if r['attempt_state'] == 'not_attempted'),
              'outside_batch': sum(1 for r in ledger if r['attempt_state'] == 'outside_batch'),
              'expected_match': sum(1 for e in evidence.values() if e['classification'] == 'expected_match'),
              'new_observed': sum(1 for e in evidence.values() if e['classification'] == 'new_observed'),
              'batch_response_bytes': run.batch_bytes, 'cumulative_response_bytes': run.total,
              'materialization': {s: sum(1 for m in materialization.values() if m['state'] == s)
                                  for s in MATERIALIZATION_STATES}}
    delivery = counts['succeeded'] == len(selected) and counts['failed'] == 0
    materialized = delivery and all(m['state'] in ('unchanged', 'matched_new', 'shared_alias')
                                    for m in materialization.values())
    preserved = preserved and not run.postcheck_errors
    complete = delivery and preserved and run.first_error is None
    result = {'schema': RESULT_SCHEMA, 'task': TASK, 'batch': b['batch'],
              'profile_pin': {'bytes': b['profile']['bytes'], 'sha256': b['profile']['sha256']},
              'binding_pin': {'bytes': BINDING_BYTES, 'sha256': BINDING_SHA256},
              'pilot_audit_pin': ctx['audit_pin'], 'source_pin': ctx['source'], 'materialization_required': False,
              'maps_unchanged': domain['maps'], 'relations_unchanged': domain['relations'],
              'domain_provenance': {'profile_schema': PROFILE_SCHEMA, 'profile_pin': {'bytes': b['profile']['bytes'],
                                    'sha256': b['profile']['sha256']}, 'maps': '/maps', 'relations': '/relations',
                                    'queries': '/queries', 'query_ledger_query': '/queries/<i>/query',
                                    'query_ledger_profile_record': '/queries/<i>'},
              'query_ledger': ledger, 'counts': counts,
              'verdict_authority': 'candidate_before_publication; stdout, exit and Root outer audit are final', 'delivery_complete': delivery, 'materialization_complete': materialized,
              'preservation_complete': preserved, 'batch_complete': complete, 'first_error': run.first_error,
              'postcheck_errors': run.postcheck_errors, 'elapsed_seconds': elapsed,
              'ambiguous_archive_queries': list(SPEC['ambiguous_archive']), 'archive_winner_claimed': False}
    assert set(result) == set(RESULT_TYPES) and all(isinstance(result[k], t) for k, t in RESULT_TYPES.items())
    assert all(tuple(sorted(r)) == tuple(sorted(LEDGER_KEYS)) for r in ledger)
    try:
        write_new(out, 'RESULT_ROOT.json', dump_bytes(result))
    except OSError:
        complete = False
        if run.first_error is None:
            run.first_error = 'write_failed'
    # Final deadline verdict after publication/closing: a late failure overrides the written candidate.
    final_elapsed = float(io.clock() - run.started)
    late = final_elapsed >= BATCH_SECONDS
    if late:
        complete = False
        if run.first_error is None:
            run.first_error = 'deadline_after_publication'
    code = 0 if complete else 1
    emit({'status': 'complete' if code == 0 else 'failed', 'task': TASK, 'batch': b['batch'], 'exit': code,
          'first_error': (run.first_error or '')[:200] or None, 'postcheck_errors': len(run.postcheck_errors),
          'delivery_complete': delivery, 'materialization_complete': materialized,
          'preservation_complete': preserved, 'batch_complete': complete,
          'counts': {k: v for k, v in counts.items() if k != 'materialization'},
          'elapsed_seconds': round(elapsed, 6), 'final_elapsed_seconds': round(final_elapsed, 6),
          'deadline_after_publication': late})
    return code


def main(argv=None, io=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        ctx = preflight(argv, io)
    except Refusal as e:
        emit({'status': 'refused', 'reason': str(e), 'task': TASK})
        return 2
    except Exception:
        emit({'status': 'refused', 'reason': 'internal', 'task': TASK})
        return 2
    try:
        return execute(ctx)
    except Exception:
        emit({'status': 'failed', 'reason': 'internal', 'task': TASK})
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
