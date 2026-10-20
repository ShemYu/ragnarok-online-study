"""Authored controls and fake-object lifecycle tests for observe_map_dependencies.

No native binary/GRF/asset bodies, real process launch, HTTP or game/browser
state are touched. Tiny private files live under this checkout's
.tools/renewal (0700 directories/0600 files). The full metadata preflight
reads the canonical input root (OBSERVE_INPUT_ROOT overrides the default).
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
INPUT_ROOT = os.environ.get('OBSERVE_INPUT_ROOT',
                            '/Users/shem/orca/workspaces/game-reverse-engineering/reverse-the-Ragnarok-Online-to-play-by-myself')
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


if __name__ == '__main__':
    unittest.main()
