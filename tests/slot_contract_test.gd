extends SceneTree
## Run: Godot --headless --path . --script res://tests/slot_contract_test.gd
## Synthetic heads only; needs no local RO or generated assets.

const Contract = preload("res://tools/character-lab/slot_contract.gd")
const HAIR := Color("8a5842")
const SKIN := Color("f8ce9d")
const RULES := {"areaRatio": [0.95, 1.10], "bboxTolerance": 1, "alphaIoUMin": 0.80, "outlineRatioMax": 1.25, "face": {"minRatio": 0.80, "boxTolerance": 2}}
var checks := 0
var failures := 0
var is_skin := func(color: Color) -> bool: return color.to_rgba32() == SKIN.to_rgba32()

func _initialize() -> void:
	var native := head(14.0, Rect2i(10, 16, 10, 8))
	var face: Dictionary = Contract.measure(native, is_skin)
	var native_face := {"box": face.faceBox, "pixels": face.facePixels}
	var same: Dictionary = Contract.check("head", native, native.duplicate(), RULES, native_face, is_skin)
	check(same.pass, "An identical head must pass: %s" % [same.failures])
	var small: Dictionary = Contract.check("head", native, head(12.0, Rect2i(10, 16, 10, 8)), RULES, native_face, is_skin)
	check(not small.pass and _mentions(small, "area") and _mentions(small, "edge"), "A smaller head must fail on area and bounds: %s" % [small.failures])
	var tiny_face: Dictionary = Contract.check("head", native, head(14.0, Rect2i(12, 18, 5, 5)), RULES, native_face, is_skin)
	check(not tiny_face.pass and _mentions(tiny_face, "face skin") and _mentions(tiny_face, "face width"), "A shrunken face must fail: %s" % [tiny_face.failures])
	var spiky := head(14.0, Rect2i(10, 16, 10, 8))
	for x in range(2, 28, 2):
		for y in range(0, 6):
			spiky.set_pixel(x, y, Color(0, 0, 0, 0))
	var rough: Dictionary = Contract.check("head", native, spiky, RULES, native_face, is_skin)
	check(not rough.pass and _mentions(rough, "outline"), "Gappy hair must fail on outline length: %s" % [rough.failures])
	var text := Contract.brief("head", native, RULES, native_face, Vector2i(17, 19), 16)
	check(text.contains("%d logical pixels" % Contract.measure(native, is_skin).area) and text.contains("board") and text.contains("%d logical pixels" % native_face.pixels), "Brief must state the same numbers the gate checks:\n" + text)
	if failures == 0 and checks >= 5:
		print("SLOT_CONTRACT_TEST_PASS (%d checks)" % checks)
	else:
		push_error("SLOT_CONTRACT_TEST_FAIL: %d of %d checks" % [failures, checks])
	quit(1 if failures or checks < 5 else 0)


func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(message)


func _mentions(result: Dictionary, word: String) -> bool:
	for failure: String in result.failures:
		if failure.contains(word):
			return true
	return false


## A round head of `radius` in a 30x30 slot, with a skin face rectangle.
func head(radius: float, face: Rect2i) -> Image:
	var image := Image.create(30, 30, false, Image.FORMAT_RGBA8)
	for y in 30:
		for x in 30:
			if Vector2(x + 0.5, y + 0.5).distance_to(Vector2(15, 15)) <= radius:
				image.set_pixel(x, y, SKIN if face.has_point(Vector2i(x, y)) else HAIR)
	return image
