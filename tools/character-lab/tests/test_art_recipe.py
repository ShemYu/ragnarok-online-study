"""Recipe validation, comparison and reporting for art_recipe.py (inspection D14).

Run: PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tools/character-lab/tests -p 'test_*.py'

The synthetic tests build a miniature repository in a temporary directory and
need no RO files, art packs or Godot; a fake Godot stands in for the gate and
the importers. Two opt-in tests use the local study pack and the real Godot:
  ART_RECIPE_LOCAL=1  validate the shipped recipe; strict head gate writes nothing
  ART_RECIPE_FULL=1   full reproduction into a temporary directory (slow)
"""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import sys
import tempfile
import unittest
from unittest import mock
import zlib

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import art_recipe  # noqa: E402

REPO = Path(__file__).resolve().parents[3]
RECIPE = REPO / 'tools/character-lab/recipes/wayfarer-saved-art-v1.json'
A = 'tools/character-lab/assets/'
BODY_RECTS = {82: [24, 16, 47, 72], 83: [122, 15, 43, 73], 84: [217, 19, 45, 69], 85: [23, 122, 49, 62], 86: [119, 124, 49, 60], 54: [214, 117, 52, 67]}
BODY_CELLS = {82: [0, 0, 96, 96], 83: [96, 0, 96, 96], 84: [192, 0, 96, 96], 85: [0, 96, 96, 96], 86: [96, 96, 96, 96], 54: [192, 96, 96, 96]}
BACK_RECTS = {87: [30, 19, 35, 69], 88: [126, 19, 35, 69], 89: [219, 17, 41, 71], 90: [25, 121, 45, 63], 91: [121, 122, 45, 62]}
BACK_SEQUENCE = [87, 88, 88, 88, 89, 90, 91, 91, 91]
BACK_DIRECTIONS = ['W', 'NW', 'N', 'NE']


def png_bytes(width, height, seed=0):
    def chunk(kind, data):
        return struct.pack('>I', len(data)) + kind + data + struct.pack('>I', zlib.crc32(kind + data) & 0xffffffff)
    raw = b''.join(b'\0' + bytes([seed % 256]) * (width * 4) for _ in range(height))
    return art_recipe.PNG_SIGNATURE + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)) + chunk(b'IDAT', zlib.compress(raw)) + chunk(b'IEND', b'')


# Stands in for Godot. Gate calls print GATE_<PART> <FAKE_GATE_<PART> or PASS>.
# Import calls first append a byte to FAKE_TAMPER (if set), then follow
# FAKE_IMPORT: "copy" writes the saved pack (FAKE_SAVED_PACK) plus recipe
# provenance hashed like the real importers (FAKE_PROVENANCE: "absent",
# "wrong-module", "wrong-sha" or "wrong-path" corrupt it); anything else fails.
# Every call appends {"script", "log"} to FAKE_CALLS and writes its --log-file.
FAKE_GODOT = '''
import hashlib, json, os, shutil, sys
argv = sys.argv
log = argv[argv.index('--log-file') + 1] if '--log-file' in argv else None
script = argv[argv.index('--script') + 1]
args = argv[argv.index('--') + 1:]
with open(os.environ['FAKE_CALLS'], 'a') as calls:
    calls.write(json.dumps({'script': script, 'log': log}) + '\\n')
if log is None:
    sys.exit(9)
with open(log, 'w') as handle:
    handle.write('fake godot log\\n')
option = lambda name: next((a.split('=', 1)[1] for a in args if a.startswith('--' + name + '=')), None)
if script.endswith('verify_candidate.gd'):
    part = 'BODY' if option('board') or option('part') == 'body' else 'HEAD'
    verdict = os.environ.get('FAKE_GATE_' + part, 'PASS')
    print('GATE_%s %s' % (part, verdict))
    sys.exit(0 if verdict == 'PASS' else 1)
mode = os.environ.get('FAKE_IMPORT', 'fail')
if os.environ.get('FAKE_TAMPER'):
    with open(os.environ['FAKE_TAMPER'], 'ab') as handle:
        handle.write(b' ')
local = lambda value: os.path.join(os.getcwd(), value[len('res://'):]) if value.startswith('res://') else value
digest = lambda path: hashlib.sha256(open(path, 'rb').read()).hexdigest()
if mode == 'new':
    # Plausible new-art pack from the board's own plan (what import_slot_board.gd writes).
    board = option('board')
    layout = json.load(open(local(board) + 'sprite-slots.json'))
    out = option('output-dir')
    part = layout['part']
    def put(rel, data):
        path = os.path.join(out, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        open(path, 'wb').write(data)
        return {'file': rel, 'sha256': hashlib.sha256(data).hexdigest()}
    bible = json.load(open(local(option('style-bible'))))
    pack = {'schemaVersion': 2, 'kind': 'slot-pack', 'part': part, 'nativeSource': layout['nativeSource'],
            'board': {'layout': board + 'sprite-slots.json', 'sha256': digest(local(board) + 'sprite-slots.json')},
            'sourceImage': option('source'), 'sourceImageSha256': digest(local(option('source'))),
            'import': {'palette': {'sha256': bible['palette']['sha256']}},
            'contract': {'pass': True, 'allowedFailure': False, 'bibleSha256': digest(local(option('style-bible')))},
            part: {}, 'diagnostics': {}, 'fixtures': {}, 'verification': {'actUnchanged': True},
            'recipe': {'path': option('recipe'), 'sha256': digest(local(option('recipe'))), 'module': option('recipe-module')}}
    if option('fixture-look'):
        pack['fixtureLook'] = {'file': option('fixture-look')}
    for slot in layout['slots']:
        pack[part][str(slot['index'])] = put('%s/%03d.png' % (part, slot['index']), open(os.path.join(local(board), slot['sourceFile']), 'rb').read())
        pack['diagnostics'][str(slot['index'])] = {'offPalettePixels': 0, 'keyTintedPixels': 0, 'partialAlphaPixels': 0}
    directions = ['S', 'SW', 'W', 'NW', 'N', 'NE', 'E', 'SE']
    extra = int(os.environ.get('FAKE_FRAMES_DELTA', '0'))
    if 'fixtures' not in layout:
        # export_slot_board.gd board: one fixture per view direction, no frame duration recorded.
        for name in layout['view']['directions']:
            frames = [put('fixtures/%s/frame-%02d.png' % (name, i), b'frame %d' % i) for i in range(len(layout['sequences'][name]['slots']) + extra)]
            pack['fixtures'][name] = {'frames': frames, 'sourceAction': layout['groupIndex'] * 8 + directions.index(name)}
    for fixture in layout.get('fixtures', []):
        for name in fixture['directions']:
            sequence = layout['groupSequences'][fixture['group']][name]
            # Fixtures follow the body timeline, like import_slot_board.gd.
            count = sequence.get('bodyFrames', sequence['frames']) + extra
            delay = float(os.environ.get('FAKE_DELAY', sequence.get('bodyDelayMs', sequence['delayMs'])))
            for gear in fixture['headgear']:
                frames = [put('fixtures/%s/%s/%s/frame-%02d.png' % (fixture['group'], name, gear, i), b'frame %d' % i) for i in range(count)]
                pack['fixtures']['%s/%s/%s' % (fixture['group'], name, gear)] = {'group': fixture['group'], 'direction': name, 'headgear': gear,
                    'sourceAction': fixture['groupIndex'] * 8 + directions.index(name), 'frameDurationMs': delay, 'frames': frames}
    json.dump(pack, open(os.path.join(out, 'pack.json'), 'w'))
    print('fake new import done')
    sys.exit(0)
if mode != 'copy':
    sys.exit(3)
saved = os.environ['FAKE_SAVED_PACK']
out = option('output-dir')
manifest = json.load(open(os.path.join(saved, 'pack.json')))
for name in sorted(os.listdir(os.path.join(saved, 'body'))):
    os.makedirs(os.path.join(out, 'body'), exist_ok=True)
    shutil.copy(os.path.join(saved, 'body', name), os.path.join(out, 'body', name))
recipe = option('recipe')
recipe_file = os.path.join(os.getcwd(), recipe[len('res://'):]) if recipe.startswith('res://') else recipe
provenance = {'path': recipe, 'sha256': hashlib.sha256(open(recipe_file, 'rb').read()).hexdigest(), 'module': option('recipe-module')}
damage = os.environ.get('FAKE_PROVENANCE', '')
if damage == 'wrong-module':
    provenance['module'] = 'body'
elif damage == 'wrong-sha':
    provenance['sha256'] = '0' * 64
elif damage == 'wrong-path':
    provenance['path'] = 'res://other-recipe.json'
if damage != 'absent':
    manifest['recipe'] = provenance
json.dump(manifest, open(os.path.join(out, 'pack.json'), 'w'))
print('fake import done')
'''


class World:
    """A miniature repository with the three saved packs the real recipe reproduces."""

    def __init__(self, root):
        self.root = root

    def write(self, rel, data):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return hashlib.sha256(data).hexdigest()

    def json(self, rel, value):
        return self.write(rel, (json.dumps(value, indent=1) + '\n').encode())

    def png(self, rel, width, height, seed=0):
        return self.write(rel, png_bytes(width, height, seed))

    def build(self):
        res = lambda rel: 'res://' + rel  # noqa: E731
        natives = {}
        for name in ['assets/reference-ro/body.act', 'assets/reference-ro/body.spr', 'assets/reference-ro/head.act', A + 'native-equipment-v1/source/cap.act']:
            natives[res(name)] = self.write(name, name.encode())
        body_sources = {k: v for k, v in natives.items() if '/body.' in k}
        palette = self.json('tools/character-lab/style/palette.json', {'id': 'test', 'colors': ['#000000']})
        bible = self.json('tools/character-lab/style/bible.json', {'palette': {'file': res('tools/character-lab/style/palette.json'), 'sha256': palette}, 'slotRules': {'body': {}, 'head': {}}})
        slots, textures = [], {}
        for index, rect in BODY_RECTS.items():
            sha = self.png(A + f'native-template-v1/sprites/body/{index:03d}.png', rect[2], rect[3], index)
            textures[str(index)] = {'file': f'sprites/body/{index:03d}.png', 'sha256': sha, 'width': rect[2], 'height': rect[3]}
            slots.append({'index': index, 'imageRect': rect, 'cell': BODY_CELLS[index], 'sourceFile': f'sprites/body/{index:03d}.png'})
        head_native = self.png(A + 'native-template-v1/sprites/head/001.png', 30, 26)
        template = self.json(A + 'native-template-v1/template.json', {
            'sourceFiles': {k: v for k, v in natives.items() if 'reference-ro' in k},
            'parts': {'body': {'textures': textures}, 'head': {'textures': {'1': {'file': 'sprites/head/001.png', 'sha256': head_native, 'width': 30, 'height': 26}}}}})
        layout = self.json(A + 'native-template-v1/sprite-slots.json', {'canvas': [288, 192], 'slots': slots})
        head_layout = self.json(A + 'native-head-v1/head-slot.json', {'index': 1, 'imageRect': [17, 19, 30, 26], 'canvas': [64, 64], 'cell': [0, 0, 64, 64],
                                                                     'sourceFile': res(A + 'native-template-v1/sprites/head/001.png'), 'sourceFileSha256': head_native,
                                                                     'sourceTemplateSha256': template, 'requiredSourceActions': {'attack': 86, 'ready': 38}})
        equipment = self.json(A + 'native-equipment-v1/equipment.json', {'sourceFiles': {k: v for k, v in natives.items() if 'cap' in k}})
        board_dir = A + 'boards/back/'
        board_slots = []
        for index, rect in BACK_RECTS.items():
            sha = self.png(board_dir + f'sprites/body/{index:03d}.png', rect[2], rect[3])
            column, row = (index - 87) % 3, (index - 87) // 3
            board_slots.append({'index': index, 'imageRect': rect, 'cell': [column * 96, row * 96, 96, 96], 'sourceFile': f'sprites/body/{index:03d}.png', 'sourceSha256': sha})
        board = self.json(board_dir + 'sprite-slots.json', {'part': 'body', 'group': 'attack2', 'groupIndex': 10, 'canvas': [288, 192], 'slots': board_slots,
                                                            'sourceFiles': body_sources, 'view': {'directions': BACK_DIRECTIONS},
                                                            'sequences': {d: {'delayMs': 96.0, 'slots': BACK_SEQUENCE} for d in BACK_DIRECTIONS}})
        self.json(A + 'slot-inventory/test.json', {'parts': {'body': {'uniqueSlotCount': 118}, 'head': {'uniqueSlotCount': 15}}})
        body_image = self.png(A + 'native-wayfarer-v2/costume-slot-board.png', 1536, 1024)
        head_image = self.png(A + 'native-head-v1/generated-head.png', 1254, 1254)
        back_image = self.png(board_dir + 'candidates/v2/candidate.png', 1536, 1024)
        palette_record = {'file': res('tools/character-lab/style/palette.json'), 'sha256': palette, 'id': 'test'}
        self.saved = {}
        body_pack = A + 'native-wayfarer-v3/'
        self.saved['body'] = {'sourceImage': res(A + 'native-wayfarer-v2/costume-slot-board.png'), 'sourceImageSha256': body_image,
                              'originalTemplate': res(A + 'native-template-v1/template.json'), 'originalTemplateSha256': template, 'slotMetadataSha256': layout,
                              'import': {'palette': palette_record, 'normalizedBoard': {'file': 'costume/imported-board.png', 'sha256': self.png(body_pack + 'costume/imported-board.png', 288, 192, 1)}},
                              'body': {str(i): {'file': f'costume/body/{i:03d}.png', 'sha256': self.png(body_pack + f'costume/body/{i:03d}.png', r[2], r[3], 2)} for i, r in BODY_RECTS.items()}}
        self.json(body_pack + 'costume.json', self.saved['body'])
        head_pack = A + 'native-head-v2/'
        self.saved['head'] = {'sourceImage': res(A + 'native-head-v1/generated-head.png'), 'sourceImageSha256': head_image, 'originalTemplateSha256': template,
                              'slotMetadataSha256': head_layout, 'equipmentManifestSha256': equipment, 'costumeManifest': res(body_pack + 'costume.json'),
                              'sourceFiles': dict(natives), 'import': {'palette': palette_record},
                              'head': {'1': {'file': 'head/001.png', 'sha256': self.png(head_pack + 'head/001.png', 30, 26, 3)}}}
        self.json(head_pack + 'head.json', self.saved['head'])
        self.back_pack = self.root / A / 'native-wayfarer-attack-back-v2'
        back_pack = A + 'native-wayfarer-attack-back-v2/'
        self.saved['back'] = {'name': 'back v2', 'board': {'layout': res(board_dir + 'sprite-slots.json'), 'sha256': board}, 'sourceImage': res(board_dir + 'candidates/v2/candidate.png'),
                              'sourceImageSha256': back_image, 'contract': {'bible': res('tools/character-lab/style/bible.json'), 'bibleSha256': bible, 'pass': True, 'allowedFailure': False},
                              'import': {'palette': palette_record}, 'verification': {'actUnchanged': True},
                              'fixtures': {d: {'sourceAction': 80 + art_recipe.DIRECTIONS.index(d), 'frames': [{'sourceFrame': i} for i in range(9)]} for d in BACK_DIRECTIONS},
                              'body': {str(i): {'file': f'body/{i:03d}.png', 'sha256': self.png(back_pack + f'body/{i:03d}.png', r[2], r[3], 4)} for i, r in BACK_RECTS.items()}}
        self.json(back_pack + 'pack.json', self.saved['back'])
        self.json('tools/character-lab/appearances/look.json', {'parts': {}})
        self.recipe = {
            'schemaVersion': 1, 'kind': 'artwork-reproduction-recipe', 'id': 'test', 'version': '1.0.0',
            'style': {'bible': {'file': res('tools/character-lab/style/bible.json'), 'sha256': bible}, 'palette': {'file': palette_record['file'], 'sha256': palette}},
            'nativeSources': natives,
            'modules': [
                {'id': 'body', 'part': 'body', 'adapter': 'native-costume-v1', 'status': 'accepted', 'gate': 'strict', 'output': 'native-wayfarer-v3',
                 'reproduces': {'pack': res(body_pack), 'manifest': 'costume.json'},
                 'generatedImage': {'file': res(A + 'native-wayfarer-v2/costume-slot-board.png'), 'sha256': body_image, 'size': [1536, 1024]},
                 'template': {'file': res(A + 'native-template-v1/template.json'), 'sha256': template},
                 'layout': {'file': res(A + 'native-template-v1/sprite-slots.json'), 'sha256': layout, 'canvas': [288, 192],
                            'slots': [{'index': i, 'use': ['ready' if i == 54 else 'attack'], 'imageRect': r} for i, r in BODY_RECTS.items()]},
                 'action': copy.deepcopy(art_recipe.ADAPTERS['native-costume-v1']['action']),
                 'expectedManifestDifferences': [{'path': 'contract', 'reason': 'gated now'}, {'path': 'recipe', 'reason': 'provenance'}]},
                {'id': 'head', 'part': 'head', 'adapter': 'native-head-v1', 'status': 'historical', 'gate': 'recorded-failure',
                 'recordedFailure': {'since': '2026-09-25', 'reason': 'undersized', 'replacement': 'head v3, not generated'}, 'output': 'native-head-v2',
                 'reproduces': {'pack': res(head_pack), 'manifest': 'head.json'},
                 'generatedImage': {'file': res(A + 'native-head-v1/generated-head.png'), 'sha256': head_image, 'size': [1254, 1254]},
                 'template': {'file': res(A + 'native-template-v1/template.json'), 'sha256': template},
                 'layout': {'file': res(A + 'native-head-v1/head-slot.json'), 'sha256': head_layout, 'canvas': [64, 64],
                            'slots': [{'index': 1, 'use': ['attack', 'ready'], 'imageRect': [17, 19, 30, 26]}]},
                 'equipment': {'file': res(A + 'native-equipment-v1/equipment.json'), 'sha256': equipment, 'variants': ['none', 'cap', 'hat']},
                 'fixtureBody': 'body', 'action': copy.deepcopy(art_recipe.ADAPTERS['native-head-v1']['action']),
                 'expectedManifestDifferences': [{'path': 'recipe', 'reason': 'provenance'}]},
                {'id': 'back', 'part': 'body', 'adapter': 'slot-board-v1', 'status': 'pending-visual-review', 'gate': 'strict', 'output': 'native-wayfarer-attack-back-v2',
                 'name': 'back v2', 'reproduces': {'pack': res(back_pack), 'manifest': 'pack.json'},
                 'generatedImage': {'file': res(board_dir + 'candidates/v2/candidate.png'), 'sha256': back_image, 'size': [1536, 1024]},
                 'layout': {'file': res(board_dir + 'sprite-slots.json'), 'sha256': board, 'canvas': [288, 192],
                            'slots': [{'index': i, 'use': ['attack'], 'imageRect': r} for i, r in BACK_RECTS.items()]},
                 'action': {'attack': {'group': 'attack2', 'groupIndex': 10, 'directions': BACK_DIRECTIONS, 'sequence': BACK_SEQUENCE, 'frameDurationMs': 96}},
                 'expectedManifestDifferences': [{'path': 'recipe', 'reason': 'provenance'}]},
            ],
            'coverage': {'inventory': res(A + 'slot-inventory/test.json'), 'parts': {'body': {'total': 118, 'gameplay': 94}, 'head': {'total': 15}}},
            'decisions': ['decide later'],
        }
        return self

    def build_new(self):
        """A board_export.gd-style board for two walk drawings, and an import recipe for NEW art."""
        res = lambda rel: 'res://' + rel  # noqa: E731
        board = A + 'completion-2026-10-02/boards/test-walk-S/'
        bible = self.recipe['style']['bible']
        slots = []
        for index, rect, cell in [(5, [24, 16, 47, 72], [0, 0, 96, 96]), (6, [122, 15, 43, 73], [96, 0, 96, 96])]:
            sha = self.png(board + f'sprites/body/{index:03d}.png', rect[2], rect[3], index)
            slots.append({'part': 'body', 'index': index, 'cell': cell, 'imageRect': rect, 'sourceFile': f'sprites/body/{index:03d}.png', 'sourceSha256': sha, 'rawFacing': ['S'], 'roles': ['walk']})
        character = self.json('tools/character-lab/characters/test.json', {'schemaVersion': 2, 'id': 'test', 'label': 'Test', 'parts': {'body': {'costume': 'test'}}})
        reference = self.png('tools/character-lab/assets/test-reference.png', 4, 4, 9)
        self.json(board + 'sprite-slots.json', {
            'schemaVersion': 2, 'kind': 'slot-board', 'id': 'test-walk-S', 'label': 'Test walk S', 'job': 'swordsman-male', 'part': 'body', 'groups': ['walk'], 'group': 'walk', 'groupIndex': 1,
            'view': {'directions': ['S'], 'rawFacing': ['S'], 'contextDirection': 'S'}, 'nativeSource': 'res://assets/reference-ro/body',
            'sourceFiles': {k: v for k, v in self.recipe['nativeSources'].items() if '/body.' in k},
            'groupSequences': {'walk': {'S': {'slots': [5, 6, 5, 6], 'mirrored': False, 'delayMs': 96.0, 'frames': 4}}},
            'fixtures': [{'group': 'walk', 'groupIndex': 1, 'directions': ['S'], 'headgear': ['none']}],
            'canvas': [288, 192], 'scale': 5, 'slots': slots,
            'boards': {'designReferences': [{'file': 'design-reference-1.png', 'from': res('tools/character-lab/assets/test-reference.png'), 'fromSha256': reference, 'role': 'test'}]},
            'character': res('tools/character-lab/characters/test.json'), 'characterSha256': character,
            'styleBible': bible['file'], 'styleBibleSha256': bible['sha256']})
        self.candidate = res(board + 'candidates/v1/candidate.png')
        self.png(board + 'candidates/v1/candidate.png', 1536, 1024, 1)
        return {
            'schemaVersion': 1, 'kind': 'artwork-import-recipe', 'id': 'test-new', 'version': '1.0.0',
            'style': {'bible': {'file': bible['file'], 'sha256': 'PENDING'}, 'palette': dict(self.recipe['style']['palette'])},
            'nativeSources': dict(self.recipe['nativeSources']),
            'modules': [{'id': 'test-walk', 'part': 'body', 'adapter': 'slot-board-v2', 'status': 'pending-visual-review', 'gate': 'strict',
                         'output': 'test-walk', 'install': res(A + 'completion-2026-10-02/packs/test-walk'),
                         'layout': {'file': res(board + 'sprite-slots.json'), 'sha256': 'PENDING', 'slots': [{'index': 5, 'use': ['walk']}, {'index': 6, 'use': ['walk']}]},
                         'generatedImage': {'sha256': 'PENDING'}}],
            'coverage': {'parts': {'body': {'total': 118}}},
        }

    def build_head_board(self, body_timeline=True):
        """A board_export.gd head board (head SPR 1 on the 64x64 head-board geometry) and its new-art module."""
        res = lambda rel: 'res://' + rel  # noqa: E731
        board = A + 'completion-2026-10-02/boards/test-head/'
        bible = self.recipe['style']['bible']
        # Exported boards record the file's hash even while the recipe's pin is pending.
        bible_sha = hashlib.sha256((self.root / bible['file'][len('res://'):]).read_bytes()).hexdigest()
        sha = self.png(board + 'sprites/head/001.png', 30, 26, 1)
        character = self.json('tools/character-lab/characters/test.json', {'schemaVersion': 2, 'id': 'test', 'label': 'Test', 'parts': {'head': {'description': 'test'}}})
        # The head's own attack action has 1 frame here; fixtures must follow the 9-frame body timeline.
        sequence = {'slots': [1], 'mirrored': True, 'delayMs': 96.0, 'frames': 1}
        if body_timeline:
            sequence.update(bodyFrames=9, bodyDelayMs=96.0)
        self.json(board + 'sprite-slots.json', {
            'schemaVersion': 2, 'kind': 'slot-board', 'id': 'test-head', 'job': 'swordsman-male', 'part': 'head', 'groups': ['attack2'], 'group': 'attack2', 'groupIndex': 10,
            'view': {'directions': ['E'], 'rawFacing': ['SW']}, 'nativeSource': 'res://assets/reference-ro/head',
            'sourceFiles': {k: v for k, v in self.recipe['nativeSources'].items() if '/head.' in k},
            'groupSequences': {'attack2': {'E': sequence}},
            'fixtures': [{'group': 'attack2', 'groupIndex': 10, 'directions': ['E'], 'headgear': ['none', 'cap']}],
            'canvas': [64, 64], 'scale': 16, 'boards': {'designReferences': []},
            'slots': [{'part': 'head', 'index': 1, 'cell': [0, 0, 64, 64], 'imageRect': [17, 19, 30, 26], 'sourceFile': 'sprites/head/001.png', 'sourceSha256': sha}],
            'character': res('tools/character-lab/characters/test.json'), 'characterSha256': character,
            'styleBible': bible['file'], 'styleBibleSha256': bible_sha})
        self.head_candidate = res(board + 'candidates/v1/candidate.png')
        self.png(board + 'candidates/v1/candidate.png', 1024, 1024, 2)
        return {'id': 'test-head', 'part': 'head', 'adapter': 'slot-board-v2', 'status': 'pending-visual-review', 'gate': 'strict', 'output': 'test-head',
                'layout': {'file': res(board + 'sprite-slots.json'), 'sha256': 'PENDING', 'slots': [{'index': 1, 'use': ['attack']}]},
                'generatedImage': {'sha256': 'PENDING'}}

    def build_legacy_board(self):
        """A board written by the older export_slot_board.gd (no fixture plan, no style bible) and its new-art module."""
        res = lambda rel: 'res://' + rel  # noqa: E731
        board = A + 'boards/test-walk-legacy/'
        slots = []
        for index, rect, cell in [(5, [24, 16, 47, 72], [0, 0, 96, 96]), (6, [122, 15, 43, 73], [96, 0, 96, 96])]:
            sha = self.png(board + f'sprites/body/{index:03d}.png', rect[2], rect[3], index)
            slots.append({'part': 'body', 'index': index, 'cell': cell, 'imageRect': rect, 'sourceFile': f'sprites/body/{index:03d}.png', 'sourceSha256': sha})
        self.json(board + 'sprite-slots.json', {
            'schemaVersion': 1, 'job': 'swordsman-male', 'part': 'body', 'group': 'walk', 'groupIndex': 1,
            'view': {'directions': ['S'], 'rawFacing': ['S'], 'contextDirection': 'S'}, 'nativeSource': 'res://assets/reference-ro/body',
            'sourceFiles': {k: v for k, v in self.recipe['nativeSources'].items() if '/body.' in k},
            'sequences': {'S': {'slots': [5, 6, 5, 6], 'mirrored': False, 'delayMs': 96.0}}, 'canvas': [288, 192], 'scale': 5, 'slots': slots})
        self.legacy_candidate = res(board + 'candidates/v1/candidate.png')
        self.png(board + 'candidates/v1/candidate.png', 1536, 1024, 3)
        return {'id': 'test-legacy', 'part': 'body', 'adapter': 'slot-board-v2', 'status': 'pending-visual-review', 'gate': 'strict', 'output': 'test-legacy',
                'layout': {'file': res(board + 'sprite-slots.json'), 'sha256': 'PENDING', 'slots': [{'index': 5, 'use': ['walk']}, {'index': 6, 'use': ['walk']}]},
                'generatedImage': {'sha256': 'PENDING'}}

    def save_recipe(self, recipe=None):
        path = self.root / 'recipe.json'
        path.write_text(json.dumps(recipe or self.recipe))
        return path


class SyntheticBase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.base = Path(self.temp.name)
        self.root = self.base / 'repo'
        self.world = World(self.root).build()

    def tearDown(self):
        self.temp.cleanup()

    def plan(self, recipe=None, selected=None):
        return art_recipe.load_plan(self.world.save_recipe(recipe), self.root, selected)

    def rejects(self, mutate, message, recipe=None):
        recipe = copy.deepcopy(recipe or self.world.recipe)
        mutate(recipe)
        with self.assertRaises(art_recipe.RecipeError) as raised:
            self.plan(recipe)
        self.assertIn(message, str(raised.exception))

    def rejects_world(self, message):
        with self.assertRaises(art_recipe.RecipeError) as raised:
            self.plan()
        self.assertIn(message, str(raised.exception))


class ValidationTest(SyntheticBase):
    def test_valid_recipe_expresses_the_six_slot_body_layout(self):
        plan = self.plan()
        self.assertEqual([m['id'] for m in plan['modules']], ['body', 'head', 'back'])
        self.assertEqual([s['index'] for s in plan['modules'][0]['slots']], [82, 83, 84, 85, 86, 54])
        self.assertIn('res://assets/reference-ro/body.act', plan['inputs'])
        # Native drawings feeding the gate are pinned run inputs.
        self.assertIn('res://' + A + 'native-template-v1/sprites/body/054.png', plan['inputs'])
        self.assertIn('res://' + A + 'boards/back/sprites/body/091.png', plan['inputs'])
        self.assertTrue(plan['coverage']['inventoryChecked'])

    def test_generic_five_slot_attack_layout_cannot_stand_in_for_the_body_pack(self):
        def drop_ready(recipe):
            recipe['modules'][0]['layout']['slots'] = recipe['modules'][0]['layout']['slots'][:5]
        self.rejects(drop_ready, 'differ from the recipe')

    def test_ready_slot_must_be_declared(self):
        def relabel(recipe):
            recipe['modules'][0]['layout']['slots'][5]['use'] = ['attack']
        self.rejects(relabel, 'attack slots')

    def test_changed_sources_are_rejected(self):
        for rel in ['assets/reference-ro/body.act', A + 'native-template-v1/sprite-slots.json',
                    'tools/character-lab/style/palette.json', A + 'native-wayfarer-v2/costume-slot-board.png']:
            with self.subTest(rel=rel):
                path = self.root / rel
                original = path.read_bytes()
                path.write_bytes(original + b' ')
                self.rejects_world('changed')
                path.write_bytes(original)

    def test_same_size_altered_native_drawings_are_rejected(self):
        for rel in [A + 'native-template-v1/sprites/body/084.png', A + 'boards/back/sprites/body/089.png', A + 'native-template-v1/sprites/head/001.png']:
            with self.subTest(rel=rel):
                path = self.root / rel
                original = path.read_bytes()
                width, height = art_recipe.png_size(path)
                path.write_bytes(png_bytes(width, height, 200))
                self.rejects_world('changed')
                path.write_bytes(original)

    def test_template_must_record_native_drawing_hashes(self):
        template_path = self.root / A / 'native-template-v1/template.json'
        template = json.loads(template_path.read_text())
        del template['parts']['body']['textures']['85']
        sha = self.world.json(A + 'native-template-v1/template.json', template)
        recipe = copy.deepcopy(self.world.recipe)
        for module in recipe['modules'][:2]:
            module['template']['sha256'] = sha
        with self.assertRaises(art_recipe.RecipeError) as raised:
            self.plan(recipe)
        self.assertIn('no recorded hash for body SPR 85', str(raised.exception))

    def test_changed_saved_evidence_is_rejected(self):
        (self.root / A / 'native-head-v2/head/001.png').write_bytes(png_bytes(30, 26, 9))
        self.rejects_world('saved evidence')

    def test_missing_inputs_are_rejected(self):
        (self.root / A / 'native-head-v1/generated-head.png').unlink()
        self.rejects_world('missing file')

    def test_slot_geometry_must_match_native_drawings(self):
        sha = self.world.png(A + 'native-template-v1/sprites/body/084.png', 44, 69)
        template_path = self.root / A / 'native-template-v1/template.json'
        template = json.loads(template_path.read_text())
        template['parts']['body']['textures']['84']['sha256'] = sha
        template_sha = self.world.json(A + 'native-template-v1/template.json', template)
        recipe = copy.deepcopy(self.world.recipe)
        for module in recipe['modules'][:2]:
            module['template']['sha256'] = template_sha
        with self.assertRaises(art_recipe.RecipeError) as raised:
            self.plan(recipe)
        self.assertIn('native SPR drawing is 44x69', str(raised.exception))

    def test_canvas_must_match_generated_aspect_ratio(self):
        self.rejects(lambda r: r['modules'][0]['layout'].update(canvas=[200, 192]), 'aspect ratio')

    def test_generated_image_must_be_the_saved_packs_source(self):
        sha = self.world.png(A + 'native-head-v1/generated-head.png', 1254, 1000)
        recipe = copy.deepcopy(self.world.recipe)
        recipe['modules'][1]['generatedImage'].update(sha256=sha, size=[1254, 1000])
        with self.assertRaises(art_recipe.RecipeError) as raised:
            self.plan(recipe)
        self.assertIn('imported from', str(raised.exception))

    def test_adapter_action_contract_is_enforced(self):
        self.rejects(lambda r: r['modules'][0]['action']['attack'].update(direction=2), 'is not what native-costume-v1 implements')
        self.rejects(lambda r: r['modules'][0]['action']['attack'].update(direction=True), 'is not what native-costume-v1 implements')

    def test_board_sequence_must_match(self):
        self.rejects(lambda r: r['modules'][2]['action']['attack'].update(sequence=[87, 88, 89, 90, 91]), 'board sequence')

    def test_schema_errors_are_rejected(self):
        self.rejects(lambda r: r.update(schemaVersion=2), 'schemaVersion')
        self.rejects(lambda r: r.update(schemaVersion=True), 'schemaVersion')
        self.rejects(lambda r: r.update(schemaVersion=1.0), 'schemaVersion')
        self.rejects(lambda r: r.update(extra=True), 'unknown keys')
        self.rejects(lambda r: r['modules'][0].update(adapter='magic'), 'unknown adapter')
        self.rejects(lambda r: r['modules'][0].pop('layout'), 'missing "layout"')
        self.rejects(lambda r: r['modules'][1].update(fixtureBody='back'), 'fixtureBody')
        self.rejects(lambda r: r['modules'][0]['expectedManifestDifferences'].append({'path': 'x'}), 'needs "path" and "reason"')
        self.rejects(lambda r: r['modules'][0]['layout']['slots'][0].update(index=True), 'expected int')

    def test_failing_head_cannot_be_accepted_or_relabelled(self):
        self.rejects(lambda r: r['modules'][1].update(status='accepted'), 'only a historical module may record a gate failure')
        self.rejects(lambda r: r['modules'][1].update(output='native-head-v3'), 'never relabelled')
        self.rejects(lambda r: r['modules'][1].pop('recordedFailure'), 'recordedFailure')

    def test_selection_needs_fixture_body(self):
        with self.assertRaises(art_recipe.RecipeError):
            self.plan(selected=['head'])
        self.assertEqual([m['id'] for m in self.plan(selected=['head', 'body'])['modules']], ['body', 'head'])

    def test_output_directory_must_be_new_and_isolated(self):
        for bad in [self.root / A / 'new-pack', self.root / 'docs/out', self.root.parent]:
            with self.assertRaises(art_recipe.RecipeError):
                art_recipe.check_output_dir(bad, self.root)
        busy = self.base / 'busy'
        busy.mkdir()
        (busy / 'file').write_text('x')
        with self.assertRaises(art_recipe.RecipeError):
            art_recipe.check_output_dir(busy, self.root)
        fresh = self.base / 'fresh'
        self.assertEqual(art_recipe.check_output_dir(fresh, self.root), fresh.resolve())

    def test_log_folder_must_exist_and_stay_outside_output_and_protected_folders(self):
        out = (self.base / 'out').resolve()
        with self.assertRaises(art_recipe.RecipeError):
            art_recipe.log_parent(str(self.base / 'missing'), out, self.root)
        (self.root / 'docs').mkdir()
        with self.assertRaises(art_recipe.RecipeError):
            art_recipe.log_parent(str(self.root / 'docs'), out, self.root)
        self.assertEqual(art_recipe.log_parent(str(self.base), out, self.root), self.base.resolve())


class CoverageValidationTest(SyntheticBase):
    def test_malformed_inventory_is_rejected_before_writes(self):
        (self.root / A / 'slot-inventory/test.json').write_text('{not json')
        self.rejects_world('coverage.inventory')
        (self.root / A / 'slot-inventory/test.json').write_text(json.dumps({'parts': {'body': {'uniqueSlotCount': '118'}, 'head': {'uniqueSlotCount': 15}}}))
        self.rejects_world('no uniqueSlotCount')
        (self.root / A / 'slot-inventory/test.json').write_text(json.dumps([1, 2]))
        self.rejects_world('expected {"parts"')

    def test_invalid_coverage_entries_are_rejected(self):
        self.rejects(lambda r: r['coverage']['parts'].update(body={'total': 'x'}), 'positive integer')
        self.rejects(lambda r: r['coverage']['parts'].update(body={'total': True}), 'positive integer')
        self.rejects(lambda r: r['coverage']['parts'].update(body=[118]), 'expected')
        self.rejects(lambda r: r['coverage']['parts'].update(body={'total': 118, 'gameplay': 200}), 'exceed')
        self.rejects(lambda r: r['coverage']['parts'].pop('head'), "no declared drawing total for part 'head'")
        self.rejects(lambda r: r['coverage']['parts'].update(body={'total': 117}), 'slot inventory lists 118')
        self.rejects(lambda r: r['coverage']['parts'].update(head={'total': 0}), 'positive integer')
        self.rejects(lambda r: r['coverage'].update(extra=1), 'unknown keys')
        self.rejects(lambda r: r.update(coverage=[]), 'expected an object')

    def test_missing_inventory_is_reported_as_declaration_only(self):
        (self.root / A / 'slot-inventory/test.json').unlink()
        plan = self.plan()
        self.assertFalse(plan['coverage']['inventoryChecked'])
        self.assertIn('not available', ' '.join(plan['coverage']['notes']))


class BoundaryTest(SyntheticBase):
    def outside_copy(self, rel):
        source = self.root / rel
        target = self.base / ('outside-' + source.name)
        shutil.copy(source, target)
        return source, target

    def test_symlinked_input_outside_the_repository_is_rejected(self):
        source, target = self.outside_copy(A + 'native-head-v1/generated-head.png')
        source.unlink()
        source.symlink_to(target)
        self.rejects_world('resolves outside')

    def test_symlinked_saved_record_outside_the_pack_is_rejected(self):
        source, target = self.outside_copy(A + 'native-head-v2/head/001.png')
        source.unlink()
        source.symlink_to(target)
        self.rejects_world('resolves outside')

    def test_saved_records_cannot_climb_out_of_their_pack(self):
        escape = self.root / A / 'escape.png'
        escape.write_bytes(png_bytes(30, 26, 3))
        sha = hashlib.sha256(escape.read_bytes()).hexdigest()
        for file in ['../escape.png', str(escape), 'head/../../escape.png']:
            with self.subTest(file=file):
                saved = copy.deepcopy(self.world.saved['head'])
                saved['head']['1'] = {'file': file, 'sha256': sha}
                self.world.json(A + 'native-head-v2/head.json', saved)
                self.rejects_world('must be relative and must not climb out')

    def test_recipe_paths_cannot_climb_out_of_the_repository(self):
        self.rejects(lambda r: r['modules'][1]['generatedImage'].update(file='res://../outside.png'), 'climb out')
        self.rejects(lambda r: r['modules'][1]['generatedImage'].update(file='/etc/hosts'), 'res:// path')

    def test_degenerate_paths_are_recipe_errors(self):
        for value in ['', '.', './', '././']:
            with self.subTest(value=value):
                with self.assertRaises(art_recipe.RecipeError):
                    art_recipe.contained(self.root, value, 'test')
                with self.assertRaises(art_recipe.RecipeError):
                    art_recipe.res_path(self.root, 'res://' + value, 'test')
        recipe = copy.deepcopy(self.world.recipe)
        recipe['modules'][1]['generatedImage']['file'] = 'res://.'
        with mock.patch('sys.stdout'), mock.patch('sys.stderr'):
            self.assertEqual(art_recipe.main(['validate', str(self.world.save_recipe(recipe))], self.root), 2)

    def test_reproduced_records_outside_their_pack_are_problems(self):
        new_dir = self.base / 'out'
        new_dir.mkdir()
        new = {'body': {'87': {'file': '../outside.png', 'sha256': '0' * 64}}}
        result = art_recipe.compare_records(self.root, {}, new, new_dir, ['body'])
        self.assertTrue(any('climb out' in problem for problem in result['problems']))


class FakeGodotBase(SyntheticBase):
    recipe_file = None

    def setUp(self):
        super().setUp()
        self.calls = self.base / 'calls.jsonl'
        self.log_parent = self.base / 'log-parent'
        self.log_parent.mkdir()
        self.godot = self.base / 'fake-godot'
        self.godot.write_text(f'#!{sys.executable}\n{FAKE_GODOT}')
        self.godot.chmod(self.godot.stat().st_mode | stat.S_IXUSR)

    def run_cli(self, out, *extra, env=None):
        environment = {'FAKE_CALLS': str(self.calls), 'FAKE_SAVED_PACK': str(self.world.back_pack), **(env or {})}
        recipe = self.recipe_file or self.world.save_recipe()
        arguments = ['run', str(recipe), '--out', str(out), '--godot', str(self.godot), '--log-dir', str(self.log_parent), *extra]
        with mock.patch.dict(os.environ, environment), mock.patch('sys.stdout'), mock.patch('sys.stderr'):
            return art_recipe.main(arguments, self.root)

    def calls_made(self):
        return [json.loads(line) for line in self.calls.read_text().splitlines()] if self.calls.exists() else []

    def assert_logs_private(self, out):
        calls = self.calls_made()
        self.assertTrue(calls)
        for call in calls:
            log = Path(call['log'])
            self.assertTrue(log.is_absolute(), call)
            self.assertTrue(log.resolve().is_relative_to(self.log_parent.resolve()), call)
            self.assertFalse(log.resolve().is_relative_to(out.resolve().parent / out.name), call)
        self.assertEqual(list(self.log_parent.iterdir()), [], 'temporary log folder must be removed')

    def report(self, out):
        return json.loads((out / art_recipe.REPORT_JSON).read_text())


class RunTest(FakeGodotBase):
    def test_strict_head_gate_failure_writes_nothing(self):
        out = self.base / 'out-strict'
        code = self.run_cli(out, '--strict', env={'FAKE_GATE_HEAD': 'FAIL'})
        self.assertEqual(code, 1)
        self.assertFalse(out.exists())
        self.assertTrue(all(call['script'].endswith('verify_candidate.gd') for call in self.calls_made()))
        self.assert_logs_private(out)

    def test_recorded_failure_that_now_passes_writes_nothing(self):
        out = self.base / 'out-stale'
        self.assertEqual(self.run_cli(out, env={'FAKE_GATE_HEAD': 'PASS'}), 1)
        self.assertFalse(out.exists())
        self.assertTrue(all(call['script'].endswith('verify_candidate.gd') for call in self.calls_made()))

    def test_failing_accepted_body_writes_nothing(self):
        out = self.base / 'out-body'
        self.assertEqual(self.run_cli(out, env={'FAKE_GATE_HEAD': 'FAIL', 'FAKE_GATE_BODY': 'FAIL'}), 1)
        self.assertFalse(out.exists())

    def test_invalid_recipe_or_missing_godot_exits_2_before_writing(self):
        recipe = copy.deepcopy(self.world.recipe)
        recipe['modules'][0]['layout']['sha256'] = '0' * 64
        self.world.save_recipe(recipe)
        out = self.base / 'out-invalid'
        with mock.patch('sys.stdout'), mock.patch('sys.stderr'):
            code = art_recipe.main(['run', str(self.root / 'recipe.json'), '--out', str(out), '--godot', str(self.godot)], self.root)
            self.assertEqual(code, 2)
            code = art_recipe.main(['run', str(self.world.save_recipe()), '--out', str(out), '--godot', str(self.base / 'no-godot')], self.root)
            self.assertEqual(code, 2)
        self.assertFalse(out.exists())
        self.assertEqual(self.calls_made(), [])

    def test_selected_back_view_reproduces_and_reports_only_what_ran(self):
        out = self.base / 'out-back'
        code = self.run_cli(out, '--module', 'back', env={'FAKE_IMPORT': 'copy'})
        report = self.report(out)
        self.assertEqual(code, 0, report['problems'])
        self.assertEqual(report['result'], 'PASS')
        self.assertEqual(report['selectedModules'], ['back'])
        self.assertFalse(report['freshBrowserValidation'])
        text = '\n'.join(report['invariants'])
        self.assertIn('5/5 saved PNGs', text)
        self.assertIn('Not selected, so not imported or checked: body, head', text)
        self.assertNotIn('reproduced body module', text)
        self.assertEqual(set(report['coverage']['parts']), {'body'})
        self.assertEqual(sorted(report['logs']), ['gate-back.log', 'import-back.log'])
        self.assertTrue((out / art_recipe.REPORT_MD).is_file())
        self.assert_logs_private(out)

    def test_import_failure_report_claims_nothing_unchecked(self):
        out = self.base / 'out-fail'
        code = self.run_cli(out, env={'FAKE_GATE_HEAD': 'FAIL'})
        report = self.report(out)
        self.assertEqual(code, 1)
        self.assertEqual(report['result'], 'FAIL')
        self.assertEqual(report['modules']['body']['import'], 'failed')
        self.assertEqual(report['modules']['head']['import'], 'skipped after body failed')
        text = '\n'.join(report['invariants'])
        self.assertIn('No output comparison for body (import failed)', text)
        self.assertNotIn('byte for byte', text)
        self.assertNotIn('confirmed', text)
        self.assertNotIn('reproduced body module', text)
        self.assertIn('not compared', (out / art_recipe.REPORT_MD).read_text())

    def test_input_changed_during_run_is_reported(self):
        out = self.base / 'out-tamper'
        palette = self.root / 'tools/character-lab/style/palette.json'
        code = self.run_cli(out, env={'FAKE_GATE_HEAD': 'FAIL', 'FAKE_IMPORT': 'tamper', 'FAKE_TAMPER': str(palette)})
        report = self.report(out)
        self.assertEqual(code, 1)
        self.assertIn('input changed during the run: res://tools/character-lab/style/palette.json', report['problems'])
        self.assertIn('1 of', '\n'.join(report['invariants']))
        self.assertTrue(any('protected file changed' in problem for problem in report['problems']))

    def test_validate_command(self):
        with mock.patch('sys.stdout'), mock.patch('sys.stderr'):
            self.assertEqual(art_recipe.main(['validate', str(self.world.save_recipe())], self.root), 0)

    def test_correct_recipe_provenance_is_required(self):
        for damage in ['absent', 'wrong-module', 'wrong-sha', 'wrong-path']:
            with self.subTest(damage=damage):
                out = self.base / f'out-provenance-{damage}'
                code = self.run_cli(out, '--module', 'back', env={'FAKE_IMPORT': 'copy', 'FAKE_PROVENANCE': damage})
                report = self.report(out)
                self.assertEqual(code, 1)
                self.assertEqual(report['result'], 'FAIL')
                self.assertTrue(any('recipe provenance matches the validated recipe failed' in p for p in report['problems']), report['problems'])
                checks = {c['name']: c['ok'] for c in report['modules']['back']['comparison']['checks']}
                self.assertFalse(checks['recipe provenance matches the validated recipe'])

    def test_recipe_changed_during_import_is_reported(self):
        out = self.base / 'out-recipe-edit'
        recipe = self.root / 'recipe.json'
        code = self.run_cli(out, '--module', 'back', env={'FAKE_IMPORT': 'copy', 'FAKE_TAMPER': str(recipe)})
        report = self.report(out)
        self.assertEqual(code, 1)
        self.assertFalse(report['recipe']['unchangedAfterRun'])
        self.assertTrue(any(p.startswith('recipe changed during the run') for p in report['problems']), report['problems'])
        # The importer hashed the edited bytes, so its provenance no longer matches the validated recipe.
        self.assertTrue(any('recipe provenance matches the validated recipe failed' in p for p in report['problems']))
        self.assertIn('The recipe file changed or disappeared during the run', '\n'.join(report['invariants']))

    def test_recipe_hash_names_the_validated_bytes(self):
        path = self.world.save_recipe()
        plan = art_recipe.load_plan(path, self.root)
        self.assertEqual(plan['recipeSha256'], hashlib.sha256(path.read_bytes()).hexdigest())

    def test_recipe_changed_during_validation_is_rejected_before_output(self):
        # The edit happens inside load_plan, after the recipe was parsed and while
        # inputs are still being validated, so the old parse must not get the new hash.
        out = self.base / 'out-recipe-during'
        original = art_recipe.validate_coverage
        edits = []

        def edit_then_validate(root, recipe, modules):
            path = self.root / 'recipe.json'
            edited = dict(recipe, description='edited while being validated')
            path.write_text(json.dumps(edited))
            edits.append(hashlib.sha256(path.read_bytes()).hexdigest())
            return original(root, recipe, modules)

        with mock.patch.object(art_recipe, 'validate_coverage', edit_then_validate):
            with self.assertRaises(art_recipe.RecipeError) as raised:
                art_recipe.load_plan(self.world.save_recipe(), self.root)
            self.assertIn('changed during validation', str(raised.exception))
            code = self.run_cli(out, '--module', 'back', env={'FAKE_IMPORT': 'copy'})
        self.assertEqual(len(edits), 2)
        self.assertEqual(code, 2)
        self.assertFalse(out.exists())
        self.assertEqual(self.calls_made(), [])

    def test_recipe_changed_after_validation_writes_nothing(self):
        out = self.base / 'out-recipe-late'
        original = art_recipe.load_plan

        def load_then_edit(*args, **kwargs):
            plan = original(*args, **kwargs)
            with open(plan['recipePath'], 'ab') as handle:
                handle.write(b' ')
            return plan

        with mock.patch.object(art_recipe, 'load_plan', load_then_edit):
            code = self.run_cli(out, '--module', 'back', env={'FAKE_IMPORT': 'copy'})
        self.assertEqual(code, 2)
        self.assertFalse(out.exists())
        self.assertEqual(self.calls_made(), [])


class NewArtTest(FakeGodotBase):
    """New art: no saved pack, PENDING pins filled by lock/pin, run verifies the pack itself, promote installs it."""

    def setUp(self):
        super().setUp()
        self.world.recipe = self.world.build_new()
        self.path = self.world.save_recipe()
        self.recipe_file = self.path

    def quiet(self, *arguments):
        with mock.patch('sys.stdout'), mock.patch('sys.stderr'):
            return art_recipe.main(list(arguments), self.root)

    def locked_and_pinned(self):
        self.assertEqual(self.quiet('lock', str(self.path)), 0)
        self.assertEqual(self.quiet('pin', str(self.path), '--module', 'test-walk', '--candidate', self.world.candidate), 0)
        return json.loads(self.path.read_text())

    def test_pending_pins_need_lock_and_run_refuses_pending_candidates(self):
        self.assertEqual(self.quiet('validate', str(self.path)), 2)  # style bible still PENDING
        self.assertEqual(self.quiet('lock', str(self.path)), 0)
        recipe = json.loads(self.path.read_text())
        bible = self.root / 'tools/character-lab/style/bible.json'
        self.assertEqual(recipe['style']['bible']['sha256'], hashlib.sha256(bible.read_bytes()).hexdigest())
        self.assertTrue(art_recipe.SHA.fullmatch(recipe['modules'][0]['layout']['sha256']))
        self.assertEqual(recipe['modules'][0]['layout']['slots'][0]['imageRect'], [24, 16, 47, 72])
        plan = art_recipe.load_plan(self.path, self.root)
        self.assertTrue(plan['modules'][0]['pending'])
        out = self.base / 'out-pending'
        self.assertEqual(self.run_cli(out, env={'FAKE_IMPORT': 'new'}), 2)
        self.assertFalse(out.exists())
        self.assertEqual(self.calls_made(), [])

    def test_pin_checks_the_board_and_candidate_location(self):
        self.quiet('lock', str(self.path))
        before = self.path.read_bytes()
        outside = 'res://' + A + 'outside.png'
        self.world.png(A + 'outside.png', 1536, 1024)
        self.assertEqual(self.quiet('pin', str(self.path), '--module', 'test-walk', '--candidate', outside), 2)
        self.assertEqual(self.path.read_bytes(), before, 'a refused pin must leave the recipe unchanged')
        recipe = json.loads(before)
        recipe['modules'][0]['layout']['slots'] = [{'index': 6, 'use': ['walk']}, {'index': 5, 'use': ['walk']}]
        self.path.write_text(json.dumps(recipe))
        self.assertEqual(self.quiet('pin', str(self.path), '--module', 'test-walk', '--candidate', self.world.candidate), 2)

    def test_new_art_run_verifies_the_pack_and_promote_installs_it_once(self):
        self.locked_and_pinned()
        out = self.base / 'out-new'
        code = self.run_cli(out, env={'FAKE_IMPORT': 'new'})
        report = json.loads((out / art_recipe.REPORT_JSON).read_text())
        self.assertEqual(code, 0, report['problems'])
        checks = {c['name']: c['ok'] for c in report['modules']['test-walk']['comparison']['checks']}
        self.assertTrue(all(checks.values()), checks)
        self.assertTrue(any('fixture plan rendered' in name for name in checks))
        text = '\n'.join(report['invariants'])
        self.assertIn('test-walk is NEW art', text)
        self.assertNotIn('byte for byte', text)
        self.assertEqual(self.quiet('promote', str(self.path), '--from', str(out)), 0)
        installed = self.root / A / 'completion-2026-10-02/packs/test-walk/pack.json'
        self.assertTrue(installed.is_file())
        self.assertEqual(self.quiet('promote', str(self.path), '--from', str(out)), 2, 'installed packs are never overwritten')

    def test_new_art_problems_fail_the_run(self):
        self.locked_and_pinned()
        out = self.base / 'out-new-bad'
        code = self.run_cli(out, env={'FAKE_IMPORT': 'new', 'FAKE_TAMPER': str(self.root / A / 'completion-2026-10-02/boards/test-walk-S/sprites/body/005.png')})
        report = json.loads((out / art_recipe.REPORT_JSON).read_text())
        self.assertEqual(code, 1)
        self.assertTrue(any('input changed during the run' in p for p in report['problems']))
        self.assertEqual(self.quiet('promote', str(self.path), '--from', str(out)), 2, 'a failed run is never promoted')

    def test_new_module_rules(self):
        locked = self.locked_and_pinned()
        for mutate, message in [
            (lambda m: m.update(gate='recorded-failure'), 'strict gate'),
            (lambda m: m.update(install='res://' + A + 'native-wayfarer-v3'), 'install'),
            (lambda m: m.update(status='historical'), 'status'),
            (lambda m: m.update(reproduces={}), 'unknown keys'),
            (lambda m: m['generatedImage'].update(file='res://' + A + 'outside.png'), 'candidates'),
        ]:
            with self.subTest(message=message):
                self.world.png(A + 'outside.png', 1536, 1024)
                recipe = copy.deepcopy(locked)
                mutate(recipe['modules'][0])
                if recipe['modules'][0]['generatedImage'].get('file', '').endswith('outside.png'):
                    recipe['modules'][0]['generatedImage']['sha256'] = hashlib.sha256((self.root / A / 'outside.png').read_bytes()).hexdigest()
                self.path.write_text(json.dumps(recipe))
                with self.assertRaises(art_recipe.RecipeError) as raised:
                    art_recipe.load_plan(self.path, self.root)
                self.assertIn(message, str(raised.exception))

    def use_module(self, module, coverage_part):
        recipe = json.loads(self.path.read_text())
        recipe['modules'] = [module]
        recipe['coverage'] = {'parts': {coverage_part: {'total': 118 if coverage_part == 'body' else 15}}}
        self.path.write_text(json.dumps(recipe))
        self.assertEqual(self.quiet('lock', str(self.path)), 0)

    def run_new(self, name, **env):
        out = self.base / name
        code = self.run_cli(out, env={'FAKE_IMPORT': 'new', **{k: str(v) for k, v in env.items()}})
        return code, json.loads((out / art_recipe.REPORT_JSON).read_text())

    def timeline_check(self, report, module):
        return next(c for c in report['modules'][module]['comparison']['checks'] if c['name'].startswith('fixture plan rendered'))

    def test_head_fixtures_are_checked_against_the_body_timeline(self):
        self.use_module(self.world.build_head_board(), 'head')
        self.assertEqual(self.quiet('pin', str(self.path), '--module', 'test-head', '--candidate', self.world.head_candidate), 0)
        code, report = self.run_new('out-head')
        self.assertEqual(code, 0, report['problems'])
        self.assertTrue(self.timeline_check(report, 'test-head')['ok'])
        for name, env in [('out-head-frames', {'FAKE_FRAMES_DELTA': -8}), ('out-head-delay', {'FAKE_DELAY': 100})]:
            with self.subTest(tamper=name):
                code, report = self.run_new(name, **env)
                self.assertEqual(code, 1)
                self.assertFalse(self.timeline_check(report, 'test-head')['ok'])

    def test_head_board_without_body_timeline_cannot_pass(self):
        self.use_module(self.world.build_head_board(body_timeline=False), 'head')
        self.assertEqual(self.quiet('pin', str(self.path), '--module', 'test-head', '--candidate', self.world.head_candidate), 0)
        code, report = self.run_new('out-head-old')
        self.assertEqual(code, 1)
        check = self.timeline_check(report, 'test-head')
        self.assertFalse(check['ok'])
        self.assertIn('no body timeline', check['detail'])

    def test_legacy_export_slot_board_boards_import_as_new_art(self):
        module = self.world.build_legacy_board()
        self.use_module(module, 'body')
        self.assertEqual(self.quiet('pin', str(self.path), '--module', 'test-legacy', '--candidate', self.world.legacy_candidate), 0)
        code, report = self.run_new('out-legacy')
        self.assertEqual(code, 0, report['problems'])
        self.assertTrue(self.timeline_check(report, 'test-legacy')['ok'])
        code, report = self.run_new('out-legacy-bad', FAKE_FRAMES_DELTA=1)
        self.assertEqual(code, 1)
        recipe = json.loads(self.path.read_text())
        recipe['modules'][0]['fixtureLook'] = {'appearance': 'res://tools/character-lab/appearances/look.json'}
        self.path.write_text(json.dumps(recipe))
        with self.assertRaises(art_recipe.RecipeError) as raised:
            art_recipe.load_plan(self.path, self.root)
        self.assertIn('native other parts only', str(raised.exception))

    def test_candidate_from_an_identical_older_board(self):
        self.use_module(self.world.build_head_board(), 'head')
        old = 'res://' + A + 'native-head-v3/candidates/old-01.png'
        self.world.png(A + 'native-head-v3/candidates/old-01.png', 1254, 1254, 4)
        self.assertEqual(self.quiet('pin', str(self.path), '--module', 'test-head', '--candidate', old), 2, 'outside the board without --generated-on')
        same_geometry = 'res://' + A + 'native-head-v1/head-slot.json'
        self.assertEqual(self.quiet('pin', str(self.path), '--module', 'test-head', '--candidate', old, '--generated-on', same_geometry), 0)
        self.assertEqual(json.loads(self.path.read_text())['modules'][0]['generatedImage']['generatedOn']['file'], same_geometry)
        other = 'res://' + A + 'native-template-v1/sprite-slots.json'
        with mock.patch('sys.stdout'), mock.patch('sys.stderr'):
            with self.assertRaises(art_recipe.RecipeError) as raised:
                art_recipe.pin_candidate(self.path, 'test-head', old, self.root, other)
        self.assertIn('differs from this board', str(raised.exception))

    def test_coverage_reports_native_fallback_per_action_and_direction(self):
        self.world.json(A + 'slot-inventory/coverage.json', {
            'groups': ['idle', 'walk'], 'gameUsesGroups': {'0': 'idle', '1': 'walk'},
            'parts': {'body': {'uniqueSlotCount': 3, 'gameSubsetSlotCount': 3, 'groups': {
                'idle': {'slots': [0], 'byDirection': [[0]] * 8},
                'walk': {'slots': [5, 6], 'byDirection': [[5, 6]] + [[5]] * 7}}}}})
        self.world.json(A + 'packs-test/pack.json', {'body': {'5': {'file': 'x.png', 'sha256': '0' * 64}}})
        self.world.json('tools/character-lab/appearances/test-look.json', {'parts': {'body': [
            {'manifest': 'res://' + A + 'packs-test/pack.json', 'field': 'body'},
            {'manifest': 'res://' + A + 'missing/pack.json', 'field': 'body', 'optional': True}]}})
        result = art_recipe.appearance_coverage('res://tools/character-lab/appearances/test-look.json', 'res://' + A + 'slot-inventory/coverage.json', self.root)
        rows = {row['state']: row for row in result['parts']['body']['groups']}
        self.assertEqual(rows['idle']['status'], 'native fallback')
        self.assertEqual(rows['walk']['status'], 'partial 1/2')
        self.assertEqual(rows['walk']['directions']['S'], 'partial')
        self.assertEqual(rows['walk']['directions']['N'], 'complete')
        self.assertEqual(result['unavailablePacks'], ['res://' + A + 'missing/pack.json'])
        self.assertIn('native fallback', art_recipe.coverage_markdown(result))


class ComparisonTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.new_dir = self.root / 'out'
        self.png = png_bytes(4, 4, 5)
        (self.new_dir / 'body').mkdir(parents=True)
        (self.new_dir / 'body/082.png').write_bytes(self.png)
        sha = hashlib.sha256(self.png).hexdigest()
        self.saved = {'body': {'82': {'file': 'body/082.png', 'sha256': sha}}, 'verification': {'actionsSha256': 'a', 'actUnchanged': True}}

    def tearDown(self):
        self.temp.cleanup()

    def test_identical_bytes_with_declared_provenance_pass(self):
        new = copy.deepcopy(self.saved)
        new['recipe'] = {'path': '/x.json', 'sha256': 'b', 'module': 'body'}
        result = art_recipe.compare_records(self.root, self.saved, new, self.new_dir, ['recipe'])
        self.assertEqual(result['problems'], [])
        self.assertEqual((result['pngs'], result['pngsByteIdentical']), (1, 1))
        self.assertEqual(result['observedExpected'], ['recipe'])

    def test_undeclared_difference_fails(self):
        new = copy.deepcopy(self.saved)
        new['verification']['actionsSha256'] = 'changed'
        result = art_recipe.compare_records(self.root, self.saved, new, self.new_dir, ['recipe'])
        self.assertTrue(any('verification.actionsSha256' in p for p in result['problems']))

    def test_boolean_is_not_a_number(self):
        new = copy.deepcopy(self.saved)
        new['verification']['actUnchanged'] = 1
        self.assertEqual(art_recipe.json_diff(self.saved, new), [('verification.actUnchanged', 'changed')])

    def test_changed_png_bytes_fail(self):
        (self.new_dir / 'body/082.png').write_bytes(png_bytes(4, 4, 6))
        result = art_recipe.compare_records(self.root, self.saved, copy.deepcopy(self.saved), self.new_dir, [])
        self.assertEqual(result['pngsByteIdentical'], 0)
        self.assertTrue(result['problems'])

    def test_json_diff_paths(self):
        self.assertEqual(art_recipe.json_diff({'a': [1, {'b': 2}]}, {'a': [1, {'b': 3}], 'c': 1}), [('a[1].b', 'changed'), ('c', 'added')])
        self.assertEqual(art_recipe.json_diff({'d': 96}, {'d': 96.0}), [])
        self.assertTrue(art_recipe.covered('contract.slots.1', ['contract']))
        self.assertFalse(art_recipe.covered('contractor', ['contract']))


def local_pack_available():
    return RECIPE.is_file() and (REPO / art_recipe.DEFAULT_GODOT).is_file() and (REPO / A / 'native-wayfarer-v3/costume.json').is_file()


@unittest.skipUnless(os.environ.get('ART_RECIPE_LOCAL') and local_pack_available(), 'set ART_RECIPE_LOCAL=1 with the local study pack')
class LocalRecipeTest(unittest.TestCase):
    def test_shipped_recipe_validates(self):
        plan = art_recipe.load_plan(RECIPE)
        self.assertEqual([m['id'] for m in plan['modules']], ['body-attack-front', 'head-v2-historical', 'body-attack-back-v2'])
        self.assertEqual([s['index'] for s in plan['modules'][0]['slots']], [82, 83, 84, 85, 86, 54])

    def test_strict_gate_rejects_old_head_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary, 'strict')
            with mock.patch('sys.stdout'), mock.patch('sys.stderr'):
                code = art_recipe.main(['run', str(RECIPE), '--out', str(out), '--strict', '--module', 'body-attack-front', '--module', 'head-v2-historical', '--log-dir', temporary])
            self.assertEqual(code, 1)
            self.assertFalse(out.exists())


@unittest.skipUnless(os.environ.get('ART_RECIPE_FULL') and local_pack_available(), 'set ART_RECIPE_FULL=1 with the local study pack (slow)')
class FullReproductionTest(unittest.TestCase):
    def test_reproduces_saved_packs_byte_for_byte(self):
        with tempfile.TemporaryDirectory() as temporary:
            out = Path(temporary, 'reproduction')
            code = art_recipe.main(['run', str(RECIPE), '--out', str(out), '--log-dir', temporary])
            report = json.loads((out / art_recipe.REPORT_JSON).read_text())
            self.assertEqual(code, 0, report['problems'])
            self.assertEqual(report['result'], 'PASS')
            self.assertFalse(report['freshBrowserValidation'])
            for module in report['modules'].values():
                self.assertEqual(module['comparison']['pngs'], module['comparison']['pngsByteIdentical'])


if __name__ == '__main__':
    unittest.main()
