"""Authored synthetic controls for tools/renewal/observe_nested_texture_delivery.py.

No listening server, network, process, guard or real asset is used: the fake
http.client transport, clock and probes are reused unchanged from the
protected tests/test_observe_direct_asset_delivery.py, and every file lives in
a private temp tree. Run with TMPDIR inside the private evidence prefix:
TMPDIR=<prefix>/tmp python3 -I -B -m unittest tests/test_observe_nested_texture_delivery.py

Optional whole-profile control (read-only, no main(), no I/O beyond one pinned
read): set T07_014_017_PROFILE to the pinned PROFILE_ROOT.json path. Without it
that class is simply not defined, so the default run has no skips.
"""
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import os
import shutil
import stat
import tempfile
import unittest
from urllib.parse import quote

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(os.path.dirname(HERE), 'tools', 'renewal', 'observe_nested_texture_delivery.py')
HEAD = 'a' * 40


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def load():
    return _load(SRC, 'ontd_under_test')


# Reuse the protected direct suite's transport/clock/probe doubles; that file is not edited.
_direct = _load(os.path.join(HERE, 'test_observe_direct_asset_delivery.py'), 'odad_doubles')
FakeIO, build, write = _direct.FakeIO, _direct.build, _direct.write


class SteadyRaw(_direct.FakeRaw):
    """Opt-in ('steady' script key) blocking-socket reads for bodies over one 64 KiB read.

    The protected double alternates a None short read, which http.client's readinto
    treats as EOF after the first buffered chunk; a blocking socket never returns None.
    """

    def readinto(self, b):
        n = super().readinto(b)
        if self.script.get('steady'):
            self.yield_next = False
        return n


_direct.FakeRaw = SteadyRaw  # this process only; the protected file is unchanged


def sha(b):
    return hashlib.sha256(b).hexdigest()


# Synthetic 13-query nested texture domain; Latin1 raw keys, never real assets.
RAW = [
    b'data\\texture\\syn\\a.tga',                          # 0 tga pilot
    b'data\\texture\\\xbf\xf6\\b.bmp',                     # 1 non-ASCII pilot
    b'data\\texture\\syn\\r.bmp',                          # 2 reuse-only
    b'data\\texture\\syn\\ver.BMP',                        # 3 case pair (upper)
    b'data\\texture\\syn\\ver.bmp',                        # 4 case pair (lower)
    b'data\\texture\\\xc7\xc1\\gid..down(side).bmp',       # 5 parentheses
    b'data\\texture\\\xc7\xc1\\gid..(side).bmp',           # 6 parentheses
    b'data\\texture\\syn\\amb.bmp',                        # 7 two current archive candidates
    b'data\\texture\\syn\\big.bmp',                        # 8 larger than the old 1 MiB body cap
    b'data\\texture\\syn\\c.TGA',                          # 9 upper TGA remainder
    b'data\\texture\\syn\\r2.bmp',                         # 10 reuse-only inside remainder range
    b'data\\texture\\syn\\d.bmp',                          # 11
    b'data\\texture\\syn\\multi.bmp',                      # 12 used by two relations/maps
]
REUSE = [2, 10]
PILOT = [0, 1, 3, 4, 5, 6, 7]
REMAINDER = [8, 9, 11, 12]
POLICY = {'bmp': 'bmp', 'BMP': 'bmp', 'tga': 'not_checked_tga', 'TGA': 'not_checked_tga'}
BIG = (1 << 20) + (1 << 19)


def ext(raw):
    return raw.decode('latin-1').rpartition('.')[2]


def body_for(i):
    size = BIG if i == 8 else 40 + i
    # TGA bodies deliberately start with arbitrary bytes: no magic claim is made for them.
    head = b'BM' if POLICY[ext(RAW[i])] == 'bmp' else b'\x00\x00\x02'
    return (head + bytes([65 + i]) * size)[:size]


BODIES = [body_for(i) for i in range(len(RAW))]
BODIES[4] = BODIES[3]  # case pair shares one metadata row, therefore identical bytes


def encode(raw):
    """Independent Root-style mapping: Latin1 -> slash path -> UTF-8 percent once per segment."""
    slash = raw.decode('latin-1').replace('\\', '/')
    return slash, '/' + '/'.join(quote(s, safe="-_.!~*'()") for s in slash.split('/'))


def make_profile():
    queries, relations = [], []
    for i, raw in enumerate(RAW):
        slash, wire = encode(raw)
        size = len(BODIES[i])
        rel_idx = [i] if i != 12 else [12, 13]
        query = {'query_index': i, 'role': 'texture', 'expected_name_hex': raw.hex(),
                 'raw_request_latin1': raw.decode('latin-1'), 'http_path': wire[1:], 'wire_target': wire,
                 'relation_indices': rel_idx, 'first_relation_index': rel_idx[0],
                 'aggregate_target_pointer': '/targets/%d' % i}
        cands = 2 if i == 7 else 1
        q = {'query': query, 'role': 'texture', 'signature_kind': POLICY[ext(raw)],
             'mapping': {'raw_name_hex': raw.hex(), 'latin1_name': raw.decode('latin-1'), 'slash_name': slash,
                         'wire_target': wire, 'http_path_encoded_once': wire[1:],
                         'candidate_loose_relative_path': slash, 'candidate_override_relative_path': slash[5:],
                         'candidate_loose_absolute_path': '/inert/should/never/be/read/' + slash,
                         'filesystem_observed': False, 'native_extraction_path_verified': False},
             'full_path_candidates': [{'real_size': size, 'source_pointer': '/q/%d/%d' % (i, k)}
                                      for k in range(cands)],
             'current_five_candidate_refs': ['/q/%d/%d' % (i, k) for k in range(cands)],
             'metadata_real_size_range_current': [size, size], 'metadata_real_size_range_all': [size, size],
             'reuse_expected': None, 'new_body_expected_sha256': None, 'new_body_observed_pin': None,
             'normal_delivery_verified': i in REUSE,
             'lookup_full_query_observation': {'query': copy.deepcopy(query), 'full_path_occurrences': [{'k': i}],
                                               'basename_only_occurrences': []},
             'archive_winner_proved': False}
        if i in REUSE:
            q['reuse_expected'] = {'qualified_wire_target': wire, 'no_new_GET': True, 'original_query_index': 900 + i,
                                   'retained_body': {'bytes': size, 'sha256': sha(BODIES[i]),
                                                     'path': '/inert/prior/body-%04d.bin' % i}}
        queries.append(q)
    for r in range(14):
        relations.append({'relation_index': r, 'map_index': r % 2})
    new = [i for i in range(len(RAW)) if i not in REUSE]
    return {'schema': 't07-014-017-normal-nested-texture-preparation-v1', 'queries': queries,
            'relations': relations, 'maps': [{'map_index': 0}, {'map_index': 1}],
            'catalogs': [{'inert': '/inert/catalog'}],
            'batches': {'reuse_only_indices': list(REUSE), 'request_indices': new, 'pilot_indices': list(PILOT),
                        'remainder_indices': list(REMAINDER)},
            'preserved_casefold_query_groups': [[3, 4]], 'preserved_parentheses_query_indices': [5, 6],
            'ambiguous_archive_queries': [7]}


def make_spec(profile_bytes):
    sizes = [len(b) for b in BODIES]
    new = [i for i in range(len(RAW)) if i not in REUSE]
    count = lambda ids: {e: sum(1 for i in ids if ext(RAW[i]) == e) for e in sorted({ext(RAW[i]) for i in ids})}
    return {'profile_bytes': len(profile_bytes), 'profile_sha256': sha(profile_bytes),
            'queries': len(RAW), 'maps': 2, 'relations': 14, 'roles': {'texture': len(RAW)},
            'extensions': count(range(len(RAW))), 'new_extensions': count(new),
            'reuse': list(REUSE), 'reused_metadata_bytes': sum(sizes[i] for i in REUSE),
            'new': len(new), 'new_metadata_bytes': sum(sizes[i] for i in new), 'nonascii': 3,
            'total_metadata_bytes': sum(sizes), 'max_body_bytes': max(sizes),
            'pilot': list(PILOT), 'pilot_metadata_bytes': sum(sizes[i] for i in PILOT),
            'remainder_count': len(REMAINDER), 'remainder_metadata_bytes': sum(sizes[i] for i in REMAINDER),
            'alias_groups': [[3, 4]], 'parentheses': [5, 6], 'ambiguous_archive': [7]}


class Env:
    """Private temporary tree (under TMPDIR), bound module slots and the reused fake probes."""

    def __init__(self, batch='pilot', mutate_binding=None, existing=None):
        self.tmp = os.path.realpath(tempfile.mkdtemp(prefix='ontd-'))
        os.chmod(self.tmp, 0o700)
        self.mod = mod = load()
        self.asset = os.path.join(self.tmp, 'assets')
        self.override = os.path.join(self.asset, '.translation', 'data')
        os.makedirs(self.override)
        self.profile_obj = make_profile()
        pbytes = json.dumps(self.profile_obj).encode()
        write(self.p('in/profile.json'), pbytes)
        mod.SPEC = make_spec(pbytes)
        self.domain = mod.load_domain(self.profile_obj, mod.SPEC)
        guard = b'# synthetic guard placeholder\n'
        write(self.p('in/guard.py'), guard)
        mod.GUARD_PIN = {'bytes': len(guard), 'sha256': sha(guard)}
        env = {'selected': {'CLIENT_AUTOEXTRACT': {'value': 'true'}, 'SERVER_ROOT': {'value': self.asset},
                            'HOST': {'value': '127.0.0.1'}, 'PORT': {'value': '33338'}}}
        ebytes = json.dumps(env).encode()
        write(self.p('in/env.json'), ebytes)
        write(self.p('native/server'), b'\x7fsynthetic-binary')
        write(self.p('native/DATA.INI'), b'[synthetic]\n')
        for k in range(5):
            write(self.p('arch/a%d.grf' % k), b'synthetic archive %d' % k)
        for i, data in (existing or {}).items():
            write(self.loose(i), data)
        self.out = self.p('out/run-1')
        os.makedirs(os.path.dirname(self.out))
        ident = mod.identity
        targets = []
        for row in self.domain['rows']:
            lp, op = mod.target_paths({'asset_root': self.asset, 'override_root': self.override}, row)
            targets.append({'query_index': row['index'], 'loose': mod.sample(lp), 'override': mod.sample(op)})
        self.binding = {
            'schema': mod.BINDING_SCHEMA, 'task': mod.TASK, 'head': HEAD, 'batch': batch,
            'profile': self.pin('in/profile.json'), 'pilot_audit': None, 'environment': {'path': self.p('in/env.json')},
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
            self.fio.responses[row['wire']] = {'body': BODIES[i], 'steady': len(BODIES[i]) > (64 << 10)}

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

    def extract_on_response(self, i, delay=None):
        target = self.loose(i)

        def do():
            if not os.path.exists(target):
                write(target, BODIES[i])
        if delay is None:
            self.fio.after_response.setdefault(self.wire(i), []).append(do)
        else:
            self.fio.after_response.setdefault(self.wire(i), []).append(
                lambda: self.fio.events.append((self.fio.clock.t + delay, do)))

    def run(self, argv=()):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = self.mod.main(list(argv), io=self.fio)
        self.stdout, self.stderr = out.getvalue(), err.getvalue()
        return code, json.loads(self.stdout)

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


def audit(env, **over):
    a = {'schema': env.mod.PILOT_AUDIT_SCHEMA, 'task': env.mod.TASK, 'auditor': 'Root', 'batch': 'pilot',
         'pilot_result_pin': {'bytes': 1, 'sha256': 'b' * 64}, 'pilot_query_indices': list(PILOT),
         'pilot_response_bytes': env.mod.SPEC['pilot_metadata_bytes'], 'admit_remainder': True}
    a.update(over)
    return a


class Base(unittest.TestCase):
    def env(self, **kw):
        e = Env(**kw)
        self.addCleanup(e.cleanup)
        return e

    def remainder_env(self, maker=None):
        def mut(env):
            data = json.dumps(audit(env) if maker is None else maker(env)).encode()
            write(env.p('in/audit.json'), data)
            env.binding['pilot_audit'] = env.pin('in/audit.json')
        return self.env(batch='remainder', mutate_binding=mut)

    def refuse(self, profile, code, spec=None):
        mod = load()
        with self.assertRaises(mod.Refusal) as cm:
            mod.load_domain(profile, spec or make_spec(b'x'))
        self.assertEqual(str(cm.exception), code)

    def assertFailedAt(self, e, i, code, attempts):
        rc, line = e.run()
        self.assertEqual(rc, 1)
        self.assertEqual(e.stderr, '')
        r = e.result()
        self.assertEqual(r['first_error'], 'q%04d:%s' % (i, code))
        self.assertFalse(r['batch_complete'] or r['delivery_complete'])
        self.assertEqual(len(e.fio.requests), attempts)
        led = r['query_ledger']
        self.assertEqual(len(led), len(RAW))
        self.assertEqual((led[i]['attempt_state'], led[i]['error']), ('failed', code))
        batch = PILOT if e.binding['batch'] == 'pilot' else REMAINDER
        self.assertTrue(all(led[x]['attempt_state'] == 'not_attempted' and led[x]['observed'] is None
                            for x in batch if x > i))
        ev = e.response(i)
        self.assertEqual(ev['classification'], 'failed')
        self.assertNotEqual(ev['hash_scope'], 'complete')
        return r, ev


# ---- 1. unbound refusal before every external observation ----

class Unbound(Base):
    def test_default_import_refuses_before_any_io(self):
        mod = load()
        self.assertIs(mod.ROOT_ADMITTED, False)
        self.assertEqual((mod.REQUIRED_HEAD, mod.BINDING_PATH, mod.BINDING_BYTES, mod.ENV_SELECTION_BYTES),
                         (None, None, None, None))
        self.assertEqual((mod.BINDING_SHA256, mod.ENV_SELECTION_SHA256), ('0' * 64, '0' * 64))

        class Trap:
            def __getattr__(self, name):
                raise AssertionError('io touched: ' + name)
        touched = []
        saved = {n: getattr(os, n) for n in ('open', 'lstat', 'stat', 'mkdir', 'listdir')}

        def spy(name):
            def f(*a, **k):
                touched.append((name, a[0] if a else None))
                return saved[name](*a, **k)
            return f
        out, err = io.StringIO(), io.StringIO()
        for n in saved:
            setattr(os, n, spy(n))
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                rc = mod.main([], io=Trap())
                rc_switch = mod.main(['--admit'], io=Trap())
        finally:
            for n, f in saved.items():
                setattr(os, n, f)
        self.assertEqual((rc, rc_switch), (2, 2))
        lines = [json.loads(x) for x in out.getvalue().splitlines()]
        self.assertEqual([x['reason'] for x in lines], ['unbound', 'argv'])
        self.assertEqual(err.getvalue(), '')
        self.assertEqual(touched, [])

    def test_mistyped_authority_refuses_without_output(self):
        e = self.env()
        for name, value, reason in [('ROOT_ADMITTED', 1, 'unbound'), ('BINDING_BYTES', True, 'unbound_binding'),
                                    ('REQUIRED_HEAD', 'A' * 40, 'unbound_head'),
                                    ('ENV_SELECTION_BYTES', 1.0, 'unbound_environment')]:
            saved = getattr(e.mod, name)
            setattr(e.mod, name, value)
            rc, line = e.run()
            setattr(e.mod, name, saved)
            self.assertEqual((rc, line['reason']), (2, reason), name)
            self.assertFalse(os.path.lexists(e.out))
        self.assertEqual((e.fio.requests, e.fio.probe_log), ([], []))


# ---- 2. whole-domain metadata mapping and profile validation ----

class Domain(Base):
    def test_mapping_batches_and_exact_wires(self):
        mod = load()
        prof = make_profile()
        before = copy.deepcopy(prof)
        d = mod.load_domain(prof, make_spec(b'x'))
        self.assertEqual(prof, before)  # nothing pruned or rewritten
        self.assertEqual(d['batches'], {'pilot': PILOT, 'remainder': REMAINDER})
        self.assertEqual(d['reuse_only'], REUSE)
        # Absence from the pilot is not eligibility: reuse rows are excluded from the remainder.
        self.assertFalse(set(REUSE) & set(d['batches']['remainder']))
        rows = d['rows']
        self.assertEqual(rows[1]['wire'], '/data/texture/%C2%BF%C3%B6/b.bmp')
        self.assertEqual(rows[5]['wire'], '/data/texture/%C3%87%C3%81/gid..down(side).bmp')
        self.assertEqual(rows[6]['wire'], '/data/texture/%C3%87%C3%81/gid..(side).bmp')
        self.assertEqual((rows[3]['wire'], rows[4]['wire']),
                         ('/data/texture/syn/ver.BMP', '/data/texture/syn/ver.bmp'))
        self.assertEqual([r['signature'] for r in rows if r['signature'] != 'bmp'],
                         ['not_checked_tga', 'not_checked_tga'])
        self.assertEqual(rows[12]['query']['relation_indices'], [12, 13])
        self.assertIs(rows[3]['record'], prof['queries'][3])
        self.assertEqual(rows[2]['expected']['source_pointer'], '/queries/2/reuse_expected/retained_body')

    def test_mapping_refusals(self):
        def mutated(fn):
            p = make_profile()
            fn(p)
            return p

        def setq(i, key, value, part='query'):
            def f(p):
                p['queries'][i][part][key] = value
                if part == 'query':  # keep the retained lookup copy equal so the targeted check is reached
                    p['queries'][i]['lookup_full_query_observation']['query'][key] = value
            return f
        double = '/data/texture/%25C2%25BF%25C3%25B6/b.bmp'
        cases = [
            (setq(1, 'http_path', double[1:]), 'http_path'),
            (setq(1, 'http_path', '/' + make_profile()['queries'][1]['query']['http_path']), 'http_path'),
            (setq(1, 'wire_target', double), 'wire_target'),
            (setq(3, 'wire_target', '/data/texture/syn/ver.bmp'), 'wire_target'),           # lower-cased
            (setq(5, 'wire_target', '/data/texture/%C3%87%C3%81/gid..down%28side%29.bmp'), 'wire_target'),
            (setq(1, 'raw_request_latin1', 'data\\texture\\b.bmp'), 'raw_name'),               # basename-ish
            (setq(1, 'http_path_encoded_once', 'data/texture/\xbf\xf6/b.bmp', 'mapping'), 'http_path'),
            (lambda p: p['queries'][0].__setitem__('signature_kind', 'bmp'), 'signature_policy'),  # tga as bmp
            (lambda p: p['queries'][1].__setitem__('signature_kind', 'not_checked_tga'), 'signature_policy'),
            (lambda p: p['queries'][1].__setitem__('signature_kind', 'jpeg'), 'signature_policy'),
            (lambda p: p['queries'][1].__setitem__('signature_kind', None), 'signature_policy'),
            (lambda p: p['queries'][1].__setitem__('new_body_expected_sha256', 'c' * 64), 'new_expected_sha'),
            (lambda p: p['queries'][1].__setitem__('reuse_expected', copy.deepcopy(p['queries'][2]['reuse_expected'])),
             'reuse_join'),
            (lambda p: p['queries'][2].__setitem__('reuse_expected', None), 'reuse_join'),
            (lambda p: p['queries'][2]['reuse_expected'].__setitem__('no_new_GET', False), 'reuse_join'),
            (lambda p: p['queries'][4]['lookup_full_query_observation']['query'].__setitem__('query_index', 3),
             'lookup_observation'),
            (lambda p: p['queries'][4].pop('lookup_full_query_observation'), 'lookup_observation'),
            (lambda p: p['queries'][9]['query'].__setitem__('role', 'model'), 'query_role'),
            (lambda p: p['queries'][9].__setitem__('metadata_real_size_range_all', [1, 1]), 'metadata_size'),
            (lambda p: p['batches'].__setitem__('remainder_indices', [2, 8, 9, 10, 11, 12]), 'batches'),
            (lambda p: p.__setitem__('preserved_parentheses_query_indices', [5]), 'parentheses'),
            (lambda p: p.__setitem__('preserved_casefold_query_groups', []), 'alias_group'),
            (lambda p: p.__setitem__('ambiguous_archive_queries', []), 'ambiguous_archive'),
        ]
        for fn, code in cases:
            with self.subTest(code=code):
                self.refuse(mutated(fn), code)

    def test_suffix_whitelist_is_case_exact(self):
        mod = load()
        raw = b'data\\texture\\syn\\odd.Bmp'
        prof = make_profile()
        slash, wire = encode(raw)
        q = prof['queries'][11]
        q['query'].update(expected_name_hex=raw.hex(), raw_request_latin1=raw.decode('latin-1'),
                          http_path=wire[1:], wire_target=wire)
        q['lookup_full_query_observation']['query'] = copy.deepcopy(q['query'])
        q['mapping'].update(raw_name_hex=raw.hex(), latin1_name=raw.decode('latin-1'), slash_name=slash,
                            wire_target=wire, http_path_encoded_once=wire[1:],
                            candidate_loose_relative_path=slash, candidate_override_relative_path=slash[5:])
        for policy in ('bmp', 'not_checked_tga'):
            q['signature_kind'] = policy
            with self.assertRaises(mod.Refusal) as cm:
                mod.load_domain(prof, make_spec(b'x'))
            self.assertEqual(str(cm.exception), 'signature_policy')

    def test_spec_refusals(self):
        spec = make_spec(b'x')
        self.refuse(make_profile(), 'pilot', dict(spec, pilot=[0, 1, 2, 3, 4, 5, 6, 7]))   # reuse in pilot
        self.refuse(make_profile(), 'reuse_join', dict(spec, reuse=[2]))   # row 10 still carries a reuse join
        self.refuse(make_profile(), 'metadata_total', dict(spec, reused_metadata_bytes=1))
        mod = load()
        mod.BODY_CAP = BIG - 1  # a metadata body above the per-body cap can never be admitted
        with self.assertRaises(mod.Refusal) as cm:
            mod.load_domain(make_profile(), spec)
        self.assertEqual(str(cm.exception), 'metadata_size')

    def test_frozen_constants(self):
        mod = load()
        self.assertEqual((mod.BODY_CAP, mod.AGGREGATE_CAP, mod.READ_BYTES), (8 << 20, 192 << 20, 64 << 10))
        self.assertEqual((mod.IO_SECONDS, mod.BATCH_SECONDS, mod.SETTLE_SECONDS), (3, 60, 2))
        s = mod.SPEC
        self.assertEqual(len(s['reuse']) + s['new'], s['queries'])
        self.assertEqual(s['pilot_metadata_bytes'] + s['remainder_metadata_bytes'], s['new_metadata_bytes'])
        self.assertEqual(s['new_metadata_bytes'] + s['reused_metadata_bytes'], s['total_metadata_bytes'])
        self.assertLess(s['new_metadata_bytes'], mod.AGGREGATE_CAP)
        self.assertLessEqual(s['max_body_bytes'], mod.BODY_CAP)
        self.assertEqual(len(s['pilot']) + s['remainder_count'], s['new'])
        self.assertFalse(set(s['pilot']) & set(s['reuse']))


# ---- 3. delivery: pilot success, mixed BMP/TGA, reuse never requested ----

class Delivery(Base):
    def test_pilot_success_mixed_policy_and_complete_ledger(self):
        e = self.env()
        for i in PILOT:
            e.extract_on_response(i)
        rc, line = e.run()
        self.assertEqual(rc, 0, e.stdout)
        self.assertEqual(e.stderr, '')
        r = e.result()
        self.assertTrue(r['batch_complete'] and r['delivery_complete'] and r['preservation_complete'])
        self.assertEqual(e.fio.requests, [e.wire(i) for i in PILOT])
        self.assertIn('/data/texture/%C3%87%C3%81/gid..down(side).bmp', e.fio.requests)
        self.assertTrue(all('%25' not in w for w in e.fio.requests))
        led = r['query_ledger']
        self.assertEqual(len(led), len(RAW))
        for i in REUSE:
            self.assertEqual((led[i]['attempt_state'], led[i]['selected'], led[i]['observed']),
                             ('reuse_only', False, None))
            self.assertEqual(led[i]['expected_pin']['sha256'], sha(BODIES[i]))
            self.assertEqual(led[i]['materialization']['state'], 'not_observed')
            self.assertEqual(led[i]['profile_record']['reuse_expected']['retained_body']['path'],
                             '/inert/prior/body-%04d.bin' % i)
        self.assertEqual([led[i]['attempt_state'] for i in REMAINDER], ['outside_batch'] * 4)
        ev0 = e.response(0)
        self.assertEqual((ev0['signature_policy'], ev0['signature'], ev0['classification']),
                         ('not_checked_tga', 'not_checked_tga', 'new_observed'))
        self.assertEqual(e.response(1)['signature'], 'match')
        self.assertEqual(r['tga_consumer_checks_claimed'], False)
        self.assertEqual(r['reuse_only_queries'], REUSE)
        self.assertEqual(r['casefold_alias_groups'], [[3, 4]])
        self.assertEqual(r['ambiguous_archive_queries'], [7])
        self.assertIs(r['archive_winner_claimed'], False)
        self.assertEqual(r['counts']['reuse_only'], 2)
        self.assertEqual(r['counts']['expected_match'], 0)
        self.assertEqual(r['maps_unchanged'], e.profile_obj['maps'])
        self.assertEqual(r['relations_unchanged'], e.profile_obj['relations'])
        self.assertEqual([x['profile_record'] for x in led], e.profile_obj['queries'])
        self.assertEqual(led[12]['query']['relation_indices'], [12, 13])
        names = sorted(os.listdir(e.out))
        self.assertEqual(names, sorted(['BEFORE_ROOT.json', 'AFTER_ROOT.json', 'RESULT_ROOT.json'] +
                                       ['response-%04d.json' % i for i in PILOT] +
                                       ['body-%04d.bin' % i for i in PILOT]))
        self.assertEqual(stat.S_IMODE(os.stat(e.out).st_mode), 0o700)
        self.assertTrue(all(stat.S_IMODE(os.stat(os.path.join(e.out, n)).st_mode) == 0o600 for n in names))
        s3, s4 = led[3]['materialization']['state'], led[4]['materialization']['state']
        if os.path.samefile(e.loose(3), e.loose(4)):
            self.assertEqual((s3, s4), ('shared_alias', 'shared_alias'))
        else:
            self.assertEqual((s3, s4), ('matched_new', 'matched_new'))

    def test_wrong_bmp_signature_stops_first_failure(self):
        e = self.env()
        e.fio.responses[e.wire(1)] = {'body': b'XX' + BODIES[1][2:]}
        r, ev = self.assertFailedAt(e, 1, 'signature_mismatch', 2)
        self.assertEqual(r['query_ledger'][0]['attempt_state'], 'succeeded')
        self.assertEqual(ev['signature'], 'mismatch')

    def test_tga_never_labelled_match_and_unknown_policy_fails(self):
        e = self.env()
        e.fio.responses[e.wire(0)] = {'body': b'BM' + BODIES[0][2:]}  # BM-looking TGA still makes no claim
        rc, _ = e.run()
        self.assertEqual(rc, 0, e.stdout)
        self.assertEqual(e.response(0)['signature'], 'not_checked_tga')
        e = self.env()
        real = e.mod.load_domain

        def bypass(profile, spec):  # simulate an unknown policy surviving into fetch()
            d = real(profile, spec)
            d['rows'][1]['signature'] = 'bypass'
            return d
        e.mod.load_domain = bypass
        r, ev = self.assertFailedAt(e, 1, 'signature_mismatch', 2)
        self.assertEqual(ev['signature'], 'unknown_policy')

    def test_remainder_large_body_no_replay(self):
        e = self.remainder_env()
        rc, _ = e.run()
        self.assertEqual(rc, 0, e.stdout)
        self.assertEqual(e.fio.requests, [e.wire(i) for i in REMAINDER])
        r = e.result()
        self.assertGreater(len(BODIES[8]), 1 << 20)
        self.assertEqual(e.body(8), BODIES[8])
        self.assertEqual(e.response(8)['hash_scope'], 'complete')
        self.assertEqual(e.response(9)['signature'], 'not_checked_tga')
        self.assertEqual(r['counts']['cumulative_response_bytes'],
                         e.mod.SPEC['pilot_metadata_bytes'] + e.mod.SPEC['remainder_metadata_bytes'])
        led = r['query_ledger']
        self.assertTrue(all(led[i]['attempt_state'] == 'outside_batch' for i in PILOT))
        self.assertEqual([led[i]['attempt_state'] for i in REUSE], ['reuse_only'] * 2)
        self.assertEqual(r['pilot_audit_pin'], {'bytes': e.binding['pilot_audit']['bytes'],
                                                'sha256': e.binding['pilot_audit']['sha256']})

    def test_reuse_in_selected_batch_refuses_before_io(self):
        e = self.env()
        real = e.mod.load_domain

        def leak(profile, spec):
            d = real(profile, spec)
            d['batches']['pilot'] = sorted(d['batches']['pilot'] + [2])
            return d
        e.mod.load_domain = leak
        rc, line = e.run()
        self.assertEqual((rc, line['reason']), (2, 'reuse_replay'))
        self.assertEqual(e.fio.requests, [])
        self.assertFalse(os.path.lexists(e.out))


# ---- 4. caps, framing, partial, EOF and stored-body checks ----

class Framing(Base):
    def test_failure_cases(self):
        cases = [
            ({'body': b'BM' + b'q' * 10, 'chunked': True}, 'size_mismatch'),
            ({'body': b'missing', 'status': 404}, 'http_status'),
            ({'body': b'', 'status': 302, 'headers': [('Location', '/x')]}, 'redirect'),
            ({'body': BODIES[1], 'headers': [('Content-Encoding', 'gzip')]}, 'content_encoding'),
            ({'body': BODIES[1], 'send': 10}, 'short_body'),
            ({'body': BODIES[1], 'chunked': True, 'truncate_chunked': 30}, 'incomplete_read'),
            ({'body': BODIES[1], 'headers': [('Content-Length', '3')]}, 'conflicting_framing'),
            ({'body': BODIES[1], 'declared_value': (8 << 20) + 1}, 'declared_over_cap'),
            ({'body': BODIES[1], 'declared_value': 2 << 20}, 'declared_length_mismatch'),  # fits new cap
            ({'body': BODIES[1], 'reset_after': 7}, 'transport'),
        ]
        for script, code in cases:
            with self.subTest(code=code):
                e = self.env()
                e.fio.responses[e.wire(1)] = script
                r, ev = self.assertFailedAt(e, 1, code, 2)
                if ev['body_file']:
                    self.assertEqual(ev['sha256'], sha(e.body(1)))  # honest prefix hash of stored bytes
                    self.assertEqual(ev['bytes'], len(e.body(1)))

    def test_tga_framing_still_checked(self):
        e = self.env()
        e.fio.responses[e.wire(0)] = {'body': BODIES[0], 'send': 5}
        self.assertFailedAt(e, 0, 'short_body', 1)

    def test_streamed_over_new_cap_without_length(self):
        e = self.env()
        e.fio.responses[e.wire(1)] = {'body': b'BM' + b'x' * (8 << 20), 'declared': None, 'steady': True}
        r, ev = self.assertFailedAt(e, 1, 'body_over_cap', 2)
        self.assertEqual(ev['bytes'], (8 << 20) + 1)
        self.assertEqual(len(e.body(1)), ev['bytes'])

    def test_aggregate_boundary_includes_pilot(self):
        e = self.remainder_env()
        e.mod.AGGREGATE_CAP = e.mod.SPEC['pilot_metadata_bytes'] + e.mod.SPEC['remainder_metadata_bytes']
        self.assertEqual(e.run()[0], 0)
        e = self.remainder_env()
        e.mod.AGGREGATE_CAP = e.mod.SPEC['pilot_metadata_bytes'] + e.mod.SPEC['remainder_metadata_bytes'] - 1
        self.assertFailedAt(e, REMAINDER[-1], 'aggregate_cap', len(REMAINDER))

    def test_stored_body_readback_mismatch(self):
        e = self.env()
        real = e.mod.pinned_read

        def tamper(path, n, digest, code):
            if code == 'stored_body' and path.endswith('body-0001.bin'):
                with open(path, 'r+b') as f:
                    f.write(b'ZZ')
            return real(path, n, digest, code)
        e.mod.pinned_read = tamper
        self.assertFailedAt(e, 1, 'stored_body_mismatch', 2)

    def test_slow_drip_deadline(self):
        e = self.env()
        e.fio.responses[e.wire(1)] = {'body': BODIES[1], 'step': 1, 'delay': 2.9}
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 1)
        self.assertIn(r['first_error'], ('q0001:deadline', 'q0001:io_timeout'))
        self.assertEqual(r['query_ledger'][3]['attempt_state'], 'not_attempted')
        self.assertEqual(e.body(1), BODIES[1][:len(e.body(1))])


# ---- 5. authority, pending settlement, sticky late failures ----

class Authority(Base):
    def test_remainder_requires_pinned_root_audit(self):
        e = self.env(batch='remainder')
        rc, line = e.run()
        self.assertEqual((rc, line['reason']), (2, 'pilot_audit_missing'))
        for maker in (lambda env: audit(env, pilot_query_indices=PILOT[:-1]),
                      lambda env: audit(env, pilot_query_indices=PILOT + [2]),
                      lambda env: audit(env, pilot_response_bytes=1),
                      lambda env: audit(env, auditor='candidate'),
                      lambda env: audit(env, schema=env.mod.RESULT_SCHEMA),
                      lambda env: dict(audit(env), extra=1)):
            e = self.remainder_env(maker)
            rc, line = e.run()
            self.assertEqual((rc, line['reason']), (2, 'pilot_audit'))
            self.assertEqual(e.fio.requests, [])

    def test_pending_settlement_and_stable_absent(self):
        e = self.env()
        e.extract_on_response(1, delay=0.3)
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 0, e.stdout)
        led = r['query_ledger']
        self.assertEqual(led[1]['materialization']['state'], 'matched_new')
        self.assertEqual(led[0]['materialization']['state'], 'absent')  # never extraction PASS
        self.assertFalse(r['materialization_complete'])
        self.assertTrue(r['batch_complete'])

    def test_existing_wrong_bytes_and_mutation(self):
        e = self.env(existing={2: b'BM' + b'w' * 40})
        rc, line = e.run()
        self.assertEqual((rc, line['reason']), (2, 'existing_wrong_bytes'))
        e = self.env(existing={2: BODIES[2]})
        e.fio.after_response.setdefault(e.wire(1), []).append(lambda: write(e.loose(2), b'BM' + b'm' * 50))
        rc, _ = e.run()
        r = e.result()
        self.assertEqual(rc, 1)
        self.assertIn('q0002:existing_mutation', r['postcheck_errors'])
        self.assertFalse(r['preservation_complete'])

    def test_postcheck_listener_and_close_failure(self):
        e = self.env()
        e.fio.listener_fail = True
        rc, _ = e.run()
        r = e.result()
        self.assertEqual((rc, r['first_error'], r['delivery_complete'], r['batch_complete']),
                         (1, 'listener_drift', True, False))
        e = self.env()
        e.fio.close_fail = True
        self.assertFailedAt(e, 0, 'close_failed', 1)

    def test_deadline_after_publication_is_sticky(self):
        e = self.env()
        for i in PILOT:
            e.extract_on_response(i)
        real = e.mod.write_new

        def slow(directory, name, data):
            real(directory, name, data)
            if name == 'RESULT_ROOT.json':
                e.fio.clock.t += e.mod.BATCH_SECONDS
        e.mod.write_new = slow
        rc, line = e.run()
        self.assertEqual((rc, line['first_error'], line['deadline_after_publication'], line['batch_complete']),
                         (1, 'deadline_after_publication', True, False))
        self.assertTrue(e.result()['batch_complete'])  # written candidate is superseded by stdout/exit

    def test_owner_drift_mid_run(self):
        e = self.env()
        e.fio.owner_fail_at = 3
        rc, _ = e.run()
        self.assertEqual((rc, e.result()['first_error'], e.fio.requests), (1, 'owner_drift', [e.wire(0)]))


PROFILE_PATH = os.environ.get('T07_014_017_PROFILE')
if PROFILE_PATH:
    class WholeProfile(unittest.TestCase):
        """Read-only metadata control on the pinned real profile; no request, target or live read."""

        def test_pinned_profile_domain(self):
            mod = load()
            s = mod.SPEC
            data = mod.pinned_read(PROFILE_PATH, s['profile_bytes'], s['profile_sha256'], 'profile_pin')
            prof = mod.strict_json(data, 'profile_json')
            d = mod.load_domain(prof, s)
            rows = d['rows']
            self.assertEqual((len(rows), len(d['relations']), len(d['maps'])), (948, 1546, 21))
            self.assertEqual(d['reuse_only'], [131, 401, 467, 468, 474, 475, 485, 501, 502, 513, 516, 584,
                                               630, 631, 677])
            self.assertEqual(d['batches']['pilot'], [0, 1, 18, 518, 542, 543, 603, 703, 837, 839])
            rem = d['batches']['remainder']
            self.assertEqual(len(rem), 923)
            self.assertFalse(set(rem) & set(d['reuse_only']) or set(rem) & set(d['batches']['pilot']))
            self.assertEqual(sum(rows[i]['metadata_bytes'] for i in d['batches']['pilot']), 9775600)
            self.assertEqual(sum(rows[i]['metadata_bytes'] for i in rem), 152966112)
            self.assertEqual(sum(1 for i in rem + d['batches']['pilot'] if rows[i]['metadata_bytes'] > 1 << 20), 75)
            self.assertEqual(max(rows[i]['metadata_bytes'] for i in (837, 839)), 4194348)
            self.assertNotEqual(rows[542]['wire'], rows[543]['wire'])
            self.assertEqual((rows[518]['wire'][-4:], rows[603]['wire'][-4:]), ('.BMP', '.bmp'))
            self.assertTrue(all(encode(bytes.fromhex(r['query']['expected_name_hex']))[1] == r['wire']
                                == '/' + r['query']['http_path'] for r in rows))
            self.assertEqual(sum(1 for r in rows if r['signature'] == 'not_checked_tga'), 25)
            multi = sum(len(r['query']['relation_indices']) for r in rows)
            self.assertEqual(multi, 1546)
            self.assertEqual([r['record'] for r in rows], prof['queries'])


if __name__ == '__main__':
    unittest.main()
