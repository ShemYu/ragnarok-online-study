import test from 'node:test';
import assert from 'node:assert/strict';
import { validateProject, segmentDistance } from '../modular-engine.js';
import { DEFAULT_TIMING, POSES, timeline, samplePose, crossedContact } from '../modular-motion.mjs';

function exportedProject() {
  return {
    type: 'wayfarer-modular-attack', version: 1,
    config: {
      hat: 'cap', weapon: 'falchion', mode: 'weighted', anchors: true,
      trails: false, feedback: true, targetInRange: true,
      visible: { body: true, head: true, hat: false, weapon: true },
      timing: { windup: 240.5, strike: 80, recovery: 350 },
      attachments: POSES.map((_, index) => ({
        weaponX: index - 2, weaponY: index * 0.5, weaponAngle: index * 2,
        hatX: index === 0 ? 0 : -index, hatY: index / 3,
      })),
    },
    poseIds: POSES.map(pose => pose.id),
    source: 'Original parts atlas + authored joints. One direction. No video frames.',
  };
}

test('exported character settings survive JSON import without losing offsets or fractions', () => {
  const project = exportedProject();
  const parsed = JSON.parse(JSON.stringify(project));
  const validated = validateProject(parsed);
  assert.deepEqual(validated, project.config);
  validated.attachments[3].weaponAngle = 70;
  validated.visible.hat = true;
  validated.timing.windup = 500;
  assert.equal(parsed.config.attachments[3].weaponAngle, 6);
  assert.equal(parsed.config.visible.hat, false);
  assert.equal(parsed.config.timing.windup, 240.5);
});

test('project import rejects wrong schemas, invalid equipment, and missing switches', () => {
  for (const value of [null, {}, [], { type: 'wayfarer-modular-attack', version: 2 }, { ...exportedProject(), config: [] }]) {
    assert.throws(() => validateProject(value));
  }
  for (const [key, invalid] of [['hat', 'helmet'], ['weapon', 'spear'], ['mode', 'automatic'], ['feedback', 1], ['targetInRange', 'false']]) {
    const project = exportedProject();
    project.config[key] = invalid;
    assert.throws(() => validateProject(project), key);
  }
  const missingSwitch = exportedProject();
  delete missingSwitch.config.anchors;
  assert.throws(() => validateProject(missingSwitch));
  const missingLayer = exportedProject();
  delete missingLayer.config.visible.weapon;
  assert.throws(() => validateProject(missingLayer));
});

test('project import requires the entire authored timing instead of silently restoring defaults', () => {
  const noTiming = exportedProject();
  delete noTiming.config.timing;
  assert.throws(() => validateProject(noTiming));
  for (const key of Object.keys(DEFAULT_TIMING)) {
    const project = exportedProject();
    delete project.config.timing[key];
    assert.throws(() => validateProject(project), `missing ${key}`);
  }
});

test('project import rejects damaged attachment records and nonnumeric timing', () => {
  for (const invalid of [[], null, [...exportedProject().config.attachments, {}]]) {
    const project = exportedProject();
    project.config.attachments = invalid;
    assert.throws(() => validateProject(project));
  }
  for (const invalid of [null, {}, { weaponX: 0, weaponY: 0, weaponAngle: 91, hatX: 0, hatY: 0 }]) {
    const project = exportedProject();
    project.config.attachments[2] = invalid;
    assert.throws(() => validateProject(project));
  }
  for (const invalid of ['220', null, NaN, Infinity, -100, 100000]) {
    const project = exportedProject();
    project.config.timing.windup = invalid;
    assert.throws(() => validateProject(project));
  }
  const hugeOffset = exportedProject();
  hugeOffset.config.attachments[3].hatX = 31;
  assert.throws(() => validateProject(hugeOffset));
});

test('segment distance clamps to blade endpoints and handles a zero-length segment', () => {
  assert.equal(segmentDistance([5, 3], [0, 0], [10, 0]), 3);
  assert.equal(segmentDistance([-3, 4], [0, 0], [10, 0]), 5);
  assert.equal(segmentDistance([13, 4], [0, 0], [10, 0]), 5);
  assert.equal(segmentDistance([3, 4], [0, 0], [0, 0]), 5);
  assert.equal(segmentDistance([6, 8], [0, 0], [9, 12]), 0);
});

test('the authored contact reaches the actual dummy while the distant dummy remains clear', () => {
  for (const timing of [DEFAULT_TIMING, { windup: 600, strike: 45, recovery: 700 }]) {
    const track = timeline(timing);
    for (const mode of ['weighted', 'armOnly']) {
      const pose = samplePose(track.contactTime, timing, mode, { interpolate: true });
      const angle = pose.swordAngle * Math.PI / 180;
      // These are the actual workshop blade geometry and dummy coordinates.
      const pointOnBlade = reach => [pose.wrist[0] + Math.cos(angle) * reach, pose.wrist[1] + Math.sin(angle) * reach];
      const base = pointOnBlade(8), tip = pointOnBlade(43);
      assert.ok(segmentDistance([58, -43], base, tip) <= 13, `${mode} must hit the near dummy`);
      assert.ok(segmentDistance([105, -43], base, tip) > 13, `${mode} must miss the distant dummy`);
      assert.equal(crossedContact(track.contactTime - 50, track.contactTime + 50, timing), true);
      assert.equal(crossedContact(track.contactTime, track.contactTime + 50, timing), false);
      assert.equal(crossedContact(track.contactTime + 50, track.contactTime - 50, timing), false);
    }
  }
});
