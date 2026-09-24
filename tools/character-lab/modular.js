const $ = (id) => document.getElementById(id);
const poseNames = ['Ready', 'Load', 'Drive', 'Contact', 'Follow-through', 'Recover'];
const phaseNames = {ready:'Ready', windup:'Wind-up', strike:'Strike', hold:'Follow-through', recovery:'Recovery', settle:'Settled'};
const poseDescriptions = [
  'Balanced stance, relaxed knees, sword ready. The same pose starts and ends the attack.',
  'Lower the weight and draw the shoulder back. The body prepares the sword to accelerate.',
  'The hips and shoulder lead; the sword follows. This is the transition from preparation to speed.',
  'The cutting edge reaches the target. The hand stays connected to the hilt throughout the swing.',
  'Let the sword carry through the cut, with the knees and torso absorbing the movement.',
  'Settle the body and return to the starting stance more slowly than the strike.'
];
const fieldsets = ['transport-controls', 'timeline-controls', 'workshop-controls', 'inspector-controls'].map($);
const attachmentFields = {weaponX:'weapon-x', weaponY:'weapon-y', weaponAngle:'weapon-angle', hatX:'hat-x', hatY:'hat-y'};
let workshop;
let currentState;
let selectedPose = 0;
let lastMessage = '';
let lastHitCount = 0;

function announce(message, error = false) {
  $('status').textContent = message;
  $('status').classList.toggle('error', error);
}

function setInput(id, value) {
  if (value !== undefined && value !== null && document.activeElement !== $(id)) $(id).value = String(value);
}

function readAttachment(config, index) {
  const entries = config?.attachments;
  if (Array.isArray(entries) || (entries && typeof entries === 'object')) return entries[index] || {};
  if (config?.attachment && (config.attachment.pose === undefined || config.attachment.pose === index)) return config.attachment;
  return {};
}

function renderState(state) {
  currentState = state;
  fieldsets.forEach((fieldset) => { fieldset.disabled = !state.ready; });
  const duration = Math.max(1, Number(state.duration) || 1);
  const time = Math.max(0, Math.min(duration, Number(state.time) || 0));
  $('timeline').max = String(duration);
  $('timeline').value = String(time);
  $('playhead').textContent = `${Math.round(time)} / ${Math.round(duration)} ms`;
  $('phase-name').textContent = phaseNames[state.phase] || state.phase || poseNames[selectedPose];
  $('pause-button').textContent = state.playing && !state.paused ? 'Pause' : 'Resume';
  $('pause-button').disabled = !state.ready;
  $('contact-indicator').classList.toggle('is-contact', Boolean(state.contact));
  const count = Math.max(0, Number(state.hitCount) || 0);
  $('hit-count').textContent = String(count);
  if (state.contact) $('contact-label').textContent = 'Contact registered';
  else if (state.message?.startsWith('Miss')) $('contact-label').textContent = 'Miss · no contact';
  else if (state.message?.startsWith('Pose preview')) $('contact-label').textContent = 'Pose preview · no damage';
  else if (state.config?.targetInRange === false) $('contact-label').textContent = 'Target out of reach';
  else $('contact-label').textContent = 'Waiting for contact';
  if (count > lastHitCount) announce(`Hit ${count} registered on the training dummy.`);
  lastHitCount = count;

  selectedPose = Math.max(0, Math.min(5, Number.isInteger(state.poseIndex) ? state.poseIndex : selectedPose));
  document.querySelectorAll('[data-pose]').forEach((button) => {
    const index = Number(button.dataset.pose);
    button.setAttribute('aria-pressed', String(index === selectedPose));
    if (Number.isFinite(state.poseTimes?.[index])) {
      const timeLabel = `${Math.round(state.poseTimes[index])} ms`;
      button.title = `${poseNames[index]} · ${timeLabel}`;
      button.setAttribute('aria-label', `${poseNames[index]}, ${timeLabel}`);
      let stamp = button.querySelector('.pose-time');
      if (!stamp) { stamp = document.createElement('small'); stamp.className = 'pose-time'; button.append(stamp); }
      stamp.textContent = timeLabel;
    }
  });
  $('pose-description').textContent = poseDescriptions[selectedPose];
  $('attachment-pose').textContent = `${String(selectedPose + 1).padStart(2, '0')} · ${poseNames[selectedPose]}`;

  const config = state.config || {};
  setInput('hat-select', config.hat);
  setInput('weapon-select', config.weapon);
  setInput('speed-select', config.speed ?? state.speed);
  if (typeof (config.loop ?? state.loop) === 'boolean') $('loop-toggle').checked = config.loop ?? state.loop;
  $('weighted-mode').setAttribute('aria-pressed', String(config.mode !== 'armOnly'));
  $('arm-mode').setAttribute('aria-pressed', String(config.mode === 'armOnly'));
  $('mode-description').textContent = config.mode === 'armOnly'
    ? 'Only the attacking arm moves through the cut. The timing and equipment match the full-body version.'
    : 'The hips and shoulders load, lead the cut, then settle. Compare using the same attack timing.';
  for (const name of ['windup', 'strike', 'recovery']) {
    const value = config.timing?.[name];
    if (Number.isFinite(value)) {
      setInput(`${name}-duration`, value);
      $(`${name}-value`).textContent = `${Math.round(value)} ms`;
    }
  }
  for (const key of ['anchors', 'trails', 'feedback']) if (typeof config[key] === 'boolean') $(`${key}-toggle`).checked = config[key];
  if (typeof config.targetInRange === 'boolean') setInput('target-select', config.targetInRange ? 'in' : 'out');
  document.querySelectorAll('[data-layer]').forEach((input) => {
    if (typeof config.visible?.[input.dataset.layer] === 'boolean') input.checked = config.visible[input.dataset.layer];
  });
  const attachment = readAttachment(config, selectedPose);
  for (const [key, id] of Object.entries(attachmentFields)) setInput(id, attachment[key] ?? 0);
  if (typeof state.message === 'string' && state.message && state.message !== lastMessage) {
    lastMessage = state.message;
    announce(state.message);
  }
}

function configure(patch) {
  invoke('configure', patch);
}

function invoke(method, ...args) {
  if (!workshop) return;
  try { return workshop[method](...args); }
  catch (error) { announce(error instanceof Error ? error.message : 'Could not apply this workshop action.', true); }
}

$('attack-button').addEventListener('click', () => invoke('attack'));
$('pause-button').addEventListener('click', () => invoke('togglePause'));
$('loop-toggle').addEventListener('change', (event) => invoke('setLoop', event.target.checked));
$('speed-select').addEventListener('change', (event) => invoke('setSpeed', Number(event.target.value)));
$('timeline').addEventListener('input', (event) => invoke('seek', Number(event.target.value)));
document.querySelectorAll('[data-pose]').forEach((button) => button.addEventListener('click', () => invoke('selectPose', Number(button.dataset.pose))));
for (const key of ['hat', 'weapon']) $(`${key}-select`).addEventListener('change', (event) => configure({[key]:event.target.value}));
$('weighted-mode').addEventListener('click', () => configure({mode:'weighted'}));
$('arm-mode').addEventListener('click', () => configure({mode:'armOnly'}));
for (const name of ['windup', 'strike', 'recovery']) {
  $(`${name}-duration`).addEventListener('input', (event) => {
    const value = Number(event.target.value);
    $(`${name}-value`).textContent = `${value} ms`;
    configure({timing:{[name]:value}});
  });
}
for (const key of ['anchors', 'trails', 'feedback']) $(`${key}-toggle`).addEventListener('change', (event) => configure({[key]:event.target.checked}));
$('target-select').addEventListener('change', (event) => configure({targetInRange:event.target.value === 'in'}));
document.querySelectorAll('[data-layer]').forEach((input) => input.addEventListener('change', () => configure({visible:{[input.dataset.layer]:input.checked}})));
for (const [key, id] of Object.entries(attachmentFields)) {
  $(id).addEventListener('focus', () => invoke('selectPose', selectedPose));
  $(id).addEventListener('input', (event) => {
    if (!event.target.validity.valid || event.target.value === '') return;
    configure({attachment:{pose:selectedPose, [key]:Number(event.target.value)}});
  });
}
$('reset-attachment').addEventListener('click', () => configure({attachment:{pose:selectedPose, weaponX:0, weaponY:0, weaponAngle:0, hatX:0, hatY:0}}));
$('reset-button').addEventListener('click', () => {
  invoke('reset');
  $('import-status').textContent = '';
  announce('Workshop reset. Effects are off; the full-body swing is ready.');
});

$('export-button').addEventListener('click', () => {
  if (!workshop) return;
  try {
    const data = workshop.exportData();
    const blob = new Blob([JSON.stringify(data, null, 2) + '\n'], {type:'application/json'});
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = 'wayfarer-attack-settings.json';
    document.body.append(anchor);
    anchor.click();
    anchor.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    $('import-status').classList.remove('error');
    $('import-status').textContent = 'Settings exported. The original artwork and video stay in the workshop.';
  } catch (error) {
    $('import-status').classList.add('error');
    $('import-status').textContent = error instanceof Error ? error.message : 'Could not export these settings.';
  }
});
$('import-button').addEventListener('click', () => $('import-file').click());
$('import-file').addEventListener('change', async (event) => {
  const file = event.target.files?.[0];
  if (!file || !workshop) return;
  try {
    if (file.size > 1024 * 1024) throw new Error('Choose a settings JSON file smaller than 1 MB.');
    const data = JSON.parse(await file.text());
    if (!data || typeof data !== 'object' || Array.isArray(data)) throw new Error('This file must contain a workshop settings object.');
    await workshop.importData(data);
    $('import-status').classList.remove('error');
    $('import-status').textContent = `Loaded ${file.name}.`;
    announce('Imported equipment, timing and pose alignment settings.');
  } catch (error) {
    $('import-status').classList.add('error');
    $('import-status').textContent = error instanceof Error ? error.message : 'Could not import this file.';
  } finally { event.target.value = ''; }
});

let referenceLoading = false;
let referenceUrl;
$('video-reference').addEventListener('toggle', async () => {
  const video = $('previous-video');
  if ($('video-reference').open && !video.getAttribute('src') && !referenceLoading) {
    referenceLoading = true;
    $('reference-status').textContent = 'Loading the original video…';
    try {
      const response = await fetch('assets/video-tests/grok-wayfarer-attack-v3/raw.mp4');
      if (!response.ok) throw new Error(`Video request returned ${response.status}.`);
      referenceUrl = URL.createObjectURL(await response.blob());
      video.src = referenceUrl;
      video.load();
      $('reference-status').textContent = 'Original V3 ready. Use the video controls to compare.';
    } catch (error) {
      $('reference-status').textContent = error instanceof Error ? error.message : 'Could not load the previous video.';
    } finally { referenceLoading = false; }
  } else if (!$('video-reference').open) video.pause();
});
window.addEventListener('pagehide', () => { if (referenceUrl) URL.revokeObjectURL(referenceUrl); });

try {
  const [{createWorkshop}, {TIMING_LIMITS}] = await Promise.all([import('./modular-engine.js'), import('./modular-motion.mjs')]);
  for (const [name, [minimum, maximum]] of Object.entries(TIMING_LIMITS)) {
    $(`${name}-duration`).min = String(minimum);
    $(`${name}-duration`).max = String(maximum);
  }
  workshop = await createWorkshop($('workshop-canvas'), {onUpdate:renderState});
  if (!currentState?.ready) announce('The workshop is preparing its artwork…');
  else announce('Ready. Try one swing, then compare “Arm only” or change the equipment.');
} catch (error) {
  fieldsets.forEach((fieldset) => { fieldset.disabled = true; });
  announce(`The workshop could not start: ${error instanceof Error ? error.message : 'unknown error'}`, true);
}
