#!/usr/bin/env python3
"""Import or reproduce Character Lab art packs from a validated recipe (inspection D14).

  validate RECIPE            check the recipe, every pinned input and the saved packs; writes nothing
  run RECIPE --out DIR       validate, gate every candidate (read-only), import into a fresh
                             directory with the Godot importers, compare reproductions with their
                             saved packs, verify new-art packs against their board and the strict
                             contract, and write reproduction-report.json + REPORT.md there
  lock RECIPE                record "PENDING" hashes that have a file now (style bible, exported boards)
  pin RECIPE --module ID [--candidate res://...]   record a board layout and a generated candidate
  promote RECIPE --from DIR  install new-art packs of a PASSing run (never overwriting)
  coverage res://LOOK.json   per-action, per-direction coverage of an appearance (native fallback explicit)

Recipes of kind "artwork-reproduction-recipe" rebuild saved packs (native-costume-v1,
native-head-v1, slot-board-v1). "artwork-import-recipe" modules (slot-board-v2) import NEW
art from boards written by board_export.gd; nothing saved is needed or compared.

Every Godot call gets an explicit --log-file in a private temporary folder, so
Godot never opens its user:// log directory. Logs are copied to DIR/godot-logs/
once the gate stage has passed; on a refused gate they are discarded with the
temporary folder, and their text is printed instead.

Exit status: 0 reproduced and verified; 1 gate, import or comparison failure;
2 invalid recipe, changed input or unusable output/log directory. Status 2, and
status 1 from the gate stage, mean nothing was written to DIR.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import struct
import subprocess
import sys
import tempfile
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GODOT = '.tools/Godot.app/Contents/MacOS/Godot'
DIRECTIONS = ['S', 'SW', 'W', 'NW', 'N', 'NE', 'E', 'SE']
TEMPLATE = 'res://tools/character-lab/assets/native-template-v1/template.json'
VERIFY_SCRIPT = 'res://tools/character-lab/verify_candidate.gd'
REPORT_JSON = 'reproduction-report.json'
REPORT_MD = 'REPORT.md'
LOG_FOLDER = 'godot-logs'
PNG_SIGNATURE = b'\x89PNG\r\n\x1a\n'
SHA = re.compile(r'[0-9a-f]{64}')
NAME = re.compile(r'[a-z0-9][a-z0-9._-]*')
GATE_LINE = re.compile(r'^GATE_([A-Z]+) (PASS|FAIL)\s*$', re.MULTILINE)

IMPORTERS = 'tools/character-lab/importers'


def _importer_config(name):
    """Configuration shared with the Godot importer (tools/character-lab/importers/<name>.json)."""
    return json.loads((ROOT / IMPORTERS / f'{name}.json').read_text(encoding='utf-8'))


_COSTUME = _importer_config('native-costume-v1')
_HEAD = _importer_config('native-head-v1')
# The two native adapters reproduce the saved packs. Their template, layout, action and
# headgear contract comes from the same configuration files the Godot importers read;
# a recipe must state exactly these values and is rejected otherwise.
ADAPTERS = {
    'native-costume-v1': {
        'script': 'res://tools/character-lab/import_native_costume.gd',
        'config': f'{IMPORTERS}/native-costume-v1.json',
        'manifest': _COSTUME['manifest'], 'part': _COSTUME['part'],
        'layout': _COSTUME['layout'],
        'template': _COSTUME['templateDir'] + 'template.json',
        'action': _COSTUME['recipeContract']['action'],
    },
    'native-head-v1': {
        'script': 'res://tools/character-lab/import_native_head.gd',
        'config': f'{IMPORTERS}/native-head-v1.json',
        'manifest': _HEAD['manifest'], 'part': _HEAD['part'],
        'layout': _HEAD['layout'],
        'template': _HEAD['templateDir'] + 'template.json',
        'equipment': _HEAD['equipmentDir'] + 'equipment.json',
        'variants': _HEAD['variants'],
        'action': _HEAD['recipeContract']['action'],
    },
    # A saved board written by export_slot_board.gd; action and view come from its layout.
    'slot-board-v1': {
        'script': 'res://tools/character-lab/import_slot_board.gd',
        'manifest': 'pack.json', 'part': None,
    },
    # NEW art: any board written by board_export.gd (body or head, any groups and views).
    # Nothing saved is reproduced; the module's own output is verified instead.
    'slot-board-v2': {
        'script': 'res://tools/character-lab/import_slot_board.gd',
        'manifest': 'pack.json', 'part': None, 'newArt': True,
    },
}
# 'reviewed-by-codex' records an automated reviewer's visual pass; only 'accepted' means the user approved.
STATUSES = ('accepted', 'reviewed-by-codex', 'pending-visual-review', 'historical')
GATES = ('strict', 'recorded-failure')
SLOT_USES = ('attack', 'ready', 'idle', 'walk')
GROUP_USE = {'idle': 'idle', 'walk': 'walk', 'ready': 'ready', 'attack2': 'attack', 'attack1': 'attack', 'attack3': 'attack'}
PENDING = 'PENDING'
INSTALL_ROOT = 'tools/character-lab/assets/completion-2026-10-02/packs'
RECIPE_KINDS = ('artwork-reproduction-recipe', 'artwork-import-recipe')
# Code and configuration a run depends on; hashed into every report and re-checked after the run.
CODE_INPUTS = ('tools/character-lab/art_import.gd', 'tools/character-lab/import_native_costume.gd', 'tools/character-lab/import_native_head.gd',
               'tools/character-lab/import_slot_board.gd', 'tools/character-lab/verify_candidate.gd', 'tools/character-lab/slot_contract.gd',
               'tools/character-lab/indexed_import.gd', f'{IMPORTERS}/native-costume-v1.json', f'{IMPORTERS}/native-head-v1.json',
               'scripts/ro_sprite_actor.gd', 'scripts/ro_sprite_data.gd')
TOP_KEYS = {'schemaVersion', 'kind', 'id', 'version', 'description', 'style', 'nativeSources', 'modules', 'coverage', 'decisions'}
MODULE_KEYS = {'id', 'label', 'part', 'adapter', 'status', 'gate', 'recordedFailure', 'output', 'name', 'reproduces',
               'generatedImage', 'template', 'layout', 'equipment', 'fixtureBody', 'action', 'expectedManifestDifferences', 'note'}
NEW_MODULE_KEYS = {'id', 'label', 'part', 'adapter', 'status', 'gate', 'output', 'name', 'install', 'generatedImage', 'layout',
                   'fixtureLook', 'note'}
COVERAGE_KEYS = {'inventory', 'parts'}
COVERAGE_COUNTS = {'total', 'gameplay'}
# Output (and temporary logs) may never land in source assets, evidence, docs or configuration.
PROTECTED_ROOTS = ('assets', 'docs', 'scenes', 'scripts', 'tests', '.git', '.godot', '.tools',
                   'tools/character-lab/assets', 'tools/character-lab/appearances', 'tools/character-lab/characters',
                   'tools/character-lab/pipeline', 'tools/character-lab/qa', 'tools/character-lab/recipes',
                   'tools/character-lab/style', 'tools/character-lab/tests')


class RecipeError(Exception):
    """Invalid recipe, changed input or unusable output directory (exit 2)."""


class RunFailure(Exception):
    """Gate, import or comparison failure (exit 1)."""


def check(condition, message):
    if not condition:
        raise RecipeError(message)


def is_int(value):
    return isinstance(value, int) and not isinstance(value, bool)


def same(a, b):
    """JSON equality that keeps booleans distinct from numbers (True is not 1)."""
    if isinstance(a, bool) or isinstance(b, bool):
        return type(a) is type(b) and a == b
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(same(a[key], b[key]) for key in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(same(x, y) for x, y in zip(a, b))
    return a == b


def sha256_file(path):
    digest = hashlib.sha256()
    with open(path, 'rb') as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b''):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path, where):
    try:
        return json.loads(Path(path).read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        raise RecipeError(f'{where}: cannot read JSON {path}: {error}')


def need(obj, key, kind, where):
    check(isinstance(obj, dict) and key in obj, f'{where}: missing "{key}"')
    value = obj[key]
    check(is_int(value) if kind is int else isinstance(value, kind), f'{where}.{key}: expected {kind.__name__}')
    return value


def ints(value, count, where):
    check(isinstance(value, list) and (count is None or len(value) == count), f'{where}: expected a list of {count} integers')
    result = []
    for item in value:
        check(isinstance(item, (int, float)) and not isinstance(item, bool) and float(item).is_integer(), f'{where}: {item!r} is not an integer')
        result.append(int(item))
    return result


def contained(base, relative, where):
    """Resolve a relative manifest path and require it to stay inside `base`, after symlinks."""
    check(isinstance(relative, str) and relative, f'{where}: expected a relative path')
    parts = PurePosixPath(relative)
    # "", "." and "./" name the base itself, never a file record or input.
    check(len(parts.parts) > 0, f'{where}: path {relative!r} names no file')
    check(not parts.is_absolute() and '..' not in parts.parts and ':' not in parts.parts[0] and '\\' not in relative,
          f'{where}: path {relative!r} must be relative and must not climb out of {base}')
    real_base = Path(base).resolve()
    path = real_base.joinpath(*parts.parts).resolve()
    check(path == real_base or path.is_relative_to(real_base), f'{where}: {relative} resolves outside {real_base} (symlink?)')
    return path


def res_path(root, value, where):
    check(isinstance(value, str) and value.startswith('res://'), f'{where}: expected a res:// path inside this repository, got {value!r}')
    return contained(root, value[len('res://'):], where)


def godot_path(root, path):
    """res:// for paths inside the project, otherwise the absolute path."""
    path = Path(path).resolve()
    try:
        return 'res://' + path.relative_to(root.resolve()).as_posix()
    except ValueError:
        return path.as_posix()


def pin_path(path, expected, label, where, inputs):
    """Require `path` (already boundary-checked) to have the expected SHA-256; record it as a run input."""
    check(expected != PENDING, f'{where}: {label} is still "{PENDING}"; review it, then record it with "art_recipe.py lock"')
    check(isinstance(expected, str) and SHA.fullmatch(expected) is not None, f'{where}: {expected!r} is not a lowercase SHA-256 hex digest')
    check(path.is_file(), f'{where}: missing file {label}')
    actual = sha256_file(path)
    check(actual == expected, f'{where}: {label} changed (sha256 {actual}; pinned {expected})')
    inputs[label] = expected
    return path


def pinned(root, entry, where, inputs):
    """Resolve {"file": res://..., "sha256"} and require the file's bytes to match."""
    file = need(entry, 'file', str, where)
    expected = need(entry, 'sha256', str, where)
    return pin_path(res_path(root, file, where + '.file'), expected, file, where, inputs)


def png_size(path):
    with open(path, 'rb') as handle:
        head = handle.read(24)
    check(len(head) == 24 and head[:8] == PNG_SIGNATURE and head[12:16] == b'IHDR', f'{path} is not a PNG image')
    return list(struct.unpack('>II', head[16:24]))


def file_records(value, path=''):
    """(json path, {"file", "sha256", ...}) for every file record in a manifest."""
    if isinstance(value, dict):
        if isinstance(value.get('file'), str) and isinstance(value.get('sha256'), str):
            yield path, value
        for key, child in value.items():
            yield from file_records(child, f'{path}.{key}' if path else str(key))
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from file_records(child, f'{path}[{index}]')


def record_path(root, pack_dir, record, where='record'):
    """res:// records stay inside the repository; other records stay inside their pack."""
    file = record['file']
    return res_path(root, file, where) if file.startswith('res://') else contained(pack_dir, file, where)


def json_diff(old, new, path=''):
    """[(json path, 'added' | 'removed' | 'changed')] between two parsed manifests."""
    if isinstance(old, dict) and isinstance(new, dict):
        result = []
        for key in sorted(set(old) | set(new)):
            child = f'{path}.{key}' if path else str(key)
            if key not in old:
                result.append((child, 'added'))
            elif key not in new:
                result.append((child, 'removed'))
            else:
                result += json_diff(old[key], new[key], child)
        return result
    if isinstance(old, list) and isinstance(new, list) and len(old) == len(new):
        result = []
        for index, (a, b) in enumerate(zip(old, new)):
            result += json_diff(a, b, f'{path}[{index}]')
        return result
    return [] if same(old, new) else [(path, 'changed')]


def covered(path, allowed):
    return any(path == a or path.startswith(a + '.') or path.startswith(a + '[') for a in allowed)


def protected_location(path, root):
    """Name of the protected repository folder containing `path`, or None."""
    real_root = root.resolve()
    for protected in PROTECTED_ROOTS:
        if path == real_root / protected or path.is_relative_to(real_root / protected):
            return protected
    return None


# ---------------------------------------------------------------- validation

def check_saved_integrity(root, pack_dir, saved, where):
    for path, record in file_records(saved):
        target = record_path(root, pack_dir, record, f'{where} saved record {path}')
        check(target.is_file() and sha256_file(target) == record['sha256'],
              f'{where}: saved evidence {record["file"]} is missing or no longer matches its manifest')


def check_geometry(where, canvas, recipe_slots, layout_slots):
    """layout_slots: [{"index", "imageRect", "cell" (or None), "native": Path}]."""
    got = [(slot['index'], slot['imageRect']) for slot in layout_slots]
    want = [(slot['index'], slot['imageRect']) for slot in recipe_slots]
    check(got == want, f'{where}: layout slots {got} differ from the recipe {want}')
    width, height = canvas
    for slot in layout_slots:
        x, y, w, h = slot['imageRect']
        label = f'{where}: SPR {slot["index"]}'
        check(w > 0 and h > 0 and x >= 0 and y >= 0 and x + w <= width and y + h <= height, f'{label} imageRect {slot["imageRect"]} is outside the {width}x{height} canvas')
        if slot.get('cell') is not None:
            cx, cy, cw, ch = slot['cell']
            check(cx <= x and cy <= y and x + w <= cx + cw and y + h <= cy + ch and cx + cw <= width and cy + ch <= height, f'{label} imageRect leaves its cell {slot["cell"]}')
        check(slot['native'].is_file(), f'{label}: native drawing {slot["native"]} is missing')
        size = png_size(slot['native'])
        check(size == [w, h], f'{label}: crop is {w}x{h} but the native SPR drawing is {size[0]}x{size[1]}; replacement slots must keep native dimensions')


def check_sources(where, files, natives):
    check(isinstance(files, dict) and files, f'{where}: no sourceFiles')
    for file, sha in files.items():
        check(natives.get(file) == sha, f'{where}: native source {file} ({sha}) is not pinned by the recipe nativeSources')


def template_texture(template, part, index, where):
    """The template's own record of a native drawing: {"file", "sha256", "width", "height"}."""
    record = template
    for key in ('parts', part, 'textures', str(index)):
        record = record.get(key) if isinstance(record, dict) else None
    check(isinstance(record, dict) and isinstance(record.get('file'), str) and isinstance(record.get('sha256'), str),
          f'{where}: template has no recorded hash for {part} SPR {index}')
    return record


def validate_costume(root, module, plan_module, adapter, layout, canvas, slots, natives, inputs, saved, palette_sha, where):
    template_entry = need(module, 'template', dict, where)
    check(template_entry.get('file') == adapter['template'], f'{where}: native-costume-v1 only implements template {adapter["template"]}')
    template_path = pinned(root, template_entry, where + '.template', inputs)
    template = read_json(template_path, where + '.template')
    check(isinstance(template, dict), f'{where}: template is not an object')
    check_sources(where + '.template', template.get('sourceFiles'), natives)
    check(ints(layout.get('canvas'), 2, where + ' layout canvas') == canvas, f'{where}: layout canvas differs from the recipe canvas {canvas}')
    layout_slots = []
    for i, slot in enumerate(need(layout, 'slots', list, where + ' layout')):
        label = f'{where} layout slots[{i}]'
        index = need(slot, 'index', int, label)
        source_file = need(slot, 'sourceFile', str, label)
        # The native drawings feed the size gate: pin them with the template's recorded hashes.
        texture = template_texture(template, 'body', index, label)
        check(texture['file'] == source_file, f'{label}: layout uses {source_file}, template records {texture["file"]}')
        native = contained(template_path.parent, source_file, label)
        pin_path(native, texture['sha256'], godot_path(root, native), label, inputs)
        layout_slots.append({'index': index, 'imageRect': ints(slot.get('imageRect'), 4, label + '.imageRect'),
                             'cell': ints(slot.get('cell'), 4, label + '.cell'), 'native': native})
    check_geometry(where, canvas, slots, layout_slots)
    action = module['action']
    check(same(action, adapter['action']), f'{where}: action {json.dumps(action)} is not what native-costume-v1 implements {json.dumps(adapter["action"])}')
    attack = sorted(slot['index'] for slot in slots if 'attack' in slot['use'])
    ready = sorted(slot['index'] for slot in slots if 'ready' in slot['use'])
    check(attack == sorted(set(action['attack']['sequence'])), f'{where}: attack slots {attack} must be exactly the drawings of the attack sequence {sorted(set(action["attack"]["sequence"]))}')
    check(ready == sorted(action['ready']['slots']), f'{where}: ready slots {ready} must be {action["ready"]["slots"]}')
    check(saved.get('slotMetadataSha256') == module['layout']['sha256'], f'{where}: the saved pack was imported with a different slot layout')
    check(saved.get('originalTemplate') == template_entry['file'] and saved.get('originalTemplateSha256') == template_entry['sha256'], f'{where}: the saved pack was imported from a different template')
    check(saved.get('import', {}).get('palette', {}).get('sha256') == palette_sha, f'{where}: the saved pack used a different palette')


def validate_head(root, module, plan_module, adapter, layout, canvas, slots, natives, inputs, saved, palette_sha, where, known):
    template_entry = need(module, 'template', dict, where)
    check(template_entry.get('file') == adapter['template'], f'{where}: native-head-v1 only implements template {adapter["template"]}')
    template_path = pinned(root, template_entry, where + '.template', inputs)
    template = read_json(template_path, where + '.template')
    check(isinstance(template, dict), f'{where}: template is not an object')
    check_sources(where + '.template', template.get('sourceFiles'), natives)
    check(layout.get('sourceTemplateSha256') == template_entry['sha256'], f'{where}: head layout was cut from a different template')
    check(ints(layout.get('canvas'), 2, where + ' layout canvas') == canvas, f'{where}: layout canvas differs from the recipe canvas {canvas}')
    index = need(layout, 'index', int, where + ' layout')
    native_sha = need(layout, 'sourceFileSha256', str, where + ' layout')
    texture = template_texture(template, 'head', index, where + ' layout')
    check(texture['sha256'] == native_sha, f'{where}: head layout and template record different native head drawings')
    native = pinned(root, {'file': need(layout, 'sourceFile', str, where + ' layout'), 'sha256': native_sha}, where + ' native head', inputs)
    layout_slots = [{'index': index, 'imageRect': ints(layout.get('imageRect'), 4, where + ' layout imageRect'),
                     'cell': ints(layout.get('cell'), 4, where + ' layout cell'), 'native': native}]
    check_geometry(where, canvas, slots, layout_slots)
    action = module['action']
    check(same(action, adapter['action']), f'{where}: action {json.dumps(action)} is not what native-head-v1 implements {json.dumps(adapter["action"])}')
    check(same(layout.get('requiredSourceActions', {}).get('attack'), action['attack']['sourceAction']), f'{where}: head layout was prepared for a different attack action')
    equipment = need(module, 'equipment', dict, where)
    check(equipment.get('file') == adapter['equipment'], f'{where}: native-head-v1 only implements equipment {adapter["equipment"]}')
    equipment_path = pinned(root, equipment, where + '.equipment', inputs)
    check(same(equipment.get('variants'), adapter['variants']), f'{where}: equipment variants must be {adapter["variants"]}')
    equipment_manifest = read_json(equipment_path, where + '.equipment')
    check(isinstance(equipment_manifest, dict), f'{where}: equipment manifest is not an object')
    check_sources(where + '.equipment', equipment_manifest.get('sourceFiles'), natives)
    body_id = need(module, 'fixtureBody', str, where)
    body = known.get(body_id)
    check(body is not None and body['adapter'] == 'native-costume-v1', f'{where}: fixtureBody "{body_id}" must name an earlier native-costume-v1 module')
    plan_module['fixtureBody'] = body_id
    plan_module['snapshotDirs'].add(equipment_path.parent)
    check(saved.get('costumeManifest') == body['reproducesPack'] + body['manifestName'], f'{where}: the saved head fixtures were made with body {saved.get("costumeManifest")}, not with module {body_id}')
    check(saved.get('slotMetadataSha256') == module['layout']['sha256'], f'{where}: the saved pack was imported with a different head layout')
    check(saved.get('originalTemplateSha256') == template_entry['sha256'], f'{where}: the saved pack was imported from a different template')
    check(saved.get('equipmentManifestSha256') == equipment['sha256'], f'{where}: the saved pack used a different equipment manifest')
    check(saved.get('import', {}).get('palette', {}).get('sha256') == palette_sha, f'{where}: the saved pack used a different palette')
    check_sources(where + ' saved pack', saved.get('sourceFiles'), natives)


def validate_board(root, module, plan_module, layout_path, layout, canvas, slots, natives, inputs, saved, style, where):
    check(layout.get('part') == module['part'], f'{where}: board part {layout.get("part")!r} differs from module part {module["part"]!r}')
    check(ints(layout.get('canvas'), 2, where + ' layout canvas') == canvas, f'{where}: layout canvas differs from the recipe canvas {canvas}')
    check_sources(where + ' layout', layout.get('sourceFiles'), natives)
    layout_slots = []
    for i, slot in enumerate(need(layout, 'slots', list, where + ' layout')):
        label = f'{where} layout slots[{i}]'
        native = contained(layout_path.parent, need(slot, 'sourceFile', str, label), label)
        pin_path(native, need(slot, 'sourceSha256', str, label), godot_path(root, native), label, inputs)
        layout_slots.append({'index': need(slot, 'index', int, label), 'imageRect': ints(slot.get('imageRect'), 4, label + '.imageRect'),
                             'cell': ints(slot.get('cell'), 4, label + '.cell'), 'native': native})
    check_geometry(where, canvas, slots, layout_slots)
    action = module['action']
    check(set(action) == {'attack'} and isinstance(action['attack'], dict), f'{where}: slot-board-v1 expects one "attack" action entry')
    attack = action['attack']
    sequence = ints(attack.get('sequence'), None, where + '.action.attack.sequence')
    check(is_int(attack.get('groupIndex')) and is_int(attack.get('frameDurationMs')), f'{where}: action.attack needs integer groupIndex and frameDurationMs')
    check(attack.get('group') == layout.get('group') and same(attack.get('groupIndex'), layout.get('groupIndex')), f'{where}: action group differs from the board ({layout.get("group")}, {layout.get("groupIndex")})')
    directions = attack.get('directions')
    check(isinstance(directions, list) and directions and all(name in DIRECTIONS for name in directions), f'{where}: directions must be a list of {DIRECTIONS}')
    check(same(directions, layout.get('view', {}).get('directions')), f'{where}: directions {directions} differ from the board view')
    for name in directions:
        recorded = layout.get('sequences', {}).get(name, {})
        check(same(recorded.get('slots'), sequence), f'{where}: board sequence for {name} is {recorded.get("slots")}, recipe says {sequence}')
        check(same(recorded.get('delayMs'), attack.get('frameDurationMs')), f'{where}: board frame duration for {name} is {recorded.get("delayMs")} ms, recipe says {attack.get("frameDurationMs")}')
    used = sorted(slot['index'] for slot in slots)
    check(used == sorted(set(sequence)), f'{where}: slots {used} must be exactly the drawings of the sequence {sorted(set(sequence))}')
    plan_module['name'] = need(module, 'name', str, where)
    plan_module['boardDir'] = module['layout']['file'].rsplit('/', 1)[0] + '/'
    check(saved.get('board', {}).get('layout') == module['layout']['file'] and saved.get('board', {}).get('sha256') == module['layout']['sha256'], f'{where}: the saved pack was imported from a different board')
    check(saved.get('name') == plan_module['name'], f'{where}: saved pack name is {saved.get("name")!r}, recipe says {plan_module["name"]!r}')
    check(saved.get('contract', {}).get('bible') == style['bible']['file'] and saved.get('contract', {}).get('bibleSha256') == style['bible']['sha256'], f'{where}: the saved pack was gated with a different style bible')
    check(saved.get('import', {}).get('palette', {}).get('sha256') == style['palette']['sha256'], f'{where}: the saved pack used a different palette')


def validate_module(root, module, where, style, bible, natives, inputs, known):
    check(isinstance(module, dict), f'{where}: expected an object')
    if ADAPTERS.get(module.get('adapter'), {}).get('newArt'):
        return validate_new_module(root, module, where, style, bible, natives, inputs, known)
    unknown = sorted(set(module) - MODULE_KEYS)
    check(not unknown, f'{where}: unknown keys {unknown}')
    module_id = need(module, 'id', str, where)
    check(NAME.fullmatch(module_id) is not None, f'{where}.id: use lowercase letters, digits, ".", "-" or "_"')
    check(module_id not in known, f'{where}: duplicate module id {module_id}')
    where = f'module {module_id}'
    adapter_name = need(module, 'adapter', str, where)
    check(adapter_name in ADAPTERS, f'{where}: unknown adapter {adapter_name!r}; known: {sorted(ADAPTERS)}')
    adapter = ADAPTERS[adapter_name]
    part = need(module, 'part', str, where)
    check(adapter['part'] in (None, part), f'{where}: adapter {adapter_name} imports part {adapter["part"]!r}, not {part!r}')
    check(part in bible.get('slotRules', {}), f'{where}: the style bible has no slot rules for part {part!r}')
    status = need(module, 'status', str, where)
    check(status in STATUSES, f'{where}: status must be one of {list(STATUSES)}')
    gate = need(module, 'gate', str, where)
    check(gate in GATES, f'{where}: gate must be one of {list(GATES)}')
    if gate == 'recorded-failure':
        check(status == 'historical', f'{where}: only a historical module may record a gate failure; accepted and pending modules must pass the strict gate')
        failure = need(module, 'recordedFailure', dict, where)
        for key in ('since', 'reason', 'replacement'):
            check(isinstance(failure.get(key), str) and failure[key].strip(), f'{where}.recordedFailure.{key}: required text')
    else:
        check('recordedFailure' not in module, f'{where}: recordedFailure only belongs to gate "recorded-failure"')
    output = need(module, 'output', str, where)
    check(NAME.fullmatch(output) is not None, f'{where}.output: must be a plain directory name')
    reproduces = need(module, 'reproduces', dict, where)
    pack_res = need(reproduces, 'pack', str, where + '.reproduces').rstrip('/') + '/'
    manifest_name = need(reproduces, 'manifest', str, where + '.reproduces')
    check(manifest_name == adapter['manifest'], f'{where}: adapter {adapter_name} writes {adapter["manifest"]}, not {manifest_name}')
    pack_dir = res_path(root, pack_res.rstrip('/'), where + '.reproduces.pack')
    check(output == PurePosixPath(pack_res.rstrip('/')).name == pack_dir.name, f'{where}: output "{output}" must keep the saved pack name "{pack_dir.name}"; a reproduction is never relabelled as another version')
    manifest_path = contained(pack_dir, manifest_name, where + '.reproduces.manifest')
    check(manifest_path.is_file(), f'{where}: saved pack manifest {pack_res}{manifest_name} is missing')
    saved = read_json(manifest_path, where + ' saved manifest')
    check(isinstance(saved, dict), f'{where}: saved manifest is not an object')
    check_saved_integrity(root, pack_dir, saved, where)
    generated = need(module, 'generatedImage', dict, where)
    generated_path = pinned(root, generated, where + '.generatedImage', inputs)
    size = ints(generated.get('size'), 2, where + '.generatedImage.size')
    actual = png_size(generated_path)
    check(actual == size, f'{where}: generated image is {actual[0]}x{actual[1]}, recipe says {size[0]}x{size[1]}')
    check(saved.get('sourceImage') == generated['file'] and saved.get('sourceImageSha256') == generated['sha256'], f'{where}: the saved pack was imported from {saved.get("sourceImage")}, not from the recipe image')
    layout_entry = need(module, 'layout', dict, where)
    layout_path = pinned(root, layout_entry, where + '.layout', inputs)
    canvas = ints(layout_entry.get('canvas'), 2, where + '.layout.canvas')
    check(canvas[0] > 0 and canvas[1] > 0, f'{where}: empty canvas')
    check(size[0] * canvas[1] == size[1] * canvas[0], f'{where}: generated image {size[0]}x{size[1]} does not have the aspect ratio of the {canvas[0]}x{canvas[1]} slot canvas; the whole board is rescaled once, so every slot would be misplaced')
    slots = []
    for i, slot in enumerate(need(layout_entry, 'slots', list, where + '.layout')):
        label = f'{where}.layout.slots[{i}]'
        use = slot.get('use') if isinstance(slot, dict) else None
        check(isinstance(use, list) and use and all(item in SLOT_USES for item in use), f'{label}.use: list of {list(SLOT_USES)}')
        slots.append({'index': need(slot, 'index', int, label), 'use': use, 'imageRect': ints(slot.get('imageRect'), 4, label + '.imageRect')})
    check(slots, f'{where}: no slots')
    indices = [slot['index'] for slot in slots]
    check(len(set(indices)) == len(indices), f'{where}: duplicate slot indexes {indices}')
    check(isinstance(module.get('action'), dict), f'{where}: missing "action"')
    differences = need(module, 'expectedManifestDifferences', list, where)
    for i, item in enumerate(differences):
        check(isinstance(item, dict) and isinstance(item.get('path'), str) and item['path'] and isinstance(item.get('reason'), str) and item['reason'].strip(), f'{where}.expectedManifestDifferences[{i}]: needs "path" and "reason"')
    layout = read_json(layout_path, where + '.layout')
    check(isinstance(layout, dict), f'{where}: layout is not an object')
    plan_module = {
        'id': module_id, 'label': module.get('label', module_id), 'part': part, 'adapter': adapter_name, 'status': status, 'gate': gate,
        'recordedFailure': module.get('recordedFailure'), 'output': output, 'packDir': pack_dir, 'reproducesPack': pack_res,
        'manifestName': manifest_name, 'saved': saved, 'generatedFile': generated['file'], 'slots': slots, 'action': module['action'],
        'expectedDifferences': differences, 'snapshotDirs': {pack_dir, generated_path.parent, layout_path.parent},
    }
    if adapter_name == 'native-costume-v1':
        check(layout_entry['file'] == adapter['layout'], f'{where}: native-costume-v1 only imports its saved layout {adapter["layout"]}; use slot-board-v1 for other boards')
        validate_costume(root, module, plan_module, adapter, layout, canvas, slots, natives, inputs, saved, style['palette']['sha256'], where)
    elif adapter_name == 'native-head-v1':
        check(layout_entry['file'] == adapter['layout'], f'{where}: native-head-v1 only imports its saved layout {adapter["layout"]}')
        validate_head(root, module, plan_module, adapter, layout, canvas, slots, natives, inputs, saved, style['palette']['sha256'], where, known)
    else:
        validate_board(root, module, plan_module, layout_path, layout, canvas, slots, natives, inputs, saved, style, where)
    if 'template' in module:
        plan_module['snapshotDirs'].add(res_path(root, module['template']['file'], where).parent)
    return plan_module


def is_legacy_board(layout):
    """A board written by export_slot_board.gd (one group, one drawn view, no fixture plan)."""
    return isinstance(layout, dict) and layout.get('schemaVersion') == 1 and 'fixtures' not in layout \
        and isinstance(layout.get('sequences'), dict) and isinstance(layout.get('view'), dict)


def board_geometry(layout, where):
    """(canvas, [(index, imageRect)]) of a sprite-slots.json board or a single-slot head-slot.json layout."""
    check(isinstance(layout, dict), f'{where}: layout is not an object')
    canvas = ints(layout.get('canvas'), 2, where + ' canvas')
    if isinstance(layout.get('slots'), list):
        return canvas, [(need(s, 'index', int, where), ints(s.get('imageRect'), 4, where + ' imageRect')) for s in layout['slots']]
    return canvas, [(need(layout, 'index', int, where), ints(layout.get('imageRect'), 4, where + ' imageRect'))]


def expected_fixtures(layout, part):
    """[(key, frames, delayMs or None, sourceAction)] the importer must render, and problems with the board's timeline.
    Fixtures follow the BODY timeline (a head repeats its frames modulo the body's), so head boards
    must record the body frame count and delay; a board without them cannot be verified."""
    expected, problems = [], []
    if is_legacy_board(layout):
        for name in layout['view']['directions']:
            sequence = layout['sequences'].get(name, {})
            # Old fixtures record no frame duration; one body layer per frame.
            expected.append((name, len(sequence.get('slots', [])), None, layout['groupIndex'] * 8 + DIRECTIONS.index(name)))
        return expected, problems
    for fixture in layout['fixtures']:
        for name in fixture['directions']:
            sequence = layout.get('groupSequences', {}).get(fixture['group'], {}).get(name)
            if not isinstance(sequence, dict):
                problems.append(f'board records no sequence for {fixture["group"]}/{name}')
                continue
            frames = sequence.get('bodyFrames', sequence.get('frames') if part == 'body' else None)
            delay = sequence.get('bodyDelayMs', sequence.get('delayMs') if part == 'body' else None)
            if not is_int(frames) or frames <= 0 or delay is None:
                problems.append(f'board records no body timeline for {fixture["group"]}/{name} (re-export it with the current board_export.gd)')
                continue
            for gear in fixture['headgear']:
                expected.append((f'{fixture["group"]}/{name}/{gear}', frames, delay, fixture['groupIndex'] * 8 + DIRECTIONS.index(name)))
    return expected, problems


def validate_new_module(root, module, where, style, bible, natives, inputs, known):
    """A module that imports NEW art from a board_export.gd board. No saved pack is reproduced."""
    unknown = sorted(set(module) - NEW_MODULE_KEYS)
    check(not unknown, f'{where}: unknown keys {unknown} for a new-art module')
    module_id = need(module, 'id', str, where)
    check(NAME.fullmatch(module_id) is not None, f'{where}.id: use lowercase letters, digits, ".", "-" or "_"')
    check(module_id not in known, f'{where}: duplicate module id {module_id}')
    where = f'module {module_id}'
    adapter_name = module['adapter']
    part = need(module, 'part', str, where)
    check(part in bible.get('slotRules', {}), f'{where}: the style bible has no slot rules for part {part!r}')
    status = need(module, 'status', str, where)
    check(status in STATUSES and status != 'historical', f'{where}: status must be one of {[s for s in STATUSES if s != "historical"]}')
    check(need(module, 'gate', str, where) == 'strict', f'{where}: new art must pass the strict gate')
    output = need(module, 'output', str, where)
    check(NAME.fullmatch(output) is not None, f'{where}.output: must be a plain directory name')
    install = None
    if 'install' in module:
        install_res = need(module, 'install', str, where).rstrip('/')
        install = res_path(root, install_res, where + '.install')
        check(install.is_relative_to(res_path(root, 'res://' + INSTALL_ROOT, 'install root')) and install.name == output,
              f'{where}.install: must be res://{INSTALL_ROOT}/{output}')
    # Board layout: pinned, made by board_export.gd, for this part, style bible and character.
    layout_entry = need(module, 'layout', dict, where)
    check(str(layout_entry.get('file', '')).endswith('/sprite-slots.json'), f'{where}.layout.file: must be a board sprite-slots.json')
    board_dir = layout_entry['file'].rsplit('/', 1)[0] + '/'
    look = module.get('fixtureLook', {})
    if layout_entry.get('sha256') == PENDING:
        # Board not exported yet: only the intended drawings are declared; "pin" fills in the rest.
        check(need(module, 'generatedImage', dict, where).get('sha256') == PENDING, f'{where}: pin the board layout before a candidate')
        declared = []
        for i, slot in enumerate(need(layout_entry, 'slots', list, where + '.layout')):
            label = f'{where}.layout.slots[{i}]'
            use = slot.get('use') if isinstance(slot, dict) else None
            check(isinstance(use, list) and use and all(item in SLOT_USES for item in use), f'{label}.use: list of {list(SLOT_USES)}')
            declared.append({'index': need(slot, 'index', int, label), 'use': use, 'imageRect': None})
        check(declared and len({s['index'] for s in declared}) == len(declared), f'{where}: declare each intended drawing once')
        return {'id': module_id, 'label': module.get('label', module_id), 'part': part, 'adapter': adapter_name, 'status': status, 'gate': 'strict',
                'newArt': True, 'pending': True, 'output': output, 'install': install, 'installRes': module.get('install'), 'manifestName': 'pack.json',
                'generatedFile': None, 'slots': declared, 'boardDir': board_dir, 'layout': {}, 'name': module.get('name'),
                'fixtureLook': {'appearance': look.get('appearance'), 'modules': look.get('modules', [])}, 'expectedDifferences': [], 'action': {}, 'snapshotDirs': set()}
    layout_path = pinned(root, layout_entry, where + '.layout', inputs)
    layout = read_json(layout_path, where + '.layout')
    check(isinstance(layout, dict), f'{where}: layout is not an object')
    legacy = is_legacy_board(layout)
    check(legacy or (layout.get('schemaVersion') == 2 and layout.get('kind') == 'slot-board' and isinstance(layout.get('fixtures'), list) and layout['fixtures']),
          f'{where}: {layout_entry["file"]} is neither a board_export.gd board (schemaVersion 2 with a fixture plan) nor an export_slot_board.gd board')
    check(layout.get('part') == part, f'{where}: board part {layout.get("part")!r} differs from module part {part!r}')
    if legacy:
        # export_slot_board.gd boards record no style bible, character or fixture plan: the
        # recipe's bible gates them, and fixtures cover the board's one group and view.
        check(part == 'body', f'{where}: an export_slot_board.gd board can only be imported as body art (its fixtures follow the board\'s own timeline)')
        check(layout.get('group') in GROUP_USE and is_int(layout.get('groupIndex')) and isinstance(layout.get('view', {}).get('directions'), list), f'{where}: legacy board lacks group/view')
    else:
        check(layout.get('styleBible') == style['bible']['file'] and layout.get('styleBibleSha256') == style['bible']['sha256'], f'{where}: the board was exported with another style bible than the recipe pins')
        character = layout.get('character')
        pinned(root, {'file': character, 'sha256': layout.get('characterSha256')}, where + ' character spec', inputs)
        for k, reference in enumerate(layout.get('boards', {}).get('designReferences', [])):
            pinned(root, {'file': reference.get('from'), 'sha256': reference.get('fromSha256')}, f'{where} design reference {k + 1}', inputs)
    check_sources(where + ' layout', layout.get('sourceFiles'), natives)
    canvas = ints(layout_entry.get('canvas'), 2, where + '.layout.canvas')
    check(ints(layout.get('canvas'), 2, where + ' layout canvas') == canvas, f'{where}: layout canvas differs from the recipe canvas {canvas}')
    board_groups = [layout.get('group')] if legacy else layout.get('groups', [])
    allowed_uses = {GROUP_USE.get(name) for name in board_groups} - {None}
    slots = []
    for i, slot in enumerate(need(layout_entry, 'slots', list, where + '.layout')):
        label = f'{where}.layout.slots[{i}]'
        use = slot.get('use') if isinstance(slot, dict) else None
        check(isinstance(use, list) and use and all(item in allowed_uses for item in use), f'{label}.use: list of {sorted(allowed_uses)} (the board groups)')
        slots.append({'index': need(slot, 'index', int, label), 'use': use, 'imageRect': ints(slot.get('imageRect'), 4, label + '.imageRect')})
    check(slots, f'{where}: no slots')
    indices = [slot['index'] for slot in slots]
    check(len(set(indices)) == len(indices), f'{where}: duplicate slot indexes {indices}')
    layout_slots = []
    for i, slot in enumerate(need(layout, 'slots', list, where + ' layout')):
        label = f'{where} layout slots[{i}]'
        native = contained(layout_path.parent, need(slot, 'sourceFile', str, label), label)
        pin_path(native, need(slot, 'sourceSha256', str, label), godot_path(root, native), label, inputs)
        layout_slots.append({'index': need(slot, 'index', int, label), 'imageRect': ints(slot.get('imageRect'), 4, label + '.imageRect'),
                             'cell': ints(slot.get('cell'), 4, label + '.cell'), 'native': native})
    check_geometry(where, canvas, slots, layout_slots)
    # Candidate: pinned, or explicitly pending until art_recipe.py pin records it.
    generated = need(module, 'generatedImage', dict, where)
    pending = generated.get('sha256') == PENDING
    generated_file = generated.get('file')
    if not pending:
        generated_path = pinned(root, generated, where + '.generatedImage', inputs)
        if 'generatedOn' in generated:
            # Generated on another (e.g. older) board: allowed only with identical geometry.
            other_path = pinned(root, need(generated, 'generatedOn', dict, where + '.generatedImage'), where + '.generatedImage.generatedOn', inputs)
            other_canvas, other_slots = board_geometry(read_json(other_path, where + '.generatedImage.generatedOn'), where + '.generatedImage.generatedOn')
            check(other_canvas == canvas and other_slots == [(s['index'], s['imageRect']) for s in slots],
                  f'{where}: the candidate was generated on {generated["generatedOn"].get("file")} (canvas {other_canvas}, slots {other_slots}), which differs from this board; regenerate on this board')
        else:
            check(generated_path.is_relative_to(layout_path.parent / 'candidates'), f'{where}: candidates live in the board\'s candidates/ folder (or name the board they were generated on in generatedImage.generatedOn)')
        size = ints(generated.get('size'), 2, where + '.generatedImage.size')
        actual = png_size(generated_path)
        check(actual == size, f'{where}: generated image is {actual[0]}x{actual[1]}, recipe says {size[0]}x{size[1]}')
        check(size[0] * canvas[1] == size[1] * canvas[0], f'{where}: generated image {size[0]}x{size[1]} does not have the aspect ratio of the {canvas[0]}x{canvas[1]} board')
    # Fixture look: other parts drawn in the fixtures (an appearance and/or earlier modules).
    check(not (legacy and look), f'{where}.fixtureLook: export_slot_board.gd boards render fixtures with native other parts only')
    check(isinstance(look, dict) and set(look) <= {'appearance', 'modules'}, f'{where}.fixtureLook: expected {{"appearance", "modules"}}')
    look_modules = look.get('modules', [])
    check(isinstance(look_modules, list) and all(isinstance(i, str) for i in look_modules), f'{where}.fixtureLook.modules: list of module ids')
    for other in look_modules:
        check(other in known and known[other].get('newArt'), f'{where}.fixtureLook: "{other}" must be an earlier new-art module (its drawings sit under this module\'s in the fixtures)')
    look_appearance = look.get('appearance')
    if look_appearance is not None:
        check(res_path(root, look_appearance, where + '.fixtureLook.appearance').is_file(), f'{where}.fixtureLook.appearance: {look_appearance} is missing')
    return {
        'id': module_id, 'label': module.get('label', layout.get('label', module_id)), 'part': part, 'adapter': adapter_name, 'status': status, 'gate': 'strict',
        'newArt': True, 'pending': pending, 'output': output, 'install': install, 'installRes': module.get('install'), 'manifestName': 'pack.json',
        'generatedFile': generated_file, 'slots': slots, 'boardDir': board_dir, 'layout': layout, 'name': module.get('name'),
        'fixtureLook': {'appearance': look_appearance, 'modules': look_modules}, 'expectedDifferences': [], 'action': {},
        'snapshotDirs': {layout_path.parent},
    }


def validate_coverage(root, recipe, modules):
    """Coverage numbers feed the report only, but are validated before anything is written."""
    coverage = recipe.get('coverage', {})
    check(isinstance(coverage, dict), 'recipe.coverage: expected an object')
    unknown = sorted(set(coverage) - COVERAGE_KEYS)
    check(not unknown, f'recipe.coverage: unknown keys {unknown}')
    parts = coverage.get('parts', {})
    check(isinstance(parts, dict), 'recipe.coverage.parts: expected an object')
    for part, counts in parts.items():
        where = f'recipe.coverage.parts.{part}'
        check(isinstance(counts, dict) and 'total' in counts and set(counts) <= COVERAGE_COUNTS, f'{where}: expected {{"total"[, "gameplay"]}}')
        for key, value in counts.items():
            check(is_int(value) and value > 0, f'{where}.{key}: expected a positive integer')
        check(counts.get('gameplay', 0) <= counts['total'], f'{where}: gameplay drawings exceed the total')
    for m in modules:
        check(m['part'] in parts, f'recipe.coverage.parts: no declared drawing total for part {m["part"]!r} (module {m["id"]})')
    for part in parts:
        indices = {slot['index'] for m in modules if m['part'] == part for slot in m['slots']}
        check(len(indices) <= parts[part]['total'], f'recipe.coverage.parts.{part}: modules cover {len(indices)} drawings, more than the declared total')
    result = {'parts': parts, 'inventory': None, 'inventoryChecked': False, 'notes': []}
    inventory = coverage.get('inventory')
    if inventory is None:
        result['notes'].append('No slot inventory is referenced; drawing totals are the recipe declaration only.')
        return result
    path = res_path(root, inventory, 'recipe.coverage.inventory')
    result['inventory'] = inventory
    if not path.is_file():
        result['notes'].append(f'Slot inventory {inventory} is not available; drawing totals are the recipe declaration only.')
        return result
    data = read_json(path, 'recipe.coverage.inventory')
    check(isinstance(data, dict) and isinstance(data.get('parts'), dict), 'recipe.coverage.inventory: expected {"parts": {...}}')
    for part, counts in parts.items():
        entry = data['parts'].get(part)
        count = entry.get('uniqueSlotCount') if isinstance(entry, dict) else None
        check(is_int(count), f'recipe.coverage.inventory: no uniqueSlotCount for part {part!r}')
        check(count == counts['total'], f'recipe.coverage.parts.{part}.total is {counts["total"]}, but the slot inventory lists {count}')
    result['inventoryChecked'] = True
    result['notes'].append(f'Drawing totals match the slot inventory {inventory}.')
    return result


def load_plan(recipe_path, root=ROOT, selected=None):
    """Validate everything without writing. Raises RecipeError."""
    recipe_path = Path(recipe_path).resolve()
    check(recipe_path.is_file(), f'Recipe not found: {recipe_path}')
    # Hash and parse one read of the bytes, so recipeSha256 names exactly what is validated.
    try:
        recipe_bytes = recipe_path.read_bytes()
        recipe = json.loads(recipe_bytes.decode('utf-8'))
    except (OSError, ValueError) as error:
        raise RecipeError(f'recipe: cannot read JSON {recipe_path}: {error}')
    recipe_sha = hashlib.sha256(recipe_bytes).hexdigest()
    check(isinstance(recipe, dict), 'recipe: top level must be an object')
    unknown = sorted(set(recipe) - TOP_KEYS)
    check(not unknown, f'recipe: unknown keys {unknown}')
    check(is_int(recipe.get('schemaVersion')) and recipe['schemaVersion'] == 1, 'recipe: schemaVersion must be the integer 1')
    check(recipe.get('kind') in RECIPE_KINDS, f'recipe: kind must be one of {list(RECIPE_KINDS)}')
    need(recipe, 'id', str, 'recipe')
    need(recipe, 'version', str, 'recipe')
    inputs = {}
    style = need(recipe, 'style', dict, 'recipe')
    bible_path = pinned(root, need(style, 'bible', dict, 'style'), 'style.bible', inputs)
    palette_path = pinned(root, need(style, 'palette', dict, 'style'), 'style.palette', inputs)
    bible = read_json(bible_path, 'style.bible')
    check(isinstance(bible, dict) and isinstance(bible.get('palette'), dict) and isinstance(bible.get('slotRules'), dict), 'style.bible: needs a palette reference and slotRules')
    check(bible['palette'].get('file') == style['palette']['file'] and bible['palette'].get('sha256') == style['palette']['sha256'], 'style.palette differs from the palette the style bible references')
    natives = need(recipe, 'nativeSources', dict, 'recipe')
    check(natives, 'recipe: nativeSources is empty')
    for file, sha in natives.items():
        pinned(root, {'file': file, 'sha256': sha}, f'nativeSources[{file}]', inputs)
    modules = need(recipe, 'modules', list, 'recipe')
    check(modules, 'recipe: no modules')
    known = {}
    for i, module in enumerate(modules):
        plan_module = validate_module(root, module, f'modules[{i}]', style, bible, natives, inputs, known)
        known[plan_module['id']] = plan_module
    outputs = [m['output'] for m in known.values()]
    check(len(set(outputs)) == len(outputs), f'recipe: duplicate outputs {outputs}')
    decisions = recipe.get('decisions', [])
    check(isinstance(decisions, list) and all(isinstance(item, str) for item in decisions), 'recipe.decisions: list of text')
    if selected:
        missing = sorted(set(selected) - set(known))
        check(not missing, f'Unknown module(s) {missing}; recipe has {sorted(known)}')
        chosen = [m for m in known.values() if m['id'] in selected]
        for m in chosen:
            check(m.get('fixtureBody') in (None, *selected), f'module {m["id"]} renders its fixtures on module {m.get("fixtureBody")}; select it as well')
            for other in m.get('fixtureLook', {}).get('modules', []):
                check(other in selected, f'module {m["id"]} renders its fixtures on module {other}; select it as well')
    else:
        chosen = list(known.values())
    code_inputs = {}
    for relative in CODE_INPUTS:
        path = ROOT / relative
        check(path.is_file(), f'Workflow code missing: {relative}')
        code_inputs[relative] = sha256_file(path)
    coverage = validate_coverage(root, recipe, list(known.values()))
    snapshot_dirs = {root / 'tools/character-lab/appearances', bible_path.parent, palette_path.parent}
    for m in known.values():
        snapshot_dirs |= m['snapshotDirs']
    snapshot_files = {res_path(root, file, 'nativeSources') for file in natives}
    if coverage['inventory']:
        snapshot_files.add(res_path(root, coverage['inventory'], 'coverage.inventory'))
    try:
        current = sha256_file(recipe_path)
    except OSError:
        current = None
    check(current == recipe_sha, f'Recipe {recipe_path} changed during validation; validate it again')
    return {'recipe': recipe, 'recipePath': recipe_path, 'recipeSha256': recipe_sha, 'root': root,
            'inputs': inputs, 'codeInputs': code_inputs, 'modules': chosen, 'byId': known, 'bibleFile': style['bible']['file'], 'coverage': coverage,
            'snapshotDirs': sorted(snapshot_dirs), 'snapshotFiles': sorted(snapshot_files)}


def check_output_dir(value, root=ROOT):
    out = Path(value).expanduser()
    out = (out if out.is_absolute() else Path.cwd() / out).resolve()
    real_root = root.resolve()
    check(not (out == real_root or real_root.is_relative_to(out)), f'Output directory {out} contains the repository')
    protected = protected_location(out, root)
    check(protected is None, f'Output directory {out} is inside protected {protected}/; choose a new isolated directory')
    if out.exists():
        check(out.is_dir() and not any(out.iterdir()), f'Output directory {out} already exists and is not empty; reproductions never overwrite')
    return out


def log_parent(value, out, root=ROOT):
    """Folder for the private temporary Godot log folder (default: the system temporary folder)."""
    parent = Path(value or os.environ.get('ART_RECIPE_LOG_DIR') or tempfile.gettempdir()).expanduser().resolve()
    check(parent.is_dir(), f'Log folder {parent} does not exist (use --log-dir or ART_RECIPE_LOG_DIR)')
    check(not (parent == out or parent.is_relative_to(out)), f'Log folder {parent} must not be inside the output directory, which is only created after the gates pass')
    protected = protected_location(parent, root)
    check(protected is None, f'Log folder {parent} is inside protected {protected}/')
    return parent


def find_godot(value, root=ROOT):
    godot = Path(value or os.environ.get('GODOT') or root / DEFAULT_GODOT)
    check(godot.is_file() and os.access(godot, os.X_OK), f'Godot executable not found: {godot} (use --godot or GODOT)')
    return godot


def snapshot(plan):
    """Hashes of saved packs, inputs and their folders, to prove the run changed none of them."""
    root = plan['root']
    result = {}
    files = set(plan['snapshotFiles'])
    for directory in plan['snapshotDirs']:
        if directory.is_dir():
            files |= {path for path in directory.rglob('*') if path.is_file()}
    for path in files:
        if path.is_file():
            result[godot_path(root, path)] = sha256_file(path)
    return result


# ------------------------------------------------------------- gate / import

def run_godot(godot, root, script, arguments, timeout, log_file):
    """Run one headless Godot script. An explicit --log-file keeps Godot out of its user:// log folder."""
    command = [str(godot), '--headless', '--log-file', str(log_file), '--path', str(root), '--script', script, '--', *arguments]
    try:
        result = subprocess.run(command, cwd=root, capture_output=True, text=True, errors='replace', timeout=timeout)
    except subprocess.TimeoutExpired:
        return None, f'timed out after {timeout} s', command
    except OSError as error:
        return None, f'cannot start Godot: {error}', command
    return result.returncode, result.stdout + result.stderr, command


def tail(text, lines=25):
    return '\n'.join(text.strip().splitlines()[-lines:])


def run_gates(plan, godot, strict, timeout, logs):
    """Check every candidate before anything is imported. verify_candidate.gd writes no files."""
    results = {}
    problems = []
    for m in plan['modules']:
        if m['adapter'] in ('slot-board-v1', 'slot-board-v2'):
            arguments = [f'--board={m["boardDir"]}']
        else:
            arguments = [f'--part={m["part"]}']
        arguments += [f'--source={m["generatedFile"]}', f'--bible={plan["bibleFile"]}']
        code, output, command = run_godot(godot, plan['root'], VERIFY_SCRIPT, arguments, timeout, logs / f'gate-{m["id"]}.log')
        match = GATE_LINE.search(output)
        verdict = match.group(2) if match else None
        mode = 'strict' if strict else m['gate']
        details = [line.strip() for line in output.splitlines() if re.match(r'^\w+ SPR \d+: (PASS|FAIL)', line.strip()) or line.startswith('    - ')]
        results[m['id']] = {'mode': mode, 'result': verdict, 'exitCode': code, 'details': details, 'command': command, 'log': f'gate-{m["id"]}.log'}
        print(f'gate {m["id"]}: {verdict or "ERROR"} ({mode})')
        for line in details:
            print('    ' + line)
        if verdict is None or 'SCRIPT ERROR' in output or code != (0 if verdict == 'PASS' else 1):
            problems.append(f'{m["id"]}: the gate did not run cleanly (exit {code})\n{tail(output)}')
        elif mode == 'strict' and verdict != 'PASS':
            problems.append(f'{m["id"]}: candidate {m["generatedFile"]} fails the strict slot contract')
        elif mode == 'recorded-failure' and verdict != 'FAIL':
            problems.append(f'{m["id"]}: the recipe records a contract failure but the gate now reports {verdict}; review the module instead of importing it unchanged')
    if problems:
        raise RunFailure('Gate stage failed; nothing was written.\n' + '\n'.join(problems))
    return results


def import_arguments(plan, m, out, strict):
    root = plan['root']
    destination = godot_path(root, out / m['output']) + '/'
    common = [f'--source={m["generatedFile"]}', f'--style-bible={plan["bibleFile"]}',
              f'--recipe={godot_path(root, plan["recipePath"])}', f'--recipe-module={m["id"]}']
    if m['gate'] == 'recorded-failure' and not strict:
        # Records the failing contract in the manifest instead of skipping the gate.
        common.append('--allow-contract-failure')
    if m['adapter'] == 'native-costume-v1':
        return [f'--output-dir={destination}', *common]
    if m['adapter'] == 'native-head-v1':
        body = plan['byId'][m['fixtureBody']]
        return [f'--output-dir={destination}', f'--costume={godot_path(root, out / body["output"])}/', *common]
    if m.get('newArt'):
        arguments = [f'--board={m["boardDir"]}', f'--output-dir={destination}', *common]
        if m.get('name'):
            arguments.append(f'--name={m["name"]}')
        look = fixture_look_path(out, m)
        if look is not None:
            arguments.append(f'--fixture-look={godot_path(root, look)}')
        return arguments
    return [f'--board={m["boardDir"]}', f'--output-dir={destination}', f'--name={m["name"]}', *common]


def fixture_look_path(out, m):
    look = m.get('fixtureLook', {})
    return out / 'fixture-looks' / f'{m["id"]}.json' if look.get('appearance') or look.get('modules') else None


def write_fixture_look(plan, m, out):
    """Appearance for the parts a new module does not replace: a base appearance plus earlier modules of this run."""
    path = fixture_look_path(out, m)
    if path is None:
        return None
    root = plan['root']
    parts = {}
    base = m['fixtureLook'].get('appearance')
    if base:
        manifest = read_json(res_path(root, base, 'fixture look'), 'fixture look')
        for part, entries in manifest.get('parts', {}).items():
            parts[part] = list(entries) if isinstance(entries, list) else [entries]
    for other_id in m['fixtureLook'].get('modules', []):
        other = plan['byId'][other_id]
        parts.setdefault(other['part'], []).append({'manifest': godot_path(root, out / other['output'] / other['manifestName']), 'field': other['part']})
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({'schemaVersion': 1, 'id': f'fixture-look-{m["id"]}', 'label': f'fixture look for {m["id"]}', 'parts': parts}, indent=2) + '\n', encoding='utf-8')
    return path


# ---------------------------------------------------------------- comparison

def compare_records(root, saved, new, new_dir, allowed):
    """Byte-level and manifest-level comparison of one reproduced pack with its saved pack."""
    problems = []
    saved_records = dict(file_records(saved))
    new_records = dict(file_records(new))
    pngs = matched = 0
    for path, record in saved_records.items():
        local = not record['file'].startswith('res://')
        is_png = local and record['file'].lower().endswith('.png')
        pngs += is_png
        other = new_records.get(path)
        if other is None or other['file'] != record['file'] or other['sha256'] != record['sha256']:
            problems.append(f'{path}: saved {record["file"]} {record["sha256"]}, reproduced {other and other["file"]} {other and other["sha256"]}')
            continue
        try:
            target = record_path(root, new_dir, record, path)
        except RecipeError as error:
            problems.append(str(error))
            continue
        if not target.is_file() or sha256_file(target) != record['sha256']:
            problems.append(f'{path}: {target} does not have the saved bytes {record["sha256"]}')
        elif is_png:
            matched += 1
    referenced = set()
    for path, record in new_records.items():
        try:
            target = record_path(root, new_dir, record, f'reproduced record {path}')
        except RecipeError as error:
            problems.append(str(error))
            continue
        if record['file'].startswith('res://'):
            continue
        referenced.add(target)
        if path not in saved_records and (not target.is_file() or sha256_file(target) != record['sha256']):
            problems.append(f'{path}: reproduced {record["file"]} does not match its own manifest')
    differences = json_diff(saved, new)
    unexpected = [f'{path} ({kind})' for path, kind in differences if not covered(path, allowed)]
    observed = [a for a in allowed if any(covered(path, [a]) for path, _ in differences)]
    problems += [f'unexpected manifest difference: {item}' for item in unexpected]
    return {'pngs': pngs, 'pngsByteIdentical': matched, 'problems': problems, 'unexpected': unexpected,
            'observedExpected': observed, 'referenced': referenced}


def adapter_checks(plan, m, new, strict):
    """[{"name", "ok", "detail"}]: ACT, timing, slot set, dependency and contract facts for this module."""
    checks = []

    def add(name, ok, detail=''):
        checks.append({'name': name, 'ok': bool(ok), 'detail': detail})

    if m.get('newArt'):
        return new_art_checks(plan, m, new, add, checks)
    action = m['action']
    attack = action['attack']
    indices = sorted(slot['index'] for slot in m['slots'])
    verification = new.get('verification', {}) if isinstance(new.get('verification'), dict) else {}
    contract = new.get('contract', {}) if isinstance(new.get('contract'), dict) else {}
    expect_pass = strict or m['gate'] == 'strict'
    # The whole "recipe" subtree is a declared difference, so its content is checked here.
    expected_recipe = {'path': godot_path(plan['root'], plan['recipePath']), 'sha256': plan['recipeSha256'], 'module': m['id']}
    add('recipe provenance matches the validated recipe', same(new.get('recipe'), expected_recipe),
        f'recorded {json.dumps(new.get("recipe"))}; expected {json.dumps(expected_recipe)}')
    add('contract result recorded as expected',
        contract.get('pass') is expect_pass and (expect_pass or contract.get('allowedFailure') is True),
        f'pass={contract.get("pass")}, allowedFailure={contract.get("allowedFailure")}; expected pass={expect_pass}')

    def keys(field):
        value = new.get(field, {})
        try:
            return sorted(int(key) for key in value) if isinstance(value, dict) else None
        except ValueError:
            return None

    if m['adapter'] in ('native-costume-v1', 'native-head-v1'):
        add('importer confirmed unchanged ACT data',
            verification.get('allACTDataUnchanged') is True and isinstance(verification.get('originalActionsSha256'), dict)
            and same(verification.get('originalActionsSha256'), verification.get('afterReplacementActionsSha256')))
    if m['adapter'] == 'native-costume-v1':
        sequences = new.get('sequences', {}) if isinstance(new.get('sequences'), dict) else {}
        attack_sequence = sequences.get('attack') if isinstance(sequences.get('attack'), dict) else {}
        ready_sequence = sequences.get('ready') if isinstance(sequences.get('ready'), dict) else {}
        frames = attack_sequence.get('frames', [])
        add('attack index sequence', same(verification.get('bodyAttackIndexSequence'), attack['sequence']), str(verification.get('bodyAttackIndexSequence')))
        add('source actions 86 (attack) and 38 (ready)', same(attack_sequence.get('sourceAction'), attack['sourceAction'])
            and same(ready_sequence.get('sourceAction'), action['ready']['sourceAction']))
        add(f'{len(attack["sequence"])} attack frames of {attack["frameDurationMs"]} ms', isinstance(frames, list) and len(frames) == len(attack['sequence'])
            and all(isinstance(frame, dict) and same(frame.get('durationMs'), attack['frameDurationMs']) for frame in frames))
        add('replaced slot set', keys('body') == indices, str(keys('body')))
    elif m['adapter'] == 'native-head-v1':
        variants = ADAPTERS['native-head-v1']['variants']
        add('head index sequence and headgear variants', same(verification.get('headAttackIndexSequence'), attack['sequence'])
            and same(verification.get('headgearVariants'), variants))
        timing_ok = True
        for variant in variants:
            sequence = new.get('sequences', {}).get(variant) if isinstance(new.get('sequences'), dict) else None
            sequence = sequence if isinstance(sequence, dict) else {}
            frames = sequence.get('frames', [])
            timing_ok = timing_ok and same(sequence.get('sourceAction'), attack['sourceAction']) and isinstance(frames, list) \
                and len(frames) == len(attack['sequence']) and all(isinstance(f, dict) and same(f.get('durationMs'), attack['frameDurationMs']) for f in frames)
        add(f'action {attack["sourceAction"]}, {len(attack["sequence"])} frames of {attack["frameDurationMs"]} ms for {", ".join(variants)}', timing_ok)
        add('replaced slot set', keys('head') == indices, str(keys('head')))
        body = plan['byId'][m['fixtureBody']]
        add(f'fixtures rendered on the reproduced body module {body["id"]}',
            str(new.get('costumeManifest', '')).endswith(f'/{body["output"]}/{body["manifestName"]}'), str(new.get('costumeManifest')))
    else:
        fixtures = new.get('fixtures', {}) if isinstance(new.get('fixtures'), dict) else {}
        add('importer confirmed unchanged ACT data', verification.get('actUnchanged') is True)
        ok = sorted(fixtures) == sorted(attack['directions'])
        for name in attack['directions']:
            fixture = fixtures.get(name, {}) if isinstance(fixtures.get(name), dict) else {}
            ok = ok and same(fixture.get('sourceAction'), attack['groupIndex'] * 8 + DIRECTIONS.index(name)) \
                and isinstance(fixture.get('frames'), list) and len(fixture['frames']) == len(attack['sequence'])
        add(f'fixtures for {", ".join(attack["directions"])} with {len(attack["sequence"])} frames each', ok)
        add('replaced slot set', keys(m['part']) == indices, str(keys(m['part'])))
    return checks


def new_art_checks(plan, m, new, add, checks):
    """Facts a NEW art pack must show: provenance, strict contract, clean palette, ACT, slots and the full fixture plan."""
    layout = m['layout']
    style = plan['recipe']['style']
    verification = new.get('verification', {}) if isinstance(new.get('verification'), dict) else {}
    contract = new.get('contract', {}) if isinstance(new.get('contract'), dict) else {}
    expected_recipe = {'path': godot_path(plan['root'], plan['recipePath']), 'sha256': plan['recipeSha256'], 'module': m['id']}
    add('recipe provenance matches the validated recipe', same(new.get('recipe'), expected_recipe),
        f'recorded {json.dumps(new.get("recipe"))}; expected {json.dumps(expected_recipe)}')
    add('strict slot contract passed', contract.get('pass') is True and contract.get('allowedFailure') is False and contract.get('bibleSha256') == style['bible']['sha256'],
        f'pass={contract.get("pass")}, allowedFailure={contract.get("allowedFailure")}')
    add('imported from the pinned board and candidate',
        isinstance(new.get('board'), dict) and new['board'].get('layout') == m['boardDir'] + 'sprite-slots.json' and new['board'].get('sha256') == plan['inputs'].get(m['boardDir'] + 'sprite-slots.json')
        and new.get('sourceImage') == m['generatedFile'] and new.get('sourceImageSha256') == plan['inputs'].get(m['generatedFile']))
    add('palette-only output (no off-palette, key-tinted or partial-alpha pixels)',
        new.get('import', {}).get('palette', {}).get('sha256') == style['palette']['sha256'] and isinstance(new.get('diagnostics'), dict)
        and all(isinstance(d, dict) and d.get('offPalettePixels') == 0 and d.get('keyTintedPixels') == 0 and d.get('partialAlphaPixels') == 0 for d in new['diagnostics'].values()))
    add('importer confirmed unchanged ACT data', verification.get('actUnchanged') is True)
    value = new.get(m['part'], {})
    try:
        replaced = sorted(int(key) for key in value) if isinstance(value, dict) else None
    except ValueError:
        replaced = None
    add('replaced slot set', replaced == sorted(slot['index'] for slot in m['slots']), str(replaced))
    fixtures = new.get('fixtures', {}) if isinstance(new.get('fixtures'), dict) else {}
    expected, timeline_problems = expected_fixtures(layout, m['part'])
    expected_keys = [key for key, _, _, _ in expected]
    missing, wrong = [], []
    for key, frame_count, delay, source_action in expected:
        entry = fixtures.get(key)
        if not isinstance(entry, dict):
            missing.append(key)
            continue
        frames = entry.get('frames')
        ok = isinstance(frames, list) and len(frames) == frame_count and same(entry.get('sourceAction'), source_action)
        if delay is not None:
            ok = ok and same(entry.get('frameDurationMs'), delay)
        if not ok:
            wrong.append(key)
    add(f'fixture plan rendered on the body timeline ({len(expected_keys)} sets: native action, body frame count and delay)',
        not timeline_problems and expected_keys and not missing and not wrong and sorted(fixtures) == sorted(expected_keys),
        f'timeline {timeline_problems[:3]}, missing {missing[:5]}, wrong {wrong[:5]}, extra {sorted(set(fixtures) - set(expected_keys))[:5]}')
    if m['fixtureLook'].get('modules') or m['fixtureLook'].get('appearance'):
        add('fixtures drew the other parts from the recipe fixture look', str(new.get('fixtureLook', {}).get('file', '')).endswith(f'fixture-looks/{m["id"]}.json'), str(new.get('fixtureLook')))
    return checks


def verify_own_records(root, new, new_dir):
    """A new pack has no saved twin: every file it records must exist inside it with the recorded hash."""
    problems, referenced, pngs = [], set(), 0
    for path, record in file_records(new):
        try:
            target = record_path(root, new_dir, record, f'record {path}')
        except RecipeError as error:
            problems.append(str(error))
            continue
        if record['file'].startswith('res://'):
            continue
        referenced.add(target)
        if not target.is_file() or sha256_file(target) != record['sha256']:
            problems.append(f'{path}: {record["file"]} does not match its manifest')
        elif record['file'].lower().endswith('.png'):
            pngs += 1
    return {'kind': 'new', 'pngs': 0, 'pngsByteIdentical': 0, 'newPngs': pngs, 'problems': problems, 'unexpected': [], 'observedExpected': [], 'referenced': referenced}


def compare_module(plan, m, out, strict):
    new_dir = out / m['output']
    manifest_path = new_dir / m['manifestName']
    empty = {'pngs': 0, 'pngsByteIdentical': 0, 'unexpected': [], 'observedExpected': [], 'checks': [], 'ignoredFiles': []}
    if not manifest_path.is_file():
        return dict(empty, problems=[f'{manifest_path} was not written'])
    try:
        new = json.loads(manifest_path.read_text(encoding='utf-8'))
    except ValueError as error:
        return dict(empty, problems=[f'{manifest_path}: {error}'])
    if not isinstance(new, dict):
        return dict(empty, problems=[f'{manifest_path} is not a JSON object'])
    if m.get('newArt'):
        result = verify_own_records(plan['root'], new, new_dir)
    else:
        allowed = [item['path'] for item in m['expectedDifferences']]
        result = compare_records(plan['root'], m['saved'], new, new_dir, allowed)
        result['kind'] = 'reproduction'
    result['checks'] = adapter_checks(plan, m, new, strict)
    result['problems'] += [f'{item["name"]} failed: {item["detail"]}' for item in result['checks'] if not item['ok']]
    referenced = {path.as_posix() for path in result.pop('referenced')} | {manifest_path.resolve().as_posix()}
    stray = sorted(path.relative_to(new_dir).as_posix() for path in new_dir.rglob('*')
                   if path.is_file() and path.resolve().as_posix() not in referenced)
    result['ignoredFiles'] = [name for name in stray if name.endswith('.import')]
    result['problems'] += [f'unexpected file {name}' for name in stray if not name.endswith('.import')]
    result['manifest'] = {'file': manifest_path.relative_to(out).as_posix(), 'sha256': sha256_file(manifest_path)}
    return result


# ------------------------------------------------------------------ report

def slot_ranges(indices):
    indices = sorted(indices)
    ranges = []
    for index in indices:
        if ranges and index == ranges[-1][1] + 1:
            ranges[-1][1] = index
        else:
            ranges.append([index, index])
    return ', '.join(str(a) if a == b else f'{a}-{b}' for a, b in ranges)


def unselected_ids(plan):
    selected = {m['id'] for m in plan['modules']}
    return [module_id for module_id in plan['byId'] if module_id not in selected]


def coverage(plan):
    """Selected modules only; totals were validated by load_plan."""
    parts = {}
    for m in plan['modules']:
        entry = parts.setdefault(m['part'], {'declared': plan['coverage']['parts'][m['part']], 'byStatus': {}})
        entry['byStatus'].setdefault(m['status'], []).extend(slot['index'] for slot in m['slots'])
    unselected = unselected_ids(plan)
    notes = list(plan['coverage']['notes'])
    if unselected:
        notes.append('Modules not selected in this run (not counted): ' + ', '.join(unselected) + '.')
    return {'parts': parts, 'notes': notes, 'inventoryChecked': plan['coverage']['inventoryChecked']}


def module_outcome(entry):
    compared = entry.get('comparison')
    if entry['import'] != 'completed':
        return entry['import']
    return 'PASS' if compared and not compared['problems'] else 'FAIL'


def invariant_statements(plan, report, input_changes, before, changed, added):
    """Only facts this run established, per selected module."""
    modules = plan['modules']
    statements = ['Selected modules: ' + ', '.join(m['id'] for m in modules) + '.']
    unselected = unselected_ids(plan)
    if unselected:
        statements.append('Not selected, so not imported or checked: ' + ', '.join(unselected) + '.')
    if report['recipe'].get('unchangedAfterRun'):
        statements.append(f'The recipe kept its validated bytes (sha256 {plan["recipeSha256"]}) from validation to the end of the run.')
    else:
        statements.append('The recipe file changed or disappeared during the run; importer provenance cannot be trusted.')
    if input_changes:
        statements.append(f'{len(input_changes)} of {len(plan["inputs"])} pinned inputs changed or disappeared during the run: ' + ', '.join(input_changes) + '.')
    else:
        statements.append(f'All {len(plan["inputs"])} pinned inputs (native ACT/SPR, template, layouts, native drawings, palette, style bible, generated images) matched before the run and again after it.')
    ignored = [p for p in added if p.endswith('.import')]
    statements.append(f'{len(before)} files in the saved packs, appearances, style and source folders were hashed before and after the run: '
                      f'{len(changed)} changed or removed, {len(added) - len(ignored)} added'
                      + (f', {len(ignored)} Godot .import caches ignored.' if ignored else '.'))
    compared = [m for m in modules if report['modules'][m['id']].get('comparison')]
    missing = [m['id'] for m in modules if not report['modules'][m['id']].get('comparison')]
    reproduced = [m for m in compared if not m.get('newArt')]
    total = sum(report['modules'][m['id']]['comparison']['pngs'] for m in reproduced)
    same_pngs = sum(report['modules'][m['id']]['comparison']['pngsByteIdentical'] for m in reproduced)
    if reproduced:
        statements.append(f'{same_pngs}/{total} saved PNGs of the compared modules ({", ".join(m["id"] for m in reproduced)}) reproduced byte for byte.')
    for m in compared:
        if m.get('newArt'):
            result = report['modules'][m['id']]['comparison']
            statements.append(f'{m["id"]} is NEW art (no saved pack to compare): {result.get("newPngs", 0)} PNGs written; '
                              f'{len([p for p in result["problems"] if "manifest" in p or "climb" in p or "outside" in p])} file-record problems. Status in the recipe: {m["status"]}.')
    if missing:
        statements.append('No output comparison for ' + ', '.join(f'{i} (import {report["modules"][i]["import"]})' for i in missing) + '.')
    for m in compared:
        checks = report['modules'][m['id']]['comparison']['checks']
        passed = [c['name'] for c in checks if c['ok']]
        failed = [c['name'] for c in checks if not c['ok']]
        statements.append(f'{m["id"]}: ' + ('; '.join(passed) + ' — confirmed' if passed else 'no checks passed')
                          + ('. Failed: ' + '; '.join(failed) if failed else '') + '.')
        if m['adapter'] == 'slot-board-v1':
            statements.append(f'{m["id"]} was imported from its own board without other recipe modules.')
    return statements


def markdown(report, plan):
    recipe = plan['recipe']
    lines = [f'# Artwork reproduction report: {recipe["id"]} {recipe["version"]}', '',
             f'Result: **{report["result"]}**. Generated {report["createdAt"]} by `tools/character-lab/art_recipe.py run`'
             f'{" --strict" if report["strict"] else ""}. Recipe `{report["recipe"]["path"]}` (sha256 `{report["recipe"]["sha256"]}`).', '',
             'This run imported pinned generated images with the Godot importers. Reproduction modules were compared with their saved packs; '
             'new-art modules were checked against their board, the strict slot contract and their own manifests. '
             'It did not generate artwork, open a browser, run the game or judge visuals. Saved browser evidence was not re-run and is not refreshed by this report.', '',
             '## Modules', '', '| Module | Part | SPR | Status | Gate | Import | PNGs | Result |', '| --- | --- | --- | --- | --- | --- | --- | --- |']
    for m in plan['modules']:
        entry = report['modules'][m['id']]
        compared = entry.get('comparison') or {}
        gate = entry.get('gate') or {}
        if not compared:
            pngs = 'not compared'
        elif m.get('newArt'):
            pngs = f'{compared.get("newPngs", 0)} new'
        else:
            pngs = f'{compared["pngsByteIdentical"]}/{compared["pngs"]} saved, byte-identical'
        lines.append(f'| `{m["id"]}` → `{m["output"]}/` | {m["part"]} | {slot_ranges(s["index"] for s in m["slots"])} | {m["status"]} | '
                     f'{gate.get("mode", m["gate"])}: {gate.get("result")} | {entry["import"]} | {pngs} | {module_outcome(entry)} |')
    lines += ['', '## Gate results', '']
    for m in plan['modules']:
        gate = report['modules'][m['id']].get('gate') or {}
        lines.append(f'- `{m["id"]}` ({gate.get("mode")}): {gate.get("result")}')
        lines += [f'  - {detail}' for detail in gate.get('details', [])]
        if m['gate'] == 'recorded-failure':
            failure = m['recordedFailure']
            lines.append(f'  - Recorded failure since {failure["since"]}: {failure["reason"]} Replacement: {failure["replacement"]}')
            lines.append('  - Imported with `--allow-contract-failure`; its manifest must record `contract.pass = false` (checked below). This module keeps its historical name and is not an accepted replacement.')
    lines += ['', '## Expected manifest differences', '']
    for m in plan['modules']:
        compared = report['modules'][m['id']].get('comparison')
        observed = set(compared['observedExpected']) if compared else set()
        for item in m['expectedDifferences']:
            state = ('observed' if item['path'] in observed else 'not observed') if compared else 'not compared'
            lines.append(f'- `{m["id"]}` `{item["path"]}` ({state}): {item["reason"]}')
    lines += ['', '## Invariants established by this run', ''] + [f'- {item}' for item in report['invariants']]
    if report['problems']:
        lines += ['', '## Problems', ''] + [f'- {problem}' for problem in report['problems']]
    lines += ['', '## Coverage of the selected modules', '']
    for part, entry in report['coverage']['parts'].items():
        totals = ', '.join(f'{k} {v}' for k, v in entry['declared'].items())
        statuses = '; '.join(f'{status}: {len(set(indices))} ({slot_ranges(set(indices))})' for status, indices in entry['byStatus'].items())
        lines.append(f'- {part} ({totals} drawings): {statuses}')
    lines += [f'- Note: {note}' for note in report['coverage']['notes']]
    lines += ['', '## Remaining decisions', ''] + [f'- {item}' for item in recipe.get('decisions', [])]
    lines += ['', '## Not covered by this run', '',
              '- No browser pixel-parity or visual review was performed; earlier saved browser records are unchanged and still describe their own dates.',
              '- No appearance manifest was changed; the game keeps loading the saved packs, not this output directory.',
              f'- Godot PNG encoding is compared on this machine and Godot build only ({report["godot"]}).',
              f'- Godot logs of this run: `{LOG_FOLDER}/`.', '']
    return '\n'.join(lines)


def recipe_unchanged(plan):
    try:
        return sha256_file(plan['recipePath']) == plan['recipeSha256']
    except OSError:
        return False


def run(plan, out, godot, strict, timeout, logs):
    """Gate, import, compare and report. `logs` is a private temporary folder outside `out`."""
    # Importers hash the recipe themselves; it must still be the validated bytes.
    check(recipe_unchanged(plan), f'Recipe {plan["recipePath"]} changed after validation; validate it again')
    pending = [m['id'] for m in plan['modules'] if m.get('pending')]
    check(not pending, f'Module(s) {pending} have no pinned candidate yet (generatedImage sha256 "{PENDING}"); pin one with "art_recipe.py pin" or deselect them')
    before = snapshot(plan)
    gates = run_gates(plan, godot, strict, timeout, logs)
    check(recipe_unchanged(plan), f'Recipe {plan["recipePath"]} changed during the gate stage; nothing was imported')
    out.mkdir(parents=True, exist_ok=True)
    report = {'schemaVersion': 1, 'kind': 'artwork-reproduction-report', 'createdAt': datetime.now(timezone.utc).isoformat(timespec='seconds'),
              'recipe': {'path': godot_path(plan['root'], plan['recipePath']), 'sha256': plan['recipeSha256'], 'id': plan['recipe']['id'], 'version': plan['recipe']['version']},
              'godot': str(godot), 'strict': strict, 'output': str(out), 'freshBrowserValidation': False, 'visualReview': 'not performed by this run',
              'codeInputs': plan['codeInputs'], 'selectedModules': [m['id'] for m in plan['modules']], 'modules': {}, 'problems': []}
    failed = None
    for m in plan['modules']:
        entry = report['modules'].setdefault(m['id'], {'status': m['status'], 'gate': gates[m['id']], 'output': m['output'] + '/', 'import': 'not run',
                                                        'kind': 'new art' if m.get('newArt') else 'reproduction'})
        if failed:
            entry['import'] = f'skipped after {failed} failed'
            continue
        if m.get('newArt'):
            look = write_fixture_look(plan, m, out)
            if look is not None:
                entry['fixtureLook'] = look.relative_to(out).as_posix()
        script = ADAPTERS[m['adapter']]['script']
        code, output, command = run_godot(godot, plan['root'], script, import_arguments(plan, m, out, strict), timeout, logs / f'import-{m["id"]}.log')
        entry.update(importExitCode=code, importCommand=command, importLog=f'import-{m["id"]}.log')
        print(f'import {m["id"]}: exit {code}')
        if code != 0 or 'SCRIPT ERROR' in output:
            failed = m['id']
            entry['import'] = 'failed'
            report['problems'].append(f'{m["id"]}: importer failed (exit {code})\n{tail(output)}')
            continue
        entry['import'] = 'completed'
        entry['comparison'] = compare_module(plan, m, out, strict)
        report['problems'] += [f'{m["id"]}: {problem}' for problem in entry['comparison']['problems']]
    input_changes = []
    for file, expected in plan['inputs'].items():
        try:
            path = res_path(plan['root'], file, 'input')
            unchanged = path.is_file() and sha256_file(path) == expected
        except RecipeError:
            unchanged = False
        if not unchanged:
            input_changes.append(file)
    report['problems'] += [f'input changed during the run: {file}' for file in input_changes]
    report['recipe']['unchangedAfterRun'] = recipe_unchanged(plan)
    if not report['recipe']['unchangedAfterRun']:
        report['problems'].append(f'recipe changed during the run: {report["recipe"]["path"]} no longer has sha256 {plan["recipeSha256"]}')
    for relative, expected in plan['codeInputs'].items():
        path = ROOT / relative
        if not path.is_file() or sha256_file(path) != expected:
            report['problems'].append(f'workflow code changed during the run: {relative}')
    after = snapshot(plan)
    changed = sorted(path for path in before if after.get(path) != before[path])
    added = sorted(path for path in after if path not in before)
    report['problems'] += [f'protected file changed or removed: {path}' for path in changed]
    report['problems'] += [f'protected folder gained a file: {path}' for path in added if not path.endswith('.import')]
    report['invariants'] = invariant_statements(plan, report, input_changes, before, changed, added)
    report['coverage'] = coverage(plan)
    report['result'] = 'FAIL' if report['problems'] or failed else 'PASS'
    log_copy = out / LOG_FOLDER
    log_copy.mkdir(exist_ok=True)
    for log in sorted(logs.glob('*.log')):
        shutil.copy2(log, log_copy / log.name)
    report['logs'] = sorted(path.name for path in log_copy.iterdir())
    (out / REPORT_JSON).write_text(json.dumps(report, indent=2, ensure_ascii=False, default=str) + '\n', encoding='utf-8')
    (out / REPORT_MD).write_text(markdown(report, plan), encoding='utf-8')
    compared = [e['comparison'] for e in report['modules'].values() if e.get('comparison')]
    print(f'{report["result"]}: {sum(c["pngsByteIdentical"] for c in compared)}/{sum(c["pngs"] for c in compared)} saved PNGs byte-identical '
          f'in {len(compared)} of {len(plan["modules"])} selected modules; {len(report["problems"])} problem(s). Report: {out / REPORT_MD}')
    for problem in report['problems']:
        print('  - ' + problem.splitlines()[0], file=sys.stderr)
    return 0 if report['result'] == 'PASS' else 1


def _pin_layout(root, module_id, module):
    """Record a board layout's hash and geometry, checked against the drawings the recipe declares."""
    entry = module.get('layout', {})
    layout_path = res_path(root, str(entry.get('file', '')), f'{module_id}.layout.file')
    layout = read_json(layout_path, f'{module_id} board layout (export the board first)')
    check(isinstance(layout, dict) and isinstance(layout.get('slots'), list), f'{module_id}: board layout has no slots')
    declared = [(s.get('index'), s.get('use')) for s in entry.get('slots', []) if isinstance(s, dict)]
    board_slots = [s.get('index') for s in layout['slots']]
    check([index for index, _ in declared] == board_slots, f'{module_id}: the board holds SPR {board_slots}, the recipe declares {[i for i, _ in declared]}')
    entry['sha256'] = sha256_file(layout_path)
    entry['canvas'] = layout.get('canvas')
    entry['slots'] = [{'index': index, 'use': use, 'imageRect': [int(v) for v in slot['imageRect']]} for (index, use), slot in zip(declared, layout['slots'])]
    return layout_path


def _rewrite_recipe(recipe_path, recipe, original, root):
    recipe_path.write_text(json.dumps(recipe, indent='\t', ensure_ascii=False) + '\n', encoding='utf-8')
    try:
        return load_plan(recipe_path, root)
    except RecipeError:
        recipe_path.write_bytes(original)
        raise


def lock_recipe(recipe_path, root=ROOT):
    """Fill every "PENDING" pin that has a file now: style bible/palette, native sources, exported board layouts."""
    recipe_path = Path(recipe_path).resolve()
    original = recipe_path.read_bytes()
    recipe = read_json(recipe_path, 'recipe')
    locked = []
    for key in ('bible', 'palette'):
        entry = recipe.get('style', {}).get(key, {})
        if isinstance(entry, dict) and entry.get('sha256') == PENDING:
            entry['sha256'] = sha256_file(res_path(root, entry.get('file'), f'style.{key}'))
            locked.append(f'style.{key}')
    for file, sha in list(recipe.get('nativeSources', {}).items()):
        if sha == PENDING:
            recipe['nativeSources'][file] = sha256_file(res_path(root, file, 'nativeSources'))
            locked.append(file)
    for module in recipe.get('modules', []):
        if isinstance(module, dict) and ADAPTERS.get(module.get('adapter'), {}).get('newArt') and module.get('layout', {}).get('sha256') == PENDING:
            if res_path(root, str(module['layout'].get('file', '')), 'layout').is_file():
                _pin_layout(root, module.get('id'), module)
                locked.append(f'{module.get("id")} board layout')
    _rewrite_recipe(recipe_path, recipe, original, root)
    return locked


def pin_candidate(recipe_path, module_id, candidate, root=ROOT, generated_on=None):
    """Record a candidate's path, SHA-256 and size in a new-art module; the recipe must still validate.
    `generated_on` names the board layout the candidate was generated on when that is another
    board with identical geometry (validated by load_plan)."""
    recipe_path = Path(recipe_path).resolve()
    original = recipe_path.read_bytes()
    recipe = read_json(recipe_path, 'recipe')
    modules = [m for m in recipe.get('modules', []) if isinstance(m, dict) and m.get('id') == module_id]
    check(len(modules) == 1, f'recipe has no module {module_id!r}')
    module = modules[0]
    check(ADAPTERS.get(module.get('adapter'), {}).get('newArt'), f'{module_id}: only new-art modules take candidates; reproduction modules pin their saved source')
    entry = module.get('layout', {})
    layout_path = _pin_layout(root, module_id, module)
    if candidate:
        path = res_path(root, candidate, 'candidate')
        check(path.is_file(), f'candidate {candidate} is missing')
        module['generatedImage'] = {'file': candidate, 'sha256': sha256_file(path), 'size': png_size(path)}
        if generated_on:
            module['generatedImage']['generatedOn'] = {'file': generated_on, 'sha256': sha256_file(res_path(root, generated_on, 'generated-on layout'))}
        else:
            check(path.is_relative_to(layout_path.parent / 'candidates'), f'candidate must be inside {godot_path(root, layout_path.parent / "candidates")}/ (or pass --generated-on)')
    _rewrite_recipe(recipe_path, recipe, original, root)
    return {'layout': entry['sha256'], **module['generatedImage']}


def promote(recipe_path, run_dir, selected, root=ROOT):
    """Copy verified new-art packs from a PASSing run into their install folders (never overwriting)."""
    plan = load_plan(recipe_path, root, selected)
    run_dir = Path(run_dir).expanduser().resolve()
    report = read_json(run_dir / REPORT_JSON, 'run report')
    check(report.get('result') == 'PASS', f'{run_dir} did not PASS; nothing is promoted')
    check(report.get('recipe', {}).get('sha256') == plan['recipeSha256'], 'the run used a different recipe version; run it again')
    check(report.get('strict') is False or report.get('strict') is True, 'run report has no strict flag')
    jobs = []
    for m in plan['modules']:
        check(m.get('newArt') and m.get('install') is not None, f'{m["id"]}: only new-art modules with an "install" folder are promoted')
        entry = report.get('modules', {}).get(m['id'])
        check(isinstance(entry, dict) and entry.get('import') == 'completed' and not entry.get('comparison', {}).get('problems'), f'{m["id"]} was not imported cleanly in {run_dir}')
        check(not m['install'].exists(), f'{m["installRes"]} already exists; installed packs are never overwritten')
        source = contained(run_dir, m['output'], f'{m["id"]} output')
        manifest = read_json(source / 'pack.json', f'{m["id"]} run pack')
        result = verify_own_records(root, manifest, source)
        check(not result['problems'], f'{m["id"]}: run output changed since the run: {result["problems"][:3]}')
        jobs.append((m, source))
    for m, source in jobs:
        shutil.copytree(source, m['install'], ignore=shutil.ignore_patterns('*.import'))
        installed = verify_own_records(root, read_json(m['install'] / 'pack.json', 'installed pack'), m['install'])
        if installed['problems']:
            raise RunFailure(f'{m["id"]}: installed copy does not verify: {installed["problems"][:3]}')
        print(f'promoted {m["id"]} -> {m["installRes"]} ({installed["newPngs"]} PNGs verified)')
    return len(jobs)


def appearance_coverage(appearance, inventory, root=ROOT):
    """Per part and game action group: which native drawings an appearance replaces, per direction."""
    look = read_json(res_path(root, appearance, 'appearance'), 'appearance')
    data = read_json(res_path(root, inventory, 'inventory'), 'inventory')
    check(isinstance(look, dict) and isinstance(look.get('parts'), dict), 'appearance: expected {"parts": {...}}')
    check(isinstance(data, dict) and isinstance(data.get('parts'), dict) and isinstance(data.get('groups'), list), 'inventory: unexpected shape')
    replaced, unavailable = {}, []
    for part, entries in look['parts'].items():
        for entry in entries if isinstance(entries, list) else [entries]:
            manifest = entry.get('manifest', '')
            path = res_path(root, manifest, 'appearance pack')
            if not path.is_file():
                unavailable.append(manifest)
                continue
            pack = read_json(path, 'pack')
            field = pack.get(entry.get('field', part), {})
            replaced.setdefault(part, set()).update(int(k) for k in field)
    result = {'appearance': appearance, 'unavailablePacks': unavailable, 'parts': {}}
    game = data.get('gameUsesGroups', {})
    for part in ('body', 'head'):
        part_data = data['parts'].get(part)
        if not isinstance(part_data, dict):
            continue
        have = replaced.get(part, set())
        rows = []
        for group_index, state in sorted(game.items(), key=lambda item: int(item[0])):
            name = data['groups'][int(group_index)]
            entry = part_data['groups'][name]
            needed = set(entry['slots'])
            directions = []
            for d, slots in enumerate(entry['byDirection']):
                need_d = set(slots)
                directions.append('complete' if need_d <= have else ('native' if not need_d & have else 'partial'))
            covered_count = len(needed & have)
            status = 'complete' if needed <= have else ('native fallback' if covered_count == 0 else f'partial {covered_count}/{len(needed)}')
            rows.append({'state': state, 'group': name, 'drawings': len(needed), 'replaced': covered_count, 'status': status,
                         'directions': dict(zip(DIRECTIONS, directions)), 'missing': sorted(needed - have)})
        result['parts'][part] = {'replaced': sorted(have), 'replacedCount': len(have), 'total': part_data.get('uniqueSlotCount'),
                                 'gameplayTotal': part_data.get('gameSubsetSlotCount'), 'groups': rows}
    return result


def coverage_markdown(result):
    lines = [f'# Coverage of {result["appearance"]}', '']
    if result['unavailablePacks']:
        lines += ['Packs not available in this checkout (not counted): ' + ', '.join(result['unavailablePacks']), '']
    for part, entry in result['parts'].items():
        lines += [f'## {part}: {entry["replacedCount"]} of {entry["gameplayTotal"]} gameplay drawings ({entry["total"]} in the SPR) replaced', '',
                  '| Game state | Group | Replaced | Status | ' + ' | '.join(DIRECTIONS) + ' |', '| --- | --- | --- | --- | ' + ' | '.join('---' for _ in DIRECTIONS) + ' |']
        for row in entry['groups']:
            lines.append(f'| {row["state"]} | {row["group"]} | {row["replaced"]}/{row["drawings"]} | {row["status"]} | ' + ' | '.join(row['directions'][d] for d in DIRECTIONS) + ' |')
        lines.append('')
    lines.append('"native" means the game shows the original RO drawing there (explicit native fallback); "partial" mixes new and native drawings in one action.')
    return '\n'.join(lines) + '\n'


def main(argv=None, root=ROOT):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    commands = parser.add_subparsers(dest='command', required=True)
    validate = commands.add_parser('validate', help='check a recipe and its inputs; writes nothing')
    validate.add_argument('recipe')
    lock = commands.add_parser('lock', help='fill PENDING pins (style bible, native sources, exported board layouts) from the current files')
    lock.add_argument('recipe')
    pin = commands.add_parser('pin', help='record a candidate (path, SHA-256, size) in a new-art module of a recipe')
    pin.add_argument('recipe')
    pin.add_argument('--module', required=True)
    pin.add_argument('--candidate', help='res:// path inside the board candidates/ folder (omit to pin only the board layout)')
    pin.add_argument('--generated-on', dest='generated_on', help='res:// layout (sprite-slots.json or head-slot.json) of another board with identical geometry the candidate was generated on')
    promote_parser = commands.add_parser('promote', help='install verified new-art packs from a PASSing run')
    promote_parser.add_argument('recipe')
    promote_parser.add_argument('--from', dest='run_dir', required=True)
    promote_parser.add_argument('--module', action='append', dest='modules')
    coverage_parser = commands.add_parser('coverage', help='per-action, per-direction coverage of an appearance')
    coverage_parser.add_argument('appearance', help='res:// appearance manifest')
    coverage_parser.add_argument('--inventory', default='res://tools/character-lab/assets/slot-inventory/swordsman-male.json')
    coverage_parser.add_argument('--json', dest='json_out', help='also write the result to this new file outside protected folders')
    reproduce = commands.add_parser('run', help='gate, import into a fresh directory, compare and report')
    reproduce.add_argument('recipe')
    reproduce.add_argument('--out', required=True, help='new or empty directory outside protected folders')
    reproduce.add_argument('--strict', action='store_true', help='gate every module strictly, including recorded historical failures')
    reproduce.add_argument('--module', action='append', dest='modules', help='only this module id (repeatable)')
    reproduce.add_argument('--godot', help=f'Godot executable (default $GODOT or {DEFAULT_GODOT})')
    reproduce.add_argument('--log-dir', help='existing folder for the temporary Godot log folder (default $ART_RECIPE_LOG_DIR or the system temporary folder)')
    reproduce.add_argument('--timeout', type=int, default=1800, help='seconds per Godot call')
    args = parser.parse_args(argv)
    try:
        if args.command == 'validate':
            plan = load_plan(args.recipe, root)
            for m in plan['modules']:
                state = 'PENDING candidate' if m.get('pending') else ('new art' if m.get('newArt') else 'reproduces saved pack')
                print(f'{m["id"]}: {m["adapter"]} {m["part"]} SPR {slot_ranges(s["index"] for s in m["slots"])} -> {m["output"]}/ ({m["status"]}, gate {m["gate"]}, {state})')
            for note in plan['coverage']['notes']:
                print('coverage: ' + note)
            pending = [m['id'] for m in plan['modules'] if m.get('pending')]
            reproductions = len([m for m in plan['modules'] if not m.get('newArt')])
            print(f'VALID: {len(plan["inputs"])} pinned inputs, {reproductions} saved packs and {len(plan["modules"]) - reproductions} new-art modules match the recipe'
                  + (f'; {len(pending)} module(s) still need a candidate: {", ".join(pending)}.' if pending else '.'))
            return 0
        if args.command == 'lock':
            locked = lock_recipe(args.recipe, root)
            print('LOCKED ' + (', '.join(locked) if locked else 'nothing (no PENDING pin with an existing file)') + '; recipe validates.')
            return 0
        if args.command == 'pin':
            record = pin_candidate(args.recipe, args.module, args.candidate, root, args.generated_on)
            candidate = f'candidate {record["file"]} sha256 {record["sha256"]}' if record.get('sha256') not in (None, PENDING) else 'no candidate yet'
            print(f'PINNED {args.module}: board layout sha256 {record["layout"]}; {candidate}; recipe still validates.')
            return 0
        if args.command == 'promote':
            promote(args.recipe, args.run_dir, args.modules, root)
            return 0
        if args.command == 'coverage':
            result = appearance_coverage(args.appearance, args.inventory, root)
            if args.json_out:
                target = Path(args.json_out).expanduser().resolve()
                check(protected_location(target, root) is None and not target.exists(), f'{target} must be a new file outside protected folders')
                target.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8')
            print(coverage_markdown(result), end='')
            return 0
        plan = load_plan(args.recipe, root, args.modules)
        out = check_output_dir(args.out, root)
        godot = find_godot(args.godot, root)
        parent = log_parent(args.log_dir, out, root)
        try:
            temporary = tempfile.TemporaryDirectory(prefix='art-recipe-godot-logs-', dir=parent)
        except OSError as error:
            raise RecipeError(f'Cannot create a temporary Godot log folder in {parent}: {error}')
        with temporary as logs:
            return run(plan, out, godot, args.strict, args.timeout, Path(logs))
    except RecipeError as error:
        print(f'INVALID (nothing written): {error}', file=sys.stderr)
        return 2
    except RunFailure as error:
        print(f'FAIL: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
