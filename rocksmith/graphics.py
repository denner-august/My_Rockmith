"""Layout e desenho da interface do jogo."""

import pygame

from .config import (
    ACEITAR_OITAVA, ANTECEDENCIA, MIDI_CORDAS,
    NOMES_SOLFEJO, RIFFS, TOLERANCIA_CENTS,
)


# ----------------------------------------------------------------------------
# JOGO
# ----------------------------------------------------------------------------
VERDE = (60, 220, 110)
VERMELHO = (235, 60, 60)
DURACAO_EFEITO = 0.55  # segundos que o feedback de acerto/erro fica na tela
VISIVEL_S = 1.7  # pista mais espaçada: notas rápidas não se sobrepõem


class Layout:
    """Todas as posições e tamanhos derivados do tamanho da tela."""

    def __init__(self, largura, altura):
        self.l, self.a = largura, altura
        self.esc = min(
            largura / 800.0, altura / 520.0
        )  # fator de escala para fontes/traços
        # A faixa superior e a barra de ferramentas têm área própria.
        self.topo = int(altura * 0.31)
        self.alvo_y = int(altura * 0.74)
        self.fim_y = int(altura * 0.80)
        self.gap = min(altura * 0.17, largura * 0.8 / 6)  # distância entre as cordas
        x0 = largura / 2 - 2.5 * self.gap
        self.lane_x = [int(x0 + i * self.gap) for i in range(6)]
        self.raio = max(12, int(self.gap * 0.15))  # notas menores para riffs rápidos
        self.velocidade = (self.alvo_y - self.topo) / VISIVEL_S  # pixels por segundo
        self.nome_y = int(altura * 0.83)  # letras E A D G B e
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


def quebrar_linhas(fonte, texto, largura_max):
    """Quebra texto por palavras; palavras longas encolhem, nunca são cortadas."""
    linhas, linha = [], ""
    for palavra in texto.split():
        candidata = f"{linha} {palavra}".strip()
        if linha and fonte.size(candidata)[0] > largura_max:
            linhas.append(linha)
            linha = palavra
        else:
            linha = candidata
    if linha:
        linhas.append(linha)
    return linhas or [texto]


def nome_pt(midi_int):
    return f"{NOMES_SOLFEJO[midi_int % 12]}{midi_int // 12 - 1}"


def criar_notas(chave_riff, multiplicador_tempo=1.0):
    riff = RIFFS[chave_riff]
    passo = 60.0 / (riff["bpm"] * multiplicador_tempo)
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


def velocidade_minima_pistas(notas, raio):
    """Evita que duas notas da mesma corda ocupem a mesma área visual."""
    ultimo_tempo, menor_intervalo = {}, None
    for nota in sorted(notas, key=lambda item: item["t"]):
        corda = nota["corda"]
        if corda in ultimo_tempo:
            intervalo = nota["t"] - ultimo_tempo[corda]
            if intervalo > 0:
                menor_intervalo = (
                    intervalo if menor_intervalo is None else min(menor_intervalo, intervalo)
                )
        ultimo_tempo[corda] = nota["t"]
    if menor_intervalo is None:
        return 0.0
    return (2 * raio + 8) / menor_intervalo


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
    """Feedback limpo em área própria, sem cobrir as próximas notas."""
    camada.fill((0, 0, 0, 0))
    vivos = []
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
            (*cor, int(55 * k)),
            (x - larg // 2, lay.topo, larg, lay.fim_y - lay.topo),
        )
        # borda da tela
        pygame.draw.rect(
            camada,
            (*cor, int(140 * k)),
            (0, 0, lay.l, lay.a),
            max(6, int(12 * lay.esc)),
        )

        if acerto:  # anel discreto na linha de acerto
            r = int(lay.raio * (1.0 + 1.6 * prog))
            pygame.draw.circle(
                camada,
                (*cor, int(255 * k)),
                (x, lay.alvo_y),
                r,
                max(3, int(6 * lay.esc)),
            )

    tela.blit(camada, (0, 0))
    if vivos:
        # Só o evento mais recente é apresentado: sem fantasmas nem textos duplicados.
        ef = max(vivos, key=lambda item: item["t"])
        idade = agora - ef["t"]
        k = 1.0 - idade / DURACAO_EFEITO
        cor = VERDE if ef["tipo"] == "acerto" else VERMELHO
        surf = render_cabe(fonte_g, ef["texto"], cor, lay.l * 0.28)
        surf.set_alpha(int(255 * k))
        caixa = surf.get_rect()
        caixa.inflate_ip(int(26 * lay.esc), int(12 * lay.esc))
        caixa.center = (lay.l // 2, lay.topo - caixa.height // 2 - int(5 * lay.esc))
        fundo = pygame.Surface(caixa.size, pygame.SRCALPHA)
        pygame.draw.rect(fundo, (8, 12, 20, int(220 * k)), fundo.get_rect(), border_radius=max(6, int(8 * lay.esc)))
        pygame.draw.rect(fundo, (*cor, int(230 * k)), fundo.get_rect(), width=max(1, int(2 * lay.esc)), border_radius=max(6, int(8 * lay.esc)))
        tela.blit(fundo, caixa.topleft)
        tela.blit(surf, surf.get_rect(center=caixa.center))
    return vivos


def desenhar_painel(tela, rect, cor_fundo=(29, 32, 42), raio=14):
    """Desenha um painel escuro com profundidade, sem depender de imagens externas."""
    sombra = pygame.Surface((rect.width + 16, rect.height + 18), pygame.SRCALPHA)
    pygame.draw.rect(
        sombra, (0, 0, 0, 115), sombra.get_rect(), border_radius=raio + 5
    )
    tela.blit(sombra, (rect.x - 8, rect.y + 8))
    pygame.draw.rect(tela, cor_fundo, rect, border_radius=raio)
    pygame.draw.rect(tela, (105, 117, 142), rect, width=2, border_radius=raio)


def desenhar_botao(tela, fonte, rect, texto, ativo=False):
    """Botão com contraste de estado e realce discreto ao passar o mouse."""
    hover = rect.collidepoint(pygame.mouse.get_pos())
    if ativo:
        fundo, borda, texto_cor = (38, 119, 87), (106, 236, 162), (245, 255, 249)
    elif hover:
        fundo, borda, texto_cor = (73, 79, 98), (166, 180, 213), (255, 255, 255)
    else:
        fundo, borda, texto_cor = (48, 53, 67), (105, 115, 141), (235, 238, 246)

    pygame.draw.rect(tela, (16, 18, 25), rect.move(0, 3), border_radius=9)
    pygame.draw.rect(tela, fundo, rect, border_radius=9)
    pygame.draw.rect(tela, borda, rect, width=2, border_radius=9)
    surf = render_cabe(fonte, texto, texto_cor, rect.width - 16)
    tela.blit(surf, surf.get_rect(center=rect.center))
