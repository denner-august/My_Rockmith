"""Configurações e repertório padrão do jogo."""

# ----------------------------------------------------------------------------
# CONFIGURAÇÕES
# ----------------------------------------------------------------------------
RATE = 48000  # taxa nativa do Real Tone Cable
CHUNK = 512  # amostras lidas por vez (~11 ms); menor = menos latência no som
MONITOR_LIGADO = True  # ouvir a guitarra enquanto toca
VOLUME_INICIAL = 0.7  # 0.0 a 1.5
OVERDRIVE_INICIAL = False  # começa com timbre limpo
PORTA_RUIDO = 0.004  # RMS abaixo disso = mudo (só no overdrive, evita chiado)
JANELA_ANALISE = 4096  # amostras analisadas por vez (~85 ms); cobre a corda Mi grave
LIMIAR_SILENCIO = 0.01  # RMS mínimo para considerar que há som (ajuste se necessário)
FMIN, FMAX = (
    70.0,
    1000.0,
)  # faixa de busca (Mi grave = 82 Hz ... traste alto da Mi aguda)

TOLERANCIA_CENTS = 40  # quão afinada precisa estar a nota para acertar
JANELA_ACERTO = 0.15  # segundos antes/depois do tempo da nota
LATENCIA_S = 0.08  # atraso do cabo + buffers (ajustável com ← →)
ACEITAR_OITAVA = False  # True = aceita a mesma nota em qualquer oitava

BPM = 70
ANTECEDENCIA = 3.0  # segundos antes da primeira nota
VELOCIDADE = 220  # velocidade-base visual das notas

NOTAS = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
NOMES_CORDAS = ["E", "A", "D", "G", "B", "e"]
MIDI_CORDAS = [40, 45, 50, 55, 59, 64]  # E2 A2 D3 G3 B3 E4 (afinação padrão)
CORES_CORDAS = [
    (230, 70, 70),
    (240, 190, 50),
    (70, 140, 240),
    (240, 140, 60),
    (80, 200, 100),
    (190, 90, 220),
]

NOMES_SOLFEJO = [
    "Dó",
    "Dó#",
    "Ré",
    "Ré#",
    "Mi",
    "Fá",
    "Fá#",
    "Sol",
    "Sol#",
    "Lá",
    "Lá#",
    "Si",
]

# Escala de Dó maior em duas oitavas, tocada na região da 7ª casa.
# Cada item é (corda, traste); cordas: 0=E grave, 1=A, 2=D, 3=G, 4=B, 5=e aguda.
# A primeira nota é Dó4 na corda D, casa 10; todas as notas ficam na região VII+.
_subida = [
    (2, 10),  # Dó4
    (2, 12),  # Ré4
    (3, 9),   # Mi4
    (3, 10),  # Fá4
    (4, 8),   # Sol4
    (4, 10),  # Lá4
    (5, 7),   # Si4
    (5, 8),   # Dó5
    (5, 10),  # Ré5
    (5, 12),  # Mi5
    (5, 13),  # Fá5
    (5, 15),  # Sol5
    (5, 17),  # Lá5
    (5, 19),  # Si5
    (5, 20),  # Dó6
]
MUSICA = _subida + _subida[-2::-1]
TITULO_MUSICA = "Escala de Dó maior — região da 7ª casa"

# Biblioteca de exercícios. Para adicionar outro riff, inclua uma entrada em RIFFS.
# Eventos: (corda, traste, pulso). Corda 0 = Mi grave; pulso pode ser fracionário.
# O riff da imagem foi transcrito como uma linha monofônica na corda Mi grave.
# A tablatura tem ligaduras, pausas e acordes nas últimas compassos; como o detector
# atual reconhece uma frequência por vez, esses trechos foram simplificados para
# notas individuais, preservando o desenho principal de casas e o andamento de 140 BPM.
def _montar_riff_imagem():
    compassos = [
        [0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,3],
        [3,3,3,3,3,3,3,6],
        [6,1,1,1,1,1,1,0],
        [0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,3],
        [3,3,3,3,3,3,3,6],
        [6,1,1,1,1,1,3,1],
        [0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,3],
        [3,3,3,3,3,3,3,6],
        [6,1,1,1,1,3,1,0],
        [0,0,0,0,0,0,0,0],
        [0,0,0,0,0,0,0,3],
        [3,3,3,3,3,3,3,6],
        [6,1,1,1,1,3,12,0],
        [0,0,0,0,0,0,0,0],
        [0,0,0,0,0,3,3,3],
        [3,3,3,3,3,3,6,6],
        [1,1,1,3,1,0,0,0],
    ]
    return [(0, fret, measure * 4 + i * 0.5)
            for measure, bar in enumerate(compassos)
            for i, fret in enumerate(bar)]

RIFFS = {
    "riff_imagem": {
        "nome": "Riff da tablatura (aproximado)",
        "bpm": 140,
        "eventos": _montar_riff_imagem(),
        "descricao": "Mi grave: abertas, casa 3, casa 6 e casa 1",
    },
    "escala_dó": {
        "nome": "Escala de Dó maior — 7ª casa",
        "bpm": 70,
        "eventos": [(corda, traste, float(i)) for i, (corda, traste) in enumerate(MUSICA)],
        "descricao": "Escala de duas oitavas na região alta do braço",
    },
}

TAMANHO_PADRAO = (1920, 1080)
