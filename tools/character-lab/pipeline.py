#!/usr/bin/env python3
"""Verify and freeze this study. Does not generate art or rewrite approved assets."""
import argparse
import fnmatch
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
import zipfile

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RECIPE = 'tools/character-lab/pipeline/native-art-poc-v0.1.0.json'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text())


def contained(path):
    resolved = path.resolve()
    if not resolved.is_relative_to(ROOT):
        raise ValueError(f'Path is outside this checkout: {path}')
    return resolved


def walk_records(value):
    if isinstance(value, dict):
        if 'file' in value and 'sha256' in value:
            yield value
        for child in value.values():
            yield from walk_records(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_records(child)


def verify(recipe):
    checked = {}
    for relative in recipe['manifests']:
        path = contained(ROOT / relative)
        manifest = read_json(path)
        records = [(contained(path.parent / item['file']), item['sha256']) for item in walk_records(manifest)]
        records += [(contained(ROOT / name.removeprefix('res://')), sha) for name, sha in manifest.get('sourceFiles', {}).items()]
        for file, expected in records:
            actual = digest(file.read_bytes())
            if actual != expected:
                raise ValueError(f'Hash mismatch: {file.relative_to(ROOT)}')
            checked[str(file.relative_to(ROOT))] = actual
    command = ['node', '--test', *recipe['tests']]
    result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    passed = re.search(r'(?:#|ℹ) pass (\d+)', result.stdout)
    evidence = read_json(contained(ROOT / recipe['browserEvidence']))
    return {
        'checkedAt': datetime.now(timezone.utc).isoformat(),
        'assetAndSourceHashesChecked': len(checked),
        'unitTests': {'command': command, 'exitCode': result.returncode, 'passed': int(passed.group(1)) if passed else None, 'output': result.stdout},
        'browserEvidence': {'path': recipe['browserEvidence'], 'sha256': digest((ROOT / recipe['browserEvidence']).read_bytes()), 'observedDate': evidence['date'], 'pixelParity': evidence['pixelParity'], 'freshBrowserRun': False},
        'note': 'Unit tests and recorded asset hashes were checked now. Browser evidence is the saved review of this implementation; no fresh browser run is claimed.'
    }


def snapshot_files(recipe):
    result = {}
    for relative in recipe['snapshotIncludes']:
        path = contained(ROOT / relative)
        if not path.exists():
            raise FileNotFoundError(relative)
        candidates = path.rglob('*') if path.is_dir() else [path]
        for file in candidates:
            if not file.is_file():
                continue
            file = contained(file)
            rel = file.relative_to(ROOT).as_posix()
            if any(fnmatch.fnmatch(rel, pattern) for pattern in recipe['snapshotExcludes']):
                continue
            result[rel] = file
    return dict(sorted(result.items()))


def write_json(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False) + '\n')


def snapshot(recipe, recipe_path):
    output = contained(ROOT / recipe['releaseDirectory'])
    if output.exists():
        raise FileExistsError(f'Version already exists: {output}. Use a new version; snapshots are not overwritten.')
    verification = verify(recipe)
    files = snapshot_files(recipe)
    prefix = f"{recipe['id']}-v{recipe['version']}"
    # Build and validate in a temporary sibling, then publish the local snapshot.
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.snapshot-', dir=output.parent) as temporary:
        temp = Path(temporary)
        archive = temp / 'source.zip'
        records = []
        with zipfile.ZipFile(archive, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as package:
            for relative, file in files.items():
                data = file.read_bytes()
                package.writestr(f'{prefix}/{relative}', data)
                records.append({'path': relative, 'bytes': len(data), 'sha256': digest(data)})
        manifest = {
            'schemaVersion': 1, 'id': recipe['id'], 'version': recipe['version'], 'createdAt': verification['checkedAt'],
            'kind': 'local immutable artifact snapshot', 'gitCommit': None,
            'recipe': str(recipe_path.relative_to(ROOT)), 'recipeSha256': digest(recipe_path.read_bytes()),
            'archive': {'file': 'source.zip', 'sha256': digest(archive.read_bytes()), 'bytes': archive.stat().st_size, 'root': prefix},
            'entryPage': recipe['entryPage'], 'scope': recipe['scope'], 'components': recipe['components'],
            'review': recipe['review'], 'workflow': recipe['workflow'], 'files': records,
            'limits': recipe['limits'], 'validation': {'unitTestsPassed': verification['unitTests']['passed'], 'browserEvidenceFresh': False}
        }
        write_json(temp / 'manifest.json', manifest)
        write_json(temp / 'verification.json', verification)
        (temp / 'SHA256SUMS').write_text(''.join(f'{digest((temp/name).read_bytes())}  {name}\n' for name in ['source.zip', 'manifest.json', 'verification.json']))
        (temp / 'README.md').write_text(f'''# {prefix}

Local snapshot of the Character Lab study, including prior experiment history, native source pairs, generated assets, exact prompts, local compositor, tests, review and workflow notes. This is artifact versioning, not a Git commit or a public release. It excludes the field-map game, bundled Godot binary and generated editor import caches.

Verify archive integrity from the live checkout:

```sh
python3 tools/character-lab/pipeline.py verify-snapshot docs/character-lab/releases/{prefix}/manifest.json
```

Extract `source.zip`, open the `{prefix}` folder, and run:

```sh
python3 -m http.server 8768 --bind 127.0.0.1 --directory tools/character-lab
```

Then open http://127.0.0.1:8768/native.html. All Character Lab browser pages/assets are included. A separate port leaves the current study available.

From the extracted root, run `python3 tools/character-lab/pipeline.py verify` with Python 3.9+ and Node.js installed. Godot exporters require a compatible Godot 4.5.1 installation; the bundled executable is not included. Use `--headless --path . --script <script>` as documented in the workflow. The archived project.godot is included for script execution; this snapshot does not include the field game's main scene.

Change the recipe version and release directory to save the next milestone. This folder is never overwritten by the snapshot command. Hashes prove saved-file integrity; generation from the same prompt is not guaranteed to reproduce the same pixels.
''')
        verify_snapshot(temp / 'manifest.json', quiet=True)
        temp.rename(output)
    print(f'Saved {prefix}: {len(records)} files, {manifest["archive"]["bytes"]:,} compressed bytes')
    print(output / 'manifest.json')


def verify_snapshot(path, quiet=False):
    manifest = read_json(path)
    archive = path.parent / manifest['archive']['file']
    if digest(archive.read_bytes()) != manifest['archive']['sha256']:
        raise ValueError('Snapshot archive hash mismatch')
    prefix = manifest['archive']['root'] + '/'
    expected_names = {prefix + item['path'] for item in manifest['files']}
    with zipfile.ZipFile(archive) as package:
        names = package.namelist()
        if len(names) != len(set(names)) or set(names) != expected_names:
            raise ValueError('Snapshot file inventory mismatch')
        for item in manifest['files']:
            data = package.read(prefix + item['path'])
            if len(data) != item['bytes'] or digest(data) != item['sha256']:
                raise ValueError(f'Snapshot member mismatch: {item["path"]}')
    if not quiet:
        print(f'Verified {manifest["version"]}: archive and all {len(manifest["files"])} file hashes match.')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=['verify', 'snapshot', 'verify-snapshot'])
    parser.add_argument('manifest', nargs='?')
    parser.add_argument('--recipe', default=DEFAULT_RECIPE)
    args = parser.parse_args()
    try:
        if args.command == 'verify-snapshot':
            if not args.manifest:
                parser.error('verify-snapshot requires a manifest.json path')
            verify_snapshot(Path(args.manifest).resolve())
            return
        recipe_path = contained(ROOT / args.recipe)
        recipe = read_json(recipe_path)
        if args.command == 'snapshot':
            snapshot(recipe, recipe_path)
        else:
            result = verify(recipe)
            print(f'PASS: {result["assetAndSourceHashesChecked"]} source/asset hashes; {result["unitTests"]["passed"]} unit tests.')
            print('Browser evidence retained from ' + result['browserEvidence']['observedDate'] + '; not rerun by this command.')
    except (ValueError, OSError, RuntimeError, KeyError) as error:
        print(f'ERROR: {error}', file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
