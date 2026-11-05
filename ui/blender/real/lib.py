# Shared library for the realistic city's models (see docs/models.md): the
# tiling PBR textures every model draws from, the geometry helpers, and the
# piece / bake / export pipeline. Each model is a module next to this one
# (a1_apartment.py, c1_farmhouse.py, ...); build.py runs them.
#
# Conventions, relied on by ui/src/city/real.ts:
# - Blender z up, the front faces -y (glTF +z after export); metres.
# - Materials are named by role ("brick", "frame", "glass", ...); the app
#   picks the real material per role and building.
# - UV0 is in metres for tiling textures; textures repeat at 1 / tile size.
#   Window glass instead carries (window id + u, v) across its opening, for
#   the interior shader; ids restart at 1 in each piece and stay below 256,
#   so the app can shift them per storey and building.
# - UV1 ("Light") holds one lightmap atlas per model with baked AO.
# - Pieces: a model is built as a reference stack (ground storey, storeys,
#   roof, ...) so the bake sees its neighbours, then split into one glTF node
#   per piece, moved so its base is at the origin. Alpha-tested geometry
#   (railing bars, grates) goes in a "<piece>_cut" node, not baked; decals
#   (paint on a wall) in "<piece>_decal", made after the bake so they do not
#   shade the wall they lie on.
import math
import os
import random

import bmesh
import bpy
import numpy as np
from mathutils import Vector

Z = Vector((0, 0, 1))

# ---- textures ------------------------------------------------------------------


def lattice(n, px, py, rng):
    """Seamless value noise: px x py lattice cells over an n x n image."""
    g = rng.random((py, px))

    def axis(p):
        x = np.arange(n) * p / n
        i0 = np.floor(x).astype(int)
        f = x - i0
        return i0, (i0 + 1) % p, f * f * (3 - 2 * f)

    y0, y1, fy = axis(py)
    x0, x1, fx = axis(px)
    fy, fx = fy[:, None], fx[None, :]
    a, b = g[np.ix_(y0, x0)], g[np.ix_(y0, x1)]
    c, d = g[np.ix_(y1, x0)], g[np.ix_(y1, x1)]
    return (a * (1 - fx) + b * fx) * (1 - fy) + (c * (1 - fx) + d * fx) * fy


def fbm(n, base, octaves, seed, gain=0.5, stretch=(1, 1)):
    rng = np.random.default_rng(seed)
    s, amp, tot, p = 0.0, 1.0, 0.0, base
    for _ in range(octaves):
        if p * max(stretch) > n:
            break
        s = s + amp * lattice(n, p * stretch[0], p * stretch[1], rng)
        tot += amp
        amp *= gain
        p *= 2
    return s / tot


def normals(h, strength):
    """Tangent-space normal map (OpenGL, green up) from a height field; row 0 is the top."""
    dx = (np.roll(h, -1, 1) - np.roll(h, 1, 1)) * 0.5 * strength
    dy = (np.roll(h, 1, 0) - np.roll(h, -1, 0)) * 0.5 * strength
    n = np.dstack([-dx, -dy, np.ones_like(h)])
    n /= np.linalg.norm(n, axis=2, keepdims=True)
    return n * 0.5 + 0.5


class Tex:
    """Writes images into one directory; data is (h, w) or (h, w, 3) in 0..1, row 0 at the top."""

    def __init__(self, out):
        self.out = out
        os.makedirs(out, exist_ok=True)

    def save(self, name, data, alpha=None):
        if data.ndim == 2:
            data = np.dstack([data] * 3)
        h, w = data.shape[:2]
        rgba = np.ones((h, w, 4), np.float32)
        rgba[..., :3] = np.clip(data, 0, 1)
        if alpha is not None:
            rgba[..., 3] = np.clip(alpha, 0, 1)
        img = bpy.data.images.new(name, w, h, alpha=alpha is not None)
        img.pixels.foreach_set(np.flipud(rgba).ravel())
        img.filepath_raw = os.path.join(self.out, f"{name}.png")
        img.file_format = "PNG"
        img.save()
        bpy.data.images.remove(img)


def srgb(*c):
    return np.array(c, np.float32) / 255.0


def brick_tex(t, n=1024):
    """Running bond, 8 bricks x 24 courses: tile 1.72 x 1.8 m."""
    cols, rows = 8, 24
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    cy = y / (n / rows)
    course = np.floor(cy).astype(int)
    fy = cy - course
    bx = x / (n / cols) + 0.5 * (course % 2)
    brick = np.floor(bx).astype(int) % cols
    fx = bx - np.floor(bx)
    # Distance to the brick's edge in metres (bricks 0.215 x 0.075 with joints).
    edge = np.minimum(np.minimum(fx, 1 - fx) * 0.215, np.minimum(fy, 1 - fy) * 0.075)
    mortar = edge < 0.0055
    rng = np.random.default_rng(3)
    ids = course * cols + brick
    tone = rng.random(rows * cols)[ids]
    hue = rng.random(rows * cols)[ids]
    burnt = rng.random(rows * cols)[ids] < 0.1
    base = np.stack([srgb(150, 68, 48), srgb(128, 58, 42), srgb(166, 88, 62), srgb(112, 54, 44)])
    k = (hue * 3.999).astype(int)
    f = (hue * 3.999 - k)[..., None]
    col = base[k] * (1 - f) + base[np.minimum(k + 1, 3)] * f
    col *= (0.82 + 0.3 * tone)[..., None]
    col[burnt] *= 0.55
    fine = fbm(n, 64, 4, 11)
    blotch = fbm(n, 8, 4, 12)
    col *= (0.85 + 0.3 * fine)[..., None] * (0.9 + 0.2 * blotch)[..., None]
    mcol = srgb(168, 160, 148) * (0.8 + 0.35 * fbm(n, 128, 3, 13))[..., None]
    col[mortar] = mcol[mortar]
    # Height: bricks with worn, rounded arrises; mortar recessed.
    h = np.clip((edge - 0.004) / 0.006, 0, 1) ** 0.5
    h = h * (0.85 + 0.15 * fbm(n, 64, 4, 14)) + 0.08 * fbm(n, 256, 2, 15)
    rough = np.where(mortar, 0.95, 0.78 + 0.15 * fine)
    t.save("brick_col", col)
    t.save("brick_nrm", normals(h, 6.0))
    t.save("brick_rgh", rough)


def stone_tex(t, n=1024):
    """Limestone, smooth with pitting and soft staining: tile 2 x 2 m."""
    a = fbm(n, 4, 6, 21)
    b = fbm(n, 32, 5, 22)
    pits = (fbm(n, 256, 2, 23) > 0.72).astype(np.float32)
    col = srgb(178, 168, 148) * (0.8 + 0.2 * a)[..., None] * (0.93 + 0.1 * b)[..., None]
    col *= (1 - 0.18 * pits)[..., None]
    h = 0.4 * b + 0.2 * fbm(n, 128, 3, 24) - 0.5 * pits
    t.save("stone_col", col)
    t.save("stone_nrm", normals(h, 2.5))


def ashlar_tex(t, n=1024):
    """Rusticated limestone blocks with V joints: 2 x 4 blocks, tile 2.4 x 1.8 m."""
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    cy = y / (n / 4)
    course = np.floor(cy).astype(int)
    fy = cy - course
    bx = x / (n / 2) + 0.5 * (course % 2)
    fx = bx - np.floor(bx)
    block = (np.floor(bx).astype(int) % 2) + course * 2
    ex = np.minimum(fx, 1 - fx) * 1.2
    ey = np.minimum(fy, 1 - fy) * 0.45
    h = np.clip(np.minimum(ex * 0.6, ey) / 0.03, 0, 1)
    rng = np.random.default_rng(31)
    tone = rng.random(8)[block]
    a = fbm(n, 8, 6, 32)
    col = srgb(172, 162, 142) * (0.88 + 0.12 * tone + 0.1 * (a - 0.5))[..., None]
    col *= (0.75 + 0.25 * h)[..., None]
    h = h + 0.15 * fbm(n, 64, 4, 33)
    t.save("ashlar_col", col)
    t.save("ashlar_nrm", normals(h, 3.0))


def granite_tex(t, n=512):
    """Speckled dark granite: tile 1 m."""
    s = fbm(n, 128, 2, 41)
    m = fbm(n, 16, 4, 42)
    col = srgb(92, 90, 88) * (0.75 + 0.35 * m)[..., None]
    col[s > 0.62] = srgb(170, 166, 160)
    col[s < 0.32] = srgb(40, 38, 38)
    t.save("granite_col", col)


def roof_tex(t, n=1024):
    """Torch-on bitumen in 1 m strips with lapped seams: tile 4 m."""
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    fx = (x / (n / 4)) % 1
    seam = np.exp(-((fx - 0.03) / 0.008) ** 2)
    grit = fbm(n, 256, 2, 51)
    stain = fbm(n, 4, 5, 52)
    col = srgb(78, 78, 80) * (0.75 + 0.2 * grit + 0.25 * stain)[..., None]
    col *= (1 - 0.25 * seam)[..., None]
    h = 0.3 * grit + 0.8 * seam
    t.save("roof_col", col)
    t.save("roof_nrm", normals(h, 3.0))


def wood_tex(t, n=512):
    """Weathered cedar staves 0.15 m wide: tile 1.2 m."""
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    fx = (x / (n / 8)) % 1
    stave = np.floor(x / (n / 8)).astype(int)
    rng = np.random.default_rng(61)
    tone = rng.random(8)[stave]
    grain = fbm(n, 16, 5, 62, stretch=(4, 1))
    col = srgb(120, 98, 76) * (0.7 + 0.25 * tone + 0.3 * grain)[..., None]
    gap = np.minimum(fx, 1 - fx) < 0.03
    col[gap] *= 0.35
    h = np.where(gap, 0.0, 1.0) + 0.2 * grain
    t.save("wood_col", col)
    t.save("wood_nrm", normals(h, 2.0))


def siding_tex(t, n=1024):
    """Painted clapboard, 0.15 m exposure, boards butted at random: tile 2.4 x 1.2 m.

    Near-white so the app tints it per house; each board is darker in the
    shadow under the lap above, with brush marks and a little wear.
    """
    rows = 8
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    cy = y / (n / rows)
    row = np.floor(cy).astype(int)
    fy = cy - row  # 0 at the top of the board's exposure (under the lap), 1 at its butt edge
    rng = np.random.default_rng(101)
    # Butt joints: each course has 1-2 joints at random places along the 2.4 m tile.
    joint = np.zeros((n, n), bool)
    for r_ in range(rows):
        for u in rng.random(1 + int(rng.random() < 0.5)):
            joint[row == r_] |= np.abs(x[row == r_] / n - u) < 0.0018
    grain = fbm(n, 24, 5, 102, stretch=(6, 1))
    wear = fbm(n, 8, 5, 103)
    col = np.ones((n, n, 3), np.float32) * srgb(236, 234, 228)
    col *= (0.94 + 0.06 * grain)[..., None] * (0.95 + 0.05 * wear)[..., None]
    lap = np.clip((fy - 0.0) / 0.12, 0, 1) ** 0.6  # soft shadow just under the board above
    col *= (0.72 + 0.28 * lap)[..., None]
    col[joint] *= 0.7
    # Height: each board's face tapers from thin under the lap to thick at the butt.
    h = fy * 0.9 + 0.04 * grain
    h[joint] -= 0.3
    rough = 0.55 + 0.25 * wear
    t.save("siding_col", col)
    t.save("siding_nrm", normals(h, 4.0))
    t.save("siding_rgh", rough)


def shingle_tex(t, n=1024):
    """Three-tab asphalt shingles, 0.14 m exposure, tabs 0.33 m: tile 2 x 1.12 m.

    Mid grey for tinting, with granules, per-tab tone and the dark slots
    between tabs; row 0 (the image's top) is up the slope.
    """
    rows = 8
    W = 2.0
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    cy = y / (n / rows)
    row = np.floor(cy).astype(int)
    fy = cy - row
    xm = x / n * W + (row % 2) * 0.165 + (row % 3) * 0.06
    tab = np.floor(xm / 0.333).astype(int)
    fx = xm / 0.333 - tab
    slot = (np.minimum(fx, 1 - fx) * 0.333 < 0.006) & (fy > 0.35)
    rng = np.random.default_rng(111)
    ids = (row * 97 + tab) % 4096
    tone = rng.random(4096)[ids]
    grit = fbm(n, 256, 2, 112)
    speck = fbm(n, 512, 1, 113)
    col = np.ones((n, n, 3), np.float32) * srgb(150, 150, 150)
    col *= (0.78 + 0.3 * tone)[..., None] * (0.8 + 0.35 * grit)[..., None]
    col[speck > 0.7] *= 1.25
    col[speck < 0.25] *= 0.7
    butt = fy > 0.94  # the shadow line under each course's lower edge
    col[butt] *= 0.45
    col[slot] *= 0.3
    h = 0.6 + 0.4 * fy + 0.1 * grit
    h[butt] = 0.0
    h[slot] = 0.2
    t.save("shingle_col", col)
    t.save("shingle_nrm", normals(h, 5.0))


def louvre_tex(t, n=512):
    """Louvred shutter slats every 0.05 m inside a stile frame: tile 0.5 x 1.5 m (one shutter)."""
    w, hh = n // 2, n * 3 // 2
    y, x = np.mgrid[0:hh, 0:w].astype(np.float32)
    u, v = x / w * 0.5, y / hh * 1.5
    stile = (u < 0.06) | (u > 0.44) | (v < 0.07) | (v > 1.43) | (np.abs(v - 0.75) < 0.035)
    fy = (v / 0.05) % 1
    col = np.ones((hh, w, 3), np.float32) * srgb(225, 225, 225)
    col *= (0.7 + 0.3 * fy)[..., None]
    col[stile] = srgb(235, 235, 235)
    col *= (0.93 + 0.07 * np.tile(fbm(w, 16, 3, 121), (3, 1)))[..., None]
    h = np.where(stile, 1.0, 0.25 + 0.5 * fy)
    t.save("louvre_col", col)
    t.save("louvre_nrm", normals(h, 3.0))


def bars_tex(t):
    """Wrought-iron railing: square bars every 0.12 m with collars; tile 1.2 x 1 m."""
    w, hh = 1024, 256
    y, x = np.mgrid[0:hh, 0:w].astype(np.float32)
    u = (x / w * 10) % 1
    v = y / hh
    bar = np.abs(u - 0.5) < 0.07
    collar = bar & (np.abs(v - 0.5) < 0.03) & (np.abs(u - 0.5) < 0.12)
    spear = (np.abs(u - 0.5) < 0.12) & (v < 0.06)
    a = (bar | collar | spear).astype(np.float32)
    col = np.zeros((hh, w, 3), np.float32) + srgb(30, 30, 32)
    t.save("bars", col, a)


def grate_tex(t):
    """Fire escape slats: 0.04 m bars, 0.025 m gaps; tile 1 m."""
    n = 512
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    v = (y / n * 15) % 1
    u = (x / n * 4) % 1
    a = ((v < 0.62) | (np.abs(u - 0.5) < 0.02)).astype(np.float32)
    col = np.zeros((n, n, 3), np.float32) + srgb(34, 34, 36)
    t.save("grate", col, a)


def awning_tex(t):
    """Canvas stripes, 0.25 m: tile 1 m."""
    n = 512
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    s = np.floor(x / (n / 4)).astype(int) % 2
    weave = fbm(n, 128, 2, 71)
    col = np.where(s[..., None] == 0, srgb(38, 92, 64), srgb(232, 226, 208))
    col *= (0.9 + 0.12 * weave)[..., None]
    t.save("awning_col", col)


def render_tex(t, n=1024):
    """Smooth painted render: fine sand grain, soft trowel waves and patches; tile 3 m.

    Near-white so the app tints it per building.
    """
    grain = fbm(n, 384, 2, 131)
    trowel = fbm(n, 12, 4, 132, stretch=(3, 1))
    patch = fbm(n, 3, 4, 133)
    col = np.ones((n, n, 3), np.float32) * srgb(240, 238, 232)
    col *= ((0.95 + 0.06 * grain) * (0.97 + 0.04 * trowel) * (0.95 + 0.06 * patch))[..., None]
    t.save("render_col", col)
    t.save("render_nrm", normals(0.5 * grain + 0.4 * trowel, 1.2))


def rustic_tex(t, n=1024):
    """Banded rustication in render: smooth courses 0.4 m tall between V-joints,
    no vertical joints (the French and Viennese way); tile 3 x 1.2 m.

    Near-white like the render, so the app tints it with the building's
    stucco; the joints hold dirt and the lower edge of each band is worn.
    """
    rows = 3
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    cy = y / (n / rows)
    fy = cy - np.floor(cy)  # 0 at a band's top, 1 at its foot
    # Distance to the nearest joint in metres; the V is 0.025 deep, 0.03 wide each side.
    d = np.minimum(fy, 1 - fy) * 0.4
    v = np.clip(d / 0.03, 0, 1)
    grain = fbm(n, 384, 2, 141)
    trowel = fbm(n, 10, 4, 142, stretch=(4, 1))
    patch = fbm(n, 3, 4, 143)
    col = np.ones((n, n, 3), np.float32) * srgb(236, 232, 222)
    col *= ((0.95 + 0.06 * grain) * (0.97 + 0.04 * trowel) * (0.94 + 0.07 * patch))[..., None]
    # Dirt in the joints, and a soft shadow under each band's arris.
    col *= (0.55 + 0.45 * v ** 0.7)[..., None]
    col *= (1 - 0.08 * np.clip(1 - (fy - 0.0) / 0.12, 0, 1) * (fy < 0.5))[..., None]
    h = np.sqrt(v) + 0.3 * grain * 0.1 + 0.25 * trowel * 0.2
    t.save("rustic_col", col)
    t.save("rustic_nrm", normals(h, 5.0))


def battens_tex(t, n=1024):
    """Vertical timber battens, 45 mm with 20 mm shadow gaps: tile 1.3 m.

    Pale, low-saturation wood so the app's tint gives natural larch, cedar,
    silver-weathered or charred cladding.
    """
    k = 20
    y, x = np.mgrid[0:n, 0:n]
    fx = (x / (n / k)) % 1
    b = x * k // n
    rng = np.random.default_rng(141)
    tone, off = rng.random(k)[b], rng.random(k)[b]
    grain = fbm(n, 6, 5, 142, stretch=(8, 1))
    grain = grain[(y + (off * n).astype(int)) % n, x]  # each batten cut from elsewhere in the log
    knots = fbm(n, 24, 3, 143) > 0.78
    col = np.ones((n, n, 3), np.float32) * srgb(214, 198, 176)
    col *= (0.82 + 0.22 * tone + 0.3 * (grain - 0.5))[..., None]
    col[knots] *= 0.8
    edge = np.minimum(fx, 0.69 - fx) * (n / k)  # px from the batten's edge; the gap is fx > 0.69
    gap = fx > 0.69
    col *= np.clip(0.55 + edge / 6, 0.55, 1.0)[..., None]
    col[gap] = srgb(40, 34, 30)
    h = np.where(gap, 0.0, np.clip(edge / 4, 0, 1) ** 0.5) + 0.06 * grain
    t.save("battens_col", col)
    t.save("battens_nrm", normals(h, 4.0))


def gravel_tex(t, n=1024):
    """Rounded roof ballast, ~2.5 cm pebbles in greys and buffs: tile 1.5 m."""
    c = 64
    rng = np.random.default_rng(151)
    pts = rng.random((c, c, 2))
    y, x = np.mgrid[0:n, 0:n].astype(np.float32) / (n / c)
    iy, ix = y.astype(int), x.astype(int)
    best = np.full((n, n), 9.0, np.float32)
    bid = np.zeros((n, n), int)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            cy, cx = (iy + dy) % c, (ix + dx) % c
            p = pts[cy, cx]
            d = (x - (ix + dx + p[..., 0])) ** 2 + (y - (iy + dy + p[..., 1])) ** 2
            near = d < best
            best[near] = d[near]
            bid[near] = (cy * c + cx)[near]
    dome = np.clip(1 - np.sqrt(best) / 0.75, 0, 1) ** 0.6
    pal = np.stack([srgb(150, 146, 138), srgb(118, 114, 108), srgb(176, 168, 152), srgb(96, 94, 92), srgb(160, 150, 128)])
    col = pal[(rng.random(c * c) * 4.999).astype(int)][bid] * (0.85 + 0.3 * rng.random(c * c)[bid])[..., None]
    col *= (0.35 + 0.65 * dome)[..., None]
    t.save("gravel_col", col)
    t.save("gravel_nrm", normals(dome, 5.0))


def sedum_tex(t, n=1024):
    """A sedum green roof: mats of green, olive and red succulents with yellow flowers; tile 1.2 m."""
    a = fbm(n, 24, 5, 161)
    b = fbm(n, 5, 4, 162)
    s = fbm(n, 256, 2, 163)
    col = np.ones((n, n, 3), np.float32) * srgb(86, 118, 56)
    col = np.where((a < 0.42)[..., None], srgb(128, 126, 66), col)
    red = (np.clip((b - 0.52) / 0.2, 0, 1) * np.clip((a - 0.3) / 0.4, 0, 1) * 0.65)[..., None]
    col = col * (1 - red) + srgb(146, 74, 58) * red
    col *= (0.65 + 0.5 * s)[..., None] * (0.85 + 0.3 * a)[..., None]
    col[(s > 0.78) & (b < 0.45)] = srgb(222, 196, 70)
    t.save("sedum_col", col)
    t.save("sedum_nrm", normals(0.6 * a + 0.5 * s, 4.0))


def solar_tex(t):
    """One solar panel, 6 x 10 monocrystalline cells with busbars; UVs 0..1 across the panel."""
    w, hh = 608, 1024
    y, x = np.mgrid[0:hh, 0:w].astype(np.float32)
    fu, fv = (x / w * 6) % 1, (y / hh * 10) % 1
    eu, ev = np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv)
    sheet = (eu < 0.025) | (ev < 0.02) | (eu + ev < 0.09)  # gaps and chamfered cell corners
    col = np.ones((hh, w, 3), np.float32) * srgb(20, 28, 48)
    col *= (0.85 + 0.3 * fbm(w, 32, 3, 171)[np.arange(hh) % w])[..., None]
    col[np.min(np.abs(fu[..., None] - np.array([0.2, 0.5, 0.8])), axis=-1) < 0.008] = srgb(92, 98, 110)
    col[sheet] = srgb(48, 52, 60)
    t.save("solar_col", col)


def shake_tex(t, n=1024):
    """Hand-split cedar shakes, 0.25 m exposure, random widths 0.08-0.3 m: tile 1.5 m.

    Pale weathered wood for the app to tint (natural cedar, silvered,
    dark-stained): split grain along the slope, a dark keyway between
    shakes, a shadow under each course's butt and a little lichen; row 0
    (the image's top) is up the slope.
    """
    rows, T = 6, 1.5
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    cy = y / (n / rows)
    row = np.floor(cy).astype(int)
    fy = cy - row  # 0 just under the butt of the course above, 1 at this course's butt
    u = x / n * T
    rng = np.random.default_rng(181)
    sid = np.zeros((n, n), int)
    key = np.zeros((n, n), bool)
    for r_ in range(rows):
        w = []
        while sum(w) < T:
            w.append(0.08 + 0.22 * rng.random() ** 1.4)
        w = np.array(w) * T / sum(w)
        e = np.concatenate([[0.0], np.cumsum(w)])
        sel = row == r_
        uu = (u[sel] - rng.random() * T) % T
        k = np.clip(np.searchsorted(e, uu, side="right") - 1, 0, len(w) - 1)
        sid[sel] = r_ * 64 + k
        key[sel] = (uu - e[k]) < 0.006 + 0.004 * rng.random(len(w))[k]
    tone = rng.random(rows * 64)[sid]
    off = (rng.random(rows * 64)[sid] * n).astype(int)
    grain = fbm(n, 8, 6, 182, stretch=(10, 1))
    grain = grain[(y.astype(int) + off) % n, x.astype(int)]  # each shake split from elsewhere in the log
    lichen = fbm(n, 6, 5, 183)
    col = np.ones((n, n, 3), np.float32) * srgb(214, 198, 176)
    col *= (0.74 + 0.34 * tone + 0.5 * (grain - 0.5))[..., None]
    moss = (np.clip((lichen - 0.62) / 0.12, 0, 1) * np.clip(fy * 1.4 - 0.2, 0, 1) * 0.45)[..., None]
    col = col * (1 - moss) + srgb(150, 158, 118) * moss
    col *= (0.5 + 0.5 * np.clip(fy / 0.16, 0, 1) ** 0.7)[..., None]  # shadow under the course above
    col[fy > 0.965] *= 0.6  # the butt's end grain
    col[key] = srgb(34, 30, 26)
    h = 0.25 + 0.75 * fy + 0.35 * (grain - 0.5)
    h[key] = 0.0
    t.save("shake_col", col)
    t.save("shake_nrm", normals(h, 6.0))


def slate_tex(t, n=1024):
    """Natural roofing slates 0.25 m wide at a 0.2 m gauge, half-bonded: tile 2 x 1.2 m.

    Blue-grey for the app to tint (Welsh purple, Westmorland green, dark),
    each slate its own tone with a riven face, a thin dark joint between
    neighbours, the butt's edge catching the light over a shadow on the
    course below, a chipped corner here and there and a little lichen;
    row 0 (the image's top) is up the slope.
    """
    rows, cols, T = 6, 8, 2.0
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    cy = y / (n / rows)
    row = np.floor(cy).astype(int)
    fy = cy - row  # 0 just under the butt of the course above, 1 at this course's butt
    rng = np.random.default_rng(191)
    # Slates are cut to near the same width; each joint wanders a little.
    shift = rng.random(rows) * 0.06
    u = (x / n * T / 0.25 + 0.5 * (row % 2) + shift[row]) % cols
    sl = np.floor(u).astype(int)
    fx = u - sl
    sid = row * cols + sl
    wob = (rng.random(rows * cols) - 0.5) * 0.08
    fx = fx + wob[sid] * (1 - fy)
    joint = np.minimum(fx, 1 - fx) * 0.25 < 0.0035
    tone = rng.random(rows * cols)[sid]
    hue = rng.random(rows * cols)[sid]
    off = (rng.random(rows * cols)[sid] * n).astype(int)
    riven = fbm(n, 16, 6, 192, stretch=(3, 1))
    riven = riven[(y.astype(int) + off) % n, x.astype(int)]  # each slate split from its own block
    col = np.ones((n, n, 3), np.float32) * srgb(124, 128, 136)
    col *= (0.78 + 0.32 * tone + 0.35 * (riven - 0.5))[..., None]
    col *= 1 + 0.06 * (hue - 0.5)[..., None] * np.array([1.0, -0.4, -0.8], np.float32)
    lichen = fbm(n, 8, 5, 193)
    moss = (np.clip((lichen - 0.66) / 0.1, 0, 1) * np.clip(fy * 1.6 - 0.3, 0, 1) * 0.4)[..., None]
    col = col * (1 - moss) + srgb(170, 164, 120) * moss
    col *= (0.42 + 0.58 * np.clip(fy / 0.12, 0, 1) ** 0.6)[..., None]  # shadow under the course above
    butt = fy > 0.975
    col[butt] *= 1.3
    # A chipped lower corner on some slates: the course below shows through.
    chip = (rng.random(rows * cols)[sid] < 0.18) & (fy > 0.86) & (np.minimum(fx, 1 - fx) < (fy - 0.86) * 0.9)
    col[chip] *= 0.45
    col[joint] = srgb(30, 32, 36)
    h = 0.2 + 0.8 * fy + 0.25 * (riven - 0.5)
    h[joint] = 0.0
    h[chip] = 0.05
    rough = 0.62 + 0.25 * riven
    t.save("slate_col", col)
    t.save("slate_nrm", normals(h, 6.0))
    t.save("slate_rgh", rough)


def brownstone_tex(t, n=1024):
    """Brownstone: Triassic sandstone dressed smooth, laid as large ashlar slabs
    with fine joints: 2 x 4 slabs, tile 2.4 x 1.8 m.

    Chocolate to reddish brown for the app to tint, each slab its own tone,
    the bedding showing as faint horizontal laminations; the stone spalls
    along them, so patches of the face have flaked off, lighter and rougher,
    with a sharp lip. Row 0 is the top.
    """
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    cy = y / (n / 4)
    course = np.floor(cy).astype(int)
    fy = cy - course
    bx = x / (n / 2) + 0.5 * (course % 2)
    fx = bx - np.floor(bx)
    block = (np.floor(bx).astype(int) % 2) + course * 2
    edge = np.minimum(np.minimum(fx, 1 - fx) * 1.2, np.minimum(fy, 1 - fy) * 0.45)
    joint = edge < 0.004
    rng = np.random.default_rng(271)
    tone = rng.random(8)[block]
    hue = rng.random(8)[block]
    off = (rng.random(8)[block] * n).astype(int)
    beds = fbm(n, 6, 6, 272, stretch=(1, 10))
    beds = beds[(y.astype(int) + off) % n, x.astype(int)]  # each slab cut from its own block
    blot = fbm(n, 6, 5, 273)
    col = np.ones((n, n, 3), np.float32) * srgb(100, 74, 63)
    col *= (0.86 + 0.2 * tone + 0.1 * (beds - 0.5) + 0.12 * (blot - 0.5))[..., None]
    col *= 1 + 0.08 * (hue - 0.5)[..., None] * np.array([0.6, -0.2, -0.6], np.float32)
    # Spalls: the face lost along the bedding, fresher and paler beneath.
    sp = fbm(n, 12, 5, 274, stretch=(1, 3))
    spall = sp > 0.7
    lip = (sp > 0.68) & ~spall
    col[spall] = col[spall] * 1.07 + srgb(6, 5, 4)
    col[lip] *= 0.72
    col *= (0.88 + 0.24 * fbm(n, 96, 3, 275))[..., None]
    col[joint] = srgb(96, 70, 60)
    h = 0.6 + 0.08 * (beds - 0.5) + 0.12 * fbm(n, 64, 4, 276)
    h[spall] -= 0.25 + 0.2 * (sp[spall] - 0.7)
    h = np.where(joint, 0.35, h) * np.clip(edge / 0.008, 0.6, 1)
    rough = np.where(spall, 0.95, 0.74 + 0.12 * beds)
    t.save("brownstone_col", col)
    t.save("brownstone_nrm", normals(h, 4.0))
    t.save("brownstone_rgh", rough)


def boards_tex(t, n=1024):
    """Vertical tongue-and-groove boards 0.14 m wide with V-grooves: tile 1.4 m.

    Pale pine with knots, for the app to stain per building (cedar, honey,
    walnut, barn red, weathered grey, ...).
    """
    k = 10
    y, x = np.mgrid[0:n, 0:n]
    fx = (x / (n / k)) % 1
    b = x * k // n
    rng = np.random.default_rng(191)
    tone, off = rng.random(k)[b], rng.random(k)[b]
    grain = fbm(n, 6, 5, 192, stretch=(8, 1))
    grain = grain[(y + (off * n).astype(int)) % n, x]
    knots = fbm(n, 20, 3, 193) > 0.8
    col = np.ones((n, n, 3), np.float32) * srgb(226, 210, 186)
    col *= (0.84 + 0.2 * tone + 0.32 * (grain - 0.5))[..., None]
    col[knots] *= 0.72
    v = np.clip(np.minimum(fx, 1 - fx) * (n / k) / 3.5, 0, 1)  # the V-groove at each joint
    col *= (0.45 + 0.55 * v)[..., None]
    t.save("boards_col", col)
    t.save("boards_nrm", normals(v ** 0.5 + 0.05 * grain, 4.0))


def fluted_tex(t, n=1024):
    """Fluted stainless steel, the diner's skin: rounded horizontal ribs every
    0.025 m between flat lands, brushed along their length; tile 1 x 0.4 m."""
    rows = 16
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    fy = (y / (n / rows)) % 1
    rib = np.clip(np.abs(fy - 0.5) / 0.38, 0, 1)
    h = np.sqrt(np.clip(1 - rib ** 2, 0, 1))  # half-round ribs
    brush = fbm(n, 4, 6, 201, stretch=(1, 48))  # long streaks along the ribs
    fine = fbm(n, 8, 5, 202, stretch=(1, 96))
    col = np.ones((n, n, 3), np.float32) * srgb(206, 210, 214)
    col *= (0.84 + 0.12 * brush + 0.08 * fine)[..., None]
    col *= (0.82 + 0.18 * h)[..., None]
    rough = 0.2 + 0.14 * brush + 0.1 * (1 - h)
    t.save("fluted_col", col)
    t.save("fluted_nrm", normals(h + 0.01 * fine, 3.0))
    t.save("fluted_rgh", rough)


def glassblock_tex(t, n=1024):
    """Glass blocks, 0.2 m with 1 cm joints: 4 x 4 blocks, tile 0.8 m. Each
    block's face is moulded in vertical flutes ("Decora"), pale green glass
    with a bevel round it; the app lights them from behind at night."""
    k = 4
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    fx, fy = (x / (n / k)) % 1, (y / (n / k)) % 1
    e = np.minimum(np.minimum(fx, 1 - fx), np.minimum(fy, 1 - fy)) * 0.2  # m to the joint
    joint = e < 0.005
    bevel = np.clip((e - 0.005) / 0.014, 0, 1)
    flute = 0.5 + 0.5 * np.cos(fx * math.tau * 7)
    wave = fbm(n, 8, 4, 211)
    col = np.ones((n, n, 3), np.float32) * srgb(164, 196, 192)
    col *= (0.62 + 0.3 * flute + 0.12 * (wave - 0.5))[..., None] * (0.55 + 0.45 * bevel)[..., None]
    col[joint] = srgb(196, 192, 184)
    h = np.where(joint, 0.0, 0.4 + 0.6 * bevel ** 0.5) + 0.25 * flute * bevel
    t.save("glassblock_col", col)
    t.save("glassblock_nrm", normals(h, 4.0))


def corrugated_tex(t, n=1024):
    """Corrugated sheet, the factory's roofs and canopies: 76 mm sine corrugations
    running down the slope, two 0.76 m sheets side by side (lapped by one
    corrugation) and a lap across every 2.4 m; tile 1.52 x 2.4 m, row 0 up the
    slope. Weathered galvanising for the app to tint (or paint): spangle and
    blotches, white rust, rust bleeding down from the laps and the fixings."""
    w, hh = n, n * 2
    y, x = np.mgrid[0:hh, 0:w].astype(np.float32)
    u, v = x / w * 1.52, y / hh * 2.4
    k = 20  # corrugations across the tile
    ph = (x / w * k) % 1
    h = 0.5 + 0.5 * np.cos(ph * math.tau)  # crowns at the corrugation lines
    sheet = (u >= 0.76).astype(int)
    lap_u = np.abs(((u + 0.019) % 0.76) - 0.019) < 0.004  # the side lap, along a crown
    lap_v = v > 2.37  # the end lap: the sheet below tucks under
    rng = np.random.default_rng(221)
    tone = rng.random(2)[sheet]
    big = fbm(w, 3, 5, 222)[np.arange(hh) % w]
    spangle = fbm(w, 96, 2, 223)[(np.arange(hh) * 7) % w]
    streak = fbm(w, 3, 5, 224, stretch=(8, 1))[(np.arange(hh) // 2) % w]  # long streaks down the slope
    col = np.ones((hh, w, 3), np.float32) * srgb(196, 198, 196)
    col *= (0.82 + 0.12 * tone + 0.16 * (big - 0.5) + 0.08 * spangle)[..., None]
    # Fixings along the purlins (every 1.2 m, on alternate crowns), rust running down from them and the laps.
    fix = (np.abs(((v + 0.6) % 1.2) - 0.6) < 0.012) & (np.abs(ph) < 0.04) & ((np.floor(x / w * k) % 2) == 0)
    # Each fixing bleeds a narrow streak, fading as it runs down; some barely at all.
    cu = np.floor(x / w * k + 0.5).astype(int)  # the nearest crown
    dc = np.abs(x / w * k - cu)
    row = np.floor((v + 0.6) / 1.2).astype(int)
    fid = (cu % k) * 7 + row % 2
    strength = rng.random(k * 7 + 7)[fid] * (cu % 2 == 0)
    dv = (v - 0.01) % 1.2
    run = np.clip(1 - dv / (0.25 + 0.6 * strength), 0, 1) ** 1.5 * np.clip(dv / 0.02, 0, 1)
    below = run * np.exp(-((dc / (0.05 + 0.1 * run)) ** 2)) * strength
    rust = np.clip((streak - 0.5) / 0.4, 0, 1) * 0.35 + 0.9 * below
    rust *= 0.6 + 0.4 * h
    rust = np.maximum(rust, np.clip((v - 2.0) / 0.37, 0, 1) * np.clip((streak - 0.3) / 0.3, 0, 1) * 0.8)
    rc = srgb(132, 78, 46) * (0.8 + 0.3 * spangle)[..., None]
    col = col * (1 - 0.75 * rust[..., None]) + rc * 0.75 * rust[..., None]
    col[fix] = srgb(70, 64, 58)
    col *= (0.86 + 0.14 * h)[..., None]  # the troughs hold dirt
    col[lap_v] *= 0.55
    col[lap_u] *= 0.8
    hgt = h * 0.8 + 0.06 * spangle
    hgt[lap_v] -= 0.4
    rough = np.clip(0.4 + 0.35 * rust + 0.15 * big, 0, 1)
    t.save("corrugated_col", col)
    t.save("corrugated_nrm", normals(hgt, 9.0))
    t.save("corrugated_rgh", rough)


def blades_tex(t, n=512):
    """Horizontal metal blades every 0.1 m, louvre screens and roller shutters: tile 1 m.

    Light grey for tinting: each blade's sloped face lit from above, the dark
    gap under its lip, a little weathering.
    """
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    fy = (y / (n / 10)) % 1  # 0 at a blade's top edge, 1 at the next blade
    face = np.clip(fy / 0.78, 0, 1)
    gap = fy > 0.82
    grime = fbm(n, 6, 4, 231, stretch=(4, 1))
    col = np.ones((n, n, 3), np.float32) * srgb(196, 198, 200)
    col *= (0.92 - 0.3 * face)[..., None] * (0.9 + 0.15 * grime)[..., None]
    col[gap] = srgb(30, 32, 34)
    col[(fy > 0.78) & ~gap] *= 1.25  # the lip catches the light
    h = np.where(gap, 0.0, 1.0 - 0.5 * face)
    t.save("blades_col", col)
    t.save("blades_nrm", normals(h, 5.0))


def grime_tex(t, n=512):
    """Grey noise the app samples in world space for weathering: blotches and rain streaks."""
    g = fbm(n, 4, 7, 91)
    g = (g - g.min()) / (g.max() - g.min())
    t.save("grime", g)


def ground_tex(t, n=1024):
    """Pavement slabs (0.9 m, tile 3.6 m) and asphalt (tile 6 m) for streets and the viewer."""
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    f = (x / (n / 4)) % 1, (y / (n / 4)) % 1
    e = np.minimum(np.minimum(f[0], 1 - f[0]), np.minimum(f[1], 1 - f[1]))
    slab = (np.floor(x / (n / 4)) + 4 * np.floor(y / (n / 4))).astype(int)
    tone = np.random.default_rng(81).random(16)[slab]
    a = fbm(n, 16, 6, 82)
    col = srgb(142, 138, 132) * (0.86 + 0.1 * tone + 0.12 * (a - 0.5))[..., None]
    col[e < 0.006] *= 0.6
    t.save("pave_col", col)
    t.save("pave_nrm", normals(np.clip(e / 0.01, 0, 1) + 0.1 * fbm(n, 128, 3, 83), 3.0))
    g = fbm(n, 256, 2, 84)
    p = fbm(n, 8, 6, 85)
    col = srgb(64, 64, 66) * (0.75 + 0.3 * g + 0.3 * (p - 0.5))[..., None]
    col[g > 0.75] = srgb(120, 118, 114)
    t.save("asphalt_col", col)
    t.save("asphalt_nrm", normals(g, 1.5))


TEXTURES = (
    brick_tex, stone_tex, ashlar_tex, granite_tex, roof_tex, wood_tex, siding_tex, shingle_tex, louvre_tex, bars_tex, grate_tex, awning_tex,
    render_tex, battens_tex, gravel_tex, sedum_tex, solar_tex, shake_tex, boards_tex, fluted_tex, glassblock_tex, corrugated_tex, slate_tex, rustic_tex, brownstone_tex, ground_tex, blades_tex,
    grime_tex,
)


def textures(out, which=None):
    t = Tex(out)
    for f in which or TEXTURES:
        f(t)
        print("texture", f.__name__)


# ---- geometry ------------------------------------------------------------------

AXES = {(1, 0, 0): "x1", (-1, 0, 0): "x0", (0, 1, 0): "y1", (0, -1, 0): "y0", (0, 0, 1): "z1", (0, 0, -1): "z0"}


def key(v):
    return AXES[tuple(int(round(c)) for c in v)]


class Mesh:
    """Faces by material role. `part` tags new faces with the piece they belong to."""

    def __init__(self, name):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.fixed = self.bm.faces.layers.int.new("fixed")
        self.piece = self.bm.faces.layers.int.new("piece")
        self.part = 0
        self.roles = []

    def mi(self, role):
        if role not in self.roles:
            self.roles.append(role)
        return self.roles.index(role)

    def poly(self, role, pts, out=None, uvs=None, smooth=False):
        vs = [self.bm.verts.new(Vector(p)) for p in pts]
        f = self.bm.faces.new(vs)
        f.material_index = self.mi(role)
        f.smooth = smooth
        f[self.piece] = self.part
        f.normal_update()
        if out is not None and f.normal.dot(Vector(out)) < 0:
            f.normal_flip()
        if uvs:
            at = {v: uv for v, uv in zip(vs, uvs)}
            for loop in f.loops:
                loop[self.uv].uv = at[loop.vert]
            f[self.fixed] = 1
        return f

    def box(self, role, lo, hi, skip=()):
        (x0, y0, z0), (x1, y1, z1) = lo, hi
        x0, x1 = min(x0, x1), max(x0, x1)
        y0, y1 = min(y0, y1), max(y0, y1)
        z0, z1 = min(z0, z1), max(z0, z1)
        faces = {
            "x0": ([(x0, y0, z0), (x0, y1, z0), (x0, y1, z1), (x0, y0, z1)], (-1, 0, 0)),
            "x1": ([(x1, y0, z0), (x1, y1, z0), (x1, y1, z1), (x1, y0, z1)], (1, 0, 0)),
            "y0": ([(x0, y0, z0), (x1, y0, z0), (x1, y0, z1), (x0, y0, z1)], (0, -1, 0)),
            "y1": ([(x0, y1, z0), (x1, y1, z0), (x1, y1, z1), (x0, y1, z1)], (0, 1, 0)),
            "z0": ([(x0, y0, z0), (x1, y0, z0), (x1, y1, z0), (x0, y1, z0)], (0, 0, -1)),
            "z1": ([(x0, y0, z1), (x1, y0, z1), (x1, y1, z1), (x0, y1, z1)], (0, 0, 1)),
        }
        for k, (pts, out) in faces.items():
            if k not in skip:
                self.poly(role, pts, out)

    def strut(self, role, a, b, t, t2=None):
        """A square bar from a to b."""
        a, b = Vector(a), Vector(b)
        ax = (b - a).normalized()
        p1 = ax.cross(Z) if abs(ax.z) < 0.99 else Vector((1, 0, 0))
        p1.normalize()
        p2 = ax.cross(p1).normalized()
        h1, h2 = p1 * t / 2, p2 * (t2 or t) / 2
        ring = [h1 + h2, -h1 + h2, -h1 - h2, h1 - h2]
        for i in range(4):
            c0, c1 = ring[i], ring[(i + 1) % 4]
            self.poly(role, [a + c0, a + c1, b + c1, b + c0], out=(c0 + c1))
        self.poly(role, [a + c for c in ring], out=-ax)
        self.poly(role, [b + c for c in ring], out=ax)

    def cyl(self, role, x, y, r, z0, z1, seg=24, top=True, bottom=False, uv=False, r1=None):
        r1 = r if r1 is None else r1
        for i in range(seg):
            a0, a1 = i / seg * math.tau, (i + 1) / seg * math.tau
            p = lambda a, rr, z: (x + math.cos(a) * rr, y + math.sin(a) * rr, z)  # noqa: E731
            pts = [p(a0, r, z0), p(a1, r, z0), p(a1, r1, z1), p(a0, r1, z1)]
            uvs = [(a0 * r, z0), (a1 * r, z0), (a1 * r, z1), (a0 * r, z1)] if uv else None
            mid = (a0 + a1) / 2
            self.poly(role, pts, out=(math.cos(mid), math.sin(mid), 0), uvs=uvs, smooth=True)
        ring = lambda rr, z: [(x + math.cos(i / seg * math.tau) * rr, y + math.sin(i / seg * math.tau) * rr, z) for i in range(seg)]  # noqa: E731
        if top and r1 > 0:
            self.poly(role, ring(r1, z1), out=(0, 0, 1))
        if bottom:
            self.poly(role, ring(r, z0), out=(0, 0, -1))

    def sweep(self, role, W, D, profile, cx=0.0, cy=0.0):
        """Sweeps (offset, z) points round a W x D rectangle with mitred corners."""
        def ring(o, z):
            return [(cx - W / 2 - o, cy - D / 2 - o, z), (cx + W / 2 + o, cy - D / 2 - o, z),
                    (cx + W / 2 + o, cy + D / 2 + o, z), (cx - W / 2 - o, cy + D / 2 + o, z)]
        outs = [(0, -1, 0), (1, 0, 0), (0, 1, 0), (-1, 0, 0)]
        for (o0, z0), (o1, z1) in zip(profile, profile[1:]):
            r0, r1 = ring(o0, z0), ring(o1, z1)
            for i in range(4):
                j = (i + 1) % 4
                dz, do = z1 - z0, o1 - o0
                out = Vector(outs[i]) * dz - Z * do  # perpendicular to the profile segment
                if out.length < 1e-6:
                    continue
                self.poly(role, [r0[i], r0[j], r1[j], r1[i]], out=out)

    def psweep(self, role, poly, profile):
        """Sweeps (offset, z) points round a convex polygon of (x, y) points, counter-clockwise
        seen from above, with mitred corners: cornices and plinths round any footprint."""
        P = [Vector((x, y)) for x, y in poly]
        n = len(P)

        def ring(o, z):
            out = []
            for i in range(n):
                a, b, c = P[i - 1], P[i], P[(i + 1) % n]
                t0, t1 = (b - a).normalized(), (c - b).normalized()
                n0, n1 = Vector((t0.y, -t0.x)), Vector((t1.y, -t1.x))  # outward
                bis = (n0 + n1).normalized()
                q = b + bis * (o / bis.dot(n0))
                out.append((q.x, q.y, z))
            return out

        for (o0, z0), (o1, z1) in zip(profile, profile[1:]):
            r0, r1 = ring(o0, z0), ring(o1, z1)
            for i in range(n):
                j = (i + 1) % n
                t = (P[j] - P[i]).normalized()
                nrm = Vector((t.y, -t.x, 0))
                out = nrm * (z1 - z0) - Z * (o1 - o0)
                if out.length < 1e-6:
                    continue
                self.poly(role, [r0[i], r0[j], r1[j], r1[i]], out=out)

    def tube(self, role, pts, r, up, closed=True, seg=6):
        """A round tube of radius r along points (neon, pipe rails); `up` is the
        normal of the plane the path lies in (or any vector off its tangents)."""
        pts = [Vector(p) for p in pts]
        n, up = len(pts), Vector(up).normalized()
        rings = []
        for i in range(n):
            a = pts[i - 1] if closed or i else pts[i]
            b = pts[(i + 1) % n] if closed or i < n - 1 else pts[i]
            t = (b - a).normalized()
            side = t.cross(up).normalized()
            rings.append([pts[i] + (side * math.cos(k / seg * math.tau) + up * math.sin(k / seg * math.tau)) * r for k in range(seg)])
        for i in range(n if closed else n - 1):
            r0, r1 = rings[i], rings[(i + 1) % n]
            for k in range(seg):
                j = (k + 1) % seg
                mid = (r0[k] + r0[j] + r1[k] + r1[j]) / 4 - (pts[i] + pts[(i + 1) % n]) / 2
                self.poly(role, [r0[k], r0[j], r1[j], r1[k]], out=mid, smooth=True)
        if not closed:
            for ring, p, q in ((rings[0], pts[0], pts[1]), (rings[-1], pts[-1], pts[-2])):
                self.poly(role, ring, out=p - q)

    def finish(self, sharp=None):
        """`sharp` (radians): edges whose faces meet at a steeper angle shade hard, the rest smooth."""
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=0.0004)
        if sharp is not None:
            for e in self.bm.edges:
                if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > sharp:
                    e.smooth = False
        for f in self.bm.faces:
            if f[self.fixed]:
                continue
            n = f.normal
            for loop in f.loops:
                p = loop.vert.co
                if abs(n.z) > 0.7:
                    uv = (p.x, p.y)
                elif abs(n.x) >= abs(n.y):
                    uv = (p.y * (1 if n.x > 0 else -1), p.z)
                else:
                    uv = (-p.x * (1 if n.y > 0 else -1), p.z)
                loop[self.uv].uv = uv
        me = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(me)
        for role in self.roles:
            mat = bpy.data.materials.get(role) or bpy.data.materials.new(role)
            me.materials.append(mat)
        ob = bpy.data.objects.new(self.name, me)
        bpy.context.scene.collection.objects.link(ob)
        return ob


class Side:
    """A facade's frame: u along it (left to right seen from outside), z up, w outward."""

    def __init__(self, m, o, t, n):
        self.m, self.o, self.t, self.n = m, Vector(o), Vector(t).normalized(), Vector(n).normalized()
        self.square = all(abs(c) < 1e-6 or abs(abs(c) - 1) < 1e-6 for c in (*self.t, *self.n))

    def p(self, u, z, w=0.0):
        return self.o + self.t * u + Z * z + self.n * w

    def box(self, role, u0, u1, z0, z1, w0, w1, skip=("back",), m=None):
        m = m or self.m
        if self.square:
            names = {"back": key(-self.n), "front": key(self.n), "left": key(-self.t), "right": key(self.t), "top": "z1", "bottom": "z0"}
            m.box(role, self.p(u0, z0, w0), self.p(u1, z1, w1), [names[s] for s in skip])
            return
        # A facade at an angle (a canted bay): the same box, oriented along it.
        u0, u1 = sorted((u0, u1))
        z0, z1 = sorted((z0, z1))
        w0, w1 = sorted((w0, w1))
        p = self.p
        faces = {
            "back": ([p(u0, z0, w0), p(u1, z0, w0), p(u1, z1, w0), p(u0, z1, w0)], -self.n),
            "front": ([p(u0, z0, w1), p(u1, z0, w1), p(u1, z1, w1), p(u0, z1, w1)], self.n),
            "left": ([p(u0, z0, w0), p(u0, z0, w1), p(u0, z1, w1), p(u0, z1, w0)], -self.t),
            "right": ([p(u1, z0, w0), p(u1, z0, w1), p(u1, z1, w1), p(u1, z1, w0)], self.t),
            "bottom": ([p(u0, z0, w0), p(u1, z0, w0), p(u1, z0, w1), p(u0, z0, w1)], -Z),
            "top": ([p(u0, z1, w0), p(u1, z1, w0), p(u1, z1, w1), p(u0, z1, w1)], Z),
        }
        for k, (pts, out) in faces.items():
            if k not in skip:
                m.poly(role, pts, out)

    def quad(self, role, u0, u1, z0, z1, w=0.0, uvs=None, out=None, m=None):
        pts = [self.p(u0, z0, w), self.p(u1, z0, w), self.p(u1, z1, w), self.p(u0, z1, w)]
        (m or self.m).poly(role, pts, out=out or self.n, uvs=uvs)

    def wall(self, role, u0, u1, z0, z1, holes, depth=0.22, reveal=None):
        zs = sorted({z0, z1, *[c for h in holes for c in h[2:4] if z0 < c < z1]})
        for za, zb in zip(zs, zs[1:]):
            cover = sorted((h[0], h[1]) for h in holes if h[2] <= za + 1e-6 and h[3] >= zb - 1e-6)
            u = u0
            for a, b in cover:
                if a > u + 1e-6:
                    self.quad(role, u, a, za, zb)
                u = max(u, b)
            if u1 > u + 1e-6:
                self.quad(role, u, u1, za, zb)
        rv = reveal or role
        for a, b, c, e, *deep in holes:
            d = deep[0] if deep else depth
            self.m.poly(rv, [self.p(a, c, 0), self.p(a, c, -d), self.p(a, e, -d), self.p(a, e, 0)], out=self.t)
            self.m.poly(rv, [self.p(b, c, 0), self.p(b, c, -d), self.p(b, e, -d), self.p(b, e, 0)], out=-self.t)
            self.m.poly(rv, [self.p(a, e, 0), self.p(b, e, 0), self.p(b, e, -d), self.p(a, e, -d)], out=-Z)
            self.m.poly(rv, [self.p(a, c, 0), self.p(b, c, 0), self.p(b, c, -d), self.p(a, c, -d)], out=Z)


def fpoly(F, role, pts, w=0.0, out=None, m=None):
    """A polygon of (u, z) points in facade F's plane at depth w; repeated points are dropped."""
    q = []
    for u, z in pts:
        if not q or abs(q[-1][0] - u) + abs(q[-1][1] - z) > 1e-6:
            q.append((u, z))
    if len(q) > 2 and abs(q[0][0] - q[-1][0]) + abs(q[0][1] - q[-1][1]) < 1e-6:
        q.pop()
    if len(q) > 2:
        (m or F.m).poly(role, [F.p(u, z, w) for u, z in q], out=out or F.n)


def sides(m, W, D, cx=0.0, cy=0.0, z=0.0):
    """The four facades of a W x D box, seen from outside: front (-y), right (+x), back, left."""
    return {
        "front": Side(m, (cx, cy - D / 2, z), (1, 0, 0), (0, -1, 0)),
        "right": Side(m, (cx + W / 2, cy, z), (0, 1, 0), (1, 0, 0)),
        "back": Side(m, (cx, cy + D / 2, z), (-1, 0, 0), (0, 1, 0)),
        "left": Side(m, (cx - W / 2, cy, z), (0, -1, 0), (-1, 0, 0)),
    }


def offset(poly, d):
    """Offsets an open polyline of (u, w) points outward (to its left, w up) by d; the ends slide along w = 0."""
    P = [Vector((u, w)) for u, w in poly]
    segs = []
    for p, q in zip(P, P[1:]):
        t = (q - p).normalized()
        segs.append((p + Vector((-t.y, t.x)) * d, t))
    out = []
    first_p, first_t = segs[0]
    out.append(first_p - first_t * (first_p.y / first_t.y))
    for (p0, t0), (p1, t1) in zip(segs, segs[1:]):
        # Intersection of the two offset lines.
        den = t0.x * t1.y - t0.y * t1.x
        s = ((p1 - p0).x * t1.y - (p1 - p0).y * t1.x) / den
        out.append(p0 + t0 * s)
    last_p, last_t = segs[-1]
    out.append(last_p - last_t * (last_p.y / last_t.y))
    return out


# ---- lettering -------------------------------------------------------------------------


def _text_mesh(body, size, extrude, offset, res, spacing):
    cu = bpy.data.curves.new("glyphs", "FONT")
    cu.body = body
    cu.size = size
    cu.extrude = extrude
    cu.offset = offset
    cu.resolution_u = res
    cu.space_character = spacing
    cu.fill_mode = "BOTH"
    ob = bpy.data.objects.new("glyphs", cu)
    bpy.context.scene.collection.objects.link(ob)
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(bpy.context.evaluated_depsgraph_get()))
    bpy.data.objects.remove(ob)
    bpy.data.curves.remove(cu)
    vs = [v.co.copy() for v in me.vertices]
    # Centre on the letters' bounding box (cap height, not the font's line box).
    c = Vector(((min(v.x for v in vs) + max(v.x for v in vs)) / 2, (min(v.y for v in vs) + max(v.y for v in vs)) / 2, 0))
    return me, [v - c for v in vs]


def glyphs(body, size, extrude=0.04, offset=0.0, res=3, spacing=1.0):
    """Solid letters in Blender's bundled font, as polygons of (x, y, z): x along
    the line, y up, z out of the face (from -extrude to +extrude), centred on
    the origin. `offset` thickens (or thins) the strokes, in metres."""
    me, vs = _text_mesh(body, size, extrude, offset, res, spacing)
    polys = [[vs[i] for i in p.vertices] for p in me.polygons]
    bpy.data.meshes.remove(me)
    return polys


def outlines(body, size, offset=0.0, res=3, spacing=1.0):
    """The letters' outlines as closed loops of (x, y, 0), for neon tubes: the
    boundary of the flat-filled text; a negative `offset` pulls them inside the
    strokes. Centred like glyphs() with the same arguments (offset aside)."""
    me, vs = _text_mesh(body, size, 0.0, offset, res, spacing)
    bm = bmesh.new()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    bm.verts.ensure_lookup_table()
    nxt = {}
    for e in bm.edges:
        if len(e.link_faces) == 1:
            # Follow the face's winding so every loop runs the same way round.
            f = e.link_faces[0]
            for loop in f.loops:
                if loop.edge == e:
                    nxt[loop.vert.index] = loop.link_loop_next.vert.index
    loops, seen = [], set()
    for start in nxt:
        if start in seen:
            continue
        loop, v = [], start
        while v not in seen and v in nxt:
            seen.add(v)
            loop.append(vs[v].copy())
            v = nxt[v]
        if len(loop) > 2:
            loops.append(loop)
    bm.free()
    return loops


def letters(m, role, F, u, z, w, body, size, depth=0.06, offset=0.0, spacing=1.0):
    """Solid letters standing `depth` proud of facade F, centred at (u, z), face at w + depth."""
    for poly in glyphs(body, size, depth / 2, offset, spacing=spacing):
        m.poly(role, [F.p(u + v.x, z + v.y, w + depth / 2 + v.z) for v in poly])


def neon(m, role, F, u, z, w, body, size, r=0.012, inset=0.03, offset=0.0, spacing=1.0):
    """Neon tubes following the letters' outlines `inset` inside them, on facade F at depth w."""
    for loop in outlines(body, size, offset - inset, spacing=spacing):
        m.tube(role, [F.p(u + v.x, z + v.y, w) for v in loop], r, F.n, seg=5)


# ---- windows and common components -------------------------------------------------

WID = [0]


def new_id():
    WID[0] += 1
    assert WID[0] < 256, "too many windows in one piece"
    return WID[0]


def pane(F, role, a, b, c, e, u0, u1, z0, z1, w, wid):
    """A glass pane inside opening (a..b, c..e): UV0 is (window id + u, v) over the opening."""
    uv = lambda u, z: (wid + (u - a) / (b - a), (z - c) / (e - c))  # noqa: E731
    F.quad(role, u0, u1, z0, z1, w, uvs=[uv(u0, z0), uv(u1, z0), uv(u1, z1), uv(u0, z1)])


def sash(F, a, b, c, e, D=0.22, lights=(2, 1), fr="frame", glass="glass"):
    """A double-hung sash window in the opening (a..b, c..e) set D deep.

    `lights` is (across, up) panes per sash: (2, 1) is two-over-two,
    (3, 2) six-over-six.
    """
    wid = new_id()
    fw = 0.07
    F.box(fr, a, a + fw, c, e, -D, -D + 0.11)
    F.box(fr, b - fw, b, c, e, -D, -D + 0.11)
    F.box(fr, a + fw, b - fw, e - fw, e, -D, -D + 0.11)
    F.box(fr, a + fw, b - fw, c, c + 0.05, -D, -D + 0.13)
    ia, ib, ic, ie = a + fw, b - fw, c + 0.05, e - fw
    mid = (ic + ie) / 2 + 0.04
    st = 0.05
    nx, ny = lights
    for z0, z1, wa, wb in ((mid - 0.025, ie, -D + 0.07, -D + 0.11), (ic, mid + 0.025, -D + 0.025, -D + 0.065)):
        F.box(fr, ia, ia + st, z0, z1, wa, wb)
        F.box(fr, ib - st, ib, z0, z1, wa, wb)
        F.box(fr, ia + st, ib - st, z1 - st, z1, wa, wb)
        F.box(fr, ia + st, ib - st, z0, z0 + st, wa, wb)
        gw = wa + 0.015
        pane(F, glass, a, b, c, e, ia + st, ib - st, z0 + st, z1 - st, gw, wid)
        for i in range(1, nx):
            u = ia + st + i * (ib - ia - 2 * st) / nx
            F.box(fr, u - 0.014, u + 0.014, z0 + st, z1 - st, gw, wb - 0.012)
        for j in range(1, ny):
            z = z0 + st + j * (z1 - z0 - 2 * st) / ny
            F.box(fr, ia + st, ib - st, z - 0.014, z + 0.014, gw, wb - 0.012)


def french(F, a, b, c, e, D=0.22):
    """A pair of glazed doors onto a balcony, with a transom light."""
    fr, wid = "frame", new_id()
    fw = 0.08
    F.box(fr, a, a + fw, c, e, -D, -D + 0.11)
    F.box(fr, b - fw, b, c, e, -D, -D + 0.11)
    F.box(fr, a + fw, b - fw, e - fw, e, -D, -D + 0.11)
    t = e - 0.45
    F.box(fr, a + fw, b - fw, t - 0.06, t, -D, -D + 0.11)
    pane(F, "glass", a, b, c, e, a + fw, b - fw, t, e - fw, -D + 0.04, wid)
    m = (a + b) / 2
    for l0, l1 in ((a + fw, m), (m, b - fw)):
        F.box(fr, l0, l0 + 0.06, c, t - 0.06, -D + 0.02, -D + 0.08)
        F.box(fr, l1 - 0.06, l1, c, t - 0.06, -D + 0.02, -D + 0.08)
        F.box(fr, l0 + 0.06, l1 - 0.06, c, c + 0.45, -D + 0.02, -D + 0.08)
        F.box(fr, l0 + 0.06, l1 - 0.06, t - 0.12, t - 0.06, -D + 0.02, -D + 0.08)
        F.box(fr, l0 + 0.06, l1 - 0.06, c + 0.45, c + 0.51, -D + 0.02, -D + 0.08)
        pane(F, "glass", a, b, c, e, l0 + 0.06, l1 - 0.06, c + 0.51, t - 0.12, -D + 0.04, wid)


def glazing(F, a, b, c, e, lights=1, D=0.12, fr="alu", slide=False, ends=(True, True), glass="glass"):
    """A modern window or glass wall in the opening (a..b, c..e), glass D deep:
    a slim aluminium frame and `lights` panes between mullions, one room
    behind them all. `slide` makes the lights sliding leaves in sashes of
    their own, alternately in front and behind; `glass` is the panes' role
    (the room behind them). An end in `ends` that is
    False is left frameless, for glass meeting glass at a corner: the
    opening runs to the corner and the glass stops D short of it, where the
    other side's glass is."""
    wid = new_id()
    fw = 0.05
    w0, w1 = -D - 0.04, -D + 0.05
    if ends[0]:
        F.box(fr, a, a + fw, c, e, w0, w1)
    if ends[1]:
        F.box(fr, b - fw, b, c, e, w0, w1)
    fa, fb = a if ends[0] else a + D - 0.05, b if ends[1] else b - D + 0.05
    F.box(fr, fa, fb, e - fw, e, w0, w1)
    F.box(fr, fa, fb, c, c + fw, w0, w1 + 0.02)
    ia, ib = a + (fw if ends[0] else D), b - (fw if ends[1] else D)
    ic, ie = c + fw, e - fw
    us = [ia + i * (ib - ia) / lights for i in range(lights + 1)]
    for i in range(lights):
        u0, u1 = us[i], us[i + 1]
        if slide:
            # Leaves overlap their neighbours; the sash is wider at the meeting stiles.
            u0, u1 = u0 - (0.03 if i else 0), u1 + (0.03 if i < lights - 1 else 0)
            w = -D + (0.025 if i % 2 else -0.025)
            s = 0.045
            for box in ((u0, u0 + s, ic, ie), (u1 - s, u1, ic, ie), (u0 + s, u1 - s, ic, ic + s), (u0 + s, u1 - s, ie - s, ie)):
                F.box(fr, *box, w - 0.022, w + 0.022)
            pane(F, glass, a, b, c, e, u0 + s, u1 - s, ic + s, ie - s, w, wid)
        else:
            if i:
                F.box(fr, u0 - 0.025, u0 + 0.025, ic, ie, -D - 0.03, -D + 0.05)
            pane(F, glass, a, b, c, e, u0 + (0.025 if i else 0), u1 - (0.025 if i < lights - 1 else 0), ic, ie, -D, wid)
    return wid


def sill(F, a, b, c, D=0.22, role="stone"):
    F.box(role, a - 0.09, b + 0.09, c - 0.07, c + 0.015, -D + 0.04, 0.06)


def lintel(F, a, b, e, key_=True, role="stone"):
    F.box(role, a - 0.1, b + 0.1, e, e + 0.26, 0, 0.025)
    if key_:
        m = (a + b) / 2
        F.box(role, m - 0.11, m + 0.11, e - 0.04, e + 0.32, 0, 0.05)


def hood(F, a, b, e, role="stone"):
    """A pedimented window head: a frieze, a cornice and two consoles."""
    F.box(role, a - 0.16, b + 0.16, e, e + 0.3, 0, 0.04)
    F.box(role, a - 0.26, b + 0.26, e + 0.3, e + 0.38, 0, 0.16)
    F.box(role, a - 0.3, b + 0.3, e + 0.38, e + 0.44, 0, 0.2)
    for u in (a - 0.2, b + 0.08):
        F.box(role, u, u + 0.12, e - 0.3, e + 0.3, 0, 0.12)


def ac_unit(F, u, c):
    F.box("ac", u - 0.33, u + 0.33, c + 0.04, c + 0.44, -0.12, 0.42, skip=())
    F.box("dark", u - 0.29, u + 0.29, c + 0.08, c + 0.4, 0.42, 0.425, skip=("back",))
    F.box("iron", u - 0.25, u - 0.22, c - 0.3, c + 0.05, 0.0, 0.35)
    F.box("iron", u + 0.22, u + 0.25, c - 0.3, c + 0.05, 0.0, 0.35)


def railing(F, cut, u0, u1, z, w0, w1, h=1.0):
    """Posts and rails in iron with alpha-tested bars between, round three sides."""
    for u in (u0, u1):
        F.box("iron", u - 0.025, u + 0.025, z, z + h, w1 - 0.05, w1)
        F.box("iron", u - 0.02, u + 0.02, z + h - 0.04, z + h, w0, w1)
        F.box("iron", u - 0.015, u + 0.015, z + 0.06, z + 0.1, w0, w1)
    F.box("iron", u0 - 0.03, u1 + 0.03, z + h - 0.04, z + h + 0.01, w1 - 0.06, w1 + 0.01)
    F.box("iron", u0, u1, z + 0.06, z + 0.1, w1 - 0.04, w1 - 0.01)
    L = u1 - u0
    uvs = lambda l: [(0, 0), (l / 1.2, 0), (l / 1.2, 1), (0, 1)]  # noqa: E731
    F.quad("bars", u0, u1, z + 0.1, z + h - 0.04, w1 - 0.025, uvs=uvs(L), m=cut)
    for u, out in ((u0, -F.t), (u1, F.t)):
        pts = [F.p(u, z + 0.1, w1), F.p(u, z + 0.1, w0), F.p(u, z + h - 0.04, w0), F.p(u, z + h - 0.04, w1)]
        cut.poly("bars", pts, out=out, uvs=uvs(w1 - w0))


def grille(F, a, b, c, e):
    """Iron security bars over a ground-storey window."""
    for i in range(7):
        u = a + 0.08 + i * (b - a - 0.16) / 6
        F.box("iron", u - 0.012, u + 0.012, c + 0.02, e - 0.02, 0.02, 0.05)
    for z in (c + 0.12, (c + e) / 2, e - 0.12):
        F.box("iron", a + 0.04, b - 0.04, z - 0.015, z + 0.015, 0.05, 0.075)


def balcony(F, cut, u, z):
    """A stone balcony on two scrolled corbels with an iron railing."""
    F.box("stone", u - 1.15, u + 1.15, z - 0.18, z, 0, 0.95, skip=())
    F.box("stone", u - 1.18, u + 1.18, z - 0.24, z - 0.18, 0, 0.98, skip=())
    for k in (-0.85, 0.85):
        F.box("stone", u + k - 0.1, u + k + 0.1, z - 0.6, z - 0.24, 0, 0.35)
        F.box("stone", u + k - 0.1, u + k + 0.1, z - 0.4, z - 0.24, 0.35, 0.75)
    railing(F, cut, u - 1.1, u + 1.1, z, 0.05, 0.9)


def shopfront(F, a, b, c, e, sign=0, door_left=False, D_=0.3, sign_w=None):
    """A shopfront in the opening (a..b, c..e) set D_ deep: stallriser, display
    window, a door at one end, transom lights, and a fascia above e with the
    sign (u = sign column + 0..1; the app picks the names) between consoles.
    `sign_w` narrows the sign to a panel in the middle of the fascia."""
    fr = "shopframe"
    t = e - 0.6  # transom bar
    # Stallriser, posts, transom bar, head.
    F.box(fr, a, b, c, c + 0.4, -D_, -D_ + 0.14)
    F.box(fr, a, a + 0.1, c, e, -D_, -D_ + 0.16)
    F.box(fr, b - 0.1, b, c, e, -D_, -D_ + 0.16)
    F.box(fr, a + 0.1, b - 0.1, t - 0.08, t, -D_, -D_ + 0.16)
    F.box(fr, a + 0.1, b - 0.1, e - 0.08, e, -D_, -D_ + 0.16)
    wid = new_id()
    dw = 1.1
    d0, d1 = (a + 0.1, a + 0.1 + dw) if door_left else (b - 0.1 - dw, b - 0.1)
    g0, g1 = (d1 + 0.06, b - 0.1) if door_left else (a + 0.1, d0 - 0.06)
    F.box(fr, d0 - 0.06 if not door_left else d1, d0 if not door_left else d1 + 0.06, c, t, -D_, -D_ + 0.16)
    # Display window in two lights, and the door.
    mid = (g0 + g1) / 2
    F.box(fr, mid - 0.03, mid + 0.03, c + 0.4, t - 0.08, -D_ + 0.02, -D_ + 0.12)
    pane(F, "shopglass", a, b, c, e, g0, g1, c + 0.4, t - 0.08, -D_ + 0.06, wid)
    pane(F, "shopglass", a, b, c, e, a + 0.1, b - 0.1, t, e - 0.08, -D_ + 0.06, wid)
    for u in [a + 0.1 + i * (b - a - 0.2) / 4 for i in range(1, 4)]:
        F.box(fr, u - 0.025, u + 0.025, t, e - 0.08, -D_ + 0.02, -D_ + 0.12)
    F.box(fr, d0, d1, c, c + 0.1, -D_ - 0.05, -D_ + 0.04)
    F.box(fr, d0, d0 + 0.09, c, t - 0.08, -D_ - 0.05, -D_ + 0.04)
    F.box(fr, d1 - 0.09, d1, c, t - 0.08, -D_ - 0.05, -D_ + 0.04)
    F.box(fr, d0 + 0.09, d1 - 0.09, c + 0.1, c + 0.35, -D_ - 0.05, -D_ + 0.04)
    F.box(fr, d0 + 0.09, d1 - 0.09, t - 0.16, t - 0.08, -D_ - 0.05, -D_ + 0.04)
    pane(F, "shopglass", a, b, c, e, d0 + 0.09, d1 - 0.09, c + 0.35, t - 0.16, -D_, wid)
    hx = d1 - 0.18 if door_left else d0 + 0.14
    F.box("brass", hx, hx + 0.04, c + 0.85, c + 1.3, -D_ + 0.04, -D_ + 0.08)
    # Fascia with the sign, between console brackets.
    F.box(fr, a - 0.15, b + 0.15, e + 0.1, e + 0.8, 0, 0.12)
    F.box(fr, a - 0.2, b + 0.2, e + 0.8, e + 0.88, 0, 0.18)
    s0, s1 = (a + 0.1, b - 0.1) if sign_w is None else ((a + b - sign_w) / 2, (a + b + sign_w) / 2)
    F.quad("sign", s0, s1, e + 0.17, e + 0.73, 0.121, uvs=[(sign, 0), (sign + 1, 0), (sign + 1, 1), (sign, 1)])
    for u in (a - 0.32, b + 0.15):
        F.box(fr, u, u + 0.17, e - 0.15, e + 0.88, 0, 0.2)


def awning(F, x0, x1, top, drop=0.75, depth=1.5):
    """A canvas awning from the wall at `top`, falling `drop` over `depth`, with a valance and iron arms."""
    m, p = F.m, F.p
    for out in (F.n + Z, -F.n - Z):
        m.poly("awning", [p(x0, top, 0.05), p(x1, top, 0.05), p(x1, top - drop, depth), p(x0, top - drop, depth)], out=out)
    for out in (F.n, -F.n):
        m.poly("awning", [p(x0, top - drop, depth), p(x1, top - drop, depth), p(x1, top - drop - 0.28, depth), p(x0, top - drop - 0.28, depth)], out=out)
    for u in (x0, x1):
        pts = [p(u, top, 0.05), p(u, top - drop, depth), p(u, top - drop - 0.12, depth)]
        m.poly("awning", pts, out=F.t)
        m.poly("awning", pts, out=-F.t)
    F.box("iron", x0, x1, top - drop - 0.03, top - drop + 0.02, depth - 0.04, depth + 0.01, skip=())
    for u in (x0 + 0.05, x1 - 0.05):
        m.strut("iron", p(u, top - 0.6, 0.0), p(u, top - drop, depth - 0.03), 0.03)


# ---- models: pieces, bake, export -----------------------------------------------------


class Model:
    """A model under construction: solid, cut-out and decal meshes, faces tagged by piece.

    `piece(name, at)` starts a piece whose base sits at `at` (x, y, z) in the
    reference scene; geometry is drawn in reference coordinates and moved
    back by `at` on export.
    """

    def __init__(self, id_, seed=7):
        self.id = id_
        self.m = Mesh(id_)
        self.cut = Mesh(f"{id_}_cut")
        self.decal = Mesh(f"{id_}_decal")
        self.names, self.at = [], []
        self.R = random.Random(seed)
        # Angle above which edges are hard on export (None: as drawn).
        self.sharp = None

    def piece(self, name, at=(0, 0, 0)):
        self.m.part = self.cut.part = self.decal.part = len(self.names)
        self.names.append(f"{self.id}_{name}")
        self.at.append(Vector(at))
        WID[0] = 0

    def export(self, out, bake=True, size=2048, samples=96, smooth=0.0):
        ob, co = self.m.finish(self.sharp), self.cut.finish()
        tris = sum(len(p.vertices) - 2 for p in ob.data.polygons) + sum(len(p.vertices) - 2 for p in co.data.polygons)
        print(self.id, "triangles", tris, "pieces", len(self.names))
        bake_ao(ob, os.path.join(out, f"{self.id}_ao.png"), bake, size, samples, smooth)
        parts = split(ob, self.names, self.at, "") + split(co, self.names, self.at, "_cut")
        if self.decal.bm.faces:
            parts += split(self.decal.finish(), self.names, self.at, "_decal")
        for o in bpy.data.objects:
            o.select_set(o in parts)
        bpy.ops.export_scene.gltf(filepath=os.path.join(out, f"{self.id}.glb"), export_format="GLB", use_selection=True, export_yup=True, export_texcoords=True, export_normals=True, export_materials="EXPORT")
        for name, o in zip(self.names, parts):
            tris = sum(len(p.vertices) - 2 for p in o.data.polygons)
            print("  piece", name, "triangles", tris)


def split(ob, names, at, suffix):
    """One object per piece tag, moved so the piece's base is at the origin; empty pieces are skipped."""
    out = []
    for k, name in enumerate(names):
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        layer = bm.faces.layers.int["piece"]
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f[layer] != k], context="FACES")
        if not bm.faces:
            bm.free()
            continue
        bmesh.ops.translate(bm, verts=bm.verts, vec=-at[k])
        me = bpy.data.meshes.new(name + suffix)
        bm.to_mesh(me)
        bm.free()
        for mat in ob.data.materials:
            me.materials.append(mat)
        o = bpy.data.objects.new(name + suffix, me)
        bpy.context.scene.collection.objects.link(o)
        out.append(o)
    return out


def blur(px, size, sigma):
    """Separable Gaussian blur of a (size x size) array; islands' baked margins keep it from bleeding."""
    r = int(sigma * 3)
    k = np.exp(-0.5 * (np.arange(-r, r + 1) / sigma) ** 2)
    k /= k.sum()
    a = px.reshape(size, size)
    a = np.apply_along_axis(lambda v: np.convolve(np.pad(v, r, mode="edge"), k, "valid"), 0, a)
    a = np.apply_along_axis(lambda v: np.convolve(np.pad(v, r, mode="edge"), k, "valid"), 1, a)
    return a.ravel()


def bake_ao(ob, path, bake=True, size=2048, samples=96, smooth=0.0):
    """Lightmap UVs (UV1, "Light") over the whole model, and AO baked in Cycles onto them.

    `smooth` blurs the bake (sigma in pixels) to take out sampling noise,
    which shows on glossy props lit mostly by the sky.
    """
    me = ob.data
    light = me.uv_layers.new(name="Light")
    me.uv_layers.active = light
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(50), island_margin=0.0015, area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
    bpy.ops.object.mode_set(mode="OBJECT")
    me.uv_layers["UVMap"].active = True
    me.uv_layers["UVMap"].active_render = True
    if not bake:
        return
    sc = bpy.context.scene
    sc.render.engine = "CYCLES"
    sc.cycles.device = "CPU"
    sc.cycles.samples = samples
    sc.world = bpy.data.worlds.new("w")
    sc.world.light_settings.distance = 2.5
    img = bpy.data.images.new(os.path.basename(path), size, size, alpha=False)
    img.colorspace_settings.name = "Non-Color"
    for mat in me.materials:
        mat.use_nodes = True
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = img
        node.select = True
        mat.node_tree.nodes.active = node
    # Edit mode reallocates the layers: look them up again by name.
    me.uv_layers.active = me.uv_layers["Light"]
    me.uv_layers["Light"].active_render = True
    bpy.ops.mesh.primitive_plane_add(size=200, location=(0, 0, 0))
    ground = bpy.context.active_object
    ground.select_set(False)
    bpy.context.view_layer.objects.active = ob
    ob.select_set(True)
    sc.render.bake.margin = 8
    bpy.ops.object.bake(type="AO", use_clear=True)
    if smooth:
        px = np.array(img.pixels[:], np.float32).reshape(-1, 4)
        v = blur(px[:, 0], size, smooth)
        px[:, 0] = px[:, 1] = px[:, 2] = v
        img.pixels.foreach_set(px.ravel())
    img.filepath_raw = path
    img.file_format = "PNG"
    img.save()
    bpy.data.objects.remove(ground)
    me.uv_layers["UVMap"].active = True
    me.uv_layers["UVMap"].active_render = True
    px = np.array(img.pixels[:]).reshape(-1, 4)[:, 0]
    print("ao mean", round(float(px.mean()), 3), "dark", round(float((px < 0.2).mean()), 3))
    for mat in me.materials:
        nodes = mat.node_tree.nodes
        for n in [n for n in nodes if n.type == "TEX_IMAGE"]:
            nodes.remove(n)
    bpy.data.images.remove(img)


def reset():
    for ob in list(bpy.data.objects):
        bpy.data.objects.remove(ob)
    for me in list(bpy.data.meshes):
        bpy.data.meshes.remove(me)
