"""Root-operated bounded observation of first-level map dependency targets.

T06.003.003.005. --preflight reads only the pinned profile, authored controls,
catalog and rule-source metadata; it never opens/stats native inputs, launches
a process or contacts HTTP. --execute requires the exact root-reviewed driver
SHA-256, then performs one owned loopback reader scan of every catalog target.
Results are first-level availability/prefix evidence only, never parsing,
rendering, playable-map or full-content proof.

T07.007.006 adds exactly one second trusted profile descriptor (the four-map
T07.007.005 integrated catalog, 311 targets). Its route keeps the same
lifecycle but separates the evidence output from a fresh served root, retains
native stdout/stderr privately under a bounded cap, binds the five startup
"Valid GRF" diagnostics and observes /api/cache-stats before and after the
assets. The profile selects its route only by exact trusted bytes/SHA-256.
"""
import argparse
import copy
from contextlib import contextmanager
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
import threading
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

PRODUCER_PATH = 'tools/renewal/catalog_map_dependencies.mjs'
LEGACY_SOURCE_PATHS = (
    'tools/renewal/observe_cache_map_cores.py', 'tools/renewal/observe_one_ground.py', PRODUCER_PATH,
    PRIOR_PROFILE_PATH, '.tools/renewal/client-source/src/Loaders/MapLoader.js',
    '.tools/renewal/client-source/src/Core/FileManager.js', '.tools/renewal/client-source/src/Loaders/Model.js',
    '.tools/renewal/remote-source/src/client.rs', '.tools/renewal/remote-source/src/config.rs',
    '.tools/renewal/remote-source/src/routes.rs', '.tools/renewal/remote-source/src/http.rs',
    '.tools/renewal/remote-source/src/cache.rs', '.tools/renewal/remote-source/src/util.rs',
    '.tools/renewal/remote-source/src/index.rs', '.tools/renewal/remote-source/src/grf.rs',
    '.tools/renewal/remote-source/src/encoding.rs')
LEGACY_ROUTE = {
    'task': TASK, 'profile_bytes': PROFILE_BYTES, 'profile_sha256': PROFILE_SHA, 'policy': POLICY,
    'native_names': NATIVE_NAMES, 'native_bases': ('home', 'input_root'), 'source_paths': LEGACY_SOURCE_PATHS,
    'prior_profile_path': PRIOR_PROFILE_PATH,
    'producer_pin': {'bytes': 31720, 'sha256': '12f5a315950a4f34ce8fd6aa7e2d0f4e075121f9ccbddeaae49b233b5f70897f'},
    'catalog_pin': {'path': '.tools/renewal/t06-root-verification-1/root-integrated-corpus-2/output/catalog.json',
                    'bytes': 32959912, 'sha256': '3c6b9707d2b9f8093d9e7ce21b7e320791d2b9d5ca4d3d6728e3f915356f64a3'},
    'split_root': False}

# ---- T07.007.006: the single second trusted descriptor.
T07_TASK = 'T07.007.006'
T07_PROFILE_BYTES = 9680
T07_PROFILE_SHA = '0615c6d9e6e7990acc3f9012d2028115fce0543bd5fe298bfb544953865db5c6'
T07_PRIOR_PROFILE_PATH = 'docs/project/fixtures/T07.007.005-profile.json'
T07_CONSTRUCTOR_PROFILE_PATH = 'docs/project/fixtures/T07.007.004-profile.json'
T07_MANIFEST_PATH = '.tools/renewal/t07-007-004-constructor-input-1/input-manifest.json'
T07_WORKER_PATH = 'tools/renewal/map_constructor_worker.mjs'
T07_CONSTRUCTOR_PRODUCER_PATH = 'tools/renewal/probe_map_constructors.mjs'
T07_SUMMARY_PATH = 'tools/renewal/map_constructor_summary.mjs'
T07_SOURCE_PATHS = tuple(T07_PRIOR_PROFILE_PATH if p == PRIOR_PROFILE_PATH else p for p in LEGACY_SOURCE_PATHS) + (
    '.tools/renewal/client-source/src/Loaders/Ground.js', T07_CONSTRUCTOR_PROFILE_PATH, T07_MANIFEST_PATH,
    T07_WORKER_PATH, T07_CONSTRUCTOR_PRODUCER_PATH, T07_SUMMARY_PATH)
T07_POLICY = dict(POLICY, asset_attempts=311, cache_mb=0, cache_files=0, cache_attempts=2, cache_bytes=65536,
                  diagnostic_bytes=16777216)
T07_NATIVE_NAMES = ['binary', '2026-08-25_live_client_4340_4349_1787295394.gpf',
                    '2026-08-25_live_client_4353_4353_1787535130.gpf', 'event.grf', 'data0.grf', 'data.grf']
# Full trusted second-route native descriptors; these paths are strings during preflight.
T07_NATIVE_TABLE = [
    {
        "name": "binary",
        "base": "input_root",
        "path": ".tools/renewal/t07-007-native-artifact-admission-1/reader",
        "bytes": 2079536,
        "sha256": "ee6b328ec73a591b23b514379e1b34e876b5d860d0e1aa4d9aa15dd7173eb1c1"
    },
    {
        "name": "2026-08-25_live_client_4340_4349_1787295394.gpf",
        "base": "input_root",
        "path": ".tools/renewal/t07-007-patch-acquisition-root-1/2026-08-25_live_client_4340_4349_1787295394.gpf",
        "bytes": 306097616,
        "sha256": "70725f6624f947c3096066cc66a07fcd2440adf94137b79561ed2d67843f9f0e"
    },
    {
        "name": "2026-08-25_live_client_4353_4353_1787535130.gpf",
        "base": "input_root",
        "path": ".tools/renewal/t07-007-patch-acquisition-root-1/2026-08-25_live_client_4353_4353_1787535130.gpf",
        "bytes": 86992,
        "sha256": "03764f614453d2b453a5ab5b552f6af9f66599a3642943566f72cbae6a501d07"
    },
    {
        "name": "event.grf",
        "base": "input_root",
        "path": ".tools/renewal/t07-007-execution-1/inner/app/event.grf",
        "bytes": 5833135,
        "sha256": "7fff4e0eececd10df9a9c4f83b70d78dc4dbb99c5ece64b117df7db8a2f85575"
    },
    {
        "name": "data0.grf",
        "base": "input_root",
        "path": ".tools/renewal/t07-007-execution-1/inner/app/data0.grf",
        "bytes": 2123919641,
        "sha256": "913402ace1d3c67818b4f070650a07eb157a6d62df9e394d596d59b4c7e6678a"
    },
    {
        "name": "data.grf",
        "base": "input_root",
        "path": ".tools/renewal/t07-007-execution-1/inner/app/data.grf",
        "bytes": 2172616301,
        "sha256": "0565853edc5ad4b70e8ad705f5bc88c1af5624ee1b7a252fa81030d2ea813cc6"
    }
]
# Artifact-observed startup literal (TWO leading spaces), in DATA.INI order.
T07_VALID_GRF = (('0x102', 5577), ('0x102', 3), ('0x102', 37), ('0x102', 89769), ('0x300', 155575))
VALID_GRF_MARK = b'Valid GRF'
VALID_GRF_LINE = re.compile(rb'\A  Valid GRF: (.+) \(version (0x[0-9a-fA-F]+), ([0-9]+) files\)\n\Z')
DIAGNOSTIC_LINE_MAX = 64 << 10
DRAIN_JOIN_SECONDS = 8
T07_HEALTH_VERSION = '1.0.5'
T07_CENSUS = {'rsm2': 174, 'rsm': 99, 'bmp': 38}
T07_CATALOG_KEYS = ('schema', 'task', 'mode', 'profile_sha256', 'input_pins', 'constructor_profile_sha256',
                    'summary_sha256', 'constructor_task', 'constructor_worker', 'constructor_producer', 'rule_sources',
                    'counts', 'roots', 'remaining_gap_root_ordinals', 'jobs', 'targets', 'limitations')
T07_ROUTE = {
    'task': T07_TASK, 'profile_bytes': T07_PROFILE_BYTES, 'profile_sha256': T07_PROFILE_SHA, 'policy': T07_POLICY,
    'native_names': T07_NATIVE_NAMES, 'native_bases': ('input_root',), 'source_paths': T07_SOURCE_PATHS,
    'prior_profile_path': T07_PRIOR_PROFILE_PATH,
    'producer_pin': {'bytes': 48337, 'sha256': '546ab2931c116e87f15348eb05610d7cab336a59898c07d7d2bf5a410372ea89'},
    'prior_pin': {'bytes': 4649, 'sha256': 'c0dccf5d0f74eecbcf772c560820dc3e0b4e5b26986243255085701136117034'},
    'catalog_pin': {'path': '.tools/renewal/t07-007-005-integrated-root-qualification-1/output-1/catalog.json',
                    'bytes': 169411, 'sha256': '0a6d44ec22de3c54f5195c32d6fd253ef5f51a74feb212181181ab5d9570c362'},
    'split_root': True}
ROUTES = {(PROFILE_BYTES, PROFILE_SHA): LEGACY_ROUTE, (T07_PROFILE_BYTES, T07_PROFILE_SHA): T07_ROUTE}
PROFILE_MAX = max(PROFILE_BYTES, T07_PROFILE_BYTES)


class Refusal(Exception):
    """Generic, no-echo refusal code."""


class Absent(Exception):
    """An admitted path or ancestor is ENOENT."""


def require(ok, code):
    if not ok:
        raise Refusal(code)


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def typed_equal(a, b):
    """JSON structural equality without bool/int/float coercion."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b))
    return a == b


def integer_tree(value):
    return all(integer_tree(v) for v in value.values()) if isinstance(value, dict) else is_int(value)


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
            except Fatal:
                raise
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
    require(stat.S_ISREG(first.st_mode) and first.st_nlink == 1, 'admit_regular')
    size = first.st_size
    require(expected_bytes is None or (is_int(expected_bytes) and size == expected_bytes), 'admit_size')
    require(limit is None or size <= limit, 'admit_limit')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise Refusal('admit_open')
    try:
        opened = os.fstat(fd)
        require(identity(opened) == identity(first) and stat.S_ISREG(opened.st_mode) and opened.st_nlink == 1, 'admit_drift')
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
    require(identity(after) == identity(first) == identity(last) and after.st_nlink == last.st_nlink == 1, 'admit_drift')
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
    require(isinstance(counts, dict) and integer_tree(counts), 'catalog_counts')
    require(isinstance(catalog, dict), 'catalog_shape')
    require(catalog.get('schema') == 'T06-map-dependency-catalog-1' and catalog.get('task') == 'T06.003.003.004'
            and catalog.get('mode') == 'corpus', 'catalog_identity')
    require(catalog.get('profile_sha256') == prior_pin['sha256'], 'catalog_profile_binding')
    require(typed_equal(catalog.get('counts'), counts), 'catalog_counts')
    pins = {p['path']: p for p in profile['source_pins']}
    for rel, pin in catalog.get('rule_sources', {}).items():
        mine = pins.get('.tools/renewal/client-source/' + rel)
        if mine is not None:
            require(pin == {'bytes': mine['bytes'], 'sha256': mine['sha256']}, 'catalog_rule_source')
    require(all(('.tools/renewal/client-source/' + r) in pins for r in ('src/Loaders/MapLoader.js', 'src/Core/FileManager.js')), 'catalog_rule_source')
    return _validate_graph(catalog, profile, legacy_gaps=True)


def _validate_graph(catalog, profile, legacy_gaps):
    """Shared root/job/loader/target/referrer validation for both routes."""
    counts = profile['expected_counts']
    require(isinstance(counts, dict) and integer_tree(counts), 'catalog_counts')
    roots, jobs, targets = catalog.get('roots'), catalog.get('jobs'), catalog.get('targets')
    require(isinstance(roots, list) and isinstance(jobs, list) and isinstance(targets, list), 'catalog_shape')
    gaps = profile['remaining_gap_root_ordinals']
    require(isinstance(gaps, list) and all(is_int(g) for g in gaps)
            and typed_equal(catalog.get('remaining_gap_root_ordinals'), gaps)
            and len(gaps) == counts['remaining_gap_roots'], 'catalog_gaps')
    require(len(roots) == counts['roots'] and typed_equal([r.get('ordinal') for r in roots], list(range(len(roots)))), 'catalog_roots')
    gap_set = set(gaps)
    if legacy_gaps:
        require(all((r.get('combined_observation') == 'gap') == (r['ordinal'] in gap_set) for r in roots), 'catalog_root_gaps')
    require(len(jobs) == counts['jobs'], 'catalog_jobs')
    job_ids = {}
    for index, job in enumerate(jobs):
        require(isinstance(job, dict) and typed_equal(job.get('source_row_index'), index) and job.get('id') not in job_ids, 'catalog_job')
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
            require(is_int(ref.get('root_ordinal')), 'catalog_root_reference')
            key = (index, ref.get('root_ordinal'), ref.get('edge_kind'))
            require(key not in job_refs, 'catalog_root_reference')
            job_refs.add(key)
    require(edge_refs == job_refs and len(job_refs) == counts['root_edge_references'], 'catalog_root_references')
    require(len(targets) == counts['http_targets'] and typed_equal([t.get('index') for t in targets], list(range(len(targets)))), 'catalog_targets')
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
            require(typed_equal(entry.get('index'), position), 'catalog_loader_index')
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
            require(is_int(ref.get('job_index')) and is_int(ref.get('loader_index')), 'catalog_referrer')
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


def _pin(entry):
    return {'bytes': entry.get('bytes'), 'sha256': entry.get('sha256')} if isinstance(entry, dict) else None


def _ordered(value):
    """Order-sensitive structural identity for exact JSON comparisons."""
    return json.dumps(value, ensure_ascii=True, allow_nan=False)


def validate_catalog_t07(catalog, profile, prior, constructor_profile, manifest):
    """Whole-catalog admission for T07.007.006 against the admitted .005/.004 metadata.

    prior, constructor_profile and manifest are the parsed T07.007.005 profile,
    T07.007.004 profile and constructor input manifest, each already admitted as
    an exact source pin. Body/reference paths are compared as strings only.
    """
    counts = profile['expected_counts']
    require(isinstance(counts, dict) and integer_tree(counts), 'catalog_counts')
    pins = {p['path']: p for p in profile['source_pins']}
    require(all(path in pins for path in T07_SOURCE_PATHS), 'profile_sources')
    for value in (catalog, prior, constructor_profile, manifest):
        require(isinstance(value, dict), 'catalog_shape')
    require(tuple(catalog) == T07_CATALOG_KEYS, 'catalog_shape')
    require(catalog['schema'] == 'T06-map-dependency-catalog-1' and catalog['task'] == 'T07.007.005'
            and catalog['mode'] == 'corpus', 'catalog_identity')
    # .005 profile identity and every binding the catalog carries.
    require(prior.get('schema') == 'T06-map-dependency-profile-1' and prior.get('task') == 'T07.007.005'
            and prior.get('constructor_task') == 'T07.007.004', 'prior_identity')
    require(catalog['profile_sha256'] == pins[T07_PRIOR_PROFILE_PATH]['sha256'], 'catalog_profile_binding')
    inputs = prior.get('inputs')
    require(isinstance(inputs, dict) and tuple(inputs) == ('report.json', 'jobs.jsonl'), 'prior_inputs')
    expected_inputs = dict(inputs, constructor_manifest=prior.get('constructor_manifest'))
    require(_ordered(catalog['input_pins']) == _ordered(expected_inputs), 'catalog_input_pins')
    require(catalog['constructor_task'] == prior['constructor_task'], 'catalog_constructor_task')
    require(_ordered(catalog['constructor_worker']) == _ordered(prior.get('constructor_worker')), 'catalog_constructor_worker')
    require(_ordered(catalog['constructor_producer']) == _ordered(prior.get('constructor_producer')), 'catalog_constructor_producer')
    require(catalog['constructor_profile_sha256'] == (prior.get('constructor_profile') or {}).get('sha256'), 'catalog_constructor_profile')
    require(catalog['summary_sha256'] == (prior.get('summary') or {}).get('sha256'), 'catalog_summary')
    rules = prior.get('rule_sources')
    require(isinstance(rules, dict) and len(rules) == 3 and _ordered(catalog['rule_sources']) == _ordered(rules), 'catalog_rule_source')
    require(catalog['limitations'] == prior.get('limitations'), 'catalog_limitations')
    require(typed_equal(catalog['counts'], counts) and typed_equal(prior.get('expected_counts'), counts), 'catalog_counts')
    # The .005 sub-pins must name exactly the admitted descriptor sources.
    for rel, rule in rules.items():
        source = pins.get('.tools/renewal/client-source/' + rel)
        require(source is not None and typed_equal(_pin(source), rule), 'catalog_rule_source')
    for key, path in (('constructor_profile', T07_CONSTRUCTOR_PROFILE_PATH), ('constructor_manifest', T07_MANIFEST_PATH),
                      ('constructor_worker', T07_WORKER_PATH), ('constructor_producer', T07_CONSTRUCTOR_PRODUCER_PATH),
                      ('summary', T07_SUMMARY_PATH)):
        entry = prior.get(key)
        require(isinstance(entry, dict) and entry.get('path') == path and typed_equal(_pin(entry), _pin(pins[path])), 'prior_source_binding')
    # .004 constructor profile and manifest bindings.
    cp, cpc = constructor_profile, constructor_profile.get('counts')
    require(cp.get('schema') == 'T06-map-constructor-profile-1' and cp.get('task') == 'T07.007.004', 'constructor_profile_identity')
    require(_ordered(cp.get('manifest')) == _ordered(prior['constructor_manifest'])
            and _ordered(cp.get('worker')) == _ordered(prior['constructor_worker'])
            and _ordered(cp.get('summary')) == _ordered(prior['summary']), 'constructor_profile_binding')
    require(manifest.get('schema') == 'T06-map-constructor-input-1' and manifest.get('task') == catalog['constructor_task'],
            'manifest_identity')
    require(isinstance(cpc, dict) and integer_tree(cpc) and typed_equal(manifest.get('counts'), cpc) and cpc.get('roots') == counts['roots']
            and cpc.get('jobs') == counts['jobs'] and cpc.get('edge_references') == counts['root_edge_references'],
            'manifest_counts')
    require(manifest.get('remaining_gap_root_ordinals') == profile['remaining_gap_root_ordinals'] == [], 'manifest_gaps')
    mroots, mjobs, jobs = manifest.get('roots'), manifest.get('jobs'), catalog['jobs']
    require(isinstance(mroots, list) and isinstance(mjobs, list) and isinstance(jobs, list)
            and len(mroots) == counts['roots'] and len(mjobs) == len(jobs) == counts['jobs'], 'manifest_shape')
    # Every ordered catalog job against its manifest row; metadata only.
    for job, mjob in zip(jobs, mjobs):
        require(isinstance(job, dict) and isinstance(mjob, dict) and isinstance(mjob.get('header'), dict), 'catalog_job_manifest')
        require(job.get('id') == mjob.get('job_id') and job.get('kind') == mjob.get('kind')
                and job.get('complete_sha256') == mjob.get('complete_sha256')
                and is_int(job.get('input_bytes')) and typed_equal(job['input_bytes'], mjob.get('bytes'))
                and typed_equal(job.get('header_version_bytes'), mjob['header'].get('version_bytes'))
                and isinstance(job.get('header_version_bytes'), list)
                and all(is_int(v) and 0 <= v <= 255 for v in job['header_version_bytes']), 'catalog_job_manifest')
        require(job.get('outcome') == 'returned' and job.get('constructor_returned') is True, 'catalog_job_outcome')
    # Expected roots: the manifest roots plus each linked job's returned outcome.
    by_id = {job['id']: job for job in jobs}
    require(len(by_id) == len(jobs), 'catalog_job')
    expected_roots = copy.deepcopy(mroots)
    core = 0
    for root in expected_roots:
        require(isinstance(root, dict) and isinstance(root.get('edges'), dict)
                and root.get('ordinal_scope') == 'four-target-subset-only'
                and 'original_gap_root_ordinal' in root and root['original_gap_root_ordinal'] is None, 'catalog_root_provenance')
        chain = 0
        for edge in root['edges'].values():
            require(isinstance(edge, dict) and edge.get('job_id') in by_id and edge.get('parse_status') == 'not_run'
                    and 'parse_outcome' not in edge, 'catalog_root_provenance')
            edge['parse_outcome'] = by_id[edge['job_id']]['outcome']
            chain += edge['parse_outcome'] == 'returned'
        core += tuple(root['edges']) == ('rsw', 'gnd', 'gat') and chain == 3
    require(_ordered(catalog['roots']) == _ordered(expected_roots), 'catalog_roots_manifest')
    require(core == counts['core_chain_roots'], 'catalog_core_chains')
    plans, referrers = _validate_graph(catalog, profile, legacy_gaps=False)
    census = {}
    for plan in plans:
        ext = plan['http_path'].rsplit('.', 1)[1]
        ext = 'bmp' if ext in ('bmp', 'BMP') else ext
        census[ext] = census.get(ext, 0) + 1
    require(census == T07_CENSUS, 'catalog_census')
    return plans, referrers


def check_profile(profile, route):
    """Exact descriptor checks once the trusted bytes/SHA selected the route."""
    require(isinstance(profile, dict), 'profile_identity')
    require(profile.get('schema') == PROFILE_SCHEMA and profile.get('task') == route['task'], 'profile_identity')
    require(typed_equal(profile.get('policy'), route['policy']), 'profile_policy')
    native = profile.get('native')
    if route['split_root']:
        require(typed_equal(native, T07_NATIVE_TABLE), 'profile_native')
    require(isinstance(native, list) and all(isinstance(n, dict) for n in native), 'profile_native')
    require([n.get('name') for n in native] == route['native_names'], 'profile_native')
    require(all(n.get('base') in route['native_bases'] for n in native), 'profile_native')
    sources = profile.get('source_pins')
    require(isinstance(sources, list) and all(isinstance(p, dict) for p in sources), 'profile_sources')
    require(tuple(p.get('path') for p in sources) == route['source_paths'], 'profile_sources')
    pins = {p['path']: p for p in sources}
    require(typed_equal(_pin(pins[PRODUCER_PATH]), route['producer_pin']), 'profile_producer')
    if 'prior_pin' in route:
        require(typed_equal(_pin(pins[route['prior_profile_path']]), route['prior_pin']), 'profile_prior_binding')
    require(typed_equal(profile.get('catalog'), route['catalog_pin']), 'profile_catalog')


def load_metadata(input_root, profile_path):
    """Metadata-only admission. Never touches native inputs, processes or HTTP."""
    require(isinstance(input_root, str) and os.path.isabs(input_root), 'input_root')
    input_root = os.path.normpath(input_root)
    try:
        check_ancestors(os.path.join(input_root, 'x'))
    except Absent:
        raise Refusal('input_root')
    profile_path = os.path.normpath(os.path.abspath(profile_path))
    # Trusted bytes/SHA select the route before the contents may authorize anything.
    profile_bytes, profile_receipt = read_admitted(profile_path, limit=PROFILE_MAX)
    route = ROUTES.get((profile_receipt['bytes'], profile_receipt['sha256']))
    require(route is not None, 'profile_pin')
    profile = strict_json(profile_bytes)
    check_profile(profile, route)
    authored_pin = profile['authored']
    authored_bytes, authored_receipt = read_admitted(relative(input_root, authored_pin['path']),
                                                     authored_pin['bytes'], authored_pin['sha256'])
    authored = strict_json(authored_bytes)
    require(authored.get('schema') == AUTHORED_SCHEMA and authored.get('status') == 'FROZEN_ROOT_REVIEWED', 'authored_identity')
    sources, kept = [], {}
    keep = {T07_PRIOR_PROFILE_PATH, T07_CONSTRUCTOR_PROFILE_PATH, T07_MANIFEST_PATH} if route['split_root'] else set()
    for pin in profile['source_pins']:
        data, receipt = read_admitted(relative(input_root, pin['path']), pin['bytes'], pin['sha256'], keep=pin['path'] in keep)
        sources.append(dict(path=pin['path'], **receipt))
        if data is not None:
            kept[pin['path']] = data
    prior = [p for p in profile['source_pins'] if p['path'] == route['prior_profile_path']]
    require(len(prior) == 1, 'profile_prior_binding')
    cpin = profile['catalog']
    require(cpin['bytes'] <= route['policy']['catalog_bytes'], 'catalog_limit')
    catalog_bytes, catalog_receipt = read_admitted(relative(input_root, cpin['path']), cpin['bytes'], cpin['sha256'])
    catalog = strict_json(catalog_bytes)
    if route['split_root']:
        plans, referrers = validate_catalog_t07(catalog, profile, strict_json(kept[T07_PRIOR_PROFILE_PATH]),
                                                strict_json(kept[T07_CONSTRUCTOR_PROFILE_PATH]),
                                                strict_json(kept[T07_MANIFEST_PATH]))
    else:
        plans, referrers = validate_catalog(catalog, profile, prior[0])
    return {'input_root': input_root, 'profile_path': profile_path, 'profile': profile,
            'profile_receipt': profile_receipt, 'authored_receipt': authored_receipt,
            'sources': sources, 'catalog_bytes': catalog_bytes, 'catalog_receipt': catalog_receipt,
            'catalog_path': relative(input_root, cpin['path']), 'catalog': catalog, 'plans': plans,
            'referrers': referrers, 'gaps': list(profile['remaining_gap_root_ordinals']), 'route': route}


def native_specs(meta):
    items = meta['profile']['native']
    home = None
    if any(item['base'] == 'home' for item in items):  # The T07 route never looks up HOME.
        home = os.path.normpath(os.path.expanduser('~'))
        require(os.path.isabs(home), 'home')
    out = []
    for item in items:
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

    def popen_piped(self, argv, cwd, env):
        """T07 route: stdout/stderr are pipes drained by bounded owned threads."""
        return subprocess.Popen(argv, cwd=cwd, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE, start_new_session=True, close_fds=True, umask=0o077, bufsize=0)

    def start_thread(self, target, name):
        thread = threading.Thread(target=target, name=name, daemon=True)
        thread.start()
        return thread

    def start_diagnostic_thread(self, thread):
        """New-route hook; Diagnostics already owns this unstarted worker."""
        thread.start()

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
        self.check = lambda: None

    @property
    def length(self):
        return self._response.length

    def read1(self, n):
        self.check()
        self._refresh()
        self.check()
        try:
            chunk = self._response.read1(n)
        except http.client.IncompleteRead as exc:
            self.wire += len(exc.partial)
            self.complete = False
            self.check()
            raise
        except Exception:
            self.check()
            raise
        if isinstance(chunk, (bytes, bytearray)):
            self.wire += len(chunk)
            self.complete = self.length == 0 or (not chunk and self.length is None)
        self.check()  # Received bytes are charged even if this raises Fatal.
        return chunk


class Diagnostics:
    """Bounded private retention of the owned reader's stdout/stderr (T07 route).

    Output files are created before Popen; pipes are adopted immediately after.
    Overflow, read/write/close errors, an unfinished drainer or any Valid GRF
    line other than the exact ordered expected lines is a failure.
    """
    STREAMS = ('stdout', 'stderr')
    FILES = {'stdout': 'native-stdout.log', 'stderr': 'native-stderr.log'}

    POLL_SECONDS = 0.02
    INTERRUPT_LIMIT = 16

    def __init__(self, directory, cap, expected, write_fn=None):
        self.directory, self.cap, self.expected, self.write_fn = directory, cap, list(expected), write_fn
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.out, self.sources, self.threads, self.receipts, self.created = {}, {}, {}, {}, []
        self.seen = dict.fromkeys(self.STREAMS, 0)
        self.stored = dict.fromkeys(self.STREAMS, 0)
        self.digest = {s: hashlib.sha256() for s in self.STREAMS}
        self.pending = dict.fromkeys(self.STREAMS, b'')
        self.overlong = dict.fromkeys(self.STREAMS, False)
        self.storing = dict.fromkeys(self.STREAMS, True)
        self.done = dict.fromkeys(self.STREAMS, False)
        self.eof = dict.fromkeys(self.STREAMS, False)
        self.lines, self.errors, self.overflow = [], [], False
        self.reserved_total, self.inflight = 0, 0
        self.clock, self.deadline, self.finish_deadline = time.monotonic, math.inf, math.inf
        self.started = self.finished = False

    def error(self, code):
        # Bounded fallback also works when a lock acquisition itself timed out.
        if code not in self.errors and len(self.errors) < 32:
            self.errors.append(code)

    @contextmanager
    def _locked(self):
        allowance = min(0.05, max(0, self.deadline - self.clock()),
                        max(0, self.finish_deadline - time.monotonic()))
        if not self.lock.acquire(timeout=allowance):
            self.error('state_lock_timeout')
            raise Fatal('diagnostic_failure')
        try:
            yield
        finally:
            self.lock.release()

    def open_outputs(self):
        for stream in self.STREAMS:
            fd = os.open(os.path.join(self.directory, self.FILES[stream]),
                         os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
            self.out[stream] = fd  # Ownership before fallible setup.
            self.created.append(self.FILES[stream])
            os.fchmod(fd, 0o600)

    def adopt(self, proc):
        for stream in self.STREAMS:
            self.sources[stream] = getattr(proc, stream, None)

    def start(self, start_thread):
        """Create/register workers locally before invoking the fallible starter."""
        for stream in self.STREAMS:
            if self.sources.get(stream) is None:
                raise Fatal('diagnostic_failure')
            try:
                thread = threading.Thread(target=lambda s=stream: self._drain(s),
                                          name='diagnostics-' + stream, daemon=True)
                self.threads[stream] = thread
                start_thread(thread)
            except Exception:
                self.error(stream + '_thread_start')
                raise Fatal('diagnostic_failure')
        self.started = True

    def _drain(self, stream):
        normal_eof = False
        try:
            fd = self.sources[stream].fileno()
            os.set_blocking(fd, False)
            interrupts = 0
            while not self.stop.is_set():
                if self.clock() >= self.deadline or time.monotonic() >= self.finish_deadline:
                    self.error(stream + '_read_deadline')
                    break
                try:
                    chunk = os.read(fd, READ_MAX)
                except InterruptedError:
                    interrupts += 1
                    if interrupts >= self.INTERRUPT_LIMIT:
                        raise OSError('interrupted read limit')
                    continue
                except BlockingIOError:
                    interrupts = 0
                    self.stop.wait(self.POLL_SECONDS)
                    continue
                interrupts = 0
                if not chunk:
                    normal_eof = True
                    break
                self._accept(stream, chunk)
        except Exception:
            self.error(stream + '_read_error')
        finally:
            try:
                with self._locked():
                    self._eof(stream)
                    self.eof[stream] = normal_eof
                    if not normal_eof:
                        self.error(stream + '_cancelled_or_failed')
            except Fatal:
                pass
            self.done[stream] = True

    def _accept(self, stream, chunk):
        with self._locked():
            self.seen[stream] += len(chunk)
            room = max(0, self.cap - self.reserved_total)
            keep = chunk[:room]
            self.reserved_total += len(keep)  # Never refund uncertain capacity.
            if len(keep) < len(chunk):
                self.overflow = True
            if not keep or not self.storing[stream]:
                return
            self.inflight += 1
        offset, interrupts = 0, 0
        try:
            while offset < len(keep):
                # Overflow does NOT cancel this already reserved prefix.
                if (self.stop.is_set() or self.clock() >= self.deadline
                        or time.monotonic() >= self.finish_deadline):
                    raise OSError('diagnostic write cancelled')
                try:
                    wrote = (self.write_fn or os.write)(self.out[stream], memoryview(keep)[offset:])
                except InterruptedError:
                    interrupts += 1
                    if interrupts >= self.INTERRUPT_LIMIT:
                        raise OSError('interrupted write limit')
                    continue
                if not is_int(wrote) or not 0 < wrote <= len(keep) - offset:
                    raise OSError('invalid diagnostic progress')
                interrupts = 0
                with self._locked():
                    piece = keep[offset:offset + wrote]
                    self.stored[stream] += wrote
                    self.digest[stream].update(piece)
                    self._frame(stream, piece)
                offset += wrote
                if self.clock() >= self.deadline or time.monotonic() >= self.finish_deadline:
                    raise OSError('diagnostic write deadline')
        except Exception:
            self.storing[stream] = False
            self.error(stream + '_write_error')
        finally:
            # No callback/syscall under the state lock, including in cleanup.
            with self._locked():
                self.inflight -= 1

    def _frame(self, stream, data):
        """LF framing that survives pipe chunk boundaries; bounded per line."""
        buf, start = self.pending[stream] + data, 0
        while True:
            end = buf.find(b'\n', start)
            if end < 0:
                break
            line = buf[start:end + 1]
            if self.overlong[stream]:
                if VALID_GRF_MARK in line or self.overlong[stream] == 'marked':
                    self.lines.append((stream, b''))  # An overlong marked line never matches.
                self.overlong[stream] = False
            elif VALID_GRF_MARK in line:
                self.lines.append((stream, line))
            start = end + 1
        rest = buf[start:]
        if len(rest) > DIAGNOSTIC_LINE_MAX:
            tail = len(VALID_GRF_MARK) - 1
            if VALID_GRF_MARK in rest:
                self.overlong[stream] = 'marked'
            elif not self.overlong[stream]:
                self.overlong[stream] = True
            rest = rest[-tail:]
        self.pending[stream] = rest

    def _eof(self, stream):
        rest = self.pending[stream]
        if VALID_GRF_MARK in rest or self.overlong[stream] == 'marked':
            self.lines.append((stream, rest))  # Unterminated: never equals an LF line.
        self.pending[stream], self.overlong[stream] = b'', False

    def failed(self):
        try:
            with self._locked():
                return bool(self.errors or self.overflow or not self._prefix_ok(self.lines))
        except Fatal:
            return True

    def snapshot_lines(self):
        with self._locked():
            return list(self.lines)

    def startup_state(self):
        """Only confirmed written lines, with no reserved write still in flight."""
        with self._locked():
            lines, failed, inflight = list(self.lines), bool(self.errors or self.overflow), self.inflight
        if failed:
            raise Fatal('diagnostic_failure')
        if not self._prefix_ok(lines):
            raise Fatal('startup_diagnostics')
        return not inflight and len(lines) == len(self.expected)

    def _prefix_ok(self, lines):
        if len({stream for stream, _ in lines}) > 1 or len(lines) > len(self.expected):
            return False
        return all(line == self.expected[i] for i, (_, line) in enumerate(lines))

    def lines_exact(self):
        lines = self.snapshot_lines()
        return self._prefix_ok(lines) and len(lines) == len(self.expected)

    def finish(self, join_seconds=DRAIN_JOIN_SECONDS):
        """One total allowance; never close an FD beneath a live writer."""
        end = time.monotonic() + max(0, join_seconds)
        self.finish_deadline = end
        cancel_by = end - min(1, max(0, join_seconds) / 2)
        self.deadline = math.inf  # Cleanup draining has its own absolute allowance.
        for thread in self.threads.values():
            if thread.ident is not None:
                thread.join(max(0, cancel_by - time.monotonic()))
        self.stop.set()
        for thread in self.threads.values():
            if thread.ident is not None:
                thread.join(max(0, end - time.monotonic()))
        all_stopped = True
        for stream in self.STREAMS:
            thread = self.threads.get(stream)
            if thread is not None and thread.is_alive():
                self.error(stream + '_drainer_incomplete')
                all_stopped = False
                continue  # Preserve both FDs; the outer guard bounds kernel-stalled I/O.
            source = self.sources.pop(stream, None)
            if source is not None:
                try:
                    source.close()
                except Exception:
                    self.error(stream + '_source_close')
            fd = self.out.pop(stream, None)  # Never retain a stale numeric FD after close.
            if fd is None:
                continue
            try:
                os.close(fd)
            except OSError:
                self.error(stream + '_output_close')
            path = os.path.join(self.directory, self.FILES[stream])
            try:
                _, receipt = read_admitted(path, limit=self.cap)
                self.receipts[stream] = receipt
                if receipt['bytes'] != self.stored[stream] or receipt['sha256'] != self.digest[stream].hexdigest():
                    self.error(stream + '_stored_mismatch')
            except (Refusal, Absent, OSError):
                self.error(stream + '_verify_failed')
        self.finished = all_stopped

    def record(self):
        try:
            with self._locked():
                complete = self.started and all(self.done.values())
                exact = self._prefix_ok(self.lines) and len(self.lines) == len(self.expected)
                files = {s: dict(file=self.FILES[s], bytes=self.receipts[s]['bytes'], sha256=self.receipts[s]['sha256'])
                         if s in self.receipts else {'file': self.FILES[s], 'bytes': None, 'sha256': None} for s in self.STREAMS}
                return {'files': files, 'seen_bytes': dict(self.seen), 'stored_bytes': dict(self.stored),
                        'reserved_bytes': self.reserved_total, 'eof': dict(self.eof),
                        'cap_bytes': self.cap, 'overflow': self.overflow, 'errors': list(self.errors),
                        'drainers_started': self.started, 'drainers_complete': complete, 'finished': self.finished,
                        'valid_grf_lines': len(self.lines), 'valid_grf_exact': exact,
                        'valid': bool(complete and all(self.eof.values()) and self.finished and exact
                                      and not self.errors and not self.overflow and len(self.receipts) == len(self.STREAMS))}
        except Fatal:
            return {'valid': False, 'finished': False, 'drainers_complete': False, 'errors': list(self.errors)}


def unattempted(plan, reason):
    return {'target_index': plan['index'], 'attempted': False, 'request_index': None, 'wire_target': plan['wire'],
            'started_elapsed_seconds': None, 'finished_elapsed_seconds': None, 'http_status': None, 'headers': None,
            'wire_bytes': 0, 'wire_complete': False, 'stop_reason': reason,
            'stored': {'file': None, 'bytes': None, 'sha256': None, 'complete': False, 'error': None},
            'signature': {'kind': plan['kind'], 'state': 'not_checked', 'prefix_hex': None}}


class Observer:
    def __init__(self, meta, output, driver, ops=None, natives=None, policy=None, container=None, write_fn=None,
                 diag_write_fn=None):
        self.meta, self.output, self.driver = meta, output, driver
        self.route = meta.get('route') or LEGACY_ROUTE
        self.split = self.route['split_root']
        self.ops = ops or SystemOps()
        self.natives = natives if natives is not None else native_specs(meta)
        self.policy = dict(self.route['policy'] if policy is None else policy)
        self.container = str(CONTAINER) if container is None else container
        self.write_fn, self.diag_write_fn = write_fn, diag_write_fn
        # Evidence stays at output; only the T07 native cwd/SERVER_ROOT is the fresh server subdirectory.
        self.server = os.path.join(output, 'server') if self.split else output
        self.proc, self.port, self.epoch, self.deadline = None, None, None, None
        self.halt, self.errors, self.created, self.request_index = None, [], False, 0
        self.wire_total, self.stored_total, self.asset_attempts, self.health_attempts = 0, 0, 0, 0
        self.cache_attempts, self.diag = 0, None
        self.stored_unknown = False
        self.body_files, self.native_before = [], {}
        self.retained = {}  # Private full receipts of every retained evidence file.
        self.output_created = False
        plans = meta['plans']
        self.report = {
            'schema': SCHEMA, 'task': self.route['task'], 'mode': 'execute',
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
        if self.split:
            self.report.update(cache_before=None, cache_after=None, startup_archive_counts=None, diagnostics=None,
                               server_tree=None, evidence_tree=None, retained_postverify=None)

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
        elif reason != self.halt and len(self.errors) < 64:
            self.errors.append('later_' + reason)
        if detail and len(self.errors) < 64:
            self.errors.append(detail[:128])

    # -- private file writes
    def path(self, rel):
        return os.path.join(self.output, rel)

    def served(self, rel):
        """Served-root path; equals path() for the legacy route."""
        return os.path.join(self.server, rel)

    def create_private(self, rel, data, base=None):
        target = os.path.join(self.output if base is None else base, rel)
        fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        try:
            os.fchmod(fd, 0o600)
            write_all(fd, data)
        finally:
            os.close(fd)
        _, receipt = read_admitted(target, len(data), sha(data), keep=False)
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
        out = {'asset_attempts': self.asset_attempts, 'health_attempts': self.health_attempts,
               'wire_bytes': self.wire_total, 'stored_bytes': None if self.stored_unknown else self.stored_total,
               'elapsed_seconds': self.elapsed()}
        if self.split:
            out['cache_attempts'] = self.cache_attempts
        return out

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
        if self.split:
            os.mkdir(self.server, 0o700)  # Fresh independent served root.
            os.chmod(self.server, 0o700)
        os.mkdir(self.served('resources'), 0o700)
        os.chmod(self.served('resources'), 0o700)
        self.retained['catalog-input.json'] = self.create_private('catalog-input.json', self.meta['catalog_bytes'])
        self.checkpoint()  # Every target is prefilled before native access.

    def hash_natives(self):
        out = {}
        for spec in self.natives:
            _, receipt = read_admitted(spec['path'], spec['bytes'], spec['sha256'], keep=False)
            out[spec['name']] = dict(receipt, name=spec['name'])
        return out

    def environment(self):
        port, output = str(self.port), self.output
        if self.split:
            # No HOME/GRF_FILENAME_ENCODING; the reader serves only the fresh server root.
            return {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'SERVER_ROOT': self.server, 'HOST': '127.0.0.1',
                    'PORT': port, 'NODE_ENV': 'development', 'CLIENT_PUBLIC_URL': 'http://127.0.0.1:' + port,
                    'CLIENT_RESPATH': 'resources/', 'CLIENT_DATAINI': self.served('resources/DATA.INI'),
                    'CACHE_MAX_FILES': str(self.policy['cache_files']), 'CACHE_MAX_MEMORY_MB': str(self.policy['cache_mb']),
                    'CACHE_WARM_UP': 'false', 'CLIENT_AUTOEXTRACT': 'false', 'CLIENT_ENABLESEARCH': 'false',
                    'ENABLE_STATIC_SERVE': 'false', 'ENABLE_WSPROXY': 'false', 'ENABLE_COMPRESSION': 'false'}
        return {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'SERVER_ROOT': output, 'PORT': port, 'HOST': '127.0.0.1',
                'NODE_ENV': 'production', 'CLIENT_PUBLIC_URL': 'http://127.0.0.1:' + port, 'CLIENT_RESPATH': 'resources/',
                'CLIENT_DATAINI': os.path.join(output, 'resources/DATA.INI'), 'ENABLE_STATIC_SERVE': 'false',
                'ENABLE_WSPROXY': 'false', 'ENABLE_COMPRESSION': 'false', 'CACHE_WARM_UP': 'false',
                'CLIENT_AUTOEXTRACT': 'false', 'CLIENT_ENABLESEARCH': 'false', 'GRF_FILENAME_ENCODING': 'auto',
                'CACHE_MAX_MEMORY_MB': str(self.policy['cache_mb']), 'CACHE_MAX_FILES': str(self.policy['cache_files'])}

    def expected_startup_lines(self):
        by_name = {s['name']: s for s in self.natives}
        return [b'  Valid GRF: %s (version %s, %d files)\n' % (by_name[n]['path'].encode('utf-8'), version.encode('ascii'), count)
                for n, (version, count) in zip(self.route['native_names'][1:], T07_VALID_GRF)]

    def startup_archive_counts(self):
        by_name = {s['name']: s for s in self.natives}
        lines, single = [], True
        if self.diag is not None:
            try:
                snapshot = self.diag.snapshot_lines()
                lines = [line for _, line in snapshot]
                single = len({stream for stream, _ in snapshot}) <= 1
            except Fatal:
                single = False
        out = []
        for i, (name, (version, count)) in enumerate(zip(self.route['native_names'][1:], T07_VALID_GRF)):
            path = by_name[name]['path']
            observed = VALID_GRF_LINE.match(lines[i]) if i < len(lines) else None
            row = {'name': name, 'path': path, 'expected_version': version, 'expected_count': count,
                   'observed_path_matches': False, 'observed_version': None, 'observed_count': None, 'valid': False}
            if observed:
                row.update(observed_path_matches=observed.group(1) == path.encode('utf-8'),
                           observed_version=observed.group(2).decode('ascii'), observed_count=int(observed.group(3)) if len(observed.group(3)) <= 10 else None)
            row['valid'] = bool(single and i < len(lines) and lines[i] == self.expected_startup_lines()[i])
            out.append(row)
        return out

    def _startup_check(self, ready_by):
        if self.ops.clock() >= ready_by:
            raise Fatal('startup_timeout')

    def _launch_piped(self):
        self.native_before = self.hash_natives()
        self.report['native_before'] = self.native_before
        by_name = {s['name']: s for s in self.natives}
        ini = '[Data]\n' + ''.join('%d=%s\n' % (i, by_name[n]['path']) for i, n in enumerate(self.route['native_names'][1:]))
        ini_receipt = self.create_private('resources/DATA.INI', ini.encode('utf-8'), base=self.server)
        self.retained['server/resources/DATA.INI'] = ini_receipt
        self.port = self.ops.fresh_port()
        require(not self.ops.port_listeners(self.port), 'port_in_use')
        env = self.environment()
        self.diag = Diagnostics(self.output, self.policy['diagnostic_bytes'], self.expected_startup_lines(), self.diag_write_fn)
        self.diag.open_outputs()
        self.report['launch'] = {'pid': None, 'pgid': None, 'port': self.port, 'environment': env, 'cwd': self.server,
                                 'task': self.route['task'], 'profile_sha256': self.route['profile_sha256'],
                                 'data_ini': {'bytes': ini_receipt['bytes'], 'sha256': ini_receipt['sha256']},
                                 'startup_seconds': self.policy['startup_seconds'], 'listener_proof': None}
        ready_by = self.ops.clock() + self.policy['startup_seconds']  # Immediately before Popen; never reset.
        self.proc = self.ops.popen_piped([by_name['binary']['path']], self.server, env)
        self.diag.adopt(self.proc)  # Registered before any fallible after-Popen setup.
        self.report['launch']['pid'] = self.proc.pid
        pgid = self.ops.getpgid(self.proc.pid)
        self.report['launch']['pgid'] = pgid
        if pgid != self.proc.pid:
            raise Fatal('launch_identity')
        self.diag.clock, self.diag.deadline = self.ops.clock, ready_by
        self.diag.start(self.ops.start_diagnostic_thread)
        self._startup_check(ready_by)
        self.checkpoint()  # PID/PGID/port recorded before any request.
        self._startup_check(ready_by)
        while True:
            if self.proc.poll() is not None:
                raise Fatal('reader_exited_at_startup')
            self._startup_check(ready_by)
            owned = self.ops.owned_listener(self.proc.pid, self.port)
            lines_ready = self.diag.startup_state()
            self._startup_check(ready_by)
            if owned and lines_ready:
                break
            self.ops.sleep(0.2)
        self.report['startup_archive_counts'] = self.startup_archive_counts()
        self.report['launch']['listener_proof'] = {'owned_listener': True, 'host': '127.0.0.1', 'port': self.port}

    def launch(self):
        if self.split:
            return self._launch_piped()
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
                                 'profile_sha256': self.route['profile_sha256'], 'data_ini': {'bytes': ini_receipt['bytes'], 'sha256': ini_receipt['sha256']},
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
        if self.split:
            invocations = sum(self.policy[k] for k in ('asset_attempts', 'health_attempts', 'cache_attempts'))
            if self.request_index >= invocations:
                raise Fatal('http_invocation_cap')
            self.diag_check()
        index = self.request_index
        self.request_index += 1
        name = '%06d' % index
        record.update(attempted=True, request_index=index, started_elapsed_seconds=self.elapsed())
        con = response = None
        fd = None
        result = None
        written = [0]

        def counted_write(target_fd, buffer):
            self.diag_check()
            wrote = (self.write_fn or os.write)(target_fd, buffer)
            if is_int(wrote) and 0 < wrote <= len(buffer):
                written[0] += wrote
            self.diag_check()
            return wrote
        metered = None
        try:
            try:
                self.diag_check()
                con = self.ops.connect(self.port, self.remaining_io())
                self.diag_check()
            except Fatal:
                raise
            except Exception:
                self.diag_check()
                record['stop_reason'] = 'connection_setup_error'
                return None
            try:
                self.diag_check()
                con.request('GET', wire, headers={'Accept-Encoding': 'identity'})
                self.diag_check()
                if getattr(con, 'sock', None) is not None:
                    con.sock.settimeout(self.remaining_io())
                self.diag_check()
                response = con.getresponse()
                record['http_status'] = response.status
                self.diag_check()
            except Fatal:
                raise
            except socket.timeout:
                self.diag_check()
                record['stop_reason'] = 'timeout'
                return None
            except Exception:
                self.diag_check()
                record['stop_reason'] = 'transport_error'
                return None
            self.diag_check()
            headers, malformed = dict.fromkeys(key for key, _ in HEADER_NAMES), False
            record['headers'] = headers
            for key, header in HEADER_NAMES:
                self.diag_check()
                value = response.getheader(header)
                if value is not None and (not isinstance(value, str) or len(value.encode('utf-8', 'surrogateescape')) > HEADER_MAX):
                    value, malformed = None, True
                headers[key] = value
                self.diag_check()
            self.diag_check()
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
            metered.check = self.diag_check
            self.diag_check()
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
            self.diag_check()
            return result
        except Fatal as fatal:
            self.fail(fatal.reason)  # First operation failure precedes all finally closers.
            if record.get('stop_reason') in (None, 'not_started'):
                record['stop_reason'] = 'deadline' if fatal.reason == 'acquisition_deadline' else fatal.reason
            raise
        except OSError:
            self.fail('storage_failure', 'request_storage_error')
            record['stored']['error'] = 'storage_error'
            record['stop_reason'] = 'storage_error'
            raise Fatal('storage_failure')
        except Exception as exc:
            self.fail('internal_failure', 'request_' + type(exc).__name__)
            raise
        finally:
            if metered is not None:
                record['wire_bytes'] = metered.wire
                record['wire_complete'] = metered.complete
                self.wire_total += metered.wire
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
                    record['stored']['error'] = record['stored']['error'] or 'storage_close_error'
                    self.fail('storage_failure', 'storage_close_error')
            record['finished_elapsed_seconds'] = self.elapsed()
            if fd is not None:
                self.verify_stored(record, result, written[0])
            if self.diag is not None and self.diag.failed():
                self.fail('diagnostic_failure', 'request_final_diagnostics')

    def diag_check(self):
        if self.diag is not None and self.diag.failed():
            raise Fatal('diagnostic_failure')

    def verify_stored(self, record, result, written):
        stored = record['stored']
        try:
            data, receipt = read_admitted(self.path(stored['file']), keep=True, limit=self.policy['body_bytes'])
            st = os.lstat(self.path(stored['file']))
            if self.split:
                self.retained[stored['file']] = receipt
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
        if self.split:
            record['version_ok'] = False
        self.report['health'] = record
        self.health_attempts += 1
        try:
            result = self.request('/api/health', self.policy['health_bytes'], record)
        finally:
            record.pop('_prefix', None)  # Never left in a record that is checkpointed after a storage Fatal.
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
        if self.split:
            record['version_ok'] = isinstance(body, dict) and body.get('version') == T07_HEALTH_VERSION
            record['valid'] = record['valid'] and record['version_ok']
            if self.ops.clock() >= self.deadline:  # After the final metadata observation.
                record['valid'] = False
                raise Fatal('acquisition_deadline')
        if result['late']:
            raise Fatal('acquisition_deadline')
        self.diag_check()
        if not record['valid']:
            raise Fatal('health_failure')

    def cache_stats(self, key):
        """One /api/cache-stats observation (T07 route); any failure is fatal."""
        record = {'attempted': False, 'request_index': None, 'http_status': None, 'headers': None, 'wire_bytes': 0,
                  'wire_complete': False, 'stop_reason': None, 'started_elapsed_seconds': None, 'finished_elapsed_seconds': None,
                  'stored': {'file': None, 'bytes': None, 'sha256': None, 'complete': False, 'error': None},
                  'grf_count_ok': False, 'cache_size_ok': False, 'cache_max_size_ok': False, 'observations': None,
                  'valid': False}
        self.report[key] = record
        self.cache_attempts += 1
        try:
            result = self.request('/api/cache-stats', self.policy['cache_bytes'], record)
        finally:
            record.pop('_prefix', None)
        if result is None or result['outcome'] != 'complete' or record['http_status'] != 200 or not record['stored']['complete']:
            if result is not None:
                record['stop_reason'] = result['outcome']
                if result['late']:
                    self.fail('acquisition_deadline')
            raise Fatal('cache_failure')
        record['stop_reason'] = 'complete'
        data, _ = read_admitted(self.path(record['stored']['file']), record['stored']['bytes'], record['stored']['sha256'])
        try:
            body = strict_json(data)
        except Refusal:
            raise Fatal('cache_failure')
        index = body.get('index') if isinstance(body, dict) else None
        cache = body.get('cache') if isinstance(body, dict) else None
        index = index if isinstance(index, dict) else {}
        cache = cache if isinstance(cache, dict) else {}
        exact = lambda section, name, value: is_int(section.get(name)) and section[name] == value  # noqa: E731
        record['grf_count_ok'] = exact(index, 'grfCount', len(self.route['native_names']) - 1)
        record['cache_size_ok'] = exact(cache, 'size', 0)
        record['cache_max_size_ok'] = exact(cache, 'maxSize', 0)
        observed = {}
        for section_name, section, names in (('cache', cache, ('maxMemoryMB', 'memoryUsedMB', 'hitRate')),
                                             ('index', index, ('uniqueFiles', 'totalFiles', 'mojibakeKeys'))):
            for name in names:
                value = section.get(name)
                if value is None or isinstance(value, (bool, int, float)) or (isinstance(value, str) and len(value) <= 256):
                    observed[section_name + '.' + name] = value if name in section else 'absent'
                else:
                    observed[section_name + '.' + name] = 'unrecorded_type'
        record['observations'] = observed
        record['valid'] = record['grf_count_ok'] and record['cache_size_ok'] and record['cache_max_size_ok']
        if result['late'] or self.ops.clock() >= self.deadline:  # After the final metadata observation.
            record['valid'] = False
            raise Fatal('acquisition_deadline')
        self.diag_check()
        if not record['valid']:
            raise Fatal('cache_failure')

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
                   'listener_absent': None, 'group_members_after': None, 'error': None, 'errors': [], 'clean': False}
        self.report['cleanup'] = cleanup

        def fault(phase, exc):
            code = phase + '_' + type(exc).__name__
            if cleanup['error'] is None:
                cleanup['error'] = ('listener_' if phase == 'listener_before' else '') + type(exc).__name__
            if len(cleanup['errors']) < 16:
                cleanup['errors'].append(code)
            self.fail('cleanup_failure', code)

        if self.proc is None:
            cleanup.update(listener_absent=True, group_members_after=[], clean=True)
            if self.port is not None:
                try:
                    cleanup['listener_absent'] = not self.ops.port_listeners(self.port)
                except Exception as exc:
                    fault('listener_after', exc)
                cleanup['clean'] = cleanup['error'] is None and cleanup['listener_absent'] is True
            return
        running = True  # Unknown poll cannot revoke ownership of the Popen child.
        try:
            running = self.proc.poll() is None
        except Exception as exc:
            fault('poll', exc)
        try:
            cleanup['listener_before_shutdown'] = self.ops.owned_listener(self.proc.pid, self.port)
        except Exception as exc:
            fault('listener_before', exc)
        if running:
            try:
                self.proc.terminate()  # Exact owned child only, never a group/name/port.
                cleanup['terminated'] = True
            except Exception as exc:
                fault('terminate', exc)
        try:
            cleanup['exit_code'] = self.proc.wait(timeout=8)
        except subprocess.TimeoutExpired:
            cleanup['forced_kill'] = True
            try:
                self.proc.kill()
            except Exception as exc:
                fault('kill', exc)
            try:
                cleanup['exit_code'] = self.proc.wait(timeout=8)
            except Exception as exc:
                fault('forced_wait', exc)
        except Exception as exc:
            fault('wait', exc)
        try:
            cleanup['listener_absent'] = not self.ops.port_listeners(self.port)
        except Exception as exc:
            fault('listener_after', exc)
        pgid = (self.report['launch'] or {}).get('pgid')
        try:
            require(is_int(pgid) and pgid == self.proc.pid, 'pgid_unknown')
            cleanup['group_members_after'] = self.ops.group_members(pgid)
        except Exception as exc:
            fault('group_after', exc)
        cleanup['clean'] = bool(cleanup['error'] is None and not cleanup['forced_kill'] and cleanup['exit_code'] == 0
                                and cleanup['listener_before_shutdown'] is True
                                and cleanup['listener_absent'] is True and cleanup['group_members_after'] == [])

    def audit_missing_log(self):
        expected = [unquote(self.meta['plans'][r['target_index']]['http_path'], encoding='utf-8', errors='strict')
                    for r in self.report['targets'] if r['http_status'] == 404]
        audit = {'present': False, 'bytes': None, 'sha256': None, 'entries': None, 'expected_404': len(expected), 'valid': False, 'error': None}
        self.report['missing_log'] = audit
        path = self.served('logs/missing-files.log')
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
        if self.split:
            return self._audit_split_trees()
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

    def _audit_dir(self, base, dirs, files, required, opaque=()):
        """Strict tree: only listed dirs/files, 0700 dirs, 0600 nlink-1 files, no links."""
        audit = {'unexpected': [], 'bad_mode': [], 'missing': [], 'valid': False, 'error': None}
        try:
            root = os.lstat(base)
            if not stat.S_ISDIR(root.st_mode) or stat.S_IMODE(root.st_mode) != 0o700 or root.st_uid != os.getuid():
                audit['bad_mode'].append('.')
            stack, found = [''], set()
            while stack:
                rel = stack.pop()
                with os.scandir(os.path.join(base, rel) if rel else base) as entries:
                    for entry in entries:
                        child = entry.name if not rel else rel + '/' + entry.name
                        st = entry.stat(follow_symlinks=False)
                        if stat.S_ISDIR(st.st_mode):
                            if child not in dirs and child not in opaque:
                                audit['unexpected'].append(child)
                                continue
                            if stat.S_IMODE(st.st_mode) != 0o700 or st.st_uid != os.getuid():
                                audit['bad_mode'].append(child)
                            if child not in opaque:
                                stack.append(child)
                        elif stat.S_ISREG(st.st_mode) and child in files:
                            found.add(child)
                            if stat.S_IMODE(st.st_mode) != 0o600 or st.st_nlink != 1 or st.st_uid != os.getuid():
                                audit['bad_mode'].append(child)
                        else:
                            audit['unexpected'].append(child)
            audit['missing'] = sorted(set(required) - found)
            audit['unexpected'].sort()
            audit['bad_mode'].sort()
            audit['valid'] = not (audit['unexpected'] or audit['bad_mode'] or audit['missing'])
        except (OSError, Refusal, Absent) as exc:
            audit['error'] = type(exc).__name__
        return audit

    def _audit_split_trees(self):
        """Evidence root and served root are audited separately; tree.valid requires both."""
        require(all(NUMERIC.match(name) for name in self.body_files), 'body_name')
        diag_files = set(self.diag.created) if self.diag is not None else set()
        evidence_files = {'catalog-input.json', 'report.json', *self.body_files, *diag_files}
        evidence = self._audit_dir(self.output, (), evidence_files, evidence_files, opaque=('server',))
        if not os.path.lexists(self.server):
            evidence['missing'].append('server')
            evidence['valid'] = False
        ini = {'resources/DATA.INI'} if 'server/resources/DATA.INI' in self.retained else set()
        server = self._audit_dir(self.server, ('resources', 'logs'), {'resources/DATA.INI', 'logs/missing-files.log'},
                                 ini)
        self.report['evidence_tree'], self.report['server_tree'] = evidence, server
        tree = {'unexpected': evidence['unexpected'] + ['server/' + p for p in server['unexpected']],
                'bad_mode': evidence['bad_mode'] + ['server/' + p for p in server['bad_mode']],
                'missing': evidence['missing'] + ['server/' + p for p in server['missing']],
                'catalog_copy_exact': False, 'valid': False, 'error': evidence['error'] or server['error']}
        self.report['tree'] = tree
        try:
            read_admitted(self.path('catalog-input.json'), self.meta['catalog_receipt']['bytes'],
                          self.meta['catalog_receipt']['sha256'], keep=False)
            tree['catalog_copy_exact'] = True
        except (OSError, Refusal, Absent) as exc:
            tree['error'] = tree['error'] or type(exc).__name__
        tree['valid'] = bool(evidence['valid'] and server['valid'] and tree['catalog_copy_exact'] and tree['error'] is None)

    def retained_postverify(self):
        """Re-admit every retained evidence file; full receipt (identity/bytes/hash) equality."""
        entries = dict(self.retained)
        if self.diag is not None:
            for stream, receipt in self.diag.receipts.items():
                entries[Diagnostics.FILES[stream]] = receipt
        mismatched = []
        for rel, receipt in sorted(entries.items()):
            try:
                _, again = read_admitted(self.path(rel), keep=False)
            except (OSError, Refusal, Absent):
                mismatched.append(rel)
                continue
            if again != receipt:
                mismatched.append(rel)
        expected = {'catalog-input.json', 'server/resources/DATA.INI', *self.body_files}
        if self.diag is not None:
            expected.update(self.diag.created)
        missing = sorted(expected - set(entries))
        verify = {'files': len(entries), 'mismatched': mismatched, 'missing': missing,
                  'valid': not mismatched and not missing}
        self.report['retained_postverify'] = verify
        return verify['valid']

    def finish_diagnostics(self):
        if self.diag is None:
            self.report['diagnostics'] = {'valid': False, 'error': 'not_created'}
            return
        try:
            self.diag.finish()
        except Exception as exc:
            self.diag.error('finish_' + type(exc).__name__)
        self.report['diagnostics'] = self.diag.record()
        self.report['startup_archive_counts'] = self.startup_archive_counts()
        if not self.report['diagnostics']['valid']:
            self.fail('diagnostic_failure')  # A late failure cannot hide behind an earlier valid state.

    def postchecks(self):
        ok = True
        try:
            after = self.hash_natives()
            self.report['native_after'] = after
            ok = after == self.native_before and len(after) == len(self.route['native_names'])
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
        if self.split:
            ok = self.retained_postverify() and ok
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
            if self.diag is not None:
                self.diag.deadline = self.deadline
            self.health()
            if self.split:
                self.cache_stats('cache_before')  # Before the first asset.
            self.scan()
            if self.split and not self.halt:
                self.cache_stats('cache_after')  # After the final asset.
            self.diag_check()
            if not self.halt and not (self.proc.poll() is None and self.ops.owned_listener(self.proc.pid, self.port)):
                self.fail('reader_lost')
            self.diag_check()
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
                except Exception:  # Never skips the owned-child cleanup below.
                    self.fail('publication_failure')
            try:
                self.shutdown()
            finally:
                if self.split:
                    self.finish_diagnostics()  # Independently closes every owned pipe/output descriptor.
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
        if self.split:
            archives = self.report['startup_archive_counts'] or []
            self.report['acquisition_and_cleanup_valid'] = bool(
                self.report['acquisition_and_cleanup_valid'] and health.get('version_ok')
                and all((self.report[k] or {}).get('valid') for k in ('cache_before', 'cache_after', 'diagnostics'))
                and len(archives) == len(T07_VALID_GRF) and all(r['valid'] for r in archives)
                and self.report['server_tree']['valid'] and self.report['evidence_tree']['valid'])
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
        emit(sys.stdout, {'status': 'preflight_ok', 'task': meta['route']['task'], 'driver_sha256': driver['sha256'],
                          'profile_sha256': meta['route']['profile_sha256'], 'catalog_sha256': meta['catalog_receipt']['sha256'],
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
    emit(sys.stdout, {'status': 'execute_qualified' if code == 0 else 'execute_failed', 'task': meta['route']['task'],
                      'profile_sha256': meta['route']['profile_sha256'],
                      'halt_reason': observer.halt, 'totals': observer.totals(),
                      'coverage': {k: v for k, v in (observer.report.get('coverage_counts') or {}).items()
                                   if not isinstance(v, dict)},
                      'acquisition_and_cleanup_valid': observer.report['acquisition_and_cleanup_valid']})
    return code


if __name__ == '__main__':
    sys.exit(main())
