import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {composeNative, headAttachment, nativePartFrame, pixelDifference} from '../native-core.mjs';

const base = new URL('../assets/native-template-v1/', import.meta.url);
const equipmentBase = new URL('../assets/native-equipment-v1/', import.meta.url);
const headBase = new URL('../assets/native-head-v1/', import.meta.url);
const repository = new URL('../../../', import.meta.url);
const readJson = url => JSON.parse(readFileSync(url));
const template = readJson(new URL('template.json', base));
const equipment = readJson(new URL('equipment.json', equipmentBase));
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
function freeze(value) {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
}
freeze(template);
freeze(equipment);

function solid(width, height, color) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let index = 0; index < data.length; index += 4) data.set(color, index);
  return {width, height, data};
}

function fixtures(model) {
  const colors = {body:[24,83,92,255],head:[240,188,142,255],headgear:[84,42,22,255],weapon:[125,146,155,255],trail:[250,236,185,128]};
  return Object.fromEntries(Object.entries(model.parts).map(([part, source]) => [part,
    Object.fromEntries(Object.entries(source.textures).map(([slot, image]) => [slot, solid(image.width, image.height, colors[part])]))
  ]));
}

test('one native head drawing follows the original nine-frame neck trajectory', () => {
  const action = template.parts.head.actions.attack;
  assert.equal(action.sourceAction, 86);
  assert.equal(action.delayMs, 96);
  assert.equal(action.frames.length, 9);
  assert.deepEqual(Object.keys(template.parts.head.textures), ['1']);
  assert.deepEqual([template.parts.head.textures[1].width, template.parts.head.textures[1].height], [30,26]);
  const expectedCenters = [[-5,-77],[-7,-80],[-8,-81],[-8,-81],[10,-73],[18,-61],[19,-58],[19,-58],[19,-58]];
  for (let index = 0; index < 9; index++) {
    const body = nativePartFrame(template, 'body', index);
    const head = nativePartFrame(template, 'head', index);
    const visible = head.layers.filter(layer => layer.index >= 0);
    assert.deepEqual(visible.map(layer => layer.index), [1], 'Reuse the same face/hair drawing rather than generating nine inconsistent heads.');
    const layer = visible[0];
    assert.deepEqual([layer.x,layer.y], expectedCenters[index]);
    assert.deepEqual(headAttachment(body,head), [0,0]);
    assert.equal(layer.mirror, true);
    assert.equal(layer.rotation, 0);
    assert.deepEqual(layer.scale, [1,1]);
    assert.deepEqual([layer.x - body.anchors[0][0],layer.y - body.anchors[0][1]], [-2,-11]);
    // With mirroring, the anchor is 2 px right / 11 px below the image center.
    assert.deepEqual([15 - (body.anchors[0][0] - layer.x),13 + body.anchors[0][1] - layer.y], [13,24]);
  }
});

test('source cap and hat keep their native registration relative to the head', () => {
  for (const [name,part] of Object.entries(equipment.parts)) {
    for (let index = 0; index < 9; index++) {
      const body = nativePartFrame(template, 'body', index);
      const head = nativePartFrame(template, 'head', index);
      const gear = part.actions.attack.frames[index];
      const headLayer = head.layers.find(layer => layer.index >= 0);
      const gearLayer = gear.layers.find(layer => layer.index >= 0);
      assert.deepEqual(headAttachment(body,gear), [0,0], `${name} keeps its original ACT attachment.`);
      assert.deepEqual([gearLayer.x - headLayer.x,gearLayer.y - headLayer.y], [-2,-7]);
      assert.equal(gearLayer.mirror,headLayer.mirror);
      assert.equal(gearLayer.rotation,headLayer.rotation);
    }
  }
});

test('head-only texture replacement cannot move or change body, headgear, dagger or trail', () => {
  for (const gear of ['none','cap','hat']) {
    const model = gear === 'none' ? template : freeze({...template,parts:{...template.parts,headgear:equipment.parts[gear]}});
    const original = fixtures(model);
    const replacement = {...original,head:{1:solid(30,26,[125,65,28,255])}};
    const sourceRecord = JSON.stringify(model);
    const originalHead = original.head[1].data.slice();
    for (let index = 0; index < 9; index++) {
      const source = composeNative(model,original,index);
      const changed = composeNative(model,replacement,index);
      assert.ok(pixelDifference(source,changed).pixels > 0, `Head choice must be visible with ${gear}, frame ${index}.`);
      assert.deepEqual(composeNative(model,replacement,index,{head:false}),composeNative(model,original,index,{head:false}), `Other modules stay identical with ${gear}, frame ${index}.`);
      const headMask = composeNative(model,original,index,{body:false,headgear:false,weapon:false,trail:false});
      for (let pixel = 0; pixel < source.data.length; pixel += 4) {
        if (headMask.data[pixel + 3] !== 0) continue;
        assert.deepEqual(changed.data.subarray(pixel,pixel + 4),source.data.subarray(pixel,pixel + 4), `Head pixels cannot affect another region with ${gear}, frame ${index}.`);
      }
      assert.deepEqual(composeNative(model,original,index),source, 'Switching back restores the original head without changing a held composite.');
    }
    assert.deepEqual(original.head[1].data,originalHead);
    assert.equal(JSON.stringify(model),sourceRecord, 'Source action/attachment records remain untouched.');
  }
});

test('replacement head asset occupies source slot 1 and preserves every source ACT record', () => {
  const head = readJson(new URL('head.json',headBase));
  assert.deepEqual(Object.keys(head.head), ['1']);
  const asset = head.head[1];
  assert.equal(asset.sourceIndex,1);
  assert.deepEqual([asset.width,asset.height],[30,26]);
  const png = readFileSync(new URL(asset.file,headBase));
  assert.deepEqual([...png.subarray(0,8)],[137,80,78,71,13,10,26,10]);
  assert.deepEqual([png.readUInt32BE(16),png.readUInt32BE(20)],[30,26]);
  assert.equal(sha256(png),asset.sha256);
  assert.equal(head.verification.allACTDataUnchanged,true);
  assert.deepEqual(head.verification.afterReplacementActionsSha256,head.verification.originalActionsSha256);
  for (const [source,hash] of Object.entries(head.sourceFiles)) {
    assert.ok(source.startsWith('res://'));
    assert.equal(sha256(readFileSync(new URL(source.slice('res://'.length),repository))),hash, `${source} is unchanged.`);
  }
  for (const gear of ['none','cap','hat']) {
    const sequence = head.sequences[gear];
    assert.equal(sequence.sourceAction,86);
    assert.equal(sequence.frameDurationMs,96);
    assert.equal(sequence.durationMs,864);
    assert.equal(sequence.frames.length,9);
    for (const frame of sequence.frames) {
      const bytes = readFileSync(new URL(frame.file,headBase));
      assert.deepEqual([bytes.readUInt32BE(16),bytes.readUInt32BE(20)],template.canvas);
      assert.equal(sha256(bytes),frame.sha256);
    }
  }
});
