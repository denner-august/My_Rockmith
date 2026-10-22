class_name GameConfig
extends RefCounted

const RATE := 48000
const CHUNK := 512
const ANALYSIS_WINDOW := 4096
const SILENCE_THRESHOLD := 0.01
const FMIN := 70.0
const FMAX := 1000.0
const TOLERANCE_CENTS := 40.0
const HIT_WINDOW := 0.15
const DEFAULT_LATENCY := 0.08
const ACCEPT_OCTAVE := false
const COUNTDOWN := 3.0
const BASE_NOTE_SPEED := 220.0
const EFFECT_DURATION := 0.55
const VISIBLE_SECONDS := 1.7

const STRING_NAMES := ["E", "A", "D", "G", "B", "e"]
const STRING_MIDI := [40, 45, 50, 55, 59, 64]
const STRING_COLORS := [
	Color8(230, 70, 70), Color8(240, 190, 50), Color8(70, 140, 240),
	Color8(240, 140, 60), Color8(80, 200, 100), Color8(190, 90, 220)
]
const NOTE_NAMES := ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
const SOLFEGE := ["Dó", "Dó#", "Ré", "Ré#", "Mi", "Fá", "Fá#", "Sol", "Sol#", "Lá", "Lá#", "Si"]
const GREEN := Color8(60, 220, 110)
const RED := Color8(235, 60, 60)

static func default_riffs() -> Dictionary:
	var bars := [
		[0,0,0,0,0,0,0,0], [0,0,0,0,0,0,0,3], [3,3,3,3,3,3,3,6], [6,1,1,1,1,1,1,0],
		[0,0,0,0,0,0,0,0], [0,0,0,0,0,0,0,3], [3,3,3,3,3,3,3,6], [6,1,1,1,1,1,3,1],
		[0,0,0,0,0,0,0,0], [0,0,0,0,0,0,0,3], [3,3,3,3,3,3,3,6], [6,1,1,1,1,3,1,0],
		[0,0,0,0,0,0,0,0], [0,0,0,0,0,0,0,3], [3,3,3,3,3,3,3,6], [6,1,1,1,1,3,12,0],
		[0,0,0,0,0,0,0,0], [0,0,0,0,0,3,3,3], [3,3,3,3,3,3,6,6], [1,1,1,3,1,0,0,0]
	]
	var image_events: Array[Dictionary] = []
	for bar_index in bars.size():
		for beat_index in bars[bar_index].size():
			image_events.append({"corda": 0, "traste": bars[bar_index][beat_index], "pulso": bar_index * 4.0 + beat_index * 0.5})

	var scale := [[2,10],[2,12],[3,9],[3,10],[4,8],[4,10],[5,7],[5,8],[5,10],[5,12],[5,13],[5,15],[5,17],[5,19],[5,20]]
	var scale_events: Array[Dictionary] = []
	for i in range(scale.size()):
		scale_events.append({"corda": scale[i][0], "traste": scale[i][1], "pulso": float(i)})
	for i in range(scale.size() - 2, -1, -1):
		scale_events.append({"corda": scale[i][0], "traste": scale[i][1], "pulso": float(scale_events.size())})
	return {
		"riff_imagem": {"nome": "Riff da tablatura (aproximado)", "bpm": 140, "eventos": image_events, "descricao": "Mi grave: abertas, casa 3, casa 6 e casa 1"},
		"escala_dó": {"nome": "Escala de Dó maior — 7ª casa", "bpm": 70, "eventos": scale_events, "descricao": "Escala de duas oitavas na região alta do braço"}
	}

static func note_name(midi: int) -> String:
	return "%s%d" % [SOLFEGE[posmod(midi, 12)], floori(float(midi) / 12.0) - 1]

static func pitch_matches(detected: Variant, target: int) -> bool:
	if detected == null:
		return false
	var difference: float = float(detected) - target
	if ACCEPT_OCTAVE:
		difference = fposmod(difference + 6.0, 12.0) - 6.0
	return absf(difference) * 100.0 <= TOLERANCE_CENTS
