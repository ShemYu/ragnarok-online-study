extends Node3D
## Offline simulation. Input issues commands; attacks commit at their hit time.
## Rules, sprite decoding/playback, field rendering and HUD are separate modules.
const FieldWorld = preload("res://scripts/field_world_ro.gd")
const ActorVisual = preload("res://scripts/ro_sprite_actor.gd")
const GameHUD = preload("res://scripts/game_hud.gd")
const Rules = preload("res://scripts/rpg_rules.gd")
const SAVE_PATH := "user://progress-v2.json"
const ATTACK_RANGE := 1.35
var GUIDE_POSITION := Vector3(-3, 0, 4)
# Replacement-art looks for the player (inspection B6). "" is native RO art.
const APPEARANCES := ["", "res://tools/character-lab/appearances/wayfarer-v3.json", "res://tools/character-lab/appearances/wayfarer-preview.json"]
const HEADGEARS := ["", "cap", "hat"]
const SPAWNS = [Vector3(-4,0,0), Vector3(3,0,-3), Vector3(-6,0,-5), Vector3(4,0,5), Vector3(3,0,-7), Vector3(-8,0,1)]

var field: FieldWorld
var player: ActorVisual
var guide: ActorVisual
var hud: GameHUD
var camera: Camera3D
var destination_marker: MeshInstance3D
var player_spawn := Vector3(0,0,3)
var character: Dictionary = Rules.default_character()
var derived: Dictionary = Rules.derived_stats(character)
var quest: Dictionary = {"active":false,"complete":false,"claimed":false,"poring":0,"lunatic":0}
var monsters: Array[Dictionary] = []
var drops: Array[Dictionary] = []
var floating_labels: Array[Dictionary] = []
var path: Array[Vector3] = []
var pending_attack: Dictionary = {}
var selected_id: int = -1
var selected_drop: int = -1
var hovered_id: int = -1
var next_skill: String = ""
var talk_pending: bool = false
var command: String = "idle"
var attack_timer: float = 0
var attack_pose: float = 0
var chase_timer: float = 0
var death_timer: float = 0
var potion_timer: float = 0
var regen_timer: float = 0
var hit_stun: float = 0
var time: float = 0
var camera_focus := Vector3.ZERO
var camera_yaw: float = 0
var camera_pitch: float = deg_to_rad(48)
var camera_distance: float = 62
var kills: int = 0
var sitting: bool = false
var dead: bool = false
var rng := RandomNumberGenerator.new()
var qa_mode: bool = false
var save_enabled: bool = true
var save_path: String = SAVE_PATH
var qa_runner: RefCounted
var hp: float:
	get: return character.hp
	set(value): character.hp = value
var max_hp: float:
	get: return derived.max_hp
var sp: float:
	get: return character.sp
	set(value): character.sp = value

func _ready() -> void:
	rng.seed = 20260923
	qa_mode = "--qa" in OS.get_cmdline_user_args() or "--qa-playthrough" in OS.get_cmdline_user_args() or "--qa-progression" in OS.get_cmdline_user_args()
	save_enabled = not qa_mode
	field = FieldWorld.new()
	add_child(field)
	field.build()
	player_spawn = field.nearest_ground(player_spawn)
	GUIDE_POSITION = field.nearest_ground(GUIDE_POSITION)
	_setup_lighting()
	_setup_camera()
	player = ActorVisual.new()
	add_child(player)
	player.configure("novice")
	for argument in OS.get_cmdline_user_args():
		if argument.begins_with("--appearance="):
			player.set_appearance(argument.trim_prefix("--appearance="))
		elif argument.begins_with("--headgear="):
			player.set_headgear(argument.trim_prefix("--headgear="))
	player.position = player_spawn
	_setup_destination()
	for i in SPAWNS.size():
		_spawn_monster(SPAWNS[i], "poring" if i < 3 else "lunatic")
	guide = ActorVisual.new()
	add_child(guide)
	guide.configure("guide")
	guide.position = GUIDE_POSITION
	guide.set_motion(Vector3(0.05,0,0.05))
	guide.set_motion(Vector3.ZERO)
	var guide_name := _nameplate("Training Instructor", 0.04)
	guide_name.offset = Vector2(0,-26)
	guide_name.no_depth_test = true
	guide.add_child(guide_name)
	field.navigation.set_point_solid(field.world_to_cell(GUIDE_POSITION), true)
	hud = GameHUD.new()
	add_child(hud)
	hud.set_field_map(field.minimap_texture,24.5,"Prontera South Field")
	hud.potion_requested.connect(use_potion)
	hud.rest_requested.connect(toggle_rest)
	hud.pickup_requested.connect(gather_nearby)
	hud.first_aid_requested.connect(use_first_aid)
	hud.bash_requested.connect(queue_bash)
	hud.stat_requested.connect(allocate_stat)
	hud.learn_bash_requested.connect(learn_bash)
	hud.equip_requested.connect(toggle_weapon)
	hud.trainer_requested.connect(talk_to_guide)
	hud.dialog_action.connect(_dialog_action)
	_load_progress()
	_refresh_derived()
	_update_hud()
	camera_focus = player.position
	_update_camera(1)
	if "--qa" in OS.get_cmdline_user_args():
		qa_runner = load("res://tests/gameplay_test.gd").new()
		qa_runner.call_deferred("run",self)
	elif "--qa-playthrough" in OS.get_cmdline_user_args():
		qa_runner = load("res://tests/rendered_playthrough.gd").new()
		qa_runner.call_deferred("run",self)

func _setup_lighting() -> void:
	var node := WorldEnvironment.new()
	var env := Environment.new()
	env.background_mode = Environment.BG_COLOR
	env.background_color = Color("829c8a")
	env.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	env.ambient_light_color = Color("cfdfec")
	env.ambient_light_energy = 0.35
	env.tonemap_mode = Environment.TONE_MAPPER_LINEAR
	node.environment = env
	add_child(node)
	var sun := DirectionalLight3D.new()
	sun.rotation_degrees = Vector3(-58,-32,0)
	sun.light_color = Color("fff8ed")
	sun.light_energy = 0.18
	sun.shadow_enabled = true
	sun.directional_shadow_max_distance = 110
	sun.shadow_blur = 2
	add_child(sun)

func _setup_camera() -> void:
	camera = Camera3D.new()
	add_child(camera)
	# Narrow perspective is characteristic of the classic RO client. The
	# prototype's world units differ; distance is tuned to our field scale.
	camera.projection = Camera3D.PROJECTION_PERSPECTIVE
	camera.fov = 15
	camera.near = 1
	camera.far = 180
	camera.current = true
	camera.position = Vector3(0,48,42)
	camera.look_at(Vector3.ZERO)

func _setup_destination() -> void:
	destination_marker = MeshInstance3D.new()
	var torus := TorusMesh.new()
	torus.inner_radius = 0.32
	torus.outer_radius = 0.36
	torus.rings = 24
	torus.ring_segments = 6
	destination_marker.mesh = torus
	var material := StandardMaterial3D.new()
	material.albedo_color = Color("7bef77")
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	destination_marker.material_override = material
	destination_marker.scale.y = 0.1
	destination_marker.visible = false
	add_child(destination_marker)

func _nameplate(text: String, height: float) -> Label3D:
	var label := Label3D.new()
	label.text = text
	label.font_size = 22
	label.pixel_size = 0.009
	label.position.y = height
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.modulate = Color("ffffff")
	label.outline_modulate = Color("283131")
	label.outline_size = 6
	return label

func _spawn_monster(spawn: Vector3, species: String) -> void:
	spawn = field.nearest_ground(spawn)
	var definition := Rules.monster_def(species)
	var actor := ActorVisual.new()
	add_child(actor)
	actor.configure(species)
	actor.position = spawn
	var label := _nameplate(definition.name, 1.1)
	label.visible = false
	actor.add_child(label)
	monsters.append({"visual":actor,"label":label,"spawn":spawn,"id":species,"def":definition,
		"hp":float(definition.hp),"max_hp":float(definition.max_hp),"alive":true,"aggro":false,
		"cooldown":0.6,"windup":0.0,"stun":0.0,"pose":0.0,"death_pose":0.0,
		"respawn":0.0,"returning":false,"generation":0,"wander":rng.randf_range(2,5),
		"route":[],"repath":0.0})

func _process(delta: float) -> void:
	time += delta
	attack_timer = maxf(0,attack_timer-delta)
	attack_pose = maxf(0,attack_pose-delta)
	potion_timer = maxf(0,potion_timer-delta)
	hit_stun = maxf(0,hit_stun-delta)
	chase_timer -= delta
	if dead:
		death_timer -= delta
		if death_timer <= 0:
			_respawn_player()
	else:
		_advance_attack(delta)
		_update_player(delta)
		_regenerate(delta)
	_update_monsters(delta)
	_update_drops(delta)
	_update_floating_text(delta)
	_update_camera(delta)
	_update_hover()
	_update_hud()

func _update_player(delta: float) -> void:
	if sitting:
		command = "sit"
		player.set_motion(Vector3.ZERO)
		player.set_state("sit")
		return
	if attack_pose > 0 or hit_stun > 0:
		player.set_motion(Vector3.ZERO)
		return
	if selected_id >= 0 and monsters[selected_id].alive:
		var foe: ActorVisual = monsters[selected_id].visual
		var distance := player.position.distance_to(foe.position)
		if distance <= ATTACK_RANGE:
			path.clear()
			destination_marker.visible = false
			player.set_motion((foe.position-player.position).normalized()*0.05)
			if attack_timer <= 0:
				_start_attack(selected_id)
			else:
				player.set_state("ready")
			return
		if chase_timer <= 0:
			path = _find_path(player.position,foe.position)
			chase_timer = 0.45
		command = "chase"
	var movement := Vector3.ZERO
	if not path.is_empty():
		var point: Vector3 = path[0]
		var previous := player.position
		player.position = player.position.move_toward(point, float(derived.walk_speed)*delta)
		player.position = field.ground_position(player.position)
		movement = (player.position-previous)/maxf(delta,0.0001)
		if player.position.distance_to(point)<0.025:
			path.pop_front()
		if path.is_empty():
			destination_marker.visible = false
	player.set_motion(movement)
	if movement == Vector3.ZERO and command not in ["chase"]:
		command = "idle"
	if selected_drop>=0 and selected_drop<drops.size() and player.position.distance_to(drops[selected_drop].base)<1.45:
		_collect_drop(selected_drop)
	if talk_pending and player.position.distance_to(GUIDE_POSITION)<1.65:
		talk_pending = false
		path.clear()
		_open_trainer_dialog()

func _find_path(start: Vector3, goal: Vector3) -> Array[Vector3]:
	var result: Array[Vector3] = []
	var from_cell: Vector2i = field.world_to_cell(start)
	var to_cell: Vector2i = field.world_to_cell(goal)
	if not field.is_walkable(from_cell) or not field.is_walkable(to_cell):
		return result
	for cell in field.navigation.get_id_path(from_cell,to_cell):
		var point: Vector3 = field.cell_to_world(cell)
		if start.distance_to(point)>0.025:
			result.append(point)
	return result

func move_to(destination: Vector3) -> void:
	if dead:
		return
	var cell: Vector2i = field.world_to_cell(destination)
	if not field.is_walkable(cell):
		hud.show_message("You cannot walk there.")
		return
	_cancel_target()
	sitting = false
	player.set_state("idle")
	command = "move"
	path = _find_path(player.position,destination)
	if not path.is_empty():
		destination_marker.position = field.cell_to_world(cell)+Vector3(0,0.055,0)
		destination_marker.visible = true

func select_monster(index: int) -> void:
	if dead or index<0 or index>=monsters.size() or not monsters[index].alive:
		return
	_cancel_target()
	selected_id = index
	monsters[index].visual.set_selected(true)
	sitting = false
	player.set_state("idle")
	command = "chase"
	chase_timer = 0

func _cancel_target(preserve_action: bool = false) -> void:
	if selected_id>=0:
		monsters[selected_id].visual.set_selected(false)
	selected_id = -1
	selected_drop = -1
	next_skill = ""
	talk_pending = false
	pending_attack.clear()
	if not preserve_action:
		attack_pose = 0
	path.clear()
	destination_marker.visible = false
	if not dead and not preserve_action:
		player.set_state("idle")

func _start_attack(index: int) -> void:
	if dead or index<0 or index>=monsters.size() or not monsters[index].alive:
		return
	var multiplier := 1.0
	var skill: String = next_skill
	next_skill = ""
	if skill == "bash":
		var cast := Rules.try_use_bash(character)
		if not cast.success:
			hud.show_message("Not enough SP for Bash.")
			skill = ""
		else:
			multiplier = cast.multiplier
	var duration := minf(Rules.ATTACK_ANIMATION_MAX_SECONDS,float(derived.attack_interval)*0.65)
	attack_timer = float(derived.attack_interval)
	attack_pose = duration
	command = "attack"
	player.play_action("attack",duration)
	pending_attack = {"target":index,"generation":monsters[index].generation,
		"remaining":duration*Rules.ATTACK_HIT_FRACTION,"multiplier":multiplier,"skill":skill}

func _advance_attack(delta: float) -> void:
	if pending_attack.is_empty():
		return
	pending_attack.remaining -= delta
	if pending_attack.remaining>0:
		return
	var strike := pending_attack.duplicate()
	pending_attack.clear()
	var index: int = strike.target
	if dead or index<0 or index>=monsters.size() or index != selected_id or not monsters[index].alive or monsters[index].generation != strike.generation:
		return
	var mob: Dictionary = monsters[index]
	if player.position.distance_to(mob.visual.position)>ATTACK_RANGE+0.25:
		_float_text("Miss",mob.visual.position+Vector3(0,1.2,0),Color.WHITE)
		return
	mob.aggro = true
	var result := Rules.resolve_attack(derived,mob.def.stats,rng,strike.multiplier)
	if not result.hit:
		_float_text("Miss",mob.visual.position+Vector3(0,1.2,0),Color.WHITE)
		return
	mob.hp = maxf(0,mob.hp-result.damage)
	mob.stun = Rules.HIT_STOP_SECONDS
	mob.visual.flash_hit()
	var color := Color("ffd873") if result.critical or strike.skill=="bash" else Color("fff9ec")
	_float_text(("Critical! " if result.critical else "")+str(result.damage),mob.visual.position+Vector3(0,1.7,0),color)
	if strike.skill=="bash":
		_float_text("Bash!",player.position+Vector3(0,2.1,0),Color("b3dcff"))
	if mob.hp<=0:
		_defeat_monster(index)

func _defeat_monster(index: int) -> void:
	if index<0 or index>=monsters.size() or not monsters[index].alive:
		return
	var mob: Dictionary = monsters[index]
	mob.alive = false
	mob.aggro = false
	mob.windup = 0
	mob.route = []
	mob.death_pose = 0.85
	mob.respawn = float(mob.def.respawn_seconds)
	mob.visual.set_motion(Vector3.ZERO)
	mob.visual.play_action("dead",0.75)
	mob.visual.set_selected(false)
	if rng.randf()<float(mob.def.drop_chance):
		_spawn_drop(mob.visual.position,mob.def.drop)
	kills += 1
	if quest.active and not quest.claimed:
		quest[mob.id] += 1
		quest.complete = quest.poring>=3 and quest.lunatic>=2
	var reward := Rules.grant_exp(character,mob.def.base_exp,mob.def.job_exp)
	_refresh_derived()
	if reward.base_levels>0:
		_float_text("BASE LEVEL UP!",player.position+Vector3(0,2.2,0),Color("fff19c"))
	if reward.job_levels>0:
		_float_text("JOB LEVEL UP!",player.position+Vector3(0,2.6,0),Color("b9e4ff"))
	hud.show_message("%s defeated. EXP +%d / Job +%d" % [mob.def.name,mob.def.base_exp,mob.def.job_exp])
	if selected_id==index:
		# The killing hit still has a visible swing follow-through.
		_cancel_target(true)
	_save_progress()

func _update_monsters(delta: float) -> void:
	for mob in monsters:
		var actor: ActorVisual = mob.visual
		if not mob.alive:
			mob.death_pose -= delta
			actor.visible = mob.death_pose>0
			mob.respawn -= delta
			if mob.respawn<=0:
				mob.alive = true
				mob.generation += 1
				mob.hp = mob.max_hp
				actor.position = mob.spawn
				actor.visible = true
				actor.play_action("idle",0.01)
				mob.route = []
				mob.returning = false
				mob.cooldown = 0.5
			continue
		mob.cooldown = maxf(0,mob.cooldown-delta)
		mob.stun = maxf(0,mob.stun-delta)
		mob.pose = maxf(0,mob.pose-delta)
		mob.repath -= delta
		if mob.windup>0:
			mob.windup -= delta
			if mob.windup<=0 and not dead and actor.position.distance_to(player.position)<1.55:
				var result := Rules.resolve_attack(mob.def.stats,derived,rng)
				if result.hit:
					_damage_player(result.damage)
				else:
					_float_text("Miss",player.position+Vector3(0,1.8,0),Color.WHITE)
		if mob.stun>0 or mob.pose>0:
			actor.set_motion(Vector3.ZERO)
			continue
		if mob.aggro and not dead:
			var distance := actor.position.distance_to(player.position)
			if actor.position.distance_to(mob.spawn)>6 or distance>8:
				mob.aggro = false
				mob.returning = true
				mob.route = _find_path(actor.position,mob.spawn)
			elif distance<=1.20:
				mob.route = []
				actor.set_motion((player.position-actor.position).normalized()*0.05)
				if mob.cooldown<=0:
					mob.cooldown = mob.def.attack_interval
					mob.windup = 0.22
					mob.pose = 0.46
					actor.play_action("attack",0.46)
				continue
			elif mob.repath<=0:
				mob.route = _find_path(actor.position,player.position)
				mob.repath = 0.65
		elif mob.returning:
			if actor.position.distance_to(mob.spawn)<0.2:
				mob.returning = false
				mob.hp = mob.max_hp
		else:
			mob.wander -= delta
			if mob.wander<=0:
				mob.wander = rng.randf_range(3,6)
				mob.route = _find_path(actor.position,mob.spawn+Vector3(rng.randi_range(-2,2),0,rng.randi_range(-2,2)))
		var movement := Vector3.ZERO
		if not mob.route.is_empty():
			var old := actor.position
			var speed: float = float(mob.def.walk_speed)*(1.0 if mob.aggro or mob.returning else 0.48)
			actor.position = actor.position.move_toward(mob.route[0],speed*delta)
			actor.position = field.ground_position(actor.position)
			movement = (actor.position-old)/maxf(delta,0.0001)
			if actor.position.distance_to(mob.route[0])<0.025:
				mob.route.pop_front()
		actor.set_motion(movement)

func _damage_player(amount: float) -> void:
	if dead:
		return
	sitting = false
	hp = maxf(0,hp-amount)
	hit_stun = Rules.HIT_STOP_SECONDS
	player.flash_hit()
	_float_text(str(int(amount)),player.position+Vector3(0,1.8,0),Color("ff8e8e"))
	if hp<=0:
		dead = true
		command = "dead"
		death_timer = 4
		_cancel_target()
		player.set_motion(Vector3.ZERO)
		player.play_action("dead",0.8)
		for mob in monsters:
			mob.aggro = false
			mob.windup = 0
			mob.returning = mob.alive and mob.visual.position.distance_to(mob.spawn)>0.2
			mob.route = _find_path(mob.visual.position,mob.spawn) if mob.returning else []
		hud.show_message("You were knocked out. Returning to camp in 4 seconds.")

func _respawn_player() -> void:
	dead = false
	sitting = false
	player.position = player_spawn
	player.play_action("idle",0.01)
	hp = max_hp
	sp = derived.max_sp
	command = "idle"
	hud.show_message("Back at camp. Rest or use a Red Potion to recover.")

func _regenerate(delta: float) -> void:
	regen_timer += delta
	if regen_timer<Rules.REGEN_TICK_SECONDS or attack_pose>0 or not pending_attack.is_empty():
		return
	regen_timer = 0
	var safe := true
	for mob in monsters:
		if mob.alive and mob.aggro:
			safe = false
	if not safe or not path.is_empty():
		return
	hp = minf(max_hp,hp+(3 if sitting else 1))
	sp = minf(derived.max_sp,sp+(2 if sitting else 1))

func use_potion() -> void:
	if dead or potion_timer>0:
		return
	if character.inventory.red_potion<=0:
		hud.show_message("No Red Potions left. The instructor can help.")
		return
	if hp>=max_hp:
		hud.show_message("HP is already full.")
		return
	character.inventory.red_potion -= 1
	var restored := minf(float(rng.randi_range(45,65)),max_hp-hp)
	hp += restored
	potion_timer = Rules.POTION_COOLDOWN_SECONDS
	_float_text("+%d" % int(restored),player.position+Vector3(0,1.8,0),Color("94ed9a"))
	_save_progress()

func toggle_rest() -> void:
	if dead:
		return
	_cancel_target()
	sitting = not sitting
	player.play_action("sit" if sitting else "idle",0.01)
	player.set_state("sit" if sitting else "idle")
	hud.show_message("Sitting: HP and SP regenerate faster." if sitting else "Standing.")

func use_first_aid() -> void:
	if dead or attack_pose>0:
		return
	var result := Rules.try_first_aid(character)
	if not result.success:
		hud.show_message("First Aid needs 3 SP and missing HP.")
		return
	_cancel_target()
	sitting = false
	attack_pose = 0.48
	player.play_action("cast",0.48)
	_float_text("+%d" % result.healed,player.position+Vector3(0,1.8,0),Color("a6f2cb"))

func queue_bash() -> void:
	if dead:
		return
	if character.skills.bash<=0:
		hud.show_message("Bash belongs to Swordsmen. Train with the instructor, then learn it in Status.")
		return
	if selected_id<0:
		hud.show_message("Select a monster before using Bash.")
		return
	next_skill = "bash"
	hud.show_message("Bash queued for your next attack.")

func allocate_stat(stat: String) -> void:
	if Rules.spend_stat(character,stat):
		_refresh_derived()
		_save_progress()

func learn_bash() -> void:
	if Rules.learn_bash(character):
		hud.show_message("Bash learned. Press F3 against a selected target.")
		_save_progress()

func toggle_weapon() -> void:
	if dead or attack_pose>0:
		return
	if character.equipped_weapon!="knife" and character.inventory.knife<=0:
		hud.show_message("You do not have a Knife to equip.")
		return
	character.equipped_weapon = "" if character.equipped_weapon=="knife" else "knife"
	_refresh_derived()
	hud.show_message("Knife equipped." if character.equipped_weapon=="knife" else "Knife unequipped. Barehand damage and animation active.")
	_save_progress()

func cycle_appearance() -> void:
	var current := maxi(0, APPEARANCES.find(player.appearance_path))
	for step in range(1, APPEARANCES.size() + 1):
		var path: String = APPEARANCES[(current + step) % APPEARANCES.size()]
		if player.set_appearance(path):
			hud.show_message(_look_message())
			_save_progress()
			return
	hud.show_message("No replacement art is available in this checkout.")

func cycle_headgear() -> void:
	var current := HEADGEARS.find(player.headgear_id)
	for step in range(1, HEADGEARS.size() + 1):
		if player.set_headgear(HEADGEARS[(current + step) % HEADGEARS.size()]):
			hud.show_message("Headgear: %s." % ("none" if player.headgear_id.is_empty() else player.headgear_id))
			_save_progress()
			return

func _look_message() -> String:
	if player.appearance_id.is_empty():
		return "Outfit: native RO art."
	var parts := []
	for part: String in player.coverage:
		parts.append("%s %d/%d" % [part, player.coverage[part].replaced, player.coverage[part].used])
	if parts.is_empty():
		return "Outfit: %s has no drawings for this job yet." % player.appearance_label
	return "Outfit: %s (replaced drawings %s; the rest stay native)." % [player.appearance_label, ", ".join(parts)]

func _refresh_derived() -> void:
	derived = Rules.derived_stats(character)
	hp = clampf(hp,0,max_hp)
	sp = clampf(sp,0,derived.max_sp)
	player.weapon_visible = character.equipped_weapon=="knife"

func talk_to_guide() -> void:
	if dead:
		return
	_cancel_target()
	sitting = false
	player.set_state("idle")
	if player.position.distance_to(GUIDE_POSITION)<1.65:
		_open_trainer_dialog()
	else:
		move_to(field.nearest_ground(GUIDE_POSITION+Vector3(0,0,-1)))
		talk_pending = true

func _open_trainer_dialog() -> void:
	player.set_motion((GUIDE_POSITION-player.position).normalized()*0.05)
	if not quest.active and not quest.claimed:
		hud.show_dialog("Training Instructor","Welcome, Novice. Practice against 3 Porings and 2 Lunatics, then return.\n\nThis local training course grants accelerated EXP so you can try the Swordsman job without hours of grinding.",[{"label":"Begin training","action":"accept"},{"label":"Leave","action":"close"}])
	elif quest.complete and not quest.claimed:
		hud.show_dialog("Training complete","Good work. Your reward is 100 Base EXP, 1151 Job EXP and 5 Red Potions.\n\nOnce you reach Novice Job Level 10, I can promote you to Swordsman.",[{"label":"Claim reward","action":"claim"},{"label":"Leave","action":"close"}])
	elif character.job_class=="Novice" and character.job_level>=10:
		hud.show_dialog("Choose your first job","Become a Swordsman? Your base level and stats stay. Job level starts at 1. Bash becomes available through Status as you gain job skill points.",[{"label":"Become Swordsman","action":"change_job"},{"label":"Later","action":"close"}])
	else:
		hud.show_dialog("Training Instructor","Poring: %d / 3\nLunatic: %d / 2\n\nAllocate STR, AGI or DEX in Status. Equip your Knife in the Bag. Sit to recover HP and SP. I can restore your health here." % [mini(quest.poring,3),mini(quest.lunatic,2)],[{"label":"Restock and heal","action":"heal"},{"label":"Leave","action":"close"}])

func _dialog_action(action: String) -> void:
	hud.close_panels()
	if player.position.distance_to(GUIDE_POSITION)>1.8 or dead:
		return
	match action:
		"accept":
			quest.active = true
			hud.show_message("Training started: defeat 3 Porings and 2 Lunatics.")
		"claim":
			if quest.complete and not quest.claimed:
				quest.claimed = true
				quest.active = false
				Rules.grant_exp(character,100,1151)
				character.inventory.red_potion += 5
				_refresh_derived()
				hud.show_message("Training reward claimed. Speak again to choose Swordsman.")
		"change_job":
			if Rules.change_job(character):
				player.configure("swordsman")
				_refresh_derived()
				_float_text("SWORDSMAN",player.position+Vector3(0,2.4,0),Color("a3dcff"))
				hud.show_message("You are now a Swordsman. Gain Job EXP to learn Bash.")
		"heal":
			hp = max_hp
			sp = derived.max_sp
			character.inventory.red_potion = maxi(3,character.inventory.red_potion)
			hud.show_message("HP and SP restored. At least three potions supplied for practice.")
	_save_progress()

func _spawn_drop(at: Vector3,item: String) -> void:
	var node := MeshInstance3D.new()
	var mesh := PrismMesh.new()
	mesh.size = Vector3(0.22,0.24,0.22)
	node.mesh = mesh
	var material := StandardMaterial3D.new()
	material.albedo_color = Color("bde99c") if item=="clover" else Color("f2c085")
	material.shading_mode = BaseMaterial3D.SHADING_MODE_UNSHADED
	node.material_override = material
	node.position = at+Vector3(0,0.18,0)
	add_child(node)
	var label := _nameplate(Rules.item_def(item).name,0.45)
	label.font_size = 18
	node.add_child(label)
	drops.append({"node":node,"base":at,"life":90.0,"item":item})

func _update_drops(delta: float) -> void:
	for i in range(drops.size()-1,-1,-1):
		drops[i].node.position.y = drops[i].base.y+0.18+sin(time*2+i)*0.025
		drops[i].life -= delta
		if drops[i].life<=0:
			_remove_drop(i)

func _remove_drop(index: int) -> void:
	drops[index].node.queue_free()
	drops.remove_at(index)
	if selected_drop==index:
		selected_drop = -1
	elif selected_drop>index:
		selected_drop -= 1

func gather_nearby() -> void:
	if dead or attack_pose>0 or not pending_attack.is_empty():
		return
	var count := 0
	for i in range(drops.size()-1,-1,-1):
		if player.position.distance_to(drops[i].base)<=1.8:
			_collect_drop(i)
			count += 1
	if count==0:
		hud.show_message("No items nearby. Walk to a drop, then press E.")

func _collect_drop(index: int) -> void:
	if dead or index<0 or index>=drops.size() or not pending_attack.is_empty():
		return
	var item: String = drops[index].item
	_remove_drop(index)
	character.inventory[item] = int(character.inventory.get(item,0))+1
	_cancel_target()
	player.set_motion(Vector3.ZERO)
	attack_pose = 0.24
	player.play_action("pickup",0.24)
	hud.show_message("Obtained %s." % Rules.item_def(item).name)
	_save_progress()

func _float_text(value: String,at: Vector3,color: Color) -> void:
	var label := Label3D.new()
	label.text = value
	label.font_size = 36
	label.pixel_size = 0.010
	label.outline_size = 7
	label.outline_modulate = Color("303231")
	label.modulate = color
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.no_depth_test = true
	label.position = at
	add_child(label)
	floating_labels.append({"node":label,"life":0.9})

func _update_floating_text(delta: float) -> void:
	for i in range(floating_labels.size()-1,-1,-1):
		var item: Dictionary = floating_labels[i]
		item.life -= delta
		item.node.position.y += delta*0.8
		item.node.modulate.a = maxf(0,minf(1,item.life*3))
		if item.life<=0:
			item.node.queue_free()
			floating_labels.remove_at(i)

func _update_camera(delta: float) -> void:
	var desired := player.position+Vector3(0,0,-0.7)
	desired.x = clampf(desired.x,-20,20)
	desired.z = clampf(desired.z,-20,20)
	camera_focus = camera_focus.lerp(desired,1-exp(-delta*6))
	var horizontal := cos(camera_pitch)*camera_distance
	camera.position = camera_focus+Vector3(sin(camera_yaw)*horizontal,sin(camera_pitch)*camera_distance,cos(camera_yaw)*horizontal)
	camera.look_at(camera_focus)

func _monster_at_screen(screen: Vector2) -> int:
	var best := INF
	var result := -1
	for i in monsters.size():
		if monsters[i].alive:
			var bounds: Rect2 = monsters[i].visual.screen_rect(camera).grow(7)
			var distance := bounds.get_center().distance_to(screen)
			if bounds.has_point(screen) and distance<best:
				best = distance
				result = i
	return result

func _update_hover() -> void:
	hovered_id = _monster_at_screen(get_viewport().get_mouse_position())
	for i in monsters.size():
		monsters[i].label.visible = monsters[i].alive and (i==hovered_id or i==selected_id)
	Input.set_default_cursor_shape(Input.CURSOR_CROSS if hovered_id>=0 else Input.CURSOR_ARROW)

func _unhandled_input(event: InputEvent) -> void:
	if event is InputEventMouseMotion and event.button_mask & MOUSE_BUTTON_MASK_RIGHT:
		if event.shift_pressed:
			camera_pitch = clampf(camera_pitch+event.relative.y*0.004,deg_to_rad(35),deg_to_rad(65))
		elif event.ctrl_pressed:
			camera_distance = clampf(camera_distance+event.relative.y*0.11,44,80)
		else:
			camera_yaw = clampf(camera_yaw-event.relative.x*0.007,-PI*0.5,PI*0.5)
	if event is InputEventMouseButton and event.pressed:
		if event.button_index==MOUSE_BUTTON_WHEEL_UP:
			camera_distance = maxf(44,camera_distance-3)
		elif event.button_index==MOUSE_BUTTON_WHEEL_DOWN:
			camera_distance = minf(80,camera_distance+3)
		elif event.button_index==MOUSE_BUTTON_LEFT and not dead:
			if guide.screen_rect(camera).grow(7).has_point(event.position):
				talk_to_guide()
				return
			var index := _monster_at_screen(event.position)
			if index>=0:
				select_monster(index)
				return
			for i in drops.size():
				if camera.unproject_position(drops[i].node.position).distance_to(event.position)<20:
					move_to(drops[i].base)
					selected_drop = i
					return
			var hit: Variant = field.pick_ground(camera.project_ray_origin(event.position),camera.project_ray_normal(event.position))
			if hit!=null:
				move_to(hit)
	if event is InputEventKey and event.pressed and not event.echo:
		if event.physical_keycode==KEY_E and (event.alt_pressed or event.ctrl_pressed):
			hud.toggle_inventory()
			return
		match event.physical_keycode:
			KEY_1, KEY_F1: use_potion()
			KEY_2, KEY_INSERT: toggle_rest()
			KEY_F2, KEY_3: use_first_aid()
			KEY_F3, KEY_4: queue_bash()
			KEY_E: gather_nearby()
			KEY_I: hud.toggle_inventory()
			KEY_C: hud.toggle_status()
			KEY_T: talk_to_guide()
			KEY_O: cycle_appearance()
			KEY_H: cycle_headgear()
			KEY_ESCAPE:
				if not hud.close_panels():
					_cancel_target()
					sitting = false

func _update_hud() -> void:
	hud.update_status({"character":character,"derived":derived,"kills":kills,"quest":quest,
		"sitting":sitting,"dead":dead,"busy":attack_pose>0})
	if selected_id>=0 and monsters[selected_id].alive:
		var mob: Dictionary = monsters[selected_id]
		hud.update_target(mob.def.name,mob.hp,mob.max_hp)
	else:
		hud.update_target("",0,1)
	var positions: Array = []
	for mob in monsters:
		if mob.alive:
			positions.append(mob.visual.position)
	hud.update_map(player.position,positions)

func _save_progress() -> void:
	if not save_enabled:
		return
	var temp_path := save_path+".tmp"
	var file := FileAccess.open(temp_path,FileAccess.WRITE)
	if file:
		var look := {"appearance":player.appearance_path,"headgear":player.headgear_id}
		file.store_string(JSON.stringify({"version":2,"character":character,"quest":quest,"kills":kills,"look":look}))
		file.close()
		if DirAccess.rename_absolute(temp_path,save_path)!=OK:
			push_warning("Could not replace the local progress file.")
	else:
		push_warning("Could not open the local progress file for writing.")

func _saved_int(value: Variant, fallback: int) -> int:
	if (value is int or value is float) and is_finite(float(value)):
		return int(clampf(float(value),0,1000000000))
	return fallback

func _load_progress() -> void:
	if not save_enabled or not FileAccess.file_exists(save_path):
		return
	var data: Variant = JSON.parse_string(FileAccess.get_file_as_string(save_path))
	if not data is Dictionary or data.get("version",0)!=2 or not data.get("character") is Dictionary:
		return
	var loaded: Dictionary = data.character
	var loaded_stats: Dictionary = loaded.get("stats",{}) if loaded.get("stats") is Dictionary else {}
	var loaded_items: Dictionary = loaded.get("inventory",{}) if loaded.get("inventory") is Dictionary else {}
	var loaded_skills: Dictionary = loaded.get("skills",{}) if loaded.get("skills") is Dictionary else {}
	var loaded_quest: Dictionary = data.get("quest",{}) if data.get("quest") is Dictionary else {}
	# Only known schema fields are restored. The v1 save remains untouched.
	for key in ["base_level","base_exp","job_level","job_exp","stat_points","skill_points"]:
		character[key] = _saved_int(loaded.get(key),character[key])
	character.base_level = clampi(character.base_level,1,99)
	character.job_class = "Swordsman" if loaded.get("job_class","")=="Swordsman" else "Novice"
	character.job_level = clampi(character.job_level,1,Rules.job_level_cap(character.job_class))
	for stat in Rules.STAT_NAMES:
		character.stats[stat] = clampi(_saved_int(loaded_stats.get(stat),character.stats[stat]),1,99)
	for item in character.inventory:
		character.inventory[item] = clampi(_saved_int(loaded_items.get(item),character.inventory[item]),0,99999)
	character.equipped_weapon = "knife" if loaded.get("equipped_weapon","")=="knife" and character.inventory.knife>0 else ""
	character.skills.bash = clampi(_saved_int(loaded_skills.get("bash"),0),0,10) if character.job_class=="Swordsman" else 0
	for key in ["active","claimed"]:
		quest[key] = loaded_quest.get(key,quest[key]) if loaded_quest.get(key) is bool else quest[key]
	for key in ["poring","lunatic"]:
		quest[key] = _saved_int(loaded_quest.get(key),quest[key])
	quest.complete = quest.poring>=3 and quest.lunatic>=2
	if quest.claimed:
		quest.active = false
	kills = _saved_int(data.get("kills"),0)
	_refresh_derived()
	hp = max_hp
	sp = derived.max_sp
	if character.job_class=="Swordsman":
		player.configure("swordsman")
		player.weapon_visible = character.equipped_weapon=="knife"
	var look: Dictionary = data.get("look",{}) if data.get("look") is Dictionary else {}
	if str(look.get("appearance","")) in APPEARANCES:
		player.set_appearance(str(look.get("appearance","")))
	if str(look.get("headgear","")) in HEADGEARS:
		player.set_headgear(str(look.get("headgear","")))
	hud.show_message("Local character and training progress restored.")

func _notification(what: int) -> void:
	if what==NOTIFICATION_WM_CLOSE_REQUEST:
		_save_progress()
