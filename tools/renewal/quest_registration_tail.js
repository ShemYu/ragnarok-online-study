// T10.005 closed quest-registration diagnostic tail.
// Root appends this text to an independently qualified diagnostic module whose
// private DB bindings (Configs, lookTables, startLua, QuestInfo, userCharpage,
// getSystemAliases, tryLoadLuaAliases, loadQuestInfo, loadTable, parseQuestEntry)
// are already initialized. It defines one global promise and starts one run;
// it exports nothing else and takes no parameters.
;void function questRegistrationTailT10005() {
	'use strict';

	const SLOT = '__rootQuestRegistrationT10005';
	const HOST = globalThis;

	// Collision is refused synchronously from the descriptor alone; no getter
	// is read and the existing property is left exactly as it was.
	if (Object.getOwnPropertyDescriptor(HOST, SLOT) !== undefined) {
		throw new Error('T10.005 refused: ' + SLOT + ' already exists');
	}

	let resolveRun;
	let rejectRun;
	const retained = new Promise((resolve, reject) => {
		resolveRun = resolve;
		rejectRun = reject;
	});
	// A failed definition throws here, before any startup work begins.
	Object.defineProperty(HOST, SLOT, {
		value: retained,
		writable: false,
		enumerable: false,
		configurable: false
	});

	const FIXED_IDS = [21001, 16912];
	const MAX_DEPTH = 8;
	const MAX_NODES = 32768;
	const MAX_STRING = 65536;
	const MAX_ROW_KEYS = 65536;
	const MAX_REPORT_BYTES = 524288;
	const MAX_STAGES = 41;
	const MAX_CUSTOM = 32;
	const MAX_CUSTOM_PATH = 1024;
	const NOT_REPORTED = 'NOT_REPORTED';
	const UNKNOWN = 'UNKNOWN';

	// Conservative compact-JSON charges for fixed report structure. Typed
	// leaves and keys are charged exactly from their serialization.
	const CHARGE_REPORT = 1024;
	const CHARGE_SNAPSHOT = 160;
	const CHARGE_STAGE = 96;
	const CHARGE_CALLBACK = 96;
	const CHARGE_AGGREGATE = 200;

	function Refused(code) {
		this.code = code;
	}

	const reasons = [];
	const stages = [];
	let nodes = 0;
	let bytes = 0;
	let pending = 0;
	let depth = 0;
	let terminalSeen = false;
	let thrownSeen = false;
	let finalizeQueued = false;
	let settled = false;
	let phase = 'alias';
	let branch = null;
	let lookupValues = null;
	let initial = null;

	function latch(code) {
		if (reasons.indexOf(code) === -1) {
			reasons.push(code);
		}
	}

	function refusal() {
		const error = new Error('T10.005 diagnostic refused: ' + reasons.join(', '));
		error.reasons = reasons.slice();
		error.diagnostic_complete = false;
		error.stage_count = stages.length;
		return error;
	}

	function utf8Length(text) {
		let length = 0;
		for (let i = 0; i < text.length; i++) {
			const unit = text.charCodeAt(i);
			if (unit < 0x80) {
				length += 1;
			} else if (unit < 0x800) {
				length += 2;
			} else if (unit >= 0xd800 && unit <= 0xdbff && i + 1 < text.length) {
				const next = text.charCodeAt(i + 1);
				if (next >= 0xdc00 && next <= 0xdfff) {
					length += 4;
					i++;
				} else {
					length += 3;
				}
			} else {
				length += 3;
			}
		}
		return length;
	}

	function charge(amount) {
		if (bytes + amount > MAX_REPORT_BYTES) {
			throw new Refused('report-budget');
		}
		bytes += amount;
	}

	function leaf(node) {
		charge(utf8Length(JSON.stringify(node)) + 1);
		return node;
	}

	function countNode(level) {
		if (level > MAX_DEPTH) {
			throw new Refused('depth-cap');
		}
		if (++nodes > MAX_NODES) {
			throw new Refused('node-cap');
		}
	}

	function typed(value, level, ancestors) {
		countNode(level);
		switch (typeof value) {
			case 'undefined':
				return leaf(['undefined']);
			case 'boolean':
				return leaf(['boolean', value]);
			case 'string':
				if (value.length > MAX_STRING) {
					throw new Refused('string-cap');
				}
				return leaf(['string', value]);
			case 'number':
				if (value !== value) {
					return leaf(['nan']);
				}
				if (value === Infinity) {
					return leaf(['positive-infinity']);
				}
				if (value === -Infinity) {
					return leaf(['negative-infinity']);
				}
				if (value === 0 && 1 / value < 0) {
					return leaf(['negative-zero']);
				}
				return leaf(['number', value]);
			case 'object':
				if (value === null) {
					return leaf(['null']);
				}
				break;
			default:
				throw new Refused('unsupported-value');
		}
		if (ancestors.indexOf(value) !== -1) {
			throw new Refused('cyclic-value');
		}
		ancestors.push(value);
		try {
			return Array.isArray(value) ? typedArray(value, level, ancestors) : typedRecord(value, level, ancestors);
		} finally {
			ancestors.pop();
		}
	}

	function typedArray(value, level, ancestors) {
		const length = Object.getOwnPropertyDescriptor(value, 'length').value;
		if (length > MAX_NODES) {
			throw new Refused('node-cap');
		}
		const keys = Reflect.ownKeys(value);
		for (let i = 0; i < keys.length; i++) {
			const key = keys[i];
			if (typeof key !== 'string') {
				throw new Refused('symbol-key');
			}
			if (key === 'length') {
				continue;
			}
			const index = Number(key);
			if (String(index) !== key || index % 1 !== 0 || index < 0 || index >= length) {
				throw new Refused('array-extra-key');
			}
		}
		charge(12);
		const items = [];
		for (let i = 0; i < length; i++) {
			const descriptor = Object.getOwnPropertyDescriptor(value, String(i));
			if (descriptor === undefined) {
				countNode(level + 1);
				items.push(leaf(['hole']));
			} else if (!('value' in descriptor)) {
				throw new Refused('accessor');
			} else {
				items.push(typed(descriptor.value, level + 1, ancestors));
			}
		}
		return ['array', items];
	}

	function typedRecord(value, level, ancestors) {
		const prototype = Object.getPrototypeOf(value);
		if (prototype !== null && prototype !== Object.prototype) {
			throw new Refused('unsupported-object');
		}
		const keys = Reflect.ownKeys(value);
		if (keys.length > MAX_NODES) {
			throw new Refused('node-cap');
		}
		for (let i = 0; i < keys.length; i++) {
			if (typeof keys[i] !== 'string') {
				throw new Refused('symbol-key');
			}
		}
		keys.sort();
		charge(13);
		const entries = [];
		for (let i = 0; i < keys.length; i++) {
			const key = keys[i];
			if (key.length > MAX_STRING) {
				throw new Refused('string-cap');
			}
			const descriptor = Object.getOwnPropertyDescriptor(value, key);
			if (!('value' in descriptor)) {
				throw new Refused('accessor');
			}
			charge(utf8Length(JSON.stringify(key)) + 4);
			entries.push([key, typed(descriptor.value, level + 1, ancestors)]);
		}
		return ['object', entries];
	}

	// Own string keys only (enumerable or not); symbols and inherited keys are
	// outside the aggregate. Only the two fixed rows have their values read.
	function snapshot() {
		const names = Object.getOwnPropertyNames(QuestInfo);
		if (names.length > MAX_ROW_KEYS) {
			throw new Refused('row-key-cap');
		}
		charge(CHARGE_SNAPSHOT);
		const fixed = {};
		const compare = {};
		for (let i = 0; i < FIXED_IDS.length; i++) {
			const key = String(FIXED_IDS[i]);
			const descriptor = Object.getOwnPropertyDescriptor(QuestInfo, key);
			if (descriptor === undefined) {
				fixed[key] = { own: false };
				compare[key] = 'absent';
				continue;
			}
			if (!('value' in descriptor)) {
				throw new Refused('accessor');
			}
			const value = typed(descriptor.value, 1, []);
			fixed[key] = { own: true, value: value };
			compare[key] = JSON.stringify(value);
		}
		return { view: { own_row_count: names.length, fixed: fixed }, keys: new Set(names), compare: compare };
	}

	function aggregate(before, after) {
		let retainedCount = 0;
		after.keys.forEach(key => {
			if (before.keys.has(key)) {
				retainedCount++;
			}
		});
		const fixedChanged = {};
		for (let i = 0; i < FIXED_IDS.length; i++) {
			const key = String(FIXED_IDS[i]);
			fixedChanged[key] = before.compare[key] !== after.compare[key];
		}
		return {
			before_count: before.keys.size,
			after_count: after.keys.size,
			added: after.keys.size - retainedCount,
			removed: before.keys.size - retainedCount,
			retained: retainedCount,
			fixed_changed: fixedChanged
		};
	}

	// Observation never throws into the original chain; it latches instead.
	function observe(step) {
		if (settled || reasons.length) {
			return;
		}
		try {
			step();
		} catch (error) {
			latch(error instanceof Refused ? error.code : 'observer-exception');
		}
	}

	function eligible() {
		return (terminalSeen || thrownSeen) && pending === 0 && depth === 0;
	}

	function queueFinalize() {
		if (settled || finalizeQueued || !eligible()) {
			return;
		}
		finalizeQueued = true;
		Promise.resolve().then(finalize);
	}

	function finalize() {
		finalizeQueued = false;
		if (settled || !eligible()) {
			return;
		}
		settled = true;
		try {
			if (!terminalSeen) {
				latch('route-aborted');
			}
			let final = null;
			if (!reasons.length) {
				try {
					final = snapshot().view;
				} catch (error) {
					latch(error instanceof Refused ? error.code : 'observer-exception');
				}
			}
			if (reasons.length) {
				rejectRun(refusal());
				return;
			}
			const report = {
				branch: branch,
				current_session_equivalence: UNKNOWN,
				diagnostic_complete: true,
				final: final,
				initial: initial,
				internal_execution_errors: UNKNOWN,
				lookup_values: lookupValues,
				main_quest_semantic_result: UNKNOWN,
				observed_window: 'terminal-callback/finalization-microtask',
				original_lazyInit_executed: false,
				positive_control_present: final.fixed['21001'].own,
				producer_provenance: UNKNOWN,
				registration_and_append_call_counts: UNKNOWN,
				schema: 't10.005.quest-registration-diagnostic.v1',
				scope: 'original-private-loaders/reproduced-routing',
				stages: stages
			};
			if (utf8Length(JSON.stringify(report)) > MAX_REPORT_BYTES) {
				latch('report-budget');
				rejectRun(refusal());
				return;
			}
			resolveRun(report);
		} catch (error) {
			latch('observer-exception');
			rejectRun(refusal());
		}
	}

	function terminal() {
		if (terminalSeen) {
			latch('duplicate-terminal');
		}
		terminalSeen = true;
		queueFinalize();
	}

	function startInvocation(kind, path) {
		const invocation = { awaiting: true, stage: null };
		pending++;
		observe(() => {
			if (stages.length >= MAX_STAGES) {
				throw new Refused('stage-cap');
			}
			if (typeof path !== 'string') {
				throw new Refused('path-type');
			}
			charge(CHARGE_STAGE + utf8Length(JSON.stringify(path)));
			const before = snapshot();
			const record = { index: stages.length, kind: kind, path: path, before: before.view, callbacks: [] };
			stages.push(record);
			invocation.stage = { record: record, before: before };
		});
		return invocation;
	}

	function endInvocation(invocation) {
		if (invocation.awaiting) {
			invocation.awaiting = false;
			pending--;
		}
	}

	function delegate(loader, thisArg, args, invocation) {
		depth++;
		try {
			return Reflect.apply(loader, thisArg, args);
		} catch (error) {
			thrownSeen = true;
			latch('original-loader-throw');
			endInvocation(invocation);
			throw error;
		} finally {
			depth--;
			queueFinalize();
		}
	}

	function observedCallback(invocation, forward) {
		let calls = 0;
		return function observedCompletion() {
			const ordinal = calls++;
			if (ordinal > 0) {
				latch('duplicate-callback');
			}
			const argc = arguments.length;
			const first = arguments[0];
			observe(() => {
				const stage = invocation.stage;
				if (stage === null) {
					return;
				}
				charge(CHARGE_CALLBACK + CHARGE_AGGREGATE);
				const after = snapshot();
				stage.record.callbacks.push({
					ordinal: ordinal,
					argc: argc,
					first_boolean: typeof first === 'boolean' ? first : NOT_REPORTED,
					after: after.view,
					aggregate: aggregate(stage.before, after)
				});
			});
			endInvocation(invocation);
			depth++;
			try {
				return Reflect.apply(forward, this, arguments);
			} catch (error) {
				thrownSeen = true;
				latch('original-callback-throw');
				throw error;
			} finally {
				depth--;
				queueFinalize();
			}
		};
	}

	// Passed as tryLoadLuaAliases' rFunc and reused for SystemEN/custom calls.
	function observedLoader() {
		const args = [];
		for (let i = 0; i < arguments.length; i++) {
			args.push(arguments[i]);
		}
		const invocation = startInvocation(phase, args[0]);
		args[2] = observedCallback(invocation, args[2]);
		return delegate(loadQuestInfo, this, args, invocation);
	}

	function admitCustom(list) {
		if (!Array.isArray(list)) {
			throw new Refused('custom-not-array');
		}
		const length = Object.getOwnPropertyDescriptor(list, 'length').value;
		if (length > MAX_CUSTOM) {
			throw new Refused('custom-count-cap');
		}
		const keys = Reflect.ownKeys(list);
		for (let i = 0; i < keys.length; i++) {
			if (typeof keys[i] !== 'string') {
				throw new Refused('custom-symbol-key');
			}
		}
		if (keys.length !== length + 1) {
			throw new Refused('custom-not-dense');
		}
		for (let i = 0; i < length; i++) {
			const descriptor = Object.getOwnPropertyDescriptor(list, String(i));
			if (descriptor === undefined) {
				throw new Refused('custom-not-dense');
			}
			if (!('value' in descriptor)) {
				throw new Refused('accessor');
			}
			const path = descriptor.value;
			if (typeof path !== 'string' || path.length === 0 || path.length > MAX_CUSTOM_PATH || path.indexOf('\0') !== -1) {
				throw new Refused('custom-invalid-entry');
			}
		}
	}

	async function run() {
		// DBManager lazyInit startup steps, unchanged.
		await lookTables?.catch(() => {});
		try {
			await startLua();
		} catch (error) {
			throw new Refused('startLua-rejected');
		}

		const loadLua = Configs.get('loadLua');
		charge(CHARGE_REPORT);
		const lookup = { loadLua: typed(loadLua, 1, []), customQuestInfo: null, userCharpage: null };
		let customQuestInfo = null;
		if (loadLua) {
			customQuestInfo = Configs.get('customQuestInfo', []);
			admitCustom(customQuestInfo);
			lookup.customQuestInfo = typed(customQuestInfo, 1, []);
		}
		lookup.userCharpage = typed(userCharpage, 1, []);
		branch = loadLua ? 'lua' : 'text';
		lookupValues = lookup;
		initial = snapshot().view;

		depth++;
		try {
			if (loadLua) {
				// DBManager quest fragment: aliases, then SystemEN, then custom in
				// order, each continuing regardless of the reported boolean.
				const loadCustomQuestInfo = (index = 0) =>
					index < customQuestInfo.length
						? observedLoader(customQuestInfo[index], null, () => loadCustomQuestInfo(index + 1))
						: terminal();
				tryLoadLuaAliases(observedLoader, getSystemAliases('System/OngoingQuestInfoList.lub'), null, () => {
					phase = 'systemEN';
					observedLoader('SystemEN/OngoingQuests.lub', null, () => {
						phase = 'custom';
						loadCustomQuestInfo();
					});
				});
			} else {
				const invocation = startInvocation('text', 'data/questid2display.txt');
				const done = observedCallback(invocation, terminal);
				delegate(loadTable, undefined, ['data/questid2display.txt', '#', 6, parseQuestEntry, done, true], invocation);
			}
		} catch (error) {
			// The identical object already reached every original caller.
			thrownSeen = true;
			latch('original-route-throw');
		} finally {
			depth--;
			queueFinalize();
		}
	}

	run().then(undefined, error => {
		if (settled) {
			return;
		}
		settled = true;
		latch(error instanceof Refused ? error.code : 'pre-dispatch-exception');
		rejectRun(refusal());
	});
}();
