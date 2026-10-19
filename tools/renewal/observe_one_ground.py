"""Root-operated isolated observation of the previously capped ground resource.

T06.003.003.002: frozen metadata and private assets are required. --preflight
reads only metadata/source. --execute needs the exact root-reviewed source SHA,
qualified independent plan review and a new exclusive private destination.
Observed resource/header chains do not establish full map playability.
"""
import argparse
import datetime
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import subprocess
import sys
import types

ROOT = Path(__file__).resolve().parents[2]
PREP = ROOT / '.tools/renewal/t06-map-gap-preparation-1'
BASE = PREP / 'native-one-ground-1'
SOURCE = ROOT / 'tools/renewal/observe_cache_map_cores.py'
SOURCE_SHA = 'ef4f70c965cff19308741041a82bc54fa7d70c87b9069a7cacce7839f6bb7a4f'
PROFILE = ROOT / 'docs/project/fixtures/T06.003.003.002-profile.json'
PROFILE_SHA = '89fd0df477ce6e628d258899faa52ed0273a745a5f7367197423252430c5c059'
NAME, EXPECTED, CAP, TOTAL = 'schg_dun01', 21395470, 24 << 20, 32 << 20
REPORT_PATH = '.tools/renewal/t06-map-core-preparation-1/native-all-cache-map-1/report.json'
AUDIT_PATH = '.tools/renewal/t06-map-core-preparation-1/root-corpus-verification-2/root-result.json'
sha = lambda data: hashlib.sha256(data).hexdigest()


def load_observer():
    # Executed only by a future root invocation. Execute the exact checked bytes,
    # avoiding a check/reopen import race; the pinned module has no main effects.
    fd = os.open(SOURCE, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    with os.fdopen(fd, 'rb') as stream:
        before = os.fstat(stream.fileno())
        if not stat.S_ISREG(before.st_mode) or before.st_size != 32153:
            raise ValueError('observer source type/size')
        data = stream.read(32154)
        after = os.fstat(stream.fileno())
        identity = lambda s: (s.st_dev, s.st_ino, s.st_size, s.st_mtime_ns, s.st_ctime_ns)
        if len(data) != 32153 or identity(before) != identity(after) or identity(after) != identity(SOURCE.lstat()):
            raise ValueError('observer source changed while reading')
    if sha(data) != SOURCE_SHA:
        raise ValueError('observer source pin')
    module = types.ModuleType('_root_owned_observer_reuse')
    module.__file__ = str(SOURCE)
    exec(compile(data, str(SOURCE), 'exec'), module.__dict__)
    return module


def admission(obs):
    data = PROFILE.read_bytes()
    obs.require(sha(data) == PROFILE_SHA, 'target profile pin')
    profile, receipts = json.loads(data), {}
    obs.require((profile['target_root'], profile['target_prior_declared_bytes'], profile['target_body_cap'],
                 profile['target_aggregate_cap'], profile['target_asset_get_cap'],
                 profile['target_acquisition_seconds'], profile['io_timeout_seconds']) ==
                (NAME, EXPECTED, CAP, TOTAL, 4, 120, 5), 'target profile constants')
    for item in profile['inputs']:
        got = obs.hash_file(ROOT / item['path'])
        obs.require(got['sha256'] == item['sha256'] and got['identity'][2] == item['bytes'], 'frozen target input: ' + item['path'])
        receipts[item['path']] = got
    roots, aliases, pins, sources = obs.metadata()  # Metadata/source only.
    data = (ROOT / REPORT_PATH).read_bytes()
    obs.require(sha(data) == receipts[REPORT_PATH]['sha256'], 'prior report reread drift')
    old = json.loads(data)
    data = (ROOT / AUDIT_PATH).read_bytes()
    obs.require(sha(data) == receipts[AUDIT_PATH]['sha256'], 'prior audit reread drift')
    audit = json.loads(data)
    obs.require(audit['independent_root_corpus_audit'] is True and
                audit['complete_report_sha256'] == receipts[REPORT_PATH]['sha256'], 'prior audited context')
    target = next(r for r in old['roots'] if r['name'] == NAME)
    root = next(r for r in roots if r['name'] == NAME)
    obs.require(all(target[k] == root[k] for k in root), 'target root/provenance mismatch')
    prior = {'root': target, 'native_inputs': old['inputs_before'], 'alias': old['requests'][old['observed_alias_request_index']],
             **{kind: old['requests'][target[kind]['request_index']] for kind in ('rsw', 'gat', 'gnd')}}
    obs.require(prior['gnd']['outcome'] == 'declared_length_over_cap' and
                prior['gnd']['declared_length'] == str(EXPECTED) and prior['gnd']['complete_sha256'] is None,
                'prior gap identity')
    obs.require(sum(prior[k]['bytes'] for k in ('alias', 'rsw', 'gat')) + EXPECTED + 65536 < TOTAL, 'context/body budget')
    return root, aliases, pins, sources, receipts, prior


def driver_type(obs):
    class OneGround(obs.Acquisition):
        def __init__(self, context, self_sha):
            root, aliases, pins, sources, receipts, self.prior = context
            super().__init__([root], aliases, pins, sources, self_sha)
            self.target_receipts = receipts
            self.report.update(task='T06.003.003.002', status='ROOT_TARGET_OBSERVATION_ONLY',
                target_inputs_before=receipts, target_profile_sha256=PROFILE_SHA,
                reused_source_sha256=SOURCE_SHA, prior_context=self.prior,
                limits='One isolated observed core/header chain only; no full Ground parsing, native memory cap, installed override, geometry/render/playability or production/PASS claim. Original corpus remains unchanged.')

        def get(self, logical, asset=True, cap=None):
            # Required explicit argument: the original default is bound to16MiB.
            if self.proc is not None:
                obs.require(self.before == self.prior['native_inputs'], 'native input hash/identity changed since original corpus')
                obs.require(self.proc.poll() is None and os.getpgid(self.proc.pid) ==
                            self.report['owned_pgid'] == self.proc.pid, 'owned process-group identity lost')
            return super().get(logical, asset=asset, cap=CAP if cap is None else cap)

        def match_row(self, row, prior):
            obs.require(row['outcome'] == 'complete_200' and row.get('body_storage_verified'), 'context body incomplete')
            for key in ('logical', 'http_target', 'bytes', 'complete_sha256', 'content_encoding', 'content_type'):
                obs.require(row.get(key) == prior.get(key), 'context row mismatch: ' + key)
            actual = obs.hash_file(BASE / row['body_file'])
            obs.require(actual['sha256'] == row['complete_sha256'] and actual['identity'][2] == row['bytes'], 'stored context identity')

        def walk(self):
            alias = self.get('data/resnametable.txt', cap=CAP)
            self.report['observed_alias_request_index'] = alias['index']
            self.match_row(alias, self.prior['alias'])
            obs.require(alias['complete_sha256'] == obs.ALIAS_SHA, 'observed alias mismatch')
            root = self.report['roots'][0]
            root['outcome'] = 'started'
            for kind in ('rsw', 'gat', 'gnd'):
                request = root['renderer_name'] if kind == 'rsw' else root['rsw']['header']['fields'][kind]['client_string']
                edge = self.edge(request, kind)
                root[kind] = edge
                prior_edge = self.prior['root'][kind]
                for key in ('request', 'effective', 'alias_key_present', 'client_filename', 'predicted_client_parser', 'trim_changed', 'diagnostic_only'):
                    obs.require(edge.get(key) == prior_edge.get(key), 'edge context mismatch: ' + kind + '/' + key)
                row = self.report['requests'][edge['request_index']] if 'request_index' in edge else None
                obs.require(edge['outcome'] == 'observed_header' and row is not None, 'target edge not observed: ' + kind)
                if kind != 'gnd':
                    obs.require(edge['header'] == prior_edge['header'], 'raw header context mismatch: ' + kind)
                    self.match_row(row, self.prior[kind])
                else:
                    obs.require(row['http_target'] == self.prior['gnd']['http_target'] and
                                row['logical'] == self.prior['gnd']['logical'], 'GND exact target changed')
                    obs.require(row['outcome'] == 'complete_200' and row['response_complete'] and
                                row.get('body_storage_verified') and row['bytes'] == EXPECTED, 'GND incomplete/size mismatch')
                    actual = obs.hash_file(BASE / row['body_file'])
                    obs.require(actual['sha256'] == row['complete_sha256'] and actual['identity'][2] == EXPECTED, 'stored GND identity')
                    self.report['ground_complete_sha256'] = actual['sha256']
                self.checkpoint()
            root['outcome'] = 'observed_core_header_chain'
            obs.require(self.asset_gets == 4 and len(self.report['requests']) == 4 and len(self.report['diagnostics']) == 1, 'finite GET accounting')

        def logs(self):
            directory, file = BASE / 'logs', BASE / 'logs/missing-files.log'
            failed = [r for r in self.report['requests'] if r.get('http_status') == 404]
            if not directory.exists() and not directory.is_symlink():
                obs.require(not failed, 'missing expected native miss log')
                return {'present': False, 'validated': True}
            obs.require(directory.is_dir() and not directory.is_symlink() and
                        stat.S_IMODE(directory.stat().st_mode) == 0o700, 'diagnostic directory type/mode')
            obs.require(file.lstat().st_size <= 65536, 'diagnostic file size bound')
            receipt = obs.hash_file(file)
            obs.require(receipt['identity'][2] <= 65536 and stat.S_IMODE(file.stat().st_mode) == 0o600 and
                        file.stat().st_nlink == 1, 'diagnostic file bounds/mode/links')
            data = file.read_bytes()
            obs.require(sha(data) == receipt['sha256'] and data.endswith(b'\n'), 'diagnostic bytes/framing')
            lines = data.splitlines()
            obs.require(len(lines) == len(failed) <= 4, 'diagnostic row denominator')
            paths = []
            for line, request in zip(lines, failed):
                obs.require(0 < len(line) <= 4096, 'diagnostic line bound')
                item = json.loads(line)
                obs.require(set(item) == {'timestamp', 'requestedPath', 'grfPath', 'mappedPath'}, 'diagnostic schema')
                obs.require(re.fullmatch(r'\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z', item['timestamp']) is not None, 'diagnostic timestamp')
                datetime.datetime.strptime(item['timestamp'], '%Y-%m-%dT%H:%M:%S.%fZ')
                expected = request['logical'].replace('\\', '/')
                obs.require(item['requestedPath'] == expected and item['grfPath'] == expected.replace('/', '\\') and item['mappedPath'] is None, 'diagnostic request relation')
                paths.append(expected)
            obs.require(len(set(paths)) == len(paths), 'duplicate native miss log')
            return {'present': True, 'validated': True, 'bytes': len(data), 'rows': len(lines), 'sha256': receipt['sha256']}

        def finish(self):
            self.report['forced_kill'] = False
            try:
                if self.proc and self.proc.poll() is None:
                    self.proc.terminate()
                    try:
                        self.proc.wait(timeout=8)
                    except subprocess.TimeoutExpired:
                        self.report['forced_kill'] = True
                        self.proc.kill()  # Owned Popen child only, never by name/port.
                        self.proc.wait(timeout=8)
                self.report['owned_exit'] = None if self.proc is None else self.proc.poll()
                self.report['listener_absent'] = self.port is None or not self.listener(False)
                pgid = self.report.get('owned_pgid')
                text = subprocess.run(['/bin/ps', '-axo', 'pid=,pgid='], stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, timeout=3, check=True).stdout.decode('ascii', 'strict')
                self.report['owned_pgid_members_after'] = [int(p[0]) for line in text.splitlines()
                    if len(p := line.split()) == 2 and int(p[1]) == pgid] if pgid is not None else []
            except BaseException as exc:
                self.report['cleanup_error'] = type(exc).__name__ + ': ' + str(exc)[:200]
            for name, path, pin in obs.NATIVE:
                try:
                    got = obs.hash_file(path)
                    self.report['inputs_after'].append(dict(input=name,
                        full_hash_identity_equal=got['sha256'] == pin and got == self.before.get(name), **got))
                except BaseException as exc:
                    self.report['inputs_after'].append({'input': name, 'error': type(exc).__name__})
            try:
                context = admission(obs)
                self.report['target_metadata_sources_equal_after'] = (context[2] == self.report['metadata_before'] and
                    context[3] == self.report['source_pins'] and context[4] == self.target_receipts and
                    obs.hash_file(Path(__file__))['sha256'] == self.report['helper_sha256'])
                self.report['known_native_log'] = self.logs()
                allowed = {'root-manifest-input.json', 'resources/DATA.INI', 'server.log', 'report.json', 'logs/missing-files.log'}
                allowed.update(r['body_file'] for r in self.report['requests'] + self.report['diagnostics'] if 'body_file' in r)
                entries = list(BASE.rglob('*'))
                self.report['unexpected_files'] = sorted(str(p.relative_to(BASE)) for p in entries if (p.is_file() or p.is_symlink()) and str(p.relative_to(BASE)) not in allowed)
                self.report['unexpected_directories'] = sorted(str(p.relative_to(BASE)) for p in entries if p.is_dir() and str(p.relative_to(BASE)) not in {'resources', 'logs'})
                self.report['private_modes'] = all(not p.is_symlink() and (p.is_file() or p.is_dir()) and stat.S_IMODE(p.stat().st_mode) == (0o700 if p.is_dir() else 0o600) for p in [BASE, *entries])
                self.report['no_extraction'] = not any((BASE / p).exists() or (BASE / p).is_symlink() for p in ('data', 'resources/data'))
            except BaseException as exc:
                self.report['post_audit_error'] = type(exc).__name__ + ': ' + str(exc)[:200]
            root = self.report['roots'][0]
            if root['outcome'] != 'observed_core_header_chain':
                root['outcome'] = 'gap'
                root['reason'] = self.halt or self.report.get('error', 'incomplete target observation')
                for kind in ('rsw', 'gat', 'gnd'):
                    if root[kind]['outcome'] == 'unattempted':
                        root[kind]['reason'] = root['reason']
            self.report['root_count'] = 1
            self.report['observed_core_header_chains'] = int(root['outcome'] == 'observed_core_header_chain')
            self.report['acquisition_and_cleanup_valid'] = bool(self.report.get('acquisition_loop_finished') and
                self.report['observed_core_header_chains'] == 1 and not self.report.get('error_type') and not self.halt and
                not self.report.get('cleanup_error') and not self.report.get('post_audit_error') and not self.report['forced_kill'] and
                self.report.get('owned_exit') == 0 and self.report.get('listener_absent') and self.report.get('owned_pgid_members_after') == [] and
                len(self.report['inputs_after']) == 4 and all(r.get('full_hash_identity_equal') for r in self.report['inputs_after']) and
                self.report.get('target_metadata_sources_equal_after') and self.report.get('known_native_log', {}).get('validated') and
                not self.report.get('unexpected_files') and not self.report.get('unexpected_directories') and self.report.get('private_modes') and self.report.get('no_extraction'))
            self.checkpoint()
    return OneGround


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    action = parser.add_mutually_exclusive_group()
    action.add_argument('--preflight', action='store_true')
    action.add_argument('--execute', action='store_true')
    parser.add_argument('--root-reviewed-sha256')
    args = parser.parse_args()
    if not args.preflight and not args.execute:
        parser.error('choose metadata preflight or root-reviewed execution')
    self_sha = sha(Path(__file__).read_bytes())
    if args.execute and args.root_reviewed_sha256 != self_sha:
        parser.error('exact root-reviewed source SHA required')
    obs = load_observer()
    context = admission(obs)
    obs.synthetic_checks()
    if args.preflight:
        print(json.dumps({'status': 'metadata_and_authored_controls_only', 'helper_sha256': self_sha,
            'target': NAME, 'prior_declared_bytes': EXPECTED, 'native_archive_or_network_access': False}))
        return 0
    obs.PREP, obs.BASE = PREP, BASE
    obs.BODY_CAP, obs.TOTAL_CAP, obs.GET_CAP, obs.SECONDS, obs.IO = CAP, TOTAL, 4, 120, 5
    return driver_type(obs)(context, self_sha).run()


if __name__ == '__main__':
    sys.exit(main())
