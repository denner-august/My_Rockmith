# My_Rockmith

## Biblioteca de riffs

Coloque um arquivo `.json` para cada música em [`riffs/`](riffs/). Ao iniciar o
jogo, todos os arquivos válidos dessa pasta são carregados e aparecem no botão
**RIFFS**; use a roda do mouse no menu se a lista ficar maior que a tela.

Use [`riffs/exemplo_riff.json`](riffs/exemplo_riff.json) como modelo. Cada riff
precisa conter `id`, `nome`, `bpm`, `descricao` e uma lista de `eventos`.
Em cada evento, `corda` pode ser `E`, `A`, `D`, `G`, `B` ou `e`; `traste` é de
0 a 24; e `pulso` representa o tempo musical da nota.

## Organização do código

- `rocksmith/config.py`: parâmetros e riffs incluídos no jogo.
- `rocksmith/library.py`: validação e carregamento dos arquivos JSON.
- `rocksmith/audio.py`: captura de áudio e detecção de notas.
- `rocksmith/graphics.py`: layout e componentes visuais.
- `rocksmith/game.py`: inicialização e ciclo principal.
- `mini_rocksmith.py`: ponto de entrada do programa.

## Executar

Instale as dependências com `pip install numpy pyaudiowpatch pygame` e inicie o jogo:

```bash
python mini_rocksmith.py
```

Opções úteis: `--listar` mostra dispositivos de áudio, `--dispositivo N` escolhe a
entrada, `--saida N` escolhe a saída, `--sem-monitor` desliga o retorno de áudio,
`--janela` inicia em janela e `--tamanho 1920x1080` define as dimensões.

## Controles

- Espaço: começar ou jogar novamente; P: pausar; R: reiniciar.
- 1/2/3: selecionar velocidade lenta, padrão ou rápida; -/+: ajustar velocidade.
- T: metrônomo; M: monitor de áudio; D: alternar timbre limpo/overdrive.
- Setas ↑/↓: volume; ←/→: latência; F11: tela cheia/janela; Esc: sair.
