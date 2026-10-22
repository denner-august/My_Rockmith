extends Control

const MUTED := Color8(163, 170, 188)

var riffs := GameConfig.default_riffs()
var riff_keys: Array[String] = []
var selected_riff := "riff_imagem"
var app_screen := "splash"
var game_state := "espera"
var notes: Array[Dictionary] = []
var effects: Array[Dictionary] = []
var game_time := 0.0
var pause_time := 0.0
var latency := GameConfig.DEFAULT_LATENCY
var speed_profiles := {"lento": 0.75, "padrao": 1.0, "rapido": 1.25}
var speed_profile := "padrao"
var speed_multiplier := 1.0
var score := 0
var combo := 0
var best_combo := 0
var hits := 0
var misses := 0
var metronome_enabled := true
var last_beat := -1
var riff_menu_open := false
var riff_focus := 0
var riff_scroll := 0
var mic: MicPitch
var metronome_player: AudioStreamPlayer
var beat_sound: AudioStreamWAV
var strong_sound: AudioStreamWAV
var windowed := false
var status_label: Label
var shortcuts_label: Label
var prompt_label: Label
var selected_label: Label
var signal_label: Label
var paused_label: Label
var results_label: Label
var riff_modal_shield: Control
var top_hud: Control
var center_message_container: Control
var start_screen: Control
var main_menu: Control
var menu_info_overlay: Control
var menu_info_title: Label
var menu_info_body: Label
var menu_info_return_button: Button
var menu_info_page := ""
var menu_buttons: Array[Button] = []
var menu_texture: Texture2D
var menu_return_to_main := false
var action_buttons: Dictionary = {}
var highway: Node

func _ready() -> void:
	get_window().title = "Mini Rocksmith"
	get_window().size = Vector2i(1920, 1080)
	get_window().mode = Window.MODE_EXCLUSIVE_FULLSCREEN
	windowed = false
	_build_3d_view()
	_build_ui()
	_build_start_screen()
	_build_main_menu()
	riff_keys.assign(riffs.keys())
	RiffLibrary.load_all(riffs)
	riff_keys.assign(riffs.keys())
	if not riffs.has(selected_riff) and not riff_keys.is_empty():
		selected_riff = riff_keys[0]
	riff_focus = maxi(0, riff_keys.find(selected_riff))
	mic = MicPitch.new()
	add_child(mic)
	metronome_player = AudioStreamPlayer.new()
	add_child(metronome_player)
	beat_sound = _make_click(750.0, 0.25)
	strong_sound = _make_click(1100.0, 0.42)
	set_process(true)
	_refresh_ui()

func _process(delta: float) -> void:
	if game_state == "jogando":
		game_time += delta
		_update_notes()
		_update_metronome()
	if highway != null:
		var highway_time := game_time if game_state != "pausado" else pause_time
		highway.call("update_game", highway_time, notes, speed_multiplier)
	for effect in effects:
		effect["age"] = float(effect["age"]) + delta
	effects = effects.filter(func(effect: Dictionary) -> bool: return float(effect["age"]) < GameConfig.EFFECT_DURATION)
	_refresh_ui()
	queue_redraw()

func _build_3d_view() -> void:
	var layer := CanvasLayer.new()
	layer.name = "Gameplay3DLayer"
	layer.layer = -1
	add_child(layer)

	var viewport_container := SubViewportContainer.new()
	viewport_container.name = "HighwayViewportContainer"
	viewport_container.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	viewport_container.stretch = true
	viewport_container.mouse_filter = Control.MOUSE_FILTER_IGNORE
	layer.add_child(viewport_container)

	var viewport := SubViewport.new()
	viewport.name = "HighwayViewport"
	viewport.render_target_update_mode = SubViewport.UPDATE_ALWAYS
	viewport.own_world_3d = true
	viewport_container.add_child(viewport)

	var highway_script: Script = load("res://scripts/highway_3d.gd")
	highway = Node3D.new()
	highway.name = "GuitarHighway"
	highway.set_script(highway_script)
	viewport.add_child(highway)

func _build_ui() -> void:
	# Status e botões ocupam a faixa superior; o VBox da direita mantém os
	# perfis abaixo da fileira de ações sem sobreposição.
	var top_row := HBoxContainer.new()
	top_row.name = "TopHUD"
	top_hud = top_row
	top_row.anchor_right = 1.0
	top_row.offset_left = 18.0
	top_row.offset_top = 16.0
	top_row.offset_right = -18.0
	top_row.offset_bottom = 126.0
	top_row.add_theme_constant_override("separation", 18)
	add_child(top_row)

	var left_column := VBoxContainer.new()
	left_column.name = "AudioStatus"
	left_column.custom_minimum_size.x = 400.0
	left_column.add_theme_constant_override("separation", 9)
	top_row.add_child(left_column)
	status_label = _new_label(17, Color8(174, 207, 255))
	left_column.add_child(status_label)
	shortcuts_label = _new_label(14, Color8(139, 155, 181))
	shortcuts_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	shortcuts_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	left_column.add_child(shortcuts_label)

	var spacer := Control.new()
	spacer.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	top_row.add_child(spacer)

	var toolbar := VBoxContainer.new()
	toolbar.name = "ToolbarAndSpeedProfiles"
	toolbar.custom_minimum_size.x = 650.0
	toolbar.add_theme_constant_override("separation", 7)
	top_row.add_child(toolbar)
	var action_row := HBoxContainer.new()
	action_row.add_theme_constant_override("separation", 6)
	toolbar.add_child(action_row)
	_add_action_button(action_row, "menu", "RIFFS", 78, _open_riff_menu)
	_add_action_button(action_row, "pause", "PAUSAR", 92, _on_pause_pressed)
	_add_action_button(action_row, "restart", "REINICIAR", 98, _on_restart_pressed)
	_add_action_button(action_row, "metro", "METRÔNOMO", 118, _on_metronome_pressed)
	_add_action_button(action_row, "menos", "−", 42, _on_slower_pressed)
	_add_action_button(action_row, "mais", "+", 42, _on_faster_pressed)
	var profile_row := HBoxContainer.new()
	profile_row.add_theme_constant_override("separation", 6)
	toolbar.add_child(profile_row)
	_add_action_button(profile_row, "lento", "1 LENTO", 92, func() -> void: _set_speed("lento"))
	_add_action_button(profile_row, "padrao", "2 PADRÃO", 92, func() -> void: _set_speed("padrao"))
	_add_action_button(profile_row, "rapido", "3 RÁPIDO", 92, func() -> void: _set_speed("rapido"))

	var center_messages := VBoxContainer.new()
	center_messages.name = "CenterMessages"
	center_message_container = center_messages
	center_messages.anchor_left = 0.12
	center_messages.anchor_top = 0.18
	center_messages.anchor_right = 0.88
	center_messages.anchor_bottom = 0.35
	center_messages.offset_left = 0.0
	center_messages.offset_top = 0.0
	center_messages.offset_right = 0.0
	center_messages.offset_bottom = 0.0
	center_messages.alignment = BoxContainer.ALIGNMENT_CENTER
	center_messages.add_theme_constant_override("separation", 5)
	center_messages.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(center_messages)
	prompt_label = _new_label(32, Color.WHITE)
	prompt_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	prompt_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	prompt_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center_messages.add_child(prompt_label)
	selected_label = _new_label(22, MUTED)
	selected_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	selected_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	selected_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center_messages.add_child(selected_label)
	signal_label = _new_label(18, GameConfig.RED)
	signal_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	signal_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	signal_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center_messages.add_child(signal_label)
	paused_label = _new_label(34, Color8(255, 220, 100))
	paused_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	paused_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	paused_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center_messages.add_child(paused_label)
	results_label = _new_label(28, Color.WHITE)
	results_label.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	results_label.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	results_label.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	center_messages.add_child(results_label)

	riff_modal_shield = Control.new()
	riff_modal_shield.name = "RiffModalInputShield"
	riff_modal_shield.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	riff_modal_shield.mouse_filter = Control.MOUSE_FILTER_STOP
	riff_modal_shield.z_index = 10
	riff_modal_shield.visible = false
	add_child(riff_modal_shield)

func _build_start_screen() -> void:
	start_screen = Control.new()
	start_screen.name = "StartScreen"
	start_screen.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	start_screen.z_index = 20
	start_screen.mouse_filter = Control.MOUSE_FILTER_IGNORE
	add_child(start_screen)

	var background := TextureRect.new()
	background.name = "PhotoBackground"
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	background.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	background.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_COVERED
	background.texture = load("res://Photo Start/01.jpg")
	background.mouse_filter = Control.MOUSE_FILTER_IGNORE
	start_screen.add_child(background)

	var tint := ColorRect.new()
	tint.name = "PhotoTint"
	tint.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	tint.color = Color(0.015, 0.02, 0.04, 0.34)
	tint.mouse_filter = Control.MOUSE_FILTER_IGNORE
	start_screen.add_child(tint)

	var lower_shade := ColorRect.new()
	lower_shade.name = "InstructionShade"
	lower_shade.anchor_top = 0.68
	lower_shade.anchor_right = 1.0
	lower_shade.anchor_bottom = 1.0
	lower_shade.color = Color(0.015, 0.02, 0.04, 0.66)
	lower_shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	start_screen.add_child(lower_shade)

	var copy := VBoxContainer.new()
	copy.name = "StartInstructions"
	copy.anchor_left = 0.08
	copy.anchor_top = 0.70
	copy.anchor_right = 0.92
	copy.anchor_bottom = 0.94
	copy.alignment = BoxContainer.ALIGNMENT_CENTER
	copy.add_theme_constant_override("separation", 12)
	copy.mouse_filter = Control.MOUSE_FILTER_IGNORE
	start_screen.add_child(copy)

	var title := _new_label(46, Color.WHITE)
	title.text = "MINI ROCKSMITH"
	title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	copy.add_child(title)

	var instruction := _new_label(23, Color8(232, 237, 249))
	instruction.text = "Pressione qualquer tecla ou botão para abrir o menu"
	instruction.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	instruction.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	instruction.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	copy.add_child(instruction)

func _build_main_menu() -> void:
	main_menu = Control.new()
	main_menu.name = "MainMenu"
	main_menu.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	main_menu.z_index = 15
	main_menu.visible = false
	main_menu.mouse_filter = Control.MOUSE_FILTER_STOP
	add_child(main_menu)

	var background := ColorRect.new()
	background.name = "MenuLetterboxBackground"
	background.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	background.color = Color(0.018, 0.015, 0.012)
	background.mouse_filter = Control.MOUSE_FILTER_IGNORE
	main_menu.add_child(background)

	var artwork := TextureRect.new()
	artwork.name = "MenuArtwork"
	artwork.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	artwork.expand_mode = TextureRect.EXPAND_IGNORE_SIZE
	artwork.stretch_mode = TextureRect.STRETCH_KEEP_ASPECT_CENTERED
	menu_texture = load("res://Photo Start/menu_jogo_4x3.png")
	artwork.texture = menu_texture
	artwork.mouse_filter = Control.MOUSE_FILTER_IGNORE
	main_menu.add_child(artwork)

	var menu_entries := [
		{"text": "MÚSICAS", "callback": _open_music_library},
		{"text": "TREINO", "callback": _start_training},
		{"text": "CONFIGURAÇÕES", "callback": func() -> void: _show_menu_info("settings")},
		{"text": "CRÉDITOS", "callback": func() -> void: _show_menu_info("credits")}
	]
	for entry in menu_entries:
		var button := Button.new()
		button.name = str(entry["text"]).replace(" ", "")
		button.text = ""
		button.tooltip_text = str(entry["text"])
		button.focus_mode = Control.FOCUS_ALL
		button.mouse_default_cursor_shape = Control.CURSOR_POINTING_HAND
		button.z_index = 2
		button.pressed.connect(entry["callback"])
		var idle_style := _menu_button_style(Color(0.0, 0.0, 0.0, 0.0), Color(0.0, 0.0, 0.0, 0.0), 0)
		var hover_style := _menu_button_style(Color(0.62, 0.20, 0.035, 0.12), Color(0.90, 0.70, 0.38, 0.72), 2)
		var focus_style := _menu_button_style(Color(0.58, 0.17, 0.025, 0.10), Color(0.96, 0.73, 0.40, 0.9), 2)
		button.add_theme_stylebox_override("normal", idle_style)
		button.add_theme_stylebox_override("pressed", hover_style)
		button.add_theme_stylebox_override("hover", hover_style)
		button.add_theme_stylebox_override("focus", focus_style)
		main_menu.add_child(button)
		menu_buttons.append(button)
	main_menu.resized.connect(_layout_main_menu_buttons)
	_layout_main_menu_buttons()
	_build_menu_info_overlay()

func _menu_button_style(fill: Color, border: Color, border_width: int) -> StyleBoxFlat:
	var style := StyleBoxFlat.new()
	style.bg_color = fill
	style.border_color = border
	style.set_border_width_all(border_width)
	style.set_corner_radius_all(12)
	return style

func _layout_main_menu_buttons() -> void:
	if menu_texture == null or menu_buttons.size() != 4:
		return
	var source_size := menu_texture.get_size()
	var viewport_size := get_viewport_rect().size
	var image_scale := minf(viewport_size.x / source_size.x, viewport_size.y / source_size.y)
	var image_size := source_size * image_scale
	var image_origin := (viewport_size - image_size) * 0.5
	var source_rects: Array[Rect2] = [
		Rect2(390.0, 400.0, 672.0, 135.0),
		Rect2(390.0, 552.0, 672.0, 132.0),
		Rect2(390.0, 700.0, 672.0, 128.0),
		Rect2(390.0, 846.0, 672.0, 132.0)
	]
	for index in menu_buttons.size():
		var button := menu_buttons[index]
		var source_rect := source_rects[index]
		button.position = image_origin + source_rect.position * image_scale
		button.size = source_rect.size * image_scale

func _build_menu_info_overlay() -> void:
	menu_info_overlay = Control.new()
	menu_info_overlay.name = "MenuInfoOverlay"
	menu_info_overlay.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	menu_info_overlay.z_index = 5
	menu_info_overlay.mouse_filter = Control.MOUSE_FILTER_STOP
	menu_info_overlay.visible = false
	main_menu.add_child(menu_info_overlay)

	var shade := ColorRect.new()
	shade.set_anchors_and_offsets_preset(Control.PRESET_FULL_RECT)
	shade.color = Color(0.0, 0.0, 0.0, 0.76)
	shade.mouse_filter = Control.MOUSE_FILTER_IGNORE
	menu_info_overlay.add_child(shade)

	var panel := PanelContainer.new()
	panel.name = "InfoPanel"
	panel.anchor_left = 0.25
	panel.anchor_top = 0.25
	panel.anchor_right = 0.75
	panel.anchor_bottom = 0.75
	var panel_style := _menu_button_style(Color(0.045, 0.035, 0.025, 0.98), Color(0.82, 0.63, 0.34, 1.0), 3)
	panel_style.set_corner_radius_all(14)
	panel.add_theme_stylebox_override("panel", panel_style)
	menu_info_overlay.add_child(panel)

	var margin := MarginContainer.new()
	margin.add_theme_constant_override("margin_left", 34)
	margin.add_theme_constant_override("margin_top", 30)
	margin.add_theme_constant_override("margin_right", 34)
	margin.add_theme_constant_override("margin_bottom", 30)
	panel.add_child(margin)

	var content := VBoxContainer.new()
	content.alignment = BoxContainer.ALIGNMENT_CENTER
	content.add_theme_constant_override("separation", 22)
	margin.add_child(content)

	menu_info_title = _new_label(32, Color8(238, 211, 165))
	menu_info_title.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	menu_info_title.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	content.add_child(menu_info_title)

	menu_info_body = _new_label(20, Color8(225, 220, 209))
	menu_info_body.horizontal_alignment = HORIZONTAL_ALIGNMENT_CENTER
	menu_info_body.vertical_alignment = VERTICAL_ALIGNMENT_CENTER
	menu_info_body.autowrap_mode = TextServer.AUTOWRAP_WORD_SMART
	menu_info_body.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	menu_info_body.size_flags_vertical = Control.SIZE_EXPAND_FILL
	content.add_child(menu_info_body)

	menu_info_return_button = Button.new()
	menu_info_return_button.text = "VOLTAR"
	menu_info_return_button.custom_minimum_size = Vector2(220.0, 52.0)
	menu_info_return_button.size_flags_horizontal = Control.SIZE_SHRINK_CENTER
	menu_info_return_button.pressed.connect(_close_menu_info)
	content.add_child(menu_info_return_button)

func _show_menu_info(page: String) -> void:
	menu_info_page = page
	if page == "settings":
		menu_info_title.text = "CONFIGURAÇÕES"
		menu_info_body.text = "ATALHOS DURANTE O JOGO\n\n[M] Som   •   [D] Timbre   •   [T] Metrônomo\n[↑] Aumentar volume   •   [↓] Diminuir volume\n[←] Menor latência   •   [→] Maior latência\n\nO estado atual aparece no HUD."
	else:
		menu_info_title.text = "CRÉDITOS"
		menu_info_body.text = "MINI ROCKSMITH\n\nUm jogo de prática e reconhecimento de notas para guitarra.\n\nFeito com Godot Engine."
	_refresh_ui()
	menu_info_return_button.grab_focus()

func _return_from_music_library() -> void:
	riff_menu_open = false
	menu_return_to_main = false
	app_screen = "menu"
	_refresh_ui()
	if not menu_buttons.is_empty():
		menu_buttons[0].call_deferred("grab_focus")

func _close_menu_info() -> void:
	menu_info_page = ""
	_refresh_ui()
	if not menu_buttons.is_empty():
		menu_buttons[0].grab_focus()

func _open_music_library() -> void:
	menu_return_to_main = true
	app_screen = "game"
	riff_menu_open = true
	riff_focus = maxi(0, riff_keys.find(selected_riff))
	_update_riff_scroll()
	_refresh_ui()
	queue_redraw()

func _start_training() -> void:
	menu_return_to_main = false
	_start_game()
	_refresh_ui()

func _new_label(font_size: int, color: Color) -> Label:
	var label := Label.new()
	label.add_theme_font_size_override("font_size", font_size)
	label.add_theme_color_override("font_color", color)
	label.clip_text = false
	return label

func _add_action_button(parent: HBoxContainer, key: String, caption: String, min_width: float, callback: Callable) -> void:
	var button := Button.new()
	button.name = key.capitalize()
	button.text = caption
	button.custom_minimum_size = Vector2(min_width, 38.0)
	button.size_flags_horizontal = Control.SIZE_EXPAND_FILL
	button.toggle_mode = key in ["metro", "lento", "padrao", "rapido"]
	button.pressed.connect(callback)
	parent.add_child(button)
	action_buttons[key] = button

func _refresh_ui() -> void:
	if status_label == null:
		return
	status_label.text = "LATÊNCIA %d ms  •  %s  •  VOL %.1f  •  %s" % [roundi(latency * 1000.0), "SOM ON" if mic.monitor_enabled else "SOM OFF", mic.volume, "OVERDRIVE" if mic.overdrive else "LIMPO"]
	shortcuts_label.text = "[M] som  [D] timbre  [T] metrônomo  [↑↓] volume  [←→] latência"
	var selected_name := str(riffs[selected_riff]["nome"])
	prompt_label.text = "Toque uma corda para testar — ESPAÇO para começar"
	selected_label.text = "Selecionado: %s" % selected_name
	signal_label.text = "Sem sinal: habilite a entrada de áudio do sistema"
	paused_label.text = "PAUSADO  •  P para continuar"
	var total := maxi(1, hits + misses)
	results_label.text = "PONTOS: %d\nAcertos: %d/%d (%d%%)  •  Melhor combo: %d\nESPAÇO para jogar novamente" % [score, hits, total, roundi(100.0 * hits / total), best_combo]
	prompt_label.visible = game_state == "espera"
	selected_label.visible = game_state == "espera"
	signal_label.visible = game_state == "espera" and mic.level < GameConfig.SILENCE_THRESHOLD
	paused_label.visible = game_state == "pausado"
	results_label.visible = game_state == "fim"
	var pause_button: Button = action_buttons["pause"]
	pause_button.text = "CONTINUAR" if game_state == "pausado" else "PAUSAR"
	var metro_button: Button = action_buttons["metro"]
	metro_button.text = "METRÔNOMO ON" if metronome_enabled else "METRÔNOMO OFF"
	metro_button.button_pressed = metronome_enabled
	for profile in ["lento", "padrao", "rapido"]:
		var button: Button = action_buttons[profile]
		button.button_pressed = speed_profile == profile
	riff_modal_shield.visible = riff_menu_open
	var gameplay_visible := app_screen == "game"
	start_screen.visible = app_screen == "splash"
	main_menu.visible = app_screen == "menu"
	top_hud.visible = gameplay_visible and not riff_menu_open
	center_message_container.visible = gameplay_visible and not riff_menu_open
	menu_info_overlay.visible = app_screen == "menu" and not menu_info_page.is_empty()

func _open_riff_menu() -> void:
	menu_return_to_main = false
	riff_menu_open = true
	riff_focus = maxi(0, riff_keys.find(selected_riff))
	_update_riff_scroll()
	if game_state == "jogando":
		_toggle_pause()
	_refresh_ui()
	queue_redraw()

func _on_pause_pressed() -> void:
	_toggle_pause()
	_refresh_ui()

func _on_restart_pressed() -> void:
	_start_game()
	_refresh_ui()

func _on_metronome_pressed() -> void:
	metronome_enabled = not metronome_enabled
	_refresh_ui()

func _on_slower_pressed() -> void:
	_adjust_speed(-0.05)
	_refresh_ui()

func _on_faster_pressed() -> void:
	_adjust_speed(0.05)
	_refresh_ui()

func _make_click(frequency: float, volume: float) -> AudioStreamWAV:
	var rate := 22050
	var samples := PackedByteArray()
	var length := int(rate * 0.045)
	samples.resize(length * 2)
	for i in length:
		var envelope := 1.0 - float(i) / length
		var value := int(clampf(sin(TAU * frequency * i / rate) * envelope * volume, -1.0, 1.0) * 32767.0)
		samples.encode_s16(i * 2, value)
	var wav := AudioStreamWAV.new()
	wav.format = AudioStreamWAV.FORMAT_16_BITS
	wav.mix_rate = rate
	wav.stereo = false
	wav.data = samples
	return wav

func _start_game() -> void:
	if mic == null:
		return
	app_screen = "game"
	menu_info_page = ""
	riff_menu_open = false
	menu_return_to_main = false
	notes = RiffLibrary.build_notes(riffs[selected_riff], speed_multiplier)
	game_time = 0.0
	score = 0
	combo = 0
	best_combo = 0
	hits = 0
	misses = 0
	effects.clear()
	last_beat = -1
	game_state = "jogando"
	if highway != null:
		highway.call("set_notes", notes)
		highway.call("update_game", 0.0, notes, speed_multiplier)

func _toggle_pause() -> void:
	if game_state == "jogando":
		game_state = "pausado"
		pause_time = game_time
	elif game_state == "pausado":
		game_state = "jogando"

func _update_notes() -> void:
	var audio_time := game_time - latency
	for note in notes:
		if note["estado"] != "pendente":
			continue
		if audio_time > float(note["t"]) + GameConfig.HIT_WINDOW:
			note["estado"] = "errou"
			misses += 1
			combo = 0
			if highway != null:
				highway.call("pulse_lane", int(note["corda"]), false)
			_add_effect(note, false, "ERROU")
		elif absf(audio_time - float(note["t"])) <= GameConfig.HIT_WINDOW and GameConfig.pitch_matches(mic.midi, int(note["midi"])):
			note["estado"] = "acertou"
			hits += 1
			combo += 1
			best_combo = maxi(best_combo, combo)
			var perfect := absf(audio_time - float(note["t"])) <= 0.06
			var gain := 100 + mini(combo, 10) * 10 + (50 if perfect else 0)
			score += gain
			if highway != null:
				highway.call("pulse_lane", int(note["corda"]), true)
			_add_effect(note, true, ("PERFEITO" if perfect else "BOA") + "  +" + str(gain))
	var finished := not notes.is_empty()
	for note in notes:
		if note["estado"] == "pendente":
			finished = false
			break
	if finished:
		game_state = "fim"

func _add_effect(note: Dictionary, success: bool, text: String) -> void:
	effects.append({"corda": int(note["corda"]), "ok": success, "texto": text, "age": 0.0})

func _update_metronome() -> void:
	if not metronome_enabled:
		return
	var bpm := float(riffs[selected_riff]["bpm"]) * speed_multiplier
	var beat := floori(game_time * bpm / 60.0)
	if beat > last_beat:
		metronome_player.stream = strong_sound if beat % 4 == 0 else beat_sound
		metronome_player.play()
		last_beat = beat

func _input(event: InputEvent) -> void:
	if app_screen == "splash":
		if _is_start_button_event(event):
			app_screen = "menu"
			_refresh_ui()
			if not menu_buttons.is_empty():
				menu_buttons[0].call_deferred("grab_focus")
			get_viewport().set_input_as_handled()
		return
	if app_screen == "menu":
		if event is InputEventKey and event.pressed and not event.echo and event.keycode == KEY_ESCAPE:
			if not menu_info_page.is_empty():
				_close_menu_info()
			else:
				app_screen = "splash"
				_refresh_ui()
			get_viewport().set_input_as_handled()
		return
	if event is InputEventKey and event.pressed and not event.echo:
		_handle_key(event as InputEventKey)
	elif event is InputEventMouseButton and event.pressed and riff_menu_open:
		_handle_click((event as InputEventMouseButton).position)
		get_viewport().set_input_as_handled()

func _is_start_button_event(event: InputEvent) -> bool:
	if event is InputEventKey:
		return event.pressed and not event.echo
	if event is InputEventMouseButton:
		return event.pressed
	if event is InputEventJoypadButton:
		return event.pressed
	if event is InputEventScreenTouch:
		return event.pressed
	return false

func _handle_key(event: InputEventKey) -> void:
	var key := event.keycode
	if riff_menu_open:
		if key == KEY_ESCAPE:
			if menu_return_to_main:
				_return_from_music_library()
			elif game_state == "pausado":
				riff_menu_open = false
				_toggle_pause()
			else:
				riff_menu_open = false
			_refresh_ui()
		elif key == KEY_UP or key == KEY_LEFT:
			riff_focus = maxi(0, riff_focus - 1)
			_update_riff_scroll()
		elif key == KEY_DOWN or key == KEY_RIGHT:
			riff_focus = mini(riff_keys.size() - 1, riff_focus + 1)
			_update_riff_scroll()
		elif key == KEY_ENTER or key == KEY_KP_ENTER or key == KEY_SPACE:
			selected_riff = riff_keys[riff_focus]
			riff_menu_open = false
			_start_game()
			_refresh_ui()
		return
	match key:
		KEY_ESCAPE: get_tree().quit()
		KEY_F11:
			windowed = not windowed
			get_window().mode = Window.MODE_WINDOWED if windowed else Window.MODE_EXCLUSIVE_FULLSCREEN
		KEY_SPACE:
			if game_state == "espera" or game_state == "fim": _start_game()
		KEY_P: _toggle_pause()
		KEY_R: _start_game()
		KEY_T: metronome_enabled = not metronome_enabled
		KEY_M: mic.monitor_enabled = not mic.monitor_enabled
		KEY_D: mic.overdrive = not mic.overdrive
		KEY_UP: mic.volume = minf(1.5, mic.volume + 0.1)
		KEY_DOWN: mic.volume = maxf(0.0, mic.volume - 0.1)
		KEY_LEFT: latency = maxf(0.0, latency - 0.01)
		KEY_RIGHT: latency = minf(0.5, latency + 0.01)
		KEY_1: _set_speed("lento")
		KEY_2: _set_speed("padrao")
		KEY_3: _set_speed("rapido")
		KEY_MINUS: _adjust_speed(-0.05)
		KEY_EQUAL, KEY_KP_ADD: _adjust_speed(0.05)
	_refresh_ui()

func _set_speed(profile: String) -> void:
	speed_profile = profile
	speed_multiplier = float(speed_profiles[profile])
	if game_state == "jogando" or game_state == "pausado":
		_start_game()
	_refresh_ui()

func _update_riff_scroll() -> void:
	var size := get_viewport_rect().size
	var visible := maxi(1, int((size.y * 0.70 - 140.0) / 118.0))
	if riff_focus < riff_scroll:
		riff_scroll = riff_focus
	elif riff_focus >= riff_scroll + visible:
		riff_scroll = riff_focus - visible + 1

func _adjust_speed(amount: float) -> void:
	if speed_profile == "padrao":
		return
	speed_profiles[speed_profile] = clampf(float(speed_profiles[speed_profile]) + amount, 0.35, 2.0)
	speed_multiplier = float(speed_profiles[speed_profile])
	if game_state == "jogando" or game_state == "pausado":
		_start_game()
	_refresh_ui()

func _handle_click(point: Vector2) -> void:
	var size := get_viewport_rect().size
	if riff_menu_open:
		var menu := Rect2(Vector2(size.x * 0.15, size.y * 0.15), Vector2(size.x * 0.70, size.y * 0.70))
		if not menu.has_point(point):
			if menu_return_to_main:
				_return_from_music_library()
			elif game_state == "pausado":
				riff_menu_open = false
				_toggle_pause()
			else:
				riff_menu_open = false
			_refresh_ui()
			queue_redraw()
			return
		var top := menu.position.y + 100.0
		for i in range(riff_keys.size()):
			var visible_index := i - riff_scroll
			if visible_index < 0 or visible_index >= maxi(1, int((menu.size.y - 140.0) / 118.0)):
				continue
			var card := Rect2(menu.position.x + 24.0, top + visible_index * 118.0, menu.size.x - 48.0, 110.0)
			if card.has_point(point):
				riff_focus = i
				selected_riff = riff_keys[i]
				riff_menu_open = false
				_start_game()
				_refresh_ui()
				queue_redraw()
				return
		return

func _draw() -> void:
	var size := get_viewport_rect().size
	var scale := minf(size.x / 800.0, size.y / 520.0)
	if game_state == "jogando" or game_state == "pausado":
		var elapsed := game_time if game_state == "jogando" else pause_time
		if elapsed < GameConfig.COUNTDOWN:
			_draw_text("%.1f" % (GameConfig.COUNTDOWN - elapsed), Vector2(size.x / 2.0, size.y * 0.43), 64.0 * scale, Color.WHITE, HORIZONTAL_ALIGNMENT_CENTER)
	if not effects.is_empty():
		var effect: Dictionary = effects.back()
		var effect_color: Color = GameConfig.GREEN if effect["ok"] else GameConfig.RED
		effect_color.a = 1.0 - float(effect["age"]) / GameConfig.EFFECT_DURATION
		_draw_text(str(effect["texto"]), Vector2(size.x / 2.0, size.y * 0.40), 30.0 * scale, effect_color, HORIZONTAL_ALIGNMENT_CENTER)
	_draw_tuner(size, scale)
	if riff_menu_open: _draw_riff_menu(size, scale)

func _draw_riff_menu(size: Vector2, scale: float) -> void:
	draw_rect(Rect2(Vector2.ZERO, size), Color(0.01,0.015,0.035,0.96), true)
	var menu := Rect2(Vector2(size.x * 0.15, size.y * 0.15), Vector2(size.x * 0.70, size.y * 0.70))
	draw_rect(menu, Color8(27,31,43), true, 16.0 * scale)
	draw_rect(menu, Color8(105,117,142), false, 2.0 * scale, true)
	_draw_text("BIBLIOTECA DE RIFFS", Vector2(menu.position.x + 28.0, menu.position.y + 48.0), 30.0 * scale, Color.WHITE)
	_draw_text("Escolha um exercício para começar a tocar", Vector2(menu.position.x + 28.0, menu.position.y + 78.0), 18.0 * scale, MUTED)
	var visible_count := maxi(1, int((menu.size.y - 140.0) / 118.0))
	var count := mini(visible_count, riff_keys.size() - riff_scroll)
	for i in count:
		var key_index := riff_scroll + i
		var key := riff_keys[key_index]
		var card := Rect2(menu.position.x + 24.0, menu.position.y + 100.0 + i * 118.0, menu.size.x - 48.0, 110.0)
		var selected := key == selected_riff
		var focused := key_index == riff_focus
		draw_rect(card, Color8(39,78,66) if selected else Color8(38,43,57), true, 10.0)
		draw_rect(card, Color8(92,227,160) if selected else (Color8(255,204,102) if focused else Color8(72,82,108)), false, 2.0 * scale, true)
		_draw_text(str(riffs[key]["nome"]), Vector2(card.position.x + 22.0, card.position.y + 34.0), 21.0 * scale, Color.WHITE)
		var description := "%d BPM  •  %s" % [riffs[key]["bpm"], riffs[key]["descricao"]]
		var description_lines := _wrap_menu_description(description, card.size.x - 44.0, 15.0 * scale, 2)
		for line_index in description_lines.size():
			_draw_text(description_lines[line_index], Vector2(card.position.x + 22.0, card.position.y + 64.0 + line_index * 18.0 * scale), 15.0 * scale, MUTED)
	_draw_text("Setas para navegar  •  Enter para escolher  •  Esc para fechar", Vector2(menu.get_center().x, menu.end.y - 22.0), 16.0 * scale, MUTED, HORIZONTAL_ALIGNMENT_CENTER)

func _wrap_menu_description(text: String, max_width: float, font_size: float, max_lines: int) -> Array[String]:
	var result: Array[String] = []
	var font := ThemeDB.fallback_font
	if font == null:
		var fallback: Array[String] = [text]
		return fallback
	var pixel_size := maxi(10, roundi(font_size))
	var current := ""
	var truncated := false
	for word in text.split(" ", false):
		var candidate := word if current.is_empty() else current + " " + word
		if font.get_string_size(candidate, HORIZONTAL_ALIGNMENT_LEFT, -1.0, pixel_size).x > max_width and not current.is_empty():
			result.append(current)
			current = word
			if result.size() >= max_lines:
				truncated = true
				break
		else:
			current = candidate
	if not current.is_empty() and result.size() < max_lines:
		result.append(current)
	if truncated and not result.is_empty():
		var last := result.size() - 1
		var shortened := result[last]
		while not shortened.is_empty() and font.get_string_size(shortened + "…", HORIZONTAL_ALIGNMENT_LEFT, -1.0, pixel_size).x > max_width:
			shortened = shortened.left(shortened.length() - 1).strip_edges()
		result[last] = shortened + "…"
	return result

func _draw_effects(lanes: Array[float], top: float, end_y: float, target_y: float, radius: float, scale: float, size: Vector2) -> void:
	for effect in effects:
		var alpha := 1.0 - float(effect["age"]) / GameConfig.EFFECT_DURATION
		var color: Color = GameConfig.GREEN if effect["ok"] else GameConfig.RED
		color.a = alpha * 0.22
		draw_rect(Rect2(lanes[int(effect["corda"])] - 35.0 * scale, top, 70.0 * scale, end_y - top), color, true)
		if effect["ok"]:
			var ring := radius * (1.0 + 1.6 * (1.0 - alpha))
			color.a = alpha
			draw_arc(Vector2(lanes[int(effect["corda"])], target_y), ring, 0.0, TAU, 48, color, 5.0 * scale, true)
	if not effects.is_empty():
		var effect: Dictionary = effects.back()
		var color: Color = GameConfig.GREEN if effect["ok"] else GameConfig.RED
		color.a = 1.0 - float(effect["age"]) / GameConfig.EFFECT_DURATION
		_draw_text(str(effect["texto"]), Vector2(size.x / 2.0, top - 18.0 * scale), 30.0 * scale, color, HORIZONTAL_ALIGNMENT_CENTER)

func _draw_tuner(size: Vector2, scale: float) -> void:
	var center := Vector2(size.x / 2.0, size.y * 0.91)
	var half := 150.0 * scale
	_draw_line(center + Vector2(-half, 0), center + Vector2(half, 0), Color8(90,90,90), 2.0 * scale)
	_draw_line(center + Vector2(0,-12.0 * scale), center + Vector2(0,12.0 * scale), Color8(160,160,160), 2.0 * scale)
	if mic.midi == null:
		_draw_text("--", center + Vector2(0,-30.0 * scale), 36.0 * scale, Color8(120,120,120), HORIZONTAL_ALIGNMENT_CENTER)
		return
	var midi_value := float(mic.midi)
	var rounded := roundi(midi_value)
	var cents := (midi_value - rounded) * 100.0
	var color := GameConfig.GREEN if absf(cents) <= GameConfig.TOLERANCE_CENTS * 0.5 else Color8(240,190,50)
	_draw_text(GameConfig.note_name(rounded), center + Vector2(0,-30.0 * scale), 36.0 * scale, color, HORIZONTAL_ALIGNMENT_CENTER)
	draw_circle(center + Vector2(clampf(cents, -50.0, 50.0) / 50.0 * half, 0), 9.0 * scale, color)
	_draw_text("%+.0f cents" % cents, center + Vector2(0,28.0 * scale), 16.0 * scale, MUTED, HORIZONTAL_ALIGNMENT_CENTER)

func _minimum_lane_speed(radius: float) -> float:
	var last_time := {}
	var shortest := INF
	var sorted_notes := notes.duplicate()
	sorted_notes.sort_custom(func(a: Dictionary, b: Dictionary) -> bool: return float(a["t"]) < float(b["t"]))
	for note in sorted_notes:
		var lane := int(note["corda"])
		if last_time.has(lane):
			var interval := float(note["t"]) - float(last_time[lane])
			if interval > 0.0:
				shortest = minf(shortest, interval)
		last_time[lane] = note["t"]
	return 0.0 if is_inf(shortest) else (2.0 * radius + 8.0) / shortest

func _draw_text(text: String, position: Vector2, size: float, color: Color, align: HorizontalAlignment = HORIZONTAL_ALIGNMENT_LEFT) -> void:
	var font := ThemeDB.fallback_font
	if font == null: return
	var font_size := maxi(10, roundi(size))
	var draw_position := position
	var text_width := font.get_string_size(text, HORIZONTAL_ALIGNMENT_LEFT, -1.0, font_size).x
	if align == HORIZONTAL_ALIGNMENT_CENTER:
		draw_position.x -= text_width * 0.5
	elif align == HORIZONTAL_ALIGNMENT_RIGHT:
		draw_position.x -= text_width
	draw_string(font, draw_position, text, HORIZONTAL_ALIGNMENT_LEFT, -1.0, font_size, color)

func _draw_line(from: Vector2, to: Vector2, color: Color, width: float) -> void:
	draw_line(from, to, color, width, true)
