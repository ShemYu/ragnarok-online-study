import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createWorkshop } from '../modular-engine.js';

// Exercise the real workshop state machine without a browser or wall-clock waits.
// Canvas methods are no-ops: these assertions verify lifecycle behavior, not art.
test('workshop playback lifecycle', async t => {
  const names = ['performance', 'requestAnimationFrame', 'cancelAnimationFrame', 'window', 'document', 'Image', 'fetch'];
  const descriptors = new Map(names.map(name => [name, Object.getOwnPropertyDescriptor(globalThis, name)]));
  const install = (name, value) => Object.defineProperty(globalThis, name, { configurable: true, writable: true, value });
  let now = 0, nextID = 0, app;
  const pending = new Map();
  t.after(() => {
    try { app?.dispose(); }
    finally {
      pending.clear();
      for (const [name, descriptor] of descriptors) {
        if (descriptor) Object.defineProperty(globalThis, name, descriptor);
        else delete globalThis[name];
      }
    }
  });

  install('performance', { now: () => now });
  install('requestAnimationFrame', callback => { pending.set(++nextID, callback); return nextID; });
  install('cancelAnimationFrame', id => pending.delete(id));
  install('window', {});
  const makeContext = () => new Proxy({
    getImageData(_x, _y, width, height) { return { data: new Uint8ClampedArray(width * height * 4).fill(255) }; },
    createLinearGradient() { return { addColorStop() {} }; },
  }, { get(target, key) { return key in target ? target[key] : () => {}; } });
  const makeCanvas = () => ({ width: 960, height: 500, getContext: makeContext });
  install('document', { createElement: makeCanvas });
  install('Image', class { async decode() {} });
  const manifest = JSON.parse(readFileSync(new URL('../assets/modular-v1/atlas.json', import.meta.url), 'utf8'));
  install('fetch', async () => ({ ok: true, json: async () => manifest }));
  app = await createWorkshop(makeCanvas());

  function tick(milliseconds = 16) {
    now += milliseconds;
    const callbacks = [...pending.values()];
    pending.clear();
    for (const callback of callbacks) callback(now);
  }
  function advance(milliseconds) {
    const end = now + milliseconds;
    while (now < end) tick(Math.min(16, end - now));
  }

  await t.test('pause and seek never duplicate contact; resumed playback crosses it once', () => {
    app.attack();
    advance(352);
    assert.equal(app.getState().hitCount, 1);
    app.togglePause();
    const pausedTime = app.getState().time;
    advance(500);
    assert.equal(app.getState().time, pausedTime);
    assert.equal(app.getState().hitCount, 1);
    app.togglePause();
    advance(800);
    assert.equal(app.getState().playing, false);
    assert.equal(app.getState().hitCount, 1);

    app.seek(340);
    advance(100);
    assert.equal(app.getState().hitCount, 1);
    app.togglePause();
    advance(100);
    assert.equal(app.getState().hitCount, 2);
    app.seek(400);
    app.togglePause();
    advance(600);
    assert.equal(app.getState().hitCount, 2);
  });

  await t.test('impact feedback holds the contact pose without repeating damage', () => {
    app.reset();
    app.configure({ feedback: true });
    app.attack();
    advance(352);
    assert.equal(app.getState().hitCount, 1);
    assert.equal(app.getState().time, 345);
    advance(48);
    assert.equal(app.getState().time, 345);
    advance(650);
    assert.equal(app.getState().hitCount, 1);
    assert.equal(app.getState().playing, false);
  });

  await t.test('three completed loops produce three hits', () => {
    app.reset();
    app.setLoop(true);
    app.attack();
    advance(4000);
    assert.equal(app.getState().hitCount, 3);
    assert.equal(app.getState().playing, true);
  });

  await t.test('distant targets and hidden weapons cause misses', () => {
    app.reset();
    app.configure({ targetInRange: false });
    app.attack();
    advance(1000);
    assert.equal(app.getState().hitCount, 0);
    assert.equal(app.getState().contact, false);
    app.reset();
    app.configure({ visible: { weapon: false } });
    app.attack();
    advance(1000);
    assert.equal(app.getState().hitCount, 0);
  });

  await t.test('replay re-arms contact and disposal cancels the remaining animation frame', () => {
    app.reset();
    app.attack();
    advance(1000);
    app.togglePause();
    advance(1000);
    assert.equal(app.getState().hitCount, 2);
    app.dispose();
    assert.equal(pending.size, 0);
  });
});
