"""Tests for observe_model_textures.py (T06.003.003.008).

Run: python3 -I -B tools/renewal/test_observe_model_textures.py
Uses frozen authored literals, real tiny private files/FDs under this checkout's
.tools/renewal, fake process/HTTP objects and the full canonical METADATA-ONLY
preflight. Never stats/opens native inputs, launches native code or makes HTTP.
CANONICAL_ROOT overrides the canonical input root.
"""
import copy
import fcntl
import hashlib
import http.client
import importlib.util
import io
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import time
import unittest
from contextlib import redirect_stdout
from unittest import mock
from urllib.parse import unquote

HERE = os.path.dirname(os.path.abspath(__file__))
CHECKOUT = os.path.dirname(os.path.dirname(HERE))
DRIVER = os.path.join(HERE, 'observe_model_textures.py')
CANONICAL = os.environ.get('CANONICAL_ROOT',
                           '/Users/shem/orca/workspaces/game-reverse-engineering/'
                           'reverse-the-Ragnarok-Online-to-play-by-myself')
PROFILE_REL = 'docs/project/fixtures/T06.003.003.008-profile.json'
AUTHORED_PATH = os.path.join(CHECKOUT, 'docs/project/fixtures/T06.003.003.008-authored.json')
ENGINE_PATH = os.path.join(CHECKOUT, 'tools/renewal/observe_map_dependencies.py')
ENGINE_SHA = '565a42c380e69b1c498907cf48ec2c609984b6899d16263d55a92e4e353a3a35'
NEW_PROFILE_SHA = '2ee28e4e4de7d8088d589c5cba663f247b3eb8dcde6348079e19a21be236ce7d'
OLD_PROFILE_SHA = 'c581255b5b77cbd7c675ada5e271360e274bdbbe740a4e7eb921317b4c6889f5'

_spec = importlib.util.spec_from_file_location('observe_model_textures', DRIVER)
M = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(M)

with open(AUTHORED_PATH, 'rb') as _fh:
    AUTHORED = json.loads(_fh.read().decode('utf-8'))
SCRATCH = None
_SERIAL = [0]


def typed_eq(a, b):
    """Independent typed deep comparison (bool is not int, 1 is not 1.0)."""
    if type(a) is not type(b):
        return False
    if isinstance(a, dict):
        return set(a) == set(b) and all(typed_eq(a[k], b[k]) for k in a)
    if isinstance(a, list):
        return len(a) == len(b) and all(typed_eq(x, y) for x, y in zip(a, b))
    return a == b


def open_fds():
    return sorted(int(n) for n in os.listdir('/dev/fd'))


def fd_path(fd):
    try:
        raw = fcntl.fcntl(fd, fcntl.F_GETPATH, b'\0' * 1024)
    except OSError:
        return ''
    return raw.split(b'\0', 1)[0].decode('utf-8', 'replace')


def private_dir(path):
    os.mkdir(path, 0o700)
    os.chmod(path, 0o700)
    return path


def private_file(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    try:
        os.fchmod(fd, 0o600)
        M.write_all(fd, data)
    finally:
        os.close(fd)
    return path


def fresh(name):
    _SERIAL[0] += 1
    return private_dir(os.path.join(SCRATCH, '%s-%03d' % (name, _SERIAL[0])))


def setUpModule():
    global SCRATCH
    base = CHECKOUT
    for part in ('.tools', 'renewal'):
        base = os.path.join(base, part)
        if not os.path.isdir(base):
            private_dir(base)
    SCRATCH = os.path.join(base, 'test-observe-model-textures-%d' % os.getpid())
    private_dir(SCRATCH)


def tearDownModule():
    if SCRATCH and os.path.isdir(SCRATCH):
        for root, dirs, _ in os.walk(SCRATCH):
            for d in dirs:
                os.chmod(os.path.join(root, d), 0o700)
        shutil.rmtree(SCRATCH)


def set_pointer(doc, pointer, value):
    parts = [p.replace('~1', '/').replace('~0', '~') for p in pointer.split('/')[1:]]
    node = doc
    for part in parts[:-1]:
        node = node[int(part)] if isinstance(node, list) else node[part]
    last = parts[-1]
    if isinstance(node, list):
        node[int(last)] = value
    else:
        node[last] = value


# ---------------------------------------------------------------- authored pure controls

class AuthoredControls(unittest.TestCase):
    def test_case_counts_frozen(self):
        counts = AUTHORED['case_counts']
        self.assertEqual(counts, {'wire': 16, 'transport': 11, 'write_controls': 3, 'header': 34,
                                  'header_argument_refusals': 9, 'plan_mutations': 17})
        self.assertEqual(len(AUTHORED['wire_cases']), 16)
        self.assertEqual(len(AUTHORED['transport_cases']), 11)
        self.assertEqual(len(AUTHORED['write_controls']), 3)
        self.assertEqual(len(AUTHORED['header_cases']), 34)
        self.assertEqual(len(AUTHORED['header_argument_refusals']), 9)
        self.assertEqual(len(AUTHORED['plan_refusal_mutations']), 17)

    def test_34_header_literals(self):
        for case in AUTHORED['header_cases']:
            with self.subTest(case['id']):
                prefix = bytes(case['prefix_bytes'])
                before = bytes(prefix)
                got = M.inspect_texture_header(case['kind'], prefix)
                self.assertTrue(typed_eq(got, case['expected']), case['id'])
                self.assertEqual(prefix, before)
                again = M.inspect_texture_header(case['kind'], prefix)
                self.assertIsNot(got, again)
                if got['tga'] is not None:
                    self.assertIsNot(got['tga']['header'], again['tga']['header'])
                json.dumps(got, allow_nan=False)
                self.assertEqual(list(got), ['kind', 'state', 'prefix_hex', 'tga'])

    def test_header_extra_bytes_and_huge_dimensions_bounded(self):
        header = bytes.fromhex('00000a000000000000000000ffffffff2000')
        big = header + b'\xab' * (1 << 20)
        start = time.perf_counter()
        got = M.inspect_texture_header('tga', big)
        self.assertLess(time.perf_counter() - start, 0.5)
        self.assertEqual(got['prefix_hex'], header.hex())
        self.assertEqual(got['tga']['header']['width'], 65535)
        self.assertEqual(M.inspect_texture_header('bmp', b'BM' + b'\0' * 100)['prefix_hex'], '424d')

    def test_nine_argument_refusals(self):
        class StrSub(str):
            pass

        class BytesSub(bytes):
            pass

        def build(desc):
            kind = desc['type']
            if kind == 'str':
                return desc['value']
            if kind == 'bool':
                return desc['value']
            if kind == 'str_subclass':
                return StrSub(desc['value'])
            if kind == 'NoneType':
                return None
            if kind == 'bytes':
                return bytes.fromhex(desc['hex'])
            if kind == 'bytearray':
                return bytearray.fromhex(desc['hex'])
            if kind == 'memoryview_of_bytes':
                return memoryview(bytes.fromhex(desc['hex']))
            if kind == 'bytes_subclass':
                return BytesSub(bytes.fromhex(desc['hex']))
            raise AssertionError(kind)
        for case in AUTHORED['header_argument_refusals']:
            with self.subTest(case['id']):
                kind, prefix = build(case['kind_descriptor']), build(case['prefix_descriptor'])
                with self.assertRaises(ValueError) as ctx:
                    M.inspect_texture_header(kind, prefix)
                message = str(ctx.exception)
                for raw in (case['kind_descriptor'].get('value'), case['prefix_descriptor'].get('value'),
                            case['prefix_descriptor'].get('hex')):
                    if isinstance(raw, str) and raw:
                        self.assertNotIn(raw, message)

    def test_16_wire_cases(self):
        for case in AUTHORED['wire_cases']:
            with self.subTest(case['id']):
                expected = case['expected']
                if 'returns' in expected:
                    got = M.wire_target(case['http_path'])
                    self.assertTrue(typed_eq(got, expected['returns']))
                else:
                    with self.assertRaises(ValueError) as ctx:
                        M.wire_target(case['http_path'])
                    if case['http_path']:
                        self.assertNotIn(case['http_path'], str(ctx.exception))

    def test_toy_plan_exact_and_caller_preserved(self):
        toy = AUTHORED['toy_catalog']
        snapshot = copy.deepcopy(toy)
        counts = copy.deepcopy(toy['counts'])
        plan = M.build_plan(toy, counts)
        self.assertTrue(typed_eq(plan, AUTHORED['toy_expected_plan']))
        self.assertEqual(len(plan), 4)
        self.assertTrue(typed_eq(toy, snapshot))
        self.assertTrue(typed_eq(counts, toy['counts']))
        for row, target in zip(plan, toy['nested_targets']):
            self.assertIsNot(row['referrers'], target['referrers'])
            for a, b in zip(row['referrers'], target['referrers']):
                self.assertIsNot(a, b)
            self.assertEqual(list(row), ['index', 'catalog_pointer', 'http_path', 'wire', 'kind', 'referrers'])
        plan[0]['referrers'][0]['job_index'] = 77
        self.assertTrue(typed_eq(toy, snapshot))
        self.assertIsNot(M.build_plan(toy, counts), M.build_plan(toy, counts))

    def test_17_plan_mutations_refuse(self):
        for case in AUTHORED['plan_refusal_mutations']:
            with self.subTest(case['id']):
                toy = copy.deepcopy(AUTHORED['toy_catalog'])
                expected_counts = copy.deepcopy(AUTHORED['toy_catalog']['counts'])
                for mutation in case['mutations']:
                    self.assertEqual(mutation['op'], 'set')
                    set_pointer(toy, mutation['path'], copy.deepcopy(mutation['value']))
                snapshot = copy.deepcopy(toy)
                with self.assertRaises(M.Refusal):
                    M.build_plan(toy, expected_counts)
                self.assertTrue(typed_eq(toy, snapshot))

    def test_plan_rejects_bool_expected_counts(self):
        toy = AUTHORED['toy_catalog']
        counts = copy.deepcopy(toy['counts'])
        counts['constructor_exception_jobs'] = True
        with self.assertRaises(M.Refusal):
            M.build_plan(toy, counts)
        mutated = copy.deepcopy(toy)
        mutated['nested_targets'][3]['http_path'] = 'data/texture/a b.png'
        mutated['jobs'][1]['declarations'][1]['http_path'] = 'data/texture/a b.png'
        with self.assertRaises(M.Refusal):  # Unsupported authored names still refuse.
            M.build_plan(mutated, toy['counts'])

    def _fixture_response(self, spec, clock):
        class Response:
            def __init__(self):
                self.length = spec['initial_length']
                self.steps = [dict(s) for s in spec['steps']]
                self.pos, self.offset, self.reads, self.eof_reads, self.requests = 0, 0, 0, 0, []

            def read1(self, n):
                self.reads += 1
                self.requests.append(n)
                if self.pos >= len(self.steps):
                    raise AssertionError('read past script')
                step = self.steps[self.pos]
                if 'raises' in step:
                    raise {'OSError': OSError, 'AssertionError': AssertionError}[step['raises']](step['message'])
                if step.get('eof'):
                    self.eof_reads += 1
                    return b''
                data = bytes.fromhex(step['data_hex'])
                chunk = data[self.offset:self.offset + n]
                self.offset += len(chunk)
                if self.offset == len(data):
                    self.pos, self.offset = self.pos + 1, 0
                    if 'clock_when_fully_served' in step:
                        clock[0] = step['clock_when_fully_served']
                if self.length is not None:
                    self.length -= len(chunk)
                return chunk

            def unread_hex(self):
                if self.pos >= len(self.steps) or 'data_hex' not in self.steps[self.pos]:
                    return ''
                return bytes.fromhex(self.steps[self.pos]['data_hex'])[self.offset:].hex()
        return Response()

    def _fd(self):
        path = os.path.join(fresh('transfer'), 'body')
        return os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)

    def test_11_transport_cases(self):
        for case in AUTHORED['transport_cases']:
            with self.subTest(case['id']):
                clock = [case['clock']['initial_value']]
                response = self._fixture_response(case['response'], clock)
                fd = self._fd()
                try:
                    got = M.transfer(response, fd, clock=lambda: clock[0], **case['arguments'])
                    self.assertTrue(typed_eq(got, case['expected']), (case['id'], got))
                    self.assertEqual(os.pread(fd, 1 << 16, 0).hex(), case['expected_stored_hex'])
                    effects = case.get('expected_effects', {})
                    if effects.get('read1_must_not_be_called'):
                        self.assertEqual(response.reads, 0)
                    if any(k.startswith('do_not_read') for k in effects):
                        self.assertEqual(response.eof_reads, 0)
                    if 'unread_data_hex' in effects:
                        self.assertEqual(response.unread_hex(), effects['unread_data_hex'])
                    self.assertTrue(all(n <= M.READ_MAX for n in response.requests))
                finally:
                    os.close(fd)

    def test_3_write_controls(self):
        for case in AUTHORED['write_controls']:
            with self.subTest(case['id']):
                clock = [case['clock']['initial_value']]
                response = self._fixture_response(case['response'], clock)
                plan = list(case['write_plan'])
                seen = {'calls': 0, 'multi_byte': False, 'zero': False, 'error': False, 'positive': False}

                def write_fn(target, buffer):
                    step = plan[min(seen['calls'], len(plan) - 1)]
                    seen['calls'] += 1
                    if 'safety_sentinel_if_called' in step:
                        raise AssertionError('retried after zero')
                    if step.get('return_zero_without_storing'):
                        seen['zero'] = True
                        return 0
                    if 'raises' in step:
                        seen['error'] = True
                        raise OSError(step['message'])
                    if step.get('actually_store_at_most') == 1:
                        seen['multi_byte'] = seen['multi_byte'] or len(buffer) > 1
                        seen['positive'] = True
                        return os.write(target, bytes(buffer[:1]))
                    return os.write(target, bytes(buffer))
                fd = self._fd()
                try:
                    if 'expected_exception' in case:
                        with self.assertRaises(OSError):
                            M.transfer(response, fd, clock=lambda: clock[0], write_fn=write_fn, **case['arguments'])
                    else:
                        got = M.transfer(response, fd, clock=lambda: clock[0], write_fn=write_fn, **case['arguments'])
                        self.assertTrue(typed_eq(got, case['expected']))
                    self.assertEqual(os.pread(fd, 1 << 16, 0).hex(), case['expected_stored_hex'])
                    os.fstat(fd)  # Caller fd stays open.
                    effects = case['expected_effects']
                    if effects.get('zero_injection_observed'):
                        self.assertTrue(seen['zero'])
                        self.assertEqual(seen['calls'], effects['write_calls'])
                    if effects.get('error_injection_observed'):
                        self.assertTrue(seen['error'] and seen['positive'])
                    if effects.get('positive_short_injection_observed_if_multi_byte_buffer_requested'):
                        self.assertTrue(seen['multi_byte'])  # Candidate requests 3-byte buffers.
                finally:
                    os.close(fd)

    def test_write_all_progress_validation(self):
        fd = self._fd()
        try:
            for bad in (True, -1, 99, 1.0, None):
                with self.assertRaises(OSError):
                    M.write_all(fd, b'abc', lambda f, b, bad=bad: bad)
            calls = []

            def eintr(f, b):
                calls.append(1)
                if len(calls) == 1:
                    raise InterruptedError()
                return os.write(f, bytes(b))
            self.assertEqual(M.write_all(fd, b'xyz', eintr), 3)
        finally:
            os.close(fd)

    def test_transfer_argument_shapes(self):
        class R:
            length = None

            def read1(self, n):
                return b''
        fd = self._fd()
        try:
            for kwargs in ({'body_cap': True, 'aggregate_left': 1, 'deadline': 1},
                           {'body_cap': 1, 'aggregate_left': -1, 'deadline': 1},
                           {'body_cap': 1, 'aggregate_left': 1, 'deadline': float('inf')},
                           {'body_cap': 1, 'aggregate_left': 1, 'deadline': True}):
                with self.assertRaises(ValueError):
                    M.transfer(R(), fd, **kwargs)
            r = R()
            r.length = True
            with self.assertRaises(ValueError):
                M.transfer(r, fd, body_cap=1, aggregate_left=1, deadline=1)
        finally:
            os.close(fd)


# ---------------------------------------------------------------- admission helpers

class Admission(unittest.TestCase):
    def test_strict_json(self):
        for raw in (b'1e309', b'[-1e309]', b'{"a": 1e999}', b'NaN', b'[Infinity]', b'{"a":1,"a":2}', b'\xff',
                    b'{"a": -Infinity}'):
            with self.subTest(raw=raw):
                with self.assertRaises(M.Refusal):
                    M.strict_json(raw)
        self.assertTrue(typed_eq(M.strict_json(b'{"a": [1, 1.5, true, null]}'), {'a': [1, 1.5, True, None]}))

    def test_read_admitted_single_link_and_drift(self):
        root = fresh('admit')
        path = private_file(os.path.join(root, 'a'), b'hello')
        data, receipt = M.read_admitted(path, 5, hashlib.sha256(b'hello').hexdigest())
        self.assertEqual(data, b'hello')
        head, _ = M.read_admitted(path, keep=False, prefix=2)
        self.assertEqual(head, b'he')
        with self.assertRaises(M.Refusal):
            M.read_admitted(path, 4)
        with self.assertRaises(M.Refusal):
            M.read_admitted(path, 5, '0' * 64)
        with self.assertRaises(M.Refusal):
            M.read_admitted(path, limit=4)
        os.link(path, os.path.join(root, 'hard'))
        with self.assertRaises(M.Refusal):
            M.read_admitted(path)
        os.unlink(os.path.join(root, 'hard'))
        os.symlink(path, os.path.join(root, 'sym'))
        with self.assertRaises(M.Refusal):
            M.read_admitted(os.path.join(root, 'sym'))
        os.symlink(root, os.path.join(SCRATCH, 'linkdir-%d' % _SERIAL[0]))
        with self.assertRaises(M.Refusal):
            M.read_admitted(os.path.join(SCRATCH, 'linkdir-%d' % _SERIAL[0], 'a'))
        os.unlink(os.path.join(SCRATCH, 'linkdir-%d' % _SERIAL[0]))
        with self.assertRaises(M.Absent):
            M.read_admitted(os.path.join(root, 'missing'))
        with self.assertRaises(M.Refusal):
            M.read_admitted(path, deadline=1, clock=lambda: 9)

    def test_parse_rejects_bad_flags(self):
        good = ['--preflight', '--input-root', '/x', '--profile', PROFILE_REL]
        self.assertFalse(M.parse(good)['execute'])
        sha = 'a' * 64
        bad = [[], ['--preflight'], good + ['--preflight'], good + ['--execute'], good + ['--bogus'],
               good + ['--profile', PROFILE_REL], good + ['--output', '/o'],
               ['--execute', '--input-root', '/x', '--profile', PROFILE_REL, '--output', '/o'],
               ['--execute', '--input-root', '/x', '--profile', PROFILE_REL, '--root-reviewed-sha256', sha],
               ['--execute', '--input-root', '/x', '--profile', PROFILE_REL, '--output', 'rel',
                '--root-reviewed-sha256', sha],
               ['--execute', '--input-root', '/x', '--profile', PROFILE_REL, '--output', '/o',
                '--root-reviewed-sha256', 'A' * 64],
               ['--preflight=1', '--input-root', '/x', '--profile', PROFILE_REL],
               ['--preflight', '--input-root', '--profile', PROFILE_REL]]
        for argv in bad:
            with self.subTest(argv=argv):
                with self.assertRaises(M.Refusal):
                    M.parse(argv)

    def test_main_refusals_bounded_no_echo(self):
        secret = '/Users/secret-path-%d' % os.getpid()
        cases = [['--preflight', '--input-root', secret, '--profile', PROFILE_REL],
                 ['--preflight', '--input-root', CANONICAL, '--profile', os.path.join(CANONICAL, PROFILE_REL)],
                 ['--preflight', '--input-root', CANONICAL, '--profile', './' + PROFILE_REL],
                 ['--execute', '--input-root', CANONICAL, '--profile', PROFILE_REL,
                  '--output', os.path.join(SCRATCH, 'never-created'), '--root-reviewed-sha256', '0' * 64],
                 ['--nonsense', secret]]
        for argv in cases:
            with self.subTest(argv=argv[:2]):
                out = io.StringIO()
                with redirect_stdout(out):
                    code = M.main(argv)
                self.assertEqual(code, 2)
                text = out.getvalue()
                self.assertEqual(text.count('\n'), 1)
                self.assertLessEqual(len(text.encode()), 4096)
                self.assertNotIn('secret-path', text)
                self.assertNotIn('Traceback', text)
        self.assertFalse(os.path.exists(os.path.join(SCRATCH, 'never-created')))

    def test_import_and_pure_calls_do_no_io(self):
        script = r'''
import sys, os, json, hashlib, math, re, stat, time, builtins, importlib.util
events = []
armed = [False]
def hook(event, args):
    if armed[0] and event in ('open', 'os.mkdir', 'os.listdir', 'os.scandir', 'os.chmod', 'os.remove',
                              'subprocess.Popen', 'socket.connect', 'socket.bind', 'os.rename', 'os.truncate'):
        events.append((event, str(args[0]) if args else ''))
sys.addaudithook(hook)
path = sys.argv[1]
spec = importlib.util.spec_from_file_location('omt', path)
mod = importlib.util.module_from_spec(spec)
armed[0] = True
spec.loader.exec_module(mod)
cache = importlib.util.cache_from_source(path)
events[:] = [e for e in events if e[1] != cache]  # Import-machinery bytecode probe (absent under -B).
import_events = [e for e in events if e[1] != path]
armed[0] = False
data = open(sys.argv[2], 'rb').read()
toy = json.loads(data)['toy_catalog']
armed[0] = True
mod.build_plan(toy, toy['counts'])
mod.inspect_texture_header('tga', bytes(18))
mod.wire_target('data/a.bmp')
armed[0] = False
print(json.dumps({'import': import_events, 'pure': [e for e in events if e[1] != path][len(import_events):],
                  'modules': sorted(m for m in ('subprocess', 'socket', 'http.client') if m in sys.modules)}))
'''
        result = subprocess.run([sys.executable, '-I', '-B', '-c', script, DRIVER, AUTHORED_PATH],
                                stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=60)
        self.assertEqual(result.returncode, 0, result.stderr[-2000:])
        got = json.loads(result.stdout)
        self.assertEqual(got['import'], [])
        self.assertEqual(got['pure'], [])
        self.assertEqual(got['modules'], [])


# ---------------------------------------------------------------- full canonical metadata preflight

class CanonicalPreflight(unittest.TestCase):
    meta = None

    @classmethod
    def setUpClass(cls):
        with open(os.path.join(CANONICAL, PROFILE_REL), 'rb') as fh:
            profile = json.loads(fh.read())
        home = os.path.normpath(os.path.expanduser('~'))
        cls.natives = [os.path.join(home if n['base'] == 'home' else CANONICAL, n['path']) for n in profile['native']]
        cls.forbidden_prefixes = [os.path.dirname(p) for p in cls.natives]
        cls.hits = []
        before = sorted(os.listdir(os.path.join(CHECKOUT, '.tools', 'renewal')))

        def forbidden(path):
            if isinstance(path, int):
                return False
            text = os.fsdecode(os.fspath(path))
            return any(text == p or text.startswith(p + '/') for p in cls.natives + cls.forbidden_prefixes)

        def guard(name, real):
            def wrapper(path, *args, **kwargs):
                if forbidden(path):
                    cls.hits.append(name)
                    raise AssertionError('native access')
                return real(path, *args, **kwargs)
            return wrapper

        def deny(name):
            def wrapper(*args, **kwargs):
                cls.hits.append(name)
                raise AssertionError('forbidden effect')
            return wrapper
        patches = [mock.patch.object(os, 'lstat', guard('lstat', os.lstat)),
                   mock.patch.object(os, 'stat', guard('stat', os.stat)),
                   mock.patch.object(os, 'open', guard('open', os.open)),
                   mock.patch.object(os, 'mkdir', deny('mkdir')),
                   mock.patch.object(os, 'statvfs', deny('statvfs')),
                   mock.patch.object(subprocess, 'Popen', deny('Popen')),
                   mock.patch.object(socket, 'socket', deny('socket')),
                   mock.patch.object(http.client, 'HTTPConnection', deny('http'))]
        for p in patches:
            p.start()
        try:
            start = time.monotonic()
            cls.meta = M.load_metadata(CANONICAL, PROFILE_REL)
            cls.elapsed = time.monotonic() - start
            cls.specs = M.native_specs(cls.meta)  # Pure path computation; must not stat.
            out = io.StringIO()
            with redirect_stdout(out):
                cls.code = M.main(['--preflight', '--input-root', CANONICAL, '--profile', PROFILE_REL])
            cls.stdout = out.getvalue()
        finally:
            for p in reversed(patches):
                p.stop()
        cls.after = sorted(os.listdir(os.path.join(CHECKOUT, '.tools', 'renewal')))
        cls.before = before

    def test_no_native_or_effects(self):
        self.assertEqual(self.hits, [])
        self.assertEqual(self.before, self.after)
        self.assertEqual([s['path'] for s in self.specs], self.natives)

    def test_preflight_cli_line(self):
        self.assertEqual(self.code, 0)
        self.assertEqual(self.stdout.count('\n'), 1)
        self.assertLessEqual(len(self.stdout.encode()), 4096)
        line = json.loads(self.stdout)
        self.assertEqual(line['status'], 'preflight_ok')
        self.assertIsNone(line['native_qualification'])
        self.assertEqual(line['counts']['targets'], 8119)
        self.assertEqual(line['counts']['referrers'], 16142)
        self.assertEqual(line['counts']['roots'], 1296)
        self.assertEqual(line['counts']['kinds'], {'bmp': 7902, 'tga': 216, 'unknown': 1})
        self.assertNotIn(CANONICAL, self.stdout)

    def test_full_plan_retains_all_targets_and_referrers(self):
        meta, catalog = self.meta, self.meta['catalog']
        plans = meta['plans']
        self.assertLess(self.elapsed, 120)
        self.assertEqual(len(plans), 8119)
        self.assertEqual([p['index'] for p in plans], list(range(8119)))
        self.assertEqual(sum(len(p['referrers']) for p in plans), 16142)
        self.assertEqual(meta['referrers'], 16142)
        self.assertEqual(len(catalog['roots']), 1296)
        self.assertEqual(len(meta['gaps']), 82)
        self.assertEqual(len(catalog['prior_first_level_gaps']), 2)
        self.assertEqual(len(catalog['jobs']), 8166)
        self.assertEqual(len(catalog['model_parent_links']), 48980)
        self.assertEqual(meta['kind_counts'], {'bmp': 7902, 'tga': 216, 'unknown': 1})
        for p, t in zip(plans, catalog['nested_targets']):
            self.assertEqual(p['http_path'], t['http_path'])
            self.assertEqual(p['wire'], '/' + t['http_path'])
            self.assertEqual(p['catalog_pointer'], '/nested_targets/%d' % p['index'])
            self.assertTrue(typed_eq(p['referrers'], t['referrers']))
            self.assertIsNot(p['referrers'], t['referrers'])
        decoded = [unquote(p['http_path'], encoding='utf-8', errors='strict') for p in plans]
        self.assertEqual(len(set(decoded)), 8119)
        self.assertEqual(len(meta['sources']), 20)
        self.assertLessEqual(meta['plan_bytes'], 16 << 20)

    def test_engine_identity_and_binding(self):
        ns = self.meta['engine']
        self.assertEqual(self.meta['engine_pin']['sha256'], ENGINE_SHA)
        for name in M.BOUND_API:
            self.assertIs(ns[name], getattr(M, name))
        self.assertIs(ns['Observer'].request.__globals__, ns)
        self.assertEqual(ns['TASK'], 'T06.003.003.005')  # No identity/schema/profile/policy rebinding.
        self.assertEqual(ns['SCHEMA'], 'T06-map-dependency-observation-1')
        self.assertEqual(ns['PROFILE_SHA'], OLD_PROFILE_SHA)
        self.assertEqual(ns['POLICY']['asset_attempts'], 11134)
        self.assertNotEqual(ns['__name__'], '__main__')
        self.assertNotIn(ns['__name__'], sys.modules)

    def test_make_observer_production_defaults(self):
        observer = M.make_observer(self.meta, os.path.join(SCRATCH, 'not-created'), self.meta['driver_receipt'])
        self.assertEqual(observer.policy, M.POLICY)
        self.assertEqual(observer.container, os.path.join(CHECKOUT, '.tools', 'renewal'))
        self.assertEqual([n['path'] for n in observer.natives], self.natives)
        self.assertEqual(observer.report['schema'], 'T06-nested-texture-observation-1')
        self.assertEqual(len(observer.report['targets']), 8119)
        refs = observer.report['catalog_refs']
        self.assertEqual((refs['roots'], refs['targets'], refs['referrers'], len(refs['gap_root_ordinals'])),
                         (1296, 8119, 16142, 82))
        self.assertEqual(refs['targets_pointer'], '/nested_targets')
        self.assertTrue(all(r['header']['state'] == 'not_checked' and 'signature' not in r
                            for r in observer.report['targets']))
        self.assertFalse(os.path.exists(os.path.join(SCRATCH, 'not-created')))


# ---------------------------------------------------------------- production observer with fakes

HEALTH = b'{"status":"ok","service":"robrowser-remoteclient"}'
TGA_HEADER = bytes.fromhex('000002000000000000000000010001001800')


class World:
    """Fake reader process + loopback HTTP. Writes the native-style missing log for 404s."""

    def __init__(self, output):
        self.output = output
        self.now = [1000.0]
        self.pid = 424242
        self.routes = {
            '/api/health': (200, {'Content-Type': 'application/json'}, HEALTH, True),
            '/data/texture/%20bark.bmp': (200, {'Content-Type': 'image/bmp'}, b'BM' + b'\x01' * 40, True),
            '/data/texture/unused.tga': (200, {'Content-Type': 'image/x-tga'}, TGA_HEADER + b'\x10\x20\x30', False),
            '/data/texture/Bark.bmp': (404, {'Content-Type': 'text/plain'}, b'missing', True),
            '/data/texture/animated.png': (200, {'Content-Type': 'image/png'}, b'\x89PNG\r\n\x1a\n' + b'\0' * 24, True),
        }
        self.requests, self.responses, self.connections = [], [], []
        self.listener, self.port_busy_after, self.group_after = True, False, []
        self.exit_code, self.ignore_terminate, self.startup_exit = 0, False, False
        self.poll_after_requests = None
        self.write_log, self.log_extra_field = True, False
        self.hooks = {}
        self.proc = None
        self.calls = {'terminate': 0, 'kill': 0, 'popen': 0}

    def hook(self, name, *args):
        fn = self.hooks.get(name)
        if fn:
            fn(*args)

    def log_404(self, wire):
        if not self.write_log:
            return
        logs = os.path.join(self.output, 'logs')
        if not os.path.isdir(logs):
            private_dir(logs)
        requested = unquote(wire[1:], encoding='utf-8')
        entry = {'timestamp': '2026-10-20T00:00:00.000Z', 'requestedPath': requested,
                 'grfPath': requested.replace('/', '\\'), 'mappedPath': None}
        if self.log_extra_field:
            entry['extra'] = 1
        line = (json.dumps(entry) + '\n').encode()
        path = os.path.join(logs, 'missing-files.log')
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        try:
            os.write(fd, line)
        finally:
            os.close(fd)


class FakeProc:
    def __init__(self, world):
        self.world, self.pid, self.returncode = world, world.pid, None

    def poll(self):
        w = self.world
        if self.returncode is None and w.startup_exit:
            self.returncode = 1
        if self.returncode is None and w.poll_after_requests is not None and len(w.requests) >= w.poll_after_requests:
            self.returncode = 1
        return self.returncode

    def terminate(self):
        self.world.calls['terminate'] += 1
        if not self.world.ignore_terminate:
            self.returncode = self.world.exit_code
            self.world.listener = False

    def wait(self, timeout=None):
        if self.returncode is None:
            raise subprocess.TimeoutExpired('fake', timeout)
        return self.returncode

    def kill(self):
        self.world.calls['kill'] += 1
        self.returncode = -9
        self.world.listener = False


class FakeResponse:
    def __init__(self, world, status, headers, body, framed):
        self.world, self.status, self._headers, self.body = world, status, headers, body
        self.length = len(body) if framed else None
        self.offset, self.closed = 0, False

    def getheader(self, name):
        return self._headers.get(name)

    def read1(self, n):
        self.world.hook('read', self)
        chunk = self.body[self.offset:self.offset + n]
        self.offset += len(chunk)
        if self.length is not None:
            self.length -= len(chunk)
        if self.offset == len(self.body):
            self.world.hook('final_read', self)
        return chunk

    def close(self):
        self.closed = True
        self.world.hook('response_close', self)


class FakeConnection:
    def __init__(self, world):
        self.world, self.sock, self.closed, self.path = world, None, False, None

    def request(self, method, path, headers=None):
        assert method == 'GET' and headers == {'Accept-Encoding': 'identity'}
        self.path = path
        self.world.requests.append(path)

    def getresponse(self):
        status, headers, body, framed = self.world.routes[self.path]
        if status == 404:
            self.world.log_404(self.path)
        response = FakeResponse(self.world, status, headers, body, framed)
        self.world.responses.append(response)
        return response

    def close(self):
        self.closed = True
        self.world.hook('connection_close', self)


class FakeOps:
    def __init__(self, world):
        self.world = world

    def clock(self):
        return self.world.now[0]

    def sleep(self, seconds):
        self.world.now[0] += seconds

    def free_bytes(self, path):
        return 1 << 50

    def fresh_port(self):
        return 45678

    def popen(self, argv, cwd, env):
        w = self.world
        w.calls['popen'] += 1
        w.argv, w.cwd, w.env = argv, cwd, env
        w.hook('popen')
        w.proc = FakeProc(w)
        return w.proc

    def getpgid(self, pid):
        return pid

    def owned_listener(self, pid, port):
        self.world.hook('owned_listener')
        return self.world.listener

    def port_listeners(self, port):
        return self.world.proc is not None and (self.world.listener or self.world.port_busy_after)

    def group_members(self, pgid):
        self.world.hook('group_members')
        return list(self.world.group_after)

    def connect(self, port, timeout):
        assert 0 < timeout <= 5
        con = FakeConnection(self.world)
        self.world.connections.append(con)
        return con


class Harness:
    """Tiny metadata from the frozen toy catalog plus real tiny owned files."""

    def __init__(self, engine=None):
        self.root = fresh('observer')
        files = private_dir(os.path.join(self.root, 'inputs'))
        toy = AUTHORED['toy_catalog']
        catalog_bytes = json.dumps(toy, ensure_ascii=True).encode()
        self.catalog_path = private_file(os.path.join(files, 'catalog.json'), catalog_bytes)
        engine_bytes, engine_receipt = M.read_admitted(ENGINE_PATH, None, ENGINE_SHA)
        self.engine_copy = private_file(os.path.join(files, 'engine.py'), engine_bytes)
        self.source_path = private_file(os.path.join(files, 'rule.js'), b'// tiny rule source\n')
        profile_bytes, profile_receipt = M.read_admitted(os.path.join(CHECKOUT, PROFILE_REL), M.PROFILE_BYTES,
                                                         M.PROFILE_SHA)
        _, authored_receipt = M.read_admitted(AUTHORED_PATH)
        _, catalog_receipt = M.read_admitted(self.catalog_path)
        sources = []
        for path in (self.engine_copy, self.source_path):
            _, receipt = M.read_admitted(path)
            sources.append(dict(path=os.path.relpath(path, self.root), **receipt))
        self.natives = []
        for name in M.NATIVE_NAMES:
            data = ('fake %s\n' % name).encode()
            path = private_file(os.path.join(files, name), data)
            self.natives.append({'name': name, 'path': path, 'bytes': len(data),
                                 'sha256': hashlib.sha256(data).hexdigest()})
        plans = M.build_plan(toy, toy['counts'])
        self.engine = engine if engine is not None else M.load_engine(engine_bytes, ENGINE_PATH)
        driver = M.own_sha()
        self.meta = {'input_root': self.root, 'profile_path': os.path.join(CHECKOUT, PROFILE_REL),
                     'profile': json.loads(profile_bytes), 'profile_receipt': profile_receipt,
                     'authored_receipt': authored_receipt, 'sources': sources, 'catalog_bytes': catalog_bytes,
                     'catalog_receipt': catalog_receipt, 'catalog_path': self.catalog_path, 'catalog': toy,
                     'plans': plans, 'referrers': sum(len(p['referrers']) for p in plans),
                     'gaps': list(toy['remaining_gap_root_ordinals']),
                     'kind_counts': {k: sum(p['kind'] == k for p in plans) for k in M.HEADER_KINDS},
                     'driver_receipt': driver, 'engine': self.engine,
                     'engine_pin': {'path': M.ENGINE_REL, 'bytes': engine_receipt['bytes'],
                                    'sha256': engine_receipt['sha256']}}
        self.meta['recheck'] = [dict(path=M._driver_path(), **driver),
                                dict(path=os.path.join(CHECKOUT, PROFILE_REL), **profile_receipt),
                                dict(path=AUTHORED_PATH, **authored_receipt),
                                dict(path=self.catalog_path, **catalog_receipt)] + \
            [dict(s, path=os.path.join(self.root, s['path'])) for s in sources]
        self.container = private_dir(os.path.join(self.root, 'container'))
        self.output = os.path.join(self.container, 'out')
        self.world = World(self.output)
        self.policy = dict(M.POLICY, asset_attempts=4)

    def observer(self, write_fn=None, policy=None):
        return M.make_observer(self.meta, self.output, self.meta['driver_receipt'], ops=FakeOps(self.world),
                               natives=self.natives, policy=policy or self.policy, container=self.container,
                               write_fn=write_fn)

    def report(self):
        with open(os.path.join(self.output, 'report.json'), 'rb') as fh:
            raw = fh.read()
        return raw, M.strict_json(raw)

    def owned_resources_closed(self, test, fds_before):
        test.assertEqual(open_fds(), fds_before)
        test.assertTrue(all(r.closed for r in self.world.responses))
        test.assertTrue(all(c.closed for c in self.world.connections))


def assert_new_provenance(test, raw, report):
    text = raw.decode()
    test.assertEqual((report['schema'], report['task'], report['mode']),
                     ('T06-nested-texture-observation-1', 'T06.003.003.008', 'execute'))
    test.assertNotIn('signature', text)
    test.assertNotIn('T06-map-dependency-observation-1', text)
    test.assertNotIn(OLD_PROFILE_SHA, text)
    test.assertNotIn('"/targets"', text)
    test.assertEqual(report['profile_pin']['sha256'], NEW_PROFILE_SHA)
    test.assertEqual(report['catalog_refs']['targets_pointer'], '/nested_targets')
    if report['launch'] is not None:
        test.assertEqual(report['launch']['profile_sha256'], NEW_PROFILE_SHA)
    for row in report['targets']:
        test.assertEqual(row['referrers_pointer'], row['catalog_pointer'] + '/referrers')
        test.assertEqual(set(row['header']), {'kind', 'state', 'prefix_hex', 'tga'})
        if row['header']['state'] == 'not_checked':
            test.assertIsNone(row['header']['prefix_hex'])
            test.assertIsNone(row['header']['tga'])


class ProductionObserver(unittest.TestCase):
    def test_root_final_io_failures_retain_complete_observations(self):
        for fault in ('native_close', 'native_read', 'missing_log_close'):
            with self.subTest(fault=fault):
                h = Harness()
                observer = h.observer()
                target = (os.path.join(h.output, 'logs', 'missing-files.log')
                          if fault == 'missing_log_close' else h.natives[0]['path'])
                fired = []
                real_close, real_read = os.close, os.read

                def eligible(fd):
                    return h.world.calls['terminate'] > 0 and fd_path(fd) == target and not fired

                def close(fd):
                    inject = fault != 'native_read' and eligible(fd)
                    real_close(fd)
                    if inject:
                        fired.append(True)
                        raise OSError('root close fault after actual release')

                def read(fd, size):
                    if fault == 'native_read' and eligible(fd):
                        fired.append(True)
                        raise OSError('root postcheck read fault')
                    return real_read(fd, size)

                before = open_fds()
                with mock.patch.object(os, 'close', close), mock.patch.object(os, 'read', read):
                    self.assertEqual(observer.run(), 1)
                self.assertEqual(fired, [True])
                h.owned_resources_closed(self, before)
                _, report = h.report()
                self.assertEqual(sum(r['attempted'] for r in report['targets']), 4)
                self.assertEqual(report['targets'], observer.report['targets'])
                self.assertTrue(report['cleanup']['clean'])
                self.assertFalse(report['acquisition_and_cleanup_valid'])
                if fault == 'missing_log_close':
                    self.assertFalse(report['missing_log']['valid'])
                else:
                    self.assertFalse(report['postchecks_valid'])

    def test_root_metadata_close_completion_obeys_deadline(self):
        h = Harness()
        now, fired = [0.0], []
        real_close = os.close

        def close(fd):
            inject = fd_path(fd) == h.source_path
            real_close(fd)
            if inject:
                fired.append(True)
                now[0] = 121.0

        with mock.patch.object(os, 'close', close):
            with self.assertRaises(M.Refusal):
                M.read_admitted(h.source_path, deadline=120.0, clock=lambda: now[0])
        self.assertEqual(fired, [True])

    def run_observer(self, harness, write_fn=None, policy=None):
        fds = open_fds()
        observer = harness.observer(write_fn=write_fn, policy=policy)
        code = observer.run()
        harness.owned_resources_closed(self, fds)  # Candidate cleanup, before harness cleanup.
        raw, report = harness.report()
        assert_new_provenance(self, raw, report)
        return observer, code, report

    def test_complete_run_headers_and_coverage(self):
        h = Harness()
        snapshots = {}

        def capture(name):
            def fn(*_):
                if name not in snapshots:
                    snapshots[name] = h.report()
            return fn
        h.world.hooks.update(popen=capture('prelaunch'), owned_listener=capture('launch'))
        observer, code, report = self.run_observer(h)
        self.assertEqual(code, 0, (report['halt_reason'], report['errors'], report['cleanup'], report['tree'],
                                   report['missing_log']))
        for name in ('prelaunch', 'launch'):
            assert_new_provenance(self, *snapshots[name])
        self.assertIsNone(snapshots['prelaunch'][1]['launch'])
        self.assertEqual(snapshots['launch'][1]['launch']['pid'], h.world.pid)
        self.assertGreaterEqual(observer.freezes, 3)
        self.assertEqual(h.world.requests, ['/api/health'] + [p['wire'] for p in h.meta['plans']])
        rows = report['targets']
        self.assertEqual([r['stop_reason'] for r in rows], ['complete', 'complete', 'http_404', 'complete'])
        self.assertEqual(rows[0]['header'], {'kind': 'bmp', 'state': 'match', 'prefix_hex': '424d', 'tga': None})
        self.assertEqual(rows[1]['header']['state'], 'observed')
        self.assertEqual(rows[1]['header']['prefix_hex'], TGA_HEADER.hex())
        self.assertTrue(rows[1]['header']['tga']['checks_all'])
        self.assertEqual(rows[2]['header']['state'], 'not_checked')
        self.assertEqual(rows[3]['header'], {'kind': 'unknown', 'state': 'unclassified',
                                             'prefix_hex': (b'\x89PNG\r\n\x1a\n' + b'\0' * 10).hex(), 'tga': None})
        cov = report['coverage_counts']
        self.assertEqual(cov['header_states'], {'bmp:match': 1, 'tga:observed': 1, 'bmp:not_checked': 1,
                                                'unknown:unclassified': 1})
        self.assertEqual(sum(cov['header_states'].values()), 4)
        self.assertEqual(cov['tga_header_checks'], {'observed': 1, 'all_true': 1, 'any_false': 0})
        self.assertEqual(cov['complete_200_bytes_available'], 3)
        self.assertEqual(cov['http_404'], 1)
        self.assertNotIn('complete_200_matching_prefix', cov)
        self.assertEqual(report['catalog_refs']['prior_gaps_pointer'], '/prior_first_level_gaps')
        self.assertEqual(report['engine_pin']['sha256'], ENGINE_SHA)
        self.assertTrue(report['missing_log']['valid'] and report['tree']['valid'] and report['cleanup']['clean'])
        self.assertEqual(report['totals']['wire_bytes'], len(HEALTH) + 42 + 21 + 7 + 32)
        with open(os.path.join(h.output, 'catalog-input.json'), 'rb') as fh:
            self.assertEqual(fh.read(), h.meta['catalog_bytes'])
        self.assertEqual(h.world.env['PORT'], '45678')
        self.assertEqual(len(h.world.env), 17)
        self.assertEqual(h.world.argv, [h.natives[0]['path']])
        for root, dirs, files in os.walk(h.output):
            for d in dirs:
                self.assertEqual(stat.S_IMODE(os.lstat(os.path.join(root, d)).st_mode), 0o700)
            for f in files:
                self.assertEqual(stat.S_IMODE(os.lstat(os.path.join(root, f)).st_mode), 0o600)

    def test_engine_dispatches_through_bound_transfer(self):
        engine_bytes, _ = M.read_admitted(ENGINE_PATH, None, ENGINE_SHA)
        engine = M.load_engine(engine_bytes, ENGINE_PATH)
        self.assertIs(engine['transfer'], M.transfer)
        calls = []

        def spy(*args, **kwargs):
            calls.append(1)
            return M.transfer(*args, **kwargs)
        engine['transfer'] = spy  # Test-only spy in this fresh test namespace.
        h = Harness(engine=engine)
        observer, code, report = self.run_observer(h)
        self.assertEqual(len(calls), 5)  # Health plus four targets dispatched via the namespace name.
        self.assertIsNone(report['halt_reason'])
        self.assertTrue(report['all_targets_attempted'])
        self.assertFalse(observer.engine_bound()['transfer'])  # The production postcheck detects the spy.
        self.assertIs(report['postchecks_valid'], False)
        self.assertEqual(code, 1)

    def test_empty_html_200_are_inspected_gaps(self):
        h = Harness()
        h.world.routes['/data/texture/%20bark.bmp'] = (200, {'Content-Type': 'image/bmp'}, b'', True)
        h.world.routes['/data/texture/unused.tga'] = (200, {'Content-Type': 'text/html'}, b'<html>', True)
        _, code, report = self.run_observer(h)
        self.assertEqual(code, 0)
        rows = report['targets']
        self.assertEqual(rows[0]['stop_reason'], 'empty_200')
        self.assertEqual(rows[0]['header'], {'kind': 'bmp', 'state': 'short', 'prefix_hex': '', 'tga': None})
        self.assertEqual(rows[1]['stop_reason'], 'html_200')
        self.assertEqual(rows[1]['header']['state'], 'short')
        self.assertEqual(report['coverage_counts']['complete_200_bytes_available'], 1)

    def test_short_writes_complete(self):
        h = Harness()
        fired = []

        def short(fd, buffer):
            if len(buffer) > 1:
                fired.append(len(buffer))
                return os.write(fd, bytes(buffer[:1]))
            return os.write(fd, bytes(buffer))
        _, code, report = self.run_observer(h, write_fn=short)
        self.assertEqual(code, 0)
        self.assertTrue(fired)
        self.assertTrue(all(r['stored']['complete'] for r in report['targets'] if r['http_status'] == 200))

    def _fatal_suffix(self, report, first_unattempted, reason):
        for row in report['targets'][first_unattempted:]:
            self.assertFalse(row['attempted'])
            self.assertEqual(row['stop_reason'], reason)
            self.assertEqual(row['wire_bytes'], 0)
            self.assertIsNone(row['request_index'])
            self.assertEqual(row['header']['state'], 'not_checked')

    def test_zero_write_halts_storage(self):
        h = Harness()
        fired = []

        def zero(fd, buffer):
            if h.world.requests[-1] != '/api/health':
                fired.append(1)
                return 0
            return os.write(fd, bytes(buffer))
        _, code, report = self.run_observer(h, write_fn=zero)
        self.assertEqual(code, 1)
        self.assertEqual(fired, [1])
        self.assertEqual(report['halt_reason'], 'storage_failure')
        row = report['targets'][0]
        self.assertEqual((row['stop_reason'], row['stored']['error'], row['stored']['complete']),
                         ('storage_error', 'storage_error', False))
        self.assertEqual(row['wire_bytes'], 42)  # Received bytes retained despite storage failure.
        self._fatal_suffix(report, 1, 'storage_failure')

    def test_partial_then_error_write(self):
        h = Harness()
        fired = []

        def partial(fd, buffer):
            if h.world.requests[-1] == '/api/health':
                return os.write(fd, bytes(buffer))
            fired.append(1)
            if len(fired) == 1:
                return os.write(fd, bytes(buffer[:1]))
            raise OSError('authored write fault')
        _, code, report = self.run_observer(h, write_fn=partial)
        self.assertEqual(code, 1)
        self.assertEqual(len(fired), 2)
        row = report['targets'][0]
        self.assertEqual(row['stored']['bytes'], 1)
        self.assertFalse(row['stored']['complete'])
        self._fatal_suffix(report, 1, 'storage_failure')

    def test_fd_close_fault(self):
        h = Harness()
        real_close, fired = os.close, []

        def close(fd):
            path = fd_path(fd)
            real_close(fd)
            if path.endswith('/out/000002') and not fired:
                fired.append(path)
                raise OSError('authored close fault')
        fds = open_fds()
        observer = h.observer()
        with mock.patch.object(os, 'close', close):
            code = observer.run()
        h.owned_resources_closed(self, fds)
        raw, report = h.report()
        assert_new_provenance(self, raw, report)
        self.assertEqual(code, 1)
        self.assertEqual(len(fired), 1)
        self.assertEqual(report['targets'][1]['stored']['error'], 'storage_close_error')
        self.assertEqual(report['halt_reason'], 'storage_failure')
        self._fatal_suffix(report, 2, 'storage_failure')

    def test_response_and_connection_close_faults(self):
        for which in ('response_close', 'connection_close'):
            with self.subTest(which):
                h = Harness()
                fired = []

                def fault(obj, fired=fired, h=h):
                    if len(h.world.requests) == 2 and not fired:
                        fired.append(1)
                        raise OSError('authored close fault')
                h.world.hooks[which] = fault
                _, code, report = self.run_observer(h)
                self.assertEqual(code, 1)
                self.assertEqual(fired, [1])
                self.assertEqual(report['halt_reason'], 'resource_close_failure')
                self._fatal_suffix(report, 1, 'resource_close_failure')

    def test_health_inclusive_aggregate_cap(self):
        h = Harness()
        policy = dict(h.policy, aggregate_bytes_including_health=len(HEALTH) + 10)
        _, code, report = self.run_observer(h, policy=policy)
        self.assertEqual(code, 1)
        self.assertEqual(report['halt_reason'], 'aggregate_cap')
        self.assertEqual(report['targets'][0]['stop_reason'], 'aggregate_cap')
        self.assertEqual(report['targets'][0]['wire_bytes'], 10)
        self.assertEqual(report['totals']['wire_bytes'], len(HEALTH) + 10)
        self._fatal_suffix(report, 1, 'aggregate_cap')

    def test_late_final_read(self):
        h = Harness()

        def late(response):
            if len(h.world.requests) == 2:  # Framed BMP: final read reaches the deadline.
                h.world.now[0] += 5000
        h.world.hooks['final_read'] = late
        _, code, report = self.run_observer(h)
        self.assertEqual(code, 1)
        self.assertEqual(report['halt_reason'], 'acquisition_deadline')
        row = report['targets'][0]
        self.assertEqual(row['stop_reason'], 'complete')
        self.assertTrue(row['stored']['complete'])
        self.assertEqual(row['header']['state'], 'match')
        self._fatal_suffix(report, 1, 'acquisition_deadline')

    def test_header_verification_failure_is_storage_failure(self):
        h = Harness()

        def tamper(response):
            if len(h.world.requests) == 2:
                with open(os.path.join(h.output, '000001'), 'ab') as fh:
                    fh.write(b'!')
        h.world.hooks['response_close'] = tamper
        _, code, report = self.run_observer(h)
        self.assertEqual(code, 1)
        row = report['targets'][0]
        self.assertEqual(row['stored']['error'], 'stored_mismatch')
        self.assertEqual(row['header']['state'], 'not_checked')
        self.assertEqual(report['halt_reason'], 'storage_failure')

    def test_reader_loss(self):
        h = Harness()
        h.world.poll_after_requests = 3
        _, code, report = self.run_observer(h)
        self.assertEqual(code, 1)
        self.assertEqual(report['halt_reason'], 'reader_lost')
        self._fatal_suffix(report, 2, 'reader_lost')

    def test_startup_failure_checkpoint_provenance(self):
        h = Harness()
        h.world.startup_exit = True
        _, code, report = self.run_observer(h)
        self.assertEqual(code, 1)
        self.assertEqual(report['halt_reason'], 'reader_exited_at_startup')
        self.assertEqual(h.world.requests, [])
        self._fatal_suffix(report, 0, 'reader_exited_at_startup')

    def test_final_listener_query_failure(self):
        h = Harness()
        count = [0]

        def boom():
            count[0] += 1
            if len(h.world.requests) == 5 and count[0] == 2:
                raise RuntimeError('listener query')
        h.world.hooks['owned_listener'] = boom
        _, code, report = self.run_observer(h)
        self.assertEqual(code, 1)
        self.assertEqual(report['halt_reason'], 'internal_failure')

    def test_drift_detected(self):
        for target in ('source', 'engine', 'catalog', 'native'):
            with self.subTest(target):
                h = Harness()
                path = {'source': h.source_path, 'engine': h.engine_copy, 'catalog': h.catalog_path,
                        'native': h.natives[3]['path']}[target]
                fired = []

                def drift(path=path, fired=fired):
                    with open(path, 'ab') as fh:
                        fh.write(b' ')
                    fired.append(1)
                h.world.hooks['group_members'] = drift
                _, code, report = self.run_observer(h)
                self.assertEqual(fired, [1])
                self.assertEqual(code, 1)
                self.assertFalse(report['postchecks_valid'])
                self.assertFalse(report['acquisition_and_cleanup_valid'])

    def test_exit_and_residue_failures(self):
        cases = {'forced': {'ignore_terminate': True}, 'unknown_exit': {'exit_code': 3},
                 'group_residue': {'group_after': [424242]}, 'listener_residue': {'port_busy_after': True}}
        for name, attrs in cases.items():
            with self.subTest(name):
                h = Harness()
                for k, v in attrs.items():
                    setattr(h.world, k, v)
                _, code, report = self.run_observer(h)
                self.assertEqual(code, 1)
                self.assertFalse(report['cleanup']['clean'])
                self.assertTrue(report['all_targets_attempted'])
                if name == 'forced':
                    self.assertTrue(report['cleanup']['forced_kill'])
                    self.assertEqual(h.world.calls['kill'], 1)

    def test_strict_log_and_tree(self):
        cases = {'absent_log': lambda w: setattr(w, 'write_log', False),
                 'extra_field': lambda w: setattr(w, 'log_extra_field', True),
                 'extra_file': lambda w: w.hooks.__setitem__('group_members', lambda: private_file(
                     os.path.join(w.output, 'server.log'), b'x'))}
        for name, setup in cases.items():
            with self.subTest(name):
                h = Harness()
                setup(h.world)
                _, code, report = self.run_observer(h)
                self.assertEqual(code, 1)
                if name == 'extra_file':
                    self.assertFalse(report['tree']['valid'])
                    self.assertIn('server.log', report['tree']['unexpected'])
                else:
                    self.assertFalse(report['missing_log']['valid'])

    def test_final_publication_failure(self):
        h = Harness()
        h.world.hooks['group_members'] = lambda: private_dir(os.path.join(h.output, '.report-next'))
        fds = open_fds()
        observer = h.observer()
        code = observer.run()
        h.owned_resources_closed(self, fds)
        self.assertEqual(code, 1)
        self.assertEqual(observer.halt, 'publication_failure')
        raw, report = h.report()  # Earlier persisted checkpoint retained.
        assert_new_provenance(self, raw, report)

    def test_existing_output_refused_before_creation(self):
        h = Harness()
        private_dir(h.output)
        observer = h.observer()
        self.assertEqual(observer.run(), 2)
        self.assertEqual(os.listdir(h.output), [])
        self.assertEqual(h.world.calls['popen'], 0)

    def test_provenance_freeze_rejects_old_fields(self):
        h = Harness()
        observer = h.observer()
        observer.report['targets'][0]['signature'] = {'kind': 'bmp', 'state': 'not_checked', 'prefix_hex': None}
        with self.assertRaises(h.engine['Fatal']):
            observer.freeze()


if __name__ == '__main__':
    unittest.main(verbosity=2)
