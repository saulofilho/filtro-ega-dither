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
- Navegador: abra `index.html`, arraste a foto, ajuste e baixe o PNG. No iPhone, o botão **Salvar** abre a folha de compartilhar; escolha "Salvar Imagem" para ir ao rolo de fotos.
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

Opções:

| Opção | Valores | O que faz |
|---|---|---|
| `--palette` | `magenta` `cga` `ega` `gameboy` `alpenglow` `gelo` | conjunto de cores e rampas fria/quente |
| `--dither` | `checker` `bayer4` `halftone` `atkinson` `floyd` `flat` | xadrez 2×2, trama 4×4, meio-tom de jornal, difusão Atkinson, difusão Floyd–Steinberg, sem dither |
| `--aspect` | `alto` `quadrado` `largo` | formato do pixel (1:2, 1:1, 2:1) |
| `--cols` / `--scale` | inteiros | grão e ampliação final |
| `--grade` | 0–1 | 0 = cores da foto, 1 = só a paleta (padrão vem do preset) |
| `--warm` | 0–2 | quanto terra/rocha/pele vai para a rampa quente |
| `--contrast` `--saturation` | números | ajuste antes do filtro |
| `--spread` | 0–0.6 | evita misturar cores muito distantes |
| `--smooth` | 0–3 | passadas de suavização em manchas |
| `--outline` | 0–1 | contorno escuro nas bordas |
| `--glitch` | 0–1 | linhas deslocadas e arrastadas, como ruído de sinal |
| `--scanlines` | 0–1 | linhas de monitor CRT |
| `--chroma` | px | aberração cromática (vermelho e azul separados) |
| `--vignette` | 0–1 | bordas escurecidas |
| `--grain` | 0–1 | grão de filme |

Exemplo com tudo:

```
.venv/bin/python ega_dither.py foto.jpg saida.png --palette alpenglow --dither halftone \
  --outline 0.5 --glitch 0.4 --scanlines 0.5 --chroma 2 --vignette 0.6 --grain 0.2
```

Os presets (`PRESETS`) ficam no topo de `ega_dither.py` e do `<script>` em `index.html`; para criar uma paleta nova, adicione nos dois.
