import test from 'node:test';
import assert from 'node:assert/strict';
import { DEFAULT_TIMING, POSES, timeline, samplePose, crossedContact, validateTiming, validateImport } from '../modular-motion.mjs';

test('authored poses are reached exactly and recovery returns to the initial stance', () => {
  const track = timeline();
  track.poseTimes.forEach((time, index) => {
    const pose = samplePose(time, DEFAULT_TIMING, 'weighted', { interpolate: true });
    for (const key of ['head', 'hips', 'shoulder', 'elbow', 'wrist', 'swordAngle']) assert.deepEqual(pose[key], POSES[index][key]);
  });
  const end = samplePose(track.duration, DEFAULT_TIMING, 'weighted', { interpolate: true, fps: 24 });
  assert.deepEqual(end.wrist, POSES[0].wrist);
  assert.deepEqual(end.head, POSES[0].head);
  assert.equal(end.swordAngle, POSES[0].swordAngle);
});

test('body comparison preserves the same weapon motion while feet stay planted', () => {
  const track = timeline();
  let bodyMoved = false;
  for (let time = 0; time <= track.duration; time += 7) {
    const body = samplePose(time, DEFAULT_TIMING, 'weighted', { interpolate: true });
    const arm = samplePose(time, DEFAULT_TIMING, 'armOnly', { interpolate: true });
    assert.deepEqual(body.wrist, arm.wrist);
    assert.equal(body.swordAngle, arm.swordAngle);
    assert.deepEqual(arm.head, POSES[0].head);
    assert.deepEqual(arm.hips, POSES[0].hips);
    for (const key of ['ankle', 'rearAnkle']) assert.deepEqual(body[key], POSES[0][key]);
    bodyMoved ||= body.hips[0] !== POSES[0].hips[0];
  }
  assert.equal(bodyMoved, true);
});

test('contact is a single crossing at low and high playback frame rates', () => {
  const track = timeline();
  for (const step of [1000 / 120, 1000 / 24, 1000 / 10, 500, 1000]) {
    let hits = 0;
    for (let previous = 0; previous < track.duration; previous += step) {
      hits += Number(crossedContact(previous, Math.min(previous + step, track.duration)));
    }
    assert.equal(hits, 1, `step=${step}`);
  }
  assert.equal(crossedContact(track.contactTime, track.contactTime + 10), false);
  assert.equal(crossedContact(track.contactTime + 10, 0), false);
  assert.equal(crossedContact(0, track.contactTime), true);
});

test('timing controls move the actual contact marker and retain a complete recovery', () => {
  const slow = { windup: 400, strike: 160, recovery: 600 };
  const track = timeline(slow);
  assert.equal(track.contactTime, 560);
  assert.equal(track.duration, 1420);
  assert.equal(crossedContact(344, 346, slow), false);
  assert.equal(crossedContact(559, 561, slow), true);
  const pose = samplePose(track.contactTime, slow, 'weighted', { interpolate: true, fps: 24 });
  assert.deepEqual(pose.wrist, POSES[3].wrist);
  assert.equal(pose.swordAngle, 15);
  // The rendered blade passes through the fixed dummy at (50, -44), radius 12.
  const radians = pose.swordAngle * Math.PI / 180;
  const handToTarget = [50 - pose.wrist[0], -44 - pose.wrist[1]];
  const alongBlade = handToTarget[0] * Math.cos(radians) + handToTarget[1] * Math.sin(radians);
  const acrossBlade = Math.abs(handToTarget[0] * Math.sin(radians) - handToTarget[1] * Math.cos(radians));
  assert.ok(alongBlade > 0 && alongBlade < 42);
  assert.ok(acrossBlade < 12);
});

test('import round trips exact numeric timings and rejects malformed input', () => {
  const original = { version: 1, timing: { windup: 240.5, strike: 80, recovery: 350 }, mode: 'weighted', equipment: { weapon: 'iron' } };
  assert.deepEqual(validateImport(JSON.parse(JSON.stringify(original))), original);
  for (const invalid of [null, [], '220', NaN, Infinity, -1, 0, 10000]) {
    assert.throws(() => validateTiming({ windup: invalid }));
  }
  assert.throws(() => validateImport({ version: 2, timing: DEFAULT_TIMING }));
  assert.throws(() => validateImport({ version: 1 }));
  assert.throws(() => validateImport({ timing: DEFAULT_TIMING, mode: 'unknown' }));
});

test('sampling is independent and callers cannot mutate the source poses', () => {
  const first = samplePose(345);
  first.wrist[0] = 999;
  assert.notEqual(samplePose(345).wrist[0], 999);
  assert.notEqual(POSES[3].wrist[0], 999);
  assert.throws(() => samplePose(NaN));
  assert.throws(() => samplePose(10, DEFAULT_TIMING, 'weighted', { fps: 0 }));
});
