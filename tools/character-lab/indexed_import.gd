extends RefCounted
## Palette-indexed import adapter for generated slot boards (inspection A1–A3).
## Every output pixel is either transparent or an exact entry of one style palette,
## so characters imported with the same palette share colors and can later be
## written as indexed SPR data. No recentering, warping or per-slot resizing.
##
## Downscale: each target pixel covers a fractional block of the source board.
## Every source pixel inside it is classified (palette entry or key) and the
## majority wins, so a 1536-wide result of a 1440-wide reference imports the
## same as an exact 5x board would. Ties prefer the class nearest the block center.
##
## Key unmixing: an anti-aliased edge is modelled as t*key + (1-t)*palette color.
## Mostly-key pixels become transparent, the rest take the palette color, so no
## pink fringe survives on opaque pixels.
const ADAPTER := "indexed-majority-v1"
const TRANSPARENT := -1
# Classification is cached on 5-bit-per-channel bins; +-4 levels is far below
# the spacing between palette entries, and bounds the work to 32768 bins.
const BIN_SHIFT := 3
# Favour explaining a pixel with less key: a clean sprite color should not be
# re-labelled as a darker color blended with magenta.
const KEY_BLEND_PENALTY := 0.05


static func load_palette(path: String) -> Dictionary:
	var text := FileAccess.get_file_as_string(path)
	var data = JSON.parse_string(text)
	if typeof(data) != TYPE_DICTIONARY or not data.has("colors") or data.colors.is_empty():
		push_error("Invalid style palette: " + path)
		return {}
	var colors: Array[Color] = []
	for value in data.colors:
		colors.append(Color(value))
	var key := Color(data.get("key", "#ff00ff"))
	return {"id": data.get("id", path.get_file().get_basename()), "path": path, "sha256": FileAccess.get_sha256(path), "colors": colors, "key": key, "keyBlendThreshold": float(data.get("keyBlendThreshold", 0.5))}


## Returns the palette index for an 8-bit RGB color, or TRANSPARENT.
static func classify(palette: Dictionary, r: int, g: int, b: int) -> int:
	var key: Color = palette.key
	var kr := key.r8
	var kg := key.g8
	var kb := key.b8
	var best_cost := INF
	var best_index := TRANSPARENT
	var best_t := 1.0
	var colors: Array[Color] = palette.colors
	for i in colors.size():
		var p := colors[i]
		var pr := p.r8
		var pg := p.g8
		var pb := p.b8
		# Project (c - p) onto (key - p), clamp t to [0, 1].
		var dr := kr - pr
		var dg := kg - pg
		var db := kb - pb
		var length := float(dr * dr + dg * dg + db * db)
		var t := 0.0
		if length > 0.0:
			t = clampf(((r - pr) * dr + (g - pg) * dg + (b - pb) * db) / length, 0.0, 1.0)
		var er := r - (pr + t * dr)
		var eg := g - (pg + t * dg)
		var eb := b - (pb + t * db)
		var cost := er * er + eg * eg + eb * eb + KEY_BLEND_PENALTY * t * t * length
		if cost < best_cost:
			best_cost = cost
			best_index = i
			best_t = t
	return TRANSPARENT if best_t >= palette.keyBlendThreshold else best_index


## Downscale a generated board to `target` with block-majority palette classes.
## Returns {"image": Image (RGBA8, palette colors only), "indices": PackedInt32Array,
## "stats": Dictionary}.
static func import_board(source: Image, target: Vector2i, palette: Dictionary) -> Dictionary:
	var board: Image = source.duplicate()
	board.convert(Image.FORMAT_RGBA8)
	var width := board.get_width()
	var height := board.get_height()
	var data := board.get_data()
	var bins := {}
	var classes := PackedInt32Array()
	classes.resize(width * height)
	for y in height:
		for x in width:
			var offset := (y * width + x) * 4
			if data[offset + 3] < 128:
				classes[y * width + x] = TRANSPARENT
				continue
			var r := data[offset]
			var g := data[offset + 1]
			var b := data[offset + 2]
			var bin := ((r >> BIN_SHIFT) << 10) | ((g >> BIN_SHIFT) << 5) | (b >> BIN_SHIFT)
			if not bins.has(bin):
				var half := 1 << (BIN_SHIFT - 1)
				bins[bin] = classify(palette, ((r >> BIN_SHIFT) << BIN_SHIFT) + half, ((g >> BIN_SHIFT) << BIN_SHIFT) + half, ((b >> BIN_SHIFT) << BIN_SHIFT) + half)
			classes[y * width + x] = bins[bin]
	var colors: Array[Color] = palette.colors
	var out := Image.create(target.x, target.y, false, Image.FORMAT_RGBA8)
	var indices := PackedInt32Array()
	indices.resize(target.x * target.y)
	var ties := 0
	var mixed_blocks := 0
	var used := {}
	var scale := Vector2(float(width) / target.x, float(height) / target.y)
	for ty in target.y:
		var y0 := int(floor(ty * scale.y))
		var y1 := maxi(y0 + 1, int(floor((ty + 1) * scale.y)))
		for tx in target.x:
			var x0 := int(floor(tx * scale.x))
			var x1 := maxi(x0 + 1, int(floor((tx + 1) * scale.x)))
			var counts := {}
			for y in range(y0, mini(y1, height)):
				for x in range(x0, mini(x1, width)):
					var c: int = classes[y * width + x]
					counts[c] = counts.get(c, 0) + 1
			var center: int = classes[mini(height - 1, int((ty + 0.5) * scale.y)) * width + mini(width - 1, int((tx + 0.5) * scale.x))]
			var winner := center
			var winner_count := -1
			for c in counts:
				var n: int = counts[c]
				if n > winner_count or (n == winner_count and c == center):
					winner = c
					winner_count = n
			var tied := 0
			for c in counts:
				if counts[c] == winner_count:
					tied += 1
			if tied > 1:
				ties += 1
			if counts.size() > 1:
				mixed_blocks += 1
			indices[ty * target.x + tx] = winner
			if winner != TRANSPARENT:
				out.set_pixel(tx, ty, colors[winner])
				used[winner] = true
	var used_list := used.keys()
	used_list.sort()
	return {"image": out, "indices": indices, "stats": {
		"adapter": ADAPTER, "sourceSize": [width, height], "targetSize": [target.x, target.y],
		"blockSize": [scale.x, scale.y], "classifiedColorBins": bins.size(),
		"mixedBlocks": mixed_blocks, "tiedBlocks": ties, "paletteIndicesUsed": used_list,
	}}


## Diagnostics that must be zero for an accepted indexed import.
static func validate(image: Image, palette: Dictionary) -> Dictionary:
	var allowed := {}
	for color: Color in palette.colors:
		allowed[color.to_rgba32() | 0xff] = true
	var off_palette := 0
	var partial_alpha := 0
	var key_tinted := 0
	for y in image.get_height():
		for x in image.get_width():
			var color := image.get_pixel(x, y)
			if color.a8 == 0:
				continue
			if color.a8 != 255:
				partial_alpha += 1
			if not allowed.has(color.to_rgba32() | 0xff):
				off_palette += 1
			# Same model as import: an opaque pixel best explained as mostly key.
			if classify(palette, color.r8, color.g8, color.b8) == TRANSPARENT:
				key_tinted += 1
	return {"offPalettePixels": off_palette, "partialAlphaPixels": partial_alpha, "keyTintedPixels": key_tinted}


## Colors in one image, ignoring transparent pixels. For native/replacement comparison.
static func unique_colors(image: Image) -> int:
	var seen := {}
	for y in image.get_height():
		for x in image.get_width():
			var color := image.get_pixel(x, y)
			if color.a8 > 0:
				seen[color.to_rgba32()] = true
	return seen.size()


static func save_png(image: Image, path: String) -> bool:
	var error := image.save_png(path)
	if error != OK:
		push_error("Cannot save %s (error %d)" % [path, error])
		return false
	return true
