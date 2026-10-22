"""Detecção de notas e integração com os dispositivos de áudio."""

import threading
from collections import deque

import numpy as np
import pyaudiowpatch as pyaudio
import pygame

from .config import (
    CHUNK, FMAX, FMIN, JANELA_ANALISE, LIMIAR_SILENCIO, MONITOR_LIGADO,
    NOTAS, OVERDRIVE_INICIAL, PORTA_RUIDO, RATE, VOLUME_INICIAL,
)
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

def criar_click(frequencia, duracao=0.045, volume=0.35):
    """Cria um clique curto para o metrônomo usando o mixer do Pygame."""
    taxa = 22050
    n = int(taxa * duracao)
    t = np.arange(n, dtype=np.float32) / taxa
    envelope = np.linspace(1.0, 0.0, n, dtype=np.float32)
    onda = np.sin(2 * np.pi * frequencia * t) * envelope * volume
    pcm = np.asarray(onda * 32767, dtype=np.int16)
    return pygame.mixer.Sound(buffer=pcm.tobytes())
