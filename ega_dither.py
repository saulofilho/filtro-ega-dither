#!/usr/bin/env python3
"""Filtro EGA dither: pixels altos 1:2, paleta curta magenta/azul/amarelo,
dither em xadrez entre pares de cores (estilo telas de jogos de 1987-90).

uso: python ega_dither.py foto.jpg saida.png [--cols 320] [--scale 3] [--grade 0.85]
"""
import argparse, itertools
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter

def hexrgb(h): return [int(h[i:i+2], 16) for i in (1, 3, 5)]

PALETTE = np.array([hexrgb(h) for h in [
    "#000000",  # preto
    "#ffffff",  # branco
    "#2018f0",  # azul
    "#9a00b8",  # roxo
    "#ff10ff",  # magenta
    "#ffff48",  # amarelo
    "#ff8a30",  # laranja
    "#d82018",  # vermelho
    "#5a0a3a",  # vinho escuro
]], float)

# rampas de gradient-map (luminância -> cor), fria e quente
COOL = [(0.00, "#000000"), (0.18, "#2018f0"), (0.36, "#9a00b8"),
        (0.58, "#ff10ff"), (0.80, "#ffa0ff"), (0.95, "#ffffff")]
WARM = [(0.00, "#000000"), (0.20, "#5a0a3a"), (0.40, "#d82018"),
        (0.62, "#ff8a30"), (0.82, "#ffff48"), (0.97, "#ffffff")]

BAYER2 = np.array([[0, 2], [3, 1]]) / 4.0 + 0.125

def ramp(lum, stops):
    xs = [s for s, _ in stops]; cs = np.array([hexrgb(c) for _, c in stops], float)
    return np.stack([np.interp(lum, xs, cs[:, k]) for k in range(3)], -1)

def grade(rgb, amount, warm_bias):
    r, g, b = [rgb[..., k] / 255 for k in range(3)]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    sat = (mx - mn) / (mx + 1e-6)
    # "quentura": quanto o pixel puxa pra vermelho/amarelo/marrom (terra, rocha, pele)
    warm = np.clip(((r - b) * 2.2 + (g - b) * 0.6) * (0.4 + sat), 0, 1)
    warm = np.clip(warm * warm_bias, 0, 1)
    mapped = ramp(lum, COOL) * (1 - warm[..., None]) + ramp(lum, WARM) * warm[..., None]
    return rgb * (1 - amount) + mapped * amount

def build_mixes(pal, levels=(0, .25, .5, .75, 1.0)):
    pairs, mixes = [], []
    for i, j in itertools.combinations_with_replacement(range(len(pal)), 2):
        for r in levels:
            if i == j and r not in (0,): continue
            pairs.append((i, j, r)); mixes.append(pal[i] * (1 - r) + pal[j] * r)
    pairs = np.array(pairs); mixes = np.array(mixes)
    # penaliza misturar cores muito distantes (preto+branco vira ruído cinza)
    spread = np.linalg.norm(pal[pairs[:, 0].astype(int)] - pal[pairs[:, 1].astype(int)], axis=1)
    return pairs, mixes, spread

W = np.array([0.30, 0.59, 0.11]) ** 0.5  # peso perceptual simples

def dither(img, pal, spread_penalty=0.12):
    pairs, mixes, spread = build_mixes(pal)
    h, w, _ = img.shape
    flat = img.reshape(-1, 3)
    out_idx = np.empty(len(flat), int)
    ys, xs = np.divmod(np.arange(len(flat)), w)
    thr = BAYER2[ys % 2, xs % 2]
    for s in range(0, len(flat), 20000):
        f = flat[s:s + 20000]
        d = (((f[:, None, :] - mixes[None]) * W) ** 2).sum(-1) + (spread_penalty * spread[None]) ** 2 * 0.25
        best = pairs[d.argmin(1)]
        out_idx[s:s + 20000] = np.where(thr[s:s + 20000] < best[:, 2], best[:, 1], best[:, 0]).astype(int)
    return pal[out_idx].reshape(h, w, 3)

def run(src, dst, cols=320, scale=3, amount=0.85, warm_bias=0.6, contrast=1.25, saturation=1.3, spread=0.2, smooth=1):
    im = Image.open(src).convert("RGB")
    im = ImageEnhance.Contrast(im).enhance(contrast)
    im = ImageEnhance.Color(im).enhance(saturation)
    rows = max(1, round(im.height / im.width * cols / 2))  # pixel 1:2 => metade das linhas
    small = im.resize((cols, rows), Image.LANCZOS)
    for _ in range(smooth):  # achata texturas finas em manchas, como pintado à mão
        small = small.filter(ImageFilter.ModeFilter(3)).filter(ImageFilter.SMOOTH)
    small = np.asarray(small, float)
    graded = np.clip(grade(small, amount, warm_bias), 0, 255)
    out = dither(graded, PALETTE, spread).astype(np.uint8)
    Image.fromarray(out).resize((cols * scale, rows * scale * 2), Image.NEAREST).save(dst)
    print(f"salvo: {dst} ({cols * scale}x{rows * scale * 2})")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--cols", type=int, default=320, help="largura em pixels lógicos (menor = mais grosso)")
    ap.add_argument("--scale", type=int, default=3, help="ampliação final")
    ap.add_argument("--grade", type=float, default=0.85, help="0 = cores da foto, 1 = paleta total magenta")
    ap.add_argument("--warm", type=float, default=0.6, help="quanto terra/rocha vira laranja/amarelo")
    ap.add_argument("--contrast", type=float, default=1.25)
    ap.add_argument("--saturation", type=float, default=1.3)
    ap.add_argument("--spread", type=float, default=0.2, help="penalidade para misturar cores distantes")
    ap.add_argument("--smooth", type=int, default=1, help="passadas de suavização (0 = foto crua)")
    a = ap.parse_args()
    run(a.src, a.dst, a.cols, a.scale, a.grade, a.warm, a.contrast, a.saturation, a.spread, a.smooth)
