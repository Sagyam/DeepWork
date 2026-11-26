# O5, modernist slab: an International Style office of the late 1950s, the
# kind insurers and airlines built on a new boulevard. A thin slab with its
# long side to the street, framed like a picture: two blank end walls in
# small glass mosaic and a thin white roof edge stand proud of the curtain
# wall between them. The curtain wall is all horizontals: on every storey a
# band of porcelain-enamel spandrel panels in a period colour, then a ribbon
# of glass between slim aluminium mullions, a few venetian blinds let down
# behind it. The slab rides on round pilotis over a glass lobby set back
# under it, its back wall a mosaic mural; a folded-plate canopy over the
# door carries the name. On the roof a louvred plant room under a butterfly
# roof on thin steel posts. The app tints the mosaic, the panels and the
# glass, and picks the name.
#
# Pieces (base at the origin, stacked by the app):
#   ground   4.6 m: pilotis, lobby, canopy with the name, the end walls' feet
#   floor_a  3.5 m: a typical storey; blinds one way
#   floor_b  3.5 m: the same, blinds another way; the app alternates them
#   roof     roof edge, the end walls' tops, plant room and butterfly roof
import math

import numpy as np

from lib import Model, Side, Z, fbm, fpoly, new_id, normals, pane, sides, srgb

ID = "o5"
W, D = 15.0, 10.4
HW, HD = W / 2, D / 2
G = 4.6
FL = 3.5
EW = 0.45  # end walls' thickness
PROUD = 0.4  # how far the end walls and the roof edge stand out of the curtain wall
BAY = 1.25  # mullion spacing
SPAN = 1.05  # spandrel band height
CX = HW - EW  # the curtain wall runs between the end walls, -CX..CX
LOBBY = 2.4  # how far the lobby glass is set back under the slab


def build(out, bake=True):
    M = Model(ID)
    M.piece("ground")
    ground(M)
    M.piece("floor_a", (0, 0, G))
    storey(M, G, 0)
    M.piece("floor_b", (0, 0, G + FL))
    storey(M, G + FL, 1)
    M.piece("roof", (0, 0, G + 2 * FL))
    roof(M, G + 2 * FL)
    M.export(out, bake)


def bays():
    n = round(2 * CX / BAY)
    step = 2 * CX / n
    return [-CX + i * step for i in range(n + 1)]


def ends(m, z0, z1):
    """The end walls: mosaic slabs standing PROUD of the curtain wall front and
    back, wrapped round their edges."""
    for sx in (-1, 1):
        x0, x1 = sorted((sx * CX, sx * HW))
        m.box("mosaic", (x0, -HD - PROUD, z0), (x1, HD + PROUD, z1), skip=("z0", "z1"))


def core(m, z0, z1):
    m.box("dark", (-CX, -HD + 0.3, z0), (CX, HD - 0.3, z1), skip=("z0", "z1"))


# ---- the curtain wall --------------------------------------------------------------------------


BLINDS = (
    # (front, back) per bay: how far down each window's blind is let, 0 to 1.
    ([0, 0.6, 0, 0, 0.3, 0, 0, 0, 0.9, 0.9, 0, 0], [0, 0, 0.4, 0, 0, 0, 0.7, 0, 0, 0.2, 0, 0]),
    ([0.3, 0, 0, 0.8, 0, 0, 0.5, 0.5, 0, 0, 0, 0.6], [0.6, 0, 0, 0, 0.9, 0, 0, 0, 0.3, 0, 0, 0]),
)


def curtain(M, F, z, blinds):
    """One storey of curtain wall on facade F (the plane at w = 0): the enamel
    spandrel band, the glass ribbon over it, the mullions and rails."""
    m = M.m
    us = bays()
    zs, zt = z + SPAN, z + FL
    for i, (a, b) in enumerate(zip(us, us[1:])):
        # Spandrel panels, two to a bay, with thin joints.
        mid = (a + b) / 2
        F.quad("o5panel", a, mid - 0.006, z, zs, 0.0)
        F.quad("o5panel", mid + 0.006, b, z, zs, 0.0)
        F.box("dark", mid - 0.006, mid + 0.006, z, zs, -0.01, 0.0)
        wid = new_id()
        pane(F, "officeglass", a, b, zs, zt, a, b, zs + 0.05, zt - 0.05, -0.02, wid)
        # The blind: slats pale behind the glass, let down part way.
        k = blinds[i % len(blinds)]
        if k > 0:
            hb = (zt - zs - 0.1) * k
            F.quad("blind", a + 0.03, b - 0.03, zt - 0.05 - hb, zt - 0.05, -0.12, uvs=[(0, 0), (b - a, 0), (b - a, hb), (0, hb)])
        # A hopper light at the foot of every other bay.
        if i % 2 == 0:
            F.box("alu", a + 0.04, b - 0.04, zs + 0.62, zs + 0.66, -0.03, 0.01)
    for u in us[1:-1]:
        F.box("alu", u - 0.03, u + 0.03, z, zt, -0.02, 0.12, skip=("back",))
    for zz in (z, zs, zt - 0.05):
        F.box("alu", -CX, CX, zz, zz + 0.05, -0.02, 0.05, skip=("back",))


def storey(M, z, variant):
    m = M.m
    S = sides(m, 2 * CX, D)
    front, back = BLINDS[variant]
    curtain(M, S["front"], z, front)
    curtain(M, S["back"], z, back)
    ends(m, z, z + FL)
    # A thin dark slab edge seen in the joint where the end walls meet the glass.
    core(m, z, z + FL)
    m.poly("dark", [(-CX, -HD, z + FL - 0.02), (CX, -HD, z + FL - 0.02), (CX, HD, z + FL - 0.02), (-CX, HD, z + FL - 0.02)], out=Z)


# ---- the ground storey ------------------------------------------------------------------------


def ground(M):
    m = M.m
    ends(m, 0.0, G)
    zb = G - 0.45  # the slab's underside over the undercroft
    # The first floor's slab edge over the pilotis, faced in white.
    for sy in (-1, 1):
        y0, y1 = sorted((sy * HD, sy * (HD - 0.2)))
        m.box("render", (-CX, y0, zb), (CX, y1, G), skip=("x0", "x1"))
    # The soffit over the undercroft, white, with downlights.
    yl = -HD + LOBBY
    m.poly("render", [(-CX, -HD, zb), (CX, -HD, zb), (CX, yl, zb), (-CX, yl, zb)], out=-Z)
    for x in [-CX + 1.2 + i * 2.4 for i in range(int((2 * CX - 1.2) / 2.4) + 1)]:
        m.cyl("lamp", x, -HD + LOBBY / 2, 0.12, zb - 0.02, zb, seg=10, top=False, bottom=True)
    # Pilotis: round, polished, on the line of the curtain wall above.
    for x in (-4.5, -1.5, 1.5, 4.5):
        m.cyl("alu", x, -HD + 0.3, 0.17, 0.12, zb, seg=16)
        m.cyl("dark", x, -HD + 0.3, 0.2, 0.0, 0.12, seg=16)
    # Terrazzo forecourt under the slab, a step up from the pavement.
    m.box("terrazzo", (-CX, -HD - PROUD, 0.0), (CX, yl, 0.12), skip=("z0",))
    lobby(M, yl, zb)
    # The back: a service storey under the slab, mosaic with a loading door.
    F = sides(m, 2 * CX, D)["back"]
    F.wall("mosaic", -CX, CX, 0.0, zb, [(-3.5, -0.5, 0.0, 3.0), (1.5, 2.5, 0.12, 2.4), (3.4, 5.8, 1.2, 3.2)], depth=0.25)
    F.quad("blades", -3.5, -0.5, 0.0, 3.0, -0.2, uvs=[(0, 0), (3, 0), (3, 3), (0, 3)])
    F.quad("door", 1.5, 2.5, 0.12, 2.4, -0.2)
    F.quad("officeglass", 3.4, 5.8, 1.2, 3.2, -0.15)
    for u in (3.4, 4.6, 5.8):
        F.box("alu", u - 0.03, u + 0.03, 1.2, 3.2, -0.15, -0.08)
    F.box("render", -CX, CX, zb, G, 0.0, 0.05, skip=("back",))
    m.box("lamp", (1.85, HD, 2.6), (2.15, HD + 0.12, 2.72))
    canopy(M, -HD - 0.0)


def lobby(M, yl, zb):
    """The lobby: a wall of glass in tall panes, a pair of doors in the middle,
    the mosaic mural on the core wall behind; the lobby's sides are mosaic."""
    m = M.m
    F = Side(m, (0, yl, 0), (1, 0, 0), (0, -1, 0))
    us = [-CX + i * (2 * CX) / 8 for i in range(9)]
    for a, b in zip(us, us[1:]):
        wid = new_id()
        pane(F, "doorglass", a, b, 0.12, zb, a, b, 0.12, zb, -0.02, wid)
    for u in us:
        F.box("alu", u - 0.035, u + 0.035, 0.12, zb, -0.04, 0.06)
    F.box("alu", -CX, CX, 2.6, 2.66, -0.04, 0.06)
    # The doors: two glass leaves with long bar handles.
    for a in (-1.6, 0.0):
        F.box("alu", a, a + 1.6, 0.12, 2.6, 0.0, 0.05, skip=("back",))
        pane(F, "doorglass", -CX, CX, 0.12, zb, a + 0.08, a + 1.52, 0.2, 2.52, 0.06, new_id())
        F.box("brass", a + (1.3 if a < 0 else 0.25), a + (1.35 if a < 0 else 0.3), 0.9, 1.9, 0.06, 0.12)
    # The lobby's floor-to-ceiling mural on the core wall, seen through the glass.
    yc = yl + 3.2
    m.poly("mural", [(-CX, yc, 0.12), (CX, yc, 0.12), (CX, yc, zb), (-CX, yc, zb)], out=(0, -1, 0), uvs=[(0, 0), (1, 0), (1, 1), (0, 1)])
    m.poly("terrazzo", [(-CX, yl, 0.12), (CX, yl, 0.12), (CX, yc, 0.12), (-CX, yc, 0.12)], out=Z)
    m.poly("render", [(-CX, yl, zb), (CX, yl, zb), (CX, yc, zb), (-CX, yc, zb)], out=-Z)
    for x in (-3.0, 3.0):
        m.cyl("lamp", x, yl + 1.6, 0.35, zb - 0.6, zb - 0.45, seg=16, bottom=True)
        m.cyl("alu", x, yl + 1.6, 0.01, zb - 0.45, zb, seg=4)
    # A reception desk and a planter inside.
    m.box("door", (-1.6, yl + 1.6, 0.12), (1.6, yl + 2.2, 1.1))
    m.box("mosaic", (4.2, yl + 0.6, 0.12), (6.2, yl + 1.2, 0.6))
    m.cyl("hedge", 5.2, yl + 0.9, 0.5, 0.6, 1.3, seg=10, r1=0.3)


def canopy(M, yf):
    """A folded-plate canopy over the doors: a thin zigzag of concrete on two
    steel posts, its fascia carrying the name."""
    m = M.m
    x0, x1 = -3.0, 3.0
    y0, y1 = yf - 1.8, yf + LOBBY
    z = 3.3
    n = 6
    xs = [x0 + i * (x1 - x0) / n for i in range(n + 1)]
    for i, (a, b) in enumerate(zip(xs, xs[1:])):
        za, zb = (z, z + 0.25) if i % 2 == 0 else (z + 0.25, z)
        m.poly("render", [(a, y0, za), (b, y0, zb), (b, y1, zb), (a, y1, za)], out=(za - zb, 0, b - a))
        m.poly("render", [(a, y0, z - 0.08), (b, y0, z - 0.08), (b, y0, zb), (a, y0, za)], out=(0, -1, 0))
    # A flat soffit under the folds, with downlights.
    m.poly("render", [(x0, y0, z - 0.08), (x1, y0, z - 0.08), (x1, y1, z - 0.08), (x0, y1, z - 0.08)], out=-Z)
    for x in (-1.5, 0.0, 1.5):
        m.cyl("lamp", x, y0 + 0.9, 0.1, z - 0.1, z - 0.08, seg=10, top=False, bottom=True)
    # The name on a fascia board hung across the canopy's front.
    F = Side(m, (0, y0, 0), (1, 0, 0), (0, -1, 0))
    F.box("alu", -2.9, 2.9, z - 0.5, z - 0.06, 0.0, 0.06, skip=())
    F.quad("towername", -2.8, 2.8, z - 0.46, z - 0.1, 0.061, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    for x in (x0 + 0.3, x1 - 0.3):
        m.cyl("alu", x, y0 + 0.3, 0.06, 0.0, z - 0.03, seg=10)


# ---- the roof ---------------------------------------------------------------------------------


def roof(M, z):
    m = M.m
    # The roof edge: a thin white slab standing proud, end wall to end wall.
    t = 0.45
    m.box("render", (-CX, -HD - PROUD, z), (CX, HD + PROUD, z + t), skip=("x0", "x1"))
    m.poly("render", [(-CX, -HD - PROUD, z), (CX, -HD - PROUD, z), (CX, -HD, z), (-CX, -HD, z)], out=-Z)
    m.poly("render", [(-CX, HD, z), (CX, HD, z), (CX, HD + PROUD, z), (-CX, HD + PROUD, z)], out=-Z)
    # The end walls rise past it a little, capped.
    ends(m, z, z + t + 0.35)
    for sx in (-1, 1):
        x0, x1 = sorted((sx * CX, sx * HW))
        m.poly("mosaic", [(x0, -HD - PROUD, z + t + 0.35), (x1, -HD - PROUD, z + t + 0.35), (x1, HD + PROUD, z + t + 0.35), (x0, HD + PROUD, z + t + 0.35)], out=Z)
        m.box("alu", (x0 - 0.02, -HD - PROUD - 0.02, z + t + 0.35), (x1 + 0.02, HD + PROUD + 0.02, z + t + 0.4))
    # A low parapet inside the edge, the gravelled roof.
    deck = z + t - 0.05
    m.box("render", (-CX, -HD - PROUD + 0.0, z + t), (CX, -HD - PROUD + 0.15, z + t + 0.25), skip=("x0", "x1"))
    m.box("render", (-CX, HD + PROUD - 0.15, z + t), (CX, HD + PROUD, z + t + 0.25), skip=("x0", "x1"))
    m.poly("gravel", [(-CX, -HD - PROUD + 0.15, deck), (CX, -HD - PROUD + 0.15, deck), (CX, HD + PROUD - 0.15, deck), (-CX, HD + PROUD - 0.15, deck)], out=Z)
    plant(m, deck)


def plant(m, deck):
    """The plant room: louvres round the machinery, set back from the edge, under
    a butterfly roof on thin posts that oversails it all round."""
    x0, x1, y0, y1 = -4.2, 4.2, -2.2, 2.6
    h = 2.8
    m.box("render", (x0, y0, deck), (x1, y1, deck + 0.3), skip=("z0",))
    for F, L in ((Side(m, (0, y0, 0), (1, 0, 0), (0, -1, 0)), x1 - x0), (Side(m, (0, y1, 0), (-1, 0, 0), (0, 1, 0)), x1 - x0),
                 (Side(m, (x1, (y0 + y1) / 2, 0), (0, 1, 0), (1, 0, 0)), y1 - y0), (Side(m, (x0, (y0 + y1) / 2, 0), (0, -1, 0), (-1, 0, 0)), y1 - y0)):
        F.quad("blades", -L / 2, L / 2, deck + 0.3, deck + h, 0.0, uvs=[(0, 0), (L, 0), (L, h - 0.3), (0, h - 0.3)])
        for k in range(int(L / 1.2) + 1):
            u = -L / 2 + k * L / int(L / 1.2)
            F.box("alu", u - 0.04, u + 0.04, deck + 0.3, deck + h, 0.0, 0.08)
    m.poly("dark", [(x0, y0, deck + h), (x1, y0, deck + h), (x1, y1, deck + h), (x0, y1, deck + h)], out=Z)
    # The butterfly roof: two thin planes falling to a valley along the middle.
    ox, oy = 1.0, 0.8
    xa, xb, ya, yb = x0 - ox, x1 + ox, y0 - oy, y1 + oy
    zv, ze = deck + h + 0.35, deck + h + 1.2
    ym = (ya + yb) / 2
    for edge, sgn in ((ya, -1), (yb, 1)):
        pts = [(xa, ym, zv), (xb, ym, zv), (xb, edge, ze), (xa, edge, ze)]
        m.poly("render", pts, out=(0, -sgn * (ze - zv), abs(edge - ym)))
        m.poly("render", [(x, y, zz - 0.12) for x, y, zz in pts], out=(0, sgn * (ze - zv), -abs(edge - ym)))
        m.poly("render", [(xa, edge, ze - 0.12), (xb, edge, ze - 0.12), (xb, edge, ze), (xa, edge, ze)], out=(0, sgn, 0))
        for x in (xa, xb):
            m.poly("render", [(x, ym, zv - 0.12), (x, edge, ze - 0.12), (x, edge, ze), (x, ym, zv)], out=(1 if x > 0 else -1, 0, 0))
    for x in (x0 - 0.4, 0.0, x1 + 0.4):
        for y in (y0 - 0.3, y1 + 0.3):
            zt = zv + (ze - zv) * abs(y - ym) / (yb - ym) - 0.12
            m.cyl("iron", x, y, 0.06, deck, zt, seg=8)
    # The valley's rainwater pipe, a flagpole at the corner.
    m.cyl("iron", xb - 0.2, ym, 0.08, deck, zv - 0.1, seg=8)
    m.cyl("alu", -CX + 0.6, -HD - 0.1, 0.05, deck, deck + 6.0, seg=8, r1=0.03)
    m.cyl("alu", -CX + 0.6, -HD - 0.1, 0.09, deck + 6.0, deck + 6.15, seg=8)


# ---- textures ---------------------------------------------------------------------------------


def mosaic_tex(t, n=1024):
    """Glass mosaic: 25 mm square tesserae on a 1 m tile, each its own tone, in
    pale grout; near-white for the app to tint."""
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    k = 40  # tesserae a metre
    cu, cv = x / n * k, y / n * k
    iu, iv = np.floor(cu).astype(int), np.floor(cv).astype(int)
    fu, fv = cu - iu, cv - iv
    rng = np.random.default_rng(511)
    tone = rng.random((k, k))[iv % k, iu % k]
    e = np.minimum(np.minimum(fu, 1 - fu), np.minimum(fv, 1 - fv))  # tile fraction to the joint
    grout = e < 0.06
    dirt = fbm(n, 4, 4, 512)
    col = np.ones((n, n, 3), np.float32) * srgb(232, 236, 236)
    col *= (0.82 + 0.26 * tone + 0.06 * (dirt - 0.5))[..., None]
    col[grout] = srgb(214, 210, 200) * (0.85 + 0.15 * dirt[grout])[..., None]
    h = np.where(grout, 0.0, 0.6 + 0.4 * np.sqrt(np.clip(e / 0.15, 0, 1)))
    t.save("mosaic_col", col)
    t.save("mosaic_nrm", normals(h, 3.0))


def mural_tex(t, n=1024):
    """The lobby's mosaic mural: an abstract of overlapping arcs and bands in
    period colours, the tesserae showing."""
    y, x = (np.mgrid[0:n, 0:n].astype(np.float32) + 0.5) / n
    pal = [srgb(30, 110, 130), srgb(232, 180, 60), srgb(206, 80, 54), srgb(240, 234, 220), srgb(40, 44, 60), srgb(120, 170, 120)]
    col = np.ones((n, n, 3), np.float32) * pal[3]
    rng = np.random.default_rng(521)
    for i in range(14):
        cx, cy, r = rng.random(), rng.random(), 0.1 + 0.35 * rng.random()
        d = np.hypot((x - cx) * 2.6, y - cy)
        band = (d > r) & (d < r + 0.03 + 0.05 * rng.random())
        col[band] = pal[i % len(pal)]
    for i in range(5):
        a = rng.random() * math.pi
        off = rng.random()
        s = (x * 2.6 * math.cos(a) + y * math.sin(a)) - off * 2
        col[(s > 0) & (s < 0.06)] = pal[(i + 2) % len(pal)]
    k = 160
    fu, fv = (x * 2.6 * k) % 1, (y * k) % 1
    grout = (np.minimum(fu, 1 - fu) < 0.07) | (np.minimum(fv, 1 - fv) < 0.07)
    col *= (0.9 + 0.1 * fbm(n, 64, 2, 522))[..., None]
    col[grout] *= 0.8
    t.save("mural_col", col)


def blind_tex(t, n=256):
    """Venetian blind slats, 50 mm, pale, a thin shadow under each: tile 1 m tall over 1 m."""
    y, x = np.mgrid[0:n, 0:n].astype(np.float32)
    fv = (y / n * 20) % 1
    col = np.ones((n, n, 3), np.float32) * srgb(226, 222, 210)
    col *= (0.75 + 0.25 * np.clip(fv / 0.2, 0, 1))[..., None]
    t.save("blind_col", col)


def terrazzo_tex(t, n=1024):
    """Terrazzo: marble chips in a pale cement, polished: tile 1.5 m."""
    base = fbm(n, 8, 3, 531)
    chips = fbm(n, 96, 2, 532)
    chips2 = fbm(n, 160, 2, 533)
    col = np.ones((n, n, 3), np.float32) * srgb(214, 208, 196) * (0.95 + 0.05 * base)[..., None]
    col[chips > 0.68] = srgb(150, 146, 140)
    col[chips < 0.3] = srgb(236, 232, 224)
    col[chips2 > 0.75] = srgb(170, 110, 86)
    t.save("terrazzo_col", col)


TEXTURES = (mosaic_tex, mural_tex, blind_tex, terrazzo_tex)
