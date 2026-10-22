# My_Rockmith

## Biblioteca de riffs

Coloque um arquivo `.json` para cada música em [`riffs/`](riffs/). Ao iniciar o
jogo, todos os arquivos válidos dessa pasta são carregados e aparecem no botão
**RIFFS**; use as setas no menu se a lista ficar maior que a tela.

Use [`riffs/exemplo_riff.json`](riffs/exemplo_riff.json) como modelo. Cada riff
precisa conter `id`, `nome`, `bpm`, `descricao` e uma lista de `eventos`.
Em cada evento, `corda` pode ser `E`, `A`, `D`, `G`, `B` ou `e`; `traste` é de
0 a 24; e `pulso` representa o tempo musical da nota.

## Projeto Godot

O código GDScript está em `scripts/` e o projeto pode ser aberto diretamente pelo
Godot 4 usando `project.godot`.

- `scripts/game_config.gd`: parâmetros, repertório padrão, notas e validação de pitch.
- `scripts/riff_library.gd`: carregamento e validação dos riffs JSON.
- `scripts/mic_pitch.gd`: captura do microfone, detecção de notas e retorno de áudio.
- `scripts/game.gd`: interface, controles, metrônomo, pontuação e ciclo do jogo.
- `scenes/main.tscn`: cena principal e ponto de entrada.

Os arquivos JSON em `riffs/` continuam sendo carregados automaticamente. Para que a
detecção da guitarra funcione, habilite a entrada de áudio nas configurações do
projeto Godot e selecione o cabo Rocksmith como microfone padrão do sistema. O
monitoramento e o metrônomo usam a saída padrão do sistema.

Os arquivos Python originais foram mantidos como referência durante a migração.

## Controles

- Espaço: começar ou jogar novamente; P: pausar; R: reiniciar; Esc: sair/fechar menu.
- 1/2/3: selecionar velocidade lenta, padrão ou rápida; -/+: ajustar velocidade.
- T: metrônomo; M: monitor de áudio; D: alternar timbre limpo/overdrive.
- Setas ↑/↓: volume ou navegar no menu de riffs; ←/→: latência ou navegar no menu.
- F11: tela cheia/janela.
