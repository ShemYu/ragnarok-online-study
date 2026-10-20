// T06.003.003.006 isolated model constructor worker.
// One worker_threads.Worker per job. Fresh VM context and closed
// SourceTextModule graph. The seven pinned client modules arrive as verified
// text from the parent. SourceTextModule is an execution adapter, not an OS
// memory or security boundary.
import vm from 'node:vm';
import { isMainThread, parentPort, workerData } from 'node:worker_threads';

export const ROLE = 't06-model-constructor-job';
export const MODULE_KEYS = [
  'src/Loaders/Model.js',
  'src/Utils/BinaryReader.js',
  'src/Utils/Struct.js',
  'src/Utils/CodepageManager.js',
  'src/Utils/gl-matrix.js',
  'src/Vendors/gl-matrix.js',
  'src/Vendors/iconv-lite.js'
];
export const RULE_KEYS = [
  'src/Loaders/MapLoader.js',
  'src/Core/FileManager.js',
  'src/Renderer/Map/AnimatedModels.js'
];
export const ENTRY_SOURCE = "import Model from 'Loaders/Model.js';\nexport { Model };\n";
const ENTRY_ID = 'entry:t06-model-constructor';

// Resolve a static specifier to one of the seven keys, or throw.
export function resolveSpecifier(specifier, referrer) {
  if (typeof specifier !== 'string' || specifier.includes('\\') || specifier.includes(':') || specifier.includes('?')) {
    throw new Error(`closed linker refused specifier ${JSON.stringify(String(specifier)).slice(0, 80)}`);
  }
  let parts;
  if (specifier.startsWith('./') || specifier.startsWith('../')) {
    if (referrer === ENTRY_ID) throw new Error('closed linker refused relative entry import');
    parts = referrer.split('/').slice(0, -1).concat(specifier.split('/'));
  } else parts = ['src', ...specifier.split('/')];
  const out = [];
  for (const part of parts) {
    if (part === '.' || part === '') continue;
    if (part === '..') {
      if (out.length <= 1) throw new Error('closed linker refused escaping specifier');
      out.pop();
      continue;
    }
    out.push(part);
  }
  const key = out.join('/');
  if (!MODULE_KEYS.includes(key)) throw new Error(`closed linker refused unknown module ${key.slice(0, 80)}`);
  return key;
}

function boundedConsoleSource(maxBytes) {
  return `(() => { const max = ${Number(maxBytes) | 0}; let used = 0; const lines = []; let dropped = 0;
    const put = (level, args) => { let s; try { s = level + ': ' + args.map(a => String(a)).join(' '); } catch { s = level + ': <unprintable>'; }
      let bytes = 0; for (let i = 0; i < s.length; i++) { const c = s.charCodeAt(i); bytes += c < 0x80 ? 1 : c < 0x800 ? 2 : 3; }
      if (used + bytes + 1 > max) { dropped++; return; } used += bytes + 1; lines.push(s); };
    globalThis.console = { log: (...a) => put('log', a), info: (...a) => put('info', a), warn: (...a) => put('warn', a),
      error: (...a) => put('error', a), debug: (...a) => put('debug', a) };
    globalThis.__t06Logs = () => ({ text: lines.join('\\n'), dropped }); })();`;
}

// Fresh realm. Returns the VM Model constructor and an exact-length copier.
export async function createRealm(sources, { moduleTimeoutMs = 5000, maxLogBytes = 4096 } = {}) {
  for (const key of MODULE_KEYS) if (typeof sources[key] !== 'string') throw new Error(`missing pinned source ${key}`);
  const context = vm.createContext({}, { name: 't06-model-realm', codeGeneration: { strings: false, wasm: false } });
  // self = globalThis so BinaryReader's SEEK_CUR/SET/END land on VM globals as 1/2/3.
  vm.runInContext('globalThis.self = globalThis;', context);
  vm.runInContext(boundedConsoleSource(maxLogBytes), context);
  const dynamicImports = [];
  const refuseDynamic = (specifier) => {
    dynamicImports.push(String(specifier).slice(0, 80));
    throw new Error('closed linker refused dynamic import');
  };
  const cache = new Map();
  const loaded = [];
  const make = (id, text) => new vm.SourceTextModule(text, {
    identifier: id, context, importModuleDynamically: refuseDynamic
  });
  const entry = make(ENTRY_ID, ENTRY_SOURCE);
  await entry.link((specifier, referencing) => {
    const key = resolveSpecifier(specifier, referencing.identifier);
    if (!cache.has(key)) {
      cache.set(key, make(key, sources[key]));
      loaded.push(key);
    }
    return cache.get(key);
  });
  await entry.evaluate({ timeout: moduleTimeoutMs });
  if (loaded.length !== MODULE_KEYS.length || MODULE_KEYS.some((key) => !loaded.includes(key))) {
    throw new Error('closed linker loaded a different module set');
  }
  const Model = entry.namespace.Model;
  if (typeof Model !== 'function') throw new Error('Model export missing');
  return {
    context, Model, loaded, dynamicImports,
    seekGlobals: vm.runInContext('[globalThis.SEEK_CUR, globalThis.SEEK_SET, globalThis.SEEK_END]', context),
    logs: () => vm.runInContext('__t06Logs()', context),
    // Exact-length ArrayBuffer allocated inside the VM realm.
    exactBuffer(bytes) {
      const buffer = vm.runInContext(`new ArrayBuffer(${bytes.length | 0})`, context);
      new Uint8Array(buffer).set(bytes);
      return buffer;
    },
    // Same-realm Uint8Array with a leading pad. BinaryReader reads mixed.buffer
    // from offset 0, so the pad becomes the header. Adapter hazard only.
    offsetView(bytes, offset, padByte = 0) {
      const buffer = vm.runInContext(`new ArrayBuffer(${(bytes.length + offset * 2) | 0})`, context);
      const all = new Uint8Array(buffer);
      all.fill(padByte);
      all.set(bytes, offset);
      return vm.runInContext('(b, o, n) => new Uint8Array(b, o, n)', context)(buffer, offset, bytes.length);
    },
    construct(arg, timeoutMs) {
      context.__t06Ctor = Model;
      context.__t06Arg = arg;
      try {
        return new vm.Script('new __t06Ctor(__t06Arg)', { importModuleDynamically: refuseDynamic })
          .runInContext(context, { timeout: timeoutMs });
      } finally {
        delete context.__t06Ctor;
        delete context.__t06Arg;
      }
    }
  };
}

export function boundedException(error, phase, maxChars) {
  let name = 'Unknown';
  let message = '';
  try { name = String(error && error.name || typeof error); } catch { /* keep Unknown */ }
  try { message = String(error && error.message !== undefined ? error.message : error); } catch { message = '<unprintable>'; }
  return {
    phase,
    name: name.slice(0, 64),
    message: message.slice(0, maxChars),
    message_truncated: message.length > maxChars,
    code: error && typeof error.code === 'string' ? error.code.slice(0, 64) : null
  };
}

// SummaryLimitError is a cap, never a truncated complete dependency list.
export function outcomeForSummaryThrow(error) {
  return error && error.name === 'SummaryLimitError' ? 'summary_limit' : 'summary_error';
}

function isTimeout(error) { return error && error.code === 'ERR_SCRIPT_EXECUTION_TIMEOUT'; }

function vmBudget(cap, remaining) {
  const value = Math.floor(Math.min(cap, remaining));
  if (value < 1) throw Object.assign(new Error('job budget exhausted before VM invocation'), { code: 'ERR_SCRIPT_EXECUTION_TIMEOUT' });
  return value;
}

async function runJob(data) {
  const post = (message) => parentPort.postMessage(message);
  const policy = data.policy;
  const started = performance.now();
  const remaining = () => data.budget_ms - (performance.now() - started);
  const maxChars = policy.max_exception_message_chars;
  let realm;
  post({ type: 'phase', phase: 'module' });
  try {
    const summaryModule = await import(`data:text/javascript;base64,${Buffer.from(data.summary_text, 'utf8').toString('base64')}`);
    if (typeof summaryModule.summarizeModel !== 'function') throw new Error('summary export missing');
    realm = await createRealm(data.sources, {
      moduleTimeoutMs: vmBudget(policy.module_timeout_ms, remaining()),
      maxLogBytes: policy.max_job_log_bytes
    });
    if (!Array.isArray(realm.seekGlobals) || realm.seekGlobals.length !== 3) throw new Error('SEEK globals missing');
    realm.summarize = summaryModule.summarizeModel;
  } catch (error) {
    post({
      type: 'result',
      outcome: isTimeout(error) ? 'timeout' : 'environment_failure',
      constructor_returned: null,
      exception: boundedException(error, 'module', maxChars)
    });
    return;
  }
  const bytes = new Uint8Array(data.body);
  const buffer = realm.exactBuffer(bytes);
  if (buffer.byteLength !== bytes.length) throw new Error('exact buffer length mismatch');
  let constructorBudget;
  try { constructorBudget = vmBudget(policy.constructor_timeout_ms, remaining()); }
  catch (error) {
    post({ type: 'result', outcome: 'timeout', constructor_returned: null,
      exception: boundedException(error, 'constructor_budget', maxChars),
      log: realm.logs(), dynamic_imports: realm.dynamicImports,
      loaded_module_keys: realm.loaded, seek_globals: realm.seekGlobals });
    return;
  }
  let value;
  post({ type: 'phase', phase: 'constructor' });
  const t0 = performance.now();
  try {
    value = realm.construct(buffer, constructorBudget);
  } catch (error) {
    post({
      type: 'result',
      outcome: isTimeout(error) ? 'timeout' : 'constructor_exception',
      constructor_returned: isTimeout(error) ? null : false,
      constructor_ms: performance.now() - t0,
      exception: boundedException(error, 'constructor', maxChars),
      log: realm.logs(),
      dynamic_imports: realm.dynamicImports,
      loaded_module_keys: realm.loaded,
      seek_globals: realm.seekGlobals
    });
    return;
  }
  const constructorMs = performance.now() - t0;
  post({ type: 'phase', phase: 'summary' });
  let json;
  try {
    json = JSON.stringify(realm.summarize(value));
  } catch (error) {
    post({
      type: 'result',
      outcome: outcomeForSummaryThrow(error),
      constructor_returned: true,
      constructor_ms: constructorMs,
      exception: boundedException(error, 'summary', maxChars),
      log: realm.logs(),
      dynamic_imports: realm.dynamicImports,
      loaded_module_keys: realm.loaded,
      seek_globals: realm.seekGlobals
    });
    return;
  }
  const jsonBytes = Buffer.byteLength(json, 'utf8');
  if (jsonBytes > policy.max_job_json_bytes) {
    post({
      type: 'result',
      outcome: 'summary_limit',
      constructor_returned: true,
      constructor_ms: constructorMs,
      summary_json_bytes: jsonBytes,
      limit: 'max_job_json_bytes',
      log: realm.logs(),
      dynamic_imports: realm.dynamicImports,
      loaded_module_keys: realm.loaded,
      seek_globals: realm.seekGlobals
    });
    return;
  }
  post({
    type: 'result',
    outcome: 'returned',
    constructor_returned: true,
    constructor_ms: constructorMs,
    summary_json: json,
    summary_json_bytes: jsonBytes,
    log: realm.logs(),
    dynamic_imports: realm.dynamicImports,
    loaded_module_keys: realm.loaded,
    seek_globals: realm.seekGlobals
  });
}

if (!isMainThread && workerData && workerData.role === ROLE) {
  runJob(workerData).then(() => {
    // Flush the result message, then exit 0. The parent must see this exit
    // and must not terminate a normal returned/constructor_exception worker.
    setImmediate(() => process.exit(0));
  }, (error) => {
    try {
      parentPort.postMessage({
        type: 'result',
        outcome: 'worker_error',
        constructor_returned: null,
        exception: boundedException(error, 'worker', workerData.policy.max_exception_message_chars)
      });
    } catch { /* parent may already be gone */ }
    setImmediate(() => process.exit(1));
  });
}
