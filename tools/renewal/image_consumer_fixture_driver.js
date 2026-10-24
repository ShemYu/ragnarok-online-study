// T07.007.014.016 browser driver for the authored image-consumer fixture.
// Copied byte-identically into the generated fixture as driver.js (pinned by
// the builder). In a page it renders one button per control/consumer plus
// "Run all"; each run uses a fresh iframe realm that loads production.js
// (unchanged S01-S08 slices + pinned scaffold), one authored image in flight,
// an owned WebGL2 context and explicit cleanup. Records are JSON-visible in
// #records and window.__imageConsumerFixtureRecords. In Node (module.exports
// present) it only exports the pure observer/adapter/judge functions so tests
// can drive them with authored doubles; nothing starts.
//
// Observation is transparent: the Texture.load completion observer and the
// texImage2D/generateMipmap adapters forward the actual this/arguments to the
// unchanged originals. Injected faults are labelled and never reported as
// natural outcomes. Records are observations; Root qualifies them.
(function (root, factory) {
  'use strict';
  const api = factory();
  if (typeof module === 'object' && module && module.exports) module.exports = api;
  else {
    root.__imageConsumerFixtureDriver = api;
    if (root.document && root.__IMAGE_CONSUMER_FIXTURES) api.start(root);
  }
})(typeof window !== 'undefined' ? window : globalThis, function () {
  'use strict';

  const SCHEMA = 't07.007.014.016/record-v1';
  const LIMITS = Object.freeze({
    maxEncodedBytes: 4096, maxDimension: 32, maxCanvasReadPixels: 1024, maxGlErrors: 16,
    validTimeoutMs: 4000, boundedControlMs: 2000, matrixBudgetMs: 60000, workerReplyMs: 1000, realmSetupMs: 3000
  });
  const GL = Object.freeze({
    NO_ERROR: 0, INVALID_ENUM: 0x0500, INVALID_VALUE: 0x0501, INVALID_OPERATION: 0x0502, OUT_OF_MEMORY: 0x0505,
    INVALID_FRAMEBUFFER_OPERATION: 0x0506, CONTEXT_LOST_WEBGL: 0x9242, FRAMEBUFFER_COMPLETE: 0x8cd5
  });

  // ---- Pure parts (exercised by Node tests with authored doubles) ----

  // One canonical completion schema: the gate's record fields (submissions,
  // events, forward_count, late, duplicates) are exactly what evaluateControl
  // reads, via projectCompletion. receivers holds the actual completion `this`
  // objects for identity checks only and is never projected.
  const COMPLETION_FIELDS = ['submissions', 'events', 'forward_count', 'late', 'duplicates'];
  function makeGate(now) {
    const gate = { open: true, submissions: [], events: [], forward_count: 0, late: [], duplicates: [] };
    Object.defineProperties(gate, {
      now: { value: now }, seq: { value: 0, writable: true }, onSettle: { value: null, writable: true },
      receivers: { value: [] }
    });
    return gate;
  }

  function deepFreeze(o) {
    if (o && typeof o === 'object' && !Object.isFrozen(o)) { Object.freeze(o); Object.keys(o).forEach((k) => deepFreeze(o[k])); }
    return o;
  }
  // Checked immutable projection of the gate into a record.
  function projectCompletion(gate) {
    const out = {};
    for (const k of COMPLETION_FIELDS) {
      const v = gate[k];
      if (k === 'forward_count' ? !Number.isInteger(v) : !Array.isArray(v)) throw new Error('completion schema: ' + k);
      out[k] = JSON.parse(JSON.stringify(v));
    }
    return deepFreeze(out);
  }
  function completionSchemaOk(c) {
    return !!c && COMPLETION_FIELDS.every((k) => (k === 'forward_count' ? Number.isInteger(c[k]) : Array.isArray(c[k])));
  }

  // Wrap Texture.load: forward the actual this/arguments to the unchanged
  // original with only the completion callback replaced by an observer that
  // records then forwards the actual this/arguments exactly once while open.
  function observeTextureLoad(originalLoad, gate, inspectCanvas) {
    return function observedTextureLoad(data, oncomplete) {
      const args = Array.prototype.slice.call(arguments);
      gate.submissions.push({ at: gate.now(), seq: gate.seq++, arg_count: args.length, data_kind: data === null ? 'null' : typeof data });
      args[1] = function observedCompletion() {
        const event = {
          at: gate.now(), seq: gate.seq++, success: arguments[0], arg_count: arguments.length,
          this_null: this === null || this === undefined, canvas: inspectCanvas(this)
        };
        gate.receivers.push(this);
        event.receiver_index = gate.receivers.length - 1;
        if (!gate.open) {
          event.forwarded = false; event.reason = 'control_closed';
          gate.late.push(event);
          if (gate.onSettle) gate.onSettle('late', event);
          return undefined;
        }
        if (gate.forward_count > 0) {
          event.forwarded = false; event.reason = 'duplicate_completion';
          gate.duplicates.push(event);
          return undefined;
        }
        gate.forward_count++;
        event.forwarded = true;
        gate.events.push(event);
        try {
          return oncomplete.apply(this, arguments);
        } catch (e) {
          event.forward_threw = String(e && e.message || e);
          throw e;
        } finally {
          event.forward_returned_at = gate.now();
          if (gate.onSettle) gate.onSettle('forwarded', event);
        }
      };
      return originalLoad.apply(this, args);
    };
  }

  // Own-property forwarding adapter on one owned context. The actual receiver
  // and arguments reach the native prototype function; its result is returned.
  function installForwardingAdapter(gl, name, nativeFn, onCall, after) {
    const adapter = function () {
      const call = onCall(this, arguments);
      const result = nativeFn.apply(this, arguments);
      if (after) after(this, arguments, call);
      return result;
    };
    Object.defineProperty(gl, name, { value: adapter, configurable: true, writable: true, enumerable: false });
    return adapter;
  }

  function recordTexImage2D(gl, log, now, gate) {
    return function (receiver, args) {
      const source = args[args.length - 1];
      const call = {
        at: now(), seq: gate ? gate.seq++ : null, receiver_is_owned_context: receiver === gl, arg_count: args.length,
        source_kind: source && source.constructor ? source.constructor.name : typeof source,
        source_width: source && typeof source.width === 'number' ? source.width : null,
        source_height: source && typeof source.height === 'number' ? source.height : null,
        context_lost_at_call: typeof gl.isContextLost === 'function' ? gl.isContextLost() : null
      };
      log.push(call);
      return call;
    };
  }

  // Transparent context-local drawImage observer for the owned ground 2D
  // context: records receiver/source identity/all numeric arguments and how
  // the native call ended, forwards the actual this/arguments and returns the
  // native result (or rethrows its exception unchanged).
  function observeDrawImage(owner, nativeFn, log, gate) {
    return function observedDrawImage() {
      const call = {
        seq: gate.seq++, at: gate.now(), receiver_is_owned_context: this === owner, arg_count: arguments.length,
        source_receiver_index: gate.receivers.indexOf(arguments[0]),
        args: Array.prototype.slice.call(arguments, 1).map((v) => (typeof v === 'number' ? v : String(v))),
        returned: false, threw: null
      };
      log.push(call);
      try {
        const r = nativeFn.apply(this, arguments);
        call.returned = true;
        return r;
      } catch (e) { call.threw = String(e && e.message || e); throw e; }
    };
  }
  // Install on the owned context only; returns a restore that removes only
  // this observer (re-installing any prior own property it shadowed).
  function installDrawImageObserver(ctx2d, log, gate) {
    const prior = Object.getOwnPropertyDescriptor(ctx2d, 'drawImage');
    const observer = observeDrawImage(ctx2d, ctx2d.drawImage, log, gate);
    Object.defineProperty(ctx2d, 'drawImage', { value: observer, configurable: true, writable: true, enumerable: false });
    return function restoreDrawImage() {
      const now = Object.getOwnPropertyDescriptor(ctx2d, 'drawImage');
      if (!now || now.value !== observer) return false;
      if (prior) Object.defineProperty(ctx2d, 'drawImage', prior); else delete ctx2d.drawImage;
      return true;
    };
  }
  // Ground 258/256 call evidence: exactly two normally returned calls, in order,
  // on the owned receiver, from the first observed completion canvas, with
  // five arguments, both before the sole 512x512 atlas upload.
  const GROUND_DRAWS = [[0, 0, 258, 258], [1, 1, 256, 256]];
  function judgeGroundDraws(draws, uploads) {
    const reasons = [];
    if (draws.length !== 2) reasons.push('draw_count:' + draws.length);
    draws.slice(0, 2).forEach(function (d, i) {
      if (!d.returned || d.threw !== null) reasons.push('draw' + i + '_not_returned_normally');
      if (!d.receiver_is_owned_context) reasons.push('draw' + i + '_receiver_not_owned_context');
      if (d.arg_count !== 5) reasons.push('draw' + i + '_arg_count:' + d.arg_count);
      if (d.source_receiver_index !== 0) reasons.push('draw' + i + '_source_not_completion_canvas');
      if (JSON.stringify(d.args) !== JSON.stringify(GROUND_DRAWS[i])) reasons.push('draw' + i + '_args:' + d.args.join(','));
    });
    if (draws.length >= 2 && !(draws[0].seq < draws[1].seq)) reasons.push('draw_order');
    if (uploads.length !== 1) reasons.push('upload_count:' + uploads.length);
    else {
      const up = uploads[0];
      if (up.source_width !== 512 || up.source_height !== 512) reasons.push('upload_not_512_atlas');
      if (!draws.every((d) => typeof up.seq === 'number' && d.seq < up.seq)) reasons.push('draw_not_before_upload');
    }
    return { ok: reasons.length === 0, reasons };
  }

  // Labelled owned-observer fault: one deliberate invalid-enum query after
  // the forwarded upload. It never edits production bytes or arguments.
  function injectedFault(label) {
    const fault = { label, armed: true, fired: false };
    fault.after = function (receiver, args, call) {
      if (!fault.armed || fault.fired) return;
      fault.fired = true;
      receiver.getParameter(0);
      call.injected_fault_after = label;
    };
    return fault;
  }

  function drainGlErrors(gl, max) {
    const errors = [];
    const limit = max || LIMITS.maxGlErrors;
    for (let i = 0; i < limit; i++) {
      const e = gl.getError();
      if (e === GL.NO_ERROR) return { errors, exhausted: false };
      errors.push(e);
    }
    return { errors, exhausted: true };
  }

  function pixelMatches(actual, expected, tol) {
    if (!actual || actual.length !== 4) return false;
    for (let i = 0; i < 4; i++) if (Math.abs(actual[i] - expected[i]) > tol) return false;
    return true;
  }

  function comparePixels(expected, read) {
    const rows = expected.map(function (p) {
      const actual = read(p.x, p.y);
      return { x: p.x, y: p.y, expected: p.rgba, tol: p.tol, actual, ok: pixelMatches(actual, p.rgba, p.tol) };
    });
    return { all_ok: rows.length > 0 && rows.every((r) => r.ok), rows };
  }

  const drainClean = (d) => !!d && Array.isArray(d.errors) && d.errors.length === 0 && d.exhausted === false;

  // Upload verification is independent of callbacks and texture handles. It
  // also needs a positive successful GPU readback and a bounded, nonexhausted,
  // empty diagnostic drain; consumer and diagnostic errors stay separate.
  function judgeUpload(u) {
    const reasons = [];
    const attempted = u.upload_calls > 0;
    if (!attempted) reasons.push('no_texImage2D_call');
    if (u.context_lost) reasons.push('context_lost');
    if (!u.consumer_errors) reasons.push('consumer_errors_unchecked');
    else {
      if (u.consumer_errors.errors.length) reasons.push('gl_errors:' + u.consumer_errors.errors.map((e) => '0x' + e.toString(16)).join(','));
      if (u.consumer_errors.exhausted) reasons.push('gl_error_drain_exhausted');
    }
    if (!u.texture_present) reasons.push('no_texture_object');
    if (u.fbo_status !== GL.FRAMEBUFFER_COMPLETE) reasons.push('framebuffer_not_complete');
    if (!u.readback || u.readback.readback_ok !== true) reasons.push('gpu_readback_not_positive');
    if (!drainClean(u.diagnostic_errors)) reasons.push('diagnostic_gl_errors_or_exhausted');
    return { upload_attempted: attempted, upload_verified: attempted && reasons.length === 0, reasons };
  }

  // Bounded texture readback through an owned FBO. Each probe is read twice
  // into the buffer prefilled with two different sentinels; a readPixels that
  // throws, raises a GL error or leaves the buffer untouched (zero or stale)
  // is an explicit failure, never pixels. The FBO is always released.
  const SENTINELS = [[1, 2, 3, 4], [254, 253, 252, 251]];
  function readOnce(gl, x, y, buf, sentinel) {
    buf.set(sentinel);
    try { gl.readPixels(x, y, 1, 1, gl.RGBA, gl.UNSIGNED_BYTE, buf); } catch (e) { return { ok: false, reason: 'readPixels_threw:' + String(e && e.message || e) }; }
    let d;
    try { d = drainGlErrors(gl, 4); } catch (e) { return { ok: false, reason: 'getError_threw:' + String(e && e.message || e) }; }
    if (!drainClean(d)) return { ok: false, reason: 'readPixels_gl_error:' + d.errors.join(',') + (d.exhausted ? ':exhausted' : '') };
    return { ok: true, px: [buf[0], buf[1], buf[2], buf[3]] };
  }
  function readTextureProbes(gl, tex, dims, points) {
    const out = { fbo_status: null, read: null, unavailable: null, failures: [], pre_errors: null, fbo_created: false, fbo_deleted: null, readback_ok: false };
    if (!tex) { out.unavailable = 'no_texture'; return out; }
    let fbo = null;
    try {
      if (gl.isContextLost()) out.unavailable = 'context_lost';
      else {
        out.pre_errors = drainGlErrors(gl);
        if (!drainClean(out.pre_errors)) out.failures.push('pre_probe_gl_errors');
        fbo = gl.createFramebuffer();
        out.fbo_created = !!fbo;
        if (!fbo) out.failures.push('createFramebuffer_null');
        else {
          gl.bindFramebuffer(gl.FRAMEBUFFER, fbo);
          gl.framebufferTexture2D(gl.FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, tex, 0);
          out.fbo_status = gl.checkFramebufferStatus(gl.FRAMEBUFFER);
          if (out.fbo_status !== GL.FRAMEBUFFER_COMPLETE) out.failures.push('framebuffer_not_complete');
          else {
            const buf = new Uint8Array(4);
            out.read = comparePixels(points, function (x, y) {
              if (!dims || x >= dims.width || y >= dims.height) { out.failures.push('probe_outside_upload@' + x + ',' + y); return null; }
              const a = readOnce(gl, x, y, buf, SENTINELS[0]);
              const b = a.ok ? readOnce(gl, x, y, buf, SENTINELS[1]) : a;
              if (!a.ok || !b.ok) { out.failures.push((a.ok ? b : a).reason + '@' + x + ',' + y); return null; }
              if (a.px.join() !== b.px.join()) { out.failures.push('readPixels_buffer_untouched@' + x + ',' + y); return null; }
              return a.px;
            });
          }
        }
      }
    } catch (e) {
      out.failures.push('probe_exception:' + String(e && e.message || e));
    } finally {
      if (fbo) {
        try { gl.bindFramebuffer(gl.FRAMEBUFFER, null); } catch (e) { out.failures.push('unbind_exception:' + String(e && e.message || e)); }
        try { gl.deleteFramebuffer(fbo); out.fbo_deleted = true; } catch (e) { out.fbo_deleted = false; out.failures.push('deleteFramebuffer_exception:' + String(e && e.message || e)); }
      }
    }
    out.readback_ok = !out.unavailable && out.failures.length === 0 && !!out.read && out.read.rows.length > 0 && out.read.rows.every((r) => r.actual !== null);
    return out;
  }

  function check(list, name, ok, detail) { list.push({ name, ok: !!ok, detail: detail === undefined ? null : detail }); }
  const dimsEq = (got, want) => !!got && !!want && got.width === want.width && got.height === want.height;

  // Expected-control evaluation from separate decode/forward/upload/pixel facts.
  const within = (ms, limit) => typeof ms === 'number' && Number.isFinite(ms) && ms >= 0 && ms <= limit;
  function controlDeadlineMs(control) {
    return control.kind === 'malformed' || control.kind === 'closed_late' ? LIMITS.boundedControlMs : LIMITS.validTimeoutMs + LIMITS.realmSetupMs;
  }
  // Sticky failures: once a driver, realm, unhandled-rejection, forwarding,
  // ground-draw, diagnostic readback/FBO-release or cleanup failure is
  // observed, no expected outcome PASSes. The labelled injected GL fault is a
  // consumer GL error drained before diagnostics, not one of these; any
  // readback/status/FBO-release failure or post-probe diagnostic GL error is
  // unrelated to it and stays sticky even where upload_verified=false is expected.
  function stickyFailures(rec) {
    const out = [];
    if (rec.exception) out.push('driver_exception');
    (rec.failures || []).forEach((f) => out.push(f.kind));
    if (rec.realm_errors && rec.realm_errors.length) out.push('realm_errors:' + rec.realm_errors.length);
    const g = rec.gl || {};
    if (Array.isArray(g.gpu_failures) && g.gpu_failures.length) out.push('diagnostic_readback_failures:' + g.gpu_failures.length);
    if (g.diagnostic_errors && !drainClean(g.diagnostic_errors)) out.push('diagnostic_gl_errors');
    const c = rec.completion;
    if (c && Array.isArray(c.events) && c.events.some((e) => e.forward_threw !== undefined)) out.push('forward_threw');
    if ((rec.ground_draws || []).some((d) => d.threw !== null)) out.push('ground_draw_threw');
    if (rec.cleanup && rec.cleanup.failures && rec.cleanup.failures.length) out.push('cleanup_failures:' + rec.cleanup.failures.length);
    return out;
  }

  function evaluateControl(rec, control) {
    const c = [];
    if (!completionSchemaOk(rec.completion)) {
      check(c, 'completion_schema', false, rec.completion ? Object.keys(rec.completion) : null);
      check(c, 'no_sticky_failures', stickyFailures(rec).length === 0, stickyFailures(rec));
      return { result: 'FAIL', checks: c };
    }
    const consumer = rec.consumer;
    const want = control.expect ? control.expect[consumer] : null;
    const first = rec.completion.events[0] || null;
    const uploads = rec.upload.calls;
    const lastUpload = uploads[uploads.length - 1] || null;
    const waterCb = rec.water_user_callback;
    const decoded = rec.decode.native_load_events > 0;
    switch (control.kind) {
      case 'valid':
        check(c, 'native_decode_completed', decoded);
        check(c, 'forwarded_once_success', rec.completion.forward_count === 1 && first && first.success === true);
        check(c, 'completion_canvas_dims', first && dimsEq(first.canvas, control.expect.completion), first && first.canvas);
        check(c, 'completion_canvas_pixels', rec.probes.completion && rec.probes.completion.all_ok);
        if (control.expect.preMagenta) check(c, 'proc_canvas_pre_magenta_pixels', rec.probes.pre_magenta && rec.probes.pre_magenta.all_ok);
        check(c, 'revoke_before_completion', rec.revokes.length > 0 && first && rec.revokes[0].seq < first.seq);
        if (consumer === 'water') check(c, 'water_user_callback_once_with_texture', waterCb.count === 1 && waterCb.texture_non_null);
        check(c, 'one_upload_observed_dims', uploads.length === 1 && dimsEq({ width: lastUpload.source_width, height: lastUpload.source_height }, want.upload), lastUpload);
        check(c, 'upload_receiver_is_owned_context', uploads.length === 1 && lastUpload.receiver_is_owned_context);
        check(c, 'upload_verified', rec.judge.upload_verified, rec.judge.reasons);
        check(c, 'upload_source_probes', rec.probes.upload_source && rec.probes.upload_source.all_ok);
        check(c, 'gpu_probes', rec.probes.gpu && rec.probes.gpu.all_ok);
        if (consumer === 'ground') check(c, 'ground_258_256_draw_calls', rec.ground_draw_judge && rec.ground_draw_judge.ok, rec.ground_draw_judge && rec.ground_draw_judge.reasons);
        if (control.mipmapControl) {
          check(c, 'configs_enableMipmap', rec.realm.configs_enableMipmap === control.enableMipmap, rec.realm.configs_enableMipmap);
          check(c, 'generateMipmap_calls', rec.upload.generate_mipmap_calls === (control.enableMipmap ? 1 : 0), rec.upload.generate_mipmap_calls);
          if (consumer === 'water') check(c, 'water_min_filter', rec.gl.min_filter === (control.enableMipmap ? 0x2703 : 0x2601), rec.gl.min_filter);
        }
        break;
      case 'null':
        check(c, 'no_native_image', rec.decode.image_constructed === 0);
        check(c, 'forwarded_once_false_synchronously', rec.completion.forward_count === 1 && first && first.success === false && first.this_null && first.at <= rec.timing.submit_returned_at);
        if (consumer === 'ground') {
          check(c, 'blank_atlas_upload_dims', uploads.length === 1 && dimsEq({ width: lastUpload.source_width, height: lastUpload.source_height }, want.upload), lastUpload);
          check(c, 'upload_verified', rec.judge.upload_verified, rec.judge.reasons);
          check(c, 'blank_gpu_probes', rec.probes.gpu && rec.probes.gpu.all_ok);
          check(c, 'no_ground_draw', Array.isArray(rec.ground_draws) && rec.ground_draws.length === 0, rec.ground_draws);
        } else {
          check(c, 'water_user_callback_omitted', waterCb.count === 0);
          check(c, 'no_upload', uploads.length === 0);
        }
        break;
      case 'malformed':
        check(c, 'terminal_timeout_unknown_decode', rec.terminal.state === 'timeout_unknown_decode');
        check(c, 'no_native_load_event', rec.decode.native_load_events === 0, rec.decode.native_load_events);
        check(c, 'no_forwarded_completion', rec.completion.forward_count === 0);
        check(c, 'no_upload', uploads.length === 0);
        if (consumer === 'water') check(c, 'water_user_callback_omitted', waterCb.count === 0);
        break;
      case 'lose_context':
        check(c, 'native_context_lost_before_submit', rec.gl.context_lost_before_submit === true);
        check(c, 'forwarded_once_success', rec.completion.forward_count === 1 && first && first.success === true);
        check(c, 'upload_not_verified', !rec.judge.upload_verified, rec.judge.reasons);
        if (consumer === 'water') {
          check(c, 'water_user_callback_omitted', waterCb.count === 0);
          check(c, 'no_upload', uploads.length === 0);
        }
        break;
      case 'injected_gl_error':
        check(c, 'native_decode_completed', decoded);
        check(c, 'forwarded_once_success', rec.completion.forward_count === 1 && first && first.success === true);
        check(c, 'injected_fault_fired', rec.upload.injected_fault && rec.upload.injected_fault.fired);
        check(c, 'apparent_success_signal_present', consumer === 'water' ? waterCb.count === 1 && waterCb.texture_non_null : rec.gl.texture_present);
        check(c, 'checker_saw_invalid_enum', rec.gl.consumer_errors.errors.indexOf(GL.INVALID_ENUM) >= 0, rec.gl.consumer_errors);
        check(c, 'checker_rejects_false_upload_success', !rec.judge.upload_verified, rec.judge.reasons);
        break;
      case 'closed_late':
        check(c, 'terminal_closed_before_completion', rec.terminal.state === 'closed_unknown' && (!rec.completion.late[0] || rec.terminal.at <= rec.completion.late[0].at));
        check(c, 'terminal_not_overwritten', rec.terminal.state === 'closed_unknown' && rec.terminal.at === rec.terminal.closed_at && rec.terminal.rewrites_refused === (rec.completion.late.length ? 1 : 0));
        check(c, 'no_forwarded_completion', rec.completion.forward_count === 0);
        check(c, 'late_completion_recorded_not_forwarded', rec.completion.late.length >= 1 && rec.completion.late.every((e) => e.forwarded === false));
        check(c, 'no_upload', uploads.length === 0);
        if (consumer === 'water') check(c, 'water_user_callback_omitted', waterCb.count === 0);
        break;
      default:
        check(c, 'known_control_kind', false, control.kind);
    }
    check(c, 'within_control_deadline_ms', within(rec.timing.elapsed_ms, controlDeadlineMs(control)), { elapsed_ms: rec.timing.elapsed_ms, limit_ms: controlDeadlineMs(control) });
    check(c, 'no_duplicate_completion', rec.completion.duplicates.length === 0);
    if (control.kind !== 'closed_late' && control.kind !== 'malformed') check(c, 'no_late_completion', rec.completion.late.length === 0);
    const sticky = stickyFailures(rec);
    check(c, 'no_sticky_failures', sticky.length === 0, sticky);
    return { result: c.every((x) => x.ok) ? 'PASS' : 'FAIL', checks: c };
  }

  // ---- Browser runner ----

  function b64ToBytes(win, b64) {
    const s = win.atob(b64);
    const out = new Uint8Array(s.length);
    for (let i = 0; i < s.length; i++) out[i] = s.charCodeAt(i);
    return out;
  }
  async function sha256Hex(win, bytes) {
    const d = new Uint8Array(await win.crypto.subtle.digest('SHA-256', bytes));
    return Array.from(d, (b) => b.toString(16).padStart(2, '0')).join('');
  }

  function readCanvasPixel(canvas, x, y) {
    try {
      const d = canvas.getContext('2d').getImageData(x, y, 1, 1).data;
      return [d[0], d[1], d[2], d[3]];
    } catch (e) { return null; }
  }
  function inspectCanvas(canvas) {
    if (!canvas || typeof canvas.width !== 'number') return null;
    const out = { width: canvas.width, height: canvas.height, pixels: null };
    if (canvas.width * canvas.height <= LIMITS.maxCanvasReadPixels && canvas.width > 0 && canvas.height > 0) {
      try {
        const d = canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data;
        out.pixels = Array.from(d);
      } catch (e) { out.read_error = String(e && e.message || e); }
    }
    return out;
  }
  const fromSnapshot = (snap) => function (x, y) {
    if (!snap || !snap.pixels || x >= snap.width || y >= snap.height) return null;
    const i = (y * snap.width + x) * 4;
    return snap.pixels.slice(i, i + 4);
  };

  // The iframe is registered in `owned` before any await, so cleanup removes
  // it even when the script fails or never loads. Setup is bounded by an
  // owned timer. Setup settles exactly once even when releasing that timer
  // throws: the failure is sticky and the id stays owned for cleanup to retry.
  function createRealm(win, enableMipmap, rec, owned, timers, limits) {
    const L = limits || LIMITS;
    return new Promise(function (resolve, reject) {
      let settled = false, id = null;
      const finish = function (fn, value) {
        if (settled) return;
        settled = true;
        try { win.clearTimeout(id); timers.delete(id); } catch (e) {
          rec.failures.push({ kind: 'setup_timer_release', at: rec.now(), detail: String(e && e.message || e).slice(0, 300) });
        }
        fn(value);
      };
      id = win.setTimeout(function () { finish(reject, new Error('realm setup exceeded ' + L.realmSetupMs + 'ms')); }, L.realmSetupMs);
      timers.add(id);
      try {
        const iframe = win.document.createElement('iframe');
        owned.iframe = iframe;
        iframe.src = 'realm.html';
        iframe.width = '64'; iframe.height = '64';
        iframe.onload = function () {
          try {
            const w = iframe.contentWindow;
            owned.win = w;
            w.ROConfig = { enableMipmap: !!enableMipmap };
            w.addEventListener('error', (e) => rec.realm_errors.push({ at: rec.now(), message: String(e.message || e.error) }));
            w.addEventListener('unhandledrejection', (e) => rec.realm_errors.push({ at: rec.now(), message: 'unhandledrejection:' + String(e.reason) }));
            ['error', 'warn'].forEach(function (level) {
              const orig = w.console[level];
              w.console[level] = function () {
                rec.realm_console.push({ at: rec.now(), level, text: Array.prototype.map.call(arguments, String).join(' ').slice(0, 300) });
                return orig.apply(this, arguments);
              };
            });
            const s = w.document.createElement('script');
            s.src = 'production.js';
            s.onload = function () {
              const api = w.__imageConsumerFixtureRealm;
              if (!api) finish(reject, new Error('production.js loaded without realm accessors'));
              else finish(resolve, { iframe, win: w, api });
            };
            s.onerror = function () { finish(reject, new Error('production.js failed to load in realm')); };
            w.document.head.appendChild(s);
          } catch (e) { finish(reject, e); }
        };
        win.document.getElementById('realms').appendChild(iframe);
      } catch (e) { finish(reject, e); }
    });
  }

  function newRecord(ctx, control, consumer) {
    const t0 = ctx.win.performance.now();
    const now = () => Math.round((ctx.win.performance.now() - t0) * 1000) / 1000;
    return {
      schema: SCHEMA, control: control.id, kind: control.kind, consumer, enable_mipmap: control.enableMipmap, url_origin: control.image ? control.url : null,
      now, started_iso: new Date().toISOString(),
      pins: { manifest_sha256: ctx.manifestSha, production_sha256: ctx.manifest && ctx.manifest.production.sha256, driver_sha256: ctx.manifest && ctx.manifest.driver.sha256, fixture: null },
      realm: { kind: 'iframe', fresh: true, configs_enableMipmap: null },
      timing: { submit_at: null, submit_returned_at: null, terminal_at: null, elapsed_ms: null, with_cleanup_ms: null },
      terminal: { state: 'pending', at: null, rewrites_refused: 0 },
      decode: { image_constructed: 0, native_load_events: 0, native_error_events: 0, events: [] },
      completion: null, probes: {}, revokes: [], water_user_callback: { count: 0, texture_non_null: false, arg_count: null },
      upload: { calls: [], generate_mipmap_calls: 0, injected_fault: null },
      ground_draws: [], ground_draw_judge: null,
      gl: { context_lost_before_submit: null, pre_errors: null, consumer_errors: null, context_lost: null, texture_present: null, min_filter: null, fbo_status: null, gpu_unavailable: null, gpu_failures: null, readback_ok: null, diagnostic_errors: null },
      judge: null, realm_errors: [], realm_console: [], failures: [], expectation: null, cleanup: { failures: [] }, exception: null
    };
  }

  function setTerminal(rec, state, reason) {
    if (rec.terminal.state !== 'pending') { rec.terminal.rewrites_refused++; return; }
    rec.terminal.state = state; rec.terminal.at = rec.now(); rec.terminal.reason = reason || null;
  }

  function sleepUntil(ctx, timers, ms, gate, want) {
    return new Promise(function (resolve) {
      const id = ctx.win.setTimeout(function () { timers.delete(id); gate.onSettle = null; resolve(false); }, ms);
      timers.add(id);
      gate.onSettle = function (kind) {
        if (kind !== want) return;
        ctx.win.clearTimeout(id); timers.delete(id); gate.onSettle = null; resolve(true);
      };
    });
  }

  function workerRequest(ctx, worker, msg, timers) {
    return new Promise(function (resolve) {
      const id = ctx.win.setTimeout(function () { timers.delete(id); worker.onmessage = null; resolve(null); }, LIMITS.workerReplyMs);
      timers.add(id);
      worker.onmessage = function (e) { ctx.win.clearTimeout(id); timers.delete(id); worker.onmessage = null; resolve(e.data); };
      worker.postMessage(msg);
    });
  }

  // Each step independently attempts its own release; a throw is recorded as
  // a sticky cleanup failure and the next step still runs.
  async function cleanupOwned(ctx, rec, owned, timers) {
    const cl = rec.cleanup;
    const step = async function (name, fn) {
      try { await fn(); } catch (e) { cl.failures.push({ step: name, error: String(e && e.message || e) }); }
    };
    const urlApi = owned.win && owned.win.URL;
    cl.own_urls_revoked = 0;
    for (const u of owned.urls) await step('revoke_own_url', function () { owned.nativeRevoke.call(urlApi, u); cl.own_urls_revoked++; });
    if (owned.worker) {
      if (owned.workerUrl) await step('worker_url_revoke_ack', async function () {
        const r = await workerRequest(ctx, owned.worker, { op: 'revoke', url: owned.workerUrl }, timers);
        cl.worker_url_revoke_ack = !!(r && r.op === 'revoked');
        if (!cl.worker_url_revoke_ack) throw new Error('no worker revoke ACK');
      });
      await step('worker_terminate', function () { owned.worker.terminate(); cl.worker_terminated = true; });
    }
    if (owned.workerScriptUrl) await step('worker_script_url_revoke', function () { owned.nativeRevoke.call(urlApi, owned.workerScriptUrl); cl.worker_script_url_revoked = true; });
    cl.textures_deleted = 0;
    const gl = owned.gl;
    // Each texture accessor is enumerated in its own step, so a throwing
    // accessor skips only its own texture.
    for (const [name, get] of owned.textures) {
      let t = null;
      await step('enumerate_texture_' + name, function () { t = get(); });
      if (t) await step('delete_texture', function () { if (!gl.isContextLost()) { gl.deleteTexture(t); cl.textures_deleted++; } });
    }
    if (gl) await step('lose_own_context', function () {
      const ext = gl.getExtension('WEBGL_lose_context');
      if (ext && !gl.isContextLost()) { ext.loseContext(); cl.context_lost_by_fixture = true; } else cl.context_lost_by_fixture = false;
    });
    cl.observers_restored = [];
    for (const [name, restore] of owned.restores.slice().reverse()) await step('restore_' + name, function () { if (restore() !== false) cl.observers_restored.push(name); });
    // Every owned timer is released independently. Only a returned
    // clearTimeout removes its bookkeeping; a failed release stays in `timers`
    // and is counted unreleased, never as cleared.
    const ids = Array.from(timers);
    cl.timers_attempted = ids.length;
    cl.timers_cleared = 0;
    for (const id of ids) await step('clear_timer', function () { ctx.win.clearTimeout(id); timers.delete(id); cl.timers_cleared++; });
    cl.timers_unreleased = timers.size;
    if (owned.iframe) await step('remove_realm', function () { owned.iframe.remove(); cl.realm_removed = true; });
  }

  async function runControl(ctx, control, consumer) {
    const rec = newRecord(ctx, control, consumer);
    const L = Object.assign({}, LIMITS, ctx.limits || {});
    const timers = new Set();
    const gate = makeGate(rec.now);
    let realm = null, gl = null, waterTexture = null;
    // Ownership is registered before the first await.
    const owned = {
      iframe: null, win: null, urls: [], worker: null, workerUrl: null, workerScriptUrl: null, nativeRevoke: null, gl: null, restores: [],
      textures: [['ground_atlas', () => (consumer === 'ground' && realm ? realm.api.groundAtlasTexture() : null)], ['water', () => waterTexture]]
    };
    const t0 = rec.now();
    try {
      realm = await createRealm(ctx.win, control.enableMipmap, rec, owned, timers, L);
      const w = realm.win, api = realm.api;
      rec.realm.configs_enableMipmap = api.configs().get('enableMipmap');
      // Transparent realm observers: Image construction/native events, revokes.
      const NativeImage = w.Image;
      w.Image = new Proxy(NativeImage, {
        construct: function (target, args) {
          const img = Reflect.construct(target, args);
          rec.decode.image_constructed++;
          img.addEventListener('load', function () { rec.decode.native_load_events++; rec.decode.events.push({ type: 'load', at: rec.now() }); });
          img.addEventListener('error', function () { rec.decode.native_error_events++; rec.decode.events.push({ type: 'error', at: rec.now() }); });
          return img;
        }
      });
      owned.restores.push(['Image', function () { w.Image = NativeImage; }]);
      const nativeRevoke = owned.nativeRevoke = w.URL.revokeObjectURL;
      const revokeObserver = function (u) {
        rec.revokes.push({ at: rec.now(), seq: gate.seq++, own_url: owned.urls.indexOf(u) >= 0 || u === owned.workerUrl });
        return nativeRevoke.apply(this, arguments);
      };
      w.URL.revokeObjectURL = revokeObserver;
      owned.restores.push(['revokeObjectURL', function () { if (w.URL.revokeObjectURL !== revokeObserver) return false; w.URL.revokeObjectURL = nativeRevoke; return true; }]);
      // Owned WebGL2 context through the unchanged production getContext.
      const canvas = w.document.createElement('canvas');
      canvas.width = 4; canvas.height = 4;
      gl = owned.gl = api.webgl().getContext(canvas);
      const proto = Object.getPrototypeOf(gl);
      const fault = control.kind === 'injected_gl_error' ? injectedFault('owned_observer_injected_invalid_enum_after_texImage2D') : null;
      rec.upload.injected_fault = fault ? { label: fault.label, fired: false } : null;
      installForwardingAdapter(gl, 'texImage2D', proto.texImage2D, recordTexImage2D(gl, rec.upload.calls, rec.now, gate), function (receiver, args, call) {
        // Snapshot a tiny actual upload source after the forwarded call; then any labelled fault.
        const snap = inspectCanvas(args[args.length - 1]);
        if (snap && snap.pixels) rec.upload.last_source_snapshot = snap;
        if (fault) fault.after(receiver, args, call);
      });
      installForwardingAdapter(gl, 'generateMipmap', proto.generateMipmap, function () { rec.upload.generate_mipmap_calls++; return null; });
      // Context-local drawImage observer on the owned ground 2D context.
      if (consumer === 'ground') owned.restores.push(['ground_drawImage', installDrawImageObserver(api.groundContext(), rec.ground_draws, gate)]);
      if (control.kind === 'lose_context') {
        const ext = gl.getExtension('WEBGL_lose_context');
        if (!ext) throw new Error('WEBGL_lose_context unavailable');
        ext.loseContext();
      }
      rec.gl.context_lost_before_submit = gl.isContextLost();
      rec.gl.pre_errors = drainGlErrors(gl);
      // Data: null, page-created Blob URL or owned Worker-created Blob URL.
      let data = null;
      if (control.image) {
        const im = ctx.images[control.image];
        const bytes = b64ToBytes(ctx.win, im.base64);
        const computed = await sha256Hex(ctx.win, bytes);
        rec.pins.fixture = { id: im.id, bytes: bytes.length, sha256: im.sha256, computed_sha256: computed, width: im.width, height: im.height };
        if (computed !== im.sha256 || bytes.length > LIMITS.maxEncodedBytes || bytes.length !== im.bytes) throw new Error('fixture pin mismatch ' + im.id);
        if (control.url === 'worker') {
          const code = "self.onmessage=function(e){var d=e.data;if(d.op==='make'){var u=URL.createObjectURL(new Blob([d.bytes],{type:d.mime}));self.postMessage({op:'made',url:u});}else if(d.op==='revoke'){URL.revokeObjectURL(d.url);self.postMessage({op:'revoked'});}};";
          owned.workerScriptUrl = w.URL.createObjectURL(new w.Blob([code], { type: 'text/javascript' }));
          owned.worker = new w.Worker(owned.workerScriptUrl);
          const made = await workerRequest(ctx, owned.worker, { op: 'make', bytes, mime: im.mime }, timers);
          if (!made || !made.url) throw new Error('owned worker did not create a Blob URL');
          owned.workerUrl = made.url;
          data = owned.workerUrl;
        } else {
          const u = w.URL.createObjectURL(new w.Blob([bytes], { type: im.mime }));
          owned.urls.push(u);
          data = u;
        }
      }
      // Completion observer around the unchanged original Texture.load.
      const textureObj = api.texture();
      const originalLoad = textureObj.load;
      const observedLoad = textureObj.load = observeTextureLoad(originalLoad, gate, inspectCanvas);
      owned.restores.push(['Texture.load', function () { if (textureObj.load !== observedLoad) return false; textureObj.load = originalLoad; return true; }]);
      // Submit exactly one image.
      rec.timing.submit_at = rec.now();
      if (consumer === 'ground') api.initTextures(gl, [data]);
      else api.webgl().texture(gl, data, function (tex) {
        rec.water_user_callback.count++;
        rec.water_user_callback.texture_non_null = tex !== null && tex !== undefined;
        rec.water_user_callback.arg_count = arguments.length;
        waterTexture = tex;
      }, 0);
      rec.timing.submit_returned_at = rec.now();
      if (control.kind === 'closed_late') {
        gate.open = false;
        setTerminal(rec, 'closed_unknown', 'closed synchronously after submit');
        rec.terminal.closed_at = rec.terminal.at;
        if (await sleepUntil(ctx, timers, control.lateWindowMs, gate, 'late')) setTerminal(rec, 'forwarded', 'late completion must not overwrite');
      } else if (gate.forward_count > 0 && gate.events[0].forward_returned_at !== undefined) {
        setTerminal(rec, 'forwarded', 'synchronous completion');
      } else {
        const limit = control.timeoutMs || L.validTimeoutMs;
        const done = await sleepUntil(ctx, timers, limit, gate, 'forwarded');
        if (done) setTerminal(rec, 'forwarded', null);
        else { gate.open = false; setTerminal(rec, 'timeout_unknown_decode', 'no forwarded completion within ' + limit + 'ms'); }
      }
      rec.timing.terminal_at = rec.terminal.at;
      // Independent GL checks first; diagnostic readback errors kept separate.
      rec.gl.consumer_errors = drainGlErrors(gl);
      rec.gl.context_lost = gl.isContextLost();
      if (fault) rec.upload.injected_fault.fired = fault.fired;
      const tex = consumer === 'ground' ? api.groundAtlasTexture() : waterTexture;
      rec.gl.texture_present = !!tex;
      const want = control.expect ? control.expect[consumer] : null;
      const last = rec.upload.calls[rec.upload.calls.length - 1];
      const dims = last ? { width: last.source_width, height: last.source_height } : null;
      if (consumer === 'water' && tex && !rec.gl.context_lost) {
        gl.bindTexture(gl.TEXTURE_2D, tex);
        rec.gl.min_filter = gl.getTexParameter(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER);
        gl.bindTexture(gl.TEXTURE_2D, null);
      }
      let readback = null;
      if (want) {
        readback = readTextureProbes(gl, tex, dims, want.pixels);
        rec.gl.fbo_status = readback.fbo_status;
        rec.gl.gpu_unavailable = readback.unavailable;
        rec.gl.gpu_failures = readback.failures;
        rec.gl.readback_ok = readback.readback_ok;
        rec.probes.gpu = readback.readback_ok ? readback.read : { all_ok: false, rows: readback.read ? readback.read.rows : [], failures: readback.failures };
        // Source probes: the actual uploaded canvas pixels, read after upload.
        const srcCanvas = consumer === 'ground' ? api.groundCanvas() : null;
        if (srcCanvas) rec.probes.upload_source = comparePixels(want.pixels, (x, y) => readCanvasPixel(srcCanvas, x, y));
      }
      rec.gl.diagnostic_errors = drainGlErrors(gl);
      const first = gate.events[0] || gate.late[0];
      if (control.expect && control.expect.completion && first) rec.probes.completion = comparePixels(control.expect.completion.pixels, fromSnapshot(first.canvas));
      if (control.expect && control.expect.preMagenta) rec.probes.pre_magenta = comparePixels(control.expect.preMagenta.pixels, fromSnapshot(inspectCanvas(api.procCanvas3())));
      if (consumer === 'water' && want && rec.upload.last_source_snapshot) rec.probes.upload_source = comparePixels(want.pixels, fromSnapshot(rec.upload.last_source_snapshot));
      if (consumer === 'ground') rec.ground_draw_judge = judgeGroundDraws(rec.ground_draws, rec.upload.calls);
      rec.judge = judgeUpload({ upload_calls: rec.upload.calls.length, consumer_errors: rec.gl.consumer_errors, context_lost: rec.gl.context_lost, texture_present: rec.gl.texture_present, fbo_status: rec.gl.fbo_status, readback, diagnostic_errors: rec.gl.diagnostic_errors });
    } catch (e) {
      rec.exception = String(e && e.stack || e).slice(0, 600);
      rec.failures.push({ kind: 'driver_exception', at: rec.now(), detail: String(e && e.message || e).slice(0, 300) });
    } finally {
      rec.timing.elapsed_ms = Math.round((rec.now() - t0) * 1000) / 1000;
      gate.open = false;
      gate.onSettle = null;
      try { await cleanupOwned(ctx, rec, owned, timers); } catch (e) { rec.cleanup.failures.push({ step: 'cleanup', error: String(e && e.message || e) }); }
      rec.timing.with_cleanup_ms = Math.round((rec.now() - t0) * 1000) / 1000;
    }
    try { rec.completion = projectCompletion(gate); } catch (e) { rec.failures.push({ kind: 'completion_projection', at: rec.now(), detail: String(e && e.message || e) }); }
    if (rec.terminal.state === 'pending') setTerminal(rec, rec.exception ? 'driver_exception' : 'no_terminal', rec.exception ? 'exception before terminal' : null);
    const d = rec.decode;
    d.state = d.image_constructed === 0 ? 'no_native_image' : d.native_load_events > 0 ? 'native_load_observed'
      : d.native_error_events > 0 ? 'native_error_event_observed_consumer_has_no_onerror' : 'unknown_no_native_event';
    try { rec.expectation = evaluateControl(rec, control); } catch (e) {
      rec.expectation = { result: 'FAIL', checks: [{ name: 'evaluation_exception', ok: false, detail: String(e && e.message || e) }] };
    }
    delete rec.now;
    return rec;
  }

  // Runner state is always restored, even when a run or render throws.
  function makeRunner(ctx, ui, run) {
    const runFn = run || runControl;
    return async function runOne(control, consumer) {
      if (ctx.busy || !ctx.manifest) return null;
      ctx.busy = true;
      let rec = null;
      try {
        ui.setDisabled(true);
        ui.setStatus('running', 'running ' + control.id + ' / ' + consumer);
        rec = await runFn(ctx, control, consumer);
      } catch (e) {
        rec = { schema: SCHEMA, control: control.id, kind: control.kind, consumer, terminal: { state: 'runner_exception', at: null, rewrites_refused: 0 },
          timing: { elapsed_ms: null }, exception: String(e && e.message || e).slice(0, 300),
          expectation: { result: 'FAIL', checks: [{ name: 'no_runner_exception', ok: false, detail: String(e && e.message || e).slice(0, 300) }] } };
      } finally {
        if (rec) ctx.records.push(rec);
        ctx.busy = false;
        try { ui.render(); } catch (e) { ctx.render_errors = (ctx.render_errors || 0) + 1; }
        try { ui.setDisabled(false); } catch (e) { ctx.render_errors = (ctx.render_errors || 0) + 1; }
        try { ui.setStatus('ready', 'ready; last ' + control.id + '/' + consumer + ' ' + (rec ? rec.expectation.result : 'none')); } catch (e) { ctx.render_errors = (ctx.render_errors || 0) + 1; }
      }
      return rec;
    };
  }

  function summarizeMatrix(records, elapsedMs) {
    const pass = records.filter((r) => r.expectation && r.expectation.result === 'PASS').length;
    return { elapsed_ms: elapsedMs, budget_ms: LIMITS.matrixBudgetMs, within_budget: within(elapsedMs, LIMITS.matrixBudgetMs), pass, total: records.length,
      result: records.length > 0 && pass === records.length && within(elapsedMs, LIMITS.matrixBudgetMs) ? 'PASS' : 'FAIL' };
  }

  function start(win) {
    const doc = win.document;
    const fixtures = win.__IMAGE_CONSUMER_FIXTURES;
    const ctx = { win, images: {}, manifest: null, manifestSha: null, busy: false, records: [], matrix: null };
    fixtures.images.forEach((im) => { ctx.images[im.id] = im; });
    win.__imageConsumerFixtureRecords = ctx.records;
    const status = doc.getElementById('status');
    const setStatus = (s, text) => { status.dataset.state = s; status.textContent = text || s; doc.body.dataset.state = s; };
    const buttons = [];
    const ui = {
      setStatus,
      setDisabled: (v) => { buttons.forEach((b) => { b.disabled = v; }); },
      render: function () {
        doc.getElementById('records').textContent = JSON.stringify(ctx.records, null, 1);
        doc.getElementById('summary').textContent = JSON.stringify({ matrix: ctx.matrix, records: ctx.records.map((r) => ({ control: r.control, consumer: r.consumer, terminal: r.terminal.state, expectation: r.expectation.result, elapsed_ms: r.timing.elapsed_ms })) }, null, 1);
      }
    };
    const runOne = makeRunner(ctx, ui);
    const box = doc.getElementById('controls');
    fixtures.controls.forEach(function (control) {
      control.consumers.forEach(function (consumer) {
        const b = doc.createElement('button');
        b.textContent = control.id + ' / ' + consumer;
        b.dataset.control = control.id; b.dataset.consumer = consumer;
        b.disabled = true;
        b.addEventListener('click', () => { runOne(control, consumer); });
        box.appendChild(b); buttons.push(b);
      });
    });
    const all = doc.createElement('button');
    all.textContent = 'Run all controls';
    all.dataset.control = 'all';
    all.disabled = true;
    all.addEventListener('click', async function () {
      if (ctx.busy) return;
      const t0 = win.performance.now();
      const from = ctx.records.length;
      for (const control of fixtures.controls) for (const consumer of control.consumers) await runOne(control, consumer);
      ctx.matrix = summarizeMatrix(ctx.records.slice(from), Math.round(win.performance.now() - t0));
      ui.render();
      setStatus('done', 'run-all ' + ctx.matrix.result + ' in ' + ctx.matrix.elapsed_ms + 'ms (budget ' + LIMITS.matrixBudgetMs + 'ms); ' + ctx.matrix.pass + '/' + ctx.matrix.total + ' expected-control PASS');
    });
    box.appendChild(all); buttons.push(all);
    win.__imageConsumerFixtureRun = runOne;
    // Closed manifest check before any control may run.
    (async function () {
      try {
        const mres = await win.fetch('MANIFEST.json', { cache: 'no-store' });
        const mbytes = new Uint8Array(await mres.arrayBuffer());
        ctx.manifestSha = await sha256Hex(win, mbytes);
        const manifest = JSON.parse(new TextDecoder().decode(mbytes));
        const bad = [];
        for (const f of manifest.files) {
          const b = new Uint8Array(await (await win.fetch(f.name, { cache: 'no-store' })).arrayBuffer());
          if (b.length !== f.bytes || await sha256Hex(win, b) !== f.sha256) bad.push(f.name);
        }
        for (const im of manifest.fixture_images) if (!ctx.images[im.id] || ctx.images[im.id].sha256 !== im.sha256) bad.push(im.id);
        if (bad.length) { setStatus('manifest_failed', 'manifest mismatch: ' + bad.join(',')); return; }
        ctx.manifest = manifest;
        buttons.forEach((b) => { b.disabled = false; });
        setStatus('ready', 'ready; manifest ' + ctx.manifestSha.slice(0, 12) + ' verified');
      } catch (e) {
        setStatus('manifest_failed', 'manifest check failed: ' + String(e && e.message || e));
      }
    })();
  }

  return {
    SCHEMA, LIMITS, GL, makeGate, projectCompletion, completionSchemaOk, observeTextureLoad, installForwardingAdapter, recordTexImage2D, injectedFault,
    observeDrawImage, installDrawImageObserver, judgeGroundDraws, drainGlErrors, pixelMatches, comparePixels, judgeUpload, readTextureProbes,
    stickyFailures, evaluateControl, createRealm, cleanupOwned, runControl, makeRunner, summarizeMatrix, start
  };
});
