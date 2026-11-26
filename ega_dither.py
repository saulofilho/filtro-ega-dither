#!/usr/bin/env python3
"""Filtro EGA dither: transforma fotos em telas de PC do fim dos anos 80.

Paletas curtas, gradient-map frio/quente, dither ordenado ou por difusão,
pixels altos 1:2, contorno, scanlines e glitch horizontal.

uso: python3 ega_dither.py foto.jpg saida.png [--palette magenta] [--dither checker] ...
"""
import argparse, itertools
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter


def hexrgb(h): return [int(h[i:i + 2], 16) for i in (1, 3, 5)]


def ramp_stops(*pairs): return [(s, c) for s, c in pairs]


# Cada preset: paleta, rampa fria, rampa quente e "grade" sugerido.
PRESETS = {
    "magenta": dict(
        pal=["#000000", "#ffffff", "#2018f0", "#9a00b8", "#ff10ff", "#ffff48", "#ff8a30", "#d82018", "#5a0a3a"],
        cool=[(0, "#000000"), (.18, "#2018f0"), (.36, "#9a00b8"), (.58, "#ff10ff"), (.80, "#ffa0ff"), (.95, "#ffffff")],
        warm=[(0, "#000000"), (.20, "#5a0a3a"), (.40, "#d82018"), (.62, "#ff8a30"), (.82, "#ffff48"), (.97, "#ffffff")],
        grade=0.85),
    "cga": dict(  # CGA paleta 1, alta intensidade
        pal=["#000000", "#55ffff", "#ff55ff", "#ffffff"],
        cool=[(0, "#000000"), (.40, "#55ffff"), (.95, "#ffffff")],
        warm=[(0, "#000000"), (.45, "#ff55ff"), (.95, "#ffffff")],
        grade=0.9),
    "ega": dict(  # as 16 cores padrão
        pal=["#000000", "#0000aa", "#00aa00", "#00aaaa", "#aa0000", "#aa00aa", "#aa5500", "#aaaaaa",
             "#555555", "#5555ff", "#55ff55", "#55ffff", "#ff5555", "#ff55ff", "#ffff55", "#ffffff"],
        cool=[(0, "#000000"), (.25, "#0000aa"), (.50, "#5555ff"), (.75, "#55ffff"), (.95, "#ffffff")],
        warm=[(0, "#000000"), (.25, "#aa0000"), (.45, "#aa5500"), (.70, "#ffff55"), (.95, "#ffffff")],
        grade=0.3),
    "gameboy": dict(
        pal=["#0f380f", "#306230", "#8bac0f", "#c4d86a"],
        cool=[(0, "#0f380f"), (.35, "#306230"), (.70, "#8bac0f"), (1, "#c4d86a")],
        warm=[(0, "#0f380f"), (.35, "#306230"), (.70, "#8bac0f"), (1, "#c4d86a")],
        grade=1.0),
    "alpenglow": dict(  # azul saturado + luz rasante laranja/rosa, sombras nunca pretas
        pal=["#002732", "#044a87", "#027ae0", "#3595f6", "#6b8dee", "#af83e9", "#d37c92", "#e28868", "#e39e64", "#f4d3b0"],
        cool=[(0, "#002732"), (.22, "#044a87"), (.42, "#027ae0"), (.60, "#3595f6"), (.78, "#6b8dee"), (.95, "#af83e9")],
        warm=[(0, "#002732"), (.25, "#044a87"), (.50, "#d37c92"), (.70, "#e28868"), (.85, "#e39e64"), (1, "#f4d3b0")],
        grade=0.9),
    "gelo": dict(
        pal=["#05051a", "#102060", "#2060ff", "#60e0ff", "#c8b8ff", "#ffffff"],
        cool=[(0, "#05051a"), (.25, "#102060"), (.50, "#2060ff"), (.72, "#60e0ff"), (.95, "#ffffff")],
        warm=[(0, "#05051a"), (.30, "#102060"), (.60, "#c8b8ff"), (.95, "#ffffff")],
        grade=0.9),
}

ASPECTS = {"alto": (1, 2), "quadrado": (1, 1), "largo": (2, 1)}


HALFTONE4 = (np.array([[12, 5, 6, 13], [4, 0, 1, 7], [11, 3, 2, 8], [15, 10, 9, 14]]) + 0.5) / 16  # ponto aglomerado


def bayer(n):
    m = np.array([[0]])
    while m.shape[0] < n:
        m = np.block([[4 * m, 4 * m + 2], [4 * m + 3, 4 * m + 1]])
    return (m + 0.5) / m.size


W = np.array([0.30, 0.59, 0.11]) ** 0.5  # peso perceptual simples


def ramp(lum, stops):
    xs = [s for s, _ in stops]; cs = np.array([hexrgb(c) for _, c in stops], float)
    return np.stack([np.interp(lum, xs, cs[:, k]) for k in range(3)], -1)


def grade(rgb, preset, amount, warm_bias):
    r, g, b = [rgb[..., k] / 255 for k in range(3)]
    lum = 0.299 * r + 0.587 * g + 0.114 * b
    mx, mn = np.maximum(np.maximum(r, g), b), np.minimum(np.minimum(r, g), b)
    sat = (mx - mn) / (mx + 1e-6)
    # "quentura": quanto o pixel puxa pra vermelho/amarelo/marrom (terra, rocha, pele)
    warm = np.clip(((r - b) * 2.2 + (g - b) * 0.6) * (0.4 + sat) * warm_bias, 0, 1)[..., None]
    mapped = ramp(lum, preset["cool"]) * (1 - warm) + ramp(lum, preset["warm"]) * warm
    return rgb * (1 - amount) + mapped * amount


def dither_ordered(img, pal, n, spread_penalty, matrix=None):
    """Para cada pixel escolhe par de cores + proporção; a matriz Bayer decide qual aparece."""
    levels = np.arange(n * n + 1) / (n * n)
    pairs, mixes = [], []
    for i, j in itertools.combinations_with_replacement(range(len(pal)), 2):
        for r in (levels if i != j else [0.0]):
            pairs.append((i, j, r)); mixes.append(pal[i] * (1 - r) + pal[j] * r)
    pairs = np.array(pairs); mixes = np.array(mixes)
    spread = np.linalg.norm(pal[pairs[:, 0].astype(int)] - pal[pairs[:, 1].astype(int)], axis=1)
    pen = (spread_penalty * spread) ** 2 * 0.25
    h, w, _ = img.shape
    flat = img.reshape(-1, 3)
    ys, xs = np.divmod(np.arange(len(flat)), w)
    thr = (bayer(n) if matrix is None else matrix)[ys % n, xs % n]
    out = np.empty(len(flat), int)
    for s in range(0, len(flat), 8000):
        f = flat[s:s + 8000]
        d = (((f[:, None, :] - mixes[None]) * W) ** 2).sum(-1) + pen[None]
        best = pairs[d.argmin(1)]
        out[s:s + 8000] = np.where(thr[s:s + 8000] < best[:, 2], best[:, 1], best[:, 0]).astype(int)
    return out.reshape(h, w)


def nearest(c, pal): return int((((pal - c) * W) ** 2).sum(1).argmin())


ATKINSON = [((1, 0), 1 / 8), ((2, 0), 1 / 8), ((-1, 1), 1 / 8), ((0, 1), 1 / 8), ((1, 1), 1 / 8), ((0, 2), 1 / 8)]
FLOYD = [((1, 0), 7 / 16), ((-1, 1), 3 / 16), ((0, 1), 5 / 16), ((1, 1), 1 / 16)]


def dither_diffuse(img, pal, kernel):
    """Difusão de erro. Atkinson (Mac clássico) espalha só 3/4 do erro e mantém áreas chapadas;
    Floyd-Steinberg espalha tudo e dá um grão mais fino e orgânico."""
    a = img.copy(); h, w, _ = a.shape
    out = np.empty((h, w), int)
    for y in range(h):
        for x in range(w):
            i = nearest(a[y, x], pal); out[y, x] = i
            err = a[y, x] - pal[i]
            for (dx, dy), k in kernel:
                xx, yy = x + dx, y + dy
                if 0 <= xx < w and yy < h: a[yy, xx] += err * k
    return out


def dither_flat(img, pal):
    d = (((img[:, :, None, :] - pal[None, None]) * W) ** 2).sum(-1)
    return d.argmin(-1)


def outline_mask(small, strength):
    """Bordas fortes viram traço escuro, como o contorno pintado à mão nas telas da época."""
    lum = small @ np.array([0.299, 0.587, 0.114]) / 255
    gx = np.zeros_like(lum); gy = np.zeros_like(lum)
    gx[:, 1:-1] = lum[:, 2:] - lum[:, :-2]; gy[1:-1] = lum[2:] - lum[:-2]
    mag = np.hypot(gx, gy)
    return mag > (0.55 - 0.45 * strength)


def glitch(idx, amount, seed=7):
    """Linhas deslocadas e arrastadas na horizontal, como ruído de sinal."""
    rng = np.random.default_rng(seed); out = idx.copy(); h, w = idx.shape
    for y in range(h):
        if rng.random() < amount * 0.12:
            out[y] = np.roll(out[y], int(rng.integers(-8, 9) * amount))
        if rng.random() < amount * 0.08:
            x0 = int(rng.integers(0, w)); ln = int(rng.integers(4, max(5, int(w * 0.25 * amount) + 5)))
            out[y, x0:x0 + ln] = out[y, x0]
    return out


def run(src, dst, palette="magenta", dither="checker", aspect="alto", cols=320, scale=3, amount=None,
        warm_bias=0.6, contrast=1.25, saturation=1.3, spread=0.2, smooth=1,
        outline=0.0, scanlines=0.0, glitch_amt=0.0, chroma=0, vignette=0.0, grain=0.0):
    preset = PRESETS[palette]
    pal = np.array([hexrgb(h) for h in preset["pal"]], float)
    amount = preset["grade"] if amount is None else amount
    pxw, pxh = ASPECTS[aspect]

    im = Image.open(src).convert("RGB")
    im = ImageEnhance.Contrast(im).enhance(contrast)
    im = ImageEnhance.Color(im).enhance(saturation)
    rows = max(1, round(im.height / im.width * cols * pxw / pxh))
    small = im.resize((cols, rows), Image.LANCZOS)
    for _ in range(smooth):  # achata texturas finas em manchas, como pintado à mão
        small = small.filter(ImageFilter.ModeFilter(3)).filter(ImageFilter.SMOOTH)
    small = np.asarray(small, float)
    graded = np.clip(grade(small, preset, amount, warm_bias), 0, 255)

    if dither == "checker": idx = dither_ordered(graded, pal, 2, spread)
    elif dither == "bayer4": idx = dither_ordered(graded, pal, 4, spread)
    elif dither == "halftone": idx = dither_ordered(graded, pal, 4, spread, HALFTONE4)
    elif dither == "atkinson": idx = dither_diffuse(graded, pal, ATKINSON)
    elif dither == "floyd": idx = dither_diffuse(graded, pal, FLOYD)
    else: idx = dither_flat(graded, pal)

    if outline > 0:
        darkest = int((pal @ np.array([0.299, 0.587, 0.114])).argmin())
        idx[outline_mask(small, outline)] = darkest
    if glitch_amt > 0:
        idx = glitch(idx, glitch_amt)

    out = pal[idx]
    big = np.repeat(np.repeat(out, scale * pxh, 0), scale * pxw, 1)
    if scanlines > 0:  # escurece a parte de baixo de cada linha lógica
        cell = scale * pxh; dark = max(1, cell // 3)
        mask = (np.arange(big.shape[0]) % cell) >= cell - dark
        big[mask] *= 1 - 0.7 * scanlines
    if chroma:  # aberração cromática: vermelho e azul deslocados em sentidos opostos
        big[..., 0] = np.roll(big[..., 0], chroma, 1); big[..., 2] = np.roll(big[..., 2], -chroma, 1)
    if vignette > 0:
        yy, xx = np.mgrid[-1:1:big.shape[0] * 1j, -1:1:big.shape[1] * 1j]
        big *= np.clip(1 - vignette * 0.8 * (xx ** 2 + yy ** 2) ** 1.5 / 2.8, 0, 1)[..., None]
    if grain > 0:
        big += np.random.default_rng(3).normal(0, 40 * grain, big.shape[:2])[..., None]
    Image.fromarray(big.clip(0, 255).astype(np.uint8)).save(dst)
    print(f"salvo: {dst} ({big.shape[1]}x{big.shape[0]})")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("src"); ap.add_argument("dst")
    ap.add_argument("--palette", choices=PRESETS, default="magenta")
    ap.add_argument("--dither", choices=["checker", "bayer4", "halftone", "atkinson", "floyd", "flat"],
                    default="checker", help="checker = xadrez 2x2, bayer4 = trama 4x4, halftone = meio-tom de "
                    "jornal, atkinson/floyd = difusão de erro, flat = sem dither")
    ap.add_argument("--aspect", choices=ASPECTS, default="alto", help="formato do pixel: alto 1:2, quadrado, largo 2:1")
    ap.add_argument("--cols", type=int, default=320, help="largura em pixels lógicos (menor = mais grosso)")
    ap.add_argument("--scale", type=int, default=3, help="ampliação final")
    ap.add_argument("--grade", type=float, default=None, help="0 = cores da foto, 1 = paleta total (padrão: do preset)")
    ap.add_argument("--warm", type=float, default=0.6, help="quanto terra/rocha vai para a rampa quente")
    ap.add_argument("--contrast", type=float, default=1.25)
    ap.add_argument("--saturation", type=float, default=1.3)
    ap.add_argument("--spread", type=float, default=0.2, help="penalidade para misturar cores distantes")
    ap.add_argument("--smooth", type=int, default=1, help="passadas de suavização (0 = foto crua)")
    ap.add_argument("--outline", type=float, default=0.0, help="0-1: contorno escuro nas bordas")
    ap.add_argument("--scanlines", type=float, default=0.0, help="0-1: linhas de CRT")
    ap.add_argument("--glitch", type=float, default=0.0, help="0-1: linhas deslocadas e arrastadas")
    ap.add_argument("--chroma", type=int, default=0, help="px de aberração cromática (vermelho/azul separados)")
    ap.add_argument("--vignette", type=float, default=0.0, help="0-1: bordas escurecidas")
    ap.add_argument("--grain", type=float, default=0.0, help="0-1: grão de filme por cima")
    a = ap.parse_args()
    run(a.src, a.dst, a.palette, a.dither, a.aspect, a.cols, a.scale, a.grade, a.warm, a.contrast,
        a.saturation, a.spread, a.smooth, a.outline, a.scanlines, a.glitch,
        a.chroma, a.vignette, a.grain)
