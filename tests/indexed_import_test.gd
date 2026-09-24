extends SceneTree
## Run: Godot --headless --path . --script res://tests/indexed_import_test.gd
## Synthetic images only; needs no local RO or generated assets.

const Indexed = preload("res://tools/character-lab/indexed_import.gd")
const KEY := Color("ff00ff")
var checks := 0
var failures := 0
var palette := {}

func _initialize() -> void:
	palette = _palette(["#2a1d17", "#e8c39e", "#3b6b68", "#6a5a78"])
	_test_classify_pure_and_key()
	_test_fringe_is_unmixed()
	_test_violet_is_not_keyed()
	_test_grid_independent_downscale()
	_test_validate_flags_off_palette()
	if failures == 0 and checks >= 13:
		print("INDEXED_IMPORT_TEST_PASS (%d checks)" % checks)
	else:
		push_error("INDEXED_IMPORT_TEST_FAIL: %d of %d checks" % [failures, checks])
	quit(1 if failures else 0)


func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(message)


func _palette(hexes: Array) -> Dictionary:
	var colors: Array[Color] = []
	for value: String in hexes:
		colors.append(Color(value))
	return {"id": "test", "colors": colors, "key": KEY, "keyBlendThreshold": 0.5}


func _rgb(color: Color) -> Array:
	return [color.r8, color.g8, color.b8]


func _test_classify_pure_and_key() -> void:
	for i in palette.colors.size():
		var c: Array = _rgb(palette.colors[i])
		check(Indexed.classify(palette, c[0], c[1], c[2]) == i, "Exact palette color %d must map to itself" % i)
	check(Indexed.classify(palette, 255, 0, 255) == Indexed.TRANSPARENT, "Pure key must be transparent")
	check(Indexed.classify(palette, 250, 8, 245) == Indexed.TRANSPARENT, "Near key must be transparent")


func _test_fringe_is_unmixed() -> void:
	var outline: Color = palette.colors[0]
	var light := outline.lerp(KEY, 0.3)
	var heavy := outline.lerp(KEY, 0.75)
	check(Indexed.classify(palette, light.r8, light.g8, light.b8) == 0, "30% key blend of the outline must stay outline")
	check(Indexed.classify(palette, heavy.r8, heavy.g8, heavy.b8) == Indexed.TRANSPARENT, "75% key blend must be transparent")


func _test_violet_is_not_keyed() -> void:
	# The Wayfarer trousers are gray-violet: close in hue to the key but in the palette.
	var violet: Color = palette.colors[3]
	check(Indexed.classify(palette, violet.r8 + 3, violet.g8 - 2, violet.b8 + 4) == 3, "Noisy palette violet must not become transparent or another color")


func _board(scale: float) -> Image:
	# 6x4 logical pixel pattern drawn at a (possibly fractional) scale, with noise
	# and a magenta blend on every boundary to imitate generated output.
	var pattern := [
		[-1, 0, 0, 0, 0, -1],
		[0, 1, 1, 2, 2, 0],
		[0, 1, 3, 3, 2, 0],
		[-1, 0, 0, 0, 0, -1],
	]
	var width := int(round(6 * scale))
	var height := int(round(4 * scale))
	var image := Image.create(width, height, false, Image.FORMAT_RGBA8)
	var rng := RandomNumberGenerator.new()
	rng.seed = 7
	for y in height:
		for x in width:
			var lx := mini(5, int(x / scale))
			var ly := mini(3, int(y / scale))
			var index: int = pattern[ly][lx]
			var color: Color = KEY if index < 0 else palette.colors[index]
			var edge := fposmod(x / scale, 1.0) < 0.12 or fposmod(y / scale, 1.0) < 0.12
			if edge and index >= 0:
				color = color.lerp(KEY, 0.25)
			color = Color(clampf(color.r + rng.randf_range(-0.02, 0.02), 0, 1), clampf(color.g + rng.randf_range(-0.02, 0.02), 0, 1), clampf(color.b + rng.randf_range(-0.02, 0.02), 0, 1))
			image.set_pixel(x, y, color)
	return image


func _test_grid_independent_downscale() -> void:
	var exact: Dictionary = Indexed.import_board(_board(5.0), Vector2i(6, 4), palette)
	var fractional: Dictionary = Indexed.import_board(_board(5.3333), Vector2i(6, 4), palette)
	var expected := PackedInt32Array([-1, 0, 0, 0, 0, -1, 0, 1, 1, 2, 2, 0, 0, 1, 3, 3, 2, 0, -1, 0, 0, 0, 0, -1])
	check(exact.indices == expected, "5x board must recover the logical pixels: %s" % [exact.indices])
	check(fractional.indices == expected, "5.33x board must recover the same logical pixels: %s" % [fractional.indices])
	var result: Dictionary = Indexed.validate(fractional.image, palette)
	check(result.offPalettePixels == 0 and result.keyTintedPixels == 0 and result.partialAlphaPixels == 0, "Indexed output must be clean: %s" % [result])


func _test_validate_flags_off_palette() -> void:
	var image := Image.create(3, 1, false, Image.FORMAT_RGBA8)
	image.set_pixel(0, 0, Color(0.9, 0.1, 0.85))
	# Dark fringe: the outline blended 60% with magenta.
	image.set_pixel(1, 0, (palette.colors[0] as Color).lerp(KEY, 0.6))
	image.set_pixel(2, 0, Color(0.5, 0.5, 0.5, 0.5))
	var result: Dictionary = Indexed.validate(image, palette)
	check(result.offPalettePixels == 3 and result.keyTintedPixels == 2 and result.partialAlphaPixels == 1, "Validation must count every defect: %s" % [result])
