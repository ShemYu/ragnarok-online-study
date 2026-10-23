// T07.006.002: fixed source patch for request-local ordinary-portal guidance.
//
// applyNavigationPortalPolicy(onlineText, workerText) verifies the two pinned
// inputs, applies a fixed list of exact literal hunks inside the retained
// Navigation module and its sibling PathFindingWorker, and returns the patched
// texts. It performs no file, network or process access and executes nothing.
// Hunk literals below are exact source text (tabs and LF included); they are
// data, not a template language.
"use strict";

const crypto = require("crypto");

const PINS = Object.freeze({
  online: Object.freeze({ bytes: 13174290, sha256: "50b724b708393d7bb6d71b4f5102e62b16e340eb1bb54f05b1c8613af4116418" }),
  worker: Object.freeze({ bytes: 5291, sha256: "e3b5db57a3cfd1bb83daf9a49fa656af18fda470b34807c0f52cbc65b503c85d" }),
});
const CAPS = Object.freeze({ online: 13239826, worker: 38059 });
const NAVIGATION_REGION = Object.freeze([
  "//#region src/UI/Components/Navigation/Navigation.js\n",
  "//#endregion\n//#region src/UI/Components/WorldMap/WorldMap.js\n",
]);

const HOST_HUNKS = [
  ["host-policy-helpers", `function resetPathFindingWorker() {
	terminatePathFindingWorker();
	initializePathFindingWorker();
}
`, `function resetPathFindingWorker() {
	terminatePathFindingWorker();
	initializePathFindingWorker();
}
var NAVIGATION_PORTAL_POLICY = "ordinary-portals-only";
var NAVIGATION_TAGGED_DEADLINE_MS = 5e3;
var _navigationAttached = false;
var _navigationRequestGeneration = 0;
var _navigationTaggedPending = null;
var _navigationTaggedJob = null;
function navigationLinkTypes(linkPolicy) {
	return linkPolicy === NAVIGATION_PORTAL_POLICY ? [200] : null;
}
function navigationNow() {
	return performance.now();
}
function readNavigationLinkPolicy(options) {
	if (!options || options.linkPolicy === void 0) return void 0;
	return options.linkPolicy === NAVIGATION_PORTAL_POLICY ? NAVIGATION_PORTAL_POLICY : false;
}
function isValidTaggedNavigationRequest(options) {
	for (const key of ["startMap", "endMap"]) if (typeof options[key] !== "string" || !normalizeMapName(options[key])) return false;
	for (const key of ["startX", "startY", "endX", "endY"]) if (!Number.isInteger(options[key]) || options[key] < 0) return false;
	return true;
}
function getTaggedPlayerPosition() {
	const entity = SessionStorage_default.Entity;
	if (!entity || !entity.position) return null;
	const x = Math.ceil(entity.position[0]);
	const y = Math.ceil(entity.position[1]);
	return Number.isInteger(x) && Number.isInteger(y) && x >= 0 && y >= 0 ? { x, y } : null;
}
function invalidateTaggedNavigation() {
	if (_navigationTaggedJob) _pathUpdateLock = false;
	_navigationRequestGeneration++;
	_navigationTaggedPending = null;
	_navigationTaggedJob = null;
}
function finishTaggedNavigation(record, state) {
	if (record !== _navigationTaggedPending) return true;
	record.state = state;
	_navigationTaggedJob = null;
	_targetData = null;
	Navigation.clearPath();
	Navigation.setTargetCoordinatesBlinking(false);
	return true;
}
function retainedNavigationOptions(mapName) {
	const linkPolicy = _finalTargetData.linkPolicy;
	const position = linkPolicy ? getTaggedPlayerPosition() : getPlayerPosition();
	if (!position) return null;
	const options = {
		startMap: mapName,
		startX: position.x,
		startY: position.y,
		endMap: _finalTargetData.map,
		endX: _finalTargetData.x,
		endY: _finalTargetData.y,
		displayName: _finalTargetData.displayName
	};
	if (linkPolicy) options.linkPolicy = linkPolicy;
	return options;
}
function maintainTaggedNavigation(tick) {
	if (!_navigationAttached || !getTaggedPlayerPosition()) return;
	if (this.hasReachedTarget()) {
		this.completeNavigation();
		return;
	}
	if (!(tick - _lastPathUpdate > _pathUpdateThrottle)) return;
	_lastPathUpdate = tick;
	const retained = retainedNavigationOptions(getCurrentMap());
	if (retained) this.navigateTo(retained);
}
function startTaggedNavigation(startMap, endMap, options, displayName) {
	const currentMap = getCurrentMap();
	if (!_navigationAttached || !currentMap) return true;
	const linkPolicy = _finalTargetData.linkPolicy;
	const key = [startMap, currentMap, endMap, options.endX, options.endY, linkPolicy].join("|");
	const now = navigationNow();
	const pending = _navigationTaggedPending;
	if (pending && pending.key === key && pending.state !== "done") {
		if (pending.state !== "unavailable" && now >= pending.deadline) finishTaggedNavigation(pending, "unavailable");
		return true;
	}
	if (_navigationTaggedJob) _pathUpdateLock = false;
	const record = {
		key,
		generation: ++_navigationRequestGeneration,
		map: currentMap,
		linkPolicy,
		deadline: now + NAVIGATION_TAGGED_DEADLINE_MS,
		state: "waiting",
		result: null
	};
	_navigationTaggedPending = record;
	_navigationTaggedJob = null;
	if (startMap !== currentMap) return finishTaggedNavigation(record, "unavailable");
	const path = MapPathFinder.findPathBetweenMaps(startMap, options.startX, options.startY, endMap, options.endX, options.endY, navigationLinkTypes(linkPolicy));
	if (!path || !path.length) return finishTaggedNavigation(record, "unavailable");
	const target = path[0];
	this.waitForMapData(function() {
		const walkableCell = this.findClosestWalkableCell(target.x, target.y);
		if (!walkableCell) return finishTaggedNavigation(record, "unavailable");
		_targetData = {
			x: walkableCell.x,
			y: walkableCell.y,
			map: target.map,
			displayName
		};
		this.findPath(options.startX, options.startY, _targetData.x, _targetData.y, record);
	}, () => {
		if (record !== _navigationTaggedPending || record.state !== "waiting" || !_navigationAttached) return false;
		if (getCurrentMap() !== record.map || navigationNow() >= record.deadline) {
			finishTaggedNavigation(record, "unavailable");
			return false;
		}
		return true;
	});
	return true;
}
function navigationRequestFields(request) {
	return request ? {
		requestGeneration: request.generation,
		requestMap: request.map,
		linkPolicy: request.linkPolicy
	} : {};
}
function acceptNavigationPathResult(worker, data) {
	if (worker !== _pathFindingWorker) return false;
	const job = _navigationTaggedJob;
	if (data.requestGeneration === void 0 && data.requestMap === void 0 && data.linkPolicy === void 0) return !job && !(_finalTargetData && _finalTargetData.linkPolicy);
	const record = job && job.record;
	if (!record || job.worker !== worker || record !== _navigationTaggedPending || record.state !== "worker" || !_navigationAttached) return false;
	if (data.workerId !== worker.id || data.requestGeneration !== record.generation || data.requestMap !== record.map || data.linkPolicy !== record.linkPolicy) return false;
	if (!_finalTargetData || _finalTargetData.linkPolicy !== record.linkPolicy || getCurrentMap() !== record.map || !Array.isArray(data.path)) return false;
	if (navigationNow() >= record.deadline) {
		finishTaggedNavigation(record, "unavailable");
		return false;
	}
	_navigationTaggedJob = null;
	record.state = "done";
	record.result = data.path.length ? "routed" : "empty";
	return true;
}
`],
  ["host-worker-result-fence", `		_pathFindingWorker.onmessage = function(e) {
			const data = e.data;
			switch (data.type) {
				case "pathResult":
					_pathUpdateLock = false;
`, `		const worker = _pathFindingWorker;
		_pathFindingWorker.onmessage = function(e) {
			const data = e.data;
			switch (data.type) {
				case "pathResult":
					if (!acceptNavigationPathResult(worker, data)) break;
					_pathUpdateLock = false;
`],
  ["host-on-append", `		initializePathFindingWorker();
		const mapName = getCurrentMap();
		this.loadMap(mapName);
		if (_finalTargetData) {
			const currentPos = getPlayerPosition();
			this.navigateTo({
				startMap: mapName,
				startX: currentPos.x,
				startY: currentPos.y,
				endMap: _finalTargetData.map,
				endX: _finalTargetData.x,
				endY: _finalTargetData.y,
				displayName: _finalTargetData.displayName
			});
		}
	};
`, `		initializePathFindingWorker();
		if (!_navigationAttached) invalidateTaggedNavigation();
		_navigationAttached = true;
		const mapName = getCurrentMap();
		this.loadMap(mapName);
		if (_finalTargetData) {
			const retained = retainedNavigationOptions(mapName);
			if (retained) this.navigateTo(retained);
		}
	};
`],
  ["host-on-remove", `	Navigation.onRemove = function onRemove() {
		this.clearPath();
`, `	Navigation.onRemove = function onRemove() {
		this.clearPath();
		_navigationAttached = false;
		invalidateTaggedNavigation();
`],
  ["host-clear", `	Navigation.clear = function clear() {
		this.clearPath();
`, `	Navigation.clear = function clear() {
		this.clearPath();
		invalidateTaggedNavigation();
`],
  ["host-complete", `	Navigation.completeNavigation = function completeNavigation() {
		if (!_finalTargetData) return;
`, `	Navigation.completeNavigation = function completeNavigation() {
		if (!_finalTargetData) return;
		invalidateTaggedNavigation();
`],
  ["host-render-maintenance", `	Navigation.renderCanvas = function renderCanvas(tick) {
`, `	Navigation.renderCanvas = function renderCanvas(tick) {
		if (_finalTargetData && _finalTargetData.linkPolicy) maintainTaggedNavigation.call(this, tick);
`],
  ["host-render-manual-only", `		if (_finalTargetData && tick - _lastPathUpdate > _pathUpdateThrottle && !_pathUpdateLock) {
`, `		if (_finalTargetData && !_finalTargetData.linkPolicy && tick - _lastPathUpdate > _pathUpdateThrottle && !_pathUpdateLock) {
`],
  ["host-find-path-signature", `	Navigation.findPath = function findPath(startX, startY, endX, endY) {
`, `	Navigation.findPath = function findPath(startX, startY, endX, endY, request) {
`],
  ["host-find-path-local-links", `				if (srcMap === currentMap && destMap === currentMap) warps.push({
`, `				if (srcMap === currentMap && destMap === currentMap && (!request || navigationLinkTypes(request.linkPolicy).indexOf(warp[2]) !== -1)) warps.push({
`],
  ["host-find-path-job", `			_mapData.warps = warps;
`, `			_mapData.warps = warps;
			if (request) {
				request.state = "worker";
				_navigationTaggedJob = {
					record: request,
					worker: _pathFindingWorker
				};
			}
`],
  ["host-find-path-message", `				existingPath: _path
`, `				existingPath: request ? null : _path,
				...navigationRequestFields(request)
`],
  ["host-show", `		if (_finalTargetData) this.navigateTo({
			startMap: mapName,
			startX: currentPos.x,
			startY: currentPos.y,
			endMap: _finalTargetData.map,
			endX: _finalTargetData.x,
			endY: _finalTargetData.y,
			displayName: _finalTargetData.displayName
		});
`, `		const retained = _finalTargetData && retainedNavigationOptions(mapName);
		if (retained) this.navigateTo(retained);
`],
  ["host-wait-fence", `	Navigation.waitForMapData = function waitForMapData(callback) {
		if (!_mapData || _mapData.map !== getCurrentMap()) setTimeout(() => {
			Navigation.waitForMapData(callback);
		}, 100);
`, `	Navigation.waitForMapData = function waitForMapData(callback, guard) {
		if (guard && !guard()) return;
		if (!_mapData || _mapData.map !== getCurrentMap()) setTimeout(() => {
			Navigation.waitForMapData(callback, guard);
		}, 100);
`],
  ["host-navigate-policy", `	Navigation.navigateTo = function navigateTo(options) {
		const root = Navigation.getRoot();
		const startMap = normalizeMapName(options.startMap);
		const endMap = normalizeMapName(options.endMap);
		const displayName = options.displayName;
		if (_finalTargetData && (_finalTargetData.map !== endMap || _finalTargetData.x !== options.endX || _finalTargetData.y !== options.endY)) {
			this.clearPath();
			resetPathFindingWorker();
`, `	Navigation.navigateTo = function navigateTo(options) {
		const linkPolicy = readNavigationLinkPolicy(options);
		if (linkPolicy === false || linkPolicy && !isValidTaggedNavigationRequest(options)) return false;
		const root = Navigation.getRoot();
		const startMap = normalizeMapName(options.startMap);
		const endMap = normalizeMapName(options.endMap);
		const displayName = options.displayName;
		if (_finalTargetData && (_finalTargetData.map !== endMap || _finalTargetData.x !== options.endX || _finalTargetData.y !== options.endY || _finalTargetData.linkPolicy !== linkPolicy)) {
			this.clearPath();
			invalidateTaggedNavigation();
			if (linkPolicy && !_navigationAttached) terminatePathFindingWorker();
			else resetPathFindingWorker();
`],
  ["host-navigate-tagged-branch", `			y: options.endY,
			displayName
		};
		let warpTypes = [200, 201];
`, `			y: options.endY,
			displayName
		};
		if (linkPolicy) {
			_finalTargetData.linkPolicy = linkPolicy;
			return startTaggedNavigation.call(this, startMap, endMap, options, displayName);
		}
		let warpTypes = [200, 201];
`],
  ["host-manual-wait-generation", `			const target = path[0];
			this.waitForMapData(function() {
`, `			const target = path[0];
			const generation = _navigationRequestGeneration;
			this.waitForMapData(function() {
`],
  ["host-manual-wait-guard-status", `				} else this.clear();
			});
		}
	};
	Navigation_default = UIManager.addComponent(Navigation);
`, `				} else this.clear();
			}, () => generation === _navigationRequestGeneration);
		}
	};
	Navigation.getLinkPolicyStatus = function getLinkPolicyStatus() {
		const linkPolicy = _finalTargetData && _finalTargetData.linkPolicy || null;
		const record = linkPolicy && _navigationAttached ? _navigationTaggedPending : null;
		return {
			linkPolicy,
			active: Boolean(linkPolicy && _navigationAttached),
			requestGeneration: record ? record.generation : null,
			requestMap: record ? record.map : null,
			state: !linkPolicy ? "none" : !_navigationAttached ? "inactive" : !record ? "idle" : record.state === "done" ? record.result : record.state
		};
	};
	Navigation_default = UIManager.addComponent(Navigation);
`],
];

const WORKER_HUNKS = [
  ["worker-policy-request", `			case "findPath": {
				const path = findPath(data.startX, data.startY, data.endX, data.endY, data.mapData, data.existingPath);
`, `			case "findPath": {
				if (data.linkPolicy !== void 0) {
					const allowedTypes = data.linkPolicy === "ordinary-portals-only" ? [200] : null;
					const mapData = allowedTypes ? Object.assign({}, data.mapData, { warps: (data.mapData.warps || []).filter((warp) => warp && allowedTypes.indexOf(warp.type) !== -1) }) : null;
					self.postMessage({
						type: "pathResult",
						path: mapData ? findPath(data.startX, data.startY, data.endX, data.endY, mapData, null) : null,
						workerId: data.workerId,
						requestGeneration: data.requestGeneration,
						requestMap: data.requestMap,
						linkPolicy: data.linkPolicy
					});
					break;
				}
				const path = findPath(data.startX, data.startY, data.endX, data.endY, data.mapData, data.existingPath);
`],
];

for (const hunk of HOST_HUNKS.concat(WORKER_HUNKS)) Object.freeze(hunk);
Object.freeze(HOST_HUNKS);
Object.freeze(WORKER_HUNKS);

function sha256(text) {
  return crypto.createHash("sha256").update(text, "utf8").digest("hex");
}

function uniqueIndex(text, literal, label) {
  const at = text.indexOf(literal);
  if (at < 0 || text.indexOf(literal, at + 1) !== -1) throw new Error(label + ": anchor is missing or not unique; refusing to patch");
  return at;
}

function patchText(label, text, pin, cap, hunks, region) {
  if (typeof text !== "string") throw new TypeError(label + ": source must be a string");
  if (Buffer.byteLength(text, "utf8") !== pin.bytes || sha256(text) !== pin.sha256) {
    throw new Error(label + ": source size/SHA256 differs from the pinned input; refusing to patch");
  }
  let low = 0;
  let high = text.length;
  if (region) {
    low = uniqueIndex(text, region[0], label + " region start");
    high = uniqueIndex(text, region[1], label + " region end") + "//#endregion\n".length;
    if (high <= low) throw new Error(label + ": region bounds out of order; refusing to patch");
  }
  const located = hunks.map(([name, before, after]) => {
    const at = uniqueIndex(text, before, label + " " + name);
    if (at < low || at + before.length > high) throw new Error(label + " " + name + ": anchor outside the pinned module; refusing to patch");
    return { at, before, after };
  }).sort((a, b) => a.at - b.at);
  const parts = [];
  let cursor = 0;
  for (const hunk of located) {
    if (hunk.at < cursor) throw new Error(label + ": overlapping hunks; refusing to patch");
    parts.push(text.slice(cursor, hunk.at), hunk.after);
    cursor = hunk.at + hunk.before.length;
  }
  parts.push(text.slice(cursor));
  const patched = parts.join("");
  if (Buffer.byteLength(patched, "utf8") > cap) throw new Error(label + ": patched size exceeds the frozen cap");
  return patched;
}

function applyNavigationPortalPolicy(onlineText, workerText) {
  const patchedOnline = patchText("online", onlineText, PINS.online, CAPS.online, HOST_HUNKS, NAVIGATION_REGION);
  const patchedWorker = patchText("worker", workerText, PINS.worker, CAPS.worker, WORKER_HUNKS, null);
  return { onlineText: patchedOnline, workerText: patchedWorker };
}

module.exports = { applyNavigationPortalPolicy, PINS, CAPS, NAVIGATION_REGION, HOST_HUNKS, WORKER_HUNKS };
