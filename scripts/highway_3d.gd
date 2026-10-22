extends Node3D

const ROAD_WIDTH := 8.2
const ROAD_LENGTH := 48.0
const ROAD_CENTER_Z := 22.5
const HIT_Z := 1.5
const NOTE_SPEED := 8.0
const LANE_SPACING := 1.15
const NOTE_LEAD_DISTANCE := ROAD_LENGTH - HIT_Z - 2.0

var note_visuals: Array[Dictionary] = []
var string_materials: Array[StandardMaterial3D] = []
var pulse_materials: Array[StandardMaterial3D] = []
var pulse_timers: Array[float] = []
var pulse_colors: Array[Color] = []
var road_material: StandardMaterial3D
var hit_material: StandardMaterial3D
var error_material: StandardMaterial3D
var song_time := 0.0
var speed_multiplier := 1.0

func _ready() -> void:
	_build_world()
	_build_highway()

func _build_world() -> void:
	var environment := Environment.new()
	environment.background_mode = Environment.BG_COLOR
	environment.background_color = Color(0.008, 0.012, 0.028)
	environment.ambient_light_source = Environment.AMBIENT_SOURCE_COLOR
	environment.ambient_light_color = Color(0.16, 0.21, 0.30)
	environment.ambient_light_energy = 0.65
	environment.glow_enabled = true
	environment.glow_intensity = 0.85
	environment.glow_strength = 1.2
	environment.glow_bloom = 0.08
	var world_environment := WorldEnvironment.new()
	world_environment.environment = environment
	add_child(world_environment)

	var camera := Camera3D.new()
	camera.name = "HighwayCamera"
	camera.position = Vector3(0.0, 7.0, -9.5)
	camera.fov = 52.0
	camera.current = true
	add_child(camera)
	camera.look_at(Vector3(0.0, 0.0, 21.0), Vector3.UP)

	var key_light := DirectionalLight3D.new()
	key_light.rotation_degrees = Vector3(-48.0, -18.0, 0.0)
	key_light.light_color = Color(0.48, 0.74, 1.0)
	key_light.light_energy = 0.75
	add_child(key_light)

	var fill_light := OmniLight3D.new()
	fill_light.position = Vector3(0.0, 4.5, 5.0)
	fill_light.light_color = Color(0.15, 0.85, 1.0)
	fill_light.light_energy = 1.0
	fill_light.omni_range = 24.0
	add_child(fill_light)

func _build_highway() -> void:
	road_material = StandardMaterial3D.new()
	road_material.albedo_color = Color(0.025, 0.065, 0.105)
	road_material.metallic = 0.28
	road_material.roughness = 0.38
	var road := MeshInstance3D.new()
	road.name = "GuitarNeck"
	var road_mesh := PlaneMesh.new()
	road_mesh.size = Vector2(ROAD_WIDTH, ROAD_LENGTH)
	road.mesh = road_mesh
	road.rotation_degrees.x = -90.0
	road.position = Vector3(0.0, 0.0, ROAD_CENTER_Z)
	road.material_override = road_material
	add_child(road)

	var edge_material := _emissive_material(Color(0.08, 0.72, 1.0), 2.5)
	_add_box("LeftNeonRail", Vector3(0.055, 0.045, ROAD_LENGTH), Vector3(-ROAD_WIDTH * 0.5, 0.035, ROAD_CENTER_Z), edge_material)
	_add_box("RightNeonRail", Vector3(0.055, 0.045, ROAD_LENGTH), Vector3(ROAD_WIDTH * 0.5, 0.035, ROAD_CENTER_Z), edge_material)

	for lane in 6:
		var lane_color: Color = GameConfig.STRING_COLORS[lane]
		var string_material := _emissive_material(lane_color, 1.9)
		string_materials.append(string_material)
		var x := _lane_x(lane)
		_add_box("String_%s" % GameConfig.STRING_NAMES[lane], Vector3(0.035, 0.035, ROAD_LENGTH), Vector3(x, 0.075, ROAD_CENTER_Z), string_material)

		var pulse_material := _emissive_material(lane_color, 0.8)
		pulse_material.transparency = BaseMaterial3D.TRANSPARENCY_ALPHA
		pulse_material.albedo_color.a = 0.12
		pulse_materials.append(pulse_material)
		pulse_timers.append(0.0)
		pulse_colors.append(lane_color)
		_add_box("HitFlash_%s" % GameConfig.STRING_NAMES[lane], Vector3(LANE_SPACING * 0.92, 0.045, 1.0), Vector3(x, 0.11, HIT_Z), pulse_material)
		_add_string_label(lane, x)

	var fret_material := _emissive_material(Color(0.28, 0.53, 0.68), 0.65)
	for fret in range(1, 15):
		var z := HIT_Z + fret * 1.45
		_add_box("Fret_%02d" % fret, Vector3(ROAD_WIDTH - 0.12, 0.028, 0.035), Vector3(0.0, 0.035, z), fret_material)
	# Linhas transversais discretas dão escala e profundidade à pista.
	var grid_material := _emissive_material(Color(0.12, 0.28, 0.38), 0.3)
	for mark in range(0, 19):
		var z := 3.0 + mark * 2.35
		_add_box("RoadGrid_%02d" % mark, Vector3(ROAD_WIDTH - 0.1, 0.018, 0.018), Vector3(0.0, 0.025, z), grid_material)

	hit_material = _emissive_material(Color(0.55, 0.96, 1.0), 5.0)
	_add_box("HitLine", Vector3(ROAD_WIDTH + 0.18, 0.10, 0.14), Vector3(0.0, 0.13, HIT_Z), hit_material)
	var hit_edge_material := _emissive_material(Color(0.08, 0.9, 1.0), 3.2)
	for side in [-1.0, 1.0]:
		_add_box("HitPost", Vector3(0.075, 0.72, 0.08), Vector3(side * (ROAD_WIDTH * 0.5 + 0.15), 0.38, HIT_Z), hit_edge_material)

	var note_outline := _emissive_material(Color(1.0, 0.16, 0.10), 1.5)
	error_material = _emissive_material(Color(1.0, 0.08, 0.06), 1.2)
	# Um pequeno detalhe emissivo junto à pestana reforça o foco visual.
	_add_box("HitLineGlow", Vector3(ROAD_WIDTH + 0.28, 0.035, 0.28), Vector3(0.0, 0.095, HIT_Z), note_outline)

func _lane_x(lane: int) -> float:
	return (float(lane) - 2.5) * LANE_SPACING

func _emissive_material(color: Color, energy: float) -> StandardMaterial3D:
	var material := StandardMaterial3D.new()
	material.albedo_color = color
	material.emission_enabled = true
	material.emission = color
	material.emission_energy_multiplier = energy
	material.roughness = 0.32
	return material

func _add_box(node_name: String, dimensions: Vector3, at: Vector3, material: Material) -> MeshInstance3D:
	var instance := MeshInstance3D.new()
	instance.name = node_name
	var box := BoxMesh.new()
	box.size = dimensions
	instance.mesh = box
	instance.position = at
	instance.material_override = material
	add_child(instance)
	return instance

func _add_string_label(lane: int, x: float) -> void:
	var label := Label3D.new()
	label.name = "StringLabel_%s" % GameConfig.STRING_NAMES[lane]
	label.text = GameConfig.STRING_NAMES[lane]
	label.position = Vector3(x, 0.28, -0.15)
	label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
	label.font_size = 64
	label.pixel_size = 0.004
	label.modulate = GameConfig.STRING_COLORS[lane]
	label.outline_size = 8
	label.outline_modulate = Color(0.015, 0.025, 0.05)
	add_child(label)

func set_notes(notes: Array[Dictionary]) -> void:
	for visual in note_visuals:
		var node: Node3D = visual["node"]
		node.queue_free()
	note_visuals.clear()
	for note in notes:
		var lane := int(note["corda"])
		var group := Node3D.new()
		group.name = "Note_%03d" % note_visuals.size()
		var block := MeshInstance3D.new()
		var box := BoxMesh.new()
		box.size = Vector3(0.82, 0.19, 0.62)
		block.mesh = box
		block.material_override = string_materials[lane]
		group.add_child(block)
		var fret_label := Label3D.new()
		fret_label.name = "FretNumber"
		fret_label.text = str(note["traste"])
		fret_label.position = Vector3(0.0, 0.28, 0.0)
		fret_label.billboard = BaseMaterial3D.BILLBOARD_ENABLED
		fret_label.font_size = 84
		fret_label.pixel_size = 0.003
		fret_label.modulate = Color.WHITE
		fret_label.outline_size = 12
		fret_label.outline_modulate = Color(0.01, 0.02, 0.035)
		group.add_child(fret_label)
		add_child(group)
		note_visuals.append({"node": group, "block": block, "label": fret_label, "lane": lane, "state": "pendente"})
	update_game(song_time, notes, speed_multiplier)

func update_game(elapsed: float, notes: Array[Dictionary], speed: float) -> void:
	song_time = elapsed
	speed_multiplier = speed
	for index in mini(note_visuals.size(), notes.size()):
		var visual := note_visuals[index]
		var note: Dictionary = notes[index]
		var node: Node3D = visual["node"]
		var state := str(note["estado"])
		if state == "acertou":
			node.visible = false
			continue
		var time_to_hit := float(note["t"]) - elapsed
		var lead_time := NOTE_LEAD_DISTANCE / NOTE_SPEED
		node.visible = time_to_hit <= lead_time
		if not node.visible:
			continue
		var lane := int(visual["lane"])
		# `t` já converte pulso para segundos usando o BPM e o perfil atual.
		# A velocidade espacial fica fixa para a nota cruzar a hit line exatamente em t.
		var distance := minf(time_to_hit * NOTE_SPEED, NOTE_LEAD_DISTANCE)
		node.position = Vector3(_lane_x(lane), 0.21, HIT_Z + distance)
		if state != str(visual["state"]):
			visual["state"] = state
			var block: MeshInstance3D = visual["block"]
			block.material_override = error_material if state == "errou" else string_materials[lane]

func pulse_lane(lane: int, success: bool) -> void:
	if lane < 0 or lane >= pulse_timers.size():
		return
	pulse_timers[lane] = 0.55
	pulse_colors[lane] = GameConfig.GREEN if success else GameConfig.RED

func _process(delta: float) -> void:
	for lane in pulse_timers.size():
		if pulse_timers[lane] <= 0.0:
			continue
		pulse_timers[lane] = maxf(0.0, pulse_timers[lane] - delta)
		var strength := pulse_timers[lane] / 0.55
		var material := pulse_materials[lane]
		material.emission = pulse_colors[lane]
		material.emission_energy_multiplier = 0.8 + strength * 6.0
		material.albedo_color = Color(pulse_colors[lane].r, pulse_colors[lane].g, pulse_colors[lane].b, 0.12 + strength * 0.4)
