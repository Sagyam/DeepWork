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

from lib import Model, Side, Z, aerial, fbm, letters, new_id, normals, pane, sides, srgb

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
STAIR = (1.1, 2.1)  # the stair's glass-block strip in the end walls, u from the front edge's side


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


def ends(m, z0, z1, stair=None):
    """The end walls: mosaic slabs standing PROUD of the curtain wall front and
    back, wrapped round their edges, aluminium beads on their four arrises.
    `stair` (sill, head) cuts the staircase's glass-block strip in the outer
    face, a slot of glass blocks in an aluminium frame lighting each landing."""
    for sx in (-1, 1):
        x0, x1 = sorted((sx * CX, sx * HW))
        m.box("mosaic", (x0, -HD - PROUD, z0), (x1, HD + PROUD, z1), skip=("z0", "z1", "x1" if sx > 0 else "x0"))
        F = Side(m, (sx * HW, 0, 0), (0, sx, 0), (sx, 0, 0))
        holes = []
        if stair:
            u0, u1 = STAIR
            holes.append((u0, u1, z0 + stair[0], z0 + stair[1], 0.18))
        F.wall("mosaic", -HD - PROUD, HD + PROUD, z0, z1, holes, depth=0.18, reveal="alu")
        for a, b, c, e, _ in holes:
            F.quad("glassblock", a, b, c, e, -0.16, uvs=[(0, 0), ((b - a) / 0.6, 0), ((b - a) / 0.6, (e - c) / 0.6), (0, (e - c) / 0.6)])
            F.box("alu", a - 0.05, b + 0.05, c - 0.06, c, 0.0, 0.05)
            F.box("alu", a - 0.05, b + 0.05, e, e + 0.04, 0.0, 0.03)
        for y in (-HD - PROUD, HD + PROUD):
            for x in (sx * CX, sx * HW):
                m.box("alu", (x - 0.025, y - 0.025, z0), (x + 0.025, y + 0.025, z1))


def core(m, z0, z1):
    m.box("dark", (-CX, -HD + 0.3, z0), (CX, HD - 0.3, z1), skip=("z0", "z1"))


# ---- the curtain wall --------------------------------------------------------------------------


BLINDS = (
    # (front, back) per bay: how far down each window's blind is let, 0 to 1.
    ([0, 0.6, 0, 0, 0.3, 0, 0, 0, 0.9, 0.9, 0, 0], [0, 0, 0.4, 0, 0, 0, 0.7, 0, 0, 0.2, 0, 0]),
    ([0.3, 0, 0, 0.8, 0, 0, 0.5, 0.5, 0, 0, 0, 0.6], [0.6, 0, 0, 0, 0.9, 0, 0, 0, 0.3, 0, 0, 0]),
)


OPEN = ((3, 8), (5,))  # bays whose awning light is pushed open, per storey variant


def curtain(M, F, z, blinds, opened=()):
    """One storey of curtain wall on facade F (the plane at w = 0): the enamel
    spandrel band, the glass ribbon over it, the mullions and rails."""
    m = M.m
    us = bays()
    zs, zt = z + SPAN, z + FL
    for i, (a, b) in enumerate(zip(us, us[1:])):
        # Spandrel panels, two to a bay, each pressed with a shallow tray and a
        # stiffening rib across the middle, in aluminium sub-frames.
        mid = (a + b) / 2
        for p0, p1 in ((a + 0.03, mid - 0.006), (mid + 0.006, b - 0.03)):
            F.quad("o5panel", p0, p1, z + 0.08, zs - 0.03, 0.0)
            F.box("o5panel", p0 + 0.06, p1 - 0.06, z + 0.16, zs - 0.11, 0.0, 0.02, skip=("back",))
            F.box("o5panel", p0 + 0.06, p1 - 0.06, (z + zs) / 2 + 0.03, (z + zs) / 2 + 0.06, 0.02, 0.035, skip=("back",))
        F.box("dark", mid - 0.006, mid + 0.006, z, zs, -0.01, 0.0)
        wid = new_id()
        ta = zt - 0.62  # the transom over the awning light
        pane(F, "officeglass", a, b, zs, zt, a, b, zs + 0.05, ta, -0.02, wid)
        # The awning light under the transom: a framed sash, top-hung, some pushed out.
        if i in opened:
            tilt, hgt = 0.2, ta - zs - 0.08
            q = lambda u, h: F.p(u, ta - h * math.cos(tilt), -0.02 + h * math.sin(tilt))  # noqa: E731
            m.poly("officeglass", [q(a + 0.08, hgt), q(b - 0.08, hgt), q(b - 0.08, 0.0), q(a + 0.08, 0.0)], out=F.n, uvs=[(wid + 0.05, 0.02), (wid + 0.95, 0.02), (wid + 0.95, 0.3), (wid + 0.05, 0.3)])
            for u in (a + 0.06, b - 0.1):
                m.poly("alu", [q(u, hgt), q(u + 0.04, hgt), q(u + 0.04, 0.0), q(u, 0.0)], out=F.n)
            m.poly("alu", [q(a + 0.06, hgt), q(b - 0.06, hgt), q(b - 0.06, hgt - 0.05), q(a + 0.06, hgt - 0.05)], out=F.n)
            m.poly("dark", [F.p(a + 0.08, zs + 0.06, -0.04), F.p(b - 0.08, zs + 0.06, -0.04), F.p(b - 0.08, ta, -0.04), F.p(a + 0.08, ta, -0.04)], out=F.n)
        else:
            pane(F, "officeglass", a, b, zs, zt, a + 0.06, b - 0.06, ta - 0.02, zt - 0.05, -0.03, wid)
            for u0, u1 in ((a + 0.02, a + 0.06), (b - 0.06, b - 0.02)):
                F.box("alu", u0, u1, zs + 0.04, ta, -0.04, 0.0)
        F.box("alu", a, b, ta - 0.03, ta + 0.03, -0.03, 0.04)
        # The blind: slats pale behind the glass, let down part way.
        k = blinds[i % len(blinds)]
        if k > 0:
            hb = (zt - zs - 0.1) * k
            F.quad("blind", a + 0.03, b - 0.03, zt - 0.05 - hb, zt - 0.05, -0.12, uvs=[(0, 0), (b - a, 0), (b - a, hb), (0, hb)])
    # Mullions: a box section with a pressed cover and a slim fin standing out.
    for u in us[1:-1]:
        F.box("alu", u - 0.035, u + 0.035, z, zt, -0.02, 0.06, skip=("back",))
        F.box("alu", u - 0.012, u + 0.012, z, zt, 0.06, 0.16, skip=("back", "top", "bottom"))
    # The window-cleaning track on the transom at the slab line.
    F.box("alu", -CX, CX, z - 0.02, z + 0.02, 0.05, 0.1, skip=("back",))
    for zz in (z, zs, zt - 0.05):
        F.box("alu", -CX, CX, zz, zz + 0.05, -0.02, 0.05, skip=("back",))


def storey(M, z, variant):
    m = M.m
    S = sides(m, 2 * CX, D)
    front, back = BLINDS[variant]
    curtain(M, S["front"], z, front, OPEN[variant])
    curtain(M, S["back"], z, back, OPEN[1 - variant])
    ends(m, z, z + FL, stair=(0.7, 3.1))
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
    # Pilotis: tapering up to a flared head under the slab, on a black granite foot.
    for x in (-4.5, -1.5, 1.5, 4.5):
        m.cyl("alu", x, -HD + 0.3, 0.13, 0.32, zb - 0.45, seg=16, top=False, r1=0.18)
        m.cyl("alu", x, -HD + 0.3, 0.18, zb - 0.45, zb, seg=16, top=False, r1=0.32)
        m.cyl("dark", x, -HD + 0.3, 0.2, 0.12, 0.32, seg=16, r1=0.16)
    # Long mosaic planters under the slab at each end, low shrubs in them.
    for sx in (-1, 1):
        xa, xb = sorted((sx * (CX - 0.2), sx * (CX - 2.2)))
        m.box("mosaic", (xa, -HD - 0.2, 0.12), (xb, -HD + 0.6, 0.62), skip=("z0",))
        m.poly("hedge", [(xa + 0.08, -HD - 0.12, 0.6), (xb - 0.08, -HD - 0.12, 0.6), (xb - 0.08, -HD + 0.52, 0.6), (xa + 0.08, -HD + 0.52, 0.6)], out=Z)
        for k in range(4):
            m.cyl("hedge", xa + 0.3 + k * 0.48, -HD + 0.2, 0.22, 0.6, 0.95, seg=8, r1=0.08)
    # The street number in aluminium figures on the left end wall's front edge.
    E_ = Side(m, (-CX - EW / 2, -HD - PROUD, 0), (1, 0, 0), (0, -1, 0))
    letters(m, "alu", E_, 0.0, 2.6, 0.0, "200", 0.2, depth=0.03)
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
    # A steel canopy over the loading door on two hangers back to the slab.
    F.box("alu", -3.7, -0.3, 3.3, 3.42, 0.0, 1.4, skip=())
    for u in (-3.5, -0.5):
        m.strut("iron", F.p(u, 3.42, 1.3), F.p(u, zb - 0.1, 0.02), 0.03)
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
    plant(M, deck)
    # Window-cleaning davits along the front and back edges.
    for y, sy in ((-HD - PROUD + 0.3, -1), (HD + PROUD - 0.3, 1)):
        for x in (-5.4, -1.8, 1.8, 5.4):
            m.box("iron", (x - 0.15, y - 0.15, deck), (x + 0.15, y + 0.15, deck + 0.08))
            m.cyl("iron", x, y, 0.05, deck + 0.08, deck + 1.6, seg=8)
            m.strut("iron", (x, y, deck + 1.55), (x, y + sy * 0.7, deck + 1.55), 0.06)


def plant(M, deck):
    """The plant room: louvres round the machinery, set back from the edge, under
    a butterfly roof on thin posts that oversails it all round."""
    m = M.m
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
    # A cooling tower beside the plant room: a louvred box under a fan stack and its guard.
    cx, cy = 5.6, 1.6
    m.box("render", (cx - 1.0, cy - 0.9, deck), (cx + 1.0, cy + 0.9, deck + 0.2), skip=("z0",))
    m.box("blades", (cx - 0.9, cy - 0.8, deck + 0.2), (cx + 0.9, cy + 0.8, deck + 1.6), skip=("z0",))
    m.box("alu", (cx - 0.95, cy - 0.85, deck + 1.6), (cx + 0.95, cy + 0.85, deck + 1.7))
    m.cyl("alu", cx, cy, 0.7, deck + 1.7, deck + 2.2, seg=20, top=False)
    m.cyl("dark", cx, cy, 0.66, deck + 2.15, deck + 2.16, seg=20)
    for k in range(4):
        a = k * math.pi / 4
        m.strut("iron", (cx - math.cos(a) * 0.68, cy - math.sin(a) * 0.68, deck + 2.2), (cx + math.cos(a) * 0.68, cy + math.sin(a) * 0.68, deck + 2.2), 0.025)
    # The rooftop sign: the name on a lit panel in a steel lattice over the front.
    sy = ya + 0.2
    sz = ze + 0.15
    sw, sh = 4.6, 1.0
    S = Side(m, (0, sy, 0), (1, 0, 0), (0, -1, 0))
    S.box("alu", -sw - 0.08, sw + 0.08, sz - 0.08, sz + sh + 0.08, -0.1, 0.0, skip=())
    S.quad("towername", -sw, sw, sz, sz + sh, 0.001, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    for u in (-sw + 0.4, -sw / 3, sw / 3, sw - 0.4):
        m.strut("iron", S.p(u, sz - 0.08, -0.05), S.p(u, ze - 0.12, -0.05), 0.05)
        m.strut("iron", S.p(u, sz + 0.5, -0.1), S.p(u, ze - 0.1, -1.2), 0.03)
    # An aerial on the plant room's roof.
    aerial(m, -3.2, 2.0, ze + 1.2)
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
