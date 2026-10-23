"""T10.005.001 authored source controls (worker-authored, unrun). Compiles only the actual
patched trial_now helper and single-statement fragments located by AST, with fake time/need/E;
never runs a complete actor, files, processes, network or dynamic dependency loading.
"""
import ast
import hashlib
import math
import types

ROLES = ('parent', 'proxy', 'launcher')
COUNTS = {'parent': 11, 'proxy': 11, 'launcher': 21}
OLD, NEW = b'time.monotonic()', b'trial_now()'
T_OLD = b'deadline=deadline,write_fn=write_body'
T_NEW = b'deadline=deadline,clock=trial_now,write_fn=write_body'
ANCHOR = b'\ndef need('
RAW_ID = 8
P1, R1 = ['pass', 1], ['refuse', 1]


class Refused(Exception):
    pass


def fake_need(v, code):
    if not v:
        raise Refused(code)


def sha(b):
    return hashlib.sha256(b).hexdigest()


def clean(v):
    if isinstance(v, dict):
        return {str(k)[:80]: clean(x) for k, x in list(v.items())[:64]}
    if isinstance(v, (list, tuple)):
        return [clean(x) for x in v[:64]]
    ok = v is None or isinstance(v, (bool, int)) or isinstance(v, float) and math.isfinite(v)
    return v if ok else str(v)[:240]


def refuses(call):
    try:
        call()
    except Exception as e:
        return type(e).__name__
    return None


def group(gid, items):
    checks = []
    for name, fn in items:
        try:
            ok, obs = fn()
            ok = ok is True
        except Exception as e:
            ok, obs = False, 'error:%s:%s' % (type(e).__name__, str(e)[:160])
        checks.append({'name': name, 'passed': ok, 'observed': clean(obs)})
    return {'id': gid, 'passed': bool(checks) and all(c['passed'] for c in checks), 'checks': checks}


def fake_time(values, drop=(), raw=RAW_ID):
    log, vals = [], list(values)

    def clock_gettime(cid):
        log.append(cid)
        v = vals.pop(0)
        if isinstance(v, BaseException):
            raise v
        return v

    def monotonic():
        raise AssertionError('time.monotonic read')
    ns = {'CLOCK_UPTIME_RAW': raw, 'clock_gettime': clock_gettime, 'monotonic': monotonic}
    for k in drop:
        del ns[k]
    return types.SimpleNamespace(**ns), log


def helper_of(src):
    i = src.index(ANCHOR) + 1
    return src[src.rindex(b'\ndef trial_now():\n', 0, i) + 1:i]


def build(helper, t):
    ns = {'time': t, 'math': math, 'need': fake_need}
    exec(compile(helper.decode('utf-8'), '<trial_now>', 'exec'), ns)
    return ns['trial_now']


def one(nodes):
    (node,) = nodes  # Exactly one match, else ValueError.
    return node


def is_name(n, name):
    return isinstance(n, ast.Name) and n.id == name


def need_seg(text, t, label):
    return ast.get_source_segment(text, one([
        n for n in ast.walk(t) if isinstance(n, ast.Call) and is_name(n.func, 'need') and len(n.args) == 2
        and isinstance(n.args[1], ast.Constant) and n.args[1].value == label]))


def assign_seg(text, t, name):
    return ast.get_source_segment(text, one([
        n for n in ast.walk(t) if isinstance(n, ast.Assign) and len(n.targets) == 1 and is_name(n.targets[0], name)
        and isinstance(n.value, ast.Call) and is_name(n.value.func, 'trial_now')]))


def transfer_calls(t):
    return [n for n in ast.walk(t) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == 'transfer' and is_name(n.func.value, 'E')]


def ev(seg):
    code = compile(seg, '<fragment>', 'eval')
    return lambda ns: eval(code, ns)


def run_authored(sources, patcher):
    arg = dict(sources)
    O = {r: sources[r] for r in ROLES}
    orig_hash = {r: sha(O[r]) for r in ROLES}
    try:
        out = patcher(arg)
    except Exception:
        out = None
    P = out if type(out) is dict else {}
    try:  # A malformed patch output fails the dependent checks instead of the run.
        text = {r: P[r].decode('utf-8') for r in ROLES}
        trees = {r: ast.parse(text[r]) for r in ROLES}
        H = helper_of(P['parent'])
    except Exception:
        text, trees, H = {}, {}, b''
    otext = {r: O[r].decode('utf-8') for r in ROLES}
    otrees = {r: ast.parse(otext[r]) for r in ROLES}

    # G01: pinned triple, drift/malformed/repeat refusal, inputs unchanged.
    def g01_triple():
        ok = type(out) is dict and sorted(out) == sorted(ROLES) and all(
            type(out[r]) is bytes and out[r] != O[r] for r in ROLES)
        return ok and patcher(dict(O)) == out, {r: [len(O[r]), len(out[r])] for r in ROLES}

    def g01_drift():
        obs = {}
        for r in ROLES:
            s = O[r]
            flip = bytearray(s)
            flip[len(s) // 2] ^= 1
            muts = (bytes(flip), s[:-1], s + b'\n', s.replace(ANCHOR, b'\ndef nede(', 1))
            obs[r] = [refuses(lambda v=v: patcher(dict(O, **{r: v}))) for v in muts]
        return all(x is not None for v in obs.values() for x in v), obs

    def all_refuse(cases):
        obs = [refuses(lambda c=c: patcher(c)) for c in cases]
        return all(x is not None for x in obs), obs

    def g01_malformed():
        return all_refuse([None, list(O.items()), {}, {k: O[k] for k in ROLES[:2]}, dict(O, extra=b''),
                           dict(O, proxy=otext['proxy']), dict(O, launcher=bytearray(O['launcher'])),
                           dict(O, parent=memoryview(O['parent'])), dict(O, parent=None)])

    def g01_repeat():
        return all_refuse([dict(out), dict(O, parent=out['parent'])])

    def g01_unchanged():
        ok = set(arg) == set(sources) and all(arg[r] is sources[r] is O[r] for r in ROLES)
        return ok and {r: sha(sources[r]) for r in ROLES} == orig_hash, orig_hash

    # G02: the actual inserted helper text, compiled with a fake time module.
    def g02_same_text():
        hs = [helper_of(P[r]) for r in ROLES]
        ok = (hs[0] == hs[1] == hs[2] == H and all(P[r].count(b'def trial_now(') == 1 for r in ROLES)
              and H.endswith(b'\n\n') and not H.endswith(b'\n\n\n') and b'monotonic' not in H)
        return ok, {'helper_bytes': len(H), 'helper_sha256': sha(H)}

    def g02_each_call():
        t, log = fake_time([5.25, 7.5, 7.5, 123456.789, 0.0])
        f = build(H, t)
        got = [f() for _ in range(5)]
        return got == [5.25, 7.5, 7.5, 123456.789, 0.0] and log == [RAW_ID] * 5, {'got': got, 'ids': log}

    def g02_invalid():
        obs = {}
        for v in (float('nan'), float('inf'), float('-inf'), -0.5, -1e-9, 5, True, None, '1.0', OSError(5, 'x')):
            t, log = fake_time([v])
            obs[repr(v)] = [refuses(build(H, t)), len(log)]
        return all(x == ['Refused', 1] for x in obs.values()), obs

    def g02_unavailable():
        obs = {}
        for drop, raw in ((('CLOCK_UPTIME_RAW',), RAW_ID), (('clock_gettime',), RAW_ID), ((), '8'), ((), None)):
            t, log = fake_time([1.0], drop, raw)
            obs['%s/%r' % (drop, raw)] = [refuses(build(H, t)), len(log)]
        return all(x == ['Refused', 0] for x in obs.values()), obs

    def g02_no_mutation():
        t, log = fake_time([1.0, 2.0])
        mono, before, f = t.monotonic, dict(vars(t)), build(H, t)
        got = [f(), f()]
        bad = [type(n).__name__ for n in ast.walk(ast.parse(H.decode('utf-8')))
               if isinstance(n, (ast.Global, ast.Nonlocal, ast.Import, ast.ImportFrom, ast.AugAssign, ast.AnnAssign))
               or isinstance(n, ast.Assign) and not all(isinstance(x, ast.Name) for x in n.targets)]
        return got == [1.0, 2.0] and t.monotonic is mono and vars(t) == before and not bad, bad

    # G03: actual patched startup/deadline predicates driven by the actual helper.
    def drive(run, ns, values, prep=None):
        res = []
        for v in values:
            t, log = fake_time([v])
            ns['trial_now'] = build(H, t)
            try:
                if prep:
                    exec(compile(prep, '<prep>', 'exec'), ns)
                run(ns)
                res.append(['pass', len(log)])
            except Refused:
                res.append(['refuse', len(log)])
        return res

    def same(role, *segs):  # Each fragment is the original fragment with only the token replaced.
        return all(s.replace('trial_now()', 'time.monotonic()') in otext[role] for s in segs)

    def g03_parent_before():
        seg = ast.get_source_segment(text['parent'], one(
            [n for n in trees['parent'].body if isinstance(n, ast.FunctionDef) and n.name == 'before']))
        ns = {'need': fake_need}
        exec(compile(seg, '<before>', 'exec'), ns)
        got = drive(lambda n: n['before'](1050.0, 'c'), ns, [1049.5, 1050.0, 1050.5])
        return same('parent', seg) and 'trial_now()' in seg and got == [P1, R1, R1], got

    def pred(role, label, ns, values, expect, assign=None):
        # Optional actual 'name=trial_now()' statement, then the actual labelled need(...) predicate.
        a = assign_seg(text[role], trees[role], assign) if assign else ''
        seg = need_seg(text[role], trees[role], label)
        ns['need'] = fake_need
        got = drive(ev(seg), ns, values, prep=a)
        ok = same(role, seg, a) and 'trial_now()' in seg + a and got == expect
        return ok and (not a or ns[assign] == values[-1]), got

    tc = {'ready_cutoff': 1025.0}
    shared = {'started_monotonic': 1000.0, 'deadline_monotonic': 1120.0, 'cleanup_reserve_seconds': 10}
    g03 = [('parent grant by ready', 'parent', 'grant issue by25', {'times': {'ready': 1025.0}},
            [1024.5, 1025.0, 1026.0], [P1, R1, R1], 'grant_issue'),
           ('proxy finite deadline', 'proxy', 'finite proxy deadline', {'deadline': 1110.0},
            [1109.9, 1110.0, 1111.0], [P1, R1, R1]),
           ('proxy pre-T0 start refused', 'proxy', 'whole120s shared caller trial', {'clock': shared},
            [999.5, 1000.0, 1109.5, 1110.0], [R1, P1, P1, R1], 'start'),
           ('launcher startup window', 'launcher', 'T10 startup phase', {'t0': 1000.0, 'tc': tc},
            [999.999, 1000.0, 1024.999, 1025.0, 1030.0], [R1, P1, P1, R1, R1]),
           ('launcher spawn cutoff', 'launcher', 'T10 spawn startup cutoff', {'tc': tc}, [1024.5, 1025.0], [P1, R1])]

    # G04: the actual patched E.transfer call and its clock/deadline arguments.
    def call_seg(src_text, t):
        return ast.get_source_segment(src_text, one(transfer_calls(t)))

    def capture(seg, helper_fn, deadline):
        seen = {}

        def transfer(*a, **kw):
            seen['args'], seen['kw'] = a, kw
        ns = {'E': types.SimpleNamespace(transfer=transfer), 'meter': object(), 'fd': 7, 'BODY_CAP': 100,
              'WIRE_CAP': 1000, 'report': {'wire_bytes': 10}, 'deadline': deadline,
              'write_body': fake_need, 'trial_now': helper_fn}
        eval(compile(seg, '<transfer>', 'eval'), ns)
        return seen['kw'], ns

    def g04_keyword():
        n = one(transfer_calls(trees['proxy']))
        kw = {k.arg: k.value for k in n.keywords}
        others = [len(transfer_calls(trees[r])) == len(transfer_calls(otrees[r])) for r in ('parent', 'launcher')]
        ok = ([k.arg for k in n.keywords] == ['body_cap', 'aggregate_left', 'deadline', 'clock', 'write_fn']
              and is_name(kw['clock'], 'trial_now') and is_name(kw['deadline'], 'deadline') and all(others))
        seg, oseg = call_seg(text['proxy'], trees['proxy']), call_seg(otext['proxy'], otrees['proxy'])
        return ok and seg.replace(',clock=trial_now', '', 1) == oseg, list(kw)

    def g04_same_callable():
        t, log = fake_time([1234.5])
        helper_fn, dl = build(H, t), float('1234.5')
        kw, ns = capture(call_seg(text['proxy'], trees['proxy']), helper_fn, dl)
        clk = kw.get('clock')
        read = clk() if callable(clk) else None
        okw, _ = capture(call_seg(otext['proxy'], otrees['proxy']), helper_fn, dl)
        ok = (clk is helper_fn is ns['trial_now'] and kw.get('deadline') is dl and read == dl
              and log == [RAW_ID] and 'clock' not in okw)
        return ok, {'deadline_is': kw.get('deadline') is dl, 'read': read,
                    'orig_clock': 'clock' in okw, 'seam': 'Root witness pending'}

    # G05: coverage, exact surface, inverse and unchanged remaining bytes.
    def g05_counts():
        obs = {r: [O[r].count(OLD), P[r].count(OLD), P[r].count(NEW) - 1] for r in ROLES}
        return all(obs[r] == [COUNTS[r], 0, COUNTS[r]] for r in ROLES) and sum(COUNTS.values()) == 43, obs

    def g05_transfer_token():
        obs = {r: [O[r].count(T_OLD), P[r].count(T_OLD), P[r].count(T_NEW), P[r].count(b'clock=trial_now')]
               for r in ROLES}
        return obs == {'parent': [0, 0, 0, 0], 'proxy': [1, 0, 1, 1], 'launcher': [0, 0, 0, 0]}, obs

    def g05_anchor_growth():
        obs = {}
        for r in ROLES:
            i = O[r].index(ANCHOR) + 1
            exp = len(O[r]) + len(H) - 5 * COUNTS[r] + (16 if r == 'proxy' else 0)
            obs[r] = [O[r].count(ANCHOR) == 1 and O[r].count(b'def need(') == 1 and P[r][:i] == O[r][:i]
                      and P[r][i:i + len(H)] == H and P[r][i + len(H):].startswith(b'def need('),
                      len(P[r]) - len(O[r]), len(P[r]) == exp]
        return all(a and 0 < d <= 2048 and e for a, d, e in obs.values()), obs

    def g05_inverse():
        obs = {}
        for r in ROLES:
            i = P[r].index(H + b'def need(')
            rest = P[r][:i] + P[r][i + len(H):]
            inv = rest.replace(T_NEW, T_OLD).replace(NEW, OLD)
            changed = sum(1 for a, b in zip(O[r].split(b'\n'), rest.split(b'\n')) if a != b)
            obs[r] = [inv == O[r] and sha(inv) == orig_hash[r], changed]
        return all(v[0] for v in obs.values()), obs

    def g05_no_monkeypatch():
        obs = {}
        for r in ROLES:
            stores = [x for n in ast.walk(trees[r]) if isinstance(n, (ast.Assign, ast.AugAssign))
                      for x in getattr(n, 'targets', [getattr(n, 'target', None)])
                      if isinstance(x, ast.Attribute) and is_name(x.value, 'time')]
            obs[r] = [len(stores), O[r].count(b'clock_gettime'),
                      P[r].count(b'clock_gettime') - H.count(b'clock_gettime'),
                      P[r].count(b'CLOCK_UPTIME_RAW') - H.count(b'CLOCK_UPTIME_RAW')]
        return bool(H) and all(v == [0, 0, 0, 0] for v in obs.values()), obs

    def g05_module_shape():
        obs = {}
        for r in ROLES:
            body, obody = trees[r].body, otrees[r].body
            k = [i for i, n in enumerate(body) if isinstance(n, ast.FunctionDef) and n.name == 'trial_now'][0]
            imported = {a.name for n in body[:k] if isinstance(n, ast.Import) for a in n.names}
            shape = [[type(n).__name__, getattr(n, 'name', None)] for n in body[:k] + body[k + 1:]]
            obs[r] = (shape == [[type(n).__name__, getattr(n, 'name', None)] for n in obody]
                      and body[k + 1].name == 'need' and {'time', 'math'} <= imported)
        return all(obs.values()), obs

    groups = [
        group('G01', [('pinned triple patches', g01_triple), ('byte anchor size drift refuses', g01_drift),
                      ('malformed argument refuses', g01_malformed), ('repeat application refuses', g01_repeat),
                      ('inputs unchanged', g01_unchanged)]),
        group('G02', [('same helper text once each', g02_same_text), ('reads selected clock every call', g02_each_call),
                      ('invalid reads refuse', g02_invalid), ('unavailable clock refuses', g02_unavailable),
                      ('no time module mutation', g02_no_mutation)]),
        group('G03', [('parent before cutoff', g03_parent_before)] +
              [(c[0], lambda c=c: pred(*c[1:])) for c in g03]),
        group('G04', [('transfer keyword exact', g04_keyword), ('same helper and absolute deadline', g04_same_callable)]),
        group('G05', [('43 own clock reads', g05_counts), ('one transfer keyword', g05_transfer_token),
                      ('helper at anchor exact growth', g05_anchor_growth), ('inverse restores donors', g05_inverse),
                      ('no time monkeypatch', g05_no_monkeypatch), ('module shape preserved', g05_module_shape)]),
    ]
    return {'schema': 'T10.005.001-authored-1', 'scope': 'authored_source_controls', 'original_sha256': orig_hash,
            'patched_sha256': {r: sha(P[r]) if type(P.get(r)) is bytes else None for r in ROLES}, 'groups': groups}
