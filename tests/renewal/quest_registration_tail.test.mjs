// T10.005 authored controls. The actual tail text is appended to authored
// lexical stubs and evaluated in a fresh vm context per case. Stubs model
// callers and table writes only; no original loader, Lua, vendor or game data
// runs. Expected reports are written out here, not produced by the tail.

import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

const TAIL = fs.readFileSync(new URL('../../tools/renewal/quest_registration_tail.js', import.meta.url), 'utf8');
const SLOT = '__rootQuestRegistrationT10005';
const ALIASES = [
	'System/OngoingQuestInfoList.lub',
	'System/OngoingQuestInfoList.lua',
	'System/OngoingQuestInfoList_true.lub',
	'System/OngoingQuestInfoList_true.lua',
	'System/OngoingQuestInfoList_sak.lub',
	'System/OngoingQuestInfoList_sak.lua',
	'System/OngoingQuestInfoList_Sakray.lub',
	'System/OngoingQuestInfoList_Sakray.lua'
];
const SYSTEM_EN = 'SystemEN/OngoingQuests.lub';

// Authored lexical stubs standing in for the private DB module bindings.
const STUBS = String.raw`'use strict';
const log = [];
const gates = [];
const LOADER_RETURN = { loaderReturn: true };
const CALLBACK_RETURN = { callbackReturn: true };
const THROWN = { thrown: 1 };
const THROWN2 = { thrown: 2 };
const MARK = { mark: true };
let throwInAliasCallback = -1;
const thisTag = value => (value === undefined ? 'undefined' : value === MARK ? 'MARK' : typeof value);
let _server = {};
let _global = {};
const Configs = {
	get: (key, defaultValue) => {
		log.push('Configs.get:' + key);
		if (key in _server) return _server[key];
		if (key in _global) return _global[key];
		return defaultValue;
	}
};
let lookTables;
let startLuaRejects = false;
async function startLua() {
	log.push('startLua');
	await Promise.resolve();
	if (startLuaRejects) throw new Error('startLua stub rejection');
	log.push('startLua:done');
}
let QuestInfo = {};
let userCharpage = 'windows-1252';
const DB = {
	isLoaded: false, index: 0, count: 0,
	init() { log.push('DB.init'); }, lazyInit() { log.push('DB.lazyInit'); },
	getQuestInfo() { log.push('DB.getQuestInfo'); return { Title: 'Unknown Quest' }; }
};
const MemoryManager = { forceClean() { log.push('forceClean'); } };
const lua = { doStringSync() { log.push('lua.doStringSync'); }, doFile() { log.push('lua.doFile'); } };
// Authored model of the alias helpers' routing (with recording); not original code.
function getSystemAliases(basePath) {
	log.push('getSystemAliases:' + basePath);
	basePath = basePath.replace(/\.(lub|lua)$/i, '');
	const list = [];
	for (const s of ['', '_true', '_sak', '_Sakray']) for (const e of ['.lub', '.lua']) list.push(basePath + s + e);
	return list;
}
function tryLoadLuaAliases(rFunc, files, callBack, onEnd, loadAll = false) {
	log.push('aliases:' + files.length + ':' + String(callBack) + ':' + arguments.length + ':' + loadAll);
	const totalFiles = files.length;
	let finishedCount = 0;
	const trackedOnEnd = isSuccess => {
		finishedCount++;
		if (finishedCount === totalFiles || (isSuccess && !loadAll)) onEnd();
	};
	function tryNext(index) {
		if (index >= totalFiles) return;
		if (files[index].indexOf('System/') !== 0 && files[index].indexOf('SystemEN/') !== 0) files[index] = 'System/' + files[index];
		let returned;
		try {
			returned = rFunc(files[index], callBack, function aliasOnEnd(isSuccess) {
				log.push('aliasOnEnd:' + index + ':' + thisTag(this) + ':' + arguments.length + ':' + isSuccess);
				trackedOnEnd(isSuccess);
				if ((isSuccess && loadAll) || !isSuccess) tryNext(index + 1);
				if (throwInAliasCallback === index) throw THROWN;
				return CALLBACK_RETURN;
			});
		} catch (error) {
			log.push('aliasCaught:' + index + ':' + (error === THROWN ? 'identical' : 'other'));
			throw error;
		}
		log.push('aliasReturned:' + index + ':' + (returned === LOADER_RETURN ? 'identical' : String(returned)));
	}
	tryNext(0);
}
const PLAN = {};
function loadQuestInfo(filename, callback, onEnd) {
	log.push('load:' + filename);
	const step = PLAN[filename] || PLAN['*'];
	return step ? step.call(this, onEnd, filename, callback, arguments.length) : undefined;
}
const reply = value => onEnd => { Promise.resolve().then(() => onEnd(value)); return LOADER_RETURN; };
const replyNow = value => onEnd => { onEnd(value); return LOADER_RETURN; };
const effect = (write, value) => onEnd => { Promise.resolve().then(() => { write(); onEnd(value); }); return LOADER_RETURN; };
// Row shapes follow the reviewed AddQuestInfo/Description/Reward writes.
function addQuest(id, title) {
	QuestInfo[id] = { Title: title, Summary: title, IconName: '', Description: [], NpcSpr: null, NpcNavi: null,
		NpcPosX: 0, NpcPosY: 0, RewardItemList: [], RewardEXP: 0, RewardJEXP: 0 };
}
const addDescription = (id, text) => QuestInfo[id].Description.push(text);
const addReward = (id, item, count) => QuestInfo[id].RewardItemList.push({ ItemID: item, ItemNum: count });
function parseQuestEntry(index, key, title, group, image, description, summary) {
	const quest = QuestInfo[key] || (QuestInfo[key] = {});
	quest.Title = title; quest.Group = group; quest.Image = image; quest.Description = description; quest.Summary = summary;
}
let TEXT_ROWS = [];
function loadTable(filename, separator, size, callback, onEnd, useCharPage) {
	log.push('loadTable:' + [filename, separator, size, callback === parseQuestEntry, typeof onEnd, useCharPage, arguments.length, thisTag(this)].join('|'));
	if (TEXT_ROWS === null) return LOADER_RETURN;
	Promise.resolve().then(() => {
		TEXT_ROWS.forEach((row, i) => callback.apply(null, [i * size].concat(row)));
		const returned = onEnd();
		log.push('textOnEndReturned:' + String(returned));
	});
	return LOADER_RETURN;
}
`;

const plain = value => JSON.parse(JSON.stringify(value));
const tick = () => new Promise(resolve => setImmediate(resolve));

function launch(setup = '') {
	const context = vm.createContext({});
	vm.runInContext(STUBS + '\n' + setup + '\n' + TAIL, context, { filename: 'tail-fixture.js' });
	const promise = vm.runInContext('globalThis.' + SLOT, context);
	const state = { settled: false };
	const outcome = promise.then(
		report => { state.settled = true; return { report: plain(report) }; },
		error => { state.settled = true; return { reasons: plain(error.reasons), complete: error.diagnostic_complete }; }
	);
	return { context, promise, outcome, state, read: expr => plain(vm.runInContext(expr, context)) };
}

const only = (log, prefix) => log.filter(entry => entry.startsWith(prefix));

// Expected-value builders for the contract grammar.
const T = {
	u: ['undefined'], n: ['null'], hole: ['hole'],
	b: v => ['boolean', v], s: v => ['string', v], num: v => ['number', v],
	arr: (...items) => ['array', items], obj: (...entries) => ['object', entries]
};
function luaRow(title, description = [], rewards = []) {
	return T.obj(
		['Description', T.arr(...description.map(T.s))], ['IconName', T.s('')], ['NpcNavi', T.n],
		['NpcPosX', T.num(0)], ['NpcPosY', T.num(0)], ['NpcSpr', T.n], ['RewardEXP', T.num(0)],
		['RewardItemList', T.arr(...rewards.map(([id, n]) => T.obj(['ItemID', T.num(id)], ['ItemNum', T.num(n)])))],
		['RewardJEXP', T.num(0)], ['Summary', T.s(title)], ['Title', T.s(title)]);
}
const own = value => (value === undefined ? { own: false } : { own: true, value });
const snap = (count, row21001, row16912) => ({ own_row_count: count, fixed: { 21001: own(row21001), 16912: own(row16912) } });
const agg = (before, after, added, removed, retained, c21001 = false, c16912 = false) =>
	({ before_count: before, after_count: after, added, removed, retained, fixed_changed: { 21001: c21001, 16912: c16912 } });
const cb = (first, after, aggregate, argc = 1, ordinal = 0) => ({ ordinal, argc, first_boolean: first, after, aggregate });
const stage = (index, kind, path, before, callbacks) => ({ index, kind, path, before, callbacks });
function report(fields) {
	return {
		branch: fields.branch, current_session_equivalence: 'UNKNOWN', diagnostic_complete: true,
		final: fields.final, initial: fields.initial, internal_execution_errors: 'UNKNOWN',
		lookup_values: fields.lookup, main_quest_semantic_result: 'UNKNOWN',
		observed_window: 'terminal-callback/finalization-microtask', original_lazyInit_executed: false,
		positive_control_present: fields.positive, producer_provenance: 'UNKNOWN',
		registration_and_append_call_counts: 'UNKNOWN', schema: 't10.005.quest-registration-diagnostic.v1',
		scope: 'original-private-loaders/reproduced-routing', stages: fields.stages
	};
}
const EMPTY = snap(0);
const ZERO = agg(0, 0, 0, 0, 0);

test('A01 global slot: descriptor, one retained run, collision and definition refusal', async () => {
	const run = launch(`_global = { loadLua: false };`);
	const descriptor = vm.runInContext(`Object.getOwnPropertyDescriptor(globalThis, '${SLOT}')`, run.context);
	assert.equal(descriptor.writable, false);
	assert.equal(descriptor.enumerable, false);
	assert.equal(descriptor.configurable, false);
	assert.equal(vm.runInContext(`globalThis.${SLOT} instanceof Promise`, run.context), true);
	assert.equal(vm.runInContext(`globalThis.${SLOT}`, run.context), run.promise);
	const result = await run.outcome;
	assert.equal(result.report.diagnostic_complete, true);
	assert.deepEqual(only(run.read('log'), 'startLua'), ['startLua', 'startLua:done']);
	assert.deepEqual(only(run.read('log'), 'loadTable:').length, 1);

	// Exactly one new global own key; tail locals stay inside its expression.
	const context = vm.createContext({});
	vm.runInContext(STUBS + `_global = { loadLua: false };`, context);
	const beforeKeys = vm.runInContext('Reflect.ownKeys(globalThis).map(String)', context);
	vm.runInContext(TAIL, context);
	const afterKeys = vm.runInContext('Reflect.ownKeys(globalThis).map(String)', context);
	assert.deepEqual(plain(afterKeys.filter(key => !beforeKeys.includes(key))), [SLOT]);
	assert.deepEqual(plain(beforeKeys.filter(key => !afterKeys.includes(key))), []);
	await vm.runInContext(`globalThis.${SLOT}`, context);

	// Existing accessor slot: synchronous refusal, getter unread, descriptor kept.
	for (const prior of [
		`let getterReads = 0; const priorGet = () => { getterReads++; return 1; };
		Object.defineProperty(globalThis, '${SLOT}', { get: priorGet, configurable: true });`,
		`let getterReads = 0; const priorGet = null;
		Object.defineProperty(globalThis, '${SLOT}', { value: 'prior', writable: true, enumerable: true, configurable: true });`
	]) {
		const collide = vm.createContext({});
		vm.runInContext(STUBS + prior + `lookTables = { catch() { log.push('lookTables.catch'); } };`, collide);
		const before = vm.runInContext(`Object.getOwnPropertyDescriptor(globalThis, '${SLOT}')`, collide);
		assert.throws(() => vm.runInContext(TAIL, collide), error => /already exists/.test(error.message));
		const after = vm.runInContext(`Object.getOwnPropertyDescriptor(globalThis, '${SLOT}')`, collide);
		assert.equal(vm.runInContext('getterReads', collide), 0);
		assert.equal(after.get, before.get);
		assert.equal(after.value, before.value);
		assert.equal(after.writable, before.writable);
		assert.equal(after.enumerable, before.enumerable);
		await tick();
		assert.deepEqual(vm.runInContext('log.slice()', collide).length, 0);
	}

	// Definition failure (a vm global cannot be made non-extensible, so the
	// authored control makes the definition step itself throw): nothing starts.
	const sealed = vm.createContext({});
	vm.runInContext(STUBS + `lookTables = { catch() { log.push('lookTables.catch'); } };
		Object.defineProperty = () => { throw new TypeError('authored definition failure'); };`, sealed);
	assert.throws(() => vm.runInContext(TAIL, sealed), error => error.name === 'TypeError');
	await tick();
	assert.equal(vm.runInContext('log.length', sealed), 0);
	assert.equal(vm.runInContext(`Object.getOwnPropertyDescriptor(globalThis, '${SLOT}')`, sealed), undefined);
});

test('A02 startup: lookTables fulfilled/rejected/absent then startLua; startLua rejection refuses; no DB control calls', async () => {
	const gated = launch(`_global = { loadLua: false };
		lookTables = new Promise(resolve => gates.push(resolve)).then(() => log.push('lookTables:settled'));`);
	await tick();
	assert.deepEqual(gated.read('log'), []);
	vm.runInContext('gates[0]()', gated.context);
	const gatedResult = await gated.outcome;
	assert.equal(gatedResult.report.branch, 'text');
	assert.deepEqual(gated.read('log').slice(0, 4), ['lookTables:settled', 'startLua', 'startLua:done', 'Configs.get:loadLua']);

	const rejected = launch(`_global = { loadLua: false }; lookTables = Promise.reject(new Error('LOOK-TABLES-PAYLOAD'));`);
	const rejectedResult = await rejected.outcome;
	assert.equal(rejectedResult.report.diagnostic_complete, true);
	assert.equal(JSON.stringify(rejectedResult).includes('LOOK-TABLES-PAYLOAD'), false);
	assert.deepEqual(rejected.read('log').slice(0, 3), ['startLua', 'startLua:done', 'Configs.get:loadLua']);

	const absent = launch(`_global = { loadLua: false };`);
	assert.equal((await absent.outcome).report.diagnostic_complete, true);
	assert.deepEqual(absent.read('log').slice(0, 3), ['startLua', 'startLua:done', 'Configs.get:loadLua']);

	const failing = launch(`_global = { loadLua: true }; startLuaRejects = true;`);
	assert.deepEqual(await failing.outcome, { reasons: ['startLua-rejected'], complete: false });
	assert.deepEqual(failing.read('log'), ['startLua']);

	for (const run of [gated, rejected, absent, failing]) {
		const log = run.read('log');
		assert.deepEqual(log.filter(e => /^(DB\.|forceClean|lua\.)/.test(e)), []);
		assert.deepEqual(run.read('[DB.isLoaded, DB.index, DB.count]'), [false, 0, 0]);
	}
});

test('A03 Configs inherited server->global->default semantics and loadLua truthiness', async () => {
	const cases = [
		[`_server = { loadLua: null }; _global = { loadLua: true };`, 'text', T.n],
		[`_server = { loadLua: false }; _global = { loadLua: true };`, 'text', T.b(false)],
		[`_server = { loadLua: 0 }; _global = { loadLua: true };`, 'text', T.num(0)],
		[`_server = { loadLua: '' }; _global = { loadLua: true };`, 'text', T.s('')],
		[`_server = { loadLua: undefined }; _global = { loadLua: true };`, 'text', T.u],
		[`_server = Object.create({ loadLua: 0 }); _global = { loadLua: true };`, 'text', T.num(0)],
		[`_server = Object.create({ loadLua: 'false' }); _global = { loadLua: false };`, 'lua', T.s('false')],
		[`_server = {}; _global = Object.create({ loadLua: 1 });`, 'lua', T.num(1)],
		[`_server = {}; _global = { loadLua: 'yes' };`, 'lua', T.s('yes')],
		[`_server = {}; _global = {};`, 'text', T.u]
	];
	for (const [setup, branch, typedValue] of cases) {
		const run = launch(setup + ` PLAN['*'] = replyNow(true);`);
		const { report: result } = await run.outcome;
		assert.equal(result.branch, branch, setup);
		assert.deepEqual(result.lookup_values.loadLua, typedValue, setup);
		assert.deepEqual(only(run.read('log'), 'Configs.get:loadLua').length, 1);
		assert.equal(only(run.read('log'), 'loadTable:').length, branch === 'text' ? 1 : 0, setup);
		assert.equal(only(run.read('log'), 'aliases:').length, branch === 'lua' ? 1 : 0, setup);
	}
});

test('A04 single lookups after startLua, custom identity/order, existing userCharpage', async () => {
	const run = launch(`_global = { loadLua: true, customQuestInfo: ['C/one.lub', 'C/two.lub'], langtype: 4, disableKorean: true };
		userCharpage = 'big5';
		PLAN['*'] = replyNow(true);
		// Identity probe only (outside the Root no-mutation precondition): the
		// routing must see a write to the very same configured array.
		PLAN['${SYSTEM_EN}'] = onEnd => { _global.customQuestInfo[1] = 'C/mutated.lub'; onEnd(true); };`);
	const { report: result } = await run.outcome;
	const log = run.read('log');
	assert.deepEqual(only(log, 'Configs.get:'), ['Configs.get:loadLua', 'Configs.get:customQuestInfo']);
	assert.ok(log.indexOf('Configs.get:loadLua') > log.indexOf('startLua:done'));
	assert.ok(log.indexOf('Configs.get:customQuestInfo') < log.indexOf('getSystemAliases:System/OngoingQuestInfoList.lub'));
	assert.deepEqual(only(log, 'load:'), ['load:' + ALIASES[0], 'load:' + SYSTEM_EN, 'load:C/one.lub', 'load:C/mutated.lub']);
	assert.deepEqual(result.lookup_values, {
		loadLua: T.b(true), customQuestInfo: T.arr(T.s('C/one.lub'), T.s('C/two.lub')), userCharpage: T.s('big5')
	});
	assert.deepEqual(result.stages.map(s => [s.kind, s.path]),
		[['alias', ALIASES[0]], ['systemEN', SYSTEM_EN], ['custom', 'C/one.lub'], ['custom', 'C/mutated.lub']]);
	assert.equal(vm.runInContext('Object.isFrozen(_global.customQuestInfo)', run.context), false);

	const text = launch(`_global = { loadLua: false, customQuestInfo: ['C/never.lub'] };`);
	const textResult = await text.outcome;
	assert.equal(textResult.report.lookup_values.customQuestInfo, null);
	assert.deepEqual(only(text.read('log'), 'Configs.get:'), ['Configs.get:loadLua']);
});

test('A05 exact eight aliases; false continues, first reported true stops; zero-write true still stops', async () => {
	const run = launch(`_global = { loadLua: true, customQuestInfo: ['Custom/A.lub'] };
		PLAN['${ALIASES[0]}'] = reply(false);
		PLAN['${ALIASES[1]}'] = reply(false);
		PLAN['${ALIASES[2]}'] = effect(() => { addQuest(21001, 'Alpha'); addDescription(21001, 'step one'); addReward(21001, 501, 2); }, true);
		PLAN['${SYSTEM_EN}'] = reply(true);
		PLAN['Custom/A.lub'] = effect(() => addQuest(16912, 'Beta'), true);`);
	const result = await run.outcome;
	const alpha = luaRow('Alpha', ['step one'], [[501, 2]]);
	const beta = luaRow('Beta');
	const one = snap(1, alpha);
	const two = snap(2, alpha, beta);
	assert.deepEqual(result, { report: report({
		branch: 'lua',
		lookup: { loadLua: T.b(true), customQuestInfo: T.arr(T.s('Custom/A.lub')), userCharpage: T.s('windows-1252') },
		initial: EMPTY,
		stages: [
			stage(0, 'alias', ALIASES[0], EMPTY, [cb(false, EMPTY, ZERO)]),
			stage(1, 'alias', ALIASES[1], EMPTY, [cb(false, EMPTY, ZERO)]),
			stage(2, 'alias', ALIASES[2], EMPTY, [cb(true, one, agg(0, 1, 1, 0, 0, true, false))]),
			stage(3, 'systemEN', SYSTEM_EN, one, [cb(true, one, agg(1, 1, 0, 0, 1))]),
			stage(4, 'custom', 'Custom/A.lub', one, [cb(true, two, agg(1, 2, 1, 0, 1, false, true))])
		],
		final: two,
		positive: true
	}) });
	const log = run.read('log');
	assert.deepEqual(only(log, 'aliases:'), ['aliases:8:null:4:false']);
	assert.deepEqual(only(log, 'load:'), ['load:' + ALIASES[0], 'load:' + ALIASES[1], 'load:' + ALIASES[2], 'load:' + SYSTEM_EN, 'load:Custom/A.lub']);

	const zero = launch(`_global = { loadLua: true }; PLAN['${ALIASES[0]}'] = reply(true); PLAN['${SYSTEM_EN}'] = reply(true);`);
	assert.deepEqual(await zero.outcome, { report: report({
		branch: 'lua',
		lookup: { loadLua: T.b(true), customQuestInfo: T.arr(), userCharpage: T.s('windows-1252') },
		initial: EMPTY,
		stages: [stage(0, 'alias', ALIASES[0], EMPTY, [cb(true, EMPTY, ZERO)]), stage(1, 'systemEN', SYSTEM_EN, EMPTY, [cb(true, EMPTY, ZERO)])],
		final: EMPTY,
		positive: false
	}) });
	assert.deepEqual(only(zero.read('log'), 'load:'), ['load:' + ALIASES[0], 'load:' + SYSTEM_EN]);
});

test('A06 all aliases false still reach SystemEN; SystemEN/custom false continue; custom spelling unchanged', async () => {
	const expectedCustoms = ['custom/Path.LUA', 'System\\X.lub', 'data\\Quest.lub', '/abs/Q.lub'];
	const run = launch(`_global = { loadLua: true, customQuestInfo: ['custom/Path.LUA', 'System\\\\X.lub', 'data\\\\Quest.lub', '/abs/Q.lub'] };
		PLAN['*'] = reply(false);
		PLAN['/abs/Q.lub'] = reply(true);`);
	const { report: result } = await run.outcome;
	assert.deepEqual(only(run.read('log'), 'load:'), [...ALIASES, SYSTEM_EN, ...expectedCustoms].map(path => 'load:' + path));
	assert.deepEqual(result.stages.map(s => [s.index, s.kind, s.path, s.callbacks.map(c => c.first_boolean)]), [
		...ALIASES.map((path, i) => [i, 'alias', path, [false]]),
		[8, 'systemEN', SYSTEM_EN, [false]],
		[9, 'custom', expectedCustoms[0], [false]],
		[10, 'custom', expectedCustoms[1], [false]],
		[11, 'custom', expectedCustoms[2], [false]],
		[12, 'custom', expectedCustoms[3], [true]]
	]);
	assert.equal(result.diagnostic_complete, true);
	assert.equal(result.positive_control_present, false);
});

test('A07 SystemEN overlay replaces whole row and resets arrays; empty overlay preserves; no clearing', async () => {
	const run = launch(`_global = { loadLua: true, customQuestInfo: ['Custom/empty.lub'] };
		QuestInfo.other = { kept: true };
		PLAN['${ALIASES[0]}'] = effect(() => { addQuest(21001, 'Old'); addDescription(21001, 'old line'); addReward(21001, 601, 1); }, true);
		PLAN['${SYSTEM_EN}'] = effect(() => { addQuest(21001, 'New'); addDescription(21001, 'new line'); }, true);
		PLAN['Custom/empty.lub'] = reply(true);`);
	const result = await run.outcome;
	const start = snap(1);
	const oldRow = snap(2, luaRow('Old', ['old line'], [[601, 1]]));
	const newRow = snap(2, luaRow('New', ['new line']));
	assert.deepEqual(result, { report: report({
		branch: 'lua',
		lookup: { loadLua: T.b(true), customQuestInfo: T.arr(T.s('Custom/empty.lub')), userCharpage: T.s('windows-1252') },
		initial: start,
		stages: [
			stage(0, 'alias', ALIASES[0], start, [cb(true, oldRow, agg(1, 2, 1, 0, 1, true, false))]),
			stage(1, 'systemEN', SYSTEM_EN, oldRow, [cb(true, newRow, agg(2, 2, 0, 0, 2, true, false))]),
			stage(2, 'custom', 'Custom/empty.lub', newRow, [cb(true, newRow, agg(2, 2, 0, 0, 2))])
		],
		final: newRow,
		positive: true
	}) });
	assert.deepEqual(run.read('QuestInfo.other'), { kept: true });
});

test('A08 text branch: exact loadTable call only; text update retains reward fields; NOT_REPORTED', async () => {
	const run = launch(`_global = { loadLua: false };
		addQuest(21001, 'Lua title'); addReward(21001, 7, 1);
		TEXT_ROWS = [['21001', 'T title', 'G1', 'img.bmp', 'desc text', 'sum text'], ['16912', 'Second', 'G2', '', '', '']];`);
	const result = await run.outcome;
	const before = snap(1, luaRow('Lua title', [], [[7, 1]]));
	const textRow = T.obj(
		['Description', T.s('desc text')], ['Group', T.s('G1')], ['IconName', T.s('')], ['Image', T.s('img.bmp')],
		['NpcNavi', T.n], ['NpcPosX', T.num(0)], ['NpcPosY', T.num(0)], ['NpcSpr', T.n], ['RewardEXP', T.num(0)],
		['RewardItemList', T.arr(T.obj(['ItemID', T.num(7)], ['ItemNum', T.num(1)]))], ['RewardJEXP', T.num(0)],
		['Summary', T.s('sum text')], ['Title', T.s('T title')]);
	const second = T.obj(['Description', T.s('')], ['Group', T.s('G2')], ['Image', T.s('')], ['Summary', T.s('')], ['Title', T.s('Second')]);
	const after = snap(2, textRow, second);
	assert.deepEqual(result, { report: report({
		branch: 'text',
		lookup: { loadLua: T.b(false), customQuestInfo: null, userCharpage: T.s('windows-1252') },
		initial: before,
		stages: [stage(0, 'text', 'data/questid2display.txt', before, [cb('NOT_REPORTED', after, agg(1, 2, 1, 0, 1, true, true), 0)])],
		final: after,
		positive: true
	}) });
	const log = run.read('log');
	assert.deepEqual(only(log, 'loadTable:'), ['loadTable:data/questid2display.txt|#|6|true|function|true|6|undefined']);
	assert.deepEqual(log.filter(e => /^(load:|aliases:|getSystemAliases:)/.test(e)), []);
	assert.ok(log.indexOf('loadTable:data/questid2display.txt|#|6|true|function|true|6|undefined') > log.indexOf('startLua:done'));
	assert.deepEqual(only(log, 'textOnEndReturned:'), ['textOnEndReturned:undefined']);
});

test('A09 forwarding: single delegation, this/args/return/identical throws, duplicates and pending work', async () => {
	const forwarding = launch(`_global = { loadLua: true };
		PLAN['${ALIASES[0]}'] = function (onEnd, filename, callback, argc) {
			log.push('loaderThis:' + thisTag(this) + ':' + argc + ':' + String(callback));
			const returned = onEnd.call(MARK, true, 'extra', 3);
			log.push('callbackReturned:' + (returned === CALLBACK_RETURN ? 'identical' : 'other'));
			return LOADER_RETURN;
		};
		PLAN['${SYSTEM_EN}'] = reply(true);`);
	const forwarded = await forwarding.outcome;
	assert.equal(forwarded.report.diagnostic_complete, true);
	assert.deepEqual(forwarded.report.stages[0].callbacks, [cb(true, EMPTY, ZERO, 3)]);
	assert.deepEqual(forwarding.read('log').filter(e => /^(loaderThis|aliasOnEnd|callbackReturned|aliasReturned|load:)/.test(e)), [
		'load:' + ALIASES[0], 'loaderThis:undefined:3:null', 'aliasOnEnd:0:MARK:3:true', 'load:' + SYSTEM_EN,
		'callbackReturned:identical', 'aliasReturned:0:identical'
	]);

	const loaderThrow = launch(`_global = { loadLua: true }; PLAN['${ALIASES[0]}'] = () => { throw THROWN; };`);
	assert.deepEqual(await loaderThrow.outcome,
		{ reasons: ['original-loader-throw', 'original-route-throw', 'route-aborted'], complete: false });
	assert.deepEqual(only(loaderThrow.read('log'), 'alias'), ['aliases:8:null:4:false', 'aliasCaught:0:identical']);
	assert.deepEqual(only(loaderThrow.read('log'), 'load:'), ['load:' + ALIASES[0]]);

	// Original callback throws after the terminal signal: identical object
	// reaches the loader and the run cannot resolve successfully.
	const callbackThrow = launch(`_global = { loadLua: true }; throwInAliasCallback = 0;
		PLAN['${ALIASES[0]}'] = onEnd => { try { onEnd(true); } catch (error) { log.push('loaderCaught:' + (error === THROWN)); } };
		PLAN['${SYSTEM_EN}'] = replyNow(true);`);
	assert.deepEqual(await callbackThrow.outcome, { reasons: ['original-callback-throw'], complete: false });
	assert.deepEqual(callbackThrow.read('log').filter(e => /^(loaderCaught|load:)/.test(e)),
		['load:' + ALIASES[0], 'load:' + SYSTEM_EN, 'loaderCaught:true']);

	// Loader throws after its own callback ended the route.
	const lateLoaderThrow = launch(`_global = { loadLua: true, customQuestInfo: ['C/last.lub'] };
		PLAN['${ALIASES[0]}'] = reply(true);
		PLAN['${SYSTEM_EN}'] = onEnd => { Promise.resolve().then(() => { try { onEnd(true); } catch (error) { log.push('systemENCaught:' + (error === THROWN2)); } }); };
		PLAN['C/last.lub'] = onEnd => { onEnd(true); throw THROWN2; };`);
	assert.deepEqual(await lateLoaderThrow.outcome, { reasons: ['original-loader-throw', 'original-callback-throw'], complete: false });
	assert.deepEqual(only(lateLoaderThrow.read('log'), 'systemENCaught:'), ['systemENCaught:true']);

	// Duplicate callbacks are forwarded, not suppressed; the work they create
	// must finish its first callback before the refusal is settled.
	const duplicate = launch(`_global = { loadLua: true };
		PLAN['${ALIASES[0]}'] = onEnd => { onEnd(false); onEnd(false); return LOADER_RETURN; };
		PLAN['${ALIASES[1]}'] = onEnd => { gates.push(() => onEnd(true)); return LOADER_RETURN; };
		PLAN['${SYSTEM_EN}'] = replyNow(true);`);
	await tick();
	assert.equal(duplicate.state.settled, false);
	assert.deepEqual(only(duplicate.read('log'), 'aliasOnEnd:'), ['aliasOnEnd:0:undefined:1:false', 'aliasOnEnd:0:undefined:1:false']);
	assert.deepEqual(only(duplicate.read('log'), 'load:'), ['load:' + ALIASES[0], 'load:' + ALIASES[1], 'load:' + ALIASES[1]]);
	vm.runInContext('gates[0]()', duplicate.context);
	await tick();
	assert.equal(duplicate.state.settled, false);
	vm.runInContext('gates[1]()', duplicate.context);
	assert.deepEqual(await duplicate.outcome, { reasons: ['duplicate-callback', 'duplicate-terminal'], complete: false });
	assert.equal(only(duplicate.read('log'), 'load:' + SYSTEM_EN).length, 2);

	// Finalization waits for its microtask: a synchronous duplicate in the same
	// turn is captured, and work it creates is awaited by the queued recheck.
	const sameTurn = launch(`_global = { loadLua: true }; let systemENCalls = 0;
		PLAN['${ALIASES[0]}'] = onEnd => { gates.push(onEnd); return LOADER_RETURN; };
		PLAN['${SYSTEM_EN}'] = onEnd => {
			if (systemENCalls++ === 0) onEnd(true); else gates.push(() => onEnd(true));
			return LOADER_RETURN;
		};`);
	await tick();
	vm.runInContext('gates[0](true); gates[0](true);', sameTurn.context);
	await tick();
	assert.equal(sameTurn.state.settled, false);
	vm.runInContext('gates[1]()', sameTurn.context);
	assert.deepEqual(await sameTurn.outcome, { reasons: ['duplicate-callback', 'duplicate-terminal'], complete: false });

	// A callback that never arrives keeps the run pending (external deadline).
	const hung = launch(`_global = { loadLua: true }; PLAN['${ALIASES[0]}'] = () => LOADER_RETURN;`);
	await tick();
	await tick();
	assert.equal(hung.state.settled, false);
});

test('A10 own vs inherited, primitive distinctions, holes/order, detached snapshots, no DB getter', async () => {
	const run = launch(`_global = { loadLua: true };
		QuestInfo = Object.create({ 16912: { Title: 'inherited' } });
		const bare = Object.create(null); bare.x = 1;
		QuestInfo[21001] = { a: undefined, b: null, c: false, d: 0, e: -0, f: '', g: [1, , 3], h: NaN, i: Infinity,
			j: -Infinity, k: [], l: {}, m: bare, n: ['z', 'a'], o: [undefined] };
		PLAN['${ALIASES[0]}'] = effect(() => { addQuest(21001, 'New'); addDescription(21001, 'd1'); }, true);
		PLAN['${SYSTEM_EN}'] = effect(() => addDescription(21001, 'd2'), true);`);
	const result = await run.outcome;
	const original = T.obj(
		['a', T.u], ['b', T.n], ['c', T.b(false)], ['d', T.num(0)], ['e', ['negative-zero']], ['f', T.s('')],
		['g', T.arr(T.num(1), T.hole, T.num(3))], ['h', ['nan']], ['i', ['positive-infinity']], ['j', ['negative-infinity']],
		['k', T.arr()], ['l', T.obj()], ['m', T.obj(['x', T.num(1)])], ['n', T.arr(T.s('z'), T.s('a'))], ['o', T.arr(T.u)]);
	const start = snap(1, original);
	const d1 = snap(1, luaRow('New', ['d1']));
	const d2 = snap(1, luaRow('New', ['d1', 'd2']));
	assert.deepEqual(result, { report: report({
		branch: 'lua',
		lookup: { loadLua: T.b(true), customQuestInfo: T.arr(), userCharpage: T.s('windows-1252') },
		initial: start,
		stages: [
			stage(0, 'alias', ALIASES[0], start, [cb(true, d1, agg(1, 1, 0, 0, 1, true, false))]),
			stage(1, 'systemEN', SYSTEM_EN, d1, [cb(true, d2, agg(1, 1, 0, 0, 1, true, false))])
		],
		final: d2,
		positive: true
	}) });
	assert.deepEqual(only(run.read('log'), 'DB.'), []);

	const ownUndefined = launch(`_global = { loadLua: false }; QuestInfo[16912] = undefined; QuestInfo[21001] = 0;`);
	const { report: second } = await ownUndefined.outcome;
	assert.deepEqual(second.initial, snap(2, T.num(0), T.u));
	assert.equal(second.positive_control_present, true);
});

test('A11 own-key aggregate equations; replacement, non-enumerable, inherited and symbol keys', async () => {
	const run = launch(`_global = { loadLua: true };
		QuestInfo = Object.create({ inh: {} });
		QuestInfo.a = { v: 1 }; QuestInfo.b = {}; QuestInfo[21001] = { Title: 'Same' };
		Object.defineProperty(QuestInfo, 'hidden', { value: {}, enumerable: false, writable: true, configurable: true });
		QuestInfo[Symbol('s')] = {};
		PLAN['${ALIASES[0]}'] = effect(() => {
			QuestInfo.a = { v: 2 }; delete QuestInfo.b; QuestInfo.c = {};
			Object.defineProperty(QuestInfo, 'hidden2', { value: {}, enumerable: false, configurable: true });
		}, true);
		PLAN['${SYSTEM_EN}'] = effect(() => { QuestInfo[21001] = { Title: 'Same' }; QuestInfo.a = { v: 3 }; }, true);`);
	const result = await run.outcome;
	const same = T.obj(['Title', T.s('Same')]);
	assert.deepEqual(result.report.initial, snap(4, same));
	assert.deepEqual(result.report.stages.map(s => s.callbacks.map(c => c.aggregate)), [
		[agg(4, 5, 2, 1, 3)],
		[agg(5, 5, 0, 0, 5)]
	]);
	for (const s of result.report.stages) {
		for (const c of s.callbacks) {
			assert.equal(c.aggregate.before_count, c.aggregate.removed + c.aggregate.retained);
			assert.equal(c.aggregate.after_count, c.aggregate.added + c.aggregate.retained);
		}
	}
	const text = JSON.stringify(result.report);
	for (const key of ['"hidden"', '"hidden2"', '"inh"', '"v"', '"c"']) assert.equal(text.includes(key), false, key);
	assert.equal(result.report.registration_and_append_call_counts, 'UNKNOWN');
});

test('A12 honest evidence: zero rows, partial write, absent 16912 with own 21001', async () => {
	const keys = ['branch', 'current_session_equivalence', 'diagnostic_complete', 'final', 'initial', 'internal_execution_errors',
		'lookup_values', 'main_quest_semantic_result', 'observed_window', 'original_lazyInit_executed', 'positive_control_present',
		'producer_provenance', 'registration_and_append_call_counts', 'schema', 'scope', 'stages'];
	const zero = await launch(`_global = { loadLua: true }; PLAN['*'] = reply(true);`).outcome;
	assert.deepEqual(Object.keys(zero.report).sort(), keys);
	assert.equal(zero.report.positive_control_present, false);
	assert.deepEqual(zero.report.final, EMPTY);

	const partial = await launch(`_global = { loadLua: true };
		PLAN['${ALIASES[0]}'] = effect(() => { QuestInfo[21001] = { Title: 'partial' }; }, true);
		PLAN['${SYSTEM_EN}'] = reply(true);`).outcome;
	assert.deepEqual(partial.report.final, snap(1, T.obj(['Title', T.s('partial')])));
	assert.equal(partial.report.main_quest_semantic_result, 'UNKNOWN');
	assert.equal(partial.report.internal_execution_errors, 'UNKNOWN');

	const control = await launch(`_global = { loadLua: true };
		PLAN['${ALIASES[0]}'] = effect(() => addQuest(21001, 'Control'), true);
		PLAN['${SYSTEM_EN}'] = reply(true);`).outcome;
	assert.equal(control.report.positive_control_present, true);
	assert.deepEqual(control.report.final.fixed['16912'], { own: false });
	assert.deepEqual(Object.keys(control.report).sort(), keys);
	assert.equal(control.report.producer_provenance, 'UNKNOWN');
	assert.equal(control.report.current_session_equivalence, 'UNKNOWN');
});

test('A13 invalid custom config and typed caps refuse without coercion, getters or row changes', async () => {
	const invalid = [
		['null', 'custom-not-array'],
		[`'Custom/A.lub'`, 'custom-not-array'],
		[`{ 0: 'a', length: 1 }`, 'custom-not-array'],
		[`Array.from({ length: 33 }, (_, i) => 'C/' + i)`, 'custom-count-cap'],
		[`['']`, 'custom-invalid-entry'],
		[`[1]`, 'custom-invalid-entry'],
		[`['a\\0b']`, 'custom-invalid-entry'],
		[`['x'.repeat(1025)]`, 'custom-invalid-entry'],
		[`[, 'a']`, 'custom-not-dense'],
		[`Object.assign(['a'], { extra: 1 })`, 'custom-not-dense'],
		[`(() => { const list = ['a']; list[Symbol('s')] = 1; return list; })()`, 'custom-symbol-key'],
		[`Object.defineProperty(['a'], 0, { get() { getterReads++; return 'a'; } })`, 'accessor']
	];
	for (const [value, code] of invalid) {
		const run = launch(`let getterReads = 0; _global = { loadLua: true, customQuestInfo: ${value} };`);
		assert.deepEqual(await run.outcome, { reasons: [code], complete: false }, value);
		const log = run.read('log');
		assert.deepEqual(log, ['startLua', 'startLua:done', 'Configs.get:loadLua', 'Configs.get:customQuestInfo'], value);
		assert.equal(run.read('getterReads'), 0);
	}

	const boundary = launch(`_global = { loadLua: true, customQuestInfo: Array.from({ length: 32 }, (_, i) => String(i).padStart(1024, 'q')) };
		PLAN['*'] = replyNow(true);`);
	const { report: bounded } = await boundary.outcome;
	assert.equal(bounded.stages.length, 34);
	assert.equal(bounded.stages[33].path, '31'.padStart(1024, 'q'));

	const caps = [
		[`let v = 0; for (let i = 0; i < 7; i++) v = [v]; QuestInfo[21001] = v;`, null],
		[`let v = 0; for (let i = 0; i < 8; i++) v = [v]; QuestInfo[21001] = v;`, 'depth-cap'],
		[`const row = {}; row.self = row; QuestInfo[21001] = row;`, 'cyclic-value'],
		[`const shared = { s: 1 }; QuestInfo[21001] = { a: shared, b: shared };`, null],
		[`QuestInfo[21001] = Object.defineProperty({}, 'Title', { get() { getterReads++; return 't'; }, enumerable: true });`, 'accessor'],
		[`Object.defineProperty(QuestInfo, '21001', { get() { getterReads++; return {}; } });`, 'accessor'],
		[`QuestInfo[21001] = { f() {} };`, 'unsupported-value'],
		[`QuestInfo[21001] = { s: Symbol('x') };`, 'unsupported-value'],
		[`QuestInfo[21001] = { n: 1n };`, 'unsupported-value'],
		[`QuestInfo[21001] = { d: new Date(0) };`, 'unsupported-object'],
		[`QuestInfo[21001] = { u: new Uint8Array(2) };`, 'unsupported-object'],
		[`QuestInfo[21001] = { [Symbol('k')]: 1 };`, 'symbol-key'],
		[`QuestInfo[21001] = Object.assign([1], { extra: 2 });`, 'array-extra-key'],
		[`QuestInfo[21001] = 'x'.repeat(65536);`, null],
		[`QuestInfo[21001] = 'x'.repeat(65537);`, 'string-cap'],
		[`QuestInfo[21001] = new Array(40000).fill(0);`, 'node-cap'],
		[`QuestInfo[21001] = Array.from({ length: 9 }, () => 'é'.repeat(60000));`, 'report-budget'],
		[`for (let i = 0; i < 65537; i++) QuestInfo['k' + i] = 0;`, 'row-key-cap']
	];
	for (const [setup, code] of caps) {
		const run = launch(`let getterReads = 0; _global = { loadLua: false }; ${setup} const priorDescriptor = Object.getOwnPropertyDescriptor(QuestInfo, '21001');`);
		const result = await run.outcome;
		if (code === null) {
			assert.equal(result.report.diagnostic_complete, true, setup);
		} else {
			assert.deepEqual(result, { reasons: [code], complete: false }, setup);
			assert.deepEqual(only(run.read('log'), 'loadTable:'), [], setup);
		}
		assert.equal(run.read('getterReads'), 0, setup);
		assert.equal(vm.runInContext(`(() => { const now = Object.getOwnPropertyDescriptor(QuestInfo, '21001');
			return now === priorDescriptor || (now.value === priorDescriptor.value && now.get === priorDescriptor.get); })()`, run.context), true);
		assert.equal(vm.runInContext('Object.isFrozen(QuestInfo)', run.context), false);
	}

	// Node budget spans the whole run: two 17001-node snapshots exceed it.
	const cumulative = launch(`_global = { loadLua: true }; QuestInfo[21001] = new Array(17000).fill(0);
		PLAN['*'] = reply(true);`);
	assert.deepEqual(await cumulative.outcome, { reasons: ['node-cap'], complete: false });
	assert.deepEqual(only(cumulative.read('log'), 'load:'), ['load:' + ALIASES[0], 'load:' + SYSTEM_EN]);
});

test('A14 sticky observation failure: callback forwarded once, fallback unaffected, no empty success', async () => {
	const run = launch(`_global = { loadLua: true, customQuestInfo: ['C/after.lub'] };
		PLAN['${ALIASES[0]}'] = effect(() => { QuestInfo[21001] = { bad() {} }; }, false);
		PLAN['${ALIASES[1]}'] = effect(() => addQuest(21001, 'Good'), true);
		PLAN['${SYSTEM_EN}'] = reply(true);
		PLAN['C/after.lub'] = reply(true);`);
	const result = await run.outcome;
	assert.deepEqual(result, { reasons: ['unsupported-value'], complete: false });
	const log = run.read('log');
	assert.deepEqual(only(log, 'aliasOnEnd:'), ['aliasOnEnd:0:undefined:1:false', 'aliasOnEnd:1:undefined:1:true']);
	assert.deepEqual(only(log, 'load:'), ['load:' + ALIASES[0], 'load:' + ALIASES[1], 'load:' + SYSTEM_EN, 'load:C/after.lub']);
	assert.deepEqual(run.read('QuestInfo[21001].Title'), 'Good');
});

test('A15 no main_quest/doStringSync/Lua clearing; literal UNKNOWN fields; closed source dependencies', async () => {
	for (const forbidden of [/doStringSync/, /main_quest(?!_semantic_result)/, /\bimport\b/, /\brequire\b/, /\bprocess\b/, /\bfetch\b/,
		/XMLHttpRequest/, /\bDB\./, /lazyInit\(/, /forceClean/, /\bconsole\b/, /\blua\./, /\bClient\b/, /\basync\s+function\s+observed/, /\bexport\b/, /setTimeout/]) {
		assert.equal(forbidden.test(TAIL), false, String(forbidden));
	}
	for (const required of [
		"await lookTables?.catch(() => {});", 'await startLua();', "Configs.get('loadLua')",
		"Configs.get('customQuestInfo', [])", "getSystemAliases('System/OngoingQuestInfoList.lub')",
		"observedLoader('SystemEN/OngoingQuests.lub', null,", 'delegate(loadQuestInfo, this, args, invocation)',
		'Reflect.apply(loader, thisArg, args)', 'Reflect.apply(forward, this, arguments)',
		"tryLoadLuaAliases(observedLoader, getSystemAliases('System/OngoingQuestInfoList.lub'), null, () => {",
		"['data/questid2display.txt', '#', 6, parseQuestEntry, done, true]", 'const FIXED_IDS = [21001, 16912];'
	]) {
		assert.ok(TAIL.includes(required), required);
	}
	assert.ok(Buffer.byteLength(TAIL) <= 24576);
	const run = launch(`_global = { loadLua: true };
		PLAN['*'] = effect(() => { addQuest(21001, 'x'); addQuest(16912, 'y'); }, true);`);
	const { report: result } = await run.outcome;
	for (const field of ['main_quest_semantic_result', 'internal_execution_errors', 'registration_and_append_call_counts',
		'producer_provenance', 'current_session_equivalence']) {
		assert.equal(result[field], 'UNKNOWN');
	}
	assert.equal(result.original_lazyInit_executed, false);
	assert.deepEqual(run.read('log').filter(e => /^(lua\.|DB\.|forceClean)/.test(e)), []);
	assert.ok(Buffer.byteLength(JSON.stringify(result)) <= 524288);
});
