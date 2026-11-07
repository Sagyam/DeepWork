# Trees, bushes and hedges for the realistic city. Real sizes: street and garden trees are 5-12 m tall.
#
# Trunks and branches are tapered tubes grown recursively from a seed, down
# to a level of twigs and cut short at the crown's surface; the leaves are
# sprays (alpha-tested quads with a twig of leaves drawn on them) hung from
# the twig tips and the outer branches by their stems, so every cluster is
# carried by wood. The app bends the cards' normals out from the crown's
# middle and thins cards seen edge-on (real.ts), so a crown shades like one
# soft mass instead of a heap of flat cards.
#
# Pieces (base at the origin):
#   oak, maple, linden, birch, cherry, spruce, pine, poplar, young   trees
#   bush, bush_wide, shrub, flowers                                 shrubs
#   hedge   a 2 m segment (x), 0.7 m deep, 1.25 m tall, stretched by the app
# Roles: bark, birch, leaf (broad leaves), smallleaf (birch), needles,
# blossom (cherry), bloom (flowering shrub), hedge (the hedge's dense core);
# woods and firs for the woods' light trees (forest_a-e).
import math
import random

import numpy as np

from lib import Model, Vector, fbm, normals, srgb

ID = "trees"


# ---- textures ------------------------------------------------------------------------


def _leaf_canvas(n, count, size, aspect, palette, seed, kind="broad", twigs=8, spread=0.47, flowers=None):
    """A cluster of leaves on twigs, on a transparent n x n card; returns (rgb, alpha, height)."""
    rng = np.random.default_rng(seed)
    col = np.zeros((n, n, 3), np.float32)
    alpha = np.zeros((n, n), np.float32)
    h = np.zeros((n, n), np.float32)
    c = n / 2
    # Twigs from the bottom middle, fanning out.
    stems = []
    for i in range(twigs):
        a = math.pi / 2 + (i / max(1, twigs - 1) - 0.5) * 2.4 + rng.normal(0, 0.12)
        L = n * spread * (0.75 + 0.3 * rng.random())
        x0, y0 = c + rng.normal(0, n * 0.02), n * 0.97
        x1, y1 = c + math.cos(a) * L, n * 0.97 - math.sin(a) * L
        stems.append((x0, y0, x1, y1))
        _segment(col, alpha, h, x0, y0, x1, y1, max(1.5, n / 400), srgb(92, 74, 58))
    for k in range(count):
        # Leaves sit along the twigs and fill the space between them.
        if rng.random() < 0.7:
            x0, y0, x1, y1 = stems[rng.integers(len(stems))]
            t = 0.15 + 0.85 * rng.random() ** 0.45
            px, py = x0 + (x1 - x0) * t, y0 + (y1 - y0) * t
            px += rng.normal(0, n * 0.03)
            py += rng.normal(0, n * 0.03)
        else:
            r = n * spread * math.sqrt(rng.random())
            a = rng.random() * math.tau
            px, py = c + math.cos(a) * r, c + math.sin(a) * r * 0.95
        ang = rng.random() * math.tau
        L = n * size * (0.7 + 0.6 * rng.random())
        base = palette[rng.integers(len(palette))] * (0.8 + 0.4 * rng.random())
        if flowers is not None and rng.random() < flowers[1]:
            base = flowers[0][rng.integers(len(flowers[0]))] * (0.85 + 0.3 * rng.random())
            _petals(col, alpha, h, px, py, L * 0.55, base, rng)
            continue
        _leaf(col, alpha, h, px, py, ang, L, aspect, base, kind, rng)
    return col, alpha, h


def _patch(n, x, y, r):
    x0, x1 = max(0, int(x - r - 2)), min(n, int(x + r + 3))
    y0, y1 = max(0, int(y - r - 2)), min(n, int(y + r + 3))
    if x1 <= x0 or y1 <= y0:
        return None
    yy, xx = np.mgrid[y0:y1, x0:x1].astype(np.float32)
    return (slice(y0, y1), slice(x0, x1)), xx, yy


def _segment(col, alpha, h, x0, y0, x1, y1, w, rgb):
    n = col.shape[0]
    p = _patch(n, (x0 + x1) / 2, (y0 + y1) / 2, math.hypot(x1 - x0, y1 - y0) / 2 + w)
    if p is None:
        return
    sl, xx, yy = p
    dx, dy = x1 - x0, y1 - y0
    t = np.clip(((xx - x0) * dx + (yy - y0) * dy) / max(1e-6, dx * dx + dy * dy), 0, 1)
    d = np.hypot(xx - (x0 + dx * t), yy - (y0 + dy * t))
    ww = w * (1.4 - 0.8 * t)
    m = d < ww
    col[sl][m] = rgb
    alpha[sl][m] = 1
    h[sl][m] = 0.3


def _leaf(col, alpha, h, px, py, ang, L, aspect, rgb, kind, rng):
    n = col.shape[0]
    p = _patch(n, px, py, L)
    if p is None:
        return
    sl, xx, yy = p
    ca, sa = math.cos(ang), math.sin(ang)
    # Leaf frame: u from the stalk (0) to the tip (1), v across.
    u = ((xx - px) * ca + (yy - py) * sa) / L
    v = (-(xx - px) * sa + (yy - py) * ca) / L
    if kind == "needle":
        m = (u > 0) & (u < 1) & (np.abs(v) < 0.06 * (1 - u * 0.5))
        shade = 1.0 - 0.15 * u
    else:
        half = aspect * 0.5 * np.sin(np.clip(u, 0, 1) * math.pi) ** 0.8 * (1 - 0.25 * u)
        if kind == "lobed":
            half = half * (0.75 + 0.25 * np.cos(np.clip(u, 0, 1) * math.pi * 7))
        m = (u > 0) & (u < 1) & (np.abs(v) < half)
        # Light from one side of the midrib, a darker rib and edge.
        side = np.where(v > 0, 1.06, 0.9)
        rib = 1 - 0.25 * np.exp(-(v / 0.012) ** 2)
        edge = 1 - 0.2 * np.clip(np.abs(v) / np.maximum(half, 1e-4) - 0.7, 0, 1) / 0.3
        shade = side * rib * edge
    if not m.any():
        return
    tone = (shade * (0.95 + 0.1 * rng.random()))[..., None]
    cc = col[sl]
    cc[m] = (rgb[None, None, :] * tone)[m]
    col[sl] = cc
    alpha[sl][m] = 1
    hh = h[sl]
    hh[m] = (0.6 + 0.4 * np.sin(np.clip(u, 0, 1) * math.pi))[m]
    h[sl] = hh


def _petals(col, alpha, h, px, py, r, rgb, rng):
    """A five-petalled blossom."""
    n = col.shape[0]
    p = _patch(n, px, py, r)
    if p is None:
        return
    sl, xx, yy = p
    a = np.arctan2(yy - py, xx - px) + rng.random() * 6
    d = np.hypot(xx - px, yy - py) / r
    m = d < (0.55 + 0.45 * np.abs(np.cos(a * 2.5)))
    core = d < 0.18
    cc = col[sl]
    cc[m] = rgb * (1 - 0.25 * d[m])[:, None]
    cc[core] = srgb(230, 200, 120)
    col[sl] = cc
    alpha[sl][m] = 1
    h[sl][m] = 0.7


def leaf_textures(t):
    """Leaf-cluster cards: broad leaves, small (birch) leaves, needles, cherry blossom, a flowering shrub."""
    greens = [srgb(150, 172, 104), srgb(132, 160, 92), srgb(168, 184, 116), srgb(120, 146, 84), srgb(176, 190, 128)]
    sets = {
        "leaf": dict(count=720, size=0.075, aspect=0.55, palette=greens, seed=1, kind="broad"),
        "smallleaf": dict(count=760, size=0.05, aspect=0.62, palette=greens, seed=2, kind="broad", twigs=10),
        "needles": dict(count=3000, size=0.07, aspect=0.1, palette=[srgb(98, 124, 92), srgb(84, 112, 84), srgb(110, 134, 98)], seed=3, kind="needle", twigs=7, spread=0.48),
        "blossom": dict(count=900, size=0.045, aspect=0.55, palette=greens[:2], seed=4, flowers=([srgb(246, 196, 214), srgb(240, 170, 196), srgb(252, 222, 232)], 0.82)),
        "bloom": dict(count=700, size=0.06, aspect=0.55, palette=greens, seed=5, flowers=([srgb(238, 236, 244), srgb(196, 170, 232), srgb(150, 170, 236)], 0.35)),
    }
    for name, kw in sets.items():
        col, alpha, h = _leaf_canvas(512, **kw)
        # Fill the transparent pixels with the leaves' mean colour, so mipmaps
        # do not darken the cards' edges.
        mean = col[alpha > 0.5].mean(axis=0)
        col[alpha < 0.5] = mean
        t.save(f"{name}_col", col, alpha)
        t.save(f"{name}_nrm", normals(h, 3.0))


def bark_tex(t, n=512):
    """Furrowed bark (tile 1 x 2 m) and birch bark, white with black lenticels and scars (tile 1 x 1 m)."""
    furrow = fbm(n, 4, 5, 61, stretch=(6, 1))
    fine = fbm(n, 16, 4, 62, stretch=(4, 1))
    ridges = np.clip((furrow - 0.35) / 0.3, 0, 1)
    col = srgb(98, 86, 74) * (0.55 + 0.45 * ridges + 0.15 * (fine - 0.5))[..., None]
    t.save("bark_col", col)
    t.save("bark_nrm", normals(ridges * 0.8 + 0.2 * fine, 5.0))
    rng = np.random.default_rng(63)
    base = srgb(226, 222, 212) * (0.9 + 0.12 * fbm(n, 8, 4, 64))[..., None]
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    marks = np.zeros((n, n), bool)
    for _ in range(140):
        cx, cy = rng.random() * n, rng.random() * n
        w, hh = n * (0.02 + 0.08 * rng.random()), n * (0.003 + 0.008 * rng.random())
        dx = np.minimum(np.abs(x - cx), n - np.abs(x - cx))
        dy = np.minimum(np.abs(y - cy), n - np.abs(y - cy))
        marks |= (dx / w) ** 2 + (dy / hh) ** 2 < 1
    blotch = fbm(n, 4, 4, 65) > 0.68
    base[marks] = srgb(40, 36, 34)
    base[blotch] *= 0.55
    t.save("birch_col", base)


def hedge_tex(t, n=1024):
    """A dense clipped hedge face, opaque small leaves (tile 1.5 m)."""
    greens = [srgb(134, 160, 96), srgb(120, 148, 86), srgb(150, 172, 104), srgb(108, 136, 78)]
    rng = np.random.default_rng(71)
    col = np.zeros((n, n, 3), np.float32) + srgb(52, 70, 40)
    alpha = np.zeros((n, n), np.float32)
    h = np.zeros((n, n), np.float32)
    for _ in range(5200):
        px, py = rng.random() * n, rng.random() * n
        _leaf(col, alpha, h, px, py, rng.random() * math.tau, n * 0.022 * (0.7 + 0.6 * rng.random()), 0.6, greens[rng.integers(4)] * (0.75 + 0.45 * rng.random()), "broad", rng)
    # Wrap: the leaves were drawn without wrapping, so blend the borders.
    t.save("hedge_col", col)
    t.save("hedge_nrm", normals(h, 4.0))


def grass_tex(t, n=1024):
    """Mown lawn with clover and worn patches: tile 2 m."""
    blades = fbm(n, 128, 2, 81, stretch=(2, 1))
    clump = fbm(n, 16, 5, 82)
    worn = fbm(n, 4, 4, 83)
    col = srgb(92, 128, 60) * (0.7 + 0.45 * blades + 0.25 * (clump - 0.5))[..., None]
    dry = np.clip((worn - 0.6) / 0.2, 0, 1)[..., None]
    col = col * (1 - dry * 0.5) + srgb(140, 138, 86) * dry * 0.5
    clover = fbm(n, 64, 3, 84) > 0.74
    col[clover] = col[clover] * 0.8 + srgb(70, 120, 60) * 0.2
    t.save("grass_col", col)
    t.save("grass_nrm", normals(blades * 0.6 + clump * 0.4, 2.5))


def canopy_textures(t):
    """Cards for the woods, seen from afar: the leaves' gaps filled with shade,
    so mipmaps keep the cards solid instead of thinning them away."""
    from lib import blur

    greens = [srgb(150, 172, 104), srgb(132, 160, 92), srgb(168, 184, 116), srgb(120, 146, 84)]
    sets = {
        "woods": dict(count=1500, size=0.06, aspect=0.55, palette=greens, seed=11, kind="broad", twigs=12),
        "firs": dict(count=3800, size=0.07, aspect=0.1, palette=[srgb(98, 124, 92), srgb(84, 112, 84), srgb(110, 134, 98)], seed=12, kind="needle", twigs=9),
    }
    n = 512
    for name, kw in sets.items():
        col, alpha, h = _leaf_canvas(n, **kw)
        solid = blur(alpha.ravel(), n, 7.0).reshape(n, n) > 0.3
        mean = col[alpha > 0.5].mean(axis=0)
        gap = solid & (alpha < 0.5)
        col[gap] = mean * 0.45
        col[~solid] = mean * 0.6
        t.save(f"{name}_col", col, solid.astype(np.float32))


TEXTURES = (leaf_textures, canopy_textures, bark_tex, hedge_tex, grass_tex)


# ---- geometry ------------------------------------------------------------------------


class Shift:
    """Draws into a Mesh with every point moved by `off`."""

    def __init__(self, m, off):
        self.m, self.off = m, Vector(off)

    def poly(self, role, pts, out=None, uvs=None, smooth=False):
        return self.m.poly(role, [tuple(Vector(p) + self.off) for p in pts], out=out, uvs=uvs, smooth=smooth)


def tube(m, role, a, b, r0, r1, seg=6, cap=False, v0=0.0):
    """A tapered round bar from a to b; UVs in metres round and along it (bark tiles)."""
    a, b = Vector(a), Vector(b)
    ax = b - a
    L = ax.length
    if L < 1e-4:
        return
    ax.normalize()
    p1 = ax.cross(Vector((0, 0, 1))) if abs(ax.z) < 0.99 else Vector((1, 0, 0))
    p1.normalize()
    p2 = ax.cross(p1)
    ring = lambda c, r: [c + (p1 * math.cos(i / seg * math.tau) + p2 * math.sin(i / seg * math.tau)) * r for i in range(seg)]  # noqa: E731
    ra, rb = ring(a, r0), ring(b, r1)
    circ = math.tau * (r0 + r1) / 2
    for i in range(seg):
        j = (i + 1) % seg
        u0, u1 = i / seg * circ, (i + 1) / seg * circ
        mid = (ra[i] + ra[j]) / 2 - a
        m.poly(role, [ra[i], ra[j], rb[j], rb[i]], out=mid, uvs=[(u0, v0), (u1, v0), (u1, v0 + L), (u0, v0 + L)], smooth=True)
    if cap:
        m.poly(role, rb, out=ax)


def card(m, role, c, size, nrm, rng, stretch=1.0):
    """A leaf card centred at c facing about `nrm`, turned at random about it."""
    n = Vector(nrm).normalized()
    t = n.orthogonal().normalized()
    t.rotate(_rot(n, rng.random() * math.tau))
    b = n.cross(t).normalized()
    hx, hy = size / 2, size / 2 * stretch
    c = Vector(c)
    pts = [c - t * hx - b * hy, c + t * hx - b * hy, c + t * hx + b * hy, c - t * hx + b * hy]
    m.poly(role, pts, out=n, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])


def _rot(axis, ang):
    from mathutils import Quaternion

    return Quaternion(axis, ang)


def _turn(d, rng, spread, up=0.0):
    """Direction d tilted by about `spread` radians toward a random side, nudged up by `up`."""
    d = Vector(d).normalized()
    side = d.orthogonal().normalized()
    side.rotate(_rot(d, rng.random() * math.tau))
    out = (d * math.cos(spread) + side * math.sin(spread) + Vector((0, 0, up))).normalized()
    return out


def _inside(env, q, margin=1.0):
    """How far point q is out along the crown's ellipsoid `env` (centre, rx, rz): 1 on its surface."""
    c, rx, rz = env
    q = q - c
    return math.sqrt((q.x / rx) ** 2 + (q.y / rx) ** 2 + (q.z / rz) ** 2) / margin


def grow(m, role, rng, p, d, L, r, depth, tips, spread=0.6, up=0.25, kids=(2, 3), seg=6, v0=0.0, segs=None, env=None):
    """A branch from p along d, and its children; branch ends go in `tips`, the outer branches in `segs`.

    With `env` (the crown's ellipsoid) a branch that would end outside the
    crown is cut short at its surface, so no bare stick pokes out of the leaves."""
    p = Vector(p)
    end = p + d * L
    if env is not None and _inside(env, end, 0.92) > 1:
        lo, hi = 0.0, 1.0
        for _ in range(8):
            mid = (lo + hi) / 2
            lo, hi = (mid, hi) if _inside(env, p + d * L * mid, 0.92) <= 1 else (lo, mid)
        L = max(L * lo, min(L, 0.25))
        end = p + d * L
    tube(m, role, p, end, r, r * 0.68, seg=max(3, seg), v0=v0)
    if segs is not None and depth <= 1:
        segs.append((p, end))
    if depth == 0:
        tips.append((end, d))
        return
    n = rng.randint(*kids)
    for k in range(n):
        t = 0.55 + 0.45 * (k + rng.random()) / n
        start = p + d * L * t
        dd = _turn(d, rng, spread * (0.7 + 0.6 * rng.random()), up)
        grow(m, role, rng, start, dd, L * (0.62 + 0.15 * rng.random()), r * 0.62 * (1.1 - 0.3 * t), depth - 1, tips, spread, up, kids, seg - 1, v0 + L * t, segs, env)
    # The leader carries on.
    grow(m, role, rng, end, _turn(d, rng, spread * 0.35, up * 0.5), L * 0.7, r * 0.66, depth - 1, tips, spread, up, kids, seg - 1, v0 + L, segs, env)


def crown(m, role, rng, centre, rx, rz, count, size, tips=(), shell=0.65, droop=0.0, flat_top=False):
    """Leaf cards through an ellipsoid crown, most near its surface, a card on every branch tip."""
    centre = Vector(centre)
    placed = 0
    for tip, d in tips:
        q = (tip - centre)
        nrm = q.normalized() if q.length > 1e-3 else Vector((0, 0, 1))
        card(m, role, tip + d * size * 0.3, size * (0.8 + 0.4 * rng.random()), nrm + Vector((0, 0, 0.3)), rng)
        placed += 1
    while placed < count:
        # A random direction, at a radius biased to the shell.
        z = rng.uniform(-1, 1)
        a = rng.random() * math.tau
        s = math.sqrt(1 - z * z)
        u = Vector((s * math.cos(a), s * math.sin(a), z))
        if flat_top and u.z > 0.55:
            u.z = 0.55 + (u.z - 0.55) * 0.4
        rr = shell + (1 - shell) * rng.random() ** 0.5
        q = Vector((u.x * rx * rr, u.y * rx * rr, u.z * rz * rr))
        nrm = Vector((u.x / rx, u.y / rx, u.z / rz)).normalized() + Vector((0, 0, 0.25 - droop))
        card(m, role, centre + q, size * (0.75 + 0.5 * rng.random()), nrm, rng)
        placed += 1


def spray(m, role, base, a, size, face, rng, width=1.0):
    """A leaf card whose stem end (the texture's bottom middle, where its
    twigs start) sits on a twig at `base`, reaching out along `a`, its face
    turned toward `face` as far as it can be while containing `a`."""
    a = Vector(a).normalized()
    f = Vector(face) - a * Vector(face).dot(a)
    if f.length < 1e-3:
        f = a.orthogonal()
    f.normalize()
    side = a.cross(f).normalized()
    hx = size / 2 * width
    b = Vector(base) - a * size * 0.06
    top = b + a * size
    m.poly(role, [b - side * hx, b + side * hx, top + side * hx, top - side * hx], out=f, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])


def sprays(m, role, rng, tips, segs, per_tip, size, centre, droop=0.25, along=0.35, up=0.6, lo=0.35):
    """Leaves on the twigs: sprays fanned out from every twig tip, and some
    along the outer branches, each held at its stem by the wood. Sprays face
    out of the crown and up a little, turned at random about their stems,
    so the crown reads as a mass of leafy twigs, not cards in mid-air."""
    centre = Vector(centre)

    def put(p, d):
        out = p - centre
        out = out.normalized() if out.length > 1e-3 else Vector((0, 0, 1))
        a = (d * 0.8 + out * 0.5 + _turn(d, rng, 1.0) * 0.5 + Vector((0, 0, -droop))).normalized()
        face = (out + Vector((0, 0, up))).normalized()
        face.rotate(_rot(a, rng.uniform(-1.0, 1.0)))
        spray(m, role, p, a, size * (0.75 + 0.5 * rng.random()), face, rng)

    for tip, d in tips:
        for _ in range(per_tip):
            put(tip - d * size * 0.35 * rng.random(), d)
    for _ in range(int(len(tips) * per_tip * along)):
        if not segs:
            break
        a0, a1 = segs[rng.randrange(len(segs))]
        put(a0 + (a1 - a0) * rng.uniform(lo, 1.0), (a1 - a0).normalized())


def ellipsoid(m, role, centre, rx, rz, seg=10, rings=6, rough=0.0, rng=None):
    """A closed ellipsoid (a bush's dark core), slightly lumpy."""
    c = Vector(centre)
    pts = []
    for i in range(rings + 1):
        th = math.pi * i / rings
        row = []
        for j in range(seg):
            ph = math.tau * j / seg
            k = 1 + (rough * (rng.random() - 0.5) if rng and 0 < i < rings else 0)
            row.append(c + Vector((math.sin(th) * math.cos(ph) * rx * k, math.sin(th) * math.sin(ph) * rx * k, math.cos(th) * rz * k)))
        pts.append(row)
    for i in range(rings):
        for j in range(seg):
            jj = (j + 1) % seg
            quad = [pts[i][j], pts[i + 1][j], pts[i + 1][jj], pts[i][jj]]
            mid = sum(quad, Vector()) / 4 - c
            if i == 0:
                m.poly(role, [pts[0][0], pts[1][j], pts[1][jj]], out=mid, smooth=True)
            elif i == rings - 1:
                m.poly(role, [pts[i][j], pts[rings][0], pts[i][jj]], out=mid, smooth=True)
            else:
                m.poly(role, quad, out=mid, smooth=True)


# ---- species ------------------------------------------------------------------------


def broadleaf(m, rng, height, clear, crown_r, limbs, depth, cards, size, role="leaf", bark="bark", trunk_r=0.2, spread=0.65, up=0.3, lean=0.0, reach=None, flat_top=False):
    """A deciduous tree: a trunk to `clear`, limbs fanning up and out to a
    level of twigs inside the crown, and leaf sprays hung from the twigs
    (about `cards` of them, each about `size` m long)."""
    tips, segs = [], []
    top = Vector((lean, 0, clear))
    rz = (height - clear) / 2
    cz = clear + rz
    centre = Vector((lean, 0, cz + (rz * 0.05 if flat_top else 0)))
    env = (centre, crown_r, rz * (0.9 if flat_top else 1.05))
    # A root flare, then the trunk.
    tube(m, bark, (0, 0, 0), (lean * 0.05, 0, 0.35), trunk_r * 1.35, trunk_r, seg=9)
    tube(m, bark, (lean * 0.05, 0, 0.35), top, trunk_r, trunk_r * 0.85, seg=9)
    for k in range(limbs):
        a = k / limbs * math.tau + rng.random() * 0.6
        out = (0.75 if flat_top else 0.55) + 0.25 * rng.random()
        d = Vector((math.cos(a) * out, math.sin(a) * out, 1.0)).normalized()
        L = rz * (0.62 + 0.2 * rng.random()) * (crown_r / rz) ** 0.35
        grow(m, bark, rng, top - Vector((0, 0, 0.12 * k)), d, L, trunk_r * 0.6, depth + 1, tips, spread, up, kids=(2, 3), seg=6, segs=segs, env=env)
    grow(m, bark, rng, top, Vector((0, 0, 1)), rz * 0.6, trunk_r * 0.6, depth + 1, tips, spread * 0.8, up, kids=(2, 3), seg=6, segs=segs, env=env)
    # Smaller sprays than the old scattered cards, so about twice as many,
    # three in five on the twig tips and the rest along the outer branches.
    total = cards * 1.9
    per_tip = max(2, round(total * 0.6 / max(1, len(tips))))
    sprays(m, role, rng, tips, segs, per_tip, size * 0.72, centre, along=total * 0.4 / max(1, len(tips) * per_tip))


def spruce(m, rng, height, radius, whorls, role="needles"):
    """A conifer: one straight trunk, drooping whorls of branches shortening to the top."""
    tube(m, "bark", (0, 0, 0), (0, 0, height * 0.92), 0.22, 0.04, seg=7)
    z0 = height * 0.12
    for w in range(whorls):
        f = w / whorls
        z = z0 + (height * 0.93 - z0) * f
        R = radius * (1 - f) ** 0.95 + 0.25
        n = 6 if f < 0.7 else 5
        for k in range(n):
            a = k / n * math.tau + w * 0.9 + rng.random() * 0.4
            d = Vector((math.cos(a), math.sin(a), 0.1 - 0.35 * (1 - f))).normalized()
            p = Vector((0, 0, z))
            end = p + d * R
            tube(m, "bark", p, end, 0.05 * (1 - f) + 0.015, 0.012, seg=3)
            # Side shoots in a herringbone along the branch, each a small
            # needle spray drooping from it, and one on its tip: the branch
            # holds every spray, so the whorls read as boughs, not sheets.
            side = d.cross(Vector((0, 0, 1))).normalized()
            step = 0.38
            j = 0
            t = 0.3
            while t * R < R - 0.15:
                q = p + d * R * t
                s_ = 1 if j % 2 == 0 else -1
                a_ = (d * 0.75 + side * s_ * 0.65 + Vector((0, 0, -0.25 - 0.2 * t))).normalized()
                L = (0.35 + 0.55 * (1 - t)) * min(1.0, R / 1.6) + 0.2
                # Faces up and out, so the bough is seen as a mass of
                # needles from the side as well as from above.
                face = Vector((0, 0, 0.7)) + d * 0.6 - side * s_ * 0.2
                spray(m, role, q, a_, L, face, rng, width=0.95)
                if j % 2 == 0:
                    hang = (a_ + Vector((0, 0, -0.6))).normalized()
                    spray(m, role, q + Vector((0, 0, -0.04)), hang, L * 0.8, d + Vector((0, 0, 0.3)), rng, width=0.85)
                t += step / max(R, 0.5)
                j += 1
            spray(m, role, end - d * 0.1, (d + Vector((0, 0, -0.25))).normalized(), 0.55 + 0.2 * min(1.0, R / 2), Vector((0, 0, 1)), rng, width=0.85)
    # The leader.
    card(m, role, (0, 0, height * 0.97), 0.7, (0.6, 0.2, 0.2), rng)
    card(m, role, (0, 0, height * 0.97), 0.7, (-0.2, 0.6, 0.2), rng)


def pine(m, rng, height):
    """A Scots pine: a tall bare trunk leaning a little, an irregular crown of needle clumps."""
    tips, segs = [], []
    top = Vector((0.4, 0.1, height * 0.58))
    tube(m, "bark", (0, 0, 0), top, 0.24, 0.16, seg=7)
    for k in range(6):
        a = k / 6 * math.tau + rng.random()
        d = Vector((math.cos(a) * 0.8, math.sin(a) * 0.8, 0.8)).normalized()
        grow(m, "bark", rng, top - Vector((0, 0, 0.8 * k / 6)), d, 1.5 + rng.random() * 0.8, 0.1, 3, tips, 0.55, 0.45, kids=(1, 2), seg=4, segs=segs)
    grow(m, "bark", rng, top, Vector((0, 0, 1)), 1.8, 0.12, 3, tips, 0.5, 0.3, kids=(1, 2), seg=4, segs=segs)
    # Pine needles stand up in tufts at the shoot ends.
    sprays(m, "needles", rng, tips, segs, 6, 0.8, (0.4, 0.1, height * 0.79), droop=-0.4, along=0.6, up=0.7)


def poplar(m, rng, height):
    """A Lombardy poplar: many near-upright limbs, a narrow column of leaves."""
    tips, segs = [], []
    env = (Vector((0, 0, height * 0.56)), 1.6, height * 0.45)
    tube(m, "bark", (0, 0, 0), (0, 0, 2.0), 0.2, 0.17, seg=7)
    for k in range(8):
        a = k / 8 * math.tau
        d = Vector((math.cos(a) * 0.18, math.sin(a) * 0.18, 1)).normalized()
        start = Vector((0, 0, 1.6 + k * 0.3))
        grow(m, "bark", rng, start, d, height * 0.26, 0.08, 3, tips, 0.3, 0.6, kids=(1, 2), seg=4, segs=segs, env=env)
        segs.append((start + d * 1.2, start + d * height * 0.6))
    sprays(m, "leaf", rng, tips, segs, 5, 0.62, env[0], droop=0.0, along=1.0, up=0.3)


def bush(m, rng, rx, rz, cards, size, role="leaf", flowers=False):
    """A shrub: a dark lumpy core so it never looks hollow, leaf cards round it."""
    ellipsoid(m, "hedge", (0, 0, rz * 0.85), rx * 0.82, rz * 0.82, seg=9, rings=5, rough=0.2, rng=rng)
    crown(m, role, rng, (0, 0, rz * 0.9), rx, rz, cards, size, shell=0.8)


def hedge(m, rng, L=2.0, D=0.7, H=1.25):
    """A clipped hedge segment along x: a rounded box of dense leaves, a ragged skin of cards."""
    r = 0.12
    prof = [(D / 2, 0.0), (D / 2, H - r), (D / 2 - r * 0.3, H - r * 0.3), (D / 2 - r, H), (-(D / 2 - r), H), (-(D / 2 - r * 0.3), H - r * 0.3), (-D / 2, H - r), (-D / 2, 0.0)]
    x0, x1 = -L / 2, L / 2
    for (y0, z0), (y1, z1) in zip(prof, prof[1:]):
        out = Vector((0, (y0 + y1) / 2, (z0 + z1) / 2 - H / 2))
        m.poly("hedge", [(x0, y0, z0), (x1, y0, z0), (x1, y1, z1), (x0, y1, z1)], out=out, smooth=True)
    for x, out in ((x0, (-1, 0, 0)), (x1, (1, 0, 0))):
        m.poly("hedge", [(x, y, z) for y, z in prof], out=out)
    # Shoots poking out of the clipped faces.
    for _ in range(70):
        side = rng.random()
        x = rng.uniform(x0 + 0.05, x1 - 0.05)
        if side < 0.35:
            c, n = (x, D / 2 + 0.02, rng.uniform(0.3, H - 0.1)), (0, 1, 0.2)
        elif side < 0.7:
            c, n = (x, -D / 2 - 0.02, rng.uniform(0.3, H - 0.1)), (0, -1, 0.2)
        else:
            c, n = (x, rng.uniform(-D / 2 + 0.1, D / 2 - 0.1), H + 0.02), (0, rng.uniform(-0.3, 0.3), 1)
        card(m, "leaf", c, rng.uniform(0.14, 0.24), n, rng)


def light_tree(m, rng, height, clear, crown_r, cards, size, limbs=3, rz_f=1.0, role="woods", trunk_r=0.2):
    """A cheap tree for the woods (a few dozen cards, bare limbs): drawn thousands of times."""
    top = Vector((0, 0, clear))
    if clear > 0:
        tube(m, "bark", (0, 0, 0), top, trunk_r, trunk_r * 0.7, seg=5)
    rz = (height - clear) / 2 * rz_f
    centre = Vector((0, 0, height - rz))
    env = (centre, crown_r, rz)
    tips, segs = [], []
    for k in range(limbs):
        a = k / limbs * math.tau + rng.random()
        end = centre + Vector((math.cos(a) * crown_r * 0.55, math.sin(a) * crown_r * 0.55, rz * 0.1))
        d = (end - top).normalized()
        # A limb and one fork of twigs, three-sided: cheap, but the leaves hang on wood.
        grow(m, "bark", rng, top, d, (end - top).length, trunk_r * 0.5, 1, tips, 0.6, 0.3, kids=(1, 2), seg=4, segs=segs, env=env)
    grow(m, "bark", rng, top, Vector((0, 0, 1)), rz * 1.3, trunk_r * 0.5, 1, tips, 0.5, 0.3, kids=(1, 2), seg=4, segs=segs, env=env)
    total = cards * 2.0
    per_tip = max(2, round(total * 0.5 / max(1, len(tips))))
    sprays(m, role, rng, tips, segs, per_tip, size * 0.85, centre, along=total * 0.5 / max(1, len(tips) * per_tip), lo=0.12, up=0.15, droop=0.1)


def light_conifer(m, rng, height, radius, whorls=8):
    """A cheap conifer for the woods: whorls of narrow drooping boughs, a cone."""
    tube(m, "bark", (0, 0, 0), (0, 0, height * 0.9), 0.17, 0.04, seg=4)
    for w in range(whorls):
        f = w / whorls
        z = height * (0.16 + 0.78 * f)
        R = radius * (1 - f) ** 0.9 + 0.25
        n = 5 if f < 0.6 else 4
        for k in range(n):
            a = k / n * math.tau + w * 0.7 + rng.random() * 0.3
            d = Vector((math.cos(a), math.sin(a), -0.55 - 0.3 * (1 - f))).normalized()
            # A narrow bough drooping steeply from the trunk, a skirt of
            # needles: it faces out more than up, so the side view (and the
            # impostors drawn from it) sees needles, not edges.
            roll = d.cross(Vector((0, 0, 1))).normalized() * rng.uniform(-0.6, 0.6)
            spray(m, "firs", (0, 0, z), d, R * 1.25, Vector((0, 0, 0.6)) + Vector((d.x, d.y, 0)) * 0.9 + roll, rng, width=0.75)
    spray(m, "firs", (0, 0, height * 0.86), (0.1, 0, 1), height * 0.16, (1, 0, 0.1), rng, width=0.45)
    spray(m, "firs", (0, 0, height * 0.86), (0, 0.1, 1), height * 0.16, (0, 1, 0.1), rng, width=0.45)


# Species: (piece, builder). Each draws at the origin; build() lays them out for the bake.
def _species():
    return [
        ("oak", lambda m, R: broadleaf(m, R, 10.5, 2.4, 4.6, 5, 2, 540, 1.15, trunk_r=0.34, spread=0.75, up=0.15, flat_top=True)),
        ("maple", lambda m, R: broadleaf(m, R, 9.0, 2.2, 3.6, 4, 2, 470, 1.05, trunk_r=0.26, spread=0.6, up=0.3)),
        ("linden", lambda m, R: broadleaf(m, R, 10.0, 2.8, 3.0, 4, 2, 440, 1.0, trunk_r=0.25, spread=0.5, up=0.4)),
        ("birch", lambda m, R: broadleaf(m, R, 9.5, 2.6, 2.3, 3, 2, 380, 0.85, role="smallleaf", bark="birch", trunk_r=0.15, spread=0.45, up=0.45, lean=0.2)),
        ("cherry", lambda m, R: broadleaf(m, R, 5.8, 1.5, 3.1, 5, 2, 420, 0.9, role="blossom", trunk_r=0.18, spread=0.8, up=0.15, flat_top=True)),
        ("spruce", lambda m, R: spruce(m, R, 11.0, 2.6, 17)),
        ("pine", lambda m, R: pine(m, R, 11.5)),
        ("poplar", lambda m, R: poplar(m, R, 13.0)),
        ("young", lambda m, R: broadleaf(m, R, 4.6, 1.8, 1.35, 3, 1, 150, 0.7, trunk_r=0.07, spread=0.5, up=0.4)),
        ("bush", lambda m, R: bush(m, R, 0.75, 0.6, 110, 0.34)),
        ("bush_wide", lambda m, R: bush(m, R, 1.1, 0.5, 140, 0.36)),
        ("shrub", lambda m, R: bush(m, R, 0.7, 1.0, 130, 0.36)),
        ("flowers", lambda m, R: bush(m, R, 0.65, 0.55, 110, 0.3, role="bloom")),
        ("hedge", lambda m, R: hedge(m, R)),
        # The woods: light trees at a base size land.ts scales per instance
        # (up to a tree, or a clump far out): broadleaf, conifer, rainforest
        # giant, undergrowth, and a far clump standing for several trees.
        ("forest_a", lambda m, R: light_tree(m, R, 5.0, 1.6, 1.8, 44, 1.1)),
        ("forest_b", lambda m, R: light_conifer(m, R, 5.6, 1.7)),
        ("forest_c", lambda m, R: light_tree(m, R, 9.0, 6.8, 2.6, 44, 1.3, limbs=4, rz_f=0.55, trunk_r=0.3)),
        ("forest_d", lambda m, R: light_tree(m, R, 2.6, 0.4, 1.5, 34, 1.0, limbs=2, trunk_r=0.12)),
        ("forest_e", lambda m, R: light_tree(m, R, 3.1, 0.0, 1.8, 36, 1.3, limbs=3)),
    ]


def build(out, bake=True):
    M = Model(ID)
    x = 0.0
    for i, (name, make) in enumerate(_species()):
        M.piece(name, (x, 0, 0))
        make(Shift(M.m, (x, 0, 0)), random.Random(100 + i))
        x += 12.0
    M.export(out, bake, size=2048, samples=96, smooth=1.5)
