// Authored joint positions in sprite pixels. The character's feet remain at y = 0.
// This file contains no drawing, equipment choices, playback state, or hit effects.
export const DEFAULT_TIMING = Object.freeze({ windup: 220, strike: 90, recovery: 320 });

export const TIMING_LIMITS = Object.freeze({
  windup: Object.freeze([100, 600]),
  strike: Object.freeze([45, 240]),
  recovery: Object.freeze([120, 700]),
});

const rawPoses = [
  {
    id: 'ready', name: 'Ready', description: 'Balanced stance; the blade is held away from the body.',
    head: [0, -84], neck: [1, -65], hips: [0, -35],
    rearShoulder: [-9, -61], rearElbow: [-15, -47], rearWrist: [-9, -39],
    shoulder: [10, -62], elbow: [17, -47], wrist: [26, -55],
    rearKnee: [-9, -18], knee: [11, -17], rearAnkle: [-10, -2], ankle: [13, 0],
    swordAngle: -42, torsoVariant: 'ready', torsoAngle: 0,
  },
  {
    id: 'load', name: 'Load', description: 'The knees compress and the shoulders draw back under a raised sword.',
    head: [-4, -81], neck: [-3, -62], hips: [-3, -32],
    rearShoulder: [-12, -59], rearElbow: [-21, -47], rearWrist: [-13, -35],
    shoulder: [6, -61], elbow: [18, -73], wrist: [18, -90],
    rearKnee: [-12, -17], knee: [12, -15], rearAnkle: [-10, -2], ankle: [13, 0],
    swordAngle: -125, torsoVariant: 'coil', torsoAngle: -7,
  },
  {
    id: 'drive', name: 'Drive', description: 'The hips and chest lead; the raised blade is still catching up.',
    head: [3, -84], neck: [5, -65], hips: [2, -35],
    rearShoulder: [-6, -62], rearElbow: [-18, -52], rearWrist: [-25, -57],
    shoulder: [12, -63], elbow: [25, -72], wrist: [31, -86],
    rearKnee: [-8, -18], knee: [14, -18], rearAnkle: [-10, -2], ankle: [13, 0],
    swordAngle: -80, torsoVariant: 'coil', torsoAngle: 8,
  },
  {
    id: 'contact', name: 'Contact', description: 'The sword crosses the target as the free arm balances the forward drive.',
    head: [6, -82], neck: [7, -63], hips: [4, -33],
    rearShoulder: [-4, -61], rearElbow: [-18, -49], rearWrist: [-29, -54],
    shoulder: [14, -61], elbow: [28, -61], wrist: [29, -52],
    rearKnee: [-8, -17], knee: [16, -16], rearAnkle: [-10, -2], ankle: [13, 0],
    swordAngle: 15, torsoVariant: 'follow', torsoAngle: 13,
  },
  {
    id: 'follow', name: 'Follow-through', description: 'The blade finishes below the hit; bent knees absorb the stop.',
    head: [8, -78], neck: [8, -59], hips: [3, -30],
    rearShoulder: [-3, -58], rearElbow: [-17, -47], rearWrist: [-26, -51],
    shoulder: [14, -58], elbow: [29, -47], wrist: [24, -31],
    rearKnee: [-10, -16], knee: [16, -14], rearAnkle: [-10, -2], ankle: [13, 0],
    swordAngle: 48, torsoVariant: 'follow', torsoAngle: 17,
  },
  {
    id: 'recovery', name: 'Recover', description: 'The shoulders settle and the sword returns without a second strike.',
    head: [3, -82], neck: [4, -63], hips: [1, -33],
    rearShoulder: [-7, -60], rearElbow: [-17, -47], rearWrist: [-13, -39],
    shoulder: [11, -61], elbow: [25, -48], wrist: [25, -42],
    rearKnee: [-10, -17], knee: [13, -16], rearAnkle: [-10, -2], ankle: [13, 0],
    swordAngle: -8, torsoVariant: 'ready', torsoAngle: 5,
  },
];

export const JOINT_NAMES = Object.freeze([
  'head', 'neck', 'hips', 'rearShoulder', 'rearElbow', 'rearWrist',
  'shoulder', 'elbow', 'wrist', 'rearKnee', 'knee', 'rearAnkle', 'ankle',
]);

export const POSES = Object.freeze(rawPoses.map(pose => Object.freeze({
  ...pose,
  ...Object.fromEntries(JOINT_NAMES.map(key => [key, Object.freeze([...pose[key]])])),
})));

export function validateTiming(value = {}) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new TypeError('Timing must be an object containing numeric millisecond values.');
  }
  const result = {};
  for (const key of Object.keys(DEFAULT_TIMING)) {
    const number = value[key] === undefined ? DEFAULT_TIMING[key] : value[key];
    const [minimum, maximum] = TIMING_LIMITS[key];
    if (typeof number !== 'number' || !Number.isFinite(number) || number < minimum || number > maximum) {
      throw new RangeError(`${key} must be a finite number between ${minimum} and ${maximum} ms.`);
    }
    result[key] = number;
  }
  return result;
}

export function timeline(timing = DEFAULT_TIMING) {
  const values = validateTiming(timing);
  const windupStart = 80;
  const strikeStart = windupStart + values.windup;
  const contactTime = strikeStart + values.strike * 0.5;
  const followStart = strikeStart + values.strike;
  const recoveryStart = followStart + 100;
  const settledStart = recoveryStart + values.recovery;
  const duration = settledStart + 80;
  const bounds = [0, windupStart, strikeStart, followStart, recoveryStart, settledStart, duration];
  const labels = [
    ['ready', 'Ready'], ['windup', 'Windup'], ['strike', 'Strike'],
    ['hold', 'Follow-through'], ['recovery', 'Recovery'], ['settle', 'Settled'],
  ];
  return {
    timing: values, duration, contactTime, windupStart, strikeStart, followStart, recoveryStart, settledStart,
    // Times where interpolated playback reaches each exact authored drawing.
    poseTimes: [0, strikeStart, strikeStart + values.strike * 0.25, contactTime, followStart, recoveryStart + values.recovery * 0.45],
    phases: labels.map(([id, name], index) => ({
      id, name, start: bounds[index], end: bounds[index + 1], duration: bounds[index + 1] - bounds[index],
    })),
  };
}

const clamp = (value, low, high) => Math.min(high, Math.max(low, value));
const easeInOut = value => value * value * (3 - 2 * value);

function copyPose(pose) {
  return { ...pose, ...Object.fromEntries(JOINT_NAMES.map(key => [key, [...pose[key]]])) };
}

function blendPose(from, to, amount) {
  const result = copyPose(amount < 0.5 ? from : to);
  for (const key of JOINT_NAMES) {
    result[key] = from[key].map((value, axis) => value + (to[key][axis] - value) * amount);
  }
  // These authored angles trace one attack arc; shortest-path interpolation would
  // accidentally change the direction of a future pose that crosses 180 degrees.
  result.swordAngle = from.swordAngle + (to.swordAngle - from.swordAngle) * amount;
  result.torsoAngle = from.torsoAngle + (to.torsoAngle - from.torsoAngle) * amount;
  return result;
}

function interpolatedPose(time, track) {
  const [ready, load, drive, contact, follow, recovery] = POSES;
  if (time < track.windupStart) return copyPose(ready);
  if (time < track.strikeStart) {
    return blendPose(ready, load, easeInOut((time - track.windupStart) / track.timing.windup));
  }
  if (time < track.poseTimes[2]) return blendPose(load, drive, (time - track.strikeStart) / (track.timing.strike * 0.25));
  if (time < track.contactTime) return blendPose(drive, contact, (time - track.poseTimes[2]) / (track.timing.strike * 0.25));
  if (time < track.followStart) return blendPose(contact, follow, (time - track.contactTime) / (track.timing.strike * 0.5));
  if (time < track.recoveryStart) return copyPose(follow);
  if (time < track.poseTimes[5]) return blendPose(follow, recovery, easeInOut((time - track.recoveryStart) / (track.timing.recovery * 0.45)));
  if (time < track.settledStart) return blendPose(recovery, ready, easeInOut((time - track.poseTimes[5]) / (track.timing.recovery * 0.55)));
  return copyPose(ready);
}

/**
 * Pure sampling: never emits impacts. Use interpolate:true for movement between
 * authored poses; fps:24 holds that movement at a game-like drawing cadence.
 * Leave interpolation off to inspect the six unmodified authored silhouettes.
 */
export function samplePose(milliseconds, timing = DEFAULT_TIMING, mode = 'weighted', options = {}) {
  if (typeof milliseconds !== 'number' || !Number.isFinite(milliseconds)) throw new TypeError('Sample time must be finite milliseconds.');
  if (!['weighted', 'armOnly', 'arm-only'].includes(mode)) throw new RangeError('Motion mode must be weighted or armOnly.');
  const track = timeline(timing);
  const timeMs = clamp(milliseconds, 0, track.duration);
  let sampledTime = timeMs;
  if (options.fps !== undefined) {
    if (typeof options.fps !== 'number' || !Number.isFinite(options.fps) || options.fps <= 0 || options.fps > 240) {
      throw new RangeError('Sampling fps must be greater than 0 and at most 240.');
    }
    sampledTime = Math.floor(timeMs * options.fps / 1000) * 1000 / options.fps;
    // Frame cadence must not postpone completion or the exact hit/pose markers.
    if (timeMs === track.duration || track.poseTimes.includes(timeMs)) sampledTime = timeMs;
  }
  let poseIndex = 0;
  track.poseTimes.forEach((time, index) => { if (sampledTime >= time) poseIndex = index; });
  if (sampledTime >= track.settledStart) poseIndex = 0;
  const pose = options.interpolate ? interpolatedPose(sampledTime, track) : copyPose(POSES[poseIndex]);
  if (mode !== 'weighted') {
    // Preserve the exact hand/blade motion for an honest body-mechanics comparison.
    // The shoulder attachment is stationary, so the renderer must join it to the
    // sampled elbow instead of drawing disconnected whole-arm sprites.
    for (const key of JOINT_NAMES.filter(key => !['elbow', 'wrist'].includes(key))) pose[key] = [...POSES[0][key]];
    pose.torsoVariant = POSES[0].torsoVariant;
    pose.torsoAngle = POSES[0].torsoAngle;
  }
  return {
    ...pose, poseIndex, poseId: POSES[poseIndex].id,
    phase: track.phases.find(phase => timeMs >= phase.start && timeMs < phase.end)?.id ?? 'settle',
    timeMs, sampledTime,
  };
}

// Call only during forward playback. Replays reset previous time; scrubbing never
// invokes it. A large animation frame jump still detects the one contact marker.
export function crossedContact(previous, next, timing = DEFAULT_TIMING) {
  if (![previous, next].every(value => typeof value === 'number' && Number.isFinite(value))) {
    throw new TypeError('Contact bounds must be finite milliseconds.');
  }
  const { contactTime } = timeline(timing);
  return previous < contactTime && next >= contactTime;
}

/** Validate the small portable animation recipe; renderers may retain extra fields. */
export function validateImport(value) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new TypeError('Imported recipe must be an object.');
  if (value.version !== undefined && value.version !== 1) throw new RangeError('Unsupported animation recipe version.');
  if (!value.timing || typeof value.timing !== 'object') throw new TypeError('Imported recipe must include timing.');
  if (value.mode !== undefined && !['weighted', 'armOnly', 'arm-only'].includes(value.mode)) throw new RangeError('Invalid imported motion mode.');
  return { ...value, version: 1, timing: validateTiming(value.timing) };
}
