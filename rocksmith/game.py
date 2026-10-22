"""Inicialização e ciclo principal do Mini Rocksmith."""

import argparse
import sys
import time

import pyaudiowpatch as pyaudio
import pygame

from .audio import (
    DetectorPitch,
    achar_cabo,
    abrir_saida,
    abrir_stream,
    criar_click,
    listar_dispositivos,
)
from .config import (
    ANTECEDENCIA, CORES_CORDAS, JANELA_ACERTO, LATENCIA_S, LIMIAR_SILENCIO,
    MIDI_CORDAS, NOMES_CORDAS, NOMES_SOLFEJO, RIFFS, TAMANHO_PADRAO,
)
from .graphics import (
    Layout,
    criar_notas,
    desenhar_afinador,
    desenhar_botao,
    desenhar_efeitos,
    desenhar_painel,
    nome_pt,
    nota_confere,
    quebrar_linhas,
    render_cabe,
    velocidade_minima_pistas,
)
from .library import carregar_biblioteca_json


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

    musicas_carregadas = carregar_biblioteca_json()
    if musicas_carregadas:
        print(f"Biblioteca JSON: {len(musicas_carregadas)} música(s) carregada(s).")

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
    fonte_menu_titulo = pygame.font.SysFont(None, int(30 * lay.esc), bold=True)
    fonte_menu_card = pygame.font.SysFont(None, int(22 * lay.esc), bold=True)
    fonte_menu_info = pygame.font.SysFont(None, int(17 * lay.esc))
    fonte_hud = pygame.font.SysFont(None, int(18 * lay.esc), bold=True)
    fonte_hud_menor = pygame.font.SysFont(None, int(14 * lay.esc))
    fonte_nota = pygame.font.SysFont(None, int(22 * lay.esc), bold=True)
    fonte_tag_nota = pygame.font.SysFont(None, int(14 * lay.esc), bold=True)

    latencia = LATENCIA_S
    riff_selecionado = "riff_imagem"
    menu_riffs_aberto = False
    estado_jogo = "espera"  # espera | jogando | pausado | fim
    notas, t0 = [], 0.0
    pausado_em = None
    # Padrão preserva o andamento original. Lento e rápido são perfis ajustáveis.
    velocidades_perfil = {"lento": 0.75, "padrao": 1.0, "rapido": 1.25}
    perfil_velocidade = "padrao"
    velocidade_nota = velocidades_perfil[perfil_velocidade]
    metronomo_ligado = True
    ultimo_tique = -1
    pontos = combo = melhor_combo = acertos = erros = 0
    efeitos = []

    def iniciar():
        return criar_notas(riff_selecionado, velocidade_nota), time.perf_counter(), 0, 0, 0, 0, 0

    escala_ui = lay.esc
    bw, bh = int(120 * escala_ui), int(42 * escala_ui)
    espacamento = int(8 * escala_ui)
    by = int(55 * escala_ui)
    bx0 = lay.l - (bw * 4 + int(108 * escala_ui) + espacamento * 5) - int(16 * escala_ui)
    botoes = {
        "menu": pygame.Rect(bx0, by, bw, bh),
        "pause": pygame.Rect(bx0 + bw + espacamento, by, bw, bh),
        "restart": pygame.Rect(bx0 + 2 * (bw + espacamento), by, bw, bh),
        "metro": pygame.Rect(bx0 + 3 * (bw + espacamento), by, bw, bh),
        "menos": pygame.Rect(bx0 + 4 * (bw + espacamento), by, int(54 * escala_ui), bh),
        "mais": pygame.Rect(bx0 + 4 * (bw + espacamento) + int(58 * escala_ui), by, int(54 * escala_ui), bh),
    }
    toolbar_rect = pygame.Rect(
        max(int(12 * escala_ui), bx0 - int(14 * escala_ui)),
        by - int(9 * escala_ui),
        min(lay.l - int(24 * escala_ui), lay.l - bx0 + int(2 * escala_ui)),
        bh + int(31 * escala_ui),
    )
    perfil_h = int(17 * escala_ui)
    perfil_y = botoes["menu"].bottom + int(5 * escala_ui)
    perfil_w = int(72 * escala_ui)
    perfil_gap = int(5 * escala_ui)
    botoes_perfil = {
        "lento": pygame.Rect(botoes["menu"].x, perfil_y, perfil_w, perfil_h),
        "padrao": pygame.Rect(botoes["menu"].x + perfil_w + perfil_gap, perfil_y, perfil_w, perfil_h),
        "rapido": pygame.Rect(botoes["menu"].x + 2 * (perfil_w + perfil_gap), perfil_y, perfil_w, perfil_h),
    }
    menu_rect = pygame.Rect(int(lay.l * 0.30), int(lay.a * 0.22), int(lay.l * 0.40), int(lay.a * 0.56))
    riff_botoes = {}
    item_h = int(65 * escala_ui)
    riff_scroll = 0
    riff_foco = riff_selecionado
    item_passo = item_h + int(20 * escala_ui)
    # Reserva espaço real para o cabeçalho e o rodapé. A conta anterior era
    # conservadora demais e, em 1080p, mostrava só um riff por vez.
    inicio_lista = int(82 * escala_ui)
    altura_cartao = item_h + int(12 * escala_ui)
    espaco_rodape = int(34 * escala_ui)
    riff_visiveis = max(
        1,
        1 + max(
            0,
            (menu_rect.height - inicio_lista - int(6 * escala_ui) - espaco_rodape - altura_cartao)
            // item_passo,
        ),
    )

    def atualizar_botoes_riff():
        riff_botoes.clear()
        chaves = list(RIFFS.keys())
        inicio = max(0, min(riff_scroll, max(0, len(chaves) - riff_visiveis)))
        for posicao, chave in enumerate(chaves[inicio:inicio + riff_visiveis]):
            y = menu_rect.y + inicio_lista + posicao * item_passo
            riff_botoes[chave] = pygame.Rect(
                menu_rect.x + int(24 * escala_ui), y,
                menu_rect.width - int(48 * escala_ui), item_h
            )

    atualizar_botoes_riff()

    def reiniciar():
        nonlocal notas, t0, pontos, combo, melhor_combo, acertos, erros, efeitos, estado_jogo, pausado_em, ultimo_tique
        notas, t0, pontos, combo, melhor_combo, acertos, erros = iniciar()
        efeitos = []
        estado_jogo = "jogando"
        pausado_em = None
        ultimo_tique = -1

    def selecionar_perfil_velocidade(nome):
        """Aplica o perfil e reinicia somente uma partida que já esteja em curso."""
        nonlocal perfil_velocidade, velocidade_nota
        perfil_velocidade = nome
        velocidade_nota = velocidades_perfil[perfil_velocidade]
        if estado_jogo in ("jogando", "pausado"):
            reiniciar()

    def ajustar_perfil_velocidade(delta):
        nonlocal velocidade_nota
        if perfil_velocidade == "padrao":
            return
        velocidades_perfil[perfil_velocidade] = max(
            0.35, min(2.0, round(velocidades_perfil[perfil_velocidade] + delta, 2))
        )
        velocidade_nota = velocidades_perfil[perfil_velocidade]
        if estado_jogo in ("jogando", "pausado"):
            reiniciar()

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
                    # O cartão desenhado é um pouco mais alto que seu retângulo
                    # base; aceite cliques em toda a área que o jogador vê.
                    escolhido = next(
                        (
                            k
                            for k, rect in riff_botoes.items()
                            if rect.inflate(0, int(12 * escala_ui)).collidepoint(pos)
                        ),
                        None,
                    )
                    if escolhido is not None:
                        riff_selecionado = escolhido
                        riff_foco = escolhido
                        menu_riffs_aberto = False
                        reiniciar()
                    elif not menu_rect.collidepoint(pos):
                        menu_riffs_aberto = False
                        if estado_jogo == "pausado":
                            alternar_pause()
                elif botoes["menu"].collidepoint(pos):
                    menu_riffs_aberto = True
                    riff_foco = riff_selecionado
                    atualizar_botoes_riff()
                    if estado_jogo == "jogando":
                        alternar_pause()
                elif any(rect.collidepoint(pos) for rect in botoes_perfil.values()):
                    perfil_escolhido = next(
                        nome for nome, rect in botoes_perfil.items() if rect.collidepoint(pos)
                    )
                    selecionar_perfil_velocidade(perfil_escolhido)
                elif botoes["pause"].collidepoint(pos):
                    alternar_pause()
                elif botoes["restart"].collidepoint(pos):
                    reiniciar()
                elif botoes["metro"].collidepoint(pos):
                    metronomo_ligado = not metronomo_ligado
                elif botoes["menos"].collidepoint(pos):
                    ajustar_perfil_velocidade(-0.05)
                elif botoes["mais"].collidepoint(pos):
                    ajustar_perfil_velocidade(0.05)
            elif ev.type == pygame.KEYDOWN:
                if menu_riffs_aberto:
                    chaves_riff = list(RIFFS.keys())
                    indice_foco = (
                        chaves_riff.index(riff_foco)
                        if riff_foco in chaves_riff
                        else 0
                    )
                    if ev.key in (pygame.K_UP, pygame.K_LEFT):
                        indice_foco = max(0, indice_foco - 1)
                    elif ev.key in (pygame.K_DOWN, pygame.K_RIGHT):
                        indice_foco = min(len(chaves_riff) - 1, indice_foco + 1)
                    elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                        riff_selecionado = riff_foco
                        menu_riffs_aberto = False
                        reiniciar()
                        continue
                    elif ev.key == pygame.K_ESCAPE:
                        menu_riffs_aberto = False
                        if estado_jogo == "pausado":
                            alternar_pause()
                        continue
                    else:
                        # Nenhum atalho do jogo deve vazar para trás do modal.
                        continue

                    riff_foco = chaves_riff[indice_foco]
                    if indice_foco < riff_scroll:
                        riff_scroll = indice_foco
                    elif indice_foco >= riff_scroll + riff_visiveis:
                        riff_scroll = indice_foco - riff_visiveis + 1
                    atualizar_botoes_riff()
                    continue

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
                elif ev.key in (pygame.K_1, pygame.K_KP1):
                    selecionar_perfil_velocidade("lento")
                elif ev.key in (pygame.K_2, pygame.K_KP2):
                    selecionar_perfil_velocidade("padrao")
                elif ev.key in (pygame.K_3, pygame.K_KP3):
                    selecionar_perfil_velocidade("rapido")
                elif ev.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
                    ajustar_perfil_velocidade(-0.05)
                elif ev.key in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
                    ajustar_perfil_velocidade(0.05)
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
        velocidade_visual = max(
            lay.velocidade * velocidade_nota,
            velocidade_minima_pistas(notas, lay.raio),
        )
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
                bpm_atual = RIFFS[riff_selecionado]["bpm"] * velocidade_nota
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
                y = lay.alvo_y - (n["t"] - st) * velocidade_visual
                if y < lay.topo - lay.raio or y > lay.fim_y:
                    continue
                x = lay.lane_x[n["corda"]]
                errou = n["estado"] == "errou"
                cor = (110, 45, 45) if errou else CORES_CORDAS[n["corda"]]
                pygame.draw.circle(tela, cor, (x, int(y)), lay.raio)
                pygame.draw.circle(tela, (18, 20, 28), (x, int(y)), lay.raio, max(2, int(2 * lay.esc)))
                tx = fonte_nota.render(
                    str(n["traste"]), True, (255, 255, 255) if errou else (0, 0, 0)
                )
                tela.blit(tx, tx.get_rect(center=(x, int(y))))
                nm = fonte_tag_nota.render(NOMES_SOLFEJO[n["midi"] % 12], True, (238, 241, 250))
                tag = nm.get_rect()
                tag.inflate_ip(int(12 * lay.esc), int(6 * lay.esc))
                tag.center = (
                    x + (lay.raio + tag.width // 2 + int(7 * lay.esc)) * (1 if n["corda"] < 5 else -1),
                    int(y),
                )
                pygame.draw.rect(tela, (24, 28, 39), tag, border_radius=max(4, int(5 * lay.esc)))
                pygame.draw.rect(tela, cor, tag, width=1, border_radius=max(4, int(5 * lay.esc)))
                tela.blit(nm, nm.get_rect(center=tag.center))

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
                y = lay.alvo_y - (n["t"] - st_pausa) * velocidade_visual
                if y < lay.topo - lay.raio or y > lay.fim_y:
                    continue
                x = lay.lane_x[n["corda"]]
                errou = n["estado"] == "errou"
                cor = (110, 45, 45) if errou else CORES_CORDAS[n["corda"]]
                pygame.draw.circle(tela, cor, (x, int(y)), lay.raio)
                pygame.draw.circle(tela, (18, 20, 28), (x, int(y)), lay.raio, max(2, int(2 * lay.esc)))
                tx = fonte_nota.render(str(n["traste"]), True, (255, 255, 255) if errou else (0, 0, 0))
                tela.blit(tx, tx.get_rect(center=(x, int(y))))
                nm = fonte_tag_nota.render(NOMES_SOLFEJO[n["midi"] % 12], True, (238, 241, 250))
                tag = nm.get_rect()
                tag.inflate_ip(int(12 * lay.esc), int(6 * lay.esc))
                tag.center = (
                    x + (lay.raio + tag.width // 2 + int(7 * lay.esc)) * (1 if n["corda"] < 5 else -1),
                    int(y),
                )
                pygame.draw.rect(tela, (24, 28, 39), tag, border_radius=max(4, int(5 * lay.esc)))
                pygame.draw.rect(tela, cor, tag, width=1, border_radius=max(4, int(5 * lay.esc)))
                tela.blit(nm, nm.get_rect(center=tag.center))
            msg = fonte_t.render("PAUSADO", True, (255, 220, 100))
            tela.blit(msg, msg.get_rect(center=(lay.l // 2, int(lay.a * 0.36))))
            sub = fonte_g.render("P ou botão CONTINUAR para retomar", True, (230, 230, 230))
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

        # Feedback centralizado fora das pistas.
        efeitos = desenhar_efeitos(tela, camada, lay, fonte_hud, efeitos, agora)

        # HUD dividido: partida à esquerda, sistema/atalhos à direita.
        m = int(14 * lay.esc)
        feitas = sum(1 for n in notas if n["estado"] != "pendente")
        topo_h = int(39 * lay.esc)
        pygame.draw.rect(tela, (18, 22, 31), (m, m // 2, lay.l - 2 * m, topo_h), border_radius=int(8 * lay.esc))
        pygame.draw.rect(tela, (65, 78, 105), (m, m // 2, lay.l - 2 * m, topo_h), width=1, border_radius=int(8 * lay.esc))
        nome_riff = render_cabe(
            fonte_hud, RIFFS[riff_selecionado]["nome"], (245, 248, 255), lay.l * 0.42
        )
        tela.blit(nome_riff, nome_riff.get_rect(midleft=(m + int(12 * lay.esc), m + int(9 * lay.esc))))
        partida_txt = fonte_hud_menor.render(
            f"{feitas}/{len(notas)}  •  PONTOS {pontos}  •  COMBO {combo}", True, (163, 226, 190)
        )
        tela.blit(partida_txt, partida_txt.get_rect(midleft=(m + int(12 * lay.esc), m + int(25 * lay.esc))))

        if detector.saida is None:
            som_txt = "SOM INDISPONÍVEL"
        elif detector.monitor:
            som_txt = f"SOM LIGADO  •  VOL {detector.volume:.1f}  •  {'OVERDRIVE' if detector.overdrive else 'LIMPO'}"
        else:
            som_txt = "SOM DESLIGADO"
        bw, bh = int(100 * lay.esc), int(10 * lay.esc)
        bx = lay.l - bw - m - int(12 * lay.esc)
        direita_sistema = bx - int(14 * lay.esc)
        sistema_1 = render_cabe(
            fonte_hud_menor,
            f"LATÊNCIA {latencia * 1000:.0f} ms  •  {som_txt}",
            (174, 207, 255), lay.l * 0.39,
        )
        sistema_2 = render_cabe(
            fonte_hud_menor,
            "[M] som  [D] timbre  [↑↓] volume  [←→] latência",
            (139, 155, 181), lay.l * 0.39,
        )
        tela.blit(
            sistema_1, sistema_1.get_rect(midright=(direita_sistema, m + int(9 * lay.esc)))
        )
        tela.blit(sistema_2, sistema_2.get_rect(midright=(direita_sistema, m + int(25 * lay.esc))))
        barra = int(min(1.0, nivel / 0.2) * bw)
        pygame.draw.rect(tela, (50, 50, 55), (bx, m // 2 + int(3 * lay.esc), bw, bh))
        pygame.draw.rect(tela, (80, 200, 120), (bx, m // 2 + int(3 * lay.esc), barra, bh))

        # Barra de ferramentas própria: nunca ocupa a área das cordas.
        desenhar_painel(tela, toolbar_rect, (24, 29, 40), int(10 * escala_ui))
        desenhar_botao(tela, fonte, botoes["menu"], "RIFFS", menu_riffs_aberto)
        desenhar_botao(tela, fonte, botoes["pause"], "CONTINUAR" if estado_jogo == "pausado" else "PAUSAR", estado_jogo == "pausado")
        desenhar_botao(tela, fonte, botoes["restart"], "REINICIAR")
        desenhar_botao(tela, fonte, botoes["metro"], "METRÔNOMO ON" if metronomo_ligado else "METRÔNOMO OFF", metronomo_ligado)
        desenhar_botao(tela, fonte, botoes["menos"], "−")
        desenhar_botao(tela, fonte, botoes["mais"], "+")
        for nome, rect in botoes_perfil.items():
            rotulo = {"lento": "1 LENTO", "padrao": "2 PADRÃO", "rapido": "3 RÁPIDO"}[nome]
            desenhar_botao(tela, fonte_hud_menor, rect, rotulo, nome == perfil_velocidade)
        ajuste_txt = "− / + ajusta o perfil" if perfil_velocidade != "padrao" else "Padrão usa o andamento original"
        vel_txt = render_cabe(
            fonte_hud_menor,
            f"{perfil_velocidade.upper()}  {velocidade_nota:.2f}x  •  {ajuste_txt}",
            (225, 225, 235),
            lay.l - botoes["menos"].x - m,
        )
        tela.blit(vel_txt, (botoes["menos"].x, botoes["menos"].bottom + int(5 * escala_ui)))
        if not metronomo_disponivel:
            aviso_metro = fonte.render("Metrônomo sem dispositivo de áudio", True, (240, 170, 100))
            tela.blit(aviso_metro, (m, m + int(60 * lay.esc)))

        if menu_riffs_aberto:
            sombra = pygame.Surface((lay.l, lay.a), pygame.SRCALPHA)
            # Backdrop quase opaco: a interface do jogo não compete com o modal.
            sombra.fill((2, 4, 9, 248))
            tela.blit(sombra, (0, 0))
            desenhar_painel(tela, menu_rect, (27, 31, 43), int(16 * escala_ui))

            # Cabeçalho em duas linhas: título e contexto nunca disputam espaço.
            cabecalho_h = int(70 * escala_ui)
            cabecalho = pygame.Rect(menu_rect.x + 2, menu_rect.y + 2, menu_rect.width - 4, cabecalho_h)
            pygame.draw.rect(tela, (35, 57, 78), cabecalho, border_radius=int(14 * escala_ui))
            pygame.draw.rect(
                tela, (86, 207, 153),
                (menu_rect.x + int(22 * escala_ui), menu_rect.y + cabecalho_h - int(3 * escala_ui),
                 menu_rect.width - int(44 * escala_ui), int(3 * escala_ui)),
                border_radius=2,
            )
            titulo_menu = render_cabe(
                fonte_menu_titulo, "BIBLIOTECA DE RIFFS", (248, 252, 255), menu_rect.width - int(48 * escala_ui)
            )
            tela.blit(titulo_menu, titulo_menu.get_rect(
                midleft=(menu_rect.x + int(24 * escala_ui), menu_rect.y + int(22 * escala_ui))
            ))
            contador = fonte_menu_info.render(f"{len(RIFFS)} disponíveis", True, (161, 229, 198))
            largura_subtitulo = (
                menu_rect.width - int(48 * escala_ui) - contador.get_width() - int(20 * escala_ui)
            )
            subtitulo = render_cabe(
                fonte_menu_info,
                "Escolha um exercício para começar a tocar",
                (191, 205, 225),
                largura_subtitulo,
            )
            tela.blit(subtitulo, subtitulo.get_rect(
                midleft=(menu_rect.x + int(24 * escala_ui), menu_rect.y + int(49 * escala_ui))
            ))
            tela.blit(contador, contador.get_rect(
                midright=(menu_rect.right - int(24 * escala_ui), menu_rect.y + int(49 * escala_ui))
            ))

            for chave, rect in riff_botoes.items():
                selecionado = chave == riff_selecionado
                focado = chave == riff_foco
                hover = rect.collidepoint(pygame.mouse.get_pos()) or focado
                card = rect.inflate(0, int(12 * escala_ui))
                cor_card = (39, 78, 66) if selecionado else ((50, 56, 74) if hover else (38, 43, 57))
                cor_borda = (
                    (92, 227, 160)
                    if selecionado
                    else ((255, 204, 102) if focado else ((137, 153, 192) if hover else (72, 82, 108)))
                )
                pygame.draw.rect(tela, cor_card, card, border_radius=int(10 * escala_ui))
                pygame.draw.rect(tela, cor_borda, card, width=2, border_radius=int(10 * escala_ui))
                if selecionado:
                    pygame.draw.rect(
                        tela, (103, 238, 172),
                        (card.x, card.y + int(9 * escala_ui), int(5 * escala_ui), card.height - int(18 * escala_ui)),
                        border_radius=3,
                    )

                # Toda linha reserva à direita a mesma área para a tag de status.
                margem_x = int(22 * escala_ui)
                largura_tag = int(78 * escala_ui)
                largura_nome = card.width - margem_x * 2 - largura_tag
                linhas_nome = quebrar_linhas(fonte_menu_card, RIFFS[chave]["nome"], largura_nome)
                # Em títulos excepcionalmente longos, o texto inteiro se adapta
                # à largura de uma linha, em vez de invadir a descrição do card.
                if len(linhas_nome) > 2:
                    linhas_nome = [RIFFS[chave]["nome"]]
                y_titulo = card.y + int(16 * escala_ui)
                altura_linha = fonte_menu_card.get_linesize()
                for linha in linhas_nome:
                    titulo = render_cabe(fonte_menu_card, linha, (250, 252, 255), largura_nome)
                    tela.blit(titulo, titulo.get_rect(midleft=(card.x + margem_x, y_titulo)))
                    y_titulo += altura_linha

                desc = render_cabe(
                    fonte_menu_info,
                    f"{RIFFS[chave]['bpm']} BPM  •  {RIFFS[chave]['descricao']}",
                    (192, 205, 222), card.width - margem_x * 2,
                )
                tela.blit(desc, desc.get_rect(
                    midleft=(card.x + margem_x, card.bottom - int(18 * escala_ui))
                ))
                if selecionado:
                    selo = fonte_menu_info.render("EM USO", True, (13, 48, 34))
                    selo_rect = selo.get_rect()
                    selo_bg = pygame.Rect(
                        card.right - largura_tag - int(12 * escala_ui), card.y + int(13 * escala_ui),
                        largura_tag, selo_rect.height + int(10 * escala_ui),
                    )
                    pygame.draw.rect(tela, (118, 236, 175), selo_bg, border_radius=6)
                    tela.blit(selo, selo.get_rect(center=selo_bg.center))
            total_riffs = len(RIFFS)
            if total_riffs > riff_visiveis:
                dica_txt = f"Setas ↑/↓ para navegar  •  Enter para escolher  •  {riff_scroll + 1}-{min(total_riffs, riff_scroll + riff_visiveis)} de {total_riffs}"
            else:
                dica_txt = "Setas ↑/↓ para navegar  •  Enter para escolher  •  ESC para fechar"
            dica = render_cabe(fonte_menu_info, dica_txt, (181, 194, 214), menu_rect.width - int(32 * escala_ui))
            tela.blit(dica, dica.get_rect(center=(menu_rect.centerx, menu_rect.bottom - int(22 * escala_ui))))

        if not menu_riffs_aberto:
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
