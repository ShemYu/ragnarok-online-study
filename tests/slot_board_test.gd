extends SceneTree
## Run: Godot --headless --log-file <abs log> --path . --script res://tests/slot_board_test.gd -- \
##        --out-dir=<new absolute folder> [--log-dir=<absolute writable folder>]
## Inspection B7/D14 pipeline, end to end, without generated art: the attack2
## back-view board's own native image is imported as a stand-in candidate.
## Everything is written below --out-dir (board, packs, look); saved boards and packs
## are never touched. Requires the local RO reference pack, slot inventory and Wayfarer v3 pack.

const Actor = preload("res://scripts/ro_sprite_actor.gd")
var OUT := ""
var LOGS := ""
var BOARD := ""
var PACK := ""
var LOOK := ""
var checks := 0
var failures := 0
var calls := 0

func _initialize() -> void:
	call_deferred("run")

func option(name: String) -> String:
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--%s=" % name):
			return argument.trim_prefix("--%s=" % name)
	return ""

func check(condition: bool, message: String) -> void:
	checks += 1
	if not condition:
		failures += 1
		push_error(message)

func godot(arguments: Array) -> int:
	var output := []
	calls += 1
	# An explicit log file keeps the child out of the user:// log folder.
	var log_file := LOGS.path_join("slot-board-test-%02d.log" % calls)
	var code := OS.execute(OS.get_executable_path(), ["--headless", "--log-file", log_file, "--path", ProjectSettings.globalize_path("res://")] + arguments, output, true)
	if code != 0:
		print("\n".join(output))
	return code

func run() -> void:
	OUT = option("out-dir").trim_suffix("/")
	if OUT.is_empty() or not OUT.is_absolute_path() or OUT.begins_with("res://") or DirAccess.dir_exists_absolute(OUT + "/board"):
		push_error("Give --out-dir=<new absolute folder outside saved assets>; it must not contain an earlier run")
		quit(2)
		return
	LOGS = option("log-dir").trim_suffix("/") if not option("log-dir").is_empty() else OUT + "/logs"
	DirAccess.make_dir_recursive_absolute(LOGS)
	BOARD = OUT + "/board/"
	PACK = OUT + "/pack/"
	LOOK = OUT + "/merged-look.json"
	check(godot(["--script", "res://tools/character-lab/export_slot_board.gd", "--", "--group=attack2", "--direction=2", "--out=" + BOARD]) == 0, "Board export must succeed")
	var layout: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(BOARD + "sprite-slots.json"))
	var slots := []
	for slot: Dictionary in layout.slots:
		slots.append(int(slot.index))
	check(slots == [87, 88, 89, 90, 91], "Back-view attack2 needs SPR 87-91: %s" % [slots])
	check(layout.view.directions == ["W", "NW", "N", "NE"] and layout.view.rawFacing == ["W", "NW"], "View and raw facing: %s" % [layout.view])
	check(FileAccess.get_file_as_string(BOARD + "prompt.txt").contains("SIZE CONTRACT"), "Prompt must carry the size contract")
	# A deliberately bad candidate (everything shrunk) must be refused and write nothing.
	var bad := Image.load_from_file(BOARD + "slot-board-5x.png")
	var small := Image.create(bad.get_width(), bad.get_height(), false, Image.FORMAT_RGBA8)
	small.fill(Color("ff00ff"))
	var shrunk := bad.duplicate()
	shrunk.resize(bad.get_width() * 8 / 10, bad.get_height() * 8 / 10, Image.INTERPOLATE_NEAREST)
	small.blit_rect(shrunk, Rect2i(Vector2i.ZERO, shrunk.get_size()), Vector2i(bad.get_width() / 10, bad.get_height() / 10))
	small.save_png(OUT + "/bad-candidate.png")
	check(godot(["--script", "res://tools/character-lab/import_slot_board.gd", "--", "--board=" + BOARD, "--source=" + OUT + "/bad-candidate.png", "--output-dir=" + PACK]) != 0, "Shrunken candidate must be refused")
	check(not FileAccess.file_exists(PACK + "pack.json"), "A refused candidate must not write a pack")
	# The native board itself passes and keeps every silhouette pixel-exact.
	check(godot(["--script", "res://tools/character-lab/import_slot_board.gd", "--", "--board=" + BOARD, "--source=" + BOARD + "slot-board-5x.png", "--output-dir=" + PACK, "--name=native passthrough"]) == 0, "Native passthrough import must succeed")
	var pack: Dictionary = JSON.parse_string(FileAccess.get_file_as_string(PACK + "pack.json"))
	check(pack.contract.pass and pack.verification.actUnchanged, "Passthrough must pass the contract with ACT unchanged")
	for slot: Dictionary in layout.slots:
		var native := Image.load_from_file(BOARD + slot.sourceFile)
		var imported := Image.load_from_file(PACK + "body/%03d.png" % int(slot.index))
		var same := native.get_size() == imported.get_size()
		for y in native.get_height():
			for x in native.get_width():
				same = same and ((native.get_pixel(x, y).a8 > 0) == (imported.get_pixel(x, y).a8 > 0))
		check(same, "SPR %d silhouette must survive the palette import exactly" % int(slot.index))
		check(pack.diagnostics[str(int(slot.index))].offPalettePixels == 0, "SPR %d must be palette-only" % int(slot.index))
	check(pack.fixtures.size() == 4 and pack.fixtures.W.frames.size() == 9, "Fixtures for four directions x nine frames")
	# One look can merge the accepted front view with the new back view.
	var look := {"schemaVersion": 1, "id": "test-merged", "label": "merged", "parts": {"body": [
		{"manifest": "res://tools/character-lab/assets/native-wayfarer-v3/costume.json", "field": "body"},
		{"manifest": PACK + "pack.json", "field": "body"}]}}
	var file := FileAccess.open(LOOK, FileAccess.WRITE)
	file.store_string(JSON.stringify(look))
	file.close()
	var actor := Actor.new()
	root.add_child(actor)
	actor.configure("swordsman")
	actor.set_process(false)
	check(actor.set_appearance(LOOK), "Merged look must load")
	check(actor.coverage.get("body", {}).get("replaced", 0) == 11, "Front (6) + back (5) body drawings: %s" % [actor.coverage])
	if failures == 0 and checks >= 14:
		print("SLOT_BOARD_TEST_PASS (%d checks) -> %s" % [checks, OUT])
	else:
		push_error("SLOT_BOARD_TEST_FAIL: %d of %d checks" % [failures, checks])
	quit(1 if failures or checks < 14 else 0)
