"""Root-operated bounded observation of nested model-texture targets.

T06.003.003.008. --preflight reads only this driver, the pinned profile,
authored controls, the qualified .007 catalog and the 20 pinned rule sources;
it never stats/opens native inputs, launches a process, creates output or
contacts HTTP. --execute requires the exact root-reviewed driver SHA-256, then
performs one owned loopback reader scan of every nested texture target through
an explicit adapter around the pinned, unchanged .005 observer engine.
Results are byte availability plus BMP-prefix/TGA-header observations only,
never image decode, rendering, travel or full-game proof.

T07.007.010 adds exactly one second trusted profile route, selected by its
exact relative path and then exact bytes/SHA-256 before parse. It plans the 178
nested targets of the qualified .009 four-root catalog and executes through a
minimal subclass of the CURRENT engine Observer (split served root, piped
diagnostics, cache probes) in a fresh namespace with four bound functions.
The legacy route, its engine binding and its API are unchanged.

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
    require(deadline is None or clock() < deadline, 'metadata_deadline')
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
    except OSError:
        raise Refusal('admit_read') from None
    finally:
        try:
            os.close(fd)
        except OSError:
            raise Refusal('admit_close') from None
    try:
        last = os.lstat(path)
    except OSError:
        raise Refusal('admit_drift')
    require(identity(after) == identity(first) == identity(last) and last.st_nlink == 1, 'admit_drift')
    hexdigest = digest.hexdigest()
    require(expected_sha is None or hexdigest == expected_sha, 'admit_sha')
    receipt = {'bytes': size, 'sha256': hexdigest, 'identity': identity(first)}
    data = b''.join(chunks) if keep else (head if prefix else None)
    require(deadline is None or clock() < deadline, 'metadata_deadline')
    return data, receipt


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
    require(clock() < deadline, 'metadata_deadline')
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

        def audit_missing_log(self):
            try:
                super().audit_missing_log()
            except OSError:
                # The unchanged engine reader can raise on a read/close error.
                # Retain the completed target tail and cleanup in a failed report.
                self.report['missing_log']['valid'] = False
                self.report['missing_log']['error'] = 'log_read_or_close'

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


# ---------------------------------------------------------------- T07.007.010 route

T07_TASK = 'T07.007.010'
T07_PROFILE_REL = 'docs/project/fixtures/T07.007.010-profile.json'
T07_PROFILE_BYTES = 10533
T07_PROFILE_SHA = 'ebbed64ccdba8628f3eb5d2562649e1d6926a85281b09f5bf3e7ec65cb58cb8f'
T07_PROFILE_KEYS = ('schema', 'task', 'basis_revision', 'catalog', 'authored', 'source_pins', 'expected_catalog_counts',
                    'expected_kind_counts', 'native', 'policy', 'limitations', 'catalog_producer', 'constructor_producer',
                    'engine_profile')
T07_BASIS = '09b80b1cc79cd9a28cdbb3ed3921d2cc7755518a'
T07_CATALOG_TASK = 'T07.007.009'
T07_CATALOG_PIN = {'path': '.tools/renewal/t07-007-009-integrated-new-corpus-a-1/catalog.json', 'bytes': 1346475,
                   'sha256': '9b7bca8176959ce25b05c090a75cf5b815945bc2480121675331515f9e2c1bd2'}
T07_AUTHORED_PIN = {'path': 'docs/project/fixtures/T06.003.003.008-authored.json', 'bytes': 93233,
                    'sha256': 'f73199757a34481e25107bce006251f1ebf7928ee4e6c752c677c047a8d1bdb3'}
T07_PRODUCER_REL = 'tools/renewal/catalog_model_textures.mjs'
T07_PROFILE_009_REL = 'docs/project/fixtures/T07.007.009-profile.json'
T07_PROFILE_008_REL = 'docs/project/fixtures/T07.007.008-profile.json'
T07_PROFILE_006_REL = 'docs/project/fixtures/T07.007.006-profile.json'
T07_CONSTRUCTOR_PROGRAM_REL = 'tools/renewal/probe_model_constructors.mjs'
T07_CONSTRUCTOR_WORKER_REL = 'tools/renewal/model_constructor_worker.mjs'
T07_RULE_RELS = ('src/Loaders/Model.js', 'src/Loaders/MapLoader.js', 'src/Core/FileManager.js',
                 'src/Renderer/Map/AnimatedModels.js')
T07_SOURCE_PATHS = (
    ENGINE_REL, T07_PRODUCER_REL, T07_PROFILE_009_REL, T07_PROFILE_008_REL, SUMMARY_REL,
    CLIENT_PREFIX + 'src/Loaders/Model.js', CLIENT_PREFIX + 'src/Loaders/MapLoader.js',
    CLIENT_PREFIX + 'src/Core/FileManager.js', CLIENT_PREFIX + 'src/Renderer/Map/AnimatedModels.js',
    CLIENT_PREFIX + 'src/Utils/Texture.js', CLIENT_PREFIX + 'src/Loaders/Targa.js',
    '.tools/renewal/remote-source/src/client.rs', '.tools/renewal/remote-source/src/config.rs',
    '.tools/renewal/remote-source/src/routes.rs', '.tools/renewal/remote-source/src/http.rs',
    '.tools/renewal/remote-source/src/cache.rs', '.tools/renewal/remote-source/src/util.rs',
    '.tools/renewal/remote-source/src/index.rs', '.tools/renewal/remote-source/src/grf.rs',
    '.tools/renewal/remote-source/src/encoding.rs', T07_CONSTRUCTOR_PROGRAM_REL, T07_CONSTRUCTOR_WORKER_REL,
    T07_PROFILE_006_REL)
# Exact role pins; the remaining descriptors are bound by the profile's full SHA-256.
T07_ROLE_PINS = {
    ENGINE_REL: (112136, '0e691c1e93b726cf2819f473745864469d7c2c49aebe89c0b4115f2bd7722750'),
    T07_PRODUCER_REL: (77142, '1161cd5cf80ab0ea99212e1e96e4c2073ed8b7b1efbbeb634db0fa0ffbb6d991'),
    T07_PROFILE_009_REL: (4711, 'c8e0a1aa853afa34088c4abca193addc5e8e66db0621fd950733b9d3339a7787'),
    T07_PROFILE_008_REL: (4168, 'cc53e3455c1117c5fc29431c342f925d4d58d5334bbe5d0c29f67d8489050dea'),
    SUMMARY_REL: (6452, 'ec51b8b2b4930db840503601911c1e0e5f6e6b4db641fa7ae1f85fdf6de13d5c'),
    T07_CONSTRUCTOR_PROGRAM_REL: (105504, '02079022287d188486c90cfb8380a22fa4f04a636c27bbca9606d569fdfb5d23'),
    T07_CONSTRUCTOR_WORKER_REL: (11388, 'c1eee8dabacf3e69bb2fbe7fde8ed4e5fbd386a4a3ac768936484beceb22a3f4'),
    T07_PROFILE_006_REL: (9680, '0615c6d9e6e7990acc3f9012d2028115fce0543bd5fe298bfb544953865db5c6')}
T07_CATALOG_PRODUCER = {'task': T07_CATALOG_TASK, 'commit': T07_BASIS,
                        'program': {'path': T07_PRODUCER_REL, 'bytes': 77142,
                                    'sha256': T07_ROLE_PINS[T07_PRODUCER_REL][1]}}
T07_CONSTRUCTOR_PRODUCER = {'task': 'T07.007.008', 'commit': '31e16bf669cd67a0a0f114d1abc02a753c38868e',
                            'program': {'path': T07_CONSTRUCTOR_PROGRAM_REL, 'bytes': 105504,
                                        'sha256': T07_ROLE_PINS[T07_CONSTRUCTOR_PROGRAM_REL][1]},
                            'worker': {'path': T07_CONSTRUCTOR_WORKER_REL, 'bytes': 11388,
                                       'sha256': T07_ROLE_PINS[T07_CONSTRUCTOR_WORKER_REL][1]}}
T07_ENGINE_PROFILE = {'path': T07_PROFILE_006_REL, 'bytes': 9680, 'sha256': T07_ROLE_PINS[T07_PROFILE_006_REL][1]}
T07_POLICY = dict(POLICY, asset_attempts=178, cache_mb=0, cache_files=0, cache_attempts=2, cache_bytes=65536,
                  diagnostic_bytes=16777216)
T07_NATIVE_NAMES = ['binary', '2026-08-25_live_client_4340_4349_1787295394.gpf',
                    '2026-08-25_live_client_4353_4353_1787535130.gpf', 'event.grf', 'data0.grf', 'data.grf']
# Exact ordered input_root descriptors; strings only during preflight.
T07_NATIVE_TABLE = [
    {'name': 'binary', 'base': 'input_root', 'path': '.tools/renewal/t07-007-native-artifact-admission-1/reader',
     'bytes': 2079536, 'sha256': 'ee6b328ec73a591b23b514379e1b34e876b5d860d0e1aa4d9aa15dd7173eb1c1'},
    {'name': T07_NATIVE_NAMES[1], 'base': 'input_root',
     'path': '.tools/renewal/t07-007-patch-acquisition-root-1/' + T07_NATIVE_NAMES[1],
     'bytes': 306097616, 'sha256': '70725f6624f947c3096066cc66a07fcd2440adf94137b79561ed2d67843f9f0e'},
    {'name': T07_NATIVE_NAMES[2], 'base': 'input_root',
     'path': '.tools/renewal/t07-007-patch-acquisition-root-1/' + T07_NATIVE_NAMES[2],
     'bytes': 86992, 'sha256': '03764f614453d2b453a5ab5b552f6af9f66599a3642943566f72cbae6a501d07'},
    {'name': 'event.grf', 'base': 'input_root', 'path': '.tools/renewal/t07-007-execution-1/inner/app/event.grf',
     'bytes': 5833135, 'sha256': '7fff4e0eececd10df9a9c4f83b70d78dc4dbb99c5ece64b117df7db8a2f85575'},
    {'name': 'data0.grf', 'base': 'input_root', 'path': '.tools/renewal/t07-007-execution-1/inner/app/data0.grf',
     'bytes': 2123919641, 'sha256': '913402ace1d3c67818b4f070650a07eb157a6d62df9e394d596d59b4c7e6678a'},
    {'name': 'data.grf', 'base': 'input_root', 'path': '.tools/renewal/t07-007-execution-1/inner/app/data.grf',
     'bytes': 2172616301, 'sha256': '0565853edc5ad4b70e8ad705f5bc88c1af5624ee1b7a252fa81030d2ea813cc6'}]
T07_VALID_GRF = (('0x102', 5577), ('0x102', 3), ('0x102', 37), ('0x102', 89769), ('0x300', 155575))
T07_HEALTH_VERSION = '1.0.5'
T07_COUNTS = {'roots': 4, 'constructor_jobs': 273, 'model_targets': 273, 'returned_jobs': 273, 'returned_empty_jobs': 0,
              'returned_nonempty_jobs': 273, 'constructor_exception_jobs': 0, 'global_declarations': 397,
              'target_expanded_declarations': 397, 'nested_targets': 178, 'model_parent_links': 297,
              'model_placement_occurrences': 4922, 'root_expanded_model_placements': 4922, 'resolved_node_slots': 401,
              'unresolved_node_slots': 0, 'animation_jobs': {'true': 3, 'false': 270, 'unknown': 0},
              'remaining_core_gap_roots': 0, 'prior_first_level_gaps': 0}
T07_KIND_COUNTS = {'bmp': 171, 'tga': 7, 'unknown': 0}
T07_PLAN_BYTES = 46000
T07_CATALOG_KEYS = ('schema', 'task', 'mode', 'profile_sha256', 'constructor_profile_sha256', 'summary_sha256',
                    'input_pins', 'rule_sources', 'counts', 'roots', 'remaining_gap_root_ordinals',
                    'prior_first_level_gaps', 'model_targets', 'model_parent_links', 'jobs', 'nested_targets', 'limits',
                    'root_model_references', 'carried_ground_targets', 'world_gap_ledger_reference',
                    'constructor_producer')
T07_JOB_KEYS = ('source_row_index', 'id', 'job_id', 'kind', 'input_bytes', 'complete_sha256', 'header_version_bytes',
                'outcome', 'constructor_returned', 'worker_started', 'cleanup', 'target_model_ordinals', 'exception',
                'animation_by_node_keys', 'numeric_fields', 'nodes', 'declarations')
T07_CLEANUP = (('exit_observed', True), ('exit_code', 0), ('terminated_by_parent', False),
               ('stdout_eof_observed', True), ('stderr_eof_observed', True))
T07_ROOT_KEYS = ('ordinal', 'name', 'ordinal_scope', 'original_gap_root_ordinal', 'original_gap_root_ordinal_status',
                 'edges')
T07_REFERENCE_KEYS = ('model_ordinal', 'target_index', 'catalog_job_index', 'catalog_job_id', 'catalog_source_row_index',
                      'loader_index', 'role', 'root_ordinal', 'edge_kind', 'occurrence_summary_pointer',
                      'occurrence_indexes')
T07_CARRIED = 38
T07_GROUND_REFERRERS = 40
T07_LEDGER = {'path': 'docs/project/fixtures/T06.003.003.006-profile.json', 'bytes': 4855,
              'sha256': '9ad903297104cd6f9a03d74196d5db7a4091ee07da4d2b73b4b4f61027b2140d', 'roots': 1296,
              'remaining_core_gap_roots': 82}
T07_METADATA_PATHS = 4 + len(T07_SOURCE_PATHS)
T07_BOUND_API = ('wire_target', 'write_all', 'transfer', 'unattempted')
T07_ENGINE_TASK = 'T07.007.006'
# Explicit runtime route handed to the current engine Observer; engine constants stay untouched.
T07_ROUTE = {'task': T07_TASK, 'profile_bytes': T07_PROFILE_BYTES, 'profile_sha256': T07_PROFILE_SHA,
             'policy': T07_POLICY, 'native_names': T07_NATIVE_NAMES, 'native_bases': ('input_root',),
             'split_root': True}
# Inherited current-engine lifecycle; the subclass must not redefine any of these.
T07_INHERITED = ('run', 'request', 'scan', 'launch', '_launch_piped', 'health', 'cache_stats', 'shutdown',
                 'finish_diagnostics', 'retained_postverify', '_audit_split_trees', 'audit_tree', 'create_output',
                 'admit_output', 'hash_natives', 'diag_check', 'create_private', 'environment')


def _ordered(value):
    """Order-sensitive structural identity (typed: bool/int/float stay distinct)."""
    return json.dumps(value, ensure_ascii=True, allow_nan=False)


def _role_pin(rel):
    nbytes, digest = T07_ROLE_PINS[rel]
    return {'path': rel, 'bytes': nbytes, 'sha256': digest}


def validate_profile_t07(profile):
    """Exact checks after the trusted path/bytes/SHA selected the route."""
    require(isinstance(profile, dict) and tuple(profile) == T07_PROFILE_KEYS, 'profile_identity')
    require(profile['schema'] == PROFILE_SCHEMA and profile['task'] == T07_TASK
            and profile['basis_revision'] == T07_BASIS, 'profile_identity')
    require(typed_equal(profile['policy'], T07_POLICY), 'profile_policy')
    require(_ordered(profile['catalog']) == _ordered(T07_CATALOG_PIN), 'profile_catalog')
    require(_ordered(profile['authored']) == _ordered(T07_AUTHORED_PIN), 'profile_authored')
    pins = profile['source_pins']
    require(isinstance(pins, list) and all(_pin_ok(p) for p in pins)
            and tuple(p['path'] for p in pins) == T07_SOURCE_PATHS
            and all(p['bytes'] <= T07_POLICY['source_bytes'] for p in pins), 'profile_sources')
    by_path = {p['path']: p for p in pins}
    require(all(typed_equal(by_path[rel], _role_pin(rel)) for rel in T07_ROLE_PINS), 'profile_source_roles')
    require(_ordered(profile['native']) == _ordered(T07_NATIVE_TABLE), 'profile_native')
    require(_counts_ok(profile['expected_catalog_counts'], T07_COUNTS), 'profile_counts')
    kinds = profile['expected_kind_counts']
    require(isinstance(kinds, dict) and tuple(kinds) == HEADER_KINDS and typed_equal(kinds, T07_KIND_COUNTS)
            and sum(kinds.values()) == T07_COUNTS['nested_targets'] == T07_POLICY['asset_attempts'], 'profile_kinds')
    require(_ordered(profile['catalog_producer']) == _ordered(T07_CATALOG_PRODUCER)
            and typed_equal(profile['catalog_producer']['program'], by_path[T07_PRODUCER_REL]), 'profile_catalog_producer')
    producer = profile['constructor_producer']
    require(_ordered(producer) == _ordered(T07_CONSTRUCTOR_PRODUCER)
            and typed_equal(producer['program'], by_path[T07_CONSTRUCTOR_PROGRAM_REL])
            and typed_equal(producer['worker'], by_path[T07_CONSTRUCTOR_WORKER_REL]), 'profile_constructor_producer')
    require(_ordered(profile['engine_profile']) == _ordered(T07_ENGINE_PROFILE)
            and typed_equal(profile['engine_profile'], by_path[T07_PROFILE_006_REL]), 'profile_engine')
    limits = profile['limitations']
    require(isinstance(limits, list) and limits and all(isinstance(x, str) for x in limits), 'profile_limitations')


def validate_engine_profile_t07(engine_profile):
    """The .006 profile is lifecycle/native authority only; its catalog is never followed."""
    require(isinstance(engine_profile, dict) and engine_profile.get('schema') == 'T06-map-dependency-observation-profile-1'
            and engine_profile.get('task') == T07_ENGINE_TASK, 'engine_profile')
    require(isinstance(engine_profile.get('native'), list)
            and _ordered(engine_profile['native']) == _ordered(T07_NATIVE_TABLE), 'engine_profile_native')
    policy = engine_profile.get('policy')
    lifecycle = set(T07_POLICY) - {'metadata_seconds', 'source_bytes', 'authored_bytes', 'plan_bytes'}
    require(isinstance(policy, dict) and set(policy) == lifecycle
            and all(typed_equal(policy[k], T07_POLICY[k]) for k in lifecycle if k != 'asset_attempts'),
            'engine_profile_policy')


def _decimal_identity(value, nbytes):
    keys = ('dev', 'ino', 'size', 'mtime_ns', 'ctime_ns')
    return (isinstance(value, dict) and tuple(value) == keys
            and all(isinstance(value[k], str) and re.match(r'\A(?:0|[1-9][0-9]*)\Z', value[k]) for k in keys)
            and value['size'] == str(nbytes))


def validate_catalog_t07(catalog, profile, pins, prior, constructor_profile):
    """Exact .009 envelope, cleanup5 and corpus-only provenance; the pure plan checks the tables.

    prior and constructor_profile are the parsed .009/.008 profiles, each already an
    exact pinned source. Embedded receipt/body paths are compared as strings only.
    """
    require(isinstance(catalog, dict) and tuple(catalog) == T07_CATALOG_KEYS, 'catalog_shape')
    require(catalog['schema'] == CATALOG_SCHEMA and catalog['task'] == T07_CATALOG_TASK and catalog['mode'] == 'corpus',
            'catalog_identity')
    require(catalog['profile_sha256'] == pins[T07_PROFILE_009_REL]['sha256']
            and catalog['constructor_profile_sha256'] == pins[T07_PROFILE_008_REL]['sha256']
            and catalog['summary_sha256'] == pins[SUMMARY_REL]['sha256'], 'catalog_binding')
    # .009 profile: the catalog's own admitted authority.
    require(isinstance(prior, dict) and prior.get('schema') == 'T06-model-texture-catalog-profile-1'
            and prior.get('task') == T07_CATALOG_TASK, 'prior_identity')
    require(typed_equal(prior.get('constructor_profile'), pins[T07_PROFILE_008_REL])
            and typed_equal(prior.get('summary'), pins[SUMMARY_REL])
            and _ordered(prior.get('constructor_producer')) == _ordered(profile['constructor_producer']), 'prior_binding')
    inputs = prior.get('inputs')
    require(isinstance(inputs, dict) and tuple(inputs) == ('report', 'jobs', 'manifest', 'catalog')
            and _ordered(catalog['input_pins']) == _ordered(inputs), 'catalog_input_pins')
    rules = prior.get('rule_sources')
    require(isinstance(rules, dict) and tuple(rules) == T07_RULE_RELS
            and _ordered(catalog['rule_sources']) == _ordered(rules), 'catalog_rule_sources')
    for rel, pin in rules.items():
        mine = pins[CLIENT_PREFIX + rel]
        require(typed_equal(pin, {'bytes': mine['bytes'], 'sha256': mine['sha256']}), 'catalog_rule_sources')
    counts = profile['expected_catalog_counts']
    require(typed_equal(catalog['counts'], counts) and typed_equal(prior.get('expected_counts'), counts), 'catalog_counts')
    require(typed_equal(catalog['limits'], prior.get('limitations')), 'catalog_limits')
    require(_ordered(catalog['constructor_producer']) == _ordered(profile['constructor_producer']),
            'catalog_constructor_producer')
    # .008 constructor profile: upstream supplement facts.
    cp = constructor_profile
    require(isinstance(cp, dict) and cp.get('schema') == 'T06-model-constructor-profile-1'
            and cp.get('task') == profile['constructor_producer']['task'], 'constructor_profile_identity')
    cpc, availability = cp.get('counts'), cp.get('availability')
    require(typed_equal(cp.get('summary'), pins[SUMMARY_REL])
            and typed_equal(cp.get('worker'), profile['constructor_producer']['worker'])
            and typed_equal(cp.get('manifest'), inputs['manifest'])
            and isinstance(availability, dict) and typed_equal(availability.get('catalog'), inputs['catalog'])
            and isinstance(cpc, dict) and all(is_int(cpc.get(k)) for k in ('roots', 'model_targets', 'constructor_jobs',
                                                                          'model_referrers', 'remaining_core_gap_roots'))
            and cpc['roots'] == counts['roots'] and cpc['model_targets'] == counts['model_targets']
            and cpc['constructor_jobs'] == counts['constructor_jobs']
            and cpc['model_referrers'] == counts['model_parent_links']
            and cpc['remaining_core_gap_roots'] == counts['remaining_core_gap_roots'], 'constructor_profile_binding')
    # Every original job keeps its five typed cleanup facts; never projected to cleanup3.
    for i, job in enumerate(catalog['jobs'] if isinstance(catalog['jobs'], list) else ()):
        require(isinstance(job, dict) and tuple(job) == T07_JOB_KEYS and job['job_id'] == job['id']
                and job['worker_started'] is True, 'catalog_job_shape')
        cleanup = job['cleanup']
        require(isinstance(cleanup, dict) and tuple(cleanup) == tuple(k for k, _ in T07_CLEANUP)
                and all(type(cleanup[k]) is type(v) and cleanup[k] == v for k, v in T07_CLEANUP), 'catalog_cleanup')
    # Four roots: subset-only ordinals with unknown original world ordinals.
    roots = catalog['roots']
    require(isinstance(roots, list) and len(roots) == counts['roots'], 'catalog_root_provenance')
    for i, root in enumerate(roots):
        require(isinstance(root, dict) and tuple(root) == T07_ROOT_KEYS and root['ordinal'] == i
                and isinstance(root['name'], str) and root['ordinal_scope'] == 'four-target-subset-only'
                and root['original_gap_root_ordinal'] is None
                and root['original_gap_root_ordinal_status'] == 'unknown_in_admitted_reference_metadata'
                and isinstance(root['edges'], dict) and tuple(root['edges']) == ('rsw', 'gnd', 'gat')
                and all(isinstance(e, dict) and tuple(e) == ('job_id', 'parse_status', 'parse_outcome')
                        and isinstance(e['job_id'], str) and e['parse_status'] == 'not_run'
                        and e['parse_outcome'] == 'returned' for e in root['edges'].values()), 'catalog_root_provenance')
    require(len({r['name'] for r in roots}) == len(roots), 'catalog_root_provenance')
    # Root model references: one per parent link, exact joins, placements preserved.
    refs, links, models = catalog['root_model_references'], catalog['model_parent_links'], catalog['model_targets']
    require(isinstance(refs, list) and isinstance(links, list) and isinstance(models, list)
            and len(refs) == len(links) == counts['model_parent_links'], 'catalog_root_references')
    occurrences = 0
    for ref, link in zip(refs, links):
        require(isinstance(ref, dict) and tuple(ref) == T07_REFERENCE_KEYS and isinstance(link, dict)
                and is_int(ref['model_ordinal']) and 0 <= ref['model_ordinal'] < len(models)
                and is_int(ref['root_ordinal']) and 0 <= ref['root_ordinal'] < len(roots)
                and all(is_int(ref[k]) and ref[k] >= 0 for k in
                        ('target_index', 'catalog_job_index', 'catalog_source_row_index', 'loader_index'))
                and ref['catalog_source_row_index'] == ref['catalog_job_index']
                and ref['occurrence_summary_pointer'] == '/summary/model_dependencies'
                and isinstance(ref['edge_kind'], str) and ref['edge_kind'] in roots[ref['root_ordinal']]['edges']
                and isinstance(ref['occurrence_indexes'], list)
                and all(is_int(x) and x >= 0 for x in ref['occurrence_indexes']), 'catalog_root_references')
        model = models[ref['model_ordinal']]
        referrer = link.get('referrer')
        require(isinstance(model, dict) and typed_equal(model.get('target_index'), ref['target_index'])
                and roots[ref['root_ordinal']]['edges'][ref['edge_kind']]['job_id'] == ref['catalog_job_id']
                and typed_equal(link.get('model_ordinal'), ref['model_ordinal'])
                and typed_equal(link.get('catalog_target_index'), ref['target_index'])
                and link.get('source_job_id') == ref['catalog_job_id']
                and isinstance(referrer, dict) and typed_equal(referrer.get('job_index'), ref['catalog_job_index'])
                and typed_equal(referrer.get('loader_index'), ref['loader_index']) and referrer.get('role') == ref['role']
                and _ordered(link.get('root_references')) == _ordered([{'root_ordinal': ref['root_ordinal'],
                                                                         'edge_kind': ref['edge_kind']}])
                and _ordered(link.get('placement_indexes')) == _ordered(ref['occurrence_indexes']),
                'catalog_root_references')
        occurrences += len(ref['occurrence_indexes'])
    require(occurrences == counts['model_placement_occurrences'], 'catalog_root_references')
    # Carried BMP ground pairs: provenance only, never extra requests.
    carried = catalog['carried_ground_targets']
    require(isinstance(carried, list) and len(carried) == T07_CARRIED, 'catalog_carried')
    ground, previous = 0, -1
    for pair in carried:
        require(isinstance(pair, dict) and tuple(pair) == ('target_index', 'catalog_target', 'availability_record')
                and is_int(pair['target_index']) and pair['target_index'] > previous, 'catalog_carried')
        previous = pair['target_index']
        target, record = pair['catalog_target'], pair['availability_record']
        require(isinstance(target, dict) and tuple(target) == ('index', 'http_path', 'referrers')
                and target['index'] == pair['target_index'] and isinstance(target['http_path'], str)
                and filemanager_kind(target['http_path']) == 'bmp' and isinstance(target['referrers'], list)
                and target['referrers'] and all(isinstance(r, dict) and r.get('role') == 'ground_texture'
                                                for r in target['referrers']), 'catalog_carried')
        require(isinstance(record, dict) and record.get('target_index') == pair['target_index']
                and record.get('wire_target') == '/' + target['http_path']
                and isinstance(record.get('signature'), dict) and record['signature'].get('kind') == 'bmp'
                and isinstance(record.get('stored'), dict) and record['stored'].get('complete') is True, 'catalog_carried')
        ground += len(target['referrers'])
    require(ground == T07_GROUND_REFERRERS, 'catalog_carried')
    # World ledger: declared, never opened; this subset never reconciles it.
    ledger = catalog['world_gap_ledger_reference']
    require(isinstance(ledger, dict) and tuple(ledger) == ('profile', 'roots', 'remaining_core_gap_roots',
                                                           'reconciled_by_this_subset'), 'catalog_world_ledger')
    lp = ledger['profile']
    require(isinstance(lp, dict) and tuple(lp) == ('path', 'bytes', 'sha256', 'identity')
            and lp['path'] == T07_LEDGER['path'] and is_int(lp['bytes']) and lp['bytes'] == T07_LEDGER['bytes']
            and lp['sha256'] == T07_LEDGER['sha256'] and _decimal_identity(lp['identity'], lp['bytes'])
            and is_int(ledger['roots']) and ledger['roots'] == T07_LEDGER['roots']
            and is_int(ledger['remaining_core_gap_roots'])
            and ledger['remaining_core_gap_roots'] == T07_LEDGER['remaining_core_gap_roots']
            and ledger['reconciled_by_this_subset'] is False, 'catalog_world_ledger')


def load_engine_t07(source_bytes, engine_path):
    """Exact admitted CURRENT engine bytes in a fresh non-main namespace; bind exactly four functions."""
    require(type(source_bytes) is bytes, 'engine_bytes')
    code = compile(source_bytes, engine_path, 'exec', dont_inherit=True)
    namespace = {'__name__': '_t07_010_engine_' + sha(source_bytes)[:12], '__file__': engine_path,
                 '__builtins__': builtins}
    exec(code, namespace)  # Pinned bytes only; never sys.modules, engine main or map load_metadata.
    require(namespace.get('TASK') == ENGINE_TASK and namespace.get('T07_TASK') == T07_ENGINE_TASK
            and namespace.get('T07_PROFILE_SHA') == T07_ENGINE_PROFILE['sha256']
            and typed_equal(namespace.get('T07_NATIVE_TABLE'), T07_NATIVE_TABLE)
            and namespace.get('T07_NATIVE_NAMES') == T07_NATIVE_NAMES
            and namespace.get('T07_VALID_GRF') == T07_VALID_GRF
            and namespace.get('T07_HEALTH_VERSION') == T07_HEALTH_VERSION, 'engine_identity')
    own = {'wire_target': wire_target, 'write_all': write_all, 'transfer': transfer, 'unattempted': unattempted}
    for name in T07_BOUND_API:
        require(callable(namespace.get(name)), 'engine_api')
        namespace[name] = own[name]
    require(all(t07_engine_bound(namespace).values()), 'engine_binding')
    return namespace


def t07_engine_bound(engine):
    """Four exact identities plus every inherited lifecycle method's globals."""
    observer = engine.get('Observer')
    methods = [getattr(observer, name, None) for name in T07_INHERITED]
    same = all(getattr(m, '__globals__', None) is engine for m in methods)
    return {name: bool(same and engine.get(name) is fn) for name, fn in
            (('wire_target', wire_target), ('write_all', write_all), ('transfer', transfer),
             ('unattempted', unattempted))}


def load_metadata_t07(input_root, profile_path, clock=None):
    """Metadata-only admission of the new route; never native, HOME, process, output or HTTP."""
    clock = time.monotonic if clock is None else clock
    deadline = clock() + T07_POLICY['metadata_seconds']
    require(isinstance(input_root, str) and os.path.isabs(input_root) and os.path.normpath(input_root) == input_root,
            'input_root')
    try:
        check_directory(input_root)
    except Absent:
        raise Refusal('input_root')
    require(profile_path == T07_PROFILE_REL, 'profile_path')
    driver = own_sha()
    profile_abs = relative(input_root, profile_path)
    profile_bytes, profile_receipt = read_admitted(profile_abs, T07_PROFILE_BYTES, T07_PROFILE_SHA, deadline=deadline,
                                                   clock=clock)
    profile = strict_json(profile_bytes)
    validate_profile_t07(profile)
    apin = profile['authored']
    authored_bytes, authored_receipt = read_admitted(relative(input_root, apin['path']), apin['bytes'], apin['sha256'],
                                                     limit=T07_POLICY['authored_bytes'], deadline=deadline, clock=clock)
    authored = strict_json(authored_bytes)
    require(isinstance(authored, dict) and authored.get('schema') == AUTHORED_SCHEMA
            and authored.get('status') == 'FROZEN_ROOT_REVIEWED', 'authored_identity')
    sources, kept, pins = [], {}, {}
    keep = (ENGINE_REL, T07_PROFILE_009_REL, T07_PROFILE_008_REL, T07_PROFILE_006_REL)
    for pin in profile['source_pins']:
        data, receipt = read_admitted(relative(input_root, pin['path']), pin['bytes'], pin['sha256'],
                                      limit=T07_POLICY['source_bytes'], deadline=deadline, clock=clock)
        sources.append(dict(path=pin['path'], **receipt))
        pins[pin['path']] = {'path': pin['path'], 'bytes': pin['bytes'], 'sha256': pin['sha256']}
        if pin['path'] in keep:
            kept[pin['path']] = data
    validate_engine_profile_t07(strict_json(kept[T07_PROFILE_006_REL]))
    cpin = profile['catalog']
    catalog_path = relative(input_root, cpin['path'])
    catalog_bytes, catalog_receipt = read_admitted(catalog_path, cpin['bytes'], cpin['sha256'],
                                                   limit=T07_POLICY['catalog_bytes'], deadline=deadline, clock=clock)
    catalog = strict_json(catalog_bytes)
    require(clock() < deadline, 'metadata_deadline')
    validate_catalog_t07(catalog, profile, pins, strict_json(kept[T07_PROFILE_009_REL]),
                         strict_json(kept[T07_PROFILE_008_REL]))
    plans = build_plan(catalog, profile['expected_catalog_counts'], deadline=deadline, clock=clock)  # Full catalog.
    referrers = sum(len(p['referrers']) for p in plans)
    require(len(plans) == T07_COUNTS['nested_targets'] and referrers == T07_COUNTS['global_declarations'], 'plan_counts')
    kind_counts = {k: sum(p['kind'] == k for p in plans) for k in HEADER_KINDS}
    require(typed_equal(kind_counts, profile['expected_kind_counts']), 'plan_kinds')
    plan_bytes = len(json.dumps(plans, ensure_ascii=True, allow_nan=False, separators=(',', ':')))
    require(plan_bytes == T07_PLAN_BYTES and plan_bytes <= T07_POLICY['plan_bytes'], 'plan_size')
    engine_path = relative(input_root, ENGINE_REL)
    engine = load_engine_t07(kept[ENGINE_REL], engine_path)
    nested = {p['http_path'] for p in plans}
    carried = catalog['carried_ground_targets']
    meta = {'input_root': input_root, 'profile_path': profile_abs, 'profile': profile,
            'profile_receipt': profile_receipt, 'authored_receipt': authored_receipt, 'sources': sources,
            'catalog_bytes': catalog_bytes, 'catalog_receipt': catalog_receipt, 'catalog_path': catalog_path,
            'catalog': catalog, 'plans': plans, 'referrers': referrers,
            'gaps': list(catalog['remaining_gap_root_ordinals']), 'kind_counts': kind_counts,
            'plan_bytes': plan_bytes, 'driver_receipt': driver, 'engine': engine,
            'engine_pin': dict(pins[ENGINE_REL]), 'authored': authored, 'route': T07_ROUTE,
            'carried': {'pairs': len(carried), 'ground_referrers': sum(len(c['catalog_target']['referrers'])
                                                                       for c in carried),
                        'http_paths_also_nested': sum(c['catalog_target']['http_path'] in nested for c in carried),
                        'requested_separately': 0}}
    meta['recheck'] = recheck_list(meta)
    require(len(meta['recheck']) == T07_METADATA_PATHS, 'recheck_count')
    verify_recheck(meta['recheck'], deadline=deadline, clock=clock)  # Rehash all27 after plan construction.
    require(clock() < deadline, 'metadata_deadline')
    return meta


def load_route_metadata(input_root, profile_path, clock=None):
    """Exactly two routes, selected by the exact relative profile path before any profile read."""
    if profile_path == T07_PROFILE_REL:
        return load_metadata_t07(input_root, profile_path, clock=clock)
    return load_metadata(input_root, profile_path, clock=clock)


def native_specs_t07(meta):
    """Six ordered input_root descriptors; never resolves HOME."""
    out = []
    for item in meta['profile']['native']:
        require(item['base'] == 'input_root', 'profile_native')
        out.append({'name': item['name'], 'path': relative(meta['input_root'], item['path']), 'bytes': item['bytes'],
                    'sha256': item['sha256']})
    return out


def texture_coverage(targets):
    """Per-row availability/header tallies; availability and header states stay separate."""
    counts = {'transfer': {}, 'stop_reason': {}, 'http_status': {}, 'header_states': {},
              'tga_header_checks': {'observed': 0, 'all_true': 0, 'any_false': 0},
              'stored_complete': 0, 'storage_error': 0, 'complete_200_bytes_available': 0,
              'http_404': 0, 'other_http': 0, 'redirect': 0, 'empty_200': 0, 'html_200': 0,
              'cap': 0, 'transport': 0, 'unattempted': 0, 'attempted': 0}
    for r in targets:
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
        if r['stop_reason'] in OUTCOMES or r['stop_reason'] in ('http_404', 'redirect', 'http_status', 'empty_200',
                                                                'html_200'):
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


_T07_CLASSES = {}


def _observer_class_t07(engine):
    """Minimal subclass of the current engine Observer; cached per fresh namespace.

    It inherits run/request/scan/launch/health/cache/shutdown/diagnostic/retained
    behavior and only adds report provenance, 18-byte stored-prefix headers,
    texture coverage and texture metadata postchecks.
    """
    key = id(engine)
    if key in _T07_CLASSES and _T07_CLASSES[key][0] is engine:
        return _T07_CLASSES[key][1]
    base, Fatal = engine['Observer'], engine['Fatal']
    caught = (Refusal, Absent, engine['Refusal'], engine['Absent'])

    class NestedTextureObserver(base):
        def __init__(self, meta, output, driver, ops=None, natives=None, policy=None, container=None, write_fn=None,
                     diag_write_fn=None):
            super().__init__(meta, output, driver, ops=ops, natives=natives, policy=policy, container=container,
                             write_fn=write_fn, diag_write_fn=diag_write_fn)
            catalog, ledger = meta['catalog'], meta['catalog']['world_gap_ledger_reference']
            # Base report first: every current split-route field is retained.
            self.report.update({
                'schema': SCHEMA, 'task': T07_TASK, 'mode': 'execute',
                'engine_pin': dict(meta['engine_pin'], bound_api=list(T07_BOUND_API)),
                'catalog_refs': {
                    'file': 'catalog-input.json', 'targets_pointer': '/nested_targets', 'roots_pointer': '/roots',
                    'jobs_pointer': '/jobs', 'model_targets_pointer': '/model_targets',
                    'parents_pointer': '/model_parent_links', 'prior_gaps_pointer': '/prior_first_level_gaps',
                    'root_model_references_pointer': '/root_model_references',
                    'carried_ground_targets_pointer': '/carried_ground_targets',
                    'world_gap_ledger_pointer': '/world_gap_ledger_reference',
                    'roots': len(catalog['roots']), 'targets': len(meta['plans']), 'referrers': meta['referrers'],
                    'gap_root_ordinals': list(meta['gaps']), 'counts': catalog['counts'],
                    'kind_counts': meta['kind_counts'], 'carried_ground': dict(meta['carried']),
                    'unknown_world_ordinals': sum(r['original_gap_root_ordinal'] is None for r in catalog['roots']),
                    'world_ledger': {'roots': ledger['roots'],
                                     'remaining_core_gap_roots': ledger['remaining_core_gap_roots'],
                                     'reconciled_by_this_subset': ledger['reconciled_by_this_subset']}},
                'producers': {'catalog': meta['profile']['catalog_producer'],
                              'constructor': meta['profile']['constructor_producer'],
                              'engine_profile': meta['profile']['engine_profile']},
                'header_api': {'retained_prefix_bytes': dict(HEADER_KEEP), 'stored_prefix_bytes': PREFIX_KEEP,
                               'image_decode': 'untested', 'render': 'untested', 'playability': 'untested'},
                'engine_bindings_after': None, 'postchecks_valid': False})
            self.freezes = 0

        @staticmethod
        def _source_receipts(meta):
            return {'driver': meta['driver_receipt'], 'profile': meta['profile_receipt'],
                    'authored': meta['authored_receipt'], 'catalog': meta['catalog_receipt'],
                    'sources': meta['sources']}

        # -- provenance freeze before every persisted checkpoint
        def freeze(self):
            report, plans = self.report, self.meta['plans']
            ok = (report.get('schema') == SCHEMA and report.get('task') == T07_TASK
                  and report['profile_pin']['sha256'] == T07_PROFILE_SHA
                  and report['catalog_refs']['targets_pointer'] == '/nested_targets'
                  and report['engine_pin']['bound_api'] == list(T07_BOUND_API)
                  and len(report['targets']) == len(plans))
            launch = report.get('launch')
            if launch is not None:
                env = launch.get('environment') or {}
                ok = ok and (launch.get('task') == T07_TASK and launch.get('profile_sha256') == T07_PROFILE_SHA
                             and 'HOME' not in env and 'GRF_FILENAME_ENCODING' not in env
                             and env.get('NODE_ENV') == 'development')
            for row, plan in zip(report['targets'], plans):
                ok = ok and ('signature' not in row and '_prefix' not in row
                             and row.get('header', {}).get('kind') == plan['kind']
                             and row['target_index'] == plan['index'] and row['catalog_pointer'] == plan['catalog_pointer']
                             and row['referrers_pointer'] == plan['catalog_pointer'] + '/referrers'
                             and row['http_path'] == plan['http_path'] and row['wire_target'] == plan['wire'])
            if not ok:
                raise Fatal('provenance_failure')
            self.freezes += 1

        def checkpoint(self):
            self.freeze()
            super().checkpoint()

        # -- 18-byte stored prefix after the engine's full verification/registration
        def verify_stored(self, record, result, written):
            super().verify_stored(record, result, written)
            if '_prefix' not in record:
                return
            stored = record['stored']
            try:
                prefix, receipt = read_admitted(self.path(stored['file']), stored['bytes'], stored['sha256'],
                                                keep=False, limit=self.policy['body_bytes'], prefix=PREFIX_KEEP)
                require(receipt == self.retained.get(stored['file']), 'prefix_receipt')
            except caught + (OSError,):
                record.pop('_prefix', None)
                stored['complete'] = False
                stored['error'] = stored['error'] or 'prefix_verify_failed'
                self.fail('storage_failure', 'stored_prefix_failed')
                return
            record['_prefix'] = prefix[:PREFIX_KEEP]

        def classify(self, record, result, kind):
            prefix = record.pop('_prefix', None)
            super().classify(record, result, None)  # Availability only; never an engine signature.
            if (result is not None and result['outcome'] == 'complete' and record['http_status'] == 200
                    and record['stored']['complete'] and prefix is not None):
                record['header'] = inspect_texture_header(kind, bytes(prefix))

        def audit_missing_log(self):
            try:
                super().audit_missing_log()
            except OSError:
                # The unchanged engine reader can raise on a read/close error.
                self.report['missing_log']['valid'] = False
                self.report['missing_log']['error'] = 'log_read_or_close'

        def engine_bound(self):
            return t07_engine_bound(engine)

        def postchecks(self):
            """Texture metadata/driver/bindings/natives; never map metadata admission."""
            ok = True
            try:
                after = self.hash_natives()
                self.report['native_after'] = after
                ok = after == self.native_before and list(after) == T07_NATIVE_NAMES
            except caught + (OSError,):
                self.report['native_after'] = None
                ok = False
            try:
                verify_recheck(self.meta['recheck'])
                receipts = self._source_receipts(self.meta)
                self.report['sources_after'] = receipts
                ok = ok and receipts == self.report['sources_before']
                ok = ok and own_sha() == self.driver == self.meta['driver_receipt']
            except caught + (OSError,):
                self.report['sources_after'] = None
                ok = False
            bound = self.engine_bound()
            self.report['engine_bindings_after'] = bound
            ok = ok and all(bound.values())
            return self.retained_postverify() and ok  # Always executed, even after an earlier failure.

        def coverage(self):
            return texture_coverage(self.report['targets'])

    for name in T07_INHERITED:
        require(name not in NestedTextureObserver.__dict__, 'engine_lifecycle')
    _T07_CLASSES[key] = (engine, NestedTextureObserver)
    return NestedTextureObserver


def make_observer_t07(meta, output, driver, ops=None, natives=None, policy=None, container=None, write_fn=None,
                      diag_write_fn=None):
    """Production new-route observer; ops/natives/policy/container/write fns are fake-test seams only."""
    cls = _observer_class_t07(meta['engine'])
    return cls(meta, output, driver, ops=ops, natives=natives if natives is not None else native_specs_t07(meta),
               policy=dict(T07_POLICY if policy is None else policy),
               container=default_container() if container is None else container, write_fn=write_fn,
               diag_write_fn=diag_write_fn)


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
        meta = load_route_metadata(args['input_root'], args['profile'])
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
    if meta.get('route') is T07_ROUTE:
        return _main_t07(args, meta, driver, counts)
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


def _main_t07(args, meta, driver, counts):
    catalog = meta['catalog']
    counts.update(model_parent_links=len(catalog['model_parent_links']),
                  placements=sum(len(r['occurrence_indexes']) for r in catalog['root_model_references']),
                  carried_ground=meta['carried'], metadata_paths=len(meta['recheck']),
                  world_ledger={k: catalog['world_gap_ledger_reference'][k]
                                for k in ('roots', 'remaining_core_gap_roots', 'reconciled_by_this_subset')})
    if not args['execute']:
        emit(sys.stdout, {'status': 'preflight_ok', 'task': T07_TASK, 'driver_sha256': driver['sha256'],
                          'profile_sha256': T07_PROFILE_SHA, 'catalog_sha256': meta['catalog_receipt']['sha256'],
                          'engine_sha256': meta['engine_pin']['sha256'], 'bound_api': list(T07_BOUND_API),
                          'counts': counts, 'native_qualification': None, 'native_or_network_or_process': False})
        return 0
    observer = None
    try:
        observer = make_observer_t07(meta, args['output'], driver)
        code = observer.run()
    except Exception:
        code = 1
    if code == 2:
        emit(sys.stdout, {'status': 'refused', 'reason': 'output_admission'})
        return 2
    report = observer.report if observer is not None else {}
    emit(sys.stdout, {'status': 'execute_qualified' if code == 0 else 'execute_failed', 'task': T07_TASK,
                      'halt_reason': observer.halt if observer is not None else 'internal',
                      'coverage': {k: v for k, v in (report.get('coverage_counts') or {}).items()
                                   if not isinstance(v, dict)},
                      'acquisition_and_cleanup_valid': bool(report.get('acquisition_and_cleanup_valid'))})
    return code


if __name__ == '__main__':
    sys.exit(main())
