'use strict';

const experiments = {
  v1: { root: 'assets/video-tests/grok-wayfarer-attack-v1/', title: 'V1 · Style rejected', note: 'You rejected this version’s RO style match. It is preserved as a comparison with the revised starting art.', referenceTitle: 'V1 starting art', reviewLabel: 'RO style rejected', readyNote: 'Its RO style match was rejected.' },
  v2: { root: 'assets/video-tests/grok-wayfarer-attack-v2/', title: 'V2 · Motion rejected', note: 'The artwork improved, but the attack motion was rejected. Compare it with the next motion-focused experiment.', referenceTitle: 'V2 starting art', reviewLabel: 'Motion rejected', readyNote: 'The artwork improved, but the attack motion was rejected.' },
  v3: { root: 'assets/video-tests/grok-wayfarer-attack-v3/', title: 'V3 · Compact downward attack', note: 'Same V2 character art; a shorter prompt focuses on target direction, sword grip and attack poses.', referenceTitle: 'V3 starting art · unchanged from V2', reviewLabel: 'Visual review pending', readyNote: 'Review the target direction, sword grip and recovery before judging the motion.' }
};
const experimentPriority = ['v3', 'v2', 'v1'];
const nativeRoot = 'assets/video-tests/ro-study-v2/';
const video = document.getElementById('attack-video');
const nativeCanvas = document.getElementById('ro-animation');
const nativeContext = nativeCanvas.getContext('2d');
const nativePlayButton = document.getElementById('ro-play-button');
const nativeReplayButton = document.getElementById('ro-replay-button');
const experimentSelect = document.getElementById('experiment-select');
const playButton = document.getElementById('play-button');
const restartButton = document.getElementById('restart-button');
const previousFrame = document.getElementById('previous-frame');
const nextFrame = document.getElementById('next-frame');
const loopToggle = document.getElementById('loop-toggle');
const speedSelect = document.getElementById('speed-select');
const status = document.getElementById('status');
const playhead = document.getElementById('playhead');
const frameNote = document.getElementById('frame-note');
const downloadLink = document.getElementById('download-video');
let sourceFps = null;
let sourceFrameCount = null;
let manifestState = 'unknown';
let loadVersion = 0;
let sourceObjectUrl = null;
let sourceFetchController = null;
let nativeImages = [];
let nativeFrameDuration = 96;
let nativeElapsed = 0;
let nativePlaying = false;
let nativeStartedAt = 0;
let nativeStartedElapsed = 0;
let nativeAnimationRequest = null;
let nativeFetchController = null;
let nativeLoadVersion = 0;
let userSelectedExperiment = false;

function setStatus(message, error = false) {
  status.textContent = message;
  status.classList.toggle('error', error);
}

function hasDuration() {
  return Number.isFinite(video.duration) && video.duration > 0;
}

function updateControls() {
  const ready = hasDuration() && !video.error;
  playButton.disabled = !ready;
  restartButton.disabled = !ready;
  previousFrame.disabled = !ready || !sourceFps;
  nextFrame.disabled = !ready || !sourceFps;
  playButton.textContent = video.paused ? 'Play' : 'Pause';
  downloadLink.classList.toggle('disabled', !ready);
  downloadLink.setAttribute('aria-disabled', String(!ready));
  downloadLink.tabIndex = ready ? 0 : -1;
  const duration = hasDuration() ? `${video.duration.toFixed(3)} s` : '—';
  const frame = sourceFps && hasDuration() ? ` · frame ${Math.min(Math.floor(video.currentTime * sourceFps + 0.001), maxFrame()) + 1}` : '';
  playhead.textContent = `${video.currentTime.toFixed(3)} s / ${duration}${frame}`;
  frameNote.textContent = sourceFps ? `Frame step: 1 / ${sourceFps.toFixed(3).replace(/\.?0+$/, '')} second. Playback pauses when stepping.` : 'Frame stepping needs source FPS metadata.';
}

function maxFrame() {
  if (Number.isInteger(sourceFrameCount) && sourceFrameCount > 0) return sourceFrameCount - 1;
  return Math.max(0, Math.ceil(video.duration * sourceFps - 0.001) - 1);
}

function stepFrame(delta) {
  if (!sourceFps || !hasDuration() || video.error) return;
  video.pause();
  const currentFrame = Math.floor(video.currentTime * sourceFps + 0.001);
  const targetFrame = Math.min(maxFrame(), Math.max(0, currentFrame + delta));
  video.currentTime = targetFrame / sourceFps;
  updateControls();
}

async function readJson(root, filename, signal) {
  const response = await fetch(root + filename, { cache: 'no-store', signal });
  if (!response.ok) throw new Error(`${filename} is not available (${response.status}).`);
  return response.json();
}

async function exists(url, signal) {
  try {
    const response = await fetch(url, { method: 'HEAD', cache: 'no-store', signal });
    return response.ok;
  } catch (_) { return false; }
}

function appendMetadata(label, value) {
  if (value === undefined || value === null || value === '') return;
  const term = document.createElement('dt');
  const definition = document.createElement('dd');
  term.textContent = label;
  definition.textContent = String(value);
  document.getElementById('provenance').append(term, definition);
}

function showReference(root, filename, version) {
  const link = document.getElementById('character-reference-link');
  const image = document.getElementById('character-reference');
  const pending = document.getElementById('character-reference-pending');
  link.hidden = true;
  pending.hidden = false;
  image.onload = () => {
    if (version !== loadVersion) return;
    link.hidden = false;
    pending.hidden = true;
    video.poster = root + filename;
  };
  image.onerror = () => {
    if (version !== loadVersion) return;
    link.hidden = true;
    pending.hidden = false;
    video.removeAttribute('poster');
  };
  link.href = root + filename;
  image.src = root + filename;
}

function showManifest(manifest, root) {
  manifestState = manifest.state || manifest.status || 'unknown';
  const experiment = experiments[experimentSelect.value];
  const stateLabels = { running: 'Generation running', generated: 'Generated · pending visual review', needs_review: 'Pending visual review', failed: 'Generation failed', error: 'Generation error' };
  document.getElementById('generation-state').textContent = ['generated', 'needs_review'].includes(manifestState) ? `Generated · ${experiment.reviewLabel.toLowerCase()}` : stateLabels[manifestState] || `Request state: ${manifestState}`;
  const prompt = manifest.tool_arguments?.prompt || manifest.prompt || manifest.request?.prompt;
  document.getElementById('generation-prompt').textContent = typeof prompt === 'string' ? prompt : 'No prompt was found in the local manifest.';
  document.getElementById('provenance').replaceChildren();
  appendMetadata('Tool', manifest.tool || 'Grok CLI');
  appendMetadata('CLI version', manifest.cli_version);
  appendMetadata('Facing', manifest.direction_label);
  appendMetadata('Requested duration', manifest.tool_arguments?.duration ? `${manifest.tool_arguments.duration} seconds` : null);
  appendMetadata('Source first frame', 'Original character starting art shown above');
  appendMetadata('Source last frame', manifest.tool_arguments?.first_frame === manifest.tool_arguments?.last_frame ? 'Same original character starting art' : manifest.tool_arguments?.last_frame ? 'Recorded separately in the request manifest' : null);
  const styleFiles = Object.keys(manifest.input_hashes || {}).filter(name => /^style-reference-[\w.-]+\.(png|jpe?g|webp)$/i.test(name));
  appendMetadata('Style references', `${styleFiles.length} supplied images; expanded study sources are linked separately`);
  document.getElementById('style-reference-note').textContent = styleFiles.length ? 'The exact style images supplied with the selected video.' : 'No separate style images were supplied. This generation uses the starting character image and written motion prompt.';
  const grid = document.getElementById('style-references');
  grid.replaceChildren();
  for (const [index, filename] of styleFiles.entries()) {
    const link = document.createElement('a');
    link.href = root + filename;
    link.target = '_blank';
    link.rel = 'noopener';
    const image = document.createElement('img');
    image.src = root + filename;
    image.alt = `Style reference ${index + 1} supplied to this generation`;
    image.loading = 'lazy';
    link.append(image);
    grid.append(link);
  }
  appendMetadata('Source video', 'raw.mp4 · original generation output');
  appendMetadata('Reproducibility', manifest.reproducibility);
  if (manifest.collection_audit?.verbatimArgumentsMatched === false) {
    appendMetadata('Request audit', 'Grok omitted one final prompt newline. Wording, other arguments and image hashes matched; both request records are preserved.');
  }
}

async function loadResult() {
  const version = ++loadVersion;
  sourceFetchController?.abort();
  const controller = new AbortController();
  sourceFetchController = controller;
  video.pause();
  video.removeAttribute('src');
  video.removeAttribute('poster');
  video.load();
  if (sourceObjectUrl) URL.revokeObjectURL(sourceObjectUrl);
  sourceObjectUrl = null;
  sourceFps = null;
  sourceFrameCount = null;
  manifestState = 'unknown';
  setStatus('Reading local generation records…');
  document.getElementById('reload-button').disabled = true;
  document.getElementById('result-review').hidden = true;
  document.getElementById('style-references').replaceChildren();
  document.getElementById('style-reference-note').textContent = 'Reading the style references recorded for this generation…';
  updateControls();
  if (!userSelectedExperiment) {
    const available = await Promise.all(experimentPriority.map(key => exists(experiments[key].root + 'raw.mp4', controller.signal)));
    if (version !== loadVersion || controller.signal.aborted) return;
    experimentSelect.value = experimentPriority.find((_, index) => available[index]) || 'v1';
  }
  const experiment = experiments[experimentSelect.value];
  const root = experiment.root;
  document.getElementById('video-title').textContent = experiment.title;
  document.getElementById('review-badge').textContent = `${experimentSelect.value.toUpperCase()} · ${experiment.reviewLabel}`;
  document.getElementById('experiment-note').textContent = experiment.note;
  document.getElementById('motion-target').hidden = experimentSelect.value !== 'v3';
  document.getElementById('character-reference-title').textContent = experiment.referenceTitle;
  document.getElementById('character-reference-note').textContent = 'The character image supplied to this generation. Compare its proportions and shading against the original RO sprites.';
  document.getElementById('manifest-link').href = root + 'manifest.json';
  document.getElementById('media-link').href = root + 'media.json';
  downloadLink.href = root + 'raw.mp4';
  downloadLink.download = `grok-wayfarer-attack-${experimentSelect.value}-raw.mp4`;
  showReference(root, 'reference.png', version);
  const records = await Promise.allSettled([readJson(root, 'manifest.json', controller.signal), readJson(root, 'media.json', controller.signal), readJson(root, 'review-notes.json', controller.signal)]);
  if (version !== loadVersion || controller.signal.aborted) return;
  if (records[0].status === 'fulfilled') showManifest(records[0].value, root);
  else {
    document.getElementById('generation-state').textContent = 'Request record unavailable';
    document.getElementById('generation-prompt').textContent = 'The request manifest is not available yet. Use Reload result to check again.';
    document.getElementById('provenance').replaceChildren();
    document.getElementById('style-reference-note').textContent = 'The generation reference record is not available yet.';
  }
  const media = records[1].status === 'fulfilled' ? records[1].value : null;
  if (media && typeof media.fps === 'number' && Number.isFinite(media.fps) && media.fps > 0) sourceFps = media.fps;
  if (media && Number.isInteger(media.frameCount) && media.frameCount > 0) sourceFrameCount = media.frameCount;
  const summary = [];
  if (media?.width && media?.height) summary.push(`${media.width} × ${media.height}`);
  if (sourceFps) summary.push(`${Number(sourceFps.toFixed(3))} fps`);
  if (media?.duration) summary.push(`${Number(Number(media.duration).toFixed(3))} seconds`);
  document.getElementById('media-summary').textContent = summary.join(' · ') || 'Original MP4 · metadata pending';
  if (media?.sha256) appendMetadata('Video SHA-256', media.sha256);
  const review = records[2].status === 'fulfilled' ? records[2].value : null;
  document.getElementById('result-review').hidden = !review;
  document.getElementById('review-summary').textContent = typeof review?.summary === 'string' ? review.summary : '';
  const observations = document.getElementById('review-observations');
  observations.replaceChildren();
  for (const observation of Array.isArray(review?.observations) ? review.observations : []) {
    if (typeof observation !== 'string') continue;
    const item = document.createElement('li');
    item.textContent = observation;
    observations.append(item);
  }
  setStatus(manifestState === 'running' ? 'Generation is running. Checking for the source clip…' : 'Loading the original source video…');
  try {
    const response = await fetch(root + 'raw.mp4', { cache: 'no-store', signal: controller.signal });
    if (!response.ok) throw new Error(`Source video is not available (${response.status}).`);
    const sourceBlob = await response.blob();
    if (version !== loadVersion || controller.signal.aborted) return;
    // A full local blob permits frame seeking when the static server lacks Range support.
    sourceObjectUrl = URL.createObjectURL(sourceBlob);
    video.src = sourceObjectUrl;
    video.load();
    video.playbackRate = Number(speedSelect.value);
    video.loop = loopToggle.checked;
  } catch (error) {
    if (version !== loadVersion || error.name === 'AbortError') return;
    setStatus(`${experimentSelect.value.toUpperCase()} is not available or could not be loaded. Select another experiment, use Reload result, or inspect the request record below.`, true);
  } finally {
    if (version === loadVersion) {
      sourceFetchController = null;
      document.getElementById('reload-button').disabled = false;
      updateControls();
    }
  }
}

function nativeDuration() {
  return nativeImages.length * nativeFrameDuration;
}

function drawNativeFrame() {
  if (!nativeImages.length) return;
  const index = Math.max(0, Math.min(nativeImages.length - 1, Math.floor(nativeElapsed / nativeFrameDuration)));
  nativeContext.imageSmoothingEnabled = false;
  nativeContext.fillStyle = '#e8e6df';
  nativeContext.fillRect(0, 0, nativeCanvas.width, nativeCanvas.height);
  // Every original 3x image has the same fixed canvas and registration. Never recenter poses.
  nativeContext.drawImage(nativeImages[index], 0, 0);
  nativeCanvas.dataset.frame = String(index + 1);
  nativeCanvas.dataset.playing = String(nativePlaying);
  nativeCanvas.setAttribute('aria-label', `Original RO attack, native pose ${index + 1} of ${nativeImages.length}`);
  const ended = nativeElapsed >= nativeDuration();
  document.getElementById('ro-playhead').textContent = `Pose ${index + 1} / ${nativeImages.length} · ${(nativeElapsed / 1000).toFixed(3)} / ${(nativeDuration() / 1000).toFixed(3)} s${ended ? ' · End' : ''}`;
  nativePlayButton.textContent = nativePlaying ? 'Pause RO' : 'Play RO';
  nativePlayButton.disabled = ended;
  nativeReplayButton.disabled = false;
}

function tickNativeFrame(timestamp) {
  if (!nativePlaying) return;
  // A frame timestamp can precede the click's performance.now() within the same refresh.
  nativeElapsed = Math.max(0, Math.min(nativeDuration(), nativeStartedElapsed + timestamp - nativeStartedAt));
  if (nativeElapsed >= nativeDuration()) {
    nativePlaying = false;
    nativeAnimationRequest = null;
    drawNativeFrame();
    return;
  }
  drawNativeFrame();
  nativeAnimationRequest = requestAnimationFrame(tickNativeFrame);
}

function pauseNativeReference() {
  if (nativePlaying) nativeElapsed = Math.min(nativeDuration(), nativeStartedElapsed + performance.now() - nativeStartedAt);
  nativePlaying = false;
  if (nativeAnimationRequest !== null) cancelAnimationFrame(nativeAnimationRequest);
  nativeAnimationRequest = null;
  drawNativeFrame();
}

function playNativeReference() {
  if (!nativeImages.length || nativeElapsed >= nativeDuration() || nativePlaying) return;
  nativePlaying = true;
  nativeStartedAt = performance.now();
  nativeStartedElapsed = nativeElapsed;
  drawNativeFrame();
  nativeAnimationRequest = requestAnimationFrame(tickNativeFrame);
}

function loadNativeImage(path) {
  return new Promise((resolve, reject) => {
    const image = new Image();
    image.onload = () => resolve(image);
    image.onerror = () => reject(new Error('A native source frame is unavailable.'));
    image.src = path;
  });
}

async function loadNativeReference() {
  const version = ++nativeLoadVersion;
  nativeFetchController?.abort();
  const controller = new AbortController();
  nativeFetchController = controller;
  const mat = document.getElementById('ro-animation-mat');
  const pending = document.getElementById('ro-animation-pending');
  const direction = document.getElementById('ro-direction').value;
  pauseNativeReference();
  nativeImages = [];
  nativeElapsed = 0;
  nativePlayButton.disabled = true;
  nativeReplayButton.disabled = true;
  mat.hidden = true;
  pending.hidden = false;
  pending.textContent = 'Loading original sprite frames…';
  document.getElementById('ro-playhead').textContent = 'Native frames loading…';
  document.getElementById('ro-download-video').href = nativeRoot + `swordsman-attack-${direction}.mp4`;
  try {
    const manifest = await readJson(nativeRoot, 'manifest.json', controller.signal);
    const sequence = manifest.sequences?.find(item => item.id === `swordsman-attack-${direction}`);
    if (!sequence || sequence.frames?.length !== 9 || sequence.frameDurationMs !== 96) throw new Error('Unexpected native source sequence.');
    const frames = await Promise.all(sequence.frames.map(frame => loadNativeImage(nativeRoot + frame.file.replace(/\.png$/, '-3x.png'))));
    if (version !== nativeLoadVersion || controller.signal.aborted) return;
    if (frames.some(frame => frame.naturalWidth !== 576 || frame.naturalHeight !== 576)) throw new Error('Unexpected native source canvas.');
    nativeImages = frames;
    nativeFrameDuration = sequence.frameDurationMs;
    nativeElapsed = 0;
    drawNativeFrame();
    mat.hidden = false;
    pending.hidden = true;
  } catch (error) {
    if (version !== nativeLoadVersion || error.name === 'AbortError') return;
    pending.textContent = 'The native frames could not be loaded. Reload result to check again.';
    document.getElementById('ro-playhead').textContent = 'Native preview unavailable';
  } finally {
    if (version === nativeLoadVersion) nativeFetchController = null;
  }
}

experimentSelect.addEventListener('change', () => { userSelectedExperiment = true; loadResult(); });
playButton.addEventListener('click', async () => {
  if (!video.paused) return video.pause();
  try {
    if (video.ended) video.currentTime = 0;
    await video.play();
  } catch (error) {
    if (error.name !== 'AbortError') setStatus('Playback could not start. Try the native video controls or Reload result.', true);
  }
});
restartButton.addEventListener('click', () => { video.pause(); video.currentTime = 0; updateControls(); });
previousFrame.addEventListener('click', () => stepFrame(-1));
nextFrame.addEventListener('click', () => stepFrame(1));
loopToggle.addEventListener('change', () => { video.loop = loopToggle.checked; });
speedSelect.addEventListener('change', () => { video.playbackRate = Number(speedSelect.value); });
document.getElementById('reload-button').addEventListener('click', () => { loadResult(); loadNativeReference(); });
document.getElementById('ro-direction').addEventListener('change', loadNativeReference);
document.getElementById('native-source-record').href = nativeRoot + 'manifest.json';
downloadLink.addEventListener('click', event => { if (downloadLink.getAttribute('aria-disabled') === 'true') event.preventDefault(); });
video.addEventListener('loadedmetadata', () => {
  const experiment = experiments[experimentSelect.value];
  setStatus(`Original ${experimentSelect.value.toUpperCase()} video ready. ${experiment.readyNote}`);
  updateControls();
});
video.addEventListener('error', () => {
  setStatus('The source MP4 could not be decoded. Use Reload result or inspect the request record below.', true);
  updateControls();
});
for (const event of ['play', 'pause', 'ended', 'timeupdate', 'seeked', 'durationchange', 'emptied']) video.addEventListener(event, updateControls);
video.addEventListener('ratechange', () => {
  if ([0.5, 1, 1.5].includes(video.playbackRate)) speedSelect.value = String(video.playbackRate);
});
nativePlayButton.addEventListener('click', () => {
  if (nativePlaying) pauseNativeReference();
  else playNativeReference();
});
nativeReplayButton.addEventListener('click', () => {
  if (!nativeImages.length) return;
  pauseNativeReference();
  nativeElapsed = 0;
  playNativeReference();
});
loopToggle.checked = false;
video.loop = false;
window.addEventListener('pagehide', () => {
  sourceFetchController?.abort();
  nativeFetchController?.abort();
  if (sourceObjectUrl) URL.revokeObjectURL(sourceObjectUrl);
  pauseNativeReference();
});
loadResult();
loadNativeReference();
