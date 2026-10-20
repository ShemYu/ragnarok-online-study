"""Root-operated bounded observation of nested model-texture targets.

T06.003.003.008. --preflight reads only this driver, the pinned profile,
authored controls, the qualified .007 catalog and the 20 pinned rule sources;
it never stats/opens native inputs, launches a process, creates output or
contacts HTTP. --execute requires the exact root-reviewed driver SHA-256, then
performs one owned loopback reader scan of every nested texture target through
an explicit adapter around the pinned, unchanged .005 observer engine.
Results are byte availability plus BMP-prefix/TGA-header observations only,
never image decode, rendering, travel or full-game proof.

Importing this module defines constants and functions only.
"""
import builtins
import hashlib
import json
import math
import os
import re
import stat
import sys
import time

TASK = 'T06.003.003.008'
SCHEMA = 'T06-nested-texture-observation-1'
PROFILE_SCHEMA = 'T06-nested-texture-observation-profile-1'
AUTHORED_SCHEMA = 'T06-nested-texture-observation-authored-1'
PROFILE_REL = 'docs/project/fixtures/T06.003.003.008-profile.json'
PROFILE_BYTES = 7377
PROFILE_SHA = '2ee28e4e4de7d8088d589c5cba663f247b3eb8dcde6348079e19a21be236ce7d'
CATALOG_SCHEMA = 'T06-model-texture-catalog-1'
CATALOG_TASK = 'T06.003.003.007'
ENGINE_REL = 'tools/renewal/observe_map_dependencies.py'
ENGINE_TASK = 'T06.003.003.005'
PROFILE_007_REL = 'docs/project/fixtures/T06.003.003.007-profile.json'
PROFILE_006_REL = 'docs/project/fixtures/T06.003.003.006-profile.json'
SUMMARY_REL = 'tools/renewal/model_constructor_summary.mjs'
CLIENT_PREFIX = '.tools/renewal/client-source/'
SOURCE_PIN_COUNT = 20
POLICY = {
    'body_bytes': 25165824, 'aggregate_bytes_including_health': 8589934592, 'health_bytes': 65536,
    'asset_attempts': 8119, 'health_attempts': 1, 'startup_seconds': 25, 'acquisition_seconds': 1200,
    'io_seconds': 5, 'cache_mb': 64, 'cache_files': 32, 'missing_log_bytes': 16777216,
    'report_bytes': 67108864, 'catalog_bytes': 134217728, 'stdout_bytes': 4096,
    'disk_reserve_bytes': 4294967296, 'root_guard_seconds': 1800, 'root_observed_rss_bytes': 2147483648,
    'metadata_seconds': 120, 'source_bytes': 2097152, 'authored_bytes': 1048576, 'plan_bytes': 16777216}
NATIVE_NAMES = ['binary', 'event.grf', 'data0.grf', 'data.grf']
COUNT_KEYS = ('roots', 'constructor_jobs', 'model_targets', 'returned_jobs', 'returned_empty_jobs',
              'returned_nonempty_jobs', 'constructor_exception_jobs', 'global_declarations',
              'target_expanded_declarations', 'nested_targets', 'model_parent_links',
              'model_placement_occurrences', 'root_expanded_model_placements', 'resolved_node_slots',
              'unresolved_node_slots', 'animation_jobs', 'remaining_core_gap_roots', 'prior_first_level_gaps')
ANIMATION_KEYS = ('true', 'false', 'unknown')
HEADER_KINDS = ('bmp', 'tga', 'unknown')
HEADER_KEEP = {'bmp': 2, 'tga': 18, 'unknown': 18}
PREFIX_KEEP = 18
TGA_FIELDS = (('id_length', 0, 1), ('color_map_type', 1, 1), ('image_type', 2, 1), ('color_map_index', 3, 2),
              ('color_map_length', 5, 2), ('color_map_depth', 7, 1), ('offset_x', 8, 2), ('offset_y', 10, 2),
              ('width', 12, 2), ('height', 14, 2), ('pixel_depth', 16, 1), ('flags', 17, 1))
READ_MAX = 64 << 10
HASH_CHUNK = 4 << 20
WIRE_CHARS = frozenset('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
                       "-._~!$&'()*+,;=:@")
HEX = frozenset('0123456789abcdefABCDEF')
URI_SAFE = frozenset('ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789'
                     "-_.!~*'()")
OUTCOMES = ('complete', 'declared_over_cap', 'cap_unresolved_eof', 'aggregate_cap', 'deadline', 'transport_error')
SHA_RE = re.compile(r'\A[0-9a-f]{64}\Z')
BOUND_API = ('wire_target', 'write_all', 'transfer')


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


def typed_equal(a, b):
    """Deep equality that distinguishes bool/int/float and preserves key order irrelevance."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return a.keys() == b.keys() and all(typed_equal(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_equal(x, y) for x, y in zip(a, b))
    return a == b


# ---------------------------------------------------------------- shared pure API

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
                if len(segment) - i < 3 or segment[i + 1] not in HEX or segment[i + 2] not in HEX:
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


def inspect_texture_header(kind, prefix):
    """Bounded header observation; never decodes payload or allocates from dimensions."""
    if type(kind) is not str or kind not in HEADER_KINDS or type(prefix) is not bytes:
        raise ValueError('invalid header arguments')
    kept = prefix[:HEADER_KEEP[kind]]
    result = {'kind': kind, 'state': None, 'prefix_hex': kept.hex(), 'tga': None}
    if kind == 'unknown':
        result['state'] = 'unclassified'
    elif kind == 'bmp':
        result['state'] = 'short' if len(kept) < 2 else ('match' if kept == b'BM' else 'mismatch')
    elif len(kept) < 18:
        result['state'] = 'short'
    else:
        header = {name: int.from_bytes(kept[at:at + size], 'little') for name, at, size in TGA_FIELDS}
        image_type = header['image_type']
        derived = {'has_encoding': image_type in (9, 10, 11), 'has_color_map': image_type in (1, 9),
                   'is_grey_color': image_type in (3, 11)}
        if derived['has_color_map']:
            palette = (header['color_map_length'] <= 256 and header['color_map_depth'] == 24
                       and header['color_map_type'] == 1)
        else:
            palette = header['color_map_type'] == 0
        checks = {'image_type_nonzero': image_type != 0, 'color_map_consistent': palette,
                  'dimensions_positive': header['width'] > 0 and header['height'] > 0,
                  'pixel_depth_supported': header['pixel_depth'] in (8, 16, 24, 32)}
        result['state'] = 'observed'
        result['tga'] = {'header': header, 'derived': derived, 'checks': checks,
                         'checks_all': all(checks.values())}
    return result


def filemanager_kind(name):
    """Inspection category from the final FileManager basename extension."""
    base = name.replace('\\', '/').rsplit('/', 1)[-1]
    if '.' not in base:
        return 'unknown'
    ext = base.rsplit('.', 1)[1]
    if ext.isascii() and ext.lower() in ('bmp', 'tga'):
        return ext.lower()
    return 'unknown'


def http_from_name(name):
    """FileManager.getHTTP: per-segment UTF-8 encodeURIComponent after slash replacement."""
    parts = []
    for part in name.replace('\\', '/').split('/'):
        try:
            raw = part.encode('utf-8', 'strict')
        except UnicodeError:
            raise Refusal('name_encoding')
        parts.append(''.join(chr(b) if chr(b) in URI_SAFE else '%%%02X' % b for b in raw))
    return '/'.join(parts)


def _counts_ok(counts, expected):
    if not (isinstance(counts, dict) and isinstance(expected, dict) and list(expected) and
            set(expected) == set(COUNT_KEYS) == set(counts)):
        return False
    for key in COUNT_KEYS:
        if key == 'animation_jobs':
            a, b = counts[key], expected[key]
            if not (isinstance(a, dict) and isinstance(b, dict) and set(a) == set(b) == set(ANIMATION_KEYS)
                    and all(is_int(a[k]) and is_int(b[k]) and a[k] == b[k] >= 0 for k in ANIMATION_KEYS)):
                return False
        elif not (is_int(counts[key]) and is_int(expected[key]) and counts[key] == expected[key] >= 0):
            return False
    return True


def build_plan(catalog, expected_counts, deadline=None, clock=None):
    """Metadata-only exact plan: ordered six-key objects for every nested target."""
    clock = time.monotonic if clock is None else clock

    def budget():
        require(deadline is None or clock() < deadline, 'metadata_deadline')
    require(isinstance(catalog, dict), 'catalog_shape')
    counts = catalog.get('counts')
    require(_counts_ok(counts, expected_counts), 'catalog_counts')
    tables = {key: catalog.get(key) for key in ('roots', 'jobs', 'model_targets', 'model_parent_links',
                                                'nested_targets', 'remaining_gap_root_ordinals',
                                                'prior_first_level_gaps')}
    require(all(isinstance(v, list) for v in tables.values()), 'catalog_shape')
    roots, jobs, targets = tables['roots'], tables['jobs'], tables['nested_targets']
    require(len(roots) == counts['roots'] and len(jobs) == counts['constructor_jobs']
            and len(tables['model_targets']) == counts['model_targets']
            and len(tables['model_parent_links']) == counts['model_parent_links']
            and len(targets) == counts['nested_targets']
            and len(tables['remaining_gap_root_ordinals']) == counts['remaining_core_gap_roots']
            and len(tables['prior_first_level_gaps']) == counts['prior_first_level_gaps'], 'catalog_cardinality')
    require(all(isinstance(r, dict) and is_int(r.get('ordinal')) and r['ordinal'] == i for i, r in enumerate(roots)),
            'catalog_roots')
    gaps = tables['remaining_gap_root_ordinals']
    require(all(is_int(g) and 0 <= g < len(roots) for g in gaps) and gaps == sorted(set(gaps)), 'catalog_gaps')
    require(all(isinstance(g, dict) and is_int(g.get('target_index')) for g in tables['prior_first_level_gaps']),
            'catalog_prior_gaps')
    occurrences = expanded = 0
    for i, link in enumerate(tables['model_parent_links']):
        require(isinstance(link, dict) and isinstance(link.get('placement_indexes'), list)
                and isinstance(link.get('root_references'), list), 'catalog_parent')
        occurrences += len(link['placement_indexes'])
        expanded += len(link['placement_indexes']) * len(link['root_references'])
        if i % 4096 == 0:
            budget()
    require(occurrences == counts['model_placement_occurrences']
            and expanded == counts['root_expanded_model_placements'], 'catalog_placements')
    model_refs = 0
    for model in tables['model_targets']:
        require(isinstance(model, dict) and isinstance(model.get('referrers'), list), 'catalog_model_target')
        model_refs += len(model['referrers'])
    require(model_refs == counts['model_parent_links'], 'catalog_model_referrers')
    tally = {'returned': 0, 'exception': 0, 'empty': 0, 'nonempty': 0, 'declarations': 0, 'expanded': 0,
             'resolved': 0, 'unresolved': 0}
    animation = {k: 0 for k in ANIMATION_KEYS}
    forward = {}
    for job_index, job in enumerate(jobs):
        if job_index % 1024 == 0:
            budget()
        require(isinstance(job, dict) and is_int(job.get('source_row_index')) and job['source_row_index'] == job_index,
                'catalog_job')
        models = job.get('target_model_ordinals')
        require(isinstance(models, list) and models, 'catalog_job_models')
        outcome, decls, nodes, anim = job.get('outcome'), job.get('declarations'), job.get('nodes'), \
            job.get('animation_by_node_keys')
        if outcome == 'returned':
            require(job.get('constructor_returned') is True and job.get('exception') is None
                    and isinstance(decls, list) and isinstance(nodes, list) and type(anim) is bool, 'catalog_returned')
            tally['returned'] += 1
            tally['nonempty' if decls else 'empty'] += 1
            animation['true' if anim else 'false'] += 1
        else:
            require(outcome == 'constructor_exception' and job.get('constructor_returned') is False
                    and isinstance(job.get('exception'), dict) and decls is None and nodes is None and anim is None,
                    'catalog_exception_tables')
            tally['exception'] += 1
            animation['unknown'] += 1
            continue
        for node in nodes:
            refs = node.get('texture_references') if isinstance(node, dict) else None
            require(isinstance(refs, list), 'catalog_node')
            for ref in refs:
                require(isinstance(ref, dict) and ref.get('state') in ('resolved', 'unresolved'), 'catalog_slot')
                tally[ref['state']] += 1
        tally['declarations'] += len(decls)
        tally['expanded'] += len(decls) * len(models)
        for position, decl in enumerate(decls):
            require(isinstance(decl, dict) and is_int(decl.get('texture_index')) and decl['texture_index'] == position,
                    'catalog_declaration_index')
            t = decl.get('nested_target_index')
            require(is_int(t) and 0 <= t < len(targets), 'catalog_declaration_target')
            name, http = decl.get('filemanager_name'), decl.get('http_path')
            require(isinstance(name, str) and isinstance(http, str), 'catalog_declaration_name')
            require(http_from_name(name) == http, 'catalog_declaration_http')
            forward[(job_index, position)] = (t, http, filemanager_kind(name))
    require(tally['returned'] == counts['returned_jobs'] and tally['exception'] == counts['constructor_exception_jobs']
            and tally['empty'] == counts['returned_empty_jobs'] and tally['nonempty'] == counts['returned_nonempty_jobs']
            and tally['declarations'] == counts['global_declarations']
            and tally['expanded'] == counts['target_expanded_declarations']
            and tally['resolved'] == counts['resolved_node_slots']
            and tally['unresolved'] == counts['unresolved_node_slots']
            and animation == counts['animation_jobs'], 'catalog_tallies')
    plan, seen_http, backward = [], set(), 0
    for position, target in enumerate(targets):
        if position % 1024 == 0:
            budget()
        require(isinstance(target, dict) and is_int(target.get('index')) and target['index'] == position, 'catalog_target')
        http, refs = target.get('http_path'), target.get('referrers')
        require(isinstance(http, str) and http not in seen_http, 'catalog_target_http')
        seen_http.add(http)
        require(isinstance(refs, list) and refs, 'catalog_referrers')
        kinds, keys, copied = set(), [], []
        for ref in refs:
            require(isinstance(ref, dict) and set(ref) == {'job_index', 'texture_index'}
                    and is_int(ref['job_index']) and is_int(ref['texture_index']), 'catalog_referrer')
            key = (ref['job_index'], ref['texture_index'])
            entry = forward.get(key)
            require(entry is not None and entry[0] == position and entry[1] == http, 'catalog_referrer_join')
            keys.append(key)
            kinds.add(entry[2])
            copied.append({'job_index': key[0], 'texture_index': key[1]})
        require(keys == sorted(set(keys)), 'catalog_referrer_order')
        require(len(kinds) == 1, 'catalog_kind_disagree')
        backward += len(keys)
        try:
            wire = wire_target(http)
        except ValueError:
            raise Refusal('catalog_wire')
        plan.append({'index': position, 'catalog_pointer': '/nested_targets/%d' % position, 'http_path': http,
                     'wire': wire, 'kind': kinds.pop(), 'referrers': copied})
    require(backward == len(forward) == counts['global_declarations'], 'catalog_bijection')
    return plan


# ---------------------------------------------------------------- admission

def check_ancestors(path):
    """Every ancestor of the absolute normalized path is a real directory."""
    require(isinstance(path, str) and os.path.isabs(path) and os.path.normpath(path) == path
            and '\0' not in path, 'path_shape')
    current = '/'
    for part in path.split('/')[1:-1]:
        current = os.path.join(current, part)
        try:
            st = os.lstat(current)
        except FileNotFoundError:
            raise Absent()
        except OSError:
            raise Refusal('ancestor_error')
        require(stat.S_ISDIR(st.st_mode) and not stat.S_ISLNK(st.st_mode), 'ancestor_link')


def check_directory(path):
    """Absolute normalized link-free existing directory."""
    check_ancestors(path)
    try:
        st = os.lstat(path)
    except OSError:
        raise Refusal('directory')
    require(stat.S_ISDIR(st.st_mode), 'directory')


def relative(base, rel):
    require(isinstance(rel, str) and rel and not rel.startswith('/') and '\\' not in rel and '\0' not in rel, 'relative_path')
    require(all(part not in ('', '.', '..') for part in rel.split('/')), 'relative_path')
    return os.path.join(base, rel)


def read_admitted(path, expected_bytes=None, expected_sha=None, keep=True, limit=None, prefix=0, deadline=None,
                  clock=None):
    """Stable single-link regular-file read; returns (data|prefix|None, receipt)."""
    clock = time.monotonic if clock is None else clock
    check_ancestors(path)
    try:
        first = os.lstat(path)
    except FileNotFoundError:
        raise Absent()
    except OSError:
        raise Refusal('admit_stat')
    require(stat.S_ISREG(first.st_mode) and first.st_nlink == 1, 'admit_regular')
    size = first.st_size
    require(expected_bytes is None or size == expected_bytes, 'admit_size')
    require(limit is None or size <= limit, 'admit_limit')
    try:
        fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    except OSError:
        raise Refusal('admit_open')
    try:
        opened = os.fstat(fd)
        require(identity(opened) == identity(first) and stat.S_ISREG(opened.st_mode) and opened.st_nlink == 1,
                'admit_drift')
        digest, chunks, head, left = hashlib.sha256(), [], b'', size
        while left:
            require(deadline is None or clock() < deadline, 'metadata_deadline')
            chunk = os.read(fd, min(HASH_CHUNK, left))
            require(bool(chunk), 'admit_truncated')
            digest.update(chunk)
            if keep:
                chunks.append(chunk)
            if len(head) < prefix:
                head += chunk[:prefix - len(head)]
            left -= len(chunk)
        require(os.read(fd, 1) == b'', 'admit_grew')
        after = os.fstat(fd)
    finally:
        os.close(fd)
    try:
        last = os.lstat(path)
    except OSError:
        raise Refusal('admit_drift')
    require(identity(after) == identity(first) == identity(last) and last.st_nlink == 1, 'admit_drift')
    hexdigest = digest.hexdigest()
    require(expected_sha is None or hexdigest == expected_sha, 'admit_sha')
    receipt = {'bytes': size, 'sha256': hexdigest, 'identity': identity(first)}
    if keep:
        return b''.join(chunks), receipt
    return (head if prefix else None), receipt


def strict_json(data):
    """Strict UTF-8 JSON: no duplicate keys, NaN/Infinity or overflowing numbers."""
    def pairs(items):
        out = {}
        for key, value in items:
            require(key not in out, 'json_duplicate')
            out[key] = value
        return out

    def constant(_):
        raise Refusal('json_nonfinite')

    def finite(text):
        value = float(text)
        require(math.isfinite(value), 'json_nonfinite')
        return value
    try:
        return json.loads(data.decode('utf-8', 'strict'), object_pairs_hook=pairs, parse_constant=constant,
                          parse_float=finite)
    except (UnicodeDecodeError, ValueError, RecursionError):
        raise Refusal('json_invalid')


def _driver_path():
    return os.path.normpath(os.path.abspath(__file__))


def own_sha():
    _, receipt = read_admitted(_driver_path(), keep=False, limit=POLICY['source_bytes'])
    return receipt


def load_engine(source_bytes, engine_path):
    """Execute exact admitted .005 bytes in a fresh non-main namespace; bind only the pure API."""
    require(type(source_bytes) is bytes, 'engine_bytes')
    code = compile(source_bytes, '<T06.003.003.005-engine>', 'exec', dont_inherit=True)
    namespace = {'__name__': '_t06_005_engine_' + sha(source_bytes)[:12], '__file__': engine_path,
                 '__builtins__': builtins}
    exec(code, namespace)  # Pinned bytes only; never sys.modules, never main/load_metadata.
    require(namespace.get('TASK') == ENGINE_TASK and namespace.get('NATIVE_NAMES') == NATIVE_NAMES, 'engine_identity')
    own = {'wire_target': wire_target, 'write_all': write_all, 'transfer': transfer}
    for name in BOUND_API:
        require(callable(namespace.get(name)), 'engine_api')
        namespace[name] = own[name]
    observer = namespace['Observer']
    require(observer.request.__globals__ is namespace and observer.create_private.__globals__ is namespace,
            'engine_namespace')
    require(all(namespace[name] is own[name] for name in BOUND_API), 'engine_binding')
    return namespace


def native_specs(meta):
    home = os.path.normpath(os.path.expanduser('~'))
    require(os.path.isabs(home), 'home')
    out = []
    for item in meta['profile']['native']:
        base = home if item['base'] == 'home' else meta['input_root']
        out.append({'name': item['name'], 'path': relative(base, item['path']), 'bytes': item['bytes'],
                    'sha256': item['sha256']})
    return out


def _pin_ok(pin):
    return (isinstance(pin, dict) and set(pin) == {'path', 'bytes', 'sha256'} and isinstance(pin['path'], str)
            and is_int(pin['bytes']) and pin['bytes'] >= 0 and isinstance(pin['sha256'], str)
            and SHA_RE.match(pin['sha256']) is not None)


def validate_profile(profile):
    require(isinstance(profile, dict) and profile.get('schema') == PROFILE_SCHEMA and profile.get('task') == TASK,
            'profile_identity')
    require(typed_equal(profile.get('policy'), POLICY), 'profile_policy')
    require(_pin_ok(profile.get('catalog')) and _pin_ok(profile.get('authored')), 'profile_pins')
    require(profile['catalog']['bytes'] <= POLICY['catalog_bytes']
            and profile['authored']['bytes'] <= POLICY['authored_bytes'], 'profile_caps')
    pins = profile.get('source_pins')
    require(isinstance(pins, list) and len(pins) == SOURCE_PIN_COUNT and all(_pin_ok(p) for p in pins)
            and len({p['path'] for p in pins}) == SOURCE_PIN_COUNT
            and all(p['bytes'] <= POLICY['source_bytes'] for p in pins), 'profile_sources')
    paths = [p['path'] for p in pins]
    require(all(rel in paths for rel in (ENGINE_REL, PROFILE_007_REL, PROFILE_006_REL, SUMMARY_REL)), 'profile_sources')
    native = profile.get('native')
    require(isinstance(native, list) and [n.get('name') for n in native if isinstance(n, dict)] == NATIVE_NAMES
            and all(n.get('base') in ('home', 'input_root') and isinstance(n.get('path'), str)
                    and is_int(n.get('bytes')) and isinstance(n.get('sha256'), str) for n in native), 'profile_native')
    require(_counts_ok(profile.get('expected_catalog_counts'), profile.get('expected_catalog_counts')), 'profile_counts')
    kinds = profile.get('expected_kind_counts')
    require(isinstance(kinds, dict) and list(kinds) == list(HEADER_KINDS) and all(is_int(v) for v in kinds.values())
            and sum(kinds.values()) == profile['expected_catalog_counts']['nested_targets']
            == POLICY['asset_attempts'], 'profile_kinds')
    require(isinstance(profile.get('limitations'), list) and all(isinstance(x, str) for x in profile['limitations']),
            'profile_limitations')


def validate_catalog_envelope(catalog, profile, pins, prior):
    """Exact .007 file-envelope bindings; the pure plan checks the tables."""
    require(isinstance(catalog, dict) and catalog.get('schema') == CATALOG_SCHEMA and catalog.get('task') == CATALOG_TASK
            and catalog.get('mode') == 'corpus', 'catalog_identity')
    require(catalog.get('profile_sha256') == pins[PROFILE_007_REL]['sha256']
            and catalog.get('constructor_profile_sha256') == pins[PROFILE_006_REL]['sha256']
            and catalog.get('summary_sha256') == pins[SUMMARY_REL]['sha256'], 'catalog_binding')
    require(prior.get('task') == CATALOG_TASK and isinstance(prior.get('inputs'), dict)
            and typed_equal(catalog.get('input_pins'), prior['inputs']), 'catalog_input_pins')
    require(typed_equal(prior.get('constructor_profile'), dict(pins[PROFILE_006_REL]))
            and typed_equal(prior.get('summary'), dict(pins[SUMMARY_REL])), 'catalog_prior_binding')
    rules = catalog.get('rule_sources')
    require(isinstance(rules, dict) and rules and typed_equal(rules, prior.get('rule_sources')), 'catalog_rule_sources')
    for rel, pin in rules.items():
        mine = pins.get(CLIENT_PREFIX + rel)
        require(mine is not None and typed_equal(pin, {'bytes': mine['bytes'], 'sha256': mine['sha256']}),
                'catalog_rule_sources')
    require(typed_equal(catalog.get('counts'), profile['expected_catalog_counts'])
            and typed_equal(prior.get('expected_counts'), profile['expected_catalog_counts']), 'catalog_counts')
    require(typed_equal(catalog.get('limits'), prior.get('limitations')), 'catalog_limits')


def load_metadata(input_root, profile_path, clock=None):
    """Metadata-only admission; never touches native inputs, processes, output or HTTP."""
    clock = time.monotonic if clock is None else clock
    deadline = clock() + POLICY['metadata_seconds']
    require(isinstance(input_root, str) and os.path.isabs(input_root) and os.path.normpath(input_root) == input_root,
            'input_root')
    try:
        check_directory(input_root)
    except Absent:
        raise Refusal('input_root')
    require(profile_path == PROFILE_REL, 'profile_path')
    driver = own_sha()
    profile_abs = relative(input_root, profile_path)
    profile_bytes, profile_receipt = read_admitted(profile_abs, PROFILE_BYTES, PROFILE_SHA, deadline=deadline,
                                                   clock=clock)
    profile = strict_json(profile_bytes)
    validate_profile(profile)
    apin = profile['authored']
    authored_bytes, authored_receipt = read_admitted(relative(input_root, apin['path']), apin['bytes'], apin['sha256'],
                                                     limit=POLICY['authored_bytes'], deadline=deadline, clock=clock)
    authored = strict_json(authored_bytes)
    require(isinstance(authored, dict) and authored.get('schema') == AUTHORED_SCHEMA
            and authored.get('status') == 'FROZEN_ROOT_REVIEWED', 'authored_identity')
    sources, kept, pins = [], {}, {}
    for pin in profile['source_pins']:
        data, receipt = read_admitted(relative(input_root, pin['path']), pin['bytes'], pin['sha256'],
                                      limit=POLICY['source_bytes'], deadline=deadline, clock=clock)
        sources.append(dict(path=pin['path'], **receipt))
        pins[pin['path']] = {'path': pin['path'], 'bytes': pin['bytes'], 'sha256': pin['sha256']}
        if pin['path'] in (ENGINE_REL, PROFILE_007_REL):
            kept[pin['path']] = data
    prior = strict_json(kept[PROFILE_007_REL])
    require(isinstance(prior, dict), 'prior_profile')
    cpin = profile['catalog']
    catalog_path = relative(input_root, cpin['path'])
    catalog_bytes, catalog_receipt = read_admitted(catalog_path, cpin['bytes'], cpin['sha256'],
                                                   limit=POLICY['catalog_bytes'], deadline=deadline, clock=clock)
    catalog = strict_json(catalog_bytes)
    require(clock() < deadline, 'metadata_deadline')
    validate_catalog_envelope(catalog, profile, pins, prior)
    plans = build_plan(catalog, profile['expected_catalog_counts'], deadline=deadline, clock=clock)
    kind_counts = {k: sum(p['kind'] == k for p in plans) for k in HEADER_KINDS}
    require(typed_equal(kind_counts, profile['expected_kind_counts']), 'plan_kinds')
    plan_bytes = len(json.dumps(plans, ensure_ascii=True, allow_nan=False, separators=(',', ':')))
    require(plan_bytes <= POLICY['plan_bytes'], 'plan_size')
    engine_path = relative(input_root, ENGINE_REL)
    engine = load_engine(kept[ENGINE_REL], engine_path)
    meta = {'input_root': input_root, 'profile_path': profile_abs, 'profile': profile,
            'profile_receipt': profile_receipt, 'authored_receipt': authored_receipt, 'sources': sources,
            'catalog_bytes': catalog_bytes, 'catalog_receipt': catalog_receipt, 'catalog_path': catalog_path,
            'catalog': catalog, 'plans': plans, 'referrers': sum(len(p['referrers']) for p in plans),
            'gaps': list(catalog['remaining_gap_root_ordinals']), 'kind_counts': kind_counts,
            'plan_bytes': plan_bytes, 'driver_receipt': driver, 'engine': engine,
            'engine_pin': dict(pins[ENGINE_REL]), 'authored': authored}
    meta['recheck'] = recheck_list(meta)
    verify_recheck(meta['recheck'], deadline=deadline, clock=clock)  # Rehash after plan construction.
    return meta


def recheck_list(meta):
    """Every admitted metadata file: own driver, profile, authored, catalog and source pins."""
    root = meta['input_root']
    items = [dict(path=_driver_path(), **meta['driver_receipt']),
             dict(path=meta['profile_path'], **meta['profile_receipt']),
             dict(path=relative(root, meta['profile']['authored']['path']), **meta['authored_receipt']),
             dict(path=meta['catalog_path'], **meta['catalog_receipt'])]
    items.extend(dict(s, path=relative(root, s['path'])) for s in meta['sources'])
    return items


def verify_recheck(items, deadline=None, clock=None):
    for item in items:
        _, receipt = read_admitted(item['path'], item['bytes'], item['sha256'], keep=False, deadline=deadline,
                                   clock=clock)
        require(receipt['identity'] == item['identity'], 'recheck_identity')


# ---------------------------------------------------------------- execute adapter

def unattempted(plan, reason):
    return {'target_index': plan['index'], 'catalog_pointer': plan['catalog_pointer'],
            'referrers_pointer': plan['catalog_pointer'] + '/referrers', 'http_path': plan['http_path'],
            'attempted': False, 'request_index': None, 'wire_target': plan['wire'],
            'started_elapsed_seconds': None, 'finished_elapsed_seconds': None, 'http_status': None, 'headers': None,
            'wire_bytes': 0, 'wire_complete': False, 'stop_reason': reason,
            'stored': {'file': None, 'bytes': None, 'sha256': None, 'complete': False, 'error': None},
            'header': {'kind': plan['kind'], 'state': 'not_checked', 'prefix_hex': None, 'tga': None}}


def default_container():
    return os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(_driver_path()))), '.tools', 'renewal')


_CLASSES = {}


def _observer_class(engine):
    """Explicit adapter over the admitted engine's Observer; cached per fresh namespace."""
    key = id(engine)
    if key in _CLASSES and _CLASSES[key][0] is engine:
        return _CLASSES[key][1]
    base, Fatal = engine['Observer'], engine['Fatal']
    caught = (Refusal, Absent, engine['Refusal'], engine['Absent'])

    class TextureObserver(base):
        def __init__(self, meta, output, driver, ops=None, natives=None, policy=None, container=None, write_fn=None):
            super().__init__(meta, output, driver, ops=ops, natives=natives, policy=policy, container=container,
                             write_fn=write_fn)
            catalog = meta['catalog']
            self.report = {
                'schema': SCHEMA, 'task': TASK, 'mode': 'execute',
                'driver_pin': {'bytes': driver['bytes'], 'sha256': driver['sha256']},
                'profile_pin': {'bytes': meta['profile_receipt']['bytes'], 'sha256': meta['profile_receipt']['sha256']},
                'authored_pin': {'bytes': meta['authored_receipt']['bytes'],
                                 'sha256': meta['authored_receipt']['sha256']},
                'catalog_pin': {'bytes': meta['catalog_receipt']['bytes'], 'sha256': meta['catalog_receipt']['sha256']},
                'engine_pin': dict(meta['engine_pin'], bound_api=list(BOUND_API)),
                'catalog_refs': {
                    'file': 'catalog-input.json', 'targets_pointer': '/nested_targets', 'roots_pointer': '/roots',
                    'jobs_pointer': '/jobs', 'model_targets_pointer': '/model_targets',
                    'parents_pointer': '/model_parent_links', 'prior_gaps_pointer': '/prior_first_level_gaps',
                    'roots': len(catalog['roots']), 'targets': len(meta['plans']), 'referrers': meta['referrers'],
                    'gap_root_ordinals': list(meta['gaps']), 'counts': catalog['counts'],
                    'kind_counts': meta['kind_counts']},
                'header_api': {'retained_prefix_bytes': dict(HEADER_KEEP), 'image_decode': 'untested',
                               'render': 'untested', 'playability': 'untested'},
                'native_before': None, 'native_after': None,
                'sources_before': self._source_receipts(meta), 'sources_after': None,
                'launch': None, 'health': None, 'totals': None,
                'targets': [unattempted(p, 'not_started') for p in meta['plans']],
                'missing_log': None, 'tree': None, 'cleanup': None, 'coverage_counts': None,
                'halt_reason': None, 'errors': self.errors, 'records_complete': False,
                'all_targets_attempted': False, 'postchecks_valid': False, 'acquisition_and_cleanup_valid': False,
                'limitations': list(meta['profile']['limitations'])}
            self.freezes = 0

        @staticmethod
        def _source_receipts(meta):
            return {'driver': meta['driver_receipt'], 'profile': meta['profile_receipt'],
                    'authored': meta['authored_receipt'], 'catalog': meta['catalog_receipt'],
                    'sources': meta['sources']}

        # -- provenance freeze before every persisted checkpoint
        def freeze(self):
            report = self.report
            report.update(schema=SCHEMA, task=TASK, mode='execute')
            if report.get('launch') is not None:
                report['launch']['profile_sha256'] = PROFILE_SHA
                report['launch']['task'] = TASK
            refs = report['catalog_refs']
            ok = (report['profile_pin']['sha256'] == PROFILE_SHA and refs['targets_pointer'] == '/nested_targets'
                  and len(report['targets']) == len(self.meta['plans']))
            for row, plan in zip(report['targets'], self.meta['plans']):
                ok = ok and ('signature' not in row and row.get('header', {}).get('kind') == plan['kind']
                             and row['target_index'] == plan['index'] and row['catalog_pointer'] == plan['catalog_pointer']
                             and row['wire_target'] == plan['wire'])
            if not ok:
                raise Fatal('provenance_failure')
            self.freezes += 1

        def checkpoint(self):
            self.freeze()
            super().checkpoint()

        # -- admission supplements
        def hash_natives(self):
            out = {}
            for spec in self.natives:
                _, receipt = read_admitted(spec['path'], spec['bytes'], spec['sha256'], keep=False)
                out[spec['name']] = dict(receipt, name=spec['name'])
            return out

        def verify_stored(self, record, result, written):
            stored = record['stored']
            try:
                prefix, receipt = read_admitted(self.path(stored['file']), keep=False, limit=self.policy['body_bytes'],
                                                prefix=PREFIX_KEEP)
                st = os.lstat(self.path(stored['file']))
            except caught + (OSError,):
                stored.update(bytes=None, sha256=None, complete=False, error=stored['error'] or 'verify_failed')
                self.stored_unknown = True
                self.fail('storage_failure', 'stored_verify_failed')
                return
            stored.update(bytes=receipt['bytes'], sha256=receipt['sha256'])
            good = (result is not None and stored['error'] is None and st.st_nlink == 1
                    and stat.S_IMODE(st.st_mode) == 0o600 and receipt['bytes'] == result['bytes'] == written
                    and receipt['sha256'] == (result['complete_sha256'] or result['partial_sha256']))
            stored['complete'] = bool(good and result['response_complete'])
            if result is not None and not good and stored['error'] is None:
                stored['error'] = 'stored_mismatch'
                self.fail('storage_failure', 'stored_mismatch')
            self.stored_total += receipt['bytes']
            record['_prefix'] = prefix[:PREFIX_KEEP]

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
            if outcome == 'complete' and status == 200 and record['stored']['complete'] and prefix is not None:
                record['header'] = inspect_texture_header(kind, bytes(prefix))
            if outcome == 'aggregate_cap':
                self.fail('aggregate_cap')
            elif outcome == 'deadline' or result['late']:
                self.fail('acquisition_deadline')

        def health(self):
            record = {'attempted': False, 'request_index': None, 'http_status': None, 'headers': None, 'wire_bytes': 0,
                      'wire_complete': False, 'stop_reason': None, 'started_elapsed_seconds': None,
                      'finished_elapsed_seconds': None,
                      'stored': {'file': None, 'bytes': None, 'sha256': None, 'complete': False, 'error': None},
                      'status_ok': False, 'service_ok': False, 'valid': False}
            self.report['health'] = record
            self.health_attempts += 1
            result = self.request('/api/health', self.policy['health_bytes'], record)
            record.pop('_prefix', None)
            if (result is None or result['outcome'] != 'complete' or record['http_status'] != 200
                    or not record['stored']['complete']):
                if result is not None:
                    record['stop_reason'] = result['outcome']
                    if result['late']:
                        self.fail('acquisition_deadline')
                raise Fatal('health_failure')
            record['stop_reason'] = 'complete'
            try:
                data, _ = read_admitted(self.path(record['stored']['file']), record['stored']['bytes'],
                                        record['stored']['sha256'])
                body = strict_json(data)
            except caught:
                raise Fatal('health_failure')
            record['status_ok'] = isinstance(body, dict) and body.get('status') == 'ok'
            record['service_ok'] = isinstance(body, dict) and body.get('service') == 'robrowser-remoteclient'
            record['valid'] = record['status_ok'] and record['service_ok']
            if result['late']:
                raise Fatal('acquisition_deadline')
            if not record['valid']:
                raise Fatal('health_failure')

        def audit_tree(self):
            super().audit_tree()
            audit = self.report['tree']
            try:
                read_admitted(self.path('catalog-input.json'), self.meta['catalog_receipt']['bytes'],
                              self.meta['catalog_receipt']['sha256'], keep=False)
            except caught:
                audit['catalog_copy_exact'] = False
                audit['valid'] = False
                audit['error'] = audit['error'] or 'catalog_copy'

        def postchecks(self):
            ok = True
            try:
                after = self.hash_natives()
                self.report['native_after'] = after
                ok = after == self.native_before and len(after) == len(NATIVE_NAMES)
            except caught:
                self.report['native_after'] = None
                ok = False
            try:
                verify_recheck(self.meta['recheck'])
                self.report['sources_after'] = self._source_receipts(self.meta)
                ok = ok and own_sha() == self.driver == self.meta['driver_receipt']
                ok = ok and all(self.engine_bound().values())
            except caught:
                self.report['sources_after'] = None
                ok = False
            return ok

        def engine_bound(self):
            return {name: base.request.__globals__.get(name) is globals()[name] for name in BOUND_API}

        def coverage(self):
            counts = {'transfer': {}, 'stop_reason': {}, 'http_status': {}, 'header_states': {},
                      'tga_header_checks': {'observed': 0, 'all_true': 0, 'any_false': 0},
                      'stored_complete': 0, 'storage_error': 0, 'complete_200_bytes_available': 0,
                      'http_404': 0, 'other_http': 0, 'redirect': 0, 'empty_200': 0, 'html_200': 0,
                      'cap': 0, 'transport': 0, 'unattempted': 0, 'attempted': 0}
            for r in self.report['targets']:
                counts['stop_reason'][r['stop_reason']] = counts['stop_reason'].get(r['stop_reason'], 0) + 1
                header = r['header']
                key = header['kind'] + ':' + header['state']
                counts['header_states'][key] = counts['header_states'].get(key, 0) + 1
                if header['tga'] is not None:
                    counts['tga_header_checks']['observed'] += 1
                    counts['tga_header_checks']['all_true' if header['tga']['checks_all'] else 'any_false'] += 1
                if not r['attempted']:
                    counts['unattempted'] += 1
                    continue
                counts['attempted'] += 1
                counts['stored_complete'] += r['stored']['complete']
                counts['storage_error'] += r['stored']['error'] is not None
                if r['stop_reason'] in OUTCOMES or r['stop_reason'] in ('http_404', 'redirect', 'http_status',
                                                                        'empty_200', 'html_200'):
                    key = r['stop_reason'] if r['stop_reason'] in OUTCOMES else 'complete'
                    counts['transfer'][key] = counts['transfer'].get(key, 0) + 1
                status = r['http_status']
                if status is not None:
                    counts['http_status'][str(status)] = counts['http_status'].get(str(status), 0) + 1
                if status == 404:
                    counts['http_404'] += 1
                elif status is not None and status != 200:
                    counts['other_http'] += 1
                    counts['redirect'] += 300 <= status < 400
                counts['empty_200'] += r['stop_reason'] == 'empty_200'
                counts['html_200'] += r['stop_reason'] == 'html_200'
                counts['complete_200_bytes_available'] += (r['stop_reason'] == 'complete' and status == 200
                                                           and r['stored']['complete'] and r['stored']['bytes'] > 0)
                counts['cap'] += r['stop_reason'] in ('declared_over_cap', 'cap_unresolved_eof')
                counts['transport'] += r['stop_reason'] in ('transport_error', 'timeout', 'connection_setup_error',
                                                            'malformed_header')
            return counts

        def run(self):
            """Returns exit status: 0 qualified, 1 retained failure, 2 refusal before output."""
            try:
                self.admit_output()
            except caught + (OSError,):
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
            except caught as exc:
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

    _CLASSES[key] = (engine, TextureObserver)
    return TextureObserver


def make_observer(meta, output, driver, ops=None, natives=None, policy=None, container=None, write_fn=None):
    """Production observer; ops/natives/policy/container/write_fn are fake-test seams only."""
    cls = _observer_class(meta['engine'])
    return cls(meta, output, driver, ops=ops, natives=natives if natives is not None else native_specs(meta),
               policy=dict(POLICY if policy is None else policy),
               container=default_container() if container is None else container, write_fn=write_fn)


# ---------------------------------------------------------------- CLI

def emit(stream, payload):
    data = json.dumps(payload, sort_keys=True, ensure_ascii=True, allow_nan=False)
    if len(data) + 1 > POLICY['stdout_bytes']:
        data = json.dumps({'status': payload.get('status', 'refused'), 'reason': 'output_bound'})
    stream.write(data + '\n')
    stream.flush()


VALUE_FLAGS = ('--input-root', '--profile', '--output', '--root-reviewed-sha256')
MODE_FLAGS = ('--preflight', '--execute')


def parse(argv):
    """Exactly one mode; unknown, duplicate, missing or mixed flags refuse."""
    require(isinstance(argv, list) and all(type(a) is str for a in argv), 'usage')
    seen, i = {}, 0
    while i < len(argv):
        flag = argv[i]
        require(flag not in seen, 'usage')
        if flag in MODE_FLAGS:
            seen[flag] = True
            i += 1
        elif flag in VALUE_FLAGS:
            require(i + 1 < len(argv) and not argv[i + 1].startswith('--'), 'usage')
            seen[flag] = argv[i + 1]
            i += 2
        else:
            raise Refusal('usage')
    modes = [m for m in MODE_FLAGS if m in seen]
    require(len(modes) == 1 and '--input-root' in seen and '--profile' in seen, 'usage')
    execute = modes[0] == '--execute'
    extra = ('--output' in seen, '--root-reviewed-sha256' in seen)
    require(extra == ((True, True) if execute else (False, False)), 'usage')
    if execute:
        output = seen['--output']
        require(os.path.isabs(output) and os.path.normpath(output) == output, 'usage')
        require(SHA_RE.match(seen['--root-reviewed-sha256']) is not None, 'usage')
    return {'execute': execute, 'input_root': seen['--input-root'], 'profile': seen['--profile'],
            'output': seen.get('--output'), 'reviewed': seen.get('--root-reviewed-sha256')}


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    try:
        args = parse(argv)
        driver = own_sha()
        if args['execute']:
            require(args['reviewed'] == driver['sha256'], 'driver_sha')  # Before any output/native access.
        meta = load_metadata(args['input_root'], args['profile'])
        require(meta['driver_receipt'] == driver, 'driver_drift')
    except (Refusal, Absent) as exc:
        emit(sys.stdout, {'status': 'refused', 'reason': exc.args[0] if exc.args else 'absent'})
        return 2
    except Exception:
        emit(sys.stdout, {'status': 'refused', 'reason': 'internal'})
        return 2
    counts = {'roots': len(meta['catalog']['roots']), 'jobs': len(meta['catalog']['jobs']),
              'targets': len(meta['plans']), 'referrers': meta['referrers'], 'gap_roots': len(meta['gaps']),
              'prior_gaps': len(meta['catalog']['prior_first_level_gaps']), 'source_pins': len(meta['sources']),
              'kinds': meta['kind_counts'], 'plan_bytes': meta['plan_bytes']}
    if not args['execute']:
        emit(sys.stdout, {'status': 'preflight_ok', 'task': TASK, 'driver_sha256': driver['sha256'],
                          'profile_sha256': PROFILE_SHA, 'catalog_sha256': meta['catalog_receipt']['sha256'],
                          'engine_sha256': meta['engine_pin']['sha256'], 'counts': counts,
                          'native_qualification': None, 'native_or_network_or_process': False})
        return 0
    observer = None
    try:
        observer = make_observer(meta, args['output'], driver)
        code = observer.run()
    except Exception:
        code = 1
    if code == 2:
        emit(sys.stdout, {'status': 'refused', 'reason': 'output_admission'})
        return 2
    report = observer.report if observer is not None else {}
    emit(sys.stdout, {'status': 'execute_qualified' if code == 0 else 'execute_failed', 'task': TASK,
                      'halt_reason': observer.halt if observer is not None else 'internal',
                      'coverage': {k: v for k, v in (report.get('coverage_counts') or {}).items()
                                   if not isinstance(v, dict)},
                      'acquisition_and_cleanup_valid': bool(report.get('acquisition_and_cleanup_valid'))})
    return code


if __name__ == '__main__':
    sys.exit(main())
