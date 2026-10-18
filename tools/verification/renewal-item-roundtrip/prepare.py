#!/usr/bin/env python3
"""Stage source-only verifier plus exact private inputs into an ignored folder."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess

CLIENT = '775f8847a8b09749d03c82fcb554e155401d1e02'
INPUT = '0c70abe66e6978c55886b9e4acf8a491028f3c439abc1324cef183577a3e2f19'
VENDORS = {
    'wasmoon-lua5.1.js': '80bed5fb68c5221330af6787629ed651e0b357b0a0f8b2cc8efdcb6a9cc972ee',
    'liblua5.1.wasm': 'cba969b97e8a319eba8996b5df488aed5cdd22a56f2de53b42598e474014e610',
}


def checked(data, expected, label):
    if hashlib.sha256(data).hexdigest() != expected:
        raise ValueError(f'{label}: pinned SHA-256 mismatch')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--client-source', type=Path, required=True)
    parser.add_argument('--item-table', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    # Require an ignored destination before writing private/copied data.
    output = args.output.absolute()
    repo = Path(__file__).resolve().parents[3]
    if not output.is_relative_to(repo):
        parser.error('output must be inside this checkout and ignored by Git')
    relative = output.relative_to(repo)
    ignore = subprocess.run(['git', 'check-ignore', '-q', '--', str(relative)], cwd=repo)
    if ignore.returncode != 0:
        parser.error('output must be ignored by Git')
    if output.exists() or output.is_symlink():
        parser.error('output already exists; choose a new private directory')
    original = checked(args.item_table.read_bytes(), INPUT, 'modern item table')
    vendors = {}
    for name, digest in VENDORS.items():
        data = subprocess.check_output([
            'git', '-C', str(args.client_source), 'show', f'{CLIENT}:src/Vendors/{name}'
        ])
        vendors[name] = checked(data, digest, name)
    # All inputs are validated before creating the no-overwrite output folder.
    output.mkdir(parents=True, exist_ok=False)
    (output / 'vendor').mkdir()
    for name in ['index.html', 'fixture.js', 'canonical.lua', 'lodash-compat.js']:
        shutil.copyfile(Path(__file__).with_name(name), output / name)
    (output / 'iteminfo_new.lub').write_bytes(original)
    for name, data in vendors.items():
        (output / 'vendor' / name).write_bytes(data)
    print(f'Prepared private fixture: {output}')


if __name__ == '__main__':
    main()
