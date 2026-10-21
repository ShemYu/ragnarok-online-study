"""Authored controls and fake-object lifecycle tests for observe_map_dependencies.

No native binary/GRF/asset bodies, real process launch, HTTP or game/browser
state are touched. Tiny private files live under this checkout's
.tools/renewal (0700 directories/0600 files). Legacy (T06.003.003.005) metadata
tests read the root-prepared read-only legacy snapshot (OBSERVE_INPUT_ROOT);
T07.007.006 tests read the canonical input root (OBSERVE_NEW_INPUT_ROOT).
Neither variable bypasses the CLI pins; both default to the canonical checkout.
"""
import errno
import hashlib
import http.client
import io
import json
import os
import shutil
import socket
import stat
import subprocess
import sys
import threading
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import observe_map_dependencies as omd  # noqa: E402

CHECKOUT = Path(__file__).resolve().parents[2]
AUTHORED = CHECKOUT / 'docs/project/fixtures/T06.003.003.005-authored.json'
PROFILE = CHECKOUT / 'docs/project/fixtures/T06.003.003.005-profile.json'
AUTHORED_SHA = '8c06aceab400e87416cb4486991daf20d93f1d19b8a644dd10318ab45343f989'
CANONICAL = '/Users/shem/orca/workspaces/game-reverse-engineering/reverse-the-Ragnarok-Online-to-play-by-myself'
INPUT_ROOT = os.environ.get('OBSERVE_INPUT_ROOT', CANONICAL + '/.tools/renewal/t07-007-006-legacy-metadata-1/snapshot')
NEW_INPUT_ROOT = os.environ.get('OBSERVE_NEW_INPUT_ROOT', CANONICAL)
NEW_PROFILE = CHECKOUT / 'docs/project/fixtures/T07.007.006-profile.json'
NEW_PROFILE_SHA = '0615c6d9e6e7990acc3f9012d2028115fce0543bd5fe298bfb544953865db5c6'
PRIVATE = CHECKOUT / '.tools/renewal/t06-005-claude-tests'
HEALTH_BODY = b'{"status":"ok","service":"robrowser-remoteclient"}'
EMPTY_SHA = hashlib.sha256(b'').hexdigest()


def private_dir(path):
    path.mkdir(mode=0o700, parents=True, exist_ok=True)
    os.chmod(path, 0o700)
    return path


def open_fds():
    return set(int(n) for n in os.listdir('/dev/fd'))


class Clock:
    def __init__(self, value=0):
        self.value = value

    def __call__(self):
        return self.value


class AuthoredResponse:
    """fixture_adapter_rules: steps, framing and clock updates."""

    def __init__(self, spec, clock):
        self.length, self.steps, self.clock = spec['initial_length'], spec['steps'], clock
        self.pos, self.offset, self.reads, self.eof_reads = 0, 0, [], 0

    def read1(self, n):
        self.reads.append(n)
        step = self.steps[self.pos]
        if 'raises' in step:
            raise {'OSError': OSError, 'AssertionError': AssertionError}[step['raises']](step['message'])
        if step.get('eof'):
            self.eof_reads += 1
            return b''
        data = bytes.fromhex(step['data_hex'])
        out = data[self.offset:self.offset + n]
        self.offset += len(out)
        if self.offset == len(data):
            self.pos, self.offset = self.pos + 1, 0
            if 'clock_when_fully_served' in step:
                self.clock.value = step['clock_when_fully_served']
        if self.length is not None:
            self.length -= len(out)
        return out

    def unread(self):
        step = self.steps[self.pos]
        return bytes.fromhex(step['data_hex'])[self.offset:] if 'data_hex' in step else b''


class TinyFile:
    def __init__(self, case):
        private_dir(PRIVATE)
        self.path = PRIVATE / ('store-%s-%d' % (case, os.getpid()))
        self.fd = os.open(self.path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)

    def stored(self):
        os.fstat(self.fd)  # Caller-owned descriptor must remain open.
        return self.path.read_bytes()

    def close(self):
        os.close(self.fd)
        self.path.unlink()


AUTH = json.loads(AUTHORED.read_bytes())


class AuthoredControls(unittest.TestCase):
    def test_fixture_pin(self):
        self.assertEqual(hashlib.sha256(AUTHORED.read_bytes()).hexdigest(), AUTHORED_SHA)
        self.assertEqual({k: len(AUTH[k + ('_cases' if k != 'write_controls' else '')]) for k in ('wire', 'transport', 'signature', 'write_controls')},
                         {'wire': 16, 'transport': 11, 'signature': 10, 'write_controls': 3})

    def test_wire_cases(self):
        for case in AUTH['wire_cases']:
            with self.subTest(case['id']):
                if 'returns' in case['expected']:
                    self.assertEqual(omd.wire_target(case['http_path']), case['expected']['returns'])
                else:
                    with self.assertRaises(ValueError) as caught:
                        omd.wire_target(case['http_path'])
                    if case['http_path']:
                        self.assertNotIn(case['http_path'], str(caught.exception))
                        self.assertNotIn('model', str(caught.exception))

    def test_wire_additional_policy(self):
        for bad in ('data\\a.rsm', 'data/a.rsm/', 'a/"b', 'a/<b', 'a/%zz', 7, None, 'a/b`'):
            with self.subTest(repr(bad)):
                self.assertRaises(ValueError, omd.wire_target, bad)
        self.assertEqual(omd.wire_target("a/$&+,;=:@~-._/%Aa"), "/a/$&+,;=:@~-._/%Aa")

    def run_transfer(self, case, write_fn=None):
        clock = Clock(case['clock']['initial_value'])
        response = AuthoredResponse(case['response'], clock)
        store = TinyFile(case['id'])
        try:
            try:
                result = omd.transfer(response, store.fd, clock=clock, write_fn=write_fn, **case['arguments'])
            except Exception as exc:
                return exc, response, store.stored()
            return result, response, store.stored()
        finally:
            store.close()

    def test_transport_cases(self):
        for case in AUTH['transport_cases']:
            with self.subTest(case['id']):
                result, response, stored = self.run_transfer(case)
                self.assertEqual(result, case['expected'])
                self.assertEqual(list(result), ['outcome', 'bytes', 'response_complete', 'complete_sha256', 'partial_sha256', 'late'])
                self.assertEqual(stored.hex(), case['expected_stored_hex'])
                self.assertTrue(all(n <= omd.READ_MAX for n in response.reads))
                effects = case.get('expected_effects', {})
                if effects.get('read1_must_not_be_called'):
                    self.assertEqual(response.reads, [])
                if effects.get('do_not_read_eof_after_framing_reaches_zero') or effects.get('do_not_read_eof_after_body_cap'):
                    self.assertEqual(response.eof_reads, 0)
                if 'unread_data_hex' in effects:
                    self.assertEqual(response.unread().hex(), effects['unread_data_hex'])
                    self.assertEqual(response.eof_reads, 0)

    def test_write_controls(self):
        for case in AUTH['write_controls']:
            with self.subTest(case['id']):
                calls, observed = [], {'short': False, 'zero': False, 'error': False}

                def plan_write(fd, buffer, plan=case['write_plan']):
                    calls.append(len(buffer))
                    step = plan[min(len(calls) - 1, len(plan) - 1)]
                    if 'safety_sentinel_if_called' in step:
                        raise AssertionError(step['safety_sentinel_if_called'])
                    if step.get('return_zero_without_storing'):
                        observed['zero'] = True
                        return 0
                    if 'raises' in step:
                        observed['error'] = True
                        raise OSError(step['message'])
                    if step.get('actually_store_at_most') is not None and len(calls) == 1:
                        observed['short'] = len(buffer) > 1
                        return os.write(fd, bytes(buffer[:step['actually_store_at_most']]))
                    return os.write(fd, bytes(buffer))
                result, _, stored = self.run_transfer(case, plan_write)
                self.assertEqual(stored.hex(), case['expected_stored_hex'])
                if 'expected' in case:
                    self.assertEqual(result, case['expected'])
                    self.assertTrue(observed['short'], 'positive short write path exercised')
                else:
                    self.assertIsInstance(result, OSError)
                    self.assertNotIsInstance(result, AssertionError)
                    if case['expected_effects'].get('write_calls'):
                        self.assertEqual(len(calls), case['expected_effects']['write_calls'])
                    if case['expected_effects'].get('zero_injection_observed'):
                        self.assertTrue(observed['zero'])
                    if case['expected_effects'].get('error_injection_observed'):
                        self.assertTrue(observed['error'])

    def test_signature_cases(self):
        for case in AUTH['signature_cases']:
            with self.subTest(case['id']):
                got = omd.inspect_signature(case['kind'], bytes.fromhex(case['prefix_hex']))
                self.assertEqual(got, case['expected'])
                self.assertEqual(list(got), ['state', 'prefix_hex'])

    def test_argument_refusals(self):
        response = AuthoredResponse({'initial_length': 0, 'steps': []}, Clock())
        for kwargs in ({'body_cap': True, 'aggregate_left': 1, 'deadline': 1}, {'body_cap': -1, 'aggregate_left': 1, 'deadline': 1},
                       {'body_cap': 1, 'aggregate_left': 1.0, 'deadline': 1}, {'body_cap': 1, 'aggregate_left': 1, 'deadline': float('nan')},
                       {'body_cap': 1, 'aggregate_left': 1, 'deadline': True}, {'body_cap': 1, 'aggregate_left': 1, 'deadline': float('inf')}):
            with self.subTest(kwargs):
                self.assertRaises(ValueError, omd.transfer, response, 0, **kwargs)
        self.assertRaises(ValueError, omd.transfer, object(), 0, body_cap=1, aggregate_left=1, deadline=1)
        self.assertRaises(ValueError, omd.transfer, response, True, body_cap=1, aggregate_left=1, deadline=1)
        self.assertRaises(ValueError, omd.inspect_signature, 'gif', b'GIF8')
        self.assertRaises(ValueError, omd.inspect_signature, 'bmp', 'BM')
        bad = AuthoredResponse({'initial_length': True, 'steps': []}, Clock())
        store = TinyFile('badlen')
        try:
            self.assertRaises(ValueError, omd.transfer, bad, store.fd, body_cap=4, aggregate_left=4, deadline=1, clock=Clock())
        finally:
            store.close()


class WriteAll(unittest.TestCase):
    def test_progress_validation_and_eintr(self):
        store = TinyFile('writeall')
        try:
            for value in (0, True, 99, '1', None, -1):
                with self.subTest(value):
                    self.assertRaises(OSError, omd.write_all, store.fd, b'abc', lambda fd, b, v=value: v)
            state = {'n': 0}

            def eintr_then_one(fd, buffer):
                state['n'] += 1
                if state['n'] == 1:
                    raise InterruptedError(errno.EINTR, 'interrupted')
                return os.write(fd, bytes(buffer[:1]))
            self.assertEqual(omd.write_all(store.fd, bytearray(b'xyz'), eintr_then_one), 3)
            self.assertEqual(store.stored(), b'xyz')
            self.assertEqual(state['n'], 4)
            omd.write_all(store.fd, memoryview(b'!'))
            self.assertEqual(store.stored(), b'xyz!')
        finally:
            store.close()


# ------------------------------------------------------------- lifecycle fakes

_META = None


def real_meta():
    global _META
    if _META is None:
        _META = omd.load_metadata(INPUT_ROOT, str(PROFILE))
    return _META


class FakeSock:
    def __init__(self):
        self.timeouts = []

    def settimeout(self, value):
        assert 0 < value <= 5
        self.timeouts.append(value)


class FakeHTTPResponse:
    def __init__(self, status, headers, body, framed=True, fault=None, clock=None, advance=None):
        self.status, self._headers, self._body = status, headers, body
        self.length = len(body) if framed else None
        self.fault, self.clock, self.advance, self.closed, self._pos = fault, clock, advance, False, 0

    def getheader(self, name, default=None):
        return self._headers.get(name, default)

    def read1(self, n):
        if self.fault == 'read':
            raise ConnectionResetError('authored reset')
        end = len(self._body) // 2 if self.fault == 'truncate' else len(self._body)
        out = self._body[self._pos:min(self._pos + n, end)]
        self._pos += len(out)
        if self.length is not None:
            self.length -= len(out)
        if self.advance is not None and self._pos >= len(self._body):
            self.clock.value = self.advance
        return out

    def close(self):
        self.closed = True
        if self.fault == 'close':
            raise OSError('authored close fault')


class FakeConnection:
    def __init__(self, server, timeout):
        self.server, self.timeout, self.sock, self.closed, self.response = server, timeout, FakeSock(), False, None

    def request(self, method, url, headers):
        assert method == 'GET' and headers == {'Accept-Encoding': 'identity'}
        self.server.requests.append(url)
        self.url = url

    def getresponse(self):
        self.response = self.server.respond(self.url)
        return self.response

    def close(self):
        self.closed = True


class FakeProc:
    def __init__(self, ops):
        self.ops, self.pid, self.returncode, self.terminated, self.killed = ops, 424242, None, False, False

    def poll(self):
        return self.returncode

    def terminate(self):
        self.terminated = True
        if self.ops.exit_mode != 'hang':
            self.returncode = self.ops.exit_code

    def wait(self, timeout):
        if self.returncode is None:
            raise subprocess.TimeoutExpired('fake', timeout)
        return self.returncode

    def kill(self):
        self.killed = True
        self.returncode = -9


class FakeOps:
    """Fake process/network effects; the server map is keyed by wire target."""

    def __init__(self, output, routes=None):
        self.output, self.routes, self.requests = output, routes or {}, []
        self.clock, self.sleep_calls, self.connections, self.proc = Clock(100.0), 0, [], None
        self.exit_mode, self.exit_code, self.residue, self.listener_after = 'normal', 0, [], False
        self.lose_listener_at, self.group_error, self.free = None, False, 1 << 50
        self.popen_calls, self.on_404_log, self.after_request = [], True, None
        self.log_lines = []

    def sleep(self, seconds):
        self.sleep_calls += 1

    def free_bytes(self, path):
        return self.free

    def fresh_port(self):
        return 54321

    def popen(self, argv, cwd, env):
        self.popen_calls.append((argv, cwd, env))
        self.proc = FakeProc(self)
        return self.proc

    def getpgid(self, pid):
        return pid

    def owned_listener(self, pid, port):
        if self.lose_listener_at is not None and len(self.requests) >= self.lose_listener_at:
            return False
        return self.proc is not None and self.proc.returncode is None and port == 54321

    def port_listeners(self, port):
        if self.proc is None:
            return False
        return self.listener_after or self.proc.returncode is None

    def group_members(self, pgid):
        if self.group_error:
            raise subprocess.CalledProcessError(1, 'ps')
        return list(self.residue) + ([pgid] if self.proc.returncode is None else [])

    def connect(self, port, timeout):
        assert 0 < timeout <= 5
        route = self.routes.get(('connect', len(self.connections)))
        if route == 'fail':
            self.connections.append(None)
            raise OSError('authored connect fault')
        con = FakeConnection(self, timeout)
        self.connections.append(con)
        return con

    def respond(self, url):
        if url == '/api/health':
            spec = self.routes.get(url, (200, {'Content-Type': 'application/json'}, HEALTH_BODY))
        else:
            spec = self.routes.get(url, (404, {'Content-Type': 'text/plain'}, b'Not Found'))
        status, headers, body = spec[:3]
        options = spec[3] if len(spec) > 3 else {}
        if options.get('raise'):
            raise options['raise']
        if status == 404 and self.on_404_log:
            self.append_log(url)
        if self.after_request:
            self.after_request(url)
        return FakeHTTPResponse(status, headers, body, framed=options.get('framed', True), fault=options.get('fault'),
                                clock=self.clock, advance=options.get('advance'))

    def append_log(self, url):
        from urllib.parse import unquote
        requested = unquote(url[1:])
        line = json.dumps({'timestamp': '2026-10-20T01:02:03.456Z', 'requestedPath': requested,
                           'grfPath': requested.replace('/', '\\'), 'mappedPath': None}, ensure_ascii=False)
        logs = os.path.join(self.output, 'logs')
        if not os.path.isdir(logs):
            os.mkdir(logs, 0o700)
            os.chmod(logs, 0o700)
        fd = os.open(os.path.join(logs, 'missing-files.log'), os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600)
        os.write(fd, line.encode('utf-8') + b'\n')
        os.close(fd)


class Lifecycle(unittest.TestCase):
    """Real tiny native-stand-in files and fake process/network objects."""

    @classmethod
    def setUpClass(cls):
        cls.meta = real_meta()
        cls.driver = omd.own_sha()

    def setUp(self):
        self.root = private_dir(PRIVATE / ('life-%d-%s' % (os.getpid(), self._testMethodName)))
        for child in self.root.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
        self.native_dir = private_dir(self.root / 'native')
        self.natives = []
        for name in omd.NATIVE_NAMES:
            data = ('tiny stand-in ' + name).encode()
            path = self.native_dir / name
            path.write_bytes(data)
            os.chmod(path, 0o600)
            self.natives.append({'name': name, 'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        self.container = str(private_dir(self.root / 'container'))
        self.output = os.path.join(self.container, 'out')
        self.fds_before = open_fds()
        self.reload = mock.patch.object(omd, 'load_metadata', return_value=self.meta)
        self.reload.start()

    def tearDown(self):
        self.reload.stop()
        # Leak inspection happens before fixture cleanup.
        self.assertEqual(open_fds() - self.fds_before, set(), 'descriptor leak')
        shutil.rmtree(self.root)

    def plans(self, n=3):
        return self.meta['plans'][:n]

    def observer(self, ops, n=3, policy=None, write_fn=None, plans=None):
        meta = dict(self.meta, plans=plans if plans is not None else self.plans(n))
        return omd.Observer(meta, self.output, self.driver, ops=ops, natives=self.natives, policy=policy,
                            container=self.container, write_fn=write_fn)

    def report(self):
        return json.loads(Path(self.output, 'report.json').read_bytes())

    def model_route(self, plan, body=b'GRSM\x01\x05tiny', status=200, **options):
        return {plan['wire']: (status, {'Content-Type': 'application/octet-stream', 'Content-Length': str(len(body))}, body, options)}

    def test_normal_run_qualifies_with_gaps(self):
        plans = self.plans(4)
        ops = FakeOps(self.output)
        ops.routes.update(self.model_route(plans[0]))
        ops.routes.update(self.model_route(plans[1], body=b'BAD!\x01\x02'))
        ops.routes.update(self.model_route(plans[3], body=b'<html>', framed=False))
        ops.routes[plans[3]['wire']][1]['Content-Type'] = 'text/html'
        obs = self.observer(ops, plans=plans)
        self.assertEqual(obs.run(), 0)
        rep = self.report()
        self.assertTrue(rep['acquisition_and_cleanup_valid'])
        self.assertEqual([r['stop_reason'] for r in rep['targets']], ['complete', 'complete', 'http_404', 'html_200'])
        self.assertEqual(rep['targets'][0]['signature'], {'kind': 'model', 'state': 'match', 'prefix_hex': '4752534d0105'})
        self.assertEqual(rep['targets'][1]['signature']['state'], 'mismatch')
        self.assertEqual(rep['targets'][2]['signature']['state'], 'not_checked')
        self.assertEqual([r['request_index'] for r in rep['targets']], [1, 2, 3, 4])
        self.assertEqual(ops.requests[0], '/api/health')
        self.assertEqual(ops.requests[1:], [p['wire'] for p in plans])
        self.assertEqual(rep['totals']['wire_bytes'], len(HEALTH_BODY) + 10 + 6 + 9 + 6)
        self.assertEqual(rep['totals']['health_attempts'], 1)
        self.assertEqual(rep['missing_log']['entries'], 1)
        self.assertTrue(rep['tree']['valid'])
        self.assertEqual(Path(self.output, 'catalog-input.json').read_bytes(), self.meta['catalog_bytes'])
        self.assertEqual(rep['coverage_counts']['complete_200_matching_prefix'], 1)
        self.assertEqual(rep['coverage_counts']['http_404'], 1)
        env = ops.popen_calls[0][2]
        self.assertEqual(env['CLIENT_DATAINI'], os.path.join(self.output, 'resources/DATA.INI'))
        self.assertEqual(set(env), {'PATH', 'SERVER_ROOT', 'PORT', 'HOST', 'NODE_ENV', 'CLIENT_PUBLIC_URL', 'CLIENT_RESPATH',
                                    'CLIENT_DATAINI', 'ENABLE_STATIC_SERVE', 'ENABLE_WSPROXY', 'ENABLE_COMPRESSION',
                                    'CACHE_WARM_UP', 'CLIENT_AUTOEXTRACT', 'CLIENT_ENABLESEARCH', 'GRF_FILENAME_ENCODING',
                                    'CACHE_MAX_MEMORY_MB', 'CACHE_MAX_FILES'})
        self.assertEqual((env['PATH'], env['HOST'], env['PORT'], env['CACHE_MAX_MEMORY_MB']), ('/usr/bin:/bin:/usr/sbin:/sbin', '127.0.0.1', '54321', '64'))
        ini = Path(self.output, 'resources/DATA.INI').read_text()
        self.assertEqual(ini, '[Data]\n0=%s\n1=%s\n2=%s\n' % tuple(s['path'] for s in self.natives[1:]))
        self.assertTrue(all(c.closed and (c.response is None or c.response.closed) for c in ops.connections))
        self.assertTrue(ops.proc.terminated and not ops.proc.killed)
        for path in Path(self.output).rglob('*'):
            self.assertEqual(stat.S_IMODE(path.lstat().st_mode), 0o700 if path.is_dir() else 0o600)

    def test_prefill_before_native_access(self):
        ops = FakeOps(self.output)
        seen = {}
        obs = self.observer(ops)
        original = obs.hash_natives

        def spy():
            seen['report'] = self.report()
            return original()
        obs.hash_natives = spy
        obs.run()
        self.assertEqual(len(seen['report']['targets']), 3)
        self.assertTrue(all(not r['attempted'] for r in seen['report']['targets']))

    def test_transport_gaps_continue_and_connection_fault(self):
        plans = self.plans(4)
        ops = FakeOps(self.output)
        ops.routes[('connect', 1)] = 'fail'
        ops.routes.update(self.model_route(plans[1], fault='read'))
        ops.routes.update(self.model_route(plans[2], fault='truncate'))
        ops.routes.update(self.model_route(plans[3]))
        obs = self.observer(ops, plans=plans)
        self.assertEqual(obs.run(), 0)
        rep = self.report()
        self.assertEqual([r['stop_reason'] for r in rep['targets']], ['connection_setup_error', 'transport_error', 'transport_error', 'complete'])
        self.assertTrue(rep['targets'][0]['attempted'])
        self.assertEqual(rep['targets'][0]['wire_bytes'], 0)
        self.assertIsNone(rep['targets'][0]['http_status'])
        self.assertEqual(rep['targets'][2]['wire_bytes'], 5)
        self.assertEqual(rep['targets'][2]['stored']['bytes'], 5)
        self.assertFalse(rep['targets'][2]['stored']['complete'])
        self.assertTrue(ops.connections[-1].closed)

    def test_storage_fault_is_fatal_with_untouched_suffix(self):
        plans = self.plans(4)
        ops = FakeOps(self.output)
        ops.routes.update(self.model_route(plans[1]))
        state = {'n': 0}

        def faulty(fd, buffer):
            state['n'] += 1
            if state['n'] == 3:  # health, 404 body, then this asset
                return os.write(fd, bytes(buffer[:2])) * 0 or 0
            return os.write(fd, bytes(buffer))
        obs = self.observer(ops, plans=plans, write_fn=faulty)
        self.assertEqual(obs.run(), 1)
        rep = self.report()
        self.assertEqual(rep['halt_reason'], 'storage_failure')
        target = rep['targets'][1]
        self.assertEqual(target['stop_reason'], 'storage_error')
        self.assertEqual(target['wire_bytes'], 10)  # Received bytes retained after storage failure.
        self.assertFalse(target['stored']['complete'])
        self.assertEqual(target['stored']['error'], 'storage_error')
        for suffix in rep['targets'][2:]:
            self.assertEqual((suffix['attempted'], suffix['stop_reason'], suffix['request_index']), (False, 'storage_failure', None))
            self.assertEqual(suffix['signature']['state'], 'not_checked')
        self.assertTrue(ops.proc.terminated)
        self.assertFalse(rep['acquisition_and_cleanup_valid'])

    def test_positive_short_production_writes(self):
        ops = FakeOps(self.output)
        ops.routes.update(self.model_route(self.plans(1)[0]))
        calls = []

        def one_byte(fd, buffer):
            calls.append(len(buffer))
            return os.write(fd, bytes(buffer[:1]))
        obs = self.observer(ops, n=1, write_fn=one_byte)
        self.assertEqual(obs.run(), 0)
        rep = self.report()
        self.assertTrue(rep['targets'][0]['stored']['complete'])
        self.assertTrue(any(n > 1 for n in calls))

    def test_health_inclusive_aggregate_cap(self):
        plans = self.plans(3)
        policy = dict(omd.POLICY, aggregate_bytes_including_health=len(HEALTH_BODY) + 4)
        for framed in (True, False):
            with self.subTest(framed=framed):
                if os.path.exists(self.output):
                    shutil.rmtree(self.output)
                ops = FakeOps(self.output)
                ops.routes.update(self.model_route(plans[0], framed=framed))
                self.assertEqual(self.observer(ops, plans=plans, policy=policy).run(), 1)
                rep = self.report()
                self.assertEqual(rep['halt_reason'], 'aggregate_cap')
                self.assertEqual(rep['targets'][0]['stop_reason'], 'aggregate_cap')
                self.assertEqual(rep['targets'][0]['wire_bytes'], 4)
                self.assertEqual(rep['totals']['wire_bytes'], len(HEALTH_BODY) + 4)
                self.assertEqual([(r['attempted'], r['stop_reason']) for r in rep['targets'][1:]], [(False, 'aggregate_cap')] * 2)
                self.assertEqual(len(ops.requests), 2)

    def test_late_final_read_stays_complete_but_halts(self):
        plans = self.plans(2)
        ops = FakeOps(self.output)
        ops.routes.update(self.model_route(plans[1], advance=100.0 + 1200))
        obs = self.observer(ops, plans=plans)
        self.assertEqual(obs.run(), 1)
        rep = self.report()
        self.assertEqual(rep['targets'][1]['stop_reason'], 'complete')
        self.assertTrue(rep['targets'][1]['wire_complete'])
        self.assertEqual(rep['halt_reason'], 'acquisition_deadline')
        self.assertTrue(rep['all_targets_attempted'])
        self.assertFalse(rep['acquisition_and_cleanup_valid'])

    def test_deadline_before_suffix(self):
        plans = self.plans(3)
        ops = FakeOps(self.output)
        ops.routes.update(self.model_route(plans[0], advance=100.0 + 1200))
        obs = self.observer(ops, plans=plans)
        self.assertEqual(obs.run(), 1)
        rep = self.report()
        self.assertEqual([r['attempted'] for r in rep['targets']], [True, False, False])
        self.assertEqual(rep['targets'][2]['stop_reason'], 'acquisition_deadline')
        self.assertEqual(len(ops.requests), 2)

    def test_health_failure_halts_all(self):
        ops = FakeOps(self.output)
        ops.routes['/api/health'] = (200, {}, b'{"status":"bad","service":"robrowser-remoteclient"}')
        self.assertEqual(self.observer(ops).run(), 1)
        rep = self.report()
        self.assertEqual(rep['halt_reason'], 'health_failure')
        self.assertTrue(all(r['stop_reason'] == 'health_failure' and not r['attempted'] for r in rep['targets']))
        self.assertEqual(len(ops.requests), 1)

    def test_encoded_and_oversized_header_gaps(self):
        plans = self.plans(3)
        ops = FakeOps(self.output)
        ops.routes[plans[0]['wire']] = (200, {'Content-Encoding': 'gzip'}, b'GRSM\x01\x05')
        ops.routes[plans[1]['wire']] = (200, {'Content-Type': 'x' * 2049}, b'GRSM\x01\x05')
        ops.routes[plans[2]['wire']] = (302, {'Location': '/elsewhere'}, b'')
        self.assertEqual(self.observer(ops, plans=plans).run(), 0)
        rep = self.report()
        self.assertEqual([r['stop_reason'] for r in rep['targets']], ['unsupported_encoding', 'malformed_header', 'redirect'])
        self.assertIsNone(rep['targets'][1]['headers']['content_type'])
        self.assertEqual(rep['targets'][2]['headers']['location'], '/elsewhere')
        self.assertEqual(rep['coverage_counts']['redirect'], 1)

    def test_reader_loss_is_fatal(self):
        plans = self.plans(3)
        ops = FakeOps(self.output)
        ops.routes.update(self.model_route(plans[0], fault='read'))

        def die(url):
            if url == plans[0]['wire']:
                ops.proc.returncode = 1
        ops.after_request = die
        self.assertEqual(self.observer(ops, plans=plans).run(), 1)
        rep = self.report()
        self.assertEqual(rep['halt_reason'], 'reader_lost')
        self.assertFalse(rep['targets'][1]['attempted'])
        self.assertFalse(rep['cleanup']['clean'])

    def test_missing_log_and_tree_faults(self):
        cases = {
            'absent_log': lambda ops: setattr(ops, 'on_404_log', False),
            'field_order': None, 'extra_file': None, 'symlink': None, 'extraction': None, 'mode': None}
        for name in cases:
            with self.subTest(name):
                if os.path.exists(self.output):
                    shutil.rmtree(self.output)
                ops = FakeOps(self.output)
                if name == 'absent_log':
                    ops.on_404_log = False
                plans = self.plans(1)

                def tamper(url, name=name):
                    if url == '/api/health':
                        return
                    out = Path(self.output)
                    if name == 'field_order':
                        (out / 'logs/missing-files.log').write_text(
                            json.dumps({'requestedPath': 'x', 'timestamp': '2026-10-20T01:02:03.456Z', 'grfPath': 'x', 'mappedPath': None}) + '\n')
                    elif name == 'extra_file':
                        (out / 'server.log').write_bytes(b'')
                        os.chmod(out / 'server.log', 0o600)
                    elif name == 'symlink':
                        os.symlink('/nonexistent', out / 'resources/link')
                    elif name == 'extraction':
                        os.mkdir(out / 'data', 0o700)
                    elif name == 'mode':
                        os.chmod(out / 'catalog-input.json', 0o644)
                ops.after_request = lambda url: None
                original = ops.respond

                def respond(url, original=original, tamper=tamper):
                    response = original(url)
                    tamper(url)
                    return response
                ops.respond = respond
                self.assertEqual(self.observer(ops, plans=plans).run(), 1)
                rep = self.report()
                if name in ('absent_log', 'field_order'):
                    self.assertFalse(rep['missing_log']['valid'])
                else:
                    self.assertFalse(rep['tree']['valid'])
                self.assertIsNone(rep['halt_reason'])
                self.assertFalse(rep['acquisition_and_cleanup_valid'])

    def test_native_and_source_drift(self):
        ops = FakeOps(self.output)

        def drift(url):
            if url == '/api/health':
                path = self.natives[2]['path']
                os.utime(path, ns=(1, 1))
        ops.after_request = drift
        self.assertEqual(self.observer(ops).run(), 1)
        rep = self.report()
        self.assertFalse(rep['postchecks_valid'])
        shutil.rmtree(self.output)
        drifted = dict(self.meta, sources=[dict(self.meta['sources'][0], sha256='0' * 64)] + self.meta['sources'][1:])
        with mock.patch.object(omd, 'load_metadata', return_value=drifted):
            ops = FakeOps(self.output)
            for spec in self.natives:
                st = os.lstat(spec['path'])
                spec['identity'] = st
            self.assertEqual(self.observer(ops).run(), 1)
        rep = self.report()
        self.assertFalse(rep['postchecks_valid'])
        self.assertNotEqual(rep['sources_after'], rep['sources_before'])

    def test_native_pin_mismatch_before_launch(self):
        self.natives[1] = dict(self.natives[1], sha256='0' * 64)
        ops = FakeOps(self.output)
        self.assertEqual(self.observer(ops).run(), 1)
        self.assertEqual(ops.popen_calls, [])
        self.assertEqual(self.report()['halt_reason'], 'admission_failure')

    def test_cleanup_variants(self):
        variants = {
            'forced': lambda ops: setattr(ops, 'exit_mode', 'hang'),
            'nonzero': lambda ops: setattr(ops, 'exit_code', 3),
            'residue': lambda ops: ops.residue.append(424243),
            'listener': lambda ops: setattr(ops, 'listener_after', True),
            'unknown': lambda ops: setattr(ops, 'group_error', True)}
        for name, setup in variants.items():
            with self.subTest(name):
                if os.path.exists(self.output):
                    shutil.rmtree(self.output)
                ops = FakeOps(self.output)
                setup(ops)
                self.assertEqual(self.observer(ops, n=1).run(), 1)
                rep = self.report()
                self.assertFalse(rep['cleanup']['clean'])
                self.assertFalse(rep['acquisition_and_cleanup_valid'])
                if name == 'forced':
                    self.assertTrue(rep['cleanup']['forced_kill'] and ops.proc.killed)
                if name == 'unknown':
                    self.assertEqual(rep['cleanup']['error'], 'CalledProcessError')

    def test_listener_missing_before_shutdown(self):
        ops = FakeOps(self.output)
        ops.lose_listener_at = 2
        self.assertEqual(self.observer(ops, n=1).run(), 1)
        self.assertEqual(self.report()['halt_reason'], 'reader_lost')

    def test_startup_timeout(self):
        ops = FakeOps(self.output)
        ops.lose_listener_at = 0
        original = ops.sleep

        def tick(seconds):
            original(seconds)
            ops.clock.value += 1
        ops.sleep = tick
        self.assertEqual(self.observer(ops, n=1).run(), 1)
        self.assertEqual(self.report()['halt_reason'], 'startup_timeout')
        self.assertEqual(ops.requests, [])
        self.assertLessEqual(ops.sleep_calls, 26)

    def test_failed_final_publication_exits_nonzero(self):
        ops = FakeOps(self.output)
        obs = self.observer(ops, n=1)
        real_replace, calls = os.replace, []

        def flaky(src, dst):
            calls.append(dst)
            if len(calls) >= 3:  # prefill and launch checkpoints succeed; final publication fails
                raise OSError('authored publication fault')
            return real_replace(src, dst)
        with mock.patch.object(os, 'replace', flaky):
            self.assertEqual(obs.run(), 1)
        self.assertEqual(obs.halt, 'publication_failure')
        self.assertFalse(os.path.exists(os.path.join(self.output, '.report-next')))

    def test_output_admission_refusals(self):
        ops = FakeOps(self.output)
        os.mkdir(self.output, 0o700)
        self.assertEqual(self.observer(ops).run(), 2)
        os.rmdir(self.output)
        ops.free = 1 << 30
        self.assertEqual(self.observer(ops).run(), 2)
        self.assertFalse(os.path.exists(self.output))
        outside = omd.Observer(dict(self.meta, plans=self.plans(1)), str(self.root / 'elsewhere'), self.driver, ops=FakeOps(''),
                               natives=self.natives, container=self.container)
        self.assertEqual(outside.run(), 2)
        self.assertEqual(ops.popen_calls, [])


class Cli(unittest.TestCase):
    def run_main(self, argv):
        out = io.StringIO()
        with redirect_stdout(out):
            code = omd.main(argv)
        text = out.getvalue()
        self.assertLessEqual(len(text.encode()), 4096)
        self.assertEqual(text.count('\n'), 1)
        return code, json.loads(text), text

    def test_full_preflight_touches_no_native_process_or_http(self):
        natives = [os.path.normpath(os.path.join(INPUT_ROOT, n['path'])) for n in json.loads(PROFILE.read_bytes())['native'] if n['base'] == 'input_root']
        natives.append(os.path.normpath(os.path.expanduser('~/Library/Application Support/Ragnarok Offline/runtime/bin/robrowser-remoteclient')))
        real_open, real_lstat, real_stat = os.open, os.lstat, os.stat

        def guard(fn):
            def inner(path, *a, **k):
                if os.path.normpath(os.fspath(path)) in natives:
                    raise AssertionError('native input reached')
                return fn(path, *a, **k)
            return inner
        forbid = mock.Mock(side_effect=AssertionError('forbidden effect'))
        with mock.patch.object(os, 'open', guard(real_open)), mock.patch.object(os, 'lstat', guard(real_lstat)), \
                mock.patch.object(os, 'stat', guard(real_stat)), mock.patch.object(subprocess, 'Popen', forbid), \
                mock.patch.object(subprocess, 'run', forbid), mock.patch.object(http.client, 'HTTPConnection', forbid), \
                mock.patch.object(socket, 'socket', forbid):
            code, payload, text = self.run_main(['--preflight', '--input-root', INPUT_ROOT, '--profile', str(PROFILE)])
        self.assertEqual(code, 0, text)
        self.assertEqual(payload['status'], 'preflight_ok')
        self.assertIsNone(payload['native_qualification'])
        self.assertEqual(payload['counts']['targets'], 11134)
        self.assertEqual(payload['counts']['referrers'], 63557)
        self.assertEqual(payload['counts']['roots'], 1296)
        self.assertEqual(payload['counts']['gap_roots'], 82)
        self.assertEqual(payload['counts']['kinds'], {'model': 8194, 'bmp': 2938, 'jpeg': 2})
        self.assertNotIn(INPUT_ROOT, text)
        forbid.assert_not_called()

    def test_refusals_exit_two_without_echo(self):
        private_dir(PRIVATE)
        out = str(PRIVATE / 'never-created')
        cases = [[], ['--preflight', '--execute', '--input-root', INPUT_ROOT, '--profile', str(PROFILE)],
                 ['--preflight', '--input-root', INPUT_ROOT + '/secret-missing', '--profile', str(PROFILE)],
                 ['--preflight', '--input-root', INPUT_ROOT, '--profile', str(AUTHORED)],
                 ['--execute', '--input-root', INPUT_ROOT, '--profile', str(PROFILE), '--output', out,
                  '--root-reviewed-sha256', '0' * 64],
                 ['--preflight', '--input-root', INPUT_ROOT, '--profile', str(PROFILE), '--output', out]]
        with mock.patch.object(omd, 'load_metadata', side_effect=AssertionError('metadata reached')) as guard:
            code, payload, text = self.run_main(cases[4])
            guard.assert_not_called()  # Driver SHA check precedes metadata/output/native access.
        self.assertEqual(code, 2)
        for argv in cases:
            with self.subTest(argv[:1]):
                code, payload, text = self.run_main(argv)
                self.assertEqual(code, 2)
                self.assertEqual(payload['status'], 'refused')
                self.assertNotIn('secret-missing', text)
                self.assertNotIn(INPUT_ROOT, text)
        self.assertFalse(os.path.exists(out))

    def test_catalog_validation_refuses_corruption(self):
        meta = real_meta()
        profile = meta['profile']
        prior = [p for p in profile['source_pins'] if p['path'] == omd.PRIOR_PROFILE_PATH][0]
        catalog = json.loads(meta['catalog_bytes'])
        self.assertEqual(len(omd.validate_catalog(catalog, profile, prior)[0]), 11134)
        mutations = {
            'referrer': lambda c: c['targets'][5]['referrers'].pop(),
            'http': lambda c: c['targets'][7].__setitem__('http_path', c['targets'][7]['http_path'] + 'x'),
            'gap': lambda c: c['remaining_gap_root_ordinals'].pop(),
            'order': lambda c: c['targets'].reverse(),
            'filemanager': lambda c: c['jobs'][0]['loader_entries'][0].__setitem__('filemanager_name', 'data\\model\\other.rsm'),
            'binding': lambda c: c.__setitem__('profile_sha256', '0' * 64)}
        for name, mutate in mutations.items():
            with self.subTest(name):
                broken = json.loads(meta['catalog_bytes'])
                mutate(broken)
                self.assertRaises(omd.Refusal, omd.validate_catalog, broken, profile, prior)

    def test_strict_json(self):
        self.assertRaises(omd.Refusal, omd.strict_json, b'{"a":1,"a":2}')
        self.assertRaises(omd.Refusal, omd.strict_json, b'{"a":NaN}')
        self.assertEqual(omd.http_from_name('data\\model\\¾.rsm'), 'data/model/%C2%BE.rsm')


# Coordinator regressions for independently reproduced failure paths.
class Root005Regressions(unittest.TestCase):
    setUp = Lifecycle.setUp
    tearDown = Lifecycle.tearDown
    plans = Lifecycle.plans
    observer = Lifecycle.observer
    report = Lifecycle.report
    model_route = Lifecycle.model_route

    @classmethod
    def setUpClass(cls):
        cls.meta = real_meta()
        cls.driver = omd.own_sha()

    @staticmethod
    def _owned_fd_state(fd, expected):
        try:
            st = os.fstat(fd)
        except OSError as exc:
            if exc.errno == errno.EBADF:
                return 'closed'
            raise
        return 'owned_open' if (st.st_dev, st.st_ino) == expected else 'foreign'

    def test_root_initial_framing_invalid_before_read_or_write(self):
        for index, value in enumerate((True, -1, 1.0, '1', [], {})):
            with self.subTest(index=index):
                response = FakeHTTPResponse(200, {}, b'abc')
                response.length = value
                response.read1 = mock.Mock(side_effect=AssertionError('unexpected read'))
                writer = mock.Mock(side_effect=AssertionError('unexpected write'))
                store = TinyFile('root-invalid-framing-%d' % index)
                try:
                    with self.assertRaises(ValueError):
                        omd.transfer(response, store.fd, body_cap=4, aggregate_left=4,
                                     deadline=1, clock=Clock(), write_fn=writer)
                    response.read1.assert_not_called()
                    writer.assert_not_called()
                    self.assertEqual(store.stored(), b'')
                finally:
                    store.close()

    def test_root_complete_wire_physical_partial_write_is_counted(self):
        plans = self.plans(2)
        body = b'GRSM\x01\x05tiny'
        ops = FakeOps(self.output, self.model_route(plans[0], body=body))
        fired = []

        def writer(fd, buffer):
            if ops.requests and ops.requests[-1] == plans[0]['wire'] and not fired:
                # The fixture proves the whole framed response was delivered
                # before the storage fault, rather than assuming that premise.
                response = ops.connections[-1].response
                self.assertEqual((response._pos, response.length), (len(body), 0))
                self.assertEqual(os.write(fd, bytes(buffer[:1])), 1)
                fired.append(True)
                raise OSError(errno.EIO, 'authored partial physical write')
            return os.write(fd, buffer)

        obs = self.observer(ops, plans=plans, write_fn=writer)
        self.assertEqual(obs.run(), 1)
        rep, row = self.report(), obs.report['targets'][0]
        self.assertEqual(fired, [True])
        self.assertEqual(row['wire_bytes'], len(body))
        self.assertTrue(row['wire_complete'])
        self.assertEqual(row['stored']['bytes'], 1)
        self.assertEqual(row['stored']['sha256'], hashlib.sha256(body[:1]).hexdigest())
        self.assertFalse(row['stored']['complete'])
        self.assertIsNotNone(row['stored']['error'])
        self.assertEqual(rep['totals']['wire_bytes'], len(HEALTH_BODY) + len(body))
        self.assertEqual(rep['totals']['stored_bytes'], len(HEALTH_BODY) + 1)
        self.assertFalse(rep['targets'][1]['attempted'])
        self.assertFalse(rep['acquisition_and_cleanup_valid'])

    def test_root_before_release_http_close_errors_are_not_qualification(self):
        observations = []
        for kind in ('response', 'connection'):
            with self.subTest(resource=kind):
                if os.path.exists(self.output):
                    shutil.rmtree(self.output)
                plan = self.plans(1)[0]
                ops = FakeOps(self.output, self.model_route(plan))
                resource_path = self.root / ('http-close-' + kind)
                fd = os.open(resource_path, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
                st = os.fstat(fd)
                identity = (st.st_dev, st.st_ino)
                real_close, real_connect = os.close, ops.connect
                state = {'faults': 0, 'selected_calls': 0, 'other_calls': 0}

                def connect(port, timeout):
                    con = real_connect(port, timeout)
                    get_response, con_close = con.getresponse, con.close

                    def get():
                        response = get_response()
                        if con.url != plan['wire']:
                            return response
                        response_close = response.close

                        def selected_close():
                            state['selected_calls'] += 1
                            if state['selected_calls'] == 1:
                                state['faults'] += 1
                                raise OSError(errno.EIO, 'authored before-release close')
                            if self._owned_fd_state(fd, identity) == 'owned_open':
                                real_close(fd)
                            (response_close if kind == 'response' else con_close)()

                        def other_close():
                            state['other_calls'] += 1
                            (con_close if kind == 'response' else response_close)()

                        if kind == 'response':
                            response.close, con.close = selected_close, other_close
                        else:
                            response.close, con.close = other_close, selected_close
                        return response
                    con.getresponse = get
                    return con

                ops.connect = connect
                obs = self.observer(ops, n=1)
                try:
                    code = obs.run()
                    # Record production behavior before the fixture releases
                    # an uncertain resource. Later cleanup cannot rewrite it.
                    state['fd_before_fixture_cleanup'] = self._owned_fd_state(fd, identity)
                    state['child_terminated'] = ops.proc.terminated
                    state['child_exit'] = ops.proc.poll()
                    observations.append(dict(resource=kind, **state))
                finally:
                    current = self._owned_fd_state(fd, identity)
                    if current == 'owned_open':
                        real_close(fd)
                    # A foreign descriptor is never ours to close.
                    if current != 'foreign':
                        resource_path.unlink()
                self.assertNotEqual(state['fd_before_fixture_cleanup'], 'foreign', state)
                self.assertEqual(state['faults'], 1, state)
                self.assertGreaterEqual(state['other_calls'], 1, state)
                self.assertEqual(code, 1, state)
                self.assertFalse(obs.report['acquisition_and_cleanup_valid'], state)
                self.assertTrue(obs.report['errors'] or obs.report['halt_reason'], state)
                self.assertTrue(state['child_terminated'], state)
                self.assertEqual(state['child_exit'], 0, state)
                # Transfer/storage facts survive a lifecycle-close fault.
                self.assertTrue(obs.report['targets'][0]['wire_complete'])
                self.assertTrue(obs.report['targets'][0]['stored']['complete'])
        self.root_close_observations = observations

    def test_root_listener_observation_exception_still_reaps_owned_fake_child(self):
        ops = FakeOps(self.output)
        obs = self.observer(ops, n=1)
        original_shutdown, original_listener = obs.shutdown, ops.owned_listener
        state = {'shutdown': False, 'faults': 0}

        def listener(pid, port):
            if state['shutdown'] and not state['faults']:
                state['faults'] += 1
                raise OSError(errno.EIO, 'authored listener observation')
            return original_listener(pid, port)

        def shutdown():
            state['shutdown'] = True
            try:
                return original_shutdown()
            finally:
                state['shutdown'] = False
        obs.shutdown, ops.owned_listener = shutdown, listener
        try:
            code = obs.run()
            observed = {'terminated': ops.proc.terminated, 'exit': ops.proc.poll()}
        finally:
            # Fake only; this cleanup must not turn a missing production
            # termination into a passing observation above.
            if ops.proc is not None and ops.proc.poll() is None:
                ops.proc.terminate()
                ops.proc.wait(timeout=8)
        self.assertEqual(state['faults'], 1)
        self.assertEqual(code, 1)
        self.assertFalse(obs.report['cleanup']['clean'])
        self.assertFalse(obs.report['acquisition_and_cleanup_valid'])
        self.assertTrue(observed['terminated'], observed)
        self.assertEqual(observed['exit'], 0, observed)

    def test_root_truncated_404_log_uses_status_axis(self):
        plans = self.plans(2)
        body = b'Not Found'
        ops = FakeOps(self.output, {plans[0]['wire']: (
            404, {'Content-Length': str(len(body)), 'Content-Type': 'text/plain'}, body, {'fault': 'truncate'})})
        ops.routes.update(self.model_route(plans[1]))
        obs = self.observer(ops, plans=plans)
        self.assertEqual(obs.run(), 0)
        rep = self.report()
        row = rep['targets'][0]
        self.assertEqual(row['http_status'], 404)
        self.assertEqual(row['stop_reason'], 'transport_error')
        self.assertFalse(row['wire_complete'])
        self.assertEqual(row['wire_bytes'], len(body) // 2)
        self.assertEqual(rep['missing_log']['expected_404'], 1)
        self.assertEqual(rep['missing_log']['entries'], 1)
        self.assertTrue(rep['missing_log']['valid'])
        self.assertEqual(rep['coverage_counts']['http_404'], 1)
        self.assertEqual(rep['coverage_counts']['transport'], 1)
        self.assertTrue(rep['targets'][1]['stored']['complete'])
        self.assertTrue(rep['acquisition_and_cleanup_valid'])

    def test_root_late_startup_listener_query_cannot_admit_health(self):
        ops = FakeOps(self.output)
        original = ops.owned_listener
        fired = []

        def listener(pid, port):
            if ops.proc is not None and not ops.requests and not fired:
                fired.append(True)
                ops.clock.value += omd.POLICY['startup_seconds'] + 1
                return True
            return original(pid, port)
        ops.owned_listener = listener
        obs = self.observer(ops, n=1)
        self.assertEqual(obs.run(), 1)
        self.assertEqual(fired, [True])
        self.assertEqual(ops.requests, [])
        self.assertEqual(obs.report['halt_reason'], 'startup_timeout')
        self.assertFalse(obs.report['acquisition_and_cleanup_valid'])
        self.assertTrue(ops.proc.terminated)
        self.assertEqual(ops.proc.poll(), 0)

    def test_root_exact_private_driver_identity_drift_rejects(self):
        private_driver = self.root / 'exact-driver-copy.py'
        data = Path(omd.__file__).read_bytes()
        private_driver.write_bytes(data)
        os.chmod(private_driver, 0o600)
        ops = FakeOps(self.output)
        fired = []

        def change_identity(url):
            if url == '/api/health':
                os.utime(private_driver, ns=(1, 1))
                fired.append(True)
        ops.after_request = change_identity
        # __file__ is used solely by own_sha(); the copied bytes are data,
        # never imported or executed. All mutations stay in this fixture root.
        with mock.patch.object(omd, '__file__', str(private_driver)):
            before = omd.own_sha()
            obs = omd.Observer(dict(self.meta, plans=self.plans(1)), self.output, before,
                               ops=ops, natives=self.natives, container=self.container)
            code = obs.run()
            after = omd.own_sha()
        self.assertEqual(fired, [True])
        self.assertEqual((before['bytes'], before['sha256']), (after['bytes'], after['sha256']))
        self.assertNotEqual(before['identity'], after['identity'])
        self.assertEqual(code, 1)
        self.assertFalse(obs.report['postchecks_valid'])
        self.assertFalse(obs.report['acquisition_and_cleanup_valid'])

    def test_root_postscan_listener_query_crossing_deadline_rejects(self):
        ops = FakeOps(self.output, self.model_route(self.plans(1)[0]))
        obs = self.observer(ops, n=1)
        original_scan, original_listener = obs.scan, ops.owned_listener
        state = {'scan_returned': False, 'faults': 0}

        def scan():
            result = original_scan()
            state['scan_returned'] = True
            return result

        def listener(pid, port):
            if state['scan_returned'] and not state['faults']:
                state['faults'] += 1
                ops.clock.value = obs.deadline + 1
            return original_listener(pid, port)
        obs.scan, ops.owned_listener = scan, listener
        self.assertEqual(obs.run(), 1)
        self.assertEqual(state['faults'], 1)
        self.assertTrue(obs.report['all_targets_attempted'])
        self.assertTrue(obs.report['targets'][0]['wire_complete'])
        self.assertTrue(obs.report['targets'][0]['stored']['complete'])
        self.assertEqual(obs.report['halt_reason'], 'acquisition_deadline')
        self.assertFalse(obs.report['acquisition_and_cleanup_valid'])

    def test_root_unknown_stored_bytes_does_not_publish_numeric_total(self):
        ops = FakeOps(self.output, self.model_route(self.plans(1)[0]))
        obs = self.observer(ops, n=1)
        original = omd.read_admitted
        fired = []

        def read(path, *args, **kwargs):
            rel = obs.report['targets'][0]['stored']['file']
            if rel is not None and os.fspath(path) == os.path.join(self.output, rel) and kwargs.get('keep'):
                fired.append(True)
                raise omd.Refusal('authored stored verification unavailable')
            return original(path, *args, **kwargs)
        with mock.patch.object(omd, 'read_admitted', read):
            self.assertEqual(obs.run(), 1)
        rep = self.report()
        self.assertTrue(fired)
        self.assertTrue(rep['targets'][0]['wire_complete'])
        self.assertIsNone(rep['targets'][0]['stored']['bytes'])
        self.assertIsNone(rep['targets'][0]['stored']['sha256'])
        self.assertFalse(rep['targets'][0]['stored']['complete'])
        self.assertIsNone(rep['totals']['stored_bytes'])
        self.assertEqual(rep['totals']['wire_bytes'], len(HEALTH_BODY) + 10)
        self.assertFalse(rep['acquisition_and_cleanup_valid'])

    def test_root_one_shot_final_publication_failure_stays_unqualified(self):
        ops = FakeOps(self.output)
        obs = self.observer(ops, n=1)
        original, hits = os.replace, []

        def replace(src, dst):
            hits.append(dst)
            if len(hits) == 3:  # Prefill and launch are the first two checkpoints.
                raise OSError(errno.EIO, 'authored final publication')
            return original(src, dst)
        with mock.patch.object(os, 'replace', replace):
            self.assertEqual(obs.run(), 1)
        self.assertGreaterEqual(len(hits), 3)
        self.assertFalse(obs.report['acquisition_and_cleanup_valid'])
        self.assertEqual(obs.report['halt_reason'], 'publication_failure')
        # This one-shot fault permits the root correction's bounded recovery;
        # unlike the persistent-failure control, require its failure receipt.
        rep = self.report()
        self.assertFalse(rep['acquisition_and_cleanup_valid'])
        self.assertEqual(rep['halt_reason'], 'publication_failure')
        self.assertFalse(Path(self.output, '.report-next').exists())

    def test_root_incomplete_read_partial_received_bytes_count_without_storage(self):
        plans = self.plans(2)
        body = b'GRSM\x01\x05tiny'
        partial = body[:2]
        ops = FakeOps(self.output, self.model_route(plans[0], body=body))
        ops.routes.update(self.model_route(plans[1]))
        original = ops.respond
        fired = []

        def respond(url):
            response = original(url)
            if url == plans[0]['wire']:
                def read1(n):
                    self.assertGreaterEqual(n, len(partial))
                    response._pos = len(partial)
                    response.length = len(body) - len(partial)
                    fired.append(True)
                    raise http.client.IncompleteRead(partial, len(body) - len(partial))
                response.read1 = read1
            return response
        ops.respond = respond
        obs = self.observer(ops, plans=plans)
        self.assertEqual(obs.run(), 0)
        rep, row = self.report(), obs.report['targets'][0]
        self.assertEqual(fired, [True])
        self.assertEqual(row['stop_reason'], 'transport_error')
        self.assertEqual(row['wire_bytes'], len(partial))
        self.assertFalse(row['wire_complete'])
        self.assertEqual(row['stored']['bytes'], 0)
        self.assertEqual(row['stored']['sha256'], EMPTY_SHA)
        self.assertFalse(row['stored']['complete'])
        self.assertEqual(rep['totals']['wire_bytes'], len(HEALTH_BODY) + len(partial) + 10)
        self.assertEqual(rep['totals']['stored_bytes'], len(HEALTH_BODY) + 10)
        self.assertTrue(rep['targets'][1]['stored']['complete'])
        self.assertTrue(rep['acquisition_and_cleanup_valid'])


# ------------------------------------------------------------- T07.007.006

NEW_HEALTH_BODY = b'{"status":"ok","service":"robrowser-remoteclient","version":"1.0.5"}'
CACHE_DOC = {'index': {'grfCount': 5, 'uniqueFiles': 12, 'totalFiles': 20, 'mojibakeKeys': 0},
             'cache': {'size': 0, 'maxSize': 0, 'maxMemoryMB': '0', 'memoryUsedMB': '0.00', 'hitRate': '0.00%'}}
CACHE_BODY = json.dumps(CACHE_DOC, separators=(',', ':')).encode()
JSON_HEADERS = {'Content-Type': 'application/json'}
_NEW_META = None


def new_meta():
    global _NEW_META
    if _NEW_META is None:
        _NEW_META = omd.load_metadata(NEW_INPUT_ROOT, str(NEW_PROFILE))
    return _NEW_META


def cache_body(**changes):
    doc = json.loads(CACHE_BODY)
    for dotted, value in changes.items():
        section, name = dotted.split('__')
        if value is _ABSENT:
            doc[section].pop(name)
        else:
            doc[section][name] = value
    return json.dumps(doc).encode()


_ABSENT = object()


class T07Admission(unittest.TestCase):
    """Metadata-only checks for the exact second descriptor; canonical inputs stay unopened."""

    def run_main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), mock.patch.object(sys, 'stderr', err):
            code = omd.main(argv)
        text = out.getvalue()
        self.assertLessEqual(len(text.encode()), 4096)
        self.assertEqual(text.count('\n'), 1)
        self.assertEqual(err.getvalue(), '')
        return code, json.loads(text), text

    def test_profile_pin(self):
        data = NEW_PROFILE.read_bytes()
        self.assertEqual((len(data), hashlib.sha256(data).hexdigest()), (9680, NEW_PROFILE_SHA))
        self.assertEqual((omd.T07_PROFILE_BYTES, omd.T07_PROFILE_SHA), (9680, NEW_PROFILE_SHA))
        # Old pins are unchanged, including the pre-.005 producer.
        self.assertEqual((omd.PROFILE_BYTES, omd.PROFILE_SHA), (7258, 'c581255b5b77cbd7c675ada5e271360e274bdbbe740a4e7eb921317b4c6889f5'))
        self.assertEqual(omd.LEGACY_ROUTE['producer_pin'], {'bytes': 31720, 'sha256': '12f5a315950a4f34ce8fd6aa7e2d0f4e075121f9ccbddeaae49b233b5f70897f'})
        self.assertEqual(len(omd.ROUTES), 2)
        self.assertEqual(len(omd.T07_SOURCE_PATHS), 22)
        self.assertEqual([p for p in omd.T07_SOURCE_PATHS[:16] if p not in omd.LEGACY_SOURCE_PATHS], [omd.T07_PRIOR_PROFILE_PATH])

    def test_new_preflight_forbidden_native_process_socket_output_home(self):
        profile = json.loads(NEW_PROFILE.read_bytes())
        manifest = json.loads(Path(NEW_INPUT_ROOT, omd.T07_MANIFEST_PATH).read_bytes())
        forbidden = {os.path.normpath(os.path.join(NEW_INPUT_ROOT, n['path'])) for n in profile['native']}
        forbidden.update(os.path.normpath(os.path.join(NEW_INPUT_ROOT, j['body_path'])) for j in manifest['jobs'])
        forbidden.add(os.path.normpath(os.path.join(NEW_INPUT_ROOT, profile['native'][0]['path'], '..')))
        forbidden.add('/Users/shem/Library/Application Support/Ragnarok Offline/runtime/bin/robrowser-remoteclient')
        self.assertEqual(len(forbidden), 6 + 12 + 2)
        real_open, real_lstat, real_stat = os.open, os.lstat, os.stat
        hits = []

        def guard(fn, writes=False):
            def inner(path, *a, **k):
                if os.path.normpath(os.fspath(path)) in forbidden:
                    hits.append('native')
                    raise AssertionError('native/body path reached')
                if writes and a and a[0] & (os.O_CREAT | os.O_WRONLY | os.O_RDWR):
                    hits.append('write')
                    raise AssertionError('output created')
                return fn(path, *a, **k)
            return inner
        forbid = mock.Mock(side_effect=AssertionError('forbidden effect'))
        env = {k: v for k, v in os.environ.items() if k != 'HOME'}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(os, 'open', guard(real_open, writes=True)), mock.patch.object(os, 'lstat', guard(real_lstat)), \
                mock.patch.object(os, 'stat', guard(real_stat)), mock.patch.object(subprocess, 'Popen', forbid), \
                mock.patch.object(subprocess, 'run', forbid), mock.patch.object(http.client, 'HTTPConnection', forbid), \
                mock.patch.object(socket, 'socket', forbid), mock.patch.object(socket, 'create_connection', forbid), \
                mock.patch.object(threading.Thread, 'start', forbid), mock.patch.object(os, 'mkdir', forbid), \
                mock.patch.object(os, 'replace', forbid), mock.patch.object(os.path, 'expanduser', forbid), \
                mock.patch.object(omd, 'native_specs', forbid), mock.patch.object(omd, 'Observer', forbid):
            code, payload, text = self.run_main(['--preflight', '--input-root', NEW_INPUT_ROOT, '--profile', str(NEW_PROFILE)])
        self.assertEqual(code, 0, text)
        self.assertEqual(hits, [])
        forbid.assert_not_called()
        self.assertEqual((payload['status'], payload['task'], payload['profile_sha256']), ('preflight_ok', 'T07.007.006', NEW_PROFILE_SHA))
        self.assertEqual(payload['catalog_sha256'], '0a6d44ec22de3c54f5195c32d6fd253ef5f51a74feb212181181ab5d9570c362')
        self.assertEqual(payload['counts'], {'roots': 4, 'jobs': 12, 'targets': 311, 'referrers': 337, 'gap_roots': 0,
                                             'source_pins': 22, 'kinds': {'model': 273, 'bmp': 38, 'jpeg': 0}})
        self.assertIsNone(payload['native_qualification'])
        self.assertFalse(payload['native_or_network_or_process'])
        self.assertNotIn(NEW_INPUT_ROOT, text)
        self.assertNotIn('T06.003.003.005', text)

    def test_old_profile_refuses_canonical_producer_drift(self):
        # Expected evidence: the unchanged old pin refuses the integrated .005 producer.
        code, payload, text = self.run_main(['--preflight', '--input-root', NEW_INPUT_ROOT, '--profile', str(PROFILE)])
        self.assertEqual((code, payload), (2, {'status': 'refused', 'reason': 'admit_size'}))
        code, payload, _ = self.run_main(['--preflight', '--input-root', INPUT_ROOT, '--profile', str(PROFILE)])
        self.assertEqual((code, payload['task'], payload['counts']['targets']), (0, 'T06.003.003.005', 11134))

    def test_new_profile_refuses_legacy_snapshot(self):
        code, payload, text = self.run_main(['--preflight', '--input-root', INPUT_ROOT, '--profile', str(NEW_PROFILE)])
        self.assertEqual(code, 2)
        self.assertEqual(payload['status'], 'refused')
        self.assertNotIn(INPUT_ROOT, text)

    def test_route_selected_only_by_trusted_bytes(self):
        root = private_dir(PRIVATE / ('t07-profile-%d' % os.getpid()))
        try:
            data = NEW_PROFILE.read_bytes()
            exact, changed, padded = root / 'exact.json', root / 'changed.json', root / 'padded.json'
            exact.write_bytes(data)
            changed.write_bytes(data.replace(b'"asset_attempts": 311', b'"asset_attempts": 312'))
            padded.write_bytes(data + b' ')
            for path in (exact, changed, padded):
                os.chmod(path, 0o600)
            self.assertEqual(self.run_main(['--preflight', '--input-root', NEW_INPUT_ROOT, '--profile', str(exact)])[0], 0)
            # Same size, wrong SHA: no route. Larger than any descriptor: refused before allocation.
            for path, reason in ((changed, 'profile_pin'), (padded, 'admit_limit')):
                with self.subTest(path.name):
                    code, payload, _ = self.run_main(['--preflight', '--input-root', NEW_INPUT_ROOT, '--profile', str(path)])
                    self.assertEqual((code, payload['reason']), (2, reason))
        finally:
            shutil.rmtree(root)

    def test_descriptor_cross_substitution(self):
        new = json.loads(NEW_PROFILE.read_bytes())
        old = json.loads(PROFILE.read_bytes())
        omd.check_profile(new, omd.T07_ROUTE)
        omd.check_profile(old, omd.LEGACY_ROUTE)
        self.assertRaises(omd.Refusal, omd.check_profile, old, omd.T07_ROUTE)
        self.assertRaises(omd.Refusal, omd.check_profile, new, omd.LEGACY_ROUTE)

        def pin_of(profile, path):
            return [p for p in profile['source_pins'] if p['path'] == path][0]
        mutations = {
            'old_task': lambda p: p.__setitem__('task', 'T06.003.003.005'),
            'old_policy': lambda p: p.__setitem__('policy', dict(omd.POLICY)),
            'cache_attempt_override': lambda p: p['policy'].__setitem__('cache_attempts', 3),
            'asset_count_override': lambda p: p['policy'].__setitem__('asset_attempts', 11134),
            'native_order': lambda p: p['native'].insert(1, p['native'].pop(2)),
            'old_native_names': lambda p: p.__setitem__('native', old['native']),
            'home_base': lambda p: p['native'][0].__setitem__('base', 'home'),
            'missing_native': lambda p: p['native'].pop(),
            'old_sources': lambda p: p.__setitem__('source_pins', old['source_pins']),
            'source_dropped': lambda p: p['source_pins'].pop(),
            'source_reordered': lambda p: p['source_pins'].insert(0, p['source_pins'].pop()),
            'old_producer': lambda p: pin_of(p, omd.PRODUCER_PATH).update(bytes=31720, sha256=omd.LEGACY_ROUTE['producer_pin']['sha256']),
            'old_prior_path': lambda p: pin_of(p, omd.T07_PRIOR_PROFILE_PATH).__setitem__('path', omd.PRIOR_PROFILE_PATH),
            'prior_hash': lambda p: pin_of(p, omd.T07_PRIOR_PROFILE_PATH).__setitem__('sha256', '0' * 64),
            'old_catalog': lambda p: p.__setitem__('catalog', old['catalog']),
            'catalog_hash': lambda p: p['catalog'].__setitem__('sha256', '0' * 64)}
        for name, mutate in mutations.items():
            with self.subTest(name):
                broken = json.loads(NEW_PROFILE.read_bytes())
                mutate(broken)
                self.assertRaises(omd.Refusal, omd.check_profile, broken, omd.T07_ROUTE)
        old_mut = json.loads(PROFILE.read_bytes())
        [p for p in old_mut['source_pins'] if p['path'] == omd.PRODUCER_PATH][0].update(
            bytes=48337, sha256=omd.T07_ROUTE['producer_pin']['sha256'])
        self.assertRaises(omd.Refusal, omd.check_profile, old_mut, omd.LEGACY_ROUTE)  # Never accept both producers.

    def admitted_inputs(self):
        def load(rel):
            return json.loads(Path(NEW_INPUT_ROOT, rel).read_bytes())
        return (load(omd.T07_PRIOR_PROFILE_PATH), load(omd.T07_CONSTRUCTOR_PROFILE_PATH), load(omd.T07_MANIFEST_PATH))

    def test_new_catalog_validation_refuses_corruption(self):
        meta = new_meta()
        profile = meta['profile']
        prior, cp, manifest = self.admitted_inputs()
        plans, referrers = omd.validate_catalog_t07(json.loads(meta['catalog_bytes']), profile, prior, cp, manifest)
        self.assertEqual((len(plans), referrers), (311, 337))
        self.assertEqual(sum(len(t['referrers']) for t in meta['catalog']['targets']), 337)
        catalog_mutations = {
            'referrer_pop': lambda c: c['targets'][5]['referrers'].pop(),
            'referrer_duplicate': lambda c: c['targets'][0]['referrers'].append(dict(c['targets'][0]['referrers'][0])),
            'referrer_role': lambda c: c['targets'][0]['referrers'][0].__setitem__('role', 'model'),
            'http': lambda c: c['targets'][7].__setitem__('http_path', c['targets'][7]['http_path'] + 'x'),
            'order': lambda c: c['targets'].reverse(),
            'filemanager': lambda c: c['jobs'][2]['loader_entries'][0].__setitem__('filemanager_name', 'data\\model\\other.rsm'),
            'loader_target': lambda c: c['jobs'][2]['loader_entries'][0].__setitem__('target_index', 0),
            'occurrence_range': lambda c: c['jobs'][2]['occurrence_loader_indexes'].append(10 ** 6),
            'job_reference_dup': lambda c: c['jobs'][0]['root_references'].append(dict(c['jobs'][0]['root_references'][0])),
            'root_original_ordinal': lambda c: c['roots'][1].__setitem__('original_gap_root_ordinal', 7),
            'root_ordinal_status': lambda c: c['roots'][1].__setitem__('original_gap_root_ordinal_status', 'known'),
            'root_scope': lambda c: c['roots'][2].__setitem__('ordinal_scope', 'world'),
            'root_name': lambda c: c['roots'][3].__setitem__('name', 'prontera'),
            'parse_outcome': lambda c: c['roots'][0]['edges']['gnd'].__setitem__('parse_outcome', 'failed'),
            'parse_status': lambda c: c['roots'][0]['edges']['gnd'].__setitem__('parse_status', 'run'),
            'edge_swap': lambda c: c['roots'][0]['edges']['gnd'].__setitem__('job_id', 'target-004:gnd'),
            'job_sha': lambda c: c['jobs'][1].__setitem__('complete_sha256', '0' * 64),
            'job_bytes': lambda c: c['jobs'][1].__setitem__('input_bytes', c['jobs'][1]['input_bytes'] + 1),
            'job_header': lambda c: c['jobs'][1].__setitem__('header_version_bytes', [1, 8]),
            'job_outcome': lambda c: c['jobs'][1].__setitem__('outcome', 'threw'),
            'job_constructor_int': lambda c: c['jobs'][1].__setitem__('constructor_returned', 1),
            'input_pins': lambda c: c['input_pins']['jobs.jsonl'].__setitem__('bytes', 1),
            'input_pins_order': lambda c: c.__setitem__('input_pins', dict(reversed(list(c['input_pins'].items())))),
            'limitations': lambda c: c['limitations'].pop(),
            'rule_sources': lambda c: c['rule_sources'].pop('src/Loaders/Ground.js'),
            'constructor_profile': lambda c: c.__setitem__('constructor_profile_sha256', '0' * 64),
            'summary': lambda c: c.__setitem__('summary_sha256', '0' * 64),
            'constructor_task': lambda c: c.__setitem__('constructor_task', 'T07.007.003'),
            'constructor_worker': lambda c: c['constructor_worker'].__setitem__('bytes', 1),
            'constructor_producer': lambda c: c['constructor_producer'].__setitem__('commit', '0' * 40),
            'counts': lambda c: c['counts'].__setitem__('http_targets', 312),
            'gaps': lambda c: c.__setitem__('remaining_gap_root_ordinals', [0]),
            'profile_binding': lambda c: c.__setitem__('profile_sha256', '0' * 64),
            'task': lambda c: c.__setitem__('task', 'T06.003.003.004'),
            'extra_key': lambda c: c.__setitem__('combined_observation', 'ok'),
            'census_jpeg': None}
        for name, mutate in catalog_mutations.items():
            with self.subTest(catalog=name):
                broken = json.loads(meta['catalog_bytes'])
                if name == 'census_jpeg':
                    # A consistent rename into a JPEG target is still outside the admitted census.
                    t = broken['targets'][0]
                    t['http_path'] = t['http_path'][:-4] + '.jpg'
                    for ref in t['referrers']:
                        entry = broken['jobs'][ref['job_index']]['loader_entries'][ref['loader_index']]
                        for f in ('raw_name', 'logical_name', 'filemanager_name'):
                            entry[f] = entry[f][:-4] + '.jpg'
                        entry['http_path'] = t['http_path']
                else:
                    mutate(broken)
                self.assertRaises(omd.Refusal, omd.validate_catalog_t07, broken, profile, prior, cp, manifest)
        side_mutations = {
            'prior_manifest_pin': ('prior', lambda d: d['constructor_manifest'].__setitem__('sha256', '0' * 64)),
            'prior_summary': ('prior', lambda d: d['summary'].__setitem__('bytes', 1)),
            'prior_counts': ('prior', lambda d: d['expected_counts'].__setitem__('jobs', 13)),
            'prior_task': ('prior', lambda d: d.__setitem__('task', 'T06.003.003.004')),
            'cp_manifest': ('cp', lambda d: d['manifest'].__setitem__('bytes', 1)),
            'cp_counts': ('cp', lambda d: d['counts'].__setitem__('observed', 3)),
            'manifest_scope': ('manifest', lambda d: d['roots'][0].__setitem__('ordinal_scope', 'world')),
            'manifest_ordinal': ('manifest', lambda d: d['roots'][0].__setitem__('original_gap_root_ordinal', 3)),
            'manifest_job_sha': ('manifest', lambda d: d['jobs'][3].__setitem__('complete_sha256', '0' * 64)),
            'manifest_job_order': ('manifest', lambda d: d['jobs'].reverse()),
            'manifest_gaps': ('manifest', lambda d: d.__setitem__('remaining_gap_root_ordinals', [1])),
            'manifest_task': ('manifest', lambda d: d.__setitem__('task', 'T07.007.005'))}
        for name, (which, mutate) in side_mutations.items():
            with self.subTest(side=name):
                inputs = dict(zip(('prior', 'cp', 'manifest'), self.admitted_inputs()))
                mutate(inputs[which])
                self.assertRaises(omd.Refusal, omd.validate_catalog_t07, json.loads(meta['catalog_bytes']), profile,
                                  inputs['prior'], inputs['cp'], inputs['manifest'])

    def test_old_new_catalog_cross_validation(self):
        meta, old = new_meta(), real_meta()
        prior, cp, manifest = self.admitted_inputs()
        old_prior = [p for p in old['profile']['source_pins'] if p['path'] == omd.PRIOR_PROFILE_PATH][0]
        self.assertRaises(omd.Refusal, omd.validate_catalog, json.loads(meta['catalog_bytes']), old['profile'], old_prior)
        self.assertRaises(omd.Refusal, omd.validate_catalog_t07, old['catalog'], meta['profile'], prior, cp, manifest)
        self.assertRaises(omd.Refusal, omd.validate_catalog_t07, json.loads(meta['catalog_bytes']), old['profile'], prior, cp, manifest)

    def test_native_specs_never_look_up_home(self):
        meta = new_meta()
        env = {k: v for k, v in os.environ.items() if k != 'HOME'}
        with mock.patch.dict(os.environ, env, clear=True), \
                mock.patch.object(os.path, 'expanduser', side_effect=AssertionError('HOME lookup')) as lookup:
            specs = omd.native_specs(meta)
        lookup.assert_not_called()
        self.assertEqual([s['name'] for s in specs], omd.T07_NATIVE_NAMES)
        self.assertTrue(all(s['path'].startswith(os.path.normpath(NEW_INPUT_ROOT) + '/') for s in specs))
        self.assertEqual(specs[0]['path'], os.path.join(os.path.normpath(NEW_INPUT_ROOT),
                                                        '.tools/renewal/t07-007-native-artifact-admission-1/reader'))
        self.assertEqual([s['bytes'] for s in specs[1:]], [306097616, 86992, 5833135, 2123919641, 2172616301])
        # The legacy route keeps its HOME-based binary semantics unchanged.
        fake_home = str(PRIVATE / 'wrong-home')
        with mock.patch.dict(os.environ, dict(os.environ, HOME=fake_home)):
            old_specs = omd.native_specs(real_meta())
        self.assertTrue(old_specs[0]['path'].startswith(fake_home + '/'))


class PipedProc(FakeProc):
    """Fake owned child whose stdout/stderr are real tiny pipes."""

    def __init__(self, ops):
        super().__init__(ops)
        self.writers = {}
        for stream in ('stdout', 'stderr'):
            read_fd, write_fd = os.pipe()
            setattr(self, stream, os.fdopen(read_fd, 'rb', buffering=0))
            self.writers[stream] = write_fd

    def emit(self, stream, data):
        os.write(self.writers[stream], data)

    def close_writers(self):
        for stream in list(self.writers):
            os.close(self.writers.pop(stream))

    def poll(self):
        if self.returncode is not None:
            self.close_writers()
        return self.returncode

    def terminate(self):
        if self.ops.on_terminate is not None and self.writers:
            self.ops.on_terminate(self)
        super().terminate()
        if self.returncode is not None:
            self.close_writers()

    def kill(self):
        super().kill()
        self.close_writers()


class PipedOps(FakeOps):
    def __init__(self, server, natives, routes=None):
        super().__init__(server, routes)
        self.routes.setdefault('/api/health', (200, dict(JSON_HEADERS), NEW_HEALTH_BODY))
        self.cache_specs = [(200, dict(JSON_HEADERS), CACHE_BODY), (200, dict(JSON_HEADERS), CACHE_BODY)]
        self.cache_calls, self.thread_names, self.thread_fail_at = 0, [], None
        self.on_terminate = self.getpgid_hook = self.popen_error = None
        self.startup = [b'remote client 1.0.5 starting\n']
        self.startup += [b'  Valid GRF: %s (version %s, %d files)\n' % (n['path'].encode(), v.encode(), c)
                         for n, (v, c) in zip(natives[1:], omd.T07_VALID_GRF)]
        self.startup.append(b'listening on 127.0.0.1:54321\n')
        self.startup_stream, self.chunk = 'stdout', 7

    def sleep(self, seconds):
        self.sleep_calls += 1
        time.sleep(0.002)
        self.clock.value += 0.05

    def popen(self, argv, cwd, env):
        raise AssertionError('legacy DEVNULL popen on the T07 route')

    def popen_piped(self, argv, cwd, env):
        self.popen_calls.append((argv, cwd, env))
        if self.popen_error is not None:
            raise self.popen_error
        self.proc = PipedProc(self)
        data = b''.join(self.startup)
        for i in range(0, len(data), self.chunk):  # Lines straddle pipe chunks.
            self.proc.emit(self.startup_stream, data[i:i + self.chunk])
        return self.proc

    def getpgid(self, pid):
        if self.getpgid_hook is not None:
            self.getpgid_hook()
        return pid

    def start_thread(self, target, name):
        self.thread_names.append(name)
        if self.thread_fail_at == len(self.thread_names):
            raise RuntimeError('authored thread start failure')
        thread = threading.Thread(target=target, name='fixture-' + name, daemon=True)
        thread.start()
        return thread

    def respond(self, url):
        if url == '/api/cache-stats':
            self.routes[url] = self.cache_specs[min(self.cache_calls, 1)]
            self.cache_calls += 1
        return super().respond(url)


def asset_routes(plans, missing=()):
    routes = {}
    for position, plan in enumerate(plans):
        if position in missing:
            continue
        body = (b'GRSM\x02\x02' if plan['kind'] == 'model' else b'BM\x36\x00') + bytes([position % 251]) * 3
        routes[plan['wire']] = (200, {'Content-Type': 'application/octet-stream', 'Content-Length': str(len(body))}, body)
    return routes


class T07Lifecycle(unittest.TestCase):
    """Production methods with tiny private stand-ins, real tiny pipes and fake process/network."""

    @classmethod
    def setUpClass(cls):
        cls.meta = new_meta()
        cls.driver = omd.own_sha()

    def setUp(self):
        self.root = private_dir(PRIVATE / ('t07-%d-%s' % (os.getpid(), self._testMethodName)))
        for child in self.root.iterdir():
            shutil.rmtree(child) if child.is_dir() else child.unlink()
        native_dir = private_dir(self.root / 'native')
        self.natives = []
        for name in omd.T07_NATIVE_NAMES:
            data = ('tiny authored stand-in ' + name).encode()
            path = native_dir / name
            path.write_bytes(data)
            os.chmod(path, 0o600)
            self.natives.append({'name': name, 'path': str(path), 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
        self.container = str(private_dir(self.root / 'container'))
        self.output = os.path.join(self.container, 'out')
        self.server = os.path.join(self.output, 'server')
        self.ops_made = []
        self.fds_before, self.threads_before = open_fds(), set(threading.enumerate())
        self.reload = mock.patch.object(omd, 'load_metadata', return_value=self.meta)
        self.reload.start()

    def tearDown(self):
        self.reload.stop()
        for ops in self.ops_made:  # Fake child exit only; production descriptors are inspected next.
            if isinstance(ops.proc, PipedProc):
                ops.proc.close_writers()
        try:  # Leak inspection happens before fixture deletion.
            self.assertEqual(open_fds() - self.fds_before, set(), 'descriptor leak')
            self.assertEqual(set(threading.enumerate()) - self.threads_before, set(), 'thread leak')
        finally:
            shutil.rmtree(self.root)

    def ops(self, plans=None, missing=()):
        if os.path.exists(self.output):
            shutil.rmtree(self.output)
        ops = PipedOps(self.server, self.natives, asset_routes(plans or [], missing))
        self.ops_made.append(ops)
        return ops

    def observer(self, ops, plans, policy=None, write_fn=None, diag_write_fn=None):
        return omd.Observer(dict(self.meta, plans=plans), self.output, self.driver, ops=ops, natives=self.natives,
                            policy=policy, container=self.container, write_fn=write_fn, diag_write_fn=diag_write_fn)

    def report(self):
        return json.loads(Path(self.output, 'report.json').read_bytes())

    def wait_for(self, predicate):
        end = time.monotonic() + 5
        while not predicate():
            self.assertLess(time.monotonic(), end, 'fixture wait')
            time.sleep(0.002)

    def assert_cleaned(self, ops, rep):
        self.assertTrue(ops.proc.terminated or ops.proc.returncode is not None)
        self.assertIsNotNone(ops.proc.poll())
        self.assertTrue(rep['diagnostics']['finished'] if 'finished' in rep['diagnostics'] else True)
        self.assertFalse(rep['acquisition_and_cleanup_valid'])

    def test_full_production_fake_scan_all_311(self):
        plans = self.meta['plans']
        self.assertEqual(len(plans), 311)
        missing = (3, 200)
        ops = self.ops(plans, missing)
        obs = self.observer(ops, plans)
        self.assertEqual(obs.run(), 0)
        rep = self.report()
        self.assertTrue(rep['acquisition_and_cleanup_valid'])
        self.assertEqual((rep['task'], rep['schema'], rep['launch']['profile_sha256']), ('T07.007.006', omd.SCHEMA, NEW_PROFILE_SHA))
        self.assertEqual(ops.requests, ['/api/health', '/api/cache-stats'] + [p['wire'] for p in plans] + ['/api/cache-stats'])
        self.assertEqual(len(ops.requests), 314)
        self.assertEqual(len(rep['targets']), 311)
        self.assertTrue(all(r['attempted'] for r in rep['targets']))
        self.assertEqual([r['request_index'] for r in rep['targets']], list(range(2, 313)))
        self.assertEqual((rep['health']['request_index'], rep['cache_before']['request_index'], rep['cache_after']['request_index']), (0, 1, 313))
        self.assertTrue(rep['health']['version_ok'] and rep['health']['valid'])
        for key in ('cache_before', 'cache_after'):
            self.assertTrue(rep[key]['valid'] and rep[key]['grf_count_ok'] and rep[key]['cache_size_ok'] and rep[key]['cache_max_size_ok'])
            self.assertEqual(rep[key]['observations'], {'cache.maxMemoryMB': '0', 'cache.memoryUsedMB': '0.00', 'cache.hitRate': '0.00%',
                                                        'index.uniqueFiles': 12, 'index.totalFiles': 20, 'index.mojibakeKeys': 0})
        self.assertEqual({k: rep['totals'][k] for k in ('asset_attempts', 'health_attempts', 'cache_attempts')},
                         {'asset_attempts': 311, 'health_attempts': 1, 'cache_attempts': 2})
        bodies = sum(len(asset_routes(plans, missing)[p['wire']][2]) for i, p in enumerate(plans) if i not in missing)
        self.assertEqual(rep['totals']['wire_bytes'], len(NEW_HEALTH_BODY) + 2 * len(CACHE_BODY) + bodies + 2 * len(b'Not Found'))
        stops = [r['stop_reason'] for r in rep['targets']]
        self.assertEqual(stops.count('complete'), 309)
        self.assertEqual([i for i, s in enumerate(stops) if s == 'http_404'], list(missing))
        self.assertEqual(rep['coverage_counts']['complete_200_matching_prefix'], 309)
        self.assertEqual(rep['referrers'] if 'referrers' in rep else rep['catalog_refs']['referrers'], 337)
        archives = rep['startup_archive_counts']
        self.assertEqual([(a['name'], a['expected_version'], a['expected_count'], a['observed_version'], a['observed_count'], a['valid'])
                          for a in archives],
                         [(n, v, c, v, c, True) for n, (v, c) in zip(omd.T07_NATIVE_NAMES[1:], omd.T07_VALID_GRF)])
        self.assertEqual([a['path'] for a in archives], [n['path'] for n in self.natives[1:]])
        diag = rep['diagnostics']
        emitted = len(b''.join(ops.startup))
        self.assertTrue(diag['valid'] and diag['drainers_complete'] and diag['valid_grf_exact'])
        self.assertEqual((diag['seen_bytes'], diag['stored_bytes'], diag['overflow'], diag['errors']),
                         ({'stdout': emitted, 'stderr': 0}, {'stdout': emitted, 'stderr': 0}, False, []))
        self.assertEqual(Path(self.output, 'native-stdout.log').read_bytes(), b''.join(ops.startup))
        self.assertEqual(diag['files']['stdout']['sha256'], hashlib.sha256(b''.join(ops.startup)).hexdigest())
        argv, cwd, env = ops.popen_calls[0]
        self.assertEqual((argv, cwd), ([self.natives[0]['path']], self.server))
        self.assertEqual(env, {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'SERVER_ROOT': self.server, 'HOST': '127.0.0.1',
                               'PORT': '54321', 'NODE_ENV': 'development', 'CLIENT_PUBLIC_URL': 'http://127.0.0.1:54321',
                               'CLIENT_RESPATH': 'resources/', 'CLIENT_DATAINI': os.path.join(self.server, 'resources/DATA.INI'),
                               'CACHE_MAX_FILES': '0', 'CACHE_MAX_MEMORY_MB': '0', 'CACHE_WARM_UP': 'false',
                               'CLIENT_AUTOEXTRACT': 'false', 'CLIENT_ENABLESEARCH': 'false', 'ENABLE_STATIC_SERVE': 'false',
                               'ENABLE_WSPROXY': 'false', 'ENABLE_COMPRESSION': 'false'})
        ini = Path(self.server, 'resources/DATA.INI').read_text()
        self.assertEqual(ini, '[Data]\n' + ''.join('%d=%s\n' % (i, n['path']) for i, n in enumerate(self.natives[1:])))
        self.assertEqual(rep['missing_log']['entries'], 2)
        self.assertTrue(Path(self.server, 'logs/missing-files.log').exists())
        self.assertFalse(Path(self.output, 'logs').exists() or Path(self.output, 'resources').exists())
        self.assertTrue(rep['tree']['valid'] and rep['server_tree']['valid'] and rep['evidence_tree']['valid'])
        self.assertTrue(rep['retained_postverify']['valid'])
        self.assertEqual(rep['retained_postverify']['files'], 1 + 1 + 314 + 2)
        self.assertTrue(rep['postchecks_valid'] and rep['cleanup']['clean'])
        self.assertEqual(sorted(os.listdir(self.server)), ['logs', 'resources'])
        for path in Path(self.output).rglob('*'):
            self.assertEqual(stat.S_IMODE(path.lstat().st_mode), 0o700 if path.is_dir() else 0o600)
        self.assertEqual(ops.thread_names, ['diagnostics-stdout', 'diagnostics-stderr'])

    def test_404_continuation_versus_fatal_suffix(self):
        plans = self.meta['plans'][:6]
        ops = self.ops(plans, missing=(1,))
        state = {'n': 0, 'fired': False}

        def faulty(fd, buffer):
            state['n'] += 1
            if state['n'] == 6:  # health, cache, asset0, 404 body, asset2, then asset3
                state['fired'] = True
                return 0
            return os.write(fd, bytes(buffer))
        self.assertEqual(self.observer(ops, plans, write_fn=faulty).run(), 1)
        rep = self.report()
        self.assertTrue(state['fired'])
        self.assertEqual([r['stop_reason'] for r in rep['targets'][:4]], ['complete', 'http_404', 'complete', 'storage_error'])
        self.assertEqual(rep['halt_reason'], 'storage_failure')
        for row in rep['targets'][4:]:
            self.assertEqual((row['attempted'], row['stop_reason'], row['request_index']), (False, 'storage_failure', None))
        self.assertIsNone(rep['cache_after'])
        self.assertNotIn('/api/cache-stats', ops.requests[2:])
        self.assert_cleaned(ops, rep)

    def test_health_and_cache_failures_are_fatal(self):
        plans = self.meta['plans'][:2]
        cases = {
            'health_version': ('health', (200, JSON_HEADERS, b'{"status":"ok","service":"robrowser-remoteclient","version":"1.0.4"}')),
            'health_no_version': ('health', (200, JSON_HEADERS, b'{"status":"ok","service":"robrowser-remoteclient"}')),
            'grf_bool': ('before', (200, JSON_HEADERS, cache_body(index__grfCount=True))),
            'grf_float': ('before', (200, JSON_HEADERS, cache_body(index__grfCount=5.0))),
            'grf_string': ('before', (200, JSON_HEADERS, cache_body(index__grfCount='5'))),
            'grf_four': ('before', (200, JSON_HEADERS, cache_body(index__grfCount=4))),
            'grf_absent': ('before', (200, JSON_HEADERS, cache_body(index__grfCount=_ABSENT))),
            'size_one': ('before', (200, JSON_HEADERS, cache_body(cache__size=1))),
            'max_null': ('before', (200, JSON_HEADERS, cache_body(cache__maxSize=None))),
            'max_bool_false': ('before', (200, JSON_HEADERS, cache_body(cache__maxSize=False))),
            'status_500': ('before', (500, JSON_HEADERS, CACHE_BODY)),
            'invalid_json': ('before', (200, JSON_HEADERS, b'{"index":')),
            'truncated': ('before', (200, JSON_HEADERS, CACHE_BODY, {'fault': 'truncate'})),
            'oversize': ('before', (200, JSON_HEADERS, b' ' * 65537)),
            'after_invalid': ('after', (200, JSON_HEADERS, cache_body(cache__size=2)))}
        for name, (where, spec) in cases.items():
            with self.subTest(name):
                ops = self.ops(plans)
                if where == 'health':
                    ops.routes['/api/health'] = spec
                else:
                    ops.cache_specs[0 if where == 'before' else 1] = spec
                self.assertEqual(self.observer(ops, plans).run(), 1)
                rep = self.report()
                self.assertEqual(rep['halt_reason'], 'health_failure' if where == 'health' else 'cache_failure')
                if where == 'after':
                    self.assertTrue(all(r['attempted'] for r in rep['targets']))
                    self.assertFalse(rep['cache_after']['valid'])
                else:
                    self.assertTrue(all(not r['attempted'] for r in rep['targets']))
                    self.assertEqual(len(ops.requests), 1 if where == 'health' else 2)
                self.assert_cleaned(ops, rep)

    def test_health_cache_inclusive_aggregate_cap(self):
        plans = self.meta['plans'][:3]
        policy = dict(omd.T07_POLICY, aggregate_bytes_including_health=len(NEW_HEALTH_BODY) + len(CACHE_BODY) + 4)
        ops = self.ops(plans)
        self.assertEqual(self.observer(ops, plans, policy=policy).run(), 1)
        rep = self.report()
        self.assertEqual(rep['halt_reason'], 'aggregate_cap')
        self.assertEqual((rep['targets'][0]['stop_reason'], rep['targets'][0]['wire_bytes']), ('aggregate_cap', 4))
        self.assertEqual(rep['totals']['wire_bytes'], len(NEW_HEALTH_BODY) + len(CACHE_BODY) + 4)
        self.assertEqual([r['attempted'] for r in rep['targets']], [True, False, False])
        self.assertIsNone(rep['cache_after'])

    def test_attempt_and_invocation_caps(self):
        plans = self.meta['plans'][:3]
        ops = self.ops(plans)
        self.assertEqual(self.observer(ops, plans, policy=dict(omd.T07_POLICY, asset_attempts=2)).run(), 1)
        rep = self.report()
        self.assertEqual(rep['halt_reason'], 'asset_attempt_cap')
        self.assertEqual(len(ops.requests), 4)
        plans = plans[:2]
        ops = self.ops(plans)
        self.assertEqual(self.observer(ops, plans, policy=dict(omd.T07_POLICY, asset_attempts=2, cache_attempts=1)).run(), 1)
        rep = self.report()
        self.assertEqual(rep['halt_reason'], 'http_invocation_cap')
        self.assertEqual(len(ops.requests), 4)
        self.assertFalse(rep['cache_after']['attempted'])

    def test_late_final_cache_and_late_eof(self):
        plans = self.meta['plans'][:2]
        ops = self.ops(plans)
        ops.cache_specs[1] = (200, JSON_HEADERS, CACHE_BODY, {'advance': 100.0 + 1200})
        self.assertEqual(self.observer(ops, plans).run(), 1)
        rep = self.report()
        self.assertEqual(rep['halt_reason'], 'acquisition_deadline')
        self.assertTrue(rep['cache_after']['wire_complete'])
        self.assertFalse(rep['cache_after']['valid'])
        # Framed: the late final read stays complete. Unframed: the EOF read is past the deadline.
        for framed, stop in ((True, 'complete'), (False, 'deadline')):
            with self.subTest(framed=framed):
                ops = self.ops(plans)
                route = ops.routes[plans[1]['wire']]
                ops.routes[plans[1]['wire']] = route + ({'advance': 100.0 + 1200, 'framed': framed},)
                self.assertEqual(self.observer(ops, plans).run(), 1)
                rep = self.report()
                self.assertEqual(rep['halt_reason'], 'acquisition_deadline')
                self.assertEqual(rep['targets'][1]['stop_reason'], stop)
                self.assertEqual(rep['targets'][1]['wire_complete'], framed)
                self.assertIsNone(rep['cache_after'])
                self.assertEqual(ops.requests.count('/api/cache-stats'), 1)

    def test_production_write_variants(self):
        plans = self.meta['plans'][:2]
        state = {}

        def one_byte(fd, buffer):
            state['short'] = state.get('short', False) or len(buffer) > 1
            return os.write(fd, bytes(buffer[:1]))

        def eintr(fd, buffer):
            state['eintr'] = state.get('eintr', 0) + 1
            if state['eintr'] == 3:
                raise InterruptedError(errno.EINTR, 'authored')
            return os.write(fd, bytes(buffer))

        def zero(fd, buffer):
            state['zero'] = True
            return 0

        def boolean(fd, buffer):
            state['bool'] = True
            return True
        for name, fn, expected in (('short', one_byte, 0), ('eintr', eintr, 0), ('zero', zero, 1), ('bool', boolean, 1)):
            with self.subTest(name):
                ops = self.ops(plans)
                self.assertEqual(self.observer(ops, plans, write_fn=fn).run(), expected)
                self.assertTrue(state[name])
                rep = self.report()
                if expected:
                    self.assertEqual(rep['halt_reason'], 'storage_failure')
                    self.assertFalse(rep['acquisition_and_cleanup_valid'])
                else:
                    self.assertTrue(all(r['stored']['complete'] for r in rep['targets']))

    def test_connection_close_and_input_drift_faults(self):
        plans = self.meta['plans'][:3]
        ops = self.ops(plans)
        ops.routes[('connect', 3)] = 'fail'  # health, cache, asset0, then asset1
        self.assertEqual(self.observer(ops, plans).run(), 0)
        self.assertEqual([r['stop_reason'] for r in self.report()['targets']], ['complete', 'connection_setup_error', 'complete'])
        ops = self.ops(plans)
        ops.routes[plans[0]['wire']] = ops.routes[plans[0]['wire']] + ({'fault': 'close'},)
        self.assertEqual(self.observer(ops, plans).run(), 1)
        self.assertEqual(self.report()['halt_reason'], 'resource_close_failure')
        ops = self.ops(plans)
        drift = []

        def native_drift(url):
            if url == '/api/cache-stats' and not drift:
                os.utime(self.natives[1]['path'], ns=(1, 1))
                drift.append('native')
        ops.after_request = native_drift
        self.assertEqual(self.observer(ops, plans).run(), 1)
        self.assertEqual(drift, ['native'])
        self.assertFalse(self.report()['postchecks_valid'])
        ops = self.ops(plans)

        def body_drift(url):
            if url == plans[2]['wire'] and len(drift) == 1:
                os.utime(os.path.join(self.output, '000002'), ns=(1, 1))
                drift.append('body')
        ops.after_request = body_drift
        self.assertEqual(self.observer(ops, plans).run(), 1)
        rep = self.report()
        self.assertEqual(drift, ['native', 'body'])
        self.assertEqual(rep['retained_postverify']['mismatched'], ['000002'])
        self.assertFalse(rep['postchecks_valid'] or rep['acquisition_and_cleanup_valid'])

    def test_failed_final_publication(self):
        plans = self.meta['plans'][:1]
        ops = self.ops(plans)
        obs = self.observer(ops, plans)
        real_replace, hits = os.replace, []

        def replace(src, dst):
            hits.append(dst)
            if len(hits) >= 3:
                raise OSError(errno.EIO, 'authored persistent publication fault')
            return real_replace(src, dst)
        with mock.patch.object(os, 'replace', replace):
            self.assertEqual(obs.run(), 1)
        self.assertEqual(obs.halt, 'publication_failure')
        self.assertFalse(obs.report['acquisition_and_cleanup_valid'])
        self.assertFalse(Path(self.output, '.report-next').exists())

    def test_split_root_placement_faults(self):
        plans = self.meta['plans'][:2]
        cases = {
            'loose_asset_in_server': lambda: (os.makedirs(os.path.join(self.server, 'data/model'), 0o700),
                                              Path(self.server, 'data/model/x.rsm').write_bytes(b'GRSM')),
            'cache_file_in_server': lambda: (Path(self.server, 'cache.bin').write_bytes(b''), os.chmod(Path(self.server, 'cache.bin'), 0o600)),
            'symlink_in_server': lambda: os.symlink('/nonexistent', os.path.join(self.server, 'resources/link')),
            'evidence_extra': lambda: (Path(self.output, 'server.log').write_bytes(b''), os.chmod(Path(self.output, 'server.log'), 0o600)),
            'evidence_dir': lambda: os.mkdir(os.path.join(self.output, 'resources'), 0o700),
            'server_mode': lambda: os.chmod(self.server, 0o755),
            'ini_mode': lambda: os.chmod(os.path.join(self.server, 'resources/DATA.INI'), 0o644),
            'log_in_evidence': None}
        for name, tamper in cases.items():
            with self.subTest(name):
                ops = self.ops(plans, missing=(0,) if name == 'log_in_evidence' else ())
                if name == 'log_in_evidence':
                    ops.output = self.output  # The fake reader writes its log outside the served root.
                fired = []

                def hook(url, tamper=tamper):
                    if url == plans[0]['wire'] and tamper is not None and not fired:
                        tamper()
                        fired.append(True)
                ops.after_request = hook
                self.assertEqual(self.observer(ops, plans).run(), 1)
                rep = self.report()
                self.assertIsNone(rep['halt_reason'])
                self.assertFalse(rep['tree']['valid'])
                self.assertFalse(rep['acquisition_and_cleanup_valid'])
                if name == 'log_in_evidence':
                    self.assertFalse(rep['missing_log']['valid'])
                    self.assertFalse(rep['evidence_tree']['valid'])
                    self.assertTrue(rep['server_tree']['valid'])
                else:
                    self.assertEqual(fired, [True])
                    which = 'evidence_tree' if name.startswith('evidence') else 'server_tree'
                    self.assertFalse(rep[which]['valid'])
                if name == 'ini_mode':
                    os.chmod(os.path.join(self.server, 'resources/DATA.INI'), 0o600)

    def test_diagnostic_cap_overflow_at_startup_and_during_scan(self):
        plans = self.meta['plans'][:3]
        ops = self.ops(plans)
        startup = len(b''.join(ops.startup))
        self.assertEqual(self.observer(ops, plans, policy=dict(omd.T07_POLICY, diagnostic_bytes=startup - 1)).run(), 1)
        rep = self.report()
        self.assertEqual(rep['halt_reason'], 'diagnostic_failure')
        self.assertTrue(rep['diagnostics']['overflow'])
        self.assertEqual(ops.requests, [])
        self.assert_cleaned(ops, rep)
        ops = self.ops(plans)
        obs = self.observer(ops, plans, policy=dict(omd.T07_POLICY, diagnostic_bytes=startup + 10))
        fired = []

        def overflow(url):
            if url == plans[0]['wire'] and not fired:
                ops.proc.emit('stderr', b'x' * 64 + b'\n')
                self.wait_for(obs.diag.failed)
                fired.append(True)
        ops.after_request = overflow
        self.assertEqual(obs.run(), 1)
        rep = self.report()
        self.assertEqual(fired, [True])
        self.assertEqual(rep['halt_reason'], 'diagnostic_failure')
        self.assertEqual((rep['diagnostics']['seen_bytes']['stderr'], rep['diagnostics']['stored_bytes']['stderr']), (65, 10))
        self.assertTrue(rep['targets'][0]['attempted'])
        self.assertFalse(rep['targets'][1]['attempted'])
        self.assert_cleaned(ops, rep)

    def test_diagnostic_write_variants(self):
        plans = self.meta['plans'][:1]
        calls = []

        def short(fd, buffer):
            calls.append(len(buffer))
            return os.write(fd, bytes(buffer[:1]))
        ops = self.ops(plans)
        self.assertEqual(self.observer(ops, plans, diag_write_fn=short).run(), 0)
        self.assertTrue(any(n > 1 for n in calls))
        self.assertTrue(self.report()['diagnostics']['valid'])
        for name, fn in (('zero', lambda fd, b: 0), ('error', lambda fd, b: (_ for _ in ()).throw(OSError(errno.EIO, 'authored')))):
            with self.subTest(name):
                ops = self.ops(plans)
                self.assertEqual(self.observer(ops, plans, diag_write_fn=fn).run(), 1)
                rep = self.report()
                self.assertEqual(rep['halt_reason'], 'diagnostic_failure')
                self.assertIn('stdout_write_error', rep['diagnostics']['errors'])
                self.assertEqual(ops.requests, [])

    def test_late_eof_partial_and_duplicate_diagnostics(self):
        plans = self.meta['plans'][:2]
        line = PipedOps(self.server, self.natives).startup[1]
        for name, data in (('unterminated', b'  Valid GRF: trailing'), ('duplicate_after_scan', line),
                           ('stderr_extra', None)):
            with self.subTest(name):
                ops = self.ops(plans)
                fired = []

                def late(proc, data=data):
                    proc.emit('stderr' if data is None else 'stdout', line if data is None else data)
                    fired.append(True)
                ops.on_terminate = late
                self.assertEqual(self.observer(ops, plans).run(), 1)
                rep = self.report()
                self.assertEqual(fired, [True])
                self.assertTrue(rep['all_targets_attempted'])
                self.assertTrue(rep['cache_after']['valid'])
                self.assertEqual(rep['halt_reason'], 'diagnostic_failure')
                self.assertFalse(rep['diagnostics']['valid_grf_exact'] or rep['diagnostics']['valid'])
                self.assertTrue(rep['diagnostics']['drainers_complete'])

    def test_diagnostic_source_close_failure(self):
        plans = self.meta['plans'][:1]
        ops = self.ops(plans)
        original = ops.popen_piped
        fired = []

        class Closing:
            def __init__(self, raw):
                self.raw = raw

            def fileno(self):
                return self.raw.fileno()

            def close(self):
                self.raw.close()  # Released, but the close is reported uncertain.
                fired.append(True)
                raise OSError(errno.EIO, 'authored source close')

        def popen(argv, cwd, env):
            proc = original(argv, cwd, env)
            proc.stdout = Closing(proc.stdout)
            return proc
        ops.popen_piped = popen
        self.assertEqual(self.observer(ops, plans).run(), 1)
        rep = self.report()
        self.assertEqual(fired, [True])
        self.assertIn('stdout_source_close', rep['diagnostics']['errors'])
        self.assertEqual(rep['halt_reason'], 'diagnostic_failure')

    def test_startup_line_mismatches(self):
        plans = self.meta['plans'][:1]
        base = PipedOps(self.server, self.natives).startup
        valid = base[1:6]

        def edit(lines):
            return [base[0]] + lines + [base[-1]]
        cases = {
            'version': edit([valid[0].replace(b'0x102', b'0x200')] + valid[1:]),
            'count': edit([valid[0]] + [valid[1].replace(b' 3 files', b' 4 files')] + valid[2:]),
            'duplicate': edit([valid[0], valid[0]] + valid[1:]),
            'reordered': edit([valid[1], valid[0]] + valid[2:]),
            'extra': edit(valid + [valid[4]]),
            'one_space': edit([valid[0][1:]] + valid[1:]),
            'path': edit([valid[0].replace(self.natives[1]['path'].encode(), b'/elsewhere.gpf')] + valid[1:]),
            'missing': edit(valid[:4]),
            'unterminated_last': edit(valid[:4] + [valid[4][:-1]]),
            'split_streams': None}
        for name, lines in cases.items():
            with self.subTest(name):
                ops = self.ops(plans)
                if name == 'split_streams':
                    original = ops.popen_piped

                    def popen(argv, cwd, env):
                        ops.startup = edit(valid[:4])
                        proc = original(argv, cwd, env)
                        proc.emit('stderr', valid[4])
                        return proc
                    ops.popen_piped = popen
                else:
                    ops.startup = lines
                self.assertEqual(self.observer(ops, plans).run(), 1)
                rep = self.report()
                self.assertFalse(rep['diagnostics']['valid'] or rep['diagnostics']['valid_grf_exact'])
                if name == 'missing':
                    self.assertEqual(rep['halt_reason'], 'startup_timeout')
                elif name == 'extra':
                    # The first five rows match; the sixth line disqualifies at startup or final check.
                    self.assertIn(rep['halt_reason'], ('startup_diagnostics', 'diagnostic_failure'))
                    self.assertTrue(all(a['valid'] for a in rep['startup_archive_counts']))
                else:
                    self.assertEqual(rep['halt_reason'], 'startup_diagnostics')
                    self.assertEqual(ops.requests, [])
                if name != 'extra':
                    self.assertFalse(all(a['valid'] for a in rep['startup_archive_counts']))
                self.assertTrue(ops.proc.terminated)
                self.assert_cleaned(ops, rep)
        ops = self.ops(plans)
        ops.startup = edit([valid[0].replace(b'0x102', b'0x200')] + valid[1:])
        self.observer(ops, plans).run()
        row = self.report()['startup_archive_counts'][0]
        self.assertEqual((row['observed_version'], row['observed_count'], row['observed_path_matches'], row['valid']),
                         ('0x200', 5577, True, False))

    def test_post_popen_delayed_setup_deadline(self):
        plans = self.meta['plans'][:1]
        ops = self.ops(plans)
        fired = []

        def slow():
            ops.clock.value += omd.T07_POLICY['startup_seconds'] + 1
            fired.append(True)
        ops.getpgid_hook = slow
        self.assertEqual(self.observer(ops, plans).run(), 1)
        rep = self.report()
        self.assertEqual(fired, [True])
        self.assertEqual(rep['halt_reason'], 'startup_timeout')
        self.assertEqual(ops.requests, [])
        self.assertTrue(ops.proc.terminated)
        self.assertEqual(rep['launch']['pgid'], ops.proc.pid)
        self.assertEqual(ops.thread_names, ['diagnostics-stdout', 'diagnostics-stderr'])
        self.assert_cleaned(ops, rep)

    def test_thread_start_failure_after_popen(self):
        plans = self.meta['plans'][:1]
        for fail_at in (1, 2):
            with self.subTest(fail_at=fail_at):
                ops = self.ops(plans)
                ops.thread_fail_at = fail_at
                self.assertEqual(self.observer(ops, plans).run(), 1)
                rep = self.report()
                self.assertEqual(len(ops.thread_names), fail_at)
                self.assertEqual(rep['halt_reason'], 'diagnostic_failure')
                self.assertIn(('stdout' if fail_at == 1 else 'stderr') + '_thread_start', rep['diagnostics']['errors'])
                self.assertTrue(ops.proc.terminated)
                self.assertEqual(ops.proc.poll(), 0)
                self.assertEqual(ops.requests, [])
                self.assert_cleaned(ops, rep)

    def test_popen_failure_and_forced_kill(self):
        plans = self.meta['plans'][:1]
        ops = self.ops(plans)
        ops.popen_error = OSError(errno.ENOENT, 'authored popen failure')
        self.assertEqual(self.observer(ops, plans).run(), 1)
        rep = self.report()
        self.assertEqual(rep['halt_reason'], 'internal_failure')
        self.assertFalse(rep['diagnostics']['valid'])
        ops = self.ops(plans)
        ops.exit_mode = 'hang'
        self.assertEqual(self.observer(ops, plans).run(), 1)
        rep = self.report()
        self.assertTrue(rep['cleanup']['forced_kill'] and ops.proc.killed)
        self.assertFalse(rep['cleanup']['clean'] or rep['acquisition_and_cleanup_valid'])


if __name__ == '__main__':
    unittest.main()
