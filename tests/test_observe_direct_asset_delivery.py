"""Authored synthetic controls for tools/renewal/observe_direct_asset_delivery.py.

No listening server, network, process, guard, GET34 or real asset is used:
http.client runs over an in-memory fake socket, time is a fake clock, owner
and listener probes are fakes, and every file lives in a private temp tree.
Run: python3 -I -m unittest tests/test_observe_direct_asset_delivery.py
"""
import contextlib
import copy
import hashlib
import http.client
import importlib.util
import io
import json
import os
import shutil
import socket
import stat
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), 'tools', 'renewal', 'observe_direct_asset_delivery.py')
HEAD = 'a' * 40


def load():
    spec = importlib.util.spec_from_file_location('odad_under_test', SRC)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def sha(b):
    return hashlib.sha256(b).hexdigest()


# Synthetic twelve-query domain: names are Latin1 raw keys, never real assets.
RAW = [
    (b'data\\model\\syn\\a.rsm', 'model'),                 # 0 retained expected
    (b'data\\texture\\\xbf\xf6\\b.bmp', 'texture'),        # 1 non-ASCII
    (b'data\\texture\\\xbf\xf6\xc5\xcd/w01.jpg', 'water'),  # 2 forward slash water, non-ASCII
    (b'data\\model\\syn\\\xc7\xaea03.rsm', 'model'),       # 3 alias A
    (b'data\\model\\syn\\\xc7\xaeA03.rsm', 'model'),       # 4 alias A
    (b'data\\model\\syn\\\xc7\xaea01.rsm', 'model'),       # 5 alias B
    (b'data\\model\\syn\\\xc7\xaeA01.rsm', 'model'),       # 6 alias B
    (b'data\\model\\syn\\\xc7\xaea04.rsm', 'model'),       # 7 alias C
    (b'data\\model\\syn\\\xc7\xaeA04.rsm', 'model'),       # 8 alias C
    (b'data\\model\\syn\\amb.rsm', 'model'),               # 9 two current candidates
    (b'data\\texture\\syn\\c.bmp', 'texture'),             # 10
    (b'data\\model\\syn\\d.rsm', 'model'),                 # 11
]
SIG = {'model': b'GRSM', 'texture': b'BM', 'water': b'\xff\xd8\xff'}


def body_for(i, role):
    size = 40 + i
    return (SIG[role] + bytes([65 + i]) * size)[:size]


BODIES = [body_for(i, role) for i, (_, role) in enumerate(RAW)]
# Alias pairs share one catalog record, therefore identical bytes.
for a, b in ((3, 4), (5, 6), (7, 8)):
    BODIES[b] = BODIES[a]
RETAINED = {0}
PILOT = [0, 1, 2, 3, 4, 9]


def make_profile(mod):
    queries, relations = [], []
    for i, (raw, role) in enumerate(RAW):
        rel, wire = mod.wire_from_raw(raw)
        size = len(BODIES[i])
        relations.append({'query_index': i, 'relation_index': i, 'role': role})
        q = {'query': {'query_index': i, 'role': role, 'expected_name_hex': raw.hex(), 'relation_indices': [i],
                       'first_relation_index': i},
             'role': role, 'signature_kind': mod.ROLE_SIGNATURE[role],
             'mapping': {'raw_name_hex': raw.hex(), 'wire_target': wire, 'candidate_loose_relative_path': rel,
                         'candidate_override_relative_path': mod.override_relative(rel)},
             'metadata_real_size_range_current': [size, size],
             'full_path_candidates': [{'real_size': size}] * (2 if i == 9 else 1),
             'current_five_candidate_refs': ['/q/%d/0' % i] + (['/q/%d/1' % i] if i == 9 else []),
             'reuse_expected': None, 'new_body_expected_sha256': None}
        if i in RETAINED:
            q['reuse_expected'] = {'qualified_wire_target': wire,
                                   'retained_body': {'bytes': size, 'sha256': sha(BODIES[i])}}
        queries.append(q)
    return {'schema': mod.PROFILE_SCHEMA, 'queries': queries, 'relations': relations, 'maps': [{}, {}]}


def make_spec(mod, profile_bytes):
    sizes = [len(b) for b in BODIES]
    rem = [i for i in range(len(RAW)) if i not in PILOT]
    return {'profile_bytes': len(profile_bytes), 'profile_sha256': sha(profile_bytes),
            'queries': len(RAW), 'maps': 2, 'relations': len(RAW),
            'roles': {'model': 9, 'texture': 2, 'water': 1}, 'retained': 1, 'new': 11,
            'nonascii': 8, 'slash_water': 1, 'total_metadata_bytes': sum(sizes), 'max_body_bytes': max(sizes),
            'pilot': list(PILOT), 'pilot_metadata_bytes': sum(sizes[i] for i in PILOT),
            'remainder_count': len(rem), 'remainder_metadata_bytes': sum(sizes[i] for i in rem),
            'alias_groups': [[3, 4], [5, 6], [7, 8]], 'ambiguous_archive': [9]}


# ---- fake transport over real http.client parsing ----

class FakeRaw(io.RawIOBase):
    def __init__(self, sock, data, body_start, script):
        self.sock, self.data, self.pos, self.body_start, self.script = sock, data, 0, body_start, script
        self.yield_next = False

    def readable(self):
        return True

    def readinto(self, b):
        if self.pos >= len(self.data):
            if self.script.get('reset_at_end'):
                raise ConnectionResetError()
            return 0
        if self.yield_next:
            # Socket-like short read boundary: the buffered layer returns what it holds,
            # so an error on a later recv cannot discard bytes already handed out.
            self.yield_next = False
            return None
        if self.pos >= self.body_start:
            self.yield_next = not self.script.get('chunked')
            delay = self.script.get('delay', 0)
            if delay:
                if delay > self.sock.timeout:
                    self.sock.clock.t += self.sock.timeout
                    raise TimeoutError()
                self.sock.clock.t += delay
            if self.script.get('reset_after') is not None and self.pos - self.body_start >= self.script['reset_after']:
                raise ConnectionResetError()
            step = self.script.get('step', len(b))
        else:
            step = self.body_start - self.pos  # headers never carry body bytes in the same read
        n = min(len(b), step, len(self.data) - self.pos)
        if self.script.get('reset_after') is not None and self.pos >= self.body_start:
            n = min(n, self.body_start + self.script['reset_after'] - self.pos)
        b[:n] = self.data[self.pos:self.pos + n]
        self.pos += n
        return n


class FakeSock:
    def __init__(self, fio, wire):
        self.fio, self.clock, self.timeout, self.sent = fio, fio.clock, None, b''
        self.wire = wire

    def settimeout(self, t):
        self.timeout = t

    def sendall(self, data):
        self.sent += data

    def makefile(self, mode):
        script = self.fio.responses[self.wire]
        head, body = build(script)
        self.fio.on_response(self.wire)
        return io.BufferedReader(FakeRaw(self, head + body, len(head), script))

    def close(self):
        pass


def build(script):
    body = script['body']
    status = script.get('status', 200)
    headers = list(script.get('headers', []))
    if script.get('chunked'):
        headers.append(('Transfer-Encoding', 'chunked'))
        enc = b''
        for k in range(0, len(body), 16):
            part = body[k:k + 16]
            enc += b'%x\r\n' % len(part) + part + b'\r\n'
        if script.get('truncate_chunked') is not None:
            enc = enc[:script['truncate_chunked']]
        else:
            enc += b'0\r\n\r\n'
        body = enc
    elif script.get('declared', True) is not None:
        headers.append(('Content-Length', str(script.get('declared_value', len(script['body'])))))
    head = ('HTTP/1.1 %d X\r\n' % status + ''.join('%s: %s\r\n' % h for h in headers) + '\r\n').encode('latin-1')
    return head, body[:script['send']] if 'send' in script else body


class FakeConn(http.client.HTTPConnection):
    def __init__(self, fio, host, port, timeout):
        super().__init__(host, port, timeout=timeout)
        self.fio = fio

    def connect(self):
        self.fio.connects += 1
        self.sock = FakeSock(self.fio, self._wire)

    def putrequest(self, method, url, **kw):
        self._wire = url
        self.fio.requests.append(url)
        super().putrequest(method, url, **kw)

    def close(self):
        super().close()
        if self.fio.close_fail:
            raise OSError('close')


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


class FakeIO:
    def __init__(self, env):
        self.env, self.clock, self.requests, self.connects = env, Clock(), [], 0
        self.responses, self.events, self.after_response = {}, [], {}
        self.owner_calls, self.owner_fail_at, self.listener_fail, self.close_fail = 0, None, False, False
        self.listener_calls = 0
        self.probe_log = []

    def sleep(self, s):
        self.clock.t += s
        due = [e for e in self.events if e[0] <= self.clock.t]
        self.events = [e for e in self.events if e[0] > self.clock.t]
        for _, fn in due:
            fn()

    def connect(self, host, port, timeout):
        assert host == '127.0.0.1' and port == 33338
        return FakeConn(self, host, port, timeout)

    def on_response(self, wire):
        for fn in self.after_response.get(wire, []):
            fn()

    def owners_check(self):
        self.owner_calls += 1
        self.probe_log.append('owners')
        if self.owner_fail_at is not None and self.owner_calls >= self.owner_fail_at:
            raise self.env.mod.Fail('owner_drift')

    def listener_check(self):
        self.probe_log.append('listener')
        self.listener_calls += 1
        if self.listener_fail and self.listener_calls > 1:  # preflight passes, postcheck drifts
            raise self.env.mod.Fail('listener_drift')


def write(path, data, mode=0o600):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, 'wb') as f:
        f.write(data)
    os.chmod(path, mode)


class Env:
    """Private temporary tree, bound module slots and fake probes."""

    def __init__(self, batch='pilot', audit=None, existing=None, mutate_binding=None):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix='odad-'))
        os.chmod(self.tmp, 0o700)
        self.mod = mod = load()
        self.asset = os.path.join(self.tmp, 'assets')
        self.override = os.path.join(self.asset, '.translation')
        os.makedirs(self.override)
        self.profile_obj = make_profile(mod)
        pbytes = json.dumps(self.profile_obj).encode()
        write(os.path.join(self.tmp, 'in', 'profile.json'), pbytes)
        mod.SPEC = make_spec(mod, pbytes)
        self.domain = mod.load_domain(self.profile_obj, mod.SPEC)
        guard = b'# synthetic guard placeholder\n'
        write(os.path.join(self.tmp, 'in', 'guard.py'), guard)
        mod.GUARD_PIN = {'bytes': len(guard), 'sha256': sha(guard)}
        env = {'selected': {'CLIENT_AUTOEXTRACT': {'value': 'true'}, 'SERVER_ROOT': {'value': self.asset},
                            'HOST': {'value': '127.0.0.1'}, 'PORT': {'value': '33338'}}}
        ebytes = json.dumps(env).encode()
        write(os.path.join(self.tmp, 'in', 'env.json'), ebytes)
        write(os.path.join(self.tmp, 'native', 'server'), b'\x7fsynthetic-binary')
        ini = b'[synthetic]\n'
        write(os.path.join(self.tmp, 'native', 'DATA.INI'), ini)
        for k in range(5):
            write(os.path.join(self.tmp, 'arch', 'a%d.grf' % k), b'synthetic archive %d' % k)
        for i, data in (existing or {}).items():
            write(self.loose(i), data)
        self.out = os.path.join(self.tmp, 'out', 'run-1')
        os.makedirs(os.path.dirname(self.out))
        ident = lambda p: mod.identity(p)
        targets = []
        for row in self.domain['rows']:
            lp, op = mod.target_paths({'asset_root': self.asset, 'override_root': self.override}, row)
            targets.append({'query_index': row['index'], 'loose': mod.sample(lp), 'override': mod.sample(op)})
        self.binding = {
            'schema': mod.BINDING_SCHEMA, 'task': mod.TASK, 'head': HEAD, 'batch': batch,
            'profile': self.pin('in/profile.json'), 'pilot_audit': audit, 'environment': {'path': self.p('in/env.json')},
            'host': '127.0.0.1', 'port': 33338, 'asset_root': self.asset, 'override_root': self.override,
            'owners': {k: {'identity': {'pid': 100 + n, 'ppid': 1, 'pgid': 100 + n, 'uid': 501, 'birth': [1, n]},
                           'executable': '/synthetic/bin/' + k} for n, k in enumerate(('asset', 'vm', 'app', 'gpu'))},
            'guard': self.pin('in/guard.py'),
            'native': {'binary': {'path': self.p('native/server'), 'identity': ident(self.p('native/server'))},
                       'ini': dict(self.pin('native/DATA.INI'), identity=ident(self.p('native/DATA.INI')))},
            'archives': [{'order': k, 'path': self.p('arch/a%d.grf' % k), 'identity': ident(self.p('arch/a%d.grf' % k))}
                         for k in range(5)],
            'targets': targets, 'output': self.out}
        if mutate_binding:
            mutate_binding(self)
        self.bind(ebytes)
        self.fio = FakeIO(self)
        for i, row in enumerate(self.domain['rows']):
            self.fio.responses[row['wire']] = {'body': BODIES[i]}

    def p(self, rel):
        return os.path.join(self.tmp, rel)

    def pin(self, rel):
        with open(self.p(rel), 'rb') as f:
            data = f.read()
        return {'path': self.p(rel), 'bytes': len(data), 'sha256': sha(data)}

    def loose(self, i):
        return os.path.join(self.asset, self.domain['rows'][i]['loose_rel'])

    def wire(self, i):
        return self.domain['rows'][i]['wire']

    def bind(self, ebytes=None):
        mod = self.mod
        bbytes = json.dumps(self.binding).encode()
        bp = self.p('in/binding-%d.json' % len(os.listdir(self.p('in'))))
        write(bp, bbytes)
        mod.ROOT_ADMITTED, mod.REQUIRED_HEAD = True, HEAD
        mod.BINDING_PATH, mod.BINDING_BYTES, mod.BINDING_SHA256 = bp, len(bbytes), sha(bbytes)
        if ebytes is not None:
            mod.ENV_SELECTION_BYTES, mod.ENV_SELECTION_SHA256 = len(ebytes), sha(ebytes)

    def extract_on_response(self, i, data=None, delay=None):
        """Simulate native autoextract writing the requested spelling (inline or later)."""
        target, payload = self.loose(i), BODIES[i] if data is None else data

        def do():
            if not os.path.exists(target):
                write(target, payload)
        if delay is None:
            self.fio.after_response.setdefault(self.wire(i), []).append(do)
        else:
            self.fio.after_response.setdefault(self.wire(i), []).append(
                lambda: self.fio.events.append((self.fio.clock.t + delay, do)))

    def run(self, argv=()):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = self.mod.main(list(argv), io=self.fio)
        line = out.getvalue()
        self.stdout, self.stderr = line, err.getvalue()
        return code, json.loads(line)

    def result(self):
        with open(os.path.join(self.out, 'RESULT_ROOT.json')) as f:
            return json.load(f)

    def response(self, i):
        with open(os.path.join(self.out, 'response-%04d.json' % i)) as f:
            return json.load(f)

    def body(self, i):
        with open(os.path.join(self.out, 'body-%04d.bin' % i), 'rb') as f:
            return f.read()

    def cleanup(self):
        shutil.rmtree(self.tmp, ignore_errors=True)


class Base(unittest.TestCase):
    def env(self, **kw):
        e = Env(**kw)
        self.addCleanup(e.cleanup)
        return e

    def assertOneLine(self, e):
        self.assertEqual(e.stderr, '')
        self.assertEqual(e.stdout.count('\n'), 1)
        self.assertLessEqual(len(e.stdout.encode()), 4096)

    def assertFailedAt(self, e, i, code, attempts):
        rc, line = e.run()
        self.assertEqual(rc, 1)
        self.assertOneLine(e)
        r = e.result()
        self.assertEqual(r['first_error'], 'q%04d:%s' % (i, code))
        self.assertFalse(r['batch_complete'])
        self.assertFalse(r['delivery_complete'])
        self.assertEqual(len(e.fio.requests), attempts)
        led = r['query_ledger']
        self.assertEqual(len(led), 12)
        self.assertEqual(led[i]['attempt_state'], 'failed')
        self.assertEqual(led[i]['error'], code)
        later = [x for x in e.mod.SPEC['pilot'] if x > i]
        self.assertTrue(all(led[x]['attempt_state'] == 'not_attempted' for x in later))
        self.assertTrue(all(led[x]['observed'] is None for x in later))
        ev = e.response(i)
        self.assertEqual(ev['classification'], 'failed')
        self.assertNotEqual(ev['hash_scope'], 'complete')
        return r, ev


# ---- 1. refusal, typed domain, mapping, batches ----

class Refusals(Base):
    def test_default_import_refuses_without_io(self):
        mod = load()
        self.assertIs(mod.ROOT_ADMITTED, False)
        self.assertIsNone(mod.BINDING_PATH)
        self.assertIsNone(mod.BINDING_BYTES)
        self.assertIsNone(mod.ENV_SELECTION_BYTES)
        self.assertIsNone(mod.REQUIRED_HEAD)
        self.assertEqual(mod.BINDING_SHA256, '0' * 64)
        self.assertEqual(mod.ENV_SELECTION_SHA256, '0' * 64)

        class Trap:
            def __getattr__(self, name):
                raise AssertionError('io touched: ' + name)
        opened = []
        real_open = os.open

        def spy(*a, **k):
            opened.append(a[0])
            return real_open(*a, **k)
        out, err = io.StringIO(), io.StringIO()
        os.open = spy
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = mod.main([], io=Trap())
        finally:
            os.open = real_open
        self.assertEqual(rc, 2)
        self.assertEqual(json.loads(out.getvalue())['reason'], 'unbound')
        self.assertEqual(err.getvalue(), '')
        self.assertEqual(opened, [])

    def test_mistyped_authority_and_cli_switch_refuse(self):
        e = self.env()
        cases = [('ROOT_ADMITTED', 1, 'unbound'), ('BINDING_BYTES', True, 'unbound_binding'),
                 ('BINDING_SHA256', '0' * 64, 'unbound_binding'), ('REQUIRED_HEAD', 'A' * 40, 'unbound_head'),
                 ('ENV_SELECTION_BYTES', 1.0, 'unbound_environment'), ('BINDING_PATH', 'rel/b.json', 'unbound_binding')]
        for name, value, reason in cases:
            saved = getattr(e.mod, name)
            setattr(e.mod, name, value)
            rc, line = e.run()
            setattr(e.mod, name, saved)
            self.assertEqual((rc, line['reason']), (2, reason), name)
            self.assertFalse(os.path.lexists(e.out))
        rc, line = e.run(['--admit'])
        self.assertEqual((rc, line['reason']), (2, 'argv'))
        self.assertEqual(e.fio.requests, [])
        self.assertEqual(e.fio.probe_log, [])

    def test_binding_typed_rejections(self):
        def mutate(path, value):
            def f(env):
                obj = env.binding
                for k in path[:-1]:
                    obj = obj[k]
                obj[path[-1]] = value
            return f
        for path, value, reason in [(('port',), True, 'binding_listener'), (('port',), 33338.0, 'binding_listener'),
                                    (('extra',), 1, 'binding_keys'), (('head',), 'b' * 40, 'binding_head'),
                                    (('host',), 'localhost', 'binding_listener'),
                                    (('archives', 0, 'order'), False, 'binding_archives'),
                                    (('pilot_audit',), {'path': '/x', 'bytes': 1, 'sha256': 'a' * 64},
                                     'pilot_audit_unexpected')]:
            e = self.env(mutate_binding=mutate(path, value))
            rc, line = e.run()
            self.assertEqual((rc, line['reason']), (2, reason), path)
            self.assertFalse(os.path.lexists(e.out))
            self.assertEqual(e.fio.requests, [])

    def test_strict_json_rejects_duplicates_nonfinite(self):
        mod = load()
        for data in (b'{"a":1,"a":2}', b'{"a":NaN}', b'{"a":Infinity}', b'{"a":1e999}', b'\xff'):
            with self.assertRaises(mod.Refusal):
                mod.strict_json(data, 'x')

    def test_mapping_once_only_slash_water_alias_rows_and_batches(self):
        e = self.env()
        rows = e.domain['rows']
        self.assertEqual(rows[1]['wire'], '/data/texture/%C2%BF%C3%B6/b.bmp')
        self.assertEqual(rows[1]['loose_rel'], 'data/texture/\xbf\xf6/b.bmp')
        self.assertEqual(rows[2]['wire'], '/data/texture/%C2%BF%C3%B6%C3%85%C3%8D/w01.jpg')
        self.assertEqual(rows[2]['override_rel'], 'texture/\xbf\xf6\xc5\xcd/w01.jpg')
        self.assertNotEqual(rows[3]['wire'], rows[4]['wire'])
        self.assertEqual([r['alias_group'] for r in rows[3:9]], [[3, 4], [3, 4], [5, 6], [5, 6], [7, 8], [7, 8]])
        b = e.domain['batches']
        self.assertEqual(sorted(b['pilot'] + b['remainder']), list(range(12)))
        self.assertFalse(set(b['pilot']) & set(b['remainder']))
        mod = e.mod
        bad = []
        p = copy.deepcopy(e.profile_obj)
        p['queries'][1]['mapping']['wire_target'] = '/data/texture/%25C2%25BF%25C3%25B6/b.bmp'  # double encoded
        bad.append((p, 'wire_target'))
        p = copy.deepcopy(e.profile_obj)
        p['queries'][4]['mapping']['wire_target'] = p['queries'][4]['mapping']['wire_target'].lower()
        bad.append((p, 'wire_target'))
        p = copy.deepcopy(e.profile_obj)
        p['queries'][3]['query']['query_index'] = True
        bad.append((p, 'query_index'))
        p = copy.deepcopy(e.profile_obj)
        p['queries'][5]['metadata_real_size_range_current'] = [45, 45.0]
        bad.append((p, 'metadata_size'))
        p = copy.deepcopy(e.profile_obj)
        del p['queries'][4]
        bad.append((p, 'profile_queries'))
        p = copy.deepcopy(e.profile_obj)
        raw = b'data\\model\\..\\x.rsm'
        p['queries'][11]['query']['expected_name_hex'] = p['queries'][11]['mapping']['raw_name_hex'] = raw.hex()
        p['queries'][11]['mapping']['wire_target'] = mod.wire_from_raw(raw)[1]
        p['queries'][11]['mapping']['candidate_loose_relative_path'] = 'data/model/../x.rsm'
        bad.append((p, 'unsafe_path'))
        for prof, reason in bad:
            with self.assertRaises(mod.Refusal) as cm:
                mod.load_domain(prof, mod.SPEC)
            self.assertEqual(str(cm.exception), reason)
        spec = dict(mod.SPEC, pilot=[0, 1, 2, 3, 9])  # pilot splitting an alias pair still fails metadata pin
        with self.assertRaises(mod.Refusal):
            mod.load_domain(e.profile_obj, spec)


# ---- 2. response classification and transport failures ----

class Responses(Base):
    def test_pilot_success_expected_and_new(self):
        e = self.env()
        for i in PILOT:
            e.extract_on_response(i)
        rc, line = e.run()
        self.assertEqual(rc, 0, e.stdout)
        self.assertOneLine(e)
        r = e.result()
        self.assertTrue(r['batch_complete'] and r['delivery_complete'] and r['preservation_complete'])
        self.assertIs(r['materialization_required'], False)
        self.assertEqual(e.fio.requests, [e.wire(i) for i in PILOT])
        led = r['query_ledger']
        self.assertEqual(len(led), 12)
        self.assertEqual(led[0]['observed']['classification'], 'expected_match')
        # Correction .001: the independent pin keeps its source join (was bytes/sha256 only).
        self.assertEqual(led[0]['expected_pin'], {'bytes': len(BODIES[0]), 'sha256': sha(BODIES[0]),
                                                  'qualified_wire_target': e.wire(0),
                                                  'source_pointer': '/queries/0/reuse_expected/retained_body'})
        self.assertEqual(led[1]['observed']['classification'], 'new_observed')
        self.assertIsNone(led[1]['expected_pin'])
        self.assertEqual(led[1]['observed']['sha256'], sha(BODIES[1]))
        self.assertEqual([led[i]['attempt_state'] for i in range(12) if i not in PILOT], ['outside_batch'] * 6)
        self.assertEqual(led[3]['query'], e.profile_obj['queries'][3]['query'])
        self.assertEqual(r['counts']['succeeded'], 6)
        self.assertEqual(r['counts']['expected_match'], 1)
        self.assertEqual(r['counts']['new_observed'], 5)
        self.assertEqual(r['ambiguous_archive_queries'], e.mod.SPEC['ambiguous_archive'])
        self.assertIs(r['archive_winner_claimed'], False)
        names = sorted(os.listdir(e.out))
        expect = sorted(['BEFORE_ROOT.json', 'AFTER_ROOT.json', 'RESULT_ROOT.json'] +
                        ['response-%04d.json' % i for i in PILOT] + ['body-%04d.bin' % i for i in PILOT])
        self.assertEqual(names, expect)
        self.assertEqual(stat.S_IMODE(os.stat(e.out).st_mode), 0o700)
        self.assertTrue(all(stat.S_IMODE(os.stat(os.path.join(e.out, n)).st_mode) == 0o600 for n in names))
        for i in PILOT:
            self.assertEqual(e.body(i), BODIES[i])
            self.assertEqual(e.response(i)['hash_scope'], 'complete')
            self.assertTrue(e.response(i)['http_eof'])
        sent = e.fio.requests
        self.assertTrue(all('%25' not in w for w in sent))

    def test_expected_hash_mismatch(self):
        e = self.env()
        e.fio.responses[e.wire(0)] = {'body': b'GRSM' + b'z' * (len(BODIES[0]) - 4)}
        self.assertFailedAt(e, 0, 'expected_sha_mismatch', 1)

    def test_failure_cases(self):
        cases = [
            ({'body': b'BM' + b'q' * 10, 'chunked': True}, 'size_mismatch'),
            ({'body': b'XXXX' + BODIES[1][4:]}, 'signature_mismatch'),
            ({'body': b'missing', 'status': 404}, 'http_status'),
            ({'body': b'', 'status': 302, 'headers': [('Location', '/x')]}, 'redirect'),
            ({'body': BODIES[1], 'headers': [('Content-Encoding', 'gzip')]}, 'content_encoding'),
            ({'body': BODIES[1], 'send': 10}, 'short_body'),
            ({'body': BODIES[1], 'chunked': True, 'truncate_chunked': 30}, 'incomplete_read'),
            ({'body': BODIES[1], 'headers': [('Content-Length', '3')]}, 'conflicting_framing'),
            ({'body': BODIES[1], 'declared_value': 2 << 20}, 'declared_over_cap'),
            ({'body': BODIES[1], 'step': 1, 'delay': 4}, 'io_timeout'),
        ]
        for script, code in cases:
            with self.subTest(code=code):
                e = self.env()
                e.fio.responses[e.wire(1)] = script
                r, ev = self.assertFailedAt(e, 1, code, 2)
                self.assertEqual(r['query_ledger'][0]['attempt_state'], 'succeeded')
                if ev['body_file']:
                    sent = script['body'] if script.get('chunked') else build(script)[1]
                    self.assertTrue(sent.startswith(e.body(1)) or code == 'incomplete_read')
                    self.assertEqual(ev['sha256'], sha(e.body(1)))

    def test_streamed_oversize_and_slow_drip_deadline(self):
        e = self.env()
        e.mod.BODY_CAP = 64
        e.fio.responses[e.wire(1)] = {'body': b'BM' + b'x' * 200, 'chunked': True}
        r, ev = self.assertFailedAt(e, 1, 'body_over_cap', 2)
        self.assertEqual(len(e.body(1)), ev['bytes'])
        e = self.env()
        e.fio.responses[e.wire(1)] = {'body': BODIES[1], 'step': 1, 'delay': 2.9}
        e.fio.clock.t += 0  # 41 bytes * 2.9s exceeds the 60 s batch bound
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 1)
        self.assertIn(r['first_error'], ('q0001:deadline', 'q0001:io_timeout'))
        self.assertEqual(r['query_ledger'][2]['attempt_state'], 'not_attempted')
        self.assertEqual(e.body(1), BODIES[1][:len(e.body(1))])
        self.assertGreater(len(e.body(1)), 0)


# ---- 3. stop on first failure, sticky errors, cleanup failures ----

class Sticky(Base):
    def test_second_interrupted_third_not_attempted_no_replay(self):
        e = self.env()
        e.mod.SPEC['pilot'] = None  # replaced below with a three-request pilot
        spec = make_spec(e.mod, json.dumps(e.profile_obj).encode())
        e.mod.SPEC = dict(spec, pilot=[0, 1, 10], pilot_metadata_bytes=sum(len(BODIES[i]) for i in (0, 1, 10)),
                          remainder_count=9,
                          remainder_metadata_bytes=sum(len(BODIES[i]) for i in range(12) if i not in (0, 1, 10)))
        e.bind()
        e.fio.responses[e.wire(1)] = {'body': BODIES[1], 'reset_after': 7}
        rc, _ = e.run()
        self.assertEqual(rc, 1)
        r = e.result()
        self.assertEqual(e.fio.requests, [e.wire(0), e.wire(1)])
        self.assertEqual(e.fio.connects, 2)
        self.assertEqual(r['first_error'], 'q0001:transport')
        self.assertEqual([r['query_ledger'][i]['attempt_state'] for i in (0, 1, 10)],
                         ['succeeded', 'failed', 'not_attempted'])
        self.assertEqual(e.body(1), BODIES[1][:7])
        self.assertEqual(e.response(1)['hash_scope'], 'prefix')
        self.assertFalse(e.response(1)['http_eof'])
        self.assertFalse(os.path.exists(os.path.join(e.out, 'response-0010.json')))
        self.assertEqual(r['counts']['attempted'], 2)

    def test_postcheck_failure_keeps_first_error(self):
        e = self.env()
        e.fio.responses[e.wire(1)] = {'body': BODIES[1], 'reset_after': 5}
        e.fio.listener_fail = True
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 1)
        self.assertEqual(r['first_error'], 'q0001:transport')
        self.assertIn('listener_drift', r['postcheck_errors'])
        self.assertFalse(r['preservation_complete'])

    def test_postcheck_only_failure_is_not_success(self):
        e = self.env()
        e.fio.listener_fail = True
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 1)
        self.assertTrue(r['delivery_complete'])
        self.assertFalse(r['batch_complete'])
        self.assertEqual(r['first_error'], 'listener_drift')

    def test_close_failure_fails(self):
        e = self.env()
        e.fio.close_fail = True
        self.assertFailedAt(e, 0, 'close_failed', 1)

    def test_write_failure_fails(self):
        e = self.env()
        real = e.mod.write_new

        def fail(directory, name, data):
            if name == 'response-0001.json':
                raise OSError('disk')
            return real(directory, name, data)
        e.mod.write_new = fail
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 1)
        self.assertEqual(r['first_error'], 'q0001:write_failed')
        self.assertEqual(r['query_ledger'][1]['attempt_state'], 'failed')
        self.assertEqual(e.body(1), BODIES[1])


# ---- 4. materialization ----

class Materialization(Base):
    def state(self, r, i):
        return r['query_ledger'][i]['materialization']

    def test_absent_to_matching_and_stable_absent(self):
        e = self.env()
        e.extract_on_response(0, delay=0.3)
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 0)
        m0 = self.state(r, 0)
        self.assertEqual(m0['state'], 'matched_new')
        self.assertGreater(m0['polls'], 1)
        self.assertEqual(self.state(r, 1)['state'], 'absent')
        self.assertTrue(r['delivery_complete'])
        self.assertFalse(r['materialization_complete'])
        self.assertEqual(self.state(r, 10)['state'], 'not_observed')
        self.assertEqual(r['query_ledger'][10]['observed'], None)

    def test_torn_to_matching_and_final_mismatch(self):
        e = self.env()
        e.extract_on_response(1, data=BODIES[1][:5])
        e.fio.after_response[e.wire(1)].append(
            lambda: e.fio.events.append((e.fio.clock.t + 0.2, lambda: write(e.loose(1), BODIES[1]))))
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 0)
        self.assertEqual(self.state(r, 1)['state'], 'matched_new')
        e = self.env()
        e.extract_on_response(1, data=BODIES[1][:5])
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 1)
        self.assertEqual(self.state(r, 1)['state'], 'mismatch')
        self.assertTrue(r['delivery_complete'])
        self.assertFalse(r['preservation_complete'])
        self.assertIn('q0001:materialization_mismatch', r['postcheck_errors'])

    def test_final_unsteady(self):
        e = self.env()
        e.extract_on_response(2)
        real = e.mod._steady_read
        target = e.loose(2)

        def torn(fd, path):
            data = real(fd, path)
            if path == target:
                os.utime(path, ns=(1, os.stat(path).st_mtime_ns + 1000))
            return data
        e.mod._steady_read = torn
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 1)
        self.assertEqual(self.state(r, 2)['state'], 'unsteady')
        self.assertEqual(r['first_error'], 'q0002:materialization_unsteady')

    def test_existing_unchanged_and_mutation(self):
        e = self.env(existing={0: BODIES[0], 10: b'BM-outside'})
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 0, e.stdout)
        self.assertEqual(self.state(r, 0)['state'], 'unchanged')
        e = self.env(existing={0: BODIES[0], 10: b'BM-outside'})
        e.fio.after_response.setdefault(e.wire(1), []).append(lambda: write(e.loose(10), b'BM-changed'))
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 1)
        self.assertIn('q0010:existing_mutation', r['postcheck_errors'])
        self.assertFalse(r['preservation_complete'])
        e = self.env(existing={0: BODIES[0]})
        e.fio.after_response.setdefault(e.wire(0), []).append(lambda: write(e.loose(0), BODIES[0][:-1] + b'!'))
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 1)
        self.assertEqual(self.state(r, 0)['state'], 'mismatch')

    def test_case_alias_rows_kept_separate(self):
        e = self.env()
        e.extract_on_response(3)
        e.extract_on_response(4)  # skipped by os.path.exists on a case-insensitive volume
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 0, e.stdout)
        self.assertEqual(e.fio.requests.count(e.wire(3)), 1)
        self.assertEqual(e.fio.requests.count(e.wire(4)), 1)
        s3, s4 = self.state(r, 3)['state'], self.state(r, 4)['state']
        insensitive = os.path.samefile(e.loose(3), e.loose(4))
        if insensitive:
            self.assertEqual((s3, s4), ('shared_alias', 'shared_alias'))
        else:
            self.assertEqual((s3, s4), ('matched_new', 'matched_new'))
        self.assertEqual(r['query_ledger'][3]['alias_group'], [3, 4])
        self.assertNotEqual(r['query_ledger'][3]['wire_target'], r['query_ledger'][4]['wire_target'])


# ---- 5. authority, budgets, drift, unsafe paths, collision ----

class Authority(Base):
    def audit(self, env, **over):
        a = {'schema': env.mod.PILOT_AUDIT_SCHEMA, 'task': env.mod.TASK, 'auditor': 'Root', 'batch': 'pilot',
             'pilot_result_pin': {'bytes': 1, 'sha256': 'b' * 64}, 'pilot_query_indices': list(PILOT),
             'pilot_response_bytes': env.mod.SPEC['pilot_metadata_bytes'], 'admit_remainder': True}
        a.update(over)
        return a

    def remainder_env(self, audit_obj=None, name='audit.json'):
        holder = {}

        def mut(env):
            obj = self.audit(env) if audit_obj is None else audit_obj(env)
            data = json.dumps(obj).encode()
            write(env.p('in/' + name), data)
            env.binding['pilot_audit'] = env.pin('in/' + name)
            holder['ok'] = True
        return self.env(batch='remainder', mutate_binding=mut)

    def test_remainder_requires_root_audit_and_skips_pilot(self):
        e = self.remainder_env()
        rc, _ = e.run()
        self.assertEqual(rc, 0, e.stdout)
        rem = [i for i in range(12) if i not in PILOT]
        self.assertEqual(e.fio.requests, [e.wire(i) for i in rem])
        r = e.result()
        self.assertEqual(r['counts']['cumulative_response_bytes'],
                         e.mod.SPEC['pilot_metadata_bytes'] + e.mod.SPEC['remainder_metadata_bytes'])
        self.assertTrue(all(r['query_ledger'][i]['attempt_state'] == 'outside_batch' for i in PILOT))

    def test_remainder_authority_refusals(self):
        e = self.env(batch='remainder')
        rc, line = e.run()
        self.assertEqual((rc, line['reason']), (2, 'pilot_audit_missing'))
        for maker, reason in [
                (lambda env: dict(self.audit(env), schema=env.mod.RESULT_SCHEMA), 'pilot_audit'),
                (lambda env: dict(self.audit(env), auditor='candidate'), 'pilot_audit'),
                (lambda env: dict(self.audit(env), pilot_query_indices=PILOT[:-1]), 'pilot_audit'),
                (lambda env: dict(self.audit(env), pilot_response_bytes=True), 'pilot_audit'),
                (lambda env: dict(self.audit(env), extra=1), 'pilot_audit')]:
            e = self.remainder_env(maker)
            rc, line = e.run()
            self.assertEqual((rc, line['reason']), (2, reason))
            self.assertEqual(e.fio.requests, [])
        e = self.remainder_env(name='RESULT_ROOT.json')
        rc, line = e.run()
        self.assertEqual((rc, line['reason']), (2, 'pilot_audit_self'))
        e = self.remainder_env()
        with open(e.binding['pilot_audit']['path'], 'ab') as f:
            f.write(b' ')
        rc, line = e.run()
        self.assertEqual((rc, line['reason']), (2, 'pilot_audit_pin'))

    def test_cumulative_byte_boundary(self):
        e = self.remainder_env()
        rem = [i for i in range(12) if i not in PILOT]
        e.mod.AGGREGATE_CAP = e.mod.SPEC['pilot_metadata_bytes'] + e.mod.SPEC['remainder_metadata_bytes']
        rc, _ = e.run()
        self.assertEqual(rc, 0)
        e = self.remainder_env()
        e.mod.AGGREGATE_CAP = e.mod.SPEC['pilot_metadata_bytes'] + e.mod.SPEC['remainder_metadata_bytes'] - 1
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 1)
        self.assertEqual(r['first_error'], 'q%04d:aggregate_cap' % rem[-1])
        self.assertEqual(e.body(rem[-1]), BODIES[rem[-1]][:len(e.body(rem[-1]))])

    def test_owner_drift_mid_run_stops(self):
        e = self.env()
        e.fio.owner_fail_at = 3  # preflight=1, request0=2, request1=3
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 1)
        self.assertEqual(r['first_error'], 'owner_drift')
        self.assertEqual(e.fio.requests, [e.wire(0)])
        self.assertEqual(r['query_ledger'][1]['attempt_state'], 'not_attempted')

    def test_preflight_drift_refuses_without_output(self):
        for what in ('archive', 'ini', 'owner', 'target', 'env'):
            with self.subTest(what=what):
                e = self.env()
                if what == 'archive':
                    write(e.p('arch/a3.grf'), b'synthetic archive 3 changed')
                elif what == 'ini':
                    write(e.p('native/DATA.INI'), b'[changed]\n')
                elif what == 'owner':
                    e.fio.owner_fail_at = 1
                elif what == 'target':
                    write(e.loose(11), b'GRSM-appeared')
                else:
                    write(e.p('in/env.json'), b'{}')
                rc, line = e.run()
                self.assertEqual(rc, 2, line)
                self.assertFalse(os.path.lexists(e.out))
                self.assertEqual(e.fio.requests, [])

    def test_postcheck_archive_parent_source_drift(self):
        e = self.env()
        e.fio.after_response.setdefault(e.wire(0), []).append(
            lambda: write(e.p('arch/a1.grf'), b'synthetic archive 1 changed'))
        rc, _ = e.run()
        self.assertEqual(rc, 1)
        self.assertIn('archive_drift', e.result()['postcheck_errors'])
        e = self.env()
        e.fio.after_response.setdefault(e.wire(0), []).append(lambda: os.chmod(e.asset, 0o750))
        rc, _ = e.run()
        self.assertEqual(rc, 1)
        self.assertIn('parent_drift', e.result()['postcheck_errors'])
        e = self.env()
        copy_src = e.p('in/source_copy.py')
        shutil.copyfile(SRC, copy_src)
        e.mod.source_path = lambda: copy_src
        e.fio.after_response.setdefault(e.wire(0), []).append(lambda: write(copy_src, open(SRC, 'rb').read() + b'#\n'))
        rc, _ = e.run()
        self.assertEqual(rc, 1)
        self.assertIn('source_drift', e.result()['postcheck_errors'])

    def test_unsafe_targets_and_output_collision(self):
        e = self.env()
        os.makedirs(os.path.dirname(e.loose(11)), exist_ok=True)
        os.symlink(e.p('in/guard.py'), e.loose(11))
        rc, line = e.run()
        self.assertEqual((rc, line['reason']), (2, 'unsafe_or_unsteady_target'))
        e = self.env(existing={11: BODIES[11]})
        os.link(e.loose(11), e.p('in/hardlink'))
        rc, line = e.run()
        self.assertEqual((rc, line['reason']), (2, 'unsafe_or_unsteady_target'))
        e = self.env()
        os.makedirs(e.out)
        write(os.path.join(e.out, 'keep.txt'), b'prior')
        rc, line = e.run()
        self.assertEqual((rc, line['reason']), (2, 'output_exists'))
        self.assertEqual(os.listdir(e.out), ['keep.txt'])
        self.assertEqual(e.fio.requests, [])


# ---- correction T07.007.014.011.001 (Root-executed defects and supplement cases) ----

class PairIO(FakeIO):
    """Real blocking stdlib HTTP over an owned in-process AF_UNIX socketpair; no TCP or listener.

    The authored response for the requested wire is written on the peer end, which is then
    closed (Connection: close), so http.client reads with ordinary socket buffering.
    """

    def __init__(self, env, wires, response_class=None):
        super().__init__(env)
        self.wires, self.response_class, self.owned = wires, response_class, []

    def connect(self, host, port, timeout):
        assert host == '127.0.0.1' and port == 33338
        fio = self

        class PairConn(http.client.HTTPConnection):
            def connect(self):
                raise AssertionError('no real connect')

            def putrequest(self, method, url, **kw):
                self._wire = url
                fio.requests.append(url)
                super().putrequest(method, url, **kw)

            def getresponse(self):
                fio.on_response(self._wire)
                self._peer.sendall(fio.wires[self._wire])
                self._peer.close()
                return super().getresponse()

        conn = PairConn(host, port, timeout=timeout)
        if self.response_class is not None:
            conn.response_class = self.response_class
        left, right = socket.socketpair(socket.AF_UNIX, socket.SOCK_STREAM)
        conn.sock, conn._peer = left, right
        self.owned.append((left, right))
        return conn


def http_close(body, extra=b''):
    return b'HTTP/1.1 200 OK\r\nContent-Length: %d\r\nConnection: close\r\n%s\r\n' % (len(body), extra) + body


class Correction(Base):
    def pair(self, e, wires=None, response_class=None):
        wires = wires or {e.wire(i): http_close(BODIES[i]) for i in range(12)}
        e.fio = PairIO(e, wires, response_class)
        e.fio.responses = {}
        self.addCleanup(lambda: [s.close() for pair in e.fio.owned for s in pair])
        return e.fio

    def assertOwnedClosed(self, fio):
        self.assertTrue(fio.owned)
        for left, right in fio.owned:
            self.assertEqual((left.fileno(), right.fileno()), (-1, -1))
            self.assertEqual(left._io_refs, 0)  # makefile reference released: real close happened

    def test_complete_content_length_close_af_unix_accepted(self):
        # Root defect 1: complete CL + Connection: close was rejected as transport.
        e = self.env()
        fio = self.pair(e)
        for i in PILOT:
            e.extract_on_response(i)
        rc, line = e.run()
        self.assertEqual(rc, 0, e.stdout)
        self.assertOneLine(e)
        r = e.result()
        self.assertTrue(r['batch_complete'])
        self.assertIsNone(r['first_error'])
        for i in PILOT:
            ev = e.response(i)
            self.assertEqual((ev['bytes'], ev['sha256'], ev['hash_scope'], ev['http_eof'], ev['error']),
                             (len(BODIES[i]), sha(BODIES[i]), 'complete', True, None))
            self.assertEqual(e.body(i), BODIES[i])
        self.assertEqual(r['counts']['batch_response_bytes'], sum(len(BODIES[i]) for i in PILOT))
        self.assertEqual(fio.requests, [e.wire(i) for i in PILOT])
        self.assertOwnedClosed(fio)

    def test_chunked_complete_and_short_over_af_unix(self):
        e = self.env()
        body = BODIES[0]
        chunked = (b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n'
                   + b''.join(b'%x\r\n' % len(body[k:k + 16]) + body[k:k + 16] + b'\r\n'
                              for k in range(0, len(body), 16)) + b'0\r\n\r\n')
        wires = {e.wire(i): http_close(BODIES[i]) for i in range(12)}
        wires[e.wire(0)] = chunked
        wires[e.wire(1)] = http_close(BODIES[1])[:-5]  # declared length, peer closes early
        fio = self.pair(e, wires)
        rc, _ = e.run()
        self.assertEqual(rc, 1)
        self.assertEqual(e.response(0)['classification'], 'expected_match')
        ev = e.response(1)
        self.assertEqual(e.result()['first_error'], 'q0001:short_body')
        self.assertEqual((ev['bytes'], ev['sha256'], ev['hash_scope']),
                         (len(BODIES[1]) - 5, sha(BODIES[1][:-5]), 'prefix'))
        self.assertEqual(e.body(1), BODIES[1][:-5])
        self.assertEqual(fio.requests, [e.wire(0), e.wire(1)])
        self.assertOwnedClosed(fio)

    def test_incomplete_read_partial_bytes_retained(self):
        # Root defect 2: IncompleteRead.partial exposed 16 bytes but evidence/storage kept 0.
        e = self.env()
        first = BODIES[1][:16]
        wires = {e.wire(i): http_close(BODIES[i]) for i in range(12)}
        wires[e.wire(1)] = (b'HTTP/1.1 200 OK\r\nTransfer-Encoding: chunked\r\nConnection: close\r\n\r\n'
                            b'10\r\n' + first + b'\r\n20\r\ncut')
        fio = self.pair(e, wires)
        r, ev = self.assertFailedAt(e, 1, 'incomplete_read', 2)
        self.assertEqual((ev['bytes'], ev['sha256'], ev['hash_scope'], ev['http_eof']),
                         (16, sha(first), 'prefix', False))
        self.assertEqual(ev['prefix_hex'], first.hex())
        self.assertEqual(e.body(1), first)
        self.assertEqual(r['counts']['batch_response_bytes'], len(BODIES[0]) + 16)
        self.assertOwnedClosed(fio)

    def test_bytes_returned_at_deadline_retained(self):
        # Root defect 3: a read returned bytes, then the deadline check dropped them.
        e = self.env()
        fio = None

        class LateResponse(http.client.HTTPResponse):
            def read(self, amt=None):
                b = super().read(amt)
                fio.clock.t += e.mod.BATCH_SECONDS + 1
                return b
        fio = self.pair(e, response_class=LateResponse)
        r, ev = self.assertFailedAt(e, 0, 'deadline', 1)
        self.assertEqual((ev['bytes'], ev['sha256'], ev['hash_scope']), (len(BODIES[0]), sha(BODIES[0]), 'prefix'))
        self.assertEqual(e.body(0), BODIES[0])
        self.assertEqual(r['counts']['cumulative_response_bytes'], len(BODIES[0]))
        self.assertIn('deadline', r['postcheck_errors'])
        self.assertOwnedClosed(fio)

    def test_unchanged_maps_relations_records_and_provenance(self):
        e = self.env()
        for i in PILOT:
            e.extract_on_response(i)
        rc, _ = e.run()
        self.assertEqual(rc, 0, e.stdout)
        r = e.result()
        self.assertEqual(r['maps_unchanged'], e.profile_obj['maps'])
        self.assertEqual(r['relations_unchanged'], e.profile_obj['relations'])
        self.assertEqual([x['profile_record'] for x in r['query_ledger']], e.profile_obj['queries'])
        self.assertEqual([x['query'] for x in r['query_ledger']], [q['query'] for q in e.profile_obj['queries']])
        self.assertEqual(r['domain_provenance']['profile_pin'], r['profile_pin'])
        self.assertEqual(r['query_ledger'][9]['profile_record']['current_five_candidate_refs'],
                         ['/q/9/0', '/q/9/1'])
        self.assertIs(r['archive_winner_claimed'], False)
        led = r['query_ledger']
        self.assertEqual(led[1]['observed']['sha256'], sha(BODIES[1]))
        self.assertIsNone(led[1]['expected_pin'])

    def test_absent_target_turns_unsafe_before_get_stops(self):
        e = self.env()
        e.fio.after_response.setdefault(e.wire(0), []).append(
            lambda: (os.makedirs(os.path.dirname(e.loose(1)), exist_ok=True),
                     os.symlink(e.p('in/guard.py'), e.loose(1))))
        rc, _ = e.run()
        self.assertEqual(rc, 1)
        r = e.result()
        self.assertEqual(e.fio.requests, [e.wire(0)])
        self.assertEqual(r['first_error'], 'q0001:unsafe_or_unsteady_target')
        self.assertEqual(r['query_ledger'][1]['attempt_state'], 'not_attempted')
        self.assertTrue(os.path.exists(os.path.join(e.out, 'AFTER_ROOT.json')))

    def test_stable_preexisting_new_row_differs_from_response(self):
        a = BODIES[1][:2] + b'Z' * (len(BODIES[1]) - 2)  # same size, valid BM signature, other bytes
        e = self.env(existing={1: a})
        for i in PILOT:
            if i != 1:
                e.extract_on_response(i)
        rc, _ = e.run()
        self.assertEqual(rc, 1)
        r = e.result()
        m = r['query_ledger'][1]['materialization']
        self.assertEqual(m['state'], 'mismatch')
        self.assertEqual(r['query_ledger'][1]['observed']['classification'], 'new_observed')
        self.assertTrue(r['delivery_complete'])
        self.assertFalse(r['materialization_complete'] or r['batch_complete'])
        self.assertIn('q0001:materialization_mismatch', r['postcheck_errors'])
        with open(e.loose(1), 'rb') as f:
            self.assertEqual(f.read(), a)
        e = self.env(existing={1: BODIES[1]})  # control: stable bytes equal to the response
        for i in PILOT:
            if i != 1:
                e.extract_on_response(i)
        rc, _ = e.run()
        self.assertEqual(rc, 0, e.stdout)
        self.assertEqual(e.result()['query_ledger'][1]['materialization']['state'], 'unchanged')

    def test_final_probe_exceptions_keep_final_evidence(self):
        import subprocess
        e = self.env()
        e.fio.responses[e.wire(1)]['status'] = 404
        calls = []

        def listener():
            calls.append(1)
            if len(calls) > 1:
                raise subprocess.TimeoutExpired(['lsof'], 3)
        e.fio.listener_check = listener
        e.fio.after_response.setdefault(e.wire(0), []).append(lambda: write(e.p('arch/a2.grf'), b'drifted'))
        rc, _ = e.run()
        self.assertEqual(rc, 1)
        self.assertOneLine(e)
        r = e.result()
        self.assertEqual(r['first_error'], 'q0001:http_status')
        self.assertIn('listener_probe_error:TimeoutExpired', r['postcheck_errors'])
        self.assertIn('archive_drift', r['postcheck_errors'])  # later independent check still ran
        self.assertEqual(len(r['query_ledger']), 12)
        self.assertTrue(os.path.exists(os.path.join(e.out, 'AFTER_ROOT.json')))

        e = self.env()
        n = []

        def owners():
            n.append(1)
            if len(n) == 3:  # preflight, q0, then q1 probe raises
                raise OSError('probe')
        e.fio.owners_check = owners
        rc, _ = e.run()
        self.assertEqual(rc, 1)
        r = e.result()
        self.assertEqual(r['first_error'], 'owners_probe_error:OSError')
        self.assertEqual(e.fio.requests, [e.wire(0)])

        e = self.env()
        n = []

        def interrupt():
            n.append(1)
            if len(n) == 2:
                raise KeyboardInterrupt()
        e.fio.owners_check = interrupt
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertRaises(KeyboardInterrupt, e.mod.main, [], e.fio)

    def test_deadline_after_publication_overrides_written_candidate(self):
        e = self.env()
        for i in PILOT:
            e.extract_on_response(i)
        real = e.mod.write_new

        def slow_result(directory, name, data):
            real(directory, name, data)
            if name == 'RESULT_ROOT.json':
                e.fio.clock.t += e.mod.BATCH_SECONDS
        e.mod.write_new = slow_result
        rc, line = e.run()
        self.assertEqual(rc, 1)
        self.assertOneLine(e)
        self.assertEqual((line['status'], line['first_error'], line['deadline_after_publication'],
                          line['batch_complete']), ('failed', 'deadline_after_publication', True, False))
        r = e.result()
        self.assertTrue(r['batch_complete'])  # earlier candidate JSON; stdout/exit are authoritative
        self.assertIn('stdout, exit and Root outer audit are final', r['verdict_authority'])

    def test_default_refusal_still_no_io(self):
        mod = load()

        class Trap:
            def __getattr__(self, name):
                raise AssertionError('io touched: ' + name)
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            self.assertEqual(mod.main([], io=Trap()), 2)
        self.assertEqual(json.loads(out.getvalue())['reason'], 'unbound')


if __name__ == '__main__':
    unittest.main()
