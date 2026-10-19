"""Root-operated observation of all pinned cached-map core resources.

Source only: private pinned metadata/assets are required. --preflight reads
source/metadata without native/archive access. --execute requires the exact
root-reviewed source hash and uses one new isolated loopback reader directory.
Results establish observed resource/header chains, never full map playability.
"""
import argparse
import hashlib
import http.client
import json
import os
import re
from pathlib import Path
import socket
import stat
import subprocess
import tempfile
import sys
import time
from urllib.parse import quote

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / '.tools/renewal/t06-map-core-preparation-1'
BASE = PREP / 'native-all-cache-map-1'
RENEWAL = ROOT / '.tools/renewal'
EXE = Path.home() / 'Library/Application Support/Ragnarok Offline/runtime/bin/robrowser-remoteclient'
ARCHIVES = RENEWAL / 'assets/tw-20260409/app'
NATIVE = [('binary', EXE, 'ee6b328ec73a591b23b514379e1b34e876b5d860d0e1aa4d9aa15dd7173eb1c1'),
          ('event.grf', ARCHIVES / 'event.grf', '7fff4e0eececd10df9a9c4f83b70d78dc4dbb99c5ece64b117df7db8a2f85575'),
          ('data0.grf', ARCHIVES / 'data0.grf', '913402ace1d3c67818b4f070650a07eb157a6d62df9e394d596d59b4c7e6678a'),
          ('data.grf', ARCHIVES / 'data.grf', '1c7d68f70714937abbd3741a6b3aea34a7ed9da63428941d5df453efacd1c0ad')]
META = {
    'map_cache': ('t06-map-cache-candidates/integrated-2/map-cache-manifest.json', 'fd49368cc132ad7a1303d1eba8705b89da1548b293265094b69dc7e80ea240f5'),
    'selection': ('t06-selection-candidates/integrated-1/selection-manifest.json', 'd62e31fd601a879a9020eb0cbc79273cdaa38f11d6119af056b36727631aec9a'),
    'alias_proof': ('t06-selection-preparation/client-dependencies/raw-ascii-map-presence/root-alias-full-proof.json', '571776963a018363d41b75270e0a45001cb669f84ad0861947b225800c5bc5d5'),
    'prior_helper': ('t06-selection-preparation/client-dependencies/native-map-slice-3.py', '5b9bfa57e9aa1c193e2651478b12ba7b022e16116a9cb1ab79072afc61431d02'),
    'roots': ('t06-map-core-preparation-1/root-all-cache-map-roots-1.json', 'e4f34649f5770cf84e17dde1657e24fa419d3ac36949bc859428cc14bc3c01fe')}
PROFILE = ROOT / 'docs/project/fixtures/T06.003.003.001-profile.json'
PROFILE_SHA = '1249e392d68c54bb92f52d4667cc2adbd8e613f4952fce8e58dc344c274cb431'
EXTRA_SOURCES = {
    'src/Loaders/Altitude.js': 'e27f5b746bb8fa77aadb59633dfbc0339f922bc4df69615a066288a6cf160b95',
    'src/Loaders/Ground.js': '8b82cf7321123054cf2bbeff1816931c7f3fc7833ae7af916077691d871f2db0'}
ALIAS_SHA = '5bdd0091b84493f601bf6bdf511b5d97ca936fba035408363fba2ad61e8d3763'
BODY_CAP, TOTAL_CAP, GET_CAP, SECONDS, IO = 16 << 20, 8 << 30, 3889, 1200, 5
# ECMAScript whitespace used by the pinned FileManager's trim regex.
JS_WS = ''.join(chr(n) for n in [9, 10, 11, 12, 13, 32, 160, 0x1680,
    *range(0x2000, 0x200B), 0x2028, 0x2029, 0x202F, 0x205F, 0x3000, 0xFEFF])

def client_filename(value):
    return value.strip(JS_WS)

def client_parser(value):
    # Deliberately preserve the source's unescaped leading dot, /.[^.]+$/.
    match = re.search(r'.[^.]+$', value)
    return None if match is None else match.group(0)[1:].lower()

sha = lambda b: hashlib.sha256(b).hexdigest()
identity = lambda s: [s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns]


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def hash_file(path):
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        require(stat.S_ISREG(before.st_mode), 'not a regular input')
        digest = hashlib.sha256()
        left = before.st_size
        while left:
            chunk = stream.read(min(4 << 20, left))
            require(bool(chunk), 'input truncated while hashing')
            digest.update(chunk)
            left -= len(chunk)
        require(not stream.read(1), 'input grew while hashing')
        require(identity(before) == identity(os.fstat(stream.fileno())) == identity(path.lstat()), 'input changed while hashing')
        return {'sha256': digest.hexdigest(), 'identity': identity(before)}


def metadata():
    """No native binary/archive reads. Fixed metadata sizes bound JSON reads."""
    pins, objects = {}, {}
    for label, (rel, pin) in META.items():
        path = RENEWAL / rel
        got = hash_file(path)
        require(got['sha256'] == pin and got['identity'][2] <= 32 << 20, 'metadata pin/size: ' + label)
        pins[label] = got
        if label in ('roots', 'alias_proof'):
            data = path.read_bytes()
            require(sha(data) == pin, 'metadata reread drift')
            objects[label] = json.loads(data)
    require(hash_file(PROFILE)['sha256'] == PROFILE_SHA, 'profile pin')
    profile = json.loads(PROFILE.read_bytes())
    require(sha(PROFILE.read_bytes()) == PROFILE_SHA, 'profile reread drift')
    sources = dict(profile['source_pins'])
    sources.update(EXTRA_SOURCES)
    for item in objects['alias_proof']['source_files']:
        sources[item['name']] = item['sha256']
    for rel, pin in sources.items():
        require(hash_file(RENEWAL / 'client-source' / rel)['sha256'] == pin, 'client source pin: ' + rel)
    for rel, pin in profile['server_source_pins'].items():
        require(hash_file(RENEWAL / 'rathena-source' / rel)['sha256'] == pin, 'server source pin: ' + rel)
    manifest, proof = objects['roots'], objects['alias_proof']
    require(manifest['input_pins'] == {k: META[k][1] for k in ('map_cache', 'selection', 'alias_proof', 'prior_helper')}, 'manifest provenance')
    roots = manifest['roots']
    require(len(roots) == 1296 and len({r['name'] for r in roots}) == 1296, 'root denominator/duplicates')
    require(sum(r['configured'] is not None for r in roots) == 1265, 'configured denominator')
    require([r['ordinal'] for r in roots] == list(range(1296)), 'root order')
    require([r['cache_file'] for r in roots] == ['db/re/map_cache.dat'] * 8 + ['db/map_cache.dat'] * 1288, 'cache file order')
    require(all(r['name'].isascii() and 0 < len(r['name']) <= 11 and '.' not in r['name'] and '#' not in r['name'] for r in roots), 'root spelling')
    require(proof['alias_response_sha256'] == ALIAS_SHA and len(proof['all_alias_events']) == 3417, 'alias proof pin/denominator')
    aliases = {}
    for i, event in enumerate(proof['all_alias_events']):
        require(event['callback_index'] == i * 2 and isinstance(event['key'], str) and isinstance(event['value'], str), 'alias event')
        aliases[event['key']] = event['value']  # Exact spelling; later callback wins.
    return roots, aliases, pins, sources


def target(logical):
    """FileManager.getHTTP per non-slash segment, never lowercase or retry."""
    logical = logical.replace('\\', '/')
    require(logical and not logical.startswith('/') and not any(ord(c) < 32 or ord(c) == 127 for c in logical), 'unsupported control/absolute path')
    require(not any(p in ('.', '..') for p in logical.split('/')), 'unsupported dot segment')
    return '/' + '/'.join(quote(p, safe="!'()*-._~", encoding='utf-8', errors='strict') for p in logical.split('/'))


def world_header(data):
    require(len(data) >= 6 and data[:4] == b'GRSW', 'bad_header: RSW')
    signed = lambda b: b if b < 128 else b - 256
    major, minor = signed(data[4]), signed(data[5])  # World uses signed readByte.
    require(major >= 0 and 0 <= minor <= 9, 'unsupported_version_spelling')
    version = major + minor / 10
    start = 6 + (4 if version >= 2.5 else 0) + (1 if version >= 2.2 else 0)
    require(len(data) >= start + 120, 'bad_header: short RSW fixed fields')
    fields = {}
    for i, name in enumerate(('ini', 'gnd', 'gat')):
        fixed = data[start + 40 * i:start + 40 * (i + 1)]
        raw = fixed.partition(b'\0')[0]
        fields[name] = {'fixed_hex': fixed.hex(), 'raw_hex': raw.hex(), 'nul_terminated': b'\0' in fixed,
                        'client_string': raw.decode('latin-1')}
    return {'version_bytes': list(data[4:6]), 'version': version, 'fixed_offset': start, 'fields': fields,
            'limits': 'Fixed header observation only; full RSW parse/compile not performed.'}


def synthetic_checks():
    require(target("data/a b/!'()*.rsw") == "/data/a%20b/!'()*.rsw", 'URI safe set')
    require(target('data\\A%?é.gat') == '/data/A%25%3F%C3%A9.gat', 'URI encoding/case')
    require(target('data/a//b') == '/data/a//b', 'empty path segment preservation')
    for raw in ('data/../a', '/data/a', 'data/a\x00'):
        try:
            target(raw)
        except ValueError:
            pass
        else:
            raise ValueError('negative path control accepted')
    for major, minor, extra in ((1, 9, b''), (2, 2, b'x'), (2, 5, b'1234x')):
        fields = [b'x.ini', b"A !'()*.gnd", b'\x80.gat']
        data = b'GRSW' + bytes((major, minor)) + extra + b''.join(f.ljust(40, b'\0') for f in fields)
        got = world_header(data)
        require(got['fixed_offset'] == 6 + len(extra) and got['fields']['gat']['client_string'] == '\x80.gat', 'fixed-field synthetic')
    for raw in (b'GRSW\x02\x05', b'NOPE\x01\x09' + b'\0' * 120):
        try:
            world_header(raw)
        except ValueError:
            pass
        else:
            raise ValueError('negative header control accepted')


def exclusive(path, data):
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
    with os.fdopen(fd, 'wb') as out:
        os.fchmod(out.fileno(), 0o600)
        out.write(data)


class LocalStorageFailure(Exception):
    pass


class PrivateBodyWriter:
    def __init__(self, fd):
        try:
            self.stream = os.fdopen(fd, 'wb')
        except OSError as exc:
            os.close(fd)
            raise LocalStorageFailure('body descriptor wrapping failed') from exc
    def __enter__(self):
        try:
            os.fchmod(self.stream.fileno(), 0o600)
        except OSError as exc:
            self.stream.close()
            raise LocalStorageFailure('body mode setting failed') from exc
        return self
    def write(self, chunk):
        try:
            self.stream.write(chunk)
        except OSError as exc:
            raise LocalStorageFailure('body write failed') from exc
    def __exit__(self, exc_type, exc, tb):
        try:
            self.stream.close()
        except OSError as close_error:
            raise LocalStorageFailure('body close/flush failed') from close_error
        return False


class Acquisition:
    def __init__(self, roots, aliases, pins, sources, self_sha):
        self.aliases, self.proc, self.port, self.total, self.asset_gets = aliases, None, None, 0, 0
        self.deadline, self.cached, self.before, self.halt = None, {}, {}, None
        self.report = {'status': 'DRAFT_ROOT_OBSERVATION_ONLY', 'task': 'T06.003.003.001', 'helper_sha256': self_sha,
                       'metadata_before': pins, 'profile_sha256': PROFILE_SHA, 'source_pins': sources,
                       'roots': [dict(r, server_packet_name=r['name'] + '.gat', renderer_name=r['name'] + '.rsw',
                                      outcome='unattempted', rsw={'outcome': 'unattempted'},
                                      gat={'outcome': 'unattempted'}, gnd={'outcome': 'unattempted'}) for r in roots],
                       'requests': [], 'diagnostics': [], 'inputs_before': {}, 'inputs_after': [],
                       'caps': {'body': BODY_CAP, 'aggregate': TOTAL_CAP, 'asset_gets': GET_CAP, 'seconds': SECONDS, 'io': IO},
                       'limits': 'No archive-owner/codec parity, full geometry/parser/compile, actual client reachability, installed override, render, model/texture or playability proof. Client byte caps do not bound native inflate memory. Native log size is not capped.'}

    def checkpoint(self):
        self.report.update(transferred_bytes=self.total, asset_gets=self.asset_gets, halt=self.halt)
        data = (json.dumps(self.report, ensure_ascii=True, sort_keys=True, indent=2) + '\n').encode()
        fd, name = tempfile.mkstemp(prefix='.report-next-', dir=BASE)
        temporary = Path(name)
        try:
            with os.fdopen(fd, 'wb') as out:
                os.fchmod(out.fileno(), 0o600)
                out.write(data)
            os.replace(temporary, BASE / 'report.json')
        finally:
            # Only the exact private temporary created by this checkpoint.
            if temporary.exists():
                temporary.unlink()

    def listener(self, owned):
        args = ['/usr/sbin/lsof', '-nP', '-iTCP:' + str(self.port), '-sTCP:LISTEN', '-Fpn']
        if owned:
            args[1:1] = ['-a', '-p', str(self.proc.pid)]
        result = subprocess.run(args, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=3)
        require(result.returncode in (0, 1), 'listener inspection failed')
        lines = result.stdout.decode('ascii', 'strict').splitlines()
        if owned:
            return self.proc.poll() is None and 'p' + str(self.proc.pid) in lines and 'n127.0.0.1:' + str(self.port) in lines
        return result.returncode == 0  # Any remaining listener on this exact port fails cleanup.

    def permitted(self):
        if self.halt:
            return self.halt
        if time.monotonic() >= self.deadline:
            self.halt = 'acquisition_deadline'
        elif self.total >= TOTAL_CAP:
            self.halt = 'aggregate_cap'
        elif self.asset_gets >= GET_CAP:
            self.halt = 'asset_get_cap'
        return self.halt

    def get(self, logical, asset=True, cap=BODY_CAP):
        encoded = target(logical)
        if asset and encoded in self.cached:
            return self.cached[encoded]
        row = {'logical': logical, 'http_target': encoded, 'asset': asset, 'outcome': 'unattempted',
               'response_complete': False, 'bytes': 0, 'complete_sha256': None, 'partial_sha256': None}
        rows = self.report['requests'] if asset else self.report['diagnostics']
        row['index'] = len(rows)
        rows.append(row)
        if asset:
            self.cached[encoded] = row
        if self.permitted():
            row['reason'] = self.halt
            return row
        if not self.listener(True):
            self.halt = 'owned_listener_unavailable'
            row['reason'] = self.halt
            return row
        if asset:
            self.asset_gets += 1
        file = ('asset-' if asset else 'diagnostic-') + f'{row["index"]:04d}.bin'
        row['body_file'] = file
        fd = os.open(BASE / file, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        digest, con = hashlib.sha256(), http.client.HTTPConnection(
            '127.0.0.1', self.port, timeout=max(.001, min(IO, self.deadline - time.monotonic())))
        try:
            with PrivateBodyWriter(fd) as out:
                con.request('GET', encoded, headers={'Accept-Encoding': 'identity'})
                response = con.getresponse()
                row['headers_after_deadline'] = time.monotonic() >= self.deadline
                if row['headers_after_deadline']:
                    self.halt = 'acquisition_deadline'
                row['http_status'] = response.status
                row['content_encoding'] = response.getheader('Content-Encoding', 'identity')
                row['content_type'] = response.getheader('Content-Type', '')
                row['declared_length'] = response.getheader('Content-Length')
                row['transfer_encoding'] = response.getheader('Transfer-Encoding')
                row['client_fetch_ok'] = 200 <= response.status < 300 and 'text/html' not in row['content_type']
                require(row['content_encoding'].lower() == 'identity', 'unsupported_content_encoding')
                if response.length is not None and response.length > cap:
                    row['outcome'] = 'declared_length_over_cap'
                    return row
                while True:
                    if response.length == 0:
                        row['response_complete'] = True
                        break
                    if time.monotonic() >= self.deadline:
                        self.halt = 'acquisition_deadline'
                        raise TimeoutError(self.halt)
                    remaining = min(cap - row['bytes'], TOTAL_CAP - self.total)
                    if remaining <= 0:
                        if self.total >= TOTAL_CAP:
                            self.halt = 'aggregate_cap'
                        row['outcome'] = 'cap_unresolved_eof'
                        break  # No over-cap lookahead; exact unframed EOF remains unresolved.
                    if con.sock:
                        con.sock.settimeout(max(.001, min(IO, self.deadline - time.monotonic())))
                    chunk = response.read1(min(65536, remaining))
                    if not chunk:
                        require(response.length in (None, 0), 'truncated_body')
                        row['response_complete'] = True
                        break
                    out.write(chunk)
                    digest.update(chunk)
                    row['bytes'] += len(chunk)
                    self.total += len(chunk)
            if row['response_complete']:
                row['outcome'] = 'complete_200' if response.status == 200 else ('http_404' if response.status == 404 else 'http_non_200')
                row['complete_sha256'] = digest.hexdigest()
                row['body_storage_verified'] = True
        except LocalStorageFailure as exc:
            self.halt = 'local_storage_failure'
            row.update(outcome='local_storage_failure', storage_error=str(exc),
                       response_complete=False, complete_sha256=None, body_storage_verified=False)
        except Exception as exc:
            row.update(outcome=('deadline' if self.halt == 'acquisition_deadline' else 'transport_or_protocol_error'),
                       error_type=type(exc).__name__, error=str(exc)[:200])
        finally:
            con.close()
            if not row['response_complete']:
                row['partial_sha256'] = None if row.get('storage_error') else digest.hexdigest()
            # A final framed chunk may finish after the deadline. Preserve its
            # actual complete-body identity, but never qualify the acquisition.
            if time.monotonic() >= self.deadline:
                self.halt = 'acquisition_deadline'
                row['finished_after_deadline'] = True
        return row

    def prefix(self, row, size=131):
        if 'body_file' not in row:
            return b''
        with (BASE / row['body_file']).open('rb') as stream:
            return stream.read(size)

    def edge(self, request, kind, diagnostic=False):
        edge = {'request': request, 'diagnostic_only': diagnostic,
                'client_reachability': 'not_executed; observation conditional on upstream full parsing/compilation'}
        try:
            require(isinstance(request, str) and request, 'unsupported_empty_field')
            effective = self.aliases.get(request, request)
            require(isinstance(effective, str) and effective, 'unsupported_empty_alias')
            edge.update(alias_key_present=request in self.aliases, effective=effective)
            logical = client_filename('data\\' + effective)
            edge.update(client_filename=logical, predicted_client_parser=client_parser(logical),
                        trim_changed=logical != 'data\\' + effective)
            row = self.get(logical)
            edge.update(request_index=row['index'], outcome=row['outcome'])
            if row['outcome'] != 'complete_200':
                return edge
            if 'text/html' in row.get('content_type', ''):
                edge['outcome'] = 'client_rejects_html_200'
                return edge
            if row['bytes'] == 0:
                edge['outcome'] = 'client_rejects_empty_200'
                return edge
            if edge['predicted_client_parser'] != kind:
                edge['outcome'] = 'unexpected_client_parser'
                edge['diagnostic_only'] = True
                return edge
            data = self.prefix(row)
            if kind == 'rsw':
                edge['header'] = world_header(data)
            else:
                signature = b'GRAT' if kind == 'gat' else b'GRGN'
                require(len(data) >= 6 and data[:4] == signature, 'bad_header: ' + kind)
                edge['header'] = {'signature': data[:4].decode('ascii'), 'version_bytes': list(data[4:6]),
                                  'limits': 'Observed signature/version bytes only; no full parser/compile claim.'}
            edge['outcome'] = 'observed_header'
        except (ValueError, UnicodeError) as exc:
            edge.update(outcome=('bad_header' if str(exc).startswith('bad_header') else 'unsupported'), reason=str(exc)[:200])
        return edge

    def walk(self):
        alias = self.get('data/resnametable.txt')
        self.report['observed_alias_request_index'] = alias['index']
        require(alias['outcome'] == 'complete_200' and alias['complete_sha256'] == ALIAS_SHA, 'observed alias bytes mismatch/unavailable')
        for root in self.report['roots']:
            if self.permitted():
                break
            root['outcome'] = 'started'
            root['rsw'] = self.edge(root['renderer_name'], 'rsw')
            if root['rsw']['outcome'] == 'observed_header':
                fields = root['rsw']['header']['fields']
                root['gat'] = self.edge(fields['gat']['client_string'], 'gat')
                root['gnd'] = self.edge(fields['gnd']['client_string'], 'gnd', root['gat']['outcome'] != 'observed_header')
            else:
                for kind in ('gat', 'gnd'):
                    root[kind] = {'outcome': 'upstream_unavailable', 'reason': 'RSW fixed fields unavailable'}
            root['outcome'] = ('observed_core_header_chain' if all(root[k]['outcome'] == 'observed_header' for k in ('rsw', 'gat', 'gnd')) else 'gap')
            self.checkpoint()

    def run(self):
        os.umask(0o077)
        require(PREP.is_dir() and not PREP.is_symlink() and stat.S_IMODE(PREP.stat().st_mode) == 0o700, 'private preparation directory required')
        BASE.mkdir(mode=0o700)  # Exclusive destination: never adopt old output.
        (BASE / 'resources').mkdir(mode=0o700)
        exclusive(BASE / 'root-manifest-input.json', (RENEWAL / META['roots'][0]).read_bytes())
        self.checkpoint()  # All1296 root records exist before native hashing/GETs.
        try:
            for name, path, pin in NATIVE:
                got = hash_file(path)
                require(got['sha256'] == pin, 'native preflight pin: ' + name)
                self.before[name] = got
                self.report['inputs_before'][name] = got
            ini = ('[Data]\n' + ''.join(f'{i}={path}\n' for i, (_, path, _) in enumerate(NATIVE[1:]))).encode()
            exclusive(BASE / 'resources/DATA.INI', ini)
            self.report['ini_sha256'] = sha(ini)
            with socket.socket() as sock:
                sock.bind(('127.0.0.1', 0))
                self.port = sock.getsockname()[1]
            env = {'PATH': '/usr/bin:/bin:/usr/sbin:/sbin', 'SERVER_ROOT': str(BASE), 'PORT': str(self.port),
                   'HOST': '127.0.0.1', 'NODE_ENV': 'production', 'CLIENT_PUBLIC_URL': f'http://127.0.0.1:{self.port}',
                   'CLIENT_RESPATH': 'resources/', 'CLIENT_DATAINI': str(BASE / 'resources/DATA.INI'),
                   'ENABLE_STATIC_SERVE': 'false', 'ENABLE_WSPROXY': 'false', 'ENABLE_COMPRESSION': 'false',
                   'CACHE_WARM_UP': 'false', 'CLIENT_AUTOEXTRACT': 'false', 'CLIENT_ENABLESEARCH': 'false',
                   'GRF_FILENAME_ENCODING': 'auto', 'CACHE_MAX_MEMORY_MB': '64', 'CACHE_MAX_FILES': '32'}
            with (BASE / 'server.log').open('xb') as log:
                os.fchmod(log.fileno(), 0o600)
                self.proc = subprocess.Popen([str(EXE)], cwd=BASE, env=env, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
            self.report.update(owned_pid=self.proc.pid, owned_pgid=os.getpgid(self.proc.pid), owned_port=self.port, environment=env)
            require(self.report['owned_pgid'] == self.proc.pid, 'new-session identity mismatch')
            self.checkpoint()  # Preserve exact ownership before any readiness/asset GET.
            self.deadline = time.monotonic() + 25  # Separately bounded readiness.
            while not self.listener(True):
                require(self.proc.poll() is None and time.monotonic() < self.deadline, 'reader readiness timeout/exit')
                time.sleep(.15)
            health = self.get('api/health', asset=False, cap=65536)
            require(health['outcome'] == 'complete_200', 'health HTTP failure')
            health_body = json.loads(self.prefix(health, 65536))
            require(health_body.get('status') == 'ok' and health_body.get('service') == 'robrowser-remoteclient', 'health identity')
            self.report['health'] = health_body
            acquisition_start = time.monotonic()
            self.deadline = acquisition_start + SECONDS
            self.walk()
            self.report['acquisition_seconds_observed'] = time.monotonic() - acquisition_start
            if self.report['acquisition_seconds_observed'] > SECONDS:
                self.halt = 'acquisition_deadline'
            require(self.listener(True), 'reader listener lost before finish')
            self.report['acquisition_loop_finished'] = not bool(self.halt)
        except BaseException as exc:
            self.report.update(error_type=type(exc).__name__, error=str(exc)[:300])
        finally:
            self.finish()
        return 0 if self.report.get('acquisition_and_cleanup_valid') else 1

    def finish(self):
        self.report['forced_kill'] = False
        try:
            if self.proc and self.proc.poll() is None:
                self.proc.terminate()  # This Popen child only; never kill by port/name.
                try:
                    self.proc.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    self.report['forced_kill'] = True
                    self.proc.kill()
                    self.proc.wait(timeout=8)
            self.report['owned_exit'] = None if self.proc is None else self.proc.poll()
            self.report['listener_absent'] = self.port is None or not self.listener(False)
            pgid = self.report.get('owned_pgid')
            if pgid is None:
                self.report['owned_pgid_members_after'] = []
            else:
                observed = subprocess.run(['/bin/ps', '-axo', 'pid=,pgid='], stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, timeout=3, check=True).stdout.decode('ascii', 'strict')
                self.report['owned_pgid_members_after'] = [int(parts[0]) for line in observed.splitlines()
                    if len(parts := line.split()) == 2 and int(parts[1]) == pgid]
        except BaseException as exc:
            self.report['cleanup_error'] = type(exc).__name__ + ': ' + str(exc)[:200]
        for name, path, pin in NATIVE:
            try:
                got = hash_file(path)
                equal = got['sha256'] == pin and got == self.before.get(name)
                self.report['inputs_after'].append(dict(input=name, full_hash_identity_equal=equal, **got))
            except BaseException as exc:
                self.report['inputs_after'].append({'input': name, 'error': type(exc).__name__})
        try:
            _, _, pins, sources = metadata()
            self.report['metadata_sources_equal_after'] = pins == self.report['metadata_before'] and sources == self.report['source_pins']
        except BaseException as exc:
            self.report['metadata_after_error'] = type(exc).__name__ + ': ' + str(exc)[:200]
        for root in self.report['roots']:
            if root['outcome'] == 'started':
                root['outcome'] = 'interrupted'
                root['reason'] = self.halt or self.report.get('error', 'acquisition interrupted')
            if root['outcome'] == 'unattempted':
                root['reason'] = self.halt or self.report.get('error', 'acquisition stopped')
            for kind in ('rsw', 'gat', 'gnd'):
                if root[kind]['outcome'] == 'unattempted':
                    root[kind]['reason'] = root[kind].get('reason', root.get('reason', self.halt or 'not attempted'))
        counts = {}
        for root in self.report['roots']:
            counts[root['outcome']] = counts.get(root['outcome'], 0) + 1
        self.report['root_outcome_counts'] = counts
        self.report['enumeration_complete'] = sum(counts.values()) == 1296
        self.report['all_root_chains_observed'] = counts.get('observed_core_header_chain', 0) == 1296
        try:
            self.report['no_extraction'] = not any((BASE / p).exists() or (BASE / p).is_symlink() for p in ('data', 'resources/data'))
            allowed_files = {'root-manifest-input.json', 'resources/DATA.INI', 'server.log', 'report.json'}
            allowed_files.update(r['body_file'] for r in self.report['requests'] + self.report['diagnostics'] if 'body_file' in r)
            actual_files = {str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_file() or p.is_symlink()}
            actual_dirs = {str(p.relative_to(BASE)) for p in BASE.rglob('*') if p.is_dir()}
            self.report['unexpected_files'] = sorted(actual_files - allowed_files)
            self.report['unexpected_directories'] = sorted(actual_dirs - {'resources'})
            self.report['private_modes'] = all(not p.is_symlink() and stat.S_IMODE(p.stat().st_mode) == (0o700 if p.is_dir() else 0o600) for p in [BASE, *BASE.rglob('*')])
        except BaseException as exc:
            self.report.update(file_inventory_error=type(exc).__name__ + ': ' + str(exc)[:200],
                               no_extraction=False, private_modes=False,
                               unexpected_files=['inventory_unavailable'], unexpected_directories=[])
        self.report['acquisition_and_cleanup_valid'] = bool(self.report.get('acquisition_loop_finished') and not self.report.get('error_type')
            and not self.report.get('cleanup_error') and not self.report['forced_kill'] and self.report.get('owned_exit') == 0
            and self.report.get('listener_absent') and self.report.get('owned_pgid_members_after') == []
            and not self.report['unexpected_files'] and not self.report['unexpected_directories']
            and len(self.report['inputs_after']) == 4
            and all(r.get('full_hash_identity_equal') for r in self.report['inputs_after'])
            and self.report.get('metadata_sources_equal_after') and self.report['no_extraction'] and self.report['private_modes'])
        self.checkpoint()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--preflight', action='store_true')
    action.add_argument('--execute', action='store_true')
    parser.add_argument('--root-reviewed-sha256')
    args = parser.parse_args()
    if not args.preflight and not args.execute:
        parser.error('DRAFT refuses by default; root must review before choosing an action')
    self_sha = hash_file(Path(__file__))['sha256']
    if args.execute and args.root_reviewed_sha256 != self_sha:
        parser.error('exact root-reviewed source hash required; this is not a self-qualification')
    roots, aliases, pins, sources = metadata()
    synthetic_checks()
    if args.preflight:
        print(json.dumps({'status': 'metadata_and_authored_synthetic_only', 'helper_sha256': self_sha,
                          'roots': len(roots), 'metadata_pins': pins, 'native_or_archive_read': False,
                          'network_or_native_execution': False, 'limits': 'Not acquisition, production qualification or PASS.'}, sort_keys=True))
        return 0
    return Acquisition(roots, aliases, pins, sources, self_sha).run()


if __name__ == '__main__':
    sys.exit(main())
