// Source-independent regression tests for native-core.mjs (inspection D13).
// Tiny synthetic ACT/SPR-shaped templates; no RO files, art packs or browser.
import test from 'node:test';
import assert from 'node:assert/strict';
import {nativeFrameAt, nativePartFrame, headAttachment, composeNative, pixelDifference} from '../native-core.mjs';

const RED = [255, 0, 0, 255], BLUE = [0, 0, 255, 255], GREEN = [0, 255, 0, 255], WHITE = [255, 255, 255, 255];

function solid(width, height, color) {
  const data = new Uint8ClampedArray(width * height * 4);
  for (let i = 0; i < width * height; i++) data.set(color, i * 4);
  return {width, height, data};
}

function striped(left, right) {
  // 2x1 image: left pixel, right pixel. Used to see mirroring.
  const data = new Uint8ClampedArray(8);
  data.set(left, 0);
  data.set(right, 4);
  return {width: 2, height: 1, data};
}

function layer(index, extra = {}) {
  return {index, x: 0, y: 0, scale: [1, 1], rotation: 0, mirror: false, color: [1, 1, 1, 1], ...extra};
}

function frame(layers, anchors = []) {
  return {layers, anchors};
}

function template(parts, canvas = [8, 8], origin = [4, 4]) {
  const result = {canvas, origin, parts: {}};
  for (const [name, frames] of Object.entries(parts)) result.parts[name] = {actions: {attack: {frames}}};
  return result;
}

function pixel(image, x, y) {
  const i = (y * image.width + x) * 4;
  return Array.from(image.data.slice(i, i + 4));
}

test('nativeFrameAt holds each frame for its delay and clamps to the last frame', () => {
  assert.equal(nativeFrameAt(0, 9, 96), 0);
  assert.equal(nativeFrameAt(95.9, 9, 96), 0);
  assert.equal(nativeFrameAt(96, 9, 96), 1);
  assert.equal(nativeFrameAt(10000, 9, 96), 8);
  assert.equal(nativeFrameAt(-5, 9, 96), 0);
  assert.throws(() => nativeFrameAt(Number.NaN, 9, 96), RangeError);
  assert.throws(() => nativeFrameAt(0, 0, 96), RangeError);
  assert.throws(() => nativeFrameAt(0, 9, 0), RangeError);
});

test('a part with fewer frames repeats them by body frame modulo', () => {
  const t = template({body: [frame([layer(0)]), frame([layer(1)]), frame([layer(2)])], head: [frame([layer(7)])]});
  assert.equal(nativePartFrame(t, 'body', 2).layers[0].index, 2);
  assert.equal(nativePartFrame(t, 'head', 2).layers[0].index, 7);
});

test('head attachment is body anchor minus head anchor, and zero without anchors', () => {
  assert.deepEqual(headAttachment({anchors: [[3, -20]]}, {anchors: [[1, 2]]}), [2, -22]);
  assert.deepEqual(headAttachment({anchors: []}, {anchors: [[1, 2]]}), [0, 0]);
});

test('a 2x2 drawing is centred on origin + layer offset without recentering', () => {
  const t = template({body: [frame([layer(0, {x: 1, y: -1})])]});
  const out = composeNative(t, {body: {0: solid(2, 2, RED)}}, 0);
  // Centre (5, 3): pixels x 4..5, y 2..3.
  assert.deepEqual(pixel(out, 4, 2), RED);
  assert.deepEqual(pixel(out, 5, 3), RED);
  assert.deepEqual(pixel(out, 3, 2), [0, 0, 0, 0]);
  assert.deepEqual(pixel(out, 4, 4), [0, 0, 0, 0]);
});

test('the head attaches at the ACT anchor and draws over the body', () => {
  const t = template({
    body: [frame([layer(0)], [[0, -2]])],
    head: [frame([layer(0)], [[0, -1]])],
  });
  const out = composeNative(t, {body: {0: solid(2, 2, RED)}, head: {0: solid(2, 2, BLUE)}}, 0);
  // Body at y 3..4; head centre moved by (0, -1): y 2..3, so row 3 is shared and the head wins.
  assert.deepEqual(pixel(out, 3, 2), BLUE);
  assert.deepEqual(pixel(out, 3, 3), BLUE);
  assert.deepEqual(pixel(out, 3, 4), RED);
});

test('draw order is body, head, headgear, weapon, trail (single studied order; C9 open)', () => {
  const parts = {};
  const textures = {};
  const colors = {body: RED, head: BLUE, headgear: GREEN, weapon: WHITE, trail: [10, 20, 30, 255]};
  for (const name of Object.keys(colors)) {
    parts[name] = [frame([layer(0)])];
    textures[name] = {0: solid(2, 2, colors[name])};
  }
  const t = template(parts);
  assert.deepEqual(pixel(composeNative(t, textures, 0), 4, 4), colors.trail);
  assert.deepEqual(pixel(composeNative(t, textures, 0, {trail: false}), 4, 4), colors.weapon);
  assert.deepEqual(pixel(composeNative(t, textures, 0, {trail: false, weapon: false}), 4, 4), colors.headgear);
  assert.deepEqual(pixel(composeNative(t, textures, 0, {trail: false, weapon: false, headgear: false}), 4, 4), colors.head);
});

test('headgear attaches with the same anchor rule as the head', () => {
  const t = template({
    body: [frame([layer(0)], [[2, 0]])],
    headgear: [frame([layer(0)], [[0, 0]])],
  });
  const out = composeNative(t, {body: {0: solid(1, 1, RED)}, headgear: {0: solid(1, 1, GREEN)}}, 0);
  // A 1x1 drawing centred on (4, 4) covers pixel (3, 3); the anchor moves the headgear by (+2, 0).
  assert.deepEqual(pixel(out, 3, 3), RED);
  assert.deepEqual(pixel(out, 5, 3), GREEN);
});

test('mirror flips the drawing horizontally around its centre', () => {
  const t = template({body: [frame([layer(0, {mirror: true})])]});
  const plain = composeNative(template({body: [frame([layer(0)])]}), {body: {0: striped(RED, BLUE)}}, 0);
  const mirrored = composeNative(t, {body: {0: striped(RED, BLUE)}}, 0);
  assert.deepEqual([pixel(plain, 3, 3), pixel(plain, 4, 3)], [RED, BLUE]);
  assert.deepEqual([pixel(mirrored, 3, 3), pixel(mirrored, 4, 3)], [BLUE, RED]);
});

test('zero-scale layers are skipped and a missing texture is an error, not a silent gap', () => {
  const zero = template({body: [frame([layer(0, {scale: [0, 1]})])]});
  assert.equal(pixelDifference(composeNative(zero, {body: {0: solid(2, 2, RED)}}, 0), {width: 8, height: 8, data: new Uint8ClampedArray(256)}).pixels, 0);
  const missing = template({body: [frame([layer(5)])]});
  assert.throws(() => composeNative(missing, {body: {}}, 0), /Missing body SPR image 5/);
});

test('layer colour alpha blends over earlier parts', () => {
  const t = template({body: [frame([layer(0)])], head: [frame([layer(0, {color: [1, 1, 1, 0.5]})])]});
  const out = composeNative(t, {body: {0: solid(2, 2, RED)}, head: {0: solid(2, 2, BLUE)}}, 0);
  const [r, g, b, a] = pixel(out, 3, 3);
  assert.equal(a, 255);
  assert.ok(Math.abs(r - 127.5) <= 1 && g === 0 && Math.abs(b - 127.5) <= 1, `got ${[r, g, b, a]}`);
});

test('replacing one part texture changes only that part (module independence)', () => {
  const t = template({body: [frame([layer(0)], [[0, -3]])], head: [frame([layer(0)], [[0, 0]])]});
  const base = {body: {0: solid(2, 2, RED)}, head: {0: solid(2, 2, BLUE)}};
  const recoloured = {body: base.body, head: {0: solid(2, 2, GREEN)}};
  const a = composeNative(t, base, 0), b = composeNative(t, recoloured, 0);
  assert.deepEqual(pixel(b, 3, 3), RED);
  assert.deepEqual(pixel(a, 3, 0), BLUE);
  assert.deepEqual(pixel(b, 3, 0), GREEN);
  assert.equal(pixelDifference(a, b).pixels, 4);
});
