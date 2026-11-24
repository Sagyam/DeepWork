# S6, tower brewery: a Victorian brewery on a town lot, brewed by gravity.
# On the left the brewhouse tower, four storeys of red brick on a blue-
# brick plinth, stone string courses at each floor and tall segmental-
# arched windows in it, under a slate pyramid roof crowned by a louvred
# timber ventilator with a lead cap and a weather vane. On the right the
# two-storey store range under a slate roof, its gables to the sides: a
# cart arch with ledged doors on the ground, a loading door over it under
# a timber hoist gable with a beam and chain, the brewery's name painted
# across the brick between the floors. Casks stand on the apron in front.
# The app tints the brick, the doors and the slate, and picks the name.
#
# Pieces (base at the origin):
#   body  the tower's and the range's walls to their eaves, the doors, casks
#   roof  the range's roof and gables, hoist gable, chimney, the tower's
#         pyramid and ventilator
import math

from lib import Model, Side, Z, lintel, new_id, pane, sash, sides, sill

ID = "s6"
TX0, TX1 = -6.6, -1.0  # the tower
RX0, RX1 = -1.0, 6.6  # the range
Y0, Y1 = -4.2, 4.2
PL = 0.6  # the blue-brick plinth
TS = 3.6  # the tower's storeys
TH = 0.4 + 4 * TS  # the tower's eaves
RH = 7.4  # the range's eaves: the roof piece's base
RR = 3.4  # the range roof's rise
TR = 4.2  # the tower pyramid's rise
WALL = 0.3


def build(out, bake=True):
    M = Model(ID, seed=6)
    M.sharp = math.radians(40)
    M.piece("body")
    tower(M)
    range_(M)
    casks(M.m)
    M.piece("roof", (0, 0, RH))
    range_roof(M.m)
    pyramid(M.m)
    M.export(out, bake)


def block(m, x0, x1, y0, y1):
    return sides(m, x1 - x0, y1 - y0, (x0 + x1) / 2, (y0 + y1) / 2)


def plinth(F, h, z1=PL):
    F.box("bluebrick", -h - 0.04, h + 0.04, 0, z1, 0, 0.06, skip=("back", "bottom"))


def arched(F, a, b, c, e, lights=(2, 3)):
    """A tall sash under a stone lintel with a key, on a stone sill."""
    sash(F, a, b, c, e, D=WALL, lights=lights)
    sill(F, a, b, c, D=WALL)
    lintel(F, a, b, e)


# ---- the tower ----------------------------------------------------------------------


def tower(M):
    m = M.m
    S = block(m, TX0, TX1, Y0, Y1)
    for name, F in S.items():
        h = (TX1 - TX0) / 2 if name in ("front", "back") else (Y1 - Y0) / 2
        if name == "right":
            # Against the range up to its eaves.
            lo = RH
        else:
            lo = 0.0
        holes = []
        for k in range(4):
            z = 0.4 + k * TS
            if z + 2.8 <= lo:
                continue
            us = [-1.4, 1.4] if name in ("front", "back") else [-2.0, 0.0, 2.0]
            for u in us:
                if name == "front" and k == 0 and u < 0:
                    continue  # the office door
                holes.append((u - 0.5, u + 0.5, z + 0.8, z + 2.9))
        if name == "front":
            holes.append((-1.95, -0.85, PL, 2.9, 0.3))
        F.wall("brick", -h, h, lo, TH, holes, depth=WALL, reveal="brick")
        for a, b, c, e, *_ in holes:
            if c > PL:
                arched(F, a, b, c, e)
        if lo == 0:
            plinth(F, h)
        for k in range(1, 4):
            z = 0.4 + k * TS
            if z > lo:
                F.box("stone", -h - 0.04, h + 0.04, z - 0.12, z, 0, 0.08, skip=("back",))
        # Pilaster strips at the corners.
        for u0, u1 in ((-h, -h + 0.45), (h - 0.45, h)):
            F.box("brick", u0, u1, max(lo, PL), TH, 0, 0.06, skip=("back", "bottom"))
        # A corbelled eaves band.
        F.box("brick", -h, h, TH - 0.35, TH - 0.2, 0, 0.1, skip=("back",))
        F.box("brick", -h, h, TH - 0.2, TH, 0, 0.16, skip=("back",))
    # The office door: panelled, a fanlight, a stone hood on brackets.
    F = S["front"]
    a, b = -1.95, -0.85
    F.quad("doors", a + 0.05, b - 0.05, PL - 0.45, 2.3, -0.26)
    F.box("doors", a, b, 2.3, 2.38, -0.3, -0.22, skip=("back",))
    pane(F, "worksglass", a, b, 2.38, 2.9, a + 0.05, b - 0.05, 2.38, 2.85, -0.26, new_id())
    F.box("stone", a - 0.2, b + 0.2, 2.95, 3.12, 0, 0.32)
    for u in (a - 0.15, b + 0.05):
        F.box("stone", u, u + 0.1, 2.6, 2.95, 0, 0.25)
    F.box("stone", a - 0.1, b + 0.1, 0, 0.15, 0, 0.45, skip=("back", "bottom"))
    F.box("brass", b - 0.2, b - 0.12, 1.1, 1.16, -0.26, -0.2, skip=("back",))
    # A works clock high on the front.
    from s4_factory import annulus, disc

    cz = TH - 1.4
    annulus(F, "stone", 0, cz, 0.55, 0.7, 0.08, seg=24)
    disc(F, "clock", 0, cz, 0.55, 0.05, seg=24)
    for ang, ln in ((-30, 0.28), (90, 0.42)):
        q = math.radians(ang)
        m.strut("iron", F.p(0, cz, 0.06), F.p(math.sin(q) * ln, cz + math.cos(q) * ln, 0.06), 0.012, 0.035)
    m.poly("dark", [(TX0, Y0, TH - 0.05), (TX1, Y0, TH - 0.05), (TX1, Y1, TH - 0.05), (TX0, Y1, TH - 0.05)], out=-Z)


# ---- the store range ------------------------------------------------------------------


def range_(M):
    m = M.m
    S = block(m, RX0, RX1, Y0, Y1)
    hw, hd = (RX1 - RX0) / 2, (Y1 - Y0) / 2
    F = S["front"]
    arch = (-1.4, 1.4, 0, 3.1)
    loft = (-0.9, 0.9, 4.4, 6.6)
    side_w = [(u - 0.55, u + 0.55, 1.2, 3.2) for u in (-2.9, 2.9)] + [(u - 0.55, u + 0.55, 4.6, 6.5) for u in (-2.9, 2.9)]
    F.wall("brick", -hw, hw, 0, RH, [(*arch, WALL), (*loft, WALL)] + side_w, depth=WALL)
    plinth(F, hw)
    for a, b, c, e in side_w:
        arched(F, a, b, c, e, lights=(2, 2))
    # The cart arch: ledged doors under a brick arch with a stone key.
    for half in ((-1.4, 0.0), (0.0, 1.4)):
        F.quad("doors", half[0] + 0.02, half[1] - 0.02, 0, 2.8, -WALL + 0.04, uvs=None)
        for z in (0.5, 1.4, 2.3):
            F.box("doors", half[0] + 0.1, half[1] - 0.1, z, z + 0.15, -WALL + 0.04, -WALL + 0.09)
        F.box("iron", half[0] + 0.15, half[1] - 0.15, 1.25, 1.3, -WALL + 0.09, -WALL + 0.12)
    F.quad("dark", -1.4, 1.4, 2.8, 3.1, -WALL + 0.02)
    for k in range(9):
        t = k / 8
        u = -1.55 + 3.1 * t
        zz = 3.1 + 0.25 * math.sin(math.pi * t)
        F.box("brick", u - 0.17, u + 0.17, zz - 0.1, zz + 0.32, 0, 0.05, skip=("back",))
    F.box("stone", -0.14, 0.14, 3.25, 3.65, 0, 0.08)
    for u in (-1.55, 1.55):
        F.box("stone", u - 0.12, u + 0.12, 0, 0.5, 0, 0.12, skip=("back", "bottom"))
    # The loft door over it, ledged, half open.
    a, b, c, e = loft
    F.quad("dark", a, b, c, e, -WALL + 0.02)
    F.box("doors", a + 0.02, 0.0, c, e - 0.05, -WALL + 0.03, -WALL + 0.08)
    D = Side(m, F.p(b, 0, 0), (0, -1, 0), (1, 0, 0))
    D.box("doors", 0.0, 0.85, c, e - 0.05, 0.0, 0.05, skip=())
    F.box("stone", a - 0.1, b + 0.1, c - 0.08, c, 0, 0.12)
    lintel(F, a, b, e)
    # The name, painted across the brick between the floors.
    F.quad("works", -3.6, 3.6, 3.87, 4.29, 0.004, uvs=[(0, 0), (1, 0), (1, 1), (0, 1)], m=M.decal)
    # The right gable end: windows; the back: a door and windows.
    for name in ("right", "back"):
        Sd = S[name]
        h = hd if name == "right" else hw
        us = [-2.2, 0.0, 2.2] if name == "right" else [-2.5, 0.0, 2.5]
        holes = [(u - 0.5, u + 0.5, 1.2, 3.0) for u in us] + [(u - 0.5, u + 0.5, 4.6, 6.4) for u in us]
        if name == "back":
            holes[0] = (-3.0, -2.0, PL, 2.6, WALL)
        Sd.wall("brick", -h, h, 0, RH, holes, depth=WALL)
        plinth(Sd, h)
        for a, b, c, e, *deep in holes:
            if deep:
                Sd.quad("doors", a + 0.03, b - 0.03, PL - 0.45, e, -WALL + 0.04)
                Sd.box("stone", a - 0.1, b + 0.1, 0, 0.15, 0, 0.45, skip=("back", "bottom"))
                lintel(Sd, a, b, e, key_=False)
            else:
                arched(Sd, a, b, c, e, lights=(2, 2))
    for name, F2 in S.items():
        if name == "left":
            continue  # against the tower
        h = hd if name == "right" else hw
        F2.box("stone", -h - 0.04, h + 0.04, 3.7, 3.82, 0, 0.08, skip=("back",))
    m.poly("dark", [(RX0, Y0, RH - 0.05), (RX1, Y0, RH - 0.05), (RX1, Y1, RH - 0.05), (RX0, Y1, RH - 0.05)], out=-Z)


def casks(m):
    """A row of casks on their sides on the apron, and two stood on end."""
    def cask(x, y, z, axis):
        r, L = 0.36, 0.95
        if axis == "z":
            m.cyl("wood", x, y, r, z, z + L, seg=14, uv=True)
            for hz in (0.12, L - 0.17):
                m.cyl("iron", x, y, r + 0.015, z + hz, z + hz + 0.05, seg=14, top=False)
            return
        for k in range(14):
            a0, a1 = k / 14 * math.tau, (k + 1) / 14 * math.tau
            p = lambda a, u: (x - L / 2 + u, y + math.cos(a) * r, z + r + math.sin(a) * r)  # noqa: E731
            m.poly("wood", [p(a0, 0), p(a1, 0), p(a1, L), p(a0, L)], out=(0, math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2)))
        for u, s in ((0, -1), (L, 1)):
            m.poly("wood", [(x - L / 2 + u, y + math.cos(k / 14 * math.tau) * r, z + r + math.sin(k / 14 * math.tau) * r) for k in range(14)], out=(s, 0, 0))
        for u in (0.1, L - 0.15):
            for k in range(14):
                a0, a1 = k / 14 * math.tau, (k + 1) / 14 * math.tau
                q = lambda a, uu: (x - L / 2 + uu, y + math.cos(a) * (r + 0.015), z + r + math.sin(a) * (r + 0.015))  # noqa: E731
                m.poly("iron", [q(a0, u), q(a1, u), q(a1, u + 0.05), q(a0, u + 0.05)], out=(0, math.cos((a0 + a1) / 2), math.sin((a0 + a1) / 2)))

    for y in (Y0 - 0.7, Y0 - 1.45):
        cask(5.6, y, 0, "x")
    cask(5.6, Y0 - 1.075, 0.62, "x")
    for x in (0.25, 0.95):
        cask(x, Y0 - 0.55, 0, "z")


# ---- roofs -----------------------------------------------------------------------------


def range_roof(m):
    """A slate roof with its ridge along the street, coped gables, a hoist gable and a chimney."""
    z0, z1 = RH, RH + RR
    yc = (Y0 + Y1) / 2
    o = 0.35  # eaves overhang
    for s in (-1, 1):
        ye = Y0 - o if s < 0 else Y1 + o
        pts = [(RX0, ye, z0 - 0.15), (RX1 + 0.1, ye, z0 - 0.15), (RX1 + 0.1, yc, z1), (RX0, yc, z1)]
        m.poly("slate", pts, out=(0, s, 1.2))
        m.poly("dark", pts, out=(0, -s, -1.2))
        m.box("gutter", (RX0, ye - 0.08 * -s - 0.06, z0 - 0.3), (RX1 + 0.1, ye + 0.06 * -s + 0.06, z0 - 0.15))
    m.box("ridge", (RX0, yc - 0.1, z1 - 0.05), (RX1 + 0.1, yc + 0.1, z1 + 0.12))
    # The right gable, coped in stone.
    S = block(m, RX0, RX1, Y0, Y1)
    G = S["right"]
    hd = (Y1 - Y0) / 2
    m.poly("brick", [G.p(-hd, z0), G.p(hd, z0), G.p(0, z1)], out=G.n)
    for s in (-1, 1):
        m.strut("stone", G.p(s * (hd + 0.3), z0 - 0.15, 0.05), G.p(0, z1 + 0.25, 0.05), 0.3, 0.2)
    pane(G, "worksglass", -0.4, 0.4, z0 + 0.6, z0 + 1.6, -0.4, 0.4, z0 + 0.6, z0 + 1.6, 0.02, new_id())
    # The hoist gable over the loading door: timber, a beam out to a pulley and a chain.
    F = S["front"]
    hz0, hz1 = z0 - 0.15, z0 + 1.6
    for u in (-1.2, 1.2):
        F.box("doors", u - 0.06, u + 0.06, hz0, hz1, -2.2, 1.0, skip=("back",))
    F.quad("doors", -1.2, 1.2, hz0, hz1, 1.0)
    for s in (-1, 1):
        m.poly("slate", [F.p(0, hz1 + 1.0, 1.25), F.p(s * 1.45, hz1 - 0.1, 1.25), F.p(s * 1.45, hz1 - 0.1, -2.2), F.p(0, hz1 + 1.0, -3.35)], out=(s, 0, 1))
    F.box("doors", -1.3, 1.3, hz1 - 0.1, hz1, 0, 1.25)
    fpts = [(-1.3, hz1), (1.3, hz1), (0, hz1 + 1.0)]
    m.poly("doors", [F.p(u, z, 1.22) for u, z in fpts], out=F.n)
    F.box("iron", -0.08, 0.08, hz0 + 0.2, hz0 + 0.35, 0, 1.9, skip=())
    m.cyl("iron", F.p(0, 0, 1.75).x, F.p(0, 0, 1.75).y, 0.1, hz0 - 0.05, hz0 + 0.2, seg=10)
    m.strut("iron", F.p(0, hz0 - 0.05, 1.75), F.p(0, hz0 - 2.8, 1.75), 0.03)
    m.strut("iron", F.p(-0.12, hz0 - 2.8, 1.75), F.p(0.12, hz0 - 2.95, 1.75), 0.06)
    # The copper's flue: a square brick chimney through the back slope.
    cx, cy = 4.4, 2.3
    ct = z1 + 2.2
    m.box("brick", (cx - 0.45, cy - 0.45, z0 + 1.0), (cx + 0.45, cy + 0.45, ct))
    m.box("stone", (cx - 0.55, cy - 0.55, ct), (cx + 0.55, cy + 0.55, ct + 0.15))
    m.cyl("terracotta", cx, cy, 0.18, ct + 0.15, ct + 0.7, seg=10, r1=0.15)


def pyramid(m):
    """The tower's hipped slate roof, a louvred ventilator on its ridge, a lead cap and a vane."""
    z0 = TH
    o = 0.3
    x0, x1, y0, y1 = TX0 - o, TX1 + o, Y0 - o, Y1 + o
    cx, cy = (TX0 + TX1) / 2, (Y0 + Y1) / 2
    ex, ey = (x1 - x0) / 2, (y1 - y0) / 2
    zt = z0 + TR
    corners = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    rr = ey - ex  # half the ridge
    inner = [(cx, cy - rr), (cx, cy - rr), (cx, cy + rr), (cx, cy + rr)]
    for i in range(4):
        j = (i + 1) % 4
        mx = (corners[i][0] + corners[j][0]) / 2 - cx
        my = (corners[i][1] + corners[j][1]) / 2 - cy
        pts = [(*corners[i], z0), (*corners[j], z0), (*inner[j], zt), (*inner[i], zt)]
        pts = [p for k, p in enumerate(pts) if p != pts[k - 1]]
        m.poly("slate", pts, out=(mx, my, 3))
        m.poly("dark", [(*p[:2], p[2] - 0.05) for p in pts], out=(-mx, -my, -3))
        m.strut("ridge", (*corners[i], z0 + 0.05), (*inner[i], zt + 0.05), 0.14)
    m.strut("ridge", (cx, cy - rr - 0.07, zt + 0.05), (cx, cy + rr + 0.07, zt + 0.05), 0.16)
    v = 0.8
    vz0, vz1 = zt - TR * v / ex, zt + 1.2
    # The ventilator: a timber box of louvres, a lead pyramid cap, the vane.
    for F in sides(m, 2 * v, 2 * v, cx, cy).values():
        F.box("wood", -v, -v + 0.12, vz0, vz1, -0.05, 0.05, skip=("back",))
        F.box("wood", v - 0.12, v, vz0, vz1, -0.05, 0.05, skip=("back",))
        F.quad("dark", -v, v, vz0, vz1, -0.2)
        for k2 in range(6):
            z = zt + 0.05 + k2 * 0.18
            m.strut("wood", F.p(-v + 0.12, z + 0.12, -0.02), F.p(v - 0.12, z + 0.12, -0.02), 0.025, 0.16)
    lz = vz1
    for i, (a, b) in enumerate(((-v - 0.15, -v - 0.15), (v + 0.15, -v - 0.15), (v + 0.15, v + 0.15), (-v - 0.15, v + 0.15))):
        c, d = [(-v - 0.15, -v - 0.15), (v + 0.15, -v - 0.15), (v + 0.15, v + 0.15), (-v - 0.15, v + 0.15)][(i + 1) % 4]
        m.poly("lead", [(cx + a, cy + b, lz), (cx + c, cy + d, lz), (cx, cy, lz + 1.1)], out=((a + c) / 2, (b + d) / 2, 1))
    m.box("lead", (cx - v - 0.15, cy - v - 0.15, lz - 0.1), (cx + v + 0.15, cy + v + 0.15, lz), skip=("z1",))
    m.cyl("iron", cx, cy, 0.03, lz + 1.0, lz + 2.6, seg=6)
    m.cyl("brass", cx, cy, 0.1, lz + 1.9, lz + 2.1, seg=10)
    for d in ((1, 0), (0, 1), (-1, 0), (0, -1)):
        m.strut("iron", (cx, cy, lz + 1.7), (cx + d[0] * 0.45, cy + d[1] * 0.45, lz + 1.7), 0.02)
    m.poly("iron", [(cx - 0.5, cy, lz + 2.35), (cx + 0.7, cy, lz + 2.35), (cx + 0.7, cy, lz + 2.55), (cx - 0.3, cy, lz + 2.65), (cx - 0.5, cy, lz + 2.5)], out=(0, -1, 0))
    m.poly("iron", [(cx - 0.5, cy, lz + 2.35), (cx + 0.7, cy, lz + 2.35), (cx + 0.7, cy, lz + 2.55), (cx - 0.3, cy, lz + 2.65), (cx - 0.5, cy, lz + 2.5)], out=(0, 1, 0))
