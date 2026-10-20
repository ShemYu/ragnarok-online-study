"""Root-operated bounded observation of first-level map dependency targets.

T06.003.003.005. --preflight reads only the pinned profile, authored controls,
catalog and rule-source metadata; it never opens/stats native inputs, launches
a process or contacts HTTP. --execute requires the exact root-reviewed driver
SHA-256, then performs one owned loopback reader scan of every catalog target.
Results are first-level availability/prefix evidence only, never parsing,
rendering, playable-map or full-content proof.
"""
import argparse
import datetime
import hashlib
import http.client
import json
import math
import os
import re
import socket
import stat
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import quote, unquote

TASK = 'T06.003.003.005'
SCHEMA = 'T06-map-dependency-observation-1'
PROFILE_SCHEMA = 'T06-map-dependency-observation-profile-1'
AUTHORED_SCHEMA = 'T06-map-dependency-observation-authored-1'
PROFILE_BYTES = 7258
PROFILE_SHA = 'c581255b5b77cbd7c675ada5e271360e274bdbbe740a4e7eb921317b4c6889f5'
PRIOR_PROFILE_PATH = 'docs/project/fixtures/T06.003.003.004-profile.json'
CHECKOUT = Path(__file__).resolve().parents[2]
CONTAINER = CHECKOUT / '.tools' / 'renewal'
READ_MAX = 64 << 10
HASH_CHUNK = 4 << 20
CHECKPOINT_EVERY = 128
POLICY = {
    'body_bytes': 25165824, 'aggregate_bytes_including_health': 8589934592, 'health_bytes': 65536,
    'asset_attempts': 11134, 'health_attempts': 1, 'startup_seconds': 25, 'acquisition_seconds': 1200,
    'io_seconds': 5, 'cache_mb': 64, 'cache_files': 32, 'missing_log_bytes': 16777216,
    'report_bytes': 67108864, 'catalog_bytes': 134217728, 'stdout_bytes': 4096,
    'disk_reserve_bytes': 4294967296, 'root_guard_seconds': 1800, 'root_observed_rss_bytes': 2147483648}
DISK_WORKING_BYTES = 8 << 30
NATIVE_NAMES = ['binary', 'event.grf', 'data0.grf', 'data.grf']
KINDS = {'rsm': 'model', 'rsm2': 'model', 'bmp': 'bmp', 'BMP': 'bmp', 'jpg': 'jpeg'}
ROLE_KINDS = {'model': {'model'}, 'ground_texture': {'bmp', 'jpeg'}}
JOB_ROLES = {'rsw': 'model', 'gnd': 'ground_texture', 'gat': None}
SIGNATURES = {'model': (6, 4, (b'GRSM', b'GRSX')), 'bmp': (2, 2, (b'BM',)), 'jpeg': (2, 2, (b'\xff\xd8',))}
WIRE_CHARS = frozenset('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
                       "-._~!$&'()*+,;=:@")
HEX = frozenset('0123456789abcdefABCDEF')
OUTCOMES = ('complete', 'declared_over_cap', 'cap_unresolved_eof', 'aggregate_cap', 'deadline', 'transport_error')
HEADER_NAMES = (('content_length', 'Content-Length'), ('content_type', 'Content-Type'),
                ('content_encoding', 'Content-Encoding'), ('transfer_encoding', 'Transfer-Encoding'),
                ('location', 'Location'))
HEADER_MAX = 2048
TIMESTAMP = re.compile(r'\A\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z\Z')
NUMERIC = re.compile(r'\A\d{6}\Z')


class Refusal(Exception):
    """Generic, no-echo refusal code."""


class Absent(Exception):
    """An admitted path or ancestor is ENOENT."""


def require(ok, code):
    if not ok:
        raise Refusal(code)


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def identity(st):
    return [st.st_dev, st.st_ino, st.st_size, st.st_mtime_ns, st.st_ctime_ns]


# ---------------------------------------------------------------- shared API

def wire_target(http_path):
    """Return slash plus the unchanged encoded ASCII path, or ValueError."""
    if not isinstance(http_path, str) or not http_path:
        raise ValueError('unsupported wire target')
    for segment in http_path.split('/'):
        if segment in ('', '.', '..'):
            raise ValueError('unsupported wire target')
        i = 0
        while i < len(segment):
            char = segment[i]
            if char == '%':
                if len(segment) - i < 3:
                    raise ValueError('unsupported wire target')
                if segment[i + 1] not in HEX or segment[i + 2] not in HEX:
                    raise ValueError('unsupported wire target')
                i += 3
                continue
            if char not in WIRE_CHARS:
                raise ValueError('unsupported wire target')
            i += 1
    return '/' + http_path


def write_all(fd, data, write_fn=None):
    """Write every byte of data, refusing zero/invalid/overlarge progress."""
    if not is_int(fd) or fd < 0:
        raise ValueError('invalid descriptor')
    view = memoryview(data).cast('B')
    write_fn = os.write if write_fn is None else write_fn
    offset, total = 0, len(view)
    while offset < total:
        try:
            wrote = write_fn(fd, view[offset:])
        except InterruptedError:
            continue
        if not is_int(wrote) or wrote < 1 or wrote > total - offset:
            raise OSError('invalid write progress')
        offset += wrote
    return total


def transfer(response, fd, *, body_cap, aggregate_left, deadline, clock=None, write_fn=None):
    """Bounded body transfer; storage errors propagate as OSError."""
    for limit in (body_cap, aggregate_left):
        if not is_int(limit) or limit < 0:
            raise ValueError('invalid limit')
    if isinstance(deadline, bool) or not isinstance(deadline, (int, float)) or not math.isfinite(deadline):
        raise ValueError('invalid deadline')
    if not is_int(fd) or fd < 0 or not callable(getattr(response, 'read1', None)) or not hasattr(response, 'length'):
        raise ValueError('invalid transfer arguments')
    clock = time.monotonic if clock is None else clock
    if not callable(clock) or (write_fn is not None and not callable(write_fn)):
        raise ValueError('invalid transfer arguments')
    initial_length = response.length
    if initial_length is not None and (not is_int(initial_length) or initial_length < 0):
        raise ValueError('invalid transfer arguments')
    digest, count, outcome = hashlib.sha256(), 0, None
    while outcome is None:
        length = response.length
        if length is not None and (not is_int(length) or length < 0):
            outcome = 'transport_error'
        elif length == 0:
            outcome = 'complete'
        elif length is not None and count + length > body_cap:
            outcome = 'declared_over_cap'
        elif clock() >= deadline:
            outcome = 'deadline'
        elif aggregate_left - count <= 0:
            outcome = 'aggregate_cap'
        elif body_cap - count <= 0:
            outcome = 'cap_unresolved_eof'
        else:
            want = min(READ_MAX, body_cap - count, aggregate_left - count)
            if length is not None:
                want = min(want, length)
            try:
                chunk = response.read1(want)
            except Exception:
                outcome = 'transport_error'
                break
            if not isinstance(chunk, (bytes, bytearray)) or len(chunk) > want:
                outcome = 'transport_error'
            elif not chunk:
                outcome = 'complete' if length is None else 'transport_error'
            else:
                write_all(fd, chunk, write_fn)
                digest.update(chunk)
                count += len(chunk)
    done = outcome == 'complete'
    hexdigest = digest.hexdigest()
    return {'outcome': outcome, 'bytes': count, 'response_complete': done,
            'complete_sha256': hexdigest if done else None, 'partial_sha256': None if done else hexdigest,
            'late': clock() >= deadline}


def inspect_signature(kind, prefix):
    """Fixed-prefix magic check only; never parsing or a version allowlist."""
    if kind not in SIGNATURES or not isinstance(prefix, (bytes, bytearray, memoryview)):
        raise ValueError('invalid signature arguments')
    minimum, width, magics = SIGNATURES[kind]
    kept = bytes(memoryview(prefix).cast('B')[:minimum])
    if len(kept) < minimum:
        state = 'short'
    else:
        state = 'match' if kept[:width] in magics else 'mismatch'
    return {'state': state, 'prefix_hex': kept.hex()}


# ---------------------------------------------------------------- admission

def check_ancestors(path):
    """Every ancestor of the absolute normalized path is a real directory."""
    require(isinstance(path, str) and os.path.isabs(path) and os.path.normpath(path) == path, 'path_shape')
    parts = path.split('/')[1:-1]
    current = '/'
    for part in parts:
        current = os.path.join(current, part)
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            raise Absent()
        except OSError:
            raise Refusal('ancestor_error')
        require(stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode), 'ancestor_link')


def relative(base, rel):
    require(isinstance(rel, str) and rel and not rel.startswith('/') and '\\' not in rel and '\0' not in rel, 'relative_path')
    require(all(part not in ('', '.', '..') for part in rel.split('/')), 'relative_path')
    return os.path.join(base, rel)


def read_admitted(path, expected_bytes=None, expected_sha=None, keep=True, limit=None):
    """Stable regular-file read; returns (data or None, receipt)."""
    check_ancestors(path)
    try:
        first = os.lstat(path)
    except FileNotFoundError:
        raise Absent()
    except OSError:
        raise Refusal('admit_stat')
    require(stat.S_ISREG(first.st_mode), 'admit_regular')
    size = first.st_size
    require(expected_bytes is None or size == expected_bytes, 'admit_size')
    require(limit is None or size <= limit, 'admit_limit')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise Refusal('admit_open')
    try:
        opened = os.fstat(fd)
        require(identity(opened) == identity(first) and stat.S_ISREG(opened.st_mode), 'admit_drift')
        digest, chunks, left = hashlib.sha256(), [], size
        while left:
            chunk = os.read(fd, min(HASH_CHUNK, left))
            require(bool(chunk), 'admit_truncated')
            digest.update(chunk)
            if keep:
                chunks.append(chunk)
            left -= len(chunk)
        require(os.read(fd, 1) == b'', 'admit_grew')
        after = os.fstat(fd)
    finally:
        os.close(fd)
    try:
        last = os.lstat(path)
    except OSError:
        raise Refusal('admit_drift')
    require(identity(after) == identity(first) == identity(last), 'admit_drift')
    hexdigest = digest.hexdigest()
    require(expected_sha is None or hexdigest == expected_sha, 'admit_sha')
    receipt = {'bytes': size, 'sha256': hexdigest, 'identity': identity(first)}
    return (b''.join(chunks) if keep else None), receipt


def strict_json(data):
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'json_duplicate')
            out[key] = value
        return out

    def constant(_):
        raise Refusal('json_nonfinite')
    try:
        return json.loads(data.decode('utf-8'), object_pairs_hook=pairs, parse_constant=constant)
    except (UnicodeDecodeError, ValueError):
        raise Refusal('json_invalid')


def http_from_name(name):
    """FileManager.getHTTP: UTF-8 encodeURIComponent per non-slash segment."""
    slashed = name.replace('\\', '/')
    try:
        return '/'.join(quote(part, safe="-_.!~*'()", encoding='utf-8', errors='strict') for part in slashed.split('/'))
    except UnicodeError:
        raise Refusal('name_encoding')


def target_kind(name):
    base = name.replace('\\', '/').rsplit('/', 1)[-1]
    require('.' in base, 'target_kind')
    kind = KINDS.get(base.rsplit('.', 1)[1])
    require(kind is not None, 'target_kind')
    return kind


def validate_catalog(catalog, profile, prior_pin):
    counts = profile['expected_counts']
    require(isinstance(catalog, dict), 'catalog_shape')
    require(catalog.get('schema') == 'T06-map-dependency-catalog-1' and catalog.get('task') == 'T06.003.003.004'
            and catalog.get('mode') == 'corpus', 'catalog_identity')
    require(catalog.get('profile_sha256') == prior_pin['sha256'], 'catalog_profile_binding')
    require(catalog.get('counts') == counts, 'catalog_counts')
    pins = {p['path']: p for p in profile['source_pins']}
    for rel, pin in catalog.get('rule_sources', {}).items():
        mine = pins.get('.tools/renewal/client-source/' + rel)
        if mine is not None:
            require(pin == {'bytes': mine['bytes'], 'sha256': mine['sha256']}, 'catalog_rule_source')
    require(all(('.tools/renewal/client-source/' + r) in pins for r in ('src/Loaders/MapLoader.js', 'src/Core/FileManager.js')), 'catalog_rule_source')
    roots, jobs, targets = catalog.get('roots'), catalog.get('jobs'), catalog.get('targets')
    require(isinstance(roots, list) and isinstance(jobs, list) and isinstance(targets, list), 'catalog_shape')
    gaps = profile['remaining_gap_root_ordinals']
    require(catalog.get('remaining_gap_root_ordinals') == gaps and len(gaps) == counts['remaining_gap_roots'], 'catalog_gaps')
    require(len(roots) == counts['roots'] and [r.get('ordinal') for r in roots] == list(range(len(roots))), 'catalog_roots')
    gap_set = set(gaps)
    require(all((r.get('combined_observation') == 'gap') == (r['ordinal'] in gap_set) for r in roots), 'catalog_root_gaps')
    require(len(jobs) == counts['jobs'], 'catalog_jobs')
    job_ids = {}
    for index, job in enumerate(jobs):
        require(isinstance(job, dict) and job.get('source_row_index') == index and job.get('id') not in job_ids, 'catalog_job')
        require(job.get('kind') in JOB_ROLES and job.get('role') == JOB_ROLES[job['kind']], 'catalog_job_role')
        job_ids[job['id']] = index
    kinds = {k: sum(j['kind'] == k for j in jobs) for k in ('rsw', 'gnd', 'gat')}
    require(kinds == counts['job_kinds'], 'catalog_job_kinds')
    # Root edge <-> job root_reference bidirectionality.
    edge_refs = set()
    for root in roots:
        for edge_kind, edge in root.get('edges', {}).items():
            if edge.get('job_id') is not None:
                require(edge['job_id'] in job_ids and jobs[job_ids[edge['job_id']]]['kind'] == edge_kind, 'catalog_edge')
                edge_refs.add((job_ids[edge['job_id']], root['ordinal'], edge_kind))
    job_refs = set()
    for index, job in enumerate(jobs):
        for ref in job.get('root_references', []):
            key = (index, ref.get('root_ordinal'), ref.get('edge_kind'))
            require(key not in job_refs, 'catalog_root_reference')
            job_refs.add(key)
    require(edge_refs == job_refs and len(job_refs) == counts['root_edge_references'], 'catalog_root_references')
    require(len(targets) == counts['http_targets'] and [t.get('index') for t in targets] == list(range(len(targets))), 'catalog_targets')
    seen_http = set()
    for t in targets:
        require(isinstance(t.get('http_path'), str) and t['http_path'] not in seen_http and isinstance(t.get('referrers'), list), 'catalog_target')
        seen_http.add(t['http_path'])
    occ = {'model': 0, 'ground_texture': 0}
    exp_occ = {'model': 0, 'ground_texture': 0}
    entries = {'model': 0, 'ground_texture': 0}
    exp_entries = {'model': 0, 'ground_texture': 0}
    names = {r: {f: set() for f in ('raw', 'logical', 'filemanager', 'http')} for r in occ}
    forward = set()
    for job_index, job in enumerate(jobs):
        role = job['role']
        loaders = job.get('loader_entries', [])
        if role is None:
            require(not loaders and not job.get('occurrence_loader_indexes'), 'catalog_gat_entries')
            continue
        require(isinstance(loaders, list), 'catalog_loader')
        refs = len(job.get('root_references', []))
        indexes = job.get('occurrence_loader_indexes', [])
        require(all(is_int(i) and 0 <= i < len(loaders) for i in indexes), 'catalog_occurrence')
        occ[role] += len(indexes)
        exp_occ[role] += len(indexes) * refs
        entries[role] += len(loaders)
        exp_entries[role] += len(loaders) * refs
        for position, entry in enumerate(loaders):
            require(entry.get('index') == position, 'catalog_loader_index')
            t = entry.get('target_index')
            require(is_int(t) and 0 <= t < len(targets) and targets[t]['http_path'] == entry.get('http_path'), 'catalog_loader_target')
            for field in ('raw', 'logical', 'filemanager', 'http'):
                value = entry.get(field + '_path' if field == 'http' else field + '_name')
                require(isinstance(value, str), 'catalog_loader_name')
                names[role][field].add(value)
            forward.add((t, job_index, position, role))
    require(occ == counts['occurrences'] and exp_occ == counts['root_expanded_occurrences'], 'catalog_occurrences')
    require(entries == counts['loader_entries'] and exp_entries == counts['root_expanded_loader_entries'], 'catalog_loader_entries')
    distinct = {r: {f: len(v) for f, v in names[r].items()} for r in names}
    require(distinct == counts['distinct_names_by_role'], 'catalog_distinct')
    backward, plans, referrers = set(), [], 0
    for t in targets:
        require(t['referrers'], 'catalog_referrers')
        first, roles = None, set()
        for ref in t['referrers']:
            key = (t['index'], ref.get('job_index'), ref.get('loader_index'), ref.get('role'))
            require(key not in backward and key in forward, 'catalog_referrer')
            backward.add(key)
            entry = jobs[key[1]]['loader_entries'][key[2]]
            slashed = entry['filemanager_name'].replace('\\', '/')
            first = slashed if first is None else first
            require(slashed == first, 'catalog_filemanager_disagree')
            roles.add(key[3])
        referrers += len(t['referrers'])
        require(len(roles) == 1, 'catalog_target_role')
        require(http_from_name(first) == t['http_path'], 'catalog_http_reconstruct')
        kind = target_kind(first)
        require(kind in ROLE_KINDS[roles.pop()], 'catalog_kind_role')
        try:
            wire = wire_target(t['http_path'])
        except ValueError:
            raise Refusal('catalog_wire')
        plans.append({'index': t['index'], 'http_path': t['http_path'], 'wire': wire, 'kind': kind})
    require(backward == forward and referrers == sum(counts['loader_entries'].values()), 'catalog_bidirectional')
    return plans, referrers


def load_metadata(input_root, profile_path):
    """Metadata-only admission. Never touches native inputs, processes or HTTP."""
    require(isinstance(input_root, str) and os.path.isabs(input_root), 'input_root')
    input_root = os.path.normpath(input_root)
    try:
        check_ancestors(os.path.join(input_root, 'x'))
    except Absent:
        raise Refusal('input_root')
    profile_path = os.path.normpath(os.path.abspath(profile_path))
    profile_bytes, profile_receipt = read_admitted(profile_path, PROFILE_BYTES, PROFILE_SHA)
    profile = strict_json(profile_bytes)
    require(profile.get('schema') == PROFILE_SCHEMA and profile.get('task') == TASK, 'profile_identity')
    require(profile.get('policy') == POLICY, 'profile_policy')
    require([n.get('name') for n in profile.get('native', [])] == NATIVE_NAMES, 'profile_native')
    require(all(n.get('base') in ('home', 'input_root') for n in profile['native']), 'profile_native')
    require(len(profile.get('source_pins', [])) == 16, 'profile_sources')
    authored_pin = profile['authored']
    authored_bytes, authored_receipt = read_admitted(relative(input_root, authored_pin['path']),
                                                     authored_pin['bytes'], authored_pin['sha256'])
    authored = strict_json(authored_bytes)
    require(authored.get('schema') == AUTHORED_SCHEMA and authored.get('status') == 'FROZEN_ROOT_REVIEWED', 'authored_identity')
    sources = []
    for pin in profile['source_pins']:
        _, receipt = read_admitted(relative(input_root, pin['path']), pin['bytes'], pin['sha256'], keep=False)
        sources.append(dict(path=pin['path'], **receipt))
    prior = [p for p in profile['source_pins'] if p['path'] == PRIOR_PROFILE_PATH]
    require(len(prior) == 1, 'profile_prior_binding')
    cpin = profile['catalog']
    require(cpin['bytes'] <= POLICY['catalog_bytes'], 'catalog_limit')
    catalog_bytes, catalog_receipt = read_admitted(relative(input_root, cpin['path']), cpin['bytes'], cpin['sha256'])
    catalog = strict_json(catalog_bytes)
    plans, referrers = validate_catalog(catalog, profile, prior[0])
    return {'input_root': input_root, 'profile_path': profile_path, 'profile': profile,
            'profile_receipt': profile_receipt, 'authored_receipt': authored_receipt,
            'sources': sources, 'catalog_bytes': catalog_bytes, 'catalog_receipt': catalog_receipt,
            'catalog_path': relative(input_root, cpin['path']), 'catalog': catalog, 'plans': plans,
            'referrers': referrers, 'gaps': list(profile['remaining_gap_root_ordinals'])}


def native_specs(meta):
    home = os.path.normpath(os.path.expanduser('~'))
    require(os.path.isabs(home), 'home')
    out = []
    for item in meta['profile']['native']:
        base = home if item['base'] == 'home' else meta['input_root']
        out.append({'name': item['name'], 'path': relative(base, item['path']), 'bytes': item['bytes'], 'sha256': item['sha256']})
    return out


def own_sha():
    path = os.path.normpath(os.path.abspath(__file__))
    _, receipt = read_admitted(path, keep=False)
    return receipt


# ---------------------------------------------------------------- execute

class SystemOps:
    """The only process/network/disk effects of execute; replaced by fakes in tests."""
    clock = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)

    def free_bytes(self, path):
        st = os.statvfs(path)
        return st.f_bavail * st.f_frsize

    def fresh_port(self):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(('127.0.0.1', 0))
            return sock.getsockname()[1]

    def popen(self, argv, cwd, env):
        return subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                stderr=subprocess.DEVNULL, start_new_session=True, close_fds=True, umask=0o077)

    def getpgid(self, pid):
        return os.getpgid(pid)

    def _lsof(self, args):
        result = subprocess.run(['/usr/sbin/lsof', '-nP'] + args, stdin=subprocess.DEVNULL,
                                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5)
        require(result.returncode in (0, 1), 'lsof_unknown')
        lines = result.stdout.decode('ascii', 'strict').splitlines()
        require(result.returncode == 0 or not lines, 'lsof_unknown')
        return lines

    def owned_listener(self, pid, port):
        lines = self._lsof(['-a', '-p', str(pid), '-iTCP:%d' % port, '-sTCP:LISTEN', '-Fpn'])
        names = {line for line in lines if line.startswith('n')}
        return ('p%d' % pid) in lines and names == {'n127.0.0.1:%d' % port}

    def port_listeners(self, port):
        return bool(self._lsof(['-iTCP:%d' % port, '-sTCP:LISTEN', '-Fp']))

    def group_members(self, pgid):
        out = subprocess.run(['/bin/ps', '-axo', 'pid=,pgid='], stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                             stderr=subprocess.DEVNULL, timeout=5, check=True).stdout.decode('ascii', 'strict')
        members = []
        for line in out.splitlines():
            parts = line.split()
            require(len(parts) == 2, 'ps_unknown')
            if int(parts[1]) == pgid:
                members.append(int(parts[0]))
        return members

    def connect(self, port, timeout):
        return http.client.HTTPConnection('127.0.0.1', port, timeout=timeout)


class Fatal(Exception):
    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class _Metered:
    """Counts wire bytes before storage and refreshes the socket I/O timeout."""

    def __init__(self, response, refresh):
        self._response, self._refresh, self.wire = response, refresh, 0
        self.complete = response.length == 0

    @property
    def length(self):
        return self._response.length

    def read1(self, n):
        self._refresh()
        try:
            chunk = self._response.read1(n)
        except http.client.IncompleteRead as exc:
            self.wire += len(exc.partial)
            self.complete = False
            raise
        if isinstance(chunk, (bytes, bytearray)):
            self.wire += len(chunk)
            self.complete = self.length == 0 or (not chunk and self.length is None)
        return chunk


def unattempted(plan, reason):
    return {'target_index': plan['index'], 'attempted': False, 'request_index': None, 'wire_target': plan['wire'],
            'started_elapsed_seconds': None, 'finished_elapsed_seconds': None, 'http_status': None, 'headers': None,
            'wire_bytes': 0, 'wire_complete': False, 'stop_reason': reason,
            'stored': {'file': None, 'bytes': None, 'sha256': None, 'complete': False, 'error': None},
            'signature': {'kind': plan['kind'], 'state': 'not_checked', 'prefix_hex': None}}


class Observer:
    def __init__(self, meta, output, driver, ops=None, natives=None, policy=None, container=None, write_fn=None):
        self.meta, self.output, self.driver = meta, output, driver
        self.ops = ops or SystemOps()
        self.natives = natives if natives is not None else native_specs(meta)
        self.policy = dict(POLICY if policy is None else policy)
        self.container = str(CONTAINER) if container is None else container
        self.write_fn = write_fn
        self.proc, self.port, self.epoch, self.deadline = None, None, None, None
        self.halt, self.errors, self.created, self.request_index = None, [], False, 0
        self.wire_total, self.stored_total, self.asset_attempts, self.health_attempts = 0, 0, 0, 0
        self.stored_unknown = False
        self.body_files, self.native_before = [], {}
        self.output_created = False
        plans = meta['plans']
        self.report = {
            'schema': SCHEMA, 'task': TASK, 'mode': 'execute',
            'driver_pin': {'bytes': driver['bytes'], 'sha256': driver['sha256']},
            'profile_pin': {'bytes': meta['profile_receipt']['bytes'], 'sha256': meta['profile_receipt']['sha256']},
            'authored_pin': {'bytes': meta['authored_receipt']['bytes'], 'sha256': meta['authored_receipt']['sha256']},
            'catalog_pin': {'bytes': meta['catalog_receipt']['bytes'], 'sha256': meta['catalog_receipt']['sha256']},
            'catalog_refs': {'file': 'catalog-input.json', 'roots_pointer': '/roots', 'targets_pointer': '/targets',
                             'roots': len(meta['catalog']['roots']), 'targets': len(plans),
                             'referrers': meta['referrers'], 'gap_root_ordinals': meta['gaps']},
            'native_before': None, 'native_after': None,
            'sources_before': self._source_receipts(meta), 'sources_after': None,
            'launch': None, 'health': None, 'totals': None,
            'targets': [unattempted(p, 'not_started') for p in plans],
            'missing_log': None, 'tree': None, 'cleanup': None, 'coverage_counts': None,
            'halt_reason': None, 'errors': self.errors, 'records_complete': False,
            'all_targets_attempted': False, 'acquisition_and_cleanup_valid': False,
            'limitations': list(meta['profile']['limitations'])}

    @staticmethod
    def _source_receipts(meta):
        return {'profile': meta['profile_receipt'], 'authored': meta['authored_receipt'],
                'catalog': meta['catalog_receipt'], 'sources': meta['sources']}

    # -- elapsed/clock
    def elapsed(self):
        return None if self.epoch is None else round(self.ops.clock() - self.epoch, 6)

    def remaining_io(self):
        left = self.deadline - self.ops.clock()
        if left <= 0:
            raise Fatal('acquisition_deadline')
        return min(self.policy['io_seconds'], left)

    def fail(self, reason, detail=None):
        if self.halt is None:
            self.halt = reason
        if detail:
            self.errors.append(detail)

    # -- private file writes
    def path(self, rel):
        return os.path.join(self.output, rel)

    def create_private(self, rel, data):
        fd = os.open(self.path(rel), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(fd, 0o600)
            write_all(fd, data)
        finally:
            os.close(fd)
        _, receipt = read_admitted(self.path(rel), len(data), sha(data), keep=False)
        return receipt

    def checkpoint(self):
        self.report['totals'] = self.totals()
        self.report['halt_reason'] = self.halt
        data = (json.dumps(self.report, ensure_ascii=True, sort_keys=True, allow_nan=False) + '\n').encode('ascii')
        if len(data) > self.policy['report_bytes']:
            raise Fatal('report_too_large')
        temporary = self.path('.report-next')
        try:
            self.create_private('.report-next', data)
            os.replace(temporary, self.path('report.json'))
            read_admitted(self.path('report.json'), len(data), sha(data), keep=False)
        except (OSError, Refusal, Absent):
            try:
                os.unlink(temporary)
            except OSError:
                pass
            raise Fatal('publication_failure')

    def totals(self):
        return {'asset_attempts': self.asset_attempts, 'health_attempts': self.health_attempts,
                'wire_bytes': self.wire_total, 'stored_bytes': None if self.stored_unknown else self.stored_total,
                'elapsed_seconds': self.elapsed()}

    # -- admission and setup
    def admit_output(self):
        output, container = self.output, self.container
        require(isinstance(output, str) and os.path.isabs(output) and os.path.normpath(output) == output, 'output_shape')
        require(output.startswith(container + '/'), 'output_container')
        parent = os.path.dirname(output)
        check_ancestors(os.path.join(container, 'x'))
        current = container
        for part in [''] + os.path.relpath(parent, container).split('/'):
            current = os.path.normpath(os.path.join(current, part))
            st = os.lstat(current)
            require(stat.S_ISDIR(st.st_mode) and st.st_uid == os.getuid() and stat.S_IMODE(st.st_mode) in (0o700, 0o755), 'output_container_mode')
        try:
            os.lstat(output)
            raise Refusal('output_exists')
        except FileNotFoundError:
            pass
        need = DISK_WORKING_BYTES + self.policy['disk_reserve_bytes']
        require(self.ops.free_bytes(parent) >= need, 'disk_free')

    def create_output(self):
        os.mkdir(self.output, 0o700)
        self.output_created = True
        os.chmod(self.output, 0o700)
        os.mkdir(self.path('resources'), 0o700)
        os.chmod(self.path('resources'), 0o700)
        self.create_private('catalog-input.json', self.meta['catalog_bytes'])
        self.checkpoint()  # Every target is prefilled before native access.

    def hash_natives(self):
        out = {}
        for spec in self.natives:
            _, receipt = read_admitted(spec['path'], spec['bytes'], spec['sha256'], keep=False)
            out[spec['name']] = dict(receipt, name=spec['name'])
        return out

    def environment(self):
        port, output = str(self.port), self.output
        return {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'SERVER_ROOT': output, 'PORT': port, 'HOST': '127.0.0.1',
                'NODE_ENV': 'production', 'CLIENT_PUBLIC_URL': 'http://127.0.0.1:' + port, 'CLIENT_RESPATH': 'resources/',
                'CLIENT_DATAINI': os.path.join(output, 'resources/DATA.INI'), 'ENABLE_STATIC_SERVE': 'false',
                'ENABLE_WSPROXY': 'false', 'ENABLE_COMPRESSION': 'false', 'CACHE_WARM_UP': 'false',
                'CLIENT_AUTOEXTRACT': 'false', 'CLIENT_ENABLESEARCH': 'false', 'GRF_FILENAME_ENCODING': 'auto',
                'CACHE_MAX_MEMORY_MB': str(self.policy['cache_mb']), 'CACHE_MAX_FILES': str(self.policy['cache_files'])}

    def launch(self):
        self.native_before = self.hash_natives()
        self.report['native_before'] = self.native_before
        by_name = {s['name']: s for s in self.natives}
        ini = '[Data]\n' + ''.join('%d=%s\n' % (i, by_name[n]['path']) for i, n in enumerate(NATIVE_NAMES[1:]))
        ini_receipt = self.create_private('resources/DATA.INI', ini.encode('utf-8'))
        self.port = self.ops.fresh_port()
        require(not self.ops.port_listeners(self.port), 'port_in_use')
        env = self.environment()
        self.proc = self.ops.popen([by_name['binary']['path']], self.output, env)
        pgid = self.ops.getpgid(self.proc.pid)
        self.report['launch'] = {'pid': self.proc.pid, 'pgid': pgid, 'port': self.port, 'environment': env,
                                 'profile_sha256': PROFILE_SHA, 'data_ini': {'bytes': ini_receipt['bytes'], 'sha256': ini_receipt['sha256']},
                                 'listener_proof': None}
        if pgid != self.proc.pid:
            raise Fatal('launch_identity')
        self.checkpoint()  # PID/PGID/port recorded before any request.
        ready_by = self.ops.clock() + self.policy['startup_seconds']
        while True:
            if self.proc.poll() is not None:
                raise Fatal('reader_exited_at_startup')
            if self.ops.clock() >= ready_by:
                raise Fatal('startup_timeout')
            owned = self.ops.owned_listener(self.proc.pid, self.port)
            if self.ops.clock() >= ready_by:
                raise Fatal('startup_timeout')
            if owned:
                break
            self.ops.sleep(0.2)
        self.report['launch']['listener_proof'] = {'owned_listener': True, 'host': '127.0.0.1', 'port': self.port}

    # -- one GET
    def request(self, wire, cap, record):
        """Perform at most one GET; returns transfer result or None. Fatal on storage/deadline/budget."""
        index = self.request_index
        self.request_index += 1
        name = '%06d' % index
        record.update(attempted=True, request_index=index, started_elapsed_seconds=self.elapsed())
        con = response = None
        fd = None
        result = None
        written = [0]

        def counted_write(target_fd, buffer):
            wrote = (self.write_fn or os.write)(target_fd, buffer)
            if is_int(wrote) and 0 < wrote <= len(buffer):
                written[0] += wrote
            return wrote
        metered = None
        try:
            try:
                con = self.ops.connect(self.port, self.remaining_io())
            except Fatal:
                raise
            except Exception:
                record['stop_reason'] = 'connection_setup_error'
                return None
            try:
                con.request('GET', wire, headers={'Accept-Encoding': 'identity'})
                if getattr(con, 'sock', None) is not None:
                    con.sock.settimeout(self.remaining_io())
                response = con.getresponse()
            except Fatal:
                raise
            except socket.timeout:
                record['stop_reason'] = 'timeout'
                return None
            except Exception:
                record['stop_reason'] = 'transport_error'
                return None
            record['http_status'] = response.status
            headers, malformed = {}, False
            for key, header in HEADER_NAMES:
                value = response.getheader(header)
                if value is not None and (not isinstance(value, str) or len(value.encode('utf-8', 'surrogateescape')) > HEADER_MAX):
                    value, malformed = None, True
                headers[key] = value
            record['headers'] = headers
            if malformed:
                record['stop_reason'] = 'malformed_header'
                return None
            encoding = headers['content_encoding']
            if encoding is not None and encoding.strip().lower() != 'identity':
                record['stop_reason'] = 'unsupported_encoding'
                return None
            fd = os.open(self.path(name), os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            self.body_files.append(name)
            record['stored']['file'] = name
            os.fchmod(fd, 0o600)
            metered = _Metered(response, lambda: con.sock.settimeout(self.remaining_io()) if getattr(con, 'sock', None) is not None else None)
            aggregate_left = max(0, self.policy['aggregate_bytes_including_health'] - self.wire_total)
            try:
                result = transfer(metered, fd, body_cap=cap, aggregate_left=aggregate_left, deadline=self.deadline,
                                  clock=self.ops.clock, write_fn=counted_write)
            except Fatal:
                raise
            except OSError:
                record['stored']['error'] = 'storage_error'
                record['stop_reason'] = 'storage_error'
                raise Fatal('storage_failure')
            record['wire_complete'] = result['response_complete']
            return result
        except Fatal as fatal:
            if fatal.reason == 'acquisition_deadline' and record.get('stop_reason') in (None, 'not_started'):
                record['stop_reason'] = 'deadline'
            raise
        finally:
            if metered is not None:
                record['wire_bytes'] = metered.wire
                record['wire_complete'] = metered.complete
                self.wire_total += metered.wire
            close_failed = False
            for closer in (response, con):
                if closer is not None:
                    try:
                        closer.close()
                    except Exception:
                        self.fail('resource_close_failure', 'http_close_error')
            if fd is not None:
                try:
                    os.close(fd)
                except OSError:
                    close_failed = True
                    record['stored']['error'] = 'storage_close_error'
            record['finished_elapsed_seconds'] = self.elapsed()
            if fd is not None:
                self.verify_stored(record, result, written[0])
            if close_failed:
                self.fail('storage_failure', 'storage_close_error')

    def verify_stored(self, record, result, written):
        stored = record['stored']
        try:
            data, receipt = read_admitted(self.path(stored['file']), keep=True, limit=self.policy['body_bytes'])
            st = os.lstat(self.path(stored['file']))
        except (Refusal, Absent, OSError):
            stored.update(bytes=None, sha256=None, complete=False, error=stored['error'] or 'verify_failed')
            self.stored_unknown = True
            self.fail('storage_failure', 'stored_verify_failed')
            return
        stored.update(bytes=receipt['bytes'], sha256=receipt['sha256'])
        good = (result is not None and stored['error'] is None and st.st_nlink == 1 and stat.S_IMODE(st.st_mode) == 0o600
                and receipt['bytes'] == result['bytes'] == written
                and receipt['sha256'] == (result['complete_sha256'] or result['partial_sha256']))
        stored['complete'] = bool(good and result['response_complete'])
        if result is not None and not good and stored['error'] is None:
            stored['error'] = 'stored_mismatch'
            self.fail('storage_failure', 'stored_mismatch')
        self.stored_total += receipt['bytes']
        record['_prefix'] = data[:6]

    def classify(self, record, result, kind):
        prefix = record.pop('_prefix', None)
        if result is None:
            return
        outcome, status = result['outcome'], record['http_status']
        if outcome != 'complete':
            record['stop_reason'] = outcome
        elif status == 200:
            ctype = (record['headers'] or {}).get('content_type') or ''
            if result['bytes'] == 0:
                record['stop_reason'] = 'empty_200'
            elif 'text/html' in ctype.lower():
                record['stop_reason'] = 'html_200'
            else:
                record['stop_reason'] = 'complete'
        elif status == 404:
            record['stop_reason'] = 'http_404'
        elif 300 <= status < 400:
            record['stop_reason'] = 'redirect'
        else:
            record['stop_reason'] = 'http_status'
        if kind is not None and status == 200 and record['stored']['complete'] and prefix is not None:
            record['signature'] = dict(inspect_signature(kind, prefix), kind=kind)
        if outcome == 'aggregate_cap':
            self.fail('aggregate_cap')
        elif outcome == 'deadline' or result['late']:
            self.fail('acquisition_deadline')

    def health(self):
        record = {'attempted': False, 'request_index': None, 'http_status': None, 'headers': None, 'wire_bytes': 0,
                  'wire_complete': False, 'stop_reason': None, 'started_elapsed_seconds': None, 'finished_elapsed_seconds': None,
                  'stored': {'file': None, 'bytes': None, 'sha256': None, 'complete': False, 'error': None},
                  'status_ok': False, 'service_ok': False, 'valid': False}
        self.report['health'] = record
        self.health_attempts += 1
        result = self.request('/api/health', self.policy['health_bytes'], record)
        prefix = record.pop('_prefix', None)
        del prefix
        if result is None or result['outcome'] != 'complete' or record['http_status'] != 200 or not record['stored']['complete']:
            if result is not None:
                record['stop_reason'] = result['outcome']
                if result['late']:
                    self.fail('acquisition_deadline')
            raise Fatal('health_failure')
        record['stop_reason'] = 'complete'
        data, _ = read_admitted(self.path(record['stored']['file']), record['stored']['bytes'], record['stored']['sha256'])
        try:
            body = strict_json(data)
        except Refusal:
            raise Fatal('health_failure')
        record['status_ok'] = isinstance(body, dict) and body.get('status') == 'ok'
        record['service_ok'] = isinstance(body, dict) and body.get('service') == 'robrowser-remoteclient'
        record['valid'] = record['status_ok'] and record['service_ok']
        if result['late']:
            raise Fatal('acquisition_deadline')
        if not record['valid']:
            raise Fatal('health_failure')

    def scan(self):
        plans, targets = self.meta['plans'], self.report['targets']
        for position, plan in enumerate(plans):
            if self.halt:
                break
            if self.ops.clock() >= self.deadline:
                self.fail('acquisition_deadline')
                break
            if self.wire_total >= self.policy['aggregate_bytes_including_health']:
                self.fail('aggregate_cap')
                break
            if self.asset_attempts >= self.policy['asset_attempts']:
                self.fail('asset_attempt_cap')
                break
            if self.proc.poll() is not None:
                self.fail('reader_lost')
                break
            record = targets[position]
            record['stop_reason'] = None
            self.asset_attempts += 1
            try:
                result = self.request(plan['wire'], self.policy['body_bytes'], record)
            except Fatal as fatal:
                record.pop('_prefix', None)
                self.fail(fatal.reason)
                break
            self.classify(record, result, plan['kind'])
            if record['stop_reason'] in ('connection_setup_error', 'transport_error', 'timeout'):
                if self.proc.poll() is not None or not self.ops.owned_listener(self.proc.pid, self.port):
                    self.fail('reader_lost')
            if (position + 1) % CHECKPOINT_EVERY == 0:
                self.checkpoint()
        if self.ops.clock() >= self.deadline:
            self.fail('acquisition_deadline')

    # -- shutdown and audits
    def shutdown(self):
        cleanup = {'listener_before_shutdown': None, 'terminated': False, 'forced_kill': False, 'exit_code': None,
                   'listener_absent': None, 'group_members_after': None, 'error': None, 'clean': False}
        self.report['cleanup'] = cleanup
        if self.proc is None:
            cleanup.update(listener_absent=True, group_members_after=[], clean=True)
            if self.port is not None:
                cleanup['listener_absent'] = not self.ops.port_listeners(self.port)
            return
        try:
            if self.proc.poll() is None:
                try:
                    cleanup['listener_before_shutdown'] = self.ops.owned_listener(self.proc.pid, self.port)
                except Exception as exc:
                    cleanup['error'] = 'listener_' + type(exc).__name__
                self.proc.terminate()  # Only the owned Popen child; never by name/port.
                cleanup['terminated'] = True
                try:
                    self.proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    cleanup['forced_kill'] = True
                    self.proc.kill()
                    self.proc.wait(timeout=8)
            else:
                cleanup['listener_before_shutdown'] = False
            cleanup['exit_code'] = self.proc.poll()
            cleanup['listener_absent'] = not self.ops.port_listeners(self.port)
            cleanup['group_members_after'] = self.ops.group_members(self.report['launch']['pgid'])
        except Exception as exc:
            cleanup['error'] = type(exc).__name__
        cleanup['clean'] = bool(cleanup['error'] is None and not cleanup['forced_kill'] and cleanup['exit_code'] == 0
                                and cleanup['listener_before_shutdown'] is True
                                and cleanup['listener_absent'] is True and cleanup['group_members_after'] == [])

    def audit_missing_log(self):
        expected = [unquote(self.meta['plans'][r['target_index']]['http_path'], encoding='utf-8', errors='strict')
                    for r in self.report['targets'] if r['http_status'] == 404]
        audit = {'present': False, 'bytes': None, 'sha256': None, 'entries': None, 'expected_404': len(expected), 'valid': False, 'error': None}
        self.report['missing_log'] = audit
        path = self.path('logs/missing-files.log')
        try:
            st = os.lstat(path)
        except FileNotFoundError:
            audit['valid'] = not expected
            if expected:
                audit['error'] = 'absent_with_404'
            return
        except OSError:
            audit['error'] = 'stat_error'
            return
        audit['present'] = True
        try:
            require(stat.S_ISREG(st.st_mode) and st.st_nlink == 1 and stat.S_IMODE(st.st_mode) == 0o600
                    and st.st_uid == os.getuid(), 'log_mode')
            data, receipt = read_admitted(path, limit=self.policy['missing_log_bytes'])
            audit.update(bytes=receipt['bytes'], sha256=receipt['sha256'])
            require(data == b'' or data.endswith(b'\n'), 'log_final_lf')
            lines = data.split(b'\n')[:-1] if data else []
            seen = []
            for line in lines:
                pairs = []
                json.loads(line.decode('utf-8'), object_pairs_hook=lambda items: pairs.append(items) or dict(items),
                           parse_constant=lambda _: (_ for _ in ()).throw(ValueError()))
                require(len(pairs) == 1 and [k for k, _ in pairs[0]] == ['timestamp', 'requestedPath', 'grfPath', 'mappedPath'], 'log_fields')
                entry = dict(pairs[0])
                stamp = entry['timestamp']
                require(isinstance(stamp, str) and len(stamp) == 24 and TIMESTAMP.match(stamp), 'log_timestamp')
                datetime.datetime.strptime(stamp, '%Y-%m-%dT%H:%M:%S.%fZ')
                require(isinstance(entry['requestedPath'], str) and entry['grfPath'] == entry['requestedPath'].replace('/', '\\')
                        and entry['mappedPath'] is None, 'log_relationship')
                seen.append(entry['requestedPath'])
            audit['entries'] = len(seen)
            require(len(set(seen)) == len(seen) and seen == expected, 'log_paths')
            audit['valid'] = True
        except (Refusal, Absent, ValueError, UnicodeError) as exc:
            audit['error'] = exc.args[0] if isinstance(exc, Refusal) and exc.args else 'log_invalid'

    def audit_tree(self):
        allowed_files = {'catalog-input.json', 'report.json', 'resources/DATA.INI', 'logs/missing-files.log'}
        require(all(NUMERIC.match(name) for name in self.body_files), 'body_name')
        allowed_files.update(self.body_files)
        audit = {'unexpected': [], 'bad_mode': [], 'missing': [], 'valid': False, 'error': None}
        self.report['tree'] = audit
        try:
            root = os.lstat(self.output)
            if not stat.S_ISDIR(root.st_mode) or stat.S_IMODE(root.st_mode) != 0o700 or root.st_uid != os.getuid():
                audit['bad_mode'].append('.')
            stack, found = [''], set()
            while stack:
                rel = stack.pop()
                with os.scandir(self.path(rel) if rel else self.output) as entries:
                    for entry in entries:
                        child = entry.name if not rel else rel + '/' + entry.name
                        st = entry.stat(follow_symlinks=False)
                        if stat.S_ISDIR(st.st_mode):
                            if child not in ('resources', 'logs'):
                                audit['unexpected'].append(child)
                                continue
                            if stat.S_IMODE(st.st_mode) != 0o700 or st.st_uid != os.getuid():
                                audit['bad_mode'].append(child)
                            stack.append(child)
                        elif stat.S_ISREG(st.st_mode) and child in allowed_files:
                            found.add(child)
                            if stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1 or st.st_uid != os.getuid():
                                audit['bad_mode'].append(child)
                        else:
                            audit['unexpected'].append(child)
            audit['missing'] = sorted({'catalog-input.json', 'report.json', 'resources/DATA.INI', *self.body_files} - found)
            audit['unexpected'].sort()
            audit['bad_mode'].sort()
            _, receipt = read_admitted(self.path('catalog-input.json'), self.meta['catalog_receipt']['bytes'],
                                       self.meta['catalog_receipt']['sha256'], keep=False)
            audit['catalog_copy_exact'] = True
            audit['valid'] = not (audit['unexpected'] or audit['bad_mode'] or audit['missing'])
        except (OSError, Refusal, Absent) as exc:
            audit['error'] = type(exc).__name__

    def postchecks(self):
        ok = True
        try:
            after = self.hash_natives()
            self.report['native_after'] = after
            ok = after == self.native_before and len(after) == 4
        except (Refusal, Absent):
            self.report['native_after'] = None
            ok = False
        try:
            meta = load_metadata(self.meta['input_root'], self.meta['profile_path'])
            receipts = self._source_receipts(meta)
            self.report['sources_after'] = receipts
            ok = ok and receipts == self.report['sources_before']
            driver = own_sha()
            ok = ok and driver == self.driver
        except (Refusal, Absent):
            self.report['sources_after'] = None
            ok = False
        return ok

    def coverage(self):
        counts = {'transfer': {}, 'stop_reason': {}, 'signature': {}, 'stored_complete': 0, 'storage_error': 0,
                  'complete_200_matching_prefix': 0, 'http_404': 0, 'other_http': 0, 'redirect': 0,
                  'cap': 0, 'transport': 0, 'unattempted': 0, 'attempted': 0}
        for r in self.report['targets']:
            counts['stop_reason'][r['stop_reason']] = counts['stop_reason'].get(r['stop_reason'], 0) + 1
            sig = r['signature']['kind'] + ':' + r['signature']['state']
            counts['signature'][sig] = counts['signature'].get(sig, 0) + 1
            if not r['attempted']:
                counts['unattempted'] += 1
                continue
            counts['attempted'] += 1
            counts['stored_complete'] += r['stored']['complete']
            counts['storage_error'] += r['stored']['error'] is not None
            if r['stop_reason'] in OUTCOMES or r['stop_reason'] in ('complete', 'http_404', 'redirect', 'http_status', 'empty_200', 'html_200'):
                key = r['stop_reason'] if r['stop_reason'] in OUTCOMES else 'complete'
                counts['transfer'][key] = counts['transfer'].get(key, 0) + 1
            status = r['http_status']
            if status == 404:
                counts['http_404'] += 1
            elif status is not None and status != 200:
                counts['other_http'] += 1
                counts['redirect'] += 300 <= status < 400
            if r['stop_reason'] == 'complete' and r['signature']['state'] == 'match':
                counts['complete_200_matching_prefix'] += 1
            counts['cap'] += r['stop_reason'] in ('declared_over_cap', 'cap_unresolved_eof')
            counts['transport'] += r['stop_reason'] in ('transport_error', 'timeout', 'connection_setup_error', 'malformed_header')
        return counts

    def run(self):
        """Returns exit status: 0 qualified, 1 retained failure, 2 refusal before output."""
        try:
            self.admit_output()
        except (Refusal, Absent, OSError):
            return 2
        try:
            self.create_output()
        except BaseException as exc:
            self.fail('publication_failure', 'setup_' + type(exc).__name__)
            return 1
        try:
            self.launch()
            self.epoch = self.ops.clock()
            self.deadline = self.epoch + self.policy['acquisition_seconds']
            self.health()
            self.scan()
            if not self.halt and not (self.proc.poll() is None and self.ops.owned_listener(self.proc.pid, self.port)):
                self.fail('reader_lost')
            if self.deadline is not None and self.ops.clock() >= self.deadline:
                self.fail('acquisition_deadline')
        except Fatal as fatal:
            self.fail(fatal.reason)
        except (Refusal, Absent) as exc:
            self.fail('admission_failure', exc.args[0] if exc.args else 'absent')
        except BaseException as exc:
            self.fail('internal_failure', type(exc).__name__)
        finally:
            if self.halt:
                try:
                    self.checkpoint()  # Halt checkpoint before shutdown.
                except Fatal:
                    self.fail('publication_failure')
            self.shutdown()
        reason = self.halt or 'not_started'
        for record in self.report['targets']:
            if not record['attempted']:
                record.update(unattempted(self.meta['plans'][record['target_index']], reason))
            elif record['stop_reason'] is None:
                record['stop_reason'] = reason
        post_ok = self.postchecks()
        self.audit_missing_log()
        self.audit_tree()
        targets = self.report['targets']
        self.report['coverage_counts'] = self.coverage()
        self.report['records_complete'] = len(targets) == len(self.meta['plans']) and all(
            r['stop_reason'] is not None and (r['attempted'] or r['request_index'] is None) for r in targets)
        self.report['all_targets_attempted'] = all(r['attempted'] for r in targets)
        health = self.report['health'] or {}
        self.report['postchecks_valid'] = post_ok
        self.report['acquisition_and_cleanup_valid'] = bool(
            self.halt is None and self.report['all_targets_attempted'] and self.report['records_complete']
            and health.get('valid') and post_ok and self.report['cleanup']['clean']
            and self.report['missing_log']['valid'] and self.report['tree']['valid'])
        self.report['halt_reason'] = self.halt
        try:
            self.checkpoint()
        except Fatal:
            self.fail('publication_failure')
            self.report['acquisition_and_cleanup_valid'] = False
            self.report['halt_reason'] = self.halt
            try:
                self.checkpoint()  # One bounded attempt to retain the failed final state.
            except Fatal:
                pass
            return 1
        return 0 if self.report['acquisition_and_cleanup_valid'] else 1


# ---------------------------------------------------------------- CLI

def emit(stream, payload):
    data = json.dumps(payload, sort_keys=True, ensure_ascii=True, allow_nan=False)
    if len(data) + 1 > POLICY['stdout_bytes']:
        data = json.dumps({'status': payload.get('status', 'refused'), 'reason': 'output_bound'})
    stream.write(data + '\n')
    stream.flush()


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise Refusal('usage')


def parse(argv):
    parser = _Parser(add_help=False, allow_abbrev=False)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--preflight', action='store_true')
    mode.add_argument('--execute', action='store_true')
    parser.add_argument('--input-root', required=True)
    parser.add_argument('--profile', required=True)
    parser.add_argument('--output')
    parser.add_argument('--root-reviewed-sha256')
    args = parser.parse_args(argv)
    if args.preflight:
        require(args.output is None and args.root_reviewed_sha256 is None, 'usage')
    else:
        require(args.output is not None and args.root_reviewed_sha256 is not None, 'usage')
        require(re.fullmatch(r'[0-9a-f]{64}', args.root_reviewed_sha256) is not None, 'usage')
    return args


def main(argv=None, ops=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        args = parse(argv)
        driver = own_sha()
        if args.execute:
            require(args.root_reviewed_sha256 == driver['sha256'], 'driver_sha')  # Before any output/native access.
        meta = load_metadata(args.input_root, args.profile)
    except (Refusal, Absent) as exc:
        emit(sys.stdout, {'status': 'refused', 'reason': exc.args[0] if exc.args else 'absent'})
        return 2
    except Exception:
        emit(sys.stdout, {'status': 'refused', 'reason': 'internal'})
        return 2
    counts = {'roots': len(meta['catalog']['roots']), 'jobs': len(meta['catalog']['jobs']), 'targets': len(meta['plans']),
              'referrers': meta['referrers'], 'gap_roots': len(meta['gaps']), 'source_pins': len(meta['sources']),
              'kinds': {k: sum(p['kind'] == k for p in meta['plans']) for k in ('model', 'bmp', 'jpeg')}}
    if args.preflight:
        emit(sys.stdout, {'status': 'preflight_ok', 'task': TASK, 'driver_sha256': driver['sha256'],
                          'profile_sha256': PROFILE_SHA, 'catalog_sha256': meta['catalog_receipt']['sha256'],
                          'counts': counts, 'native_qualification': None,
                          'native_or_network_or_process': False})
        return 0
    output = os.path.normpath(os.path.abspath(args.output))
    observer = Observer(meta, output, driver, ops=ops)
    try:
        code = observer.run()
    except Exception:
        code = 1
    if code == 2:
        emit(sys.stdout, {'status': 'refused', 'reason': 'output_admission'})
        return 2
    emit(sys.stdout, {'status': 'execute_qualified' if code == 0 else 'execute_failed', 'task': TASK,
                      'halt_reason': observer.halt, 'totals': observer.totals(),
                      'coverage': {k: v for k, v in (observer.report.get('coverage_counts') or {}).items()
                                   if not isinstance(v, dict)},
                      'acquisition_and_cleanup_valid': observer.report['acquisition_and_cleanup_valid']})
    return code


if __name__ == '__main__':
    sys.exit(main())
