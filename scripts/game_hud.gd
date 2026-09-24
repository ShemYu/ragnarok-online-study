extends CanvasLayer
## Compact, classic desktop windows for the local field study.
## Presentation only: all item, stat, skill and quest mutations stay in main.

signal potion_requested
signal rest_requested
signal pickup_requested
signal first_aid_requested
signal bash_requested
signal stat_requested(stat: String)
signal learn_bash_requested
signal equip_requested
signal trainer_requested
signal dialog_action(action: String)

const Rules = preload("res://scripts/rpg_rules.gd")
const INK := Color("#29384b")
const MUTED := Color("#63728a")
const PAPER := Color("#e9edf3")
const BLUE := Color("#5b7cab")
const EDGE := Color("#72839a")
const WHITE := Color("#f5f7fc")
const STAT_LABELS = {"str": "STR", "agi": "AGI", "vit": "VIT", "int": "INT", "dex": "DEX", "luk": "LUK"}
const STAT_TIPS = {"str": "Strength increases melee attack.", "agi": "Agility improves dodge and attack speed.",
	"vit": "Vitality increases maximum HP and defense.", "int": "Intelligence increases maximum SP.",
	"dex": "Dexterity improves accuracy and attack speed.", "luk": "Luck improves critical chance."}

var _ui: Control
var _name_label: Label
var _hp_bar: ProgressBar
var _sp_bar: ProgressBar
var _xp_bar: ProgressBar
var _job_bar: ProgressBar
var _hp_label: Label
var _sp_label: Label
var _xp_label: Label
var _job_label: Label
var _state_label: Label
var _target_panel: PanelContainer
var _target_title: Label
var _target_bar: ProgressBar
var _inventory: PanelContainer
var _inventory_items: Label
var _equipment_label: Label
var _equip_button: Button
var _status_panel: PanelContainer
var _stat_points_label: Label
var _stat_values: Dictionary = {}
var _stat_buttons: Dictionary = {}
var _derived_label: Label
var _skills_label: Label
var _learn_bash_button: Button
var _quest_label: Label
var _quest_button: Button
var _log: VBoxContainer
var _log_panel: PanelContainer
var _log_scroll: ScrollContainer
var _potion_button: Button
var _first_aid_button: Button
var _bash_button: Button
var _rest_button: Button
var _gather_button: Button
var _hotbar: PanelContainer
var _map_panel: PanelContainer
var _map_title: Label
var _quest_panel: PanelContainer
var _map: FieldMap
var _field_map_texture: Texture2D
var _field_map_extent: float = 14.0
var _field_map_title: String = "Willow Field"
var _dialog: PanelContainer
var _dialog_title: Label
var _dialog_body: Label
var _dialog_actions: HBoxContainer
var _current_data: Dictionary = {}


func _ready() -> void:
	layer = 10
	_ui = Control.new()
	_ui.name = "GameInterface"
	_ui.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	_ui.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(_ui)
	_ui.theme = _make_theme()
	_build_character()
	_build_map()
	_build_quest()
	_build_log()
	_build_hotbar()
	_build_target()
	_build_status()
	_build_inventory()
	_build_dialog()
	_ui.resized.connect(_apply_responsive_layout)
	_apply_responsive_layout()
	update_status(_current_data)
	show_message("Welcome to the field. Speak to the guide to begin.")
	show_message("Click to walk. Click a monster to attack.", Color("#d3e0f4"))


func _make_theme() -> Theme:
	var theme := Theme.new()
	theme.default_font_size = 12
	theme.set_color("font_color", "Label", INK)
	for state in ["font_color", "font_hover_color", "font_pressed_color", "font_focus_color"]:
		theme.set_color(state, "Button", INK)
	theme.set_color("font_disabled_color", "Button", Color("#9aa3b1"))
	theme.set_stylebox("normal", "Button", _style(Color("#e2e7ee"), Color("#8a9aaf"), 2, 4))
	theme.set_stylebox("hover", "Button", _style(Color("#f9fbff"), Color("#557ead"), 2, 4))
	theme.set_stylebox("pressed", "Button", _style(Color("#b6c8de"), Color("#5d7594"), 2, 4))
	theme.set_stylebox("disabled", "Button", _style(Color("#d7dde5"), Color("#b6c0cd"), 2, 4))
	theme.set_stylebox("focus", "Button", _style(Color.TRANSPARENT, Color("#5b87bf"), 2))
	return theme


func _build_character() -> void:
	var panel := _panel("BasicInfo")
	_place(panel, Vector2.ZERO, Rect2(16, 16, 236, 163))
	var body := _window(panel, "Basic Information")
	_name_label = _label("Novice    Base 1 / Job 1", 13)
	body.add_child(_name_label)
	var hp := _resource_row(body, "HP", Color("#79b66b"))
	_hp_bar = hp.bar
	_hp_label = hp.label
	var sp := _resource_row(body, "SP", Color("#729fd1"))
	_sp_bar = sp.bar
	_sp_label = sp.label
	var xp := _resource_row(body, "Base", Color("#d0b56d"))
	_xp_bar = xp.bar
	_xp_label = xp.label
	var job := _resource_row(body, "Job", Color("#bd91c7"))
	_job_bar = job.bar
	_job_label = job.label
	_state_label = _label("Ready", 11, MUTED)
	body.add_child(_state_label)


func _build_map() -> void:
	_map_panel = _panel("Minimap")
	_place(_map_panel, Vector2(1, 0), Rect2(-186, 16, 170, 166))
	var body := _window(_map_panel, _field_map_title)
	_map_title = _map_panel.find_child("WindowTitle", true, false) as Label
	_map = FieldMap.new()
	_map.map_texture = _field_map_texture
	_map.extent = _field_map_extent
	_map.custom_minimum_size = Vector2(154, 128)
	_map.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_map.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(_map)


func _build_quest() -> void:
	_quest_panel = _panel("Quest")
	_place(_quest_panel, Vector2(1, 0), Rect2(-186, 189, 170, 111))
	var body := _window(_quest_panel, "Field Training")
	_quest_label = _label("Speak to the field guide.", 12)
	_quest_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_quest_label.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_child(_quest_label)
	_quest_button = _button("Talk to Guide", "Speak to the field guide about training.")
	_quest_button.pressed.connect(func() -> void: trainer_requested.emit())
	body.add_child(_quest_button)


func _build_log() -> void:
	_log_panel = _panel("Messages", Color("#12203296"), Color("#8195b745"))
	_place(_log_panel, Vector2(0, 1), Rect2(16, -126, 320, 110))
	_log_scroll = ScrollContainer.new()
	_log_scroll.mouse_filter = Control.MOUSE_FILTER_IGNORE
	_log_scroll.horizontal_scroll_mode = ScrollContainer.SCROLL_MODE_DISABLED
	_log_scroll.vertical_scroll_mode = ScrollContainer.SCROLL_MODE_SHOW_NEVER
	_log_panel.add_child(_log_scroll)
	_log = _column(_log_scroll, 3)
	_log.size_flags_horizontal = Control.SIZE_EXPAND_FILL


func _build_hotbar() -> void:
	_hotbar = _panel("ShortcutBar")
	_place(_hotbar, Vector2(1, 1), Rect2(-530, -52, 514, 36))
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_theme_constant_override("separation", 3)
	_hotbar.add_child(row)
	_potion_button = _button("1 Potion", "Red Potion: restore 45-65 HP.")
	_potion_button.pressed.connect(func() -> void: potion_requested.emit())
	row.add_child(_potion_button)
	_first_aid_button = _button("F2 Aid", "First Aid: restore 5 HP for 3 SP.")
	_first_aid_button.pressed.connect(func() -> void: first_aid_requested.emit())
	row.add_child(_first_aid_button)
	_bash_button = _button("F3 Bash", "Swordsman skill: spend SP for a stronger attack.")
	_bash_button.pressed.connect(func() -> void: bash_requested.emit())
	row.add_child(_bash_button)
	_rest_button = _button("2 Sit", "Sit to recover HP and SP. Press again to stand.")
	_rest_button.pressed.connect(func() -> void: rest_requested.emit())
	row.add_child(_rest_button)
	_gather_button = _button("E Gather", "Pick up nearby monster drops.")
	_gather_button.pressed.connect(func() -> void: pickup_requested.emit())
	row.add_child(_gather_button)
	var bag := _button("I Bag", "Open or close your inventory.")
	bag.pressed.connect(toggle_inventory)
	row.add_child(bag)
	var status := _button("C Status", "Allocate stat points and train skills.")
	status.pressed.connect(toggle_status)
	row.add_child(status)


func _build_target() -> void:
	_target_panel = _panel("Target", Color("#dfe7f1e8"))
	_place(_target_panel, Vector2(0.5, 1), Rect2(-115, -100, 230, 37))
	var body := _column(_target_panel, 3)
	_target_title = _label("Poring", 12)
	_target_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	body.add_child(_target_title)
	_target_bar = _bar(Color("#c57f8d"), 6)
	body.add_child(_target_bar)
	_target_panel.hide()


func _build_status() -> void:
	_status_panel = _panel("CharacterStatus")
	_place(_status_panel, Vector2.ZERO, Rect2(16, 215, 285, 350))
	var body := _window(_status_panel, "Character Status", toggle_status)
	body.add_theme_constant_override("separation", 3)
	_stat_points_label = _label("Stat points: 6", 12)
	body.add_child(_stat_points_label)
	for stat: String in Rules.STAT_NAMES:
		var row := HBoxContainer.new()
		row.mouse_filter = Control.MOUSE_FILTER_IGNORE
		row.add_theme_constant_override("separation", 6)
		body.add_child(row)
		var caption := _label(STAT_LABELS[stat], 12)
		caption.tooltip_text = STAT_TIPS[stat]
		caption.custom_minimum_size.x = 37
		row.add_child(caption)
		var value := _label("1", 12)
		value.size_flags_horizontal = Control.SIZE_EXPAND_FILL
		row.add_child(value)
		_stat_values[stat] = value
		var button := _button("+  (2 pt)", STAT_TIPS[stat])
		button.custom_minimum_size = Vector2(77, 22)
		button.size_flags_horizontal = Control.SIZE_SHRINK_END
		button.pressed.connect(func() -> void: stat_requested.emit(stat))
		row.add_child(button)
		_stat_buttons[stat] = button
	_derived_label = _label("ATK 0   DEF 0\nHIT 0   FLEE 0   ASPD 0", 12, MUTED)
	_derived_label.add_theme_constant_override("line_spacing", 2)
	body.add_child(_derived_label)
	var separator := HSeparator.new()
	separator.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(separator)
	_skills_label = _label("First Aid Lv 1  /  Bash --\nSkill points: 0", 12)
	_skills_label.add_theme_constant_override("line_spacing", 2)
	body.add_child(_skills_label)
	_learn_bash_button = _button("Bash requires Swordsman", "Bash is learned with Swordsman job skill points.")
	_learn_bash_button.pressed.connect(func() -> void: learn_bash_requested.emit())
	body.add_child(_learn_bash_button)
	_status_panel.hide()


func _build_inventory() -> void:
	_inventory = _panel("Inventory")
	_place(_inventory, Vector2(1, 1), Rect2(-286, -330, 270, 264))
	var body := _window(_inventory, "Inventory", toggle_inventory)
	_inventory_items = _label("", 12)
	_inventory_items.add_theme_constant_override("line_spacing", 8)
	_inventory_items.size_flags_vertical = Control.SIZE_EXPAND_FILL
	body.add_child(_inventory_items)
	var separator := HSeparator.new()
	separator.mouse_filter = Control.MOUSE_FILTER_IGNORE
	body.add_child(separator)
	_equipment_label = _label("Weapon: Knife (ATK +17)", 12)
	body.add_child(_equipment_label)
	_equip_button = _button("Unequip Knife", "Equip or remove the knife from your weapon slot.")
	_equip_button.pressed.connect(func() -> void: equip_requested.emit())
	body.add_child(_equip_button)
	_inventory.hide()


func _build_dialog() -> void:
	_dialog = _panel("Dialogue")
	_place(_dialog, Vector2(0.5, 0.5), Rect2(-220, -125, 440, 250))
	var outer := _column(_dialog, 8)
	var title_bar := PanelContainer.new()
	title_bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	title_bar.add_theme_stylebox_override("panel", _style(Color("#93a9c5"), Color("#697f9e"), 1, 4))
	outer.add_child(title_bar)
	_dialog_title = _label("Field Guide", 14, Color("#192d47"))
	title_bar.add_child(_dialog_title)
	_dialog_body = _label("", 13)
	_dialog_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_dialog_body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	_dialog_body.add_theme_constant_override("line_spacing", 4)
	outer.add_child(_dialog_body)
	_dialog_actions = HBoxContainer.new()
	_dialog_actions.add_theme_constant_override("separation", 6)
	_dialog_actions.mouse_filter = Control.MOUSE_FILTER_IGNORE
	outer.add_child(_dialog_actions)
	_dialog.hide()


func update_status(data: Dictionary) -> void:
	_current_data = data.duplicate()
	if not is_instance_valid(_name_label):
		return
	var character: Dictionary = data.get("character", Rules.default_character())
	var derived: Dictionary = data.get("derived", Rules.derived_stats(character))
	var stats: Dictionary = character.get("stats", {})
	var inventory: Dictionary = character.get("inventory", {})
	var skills: Dictionary = character.get("skills", {})
	var job_class := str(character.get("job_class", "Novice"))
	var base_level := int(character.get("base_level", 1))
	var job_level := int(character.get("job_level", 1))
	var hp := float(character.get("hp", 0.0))
	var sp := float(character.get("sp", 0.0))
	var max_hp := maxf(1.0, float(derived.get("max_hp", 1.0)))
	var max_sp := maxf(1.0, float(derived.get("max_sp", 1.0)))
	var points := int(character.get("stat_points", 0))
	var skill_points := int(character.get("skill_points", 0))
	var bash_level := int(skills.get("bash", 0))
	var potions := int(inventory.get("red_potion", 0))
	var sitting := bool(data.get("sitting", false))
	var dead := bool(data.get("dead", false))
	var busy := bool(data.get("busy", false))
	_name_label.text = "%s    Base %d / Job %d" % [job_class, base_level, job_level]
	_set_resource(_hp_bar, _hp_label, hp, max_hp)
	_set_resource(_sp_bar, _sp_label, sp, max_sp)
	_set_exp(_xp_bar, _xp_label, int(character.get("base_exp", 0)), Rules.exp_needed(base_level))
	_set_exp(_job_bar, _job_label, int(character.get("job_exp", 0)), Rules.exp_needed(job_level, true, job_class))
	_state_label.text = "Fallen — returning to camp" if dead else ("Sitting — recovering HP / SP" if sitting else "%d monsters defeated" % int(data.get("kills", 0)))
	_potion_button.text = "1 Pot. %d" % potions
	_potion_button.disabled = dead or potions <= 0 or hp >= max_hp
	_first_aid_button.disabled = dead or busy or hp >= max_hp or sp < 3.0
	_bash_button.disabled = dead or busy or job_class != "Swordsman" or bash_level < 1 or sp < Rules.bash_cost(bash_level)
	_bash_button.tooltip_text = "Bash Lv %d: %d SP" % [bash_level, Rules.bash_cost(bash_level)] if bash_level > 0 else "Become a Swordsman and learn Bash in Character Status."
	_rest_button.text = "2 Stand" if sitting else "2 Sit"
	_rest_button.disabled = dead
	_gather_button.disabled = dead
	_stat_points_label.text = "Stat points: %d" % points
	for stat: String in Rules.STAT_NAMES:
		var value := int(stats.get(stat, 1))
		var cost := Rules.stat_cost(value)
		_stat_values[stat].text = str(value)
		_stat_buttons[stat].text = "+  (%d pt)" % cost
		_stat_buttons[stat].disabled = points < cost or value >= Rules.STAT_CAP or dead
	_derived_label.text = "ATK %d   DEF %d   CRIT %.1f%%\nHIT %d   FLEE %d   ASPD %.1f" % [int(derived.get("attack", 0)), int(derived.get("defense", 0)), float(derived.get("critical", 0.0)), int(derived.get("hit", 0)), int(derived.get("flee", 0)), float(derived.get("aspd", 0.0))]
	_skills_label.text = "First Aid Lv %d  /  Bash %s\nSkill points: %d" % [int(skills.get("first_aid", 1)), "Lv %d" % bash_level if bash_level > 0 else "--", skill_points]
	_learn_bash_button.text = "Learn Bash  (+1 / 1 skill point)" if job_class == "Swordsman" else "Bash requires Swordsman"
	if bash_level >= Rules.BASH_LEVEL_CAP:
		_learn_bash_button.text = "Bash mastered"
	_learn_bash_button.disabled = dead or job_class != "Swordsman" or skill_points < 1 or bash_level >= Rules.BASH_LEVEL_CAP
	var lines := PackedStringArray()
	for id: String in ["red_potion", "jellopy", "clover", "knife"]:
		lines.append("%s    x %d" % [Rules.item_def(id).get("name", id), int(inventory.get(id, 0))])
	_inventory_items.text = "\n".join(lines)
	var equipped := str(character.get("equipped_weapon", "")) == "knife"
	_equipment_label.text = "Weapon: Knife  (ATK +17)" if equipped else "Weapon: Empty"
	_equip_button.text = "Unequip Knife" if equipped else "Equip Knife"
	_equip_button.disabled = dead or busy or (not equipped and int(inventory.get("knife", 0)) < 1)
	_update_quest(data.get("quest", {}))


func _update_quest(quest: Dictionary) -> void:
	if bool(quest.get("claimed", false)):
		var promoted: bool = _current_data.get("character",{}).get("job_class","Novice")=="Swordsman"
		_quest_label.text = "Swordsman training:\nEarn Job EXP, learn Bash." if promoted else "Field training complete.\nJob 10: visit the guide."
	elif bool(quest.get("complete", false)):
		_quest_label.text = "Training complete!\nReturn to the field guide."
	elif bool(quest.get("active", false)):
		_quest_label.text = "Poring  %d / 3\nLunatic  %d / 2" % [mini(int(quest.get("poring", 0)), 3), mini(int(quest.get("lunatic", 0)), 2)]
	else:
		_quest_label.text = "Speak to the field guide\nto start training."


func update_target(title: String, hp: float, max_hp: float) -> void:
	if not is_instance_valid(_target_panel):
		return
	_target_panel.visible = not title.is_empty()
	_target_title.text = "%s   %d / %d" % [title, maxi(0, ceili(hp)), ceili(max_hp)]
	_target_bar.max_value = maxf(1.0, max_hp)
	_target_bar.value = hp


func show_message(message: String, color: Color = WHITE) -> void:
	if not is_instance_valid(_log):
		return
	var line := _label(message, 12, color)
	line.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	_log.add_child(line)
	while _log.get_child_count() > 7:
		var oldest := _log.get_child(0)
		_log.remove_child(oldest)
		oldest.queue_free()
	_scroll_log_to_bottom.call_deferred()


func _scroll_log_to_bottom() -> void:
	if is_instance_valid(_log_scroll):
		_log_scroll.scroll_vertical = int(_log.size.y)


func toggle_inventory() -> void:
	if is_instance_valid(_inventory):
		_inventory.visible = not _inventory.visible


func toggle_status() -> void:
	if is_instance_valid(_status_panel):
		_status_panel.visible = not _status_panel.visible
		_apply_responsive_layout()


func update_map(player_pos: Vector3, monster_positions: Array) -> void:
	if is_instance_valid(_map):
		_map.player_position = player_pos
		_map.monster_positions = monster_positions.duplicate()
		_map.queue_redraw()


func set_field_map(texture: Texture2D, extent: float, title: String) -> void:
	_field_map_texture = texture
	_field_map_extent = maxf(extent, 0.01)
	_field_map_title = title
	if is_instance_valid(_map_title):
		_map_title.text = title
	if is_instance_valid(_map):
		_map.map_texture = texture
		_map.extent = _field_map_extent
		_map.queue_redraw()


func show_dialog(title: String, body: String, actions: Array) -> void:
	if not is_instance_valid(_dialog):
		return
	close_panels()
	_dialog_title.text = title
	_dialog_body.text = body
	for child in _dialog_actions.get_children():
		_dialog_actions.remove_child(child)
		child.queue_free()
	for entry: Dictionary in actions:
		var action := str(entry.get("action", "close"))
		var button := _button(str(entry.get("label", "Continue")), "")
		button.pressed.connect(func() -> void:
			_dialog.hide()
			dialog_action.emit(action)
		)
		_dialog_actions.add_child(button)
	if actions.is_empty():
		var close := _button("Close", "Close this conversation.")
		close.pressed.connect(func() -> void: _dialog.hide())
		_dialog_actions.add_child(close)
	_dialog.show()


func close_panels() -> bool:
	var closed := false
	for panel in [_inventory, _status_panel, _dialog]:
		if is_instance_valid(panel) and panel.visible:
			panel.hide()
			closed = true
	_apply_responsive_layout()
	return closed


func _apply_responsive_layout() -> void:
	if not is_instance_valid(_inventory) or not is_instance_valid(_log_panel):
		return
	# The bottom shortcuts stay to the right of the log even at 960x640.
	# An open status sheet uses the log area on short windows; hide messages then
	# instead of layering two interactive windows on top of each other.
	_log_panel.visible = not (_ui.size.y < 720.0 and _status_panel.visible)
	_place(_inventory, Vector2(1, 1), Rect2(-286, -330, 270, 264))
	_place(_hotbar, Vector2(1, 1), Rect2(-530, -52, 514, 36))


func _panel(node_name: String, fill: Color = PAPER, edge: Color = EDGE) -> PanelContainer:
	var panel := PanelContainer.new()
	panel.name = node_name
	panel.mouse_filter = Control.MOUSE_FILTER_STOP
	panel.add_theme_stylebox_override("panel", _style(fill, edge, 2, 5))
	_ui.add_child(panel)
	return panel


func _window(panel: PanelContainer, title: String, close_action: Callable = Callable()) -> VBoxContainer:
	var outer := _column(panel, 5)
	var bar := PanelContainer.new()
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bar.add_theme_stylebox_override("panel", _style(Color("#93a9c5"), Color("#697f9e"), 1, 2))
	outer.add_child(bar)
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_theme_constant_override("separation", 3)
	bar.add_child(row)
	var heading := _label(title, 12, Color("#192d47"))
	heading.name = "WindowTitle"
	heading.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(heading)
	if close_action.is_valid():
		var close := _button("x", "Close window")
		close.custom_minimum_size = Vector2(20, 18)
		close.size_flags_horizontal = Control.SIZE_SHRINK_END
		close.pressed.connect(close_action)
		row.add_child(close)
	var body := _column(outer, 4)
	body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	return body


func _column(parent: Control, separation: int) -> VBoxContainer:
	var column := VBoxContainer.new()
	column.mouse_filter = Control.MOUSE_FILTER_IGNORE
	column.add_theme_constant_override("separation", separation)
	parent.add_child(column)
	return column


func _label(content: String, font_size: int = 12, color: Color = INK) -> Label:
	var label := Label.new()
	label.text = content
	label.mouse_filter = Control.MOUSE_FILTER_IGNORE
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	return label


func _button(content: String, tooltip: String) -> Button:
	var button := Button.new()
	button.text = content
	button.tooltip_text = tooltip
	button.focus_mode = Control.FOCUS_NONE
	button.mouse_filter = Control.MOUSE_FILTER_STOP
	button.custom_minimum_size = Vector2(0, 24)
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.add_theme_font_size_override("font_size", 12)
	return button


func _resource_row(parent: Control, title: String, color: Color) -> Dictionary:
	var row := HBoxContainer.new()
	row.mouse_filter = Control.MOUSE_FILTER_IGNORE
	row.add_theme_constant_override("separation", 5)
	parent.add_child(row)
	var caption := _label(title, 11, MUTED)
	caption.custom_minimum_size.x = 28
	row.add_child(caption)
	var bar := _bar(color, 15)
	bar.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	row.add_child(bar)
	var value := _label("0 / 0", 10, Color("#17263a"))
	value.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	value.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	value.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	bar.add_child(value)
	return {"bar": bar, "label": value}


func _set_resource(bar: ProgressBar, label: Label, value: float, maximum: float) -> void:
	bar.max_value = maximum
	bar.value = value
	label.text = "%d / %d" % [maxi(0, ceili(value)), ceili(maximum)]


func _set_exp(bar: ProgressBar, label: Label, value: int, maximum: int) -> void:
	bar.max_value = maxi(1, maximum)
	bar.value = value if maximum > 0 else 1
	label.text = "%d / %d" % [value, maximum] if maximum > 0 else "MAX"


func _bar(fill: Color, height: float) -> ProgressBar:
	var bar := ProgressBar.new()
	bar.show_percentage = false
	bar.custom_minimum_size = Vector2(0, height)
	bar.mouse_filter = Control.MOUSE_FILTER_IGNORE
	bar.add_theme_stylebox_override("background", _style(Color("#b6c0ce"), Color("#8291a4"), 1))
	bar.add_theme_stylebox_override("fill", _style(fill, Color.TRANSPARENT, 1))
	return bar


func _style(fill: Color, edge: Color, radius: int, margin: int = 0) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = fill
	style.border_color = edge
	style.set_border_width_all(1 if edge.a > 0.0 else 0)
	style.set_corner_radius_all(radius)
	style.content_margin_left = margin
	style.content_margin_right = margin
	style.content_margin_top = margin
	style.content_margin_bottom = margin
	return style


func _place(control: Control, anchor: Vector2, rect: Rect2) -> void:
	control.anchor_left = anchor.x
	control.anchor_top = anchor.y
	control.anchor_right = anchor.x
	control.anchor_bottom = anchor.y
	control.offset_left = rect.position.x
	control.offset_top = rect.position.y
	control.offset_right = rect.end.x
	control.offset_bottom = rect.end.y


class FieldMap extends Control:
	var player_position := Vector3.ZERO
	var monster_positions: Array = []
	var extent := 14.0
	var map_texture: Texture2D

	func _draw() -> void:
		var bounds := Rect2(Vector2(2, 2), size - Vector2(4, 4))
		draw_rect(bounds, Color("#c6d3bb"))
		draw_rect(bounds, Color("#809476"), false, 1.0)
		if map_texture != null:
			var inset := Vector2(6, 6)
			draw_texture_rect(map_texture, Rect2(inset, size - inset * 2.0), false)
		else:
			_draw_legacy_terrain()
		for position in monster_positions:
			if position is Vector3:
				draw_circle(_to_map(position), 2.4, Color("#b97780"), true, -1.0, true)
		var player_point := _to_map(player_position)
		draw_circle(player_point, 4.0, WHITE, true, -1.0, true)
		draw_circle(player_point, 2.5, Color("#2d77bb"), true, -1.0, true)
		draw_string(ThemeDB.fallback_font, Vector2(size.x * 0.5 - 4, 13), "N", HORIZONTAL_ALIGNMENT_LEFT, -1, 11, Color("#40556d"))

	func _draw_legacy_terrain() -> void:
		var road := PackedVector2Array()
		for point: Vector2 in [Vector2(-14, -4), Vector2(-10, -4), Vector2(-6, -2.8), Vector2(-2, -0.5), Vector2(2, 0.5), Vector2(6, 0), Vector2(12, 0), Vector2(14, 1.4)]:
			road.append(_to_map(Vector3(point.x, 0, point.y)))
		draw_polyline(road, Color("#e2d5b1"), 8.0, true)
		var branch := PackedVector2Array()
		for point: Vector2 in [Vector2(0, 0), Vector2(0.2, 3.5), Vector2(-0.8, 7), Vector2(0.5, 11.5), Vector2(0.5, 14)]:
			branch.append(_to_map(Vector3(point.x, 0, point.y)))
		draw_polyline(branch, Color("#e2d5b1"), 5.0, true)
		var river_min := _to_map(Vector3(7.5, 0, -14))
		var river_max := _to_map(Vector3(10.5, 0, 14))
		draw_rect(Rect2(river_min, river_max - river_min), Color("#93b6cf"))
		var bridge_min := _to_map(Vector3(7.5, 0, -1.5))
		var bridge_max := _to_map(Vector3(10.5, 0, 1.5))
		draw_rect(Rect2(bridge_min, bridge_max - bridge_min), Color("#b8a888"))

	func _to_map(position: Vector3) -> Vector2:
		var inset := Vector2(6, 6)
		var usable := size - inset * 2.0
		return Vector2(clampf(0.5 + position.x / (extent * 2.0), 0.0, 1.0) * usable.x,
			clampf(0.5 + position.z / (extent * 2.0), 0.0, 1.0) * usable.y) + inset
