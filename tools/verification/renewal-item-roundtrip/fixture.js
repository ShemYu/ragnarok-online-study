const EXPECTED = {
  original: '0c70abe66e6978c55886b9e4acf8a491028f3c439abc1324cef183577a3e2f19',
  vendor: '80bed5fb68c5221330af6787629ed651e0b357b0a0f8b2cc8efdcb6a9cc972ee',
  wasm: 'cba969b97e8a319eba8996b5df488aed5cdd22a56f2de53b42598e474014e610'
};
const utf8 = new TextDecoder('utf-8', {fatal:true});
const encoder = new TextEncoder();
const $ = id => document.getElementById(id);
const sha256 = async bytes => [...new Uint8Array(await crypto.subtle.digest('SHA-256', bytes))].map(x => x.toString(16).padStart(2,'0')).join('');
const status = text => { $('status').textContent = text; };
let resources;

async function localBytes(path) {
  const url = new URL(path, location.href);
  if (url.origin !== location.origin || !['http:', 'https:'].includes(url.protocol)) throw new Error('Only same-origin HTTP(S) URLs are allowed');
  const response = await fetch(url, {cache:'no-store', credentials:'omit', redirect:'error'});
  if (!response.ok) throw new Error(`${url.pathname}: HTTP ${response.status}`);
  const bytes = new Uint8Array(await response.arrayBuffer());
  if (bytes.byteLength > 64 * 1024 * 1024) throw new Error('Fixture input exceeds 64 MiB');
  return bytes;
}
async function checked(path, expected) {
  const bytes = await localBytes(path), hash = await sha256(bytes);
  if (hash !== expected) throw new Error(`SHA-256 mismatch for ${path}: ${hash}`);
  return bytes;
}
async function prepare() {
  if (resources) return resources;
  status('Checking original chunk and exact pinned JS/WASM hashes…');
  const original = await checked('./iteminfo_new.lub', EXPECTED.original);
  const vendor = await checked('./vendor/wasmoon-lua5.1.js', EXPECTED.vendor);
  const wasm = await checked('./vendor/liblua5.1.wasm', EXPECTED.wasm);
  const canonicalLua = utf8.decode(await localBytes('./canonical.lua'));
  const jsUrl = URL.createObjectURL(new Blob([vendor], {type:'text/javascript'}));
  const wasmUrl = URL.createObjectURL(new Blob([wasm], {type:'application/wasm'}));
  try {
    // Import verified bytes; explicit verified WASM URL prevents the CDN default.
    const {default: CLua} = await import(jsUrl);
    resources = {original, canonicalLua, CLua, wasmUrl};
  } finally { URL.revokeObjectURL(jsUrl); }
  return resources;
}
async function snapshot(bytes, filename) {
  const {CLua, wasmUrl, canonicalLua} = await prepare();
  const state = await CLua.Lua.create({customWasmUri:wasmUrl, openStandardLibs:true});
  let mounted = false;
  try {
    // No browser/host functions are exposed. This is trusted Lua verification,
    // not a security sandbox for arbitrary hostile source.
    state.doStringSync('tbl = nil; tbl_custom = nil; tbl_override = nil');
    state.mountFile(filename, bytes); mounted = true;
    state.global.setTimeout(Date.now() + 120000);
    state.doFileSync(filename);
    state.doStringSync(canonicalLua);
    const raw = state.doStringSync('return __roundtrip_canonical(tbl)');
    if (!(raw instanceof Uint8Array)) throw new Error('Expected canonical Lua string as Uint8Array');
    const canonical = utf8.decode(raw.slice()); // copy before lua_close frees WASM memory
    if (!/^[\x01-\x7f]*$/.test(canonical)) throw new Error('Canonical output was not NUL-free ASCII');
    return canonical;
  } finally {
    try { if (mounted) state.unmountFile(filename); }
    finally { state.global.close(); }
  }
}
function records(canonical) {
  const [header, ...lines] = canonical.split('\n');
  const counts = Object.fromEntries(header.split(',').map(part => {const [k,v] = part.split('='); return [k,Number(v)];}));
  const entries = new Map();
  for (const line of lines) {
    if (!line) continue;
    const tab = line.indexOf('\t');
    if (tab < 1) throw new Error('Malformed canonical record');
    const key = line.slice(0,tab);
    if (entries.has(key)) throw new Error('Duplicate canonical root key');
    entries.set(key,line.slice(tab+1));
  }
  if (entries.size !== counts.rootEntries) throw new Error('Canonical root count mismatch');
  return {counts, entries};
}
function label(key) {
  if (key.startsWith('s')) {
    const hex = key.slice(1,-1), bytes = Uint8Array.from(hex.match(/../g) || [], x => parseInt(x,16));
    try { return {type:'string', text:utf8.decode(bytes), hex}; }
    catch { return {type:'string', hex}; }
  }
  if (key.startsWith('n')) return {type:'number', value:key.slice(1,-1)};
  return {type:'boolean', value:key === 'b1;'};
}
async function compare(a, b) {
  const left = records(a), right = records(b);
  const onlyOriginal = [], onlyGenerated = [], changed = [];
  for (const [key, value] of left.entries) {
    if (!right.entries.has(key)) onlyOriginal.push(key);
    else if (value !== right.entries.get(key)) changed.push(key);
  }
  for (const key of right.entries.keys()) if (!left.entries.has(key)) onlyGenerated.push(key);
  return {
    exactCanonicalEqual:a === b,
    exactRootRecordsEqual:!onlyOriginal.length && !onlyGenerated.length && !changed.length,
    original:{counts:left.counts, canonicalAsciiBytes:a.length, canonicalSha256:await sha256(encoder.encode(a))},
    generated:{counts:right.counts, canonicalAsciiBytes:b.length, canonicalSha256:await sha256(encoder.encode(b))},
    mismatches:{onlyOriginal:onlyOriginal.length, onlyGenerated:onlyGenerated.length, changed:changed.length,
      preview:[...onlyOriginal.map(key=>({kind:'onlyOriginal',key})), ...onlyGenerated.map(key=>({kind:'onlyGenerated',key})), ...changed.map(key=>({kind:'changed',key}))].slice(0,20).map(({kind,key})=>({kind,key:label(key),
        originalCanonical:left.entries.get(key) ?? null, generatedCanonical:right.entries.get(key) ?? null}))}
  };
}
async function selfChecks() {
  const source = s => snapshot(encoder.encode(s), '/selfcheck.lua');
  const a = 'local s={x="same"}; tbl={[1]="numeric",["1"]="string",[true]=false,[false]=true, unicode="木材 돋보기",nul="a\\000b",hole={[1]="a",[3]="c"},zero=0,negativeZero=-1/math.huge,small=1.2345678901234567,sharedA=s,sharedB=s}';
  const b = 'tbl={sharedB={x="same"},small=1.2345678901234567,negativeZero=-1/math.huge,zero=0,hole={[3]="c",[2]=nil,[1]="a"},nul="a\\000b",unicode="木材 돋보기",[false]=true,[true]=false,["1"]="string",[1]="numeric",sharedA={x="same"},removed=nil}';
  const ca = await source(a), cb = await source(b);
  const parsed = records(ca);
  const stringKey = text => 's' + [...encoder.encode(text)].map(x=>x.toString(16).padStart(2,'0')).join('') + ';';
  const expectedTokens = new Map([
    ['n1;','s6e756d65726963;'], ['s31;','s737472696e67;'], ['b1;','b0;'], ['b0;','b1;'],
    [stringKey('unicode'),'se69ca8e69d9020eb8f8bebb3b4eab8b0;'], [stringKey('nul'),'s610062;'],
    [stringKey('hole'),'t2{n1;s61;n3;s63;}'], [stringKey('zero'),'n0;'],
    [stringKey('negativeZero'),'n-0;'], [stringKey('small'),'n1.2345678901234567;']
  ]);
  for (const [key,value] of expectedTokens) {
    if (parsed.entries.get(key) !== value) throw new Error(`Self-check failed: exact expected token for ${key}`);
  }
  if (parsed.counts.rootEntries !== 12 || parsed.entries.has(stringKey('removed'))) throw new Error('Self-check failed: exact root/nil semantics');
  const equal = await compare(ca, cb);
  if (!equal.exactCanonicalEqual) throw new Error('Self-check failed: key types/order/nil/Unicode/NUL/value expansion');
  const changed = await source(b.replace('[true]=false','[true]=true'));
  if ((await compare(ca,changed)).exactRootRecordsEqual) throw new Error('Self-check failed: changed boolean accepted');
  const rejected = {};
  for (const [name, text] of Object.entries({cycle:'tbl={};tbl.self=tbl',nonfinite:'tbl={x=1/0}',tableKey:'local k={};tbl={[k]=1}'})) {
    try { await source(text); } catch (error) { rejected[name] = String(error.message || error); }
    if (!rejected[name]) throw new Error(`Self-check failed: ${name} was accepted`);
  }
  return {knownTokenAssertions:true, equalTypedReorderedNilUnicodeNul:true, changedBooleanDetected:true, rejected};
}
async function run(onlyTests = false) {
  $('run').disabled = $('test').disabled = true;
  const started = performance.now();
  try {
    await prepare();
    const checks = (onlyTests || $('self-tests').checked) ? await selfChecks() : null;
    if (onlyTests) { status('Fixture self-checks passed. No original table comparison performed.'); $('result').textContent = JSON.stringify({selfChecks:checks},null,2); return; }
    const file = $('source-file').files[0];
    const bytes = file ? new Uint8Array(await file.arrayBuffer()) : await localBytes($('source-url').value.trim());
    if (!bytes.length || bytes.length > 64*1024*1024) throw new Error('Generated source must be 1 byte–64 MiB');
    utf8.decode(bytes); // strict, including all actual string literal UTF-8 bytes
    if (bytes[0] === 27) throw new Error('Generated input must be UTF-8 Lua source, not another binary chunk');
    const sourceHash = await sha256(bytes), expected = $('source-sha').value.trim().toLowerCase();
    if (expected && (!/^[0-9a-f]{64}$/.test(expected) || expected !== sourceHash)) throw new Error(`Generated-source SHA-256 mismatch: ${sourceHash}`);
    status('Executing pinned original in state A, then generated source in separate state B…');
    const original = await snapshot(resources.original, '/original.lub');
    const generated = await snapshot(bytes, '/generated.lua');
    const result = await compare(original, generated);
    result.inputs = {originalSha256:EXPECTED.original, generatedSha256:sourceHash,
      generatedLabel:file?.name || $('source-url').value,
      generatedBytes:bytes.length, pinnedClientCommit:'775f8847a8b09749d03c82fcb554e155401d1e02',
      generatedRuntimeUtf8Heuristic:bytes.some(b=>b>127)};
    result.selfChecks = checks;
    result.elapsedSeconds = (performance.now()-started)/1000;
    result.scope = 'Exact final tbl value equality; no app staging/rendering/asset-path/feature-support proof. Noncyclic aliases expand by value; metatables/cycles/unsupported types rejected.';
    $('result').textContent = JSON.stringify(result,null,2);
    status(result.exactCanonicalEqual && result.exactRootRecordsEqual ? 'PASS: complete final tbl values are exactly equal.' : 'FAIL: complete final tbl values differ.');
  } catch (error) {
    status('ERROR: comparison did not pass.');
    $('result').textContent = JSON.stringify({error:String(error.message || error),stack:error.stack || null},null,2);
  } finally { $('run').disabled = $('test').disabled = false; }
}
$('run').addEventListener('click', () => run(false));
$('test').addEventListener('click', () => run(true));
const source = new URL(location.href).searchParams.get('source');
if (source) $('source-url').value = source;
