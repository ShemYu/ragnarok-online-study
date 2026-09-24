import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {nativeFrameAt, nativePartFrame, headAttachment, composeNative, pixelDifference} from '../native-core.mjs';

const assets = new URL('../assets/native-template-v1/', import.meta.url);
const repository = new URL('../../../', import.meta.url);
const template = JSON.parse(readFileSync(new URL('template.json', assets)));
const costume = JSON.parse(readFileSync(new URL('costume.json', assets)));
const attackSlots = [82, 83, 83, 83, 84, 85, 86, 86, 86];
const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');

test('real action 86 retains native drawing reuse and nine 96 ms frames', () => {
  const action = template.parts.body.actions.attack;
  assert.equal(action.sourceAction, 86);
  assert.equal(action.delayMs, 96);
  assert.deepEqual(action.frames.map(frame => frame.layers.map(layer => layer.index)), attackSlots.map(index => [index]));
  assert.equal(template.sequences.attack.durationMs, 864);
  assert.equal(template.sequences.attack.exportedFrameCount, 9);
  assert.deepEqual(template.sequences.attack.frames.map(frame => frame.sourceFrame), [0,1,2,3,4,5,6,7,8]);
  assert.ok(template.sequences.attack.frames.every(frame => frame.durationMs === 96));
  assert.ok(action.frames.every(frame => frame.layers.every(layer => layer.mirror && layer.rotation === 0 && layer.scale[0] === 1 && layer.scale[1] === 1)));
});

test('native timeline changes only at source frame boundaries and holds the last pose', () => {
  assert.equal(nativeFrameAt(-1, 9, 96), 0);
  for (let frame = 0; frame < 9; frame++) {
    assert.equal(nativeFrameAt(frame * 96, 9, 96), frame);
    assert.equal(nativeFrameAt((frame + 1) * 96 - 0.001, 9, 96), frame);
  }
  assert.equal(nativeFrameAt(864, 9, 96), 8);
  assert.equal(nativeFrameAt(10000, 9, 96), 8);
});

test('attachment uses parent minus child anchors and safely handles absent anchors', () => {
  assert.deepEqual(headAttachment({anchors:[[12,-62]]}, {anchors:[[-3,-66]]}), [15,4]);
  assert.deepEqual(headAttachment({anchors:[]}, {anchors:[[0,0]]}), [0,0]);
  assert.deepEqual(headAttachment({anchors:[[0,0]]}, {anchors:[]}), [0,0]);
  for (let frame = 0; frame < 9; frame++) {
    assert.deepEqual(headAttachment(nativePartFrame(template, 'body', frame), nativePartFrame(template, 'head', frame)), [0,0]);
  }
});

test('the source dagger stays hidden for frames 0–4 and uses slot 2 for frames 5–8', () => {
  for (let frame = 0; frame < 9; frame++) {
    const visible = nativePartFrame(template, 'weapon', frame).layers.filter(layer => layer.index >= 0);
    assert.deepEqual(visible.map(layer => layer.index), frame < 5 ? [] : [2]);
    if (frame < 5) {
      const image = composeNative(template, {}, frame, {body:false,head:false,trail:false});
      assert.ok(image.data.every(value => value === 0), `Hidden dagger frame ${frame} must remain transparent without loading a texture.`);
    }
  }
});

test('replacement files occupy exactly the original SPR slots and dimensions', () => {
  const expected = {54:[52,67],82:[47,72],83:[43,73],84:[45,69],85:[49,62],86:[49,60]};
  assert.deepEqual(Object.keys(costume.body).map(Number), Object.keys(expected).map(Number));
  for (const [index, size] of Object.entries(expected)) {
    const meta = costume.body[index], original = template.parts.body.textures[index];
    assert.equal(meta.sourceIndex, Number(index));
    assert.deepEqual([meta.width,meta.height], size);
    assert.deepEqual([original.width,original.height], size);
    const bytes = readFileSync(new URL(meta.file, assets));
    assert.deepEqual([...bytes.subarray(0,8)], [137,80,78,71,13,10,26,10]);
    assert.equal(bytes.toString('ascii',12,16), 'IHDR');
    assert.deepEqual([bytes.readUInt32BE(16),bytes.readUInt32BE(20)], size, `PNG dimensions must fit SPR ${index}.`);
    assert.equal(sha256(bytes), meta.sha256, `Replacement SPR ${index} must match its recorded file.`);
  }
});

test('all four original ACT files are unchanged from the exported template', () => {
  const records = Object.entries(template.sourceFiles).filter(([path]) => path.endsWith('.act'));
  assert.equal(records.length, 4);
  for (const [source, digest] of records) {
    assert.ok(source.startsWith('res://assets/reference-ro/'));
    const bytes = readFileSync(new URL(source.slice('res://'.length), repository));
    assert.equal(sha256(bytes), digest, `${source} must not change when importing costume pixels.`);
  }
});

const layer = (index, extras={}) => ({index,x:0,y:0,mirror:false,scale:[1,1],rotation:0,color:[1,1,1,1],...extras});
const rgba = (...colors) => ({width:colors.length,height:1,data:new Uint8ClampedArray(colors.flat())});
const pixel = (image,x,y) => [...image.data.subarray((y*image.width+x)*4,(y*image.width+x+1)*4)];
function smallTemplate(bodyLayers) {
  return {canvas:[8,8],origin:[3,3],parts:Object.fromEntries(['body','head','weapon','trail'].map(part => [part, {actions:{attack:{frames:[{layers:part==='body'?bodyLayers:[],anchors:[]}]}}}]))};
}

test('composition uses ACT image indices, offsets and mirroring; hidden layers never request pixels', () => {
  const source = smallTemplate([layer(-1),layer(7,{x:1,mirror:true})]);
  const colors = rgba([255,0,0,255],[0,0,255,255]);
  const image = composeNative(source, {body:{7:colors}}, 0);
  assert.deepEqual(pixel(image,3,2), [0,0,255,255]);
  assert.deepEqual(pixel(image,4,2), [255,0,0,255]);
  assert.equal([...image.data].filter((_,index) => index % 4 === 3 && image.data[index] > 0).length, 2);
  source.parts.body.actions.attack.frames[0].layers[1].mirror = false;
  const unmirrored = composeNative(source, {body:{7:colors}}, 0);
  assert.deepEqual(pixel(unmirrored,3,2), [255,0,0,255]);
  assert.deepEqual(pixel(unmirrored,4,2), [0,0,255,255]);
  assert.equal(pixelDifference(image,unmirrored).pixels, 2);
});

test('composition applies head attachment and visibility without changing the source action', () => {
  const source = smallTemplate([]);
  source.parts.body.actions.attack.frames[0].anchors = [[2,-2]];
  source.parts.head.actions.attack.frames[0] = {layers:[layer(3)],anchors:[[-1,-3]]};
  const before = JSON.stringify(source);
  const textures = {head:{3:rgba([0,255,0,255])}};
  assert.deepEqual(pixel(composeNative(source,textures,0),5,3), [0,255,0,255]);
  assert.ok(composeNative(source,textures,0,{head:false}).data.every(value => value === 0));
  assert.equal(JSON.stringify(source), before);
});
