// Palette-indexed Wayfarer packs (inspection A1–A3). Requires the local asset pack.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {composeNative, pixelDifference} from '../native-core.mjs';
import {readPng} from './png.mjs';

const assets = new URL('../assets/', import.meta.url);
const repository = new URL('../../../', import.meta.url);
const templateBase = new URL('native-template-v1/', assets);
const bodyBase = new URL('native-wayfarer-v3/', assets);
const headBase = new URL('native-head-v2/', assets);
const equipmentBase = new URL('native-equipment-v1/', assets);
const readJson = url => JSON.parse(readFileSync(url));
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const template = readJson(new URL('template.json', templateBase));
const costume = readJson(new URL('costume.json', bodyBase));
const head = readJson(new URL('head.json', headBase));
const equipment = readJson(new URL('equipment.json', equipmentBase));
const resource = path => new URL(path.replace(/^res:\/\//, ''), repository);

function paletteSet(manifest) {
  const palette = readJson(resource(manifest.import.palette.file));
  assert.equal(sha256(readFileSync(resource(manifest.import.palette.file))), manifest.import.palette.sha256, 'Pack must record the exact palette it was imported with.');
  return {palette, colors: new Set(palette.colors.map(hex => hex.toLowerCase()))};
}

function hex(data, i) {
  return '#' + [data[i], data[i + 1], data[i + 2]].map(v => v.toString(16).padStart(2, '0')).join('');
}

function textures(definitions, base) {
  return Object.fromEntries(Object.entries(definitions).map(([index, meta]) => [index, readPng(new URL(meta.file, base))]));
}

test('body and head packs use one shared style palette', () => {
  assert.equal(costume.import.adapter, 'indexed-majority-v1');
  assert.equal(head.import.adapter, 'indexed-majority-v1');
  assert.equal(costume.import.palette.sha256, head.import.palette.sha256, 'Body and head of one character must share a palette.');
});

for (const [name, manifest, base, slots] of [['body', costume, bodyBase, costume.body], ['head', head, headBase, head.head]]) {
  test(`every opaque ${name} pixel is an exact palette entry with full alpha`, () => {
    const {colors} = paletteSet(manifest);
    for (const [index, meta] of Object.entries(slots)) {
      const image = readPng(new URL(meta.file, base));
      const source = template.parts[name].textures[index];
      assert.deepEqual([image.width, image.height], [source.width, source.height], `Slot ${index} must keep native dimensions.`);
      assert.equal(sha256(readFileSync(new URL(meta.file, base))), meta.sha256);
      const used = new Set();
      for (let i = 0; i < image.data.length; i += 4) {
        const alpha = image.data[i + 3];
        if (!alpha) continue;
        assert.equal(alpha, 255, `Slot ${index} has partial alpha.`);
        const color = hex(image.data, i);
        assert.ok(colors.has(color), `Slot ${index} pixel ${color} is off-palette.`);
        used.add(color);
      }
      assert.ok(used.size <= colors.size && used.size > 8, `Slot ${index} uses ${used.size} colors.`);
      assert.equal(manifest.diagnostics[index].keyTintedPixels, 0);
    }
  });
}

test('indexed packs compose pixel-identically to their Godot fixtures under none/cap/hat', () => {
  const original = Object.fromEntries(Object.entries(template.parts).map(([part, definition]) => [part, textures(definition.textures, templateBase)]));
  const body = {...original.body, ...textures(costume.body, bodyBase)};
  const face = {...original.head, ...textures(head.head, headBase)};
  let compared = 0;
  for (const gear of ['none', 'cap', 'hat']) {
    const model = gear === 'none' ? template : {...template, parts: {...template.parts, headgear: equipment.parts[gear]}};
    const maps = {...original, body, head: face, ...(gear === 'none' ? {} : {headgear: textures(equipment.parts[gear].textures, equipmentBase)})};
    head.sequences[gear].frames.forEach((frame, index) => {
      const result = pixelDifference(composeNative(model, maps, index), readPng(new URL(frame.file, headBase)));
      assert.equal(result.pixels, 0, `${gear} frame ${index} differs by ${result.pixels} pixels`);
      compared++;
    });
  }
  assert.equal(compared, 27);
});

test('body-only fixtures match too, and native ACT records are untouched', () => {
  const original = Object.fromEntries(Object.entries(template.parts).map(([part, definition]) => [part, textures(definition.textures, templateBase)]));
  const maps = {...original, body: {...original.body, ...textures(costume.body, bodyBase)}};
  costume.sequences.attack.frames.forEach((frame, index) => {
    assert.equal(pixelDifference(composeNative(template, maps, index), readPng(new URL(frame.file, bodyBase))).pixels, 0, `frame ${index}`);
  });
  assert.equal(costume.verification.allACTDataUnchanged, true);
  assert.deepEqual(costume.verification.originalActionsSha256, costume.verification.afterReplacementActionsSha256);
  assert.equal(head.verification.allACTDataUnchanged, true);
});
