extends SceneTree
## Build a shared style palette (inspection A1) from accepted artwork.
## Deterministic median cut over opaque, non-key pixels; the result is a
## reviewable starting point, then edited and versioned by hand like any asset.
##
## Godot --headless --path . --script res://tools/character-lab/build_style_palette.gd -- \
##   --id=wayfarer-style-v1 --colors=48 --out=res://tools/character-lab/style/wayfarer-style-v1.json \
##   --inputs=res://a.png,res://b.png [--weighting=variance|range|population] [--refine=6]
const Indexed = preload("res://tools/character-lab/indexed_import.gd")

func _initialize() -> void:
	call_deferred("run")

func option(name: String, fallback: String = "") -> String:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--%s=" % name):
			return argument.trim_prefix("--%s=" % name)
	return fallback

func run() -> void:
	var inputs := option("inputs").split(",", false)
	var output := option("out")
	var count := int(option("colors", "48"))
	var id := option("id", output.get_file().get_basename())
	# population: favour large areas (skin, leather). range: favour distinct
	# materials even when small (a vest, a gem), closer to hand-made RO ramps.
	var weighting := option("weighting", "variance")
	if inputs.is_empty() or output.is_empty() or count < 2 or count > 255:
		push_error("Usage: --inputs=a.png,b.png --out=palette.json [--colors=48] [--id=name]")
		quit(1)
		return
	var pixels: Array[Color] = []
	var sources := []
	for path in inputs:
		var image := Image.load_from_file(path)
		if image == null:
			push_error("Cannot load " + path)
			quit(1)
			return
		image.convert(Image.FORMAT_RGBA8)
		var kept := 0
		for y in image.get_height():
			for x in image.get_width():
				var color := image.get_pixel(x, y)
				# Opaque pixels only; drop magenta-dominant key residue.
				if color.a8 < 255 or (color.r > 0.55 and color.b > 0.5 and color.g < color.r - 0.25 and color.g < color.b - 0.2):
					continue
				pixels.append(color)
				kept += 1
		sources.append({"file": path, "sha256": FileAccess.get_sha256(path), "pixels": kept})
	# Split in Oklab with chroma emphasised: a small teal vest and gray-violet
	# trousers differ mainly in hue, which plain RGB ranges under-weight.
	var entries: Array = []
	for color in pixels:
		entries.append([_oklab(color), color])
	var boxes: Array = [entries]
	while boxes.size() < count:
		var best := -1
		var best_score := 0.0
		for i in boxes.size():
			var box: Array = boxes[i]
			if box.size() < 2:
				continue
			var spread := _spread(box)
			# variance: total squared error (Wu-style); range: widest extent only.
			var score: float = spread.error if weighting == "variance" else spread.range * (sqrt(box.size()) if weighting == "population" else 1.0)
			if score > best_score:
				best_score = score
				best = i
		if best < 0:
			break
		var box: Array = boxes[best]
		var channel: int = _spread(box).channel
		box.sort_custom(func(a: Array, b: Array) -> bool: return a[0][channel] < b[0][channel] or (a[0][channel] == b[0][channel] and (a[1] as Color).to_rgba32() < (b[1] as Color).to_rgba32()))
		var middle := box.size() / 2
		boxes[best] = box.slice(0, middle)
		boxes.append(box.slice(middle))
	# Lloyd refinement in Oklab: reassign every pixel to its nearest centre.
	var centres: Array[Vector3] = []
	for box: Array in boxes:
		centres.append(_mean(box))
	for _pass in int(option("refine", "6")):
		var groups: Array = []
		for i in centres.size():
			groups.append([])
		for entry: Array in entries:
			groups[_nearest(centres, entry[0])].append(entry)
		for i in centres.size():
			if not groups[i].is_empty():
				centres[i] = _mean(groups[i])
		boxes = groups
	var colors: Array[Color] = []
	for box: Array in boxes:
		if box.is_empty():
			continue
		var sum := Vector3.ZERO
		for entry: Array in box:
			var color: Color = entry[1]
			sum += Vector3(color.r8, color.g8, color.b8)
		sum /= box.size()
		colors.append(Color8(roundi(sum.x), roundi(sum.y), roundi(sum.z)))
	colors.sort_custom(func(a: Color, b: Color) -> bool: return a.get_luminance() < b.get_luminance() or (a.get_luminance() == b.get_luminance() and a.to_rgba32() < b.to_rgba32()))
	var hexes := []
	for color in colors:
		hexes.append("#" + color.to_html(false))
	var data := {
		"schemaVersion": 1, "id": id, "key": "#ff00ff", "keyBlendThreshold": 0.5,
		"colors": hexes,
		"note": "Opaque style colors; transparency is separate (SPR index 0). Edit by hand, then bump id.",
		"derivedFrom": {"method": "median cut in Oklab (chroma x%s), %s split score, %s Lloyd passes, RGB cluster mean, luminance order" % [CHROMA_WEIGHT, weighting, option("refine", "6")], "requestedColors": count, "weighting": weighting, "sources": sources},
	}
	DirAccess.make_dir_recursive_absolute(ProjectSettings.globalize_path(output.get_base_dir()))
	var file := FileAccess.open(output, FileAccess.WRITE)
	file.store_string(JSON.stringify(data, "\t") + "\n")
	file.close()
	print("Palette %s: %d colors from %d pixels -> %s" % [id, colors.size(), pixels.size(), output])
	quit()

const CHROMA_WEIGHT := 1.0

static func _oklab(color: Color) -> Vector3:
	# sRGB -> Oklab (Ottosson 2020), scaled so L spans 0..100.
	var c := color.srgb_to_linear()
	var l := pow(0.4122214708 * c.r + 0.5363325363 * c.g + 0.0514459929 * c.b, 1.0 / 3.0)
	var m := pow(0.2119034982 * c.r + 0.6806995451 * c.g + 0.1073969566 * c.b, 1.0 / 3.0)
	var s := pow(0.0883024619 * c.r + 0.2817188376 * c.g + 0.6299787005 * c.b, 1.0 / 3.0)
	return Vector3(
		100.0 * (0.2104542553 * l + 0.7936177850 * m - 0.0040720468 * s),
		100.0 * CHROMA_WEIGHT * (1.9779984951 * l - 2.4285922050 * m + 0.4505937099 * s),
		100.0 * CHROMA_WEIGHT * (0.0259040371 * l + 0.7827717662 * m - 0.8086757660 * s))

static func _spread(box: Array) -> Dictionary:
	var low := Vector3(INF, INF, INF)
	var high := Vector3(-INF, -INF, -INF)
	for entry: Array in box:
		var v: Vector3 = entry[0]
		low = low.min(v)
		high = high.max(v)
	var mean := _mean(box)
	var error := 0.0
	for entry: Array in box:
		error += (entry[0] as Vector3).distance_squared_to(mean)
	var size := high - low
	var channel := 0
	for c in 3:
		if size[c] > size[channel]:
			channel = c
	return {"channel": channel, "range": size[channel], "error": error}

static func _mean(box: Array) -> Vector3:
	var sum := Vector3.ZERO
	for entry: Array in box:
		sum += entry[0]
	return sum / maxi(1, box.size())

static func _nearest(centres: Array[Vector3], value: Vector3) -> int:
	var best := 0
	var best_distance := INF
	for i in centres.size():
		var d := centres[i].distance_squared_to(value)
		if d < best_distance:
			best_distance = d
			best = i
	return best
