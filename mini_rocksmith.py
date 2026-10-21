#!/usr/bin/env python3
"""
Mini Rocksmith v2 - Real Tone Cable + pygame + pyaudio

Uso:
    python mini_rocksmith.py --listar          # lista entradas e saídas de áudio
    python mini_rocksmith.py                   # procura "Rocksmith" no nome
    python mini_rocksmith.py --dispositivo 2   # força a entrada (cabo)
    python mini_rocksmith.py --saida 5         # força a saída (fone/caixa)
    python mini_rocksmith.py --sem-monitor     # desliga o som da guitarra
    python mini_rocksmith.py --tamanho 920x1080  # outro tamanho (padrão 1920x1080)
    python mini_rocksmith.py --janela          # começa em janela, não em tela cheia

Teclas:
    ESPAÇO  começar / jogar de novo
    P       pausar / continuar
    R       reiniciar escala
    - / +   diminuir / aumentar velocidade
    T       ligar/desligar metrônomo
    F11     tela cheia / janela
    ← / →   ajusta a latência do acerto (-/+ 10 ms)
    M       liga/desliga o som da guitarra
    ↑ / ↓   volume do som da guitarra
    D       alterna timbre limpo / overdrive
    ESC     sair

DICA: use fone de ouvido. O cabo entrega o sinal "seco" da guitarra, então o
timbre limpo soa fino; o overdrive (tecla D) deixa mais parecido com um amp.

Dependências: pip install numpy pyaudio pygame
"""

import argparse
import sys
import threading
import time
from collections import deque

import numpy as np
import pyaudio
import pygame

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
    (3, 9),  # Mi4
    (3, 10),  # Fá4
    (4, 8),  # Sol4
    (4, 10),  # Lá4
    (5, 7),  # Si4
    (5, 8),  # Dó5
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
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 3],
        [3, 3, 3, 3, 3, 3, 3, 6],
        [6, 1, 1, 1, 1, 1, 1, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 3],
        [3, 3, 3, 3, 3, 3, 3, 6],
        [6, 1, 1, 1, 1, 1, 3, 1],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 3],
        [3, 3, 3, 3, 3, 3, 3, 6],
        [6, 1, 1, 1, 1, 3, 1, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 0, 0, 3],
        [3, 3, 3, 3, 3, 3, 3, 6],
        [6, 1, 1, 1, 1, 3, 12, 0],
        [0, 0, 0, 0, 0, 0, 0, 0],
        [0, 0, 0, 0, 0, 3, 3, 3],
        [3, 3, 3, 3, 3, 3, 6, 6],
        [1, 1, 1, 3, 1, 0, 0, 0],
    ]
    return [
        (0, fret, measure * 4 + i * 0.5)
        for measure, bar in enumerate(compassos)
        for i, fret in enumerate(bar)
    ]


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
        "eventos": [
            (corda, traste, float(i)) for i, (corda, traste) in enumerate(MUSICA)
        ],
        "descricao": "Escala de duas oitavas na região alta do braço",
    },
}


# ----------------------------------------------------------------------------
# DETECÇÃO DE PITCH
# ----------------------------------------------------------------------------
def detectar_frequencia(audio, rate):
    """Autocorrelação via FFT + escolha do primeiro pico forte + interpolação.

    Retorna (frequência em Hz ou 0.0 se não há nota, nível RMS).
    """
    audio = audio - np.mean(audio)
    rms = float(np.sqrt(np.mean(audio**2)))
    if rms < LIMIAR_SILENCIO:
        return 0.0, rms

    n = len(audio)
    espectro = np.fft.rfft(audio, n=2 * n)
    corr = np.fft.irfft(espectro * np.conj(espectro))[:n]
    if corr[0] <= 0:
        return 0.0, rms
    corr = corr / corr[0]

    lag_min = int(rate / FMAX)
    lag_max = min(int(rate / FMIN), n - 2)
    idx = np.arange(lag_min, lag_max)
    c = corr[idx]
    eh_pico = (c > corr[idx - 1]) & (c >= corr[idx + 1]) & (c > 0.3)
    picos = idx[eh_pico]
    if len(picos) == 0:
        return 0.0, rms

    # Guitarra tem harmônicos fortes: o maior pico às vezes é o múltiplo do período
    # (oitava abaixo) e o primeiro às vezes é o submúltiplo (oitava acima).
    # Regra: pega o PRIMEIRO pico que seja pelo menos 85% do melhor.
    melhor = corr[picos].max()
    lag = int(picos[np.argmax(corr[picos] >= 0.85 * melhor)])

    # Interpolação parabólica: precisão sub-amostra (importante nas notas agudas)
    a, b, c0 = corr[lag - 1], corr[lag], corr[lag + 1]
    den = a - 2 * b + c0
    delta = 0.5 * (a - c0) / den if den != 0 else 0.0
    return rate / (lag + delta), rms


_KERNEL_CAIXA = (
    np.array([1, 2, 3, 2, 1], dtype=np.float32) / 9.0
)  # filtro passa-baixa suave


def processar_monitor(dados, volume, overdrive, historico):
    """Prepara o sinal da guitarra para sair no fone/caixa.

    Limpo: só volume. Overdrive: ganho + saturação (tanh) + passa-baixa que imita
    uma caixa de amp + porta de ruído. `historico` guarda as últimas amostras do
    bloco anterior para o filtro não "quebrar" entre blocos.
    Retorna (saida float32 em [-1, 1], novo historico).
    """
    if overdrive:
        if np.sqrt(np.mean(dados**2)) < PORTA_RUIDO:
            return np.zeros_like(dados), historico
        saturado = np.tanh(dados * 10.0) * 0.5
        ext = np.concatenate([historico, saturado])
        saida = np.convolve(ext, _KERNEL_CAIXA, mode="valid").astype(np.float32)
        novo_hist = ext[-(len(_KERNEL_CAIXA) - 1) :]
    else:
        saida = dados
        novo_hist = historico
    return np.clip(saida * volume, -1.0, 1.0).astype(np.float32), novo_hist


def freq_para_midi(freq):
    return 69 + 12 * np.log2(freq / 440.0)


def nome_nota(midi_int):
    return f"{NOTAS[midi_int % 12]}{midi_int // 12 - 1}"


class DetectorPitch(threading.Thread):
    """Lê o cabo em uma thread própria e guarda a última nota detectada."""

    def __init__(self, stream, rate, canais, saida=None, canais_saida=1):
        super().__init__(daemon=True)
        self.stream = stream
        self.rate = rate
        self.canais = canais
        self.saida = saida  # stream de saída (fone/caixa) ou None
        self.canais_saida = canais_saida
        self.monitor = MONITOR_LIGADO and saida is not None
        self.volume = VOLUME_INICIAL
        self.overdrive = OVERDRIVE_INICIAL
        self._hist = np.zeros(len(_KERNEL_CAIXA) - 1, dtype=np.float32)
        self.buffer = np.zeros(JANELA_ANALISE, dtype=np.float32)
        self.historico = deque(maxlen=3)
        self.lock = threading.Lock()
        self.midi = None  # nota atual (float, suavizada) ou None
        self.nivel = 0.0
        self.erro = None
        self.ativo = True

    def run(self):
        while self.ativo:
            try:
                bruto = self.stream.read(CHUNK, exception_on_overflow=False)
            except Exception as e:  # noqa: BLE001
                self.erro = str(e)
                break
            dados = np.frombuffer(bruto, dtype=np.float32)
            if self.canais > 1:
                dados = dados[:: self.canais]  # usa só o primeiro canal

            # Som da guitarra: sai logo, antes da análise, para ter o mínimo de atraso
            if self.saida is not None and self.monitor:
                try:
                    som, self._hist = processar_monitor(
                        dados, self.volume, self.overdrive, self._hist
                    )
                    if self.canais_saida > 1:
                        som = np.repeat(som[:, None], self.canais_saida, axis=1)
                    self.saida.write(som.tobytes(), exception_on_underflow=False)
                except Exception:  # noqa: BLE001
                    self.monitor = False  # saída com problema: o jogo continua sem som

            self.buffer = np.roll(self.buffer, -len(dados))
            self.buffer[-len(dados) :] = dados

            freq, nivel = detectar_frequencia(self.buffer, self.rate)
            self.historico.append(freq_para_midi(freq) if freq > 0 else None)

            validos = [m for m in self.historico if m is not None]
            # precisa de pelo menos 2 de 3 detecções válidas; usa a mediana
            suave = float(np.median(validos)) if len(validos) >= 2 else None

            with self.lock:
                self.midi = suave
                self.nivel = nivel

    def estado(self):
        with self.lock:
            return self.midi, self.nivel

    def parar(self):
        self.ativo = False


# ----------------------------------------------------------------------------
# DISPOSITIVOS DE ÁUDIO
# ----------------------------------------------------------------------------
def listar_dispositivos(p):
    print("Entradas de áudio disponíveis (use em --dispositivo):")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0:
            print(
                f"  [{i}] {info['name']}  "
                f"({info['maxInputChannels']} canal(is), {int(info['defaultSampleRate'])} Hz)"
            )
    print("\nSaídas de áudio disponíveis (use em --saida):")
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxOutputChannels"] > 0:
            print(
                f"  [{i}] {info['name']}  "
                f"({info['maxOutputChannels']} canal(is), {int(info['defaultSampleRate'])} Hz)"
            )


def abrir_saida(p, taxa, indice=None):
    """Abre a saída de áudio (fone/caixa). Retorna (stream, canais) ou (None, 0)."""
    try:
        if indice is None:
            indice = p.get_default_output_device_info()["index"]
        info = p.get_device_info_by_index(indice)
    except Exception as e:  # noqa: BLE001
        print(f"Sem saída de áudio padrão ({e}); jogo segue sem o som da guitarra.")
        return None, 0
    canais = 2 if info["maxOutputChannels"] >= 2 else 1
    try:
        stream = p.open(
            format=pyaudio.paFloat32,
            channels=canais,
            rate=taxa,
            output=True,
            output_device_index=indice,
            frames_per_buffer=CHUNK,
        )
        print(f"Som da guitarra saindo em: [{indice}] {info['name']}")
        return stream, canais
    except Exception as e:  # noqa: BLE001
        print(
            f"Não consegui abrir a saída [{indice}] {info['name']} a {taxa} Hz: {e}\n"
            "O jogo segue sem o som da guitarra (tente --saida N)."
        )
        return None, 0


def achar_cabo(p):
    for i in range(p.get_device_count()):
        info = p.get_device_info_by_index(i)
        if info["maxInputChannels"] > 0 and "rocksmith" in info["name"].lower():
            return i
    return None


def abrir_stream(p, indice):
    """Tenta 48 kHz mono; se falhar, tenta a taxa padrão e/ou 2 canais."""
    info = p.get_device_info_by_index(indice)
    taxas = [RATE]
    padrao = int(info["defaultSampleRate"])
    if padrao != RATE:
        taxas.append(padrao)
    ultimo_erro = None
    for taxa in taxas:
        for canais in (1, 2):
            if canais > info["maxInputChannels"]:
                continue
            try:
                stream = p.open(
                    format=pyaudio.paFloat32,
                    channels=canais,
                    rate=taxa,
                    input=True,
                    input_device_index=indice,
                    frames_per_buffer=CHUNK,
                )
                return stream, taxa, canais
            except Exception as e:  # noqa: BLE001
                ultimo_erro = e
    raise RuntimeError(f"Não consegui abrir o dispositivo {indice}: {ultimo_erro}")


# ----------------------------------------------------------------------------
# JOGO
# ----------------------------------------------------------------------------
VERDE = (60, 220, 110)
VERMELHO = (235, 60, 60)
DURACAO_EFEITO = 0.55  # segundos que o feedback de acerto/erro fica na tela
VISIVEL_S = 4.5  # mais segundos visíveis: as notas aparecem mais longe
TAMANHO_PADRAO = (1920, 1080)


class Layout:
    """Todas as posições e tamanhos derivados do tamanho da tela."""

    def __init__(self, largura, altura):
        self.l, self.a = largura, altura
        self.esc = min(
            largura / 800.0, altura / 520.0
        )  # fator de escala para fontes/traços
        self.topo = int(altura * 0.08)  # pista começa mais alto para dar visão distante
        self.alvo_y = int(altura * 0.68)  # linha de acerto
        self.fim_y = int(altura * 0.74)  # fim das pistas
        self.gap = min(altura * 0.17, largura * 0.8 / 6)  # distância entre as cordas
        x0 = largura / 2 - 2.5 * self.gap
        self.lane_x = [int(x0 + i * self.gap) for i in range(6)]
        self.raio = int(self.gap * 0.27)  # raio das notas
        self.velocidade = (self.alvo_y - self.topo) / VISIVEL_S  # pixels por segundo
        self.nome_y = int(altura * 0.765)  # letras E A D G B e
        self.afin_y = int(altura * 0.91)  # afinador
        self.traco = max(2, int(4 * self.esc))


def render_cabe(fonte, texto, cor, largura_max):
    """Renderiza o texto e, se passar de largura_max, encolhe para caber na tela."""
    surf = fonte.render(texto, True, cor)
    if surf.get_width() > largura_max:
        f = largura_max / surf.get_width()
        surf = pygame.transform.smoothscale(
            surf, (int(largura_max), max(1, int(surf.get_height() * f)))
        )
    return surf


def nome_pt(midi_int):
    return f"{NOMES_SOLFEJO[midi_int % 12]}{midi_int // 12 - 1}"


def criar_notas(chave_riff):
    riff = RIFFS[chave_riff]
    passo = 60.0 / riff["bpm"]
    notas = []
    for corda, traste, pulso in riff["eventos"]:
        notas.append(
            {
                "t": ANTECEDENCIA + pulso * passo,
                "corda": corda,
                "traste": traste,
                "midi": MIDI_CORDAS[corda] + traste,
                "estado": "pendente",  # pendente | acertou | errou
            }
        )
    return notas


def nota_confere(midi_detectado, midi_alvo):
    if midi_detectado is None:
        return False
    if ACEITAR_OITAVA:
        diff = (midi_detectado - midi_alvo + 6) % 12 - 6
    else:
        diff = midi_detectado - midi_alvo
    return abs(diff) * 100 <= TOLERANCIA_CENTS


def desenhar_afinador(tela, lay, fonte, fonte_g, midi):
    cx, cy = lay.l // 2, lay.afin_y
    meia = int(150 * lay.esc)
    pygame.draw.line(
        tela, (90, 90, 90), (cx - meia, cy), (cx + meia, cy), lay.traco // 2 or 1
    )
    pygame.draw.line(
        tela,
        (160, 160, 160),
        (cx, cy - int(12 * lay.esc)),
        (cx, cy + int(12 * lay.esc)),
        lay.traco // 2 or 1,
    )
    if midi is None:
        txt = fonte_g.render("--", True, (120, 120, 120))
        tela.blit(txt, txt.get_rect(center=(cx, cy - int(32 * lay.esc))))
        return
    inteiro = int(round(midi))
    cents = (midi - inteiro) * 100
    cor = VERDE if abs(cents) <= TOLERANCIA_CENTS * 0.5 else (240, 190, 50)
    txt = fonte_g.render(nome_pt(inteiro), True, cor)
    tela.blit(txt, txt.get_rect(center=(cx, cy - int(32 * lay.esc))))
    x = cx + max(-50, min(50, cents)) / 50.0 * meia
    pygame.draw.circle(tela, cor, (int(x), cy), int(9 * lay.esc))
    leg = fonte.render(f"{cents:+.0f} cents", True, (170, 170, 170))
    tela.blit(leg, leg.get_rect(center=(cx, cy + int(28 * lay.esc))))


def desenhar_efeitos(tela, camada, lay, fonte_g, efeitos, agora):
    """Feedback visual: verde = acerto, vermelho = erro. Devolve só os efeitos ainda vivos."""
    camada.fill((0, 0, 0, 0))
    vivos, textos = [], []
    for ef in efeitos:
        idade = agora - ef["t"]
        if idade >= DURACAO_EFEITO:
            continue
        vivos.append(ef)
        prog = idade / DURACAO_EFEITO  # 0 -> 1
        k = 1.0 - prog  # 1 -> 0 (some aos poucos)
        acerto = ef["tipo"] == "acerto"
        cor = VERDE if acerto else VERMELHO
        x = lay.lane_x[ef["corda"]]

        # brilho na pista inteira
        larg = int(lay.gap * 0.9)
        pygame.draw.rect(
            camada,
            (*cor, int(110 * k)),
            (x - larg // 2, lay.topo, larg, lay.fim_y - lay.topo),
        )
        # borda da tela
        pygame.draw.rect(
            camada,
            (*cor, int(140 * k)),
            (0, 0, lay.l, lay.a),
            max(6, int(12 * lay.esc)),
        )

        if acerto:  # anel que se expande a partir da linha de acerto
            r = int(lay.raio * (1.0 + 1.6 * prog))
            pygame.draw.circle(
                camada,
                (*cor, int(255 * k)),
                (x, lay.alvo_y),
                r,
                max(3, int(6 * lay.esc)),
            )
        else:  # X vermelho
            r = int(lay.raio * 0.9)
            w = max(4, int(9 * lay.esc))
            pygame.draw.line(
                camada,
                (*cor, int(255 * k)),
                (x - r, lay.alvo_y - r),
                (x + r, lay.alvo_y + r),
                w,
            )
            pygame.draw.line(
                camada,
                (*cor, int(255 * k)),
                (x - r, lay.alvo_y + r),
                (x + r, lay.alvo_y - r),
                w,
            )

        # texto: acerto sobe, erro desce
        base = lay.alvo_y - lay.raio * 2.2
        ty = base - prog * lay.gap * 0.6 if acerto else base + prog * lay.gap * 0.4
        textos.append((ef["texto"], cor, x, ty, k))

    tela.blit(camada, (0, 0))
    for texto, cor, x, ty, k in textos:
        surf = render_cabe(fonte_g, texto, cor, lay.l * 0.5)
        surf.set_alpha(int(255 * k))
        r = surf.get_rect(center=(int(x), int(ty)))
        r.clamp_ip(pygame.Rect(0, 0, lay.l, lay.a))  # nunca sai da tela
        tela.blit(surf, r)
    return vivos


def desenhar_botao(tela, fonte, rect, texto, ativo=False):
    cor = (55, 105, 80) if ativo else (55, 58, 68)
    pygame.draw.rect(tela, cor, rect, border_radius=8)
    pygame.draw.rect(tela, (130, 135, 150), rect, width=2, border_radius=8)
    surf = fonte.render(texto, True, (245, 245, 245))
    tela.blit(surf, surf.get_rect(center=rect.center))


def criar_click(frequencia, duracao=0.045, volume=0.35):
    """Cria um clique curto para o metrônomo usando o mixer do Pygame."""
    taxa = 22050
    n = int(taxa * duracao)
    t = np.arange(n, dtype=np.float32) / taxa
    envelope = np.linspace(1.0, 0.0, n, dtype=np.float32)
    onda = np.sin(2 * np.pi * frequencia * t) * envelope * volume
    pcm = np.asarray(onda * 32767, dtype=np.int16)
    return pygame.mixer.Sound(buffer=pcm.tobytes())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--listar", action="store_true", help="lista as entradas de áudio"
    )
    parser.add_argument("--dispositivo", type=int, help="índice da entrada de áudio")
    parser.add_argument(
        "--saida", type=int, help="índice da saída de áudio (fone/caixa)"
    )
    parser.add_argument(
        "--sem-monitor", action="store_true", help="não reproduzir o som da guitarra"
    )
    parser.add_argument(
        "--tamanho",
        default=f"{TAMANHO_PADRAO[0]}x{TAMANHO_PADRAO[1]}",
        help="tamanho da tela, ex.: 1920x1080 ou 920x1080",
    )
    parser.add_argument(
        "--janela", action="store_true", help="começa em janela (sem tela cheia)"
    )
    args = parser.parse_args()

    try:
        largura, altura = (int(v) for v in args.tamanho.lower().split("x"))
    except ValueError:
        print("Use --tamanho LARGURAxALTURA, por exemplo 1920x1080")
        sys.exit(1)

    p = pyaudio.PyAudio()
    if args.listar:
        listar_dispositivos(p)
        p.terminate()
        return

    indice = args.dispositivo if args.dispositivo is not None else achar_cabo(p)
    if indice is None:
        print('Não encontrei nenhuma entrada com "Rocksmith" no nome.')
        listar_dispositivos(p)
        print("\nRode de novo com: python mini_rocksmith.py --dispositivo N")
        p.terminate()
        sys.exit(1)

    try:
        stream, taxa, canais = abrir_stream(p, indice)
    except RuntimeError as e:
        print(e)
        p.terminate()
        sys.exit(1)

    saida, canais_saida = (
        (None, 0) if args.sem_monitor else abrir_saida(p, taxa, args.saida)
    )

    detector = DetectorPitch(stream, taxa, canais, saida, canais_saida)
    detector.start()

    pygame.init()
    try:
        pygame.mixer.init(frequency=22050, size=-16, channels=1, buffer=512)
        click_forte = criar_click(1100, volume=0.42)
        click_fraco = criar_click(750, volume=0.25)
        metronomo_disponivel = True
    except pygame.error:
        click_forte = click_fraco = None
        metronomo_disponivel = False
    flags = pygame.SCALED | (0 if args.janela else pygame.FULLSCREEN)
    tela = pygame.display.set_mode((largura, altura), flags)
    pygame.display.set_caption("Mini Rocksmith v2")
    lay = Layout(largura, altura)
    camada = pygame.Surface((largura, altura), pygame.SRCALPHA)
    clock = pygame.time.Clock()
    fonte = pygame.font.SysFont(None, int(24 * lay.esc))
    fonte_g = pygame.font.SysFont(None, int(48 * lay.esc))
    fonte_t = pygame.font.SysFont(None, int(64 * lay.esc))
    fonte_n = pygame.font.SysFont(None, int(26 * lay.esc))  # nome da nota sob a bolinha

    latencia = LATENCIA_S
    riff_selecionado = "riff_imagem"
    menu_riffs_aberto = False
    estado_jogo = "espera"  # espera | jogando | pausado | fim
    notas, t0 = [], 0.0
    pausado_em = None
    velocidade_nota = 0.75  # multiplicador ajustável: 0.5 a 1.25
    metronomo_ligado = True
    ultimo_tique = -1
    pontos = combo = melhor_combo = acertos = erros = 0
    efeitos = []

    def iniciar():
        return criar_notas(riff_selecionado), time.perf_counter(), 0, 0, 0, 0, 0

    escala_ui = lay.esc
    bw, bh = int(120 * escala_ui), int(42 * escala_ui)
    espacamento = int(8 * escala_ui)
    by = int(76 * escala_ui)
    bx0 = (
        lay.l - (bw * 4 + int(108 * escala_ui) + espacamento * 5) - int(16 * escala_ui)
    )
    botoes = {
        "menu": pygame.Rect(bx0, by, bw, bh),
        "pause": pygame.Rect(bx0 + bw + espacamento, by, bw, bh),
        "restart": pygame.Rect(bx0 + 2 * (bw + espacamento), by, bw, bh),
        "metro": pygame.Rect(bx0 + 3 * (bw + espacamento), by, bw, bh),
        "menos": pygame.Rect(bx0 + 4 * (bw + espacamento), by, int(54 * escala_ui), bh),
        "mais": pygame.Rect(
            bx0 + 4 * (bw + espacamento) + int(58 * escala_ui),
            by,
            int(54 * escala_ui),
            bh,
        ),
    }
    menu_rect = pygame.Rect(
        int(lay.l * 0.30), int(lay.a * 0.22), int(lay.l * 0.40), int(lay.a * 0.56)
    )
    riff_botoes = {}
    item_h = int(58 * escala_ui)
    for idx, chave in enumerate(RIFFS):
        riff_botoes[chave] = pygame.Rect(
            menu_rect.x + int(24 * escala_ui),
            menu_rect.y + int(72 * escala_ui) + idx * (item_h + int(10 * escala_ui)),
            menu_rect.width - int(48 * escala_ui),
            item_h,
        )

    def reiniciar():
        nonlocal notas, t0, pontos, combo, melhor_combo, acertos, erros, efeitos, estado_jogo, pausado_em, ultimo_tique
        notas, t0, pontos, combo, melhor_combo, acertos, erros = iniciar()
        efeitos = []
        estado_jogo = "jogando"
        pausado_em = None
        ultimo_tique = -1

    def alternar_pause():
        nonlocal estado_jogo, pausado_em, t0, efeitos
        if estado_jogo == "jogando":
            estado_jogo = "pausado"
            pausado_em = time.perf_counter()
        elif estado_jogo == "pausado":
            agora_resume = time.perf_counter()
            pausa = agora_resume - pausado_em
            t0 += pausa
            for ef in efeitos:
                ef["t"] += pausa
            estado_jogo = "jogando"
            pausado_em = None

    rodando = True
    while rodando:
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT:
                rodando = False
            elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button == 1:
                pos = ev.pos
                if menu_riffs_aberto:
                    escolhido = next(
                        (
                            k
                            for k, rect in riff_botoes.items()
                            if rect.collidepoint(pos)
                        ),
                        None,
                    )
                    if escolhido is not None:
                        riff_selecionado = escolhido
                        menu_riffs_aberto = False
                        reiniciar()
                    elif not menu_rect.collidepoint(pos):
                        menu_riffs_aberto = False
                        if estado_jogo == "pausado":
                            alternar_pause()
                elif botoes["menu"].collidepoint(pos):
                    menu_riffs_aberto = True
                    if estado_jogo == "jogando":
                        alternar_pause()
                elif botoes["pause"].collidepoint(pos):
                    alternar_pause()
                elif botoes["restart"].collidepoint(pos):
                    reiniciar()
                elif botoes["metro"].collidepoint(pos):
                    metronomo_ligado = not metronomo_ligado
                elif botoes["menos"].collidepoint(pos):
                    velocidade_nota = max(0.5, round(velocidade_nota - 0.1, 2))
                elif botoes["mais"].collidepoint(pos):
                    velocidade_nota = min(1.25, round(velocidade_nota + 0.1, 2))
            elif ev.type == pygame.KEYDOWN:
                if ev.key == pygame.K_ESCAPE:
                    rodando = False
                elif ev.key == pygame.K_F11:
                    pygame.display.toggle_fullscreen()
                elif ev.key == pygame.K_SPACE and estado_jogo in ("espera", "fim"):
                    reiniciar()
                elif ev.key == pygame.K_p:
                    alternar_pause()
                elif ev.key == pygame.K_r:
                    reiniciar()
                elif ev.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    velocidade_nota = max(0.5, round(velocidade_nota - 0.1, 2))
                elif ev.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    velocidade_nota = min(1.25, round(velocidade_nota + 0.1, 2))
                elif ev.key == pygame.K_t:
                    metronomo_ligado = not metronomo_ligado
                elif ev.key == pygame.K_m and detector.saida is not None:
                    detector.monitor = not detector.monitor
                elif ev.key == pygame.K_d:
                    detector.overdrive = not detector.overdrive
                elif ev.key == pygame.K_UP:
                    detector.volume = min(1.5, detector.volume + 0.1)
                elif ev.key == pygame.K_DOWN:
                    detector.volume = max(0.0, detector.volume - 0.1)
                elif ev.key == pygame.K_LEFT:
                    latencia = max(0.0, latencia - 0.01)
                elif ev.key == pygame.K_RIGHT:
                    latencia = min(0.5, latencia + 0.01)

        if detector.erro:
            print(f"Erro de áudio: {detector.erro}")
            break

        agora = time.perf_counter()
        midi, nivel = detector.estado()
        tela.fill((24, 24, 28))

        # Pistas (cordas)
        for i, x in enumerate(lay.lane_x):
            pygame.draw.line(
                tela, (55, 55, 62), (x, lay.topo), (x, lay.fim_y), lay.traco // 2 or 1
            )
            rot = fonte.render(NOMES_CORDAS[i], True, CORES_CORDAS[i])
            tela.blit(rot, rot.get_rect(center=(x, lay.nome_y)))
        ext = int(lay.gap * 0.45)
        pygame.draw.line(
            tela,
            (255, 255, 255),
            (lay.lane_x[0] - ext, lay.alvo_y),
            (lay.lane_x[-1] + ext, lay.alvo_y),
            lay.traco,
        )

        if estado_jogo == "jogando":
            st = agora - t0
            if metronomo_ligado and metronomo_disponivel:
                bpm_atual = RIFFS[riff_selecionado]["bpm"]
                beat = int(st * bpm_atual / 60.0)
                if beat > ultimo_tique and st >= 0:
                    (click_forte if beat % 4 == 0 else click_fraco).play()
                    ultimo_tique = beat
            st_audio = st - latencia  # o som chega atrasado: compensa

            for n in notas:
                if n["estado"] != "pendente":
                    continue
                if st_audio > n["t"] + JANELA_ACERTO:
                    n["estado"] = "errou"
                    erros += 1
                    combo = 0
                    efeitos.append(
                        {
                            "tipo": "erro",
                            "corda": n["corda"],
                            "t": agora,
                            "texto": "ERROU",
                        }
                    )
                elif abs(st_audio - n["t"]) <= JANELA_ACERTO and nota_confere(
                    midi, n["midi"]
                ):
                    n["estado"] = "acertou"
                    acertos += 1
                    combo += 1
                    melhor_combo = max(melhor_combo, combo)
                    perfeito = abs(st_audio - n["t"]) <= 0.06
                    ganho = 100 + min(combo, 10) * 10 + (50 if perfeito else 0)
                    pontos += ganho
                    efeitos.append(
                        {
                            "tipo": "acerto",
                            "corda": n["corda"],
                            "t": agora,
                            "texto": f"{'PERFEITO' if perfeito else 'BOA'}  +{ganho}",
                        }
                    )

            # Notas descendo
            for n in notas:
                if n["estado"] == "acertou":
                    continue  # o efeito verde toma o lugar dela
                y = lay.alvo_y - (n["t"] - st) * lay.velocidade * velocidade_nota
                if y < lay.topo - lay.raio or y > lay.fim_y:
                    continue
                x = lay.lane_x[n["corda"]]
                errou = n["estado"] == "errou"
                cor = (110, 45, 45) if errou else CORES_CORDAS[n["corda"]]
                pygame.draw.circle(tela, cor, (x, int(y)), lay.raio)
                tx = fonte_g.render(
                    str(n["traste"]), True, (255, 255, 255) if errou else (0, 0, 0)
                )
                tela.blit(tx, tx.get_rect(center=(x, int(y))))
                nm = fonte_n.render(
                    NOMES_SOLFEJO[n["midi"] % 12],
                    True,
                    (150, 90, 90) if errou else (230, 230, 230),
                )
                tela.blit(
                    nm, nm.get_rect(center=(x, int(y) + lay.raio + int(14 * lay.esc)))
                )

            if st < ANTECEDENCIA:
                cont = fonte_t.render(f"{ANTECEDENCIA - st:.1f}", True, (255, 255, 255))
                tela.blit(cont, cont.get_rect(center=(lay.l // 2, int(lay.a * 0.35))))

            if all(n["estado"] != "pendente" for n in notas):
                estado_jogo = "fim"

        elif estado_jogo == "espera":
            msg = render_cabe(
                fonte_g,
                "Toque uma corda para testar - ESPAÇO para começar",
                (255, 255, 255),
                lay.l * 0.92,
            )
            tela.blit(msg, msg.get_rect(center=(lay.l // 2, int(lay.a * 0.30))))
            sub = fonte.render(
                f"Selecionado: {RIFFS[riff_selecionado]['nome']} — ESPAÇO para começar",
                True,
                (170, 170, 190),
            )
            tela.blit(
                sub,
                sub.get_rect(
                    center=(lay.l // 2, int(lay.a * 0.30) + int(50 * lay.esc))
                ),
            )
            if nivel < LIMIAR_SILENCIO:
                aviso = fonte.render(
                    "(sem sinal do cabo: confira o dispositivo/volume)",
                    True,
                    (200, 120, 120),
                )
                tela.blit(
                    aviso,
                    aviso.get_rect(
                        center=(lay.l // 2, int(lay.a * 0.30) + int(85 * lay.esc))
                    ),
                )

        elif estado_jogo == "pausado":
            # Mantém as notas visíveis exatamente onde estavam quando pausou.
            st_pausa = pausado_em - t0
            for n in notas:
                if n["estado"] == "acertou":
                    continue
                y = lay.alvo_y - (n["t"] - st_pausa) * lay.velocidade * velocidade_nota
                if y < lay.topo - lay.raio or y > lay.fim_y:
                    continue
                x = lay.lane_x[n["corda"]]
                errou = n["estado"] == "errou"
                cor = (110, 45, 45) if errou else CORES_CORDAS[n["corda"]]
                pygame.draw.circle(tela, cor, (x, int(y)), lay.raio)
                tx = fonte_g.render(
                    str(n["traste"]), True, (255, 255, 255) if errou else (0, 0, 0)
                )
                tela.blit(tx, tx.get_rect(center=(x, int(y))))
                nm = fonte_n.render(
                    NOMES_SOLFEJO[n["midi"] % 12], True, (230, 230, 230)
                )
                tela.blit(
                    nm, nm.get_rect(center=(x, int(y) + lay.raio + int(14 * lay.esc)))
                )
            msg = fonte_t.render("PAUSADO", True, (255, 220, 100))
            tela.blit(msg, msg.get_rect(center=(lay.l // 2, int(lay.a * 0.36))))
            sub = fonte_g.render(
                "P ou botão CONTINUAR para retomar", True, (230, 230, 230)
            )
            tela.blit(sub, sub.get_rect(center=(lay.l // 2, int(lay.a * 0.43))))

        elif estado_jogo == "fim":
            total = max(1, acertos + erros)
            linhas = [
                f"Pontos: {pontos}",
                f"Acertos: {acertos}/{total}  ({100 * acertos / total:.0f}%)",
                f"Melhor combo: {melhor_combo}",
                "ESPAÇO para jogar de novo",
            ]
            for i, l in enumerate(linhas):
                t = render_cabe(
                    fonte_t if i == 0 else fonte_g, l, (255, 255, 255), lay.l * 0.92
                )
                tela.blit(
                    t,
                    t.get_rect(
                        center=(lay.l // 2, int(lay.a * 0.22) + i * int(58 * lay.esc))
                    ),
                )

        # Feedback visual de acerto/erro (por cima das notas)
        efeitos = desenhar_efeitos(tela, camada, lay, fonte_g, efeitos, agora)

        # HUD
        m = int(14 * lay.esc)
        feitas = sum(1 for n in notas if n["estado"] != "pendente")
        hud = fonte.render(
            f"{RIFFS[riff_selecionado]['nome']}  {feitas}/{len(notas)}   Pontos {pontos}   Combo {combo}   "
            f"Latência {latencia * 1000:.0f} ms (Esq/Dir)  |  Velocidade {velocidade_nota:.1f}x",
            True,
            (220, 220, 220),
        )
        tela.blit(hud, (m, m))
        if detector.saida is None:
            som_txt = "Som: indisponível (sem saída de áudio)"
        elif detector.monitor:
            som_txt = (
                f"Som: LIGADO  vol {detector.volume:.1f} (Cima/Baixo)  "
                f'timbre {"OVERDRIVE" if detector.overdrive else "limpo"} (D)  '
                "[M desliga]"
            )
        else:
            som_txt = "Som: desligado  [M liga]"
        tela.blit(
            fonte.render(som_txt, True, (160, 200, 255)), (m, m + int(30 * lay.esc))
        )
        bw, bh = int(100 * lay.esc), int(10 * lay.esc)
        bx = lay.l - bw - m
        barra = int(min(1.0, nivel / 0.2) * bw)
        pygame.draw.rect(tela, (50, 50, 55), (bx, m, bw, bh))
        pygame.draw.rect(tela, (80, 200, 120), (bx, m, barra, bh))

        # Controles clicáveis
        desenhar_botao(tela, fonte, botoes["menu"], "RIFFS", menu_riffs_aberto)
        desenhar_botao(
            tela,
            fonte,
            botoes["pause"],
            "CONTINUAR" if estado_jogo == "pausado" else "PAUSAR",
            estado_jogo == "pausado",
        )
        desenhar_botao(tela, fonte, botoes["restart"], "REINICIAR")
        desenhar_botao(
            tela,
            fonte,
            botoes["metro"],
            "METRÔNOMO ON" if metronomo_ligado else "METRÔNOMO OFF",
            metronomo_ligado,
        )
        desenhar_botao(tela, fonte, botoes["menos"], "−")
        desenhar_botao(tela, fonte, botoes["mais"], "+")
        vel_txt = fonte.render(
            f"Velocidade {velocidade_nota:.1f}x  |  BPM {RIFFS[riff_selecionado]['bpm']}",
            True,
            (225, 225, 235),
        )
        tela.blit(
            vel_txt, (botoes["menos"].x, botoes["menos"].bottom + int(5 * escala_ui))
        )
        if not metronomo_disponivel:
            aviso_metro = fonte.render(
                "Metrônomo sem dispositivo de áudio", True, (240, 170, 100)
            )
            tela.blit(aviso_metro, (m, m + int(60 * lay.esc)))

        if menu_riffs_aberto:
            sombra = pygame.Surface((lay.l, lay.a), pygame.SRCALPHA)
            sombra.fill((0, 0, 0, 175))
            tela.blit(sombra, (0, 0))
            pygame.draw.rect(tela, (34, 36, 44), menu_rect, border_radius=14)
            pygame.draw.rect(
                tela, (155, 165, 185), menu_rect, width=2, border_radius=14
            )
            titulo_menu = fonte_g.render(
                "SELECIONAR RIFF / EXERCÍCIO", True, (250, 250, 255)
            )
            tela.blit(
                titulo_menu,
                titulo_menu.get_rect(
                    center=(menu_rect.centerx, menu_rect.y + int(36 * escala_ui))
                ),
            )
            for chave, rect in riff_botoes.items():
                desenhar_botao(
                    tela, fonte_g, rect, RIFFS[chave]["nome"], chave == riff_selecionado
                )
                desc = fonte.render(
                    f"{RIFFS[chave]['bpm']} BPM  |  {RIFFS[chave]['descricao']}",
                    True,
                    (200, 205, 215),
                )
                tela.blit(
                    desc,
                    desc.get_rect(
                        center=(rect.centerx, rect.bottom + int(12 * escala_ui))
                    ),
                )
            dica = fonte.render(
                "Clique em um item para carregar. Adicione novos riffs no dicionário RIFFS.",
                True,
                (200, 205, 215),
            )
            tela.blit(
                dica,
                dica.get_rect(
                    center=(menu_rect.centerx, menu_rect.bottom - int(22 * escala_ui))
                ),
            )

        desenhar_afinador(tela, lay, fonte, fonte_g, midi)

        pygame.display.flip()
        clock.tick(60)

    detector.parar()
    detector.join(timeout=1.0)
    stream.stop_stream()
    stream.close()
    if saida is not None:
        try:
            saida.stop_stream()
            saida.close()
        except Exception:  # noqa: BLE001
            pass
    p.terminate()
    pygame.mixer.quit()
    pygame.quit()


if __name__ == "__main__":
    main()
