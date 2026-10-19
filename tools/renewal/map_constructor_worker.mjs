// T06.003.003.003 isolated constructor worker. One worker_threads.Worker per job.
// Fresh VM context and closed SourceTextModule graph per job; the nine pinned
// client modules arrive as verified text from the parent. This is an execution
// adapter, not a security or memory sandbox.
import vm from 'node:vm';
import { isMainThread, parentPort, workerData } from 'node:worker_threads';

export const MODULE_KEYS = [
  'src/Loaders/World.js', 'src/Loaders/Ground.js', 'src/Loaders/Altitude.js',
  'src/Utils/BinaryReader.js', 'src/Utils/Struct.js', 'src/Utils/CodepageManager.js',
  'src/Utils/gl-matrix.js', 'src/Vendors/gl-matrix.js', 'src/Vendors/iconv-lite.js'
];
export const ENTRY_SOURCE = "import World from 'Loaders/World.js';\n" +
  "import Ground from 'Loaders/Ground.js';\nimport Altitude from 'Loaders/Altitude.js';\n" +
  'export { World, Ground, Altitude };\n';
export const CONSTRUCTOR_FOR_KIND = { rsw: 'World', gnd: 'Ground', gat: 'Altitude' };
const ENTRY_ID = 'entry:t06-constructors';

// Resolve a static specifier to one of the nine keys or throw (closed linker).
export function resolveSpecifier(specifier, referrer) {
  if (typeof specifier !== 'string' || specifier.includes('\\') || specifier.includes(':')) {
    throw new Error(`closed linker refused specifier ${JSON.stringify(String(specifier)).slice(0, 80)}`);
  }
  let parts;
  if (specifier.startsWith('./') || specifier.startsWith('../')) {
    if (referrer === ENTRY_ID) throw new Error('closed linker refused relative entry import');
    parts = referrer.split('/').slice(0, -1).concat(specifier.split('/'));
  } else {
    parts = ['src', ...specifier.split('/')];
  }
  const out = [];
  for (const p of parts) {
    if (p === '.' || p === '') continue;
    if (p === '..') { if (out.length <= 1) throw new Error('closed linker refused escaping specifier'); out.pop(); continue; }
    out.push(p);
  }
  const key = out.join('/');
  if (!MODULE_KEYS.includes(key)) throw new Error(`closed linker refused unknown module ${key.slice(0, 80)}`);
  return key;
}

function boundedConsoleSource(maxBytes) {
  // Defined inside the VM realm; host only reads the joined string afterwards.
  return `(() => { const max = ${Number(maxBytes) | 0}; let used = 0; const lines = []; let dropped = 0;
    const put = (level, args) => { let s; try { s = level + ': ' + args.map(a => String(a)).join(' '); } catch { s = level + ': <unprintable>'; }
      if (used + s.length + 1 > max) { dropped++; return; } used += s.length + 1; lines.push(s); };
    globalThis.console = { log: (...a) => put('log', a), info: (...a) => put('info', a), warn: (...a) => put('warn', a),
      error: (...a) => put('error', a), debug: (...a) => put('debug', a) };
    globalThis.__t06Logs = () => ({ text: lines.join('\\n'), dropped }); })();`;
}

// Build a fresh realm with the closed module graph. Returns VM-realm constructors.
export async function createRealm(sources, { moduleTimeoutMs = 5000, maxLogBytes = 4096 } = {}) {
  for (const k of MODULE_KEYS) if (typeof sources[k] !== 'string') throw new Error(`missing pinned source ${k}`);
  const context = vm.createContext({}, { name: 't06-constructor-realm', codeGeneration: { strings: false, wasm: false } });
  // self=globalThis so BinaryReader's SEEK_* writes land on actual VM globals.
  vm.runInContext('globalThis.self = globalThis;', context);
  vm.runInContext(boundedConsoleSource(maxLogBytes), context);
  const dynamicImports = [];
  const refuseDynamic = (specifier) => {
    dynamicImports.push(String(specifier).slice(0, 80));
    throw new Error('closed linker refused dynamic import');
  };
  const cache = new Map();
  const make = (id, text) => new vm.SourceTextModule(text, { identifier: id, context, importModuleDynamically: refuseDynamic });
  const entry = make(ENTRY_ID, ENTRY_SOURCE);
  const loaded = [];
  await entry.link((specifier, referencing) => {
    const key = resolveSpecifier(specifier, referencing.identifier);
    if (!cache.has(key)) { cache.set(key, make(key, sources[key])); loaded.push(key); }
    return cache.get(key);
  });
  await entry.evaluate({ timeout: moduleTimeoutMs });
  const ns = entry.namespace;
  return {
    context, World: ns.World, Ground: ns.Ground, Altitude: ns.Altitude, loaded, dynamicImports,
    seekGlobals: vm.runInContext('[globalThis.SEEK_CUR, globalThis.SEEK_SET, globalThis.SEEK_END]', context),
    logs: () => vm.runInContext('__t06Logs()', context),
    // Exact-length same-realm ArrayBuffer containing a copy of bytes.
    exactBuffer(bytes) {
      const buf = vm.runInContext(`new ArrayBuffer(${bytes.length | 0})`, context);
      new Uint8Array(buf).set(bytes);
      return buf;
    },
    // VM-realm Uint8Array view at an offset inside a larger buffer (hazard control only).
    offsetView(bytes, offset, padByte = 0) {
      const buf = vm.runInContext(`new ArrayBuffer(${(bytes.length + offset * 2) | 0})`, context);
      const all = new Uint8Array(buf); all.fill(padByte); all.set(bytes, offset);
      return vm.runInContext(`(b, o, n) => new Uint8Array(b, o, n)`, context)(buf, offset, bytes.length);
    },
    construct(name, arg, timeoutMs) {
      context.__t06Ctor = ns[name]; context.__t06Arg = arg;
      try {
        return new vm.Script('new __t06Ctor(__t06Arg)', { importModuleDynamically: refuseDynamic })
          .runInContext(context, { timeout: timeoutMs });
      } finally { delete context.__t06Ctor; delete context.__t06Arg; }
    }
  };
}

export function boundedException(error, phase, maxChars) {
  let name = 'Unknown', message = '';
  try { name = String(error && error.name || typeof error); } catch {}
  try { message = String(error && error.message !== undefined ? error.message : error); } catch { message = '<unprintable>'; }
  const truncated = message.length > maxChars;
  return { phase, name: name.slice(0, 64), message: message.slice(0, maxChars), message_truncated: truncated,
    code: error && typeof error.code === 'string' ? error.code.slice(0, 64) : null };
}

function isTimeout(error) { return error && error.code === 'ERR_SCRIPT_EXECUTION_TIMEOUT'; }

async function runJob(data) {
  const post = (m) => parentPort.postMessage(m);
  const p = data.policy;
  const now = () => Date.now();
  const remaining = () => Math.max(1, data.deadline_epoch_ms - now());
  const maxChars = p.max_exception_message_chars;
  let realm;
  post({ type: 'phase', phase: 'module' });
  try {
    const summaryModule = await import('data:text/javascript;base64,' + Buffer.from(data.summary_text, 'utf8').toString('base64'));
    if (typeof summaryModule.summarizeConstructor !== 'function') throw new Error('summary export missing');
    realm = await createRealm(data.sources, { moduleTimeoutMs: Math.min(p.module_timeout_ms, remaining()), maxLogBytes: p.max_job_log_bytes });
    realm.summarize = summaryModule.summarizeConstructor;
  } catch (error) {
    post({ type: 'result', outcome: isTimeout(error) ? 'timeout' : 'environment_failure', constructor_returned: null,
      exception: boundedException(error, 'module', maxChars) });
    return;
  }
  const bytes = new Uint8Array(data.body);
  const buffer = realm.exactBuffer(bytes);
  const name = CONSTRUCTOR_FOR_KIND[data.kind];
  let value;
  post({ type: 'phase', phase: 'constructor' });
  const t0 = performance.now();
  try {
    value = realm.construct(name, buffer, Math.min(p.constructor_timeout_ms, remaining()));
  } catch (error) {
    post({ type: 'result', outcome: isTimeout(error) ? 'timeout' : 'constructor_exception', constructor_returned: false,
      constructor_ms: performance.now() - t0, exception: boundedException(error, 'constructor', maxChars), log: realm.logs(),
      dynamic_imports: realm.dynamicImports });
    return;
  }
  const constructorMs = performance.now() - t0;
  post({ type: 'phase', phase: 'summary' });
  let json;
  try {
    json = JSON.stringify(realm.summarize(data.kind, value));
  } catch (error) {
    post({ type: 'result', outcome: 'summary_error', constructor_returned: true, constructor_ms: constructorMs,
      exception: boundedException(error, 'summary', maxChars), log: realm.logs(), dynamic_imports: realm.dynamicImports });
    return;
  }
  const jsonBytes = Buffer.byteLength(json, 'utf8');
  if (jsonBytes > p.max_job_json_bytes) {
    post({ type: 'result', outcome: 'summary_limit', constructor_returned: true, constructor_ms: constructorMs,
      summary_json_bytes: jsonBytes, limit: 'max_job_json_bytes', log: realm.logs(), dynamic_imports: realm.dynamicImports });
    return;
  }
  post({ type: 'result', outcome: 'returned', constructor_returned: true, constructor_ms: constructorMs,
    summary_json: json, summary_json_bytes: jsonBytes, log: realm.logs(), dynamic_imports: realm.dynamicImports,
    seek_globals: realm.seekGlobals });
}

if (!isMainThread && workerData && workerData.role === 't06-constructor-job') {
  runJob(workerData).catch((error) => {
    parentPort.postMessage({ type: 'result', outcome: 'worker_error', constructor_returned: null,
      exception: boundedException(error, 'worker', workerData.policy.max_exception_message_chars) });
  });
}
