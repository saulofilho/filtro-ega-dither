# Filtro EGA Dither

Transforma fotos no visual de telas de jogos de PC do fim dos anos 80: pixels altos (1:2),
paleta curta magenta/roxo/azul com destaques laranja/amarelo, e dither em xadrez entre pares de cores.

## Como funciona
1. Reduz a foto para ~320 colunas e metade das linhas (cada pixel vira 1×2).
2. Suaviza (moda + blur) para formar manchas "pintadas".
3. Gradient-map por luminância: tons frios viram preto→azul→roxo→magenta→rosa→branco;
   tons quentes (terra, rocha, pele) viram vinho→vermelho→laranja→amarelo.
4. Para cada pixel escolhe o par de cores da paleta + proporção (0/25/50/75/100%) que melhor
   aproxima a cor, e uma matriz Bayer 2×2 decide qual das duas cores aparece (o xadrez).
5. Amplia com vizinho mais próximo.

## Uso
- Navegador: abra `index.html`, arraste a foto, ajuste e baixe o PNG.
- Linha de comando (precisa de `pillow` e `numpy`; no macOS o comando é `python3`).
  Uma vez, crie um ambiente com as dependências:

```
python3 -m venv .venv
.venv/bin/pip install pillow numpy
```

  Depois, troque `foto.jpg` pelo caminho de uma foto sua:

```
.venv/bin/python ega_dither.py foto.jpg saida.png --cols 320 --warm 0.6
```

Opções: `--cols` (grão), `--scale`, `--grade` (0 = cores originais, 1 = paleta total),
`--warm`, `--contrast`, `--saturation`, `--spread` (evita misturar cores distantes), `--smooth`.

A paleta e as rampas ficam no topo de `ega_dither.py` e do `<script>` em `index.html`.
