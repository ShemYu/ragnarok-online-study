(() => {
  'use strict';

  const $ = (id) => document.getElementById(id);
  const manifestUrl = new URL('assets/attack/manifest.json', document.baseURI);
  const elements = {
    original: $('original-canvas'), reference: $('reference-canvas'),
    play: $('play-toggle'), once: $('play-once'), restart: $('restart'),
    previous: $('previous-frame'), next: $('next-frame'), slider: $('frame-slider'),
    loop: $('loop-toggle'), speed: $('speed-select'), background: $('background-select'),
    baseline: $('baseline-toggle'), status: $('playback-status'), progress: $('cycle-progress'),
    error: $('error-message'), exportPng: $('export-png'), exportRecipe: $('export-recipe'),
    download: $('download-link'), exportStatus: $('export-status'),
  };
  const state = { ready: false, playing: false, elapsed: 0, loop: true, oneShot: false, speed: 1, zoom: 3, background: 'plain', baseline: true };
  const tracks = {};
  let manifest;
  let previousTime = null;
  let lastFrameKey = '';
  let lastStatusKey = '';

  const number = (value, fallback) => Number.isFinite(value) ? value : fallback;
  const positive = (value, fallback) => Number.isFinite(value) && value > 0 ? value : fallback;
  const makeCanvas = (width, height) => Object.assign(document.createElement('canvas'), { width, height });

  function pixelHash(data) {
    let hash = 2166136261;
    for (let i = 0; i < data.length; i += 1) hash = Math.imul(hash ^ data[i], 16777619);
    return (hash >>> 0).toString(16).padStart(8, '0');
  }

  function loadImage(url) {
    return new Promise((resolve, reject) => {
      const image = new Image();
      image.onload = () => resolve(image);
      image.onerror = () => reject(new Error(`Could not load artwork: ${url.pathname.split('/').pop()}`));
      image.src = url.href;
    });
  }

  async function loadTrack(spec, key) {
    if (!spec || typeof spec.file !== 'string' || !Array.isArray(spec.frames) || spec.frames.length === 0) {
      throw new Error(`${key} needs an image and at least one animation frame.`);
    }
    const image = await loadImage(new URL(spec.file, manifestUrl));
    const width = Math.round(positive(spec.canvasWidth, positive(manifest.canvasWidth, 192)));
    const height = Math.round(positive(spec.canvasHeight, positive(manifest.canvasHeight, 192)));
    const targetAnchor = spec.anchor || manifest.anchor || { x: 96, y: 160 };
    const scale = positive(spec.scale, 1);
    const alphaThreshold = number(spec.alphaThreshold, 0);
    let duration = 0;
    let sourceHasTransparency = false;
    const frames = spec.frames.map((frame, index) => {
      const x = number(frame.x, 0), y = number(frame.y, 0);
      const w = positive(frame.w, positive(spec.cellWidth, width));
      const h = positive(frame.h, positive(spec.cellHeight, height));
      if (x < 0 || y < 0 || x + w > image.naturalWidth || y + h > image.naturalHeight) {
        throw new Error(`${key} frame ${index + 1} lies outside its source image.`);
      }
      const source = makeCanvas(w, h);
      const sourceContext = source.getContext('2d', { willReadFrequently: true });
      sourceContext.imageSmoothingEnabled = false;
      sourceContext.drawImage(image, x, y, w, h, 0, 0, w, h);
      const sourcePixels = sourceContext.getImageData(0, 0, w, h);
      for (let i = 3; i < sourcePixels.data.length; i += 4) {
        if (sourcePixels.data[i] < 255) sourceHasTransparency = true;
      }
      if (alphaThreshold > 0) {
        for (let i = 3; i < sourcePixels.data.length; i += 4) {
          if (sourcePixels.data[i] < alphaThreshold) sourcePixels.data[i] = 0;
        }
        sourceContext.putImageData(sourcePixels, 0, 0);
      }
      const canvas = makeCanvas(width, height);
      const context = canvas.getContext('2d', { willReadFrequently: true });
      context.imageSmoothingEnabled = false;
      const anchorX = number(frame.anchorX, w / 2);
      const anchorY = number(frame.anchorY, h);
      context.drawImage(source, Math.round(number(targetAnchor.x, width / 2) - anchorX * scale), Math.round(number(targetAnchor.y, height - 32) - anchorY * scale), Math.round(w * scale), Math.round(h * scale));
      const rgba = context.getImageData(0, 0, width, height).data;
      let opaquePixels = 0;
      for (let i = 3; i < rgba.length; i += 4) if (rgba[i] > 0) opaquePixels += 1;
      const durationMs = positive(frame.durationMs, 100);
      const result = { ...frame, x, y, w, h, anchorX, anchorY, durationMs, phase: frame.phase || `Pose ${index + 1}`, start: duration, canvas, hash: pixelHash(rgba), opaquePixels };
      duration += durationMs;
      return result;
    });
    const transparent = spec.transparent !== false && spec.sourceOpaque !== true && sourceHasTransparency;
    return { ...spec, name: spec.name || key, width, height, targetAnchor, scale, frames, duration, transparent, sourceOpaque: !transparent };
  }

  function frameIndexAt(track, elapsed) {
    for (let i = track.frames.length - 1; i >= 0; i -= 1) {
      if (elapsed >= track.frames[i].start) return i;
    }
    return 0;
  }

  function activeFrames() {
    const progress = Math.max(0, Math.min(1, state.elapsed / tracks.original.duration));
    return {
      progress,
      original: frameIndexAt(tracks.original, state.elapsed),
      reference: frameIndexAt(tracks.reference, progress * tracks.reference.duration),
    };
  }

  function drawTrack(key, index) {
    const track = tracks[key], canvas = elements[key], frame = track.frames[index];
    const context = canvas.getContext('2d');
    context.imageSmoothingEnabled = false;
    context.clearRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = '#ebe9de';
    context.fillRect(0, 0, canvas.width, canvas.height);
    if (state.background === 'checker') {
      const size = 8;
      context.fillStyle = '#f6f4eb';
      for (let y = 0; y < canvas.height; y += size) {
        for (let x = 0; x < canvas.width; x += size) {
          if ((x / size + y / size) % 2 === 0) context.fillRect(x, y, size, size);
        }
      }
    }
    if (state.baseline) {
      context.fillStyle = '#bec6ad';
      context.fillRect(12, Math.round(number(track.targetAnchor.y, canvas.height - 32)), canvas.width - 24, 1);
      context.fillRect(Math.round(number(track.targetAnchor.x, canvas.width / 2)), Math.round(number(track.targetAnchor.y, canvas.height - 32)) - 2, 1, 5);
    }
    context.drawImage(frame.canvas, 0, 0);
    Object.assign(canvas.dataset, {
      frame: String(index), frameNumber: String(index + 1), frameCount: String(track.frames.length),
      spriteHash: frame.hash, opaquePixels: String(frame.opaquePixels), source: track.file,
      phase: frame.phase, playing: String(state.playing), progress: (state.elapsed / tracks.original.duration).toFixed(4),
      modular: 'false', zoom: String(state.zoom), transparent: String(track.transparent),
    });
    $(`${key}-frame`).textContent = `Frame ${index + 1} / ${track.frames.length}`;
    if (key === 'original') $('original-phase').textContent = frame.phase;
  }

  function render(force = false) {
    if (!state.ready) return;
    const active = activeFrames();
    const key = `${active.original}:${active.reference}:${state.background}:${state.baseline}:${state.playing}:${state.zoom}`;
    if (force || key !== lastFrameKey) {
      drawTrack('original', active.original);
      drawTrack('reference', active.reference);
      elements.slider.value = String(active.original);
      lastFrameKey = key;
    }
    const statusKey = `${state.playing}:${state.oneShot}:${state.loop}:${active.original}`;
    if (statusKey !== lastStatusKey) {
      const frame = tracks.original.frames[active.original];
      const label = state.playing ? (state.oneShot ? 'Playing once' : state.loop ? 'Looping' : 'Playing') : 'Paused';
      elements.status.textContent = `${label} · ${frame.phase} · frame ${active.original + 1} of ${tracks.original.frames.length}`;
      elements.play.textContent = state.playing ? 'Pause' : 'Play';
      elements.play.setAttribute('aria-label', state.playing ? 'Pause animation' : 'Play animation');
      elements.slider.setAttribute('aria-valuetext', `Frame ${active.original + 1}: ${frame.phase}`);
      lastStatusKey = statusKey;
    }
    elements.progress.style.width = `${active.progress * 100}%`;
    document.body.dataset.playing = String(state.playing);
    document.body.dataset.originalFrame = String(active.original);
    document.body.dataset.referenceFrame = String(active.reference);
  }

  function setPlaying(playing) {
    state.playing = playing;
    previousTime = null;
    render(true);
  }

  function seek(index) {
    const value = Math.max(0, Math.min(tracks.original.frames.length - 1, index));
    state.elapsed = tracks.original.frames[value].start;
    setPlaying(false);
  }

  function tick(now) {
    if (state.ready && state.playing && previousTime !== null) {
      state.elapsed += Math.max(0, now - previousTime) * state.speed;
      if (state.elapsed >= tracks.original.duration) {
        if (state.loop && !state.oneShot) state.elapsed %= tracks.original.duration;
        else {
          state.elapsed = tracks.original.duration;
          state.playing = false;
        }
      }
      render();
    }
    previousTime = state.playing ? now : null;
    requestAnimationFrame(tick);
  }

  function updateScale() {
    for (const key of ['original', 'reference']) {
      const canvas = elements[key];
      const width = tracks[key]?.width || 192;
      canvas.style.width = `${width * state.zoom}px`;
    }
    for (const button of document.querySelectorAll('[data-zoom]')) {
      button.setAttribute('aria-pressed', String(Number(button.dataset.zoom) === state.zoom));
    }
    const actual = elements.original.getBoundingClientRect().width / (tracks.original?.width || 192);
    $('scale-note').textContent = Math.abs(actual - state.zoom) < 0.03
      ? `${state.zoom}× display · full canvas visible.`
      : `Requested ${state.zoom}× · fitted to ${actual.toFixed(2)}× to keep the full canvas visible.`;
    render(true);
  }

  function prepareDownload(kind) {
    const index = activeFrames().original;
    const track = tracks.original, frame = track.frames[index];
    const stem = `original-attack-frame-${String(index + 1).padStart(2, '0')}`;
    let href;
    if (kind === 'png') {
      href = frame.canvas.toDataURL('image/png');
    } else {
      const recipe = {
        schema: 'character-atelier-attack-frame/1',
        design: track.name, source: track.file, frameIndex: index,
        frame: { x: frame.x, y: frame.y, w: frame.w, h: frame.h, anchorX: frame.anchorX, anchorY: frame.anchorY, durationMs: frame.durationMs, phase: frame.phase },
        canvas: { width: track.width, height: track.height, anchor: track.targetAnchor, scale: track.scale },
        alphaThreshold: number(track.alphaThreshold, 0),
        sourceOpaque: track.sourceOpaque,
        modularEquipment: false,
        note: 'One-direction full-body sprite animation. Equipment is baked into the source artwork.',
      };
      href = `data:application/json;charset=utf-8,${encodeURIComponent(JSON.stringify(recipe, null, 2))}`;
    }
    elements.download.href = href;
    elements.download.download = `${stem}.${kind === 'png' ? 'png' : 'json'}`;
    elements.download.textContent = `Download frame ${index + 1} ${kind === 'png' ? 'PNG' : 'recipe JSON'} ↗`;
    elements.download.hidden = false;
    elements.exportStatus.textContent = kind === 'png' ? `Ready · ${track.transparent ? 'transparent ' : ''}${track.width} × ${track.height} PNG${track.transparent ? '' : ' with the source backdrop retained'}. Use the link to save.` : 'Ready · pose coordinates and source settings. Use the link to save.';
  }

  elements.play.addEventListener('click', () => {
    if (!state.ready) return;
    if (!state.playing && state.elapsed >= tracks.original.duration) {
      state.elapsed = 0;
      state.oneShot = false;
    }
    setPlaying(!state.playing);
  });
  elements.once.addEventListener('click', () => {
    state.elapsed = 0;
    state.oneShot = true;
    setPlaying(true);
  });
  elements.restart.addEventListener('click', () => { state.elapsed = 0; previousTime = null; render(true); });
  elements.previous.addEventListener('click', () => seek(activeFrames().original - 1));
  elements.next.addEventListener('click', () => seek(activeFrames().original + 1));
  elements.slider.addEventListener('input', () => seek(Number(elements.slider.value)));
  elements.loop.addEventListener('change', () => { state.loop = elements.loop.checked; state.oneShot = false; render(true); });
  elements.speed.addEventListener('change', () => { state.speed = Number(elements.speed.value); previousTime = null; });
  elements.background.addEventListener('change', () => { state.background = elements.background.value; render(true); });
  elements.baseline.addEventListener('change', () => { state.baseline = elements.baseline.checked; render(true); });
  document.querySelectorAll('[data-zoom]').forEach((button) => button.addEventListener('click', () => { state.zoom = Number(button.dataset.zoom); updateScale(); }));
  elements.exportPng.addEventListener('click', () => prepareDownload('png'));
  elements.exportRecipe.addEventListener('click', () => prepareDownload('json'));
  document.addEventListener('visibilitychange', () => { previousTime = null; });
  window.addEventListener('resize', updateScale);

  async function init() {
    try {
      const response = await fetch(manifestUrl, { cache: 'no-store' });
      if (!response.ok) throw new Error(`The attack manifest could not be loaded (HTTP ${response.status}).`);
      manifest = await response.json();
      if (manifest.schema !== 'character-atelier-attack/1') throw new Error('The attack manifest uses an unsupported format.');
      const loaded = await Promise.all([loadTrack(manifest.original, 'original'), loadTrack(manifest.reference, 'reference')]);
      [tracks.original, tracks.reference] = loaded;
      $('export-note').textContent = tracks.original.transparent
        ? 'Export the current original pose on a transparent canvas.'
        : 'Export the current original pose. The source backdrop remains in the PNG.';
      for (const key of ['original', 'reference']) {
        elements[key].width = tracks[key].width;
        elements[key].height = tracks[key].height;
        elements[key].style.aspectRatio = `${tracks[key].width} / ${tracks[key].height}`;
        $(`${key}-name`).textContent = tracks[key].name;
      }
      elements.slider.max = String(tracks.original.frames.length - 1);
      const strikeFrame = Math.max(0, Math.min(tracks.original.frames.length - 1, Math.round(number(manifest.strikeFrame, 0))));
      $('strike-label').textContent = `Strike · frame ${strikeFrame + 1}`;
      $('cycle-duration').textContent = `${(tracks.original.duration / 1000).toFixed(2)} s per attack at 1×`;
      document.querySelectorAll('button:disabled,input:disabled,select:disabled').forEach((control) => { control.disabled = false; });
      state.ready = true;
      state.playing = !window.matchMedia('(prefers-reduced-motion: reduce)').matches;
      document.body.dataset.ready = 'true';
      updateScale();
      render(true);
      requestAnimationFrame(tick);
    } catch (error) {
      const message = error instanceof Error ? error.message : String(error);
      elements.error.textContent = `${message} Reload this page after the local artwork is available.`;
      elements.error.hidden = false;
      elements.status.textContent = 'The attack study could not start.';
      document.body.dataset.ready = 'false';
      console.error('Attack study failed:', error);
    }
  }
  init();
})();
