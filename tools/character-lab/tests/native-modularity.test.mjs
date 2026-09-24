import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {createHash} from 'node:crypto';
import {composeNative, nativePartFrame, pixelDifference} from '../native-core.mjs';

const template = JSON.parse(readFileSync(new URL('../assets/native-template-v1/template.json', import.meta.url)));
const freeze = value => {
  if (value && typeof value === 'object') {
    Object.values(value).forEach(freeze);
    Object.freeze(value);
  }
  return value;
};
freeze(template);

function solid(width, height, rgba) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let i = 0; i < data.length; i += 4) data.set(rgba, i);
  return {width, height, data};
}

function fixtures() {
  const colors = {body:[120,60,35,255],head:[255,210,145,255],weapon:[90,110,155,255],trail:[245,245,255,120]};
  return Object.fromEntries(Object.entries(template.parts).map(([part, source]) => [part,
    Object.fromEntries(Object.entries(source.textures).map(([index, image]) => [index, solid(image.width, image.height, colors[part])]))
  ]));
}

test('replacing body artwork leaves other modules and all source action records unchanged', () => {
  const original = fixtures();
  const replacement = {...original, body:Object.fromEntries(Object.entries(original.body).map(([index, image]) => [index, solid(image.width, image.height, [20,105,110,255])]))};
  const before = JSON.stringify(template);
  const sourcePixels = Object.fromEntries(Object.entries(original.body).map(([index, image]) => [index, image.data.slice()]));
  for (let frame = 0; frame < 9; frame++) {
    const source = composeNative(template, original, frame);
    const costume = composeNative(template, replacement, frame);
    assert.ok(pixelDifference(source, costume).pixels > 0, `Costume change must be visible on source frame ${frame}.`);
    assert.deepEqual(composeNative(template, replacement, frame, {body:false}), composeNative(template, original, frame, {body:false}), `Body replacement must not alter head, weapon or trail on frame ${frame}.`);
    assert.deepEqual(composeNative(template, original, frame), source, `Original frame ${frame} must remain reusable after rendering replacement artwork.`);
  }
  for (const [index, pixels] of Object.entries(sourcePixels)) assert.deepEqual(original.body[index].data, pixels);
  assert.equal(JSON.stringify(template), before);
});

test('layer toggles can render every source frame without changing source frames or returned images', () => {
  const textures = fixtures();
  const original = composeNative(template, textures, 5);
  const heldPixels = original.data.slice();
  for (let mask = 0; mask < 16; mask++) {
    const options = Object.fromEntries(['body','head','weapon','trail'].map((part, bit) => [part, Boolean(mask & (1 << bit))]));
    for (let frame = 0; frame < 9; frame++) {
      const result = composeNative(template, textures, frame, options);
      assert.equal(result.data.length, template.canvas[0] * template.canvas[1] * 4);
      assert.notEqual(result.data, original.data);
      if (mask === 0) assert.ok(result.data.every(channel => channel === 0));
    }
  }
  assert.deepEqual(original.data, heldPixels, 'Later equipment combinations must not overwrite a cached composite.');
});

test('modules reuse their own source frame counts within a shared action timeline', () => {
  const parts = Object.fromEntries(Object.entries({body:3,head:1,weapon:2,trail:2}).map(([part, count]) => [part, {actions:{attack:{frames:Array.from({length:count}, (_, index) => ({label:`${part}-${index}`,layers:[],anchors:[]}))}}}]));
  const source = freeze({canvas:[8,8],origin:[4,4],parts});
  assert.deepEqual([0,1,2].map(frame => nativePartFrame(source,'body',frame).label), ['body-0','body-1','body-2']);
  assert.deepEqual([0,1,2].map(frame => nativePartFrame(source,'head',frame).label), ['head-0','head-0','head-0']);
  assert.deepEqual([0,1,2].map(frame => nativePartFrame(source,'weapon',frame).label), ['weapon-0','weapon-1','weapon-0']);
  for (let frame = 0; frame < 3; frame++) assert.ok(composeNative(source,{},frame).data.every(channel => channel === 0));
});

test('headgear follows its own anchor, draws over the head and can be removed without moving other parts', () => {
  const layer = extras => ({index:0,x:0,y:0,mirror:false,scale:[1,1],rotation:0,color:[1,1,1,1],...extras});
  const part = frames => ({actions:{attack:{frames}}});
  const source = freeze({canvas:[12,12],origin:[4,4],parts:{
    body:part([{anchors:[[4,-2]],layers:[]},{anchors:[[6,-1]],layers:[]}]),
    head:part([{anchors:[[2,-1]],layers:[layer({})]}]),
    headgear:part([{anchors:[[1,-3]],layers:[layer({x:-1,y:-2})]}])
  }});
  const textures = {head:{0:solid(1,1,[255,100,50,255])},headgear:{0:solid(1,1,[30,180,200,255])}};
  const original = JSON.stringify(source);
  const pixel = (image,x,y) => [...image.data.subarray((y*image.width+x)*4,(y*image.width+x+1)*4)];
  const withoutHeadgear = {...source,parts:{body:source.parts.body,head:source.parts.head}};
  for (const [frame,x,y] of [[0,5,2],[1,7,3]]) {
    const equipped = composeNative(source,textures,frame);
    const removed = composeNative(source,textures,frame,{headgear:false});
    assert.deepEqual(pixel(equipped,x,y),[30,180,200,255], 'Headgear uses body anchor minus its own anchor and overlays the head.');
    assert.deepEqual(pixel(removed,x,y),[255,100,50,255]);
    assert.deepEqual(removed,composeNative(withoutHeadgear,textures,frame), 'Removing gear must produce the unchanged underlying head.');
    assert.deepEqual(pixel(composeNative(source,textures,frame,{head:false}),x,y),[30,180,200,255], 'Headgear remains independently visible when the head module is hidden.');
    assert.equal([...equipped.data].filter((value,index) => index%4===3 && value>0).length,1);
  }
  assert.equal(JSON.stringify(source),original);
});

const sha256 = bytes => createHash('sha256').update(bytes).digest('hex');
const repository = new URL('../../../', import.meta.url);
const wayfarerAssets = new URL('../assets/native-wayfarer-v2/', import.meta.url);
const wayfarer = JSON.parse(readFileSync(new URL('costume.json',wayfarerAssets)));
const equipmentAssets = new URL('../assets/native-equipment-v1/', import.meta.url);
const equipment = JSON.parse(readFileSync(new URL('equipment.json',equipmentAssets)));

test('Wayfarer replacement pixels retain native body slot dimensions and the unchanged template', () => {
  assert.deepEqual(Object.keys(wayfarer.body).map(Number),[54,82,83,84,85,86]);
  for (const [index,meta] of Object.entries(wayfarer.body)) {
    const original = template.parts.body.textures[index];
    const png = readFileSync(new URL(meta.file,wayfarerAssets));
    assert.equal(meta.sourceIndex,Number(index));
    assert.deepEqual([meta.width,meta.height],[original.width,original.height]);
    assert.deepEqual([png.readUInt32BE(16),png.readUInt32BE(20)],[original.width,original.height]);
    assert.equal(sha256(png),meta.sha256);
  }
  const originalTemplate = readFileSync(new URL(wayfarer.originalTemplate.slice('res://'.length),repository));
  assert.equal(sha256(originalTemplate),wayfarer.originalTemplateSha256);
  assert.deepEqual(wayfarer.verification.afterReplacementActionsSha256,wayfarer.verification.originalActionsSha256);
  assert.deepEqual(wayfarer.sequences.attack.frames.map(frame => frame.durationMs),Array(9).fill(96));
});

test('native equipment source files and selected attack drawings match the exported manifests', () => {
  assert.deepEqual(Object.keys(equipment.parts).sort(),['cap','hat']);
  for (const [path,hash] of Object.entries(equipment.sourceFiles)) {
    assert.equal(sha256(readFileSync(new URL(path.slice('res://'.length),repository))),hash,`Source equipment file ${path} remains unchanged.`);
  }
  for (const [name,part] of Object.entries(equipment.parts)) {
    const action = part.actions.attack;
    assert.equal(action.sourceAction,86);
    assert.equal(action.delayMs,96);
    assert.equal(action.frames.length,9);
    for (const frame of action.frames) for (const layer of frame.layers.filter(layer => layer.index>=0)) {
      const image = part.textures[layer.index];
      assert.ok(image,`${name} must provide each visible native SPR index.`);
      const png = readFileSync(new URL(image.file,equipmentAssets));
      assert.deepEqual([png.readUInt32BE(16),png.readUInt32BE(20)],[image.width,image.height]);
      assert.equal(sha256(png),image.sha256);
    }
  }
});
