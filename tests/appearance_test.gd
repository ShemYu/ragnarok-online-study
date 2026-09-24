extends SceneTree
## Run: Godot --headless --path . --script res://tests/appearance_test.gd
## Inspection B5/B6. Requires the local RO reference pack and Character Lab packs.
## The game actor must reproduce the Character Lab fixtures pixel for pixel, and
## differently dressed actors of one job must never share cached frames.

const Actor = preload("res://scripts/ro_sprite_actor.gd")
const WAYFARER := "res://tools/character-lab/appearances/wayfarer-v3.json"
const LAB := "res://tools/character-lab/assets/"
const VIEW := 6
var checks := 0
var failures := 0

func _initialize() -> void:
	call_deferred("run")

func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(message)

func actor(kind: String) -> Actor:
	var value := Actor.new()
	root.add_child(value)
	value.configure(kind)
	value.set_process(false)
	value.direction = VIEW
	value.weapon_visible = true
	return value

func frame(value: Actor, index: int) -> Image:
	value.set_state("attack")
	var action: Dictionary = value._get_action(value._body, "attack", VIEW)
	value._clock = index * maxf(0.024, action.delay) + 0.000001
	value._render_frame()
	return value._sprite.texture.get_image()

func differing(a: Image, b: Image) -> int:
	if a.get_size() != b.get_size():
		return -1
	a.convert(Image.FORMAT_RGBA8)
	b.convert(Image.FORMAT_RGBA8)
	var da := a.get_data()
	var db := b.get_data()
	var count := 0
	for i in range(0, da.size(), 4):
		if da[i] != db[i] or da[i + 1] != db[i + 1] or da[i + 2] != db[i + 2] or da[i + 3] != db[i + 3]:
			count += 1
	return count

func run() -> void:
	var native := actor("swordsman")
	var dressed := actor("swordsman")
	var native_actions: Array = native._body.actions
	check(dressed.set_appearance(WAYFARER), "Wayfarer appearance must load and verify its hashes")
	check(dressed.coverage.get("body", {}).get("replaced", 0) == 6, "Six body slots replaced: %s" % [dressed.coverage])
	check(dressed.coverage.get("head", {}).get("replaced", 0) == 1, "One head slot replaced: %s" % [dressed.coverage])
	check(dressed._body.actions == native_actions and is_same(dressed._body.actions, native_actions), "ACT records must be shared, not copied or changed")
	# Interleave both actors so any shared cache entry would surface as a mismatch.
	for i in 9:
		var plain := frame(native, i)
		var custom := frame(dressed, i)
		var expected_plain := Image.load_from_file(LAB + "native-template-v1/attack/frame-%02d.png" % i)
		var expected_custom := Image.load_from_file(LAB + "native-head-v2/none/attack/frame-%02d.png" % i)
		check(differing(plain, expected_plain) == 0, "Native actor frame %d differs from the native fixture" % i)
		check(differing(custom, expected_custom) == 0, "Wayfarer actor frame %d differs from the Lab fixture by %d px" % [i, differing(custom, expected_custom)])
	for gear in ["cap", "hat"]:
		check(dressed.set_headgear(gear), "Headgear %s must load" % gear)
		for i in 9:
			var expected := Image.load_from_file(LAB + "native-head-v2/%s/attack/frame-%02d.png" % [gear, i])
			check(differing(frame(dressed, i), expected) == 0, "Wayfarer + %s frame %d differs from the Lab fixture" % [gear, i])
	# Removing the headgear and the outfit returns exactly to native art.
	dressed.set_headgear("")
	dressed.set_appearance("")
	for i in [0, 5, 8]:
		check(differing(frame(dressed, i), Image.load_from_file(LAB + "native-template-v1/attack/frame-%02d.png" % i)) == 0, "Restored native frame %d must match" % i)
	# Swordsman body art must not repaint a Novice; the shared head still applies.
	var novice := actor("novice")
	novice.set_appearance(WAYFARER)
	check(not novice.coverage.has("body") and novice.coverage.get("head", {}).get("replaced", 0) == 1, "Novice gets the head only: %s" % [novice.coverage])
	# The look survives a job change on the same gameplay actor.
	novice.configure("swordsman")
	check(novice.coverage.get("body", {}).get("replaced", 0) == 6, "Appearance must persist across a job change: %s" % [novice.coverage])
	check(not dressed.set_headgear("crown") and not dressed.set_appearance("res://missing.json"), "Unknown headgear or manifest must be rejected")
	if failures == 0 and checks >= 40:
		print("APPEARANCE_TEST_PASS (%d checks)" % checks)
	else:
		push_error("APPEARANCE_TEST_FAIL: %d of %d checks" % [failures, checks])
	quit(1 if failures or checks < 40 else 0)
