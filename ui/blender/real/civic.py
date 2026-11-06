# Civic props for the realistic city: what the kit still drew in low poly
# round the buildings. The water tower (the Hamlet's water need), the tower
# crane and scaffolding of construction sites, the rubble of a destroyed
# lot, the parks' fountain, bandstand, goals and stand, and the people.
#
# Pieces (base at the origin, Blender z up; the app's +z is -y here):
#   water_tower    an elevated steel tank on four battered legs, 20.6 m
#   crane_base, crane_mast, crane_slew, crane_jib, crane_jib_tip,
#   crane_counter, crane_trolley, crane_hook, crane_load
#                  the kit's tower crane at the kit's sizes, so its anchors
#                  (apex, beacon, end) still hold: the app takes them from
#                  the kit and the geometry from here
#   scaffold       one bay of tube-and-fitting scaffold, 2.4 m along x, one
#                  2 m lift tall (the app stretches it to a storey), deck at
#                  its foot; inner standards at y = 0.65, outer at y = -0.15
#   rubble_heap    a mound of broken masonry, 5 m radius, 2.5 m high
#   rubble_wall    a broken brick wall, 3.2 m long, standing on its foot
#   rubble_slab    a broken floor slab with its rebar out, 2.6 x 1.8 m
#   rubble_beam    a steel I-beam bent in the fire, 4.6 m
#   fountain, bandstand, goal, bleachers   the parks' pieces, kit sizes
#   person         a pedestrian, 1.75 m (roles skin, hair, shirt, pants:
#                  the app colours each one)
# Roles: tankpaint, tankband, crane, scaffboard, char, galv, dark, grate, concrete, trim, carglass,
# wood, brick, rubble, iron, steel, stone, water (animated by the app),
# spray (falling water), zinc, castiron, debris (dusty broken concrete), lead, paint, brass, deck, chair, corrugated, net (cut-out), skin, hair,
# shirt, pants.
import math
import random

import numpy as np

from lib import Model, Vector, fbm, normals, srgb

ID = "civic"
Z = Vector((0, 0, 1))


# ---- textures ------------------------------------------------------------------------


def rubble_tex(t, n=1024):
    """Crushed masonry: brick shards, concrete lumps and dust (tile 3 m)."""
    rng = np.random.default_rng(91)
    dust = fbm(n, 8, 5, 92)
    col = srgb(110, 106, 100) * (0.75 + 0.4 * dust)[..., None]
    h = dust * 0.3
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    # Mostly grey concrete and mortar, brick dulled by dust, a little soot.
    palette = [srgb(128, 84, 70), srgb(116, 78, 66), srgb(140, 136, 128), srgb(124, 120, 114), srgb(150, 146, 140), srgb(104, 98, 92), srgb(60, 56, 52)]
    for _ in range(5200):
        cx, cy = rng.random() * n, rng.random() * n
        r = n * (0.002 + 0.009 * rng.random() ** 2.5)
        a = rng.random() * math.pi
        ca, sa = math.cos(a), math.sin(a)
        x0, x1 = int(max(0, cx - r * 1.6)), int(min(n, cx + r * 1.6 + 1))
        y0, y1 = int(max(0, cy - r * 1.6)), int(min(n, cy + r * 1.6 + 1))
        if x1 <= x0 or y1 <= y0:
            continue
        xx, yy = x[y0:y1, x0:x1] - cx, y[y0:y1, x0:x1] - cy
        u, v = (xx * ca + yy * sa) / r, (-xx * sa + yy * ca) / (r * (0.5 + rng.random() * 0.5))
        # An angular shard: a squashed diamond with a ragged edge.
        m = (np.abs(u) + np.abs(v)) < 1.0 + 0.25 * np.sin(u * 7 + v * 5)
        c = palette[rng.integers(len(palette))] * (0.8 + 0.3 * rng.random())
        c = c * 0.75 + col[int(cy) % n, int(cx) % n] * 0.25
        shade = (1.0 - 0.15 * np.clip(u, -1, 1))[..., None]
        sub = col[y0:y1, x0:x1]
        sub[m] = (c * shade)[m]
        hs = h[y0:y1, x0:x1]
        hs[m] = np.maximum(hs[m], 0.5 + 0.5 * (1 - (np.abs(u) + np.abs(v)))[m])
    t.save("rubble_col", col)
    t.save("rubble_nrm", normals(h, 6.0))


def net_tex(t, n=256):
    """Goal netting: white cord in a 12 cm square mesh, knotted; the rest clear (tile 1 m)."""
    col = np.zeros((n, n, 3), np.float32) + srgb(236, 236, 230)
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    cell = n / 6
    dx = np.abs(((x + cell / 2) % cell) - cell / 2)
    dy = np.abs(((y + cell / 2) % cell) - cell / 2)
    alpha = ((dx < 3.5) | (dy < 3.5) | ((dx < 6) & (dy < 6))).astype(np.float32)
    t.save("net_col", col, alpha)


def paintsteel_tex(t, n=1024):
    """Painted steel out in the weather for years (tile 2 m, row 0 up): near
    white, so the app tints it (tank silver, crane yellow). Chalky fading in
    blotches, dirt run down by the rain, chips to the dark primer and rust
    spots that bleed long orange streaks down the plate."""
    rng = np.random.default_rng(301)
    big = fbm(n, 3, 5, 302)
    mid = fbm(n, 12, 4, 303)
    peel = fbm(n, 24, 4, 304)
    rain = fbm(n, 6, 5, 305, stretch=(6, 0.5))
    col = np.ones((n, n, 3), np.float32) * srgb(226, 226, 220)
    col *= (0.88 + 0.16 * (big - 0.5) + 0.07 * (mid - 0.5))[..., None]
    # Rain carries grime down the plate in long vertical runs.
    dirt = np.clip((rain - 0.45) / 0.35, 0, 1) ** 1.5
    col *= (1 - 0.22 * dirt)[..., None]
    col = col * (1 - 0.12 * dirt[..., None]) + srgb(120, 108, 88) * 0.12 * dirt[..., None]
    # Chips to the primer, where the peel field peaks.
    chip = np.clip((peel - 0.76) / 0.04, 0, 1)
    col = col * (1 - chip[..., None]) + srgb(92, 74, 64) * chip[..., None]
    # Rust spots and their streaks: each spot bleeds straight down (rows grow downward).
    rust = np.zeros((n, n), np.float32)
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    for _ in range(26):
        cx, cy = rng.random() * n, rng.random() * n
        r = n * (0.002 + 0.006 * rng.random() ** 2)
        length = n * (0.05 + 0.35 * rng.random() ** 1.5)
        width = r * (0.6 + 0.8 * rng.random())
        dx = np.abs(((x - cx + n / 2) % n) - n / 2)
        dy = (y - cy) % n
        spot = np.exp(-((dx / r) ** 2 + (np.minimum(dy, n - dy) / r) ** 2))
        run = np.exp(-((dx / (width * (1 + dy / length * 1.5))) ** 2)) * np.clip(1 - dy / length, 0, 1) ** 1.3 * (dy < length)
        rust = np.maximum(rust, np.maximum(spot * 0.8, run * (0.25 + 0.35 * rng.random())))
    # Rust also gathers in broad faint patches where the paint has gone thin.
    rust = np.maximum(rust, np.clip((big - 0.62) / 0.2, 0, 1) * np.clip((mid - 0.4) / 0.3, 0, 1) * 0.45)
    rust = np.clip(rust * (0.7 + 0.6 * mid), 0, 1)
    rc = srgb(128, 66, 34) * (0.75 + 0.4 * peel)[..., None]
    col = col * (1 - 0.85 * rust[..., None]) + rc * 0.85 * rust[..., None]
    hgt = 0.04 * mid + 0.5 * np.clip(rust - 0.5, 0, 1) - 0.25 * chip
    t.save("paintsteel_col", col)
    t.save("paintsteel_nrm", normals(hgt, 5.0))
    t.save("paintsteel_rgh", np.clip(0.42 + 0.2 * dirt + 0.45 * rust + 0.25 * chip + 0.08 * (big - 0.5), 0, 1))


def zinc_tex(t, n=1024):
    """Standing-seam zinc, the bandstand's roof (tile 2 m, row 0 up): seams
    every 0.4 m running up the slope, a blue-grey patina mottled lighter and
    darker, pale run-off below the seams and dark dirt at the eaves."""
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    u, v = x / n * 2.0, 1.0 - y / n
    big = fbm(n, 3, 5, 311)
    mot = fbm(n, 16, 4, 312)
    rain = fbm(n, 10, 4, 313, stretch=(5, 0.5))
    ds = np.abs(((u + 0.2) % 0.4) - 0.2)
    seam = np.exp(-((ds / 0.008) ** 2))
    pan = np.clip(1 - ds / 0.2, 0, 1)
    col = np.ones((n, n, 3), np.float32) * srgb(150, 158, 162)
    col *= (0.86 + 0.18 * (big - 0.5) + 0.1 * (mot - 0.5))[..., None]
    # White zinc carbonate run-off and grey streaks down each pan.
    runs = np.clip((rain - 0.5) / 0.3, 0, 1)
    col = col * (1 - 0.25 * runs[..., None]) + srgb(206, 210, 208) * 0.25 * runs[..., None]
    col *= (1 - 0.1 * (1 - pan) * (1 - seam))[..., None]
    col *= (1.08 * seam + (1 - seam))[..., None]
    hgt = seam * 1.0 + 0.03 * mot
    t.save("zinc_col", col)
    t.save("zinc_nrm", normals(hgt, 8.0))


TEXTURES = (rubble_tex, net_tex, paintsteel_tex, zinc_tex)


# ---- helpers ------------------------------------------------------------------------


class Shift:
    """Draws into a Mesh with every point moved by `off` (the piece's place in the bake)."""

    def __init__(self, m, off):
        self.m, self.off = m, Vector(off)

    def _p(self, p):
        return tuple(Vector(p) + self.off)

    def poly(self, role, pts, out=None, uvs=None, smooth=False):
        return self.m.poly(role, [self._p(p) for p in pts], out=out, uvs=uvs, smooth=smooth)

    def box(self, role, lo, hi, skip=()):
        self.m.box(role, self._p(lo), self._p(hi), skip)

    def strut(self, role, a, b, t, t2=None):
        self.m.strut(role, self._p(a), self._p(b), t, t2)

    def tube(self, role, pts, r, up, closed=True, seg=6):
        self.m.tube(role, [self._p(p) for p in pts], r, up, closed=closed, seg=seg)


def rod(m, role, a, b, r, seg=8, caps=True):
    """A round bar from a to b."""
    a, b = Vector(a), Vector(b)
    ax = b - a
    if ax.length < 1e-5:
        return
    m.tube(role, [a, b], r, ax.normalized().orthogonal(), closed=False, seg=seg) if caps else _open_rod(m, role, a, b, r, seg)


def _open_rod(m, role, a, b, r, seg):
    ax = (b - a).normalized()
    u = ax.orthogonal().normalized()
    v = ax.cross(u)
    ring = lambda c: [c + (u * math.cos(k / seg * math.tau) + v * math.sin(k / seg * math.tau)) * r for k in range(seg)]  # noqa: E731
    ra, rb = ring(a), ring(b)
    for k in range(seg):
        j = (k + 1) % seg
        m.poly(role, [ra[k], ra[j], rb[j], rb[k]], out=(ra[k] + ra[j]) / 2 - a, smooth=True)


def hoop(m, role, c, R, r, seg=32, rseg=6, a0=0.0, a1=math.tau):
    """A round rail bent in a horizontal circle (or an arc from a0 to a1) round c."""
    c = Vector(c)
    closed = abs(a1 - a0 - math.tau) < 1e-6
    n = seg if closed else max(2, int(seg * (a1 - a0) / math.tau) + 1)
    pts = [c + Vector((math.cos(a0 + (a1 - a0) * i / (n if closed else n - 1)) * R, math.sin(a0 + (a1 - a0) * i / (n if closed else n - 1)) * R, 0)) for i in range(n)]
    m.tube(role, pts, r, Z, closed=closed, seg=rseg)


def lathe(m, role, prof, seg=32, c=(0, 0), z0=0.0, uv=True, smooth=True, ur=None, slant=False):
    """A surface of revolution about the vertical through c: `prof` is (r, z)
    from bottom to top, drawn as the outside (normals away from the axis
    where the profile rises). `ur` maps each face on its own: u in metres
    across it from its centre line (placed at radius ur), so lines along v
    run parallel within a facet and meet the hips, as roof pans do; `slant`
    maps v along the profile (metres up the slope) instead of height."""
    cx, cy = c
    vs = [prof[0][1]]
    for (r0, za), (r1, zb) in zip(prof, prof[1:]):
        vs.append(vs[-1] + math.hypot(r1 - r0, zb - za))
    for k, ((r0, za), (r1, zb)) in enumerate(zip(prof, prof[1:])):
        dr, dz = r1 - r0, zb - za
        for i in range(seg):
            a0, a1 = i / seg * math.tau, (i + 1) / seg * math.tau
            p = lambda a, r, z: (cx + math.cos(a) * r, cy + math.sin(a) * r, z0 + z)  # noqa: E731
            pts = [p(a0, r0, za), p(a1, r0, za), p(a1, r1, zb), p(a0, r1, zb)]
            mid = (a0 + a1) / 2
            out = Vector((math.cos(mid) * dz, math.sin(mid) * dz, -dr))
            if out.length < 1e-9:
                continue
            if r0 < 1e-6:
                pts = [pts[0], pts[2], pts[3]]
            elif r1 < 1e-6:
                pts = [pts[0], pts[1], pts[2]]
            uvs = None
            if uv:
                va, vb = (vs[k], vs[k + 1]) if slant else (za, zb)
                if ur:
                    # Chord half-widths, so each flat face maps without distortion.
                    h0, h1 = r0 * math.sin((a1 - a0) / 2), r1 * math.sin((a1 - a0) / 2)
                    um = mid * ur
                    full = [(um - h0, va), (um + h0, va), (um + h1, vb), (um - h1, vb)]
                else:
                    rr = max(r0, r1, 0.05)
                    u0, u1 = a0 * rr, a1 * rr
                    full = [(u0, va), (u1, va), (u1, vb), (u0, vb)]
                uvs = full if len(pts) == 4 else ([full[0], full[2], full[3]] if r0 < 1e-6 else full[:3])
            m.poly(role, pts, out=out, uvs=uvs, smooth=smooth)


def disc(m, role, c, r, seg=32, down=False):
    c = Vector(c)
    pts = [c + Vector((math.cos(i / seg * math.tau) * r, math.sin(i / seg * math.tau) * r, 0)) for i in range(seg)]
    m.poly(role, pts, out=(0, 0, -1 if down else 1), uvs=[(p.x, p.y) for p in pts])


def ladder(m, a, b, w=0.4, step=0.3, role="galv", cage=False, out=(0, -1, 0)):
    """A fixed ladder from a to b (its foot and head, the rungs across x), a cage of hoops above 2.5 m."""
    a, b = Vector(a), Vector(b)
    up = (b - a).normalized()
    side = up.cross(Vector(out)).normalized() * (w / 2)
    for s in (-1, 1):
        rod(m, role, a + side * s, b + side * s, 0.025, seg=6)
    L = (b - a).length
    k = 1
    while k * step < L:
        p = a + up * (k * step)
        rod(m, role, p - side, p + side, 0.014, seg=5, caps=False)
        k += 1
    if cage:
        o = Vector(out).normalized()
        z = 2.5
        while z < L - 0.2:
            c = a + up * z + o * 0.35
            pts = [c + side * 1.6 * math.cos(t) + o * 0.38 * math.sin(t) for t in np.linspace(0, math.pi, 9)]
            m.tube(role, pts, 0.012, up, closed=False, seg=4)
            z += 0.9
        for t in np.linspace(0.15, math.pi - 0.15, 5):
            dp = side * 1.6 * math.cos(t) + o * (0.35 + 0.38 * math.sin(t))
            rod(m, role, a + up * 2.5 + dp, a + up * (L - 0.3) + dp, 0.01, seg=4)


def chamfer_box(m, role, lo, hi, c=0.04):
    """A box with its vertical and top edges chamfered (concrete blocks, plinths)."""
    (x0, y0, z0), (x1, y1, z1) = lo, hi
    ring = lambda d, z: [(x0 + c - d, y0 - d, z), (x1 - c + d, y0 - d, z), (x1 + d, y0 + c - d, z), (x1 + d, y1 - c + d, z), (x1 - c + d, y1 + d, z), (x0 + c - d, y1 + d, z), (x0 - d, y1 - c + d, z), (x0 - d, y0 + c - d, z)]  # noqa: E731
    lo_r, mid_r, top_r = ring(0, z0), ring(0, z1 - c), ring(-c, z1)
    cen = Vector(((x0 + x1) / 2, (y0 + y1) / 2, (z0 + z1) / 2))
    for r0, r1 in ((lo_r, mid_r), (mid_r, top_r)):
        for i in range(8):
            j = (i + 1) % 8
            q = [r0[i], r0[j], r1[j], r1[i]]
            mid = sum((Vector(p) for p in q), Vector()) / 4
            m.poly(role, q, out=mid - cen)
    m.poly(role, top_r, out=(0, 0, 1))


# ---- water tower ----------------------------------------------------------------------


def water_tower(m):
    """A 1930s elevated steel tank: four battered tubular legs on concrete
    piers, two tiers of struts with crossed tension rods, a riser pipe to an
    ellipsoidal bottom, a cylindrical tank with a balcony, a conical roof
    with a vent finial; ladders up a leg and over the roof."""
    top = 13.0
    foot, head = 2.75, 2.25
    corners = [(1, 1), (-1, 1), (-1, -1), (1, -1)]
    legs = []
    for sx, sy in corners:
        a = Vector((sx * foot, sy * foot, 0.55))
        b = Vector((sx * head, sy * head, top + 0.9))
        legs.append((a, b))
        chamfer_box(m, "concrete", (sx * foot - 0.55, sy * foot - 0.55, 0), (sx * foot + 0.55, sy * foot + 0.55, 0.55), 0.06)
        m.box("dark", (sx * foot - 0.32, sy * foot - 0.32, 0.55), (sx * foot + 0.32, sy * foot + 0.32, 0.6))
        rod(m, "tankpaint", a, b, 0.2, seg=14)
        # Column cap plates where the leg meets the balcony girder.
        m.box("tankpaint", (b.x - 0.3, b.y - 0.3, b.z - 0.05), (b.x + 0.3, b.y + 0.3, b.z + 0.05))

    def at(i, z):
        a, b = legs[i]
        t = (z - a.z) / (b.z - a.z)
        return a + (b - a) * t

    tiers = [0.55, 4.7, 8.85, top + 0.9]
    for k in range(len(tiers) - 1):
        z0, z1 = tiers[k], tiers[k + 1]
        for i in range(4):
            j = (i + 1) % 4
            # The strut (a latticed channel, drawn as a tube) and its crossed rods.
            if k > 0:
                rod(m, "tankpaint", at(i, z0), at(j, z0), 0.1, seg=8)
            for p, q in ((at(i, z0 + 0.15), at(j, z1 - 0.15)), (at(j, z0 + 0.15), at(i, z1 - 0.15))):
                rod(m, "tankpaint", p, q, 0.022, seg=5, caps=False)
                # Turnbuckle halfway.
                mid = (p + q) / 2
                d = (q - p).normalized()
                rod(m, "dark", mid - d * 0.18, mid + d * 0.18, 0.04, seg=6)
    # Riser pipe, with a frost casing at the foot.
    rod(m, "tankpaint", (0, 0, 0), (0, 0, top + 0.4), 0.42, seg=16)
    lathe(m, "concrete", [(1.0, 0), (1.0, 0.35), (0.85, 0.45), (0.5, 0.5)], seg=20)
    # The tank: an ellipsoidal bottom on the riser, a cylinder, a cone roof.
    R, zb, zt = 3.4, top + 1.6, top + 5.7
    bottom = [(0.42, top + 0.4)] + [(R * math.sin(a), zb - 1.25 * math.cos(a)) for a in np.linspace(0.13, math.pi / 2, 9)]
    lathe(m, "tankpaint", bottom + [(R, zt), (R + 0.04, zt + 0.02), (R + 0.04, zt + 0.08)], seg=48)
    lathe(m, "tankpaint", [(R + 0.04, zt + 0.08), (R - 0.15, zt + 0.12), (1.2, zt + 1.35), (0.45, zt + 1.62), (0.42, zt + 1.62)], seg=48)
    # Plate seams, a little proud of the shell.
    for z in (zb + 1.05, zb + 2.15, zb + 3.25):
        hoop(m, "tankpaint", (0, 0, z), R + 0.012, 0.018, seg=64, rseg=4)
    for i in range(16):
        a = i / 16 * math.tau
        rod(m, "tankpaint", (math.cos(a) * (R + 0.01), math.sin(a) * (R + 0.01), zb), (math.cos(a) * (R + 0.01), math.sin(a) * (R + 0.01), zt), 0.012, seg=4, caps=False)
    # Vent finial.
    lathe(m, "tankpaint", [(0.42, 0), (0.42, 0.25), (0.75, 0.3), (0.75, 0.42), (0.5, 0.62), (0.12, 0.72), (0.0, 0.75)], seg=24, z0=zt + 1.62)
    rod(m, "dark", (0, 0, zt + 2.35), (0, 0, zt + 3.2), 0.035, seg=6)
    # Balcony: a ring girder on the leg heads, grating, two-rail railing.
    zc = top + 0.95
    lathe(m, "tankpaint", [(R - 0.1, zc - 0.25), (R + 0.95, zc - 0.25), (R + 0.95, zc), (R - 0.1, zc)], seg=48, uv=False)
    lathe(m, "grate", [(R, zc + 0.02), (R + 0.92, zc + 0.02)], seg=48)
    for i in range(24):
        a = i / 24 * math.tau
        p = Vector((math.cos(a) * (R + 0.9), math.sin(a) * (R + 0.9), zc))
        rod(m, "tankpaint", p, p + Vector((0, 0, 1.05)), 0.025, seg=5)
    for z in (zc + 0.55, zc + 1.05):
        hoop(m, "tankpaint", (0, 0, z), R + 0.9, 0.025, seg=64, rseg=5)
    # Ladder up the south-east leg to the balcony, caged; and over the roof.
    a, b = legs[3]
    o = Vector((1, -1, 0)).normalized()
    ladder(m, a + o * 0.45 + Vector((0, 0, 1.9)), b + o * 0.45 + Vector((0, 0, -0.85)), cage=True, out=tuple(o))
    for i in range(10):
        t = i / 9
        r = R - 0.1 - (R - 0.6) * t
        z = zt + 0.15 + 1.4 * t
        if i:
            r0 = R - 0.1 - (R - 0.6) * (i - 1) / 9
            z0 = zt + 0.15 + 1.4 * (i - 1) / 9
            for s in (-0.2, 0.2):
                rod(m, "tankpaint", (r0, s, z0), (r, s, z), 0.02, seg=5, caps=False)
        rod(m, "tankpaint", (r, -0.2, z + 0.04), (r, 0.2, z + 0.04), 0.012, seg=4, caps=False)
    # The town's name band (painted, a slightly darker ring).
    lathe(m, "tankband", [(R + 0.006, zb + 2.3), (R + 0.006, zb + 3.0)], seg=48)


# ---- tower crane ----------------------------------------------------------------------
CR = "crane"


def crane_base(m):
    chamfer_box(m, "concrete", (-1.7, -1.7, 0), (1.7, 1.7, 0.6), 0.06)
    for sx in (-1, 1):
        chamfer_box(m, "concrete", (sx * 1.25 - 0.4, -1.3, 0.6), (sx * 1.25 + 0.4, 1.3, 1.1), 0.04)
    for sx in (-1, 1):
        for sy in (-1, 1):
            # Fixing angles cast into the base, with their bolts.
            m.strut(CR, (sx * 0.75, sy * 0.75, 0.6), (sx * 1.2, sy * 1.2, 0.6), 0.14)
            m.box("dark", (sx * 0.75 - 0.2, sy * 0.75 - 0.2, 0.6), (sx * 0.75 + 0.2, sy * 0.75 + 0.2, 0.66))
            for dx, dy in ((-0.12, -0.12), (0.12, -0.12), (-0.12, 0.12), (0.12, 0.12)):
                rod(m, "dark", (sx * 0.75 + dx, sy * 0.75 + dy, 0.66), (sx * 0.75 + dx, sy * 0.75 + dy, 0.74), 0.025, seg=6)


def crane_mast(m):
    """One 3 m mast section: square-tube chords, a zigzag of diagonals on
    every face, fishplates at the joints and a ladder inside."""
    h, a = 3.0, 0.75
    cs = [(-a, -a), (a, -a), (a, a), (-a, a)]
    for x, y in cs:
        m.box(CR, (x - 0.08, y - 0.08, 0), (x + 0.08, y + 0.08, h), skip=("z0", "z1"))
        for z in (0.0, h - 0.18):
            m.box(CR, (x - 0.11, y - 0.11, z), (x + 0.11, y + 0.11, z + 0.18))
    for i in range(4):
        (x0, y0), (x1, y1) = cs[i], cs[(i + 1) % 4]
        m.strut(CR, (x0, y0, 0.12), (x1, y1, 0.12), 0.07)
        mx, my = (x0 + x1) / 2, (y0 + y1) / 2
        m.strut(CR, (x0, y0, 0.15), (x1, y1, h / 2), 0.06)
        m.strut(CR, (x1, y1, h / 2), (x0, y0, h - 0.15), 0.06)
        m.strut(CR, (mx * 0.98, my * 0.98, h / 2 - 0.03), (mx * 0.98, my * 0.98, h / 2 + 0.03), 0.02)
    # A rest platform corner and the ladder up the inside of the -y face.
    ladder(m, (0, -a + 0.2, 0), (0, -a + 0.2, h), w=0.42, out=(0, 1, 0))
    m.box("grate", (-0.45, -a + 0.02, h - 0.3), (0.45, -a + 0.55, h - 0.26))


def crane_slew(m):
    """Slewing ring and platform, the operator's cab, the A-frame tower head."""
    lathe(m, "dark", [(1.0, 0), (1.0, 0.35), (0.98, 0.37)], seg=40, uv=False)
    lathe(m, CR, [(0.98, 0.37), (1.06, 0.37), (1.06, 0.45), (0.9, 0.45)], seg=40, uv=False)
    chamfer_box(m, CR, (-1.1, -0.9, 0.45), (1.1, 0.9, 0.8), 0.04)
    # Cab: a box with rounded front corners, glazed on three sides and the floor front.
    x0, x1, y0, y1, z0, z1 = -0.2, 1.2, -2.1, -0.95, -0.6, 0.75
    chamfer_box(m, "trim", (x0, y0, z0), (x1, y1, z0 + 0.35), 0.03)
    m.box("trim", (x0, y0, z1 - 0.15), (x1, y1, z1))
    m.box("trim", (x0, y1 - 0.15, z0), (x1, y1, z1))
    for x in (x0, x1):
        m.box("trim", (x - 0.03, y0, z0), (x + 0.03, y0 + 0.08, z1))
        m.box("trim", (x - 0.03, y1 - 0.2, z0), (x + 0.03, y1 - 0.12, z1))
    m.box("trim", (x0, y0 - 0.02, z0 + 0.32), (x1, y0 + 0.06, z0 + 0.38))
    m.poly("carglass", [(x0 - 0.01, y0 + 0.08, z0 + 0.35), (x0 - 0.01, y1 - 0.2, z0 + 0.35), (x0 - 0.01, y1 - 0.2, z1 - 0.15), (x0 - 0.01, y0 + 0.08, z1 - 0.15)], out=(-1, 0, 0))
    m.poly("carglass", [(x0 + 0.03, y0 - 0.01, z0 + 0.1), (x1 - 0.03, y0 - 0.01, z0 + 0.1), (x1 - 0.03, y0 - 0.01, z1 - 0.15), (x0 + 0.03, y0 - 0.01, z1 - 0.15)], out=(0, -1, 0))
    m.poly("carglass", [(x1 + 0.01, y0 + 0.08, z0 + 0.35), (x1 + 0.01, y1 - 0.2, z0 + 0.35), (x1 + 0.01, y1 - 0.2, z1 - 0.15), (x1 + 0.01, y0 + 0.08, z1 - 0.15)], out=(1, 0, 0))
    m.box("dark", (x0 + 0.1, y0 - 0.05, z1 - 0.08), (x1 - 0.1, y0 + 0.1, z1 - 0.02))  # wiper rail / sunvisor
    # Walkway round the platform, with a handrail.
    m.box("grate", (-1.5, -0.95, 0.42), (1.5, 0.95, 0.46))
    for x, y in ((-1.45, -0.9), (1.45, -0.9), (1.45, 0.9), (-1.45, 0.9)):
        rod(m, "galv", (x, y, 0.46), (x, y, 1.45), 0.025, seg=5)
    for z in (0.95, 1.45):
        m.tube("galv", [(-1.45, -0.9, z), (1.45, -0.9, z), (1.45, 0.9, z), (-1.45, 0.9, z)], 0.022, Z, closed=True, seg=5)
    # Tower head: four legs to the apex, two frames of bracing, the cap.
    apex = Vector((0, 0, 5.2))
    feet = [Vector(p) for p in ((-0.8, -0.6, 0.8), (0.8, -0.6, 0.8), (0.8, 0.6, 0.8), (-0.8, 0.6, 0.8))]
    for f in feet:
        m.strut(CR, f, apex, 0.14)
    for t in (0.3, 0.62):
        ring = [f + (apex - f) * t for f in feet]
        for i in range(4):
            m.strut(CR, ring[i], ring[(i + 1) % 4], 0.06)
    for i in range(4):
        a_, b_ = feet[i], feet[(i + 1) % 4]
        m.strut(CR, a_, b_ + (apex - b_) * 0.3, 0.05)
    chamfer_box(m, CR, (-0.25, -0.25, 5.0), (0.25, 0.25, 5.45), 0.03)
    for y in (-0.2, 0.2):
        m.box("dark", (-0.32, y - 0.03, 5.05), (0.32, y + 0.03, 5.4))
    ladder(m, (0.75, -0.68, 0.8), (0.12, -0.12, 4.9), w=0.36, out=(0, -1, 0))


def _jib_frame(m, x0, x1, w=0.55, h=1.25, diag=True):
    """A triangular jib truss from x0 to x1: bottom chords at y = +-w, a top chord at height h."""
    m.strut(CR, (x0, -w, 0), (x1, -w, 0), 0.13, 0.11)
    m.strut(CR, (x0, w, 0), (x1, w, 0), 0.13, 0.11)
    m.strut(CR, (x0, 0, h), (x1, 0, h), 0.11)
    # Trolley rails on the bottom chords' outer flanges.
    for y in (-w - 0.075, w + 0.075):
        m.box(CR, (min(x0, x1), y - 0.02, -0.06), (max(x0, x1), y + 0.02, 0.0))
    if not diag:
        return
    L = x1 - x0
    for y in (-w, w):
        m.strut(CR, (x0, y, 0.03), (x0 + L / 2, 0, h - 0.03), 0.065)
        m.strut(CR, (x0 + L / 2, 0, h - 0.03), (x1, y, 0.03), 0.065)
    m.strut(CR, (x0, -w, 0.02), (x0, w, 0.02), 0.06)
    m.strut(CR, (x0 + L / 2, -w, 0.02), (x0 + L / 2, w, 0.02), 0.05)
    m.strut(CR, (x0, -w, 0.01), (x0 + L / 2, w, 0.01), 0.04)
    m.strut(CR, (x0 + L / 2, w, 0.01), (x1, -w, 0.01), 0.04)


def crane_jib(m):
    """One 3 m section of the jib, from x = 0 to x = -3."""
    _jib_frame(m, 0.0, -3.0)
    m.box("grate", (-3.0, -0.3, 0.06), (0.0, 0.3, 0.09))


def crane_jib_tip(m):
    w, h = 0.55, 1.25
    for a in ((0, -w, 0), (0, w, 0), (0, 0, h)):
        m.strut(CR, a, (-1.2, 0, 0.3), 0.09)
    m.strut(CR, (0, -w, 0), (0, w, 0), 0.06)
    m.strut(CR, (0, -w, 0.02), (0, 0, h - 0.02), 0.05)
    m.strut(CR, (0, w, 0.02), (0, 0, h - 0.02), 0.05)
    chamfer_box(m, CR, (-1.4, -0.2, 0.1), (-1.0, 0.2, 0.5), 0.03)
    m.box("dark", (-1.3, -0.25, 0.18), (-1.1, 0.25, 0.42))  # the trolley rope's end sheave


def crane_counter(m):
    """Counter-jib from x = 0.8 to 9.5: twin girders, a walkway with
    handrails, the hoist winch and its cabinet, concrete ballast blocks."""
    for y in (-0.6, 0.6):
        m.box(CR, (0.8, y - 0.09, -0.3), (9.5, y + 0.09, -0.26))
        m.box(CR, (0.8, y - 0.02, -0.26), (9.5, y + 0.02, 0.01))
        m.box(CR, (0.8, y - 0.09, 0.01), (9.5, y + 0.09, 0.05))
        for x in (1.0, 2.6, 4.2, 5.8, 7.4, 9.3):
            rod(m, "galv", (x, y * 1.12, 0.05), (x, y * 1.12, 1.05), 0.025, seg=5)
        for z in (0.55, 1.05):
            rod(m, "galv", (0.9, y * 1.12, z), (9.4, y * 1.12, z), 0.022, seg=5)
    for x in (1.5, 3.5, 5.5, 7.5):
        m.strut(CR, (x, -0.6, -0.12), (x, 0.6, -0.12), 0.07)
    for x0, x1 in ((1.5, 3.5), (3.5, 5.5), (5.5, 7.5)):
        m.strut(CR, (x0, -0.6, -0.14), (x1, 0.6, -0.14), 0.05)
    m.box("grate", (0.8, -0.55, 0.0), (7.6, 0.55, 0.05))
    # Winch: frame, drum, motor and gearbox; the control cabinet.
    m.box(CR, (3.7, -0.55, 0.05), (4.7, -0.45, 0.85))
    m.box(CR, (3.7, 0.45, 0.05), (4.7, 0.55, 0.85))
    rod(m, "dark", (4.2, -0.45, 0.45), (4.2, 0.45, 0.45), 0.34, seg=18)
    for y in (-0.42, 0.42):
        rod(m, CR, (4.2, y, 0.45), (4.2, y + (0.04 if y > 0 else -0.04), 0.45), 0.42, seg=18)
    rod(m, "trim", (4.2, 0.55, 0.45), (4.2, 0.95, 0.45), 0.2, seg=12)
    chamfer_box(m, "trim", (4.6, -0.5, 0.05), (6.4, 0.5, 1.0), 0.04)
    for x in (4.95, 5.5, 6.05):
        m.box("dark", (x - 0.2, -0.51, 0.15), (x + 0.2, -0.5, 0.9))
    for i in range(3):
        x0 = 7.75 + i * 0.58
        chamfer_box(m, "concrete", (x0, -0.85, -1.9), (x0 + 0.52, 0.85, 0.05), 0.05)
        rod(m, "dark", (x0 + 0.26, -0.3, 0.05), (x0 + 0.26, -0.3, 0.16), 0.03, seg=5)
        rod(m, "dark", (x0 + 0.26, 0.3, 0.05), (x0 + 0.26, 0.3, 0.16), 0.03, seg=5)


def crane_trolley(m):
    chamfer_box(m, CR, (-0.55, -0.72, -0.45), (0.55, 0.72, -0.12), 0.03)
    for x in (-0.35, 0.35):
        for y in (-0.62, 0.62):
            rod(m, "dark", (x, y - 0.06, -0.05), (x, y + 0.06, -0.05), 0.11, seg=12)
            m.box(CR, (x - 0.14, y - 0.09, -0.15), (x + 0.14, y - 0.07, 0.02))
    for x in (-0.12, 0.12):
        rod(m, "dark", (x, -0.18, -0.36), (x, 0.18, -0.36), 0.16, seg=12)


def crane_hook(m):
    """Hook block; its origin is where the hoist rope ends."""
    for y in (-0.22, 0.2):
        m.box(CR, (-0.32, y, -0.85), (0.32, y + 0.02, 0.0))
    rod(m, "dark", (0, -0.2, -0.32), (0, 0.2, -0.32), 0.27, seg=16)
    chamfer_box(m, CR, (-0.3, -0.2, -0.95), (0.3, 0.2, -0.82), 0.02)
    rod(m, "dark", (0, 0, -0.95), (0, 0, -1.15), 0.06, seg=8)
    # The hook: a tapered curve, its latch.
    arc = [Vector((0, 0, -1.15)), Vector((0, 0, -1.35))] + [Vector((0.18 - 0.18 * math.cos(a), 0, -1.35 - 0.18 * math.sin(a))) for a in np.linspace(0.3, math.pi, 7)] + [Vector((0.38, 0, -1.25))]
    m.tube("dark", arc, 0.055, (0, 1, 0), closed=False, seg=8)
    rod(m, "dark", (0.0, 0, -1.3), (0.36, 0, -1.25), 0.012, seg=4)


def _i_beam(m, x0, x1, y, z, role="steel"):
    m.box(role, (x0, y - 0.15, z), (x1, y + 0.15, z + 0.03))
    m.box(role, (x0, y - 0.012, z + 0.03), (x1, y + 0.012, z + 0.37))
    m.box(role, (x0, y - 0.15, z + 0.37), (x1, y + 0.15, z + 0.4))


def crane_load(m):
    """Steel beams in slings; origin at the hook."""
    for y in (-0.18, 0.18):
        for z in (-2.45, -2.05):
            _i_beam(m, -1.6, 1.6, y, z)
    for x in (-1.1, 1.1):
        m.box("dark", (x - 0.05, -0.38, -2.5), (x + 0.05, 0.38, -1.62))
        for y in (-0.36, 0.36):
            rod(m, "dark", (0, 0, -1.4), (x, y, -1.64), 0.02, seg=5)
    lathe(m, "dark", [(0.1, -1.42), (0.14, -1.38), (0.1, -1.34)], seg=10, uv=False)


# ---- scaffold ----------------------------------------------------------------------


def scaffold(m):
    """One bay (2.4 m along x) of one lift (2 m): standards on base plates,
    ledgers and transoms in couplers, a deck of five boards at the foot with
    a toe board, guard rails on the outer face and a façade brace."""
    L, H = 2.4, 2.0
    yi, yo = 0.65, -0.15
    r = 0.028
    for x in (-L / 2, L / 2):
        for y in (yi, yo):
            rod(m, "galv", (x, y, 0), (x, y, H), r, seg=6, caps=False)
            m.box("galv", (x - 0.05, y - 0.05, 0.0), (x + 0.05, y + 0.05, 0.08))  # coupler / plate
        rod(m, "galv", (x, yi + 0.12, 0.0), (x, yo - 0.12, 0.0), r, seg=6)  # transom
    for y in (yi, yo):
        rod(m, "galv", (-L / 2 - 0.05, y, 0.02), (L / 2 + 0.05, y, 0.02), r, seg=6)
    for z in (0.55, 1.05):
        rod(m, "galv", (-L / 2 - 0.05, yo - 0.05, z), (L / 2 + 0.05, yo - 0.05, z), r, seg=6)
        for x in (-L / 2, L / 2):
            m.box("galv", (x - 0.045, yo - 0.1, z - 0.045), (x + 0.045, yo - 0.01, z + 0.045))
    rod(m, "galv", (-L / 2, yo - 0.09, 0.08), (L / 2, yo - 0.09, H - 0.05), r, seg=6)
    # Boards, each 225 mm, a little apart; their ends banded.
    for k in range(3):
        y0 = yo + 0.04 + k * 0.235
        m.box("scaffboard", (-L / 2 + 0.02, y0, 0.05), (L / 2 - 0.02, y0 + 0.225, 0.088))
        for x in (-L / 2 + 0.05, L / 2 - 0.08):
            m.box("galv", (x, y0 - 0.002, 0.048), (x + 0.03, y0 + 0.227, 0.09))
    m.box("scaffboard", (-L / 2 + 0.02, yo - 0.04, 0.088), (L / 2 - 0.02, yo - 0.005, 0.24))


# ---- rubble ----------------------------------------------------------------------


def _heap_h(x, y, R, H, rng_field):
    d = math.hypot(x, y) / R
    if d >= 1:
        return 0.0
    base = H * (1 - d * d) ** 1.4
    return max(0.0, base * (0.8 + 0.4 * rng_field(x, y)))


def chunk(m, role, c, size, rng):
    """A broken lump: a box turned at random with every corner knocked about."""
    sx, sy, sz = size
    rot = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-1, 1))).normalized().to_track_quat("Z", "Y")
    P = []
    for dz in (-1, 1):
        for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            q = Vector((dx * sx / 2 * rng.uniform(0.6, 1.1), dy * sy / 2 * rng.uniform(0.6, 1.1), dz * sz / 2 * rng.uniform(0.6, 1.1)))
            P.append(Vector(c) + rot @ q)
    cen = sum(P, Vector()) / 8
    for idx in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
        q = [P[i] for i in idx]
        mid = sum(q, Vector()) / 4
        for tri in ((q[0], q[1], q[2]), (q[0], q[2], q[3])):
            m.poly(role, list(tri), out=mid - cen)


def rubble_heap(m, rng):
    """A mound of broken masonry, 5 m radius, 2.5 m high: a lumpy surface
    under a scatter of bricks, blocks and splinters of timber."""
    R, H = 5.0, 2.5
    phase = [rng.random() * 10 for _ in range(6)]

    def field(x, y):
        return 0.5 + 0.3 * math.sin(x * 1.3 + phase[0]) * math.cos(y * 1.1 + phase[1]) + 0.2 * math.sin(x * 3.1 + y * 2.3 + phase[2]) + 0.12 * math.cos(x * 5.7 - y * 4.9 + phase[3]) + 0.08 * math.sin(x * 9.3 + y * 7.1 + phase[4])

    rings, seg = 20, 64
    pts = []
    for i in range(rings + 1):
        rr = R * 1.04 * i / rings
        row = []
        for j in range(seg):
            a = j / seg * math.tau
            x, y = math.cos(a) * rr, math.sin(a) * rr
            row.append((x, y, _heap_h(x, y, R, H, field) - (0.05 if i == rings else 0)))
        pts.append(row)
    top = (0.0, 0.0, _heap_h(0, 0, R, H, field))
    for j in range(seg):
        jj = (j + 1) % seg
        m.poly("rubble", [top, pts[1][j], pts[1][jj]], out=(0, 0, 1), uvs=[(0, 0), (pts[1][j][0] / 3, pts[1][j][1] / 3), (pts[1][jj][0] / 3, pts[1][jj][1] / 3)], smooth=True)
    for i in range(1, rings):
        for j in range(seg):
            jj = (j + 1) % seg
            q = [pts[i][j], pts[i + 1][j], pts[i + 1][jj], pts[i][jj]]
            m.poly("rubble", q, out=(0, 0, 1), uvs=[(p[0] / 3, p[1] / 3) for p in q], smooth=True)
    # Loose pieces on the surface.
    for k in range(420):
        a = rng.random() * math.tau
        d = R * 0.95 * math.sqrt(rng.random())
        x, y = math.cos(a) * d, math.sin(a) * d
        z = _heap_h(x, y, R, H, field)
        kind = rng.random()
        dirv = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.4, 0.4))).normalized()
        if kind < 0.45:
            Lb, role, t, t2 = 0.23 * rng.uniform(0.5, 1), "brick", 0.11, 0.07
        elif kind < 0.95:
            sz = rng.uniform(0.12, 0.55) ** 1.4
            Lb, role, t, t2 = sz * rng.uniform(1, 2), "concrete", sz * rng.uniform(0.6, 1.2), sz * rng.uniform(0.4, 0.9)
        else:
            Lb, role, t, t2 = rng.uniform(0.6, 1.4), "char", 0.08, 0.18
        c = Vector((x, y, z + t2 * 0.2))
        if role == "concrete":
            chunk(m, "debris", c, (Lb, t, t2), rng)
        else:
            m.strut(role, c - dirv * Lb / 2, c + dirv * Lb / 2, t, t2)


def rubble_wall(m, rng):
    """A broken brick wall, 3.2 m long and 0.33 thick, a ragged top 0.8-2.4 m high."""
    L, T = 3.2, 0.33
    n = 14
    top = []
    for i in range(n + 1):
        x = -L / 2 + L * i / n
        h = 0.8 + 1.6 * (1 - abs(i / n - 0.35) * 1.4) + rng.uniform(-0.25, 0.25)
        # Brick courses: step the break to the 75 mm grid.
        top.append((x + rng.uniform(-0.05, 0.05) * (0 < i < n), max(0.6, round(h / 0.075) * 0.075)))
    outline = [(-L / 2, 0.0), (L / 2, 0.0)] + list(reversed(top))
    for y, out in ((-T / 2, (0, -1, 0)), (T / 2, (0, 1, 0))):
        m.poly("brick", [(x, y, z) for x, z in outline], out=out, uvs=[(x, z) for x, z in outline])
    for (x0, z0), (x1, z1) in zip(top, top[1:]):
        m.poly("brick", [(x0, -T / 2, z0), (x1, -T / 2, z1), (x1, T / 2, z1), (x0, T / 2, z0)], out=(0, 0, 1))
    for x, out in ((-L / 2, (-1, 0, 0)), (L / 2, (1, 0, 0))):
        z = top[0][1] if x < 0 else top[-1][1]
        m.poly("brick", [(x, -T / 2, 0), (x, T / 2, 0), (x, T / 2, z), (x, -T / 2, z)], out=out)
    # Loose bricks hanging off the break, and a charred joist end in a pocket.
    for i in range(1, n, 2):
        x, z = top[i]
        m.strut("brick", (x - 0.11, rng.uniform(-0.1, 0.1), z + 0.03), (x + 0.11, rng.uniform(-0.1, 0.1), z + 0.06), 0.1, 0.065)
    m.strut("char", (-0.4, -0.05, 1.3), (-0.4, -1.4, 1.1), 0.2, 0.09)


def rubble_slab(m, rng):
    """A broken floor slab, 2.6 x 1.8 x 0.22 m, its rebar out of the broken edge."""
    W, D, T = 2.6, 1.8, 0.22
    edge = [(W / 2, -D / 2 + D * i / 8 + rng.uniform(-0.08, 0.08) * (0 < i < 8), 0) for i in range(9)]
    edge = [(W / 2 - abs(math.sin(i * 1.7)) * 0.35 * (0 < i < 8), y, 0) for i, (x, y, _) in enumerate(edge)]
    outline = [(-W / 2, -D / 2), *[(x, y) for x, y, _ in edge], (-W / 2, D / 2)]
    for z, out in ((0, (0, 0, -1)), (T, (0, 0, 1))):
        m.poly("debris", [(x, y, z) for x, y in outline], out=out, uvs=[(x, y) for x, y in outline])
    k = len(outline)
    cen = Vector((0, 0, T / 2))
    for i in range(k):
        (x0, y0), (x1, y1) = outline[i], outline[(i + 1) % k]
        mid = Vector(((x0 + x1) / 2, (y0 + y1) / 2, T / 2))
        m.poly("debris", [(x0, y0, 0), (x1, y1, 0), (x1, y1, T), (x0, y0, T)], out=mid - cen)
    for i in range(1, 8):
        x, y, _ = edge[i]
        for z in (0.05, 0.17):
            end = Vector((x + rng.uniform(0.3, 0.9), y + rng.uniform(-0.2, 0.2), z + rng.uniform(-0.15, 0.35)))
            mid = Vector((x + (end.x - x) * 0.5, y, z))
            m.tube("iron", [Vector((x - 0.05, y, z)), mid, end], 0.008, (0, 0, 1) if abs(end.z - z) < 0.02 else (0, 1, 0), closed=False, seg=4)


def rubble_beam(m, rng):
    """A steel I-beam, 4.6 m, bent 25 degrees in the middle by the fire."""
    L, bend = 2.3, math.radians(25)

    def place(p):
        # Half along -x stays put; the other half turns down about the middle.
        x, y, z = p
        if x <= 0:
            return (x, y, z)
        return (x * math.cos(bend) + z * math.sin(bend), y, -x * math.sin(bend) + z * math.cos(bend))

    for x0, x1 in ((-L, 0.0), (0.0, L)):
        for lo, hi in (((x0, -0.15, 0), (x1, 0.15, 0.03)), ((x0, -0.012, 0.03), (x1, 0.012, 0.37)), ((x0, -0.15, 0.37), (x1, 0.15, 0.4))):
            (a, b, c), (d, e, f) = lo, hi
            corners = [(a, b, c), (d, b, c), (d, e, c), (a, e, c), (a, b, f), (d, b, f), (d, e, f), (a, e, f)]
            P = [place(q) for q in corners]
            cen = sum((Vector(q) for q in P), Vector()) / 8
            for idx in ((0, 1, 2, 3), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)):
                q = [P[i] for i in idx]
                mid = sum((Vector(v) for v in q), Vector()) / 4
                m.poly("steel", q, out=mid - cen)


# ---- park pieces -------------------------------------------------------------------


def fountain(m):
    """A two-tier cast-stone fountain: a moulded basin, a baluster pedestal,
    a lobed bowl and a small cup, water falling from both."""
    lathe(m, "stone", [(3.2, 0), (3.2, 0.12), (3.08, 0.18), (3.05, 0.55), (3.18, 0.6), (3.18, 0.74), (3.05, 0.8), (2.82, 0.8), (2.75, 0.72), (2.75, 0.3)], seg=64)
    disc(m, "water", (0, 0, 0.6), 2.76, seg=64)
    # Pedestal.
    lathe(m, "stone", [(0.0, 0.6), (0.62, 0.6), (0.62, 0.8), (0.48, 0.86), (0.4, 1.0), (0.48, 1.3), (0.34, 1.7), (0.26, 1.85), (0.36, 1.92)], seg=32)
    # The lower bowl: a curved underside, a rolled lip, water standing in it.
    bowl = [(0.36, 1.92)] + [(0.36 + 0.92 * math.sin(a), 2.22 - 0.3 * math.cos(a)) for a in np.linspace(0.2, math.pi / 2, 8)] + [(1.32, 2.24), (1.32, 2.32), (1.2, 2.34)]
    lathe(m, "stone", bowl, seg=48)
    disc(m, "water", (0, 0, 2.3), 1.21, seg=48)
    # Upper shaft and cup, the jet.
    lathe(m, "stone", [(0.0, 2.3), (0.2, 2.3), (0.13, 2.6), (0.17, 2.85), (0.11, 3.0), (0.15, 3.05)], seg=24)
    lathe(m, "stone", [(0.15, 3.05), (0.42, 3.15), (0.52, 3.22), (0.52, 3.27), (0.46, 3.28)], seg=32)
    disc(m, "water", (0, 0, 3.25), 0.47, seg=32)


def fountain_spray(m):
    """The fountain's falling water, in the cut-out mesh so it neither takes
    nor casts baked AO: the jet, and curtains spilling over the bowls' lips
    all round, curving out as they fall (the app draws them clear, streaked)."""
    lathe(m, "spray", [(0.07, 3.25), (0.05, 3.7), (0.025, 4.2), (0.0, 4.4)], seg=10)
    lathe(m, "spray", [(1.6, 0.62), (1.57, 1.1), (1.52, 1.6), (1.44, 2.05), (1.36, 2.28), (1.33, 2.33)], seg=64)
    lathe(m, "spray", [(0.7, 2.31), (0.68, 2.6), (0.63, 2.95), (0.56, 3.2), (0.53, 3.27)], seg=40)


def bandstand(m):
    """A Victorian bandstand: an octagonal brick plinth with steps, a timber
    floor, eight cast-iron columns with brackets, a railing, a frieze and a
    bell roof in zinc with a gilt finial."""
    n, R = 8, 3.2
    rot = math.pi / 8
    ang = [rot + i / n * math.tau for i in range(n)]
    lathe(m, "brick", [(R / math.cos(math.pi / n), 0), (R / math.cos(math.pi / n), 0.5)], seg=n, smooth=False)
    lathe(m, "stone", [(R / math.cos(math.pi / n), 0.5), (R / math.cos(math.pi / n) + 0.06, 0.5), (R / math.cos(math.pi / n) + 0.06, 0.6), (0.0, 0.6)], seg=n, smooth=False)
    # Steps up on the -y side.
    for k in range(3):
        y = -R - 0.32 * (3 - k)
        m.box("stone", (-0.9, y, 0), (0.9, y + 0.32 + 0.02, 0.15 * (k + 1)))
    Rc = R - 0.25
    cols = [Vector((math.cos(a) * Rc, math.sin(a) * Rc, 0.6)) for a in ang]
    for ci, c in enumerate(cols):
        lathe(m, "castiron", [(0.13, 0), (0.13, 0.12), (0.08, 0.2), (0.07, 2.35), (0.11, 2.45), (0.13, 2.6)], seg=12, c=(c.x, c.y), z0=c.z)
        # Brackets curving out to the eaves on both sides.
        for d in (-1, 1):
            k = cols[(ci + d) % n]
            t = (k - c).normalized()
            pts = [c + Vector((0, 0, 2.1)) + t * (0.6 * (1 - math.cos(u))) + Vector((0, 0, 0.5 * math.sin(u))) for u in np.linspace(0, math.pi / 2, 6)]
            m.tube("castiron", pts, 0.025, t.cross(Z), closed=False, seg=4)
    # Railing between the columns, but the entrance bay at the steps.
    entry = min(range(n), key=lambda i: (cols[i] + cols[(i + 1) % n]).y)
    for i in range(n):
        if i == entry:
            continue
        a, b = cols[i], cols[(i + 1) % n]
        for z in (0.1, 0.95):
            rod(m, "castiron", a + Vector((0, 0, z)), b + Vector((0, 0, z)), 0.025, seg=5)
        for k in range(1, 12):
            p = a + (b - a) * (k / 12)
            rod(m, "castiron", p + Vector((0, 0, 0.1)), p + Vector((0, 0, 0.95)), 0.012, seg=4, caps=False)
    lathe(m, "deck", [(R - 0.02, 0.6), (R - 0.02, 0.62), (0.0, 0.62)], seg=n, smooth=False)
    # Frieze and eaves.
    zf = 3.2
    Rf = Rc + 0.12
    lathe(m, "paint", [(Rf / math.cos(math.pi / n), zf), (Rf / math.cos(math.pi / n), zf + 0.32), (Rf / math.cos(math.pi / n) + 0.18, zf + 0.38), (0.4, zf + 0.38)], seg=n, smooth=False)
    for i in range(n):
        a, b = ang[i], ang[(i + 1) % n]
        rr = Rf / math.cos(math.pi / n) + 0.01
        for k in range(10):
            t = (k + 0.5) / 10
            p = Vector((math.cos(a) * rr, math.sin(a) * rr, 0)).lerp(Vector((math.cos(b) * rr, math.sin(b) * rr, 0)), t)
            m.box("paint", (p.x - 0.04, p.y - 0.04, zf - 0.12), (p.x + 0.04, p.y + 0.04, zf))
    # Bell roof (ogee), octagonal, with a fascia and a finial.
    Re = R + 0.35
    prof = [(Re, zf + 0.38), (Re - 0.05, zf + 0.5)] + [(Re * (0.92 - 0.82 * u) - 0.6 * math.sin(u * math.pi) * 0.5, zf + 0.5 + 1.6 * (u ** 0.85)) for u in np.linspace(0.05, 1.0, 9)]
    prof[-1] = (0.12, zf + 2.1)
    lathe(m, "zinc", prof, seg=n, smooth=False, ur=Re, slant=True)
    lathe(m, "brass", [(0.12, zf + 2.1), (0.18, zf + 2.25), (0.08, zf + 2.4), (0.14, zf + 2.55), (0.0, zf + 2.95)], seg=12)


def goal(m):
    """A football goal, 7.32 x 2.44 m, with its net (front at y = 0, net back to y = 1.8)."""
    w, h, d = 7.32, 2.44, 1.8
    for x in (-w / 2, w / 2):
        rod(m, "paint", (x, 0, 0), (x, 0, h), 0.06, seg=12)
        rod(m, "paint", (x, 0, h - 0.05), (x, d * 0.45, h - 0.1), 0.025, seg=6)
        rod(m, "paint", (x, d * 0.45, h - 0.1), (x, d, 0.05), 0.025, seg=6)
        rod(m, "paint", (x, 0.02, 0.03), (x, d, 0.03), 0.025, seg=6)
    rod(m, "paint", (-w / 2 - 0.06, 0, h), (w / 2 + 0.06, 0, h), 0.06, seg=12)
    rod(m, "paint", (-w / 2, d, 0.03), (w / 2, d, 0.03), 0.025, seg=6)
    rod(m, "paint", (-w / 2, d * 0.45, h - 0.1), (w / 2, d * 0.45, h - 0.1), 0.02, seg=6)


def goal_net(m):
    w, h, d = 7.32, 2.44, 1.8
    top = [(-w / 2, 0.02, h), (w / 2, 0.02, h), (w / 2, d * 0.45, h - 0.1), (-w / 2, d * 0.45, h - 0.1)]
    back = [(-w / 2, d * 0.45, h - 0.1), (w / 2, d * 0.45, h - 0.1), (w / 2, d, 0.03), (-w / 2, d, 0.03)]
    m.poly("net", top, out=(0, 0, 1), uvs=[(x, y) for x, y, _ in top])
    m.poly("net", back, out=(0, 1, 0.5), uvs=[(x, z) for x, _, z in back])
    for x in (-w / 2, w / 2):
        side = [(x, 0.02, 0.03), (x, d, 0.03), (x, d * 0.45, h - 0.1), (x, 0.02, h)]
        m.poly("net", side, out=(1 if x > 0 else -1, 0, 0), uvs=[(y, z) for _, y, z in side])


def bleachers(m):
    """A small stand of seats beside the pitch, 14 m long: concrete terraces
    with tip-up seats, a stair at each end, a steel cantilever roof."""
    L = 14.0
    for i in range(5):
        y0 = i * 0.8
        z = 0.45 * (i + 1)
        chamfer_box(m, "concrete", (-L / 2, y0, 0), (L / 2, y0 + 0.8, z), 0.02)
        x = -L / 2 + 1.1
        while x < L / 2 - 1.0:
            m.box("chair", (x - 0.21, y0 + 0.12, z + 0.38), (x + 0.21, y0 + 0.5, z + 0.43))
            m.poly("chair", [(x - 0.21, y0 + 0.5, z + 0.43), (x + 0.21, y0 + 0.5, z + 0.43), (x + 0.21, y0 + 0.6, z + 0.85), (x - 0.21, y0 + 0.6, z + 0.85)], out=(0, -1, 0.3))
            m.poly("chair", [(x - 0.21, y0 + 0.5, z + 0.43), (x + 0.21, y0 + 0.5, z + 0.43), (x + 0.21, y0 + 0.6, z + 0.85), (x - 0.21, y0 + 0.6, z + 0.85)], out=(0, 1, -0.3))
            m.box("dark", (x - 0.03, y0 + 0.3, z), (x + 0.03, y0 + 0.36, z + 0.38))
            x += 0.5
    # Stairs at the ends, with handrails.
    for sx in (-1, 1):
        for i in range(10):
            m.box("concrete", (sx * (L / 2) - (0.9 if sx > 0 else 0), i * 0.4, 0), (sx * (L / 2) + (0 if sx > 0 else 0.9), i * 0.4 + 0.4, 0.225 * (i + 1)))
        rod(m, "galv", (sx * (L / 2 - 0.45), 0, 1.0), (sx * (L / 2 - 0.45), 4.0, 3.25), 0.025, seg=6)
    # Back wall and the roof on three columns.
    m.box("concrete", (-L / 2, 4.0, 0), (L / 2, 4.2, 2.6))
    for x in (-L / 2 + 0.2, 0, L / 2 - 0.2):
        m.box("galv", (x - 0.1, 4.05, 2.6), (x + 0.1, 4.25, 4.75))
        m.strut("galv", (x, 4.15, 4.75), (x, -0.6, 4.62), 0.18, 0.12)
        m.strut("galv", (x, 4.15, 3.6), (x, 1.6, 4.68), 0.08)
    m.box("corrugated", (-L / 2 - 0.3, -0.6, 4.7), (L / 2 + 0.3, 4.4, 4.78))
    m.box("trim", (-L / 2 - 0.3, -0.64, 4.62), (L / 2 + 0.3, -0.6, 4.82))


# ---- people ------------------------------------------------------------------------


def _limb(m, role, pts, radii, seg=8):
    """A limb through points with a radius at each (a tapered, jointed tube)."""
    pts = [Vector(p) for p in pts]
    rings = []
    for i, (p, r) in enumerate(zip(pts, radii)):
        a = pts[max(0, i - 1)]
        b = pts[min(len(pts) - 1, i + 1)]
        t = (b - a).normalized()
        u = t.cross(Vector((1, 0, 0)) if abs(t.x) < 0.9 else Vector((0, 1, 0))).normalized()
        v = t.cross(u)
        rings.append([p + (u * math.cos(k / seg * math.tau) + v * math.sin(k / seg * math.tau)) * r for k in range(seg)])
    for i in range(len(pts) - 1):
        for k in range(seg):
            j = (k + 1) % seg
            q = [rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]]
            mid = sum(q, Vector()) / 4
            m.poly(role, q, out=mid - (pts[i] + pts[i + 1]) / 2, smooth=True)
    for ring, p, q in ((rings[0], pts[0], pts[1]), (rings[-1], pts[-1], pts[-2])):
        m.poly(role, ring, out=p - q, smooth=True)


def _ellipsoid(m, role, c, rx, ry, rz, seg=12, rings=8):
    c = Vector(c)
    P = []
    for i in range(rings + 1):
        th = math.pi * i / rings
        P.append([c + Vector((math.sin(th) * math.cos(math.tau * j / seg) * rx, math.sin(th) * math.sin(math.tau * j / seg) * ry, math.cos(th) * rz)) for j in range(seg)])
    for i in range(rings):
        for j in range(seg):
            jj = (j + 1) % seg
            q = [P[i][j], P[i + 1][j], P[i + 1][jj], P[i][jj]]
            mid = sum(q, Vector()) / 4
            if i == 0:
                q = [P[0][0], P[1][j], P[1][jj]]
            elif i == rings - 1:
                q = [P[i][j], P[rings][0], P[i][jj]]
            m.poly(role, q, out=mid - c, smooth=True)


def person(m):
    """A pedestrian, 1.75 m, mid-stride: legs in trousers, shoes, a jacket
    over the torso and arms, hands, neck, head and hair; the app tints the
    roles per person."""
    # Legs: the left forward, the right back.
    for side, swing in ((-1, 0.18), (1, -0.14)):
        x = side * 0.095
        hip = (x, 0.0, 0.92)
        knee = (x, -swing * 0.9 - 0.02, 0.5)
        ankle = (x, -swing * 1.5, 0.09)
        _limb(m, "pants", [hip, knee, ankle], [0.085, 0.06, 0.045], seg=8)
        # Shoe.
        fy = ankle[1]
        _limb(m, "pants", [(x, fy + 0.05, 0.05), (x, fy - 0.18, 0.04)], [0.05, 0.045], seg=6)
    # Torso (jacket): a loft of rounded rings, hips to shoulders.
    levels = [(0.86, 0.17, 0.11), (0.98, 0.165, 0.1), (1.12, 0.16, 0.1), (1.3, 0.19, 0.115), (1.42, 0.2, 0.11), (1.47, 0.14, 0.08)]
    seg = 12
    rings = [[Vector((math.cos(k / seg * math.tau) * a, math.sin(k / seg * math.tau) * b, z)) for k in range(seg)] for z, a, b in levels]
    for i in range(len(rings) - 1):
        for k in range(seg):
            j = (k + 1) % seg
            q = [rings[i][k], rings[i][j], rings[i + 1][j], rings[i + 1][k]]
            mid = sum(q, Vector()) / 4
            m.poly("shirt", q, out=mid - Vector((0, 0, mid.z)), smooth=True)
    m.poly("shirt", rings[0], out=(0, 0, -1))
    m.poly("shirt", rings[-1], out=(0, 0, 1))
    # Arms swinging against the legs, hands.
    for side, swing in ((-1, -0.12), (1, 0.14)):
        sh = (side * 0.2, 0.0, 1.4)
        el = (side * 0.23, swing * 0.6, 1.12)
        wr = (side * 0.22, swing * 1.2 - 0.04, 0.88)
        _limb(m, "shirt", [sh, el, wr], [0.055, 0.045, 0.04], seg=7)
        _ellipsoid(m, "skin", (wr[0], wr[1] - 0.01, wr[2] - 0.07), 0.035, 0.045, 0.07, seg=8, rings=5)
    # Neck, head, hair.
    _limb(m, "skin", [(0, 0, 1.45), (0, 0.0, 1.55)], [0.05, 0.048], seg=8)
    _ellipsoid(m, "skin", (0, -0.01, 1.64), 0.085, 0.1, 0.115, seg=14, rings=9)
    _ellipsoid(m, "skin", (0, -0.1, 1.62), 0.018, 0.025, 0.03, seg=6, rings=4)  # nose
    _ellipsoid(m, "hair", (0, 0.015, 1.69), 0.092, 0.105, 0.085, seg=14, rings=7)


# ---- the model ----------------------------------------------------------------------


def build(out, bake=True):
    M = Model(ID)
    M.cut_shades = False
    rng = random.Random(31)
    pieces = [
        ("water_tower", lambda m: water_tower(m), 12.0),
        ("crane_base", crane_base, 5.0),
        ("crane_mast", crane_mast, 4.0),
        ("crane_slew", crane_slew, 5.0),
        ("crane_jib", crane_jib, 5.0),
        ("crane_jib_tip", crane_jib_tip, 4.0),
        ("crane_counter", crane_counter, 12.0),
        ("crane_trolley", crane_trolley, 3.0),
        ("crane_hook", crane_hook, 3.0),
        ("crane_load", crane_load, 5.0),
        ("scaffold", scaffold, 4.0),
        ("rubble_heap", lambda m: rubble_heap(m, rng), 12.0),
        ("rubble_wall", lambda m: rubble_wall(m, rng), 5.0),
        ("rubble_slab", lambda m: rubble_slab(m, rng), 5.0),
        ("rubble_beam", lambda m: rubble_beam(m, rng), 6.0),
        ("fountain", fountain, 8.0),
        ("bandstand", bandstand, 9.0),
        ("goal", goal, 9.0),
        ("bleachers", bleachers, 16.0),
        ("person", person, 2.0),
    ]
    x = 0.0
    for name, make, width in pieces:
        x += width / 2
        M.piece(name, (x, 0, 0))
        make(Shift(M.m, (x, 0, 0)))
        if name == "goal":
            goal_net(Shift(M.cut, (x, 0, 0)))
        if name == "fountain":
            fountain_spray(Shift(M.cut, (x, 0, 0)))
        x += width / 2 + 2.0
    M.export(out, bake, size=4096, samples=96, smooth=1.5)
