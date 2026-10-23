"""Reconstruct fixed Lua-diagnostic source bytes without executing the result.

The API performs closed byte substitutions and inverse checks only. Returned
actor headers retain consumed root4 bindings for lineage and require fresh binding
before any execution. It does not admit a browser trial or validate runtime Lua.
"""
import base64
import hashlib
import json
import re

INPUT_PINS = {'online': (13191909, '8e47a19f5fd32d6aa6056e8d047b1742ebe8c2536a5db37af2057b4fcc6bf728'), 'proxy': (46202, '90c3503804b047d5de437bf4598ce71dc580a4ce46bb052e57d011ccee505b7e'), 'controller': (47013, '2f1bbea7accd6e9d497ddd7f17679d7aa70f024d2fc3cebf29c160a5f4c241e2'), 'tail': (15211, '0eb63300b03b9ed9fc49b18fbb329a80f4f2f3aee1439c98b20a89f2168d9508')}
OUTPUT_PINS = {'tail': (17196, 'c4c707b68bd757f89bb5a9ad8d5327c6decef97f89aa01f7bc5baae24134fc07'), 'proxy': (46357, 'c0747c05206ba295b10b92ed26317e121db82cf599df545c55c2c198d14c1c6f'), 'controller': (47815, 'a64a7565aa371ac94b9dc0e82d4e1337d7b3c0d723abc12f47b158568aeec2df'), 'online': (12922168, '464be876aff327aef5e5d82c0284d63ac9fe7367cc5131592c1ffbdb889a08eb'), 'wasm': (203782, 'cba969b97e8a319eba8996b5df488aed5cdd22a56f2de53b42598e474014e610')}
TAIL_EDITS = (('bounded-original-startup-detail', b'\tfunction Refused(code) {\n\t\tthis.code = code;\n\t}\n', b"\tfunction Refused(code) {\n\t\tthis.code = code;\n\t}\n\n\tfunction startupClip(text, limit) {\n\t\tlet end = Math.min(text.length, limit);\n\t\tif (end > 0 && end < text.length) {\n\t\t\tconst last = text.charCodeAt(end - 1), next = text.charCodeAt(end);\n\t\t\tif (last >= 0xd800 && last <= 0xdbff && next >= 0xdc00 && next <= 0xdfff) end--;\n\t\t}\n\t\treturn text.slice(0, end);\n\t}\n\n\tfunction startupDetail(value) {\n\t\ttry {\n\t\t\tlet text;\n\t\t\tif (typeof value === 'string') {\n\t\t\t\tif (value.length > 4096) return '[oversize-string]';\n\t\t\t\ttext = value;\n\t\t\t} else if (value !== null && (typeof value === 'object' || typeof value === 'function')) {\n\t\t\t\tconst parts = [];\n\t\t\t\tfor (const key of ['name', 'message']) {\n\t\t\t\t\tconst descriptor = Object.getOwnPropertyDescriptor(value, key);\n\t\t\t\t\tif (descriptor === undefined) parts.push('[missing]');\n\t\t\t\t\telse if (!Object.hasOwn(descriptor, 'value')) parts.push('[accessor-omitted]');\n\t\t\t\t\telse if (typeof descriptor.value !== 'string') parts.push('[non-string]');\n\t\t\t\t\telse {\n\t\t\t\t\t\tif (descriptor.value.length > 4096) return '[oversize-string]';\n\t\t\t\t\t\tparts.push(descriptor.value);\n\t\t\t\t\t}\n\t\t\t\t}\n\t\t\t\tif (parts[0].length + parts[1].length + 15 > 4096) return '[oversize-summary]';\n\t\t\t\ttext = 'name=' + parts[0] + '; message=' + parts[1];\n\t\t\t} else return '[uninspectable-rejection]';\n\t\t\tif (text.length === 0) return '[empty-string]';\n\t\t\tconst dataAt = text.search(/data:/i);\n\t\t\tif (dataAt !== -1) text = text.slice(0, dataAt) + '[data omitted]';\n\t\t\ttext = text.replace(/[\\u0000-\\u001f\\u007f]/g, ' ');\n\t\t\treturn startupClip(text, 256);\n\t\t} catch (_) {\n\t\t\t// Proxy reflection may already have run unknown code; retain only a marker.\n\t\t\treturn '[reflection-failed]';\n\t\t}\n\t}\n\n\tlet startupFailureDetail = null;\n"), ('append-detail-without-truncating-reasons', b"\t\tconst error = new Error('T10.005 diagnostic refused: ' + reasons.join(', '));\n", b"\t\tconst message = 'T10.005 diagnostic refused: ' + reasons.join(', ');\n\t\tconst error = new Error(message);\n\t\tconst separator = ' | startLua: ';\n\t\tconst remaining = 512 - message.length - separator.length;\n\t\tif (startupFailureDetail !== null && remaining > 0)\n\t\t\terror.message = message + separator + startupClip(startupFailureDetail, remaining);\n"), ('capture-before-preserving-refusal', b"\t\t} catch (error) {\n\t\t\tthrow new Refused('startLua-rejected');\n\t\t}\n", b"\t\t} catch (error) {\n\t\t\tstartupFailureDetail = startupDetail(error);\n\t\t\tthrow new Refused('startLua-rejected');\n\t\t}\n"))
PROXY_EDITS = (('pin-derived-wasm-file', b"SERVED_PINS = {'ThreadEventHandler.js':(650825,'db6f0ed37c40fea30c2e513e31468ca657d5b3dca5570837375d66fd5ba205ba'),\n               'PathFindingWorker.js':(5291,'e3b5db57a3cfd1bb83daf9a49fa656af18fda470b34807c0f52cbc65b503c85d')}", b"SERVED_PINS = {'ThreadEventHandler.js':(650825,'db6f0ed37c40fea30c2e513e31468ca657d5b3dca5570837375d66fd5ba205ba'),\n               'PathFindingWorker.js':(5291,'e3b5db57a3cfd1bb83daf9a49fa656af18fda470b34807c0f52cbc65b503c85d'),\n               'liblua5.1.wasm':(203782,'cba969b97e8a319eba8996b5df488aed5cdd22a56f2de53b42598e474014e610')}"), ('six-static-files', b"STATIC = {'viewer_QUEST.html':'text/html','bootstrap_QUEST.js':'text/javascript',\n          'Online.js':'text/javascript','ThreadEventHandler.js':'text/javascript','PathFindingWorker.js':'text/javascript'}", b"STATIC = {'viewer_QUEST.html':'text/html','bootstrap_QUEST.js':'text/javascript',\n          'Online.js':'text/javascript','ThreadEventHandler.js':'text/javascript','PathFindingWorker.js':'text/javascript',\n          'liblua5.1.wasm':'application/wasm'}"), ('six-route-diagnostic', b"need(set(binding['served'])==set(STATIC),'five served quest routes'); static={}", b"need(set(binding['served'])==set(STATIC),'six served quest routes'); static={}"))
CONTROLLER_EDITS = (('fixed-wasm-route', b"const fixedGET=new Set(['/viewer_QUEST.html','/bootstrap_QUEST.js','/Online.js','/ThreadEventHandler.js','/PathFindingWorker.js','/favicon.ico','/_root/budget']);", b"const fixedGET=new Set(['/viewer_QUEST.html','/bootstrap_QUEST.js','/Online.js','/ThreadEventHandler.js','/PathFindingWorker.js','/favicon.ico','/_root/budget','/liblua5.1.wasm']);"), ('page-only-wasm-manifest', b"  if(['/_root/budget','/_viewer/report','/_viewer/failure'].includes(row.path))need(row.sessions.length===1&&row.sessions[0]==='page','fixed main route');", b"  if(['/_root/budget','/_viewer/report','/_viewer/failure','/liblua5.1.wasm'].includes(row.path))need(row.sessions.length===1&&row.sessions[0]==='page','fixed main route');"), ('maximum-observed-wasm-chains', b"    need(verb===rule.method&&rule.sessions.includes(role),'quest route method/session');need(!p.redirectResponse&&!requests.has(key)&&requests.size<LIMIT.requests,'redirect/duplicate/request cap');\n", b"    need(verb===rule.method&&rule.sessions.includes(role),'quest route method/session');need(!p.redirectResponse&&!requests.has(key)&&requests.size<LIMIT.requests,'redirect/duplicate/request cap');\n    if(u===cfg.fixtureOrigin+'/liblua5.1.wasm'){controlCheck();need([...requests.values()].filter(r=>r.url===u).length<10,'Wasm request cap');}\n"), ('wasm-terminal-deadline-fence', b"    need(requests.has(key)&&!terminals.has(key),'unmatched/duplicate terminal chain');\n", b"    need(requests.has(key)&&!terminals.has(key),'unmatched/duplicate terminal chain');\n    if(requests.get(key).url===cfg.fixtureOrigin+'/liblua5.1.wasm')controlCheck();\n"), ('genuine-wasm-mime', b"      const request=requests.get(key);need(!responses.has(key)&&p.response?.url===request.url&&Number.isInteger(p.response.status)&&request.statuses.includes(p.response.status)&&typeof p.response.mimeType==='string'&&p.response.mimeType.length<=256&&typeof p.response.protocol==='string'&&p.response.protocol.length<=64,'response metadata/admitted status');\n", b"      const request=requests.get(key);need(!responses.has(key)&&p.response?.url===request.url&&Number.isInteger(p.response.status)&&request.statuses.includes(p.response.status)&&typeof p.response.mimeType==='string'&&p.response.mimeType.length<=256&&typeof p.response.protocol==='string'&&p.response.protocol.length<=64,'response metadata/admitted status');\n      if(request.url===cfg.fixtureOrigin+'/liblua5.1.wasm')need(request.sid===pageSessionId&&request.method==='GET'&&p.response.status===200&&p.response.mimeType==='application/wasm','Wasm response metadata');\n"), ('minimum-after-failure-publication-guard', b'  result.completionFence=true;finish(null);\n', b"  const wasmRows=[...requests].filter(([,r])=>r.url===cfg.fixtureOrigin+'/liblua5.1.wasm');\n  need(wasmRows.length>=1&&wasmRows.length<=10&&wasmRows.every(([k,r])=>r.sid===pageSessionId&&r.method==='GET'&&responseStatuses.get(k)===200&&terminalMethods.get(k)==='Network.loadingFinished'),'one through ten complete Wasm chains');\n  result.completionFence=true;finish(null);\n"))
PROOF = {'schema': 't10.005.lua-startup-source-patch.v1', 'source_only': True, 'runtime_admitted': False, 'source_pins': {'online': {'bytes': 13191909, 'sha256': '8e47a19f5fd32d6aa6056e8d047b1742ebe8c2536a5db37af2057b4fcc6bf728'}, 'proxy': {'bytes': 46202, 'sha256': '90c3503804b047d5de437bf4598ce71dc580a4ce46bb052e57d011ccee505b7e'}, 'controller': {'bytes': 47013, 'sha256': '2f1bbea7accd6e9d497ddd7f17679d7aa70f024d2fc3cebf29c160a5f4c241e2'}, 'tail': {'bytes': 15211, 'sha256': '0eb63300b03b9ed9fc49b18fbb329a80f4f2f3aee1439c98b20a89f2168d9508'}}, 'output_pins': {'tail': {'bytes': 17196, 'sha256': 'c4c707b68bd757f89bb5a9ad8d5327c6decef97f89aa01f7bc5baae24134fc07'}, 'proxy': {'bytes': 46357, 'sha256': 'c0747c05206ba295b10b92ed26317e121db82cf599df545c55c2c198d14c1c6f'}, 'controller': {'bytes': 47815, 'sha256': 'a64a7565aa371ac94b9dc0e82d4e1337d7b3c0d723abc12f47b158568aeec2df'}, 'online': {'bytes': 12922168, 'sha256': '464be876aff327aef5e5d82c0284d63ac9fe7367cc5131592c1ffbdb889a08eb'}, 'wasm': {'bytes': 203782, 'sha256': 'cba969b97e8a319eba8996b5df488aed5cdd22a56f2de53b42598e474014e610'}}, 'wasm': {'wire': '/liblua5.1.wasm', 'mime': 'application/wasm', 'bytes': 203782, 'sha256': 'cba969b97e8a319eba8996b5df488aed5cdd22a56f2de53b42598e474014e610', 'uri_bytes': 271741, 'uri_sha256': 'cdf4e614af8870d38d5d3e9492f8b3dfebdf81266dea5e51f70edb0e7f6e8989', 'uri_byte_start': 9714238, 'uri_byte_end_exclusive': 9985979, 'uri_count': 1}, 'original_tail_join': {'byte_start': 13176661, 'byte_end_exclusive': 13191872, 'full_tail_occurrences': 1}, 'literal_edit_counts': {'online': 2, 'proxy': 3, 'controller': 6, 'tail': 3}, 'all_full_inverses_required': True, 'static_file_count': 6, 'existing_source_roles': 7, 'observed_wasm_chain_admission': [1, 10], 'observed_count_is_not_source_fetch_proof': True, 'original_normal_source_and_csp_unchanged': True, 'binding_headers_unchanged_consumed_root4_only': True}

def _need(condition, code):
    if not condition:
        raise ValueError(code)


def _pin(raw):
    _need(type(raw) is bytes, 'exact-bytes-required')
    return len(raw), hashlib.sha256(raw).hexdigest()


def _expect(raw, expected):
    _need(_pin(raw) == expected, 'fixed-full-source-pin')
    return raw


def _edits(raw, changes, inverse=False):
    for _, old, new in (reversed(changes) if inverse else changes):
        if inverse:
            old, new = new, old
        _need(raw.count(old) == 1, 'closed-literal-count')
        if not inverse:
            _need(new not in raw, 'closed-new-literal-absent')
        raw = raw.replace(old, new, 1)
    return raw


def _wasm(original_online):
    _expect(original_online, INPUT_PINS['online'])
    matches = re.findall(rb'data:application/wasm;base64,[A-Za-z0-9+/=]+', original_online)
    _need(len(matches) == 1, 'sole-canonical-wasm-uri')
    uri = matches[0]
    _need(_pin(uri) == (271741, 'cdf4e614af8870d38d5d3e9492f8b3dfebdf81266dea5e51f70edb0e7f6e8989'), 'uri-full-pin')
    encoded = uri.split(b',', 1)[1]
    body = base64.b64decode(encoded, validate=True)
    _need(base64.b64encode(body) == encoded and body[:8] == b'\x00asm\x01\x00\x00\x00', 'canonical-base64-wasm1')
    _expect(body, OUTPUT_PINS['wasm'])
    return uri, body


def apply_quest_lua_startup_patch(online, proxy, controller, tail):
    """Return five inert byte artifacts plus bounded source-only proof metadata."""
    original = dict(online=online, proxy=proxy, controller=controller, tail=tail)
    for role, raw in original.items():
        _expect(raw, INPUT_PINS[role])
    uri, wasm = _wasm(online)
    patched_tail = _edits(tail, TAIL_EDITS)
    quoted, route = b'"' + uri + b'"', b'"/liblua5.1.wasm"'
    _need(online.count(quoted) == 1 and route not in online and online.count(tail) == 1, 'exact-online-joins')
    patched_online = online.replace(quoted, route, 1).replace(tail, patched_tail, 1)
    result = dict(online=patched_online, proxy=_edits(proxy, PROXY_EDITS),
                  controller=_edits(controller, CONTROLLER_EDITS), tail=patched_tail, wasm=wasm)
    for role, raw in result.items():
        _expect(raw, OUTPUT_PINS[role])
    result['proof'] = json.loads(json.dumps(PROOF))
    _need(inverse_quest_lua_startup_patch(result, online) == original, 'full-source-inverse')
    return result


def inverse_quest_lua_startup_patch(patched, original_online):
    """Reverse exact output bytes using the pinned original URI, never rewritten code."""
    _need(type(patched) is dict and set(patched) == {'online', 'proxy', 'controller', 'tail', 'wasm', 'proof'}, 'closed-output-roles')
    for role in OUTPUT_PINS:
        _expect(patched[role], OUTPUT_PINS[role])
    uri, wasm = _wasm(original_online)
    _need(patched['wasm'] == wasm, 'exact-derived-body')
    tail = _edits(patched['tail'], TAIL_EDITS, inverse=True)
    _expect(tail, INPUT_PINS['tail'])
    online = patched['online']
    quoted, route = b'"' + uri + b'"', b'"/liblua5.1.wasm"'
    _need(online.count(patched['tail']) == 1 and online.count(route) == 1 and quoted not in online, 'inverse-online-joins')
    online = online.replace(patched['tail'], tail, 1).replace(route, quoted, 1)
    result = dict(online=online, proxy=_edits(patched['proxy'], PROXY_EDITS, inverse=True),
                  controller=_edits(patched['controller'], CONTROLLER_EDITS, inverse=True), tail=tail)
    for role, raw in result.items():
        _expect(raw, INPUT_PINS[role])
    _need(online == original_online, 'exact-original-online')
    return result
