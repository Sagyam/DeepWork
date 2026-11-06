# W2, pumping station: the City's waterworks engine house of 1885, built
# to look like a chapel because the board was proud of it. Red brick with
# bands of blue engineering brick and stone, its gable to the street: one
# great round-headed window over the date panel, smaller arched windows
# down the sides between buttresses, a corbelled eaves course, coped
# gables with kneelers and a finial, a slate roof with a louvred lantern
# on the ridge. A lean-to boiler house on the right, and behind it the
# chimney: a square Italianate shaft banded in blue brick with a stone-
# capped arcaded top. In front a small yard over the mains behind iron
# railings and gates hung on stone piers, cast-iron valve covers and a
# standpipe.
#
# Pieces (base at the origin):
#   body  the engine house to the eaves (7.4 m), the boiler house, the
#         chimney's base, the yard
#   roof  gables, slates and lantern, the chimney's shaft and top
import math

from lib import Model, Z, fpoly, letters, new_id, pane, sash, sides, sill
from s4_factory import arch

ID = "w2"
EX0, EX1 = -6.4, 2.6  # the engine house, x
EY0, EY1 = -5.0, 6.0  # and y; its gable faces the street (-y)
EW, ED = EX1 - EX0, EY1 - EY0
ECX, ECY = (EX0 + EX1) / 2, (EY0 + EY1) / 2
EAV = 7.4
RISE = 3.6
WALL = 0.45
BX1 = 6.4  # the boiler house's right wall
BY0, BY1 = -1.0, 6.0
BH = 4.6  # its wall top on the right, rising to BH2 against the engine house
BH2 = 6.2
CX, CY = 4.6, 4.6  # the chimney
CS0, CS1 = 0.85, 0.65  # its half-width at the base, at the top
CT = 24.0
YARD = -7.6  # the railings


def build(out, bake=True):
    M = Model(ID, seed=47)
    M.sharp = math.radians(40)
    M.piece("body")
    body(M)
    M.piece("roof", (0, 0, EAV))
    roof(M)
    # Centre the footprint, the railings to the back wall.
    for mesh in (M.m, M.cut, M.decal):
        for v in mesh.bm.verts:
            v.co.y += 0.8
    M.export(out, bake)


def bands(F, u0, u1, z0, z1, holes=()):
    """Polychrome bands: a course of blue brick every 1.2 m, standing just proud, broken by the openings."""
    z = z0 + 1.2
    while z < z1 - 0.3:
        u = u0
        for a, b, c, e, *_ in sorted(holes):
            # An arch's ring stands 0.36 m round the opening's head.
            if c - 0.1 <= z + 0.15 and z <= e + 0.4:
                if a - 0.4 > u:
                    F.box("bluebrick", u, a - 0.4, z, z + 0.15, 0, 0.012)
                u = max(u, b + 0.4)
        if u1 > u:
            F.box("bluebrick", u, u1, z, z + 0.15, 0, 0.012)
        z += 1.2


def window(F, a, b, c, e, lights=(2, 3)):
    """A round-headed window: a sash to the springing, a fanlight under the arch."""
    half = (b - a) / 2
    spring = e - half
    sash(F, a, b, c, spring, D=WALL, lights=lights, glass="worksglass")
    wid = new_id()
    pane(F, "worksglass", a, b, spring, e, a, b, spring, e, -WALL + 0.1, wid)
    mid = (a + b) / 2
    for k in range(1, 4):
        t = math.pi * k / 4
        F.m.strut("frame", F.p(mid, spring, -WALL + 0.12), F.p(mid - math.cos(t) * half, spring + math.sin(t) * half, -WALL + 0.12), 0.03)
    arch(F, a, b, e, rise=half, ring=0.36, D=WALL)
    sill(F, a, b, c, D=WALL)


# ---- body -----------------------------------------------------------------------------


def body(M):
    m = M.m
    S = sides(m, EW, ED, ECX, ECY)
    for name, F in S.items():
        h = EW / 2 if name in ("front", "back") else ED / 2
        if name == "front":
            holes = [(-1.1, 1.1, 2.2, 7.0), (-3.4, -2.4, 1.4, 4.6), (2.4, 3.4, 1.4, 4.6)]
        elif name == "back":
            holes = [(-0.7, 0.7, 2.0, 5.6)]
        elif name == "left":
            holes = [(u - 0.55, u + 0.55, 1.6, 5.8) for u in (-3.3, 0.0, 3.3)]
        else:
            # The right wall: a door into the boiler house's lean-to, windows above its roof.
            holes = [(-0.7, 0.7, 0.3, 3.0, WALL)] + [(u - 0.45, u + 0.45, BH2 - 0.2, EAV - 0.5) for u in (-3.6, -1.8)]
        F.wall("brick", -h, h, 0.0, EAV, holes, depth=WALL, reveal="brick")
        # A plinth of blue brick with a stone chamfer, polychrome bands, a stone string at the sills.
        F.box("bluebrick", -h - 0.06, h + 0.06, 0.0, 0.7, 0, 0.06)
        F.box("stone", -h - 0.08, h + 0.08, 0.7, 0.82, 0, 0.1)
        bands(F, -h, h, 0.8, EAV, holes)
        for hole in holes:
            a, b, c, e = hole[:4]
            if len(hole) == 5:
                F.quad("doors", a, b, c, e, -WALL + 0.06)
                for z in (c + 0.4, (c + e) / 2, e - 0.4):
                    F.box("iron", a + 0.05, b - 0.05, z - 0.03, z + 0.03, -WALL + 0.06, -WALL + 0.09)
                arch(F, a, b, e + 0.25, rise=0.25, ring=0.3, D=WALL)
                continue
            window(F, a, b, c, e, lights=(3, 4) if b - a > 2 else (2, 3))
        # Buttresses at the corners and between the side windows, with stone weatherings.
        us = [-h + 0.3, h - 0.3]
        if name in ("left", "right"):
            us += [-1.65, 1.65] if name == "left" else []
        for u in us:
            F.box("brick", u - 0.3, u + 0.3, 0.0, EAV - 1.2, 0, 0.35)
            F.box("stone", u - 0.32, u + 0.32, EAV - 1.2, EAV - 1.05, 0, 0.38)
            F.box("brick", u - 0.3, u + 0.3, EAV - 1.05, EAV - 0.4, 0, 0.18)
            F.box("stone", u - 0.32, u + 0.32, EAV - 0.4, EAV - 0.28, 0, 0.21)
        # A corbelled eaves course along the sides.
        if name in ("left", "right"):
            for k, d in enumerate((0.05, 0.1, 0.16)):
                F.box("brick", -h, h, EAV - 0.3 + k * 0.1, EAV - 0.2 + k * 0.1, 0, d)
    # The date panel under the great window, WATER WORKS over it.
    F = S["front"]
    F.box("stone", -1.4, 1.4, 1.05, 2.05, 0, 0.08)
    letters(m, "iron", F, 0, 1.75, 0.08, "WATER WORKS", 0.22, depth=0.02, spacing=1.25)
    letters(m, "iron", F, 0, 1.3, 0.08, "1885", 0.24, depth=0.02, spacing=1.3)
    m.poly("dark", [(EX0, EY0, EAV - 0.02), (EX1, EY0, EAV - 0.02), (EX1, EY1, EAV - 0.02), (EX0, EY1, EAV - 0.02)], out=-Z)
    boiler_house(M)
    chimney_base(m)
    yard(m)


def boiler_house(M):
    m = M.m
    bw, bd = BX1 - EX1, BY1 - BY0
    S = sides(m, bw, bd, (EX1 + BX1) / 2, (BY0 + BY1) / 2)
    for name, F in S.items():
        if name == "left":
            continue
        h = bw / 2 if name in ("front", "back") else bd / 2
        top = BH
        if name == "front":
            holes = [(-0.9, 0.9, 0.0, 2.8, WALL)]
        elif name == "right":
            holes = [(u - 0.45, u + 0.45, 1.2, 3.4) for u in (-1.8, 1.0)]
        else:
            holes = []
        if name in ("front", "back"):
            # A lean-to: the wall rises toward the engine house.
            lo, hi = (BH2, BH) if name == "front" else (BH, BH2)
            F.wall("brick", -h, h, 0.0, BH, holes, depth=0.35, reveal="brick")
            fpoly(F, "brick", [(-h, BH), (h, BH), (h, hi), (-h, lo)])
        else:
            F.wall("brick", -h, h, 0.0, top, holes, depth=0.35, reveal="brick")
        F.box("bluebrick", -h - 0.05, h + 0.05, 0.0, 0.7, 0, 0.05)
        F.box("stone", -h - 0.07, h + 0.07, 0.7, 0.8, 0, 0.08)
        for hole in holes:
            a, b, c, e = hole[:4]
            if len(hole) == 5:
                F.quad("doors", a, b, c, e, -0.3)
                for k in range(2):
                    u0, u1 = a + k * (b - a) / 2, a + (k + 1) * (b - a) / 2
                    F.box("doors", u0 + 0.06, u1 - 0.06, c + 0.2, e - 0.2, -0.3, -0.27)
                arch(F, a, b, e + 0.3, rise=0.3, ring=0.3, D=0.35)
            else:
                window(F, a, b, c, e)
    # The lean-to's slate roof.
    o = 0.3
    x0, x1 = EX1, BX1 + o
    for y0, y1 in ((BY0 - o, BY1 + o),):
        m.poly("slate", [(x0, y0, BH2), (x1, y0, BH - o * (BH2 - BH) / bw), (x1, y1, BH - o * (BH2 - BH) / bw), (x0, y1, BH2)], out=(BH2 - BH, 0, bw))
        m.poly("slate", [(x0, y0, BH2 - 0.08), (x1, y0, BH - 0.08 - o * (BH2 - BH) / bw), (x1, y1, BH - 0.08 - o * (BH2 - BH) / bw), (x0, y1, BH2 - 0.08)], out=(-(BH2 - BH), 0, -bw))
    m.box("lead", (x0 - 0.02, BY0 - o, BH2 - 0.05), (x0 + 0.25, BY1 + o, BH2 + 0.1))
    m.box("gutter", (x1, BY0 - o, BH - 0.4), (x1 + 0.12, BY1 + o, BH - 0.25))
    m.box("iron", (x1 + 0.02, BY0 - o + 0.2, 0.1), (x1 + 0.1, BY0 - o + 0.28, BH - 0.3))
    m.poly("dark", [(EX1, BY0, BH - 0.02), (BX1, BY0, BH - 0.02), (BX1, BY1, BH - 0.02), (EX1, BY1, BH - 0.02)], out=-Z)


def chimney_base(m):
    """The chimney's square base behind the boiler house, to the eaves."""
    s = CS0 + 0.2
    m.box("bluebrick", (CX - s - 0.05, CY - s - 0.05, 0.0), (CX + s + 0.05, CY + s + 0.05, 0.9), skip=("z0",))
    m.box("brick", (CX - s, CY - s, 0.9), (CX + s, CY + s, EAV - 0.3), skip=("z0", "z1"))
    m.sweep("stone", 2 * s, 2 * s, [(0.0, EAV - 0.3), (0.1, EAV - 0.3), (0.1, EAV - 0.15), (-0.2, EAV)], CX, CY)


def yard(m):
    """Railings on a low wall along the street with gates on stone piers; valve covers and a standpipe."""
    y = YARD
    for x0, x1 in ((EX0 - 0.6, -1.6), (1.6, BX1 + 0.6)):
        m.box("bluebrick", (x0, y - 0.15, 0.0), (x1, y + 0.15, 0.45))
        m.box("stone", (x0 - 0.02, y - 0.18, 0.45), (x1 + 0.02, y + 0.18, 0.55))
        m.box("iron", (x0, y - 0.03, 0.62), (x1, y + 0.03, 0.68))
        m.box("iron", (x0, y - 0.03, 1.55), (x1, y + 0.03, 1.6))
        n = int((x1 - x0) / 0.13)
        for i in range(n):
            x = x0 + (i + 0.5) * (x1 - x0) / n
            m.box("iron", (x - 0.012, y - 0.012, 0.55), (x + 0.012, y + 0.012, 1.75))
            m.cyl("iron", x, y, 0.03, 1.75, 1.85, seg=4, r1=0.0)
    for x in (-1.6, 1.6):
        sx = x - 0.3 if x < 0 else x
        m.box("stone", (sx, y - 0.3, 0.0), (sx + 0.3 if x < 0 else x + 0.3, y + 0.3, 2.1))
        cx = sx + 0.15
        m.box("stone", (cx - 0.22, y - 0.37, 2.1), (cx + 0.22, y + 0.37, 2.22))
        m.cyl("stone", cx, y, 0.14, 2.22, 2.5, seg=10, r1=0.05)
    # The gates, shut: bars and two rails, a dog bar at the foot, scrolled tops.
    for x0, x1 in ((-1.6, -0.03), (0.03, 1.6)):
        m.box("iron", (x0, y - 0.025, 0.12), (x1, y + 0.025, 0.18))
        m.box("iron", (x0, y - 0.025, 1.0), (x1, y + 0.025, 1.06))
        m.box("iron", (x0, y - 0.025, 1.8), (x1, y + 0.025, 1.86))
        n = int((x1 - x0) / 0.12)
        for i in range(n):
            x = x0 + (i + 0.5) * (x1 - x0) / n
            top = 1.9 + 0.35 * math.sin(math.pi * (x - x0) / (x1 - x0))
            m.box("iron", (x - 0.012, y - 0.012, 0.12), (x + 0.012, y + 0.012, top))
            m.cyl("iron", x, y, 0.028, top, top + 0.1, seg=4, r1=0.0)
    # Cast-iron valve covers on the mains, a standpipe and its wheel.
    for x, yy in ((-3.5, -6.5), (-0.4, -6.2), (3.2, -6.6)):
        m.box("iron", (x - 0.35, yy - 0.25, 0.0), (x + 0.35, yy + 0.25, 0.06))
    sx, sy = 4.6, -5.9
    m.cyl("iron", sx, sy, 0.1, 0.0, 1.0, seg=12)
    m.cyl("iron", sx, sy, 0.14, 0.0, 0.18, seg=12)
    m.cyl("iron", sx, sy, 0.07, 1.0, 1.15, seg=10)
    m.tube("iron", [(sx + 0.3 * math.cos(t), sy + 0.3 * math.sin(t), 1.15) for t in [i / 12 * math.tau for i in range(12)]], 0.02, (0, 0, 1))
    m.box("iron", (sx - 0.04, sy - 0.04, 0.6), (sx + 0.45, sy + 0.04, 0.68))


# ---- roof -----------------------------------------------------------------------------


def roof(M):
    m = M.m
    S = sides(m, EW, ED, ECX, ECY)
    hw = EW / 2
    ridge = EAV + RISE
    # The gables, front and back, coped in stone with kneelers and a finial.
    for name in ("front", "back"):
        F = S[name]
        fpoly(F, "brick", [(-hw, EAV), (hw, EAV), (0, ridge)])
        fpoly(F, "brick", [(-hw, EAV), (hw, EAV), (0, ridge)], -WALL, out=-F.n)
        F.box("bluebrick", -hw * 0.7, hw * 0.7, EAV + 0.6, EAV + 0.75, 0, 0.012)
        if name == "front":
            # A roundel vent in the gable.
            seg = 16
            fpoly(F, "stone", [(math.cos(i / seg * math.tau) * 0.6, EAV + 1.7 + math.sin(i / seg * math.tau) * 0.6) for i in range(seg)], 0.04)
            fpoly(F, "dark", [(math.cos(i / seg * math.tau) * 0.42, EAV + 1.7 + math.sin(i / seg * math.tau) * 0.42) for i in range(seg)], 0.05)
            for k in range(-2, 3):
                F.box("iron", -0.4, 0.4, EAV + 1.7 + k * 0.14 - 0.02, EAV + 1.7 + k * 0.14 + 0.02, 0.05, 0.07)
        for s in (-1, 1):
            a = F.p(s * (hw + 0.1), EAV - 0.05, 0.0)
            b = F.p(0, ridge + 0.15, 0.0)
            mid = F.p(0, 0, -WALL / 2)
            m.strut("stone", (a.x, mid.y, a.z + 0.15), (b.x, mid.y, b.z + 0.15), 0.62, 0.16)
            F.box("stone", s * hw - 0.45 if s > 0 else -hw - 0.05, s * hw + 0.05 if s > 0 else -hw + 0.45, EAV - 0.3, EAV + 0.2, -WALL - 0.05, 0.08)
        F.box("stone", -0.3, 0.3, ridge - 0.05, ridge + 0.35, -WALL - 0.05, 0.08)
        m.cyl("stone", F.p(0, 0, -WALL / 2).x, F.p(0, 0, -WALL / 2).y, 0.12, ridge + 0.35, ridge + 1.0, seg=8, r1=0.04)
    # The slates over the side walls, overhanging the corbelled eaves.
    o = 0.35
    y0, y1 = EY0 + 0.05, EY1 - 0.05
    run = hw + o
    zo = EAV - o * RISE / hw
    for s in (-1, 1):
        xe = ECX + s * (hw + o)
        m.poly("slate", [(xe, y0, zo), (ECX, y0, ridge), (ECX, y1, ridge), (xe, y1, zo)], out=(s * RISE, 0, hw), uvs=None)
        m.poly("slate", [(xe, y0, zo - 0.08), (ECX, y0, ridge - 0.08), (ECX, y1, ridge - 0.08), (xe, y1, zo - 0.08)], out=(-s * RISE, 0, -hw))
        m.box("gutter", (xe - 0.1 if s > 0 else xe - 0.05, y0, zo - 0.2), (xe + 0.05 if s > 0 else xe + 0.1, y1, zo - 0.05))
    del run
    m.strut("ridge", (ECX, y0, ridge + 0.03), (ECX, y1, ridge + 0.03), 0.16)
    lantern(m, ridge)
    shaft(m)


def lantern(m, ridge):
    """A louvred ventilator on the ridge: boarded sides, louvres, a little slate roof."""
    lw, ld = 1.4, 2.6
    z0 = ridge - 0.4
    z1 = ridge + 1.1
    L = sides(m, lw, ld, ECX, ECY, z0)
    for name, F in L.items():
        h = lw / 2 if name in ("front", "back") else ld / 2
        F.quad("cupola", -h + 0.1, h - 0.1, 0.5, z1 - z0 - 0.1, 0.0)
        F.box("trim", -h, h, 0.0, 0.5, -0.02, 0.02)
        for u in (-h, h - 0.1):
            F.box("trim", u, u + 0.1, 0.0, z1 - z0, -0.02, 0.04)
        F.box("trim", -h, h, z1 - z0 - 0.1, z1 - z0, -0.02, 0.04)
    o = 0.25
    for s in (-1, 1):
        xe = ECX + s * (lw / 2 + o)
        m.poly("slate", [(xe, ECY - ld / 2 - o, z1 - 0.05), (ECX, ECY - ld / 2 - o, z1 + 0.6), (ECX, ECY + ld / 2 + o, z1 + 0.6), (xe, ECY + ld / 2 + o, z1 - 0.05)], out=(s * 0.65, 0, lw / 2 + o))
    for y in (ECY - ld / 2 - o, ECY + ld / 2 + o):
        m.poly("trim", [(ECX - lw / 2 - o, y, z1 - 0.05), (ECX + lw / 2 + o, y, z1 - 0.05), (ECX, y, z1 + 0.6)], out=(0, 1 if y > ECY else -1, 0))
    m.strut("ridge", (ECX, ECY - ld / 2 - o, z1 + 0.62), (ECX, ECY + ld / 2 + o, z1 + 0.62), 0.1)
    m.cyl("iron", ECX, ECY, 0.02, z1 + 0.6, z1 + 1.6, seg=6)
    m.box("iron", (ECX - 0.01, ECY - 0.35, z1 + 1.35), (ECX + 0.01, ECY + 0.35, z1 + 1.38))


def shaft(m):
    """The chimney's square shaft from the eaves: tapering, blue-brick bands, an arcaded top under a stone cap."""
    zb = EAV
    top = CT - 2.2
    s = lambda z: CS0 + (CS1 - CS0) * (z - zb) / (top - zb)  # noqa: E731
    zs = [zb + (top - zb) * k / 6 for k in range(7)]
    for za, zz in zip(zs, zs[1:]):
        a, b = s(za), s(zz)
        for (dx0, dy0), (dx1, dy1), out in (((-1, -1), (1, -1), (0, -1, 0)), ((1, -1), (1, 1), (1, 0, 0)), ((1, 1), (-1, 1), (0, 1, 0)), ((-1, 1), (-1, -1), (-1, 0, 0))):
            m.poly("brick", [(CX + dx0 * a, CY + dy0 * a, za), (CX + dx1 * a, CY + dy1 * a, za), (CX + dx1 * b, CY + dy1 * b, zz), (CX + dx0 * b, CY + dy0 * b, zz)], out=out)
        if zz < top - 0.1:
            c = s(zz) + 0.02
            m.box("bluebrick", (CX - c, CY - c, zz - 0.15), (CX + c, CY + c, zz + 0.15), skip=("z0", "z1"))
    # The top: a stone band, an arcade of three openings a side, a corbelled cornice and cap.
    c = CS1 + 0.15
    m.box("stone", (CX - c, CY - c, top), (CX + c, CY + c, top + 0.2))
    z = top + 0.2
    for name, F in sides(m, 2 * c - 0.1, 2 * c - 0.1, CX, CY, z).items():
        h = c - 0.05
        F.wall("brick", -h, h, 0.0, 1.2, [(u - 0.15, u + 0.15, 0.2, 0.95) for u in (-0.42, 0.0, 0.42)], depth=0.12)
        for u in (-0.42, 0.0, 0.42):
            F.quad("dark", u - 0.15, u + 0.15, 0.2, 0.95, -0.12)
            F.box("stone", u - 0.2, u + 0.2, 0.95, 1.05, 0, 0.04)
    z += 1.2
    for k, d in enumerate((0.08, 0.16, 0.26)):
        m.box("brick", (CX - c - d, CY - c - d, z + k * 0.15), (CX + c + d, CY + c + d, z + (k + 1) * 0.15))
    z += 0.45
    m.box("stone", (CX - c - 0.32, CY - c - 0.32, z), (CX + c + 0.32, CY + c + 0.32, z + 0.18))
    m.poly("dark", [(CX - c + 0.15, CY - c + 0.15, z + 0.181), (CX + c - 0.15, CY - c + 0.15, z + 0.181), (CX + c - 0.15, CY + c - 0.15, z + 0.181), (CX - c + 0.15, CY + c - 0.15, z + 0.181)], out=Z)
