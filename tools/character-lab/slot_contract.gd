extends RefCounted
## Slot contract: size limits every replacement drawing must meet against its
## native SPR slot (inspection A4, "head size is a template rule"). The same
## numbers produce the generation brief and the import gate, so a prompt can
## never ask for something the gate does not verify, and vice versa.

## Measure one slot bitmap. `is_skin` classifies an opaque Color as face skin.
static func measure(image: Image, is_skin: Callable) -> Dictionary:
	var width := image.get_width()
	var height := image.get_height()
	var area := 0
	var edge := 0
	var skin := {}
	for y in height:
		for x in width:
			if image.get_pixel(x, y).a8 == 0:
				continue
			area += 1
			for offset: Vector2i in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
				var n := Vector2i(x, y) + offset
				if n.x < 0 or n.y < 0 or n.x >= width or n.y >= height or image.get_pixel(n.x, n.y).a8 == 0:
					edge += 1
					break
			# The face lives in the lower part of the head bitmap; hair highlights
			# above it can share skin-like colors in the native palette.
			if y >= floori(height * 0.45) and is_skin.call(image.get_pixel(x, y)):
				skin[Vector2i(x, y)] = true
	var face := _largest_component(skin)
	var used := image.get_used_rect()
	return {"area": area, "edgePixels": edge, "bbox": [used.position.x, used.position.y, used.size.x, used.size.y],
		"facePixels": face.size(), "faceBox": _box(face)}


## Heuristic for native RO skin, used once to derive the native face contract.
## Replacement art is classified by the style bible's tagged skin palette entries.
static func native_skin(color: Color) -> bool:
	return color.a8 > 0 and color.r > 0.78 and color.g > 0.55 and color.b > 0.45 and color.r - color.b > 0.1 and color.r - color.b < 0.4 and color.s < 0.45 and color.v > 0.8


static func palette_skin(palette: Dictionary, skin_indices: Array) -> Callable:
	var colors := {}
	for index in skin_indices:
		colors[(palette.colors[int(index)] as Color).to_rgba32() | 0xff] = true
	return func(color: Color) -> bool: return colors.has(color.to_rgba32() | 0xff)


## Returns {"pass": bool, "failures": [String], "metrics": {...}}.
static func check(part: String, native: Image, replacement: Image, rules: Dictionary, native_face: Dictionary, is_skin: Callable) -> Dictionary:
	var failures: Array[String] = []
	if native.get_size() != replacement.get_size():
		return {"pass": false, "failures": ["slot size %s differs from native %s" % [replacement.get_size(), native.get_size()]], "metrics": {}}
	var n := measure(native, native_skin)
	var r := measure(replacement, is_skin)
	var ratio := float(r.area) / maxi(1, n.area)
	var metrics := {"native": n, "replacement": r, "areaRatio": ratio, "alphaIoU": _iou(native, replacement)}
	var area_range: Array = rules.get("areaRatio", [0.0, INF])
	if ratio < float(area_range[0]) or ratio > float(area_range[1]):
		failures.append("%s area is %.0f%% of native (%d vs %d px); allowed %.0f%%-%.0f%%" % [part, ratio * 100, r.area, n.area, float(area_range[0]) * 100, float(area_range[1]) * 100])
	var tolerance := int(rules.get("bboxTolerance", 99))
	var nb: Array = n.bbox
	var rb: Array = r.bbox
	var edges := {"left": [nb[0], rb[0]], "top": [nb[1], rb[1]], "right": [nb[0] + nb[2], rb[0] + rb[2]], "bottom": [nb[1] + nb[3], rb[1] + rb[3]]}
	for side: String in edges:
		var pair: Array = edges[side]
		if absi(int(pair[0]) - int(pair[1])) > tolerance:
			failures.append("%s %s edge at %d, native %d (tolerance %d px)" % [part, side, pair[1], pair[0], tolerance])
	if metrics.alphaIoU < float(rules.get("alphaIoUMin", 0.0)):
		failures.append("%s silhouette overlap %.3f below %.2f" % [part, metrics.alphaIoU, float(rules.alphaIoUMin)])
	var roughness := float(r.edgePixels) / maxi(1, n.edgePixels)
	metrics["outlineRatio"] = roughness
	if roughness > float(rules.get("outlineRatioMax", INF)):
		failures.append("%s outline is %.0f%% of native length (gaps/spikes); max %.0f%%" % [part, roughness * 100, float(rules.outlineRatioMax) * 100])
	if rules.has("face") and not native_face.is_empty():
		var face_rules: Dictionary = rules.face
		var face_ratio := float(r.facePixels) / maxi(1, int(native_face.pixels))
		metrics["faceRatio"] = face_ratio
		if face_ratio < float(face_rules.minRatio):
			failures.append("face skin is %.0f%% of native (%d vs %d px); min %.0f%%" % [face_ratio * 100, r.facePixels, native_face.pixels, float(face_rules.minRatio) * 100])
		var fb: Array = r.faceBox
		var nf: Array = native_face.box
		var slack := int(face_rules.boxTolerance)
		if fb.is_empty():
			failures.append("no face skin found in the lower head")
		else:
			if int(fb[2]) < int(nf[2]) - slack:
				failures.append("face width %d px, native %d (min %d)" % [fb[2], nf[2], int(nf[2]) - slack])
			if int(fb[3]) < int(nf[3]) - slack:
				failures.append("face height %d px, native %d (min %d)" % [fb[3], nf[3], int(nf[3]) - slack])
	return {"pass": failures.is_empty(), "failures": failures, "metrics": metrics}


## Prompt section generated from the same limits the gate enforces.
## `offset`/`scale` convert slot pixels to the reference board sent to ImageGen.
static func brief(part: String, native: Image, rules: Dictionary, native_face: Dictionary, offset: Vector2i, scale: int) -> String:
	var n := measure(native, native_skin)
	var b: Array = n.bbox
	var area_range: Array = rules.areaRatio
	var lines := ["SIZE CONTRACT (checked automatically after generation; a candidate outside it is rejected, not repaired):"]
	lines.append("- Fill the native %s silhouette: total opaque %s area %d%%-%d%% of the native %d logical pixels. Do not draw it smaller or thinner." % [part, part, roundi(float(area_range[0]) * 100), roundi(float(area_range[1]) * 100), n.area])
	lines.append("- Outer bounds within %d logical pixel(s) of the native box: slot x%d-x%d, y%d-y%d (reference board pixels x%d-x%d, y%d-y%d)." % [
		int(rules.bboxTolerance), b[0], b[0] + b[2] - 1, b[1], b[1] + b[3] - 1,
		(b[0] + offset.x) * scale, (b[0] + b[2] + offset.x) * scale - 1, (b[1] + offset.y) * scale, (b[1] + b[3] + offset.y) * scale - 1])
	if rules.has("outlineRatioMax"):
		lines.append("- Keep a solid, rounded outer outline like the native drawing (outline length at most %d%% of native): no see-through gaps between locks, no thin isolated spikes." % roundi(float(rules.outlineRatioMax) * 100))
	if rules.has("face") and not native_face.is_empty():
		var f: Array = native_face.box
		lines.append("- Face: visible skin at least %d%% of the native face (%d logical pixels), spanning about slot x%d-x%d, y%d-y%d (board x%d-x%d, y%d-y%d). Keep RO's large rounded face, full cheek and jaw; hair must not cover or shrink it." % [
			roundi(float(rules.face.minRatio) * 100), native_face.pixels, f[0], f[0] + f[2] - 1, f[1], f[1] + f[3] - 1,
			(f[0] + offset.x) * scale, (f[0] + f[2] + offset.x) * scale - 1, (f[1] + offset.y) * scale, (f[1] + f[3] + offset.y) * scale - 1])
	return "\n".join(lines)


static func _largest_component(cells: Dictionary) -> Array:
	var seen := {}
	var best: Array = []
	for start: Vector2i in cells:
		if seen.has(start):
			continue
		var component: Array = []
		var stack: Array = [start]
		seen[start] = true
		while not stack.is_empty():
			var cell: Vector2i = stack.pop_back()
			component.append(cell)
			for offset: Vector2i in [Vector2i(1, 0), Vector2i(-1, 0), Vector2i(0, 1), Vector2i(0, -1)]:
				var n := cell + offset
				if cells.has(n) and not seen.has(n):
					seen[n] = true
					stack.append(n)
		if component.size() > best.size():
			best = component
	return best


static func _box(cells: Array) -> Array:
	if cells.is_empty():
		return []
	var low := Vector2i(1 << 20, 1 << 20)
	var high := Vector2i(-1, -1)
	for cell: Vector2i in cells:
		low = low.min(cell)
		high = high.max(cell)
	return [low.x, low.y, high.x - low.x + 1, high.y - low.y + 1]


static func _iou(a: Image, b: Image) -> float:
	var both := 0
	var either := 0
	for y in a.get_height():
		for x in a.get_width():
			var pa := a.get_pixel(x, y).a8 > 0
			var pb := b.get_pixel(x, y).a8 > 0
			if pa and pb: both += 1
			if pa or pb: either += 1
	return float(both) / either if either > 0 else 1.0
