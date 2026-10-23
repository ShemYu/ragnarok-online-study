"""T10.005.001 fixed materializer: one shared uptime trial clock per actor.

apply_shared_trial_clock(sources) is a pure bytes-to-bytes transform of the three
pinned UNBOUND actor sources (parent, proxy, launcher). It never touches files,
processes or the network and never imports or executes the supplied sources;
Root owns every actual materialization, witness and execution.

Declared finite edit surface, per source:
  1. HELPER inserted immediately before the unique module-level ``def need(``
     anchor, ending with exactly two LF bytes after its final body line;
  2. every exact ``time.monotonic()`` token replaced by ``trial_now()``;
  3. proxy only: the single E.transfer keyword sequence gains ``clock=trial_now``.
All other bytes are unchanged; the output is checked against an exact inverse.
"""
import hashlib

ROLES = ('parent', 'proxy', 'launcher')
PINS = {
    'parent': (36819, 'dd43957d2c2bb03f749e9a792b1c51e5f35befe4508f7212dfbeb90eceeae1ea'),
    'proxy': (45904, '84ca87cf1507a35cd761cb071247d28542f56cdbb2abc83f722517d7ba42529c'),
    'launcher': (40911, '0d2b2c5fef36e01b6d4fd53e8ab7c1fc686054a4289092714cdb78efc1d4c5ed'),
}
CALL_OLD = b'time.monotonic()'
CALL_NEW = b'trial_now()'
CALL_COUNTS = {'parent': 11, 'proxy': 11, 'launcher': 21}
ANCHOR = b'\ndef need('
TRANSFER_OLD = b'deadline=deadline,write_fn=write_body'
TRANSFER_NEW = b'deadline=deadline,clock=trial_now,write_fn=write_body'
TRANSFER_COUNTS = {'parent': 0, 'proxy': 1, 'launcher': 0}
GROWTH_CAP = 2048
# Same text in all three actors. It resolves time, math and need from the actor's
# own module globals at call time (all bound before any actor call site), reads
# the awake-time uptime clock on every call and refuses without any fallback.
HELPER = (
    b"def trial_now():\n"
    b"    need(callable(getattr(time,'clock_gettime',None)) and type(getattr(time,'CLOCK_UPTIME_RAW',None)) is int,'trial uptime clock unavailable')\n"
    b"    try:now=time.clock_gettime(time.CLOCK_UPTIME_RAW)\n"
    b"    except OSError:now=None\n"
    b"    need(type(now) is float and math.isfinite(now) and now>=0,'trial uptime clock invalid read')\n"
    b"    return now\n"
    b"\n"
)
# Markers that only a patched (or otherwise foreign) source would contain.
FOREIGN = (b'trial_now', b'clock_gettime', b'CLOCK_UPTIME_RAW')


def _refuse(code):
    raise ValueError('T10.005.001 refused: ' + code)


def _check_input(role, src):
    for marker in FOREIGN:
        if marker in src:
            _refuse(role + ' already patched or foreign clock marker')
    if src.count(CALL_OLD) != CALL_COUNTS[role]:
        _refuse(role + ' own clock call count')
    if src.count(ANCHOR) != 1 or src.count(b'def need(') != 1:
        _refuse(role + ' missing or nonunique def need( anchor')
    if src.count(TRANSFER_OLD) != TRANSFER_COUNTS[role] or src.count(TRANSFER_NEW) != 0:
        _refuse(role + ' transfer keyword surface')


def _inverse(role, out):
    """Exact inverse of the declared edits; refuses unless the surface is exact."""
    if out.count(HELPER + b'def need(') != 1 or out.count(b'def trial_now(') != 1:
        _refuse(role + ' inverse helper surface')
    pos = out.index(HELPER + b'def need(')
    rest = out[:pos] + out[pos + len(HELPER):]
    if rest.count(TRANSFER_NEW) != TRANSFER_COUNTS[role] or rest.count(CALL_NEW) != CALL_COUNTS[role]:
        _refuse(role + ' inverse token surface')
    return rest.replace(TRANSFER_NEW, TRANSFER_OLD).replace(CALL_NEW, CALL_OLD)


def _patch(role, src):
    tmp = src.replace(CALL_OLD, CALL_NEW)
    if TRANSFER_COUNTS[role]:
        tmp = tmp.replace(TRANSFER_OLD, TRANSFER_NEW)
    pos = tmp.index(ANCHOR) + 1
    out = tmp[:pos] + HELPER + tmp[pos:]
    if not out.startswith(src[:src.index(ANCHOR) + 1]):
        _refuse(role + ' bytes before anchor changed')
    if out.count(CALL_OLD) != 0 or out.count(CALL_NEW) != CALL_COUNTS[role] + 1:
        _refuse(role + ' patched clock call count')
    if not 0 < len(out) - len(src) <= GROWTH_CAP:
        _refuse(role + ' growth cap')
    if _inverse(role, out) != src:
        _refuse(role + ' inverse mismatch')
    return out


def apply_shared_trial_clock(sources):
    """Return {'parent','proxy','launcher'} -> patched bytes, or raise."""
    if type(sources) is not dict:
        raise TypeError('sources must be a dict')
    if set(sources) != set(ROLES) or len(sources) != len(ROLES):
        raise TypeError('sources must have exactly parent, proxy, launcher keys')
    for role in ROLES:
        if type(sources[role]) is not bytes:
            raise TypeError(role + ' source must be bytes')
    snapshot = {role: sources[role] for role in ROLES}
    # The complete pinned triple is verified before any edit is attempted.
    for role in ROLES:
        size, digest = PINS[role]
        src = snapshot[role]
        if len(src) != size or hashlib.sha256(src).hexdigest() != digest:
            _refuse(role + ' source drift from pin')
    for role in ROLES:
        _check_input(role, snapshot[role])
    return {role: _patch(role, snapshot[role]) for role in ROLES}
